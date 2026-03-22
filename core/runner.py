import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

LOG_FILE = "feedback_loop.jsonl"

VALID_DECISIONS = {"strong_yes", "yes", "maybe", "no"}
VALID_PRIORITIES = {"A", "B", "C"}
VALID_TIMINGS = {"today", "this_week", "optional"}
PRIORITY_ORDER = {"A": 0, "B": 1, "C": 2}
TIMING_ORDER = {"today": 0, "this_week": 1, "optional": 2}


# ==============================
# 0. 基础工具函数
# ==============================
def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clamp_score(value: Any, default: float = 0) -> float:
    if not _is_number(value):
        value = default
    return max(0, min(100, float(value)))


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_str_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    cleaned = []
    for v in values:
        s = _clean_text(v)
        if s:
            cleaned.append(s)
    return cleaned


def _normalize_risk(value: Any) -> str:
    if isinstance(value, dict):
        return _clean_text(value.get("description"))
    return _clean_text(value)


def _clean_risk_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []

    cleaned = []
    for value in values:
        risk = _normalize_risk(value)
        if risk:
            cleaned.append(risk)
    return cleaned


def _build_candidate_lookup(input_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    candidates = input_data.get("candidates", [])
    if not isinstance(candidates, list):
        return {}

    lookup: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_id = _clean_text(candidate.get("id"))
        if candidate_id:
            lookup[candidate_id] = candidate
    return lookup


def _extract_role_label(candidate: Dict[str, Any]) -> str:
    for key in ("role_label", "job_title", "title"):
        value = _clean_text(candidate.get(key))
        if value:
            return value

    extra_info = _clean_text(candidate.get("extra_info"))
    match = re.search(r"(高级产品经理|产品经理|项目经理|产品运营|运营经理|销售经理|研发工程师|工程师)", extra_info)
    if match:
        return match.group(1)

    candidate_id = _clean_text(candidate.get("candidate_id"))
    segments = [segment for segment in re.split(r"[_\-\s]+", candidate_id) if segment]
    role_keywords = ("产品经理", "高级产品经理", "项目经理", "运营", "工程师", "销售", "顾问")
    for segment in segments:
        if any(keyword in segment for keyword in role_keywords):
            return segment

    return ""


def _extract_candidate_name(candidate: Dict[str, Any]) -> str:
    for key in ("candidate_name", "name"):
        value = _clean_text(candidate.get(key))
        if value:
            return value

    candidate_id = _clean_text(candidate.get("candidate_id"))
    chinese_segments = re.findall(r"[\u4e00-\u9fff]{2,4}", candidate_id)
    for segment in chinese_segments:
        if segment.endswith(("经理", "总监", "顾问", "工程师", "专员")):
            continue
        if segment in {"本周", "今天", "联系", "可选"}:
            continue
        return segment

    return candidate_id


def _fallback_reasons(candidate: Dict[str, Any]) -> List[str]:
    decision = candidate.get("decision", "maybe")
    priority = candidate.get("priority", "C")

    if decision in {"strong_yes", "yes"} or priority == "A":
        return [
            "简历呈现出与目标岗位较高的相关性，具备优先沟通价值",
            "履历中存在可映射到岗位要求的经验信号，值得进入首轮验证",
            "从背景完整度和匹配度看，具备进一步转化为有效候选人的可能"
        ]

    return [
        "简历中存在部分可迁移经验，具备基础沟通价值",
        "虽然不是强匹配人选，但仍有若干点值得通过电话进一步确认",
        "当前信息显示其具备一定潜力，可作为补充候选进入比较池"
    ]


def _fallback_risks(candidate: Dict[str, Any]) -> List[str]:
    return [
        "简历偏结果摘要，真实职责边界和个人贡献比例需要在首轮沟通中进一步验证"
    ]


def _fallback_deep_questions(candidate: Dict[str, Any]) -> List[str]:
    return [
        "你最近一段最有代表性的项目里，真正由你亲自负责并产生结果的部分是什么？",
        "如果只选一个最能证明你能力的案例，你会讲哪一个？结果是怎么做出来的？",
        "这个岗位很看重落地和转化，你过去有哪些经历能直接证明你具备这种能力？"
    ]


def _build_fallback_message_template(candidate: Dict[str, Any], action: Dict[str, Any]) -> str:
    hook = _clean_text(action.get("hook_message"))
    verification_question = _clean_text(action.get("verification_question"))
    candidate_name = _extract_candidate_name(candidate)
    role_label = _extract_role_label(candidate)
    total_score = _clamp_score(candidate.get("total_score"), default=0)
    core_judgement = _clean_text(candidate.get("core_judgement"))

    if not verification_question:
        verification_question = "你最近一段最能代表你真实能力的项目，具体是怎么做成的？"

    if "高级产品经理" in role_label:
        return (
            f"你好，看到你有较完整的{role_label}经历，我们这边正在看一个更偏复杂业务流程和跨团队推进的岗位。"
            f"你的背景里有几个点和岗位要求比较贴，我想先和你确认一下，你最近一段最能代表你产品判断和落地能力的项目是什么？"
        )

    if "项目经理" in role_label:
        return (
            f"你好，看到你在项目推进和跨团队协同上有比较扎实的经验，我们这边有一个对流程设计和落地推动要求比较高的岗位，和你的背景有一定契合。"
            f"我想先确认一下，你过去最有代表性的复杂项目里，你亲自推动落地的关键动作是什么？"
        )

    if total_score < 75:
        return (
            f"你好，看到你已经有一定{role_label or '相关'}经验，我们这边有一个对执行和成长速度都比较看重的岗位。"
            f"想先和你确认一下，在你最近一段项目经历里，哪些部分是你独立负责并真正推动结果落地的？"
        )

    if hook:
        return (
            f"{hook}\n\n"
            f"我这边正在看一个与你经历方向比较接近的机会，"
            f"不是群发沟通，主要是你的背景里有几个点让我觉得值得优先确认。"
            f"如果你方便，我想先快速和你确认一个问题：{verification_question}"
        )

    if candidate_name:
        return (
            f"你好，{candidate_name}。我最近在看一个与你背景方向比较接近的岗位。"
            "从你的履历信号看，有几个点和岗位需求有一定匹配度，"
            "所以想优先和你确认一下是否值得进一步沟通。"
            f"{core_judgement + '。' if core_judgement else ''}"
            f"我最想先确认的问题是：{verification_question}"
        )

    return (
        "你好，我这边在看一个与你经历方向有一定匹配度的岗位。"
        "不确定你最近是否在主动看机会，但你的背景里有几个点值得优先聊一下。"
        f"如果你方便，我想先确认一个关键问题：{verification_question}"
    )


def _normalize_score_breakdown(score_breakdown: Any, total_score: float) -> Dict[str, float]:
    if not isinstance(score_breakdown, dict):
        score_breakdown = {}

    normalized = {}
    for key in ["hard_skill", "experience", "stability", "potential", "conversion"]:
        normalized[key] = _clamp_score(score_breakdown.get(key), default=total_score)

    return normalized


def _normalize_action(candidate: Dict[str, Any], action: Any) -> Dict[str, Any]:
    if not isinstance(action, dict):
        action = {}

    decision = candidate.get("decision", "maybe")

    should_contact = action.get("should_contact")
    if not isinstance(should_contact, bool):
        should_contact = decision in {"strong_yes", "yes"}

    hook_message = _clean_text(action.get("hook_message"))
    if not hook_message:
        hook_message = "我在看一个岗位时注意到你的背景里有几个点比较贴，这不是群发，我想先和你确认一个关键判断。"

    verification_question = _clean_text(action.get("verification_question"))
    if not verification_question:
        verification_question = "你最近一段最能证明你真实能力的项目，具体是怎么做成的？"

    deep_questions = _clean_str_list(action.get("deep_questions"))
    if len(deep_questions) < 3:
        fallback = _fallback_deep_questions(candidate)
        deep_questions = (deep_questions + fallback)[:3]

    message_template = _clean_text(action.get("message_template"))
    if not message_template:
        message_template = _build_fallback_message_template(
            candidate,
            {
                "hook_message": hook_message,
                "verification_question": verification_question
            }
        )

    return {
        "should_contact": should_contact,
        "hook_message": hook_message,
        "verification_question": verification_question,
        "message_template": message_template,
        "deep_questions": deep_questions
    }


def _sort_recommendations(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (
            PRIORITY_ORDER.get(c.get("priority"), 99),
            TIMING_ORDER.get(c.get("action_timing"), 99),
            -_clamp_score(c.get("total_score"), default=0),
            str(c.get("candidate_id", "")),
        ),
    )

    for idx, candidate in enumerate(sorted_candidates, 1):
        candidate["rank"] = idx

    return sorted_candidates


# ==============================
# 1. JSON 基础验证
# ==============================
def validate_output(output_text: str) -> Dict[str, Any]:
    """
    只做结构性强校验：
    - 必须是合法 JSON
    - 必须是 object
    - 必须有顶层关键字段
    - recommendation 必须是 object
    - recommendation 核心字段必须存在

    不在此处做业务语义兜底，业务兜底交给 sanitize_output
    """
    try:
        data = json.loads(output_text)
    except Exception as e:
        raise ValueError(f"❌ Invalid JSON output: {e}")

    if not isinstance(data, dict):
        raise ValueError("❌ Output must be a JSON object")

    if "overall_diagnosis" not in data:
        raise ValueError("❌ Missing overall_diagnosis")

    if "top_recommendations" not in data:
        raise ValueError("❌ Missing top_recommendations")

    if not isinstance(data["top_recommendations"], list):
        raise ValueError("❌ top_recommendations must be list")

    for i, c in enumerate(data["top_recommendations"]):
        if not isinstance(c, dict):
            raise ValueError(f"❌ recommendation[{i}] must be object")

        required_fields = [
            "candidate_id",
            "rank",
            "total_score",
            "decision",
            "priority",
            "action_timing",
            "core_judgement"
        ]
        for field in required_fields:
            if field not in c:
                raise ValueError(f"❌ recommendation[{i}] missing {field}")

        if "action" in c and not isinstance(c["action"], dict):
            raise ValueError(f"❌ recommendation[{i}].action must be object")

    return data


# ==============================
# 2. 数据清洗与业务兜底
# ==============================
def sanitize_output(data: Dict[str, Any], input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    修正模型可能的输出问题，让系统稳定运行。
    核心原则：
    1. 不用空字符串伪造"合格数组"
    2. message_template 必须永远可发
    3. rank 最终必须连续
    """
    data["overall_diagnosis"] = _clean_text(data.get("overall_diagnosis"))
    data.setdefault("batch_advice", "")
    data["batch_advice"] = _clean_text(data.get("batch_advice"))
    candidate_lookup = _build_candidate_lookup(input_data or {})

    recommendations = data.get("top_recommendations", [])
    sanitized: List[Dict[str, Any]] = []

    for idx, c in enumerate(recommendations, 1):
        if not isinstance(c, dict):
            c = {}

        candidate_id = _clean_text(c.get("candidate_id")) or f"unknown_{idx}"

        total_score = _clamp_score(c.get("total_score"), default=0)

        decision = c.get("decision")
        if decision not in VALID_DECISIONS:
            decision = "maybe"

        priority = c.get("priority")
        if priority not in VALID_PRIORITIES:
            priority = "C"

        action_timing = c.get("action_timing")
        if action_timing not in VALID_TIMINGS:
            action_timing = "optional"

        core_judgement = _clean_text(c.get("core_judgement"))
        source_candidate = candidate_lookup.get(candidate_id, {})
        candidate_name = _clean_text(c.get("candidate_name")) or _clean_text(source_candidate.get("name"))
        role_label = _extract_role_label(c) or _extract_role_label(source_candidate)

        reasons = _clean_str_list(c.get("reasons"))
        if len(reasons) < 3:
            reasons = (reasons + _fallback_reasons(c))[:3]

        risks = _clean_risk_list(c.get("risks"))
        if len(risks) < 1:
            risks = _fallback_risks(c)

        score_breakdown = _normalize_score_breakdown(c.get("score_breakdown"), total_score)

        normalized_candidate = {
            "candidate_id": candidate_id,
            "rank": c.get("rank"),
            "candidate_name": candidate_name,
            "name": candidate_name,
            "role_label": role_label,
            "total_score": total_score,
            "decision": decision,
            "priority": priority,
            "action_timing": action_timing,
            "core_judgement": core_judgement,
            "reasons": reasons,
            "risks": risks,
            "score_breakdown": score_breakdown
        }

        normalized_candidate["action"] = _normalize_action(
            normalized_candidate,
            c.get("action")
        )

        sanitized.append(normalized_candidate)

    data["top_recommendations"] = _sort_recommendations(sanitized)
    return data


# ==============================
# 3. 日志记录
# ==============================
def log_decision(input_data: Dict[str, Any], output_data: Dict[str, Any]):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "input": input_data,
        "output": output_data,
        "feedback": None
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ==============================
# 4. 简单质量评分
# ==============================
def evaluate_output_quality(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    用来判断输出是否存在明显弱化：
    - 没有候选人
    - 没有有效分数
    - 分差过小
    - 没有 A 优先级
    - 默认兜底文案占比过高
    """
    candidates = data.get("top_recommendations", [])

    if not candidates:
        return {
            "quality_score": 0,
            "issue": "no_candidates",
            "quality_flag": "invalid"
        }

    scores = [c.get("total_score", 0) for c in candidates if _is_number(c.get("total_score", 0))]
    if not scores:
        return {
            "quality_score": 0,
            "issue": "no_valid_scores",
            "quality_flag": "invalid"
        }

    avg_score = sum(scores) / len(scores)
    variance = max(scores) - min(scores)

    has_a = any(c.get("priority") == "A" for c in candidates)
    contact_ratio = sum(
        1 for c in candidates if c.get("action", {}).get("should_contact")
    ) / len(candidates)

    fallback_message_count = 0
    for c in candidates:
        msg = _clean_text(c.get("action", {}).get("message_template"))
        if msg.startswith("你好，我这边在看一个与你经历方向有一定匹配度的岗位") or \
           msg.startswith("你好，我最近在看一个与你背景方向比较接近的岗位") or \
           msg.startswith("我在看一个岗位时注意到你的背景里有几个点比较贴"):
            fallback_message_count += 1

    fallback_message_ratio = fallback_message_count / len(candidates)

    quality_flag = "ok"
    issue = ""

    if variance < 10:
        quality_flag = "low_variance"
        issue = "scores_too_close"

    if not has_a and len(candidates) >= 3:
        quality_flag = "weak_ranking"
        issue = "no_priority_a"

    if fallback_message_ratio > 0.5:
        quality_flag = "weak_action_quality"
        issue = "too_many_fallback_messages"

    quality_score = 100
    if variance < 10:
        quality_score -= 20
    if not has_a and len(candidates) >= 3:
        quality_score -= 15
    if fallback_message_ratio > 0.5:
        quality_score -= 15

    return {
        "quality_score": max(0, quality_score),
        "avg_score": round(avg_score, 2),
        "score_variance": round(variance, 2),
        "candidate_count": len(candidates),
        "has_priority_a": has_a,
        "contact_ratio": round(contact_ratio, 2),
        "fallback_message_ratio": round(fallback_message_ratio, 2),
        "quality_flag": quality_flag,
        "issue": issue
    }


# ==============================
# 5. Markdown 渲染（给飞书/人看）
# ==============================
def render_human_readable(data: Dict[str, Any]) -> str:
    lines = []

    if data.get("overall_diagnosis"):
        lines.append("## 📋 整体诊断\n")
        lines.append(f"{data['overall_diagnosis']}\n")

    if data.get("batch_advice"):
        lines.append("## 💡 批量建议\n")
        lines.append(f"{data['batch_advice']}\n")

    recommendations = data.get("top_recommendations", [])
    if not recommendations:
        return "\n".join(lines)

    lines.append("## 🎯 推荐候选人\n")

    priority_map = {
        "A": "🔥 必须今天联系",
        "B": "👍 本周联系",
        "C": "👌 备选"
    }

    decision_map = {
        "strong_yes": "💚 强烈推荐",
        "yes": "✅ 建议联系",
        "maybe": "⏸️ 观察",
        "no": "❌ 不推荐"
    }

    timing_map = {
        "today": "⚡ 今天",
        "this_week": "📅 本周",
        "optional": "🔖 可选"
    }

    for c in recommendations:
        lines.append(
            f"\n### Rank #{c.get('rank', '-')} | "
            f"{priority_map.get(c.get('priority'), '')} - {c.get('candidate_id', '')}"
        )
        lines.append(
            f"**得分**: {c.get('total_score', 0)} | "
            f"**决策**: {decision_map.get(c.get('decision'))} | "
            f"**时机**: {timing_map.get(c.get('action_timing'))}\n"
        )

        if c.get("core_judgement"):
            lines.append(f"**🎯 核心判断**: {c['core_judgement']}\n")

        sb = c.get("score_breakdown", {})
        if sb:
            lines.append(
                f"**📊 评分拆解**: "
                f"硬技能 {sb.get('hard_skill', 0)} / "
                f"经验 {sb.get('experience', 0)} / "
                f"稳定性 {sb.get('stability', 0)} / "
                f"潜力 {sb.get('potential', 0)} / "
                f"转化率 {sb.get('conversion', 0)}\n"
            )

        if c.get("reasons"):
            lines.append("**✨ 优势**:")
            for r in c["reasons"][:3]:
                lines.append(f"- {r}")
            lines.append("")

        if c.get("risks"):
            lines.append("**⚠️ 风险**:")
            for r in c["risks"][:3]:
                lines.append(f"- {r}")
            lines.append("")

        action = c.get("action", {})

        if action.get("hook_message"):
            lines.append("**🪝 钩子话术**:")
            lines.append("```")
            lines.append(action["hook_message"])
            lines.append("```")

        if action.get("verification_question"):
            lines.append("**🎯 验证问题**:")
            lines.append(action["verification_question"])
            lines.append("")

        if action.get("message_template"):
            lines.append("**💬 完整联系话术**:")
            lines.append("```")
            lines.append(action["message_template"])
            lines.append("```")

        if action.get("deep_questions"):
            lines.append("**🔍 深问问题**:")
            for q in action["deep_questions"][:3]:
                lines.append(f"- {q}")
            lines.append("")

        lines.append("---")

    return "\n".join(lines)


# ==============================
# 6. 主入口
# ==============================
def run(input_data: dict, output_text: str):
    """
    主流程：
    1. JSON 结构验证
    2. 容错与业务兜底
    3. 写日志
    4. 输出质量评估
    5. 人类可读渲染
    """
    output_data = validate_output(output_text)
    output_data = sanitize_output(output_data, input_data=input_data)

    log_decision(input_data, output_data)

    quality = evaluate_output_quality(output_data)
    human_readable = render_human_readable(output_data)

    return {
        "json": output_data,
        "display": human_readable,
        "meta": quality
    }
