"""Deprecated compatibility module.

TalentFlow 已收敛为 skill / pipeline。
运行模式门控不再是主设计，保留本模块仅为兼容旧引用。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RunMode(str, Enum):
    EXTERNAL = "external"
    LOCAL_DEV = "local_dev"
    TEST = "test"
    EMERGENCY_DEBUG = "emergency_debug"


@dataclass(frozen=True)
class RuntimeContext:
    run_mode: str = RunMode.EXTERNAL.value
    decision_owner: str = "external_bot"
    evaluator_source: str = "deprecated"
    model_identity: str | None = None

    @property
    def fallback_allowed(self) -> bool:
        return False
