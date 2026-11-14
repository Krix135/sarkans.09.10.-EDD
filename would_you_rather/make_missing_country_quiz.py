#!/usr/bin/env python3
""""WHICH COUNTRY IS MISSING?" Short (1080x1920), part 3 formula with a big hook.

Each round the globe flies to a region where every country is lit up in bright colours except one,
which is a dark, glowing gap with a "?". A 3-2-1 runs on the beat; on the drop the gap fills with the
country's flag and pops up, the colours around it calm down, the name flips in on letter tiles and a
fun fact appears. Hook intro: cold open on the bonus gap, a rapid montage of gaps, then WHICH COUNTRY /
IS MISSING? / 99% FAIL over a spinning, colour-lit globe. EASY -> IMPOSSIBLE plus a bonus, one like
call-out after round 3, looping score screen. Borders: Natural Earth (public domain); flags: public
domain.

    python3 make_missing_country_quiz.py
    python3 make_missing_country_quiz.py --stills 0,2,6
    python3 make_missing_country_quiz.py --cover
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

import globe as G  # noqa: E402
import make_bigger_country_quiz as bq  # noqa: E402
import make_club_quiz as cq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_pin_country_quiz as pq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_in_out, ease_out_back, ease_out_cubic, emoji, paste_center, \
    rounded_card, scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
GC = (540, 1110)
CARD_Y = 462
NUM_Y = 720
mm.TILE_Y = 1560
FACT_Y = 1670
FLY_BEATS = 3
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
PALETTE = [(255, 92, 150), (60, 200, 255), (255, 200, 60), (170, 110, 255), (70, 220, 140), (255, 140, 60)]
HOLE = (10, 4, 28)
SS = 1.25                           # supersampling for the colour layer

ROUNDS = [  # map code, flag, tiles, fact, fact emoji, tier, prompt, spoken answer, sticker
    ("FRA", "FR", "FRANCE", "it has the most time zones of any country", "🕐", "EASY", "Which country is missing?",
     "France!", "😎"),
    ("BRA", "BR", "BRAZIL", "it borders every South American country but two", "🗺", "EASY", "Next!", "Brazil!",
     "🔥"),
    ("IND", "IN", "INDIA", "chess was invented here", "♟", "EASY", "Too easy?", "India!", "🤔"),
    ("DEU", "DE", "GERMANY", "it borders 9 different countries", "🧭", "MEDIUM", "Think fast!", "Germany!", "😳"),
    ("SAU", "SA", "SAUDI ARABIA", "home to the world's largest sand desert", "🏜", "MEDIUM", "Ooh, tricky!",
     "Saudi Arabia!", "🤯"),
    ("NGA", "NG", "NIGERIA", "Africa's most populous country", "👥", "MEDIUM", "Next!", "Nigeria!", "🔥"),
    ("CHE", "CH", "SWITZERLAND", "it has 4 official languages", "🗣", "HARD", "Hard level!", "Switzerland!", "😱"),
    ("NPL", "NP", "NEPAL", "8 of the 10 highest mountains on Earth are here", "🏔", "HARD", "No way!", "Nepal!",
     "💀"),
    ("SRB", "RS", "SERBIA", "one of the world's top raspberry growers", "🍓", "INSANE", "Insane level!", "Serbia!",
     "🧠"),
    ("ZMB", "ZM", "ZAMBIA", "Victoria Falls is on its border", "💦", "IMPOSSIBLE", "Impossible level!", "Zambia!",
     "☠"),
    ("MDA", "MD", "MOLDOVA", "home to the world's biggest wine collection", "🍷", "BONUS",
     "Bonus! Only one percent!", "Moldova!", "👑"),
]
INTRO_LINE = "Only one percent can find them all!"
END_LINE = "How many did you get? Comment your score!"


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


class ColourMap:
    """Draws every visible country in a bright colour, and the missing one as a dark glowing gap."""

    def __init__(self, world):
        self.w = world
        self.cols = self.colour_graph(world)

    @staticmethod
    def colour_graph(world):
        """Greedy map colouring so that neighbouring countries get different colours."""
        n = len(world.codes)
        own = np.repeat(np.asarray(world.owner), world.lens)
        cen = np.zeros((n, 3))
        np.add.at(cen, own, world.P)
        cen /= np.maximum(np.linalg.norm(cen, axis=1, keepdims=True), 1e-9)
        rad = np.zeros(n)
        np.maximum.at(rad, own, np.arccos(np.clip(np.sum(world.P * cen[own], axis=1), -1, 1)))
        ang = np.arccos(np.clip(cen @ cen.T, -1, 1))
        near = ang < (rad[:, None] + rad[None, :]) * 1.02 + 0.01
        cols = [None] * n
        for i in sorted(range(n), key=lambda k: -rad[k]):
            used = {cols[j] for j in np.nonzero(near[i])[0] if cols[j] is not None and j != i}
            free = [k for k in range(len(PALETTE)) if k not in used]
            cols[i] = free[(i * 7) % len(free)] if free else (i * 7) % len(PALETTE)
        return [PALETTE[k] for k in cols]

    def draw(self, im, c, R, center, target=None, alpha=1.0, hole=1.0, pulse=0.0):
        """Returns the target's screen centre (or None)."""
        w = self.w
        SW, SH = int(W * SS), int(H * SS)
        east, up, view = G.frame_axes(c)
        sx, sy, dep = w.P @ east, w.P @ up, w.P @ view
        hidden = dep < 0
        nrm = np.hypot(sx, sy)
        nrm[nrm == 0] = 1
        sx = np.where(hidden, sx / nrm, sx)
        sy = np.where(hidden, sy / nrm, sy)
        X, Y = center[0] * SS + R * SS * sx, center[1] * SS - R * SS * sy
        vis = np.maximum.reduceat(dep, w.starts) > 0
        minx, maxx = np.minimum.reduceat(X, w.starts), np.maximum.reduceat(X, w.starts)
        miny, maxy = np.minimum.reduceat(Y, w.starts), np.maximum.reduceat(Y, w.starts)
        on = vis & (maxx > 0) & (minx < SW) & (maxy > 0) & (miny < SH) & ((maxx - minx) + (maxy - miny) > 2)
        layer = Image.new("RGBA", (SW, SH))
        d = ImageDraw.Draw(layer)
        lw = max(1, int(2 * SS))
        holes = []
        for i in np.nonzero(on)[0]:
            s, n = w.starts[i], w.lens[i]
            pts = list(zip(X[s:s + n].tolist(), Y[s:s + n].tolist()))
            if target is not None and w.owner[i] == target:
                holes.append(pts)
                continue
            if alpha > 0.01:
                d.polygon(pts, fill=self.cols[w.owner[i]] + (int(232 * alpha),))
                d.line(pts + [pts[0]], fill=(255, 255, 255, int(230 * alpha)), width=lw)
        centre = None
        if holes:
            xs = [x for p in holes for x, _ in p]
            ys = [y for p in holes for _, y in p]
            centre = ((min(xs) + max(xs)) / 2 / SS, (min(ys) + max(ys)) / 2 / SS)
            if hole > 0.01:
                for p in holes:
                    d.polygon(p, fill=HOLE + (int(250 * hole),))
                for p in holes:                              # glowing edge that pulses on the beat
                    d.line(p + [p[0]], fill=CYAN + (int(90 * hole),), width=int((10 + 10 * pulse) * SS))
                    d.line(p + [p[0]], fill=(220, 250, 255, int(255 * hole)), width=int(3 * SS))
        im.alpha_composite(layer.resize((W, H), Image.BILINEAR))
        return centre


