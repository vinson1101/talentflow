from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.runner import run as run_output_processing
from core.sequence_identifier import identify_sequence_with_meta


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
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
        }

    count = len(batch_summaries)
    totals = {
        "contact_accuracy": 0.0,
        "priority_accuracy": 0.0,
        "decision_accuracy": 0.0,
        "top3_hit_rate": 0.0,
        "false_positive_rate": 0.0,
        "false_negative_rate": 0.0,
        "reason_accuracy": 0.0,
    }
    routing_error_count = 0
    hard_errors = {
        "hard_mismatch_false_positive": 0,
        "low_fit_high_willingness_promoted": 0,
        "routing_error_count": 0,
        "new_high_priority_false_positive": 0,
    }

    for summary in batch_summaries:
        metrics = summary.get("metrics", {})
        for key in totals:
            totals[key] += float(metrics.get(key, 0))
        routing_error_count += int(metrics.get("routing_error_count", 0))
        batch_hard = summary.get("hard_errors", {})
        for key in hard_errors:
            hard_errors[key] += int(batch_hard.get(key, 0))

    aggregated = {key: round(value / count, 4) for key, value in totals.items()}
    aggregated["routing_error_count"] = routing_error_count
    aggregated["score"] = compute_score(aggregated, weights)
    aggregated["hard_errors"] = hard_errors
    return aggregated


def build_model_output(candidate_id: str, template_id: str, decision: str, priority: str, should_contact: bool = True) -> str:
    payload = {
        "overall_diagnosis": "judge fixture",
        "batch_advice": "judge fixture",
        "top_recommendations": [
            {
                "candidate_id": candidate_id,
                "rank": 1,
                "total_score": 85,
                "decision": decision,
                "priority": priority,
                "action_timing": "today",
                "core_judgement": "judge candidate",
                "reasons": ["reason 1", "reason 2", "reason 3"],
                "risks": ["risk 1"],
                "score_breakdown": {
                    "hard_skill": 80,
                    "experience": 80,
                    "stability": 80,
                    "potential": 80,
                    "conversion": 80
                },
                "structured_score": {
                    "template_id": template_id,
                    "dimension_scores": {
                        "hard_skill_match": 80,
                        "experience_depth": 80,
                        "innovation_potential": 75,
                        "execution_goal_breakdown": 80,
                        "team_fit": 75,
                        "willingness": 95,
                        "stability": 70
                    },
                    "weight_snapshot": {},
                    "dimension_evidence": {}
                },
                "action": {
                    "should_contact": should_contact,
                    "hook_message": "hook",
                    "verification_question": "question",
                    "message_template": "template",
                    "deep_questions": ["q1", "q2", "q3"]
                }
            }
        ]
    }
    return json.dumps(payload, ensure_ascii=False)


