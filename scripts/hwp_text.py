"""HWP 5.x 파일에서 본문 텍스트만 뽑는 최소 파서(표는 셀 순서대로 줄 단위로 나열됨)."""

from __future__ import annotations

import struct
import sys
import zlib

import olefile

HWPTAG_PARA_TEXT = 67
# 8바이트(16byte 확장) 인라인/확장 컨트롤 문자
_EXTENDED_CTRL = {1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}


def _para_text(raw: bytes) -> str:
    out, j = [], 0
    while j + 1 < len(raw):
        c = struct.unpack_from("<H", raw, j)[0]
        if c < 32:
            if c in _EXTENDED_CTRL:
                j += 16
                continue
            if c == 9:  # 탭
                out.append("\t")
                j += 16
                continue
            if c in (10, 13):
                out.append("\n")
            j += 2
            continue
        out.append(chr(c))
        j += 2
    return "".join(out).strip()


def hwpx_text(path: str) -> str:
    """HWPX(zip+XML): 문단(<hp:p>)마다 <hp:t> 텍스트를 이어 붙인다."""
    import re
    import zipfile

    paras: list[str] = []
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml$", n))
        for n in names:
            xml = z.read(n).decode("utf-8")
            for p in re.findall(r"<hp:p\b.*?</hp:p>", xml, re.S):
                # 표 안 문단은 바깥 문단에도 중복 포함되므로 가장 안쪽 문단만 사용
                if "<hp:p " in p[5:]:
                    continue
                text = "".join(re.findall(r"<hp:t[^>]*>(.*?)</hp:t>", p, re.S))
                text = re.sub(r"<[^>]+>", "", text).strip()
                if text:
                    paras.append(text)
    return "\n".join(paras)


def pdf_text(path: str) -> str:
    from pypdf import PdfReader

    return "\n".join((page.extract_text() or "").strip() for page in PdfReader(path).pages).strip()


def any_text(path: str) -> str:
    """파일 시그니처로 HWP/HWPX/PDF를 판별해 텍스트를 뽑는다."""
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic.startswith(b"PK"):
        return hwpx_text(path)
    if magic.startswith(b"%PDF"):
        return pdf_text(path)
    return hwp_text(path)


def hwp_text(path: str) -> str:
    ole = olefile.OleFileIO(path)
    compressed = bool(ole.openstream("FileHeader").read()[36] & 1)
    sections = sorted((e for e in ole.listdir() if e[0] == "BodyText"), key=lambda e: int(e[1][7:]))
    paras: list[str] = []
    for sec in sections:
        data = ole.openstream(sec).read()
        if compressed:
            data = zlib.decompress(data, -15)
        i = 0
        while i + 4 <= len(data):
            header = struct.unpack_from("<I", data, i)[0]
            i += 4
            tag, size = header & 0x3FF, (header >> 20) & 0xFFF
            if size == 0xFFF:
                size = struct.unpack_from("<I", data, i)[0]
                i += 4
            if tag == HWPTAG_PARA_TEXT:
                text = _para_text(data[i : i + size])
                if text:
                    paras.append(text)
            i += size
    return "\n".join(paras)


if __name__ == "__main__":
    print(any_text(sys.argv[1]))
