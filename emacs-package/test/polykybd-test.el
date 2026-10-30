;;; polykybd-test.el --- Tests for polykybd.el  -*- lexical-binding: t; -*-

;; SPDX-License-Identifier: GPL-3.0-or-later

;;; Commentary:

;; emacs -Q --batch -L emacs-package -l emacs-package/test/polykybd-test.el \
;;       -f ert-run-tests-batch-and-exit
;;
;; The end-to-end tests run a loopback HTTP listener inside Emacs and check
;; what the mode sends.  --batch has no focused frame, so they set the focus
;; through `polykybd--focused-p'.

;;; Code:

(require 'ert)
(require 'cl-lib)
(require 'json)
(require 'polykybd)

;;;; A loopback listener that records each request body

(defvar polykybd-test--bodies nil "Request bodies received, oldest first.")

(defun polykybd-test--filter (proc chunk)
  (let ((buf (concat (or (process-get proc 'buf) "") chunk)))
    (process-put proc 'buf buf)
    (when (string-match "\r\n\r\n" buf)
      (let* ((head (substring buf 0 (match-beginning 0)))
             (body (substring buf (match-end 0)))
             (len (and (string-match "Content-Length: \\([0-9]+\\)" head)
                       (string-to-number (match-string 1 head)))))
        (when (and len (>= (string-bytes body) len))
          (setq polykybd-test--bodies
                (append polykybd-test--bodies
                        (list (cons head (decode-coding-string body 'utf-8)))))
          (process-send-string proc "HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n{\"ok\":true}")
          (delete-process proc))))))

(defmacro polykybd-test--with-listener (&rest body)
  "Run BODY with a listener on an ephemeral port and `polykybd-port' set to it."
  (declare (indent 0))
  `(let* ((polykybd-test--bodies nil)
          (server (make-network-process
                   :name "polykybd-test" :server t :host "127.0.0.1" :service t
                   :coding 'binary :noquery t :filter #'polykybd-test--filter))
          (polykybd-port (process-contact server :service)))
     (unwind-protect (progn ,@body)
       (when polykybd-mode (polykybd-mode -1))
       (polykybd-test--wait-quiet)
       (delete-process server))))

(defun polykybd-test--wait (n)
  "Process events until N bodies have arrived (at most 3 s)."
  (let ((deadline (+ (float-time) 3.0)))
    (while (and (< (length polykybd-test--bodies) n) (< (float-time) deadline))
      (accept-process-output nil 0.05))))

(defun polykybd-test--wait-quiet ()
  "Process events for 0.3 s."
  (let ((deadline (+ (float-time) 0.3)))
    (while (< (float-time) deadline)
      (accept-process-output nil 0.05))))

(defun polykybd-test--json (n)
  "Body N (0-based) as an alist."
  (let ((json-object-type 'alist) (json-key-type 'string) (json-false :false))
    (json-read-from-string (cdr (nth n polykybd-test--bodies)))))

(defmacro polykybd-test--focused (var &rest body)
  "Run BODY with `polykybd--focused-p' answering the value of VAR."
  (declare (indent 1))
  `(cl-letf (((symbol-function 'polykybd--focused-p) (lambda () ,var)))
     ,@body))

;;;; Pure parts

(ert-deftest polykybd-url-for ()
  (should (equal (polykybd--url-for 'org-mode nil) "emacs://org-mode"))
  (should (equal (polykybd--url-for 'dired-mode nil) "emacs://dired-mode"))
  (should (equal (polykybd--url-for 'c++-mode nil) "emacs://c++-mode"))
  (should (equal (polykybd--url-for 'org-mode 'normal) "emacs://org-mode/normal"))
  ;; A state that is not a plain identifier is dropped, a mode makes no URL.
  (should (equal (polykybd--url-for 'org-mode (intern "a/b")) "emacs://org-mode"))
  (should-not (polykybd--url-for (intern "my mode") nil))
  (should-not (polykybd--url-for nil nil)))

(ert-deftest polykybd-payload-fields ()
  (let ((polykybd-token "")
        (polykybd--last-input (- (float-time) 2.0)))
    (let ((j (let ((json-object-type 'alist) (json-key-type 'string) (json-false :false))
               (json-read-from-string (polykybd--payload "emacs://org-mode" t)))))
      (should (equal (sort (mapcar #'car j) #'string<)
                     '("app" "focused" "input_age" "pid" "url")))
      (should (equal (cdr (assoc "app" j)) "emacs"))
      (should (eq (cdr (assoc "focused" j)) t))
      (should (= (cdr (assoc "pid" j)) (emacs-pid)))
      (should (<= 1.9 (cdr (assoc "input_age" j)) 2.5)))
    (let ((j (let ((json-object-type 'alist) (json-key-type 'string) (json-false :false))
               (json-read-from-string (polykybd--payload nil nil)))))
      (should (eq (cdr (assoc "url" j)) nil))
      (should (assoc "url" j))
      (should (eq (cdr (assoc "focused" j)) :false))))
  (let ((polykybd-token "s3cret"))
    (should (string-match-p "\"token\":\"s3cret\"" (polykybd--payload "emacs://x" t)))))

(ert-deftest polykybd-request-counts-bytes ()
  (let* ((polykybd-port 50164)
         (req (polykybd--request "{\"a\":\"é\"}")))
    (should (string-match-p "\\`POST /report HTTP/1\\.1\r\n" req))
    (should (string-match-p "Content-Type: application/json\r\n" req))
    (should (string-match-p "Connection: close\r\n" req))
    ;; 9 characters, 10 bytes in UTF-8.
    (should (string-match-p "Content-Length: 10\r\n" req))
    (should-not (multibyte-string-p req))))

