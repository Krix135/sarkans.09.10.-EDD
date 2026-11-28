#!/usr/bin/env python3
""""99% OF MINECRAFT PLAYERS CAN'T GET 10/10!" - vertical quiz Short (1080x1920, ~58 s).

Everything is original and generated here: blocky 3D worlds (plains, snowy
taiga, desert, cave, Nether, End) rendered from procedural pixel textures,
pixel-art icons, chiptune music and sound effects. Narration uses the Kokoro
TTS engine from make_video.py. Fan-made; not affiliated with Mojang/Microsoft.

    python3 make_minecraft_quiz.py               # render the Short
    python3 make_minecraft_quiz.py --stills 1,8  # preview frames
    python3 make_minecraft_quiz.py --cover       # Shorts cover image
"""

import argparse
import math
import multiprocessing as mp
import os
import random
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

import make_video as mv  # noqa: E402
from make_video import (SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, font, highpass,  # noqa: E402
                        lowpass, midi, paste_center, radial_glow, rounded_card, scaled, sfx_whoosh, text_img, tt)

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
PIXFONT = os.path.join(HERE, "models", "PressStart2P-Regular.ttf")
PIXFONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/pressstart2p/PressStart2P-Regular.ttf"
YELLOW = (255, 222, 40)
DIFF = {"EASY": (90, 220, 90), "NORMAL": (70, 160, 255), "MEDIUM": (255, 165, 30), "HARD": (255, 60, 60)}

T_IN, COUNTDOWN, T_HOLD = 0.22, 4.0, 0.95
FRAME_Y, ANSWER_Y, BAR_Y, HOTBAR_Y = 960, 1215, 1215, 1440

# ----------------------------------------------------------------------------
# questions (wording checked for accuracy; answers as requested)
# ----------------------------------------------------------------------------
QUESTIONS = [
    # text (*word* = highlighted), answer, spoken answer, level, scene, icon, camera start/end, extra
    dict(q="Which mob *EXPLODES* when it gets close to you?", a="CREEPER", say="Creeper!", level="EASY",
         scene="plains", icon="creeper", cam=((1900, 1560, 1.15), (2160, 1460, 1.05)), fx="explode", col=(90, 200, 70)),
    dict(q="What block do you need to build a *Nether Portal*?", a="OBSIDIAN", say="Obsidian!", level="EASY",
         scene="cave", icon="obsidian", cam=((2220, 1520, 1.25), (1960, 1590, 1.1)), col=(140, 80, 220)),
    dict(q="Which mob gives you *wool*?", a="SHEEP", say="Sheep!", level="EASY",
         scene="snowy", icon="sheep", cam=((1960, 1400, 1.05), (2060, 1560, 1.22)), col=(240, 240, 240)),
    dict(q="Which dimension has *floating islands* and *Chorus Plants*?", a="THE END", say="The End!",
         level="NORMAL", scene="night", reveal_scene="end", icon="end_island",
         cam=((2120, 1500, 1.1), (1960, 1450, 1.02)), col=(230, 230, 150)),
    dict(q="What do you need to activate an *End Portal*?", a="EYES OF ENDER", say="Eyes of Ender!",
         level="NORMAL", scene="desert", icon="eye", cam=((1850, 1500, 1.2), (2220, 1500, 1.2)), col=(60, 200, 150)),
    dict(q="Which block do you smelt to get *Netherite Scrap*?", a="ANCIENT DEBRIS", say="Ancient Debris!",
         level="NORMAL", scene="nether", icon="debris", cam=((2050, 1660, 1.3), (2050, 1420, 1.06)), col=(150, 100, 80)),
    dict(q="Which mob *teleports* and gets hurt by *water*?", a="ENDERMAN", say="Enderman!", level="MEDIUM",
         scene="night2", icon="enderman", cam=((2300, 1600, 1.15), (2000, 1500, 1.25)), col=(200, 60, 255)),
    dict(q="What happens if you try to *sleep* in the *Nether*?", a="THE BED EXPLODES!", say="Your bed explodes!",
         level="MEDIUM", scene="nether", icon="bed", cam=("portal", 1.22, 1.08), fx="explode", col=(230, 40, 40)),
    dict(q="Which Minecraft mob turns into a *Drowned* when it stays *underwater* long enough?", a="ZOMBIE",
         say="Zombie!", level="HARD", scene="ocean", icon="zombie", cam=((1980, 1480, 1.1), (2160, 1560, 1.22)),
         col=(90, 180, 90), time=7),
    dict(q="What is one of the *RAREST* structures in Minecraft, found only in *Dark Forests*?",
         a="WOODLAND MANSION", say="The Woodland Mansion!", level="HARD", scene="darkforest", icon="mansion",
         cam=((2120, 1620, 1.25), (1960, 1460, 1.05)), col=(240, 200, 120), time=7),
]
INTRO_CAM = ((2048, 1500, 1.65), (2048, 1450, 1.05))


# ----------------------------------------------------------------------------
# fonts / text
# ----------------------------------------------------------------------------

def ensure_pixfont():
    if not os.path.exists(PIXFONT):
        os.makedirs(os.path.dirname(PIXFONT), exist_ok=True)
        urllib.request.urlretrieve(PIXFONT_URL, PIXFONT)


_pf = {}


def pixfont(size):
    if size not in _pf:
        _pf[size] = ImageFont.truetype(PIXFONT, size)
    return _pf[size]


