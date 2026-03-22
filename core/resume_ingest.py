"""
简历解析与候选人标准化模块

功能：
- 从统一文件对象中提取文本
- 标准化为面向决策层的 candidate 对象
- 记录失败项并输出统计信息
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import re

from docx import Document
from pypdf import PdfReader


SUPPORTED_TEXT_EXTENSIONS = {"txt", "md"}
SUPPORTED_WORD_EXTENSIONS = {"docx"}
SUPPORTED_PDF_EXTENSIONS = {"pdf"}
MAX_RAW_RESUME_LENGTH = 30000


def ingest_resume_files(
    resume_files: List[Any],
    extract_contact: bool = False,
) -> Dict[str, Any]:
    """
    批量解析简历文件并输出符合决策层输入契约的 candidates[]。

    Args:
        resume_files: 统一文件对象列表。对象应尽量提供：
            - source_platform
            - file_id
            - file_name
            - file_path
            - file_bytes
            - file_url
            - folder_id
            - channel
            - mime_type
        extract_contact: 预留参数，当前版本不做复杂字段抽取。

    Returns:
        {
            "candidates": [...],
            "stats": {...},
            "failures": [...]
        }
    """
    del extract_contact  # 当前版本只做稳定入模，不做复杂抽取

    candidates: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []

    for file_obj in resume_files:
        file_meta = _extract_file_meta(file_obj)

        try:
            raw_resume, parse_method = _extract_resume_text(file_obj, file_meta)
            raw_resume, is_truncated = _normalize_resume_text(raw_resume)

            if not raw_resume:
                raise ValueError("resume text empty")

            candidate = _build_candidate(file_meta, raw_resume, parse_method, is_truncated)
            candidates.append(candidate)
        except Exception as exc:
            failures.append(
                {
                    "file_id": file_meta["file_id"],
                    "file_name": file_meta["file_name"],
                    "status": "failed",
                    "reason": str(exc),
                }
            )

    return {
        "candidates": candidates,
        "stats": {
            "total_files": len(resume_files),
            "success_count": len(candidates),
            "failed_count": len(failures),
        },
        "failures": failures,
    }


def _extract_file_meta(file_obj: Any) -> Dict[str, str]:
    file_name = _get_attr(file_obj, "file_name") or _get_attr(file_obj, "name") or "unknown_resume"
    file_path = _get_attr(file_obj, "file_path") or ""
    file_id = _get_attr(file_obj, "file_id") or _stable_file_id(file_name, file_path)

    return {
        "source_platform": _get_attr(file_obj, "source_platform") or "local",
        "file_id": str(file_id),
        "file_name": str(file_name),
        "file_path": str(file_path),
        "file_url": str(_get_attr(file_obj, "file_url") or ""),
        "folder_id": str(_get_attr(file_obj, "folder_id") or ""),
        "channel": str(_get_attr(file_obj, "channel") or ""),
        "mime_type": str(_get_attr(file_obj, "mime_type") or ""),
    }


def _build_candidate(
    file_meta: Dict[str, str],
    raw_resume: str,
    parse_method: str,
    is_truncated: bool,
) -> Dict[str, Any]:
    candidate_id = f"{file_meta['source_platform']}_{file_meta['file_id']}"
    name = _extract_name(file_meta["file_name"], raw_resume)

    source = {
        "platform": file_meta["source_platform"],
        "channel": file_meta["channel"],
        "file_id": file_meta["file_id"],
        "file_name": file_meta["file_name"],
        "folder_id": file_meta["folder_id"],
        "file_url": file_meta["file_url"],
    }
    source = {key: value for key, value in source.items() if value}

    candidate: Dict[str, Any] = {
        "id": candidate_id,
        "name": name,
        "raw_resume": raw_resume,
        "extra_info": f"source={file_meta['source_platform']}; file_name={file_meta['file_name']}",
        "ingestion_meta": {
            "parse_status": "success",
            "parse_method": parse_method,
            "text_length": len(raw_resume),
            "is_truncated": is_truncated,
        },
    }

    if source:
        candidate["source"] = source

    return candidate


def _extract_resume_text(file_obj: Any, file_meta: Dict[str, str]) -> Tuple[str, str]:
    file_name = file_meta["file_name"]
    file_path = file_meta["file_path"]
    extension = Path(file_name).suffix.lower().lstrip(".")

    file_bytes = _get_attr(file_obj, "file_bytes")
    if isinstance(file_bytes, str):
        file_bytes = file_bytes.encode("utf-8")

    if extension in SUPPORTED_TEXT_EXTENSIONS:
        if file_bytes is not None:
            return _decode_text_bytes(file_bytes), "text_bytes"
        if file_path:
            return Path(file_path).read_text(encoding="utf-8", errors="ignore"), "text_file"

    if extension in SUPPORTED_WORD_EXTENSIONS:
        if not file_path:
            raise ValueError("docx file_path missing")
        return _read_docx_text(Path(file_path)), "docx"

    if extension in SUPPORTED_PDF_EXTENSIONS:
        if file_path:
            return _read_pdf_text(Path(file_path)), "pdf"
        raise ValueError("pdf file_path missing")

    if file_bytes is not None:
        return _decode_text_bytes(file_bytes), "bytes_fallback"

    if file_path:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore"), "file_fallback"

    raise ValueError(f"unsupported resume file: {file_name}")


def _normalize_resume_text(raw_text: str) -> Tuple[str, bool]:
    text = raw_text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    is_truncated = len(text) > MAX_RAW_RESUME_LENGTH
    if is_truncated:
        text = text[:MAX_RAW_RESUME_LENGTH].rstrip()

    return text, is_truncated


def _extract_name(file_name: str, raw_resume: str) -> str:
    stem = Path(file_name).stem.strip()
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    if stem:
        return stem

    first_line = next((line.strip() for line in raw_resume.splitlines() if line.strip()), "")
    return first_line[:50] if first_line else "未知候选人"


def _read_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    texts = []
    for page in reader.pages:
        texts.append(page.extract_text() or "")
    return "\n".join(texts)


def _read_docx_text(path: Path) -> str:
    document = Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _decode_text_bytes(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("unable to decode text bytes")


def _get_attr(file_obj: Any, key: str) -> Optional[Any]:
    if isinstance(file_obj, dict):
        return file_obj.get(key)
    return getattr(file_obj, key, None)


def _stable_file_id(file_name: str, file_path: str) -> str:
    base = file_path or file_name or "unknown_resume"
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_")
    return normalized[:80] or "unknown_resume"
