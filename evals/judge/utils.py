from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.sequence_identifier import identify_sequence_with_meta


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUITE_BATCH_IDS = {
    "product": "product_manager_batch_001",
    "frontend_dev": "frontend_dev_batch_001",
    "blockchain_lead": "blockchain_lead_batch_001",
    "sales_director": "sales_director_batch_001",
}
SUITE_EXPECTED_TEMPLATES = {
    "product": "product_manager",
    "frontend_dev": "rd_engineer",
    "blockchain_lead": "sales_director",
    "sales_director": "sales_director",
}


def load_json(path: Path) -> Any:
    import json

    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def timestamp_tag() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def normalize_decision(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_priority(value: Any) -> str:
    value = str(value or "").strip().upper()
    return value if value in {"A", "B", "C", "N"} else "N"


def normalize_level(value: Any) -> str:
    value = str(value or "").strip().lower()
    return value if value in {"high", "medium", "low"} else "low"


def normalize_mismatch(value: Any) -> str:
    value = str(value or "").strip().lower()
    return value if value in {"none", "recoverable", "hard_mismatch"} else "none"


def normalize_should_contact(value: Any) -> bool:
    return bool(value)


def normalize_candidate_output(candidate: Dict[str, Any]) -> Dict[str, Any]:
    action = candidate.get("action", {}) if isinstance(candidate.get("action"), dict) else {}
    return {
        "candidate_id": str(candidate.get("candidate_id") or candidate.get("id") or "").strip(),
        "should_contact": normalize_should_contact(action.get("should_contact")),
        "priority": normalize_priority(candidate.get("priority")),
        "decision": normalize_decision(candidate.get("decision")),
        "match_fit": normalize_level(candidate.get("match_fit")),
        "recruitability": normalize_level(candidate.get("recruitability")),
        "mismatch_type": normalize_mismatch(candidate.get("mismatch_type")),
        "willingness": str(candidate.get("willingness") or "").strip().lower(),
        "decision_trace": candidate.get("decision_trace", {}),
    }


def normalize_human_label(label: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "candidate_id": str(label.get("candidate_id") or "").strip(),
        "should_contact": normalize_should_contact(label.get("should_contact")),
        "priority": normalize_priority(label.get("priority")),
        "decision": normalize_decision(label.get("decision")),
        "match_fit": normalize_level(label.get("match_fit")),
        "recruitability": normalize_level(label.get("recruitability")),
        "mismatch_type": normalize_mismatch(label.get("mismatch_type")),
        "primary_reason": str(label.get("primary_reason") or "other").strip(),
        "comment": str(label.get("comment") or "").strip(),
    }


def reason_bucket_from_output(candidate: Dict[str, Any]) -> str:
    mismatch = normalize_mismatch(candidate.get("mismatch_type"))
    match_fit = normalize_level(candidate.get("match_fit"))
    recruitability = normalize_level(candidate.get("recruitability"))
    decision = normalize_decision(candidate.get("decision"))
    trace = candidate.get("decision_trace", {}) if isinstance(candidate.get("decision_trace"), dict) else {}
    hard_constraints = trace.get("hard_constraints", {})
    issues = hard_constraints.get("hard_issues", []) if isinstance(hard_constraints, dict) else []

    if mismatch == "hard_mismatch" or issues:
        return "hard_mismatch"
    if match_fit == "low":
        return "low_match_fit"
    if recruitability == "low":
        return "low_recruitability"
    if mismatch == "recoverable":
        return "recoverable_but_uncertain"
    if decision == "maybe":
        return "insufficient_info"
    if match_fit in {"high", "medium"} and recruitability in {"high", "medium"}:
        return "fit_and_reachable"
    return "other"


def compute_score(metrics: Dict[str, float], weights: Dict[str, float]) -> float:
    score = (
        weights.get("contact_accuracy", 0) * metrics.get("contact_accuracy", 0)
        + weights.get("top3_hit_rate", 0) * metrics.get("top3_hit_rate", 0)
        + weights.get("priority_accuracy", 0) * metrics.get("priority_accuracy", 0)
        + weights.get("reason_accuracy", 0) * metrics.get("reason_accuracy", 0)
        - weights.get("false_positive_penalty", 0) * metrics.get("false_positive_rate", 0)
    )
    return round(score, 4)


def aggregate_metric_rows(batch_summaries: List[Dict[str, Any]], weights: Dict[str, float]) -> Dict[str, Any]:
    if not batch_summaries:
        return {
            "contact_accuracy": 0.0,
            "priority_accuracy": 0.0,
            "decision_accuracy": 0.0,
            "top3_hit_rate": 0.0,
            "false_positive_rate": 0.0,
            "false_negative_rate": 0.0,
            "reason_accuracy": 0.0,
            "routing_error_count": 0,
            "score": 0.0,
            "hard_errors": {
                "hard_mismatch_false_positive": 0,
                "low_fit_high_willingness_promoted": 0,
                "routing_error_count": 0,
                "new_high_priority_false_positive": 0,
            },
        }

    total_candidates = 0
    contact_matches = 0
    priority_matches = 0
    decision_matches = 0
    reason_matches = 0
    false_positive = 0
    false_negative = 0
    top3_hit_count = 0
    top3_base = 0
    routing_error_count = 0
    hard_errors = {
        "hard_mismatch_false_positive": 0,
        "low_fit_high_willingness_promoted": 0,
        "routing_error_count": 0,
        "new_high_priority_false_positive": 0,
    }

    for summary in batch_summaries:
        counts = summary.get("counts", {})
        total_candidates += int(counts.get("total_candidates", 0))
        contact_matches += int(counts.get("contact_matches", 0))
        priority_matches += int(counts.get("priority_matches", 0))
        decision_matches += int(counts.get("decision_matches", 0))
        reason_matches += int(counts.get("reason_matches", 0))
        false_positive += int(counts.get("false_positive", 0))
        false_negative += int(counts.get("false_negative", 0))
        top3_hit_count += int(counts.get("top3_hit_count", 0))
        top3_base += int(counts.get("top3_base", 0))

        metrics = summary.get("metrics", {})
        routing_error_count += int(metrics.get("routing_error_count", 0))
        batch_hard = summary.get("hard_errors", {})
        for key in hard_errors:
            hard_errors[key] += int(batch_hard.get(key, 0))

    candidate_base = total_candidates or 1
    top3_denominator = top3_base or 1

    aggregated = {
        "contact_accuracy": round(contact_matches / candidate_base, 4),
        "priority_accuracy": round(priority_matches / candidate_base, 4),
        "decision_accuracy": round(decision_matches / candidate_base, 4),
        "top3_hit_rate": round(top3_hit_count / top3_denominator, 4),
        "false_positive_rate": round(false_positive / candidate_base, 4),
        "false_negative_rate": round(false_negative / candidate_base, 4),
        "reason_accuracy": round(reason_matches / candidate_base, 4),
    }
    aggregated["routing_error_count"] = routing_error_count
    aggregated["score"] = compute_score(aggregated, weights)
    aggregated["hard_errors"] = hard_errors
    return aggregated


def discover_suite(name: str) -> Dict[str, Any]:
    if name not in SUITE_BATCH_IDS:
        raise ValueError(f"Unsupported suite: {name}")

    batch_id = SUITE_BATCH_IDS[name]
    batch_dir = PROJECT_ROOT / "evals" / "calibration_set" / batch_id
    if not batch_dir.exists():
        raise FileNotFoundError(f"Calibration batch not found for {name}: {batch_dir}")

    batch_input_path = batch_dir / "batch_input.json"
    human_labels_path = batch_dir / "human_labels.json"
    expected_summary_path = batch_dir / "expected_summary.json"
    notes_path = batch_dir / "notes.md"

    missing_required = [
        str(path.relative_to(PROJECT_ROOT))
        for path in (batch_input_path, human_labels_path)
        if not path.exists()
    ]
    if missing_required:
        raise FileNotFoundError(
            f"Calibration batch exists for {name}, but required files are missing: {', '.join(missing_required)}"
        )

    return {
        "suite_name": name,
        "batch_id": batch_id,
        "expected_template": SUITE_EXPECTED_TEMPLATES[name],
        "batch_input_path": batch_input_path,
        "human_labels_path": human_labels_path,
        "expected_summary_path": expected_summary_path if expected_summary_path.exists() else None,
        "notes_path": notes_path if notes_path.exists() else None,
    }


def _resolve_final_output_path(run_dir: Path, batch_id: str) -> Path:
    nested_path = run_dir / batch_id / "final_output.json"
    direct_path = run_dir / "final_output.json"

    if nested_path.exists():
        return nested_path
    if direct_path.exists():
        return direct_path

    raise FileNotFoundError(
        "final_output.json not found. Checked: "
        f"{direct_path} and {nested_path}"
    )


def load_batch_payload(
    suite: Dict[str, Any],
    run_dir: Path,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any], Dict[str, str]]:
    batch_input = load_json(suite["batch_input_path"])
    human_labels = load_json(suite["human_labels_path"])
    expected_summary_path = suite.get("expected_summary_path")
    expected_summary = load_json(expected_summary_path) if expected_summary_path else {}

    final_output_path = _resolve_final_output_path(run_dir, suite["batch_id"])
    final_output = load_json(final_output_path)

    source_paths = {
        "batch_input": str(suite["batch_input_path"]),
        "human_labels": str(suite["human_labels_path"]),
        "final_output": str(final_output_path),
    }
    if expected_summary_path:
        source_paths["expected_summary"] = str(expected_summary_path)
    if suite.get("notes_path"):
        source_paths["notes"] = str(suite["notes_path"])

    return batch_input, human_labels, expected_summary, final_output, source_paths


def detect_routing_error(batch_input: Dict[str, Any], expected_template: str) -> int:
    jd = batch_input.get("jd", {}) if isinstance(batch_input, dict) else {}
    route = identify_sequence_with_meta(str(jd.get("title") or ""))
    current_template = getattr(route, "template_id", "")
    return 0 if current_template == expected_template else 1
