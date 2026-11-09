#!/usr/bin/env python3
""""name this country": a harder, heavily edited spinning-globe quiz Short (1080x1920).

Everything is cut to a 130 BPM phonk beat: 6-beat hook (cold open on the bonus country, mystery montage,
title slams), 10 beats per
country (whip-spin with zoom blur + RGB split, big 3-2-1 slams on the beats,
reveal with shake / flash / zoom punch / speed lines / sticker), a streak
counter, glitch transitions and a red heartbeat vignette on the hard levels,
a narrator with a "like this video" call-out after country 3, and an
ending that loops into the first frame.
Borders: Natural Earth 1:50m (public domain). Flags: public domain.

    python3 make_map_quiz_crazy.py
    python3 make_map_quiz_crazy.py --stills 0,1,3
    python3 make_map_quiz_crazy.py --cover
    python3 make_map_quiz_crazy.py --voice-pack voice_packs/map3_adam      # ElevenLabs Adam narrator
    python3 make_map_quiz_crazy.py --episode 4                             # easier episode, new countries
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
from PIL import Image, ImageDraw  # noqa: E402

import brand  # noqa: E402
import globe as G  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, RED, VIOLET, join, rfont, rtext  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center, rounded_card, \
    scaled, tt  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM                     # one beat
CENTER = mm.CENTER
FLAG_DIR = os.path.join(HERE, "flags")
NUM_Y = 405
FLY_BEATS = 3                    # beats spent spinning from one country to the next
TIERS = dict(mm.TIERS, IMPOSSIBLE=((200, 40, 255), "☠"))
START = (G.unit(-40, 28), 620.0)
CTA_AFTER = (3,)                 # "like this video" call-out after these countries (end of MEDIUM)
CTA_LINE = "Like this video if you got everything so far!"
CTA_AT = 2 * B                   # after the reveal, once the answer has been said
CTA_BEATS = 5                    # extra beats the scene holds for it
CTA_Y = 1585

COUNTRIES = [  # map code, flag, name, fact, fact emoji, tier, prompt, spoken answer, reaction sticker
    ("PRT", "PT", "PORTUGAL", "its borders haven't changed since 1297", "🏰", "MEDIUM",
     "Name this country!", "Portugal!", "😎"),
    ("SWE", "SE", "SWEDEN", "it has about 267,000 islands", "🏝", "MEDIUM", "Next!", "Sweden!", "🔥"),
    ("THA", "TH", "THAILAND", "it was never colonised by Europe", "🐘", "MEDIUM", "Too easy?", "Thailand!", "🤔"),
    ("CUB", "CU", "CUBA", "home to the world's smallest bird", "🐦", "HARD", "Hard level!", "Cuba!", "😳"),
    ("PHL", "PH", "PHILIPPINES", "it's made of over 7,600 islands", "🌴", "HARD", "Think fast!",
     "The Philippines!", "🤯"),
    ("COL", "CO", "COLOMBIA", "more bird species than any other country", "🦜", "HARD", "Ooh, tricky!",
     "Colombia!", "🔥"),
    ("PAN", "PA", "PANAMA", "its canal links the Atlantic and the Pacific", "🚢", "INSANE", "Insane level!",
     "Panama!", "😱"),
    ("HRV", "HR", "CROATIA", "the necktie was invented here", "👔", "INSANE", "No way!", "Croatia!", "💀"),
    ("LAO", "LA", "LAOS", "the most bombed country per person in history", "💣", "INSANE", "Only geniuses!",
     "Laos!", "🧠"),
    ("MWI", "MW", "MALAWI", "about a fifth of it is one giant lake", "🌊", "IMPOSSIBLE", "Impossible level!",
     "Malawi!", "☠"),
    ("GMB", "GM", "THE GAMBIA", "the smallest country on mainland Africa", "🤯", "BONUS",
     "Bonus! Only one percent!", "The Gambia!", "👑"),
]


COUNTRIES_4 = [  # episode 4: easier, and none of these were in episodes 1-3
    ("BRA", "BR", "BRAZIL", "about 60% of the Amazon rainforest is here", "🌳", "EASY", "Name this country!",
     "Brazil!", "😎"),
    ("IND", "IN", "INDIA", "the most populous country on Earth", "👥", "EASY", "Next!", "India!", "🔥"),
    ("AUS", "AU", "AUSTRALIA", "it's a country and a continent", "🦘", "EASY", "Too easy?", "Australia!", "🤔"),
    ("JPN", "JP", "JAPAN", "it's made of over 14,000 islands", "🗾", "MEDIUM", "Think fast!", "Japan!", "😳"),
    ("NOR", "NO", "NORWAY", "up north the sun doesn't set in summer", "☀", "MEDIUM", "Ooh, tricky!", "Norway!",
     "🤯"),
    ("ARG", "AR", "ARGENTINA", "home to the highest peak in the Americas", "🏔", "MEDIUM", "Next!", "Argentina!",
     "🔥"),
    ("DEU", "DE", "GERMANY", "it has over 1,500 kinds of sausage", "🌭", "HARD", "Hard level!", "Germany!", "😱"),
    ("ZAF", "ZA", "SOUTH AFRICA", "it has three capital cities", "🏛", "HARD", "No way!", "South Africa!", "💀"),
    ("KOR", "KR", "SOUTH KOREA", "half its people live in and around Seoul", "🏙", "HARD", "Only geniuses!",
     "South Korea!", "🧠"),
    ("IRL", "IE", "IRELAND", "Halloween started here", "🎃", "INSANE", "Insane level!", "Ireland!", "☠"),
    ("LKA", "LK", "SRI LANKA", "one of the world's biggest tea exporters", "🍵", "BONUS", "Bonus! Only one percent!",
     "Sri Lanka!", "👑"),
]

EPISODES = {  # countries, cold-open country, montage, cover (country, view lon/lat, zoom, tiles), file number
    3: (COUNTRIES, "GMB", ("CUB", "LAO", "HRV", "MWI"), ("HRV", 17.5, 44.5, 0.55, "CROATIA"), 3,
        ("HARDEST", "MAP QUIZ")),
    4: (COUNTRIES_4, "LKA", ("IRL", "KOR", "ZAF", "NOR"), ("NOR", 15.0, 65.5, 1.25, "NORWAY"), 4,
        ("NAME THE", "COUNTRY")),
}
EPISODE = 3
COVER = EPISODES[3][3]


def set_episode(ep):
    global COUNTRIES, COVER, EPISODE
    EPISODE = ep
    COUNTRIES, tease, montage, COVER, _, title = EPISODES[ep]
    Intro.TEASE, Intro.MONTAGE, Intro.TITLE = tease, montage, title


# ----------------------------------------------------------------------------
# effects
# ----------------------------------------------------------------------------

def rgb_split(im, amt):
    """Chromatic aberration: red shifted left, blue shifted right."""
    amt = int(amt)
    if amt < 1:
        return im
    a = np.asarray(im).copy()
    a[..., 0] = np.roll(a[..., 0], -amt, axis=1)
    a[..., 2] = np.roll(a[..., 2], amt, axis=1)
    return Image.fromarray(a, im.mode)


def glitch(im, k, seed):
    """Horizontal slice offsets + RGB split (k = 0..1)."""
    if k <= 0.02:
        return im
    r = random.Random(seed)
    a = np.asarray(im).copy()
    for _ in range(int(6 + 14 * k)):
        y0 = r.randrange(0, H - 40)
        h = r.randint(8, int(30 + 90 * k))
        a[y0:y0 + h] = np.roll(a[y0:y0 + h], r.randint(-int(80 * k) - 1, int(80 * k) + 1), axis=1)
    return rgb_split(Image.fromarray(a, im.mode), 6 + 18 * k)


def shake(im, amt, t):
    if amt < 0.5:
        return im
    dx, dy = int(amt * math.sin(t * 97)), int(amt * math.cos(t * 83))
    out = Image.new(im.mode, im.size, (10, 5, 30, 255))
    out.paste(im, (dx, dy))
    return out


def speed_lines(k, seed):
    """Radial anime speed lines around the centre (k = opacity 0..1)."""
    im = Image.new("RGBA", (W, H))
    if k <= 0.02:
        return im
    d = ImageDraw.Draw(im)
    r = random.Random(seed)
    cx, cy = CENTER
    for _ in range(46):
        a = r.uniform(0, 2 * math.pi)
        r0, r1 = r.uniform(420, 620), r.uniform(1100, 1500)
        w = r.uniform(3, 10)
        p0 = (cx + r0 * math.cos(a), cy + r0 * math.sin(a))
        p1 = (cx + r1 * math.cos(a + 0.015), cy + r1 * math.sin(a + 0.015))
        p2 = (cx + r1 * math.cos(a - 0.015), cy + r1 * math.sin(a - 0.015))
        d.polygon([p0, p1, p2], fill=(255, 255, 255, int(170 * k)))
        del w
    return im


def red_vignette(k):
    a = np.zeros((H, W, 4), np.uint8)
    ys, xs = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xs - W / 2) / (W * 0.62)) ** 2 + ((ys - H / 2) / (H * 0.6)) ** 2)
    a[..., 0], a[..., 1], a[..., 2] = 220, 20, 40
    a[..., 3] = (np.clip(d - 0.55, 0, 1) * 400 * k).clip(0, 200).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def sfx_heartbeat():
    t = tt(0.5)
    out = np.zeros_like(t)
    for st, g in ((0.0, 1.0), (0.16, 0.7)):
        tt_ = np.clip(t - st, 0, None)
        out += (t >= st) * g * np.sin(2 * np.pi * (48 + 40 * np.exp(-tt_ * 30)) * tt_) * np.exp(-tt_ * 14)
    return np.tanh(2 * out) * 0.8


def beat_pulse(T):
    """1 right on a beat, decaying to 0 within ~0.18 s."""
    return max(0.0, 1 - (T % B) / 0.18)


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------

class Intro(mv.Scene):
    """6 beats: cold open on the glowing bonus country, a rapid-fire montage of mystery countries,
    then HARDEST / MAP QUIZ / 99% FAIL over the spinning globe and a whip into country 1."""

    TEASE, MONTAGE = "GMB", ("CUB", "LAO", "HRV", "MWI")
    TITLE = ("HARDEST", "MAP QUIZ")

    def __init__(self, globe, ui, tts):
        super().__init__()
        self.globe, self.ui = globe, ui
        self.dur = 6 * B
        self.t1, self.t2 = 1.5 * B, 3.5 * B          # cold open | montage | globe
        w = globe.world

        def view(code, zf=1.0):
            c, near, _ = w.country(code)
            return c, G.zoom_for(w, c, near, W, H, 0.34, 0.2) * zf, near
        self.tease = view(self.TEASE, 0.8)
        self.cuts = [view(c) for c in self.MONTAGE]
        self.o1 = rtext("ONLY 1% KNOW", 124, fill=PINK, stroke=12)
        self.o2 = rtext("THIS COUNTRY", 108, stroke=10)
        self.q = rtext("?", 300, stroke=18)
        self.o3 = join(rtext("answer at the end", 60, fill=GOLD, stroke=7), emoji("👀", 64))
        self.m1 = rtext("CAN YOU NAME", 108, stroke=10)
        self.m2 = rtext("ALL OF THEM?", 120, fill=CYAN, stroke=11)
        self.l1 = rtext(self.TITLE[0], 180, fill=PINK, stroke=14)
        self.l2 = rtext(self.TITLE[1], 150, stroke=13)
        self.l3 = join(rtext("99% FAIL", 120, fill=GOLD, stroke=11), emoji("💀", 120))
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9),
                        (B, sfx_heartbeat(), 0.8), (self.t2, mq.sfx_boom(), 0.9), (4 * B, mv.sfx_pop(), 0.9),
                        (4.5 * B, mq.sfx_boom(), 0.6), (4.5 * B, mv.sfx_riser(1.5 * B), 0.7),
                        (6 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k in range(len(self.cuts)):
            at = self.t1 + k * 0.5 * B
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mq.sfx_glitch(), 0.35), (at, mv.sfx_click(), 0.7)]
        if tts:
            self.voices.append((0.04, tts.say("Only one percent can name this!", speed=1.18)))

    def view(self, t):
        lon = -110 + 70 * clamp((t - self.t2) / (self.dur - self.t2)) ** 0.7  # settles on the start view
        return G.unit(lon, 28), 620.0

    def render(self, t):
        T = self.t0 + t
        if t < self.t1:                                   # cold open on the mystery country
            c, R, near = self.tease
            R *= (1.12 - 0.12 * ease_out_cubic(t / 0.3)) * (1 + 0.05 * beat_pulse(T))
            im = self.globe.render(c, R, CENTER, near, 1.0, lift=16 + 8 * math.sin(t * 9))
            im.alpha_composite(self.ui["shade"])
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.45 * beat_pulse(T)))])
            s = 1 + 0.08 * (1 - ease_out_cubic(t / 0.2))   # readable on frame one
            paste_center(im, scaled(self.o1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 300)
            paste_center(im, scaled(self.o2, s).rotate(2, Image.BICUBIC, expand=True), W / 2, 440)
            paste_center(im, scaled(self.q, 1 + 0.12 * math.sin(t * 12)).rotate(10 * math.sin(t * 6), Image.BICUBIC,
                                                                                   expand=True), 840, 1010)
            paste_center(im, self.o3, W / 2, 1480)
            im = shake(im, 26 * (1 - t / 0.3) if t < 0.3 else 0, t)
            im = rgb_split(im, 12 * (1 - clamp(t / 0.25)))
        elif t < self.t2:                                 # rapid-fire montage
            k = min(len(self.cuts) - 1, int((t - self.t1) / (0.5 * B)))
            tc = t - self.t1 - k * 0.5 * B
            c, R, near = self.cuts[k]
            im = self.globe.render(c, R * (1.08 - 0.08 * ease_out_cubic(tc / 0.15)), CENTER, near, 1.0, lift=14)
            im.alpha_composite(self.ui["shade"])
            s = 1 + 0.12 * (1 - ease_out_cubic((t - self.t1) / 0.15))
            paste_center(im, scaled(self.m1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 300)
            paste_center(im, scaled(self.m2, s).rotate(3, Image.BICUBIC, expand=True), W / 2, 440)
            paste_center(im, self.q, 840, 1010)
            im = rgb_split(im, 18 * (1 - clamp(tc / 0.12)))
            if tc < 0.06:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
        else:                                             # globe + title slams on the beats
            tg = t - self.t2
            c, R = self.view(t)
            R *= 1 + 0.06 * beat_pulse(T)
            im = self.globe.render(c, R, CENTER)
            im = rgb_split(im, 10 * (1 - clamp(tg / B)))
            im.alpha_composite(self.ui["shade"])
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 5, 30, 70)))
            b = int(tg / (0.5 * B))
            kk = (tg % (0.5 * B)) / (0.5 * B)
            slam = 1 + 0.35 * (1 - ease_out_cubic(kk / 0.4))
            paste_center(im, scaled(self.l1, slam if b == 0 else 1.0).rotate(-4, Image.BICUBIC, expand=True), W / 2,
                         400)
            if b >= 1:
                paste_center(im, scaled(self.l2, slam if b == 1 else 1.0).rotate(3, Image.BICUBIC, expand=True),
                             W / 2, 575)
            if b >= 2:
                paste_center(im, scaled(self.l3, slam if b == 2 else 1.0), W / 2, 1400)
            im = shake(im, 22 * (1 - kk) if kk < 0.4 and b <= 2 else 0, t)
            whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
            if whip > 0:
                im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Country(mv.Scene):
    def __init__(self, idx, q, prev_view, prev_tier, globe, ui, tts):
        super().__init__()
        code, fcode, name, fact, femoji, tier, prompt, said, sticker = q
        self.idx, self.globe, self.ui, self.tier = idx, globe, ui, tier
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = FLY_BEATS
        beats = f + (12 if self.bonus else 8) + (CTA_BEATS if self.cta else 0)
        self.dur = beats * B
        self.fly = f * B
        self.reveal = (f + (7 if self.bonus else 4)) * B
        self.count_beats = list(range(f + 2, f + 7)) if self.bonus else [f + 1, f + 2, f + 3]
        c, self.near, _ = globe.world.country(code)
        self.view = (c, G.zoom_for(globe.world, c, self.near, W, H, 0.34, 0.2))
        self.cam = mm.Camera(prev_view, self.view, self.fly, self.dur)
        self.flag = Image.open(os.path.join(FLAG_DIR, fcode + ".png")).convert("RGBA")
        self.cols = mm.flag_colours(self.flag)
        self.tiles = mm.Tiles(name, tier in ("INSANE", "IMPOSSIBLE", "BONUS"))
        size = 42
        while rfont(size).getlength(fact) > 760 and size > 26:
            size -= 1
        body = join(emoji(femoji, 52), rtext(fact, size, stroke=0), gap=14)
        self.fact = rounded_card(body.width + 56, body.height + 22, (body.height + 22) // 2, INK + (225,))
        paste_center(self.fact, body, self.fact.width / 2, self.fact.height / 2)
        self.sticker = emoji(sticker, 150)
        col, e = TIERS[tier]
        self.count = rtext("BONUS" if self.bonus else f"{idx}/10", 46, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, col + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.level_up = tier != prev_tier and idx > 1
        self.banner = None
        if self.level_up:
            label = "BONUS: ONLY 1% KNOW THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 62 if self.bonus else 92, fill=col, stroke=9), emoji(e, 90))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        self.nums = {n: rtext(str(n), 230, fill=PINK if n == 1 else (255, 255, 255), stroke=16)
                     for n in range(1, len(self.count_beats) + 1)}
        self.streak = {n: join(rtext(f"x{n}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for n in (idx - 1, idx)}
        # sounds: whip in, ticks on the beats, heartbeat on hard levels, big reveal
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (self.fly, mv.sfx_pop(), 0.8)]
        for j, b in enumerate(self.count_beats):
            self.sounds.append((b * B, mq.sfx_tock(high=j == len(self.count_beats) - 1), 1.0))
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        self.sounds += [(self.reveal, mq.sfx_boom(), 0.9), (self.reveal, mv.sfx_ding(), 1.0),
                        (self.reveal + 0.05, mq.sfx_pling(), 0.6), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        for i in range(len(self.tiles.pos)):
            self.sounds.append((self.reveal + 0.07 + 0.035 * i, mv.sfx_click(), 0.5))
        if tts:
            v = tts.say(prompt, speed=1.18)
            self.voices.append((0.12, v))
            if 0.12 + len(v) / SR > self.count_beats[0] * B + 0.1:
                print(f"warning: prompt {idx} runs into the countdown", flush=True)
            self.voices.append((self.reveal + 0.08, tts.say(said, speed=1.12)))
            if self.cta:
                v = tts.say(CTA_LINE, speed=1.12)
                self.voices.append((self.reveal + CTA_AT, v))
                if self.reveal + CTA_AT + len(v) / SR > self.dur - 0.2:
                    print(f"warning: the like line after {idx} runs into the next country", flush=True)
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            self.sounds += [(self.reveal + CTA_AT, mv.sfx_pop(), 0.9), (self.reveal + CTA_AT + 0.02, mq.sfx_pling(), 0.5),
                            (self.reveal + CTA_AT + 0.45, mv.sfx_click(), 0.8)]
        r = random.Random(idx * 31)
        self.conf = [(r.uniform(-1, 1) * 700, r.uniform(-1350, -450), r.randint(12, 26), r.choice(self.cols),
                      r.uniform(0, 3)) for _ in range(60)]

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        c, R, blur = self.cam.at(t)
        if t > self.fly:
            R *= 1 + 0.03 * beat_pulse(T)               # bass bounce on every beat
        if 0 < rv < 0.35:
            R *= 1 + 0.09 * (1 - rv / 0.35)             # zoom punch
        hl = clamp((t - self.fly + 0.3) / 0.3)
        fa = clamp(rv / 0.15) if rv > 0 else 0.0
        lift = 26 * ease_out_back(clamp(rv / 0.3)) if rv > 0 else 0.0
        im = self.globe.render(c, R, CENTER, self.near, hl, self.flag, fa, lift=lift)
        im = mm.zoom_blur(im, blur)
        im = rgb_split(im, 22 * blur)                    # whip
        im.alpha_composite(self.ui["shade"])
        if self.danger and 0 < t < self.reveal:          # red heartbeat vignette
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv > 0:
            im.alpha_composite(speed_lines(1 - clamp(rv / 0.45), self.idx))
        d = ImageDraw.Draw(im)
        # top bar: count, timer, tier tag, streak
        paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
        x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
        frac = 1.0 if t < self.fly else max(0.0, 1 - (t - self.fly) / (self.reveal - self.fly))
        d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
        colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
        if frac > 0.01:
            d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 11, fill=colr + (255,))
        paste_center(im, self.tag, x0 + self.tag.width / 2, 285)
        n = self.idx if rv > 0 else self.idx - 1
        if n > 0:
            s = 1 + 0.5 * (1 - ease_out_cubic(rv / 0.25)) if 0 < rv < 0.25 else 1.0
            st = self.streak[n]
            paste_center(im, scaled(st, s), x1 - st.width / 2 + 10, 288)
        # level banner
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            s = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, s).rotate(-4, Image.BICUBIC, expand=True), W / 2, 430, a)
        # big 3-2-1 slams on the beats
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                s = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, s).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a * 0.82)
        # hint tiles, reveal
        self.tiles.draw(im, t - self.fly - B, rv)
        if rv > 0:
            cx, cy = getattr(self.globe, "last_hl_center", CENTER)
            for vx, vy, sz, cc, spin in self.conf:
                px, py = cx + vx * rv, cy + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            sk = ease_out_back((rv - 0.12) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             900, 1130)
            fk = ease_out_back((rv - 0.35) / 0.3)
            if fk > 0.01:
                paste_center(im, scaled(self.fact, fk), W / 2, mm.FACT_Y)
            f = 1 - clamp(rv / 0.14)
            if f > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(190 * f))))
            im = shake(im, 30 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 16 * (1 - rv / 0.18))
        if self.cta and rv > CTA_AT:                     # "like this video" card
            ct = rv - CTA_AT
            k = ease_out_back(ct / 0.3, 2.0) * (1 - ease_in_cubic(clamp((t - (self.dur - 0.45)) / 0.25)))
            if k > 0.01:
                card = self.cta_card.copy()
                tap = 1 - 0.18 * math.sin(math.pi * clamp((ct - 0.45) / 0.2))   # the thumb "presses" like
                th = scaled(self.thumb, tap * (1 + 0.08 * beat_pulse(T))).rotate(10 * math.sin(ct * 7), Image.BICUBIC,
                                                                                 expand=True)
                paste_center(card, th, 98, 98)
                s = k * (1 + 0.025 * beat_pulse(T))
                paste_center(im, scaled(card, s).rotate(-2, Image.BICUBIC, expand=True), W / 2, CTA_Y)
                rp = (ct - 0.5) / 0.45                    # ripple from the tap
                if 0 < rp < 1:
                    d = ImageDraw.Draw(im)
                    rr, cx = 70 + 110 * ease_out_cubic(rp), W / 2 - 312 * s
                    d.ellipse((cx - rr, CTA_Y - rr, cx + rr, CTA_Y + rr), outline=PINK + (int(255 * (1 - rp)),),
                              width=max(1, int(10 * (1 - rp))))
        if self.level_up and t < 0.35:                   # glitch into a harder level
            im = glitch(im, 1 - t / 0.35, int(t * 30) + self.idx * 7)
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(im, 20 * out)
        return im


class Ending(mv.Scene):
    """Score screen over the globe flying home; fades into the first frame so the Short loops."""

    def __init__(self, prev_view, globe, ui, intro, tts):
        super().__init__()
        self.globe, self.ui, self.intro = globe, ui, intro
        self.dur = 10 * B
        self.cam = mm.Camera(prev_view, START, 2 * B, self.dur)
        logo = Image.open(brand.round_logo()).convert("RGBA").resize((120, 120), Image.LANCZOS)
        logo.putalpha(mv.circle(120, (255, 255, 255, 255)).getchannel("A"))
        self.brand = join(logo, rtext(brand.NAME, 60, stroke=6), gap=18)
        self.title = rtext("HOW MANY?", 124, fill=CYAN, stroke=11)
        tiers = [("0-3", "Tourist", "📸"), ("4-5", "Backpacker", "🎒"), ("6-7", "Explorer", "🧭"),
                 ("8-9", "Map nerd", "🤓"), ("10", "Human globe", "🌍")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            colr = PINK if i == 4 else (255, 255, 255)
            row = rounded_card(780, 104, 52, INK + (210,), outline=(colr if i == 4 else (90, 70, 130)) + (255,),
                               width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 52), sc, font=rfont(60), fill=colr, anchor="lm")
            dr.text((210, 52), label, font=rfont(60, "SemiBold"), fill=colr, anchor="lm")
            row.alpha_composite(emoji(e, 60), (780 - 96, 22))
            self.rows.append(row)
        self.bonus = join(rtext("+ bonus = LEGEND", 58, fill=GOLD, stroke=6), emoji("👑", 62))
        self.cta = join(rtext("comment your score", 58, stroke=6), emoji("👇", 62))
        self.sounds += [(0.0, mv.sfx_whoosh(0.8), 0.7), (B, mq.sfx_levelup(), 0.9)]
        for i in range(5):
            self.sounds.append(((1.5 + 0.5 * i) * B, mv.sfx_pop(), 0.7))
        self.sounds.append((5 * B, mq.sfx_pling(), 0.7))
        if tts:
            self.voices.append((0.3, tts.say("How many did you get? Comment your score!", speed=1.12)))

    def render(self, t):
        c, R, blur = self.cam.at(t)
        if t > 2 * B:
            c = G.unit(-40 - 6 * (self.dur - t), 28)
        im = rgb_split(mm.zoom_blur(self.globe.render(c, R, CENTER), blur), 18 * blur)
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        a = 1 - out
        im.alpha_composite(Image.new("RGBA", (W, H), INK + (int(150 * clamp((t - 0.4) / 0.3) * a),)))
        paste_center(im, self.brand, W / 2, 300, clamp((t - B) / 0.2) * a)
        paste_center(im, scaled(self.title, ease_out_back((t - B) / 0.25)), W / 2, 460, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - (1.5 + 0.5 * i) * B) / 0.2)
            if k > 0:
                paste_center(im, row, W / 2 + (1 - k) * 160, 620 + i * 122, k * a)
        paste_center(im, scaled(self.bonus, ease_out_back((t - 4.5 * B) / 0.25)), W / 2, 1255, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 5 * B) / 0.25) * (1 + 0.03 * math.sin(t * 8))),
                     W / 2, 1350, a)
        if out > 0:
            first = self.intro.render(0.0)
            first.putalpha(first.getchannel("A").point(lambda v: int(v * out)))
            im.alpha_composite(first)
        return im


class VoicePack:
    """Pre-recorded narrator lines (e.g. ElevenLabs): DIR/lines.txt lists the text, DIR/00.wav... the audio."""

    def __init__(self, folders):
        """folders: one folder, or several separated by commas (earlier ones win)."""
        import wave
        self.clips = {}
        for folder in folders.split(","):
            with open(os.path.join(folder, "lines.txt")) as fh:
                texts = [ln.strip() for ln in fh if ln.strip()]
            for k, text in enumerate(texts):
                if text in self.clips:
                    continue
                with wave.open(os.path.join(folder, f"{k:02d}.wav")) as w:
                    assert w.getframerate() == SR, "voice pack clips must be 48 kHz"
                    self.clips[text] = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32767

    def say(self, text, speed=None):
        if text not in self.clips:
            raise KeyError(f"voice pack has no recording of {text!r}")
        return self.clips[text]


def build(voice="af_heart", voice_pack=None):
    globe = G.GlobeRenderer(W, H)
    tts = VoicePack(voice_pack) if voice_pack else (mv.TTS(voice, "en-us") if voice != "none" else None)
    ui = {"shade": mm.shade_overlay(), "vig": [red_vignette(i / 10) for i in range(11)]}
    intro = Intro(globe, ui, tts)
    scenes, view, prev = [intro], (intro.view(intro.dur)[0], 620.0), "MEDIUM"
    for i, q in enumerate(COUNTRIES, 1):
        sc = Country(i, q, view, prev if i > 1 else q[5], globe, ui, tts)
        scenes.append(sc)
        c, R = sc.view
        view, prev = (c, R * 1.07), q[5]
    scenes.append(Ending(view, globe, ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, globe


def make_cover(globe, path):
    code, lon, lat, zf, tiles = COVER
    c, near, _ = globe.world.country(code)
    R = G.zoom_for(globe.world, c, near, W, H, 0.36, 0.22) * zf
    im = globe.render(G.unit(lon, lat), R, (540, 1130), near, 1.0, lift=20)
    im = rgb_split(im, 6)
    im.alpha_composite(mm.shade_overlay())
    paste_center(im, mm.rtext("name this", 136, stroke=12), W / 2, 250)
    paste_center(im, mm.rtext("country", 166, fill=CYAN, stroke=14), W / 2, 420)
    paste_center(im, join(rtext("99% FAIL", 84, fill=PINK, stroke=8), emoji("💀", 86)).rotate(-4, Image.BICUBIC,
                                                                                              expand=True),
                 W / 2, 585)
    paste_center(im, rtext("?", 300, stroke=18), 830, 1090)
    mm.TILE_Y = 1520
    mm.Tiles(tiles, True).draw(im, 1.0, -1.0)
    mm.TILE_Y = 1292
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", type=int, default=3, choices=sorted(EPISODES))
    ap.add_argument("--out", default=None, help="default: short_map_quiz_<episode>.mp4")
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--music", default="phonk", choices=["phonk", "none"])
    ap.add_argument("--voice-pack", default=None, help="folder of recorded narrator lines (lines.txt + 00.wav...)")
    ap.add_argument("--audio-only", action="store_true", help="rebuild only the sound and swap it into --out")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    set_episode(a.episode)
    num = EPISODES[a.episode][4]
    a.out = a.out or os.path.join(HERE, f"short_map_quiz_{num}.mp4")
    quiet = a.stills or a.cover
    scenes, starts, total, globe = build(a.voice if not quiet else "none", None if quiet else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    if a.audio_only:  # same picture, new sound
        import make_movie_quiz as mmq
        work = os.path.join(mv.CACHE_DIR, f"render_map{num}")
        os.makedirs(work, exist_ok=True)
        src, wav = os.path.join(work, "video_src.mp4"), os.path.join(work, "audio_only.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.out, "-map", "0:v", "-c", "copy", src], check=True)
        mv.write_wav(wav, mmq.mix_audio(scenes, starts, total, a.music))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-c:a", "aac",
                        "-b:a", "192k", "-movflags", "+faststart", "-shortest", a.out], check=True)
        print(f"Done (audio only): {a.out}")
        return
    if a.cover:
        make_cover(globe, os.path.join(HERE, f"map_quiz_{num}_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"map{num}_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, f"render_map{num}")
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
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-c:v", "libx264", "-crf", "23", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.out], check=True)
    print(f"Done: {a.out}")


if __name__ == "__main__":
    main()
