;; Dump the command each single key (with modifiers) runs, per major mode.
(require 'org)
(require 'dired)
(defvar keys
  (append (mapcar #'char-to-string (number-sequence ?a ?z))
          (mapcar #'char-to-string (number-sequence ?0 ?9))
          '("-" "=" "[" "]" "\\" ";" "'" "`" "," "." "/"
            "<" ">" "%" "^" "!" "&" "*" "(" ")" "{" "}" "@" "#" "$" "~" "?" "+" "_" ":" "\"" "|")
          '("<f1>" "<f2>" "<f3>" "<f4>" "<f5>" "<f6>" "<f7>" "<f8>" "<f9>" "<f10>" "<f11>" "<f12>"
            "<left>" "<right>" "<up>" "<down>" "<home>" "<end>" "<prior>" "<next>"
            "<insert>" "<delete>" "<backspace>" "DEL" "RET" "TAB" "SPC" "<return>" "<tab>")))
(defvar mods '("" "C-" "M-" "S-" "C-S-" "M-S-" "C-M-"))
(defun dump (name setup)
  (with-temp-buffer
    (funcall setup)
    (dolist (m mods)
      (dolist (k keys)
        (let* ((ks (concat m k))
               (v (ignore-errors (kbd ks)))
               (b (and v (ignore-errors (key-binding v)))))
          (when (and b (not (memq b '(self-insert-command org-self-insert-command undefined))))
            (princ (format "%s\t%s\t%s\n" name ks (if (keymapp b) "PREFIX" b)))))))))
(dump "global" #'fundamental-mode)
(dump "org" #'org-mode)
(dump "dired" (lambda () (dired-mode default-directory)))
