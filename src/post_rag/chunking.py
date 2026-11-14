from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


SERVICE_NAMES = {
    "국제특급(EMS)": "ems",
    "EMS프리미엄": "premium",
    "국제소포": "parcel",
    "국제통상": "letter",
    "K-Packet": "kpacket",
}


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    content: str
    metadata: dict[str, str]


def _frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    _, raw, body = text.split("---", 2)
    return yaml.safe_load(raw) or {}, body.strip()


def _service_type(section_path: list[str]) -> str:
    joined = " ".join(section_path)
    for label, value in SERVICE_NAMES.items():
        if label in joined:
            return value
    return "ALL"


def _source_url(metadata: dict) -> str:
    value = metadata.get("source_url") or metadata.get("source_urls")
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and value:
        return str(next(iter(value.values())))
    return ""


def _blocks(content: str) -> list[tuple[bool, str]]:
    """섹션 본문을 (표 여부, 텍스트) 블록으로 나눈다. 연속된 `|` 줄이 하나의 표다."""
    blocks: list[tuple[bool, list[str]]] = []
    for line in content.splitlines():
        is_table = line.lstrip().startswith("|")
        if blocks and blocks[-1][0] == is_table:
            blocks[-1][1].append(line)
        else:
            blocks.append((is_table, [line]))
    return [(is_table, "\n".join(lines).strip()) for is_table, lines in blocks]


def _table_rows(table: str) -> list[str]:
    """표는 행마다 하나의 청크로 만들고 머리글을 붙인다.

    물품별 가능 여부 표를 글자 수로 자르면 한 청크에 10여 개 품목이 섞여, 특정 품목
    (예: 향수) 행의 의미가 임베딩에서 묻힌다.
    """
    lines = [line for line in table.splitlines() if line.strip()]
    if len(lines) < 3:
        return [table]
    header, rows = lines[0], [line for line in lines[1:] if not re.match(r"^\|[\s:|-]+\|?$", line)]
    return [f"{header}\n{row}" for row in rows]


def _section_parts(content: str, available: int, overlap: int) -> list[str]:
    parts: list[str] = []
    for is_table, text in _blocks(content):
        if not text:
            continue
        if is_table:
            parts.extend(_table_rows(text))
            continue
        for start in range(0, len(text), max(1, available - overlap)):
            part = text[start : start + available].strip()
            if part:
                parts.append(part)
    return parts


def split_markdown_document(path: Path, max_chars: int = 1200, overlap: int = 120) -> list[DocumentChunk]:
    metadata, body = _frontmatter(path.read_text(encoding="utf-8"))
    headings: list[str] = []
    sections: list[tuple[list[str], list[str]]] = []
    current: list[str] = []

    for line in body.splitlines():
        match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if match:
            if current:
                sections.append((list(headings), current))
            level = len(match.group(1))
            headings = headings[: level - 1] + [match.group(2).strip()]
            current = []
        else:
            current.append(line)
    if current:
        sections.append((list(headings), current))

    country_codes = metadata.get("country_codes") or ["ALL"]
    country_code = str(country_codes[0]) if isinstance(country_codes, list) else str(country_codes)
    document_id = str(metadata.get("doc_id") or path.stem)
    title = str(metadata.get("title") or path.stem)
    chunks: list[DocumentChunk] = []

    for section_index, (section_path, lines) in enumerate(sections):
        content = "\n".join(lines).strip()
        if not content:
            continue
        prefix = f"문서: {title}\n경로: {' > '.join(section_path)}\n\n"
        available = max(200, max_chars - len(prefix))
        for part_index, part in enumerate(_section_parts(content, available, overlap)):
            chunk_id = f"{document_id}:{section_index}:{part_index}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    content=prefix + part,
                    metadata={
                        "document_id": document_id,
                        "title": title,
                        "country_code": country_code,
                        "service_type": _service_type(section_path),
                        "source_type": str(metadata.get("source_type") or "문서"),
                        "source_url": _source_url(metadata),
                        "collected_at": str(metadata.get("collected_at") or ""),
                        "section_path": " > ".join(section_path),
                    },
                )
            )
    return chunks

