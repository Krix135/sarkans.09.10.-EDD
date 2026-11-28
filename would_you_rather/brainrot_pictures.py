"""Emoji-fusion pictures of famous Italian brainrot characters (original compositions).

Built from Google's Noto 3D emoji (Apache 2.0) in brainrot_art/.
Each entry: list of (emoji file, size, dx, dy, rotation, mirror) drawn back to front.
"""

import os

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "brainrot_art")

PICTURES = {
    "tralalero": [("shark", 560, 0, -60, -12, False), ("sneaker", 230, -150, 230, 8, False),
                  ("sneaker", 230, 120, 250, -6, False)],
    "bombardiro": [("plane", 600, 0, 0, 0, False), ("croc", 330, 110, -70, -20, False)],
    "tungtung": [("bat", 420, 190, 40, 25, False), ("log", 600, -60, 10, 0, False),
                 ("eyes", 170, -60, -110, 0, False)],
    "ballerina": [("ballet", 400, 0, 170, 0, False), ("coffee", 360, 0, -150, 0, False)],
    "chimpanzini": [("banana", 600, 0, 40, 0, False), ("monkeyface", 240, 20, -60, 0, False)],
    "lirili": [("sandal", 190, -110, 280, 0, False), ("sandal", 190, 110, 280, 0, True),
               ("cactus", 520, 0, 60, 0, False), ("elephant", 320, 0, -200, 0, False)],
    "patapim": [("foot", 220, -130, 270, 0, True), ("foot", 220, 130, 270, 0, False),
                ("tree", 580, 0, -40, 0, False), ("monkeyface", 230, 0, -30, 0, False)],
    "cappuccino": [("dagger", 330, -170, -110, -35, False), ("dagger", 330, 170, -110, 35, True),
                   ("coffee", 460, 0, 50, 0, False)],
    "trippi": [("shrimp", 540, 20, 70, 0, False), ("cat", 270, -130, -130, -10, False)],
    "lavaca": [("saturn", 640, 0, 0, 0, False), ("cow", 320, 0, -30, 0, False)],
}

_cache = {}


def _emoji(name, size):
    key = (name, size)
    if key not in _cache:
        _cache[key] = Image.open(os.path.join(ART, name + ".png")).convert("RGBA").resize((size, size), Image.LANCZOS)
    return _cache[key]


def picture(key, box=760):
    """Compose one brainrot picture on a transparent box x box canvas, with soft drop shadows."""
    im = Image.new("RGBA", (box, box))
    for name, size, dx, dy, rot, mirror in PICTURES[key]:
        e = _emoji(name, size)
        if mirror:
            e = e.transpose(Image.FLIP_LEFT_RIGHT)
        if rot:
            e = e.rotate(rot, Image.BICUBIC, expand=True)
        sh = Image.new("RGBA", e.size, (0, 0, 0, 0))
        sh.putalpha(e.getchannel("A").point(lambda v: v * 0.35))
        sh = sh.filter(ImageFilter.GaussianBlur(12))
        x, y = int(box / 2 + dx - e.width / 2), int(box / 2 + dy - e.height / 2)
        im.alpha_composite(sh, (x + 10, y + 18)) if 0 <= x + 10 and 0 <= y + 18 else None
        layer = Image.new("RGBA", im.size)
        layer.paste(e, (x, y), e)
        im = Image.alpha_composite(im, layer)
    return im
