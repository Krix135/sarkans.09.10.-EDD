#!/usr/bin/env python3
"""YouTube thumbnail (1280x720) for the Would You Rather? video.

    python3 make_thumbnail.py
    python3 make_thumbnail.py --left "🦖" "MEET DINOSAURS" --right "👶" "MEET YOUR GREAT-GRANDKIDS"
"""

import argparse
import os

from PIL import Image, ImageDraw, ImageFilter

from make_video import (BLUE_BOT, BLUE_TOP, RED_BOT, RED_TOP, YELLOW, circle, emoji, font,
                        paste_center, radial_glow, soft_circle, text_img, vgradient, wrap)

TW, TH = 1280, 720
HERE = os.path.dirname(os.path.abspath(__file__))


def label(text, size, max_w):
    """Big white caption with a thick black outline, shrunk to fit."""
    while True:
        f = font("Black", size)
        lines = wrap(text, f, max_w)
        if (len(lines) <= 2 and all(f.getlength(l) <= max_w for l in lines)) or size <= 40:
            break
        size -= 4
    imgs = [text_img(l, f, stroke=9, stroke_fill=(0, 0, 0)) for l in lines]
    h = sum(i.height for i in imgs) - 40 * (len(imgs) - 1)
    out = Image.new("RGBA", (max(i.width for i in imgs), h))
    y = 0
    for i in imgs:
        out.alpha_composite(i, ((out.width - i.width) // 2, y))
        y += i.height - 40
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--left", nargs=2, default=["🧠", "READ MINDS"], metavar=("EMOJI", "TEXT"))
    ap.add_argument("--right", nargs=2, default=["🔮", "SEE THE FUTURE"], metavar=("EMOJI", "TEXT"))
    ap.add_argument("--out", default=os.path.join(HERE, "thumbnail.jpg"))
    a = ap.parse_args()

    im = Image.new("RGBA", (TW, TH))
    red = vgradient(TW, TH, RED_TOP, RED_BOT).convert("RGBA")
    blue = vgradient(TW, TH, BLUE_TOP, BLUE_BOT).convert("RGBA")
    # slanted split looks more dynamic than a straight line
    mask = Image.new("L", (TW, TH))
    ImageDraw.Draw(mask).polygon([(0, 0), (690, 0), (590, TH), (0, TH)], fill=255)
    im.alpha_composite(blue)
    im.paste(red, (0, 0), mask)
    seam = Image.new("RGBA", (TW, TH))
    ImageDraw.Draw(seam).line([(690, 0), (590, TH)], fill=(255, 255, 255, 255), width=10)
    im.alpha_composite(seam)

    # emoji with glow + drop shadow, slightly tilted toward the centre
    for (emo, _), cx, tilt in ((a.left, 310, 8), (a.right, 975, -8)):
        im.alpha_composite(radial_glow(TW, TH, cx, 370, 300, (255, 255, 200), 0.55))
        e = emoji(emo, 310)
        e.putalpha(e.getchannel("A").filter(ImageFilter.GaussianBlur(1.2)))  # smooth upscaled bitmap edges
        e = e.rotate(tilt, Image.BICUBIC, expand=True)
        sh = Image.new("RGBA", e.size, (0, 0, 0, 0))
        sh.putalpha(e.getchannel("A").point(lambda v: v * 0.5))
        paste_center(im, sh.filter(ImageFilter.GaussianBlur(12)), cx + 10, 385)
        paste_center(im, e, cx, 365)

    paste_center(im, label(a.left[1], 84, 520), 300, 615)
    paste_center(im, label(a.right[1], 84, 540), 985, 615)

    # banner
    banner = text_img("WOULD YOU RATHER?", font("Black", 96), stroke=8, stroke_fill=(0, 0, 0))
    paste_center(im, banner, TW / 2, 78)

    # OR badge
    paste_center(im, soft_circle(190, (0, 0, 0, 170), 14), 645, 395)
    paste_center(im, circle(196, (0, 0, 0, 255)), 640, 380)
    paste_center(im, circle(176, YELLOW + (255,)), 640, 380)
    paste_center(im, text_img("OR", font("Black", 92), fill=(20, 22, 45), shadow=False), 640, 382)

    # timer sticker
    st = circle(132, (255, 255, 255, 255))
    paste_center(st, circle(118, (255, 59, 48, 255)), 66, 66)
    paste_center(st, text_img("5s", font("Black", 58), shadow=False), 66, 62)
    paste_center(im, st.rotate(-12, Image.BICUBIC, expand=True), 1185, 225)

    im.convert("RGB").save(a.out, quality=92)
    print(a.out)


if __name__ == "__main__":
    main()
