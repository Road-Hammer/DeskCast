"""Process generated studio art into DeskCast host cutouts + desk background."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

SRC = Path(
    r"C:\Users\Tony Zurenda\.grok\sessions\C%3A%5CUsers%5CTony%20Zurenda\019f7d20-9eb8-7e80-8aa0-c02611641023\images"
)
OUT = Path(__file__).resolve().parent.parent / "assets"


def cutout_portrait(im: Image.Image, crop_bottom_frac: float = 0.0) -> Image.Image:
    w, h = im.size
    if crop_bottom_frac > 0:
        im = im.crop((0, 0, w, int(h * (1 - crop_bottom_frac))))
        w, h = im.size
    rgba = im.convert("RGBA")
    arr = np.array(rgba).astype(np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    brightness = (r + g + b) / 3.0
    dark = brightness < 52
    navy = (b >= r - 8) & (b >= g - 8) & (brightness < 72)
    bg = dark | navy
    yy, xx = np.ogrid[:h, :w]
    cy, cx = h * 0.40, w * 0.5
    dist = np.sqrt(((xx - cx) / (w * 0.40)) ** 2 + ((yy - cy) / (h * 0.45)) ** 2)
    center = dist < 1.05
    m = np.where(bg & ~center, 0.0, 1.0)
    m_img = Image.fromarray((m * 255).astype(np.uint8), mode="L")
    m_img = m_img.filter(ImageFilter.GaussianBlur(radius=4.0))
    m = np.array(m_img).astype(np.float32) / 255.0
    m = np.clip(m + np.where(center & (brightness > 35), 0.3, 0), 0, 1)
    arr[:, :, 3] = (m * 255).astype(np.uint8)
    out_im = Image.fromarray(arr.astype(np.uint8), "RGBA")
    bbox = out_im.getbbox()
    if bbox:
        out_im = out_im.crop(bbox)
    target_h = 700
    ratio = target_h / out_im.height
    nw = max(1, int(out_im.width * ratio))
    return out_im.resize((nw, target_h), Image.Resampling.LANCZOS)


def main() -> None:
    (OUT / "hosts").mkdir(parents=True, exist_ok=True)
    (OUT / "set").mkdir(parents=True, exist_ok=True)

    desk = Image.open(SRC / "1.jpg").convert("RGB").resize((1280, 720), Image.Resampling.LANCZOS)
    v = Image.new("L", (1280, 720), 0)
    ImageDraw.Draw(v).ellipse([-100, -60, 1380, 780], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(90))
    edge = ImageEnhance.Brightness(desk).enhance(0.5).convert("RGBA")
    desk = Image.composite(desk.convert("RGBA"), edge, v).convert("RGB")
    desk_path = OUT / "set" / "desk_bg.png"
    desk.save(desk_path, "PNG", optimize=True)

    mike = cutout_portrait(Image.open(SRC / "3.jpg"), crop_bottom_frac=0.15)
    mike_path = OUT / "hosts" / "mike_pbp.png"
    mike.save(mike_path, "PNG")

    dana = cutout_portrait(Image.open(SRC / "2.jpg"), crop_bottom_frac=0.02)
    dana_path = OUT / "hosts" / "dana_color.png"
    dana.save(dana_path, "PNG")

    print("desk", desk_path, desk_path.stat().st_size)
    print("mike", mike.size, mike_path.stat().st_size)
    print("dana", dana.size, dana_path.stat().st_size)
    print("DONE")


if __name__ == "__main__":
    main()
