"""ElevenLabs API 래퍼 — 고품질 한국어 TTS"""

import os


# 한국어 음성 ID 매핑 (ElevenLabs에서 제공하는 한국어 지원 음성)
KOREAN_VOICES = {
    "서연 (한국어 여성)": "21m00Tcm4TlvDq8ikWAM",   # Rachel (예시 ID, 실제 ID로 교체 필요)
    "지호 (한국어 남성)": "AZnzlk1XvdvUeBnXmlld",    # Domi (예시 ID)
    "Rachel (영어 여성)": "21m00Tcm4TlvDq8ikWAM",
}


class ElevenLabsClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate_tts(
        self,
        text: str,
        voice: str = "서연 (한국어 여성)",
        model_id: str = "eleven_multilingual_v2",
        output_path: str = "output/audio.mp3",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
    ) -> str:
        from elevenlabs import ElevenLabs

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        client = ElevenLabs(api_key=self.api_key)

        voice_id = KOREAN_VOICES.get(voice, voice)

        audio_generator = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
            voice_settings={
                "stability": stability,
                "similarity_boost": similarity_boost,
            },
        )

        with open(output_path, "wb") as f:
            for chunk in audio_generator:
                f.write(chunk)

        return output_path

    def list_voices(self) -> list[dict]:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=self.api_key)
        voices = client.voices.get_all()
        return [{"name": v.name, "voice_id": v.voice_id} for v in voices.voices]