def discover_suite(name: str) -> Dict[str, Any]:
    calibration_root = PROJECT_ROOT / "evals" / "calibration_set"
    golden_root = PROJECT_ROOT / "evals" / "golden_set"

    if name == "product":
        calibration_batch_dir = calibration_root / "product_manager_batch_001"
        golden_batch_dir = golden_root / "product_manager_batch_001"
        batch_input_path = calibration_batch_dir / "batch_input.json"
        if not batch_input_path.exists():
            batch_input_path = golden_batch_dir / "batch_input.json"
        model_output_path = calibration_batch_dir / "huntmind_output.json"
        if not model_output_path.exists():
            model_output_path = golden_batch_dir / "huntmind_output.json"
        return {
            "suite_name": "product",
            "batch_id": "product_manager_batch_001",
            "mode": "cached",
            "expected_template": "product_manager",
            "batch_input_path": batch_input_path,
            "model_output_path": model_output_path,
            "human_labels_path": calibration_batch_dir / "human_labels.json",
            "expected_summary_path": calibration_batch_dir / "expected_summary.json",
            "source_paths": {
                "batch_input": str(batch_input_path),
                "model_output": str(model_output_path),
                "human_labels": str(calibration_batch_dir / "human_labels.json"),
                "expected_summary": str(calibration_batch_dir / "expected_summary.json"),
            },
        }

    if name == "frontend_dev":
        batch_input = {
            "jd": {
                "title": "前端开发工程师",
                "must_have": ["React", "TypeScript", "前端工程化"],
                "nice_to_have": ["性能优化"],
                "salary_range": "25-35K",
                "base_location": "上海",
                "seniority_level": "mid"
            },
            "candidates": [
                {
                    "id": "frontend_001",
                    "name": "前端开发样本",
                    "raw_resume": "前端开发工程师，熟悉 React TypeScript 前端工程化，上海，期望 30K",
                    "location": "上海",
                    "expected_salary": "30K"
                }
            ]
        }
        return {
            "suite_name": "frontend_dev",
            "batch_id": "frontend_dev_fixture_001",
            "mode": "fixture",
            "expected_template": "rd_engineer",
            "batch_input": batch_input,
            "model_output_text": build_model_output("frontend_001", "rd_engineer", "yes", "A"),
            "human_labels": [
                {
                    "candidate_id": "frontend_001",
                    "should_contact": True,
                    "priority": "A",
                    "decision": "yes",
                    "match_fit": "high",
                    "recruitability": "high",
                    "mismatch_type": "none",
                    "primary_reason": "fit_and_reachable",
                    "comment": "前端开发样本"
                }
            ],
            "expected_summary": {
                "expected_top_contact_ids": ["frontend_001"],
                "expected_no_contact_ids": [],
                "risk_focus": ["前端开发不应误路由到 product"]
            }
        }

    if name == "blockchain_lead":
        batch_input = {
            "jd": {
                "title": "区块链业务负责人",
                "must_have": ["渠道合作", "战略合作", "香港市场资源"],
                "nice_to_have": ["交易所合作"],
                "salary_range": "40-60K",
                "base_location": "香港",
                "seniority_level": "senior",
                "domain_tags": ["web3", "bd"]
            },
            "candidates": [
                {
                    "id": "blockchain_001",
                    "name": "区块链业务负责人样本",
                    "raw_resume": "Web3 BD 负责人，负责交易所、钱包、机构合作，香港市场渠道资源，战略合作协议谈判",
                    "location": "香港",
                    "expected_salary": "50K"
                }
            ]
        }
        return {
            "suite_name": "blockchain_lead",
            "batch_id": "blockchain_lead_fixture_001",
            "mode": "fixture",
            "expected_template": "sales_director",
            "batch_input": batch_input,
            "model_output_text": build_model_output("blockchain_001", "sales_director", "strong_yes", "A"),
            "human_labels": [
                {
                    "candidate_id": "blockchain_001",
                    "should_contact": True,
                    "priority": "A",
                    "decision": "strong_yes",
                    "match_fit": "high",
                    "recruitability": "high",
                    "mismatch_type": "none",
                    "primary_reason": "fit_and_reachable",
                    "comment": "区块链 BD 样本"
                }
            ],
            "expected_summary": {
                "expected_top_contact_ids": ["blockchain_001"],
                "expected_no_contact_ids": [],
                "risk_focus": ["区块链业务负责人不应再误路由到 product_manager"]
            }
        }

    if name == "sales_director":
        batch_input = {
            "jd": {
                "title": "销售总监",
                "must_have": ["大客户销售", "渠道管理"],
                "nice_to_have": ["汽车行业"],
                "salary_range": "30-40K",
                "base_location": "上海",
                "seniority_level": "senior"
            },
            "candidates": [
                {
                    "id": "sales_001",
                    "name": "销售总监样本",
                    "raw_resume": "高级产品经理，负责 PRD、需求分析、增长策略，对销售岗位有兴趣",
                    "location": "上海",
                    "expected_salary": "35K"
                }
            ]
        }
        return {
            "suite_name": "sales_director",
            "batch_id": "sales_director_fixture_001",
            "mode": "fixture",
            "expected_template": "sales_director",
            "batch_input": batch_input,
            "model_output_text": build_model_output("sales_001", "sales_director", "yes", "A"),
            "human_labels": [
                {
                    "candidate_id": "sales_001",
                    "should_contact": False,
                    "priority": "N",
                    "decision": "no",
                    "match_fit": "low",
                    "recruitability": "high",
                    "mismatch_type": "hard_mismatch",
                    "primary_reason": "hard_mismatch",
                    "comment": "低匹配高意愿样本"
                }
            ],
            "expected_summary": {
                "expected_top_contact_ids": [],
                "expected_no_contact_ids": ["sales_001"],
                "risk_focus": ["low_fit + high_willingness 不得被抬成 yes"]
            }
        }

    raise ValueError(f"Unsupported suite: {name}")


def load_batch_payload(suite: Dict[str, Any]) -> Tuple[Dict[str, Any], str, List[Dict[str, Any]], Dict[str, Any]]:
    if suite["mode"] == "cached":
        batch_input_text = (suite["batch_input_path"]).read_text(encoding="utf-8")
        model_output_text = (suite["model_output_path"]).read_text(encoding="utf-8")
        human_labels = load_json(suite["human_labels_path"])
        expected_summary = load_json(suite["expected_summary_path"])
        return json.loads(batch_input_text), model_output_text, human_labels, expected_summary

    return suite["batch_input"], suite["model_output_text"], suite["human_labels"], suite["expected_summary"]


def run_batch_through_runner(batch_input: Dict[str, Any], model_output_text: str) -> Dict[str, Any]:
    return run_output_processing(batch_input, model_output_text)["json"]


def detect_routing_error(batch_input: Dict[str, Any], expected_template: str) -> int:
    jd = batch_input.get("jd", {}) if isinstance(batch_input, dict) else {}
    route = identify_sequence_with_meta(str(jd.get("title") or ""))
    current_template = getattr(route, "template_id", "")
    return 0 if current_template == expected_template else 1
