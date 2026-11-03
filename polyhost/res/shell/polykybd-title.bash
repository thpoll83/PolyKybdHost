# PolyKybd title integration for bash: put the running command line into the
# terminal window title, so that PolyKybdHost can select the overlay for the
# program running in the terminal (nano, for example). The prompt's own title
# comes back when the command ends.
#
# Installed by PolyKybdHost ("Updates > Show the running command in the
# terminal title" in the tray, or `polyctl shell-integration install`), which
# adds one line to ~/.bashrc that sources this file. Safe to source twice.

# Interactive shells only, and only once per shell.
case $- in *i*) ;; *) return 0 ;; esac
[ -n "${__poly_title_loaded-}" ] && return 0
__poly_title_loaded=1

__poly_title_armed=
__poly_title_ready=
__poly_title_prev=

# With bash-preexec: its preexec hook gets the command line.
__poly_title_preexec() {
  printf '\033]2;%s\007' "${1//[[:cntrl:]]/}"
}

# Without it: a DEBUG trap writes the first command run after the command
# line is read. On bash 4.4 and later PS0 arms it, which is expanded after the
# line is read, so the commands of PROMPT_COMMAND (also ones added after this
# file) never take the title; the subscript assignment sets the flag and
# expands to nothing. Older bash (macOS /bin/bash is 3.2) has no PS0, and
# the last command of PROMPT_COMMAND arms it.
__poly_title_cmd() {
  [ -n "$__poly_title_armed" ] || return 0
  __poly_title_armed=
  printf '\033]2;%s\007' "${BASH_COMMAND//[[:cntrl:]]/}"
}

# Runs once, at the first prompt. A sourced file does not see a DEBUG trap set
# outside it, so PROMPT_COMMAND reads the trap at top level into
# __poly_title_prev and calls this; a trap that was set before runs first.
# bash-preexec may also be loaded after this file, so it is checked here.
__poly_title_setup() {
  __poly_title_ready=1
  if [ -n "${bash_preexec_imported-}${__bp_imported-}" ]; then
    preexec_functions+=(__poly_title_preexec)
    return 0
  fi
  __poly_title_prev=${__poly_title_prev#trap -- \'}
  __poly_title_prev=${__poly_title_prev%\' DEBUG}
  __poly_title_prev=${__poly_title_prev//\'\\\'\'/\'}
  if [ -n "$__poly_title_prev" ]; then
    trap 'eval "$__poly_title_prev"; __poly_title_cmd' DEBUG
  else
    trap '__poly_title_cmd' DEBUG
  fi
  if __poly_title_has_ps0; then
    PS0="${PS0-}"'${__poly_title_none[__poly_title_armed=1]}'
  fi
}

__poly_title_has_ps0() {
  (( BASH_VERSINFO[0] > 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 4) ))
}

__poly_title_pc='[ -n "$__poly_title_ready" ] || { __poly_title_prev=$(trap -p DEBUG); __poly_title_setup; }'
__poly_title_has_ps0 || __poly_title_pc+='; __poly_title_armed=1'
if [[ "$(declare -p PROMPT_COMMAND 2>/dev/null)" == "declare -a"* ]]; then
  PROMPT_COMMAND+=("$__poly_title_pc")
else
  # Drop a trailing ";" or blank, which would make "; ;" a syntax error.
  __poly_title_old=${PROMPT_COMMAND-}
  while [[ "$__poly_title_old" == *[\;[:space:]] ]]; do
    __poly_title_old=${__poly_title_old%?}
  done
  PROMPT_COMMAND="${__poly_title_old:+$__poly_title_old; }$__poly_title_pc"
  unset __poly_title_old
fi
unset __poly_title_pc
