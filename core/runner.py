import ast
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

LOG_FILE = "feedback_loop.jsonl"

VALID_DECISIONS = {"strong_yes", "yes", "maybe", "no"}
VALID_PRIORITIES = {"A", "B", "C"}
VALID_TIMINGS = {"today", "this_week", "optional"}
PRIORITY_ORDER = {"A": 0, "B": 1, "C": 2}
TIMING_ORDER = {"today": 0, "this_week": 1, "optional": 2}

ROLE_KEYWORDS = (
    "高级产品经理",
    "产品经理",
    "项目经理",
    "产品专员",
    "产品运营",
    "运营经理",
    "销售经理",
    "研发工程师",
    "工程师",
    "顾问",
)
LOCATION_KEYWORDS = {
    "杭州", "宁波", "上海", "北京", "深圳", "广州", "苏州", "南京", "成都",
    "武汉", "厦门", "天津", "青岛", "西安", "重庆", "长沙", "无锡", "嘉兴",
}
NAME_STOPWORDS = {
    "local", "resume", "candidate", "unknown", "today", "this", "week", "optional",
    "contact", "rank", "name", "title", "jd", "简历", "候选人", "推荐", "联系",
    "今天", "本周", "可选", "待定", "待确认", "未知", "岗位", "杭州11", "宁波8",
}


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

    cleaned: List[str] = []
    for value in values:
        text = _clean_text(value)
        if text:
            cleaned.append(text)
    return cleaned


