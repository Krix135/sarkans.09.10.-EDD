#!/usr/bin/env python3
""""GUESS THE FLAG WITH NO COLOURS" Short (1080x1920).

Each round the whole screen is black and white: a flag waves in grey in the middle, with a hint (continent
and an emoji), letter tiles for the name and a 3-2-1 on the beat. On the drop colour floods out from the
flag across the entire screen with a paint splash, the tiles flip to the country's name and a fun fact
pops up. The traps are flags that look almost the same in grey (Italy / Ireland / Ivory Coast,
Romania / Chad). Spoken-title intro (6 beats) that ends with the title card bursting into colour,
EASY -> IMPOSSIBLE plus a bonus, one like call-out after round 3, looping score screen.
Flags: public domain.

    python3 make_no_colour_flag_quiz.py
    python3 make_no_colour_flag_quiz.py --stills 0,5,9
    python3 make_no_colour_flag_quiz.py --cover
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
import make_logo_quiz as lq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_missing_country_quiz as mcq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center, \
    rounded_card, scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
CARD_Y = 440
NUM_Y = 600
FC = (540, 975)                      # flag centre
FLAG_BOX = (860, 540)
mm.TILE_Y = 1400
FACT_Y = 1520
CTA_Y = 1600
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
AMP = 16                             # wave height in pixels

ROUNDS = [  # flag, name, hint, hint emoji, fact, fact emoji, tier, prompt, spoken answer, sticker
    ("JP", "JAPAN", "ASIA", "🍣", "its flag is called Hinomaru, the \"circle of the sun\"", "🌞", "EASY",
     "No colours! Guess the flag! Hint: Asia!", "Japan!", "😎"),
    ("CA", "CANADA", "NORTH AMERICA", "🏒", "the maple leaf flag only dates from 1965", "🍁", "EASY",
     "Hint: North America!", "Canada!", "🔥"),
    ("BR", "BRAZIL", "SOUTH AMERICA", "⚽", "the stars show the night sky over Rio in 1889", "✨", "EASY",
     "Hint: South America!", "Brazil!", "🤔"),
    ("DE", "GERMANY", "EUROPE", "🥨", "its black, red and gold go back to the 1800s", "📜", "MEDIUM",
     "Hint: Europe!", "Germany!", "😳"),
    ("IT", "ITALY", "EUROPE", "🍕", "its flag is nicknamed \"Il Tricolore\"", "🎨", "MEDIUM",
     "Hint: Europe, and pizza!", "Italy!", "🤯"),
    ("IN", "INDIA", "ASIA", "🏏", "the wheel in the middle has 24 spokes", "☸", "MEDIUM",
     "Hint: Asia!", "India!", "🔥"),
    ("IE", "IRELAND", "EUROPE", "☘", "the white stands for peace between the green and the orange", "🕊", "HARD",
     "Careful! Hint: Europe!", "Ireland! Not Italy!", "😱"),
    ("AR", "ARGENTINA", "SOUTH AMERICA", "🧉", "the sun on it is called the Sun of May", "☀", "HARD",
     "Hint: South America!", "Argentina!", "💀"),
    ("UA", "UKRAINE", "EUROPE", "🌻", "blue sky over golden wheat fields", "🌾", "INSANE",
     "Insane level! Hint: Europe!", "Ukraine!", "🧠"),
    ("CI", "IVORY COAST", "AFRICA", "🐘", "it's Ireland's flag flipped the other way round", "🔄", "IMPOSSIBLE",
     "Impossible level! Hint: Africa!", "Ivory Coast! Not Ireland!", "☠"),
    ("RO", "ROMANIA", "EUROPE", "🧛", "it's almost identical to Chad's flag", "🔍", "BONUS",
     "Bonus! Hint: Dracula's country!", "Romania!", "👑"),
]
INTRO_WORDS = ("Guess the flag", "with no colours!", "Ninety-nine percent fail!")


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


def grey(im):
    """Black-and-white version of an RGBA image (alpha kept)."""
    g = im.convert("L").convert("RGBA")
    g.putalpha(im.getchannel("A"))
    return g


class PaintWall(lq.BrandWall):
    EMOJIS = ["🎨", "🚩", "🖌", "🌍", "🏳", "❓", "🌈", "🎌"]


def framed_flag(code):
    fl = Image.open(os.path.join(FLAG_DIR, code + ".png")).convert("RGBA")
    k = min(FLAG_BOX[0] / fl.width, FLAG_BOX[1] / fl.height)
    fl = fl.resize((int(fl.width * k), int(fl.height * k)), Image.LANCZOS)
    b = 12
    out = Image.new("RGBA", (fl.width + 2 * b, fl.height + 2 * b + 2 * AMP))
    ImageDraw.Draw(out).rectangle((0, AMP, out.width - 1, AMP + fl.height + 2 * b - 1), fill=(255, 255, 255, 255))
    out.paste(fl, (b, AMP + b), fl)
    return out


def wave(img, t, amp=AMP):
    """Wave the flag like it's on a pole: the left edge stays still, the ripple grows to the right."""
    a = np.asarray(img)
    h, w = a.shape[:2]
    x = np.arange(w)
    ph = 2 * np.pi * x / (w * 0.85) - t * 4.2
    grow = 0.25 + 0.75 * x / w
    dy = np.round(amp * np.sin(ph) * grow).astype(int)
    rows = np.clip(np.arange(h)[:, None] - dy[None, :], 0, h - 1)
    out = a[rows, x[None, :]].astype(np.float32)
    shade = 1 + 0.13 * np.cos(ph) * grow
    out[..., :3] = np.clip(out[..., :3] * shade[None, :, None], 0, 255)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def shadow_for(img):
    s = Image.new("RGBA", (img.width + 80, img.height + 80))
    ImageDraw.Draw(s).rectangle((40, 40 + AMP, 40 + img.width, 40 + img.height - AMP), fill=(0, 0, 10, 150))
    return s.filter(ImageFilter.GaussianBlur(18))


