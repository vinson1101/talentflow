"""
core/feishu_bitable_writer.py

将 TalentFlow 的最终结果写入飞书多维表格。
本模块是纯数据转换层，不直接调用飞书工具，而是通过 OpenClaw 的 feishu_bitable_* 工具执行写入。

职责边界：
- 读取 final_output.json、quality_meta.json、run_meta.json、owner_summary.md
- 将数据映射为飞书多维表格的记录格式
- 返回构造好的 records 列表，供调用者通过 feishu_bitable_* 工具写入
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

RUN_TABLE_NAME = "Runs"
CANDIDATES_TABLE_NAME = "Candidates"

# Runs 表字段定义（field_name → type）
# type: 1=文本, 2=数字, 3=单选, 4=多选, 5=日期, 7=复选框, 11=人员, 13=电话, 15=超链接, 1001=创建时间
RUN_FIELDS: Dict[str, int] = {
    "run_id": 1,                   # 文本
    "jd_title": 1,                 # 文本
    "jd_location": 1,              # 文本
    "jd_salary_range": 1,          # 文本
    "candidate_count": 2,          # 数字
    "contact_count": 2,            # 数字
    "top_candidate_names": 1,      # 文本（数组转文本）
    "quality_score": 2,            # 数字
    "quality_flag": 1,             # 文本
    "identity_conflict_count": 2,  # 数字
    "avg_score": 2,                # 数字
    "output_version": 1,           # 文本
    "owner_summary": 1,            # 文本（长文本）
    "batch_input_path": 1,         # 文本
    "final_output_path": 1,        # 文本
    "created_at": 5,               # 日期（毫秒时间戳）
}

# Candidates 表字段定义
CANDIDATE_FIELDS: Dict[str, int] = {
    # 基础识别
    "run_id": 1,
    "candidate_id": 1,
    "candidate_name": 1,
    "canonical_name": 1,
    "role_label": 1,
    "source_platform": 1,
    "source_file_name": 1,
    # AI 决策主字段
    "rank": 2,
    "total_score": 2,
    "decision": 1,
    "priority": 1,
    "action_timing": 1,
    "should_contact": 7,
    "core_judgement": 1,
    "reasons": 1,
    "risks": 1,
    "verification_question": 1,
    "hook_message": 1,
    "message_template": 1,
    # 7维评分
    "hard_skill_match": 2,
    "experience_depth": 2,
    "innovation_potential": 2,
    "execution_goal_breakdown": 2,
    "team_fit": 2,
    "willingness": 2,
    "stability": 2,
    "template_id": 1,
    "weighted_total": 2,
    "dimension_evidence_summary": 1,
    # 质量与身份
    "has_identity_conflict": 7,
    "identity_resolution": 1,
    "conflict_fields": 1,
    "quality_note": 1,
    # 人工跟进字段（脚本不覆盖，仅写入预留）
    "follow_up_status": 1,
    "hr_owner": 1,
    "hr_comment": 1,
    "interview_result": 1,
    "reject_reason": 1,
    "manual_priority": 1,
    "manual_override_note": 1,
    "final_outcome": 1,
}

# 飞书字段类型映射到名称（用于日志输出）
FIELD_TYPE_NAMES = {
    1: "文本",
    2: "数字",
    3: "单选",
    4: "多选",
    5: "日期",
    7: "复选框",
    11: "人员",
    13: "电话",
    15: "超链接",
    17: "附件",
    1001: "创建时间",
    1002: "修改时间",
}


# ---------------------------------------------------------------------------
# 数据转换工具
# ---------------------------------------------------------------------------

def array_to_text(arr: Any, separator: str = "\n") -> str:
    """将列表转为分隔符分隔的文本，用于表格展示。"""
    if not arr:
        return ""
    if isinstance(arr, list):
        return separator.join(str(x) for x in arr)
    return str(arr)


def now_ms() -> int:
    """返回当前时间的毫秒时间戳。"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def extract_run_id_from_path(final_output_path: str) -> str:
    """从 final_output.json 路径中提取 run_id。"""
    # 路径格式: .../runs/run_20260323_214437/final_output.json
    m = re.search(r'run_(\d{8}_\d{6})', final_output_path)
    if m:
        return f"run_{m.group(1)}"
    # fallback: 用当前时间戳
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


# ---------------------------------------------------------------------------
# Runs 表数据构建
# ---------------------------------------------------------------------------