def ptext(text, size, fill=(255, 255, 255), shadow=True, stroke=None):
    """Pixel-font text with a hard drop shadow and outline (game-UI look)."""
    f = pixfont(size)
    st = stroke if stroke is not None else max(2, size // 10)
    l, t, r, b = f.getbbox(text, stroke_width=st)
    off = max(3, size // 8)
    im = Image.new("RGBA", (r - l + off + 4, b - t + off + 4))
    d = ImageDraw.Draw(im)
    if shadow:
        d.text((2 - l + off, 2 - t + off), text, font=f, fill=(0, 0, 0, 200), stroke_width=st,
               stroke_fill=(0, 0, 0, 200))
    d.text((2 - l, 2 - t), text, font=f, fill=fill, stroke_width=st, stroke_fill=(0, 0, 0))
    return im


def bold(text, size, fill=(255, 255, 255), stroke=9, max_w=None):
    while max_w and font("Black", size).getlength(text) + 2 * stroke > max_w and size > 30:
        size -= 2
    return text_img(text, font("Black", size), fill=fill, stroke=stroke, stroke_fill=(0, 0, 0))


def rich_block(text, size, max_w, base=(255, 255, 255), hi=YELLOW, stroke=8, line_gap=1.12):
    """Multi-line bold text; words wrapped in *stars* are highlighted."""
    words = []
    hl = False
    for w in text.split():
        start = w.startswith("*")
        if start:
            hl = True
        clean = w.replace("*", "")
        words.append((clean, hl))
        if w.endswith("*") or w.endswith("*?") or w.endswith("*!") or "*?" in w:
            hl = False
    def wrap(f, width):
        sp = f.getlength(" ")
        lines, cur, cw = [], [], 0
        for w, h in words:
            wl = f.getlength(w)
            if cur and cw + sp + wl > width:
                lines.append(cur)
                cur, cw = [], 0
            cw += (sp if cur else 0) + wl
            cur.append((w, h))
        lines.append(cur)
        return lines

    # prefer 2 lines if a slightly smaller size allows it, otherwise balance the line lengths
    for sz in (size, size - 4, size - 8):
        if len(wrap(font("Black", sz), max_w)) <= 2:
            size = sz
            break
    while len(wrap(font("Black", size), max_w)) > 3 and size > 54:  # long questions: shrink to fit 3 lines
        size -= 2
    f = font("Black", size)
    sp = f.getlength(" ")
    n = len(wrap(f, max_w))
    lo_w, hi_w = max(f.getlength(w) for w, _ in words), max_w
    for _ in range(14):
        mid = (lo_w + hi_w) / 2
        if len(wrap(f, mid)) <= n:
            hi_w = mid
        else:
            lo_w = mid
    lines = wrap(f, hi_w)
    lh = int(size * line_gap)
    pad = stroke + 12
    im = Image.new("RGBA", (int(max_w) + 2 * pad, lh * len(lines) + 2 * pad))
    shadow = Image.new("RGBA", im.size)
    d, ds = ImageDraw.Draw(im), ImageDraw.Draw(shadow)
    for i, ln in enumerate(lines):
        total = sum(f.getlength(w) for w, _ in ln) + sp * (len(ln) - 1)
        x = pad + (max_w - total) / 2
        y = pad + i * lh
        for w, h in ln:
            ds.text((x + 4, y + 7), w, font=f, fill=(0, 0, 0, 170), stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
            d.text((x, y), w, font=f, fill=hi if h else base, stroke_width=stroke, stroke_fill=(0, 0, 0))
            x += f.getlength(w) + sp
    out = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(4)), im)
    return out.crop(out.getbbox())


# ----------------------------------------------------------------------------
# procedural 16x16 pixel textures (original)
# ----------------------------------------------------------------------------

def _pal(r, pal, shape=(16, 16), p=None):
    return np.array(pal, np.uint8)[r.choice(len(pal), size=shape, p=p)]


def make_textures():
    r = np.random.default_rng(7)
    T = {}

    def put(name, arr):
        T[name] = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")

    grass = [(95, 159, 53), (108, 173, 61), (86, 145, 48), (121, 186, 70)]
    dirt = [(134, 96, 67), (121, 85, 58), (150, 108, 75), (104, 74, 50)]
    stone = [(125, 125, 125), (115, 115, 115), (136, 136, 136), (104, 104, 104)]
    sand = [(219, 207, 163), (210, 197, 150), (226, 216, 176), (200, 186, 138)]
    snow = [(240, 246, 250), (228, 236, 244), (250, 252, 255), (218, 228, 240)]

    def topped(base, top, rows):
        a = _pal(r, base)
        b = _pal(r, top)
        a[:rows] = b[:rows]
        drip = r.integers(0, 3, 16)
        for x in range(16):
            a[rows:rows + drip[x], x] = b[rows:rows + drip[x], x]
        return a

    put("grass_top", _pal(r, grass))
    put("grass_side", topped(dirt, grass, 2))
    put("dirt", _pal(r, dirt))
    put("stone", _pal(r, stone, p=[.35, .3, .2, .15]))
    put("sand", _pal(r, sand))
    ss = _pal(r, sand)
    ss[0:2] = np.array((236, 226, 186))
    ss[13:16] = np.array((196, 180, 130))
    ss[6] = np.array((205, 190, 142))
    put("sandstone", ss)
    put("snow", _pal(r, snow))
    put("snow_side", topped(dirt, snow, 3))
    put("gravel", _pal(r, [(130, 124, 122), (100, 96, 94), (150, 146, 140), (84, 80, 80)]))

    def log_side(c):
        a = np.zeros((16, 16, 3))
        for x in range(16):
            a[:, x] = c[x % 3]
        a += r.integers(-8, 8, (16, 16, 1))
        return np.clip(a, 0, 255)

    def log_top(bark, rings):
        a = np.zeros((16, 16, 3))
        for y in range(16):
            for x in range(16):
                ring = max(abs(x - 7.5), abs(y - 7.5))
                a[y, x] = bark if ring > 6.5 else rings[int(ring) % 2]
        return a

    put("log_side", log_side([(102, 79, 47), (85, 65, 38), (117, 90, 54)]))
    put("log_top", log_top((95, 72, 42), [(182, 145, 90), (150, 115, 70)]))
    put("spruce_side", log_side([(70, 50, 30), (58, 41, 24), (82, 60, 36)]))
    put("spruce_top", log_top((60, 44, 26), [(130, 96, 58), (105, 76, 45)]))
    put("leaves", _pal(r, [(55, 120, 40), (45, 100, 32), (70, 140, 50), (30, 75, 22)], p=[.35, .3, .2, .15]))
    put("spruce_leaves", _pal(r, [(40, 80, 50), (30, 65, 40), (52, 96, 62), (22, 50, 30)]))
    sl = _pal(r, [(40, 80, 50), (30, 65, 40)])
    sl[:5] = _pal(r, snow)[:5]
    put("snowy_leaves_side", sl)
    put("water", _pal(r, [(52, 95, 200), (45, 85, 190), (62, 110, 215), (80, 130, 225)], p=[.35, .35, .2, .1]))
    put("ice", _pal(r, [(160, 200, 250), (140, 185, 245), (175, 215, 255)]))
    put("lava", _pal(r, [(230, 90, 20), (250, 140, 30), (255, 190, 60), (200, 60, 10)]))
    ob = _pal(r, [(20, 12, 30), (30, 18, 45), (14, 8, 22), (45, 28, 70)], p=[.35, .3, .25, .1])
    for _ in range(6):
        y, x = r.integers(0, 16, 2)
        ob[y, x] = (90, 60, 140)
    put("obsidian", ob)
    put("netherrack", _pal(r, [(110, 40, 40), (95, 32, 32), (128, 52, 50), (80, 25, 28)]))
    put("glowstone", _pal(r, [(250, 210, 110), (220, 170, 80), (255, 235, 160), (180, 130, 60)]))
    put("soul_sand", _pal(r, [(85, 64, 50), (72, 54, 42), (98, 75, 58), (60, 44, 34)]))
    es = _pal(r, [(220, 222, 160), (206, 208, 146), (232, 234, 178)])
    for _ in range(10):
        y, x = r.integers(0, 16, 2)
        es[y, x] = (175, 175, 115)
    put("end_stone", es)
    portal = np.zeros((16, 16, 3))
    for y in range(16):
        for x in range(16):
            v = 0.5 + 0.5 * math.sin(x * 0.9 + math.sin(y * 0.7) * 2)
            portal[y, x] = (90 + 80 * v, 20 + 40 * v, 170 + 70 * v)
    put("portal", portal)
    cac = _pal(r, [(80, 140, 50), (70, 128, 44)])
    cac[:, [0, 15]] = (40, 90, 30)
    cac[:, [4, 11]] = (55, 110, 38)
    cac[::4, [2, 7, 13]] = (210, 220, 170)
    put("cactus", cac)
    put("cactus_top", _pal(r, [(95, 160, 60), (80, 140, 50)]))

    def ore(colors, n=5):
        a = _pal(r, stone, p=[.35, .3, .2, .15]).astype(int)
        for _ in range(n):
            cy, cx = r.integers(2, 14, 2)
            for dy, dx in ((0, 0), (0, 1), (1, 0), (1, 1), (-1, 0)):
                if r.random() < 0.85:
                    a[cy + dy, cx + dx] = colors[r.integers(0, len(colors))]
        return a

    put("coal", ore([(30, 30, 30), (55, 55, 55)]))
    put("iron", ore([(216, 175, 147), (190, 150, 120)]))
    put("gold", ore([(250, 220, 70), (220, 180, 40)]))
    put("diamond", ore([(90, 230, 225), (40, 190, 190)]))
    put("redstone", ore([(220, 20, 20), (170, 10, 10)]))
    deb = np.zeros((16, 16, 3))
    for y in range(16):
        for x in range(16):
            d = math.hypot(x - 7.5, y - 9)
            deb[y, x] = (62, 44, 40) if int(d * 1.3) % 3 == 0 else (104, 76, 66) if (x + y) % 3 else (92, 66, 58)
    put("debris_side", deb)
    put("dark_oak_side", log_side([(66, 43, 20), (54, 35, 16), (76, 52, 26)]))
    put("dark_oak_top", log_top((50, 32, 14), [(96, 66, 34), (78, 52, 26)]))
    put("dark_leaves", _pal(r, [(40, 90, 30), (30, 72, 22), (52, 108, 40), (22, 58, 16)]))

    def planks(pal, seam):
        a = _pal(r, pal)
        a[[3, 7, 11, 15]] = seam
        for row, x in ((1, 9), (5, 3), (9, 12), (13, 6)):
            a[row - 1:row + 3, x] = seam
        return a

    put("planks", planks([(216, 201, 150), (204, 189, 138), (226, 212, 162)], (168, 152, 106)))
    put("roof", planks([(72, 47, 23), (60, 39, 19), (84, 56, 29)], (40, 26, 12)))
    gl = np.full((16, 16, 3), (165, 205, 235))
    gl[[0, 15]] = (235, 242, 250)
    gl[:, [0, 15]] = (235, 242, 250)
    for k in range(3, 8):
        gl[k, k + 2] = (235, 245, 255)
    put("glass", gl)
    put("debris_top", log_top((80, 58, 52), [(120, 92, 80), (70, 50, 44)]))
    return T


# block id -> (top texture, side texture, emissive)
BLOCKS = {
    1: ("grass_top", "grass_side", False), 2: ("dirt", "dirt", False), 3: ("stone", "stone", False),
    4: ("sand", "sand", False), 5: ("sand", "sandstone", False), 6: ("snow", "snow_side", False),
    7: ("log_top", "log_side", False), 8: ("leaves", "leaves", False), 9: ("spruce_top", "spruce_side", False),
    10: ("spruce_leaves", "spruce_leaves", False), 11: ("water", "water", False), 12: ("lava", "lava", True),
    13: ("obsidian", "obsidian", False), 14: ("netherrack", "netherrack", False),
    15: ("glowstone", "glowstone", True), 16: ("soul_sand", "soul_sand", False), 17: ("end_stone", "end_stone", False),
    18: ("coal", "coal", False), 19: ("iron", "iron", False), 20: ("gold", "gold", False),
    21: ("diamond", "diamond", False), 22: ("redstone", "redstone", False), 23: ("debris_top", "debris_side", False),
    24: ("cactus_top", "cactus", False), 25: ("ice", "ice", False), 26: ("portal", "portal", True),
    27: ("snow", "snowy_leaves_side", False), 28: ("gravel", "gravel", False),
    29: ("dark_oak_top", "dark_oak_side", False), 30: ("dark_leaves", "dark_leaves", False),
    31: ("planks", "planks", False), 32: ("glass", "glass", False), 33: ("roof", "roof", False),
}
(GRASS, DIRT, STONE, SAND, SANDSTONE, SNOW, LOG, LEAVES, SPRUCE, SPRUCE_LEAVES, WATER, LAVA, OBSIDIAN,
 NETHERRACK, GLOWSTONE, SOUL_SAND, END_STONE, COAL, IRON, GOLD, DIAMOND, REDSTONE, DEBRIS, CACTUS, ICE, PORTAL,
 SNOWY_LEAVES, GRAVEL, DARK_OAK, DARK_LEAVES, PLANKS, GLASS, ROOF) = range(1, 34)

# ----------------------------------------------------------------------------
# isometric voxel renderer
# ----------------------------------------------------------------------------
U, HS = 32, 36                 # half tile width, side height
SPR_W, SPR_H = 2 * U, U + HS
HEX = [(32, 0), (64, 16), (64, 52), (32, 68), (0, 52), (0, 16)]
AFF_TOP = (0.25, -0.5, 8, 0.25, 0.5, -8)
AFF_LEFT = (0.5, 0, 0, -0.5 / 2.25, 1 / 2.25, -16 / 2.25)
AFF_RIGHT = (0.5, 0, -16, 0.5 / 2.25, 1 / 2.25, -48 / 2.25)


def _face(tex, aff, shade, tint, fog, fog_col):
    f = tex.transform((SPR_W, SPR_H), Image.AFFINE, aff, resample=Image.NEAREST, fillcolor=(0, 0, 0, 0))
    a = np.asarray(f).astype(np.float32)
    rgb = a[..., :3] * shade * np.array(tint)
    rgb = rgb * (1 - fog) + np.array(fog_col) * fog
    a[..., :3] = np.clip(rgb, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


class SpriteCache:
    def __init__(self, tex, ambient=(1, 1, 1), fog_col=(200, 220, 255)):
        self.tex, self.ambient, self.fog_col, self.c = tex, ambient, fog_col, {}

    def get(self, bid, fog_level):
        key = (bid, fog_level)
        if key not in self.c:
            top, side, emissive = BLOCKS[bid]
            fog = fog_level / 10
            amb = (1, 1, 1) if emissive else self.ambient
            sh = (1.0, 0.95, 0.88) if emissive else (1.0, 0.8, 0.62)
            spr = Image.new("RGBA", (SPR_W, SPR_H))
            ImageDraw.Draw(spr).polygon(HEX, fill=tuple(int(v * 0.35) for v in self.fog_col) + (255,))
            for t, aff, s in ((top, AFF_TOP, sh[0]), (side, AFF_LEFT, sh[1]), (side, AFF_RIGHT, sh[2])):
                spr.alpha_composite(_face(self.tex[t], aff, s, amb, fog, self.fog_col))
            self.c[key] = spr
        return self.c[key]


def render_voxels(vox, cache, fog_strength=0.35, glow=None):
    X, Y, Z = vox.shape
    cw, ch = (X + Y) * U, (X + Y) * U // 2 + Z * HS + SPR_H
    X0, Y0 = Y * U, Z * HS
    canvas = Image.new("RGBA", (cw, ch))
    solid = vox > 0
    pad = np.zeros((X + 1, Y + 1, Z + 1), bool)
    pad[:X, :Y, :Z] = solid
    exposed = solid & (~pad[:X, :Y, 1:] | ~pad[1:, :Y, :Z] | ~pad[:X, 1:, :Z])
    xs, ys, zs = np.nonzero(exposed)
    order = np.lexsort((zs, xs + ys))
    glows = []
    for i in order:
        x, y, z = int(xs[i]), int(ys[i]), int(zs[i])
        bid = int(vox[x, y, z])
        d = (x + y) / (X + Y)
        lvl = int(round(10 * fog_strength * (1 - d) ** 1.6))
        sx = (x - y) * U + X0 - U
        sy = (x + y) * U // 2 - z * HS + Y0
        canvas.alpha_composite(cache.get(bid, lvl), (sx, sy))
        if glow and bid in glow and not pad[x, y, z + 1]:
            glows.append((sx + U, sy + U // 2, glow[bid]))
    if glows:
        gl = Image.new("RGBA", canvas.size)
        spr = {}
        for gx, gy, (col, rad, strength) in glows[::2]:
            k = (col, rad, strength)
            if k not in spr:
                spr[k] = radial_glow(rad * 2, rad * 2, rad, rad, rad, col, strength)
            gl.alpha_composite(spr[k], (int(gx - rad), int(gy - rad)))
        canvas = Image.alpha_composite(canvas, gl)
    return canvas, (X0, Y0)


def iso_xy(x, y, z, origin):
    X0, Y0 = origin
    return (x - y) * U + X0, (x + y) * U / 2 - z * HS + Y0 + U / 2


# ----------------------------------------------------------------------------
# world generation
# ----------------------------------------------------------------------------
N, ZMAX = 64, 26


def fbm(seed, cells=(14, 7, 3.5), weights=(0.6, 0.3, 0.1)):
    rng = np.random.default_rng(seed)
    out = np.zeros((N, N))
    for c, w in zip(cells, weights):
        g = int(N / c) + 3
        img = Image.fromarray((rng.random((g, g)) * 255).astype(np.uint8)).resize(
            (int(g * c), int(g * c)), Image.BICUBIC)
        out += w * np.asarray(img, np.float32)[:N, :N] / 255
    return (out - out.min()) / (out.max() - out.min() + 1e-9)


def column(vox, x, y, h, top, mid, low=STONE, mid_depth=3):
    vox[x, y, :max(h - mid_depth, 0)] = low
    vox[x, y, max(h - mid_depth, 0):h] = mid
    vox[x, y, h] = top


def tree(vox, x, y, z, rng):
    th = int(rng.integers(4, 6))
    vox[x, y, z + 1:z + 1 + th] = LOG
    top = z + th
    for dz, rad in ((-1, 2), (0, 2), (1, 1), (2, 1)):
        for dx in range(-rad, rad + 1):
            for dy in range(-rad, rad + 1):
                if rad == 2 and abs(dx) == 2 and abs(dy) == 2:
                    continue
                if dz == 2 and abs(dx) + abs(dy) > 1:
                    continue
                if vox[x + dx, y + dy, top + dz] == 0:
                    vox[x + dx, y + dy, top + dz] = LEAVES


def spruce(vox, x, y, z, rng):
    th = int(rng.integers(6, 8))
    vox[x, y, z + 1:z + 1 + th] = SPRUCE
    rads = [2, 1, 2, 1, 1, 0]
    for i, rad in enumerate(rads):
        zz = z + 2 + i
        for dx in range(-rad, rad + 1):
            for dy in range(-rad, rad + 1):
                if rad == 2 and abs(dx) == 2 and abs(dy) == 2:
                    continue
                if vox[x + dx, y + dy, zz] == 0:
                    vox[x + dx, y + dy, zz] = SNOWY_LEAVES if (i == len(rads) - 1 or rads[min(i + 1, 5)] < rad) \
                        else SPRUCE_LEAVES
    vox[x, y, z + 2 + len(rads)] = SNOWY_LEAVES


def gen_overworld(seed, biome):
    rng = np.random.default_rng(seed)
    vox = np.zeros((N, N, ZMAX), np.uint8)
    hm = (5 + fbm(seed) * (10 if biome != "desert" else 7)).astype(int)
    wl = 7
    for x in range(N):
        for y in range(N):
            h = hm[x, y]
            if biome == "desert":
                column(vox, x, y, h, SAND, SAND, SANDSTONE, 2)
            elif biome == "snowy":
                column(vox, x, y, h, SNOW if h > wl else GRAVEL, DIRT)
                if h < wl:
                    vox[x, y, h + 1:wl] = WATER
                    vox[x, y, wl] = ICE
            else:
                top = SAND if h <= wl + 1 and h >= wl - 1 else GRASS if h > wl else DIRT
                column(vox, x, y, h, top, DIRT)
                if h < wl:
                    vox[x, y, h + 1:wl + 1] = WATER
    for _ in range(140):
        x, y = rng.integers(3, N - 3, 2)
        h = hm[x, y]
        if h <= wl + 1 or vox[x, y, h + 1] != 0:
            continue
        if biome == "plains" and rng.random() < 0.28:
            tree(vox, x, y, h, rng)
        elif biome == "snowy" and rng.random() < 0.6:
            spruce(vox, x, y, h, rng)
        elif biome == "desert" and rng.random() < 0.22:
            vox[x, y, h + 1:h + 1 + int(rng.integers(2, 4))] = CACTUS
    return vox


def gen_ocean(seed):
    rng = np.random.default_rng(seed)
    vox = np.zeros((N, N, ZMAX), np.uint8)
    hm = (2 + fbm(seed, (16, 8, 4)) * 10).astype(int)
    wl = 8
    for x in range(N):
        for y in range(N):
            h = hm[x, y]
            column(vox, x, y, h, SAND if h <= wl + 1 else GRASS, SAND if h <= wl + 1 else DIRT)
            if h < wl:
                vox[x, y, h + 1:wl + 1] = WATER
    for _ in range(40):
        x, y = rng.integers(3, N - 3, 2)
        h = hm[x, y]
        if h > wl + 1 and vox[x, y, h + 1] == 0 and rng.random() < 0.5:
            tree(vox, x, y, h, rng)
    return vox


def gen_dark_forest(seed):
    rng = np.random.default_rng(seed)
    vox = np.zeros((N, N, ZMAX), np.uint8)
    hm = (6 + fbm(seed) * 6).astype(int)
    for x in range(N):
        for y in range(N):
            column(vox, x, y, hm[x, y], GRASS, DIRT)
    for _ in range(170):
        x, y = rng.integers(4, N - 5, 2)
        z = int(max(hm[x, y], hm[x + 1, y], hm[x, y + 1], hm[x + 1, y + 1]))
        if vox[x, y, z + 1] != 0 or vox[x, y, z + 3] != 0:
            continue
        th = int(rng.integers(5, 8))
        vox[x:x + 2, y:y + 2, z + 1:z + 1 + th] = DARK_OAK  # 2x2 dark oak trunk
        top = z + th
        for dz, rad in ((-1, 3), (0, 3), (1, 2)):
            for dx in range(-rad, rad + 2):
                for dy in range(-rad, rad + 2):
                    if abs(dx - 0.5) + abs(dy - 0.5) > rad + 1.2:
                        continue
                    if vox[x + dx, y + dy, top + dz] == 0:
                        vox[x + dx, y + dy, top + dz] = DARK_LEAVES
    return vox


def gen_cave(seed):
    rng = np.random.default_rng(seed)
    vox = np.zeros((N, N, ZMAX), np.uint8)
    hm = (3 + fbm(seed, (10, 5, 2.5)) * 8).astype(int)
    pil = fbm(seed + 1, (6, 3, 1.5))
    for x in range(N):
        for y in range(N):
            h = hm[x, y] + (int(6 + 6 * pil[x, y]) if pil[x, y] > 0.82 else 0)
            vox[x, y, :h + 1] = STONE
            if hm[x, y] <= 4:
                vox[x, y, hm[x, y] + 1:6] = LAVA
    ores = [COAL] * 8 + [IRON] * 6 + [GOLD] * 2 + [REDSTONE] * 3 + [DIAMOND] * 2
    stone = np.argwhere(vox == STONE)
    for i in rng.choice(len(stone), int(len(stone) * 0.05), replace=False):
        x, y, z = stone[i]
        vox[x, y, z] = ores[rng.integers(0, len(ores))]
    for x, y in rng.integers(2, N - 2, (60, 2)):
        z = int(np.max(np.nonzero(vox[x, y])[0]))
        if vox[x, y, z] == STONE:
            vox[x, y, z] = GRAVEL
    return vox


def gen_nether(seed):
    rng = np.random.default_rng(seed)
    vox = np.zeros((N, N, ZMAX), np.uint8)
    hm = (4 + fbm(seed, (12, 6, 3)) * 12).astype(int)
    soul = fbm(seed + 3)
    for x in range(N):
        for y in range(N):
            h = hm[x, y]
            vox[x, y, :h + 1] = NETHERRACK
            if soul[x, y] > 0.72 and h > 7:
                vox[x, y, h] = SOUL_SAND
            if h < 7:
                vox[x, y, h + 1:8] = LAVA
    for x, y in rng.integers(2, N - 2, (70, 2)):
        h = hm[x, y]
        if h >= 8:
            vox[x, y, h + 1:h + 1 + int(rng.integers(1, 3))] = GLOWSTONE
    # obsidian portal on a flat spot
    px, py = 40, 30
    base = int(hm[px - 1:px + 5, py].max())
    vox[px - 1:px + 5, py - 1:py + 2, base - 2:base + 1] = NETHERRACK
    vox[px - 1:px + 5, py - 1:py + 2, base + 1:] = 0
    for i in range(4):
        vox[px + i, py, base + 1] = OBSIDIAN
        vox[px + i, py, base + 5] = OBSIDIAN
    for k in range(5):
        vox[px, py, base + 1 + k] = OBSIDIAN
        vox[px + 3, py, base + 1 + k] = OBSIDIAN
    vox[px + 1:px + 3, py, base + 2:base + 5] = PORTAL
    return vox, (px + 1.5, py, base + 3)


def gen_end(seed):
    rng = np.random.default_rng(seed)
    vox = np.zeros((N, N, ZMAX), np.uint8)
    hm = (6 + fbm(seed, (12, 6, 3)) * 3).astype(int)
    edge = fbm(seed + 5, (8, 4, 2))
    for x in range(N):
        for y in range(N):
            d = math.hypot(x - 32, y - 32)
            small = min(math.hypot(x - 8, y - 50), math.hypot(x - 52, y - 10), math.hypot(x - 54, y - 54))
            if d < 21 + edge[x, y] * 7:
                h = hm[x, y]
                vox[x, y, max(0, h - 4 - int(edge[x, y] * 3)):h + 1] = END_STONE
            elif small < 4 + edge[x, y] * 3:
                vox[x, y, 3:6] = END_STONE
    for k in range(7):
        a = k / 7 * 2 * math.pi + 0.3
        cx, cy = int(32 + 14 * math.cos(a)), int(32 + 14 * math.sin(a))
        top = int(hm[cx, cy] + rng.integers(8, 15))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                vox[cx + dx, cy + dy, hm[cx, cy]:top] = OBSIDIAN
    return vox


# ----------------------------------------------------------------------------
# skies + particles
# ----------------------------------------------------------------------------

def sky_image(kind, seed=1):
    r = random.Random(seed)
    cols = {"day": ((105, 170, 255), (200, 228, 255)), "snowy": ((150, 185, 230), (225, 236, 250)),
            "desert": ((110, 175, 245), (245, 222, 180)), "night": ((6, 10, 32), (28, 38, 82)),
            "cave": ((12, 9, 8), (40, 30, 24)), "nether": ((50, 8, 8), (140, 42, 24)),
            "end": ((5, 2, 12), (34, 14, 52))}[kind]
    sw, sh = W + 300, H + 300
    im = mv.vgradient(sw, sh, *cols).convert("RGBA")
    d = ImageDraw.Draw(im)
    if kind in ("night", "end"):
        for _ in range(170):
            s = r.choice((4, 4, 6, 8))
            x, y = r.randrange(sw), r.randrange(int(sh * 0.75))
            c = r.choice([(255, 255, 255), (220, 220, 255), (255, 240, 220)]) if kind == "night" else \
                r.choice([(230, 210, 255), (200, 160, 255), (255, 255, 255)])
            d.rectangle((x, y, x + s, y + s), fill=c + (r.randrange(140, 255),))
    if kind == "night":
        d.rectangle((760, 180, 880, 300), fill=(240, 240, 220, 255))
        for cx, cy, s in ((790, 210, 22), (840, 250, 16), (800, 265, 12)):
            d.rectangle((cx, cy, cx + s, cy + s), fill=(205, 205, 190, 255))
    if kind in ("day", "snowy", "desert"):
        cl = Image.new("RGBA", (sw, sh))
        dc = ImageDraw.Draw(cl)
        for _ in range(9):
            x, y = r.randrange(-100, sw), r.randrange(40, 700)
            for _ in range(r.randint(3, 6)):
                w, h = r.randrange(90, 220), r.randrange(40, 70)
                ox, oy = r.randrange(-120, 120), r.randrange(-30, 30)
                dc.rectangle((x + ox, y + oy, x + ox + w, y + oy + h), fill=(255, 255, 255, 215))
        im.alpha_composite(cl)
    if kind == "nether":
        im.alpha_composite(radial_glow(sw, sh, sw / 2, sh * 0.9, 1100, (255, 110, 30), 0.35))
    if kind == "end":
        im.alpha_composite(radial_glow(sw, sh, sw / 2, sh * 0.3, 900, (140, 60, 200), 0.25))
    return im


PARTICLES = {"snowy": ((255, 255, 255), (6, 12), (40, 110), 60), "nether": ((255, 140, 40), (5, 10), (-90, -30), 45),
             "end": ((190, 110, 255), (6, 10), (-25, 25), 40), "cave": ((190, 170, 140), (4, 7), (-15, 15), 30),
             "night": ((180, 255, 140), (5, 7), (-12, 12), 18), "night2": ((180, 255, 140), (5, 7), (-12, 12), 18)}


class World:
    def __init__(self, name, canvas, origin, sky, seed=0):
        self.name, self.canvas, self.origin, self.sky = name, canvas, origin, sky
        r = random.Random(seed)
        self.parts = []
        if name in PARTICLES:
            col, (s0, s1), (v0, v1), n = PARTICLES[name]
            for _ in range(n):
                self.parts.append((r.uniform(0, W), r.uniform(0, H), r.uniform(-15, 15), r.uniform(v0, v1),
                                   r.randint(s0, s1), col, r.uniform(0, 6.3)))

    def view(self, cx, cy, z, t, shake=(0, 0)):
        sx = int(150 - (cx - 2048) * 0.06) % 300
        sy = int(150 - (cy - 1450) * 0.04)
        sy = max(0, min(300, sy))
        frame = self.sky.crop((sx, sy, sx + W, sy + H))
        w, h = W / z, H / z
        x0, y0 = cx - w / 2 + shake[0] / z, cy - h / 2 + shake[1] / z
        crop = self.canvas.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((W, H), Image.BILINEAR)
        frame.alpha_composite(crop)
        if self.parts:
            d = ImageDraw.Draw(frame)
            for x, y, vx, vy, s, col, ph in self.parts:
                px = (x + vx * t + 18 * math.sin(t * 1.3 + ph)) % W
                py = (y + vy * t) % H
                d.rectangle((px, py, px + s, py + s), fill=col + (255,))
        return frame


def build_worlds(tex):
    worlds = {}
    specs = [
        ("plains", lambda: gen_overworld(11, "plains"), (1, 1, 1), (205, 225, 255), 0.35, "day", None),
        ("snowy", lambda: gen_overworld(23, "snowy"), (1, 1, 1.03), (225, 235, 250), 0.38, "snowy", None),
        ("desert", lambda: gen_overworld(31, "desert"), (1.03, 1, 0.95), (245, 225, 190), 0.38, "desert", None),
        ("night", lambda: gen_overworld(11, "plains"), (0.42, 0.47, 0.72), (20, 28, 60), 0.45, "night", None),
        ("night2", lambda: gen_overworld(47, "plains"), (0.42, 0.47, 0.72), (20, 28, 60), 0.45, "night", None),
        ("cave", lambda: gen_cave(5), (0.55, 0.5, 0.48), (30, 22, 18), 0.5, "cave",
         {LAVA: ((255, 120, 30), 120, 0.35)}),
        ("nether", lambda: gen_nether(9), (0.88, 0.7, 0.66), (130, 35, 22), 0.45, "nether",
         {LAVA: ((255, 120, 30), 110, 0.25), GLOWSTONE: ((255, 220, 120), 120, 0.35),
          PORTAL: ((180, 80, 255), 140, 0.5)}),
        ("end", lambda: gen_end(3), (0.9, 0.88, 1.0), (30, 14, 46), 0.4, "end", None),
        ("ocean", lambda: gen_ocean(17), (1, 1, 1), (200, 225, 255), 0.38, "day", None),
        ("darkforest", lambda: gen_dark_forest(29), (0.72, 0.8, 0.72), (70, 90, 70), 0.42, "day", None),
    ]
    extra = {}
    for i, (name, gen, amb, fog, fs, sky, glow) in enumerate(specs):
        res = gen()
        if isinstance(res, tuple):
            res, extra[name] = res
        cache = SpriteCache(tex, amb, fog)
        canvas, origin = render_voxels(res, cache, fs, glow)
        worlds[name] = World(name, canvas, origin, sky_image(sky, i + 1), seed=i)
    px, py, pz = extra["nether"]
    worlds["nether"].portal = iso_xy(px, py, pz, worlds["nether"].origin)
    return worlds


# ----------------------------------------------------------------------------
# pixel-art icons (original drawings)
# ----------------------------------------------------------------------------

def grid_icon(rows, pal, scale, seed=0):
    r = random.Random(seed)
    h, w = len(rows), max(len(x) for x in rows)
    im = Image.new("RGBA", (w, h))
    px = im.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in pal:
                c = pal[ch]
                px[x, y] = (r.choice(c) if isinstance(c, list) else c) + (255,)
    return im.resize((w * scale, h * scale), Image.NEAREST)


def cube_icon(tex, bid, scale=4):
    cache = SpriteCache(tex, (1, 1, 1), (0, 0, 0))
    return cache.get(bid, 0).resize((SPR_W * scale, SPR_H * scale), Image.NEAREST)


def make_icons(tex):
    G = [(95, 190, 80), (75, 160, 60), (115, 210, 95), (60, 140, 50)]
    icons = {}
    icons["creeper"] = grid_icon(["GGGGGGGG", "GGGGGGGG", "GBBGGBBG", "GBBGGBBG", "GGGBBGGG",
                                  "GGBBBBGG", "GGBBBBGG", "GGBGGBGG"],
                                 {"G": G, "B": (22, 30, 22)}, 32, 1)
    icons["obsidian"] = cube_icon(tex, OBSIDIAN)
    icons["debris"] = cube_icon(tex, DEBRIS)
    icons["sheep"] = grid_icon(["...........wWWW.", ".wWWWWWWWWWWFFFF", "wWWWWWWWWWWWEFFE", "wWWWWWWWWWWWFFFF",
                                "wWWWWWWWWWWWFPPF", "wWWWWWWWWWWW.FF.", ".wWWWWWWWWWw....", "..LL.LL..LL.LL..",
                                "..LL.LL..LL.LL..", "..LL.LL..LL.LL.."],
                               {"W": [(240, 240, 240), (228, 228, 228)], "w": (205, 205, 205),
                                "F": (226, 196, 172), "E": (30, 30, 30), "P": (230, 150, 150), "L": (200, 170, 150)},
                               16, 2)
    icons["eye"] = grid_icon(["....AAAA....", "..AABBBBAA..", ".ABBCCCCBBA.", ".ABCCDDCCBA.", "ABCCDKKDCCBA",
                              "ABCDKKKKDCBA", "ABCDKKKKDCBA", "ABCCDKKDCCBA", ".ABCCDDCCBA.", ".ABBCCCCBBA.",
                              "..AABBBBAA..", "....AAAA...."],
                             {"A": (20, 80, 70), "B": (40, 140, 120), "C": (90, 200, 150), "D": (170, 235, 190),
                              "K": (10, 45, 40)}, 20, 3)
    B, P, p = [(18, 14, 24), (26, 20, 34)], (204, 0, 250), (255, 150, 255)
    em = ["..BBBBBBBB..", "..BBBBBBBB..", "..BBBBBBBB..", "..BBBBBBBB..", "..PPpBBpPP..", "..BBBBBBBB..",
          "..BBBBBBBB..", "..BBBBBBBB.."] + ["BB..BBBB..BB"] * 8 + ["BB..B..B..BB"] * 6 + ["....B..B...."] * 8
    icons["enderman"] = grid_icon(em, {"B": B, "P": P, "p": p}, 8, 4)
    icons["bed"] = grid_icon(["..WWWW..........", "..WWWWrrrrrrrrrr", "MMMMMMRRRRRRRRRR", "MMMMMMRRRRRRRRRR",
                              "PPPPPPPPPPPPPPPP", "PP............PP", "PP............PP"],
                             {"W": (245, 245, 245), "M": (210, 210, 210), "r": (200, 30, 30), "R": (170, 20, 20),
                              "P": [(150, 110, 60), (130, 95, 50)]}, 16, 5)
    disc = Image.new("RGBA", (16, 16))
    dpx = disc.load()
    for y in range(16):
        for x in range(16):
            d = math.hypot(x - 7.5, y - 7.5)
            if d < 7.6:
                dpx[x, y] = (40, 40, 46, 255) if d > 2.2 else (120, 120, 130, 255)
                if 4.8 < d < 5.6:
                    dpx[x, y] = (62, 62, 70, 255)
    for x, y in ((11, 1), (12, 2), (11, 3), (12, 4), (11, 5), (10, 6), (9, 7), (13, 3), (14, 4), (13, 1), (14, 2)):
        dpx[x, y] = (0, 0, 0, 0)
    for x, y in ((10, 2), (10, 4), (9, 5), (8, 6), (7, 7)):
        dpx[x, y] = (12, 12, 14, 255)
    icons["disc"] = disc.resize((240, 240), Image.NEAREST)
    icons["dragon"] = grid_icon(["B..............................B", "BB............................BB",
                                 ".BBB........................BBB.", "..BBBB.......BBBBBB.......BBBB..",
                                 "...BBBBB....BBPBBPBB....BBBBB...", "....BBBBBBBBBBBBBBBBBBBBBBBB....",
                                 ".....BBBBBBBBBBBBBBBBBBBBBB.....", ".......BBBBBBBBBBBBBBBBBB.......",
                                 "..........BBBBBBBBBBBB..........", "............BBBBBBBB............",
                                 ".............BBBBBB.............", "..............BBBB..............",
                                 "...............BB...............", "................B..............."],
                                {"B": [(20, 16, 26), (32, 26, 40)], "P": (210, 60, 255)}, 9, 6)
    Z1, Z2 = [(90, 150, 80), (80, 138, 70), (100, 160, 88)], [(60, 110, 55), (52, 98, 48)]
    icons["zombie"] = grid_icon(["HHHHHHHH", "HHHHHHHH", "ZZZZZZZZ", "ZZZZZZZZ", "ZEEZZEEZ", "ZZZNNZZZ",
                                 "ZZMMMMZZ", "ZZZZZZZZ"],
                                {"H": Z2, "Z": Z1, "E": (20, 26, 20), "N": (60, 100, 52), "M": (40, 70, 36)}, 32, 7)
    m = np.zeros((16, 14, 13), np.uint8)
    x0, x1, y0, y1 = 1, 13, 1, 11
    m[x0:x1 + 1, y0:y1 + 1, 0] = STONE
    m[x0:x1 + 1, y0:y1 + 1, 1:8] = PLANKS
    for z in (4,):
        m[x0:x1 + 1, y0:y1 + 1, z] = DARK_OAK
    for cx in (x0, x1, (x0 + x1) // 2):
        for cy in (y0, y1):
            m[cx, cy, 1:8] = DARK_OAK
    for cy in (y0, (y0 + y1) // 2):
        m[x1, cy, 1:8] = DARK_OAK
    for z in (2, 3, 5, 6):
        for xx in range(x0 + 2, x1 - 1, 3):
            m[xx, y1, z] = GLASS
            m[xx + 1, y1, z] = GLASS
        for yy in range(y0 + 2, y1 - 1, 3):
            m[x1, yy, z] = GLASS
    for k, z in enumerate(range(8, 12)):
        m[max(0, x0 - 1 + k):x1 + 2 - k, max(0, y0 - 1 + k):y1 + 2 - k, z] = ROOF
    man, _ = render_voxels(m, SpriteCache(tex, (1, 1, 1), (0, 0, 0)), 0)
    man = man.crop(man.getbbox())
    icons["mansion"] = man.resize((300, int(300 * man.height / man.width)), Image.LANCZOS)
    island = np.zeros((11, 11, 10), np.uint8)
    for x in range(11):
        for y in range(11):
            if math.hypot(x - 5, y - 5) < 5.2:
                island[x, y, 0:3] = END_STONE
    island[4:7, 4:7, 3:9] = OBSIDIAN
    isl, _ = render_voxels(island, SpriteCache(tex, (1, 1, 1), (0, 0, 0)), 0)
    isl = isl.crop(isl.getbbox())
    icons["end_island"] = isl.resize((300, int(300 * isl.height / isl.width)), Image.LANCZOS)
    return icons


def fit(im, box):
    s = min(box / im.width, box / im.height)
    rs = Image.NEAREST if s >= 1 else Image.LANCZOS
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), rs)


# ----------------------------------------------------------------------------
# game-style UI pieces
# ----------------------------------------------------------------------------

def bevel_box(w, h, fill=(20, 20, 30, 175), light=(205, 205, 205), dark=(70, 70, 70), border=7):
    im = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), fill=(0, 0, 0, 255))
    d.rectangle((4, 4, w - 5, h - 5), fill=dark + (255,))
    d.polygon([(4, 4), (w - 5, 4), (w - 5 - border, 4 + border), (4 + border, 4 + border), (4 + border, h - 5 - border),
               (4, h - 5)], fill=light + (255,))
    d.rectangle((4 + border, 4 + border, w - 5 - border, h - 5 - border), fill=fill)
    return im


def mc_button(text, w, h, col, size=40):
    im = bevel_box(w, h, fill=col + (235,), light=tuple(min(255, c + 70) for c in col),
                   dark=tuple(int(c * 0.5) for c in col), border=6)
    paste_center(im, ptext(text, size), w / 2, h / 2 + 2)
    return im


def sunburst(size, col, rays=14):
    ss = 2
    im = Image.new("RGBA", (size * ss, size * ss))
    d = ImageDraw.Draw(im)
    c = size * ss / 2
    for i in range(rays):
        a0 = i / rays * 2 * math.pi
        a1 = a0 + math.pi / rays
        d.polygon([(c, c), (c + c * 1.5 * math.cos(a0), c + c * 1.5 * math.sin(a0)),
                   (c + c * 1.5 * math.cos(a1), c + c * 1.5 * math.sin(a1))], fill=col + (90,))
    im = im.resize((size, size), Image.LANCZOS)
    mask = radial_glow(size, size, size / 2, size / 2, size / 2, (255, 255, 255), 1.0).getchannel("A")
    im.putalpha(Image.fromarray(np.minimum(np.asarray(im.getchannel("A")), np.asarray(mask))))
    im.alpha_composite(radial_glow(size, size, size / 2, size / 2, size * 0.4, col, 0.8))
    return im


def shade_overlays():
    top = np.zeros((H, W, 4), np.uint8)
    ys = np.arange(H)
    a = np.clip(1 - ys / 760, 0, 1) ** 1.3 * 150 + np.clip((ys - 1250) / 670, 0, 1) ** 1.2 * 175
    top[..., 3] = a[:, None].astype(np.uint8)
    return Image.fromarray(top, "RGBA")


class UI:
    """Shared, pre-rendered UI assets."""

    def __init__(self, icons):
        self.frame = bevel_box(340, 340)
        self.frame_gold = bevel_box(340, 340, fill=(20, 20, 30, 70), light=(255, 230, 120), dark=(170, 120, 20))
        self.slot = bevel_box(88, 88, fill=(30, 30, 38, 200), light=(150, 150, 150), dark=(50, 50, 50), border=4)
        sel = Image.new("RGBA", (100, 100))
        ImageDraw.Draw(sel).rectangle((0, 0, 99, 99), outline=(255, 255, 255, 255), width=7)
        self.selector = sel
        self.shade = shade_overlays()
        self.nums = {(n, red): ptext(str(n), 160, fill=(255, 80, 70) if red else (255, 255, 255))
                     for n in range(1, 10) for red in (False, True)}
        self.small = {}
        for k, v in icons.items():  # dark icons get a soft glow so they stay visible in the dark slots
            sm = fit(v, 64)
            if k in ("dragon", "enderman", "disc", "obsidian", "mansion"):
                g = radial_glow(84, 84, 42, 42, 44, (200, 140, 255), 0.75)
                paste_center(g, sm, 42, 42)
                sm = g
            self.small[k] = sm
        self.big = {k: fit(v, 270) for k, v in icons.items()}
        r = random.Random(5)
        cell = 90
        self.cells = [(x, y) for y in range(0, H, cell) for x in range(0, W, cell)]
        r.shuffle(self.cells)
        self.cell = cell

    def hotbar(self, im, icons_on, current, fly=None):
        n = 10
        x0 = W / 2 - n * 88 / 2
        for i in range(n):
            x = x0 + i * 88
            im.alpha_composite(self.slot, (int(x), HOTBAR_Y - 44))
            if i < len(icons_on) and icons_on[i] is not None:
                paste_center(im, self.small[icons_on[i]], x + 44, HOTBAR_Y)
        if current is not None:
            im.alpha_composite(self.selector, (int(x0 + current * 88 - 6), HOTBAR_Y - 50))
        if fly:
            key, k, idx = fly
            tx, ty = x0 + idx * 88 + 44, HOTBAR_Y
            e = ease_in_cubic(k)
            x = W / 2 + (tx - W / 2) * e
            y = FRAME_Y + (ty - FRAME_Y) * e - math.sin(math.pi * k) * 160
            paste_center(im, scaled(self.big[key], 1 - 0.76 * e), x, y)

    def blocks(self, im, coverage):
        if coverage <= 0:
            return
        d = ImageDraw.Draw(im)
        n = int(len(self.cells) * clamp(coverage))
        c = self.cell
        for x, y in self.cells[:n]:
            d.rectangle((x, y, x + c, y + c), fill=(12, 10, 16, 255))


# ----------------------------------------------------------------------------
# audio (original synths)
# ----------------------------------------------------------------------------

def square(freq, dur, duty=0.5):
    t = tt(dur)
    return np.where((t * freq) % 1 < duty, 1.0, -1.0)


def tri(freq, dur):
    t = tt(dur)
    return 2 * np.abs(2 * ((t * freq) % 1) - 1) - 1


def env(n, a=0.004, d=8.0):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t * d)


def sfx_boom():
    t = tt(1.4)
    f = 32 + 90 * np.exp(-t * 6)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3)
    n = lowpass(np.random.default_rng(1).standard_normal(len(t)), 900) * np.exp(-t * 4) * 2.2
    out = np.tanh(1.8 * (s + n))
    return out / np.abs(out).max() * 0.9