def question_card(hint, em):
    a = join(rtext("WHICH COUNTRY'S FLAG IS THIS?", 50, stroke=6), emoji("🏳", 50), gap=10)
    h = join(rtext(f"HINT: {hint}", 44, fill=GOLD, stroke=5), emoji(em, 46), gap=10)
    pill = rounded_card(h.width + 40, h.height + 12, (h.height + 12) // 2, (40, 20, 70, 255), outline=GOLD + (255,),
                        width=3)
    paste_center(pill, h, pill.width / 2, pill.height / 2)
    card = rounded_card(min(1040, max(a.width, pill.width) + 60), a.height + pill.height + 48, 44, (14, 6, 40, 232),
                        outline=CYAN + (255,), width=5)
    paste_center(card, a, card.width / 2, 20 + a.height / 2)
    paste_center(card, pill, card.width / 2, 28 + a.height + pill.height / 2)
    return card


def sfx_splash():
    t = np.arange(int(0.55 * SR)) / SR
    n = np.random.default_rng(5).standard_normal(len(t))
    body = (mv.lowpass(n, 2600) - mv.lowpass(n, 300)) * np.exp(-t * 8)
    bloop = np.sin(2 * np.pi * np.cumsum(90 + 520 * np.exp(-t * 14)) / SR) * np.exp(-t * 12)
    x = 0.8 * body + 0.6 * bloop
    return x / (np.abs(x).max() + 1e-9)


