# PolyKybd title integration for zsh: put the running command line into the
# terminal window title, so that PolyKybdHost can select the overlay for the
# program running in the terminal (nano, for example). When the command ends,
# the next prompt writes "user@host: ~/dir", so the program's title (and its
# overlay) does not stay at the prompt; a prompt or theme that sets its own
# title afterwards takes priority.
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
typeset -g __poly_title_set=
__poly_title() {
  print -rn -- $'\e]2;'"${1//[[:cntrl:]]/}"$'\a'
  __poly_title_set=1
}
# First among the precmd hooks, so a theme's own title (oh-my-zsh sets one in
# precmd) is written after it.
__poly_title_reset() {
  [[ -n $__poly_title_set ]] || return 0
  __poly_title_set=
  print -Pn -- $'\e]2;%n@%m: %~\a'
}
add-zsh-hook preexec __poly_title
precmd_functions=(__poly_title_reset ${precmd_functions:#__poly_title_reset})

# Codex replaces the shell's title with its own, and its default title does
# not name it. With the Codex option the installed line sets
# __poly_title_codex, and this wraps the command so that Codex's title starts
# with "codex". A codex alias or function of your own is kept, and so is a
# terminal_title you set in Codex's config.toml.
__poly_codex_title="tui.terminal_title=['app-name','activity','thread-name','project-name']"
__poly_codex_own_title() {
  grep -qsE '^[[:space:]]*(tui\.)?terminal_title[[:space:]]*=' \
    "${CODEX_HOME:-$HOME/.codex}/config.toml"
}
if [[ -n ${__poly_title_codex-} ]] && (( ! ${+functions[codex]} && ! ${+aliases[codex]} )); then
  codex() {
    if __poly_codex_own_title; then command codex "$@"
    else command codex -c "$__poly_codex_title" "$@"; fi
  }
fi
