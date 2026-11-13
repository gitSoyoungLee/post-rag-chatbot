from langchain_core.embeddings import DeterministicFakeEmbedding

from post_rag.models import Item
from post_rag.vector_store import RegulationRetriever, build_vector_store


def test_chroma_index_and_country_filtered_retrieval(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "us.md").write_text(
        """---
doc_id: us-policy
title: 미국 발송조건
source_type: 우체국안내
country_codes: [US]
collected_at: 2026-11-13
---
# 미국 발송조건
## 미국 국제특급(EMS)
### 금지·제한품목
화장품은 통관 확인이 필요합니다.
""",
        encoding="utf-8",
    )
    chroma = tmp_path / "chroma"
    embeddings = DeterministicFakeEmbedding(size=32)

    count = build_vector_store(docs, chroma, embeddings=embeddings)
    retriever = RegulationRetriever(chroma, embeddings=embeddings)
    results = retriever.by_item(
        Item(original_name="립밤", normalized_name="립밤", categories=["화장품"]),
        country_code="US",
        service_type="ems",
    )

    assert count == 1
    assert results[0].document_id == "us-policy"
    assert results[0].country_code == "US"
