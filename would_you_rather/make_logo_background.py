#!/usr/bin/env python3
"""Branded Shorts background: soft gradient with the channel logo repeated as a faint pattern.

    python3 make_logo_background.py                 # orange (default)
    python3 make_logo_background.py --color blue
    python3 make_logo_background.py --video 12      # also a seamless 12 s scrolling loop

Outputs quizzies_background_<color>.png (1080x1920) and, with --video, quizzies_background_<color>.mp4.
"""

import argparse
import os
import subprocess

import numpy as np
from PIL import Image, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
LOGO = os.path.join(HERE, "profile_picture.png")
STEP_X, STEP_Y = 270, 300      # pattern spacing; the scrolling loop moves one full step so it repeats
LOGO_SIZE = 190

COLORS = {  # top, bottom, logo tint
    "orange": ((238, 104, 62), (250, 128, 74), (160, 52, 24)),
    "blue": ((40, 90, 200), (70, 140, 240), (16, 44, 120)),
    "purple": ((110, 50, 200), (160, 90, 240), (60, 20, 120)),
    "green": ((40, 160, 90), (80, 200, 120), (16, 90, 44)),
}


def logo_stamp(tint, size=LOGO_SIZE, alpha=0.30):
    """Profile picture as a flat, tinted round stamp (like a watermark)."""
    im = Image.open(LOGO).convert("RGBA").resize((size, size), Image.LANCZOS)
    g = ImageEnhance.Contrast(im.convert("L")).enhance(1.3)
    lum = np.asarray(g).astype(np.float32) / 255
    out = np.zeros((size, size, 4), np.uint8)
    out[..., :3] = np.array(tint)
    yy, xx = np.mgrid[0:size, 0:size]
    inside = np.hypot(xx - size / 2 + 0.5, yy - size / 2 + 0.5) <= size / 2 - 1
    out[..., 3] = (inside * (0.55 + 0.45 * (1 - lum)) * 255 * alpha).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def gradient(top, bot):
    t = np.linspace(0, 1, H)[:, None, None]
    arr = np.array(top)[None, None] * (1 - t) + np.array(bot)[None, None] * t
    return Image.fromarray(np.repeat(arr, W, axis=1).astype(np.uint8), "RGB").convert("RGBA")


def background(color, shift=(0.0, 0.0)):
    top, bot, tint = COLORS[color]
    im = gradient(top, bot)
    stamp = logo_stamp(tint)
    sx, sy = shift[0] % STEP_X, shift[1] % (2 * STEP_Y)   # pattern repeats every STEP_X / 2*STEP_Y
    pat = Image.new("RGBA", (W, H))
    for r in range(-3, H // STEP_Y + 3):
        off = STEP_X / 2 if r % 2 else 0   # staggered rows like the reference
        for c in range(-2, W // STEP_X + 3):
            x, y = int(c * STEP_X + off + sx), int(r * STEP_Y + sy)
            _paste_clipped(pat, stamp, x - LOGO_SIZE // 2, y - LOGO_SIZE // 2)
    im.alpha_composite(pat)
    # soft vignette for depth
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.8)) ** 2)
    v = np.zeros((H, W, 4), np.uint8)
    v[..., 3] = (np.clip(d - 0.45, 0, 1) * 110).astype(np.uint8)
    im.alpha_composite(Image.fromarray(v, "RGBA"))
    return im.convert("RGB")


def _paste_clipped(dst, src, x, y):
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dst.width, x + src.width), min(dst.height, y + src.height)
    if x1 <= x0 or y1 <= y0:
        return
    dst.alpha_composite(src.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--color", default="orange", choices=list(COLORS))
    ap.add_argument("--video", type=float, default=0, help="also render a seamless scrolling loop of this length")
    a = ap.parse_args()
    png = os.path.join(HERE, f"quizzies_background_{a.color}.png")
    background(a.color).save(png)
    print(png)
    if a.video:
        out = os.path.join(HERE, f"quizzies_background_{a.color}.mp4")
        n = int(a.video * FPS)
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                              f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                              "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
        for i in range(n):
            k = i / n  # one full pattern step per loop, diagonally, so the end matches the start
            p.stdin.write(background(a.color, (k * STEP_X, -k * 2 * STEP_Y)).tobytes())
        p.stdin.close()
        p.wait()
        print(out)


if __name__ == "__main__":
    main()
