"""5단계: 썸네일 생성 & 유튜브 업로드

탭 구성:
  Tab 1. 썸네일 생성  — Gemini로 썸네일 생성 / 직접 업로드
  Tab 2. 유튜브 업로드 — 메타데이터 입력 + OAuth 인증 + 업로드 진행률
"""

import glob as glob_module
import os
import sys

import streamlit as st
import yaml

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

st.set_page_config(page_title="5단계: 썸네일/업로드", page_icon="🚀", layout="wide")


# ─── 설정 로딩 ────────────────────────────────────────────────────────────────

def load_config() -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config()
gemini_key: str = config.get("api", {}).get("gemini_api_key", "")
secret_path: str = config.get("api", {}).get("youtube_client_secret_path", "client_secret.json")

# ─── 헤더 ────────────────────────────────────────────────────────────────────

st.title("🚀 5단계: 썸네일 생성 & 유튜브 업로드")
st.markdown("썸네일을 AI로 생성하고 유튜브에 자동 업로드합니다.")
st.divider()

# ─── 프로젝트 확인 ───────────────────────────────────────────────────────────

from utils.project_manager import ProjectManager

pm = ProjectManager()

if not st.session_state.get("project_name"):
    projects = pm.list_projects()
    if not projects:
        st.warning("1단계에서 프로젝트를 먼저 생성해 주세요.")
        st.stop()
    col_s, col_b = st.columns([3, 1])
    with col_s:
        selected = st.selectbox("프로젝트 선택", projects)
    with col_b:
        st.write("")
        if st.button("불러오기", type="primary"):
            st.session_state["project_name"] = selected
            st.rerun()
    st.stop()

project_name: str = st.session_state["project_name"]
st.caption(f"현재 프로젝트: **{project_name}**")

# 세션에 없으면 프로젝트 폴더에서 최신 파일 자동 로딩
script: str = st.session_state.get("final_script", "")
if not script:
    script_path = os.path.join(pm._project_path(project_name), "script.txt")
    if os.path.exists(script_path):
        with open(script_path, encoding="utf-8") as f:
            script = f.read()
        st.session_state["final_script"] = script

video_path: str = st.session_state.get("output_video_path", "")
if not video_path or not os.path.exists(video_path):
    out_dir = pm.get_output_dir(project_name)
    mp4_files = sorted(
        glob_module.glob(os.path.join(out_dir, "*.mp4")),
        key=os.path.getmtime, reverse=True,
    )
    if mp4_files:
        video_path = mp4_files[0]
        st.session_state["output_video_path"] = video_path

# 출력 디렉토리
output_dir = pm.get_output_dir(project_name)
os.makedirs(output_dir, exist_ok=True)

# ─── 탭 구성 ─────────────────────────────────────────────────────────────────

thumb_tab, upload_tab = st.tabs(["🖼️ 썸네일 생성", "📤 유튜브 업로드"])


# ════════════════════════════════════════════════════════════════════════════
# Tab 1: 썸네일 생성
# ════════════════════════════════════════════════════════════════════════════

