import streamlit as st
import yaml
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.project_manager import ProjectManager

st.set_page_config(page_title="3단계: 음성 생성", page_icon="🔊", layout="wide")

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()

st.title("🔊 3단계: 음성 생성")
st.markdown("대본을 자연스러운 한국어 음성으로 변환합니다.")
st.divider()

# ─── 스크립트 확인 ────────────────────────────
st.subheader("스크립트")
script = st.session_state.get("final_script", "")
if script:
    with st.expander("현재 스크립트 보기", expanded=False):
        st.text(script[:500] + ("..." if len(script) > 500 else ""))
    st.success(f"스크립트 준비됨 (총 {len(script):,}자)")
else:
    st.warning("1단계에서 생성된 스크립트가 없습니다.")
    manual_script = st.text_area("스크립트 직접 입력", height=150)
    if manual_script:
        st.session_state["final_script"] = manual_script
        script = manual_script

st.divider()

# ─── TTS 엔진 설정 ────────────────────────────
st.subheader("TTS 설정")

col1, col2 = st.columns(2)

with col1:
    tts_engine = st.radio(
        "TTS 엔진",
        ["Gemini TTS (무료)", "ElevenLabs (유료, 고품질)"],
    )

    if "Gemini" in tts_engine:
        gemini_voices = {
            "Kore (한국어 여성)": "Kore",
            "Aoede (여성, 밝음)": "Aoede",
            "Charon (남성, 중립)": "Charon",
            "Fenrir (남성, 낮음)": "Fenrir",
            "Puck (남성, 경쾌)": "Puck",
        }
        selected_voice_name = st.selectbox("목소리", list(gemini_voices.keys()))
        selected_voice = gemini_voices[selected_voice_name]

    else:
        elevenlabs_key = config.get("api", {}).get("elevenlabs_api_key", "")
        if not elevenlabs_key:
            st.warning("config.yaml에 ElevenLabs API 키를 설정해 주세요.")
        el_voices = ["서연 (한국어 여성)", "지호 (한국어 남성)", "Rachel (영어 여성)"]
        selected_voice_name = st.selectbox("목소리", el_voices)
        selected_voice = selected_voice_name

with col2:
    speed = st.slider("음성 속도", min_value=0.8, max_value=1.5, value=1.0, step=0.05)
    split_500 = st.checkbox("500자 단위로 분할 생성", value=True)
    st.caption("긴 대본은 분할 생성 권장")

    style_options = ["기본", "뉴스 앵커", "차분한 내레이션", "활기찬 유튜버"]
    speech_style = st.selectbox("말투 스타일", style_options)

st.divider()

# ─── 음성 생성 버튼 ───────────────────────────
st.subheader("음성 생성")

col_gen, col_prev = st.columns([1, 2])

with col_gen:
    generate_btn = st.button(
        "음성 생성 시작",
        type="primary",
        disabled=not script,
    )

if generate_btn:
    gemini_key = config.get("api", {}).get("gemini_api_key", "")
    elevenlabs_key = config.get("api", {}).get("elevenlabs_api_key", "")

    if "Gemini" in tts_engine and not gemini_key:
        st.error("config.yaml에 Gemini API 키를 먼저 설정해 주세요.")
    elif "ElevenLabs" in tts_engine and not elevenlabs_key:
        st.error("config.yaml에 ElevenLabs API 키를 먼저 설정해 주세요.")
    else:
        with st.spinner("음성을 생성 중입니다... (대본 길이에 따라 1~3분 소요)"):
            try:
                if "Gemini" in tts_engine:
                    from utils.gemini_client import GeminiClient
                    client = GeminiClient(api_key=gemini_key, config=config)
                    audio_path = client.generate_tts(
                        text=script,
                        voice=selected_voice,
                        speed=speed,
                        split=split_500,
                    )
                else:
                    from utils.elevenlabs_client import ElevenLabsClient
                    client = ElevenLabsClient(api_key=elevenlabs_key)
                    audio_path = client.generate_tts(
                        text=script,
                        voice=selected_voice,
                    )

                st.session_state["audio_path"] = audio_path
                st.success("음성 생성 완료!")
            except Exception as e:
                st.error(f"음성 생성 오류: {e}")

# 오디오 미리듣기
if "audio_path" in st.session_state:
    audio_path = st.session_state["audio_path"]
    if os.path.exists(audio_path):
        st.subheader("미리듣기")
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        st.audio(audio_bytes)
        st.caption(f"파일 위치: {audio_path}")

st.divider()
col_back, col_next = st.columns(2)
with col_back:
    st.page_link("pages/2_장면이미지.py", label="← 2단계: 장면/이미지", icon="🖼️")
with col_next:
    st.page_link("pages/4_최종영상.py", label="4단계: 최종 영상으로 이동 →", icon="🎬")
