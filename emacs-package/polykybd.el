;;; polykybd.el --- Report the Emacs major mode to PolyKybdHost  -*- lexical-binding: t; -*-

;; SPDX-License-Identifier: GPL-3.0-or-later
;; Author: PolyKybd contributors
;; Version: 1.0.0
;; Package-Requires: ((emacs "27.1"))
;; Keywords: convenience, hardware
;; URL: https://github.com/thpoll83/PolyKybdHost

;;; Commentary:

;; `polykybd-mode' tells PolyKybdHost which major mode the selected window
;; shows, so the PolyKybd keycaps show the keys of that mode: the org-mode
;; keys in an Org buffer, the Dired keys in a Dired buffer, the global Emacs
;; keys elsewhere.  It works in a terminal (`emacs -nw') and in a GUI frame.
;;
;; What is sent, and nothing else (no file name, no buffer name, no text):
;;
;;   POST http://127.0.0.1:<polykybd-port>/report   Content-Type: application/json
;;   {"app": "emacs", "url": "emacs://org-mode", "focused": true,
;;    "pid": 4242, "input_age": 0.4, "token": "<only if set>"}
;;
;; With evil-mode active in the buffer the URL also names the evil state:
;; "emacs://org-mode/normal".
;;
;; A report is sent when that URL changes, when an Emacs frame gains or loses
;; focus, and every 3 s as a keep-alive while a frame has focus (the host
;; drops a report older than 8 s).  On focus-out, when the mode is turned off
;; and when Emacs exits, one report with "focused": false and "url": null
;; withdraws it.
;;
;; The network I/O never blocks redisplay or a command: see
;; `polykybd--send'.  Errors (no host running) are ignored.

;;; Code:

(require 'json)

(defgroup polykybd nil
  "Report the Emacs major mode to PolyKybdHost."
  :group 'convenience
  :prefix "polykybd-")

(defcustom polykybd-port 50164
  "Port of PolyKybdHost's report receiver on 127.0.0.1.
The host setting is `browser_report_port'."
  :type 'integer)