def sfx_tock(high=False):
    t = tt(0.09)
    f = 1150 if high else 760
    s = np.sin(2 * np.pi * f * t) * np.exp(-t * 70) + 0.5 * np.sin(2 * np.pi * f * 1.5 * t) * np.exp(-t * 90)
    n = highpass(np.random.default_rng(2).standard_normal(len(t)), 1800) * np.exp(-t * 300) * 0.5
    return (s + n) * (0.75 if high else 0.6)


def sfx_pling():
    out = np.zeros(int(0.9 * SR))
    for i, n in enumerate((79, 84, 88, 91)):
        s = 0.5 * square(midi(n), 0.5, 0.25) * env(int(0.5 * SR), 0.002, 7) + 0.5 * tri(midi(n + 12), 0.5) * env(
            int(0.5 * SR), 0.002, 9)
        st = int(i * 0.055 * SR)
        out[st:st + len(s)] += s[: len(out) - st]
    return lowpass(out, 7000) * 0.35


def sfx_crunch():
    n = int(0.14 * SR)
    rng = np.random.default_rng(4)
    s = lowpass(rng.standard_normal(n), 2500) * env(n, 0.002, 30)
    s *= (rng.random(n) > 0.3)
    return s * 0.6


def sfx_levelup():
    out = np.zeros(int(0.8 * SR))
    for i, n in enumerate((72, 76, 79, 84, 88)):
        s = square(midi(n), 0.3, 0.5) * env(int(0.3 * SR), 0.002, 9)
        st = int(i * 0.06 * SR)
        out[st:st + len(s)] += s[: len(out) - st]
    return lowpass(out, 6000) * 0.22