def build_run_record(
    run_id: str,
    final_output_path: str,
    batch_input_path: str,
    quality_meta: Dict[str, Any],
    owner_summary: str,
    jd: Dict[str, Any],
    final_output: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    根据 Runs 表字段定义，从各数据源构造一条 Runs 记录。

    Args:
        run_id: 批次ID
        final_output_path: final_output.json 的绝对路径
        batch_input_path: batch_input.json 的绝对路径
        quality_meta: quality_meta.json 内容
        owner_summary: owner_summary.md 原文
        jd: batch_input.json 中的 jd 对象

    Returns:
        符合 Runs 表字段的 dict，key=field_name，value=字段值
    """
    # top_recommendations 中 priority=A 的人（来自 final_output.json）
    top_recs = (final_output or {}).get("top_recommendations", [])
    top_names = [
        c.get("candidate_name", "")
        for c in top_recs
        if c.get("priority") == "A"
    ]
    top_candidate_names = array_to_text(top_names, separator=", ")

    record = {
        "run_id": run_id,
        "jd_title": jd.get("title", ""),
        "jd_location": jd.get("location", ""),
        "jd_salary_range": jd.get("salary_range", ""),
        "candidate_count": quality_meta.get("candidate_count", 0),
        "contact_count": _calc_contact_count(quality_meta),
        "top_candidate_names": top_candidate_names,
        "quality_score": quality_meta.get("quality_score", 0),
        "quality_flag": quality_meta.get("quality_flag", ""),
        "identity_conflict_count": quality_meta.get("identity_conflict_count", 0),
        "avg_score": round(quality_meta.get("avg_score", 0), 2),
        "output_version": "v1",  # TalentFlow 当前版本标记
        "owner_summary": owner_summary[:5000] if owner_summary else "",  # 截断防超限
        "batch_input_path": batch_input_path,
        "final_output_path": final_output_path,
        "created_at": now_ms(),
    }
    return record


def _calc_contact_count(quality_meta: Dict[str, Any]) -> int:
    """计算应该联系的人数。"""
    # 从 top_recommendations 中筛选 decision 包含 yes/strong_yes 且 should_contact=true
    # 但 quality_meta 没有这个细分，用 contact_ratio 估算
    count = quality_meta.get("candidate_count", 0)
    ratio = quality_meta.get("contact_ratio", 0.5)
    return int(round(count * ratio))


# ---------------------------------------------------------------------------
# Candidates 表数据构建
# ---------------------------------------------------------------------------

def build_candidate_records(
    run_id: str,
    final_output: Dict[str, Any],
    batch_input: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    根据 Candidates 表字段定义，从 final_output.json 和 batch_input.json 构造候选人记录列表。

    Args:
        run_id: 批次ID
        final_output: final_output.json 内容（dict）
        batch_input: batch_input.json 内容（dict）

    Returns:
        List[Dict]，每条为一条候选人记录
    """
    candidates_out = final_output.get("top_recommendations", [])
    candidates_in = batch_input.get("candidates", [])

    # 建立 candidate_id → batch_input 记录的映射（用于 source_file_name）
    in_map = {c.get("candidate_id", ""): c for c in candidates_in}

    records = []
    for c in candidates_out:
        candidate_id = c.get("candidate_id", "")

        # 从 batch_input 获取原始文件名字段
        in_c = in_map.get(candidate_id, {})
        raw_resume = in_c.get("raw_resume", {})
        ingestion_meta = in_c.get("ingestion_meta", {})

        # source_file_name 优先从 ingestion_meta 读
        source_file_name = ingestion_meta.get("original_file_name", "") or raw_resume.get("source", {}).get("file_name", "")

        # structured_score
        ss = c.get("structured_score", {})
        ds = ss.get("dimension_scores", {})
        de = ss.get("dimension_evidence", {})

        # 7维 evidence 拼接成一段文本
        dim_keys = [
            "hard_skill_match", "experience_depth", "innovation_potential",
            "execution_goal_breakdown", "team_fit", "willingness", "stability"
        ]
        evidence_parts = [f"[{k}] {de.get(k, '')}" for k in dim_keys if de.get(k)]
        dimension_evidence_summary = "\n".join(evidence_parts)

        # identity_meta
        im = c.get("identity_meta", {})
        identity_resolution = im.get("resolution", "unchanged")

        # action
        action = c.get("action", {})

        record = {
            # 基础识别
            "run_id": run_id,
            "candidate_id": candidate_id,
            "candidate_name": c.get("candidate_name", ""),
            "canonical_name": im.get("canonical_name", c.get("candidate_name", "")),
            "role_label": c.get("role_label", ""),
            "source_platform": "local",
            "source_file_name": source_file_name,
            # AI 决策主字段
            "rank": c.get("rank", 0),
            "total_score": round(c.get("total_score", 0), 2),
            "decision": c.get("decision", ""),
            "priority": c.get("priority", ""),
            "action_timing": c.get("action_timing", ""),
            "should_contact": action.get("should_contact", False),
            "core_judgement": c.get("core_judgement", ""),
            "reasons": array_to_text(c.get("reasons", [])),
            "risks": array_to_text(c.get("risks", [])),
            "verification_question": action.get("verification_question", ""),
            "hook_message": action.get("hook_message", ""),
            "message_template": action.get("message_template", ""),
            # 7维评分
            "hard_skill_match": round(ds.get("hard_skill_match", 0), 2),
            "experience_depth": round(ds.get("experience_depth", 0), 2),
            "innovation_potential": round(ds.get("innovation_potential", 0), 2),
            "execution_goal_breakdown": round(ds.get("execution_goal_breakdown", 0), 2),
            "team_fit": round(ds.get("team_fit", 0), 2),
            "willingness": round(ds.get("willingness", 0), 2),
            "stability": round(ds.get("stability", 0), 2),
            "template_id": ss.get("template_id", ""),
            "weighted_total": round(ss.get("weighted_total", 0), 2),
            "dimension_evidence_summary": dimension_evidence_summary[:3000],  # 截断防超限
            # 质量与身份
            "has_identity_conflict": bool(im.get("has_conflict", False)),
            "identity_resolution": identity_resolution,
            "conflict_fields": array_to_text(im.get("conflict_fields", [])),
            "quality_note": "",
            # 人工跟进字段（预留，值留空由HR填写）
            "follow_up_status": "",
            "hr_owner": "",
            "hr_comment": "",
            "interview_result": "",
            "reject_reason": "",
            "manual_priority": "",
            "manual_override_note": "",
            "final_outcome": "",
        }
        records.append(record)

    return records


# ---------------------------------------------------------------------------
# 批量写入辅助：字段过滤（只保留表定义的字段）
# ---------------------------------------------------------------------------

def filter_fields(record: Dict[str, Any], field_definitions: Dict[str, int]) -> Dict[str, Any]:
    """只保留在 field_definitions 中定义了的字段，去掉多余字段。"""
    return {k: v for k, v in record.items() if k in field_definitions}


def filter_run_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return filter_fields(record, RUN_FIELDS)


def filter_candidate_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return filter_fields(record, CANDIDATE_FIELDS)


# ---------------------------------------------------------------------------
# 核心读取函数（供调用者使用）
# ---------------------------------------------------------------------------

def load_run_sources(run_dir: str) -> Tuple[str, Dict[str, Any], Dict[str, Any], Dict[str, Any], str, Dict[str, Any]]:
    """
    从 run 目录加载所有数据源。

    Returns:
        (run_id, final_output, quality_meta, batch_input, owner_summary, jd)

    Raises:
        FileNotFoundError: 必需文件缺失
    """
    run_path = Path(run_dir)

    final_output_path = run_path / "final_output.json"
    quality_meta_path = run_path / "quality_meta.json"
    batch_input_path = run_path / "batch_input.json"
    owner_summary_path = run_path / "owner_summary.md"

    if not final_output_path.exists():
        raise FileNotFoundError(f"final_output.json not found: {final_output_path}")
    if not quality_meta_path.exists():
        raise FileNotFoundError(f"quality_meta.json not found: {quality_meta_path}")
    if not batch_input_path.exists():
        raise FileNotFoundError(f"batch_input.json not found: {batch_input_path}")
    if not owner_summary_path.exists():
        raise FileNotFoundError(f"owner_summary.md not found: {owner_summary_path}")

    with open(final_output_path, "r", encoding="utf-8") as f:
        final_output = json.load(f)

    with open(quality_meta_path, "r", encoding="utf-8") as f:
        quality_meta = json.load(f)

    with open(batch_input_path, "r", encoding="utf-8") as f:
        batch_input = json.load(f)

    with open(owner_summary_path, "r", encoding="utf-8") as f:
        owner_summary = f.read()

    run_id = extract_run_id_from_path(str(final_output_path.resolve()))
    jd = batch_input.get("jd", {})

    return run_id, final_output, quality_meta, batch_input, owner_summary, jd


def build_all_records(run_dir: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    从 run 目录构建 Runs 表单条记录 + Candidates 表所有记录。

    Returns:
        (run_record, candidate_records)
        run_record: Runs 表的单条记录
        candidate_records: Candidates 表的记录列表
    """
    run_id, final_output, quality_meta, batch_input, owner_summary, jd = load_run_sources(run_dir)

    # 解析 run_id 中的时间（用于 batch_input_path / final_output_path）
    fo_resolved = str((Path(run_dir) / "final_output.json").resolve())
    bi_resolved = str((Path(run_dir) / "batch_input.json").resolve())

    run_record = build_run_record(
        run_id=run_id,
        final_output_path=fo_resolved,
        batch_input_path=bi_resolved,
        quality_meta=quality_meta,
        owner_summary=owner_summary,
        jd=jd,
        final_output=final_output,
    )
    run_record = filter_run_record(run_record)

    candidate_records_raw = build_candidate_records(
        run_id=run_id,
        final_output=final_output,
        batch_input=batch_input,
    )
    candidate_records = [filter_candidate_record(r) for r in candidate_records_raw]

    return run_record, candidate_records
