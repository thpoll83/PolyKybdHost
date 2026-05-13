---
name: fix-debugpy-wmi
description: Fix the "KeyboardInterrupt in platform._wmi_query" crash that kills the first debugpy launch on Windows (Python 3.13 bug). Creates a sitecustomize.py in the venv's site-packages that pre-warms platform.uname() before debugpy initialises, so the WMI COM subsystem is ready and the second-run-works issue disappears.
---

# Fix debugpy WMI crash on first launch (Python 3.13 / Windows)

## Symptom

First debug launch in VS Code fails with a traceback ending in:

```
File "C:\Program Files\Python313\Lib\platform.py", line 330, in _wmi_query
    data = _wmi.exec_query(...)
KeyboardInterrupt
```

Second launch (without touching anything) succeeds. This is a Python 3.13 race condition: the WMI COM subsystem is not yet initialised when debugpy's `log.py` calls `platform.platform()` on the very first attach.

## Fix

Create `sitecustomize.py` in the venv's `Lib\site-packages\` directory. Python imports this file automatically at interpreter startup — before debugpy — so WMI is warm by the time it's needed.

## Procedure

1. **Locate the venv site-packages directory.**

   From the repo root (`PolyKybdHost/`), the path is:
   ```
   .venv\Lib\site-packages\
   ```
   Absolute example: `c:\Users\john.doe\repositories\PolyKybdHost\.venv\Lib\site-packages\`

   Confirm the directory exists before writing. If it doesn't, the venv may not be installed — tell the user to run `pip install -e .` first.

2. **Check for an existing `sitecustomize.py`.**

   - If absent: create it (step 3).
   - If present and already contains the pre-warm block: report "already applied, nothing to do".
   - If present but does not contain the pre-warm block: append the block at the end with a blank line separator.

3. **Write (or append) the pre-warm block:**

   ```python
   # Pre-warm WMI to avoid KeyboardInterrupt on first debugpy attach (Python 3.13 bug).
   try:
       import platform
       platform.uname()
   except Exception:
       pass
   ```

4. **Verify** by printing the final contents of `sitecustomize.py` so the user can confirm it looks right.

5. **Tell the user**: the fix takes effect immediately — no venv reinstall needed. The next VS Code debug launch (including the very first one) should succeed.

## Notes

- The file path uses capital `Lib` on Windows (unlike Linux `lib`). Get this right.
- `sitecustomize.py` is a standard Python mechanism — it is not part of any package and won't be overwritten by `pip install` or venv recreation (the file is in `site-packages`, not tracked by pip).
- If the user is on Linux/macOS (unlikely for this bug, which is Windows-only), the path is `.venv/lib/pythonX.Y/site-packages/sitecustomize.py`.
- Do not modify `usercustomize.py` or `PYTHONSTARTUP` — `sitecustomize.py` is the correct, earliest hook.