def sfx_roar():
    t = tt(1.5)
    f = 62 + 10 * np.sin(2 * np.pi * 7 * t) - 15 * t
    ph = np.cumsum(f) / SR
    saw = 2 * (ph % 1) - 1
    n = lowpass(np.random.default_rng(6).standard_normal(len(t)), 1200)
    e = np.minimum(1, t / 0.15) * np.exp(-np.maximum(t - 0.6, 0) * 3)
    out = np.tanh(2.5 * (saw + 0.6 * n) * e)
    return lowpass(out, 2500) * 0.7


def sfx_glitch():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    s = square(110, 0.25) * (np.sin(2 * np.pi * 23 * t) > 0) * env(n, 0.001, 10)
    return lowpass(s, 3000) * 0.3


def make_chiptune(total):
    """Original upbeat chiptune loop: Am - F - C - G."""
    bpm = 140
    beat = 60 / bpm
    bars = [(57, (69, 72, 76)), (53, (65, 69, 72)), (48, (64, 67, 72)), (55, (62, 67, 71))]
    lead = {4: [(0, 81, 1), (1, 84, 1), (2, 83, .5), (2.5, 79, .5), (3, 76, 1)],
            5: [(0, 77, 1), (1, 81, 1), (2, 79, 1), (3, 77, 1)],
            6: [(0, 76, 1), (1, 79, 1), (2, 84, 1.5), (3.5, 83, .5)],
            7: [(0, 83, 2), (2, 79, 2)]}
    loop_len = 8 * 4 * beat
    out = np.zeros(int(loop_len * SR) + SR)
    rng = np.random.default_rng(3)

    def add(sig, at, g):
        st = int(at * SR)
        e = min(len(out), st + len(sig))
        out[st:e] += sig[:e - st] * g

    kick_t = tt(0.22)
    kick = np.sin(2 * np.pi * np.cumsum(50 + 120 * np.exp(-kick_t * 35)) / SR) * np.exp(-kick_t * 14)
    snare = highpass(rng.standard_normal(int(0.16 * SR)), 1200) * env(int(0.16 * SR), 0.001, 22)
    hat = highpass(rng.standard_normal(int(0.04 * SR)), 7000) * env(int(0.04 * SR), 0.001, 110)
    for b in range(8):
        root, chord = bars[b % 4]
        t0 = b * 4 * beat
        for k in range(8):
            n = root - 12 + (12 if k % 2 else 0)
            add(square(midi(n), beat / 2 * 0.9, 0.5) * env(int(beat / 2 * 0.9 * SR), 0.002, 6), t0 + k * beat / 2,
                0.09)
        for k in range(16):
            n = chord[k % 3] + (12 if (k // 3) % 2 else 0)
            add(tri(midi(n), beat / 4) * env(int(beat / 4 * SR), 0.002, 14), t0 + k * beat / 4, 0.07)
        for pos, n, ln in lead.get(b, []):
            d = ln * beat * 0.95
            add(square(midi(n), d, 0.25) * env(int(d * SR), 0.005, 2.2), t0 + pos * beat, 0.06)
        for k in range(4):
            add(kick if k % 2 == 0 else snare, t0 + k * beat, 0.5 if k % 2 == 0 else 0.22)
            add(hat, t0 + k * beat + beat / 2, 0.05)
    loop = lowpass(out[:int(loop_len * SR)], 8000)
    music = np.tile(loop, int(math.ceil(total / loop_len)) + 1)[:int(total * SR)]
    return music / (np.abs(music).max() + 1e-9)


def piano_note(freq, vel=0.6, ring=3.2):
    """Soft synthesised piano tone: slightly inharmonic partials, two detuned strings, felt hammer."""
    t = tt(ring)
    out = np.zeros_like(t)
    base = 0.9 + 0.7 * (freq / 261.6)
    for n in range(1, 9):
        fn = n * freq * math.sqrt(1 + 0.0004 * n * n)
        if fn > 8000:
            break
        amp = (1 / n ** 1.35) * (0.45 + 0.4 * vel) ** (n - 1)
        dn = base * (0.6 + 0.45 * n)
        e = 0.55 * np.exp(-t * dn * 2.4) + 0.45 * np.exp(-t * dn * 0.45)
        out += amp * 0.5 * (np.sin(2 * np.pi * fn * t) + np.sin(2 * np.pi * fn * 1.0008 * t + n)) * e
    out *= np.minimum(1, t / 0.005)
    out[: int(0.02 * SR)] += lowpass(np.random.default_rng(int(freq)).standard_normal(int(0.02 * SR)), 1500) * 0.03
    fade = int(0.3 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out * vel


def make_piano(total):
    """Original calm piano piece (Cmaj7 - Am7 - Fmaj7 - G), loops seamlessly."""
    from scipy.signal import fftconvolve
    bpm = 76
    beat = 60 / bpm
    chords = [(48, (48, 55, 59, 64)), (45, (45, 52, 55, 60)), (41, (41, 48, 52, 57)), (43, (43, 50, 55, 59))]
    melody = {0: [(0, 76, .62), (2, 79, .5), (3, 74, .45)], 1: [(0, 72, .6), (3, 76, .45)],
              2: [(0, 81, .62), (1.5, 79, .4), (2, 76, .5)], 3: [(0, 74, .55), (2, 71, .45), (3, 74, .4)],
              4: [(0, 76, .55), (1, 79, .55), (2, 84, .62)], 5: [(0, 83, .58), (1.5, 79, .4), (2, 76, .5)],
              6: [(0, 81, .55), (1, 79, .45), (2, 77, .45), (3, 72, .45)], 7: [(0, 74, .55), (2, 67, .45)]}
    L = 8 * 4 * beat
    buf = np.zeros(int((L + 4) * SR))
    cache = {}

    def note(m, vel, at):
        key = (m, round(vel, 2))
        if key not in cache:
            cache[key] = piano_note(midi(m), vel)
        sig = cache[key]
        st = int(at * SR)
        buf[st:st + len(sig)] += sig[: len(buf) - st]

    for b in range(8):
        root, v = chords[b % 4]
        t0 = b * 4 * beat
        note(root - 12, 0.38, t0)
        for k, idx in enumerate((0, 1, 2, 3, 2, 1, 2, 3)):
            note(v[idx], 0.26 + 0.04 * (k == 0), t0 + k * beat / 2)
        for pos, m, vel in melody[b]:
            note(m, vel, t0 + pos * beat)
    n = int(L * SR)
    tail = buf[n:]
    loop = buf[:n].copy()
    loop[:len(tail)] += tail[:n]
    ir_t = tt(2.6)
    ir = lowpass(np.random.default_rng(8).standard_normal(len(ir_t)), 5000) * np.exp(-ir_t / 0.55)
    ir /= np.sqrt(np.sum(ir ** 2))
    wet = fftconvolve(np.concatenate([loop, loop]), ir)[n:2 * n]  # circular reverb so the loop is seamless
    loop = 0.8 * loop + 0.35 * wet
    music = np.tile(loop, int(math.ceil(total / L)) + 1)[: int(total * SR)]
    fade = int(0.8 * SR)
    music[-fade:] *= np.linspace(1, 0.3, fade)
    return music / (np.abs(music).max() + 1e-9)


def mix(scenes, starts, total, music_kind="piano"):
    n = int(total * SR) + SR
    voice, fx = np.zeros(n), np.zeros(n)
    for sc, st in zip(scenes, starts):
        for at, arr in sc.voices:
            i = int((st + at) * SR)
            voice[i:i + len(arr)] += arr[:n - i]
        for at, arr, g in sc.sounds:
            i = int((st + at) * SR)
            fx[i:i + len(arr)] += arr[:n - i] * g
    music = np.zeros(n)
    m = make_piano(total) if music_kind == "piano" else make_chiptune(total)
    music[:len(m)] = m
    envv = lowpass(np.abs(voice), 8)
    duck = lowpass(1 - 0.5 * np.clip(envv / 0.05, 0, 1), 3)
    out = voice + fx * 0.6 + music * (0.3 if music_kind == "piano" else 0.2) * duck
    out = np.tanh(out * 1.1) / np.tanh(1.1)
    return (np.clip(np.stack([out, out], 1), -1, 1) * 32767).astype(np.int16)


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------

def cam_at(path, k):
    (x0, y0, z0), (x1, y1, z1) = path
    e = 3 * k * k - 2 * k * k * k
    return x0 + (x1 - x0) * e, y0 + (y1 - y0) * e, z0 + (z1 - z0) * e


class Intro(mv.Scene):
    def __init__(self, tts, worlds, ui):
        super().__init__()
        v = tts.say("Only real Minecraft players can get ten out of ten!", speed=1.18)
        self.voices.append((0.05, v))
        self.dur = max(2.3, 0.05 + len(v) / SR + 0.12)
        self.sounds += [(0.0, sfx_boom(), 0.9), (0.0, sfx_whoosh(0.5), 0.8), (0.95, sfx_glitch(), 0.8),
                        (1.2, sfx_levelup(), 0.8)]
        self.world, self.ui = worlds["plains"], ui
        self.lines = [(bold("ONLY REAL", 130), 0.08, 560), (bold("MINECRAFT", 150, fill=(100, 230, 80)), 0.3, 720),
                      (bold("PLAYERS", 150), 0.5, 880), (bold("CAN GET 10/10!", 128, fill=YELLOW, max_w=1000), 0.72, 1050)]
        tag = mc_button("99% FAIL", 420, 110, (210, 30, 30), 44)
        self.tag = tag.rotate(8, Image.BICUBIC, expand=True)

    def render(self, t):
        k = ease_out_cubic(t / 0.55)
        cx, cy, z = cam_at(INTRO_CAM, k)
        shake = (0, 0)
        if t < 0.35:
            shake = (24 * math.sin(t * 90) * (1 - t / 0.35), 18 * math.cos(t * 70) * (1 - t / 0.35))
        im = self.world.view(cx, cy, z, t, shake)
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 90)))
        for img, t0, y in self.lines:
            if t >= t0:
                s = 1 + 1.2 * (1 - ease_out_cubic((t - t0) / 0.16))
                paste_center(im, scaled(img, s), W / 2, y, clamp((t - t0) / 0.08))
        if t > 0.95:
            paste_center(im, scaled(self.tag, ease_out_back((t - 0.95) / 0.25)), W / 2, 1250)
        fl = 1 - clamp(t / 0.3)
        if fl > 0:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))
        self.ui.blocks(im, clamp((t - (self.dur - 0.15)) / 0.15))
        return im


