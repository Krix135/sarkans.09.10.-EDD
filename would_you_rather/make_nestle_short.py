#!/usr/bin/env python3
"""Satire Short (1080x1920): "Nestlé when AI uses water".

An original hand-built cartoon (no logos, no real people): a smug corporate
character points at an AI data center and complains about wasted water, then
"Meanwhile, Nestlé" cards list real, widely reported facts.

    python3 make_nestle_short.py
    python3 make_nestle_short.py --stills 1,5,12
    python3 make_nestle_short.py --cover
"""

import argparse
import math
import multiprocessing as mp
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_video import (SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, font, highpass,  # noqa: E402
                        lowpass, paste_center, rounded_card, scaled, sfx_pop, sfx_whoosh, soft_circle, text_img, tt)

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
CW, CH = 2160, 2880          # cartoon canvas (wider and taller than the screen, for camera moves)
HORIZON = 1150
COMIC = os.path.join(HERE, "models", "ComicNeue-Bold.ttf")
YELLOW = (255, 222, 40)
INK = (20, 20, 24)

FACTS = [  # tag, main line, small line, narration, camera target (x, y, zoom)
    ("🇺🇸", "MICHIGAN · 2018", "Nestlé got approval to pump 400 gallons of groundwater A MINUTE…",
     "…paying about $200 a year in state fees. Flint, in the same state, was still on bottled water.",
     "In 2018, Michigan let Nestlé pump four hundred gallons of groundwater a minute, "
     "for about two hundred dollars a year in fees.", (850, 1530, 1.25)),
    ("🎙", "2005", "Its boss at the time called the idea of water as a human right “extreme”",
     "He later said he was quoted out of context.",
     "In 2005, its boss at the time called the idea that water is a human right, extreme. "
     "He later said he was taken out of context.", (800, 1560, 1.3)),
    ("🇫🇷", "FRANCE · 2024", "Nestlé admitted using banned filters on its “natural mineral water”",
     "It agreed to pay a €2 million fine to avoid a trial.",
     "In 2024, Nestlé admitted using banned filters on its natural mineral water in France, "
     "and paid two million euros to avoid a trial.", (780, 1500, 1.2)),
    ("🍼", "SINCE 1977", "People have been boycotting Nestlé for almost 50 years…",
     "…over how it marketed baby formula in poorer countries.",
     "And people have been boycotting Nestlé since 1977, over how it marketed baby formula in poorer countries.",
     (830, 1540, 1.28)),
]

K_HOOK, K_AI, K_FACTORY, K_WIDE = (800, 1700, 1.45), (1700, 1080, 1.3), (620, 1600, 1.1), (1080, 1520, 0.72)


# ----------------------------------------------------------------------------
# drawing helpers (draw at 2x, downscale for smooth edges)
# ----------------------------------------------------------------------------
SS = 2


