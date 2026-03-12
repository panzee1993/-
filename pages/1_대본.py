import streamlit as st
import yaml
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.project_manager import ProjectManager

st.set_page_config(page_title="1단계: 대본 작성", page_icon="📝", layout="wide")

# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(__file__))

def load_config() -> dict:
    with open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_gemini_client(config: dict):
    from utils.gemini_client import GeminiClient
    key = config.get("api", {}).get("gemini_api_key", "").strip()
    if not key:
        return None, "config.yaml에 Gemini API 키를 먼저 설정해 주세요."
    try:
        return GeminiClient(api_key=key, config=config), None
    except Exception as e:
        return None, str(e)

def script_stats(text: str) -> dict:
    """스크립트 통계 및 스타일 가이드 준수 여부 반환"""
    if not text.strip():
        return {}
    lines = [l for l in text.split("\n") if l.strip()]
    char_count = len(text.replace("\n", ""))
    line_lengths = [len(l) for l in lines]
    long_lines = [l for l in line_lengths if l > 200]
    short_lines = [l for l in line_lengths if l < 100]
    return {
        "char_count": char_count,
        "line_count": len(lines),
        "estimated_min": char_count / 385,
        "long_lines": len(long_lines),
        "short_lines": len(short_lines),
        "avg_line_len": sum(line_lengths) / len(line_lengths) if line_lengths else 0,
    }

# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
config = load_config()
gemini_key = config.get("api", {}).get("gemini_api_key", "").strip()

st.title("📝 1단계: 대본 작성")

# API 키 미설정 경고 배너
if not gemini_key:
    st.warning("**Gemini API 키가 설정되지 않았습니다.** `config.yaml`의 `gemini_api_key`를 입력해야 AI 기능을 사용할 수 있습니다.  \n직접 주제를 입력하고 스크립트를 붙여넣는 방식으로도 사용 가능합니다.")

st.divider()

# ─────────────────────────────────────────────
# STEP 1 : 프로젝트 설정
# ─────────────────────────────────────────────
st.subheader("① 프로젝트 설정")

col1, col2, col3, col4 = st.columns([2, 1, 1, 2])

with col1:
    project_name = st.text_input(
        "프로젝트 이름",
        value=st.session_state.get("project_name", ""),
        placeholder="예: 이순신_위기의_조선",
        help="한글·영문·숫자·언더스코어 권장. 저장 폴더명으로 사용됩니다.",
    )

with col2:
    content_type = st.radio(
        "영상 유형",
        ["롱폼", "쇼츠"],
        index=0 if st.session_state.get("content_type", "롱폼") == "롱폼" else 1,
        horizontal=True,
    )

with col3:
    if content_type == "롱폼":
        duration = st.number_input("길이 (분)", min_value=3, max_value=30,
                                   value=st.session_state.get("duration", 15))
        duration_unit = "분"
    else:
        duration = st.number_input("길이 (초)", min_value=15, max_value=60,
                                   value=st.session_state.get("duration", 60))
        duration_unit = "초"

with col4:
    category = st.selectbox(
        "카테고리",
        ["역사/인물", "물건/발명", "음식/요리", "여행지", "IT/기술", "자연/과학", "사건/사고", "기타"],
        index=["역사/인물", "물건/발명", "음식/요리", "여행지", "IT/기술", "자연/과학", "사건/사고", "기타"]
              .index(st.session_state.get("category", "역사/인물")),
    )

# 세션에 설정값 유지
st.session_state["project_name"] = project_name
st.session_state["content_type"] = content_type
st.session_state["duration"] = duration
st.session_state["category"] = category

st.divider()

# ─────────────────────────────────────────────
# STEP 2 : 벤치마킹 + 주제 추천
# ─────────────────────────────────────────────
st.subheader("② 주제 선택")

tab_recommend, tab_manual = st.tabs(["🤖 AI 주제 추천", "✏️ 직접 입력"])

