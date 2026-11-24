"""Property and fuzz tests (Hypothesis).

Every module here imports :mod:`tests.fuzz.profile` first, which registers four
settings profiles and loads one:

* ``default``: 50 examples per test and a 2 s deadline, so the normal suite stays fast.
* ``fuzz``: 20000 examples per test, no deadline, for a long run.
* ``paths``: 50 examples with a fixed seed; ``scripts/fuzz_paths.py`` uses it.
* ``nightly``: 200000 examples per test, no deadline; the Wednesday/Sunday CI run.

Select the long profile with ``POLYKYBD_HYPOTHESIS_PROFILE=fuzz`` (docs/testing.md).
"""
