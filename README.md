# Qase Automation Coverage — Grafana dashboard for IAO & AL

A self-contained Grafana dashboard that shows automation coverage for the
Qase projects [`IAO`](https://app.qase.io/project/IAO) (`[iS] Aura - oobe`)
and [`AL`](https://app.qase.io/project/AL) (`Aura - Laika`):

- Per-project: total cases, automated, to-be-automated, manual, coverage %
- A combined summary across both projects with a comparison table

The dashboard is **fully static** — counts are baked into the JSON at
generation time. No Postgres, no datasource, no plugins. To refresh the
numbers you re-run the generator and re-import the dashboard.

## Files

| File | Purpose |
| --- | --- |
| `generate_dashboard.py` | Fetches current counts from Qase, writes `dashboard.json` |
| `dashboard.json`        | The Grafana dashboard, ready to import |
| `requirements.txt`      | Python deps (`requests`) |
| `.env.example`          | Env vars the generator needs |

## How it works

```
+-----------+    HTTPS     +------------------------+   import
| Qase API  | <----------- | generate_dashboard.py  | --------> dashboard.json --> Grafana
+-----------+              +------------------------+
```

Every panel is a Grafana **Text panel in HTML mode**, so the dashboard works
in any Grafana install with no datasource configuration. The numbers are
literally written into the HTML at generation time. That means:

- Importing is a one-step manual upload — no datasources to wire up.
- "Refresh" = re-run the script, then re-import (or use *Dashboard
  settings → JSON Model → paste*) to update an existing dashboard.

## Setup (one-time)

```bash
cd qase-grafana-coverage
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: set QASE_API_TOKEN
```

Get a Qase API token at https://app.qase.io/user/api/token.

## Generate the dashboard

```bash
set -a; source .env; set +a
python generate_dashboard.py            # writes ./dashboard.json
# python generate_dashboard.py out.json  # custom path
```

You should see:

```
fetching IAO ([iS] Aura - oobe)...
  total=9178 automated=699 to_be=398 manual=8081 coverage=7.62%
fetching AL (Aura - Laika)...
  total=360 automated=16 to_be=124 manual=220 coverage=4.44%
wrote dashboard.json
```

## Import into Grafana

**First time:**

1. Grafana → **Dashboards → New → Import**
2. Click **Upload JSON file** and pick `dashboard.json`
3. Click **Import**. Done — no datasource selection needed.

After import the URL will be:

```
https://<your-grafana-host>/d/qase-automation-coverage
```

The UID `qase-automation-coverage` is hard-coded so the link is stable.

**Subsequent refreshes** (two options):

- *Quickest:* open the dashboard → **Settings (gear) → JSON Model** → paste
  the new contents of `dashboard.json` → **Save changes**.
- *Or:* delete the existing dashboard and re-import. The UID stays the
  same so any links/embeds keep working.

## What the dashboard shows

```
┌────────────────────────────────────────────────────────────┐
│ Qase Automation Coverage — IAO & AL                        │  banner
│ Snapshot generated 2026-05-12 ...                          │
├──────────────────────────┬─────────────────────────────────┤
│ [iS] Aura - oobe (IAO)   │ Aura - Laika (AL)               │
│  Total / Auto / ToBe /   │  Total / Auto / ToBe /          │  per-project cards
│  Manual + coverage bar   │  Manual + coverage bar          │
├──────────────────────────┴─────────────────────────────────┤
│ Combined                                                   │
│  Total + Auto + ToBe + Manual + combined coverage bar      │  summary
│  Per-project comparison table                              │
└────────────────────────────────────────────────────────────┘
```

## Notes

- The script makes 3 lightweight Qase API calls per project (total +
  automated + to-be-automated counts). Manual count is derived. ~6 calls
  total, runs in well under a second.
- To add another project, edit the `PROJECTS` list at the top of
  `generate_dashboard.py` and re-run.
- If you want the dashboard to truly auto-refresh in Grafana (without you
  re-running the script), you'd need to push counts to a datasource
  Grafana can query — see earlier Postgres-based version of this project
  in git history if you change your mind.
