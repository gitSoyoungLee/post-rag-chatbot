from __future__ import annotations

import uuid

import streamlit as st

from post_rag.clients import create_chat_model
from post_rag.config import GMS_KEY
from post_rag.graph import PostalAssistant
from post_rag.vector_store import RegulationRetriever


st.set_page_config(page_title="PostGuard", page_icon="📮", layout="centered")
st.title("📮 PostGuard")
st.caption("근거와 함께 확인하는 국제우편 규정 어시스턴트")

DISCLAIMER = "안내 결과는 수집된 자료를 기준으로 하며, 실제 접수 조건과 최종 요금은 우체국에서 확인해 주세요."

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

if not GMS_KEY:
    st.error("GMS_KEY가 필요합니다. 프로젝트 루트의 .env 파일에 직접 입력해 주세요.")
    st.stop()

if "assistant" not in st.session_state:
    model = create_chat_model()
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
        if message["role"] == "assistant":
            st.caption(DISCLAIMER)

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
                st.caption("상세 오류는 서버 로그에서 확인할 수 있습니다.")
            st.markdown(answer)
            st.caption(DISCLAIMER)
    st.session_state.messages.append({"role": "assistant", "content": answer})

