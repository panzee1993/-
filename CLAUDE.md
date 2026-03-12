# 유튜브 롱폼 자동 제작 도구 설계서

## 프로젝트 개요

구독형 서비스(vidmaker 등)를 대체하는 개인용 유튜브 영상 자동 제작 도구.
Streamlit + Python 기반, 5단계 파이프라인으로 대본부터 영상 업로드까지 자동화.

---

## 기술 스택

| 구분 | 기술 | 용도 |
|---|---|---|
| UI | Streamlit | 웹 기반 인터페이스 (브라우저에서 실행) |
| 대본 생성 | Gemini API | 벤치마킹 분석, 주제 추천, 스크립트 작성 |
| 이미지 생성 | Gemini API (나노바나나2) | 장면별 이미지 프롬프트 → 이미지 생성 |
| TTS 음성 | Gemini TTS / ElevenLabs API | 대본 → 음성 파일 생성 |
| 영상 합성 | FFmpeg + MoviePy | 이미지 + 음성 + 자막 → MP4 |
| 썸네일 | Gemini API (나노바나나2) | 썸네일 이미지 생성 |
| 업로드 | YouTube Data API v3 | 자동 업로드 (제목/설명/태그 포함) |
| 데이터 저장 | JSON 파일 | 프로젝트별 설정 및 진행상황 저장 |

---

## 필요한 API 키

- **Google Gemini API 키** — 대본 생성 + 이미지 생성(나노바나나2) + TTS
- **ElevenLabs API 키** — 고품질 한국어 TTS (선택)
- **YouTube Data API v3** — 영상 업로드 자동화 (Google Cloud Console에서 OAuth 설정 필요)

---

## 5단계 파이프라인

### 1단계: 대본 작성

**기능:**
- 프로젝트 이름 입력
- 롱폼/쇼츠 선택, 분량(분) 설정
- 벤치마킹 대본 붙여넣기 → AI가 분석 후 주제 추천
- 주제 선택 → 스크립트 자동 생성
- 기존 14포인트 하우스 스타일 가이드 적용 (100~200자/줄, 150줄 이하, 위기감 도입부 등)

**Gemini API 호출:**
```python
import google.generativeai as genai

genai.configure(api_key="YOUR_KEY")
model = genai.GenerativeModel("gemini-2.5-flash")

# 벤치마킹 분석
response = model.generate_content(f"""
다음 유튜브 대본을 분석하고 비슷한 주제 10개를 추천해줘:
{benchmark_script}
카테고리: {category}  # 예: 물건, 음식, 여행지, IT
""")

# 스크립트 생성
response = model.generate_content(f"""
주제: {selected_topic}
분량: {duration}분 (약 {duration * 385}자)
스타일 가이드:
- 인사 없이 본론부터, 도입부에 위기감 강조
- 한 줄 100~200자, 총 줄바꿈 150개 이하
- 반말 톤, 친근한 형/누나 느낌
...
""")
```

---

### 2단계: 장면/이미지

**기능:**
- 스크립트를 장면 단위로 자동 분할
- 각 장면별 이미지 프롬프트 자동 생성
- 각 장면별 동영상 프롬프트 자동 생성 (선택)
- 스타일 선택 (K웹툰 실사, 실사, 애니메이션 등)
- 캐릭터 설정 (char_1, char_2 등 일관성 유지)
- 이미지 생성 → 미리보기
- 마음에 안 드는 이미지 재생성

**핵심 코드 구조:**
```python
# 장면 분할 + 이미지 프롬프트 생성
response = model.generate_content(f"""
다음 스크립트를 장면 단위로 분할하고,
각 장면에 대해 이미지 프롬프트를 생성해줘.

스타일: {selected_style}  # K웹툰 실사
캐릭터: {characters}  # char_1: 너구리 해설자, char_2: 조선시대 장군
출력 형식: JSON

스크립트:
{script}
""")

# 나노바나나2로 이미지 생성 (Gemini API)
image_model = genai.GenerativeModel("gemini-2.0-flash-exp")
response = image_model.generate_content(image_prompt)
```

---

### 3단계: 음성

**기능:**
- 대본 전체를 TTS로 음성 생성
- Gemini TTS 또는 ElevenLabs 선택
- 남성/여성 목소리 선택
- 음성 속도 조절 (1.0x ~ 1.5x)
- 말투 스타일 설정 (기본, 뉴스 앵커 등)
- 오디오 미리듣기
- 500자 분할 옵션

**Gemini TTS 코드:**
```python
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_KEY")

response = client.models.generate_content(
    model="gemini-2.5-flash-preview-tts",
    contents=script_text,
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Kore"
                )
            )
        )
    )
)

with open("output.wav", "wb") as f:
    f.write(response.candidates[0].content.parts[0].inline_data.data)
```

**ElevenLabs TTS 코드:**
```python
from elevenlabs import ElevenLabs

client = ElevenLabs(api_key="YOUR_KEY")

audio = client.text_to_speech.convert(
    voice_id="서연",
    text=script_text,
    model_id="eleven_multilingual_v2"
)

with open("output.mp3", "wb") as f:
    for chunk in audio:
        f.write(chunk)
```

---

### 4단계: 최종 영상

