# PolyKybd context reporter: Houdini runs every uiready.py on HOUDINI_PATH once
# its UI is ready. This one only starts the reporter (../python/polykybd_houdini).
import os as _pk_os
import sys as _pk_sys

_pk_dir = _pk_os.path.join(_pk_os.environ.get("POLYKYBD_HOUDINI", ""), "python")
if _pk_os.path.isdir(_pk_dir) and _pk_dir not in _pk_sys.path:
    _pk_sys.path.append(_pk_dir)
try:
    import polykybd_houdini as _pk
    _pk.start()
except Exception:  # noqa: BLE001 -- never stop Houdini's start-up
    import traceback as _pk_tb
    _pk_tb.print_exc()
