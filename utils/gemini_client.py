"""Gemini API 래퍼 — 대본 생성, 이미지 생성, TTS"""

import os
import json
import base64
import re
from typing import Optional


class GeminiClient:
    def __init__(self, api_key: str, config: dict):
        self.api_key = api_key
        self.config = config

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai

        script_model = config.get("gemini", {}).get("script_model", "gemini-2.5-flash")
        self.model = genai.GenerativeModel(script_model)

    # ─── 주제 추천 ────────────────────────────────────────────────────────
    def recommend_topics(
        self,
        benchmark_script: str,
        category: str,
        content_type: str = "롱폼",
        count: int = 10,
    ) -> list[str]:
        if benchmark_script.strip():
            prompt = f"""너는 한국 유튜브 대본 기획 전문가야.
아래 대본을 분석해서, 비슷한 포맷과 스타일로 만들 수 있는 새로운 주제 {count}개를 추천해 줘.

[분석할 대본]
{benchmark_script[:3000]}

[추천 조건]
- 카테고리: {category}
- 영상 유형: {content_type}
- 제목만 봐도 클릭하고 싶은 주제 (클릭베이트 요소 포함)
- 대본 시작부터 위기감·충격·호기심을 줄 수 있는 주제
- 실제로 구체적인 사실과 스토리가 있어야 함 (허구 금지)
- 주제 제목은 30자 이내, 임팩트 있게

[출력 형식]
번호. 주제 제목 (설명 없이 제목만)
예) 1. 조선 최고의 명장이 처형 직전까지 몰린 진짜 이유

{count}개를 번호와 함께 출력해 줘."""
        else:
            prompt = f"""너는 한국 유튜브 대본 기획 전문가야.
한국 유튜브에서 조회수를 높게 받을 수 있는 {category} 카테고리 주제 {count}개를 추천해 줘.

[조건]
- 영상 유형: {content_type}
- 제목만 봐도 클릭하고 싶은 주제
- 도입부에 위기감·충격·호기심을 강하게 줄 수 있는 주제
- 실제 역사적 사실, 검증된 정보 기반 (허구 금지)
- 주제 제목은 30자 이내, 임팩트 있게
- "~한 이유", "~의 진실", "~몰랐던 사실", "~충격" 등 유튜브 스타일 제목

[출력 형식]
번호. 주제 제목 (설명 없이 제목만)
예) 1. 조선 최고의 명장이 처형 직전까지 몰린 진짜 이유

{count}개를 번호와 함께 출력해 줘."""

        response = self.model.generate_content(prompt)
        raw = response.text.strip()

        # "1. 주제" 형식 파싱
        topics = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line[0].isdigit() or line.startswith("-") or line.startswith("•"):
                topic = re.sub(r"^[\d]+[.\)]\s*", "", line).strip()
                topic = re.sub(r"^[-•]\s*", "", topic).strip()
                if topic:
                    topics.append(topic)

        return topics if topics else [raw]

    # ─── 스크립트 생성 ─────────────────────────────────────────────────────
    def generate_script(
        self,
        topic: str,
        duration: int,
        content_type: str = "롱폼",
        category: str = "역사/인물",
        style_guide: dict = None,
    ) -> str:
        script_cfg = self.config.get("script", {})
        chars_per_minute = script_cfg.get("chars_per_minute", 385)

        sg = style_guide or {}
        min_chars = sg.get("min_chars", script_cfg.get("min_chars_per_line", 100))
        max_chars = sg.get("max_chars", script_cfg.get("max_chars_per_line", 200))
        max_lines = sg.get("max_lines", script_cfg.get("max_lines", 150))
        tone = sg.get("tone", "반말 친근체 (형/누나)")
        opening = sg.get("opening", "위기감/충격 강조")
        ending = sg.get("ending", True)

        if content_type == "롱폼":
            target_chars = duration * chars_per_minute
            duration_desc = f"{duration}분 (약 {target_chars:,}자)"
        else:
            # 쇼츠: 초 단위, 1초당 약 6.4자
            target_chars = int(duration * 6.4)
            duration_desc = f"{duration}초 (약 {target_chars:,}자)"

        # 톤 설명
        tone_guide = {
            "반말 친근체 (형/누나)": "반말, 친근한 형/누나 느낌. '~야', '~거든', '~지', '~잖아' 어미 사용. 독자와 대화하듯 편하게.",
            "반말 강의체": "반말이지만 강의하듯 명확하고 자신감 있게. '~다', '~이다', '~했어' 어미 위주.",
            "존댓말 친근체": "존댓말이지만 너무 딱딱하지 않게. '~요', '~죠', '~거든요' 어미 사용.",
            "존댓말 격식체": "정중한 존댓말. '~습니다', '~입니다' 어미 위주. 신뢰감 강조.",
        }.get(tone, "반말, 친근한 느낌.")

        # 도입부 스타일
        opening_guide = {
            "위기감/충격 강조": "첫 3~5줄에 충격적인 사실이나 위기 상황을 던져서 '도대체 왜?' 라는 궁금증 유발.",
            "호기심 자극": "첫 3~5줄에 반전이나 의외의 사실을 제시해서 끝까지 보고 싶게 만들기.",
            "질문으로 시작": "시청자에게 직접 질문을 던지며 시작. '너 혹시 알고 있어? ...'",
            "통계/수치 시작": "충격적인 숫자나 통계로 시작. 신뢰감 + 호기심 동시 자극.",
        }.get(opening, "위기감이나 충격적인 사실로 시작.")

        ending_guide = "- 마지막 줄에 구독/좋아요 유도 멘트 1줄 포함 (자연스럽게)" if ending else "- 구독/좋아요 유도 멘트 없이 마무리"

        prompt = f"""너는 한국 유튜브 채널의 전문 대본 작가야.
아래 조건에 맞는 유튜브 {content_type} 대본을 작성해 줘.

━━━━━━━━━━━━━━━━━━━━
주제: {topic}
카테고리: {category}
목표 분량: {duration_desc}
━━━━━━━━━━━━━━━━━━━━

[필수 스타일 규칙 — 반드시 지켜야 함]

1. 첫 줄부터 본론 시작
   - "안녕하세요", "오늘은", "여러분" 같은 인사말 절대 금지
   - {opening_guide}

2. 줄 길이 규칙 (매우 중요)
   - 한 줄은 {min_chars}자 이상 {max_chars}자 이하로 작성
   - 200자를 넘는 줄은 무조건 두 줄로 나눠
   - 100자 미만의 너무 짧은 줄은 앞뒤 줄과 합쳐
   - 줄바꿈은 총 {max_lines}개 이하

3. 톤 & 문체
   - {tone_guide}
   - 숫자, 연도, 구체적 사실로 신뢰감 형성 (예: "1597년", "조선군 12만 명")
   - "그런데", "사실은", "놀라운 건", "근데 여기서", "진짜 충격적인 건" 등 전환어로 흐름 유지

4. 구성 흐름
   - 도입부(10%): {opening_guide}
   - 전개부(70%): 사실과 이야기를 구체적으로 서술, 중간중간 호기심 유발
   - 마무리(20%): 핵심 메시지 정리, 여운 남기기
   {ending_guide}

5. 금지 사항
   - 마크다운 기호(#, *, -, 등) 사용 금지
   - [장면1] [씬] 같은 장면 번호 표기 금지
   - 대본 제목, 설명, 주석 없이 대본 텍스트만 출력

지금 바로 대본 첫 줄부터 시작해 줘.
"""

        response = self.model.generate_content(prompt)
        return response.text.strip()

    # ─── 장면 분할 ─────────────────────────────────────────────────────────
    def split_scenes(
        self,
        script: str,
        style: str = "K웹툰 실사",
        characters: str = "",
    ) -> list[dict]:
        char_info = f"\n캐릭터 정보: {characters}" if characters else ""

        prompt = f"""
다음 스크립트를 장면 단위로 분할하고, 각 장면에 대한 이미지 생성 프롬프트를 만들어 줘.

이미지 스타일: {style}
{char_info}

[스크립트]
{script[:5000]}

[출력 형식 - JSON 배열]
[
  {{
    "scene_number": 1,
    "narration": "장면 나레이션 텍스트",
    "image_prompt": "영어로 된 이미지 생성 프롬프트 (스타일 포함)"
  }},
  ...
]

JSON만 출력해 줘. 다른 텍스트 없이.
"""

        response = self.model.generate_content(prompt)
        raw = response.text.strip()

        # JSON 파싱
        raw = re.sub(r"```json\n?", "", raw)
        raw = re.sub(r"```\n?", "", raw)

        try:
            scenes = json.loads(raw)
        except json.JSONDecodeError:
            # 파싱 실패 시 단순 분할로 대체
            lines = [l for l in script.split("\n") if l.strip()]
            scenes = [
                {
                    "scene_number": i + 1,
                    "narration": line,
                    "image_prompt": f"{style} style illustration of: {line[:100]}",
                }
                for i, line in enumerate(lines[:30])
            ]

        return scenes

    # ─── 이미지 생성 ───────────────────────────────────────────────────────
    def generate_image(self, prompt: str, scene_index: int, output_dir: str = "output") -> str:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"scene_{scene_index:03d}.png")

        image_model_name = self.config.get("gemini", {}).get("image_model", "gemini-2.0-flash-exp")
        image_model = self._genai.GenerativeModel(image_model_name)

        response = image_model.generate_content(
            prompt,
            generation_config={"response_mime_type": "image/png"},
        )

        # 이미지 데이터 추출 및 저장
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                img_data = base64.b64decode(part.inline_data.data)
                with open(output_path, "wb") as f:
                    f.write(img_data)
                return output_path

        raise RuntimeError("이미지 생성 응답에서 이미지 데이터를 찾을 수 없습니다.")

    # ─── TTS (음성 생성) ───────────────────────────────────────────────────
    def generate_tts(
        self,
        text: str,
        voice: str = "Kore",
        speed: float = 1.0,
        split: bool = True,
        output_path: str = "output/audio.wav",
    ) -> str:
        from google import genai as google_genai
        from google.genai import types

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        client = google_genai.Client(api_key=self.api_key)
        tts_model = self.config.get("gemini", {}).get("tts_model", "gemini-2.5-flash-preview-tts")

        # 500자 분할
        chunks = [text[i:i+500] for i in range(0, len(text), 500)] if split else [text]

        all_audio = b""
        for chunk in chunks:
            response = client.models.generate_content(
                model=tts_model,
                contents=chunk,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            )
                        )
                    ),
                ),
            )
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            all_audio += audio_data

        with open(output_path, "wb") as f:
            f.write(all_audio)

        return output_path

    # ─── 썸네일 문구 추출 ─────────────────────────────────────────────────
    def extract_thumbnail_phrases(self, script: str) -> list[str]:
        prompt = f"""
다음 유튜브 대본에서 썸네일에 넣으면 클릭률이 높아질 핵심 문구 4개를 추출해 줘.
- 짧고 임팩트 있어야 함 (10~20자 이내)
- 호기심이나 충격을 유발하는 문구
- 시청자가 "이게 뭐지?" 하고 클릭하게 만드는 문구

[대본 요약 (첫 500자)]
{script[:500]}

출력 형식:
1. 문구
2. 문구
3. 문구
4. 문구

문구만 출력해 줘.
"""
        response = self.model.generate_content(prompt)
        raw = response.text.strip()

        phrases = []
        for line in raw.split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                phrase = re.sub(r"^[\d]+[.\)]\s*", "", line).strip()
                if phrase:
                    phrases.append(phrase)

        return phrases

    # ─── 썸네일 생성 ───────────────────────────────────────────────────────
    def generate_thumbnail(
        self,
        main_text: str,
        sub_text: str = "",
        style: str = "실사 + 임팩트 텍스트",
        size: str = "16:9 (유튜브 기본)",
        output_path: str = "output/thumbnail.jpg",
    ) -> str:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        ratio = "16:9" if "16:9" in size else "9:16"
        prompt = f"""
Create a YouTube thumbnail image.
Style: {style}
Ratio: {ratio}
Main text overlay: "{main_text}"
Sub text: "{sub_text}"
Requirements: Eye-catching, high contrast, professional YouTube thumbnail design,
dramatic lighting, Korean YouTube style, bold impactful composition.
"""

        image_model_name = self.config.get("gemini", {}).get("image_model", "gemini-2.0-flash-exp")
        image_model = self._genai.GenerativeModel(image_model_name)

        response = image_model.generate_content(
            prompt,
            generation_config={"response_mime_type": "image/jpeg"},
        )

        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                img_data = base64.b64decode(part.inline_data.data)
                with open(output_path, "wb") as f:
                    f.write(img_data)
                return output_path

        raise RuntimeError("썸네일 이미지 생성에 실패했습니다.")
