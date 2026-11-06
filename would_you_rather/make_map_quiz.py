#!/usr/bin/env python3
""""name this country" spinning-globe quiz Short (1080x1920), fast 3.5 s rhythm.

Each country: the globe zooms out, spins and zooms in (with zoom blur), the
country glows, a thin timer drains white -> cyan -> pink with three ticks,
letter tiles show how long the name is (first letter on hard ones), then the
country lifts off the map, the flag fills it, letters pop into the tiles and
confetti in the flag's colours bursts out. 10 countries + a bonus, difficulty
banners, and an ending that loops back into the first frame.
Borders: Natural Earth 1:50m (public domain). Flags: public domain.

    python3 make_map_quiz.py
    python3 make_map_quiz.py --stills 0,1,2,2.9
    python3 make_map_quiz.py --cover
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
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import globe as G  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_video import (SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center,  # noqa: E402
                        rounded_card, scaled, text_img)

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
FONT = os.path.join(HERE, "models", "Fredoka.ttf")
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/fredoka/Fredoka%5Bwdth%2Cwght%5D.ttf"
FLAG_DIR = os.path.join(HERE, "flags")
CENTER = (540, 860)
INK = (34, 18, 52)
CYAN, PINK, VIOLET, GOLD, RED = (90, 225, 255), (255, 90, 170), (175, 120, 255), (255, 205, 60), (255, 70, 70)
FLY, DRAIN0, HINT = 1.0, 1.0, 1.75
TILE_Y, FACT_Y = 1292, 1405
START_LON, START_LAT = -25, 30
START_VIEW = (G.unit(START_LON, START_LAT), 620.0)
EPISODE = 1
TIERS = {"EASY": (CYAN, "😎"), "MEDIUM": (VIOLET, "🤔"), "HARD": (PINK, "😳"), "INSANE": (RED, "💀"),
         "BONUS": (GOLD, "😱")}

COUNTRIES = [  # episode 1: map code, flag, name, fun fact, fact emoji, tier (none are in the reference video)
    ("ITA", "IT", "ITALY", "more UNESCO sites than any other country", "🏛", "EASY"),
    ("GBR", "GB", "UNITED KINGDOM", "nowhere is more than 113 km from the sea", "🌊", "EASY"),
    ("MEX", "MX", "MEXICO", "parts of its capital sink 50 cm a year", "🏙", "EASY"),
    ("EGY", "EG", "EGYPT", "95% of people live along the Nile", "🏜", "MEDIUM"),
    ("CHL", "CL", "CHILE", "4,300 km long, only 177 km wide on average", "📏", "MEDIUM"),
    ("TUR", "TR", "TURKEY", "its biggest city sits on two continents", "🌉", "MEDIUM"),
    ("MDG", "MG", "MADAGASCAR", "90% of its wildlife lives nowhere else", "🦎", "HARD"),
    ("NZL", "NZ", "NEW ZEALAND", "about 5 sheep for every person", "🐑", "HARD"),
    ("MNG", "MN", "MONGOLIA", "the emptiest country on Earth", "🐎", "HARD"),
    ("KAZ", "KZ", "KAZAKHSTAN", "the biggest landlocked country on Earth", "🗺", "INSANE"),
    ("LSO", "LS", "LESOTHO", "it's completely surrounded by South Africa", "🤯", "BONUS"),
]

COUNTRIES_2 = [  # episode 2: none of these are in the reference video or in episode 1
    ("FRA", "FR", "FRANCE", "the most visited country on Earth", "🗼", "EASY"),
    ("ESP", "ES", "SPAIN", "home to the world's oldest restaurant", "🍽", "EASY"),
    ("CHN", "CN", "CHINA", "the whole country uses just one time zone", "🕐", "EASY"),
    ("GRC", "GR", "GREECE", "it has about 6,000 islands", "🏝", "MEDIUM"),
    ("VNM", "VN", "VIETNAM", "the world's 2nd-biggest coffee grower", "☕", "MEDIUM"),
    ("PER", "PE", "PERU", "the potato was first farmed here", "🥔", "MEDIUM"),
    ("UKR", "UA", "UKRAINE", "the biggest country fully inside Europe", "🌻", "HARD"),
    ("ISL", "IS", "ICELAND", "about 11% of it is covered by glaciers", "🧊", "HARD"),
    ("SAU", "SA", "SAUDI ARABIA", "it has no permanent rivers at all", "🏜", "HARD"),
    ("PNG", "PG", "PAPUA NEW GUINEA", "over 800 languages are spoken here", "🗣", "INSANE"),
    ("BTN", "BT", "BHUTAN", "it measures Gross National Happiness", "😊", "BONUS"),
]

EPISODES = {  # countries, start view (lon, lat), cover (country, view lon/lat, zoom factor), file suffix
    1: (COUNTRIES, (-25, 30), ("MDG", (32, -14), None), ""),
    2: (COUNTRIES_2, (75, 22), ("VNM", (103, 13), 0.62), "_2"),
}


def set_episode(ep):
    global COUNTRIES, START_LON, START_LAT, START_VIEW, EPISODE
    EPISODE = ep
    COUNTRIES, (START_LON, START_LAT) = EPISODES[ep][0], EPISODES[ep][1]
    START_VIEW = (G.unit(START_LON, START_LAT), 620.0)

_f = {}


def rfont(size, weight="Bold"):
    if not os.path.exists(FONT):
        import urllib.request
        os.makedirs(os.path.dirname(FONT), exist_ok=True)
        urllib.request.urlretrieve(FONT_URL, FONT)
    key = (size, weight)
    if key not in _f:
        f = ImageFont.truetype(FONT, size)
        f.set_variation_by_name(weight)
        _f[key] = f
    return _f[key]


def rtext(text, size, fill=(255, 255, 255), stroke=None, weight="Bold"):
    return text_img(text, rfont(size, weight), fill=fill, stroke=stroke if stroke is not None else max(4, size // 11),
                    stroke_fill=INK)


def join(*parts, gap=12):
    h = max(p.height for p in parts)
    out = Image.new("RGBA", (sum(p.width for p in parts) + gap * (len(parts) - 1), h))
    x = 0
    for p in parts:
        out.alpha_composite(p, (x, (h - p.height) // 2))
        x += p.width + gap
    return out


def zoom_blur(im, b):
    """Cheap radial zoom blur around the globe centre (b = 0..1)."""
    if b < 0.05:
        return im
    s = 1 + 0.045 * b
    big = im.resize((int(W * s), int(H * s)), Image.BILINEAR)
    x0, y0 = int(CENTER[0] * s - CENTER[0]), int(CENTER[1] * s - CENTER[1])
    return Image.blend(im, big.crop((x0, y0, x0 + W, y0 + H)), 0.4 * b)


def flag_colours(flag):
    q = flag.convert("RGB").resize((90, 60)).quantize(6)
    pal = q.getpalette()
    total = 90 * 60
    cols = [tuple(pal[i * 3:i * 3 + 3]) for n, i in sorted(q.getcolors(), reverse=True) if n > 0.04 * total]
    return cols or [(255, 255, 255)]


class Camera:
    """Zoom out to the whole planet, spin, zoom in; then a slow push-in."""

    def __init__(self, a, b, fly=FLY, q_len=3.5):
        (self.ca, self.Ra), (self.cb, self.Rb) = a, b
        self.Rmid = min(620.0, self.Ra, self.Rb)
        self.fly, self.q_len = fly, q_len

    def at(self, t):
        if t < self.fly:
            k = clamp(t / self.fly)
            e = k * k * (3 - 2 * k)
            c = G.slerp(self.ca, self.cb, e)
            la, lb, lm = math.log(self.Ra), math.log(self.Rb), math.log(self.Rmid)
            if k < 0.5:  # out for the first half, in for the second
                R = math.exp(la + (lm - la) * ease_out_cubic(k / 0.5))
            else:
                R = math.exp(lm + (lb - lm) * ease_out_cubic((k - 0.5) / 0.5))
            return c, R, math.sin(math.pi * k) * min(1.0, abs(lb - la) / 1.5 + 0.4)
        return self.cb, self.Rb * (1 + 0.07 * clamp((t - self.fly) / (self.q_len - self.fly))), 0.0


class Tiles:
    """Wordle-style letter tiles for the country's name."""

    def __init__(self, name, show_first):
        self.name, self.show_first = name, show_first
        n = sum(ch != " " for ch in name)
        g = name.count(" ")
        self.T = int(min(84, 880 / (1.12 * n + 0.55 * g)))
        T = self.T
        self.blank = rounded_card(T, T, T // 5, INK + (215,), outline=CYAN + (255,), width=3)
        self.done = rounded_card(T, T, T // 5, (255, 255, 255, 255), outline=INK + (255,), width=4)
        f = rfont(int(T * 0.68))
        self.letter, self.hint = {}, {}
        for ch in set(name.replace(" ", "")):
            a = self.done.copy()
            ImageDraw.Draw(a).text((T / 2, T / 2 + 2), ch, font=f, fill=INK, anchor="mm")
            self.letter[ch] = a
            b = self.blank.copy()
            ImageDraw.Draw(b).text((T / 2, T / 2 + 2), ch, font=f, fill=CYAN, anchor="mm")
            self.hint[ch] = b
        self.pos = []
        x = 0.0
        for ch in name:
            if ch == " ":
                x += 0.55 * T
                continue
            self.pos.append((ch, x + T / 2))
            x += 1.12 * T
        self.width = x - 0.12 * T

    def draw(self, im, t_hint, t_reveal):
        x0 = W / 2 - self.width / 2
        for i, (ch, x) in enumerate(self.pos):
            k_in = ease_out_back((t_hint - 0.02 * i) / 0.25)
            if k_in <= 0.01:
                continue
            tr = t_reveal - 0.035 * i
            if tr > 0:  # flip: squash to a line, then open as the solved tile
                if tr < 0.07:
                    img, sy = self.blank, 1 - tr / 0.07
                else:
                    img, sy = self.letter[ch], ease_out_back((tr - 0.07) / 0.15)
            else:
                img = self.hint[ch] if (i == 0 and self.show_first) else self.blank
                sy = 1.0
            sy = max(0.05, sy) * min(1.0, k_in)
            tile = img.resize((max(1, int(self.T * min(1.0, k_in))), max(1, int(self.T * sy))), Image.BILINEAR)
            paste_center(im, tile, x0 + x, TILE_Y)


class Question(mv.Scene):
    def __init__(self, idx, q, prev_view, globe, ui, prev_tier):
        super().__init__()
        code, fcode, name, fact, femoji, tier = q
        self.idx, self.globe, self.ui, self.tier = idx, globe, ui, tier
        self.bonus = tier == "BONUS"
        self.dur = 4.7 if self.bonus else 3.5
        self.reveal = 3.75 if self.bonus else 2.65
        c, self.near, _ = globe.world.country(code)
        self.view = (c, G.zoom_for(globe.world, c, self.near, W, H, 0.36, 0.22))
        self.cam = Camera(prev_view, self.view, FLY, self.dur)
        self.flag = Image.open(os.path.join(FLAG_DIR, fcode + ".png")).convert("RGBA")
        self.cols = flag_colours(self.flag)
        self.tiles = Tiles(name, tier in ("HARD", "INSANE", "BONUS"))
        size = 42
        while rfont(size).getlength(fact) > 760 and size > 26:
            size -= 1
        fact_txt = rtext(fact, size, stroke=0)
        body = join(emoji(femoji, 52), fact_txt, gap=14)
        self.fact = rounded_card(body.width + 56, body.height + 22, (body.height + 22) // 2, INK + (225,))
        paste_center(self.fact, body, self.fact.width / 2, self.fact.height / 2)
        self.count = rtext("BONUS" if self.bonus else f"{idx}/10", 46, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        col, e = TIERS[tier]
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, col + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.banner = None
        if tier != prev_tier and idx > 1:
            label = "BONUS: ONLY 1% KNOW THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 78 if not self.bonus else 60, fill=col, stroke=8), emoji(e, 80))
            self.sounds += [(0.12, mq.sfx_boom(), 0.45), (0.12, mq.sfx_levelup(), 0.7)]
        ticks = [1.4, 1.85, 2.25] if not self.bonus else [1.4, 1.85, 2.3, 2.75, 3.2]
        for k, tk in enumerate(ticks):
            self.sounds.append((tk, mq.sfx_tock(high=k == len(ticks) - 1), 0.9))
        self.sounds.append((HINT, mv.sfx_pop(), 0.35))
        if self.bonus:
            self.sounds.append((self.reveal - 1.25, mv.sfx_riser(1.2), 0.7))
        self.sounds += [(self.reveal, mv.sfx_ding(), 1.0), (self.reveal, mq.sfx_boom(), 0.35),
                        (self.dur - 0.25, mv.sfx_whoosh(0.5), 0.55)]
        for i in range(len(self.tiles.pos)):
            self.sounds.append((self.reveal + 0.07 + 0.035 * i, mv.sfx_click(), 0.5))
        if idx == 1:
            self.sounds.append((0.0, mv.sfx_pop(), 0.9))
        r = random.Random(idx * 13)
        self.conf = [(r.uniform(-1, 1) * 650, r.uniform(-1250, -450), r.randint(12, 24), r.choice(self.cols),
                      r.uniform(0, 3)) for _ in range(46)]

    def render(self, t):
        rv = t - self.reveal
        c, R, blur = self.cam.at(t)
        hl = clamp((t - FLY + 0.35) / 0.35)
        fa = clamp(rv / 0.2) if rv > 0 else 0.0
        lift = 24 * ease_out_back(clamp(rv / 0.3)) if rv > 0 else 0.0
        im = self.globe.render(c, R, CENTER, self.near, hl, self.flag, fa, lift=lift)
        im = zoom_blur(im, blur)
        im.alpha_composite(self.ui["shade"])
        d = ImageDraw.Draw(im)
        # count + thin draining timer bar + difficulty tag
        paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
        x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
        frac = 1.0 if t < DRAIN0 else max(0.0, 1 - (t - DRAIN0) / (self.reveal - DRAIN0))
        d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
        col = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
        if frac > 0.01:
            d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 11, fill=col + (255,))
        paste_center(im, self.tag, x0 + self.tag.width / 2, 285)
        if self.idx == 1 and t < 2.6:  # hook, gone before the first reveal
            a = 1 - clamp((t - 2.2) / 0.4)
            paste_center(im, self.ui["hook1"], W / 2, 380, a)
            paste_center(im, self.ui["hook2"], W / 2, 460, a)
            if self.ui.get("part") is not None:
                paste_center(im, self.ui["part"], W / 2, 545, a)
        if self.banner is not None and 0.12 < t < 1.25:
            tb = t - 0.12
            s = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.18))
            a = clamp(tb / 0.08) * (1 - clamp((tb - 0.85) / 0.25))
            paste_center(im, scaled(self.banner, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 420, a)
        self.tiles.draw(im, t - HINT, rv)
        if rv > 0:
            cx, cy = getattr(self.globe, "last_hl_center", CENTER)
            for vx, vy, sz, cc, spin in self.conf:
                px, py = cx + vx * rv, cy + vy * rv + 2300 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            fk = ease_out_back((rv - 0.4) / 0.3)
            if fk > 0.01:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            f = 1 - clamp(rv / 0.18)
            if f > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(110 * f))))
        return im


