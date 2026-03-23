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

NAME_LABEL_PATTERNS = [
    re.compile(r"(?:^|\n)\s*姓名\s*[:：]?\s*([^\n]{1,40})"),
    re.compile(r"(?:^|\n)\s*(?:Name|NAME|name)\s*[:：]?\s*([^\n]{1,40})"),
    re.compile(r"(?:^|\n)\s*(?:候选人|应聘者)\s*[:：]?\s*([^\n]{1,40})"),
]
NAME_STOPWORDS = {
    "个人简历",
    "简历",
    "求职简历",
    "应聘简历",
    "个人信息",
    "基本信息",
    "候选人",
    "应聘者",
    "姓名",
    "name",
    "resume",
    "cv",
    "about me",
    "profile",
    "summary",
    "experience",
    "education",
    "skills",
}
NAME_REJECT_KEYWORDS = (
    "简历",
    "求职",
    "应聘",
    "岗位",
    "职位",
    "产品经理",
    "高级产品经理",
    "项目经理",
    "运营经理",
    "销售经理",
    "研发工程师",
    "工程师",
    "总监",
    "经理",
    "工作经历",
    "教育经历",
    "项目经历",
    "自我评价",
    "个人优势",
    "求职意向",
    "基本信息",
    "联系方式",
    "电话",
    "手机",
    "邮箱",
    "微信",
    "现居",
    "地址",
    "本科",
    "硕士",
    "博士",
    "大学",
    "学院",
    "学校",
    "科技大学",
    "about",
    "experience",
    "education",
    "skills",
    "profile",
    "summary",
    "requirement",
    "requirements",
)
SECTION_HEADING_WORDS = {
    "about me",
    "about",
    "experience",
    "education",
    "skills",
    "profile",
    "summary",
    "objective",
    "projects",
    "project",
    "requirements",
    "requirement",
}
CHINESE_SINGLE_SURNAMES = {
    "赵","钱","孙","李","周","吴","郑","王","冯","陈","褚","卫","蒋","沈","韩","杨","朱","秦","尤","许","何","吕","施","张","孔","曹","严","华","金","魏","陶","姜","戚","谢","邹","喻","柏","水","窦","章","云","苏","潘","葛","奚","范","彭","郎","鲁","韦","昌","马","苗","凤","花","方","俞","任","袁","柳","酆","鲍","史","唐","费","廉","岑","薛","雷","贺","倪","汤","滕","殷","罗","毕","郝","邬","安","常","乐","于","时","傅","皮","卞","齐","康","伍","余","元","卜","顾","孟","平","黄","和","穆","萧","尹","姚","邵","湛","汪","祁","毛","禹","狄","米","贝","明","臧","计","伏","成","戴","谈","宋","茅","庞","熊","纪","舒","屈","项","祝","董","梁","杜","阮","蓝","闵","席","季","麻","强","贾","路","娄","危","江","童","颜","郭","梅","盛","林","刁","钟","徐","邱","骆","高","夏","蔡","田","樊","胡","凌","霍","虞","万","支","柯","昝","管","卢","莫","经","房","裘","缪","干","解","应","宗","丁","宣","贲","邓","郁","单","杭","洪","包","诸","左","石","崔","吉","钮","龚","程","嵇","邢","滑","裴","陆","荣","翁","荀","羊","於","惠","甄","曲","家","封","芮","羿","储","靳","汲","邴","糜","松","井","段","富","巫","乌","焦","巴","弓","牧","隗","山","谷","车","侯","宓","蓬","全","郗","班","仰","秋","仲","伊","宫","宁","仇","栾","暴","甘","斜","厉","戎","祖","武","符","刘","景","詹","束","龙","叶","幸","司","韶","郜","黎","蓟","薄","印","宿","白","怀","蒲","邰","从","鄂","索","咸","籍","赖","卓","蔺","屠","蒙","池","乔","阴","鬱","胥","能","苍","双","闻","莘","党","翟","谭","贡","劳","逄","姬","申","扶","堵","冉","宰","郦","雍","却","璩","桑","桂","濮","牛","寿","通","边","扈","燕","冀","郏","浦","尚","农","温","别","庄","晏","柴","瞿","阎","充","慕","连","茹","习","宦","艾","鱼","容","向","古","易","慎","戈","廖","庾","终","暨","居","衡","步","都","耿","满","弘","匡","国","文","寇","广","禄","阙","东","欧","殳","沃","利","蔚","越","夔","隆","师","巩","厍","聂","晁","勾","敖","融","冷","訾","辛","阚","那","简","饶","空","曾","毋","沙","乜","养","鞠","须","丰","巢","关","蒯","相","查","后","荆","红","游","竺","权","逯","盖","益","桓","公","仉","督","岳","帅","缑","亢","况","郈","有","琴","归","海","晋","楚","闫","法","佘","福",
}
CHINESE_DOUBLE_SURNAMES = {
    "欧阳","太史","端木","上官","司马","东方","独孤","南宫","万俟","闻人","夏侯","诸葛","尉迟","公羊","赫连","澹台","皇甫","宗政","濮阳","公冶","太叔","申屠","公孙","慕容","仲孙","钟离","长孙","宇文","司徒","鲜于","司空","闾丘","子车","亓官","司寇","巫马","公西","颛孙","壤驷","公良","漆雕","乐正","宰父","谷梁","拓跋","夹谷","轩辕","令狐","段干","百里","呼延","东郭","南门","羊舌","微生","梁丘","左丘","东门","西门","南荣",
}


