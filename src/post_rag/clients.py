from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from post_rag.config import (
    LLM_BASE_URL,
    LLM_CHAT_MODEL,
    LLM_EMBEDDING_BATCH_SIZE,
    LLM_EMBEDDING_MODEL,
    LLM_KEY,
    LLM_TEMPERATURE,
    LLM_USE_RESPONSES_API,
)


def require_llm_key() -> str:
    if not LLM_KEY:
        raise RuntimeError(".env 파일에 LLM_KEY를 설정해 주세요.")
    return LLM_KEY


def create_chat_model() -> ChatOpenAI:
    options = {} if LLM_TEMPERATURE is None else {"temperature": LLM_TEMPERATURE}
    return ChatOpenAI(
        model=LLM_CHAT_MODEL,
        api_key=require_llm_key(),
        base_url=LLM_BASE_URL,
        use_responses_api=LLM_USE_RESPONSES_API,
        **options,
    )


def create_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=LLM_EMBEDDING_MODEL,
        api_key=require_llm_key(),
        base_url=LLM_BASE_URL,
        # 기본값(True)은 tiktoken으로 토큰 ID 배열을 보내는데, OpenAI 외 업체는 이를 받지 않는다.
        # 청크는 1,200자 이하라 길이 초과 분할이 필요 없다.
        check_embedding_ctx_length=False,
        chunk_size=LLM_EMBEDDING_BATCH_SIZE,
    )
