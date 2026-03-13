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
        style_prompt: str = "",
        characters: str = "",
        target_count: int = None,
    ) -> list[dict]:
        lines = [l for l in script.split("\n") if l.strip()]
        line_count = len(lines)

        # 목표 장면 수 결정 (지정 없으면 5줄당 1장면)
        if target_count and target_count > 0:
            scene_count_guide = f"정확히 {target_count}개 장면으로 분할해 줘."
        else:
            auto_count = max(5, min(30, line_count // 5))
            scene_count_guide = f"약 {auto_count}개 장면으로 분할해 줘 (스크립트 길이 기준 자동 결정)."

        char_section = f"\n[캐릭터 정보 — 이미지 프롬프트에 반드시 반영]\n{characters}\n" if characters.strip() else ""

        style_desc = style_prompt if style_prompt else style

        prompt = f"""너는 유튜브 영상 제작 전문가야.
아래 스크립트를 장면 단위로 분할하고, 각 장면에 대한 이미지 생성 프롬프트를 만들어 줘.

{scene_count_guide}
{char_section}
[이미지 스타일]
{style_desc}

[스크립트]
{script[:6000]}

[장면 분할 규칙]
1. 하나의 장면 = 같은 공간·시간·상황이 지속되는 나레이션 묶음 (보통 3~6줄)
2. 나레이션이 전환되거나 새로운 사건·장소가 나오면 새 장면으로 분리
3. narration 필드에는 해당 장면의 나레이션 전체를 그대로 포함 (줄바꿈 포함)

[image_prompt 작성 규칙]
- 반드시 영어로 작성
- 스타일 키워드를 프롬프트 앞에 붙일 것: "{style_desc[:60]}, ..."
- 장면의 시각적 상황을 구체적으로 묘사: 인물, 배경, 조명, 분위기, 카메라 앵글
- 캐릭터가 있으면 외형 묘사를 포함
- 50~100 단어 분량으로 상세하게
- 텍스트(글자)를 이미지에 넣지 말 것

[출력 형식 — 순수 JSON만 출력, 주석 없음]
[
  {{
    "scene_number": 1,
    "narration": "장면 나레이션 텍스트 (원문 그대로)",
    "image_prompt": "Detailed English image generation prompt here...",
    "mood": "dramatic / calm / tense / uplifting 중 하나"
  }}
]

반드시 유효한 JSON만 출력해 줘. 코드 블록(```)이나 설명 텍스트 없이."""

        response = self.model.generate_content(prompt)
        raw = response.text.strip()

        # 코드 블록 제거
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        # 앞뒤 공백 제거 후 JSON 시작 위치 찾기
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        try:
            scenes = json.loads(raw)
            # 필수 필드 보정
            for i, scene in enumerate(scenes):
                scene.setdefault("scene_number", i + 1)
                scene.setdefault("narration", "")
                scene.setdefault("image_prompt", "")
                scene.setdefault("mood", "neutral")
                scene.pop("image_path", None)  # 이전 경로 초기화
            return scenes
        except json.JSONDecodeError:
            # 파싱 완전 실패 시 스크립트를 균등 분할
            chunk_size = max(3, line_count // (target_count or max(5, line_count // 5)))
            scenes = []
            for i in range(0, line_count, chunk_size):
                chunk_lines = lines[i:i + chunk_size]
                narration = "\n".join(chunk_lines)
                scenes.append({
                    "scene_number": len(scenes) + 1,
                    "narration": narration,
                    "image_prompt": f"{style_desc}, cinematic scene illustration of: {narration[:80]}",
                    "mood": "neutral",
                })
            return scenes

    # ─── 이미지 생성 ───────────────────────────────────────────────────────
    def generate_image(
        self,
        prompt: str,
        scene_index: int,
        output_dir: str = "output",
        aspect_ratio: str = "16:9",
    ) -> str:
        from google import genai as google_genai
        from google.genai import types

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"scene_{scene_index:03d}.png")

        client = google_genai.Client(api_key=self.api_key)
        image_model = self.config.get("gemini", {}).get("image_model", "gemini-2.0-flash-exp")

        # Gemini 2.0 Flash 이미지 생성 (IMAGE 모달리티)
        response = client.models.generate_content(
            model=image_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                img_data = part.inline_data.data
                # bytes 또는 base64 문자열 모두 처리
                if isinstance(img_data, str):
                    img_data = base64.b64decode(img_data)
                with open(output_path, "wb") as f:
                    f.write(img_data)
                return output_path

        raise RuntimeError("이미지 생성 응답에서 이미지 데이터를 찾을 수 없습니다. 모델이 이미지 생성을 지원하는지 확인하세요.")

    # ─── TTS 단일 청크 호출 ────────────────────────────────────────────────
    def _tts_single_chunk(self, client, tts_model: str, text: str, voice: str) -> bytes:
        """청크 하나에 대한 TTS 호출. PCM bytes 반환."""
        import io, wave
        from google.genai import types

        response = client.models.generate_content(
            model=tts_model,
            contents=text,
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
        part = response.candidates[0].content.parts[0]
        audio_data = part.inline_data.data
        mime_type = part.inline_data.mime_type or ""

        # WAV 컨테이너면 PCM 프레임만 추출
        if "wav" in mime_type.lower():
            buf = io.BytesIO(audio_data)
            with wave.open(buf, "rb") as wf:
                return wf.readframes(wf.getnframes()), wf.getframerate(), wf.getnchannels(), wf.getsampwidth()
        # 이미 raw PCM
        return audio_data, 24000, 1, 2  # 24kHz, mono, 16-bit 기본값

    # ─── TTS (음성 생성) — 단건 ───────────────────────────────────────────
    def generate_tts(
        self,
        text: str,
        voice: str = "Kore",
        split: bool = False,
        output_path: str = "output/audio.wav",
    ) -> str:
        """짧은 텍스트 단건 생성 (목소리 테스트용)."""
        from google import genai as google_genai
        import wave

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        client = google_genai.Client(api_key=self.api_key)
        tts_model = self.config.get("gemini", {}).get("tts_model", "gemini-2.5-flash-preview-tts")

        pcm, sample_rate, channels, sampwidth = self._tts_single_chunk(client, tts_model, text, voice)

        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)

        return output_path

    # ─── TTS (음성 생성) — 청크 분할 + 진행률 콜백 ──────────────────────
    def generate_tts_chunked(
        self,
        text: str,
        voice: str = "Kore",
        chunk_size: int = 500,
        output_path: str = "output/audio.wav",
        progress_callback=None,
    ) -> str:
        """긴 텍스트를 chunk_size 단위로 분할 생성 후 단일 WAV로 합칩니다."""
        from google import genai as google_genai
        import wave

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        client = google_genai.Client(api_key=self.api_key)
        tts_model = self.config.get("gemini", {}).get("tts_model", "gemini-2.5-flash-preview-tts")

        # 문장 단위로 자르되 chunk_size 이하로 묶기 (단어 중간 잘림 방지)
        chunks = self._split_text_smart(text, chunk_size)
        total = len(chunks)

        all_pcm = b""
        wav_params = None  # (channels, sampwidth, rate)

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i, total, f"청크 {i + 1} / {total} 생성 중... ({len(chunk)}자)")
            pcm, rate, ch, sw = self._tts_single_chunk(client, tts_model, chunk, voice)
            all_pcm += pcm
            if wav_params is None:
                wav_params = (ch, sw, rate)

        if progress_callback:
            progress_callback(total, total, "WAV 파일 저장 중...")

        channels, sampwidth, sample_rate = wav_params or (1, 2, 24000)
        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(sample_rate)
            wf.writeframes(all_pcm)

        return output_path

    @staticmethod
    def _split_text_smart(text: str, chunk_size: int) -> list[str]:
        """chunk_size 이하로 문장/줄 단위 분할 (단어 중간 잘림 방지)."""
        # 줄 단위로 먼저 묶기
        lines = text.split("\n")
        chunks = []
        current = ""
        for line in lines:
            candidate = (current + "\n" + line).strip() if current else line
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # 줄 자체가 chunk_size 초과면 강제 분할
                if len(line) > chunk_size:
                    for i in range(0, len(line), chunk_size):
                        chunks.append(line[i:i + chunk_size])
                    current = ""
                else:
                    current = line
        if current:
            chunks.append(current)
        return [c for c in chunks if c.strip()]

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
        ref_image_bytes: bytes = None,
        ref_image_mime: str = "image/jpeg",
    ) -> str:
        from google import genai as google_genai
        from google.genai import types

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        ratio = "16:9" if "16:9" in size else "9:16"

        STYLE_PROMPT = {
            "실사 + 임팩트 텍스트": "photorealistic, cinematic lighting, high contrast, dramatic",
            "K웹툰 실사": "Korean webtoon realistic style, vibrant colors, detailed linework",
            "충격적인 얼굴 클로즈업": "extreme close-up face, shocked expression, photorealistic, dramatic lighting",
            "다큐멘터리 스타일": "documentary photography, gritty realism, cinematic, historical",
            "일러스트": "digital illustration, vivid bold colors, graphic design style",
        }
        style_desc = STYLE_PROMPT.get(style, style)

        text_block = f'Main overlay text on image: "{main_text}"'
        if sub_text:
            text_block += f'\nSub text (smaller): "{sub_text}"'

        prompt = (
            f"Create a YouTube thumbnail. Aspect ratio: {ratio}. "
            f"Style: {style_desc}. {text_block}. "
            "Requirements: bold impactful composition, eye-catching, high contrast, "
            "professional Korean YouTube style, dramatic lighting, vivid colors. "
            "Text must be large and clearly readable."
        )

        client = google_genai.Client(api_key=self.api_key)
        image_model = self.config.get("gemini", {}).get("image_model", "gemini-2.0-flash-exp")

        # 참조 이미지가 있으면 멀티모달 입력
        if ref_image_bytes:
            contents = [
                types.Part.from_bytes(data=ref_image_bytes, mime_type=ref_image_mime),
                prompt,
            ]
        else:
            contents = prompt

        response = client.models.generate_content(
            model=image_model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                img_data = part.inline_data.data
                if isinstance(img_data, str):
                    img_data = base64.b64decode(img_data)
                with open(output_path, "wb") as f:
                    f.write(img_data)
                return output_path

        raise RuntimeError(
            "썸네일 이미지 생성에 실패했습니다. 모델 응답에 이미지 데이터가 없습니다."
        )

    # ─── 유튜브 메타데이터 생성 ────────────────────────────────────────────
    def generate_youtube_metadata(
        self,
        script: str,
        topic: str = "",
    ) -> dict:
        """대본에서 유튜브 제목·설명·태그를 AI로 생성."""
        topic_line = f"주제: {topic}\n" if topic else ""
        prompt = f"""너는 유튜브 채널 운영 전문가야.
아래 대본을 기반으로 유튜브 업로드에 필요한 메타데이터를 만들어 줘.

{topic_line}[대본 (처음 600자)]
{script[:600]}

[출력 규칙]
- title: 클릭률 높은 제목, 30자 이내, 이모지 1~2개 포함
- description: 영상 내용 요약 3~4줄, 마지막 줄에 해시태그 5개 (줄바꿈으로 구분)
- tags: 관련 키워드 10개 배열 (한국어)

반드시 아래 JSON 형식만 출력해 줘 (코드블록·설명 없이):
{{
  "title": "...",
  "description": "...",
  "tags": ["태그1", "태그2", ...]
}}"""
        response = self.model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"title": "", "description": "", "tags": []}
