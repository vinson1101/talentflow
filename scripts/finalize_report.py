from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.final_reporter import FinalReporter
from core.runner import run as run_output_processing


def main() -> None:
    parser = argparse.ArgumentParser(description="将 bot 输出 finalize 为 TalentFlow 最终产物")
    parser.add_argument("run_dir", help="运行目录，例如 runs/run_2026-03-23_123456")
    parser.add_argument("model_output_path", help="bot 原始输出文件路径（JSON 文本）")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    batch_input_path = run_dir / "batch_input.json"
    if not batch_input_path.exists():
        raise FileNotFoundError(f"batch_input.json not found in run_dir: {run_dir}")

    batch_input = json.loads(batch_input_path.read_text(encoding="utf-8"))
    output_text = Path(args.model_output_path).read_text(encoding="utf-8")
    runner_result = run_output_processing(batch_input, output_text)

    final_output_path = run_dir / "final_output.json"
    final_output_path.write_text(
        json.dumps(runner_result["json"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    quality_meta_path = run_dir / "quality_meta.json"
    quality_meta_path.write_text(
        json.dumps(runner_result["meta"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    reporter = FinalReporter(run_dir)
    final_report_path = reporter.generate_final_report(
        runner_result["json"].get("top_recommendations", []),
        {
            "jd": json.dumps(batch_input.get("jd", {}), ensure_ascii=False, indent=2),
            "overall_diagnosis": runner_result["json"].get("overall_diagnosis", ""),
            "batch_advice": runner_result["json"].get("batch_advice", ""),
        },
        filename="final_report.md",
    )
    owner_summary_path = reporter.save_owner_summary(
        runner_result["json"].get("top_recommendations", []),
        jd_title=batch_input.get("jd", {}).get("title", "待确认") if isinstance(batch_input.get("jd"), dict) else "待确认",
        jd_location=batch_input.get("jd", {}).get("location", "待确认") if isinstance(batch_input.get("jd"), dict) else "待确认",
        jd_salary=batch_input.get("jd", {}).get("salary_range", "待确认") if isinstance(batch_input.get("jd"), dict) else "待确认",
        filename="owner_summary.md",
    )

    print(json.dumps({
        "ok": True,
        "run_dir": str(run_dir),
        "final_output_path": str(final_output_path),
        "quality_meta_path": str(quality_meta_path),
        "final_report_path": str(final_report_path),
        "owner_summary_path": str(owner_summary_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
