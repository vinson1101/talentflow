# Feishu 多维表格访问地址（固定值，勿改）
FEISHU_TABLE_URL = "https://ucn43sn4odey.feishu.cn/base/AINFbZLOQaSo6rslOeZc95RTnPb"

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
        jd_title: str = "待确认",
        jd_location: str = "待确认",
        jd_salary: str = "待确认",
        filename: str = "owner_summary.md",
    ) -> Path:
        summary = self.generate_owner_summary(
            candidates,
            jd_title=jd_title,
            jd_location=jd_location,
            jd_salary=jd_salary,
        )
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

        # P5: 展示 7 维 structured_score
        ss = candidate.get("structured_score", {})
        if ss and isinstance(ss, dict) and ss.get("dimension_scores"):
            ws = ss.get("weight_snapshot", {})
            lines.append("")
            lines.append("**7维评分**:")
            dim_labels = {
                "hard_skill_match": "硬技能匹配",
                "experience_depth": "经验深度",
                "innovation_potential": "创新潜能",
                "execution_goal_breakdown": "目标拆解执行",
                "team_fit": "团队融合",
                "willingness": "意愿度",
                "stability": "稳定性",
            }
            for dim, label in dim_labels.items():
                score = ss["dimension_scores"].get(dim, 0)
                weight = ws.get(dim, 0)
                evidence = ss.get("dimension_evidence", {}).get(dim, "")
                ev_text = f"（{evidence[:20]}…）" if evidence and len(evidence) > 20 else (f"（{evidence}）" if evidence else "")
                lines.append(f"- {label} {int(score)}分(权重{weight}%) {ev_text}")

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
        jd_title: str = "待确认",
        jd_location: str = "待确认",
        jd_salary: str = "待确认",
    ) -> str:
        """
        按 references/summary-card-template.md V1 生成人类可读摘要。

        Args:
            candidates: 候选人列表（从 final_output.json top_recommendations 获取）
            jd_title: 岗位名称
            jd_location: 工作城市
            jd_salary: 薪资范围
        """
        stats = self._load_summary_stats(candidates)

        # 分档
        a_candidates = [c for c in candidates if c.get("priority") == "A" and c.get("decision") in {"strong_yes", "yes"}]
        b_candidates = [c for c in candidates if c.get("priority") == "B" and c.get("decision") in {"strong_yes", "yes"}]
        c_candidates = [c for c in candidates if c.get("decision") == "maybe"]
        no_candidates = [c for c in candidates if c.get("decision") == "no"]
        today_candidates = [c for c in candidates if c.get("action_timing") == "today"]
        this_week_candidates = [c for c in candidates if c.get("action_timing") == "this_week"]

        def _fmt(c: Dict[str, Any]) -> str:
            score = round(float(c.get("total_score") or 0), 1)
            return f"{self._display_name(c)}（{score}分）"

        def _fmt_list(cands: List[Dict[str, Any]]) -> str:
            return "、".join(_fmt(c) for c in cands) if cands else "无"

        def _risk_short(c: Dict[str, Any]) -> str:
            risks = c.get("risks", [])
            if not risks:
                return "无明显风险"
            r = self._normalize_risk(risks[0])
            return r[:50] + ("…" if len(r) > 50 else "")

        # ---- Block 1: 标题 ----
        lines = [
            f"【招聘决策报告】{jd_title} · {jd_location} · {jd_salary}",
            "",
        ]

        # ---- Block 2: 批次概览 ----
        # Task 8: 批次口径统一，共收到/排除/实际评估
        # contact_count/maybe_count/no_count computed in Block 3
        total_received = stats.get("total_received", stats["total_processed"])
        total_excluded = stats.get("total_excluded", 0)
        if total_excluded > 0:
            lines.append(f"本批共收到 {total_received} 份简历，其中 {total_excluded} 份因岗位不匹配已排除，实际评估 {stats['total_processed']} 份。")
        else:
            lines.append(f"本批共收到 {stats['total_processed']} 份简历，决策结果：")
        lines.append("")

        # ---- Block 3: 分档表 ----
        lines.append("| 档位 | 人数 | 候选人 |")
        lines.append("|---|---:|---|")
        lines.append(f"| 🟢 A / strong_yes（强烈推荐，今天联系） | {len(a_candidates)}人 | {_fmt_list(a_candidates)} |")
        lines.append(f"| 🔵 B / yes（值得联系，本周联系） | {len(b_candidates)}人 | {_fmt_list(b_candidates)} |")
        lines.append(f"| 🟡 C / maybe（备选观察，暂不推进） | {len(c_candidates)}人 | {_fmt_list(c_candidates)} |")
        lines.append(f"| ⚫ no（不推进） | {len(no_candidates)}人 | {_fmt_list(no_candidates)} |")
        lines.append("")

        # ---- Block 4: 今日优先联系 / 本周建议联系 ----
        lines.append("**今日优先联系：**")
        if today_candidates:
            for c in today_candidates:
                score = round(float(c.get("total_score") or 0), 1)
                lines.append(f"- **{self._display_name(c)}**（{score}分 / {c.get('priority','')}）：{self._summary_judgement(c)}。风险：{_risk_short(c)}")
        else:
            lines.append("- 无")
        lines.append("")

        lines.append("**本周建议联系：**")
        if this_week_candidates:
            names = "、".join(self._display_name(c) for c in this_week_candidates)
            risk_set = []
            for c in this_week_candidates:
                risks = c.get("risks", [])
                if risks:
                    risk_set.append(self._normalize_risk(risks[0]))
            deduped = []
            seen = set()
            for r in risk_set:
                if r and r not in seen:
                    deduped.append(r)
                    seen.add(r)
            verify_point = "；".join(deduped[:2]) if deduped else "稳定性与产品 ownership"
            lines.append(f"{names}（重点核实：{verify_point}）")
        else:
            lines.append("- 无")
        lines.append("")

        # ---- Block 5: 主要风险提示（批次级）----
        # Task 10: 批次级风险，涵盖技能不足型和角色错位型两类
        lines.append("**主要风险提示：**")
        batch_risks = self._collect_batch_level_risks(candidates)
        for risk in batch_risks:
            lines.append(f"- {risk}")
        lines.append("")

        # ---- Block 6: 结论 ----
        # Task 11+12: contact_count/maybe_count 在此处计算
        contact_count = sum(1 for c in candidates if c.get("decision") in {"strong_yes", "yes"})
        maybe_count = len([c for c in candidates if c.get("decision") == "maybe"])
        lines.append("**结论：**")
        if contact_count == 0 and maybe_count > 0:
            lines.append(f"- 本批无可直接推进的前端工程师候选人，建议继续搜寻")
            # Task 12: C档内部优先级
            if len(c_candidates) >= 2:
                # 按分数排序，高分在前
                sorted_c = sorted(c_candidates, key=lambda c: float(c.get("total_score", 0) or 0), reverse=True)
                top_c = self._display_name(sorted_c[0])
                second_c = self._display_name(sorted_c[1])
                lines.append(f"- 如招聘节奏较急，可低优先级观察 {top_c}（分数更高），{second_c} 次之")
        elif contact_count > 0:
            lines.append(f"- 建议优先推进 {contact_count} 位 strong_yes/yes 候选人")
        else:
            lines.append("- 本批候选人建议继续观察")
        lines.append("")

        # Task 13: 排除项
        excluded_list = stats.get("excluded_list", [])
        if excluded_list:
            lines.append("**排除项：**")
            for ex in excluded_list:
                lines.append(f"- {ex}")
            lines.append("")

        # 元信息
        lines.append(f"**run_id：** {self.output_dir.name}")
        lines.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**飞书表格：** {FEISHU_TABLE_URL}")

        return "\n".join(lines).rstrip() + "\n"

    def _load_summary_stats(self, candidates: List[Dict[str, Any]]) -> Dict[str, int]:
        batch_input_path = self.output_dir / "batch_input.json"
        total_processed = len(candidates)
        successful_ingested = len(candidates)
        total_received = len(candidates)
        total_excluded = 0
        excluded_list: List[str] = []

        if batch_input_path.exists():
            try:
                batch_input = json.loads(batch_input_path.read_text(encoding="utf-8"))
                source_candidates = batch_input.get("candidates", [])
                excluded = batch_input.get("excluded", [])
                if isinstance(source_candidates, list):
                    total_processed = len(source_candidates)
                    successful_ingested = len(source_candidates)
                if isinstance(excluded, list) and excluded:
                    total_excluded = len(excluded)
                    total_received = total_processed + total_excluded
                    excluded_list = [e.get("file_name", e.get("reason", "未知")) for e in excluded if isinstance(e, dict)]
            except Exception:
                pass

        return {
            "total_processed": total_processed,
            "successful_ingested": successful_ingested,
            "recommended_count": len(candidates),
            "total_received": total_received,
            "total_excluded": total_excluded,
            "excluded_list": excluded_list,
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

        if "项目经理" in role_label:
            if decision in {"strong_yes", "yes"}:
                return f"{display_name}具备项目推进与跨团队协同经验，建议进入首轮沟通，重点核实产品设计与需求定义的直接职责深度。"
            if decision == "no":
                return f"{display_name}与目标岗位匹配度偏弱，当前不建议作为正式候选人推进。"
            return f"{display_name}与目标岗位存在一定相关性，可作为备选，建议优先确认产品职责重合度。"

        if decision == "no":
            return f"{display_name}与目标岗位匹配度偏弱，当前不建议作为正式候选人推进。"

        if priority == "A":
            return f"{display_name}与目标岗位匹配度较高，建议优先联系。"

        if decision in {"strong_yes", "yes"}:
            return f"{display_name}具备较明确的相关经验信号，建议安排首轮沟通。"

        return f"{display_name}具备一定匹配度，可作为备选进一步核实。"

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

    def _collect_batch_level_risks(self, candidates: List[Dict[str, Any]]) -> List[str]:
        """
        Task 10: 批次级风险，只返回两类核心风险：
        1. 技能不足型（无正式经验 / 技能描述弱）
        2. 角色错位型（实际角色与目标岗位不匹配）
        每个维度最多1条，去重。
        """
        skill_insufficient = None  # 技能不足型
        role_mismatch = None        # 角色错位型
        instability = None          # 稳定性问题

        for c in candidates:
            decision = c.get("decision", "")
            risks = c.get("risks", [])
            for risk_raw in risks[:2]:
                risk = self._normalize_risk(risk_raw).lower()
                if not risk:
                    continue
                # 技能不足型：无经验/无技能/在校为主
                if not skill_insufficient and any(kw in risk for kw in ["无正式", "无前端", "缺乏", "工程化", "深度不足", "笼统"]):
                    normalized = self._normalize_risk(risk_raw)
                    if normalized:
                        skill_insufficient = normalized
                # 角色错位型：职位与目标不匹配
                elif not role_mismatch and any(kw in risk for kw in ["产品经理", "非前端", "ba", "项目经理", "售前", "运营"]):
                    normalized = self._normalize_risk(risk_raw)
                    if normalized:
                        role_mismatch = normalized

        result = []
        if skill_insufficient:
            result.append(skill_insufficient)
        if role_mismatch:
            result.append(role_mismatch)
        if not result:
            result.append("候选人技能与岗位要求存在差距，建议首轮沟通重点核实实际编码能力")
        return result

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
