#!/usr/bin/env python3
""""GUESS THE COUNTRY BY ITS OUTLINE" Short (1080x1920).

Each round a country appears as a glowing neon outline on a dark grid, no map, no neighbours: it draws
itself in with a spark racing along the border, then sways and pulses on the beat while letter tiles show
the name's length and a 3-2-1 runs. On the drop the outline fills with the country's flag and pops; then
the real map fades in around it at exactly the same place and size, and the camera zooms out to show
where it is, while the tiles flip to the name and a fun fact appears. Spoken-title intro (6 beats),
EASY -> IMPOSSIBLE plus a bonus, one like call-out after round 3, looping score screen.
Borders: Natural Earth (public domain). Flags: public domain.

    python3 make_outline_quiz.py
    python3 make_outline_quiz.py --stills 0,5,9
    python3 make_outline_quiz.py --cover
    python3 make_outline_quiz.py --episode 2      # part 2: new outlines
    python3 make_outline_quiz.py --episode 2 --no-intro    # starts straight on round 1
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
import make_missing_country_quiz as mcq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_in_out, ease_out_back, ease_out_cubic, emoji, paste_center, \
    rounded_card, scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
OC = (540, 1035)                     # outline centre
BOX = (440, 360)                     # outline half-size
CARD_Y = 438
NUM_Y = 598
mm.TILE_Y = 1515
FACT_Y = 1628
CTA_Y = 1660
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
DRAW = 1.15                          # seconds the outline takes to draw itself

ROUNDS = [  # map code, flag, name, fact, fact emoji, tier, prompt, spoken answer, sticker
    ("ITA", "IT", "ITALY", "Europe's most active volcano, Etna, is here", "🌋", "EASY", "Name this country!",
     "Italy!", "😎"),
    ("CHL", "CL", "CHILE", "it's over 4,000 km long but only about 177 km wide", "📏", "EASY", "Next!", "Chile!",
     "🔥"),
    ("GBR", "GB", "UNITED KINGDOM", "nowhere in it is more than 113 km from the sea", "🌊", "EASY", "Too easy?",
     "The United Kingdom!", "🤔"),
    ("MEX", "MX", "MEXICO", "parts of Mexico City sink up to 50 cm a year", "📉", "MEDIUM", "Think fast!", "Mexico!",
     "😳"),
    ("VNM", "VN", "VIETNAM", "it's shaped like the letter S", "🐍", "MEDIUM", "Ooh, tricky!", "Vietnam!", "🤯"),
    ("GRC", "GR", "GREECE", "it has about 6,000 islands", "🏝", "MEDIUM", "Next!", "Greece!", "🔥"),
    ("TUR", "TR", "TURKEY", "Istanbul sits on two continents", "🌉", "HARD", "Hard level!", "Turkey!", "😱"),
    ("MDG", "MG", "MADAGASCAR", "about 90% of its wildlife lives nowhere else", "🐒", "HARD", "No way!",
     "Madagascar!", "💀"),
    ("NZL", "NZ", "NEW ZEALAND", "there are about 5 sheep for every person", "🐑", "INSANE", "Insane level!",
     "New Zealand!", "🧠"),
    ("MNG", "MN", "MONGOLIA", "it's the most sparsely populated country", "🐎", "IMPOSSIBLE", "Impossible level!",
     "Mongolia!", "☠"),
    ("CZE", "CZ", "CZECHIA", "it has over 2,000 castles", "🏰", "BONUS", "Bonus! Only one percent!", "Czechia!",
     "👑"),
]
ROUNDS_1 = ROUNDS
ROUNDS_2 = [  # none of these were in the earlier shape or outline videos
    ("FRA", "FR", "FRANCE", "the Eiffel Tower was only meant to stand for 20 years", "🗼", "EASY",
     "Name this country! Part two!", "France!", "😎"),
    ("ESP", "ES", "SPAIN", "it makes almost half of the world's olive oil", "🫒", "EASY", "Next!", "Spain!", "🔥"),
    ("EGY", "EG", "EGYPT", "about 95% of its people live along the Nile", "🌊", "EASY", "Too easy?", "Egypt!", "🤔"),
    ("PER", "PE", "PERU", "it grows over 3,000 kinds of potato", "🥔", "MEDIUM", "Think fast!", "Peru!", "😳"),
    ("SAU", "SA", "SAUDI ARABIA", "it has no permanent rivers at all", "🏜", "MEDIUM", "Ooh, tricky!",
     "Saudi Arabia!", "🤯"),
    ("UKR", "UA", "UKRAINE", "the world's biggest plane was built here", "✈", "MEDIUM", "Next!", "Ukraine!", "🔥"),
    ("ISL", "IS", "ICELAND", "about a tenth of it is covered by glaciers", "🧊", "HARD", "Hard level!", "Iceland!",
     "😱"),
    ("KAZ", "KZ", "KAZAKHSTAN", "it's the biggest landlocked country in the world", "🗺", "HARD", "No way!",
     "Kazakhstan!", "💀"),
    ("PRY", "PY", "PARAGUAY", "its flag has a different design on each side", "🚩", "INSANE", "Insane level!",
     "Paraguay!", "🧠"),
    ("ZMB", "ZM", "ZAMBIA", "it's named after the Zambezi River", "🌊", "IMPOSSIBLE", "Impossible level!",
     "Zambia!", "☠"),
    ("PNG", "PG", "PAPUA NEW GUINEA", "over 800 languages are spoken here", "🗣", "BONUS", "Bonus! Only one percent!",
     "Papua New Guinea!", "👑"),
]
EPISODES = {  # rounds, part, file name, cover round, intro phrases
    1: (ROUNDS_1, None, "outline_quiz", 4, ("Guess the country", "by its outline!", "Ninety-nine percent fail!")),
    2: (ROUNDS_2, 2, "outline_quiz_2", 6, ("Guess the country", "by its outline!", "Part two!")),
}
PART, NAME, COVER, INTRO_WORDS = EPISODES[1][1:]


def set_episode(ep):
    global ROUNDS, PART, NAME, COVER, INTRO_WORDS
    ROUNDS, PART, NAME, COVER, INTRO_WORDS = EPISODES[ep]


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


class NeonBG:
    """Dark blueprint grid with a glow behind the outline that breathes on the beat, plus drifting dust."""

    def __init__(self):
        base = mv.vgradient(W, H, (8, 6, 30), (34, 10, 64)).convert("RGBA")
        d = ImageDraw.Draw(base)
        for x in range(0, W, 90):
            d.line((x, 0, x, H), fill=(80, 200, 255, 20), width=2)
        for y in range(0, H, 90):
            d.line((0, y, W, y), fill=(80, 200, 255, 20), width=2)
        self.base = base
        self.glows = {}
        r = random.Random(4)
        self.dust = [(r.uniform(0, W), r.uniform(0, H), r.uniform(2, 5), r.uniform(10, 40), r.uniform(0, 6))
                     for _ in range(60)]

    def glow(self, col):
        if col not in self.glows:
            self.glows[col] = mv.soft_circle(1100, col + (110,), 260)
        return self.glows[col]

    def render(self, T, col, pulse=0.0):
        im = self.base.copy()
        paste_center(im, self.glow(col), *OC, 0.55 + 0.45 * pulse)
        d = ImageDraw.Draw(im, "RGBA")
        for x0, y0, r, sp, ph in self.dust:
            y = (y0 - sp * T) % H
            x = x0 + 14 * math.sin(T * 0.7 + ph)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(150, 220, 255, 90))
        return im


class Outline:
    """A country's border, projected the same way the globe does it so the map can fade in around it."""

    def __init__(self, world, code, col):
        ci = world.codes.index(code)
        idx = np.nonzero(world.owner == ci)[0]
        allp = np.concatenate([world.P[world.starts[i]:world.starts[i] + world.lens[i]] for i in idx])
        c = allp.mean(0)
        c /= np.linalg.norm(c)

        def area(i, east, up):
            p = world.P[world.starts[i]:world.starts[i] + world.lens[i]]
            x, y = p @ east, p @ up
            return abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) / 2

        east, up, _ = G.frame_axes(c)
        areas = {i: area(i, east, up) for i in idx}
        big = max(areas.values())
        main = max(areas, key=areas.get)                     # land near the main landmass only, so overseas
        mp = world.P[world.starts[main]:world.starts[main] + world.lens[main]].mean(0)   # parts (French Guiana)
        mp /= np.linalg.norm(mp)                                                          # don't count

        def near(i):
            q = world.P[world.starts[i]:world.starts[i] + world.lens[i]].mean(0)
            return float(q @ mp) / np.linalg.norm(q) > math.cos(math.radians(20))
        self.keep = np.array([i for i in idx if areas[i] >= 0.025 * big and near(i)])
        kp = np.concatenate([world.P[world.starts[i]:world.starts[i] + world.lens[i]] for i in self.keep])
        c = kp.mean(0)
        c /= np.linalg.norm(c)
        east, up, _ = G.frame_axes(c)
        for _ in range(2):                                   # centre on the bounding box
            ex, uy = kp @ east, kp @ up
            c = c + east * (ex.max() + ex.min()) / 2 + up * (uy.max() + uy.min()) / 2
            c /= np.linalg.norm(c)
            east, up, _ = G.frame_axes(c)
        ex, uy = kp @ east, kp @ up
        self.c = c
        self.R = float(min(BOX[0] / np.abs(ex).max(), BOX[1] / np.abs(uy).max()))
        self.polys = []
        for i in self.keep:
            p = world.P[world.starts[i]:world.starts[i] + world.lens[i]]
            pts = np.stack([OC[0] + self.R * (p @ east), OC[1] - self.R * (p @ up)], 1)
            self.polys.append(np.vstack([pts, pts[:1]]))
        allxy = np.concatenate(self.polys)
        m = 60
        self.x0, self.y0 = int(allxy[:, 0].min()) - m, int(allxy[:, 1].min()) - m
        self.w, self.h = int(allxy[:, 0].max()) + m - self.x0, int(allxy[:, 1].max()) + m - self.y0
        self.lens = [np.concatenate([[0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))]) for p in self.polys]
        self.col = col
        self.full = self.neon(1.0)[0]
        self.fill_mask = self.mask()

    def local(self, p):
        return [(x - self.x0, y - self.y0) for x, y in p]

    def partial(self, p, L, frac):
        """The first `frac` of a polyline, and its tip."""
        cut = frac * L[-1]
        k = int(np.searchsorted(L, cut))
        if k <= 0:
            return p[:1], p[0]
        if k >= len(p):
            return p, p[-1]
        a = (cut - L[k - 1]) / max(L[k] - L[k - 1], 1e-9)
        tip = p[k - 1] + a * (p[k] - p[k - 1])
        return np.vstack([p[:k], tip]), tip

    def neon(self, frac):
        ss = 2
        core = Image.new("RGBA", (self.w * ss, self.h * ss))
        glow = Image.new("RGBA", (self.w, self.h))
        dc, dg = ImageDraw.Draw(core), ImageDraw.Draw(glow)
        tips = []
        for p, L in zip(self.polys, self.lens):
            seg, tip = self.partial(p, L, frac) if frac < 1 else (p, None)
            if len(seg) < 2:
                continue
            pts = self.local(seg)
            dg.line(pts, fill=self.col + (230,), width=22, joint="curve")
            dc.line([(x * ss, y * ss) for x, y in pts], fill=(255, 255, 255, 255), width=7 * ss, joint="curve")
            if tip is not None:
                tips.append((tip[0] - self.x0, tip[1] - self.y0))
        glow = glow.filter(ImageFilter.GaussianBlur(11))
        out = Image.new("RGBA", (self.w, self.h))
        out.alpha_composite(glow)
        out.alpha_composite(glow)
        out.alpha_composite(core.resize((self.w, self.h), Image.LANCZOS))
        return out, tips

    def mask(self):
        ss = 2
        m = Image.new("L", (self.w * ss, self.h * ss))
        d = ImageDraw.Draw(m)
        for p in self.polys:
            d.polygon([(x * ss, y * ss) for x, y in self.local(p)], fill=255)
        return m.resize((self.w, self.h), Image.LANCZOS)

    def flag_fill(self, flag):
        allxy = np.concatenate(self.polys)
        bx0, by0 = allxy[:, 0].min() - self.x0, allxy[:, 1].min() - self.y0
        bw, bh = allxy[:, 0].max() - allxy[:, 0].min(), allxy[:, 1].max() - allxy[:, 1].min()
        fl = flag.resize((max(2, int(bw * 1.04)), max(2, int(bh * 1.04))), Image.BILINEAR).convert("RGBA")
        lay = Image.new("RGBA", (self.w, self.h))
        lay.paste(fl, (int(bx0 + bw / 2 - fl.width / 2), int(by0 + bh / 2 - fl.height / 2)))
        lay.putalpha(self.fill_mask)
        return lay


