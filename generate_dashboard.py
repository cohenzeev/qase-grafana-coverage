"""
Generate a self-contained Grafana dashboard JSON for Qase automation
coverage of projects IAO and AL.

The output dashboard uses only Grafana's built-in Text panel (HTML mode) —
no datasource, no plugins, no Postgres. Numbers are baked in at generation
time. Re-run this script and re-import dashboard.json whenever you want
fresh numbers.

Env:
  QASE_API_TOKEN  - Qase API token (https://app.qase.io/user/api/token)

Usage:
  set -a; source .env; set +a
  python generate_dashboard.py            # writes ./dashboard.json
  python generate_dashboard.py path.json  # writes to a custom path
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import requests

QASE_BASE = "https://api.qase.io/v1"
PROJECTS = [
    {"code": "IAO", "title": "[iS] Aura - oobe"},
    {"code": "AL",  "title": "Aura - Laika"},
    {"code": "IAI", "title": "IAI"},
]


def api_count(token: str, project: str, params: dict) -> int:
    """Return the `filtered` count for a /case query, regardless of how many
    entities we actually fetched."""
    resp = requests.get(
        f"{QASE_BASE}/case/{project}",
        headers={"Token": token, "accept": "application/json"},
        params={"limit": 1, **params},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["result"]["filtered"]


def fetch_project_stats(token: str, code: str) -> dict:
    total           = api_count(token, code, {})
    automated       = api_count(token, code, {"automation": "automated"})
    to_be_automated = api_count(token, code, {"automation": "to-be-automated"})
    manual          = max(total - automated - to_be_automated, 0)
    coverage        = round(automated * 100 / total, 2) if total else 0.0
    target_denom    = automated + to_be_automated
    target_coverage = round(automated * 100 / target_denom, 2) if target_denom else 0.0
    return {
        "total": total,
        "automated": automated,
        "to_be_automated": to_be_automated,
        "manual": manual,
        "coverage_pct": coverage,
        "target_coverage_pct": target_coverage,
    }


# ---------- Native Grafana panel builders ----------
#
# All panels are real Grafana panels (Stat, Pie chart, Table, Markdown text)
# fed by the built-in TestData datasource via inline CSV. No raw HTML, no
# `<div>`, no `<style>`, no `<svg>` — just JSON describing panels.

GREEN = "green"
YELL  = "yellow"
RED   = "red"
BLUE  = "blue"


def _frame(fields: list[dict]) -> dict:
    """Wrap a list of {name,type,values} field dicts as one Grafana DataFrame."""
    return {"fields": fields}


def _snapshot_target() -> dict:
    return {"refId": "A"}


def banner_panel(panel_id: int, generated_at: str, gridPos: dict) -> dict:
    md = (
        "# Qase Automation Coverage — IAO, AL & IAI\n\n"
        f"Snapshot generated **{generated_at}** · "
        "re-run `generate_dashboard.py` and re-import this dashboard to refresh."
    )
    return {
        "id": panel_id,
        "type": "text",
        "title": "",
        "transparent": True,
        "gridPos": gridPos,
        "options": {"mode": "markdown", "content": md},
    }


def stats_panel(panel_id: int, title: str, stats: dict, gridPos: dict) -> dict:
    frame = _frame([
        {"name": "Total",           "type": "number", "values": [stats["total"]]},
        {"name": "Automated",       "type": "number", "values": [stats["automated"]]},
        {"name": "To be automated", "type": "number", "values": [stats["to_be_automated"]]},
        {"name": "Manual",          "type": "number", "values": [stats["manual"]]},
        {"name": "Coverage %",      "type": "number", "values": [stats["coverage_pct"]]},
        {"name": "Target coverage %", "type": "number", "values": [stats["target_coverage_pct"]]},
    ])
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "gridPos": gridPos,
        "datasource": None,
        "targets": [_snapshot_target()],
        "snapshotData": [frame],
        "options": {
            "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
            "orientation": "horizontal",
            "textMode": "value_and_name",
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "auto",
        },
        "fieldConfig": {
            "defaults": {"color": {"mode": "fixed", "fixedColor": BLUE}, "unit": "short"},
            "overrides": [
                {"matcher": {"id": "byName", "options": "Automated"},
                 "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": GREEN}}]},
                {"matcher": {"id": "byName", "options": "To be automated"},
                 "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": YELL}}]},
                {"matcher": {"id": "byName", "options": "Manual"},
                 "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": RED}}]},
                {"matcher": {"id": "byName", "options": "Coverage %"},
                 "properties": [
                     {"id": "color", "value": {"mode": "fixed", "fixedColor": BLUE}},
                     {"id": "unit", "value": "percent"},
                 ]},
                {"matcher": {"id": "byName", "options": "Target coverage %"},
                 "properties": [
                     {"id": "color", "value": {"mode": "fixed", "fixedColor": BLUE}},
                     {"id": "unit", "value": "percent"},
                 ]},
            ],
        },
    }


def pie_panel(panel_id: int, title: str, stats: dict, gridPos: dict) -> dict:
    target_pct = stats.get("target_coverage_pct", 0.0)
    target_label = f"★ TARGET COVERAGE — {target_pct}% ★"
    frame = _frame([
        {"name": "status", "type": "string",
         "values": ["Automated", "To be automated", "Manual", target_label]},
        {"name": "count",  "type": "number",
         "values": [stats["automated"], stats["to_be_automated"], stats["manual"], 0]},
    ])
    return {
        "id": panel_id,
        "type": "piechart",
        "title": title,
        "gridPos": gridPos,
        "datasource": None,
        "targets": [_snapshot_target()],
        "snapshotData": [frame],
        "options": {
            "reduceOptions": {"values": True, "calcs": ["lastNotNull"], "fields": "/^count$/"},
            "pieType": "pie",
            "tooltip": {"mode": "single", "sort": "none"},
            "legend": {
                "displayMode": "table",
                "placement": "right",
                "showLegend": True,
                "values": ["value", "percent"],
            },
            "displayLabels": ["percent"],
        },
        "fieldConfig": {
            "defaults": {"unit": "short", "color": {"mode": "palette-classic"}},
            "overrides": [
                {"matcher": {"id": "byName", "options": "Automated"},
                 "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": GREEN}}]},
                {"matcher": {"id": "byName", "options": "To be automated"},
                 "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": YELL}}]},
                {"matcher": {"id": "byName", "options": "Manual"},
                 "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": RED}}]},
                {"matcher": {"id": "byName", "options": target_label},
                 "properties": [
                     {"id": "color", "value": {"mode": "fixed", "fixedColor": "orange"}},
                     {"id": "displayName", "value": target_label},
                 ]},
            ],
        },
    }


def comparison_table_panel(panel_id: int, title: str, stats_by_project: dict, gridPos: dict) -> dict:
    codes = list(stats_by_project.keys())
    frame = _frame([
        {"name": "Project",          "type": "string", "values": codes},
        {"name": "Total",            "type": "number", "values": [stats_by_project[c]["total"]           for c in codes]},
        {"name": "Automated",        "type": "number", "values": [stats_by_project[c]["automated"]       for c in codes]},
        {"name": "To be automated",  "type": "number", "values": [stats_by_project[c]["to_be_automated"] for c in codes]},
        {"name": "Manual",           "type": "number", "values": [stats_by_project[c]["manual"]              for c in codes]},
        {"name": "Coverage %",       "type": "number", "values": [stats_by_project[c]["coverage_pct"]        for c in codes]},
        {"name": "Target coverage %", "type": "number", "values": [stats_by_project[c]["target_coverage_pct"] for c in codes]},
    ])
    return {
        "id": panel_id,
        "type": "table",
        "title": title,
        "gridPos": gridPos,
        "datasource": None,
        "targets": [_snapshot_target()],
        "snapshotData": [frame],
        "options": {"showHeader": True, "cellHeight": "sm"},
        "fieldConfig": {
            "defaults": {"custom": {"align": "right", "displayMode": "auto"}},
            "overrides": [
                {"matcher": {"id": "byName", "options": "Project"},
                 "properties": [{"id": "custom.align", "value": "left"}]},
                {"matcher": {"id": "byName", "options": "Coverage %"},
                 "properties": [{"id": "unit", "value": "percent"}]},
                {"matcher": {"id": "byName", "options": "Target coverage %"},
                 "properties": [{"id": "unit", "value": "percent"}]},
            ],
        },
    }


def combined_stats(stats_by_project: dict) -> dict:
    total = sum(s["total"] for s in stats_by_project.values())
    automated = sum(s["automated"] for s in stats_by_project.values())
    to_be = sum(s["to_be_automated"] for s in stats_by_project.values())
    manual = sum(s["manual"] for s in stats_by_project.values())
    pct = round(automated * 100 / total, 2) if total else 0.0
    target_denom = automated + to_be
    target_pct = round(automated * 100 / target_denom, 2) if target_denom else 0.0
    return {
        "total": total,
        "automated": automated,
        "to_be_automated": to_be,
        "manual": manual,
        "coverage_pct": pct,
        "target_coverage_pct": target_pct,
    }


PROJECT_ROWS = [
    ("IAO", "[iS] Aura - oobe"),
    ("AL",  "Aura - Laika"),
    ("IAI", "IAI"),
]


def build_dashboard(stats_by_project: dict, generated_at: str) -> dict:
    combined = combined_stats(stats_by_project)

    panels = [banner_panel(1, generated_at, {"h": 3, "w": 24, "x": 0, "y": 0})]

    pid = 11
    x = 0
    for code, title in PROJECT_ROWS:
        s = stats_by_project[code]
        panels.append(pie_panel(pid, f"{title} ({code}) — Automation breakdown", s,
                                {"h": 10, "w": 8, "x": x, "y": 3}))
        pid += 10
        x += 8

    panels.append(pie_panel(40, "Combined — Automation breakdown", combined,
                            {"h": 10, "w": 10, "x": 0, "y": 13}))
    panels.append(comparison_table_panel(41, "Per-project comparison", stats_by_project,
                                         {"h": 10, "w": 14, "x": 10, "y": 13}))

    return {
        "title": "Qase Automation Coverage — IAO, AL & IAI",
        "uid": "qase-automation-coverage",
        "tags": ["qase", "automation", "coverage", "iao", "al", "iai"],
        "timezone": "browser",
        "schemaVersion": 39,
        "refresh": "",
        "time": {"from": "now-24h", "to": "now"},
        "snapshot": {
            "name": "Qase Automation Coverage Snapshot",
            "timestamp": generated_at,
            "originalUrl": "",
            "expires": "0001-01-01T00:00:00Z",
            "external": False,
            "externalUrl": "",
        },
        "panels": panels,
    }


def main():
    token = os.environ.get("QASE_API_TOKEN")
    if not token:
        sys.exit("missing env var: QASE_API_TOKEN")
    out_path = sys.argv[1] if len(sys.argv) > 1 else "dashboard.json"

    stats_by_project: dict[str, dict] = {}
    for p in PROJECTS:
        print(f"fetching {p['code']} ({p['title']})...")
        s = fetch_project_stats(token, p["code"])
        print(f"  total={s['total']} automated={s['automated']} "
              f"to_be={s['to_be_automated']} manual={s['manual']} "
              f"coverage={s['coverage_pct']}% "
              f"target_coverage={s['target_coverage_pct']}%")
        stats_by_project[p["code"]] = s

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    dashboard = build_dashboard(stats_by_project, generated_at)
    with open(out_path, "w") as f:
        json.dump(dashboard, f, indent=2)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
