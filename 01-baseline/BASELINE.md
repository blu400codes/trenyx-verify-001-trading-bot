# Baseline — the target's own suite, unplanted

- Target: gr8monk3ys/trading-bot @ 52b8dffebb683ecadff753f5efc178b4ea21a029
- Environment: macOS, Python 3.12.14 (Homebrew), isolated venv, `pip install -r requirements.txt`
  plus two additions the suite needed to collect/run: `httpx2` (required by
  `tests/unit/misc/test_web_app_auth.py` via starlette's test client — out of scope
  file, but pytest aborts collection without it) and `pytest-timeout`.
- Command: `python -m pytest -q -p no:cacheprovider -rf --timeout=300`
- Result: **1921 passed, 11 skipped, 0 failed, 66 warnings, 46.97s** (2026-08-24).
- Pre-existing failures: none (`baseline_failures.txt` is empty by construction).

Note on the suite's shape: ~46k lines of tests across 121 files; 57% of the repo's
commits are `Co-Authored-By: Claude`. The detection matrix in `03-planted-defects/`
measures what this suite catches when the implementation is deliberately wrong.
