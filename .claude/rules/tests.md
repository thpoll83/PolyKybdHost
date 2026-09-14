---
paths:
  - "tests/**/*_test.py"
  - "scripts/run_tests.py"
---
# Writing tests here

Full notes: `docs/testing.md` · `docs/dev-environment.md`.

- ⚠️ **Check the test COUNT changed, not just that the suite is green.** Methods
  appended after a trailing `if __name__ == "__main__":` become part of the `if` body:
  they parse, never run, and never fail. A missing dependency is the same trap in
  reverse — it DELETES tests (1982 vs 2447 on one tree) while the run still looks
  substantial.
- ⚠️ **`patch.object(Class, "method")` does NOT reach a fixture that already BOUND that
  method**, which this repo's fixture idiom does constantly. Drive the real input, or
  override the attribute on the instance.
- ⚠️ **A stale `.pyc` can survive a correct fix** — invalidation is (mtime, size), so a
  length-neutral edit in the same second is invisible. Clear `__pycache__` after
  RESTORING too, not only after editing.
- **RUN the real entry point once before believing a mocked suite.**
- **Use `.venv/bin/python`**, and `xvfb-run -a` for GUI tests (never two chained).
