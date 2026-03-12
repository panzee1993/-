import streamlit as st
import yaml
import os

# ─────────────────────────────────────────────
# 페이지 기본 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="유튜브 자동 제작 도구",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# config.yaml 로드
# ─────────────────────────────────────────────
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

config = load_config()

# ─────────────────────────────────────────────
# API 키 상태 확인
# ─────────────────────────────────────────────
def check_api_keys(config):
    gemini_key = config.get("api", {}).get("gemini_api_key", "")
    elevenlabs_key = config.get("api", {}).get("elevenlabs_api_key", "")
    youtube_path = config.get("api", {}).get("youtube_client_secret_path", "")

    return {
        "gemini": bool(gemini_key and gemini_key.strip()),
        "elevenlabs": bool(elevenlabs_key and elevenlabs_key.strip()),
        "youtube": os.path.exists(youtube_path) if youtube_path else False,
    }

api_status = check_api_keys(config)

# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🎬 유튜브 자동 제작")
    st.caption("롱폼 영상 자동화 파이프라인")
    st.divider()

    st.subheader("API 연결 상태")
    st.write("Gemini API", "✅" if api_status["gemini"] else "❌ 미설정")
    st.write("ElevenLabs", "✅" if api_status["elevenlabs"] else "⚪ 미설정 (선택)")
    st.write("YouTube API", "✅" if api_status["youtube"] else "❌ 미설정")

    if not api_status["gemini"]:
        st.warning("config.yaml에 Gemini API 키를 입력하세요.")

    st.divider()
    st.subheader("진행 단계")
    steps = [
        ("1단계", "대본 작성", "pages/1_대본.py"),
        ("2단계", "장면/이미지", "pages/2_장면이미지.py"),
        ("3단계", "음성 생성", "pages/3_음성.py"),
        ("4단계", "최종 영상", "pages/4_최종영상.py"),
        ("5단계", "썸네일/업로드", "pages/5_썸네일업로드.py"),
    ]
    for step_num, step_name, _ in steps:
        st.write(f"**{step_num}** {step_name}")

    st.divider()
    st.caption("v0.1.0 · Phase 1 완료")

# ─────────────────────────────────────────────
# 메인 화면
# ─────────────────────────────────────────────
st.title("🎬 유튜브 롱폼 자동 제작 도구")
st.markdown("대본 작성부터 유튜브 업로드까지 — **5단계 파이프라인**으로 자동화")

st.divider()

# 5단계 탭
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 1단계: 대본 작성",
    "🖼️ 2단계: 장면/이미지",
    "🔊 3단계: 음성 생성",
    "🎬 4단계: 최종 영상",
    "🚀 5단계: 썸네일/업로드",
])

# ── 1단계 탭 ──────────────────────────────────
with tab1:
    st.header("📝 1단계: 대본 작성")
    st.markdown("Gemini AI가 벤치마킹 대본을 분석하고 스크립트를 자동 생성합니다.")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("주요 기능")
        st.markdown("""
- 프로젝트 이름 설정
- 롱폼 / 쇼츠 선택
- 분량(분) 설정
- 벤치마킹 대본 → AI 주제 추천
- 주제 선택 → 스크립트 자동 생성
- 하우스 스타일 가이드 자동 적용
        """)
    with col2:
        st.info("**하우스 스타일 가이드**\n\n- 한 줄 100~200자\n- 150줄 이하\n- 도입부 위기감\n- 반말 친근체")

    st.page_link("pages/1_대본.py", label="1단계로 이동 →", icon="📝")

# ── 2단계 탭 ──────────────────────────────────
with tab2:
    st.header("🖼️ 2단계: 장면/이미지")
    st.markdown("스크립트를 장면 단위로 분할하고, AI로 이미지를 생성합니다.")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("주요 기능")
        st.markdown("""
- 스크립트 자동 장면 분할
- 장면별 이미지 프롬프트 생성
- 스타일 선택 (K웹툰 실사 / 실사 / 3D 애니메이션)
- 캐릭터 일관성 설정 (char_1, char_2)
- 이미지 생성 미리보기
- 개별 이미지 재생성
        """)
    with col2:
        st.info("**지원 스타일**\n\n- K웹툰 실사\n- 실사 사진\n- 3D 애니메이션\n- 커스텀 프리셋")

    st.page_link("pages/2_장면이미지.py", label="2단계로 이동 →", icon="🖼️")

# ── 3단계 탭 ──────────────────────────────────
with tab3:
    st.header("🔊 3단계: 음성 생성")
    st.markdown("대본을 자연스러운 한국어 음성으로 변환합니다.")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("주요 기능")
        st.markdown("""
- TTS 엔진 선택 (Gemini / ElevenLabs)
- 남성 / 여성 목소리 선택
- 음성 속도 조절 (1.0x ~ 1.5x)
- 말투 스타일 설정
- 500자 자동 분할 옵션
- 오디오 미리듣기
        """)
    with col2:
        st.info("**TTS 엔진**\n\n- **Gemini TTS** (무료)\n  Kore, Aoede 등\n- **ElevenLabs** (유료)\n  고품질 한국어")

    st.page_link("pages/3_음성.py", label="3단계로 이동 →", icon="🔊")

# ── 4단계 탭 ──────────────────────────────────
with tab4:
    st.header("🎬 4단계: 최종 영상")
    st.markdown("이미지 + 음성 + 자막을 합성하여 MP4 영상을 만듭니다.")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("주요 기능")
        st.markdown("""
- 이미지 + 음성 + 자막 합성 (FFmpeg/MoviePy)
- 자막 폰트 / 크기 / 위치 설정
- 배경음악 추가 (선택)
- 효과음 추가 (선택)
- 1920×1080 MP4 출력 (24fps)
- 영상 미리보기
        """)
    with col2:
        st.info("**출력 규격**\n\n- 해상도: 1920×1080\n- FPS: 24\n- 코덱: H.264\n- 포맷: MP4")

    st.page_link("pages/4_최종영상.py", label="4단계로 이동 →", icon="🎬")

# ── 5단계 탭 ──────────────────────────────────
with tab5:
    st.header("🚀 5단계: 썸네일/업로드")
    st.markdown("썸네일을 생성하고 유튜브에 자동 업로드합니다.")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("주요 기능")
        st.markdown("""
- 대본에서 썸네일 문구 4개 자동 추출
- 참조 이미지 업로드 (선택)
- AI 썸네일 생성 (16:9 / 9:16)
- 유튜브 자동 업로드
- 제목 / 설명 / 태그 자동 생성
- 비공개로 먼저 올리고 확인 후 공개
        """)
    with col2:
        st.info("**업로드 설정**\n\n- 기본값: 비공개\n- 카테고리: 자동 설정\n- 썸네일: 자동 등록\n- OAuth 인증 필요")

    st.page_link("pages/5_썸네일업로드.py", label="5단계로 이동 →", icon="🚀")

# ─────────────────────────────────────────────
# 빠른 시작 안내
# ─────────────────────────────────────────────
st.divider()
st.subheader("빠른 시작 방법")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**1. API 키 설정**")
    st.code("config.yaml\n→ gemini_api_key: 입력", language="yaml")

with col2:
    st.markdown("**2. 패키지 설치**")
    st.code("pip install -r requirements.txt", language="bash")

with col3:
    st.markdown("**3. 앱 실행**")
    st.code("streamlit run app.py", language="bash")
