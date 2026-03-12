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
            prompt = f"""
다음 유튜브 대본을 분석하고, 비슷한 스타일의 주제 {count}개를 추천해 줘.
카테고리: {category}
영상 유형: {content_type}

[대본]
{benchmark_script[:3000]}

출력 형식:
1. 주제 제목
2. 주제 제목
...

주제만 번호와 함께 출력해 줘. 설명 없이.
"""
        else:
            prompt = f"""
한국 유튜브에서 인기 있는 {category} 카테고리의 흥미로운 주제 {count}개를 추천해 줘.
영상 유형: {content_type}
- 도입부에 위기감이나 호기심을 자극하는 주제
- 시청자가 끝까지 보고 싶게 만드는 주제

출력 형식:
1. 주제 제목
2. 주제 제목
...

주제만 번호와 함께 출력해 줘. 설명 없이.
"""

        response = self.model.generate_content(prompt)
        raw = response.text.strip()

        # "1. 주제" 형식 파싱
        topics = []
        for line in raw.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
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
    ) -> str:
        script_cfg = self.config.get("script", {})
        chars_per_minute = script_cfg.get("chars_per_minute", 385)
        max_lines = script_cfg.get("max_lines", 150)
        max_chars = script_cfg.get("max_chars_per_line", 200)
        min_chars = script_cfg.get("min_chars_per_line", 100)
        target_chars = duration * chars_per_minute

        prompt = f"""
유튜브 {content_type} 대본을 작성해 줘.

주제: {topic}
카테고리: {category}
목표 분량: {duration}분 (약 {target_chars:,}자)

[하우스 스타일 가이드]
1. 인사말 없이 본론부터 시작 (절대 "안녕하세요" 금지)
2. 도입부 첫 3~5줄에 위기감/충격/호기심 요소 강조
3. 한 줄 {min_chars}~{max_chars}자 사이로 작성
4. 총 줄바꿈 {max_lines}개 이하
5. 반말 톤, 친근한 형/누나 느낌 (예: "~야", "~거든", "~지")
6. 숫자와 구체적인 사실로 신뢰감 형성
7. 중간중간 "그런데", "사실은", "놀라운 건" 등 전환어 사용
8. 마지막에 구독/좋아요 유도 멘트 1줄

대본만 출력해 줘. 제목이나 설명 없이.
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
