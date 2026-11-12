# Sourcetree overlays — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `sourcetree_template` (3 files) | Windows: 34 keys |
| `sourcetree_template_mac` (4 files) | macOS: 51 keys |

Sourcetree for Windows (a WPF program) and Sourcetree for Mac are separate
programs. 22 keys do the same thing in both and are written once with
`CMDCTRL`; the others are scoped to one platform. Sourcetree has no Linux
build.

The Windows executable is `SourceTree.exe` (File table of
`SourcetreeEnterpriseSetup_3.4.33.msi`) and the macOS bundle executable is
`Sourcetree` (`CFBundleExecutable` of 4.2.20). Both map to `sourcetree`.
Neither name was checked on a running install.

## Shortcut references

Atlassian's Sourcetree documentation has no keyboard shortcut table. These
sources were used instead:

- **macOS**: the menu of Sourcetree 4.2.20,
  `Sourcetree.app/Contents/Resources/English.lproj/MainMenu.nib`, from
  <https://product-downloads.atlassian.com/software/sourcetree/ga/Sourcetree_4.2.20_324.zip>
  (read 2026-11-05). The key equivalents agree with Atlassian's Sourcetree
  cheat sheet for Dash, written by the Sourcetree for Mac team
  (<https://github.com/Kapeli/cheatsheets/blob/master/cheatsheets/Sourcetree.rb>,
  announced in "Tip from the team: workflow and keyboard shortcuts",
  <https://community.atlassian.com/forums/Sourcetree-articles/Tip-from-the-team-workflow-and-keyboard-shortcuts/ba-p/709521>).
  The menu adds the keys the cheat sheet lacks (Commit all, Commit selected,
  View remote, Repository details, Filter in sidebar, Full screen).
- **Windows**: the `InputBindings` of the main window and the
  `InputGestureText` of its menu items in Sourcetree 3.4.33
  (`SourcetreeEnterpriseSetup_3.4.33.msi`,
  <https://www.sourcetreeapp.com/download-archives>, read 2026-11-05).

### Left out

- Windows Ctrl+Tab and Ctrl+Shift+Tab (next and previous tab): the menu shows
  Ctrl+Tab as "Next tab", but the key binding sends Ctrl+Shift+Tab to "Next
  tab" and Ctrl+Tab to "Previous tab", so the direction is uncertain.
- Windows Ctrl+Shift+D: a key binding to an internal "draft commit" command
  that no menu item names.
- Space (Quick Look, macOS), Alt+F4 / Cmd+Q, Cmd+H, Cmd+M and the other macOS
  window keys.
- Cut, Copy, Paste, Select all, Undo, Redo, Find and the spelling items of the
  macOS Edit menu: the standard keys of every text field.
- The Bookmarks window keys on Windows (Ctrl+N, Ctrl+Shift+N new folder): they
  act only in that window.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- `clone`, `commit`, `push`, `pull`, `fetch`, `newbranch`, `merge`, `stash`,
  `discard`, `changes`, `history`, `shell`, `pullrequest`, `viewongithub`,
  `repolist`, `filter`, `fullscreen` and `update` are copied from
  `../githubdesktop/icons` (same sources and licences), so both git clients
  show the same picture for the same action.
- Settings, Bold and Italic are drawn by the shared concept renderer.
- ESC: the Sourcetree mark from Simple Icons (CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
