"""Channel branding: the one place for the channel's name and logo.

Every generator takes the name and the logo from here, so a rebrand is a one-file change.
The logo is the FUNNY QUIZZ popcorn badge (make_funny_quizz_logo.py -> funny_quizz_logo.png).
"""

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))

NAME = "FUNNY QUIZZ"          # on screen
SPOKEN = "Funny Quizz"        # for the narrator and the descriptions
HASHTAG = "#funnyquizz"
LOGO = os.path.join(HERE, "funny_quizz_logo.png")
_ROUND = os.path.join(HERE, ".cache", "brand", "logo_round.png")


def round_logo():
    """Path to the badge cropped to its ring (a square image the circle fills), for round avatars."""
    if os.path.exists(_ROUND) and os.path.getmtime(_ROUND) >= os.path.getmtime(LOGO):
        return _ROUND
    im = Image.open(LOGO).convert("RGBA")
    m = round(im.width * 0.029)                        # the ring's outer edge is 2.8% in from each side
    im = im.crop((m, m, im.width - m, im.height - m))
    s = im.width
    mask = Image.new("L", (s * 2, s * 2), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, s * 2 - 1, s * 2 - 1), fill=255)
    im.putalpha(mask.resize((s, s), Image.LANCZOS))
    os.makedirs(os.path.dirname(_ROUND), exist_ok=True)
    im.save(_ROUND)
    return _ROUND
