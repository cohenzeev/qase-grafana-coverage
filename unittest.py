"""
Tests for generate_dashboard.py.

Run:
  python3 unittest.py

Note: this file is named `unittest.py` per request, which shadows the stdlib
`unittest` module on sys.path. We therefore use plain `assert` + a small
runner instead of the stdlib framework.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

import generate_dashboard as gd


class _Skip(Exception):
    """Raised by a test to mark itself skipped (e.g. missing credentials)."""


def _load_env_file() -> None:
    """Best-effort load of ./.env so live tests can pick up QASE_API_TOKEN
    without requiring `set -a; source .env`."""
    env = Path(__file__).parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


SAMPLE_STATS = {
    "IAO": {"total": 1000, "automated": 100, "to_be_automated":  50, "manual": 850, "coverage_pct": 10.0},
    "AL":  {"total":  200, "automated":  20, "to_be_automated":  30, "manual": 150, "coverage_pct": 10.0},
    "IAI": {"total":  300, "automated":   0, "to_be_automated":  10, "manual": 290, "coverage_pct":  0.0},
}


def _field(frame: dict, name: str) -> dict:
    return next(f for f in frame["fields"] if f["name"] == name)


# ---------- 1. combined_stats ----------

def test_combined_stats_sums_across_projects():
    c = gd.combined_stats(SAMPLE_STATS)
    assert c["total"]           == 1500, c
    assert c["automated"]       ==  120, c
    assert c["to_be_automated"] ==   90, c
    assert c["manual"]          == 1290, c
    # 120 / 1500 = 8.0%
    assert c["coverage_pct"]    ==  8.0, c


# ---------- 2. combined_stats edge case ----------

def test_combined_stats_empty_returns_zeroes():
    c = gd.combined_stats({})
    assert c == {
        "total": 0, "automated": 0, "to_be_automated": 0,
        "manual": 0, "coverage_pct": 0.0,
    }, c


# ---------- 3. pie_panel snapshotData ----------

def test_pie_panel_carries_inline_snapshot_data():
    panel = gd.pie_panel(99, "IAO pie", SAMPLE_STATS["IAO"],
                         {"h": 10, "w": 8, "x": 0, "y": 3})

    assert panel["type"] == "piechart"
    assert panel["datasource"] is None,     "pie panel must not reference a datasource"
    assert "snapshotData" in panel,         "pie panel must carry inline snapshotData"

    frame = panel["snapshotData"][0]
    assert _field(frame, "status")["values"] == ["Automated", "To be automated", "Manual"]
    assert _field(frame, "count")["values"]  == [100, 50, 850]


# ---------- 4. comparison_table_panel ----------

def test_comparison_table_panel_has_one_row_per_project():
    panel = gd.comparison_table_panel(
        77, "Comparison", SAMPLE_STATS,
        {"h": 10, "w": 14, "x": 10, "y": 13},
    )

    assert panel["type"] == "table"
    assert panel["datasource"] is None

    frame = panel["snapshotData"][0]
    assert _field(frame, "Project")["values"]   == ["IAO", "AL", "IAI"]
    assert _field(frame, "Total")["values"]     == [1000, 200, 300]
    assert _field(frame, "Automated")["values"] == [100,  20,   0]
    assert _field(frame, "Manual")["values"]    == [850, 150, 290]


# ---------- 5. build_dashboard structure ----------

def test_build_dashboard_has_banner_pies_and_table_only():
    dash = gd.build_dashboard(SAMPLE_STATS, "2026-05-12 12:00 UTC")

    assert dash["uid"]   == "qase-automation-coverage"
    assert dash["title"] == "Qase Automation Coverage — IAO, AL & IAI"
    assert "snapshot" in dash, "dashboard root must have snapshot block"
    assert "__inputs" not in dash, "dashboard must not require any datasource input"

    types = [p["type"] for p in dash["panels"]]
    assert types.count("text")     == 1, f"expected 1 banner, got {types}"
    assert types.count("piechart") == 4, f"expected 4 pies (3 projects + combined), got {types}"
    assert types.count("table")    == 1, f"expected 1 comparison table, got {types}"
    assert "stat" not in types,           f"stat panels were removed; got {types}"


# ---------- 6. live Qase coverage fetch ----------

def test_fetch_project_stats_from_qase_api():
    """Hit the real Qase API for each configured project and verify we get
    back a sane coverage breakdown. Skipped if QASE_API_TOKEN isn't set."""
    _load_env_file()
    token = os.environ.get("QASE_API_TOKEN")
    if not token:
        raise _Skip("QASE_API_TOKEN not set — skipping live Qase fetch")

    expected_keys = {"total", "automated", "to_be_automated", "manual", "coverage_pct"}

    for p in gd.PROJECTS:
        code = p["code"]
        s = gd.fetch_project_stats(token, code)

        assert set(s) == expected_keys,         f"{code}: missing keys, got {s}"
        assert s["total"] > 0,                  f"{code}: expected total > 0, got {s}"
        assert s["automated"]       >= 0,       f"{code}: negative automated, got {s}"
        assert s["to_be_automated"] >= 0,       f"{code}: negative to_be_automated, got {s}"
        assert s["manual"]          >= 0,       f"{code}: negative manual, got {s}"
        assert s["automated"] + s["to_be_automated"] + s["manual"] == s["total"], (
            f"{code}: parts must sum to total, got {s}"
        )
        assert 0 <= s["coverage_pct"] <= 100,   f"{code}: coverage out of range, got {s}"

        print(f"      {code}: total={s['total']} automated={s['automated']} "
              f"coverage={s['coverage_pct']}%")


# ---------- runner ----------

TESTS = [
    test_combined_stats_sums_across_projects,
    test_combined_stats_empty_returns_zeroes,
    test_pie_panel_carries_inline_snapshot_data,
    test_comparison_table_panel_has_one_row_per_project,
    test_build_dashboard_has_banner_pies_and_table_only,
    test_fetch_project_stats_from_qase_api,
]


def main() -> int:
    failed = skipped = 0
    for t in TESTS:
        try:
            t()
        except _Skip as e:
            skipped += 1
            print(f"SKIP  {t.__name__}: {e}")
        except Exception:
            failed += 1
            print(f"FAIL  {t.__name__}")
            traceback.print_exc()
        else:
            print(f"ok    {t.__name__}")
    total = len(TESTS)
    print(f"\n{total - failed - skipped}/{total} passed, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
