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

# Optional per-role prosody (edge-tts). When None, uses defaults / host profile.
Prosody = dict[str, str]  # keys: rate, pitch, volume


async def _edge_line(
    text: str,
    voice: str,
    out: Path,
    *,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
) -> None:
    import edge_tts

    # Light pause-friendly cleanup for more natural overnight reads
    spoken = _speakable(text)
    communicate = edge_tts.Communicate(
        spoken, voice, rate=rate, pitch=pitch, volume=volume
    )
    await communicate.save(str(out))


def _speakable(text: str) -> str:
    """Make line text less robotic for TTS (ellipsis, dashes, dense titles)."""
    t = " ".join(text.split())
    # Expand common legal denseness that TTS chokes on
    t = t.replace("—", ", ")
    t = t.replace("–", ", ")
    t = t.replace("…", "...")
    t = t.replace(" / ", ", ")
    # Soften package indices TTS reads poorly
    t = t.replace("pack 1 of ", "package one of ")
    t = t.replace("pack 2 of ", "package two of ")
    t = t.replace("pack 3 of ", "package three of ")
    t = t.replace("pack 4 of ", "package four of ")
    t = t.replace("pack 5 of ", "package five of ")
    # Avoid reading bare "shall" stacks without breathing room
    if len(t) > 220:
        # Insert a short breath after first sentence if missing
        for sep in (". ", "? ", "! "):
            i = t.find(sep)
            if 40 < i < 160:
                break
    return t


def synthesize_script(
    script: Script,
    audio_dir: Path,
    *,
    voice_a: str = "en-US-GuyNeural",
    voice_b: str = "en-US-JennyNeural",
    offline: bool = False,
    prosody_a: Prosody | None = None,
    prosody_b: Prosody | None = None,
) -> list[Path]:
    """Synthesize each line. prosody_* optional: rate/pitch/volume for edge-tts."""
    audio_dir.mkdir(parents=True, exist_ok=True)
    pa = prosody_a or {}
    pb = prosody_b or {}
    paths: list[Path] = []
    lines = script.all_lines()
    for i, line in enumerate(lines):
        if line.role == "color":
            voice = voice_b
            rate = pb.get("rate", "+0%")
            pitch = pb.get("pitch", "+0Hz")
            volume = pb.get("volume", "+0%")
        else:
            voice = voice_a
            rate = pa.get("rate", "+0%")
            pitch = pa.get("pitch", "+0Hz")
            volume = pa.get("volume", "+0%")
        out = audio_dir / f"{i:03d}_{line.role}.mp3"
        if offline:
            out = audio_dir / f"{i:03d}_{line.role}.wav"
            _pyttsx3_line(line.text, out, slower=(line.role == "pbp"))
        else:
            try:
                asyncio.run(
                    _edge_line(
                        line.text, voice, out, rate=rate, pitch=pitch, volume=volume
                    )
                )
            except Exception:
                # Network / edge-tts failure → offline fallback
                out = audio_dir / f"{i:03d}_{line.role}.wav"
                _pyttsx3_line(line.text, out, slower=(line.role != "color"))
        paths.append(out)
    return paths


def _pyttsx3_line(text: str, out: Path, *, slower: bool = False) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    # Overnight / lead hosts slightly slower offline too
    if slower or "_pbp" in out.name:
        engine.setProperty("rate", 145)
    else:
        engine.setProperty("rate", 160)
    engine.save_to_file(_speakable(text), str(out))
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
