"""Deprecated compatibility module.

TalentFlow 已收敛为 skill / pipeline。
该模块不再代表主路径设计，仅为兼容旧引用保留。
"""

from __future__ import annotations

from pipelines.process_local_folder import process_local_folder

__all__ = ["process_local_folder"]
