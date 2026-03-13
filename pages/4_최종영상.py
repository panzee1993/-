"""4단계: 최종 영상 합성

이미지 + 음성 + 자막을 FFmpeg로 합성해서 MP4 영상을 만듭니다.

파이프라인:
  이미지(2단계) + 음성(3단계) → 슬라이드쇼 → 자막(ASS) 소각 → 최종 MP4
"""

import glob as glob_module
import os
import sys
import time

import streamlit as st
import yaml

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

st.set_page_config(page_title="4단계: 최종 영상", page_icon="🎬", layout="wide")


# ─── 설정 로딩 ────────────────────────────────────────────────────────────────

def load_config() -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config()

# ─── 헤더 ────────────────────────────────────────────────────────────────────

st.title("🎬 4단계: 최종 영상")
st.markdown("이미지 + 음성 + 자막을 **FFmpeg**로 합성해 MP4 영상을 만듭니다.")
st.divider()

# ─── 프로젝트 확인 ───────────────────────────────────────────────────────────

from utils.project_manager import ProjectManager

pm = ProjectManager()

if not st.session_state.get("project_name"):
    projects = pm.list_projects()
    if not projects:
        st.warning("1단계에서 프로젝트를 먼저 생성해 주세요.")
        st.stop()

    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        selected = st.selectbox("진행할 프로젝트를 선택하세요", projects)
    with col_btn:
        st.write("")
        if st.button("불러오기", type="primary"):
            st.session_state["project_name"] = selected
            st.rerun()
    st.stop()

project_name: str = st.session_state["project_name"]
st.caption(f"현재 프로젝트: **{project_name}**")

# ─── 소재 자동 로딩 ──────────────────────────────────────────────────────────
# 세션에 없으면 프로젝트 폴더에서 자동으로 읽어 옴

scenes: list = st.session_state.get("scenes", [])
if not scenes:
    scenes = pm.load_scenes(project_name)
    if scenes:
        st.session_state["scenes"] = scenes

audio_path: str = st.session_state.get("audio_path", "")
if not audio_path or not os.path.exists(audio_path):
    audio_dir = pm.get_audio_dir(project_name)
    found = sorted(
        glob_module.glob(os.path.join(audio_dir, "*.wav"))
        + glob_module.glob(os.path.join(audio_dir, "*.mp3")),
        key=os.path.getmtime,
        reverse=True,
    )
    if found:
        audio_path = found[0]
        st.session_state["audio_path"] = audio_path

# ─── ① 소재 확인 ─────────────────────────────────────────────────────────────

st.subheader("① 소재 확인")

total_scenes = len(scenes)
img_ok = sum(
    1 for s in scenes
    if s.get("image_path") and os.path.exists(s["image_path"])
)
has_audio = bool(audio_path and os.path.exists(audio_path))
total_narration_chars = sum(len((s.get("narration") or "")) for s in scenes)
has_narration = any((s.get("narration") or "").strip() for s in scenes)

col_img, col_aud, col_txt = st.columns(3)

with col_img:
    if total_scenes == 0:
        st.error("🖼️ 이미지 없음")
        st.caption("2단계에서 이미지를 생성해 주세요.")
    elif img_ok < total_scenes:
        st.warning(f"🖼️ {img_ok} / {total_scenes} 장")
        st.caption(f"없는 {total_scenes - img_ok}장은 검은 화면으로 대체됩니다.")
    else:
        st.success(f"🖼️ 이미지 {img_ok}장 준비 완료")

with col_aud:
    if has_audio:
        size_mb = os.path.getsize(audio_path) / 1024 / 1024
        st.success(f"🔊 음성 {size_mb:.1f} MB 준비 완료")
        st.caption(os.path.basename(audio_path))
    else:
        st.error("🔊 음성 파일 없음")
        st.caption("3단계에서 음성을 생성해 주세요.")

with col_txt:
    if has_narration:
        st.success(f"📝 나레이션 {total_narration_chars:,}자")
        st.caption("줄 단위로 자막이 생성됩니다.")
    else:
        st.info("📝 나레이션 없음")
        st.caption("자막 없이 합성됩니다.")

material_ready = total_scenes > 0 and has_audio

if not material_ready:
    st.warning("이미지(2단계)와 음성(3단계)이 모두 준비되어야 합성할 수 있습니다.")

st.divider()

