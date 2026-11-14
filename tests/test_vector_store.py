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


def test_service_filter_is_applied_before_top_k(tmp_path) -> None:
    """서비스가 섞인 국가 문서에서도 요청 서비스 근거가 top-k 안에 확보되어야 한다."""
    docs = tmp_path / "docs"
    docs.mkdir()
    premium_sections = "\n".join(
        f"### 접수 시 주의사항 {index}\n프리미엄 안내 {index}: 화장품 립밤 통관 확인\n" for index in range(30)
    )
    (docs / "us.md").write_text(
        f"""---
doc_id: us-policy
title: 미국 발송조건
source_type: 우체국안내
country_codes: [US]
collected_at: 2026-11-13
---
# 미국 발송조건
## 미국 EMS프리미엄
{premium_sections}
## 미국 국제특급(EMS)
### 금지·제한품목
제한품목 : 화장품
""",
        encoding="utf-8",
    )
    chroma = tmp_path / "chroma"
    embeddings = DeterministicFakeEmbedding(size=32)
    build_vector_store(docs, chroma, embeddings=embeddings)
    retriever = RegulationRetriever(chroma, embeddings=embeddings)

    results = retriever.by_item(
        Item(original_name="립밤", normalized_name="립밤", categories=["화장품"]),
        country_code="US",
        service_type="ems",
    )

    assert results, "EMS 근거가 비어 있으면 안 된다"
    assert {result.service_type for result in results} <= {"ems", "ALL"}
    assert any("화장품" in result.content for result in results)


def test_common_documents_survive_when_country_fills_top_k(tmp_path) -> None:
    """국가 문서 청크가 k개를 넘어도 공통 금지물품 문서가 근거에 포함되어야 한다."""
    docs = tmp_path / "docs"
    docs.mkdir()
    country_sections = "\n".join(f"### 안내 {index}\n미국 노트북 배터리 안내 {index}\n" for index in range(12))
    (docs / "us.md").write_text(
        f"""---
doc_id: us-policy
title: 미국 발송조건
country_codes: [US]
---
# 미국 발송조건
## 미국 국제특급(EMS)
{country_sections}
""",
        encoding="utf-8",
    )
    (docs / "common.md").write_text(
        """---
doc_id: common-items
title: 보낼 수 없는 물품
country_codes: [ALL]
---
# 보낼 수 없는 물품
## 항공탑재금지물품
리튬 배터리가 포함된 전자기기는 발송 불가
""",
        encoding="utf-8",
    )
    chroma = tmp_path / "chroma"
    embeddings = DeterministicFakeEmbedding(size=32)
    build_vector_store(docs, chroma, embeddings=embeddings)
    retriever = RegulationRetriever(chroma, embeddings=embeddings)

    results = retriever.by_item(
        Item(original_name="노트북", normalized_name="노트북", categories=["전자제품", "배터리"]),
        country_code="US",
        service_type="ems",
    )

    assert len(results) == 5
    assert "common-items" in {result.document_id for result in results}