def question_card():
    a = rtext("WHICH COUNTRY", 66, fill=(255, 255, 255), stroke=6)
    b = join(rtext("IS MISSING?", 92, fill=GOLD, stroke=8), emoji("🧩", 84), gap=12)
    card = rounded_card(max(a.width, b.width) + 90, a.height + b.height + 40, 46, (14, 6, 40, 228),
                        outline=CYAN + (255,), width=5)
    paste_center(card, a, card.width / 2, 22 + a.height / 2)
    paste_center(card, b, card.width / 2, 22 + a.height + b.height / 2 - 4)
    return card


def region_for(world, code):
    c, near, _ = world.country(code)
    R = G.zoom_for(world, c, near, W, H, 0.34, 0.2)
    return c, near, R


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    TEASE, MONTAGE = 10, (6, 7, 8, 9)

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 6 * B
        self.t1, self.t2 = 1.5 * B, 3.5 * B
        world = ui["globe"].world
        self.views = {}
        for k in (self.TEASE, *self.MONTAGE):
            c, _, R = region_for(world, ROUNDS[k][0])
            self.views[k] = (c, R * 0.42, world.codes.index(ROUNDS[k][0]))
        self.o1 = fit(join(rtext("ONLY 1% CAN FIND", 96, fill=PINK, stroke=10), emoji("😳", 92), gap=10))
        self.o2 = fit(join(rtext("THE MISSING ONE", 112, stroke=11), emoji("🧩", 100), gap=12))
        self.q = rtext("?", 220, stroke=16)
        self.o3 = join(rtext("answer at the end", 60, fill=GOLD, stroke=7), emoji("👀", 64))
        self.m1 = fit(rtext("CAN YOU FIND", 108, stroke=10))
        self.m2 = fit(rtext("ALL OF THEM?", 120, fill=CYAN, stroke=11))
        self.l1 = fit(rtext("WHICH COUNTRY", 128, fill=PINK, stroke=12), 940)
        self.l2 = fit(join(rtext("IS MISSING?", 140, stroke=13), emoji("🧩", 124), gap=14), 940)
        self.l3 = join(rtext("99% FAIL", 120, fill=GOLD, stroke=11), emoji("💀", 120))
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9),
                        (0.02, mq.sfx_glitch(), 0.5), (B, sfx_heartbeat(), 0.8), (B, mq.sfx_boom(), 0.5),
                        (self.t2, mq.sfx_boom(), 0.9), (self.t2, mv.sfx_whoosh(0.5), 0.6),
                        (4 * B, mv.sfx_pop(), 0.9), (4.5 * B, mq.sfx_boom(), 0.7), (4.5 * B, mv.sfx_riser(1.5 * B), 0.7),
                        (6 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k in range(len(self.MONTAGE)):
            at = self.t1 + k * 0.5 * B
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mq.sfx_glitch(), 0.35), (at, mv.sfx_click(), 0.7)]
        if tts:
            self.voices.append((0.04, tts.say(INTRO_LINE, speed=1.18)))

    def region(self, k, t, T, zoom=1.0):
        c, R, target = self.views[k]
        im = self.ui["globe"].render(c, R * zoom, GC)
        ctr = self.ui["cmap"].draw(im, c, R * zoom, GC, target, 1.0, 1.0, beat_pulse(T))
        im.alpha_composite(self.ui["shade"])
        if ctr:
            paste_center(im, scaled(self.q, 0.6 + 0.08 * math.sin(t * 10)), ctr[0], ctr[1])
        return im

    def render(self, t):
        T = self.t0 + t
        if t < self.t1:                                      # cold open: the gap is on screen from frame one
            im = self.region(self.TEASE, t, T, 1.05 - 0.05 * ease_out_cubic(t / 0.3))
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.5 * beat_pulse(T)))])
            s = 1 + 0.06 * (1 - ease_out_cubic(t / 0.2))
            paste_center(im, scaled(self.o1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 260)
            paste_center(im, scaled(self.o2, s).rotate(2, Image.BICUBIC, expand=True), W / 2, 400)
            paste_center(im, self.o3, W / 2, 1700)
            im = shake(im, 26 * (1 - t / 0.3) if t < 0.3 else 0, t)
            return rgb_split(im, 8 * (1 - clamp(t / 0.25)))
        if t < self.t2:                                      # rapid montage of gaps
            k = min(len(self.MONTAGE) - 1, int((t - self.t1) / (0.5 * B)))
            tc = t - self.t1 - k * 0.5 * B
            im = self.region(self.MONTAGE[k], t, T, 1.1 - 0.1 * ease_out_cubic(tc / 0.15))
            s = 1 + 0.12 * (1 - ease_out_cubic((t - self.t1) / 0.15))
            paste_center(im, scaled(self.m1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 300)
            paste_center(im, scaled(self.m2, s).rotate(3, Image.BICUBIC, expand=True), W / 2, 450)
            im = rgb_split(im, 18 * (1 - clamp(tc / 0.12)))
            if tc < 0.06:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            return im
        tg = t - self.t2                                     # titles over a spinning, colour-lit globe
        gc = (540, 1250)
        R = 480 * (1 + 0.05 * beat_pulse(T)) * (1.25 - 0.25 * ease_out_cubic(clamp(tg / 0.3)))
        c = G.unit(-10 + 60 * tg, 20)
        im = self.ui["globe"].render(c, R, gc)
        self.ui["cmap"].draw(im, c, R, gc, None, 0.85 + 0.15 * beat_pulse(T))
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 40)))
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
        code, fcode, name, fact, femoji, tier, prompt, said, stick = r
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
        self.target = world.codes.index(code)
        self.c, self.near, self.Rc = region_for(world, code)
        self.region = (self.c, self.Rc * 0.42)
        self.cam = mm.Camera(prev_view, self.region, self.fly, self.reveal)
        self.flag = Image.open(os.path.join(FLAG_DIR, fcode + ".png")).convert("RGBA")
        self.cols = mm.flag_colours(self.flag)
        self.tiles = mm.Tiles(name, tier in ("INSANE", "IMPOSSIBLE", "BONUS"))
        self.card = ui["card"]
        self.q = rtext("?", 200, stroke=15)
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
        self.nums = {k: rtext(str(k), 190, fill=PINK if k == 1 else (255, 255, 255), stroke=15) for k in range(1, n + 1)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (self.fly, mv.sfx_pop(), 0.8)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
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
        k = ease_in_out(clamp(rv / 0.6))
        return c0, math.exp(math.log(R0) + (math.log(self.Rc * 0.7) - math.log(R0)) * k), 0.0

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        c, R, blur = self.camera(t)
        if t > self.fly and rv < 0:
            R *= 1 + 0.02 * beat_pulse(T)
        fa = clamp((rv - 0.05) / 0.25) if rv > 0 else 0.0
        lift = 24 * ease_out_back(clamp(rv / 0.3)) if rv > 0 else 0.0
        im = self.ui["globe"].render(c, R, GC, self.near if rv > 0 else None, 1.0 if rv > 0 else 0.0, self.flag, fa,
                                     lift=lift)
        on = clamp((t - self.fly * 0.6) / (self.fly * 0.4))       # colours switch on as the camera lands
        alpha = on * (1 - 0.45 * clamp(rv / 0.4)) if rv > 0 else on
        hole = on * (1 - clamp(rv / 0.12)) if rv > 0 else on
        ctr = self.ui["cmap"].draw(im, c, R, GC, self.target, alpha, hole, beat_pulse(T) if t > self.fly else 0.0)
        im = mm.zoom_blur(im, blur)
        im = rgb_split(im, 22 * blur)
        im.alpha_composite(self.ui["shade"])
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv > 0:
            im.alpha_composite(cq.speed_lines(1 - clamp(rv / 0.45), self.idx, GC))
        counting = any(0 <= t - b * B < B for b in self.count_beats)
        if ctr and rv <= 0 and on > 0.5:
            paste_center(im, scaled(self.q, (0.55 + 0.08 * math.sin(t * 10)) * (0.7 if counting else 1.0)),
                         ctr[0], ctr[1], 0.5 if counting else 1.0)
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
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, NUM_Y + 40, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a * 0.9)
        self.tiles.draw(im, t - self.fly - B, rv)
        cta_on = self.cta and rv > self.cta_at
        if rv > 0:
            cx, cy = getattr(self.ui["globe"], "last_hl_center", GC)
            for vx, vy, sz, cc, spin in self.conf:
                px, py = cx + vx * rv, cy + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d = ImageDraw.Draw(im)
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            sk = ease_out_back((rv - 0.12) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             910, 1440)
            fk = ease_out_back((rv - 0.35) / 0.3)
            if fk > 0.01 and not cta_on:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * fl))))
            im = shake(im, 30 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
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
    ui = {"globe": globe, "big_globe": globe, "cmap": ColourMap(world), "card": question_card(),
          "shade": mm.shade_overlay(0.8), "vig": [mc.red_vignette(i / 10) for i in range(11)]}
    intro = Intro(ui, tts)
    scenes, view, prev = [intro], (G.unit(-10 + 60 * (intro.dur - intro.t2), 20), 600.0), ROUNDS[0][5]
    for i, r in enumerate(ROUNDS, 1):
        sc = Round(i, r, view, prev, ui, tts)
        scenes.append(sc)
        view, prev = (sc.c, sc.Rc * 0.75), r[5]
    scenes.append(bq.Ending(ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    k = 6
    world = ui["globe"].world
    c, _, R = region_for(world, ROUNDS[k][0])
    R *= 0.42
    im = ui["globe"].render(c, R, GC)
    ctr = ui["cmap"].draw(im, c, R, GC, world.codes.index(ROUNDS[k][0]), 1.0, 1.0, 0.6)
    im.alpha_composite(mm.shade_overlay(0.9))
    if ctr:
        paste_center(im, rtext("?", 170, stroke=14), ctr[0], ctr[1])
    paste_center(im, ui["card"], W / 2, CARD_Y)
    paste_center(im, fit(join(rtext("ONLY 1% CAN FIND IT", 80, fill=PINK, stroke=8), emoji("😳", 80), gap=10), 960)
                 .rotate(-3, Image.BICUBIC, expand=True), W / 2, 220)
    paste_center(im, join(rtext("99% FAIL", 96, fill=GOLD, stroke=9), emoji("💀", 98)), W / 2, 1720)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_missing_country_quiz.mp4"))
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
        make_cover(ui, os.path.join(HERE, "missing_country_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"missing_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_missing")
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
