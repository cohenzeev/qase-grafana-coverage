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

import html
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
    return {
        "total": total,
        "automated": automated,
        "to_be_automated": to_be_automated,
        "manual": manual,
        "coverage_pct": coverage,
    }


# ---------- HTML rendering helpers ----------

CSS = """
<style>
  .qase-card { font-family: -apple-system, system-ui, sans-serif; padding: 16px; }
  .qase-card h2 { margin: 0 0 4px 0; font-size: 22px; }
  .qase-card .sub { color: #8a929d; font-size: 13px; margin-bottom: 16px; }
  .qase-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
  .qase-tile { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 12px; text-align: center; }
  .qase-tile .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #8a929d; }
  .qase-tile .value { font-size: 28px; font-weight: 600; margin-top: 4px; }
  .qase-tile.automated .value { color: #56a64b; }
  .qase-tile.to-be-automated .value { color: #f2cc0c; }
  .qase-tile.manual .value { color: #e02f44; }
  .qase-tile.total .value { color: #5794f2; }
  .qase-bar-wrap { background: rgba(255,255,255,0.08); border-radius: 4px; height: 24px; overflow: hidden; position: relative; }
  .qase-bar { height: 100%; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px; color: #fff; font-weight: 600; font-size: 13px; }
  .qase-bar.green  { background: linear-gradient(90deg, #56a64b, #37872d); }
  .qase-bar.yellow { background: linear-gradient(90deg, #f2cc0c, #e0b400); color: #222; }
  .qase-bar.red    { background: linear-gradient(90deg, #e02f44, #c4162a); }
  .qase-coverage-label { font-size: 12px; color: #8a929d; margin-bottom: 4px; }
  .qase-coverage-wrap { display: flex; align-items: center; gap: 14px; margin-top: 8px; }
  .qase-pie {
    width: 84px;
    height: 84px;
    border-radius: 50%;
    position: relative;
    flex: 0 0 auto;
  }
  .qase-pie::after {
    content: "";
    position: absolute;
    inset: 16px;
    border-radius: 50%;
    background: #0b0f14;
  }
  .qase-pie-label {
    font-size: 24px;
    font-weight: 700;
    line-height: 1;
    min-width: 76px;
  }
  .qase-banner { font-family: -apple-system, system-ui, sans-serif; padding: 20px 24px; }
  .qase-banner h1 { margin: 0; font-size: 26px; }
  .qase-banner .meta { color: #8a929d; font-size: 13px; margin-top: 6px; }
  .qase-link { color: #6e9fff; text-decoration: none; }
  .qase-link:hover { text-decoration: underline; }
</style>
"""


def bar_class(pct: float) -> str:
    if pct >= 75:
        return "green"
    if pct >= 50:
        return "yellow"
    return "red"


def banner_html(generated_at: str) -> str:
    return f"""
{CSS}
<div class="qase-banner">
  <h1>Qase Automation Coverage — IAO, AL &amp; IAI</h1>
  <div class="meta">
    Snapshot generated <b>{html.escape(generated_at)}</b> ·
    Re-run <code>generate_dashboard.py</code> and re-import this dashboard to refresh.
  </div>
</div>
""".strip()


def project_card_html(code: str, title: str, stats: dict) -> str:
    pct = stats["coverage_pct"]
    cls = bar_class(pct)
    color = {"red": "#e02f44", "yellow": "#f2cc0c", "green": "#56a64b"}[cls]
    return f"""
{CSS}
<div class="qase-card">
  <h2>{html.escape(title)} <span style="color:#8a929d;font-weight:400;font-size:14px;">(<a class="qase-link" href="https://app.qase.io/project/{html.escape(code)}" target="_blank">{html.escape(code)}</a>)</span></h2>
  <div class="sub">Automation status across all test cases</div>
  <div class="qase-grid">
    <div class="qase-tile total"><div class="label">Total</div><div class="value">{stats['total']:,}</div></div>
    <div class="qase-tile automated"><div class="label">Automated</div><div class="value">{stats['automated']:,}</div></div>
    <div class="qase-tile to-be-automated"><div class="label">To be automated</div><div class="value">{stats['to_be_automated']:,}</div></div>
    <div class="qase-tile manual"><div class="label">Manual</div><div class="value">{stats['manual']:,}</div></div>
  </div>
  <div class="qase-coverage-label">Automation coverage ({stats['automated']:,} / {stats['total']:,})</div>
  <div class="qase-coverage-wrap">
    <div class="qase-pie" style="background: conic-gradient({color} 0% {pct}%, rgba(255,255,255,0.09) {pct}% 100%);"></div>
    <div class="qase-pie-label" style="color:{color};">{pct}%</div>
  </div>
</div>
""".strip()