# ─── 설정 패널 ────────────────────────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    # ② 영상 기본 설정
    st.subheader("② 영상 기본 설정")

    RES_OPTIONS = {
        "1920 × 1080  (Full HD)": (1920, 1080),
        "1280 × 720   (HD)": (1280, 720),
    }
    res_label = st.selectbox("해상도", list(RES_OPTIONS.keys()))
    vid_w, vid_h = RES_OPTIONS[res_label]

    output_fps = st.select_slider("FPS", options=[24, 30, 60], value=24)

    st.divider()

    # ③ 자막 설정
    st.subheader("③ 자막 설정")

    subtitle_enabled = st.toggle("자막 사용", value=True, disabled=not has_narration)

    if subtitle_enabled and has_narration:
        subtitle_fontname = st.text_input(
            "폰트 이름",
            value="NanumGothic",
            help=(
                "시스템에 설치된 폰트명을 입력하세요.\n"
                "• Linux: NanumGothic, NotoSansCJK\n"
                "• Windows: 맑은 고딕, 나눔고딕\n"
                "• Mac: AppleGothic"
            ),
        )
        subtitle_fontsize = st.slider("폰트 크기", 40, 120, 75, step=5)
        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            subtitle_color = st.color_picker("자막 색상", "#FFFFFF")
        with sub_col2:
            subtitle_stroke = st.slider("외곽선 두께", 0, 6, 3)
        subtitle_position = st.radio(
            "자막 위치", ["하단", "중앙", "상단"], horizontal=True
        )
    else:
        subtitle_fontname = "NanumGothic"
        subtitle_fontsize = 75
        subtitle_color = "#FFFFFF"
        subtitle_stroke = 3
        subtitle_position = "하단"
        if not has_narration:
            st.caption("나레이션이 없어 자막을 생성할 수 없습니다.")

with col_right:
    # ④ 전환 효과
    st.subheader("④ 전환 효과")

    ken_burns = st.toggle(
        "Ken Burns 효과 (줌 인 / 줌 아웃)",
        value=False,
        help="각 이미지에 서서히 줌 인·아웃 효과를 적용합니다. 처리 시간이 크게 늘어납니다.",
    )
    if ken_burns:
        st.info(
            "켄 번스 효과는 장면별 개별 처리가 필요해 합성 시간이 수 배 길어집니다.\n"
            "테스트 시에는 꺼두는 것을 권장합니다.",
            icon="⏱️",
        )

    st.divider()

    # ⑤ 배경음악
    st.subheader("⑤ 배경음악 (선택)")

    bgm_file = st.file_uploader(
        "BGM 파일 업로드", type=["mp3", "wav", "ogg", "m4a", "aac"]
    )
    bgm_path: str | None = None
    bgm_volume = 0.1

    if bgm_file:
        bgm_dir = os.path.join(pm._project_path(project_name), "bgm")
        os.makedirs(bgm_dir, exist_ok=True)
        bgm_path = os.path.join(bgm_dir, bgm_file.name)
        with open(bgm_path, "wb") as fh:
            fh.write(bgm_file.getvalue())
        bgm_volume = st.slider(
            "BGM 볼륨",
            min_value=0.0,
            max_value=0.5,
            value=0.1,
            step=0.01,
            help="0.1 = 나레이션의 10% 볼륨. 배경음악은 작을수록 좋습니다.",
        )
        st.success(f"BGM 로드됨: `{bgm_file.name}`")

    st.divider()

    # ⑥ 출력 설정
    st.subheader("⑥ 출력 설정")

    default_filename = f"{project_name}_final.mp4"
    output_name = st.text_input("출력 파일 이름", value=default_filename)
    if not output_name.endswith(".mp4"):
        output_name += ".mp4"

st.divider()

# ─── ⑦ 합성 시작 ─────────────────────────────────────────────────────────────

st.subheader("⑦ 영상 합성 시작")

# 합성 전 요약 카드
if material_ready:
    summary_col1, summary_col2 = st.columns(2)
    with summary_col1:
        st.markdown(f"""
| 항목 | 값 |
|---|---|
| 장면 수 | {total_scenes}개 |
| 이미지 | {img_ok} / {total_scenes}장 |
| 해상도 | {vid_w} × {vid_h} |
| FPS | {output_fps} |
""")
    with summary_col2:
        st.markdown(f"""
| 항목 | 값 |
|---|---|
| 자막 | {'켜짐' if subtitle_enabled and has_narration else '꺼짐'} |
| Ken Burns | {'켜짐' if ken_burns else '꺼짐'} |
| BGM | {'있음' if bgm_path else '없음'} |
| 출력 파일 | `{output_name}` |
""")

