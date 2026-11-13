from __future__ import annotations

import os
import uuid

import streamlit as st
from langchain_openai import ChatOpenAI

from post_rag.graph import PostalAssistant
from post_rag.vector_store import RegulationRetriever


st.set_page_config(page_title="PostGuard", page_icon="📮", layout="centered")
st.title("📮 PostGuard")
st.caption("근거와 함께 확인하는 국제우편 규정 어시스턴트")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

if not os.getenv("OPENAI_API_KEY"):
    st.error("OPENAI_API_KEY가 필요합니다. .env 또는 실행 환경에 설정해 주세요.")
    st.stop()

if "assistant" not in st.session_state:
    model = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), temperature=0)
    st.session_state.assistant = PostalAssistant(model=model, retriever=RegulationRetriever())

with st.sidebar:
    st.subheader("MVP 지원 범위")
    st.write("한국에서 외국으로 보내는 국제우편")
    st.write("품목별 규정, 이용 가능한 서비스, EMS 예상 기본요금")
    if st.button("대화 초기화"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("예: 미국 펜팔에게 과자와 립밤 1.5kg을 EMS로 보내도 될까?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("우편규정과 조건을 확인하고 있어요..."):
            try:
                result = st.session_state.assistant.invoke(prompt, st.session_state.thread_id)
                answer = result["answer"]
            except Exception as exc:
                answer = "요청을 처리하지 못했습니다. 설정과 색인 상태를 확인해 주세요."
                if os.getenv("POST_RAG_DEBUG") == "1":
                    st.exception(exc)
            st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})

