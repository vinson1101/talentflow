from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.runner import run as run_output_processing


def main() -> None:
    parser = argparse.ArgumentParser(description="校验并清洗 HuntMind / bot 输出结果")
    parser.add_argument("batch_input_path", help="batch_input.json 文件路径")
    parser.add_argument("model_output_path", help="bot 原始输出文件路径（JSON 文本）")
    parser.add_argument("--write-final-output", help="可选：将清洗后的 final_output.json 写到指定路径")
    parser.add_argument("--write-quality-meta", help="可选：将 quality_meta.json 写到指定路径")
    args = parser.parse_args()

    batch_input = json.loads(Path(args.batch_input_path).read_text(encoding="utf-8"))
    output_text = Path(args.model_output_path).read_text(encoding="utf-8")

    result = run_output_processing(batch_input, output_text)

    if args.write_final_output:
        Path(args.write_final_output).write_text(
            json.dumps(result["json"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.write_quality_meta:
        Path(args.write_quality_meta).write_text(
            json.dumps(result["meta"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(json.dumps({
        "ok": True,
        "candidate_count": len(result["json"].get("top_recommendations", [])),
        "quality": result["meta"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
