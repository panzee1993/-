import streamlit as st
import yaml
import os
import json
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.project_manager import ProjectManager
from utils.gemini_client import GeminiClient

st.set_page_config(page_title="2단계: 장면/이미지", page_icon="🖼️", layout="wide")

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()

st.title("🖼️ 2단계: 장면/이미지")
st.markdown("스크립트를 장면 단위로 분할하고 AI로 이미지를 생성합니다.")
st.divider()

# ─── 스크립트 불러오기 ────────────────────────
st.subheader("스크립트")

script_source = st.radio(
    "스크립트 불러오기",
    ["1단계에서 이어서", "직접 입력", "파일에서 불러오기"],
    horizontal=True,
)

script = ""
if script_source == "1단계에서 이어서":
    script = st.session_state.get("final_script", "")
    if script:
        st.text_area("현재 스크립트", value=script, height=120, disabled=True, label_visibility="collapsed")
    else:
        st.warning("1단계에서 생성된 스크립트가 없습니다. 직접 입력하거나 파일에서 불러오세요.")
elif script_source == "직접 입력":
    script = st.text_area("스크립트 입력", height=150, placeholder="여기에 스크립트를 붙여넣으세요.")
elif script_source == "파일에서 불러오기":
    pm = ProjectManager()
    projects = pm.list_projects()
    if projects:
        selected_project = st.selectbox("프로젝트 선택", projects)
        loaded = pm.load_script(selected_project)
        if loaded:
            script = loaded
            st.success(f"{selected_project} 스크립트를 불러왔습니다.")
    else:
        st.info("저장된 프로젝트가 없습니다.")

st.divider()

# ─── 이미지 스타일 설정 ───────────────────────
st.subheader("이미지 스타일 설정")

col1, col2 = st.columns(2)
with col1:
    style_options = {
        "K웹툰 실사": "k_webtoon_real",
        "실사 사진": "realistic",
        "3D 애니메이션": "3d_animation",
        "수채화": "watercolor",
        "커스텀": "custom",
    }
    selected_style_name = st.selectbox("이미지 스타일", list(style_options.keys()))
    selected_style = style_options[selected_style_name]

with col2:
    characters = st.text_area(
        "캐릭터 설정 (선택)",
        placeholder="char_1: 너구리 해설자, 갈색 후드 착용\nchar_2: 조선시대 장군, 갑옷 착용",
        height=100,
    )

if selected_style == "custom":
    custom_style_prompt = st.text_input(
        "커스텀 스타일 프롬프트",
        placeholder="예: Japanese manga style, black and white, detailed line art",
    )

st.divider()

# ─── 장면 분할 ────────────────────────────────
st.subheader("장면 분할 및 이미지 프롬프트 생성")

col_split, _ = st.columns([1, 4])
with col_split:
    split_btn = st.button("장면 분할 시작", type="primary", disabled=not script)

if split_btn:
    gemini_key = config.get("api", {}).get("gemini_api_key", "")
    if not gemini_key:
        st.error("config.yaml에 Gemini API 키를 먼저 설정해 주세요.")
    else:
        with st.spinner("장면을 분할하고 이미지 프롬프트를 생성 중..."):
            try:
                client = GeminiClient(api_key=gemini_key, config=config)
                scenes = client.split_scenes(
                    script=script,
                    style=selected_style_name,
                    characters=characters,
                )
                st.session_state["scenes"] = scenes
                st.success(f"총 {len(scenes)}개 장면으로 분할되었습니다!")
            except Exception as e:
                st.error(f"오류: {e}")

# ─── 장면별 카드 표시 ─────────────────────────
if "scenes" in st.session_state:
    scenes = st.session_state["scenes"]
    st.divider()
    st.subheader(f"장면 목록 ({len(scenes)}개)")

    gemini_key = config.get("api", {}).get("gemini_api_key", "")

    for i, scene in enumerate(scenes):
        with st.expander(f"장면 {i+1}: {scene.get('narration', '')[:40]}...", expanded=(i < 3)):
            col_left, col_right = st.columns([2, 1])

            with col_left:
                st.markdown("**나레이션**")
                st.text(scene.get("narration", ""))
                st.markdown("**이미지 프롬프트**")
                edited_prompt = st.text_area(
                    f"프롬프트_{i}",
                    value=scene.get("image_prompt", ""),
                    height=80,
                    label_visibility="collapsed",
                    key=f"prompt_{i}",
                )
                scenes[i]["image_prompt"] = edited_prompt

            with col_right:
                if scene.get("image_path") and os.path.exists(scene["image_path"]):
                    st.image(scene["image_path"], caption=f"장면 {i+1}")
                else:
                    st.markdown("*이미지 없음*")
                    if st.button(f"이미지 생성", key=f"gen_{i}", disabled=not gemini_key):
                        with st.spinner(f"장면 {i+1} 이미지 생성 중..."):
                            try:
                                client = GeminiClient(api_key=gemini_key, config=config)
                                img_path = client.generate_image(
                                    prompt=edited_prompt,
                                    scene_index=i,
                                )
                                scenes[i]["image_path"] = img_path
                                st.session_state["scenes"] = scenes
                                st.rerun()
                            except Exception as e:
                                st.error(f"이미지 생성 오류: {e}")

    # 전체 이미지 생성 버튼
    st.divider()
    col_all, col_next = st.columns([1, 1])
    with col_all:
        if st.button("전체 이미지 일괄 생성", type="primary", disabled=not gemini_key):
            st.info("전체 이미지 생성은 시간이 걸립니다. Phase 3에서 구현 예정입니다.")

    with col_next:
        st.page_link("pages/3_음성.py", label="3단계: 음성 생성으로 이동 →", icon="🔊")
