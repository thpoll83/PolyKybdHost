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
