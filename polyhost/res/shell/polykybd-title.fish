# PolyKybd integration for fish. fish puts the running command into the
# terminal window title itself (fish_title), so this file only adds the Codex
# option: Codex replaces the title with its own, and its default title does not
# name it. With the option the installed line sets __poly_title_codex, and this
# wraps the codex command so that Codex's title starts with "codex". A codex
# function or alias of your own is kept, and so is a terminal_title you set in
# Codex's config.toml.
#
# Installed by PolyKybdHost ("Updates > Show the running command in the
# terminal title" in the tray, or `polyctl shell-integration install --codex`),
# which writes one line that sources this file into
# ~/.config/fish/conf.d/polykybd.fish. Safe to source twice.

status is-interactive; or return 0
set -q __poly_title_loaded; and return 0
set -g __poly_title_loaded 1

if set -q __poly_title_codex; and not functions -q codex
    function codex --description 'codex, with a window title that names it (PolyKybdHost)'
        set -l dir $HOME/.codex
        set -q CODEX_HOME; and set dir $CODEX_HOME
        if test -r $dir/config.toml
            and string match -qr '^\s*(tui\.)?terminal_title\s*=' <$dir/config.toml
            command codex $argv
        else
            command codex -c "tui.terminal_title=['app-name','activity','thread-name','project-name']" $argv
        end
    end
end
