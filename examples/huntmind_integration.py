from __future__ import annotations

import json
from typing import Any, Dict

from entrypoints.skill_entry import run_talentflow_skill


class HuntMindBatchEvaluator:
    """示例：把 HuntMind 的招聘决策能力适配成 TalentFlow 可注入 evaluator。"""

    def __init__(self, huntmind_runtime: Any):
        self.huntmind_runtime = huntmind_runtime

    def __call__(self, batch_input: Dict[str, Any]) -> str:
        """
        TalentFlow 当前要求 evaluator 接收 batch_input，并返回模型原始输出文本。

        这里假设 HuntMind runtime 暴露了 evaluate_recruiting_batch 方法；
        你只需要保证最后返回给 TalentFlow 的是 runner 可消费的 JSON 文本。
        """
        result = self.huntmind_runtime.evaluate_recruiting_batch(
            batch_input=batch_input,
            role="ai_hr",
            capability="recruiting_decision",
        )

        if isinstance(result, str):
            return result

        return json.dumps(result, ensure_ascii=False)


def run_talentflow_from_huntmind(
    *,
    huntmind_runtime: Any,
    folder_path: str,
    jd_data: Dict[str, Any],
):
    evaluator = HuntMindBatchEvaluator(huntmind_runtime)
    return run_talentflow_skill(
        folder_path=folder_path,
        jd_data=jd_data,
        evaluator=evaluator,
    )


class FakeHuntMindRuntime:
    """仅用于演示接线方式。"""

    def evaluate_recruiting_batch(self, *, batch_input: Dict[str, Any], role: str, capability: str) -> Dict[str, Any]:
        raise NotImplementedError(
            "请在 HuntMind 本体里实现 evaluate_recruiting_batch，"
            "并返回符合 TalentFlow runner 预期的 JSON 结构。"
        )
