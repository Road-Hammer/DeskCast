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

import asyncio
import subprocess
import wave
from pathlib import Path

from .models import Line, Script


async def _edge_line(text: str, voice: str, out: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out))


def synthesize_script(
    script: Script,
    audio_dir: Path,
    *,
    voice_a: str = "en-US-GuyNeural",
    voice_b: str = "en-US-JennyNeural",
    offline: bool = False,
) -> list[Path]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    lines = script.all_lines()
    for i, line in enumerate(lines):
        voice = voice_a if line.role == "pbp" else voice_b
        if line.role == "both":
            voice = voice_a
        out = audio_dir / f"{i:03d}_{line.role}.mp3"
        if offline:
            out = audio_dir / f"{i:03d}_{line.role}.wav"
            _pyttsx3_line(line.text, out)
        else:
            try:
                asyncio.run(_edge_line(line.text, voice, out))
            except Exception:
                # Network / edge-tts failure → offline fallback
                out = audio_dir / f"{i:03d}_{line.role}.wav"
                _pyttsx3_line(line.text, out)
        paths.append(out)
    return paths


def _pyttsx3_line(text: str, out: Path) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    # Best-effort different rates for roles encoded in filename
    if "_color" in out.name:
        engine.setProperty("rate", 155)
    else:
        engine.setProperty("rate", 175)
    engine.save_to_file(text, str(out))
    engine.runAndWait()
    engine.stop()


def probe_duration_seconds(path: Path) -> float:
    """Duration via ffprobe, or wave module, or estimate."""
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return max(0.5, float(r.stdout.strip()))
    except Exception:
        pass
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as w:
                return max(0.5, w.getnframes() / float(w.getframerate()))
        except Exception:
            pass
    # crude estimate ~14 chars/sec
    try:
        # no text file; use size heuristic
        return max(1.5, path.stat().st_size / 4000)
    except Exception:
        return 3.0
