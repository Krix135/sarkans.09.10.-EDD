#!/usr/bin/env python3
""""FIND THE ODD EMOJI: CHRISTMAS EDITION" Short (1080x1920).

Each round a grid of Christmas emojis pops in row by row on a snowy, candy-cane-framed board. One of them
is different: another emoji at first (a pine tree among Christmas trees, Mrs Claus among Santas), and in
the hard rounds the same emoji mirrored or turned. A timer ticks on every beat with a 3-2-1 at the end;
on the drop every other emoji dims, the board zooms in on the odd one, a ring and shockwaves mark it and
its name pops up. The grids get bigger every round. Falling snow, twinkling lights and our Jingle Bells
track; spoken-title intro (6 beats), EASY -> IMPOSSIBLE plus a bonus, one like call-out after round 3 and
a Christmas score screen that loops back to the start.

    python3 make_odd_emoji_quiz.py
    python3 make_odd_emoji_quiz.py --stills 0,5,9
    python3 make_odd_emoji_quiz.py --cover
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
from PIL import Image, ImageDraw, ImageFilter, ImageOps  # noqa: E402

import brand  # noqa: E402
import christmas_music as xm  # noqa: E402
import make_christmas_quiz as xq  # noqa: E402
import make_club_quiz as cq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center, \
    rounded_card, scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
CARD_Y = 438
BOARD_C = (540, 1085)
BOARD_W, BOARD_H = 1000, 1010
NUM_Y = 600
CTA_Y = 1690
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
XRED, XGREEN = xq.XRED, xq.XGREEN

ROUNDS = [  # main emoji, odd emoji (or the main one transformed), transform, cols, rows, search beats, tier,
    #         prompt, spoken answer, answer label, sticker
    ("🎄", "🌲", None, 6, 6, 8, "EASY", "Find the odd one out! Quick!", "A pine tree!", "PINE TREE", "😎"),
    ("🔔", "🛎", None, 6, 6, 8, "EASY", "Next!", "A hotel bell!", "HOTEL BELL", "🔥"),
    ("🎅", "🤶", None, 7, 7, 8, "EASY", "Find the odd one!", "Mrs Claus!", "MRS CLAUS", "🤔"),
    ("🦌", "🦌", "mirror", 7, 7, 9, "MEDIUM", "Medium level!", "This reindeer looks the other way!",
     "FACING THE OTHER WAY", "😳"),
    ("🧤", "🧦", None, 7, 8, 9, "MEDIUM", "Find it!", "Socks!", "SOCKS", "🤯"),
    ("⭐", "🌟", None, 8, 8, 9, "MEDIUM", "Look closely!", "The glowing star!", "GLOWING STAR", "🔥"),
    ("⛄", "☃", None, 8, 8, 10, "HARD", "Hard level!", "This snowman has snow!", "SNOWMAN WITH SNOW", "😱"),
    ("🎁", "🎁", "rot90", 8, 9, 10, "HARD", "Find the odd present!", "This present is turned!",
     "TURNED SIDEWAYS", "💀"),
    ("🧦", "🧦", "mirror", 9, 9, 10, "INSANE", "Insane level!", "These socks are flipped!", "FLIPPED", "🧠"),
    ("🧣", "🧣", "mirror", 9, 10, 10, "IMPOSSIBLE", "Impossible level!", "This scarf is flipped!", "FLIPPED",
     "☠"),
    ("❄", "❄", "rot15", 10, 10, 12, "BONUS", "Bonus! Only one percent find this!", "This snowflake is turned!",
     "TURNED A LITTLE", "👑"),
]
INTRO_WORDS = ("Find the odd one!", "Christmas edition!", "Ninety-nine percent fail!")
END_LINE = "How many did you find? Comment your score!"


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


def zoom_about(img, s, cx, cy):
    """Scale a full-frame layer by s, keeping the point (cx, cy) where it is."""
    if abs(s - 1) < 1e-3:
        return img
    big = scaled(img, s)
    x0, y0 = int(cx * s - cx), int(cy * s - cy)
    return big.crop((x0, y0, x0 + W, y0 + H))


def transform(im, kind):
    if kind == "mirror":
        return ImageOps.mirror(im)
    if kind == "rot90":
        return im.rotate(90, Image.BICUBIC)
    if kind == "rot15":
        return im.rotate(15, Image.BICUBIC)
    return im


class NightSky:
    """Night-blue backdrop with soft red and green glows, falling snow and twinkling Christmas lights."""

    def __init__(self):
        self.base = mv.vgradient(W, H, (10, 16, 46), (34, 10, 44)).convert("RGBA")
        paste_center(self.base, mv.soft_circle(1100, XRED + (60,), 260), 160, 500)
        paste_center(self.base, mv.soft_circle(1100, XGREEN + (55,), 260), 920, 1600)
        self.snow = xq.Snow(120, seed=9)
        self.lights = xq.light_string()

    def render(self, T, strobe=0.0):
        im = self.base.copy()
        self.snow.draw(im, T, 0.9)
        im.alpha_composite(self.lights[int(T / (0.5 * B)) % 2])
        if strobe > 0.01:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(40 * strobe))))
        return im


def board_frame():
    """Cream board with a candy-cane border and snow piled on top."""
    w, h = BOARD_W, BOARD_H
    pad = 40
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad))
    sh = Image.new("L", im.size)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 14, pad + w, pad + h + 14), 56, fill=170)
    im.paste(Image.new("RGBA", im.size, (0, 0, 10, 255)), (0, 0), sh.filter(ImageFilter.GaussianBlur(16)))
    stripes = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(stripes)
    for k in range(-h, w + h, 56):
        d.polygon([(k, 0), (k + 28, 0), (k + 28 - h, h), (k - h, h)], fill=XRED + (255,))
    base = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    base.alpha_composite(stripes)
    m = Image.new("L", (w * 2, h * 2))
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 2 - 1, h * 2 - 1), 112, fill=255)
    base.putalpha(m.resize((w, h), Image.LANCZOS))
    inner = Image.new("RGBA", (w, h))
    ImageDraw.Draw(inner).rounded_rectangle((22, 22, w - 23, h - 23), 40, fill=(253, 249, 240, 255),
                                            outline=(255, 255, 255, 255), width=4)
    base.alpha_composite(inner)
    im.alpha_composite(base, (pad, pad))
    cap = Image.new("RGBA", im.size)                          # snow on top, with icicles
    cd = ImageDraw.Draw(cap)
    r = random.Random(3)
    for x in range(pad + 70, pad + w - 60, 38):
        hh = r.uniform(26, 40)
        cd.ellipse((x - 36, pad - hh * 0.55, x + 36, pad + hh * 0.75), fill=(250, 253, 255, 255))
    for x in range(pad + 110, pad + w - 80, 120):
        ln = r.uniform(24, 46)
        cd.polygon([(x - 9, pad + 18), (x + 9, pad + 18), (x, pad + 18 + ln)], fill=(225, 242, 255, 255))
    shadow = Image.new("RGBA", im.size, (120, 150, 200, 0))
    shadow.putalpha(cap.getchannel("A").filter(ImageFilter.GaussianBlur(5)).point(lambda v: v * 90 // 255))
    im.alpha_composite(shadow, (0, 5))
    im.alpha_composite(cap)
    return im


def question_card():
    a = join(rtext("FIND THE ODD ONE OUT", 60, stroke=6), emoji("👀", 60), gap=12)
    h = join(rtext("ONE OF THEM IS DIFFERENT", 40, fill=GOLD, stroke=5), emoji("🔍", 42), gap=10)
    pill = rounded_card(h.width + 40, h.height + 12, (h.height + 12) // 2, (40, 20, 70, 255), outline=GOLD + (255,),
                        width=3)
    paste_center(pill, h, pill.width / 2, pill.height / 2)
    card = rounded_card(max(a.width, pill.width) + 70, a.height + pill.height + 48, 44, (14, 6, 40, 232),
                        outline=XRED + (255,), width=6)
    paste_center(card, a, card.width / 2, 20 + a.height / 2)
    paste_center(card, pill, card.width / 2, 28 + a.height + pill.height / 2)
    return card


# ----------------------------------------------------------------------------
# rounds
# ----------------------------------------------------------------------------
class Round(mv.Scene):
    def __init__(self, idx, r, prev_tier, ui, tts):
        super().__init__()
        main, odd, kind, cols, rows, search, tier, prompt, said, label, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        self.cols, self.rows = cols, rows
        self.entry = 0.5
        self.count_beats = list(range(search - 2, search + 1))   # the last three beats are the 3-2-1
        self.reveal = (search + 1) * B
        self.dur = self.reveal + (5 + (5 if self.cta else 0)) * B
        self.cta_at = 2.6 * B
        # the grid
        cell = min((BOARD_W - 90) / cols, (BOARD_H - 110) / rows)
        self.cell = cell
        size = int(cell * 0.82)
        e_main = emoji(main, size)
        e_odd = transform(emoji(odd, size), kind)
        rr = random.Random(idx * 97 + 5)
        self.odd_rc = (rr.randint(1, rows - 2), rr.randint(1, cols - 2)) if rows > 4 else (2, 2)
        gx0 = BOARD_C[0] - cell * (cols - 1) / 2
        gy0 = BOARD_C[1] + 14 - cell * (rows - 1) / 2
        self.cells = [(r_, c_, gx0 + c_ * cell, gy0 + r_ * cell) for r_ in range(rows) for c_ in range(cols)]
        self.odd_xy = (gx0 + self.odd_rc[1] * cell, gy0 + self.odd_rc[0] * cell)
        self.e_main, self.e_odd = e_main, e_odd
        self.board = ui["board"]
        full = Image.new("RGBA", (W, H))                    # the finished board, as one layer
        paste_center(full, self.board, *BOARD_C)
        for r_, c_, x, y in self.cells:
            e = e_odd if (r_, c_) == self.odd_rc else e_main
            paste_center(full, e, x, y)
        self.full = full
        dim = full.copy()                                    # every other emoji faded out for the reveal
        veil = Image.new("RGBA", (W, H))
        vd = ImageDraw.Draw(veil)
        bx0, by0 = BOARD_C[0] - BOARD_W / 2 + 24, BOARD_C[1] - BOARD_H / 2 + 24
        vd.rounded_rectangle((bx0, by0, bx0 + BOARD_W - 48, by0 + BOARD_H - 48), 40, fill=(253, 249, 240, 200))
        dim.alpha_composite(veil)
        paste_center(dim, e_odd, *self.odd_xy)
        self.dim = dim
        self.ring = self.make_ring(cell)
        tag = join(emoji(odd if kind is None else main, 54), rtext(label, 50, fill=(255, 255, 255), stroke=6), gap=12)
        self.answer = rounded_card(tag.width + 50, tag.height + 24, (tag.height + 24) // 2, (24, 150, 80, 250),
                                   outline=(255, 255, 255, 255), width=5)
        paste_center(self.answer, tag, self.answer.width / 2, self.answer.height / 2)
        self.sticker = emoji(stick, 140)
        self.col, e = TIERS[tier]
        self.count = rtext("BONUS" if self.bonus else f"{idx}/10", 46, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, self.col + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.size_tag = rtext(f"{cols * rows} EMOJIS", 30, fill=(220, 220, 240), stroke=4)
        self.level_up = tier != prev_tier and idx > 1
        self.banner = None
        if self.level_up:
            label_ = "BONUS: ONLY 1% FIND IT" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label_, 66 if self.bonus else 96, fill=self.col, stroke=9), emoji(e, 92))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        self.nums = {k: rtext(str(k), 128, fill=XRED if k == 1 else (255, 255, 255), stroke=12) for k in range(1, 4)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8)]
        for k in range(rows):                                # rows popping in
            self.sounds.append((0.05 + k * 0.03, mv.sfx_click(), 0.35))
        self.sounds += [(0.05 + rows * 0.03, mv.sfx_pop(), 0.7), (0.05 + rows * 0.03, xm.sleigh(idx, 0.7), 0.5)]
        for b in range(2, search - 2):                       # the clock ticking
            self.sounds.append((b * B, mv.sfx_click(), 0.55 if b % 2 else 0.4))
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == 2), 1.0), (b * B, xm.sfx_chime(79 + 2 * j), 0.3)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        if self.danger:
            self.sounds.append((self.count_beats[-1] * B, mq.sfx_boom(), 0.6))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        rv0 = self.reveal
        self.sounds += [(rv0, mq.sfx_boom(), 1.0), (rv0, mv.sfx_ding(), 1.0), (rv0 + 0.02, xm.sfx_jingle(), 0.8),
                        (rv0 + 0.45, mv.sfx_pop(), 0.8), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        if tts:
            v_q = tts.say(prompt, speed=1.16)
            self.voices.append((0.15, v_q))
            self.voices.append((self.reveal + 0.1, tts.say(said, speed=1.12)))
            if self.cta:
                self.voices.append((self.reveal + self.cta_at, tts.say(CTA_LINE, speed=1.12)))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=XRED + (255,), width=6)
            paste_center(self.cta_card, rtext(f"FOUND {idx}/{idx} SO FAR?", 50, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = self.reveal + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, xm.sfx_chime(84), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        rr = random.Random(idx * 31)
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1350, -450), rr.randint(12, 26),
                      rr.choice([XRED, XGREEN, GOLD, (255, 255, 255)]), rr.uniform(0, 3)) for _ in range(60)]

    @staticmethod
    def make_ring(cell):
        s = int(cell * 1.5)
        im = Image.new("RGBA", (s * 2, s * 2))
        d = ImageDraw.Draw(im)
        d.ellipse((8, 8, 2 * s - 8, 2 * s - 8), outline=(255, 255, 255, 255), width=22)
        d.ellipse((14, 14, 2 * s - 14, 2 * s - 14), outline=XRED + (255,), width=12)
        return im.resize((s, s), Image.LANCZOS)

    def board_layer(self, t, rv):
        """The board with its emojis: rows pop in, then it sits still; after the drop it zooms on the odd one."""
        if t < self.entry:                                   # rows drop in one after another
            im = Image.new("RGBA", (W, H))
            kb = ease_out_back(clamp(t / 0.3), 1.4)
            paste_center(im, scaled(self.board, 0.7 + 0.3 * kb), *BOARD_C, min(1.0, kb * 1.5))
            for r_, c_, x, y in self.cells:
                k = clamp((t - 0.05 - r_ * 0.03) / 0.18)
                if k > 0:
                    e = self.e_odd if (r_, c_) == self.odd_rc else self.e_main
                    paste_center(im, scaled(e, ease_out_back(k, 2.2)), x, y - 40 * (1 - k))
            return im
        if rv <= 0:
            return self.full
        k = ease_out_cubic(clamp((rv - 0.05) / 0.5))
        s = 1 + 0.45 * k
        lay = self.dim if rv > 0.02 else self.full
        return zoom_about(lay, s, *self.odd_xy)

    def render(self, t, header=True):
        T = self.t0 + t
        rv = t - self.reveal
        ui = self.ui
        pulse = beat_pulse(T) if t > self.entry else 0.0
        im = ui["bg"].render(T, strobe=0.3 * pulse + (1 - clamp(rv / 0.25) if rv > 0 else 0))
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        lay = self.board_layer(t, rv)
        if rv <= 0 and t > self.entry:                       # a gentle punch on the 3-2-1 beats
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.2:
                    lay = zoom_about(lay, 1 + 0.025 * (1 - ease_out_cubic(tb / 0.2)), *BOARD_C)
        im.alpha_composite(lay)
        if rv > 0:                                           # ring, shockwaves and the answer on the odd one
            ox, oy = self.odd_xy
            for j in range(3):
                tl = rv - 0.12 * j
                if 0 < tl < 0.6:
                    r_ = 60 + 420 * ease_out_cubic(tl / 0.6)
                    ImageDraw.Draw(im, "RGBA").ellipse((ox - r_, oy - r_, ox + r_, oy + r_),
                                                       outline=XRED + (int(255 * (1 - tl / 0.6)),), width=10)
            kr = ease_out_back(clamp((rv - 0.1) / 0.3), 2.2)
            if kr > 0.01:
                s = (1 + 0.45 * ease_out_cubic(clamp((rv - 0.05) / 0.5))) * kr * (1 + 0.06 * beat_pulse(T))
                paste_center(im, scaled(self.ring, s), ox, oy)
            ka = ease_out_back(clamp((rv - 0.45) / 0.3), 2.0)
            if ka > 0.01:
                ay = oy + self.cell * 1.4 + 40 if oy < 1250 else oy - self.cell * 1.4 - 40
                ax = min(max(ox, self.answer.width / 2 + 20), W - self.answer.width / 2 - 20)
                paste_center(im, scaled(self.answer, ka * (1 + 0.02 * beat_pulse(T))), ax, ay)
        d = ImageDraw.Draw(im)
        if header:
            paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
            x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
            frac = 1.0 if t < self.entry else max(0.0, 1 - (t - self.entry) / (self.reveal - self.entry))
            d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
            colr = (255, 255, 255) if frac > 0.6 else XGREEN if frac > 0.3 else XRED
            if frac > 0.01:
                d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 11, fill=colr + (255,))
            paste_center(im, self.tag, x0 + self.tag.width / 2, 285)
            paste_center(im, self.size_tag, W / 2, 287)
            nk = self.idx if rv > 0 else self.idx - 1
            if nk > 0:
                sc = 1 + 0.5 * (1 - ease_out_cubic(rv / 0.25)) if 0 < rv < 0.25 else 1.0
                stk = self.streak[nk]
                paste_center(im, scaled(stk, sc), x1 - stk.width / 2 + 10, 288)
        kc = ease_out_back(clamp((t - 0.05) / 0.3), 1.6)
        if kc > 0.01:
            paste_center(im, scaled(ui["card"], kc * (1 + 0.015 * beat_pulse(T))), W / 2, CARD_Y)
        if self.banner is not None and 0.05 < t < self.entry + 0.6:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.entry - 0.3) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, BOARD_C[1], a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[3 - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a * 0.9)
        cta_on = self.cta and rv > self.cta_at
        if rv > 0:
            ox, oy = self.odd_xy
            for vx, vy, sz, cc, spin in self.conf:
                px, py = ox + vx * rv, oy + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    dd = ImageDraw.Draw(im)
                    dd.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                 outline=INK + (255,))
            sk = ease_out_back((rv - 0.3) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             940, 1690)
            fl = 1 - clamp(rv / 0.12)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(190 * fl))))
            im = shake(im, 26 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 14 * (1 - rv / 0.18))
        else:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.12:
                    im = shake(im, 8 * (1 - tb / 0.12), t)
            tb = t - self.count_beats[-1] * B
            if self.danger and 0 <= tb < 0.2:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 30, 60, int(80 * (1 - tb / 0.2)))))
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
        if self.level_up and t < 0.3:
            im = glitch(im, 1 - t / 0.3, int(t * 30) + self.idx * 7)
        if t < 0.14:
            im = rgb_split(mm.zoom_blur(im, 0.5 * (1 - t / 0.14)), 14 * (1 - t / 0.14))
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(mm.zoom_blur(im, 0.6 * out), 20 * out)
        return im


# ----------------------------------------------------------------------------
# intro and ending
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    SHOW = (10, 8, 6)

    def __init__(self, ui, tts, rounds):
        super().__init__()
        self.ui, self.rounds = ui, rounds
        self.dur = 6 * B
        hb = 0.5 * B
        clips = [tts.say(w, speed=1.24) for w in INTRO_WORDS] if tts else None
        lens = [len(c) / SR for c in clips] if clips else [0.8, 0.85, 1.0]
        self.slams = [0.0]
        for ln in lens:
            prev = self.slams[-1]
            self.slams.append(max(prev + hb, round((prev + ln - 0.08) / hb) * hb))
        self.slams[-1] = min(self.slams[-1], self.dur - 0.4)
        if clips:
            for at, c in zip(self.slams, clips):
                self.voices.append((at, c))
        self.o3 = join(rtext("answer at the end", 58, fill=GOLD, stroke=7), emoji("👀", 62))
        self.w1 = fit(join(rtext("FIND THE ODD ONE", 124, stroke=12), emoji("👀", 110), gap=12), 990)
        self.w2 = fit(join(rtext("CHRISTMAS EDITION", 112, fill=XRED, stroke=11), emoji("🎄", 104), gap=12), 990)
        self.w3 = join(rtext("99% FAIL", 150, fill=GOLD, stroke=14), emoji("💀", 140))
        self.l1 = fit(rtext("FIND THE", 150, stroke=13), 990)
        self.l2 = fit(join(rtext("ODD ONE", 170, fill=GOLD, stroke=15), emoji("👀", 150), gap=14), 990)
        self.l3 = fit(join(rtext("CHRISTMAS EDITION", 90, fill=XRED, stroke=9), emoji("🎄", 86), gap=10), 960)
        self.burst = [emoji(e, 230) for e in ("🎅", "🎁", "⛄", "🎄", "🦌", "🔔")]
        self.sounds += [(0.0, sfx_heartbeat(), 0.8), (0.0, xm.sfx_jingle(), 0.6),
                        (self.slams[2], mv.sfx_riser(self.slams[3] - self.slams[2]), 0.6),
                        (self.slams[3], xm.sfx_jingle(), 0.9), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.9)]
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
        if k < 3:                                            # word slams over real grids
            r = self.rounds[self.SHOW[k]]
            im = r.render(r.count_beats[0] * B - 0.1)
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 140)))
            words = [(self.w1, 820, -3), (self.w2, 990, 2), (self.w3, 1190, -2)]
            for j in range(k + 1):
                img, y, rot = words[j]
                sc = (slam if j == k else 1.0) * (1 + 0.025 * beat_pulse(T))
                paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
            paste_center(im, self.o3, W / 2, 1745)
            im = shake(im, 24 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
            im = rgb_split(im, (8 if k == 0 else 16) * (1 - clamp(ts / 0.15)))
            if k > 0:
                im = mm.zoom_blur(im, 0.6 * (1 - clamp(ts / 0.1)))
                if ts < 0.06:
                    im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            return im
        im = self.ui["bg"].render(T, strobe=beat_pulse(T))  # title card with Christmas emojis bursting out
        for j, e in enumerate(self.burst):
            ang = j * (2 * math.pi / len(self.burst)) + 0.3
            r = 200 + 900 * ease_out_cubic(clamp(ts / 0.8))
            paste_center(im, scaled(e, 1 - 0.3 * clamp(ts / 0.8)).rotate(ts * 160, Image.BICUBIC, expand=True),
                         W / 2 + r * math.cos(ang), 860 + r * math.sin(ang) * 0.85)
        for j, (img, y, rot) in enumerate([(self.l1, 660, -3), (self.l2, 850, 3), (self.l3, 1040, -2)]):
            sc = (slam if j == 2 else 1 + 0.12 * (1 - ease_out_cubic(clamp(ts / 0.18)))) * (1 + 0.03 * beat_pulse(T))
            paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
        im = shake(im, 22 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
        if ts < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - ts / 0.08)))))
        whip = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Ending(mv.Scene):
    """Christmas score screen; it fades into the first frame so the Short loops."""

    def __init__(self, ui, intro, tts):
        super().__init__()
        self.ui, self.intro = ui, intro
        self.dur = 10 * B
        logo = Image.open(brand.round_logo()).convert("RGBA").resize((120, 120), Image.LANCZOS)
        self.brand = join(logo, rtext(brand.NAME, 60, stroke=6), gap=18)
        self.title = rtext("HOW MANY?", 124, fill=GOLD, stroke=11)
        tiers = [("0-3", "Grinch", "💚"), ("4-5", "Snowman", "⛄"), ("6-7", "Elf", "🧝"), ("8-9", "Reindeer", "🦌"),
                 ("10", "Santa", "🎅")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            colr = GOLD if i == 4 else (255, 255, 255)
            row = rounded_card(780, 104, 52, INK + (215,), outline=(XRED if i == 4 else (90, 70, 130)) + (255,),
                               width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 52), sc, font=rfont(60), fill=colr, anchor="lm")
            dr.text((210, 52), label, font=rfont(60, "SemiBold"), fill=colr, anchor="lm")
            row.alpha_composite(emoji(e, 60), (780 - 96, 22))
            self.rows.append(row)
        self.bonus = join(rtext("+ bonus = CHRISTMAS LEGEND", 50, fill=GOLD, stroke=6), emoji("👑", 54))
        self.cta = join(rtext("comment your score", 58, stroke=6), emoji("👇", 62))
        self.sounds += [(0.0, mv.sfx_whoosh(0.8), 0.7), (B, mq.sfx_levelup(), 0.9)]
        for i in range(5):
            self.sounds.append(((1.5 + 0.5 * i) * B, mv.sfx_pop(), 0.7))
        self.sounds.append((5 * B, xm.sfx_jingle(), 0.7))
        if tts:
            self.voices.append((0.3, tts.say(END_LINE, speed=1.12)))

    def render(self, t):
        T = self.t0 + t
        im = self.ui["bg"].render(T, strobe=0.3 * beat_pulse(T))
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        a = 1 - out
        paste_center(im, self.brand, W / 2, 300, clamp((t - B) / 0.2) * a)
        paste_center(im, scaled(self.title, ease_out_back((t - B) / 0.25) * (1 + 0.03 * beat_pulse(T))), W / 2, 460, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - (1.5 + 0.5 * i) * B) / 0.2)
            if k > 0:
                paste_center(im, row, W / 2 + (1 - k) * 160, 620 + i * 122, k * a)
        paste_center(im, scaled(self.bonus, ease_out_back((t - 4.5 * B) / 0.25)), W / 2, 1255, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 5 * B) / 0.25) * (1 + 0.03 * math.sin(t * 8))),
                     W / 2, 1350, a)
        if t < 0.2:
            im = rgb_split(mm.zoom_blur(im, 1 - t / 0.2), 18 * (1 - t / 0.2))
        if out > 0:
            first = self.intro.render(0.0)
            first.putalpha(first.getchannel("A").point(lambda v: int(v * out)))
            im.alpha_composite(first)
        return im


def build(voice="am_adam", voice_pack=None):
    if voice_pack:
        tts = cq.Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    ui = {"bg": NightSky(), "vig": [mc.red_vignette(i / 10) for i in range(11)], "board": board_frame(),
          "card": question_card()}
    rounds, prev = [], ROUNDS[0][6]
    for i, r in enumerate(ROUNDS, 1):
        rounds.append(Round(i, r, prev, ui, tts))
        prev = r[6]
    intro = Intro(ui, tts, rounds)
    scenes = [intro, *rounds, Ending(ui, intro, tts)]
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(scenes, ui, path):
    r = scenes[1 + 2]                                        # Santas, and one Mrs Claus
    im = r.render(r.count_beats[0] * B + 0.43, header=False)
    im.alpha_composite(Image.new("RGBA", (W, 330), (10, 0, 30, 150)), (0, 0))
    paste_center(im, fit(join(rtext("FIND THE ODD ONE", 104, stroke=10), emoji("👀", 96), gap=10), 1000)
                 .rotate(-3, Image.BICUBIC, expand=True), W / 2, 130)
    paste_center(im, fit(join(rtext("CHRISTMAS EDITION", 76, fill=XRED, stroke=8), emoji("🎄", 72), gap=10), 1000)
                 .rotate(2, Image.BICUBIC, expand=True), W / 2, 250)
    paste_center(im, join(rtext("99% FAIL", 100, fill=GOLD, stroke=10), emoji("💀", 100)), W / 2, 1745)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_odd_emoji_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    quiet = a.stills or a.cover
    scenes, starts, total, ui = build(a.voice if not quiet else "none", None if quiet else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    if a.cover:
        make_cover(scenes, ui, os.path.join(HERE, "odd_emoji_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"oddemo_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    work = os.path.join(mv.CACHE_DIR, "render_odd_emoji")
    os.makedirs(work, exist_ok=True)
    for f in os.listdir(work):
        os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, xq.mix_audio(scenes, starts, total))
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
