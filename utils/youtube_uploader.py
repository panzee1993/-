"""YouTube Data API v3 — 자동 업로드 유틸리티

인증 흐름:
1. client_secret.json (Google Cloud Console OAuth 2.0 클라이언트 ID)
2. 최초 실행 시 브라우저 OAuth 승인 → token.pkl 저장
3. 이후 실행 시 저장된 토큰 재사용 (만료 시 자동 갱신)

필요한 OAuth 스코프:
  youtube.upload  — 영상 업로드
  youtube         — 썸네일 설정 (upload 스코프보다 상위)
"""

import os
import pickle


SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
TOKEN_FILENAME = "youtube_token.pkl"


class YouTubeUploader:
    def __init__(
        self,
        client_secret_path: str = "client_secret.json",
        token_dir: str = ".",
    ):
        self.client_secret_path = client_secret_path
        self.token_path = os.path.join(token_dir, TOKEN_FILENAME)
        self._youtube = None

    # ─── 인증 상태 확인 ──────────────────────────────────────────────────

    def is_authenticated(self) -> bool:
        """저장된 토큰이 유효한지 확인 (만료 시 자동 갱신 시도)."""
        if not os.path.exists(self.token_path):
            return False
        try:
            from google.auth.transport.requests import Request
            with open(self.token_path, "rb") as f:
                creds = pickle.load(f)
            if creds and creds.valid:
                return True
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(self.token_path, "wb") as f:
                    pickle.dump(creds, f)
                return True
        except Exception:
            pass
        return False

    def get_channel_info(self) -> dict:
        """인증된 계정의 채널 정보 반환."""
        youtube = self._authenticate()
        resp = youtube.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            snippet = items[0].get("snippet", {})
            return {
                "id": items[0].get("id", ""),
                "title": snippet.get("title", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            }
        return {}

    # ─── OAuth 인증 ──────────────────────────────────────────────────────

    def _authenticate(self):
        """토큰 로드 또는 OAuth 플로우 실행. youtube API 클라이언트 반환."""
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        credentials = None

        # 저장된 토큰 불러오기
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, "rb") as f:
                    credentials = pickle.load(f)
            except Exception:
                credentials = None

        # 토큰 없거나 만료 → 재인증
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                except Exception:
                    credentials = None

            if not credentials or not credentials.valid:
                if not os.path.exists(self.client_secret_path):
                    raise FileNotFoundError(
                        f"client_secret.json을 찾을 수 없습니다: {self.client_secret_path}\n"
                        "Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 다운로드하세요."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, SCOPES
                )
                # 로컬 서버에서 OAuth 콜백 수신 (브라우저가 자동으로 열림)
                credentials = flow.run_local_server(port=0, open_browser=True)

            # 토큰 저장
            with open(self.token_path, "wb") as f:
                pickle.dump(credentials, f)

        return build("youtube", "v3", credentials=credentials)

    def revoke_token(self):
        """저장된 인증 토큰 삭제 (재인증 필요 상태로 초기화)."""
        if os.path.exists(self.token_path):
            os.remove(self.token_path)

    # ─── 영상 업로드 ─────────────────────────────────────────────────────

    def upload(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: list = None,
        category_id: str = "22",
        privacy: str = "private",
        thumbnail_path: str = None,
        progress_callback=None,
    ) -> dict:
        """영상을 유튜브에 업로드하고 썸네일을 설정합니다.

        Args:
            video_path: 업로드할 MP4 파일 경로
            title: 영상 제목
            description: 영상 설명
            tags: 태그 목록
            category_id: 카테고리 ID ("22" = People & Blogs)
            privacy: "private" | "unlisted" | "public"
            thumbnail_path: 썸네일 이미지 경로 (선택)
            progress_callback: 진행률 콜백 fn(percent: int, status: str)

        Returns:
            업로드된 영상의 API 응답 dict (id 포함)
        """
        from googleapiclient.http import MediaFileUpload

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"영상 파일을 찾을 수 없습니다: {video_path}")

        youtube = self._authenticate()

        file_size_mb = os.path.getsize(video_path) / 1024 / 1024

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title[:100],           # YouTube 제목 최대 100자
                    "description": description[:5000],  # 최대 5000자
                    "tags": (tags or [])[:500],     # 태그 최대 500개
                    "categoryId": category_id,
                    "defaultLanguage": "ko",
                    "defaultAudioLanguage": "ko",
                },
                "status": {
                    "privacyStatus": privacy,
                    "selfDeclaredMadeForKids": False,
                },
            },
            media_body=MediaFileUpload(
                video_path,
                mimetype="video/mp4",
                resumable=True,
                chunksize=10 * 1024 * 1024,  # 10MB 청크
            ),
        )

        if progress_callback:
            progress_callback(0, f"업로드 시작 ({file_size_mb:.0f} MB)")

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status and progress_callback:
                pct = int(status.progress() * 100)
                uploaded_mb = file_size_mb * status.progress()
                progress_callback(pct, f"{pct}% ({uploaded_mb:.0f} / {file_size_mb:.0f} MB)")

        video_id = response.get("id", "")

        if progress_callback:
            progress_callback(100, "업로드 완료, 썸네일 설정 중...")

        # 썸네일 업로드
        if thumbnail_path and os.path.exists(thumbnail_path) and video_id:
            ext = os.path.splitext(thumbnail_path)[1].lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype=mime),
            ).execute()

        if progress_callback:
            progress_callback(100, "완료!")

        return response
