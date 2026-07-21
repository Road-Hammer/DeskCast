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

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .models import Line, Outline, Script

W, H = 1280, 720

ACCENT = (220, 50, 47)
GOLD = (240, 190, 60)
WHITE = (250, 250, 250)
MUTED = (175, 185, 205)
PBP_COLOR = (200, 40, 40)
COLOR_COLOR = (30, 110, 190)
ON_AIR = (50, 210, 100)
SHADOW = (0, 0, 0, 140)


def project_assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets"


def ensure_default_hosts(assets: Path | None = None) -> dict[str, Path]:
    """Return host/desk asset paths. Prefer photoreal assets; only draw placeholders if missing."""
    root = assets or project_assets_dir()
    hosts = root / "hosts"
    hosts.mkdir(parents=True, exist_ok=True)
    (root / "broll").mkdir(parents=True, exist_ok=True)
    (root / "set").mkdir(parents=True, exist_ok=True)

    paths = {
        "pbp": hosts / "mike_pbp.png",
        "color": hosts / "dana_color.png",
        "desk": root / "set" / "desk_bg.png",
    }
    # Placeholders only if professional assets not present
    if not paths["pbp"].exists() or paths["pbp"].stat().st_size < 50_000:
        _draw_host_portrait(paths["pbp"], name="MIKE", role="PBP", skin=(230, 190, 160), shirt=PBP_COLOR, hair=(40, 30, 25))
    if not paths["color"].exists() or paths["color"].stat().st_size < 50_000:
        _draw_host_portrait(paths["color"], name="DANA", role="COLOR", skin=(210, 170, 140), shirt=COLOR_COLOR, hair=(90, 55, 35))
    if not paths["desk"].exists() or paths["desk"].stat().st_size < 50_000:
        _draw_simple_desk(paths["desk"])
    return paths


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_host_portrait(
    path: Path,
    *,
    name: str,
    role: str,
    skin: tuple[int, int, int],
    shirt: tuple[int, int, int],
    hair: tuple[int, int, int],
    size: tuple[int, int] = (420, 520),
) -> None:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([20, 40, w - 20, h - 10], fill=(30, 40, 60, 200))
    d.ellipse([40, 300, w - 40, h + 80], fill=shirt + (255,))
    d.polygon([(w // 2 - 40, 320), (w // 2, 380), (w // 2 + 40, 320)], fill=(20, 20, 30, 255))
    d.rectangle([w // 2 - 28, 250, w // 2 + 28, 320], fill=skin + (255,))
    d.ellipse([w // 2 - 90, 90, w // 2 + 90, 290], fill=skin + (255,))
    d.ellipse([w // 2 - 95, 70, w // 2 + 95, 180], fill=hair + (255,))
    d.ellipse([w // 2 - 45, 160, w // 2 - 20, 185], fill=(30, 30, 35, 255))
    d.ellipse([w // 2 + 20, 160, w // 2 + 45, 185], fill=(30, 30, 35, 255))
    d.arc([w // 2 - 35, 200, w // 2 + 35, 250], 20, 160, fill=(120, 70, 60, 255), width=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def _draw_simple_desk(path: Path) -> None:
    img = Image.new("RGB", (W, H), (12, 18, 32))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 500, W, H], fill=(28, 36, 52))
    d.rectangle([60, 508, W - 60, 516], fill=ACCENT)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


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


def _load_host(path: Path, max_h: int) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    # If image is fully opaque (no cutout), apply soft oval vignette so it composites cleanly
    alpha = im.split()[-1]
    extrema = alpha.getextrema()
    if extrema[0] > 240:  # nearly fully opaque
        mask = Image.new("L", im.size, 0)
        md = ImageDraw.Draw(mask)
        # oval focus on upper body
        md.ellipse([int(im.width * 0.05), int(im.height * 0.02), int(im.width * 0.95), int(im.height * 0.98)], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(18))
        im.putalpha(mask)
    ratio = max_h / im.height
    nw, nh = max(1, int(im.width * ratio)), max(1, int(im.height * ratio))
    return im.resize((nw, nh), Image.Resampling.LANCZOS)


def _paste_host(
    base: Image.Image,
    portrait: Image.Image,
    *,
    center_x: int,
    bottom_y: int,
    active: bool,
    bob: int = 0,
) -> None:
    img = portrait.copy()
    if not active:
        img = ImageEnhance.Brightness(img).enhance(0.42)
        img = ImageEnhance.Color(img).enhance(0.5)
        img = ImageEnhance.Contrast(img).enhance(0.9)
    else:
        # soft glow behind active host
        glow = img.filter(ImageFilter.GaussianBlur(10))
        glow = ImageEnhance.Brightness(glow).enhance(1.35)
        gx = center_x - glow.width // 2
        gy = bottom_y - glow.height - bob + 12
        base.paste(glow, (gx, gy), glow)
        img = ImageEnhance.Contrast(img).enhance(1.05)
        img = ImageEnhance.Brightness(img).enhance(1.04)

    # Drop shadow
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sa = img.split()[-1].point(lambda p: int(p * 0.45))
    shadow.putalpha(sa)
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    sx = center_x - img.width // 2 + 10
    sy = bottom_y - img.height - bob + 14
    base.paste(shadow, (sx, sy), shadow)

    x = center_x - img.width // 2
    y = bottom_y - img.height - bob
    base.paste(img, (x, y), img)

    if active:
        d = ImageDraw.Draw(base)
        # ON AIR pill
        pill = [center_x - 48, bottom_y - 8, center_x + 48, bottom_y + 14]
        d.rounded_rectangle(pill, radius=8, fill=ON_AIR)
        d.text((center_x - 28, bottom_y - 6), "ON AIR", font=_font(14, bold=True), fill=(10, 20, 10))


def _pick_broll(broll_dir: Path | None, index: int) -> Image.Image | None:
    if not broll_dir or not broll_dir.exists():
        return None
    files = sorted(
        [
            *broll_dir.glob("*.png"),
            *broll_dir.glob("*.jpg"),
            *broll_dir.glob("*.jpeg"),
            *broll_dir.glob("*.webp"),
        ]
    )
    if not files:
        return None
    path = files[index % len(files)]
    im = Image.open(path).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    return ImageEnhance.Brightness(im).enhance(0.32)


def _lower_third(
    d: ImageDraw.ImageDraw,
    x: int,
    y: int,
    name: str,
    role: str,
    color: tuple[int, int, int],
) -> None:
    # Modern sports lower-third: accent bar + dark plate
    d.rectangle([x, y, x + 8, y + 56], fill=color)
    d.rectangle([x + 8, y, x + 300, y + 34], fill=(12, 14, 22, 235))
    d.rectangle([x + 8, y + 34, x + 300, y + 56], fill=(22, 26, 38, 235))
    d.text((x + 18, y + 6), name, font=_font(20, bold=True), fill=WHITE)
    d.text((x + 18, y + 36), role, font=_font(13, bold=True), fill=GOLD)


def render_character_frame(
    path: Path,
    *,
    show_title: str,
    line: Line,
    source_blurb: str,
    index: int,
    total: int,
    host_paths: dict[str, Path],
    segment_label: str = "",
    broll: Image.Image | None = None,
    hybrid: bool = False,
) -> None:
    desk = Image.open(host_paths["desk"]).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    if broll is not None:
        base = Image.blend(broll.convert("RGB"), desk, 0.55).convert("RGBA")
    else:
        base = desk.convert("RGBA")

    # Subtle top gradient for broadcast bar readability
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(0, 90):
        a = int(140 * (1 - y / 90))
        od.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    for y in range(H - 160, H):
        t = (y - (H - 160)) / 160
        od.line([(0, y), (W, y)], fill=(0, 0, 0, int(160 * t)))
    base = Image.alpha_composite(base, overlay)

    pbp = _load_host(host_paths["pbp"], 520)
    color = _load_host(host_paths["color"], 520)

    if line.role == "pbp":
        active_pbp, active_color = True, False
    elif line.role == "color":
        active_pbp, active_color = False, True
    else:
        active_pbp, active_color = True, True

    bob_p = 5 if active_pbp else 0
    bob_c = 5 if active_color else 0

    # When one host is active, push them slightly larger via re-load? keep same size, positions
    # Active host slightly forward (lower bottom_y = higher on screen? bottom_y is feet)
    # Sit them behind desk line ~ y=500
    _paste_host(base, pbp, center_x=360, bottom_y=505, active=active_pbp, bob=bob_p)
    _paste_host(base, color, center_x=920, bottom_y=505, active=active_color, bob=bob_c)

    d = ImageDraw.Draw(base)
    title_f = _font(28, bold=True)
    body_f = _font(23)
    small_f = _font(16)
    tiny_f = _font(14)

    # Top bar
    d.rectangle([0, 0, W, 52], fill=(8, 10, 18, 230))
    d.rectangle([0, 52, W, 56], fill=ACCENT)
    d.text((22, 12), "DESKCAST", font=title_f, fill=GOLD)
    d.text((200, 18), "LIVE DESK", font=small_f, fill=MUTED)
    # Small ownership mark (Susquehanna Timberwolf Lines, LLC)
    d.text((200, 34), "(c) 2026 Susquehanna Timberwolf Lines, LLC", font=_font(11), fill=(120, 130, 150))
    # LIVE pill
    d.rounded_rectangle([W - 280, 12, W - 210, 40], radius=4, fill=ACCENT)
    d.text((W - 268, 16), "LIVE", font=small_f, fill=WHITE)
    d.text((W - 195, 16), f"{index + 1}/{total}", font=small_f, fill=MUTED)

    # Show title
    d.rounded_rectangle([20, 68, 20 + min(700, 18 * max(8, len(show_title[:42]))), 104], radius=6, fill=(0, 0, 0, 170))
    d.text((32, 76), show_title[:42], font=_font(18, bold=True), fill=WHITE)

    if segment_label:
        d.rounded_rectangle([W - 340, 68, W - 20, 104], radius=6, fill=(0, 0, 0, 180))
        d.rectangle([W - 340, 68, W - 332, 104], fill=ACCENT)
        d.text((W - 324, 78), segment_label[:30].upper(), font=small_f, fill=WHITE)

    # Lower thirds
    if line.role == "pbp":
        _lower_third(d, 60, 518, "MIKE", "PLAY-BY-PLAY", PBP_COLOR)
    elif line.role == "color":
        _lower_third(d, 860, 518, "DANA", "COLOR ANALYST", COLOR_COLOR)
    else:
        _lower_third(d, 460, 518, line.speaker.upper()[:12], "DESK", GOLD)

    # Dialogue plate
    d.rounded_rectangle([16, 588, W - 16, H - 8], radius=8, fill=(6, 8, 16, 235))
    stripe = PBP_COLOR if line.role == "pbp" else (COLOR_COLOR if line.role == "color" else GOLD)
    d.rectangle([16, 588, 22, H - 8], fill=stripe)
    y = 598
    for ln in _wrap(d, line.text, body_f, W - 70)[:3]:
        d.text((36, y), ln, font=body_f, fill=WHITE)
        y += 28

    # Source ticker
    d.rectangle([0, H - 26, W, H], fill=(0, 0, 0, 230))
    ticker = " ".join(source_blurb.split())[:130]
    d.text((14, H - 20), f"SOURCE  ·  {ticker}", font=tiny_f, fill=MUTED)

    base.convert("RGB").save(path, "PNG", optimize=True)


def render_character_frames(
    script: Script,
    outline: Outline,
    slides_dir: Path,
    *,
    assets_dir: Path | None = None,
    broll_dir: Path | None = None,
    hybrid: bool = False,
) -> list[Path]:
    host_paths = ensure_default_hosts(assets_dir)
    bdir = broll_dir or (project_assets_dir() / "broll")
    slides_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    lines = script.all_lines()
    chunk_i = 0

    for i, line in enumerate(lines):
        if "Package" in line.text:
            try:
                part = line.text.split("Package", 1)[1].strip().split()[0]
                chunk_i = max(0, min(int(part) - 1, len(outline.chunks) - 1))
            except Exception:
                pass
        ch = outline.chunks[chunk_i] if outline.chunks else None
        seg = f"PKG {chunk_i + 1}/{max(1, len(outline.chunks))}"
        if ch:
            kind = (ch.kind or line.chunk_kind or "narrative").upper()
            pri = ch.priority or 0
            flag = "!" if pri >= 8 else ""
            seg = f"{flag}{kind} · {ch.title[:16]}"

        use_broll = None
        if hybrid:
            use_broll = _pick_broll(bdir, i)

        # Prefer metadata on the line when present
        if line.chunk_kind and ch is None:
            seg = f"{line.chunk_kind.upper()}"

        out = slides_dir / f"{i:03d}.png"
        render_character_frame(
            out,
            show_title=script.title,
            line=line,
            source_blurb=ch.text if ch else "",
            index=i,
            total=len(lines),
            host_paths=host_paths,
            segment_label=seg,
            broll=use_broll,
            hybrid=hybrid,
        )
        paths.append(out)
    return paths