with thumb_tab:

    # ── ① 썸네일 문구 ──────────────────────────────────────────────────────
    st.subheader("① 썸네일 문구")

    col_extract, col_extract_status = st.columns([2, 5])
    with col_extract:
        extract_btn = st.button(
            "대본에서 문구 자동 추출",
            type="primary",
            disabled=not (script and gemini_key),
            use_container_width=True,
        )
    with col_extract_status:
        if not gemini_key:
            st.warning("config.yaml에 Gemini API 키를 설정해야 추출됩니다.")
        elif not script:
            st.info("1단계에서 대본을 먼저 작성해야 추출됩니다.")

    if extract_btn:
        with st.spinner("대본에서 썸네일 문구를 추출 중..."):
            try:
                from utils.gemini_client import GeminiClient
                gc = GeminiClient(api_key=gemini_key, config=config)
                phrases = gc.extract_thumbnail_phrases(script)
                st.session_state["thumbnail_phrases"] = phrases
                st.success(f"문구 {len(phrases)}개 추출 완료!")
            except Exception as e:
                st.error(f"추출 오류: {e}")

    # 추출된 문구 목록 — 클릭하면 메인/서브 자동 입력
    phrases: list = st.session_state.get("thumbnail_phrases", [])
    if phrases:
        st.markdown("**추출된 문구 — 버튼을 눌러 입력란에 자동 입력**")
        for i, phrase in enumerate(phrases):
            p_col, m_col, s_col = st.columns([5, 1, 1])
            with p_col:
                st.markdown(f"**{i + 1}.** {phrase}")
            with m_col:
                if st.button("메인으로", key=f"main_{i}", use_container_width=True):
                    st.session_state["thumb_main"] = phrase
                    st.rerun()
            with s_col:
                if st.button("서브로", key=f"sub_{i}", use_container_width=True):
                    st.session_state["thumb_sub"] = phrase
                    st.rerun()
        st.write("")

    col_m, col_s = st.columns(2)
    with col_m:
        thumb_main = st.text_input(
            "메인 문구",
            value=st.session_state.get("thumb_main", ""),
            placeholder="예: 처형 직전까지 간 이순신",
            key="thumb_main_input",
        )
    with col_s:
        thumb_sub = st.text_input(
            "서브 문구 (선택)",
            value=st.session_state.get("thumb_sub", ""),
            placeholder="예: 조선 최고의 명장, 그 진실",
            key="thumb_sub_input",
        )

    st.divider()

    # ── ② 썸네일 스타일 설정 ──────────────────────────────────────────────
    st.subheader("② 썸네일 스타일 설정")

    col_style, col_ref = st.columns(2)
    with col_style:
        thumb_ratio = st.radio(
            "비율",
            ["16:9 (유튜브 기본)", "9:16 (쇼츠)"],
            horizontal=True,
        )
        thumb_style = st.selectbox(
            "스타일",
            [
                "실사 + 임팩트 텍스트",
                "K웹툰 실사",
                "충격적인 얼굴 클로즈업",
                "다큐멘터리 스타일",
                "일러스트",
            ],
        )

    with col_ref:
        ref_img_file = st.file_uploader(
            "참조 이미지 (선택 — 스타일 참고용)",
            type=["jpg", "jpeg", "png", "webp"],
        )
        if ref_img_file:
            st.image(ref_img_file, caption="참조 이미지", width=220)

    st.divider()

    # ── ③ 생성 / 결과 ──────────────────────────────────────────────────────
    st.subheader("③ 썸네일 생성")

    can_generate = bool(gemini_key and (thumb_main or thumb_sub))

    col_gen, col_regen = st.columns([2, 1])
    with col_gen:
        gen_btn = st.button(
            "🎨 썸네일 생성",
            type="primary",
            disabled=not can_generate,
            use_container_width=True,
        )
    with col_regen:
        regen_btn = st.button(
            "🔄 재생성",
            disabled=not (can_generate and "thumbnail_path" in st.session_state),
            use_container_width=True,
        )

    if gen_btn or regen_btn:
        if not gemini_key:
            st.error("config.yaml에 Gemini API 키를 설정해 주세요.")
        else:
            thumb_out = os.path.join(output_dir, "thumbnail.png")
            ref_bytes = ref_img_file.getvalue() if ref_img_file else None
            ref_mime = (
                f"image/{ref_img_file.type.split('/')[-1]}"
                if ref_img_file else "image/jpeg"
            )
            with st.spinner("썸네일을 생성 중... (10~30초)"):
                try:
                    from utils.gemini_client import GeminiClient
                    gc = GeminiClient(api_key=gemini_key, config=config)
                    path = gc.generate_thumbnail(
                        main_text=thumb_main,
                        sub_text=thumb_sub,
                        style=thumb_style,
                        size=thumb_ratio,
                        output_path=thumb_out,
                        ref_image_bytes=ref_bytes,
                        ref_image_mime=ref_mime,
                    )
                    st.session_state["thumbnail_path"] = path
                    st.success("썸네일 생성 완료!")
                except Exception as e:
                    st.error(f"썸네일 생성 오류: {e}")

    # 결과 미리보기
    thumb_path: str = st.session_state.get("thumbnail_path", "")
    if thumb_path and os.path.exists(thumb_path):
        st.image(thumb_path, caption="생성된 썸네일", use_column_width=True)
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            with open(thumb_path, "rb") as fh:
                ext = os.path.splitext(thumb_path)[1] or ".png"
                st.download_button(
                    "⬇️ 썸네일 다운로드",
                    data=fh,
                    file_name=f"thumbnail{ext}",
                    mime="image/png" if ext == ".png" else "image/jpeg",
                    use_container_width=True,
                )

    st.divider()

    # ── 직접 업로드 옵션 ──────────────────────────────────────────────────
    with st.expander("📁 직접 준비한 썸네일 이미지 사용"):
        manual_thumb = st.file_uploader(
            "썸네일 이미지 업로드 (JPG / PNG)",
            type=["jpg", "jpeg", "png"],
            key="manual_thumb_upload",
        )
        if manual_thumb:
            ext = os.path.splitext(manual_thumb.name)[1] or ".jpg"
            save_path = os.path.join(output_dir, f"thumbnail_manual{ext}")
            with open(save_path, "wb") as fh:
                fh.write(manual_thumb.getvalue())
            st.session_state["thumbnail_path"] = save_path
            st.image(manual_thumb, caption="업로드된 썸네일", width=320)
            st.success(f"썸네일 등록됨: `{os.path.basename(save_path)}`")