class Ending(mv.Scene):
    """Score screen over the globe flying home; its last frame matches the first frame of the video."""

    def __init__(self, prev_view, globe, ui):
        super().__init__()
        self.globe, self.ui = globe, ui
        self.dur = 4.6
        self.spin = 7.0  # degrees per second while the score list is up
        self.home = (G.unit(START_LON - self.spin * (self.dur - 1.3), START_LAT), 620.0)
        self.cam = Camera(prev_view, self.home, 1.3, self.dur)
        logo = Image.open(os.path.join(HERE, "profile_picture.png")).convert("RGBA").resize((120, 120), Image.LANCZOS)
        logo.putalpha(mv.circle(120, (255, 255, 255, 255)).getchannel("A"))
        self.brand = join(logo, rtext("QUIZZIES", 60, stroke=6), gap=18)
        self.title = rtext("HOW MANY?", 124, fill=CYAN, stroke=11)
        tiers = [("0-3", "Tourist", "📸"), ("4-5", "Backpacker", "🎒"), ("6-7", "Explorer", "🧭"),
                 ("8-9", "Map nerd", "🤓"), ("10", "Human globe", "🌍")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            col = PINK if i == 4 else (255, 255, 255)
            row = rounded_card(780, 104, 52, INK + (205,), outline=(col if i == 4 else (90, 70, 130)) + (255,), width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 52), sc, font=rfont(60), fill=col, anchor="lm")
            dr.text((210, 52), label, font=rfont(60, "SemiBold"), fill=col, anchor="lm")
            row.alpha_composite(emoji(e, 60), (780 - 96, 22))
            self.rows.append(row)
            self.sounds.append((0.9 + 0.14 * i, mv.sfx_pop(), 0.7))
        self.bonus = join(rtext("+ bonus = LEGEND", 58, fill=GOLD, stroke=6), emoji("👑", 62))
        self.cta = join(rtext("comment your score", 56, stroke=6), emoji("👇", 60))
        self.sounds += [(0.0, mv.sfx_whoosh(1.0), 0.7), (0.7, mq.sfx_levelup(), 0.9), (1.75, mq.sfx_pling(), 0.7)]
        self.count = rtext("1/10", 46, stroke=5)

    def render(self, t):
        if t < 1.3:
            c, R, blur = self.cam.at(t)
        else:
            c, R, blur = G.unit(START_LON - self.spin * (self.dur - t), START_LAT), 620.0, 0.0
        im = zoom_blur(self.globe.render(c, R, CENTER), blur)
        out = clamp((t - (self.dur - 0.45)) / 0.4)  # hand over to the first frame of the video
        dim = clamp((t - 0.5) / 0.4) * (1 - out)
        im.alpha_composite(Image.new("RGBA", (W, H), INK + (int(150 * dim),)))
        a = 1 - out
        paste_center(im, self.brand, W / 2, 300, clamp((t - 0.6) / 0.3) * a)
        paste_center(im, scaled(self.title, ease_out_back((t - 0.7) / 0.3)), W / 2, 460, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - 0.9 - 0.14 * i) / 0.3)
            if k > 0:
                paste_center(im, row, W / 2 + (1 - k) * 120, 620 + i * 122, k * a)
        paste_center(im, scaled(self.bonus, ease_out_back((t - 1.7) / 0.3)), W / 2, 1255, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.95) / 0.3) * (1 + 0.03 * math.sin(t * 8))), W / 2,
                     1350, a)
        if out > 0:  # the video's first frame: count, full bar and hook
            im.alpha_composite(self.ui["shade_a"][int(out * 10)])
            paste_center(im, self.count, 92, 222, out)
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((155, 206, 1005, 238), 16, fill=INK + (int(235 * out),))
            d.rounded_rectangle((160, 211, 1000, 233), 11, fill=(255, 255, 255, int(255 * out)))
            paste_center(im, self.ui["hook1"], W / 2, 380, out)
            paste_center(im, self.ui["hook2"], W / 2, 460, out)
            if self.ui.get("part") is not None:
                paste_center(im, self.ui["part"], W / 2, 545, out)
        return im


