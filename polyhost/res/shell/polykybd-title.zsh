# PolyKybd title integration for zsh: put the running command line into the
# terminal window title, so that PolyKybdHost can select the overlay for the
# program running in the terminal (nano, for example).
#
# Installed by PolyKybdHost ("Updates > Show the running command in the
# terminal title" in the tray, or `polyctl shell-integration install`), which
# adds one line to ~/.zshrc that sources this file. Safe to source twice.
# oh-my-zsh, prezto and similar frameworks already do this; both together
# write the same title.

[[ -o interactive ]] || return 0
(( ${+__poly_title_loaded} )) && return 0
typeset -g __poly_title_loaded=1

autoload -Uz add-zsh-hook
__poly_title() { print -rn -- $'\e]2;'"${1//[[:cntrl:]]/}"$'\a' }
add-zsh-hook preexec __poly_title