;;;; End to end, against the loopback listener

(ert-deftest polykybd-reports-the-mode-and-focus ()
  (polykybd-test--with-listener
   (let ((focus t))
     (polykybd-test--focused focus
                             (with-temp-buffer
                               (switch-to-buffer (current-buffer))
                               (org-mode)
                               (polykybd-mode 1)
                               (polykybd-test--wait 1)
                               (should (string-match-p "\\`POST /report HTTP/1\\.1"
                                                       (car (nth 0 polykybd-test--bodies))))
                               (should (equal (cdr (assoc "url" (polykybd-test--json 0))) "emacs://org-mode"))
                               (should (eq (cdr (assoc "focused" (polykybd-test--json 0))) t))
                               ;; A command that changes nothing sends nothing.
                               (polykybd--post-command)
                               (polykybd-test--wait-quiet)
                               (should (= (length polykybd-test--bodies) 1))
                               ;; A mode change is sent.
                               (dired-mode default-directory)
                               (polykybd--post-command)
                               (polykybd-test--wait 2)
                               (should (equal (cdr (assoc "url" (polykybd-test--json 1))) "emacs://dired-mode"))
                               ;; Focus out: one unfocused report with no URL.
                               (setq focus nil)
                               (polykybd--focus-change)
                               (polykybd-test--wait 3)
                               (should (eq (cdr (assoc "focused" (polykybd-test--json 2))) :false))
                               (should (null (cdr (assoc "url" (polykybd-test--json 2)))))
                               ;; Unfocused: a mode change and the keep-alive send nothing.
                               (fundamental-mode)
                               (polykybd--post-command)
                               (polykybd--keepalive)
                               (polykybd-test--wait-quiet)
                               (should (= (length polykybd-test--bodies) 3))
                               ;; Focus in: the current mode again.
                               (setq focus t)
                               (polykybd--focus-change)
                               (polykybd-test--wait 4)
                               (should (equal (cdr (assoc "url" (polykybd-test--json 3))) "emacs://fundamental-mode"))
                               ;; The keep-alive re-sends while focused.
                               (polykybd--keepalive)
                               (polykybd-test--wait 5)
                               (should (equal (cdr (assoc "url" (polykybd-test--json 4))) "emacs://fundamental-mode"))
                               ;; Turning the mode off withdraws the report.
                               (polykybd-mode -1)
                               (polykybd-test--wait 6)
                               (should (eq (cdr (assoc "focused" (polykybd-test--json 5))) :false)))))))

(ert-deftest polykybd-input-age-follows-commands-not-keepalives ()
  (polykybd-test--with-listener
   (polykybd-test--focused t
                           (with-temp-buffer
                             (switch-to-buffer (current-buffer))
                             (polykybd-mode 1)
                             (polykybd-test--wait 1)
                             (setq polykybd--last-input (- (float-time) 5.0))
                             (polykybd--keepalive)
                             (polykybd-test--wait 2)
                             (should (>= (cdr (assoc "input_age" (polykybd-test--json 1))) 4.9))
                             (polykybd--post-command)
                             (polykybd--keepalive)
                             (polykybd-test--wait 3)
                             (should (< (cdr (assoc "input_age" (polykybd-test--json 2))) 1.0))))))

(ert-deftest polykybd-evil-state-is-part-of-the-url ()
  (polykybd-test--with-listener
   (polykybd-test--focused t
                           (with-temp-buffer
                             (switch-to-buffer (current-buffer))
                             (org-mode)
                             (setq-local evil-local-mode t)
                             (setq-local evil-state 'insert)
                             (polykybd-mode 1)
                             (polykybd-test--wait 1)
                             (should (equal (cdr (assoc "url" (polykybd-test--json 0))) "emacs://org-mode/insert"))
                             (setq-local evil-state 'normal)
                             (polykybd--post-command)
                             (polykybd-test--wait 2)
                             (should (equal (cdr (assoc "url" (polykybd-test--json 1))) "emacs://org-mode/normal"))))))

(ert-deftest polykybd-no-host-is-silent-and-does-not-block ()
  ;; Find a port with nothing listening: open a listener, note it, close it.
  (let* ((s (make-network-process :name "probe" :server t :host "127.0.0.1"
                                  :service t :noquery t))
         (polykybd-port (process-contact s :service)))
    (delete-process s)
    (polykybd-test--focused t
                            (let ((t0 (float-time)))
                              (polykybd--send (polykybd--payload "emacs://org-mode" t))
                              (should (< (- (float-time) t0) 0.1))
                              (polykybd-test--wait-quiet)
                              (should-not (and polykybd--proc (process-live-p polykybd--proc)))
                              (polykybd--send-now (polykybd--payload nil nil))))))

(ert-deftest polykybd-batch-frame-is-never-focused ()
  ;; --batch and a daemon have only the frame on the initial terminal.
  (should-not (polykybd--focused-p)))

(provide 'polykybd-test)
;;; polykybd-test.el ends here
