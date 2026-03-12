"""ElevenLabs API 래퍼 — 고품질 다국어 TTS"""

import os
import io
import wave


class ElevenLabsClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    # ─── 목소리 목록 불러오기 ──────────────────────────────────────────────
    def list_voices(self) -> list[dict]:
        """계정에 등록된 목소리 목록 반환."""
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=self.api_key)
        resp = client.voices.get_all()
        return [
            {
                "name": v.name,
                "voice_id": v.voice_id,
                "category": getattr(v, "category", ""),
                "labels": getattr(v, "labels", {}),
            }
            for v in resp.voices
        ]

    # ─── 단일 청크 TTS ────────────────────────────────────────────────────
    def _tts_single_chunk(
        self,
        client,
        text: str,
        voice_id: str,
        model_id: str,
        stability: float,
        similarity_boost: float,
    ) -> bytes:
        """청크 하나 → MP3 bytes 반환."""
        from elevenlabs import VoiceSettings

        audio_generator = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
            voice_settings=VoiceSettings(
                stability=stability,
                similarity_boost=similarity_boost,
            ),
            output_format="mp3_44100_128",
        )
        return b"".join(audio_generator)

    # ─── 청크 분할 생성 + WAV 합치기 ──────────────────────────────────────
    def generate_tts_chunked(
        self,
        text: str,
        voice_id: str,
        model_id: str = "eleven_multilingual_v2",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        chunk_size: int = 1000,
        output_path: str = "output/audio.wav",
        progress_callback=None,
    ) -> str:
        """텍스트를 chunk_size 단위로 분할 → 각 청크 TTS → 단일 WAV 저장."""
        from elevenlabs import ElevenLabs

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        client = ElevenLabs(api_key=self.api_key)
        chunks = self._split_text_smart(text, chunk_size)
        total = len(chunks)

        mp3_parts: list[bytes] = []
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i, total, f"청크 {i + 1} / {total} 생성 중... ({len(chunk)}자)")
            mp3_data = self._tts_single_chunk(
                client, chunk, voice_id, model_id, stability, similarity_boost
            )
            mp3_parts.append(mp3_data)

        if progress_callback:
            progress_callback(total, total, "파일 병합 중...")

        # MP3 → WAV 변환 후 저장
        wav_path = output_path
        self._merge_mp3_to_wav(mp3_parts, wav_path)
        return wav_path

    # ─── 단건 생성 (짧은 텍스트) ──────────────────────────────────────────
    def generate_tts(
        self,
        text: str,
        voice_id: str,
        model_id: str = "eleven_multilingual_v2",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        output_path: str = "output/audio.wav",
    ) -> str:
        return self.generate_tts_chunked(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            stability=stability,
            similarity_boost=similarity_boost,
            chunk_size=len(text) + 1,  # 분할 없이 단건
            output_path=output_path,
        )

    # ─── 내부 유틸 ────────────────────────────────────────────────────────
    @staticmethod
    def _split_text_smart(text: str, chunk_size: int) -> list[str]:
        """chunk_size 이하로 줄/문장 단위 분할."""
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
                if len(line) > chunk_size:
                    for i in range(0, len(line), chunk_size):
                        chunks.append(line[i:i + chunk_size])
                    current = ""
                else:
                    current = line
        if current:
            chunks.append(current)
        return [c for c in chunks if c.strip()]

    @staticmethod
    def _merge_mp3_to_wav(mp3_parts: list[bytes], output_path: str) -> None:
        """MP3 청크들을 하나의 WAV 파일로 병합. pydub 또는 순수 bytes 저장."""
        try:
            from pydub import AudioSegment

            combined = AudioSegment.empty()
            for mp3_bytes in mp3_parts:
                seg = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
                combined += seg
            combined.export(output_path, format="wav")

        except ImportError:
            # pydub 없으면 MP3 bytes를 그대로 이어서 .mp3로 저장 (확장자만 wav)
            # 영상 합성에서 AudioFileClip이 mp3도 읽으므로 실용적으로 문제 없음
            raw_path = output_path.replace(".wav", "_raw.mp3")
            with open(raw_path, "wb") as f:
                for part in mp3_parts:
                    f.write(part)
            # output_path는 mp3 복사본으로 대체
            import shutil
            shutil.copy(raw_path, output_path)
