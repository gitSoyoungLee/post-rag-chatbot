from pathlib import Path

from post_rag.chunking import split_markdown_document


def test_country_document_chunks_keep_section_context() -> None:
    path = Path("data/docs/epost/countries/US.md")

    chunks = split_markdown_document(path)
    prohibited = [chunk for chunk in chunks if "금지·제한품목" in chunk.metadata["section_path"]]

    assert prohibited
    assert all(chunk.metadata["country_code"] == "US" for chunk in prohibited)
    assert any(chunk.metadata["service_type"] == "ems" for chunk in prohibited)
    assert all("경로:" in chunk.content for chunk in prohibited)


def test_common_document_uses_all_filter() -> None:
    path = Path("data/docs/epost/common/sendable-items.md")

    chunks = split_markdown_document(path)

    assert chunks
    assert all(chunk.metadata["country_code"] == "ALL" for chunk in chunks)



def test_markdown_table_rows_become_separate_chunks() -> None:
    path = Path("data/docs/epost/common/sendable-items.md")

    chunks = split_markdown_document(path)
    perfume = [chunk for chunk in chunks if "| **향수** |" in chunk.content]

    assert len(perfume) == 1
    # 머리글 + 해당 행만 들어 있어 다른 품목과 섞이지 않는다
    assert "품목" in perfume[0].content and "가능여부" in perfume[0].content
    assert "일회용 라이터" not in perfume[0].content
