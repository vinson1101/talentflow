#!/usr/bin/env python3
"""
scripts/publish_to_feishu_table.py

将 TalentFlow run 的最终结果发布到飞书多维表格。

用法:
    # 方式1: 指定 run 目录（自动查找 bitable_app_token）
    python scripts/publish_to_feishu_table.py runs/run_20260323_214437

    # 方式2: 指定 run 目录 + bitable_app_token（新建表）
    python scripts/publish_to_feishu_table.py runs/run_20260323_214437 \\
        --bitable-app-token Bxxxxxxxxxx

    # 方式3: 指定 run 目录 + bitable_app_token + 表ID（追加到现有表）
    python scripts/publish_to_feishu_table.py runs/run_20260323_214437 \\
        --bitable-app-token Bxxxxxxxxxx \\
        --runs-table-id tblXXXXX \\
        --candidates-table-id tblYYYYY

输出:
    - 在飞书多维表格中写入 1 条 Runs 记录
    - 在 Candidates 表中写入 N 条候选人记录
    - 打印每步操作的 record_id

依赖:
    - openclaw 工具: feishu_bitable_app, feishu_bitable_app_table,
      feishu_bitable_app_table_field, feishu_bitable_app_table_record
"""

import argparse
import json
import sys
import time
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.feishu_bitable_writer import (
    RUN_TABLE_NAME,
    CANDIDATES_TABLE_NAME,
    RUN_FIELDS,
    CANDIDATE_FIELDS,
    build_all_records,
    load_run_sources,
    now_ms,
)


# ---------------------------------------------------------------------------
# 飞书工具调用封装（通过 stdout JSON 输出，供 OpenClaw exec 调用）
# ---------------------------------------------------------------------------

# 注意：实际通过 OpenClaw 的 feishu_bitable_* 工具调用。
# 本脚本将需要的 API 调用序列化为 JSONPackets 输出到 stdout，
# 由上层 wrapper 解析并执行。
# 格式：{"tool": "tool_name", "params": {...}}

def _packet(tool: str, params: dict) -> dict:
    return {"tool": tool, "params": params}


def _p(*dicts):
    """将多个 dict 合并后输出为 JSONPacket"""
    result = {}
    for d in dicts:
        result.update(d)
    return result


# ---------------------------------------------------------------------------
# 主逻辑（构造所有要执行的工具调用）
# ---------------------------------------------------------------------------

