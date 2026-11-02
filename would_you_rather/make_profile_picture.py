#!/usr/bin/env python3
"""YouTube channel profile picture (800x800). YouTube crops it to a circle."""

import os

from PIL import Image, ImageDraw

from make_video import (BLUE_BOT, BLUE_TOP, RED_BOT, RED_TOP, YELLOW, circle, font, paste_center,
                        soft_circle, text_img, vgradient)

S = 800
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    im = vgradient(S, S, BLUE_TOP, BLUE_BOT).convert("RGBA")
    red = vgradient(S, S, RED_TOP, RED_BOT).convert("RGBA")
    mask = Image.new("L", (S, S))
    ImageDraw.Draw(mask).polygon([(0, 0), (S * 0.56, 0), (S * 0.44, S), (0, S)], fill=255)
    im.paste(red, (0, 0), mask)
    seam = Image.new("RGBA", (S * 2, S * 2))
    ImageDraw.Draw(seam).line([(S * 1.12, 0), (S * 0.88, S * 2)], fill=(255, 255, 255, 255), width=24)
    im.alpha_composite(seam.resize((S, S), Image.LANCZOS))

    # A / B letters sit inside the circle crop
    for ch, x in (("A", 158), ("B", 645)):
        paste_center(im, text_img(ch, font("Black", 200), stroke=10, stroke_fill=(0, 0, 0)), x, 400)

    # central "?" badge, the channel's signature
    paste_center(im, soft_circle(220, (0, 0, 0, 170), 16), S / 2 + 8, S / 2 + 14)
    paste_center(im, circle(236, (0, 0, 0, 255)), S / 2, S / 2)
    paste_center(im, circle(208, YELLOW + (255,)), S / 2, S / 2)
    paste_center(im, text_img("?", font("Black", 190), fill=(20, 22, 45), shadow=False), S / 2, S / 2 + 4)

    out = os.path.join(HERE, "profile_picture.png")
    im.convert("RGB").save(out)
    # preview of how YouTube shows it (circle crop, small size)
    prev = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    m = Image.new("L", (S * 4, S * 4))
    ImageDraw.Draw(m).ellipse((0, 0, S * 4 - 1, S * 4 - 1), fill=255)
    prev.paste(im, (0, 0), m.resize((S, S), Image.LANCZOS))
    prev.save(os.path.join(HERE, ".cache", "profile_preview.png"))
    print(out)


if __name__ == "__main__":
    main()
