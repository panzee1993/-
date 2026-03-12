import streamlit as st
import yaml
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

st.set_page_config(page_title="5단계: 썸네일/업로드", page_icon="🚀", layout="wide")

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()

st.title("🚀 5단계: 썸네일 생성 & 유튜브 업로드")
st.markdown("썸네일을 AI로 생성하고 유튜브에 자동 업로드합니다.")
st.divider()

# ─── 탭 구성 ─────────────────────────────────
thumb_tab, upload_tab = st.tabs(["🖼️ 썸네일 생성", "📤 유튜브 업로드"])

# ════════════════════════════════════════════
# 썸네일 탭
# ════════════════════════════════════════════
with thumb_tab:
    st.subheader("썸네일 문구")
    script = st.session_state.get("final_script", "")

    col_extract, _ = st.columns([1, 4])
    with col_extract:
        extract_btn = st.button(
            "대본에서 문구 추출",
            type="primary",
            disabled=not script,
        )

    if extract_btn:
        gemini_key = config.get("api", {}).get("gemini_api_key", "")
        if not gemini_key:
            st.error("config.yaml에 Gemini API 키를 먼저 설정해 주세요.")
        else:
            with st.spinner("썸네일 문구를 추출 중..."):
                try:
                    from utils.gemini_client import GeminiClient
                    client = GeminiClient(api_key=gemini_key, config=config)
                    phrases = client.extract_thumbnail_phrases(script)
                    st.session_state["thumbnail_phrases"] = phrases
                    st.success("문구 추출 완료!")
                except Exception as e:
                    st.error(f"오류: {e}")

    # 문구 선택
    phrases = st.session_state.get("thumbnail_phrases", [
        "직접 입력하기",
    ])

    col1, col2 = st.columns(2)
    with col1:
        thumb_text_main = st.text_input("메인 문구", placeholder="예: 처형 직전까지 간 이순신")
    with col2:
        thumb_text_sub = st.text_input("서브 문구", placeholder="예: 조선 최고의 명장, 그 진실")

    st.markdown("**추출된 문구 (선택하면 자동 입력)**")
    if len(phrases) > 1:
        for phrase in phrases:
            st.write(f"• {phrase}")

    st.divider()
    st.subheader("썸네일 이미지 생성")

    col_style, col_ref = st.columns(2)
    with col_style:
        thumb_size = st.radio("비율", ["16:9 (유튜브 기본)", "9:16 (쇼츠)"], horizontal=True)
        thumb_style = st.selectbox(
            "썸네일 스타일",
            ["실사 + 임팩트 텍스트", "K웹툰 실사", "충격적인 얼굴 클로즈업", "다큐멘터리 스타일"],
        )
    with col_ref:
        ref_image = st.file_uploader("참조 이미지 (선택)", type=["jpg", "jpeg", "png"])
        if ref_image:
            st.image(ref_image, caption="참조 이미지", width=200)

    col_gen, _ = st.columns([1, 4])
    with col_gen:
        thumb_gen_btn = st.button(
            "썸네일 생성",
            type="primary",
            disabled=not (thumb_text_main or thumb_text_sub),
        )

    if thumb_gen_btn:
        gemini_key = config.get("api", {}).get("gemini_api_key", "")
        if not gemini_key:
            st.error("config.yaml에 Gemini API 키를 먼저 설정해 주세요.")
        else:
            with st.spinner("썸네일을 생성 중..."):
                try:
                    from utils.gemini_client import GeminiClient
                    client = GeminiClient(api_key=gemini_key, config=config)
                    thumb_path = client.generate_thumbnail(
                        main_text=thumb_text_main,
                        sub_text=thumb_text_sub,
                        style=thumb_style,
                        size=thumb_size,
                    )
                    st.session_state["thumbnail_path"] = thumb_path
                    st.success("썸네일 생성 완료!")
                except Exception as e:
                    st.error(f"썸네일 생성 오류: {e}")

    if "thumbnail_path" in st.session_state:
        thumb_path = st.session_state["thumbnail_path"]
        if os.path.exists(thumb_path):
            st.image(thumb_path, caption="생성된 썸네일", use_column_width=True)
            with open(thumb_path, "rb") as f:
                st.download_button("썸네일 다운로드", data=f, file_name="thumbnail.jpg", mime="image/jpeg")