def _try_parse_dict_like(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return value

    text = _clean_text(value)
    if not text or not text.startswith("{") or not text.endswith("}"):
        return None

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _normalize_risk(value: Any) -> str:
    parsed = _try_parse_dict_like(value)
    if parsed is not None:
        return _clean_text(parsed.get("description") or parsed.get("risk") or parsed.get("text"))
    if isinstance(value, dict):
        return _clean_text(value.get("description") or value.get("risk") or value.get("text"))
    return _clean_text(value)


def _clean_risk_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []

    cleaned: List[str] = []
    seen = set()
    for value in values:
        risk = _normalize_risk(value)
        if risk and risk not in seen:
            cleaned.append(risk)
            seen.add(risk)
    return cleaned


def _build_candidate_lookup(input_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    candidates = input_data.get("candidates", [])
    if not isinstance(candidates, list):
        return {}

    lookup: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        for key in ("id", "candidate_id", "file_id"):
            candidate_id = _clean_text(candidate.get(key))
            if candidate_id:
                lookup[candidate_id] = candidate
    return lookup


def _split_identifier_tokens(value: str) -> List[str]:
    text = _clean_text(value)
    if not text:
        return []
    tokens = re.split(r"[\s_\-【】\[\]\(\)（）/|]+", text)
    return [token.strip() for token in tokens if token and token.strip()]


def _is_hash_like(token: str) -> bool:
    text = _clean_text(token)
    return bool(text) and bool(re.fullmatch(r"[0-9a-f]{8,}", text, flags=re.IGNORECASE))


def _is_salary_token(token: str) -> bool:
    text = _clean_text(token)
    if not text:
        return False
    return bool(re.fullmatch(r"\d{1,2}\s*[kK]", text)) or bool(re.fullmatch(r"\d{1,2}\s*-\s*\d{1,2}\s*[kK]", text))


def _is_experience_token(token: str) -> bool:
    text = _clean_text(token)
    if not text:
        return False
    return bool(re.fullmatch(r"\d+\s*年", text)) or text in {"1年以内", "应届", "在读"}


def _is_location_like(token: str) -> bool:
    text = _clean_text(token)
    if not text:
        return False
    if text in LOCATION_KEYWORDS:
        return True
    return any(city in text for city in LOCATION_KEYWORDS) and bool(re.search(r"\d", text))


def _looks_like_role(token: str) -> bool:
    text = _clean_text(token)
    if not text:
        return False
    return any(keyword in text for keyword in ROLE_KEYWORDS)


def _looks_like_composite_name(value: Any) -> bool:
    text = _clean_text(value)
    if not text:
        return False
    if len(_split_identifier_tokens(text)) >= 3:
        composite_signals = [
            bool(re.search(r"\d", text)),
            any(keyword in text for keyword in ROLE_KEYWORDS),
            any(city in text for city in LOCATION_KEYWORDS),
            "K" in text.upper(),
            "年" in text,
            "【" in text or "】" in text,
        ]
        if sum(1 for signal in composite_signals if signal) >= 2:
            return True
    return False


def _looks_like_person_name(token: str) -> bool:
    text = _clean_text(token)
    if not text:
        return False
    if text.lower() in NAME_STOPWORDS:
        return False
    if _looks_like_role(text) or _is_salary_token(text) or _is_experience_token(text) or _is_location_like(text):
        return False
    if _is_hash_like(text) or bool(re.search(r"\d", text)):
        return False
    if len(text) > 20:
        return False
    if re.fullmatch(r"[\u4e00-\u9fff]{2,6}", text):
        return True
    if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,29}", text):
        return True
    return False


def _find_name_in_identifier(identifier: Any) -> str:
    tokens = _split_identifier_tokens(_clean_text(identifier))
    if not tokens:
        return ""

    for token in reversed(tokens):
        if _looks_like_person_name(token):
            return token

    chinese_segments = re.findall(r"[\u4e00-\u9fff]{2,6}", _clean_text(identifier))
    for segment in reversed(chinese_segments):
        if _looks_like_person_name(segment):
            return segment

    return ""


def _iter_name_candidates(candidate: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for key in ("resume_name", "parsed_name", "real_name", "full_name", "name", "candidate_name"):
        value = _clean_text(candidate.get(key))
        if value:
            values.append(value)

    for nested_key in ("basic_info", "profile", "resume_info"):
        nested = candidate.get(nested_key)
        if isinstance(nested, dict):
            for key in ("resume_name", "parsed_name", "real_name", "full_name", "name", "candidate_name"):
                value = _clean_text(nested.get(key))
                if value:
                    values.append(value)

    return values


def _pick_best_name(*candidates: str) -> str:
    clean_candidates: List[str] = []
    for value in candidates:
        text = _clean_text(value)
        if not text:
            continue
        clean_candidates.append(text)

    for value in clean_candidates:
        if _looks_like_person_name(value):
            return value

    for value in clean_candidates:
        if not _looks_like_composite_name(value):
            extracted = _find_name_in_identifier(value)
            if extracted:
                return extracted
            if _looks_like_person_name(value):
                return value

    for value in clean_candidates:
        extracted = _find_name_in_identifier(value)
        if extracted:
            return extracted

    return clean_candidates[0] if clean_candidates else ""


def _extract_candidate_name(candidate: Dict[str, Any], source_candidate: Optional[Dict[str, Any]] = None) -> str:
    source_candidate = source_candidate or {}

    source_names = _iter_name_candidates(source_candidate)
    model_names = _iter_name_candidates(candidate)

    identifier_candidates = [
        _clean_text(source_candidate.get("candidate_id")),
        _clean_text(source_candidate.get("id")),
        _clean_text(candidate.get("candidate_id")),
        _clean_text(candidate.get("id")),
    ]

    return _pick_best_name(*(source_names + model_names + identifier_candidates))


def _extract_role_label(candidate: Dict[str, Any], source_candidate: Optional[Dict[str, Any]] = None) -> str:
    for current in (candidate, source_candidate or {}):
        for key in ("role_label", "job_title", "title"):
            value = _clean_text(current.get(key))
            if value:
                return value

        extra_info = _clean_text(current.get("extra_info"))
        match = re.search(r"(高级产品经理|产品经理|项目经理|产品专员|产品运营|运营经理|销售经理|研发工程师|工程师)", extra_info)
        if match:
            return match.group(1)

        identifier = _clean_text(current.get("candidate_id")) or _clean_text(current.get("id"))
        for token in _split_identifier_tokens(identifier):
            if _looks_like_role(token):
                return token

    return ""


def _extract_experience_label(candidate: Dict[str, Any], source_candidate: Optional[Dict[str, Any]] = None) -> str:
    for current in (candidate, source_candidate or {}):
        for key in ("experience_label", "years_of_experience", "work_years"):
            value = _clean_text(current.get(key))
            if value:
                return value

        extra_info = _clean_text(current.get("extra_info"))
        match = re.search(r"(\d+\s*年|1年以内|应届)", extra_info)
        if match:
            return match.group(1)

        identifier = _clean_text(current.get("candidate_id")) or _clean_text(current.get("id"))
        match = re.search(r"(\d+\s*年|1年以内|应届)", identifier)
        if match:
            return match.group(1)

    return ""


def _fallback_reasons(candidate: Dict[str, Any]) -> List[str]:
    decision = candidate.get("decision", "maybe")
    priority = candidate.get("priority", "C")
    role_label = _extract_role_label(candidate)
    experience_label = _extract_experience_label(candidate)

    if "项目经理" in role_label:
        return [
            "具备项目推进和跨团队协同经验，需要进一步核实与产品岗位的职责重合度",
            "简历中呈现出一定需求沟通与落地推动能力，具备首轮沟通价值",
            "适合作为相关方向候选人，重点验证产品设计 ownership 与业务理解深度",
        ]

    if decision in {"strong_yes", "yes"} or priority == "A":
        return [
            f"具备与目标岗位较高相关度的{role_label or '产品'}经验，适合优先进入首轮沟通",
            f"履历中存在可映射到岗位要求的经验信号，{experience_label or '经验成熟度'}具备一定竞争力",
            "从背景完整度和匹配度看，具备进一步转化为有效候选人的可能",
        ]

    return [
        "简历中存在部分可迁移经验，具备基础沟通价值",
        "当前信息显示其具备一定潜力，但关键能力仍需通过电话进一步核实",
        "更适合作为补充候选进入比较池，避免过早给出过强判断",
    ]


def _fallback_risks(candidate: Dict[str, Any]) -> List[str]:
    role_label = _extract_role_label(candidate)
    experience_label = _extract_experience_label(candidate)

    if "项目经理" in role_label:
        return ["项目推进经验较强，但产品设计与功能定义的直接 ownership 需要首轮重点验证"]

    if experience_label in {"1年以内", "应届"} or experience_label.startswith("1年") or experience_label.startswith("2年"):
        return ["年限相对偏短，独立负责复杂需求和跨团队推动的深度需要进一步确认"]

    return ["简历偏结果摘要，真实职责边界和个人贡献比例需要在首轮沟通中进一步验证"]


def _build_personalized_hook_message(candidate: Dict[str, Any]) -> str:
    role_label = _extract_role_label(candidate)
    experience_label = _extract_experience_label(candidate)
    priority = _clean_text(candidate.get("priority"))
    decision = _clean_text(candidate.get("decision"))

    if "项目经理" in role_label:
        return "您好，看到您有项目推进和跨团队协同经验，我们这边有一个更偏产品落地与流程设计的岗位，想先和您沟通一下匹配度。"

    if "高级产品经理" in role_label:
        return "您好，看到您有较完整的高级产品/复杂业务产品经历，我们这边在看一个偏B端和跨团队推进的岗位，想和您进一步聊聊。"

    if experience_label in {"1年以内", "应届"} or experience_label.startswith("1年") or experience_label.startswith("2年"):
        return "您好，看到您已有一定产品相关经历，我们这边有一个会比较看重需求分析和成长速度的岗位，想先了解一下您的实际负责深度。"

    if priority == "A" or decision in {"strong_yes", "yes"}:
        return "您好，看到您过往经历里有几个点和我们当前岗位比较贴合，不是群发沟通，想优先和您确认一下匹配度。"

    return "您好，看到您有产品相关背景，我们这边有一个方向接近的岗位，想先和您快速了解一下实际项目经历。"


def _build_personalized_verification_question(candidate: Dict[str, Any]) -> str:
    role_label = _extract_role_label(candidate)
    experience_label = _extract_experience_label(candidate)

    if "项目经理" in role_label:
        return "您过往最有代表性的项目里，哪些需求定义、方案取舍和落地动作是您亲自负责推动的？"

    if "高级产品经理" in role_label:
        return "您最近一段最能体现产品判断和复杂业务拆解能力的项目，具体是怎么推进落地的？"

    if experience_label in {"1年以内", "应届"} or experience_label.startswith("1年") or experience_label.startswith("2年"):
        return "在您最近一段项目经历里，哪些需求分析、原型或推动落地的环节是您独立负责的？"

    return "您最近最有代表性的项目里，真正由您亲自负责并推动结果落地的部分是什么？"


def _build_personalized_deep_questions(candidate: Dict[str, Any]) -> List[str]:
    role_label = _extract_role_label(candidate)

    if "项目经理" in role_label:
        return [
            "如果把您最近的代表项目拆开看，哪些需求定义和方案判断是您而不是研发或客户主导的？",
            "您过去做项目推进时，遇到需求冲突或优先级拉扯，通常如何取舍并推动共识？",
            "如果转到更偏产品的岗位，您认为自己最能迁移过来的能力是什么？",
        ]

    if "高级产品经理" in role_label:
        return [
            "您最近一段最复杂的B端场景里，是如何完成需求拆解、优先级取舍和方案落地的？",
            "当业务目标、研发资源和上线节奏发生冲突时，您通常如何做产品判断？",
            "您过去哪些经历最能证明自己不仅能写需求，还能推动跨团队协作与结果转化？",
        ]

    return [
        "您最近一段最有代表性的项目里，真正由您亲自负责并产生结果的部分是什么？",
        "如果只选一个最能证明您能力的案例，您会讲哪一个？结果是怎么做出来的？",
        "这个岗位比较看重业务理解和落地推进，您过去有哪些经历能直接证明这一点？",
    ]


def _is_generic_hook_message(message: str) -> bool:
    text = _clean_text(message)
    if not text:
        return True
    generic_patterns = (
        "看到您有产品经理经验",
        "想和您聊聊一个高级产品经理的机会",
        "看到您有产品经理相关经验",
        "想和您聊聊一个",
    )
    return any(pattern in text for pattern in generic_patterns)


def _is_generic_verification_question(question: str) -> bool:
    text = _clean_text(question)
    if not text:
        return True
    generic_patterns = (
        "最近最有代表性的项目是什么",
        "最能证明你真实能力的项目",
    )
    return any(pattern in text for pattern in generic_patterns)


def _is_generic_deep_questions(questions: List[str]) -> bool:
    if len(questions) < 3:
        return True
    joined = " ".join(_clean_text(question) for question in questions)
    generic_patterns = (
        "您最有成就感的项目是什么",
        "您对B端产品设计的理解是什么",
        "真正由你亲自负责并产生结果的部分是什么",
    )
    return sum(1 for pattern in generic_patterns if pattern in joined) >= 2


def _build_fallback_message_template(candidate: Dict[str, Any], action: Dict[str, Any]) -> str:
    hook = _clean_text(action.get("hook_message"))
    verification_question = _clean_text(action.get("verification_question"))
    candidate_name = _extract_candidate_name(candidate)
    role_label = _extract_role_label(candidate)
    total_score = _clamp_score(candidate.get("total_score"), default=0)
    core_judgement = _clean_text(candidate.get("core_judgement"))

    if not verification_question:
        verification_question = _build_personalized_verification_question(candidate)

    if "高级产品经理" in role_label:
        return (
            f"您好，{candidate_name or '这边'}。看到您有较完整的{role_label}经历，我们正在招聘一个偏B端与复杂业务流程推进的岗位。"
            f"您的背景里有几个点和岗位要求比较贴，所以想优先和您确认一下：{verification_question}"
        )

    if "项目经理" in role_label:
        return (
            f"您好，{candidate_name or '这边'}。看到您在项目推进和跨团队协同上有比较扎实的经验，我们这边有一个更偏产品落地与流程设计的岗位。"
            f"如果您方便，我想先确认一下：{verification_question}"
        )

    if total_score < 75:
        return (
            f"您好，{candidate_name or '这边'}。看到您已经有一定{role_label or '相关'}经验，我们这边有一个会比较看重需求分析、执行力和成长速度的岗位。"
            f"想先和您确认一下，在您最近一段项目经历里，哪些部分是您独立负责并真正推动结果落地的？"
        )

    if hook:
        return (
            f"{hook}\n\n"
            "我这边正在看一个与你经历方向比较接近的机会，不是群发沟通，主要是你的背景里有几个点让我觉得值得优先确认。"
            f"如果您方便，我想先快速和您确认一个问题：{verification_question}"
        )

    judgement_part = f"{core_judgement} " if core_judgement else ""
    return (
        f"您好，{candidate_name or '这边'}。我最近在看一个与您背景方向比较接近的岗位。"
        f"{judgement_part}从您的履历信号看，有几个点和岗位需求有一定匹配度，所以想优先确认是否值得进一步沟通。"
        f"我最想先确认的问题是：{verification_question}"
    )


def _is_generic_message_template(message: str) -> bool:
    text = _clean_text(message)
    if not text:
        return True
    generic_patterns = (
        "看到您有产品经理相关经验",
        "岗位要求与您的背景匹配",
        "看到您有产品经理经验",
        "想和您聊聊一个高级产品经理的机会",
    )
    return any(pattern in text for pattern in generic_patterns)


def _is_generic_core_judgement(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return True
    generic_patterns = (
        "符合JD要求，建议联系",
        "符合 JD 要求，建议联系",
        "可作为备选",
        "综合评分",
    )
    generic_hits = sum(1 for pattern in generic_patterns if pattern in cleaned)
    if generic_hits >= 2:
        return True
    if "项目经理" in cleaned and "符合JD要求" in cleaned:
        return True
    return False


def _normalize_score_breakdown(score_breakdown: Any, total_score: float) -> Dict[str, float]:
    if not isinstance(score_breakdown, dict):
        score_breakdown = {}

    normalized = {}
    for key in ["hard_skill", "experience", "stability", "potential", "conversion"]:
        normalized[key] = _clamp_score(score_breakdown.get(key), default=total_score)

    return normalized


def _build_core_judgement(candidate: Dict[str, Any]) -> str:
    candidate_name = _extract_candidate_name(candidate)
    role_label = _extract_role_label(candidate)
    priority = _clean_text(candidate.get("priority"))
    decision = _clean_text(candidate.get("decision"))
    score = int(_clamp_score(candidate.get("total_score"), 0))

    if "项目经理" in role_label:
        if decision in {"strong_yes", "yes"}:
            return f"{candidate_name or '该候选人'}具备项目推进与跨团队协同经验，适合进入首轮沟通，重点核实产品设计与需求定义的直接职责深度。"
        return f"{candidate_name or '该候选人'}与目标岗位存在一定相关性，可作为备选，建议优先确认产品职责重合度。"

    if priority == "A":
        return f"{candidate_name or '该候选人'}与目标岗位匹配度较高，综合评分{score}分，建议优先联系。"

    if decision in {"strong_yes", "yes"}:
        return f"{candidate_name or '该候选人'}具备较明确的相关经验信号，综合评分{score}分，建议安排首轮沟通。"

    return f"{candidate_name or '该候选人'}具备一定匹配度，综合评分{score}分，可作为备选进一步核实。"


def _clean_core_judgement(candidate: Dict[str, Any], source_candidate: Optional[Dict[str, Any]] = None) -> str:
    text = _clean_text(candidate.get("core_judgement"))
    candidate_name = _extract_candidate_name(candidate, source_candidate)
    replacement_candidates = []

    if source_candidate:
        replacement_candidates.extend(_iter_name_candidates(source_candidate))
        replacement_candidates.append(_clean_text(source_candidate.get("candidate_id")))
        replacement_candidates.append(_clean_text(source_candidate.get("id")))

    replacement_candidates.extend(_iter_name_candidates(candidate))
    replacement_candidates.append(_clean_text(candidate.get("candidate_id")))
    replacement_candidates.append(_clean_text(candidate.get("id")))

    cleaned = text
    for value in replacement_candidates:
        current = _clean_text(value)
        if not current or current == candidate_name:
            continue
        if _looks_like_composite_name(current) or _is_hash_like(current):
            cleaned = cleaned.replace(current, candidate_name)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned or _looks_like_composite_name(cleaned.split("，", 1)[0]) or _is_generic_core_judgement(cleaned):
        temp_candidate = dict(candidate)
        if candidate_name:
            temp_candidate["candidate_name"] = candidate_name
            temp_candidate["name"] = candidate_name
        return _build_core_judgement(temp_candidate)
    return cleaned


def _normalize_action(candidate: Dict[str, Any], action: Any) -> Dict[str, Any]:
    if not isinstance(action, dict):
        action = {}

    decision = candidate.get("decision", "maybe")

    should_contact = action.get("should_contact")
    if not isinstance(should_contact, bool):
        should_contact = decision in {"strong_yes", "yes"}

    hook_message = _clean_text(action.get("hook_message"))
    if _is_generic_hook_message(hook_message):
        hook_message = _build_personalized_hook_message(candidate)

    verification_question = _clean_text(action.get("verification_question"))
    if _is_generic_verification_question(verification_question):
        verification_question = _build_personalized_verification_question(candidate)

    deep_questions = _clean_str_list(action.get("deep_questions"))
    if _is_generic_deep_questions(deep_questions):
        deep_questions = _build_personalized_deep_questions(candidate)

    message_template = _clean_text(action.get("message_template"))
    if _is_generic_message_template(message_template):
        message_template = _build_fallback_message_template(
            candidate,
            {
                "hook_message": hook_message,
                "verification_question": verification_question,
            },
        )

    return {
        "should_contact": should_contact,
        "hook_message": hook_message,
        "verification_question": verification_question,
        "message_template": message_template,
        "deep_questions": deep_questions[:3],
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


def _build_overall_diagnosis(candidates: List[Dict[str, Any]], input_data: Optional[Dict[str, Any]] = None) -> str:
    source_candidates = (input_data or {}).get("candidates", [])
    total_processed = len(source_candidates) if isinstance(source_candidates, list) and source_candidates else len(candidates)
    successful_ingested = total_processed
    recommended_count = len(candidates)
    contact_count = sum(1 for candidate in candidates if candidate.get("decision") in {"strong_yes", "yes"})
    maybe_count = sum(1 for candidate in candidates if candidate.get("decision") == "maybe")

    role_counts: Dict[str, int] = {}
    for candidate in candidates:
        role_label = _extract_role_label(candidate)
        if role_label:
            role_counts[role_label] = role_counts.get(role_label, 0) + 1

    role_mix = "、".join(role for role, _ in sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))[:3])
    role_part = f"候选人背景主要来自{role_mix}等相关方向。" if role_mix else ""

    return (
        f"本批共处理{total_processed}份简历，成功解析{successful_ingested}份，其中{recommended_count}份进入推荐池；"
        f"值得联系{contact_count}人，备选观察{maybe_count}人。{role_part}"
    ).strip()


def _build_batch_advice(candidates: List[Dict[str, Any]]) -> str:
    today_count = sum(1 for candidate in candidates if candidate.get("action_timing") == "today")
    this_week_count = sum(1 for candidate in candidates if candidate.get("action_timing") == "this_week")
    maybe_count = sum(1 for candidate in candidates if candidate.get("decision") == "maybe")

    advice_parts: List[str] = []
    if today_count:
        advice_parts.append(f"建议优先推进 today 档的{today_count}位候选人")
    if this_week_count:
        advice_parts.append(f"本周完成 this_week 档的{this_week_count}位候选人初筛")
    if maybe_count:
        advice_parts.append(f"对{maybe_count}位备选候选人重点验证真实职责边界与产品 ownership")

    if advice_parts:
        return "；".join(advice_parts) + "。"

    return "建议先完成推荐池候选人的首轮沟通，再根据验证结果决定是否继续推进。"


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
    except Exception as exc:
        raise ValueError(f"❌ Invalid JSON output: {exc}")

    if not isinstance(data, dict):
        raise ValueError("❌ Output must be a JSON object")

    if "overall_diagnosis" not in data:
        raise ValueError("❌ Missing overall_diagnosis")

    if "top_recommendations" not in data:
        raise ValueError("❌ Missing top_recommendations")

    if not isinstance(data["top_recommendations"], list):
        raise ValueError("❌ top_recommendations must be list")

    for index, candidate in enumerate(data["top_recommendations"]):
        if not isinstance(candidate, dict):
            raise ValueError(f"❌ recommendation[{index}] must be object")

        required_fields = [
            "candidate_id",
            "rank",
            "total_score",
            "decision",
            "priority",
            "action_timing",
            "core_judgement",
        ]
        for field in required_fields:
            if field not in candidate:
                raise ValueError(f"❌ recommendation[{index}] missing {field}")

        if "action" in candidate and not isinstance(candidate["action"], dict):
            raise ValueError(f"❌ recommendation[{index}].action must be object")

    return data


# ==============================
# 2. 数据清洗与业务兜底
# ==============================
def _looks_like_person_name(value: str) -> bool:
    if not value:
        return False
    if len(value) < 2:
        return False
    if not re.match(r"^[\u4e00-\u9fff·]+$", value):
        return False
    if value[0] in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
        return False
    return True


def _build_alias_set(candidate: Dict[str, Any], source_candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build alias set from candidate and source candidate.
    Returns a dict with:
      canonical: the resolved canonical name
      aliases: list of alias strings (may include old filenames, partial names, etc.)
      sources: list of where each alias came from
    """
    canonical = _extract_candidate_name(candidate, source_candidate)
    aliases: List[str] = []
    alias_sources: List[str] = []

    def _add_alias(alias: str, source: str):
        """Add alias, extracting name from filenames/ids if needed."""
        if not alias or alias == canonical:
            return
        aliases.append(alias)
        alias_sources.append(f"{source}:{alias}")
        # Extract Chinese name from compound identifiers
        # e.g. "产品经理_宁波8-13K_吴小姐_9年.pdf" -> "吴小姐"
        extracted = _find_name_in_identifier(alias)
        if extracted and extracted != canonical and extracted not in aliases:
            aliases.append(extracted)
            alias_sources.append(f"extracted_from_{source}:{extracted}")
        # Also add English tokens as potential aliases (e.g. "Rango" from same filename)
        # Split by non-alphanumeric and check each token
        raw_tokens = re.split(r"[^a-zA-Z0-9]", alias)
        for token in raw_tokens:
            if token and token not in aliases and token != canonical:
                if 2 <= len(token) <= 20 and token[0].isalpha() and token[0].isupper():
                    # Looks like an English name (capitalized, 2-20 chars)
                    aliases.append(token)
                    alias_sources.append(f"token_from_{source}:{token}")

    # Collect from candidate and source
    for current in (source_candidate, candidate):
        if not isinstance(current, dict):
            continue
        # name fields
        for key in ("name", "candidate_name", "real_name", "resume_name"):
            v = _clean_text(current.get(key))
            if v and v != canonical:
                _add_alias(v, key)
        # candidate_id / id
        for key in ("candidate_id", "id"):
            v = _clean_text(current.get(key))
            if v:
                _add_alias(v, key)
        # source.file_name
        source = current.get("source", {})
        v = _clean_text(source.get("file_name"))
        if v:
            _add_alias(v, "file_name")

    # Deduplicate
    seen = set()
    unique_aliases: List[str] = []
    for a in aliases:
        if a not in seen:
            seen.add(a)
            unique_aliases.append(a)

    return {
        "canonical": canonical,
        "aliases": unique_aliases,
        "sources": alias_sources,
    }


def _find_alias_hits(text: str, canonical: str, aliases: List[str]) -> List[str]:
    """
    Find which aliases appear in text as standalone person-like tokens.
    Handles:
      - Standalone alias: "吴小姐"
      - Parenthetical alias: "吴小姐（孙铜）" or "吴小姐 - 孙铜"
      - Hybrid: "唐晓斌（Rango）"
    Returns list of found alias hits.
    """
    if not text:
        return []
    hits: List[str] = []

    for alias in aliases:
        if not alias or alias == canonical:
            continue
        if _is_hash_like(alias):
            continue

        # Pattern 1: "alias（canonical）" or "alias - canonical" (alias followed by separator+text)
        combo_pattern = re.escape(alias) + r"[（()\-–— ]+" + r"[^\n（）()\-–—]{1,20}"
        for m in re.finditer(combo_pattern, text):
            hits.append(alias)
            break

        # Pattern 1b: "(alias)" or "alias（...）" (alias inside or preceded by bracket)
        # e.g. "唐晓斌（Rango）" or "Rango）" preceded by "（"
        bracket_before = r"[（()\[【】】]\s*" + re.escape(alias) + r"(?:\s*[）()\]【】】])?"
        for m in re.finditer(bracket_before, text):
            hits.append(alias)
            break
        # Also: alias followed immediately by full-width right paren
        bracket_after = re.escape(alias) + r"\s*[）()\]【】】]"
        for m in re.finditer(bracket_after, text):
            hits.append(alias)
            break

        # Pattern 2: standalone alias as distinct token (no adjacent Chinese chars)
        pattern = re.escape(alias)
        for m in re.finditer(pattern, text):
            start = m.start()
            end = m.end()
            before = text[start - 1] if start > 0 else " "
            after = text[end] if end < len(text) else " "
            # Accept if not surrounded by Chinese characters
            if not re.match(r"[\u4e00-\u9fff]", before) and not re.match(r"[\u4e00-\u9fff]", after):
                hits.append(alias)
                break

    return hits


def sanitize_output(data: Dict[str, Any], input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    修正模型可能的输出问题，让系统稳定运行。
    核心原则：
    1. 不用空字符串伪造“合格数组”
    2. message_template 必须永远可发
    3. rank 最终必须连续
    """
    data["overall_diagnosis"] = _clean_text(data.get("overall_diagnosis"))
    data.setdefault("batch_advice", "")
    data["batch_advice"] = _clean_text(data.get("batch_advice"))

    candidate_lookup = _build_candidate_lookup(input_data or {})
    recommendations = data.get("top_recommendations", [])
    sanitized: List[Dict[str, Any]] = []

    for index, candidate in enumerate(recommendations, 1):
        if not isinstance(candidate, dict):
            candidate = {}

        candidate_id = _clean_text(candidate.get("candidate_id")) or f"unknown_{index}"
        source_candidate = candidate_lookup.get(candidate_id, {})

        total_score = _clamp_score(candidate.get("total_score"), default=0)

        decision = candidate.get("decision")
        if decision not in VALID_DECISIONS:
            decision = "maybe"

        priority = candidate.get("priority")
        if priority not in VALID_PRIORITIES:
            priority = "C"

        action_timing = candidate.get("action_timing")
        if action_timing not in VALID_TIMINGS:
            action_timing = "optional"

        candidate_name = _extract_candidate_name(candidate, source_candidate)
        role_label = _extract_role_label(candidate, source_candidate)
        core_judgement = _clean_core_judgement(
            {
                **candidate,
                "candidate_name": candidate_name,
                "name": candidate_name,
                "role_label": role_label,
                "total_score": total_score,
                "decision": decision,
                "priority": priority,
            },
            source_candidate,
        )

        # P1 identity conflict check: core_judgement
        alias_info = _build_alias_set(candidate, source_candidate)
        cj_hits = _find_alias_hits(core_judgement, candidate_name, alias_info["aliases"])
        identity_meta: Dict[str, Any] = {
            "canonical_name": candidate_name,
            "has_conflict": bool(cj_hits),
            "conflict_fields": [],
            "alias_hits": cj_hits,
            "resolution": "unchanged",
        }
        if cj_hits:
            # Rebuild core_judgement from scratch
            core_judgement = _build_core_judgement({
                **candidate,
                "candidate_name": candidate_name,
                "name": candidate_name,
                "role_label": role_label,
                "total_score": total_score,
                "decision": decision,
                "priority": priority,
            })
            identity_meta["conflict_fields"].append("core_judgement")
            identity_meta["resolution"] = "rebuilt_core_judgement"

        reasons = _clean_str_list(candidate.get("reasons"))
        if len(reasons) < 3:
            reasons = (reasons + _fallback_reasons({
                **candidate,
                "candidate_name": candidate_name,
                "name": candidate_name,
                "role_label": role_label,
                "decision": decision,
                "priority": priority,
            }))[:3]

        risks = _clean_risk_list(candidate.get("risks"))
        if len(risks) < 1:
            risks = _fallback_risks({
                **candidate,
                "candidate_name": candidate_name,
                "name": candidate_name,
                "role_label": role_label,
            })

        score_breakdown = _normalize_score_breakdown(candidate.get("score_breakdown"), total_score)

        normalized_candidate = {
            "candidate_id": candidate_id,
            "rank": candidate.get("rank"),
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
            "score_breakdown": score_breakdown,
        }
        normalized_candidate["action"] = _normalize_action(normalized_candidate, candidate.get("action"))

        # P1 identity conflict check: action fields
        action = normalized_candidate["action"]
        hook = action.get("hook_message", "")
        tmpl = action.get("message_template", "")

        h_hits = _find_alias_hits(hook, candidate_name, alias_info["aliases"])
        t_hits = _find_alias_hits(tmpl, candidate_name, alias_info["aliases"])

        if h_hits:
            identity_meta["conflict_fields"].append("action.hook_message")
            identity_meta["alias_hits"] = list(set(identity_meta["alias_hits"] + h_hits))
            action["hook_message"] = _build_personalized_hook_message(normalized_candidate)
            if not identity_meta["resolution"] or identity_meta["resolution"] == "unchanged":
                identity_meta["resolution"] = "rebuilt_hook_message"

        if t_hits:
            identity_meta["conflict_fields"].append("action.message_template")
            identity_meta["alias_hits"] = list(set(identity_meta["alias_hits"] + t_hits))
            action["message_template"] = _build_fallback_message_template(
                normalized_candidate,
                {"hook_message": action.get("hook_message", ""), "verification_question": action.get("verification_question", "")},
            )
            if not identity_meta["resolution"] or identity_meta["resolution"] == "unchanged":
                identity_meta["resolution"] = "rebuilt_message_template"

        if identity_meta["has_conflict"] and not identity_meta["resolution"]:
            identity_meta["resolution"] = "resolved"

        normalized_candidate["identity_meta"] = identity_meta
        sanitized.append(normalized_candidate)

    data["top_recommendations"] = _sort_recommendations(sanitized)
    data["overall_diagnosis"] = _build_overall_diagnosis(data["top_recommendations"], input_data=input_data)
    data["batch_advice"] = _build_batch_advice(data["top_recommendations"])
    return data


# ==============================
# 3. 日志记录
# ==============================
def log_decision(input_data: Dict[str, Any], output_data: Dict[str, Any]):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "input": input_data,
        "output": output_data,
        "feedback": None,
    }

    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


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
            "quality_flag": "invalid",
        }

    scores = [candidate.get("total_score", 0) for candidate in candidates if _is_number(candidate.get("total_score", 0))]
    if not scores:
        return {
            "quality_score": 0,
            "issue": "no_valid_scores",
            "quality_flag": "invalid",
        }

    avg_score = sum(scores) / len(scores)
    variance = max(scores) - min(scores)

    has_a = any(candidate.get("priority") == "A" for candidate in candidates)
    contact_ratio = sum(1 for candidate in candidates if candidate.get("action", {}).get("should_contact")) / len(candidates)

    fallback_message_count = 0
    for candidate in candidates:
        message = _clean_text(candidate.get("action", {}).get("message_template"))
        if (
            "与你背景方向比较接近的岗位" in message
            or "成长速度都比较看重的岗位" in message
            or "更偏产品落地与流程设计的岗位" in message
        ):
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
        "issue": issue,
    }


