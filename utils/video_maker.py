"""FFmpeg + MoviePy 기반 영상 합성 유틸리티"""

import os


SUBTITLE_POSITION_MAP = {
    "하단": ("center", 0.85),
    "중앙": ("center", "center"),
    "상단": ("center", 0.05),
}


class VideoMaker:
    def __init__(self, config: dict):
        self.config = config
        video_cfg = config.get("video", {})
        self.fps = video_cfg.get("fps", 24)
        self.codec = video_cfg.get("codec", "libx264")
        self.width = video_cfg.get("resolution", {}).get("width", 1920)
        self.height = video_cfg.get("resolution", {}).get("height", 1080)

    def create_video(
        self,
        scenes: list[dict],
        audio_path: str,
        subtitle_fontsize: int = 75,
        subtitle_color: str = "#FFFFFF",
        subtitle_stroke: int = 2,
        subtitle_position: str = "하단",
        bgm_path: str = None,
        bgm_volume: float = 0.1,
        fps: int = None,
        output_name: str = "output.mp4",
        output_dir: str = "output",
    ) -> str:
        from moviepy.editor import (
            ImageClip,
            AudioFileClip,
            CompositeVideoClip,
            TextClip,
            concatenate_videoclips,
            CompositeAudioClip,
        )

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_name)
        fps = fps or self.fps

        # 전체 오디오 길이 파악
        full_audio = AudioFileClip(audio_path)
        total_duration = full_audio.duration

        # 장면당 시간 균등 분배 (나중에 씬별 타이밍으로 고도화 가능)
        scene_count = len(scenes)
        scene_duration = total_duration / scene_count if scene_count > 0 else 5.0

        # 자막 위치 변환
        pos_key = subtitle_position if subtitle_position in SUBTITLE_POSITION_MAP else "하단"
        pos_x, pos_y = SUBTITLE_POSITION_MAP[pos_key]

        clips = []
        for i, scene in enumerate(scenes):
            image_path = scene.get("image_path", "")
            narration = scene.get("narration", "")
            duration = scene.get("duration", scene_duration)

            # 이미지 클립
            if image_path and os.path.exists(image_path):
                img_clip = (
                    ImageClip(image_path)
                    .set_duration(duration)
                    .resize((self.width, self.height))
                )
            else:
                # 이미지 없을 경우 검은 화면
                from moviepy.editor import ColorClip
                img_clip = ColorClip(
                    size=(self.width, self.height),
                    color=(0, 0, 0),
                    duration=duration,
                )

            # 자막 클립
            if narration:
                txt_clip = (
                    TextClip(
                        narration,
                        fontsize=subtitle_fontsize,
                        color=subtitle_color.lstrip("#"),
                        stroke_color="black",
                        stroke_width=subtitle_stroke,
                        size=(self.width - 120, None),
                        method="caption",
                    )
                    .set_position((pos_x, pos_y), relative=isinstance(pos_y, float))
                    .set_duration(duration)
                )
                composite = CompositeVideoClip([img_clip, txt_clip])
            else:
                composite = img_clip

            clips.append(composite)

        if not clips:
            raise ValueError("합성할 장면이 없습니다.")

        # 영상 합치기
        final = concatenate_videoclips(clips, method="compose")

        # 음성 입히기
        final = final.set_audio(full_audio)

        # 배경음악 (선택)
        if bgm_path and os.path.exists(bgm_path):
            bgm = AudioFileClip(bgm_path).volumex(bgm_volume)
            final_audio = CompositeAudioClip([full_audio, bgm])
            final = final.set_audio(final_audio)

        # 내보내기
        final.write_videofile(
            output_path,
            fps=fps,
            codec=self.codec,
            audio_codec="aac",
            threads=4,
        )

        return output_path