def ingest_resume_files(
    resume_files: List[Any],
    extract_contact: bool = False,
) -> Dict[str, Any]:
    del extract_contact

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
    name, name_source = _extract_name(file_meta["file_name"], raw_resume)

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
            "name_source": name_source,
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
    text = text.replace("", " ")
    text = text.strip()

    is_truncated = len(text) > MAX_RAW_RESUME_LENGTH
    if is_truncated:
        text = text[:MAX_RAW_RESUME_LENGTH].rstrip()

    return text, is_truncated


def _extract_name(file_name: str, raw_resume: str) -> Tuple[str, str]:
    explicit_content_name = _extract_explicit_name_from_resume(raw_resume)
    if explicit_content_name:
        return explicit_content_name, "resume_content_explicit"

    file_name_name = _extract_name_from_file_name(file_name)
    if file_name_name:
        return file_name_name, "file_name_fallback"

    first_line = next((line.strip() for line in raw_resume.splitlines() if line.strip()), "")
    first_line = _sanitize_name_candidate(first_line[:50])
    if _looks_like_high_confidence_name(first_line):
        return first_line, "first_line_fallback"

    return "未知候选人", "unknown"


def _extract_explicit_name_from_resume(raw_resume: str) -> Optional[str]:
    lines = [_normalize_line(line) for line in raw_resume.splitlines()]
    lines = [line for line in lines if line][:20]
    if not lines:
        return None

    text_window = "\n".join(lines)

    for pattern in NAME_LABEL_PATTERNS:
        for match in pattern.finditer(text_window):
            for candidate in _candidate_name_tokens_from_line(match.group(1)):
                if _looks_like_high_confidence_name(candidate):
                    return candidate

    return None


def _extract_name_from_file_name(file_name: str) -> Optional[str]:
    stem = Path(file_name).stem.strip()
    if not stem:
        return None

    for token in reversed(re.split(r"[_\-\s]+", stem)):
        candidate = _sanitize_name_candidate(token)
        if _looks_like_resume_name(candidate):
            return candidate

    for candidate in _candidate_name_tokens_from_line(stem):
        if _looks_like_resume_name(candidate):
            return candidate

    return None


def _candidate_name_tokens_from_line(line: str) -> List[str]:
    normalized = _sanitize_name_candidate(line)
    if not normalized:
        return []

    candidates: List[str] = [normalized]

    label_stripped = re.sub(r"^(姓名|Name|NAME|name|候选人|应聘者)\s*[:：]?\s*", "", normalized).strip()
    if label_stripped and label_stripped not in candidates:
        candidates.append(label_stripped)

    first_segment = re.split(r"[|｜/\\,，;；·•]", label_stripped, maxsplit=1)[0].strip()
    if first_segment and first_segment not in candidates:
        candidates.append(first_segment)

    first_token = re.split(r"\s+", label_stripped, maxsplit=1)[0].strip()
    if first_token and first_token not in candidates:
        candidates.append(first_token)

    chinese_match = re.match(r"^([\u4e00-\u9fff·]{2,8})(?:\s|$|[|｜/\\,，;；])", label_stripped)
    if chinese_match:
        candidates.append(chinese_match.group(1))

    results: List[str] = []
    for candidate in candidates:
        cleaned = _sanitize_name_candidate(candidate)
        if cleaned and cleaned not in results:
            results.append(cleaned)
    return results


def _normalize_line(line: str) -> str:
    cleaned = line.strip()
    cleaned = cleaned.replace("\u3000", " ")
    cleaned = cleaned.replace("", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _sanitize_name_candidate(value: str) -> str:
    text = value.strip()
    text = text.strip(" |｜/\\,，;；:：-_")
    text = re.sub(r"^(姓名|Name|NAME|name|候选人|应聘者)\s*[:：]?\s*", "", text).strip()
    text = re.sub(r"\s+", " ", text)

    text = re.split(
        r"(?:\b(?:男|女|女士|先生|小姐)\b|手机|电话|邮箱|微信|现居|住址|地址|出生年月|年龄|工作年限|教育经历|工作经历|求职意向)",
        text,
        maxsplit=1,
    )[0].strip()

    text = re.sub(r"(?:先生|女士|小姐)$", "", text).strip()
    text = text.strip(" |｜/\\,，;；:：-_")
    return text


def _looks_like_resume_name(value: str) -> bool:
    text = _sanitize_name_candidate(value)
    if not text:
        return False

    lowered = text.lower()
    if lowered in NAME_STOPWORDS or lowered in SECTION_HEADING_WORDS:
        return False

    if any(keyword.lower() in lowered for keyword in NAME_REJECT_KEYWORDS):
        return False

    if re.search(r"\d", text):
        return False

    if "@" in text or re.search(r"(?:\+?86)?1[3-9]\d{9}", text):
        return False

    if len(text) > 30:
        return False

    if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text):
        return True

    if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,29}", text):
        parts = [part for part in re.split(r"\s+", text) if part]
        if len(parts) == 1:
            return lowered not in SECTION_HEADING_WORDS
        return all(part.lower() not in SECTION_HEADING_WORDS for part in parts)

    return False


def _looks_like_high_confidence_name(value: str) -> bool:
    text = _sanitize_name_candidate(value)
    if not _looks_like_resume_name(text):
        return False

    if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text):
        if len(text) >= 2 and text[:2] in CHINESE_DOUBLE_SURNAMES:
            return True
        return text[0] in CHINESE_SINGLE_SURNAMES

    if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,29}", text):
        parts = [part for part in re.split(r"\s+", text) if part]
        if len(parts) < 2:
            return False
        return all(part.lower() not in SECTION_HEADING_WORDS for part in parts)

    return False


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
