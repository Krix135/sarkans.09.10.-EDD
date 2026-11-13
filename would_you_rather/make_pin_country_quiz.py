#!/usr/bin/env python3
""""PIN THE COUNTRY" Short (1080x1920), part 3 formula with a big hook.

Each round asks WHERE IS <country>? The globe whips to a region and four pins (A-D) drop onto the real
country and three neighbours. A 3-2-1 runs on the beat; on the drop the right pin turns green, the
wrong ones fade, and the globe zooms into the country, which fills with its flag, with a fun fact.
Hook intro: cold open on the bonus question with pins already standing, a rapid montage of pinned
regions, then PIN THE COUNTRY / ON THE MAP / 99% FAIL over a spinning globe with pins dropping on it.
EASY -> IMPOSSIBLE plus a bonus, one like call-out after round 3, looping score screen.
Borders: Natural Earth (public domain); flags: public domain.

    python3 make_pin_country_quiz.py
    python3 make_pin_country_quiz.py --stills 0,2,6
    python3 make_pin_country_quiz.py --cover
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
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import globe as G  # noqa: E402
import make_bigger_country_quiz as bq  # noqa: E402
import make_club_quiz as cq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_in_out, ease_out_back, ease_out_cubic, emoji, paste_center, \
    rounded_card, scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
GC = (540, 1150)                    # globe centre during the rounds
CARD_Y = 410
NUM_Y = 600
FACT_Y = 1600
FLY_BEATS = 3
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
GREEN = (46, 204, 113)
PIN_COLS = {"A": PINK, "B": CYAN, "C": GOLD, "D": (170, 110, 255)}

# pin points (lon, lat), chosen well inside each country
POINTS = {
    "PRT": (-8.0, 39.6), "ESP": (-3.7, 40.2), "FRA": (2.5, 46.8), "MAR": (-6.5, 32.0),
    "EGY": (30.5, 26.5), "LBY": (17.5, 27.0), "SDN": (30.0, 15.5), "SAU": (44.5, 24.0),
    "ARG": (-64.5, -35.0), "BRA": (-51.0, -10.0), "PER": (-75.0, -9.5), "COL": (-73.5, 4.0),
    "THA": (101.0, 15.5), "MMR": (96.0, 21.0), "LAO": (102.5, 19.5), "KHM": (104.9, 12.6),
    "POL": (19.4, 52.1), "DEU": (10.4, 51.1), "UKR": (31.2, 49.0), "BLR": (28.0, 53.5),
    "KEN": (37.9, 0.2), "ETH": (39.5, 9.0), "TZA": (34.8, -6.3), "UGA": (32.3, 1.4),
    "HRV": (15.9, 45.6), "SRB": (20.9, 44.0), "HUN": (19.4, 47.2), "BIH": (17.8, 44.0),
    "PRY": (-58.4, -23.4), "BOL": (-64.7, -16.7), "URY": (-56.0, -32.8),
    "LVA": (24.8, 56.9), "EST": (25.5, 58.7), "LTU": (23.9, 55.3),
    "BFA": (-1.6, 12.3), "MLI": (-4.0, 17.5), "NER": (9.0, 17.0), "GHA": (-1.0, 7.9),
    "SWZ": (31.5, -26.5), "LSO": (28.2, -29.6), "BWA": (24.7, -22.3), "MOZ": (37.0, -15.0),
}
ROUNDS = [  # asked, flag, name, three decoys, fact, fact emoji, tier, sticker
    ("PRT", "PT", "PORTUGAL", ("ESP", "FRA", "MAR"), "the westernmost country of mainland Europe", "🧭", "EASY", "😎"),
    ("EGY", "EG", "EGYPT", ("LBY", "SDN", "SAU"), "home to the last standing ancient wonder", "🔺", "EASY", "🔥"),
    ("ARG", "AR", "ARGENTINA", ("BRA", "PER", "COL"), "it has won 3 World Cups", "🏆", "EASY", "🤔"),
    ("THA", "TH", "THAILAND", ("MMR", "LAO", "KHM"), "Bangkok's full name is the longest city name", "🏙",
     "MEDIUM", "😳"),
    ("POL", "PL", "POLAND", ("DEU", "UKR", "BLR"), "home to Europe's heaviest land animal, the bison", "🦬",
     "MEDIUM", "🤯"),
    ("KEN", "KE", "KENYA", ("ETH", "TZA", "UGA"), "famous for the Great Migration of wildebeest", "🦓", "MEDIUM",
     "🔥"),
    ("HRV", "HR", "CROATIA", ("SRB", "HUN", "BIH"), "it has over 1,000 islands", "🏝", "HARD", "😱"),
    ("PRY", "PY", "PARAGUAY", ("BOL", "URY", "BRA"), "it has two official languages: Spanish and Guarani", "🗣",
     "HARD", "💀"),
    ("LVA", "LV", "LATVIA", ("EST", "LTU", "BLR"), "about half of it is covered in forest", "🌲", "INSANE", "🧠"),
    ("BFA", "BF", "BURKINA FASO", ("MLI", "NER", "GHA"), "its name means 'land of honest people'", "🤝",
     "IMPOSSIBLE", "☠"),
    ("SWZ", "SZ", "ESWATINI", ("LSO", "BWA", "MOZ"), "it was called Swaziland until 2018", "📜", "BONUS", "👑"),
]
INTRO_LINE = "Only one percent can find them all!"
END_LINE = "How many did you get? Comment your score!"


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


def project(p, c, R, center):
    east, up, view = G.frame_axes(c)
    return center[0] + R * float(p @ east), center[1] - R * float(p @ up), float(p @ view) > 0.05


def region_view(codes, center=GC):
    pts = np.array([G.unit(*POINTS[k]) for k in codes])
    c = pts.mean(0)
    c /= np.linalg.norm(c)
    east, up, view = G.frame_axes(c)
    sx, sy = np.abs(pts @ east).max(), np.abs(pts @ up).max()
    R = float(np.clip(min(360 / max(sx, 1e-3), 330 / max(sy, 1e-3)), 520, 9000))
    return c, R


# ----------------------------------------------------------------------------
# pins and cards
# ----------------------------------------------------------------------------
def pin_sprite(letter, col, mark=None):
    """A map pin (tip at the bottom centre) with its letter, or a mark like a check."""
    k = 2
    w, h = 130 * k, 172 * k
    im = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(im)
    cx, cy, r = 65 * k, 62 * k, 54 * k
    d.polygon([(cx, 168 * k), (cx - 40 * k, 98 * k), (cx + 40 * k, 98 * k)], fill=(255, 255, 255, 255))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 255))
    r2, s2 = r - 8 * k, 8 * k
    d.polygon([(cx, 168 * k - s2 * 1.6), (cx - 34 * k, 100 * k), (cx + 34 * k, 100 * k)], fill=col + (255,))
    d.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), fill=col + (255,))
    im = im.resize((130, 172), Image.LANCZOS)
    if mark is None:
        t = rtext(letter, 66, fill=(255, 255, 255), stroke=6)
        paste_center(im, t, 65, 64)
    else:
        paste_center(im, emoji(mark, 60), 65, 62)
    return im


def pin_shadow():
    s = Image.new("RGBA", (90, 40))
    ImageDraw.Draw(s).ellipse((10, 10, 80, 30), fill=(0, 0, 10, 140))
    return s.filter(ImageFilter.GaussianBlur(4))


def question_card(name, flag):
    q = rtext("WHERE IS", 50, fill=(220, 220, 240), stroke=5)
    size = 100
    while rfont(size).getlength(name + "?") > 640 and size > 60:
        size -= 4
    n = rtext(name + "?", size, fill=GOLD, stroke=9)
    fl = flag.copy()
    fl.thumbnail((150, 100), Image.LANCZOS)
    fb = Image.new("RGBA", (fl.width + 10, fl.height + 10), (255, 255, 255, 255))
    fb.paste(fl, (5, 5))
    body_w = max(q.width, n.width) + 30 + fb.width
    card = rounded_card(min(1000, body_w + 80), 200, 50, (14, 6, 40, 228), outline=CYAN + (255,), width=5)
    x0 = (card.width - body_w) // 2
    card.alpha_composite(q, (x0, 22))
    card.alpha_composite(n, (x0, 64))
    card.alpha_composite(fb, (x0 + max(q.width, n.width) + 30, (200 - fb.height) // 2))
    return card


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    TEASE, MONTAGE = 10, (8, 6, 9, 7)

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 6 * B
        self.t1, self.t2 = 1.5 * B, 3.5 * B
        self.views = {k: region_view([ROUNDS[k][0], *ROUNDS[k][3]]) for k in (self.TEASE, *self.MONTAGE)}
        self.pins = {k: [(G.unit(*POINTS[code]), pin_sprite(L, PIN_COLS[L]))
                         for L, code in zip("ABCD", [ROUNDS[k][0], *ROUNDS[k][3]])] for k in self.views}
        r = ROUNDS[self.TEASE]
        self.card = question_card(r[2], Image.open(os.path.join(FLAG_DIR, r[1] + ".png")).convert("RGBA"))
        self.o1 = fit(join(rtext("ONLY 1% CAN FIND", 96, fill=PINK, stroke=10), emoji("😳", 92), gap=10))
        self.o3 = join(rtext("answer at the end", 60, fill=GOLD, stroke=7), emoji("👀", 64))
        self.m1 = fit(rtext("CAN YOU FIND", 108, stroke=10))
        self.m2 = fit(rtext("ALL OF THEM?", 120, fill=CYAN, stroke=11))
        self.l1 = fit(join(rtext("PIN THE COUNTRY", 112, fill=PINK, stroke=11), emoji("📍", 104), gap=10), 940)
        self.l2 = fit(rtext("ON THE MAP", 140, stroke=13), 900)
        self.l3 = join(rtext("99% FAIL", 120, fill=GOLD, stroke=11), emoji("💀", 120))
        rr = random.Random(5)
        self.drops = [(G.unit(rr.uniform(-60, 60), rr.uniform(-30, 50)), pin_sprite(L, PIN_COLS[L]), 0.5 * B * k)
                      for k, L in enumerate("ABCDABCD")]
        self.shadow = pin_shadow()
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9),
                        (0.02, mq.sfx_glitch(), 0.5), (B, sfx_heartbeat(), 0.8), (B, mq.sfx_boom(), 0.5),
                        (self.t2, mq.sfx_boom(), 0.9), (self.t2, mv.sfx_whoosh(0.5), 0.6),
                        (4.5 * B, mv.sfx_riser(1.5 * B), 0.7), (6 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k in range(len(self.MONTAGE)):
            at = self.t1 + k * 0.5 * B
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mq.sfx_glitch(), 0.35), (at, mv.sfx_click(), 0.7)]
        for _, _, at in self.drops:
            self.sounds.append((self.t2 + at, mv.sfx_pop(), 0.6))
        if tts:
            self.voices.append((0.04, tts.say(INTRO_LINE, speed=1.18)))

    def draw_pins(self, im, k, c, R, T, s=1.0):
        for i, (p, spr) in enumerate(self.pins[k]):
            x, y, vis = project(p, c, R, GC)
            if vis:
                bob = 1 + 0.08 * beat_pulse(T + i * 0.1)
                paste_center(im, self.shadow, x, y)
                sp = scaled(spr, s * bob)
                im.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height)))

    def render(self, t):
        T = self.t0 + t
        g = self.ui["globe"]
        if t < self.t1:                                      # cold open: question + pins readable on frame one
            c, R = self.views[self.TEASE]
            R *= 1.04 - 0.04 * ease_out_cubic(t / 0.3)
            im = g.render(c, R, GC)
            im.alpha_composite(self.ui["shade"])
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.5 * beat_pulse(T)))])
            self.draw_pins(im, self.TEASE, c, R, T)
            s = 1 + 0.06 * (1 - ease_out_cubic(t / 0.2))
            paste_center(im, scaled(self.o1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 220)
            paste_center(im, scaled(self.card, s * (1 + 0.03 * beat_pulse(T))), W / 2, CARD_Y)
            paste_center(im, self.o3, W / 2, 1700)
            im = shake(im, 26 * (1 - t / 0.3) if t < 0.3 else 0, t)
            return rgb_split(im, 8 * (1 - clamp(t / 0.25)))
        if t < self.t2:                                      # rapid montage of pinned regions
            k = min(len(self.MONTAGE) - 1, int((t - self.t1) / (0.5 * B)))
            tc = t - self.t1 - k * 0.5 * B
            key = self.MONTAGE[k]
            c, R = self.views[key]
            R *= 1.1 - 0.1 * ease_out_cubic(tc / 0.15)
            im = g.render(c, R, GC)
            im.alpha_composite(self.ui["shade"])
            self.draw_pins(im, key, c, R, T)
            s = 1 + 0.12 * (1 - ease_out_cubic((t - self.t1) / 0.15))
            paste_center(im, scaled(self.m1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 300)
            paste_center(im, scaled(self.m2, s).rotate(3, Image.BICUBIC, expand=True), W / 2, 450)
            im = rgb_split(im, 18 * (1 - clamp(tc / 0.12)))
            if tc < 0.06:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            return im
        tg = t - self.t2                                     # titles over a spinning globe, pins raining onto it
        gc, R = (540, 1250), 480 * (1 + 0.05 * beat_pulse(T)) * (1.25 - 0.25 * ease_out_cubic(clamp(tg / 0.3)))
        c = G.unit(-20 + 50 * tg, 15)
        im = g.render(c, R, gc)
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 50)))
        for p, spr, at in self.drops:
            td = tg - at
            if td <= 0:
                continue
            x, y, vis = project(p, c, R, gc)
            if not vis:
                continue
            fall = (1 - ease_out_back(clamp(td / 0.3), 2.0)) * 500
            paste_center(im, self.shadow, x, y, clamp(td / 0.3))
            im.alpha_composite(spr, (int(x - spr.width / 2), int(y - spr.height - fall)))
        b = int(tg / (0.5 * B))
        kk = (tg % (0.5 * B)) / (0.5 * B)
        slam = 1 + 0.35 * (1 - ease_out_cubic(kk / 0.4))
        paste_center(im, scaled(self.l1, (slam if b == 0 else 1.0) * (1 + 0.03 * beat_pulse(T))).rotate(
            -3, Image.BICUBIC, expand=True), W / 2, 320)
        if b >= 1:
            paste_center(im, scaled(self.l2, slam if b == 1 else 1.0).rotate(2, Image.BICUBIC, expand=True),
                         W / 2, 490)
        if b >= 2:
            paste_center(im, scaled(self.l3, slam if b == 2 else 1.0), W / 2, 660)
        im = shake(im, 22 * (1 - kk) if kk < 0.4 and b <= 2 else 0, t)
        if tg < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(160 * (1 - tg / 0.08)))))
        whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Round(mv.Scene):
    def __init__(self, idx, r, prev_view, prev_tier, ui, tts):
        super().__init__()
        code, fcode, name, decoys, fact, femoji, tier, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = FLY_BEATS
        self.dur = (f + (12 if self.bonus else 8) + (5 if self.cta else 0)) * B
        self.fly = f * B
        self.reveal = (f + (7 if self.bonus else 4)) * B
        self.count_beats = list(range(f + 2, f + 7)) if self.bonus else [f + 1, f + 2, f + 3]
        self.cta_at = 2.2 * B
        world = ui["globe"].world
        codes = [code, *decoys]
        self.region = region_view(codes)
        self.cam = mm.Camera(prev_view, self.region, self.fly, self.reveal)
        cc, self.near, _ = world.country(code)
        self.country_c = cc
        self.country_R = G.zoom_for(world, cc, self.near, W, H, 0.34, 0.2)
        # letters A-D from left to right as the pins stand in the region view
        rc, rR = self.region
        xs = sorted((project(G.unit(*POINTS[k]), rc, rR, GC)[0], k) for k in codes)
        self.pins = []
        for L, (_, k) in zip("ABCD", xs):
            self.pins.append((L, k, G.unit(*POINTS[k])))
            if k == code:
                self.letter = L
        self.sprites = {L: pin_sprite(L, PIN_COLS[L]) for L in "ABCD"}
        self.right_sprite = pin_sprite(self.letter, GREEN, "✅")
        self.grey = {L: pin_sprite(L, (110, 110, 130)) for L in "ABCD"}
        self.shadow = pin_shadow()
        self.flag = Image.open(os.path.join(FLAG_DIR, fcode + ".png")).convert("RGBA")
        self.cols = mm.flag_colours(self.flag)
        self.card = question_card(name, self.flag)
        st = join(rtext("IT'S", 64, fill=(255, 255, 255), stroke=6), rtext(self.letter, 96, fill=GREEN, stroke=8),
                  emoji("✅", 80), gap=12)
        sc = rounded_card(st.width + 50, st.height + 24, 30, INK + (240,), outline=GREEN + (255,), width=6)
        paste_center(sc, st, sc.width / 2, sc.height / 2)
        self.stamp = sc.rotate(-6, Image.BICUBIC, expand=True)
        fs = 42
        while rfont(fs).getlength(fact) > 760 and fs > 26:
            fs -= 1
        body = join(emoji(femoji, 52), rtext(fact, fs, stroke=0), gap=14)
        self.fact = rounded_card(body.width + 56, body.height + 22, (body.height + 22) // 2, INK + (225,))
        paste_center(self.fact, body, self.fact.width / 2, self.fact.height / 2)
        self.sticker = emoji(stick, 150)
        self.col, e = TIERS[tier]
        self.count = rtext("BONUS" if self.bonus else f"{idx}/10", 46, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, self.col + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.level_up = tier != prev_tier and idx > 1
        self.banner = None
        if self.level_up:
            label = "BONUS: ONLY 1% KNOW THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 62 if self.bonus else 92, fill=self.col, stroke=9), emoji(e, 90))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        n = len(self.count_beats)
        self.nums = {k: rtext(str(k), 180, fill=PINK if k == 1 else (255, 255, 255), stroke=14) for k in range(1, n + 1)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self.drop_at = [self.fly - 0.25 + k * 0.5 * B * 0.5 for k in range(4)]
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8)]
        for at in self.drop_at:
            self.sounds += [(at + 0.2, mv.sfx_pop(), 0.8), (at + 0.2, mq.sfx_boom(), 0.3)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        self.sounds += [(self.reveal, mq.sfx_boom(), 0.9), (self.reveal, mv.sfx_ding(), 1.0),
                        (self.reveal + 0.05, mq.sfx_pling(), 0.6), (self.reveal + 0.35, mv.sfx_whoosh(0.5), 0.6),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        if tts:
            v = tts.say(f"Where is {name.title()}?", speed=1.18)
            self.voices.append((0.12, v))
            if 0.12 + len(v) / SR > self.count_beats[0] * B + 0.1:
                print(f"warning: prompt {idx} runs into the countdown", flush=True)
            self.voices.append((self.reveal + 0.08, tts.say(f"{self.letter}! {name.title()}!", speed=1.12)))
            if self.cta:
                self.voices.append((self.reveal + self.cta_at, tts.say(CTA_LINE, speed=1.12)))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = self.reveal + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, mq.sfx_pling(), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        rr = random.Random(idx * 31)
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1350, -450), rr.randint(12, 26), rr.choice(self.cols),
                      rr.uniform(0, 3)) for _ in range(70)]

    def camera(self, t):
        rv = t - self.reveal
        if rv <= 0:
            return self.cam.at(t)
        c0, R0, _ = self.cam.at(self.reveal - 1e-3)
        k = ease_in_out(clamp((rv - 0.3) / 0.6))
        return G.slerp(c0, self.country_c, k), math.exp(math.log(R0) + (math.log(self.country_R) - math.log(R0)) * k), 0.0

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        c, R, blur = self.camera(t)
        if t > self.fly and rv < 0:
            R *= 1 + 0.02 * beat_pulse(T)
        hl = clamp((rv - 0.35) / 0.2) if rv > 0 else 0.0
        fa = clamp((rv - 0.5) / 0.3) if rv > 0 else 0.0
        lift = 22 * ease_out_back(clamp((rv - 0.6) / 0.3)) if rv > 0 else 0.0
        im = self.ui["globe"].render(c, R, GC, self.near, hl, self.flag, fa, lift=lift)
        im = mm.zoom_blur(im, blur)
        im = rgb_split(im, 22 * blur)
        im.alpha_composite(self.ui["shade"])
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv > 0:
            im.alpha_composite(cq.speed_lines(1 - clamp(rv / 0.45), self.idx, GC))
        # pins drop in on the half beats, bob on the beat, then show who was right
        for i, (L, k, p) in enumerate(self.pins):
            td = t - self.drop_at[i]
            if td <= 0:
                continue
            x, y, vis = project(p, c, R, GC)
            if not vis:
                continue
            fall = (1 - ease_out_back(clamp(td / 0.3), 2.0)) * 600
            right = L == self.letter
            if rv > 0:
                if right:
                    spr = self.right_sprite
                    s = 1.15 + 0.25 * (1 - ease_out_cubic(clamp(rv / 0.3))) + 0.05 * beat_pulse(T)
                    a = 1.0
                else:
                    spr = self.grey[L]
                    s = 0.85 * (1 - 0.15 * clamp(rv / 0.3))
                    a = 1 - 0.5 * clamp(rv / 0.3)
                    x += 12 * math.sin(rv * 60) * (1 - clamp(rv / 0.4))
            else:
                spr, s, a = self.sprites[L], 1 + 0.07 * beat_pulse(T + i * 0.12), 1.0
            paste_center(im, self.shadow, x, y, clamp(td / 0.3) * a)
            sp = scaled(spr, s)
            if a < 1:
                sp.putalpha(sp.getchannel("A").point(lambda v, a=a: int(v * a)))
            im.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height - fall)))
        d = ImageDraw.Draw(im)
        paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
        x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
        frac = 1.0 if t < self.fly else max(0.0, 1 - (t - self.fly) / (self.reveal - self.fly))
        d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
        colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
        if frac > 0.01:
            d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 11, fill=colr + (255,))
        paste_center(im, self.tag, x0 + self.tag.width / 2, 285)
        nk = self.idx if rv > 0 else self.idx - 1
        if nk > 0:
            sc = 1 + 0.5 * (1 - ease_out_cubic(rv / 0.25)) if 0 < rv < 0.25 else 1.0
            stk = self.streak[nk]
            paste_center(im, scaled(stk, sc), x1 - stk.width / 2 + 10, 288)
        kc = ease_out_back(clamp((t - 0.05) / 0.3), 1.6)
        if kc > 0.01:
            paste_center(im, scaled(self.card, kc * (1 + 0.015 * beat_pulse(T))), W / 2, CARD_Y)
        if rv > 0:
            ks = ease_out_back(clamp((rv - 0.05) / 0.25), 2.4)
            if ks > 0.01:
                paste_center(im, scaled(self.stamp, 1.6 - 0.6 * ks), W / 2 + 230, CARD_Y + 170, min(1.0, ks))
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, 640, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a * 0.85)
        cta_on = self.cta and rv > self.cta_at
        if rv > 0:
            cx, cy = getattr(self.ui["globe"], "last_hl_center", GC) if hl > 0 else GC
            for vx, vy, sz, cc, spin in self.conf:
                px, py = cx + vx * rv, cy + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d = ImageDraw.Draw(im)
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            sk = ease_out_back((rv - 0.7) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             900, 1440)
            fk = ease_out_back((rv - 0.8) / 0.3)
            if fk > 0.01 and not cta_on:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(190 * fl))))
            im = shake(im, 28 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 16 * (1 - rv / 0.18))
        else:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 10 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 7 * (1 - tb / 0.15))
        if cta_on:
            ct = rv - self.cta_at
            k = ease_out_back(ct / 0.3, 2.0) * (1 - ease_in_cubic(clamp((t - (self.dur - 0.45)) / 0.25)))
            if k > 0.01:
                card = self.cta_card.copy()
                tap = 1 - 0.18 * math.sin(math.pi * clamp((ct - 0.45) / 0.2))
                th = scaled(self.thumb, tap * (1 + 0.08 * beat_pulse(T))).rotate(10 * math.sin(ct * 7), Image.BICUBIC,
                                                                                 expand=True)
                paste_center(card, th, 98, 98)
                paste_center(im, scaled(card, k * (1 + 0.025 * beat_pulse(T))).rotate(-2, Image.BICUBIC,
                                                                                     expand=True), W / 2, FACT_Y)
        if self.level_up and t < 0.35:
            im = glitch(im, 1 - t / 0.35, int(t * 30) + self.idx * 7)
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(im, 20 * out)
        return im


def build(voice="am_adam", voice_pack=None):
    if voice_pack:
        tts = cq.Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    world = G.World()
    globe = G.GlobeRenderer(W, H, world)
    ui = {"globe": globe, "big_globe": globe, "shade": mm.shade_overlay(0.8),
          "vig": [mc.red_vignette(i / 10) for i in range(11)]}
    intro = Intro(ui, tts)
    scenes, view, prev = [intro], (G.unit(-20 + 50 * intro.dur * 0.36, 15), 600.0), ROUNDS[0][6]
    for i, r in enumerate(ROUNDS, 1):
        sc = Round(i, r, view, prev, ui, tts)
        scenes.append(sc)
        view, prev = (sc.country_c, sc.country_R * 1.05), r[6]
    scenes.append(bq.Ending(ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    k = 6
    r = ROUNDS[k]
    codes = [r[0], *r[3]]
    c, R = region_view(codes)
    im = ui["globe"].render(c, R * 0.95, GC)
    im.alpha_composite(mm.shade_overlay(0.9))
    xs = sorted((project(G.unit(*POINTS[q]), c, R * 0.95, GC)[0], q) for q in codes)
    sh = pin_shadow()
    for L, (_, q) in zip("ABCD", xs):
        x, y, _ = project(G.unit(*POINTS[q]), c, R * 0.95, GC)
        paste_center(im, sh, x, y)
        sp = scaled(pin_sprite(L, PIN_COLS[L]), 1.15)
        im.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height)))
    paste_center(im, fit(join(rtext("PIN THE COUNTRY", 112, fill=PINK, stroke=11), emoji("📍", 104), gap=10), 960)
                 .rotate(-3, Image.BICUBIC, expand=True), W / 2, 220)
    flag = Image.open(os.path.join(FLAG_DIR, r[1] + ".png")).convert("RGBA")
    paste_center(im, question_card(r[2], flag), W / 2, 420)
    paste_center(im, join(rtext("99% FAIL", 96, fill=GOLD, stroke=9), emoji("💀", 98)), W / 2, 1720)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_pin_country_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--music", default="phonk", choices=["phonk", "none"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    quiet = a.stills or a.cover
    scenes, starts, total, ui = build(a.voice if not quiet else "none", None if quiet else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    if a.cover:
        make_cover(ui, os.path.join(HERE, "pin_country_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"pin_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_pin")
    os.makedirs(work, exist_ok=True)
    for f in os.listdir(work):
        os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mmq.mix_audio(scenes, starts, total, a.music))
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
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-c:v", "libx264", "-crf", "24", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.out], check=True)
    print(f"Done: {a.out}")


if __name__ == "__main__":
    main()
