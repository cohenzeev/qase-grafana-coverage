# Qase coverage metrics → Grafana (Aura `collect_metrics`)

This repo can push Qase automation coverage numbers into **VictoriaMetrics** using the shared GitHub Action [`collect_metrics`](https://github.com/ironsource-aura/aura-shared-gha/blob/main/actions/collect_metrics/action.yml). Grafana reads the same metrics through your org’s **Prometheus-compatible** datasource (often labeled VictoriaMetrics or Mimir).

**Grafana folder (your target):**  
[https://grafana.infra.us-west-2.int.isappcloud.com/dashboards/f/bfam7dqlep6o0c/](https://grafana.infra.us-west-2.int.isappcloud.com/dashboards/f/bfam7dqlep6o0c/)

**Data path:**

`GitHub Actions` → `OpenTelemetry Collector` (from the action) → `VictoriaMetrics remote_write` → `Grafana` (PromQL / Metrics drilldown)

For `us-west-2` + `prod`, the action resolves the write endpoint to:

`https://vm-prod.infra.us-west-2.int.isappcloud.com/insert/0/prometheus/api/v1/write`

(documented in the action [README](https://github.com/ironsource-aura/aura-shared-gha/blob/main/actions/collect_metrics/README.md)).

---

## 1. Wire the workflow

1. Open `.github/workflows/qase-coverage-metrics.yml`.
2. Ensure the repository has a secret **`QASE_API_TOKEN`** (Qase API token with access to projects in `generate_dashboard.py` / `PROJECTS`).
3. Run **Actions → Qase coverage metrics → Run workflow**, or wait for the schedule.

The workflow:

1. Runs `ironsource-aura/aura-shared-gha/actions/collect_metrics@main` (starts the collector).
2. Checks out this repo, installs `requirements.txt`, runs `scripts/emit_qase_coverage_otlp_json.py`.
3. Drops OTLP JSON under `./metrics-data/`; the collector ships it to VictoriaMetrics before the job finishes.

---

## 2. Metric names and labels

Emitted gauges (all include **`project_code`** on each series):

| Metric | Meaning |
|--------|---------|
| `qase_test_cases_total` | Total cases |
| `qase_test_cases_automated` | `automation=automated` count |
| `qase_test_cases_to_be_automated` | `automation=to-be-automated` count |
| `qase_test_cases_manual` | Remainder treated as manual |
| `qase_automation_coverage_percent` | `automated / total * 100` |

**`project_code` values:** one per entry in `PROJECTS` in `generate_dashboard.py` (e.g. `IAO`, `AL`, `IAI`), plus aggregated series with **`project_code="all"`**.

Resource attributes on the batch include `service.name=qase-coverage-gha`, `github.workflow`, `github.repository`, `github.run_id` (for correlating a point with a run).

If names differ slightly in Grafana (OpenTelemetry → Prometheus conversion), use **Explore → Metrics** and search for `qase_`.

---

## 3. Present the data in Grafana

1. Sign in to [Grafana](https://grafana.infra.us-west-2.int.isappcloud.com/dashboards/f/bfam7dqlep6o0c/).
2. **Create → Dashboard** (save into folder **bfam7dqlep6o0c** via dashboard settings → folder).
3. Add a panel; choose the datasource your team uses for **VictoriaMetrics / Prometheus** in `us-west-2` prod (naming is org-specific).

### Example PromQL

**Coverage % for IAO (latest point):**

```promql
last_over_time(qase_automation_coverage_percent{project_code="IAO"}[24h])
```

**Time series of coverage for all projects:**

```promql
qase_automation_coverage_percent
```

**Stacked or separate stat — automated vs manual (IAO):**

```promql
qase_test_cases_automated{project_code="IAO"}
qase_test_cases_to_be_automated{project_code="IAO"}
qase_test_cases_manual{project_code="IAO"}
```

**Table of latest values per project** (pattern; adjust datasource if `label_values` differs):

Use a **Table** panel with multiple queries, or **Bar gauge** with `project_code` as a field from **Transform → Labels to fields** if your Grafana version supports it.

### Panel tips

- **Stat / Gauge:** use `qase_automation_coverage_percent` with unit **Percent (0–100)**.
- **Time series:** same metric; set legend to `{{project_code}}`.
- **Refresh:** metrics arrive on workflow schedule; dashboard refresh **5m–1h** is usually enough.

---

## 4. Troubleshooting

- **No metrics in Grafana:** confirm the workflow is green; in job logs, check the `collect_metrics` post step collector output. Verify you’re querying the **same** VictoriaMetrics / Prometheus datasource that receives `us-west-2` **prod** remote write.
- **401 from Qase:** rotate or fix **`QASE_API_TOKEN`**.
- **Wrong project list:** edit **`PROJECTS`** in `generate_dashboard.py` (used by the emitter).

---

## References

- Action definition: [collect_metrics/action.yml](https://github.com/ironsource-aura/aura-shared-gha/blob/main/actions/collect_metrics/action.yml)
- Action usage & architecture: [collect_metrics/README.md](https://github.com/ironsource-aura/aura-shared-gha/blob/main/actions/collect_metrics/README.md)