def plan_publish(
    run_dir: str,
    bitable_app_token: str = None,
    runs_table_id: str = None,
    candidates_table_id: str = None,
    bitable_name: str = "TalentFlow Results",
) -> dict:
    """
    规划发布步骤，返回要执行的工具调用序列（JSON格式）。

    Returns:
        {
            "steps": [ {"tool": "...", "params": {...}}, ... ],
            "run_id": "...",
            "run_record": {...},
            "candidate_records": [...],
            "bitable_app_token": "...",   # 新建时返回
            "runs_table_id": "...",
            "candidates_table_id": "...",
        }
    """
    run_dir = str(Path(run_dir).resolve())
    run_record, candidate_records = build_all_records(run_dir)
    run_id = run_record["run_id"]

    steps = []

    # Step 1: 确定 bitable app
    if not bitable_app_token:
        # 需要新建 bitable app
        steps.append(_packet("feishu_bitable_app", {
            "action": "create",
            "name": bitable_name,
        }))
        create_app_step_idx = len(steps) - 1

    else:
        create_app_step_idx = None
        steps.append(_packet("feishu_bitable_app", {
            "action": "get",
            "app_token": bitable_app_token,
        }))

    # Step 2: 创建 Runs 表（仅当新建 app 时）
    if not runs_table_id:
        steps.append(_packet("feishu_bitable_app_table", {
            "action": "create",
            "app_token": "{{bitable_app_token}}",  # 占位符，下一步替换
            "table": {
                "name": RUN_TABLE_NAME,
                "fields": [
                    {"field_name": fname, "type": ftype}
                    for fname, ftype in RUN_FIELDS.items()
                ],
            },
        }))
        create_runs_table_step_idx = len(steps) - 1
    else:
        create_runs_table_step_idx = None

    # Step 3: 创建 Candidates 表（仅当新建 app 时）
    if not candidates_table_id:
        steps.append(_packet("feishu_bitable_app_table", {
            "action": "create",
            "app_token": "{{bitable_app_token}}",
            "table": {
                "name": CANDIDATES_TABLE_NAME,
                "fields": [
                    {"field_name": fname, "type": ftype}
                    for fname, ftype in CANDIDATE_FIELDS.items()
                ],
            },
        }))
        create_candidates_table_step_idx = len(steps) - 1
    else:
        create_candidates_table_step_idx = None

    # Step 4: 写入 Runs 记录
    # 先把 created_at 从毫秒时间戳转为可读日期字符串（工具支持字符串写入日期字段）
    rr = dict(run_record)
    created_at_ms = rr.pop("created_at", None)
    if created_at_ms:
        import datetime
        dt = datetime.datetime.fromtimestamp(created_at_ms / 1000, tz=datetime.timezone.utc)
        rr["created_at"] = created_at_ms  # 飞书日期字段接受毫秒时间戳

    steps.append(_packet("feishu_bitable_app_table_record", {
        "action": "create",
        "app_token": "{{bitable_app_token}}",
        "table_id": "{{runs_table_id}}",
        "fields": rr,
    }))

    # Step 5: 批量写入 Candidates 记录（每批500，分批）
    BATCH_SIZE = 500
    for i in range(0, len(candidate_records), BATCH_SIZE):
        batch = candidate_records[i : i + BATCH_SIZE]
        steps.append(_packet("feishu_bitable_app_table_record", {
            "action": "batch_create",
            "app_token": "{{bitable_app_token}}",
            "table_id": "{{candidates_table_id}}",
            "records": [{"fields": r} for r in batch],
        }))

    return {
        "steps": steps,
        "run_id": run_id,
        "run_record": run_record,
        "candidate_records": candidate_records,
        "bitable_app_token": bitable_app_token,
        "runs_table_id": runs_table_id,
        "candidates_table_id": candidates_table_id,
        "bitable_name": bitable_name,
        "create_app_step_idx": create_app_step_idx,
        "create_runs_table_step_idx": create_runs_table_step_idx,
        "create_candidates_table_step_idx": create_candidates_table_step_idx,
    }


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="将 TalentFlow run 结果发布到飞书多维表格")
    parser.add_argument("run_dir", help="run 目录路径，如 runs/run_20260323_214437")
    parser.add_argument("--bitable-app-token", help="飞书多维表格 app token（不传则新建）")
    parser.add_argument("--runs-table-id", help="Runs 表 table_id（不传则在新建 app 时自动创建）")
    parser.add_argument("--candidates-table-id", help="Candidates 表 table_id（不传则在新建 app 时自动创建）")
    parser.add_argument("--bitable-name", default="TalentFlow Results", help="新建多维表格的名称")
    parser.add_argument("--dry-run", action="store_true", help="只打印调用计划，不实际执行")
    parser.add_argument("--output-json", help="将调用计划输出到指定 JSON 文件")
    args = parser.parse_args()

    # 加载数据源（验证路径合法性）
    try:
        run_id, final_output, quality_meta, batch_input, owner_summary, jd = load_run_sources(args.run_dir)
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)

    plan = plan_publish(
        run_dir=args.run_dir,
        bitable_app_token=args.bitable_app_token,
        runs_table_id=args.runs_table_id,
        candidates_table_id=args.candidates_table_id,
        bitable_name=args.bitable_name,
    )

    print(f"✅ 数据加载成功")
    print(f"   run_id: {plan['run_id']}")
    print(f"   候选人记录数: {len(plan['candidate_records'])}")
    print(f"   计划执行 {len(plan['steps'])} 个步骤")
    print()

    if args.dry_run:
        print("=== DRY RUN - 调用计划 ===")
        print(json.dumps(plan["steps"], ensure_ascii=False, indent=2))
        print()
        print("=== run_record ===")
        print(json.dumps(plan["run_record"], ensure_ascii=False, indent=2))
        print()
        print("=== candidate_records 摘要 ===")
        for r in plan["candidate_records"]:
            print(f"  {r['rank']}. {r['candidate_name']} | score={r['total_score']} | "
                  f"decision={r['decision']} | priority={r['priority']} | "
                  f"action_timing={r['action_timing']}")

    if args.output_json:
        Path(args.output_json).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 调用计划已写入 {args.output_json}")

    if args.dry_run:
        return

    # 实际执行（通过 OpenClaw wrapper，见下方 execute_plan 函数）
    # 这里只打印说明，实际由 OpenClaw agent 执行
    print("请将以上调用计划交由 OpenClaw feishu_bitable_* 工具执行。")
    print("推荐做法：在 OpenClaw 对话中发送『执行发布计划』并附上 --output-json 输出文件路径。")


if __name__ == "__main__":
    main()
