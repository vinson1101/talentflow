"""
用 HuntMind 身份注入 evaluator，运行 TalentFlow 本地简历处理。

这个入口用于你当前的“真实简历 / 近生产环境”测试：
- 仍然调用真实模型 API
- 但走 external 模式
- 由外部注入 evaluator
- 不再使用 TalentFlow 的 fallback evaluator

推荐环境变量：
- HUNTMIND_API_KEY
- HUNTMIND_MODEL
- HUNTMIND_BASE_URL
- HUNTMIND_SYSTEM_PROMPT_PATH
- HUNTMIND_TEMPERATURE
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.process_local_folder import process_local_folder


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_SYSTEM_PROMPT_PATH = PROJECT_ROOT / "configs" / "system_prompt.md"


class HuntMindInjectedEvaluator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        system_prompt_path: Path,
        temperature: float,
        timeout: int = 120,
    ):
        if not api_key:
            raise ValueError("Missing HuntMind API key. Set HUNTMIND_API_KEY or pass --api-key.")
        if not system_prompt_path.exists():
            raise FileNotFoundError(f"System prompt file not found: {system_prompt_path}")

        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.system_prompt_path = system_prompt_path
        self.temperature = temperature
        self.timeout = timeout

    def __call__(self, batch_input: Dict[str, Any]) -> str:
        system_prompt = self.system_prompt_path.read_text(encoding="utf-8")
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(batch_input, ensure_ascii=False)},
            ],
        }

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"HuntMind evaluator request failed: {response.status_code} {response.text[:500]}") from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError(f"HuntMind evaluator response missing choices/message/content: {json.dumps(data, ensure_ascii=False)[:1000]}") from exc


def build_huntmind_evaluator(
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    system_prompt_path: Optional[str] = None,
    temperature: Optional[float] = None,
    timeout: int = 120,
) -> HuntMindInjectedEvaluator:
    resolved_api_key = api_key or os.environ.get("HUNTMIND_API_KEY") or os.environ.get("OPENAI_API_KEY")
    resolved_model = model or os.environ.get("HUNTMIND_MODEL") or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
    resolved_base_url = base_url or os.environ.get("HUNTMIND_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL
    resolved_temperature = float(
        temperature
        if temperature is not None
        else os.environ.get("HUNTMIND_TEMPERATURE", DEFAULT_TEMPERATURE)
    )
    resolved_prompt_path = Path(
        system_prompt_path
        or os.environ.get("HUNTMIND_SYSTEM_PROMPT_PATH")
        or DEFAULT_SYSTEM_PROMPT_PATH
    )

    return HuntMindInjectedEvaluator(
        api_key=resolved_api_key,
        model=resolved_model,
        base_url=resolved_base_url,
        system_prompt_path=resolved_prompt_path,
        temperature=resolved_temperature,
        timeout=timeout,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="用 HuntMind 注入 evaluator 跑本地简历处理")
    parser.add_argument("folder_path", help="本地简历目录")
    parser.add_argument("--jd", required=True, help="职位描述 JSON 文件路径")
    parser.add_argument("--types", nargs="+", default=["pdf", "docx", "txt", "md"], help="文件类型")
    parser.add_argument("--run-dir", help="运行目录（可选）")
    parser.add_argument("--api-key", help="覆盖 HUNTMIND_API_KEY")
    parser.add_argument("--model", help="覆盖 HUNTMIND_MODEL")
    parser.add_argument("--base-url", help="覆盖 HUNTMIND_BASE_URL")
    parser.add_argument("--system-prompt", help="覆盖 HUNTMIND_SYSTEM_PROMPT_PATH")
    parser.add_argument("--temperature", type=float, help="覆盖 HUNTMIND_TEMPERATURE")

    args = parser.parse_args()

    with open(Path(args.jd), "r", encoding="utf-8") as f:
        jd_data = json.load(f)

    evaluator = build_huntmind_evaluator(
        api_key=args.api_key,
        model=args.model,
        base_url=args.base_url,
        system_prompt_path=args.system_prompt,
        temperature=args.temperature,
    )

    result = process_local_folder(
        folder_path=args.folder_path,
        jd_data=jd_data,
        file_types=args.types,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        evaluator=evaluator,
        run_mode="external",
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
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