class Flood:
    """Colour spreading out from a point: a soft-edged growing circle used as a mask."""

    def __init__(self):
        ys, xs = np.mgrid[0:H // 4, 0:W // 4]
        self.xs, self.ys = xs * 4.0, ys * 4.0

    def mask(self, cx, cy, r, soft=60):
        d = np.hypot(self.xs - cx, self.ys - cy)
        m = np.clip((r - d) / soft, 0, 1) * 255
        return Image.fromarray(m.astype(np.uint8), "L").resize((W, H), Image.BILINEAR)


def flood_mix(colour, k, cx, cy, flood):
    """k=0: all grey; k=1: all colour; in between colour spreads out from (cx, cy)."""
    if k >= 1:
        return colour
    g = grey(colour)
    if k <= 0:
        return g
    g.paste(colour, (0, 0), flood.mask(cx, cy, 2300 * k))
    return g


# ----------------------------------------------------------------------------
# rounds
# ----------------------------------------------------------------------------
class Round(mv.Scene):
    def __init__(self, idx, r, prev_tier, ui, tts):
        super().__init__()
        code, name, hint, hem, fact, femoji, tier, prompt, said, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        v_q = tts.say(prompt, speed=1.14) if tts else None
        q_len = len(v_q) / SR if v_q is not None else 1.6
        c0 = max(4 if not self.bonus else 5, math.ceil((0.12 + q_len - 0.1) / B))
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.reveal = (c0 + n) * B
        self.dur = self.reveal + (6 + (5 if self.cta else 0)) * B
        self.cta_at = 2.6 * B
        self.flag = framed_flag(code)
        self.shadow = shadow_for(self.flag)
        self.cols = mm.flag_colours(Image.open(os.path.join(FLAG_DIR, code + ".png")).convert("RGBA"))
        self.card = question_card(hint, hem)
        self.tiles = mm.Tiles(name, tier in ("HARD", "INSANE", "IMPOSSIBLE", "BONUS"))
        self.tile_at = 0.55
        fs = 42
        while rfont(fs).getlength(fact) > 780 and fs > 26:
            fs -= 1
        body = join(emoji(femoji, 52), rtext(fact, fs, stroke=0), gap=14)
        self.fact = rounded_card(body.width + 56, body.height + 22, (body.height + 22) // 2, INK + (232,))
        paste_center(self.fact, body, self.fact.width / 2, self.fact.height / 2)
        self.sticker = emoji(stick, 140)
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
        self.nums = {k: rtext(str(k), 128, fill=PINK if k == 1 else (255, 255, 255), stroke=12) for k in range(1, n + 1)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self.qmark = mv.circle(120, PINK + (255,))           # a "?" badge pinned to the flag's corner
        ImageDraw.Draw(self.qmark).ellipse((4, 4, 115, 115), outline=(255, 255, 255, 255), width=6)
        paste_center(self.qmark, rtext("?", 84, stroke=0), 60, 62)
        self.q_xy = (FC[0] + self.flag.width / 2 - 20, FC[1] - self.flag.height / 2 + AMP + 18)
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (0.3, mq.sfx_boom(), 0.5), (0.3, mv.sfx_pop(), 0.7)]
        for i in range(len(self.tiles.pos)):
            self.sounds.append((self.tile_at + 0.02 * i, mv.sfx_click(), 0.3))
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        if self.danger:
            self.sounds.append((self.count_beats[-1] * B, mq.sfx_boom(), 0.6))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        rv0 = self.reveal
        self.sounds += [(rv0, mq.sfx_boom(), 1.0), (rv0, sfx_splash(), 1.0), (rv0 + 0.03, mv.sfx_ding(), 0.8),
                        (rv0 + 0.1, mq.sfx_pling(), 0.6), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        for i in range(len(self.tiles.pos)):
            self.sounds.append((rv0 + 0.07 + 0.035 * i, mv.sfx_click(), 0.5))
        if tts:
            self.voices.append((0.12, v_q))
            self.voices.append((self.reveal + 0.08, tts.say(said, speed=1.12)))
            if self.cta:
                self.voices.append((self.reveal + self.cta_at, tts.say(CTA_LINE, speed=1.12)))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = self.reveal + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, mq.sfx_pling(), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        rr = random.Random(idx * 53)
        self.blobs = [(rr.uniform(0, 2 * math.pi), rr.uniform(500, 1500), rr.uniform(14, 40), rr.choice(self.cols))
                      for _ in range(46)]

    def scene(self, t, rv):
        """Background and the waving flag, in colour (greyed or flooded by the caller)."""
        T = self.t0 + t
        pulse = beat_pulse(T) if t > 0.5 else 0.0
        im = self.ui["bg"].render(T, self.col, strobe=pulse * 0.4 + (1 - clamp(rv / 0.25) if rv > 0 else 0),
                                  rays=0.7)
        k = ease_out_back(clamp(t / 0.4), 1.5)
        s = (0.55 + 0.45 * k) * (1 + 0.015 * pulse)
        if rv <= 0:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.25:
                    s *= 1 + (0.06 if self.danger else 0.04) * (1 - ease_out_cubic(tb / 0.25))
        else:
            s *= 1 + 0.1 * (1 - ease_out_cubic(clamp(rv / 0.35)))
        fl = wave(self.flag, T)
        paste_center(im, scaled(self.shadow, s), FC[0] + 16, FC[1] + 26, min(1.0, k))
        rot = -2 * (1 - k)
        sp = scaled(fl, s)
        if abs(rot) > 0.05:
            sp = sp.rotate(rot, Image.BICUBIC, expand=True)
        paste_center(im, sp, FC[0], FC[1] - (1 - min(1.0, k)) * 300)
        return im

    def render(self, t, header=True):
        T = self.t0 + t
        rv = t - self.reveal
        ui = self.ui
        colour = self.scene(t, rv)
        kf = ease_out_cubic(clamp(rv / 0.45)) if rv > 0 else 0.0
        im = flood_mix(colour, kf, FC[0], FC[1], ui["flood"])
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if 0.4 < t and rv <= 0:                              # the "?" badge bounces on the beat
            kq = ease_out_back(clamp((t - 0.4) / 0.3), 2.2)
            paste_center(im, scaled(self.qmark, kq * (1 + 0.1 * beat_pulse(T))).rotate(12 * math.sin(T * 3),
                                                                                       Image.BICUBIC, expand=True),
                         *self.q_xy)
        d = ImageDraw.Draw(im)
        if header:
            paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
            x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
            frac = 1.0 if t < 0.5 else max(0.0, 1 - (t - 0.5) / (self.reveal - 0.5))
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
        self.tiles.draw(im, t - self.tile_at, rv)
        if self.banner is not None and 0.05 < t < 0.75:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - 0.45) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, FC[1], a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a * 0.9)
        cta_on = self.cta and rv > self.cta_at
        if rv > 0:
            dd = ImageDraw.Draw(im)                          # paint blobs splashing out in the flag's colours
            for ang, sp_, r_, cc in self.blobs:
                k = rv
                px = FC[0] + math.cos(ang) * sp_ * k
                py = FC[1] + math.sin(ang) * sp_ * k + 1800 * k * k
                rr_ = r_ * (1 - clamp((rv - 0.6) / 0.5))
                if rr_ > 1 and py < H:
                    dd.ellipse((px - rr_, py - rr_, px + rr_, py + rr_), fill=cc + (255,), outline=INK + (255,),
                               width=2)
            sk = ease_out_back((rv - 0.3) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             930, 1250)
            fk = ease_out_back((rv - 0.7) / 0.3)
            if fk > 0.01 and not cta_on:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            fl = 1 - clamp(rv / 0.12)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * fl))))
            im = shake(im, 30 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 16 * (1 - rv / 0.18))
        else:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 14 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 10 * (1 - tb / 0.15))
            tb = t - self.count_beats[-1] * B
            if self.danger and 0 <= tb < 0.2:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 30, 60, int(90 * (1 - tb / 0.2)))))
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
                                                                                     expand=True), W / 2, CTA_Y)
        if self.level_up and t < 0.35:
            im = glitch(im, 1 - t / 0.35, int(t * 30) + self.idx * 7)
        if t < 0.16:
            im = rgb_split(mm.zoom_blur(im, 0.6 * (1 - t / 0.16)), 16 * (1 - t / 0.16))
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(mm.zoom_blur(im, 0.6 * out), 20 * out)
        return im


