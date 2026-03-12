"""프로젝트 데이터를 JSON 파일로 저장하고 불러오는 유틸리티"""

import os
import json
from datetime import datetime


class ProjectManager:
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "projects")
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _project_path(self, project_name: str) -> str:
        return os.path.join(self.base_dir, project_name)

    def _ensure_project_dir(self, project_name: str):
        path = self._project_path(project_name)
        for subdir in ["", "images", "audio", "output"]:
            os.makedirs(os.path.join(path, subdir), exist_ok=True)
        return path

    def list_projects(self) -> list[str]:
        if not os.path.exists(self.base_dir):
            return []
        return [
            d for d in os.listdir(self.base_dir)
            if os.path.isdir(os.path.join(self.base_dir, d))
        ]

    def save_script(self, project_name: str, script: str, meta: dict = None):
        project_dir = self._ensure_project_dir(project_name)

        # 스크립트 저장
        script_path = os.path.join(project_dir, "script.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        # 메타 정보 저장
        project_json_path = os.path.join(project_dir, "project.json")
        existing = {}
        if os.path.exists(project_json_path):
            with open(project_json_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        existing.update({
            "project_name": project_name,
            "script_path": script_path,
            "updated_at": datetime.now().isoformat(),
            **(meta or {}),
        })
        if "created_at" not in existing:
            existing["created_at"] = datetime.now().isoformat()

        with open(project_json_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def load_script(self, project_name: str) -> str:
        script_path = os.path.join(self._project_path(project_name), "script.txt")
        if os.path.exists(script_path):
            with open(script_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def save_scenes(self, project_name: str, scenes: list):
        project_dir = self._ensure_project_dir(project_name)
        scenes_path = os.path.join(project_dir, "scenes.json")
        with open(scenes_path, "w", encoding="utf-8") as f:
            json.dump(scenes, f, ensure_ascii=False, indent=2)

    def load_scenes(self, project_name: str) -> list:
        scenes_path = os.path.join(self._project_path(project_name), "scenes.json")
        if os.path.exists(scenes_path):
            with open(scenes_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def get_project_meta(self, project_name: str) -> dict:
        project_json_path = os.path.join(self._project_path(project_name), "project.json")
        if os.path.exists(project_json_path):
            with open(project_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def get_image_dir(self, project_name: str) -> str:
        return os.path.join(self._project_path(project_name), "images")

    def get_audio_dir(self, project_name: str) -> str:
        return os.path.join(self._project_path(project_name), "audio")

    def get_output_dir(self, project_name: str) -> str:
        return os.path.join(self._project_path(project_name), "output")
