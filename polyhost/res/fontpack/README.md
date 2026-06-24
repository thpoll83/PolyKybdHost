# Bundled font pack

Drop the built PolyKybd **`.plyf`** font pack here and it ships with the host.
On a fresh keyboard connect the host compares the keyboard's loaded pack
`content_version` against the newest `.plyf` in this directory and, if the
keyboard is older or has no pack, flashes it automatically (see
`polyhost/services/fontpack_bundle.py` + `PolyCore._fontpack_autocheck_job`).

- The pack is produced by the firmware repo's
  `keyboards/polykybd/fonts/generate_fonts.py --emit-pack <out.plyf>`
  (built with the pinned `fontconvert` for byte-reproducibility).
- With **no** `.plyf` here the feature is inert — nothing is flashed.
- Auto-flash is **self-terminating** (only flashes a strictly-older / missing
  pack, never downgrades) and fires at most once per host process. Disable it
  with the `fontpack_auto_flash` setting; override the source file with
  `fontpack_path`. A manual `polyctl fontpack flash <pack>` is always available.

The release build is responsible for placing the current `.plyf` here.