# ----------------------------------------------------------------------------
# intro: the title, said and slammed in word by word over grey flags, then the title bursts into colour
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    TEASE, MONTAGE = 10, (9, 6)

    def __init__(self, ui, tts, rounds):
        super().__init__()
        self.ui, self.rounds = ui, rounds
        self.dur = 6 * B
        hb = 0.5 * B
        clips = [tts.say(w, speed=1.24) for w in INTRO_WORDS] if tts else None
        lens = [len(c) / SR for c in clips] if clips else [0.7, 0.85, 1.0]
        self.slams = [0.0]
        for ln in lens:
            prev = self.slams[-1]
            self.slams.append(max(prev + hb, round((prev + ln - 0.08) / hb) * hb))
        self.slams[-1] = min(self.slams[-1], self.dur - 0.4)
        if clips:
            for at, c in zip(self.slams, clips):
                self.voices.append((at, c))
        self.o3 = join(rtext("answer at the end", 58, fill=GOLD, stroke=7), emoji("👀", 62))
        self.w1 = fit(rtext("GUESS THE FLAG", 150, stroke=14), 990)
        self.w2 = fit(join(rtext("WITH NO COLOURS", 116, fill=(255, 255, 255), stroke=11), emoji("⚫", 96),
                           emoji("⚪", 96), gap=10), 990)
        self.w3 = join(rtext("99% FAIL", 150, fill=PINK, stroke=14), emoji("💀", 140))
        self.l1 = fit(rtext("GUESS THE FLAG", 130, stroke=12), 990)
        self.l2 = fit(join(rtext("WITH NO COLOURS", 100, fill=CYAN, stroke=10), emoji("🎨", 90), gap=12), 990)
        self.l3 = join(rtext("99% FAIL", 116, fill=PINK, stroke=11), emoji("💀", 112))
        self.sounds += [(0.0, sfx_heartbeat(), 0.9), (B, sfx_heartbeat(), 0.7),
                        (self.slams[2], mv.sfx_riser(self.slams[3] - self.slams[2]), 0.6),
                        (self.slams[3], sfx_splash(), 1.0), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k, at in enumerate(self.slams):
            self.sounds += [(at, mq.sfx_boom(), 1.0 if k in (0, 3) else 0.75), (at, mv.sfx_whoosh(0.35), 0.6),
                            (at, mv.sfx_pop(), 0.8)]
            if k:
                self.sounds.append((at, mq.sfx_glitch(), 0.45))

    def render(self, t):
        T = self.t0 + t
        k = max(i for i, at in enumerate(self.slams) if at <= t + 1e-9)
        ts = t - self.slams[k]
        slam = 1 + 0.35 * (1 - ease_out_cubic(clamp(ts / 0.18)))
        if k < 3:                                            # word slams over grey flags
            r = self.rounds[(self.TEASE, self.MONTAGE[0], self.MONTAGE[1])[k]]
            im = grey(r.scene(r.count_beats[0] * B - 0.1, -1))
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 110)))
            words = [(self.w1, 330, -3), (self.w2, 500, 2), (self.w3, 1520, -2)]
            for j in range(k + 1):
                img, y, rot = words[j]
                sc = (slam if j == k else 1.0) * (1 + 0.025 * beat_pulse(T))
                paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
            if k < 2:
                paste_center(im, self.o3, W / 2, 1745)
            im = shake(im, 24 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
            im = rgb_split(im, (8 if k == 0 else 16) * (1 - clamp(ts / 0.15)))
            if k > 0:
                im = mm.zoom_blur(im, 0.6 * (1 - clamp(ts / 0.1)))
                if ts < 0.06:
                    im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            return im
        gc = (540, 1270)                                     # the title card bursts into colour
        R = 470 * (1 + 0.05 * beat_pulse(T)) * (1.25 - 0.25 * ease_out_cubic(clamp(ts / 0.3)))
        c = G.unit(10 + 50 * t, 25)
        im = self.ui["big_globe"].render(c, R, gc)
        self.ui["cmap"].draw(im, c, R, gc, None, 0.85)
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 40)))
        for j, (img, y, rot) in enumerate([(self.l1, 330, -3), (self.l2, 490, 2), (self.l3, 660, -2)]):
            sc = (slam if j == 2 else 1 + 0.12 * (1 - ease_out_cubic(clamp(ts / 0.18)))) * (1 + 0.03 * beat_pulse(T))
            paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
        im = flood_mix(im, ease_out_cubic(clamp((ts - 0.04) / 0.3)), W / 2, 900, self.ui["flood"])
        im = shake(im, 22 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
        whip = ease_in_cubic((t - (self.dur - 0.12)) / 0.12)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


def build(voice="am_adam", voice_pack=None):
    if voice_pack:
        tts = cq.Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    world = G.World()
    globe = G.GlobeRenderer(W, H, world)
    ui = {"bg": PaintWall(), "vig": [mc.red_vignette(i / 10) for i in range(11)], "big_globe": globe,
          "cmap": mcq.ColourMap(world), "flood": Flood()}
    rounds, prev = [], ROUNDS[0][6]
    for i, r in enumerate(ROUNDS, 1):
        rounds.append(Round(i, r, prev, ui, tts))
        prev = r[6]
    intro = Intro(ui, tts, rounds)
    scenes = [intro, *rounds, bq.Ending(ui, intro, tts)]
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(scenes, ui, path):
    r = scenes[1 + 6]                                        # Ireland in grey: everyone says Italy
    im = r.render(r.count_beats[0] * B + 0.43, header=False)
    im.alpha_composite(Image.new("RGBA", (W, 300), (10, 0, 30, 140)), (0, 0))
    paste_center(im, fit(rtext("GUESS THE FLAG", 120, stroke=12), 1000).rotate(-3, Image.BICUBIC, expand=True),
                 W / 2, 118)
    paste_center(im, fit(join(rtext("WITH NO COLOURS", 88, fill=CYAN, stroke=9), emoji("🎨", 80), gap=10), 1000)
                 .rotate(2, Image.BICUBIC, expand=True), W / 2, 238)
    paste_center(im, join(rtext("99% FAIL", 104, fill=PINK, stroke=10), emoji("💀", 104)), W / 2, 1745)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_no_colour_flag_quiz.mp4"))
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
        make_cover(scenes, ui, os.path.join(HERE, "no_colour_flag_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"nocol_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_no_colour_flag")
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