class Question(mv.Scene):
    def __init__(self, tts, idx, q, worlds, ui, prev_level):
        super().__init__()
        self.idx, self.q, self.ui = idx, q, ui
        self.world = worlds[q["scene"]]
        self.reveal_world = worlds.get(q.get("reveal_scene"))
        cam = q["cam"]
        if cam[0] == "portal":
            px, py = self.world.portal
            # keep the portal visible up and to the right of the centre frame
            cam = ((px - 290 / cam[1], py + 240 / cam[1], cam[1]), (px - 290 / cam[2], py + 240 / cam[2], cam[2]))
        self.cam = cam
        spoken = q["q"].replace("*", "")
        self.cd_len = q.get("time", COUNTDOWN)  # seconds to answer
        for speed in (1.15, 1.25, 1.35):
            v = tts.say(spoken, speed=speed)
            if len(v) / SR <= self.cd_len - 0.25:
                break
        else:
            print(f"warning: question {idx} narration is {len(v) / SR:.1f}s", flush=True)
        self.voices.append((T_IN + 0.05, v))
        a = tts.say(q["say"], speed=1.12)
        self.reveal = T_IN + self.cd_len
        self.voices.append((self.reveal + 0.12, a))
        self.dur = self.reveal + T_HOLD
        self.sounds.append((0.0, sfx_whoosh(0.3), 0.5))
        for k in range(int(self.cd_len)):
            self.sounds.append((T_IN + k, sfx_tock(high=k >= self.cd_len - 2), 1.0))
        self.sounds += [(self.reveal, sfx_pling(), 1.0), (self.reveal, sfx_crunch(), 0.8),
                        (self.reveal + 0.62, sfx_crunch(), 0.5)]
        fx = q.get("fx")
        if fx == "explode":
            self.sounds.append((self.reveal, sfx_boom(), 1.0))
        if fx == "dragon":
            self.sounds.append((self.reveal + 0.05, sfx_roar(), 0.9))
        if self.reveal_world:
            self.sounds.append((self.reveal, sfx_whoosh(0.5), 0.8))
        self.level_change = q["level"] != prev_level and idx > 1
        if self.level_change:
            self.sounds.append((0.15, sfx_levelup(), 1.0))
            txt = f"{q['level']} MODE"
            self.banner = mc_button(("! " + txt + " !") if q["level"] == "HARD" else txt, 760, 120,
                                    DIFF[q["level"]], 46)
        col = DIFF[q["level"]]
        self.head = ptext(f"QUESTION {idx}/10", 40)
        self.badge = mc_button(q["level"], 300, 84, col, 36)
        qt = rich_block(q["q"], 82, 930)
        pw, ph = 1010, qt.height + 70
        panel = bevel_box(pw, ph, fill=(10, 10, 20, 205), light=tuple(min(255, c + 60) for c in col),
                          dark=tuple(int(c * 0.45) for c in col), border=7)
        paste_center(panel, qt, pw / 2, ph / 2)
        self.panel = panel
        self.panel_y = 300 + ph / 2
        self.answer = bold(q["a"], 104, fill=YELLOW, stroke=10, max_w=1000)
        self.check = ptext("+1", 48, fill=(120, 255, 90))
        self.rays = sunburst(620, q["col"])
        self.inner_glow = radial_glow(320, 320, 160, 160, 170, q["col"], 0.75)
        self.icon = ui.big[q["icon"]]
        self.dragon_big = fit(ui.big["dragon"], 900) if fx == "dragon" else None
        r = random.Random(idx)
        cols = [q["col"], tuple(min(255, c + 60) for c in q["col"]), (255, 255, 255)]
        if fx == "explode":
            cols = [(255, 180, 40), (255, 90, 20), (90, 90, 90), (200, 200, 200)]
        self.burst = [(r.uniform(-700, 700), r.uniform(-1100, -300), r.randint(12, 26), r.choice(cols))
                      for _ in range(34)]

    def render(self, t):
        q, ui = self.q, self.ui
        rv = t - self.reveal
        k = t / self.dur
        cx, cy, z = cam_at(self.cam, k)
        if rv > 0:
            z *= 1 + 0.06 * math.sin(math.pi * clamp(rv / 0.35))
        shake = (0, 0)
        if q.get("fx") in ("explode", "dragon") and 0 < rv < 0.6:
            a = (1 - rv / 0.6) * (34 if q.get("fx") == "explode" else 18)
            shake = (a * math.sin(rv * 95), a * math.cos(rv * 80))
        im = self.world.view(cx, cy, z, t, shake)
        if self.reveal_world and rv > 0:
            alt = self.reveal_world.view(2048, 1450, 1.05 + 0.08 * rv, t, shake)
            alt.putalpha(int(255 * ease_out_cubic(rv / 0.3)))
            im.alpha_composite(alt)
        if q.get("fx") == "dragon" and rv > 0:
            paste_center(im, self.dragon_big, W + 500 - rv * 1500, 760 + 30 * math.sin(rv * 6), 0.85)
        im.alpha_composite(ui.shade)
        # header
        hk = ease_out_back(t / 0.3)
        paste_center(im, scaled(self.head, hk), W / 2, 185)
        paste_center(im, scaled(self.badge, hk), W / 2, 250)
        # question panel drops in
        drop = (1 - ease_out_back(t / 0.32, 1.3)) * -500
        paste_center(im, self.panel, W / 2, self.panel_y + drop)
        # difficulty banner
        if self.level_change and t < 1.0:
            bx = W / 2 + (1 - ease_out_cubic(t / 0.2)) * W - ease_in_cubic((t - 0.8) / 0.2) * W
            paste_center(im, self.banner.rotate(-4, Image.BICUBIC, expand=True), bx, 760)
        # centre frame: countdown, then the answer
        if rv < 0:
            cd = max(0.0, t - T_IN)
            n = max(1, int(self.cd_len) - int(cd))
            red = n <= 2
            fk = ease_out_back((t - 0.1) / 0.3)
            paste_center(im, scaled(ui.frame, fk * (1 + 0.03 * math.sin(t * 12) if red else fk)), W / 2, FRAME_Y)
            pop = 1 + 0.35 * (1 - ease_out_cubic((cd % 1) / 0.3))
            paste_center(im, scaled(ui.nums[(n, red)], pop * fk), W / 2, FRAME_Y + 4)
            # draining time bar
            frac = 1 - clamp(cd / self.cd_len)
            d = ImageDraw.Draw(im)
            bw, bh, segs = 760, 34, 20
            x0 = W / 2 - bw / 2
            d.rectangle((x0 - 6, BAR_Y - bh / 2 - 6, x0 + bw + 6, BAR_Y + bh / 2 + 6), fill=(0, 0, 0, 255))
            on = int(math.ceil(segs * frac))
            col = (255, 70, 60) if red else (128, 255, 40)
            for s in range(segs):
                sx = x0 + s * bw / segs
                d.rectangle((sx + 2, BAR_Y - bh / 2, sx + bw / segs - 2, BAR_Y + bh / 2),
                            fill=col + (255,) if s < on else (45, 45, 45, 255))
        else:
            rk = ease_out_back(rv / 0.3)
            rays = self.rays.rotate(rv * 40, Image.BICUBIC)
            paste_center(im, scaled(rays, 0.6 + 0.4 * rk), W / 2, FRAME_Y)
            paste_center(im, scaled(ui.frame_gold, rk), W / 2, FRAME_Y)
            paste_center(im, scaled(self.inner_glow, rk), W / 2, FRAME_Y)
            if rv < 0.5:
                wob = 1 + 0.1 * math.sin(rv * 18) * (1 - rv / 0.5)
                paste_center(im, scaled(self.icon, rk * wob), W / 2, FRAME_Y)
            for vx, vy, s, c in self.burst:
                px = W / 2 + vx * rv
                py = FRAME_Y + vy * rv + 2200 * rv * rv
                if py < H:
                    ImageDraw.Draw(im).rectangle((px, py, px + s, py + s), fill=c + (255,))
            paste_center(im, scaled(self.answer, ease_out_back((rv - 0.05) / 0.3)), W / 2, ANSWER_Y)
            if rv > 0.25:
                paste_center(im, self.check, W / 2 + self.answer.width / 2 + 40, ANSWER_Y - 60,
                             clamp((rv - 0.25) / 0.15))
            fl = 1 - clamp(rv / (0.4 if q.get("fx") == "explode" else 0.18))
            if fl > 0:
                c = (255, 200, 120) if q.get("fx") == "explode" else (255, 255, 255)
                im.alpha_composite(Image.new("RGBA", (W, H), c + (int(220 * fl),)))
        # hotbar
        icons_on = [QUESTIONS[i]["icon"] for i in range(self.idx - 1)]
        fly = None
        if rv > 0.5:
            kk = clamp((rv - 0.5) / 0.28)
            if kk < 1:
                fly = (q["icon"], kk, self.idx - 1)
            else:
                icons_on.append(q["icon"])
        ui.hotbar(im, icons_on, self.idx - 1, fly)
        # block transitions
        ui.blocks(im, 1 - clamp(t / T_IN))
        ui.blocks(im, clamp((t - (self.dur - 0.15)) / 0.15))
        return im