def spark():
    s = Image.new("RGBA", (90, 90))
    d = ImageDraw.Draw(s)
    d.ellipse((20, 20, 70, 70), fill=(255, 255, 255, 120))
    s = s.filter(ImageFilter.GaussianBlur(9))
    ImageDraw.Draw(s).ellipse((36, 36, 54, 54), fill=(255, 255, 255, 255))
    return s


def question_card():
    a = join(rtext("NAME THIS COUNTRY", 66, stroke=7), emoji("✏", 62), gap=12)
    b = rtext("from its outline only", 40, fill=GOLD, stroke=4)
    card = rounded_card(max(a.width, b.width) + 80, a.height + b.height + 30, 44, (14, 6, 40, 230),
                        outline=CYAN + (255,), width=5)
    paste_center(card, a, card.width / 2, 16 + a.height / 2)
    paste_center(card, b, card.width / 2, 14 + a.height + b.height / 2)
    return card


# ----------------------------------------------------------------------------
# rounds
# ----------------------------------------------------------------------------
class Round(mv.Scene):
    def __init__(self, idx, r, prev_tier, ui, tts):
        super().__init__()
        code, fcode, name, fact, femoji, tier, prompt, said, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        v_q = tts.say(prompt, speed=1.16) if tts else None
        q_len = len(v_q) / SR if v_q is not None else 0.9
        c0 = max(5 if self.bonus else 4, math.ceil((0.12 + q_len - 0.1) / B))
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.reveal = (c0 + n) * B
        self.dur = self.reveal + ((6 if self.bonus else 6) + (5 if self.cta else 0)) * B
        self.cta_at = 2.6 * B
        self.col, e = TIERS[tier]
        world = ui["globe"].world
        self.target = world.codes.index(code)
        self.ol = Outline(world, code, CYAN if not self.danger else self.col)
        self.flag = Image.open(os.path.join(FLAG_DIR, fcode + ".png")).convert("RGBA")
        self.fill = self.ol.flag_fill(self.flag)
        self.cols = mm.flag_colours(self.flag)
        self.tiles = mm.Tiles(name, tier in ("HARD", "INSANE", "IMPOSSIBLE", "BONUS"))
        fs = 42
        while rfont(fs).getlength(fact) > 780 and fs > 26:
            fs -= 1
        body = join(emoji(femoji, 52), rtext(fact, fs, stroke=0), gap=14)
        self.fact = rounded_card(body.width + 56, body.height + 22, (body.height + 22) // 2, INK + (232,))
        paste_center(self.fact, body, self.fact.width / 2, self.fact.height / 2)
        self.sticker = emoji(stick, 140)
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
        self.tile_at = DRAW + 0.2
        self.opener = None                                  # set on round 1 when there is no intro
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (0.1, mv.sfx_riser(DRAW), 0.45),
                        (0.1 + DRAW, mv.sfx_pop(), 0.8), (0.1 + DRAW, mq.sfx_boom(), 0.5)]
        for k in range(8):                                   # the pen ticking along the border
            self.sounds.append((0.1 + k * DRAW / 8, mv.sfx_click(), 0.35))
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
        self.sounds += [(rv0, mq.sfx_boom(), 1.0), (rv0, mv.sfx_ding(), 1.0), (rv0 + 0.05, mq.sfx_pling(), 0.6),
                        (rv0 + 0.7, mv.sfx_whoosh(0.8), 0.7), (rv0 + 0.75, mq.sfx_boom(), 0.4),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
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
        rr = random.Random(idx * 37)
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1350, -450), rr.randint(12, 26), rr.choice(self.cols),
                      rr.uniform(0, 3)) for _ in range(70)]

    def outline_layer(self, t, rv):
        """The neon outline (drawing itself, then complete), and the flag fill after the drop."""
        ol = self.ol
        if rv <= 0:
            frac = clamp((t - 0.1) / DRAW)
            if frac < 1:
                img, tips = ol.neon(ease_in_out(frac))
                return img, tips
            return ol.full, []
        lay = ol.full.copy()
        k = clamp(rv / 0.18)
        fill = self.fill.copy()
        fill.putalpha(fill.getchannel("A").point(lambda v, k=k: int(v * k)))
        out = Image.new("RGBA", lay.size)
        out.alpha_composite(fill)
        out.alpha_composite(lay)
        return out, []

    def render(self, t, header=True):
        T = self.t0 + t
        rv = t - self.reveal
        ui = self.ui
        pulse = beat_pulse(T) if t > DRAW else 0.0
        im = ui["bg"].render(T, self.col if self.danger else CYAN, pulse)
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(Image.new("RGBA", (W, H), (120, 0, 30, 30)))
            im.alpha_composite(ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        # the map fades in around the shape and the camera pulls back to show where it is
        ga = clamp((rv - 0.7) / 0.35) if rv > 0 else 0.0
        if ga > 0:
            ol = self.ol
            k = ease_in_out(clamp((rv - 0.85) / 1.0))
            R = ol.R * math.exp(math.log(0.42) * k)
            gim = ui["globe"].render(ol.c, R, OC, ol.keep, 1.0, self.flag, 1.0)
            ui["cmap"].draw(gim, ol.c, R, OC, self.target, 0.75, 0.0)
            gim.alpha_composite(ui["shade"])
            if ga < 1:
                gim.putalpha(gim.getchannel("A").point(lambda v, a=ga: int(v * a)))
            im.alpha_composite(gim)
        # the outline itself
        if ga < 1:
            lay, tips = self.outline_layer(t, rv)
            s = 1.0
            rot = 0.0
            if rv <= 0:
                s = 0.6 + 0.4 * ease_out_back(clamp(t / 0.35), 1.6)
                if t > DRAW:
                    s *= 1 + 0.02 * pulse
                    rot = 3 * math.sin((t - DRAW) * 1.6)
                for b in self.count_beats:
                    tb = t - b * B
                    if 0 <= tb < 0.25:
                        s *= 1 + (0.08 if self.danger else 0.05) * (1 - ease_out_cubic(tb / 0.25))
            else:
                s = 1 + 0.12 * (1 - ease_out_cubic(clamp(rv / 0.35))) * (1 if rv > 0.02 else 0)
            sp = scaled(lay, s) if abs(s - 1) > 1e-3 else lay
            if abs(rot) > 0.05:
                sp = sp.rotate(rot, Image.BICUBIC, expand=True)
            cx = OC[0] + (self.ol.x0 + self.ol.w / 2 - OC[0]) * s
            cy = OC[1] + (self.ol.y0 + self.ol.h / 2 - OC[1]) * s
            paste_center(im, sp, cx, cy, 1 - ga)
            for x, y in tips:                                 # the spark racing along the border
                gx = OC[0] + (x + self.ol.x0 - OC[0]) * s
                gy = OC[1] + (y + self.ol.y0 - OC[1]) * s
                paste_center(im, ui["spark"], gx, gy)
        if rv > 0:
            im.alpha_composite(cq.speed_lines(1 - clamp(rv / 0.45), self.idx, OC))
        d = ImageDraw.Draw(im)
        if header:
            paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
            x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
            frac = 1.0 if t < DRAW else max(0.0, 1 - (t - DRAW) / (self.reveal - DRAW))
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
        kc = 1.0 if self.opener is not None else ease_out_back(clamp((t - 0.05) / 0.3), 1.6)
        if kc > 0.01:
            paste_center(im, scaled(ui["card"], kc * (1 + 0.015 * beat_pulse(T))), W / 2, CARD_Y)
        self.tiles.draw(im, t - self.tile_at, rv)
        if self.banner is not None and 0.05 < t < DRAW + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - DRAW + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, NUM_Y, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a * 0.9)
        cta_on = self.cta and rv > self.cta_at
        if rv > 0:
            for vx, vy, sz, cc, spin in self.conf:
                px, py = OC[0] + vx * rv, OC[1] + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    dd = ImageDraw.Draw(im)
                    dd.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                 outline=INK + (255,))
            sk = ease_out_back((rv - 0.3) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             925, 1330)
            fk = ease_out_back((rv - 0.9) / 0.3)
            if fk > 0.01 and not cta_on:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * fl))))
            im = shake(im, 30 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 16 * (1 - rv / 0.18))
            if 0.7 < rv < 0.8:                               # a whip as the map arrives
                im = rgb_split(mm.zoom_blur(im, 0.5 * (1 - (rv - 0.7) / 0.1)), 10)
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
        if self.opener is not None and t < self.count_beats[0] * B:   # no intro: PART badge on the first round
            to = t
            sk = 1 + 0.35 * (1 - ease_out_cubic(clamp(to / 0.18)))
            a = 1 - clamp((t - (self.count_beats[0] * B - 0.3)) / 0.3)
            paste_center(im, scaled(self.opener, sk * (1 + 0.04 * beat_pulse(T))).rotate(-5, Image.BICUBIC,
                                                                                        expand=True), W / 2, 640, a)
        if t < 0.16 and self.opener is None:
            im = rgb_split(mm.zoom_blur(im, 0.6 * (1 - t / 0.16)), 16 * (1 - t / 0.16))
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(mm.zoom_blur(im, 0.6 * out), 20 * out)
        return im


