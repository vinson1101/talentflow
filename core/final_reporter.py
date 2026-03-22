"""
最终报告生成模块

功能：
- 生成最终 MD 报告
- 生成 owner 摘要
- 导出汇总结果
"""

import ast
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    "local", "resume", "candidate", "today", "this", "week", "optional",
    "简历", "候选人", "推荐", "联系", "今天", "本周", "可选", "未知",
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


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


def _find_name_in_identifier(identifier: Any) -> str:
    for token in reversed(_split_identifier_tokens(_clean_text(identifier))):
        if _looks_like_person_name(token):
            return token

    chinese_segments = re.findall(r"[\u4e00-\u9fff]{2,6}", _clean_text(identifier))
    for segment in reversed(chinese_segments):
        if _looks_like_person_name(segment):
            return segment
    return ""


class FinalReporter:
    """最终报告生成器"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_final_report(
        self,
        candidates: List[Dict[str, Any]],
        meta: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> Path:
        report_content = self._build_report_content(candidates, meta)
        report_name = filename or f"final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = self.output_dir / report_name

        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(report_content)

        return report_path

    def save_owner_summary(
        self,
        candidates: List[Dict[str, Any]],
        filename: str = "owner_summary.md",
    ) -> Path:
        summary = self.generate_owner_summary(candidates)
        summary_path = self.output_dir / filename
        with open(summary_path, "w", encoding="utf-8") as handle:
            handle.write(summary)
        return summary_path

    def _build_report_content(
        self,
        candidates: List[Dict[str, Any]],
        meta: Dict[str, Any],
    ) -> str:
        stats = self._load_summary_stats(candidates)
        contact_candidates = [candidate for candidate in candidates if candidate.get("decision") in {"strong_yes", "yes"}]
        maybe_candidates = [candidate for candidate in candidates if candidate.get("decision") == "maybe"]

        lines = ["# 招聘决策报告", ""]
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        lines.extend(self._format_jd_section(meta.get("jd")))
        if meta.get("company"):
            lines.extend(self._format_company_section(meta.get("company")))

        lines.append("## 整体诊断")
        lines.append("")
        lines.append(self._build_overall_diagnosis(meta, candidates, stats))
        lines.append("")

        lines.append("## 批量建议")
        lines.append("")
        lines.append(self._build_batch_advice(meta, candidates))
        lines.append("")

        lines.append("## 候选人汇总")
        lines.append("")
        lines.append(f"- 总处理人数：{stats['total_processed']}")
        lines.append(f"- 成功解析人数：{stats['successful_ingested']}")
        lines.append(f"- 进入推荐池人数：{stats['recommended_count']}")
        lines.append(f"- 值得联系（yes / strong_yes）：{len(contact_candidates)}人")
        lines.append(f"- 备选观察（maybe）：{len(maybe_candidates)}人")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append("## 详细评估")
        lines.append("")
        for index, candidate in enumerate(candidates, 1):
            lines.extend(self._build_candidate_section(candidate, index))
            lines.append("---")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def _build_candidate_section(self, candidate: Dict[str, Any], idx: int) -> List[str]:
        lines: List[str] = []
        display_name = self._display_name(candidate)
        role_label = self._role_label(candidate)
        heading = display_name if not role_label else f"{display_name}｜{role_label}"

        lines.append(f"### {idx}. {heading}")
        lines.append("")
        lines.append(f"- **决策**: {self._decision_label(candidate.get('decision'))}")
        lines.append(f"- **总分**: {int(float(candidate.get('total_score', 0) or 0))}/100")
        lines.append(f"- **优先级**: {candidate.get('priority', '-')}")
        lines.append(f"- **联系时机**: {self._timing_label(candidate.get('action_timing'))}")

        lines.append("")
        lines.append("**核心判断**:")
        lines.append(f"- {self._summary_judgement(candidate)}")

        reasons = candidate.get("reasons") or []
        if reasons:
            lines.append("")
            lines.append("**评估理由**:")
            for reason in reasons[:3]:
                text = _clean_text(reason)
                if text:
                    lines.append(f"- {text}")

        risks = candidate.get("risks") or []
        if risks:
            lines.append("")
            lines.append("**风险分析**:")
            for risk in risks[:3]:
                text = self._normalize_risk(risk)
                if text:
                    lines.append(f"- {text}")

        action = candidate.get("action", {})
        hook_message = _clean_text(action.get("hook_message"))
        verification_question = _clean_text(action.get("verification_question"))
        message_template = _clean_text(action.get("message_template"))
        deep_questions = action.get("deep_questions") or []

        if hook_message:
            lines.append("")
            lines.append("**钩子话术**:")
            lines.append(f"- {hook_message}")

        if verification_question:
            lines.append("")
            lines.append("**验证问题**:")
            lines.append(f"- {verification_question}")

        if message_template:
            lines.append("")
            lines.append("**完整联系话术**:")
            lines.append("```")
            lines.append(message_template)
            lines.append("```")

        if deep_questions:
            lines.append("")
            lines.append("**深问问题**:")
            for question in deep_questions[:3]:
                text = _clean_text(question)
                if text:
                    lines.append(f"- {text}")

        lines.append("")
        return lines

    def generate_owner_summary(
        self,
        candidates: List[Dict[str, Any]],
    ) -> str:
        stats = self._load_summary_stats(candidates)
        today_candidates = [candidate for candidate in candidates if candidate.get("action_timing") == "today"]
        this_week_candidates = [candidate for candidate in candidates if candidate.get("action_timing") == "this_week"]
        optional_candidates = [candidate for candidate in candidates if candidate.get("action_timing") == "optional"]
        contact_candidates = [candidate for candidate in candidates if candidate.get("decision") in {"strong_yes", "yes"}]
        maybe_candidates = [candidate for candidate in candidates if candidate.get("decision") == "maybe"]

        lines = ["# 招聘决策摘要", ""]
        lines.append("## 基本情况")
        lines.append(f"- 总处理人数：{stats['total_processed']}")
        lines.append(f"- 成功解析人数：{stats['successful_ingested']}")
        lines.append(f"- 进入推荐池人数：{stats['recommended_count']}")
        lines.append(f"- 值得联系人数：{len(contact_candidates)}")
        lines.append(f"- 备选人数：{len(maybe_candidates)}")
        lines.append("")

        lines.append("## 建议立即行动")
        lines.append(f"- 今日优先联系：{len(today_candidates)} 人")
        lines.append(f"- 本周建议联系：{len(this_week_candidates)} 人")
        lines.append(f"- 备选观察：{len(optional_candidates)} 人")
        lines.append("")

        lines.append("## Top 5 候选人")
        for idx, candidate in enumerate(candidates[:5], 1):
            lines.append(
                f"{idx}. **{self._display_name(candidate)}**｜{self._role_label(candidate)}｜"
                f"{int(float(candidate.get('total_score', 0) or 0))}分｜"
                f"{candidate.get('priority', '-')}优先级｜{self._timing_label(candidate.get('action_timing'))}  "
            )
            lines.append(f"   核心判断：{self._summary_judgement(candidate)}")
            lines.append("")

        lines.append(f"## 值得联系（共 {len(contact_candidates)} 人）")
        for candidate in contact_candidates[:5]:
            lines.append(
                f"- {self._display_name(candidate)}｜{self._role_label(candidate)}｜"
                f"{int(float(candidate.get('total_score', 0) or 0))}分｜{candidate.get('priority', '-')}｜"
                f"{self._timing_code(candidate.get('action_timing'))}"
            )
        if len(contact_candidates) > 5:
            lines.append("- ……")
        lines.append("")

        lines.append(f"## 备选观察（共 {len(maybe_candidates)} 人）")
        for candidate in maybe_candidates[:5]:
            lines.append(
                f"- {self._display_name(candidate)}｜{self._role_label(candidate)}｜"
                f"{int(float(candidate.get('total_score', 0) or 0))}分｜{candidate.get('priority', '-')}｜"
                f"{self._timing_code(candidate.get('action_timing'))}"
            )
        if len(maybe_candidates) > 5:
            lines.append("- ……")
        lines.append("")

        lines.append("## 主要共性风险")
        for risk in self._collect_common_risks(candidates):
            lines.append(f"- {risk}")
        lines.append("")

        lines.append("## 建议的下一步")
        if today_candidates:
            lines.append("1. 先推进 A 优先级且适合 today 的候选人，尽快完成第一轮触达。")
        else:
            lines.append("1. 先确认当前推荐池中最值得优先推进的人选。")
        if this_week_candidates:
            lines.append("2. 本周完成 B 类候选人的首轮沟通，重点比较产品职责深度与业务匹配度。")
        else:
            lines.append("2. 本周补充完成备选候选人的初筛判断。")
        lines.append("3. 首轮沟通重点验证：需求拆解能力、真实 ownership、跨团队协作和业务落地深度。")

        return "\n".join(lines).rstrip() + "\n"

    def _load_summary_stats(self, candidates: List[Dict[str, Any]]) -> Dict[str, int]:
        batch_input_path = self.output_dir / "batch_input.json"
        total_processed = len(candidates)
        successful_ingested = len(candidates)

        if batch_input_path.exists():
            try:
                batch_input = json.loads(batch_input_path.read_text(encoding="utf-8"))
                source_candidates = batch_input.get("candidates", [])
                if isinstance(source_candidates, list):
                    total_processed = len(source_candidates)
                    successful_ingested = len(source_candidates)
            except Exception:
                pass

        return {
            "total_processed": total_processed,
            "successful_ingested": successful_ingested,
            "recommended_count": len(candidates),
        }

    def _display_name(self, candidate: Dict[str, Any]) -> str:
        for key in ("name", "candidate_name", "resume_name", "parsed_name", "full_name"):
            value = _clean_text(candidate.get(key))
            if value and not _looks_like_composite_name(value):
                if _looks_like_person_name(value):
                    return value
                extracted = _find_name_in_identifier(value)
                if extracted:
                    return extracted

        for key in ("name", "candidate_name", "resume_name", "parsed_name", "full_name", "candidate_id"):
            value = _clean_text(candidate.get(key))
            extracted = _find_name_in_identifier(value)
            if extracted:
                return extracted

        fallback = _clean_text(candidate.get("candidate_id"))
        return fallback or "未知候选人"

    def _role_label(self, candidate: Dict[str, Any]) -> str:
        for key in ("role_label", "title", "job_title"):
            value = _clean_text(candidate.get(key))
            if value:
                return value

        candidate_id = _clean_text(candidate.get("candidate_id"))
        for token in _split_identifier_tokens(candidate_id):
            if _looks_like_role(token):
                return token

        core_judgement = _clean_text(candidate.get("core_judgement"))
        match = re.search(r"(高级产品经理|产品经理|项目经理|产品专员|产品运营|运营经理|销售经理|研发工程师|工程师)", core_judgement)
        if match:
            return match.group(1)

        return "待确认岗位"

    def _decision_label(self, decision: Any) -> str:
        mapping = {
            "strong_yes": "strong_yes（强烈推荐）",
            "yes": "yes（值得联系）",
            "maybe": "maybe（备选观察）",
            "no": "no（暂不推荐）",
        }
        return mapping.get(_clean_text(decision), _clean_text(decision) or "未评估")

    def _timing_label(self, timing: Any) -> str:
        timing_map = {
            "today": "今天联系",
            "this_week": "本周联系",
            "optional": "可选 / 观察",
        }
        return timing_map.get(_clean_text(timing), "待安排")

    def _timing_code(self, timing: Any) -> str:
        mapping = {
            "today": "today",
            "this_week": "this_week",
            "optional": "optional",
        }
        return mapping.get(_clean_text(timing), "pending")

    def _summary_judgement(self, candidate: Dict[str, Any]) -> str:
        display_name = self._display_name(candidate)
        role_label = self._role_label(candidate)
        priority = _clean_text(candidate.get("priority"))
        decision = _clean_text(candidate.get("decision"))
        score = int(float(candidate.get("total_score", 0) or 0))

        if "项目经理" in role_label:
            if decision in {"strong_yes", "yes"}:
                return f"{display_name}具备项目推进与跨团队协同经验，建议进入首轮沟通，重点核实产品设计与需求定义的直接职责深度。"
            return f"{display_name}与目标岗位存在一定相关性，可作为备选，建议优先确认产品职责重合度。"

        if priority == "A":
            return f"{display_name}与目标岗位匹配度较高，综合评分{score}分，建议优先联系。"

        if decision in {"strong_yes", "yes"}:
            return f"{display_name}具备较明确的相关经验信号，综合评分{score}分，建议安排首轮沟通。"

        return f"{display_name}具备一定匹配度，综合评分{score}分，可作为备选进一步核实。"

    def _collect_common_risks(self, candidates: List[Dict[str, Any]]) -> List[str]:
        risks: List[str] = []
        seen = set()
        for candidate in candidates:
            for risk in candidate.get("risks", [])[:3]:
                normalized = self._normalize_risk(risk)
                if normalized and normalized not in seen:
                    risks.append(normalized)
                    seen.add(normalized)
                if len(risks) >= 3:
                    return risks

        if not risks:
            return ["多数简历偏结果摘要，真实职责边界需要在首轮沟通中进一步验证"]
        return risks

    def _normalize_risk(self, risk: Any) -> str:
        parsed = _try_parse_dict_like(risk)
        if parsed is not None:
            return _clean_text(parsed.get("description") or parsed.get("risk") or parsed.get("text"))
        if isinstance(risk, dict):
            return _clean_text(risk.get("description") or risk.get("risk") or risk.get("text"))
        return _clean_text(risk)

    def _build_overall_diagnosis(
        self,
        meta: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        stats: Dict[str, int],
    ) -> str:
        contact_candidates = [candidate for candidate in candidates if candidate.get("decision") in {"strong_yes", "yes"}]
        maybe_candidates = [candidate for candidate in candidates if candidate.get("decision") == "maybe"]

        role_counts: Dict[str, int] = {}
        for candidate in candidates:
            role = self._role_label(candidate)
            role_counts[role] = role_counts.get(role, 0) + 1

        role_mix = "、".join(role for role, _ in sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))[:3])
        role_part = f"候选人背景主要来自{role_mix}等相关方向。" if role_mix else ""

        return (
            f"本批共处理{stats['total_processed']}份简历，成功解析{stats['successful_ingested']}份，"
            f"其中{stats['recommended_count']}份进入推荐池；值得联系{len(contact_candidates)}人，"
            f"备选观察{len(maybe_candidates)}人。{role_part}".strip()
        )

    def _build_batch_advice(self, meta: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
        today_candidates = [candidate for candidate in candidates if candidate.get("action_timing") == "today"]
        this_week_candidates = [candidate for candidate in candidates if candidate.get("action_timing") == "this_week"]
        maybe_candidates = [candidate for candidate in candidates if candidate.get("decision") == "maybe"]

        advice_parts = []
        if today_candidates:
            advice_parts.append(f"建议优先推进 today 档的{len(today_candidates)}位候选人")
        if this_week_candidates:
            advice_parts.append(f"本周完成 this_week 档的{len(this_week_candidates)}位候选人初筛")
        if maybe_candidates:
            advice_parts.append(f"对{len(maybe_candidates)}位备选候选人重点验证真实职责边界与产品 ownership")

        if advice_parts:
            return "；".join(advice_parts) + "。"

        original = _clean_text(meta.get("batch_advice"))
        if original:
            return original
        return "建议先完成推荐池候选人的首轮沟通，再根据验证结果决定是否继续推进。"

    def _format_jd_section(self, jd: Any) -> List[str]:
        parsed = self._normalize_object(jd)
        lines = ["## 职位描述", ""]

        if not isinstance(parsed, dict):
            text = _clean_text(jd)
            if text:
                lines.append(text)
                lines.append("")
            return lines

        title = _clean_text(parsed.get("title"))
        location = _clean_text(parsed.get("location"))
        salary_range = _clean_text(parsed.get("salary_range"))
        company_context = _clean_text(parsed.get("company_context"))

        if title:
            lines.append(f"- 职位：{title}")
        if location:
            lines.append(f"- 工作地点：{location}")
        if salary_range:
            lines.append(f"- 薪资范围：{salary_range}")
        if company_context:
            lines.append(f"- 公司背景：{company_context}")

        must_have = parsed.get("must_have") if isinstance(parsed.get("must_have"), list) else []
        nice_to_have = parsed.get("nice_to_have") if isinstance(parsed.get("nice_to_have"), list) else []

        if must_have:
            lines.append("")
            lines.append("### 必备条件")
            for item in must_have:
                text = _clean_text(item)
                if text:
                    lines.append(f"- {text}")

        if nice_to_have:
            lines.append("")
            lines.append("### 加分项")
            for item in nice_to_have:
                text = _clean_text(item)
                if text:
                    lines.append(f"- {text}")

        lines.append("")
        return lines

    def _format_company_section(self, company: Any) -> List[str]:
        parsed = self._normalize_object(company)
        lines = ["## 企业信息", ""]

        if isinstance(parsed, dict):
            for key, value in parsed.items():
                text = _clean_text(value)
                if text:
                    lines.append(f"- {key}：{text}")
        else:
            text = _clean_text(company)
            if text:
                lines.append(text)

        lines.append("")
        return lines

    def _normalize_object(self, value: Any) -> Any:
        if isinstance(value, dict):
            return value

        text = _clean_text(value)
        if not text:
            return {}

        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue

        return value