class P:
    def __init__(self, size):
        self.im = Image.new("RGBA", (size[0] * SS, size[1] * SS))
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def s(pts):
        return [(x * SS, y * SS) for x, y in pts]

    def poly(self, pts, fill, outline=INK, width=6):
        self.d.polygon(self.s(pts), fill=fill)
        if outline:
            q = self.s(pts) + [self.s(pts)[0]]
            self.d.line(q, fill=outline, width=width * SS, joint="curve")

    def rect(self, box, fill, outline=INK, width=6, r=0):
        b = [v * SS for v in box]
        if r:
            self.d.rounded_rectangle(b, r * SS, fill=fill, outline=outline, width=width * SS if outline else 0)
        else:
            self.d.rectangle(b, fill=fill, outline=outline, width=width * SS if outline else 0)

    def ellipse(self, box, fill, outline=INK, width=6):
        self.d.ellipse([v * SS for v in box], fill=fill, outline=outline, width=width * SS if outline else 0)

    def line(self, pts, fill=INK, width=6):
        self.d.line(self.s(pts), fill=fill, width=width * SS, joint="curve")

    def thick(self, pts, fill, width, outline=INK, ow=6):
        self.line(pts, outline, width + 2 * ow)
        for x, y in (pts[0], pts[-1]):
            r = (width + 2 * ow) / 2
            self.ellipse((x - r, y - r, x + r, y + r), outline, None)
        self.line(pts, fill, width)
        for x, y in (pts[0], pts[-1]):
            r = width / 2
            self.ellipse((x - r, y - r, x + r, y + r), fill, None)

    def text(self, xy, txt, fnt, fill=INK, anchor="mm", stroke=0, stroke_fill=None):
        f = fnt.font_variant(size=fnt.size * SS)
        self.d.text((xy[0] * SS, xy[1] * SS), txt, font=f, fill=fill, anchor=anchor, stroke_width=stroke * SS,
                    stroke_fill=stroke_fill)

    def done(self):
        return self.im.resize((self.im.width // SS, self.im.height // SS), Image.LANCZOS)


def river_center(y):
    return 1080 + 55 * math.sin((y - HORIZON) / 320)


def river_half(y):
    return 34 + (y - HORIZON) * 0.15


def bottle_poly(cx, cy, ang, s=1.0):
    body = [(-14, -30), (14, -30), (16, -24), (16, 34), (12, 40), (-12, 40), (-16, 34), (-16, -24)]
    neck = [(-7, -42), (7, -42), (10, -30), (-10, -30)]
    cap = [(-8, -52), (8, -52), (8, -42), (-8, -42)]
    c, sn = math.cos(ang), math.sin(ang)

    def tr(p):
        return [(cx + s * (x * c - y * sn), cy + s * (x * sn + y * c)) for x, y in p]
    return tr(body), tr(neck), tr(cap)


def draw_bottle(p, cx, cy, ang, s=1.0):
    body, neck, cap = bottle_poly(cx, cy, ang, s)
    p.poly(neck, (190, 228, 248), (40, 90, 140), 3)
    p.poly(body, (175, 222, 248), (40, 90, 140), 3)
    p.poly(cap, (30, 110, 210), (20, 50, 100), 3)


def gradient_bg():
    y = np.arange(CH)[:, None, None].astype(np.float32)
    x = np.arange(CW)[None, :, None].astype(np.float32)
    w = np.clip((x - 900) / 450, 0, 1)  # 0 = Nestlé side, 1 = AI side
    w = w * w * (3 - 2 * w)
    ty = np.clip(y / HORIZON, 0, 1)
    sky_l = np.array((150, 135, 120)) * (1 - ty) + np.array((205, 185, 160)) * ty
    sky_r = np.array((95, 170, 250)) * (1 - ty) + np.array((200, 232, 255)) * ty
    gy = np.clip((y - HORIZON) / (CH - HORIZON), 0, 1)
    gnd_l = np.array((196, 150, 96)) * (1 - gy) + np.array((150, 104, 62)) * gy
    gnd_r = np.array((128, 205, 92)) * (1 - gy) + np.array((78, 160, 62)) * gy
    sky = sky_l * (1 - w) + sky_r * w
    gnd = gnd_l * (1 - w) + gnd_r * w
    img = np.where(y < HORIZON, sky, gnd)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def draw_scene():
    r = random.Random(4)
    base = gradient_bg()
    p = P((CW, CH))
    # far hills
    hl = [(0, HORIZON)] + [(x, HORIZON - 60 - 40 * math.sin(x / 140)) for x in range(0, 1000, 40)] + [(1000, HORIZON)]
    p.poly(hl, (170, 120, 80), INK, 4)
    hr = [(1150, HORIZON)] + [(x, HORIZON - 80 - 50 * math.sin(x / 170 + 1)) for x in range(1150, 2161, 40)] + \
         [(2160, HORIZON)]
    p.poly(hr, (100, 180, 90), INK, 4)
    # clouds (right) and smog (left)
    for cx, cy, s in ((1500, 330, 1.0), (1950, 520, 0.8), (1250, 640, 0.6)):
        for dx, dy, rr in ((0, 0, 80), (70, 15, 65), (-70, 15, 60), (30, -40, 60)):
            p.ellipse((cx + (dx - rr) * s, cy + (dy - rr) * s, cx + (dx + rr) * s, cy + (dy + rr) * s),
                      (255, 255, 255, 255), None)
    for cx, cy, s in ((250, 300, 1.3), (650, 420, 1.0), (420, 180, 0.9)):
        for dx, dy, rr in ((0, 0, 90), (80, 20, 70), (-80, 25, 70), (20, -45, 70)):
            p.ellipse((cx + (dx - rr) * s, cy + (dy - rr) * s, cx + (dx + rr) * s, cy + (dy + rr) * s),
                      (120, 110, 100, 255), None)
    # cracked dry ground on the Nestlé side
    for _ in range(70):
        x, y = r.uniform(0, 900), r.uniform(HORIZON + 60, CH)
        pts = [(x, y)]
        for _ in range(r.randint(3, 6)):
            x += r.uniform(-60, 60)
            y += r.uniform(-30, 30)
            pts.append((x, y))
        p.line(pts, (120, 82, 50, 255), 3)
    # river (exposed mud on the left bank)
    ys = list(range(HORIZON, CH + 1, 20))
    left = [(river_center(y) - river_half(y), y) for y in ys]
    right = [(river_center(y) + river_half(y), y) for y in ys]
    mud = [(x - 30 - (y - HORIZON) * 0.05, y) for x, y in left]
    p.poly(mud + left[::-1], (130, 95, 60), None)
    p.poly(left + right[::-1], (70, 160, 238), INK, 6)
    # --- AI side ---------------------------------------------------------
    p.rect((1252, 620, 1268, 1180), (235, 235, 240), INK, 4)  # wind turbine pole (blades are animated)
    p.rect((1380, 820, 2080, 1480), (60, 120, 205), INK, 7)
    for gx in range(1410, 2060, 70):
        for gy in range(990, 1460, 70):
            p.rect((gx, gy, gx + 48, gy + 48), (155, 212, 255), (30, 70, 140), 3)
    p.rect((1520, 700, 1940, 820), (255, 255, 255), INK, 7, r=18)
    p.text((1730, 760), "AI", font("Black", 110), (40, 110, 220))
    p.rect((1380, 900, 2080, 970), (30, 60, 130), INK, 5)
    p.text((1730, 935), "DATA CENTER", font("Black", 50), (255, 255, 255))
    for tx in (1300, 1470):  # cooling towers
        tw = [(tx, 1660), (tx + 18, 1560), (tx + 30, 1470), (tx + 130, 1470), (tx + 142, 1560), (tx + 160, 1660)]
        p.poly(tw, (215, 215, 222), INK, 6)
        p.ellipse((tx + 28, 1455, tx + 132, 1488), (90, 90, 100), INK, 5)
    for sx in range(1660, 2120, 120):  # solar panels
        p.poly([(sx, 1700), (sx + 100, 1700), (sx + 120, 1790), (sx + 20, 1790)], (40, 70, 140), INK, 4)
        p.line([(sx + 50, 1700), (sx + 70, 1790)], (120, 160, 230), 2)
    p.thick([(river_center(1880) + river_half(1880) - 10, 1880), (1330, 1820), (1390, 1700)], (170, 170, 180), 16,
            INK, 4)  # small intake pipe: AI uses water too
    for tx, ty, s in ((1250, 2050, 1.0), (1650, 2150, 1.2), (2000, 2000, 1.0), (1450, 2450, 1.3), (1900, 2550, 1.1),
                      (2080, 1600, 0.8)):
        p.rect((tx - 12 * s, ty, tx + 12 * s, ty + 90 * s), (120, 80, 45), INK, 4)
        for dx, dy, rr in ((0, -10, 70), (-50, 20, 50), (50, 20, 50)):
            p.ellipse((tx + (dx - rr) * s, ty + (dy - rr) * s, tx + (dx + rr) * s, ty + (dy + rr) * s),
                      (70, 170, 70), INK, 4)
    for _ in range(60):  # flowers
        fx, fy = r.uniform(1250, 2150), r.uniform(2000, 2880)
        if abs(fx - river_center(fy)) < river_half(fy) + 40:
            continue
        c = r.choice([(255, 90, 120), (255, 220, 60), (255, 255, 255), (180, 120, 255)])
        p.ellipse((fx - 9, fy - 9, fx + 9, fy + 9), c, INK, 2)
    # --- Nestlé side -----------------------------------------------------
    for sx, top in ((140, 480), (290, 540)):  # smokestacks
        p.rect((sx, top, sx + 72, 820), (120, 110, 105), INK, 6)
        for k in range(2):
            p.rect((sx, top + 30 + k * 60, sx + 72, top + 55 + k * 60), (200, 60, 50), INK, 3)
    p.rect((70, 780, 880, 1560), (150, 150, 160), INK, 7)
    p.poly([(70, 780), (200, 690), (330, 780), (460, 690), (590, 780), (720, 690), (880, 780)], (120, 120, 130),
           INK, 6)
    for gx in range(110, 860, 90):
        for gy in (1080, 1200):
            p.rect((gx, gy, gx + 54, gy + 60), (70, 70, 80), INK, 4)
    p.rect((180, 880, 760, 1030), (255, 255, 255), INK, 7, r=14)
    p.text((470, 958), "NESTLÉ", font("Black", 120), INK)
    p.rect((620, 1290, 860, 1560), (90, 140, 200), INK, 6, r=24)  # water tank
    p.text((740, 1425), "WATER", font("Black", 44), (255, 255, 255))
    p.rect((360, 1380, 560, 1560), (40, 40, 48), INK, 6)  # loading door
    p.poly([(380, 1560), (560, 1560), (520, 1830), (300, 1830)], (80, 80, 88), INK, 5)  # conveyor
    for k in range(6):
        y = 1580 + k * 42
        p.line([(380 - k * 13, y), (560 - k * 7, y)], (50, 50, 56), 3)
    # big pipes from the river into the factory, plus the pump
    p.thick([(860, 1380), (960, 1420), (1000, 1560), (river_center(1700) - 10, 1700)], (165, 165, 175), 44)
    p.thick([(860, 1480), (930, 1520), (950, 1700), (river_center(1880) - 25, 1880)], (165, 165, 175), 44)
    p.rect((880, 1600, 990, 1690), (230, 80, 60), INK, 6, r=10)
    p.text((935, 1645), "PUMP\n24/7", font("Black", 24), (255, 255, 255))
    # pile of bottles
    pile = []
    for _ in range(120):
        u = r.random()
        y = 1850 + u * 430
        half = 60 + u * 230
        x = 330 + r.uniform(-half, half)
        pile.append((y, x, r.uniform(-1.6, 1.6)))
    for y, x, a in sorted(pile):
        draw_bottle(p, x, y, a, 1.0)
    p.rect((70, 1640, 290, 1760), (255, 245, 210), INK, 6, r=10)  # price sign
    p.text((180, 1685), "$4.99", font("Black", 56), (210, 40, 40))
    p.text((180, 1735), "PER BOTTLE", font("Black", 22), INK)
    p.rect((172, 1760, 188, 1850), (120, 80, 45), INK, 4)
    # dead tree
    p.line([(120, 2650), (120, 2420), (70, 2340)], (110, 75, 45), 14)
    p.line([(120, 2480), (180, 2390), (230, 2370)], (110, 75, 45), 10)
    p.line([(120, 2420), (90, 2300)], (110, 75, 45), 8)
    # --- the CEO character (generic, not a real person) -----------------
    cx = 720
    p.rect((688, 1990, 712, 2180), INK, None)
    p.rect((728, 1990, 752, 2180), INK, None)
    p.ellipse((678, 2165, 730, 2195), INK, None)
    p.ellipse((722, 2165, 780, 2195), INK, None)
    p.poly([(650, 1850), (790, 1850), (775, 2005), (665, 2005)], (34, 34, 42), INK, 5)
    p.poly([(705, 1850), (735, 1850), (720, 1915)], (255, 255, 255), None)
    p.poly([(715, 1858), (725, 1858), (730, 1930), (720, 1945), (710, 1930)], (210, 30, 40), INK, 2)
    p.rect((742, 1885, 778, 1905), (255, 255, 255), INK, 2)
    p.text((760, 1895), "CEO", font("Black", 13), INK)
    p.thick([(656, 1862), (632, 1990)], (34, 34, 42), 22, INK, 4)
    p.ellipse((618, 1980, 646, 2008), (255, 255, 255), INK, 4)
    p.thick([(785, 1866), (900, 1810)], (34, 34, 42), 22, INK, 4)   # pointing arm
    p.ellipse((892, 1790, 926, 1824), (255, 255, 255), INK, 4)
    p.thick([(918, 1803), (968, 1788)], (255, 255, 255), 8, INK, 3)  # pointing finger
    p.ellipse((cx - 85, 1680, cx + 85, 1850), (255, 255, 255), INK, 6)  # head
    p.line([(cx + 5, 1735), (cx + 35, 1748)], INK, 7)    # smug eyebrows
    p.line([(cx + 55, 1748), (cx + 82, 1735)], INK, 7)
    p.line([(cx + 12, 1760), (cx + 34, 1762)], INK, 8)   # half-closed eyes
    p.line([(cx + 56, 1762), (cx + 78, 1760)], INK, 8)
    p.d.chord([v * SS for v in (cx + 2, 1772, cx + 80, 1822)], 0, 180, fill=(255, 255, 255), outline=INK,
              width=5 * SS)
    p.line([(cx + 8, 1797), (cx + 76, 1797)], INK, 3)
    base.alpha_composite(p.done())
    return base


def bubble_sprite(lines=("LOOK, THEY'RE", "WASTING WATER!")):
    w, h = 560, 210
    p = P((w + 40, h + 110))
    p.ellipse((20, 10, w + 20, h + 10), (255, 255, 255), INK, 6)
    p.poly([(150, h - 15), (230, h - 5), (110, h + 95)], (255, 255, 255), None)
    p.line([(150, h - 7), (110, h + 95), (232, h + 2)], INK, 6)
    size = 58
    while max(ImageFont.truetype(COMIC, size).getlength(ln) for ln in lines) > w - 70:
        size -= 2
    for i, ln in enumerate(lines):
        p.text((w / 2 + 20, 80 + i * 66), ln, ImageFont.truetype(COMIC, size), INK)
    return p.done()


# ----------------------------------------------------------------------------
# audio
# ----------------------------------------------------------------------------

def sfx_scratch():
    t = tt(0.5)
    f = 250 + 1100 * np.abs(np.sin(2 * np.pi * 2.6 * t))
    ph = np.cumsum(f) / SR
    saw = 2 * (ph % 1) - 1
    n = highpass(np.random.default_rng(3).standard_normal(len(t)), 1200)
    s = (0.55 * saw + 0.45 * n) * np.exp(-t * 3.5)
    return lowpass(s, 4500) * 0.6


# ----------------------------------------------------------------------------
# the Short
# ----------------------------------------------------------------------------

def bold(text, size, fill=(255, 255, 255), stroke=9, max_w=None):
    while max_w and font("Black", size).getlength(text) + 2 * stroke > max_w and size > 28:
        size -= 2
    return text_img(text, font("Black", size), fill=fill, stroke=stroke, stroke_fill=(0, 0, 0))


def wrap_lines(text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if fnt.getlength(test) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def fact_card(i, fact):
    icon, tag, main, small = fact[:4]
    cw = 880
    fm, fs = font("Black", 54), font("Bold", 38, display=False)
    ml, sl = wrap_lines(main, fm, cw - 90), wrap_lines(small, fs, cw - 90)
    ch = 150 + len(ml) * 64 + 24 + len(sl) * 48 + 40
    card = rounded_card(cw, ch, 34, (255, 255, 255, 255), outline=(20, 20, 24, 255), width=7)
    d = ImageDraw.Draw(card)
    e = emoji(icon, 60)
    card.alpha_composite(e, (44, 40))
    d.text((44 + e.width + 18, 70), tag, font=font("Black", 40), fill=(210, 40, 40), anchor="lm")
    d.text((cw - 44, 70), f"{i + 1}/4", font=font("Black", 34), fill=(140, 140, 150), anchor="rm")
    y = 130
    for ln in ml:
        d.text((45, y), ln, font=fm, fill=INK)
        y += 64
    y += 24
    for ln in sl:
        d.text((45, y), ln, font=fs, fill=(80, 80, 90))
        y += 48
    out = Image.new("RGBA", (cw + 40, ch + 40))
    sh = rounded_card(cw, ch, 34, (0, 0, 0, 150))
    out.alpha_composite(sh, (14, 26))
    out = out.filter(ImageFilter.GaussianBlur(10))
    out.alpha_composite(card, (0, 0))
    return out


REACTIONS = [("💀", "😳"), ("🤡", "💀"), ("😳", "🧐"), ("💀", "😬")]
CARD_Y = 700
HEAD = (720, 1765)


def chunks(text, n=3):
    words = text.replace("A.I.", "AI").split()
    return [" ".join(words[i:i + n]) for i in range(0, len(words), n)]


class Short(mv.Scene):
    def __init__(self, scene, tts, ceo):
        super().__init__()
        self.scene = scene
        self.bubble = bubble_sprite()
        self.bubble2 = bubble_sprite(("ANYWAY… WANNA", "BUY SOME WATER?"))
        self.puff = soft_circle(120, (255, 255, 255, 255), 14)
        self.smog = soft_circle(120, (110, 100, 95, 255), 16)
        self.bottle = self._bottle_sprite()
        self.subs = []
        K = []

        def narrate(at, text, speed=1.1, subs=True):
            v = tts.say(text, speed=speed)
            self.voices.append((at, v))
            if subs:
                parts = chunks(text)
                total = sum(len(p) + 3 for p in parts)
                tt0, dur = at, len(v) / SR
                for p in parts:
                    d = dur * (len(p) + 3) / total
                    self.subs.append((tt0, tt0 + d, p))
                    tt0 += d
            return len(v) / SR

        # 1) hook: the CEO line straight away
        self.t_bubble = 0.05
        c1 = ceo.say("Look, they're wasting water!", speed=1.0)
        self.voices.append((0.15, c1))
        self.sounds += [(0.0, mq.sfx_boom(), 0.6), (self.t_bubble, sfx_pop(), 1.0)]
        self.t_ai = 0.15 + len(c1) / SR + 0.25
        K += [(0.0, K_HOOK), (self.t_ai, K_HOOK), (self.t_ai + 0.9, K_AI)]
        # 2) to be fair...
        self.sounds.append((self.t_ai, sfx_whoosh(0.6), 0.8))
        d = narrate(self.t_ai + 0.2, "Okay, to be fair... A.I. data centers really do use a lot of water to stay cool.")
        self.t_mean = self.t_ai + 0.2 + d + 0.25
        K += [(self.t_mean, K_AI), (self.t_mean + 0.6, K_FACTORY)]
        # 3) meanwhile
        d = narrate(self.t_mean + 0.3, "Meanwhile... Nestlé.", speed=1.0, subs=False)
        self.sounds += [(self.t_mean, sfx_scratch(), 1.0), (self.t_mean + 0.3, mq.sfx_boom(), 0.8)]
        t = self.t_mean + 0.3 + d + 0.3
        self.punches = [self.t_mean + 0.3]
        self.facts = []
        for i, f in enumerate(FACTS):
            d = narrate(t + 0.25, f[4], subs=False)
            self.sounds += [(t, mq.sfx_boom(), 0.9), (t, sfx_whoosh(0.3), 0.5), (t + 0.55, mq.sfx_crunch(), 1.0),
                            (t + 0.62, sfx_pop(), 0.7)]
            dur = 0.25 + d + 0.5
            self.facts.append((t, t + dur, fact_card(i, f)))
            self.punches.append(t + 0.55)
            K.append((t + 0.5, f[5]))
            t += dur
        self.t_end = t
        # 4) the conclusion, wide shot
        K += [(t, FACTS[-1][5]), (t + 1.0, K_WIDE)]
        self.sounds += [(t, sfx_whoosh(0.6), 0.8)]
        d = narrate(t + 0.4, "So yes, A.I. uses water. But only one of them bottles it... and sells it back to you.")
        self.t_ceo2 = t + 0.4 + d + 0.25
        # 5) punchline: back on the CEO (loops into the first frame)
        K += [(self.t_ceo2, K_WIDE), (self.t_ceo2 + 0.7, K_HOOK)]
        c2 = ceo.say("Anyway... wanna buy some water?", speed=1.0)
        self.voices.append((self.t_ceo2 + 0.6, c2))
        self.sounds += [(self.t_ceo2, sfx_whoosh(0.5), 0.8), (self.t_ceo2 + 0.5, sfx_pop(), 1.0),
                        (self.t_ceo2 + 0.9, mq.sfx_pling(), 0.6)]
        self.dur = self.t_ceo2 + 0.6 + len(c2) / SR + 1.3
        K.append((self.dur, K_HOOK))
        self.keys = K
        # sprites
        self.cap1 = [bold("NESTLÉ WHEN", 92), bold("AI USES WATER:", 92, fill=YELLOW)]
        self.sat = mq.mc_button("SATIRE", 220, 64, (200, 40, 40), 26)
        self.cap_mean = bold("MEANWHILE, NESTLÉ:", 110, fill=YELLOW, stroke=11, max_w=1000)
        self.end1 = [bold("BOTH USE WATER.", 92), bold("ONLY ONE BOTTLES IT", 80, fill=YELLOW),
                     bold("& SELLS IT BACK TO YOU.", 70, fill=YELLOW, max_w=1000)]
        self.cta = self._with_emoji(bold("WHO'S WORSE?", 92), "🤔", 88)
        self.cta2 = self._with_emoji(bold("COMMENT BELOW", 66, stroke=7), "👇", 80)
        self.note = text_img("Satire · facts & sources in the description", font("Bold", 32, display=False),
                             fill=(235, 235, 240))
        fw = int(font("Black", 56).getlength("FACT"))
        st = rounded_card(fw + 130, 96, 22, (255, 255, 255, 235), outline=(30, 160, 70, 255), width=8)
        ImageDraw.Draw(st).text((28, 48), "FACT", font=font("Black", 56), fill=(30, 160, 70), anchor="lm")
        st.alpha_composite(emoji("✅", 56), (fw + 46, 20))
        self.stamp = st.rotate(-10, Image.BICUBIC, expand=True)
        self.react = [(emoji(a, 110), emoji(b, 110)) for a, b in REACTIONS]
        self._txt = {}

    @staticmethod
    def _with_emoji(txt, e, size):
        em = emoji(e, size)
        out = Image.new("RGBA", (txt.width + em.width + 10, max(txt.height, em.height)))
        out.alpha_composite(txt, (0, (out.height - txt.height) // 2))
        out.alpha_composite(em, (txt.width + 10, (out.height - em.height) // 2))
        return out

    @staticmethod
    def _bottle_sprite():
        p = P((80, 120))
        draw_bottle(p, 40, 62, 0.0, 1.0)
        return p.done()

    def sub_img(self, text):
        if text not in self._txt:
            self._txt[text] = bold(text.upper(), 76, stroke=9, max_w=1000)
        return self._txt[text]

    def counter_img(self, n):
        key = ("c", n)
        if key not in self._txt:
            card = rounded_card(860, 170, 30, (12, 18, 40, 230), outline=(90, 170, 255, 255), width=5)
            d = ImageDraw.Draw(card)
            d.text((430, 34), "AT NESTLÉ'S 2018 PERMIT (400 GAL/MIN), THAT'S", font=font("Bold", 26, display=False),
                   fill=(190, 215, 255), anchor="mm")
            e = emoji("💧", 64)
            num = f"{n:,} GALLONS"
            f = font("Black", 70)
            w = f.getlength(num)
            x0 = 430 - (w + e.width + 14) / 2
            card.alpha_composite(e, (int(x0), 62))
            d.text((x0 + e.width + 14, 96), num, font=f, fill=YELLOW, anchor="lm")
            d.text((430, 148), "pumped since this video started", font=font("Bold", 24, display=False),
                   fill=(190, 215, 255), anchor="mm")
            self._txt[key] = card
        return self._txt[key]

    # camera ---------------------------------------------------------------
    def cam(self, t):
        ks = self.keys
        c = ks[-1][1]
        for (t0, a), (t1, b) in zip(ks, ks[1:]):
            if t <= t1:
                k = clamp((t - t0) / max(1e-6, t1 - t0))
                k = k * k * (3 - 2 * k)
                c = tuple(a[i] + (b[i] - a[i]) * k for i in range(3))
                break
        x, y, z = c
        z *= 1 + 0.015 * math.sin(t * 0.9)
        sx = sy = 0.0
        for p in self.punches:  # zoom punch + shake on every slam
            if 0 <= t - p < 0.35:
                k = 1 - (t - p) / 0.35
                z *= 1 + 0.07 * k
                sx += 18 * k * math.sin((t - p) * 90)
                sy += 14 * k * math.cos((t - p) * 75)
        vw, vh = W / z, H / z
        x0 = min(max(x - vw / 2 + sx, 0), CW - vw)
        y0 = min(max(y - vh / 2 + sy, 0), CH - vh)
        return x0, y0, z

    def facts_shown(self, t):
        return sum(1 for t0, _, _ in self.facts if t >= t0 + 0.4)

    def draw_ceo(self, im, S, z, t):
        lvl = self.facts_shown(t)
        d = ImageDraw.Draw(im)
        cx, cy = HEAD
        if lvl >= 2:  # smug face turns nervous
            x1, y1 = S(cx + 2, 1722)
            x2, y2 = S(cx + 82, 1826)
            d.rounded_rectangle((x1, y1, x2, y2), radius=20 * z, fill=(255, 255, 255))
            w = max(2, int(6 * z))
            for a, b in (((cx + 8, 1742), (cx + 32, 1728)), ((cx + 58, 1728), (cx + 82, 1742))):
                d.line((S(*a), S(*b)), fill=INK, width=w)
            for ex in (cx + 22, cx + 68):
                px, py = S(ex, 1760)
                d.ellipse((px - 7 * z, py - 7 * z, px + 7 * z, py + 7 * z), fill=INK)
            pts = [S(cx + 18 + k * 9, 1802 + (6 if k % 2 else -6)) for k in range(7)]
            d.line(pts, fill=INK, width=w)
        for k, (dx, dy) in enumerate(((-72, -40), (86, -58), (-88, 12), (84, 18))[:lvl]):
            drip = ((t * 45 + k * 13) % 34)
            px, py = S(cx + dx, cy + dy + drip)
            r = 11 * z
            d.polygon([(px, py - 2.2 * r), (px - r, py), (px + r, py)], fill=(130, 205, 255))
            d.ellipse((px - r, py - r, px + r, py + r), fill=(130, 205, 255), outline=INK, width=max(1, int(2 * z)))

    def render(self, t):
        x0, y0, z = self.cam(t)
        im = self.scene.crop((int(x0), int(y0), int(x0 + W / z), int(y0 + H / z))).resize((W, H), Image.BILINEAR)

        def S(x, y):
            return (x - x0) * z, (y - y0) * z
        d = ImageDraw.Draw(im)
        for k in range(22):  # river shimmer
            y = HORIZON + ((t * 140 + k * 80) % (CH - HORIZON))
            off = ((k * 37) % 10 / 10 - 0.5) * 1.2 * river_half(y)
            sx, sy = S(river_center(y) + off, y)
            d.line((sx - 14 * z, sy, sx + 14 * z, sy), fill=(220, 240, 255, 255), width=max(2, int(4 * z)))
        pipes = [[(river_center(1700) - 10, 1700), (1000, 1560), (960, 1420), (860, 1380)],
                 [(river_center(1880) - 25, 1880), (950, 1700), (930, 1520), (860, 1480)]]
        for pi, pts in enumerate(pipes):  # water being sucked up the pipes
            segs = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
            L = sum(segs)
            for k in range(7):
                s = ((t * 0.45 + k / 7 + pi * 0.07) % 1) * L
                for (a, b), sl in zip(zip(pts, pts[1:]), segs):
                    if s <= sl:
                        q = s / sl
                        wx, wy = a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q
                        if 868 < wx < 1002 and 1588 < wy < 1702:
                            break
                        px, py = S(wx, wy)
                        r = 9 * z
                        d.ellipse((px - r, py - r, px + r, py + r), fill=(90, 175, 245, 255))
                        break
                    s -= sl
        for k in range(10):  # smog and steam
            for (sx, sy), spr, drift in (((176, 470), self.smog, -25), ((326, 530), self.smog, -25),
                                         ((1380, 1450), self.puff, 18), ((1550, 1450), self.puff, 18)):
                age = (t * 0.5 + k / 10) % 1
                px, py = S(sx + drift * age * 6, sy - age * 320)
                paste_center(im, scaled(spr, (0.5 + 1.3 * age) * z), px, py, 0.75 * (1 - age))
        bx, by = 1260, 620  # wind turbine
        for k in range(3):
            a = t * 1.8 + k * 2 * math.pi / 3
            tip = (bx + 115 * math.cos(a), by + 115 * math.sin(a))
            side = (bx + 30 * math.cos(a + 0.35), by + 30 * math.sin(a + 0.35))
            d.polygon([S(bx, by), S(*side), S(*tip)], fill=(245, 245, 250, 255), outline=INK)
        hx, hy = S(bx, by)
        d.ellipse((hx - 12 * z, hy - 12 * z, hx + 12 * z, hy + 12 * z), fill=(200, 200, 210), outline=INK)
        for k in range(14):
            if int(t * 3 + k * 1.7) % 3:
                lx, ly = S(1420 + (k % 7) * 92, 1440 - (k // 7) * 380)
                d.ellipse((lx - 6 * z, ly - 6 * z, lx + 6 * z, ly + 6 * z), fill=(120, 255, 140, 255))
        q = (t / 1.3) % 1
        bxp, byp = S(470 - 90 * q, 1560 + 270 * q)
        paste_center(im, scaled(self.bottle, z), bxp, byp)
        self.draw_ceo(im, S, z, t)
        # speech bubbles
        px, py = S(850, 1540)
        if t < self.t_mean + 0.4:
            k = ease_out_back((t - self.t_bubble) / 0.25)
            paste_center(im, scaled(self.bubble, k * z * 0.95), px, py, 1 - clamp((t - self.t_mean) / 0.4))
        if t >= self.t_ceo2 + 0.5:
            paste_center(im, scaled(self.bubble2, ease_out_back((t - self.t_ceo2 - 0.5) / 0.25) * z * 0.95), px, py)
        # captions ----------------------------------------------------------
        if t < self.t_ai + 0.3:
            a = 1 - clamp((t - self.t_ai) / 0.3)
            for i, c in enumerate(self.cap1):
                paste_center(im, scaled(c, ease_out_back((t + 0.2 - 0.1 * i) / 0.25)), W / 2, 250 + i * 105, a)
            paste_center(im, scaled(self.sat, ease_out_back((t - 0.15) / 0.25)), W / 2, 470, a)
        f0 = self.facts[0][0]
        if self.t_mean <= t < self.t_end + 0.3:
            dim = clamp((t - f0 + 0.3) / 0.3) * (1 - clamp((t - self.t_end) / 0.3))
            if dim > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(110 * dim))))
            if t < f0 + 0.5:
                s = 1 + 1.2 * (1 - ease_out_cubic((t - self.t_mean - 0.3) / 0.18))
                a = clamp((t - self.t_mean - 0.3) / 0.08) * (1 - clamp((t - f0 - 0.2) / 0.3))
                paste_center(im, scaled(self.cap_mean, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 280, a)
            else:
                k = ease_out_back((t - f0 - 0.5) / 0.3) * (1 - ease_in_cubic((t - self.t_end) / 0.3))
                paste_center(im, scaled(self.counter_img(int(t * 400 / 60)), k), W / 2, 285)
            for i, (t0, t1, card) in enumerate(self.facts):
                if t0 - 0.05 <= t < t1:
                    kin = ease_out_back((t - t0) / 0.35)
                    kout = ease_in_cubic((t - (t1 - 0.25)) / 0.25)
                    x = W / 2 + (1 - kin) * W - kout * W
                    rot = 1.5 * math.sin(t0 * 7)
                    paste_center(im, card.rotate(rot, Image.BICUBIC, expand=True), x, CARD_Y)
                    if t >= t0 + 0.55:
                        s = 1 + 1.3 * (1 - ease_out_cubic((t - t0 - 0.55) / 0.16))
                        paste_center(im, scaled(self.stamp, s), x + card.width / 2 - 150,
                                     CARD_Y + card.height / 2 - 30, clamp((t - t0 - 0.55) / 0.06))
                    for j, e in enumerate(self.react[i]):
                        if t >= t0 + 0.65 + 0.12 * j:
                            k = ease_out_back((t - t0 - 0.65 - 0.12 * j) / 0.3)
                            ex = 120 if j == 0 else 960
                            ey = CARD_Y - card.height / 2 - 30 + 10 * math.sin(t * 6 + j)
                            paste_center(im, scaled(e, k).rotate(12 * math.sin(t * 5 + j), Image.BICUBIC, expand=True),
                                         x - W / 2 + ex, ey, 1 - kout)
        if self.t_end + 0.3 <= t < self.t_ceo2 + 0.4:
            te = t - self.t_end - 0.3
            a = 1 - clamp((t - self.t_ceo2) / 0.4)
            im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(100 * clamp(te / 0.4) * a))))
            for i, c in enumerate(self.end1):
                paste_center(im, scaled(c, ease_out_back((te - 0.2 - 0.7 * i) / 0.35)), W / 2, 250 + i * 105, a)
        if t >= self.t_ceo2 + 0.7:
            tc = t - self.t_ceo2 - 0.7
            paste_center(im, scaled(self.cta, ease_out_back(tc / 0.35) * (1 + 0.03 * math.sin(t * 7))), W / 2, 260)
            paste_center(im, scaled(self.cta2, ease_out_back((tc - 0.25) / 0.35)), W / 2, 372)
            paste_center(im, self.note, W / 2, 460, clamp((tc - 0.4) / 0.3))
        for s0, s1, text in self.subs:  # pop-in subtitles
            if s0 <= t < s1:
                k = 1 + 0.18 * (1 - ease_out_cubic((t - s0) / 0.12))
                paste_center(im, scaled(self.sub_img(text), k), W / 2, 1400)
        return im


def build():
    print("Drawing the cartoon ...", flush=True)
    scene = draw_scene()
    tts = mv.TTS("am_onyx", "en-us")
    ceo = mv.TTS("bm_lewis", "en-gb")
    sc = Short(scene, tts, ceo)
    return [sc], [0.0], sc.dur, scene


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_nestle_satire.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    scenes, starts, total, scene = build()
    sc = scenes[0]
    print(f"Duration {total:.1f}s  (AI {sc.t_ai:.1f}, meanwhile {sc.t_mean:.1f}, CEO again {sc.t_ceo2:.1f}, "
          f"facts {[round(f[0], 1) for f in sc.facts]}, end {sc.t_end:.1f})")
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.cover:
        sc.cap1, sc.sat, sc.subs = [], Image.new("RGBA", (1, 1)), []  # cover gets its own, bigger title
        im = sc.render(0.9)
        paste_center(im, bold("NESTLÉ WHEN", 120, stroke=12), W / 2, 250)
        paste_center(im, bold("AI USES WATER", 120, fill=YELLOW, stroke=12), W / 2, 380)
        p = os.path.join(HERE, "nestle_satire_cover.jpg")
        im.convert("RGB").save(p, quality=92)
        print(p)
        return
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"nes_{float(s):06.2f}.png")
            sc.render(float(s)).convert("RGB").save(p)
            print(p)
        return
    work = os.path.join(mv.CACHE_DIR, "render_nestle")
    os.makedirs(work, exist_ok=True)
    for f in os.listdir(work):
        os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mq.mix(scenes, starts, total, "piano"))
    nframes = int(total * FPS)
    n = max(1, a.workers)
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
                    "-movflags", "+faststart", "-shortest", a.out], check=True)
    print(f"Done: {a.out}")


if __name__ == "__main__":
    main()