# ----------------------------------------------------------------------------
# intro: the title, said and slammed in word by word, over glowing outlines
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    TEASE, MONTAGE = 10, (9, 8)

    def __init__(self, ui, tts, rounds):
        super().__init__()
        self.ui, self.rounds = ui, rounds
        self.dur = 6 * B
        hb = 0.5 * B
        clips = [tts.say(w, speed=1.24) for w in INTRO_WORDS] if tts else None
        lens = [len(c) / SR for c in clips] if clips else [0.75, 0.75, 1.0]
        self.slams = [0.0]
        for ln in lens:
            prev = self.slams[-1]
            self.slams.append(max(prev + hb, round((prev + ln - 0.08) / hb) * hb))
        self.slams[-1] = min(self.slams[-1], self.dur - 0.4)
        if clips:
            for at, c in zip(self.slams, clips):
                self.voices.append((at, c))
        self.o3 = join(rtext("answer at the end", 58, fill=GOLD, stroke=7), emoji("👀", 62))
        self.w1 = fit(rtext("GUESS THE COUNTRY", 128, stroke=12), 990)
        self.w2 = fit(join(rtext("BY ITS OUTLINE", 120, fill=CYAN, stroke=12), emoji("✏", 104), gap=12), 990)
        self.w3 = mcq.part_badge(PART, 140).rotate(-4, Image.BICUBIC, expand=True) if PART else \
            join(rtext("99% FAIL", 150, fill=PINK, stroke=14), emoji("💀", 140))
        self.part = mcq.part_badge(PART, 84) if PART else None
        self.l1 = fit(rtext("GUESS THE COUNTRY", 112, stroke=11), 990)
        self.l2 = fit(join(rtext("BY ITS OUTLINE", 104, fill=CYAN, stroke=10), emoji("✏", 92), gap=12), 990)
        self.l3 = join(rtext("99% FAIL", 116, fill=PINK, stroke=11), emoji("💀", 112))
        self.sounds += [(0.0, sfx_heartbeat(), 0.9), (B, sfx_heartbeat(), 0.7),
                        (self.slams[2], mv.sfx_riser(self.slams[3] - self.slams[2]), 0.6),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k, at in enumerate(self.slams):
            self.sounds += [(at, mq.sfx_boom(), 1.0 if k in (0, 3) else 0.75), (at, mv.sfx_whoosh(0.35), 0.6),
                            (at, mv.sfx_pop(), 0.8)]
            if k:
                self.sounds.append((at, mq.sfx_glitch(), 0.45))

    def outline_frame(self, r, T):
        im = self.ui["bg"].render(T, r.col if r.danger else CYAN, beat_pulse(T))
        sp = scaled(r.ol.full, 1 + 0.03 * beat_pulse(T)).rotate(3 * math.sin(T * 1.6), Image.BICUBIC, expand=True)
        paste_center(im, sp, r.ol.x0 + r.ol.w / 2, r.ol.y0 + r.ol.h / 2)
        return im

    def render(self, t):
        T = self.t0 + t
        k = max(i for i, at in enumerate(self.slams) if at <= t + 1e-9)
        ts = t - self.slams[k]
        slam = 1 + 0.35 * (1 - ease_out_cubic(clamp(ts / 0.18)))
        if k < 3:                                            # word slams over mystery outlines
            r = self.rounds[(self.TEASE, self.MONTAGE[0], self.MONTAGE[1])[k]]
            im = self.outline_frame(r, T)
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 70)))
            words = [(self.w1, 330, -3), (self.w2, 480, 2), (self.w3, 1700, -2)]
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
        gc = (540, 1270)
        R = 470 * (1 + 0.05 * beat_pulse(T)) * (1.25 - 0.25 * ease_out_cubic(clamp(ts / 0.3)))
        c = G.unit(10 + 50 * t, 25)
        im = self.ui["big_globe"].render(c, R, gc)
        self.ui["cmap"].draw(im, c, R, gc, None, 0.75 + 0.2 * beat_pulse(T))
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 40)))
        for j, (img, y, rot) in enumerate([(self.l1, 330, -3), (self.l2, 490, 2), (self.l3, 660, -2)]):
            sc = (slam if j == 2 else 1 + 0.12 * (1 - ease_out_cubic(clamp(ts / 0.18)))) * (1 + 0.03 * beat_pulse(T))
            paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
        if self.part is not None:
            paste_center(im, scaled(self.part, slam * (1 + 0.04 * beat_pulse(T))).rotate(5, Image.BICUBIC, expand=True),
                         W / 2, 830)
        im = shake(im, 22 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
        if ts < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - ts / 0.08)))))
        whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


