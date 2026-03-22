"""
批量输入构建模块

功能：
- 从标准化候选人对象构建符合 input.schema.json 的 payload
- 独立保存运行态元数据，不污染提交给模型的 schema payload
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class BatchBuilder:
    """批量输入构建器"""

    def __init__(self, jd: Dict[str, Any], schema_path: Optional[Path] = None):
        """
        Args:
            jd: 符合 input schema 的 jd object
            schema_path: input schema 文件路径，默认指向 configs/input.schema.json
        """
        if not isinstance(jd, dict):
            raise TypeError("jd must be an object matching configs/input.schema.json")
        self.jd = jd
        self.schema_path = schema_path or Path(__file__).resolve().parent.parent / "configs" / "input.schema.json"

    def build_batch_input(
        self,
        candidates: List[Dict[str, Any]],
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """构建严格符合 input schema 的 payload。"""
        payload: Dict[str, Any] = {
            "jd": self.jd,
            "candidates": [self._normalize_candidate(candidate) for candidate in candidates],
        }

        if meta:
            payload["meta"] = meta

        return payload

    def build_run_metadata(
        self,
        candidates: List[Dict[str, Any]],
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """构建与 schema payload 分离的运行元数据。"""
        metadata = {
            "candidate_count": len(candidates),
            "generated_at": datetime.now().isoformat(),
        }
        if extra:
            metadata.update(extra)
        return metadata

    def save_batch_input(self, batch_input: Dict[str, Any], run_dir: Path):
        """保存 schema payload 到文件。"""
        batch_file = run_dir / "batch_input.json"
        with open(batch_file, "w", encoding="utf-8") as f:
            json.dump(batch_input, f, ensure_ascii=False, indent=2)
        return batch_file

    def validate_batch_input(self, batch_input: Dict[str, Any]) -> None:
        """使用 configs/input.schema.json 做运行时校验。"""
        schema = self._load_schema()
        self._validate_schema_node(batch_input, schema, path="$")

    def validate_saved_batch_input(self, batch_file: Path) -> None:
        """校验已落盘的 batch_input.json。"""
        with open(batch_file, "r", encoding="utf-8") as f:
            batch_input = json.load(f)
        self.validate_batch_input(batch_input)

    def save_run_metadata(self, run_metadata: Dict[str, Any], run_dir: Path):
        """保存独立运行元数据。"""
        metadata_file = run_dir / "run_meta.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(run_metadata, f, ensure_ascii=False, indent=2)
        return metadata_file

    def load_batch_input(self, run_dir: Path) -> Dict[str, Any]:
        """从文件加载 schema payload。"""
        batch_file = run_dir / "batch_input.json"
        with open(batch_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _normalize_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {
            "id": str(candidate["id"]),
            "name": str(candidate["name"]),
            "raw_resume": str(candidate["raw_resume"]),
        }

        for optional_key in [
            "current_salary",
            "expected_salary",
            "current_status",
            "location",
            "extra_info",
            "source",
            "ingestion_meta",
        ]:
            value = candidate.get(optional_key)
            if value is not None:
                normalized[optional_key] = value

        return normalized

    def _load_schema(self) -> Dict[str, Any]:
        with open(self.schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _validate_schema_node(self, value: Any, schema: Dict[str, Any], path: str) -> None:
        schema_type = schema.get("type")

        if schema_type == "object":
            if not isinstance(value, dict):
                raise ValueError(f"Invalid batch_input at {path}: expected object")

            properties = schema.get("properties", {})
            required = schema.get("required", [])

            for key in required:
                if key not in value:
                    raise ValueError(f"Invalid batch_input at {path}: missing required field '{key}'")

            if schema.get("additionalProperties") is False:
                extra_keys = set(value.keys()) - set(properties.keys())
                if extra_keys:
                    extras = ", ".join(sorted(extra_keys))
                    raise ValueError(f"Invalid batch_input at {path}: unexpected fields {extras}")

            for key, child_schema in properties.items():
                if key in value:
                    self._validate_schema_node(value[key], child_schema, f"{path}.{key}")
            return

        if schema_type == "array":
            if not isinstance(value, list):
                raise ValueError(f"Invalid batch_input at {path}: expected array")

            min_items = schema.get("minItems")
            max_items = schema.get("maxItems")
            if min_items is not None and len(value) < min_items:
                raise ValueError(f"Invalid batch_input at {path}: expected at least {min_items} items")
            if max_items is not None and len(value) > max_items:
                raise ValueError(f"Invalid batch_input at {path}: expected at most {max_items} items")

            item_schema = schema.get("items")
            if item_schema:
                for index, item in enumerate(value):
                    self._validate_schema_node(item, item_schema, f"{path}[{index}]")
            return

        if schema_type == "string":
            if not isinstance(value, str):
                raise ValueError(f"Invalid batch_input at {path}: expected string")
            min_length = schema.get("minLength")
            if min_length is not None and len(value) < min_length:
                raise ValueError(f"Invalid batch_input at {path}: string length must be >= {min_length}")
            enum = schema.get("enum")
            if enum is not None and value not in enum:
                raise ValueError(f"Invalid batch_input at {path}: expected one of {enum}")
            return

        if schema_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"Invalid batch_input at {path}: expected number")
            return

        if schema_type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"Invalid batch_input at {path}: expected boolean")
            return

        if schema_type is None:
            return

        raise ValueError(f"Invalid batch_input at {path}: unsupported schema type '{schema_type}'")
