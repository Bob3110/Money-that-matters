"""
Guards the app's core honesty rule: there is no sample/placeholder/demo data
module anywhere. This test fails LOUDLY (not skips) if one reappears, and
also scans source files for a small set of red-flag identifiers that
typically mark fabricated fixtures being used as if they were live data.

This intentionally does NOT forbid fixtures inside tests/ themselves (those
are fine and necessary) -- it scans only app/, the actual served code.
"""

from __future__ import annotations

import ast
import os

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")

FORBIDDEN_MODULE_NAME_FRAGMENTS = ("sample_data", "mock_data", "fake_data", "demo_data", "placeholder_data")

# Identifiers that, if found assigned at module level in app/ (not tests/),
# strongly suggest a hardcoded fixture is standing in for a live fetch.
FORBIDDEN_TOP_LEVEL_NAMES = {"SAMPLE_TICKERS", "MOCK_TRANSACTIONS", "DEMO_HEADLINES", "FAKE_INSIDERS", "PLACEHOLDER_ITEMS"}


def _all_app_py_files() -> list[str]:
    files = []
    for root, _dirs, filenames in os.walk(APP_DIR):
        for fn in filenames:
            if fn.endswith(".py"):
                files.append(os.path.join(root, fn))
    return files


def test_no_sample_data_module_file_exists():
    for path in _all_app_py_files():
        basename = os.path.basename(path).lower()
        for fragment in FORBIDDEN_MODULE_NAME_FRAGMENTS:
            assert fragment not in basename, (
                f"Found a forbidden sample-data-style module: {path}. "
                "There is no sample, placeholder, or demo data anywhere in "
                "this app, even clearly labeled -- see build spec honesty rules."
            )


def test_no_forbidden_top_level_fixture_names_in_app_code():
    for path in _all_app_py_files():
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in FORBIDDEN_TOP_LEVEL_NAMES:
                        raise AssertionError(
                            f"Found forbidden fixture-style assignment '{target.id}' "
                            f"in {path}. Real feeds must render an honest empty "
                            "state instead of a hardcoded stand-in."
                        )


def test_ticker_universe_seed_is_not_fabricated_placeholder_tickers():
    """The seed file must either be empty (honest 'not yet populated' state)
    or contain what look like real ticker symbols -- not obviously fake
    placeholders like 'FAKE1', 'TEST', 'SAMPLE'."""
    import json

    seed_path = os.path.join(APP_DIR, "data", "ticker_universe_seed.json")
    if not os.path.exists(seed_path):
        return  # honest empty state is fine
    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    forbidden = {"FAKE", "TEST", "SAMPLE", "DEMO", "PLACEHOLDER", "XXXX"}
    for ticker in data:
        assert ticker.strip().upper() not in forbidden, (
            f"Ticker universe seed contains a placeholder-looking value: {ticker!r}"
        )