def build(voice="am_adam", voice_pack=None, with_intro=True):
    if voice_pack:
        tts = cq.Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    world = G.World()
    globe = G.GlobeRenderer(W, H, world)
    ui = {"globe": globe, "big_globe": globe, "bg": NeonBG(), "shade": mm.shade_overlay(0.8),
          "vig": [mc.red_vignette(i / 10) for i in range(11)], "cmap": mcq.ColourMap(world),
          "spark": spark(), "card": question_card()}
    rounds, prev = [], ROUNDS[0][5]
    for i, r in enumerate(ROUNDS, 1):
        rounds.append(Round(i, r, prev, ui, tts))
        prev = r[5]
    if with_intro:
        intro = Intro(ui, tts, rounds)
        scenes = [intro, *rounds, bq.Ending(ui, intro, tts)]
    else:                                                   # round 1 opens the video; the ending loops back to it
        first = rounds[0]
        first.opener = mcq.part_badge(PART, 96) if PART else join(rtext("99% FAIL", 96, fill=PINK, stroke=10),
                                                                  emoji("💀", 96))
        first.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_pop(), 0.8)]
        scenes = [*rounds, bq.Ending(ui, first, tts)]
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(scenes, ui, path):
    r = scenes[1 + COVER]                                    # a striking outline (Vietnam, Iceland)
    im = ui["bg"].render(1.0, CYAN, 0.8)
    paste_center(im, scaled(r.ol.full, 1.05), r.ol.x0 + r.ol.w / 2, r.ol.y0 + r.ol.h / 2)
    paste_center(im, fit(rtext("GUESS THE COUNTRY", 112, stroke=11), 1000).rotate(-3, Image.BICUBIC, expand=True),
                 W / 2, 230)
    paste_center(im, fit(join(rtext("BY ITS OUTLINE", 104, fill=CYAN, stroke=10), emoji("✏", 92), gap=12), 1000)
                 .rotate(2, Image.BICUBIC, expand=True), W / 2, 380)
    paste_center(im, rtext("?", 260, fill=(255, 255, 255), stroke=16), 760, 1000)
    paste_center(im, join(rtext("99% FAIL", 110, fill=PINK, stroke=11), emoji("💀", 110)), W / 2, 1700)
    if PART:
        paste_center(im, mcq.part_badge(PART, 80).rotate(-6, Image.BICUBIC, expand=True), W / 2, 1530)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", type=int, default=1, choices=sorted(EPISODES))
    ap.add_argument("--out", default=None)
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--music", default="phonk", choices=["phonk", "none"])
    ap.add_argument("--no-intro", action="store_true", help="start straight on round 1")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    set_episode(a.episode)
    a.out = a.out or os.path.join(HERE, f"short_{NAME}.mp4")
    quiet = a.stills or a.cover
    scenes, starts, total, ui = build(a.voice if not quiet else "none", None if quiet else a.voice_pack,
                                      with_intro=not a.no_intro)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    if a.cover:
        make_cover(scenes, ui, os.path.join(HERE, f"{NAME}_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"outline{a.episode}_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, f"render_{NAME}")
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
