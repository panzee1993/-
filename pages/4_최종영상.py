import streamlit as st
import yaml
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

st.set_page_config(page_title="4단계: 최종 영상", page_icon="🎬", layout="wide")

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()

st.title("🎬 4단계: 최종 영상")
st.markdown("이미지 + 음성 + 자막을 합성해서 MP4 영상을 만듭니다.")
st.divider()

# ─── 소재 확인 ────────────────────────────────
st.subheader("소재 확인")

col1, col2, col3 = st.columns(3)
with col1:
    scenes = st.session_state.get("scenes", [])
    img_count = sum(1 for s in scenes if s.get("image_path") and os.path.exists(s["image_path"]))
    if scenes:
        st.metric("이미지", f"{img_count} / {len(scenes)}장", delta="준비됨" if img_count == len(scenes) else "미완성")
    else:
        st.metric("이미지", "없음")
        st.warning("2단계에서 이미지를 생성해 주세요.")

with col2:
    audio_path = st.session_state.get("audio_path", "")
    if audio_path and os.path.exists(audio_path):
        size_mb = os.path.getsize(audio_path) / 1024 / 1024
        st.metric("음성", f"{size_mb:.1f} MB", delta="준비됨")
    else:
        st.metric("음성", "없음")
        st.warning("3단계에서 음성을 생성해 주세요.")

with col3:
    script = st.session_state.get("final_script", "")
    if script:
        st.metric("자막 원고", f"{len(script):,}자", delta="준비됨")
    else:
        st.metric("자막 원고", "없음")

st.divider()

# ─── 영상 설정 ────────────────────────────────
st.subheader("영상 설정")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("**자막 설정**")
    subtitle_fontsize = st.slider("자막 크기", min_value=40, max_value=120, value=75)
    subtitle_color = st.color_picker("자막 색상", "#FFFFFF")
    subtitle_stroke = st.slider("외곽선 두께", min_value=0, max_value=5, value=2)
    subtitle_position = st.selectbox("자막 위치", ["하단", "중앙", "상단"])

with col_right:
    st.markdown("**배경음악 (선택)**")
    bgm_file = st.file_uploader("BGM 파일 업로드", type=["mp3", "wav", "ogg"])
    if bgm_file:
        bgm_volume = st.slider("BGM 볼륨", min_value=0.0, max_value=0.5, value=0.1, step=0.01)

    st.markdown("**출력 설정**")
    output_fps = st.select_slider("FPS", options=[24, 30, 60], value=24)
    project_name = st.session_state.get("project_name", "output")
    output_name = st.text_input("출력 파일 이름", value=f"{project_name}_final.mp4")

st.divider()

# ─── 영상 합성 ────────────────────────────────
st.subheader("영상 합성")

ready = bool(scenes and audio_path and script)

if not ready:
    st.warning("이미지, 음성, 스크립트가 모두 준비되어야 합니다.")

col_export, _ = st.columns([1, 3])
with col_export:
    export_btn = st.button("영상 합성 시작", type="primary", disabled=not ready)

if export_btn:
    with st.spinner("영상을 합성 중입니다... (3~10분 소요)"):
        try:
            from utils.video_maker import VideoMaker
            maker = VideoMaker(config=config)
            output_path = maker.create_video(
                scenes=scenes,
                audio_path=audio_path,
                subtitle_fontsize=subtitle_fontsize,
                subtitle_color=subtitle_color,
                subtitle_stroke=subtitle_stroke,
                subtitle_position=subtitle_position,
                bgm_path=None,
                fps=output_fps,
                output_name=output_name,
            )
            st.session_state["output_video_path"] = output_path
            st.success(f"영상 합성 완료! 저장 위치: {output_path}")
        except Exception as e:
            st.error(f"영상 합성 오류: {e}")

# 영상 미리보기
if "output_video_path" in st.session_state:
    video_path = st.session_state["output_video_path"]
    if os.path.exists(video_path):
        st.subheader("영상 미리보기")
        st.video(video_path)

        with open(video_path, "rb") as f:
            st.download_button(
                label="MP4 다운로드",
                data=f,
                file_name=os.path.basename(video_path),
                mime="video/mp4",
            )

st.divider()
col_back, col_next = st.columns(2)
with col_back:
    st.page_link("pages/3_음성.py", label="← 3단계: 음성 생성", icon="🔊")
with col_next:
    st.page_link("pages/5_썸네일업로드.py", label="5단계: 썸네일/업로드로 이동 →", icon="🚀")