def combined_card_html(stats_by_project: dict) -> str:
    total = sum(s["total"] for s in stats_by_project.values())
    automated = sum(s["automated"] for s in stats_by_project.values())
    to_be = sum(s["to_be_automated"] for s in stats_by_project.values())
    manual = sum(s["manual"] for s in stats_by_project.values())
    pct = round(automated * 100 / total, 2) if total else 0.0
    cls = bar_class(pct)
    color = {"red": "#e02f44", "yellow": "#f2cc0c", "green": "#56a64b"}[cls]
    rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 12px;'>{html.escape(code)}</td>"
        f"<td style='padding:6px 12px;text-align:right;'>{s['total']:,}</td>"
        f"<td style='padding:6px 12px;text-align:right;color:#56a64b;'>{s['automated']:,}</td>"
        f"<td style='padding:6px 12px;text-align:right;color:#f2cc0c;'>{s['to_be_automated']:,}</td>"
        f"<td style='padding:6px 12px;text-align:right;color:#e02f44;'>{s['manual']:,}</td>"
        f"<td style='padding:6px 12px;text-align:right;font-weight:600;'>{s['coverage_pct']}%</td>"
        f"</tr>"
        for code, s in stats_by_project.items()
    )
    return f"""
{CSS}
<div class="qase-card">
  <h2>Combined</h2>
  <div class="sub">All selected projects together</div>
  <div class="qase-grid">
    <div class="qase-tile total"><div class="label">Total</div><div class="value">{total:,}</div></div>
    <div class="qase-tile automated"><div class="label">Automated</div><div class="value">{automated:,}</div></div>
    <div class="qase-tile to-be-automated"><div class="label">To be automated</div><div class="value">{to_be:,}</div></div>
    <div class="qase-tile manual"><div class="label">Manual</div><div class="value">{manual:,}</div></div>
  </div>
  <div class="qase-coverage-label">Combined coverage ({automated:,} / {total:,})</div>
  <div class="qase-coverage-wrap">
    <div class="qase-pie" style="background: conic-gradient({color} 0% {pct}%, rgba(255,255,255,0.09) {pct}% 100%);"></div>
    <div class="qase-pie-label" style="color:{color};">{pct}%</div>
  </div>
  <div style="margin-top:18px;">
    <table style="width:100%;border-collapse:collapse;font-family:-apple-system,system-ui,sans-serif;font-size:13px;">
      <thead><tr style="border-bottom:1px solid rgba(255,255,255,0.15);color:#8a929d;text-transform:uppercase;font-size:11px;letter-spacing:0.5px;">
        <th style="padding:6px 12px;text-align:left;">Project</th>
        <th style="padding:6px 12px;text-align:right;">Total</th>
        <th style="padding:6px 12px;text-align:right;">Automated</th>
        <th style="padding:6px 12px;text-align:right;">To be automated</th>
        <th style="padding:6px 12px;text-align:right;">Manual</th>
        <th style="padding:6px 12px;text-align:right;">Coverage</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>
""".strip()


# ---------- Dashboard assembly ----------

def text_panel(panel_id: int, title: str, content: str, gridPos: dict) -> dict:
    return {
        "id": panel_id,
        "type": "text",
        "title": title,
        "transparent": True,
        "gridPos": gridPos,
        "options": {"mode": "html", "content": content},
    }


def build_dashboard(stats_by_project: dict, generated_at: str) -> dict:
    panels = [
        text_panel(1, "", banner_html(generated_at),
                   {"h": 4, "w": 24, "x": 0, "y": 0}),
        text_panel(2, "", project_card_html("IAO", "[iS] Aura - oobe", stats_by_project["IAO"]),
                   {"h": 11, "w": 8, "x": 0, "y": 4}),
        text_panel(3, "", project_card_html("AL", "Aura - Laika", stats_by_project["AL"]),
                   {"h": 11, "w": 8, "x": 8, "y": 4}),
        text_panel(4, "", project_card_html("IAI", "IAI", stats_by_project["IAI"]),
                   {"h": 11, "w": 8, "x": 16, "y": 4}),
        text_panel(5, "", combined_card_html(stats_by_project),
                   {"h": 14, "w": 24, "x": 0, "y": 15}),
    ]
    return {
        "title": "Qase Automation Coverage — IAO, AL & IAI",
        "uid": "qase-automation-coverage",
        "tags": ["qase", "automation", "coverage", "iao", "al", "iai"],
        "timezone": "browser",
        "schemaVersion": 39,
        "refresh": "",
        "time": {"from": "now-24h", "to": "now"},
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
              f"coverage={s['coverage_pct']}%")
        stats_by_project[p["code"]] = s

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    dashboard = build_dashboard(stats_by_project, generated_at)
    with open(out_path, "w") as f:
        json.dump(dashboard, f, indent=2)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