# ════════════════════════════════════════════════════════════════════════════
# Tab 2: 유튜브 업로드
# ════════════════════════════════════════════════════════════════════════════

with upload_tab:

    thumb_path = st.session_state.get("thumbnail_path", "")

    # ── ① 소재 확인 ────────────────────────────────────────────────────────
    st.subheader("① 소재 확인")

    chk_vid, chk_thumb = st.columns(2)
    with chk_vid:
        if video_path and os.path.exists(video_path):
            size_mb = os.path.getsize(video_path) / 1024 / 1024
            st.success(f"🎬 영상 {size_mb:.0f} MB 준비 완료")
            st.caption(os.path.basename(video_path))
        else:
            st.error("🎬 영상 없음 — 4단계에서 영상을 합성해 주세요.")

    with chk_thumb:
        if thumb_path and os.path.exists(thumb_path):
            st.success("🖼️ 썸네일 준비 완료")
            st.caption(os.path.basename(thumb_path))
        else:
            st.warning("🖼️ 썸네일 없음 (선택 사항)")

    st.divider()

    # ── ② 업로드 정보 ─────────────────────────────────────────────────────
    st.subheader("② 업로드 정보")

    # AI로 메타데이터 생성
    meta_col, _ = st.columns([2, 5])
    with meta_col:
        ai_meta_btn = st.button(
            "✨ AI로 제목·설명·태그 자동 생성",
            disabled=not (script and gemini_key),
            use_container_width=True,
        )

    if ai_meta_btn:
        with st.spinner("AI가 유튜브 메타데이터를 생성 중..."):
            try:
                from utils.gemini_client import GeminiClient
                gc = GeminiClient(api_key=gemini_key, config=config)
                meta = gc.generate_youtube_metadata(script=script)
                st.session_state["yt_title"] = meta.get("title", "")
                st.session_state["yt_description"] = meta.get("description", "")
                st.session_state["yt_tags"] = ", ".join(meta.get("tags", []))
                st.success("메타데이터 생성 완료! 아래 입력란에 자동 입력됐습니다.")
            except Exception as e:
                st.error(f"메타데이터 생성 오류: {e}")

    video_title = st.text_input(
        "영상 제목 *",
        value=st.session_state.get("yt_title", ""),
        placeholder="예: [충격] 처형 직전까지 간 이순신, 그 비밀은?",
        max_chars=100,
    )
    video_description = st.text_area(
        "영상 설명",
        value=st.session_state.get("yt_description", ""),
        height=130,
        placeholder="영상 설명을 입력하세요.\n\n#이순신 #조선역사 #역사채널",
        max_chars=5000,
    )
    video_tags_raw = st.text_input(
        "태그 (쉼표로 구분)",
        value=st.session_state.get("yt_tags", ""),
        placeholder="이순신, 조선역사, 역사채널, 한국사",
    )
    video_tags = [t.strip() for t in video_tags_raw.split(",") if t.strip()]

    col_priv, col_cat = st.columns(2)
    with col_priv:
        privacy_label = st.radio(
            "공개 범위",
            ["비공개 (확인 후 수동 공개 권장)", "미등록", "공개"],
        )
        privacy_map = {
            "비공개 (확인 후 수동 공개 권장)": "private",
            "미등록": "unlisted",
            "공개": "public",
        }
        privacy_status = privacy_map[privacy_label]

    with col_cat:
        category_label = st.selectbox(
            "카테고리",
            [
                "People & Blogs (22)",
                "Education (27)",
                "Entertainment (24)",
                "Science & Technology (28)",
                "News & Politics (25)",
                "Film & Animation (1)",
                "How-to & Style (26)",
            ],
        )
        category_id = category_label.split("(")[1].rstrip(")")

    st.divider()

    # ── ③ YouTube API 인증 ─────────────────────────────────────────────────
    st.subheader("③ YouTube API 인증")

    from utils.youtube_uploader import YouTubeUploader

    token_dir = pm._project_path(project_name)
    uploader = YouTubeUploader(
        client_secret_path=secret_path,
        token_dir=token_dir,
    )

    secret_exists = os.path.exists(secret_path)
    is_authed = uploader.is_authenticated()

    auth_col1, auth_col2 = st.columns(2)

    with auth_col1:
        if not secret_exists:
            st.error("❌ client_secret.json 없음")
        else:
            st.success("✅ client_secret.json 있음")

        # client_secret.json 직접 업로드
        with st.expander("📁 client_secret.json 업로드"):
            secret_upload = st.file_uploader(
                "Google Cloud Console에서 다운로드한 파일",
                type=["json"],
                key="secret_upload",
            )
            if secret_upload:
                with open(secret_path, "wb") as fh:
                    fh.write(secret_upload.getvalue())
                st.success(f"`{secret_path}` 저장 완료! 아래에서 인증을 진행하세요.")
                st.rerun()

        # OAuth 설정 가이드
        with st.expander("📖 YouTube API 설정 가이드"):
            st.markdown(f"""
1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. 프로젝트 생성 또는 선택
3. **API 및 서비스 → 라이브러리** → `YouTube Data API v3` 활성화
4. **API 및 서비스 → 사용자 인증 정보** → OAuth 2.0 클라이언트 ID 생성
   - 애플리케이션 유형: **데스크톱 앱**
5. JSON 다운로드 → 위 업로더로 업로드 (저장 위치: `{secret_path}`)
""")

    with auth_col2:
        if is_authed:
            st.success("✅ Google 계정 인증 완료")
            try:
                ch_info = uploader.get_channel_info()
                if ch_info:
                    st.info(f"채널: **{ch_info.get('title', '')}**")
            except Exception:
                pass
            if st.button("🔓 인증 취소 (재인증)", use_container_width=True):
                uploader.revoke_token()
                st.success("토큰이 삭제됐습니다. 다음 업로드 시 재인증이 필요합니다.")
                st.rerun()
        else:
            st.warning("⚠️ 아직 Google 계정 인증이 필요합니다.")
            if secret_exists:
                if st.button(
                    "🔐 Google 계정으로 인증",
                    type="primary",
                    use_container_width=True,
                ):
                    with st.spinner(
                        "브라우저에서 Google 계정 인증을 완료해 주세요... "
                        "(브라우저가 열리지 않으면 터미널 출력의 URL을 복사해 주세요)"
                    ):
                        try:
                            # _authenticate() 내부에서 브라우저 열림 + 토큰 저장
                            uploader._authenticate()
                            st.success("인증 완료!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"인증 실패: {e}")
            else:
                st.caption("먼저 client_secret.json을 업로드해 주세요.")

    st.divider()

    # ── ④ 업로드 ──────────────────────────────────────────────────────────
    st.subheader("④ 유튜브 업로드")

    ready_to_upload = (
        bool(video_title)
        and bool(video_path and os.path.exists(video_path))
        and secret_exists
        and is_authed
    )

    if not ready_to_upload:
        missing = []
        if not video_title:
            missing.append("영상 제목")
        if not (video_path and os.path.exists(video_path)):
            missing.append("영상 파일 (4단계)")
        if not secret_exists:
            missing.append("client_secret.json")
        if not is_authed:
            missing.append("Google 계정 인증")
        st.warning(f"업로드 전 필요: {' / '.join(missing)}")

    upload_btn = st.button(
        "📤 유튜브 업로드 시작",
        type="primary",
        disabled=not ready_to_upload,
        use_container_width=True,
    )

    if upload_btn:
        progress_bar = st.progress(0)
        status_text = st.empty()

        def on_progress(pct: int, msg: str):
            progress_bar.progress(min(pct, 100))
            status_text.info(f"업로드 중: {msg}")

        try:
            result = uploader.upload(
                video_path=video_path,
                title=video_title,
                description=video_description,
                tags=video_tags,
                category_id=category_id,
                privacy=privacy_status,
                thumbnail_path=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                progress_callback=on_progress,
            )

            video_id = result.get("id", "")
            progress_bar.progress(100)
            status_text.empty()

            st.success(f"✅ 업로드 완료!")
            st.balloons()

            res_col1, res_col2 = st.columns(2)
            with res_col1:
                st.metric("영상 ID", video_id)
                st.metric("공개 범위", privacy_label)
            with res_col2:
                if video_id:
                    yt_url = f"https://www.youtube.com/watch?v={video_id}"
                    st.markdown(f"### [▶️ 유튜브에서 보기]({yt_url})")
                    st.code(yt_url)

            # 프로젝트에 업로드 결과 기록
            from utils.project_manager import ProjectManager
            pm.save_script(
                project_name,
                script,
                meta={"youtube_video_id": video_id, "youtube_url": yt_url if video_id else ""},
            )

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"업로드 실패: {e}")
            with st.expander("오류 상세 보기"):
                st.code(str(e))

# ─── 네비게이션 ──────────────────────────────────────────────────────────────

st.divider()
st.page_link("pages/4_최종영상.py", label="← 4단계: 최종 영상 합성", icon="🎬")