# ════════════════════════════════════════════
# 업로드 탭
# ════════════════════════════════════════════
with upload_tab:
    st.subheader("업로드 정보 설정")

    video_path = st.session_state.get("output_video_path", "")
    thumb_path = st.session_state.get("thumbnail_path", "")

    col_check1, col_check2 = st.columns(2)
    with col_check1:
        if video_path and os.path.exists(video_path):
            st.success(f"영상 준비됨: {os.path.basename(video_path)}")
        else:
            st.error("4단계에서 영상을 먼저 합성해 주세요.")
    with col_check2:
        if thumb_path and os.path.exists(thumb_path):
            st.success("썸네일 준비됨")
        else:
            st.warning("썸네일이 없습니다. (선택 사항)")

    st.divider()

    video_title = st.text_input(
        "영상 제목",
        placeholder="예: [충격] 처형 직전까지 간 이순신, 그 비밀은?",
    )
    video_description = st.text_area(
        "영상 설명",
        height=120,
        placeholder="영상 설명을 입력하세요.\n\n#이순신 #조선역사 #역사채널",
    )
    video_tags_input = st.text_input(
        "태그 (쉼표로 구분)",
        placeholder="이순신, 조선역사, 역사채널, 한국사",
    )
    video_tags = [t.strip() for t in video_tags_input.split(",") if t.strip()]

    col1, col2 = st.columns(2)
    with col1:
        privacy = st.radio("공개 범위", ["비공개 (확인 후 수동 공개 권장)", "미등록", "공개"], horizontal=False)
        privacy_map = {"비공개 (확인 후 수동 공개 권장)": "private", "미등록": "unlisted", "공개": "public"}
        privacy_status = privacy_map[privacy]

    with col2:
        category = st.selectbox(
            "카테고리",
            ["People & Blogs (22)", "Education (27)", "Entertainment (24)", "Science & Tech (28)"],
        )
        category_id = category.split("(")[1].rstrip(")")

    st.divider()

    # YouTube OAuth 설정 안내
    secret_path = config.get("api", {}).get("youtube_client_secret_path", "client_secret.json")
    if not os.path.exists(secret_path):
        st.warning(f"""
**YouTube API 설정이 필요합니다.**

1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. YouTube Data API v3 활성화
3. OAuth 2.0 클라이언트 ID 생성
4. `{secret_path}` 로 저장
        """)

    ready_to_upload = (
        bool(video_title)
        and bool(video_path and os.path.exists(video_path))
        and os.path.exists(secret_path)
    )

    col_upload, _ = st.columns([1, 4])
    with col_upload:
        upload_btn = st.button("유튜브 업로드", type="primary", disabled=not ready_to_upload)

    if upload_btn:
        with st.spinner("유튜브에 업로드 중... (영상 크기에 따라 수 분 소요)"):
            try:
                from utils.youtube_uploader import YouTubeUploader
                uploader = YouTubeUploader(client_secret_path=secret_path)
                result = uploader.upload(
                    video_path=video_path,
                    title=video_title,
                    description=video_description,
                    tags=video_tags,
                    category_id=category_id,
                    privacy=privacy_status,
                    thumbnail_path=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                )
                video_id = result.get("id", "")
                st.success(f"업로드 완료! 영상 ID: `{video_id}`")
                if video_id:
                    st.markdown(f"[유튜브에서 보기](https://www.youtube.com/watch?v={video_id})")
            except Exception as e:
                st.error(f"업로드 오류: {e}")

st.divider()
st.page_link("pages/4_최종영상.py", label="← 4단계: 최종 영상", icon="🎬")
