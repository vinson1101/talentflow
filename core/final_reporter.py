"""
最终报告生成模块

功能：
- 生成最终 MD 报告
- 生成 owner 摘要
- 导出汇总结果
"""

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
        summary = f"【招聘决策摘要】\n\n"
        summary += f"总评估人数：{len(candidates)}\n\n"

        strong_yes = [c for c in candidates if c.get('decision') == 'strong_yes']
        if strong_yes:
            summary += f"🌟 强烈推荐（{len(strong_yes)}人）：\n"
            for cand in strong_yes[:3]:
                summary += f"- {cand.get('candidate_id', cand.get('name', '未知'))}（{cand.get('total_score', 0)}分）\n"
            summary += "\n"

        yes = [c for c in candidates if c.get('decision') == 'yes']
        if yes:
            summary += f"✅ 值得联系（{len(yes)}人）：\n"
            for cand in yes[:5]:
                summary += f"- {cand.get('candidate_id', cand.get('name', '未知'))}（{cand.get('total_score', 0)}分）\n"
            summary += "\n"

        return summary