export_btn = st.button(
    "🎬  영상 합성 시작",
    type="primary",
    disabled=not material_ready,
    use_container_width=True,
)

# ─── 합성 실행 ────────────────────────────────────────────────────────────────

if export_btn:
    from utils.video_maker import VideoMaker

    output_dir = pm.get_output_dir(project_name)

    # 해상도 오버라이드
    merged_config = {
        **config,
        "video": {
            **config.get("video", {}),
            "resolution": {"width": vid_w, "height": vid_h},
        },
    }
    maker = VideoMaker(config=merged_config)

    status_area = st.empty()
    log_area = st.empty()

    estimated_min = max(1, round(total_scenes * (3 if ken_burns else 0.5) / 60, 1))
    status_area.info(
        f"합성 중... 예상 소요 시간: 약 {estimated_min}분 "
        f"({'Ken Burns 켜짐, 장면별 개별 처리' if ken_burns else '단순 슬라이드쇼'})"
    )

    t_start = time.time()
    try:
        result_path = maker.create_video(
            scenes=scenes,
            audio_path=audio_path,
            subtitle_enabled=subtitle_enabled and has_narration,
            subtitle_fontname=subtitle_fontname,
            subtitle_fontsize=subtitle_fontsize,
            subtitle_color=subtitle_color,
            subtitle_stroke=subtitle_stroke,
            subtitle_position=subtitle_position,
            ken_burns=ken_burns,
            bgm_path=bgm_path,
            bgm_volume=bgm_volume,
            fps=output_fps,
            output_name=output_name,
            output_dir=output_dir,
        )
        elapsed = time.time() - t_start
        st.session_state["output_video_path"] = result_path

        status_area.success(f"✅ 합성 완료! ({elapsed:.0f}초 소요)")
        log_area.info(f"저장 위치: `{result_path}`")
        st.rerun()

    except Exception as exc:
        elapsed = time.time() - t_start
        status_area.error(f"합성 실패 ({elapsed:.0f}초 후 오류 발생)")
        with st.expander("오류 상세 보기", expanded=True):
            st.code(str(exc), language="text")
        st.markdown("""
**자주 발생하는 오류 원인:**
- `FFmpeg 오류` → FFmpeg가 설치되지 않았거나 PATH에 없음 (`ffmpeg -version` 확인)
- `ass=` 관련 오류 → FFmpeg가 libass 없이 빌드됨. 자막을 꺼보세요.
- `ffprobe 실패` → ffprobe가 설치되지 않음 (FFmpeg와 함께 설치)
- `zoompan` 오류 → Ken Burns를 꺼보세요.
""")

# ─── ⑧ 결과 미리보기 ─────────────────────────────────────────────────────────

if "output_video_path" in st.session_state:
    video_path: str = st.session_state["output_video_path"]
    if os.path.exists(video_path):
        st.divider()
        st.subheader("⑧ 완성 영상")

        # 파일 정보 메트릭
        size_mb = os.path.getsize(video_path) / 1024 / 1024
        m1, m2, m3 = st.columns(3)
        m1.metric("파일 크기", f"{size_mb:.1f} MB")
        m2.metric("파일명", os.path.basename(video_path))
        m3.metric("저장 폴더", os.path.dirname(video_path).split(os.sep)[-1])

        # 영상 플레이어
        st.video(video_path)

        # 다운로드 버튼
        with open(video_path, "rb") as fh:
            st.download_button(
                label="⬇️  MP4 다운로드",
                data=fh,
                file_name=os.path.basename(video_path),
                mime="video/mp4",
                use_container_width=True,
            )

# ─── 네비게이션 ──────────────────────────────────────────────────────────────

st.divider()
nav_back, nav_next = st.columns(2)
with nav_back:
    st.page_link("pages/3_음성.py", label="← 3단계: 음성 생성", icon="🔊")
with nav_next:
    st.page_link("pages/5_썸네일업로드.py", label="5단계: 썸네일/업로드로 이동 →", icon="🚀")
