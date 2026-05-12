#!/usr/bin/env python3
"""
Emit OTLP JSON metrics for ironsource-aura/aura-shared-gha collect_metrics.

Writes files under METRICS_DIR (default: metrics-data/) for the action's
otlpjsonfile receiver (/data/*). See:
https://github.com/ironsource-aura/aura-shared-gha/blob/main/actions/collect_metrics/action.yml
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generate_dashboard import PROJECTS, fetch_project_stats  # noqa: E402


def _ns_timestamp() -> str:
    return str(int(time.time() * 1_000_000_000))


def _kv(key: str, string_value: str) -> dict:
    return {"key": key, "value": {"stringValue": string_value}}


def _dp_int(ts: str, value: int, labels: dict[str, str]) -> dict:
    dp: dict = {"timeUnixNano": ts, "asInt": str(value)}
    if labels:
        dp["attributes"] = [_kv(k, v) for k, v in sorted(labels.items())]
    return dp


def _dp_double(ts: str, value: float, labels: dict[str, str]) -> dict:
    dp: dict = {"timeUnixNano": ts, "asDouble": float(value)}
    if labels:
        dp["attributes"] = [_kv(k, v) for k, v in sorted(labels.items())]
    return dp


def _gauge(name: str, description: str, unit: str, data_points: list[dict]) -> dict:
    return {
        "name": name,
        "description": description,
        "unit": unit,
        "gauge": {"dataPoints": data_points},
    }


def main() -> None:
    token = os.environ.get("QASE_API_TOKEN")
    if not token:
        print("missing env var: QASE_API_TOKEN", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(os.environ.get("METRICS_DIR", "metrics-data"))
    out_dir.mkdir(parents=True, exist_ok=True)

    stats_by_project: dict[str, dict] = {}
    for p in PROJECTS:
        code = p["code"]
        print(f"fetching {code} ({p['title']})...")
        stats_by_project[code] = fetch_project_stats(token, code)

    ts = _ns_timestamp()
    workflow = os.environ.get("GITHUB_WORKFLOW", "local")
    repo = os.environ.get("GITHUB_REPOSITORY", "local")
    run_id = os.environ.get("GITHUB_RUN_ID", "0")
    org = os.environ.get("METRIC_ORG_NAME", "ironsource-aura")

    resource_attrs = [
        _kv("service.name", "qase-coverage-gha"),
        _kv("org.name", org),
        _kv("github.workflow", workflow),
        _kv("github.repository", repo),
        _kv("github.run_id", run_id),
    ]

    d_total: list[dict] = []
    d_auto: list[dict] = []
    d_tba: list[dict] = []
    d_manual: list[dict] = []
    d_cov: list[dict] = []

    for code, s in stats_by_project.items():
        labels = {"project_code": code}
        d_total.append(_dp_int(ts, s["total"], labels))
        d_auto.append(_dp_int(ts, s["automated"], labels))
        d_tba.append(_dp_int(ts, s["to_be_automated"], labels))
        d_manual.append(_dp_int(ts, s["manual"], labels))
        d_cov.append(_dp_double(ts, s["coverage_pct"], labels))

    total = sum(s["total"] for s in stats_by_project.values())
    automated = sum(s["automated"] for s in stats_by_project.values())
    to_be = sum(s["to_be_automated"] for s in stats_by_project.values())
    manual = sum(s["manual"] for s in stats_by_project.values())
    cov_all = round(automated * 100 / total, 4) if total else 0.0
    all_labels = {"project_code": "all"}
    d_total.append(_dp_int(ts, total, all_labels))
    d_auto.append(_dp_int(ts, automated, all_labels))
    d_tba.append(_dp_int(ts, to_be, all_labels))
    d_manual.append(_dp_int(ts, manual, all_labels))
    d_cov.append(_dp_double(ts, cov_all, all_labels))

    metrics = [
        _gauge("qase_test_cases_total", "Qase test cases (total)", "1", d_total),
        _gauge("qase_test_cases_automated", "Qase cases with automation=automated", "1", d_auto),
        _gauge(
            "qase_test_cases_to_be_automated",
            "Qase cases with automation=to-be-automated",
            "1",
            d_tba,
        ),
        _gauge("qase_test_cases_manual", "Qase cases counted as manual remainder", "1", d_manual),
        _gauge(
            "qase_automation_coverage_percent",
            "Automated / total * 100",
            "%",
            d_cov,
        ),
    ]

    payload = {
        "resourceMetrics": [
            {
                "resource": {"attributes": resource_attrs},
                "scopeMetrics": [
                    {
                        "scope": {"name": "qase_coverage", "version": "1.0.0"},
                        "metrics": metrics,
                    }
                ],
            }
        ]
    }

    out_file = out_dir / "qase-coverage.otlp.json"
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out_file}")


if __name__ == "__main__":
    main()
