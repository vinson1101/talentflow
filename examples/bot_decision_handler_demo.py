from __future__ import annotations

import json
from typing import Any, Dict


class DemoRecruitingBot:
    """示例 bot：真实场景里这里应该是 HuntMind / OpenClaw bot。"""

    def decide(self, batch_input: Dict[str, Any]) -> str:
        # 这里只是示意接口，不代表真实判断逻辑
        result = {
            "overall_diagnosis": f"本批共收到 {len(batch_input.get('candidates', []))} 份简历，等待 bot 判断。",
            "batch_advice": "请将本示例替换为 HuntMind 的真实招聘判断逻辑。",
            "top_recommendations": [],
        }
        return json.dumps(result, ensure_ascii=False)


def decide(batch_input: Dict[str, Any]) -> str:
    return DemoRecruitingBot().decide(batch_input)
