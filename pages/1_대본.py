import streamlit as st
import yaml
import os
import json
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.project_manager import ProjectManager
from utils.gemini_client import GeminiClient

st.set_page_config(page_title="1단계: 대본 작성", page_icon="📝", layout="wide")

# config 로드
def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()

st.title("📝 1단계: 대본 작성")
st.markdown("Gemini AI로 벤치마킹 대본을 분석하고 스크립트를 자동 생성합니다.")
st.divider()

# ─── 프로젝트 설정 ────────────────────────────
st.subheader("프로젝트 설정")

col1, col2, col3 = st.columns(3)
with col1:
    project_name = st.text_input("프로젝트 이름", placeholder="예: 이순신_위기의_조선")
with col2:
    content_type = st.radio("영상 유형", ["롱폼", "쇼츠"], horizontal=True)
with col3:
    if content_type == "롱폼":
        duration = st.number_input("영상 길이 (분)", min_value=3, max_value=30, value=15)
    else:
        duration = st.number_input("영상 길이 (초)", min_value=15, max_value=60, value=60)

category = st.selectbox(
    "카테고리",
    ["역사/인물", "물건/발명", "음식/요리", "여행지", "IT/기술", "자연/과학", "사건/사고", "기타"],
)

st.divider()

# ─── 벤치마킹 대본 입력 ────────────────────────
st.subheader("벤치마킹 대본 (선택)")
st.caption("참고할 유튜브 대본을 붙여넣으면 AI가 분석해서 비슷한 주제를 추천해 줍니다.")

benchmark = st.text_area(
    "벤치마킹 대본",
    height=150,
    placeholder="여기에 참고 대본을 붙여넣으세요. (없으면 비워두세요)",
    label_visibility="collapsed",
)

col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    recommend_btn = st.button("주제 추천 받기", type="primary", disabled=not project_name)

# 주제 추천 결과
if recommend_btn:
    gemini_key = config.get("api", {}).get("gemini_api_key", "")
    if not gemini_key:
        st.error("config.yaml에 Gemini API 키를 먼저 설정해 주세요.")
    else:
        with st.spinner("Gemini AI가 주제를 분석 중입니다..."):
            try:
                client = GeminiClient(api_key=gemini_key, config=config)
                topics = client.recommend_topics(
                    benchmark_script=benchmark,
                    category=category,
                    content_type=content_type,
                )
                st.session_state["recommended_topics"] = topics
                st.success("주제 추천 완료!")
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

# 주제 선택
if "recommended_topics" in st.session_state:
    st.divider()
    st.subheader("추천 주제 선택")
    topics = st.session_state["recommended_topics"]
    selected_topic = st.radio("주제를 선택하세요", topics, label_visibility="collapsed")
    st.session_state["selected_topic"] = selected_topic
else:
    st.divider()
    st.subheader("직접 주제 입력")
    manual_topic = st.text_input(
        "주제",
        placeholder="예: 조선 최고의 명장 이순신이 사실 처형 직전까지 갔던 이유",
    )
    if manual_topic:
        st.session_state["selected_topic"] = manual_topic

st.divider()

# ─── 스크립트 생성 ────────────────────────────
st.subheader("스크립트 생성")

selected_topic = st.session_state.get("selected_topic", "")
if selected_topic:
    st.info(f"선택된 주제: **{selected_topic}**")

col_gen, col_empty = st.columns([1, 4])
with col_gen:
    generate_btn = st.button(
        "스크립트 생성",
        type="primary",
        disabled=not selected_topic,
    )

if generate_btn:
    gemini_key = config.get("api", {}).get("gemini_api_key", "")
    if not gemini_key:
        st.error("config.yaml에 Gemini API 키를 먼저 설정해 주세요.")
    else:
        with st.spinner("Gemini AI가 스크립트를 작성 중입니다... (30초~1분 소요)"):
            try:
                client = GeminiClient(api_key=gemini_key, config=config)
                script = client.generate_script(
                    topic=selected_topic,
                    duration=duration,
                    content_type=content_type,
                    category=category,
                )
                st.session_state["generated_script"] = script
                st.success("스크립트 생성 완료!")
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

# 스크립트 편집
if "generated_script" in st.session_state:
    st.subheader("스크립트 편집")
    edited_script = st.text_area(
        "생성된 스크립트 (직접 수정 가능)",
        value=st.session_state["generated_script"],
        height=400,
        label_visibility="collapsed",
    )
    st.session_state["final_script"] = edited_script

    # 글자 수 / 줄 수 통계
    lines = edited_script.strip().split("\n") if edited_script else []
    char_count = len(edited_script.replace("\n", "")) if edited_script else 0
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    col_stat1.metric("총 글자 수", f"{char_count:,}자")
    col_stat2.metric("총 줄 수", f"{len(lines)}줄")
    col_stat3.metric("예상 시간", f"{char_count / 385:.1f}분")

    st.divider()

    # 저장 버튼
    col_save, col_next = st.columns([1, 1])
    with col_save:
        if st.button("프로젝트 저장", type="secondary"):
            if not project_name:
                st.warning("프로젝트 이름을 먼저 입력해 주세요.")
            else:
                pm = ProjectManager()
                pm.save_script(
                    project_name=project_name,
                    script=edited_script,
                    meta={
                        "topic": selected_topic,
                        "content_type": content_type,
                        "duration": duration,
                        "category": category,
                    },
                )
                st.success(f"projects/{project_name}/ 에 저장되었습니다.")

    with col_next:
        st.page_link("pages/2_장면이미지.py", label="2단계: 장면/이미지로 이동 →", icon="🖼️")