(defcustom polykybd-token ""
  "Shared token, only if PolyKybdHost has `browser_report_token' set.
Leave empty otherwise."
  :type 'string)

(defconst polykybd--keepalive 3.0
  "Seconds between keep-alive reports while a frame has focus.")

(defconst polykybd--timeout 2.0
  "Seconds after which an unanswered request is dropped.")

(defconst polykybd--exit-wait 0.3
  "Seconds the report at exit may take in all: connect, send and reply.")

(defvar polykybd--last-input (float-time)
  "When this Emacs last ran a command (a key or mouse input).")

(defvar polykybd--mode nil "Major mode in the last report.")
(defvar polykybd--state nil "Evil state in the last report, or nil.")
(defvar polykybd--url nil "URL of the last report.")
(defvar polykybd--focused nil "Whether the last report said focused.")
(defvar polykybd--timer nil "The keep-alive timer.")
(defvar polykybd--proc nil "The request in flight, or nil.")
(defvar polykybd--queued nil "A report waiting for `polykybd--proc' to finish.")
(defvar polykybd--exiting nil
  "Non-nil once the report at exit is under way: nothing is sent after it.")

;;;; The report

(defun polykybd--token (sym)
  "SYM's name if it is a short plain identifier, else nil.
A mode name from a third-party package can hold any character; anything
outside [A-Za-z0-9_.+-] is not sent."
  (let ((s (and sym (symbolp sym) (symbol-name sym))))
    (and s (<= 1 (length s) 64)
         (string-match-p "\\`[A-Za-z0-9_.+-]+\\'" s)
         s)))

(defun polykybd--current ()
  "The major mode and evil state of the selected window's buffer, as a cons."
  (with-current-buffer (window-buffer (selected-window))
    (cons major-mode
          (and (bound-and-true-p evil-local-mode)
               (boundp 'evil-state)
               (symbol-value 'evil-state)))))

(defun polykybd--url-for (mode state)
  "The pseudo-URL emacs://MODE[/STATE], or nil for an unusable MODE."
  (let ((m (polykybd--token mode))
        (s (polykybd--token state)))
    (and m (if s (format "emacs://%s/%s" m s) (format "emacs://%s" m)))))

(defun polykybd--payload (url focused)
  "The JSON body of one report of URL (nil for none), FOCUSED or not.
Binds json.el's settings, so a caller's own binding cannot change the encoding."
  (let ((json-false :json-false) (json-null nil) (json-encoding-pretty-print nil))
    (json-encode
     `(("app" . "emacs")
       ("url" . ,url)
       ("focused" . ,(if focused t :json-false))
       ("pid" . ,(emacs-pid))
       ("input_age" . ,(/ (round (* 10 (max 0.0 (- (float-time) polykybd--last-input))))
                          10.0))
       ,@(and (stringp polykybd-token) (> (length polykybd-token) 0)
              `(("token" . ,polykybd-token)))))))

(defun polykybd--request (body)
  "The HTTP/1.1 request carrying BODY, as a unibyte string."
  (let ((bytes (encode-coding-string body 'utf-8)))
    (concat (format "POST /report HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n" polykybd-port)
            "Content-Type: application/json\r\n"
            (format "Content-Length: %d\r\n" (string-bytes bytes))
            "Connection: close\r\n\r\n"
            bytes)))

;;;; Sending

;; `make-network-process' with `:nowait t' rather than `url-retrieve'.  Both
;; return before the connection exists, but `url-retrieve' does synchronous
;; work first that can wait: it consults `url-proxy-services' (a proxy would
;; receive a loopback report, or be waited for), the cookie and authentication
;; code may prompt, and every call creates a buffer.  A non-blocking connect to
;; a numeric loopback address needs no DNS lookup and returns at once; the
;; request is written by the sentinel when the socket is open, from the event
;; loop, and a refused or hung connection only ever reaches the sentinel.

(defun polykybd--finish (proc)
  "Drop PROC and send the queued report, if any.
Runs again from PROC's own sentinel when it is deleted; only the first
call finds PROC current, so the queued report is sent once."
  (let ((current (eq proc polykybd--proc)))
    (when current
      (setq polykybd--proc nil))
    (when (process-live-p proc)
      (delete-process proc))
    (when current
      (let ((next polykybd--queued))
        (setq polykybd--queued nil)
        (when next
          (polykybd--send next))))))

(defun polykybd--sentinel (proc event)
  "Write the request once PROC is open; clean up on any other EVENT."
  (if (string-prefix-p "open" event)
      (condition-case nil
          (process-send-string proc (process-get proc 'polykybd-request))
        (error (polykybd--finish proc)))
    (polykybd--finish proc)))

(defun polykybd--filter (proc _output)
  "The host answered: the report was delivered, so close PROC."
  (polykybd--finish proc))

(defun polykybd--send (body)
  "POST BODY to the host without waiting for anything.
While a request is in flight only the newest BODY is kept and sent after it.
Nothing is sent once the report at exit is under way."
  (cond
   (polykybd--exiting nil)
   ((and polykybd--proc (process-live-p polykybd--proc))
    (setq polykybd--queued body))
   (t
    (setq polykybd--proc nil)
    (condition-case nil
        (let ((proc (make-network-process
                     :name "polykybd" :host "127.0.0.1" :service polykybd-port
                     :nowait t :noquery t :coding 'binary :buffer nil
                     :filter #'polykybd--filter :sentinel #'polykybd--sentinel)))
          (process-put proc 'polykybd-request (polykybd--request body))
          (setq polykybd--proc proc)
          (run-with-timer polykybd--timeout nil #'polykybd--finish proc))
      (error nil)))))

(defun polykybd--send-now (body)
  "POST BODY as the last report, in at most `polykybd--exit-wait' seconds.
For `kill-emacs-hook'.  The keep-alive stops and a queued report is
dropped, so no report is sent after this one.  A request still in flight
gets half the time to finish first, so the host does not receive it after
this one.  The connect does not block: a listener that does not accept
costs the deadline, not the system's connect timeout."
  (let* ((start (float-time))
         (deadline (+ start polykybd--exit-wait))
         (request (polykybd--request body))
         (done nil))
    (setq polykybd--exiting t
          polykybd--queued nil)
    (when polykybd--timer
      (cancel-timer polykybd--timer)
      (setq polykybd--timer nil))
    (while (and polykybd--proc (process-live-p polykybd--proc)
                (< (float-time) (+ start (/ polykybd--exit-wait 2))))
      (accept-process-output polykybd--proc 0.02))
    (condition-case nil
        (let ((proc (make-network-process
                     :name "polykybd-exit" :host "127.0.0.1" :service polykybd-port
                     :nowait t :noquery t :coding 'binary :buffer nil
                     :filter (lambda (_proc _output) (setq done t))
                     :sentinel (lambda (proc event)
                                 (if (string-prefix-p "open" event)
                                     (condition-case nil
                                         (process-send-string proc request)
                                       (error (setq done t)))
                                   (setq done t))))))
          (unwind-protect
              (while (and (not done) (< (float-time) deadline))
                (accept-process-output proc 0.02))
            (delete-process proc)))
      (error nil))))

;;;; Events

(defun polykybd--focused-p ()
  "Whether a frame of this Emacs has focus.
A frame whose focus is unknown (a terminal that sends no focus events)
counts as focused.  The frame of a daemon or of --batch, on the initial
terminal, never does."
  (let (found)
    (dolist (f (frame-list) found)
      (unless (or found
                  (equal (terminal-name (frame-terminal f)) "initial_terminal"))
        (when (frame-focus-state f)
          (setq found t))))))

(defun polykybd--report (&optional force)
  "Send a report if the URL or the focus changed, or when FORCE is non-nil.
While no frame has focus only the change to unfocused is sent."
  (let* ((cur (polykybd--current))
         (focused (polykybd--focused-p)))
    (unless (and (eq (car cur) polykybd--mode) (eq (cdr cur) polykybd--state))
      (setq polykybd--mode (car cur)
            polykybd--state (cdr cur)
            polykybd--url (polykybd--url-for (car cur) (cdr cur))
            force (or force focused)))
    (unless (eq focused polykybd--focused)
      (setq force t))
    (setq polykybd--focused focused)
    (when force
      (polykybd--send (if focused
                          (polykybd--payload polykybd--url t)
                        (polykybd--payload nil nil))))))

(defun polykybd--post-command ()
  "Record the input time and report a changed mode."
  (setq polykybd--last-input (float-time))
  (polykybd--report))

(defun polykybd--window-change (&rest _)
  "Report a mode change that ran no command (a timer, a mouse click)."
  (polykybd--report))

(defun polykybd--focus-change ()
  "Report focus in or out.
Gaining focus counts as input, as in the Vim plugin: with several editors
open the host follows the one with the newest input, so without this an
editor that just lost focus would keep answering until a key is pressed
here."
  (when (and (polykybd--focused-p) (not polykybd--focused))
    (setq polykybd--last-input (float-time)))
  (polykybd--report))

(defun polykybd--keepalive ()
  "Re-send the report while a frame has focus."
  (when polykybd--focused
    (polykybd--report t)))

(defun polykybd--withdraw ()
  "Send the final unfocused report (mode off)."
  (polykybd--send (polykybd--payload nil nil)))

(defun polykybd--exit ()
  "Send the final unfocused report as Emacs exits."
  (polykybd--send-now (polykybd--payload nil nil)))

;;;###autoload
(define-minor-mode polykybd-mode
  "Report the major mode to PolyKybdHost, which shows its keys on the keycaps.
Sends only the major mode (and the evil state) of the selected window, to
127.0.0.1 port `polykybd-port'."
  :global t
  :group 'polykybd
  (if polykybd-mode
      (progn
        (setq polykybd--mode nil polykybd--state nil polykybd--url nil
              polykybd--focused nil polykybd--last-input (float-time)
              polykybd--exiting nil)
        (add-hook 'post-command-hook #'polykybd--post-command)
        (add-hook 'window-selection-change-functions #'polykybd--window-change)
        (add-hook 'window-buffer-change-functions #'polykybd--window-change)
        (add-hook 'after-change-major-mode-hook #'polykybd--window-change)
        (add-hook 'kill-emacs-hook #'polykybd--exit)
        (add-function :after after-focus-change-function #'polykybd--focus-change)
        (setq polykybd--timer
              (run-with-timer polykybd--keepalive polykybd--keepalive #'polykybd--keepalive))
        (polykybd--report t))
    (remove-hook 'post-command-hook #'polykybd--post-command)
    (remove-hook 'window-selection-change-functions #'polykybd--window-change)
    (remove-hook 'window-buffer-change-functions #'polykybd--window-change)
    (remove-hook 'after-change-major-mode-hook #'polykybd--window-change)
    (remove-hook 'kill-emacs-hook #'polykybd--exit)
    (remove-function after-focus-change-function #'polykybd--focus-change)
    (when polykybd--timer
      (cancel-timer polykybd--timer)
      (setq polykybd--timer nil))
    (polykybd--withdraw)))

(provide 'polykybd)
;;; polykybd.el ends here
