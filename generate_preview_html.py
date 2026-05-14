"""
Generate a standalone HTML preview page for Qase coverage data.

Usage:
  set -a; source .env; set +a
  python generate_preview_html.py            # writes ./preview.html
  python generate_preview_html.py page.html  # writes custom path
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from generate_dashboard import (
    PROJECTS,
    combined_stats,
    fetch_project_stats,
)


# ---------- shared CSS ----------

CARD_CSS = """<style>
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
  .qase-coverage-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 12px; }
  .qase-coverage-block { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 12px; }
  .qase-coverage-label { font-size: 12px; color: #8a929d; margin-bottom: 4px; }
  .qase-coverage-formula { font-size: 11px; color: #6e7682; margin-top: 2px; }
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
</style>"""


# ---------- helpers ----------

def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _coverage_color(pct: float) -> str:
    if pct >= 70:
        return "#56a64b"
    if pct >= 40:
        return "#f2cc0c"
    return "#e02f44"


def _pie_block(label: str, formula: str, numerator: int, denominator: int, pct: float) -> str:
    color = _coverage_color(pct)
    return f"""<div class="qase-coverage-block">
      <div class="qase-coverage-label">{label} ({_fmt_int(numerator)} / {_fmt_int(denominator)})</div>
      <div class="qase-coverage-formula">{formula}</div>
      <div class="qase-coverage-wrap">
        <div class="qase-pie" style="background: conic-gradient({color} 0% {pct}%, rgba(255,255,255,0.09) {pct}% 100%);"></div>
        <div class="qase-pie-label" style="color:{color};">{pct}%</div>
      </div>
    </div>"""


def banner_html(generated_at: str) -> str:
    return f"""{CARD_CSS}

<div class="qase-banner">
  <h1>Qase Automation Coverage — IAO, AL &amp; IAI</h1>
  <div class="meta">
    Snapshot generated <b>{generated_at}</b> ·
    Re-run <code>generate_preview_html.py</code> to refresh.
  </div>
</div>"""


def project_card_html(code: str, title: str, stats: dict) -> str:
    target_denom = stats["automated"] + stats["to_be_automated"]
    coverage_block = _pie_block(
        "Coverage", "automated / total",
        stats["automated"], stats["total"], stats["coverage_pct"],
    )
    target_block = _pie_block(
        "Target coverage", "automated / (automated + to-be-automated)",
        stats["automated"], target_denom, stats["target_coverage_pct"],
    )
    return f"""{CARD_CSS}

<div class="qase-card">
  <h2>{title} <span style="color:#8a929d;font-weight:400;font-size:14px;">(<a class="qase-link" href="https://app.qase.io/project/{code}" target="_blank">{code}</a>)</span></h2>
  <div class="sub">Automation status across all test cases</div>
  <div class="qase-grid">
    <div class="qase-tile total"><div class="label">Total</div><div class="value">{_fmt_int(stats["total"])}</div></div>
    <div class="qase-tile automated"><div class="label">Automated</div><div class="value">{_fmt_int(stats["automated"])}</div></div>
    <div class="qase-tile to-be-automated"><div class="label">To be automated</div><div class="value">{_fmt_int(stats["to_be_automated"])}</div></div>
    <div class="qase-tile manual"><div class="label">Manual</div><div class="value">{_fmt_int(stats["manual"])}</div></div>
  </div>
  <div class="qase-coverage-row">
    {coverage_block}
    {target_block}
  </div>
</div>"""


def _row_html(code: str, s: dict) -> str:
    return (
        "<tr>"
        f"<td style='padding:6px 12px;'>{code}</td>"
        f"<td style='padding:6px 12px;text-align:right;'>{_fmt_int(s['total'])}</td>"
        f"<td style='padding:6px 12px;text-align:right;color:#56a64b;'>{_fmt_int(s['automated'])}</td>"
        f"<td style='padding:6px 12px;text-align:right;color:#f2cc0c;'>{_fmt_int(s['to_be_automated'])}</td>"
        f"<td style='padding:6px 12px;text-align:right;color:#e02f44;'>{_fmt_int(s['manual'])}</td>"
        f"<td style='padding:6px 12px;text-align:right;font-weight:600;'>{s['coverage_pct']}%</td>"
        f"<td style='padding:6px 12px;text-align:right;font-weight:600;'>{s['target_coverage_pct']}%</td>"
        "</tr>"
    )


def combined_card_html(stats_by_project: dict) -> str:
    combined = combined_stats(stats_by_project)
    target_denom = combined["automated"] + combined["to_be_automated"]
    coverage_block = _pie_block(
        "Combined coverage", "automated / total",
        combined["automated"], combined["total"], combined["coverage_pct"],
    )
    target_block = _pie_block(
        "Combined target coverage", "automated / (automated + to-be-automated)",
        combined["automated"], target_denom, combined["target_coverage_pct"],
    )
    rows = "".join(_row_html(c, stats_by_project[c]) for c in stats_by_project)
    return f"""{CARD_CSS}

<div class="qase-card">
  <h2>Combined</h2>
  <div class="sub">All selected projects together</div>
  <div class="qase-grid">
    <div class="qase-tile total"><div class="label">Total</div><div class="value">{_fmt_int(combined["total"])}</div></div>
    <div class="qase-tile automated"><div class="label">Automated</div><div class="value">{_fmt_int(combined["automated"])}</div></div>
    <div class="qase-tile to-be-automated"><div class="label">To be automated</div><div class="value">{_fmt_int(combined["to_be_automated"])}</div></div>
    <div class="qase-tile manual"><div class="label">Manual</div><div class="value">{_fmt_int(combined["manual"])}</div></div>
  </div>
  <div class="qase-coverage-row">
    {coverage_block}
    {target_block}
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
        <th style="padding:6px 12px;text-align:right;">Target coverage</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""


def build_preview_html(stats_by_project: dict[str, dict], generated_at: str) -> str:
    cards = []
    for p in PROJECTS:
        cards.append(project_card_html(p["code"], p["title"], stats_by_project[p["code"]]))
    cards_html = "".join(f"    <div>{card}</div>\n" for card in cards)

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Qase Coverage Preview</title>
  <style>
    body {{
      margin: 0;
      background: #0b0f14;
      color: #e8edf2;
      font-family: -apple-system, system-ui, sans-serif;
    }}
    .container {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 16px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }}
    .full {{
      grid-column: 1 / -1;
    }}
    code {{
      background: rgba(255, 255, 255, 0.06);
      padding: 1px 5px;
      border-radius: 4px;
    }}
    @media (max-width: 980px) {{
      .container {{
        grid-template-columns: 1fr;
      }}
      .full {{
        grid-column: auto;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="full">{banner_html(generated_at)}</div>
{cards_html.rstrip()}
    <div class="full">{combined_card_html(stats_by_project)}</div>
  </div>
</body>
</html>
"""
    return page


def main() -> None:
    token = os.environ.get("QASE_API_TOKEN")
    if not token:
        sys.exit("missing env var: QASE_API_TOKEN")

    out_path = sys.argv[1] if len(sys.argv) > 1 else "preview.html"

    stats_by_project: dict[str, dict] = {}
    for p in PROJECTS:
        print(f"fetching {p['code']} ({p['title']})...")
        stats_by_project[p["code"]] = fetch_project_stats(token, p["code"])

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html_page = build_preview_html(stats_by_project, generated_at)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_page)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
