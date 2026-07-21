# Copyright 2026 Susquehanna Timberwolf Lines, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .tts import probe_duration_seconds


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    candidates = [
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path.home() / "AppData/Local/Microsoft/WinGet/Packages",
    ]
    # WinGet Gyan package path varies; search shallow
    winget = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    if winget.exists():
        for p in winget.rglob("ffmpeg.exe"):
            return str(p)
    for c in candidates[:2]:
        if c.exists():
            return str(c)
    raise RuntimeError(
        "ffmpeg not found on PATH. Install with:\n"
        "  winget install -e --id Gyan.FFmpeg\n"
        "Then open a new terminal."
    )


def assemble_video(
    slides: list[Path],
    audio_clips: list[Path],
    out_mp4: Path,
    *,
    work_dir: Path,
) -> Path:
    if len(slides) != len(audio_clips):
        n = min(len(slides), len(audio_clips))
        slides = slides[:n]
        audio_clips = audio_clips[:n]
    if not slides:
        raise ValueError("No slides/audio to assemble")

    ffmpeg = find_ffmpeg()
    work_dir.mkdir(parents=True, exist_ok=True)
    concat_vid = work_dir / "segments.txt"
    segment_files: list[Path] = []

    for i, (slide, audio) in enumerate(zip(slides, audio_clips)):
        dur = probe_duration_seconds(audio) + 0.25  # slight pad
        seg = work_dir / f"seg_{i:03d}.mp4"
        # Still image + audio → segment
        cmd = [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-i",
            str(slide),
            "-i",
            str(audio),
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            "-t",
            f"{dur:.3f}",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-preset",
            "ultrafast",
            str(seg),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        segment_files.append(seg)

    with concat_vid.open("w", encoding="utf-8") as f:
        for seg in segment_files:
            # ffmpeg concat demuxer needs escaped paths
            p = seg.resolve().as_posix().replace("'", r"'\''")
            f.write(f"file '{p}'\n")

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_vid),
        "-c",
        "copy",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_mp4