class Ending(mv.Scene):
    def __init__(self, tts, worlds, ui):
        super().__init__()
        v = tts.say("What was your score? Comment it below!", speed=1.12)
        self.voices.append((0.2, v))
        self.dur = max(4.2, 0.2 + len(v) / SR + 1.6)
        self.sounds += [(0.0, sfx_whoosh(0.4), 0.7), (0.2, sfx_levelup(), 0.9)]
        self.world, self.ui = worlds["plains"], ui
        self.t1 = bold("WHAT WAS", 110, fill=YELLOW, stroke=10)
        self.t2 = bold("YOUR SCORE?", 120, fill=YELLOW, stroke=10)
        rows = [("0-3", "NOOB", (120, 120, 130)), ("4-6", "PRO", (60, 170, 70)),
                ("7-9", "MINECRAFT MASTER", (60, 110, 220)), ("10/10", "LEGENDARY PLAYER!", (220, 150, 20))]
        self.rows = []
        for i, (rng_, label, col) in enumerate(rows):
            b = bevel_box(940, 120, fill=col + (235,), light=tuple(min(255, c + 70) for c in col),
                          dark=tuple(int(c * 0.5) for c in col), border=6)
            ri = ptext(rng_, 40)
            b.alpha_composite(ri, (40, 60 - ri.height // 2))
            li = bold(label, 58 if i < 3 else 60, fill=(255, 255, 255) if i < 3 else YELLOW, stroke=6, max_w=640)
            b.alpha_composite(li, (940 - 30 - li.width, 60 - li.height // 2))
            self.rows.append(b)
            self.sounds.append((0.6 + 0.2 * i, sfx_crunch(), 0.7))
        ct = bold("COMMENT YOUR SCORE!", 62, stroke=7)
        e = emoji("👇", 80)
        self.cta = Image.new("RGBA", (ct.width + e.width + 10, max(ct.height, e.height)))
        self.cta.alpha_composite(ct, (0, (self.cta.height - ct.height) // 2))
        self.cta.alpha_composite(e, (ct.width + 10, (self.cta.height - e.height) // 2))
        self.sounds.append((1.5, sfx_pling(), 0.8))
        self.loop_flash = 0.35

    def render(self, t):
        k = clamp(t / self.dur)
        start = (2048, 1450, 1.05)
        cx, cy, z = cam_at((start, INTRO_CAM[0]), ease_in_cubic(k))
        im = self.world.view(cx, cy, z, t)
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 120)))
        paste_center(im, scaled(self.t1, ease_out_back(t / 0.35)), W / 2, 330)
        paste_center(im, scaled(self.t2, ease_out_back((t - 0.12) / 0.35)), W / 2, 460)
        for i, row in enumerate(self.rows):
            kk = ease_out_cubic((t - 0.6 - 0.2 * i) / 0.35)
            paste_center(im, row, W / 2 + (1 - kk) * (W if i % 2 else -W), 640 + i * 145)
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.5) / 0.4) * (1 + 0.04 * math.sin(t * 8))), W / 2,
                     1250)
        self.ui.hotbar(im, [qq["icon"] for qq in QUESTIONS], None)
        fl = clamp((t - (self.dur - self.loop_flash)) / self.loop_flash)
        if fl > 0:  # white flash that matches the intro's first frame, so the Short loops cleanly
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))
        return im