def shade_overlay(k=1.0):
    a = np.zeros((H, W, 4), np.uint8)
    ys = np.arange(H)
    v = (np.clip(1 - ys / 420, 0, 1) ** 1.5 * 120 + np.clip((ys - 1200) / 720, 0, 1) ** 1.3 * 120) * k
    a[..., 3] = v[:, None].astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def build():
    globe = G.GlobeRenderer(W, H)
    ui = {"shade": shade_overlay(), "shade_a": [shade_overlay(i / 10) for i in range(11)],
          "hook1": rtext("name this country", 88, stroke=8),
          "hook2": join(rtext("90% will fail", 56, fill=PINK, stroke=6), emoji("😳", 60)), "part": None}
    if EPISODE > 1:
        p = rounded_card(250, 64, 32, CYAN + (255,), outline=INK + (255,), width=4)
        ImageDraw.Draw(p).text((125, 33), f"PART {EPISODE}", font=rfont(40), fill=INK, anchor="mm")
        ui["part"] = p
    scenes, view, prev_tier = [], START_VIEW, None
    for i, q in enumerate(COUNTRIES, 1):
        sc = Question(i, q, view, globe, ui, prev_tier)
        scenes.append(sc)
        c, R = sc.view
        view, prev_tier = (c, R * 1.07), q[5]
    scenes.append(Ending(view, globe, ui))
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, globe, ui


