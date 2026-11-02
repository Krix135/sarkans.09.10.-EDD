#!/usr/bin/env python3
"""High-resolution YouTube profile picture (2048x2048) for the channel.

YouTube crops the picture to a circle, so everything important stays inside it.

    python3 make_profile_picture.py
    python3 make_profile_picture.py --name "QUIZZIES" --size 2048
"""

import argparse
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from make_video import (BLUE_BOT, BLUE_TOP, RED_BOT, RED_TOP, YELLOW, circle, font, paste_center,
                        radial_glow, soft_circle, vgradient)

HERE = os.path.dirname(os.path.abspath(__file__))
NAVY = (20, 22, 45)


def outlined_text(text, fnt, fill, stroke, stroke_fill, shadow_off, shadow_blur):
    """Text with a thick outline and a soft drop shadow, at any size."""
    l, t, r, b = fnt.getbbox(text, stroke_width=stroke)
    pad = shadow_off + shadow_blur * 3
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad))
    sh = Image.new("RGBA", im.size)
    ImageDraw.Draw(sh).text((pad - l + shadow_off * 0.4, pad - t + shadow_off), text, font=fnt,
                            fill=(0, 0, 0, 150), stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(shadow_blur)))
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=fnt, fill=fill, stroke_width=stroke,
                            stroke_fill=stroke_fill)
    return im


def sparkle(size, color):
    """Four-point star, supersampled for smooth edges."""
    ss = 4
    n = size * ss
    im = Image.new("RGBA", (n, n))
    c, r_out, r_in = n / 2, n / 2, n * 0.11
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        r = r_out if i % 2 == 0 else r_in
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    ImageDraw.Draw(im).polygon(pts, fill=color)
    return im.resize((size, size), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="QUIZZIES")
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--out", default=os.path.join(HERE, "profile_picture.png"))
    a = ap.parse_args()
    S = a.size
    u = S / 1000  # layout unit

    # red / blue split background, like the videos
    im = vgradient(S, S, BLUE_TOP, BLUE_BOT).convert("RGBA")
    red = vgradient(S, S, RED_TOP, RED_BOT).convert("RGBA")
    ss = 2
    mask = Image.new("L", (S * ss, S * ss))
    ImageDraw.Draw(mask).polygon([(0, 0), (S * ss * 0.58, 0), (S * ss * 0.42, S * ss), (0, S * ss)], fill=255)
    im.paste(red, (0, 0), mask.resize((S, S), Image.LANCZOS))
    seam = Image.new("RGBA", (S * ss, S * ss))
    ImageDraw.Draw(seam).line([(S * ss * 0.58, 0), (S * ss * 0.42, S * ss)], fill=(255, 255, 255, 255),
                              width=int(14 * u * ss))
    im.alpha_composite(seam.resize((S, S), Image.LANCZOS))
    # subtle diagonal stripes + centre glow for depth
    stripes = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(stripes)
    for x in range(-S, S, int(70 * u)):
        d.line((x, S, x + S, 0), fill=(255, 255, 255, 10), width=int(26 * u))
    im.alpha_composite(stripes)
    im.alpha_composite(radial_glow(S, S, S / 2, S * 0.42, S * 0.5, (255, 255, 230), 0.45))

    # big yellow badge with the Q
    cx, cy = S / 2, S * 0.415
    bd = int(560 * u)
    paste_center(im, soft_circle(bd, (0, 0, 0, 160), 22 * u), cx + 10 * u, cy + 26 * u)
    paste_center(im, circle(bd + int(56 * u), NAVY + (255,)), cx, cy)
    paste_center(im, circle(bd, YELLOW + (255,)), cx, cy)
    hl = Image.new("RGBA", (bd, bd))  # glossy highlight on the top half
    ImageDraw.Draw(hl).ellipse((bd * 0.12, bd * 0.05, bd * 0.88, bd * 0.55), fill=(255, 255, 255, 60))
    hl = hl.filter(ImageFilter.GaussianBlur(14 * u))
    m = circle(bd, (255, 255, 255, 255)).getchannel("A")
    hl.putalpha(ImageChops.darker(hl.getchannel("A"), m))  # keep highlight inside the badge
    paste_center(im, hl, cx, cy)
    q = outlined_text("Q", font("Black", int(430 * u)), NAVY, 0, NAVY, int(6 * u), int(4 * u))
    paste_center(im, q, cx + 4 * u, cy - 12 * u)
    # small question-mark tag on the badge, the channel's signature
    tag_d = int(170 * u)
    tx, ty = cx + bd * 0.38, cy + bd * 0.33
    paste_center(im, soft_circle(tag_d, (0, 0, 0, 140), 10 * u), tx + 6 * u, ty + 12 * u)
    paste_center(im, circle(tag_d + int(26 * u), (255, 255, 255, 255)), tx, ty)
    paste_center(im, circle(tag_d, RED_BOT + (255,)), tx, ty)
    qm = outlined_text("?", font("Black", int(140 * u)), (255, 255, 255), 0, (255, 255, 255), 0, 1)
    paste_center(im, qm, tx, ty - 4 * u)

    # sparkles
    for x, y, s, col in ((0.20, 0.25, 110, (255, 255, 255, 235)), (0.80, 0.22, 80, YELLOW + (255,)),
                         (0.17, 0.52, 60, YELLOW + (255,)), (0.84, 0.47, 120, (255, 255, 255, 235))):
        paste_center(im, sparkle(int(s * u), col), S * x, S * y)

    # channel name, sized to fit inside the circle crop
    y_name = S * 0.80
    half_w = math.sqrt((S / 2) ** 2 - (y_name - S / 2) ** 2) * 0.86
    size = int(190 * u)
    while font("Black", size).getlength(a.name) + 40 * u > 2 * half_w:
        size -= 4
    name = outlined_text(a.name, font("Black", size), (255, 255, 255), int(16 * u), NAVY, int(12 * u), int(8 * u))
    paste_center(im, name, S / 2, y_name)

    im.convert("RGB").save(a.out, optimize=True)
    print(a.out, f"{os.path.getsize(a.out) / 1024:.0f} KB")

    # how it looks on YouTube: circle crop at large, medium and comment-icon sizes
    os.makedirs(os.path.join(HERE, ".cache"), exist_ok=True)
    big = 700
    small = im.resize((big, big), Image.LANCZOS)
    cm = circle(big, (255, 255, 255, 255)).getchannel("A")
    disc = Image.new("RGBA", (big, big))
    disc.paste(small, (0, 0), cm)
    sheet = Image.new("RGBA", (1000, big), (255, 255, 255, 255))
    sheet.alpha_composite(disc)
    sheet.alpha_composite(disc.resize((176, 176), Image.LANCZOS), (770, 80))
    sheet.alpha_composite(disc.resize((48, 48), Image.LANCZOS), (834, 360))
    sheet.convert("RGB").save(os.path.join(HERE, ".cache", "profile_check.png"))


if __name__ == "__main__":
    main()