# ----------------------------------------------------------------------------

def build(voice="bm_george"):
    ensure_pixfont()
    tex = make_textures()
    print("Rendering worlds ...", flush=True)
    worlds = build_worlds(tex)
    icons = make_icons(tex)
    ui = UI(icons)
    tts = mv.TTS(voice, "en-gb" if voice.startswith("b") else "en-us")
    scenes = [Intro(tts, worlds, ui)]
    prev = None
    for i, q in enumerate(QUESTIONS, 1):
        scenes.append(Question(tts, i, q, worlds, ui, prev))
        prev = q["level"]
    scenes.append(Ending(tts, worlds, ui))
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, worlds, icons


def make_cover(worlds, icons, path):
    w = worlds["night"]
    im = w.view(2048, 1480, 1.15, 0)
    im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 110)))
    im.alpha_composite(radial_glow(W, H, W / 2, 1000, 650, (120, 255, 90), 0.35))
    creeper = fit(icons["creeper"], 560).rotate(-6, Image.NEAREST, expand=True)
    sh = Image.new("RGBA", creeper.size, (0, 0, 0, 0))
    sh.putalpha(creeper.getchannel("A").point(lambda v: v * 0.6))
    paste_center(im, sh.filter(ImageFilter.GaussianBlur(18)), W / 2 + 20, 1030)
    paste_center(im, creeper, W / 2, 1000)
    pick = Image.open(os.path.join(HERE, "mc_assets", "pickaxe.png")).convert("RGBA").resize((330, 330), Image.LANCZOS)
    paste_center(im, pick.rotate(15, Image.BICUBIC, expand=True), 860, 1320)
    paste_center(im, bold("99% FAIL!", 210, fill=(255, 70, 60), stroke=14), W / 2, 330)
    paste_center(im, bold("CAN YOU GET", 110, stroke=10), W / 2, 520)
    paste_center(im, bold("10/10?", 190, fill=YELLOW, stroke=14), W / 2, 680)
    paste_center(im, mc_button("MINECRAFT QUIZ", 640, 110, (60, 150, 60), 40), W / 2, 1420)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_minecraft_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--voice", default="bm_george", help="Kokoro voice, e.g. bm_george, af_heart, am_puck")
    ap.add_argument("--music", default="piano", choices=["piano", "chiptune"])
    args = ap.parse_args()
    scenes, starts, total, worlds, icons = build(args.voice)
    for sc, st in zip(scenes, starts):
        print(f"  {st:6.2f}s  {type(sc).__name__} {getattr(sc, 'idx', '')}")
    print(f"Duration {total:.1f}s")
    if args.cover:
        make_cover(worlds, icons, os.path.join(HERE, "minecraft_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if args.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in args.stills.split(","):
            p = os.path.join(d, f"mc_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    work = os.path.join(mv.CACHE_DIR, "render_mc")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mix(scenes, starts, total, args.music))
    nframes = int(total * FPS)
    n = max(1, args.workers)
    bounds = [round(nframes * k / n) for k in range(n + 1)]
    jobs = [(k, bounds[k], bounds[k + 1], os.path.join(work, f"part{k}.mp4")) for k in range(n)]
    with mp.get_context("fork").Pool(n) as pool:
        parts = pool.map(mv.render_chunk, jobs)
    lst = os.path.join(work, "parts.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", args.out], check=True)
    print(f"Done: {args.out}")


if __name__ == "__main__":
    main()
