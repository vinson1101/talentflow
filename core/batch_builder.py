"""
批量输入构建模块

功能：
- 从候选人中间产物组装批量输入
- 为AI模型准备结构化输入
- 支持自定义提示词模板
"""

from pathlib import Path
from typing import List, Dict, Any
import json


class BatchBuilder:
    """批量输入构建器"""

    def __init__(self, jd_content: str):
        """
        Args:
            jd_content: 职位描述内容
        """
        self.jd_content = jd_content

    def build_batch_input(
        self,
        candidates: List[Dict[str, Any]],
        mode: str = "sequential"
    ) -> Dict[str, Any]:
        """
        构建批量输入

        Args:
            candidates: 候选人列表
            mode: 处理模式
                - "sequential": 逐个评估
                - "batch": 批量对比评估

        Returns:
            {
                "mode": "...",
                "jd": "...",
                "candidates": [...],
                "meta": {...}
            }
        """
        return {
            "mode": mode,
            "jd": self.jd_content,
            "candidates": [
                {
                    "id": str(idx),
                    "name": cand.get("name", "未知"),
                    "raw_text": cand.get("raw_text", ""),
                    **cand
                }
                for idx, cand in enumerate(candidates)
            ],
            "meta": {
                "total_count": len(candidates),
                "timestamp": self._get_timestamp()
            }
        }

    def save_batch_input(self, batch_input: Dict[str, Any], run_dir: Path):
        """保存批量输入到文件"""
        batch_file = run_dir / "batch_input.json"
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump(batch_input, f, ensure_ascii=False, indent=2)
        return batch_file

    def load_batch_input(self, run_dir: Path) -> Dict[str, Any]:
        """从文件加载批量输入"""
        batch_file = run_dir / "batch_input.json"
        with open(batch_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
