import streamlit as st
import yaml
import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.project_manager import ProjectManager

st.set_page_config(page_title="2단계: 장면/이미지", page_icon="🖼️", layout="wide")

ROOT = os.path.dirname(os.path.dirname(__file__))

# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────
def load_config() -> dict:
    with open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_style_preset(style_key: str) -> dict:
    path = os.path.join(ROOT, "styles", f"{style_key}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_gemini_client(config: dict):
    from utils.gemini_client import GeminiClient
    key = config.get("api", {}).get("gemini_api_key", "").strip()
    if not key:
        return None, "config.yaml에 Gemini API 키를 먼저 설정해 주세요."
    try:
        return GeminiClient(api_key=key, config=config), None
    except Exception as e:
        return None, str(e)

def save_scenes_state(scenes: list):
    """scenes 목록을 세션에 저장"""
    st.session_state["scenes"] = scenes

def scene_image_status(scenes: list) -> tuple[int, int]:
    """(이미지 완료 수, 전체 수)"""
    done = sum(1 for s in scenes if s.get("image_path") and os.path.exists(s["image_path"]))
    return done, len(scenes)

# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
config = load_config()
gemini_key = config.get("api", {}).get("gemini_api_key", "").strip()

st.title("🖼️ 2단계: 장면/이미지")

if not gemini_key:
    st.warning("**Gemini API 키가 설정되지 않았습니다.** 장면 분할과 이미지 생성에 AI가 필요합니다.")

st.divider()

# ─────────────────────────────────────────────
# ① 스크립트 불러오기
# ─────────────────────────────────────────────
st.subheader("① 스크립트")

src_tab1, src_tab2, src_tab3 = st.tabs(["1단계에서 이어서", "직접 입력/붙여넣기", "프로젝트에서 불러오기"])

script = st.session_state.get("_scene_script", st.session_state.get("final_script", ""))

with src_tab1:
    carried = st.session_state.get("final_script", "")
    if carried:
        lines = [l for l in carried.split("\n") if l.strip()]
        st.success(f"1단계 스크립트 준비됨 — {len(carried):,}자 / {len(lines)}줄")
        with st.expander("스크립트 미리보기"):
            st.text(carried[:800] + ("..." if len(carried) > 800 else ""))
        if st.button("이 스크립트 사용", type="primary", key="use_carried"):
            st.session_state["_scene_script"] = carried
            script = carried
            st.rerun()
    else:
        st.info("1단계에서 생성된 스크립트가 없습니다. 다른 탭을 사용해 주세요.")

with src_tab2:
    pasted = st.text_area(
        "스크립트 입력",
        height=150,
        placeholder="여기에 스크립트를 붙여넣으세요.",
        label_visibility="collapsed",
    )
    if st.button("이 스크립트 사용", type="primary", key="use_pasted", disabled=not pasted):
        st.session_state["_scene_script"] = pasted
        script = pasted
        st.rerun()

with src_tab3:
    pm = ProjectManager()
    projects = pm.list_projects()
    if projects:
        sel_proj = st.selectbox("프로젝트 선택", projects)
        if st.button("불러오기", type="primary"):
            loaded = pm.load_script(sel_proj)
            if loaded:
                st.session_state["_scene_script"] = loaded
                script = loaded
                st.success(f"{sel_proj} 불러오기 완료!")
                st.rerun()
            else:
                st.error("스크립트 파일을 찾을 수 없습니다.")
    else:
        st.info("저장된 프로젝트가 없습니다.")

# 현재 스크립트 상태 표시
script = st.session_state.get("_scene_script", "")
if script:
    lines = [l for l in script.split("\n") if l.strip()]
    est_scenes = max(5, len(lines) // 5)
    st.info(f"현재 스크립트: **{len(script):,}자 / {len(lines)}줄** — 예상 장면 수: 약 {est_scenes}개")

st.divider()

# ─────────────────────────────────────────────
# ② 스타일 & 캐릭터 설정
# ─────────────────────────────────────────────
st.subheader("② 스타일 & 캐릭터 설정")

col_style, col_char = st.columns([1, 1])

STYLE_OPTIONS = {
    "K웹툰 실사": "k_webtoon_real",
    "실사 사진": "realistic",
    "3D 애니메이션": "3d_animation",
    "수채화 일러스트": "watercolor",
    "커스텀": "custom",
}

with col_style:
    selected_style_name = st.selectbox(
        "이미지 스타일",
        list(STYLE_OPTIONS.keys()),
        index=list(STYLE_OPTIONS.keys()).index(st.session_state.get("image_style", "K웹툰 실사")),
    )
    st.session_state["image_style"] = selected_style_name
    style_key = STYLE_OPTIONS[selected_style_name]

    # 프리셋 설명 표시
    if style_key != "custom":
        preset = load_style_preset(style_key)
        if preset:
            st.caption(f"**{preset.get('name', '')}** — {preset.get('description', '')}")
            st.caption(f"Base prompt: `{preset.get('base_prompt', '')[:80]}...`")
    else:
        custom_style = st.text_input(
            "커스텀 스타일 프롬프트 (영어)",
            value=st.session_state.get("custom_style", ""),
            placeholder="예: Japanese manga style, black and white, detailed line art",
        )
        st.session_state["custom_style"] = custom_style

    aspect_ratio = st.radio(
        "이미지 비율",
        ["16:9 (가로형)", "1:1 (정방형)", "9:16 (세로형/쇼츠)"],
        index=["16:9 (가로형)", "1:1 (정방형)", "9:16 (세로형/쇼츠)"]
              .index(st.session_state.get("aspect_ratio", "16:9 (가로형)")),
        horizontal=True,
    )
    st.session_state["aspect_ratio"] = aspect_ratio

with col_char:
    st.markdown("**캐릭터 설정** (선택 — 일관된 캐릭터 묘사에 사용)")
    char1 = st.text_input("캐릭터 1", value=st.session_state.get("char1", ""),
                          placeholder="예: char_1 — 너구리 해설자, 갈색 후드 착용")
    char2 = st.text_input("캐릭터 2", value=st.session_state.get("char2", ""),
                          placeholder="예: char_2 — 조선시대 장군, 붉은 갑옷")
    char3 = st.text_input("캐릭터 3", value=st.session_state.get("char3", ""),
                          placeholder="예: char_3 — 현대인, 캐주얼 복장")
    st.session_state.update({"char1": char1, "char2": char2, "char3": char3})

    characters = "\n".join(c for c in [char1, char2, char3] if c.strip())

    scenes_per_script = st.number_input(
        "목표 장면 수 (0 = AI 자동)",
        min_value=0, max_value=60, value=st.session_state.get("target_scenes", 0),
        help="0이면 스크립트 길이에 맞춰 AI가 자동으로 결정합니다.",
    )
    st.session_state["target_scenes"] = scenes_per_script

st.divider()

# ─────────────────────────────────────────────
# ③ 장면 분할
# ─────────────────────────────────────────────
st.subheader("③ 장면 분할")

col_split_btn, col_resplit_btn, _ = st.columns([1, 1, 3])
with col_split_btn:
    split_btn = st.button(
        "장면 분할 시작",
        type="primary",
        disabled=not script or not gemini_key,
    )
with col_resplit_btn:
    resplit_btn = st.button(
        "다시 분할",
        type="secondary",
        disabled=not script or not gemini_key or "scenes" not in st.session_state,
    )

if split_btn or resplit_btn:
    client, err = get_gemini_client(config)
    if err:
        st.error(err)
    else:
        # 스타일 프롬프트 결정
        if style_key == "custom":
            style_prompt = st.session_state.get("custom_style", "")
        else:
            preset = load_style_preset(style_key)
            style_prompt = preset.get("base_prompt", selected_style_name)

        with st.spinner("Gemini가 장면을 분석하고 분할 중입니다... (10~30초)"):
            try:
                scenes = client.split_scenes(
                    script=script,
                    style=selected_style_name,
                    style_prompt=style_prompt,
                    characters=characters,
                    target_count=scenes_per_script if scenes_per_script > 0 else None,
                )
                save_scenes_state(scenes)
                st.success(f"✅ 총 **{len(scenes)}개** 장면으로 분할 완료!")
                st.rerun()
            except Exception as e:
                st.error(f"장면 분할 오류: {e}")

# ─────────────────────────────────────────────
# ④ 장면 목록 & 이미지 생성
# ─────────────────────────────────────────────
if "scenes" in st.session_state and st.session_state["scenes"]:
    scenes: list = st.session_state["scenes"]
    done_count, total_count = scene_image_status(scenes)

    st.divider()
    st.subheader(f"④ 장면 목록 & 이미지 생성")

    # 상태 요약 헤더
    col_status, col_gen_all, col_add = st.columns([2, 1, 1])
    with col_status:
        st.markdown(f"이미지 완료: **{done_count} / {total_count}**")
        if done_count > 0:
            st.progress(done_count / total_count)

    with col_gen_all:
        gen_all_btn = st.button(
            f"전체 이미지 생성 ({total_count - done_count}개 남음)",
            type="primary",
            disabled=not gemini_key or done_count == total_count,
        )

    with col_add:
        add_scene_btn = st.button("장면 추가 +", type="secondary")

    # 장면 추가
    if add_scene_btn:
        new_scene = {
            "scene_number": len(scenes) + 1,
            "narration": "",
            "image_prompt": "",
        }
        scenes.append(new_scene)
        save_scenes_state(scenes)
        st.rerun()

    # ── 전체 이미지 일괄 생성 ───────────────────────
    if gen_all_btn:
        client, err = get_gemini_client(config)
        if err:
            st.error(err)
        else:
            pending = [i for i, s in enumerate(scenes)
                       if not (s.get("image_path") and os.path.exists(s.get("image_path", "")))]

            proj_name = st.session_state.get("project_name", "")
            output_dir = (pm.get_image_dir(proj_name) if proj_name
                          else os.path.join(ROOT, "projects", "_temp", "images"))

            ratio_map = {"16:9 (가로형)": "16:9", "1:1 (정방형)": "1:1", "9:16 (세로형/쇼츠)": "9:16"}
            ratio = ratio_map.get(aspect_ratio, "16:9")

            progress_bar = st.progress(0, text="이미지 생성 준비 중...")
            status_text = st.empty()

            success_count = 0
            for idx, scene_idx in enumerate(pending):
                prompt = scenes[scene_idx].get("image_prompt", "")
                if not prompt:
                    continue
                status_text.info(f"장면 {scene_idx + 1} 이미지 생성 중... ({idx + 1}/{len(pending)})")
                try:
                    img_path = client.generate_image(
                        prompt=prompt,
                        scene_index=scene_idx,
                        output_dir=output_dir,
                        aspect_ratio=ratio,
                    )
                    scenes[scene_idx]["image_path"] = img_path
                    save_scenes_state(scenes)
                    success_count += 1
                except Exception as e:
                    status_text.warning(f"장면 {scene_idx + 1} 실패: {e}")

                progress_bar.progress((idx + 1) / len(pending),
                                      text=f"{idx + 1}/{len(pending)} 완료")

            progress_bar.empty()
            status_text.empty()
            st.success(f"이미지 생성 완료! {success_count}개 성공 / {len(pending) - success_count}개 실패")
            st.rerun()

    st.divider()

    # ── 장면별 카드 (3열 그리드) ───────────────────
    client_ready = bool(gemini_key)
    ratio_map = {"16:9 (가로형)": "16:9", "1:1 (정방형)": "1:1", "9:16 (세로형/쇼츠)": "9:16"}
    ratio = ratio_map.get(aspect_ratio, "16:9")

    proj_name = st.session_state.get("project_name", "")
    output_dir = (pm.get_image_dir(proj_name) if proj_name
                  else os.path.join(ROOT, "projects", "_temp", "images"))
    os.makedirs(output_dir, exist_ok=True)

    # 3열 그리드로 표시
    cols_per_row = 3
    for row_start in range(0, len(scenes), cols_per_row):
        row_scenes = scenes[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)

        for col_idx, (col, scene) in enumerate(zip(cols, row_scenes)):
            scene_idx = row_start + col_idx
            img_path = scene.get("image_path", "")
            has_image = bool(img_path and os.path.exists(img_path))

            with col:
                # 이미지 또는 플레이스홀더
                if has_image:
                    st.image(img_path, use_column_width=True)
                else:
                    st.markdown(
                        f"""<div style="
                            background:#1e1e2e;border:1px dashed #555;border-radius:8px;
                            height:180px;display:flex;align-items:center;
                            justify-content:center;color:#888;font-size:14px;
                        ">이미지 없음</div>""",
                        unsafe_allow_html=True,
                    )

                # 장면 번호 + 상태
                status_icon = "✅" if has_image else "⏳"
                st.markdown(f"**{status_icon} 장면 {scene_idx + 1}**")

                # 나레이션 미리보기
                narration_preview = scene.get("narration", "")[:50]
                st.caption(narration_preview + ("..." if len(scene.get("narration", "")) > 50 else ""))

                # 편집 / 생성 버튼
                with st.expander("편집 / 이미지 생성"):
                    new_narration = st.text_area(
                        "나레이션",
                        value=scene.get("narration", ""),
                        height=80,
                        key=f"narration_{scene_idx}",
                    )
                    new_prompt = st.text_area(
                        "이미지 프롬프트 (영어)",
                        value=scene.get("image_prompt", ""),
                        height=80,
                        key=f"prompt_{scene_idx}",
                    )

                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        label = "재생성" if has_image else "이미지 생성"
                        if st.button(label, key=f"gen_{scene_idx}",
                                     type="primary", disabled=not client_ready or not new_prompt):
                            with st.spinner(f"장면 {scene_idx + 1} 생성 중..."):
                                try:
                                    client, err = get_gemini_client(config)
                                    if err:
                                        st.error(err)
                                    else:
                                        img_path = client.generate_image(
                                            prompt=new_prompt,
                                            scene_index=scene_idx,
                                            output_dir=output_dir,
                                            aspect_ratio=ratio,
                                        )
                                        scenes[scene_idx].update({
                                            "narration": new_narration,
                                            "image_prompt": new_prompt,
                                            "image_path": img_path,
                                        })
                                        save_scenes_state(scenes)
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"오류: {e}")

                    with btn_col2:
                        if st.button("저장", key=f"save_{scene_idx}", type="secondary"):
                            scenes[scene_idx].update({
                                "narration": new_narration,
                                "image_prompt": new_prompt,
                            })
                            save_scenes_state(scenes)
                            st.success("저장됨")

                    # 삭제 버튼
                    if st.button("🗑 장면 삭제", key=f"del_{scene_idx}"):
                        scenes.pop(scene_idx)
                        # scene_number 재정렬
                        for i, s in enumerate(scenes):
                            s["scene_number"] = i + 1
                        save_scenes_state(scenes)
                        st.rerun()

    # ─────────────────────────────────────────────
    # ⑤ 저장 & 다음 단계
    # ─────────────────────────────────────────────
    st.divider()
    st.subheader("⑤ 저장 & 다음 단계")

    col_save, col_next = st.columns(2)
    with col_save:
        save_proj = st.session_state.get("project_name", "")
        if st.button("💾 장면 목록 저장", type="primary", disabled=not save_proj):
            pm.save_scenes(project_name=save_proj, scenes=scenes)
            st.success(f"`projects/{save_proj}/scenes.json` 에 저장되었습니다.")
        if not save_proj:
            st.caption("1단계에서 프로젝트 이름을 설정해야 저장 가능합니다.")

    with col_next:
        done_count, total_count = scene_image_status(scenes)
        if done_count < total_count:
            st.warning(f"이미지가 {total_count - done_count}개 아직 생성되지 않았습니다. 없는 장면은 검은 화면으로 합성됩니다.")
        st.page_link("pages/3_음성.py", label="3단계: 음성 생성으로 이동 →", icon="🔊")
