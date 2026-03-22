"""
候选人数据存储模块

功能：
- 单候选人 JSON/MD 落盘
- 按运行时间组织
- 支持增量存储
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import json


class CandidateStore:
    """候选人存储管理器"""

    def __init__(self, run_dir: Path):
        """
        Args:
            run_dir: 运行目录，如 runs/run_2026-03-22_180500/
        """
        self.run_dir = Path(run_dir)
        self.candidates_dir = self.run_dir / "candidates"
        self.candidates_dir.mkdir(parents=True, exist_ok=True)

    def save_candidate(
        self,
        candidate: Dict[str, Any],
        candidate_id: str,
        save_json: bool = True,
        save_md: bool = True
    ) -> Dict[str, Optional[str]]:
        """
        保存单个候选人

        Args:
            candidate: 候选人数据
            candidate_id: 候选人ID
            save_json: 是否保存JSON
            save_md: 是否保存MD

        Returns:
            {
                "json_path": "...",
                "md_path": "..."
            }
        """
        result = {}

        if save_json:
            json_path = self.candidates_dir / f"cand_{candidate_id}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(candidate, f, ensure_ascii=False, indent=2)
            result["json_path"] = str(json_path)

        if save_md:
            md_path = self.candidates_dir / f"cand_{candidate_id}.md"
            self._save_candidate_md(candidate, md_path)
            result["md_path"] = str(md_path)

        return result

    def _save_candidate_md(self, candidate: Dict[str, Any], md_path: Path):
        """保存候选人Markdown报告"""
        content = f"# 候选人评估报告\n\n"
        content += f"**姓名**: {candidate.get('name', '未知')}\n\n"
        content += f"**决策**: {candidate.get('decision', '未评估')}\n\n"
        content += f"**总分**: {candidate.get('total_score', 0)}\n\n"

        # 添加更多字段...

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """读取单个候选人"""
        json_path = self.candidates_dir / f"cand_{candidate_id}.json"
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def list_candidates(self) -> list:
        """列出所有候选人ID"""
        candidates = []
        for json_file in self.candidates_dir.glob("cand_*.json"):
            cand_id = json_file.stem.replace("cand_", "")
            candidates.append(cand_id)
        return sorted(candidates)