# ==============================
# 5. Markdown 渲染（给飞书/人看）
# ==============================
def render_human_readable(data: Dict[str, Any]) -> str:
    lines: List[str] = []

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
        "C": "👌 备选",
    }
    decision_map = {
        "strong_yes": "💚 强烈推荐",
        "yes": "✅ 建议联系",
        "maybe": "⏸️ 观察",
        "no": "❌ 不推荐",
    }
    timing_map = {
        "today": "⚡ 今天",
        "this_week": "📅 本周",
        "optional": "🔖 可选",
    }

    for candidate in recommendations:
        candidate_name = _extract_candidate_name(candidate) or candidate.get("candidate_id", "")
        role_label = _extract_role_label(candidate)
        heading = candidate_name if not role_label else f"{candidate_name}｜{role_label}"

        lines.append(
            f"\n### Rank #{candidate.get('rank', '-')} | "
            f"{priority_map.get(candidate.get('priority'), '')} - {heading}"
        )
        lines.append(
            f"**得分**: {candidate.get('total_score', 0)} | "
            f"**决策**: {decision_map.get(candidate.get('decision'))} | "
            f"**时机**: {timing_map.get(candidate.get('action_timing'))}\n"
        )

        if candidate.get("core_judgement"):
            lines.append(f"**🎯 核心判断**: {candidate['core_judgement']}\n")

        score_breakdown = candidate.get("score_breakdown", {})
        if score_breakdown:
            lines.append(
                f"**📊 评分拆解**: "
                f"硬技能 {score_breakdown.get('hard_skill', 0)} / "
                f"经验 {score_breakdown.get('experience', 0)} / "
                f"稳定性 {score_breakdown.get('stability', 0)} / "
                f"潜力 {score_breakdown.get('potential', 0)} / "
                f"转化率 {score_breakdown.get('conversion', 0)}\n"
            )

        if candidate.get("reasons"):
            lines.append("**✨ 优势**:")
            for reason in candidate["reasons"][:3]:
                lines.append(f"- {reason}")
            lines.append("")

        if candidate.get("risks"):
            lines.append("**⚠️ 风险**:")
            for risk in candidate["risks"][:3]:
                lines.append(f"- {risk}")
            lines.append("")

        action = candidate.get("action", {})

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
            for question in action["deep_questions"][:3]:
                lines.append(f"- {question}")
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
        "meta": quality,
    }
