import streamlit as st
import yaml
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.project_manager import ProjectManager

st.set_page_config(page_title="3단계: 음성 생성", page_icon="🔊", layout="wide")

ROOT = os.path.dirname(os.path.dirname(__file__))

# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────
def load_config() -> dict:
    with open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def audio_file_info(path: str) -> dict:
    """오디오 파일 크기 + 예상 길이 반환"""
    if not os.path.exists(path):
        return {}
    size_bytes = os.path.getsize(path)
    size_mb = size_bytes / 1024 / 1024
    # WAV: 24kHz 16bit mono → 1초당 48,000 bytes
    try:
        import wave
        with wave.open(path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_sec = frames / rate
    except Exception:
        duration_sec = size_bytes / 48000  # 근사치
    return {"size_mb": size_mb, "duration_sec": duration_sec}

# ─────────────────────────────────────────────
# Gemini 목소리 정보
# ─────────────────────────────────────────────
GEMINI_VOICES = {
    "Kore (한국어 최적화, 여성)":    "Kore",
    "Aoede (밝고 활기찬, 여성)":    "Aoede",
    "Leda (젊은 느낌, 여성)":       "Leda",
    "Zephyr (밝은 톤, 여성)":       "Zephyr",
    "Callirrhoe (편안한, 여성)":    "Callirrhoe",
    "Despina (부드러운, 여성)":     "Despina",
    "Charon (차분한, 남성)":        "Charon",
    "Fenrir (낮고 힘있는, 남성)":   "Fenrir",
    "Puck (경쾌한, 남성)":          "Puck",
    "Orus (단호한, 남성)":          "Orus",
    "Iapetus (명확한, 남성)":       "Iapetus",
    "Algieba (부드러운, 남성)":     "Algieba",
}

# 각 목소리 샘플 텍스트
VOICE_SAMPLE_TEXT = "이순신 장군은 임진왜란 당시 조선을 구한 최고의 명장입니다. 그런데 그가 처형 직전까지 몰렸다는 사실, 알고 있었나요?"

# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
config = load_config()
pm = ProjectManager()

gemini_key = config.get("api", {}).get("gemini_api_key", "").strip()
elevenlabs_key = config.get("api", {}).get("elevenlabs_api_key", "").strip()

st.title("🔊 3단계: 음성 생성")

# API 키 상태 배너
key_status = []
if gemini_key:
    key_status.append("✅ Gemini TTS")
else:
    key_status.append("❌ Gemini TTS (키 미설정)")
if elevenlabs_key:
    key_status.append("✅ ElevenLabs")
else:
    key_status.append("⚪ ElevenLabs (키 미설정, 선택)")
st.caption("API 상태: " + " · ".join(key_status))

if not gemini_key and not elevenlabs_key:
    st.warning("**API 키가 없습니다.** config.yaml에 Gemini 또는 ElevenLabs API 키를 설정해 주세요.")

st.divider()

# ─────────────────────────────────────────────
# ① 스크립트 준비
# ─────────────────────────────────────────────
st.subheader("① 스크립트")

src_tab1, src_tab2, src_tab3 = st.tabs(["1단계에서 이어서", "직접 입력", "프로젝트에서 불러오기"])

with src_tab1:
    carried = st.session_state.get("final_script", "")
    if carried:
        lines = [l for l in carried.split("\n") if l.strip()]
        st.success(f"1단계 스크립트 준비됨 — {len(carried):,}자 / {len(lines)}줄")
        with st.expander("스크립트 미리보기"):
            st.text(carried[:600] + ("..." if len(carried) > 600 else ""))
        if st.button("이 스크립트 사용", type="primary", key="use_carried"):
            st.session_state["_tts_script"] = carried
            st.rerun()
    else:
        st.info("1단계에서 생성된 스크립트가 없습니다.")

with src_tab2:
    pasted = st.text_area("스크립트 입력", height=150,
                          placeholder="여기에 대본을 붙여넣으세요.",
                          label_visibility="collapsed")
    if st.button("이 스크립트 사용", type="primary", key="use_pasted", disabled=not pasted):
        st.session_state["_tts_script"] = pasted
        st.rerun()

with src_tab3:
    projects = pm.list_projects()
    if projects:
        sel_proj = st.selectbox("프로젝트 선택", projects)
        if st.button("불러오기", type="primary"):
            loaded = pm.load_script(sel_proj)
            if loaded:
                st.session_state["_tts_script"] = loaded
                st.rerun()
            else:
                st.error("스크립트 파일을 찾을 수 없습니다.")
    else:
        st.info("저장된 프로젝트가 없습니다.")

# 현재 사용할 스크립트
script = st.session_state.get("_tts_script", st.session_state.get("final_script", ""))

if script:
    lines = [l for l in script.split("\n") if l.strip()]
    char_count = len(script.replace("\n", ""))
    est_min = char_count / 385
    st.info(f"현재 스크립트: **{char_count:,}자 / {len(lines)}줄** — 예상 음성 길이: 약 **{est_min:.1f}분**")
else:
    st.warning("스크립트가 없습니다. 위 탭에서 스크립트를 선택하세요.")

st.divider()

# ─────────────────────────────────────────────
# ② TTS 엔진 & 목소리 설정
# ─────────────────────────────────────────────
st.subheader("② TTS 엔진 & 목소리 설정")

engine_tab_gemini, engine_tab_el = st.tabs([
    "🤖 Gemini TTS (무료)" + (" ✅" if gemini_key else " ❌"),
    "🎙️ ElevenLabs (유료, 고품질)" + (" ✅" if elevenlabs_key else " ⚪"),
])

# ── Gemini TTS ──────────────────────────────
with engine_tab_gemini:
    if not gemini_key:
        st.warning("config.yaml의 `gemini_api_key`를 설정해 주세요.")

    col_voice, col_opts = st.columns([1, 1])

    with col_voice:
        st.markdown("**목소리 선택**")
        gemini_voice_name = st.selectbox(
            "Gemini 목소리",
            list(GEMINI_VOICES.keys()),
            index=list(GEMINI_VOICES.keys()).index(
                st.session_state.get("gemini_voice_name", "Kore (한국어 최적화, 여성)")
            ) if st.session_state.get("gemini_voice_name") in GEMINI_VOICES else 0,
            label_visibility="collapsed",
        )
        st.session_state["gemini_voice_name"] = gemini_voice_name
        gemini_voice_id = GEMINI_VOICES[gemini_voice_name]

        # 목소리 테스트
        if st.button("🔊 목소리 테스트 (샘플 20초)", disabled=not gemini_key, key="gemini_test"):
            with st.spinner("샘플 음성 생성 중..."):
                try:
                    from utils.gemini_client import GeminiClient
                    client = GeminiClient(api_key=gemini_key, config=config)
                    sample_path = client.generate_tts(
                        text=VOICE_SAMPLE_TEXT,
                        voice=gemini_voice_id,
                        split=False,
                        output_path=os.path.join(ROOT, "projects", "_temp", "sample.wav"),
                    )
                    st.session_state["sample_audio_path"] = sample_path
                    st.rerun()
                except Exception as e:
                    st.error(f"샘플 생성 오류: {e}")

        if "sample_audio_path" in st.session_state and os.path.exists(st.session_state["sample_audio_path"]):
            st.audio(st.session_state["sample_audio_path"])

    with col_opts:
        st.markdown("**생성 설정**")
        gemini_chunk_size = st.select_slider(
            "청크 크기 (API 호출 단위)",
            options=[200, 300, 500, 800, 1000],
            value=st.session_state.get("gemini_chunk_size", 500),
            help="클수록 API 호출 횟수 ↓, 너무 크면 실패할 수 있음. 500자 권장.",
        )
        st.session_state["gemini_chunk_size"] = gemini_chunk_size

        gemini_speech_style = st.selectbox(
            "말투 스타일 (프롬프트에 추가)",
            ["기본", "차분한 내레이션", "뉴스 앵커", "활기찬 유튜버", "감정적 스토리텔링"],
            index=["기본", "차분한 내레이션", "뉴스 앵커", "활기찬 유튜버", "감정적 스토리텔링"]
                  .index(st.session_state.get("gemini_speech_style", "기본")),
        )
        st.session_state["gemini_speech_style"] = gemini_speech_style

        tts_engine_selected = "gemini"

# ── ElevenLabs TTS ──────────────────────────
with engine_tab_el:
    if not elevenlabs_key:
        st.info("config.yaml의 `elevenlabs_api_key`를 입력하면 ElevenLabs를 사용할 수 있습니다.")

    col_el_voice, col_el_opts = st.columns([1, 1])

    with col_el_voice:
        st.markdown("**목소리 선택**")

        el_voice_source = st.radio(
            "목소리 소스",
            ["API에서 불러오기", "Voice ID 직접 입력"],
            horizontal=True,
            key="el_voice_source",
        )

        if el_voice_source == "API에서 불러오기":
            if st.button("목소리 목록 불러오기", disabled=not elevenlabs_key, key="fetch_el_voices"):
                with st.spinner("ElevenLabs 목소리 목록 가져오는 중..."):
                    try:
                        from utils.elevenlabs_client import ElevenLabsClient
                        el_client = ElevenLabsClient(api_key=elevenlabs_key)
                        voices = el_client.list_voices()
                        st.session_state["el_voices"] = voices
                        st.rerun()
                    except Exception as e:
                        st.error(f"목소리 목록 오류: {e}")

            if "el_voices" in st.session_state and st.session_state["el_voices"]:
                voice_list = st.session_state["el_voices"]
                voice_labels = [f"{v['name']} ({v['voice_id'][:8]}...)" for v in voice_list]
                selected_label = st.selectbox("목소리", voice_labels, label_visibility="collapsed")
                selected_idx = voice_labels.index(selected_label)
                el_voice_id = voice_list[selected_idx]["voice_id"]
                el_voice_name = voice_list[selected_idx]["name"]
                st.session_state["el_voice_id"] = el_voice_id
                st.session_state["el_voice_name"] = el_voice_name
            else:
                st.caption("목록 불러오기 버튼을 클릭하세요.")
                el_voice_id = st.session_state.get("el_voice_id", "")
                el_voice_name = st.session_state.get("el_voice_name", "")
        else:
            el_voice_id = st.text_input(
                "Voice ID",
                value=st.session_state.get("el_voice_id", ""),
                placeholder="ElevenLabs 대시보드에서 복사한 Voice ID",
                label_visibility="collapsed",
            )
            st.session_state["el_voice_id"] = el_voice_id
            el_voice_name = el_voice_id

    with col_el_opts:
        st.markdown("**생성 설정**")
        el_model = st.selectbox(
            "모델",
            ["eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_flash_v2_5"],
            help="multilingual_v2: 고품질 / turbo_v2_5: 빠름 / flash_v2_5: 가장 빠름",
        )
        el_stability = st.slider("Stability", 0.0, 1.0, 0.5, 0.05,
                                 help="높을수록 일관된 톤. 낮을수록 표현력 풍부.")
        el_similarity = st.slider("Similarity Boost", 0.0, 1.0, 0.75, 0.05,
                                  help="높을수록 원본 목소리에 가깝게.")
        el_chunk_size = st.select_slider(
            "청크 크기",
            options=[300, 500, 800, 1000, 2000],
            value=st.session_state.get("el_chunk_size", 1000),
        )
        st.session_state["el_chunk_size"] = el_chunk_size

st.divider()

# ─────────────────────────────────────────────
# ③ 출력 설정
# ─────────────────────────────────────────────
st.subheader("③ 출력 설정")

col_out1, col_out2, col_out3 = st.columns(3)
with col_out1:
    proj_name = st.session_state.get("project_name", "")
    output_filename = st.text_input(
        "출력 파일 이름",
        value=f"{proj_name}_audio" if proj_name else "audio",
        help=".wav 확장자가 자동으로 붙습니다.",
    )
with col_out2:
    # 어느 탭이 마지막으로 선택됐는지 추적 (Streamlit은 탭 선택 상태를 알 수 없으므로 별도 라디오로 엔진 선택)
    final_engine = st.radio(
        "사용할 TTS 엔진",
        ["Gemini TTS", "ElevenLabs"],
        horizontal=True,
        index=0 if not elevenlabs_key else st.session_state.get("_engine_radio_idx", 0),
        key="_engine_radio",
    )
    st.session_state["_engine_radio_idx"] = ["Gemini TTS", "ElevenLabs"].index(final_engine)

with col_out3:
    st.markdown("&nbsp;")
    split_by_scene = st.checkbox(
        "장면별 개별 파일 생성",
        value=False,
        help="체크 시 각 장면 나레이션을 별도 .wav 파일로 저장합니다. (영상 합성 시 유용)",
    )

st.divider()

# ─────────────────────────────────────────────
# ④ 음성 생성
# ─────────────────────────────────────────────
st.subheader("④ 음성 생성")

engine_ready = (final_engine == "Gemini TTS" and bool(gemini_key)) or \
               (final_engine == "ElevenLabs" and bool(elevenlabs_key))

if not engine_ready:
    st.warning(f"{final_engine}의 API 키를 config.yaml에 설정해 주세요.")

col_gen, col_regen = st.columns([1, 1])
with col_gen:
    gen_btn = st.button(
        "음성 생성 시작",
        type="primary",
        disabled=not script or not engine_ready,
    )
with col_regen:
    regen_btn = st.button(
        "다시 생성",
        type="secondary",
        disabled=not script or not engine_ready or "audio_path" not in st.session_state,
    )

if gen_btn or regen_btn:
    # 출력 디렉터리 결정
    if proj_name:
        audio_dir = pm.get_audio_dir(proj_name)
    else:
        audio_dir = os.path.join(ROOT, "projects", "_temp", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    output_path = os.path.join(audio_dir, f"{output_filename}.wav")

    if final_engine == "Gemini TTS":
        # 스타일 지시 프롬프트 접두어
        style_prefix_map = {
            "기본": "",
            "차분한 내레이션": "Read in a calm, clear narration style. ",
            "뉴스 앵커": "Read in a professional news anchor style. ",
            "활기찬 유튜버": "Read in an energetic, engaging YouTube style. ",
            "감정적 스토리텔링": "Read with emotional storytelling, varying pace and tone. ",
        }
        style_prefix = style_prefix_map.get(gemini_speech_style, "")
        tts_text = style_prefix + script if style_prefix else script

        from utils.gemini_client import GeminiClient
        client = GeminiClient(api_key=gemini_key, config=config)

        chunks = [tts_text[i:i + gemini_chunk_size]
                  for i in range(0, len(tts_text), gemini_chunk_size)]
        total = len(chunks)

        progress_bar = st.progress(0, text=f"청크 0 / {total} 생성 중...")
        status_area = st.empty()

        try:
            audio_path = client.generate_tts_chunked(
                text=tts_text,
                voice=gemini_voice_id,
                chunk_size=gemini_chunk_size,
                output_path=output_path,
                progress_callback=lambda done, total_n, msg: (
                    progress_bar.progress(done / total_n, text=msg)
                ),
            )
            progress_bar.empty()
            status_area.empty()
            st.session_state["audio_path"] = audio_path
            st.success("✅ 음성 생성 완료!")
            st.rerun()
        except Exception as e:
            progress_bar.empty()
            st.error(f"Gemini TTS 오류: {e}")

    else:  # ElevenLabs
        if not el_voice_id:
            st.error("ElevenLabs Voice ID를 설정해 주세요.")
        else:
            from utils.elevenlabs_client import ElevenLabsClient
            el_client = ElevenLabsClient(api_key=elevenlabs_key)

            chunks = [script[i:i + el_chunk_size]
                      for i in range(0, len(script), el_chunk_size)]
            total = len(chunks)

            progress_bar = st.progress(0, text=f"청크 0 / {total} 생성 중...")

            try:
                audio_path = el_client.generate_tts_chunked(
                    text=script,
                    voice_id=el_voice_id,
                    model_id=el_model,
                    stability=el_stability,
                    similarity_boost=el_similarity,
                    chunk_size=el_chunk_size,
                    output_path=output_path,
                    progress_callback=lambda done, total_n, msg: (
                        progress_bar.progress(done / total_n, text=msg)
                    ),
                )
                progress_bar.empty()
                st.session_state["audio_path"] = audio_path
                st.success("✅ ElevenLabs 음성 생성 완료!")
                st.rerun()
            except Exception as e:
                progress_bar.empty()
                st.error(f"ElevenLabs TTS 오류: {e}")

# ─────────────────────────────────────────────
# ⑤ 결과 & 저장
# ─────────────────────────────────────────────
if "audio_path" in st.session_state:
    audio_path = st.session_state["audio_path"]
    if os.path.exists(audio_path):
        st.divider()
        st.subheader("⑤ 결과")

        info = audio_file_info(audio_path)
        if info:
            c1, c2, c3 = st.columns(3)
            c1.metric("파일 크기", f"{info['size_mb']:.1f} MB")
            minutes = int(info["duration_sec"] // 60)
            seconds = int(info["duration_sec"] % 60)
            c2.metric("음성 길이", f"{minutes}분 {seconds}초")
            c3.metric("파일", os.path.basename(audio_path))

        st.audio(audio_path)

        col_dl, col_save, col_next = st.columns(3)
        with col_dl:
            with open(audio_path, "rb") as f:
                st.download_button(
                    "📥 오디오 다운로드",
                    data=f,
                    file_name=os.path.basename(audio_path),
                    mime="audio/wav",
                )
        with col_save:
            if proj_name:
                st.success(f"`projects/{proj_name}/audio/` 에 자동 저장됨")
            else:
                st.caption("1단계에서 프로젝트 이름을 설정하면 자동 저장됩니다.")
        with col_next:
            st.page_link("pages/4_최종영상.py", label="4단계: 최종 영상으로 이동 →", icon="🎬")

st.divider()
col_back, _ = st.columns([1, 3])
with col_back:
    st.page_link("pages/2_장면이미지.py", label="← 2단계: 장면/이미지", icon="🖼️")