with tab_recommend:
    st.caption("참고할 유튜브 대본을 붙여넣으면 AI가 분석해서 비슷한 주제 10개를 추천합니다. 대본 없이도 카테고리 기반으로 추천 가능합니다.")
    benchmark = st.text_area(
        "벤치마킹 대본 (선택 — 없으면 비워두세요)",
        height=120,
        placeholder="참고 대본을 여기 붙여넣으세요.\n없으면 비워두면 카테고리 기반으로 추천해 줍니다.",
        key="benchmark_input",
    )

    col_rec_btn, col_rec_count = st.columns([1, 2])
    with col_rec_btn:
        recommend_btn = st.button(
            "주제 추천 받기",
            type="primary",
            disabled=not gemini_key,
            help="Gemini API 키가 필요합니다." if not gemini_key else "",
        )
    with col_rec_count:
        rec_count = st.slider("추천 개수", min_value=5, max_value=20, value=10, label_visibility="collapsed")

    if recommend_btn:
        client, err = get_gemini_client(config)
        if err:
            st.error(err)
        else:
            with st.spinner("Gemini가 주제를 분석 중입니다..."):
                try:
                    topics = client.recommend_topics(
                        benchmark_script=benchmark,
                        category=category,
                        content_type=content_type,
                        count=rec_count,
                    )
                    st.session_state["recommended_topics"] = topics
                    st.session_state["selected_topic"] = topics[0] if topics else ""
                    st.rerun()
                except Exception as e:
                    st.error(f"오류: {e}")

    # 추천 주제 목록 표시
    if "recommended_topics" in st.session_state:
        topics = st.session_state["recommended_topics"]
        st.markdown(f"**추천 주제 {len(topics)}개** — 클릭해서 선택하세요")

        # 라디오로 선택
        current = st.session_state.get("selected_topic", topics[0] if topics else "")
        current_idx = topics.index(current) if current in topics else 0
        selected = st.radio(
            "주제 선택",
            topics,
            index=current_idx,
            label_visibility="collapsed",
        )
        st.session_state["selected_topic"] = selected

        if st.button("추천 목록 초기화", type="secondary"):
            del st.session_state["recommended_topics"]
            st.session_state.pop("selected_topic", None)
            st.rerun()

with tab_manual:
    manual_topic = st.text_input(
        "주제 직접 입력",
        value=st.session_state.get("selected_topic", "") if "recommended_topics" not in st.session_state else "",
        placeholder="예: 조선 최고의 명장 이순신이 사실 처형 직전까지 갔던 이유",
        label_visibility="collapsed",
    )
    if manual_topic:
        st.session_state["selected_topic"] = manual_topic

# 현재 선택된 주제 표시
selected_topic = st.session_state.get("selected_topic", "")
if selected_topic:
    st.success(f"선택된 주제: **{selected_topic}**")

st.divider()

# ─────────────────────────────────────────────
# STEP 3 : 스크립트 생성
# ─────────────────────────────────────────────
st.subheader("③ 스크립트 생성")

with st.expander("스타일 가이드 설정 (고급)", expanded=False):
    col_sg1, col_sg2 = st.columns(2)
    with col_sg1:
        sg_min_chars = st.number_input("한 줄 최소 글자", value=100, min_value=50, max_value=150)
        sg_max_chars = st.number_input("한 줄 최대 글자", value=200, min_value=150, max_value=300)
        sg_max_lines = st.number_input("최대 줄 수", value=150, min_value=50, max_value=300)
    with col_sg2:
        sg_tone = st.selectbox("톤", ["반말 친근체 (형/누나)", "반말 강의체", "존댓말 친근체", "존댓말 격식체"])
        sg_opening = st.selectbox("도입부 스타일", ["위기감/충격 강조", "호기심 자극", "질문으로 시작", "통계/수치 시작"])
        sg_ending = st.checkbox("마지막에 구독/좋아요 유도 멘트 포함", value=True)

col_gen, col_regen = st.columns([1, 1])
with col_gen:
    generate_btn = st.button(
        "스크립트 생성",
        type="primary",
        disabled=not selected_topic or not gemini_key,
        help="주제를 먼저 선택하고 Gemini API 키를 설정해 주세요." if not selected_topic else "",
    )