**기능:**
- 이미지 + 음성 + 자막 → MP4 합성
- 자막 폰트/크기/위치 설정
- 배경음악 추가 (선택)
- 효과음 추가 (선택)
- 영상 미리보기

**FFmpeg + MoviePy 코드:**
```python
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    TextClip, concatenate_videoclips
)

clips = []
for scene in scenes:
    img_clip = ImageClip(scene["image_path"]).set_duration(scene["duration"])
    txt_clip = TextClip(
        scene["narration"],
        fontsize=75,
        font="배민도현체",
        color="white",
        stroke_color="black",
        stroke_width=2,
        size=(1800, None),
        method="caption"
    ).set_position(("center", "bottom")).set_duration(scene["duration"])

    composite = CompositeVideoClip([img_clip, txt_clip])
    clips.append(composite)

final = concatenate_videoclips(clips, method="compose")
audio = AudioFileClip("full_audio.mp3")
final = final.set_audio(audio)

if bgm_path:
    bgm = AudioFileClip(bgm_path).volumex(0.1)
    from moviepy.editor import CompositeAudioClip
    final_audio = CompositeAudioClip([audio, bgm])
    final = final.set_audio(final_audio)

final.write_videofile("output.mp4", fps=24, codec="libx264")
```

---

### 5단계: 썸네일 + 업로드

**기능:**
- 대본에서 썸네일 문구 4개 자동 추출
- 참조 이미지 업로드 (선택)
- 나노바나나2로 썸네일 생성 (16:9, 9:16)
- 유튜브 자동 업로드 (제목/설명/태그/썸네일)

**YouTube 업로드 코드:**
```python
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
credentials = flow.run_local_server(port=0)

youtube = build("youtube", "v3", credentials=credentials)

request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": video_title,
            "description": video_description,
            "tags": video_tags,
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False
        }
    },
    media_body=MediaFileUpload("output.mp4", mimetype="video/mp4")
)
response = request.execute()

youtube.thumbnails().set(
    videoId=response["id"],
    media_body=MediaFileUpload("thumbnail.jpg", mimetype="image/jpeg")
).execute()
```

---

## 프로젝트 폴더 구조

```
youtube-auto-tool/
├── app.py                    # Streamlit 메인 앱
├── pages/
│   ├── 1_대본.py             # 1단계
│   ├── 2_장면이미지.py       # 2단계
│   ├── 3_음성.py             # 3단계
│   ├── 4_최종영상.py         # 4단계
│   └── 5_썸네일업로드.py     # 5단계
├── utils/
│   ├── gemini_client.py      # Gemini API 래퍼
│   ├── elevenlabs_client.py  # ElevenLabs API 래퍼
│   ├── video_maker.py        # FFmpeg/MoviePy 영상 합성
│   ├── youtube_uploader.py   # YouTube API 업로드
│   └── project_manager.py   # 프로젝트 JSON 저장/불러오기
├── projects/                 # 프로젝트별 데이터 저장
├── styles/                   # 스타일 프리셋
│   ├── k_webtoon_real.json
│   ├── realistic.json
│   └── 3d_animation.json
├── config.yaml               # API 키, 기본 설정
├── requirements.txt          # Python 패키지 목록
├── CLAUDE.md                 # 이 설계서
└── README.md
```

---

## 개발 순서 (바이브 코딩 로드맵)

### Phase 1: 기초 세팅 (1일)
- [ ] 프로젝트 폴더 생성
- [ ] config.yaml에 API 키 설정
- [ ] Streamlit 기본 앱 실행 확인
- [ ] Gemini API 연결 테스트

### Phase 2: 대본 생성 (1~2일)
- [ ] 벤치마킹 대본 입력 → 주제 추천
- [ ] 주제 선택 → 스크립트 생성
- [ ] 하우스 스타일 가이드 프롬프트 적용
- [ ] 스크립트 편집 + 저장 기능

### Phase 3: 장면/이미지 (2~3일)
- [ ] 스크립트 → 장면 자동 분할
- [ ] 장면별 이미지 프롬프트 생성
- [ ] 나노바나나2로 이미지 생성
- [ ] 스타일 프리셋 선택
- [ ] 이미지 미리보기 + 재생성

### Phase 4: 음성 (1~2일)
- [ ] Gemini TTS 연동
- [ ] ElevenLabs TTS 연동
- [ ] 목소리/속도 설정
- [ ] 오디오 미리듣기

### Phase 5: 영상 합성 (2~3일)
- [ ] FFmpeg/MoviePy로 이미지+음성+자막 합성
- [ ] 자막 스타일 설정
- [ ] 배경음악 추가
- [ ] 영상 미리보기

### Phase 6: 썸네일 + 업로드 (1~2일)
- [ ] 썸네일 문구 추출 + 이미지 생성
- [ ] YouTube API OAuth 설정
- [ ] 자동 업로드 (비공개 → 확인 후 공개)

---

## 실행 방법

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. FFmpeg 설치 (영상 합성용)
# Windows: choco install ffmpeg
# Mac: brew install ffmpeg
# Linux: sudo apt install ffmpeg

# 3. config.yaml에 API 키 입력

# 4. 실행
streamlit run app.py
```