def mix_fx(scenes, starts, total):
    n = int(total * SR) + SR
    fx = np.zeros(n)
    for sc, st in zip(scenes, starts):
        for at, arr, g in sc.sounds:
            i = int((st + at) * SR)
            fx[i:i + len(arr)] += arr[: n - i] * g
    fx = fx / (np.abs(fx).max() + 1e-9) * 0.9
    return (np.stack([fx, fx], 1) * 32767).astype(np.int16)


def make_cover(globe, path):
    code, (lon, lat), zf = EPISODES[EPISODE][2]
    c, near, _ = globe.world.country(code)
    R = 1250 if zf is None else G.zoom_for(globe.world, c, near, W, H, 0.36, 0.22) * zf
    im = globe.render(G.unit(lon, lat), R, (540, 1150), near, 1.0, lift=20)
    im.alpha_composite(shade_overlay())
    paste_center(im, rtext("name this", 140, stroke=12), W / 2, 260)
    paste_center(im, rtext("country", 170, fill=CYAN, stroke=14), W / 2, 430)
    paste_center(im, join(rtext("90% will fail", 80, fill=PINK, stroke=8), emoji("😳", 84)), W / 2, 590)
    if EPISODE > 1:
        p = rounded_card(330, 90, 45, CYAN + (255,), outline=INK + (255,), width=5)
        ImageDraw.Draw(p).text((165, 47), f"PART {EPISODE}", font=rfont(58), fill=INK, anchor="mm")
        paste_center(im, p.rotate(-6, Image.BICUBIC, expand=True), W / 2, 705)
    paste_center(im, rtext("?", 300, stroke=18), 820, 1110)
    name = next(q[2] for q in COUNTRIES if q[0] == code)
    tiles = Tiles(name, True)
    tiles.draw(im, 1.0, -1.0)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", type=int, default=1, choices=sorted(EPISODES))
    ap.add_argument("--out", default=None)
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    set_episode(a.episode)
    suffix = EPISODES[a.episode][3]
    a.out = a.out or os.path.join(HERE, f"short_map_quiz{suffix}.mp4")
    scenes, starts, total, globe, ui = build()
    print(f"Duration {total:.1f}s")
    if a.cover:
        make_cover(globe, os.path.join(HERE, f"map_quiz{suffix}_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"map{suffix}_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    work = os.path.join(mv.CACHE_DIR, "render_map")
    os.makedirs(work, exist_ok=True)
    for f in os.listdir(work):
        os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mix_fx(scenes, starts, total))
    nframes = int(total * FPS)
    n = max(1, a.workers)
    bounds = [round(nframes * k / n) for k in range(n + 1)]
    jobs = [(k, bounds[k], bounds[k + 1], os.path.join(work, f"part{k}.mp4")) for k in range(n)]
    with mp.get_context("fork").Pool(n) as pool:
        parts = pool.map(mv.render_chunk, jobs)
    lst = os.path.join(work, "parts.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    tmp = os.path.join(work, "joined.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", tmp], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-c:v", "libx264", "-crf", "23", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.out], check=True)
    print(f"Done: {a.out}")


if __name__ == "__main__":
    main()
