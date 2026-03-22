"""
最终报告生成模块

功能：
- 生成最终 MD 报告
- 生成 owner 摘要
- 导出汇总结果
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class FinalReporter:
    """最终报告生成器"""

    def __init__(self, output_dir: Path):
        """
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_final_report(
        self,
        candidates: List[Dict[str, Any]],
        meta: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> Path:
        """
        生成最终评估报告

        Args:
            candidates: 候选人评估结果列表
            meta: 元数据（JD、企业信息等）
            filename: 指定输出文件名；为空时使用时间戳文件名

        Returns:
            报告文件路径
        """
        report_content = self._build_report_content(candidates, meta)
        report_name = filename or f"final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = self.output_dir / report_name

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        return report_path

    def save_owner_summary(
        self,
        candidates: List[Dict[str, Any]],
        filename: str = "owner_summary.md",
    ) -> Path:
        """生成并保存 owner 摘要。"""
        summary = self.generate_owner_summary(candidates)
        summary_path = self.output_dir / filename
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)
        return summary_path

    def _build_report_content(
        self,
        candidates: List[Dict[str, Any]],
        meta: Dict[str, Any]
    ) -> str:
        """构建报告内容"""
        content = f"# 招聘决策报告\n\n"
        content += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        if meta.get("jd"):
            content += f"## 职位描述\n\n{meta['jd']}\n\n"

        if meta.get("company"):
            content += f"## 企业信息\n\n{meta['company']}\n\n"

        if meta.get("overall_diagnosis"):
            content += f"## 整体诊断\n\n{meta['overall_diagnosis']}\n\n"

        if meta.get("batch_advice"):
            content += f"## 批量建议\n\n{meta['batch_advice']}\n\n"

        content += f"## 候选人汇总\n\n"
        content += f"**总人数**: {len(candidates)}\n\n"

        by_decision = self._group_by_decision(candidates)
        for decision, cands in by_decision.items():
            content += f"- **{decision}**: {len(cands)}人\n"

        content += "\n---\n\n"

        content += "## 详细评估\n\n"
        for idx, cand in enumerate(candidates, 1):
            content += self._build_candidate_section(cand, idx)
            content += "\n---\n\n"

        return content

    def _build_candidate_section(self, candidate: Dict[str, Any], idx: int) -> str:
        """构建单个候选人部分"""
        content = f"### {idx}. {candidate.get('candidate_id') or candidate.get('name', '未知')}\n\n"
        content += f"- **决策**: {candidate.get('decision', '未评估')}\n"
        content += f"- **总分**: {candidate.get('total_score', 0)}/100\n"
        content += f"- **优先级**: {candidate.get('priority', '-')}\n"
        content += f"- **联系时机**: {candidate.get('action_timing', '-')}\n"

        if candidate.get('core_judgement'):
            content += f"\n**核心判断**:\n- {candidate['core_judgement']}\n"

        if candidate.get('reasons'):
            content += f"\n**评估理由**:\n"
            for reason in candidate['reasons'][:3]:
                content += f"- {reason}\n"

        if candidate.get('risks'):
            content += f"\n**风险分析**:\n"
            for risk in candidate['risks'][:3]:
                content += f"- {risk.get('description', risk) if isinstance(risk, dict) else risk}\n"

        action = candidate.get('action', {})
        if action.get('hook_message'):
            content += f"\n**钩子话术**:\n- {action['hook_message']}\n"
        if action.get('verification_question'):
            content += f"\n**验证问题**:\n- {action['verification_question']}\n"
        if action.get('deep_questions'):
            content += f"\n**深问问题**:\n"
            for question in action['deep_questions'][:3]:
                content += f"- {question}\n"

        content += "\n"
        return content

    def _group_by_decision(self, candidates: List[Dict[str, Any]]) -> Dict[str, List]:
        """按决策分类"""
        groups = {}
        for cand in candidates:
            decision = cand.get('decision', 'unknown')
            if decision not in groups:
                groups[decision] = []
            groups[decision].append(cand)
        return groups

    def generate_owner_summary(
        self,
        candidates: List[Dict[str, Any]]
    ) -> str:
        """
        生成 owner 摘要（简短版）

        Returns:
            摘要文本
        """
        stats = self._load_summary_stats(candidates)
        today_candidates = [c for c in candidates if c.get("action_timing") == "today"]
        this_week_candidates = [c for c in candidates if c.get("action_timing") == "this_week"]
        optional_candidates = [c for c in candidates if c.get("action_timing") == "optional"]
        contact_candidates = [c for c in candidates if c.get("decision") in {"strong_yes", "yes"}]
        maybe_candidates = [c for c in candidates if c.get("decision") == "maybe"]

        lines = ["# 招聘决策摘要", ""]
        lines.append("## 基本情况")
        lines.append(f"- 总处理人数：{stats['total_processed']}")
        lines.append(f"- 成功解析人数：{stats['successful_ingested']}")
        lines.append(f"- 进入推荐池人数：{stats['recommended_count']}")
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
                f"{int(candidate.get('total_score', 0))}分｜{candidate.get('priority', '-')}"
                f"优先级｜{self._timing_label(candidate.get('action_timing'))}  "
            )
            lines.append(f"   核心判断：{self._core_judgement(candidate)}")
            lines.append("")

        lines.append(f"## 值得联系（共 {len(contact_candidates)} 人）")
        for candidate in contact_candidates[:5]:
            lines.append(
                f"- {self._display_name(candidate)}｜{self._role_label(candidate)}｜"
                f"{int(candidate.get('total_score', 0))}分｜{candidate.get('priority', '-')}｜"
                f"{candidate.get('action_timing', '-')}"
            )
        if len(contact_candidates) > 5:
            lines.append("- ……")
        lines.append("")

        lines.append("## 主要共性风险")
        for risk in self._collect_common_risks(candidates):
            lines.append(f"- {risk}")
        lines.append("")

        lines.append("## 建议的下一步")
        if today_candidates:
            lines.append("1. 今天先联系 A 优先级候选人")
        else:
            lines.append("1. 先确认当前推荐池中最值得优先推进的人选")
        if this_week_candidates:
            lines.append("2. 本周完成 B 优先级首轮筛选")
        else:
            lines.append("2. 本周补充完成备选候选人的初筛判断")
        if maybe_candidates:
            lines.append("3. 首轮沟通重点验证：项目 ownership、复杂协作、业务落地深度")
        else:
            lines.append("3. 推进已推荐候选人的首轮沟通，并验证真实职责边界")

        return "\n".join(lines) + "\n"

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
        for key in ("candidate_name", "name"):
            value = str(candidate.get(key, "")).strip()
            if value:
                return value

        candidate_id = str(candidate.get("candidate_id", "")).strip()
        chinese_segments = re.findall(r"[\u4e00-\u9fff]{2,4}", candidate_id)
        for segment in chinese_segments:
            if segment.endswith(("经理", "总监", "顾问", "工程师", "专员")):
                continue
            return segment

        return candidate_id or "未知候选人"

    def _role_label(self, candidate: Dict[str, Any]) -> str:
        for key in ("role_label", "title"):
            value = str(candidate.get(key, "")).strip()
            if value:
                return value

        candidate_id = str(candidate.get("candidate_id", "")).strip()
        segments = [segment for segment in re.split(r"[_\-\s]+", candidate_id) if segment]
        role_keywords = ("高级产品经理", "产品经理", "项目经理", "运营", "工程师", "销售", "顾问")
        for keyword in role_keywords:
            for segment in segments:
                if keyword in segment:
                    return segment

        return "待确认岗位"

    def _timing_label(self, timing: Any) -> str:
        timing_map = {
            "today": "今天联系",
            "this_week": "本周联系",
            "optional": "可选",
        }
        return timing_map.get(str(timing).strip(), "待安排")

    def _core_judgement(self, candidate: Dict[str, Any]) -> str:
        value = str(candidate.get("core_judgement", "")).strip()
        if value:
            return value
        return "具备一定匹配度，建议通过首轮沟通进一步确认。"

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
        if isinstance(risk, dict):
            return str(risk.get("description", "")).strip()
        return str(risk).strip()