"""
模型评估模块

功能：
- 读取冻结的 system prompt
- 调用真实模型接口执行 batch 评估
- 返回模型原始输出文本

注意：
- 不在此模块中做 schema 修复
- 不在此模块中做排序修复
- 不在此模块中做报告渲染或文件落盘
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import json
import os

import requests


DEFAULT_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "configs" / "system_prompt.md"
DEFAULT_OPENCLAW_CONFIG_PATH = Path(__file__).resolve().parent.parent / "openclaw.json"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_RESPONSE_FORMAT = "json_object"


@dataclass
class EvaluatorConfig:
    api_key: str
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    response_format: str = DEFAULT_RESPONSE_FORMAT
    base_url: str = DEFAULT_BASE_URL
    system_prompt_path: Path = DEFAULT_SYSTEM_PROMPT_PATH
    timeout: int = 120


def load_evaluator_config(
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    response_format: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    system_prompt_path: Optional[Path] = None,
    timeout: Optional[int] = None,
) -> EvaluatorConfig:
    """从参数、openclaw.json 和环境变量加载默认 fallback evaluator 配置。"""
    file_config = _load_openclaw_config()

    resolved_api_key = (
        api_key
        or _get_first_non_empty(file_config, "api_key", "openai_api_key", "llm_api_key")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("LLM_API_KEY")
    )
    if not resolved_api_key:
        raise ValueError("Missing evaluator API key: set openclaw.json api_key/openai_api_key or OPENAI_API_KEY/LLM_API_KEY")

    resolved_model = (
        model
        or _get_first_non_empty(file_config, "model", "ai_model", "openai_model")
        or os.environ.get("AI_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or DEFAULT_MODEL
    )
    resolved_temperature = (
        temperature
        if temperature is not None
        else float(
            _get_first_non_empty(file_config, "temperature", "ai_temperature")
            or os.environ.get("AI_TEMPERATURE", DEFAULT_TEMPERATURE)
        )
    )
    resolved_response_format = (
        response_format
        or _get_first_non_empty(file_config, "response_format", "ai_response_format")
        or os.environ.get("AI_RESPONSE_FORMAT")
        or DEFAULT_RESPONSE_FORMAT
    )
    resolved_base_url = (
        base_url
        or _get_first_non_empty(file_config, "base_url", "openai_base_url", "llm_base_url")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or DEFAULT_BASE_URL
    )
    resolved_timeout = (
        timeout
        if timeout is not None
        else int(_get_first_non_empty(file_config, "timeout", "ai_timeout") or os.environ.get("AI_TIMEOUT", 120))
    )
    resolved_prompt_path = Path(
        system_prompt_path
        or _get_first_non_empty(file_config, "system_prompt_path")
        or os.environ.get("SYSTEM_PROMPT_PATH")
        or DEFAULT_SYSTEM_PROMPT_PATH
    )

    return EvaluatorConfig(
        api_key=resolved_api_key,
        model=resolved_model,
        temperature=resolved_temperature,
        response_format=resolved_response_format,
        base_url=resolved_base_url.rstrip("/"),
        system_prompt_path=resolved_prompt_path,
        timeout=resolved_timeout,
    )


def _load_openclaw_config() -> Dict[str, Any]:
    if not DEFAULT_OPENCLAW_CONFIG_PATH.exists():
        return {}

    try:
        data = json.loads(DEFAULT_OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Invalid openclaw.json: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Invalid openclaw.json: root must be an object")

    return data


def _get_first_non_empty(source: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def evaluate_batch(
    batch_input: Dict[str, Any],
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    response_format: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    system_prompt_path: Optional[Path] = None,
    timeout: Optional[int] = None,
    request_post: Optional[Callable[..., requests.Response]] = None,
) -> str:
    """
    调用真实模型评估 batch_input，并返回模型原始输出文本。
    """
    config = load_evaluator_config(
        model=model,
        temperature=temperature,
        response_format=response_format,
        base_url=base_url,
        api_key=api_key,
        system_prompt_path=system_prompt_path,
        timeout=timeout,
    )

    system_prompt = _load_system_prompt(config.system_prompt_path)
    payload = _build_chat_payload(batch_input, system_prompt, config)
    post = request_post or requests.post

    response = post(
        f"{config.base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=config.timeout,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"Evaluator request failed: {response.status_code} {response.text[:500]}") from exc

    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError(f"Evaluator response is not valid JSON: {response.text[:500]}") from exc

    try:
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"Evaluator response missing choices/message/content: {json.dumps(data, ensure_ascii=False)[:1000]}") from exc


def _load_system_prompt(system_prompt_path: Path) -> str:
    if not system_prompt_path.exists():
        raise FileNotFoundError(f"System prompt file not found: {system_prompt_path}")
    return system_prompt_path.read_text(encoding="utf-8")


def _build_chat_payload(
    batch_input: Dict[str, Any],
    system_prompt: str,
    config: EvaluatorConfig,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": config.model,
        "temperature": config.temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(batch_input, ensure_ascii=False)},
        ],
    }

    if config.response_format == "json_object":
        payload["response_format"] = {"type": "json_object"}
    else:
        payload["response_format"] = {"type": config.response_format}

    return payload
