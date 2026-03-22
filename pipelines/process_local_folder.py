"""
处理本地/临时目录中的简历文件。

TalentFlow 的职责仅限于：
1. 扫描目录中的简历文件
2. 解析并标准化候选人信息
3. 构建、校验 batch_input
4. 将 batch_input 交给外部 bot 提供的 decision handler
5. 对 decision handler 返回结果做结构化后处理并落盘

重要边界：
- TalentFlow 是招聘 skill / pipeline，不是 AI 员工本体
- TalentFlow 不负责决定模型、API key、base_url
- 决策主体始终是外部 bot（如 HuntMind / OpenClaw bot）
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from adapters.local_adapter import LocalAdapter
from core.batch_builder import BatchBuilder
from core.candidate_store import CandidateStore
from core.final_reporter import FinalReporter
from core.resume_ingest import ingest_resume_files
from core.runner import run as run_output_processing


DEFAULT_FILE_TYPES = ["pdf", "docx", "txt", "md"]
BatchDecisionHandler = Callable[[Dict[str, Any]], str]


def process_local_folder(
    folder_path: str,
    jd_data: Dict[str, Any],
    file_types: Optional[List[str]] = None,
    run_dir: Optional[Path] = None,
    decision_handler: Optional[BatchDecisionHandler] = None,
    bot_name: str = "external_bot",
) -> Dict[str, Any]:
    """
    处理本地/临时目录中的简历文件。

    - 提供 decision_handler：执行完整评估闭环
    - 不提供 decision_handler：只做准备工作，生成 batch_input / run_meta，等待 bot 接管
    """
    if run_dir is None:
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        run_dir = PROJECT_ROOT / "runs" / f"run_{timestamp}"

    run_dir.mkdir(parents=True, exist_ok=True)

    adapter = LocalAdapter()
    scan_result = adapter.scan_folder(folder_path, file_types=file_types or DEFAULT_FILE_TYPES)
    store = CandidateStore(run_dir)
    batch_builder = BatchBuilder(jd_data)
    final_reporter = FinalReporter(run_dir)

    if scan_result["total_files"] == 0:
        run_metadata = {
            "source": "local_folder",
            "folder_path": str(Path(folder_path).resolve()),
            "scanned_file_count": 0,
            "ingest_stats": {
                "total_files": 0,
                "success_count": 0,
                "failed_count": 0,
            },
            "failure_count": 0,
            "candidate_count": 0,
            "candidate_paths": [],
            "status": "no_files",
            "decision_owner": bot_name,
            "decision_handler": "not_called",
        }
        run_meta_path = batch_builder.save_run_metadata(run_metadata, run_dir)
        return {
            "run_dir": str(run_dir),
            "scan_result": scan_result,
            "ingest_result": {
                "candidates": [],
                "stats": run_metadata["ingest_stats"],
                "failures": [],
            },
            "batch_input": None,
            "batch_input_path": None,
            "run_meta_path": str(run_meta_path),
            "candidate_paths": [],
            "final_output_path": None,
            "final_report_path": None,
            "quality_meta_path": None,
            "owner_summary_path": None,
        }

    resume_files = [_local_file_to_resume_file(file_obj) for file_obj in scan_result["files"]]
    ingest_result = ingest_resume_files(resume_files)

    candidate_paths = []
    for candidate in ingest_result["candidates"]:
        saved = store.save_candidate(candidate, candidate["id"], save_json=True, save_md=False)
        if saved.get("json_path"):
            candidate_paths.append(saved["json_path"])

    batch_input = batch_builder.build_batch_input(ingest_result["candidates"])
    batch_input_path = batch_builder.save_batch_input(batch_input, run_dir)
    batch_builder.validate_saved_batch_input(batch_input_path)

    if decision_handler is None:
        run_metadata = batch_builder.build_run_metadata(
            ingest_result["candidates"],
            extra={
                "source": "local_folder",
                "folder_path": str(Path(folder_path).resolve()),
                "scanned_file_count": scan_result["total_files"],
                "ingest_stats": ingest_result["stats"],
                "failure_count": len(ingest_result["failures"]),
                "candidate_paths": candidate_paths,
                "status": "prepared_only",
                "decision_owner": bot_name,
                "decision_handler": "not_provided",
            },
        )
        run_meta_path = batch_builder.save_run_metadata(run_metadata, run_dir)
        return {
            "run_dir": str(run_dir),
            "scan_result": scan_result,
            "ingest_result": ingest_result,
            "batch_input": batch_input,
            "batch_input_path": str(batch_input_path),
            "run_meta_path": str(run_meta_path),
            "candidate_paths": candidate_paths,
            "runner_result": None,
            "final_output_path": None,
            "final_report_path": None,
            "quality_meta_path": None,
            "owner_summary_path": None,
        }

    output_text = decision_handler(batch_input)
    runner_result = run_output_processing(batch_input, output_text)

    final_output_path = run_dir / "final_output.json"
    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(runner_result["json"], f, ensure_ascii=False, indent=2)

    quality_meta_path = run_dir / "quality_meta.json"
    with open(quality_meta_path, "w", encoding="utf-8") as f:
        json.dump(runner_result["meta"], f, ensure_ascii=False, indent=2)

    final_report_path = final_reporter.generate_final_report(
        runner_result["json"].get("top_recommendations", []),
        {
            "jd": json.dumps(batch_input["jd"], ensure_ascii=False, indent=2),
            "overall_diagnosis": runner_result["json"].get("overall_diagnosis", ""),
            "batch_advice": runner_result["json"].get("batch_advice", ""),
        },
        filename="final_report.md",
    )
    owner_summary_path = final_reporter.save_owner_summary(
        runner_result["json"].get("top_recommendations", []),
        filename="owner_summary.md",
    )

    run_metadata = batch_builder.build_run_metadata(
        ingest_result["candidates"],
        extra={
            "source": "local_folder",
            "folder_path": str(Path(folder_path).resolve()),
            "scanned_file_count": scan_result["total_files"],
            "ingest_stats": ingest_result["stats"],
            "failure_count": len(ingest_result["failures"]),
            "candidate_paths": candidate_paths,
            "final_output_path": str(final_output_path),
            "final_report_path": str(final_report_path),
            "quality_meta_path": str(quality_meta_path),
            "owner_summary_path": str(owner_summary_path),
            "status": "completed",
            "decision_owner": bot_name,
            "decision_handler": "provided",
        },
    )
    run_meta_path = batch_builder.save_run_metadata(run_metadata, run_dir)

    return {
        "run_dir": str(run_dir),
        "scan_result": scan_result,
        "ingest_result": ingest_result,
        "batch_input": batch_input,
        "batch_input_path": str(batch_input_path),
        "run_meta_path": str(run_meta_path),
        "candidate_paths": candidate_paths,
        "runner_result": runner_result,
        "final_output_path": str(final_output_path),
        "final_report_path": str(final_report_path),
        "quality_meta_path": str(quality_meta_path),
        "owner_summary_path": str(owner_summary_path),
    }


def _local_file_to_resume_file(file_obj: Any) -> Dict[str, Any]:
    resolved_path = str(Path(file_obj.file_path).resolve())
    digest = hashlib.sha1(resolved_path.encode("utf-8")).hexdigest()[:12]
    file_stem = Path(file_obj.file_path).stem
    safe_stem = "".join(ch if ch.isalnum() else "_" for ch in file_stem).strip("_") or "resume"

    return {
        "source_platform": "local",
        "file_id": f"{safe_stem}_{digest}",
        "file_name": file_obj.file_name,
        "file_path": file_obj.file_path,
        "file_url": "",
        "folder_id": str(Path(file_obj.file_path).resolve().parent),
        "channel": "local_folder",
        "mime_type": file_obj.file_type,
    }


def load_decision_handler(spec: str) -> BatchDecisionHandler:
    """从 module:function 形式动态加载 bot 提供的 decision handler。"""
    if ":" not in spec:
        raise ValueError("decision handler must be in 'module:function' format")

    module_name, func_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    handler = getattr(module, func_name)
    if not callable(handler):
        raise TypeError(f"Loaded decision handler is not callable: {spec}")
    return handler


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="处理本地/临时目录中的简历文件")
    parser.add_argument("folder_path", help="本地目录或外部已下载好的临时录路径")
    parser.add_argument("--jd", required=True, help="职位描述 JSON 文件路径")
    parser.add_argument("--types", nargs="+", default=DEFAULT_FILE_TYPES, help="文件类型（默认: pdf docx txt md）")
    parser.add_argument("--run-dir", help="运行目录（可选）")
    parser.add_argument("--decision-handler", help="外部 bot 提供的 decision handler，格式 module:function")
    parser.add_argument("--bot-name", default="external_bot", help="决策 bot 名称，默认 external_bot")

    args = parser.parse_args()

    jd_path = Path(args.jd)
    with open(jd_path, "r", encoding="utf-8") as f:
        jd_data = json.load(f)

    decision_handler = load_decision_handler(args.decision_handler) if args.decision_handler else None

    result = process_local_folder(
        folder_path=args.folder_path,
        jd_data=jd_data,
        file_types=args.types,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        decision_handler=decision_handler,
        bot_name=args.bot_name,
    )

    print(
        json.dumps(
            {
                "run_dir": result["run_dir"],
                "scan_total": result["scan_result"]["total_files"],
                "ingest_stats": result["ingest_result"]["stats"],
                "batch_input_path": result["batch_input_path"],
                "run_meta_path": result["run_meta_path"],
                "candidate_paths": result["candidate_paths"],
                "final_output_path": result["final_output_path"],
                "final_report_path": result["final_report_path"],
                "quality_meta_path": result["quality_meta_path"],
                "owner_summary_path": result["owner_summary_path"],
                "status": "completed" if result["final_output_path"] else "prepared_only",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
