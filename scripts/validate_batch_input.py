from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.batch_builder import BatchBuilder


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 TalentFlow 生成的 batch_input.json 是否符合 input schema")
    parser.add_argument("batch_input_path", help="batch_input.json 文件路径")
    parser.add_argument("--schema", help="可选：自定义 input schema 路径")
    args = parser.parse_args()

    batch_input_path = Path(args.batch_input_path)
    if not batch_input_path.exists():
        raise FileNotFoundError(f"batch_input file not found: {batch_input_path}")

    data = json.loads(batch_input_path.read_text(encoding="utf-8"))
    jd = data.get("jd")
    builder = BatchBuilder(jd=jd, schema_path=Path(args.schema) if args.schema else None)
    builder.validate_batch_input(data)

    print(json.dumps({
        "ok": True,
        "batch_input_path": str(batch_input_path),
        "candidate_count": len(data.get("candidates", [])),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
