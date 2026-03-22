from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.runner import evaluate_output_quality


def main() -> None:
    parser = argparse.ArgumentParser(description="对 final_output.json 执行质量门禁检查")
    parser.add_argument("final_output_path", help="final_output.json 文件路径")
    parser.add_argument("--min-score", type=int, default=70, help="最低质量分阈值，默认 70")
    args = parser.parse_args()

    final_output_path = Path(args.final_output_path)
    if not final_output_path.exists():
        raise FileNotFoundError(f"final_output file not found: {final_output_path}")

    data = json.loads(final_output_path.read_text(encoding="utf-8"))
    quality = evaluate_output_quality(data)
    passed = quality.get("quality_score", 0) >= args.min_score and quality.get("quality_flag") not in {"invalid"}

    print(json.dumps({
        "ok": passed,
        "min_score": args.min_score,
        "quality": quality,
    }, ensure_ascii=False, indent=2))

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
