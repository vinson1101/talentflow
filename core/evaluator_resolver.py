"""Deprecated compatibility module.

TalentFlow 已收敛为 skill / pipeline。
旧的 evaluator resolver 设计不再是主路径，保留本模块仅为兼容旧引用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from core.runtime import RuntimeContext


BatchEvaluator = Callable[[Dict[str, Any]], str]


class MissingEvaluatorError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedEvaluator:
    evaluator: BatchEvaluator
    runtime_context: RuntimeContext


def resolve_batch_evaluator(evaluator: BatchEvaluator | None, *, run_mode: str) -> ResolvedEvaluator:
    if evaluator is None:
        raise MissingEvaluatorError(
            "TalentFlow 已调整为 skill / pipeline。请由外部 bot 提供 decision handler，而不是依赖内部 evaluator resolver。"
        )

    return ResolvedEvaluator(
        evaluator=evaluator,
        runtime_context=RuntimeContext(
            run_mode=run_mode,
            decision_owner="external_bot",
            evaluator_source="deprecated",
            model_identity=None,
        ),
    )
