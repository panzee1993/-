"""FFmpeg 직접 호출 기반 영상 합성 유틸리티

MoviePy TextClip 대신 FFmpeg를 직접 사용:
- ASS 자막 파일 생성 → ass= 필터로 소각 (libass 필요)
- 나레이션 줄별 타이밍 계산 (장면 시간을 줄 수로 균등 분배)
- 장면 시간을 나레이션 글자 수에 비례 배분
- Ken Burns 효과 (zoompan 필터, 선택)
- BGM 혼합 (amix 필터)
"""

import os
import json
import subprocess
import shutil
import tempfile


# 자막 정렬값 (ASS Alignment 필드: numpad 방향)
_ALIGN_MAP = {"하단": 2, "중앙": 5, "상단": 8}


def _hex_to_ass_color(hex_color: str, alpha: int = 0) -> str:
    """#RRGGBB → &HAABBGGRR (ASS 색상 형식)"""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _seconds_to_ass_time(seconds: float) -> str:
    """초(float) → H:MM:SS.CC (ASS 자막 시간 형식)"""
    total_cs = int(round(seconds * 100))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


class VideoMaker:
    def __init__(self, config: dict):
        self.config = config
        video_cfg = config.get("video", {})
        self.fps = video_cfg.get("fps", 24)
        self.codec = video_cfg.get("codec", "libx264")
        res = video_cfg.get("resolution", {})
        self.width = res.get("width", 1920)
        self.height = res.get("height", 1080)

    # ─── FFmpeg 실행 헬퍼 ─────────────────────────────────

    def _run_ffmpeg(self, cmd: list) -> str:
        """FFmpeg 실행. 실패 시 stderr 포함 RuntimeError"""
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            tail = result.stderr[-3000:] if result.stderr else "(출력 없음)"
            raise RuntimeError(
                f"FFmpeg 오류 (종료코드 {result.returncode}):\n{tail}"
            )
        return result.stderr

    def _get_audio_duration(self, audio_path: str) -> float:
        """ffprobe로 오디오 파일의 재생 시간(초) 반환"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe 실패: {result.stderr}")
        data = json.loads(result.stdout or "{}")
        for stream in data.get("streams", []):
            if "duration" in stream:
                return float(stream["duration"])
        # fallback: format duration
        cmd2 = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", audio_path,
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True)
        data2 = json.loads(result2.stdout or "{}")
        fmt_dur = data2.get("format", {}).get("duration")
        if fmt_dur:
            return float(fmt_dur)
        raise RuntimeError("오디오 재생 시간을 읽을 수 없습니다.")

    # ─── 장면 시간 배분 ──────────────────────────────────

    def _assign_durations(self, scenes: list, total_duration: float) -> list:
        """나레이션 글자 수에 비례해 장면별 재생 시간 배분.
        나레이션이 없는 장면은 평균 길이(1)로 처리.
        최소 2초 보장.
        """
        lengths = [max(1, len((s.get("narration") or "").strip())) for s in scenes]
        total_len = sum(lengths)
        result = []
        for scene, char_len in zip(scenes, lengths):
            duration = max(2.0, (char_len / total_len) * total_duration)
            result.append({**scene, "duration": duration})
        return result

    # ─── 검은 배경 프레임 생성 ───────────────────────────

    def _create_black_frame(self, path: str):
        """이미지 없는 장면용 검은 PNG 생성"""
        try:
            from PIL import Image
            img = Image.new("RGB", (self.width, self.height), (0, 0, 0))
            img.save(path)
        except ImportError:
            self._run_ffmpeg([
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=black:size={self.width}x{self.height}",
                "-frames:v", "1",
                path,
            ])

    # ─── 슬라이드쇼 생성 ─────────────────────────────────

    def _create_slideshow(
        self,
        scenes: list,
        fps: int,
        output_path: str,
        tmp_dir: str,
        ken_burns: bool = False,
    ) -> str:
        """장면 이미지들 → 슬라이드쇼 MP4 생성"""
        if ken_burns:
            return self._create_slideshow_ken_burns(scenes, fps, output_path, tmp_dir)
        return self._create_slideshow_simple(scenes, fps, output_path, tmp_dir)

    def _create_slideshow_simple(
        self, scenes: list, fps: int, output_path: str, tmp_dir: str
    ) -> str:
        """FFmpeg concat demuxer로 빠른 슬라이드쇼 생성"""
        concat_file = os.path.join(tmp_dir, "images.txt")
        last_img = None

        with open(concat_file, "w", encoding="utf-8") as f:
            for i, scene in enumerate(scenes):
                img = scene.get("image_path", "")
                if not img or not os.path.exists(img):
                    bp = os.path.join(tmp_dir, f"black_{i:04d}.png")
                    self._create_black_frame(bp)
                    img = bp
                last_img = img
                duration = scene.get("duration", 5.0)
                safe = img.replace("'", "\\'")
                f.write(f"file '{safe}'\n")
                f.write(f"duration {duration:.4f}\n")

            # FFmpeg concat demuxer quirk: 마지막 이미지 한 번 더 기재
            if last_img:
                safe = last_img.replace("'", "\\'")
                f.write(f"file '{safe}'\n")

        vf = (
            f"scale={self.width}:{self.height}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={fps}"
        )
        self._run_ffmpeg([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-vf", vf,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_path,
        ])
        return output_path

    def _create_slideshow_ken_burns(
        self, scenes: list, fps: int, output_path: str, tmp_dir: str
    ) -> str:
        """각 이미지에 Ken Burns (zoompan) 효과 적용 후 concat"""
        clip_paths = []
        for i, scene in enumerate(scenes):
            img = scene.get("image_path", "")
            if not img or not os.path.exists(img):
                bp = os.path.join(tmp_dir, f"black_{i:04d}.png")
                self._create_black_frame(bp)
                img = bp

            duration = scene.get("duration", 5.0)
            frames = max(1, int(round(duration * fps)))
            clip_path = os.path.join(tmp_dir, f"clip_{i:04d}.mp4")

            # 짝수 장면: 줌인(중앙), 홀수 장면: 줌아웃(중앙)
            if i % 2 == 0:
                z_expr = "min(zoom+0.001\\,1.25)"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            else:
                z_expr = "if(eq(on\\,1)\\,1.25\\,max(1\\,zoom-0.001))"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"

            # 이미지를 2배 크기로 스케일 후 zoompan → 원본 해상도로
            vf = (
                f"scale={self.width * 2}:{self.height * 2},"
                f"zoompan="
                f"z='{z_expr}':"
                f"d={frames}:"
                f"x='{x_expr}':"
                f"y='{y_expr}':"
                f"s={self.width}x{self.height},"
                f"setpts=PTS-STARTPTS"
            )
            self._run_ffmpeg([
                "ffmpeg", "-y",
                "-loop", "1", "-i", img,
                "-vf", vf,
                "-t", str(duration),
                "-r", str(fps),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                clip_path,
            ])
            clip_paths.append(clip_path)

        # 개별 클립들을 하나로 이어 붙이기
        concat_file = os.path.join(tmp_dir, "clips.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for cp in clip_paths:
                safe = cp.replace("'", "\\'")
                f.write(f"file '{safe}'\n")

        self._run_ffmpeg([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy",
            output_path,
        ])
        return output_path

    # ─── ASS 자막 생성 ───────────────────────────────────

    def _generate_ass(
        self,
        scenes: list,
        fontname: str = "NanumGothic",
        fontsize: int = 75,
        color: str = "#FFFFFF",
        outline: int = 3,
        position: str = "하단",
        ass_path: str = None,
    ) -> str:
        """ASS 자막 파일 생성.

        각 장면의 나레이션을 줄 단위로 분할해 장면 시간을 균등 배분.
        예) 장면 10초, 나레이션 5줄 → 줄당 2초씩 표시.
        """
        alignment = _ALIGN_MAP.get(position, 2)
        margin_v = 60 if position == "하단" else 40

        primary_color = _hex_to_ass_color(color)
        outline_color = _hex_to_ass_color("#000000")
        shadow_color = _hex_to_ass_color("#000000", alpha=0x80)

        header = "\n".join([
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {self.width}",
            f"PlayResY: {self.height}",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding",
            (
                f"Style: Default,{fontname},{fontsize},"
                f"{primary_color},&H000000FF,{outline_color},{shadow_color},"
                f"0,0,0,0,100,100,0,0,1,{outline},0,"
                f"{alignment},20,20,{margin_v},1"
            ),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ])

        events = []
        cumulative = 0.0

        for scene in scenes:
            duration = scene.get("duration", 5.0)
            narration = (scene.get("narration") or "").strip()

            if not narration:
                cumulative += duration
                continue

            # 빈 줄 제거 후 분할
            lines = [ln.strip() for ln in narration.split("\n") if ln.strip()]
            if not lines:
                cumulative += duration
                continue

            time_per_line = duration / len(lines)
            for line in lines:
                t_start = _seconds_to_ass_time(cumulative)
                t_end = _seconds_to_ass_time(cumulative + time_per_line)
                # ASS 특수문자 이스케이프
                text = line.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                events.append(
                    f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{text}"
                )
                cumulative += time_per_line

        content = header + "\n" + "\n".join(events) + "\n"

        if ass_path is None:
            fd, ass_path = tempfile.mkstemp(suffix=".ass")
            os.close(fd)

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(content)

        return ass_path

    # ─── 최종 합성 ───────────────────────────────────────

    def _combine(
        self,
        slideshow_path: str,
        audio_path: str,
        ass_path: str | None,
        bgm_path: str | None,
        bgm_volume: float,
        output_path: str,
    ):
        """슬라이드쇼 + 오디오 + 자막(선택) + BGM(선택) 최종 합성"""
        # Windows 경로의 드라이브 콜론을 FFmpeg filter_complex 내에서 이스케이프
        def esc_ass(p: str) -> str:
            return p.replace("\\", "/").replace(":", "\\:")

        has_ass = ass_path and os.path.exists(ass_path)
        has_bgm = bgm_path and os.path.exists(bgm_path)

        inputs = ["-i", slideshow_path, "-i", audio_path]
        if has_bgm:
            inputs += ["-i", bgm_path]

        if has_ass and has_bgm:
            # 자막 + BGM
            safe_ass = esc_ass(ass_path)
            filter_complex = (
                f"[0:v]ass='{safe_ass}'[v];"
                f"[1:a][2:a]amix=inputs=2:duration=first:"
                f"dropout_transition=0:weights=1 {bgm_volume}[a]"
            )
            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "[v]", "-map", "[a]",
                "-c:v", self.codec, "-c:a", "aac",
                "-shortest",
                output_path,
            ]
        elif has_ass and not has_bgm:
            # 자막만
            safe_ass = esc_ass(ass_path)
            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-vf", f"ass='{safe_ass}'",
                "-map", "0:v", "-map", "1:a",
                "-c:v", self.codec, "-c:a", "aac",
                "-shortest",
                output_path,
            ]
        elif not has_ass and has_bgm:
            # BGM만
            filter_complex = (
                f"[1:a][2:a]amix=inputs=2:duration=first:"
                f"dropout_transition=0:weights=1 {bgm_volume}[a]"
            )
            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[a]",
                "-c:v", self.codec, "-c:a", "aac",
                "-shortest",
                output_path,
            ]
        else:
            # 자막/BGM 없음
            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-map", "0:v", "-map", "1:a",
                "-c:v", self.codec, "-c:a", "aac",
                "-shortest",
                output_path,
            ]

        self._run_ffmpeg(cmd)

    # ─── 공개 메서드 ─────────────────────────────────────

    def create_video(
        self,
        scenes: list[dict],
        audio_path: str,
        subtitle_enabled: bool = True,
        subtitle_fontname: str = "NanumGothic",
        subtitle_fontsize: int = 75,
        subtitle_color: str = "#FFFFFF",
        subtitle_stroke: int = 3,
        subtitle_position: str = "하단",
        ken_burns: bool = False,
        bgm_path: str = None,
        bgm_volume: float = 0.1,
        fps: int = None,
        output_name: str = "output.mp4",
        output_dir: str = "output",
    ) -> str:
        """전체 파이프라인 실행 후 출력 MP4 경로 반환.

        파이프라인:
        1. 오디오 길이 측정
        2. 나레이션 글자 수 비례로 장면별 시간 배분
        3. 이미지 → 슬라이드쇼 MP4 (Ken Burns 선택)
        4. 나레이션 줄 단위 ASS 자막 생성
        5. 슬라이드쇼 + 오디오 + 자막 + BGM 최종 합성
        """
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_name)
        fps = fps or self.fps

        tmp_dir = os.path.join(output_dir, "_tmp_video")
        os.makedirs(tmp_dir, exist_ok=True)

        try:
            # 1. 오디오 길이 → 장면 시간 배분
            total_duration = self._get_audio_duration(audio_path)
            if total_duration <= 0:
                raise ValueError("오디오 파일의 재생 시간을 읽을 수 없습니다.")
            scenes = self._assign_durations(scenes, total_duration)

            # 2. 슬라이드쇼 생성
            slideshow_path = os.path.join(tmp_dir, "slideshow.mp4")
            self._create_slideshow(scenes, fps, slideshow_path, tmp_dir, ken_burns)

            # 3. 자막 파일 생성
            ass_path = None
            if subtitle_enabled and any((s.get("narration") or "").strip() for s in scenes):
                ass_path = os.path.join(tmp_dir, "subtitles.ass")
                self._generate_ass(
                    scenes,
                    fontname=subtitle_fontname,
                    fontsize=subtitle_fontsize,
                    color=subtitle_color,
                    outline=subtitle_stroke,
                    position=subtitle_position,
                    ass_path=ass_path,
                )

            # 4. 최종 합성
            self._combine(
                slideshow_path=slideshow_path,
                audio_path=audio_path,
                ass_path=ass_path,
                bgm_path=bgm_path,
                bgm_volume=bgm_volume,
                output_path=output_path,
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return output_path
