"""YouTube Data API v3 — 자동 업로드 유틸리티"""

import os
import pickle


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PICKLE = "youtube_token.pkl"


class YouTubeUploader:
    def __init__(self, client_secret_path: str = "client_secret.json"):
        self.client_secret_path = client_secret_path
        self._youtube = None

    def _authenticate(self):
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle

        credentials = None

        # 저장된 토큰 불러오기
        if os.path.exists(TOKEN_PICKLE):
            with open(TOKEN_PICKLE, "rb") as f:
                credentials = pickle.load(f)

        # 토큰이 없거나 만료된 경우 재인증
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, SCOPES
                )
                credentials = flow.run_local_server(port=0)

            # 토큰 저장
            with open(TOKEN_PICKLE, "wb") as f:
                pickle.dump(credentials, f)

        return build("youtube", "v3", credentials=credentials)

    def upload(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: list[str] = None,
        category_id: str = "22",
        privacy: str = "private",
        thumbnail_path: str = None,
    ) -> dict:
        from googleapiclient.http import MediaFileUpload

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"영상 파일을 찾을 수 없습니다: {video_path}")

        youtube = self._authenticate()

        # 영상 업로드
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags or [],
                    "categoryId": category_id,
                },
                "status": {
                    "privacyStatus": privacy,
                    "selfDeclaredMadeForKids": False,
                },
            },
            media_body=MediaFileUpload(video_path, mimetype="video/mp4", resumable=True),
        )

        response = None
        while response is None:
            status, response = request.next_chunk()

        video_id = response.get("id", "")

        # 썸네일 업로드 (선택)
        if thumbnail_path and os.path.exists(thumbnail_path) and video_id:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
            ).execute()

        return response
