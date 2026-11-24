"""The Hypothesis settings profiles for tests/fuzz (see tests/fuzz/__init__.py)."""
import os

from hypothesis import HealthCheck, settings
from hypothesis.database import DirectoryBasedExampleDatabase

ENV_VAR = "POLYKYBD_HYPOTHESIS_PROFILE"

# The long profiles set the database and derandomize explicitly: with CI=true (every
# GitHub runner) Hypothesis's own CI defaults are database=None and derandomize=True,
# and a profile inherits them, so the cached .hypothesis/ would stay empty and every run
# would draw the same examples.
_DB = DirectoryBasedExampleDatabase(".hypothesis/examples")

settings.register_profile(
    "default", max_examples=50, deadline=2000, database=None,
    suppress_health_check=[HealthCheck.too_slow])
settings.register_profile(
    "fuzz", max_examples=20000, deadline=None, derandomize=False, database=_DB,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
# scripts/fuzz_paths.py: the default size with a fixed seed, so the modules the run
# imports (some only inside a parser) are the same on every run.
settings.register_profile(
    "paths", max_examples=50, deadline=None, database=None, derandomize=True,
    suppress_health_check=[HealthCheck.too_slow])
# The Wednesday/Sunday CI run (.github/workflows/host-fuzz.yml), one job per module.
settings.register_profile(
    "nightly", max_examples=200000, deadline=None, derandomize=False, database=_DB,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])


def load_profile():
    """Load the profile ``POLYKYBD_HYPOTHESIS_PROFILE`` names (``default`` if unset)."""
    settings.load_profile(os.environ.get(ENV_VAR, "default"))
