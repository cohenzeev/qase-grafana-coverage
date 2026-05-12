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
    banner_html,
    combined_card_html,
    fetch_project_stats,
    project_card_html,
)


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
