from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from .compare import compare_batch
from .utils import (
    PROJECT_ROOT,
    aggregate_metric_rows,
    compute_score,
    detect_routing_error,
    discover_suite,
    load_batch_payload,
    load_json,
    run_batch_through_runner,
    timestamp_tag,
    write_json,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fixed HuntMind evaluation judge.")
    parser.add_argument("--config", required=True, help="Path to judge config JSON")
    parser.add_argument("--tag", default="", help="Optional results tag")
    return parser.parse_args()


def _build_summary_record(
    batch_id: str,
    suite_name: str,
    comparison: Dict[str, Any],
    weights: Dict[str, float],
    source_paths: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    metrics = dict(comparison["metrics"])
    metrics["score"] = compute_score(metrics, weights)
    return {
        "suite_name": suite_name,
        "batch_id": batch_id,
        "metrics": metrics,
        "hard_errors": comparison["hard_errors"],
        "top3": comparison["top3"],
        "source_paths": source_paths or {},
    }


def main() -> None:
    args = _parse_args()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    config = load_json(config_path)

    results_root = PROJECT_ROOT / config["results_root"]
    tag = args.tag or timestamp_tag()
    results_dir = results_root / tag
    results_dir.mkdir(parents=True, exist_ok=True)

    batch_reports: List[Dict[str, Any]] = []

    for suite_name in config["suite_names"]:
        suite = discover_suite(suite_name)
        batch_input, model_output_text, human_labels, expected_summary = load_batch_payload(suite)
        final_output = run_batch_through_runner(batch_input, model_output_text)
        routing_error_count = detect_routing_error(batch_input, suite["expected_template"])
        comparison = compare_batch(human_labels, final_output, expected_summary, routing_error_count)
        summary = _build_summary_record(
            suite["batch_id"],
            suite_name,
            comparison,
            config["score_weights"],
            suite.get("source_paths"),
        )

        batch_dir = results_dir / suite["batch_id"]
        batch_dir.mkdir(parents=True, exist_ok=True)
        write_json(batch_dir / "final_output.json", final_output)
        write_json(batch_dir / "compare.json", {
            "batch_id": suite["batch_id"],
            "suite_name": suite_name,
            **comparison,
        })
        write_json(batch_dir / "summary.json", summary)
        batch_reports.append(summary)

    aggregated = aggregate_metric_rows(batch_reports, config["score_weights"])
    report = {
        "tag": tag,
        "config": config,
        "batches": batch_reports,
        "global_metrics": {
            key: value for key, value in aggregated.items() if key != "hard_errors"
        },
        "hard_errors": aggregated["hard_errors"],
    }
    write_json(results_dir / "report.json", report)

    print(f"Ran {len(batch_reports)} batches")
    print(f"score={aggregated['score']:.4f}")
    print(f"contact_accuracy={aggregated['contact_accuracy']:.4f}")
    print(f"top3_hit_rate={aggregated['top3_hit_rate']:.4f}")
    print(f"priority_accuracy={aggregated['priority_accuracy']:.4f}")
    print(f"false_positive_rate={aggregated['false_positive_rate']:.4f}")
    print(f"hard_mismatch_false_positive={aggregated['hard_errors']['hard_mismatch_false_positive']}")
    print(f"low_fit_high_willingness_promoted={aggregated['hard_errors']['low_fit_high_willingness_promoted']}")
    print(f"routing_error_count={aggregated['hard_errors']['routing_error_count']}")
    print(f"new_high_priority_false_positive={aggregated['hard_errors']['new_high_priority_false_positive']}")
    print(f"results_dir={results_dir}")


if __name__ == "__main__":
    main()
