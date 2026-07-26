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

from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from .characters import render_character_frames
from .hosts import DeskMode, DeskModeId
from .models import Line, Outline, Script

VisualMode = Literal["slides", "characters", "hybrid"]

W, H = 1280, 720
BG = (12, 18, 32)
PANEL = (22, 34, 58)
ACCENT = (220, 50, 47)
GOLD = (240, 190, 60)
WHITE = (245, 245, 245)
MUTED = (170, 180, 200)


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = (" ".join(cur + [w])).strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines or [""]


def render_slides(
    script: Script,
    outline: Outline,
    slides_dir: Path,
    *,
    visuals: VisualMode = "characters",
    assets_dir: Path | None = None,
    broll_dir: Path | None = None,
    desk_mode: str | DeskModeId | DeskMode | None = None,
) -> list[Path]:
    """Render per-line frames. Default visuals=characters (phase-1 desk hosts)."""
    if visuals in ("characters", "hybrid"):
        return render_character_frames(
            script,
            outline,
            slides_dir,
            assets_dir=assets_dir,
            broll_dir=broll_dir,
            hybrid=(visuals == "hybrid"),
            desk_mode=desk_mode,
        )
    return _render_classic_slides(script, outline, slides_dir)


def _render_classic_slides(
    script: Script,
    outline: Outline,
    slides_dir: Path,
) -> list[Path]:
    slides_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    lines = script.all_lines()
    chunk_i = 0
    for i, line in enumerate(lines):
        if line.role in ("pbp", "color") and "Package" in line.text:
            try:
                part = line.text.split("Package", 1)[1].strip().split()[0]
                chunk_i = max(0, min(int(part) - 1, len(outline.chunks) - 1))
            except Exception:
                pass
        ch = outline.chunks[chunk_i] if outline.chunks else None
        path = slides_dir / f"{i:03d}.png"
        _draw_classic_frame(path, script.title, line, ch.text if ch else "", i, len(lines))
        paths.append(path)
    return paths


def _draw_classic_frame(
    path: Path,
    show_title: str,
    line: Line,
    source_blurb: str,
    index: int,
    total: int,
) -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title_f = _font(36, bold=True)
    host_f = _font(28, bold=True)
    body_f = _font(26)
    small_f = _font(18)
    tiny_f = _font(16)

    d.rectangle([0, 0, W, 64], fill=PANEL)
    d.rectangle([0, 64, W, 70], fill=ACCENT)
    d.text((28, 16), "DESKCAST LIVE", font=title_f, fill=GOLD)
    d.text((W - 220, 22), f"{index + 1}/{total}", font=small_f, fill=MUTED)
    d.text((28, 90), show_title[:70], font=host_f, fill=WHITE)

    badge = "PLAY-BY-PLAY" if line.role == "pbp" else "COLOR ANALYST"
    if line.role == "both":
        badge = "DESK"
    badge_color = ACCENT if line.role == "pbp" else (40, 110, 180)
    d.rounded_rectangle([28, 150, 320, 198], radius=8, fill=badge_color)
    d.text((44, 160), f"{badge} · {line.speaker}", font=small_f, fill=WHITE)

    d.rounded_rectangle([28, 220, W - 28, 480], radius=12, fill=PANEL)
    y = 240
    for ln in _wrap(d, line.text, body_f, W - 100)[:8]:
        d.text((48, y), ln, font=body_f, fill=WHITE)
        y += 34

    d.rectangle([0, H - 140, W, H], fill=(8, 12, 22))
    d.text((28, H - 128), "SOURCE TICKER", font=tiny_f, fill=GOLD)
    blurb = " ".join(source_blurb.split())[:220]
    y2 = H - 100
    for ln in _wrap(d, blurb, small_f, W - 80)[:3]:
        d.text((28, y2), ln, font=small_f, fill=MUTED)
        y2 += 26

    img.save(path, "PNG")