with col_regen:
    regen_btn = st.button(
        "다시 생성",
        type="secondary",
        disabled=not selected_topic or not gemini_key or "generated_script" not in st.session_state,
    )

if generate_btn or regen_btn:
    client, err = get_gemini_client(config)
    if err:
        st.error(err)
    else:
        style_guide = {
            "min_chars": sg_min_chars,
            "max_chars": sg_max_chars,
            "max_lines": sg_max_lines,
            "tone": sg_tone,
            "opening": sg_opening,
            "ending": sg_ending,
        }
        with st.spinner(f"Gemini가 스크립트를 작성 중입니다... ({duration}{duration_unit} 분량, 30초~1분 소요)"):
            try:
                script = client.generate_script(
                    topic=selected_topic,
                    duration=duration,
                    content_type=content_type,
                    category=category,
                    style_guide=style_guide,
                )
                st.session_state["generated_script"] = script
                st.session_state["final_script"] = script
                st.rerun()
            except Exception as e:
                st.error(f"스크립트 생성 오류: {e}")

# ─────────────────────────────────────────────
# STEP 4 : 스크립트 편집 & 저장
# ─────────────────────────────────────────────
if "generated_script" in st.session_state or "final_script" in st.session_state:
    st.divider()
    st.subheader("④ 스크립트 편집 & 저장")

    current_script = st.session_state.get("final_script", st.session_state.get("generated_script", ""))

    edited_script = st.text_area(
        "스크립트 (직접 수정 가능)",
        value=current_script,
        height=500,
        label_visibility="collapsed",
        key="script_editor",
    )
    # 편집 내용 즉시 반영
    st.session_state["final_script"] = edited_script

    # ── 통계 & 스타일 가이드 준수 체크 ──────────────
    stats = script_stats(edited_script)
    if stats:
        st.markdown("**스타일 가이드 체크**")
        m1, m2, m3, m4, m5 = st.columns(5)

        m1.metric("총 글자 수", f"{stats['char_count']:,}자")
        m2.metric("총 줄 수", f"{stats['line_count']}줄",
                  delta="OK" if stats['line_count'] <= 150 else f"+{stats['line_count']-150} 초과",
                  delta_color="normal" if stats['line_count'] <= 150 else "inverse")
        m3.metric("예상 시간", f"{stats['estimated_min']:.1f}분")
        m4.metric("200자 초과 줄",
                  f"{stats['long_lines']}줄",
                  delta="OK" if stats['long_lines'] == 0 else f"{stats['long_lines']}줄 수정 필요",
                  delta_color="normal" if stats['long_lines'] == 0 else "inverse")
        m5.metric("평균 줄 길이", f"{stats['avg_line_len']:.0f}자")

        # 경고 메시지
        warnings = []
        if stats["line_count"] > 150:
            warnings.append(f"줄 수가 {stats['line_count']}개로 150개를 초과합니다.")
        if stats["long_lines"] > 0:
            warnings.append(f"한 줄 200자를 초과하는 줄이 {stats['long_lines']}개 있습니다.")
        if stats["short_lines"] > 5:
            warnings.append(f"한 줄 100자 미만인 줄이 {stats['short_lines']}개 있습니다.")

        if warnings:
            for w in warnings:
                st.warning(w)
        else:
            st.success("스타일 가이드 준수 완료!")

    st.divider()

    # ── 저장 / 다운로드 / 다음 단계 ─────────────────
    col_save, col_dl, col_next = st.columns(3)

    with col_save:
        save_disabled = not project_name
        if st.button("💾 프로젝트 저장", type="primary", disabled=save_disabled,
                     help="프로젝트 이름을 위에서 먼저 입력해 주세요." if save_disabled else ""):
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
            st.session_state["saved_project"] = project_name
            st.success(f"`projects/{project_name}/` 에 저장되었습니다.")

    with col_dl:
        filename = f"{project_name or 'script'}.txt"
        st.download_button(
            "📄 .txt 다운로드",
            data=edited_script.encode("utf-8"),
            file_name=filename,
            mime="text/plain",
        )

    with col_next:
        st.page_link("pages/2_장면이미지.py", label="2단계: 장면/이미지 →", icon="🖼️")
