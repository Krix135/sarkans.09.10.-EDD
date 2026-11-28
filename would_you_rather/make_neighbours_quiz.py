#!/usr/bin/env python3
""""GUESS THE COUNTRY BY ITS NEIGHBOURS" Short (1080x1920).

Each round the globe flies to a region where the mystery country sits dark in the middle with a pulsing
outline and a "?". Its neighbours pop up one by one on the half beats, each filled with its own flag and
a name tag; everything else stays dark. A 3-2-1 runs on the beat; on the drop the mystery country fills
with its flag, the tiles flip to its name, the map fades in around it and the camera pulls back to show
where it is, with a fun fact. Every neighbour list was checked against the map data (no missing or extra
neighbours). Spoken-title intro (6 beats), EASY -> IMPOSSIBLE plus a bonus, one like call-out after
round 3, looping score screen. Borders: Natural Earth (public domain). Flags: public domain.

    python3 make_neighbours_quiz.py
    python3 make_neighbours_quiz.py --stills 0,5,9
    python3 make_neighbours_quiz.py --cover
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
from scipy.ndimage import distance_transform_edt  # noqa: E402

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
GC = (540, 1005)
MAP_BOX = (30, 560, 1050, 1450)      # where name tags may go
CARD_Y = 438
NUM_Y = 600
mm.TILE_Y = 1530
FACT_Y = 1640
CTA_Y = 1665
FLY_BEATS = 3
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
DIM = (34, 30, 62)
FOG = (12, 6, 34)

COUNTRIES = {
    "PRT": ("PORTUGAL", "PT"), "ESP": ("SPAIN", "ES"), "USA": ("USA", "US"), "CAN": ("CANADA", "CA"),
    "MEX": ("MEXICO", "MX"), "DEU": ("GERMANY", "DE"), "DNK": ("DENMARK", "DK"), "POL": ("POLAND", "PL"),
    "CZE": ("CZECHIA", "CZ"), "AUT": ("AUSTRIA", "AT"), "CHE": ("SWITZERLAND", "CH"), "FRA": ("FRANCE", "FR"),
    "LUX": ("LUXEMBOURG", "LU"), "BEL": ("BELGIUM", "BE"), "NLD": ("NETHERLANDS", "NL"), "NOR": ("NORWAY", "NO"),
    "SWE": ("SWEDEN", "SE"), "FIN": ("FINLAND", "FI"), "RUS": ("RUSSIA", "RU"), "ARG": ("ARGENTINA", "AR"),
    "CHL": ("CHILE", "CL"), "BOL": ("BOLIVIA", "BO"), "PRY": ("PARAGUAY", "PY"), "BRA": ("BRAZIL", "BR"),
    "URY": ("URUGUAY", "UY"), "VNM": ("VIETNAM", "VN"), "CHN": ("CHINA", "CN"), "LAO": ("LAOS", "LA"),
    "KHM": ("CAMBODIA", "KH"), "PER": ("PERU", "PE"), "BLR": ("BELARUS", "BY"), "UKR": ("UKRAINE", "UA"),
    "LTU": ("LITHUANIA", "LT"), "LVA": ("LATVIA", "LV"), "MNG": ("MONGOLIA", "MN"), "GMB": ("THE GAMBIA", "GM"),
    "SEN": ("SENEGAL", "SN"),
}
ROUNDS = [  # mystery, neighbours (all of them), fact, emoji, tier, prompt, spoken answer, sticker
    ("PRT", ["ESP"], "it has the world's oldest alliance, with England, since 1373", "🤝", "EASY",
     "Which country is hiding in the middle? Its only neighbour is Spain!", "Portugal!", "😎"),
    ("USA", ["CAN", "MEX"], "its border with Canada is the longest in the world", "📏", "EASY",
     "It borders Canada and Mexico!", "The USA!", "🔥"),
    ("DEU", ["DNK", "POL", "CZE", "AUT", "CHE", "FRA", "LUX", "BEL", "NLD"], "Berlin has more bridges than Venice",
     "🌉", "EASY", "This one has nine neighbours!", "Germany!", "🤔"),
    ("NOR", ["SWE", "FIN", "RUS"], "it has over 1,000 fjords", "🏔", "MEDIUM", "Sweden, Finland and Russia!",
     "Norway!", "😳"),
    ("ARG", ["CHL", "BOL", "PRY", "BRA", "URY"], "it has one of the widest avenues in the world", "🛣", "MEDIUM",
     "Chile, Bolivia, Paraguay, Brazil and Uruguay!", "Argentina!", "🤯"),
    ("VNM", ["CHN", "LAO", "KHM"], "it's the world's 2nd biggest coffee producer", "☕", "MEDIUM",
     "China, Laos and Cambodia!", "Vietnam!", "🔥"),
    ("BOL", ["BRA", "PRY", "ARG", "CHL", "PER"], "it has the world's largest salt flat", "🧂", "HARD",
     "Hard level! Five neighbours, and no sea!", "Bolivia!", "😱"),
    ("BLR", ["RUS", "UKR", "POL", "LTU", "LVA"], "it has over 10,000 lakes", "🌊", "HARD",
     "Russia, Ukraine, Poland, Lithuania and Latvia!", "Belarus!", "💀"),
    ("MNG", ["RUS", "CHN"], "Genghis Khan founded the Mongol Empire here", "🐎", "INSANE",
     "Insane level! Its only neighbours are Russia and China!", "Mongolia!", "🧠"),
    ("LUX", ["FRA", "BEL", "DEU"], "public transport is free for everyone", "🚌", "IMPOSSIBLE",
     "Impossible level! France, Belgium and Germany!", "Luxembourg!", "☠"),
    ("GMB", ["SEN"], "it's the smallest country in mainland Africa", "🌍", "BONUS",
     "Bonus! Its only neighbour is Senegal!", "The Gambia!", "👑"),
]
INTRO_WORDS = ("Guess the country", "by its neighbours!", "Ninety-nine percent fail!")
LAYERS = {}                          # the round being rendered keeps its prepared layers here


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


def flag(code):
    return Image.open(os.path.join(FLAG_DIR, COUNTRIES[code][1] + ".png")).convert("RGBA")


def name_tag(code, size=34):
    fl = flag(code)
    fl.thumbnail((int(size * 1.6), int(size * 1.05)), Image.LANCZOS)
    fb = Image.new("RGBA", (fl.width + 6, fl.height + 6), (255, 255, 255, 255))
    fb.paste(fl, (3, 3), fl)
    body = join(fb, rtext(COUNTRIES[code][0], size, stroke=4), gap=10)
    card = rounded_card(body.width + 30, body.height + 16, (body.height + 16) // 2, (12, 10, 30, 235),
                        outline=(255, 255, 255, 255), width=3)
    paste_center(card, body, card.width / 2, card.height / 2)
    return card


def question_card(n):
    a = join(rtext("WHICH COUNTRY IS IN THE MIDDLE?", 50, stroke=6), emoji("🧩", 52), gap=10)
    hint = "ITS ONLY NEIGHBOUR" if n == 1 else f"IT BORDERS ALL {n} OF THESE"
    h = join(rtext(hint, 42, fill=GOLD, stroke=5), emoji("👇", 44), gap=10)
    pill = rounded_card(h.width + 40, h.height + 12, (h.height + 12) // 2, (40, 20, 70, 255), outline=GOLD + (255,),
                        width=3)
    paste_center(pill, h, pill.width / 2, pill.height / 2)
    card = rounded_card(min(1040, max(a.width, pill.width) + 60), a.height + pill.height + 48, 44, (14, 6, 40, 232),
                        outline=CYAN + (255,), width=5)
    paste_center(card, a, card.width / 2, 20 + a.height / 2)
    paste_center(card, pill, card.width / 2, 28 + a.height + pill.height / 2)
    return card


def project(world, c, R, center):
    """Screen coordinates of every border point and which polygons are on screen (as the globe does it)."""
    east, up, view = G.frame_axes(c)
    sx, sy, dep = world.P @ east, world.P @ up, world.P @ view
    hidden = dep < 0
    nrm = np.hypot(sx, sy)
    nrm[nrm == 0] = 1
    sx = np.where(hidden, sx / nrm, sx)
    sy = np.where(hidden, sy / nrm, sy)
    X, Y = center[0] + R * sx, center[1] - R * sy
    vis = np.maximum.reduceat(dep, world.starts) > 0
    minx, maxx = np.minimum.reduceat(X, world.starts), np.maximum.reduceat(X, world.starts)
    miny, maxy = np.minimum.reduceat(Y, world.starts), np.maximum.reduceat(Y, world.starts)
    on = vis & (maxx > -50) & (minx < W + 50) & (maxy > -50) & (miny < H + 50) & ((maxx - minx) + (maxy - miny) > 1)
    return X, Y, on


def polys_of(world, ci, X, Y, on):
    out = []
    for i in np.nonzero((np.asarray(world.owner) == ci) & on)[0]:
        s, n = world.starts[i], world.lens[i]
        out.append(list(zip(X[s:s + n].tolist(), Y[s:s + n].tolist())))
    return out


def mask_of(polys):
    m = Image.new("L", (W, H))
    d = ImageDraw.Draw(m)
    for p in polys:
        if len(p) > 2:
            d.polygon(p, fill=255)
    return m


def label_point(m):
    """The point inside the country (and inside the map area) farthest from its edges."""
    x0, y0, x1, y1 = MAP_BOX
    a = np.asarray(m.crop((x0, y0, x1, y1)).resize(((x1 - x0) // 4, (y1 - y0) // 4), Image.BILINEAR)) > 127
    if not a.any():
        return None
    dist = distance_transform_edt(a)
    iy, ix = np.unravel_index(np.argmax(dist), dist.shape)
    return x0 + ix * 4 + 2, y0 + iy * 4 + 2


def flag_layer(polys, fl, m):
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    bx0, bx1 = max(min(xs), -40), min(max(xs), W + 40)                 # the flag covers the part on screen
    by0, by1 = max(min(ys), -40), min(max(ys), H + 40)
    bw, bh = max(2, int(bx1 - bx0)), max(2, int(by1 - by0))
    lay = Image.new("RGBA", (W, H))
    lay.paste(fl.resize((bw, bh), Image.BILINEAR), (int(bx0), int(by0)))
    lay.putalpha(m)
    d = ImageDraw.Draw(lay)
    for p in polys:
        d.line(p + [p[0]], fill=(255, 255, 255, 255), width=3)
    return lay


# ----------------------------------------------------------------------------
# rounds
# ----------------------------------------------------------------------------
class Round(mv.Scene):
    def __init__(self, idx, r, prev_view, prev_tier, ui, tts):
        super().__init__()
        code, nbs, fact, femoji, tier, prompt, said, stick = r
        self.idx, self.ui, self.tier, self.code, self.nbs = idx, ui, tier, code, nbs
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = FLY_BEATS
        self.fly = f * B
        self.nb_at = [self.fly + 0.15 + j * 0.5 * B * (0.6 if len(nbs) > 6 else 1.0) for j in range(len(nbs))]
        v_q = tts.say(prompt, speed=1.16) if tts else None
        q_len = len(v_q) / SR if v_q is not None else 2.2
        c0 = max(math.ceil((self.nb_at[-1] + 0.45) / B), math.ceil((0.12 + q_len - 0.1) / B), f + 2)
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.reveal = (c0 + n) * B
        self.dur = self.reveal + (6 + (5 if self.cta else 0)) * B
        self.cta_at = 2.6 * B
        world = ui["globe"].world
        self.target = world.codes.index(code)
        cc, near, _ = world.country(code)
        self.near = near
        self.c, self.R = self.view(world, code)
        self.cam = mm.Camera(prev_view, (self.c, self.R), self.fly, self.reveal)
        self.end_view = (self.c, self.R * 0.42)
        self.mflag = flag(code)
        self.cols = mm.flag_colours(self.mflag)
        self.tiles = mm.Tiles(COUNTRIES[code][0], tier in ("HARD", "INSANE", "IMPOSSIBLE", "BONUS"))
        self.card = question_card(len(nbs))
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
        self.qmark = rtext("?", 150, stroke=13)
        self.tile_at = self.nb_at[-1] + 0.3
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (self.fly, mq.sfx_boom(), 0.6), (self.fly, mv.sfx_pop(), 0.6)]
        for at in self.nb_at:
            self.sounds += [(at, mv.sfx_pop(), 0.8), (at, mv.sfx_click(), 0.5)]
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
                        (rv0 + 0.75, mv.sfx_whoosh(0.8), 0.7), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
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
        rr = random.Random(idx * 43)
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1350, -450), rr.randint(12, 26), rr.choice(self.cols),
                      rr.uniform(0, 3)) for _ in range(70)]

    @staticmethod
    def view(world, code):
        """Centre on the mystery country, sized so it fills about half the map and its neighbours show around it."""
        ci = world.codes.index(code)
        idx = np.nonzero(world.owner == ci)[0]
        allp = np.concatenate([world.P[world.starts[i]:world.starts[i] + world.lens[i]] for i in idx])
        c0 = allp.mean(0) / np.linalg.norm(allp.mean(0))
        e0, u0, _ = G.frame_axes(c0)

        def area(i):                                         # by land area, so far-off islands don't count
            p = world.P[world.starts[i]:world.starts[i] + world.lens[i]]
            x, y = p @ e0, p @ u0
            return abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) / 2
        areas = {i: area(i) for i in idx}
        big = max(areas.values())
        keep = [max(areas, key=areas.get)] if code == "USA" else [i for i in idx if areas[i] >= 0.025 * big]
        pts = np.concatenate([world.P[world.starts[i]:world.starts[i] + world.lens[i]] for i in keep])
        c = pts.mean(0)
        c /= np.linalg.norm(c)
        for _ in range(2):
            east, up, _ = G.frame_axes(c)
            ex, uy = pts @ east, pts @ up
            c = c + east * (ex.max() + ex.min()) / 2 + up * (uy.max() + uy.min()) / 2
            c /= np.linalg.norm(c)
        east, up, _ = G.frame_axes(c)
        R = min(270 / np.abs(pts @ east).max(), 230 / np.abs(pts @ up).max())
        return c, float(np.clip(R, 500, 12000))

    def prep(self):
        """Layers for the still map (built when the round is first drawn, dropped when another round starts)."""
        if LAYERS.get("idx") == self.idx:
            return LAYERS
        LAYERS.clear()
        LAYERS["idx"] = self.idx
        world = self.ui["globe"].world
        X, Y, on = project(world, self.c, self.R, GC)
        base = self.ui["globe"].render(self.c, self.R, GC)
        dim = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(dim)
        skip = {world.codes.index(k) for k in self.nbs} | {self.target}
        for i in np.nonzero(on)[0]:
            if world.owner[i] in skip:
                continue
            s, n = world.starts[i], world.lens[i]
            pts = list(zip(X[s:s + n].tolist(), Y[s:s + n].tolist()))
            d.polygon(pts, fill=DIM + (238,))
            d.line(pts + [pts[0]], fill=(80, 70, 120, 255), width=2)
        base.alpha_composite(dim)
        nb = []
        small = len(self.nbs) >= 5
        for k in self.nbs:
            polys = polys_of(world, world.codes.index(k), X, Y, on)
            if not polys:
                continue
            m = mask_of(polys)
            nb.append((k, flag_layer(polys, flag(k), m), name_tag(k, 28 if small else 34), label_point(m)))
        mpolys = polys_of(world, self.target, X, Y, on)
        mm_ = mask_of(mpolys)
        nb = self.spread(nb, label_point(mm_) or GC)
        fog = Image.new("RGBA", (W, H), FOG + (255,))
        fog.putalpha(mm_)
        LAYERS.update(base=base, nb=nb, fog=fog, mflag=flag_layer(mpolys, self.mflag, mm_), mpolys=mpolys,
                      mpoint=label_point(mm_) or GC)
        return LAYERS

    @staticmethod
    def spread(nb, keep_clear):
        """Keep the tags on screen, apart from each other and off the mystery country's "?": every overlap is
        pushed apart along whichever axis needs the smaller move."""
        boxes = []                                           # [x, y, half width, half height]
        for k, lay, tag, pt in nb:
            boxes.append(None if pt is None else [pt[0], pt[1], tag.width / 2 + 5, tag.height / 2 + 5])
        qx, qy = keep_clear
        q = [qx, qy, 70, 85]

        def clampb(b):
            b[0] = min(max(b[0], b[2] + 8), W - b[2] - 8)
            b[1] = min(max(b[1], 572 + b[3]), 1455 - b[3])

        for b in boxes:
            if b:
                clampb(b)
        for _ in range(300):
            moved = False
            for i, a in enumerate(boxes):
                if a is None:
                    continue
                for other in [q] + boxes[i + 1:]:
                    if other is None:
                        continue
                    ox = a[2] + other[2] - abs(a[0] - other[0])
                    oy = a[3] + other[3] - abs(a[1] - other[1])
                    if ox <= 0 or oy <= 0:
                        continue
                    fixed = other is q
                    if ox < oy:
                        sgn = 1 if a[0] >= other[0] else -1
                        a[0] += sgn * (ox if fixed else ox / 2) + sgn
                        if not fixed:
                            other[0] -= sgn * ox / 2 + sgn
                    else:
                        sgn = 1 if a[1] >= other[1] else -1
                        a[1] += sgn * (oy if fixed else oy / 2) + sgn
                        if not fixed:
                            other[1] -= sgn * oy / 2 + sgn
                    clampb(a)
                    if not fixed:
                        clampb(other)
                    moved = True
            if not moved:
                break
        return [(k, lay, tag, (b[0], b[1]) if b else None) for (k, lay, tag, _), b in zip(nb, boxes)]

    def still_map(self, t, rv):
        L = self.prep()
        im = L["base"].copy()
        T = self.t0 + t
        tags = []
        for (k, lay, tag, pt), at in zip(L["nb"], self.nb_at):
            k_ = clamp((t - at) / 0.18)
            if k_ <= 0:
                continue
            if k_ < 1:
                lay = lay.copy()
                lay.putalpha(lay.getchannel("A").point(lambda v, a=k_: int(v * a)))
            im.alpha_composite(lay)
            if pt is not None:
                tags.append((tag, pt, t - at))
        if rv <= 0:
            im.alpha_composite(L["fog"])
            pulse = beat_pulse(T) if t > self.fly else 0.0
            d = ImageDraw.Draw(im, "RGBA")
            for p in L["mpolys"]:
                d.line(p + [p[0]], fill=CYAN + (int(110 + 80 * pulse),), width=int(10 + 8 * pulse))
                d.line(p + [p[0]], fill=(230, 250, 255, 255), width=3)
        else:
            k_ = clamp(rv / 0.18)
            lay = L["mflag"]
            if k_ < 1:
                lay = lay.copy()
                lay.putalpha(lay.getchannel("A").point(lambda v, a=k_: int(v * a)))
            im.alpha_composite(L["fog"])
            im.alpha_composite(lay)
        for tag, (x, y), age in tags:                         # name tags pop in with their country
            x = min(max(x, tag.width / 2 + 12), W - tag.width / 2 - 12)    # always fully on screen
            y = min(max(y, 600 + tag.height / 2), 1450 - tag.height / 2)
            s = ease_out_back(clamp(age / 0.25), 2.2)
            if s > 0.01:
                paste_center(im, scaled(tag, s), x, y)
            if 0 < age < 0.4:
                r_ = 30 + 160 * ease_out_cubic(age / 0.4)
                ImageDraw.Draw(im, "RGBA").ellipse((x - r_, y - r_, x + r_, y + r_),
                                                   outline=(255, 255, 255, int(220 * (1 - age / 0.4))), width=6)
        if rv <= 0:
            mx, my = L["mpoint"]
            paste_center(im, scaled(self.qmark, 0.55 + 0.08 * math.sin(t * 9)), mx, my)
        return im

    def render(self, t, header=True):
        T = self.t0 + t
        rv = t - self.reveal
        ui = self.ui
        if t < self.fly:                                     # fly in over a colour-lit globe
            c, R, blur = self.cam.at(t)
            im = ui["globe"].render(c, R, GC)
            ui["cmap"].draw(im, c, R, GC, None, 0.7, 0.0)
            im = rgb_split(mm.zoom_blur(im, blur), 22 * blur)
        else:
            im = self.still_map(t, rv)
            if rv <= 0:                                      # punch on every count beat
                for b in self.count_beats:
                    tb = t - b * B
                    if 0 <= tb < 0.25:
                        s = 1 + (0.07 if self.danger else 0.045) * (1 - ease_out_cubic(tb / 0.25))
                        big = scaled(im, s)
                        ox, oy = int(GC[0] * (s - 1)), int(GC[1] * (s - 1))
                        im = big.crop((ox, oy, ox + W, oy + H))
            ga = clamp((rv - 0.75) / 0.35) if rv > 0 else 0.0
            if ga > 0:                                       # the map fades in and the camera pulls back
                k = ease_in_out(clamp((rv - 0.9) / 1.0))
                R = self.R * math.exp(math.log(0.42) * k)
                gim = ui["globe"].render(self.c, R, GC, self.near, 1.0, self.mflag, 1.0)
                ui["cmap"].draw(gim, self.c, R, GC, self.target, 0.75, 0.0)
                if ga < 1:
                    gim.putalpha(gim.getchannel("A").point(lambda v, a=ga: int(v * a)))
                im.alpha_composite(gim)
            if 0 <= t - self.fly < 0.1:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - (t - self.fly) / 0.1)))))
        im.alpha_composite(ui["shade"])
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv > 0:
            im.alpha_composite(cq.speed_lines(1 - clamp(rv / 0.45), self.idx, GC))
        d = ImageDraw.Draw(im)
        if header:
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
        self.tiles.draw(im, t - self.tile_at, rv)
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, 760, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a * 0.9)
        cta_on = self.cta and rv > self.cta_at
        if rv > 0:
            mx, my = LAYERS.get("mpoint", GC) if LAYERS.get("idx") == self.idx else GC
            for vx, vy, sz, cc, spin in self.conf:
                px, py = mx + vx * rv, my + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    dd = ImageDraw.Draw(im)
                    dd.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                 outline=INK + (255,))
            sk = ease_out_back((rv - 0.3) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             925, 1340)
            fk = ease_out_back((rv - 0.9) / 0.3)
            if fk > 0.01 and not cta_on:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * fl))))
            im = shake(im, 30 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 16 * (1 - rv / 0.18))
            if 0.75 < rv < 0.85:
                im = rgb_split(mm.zoom_blur(im, 0.5 * (1 - (rv - 0.75) / 0.1)), 10)
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
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(mm.zoom_blur(im, 0.6 * out), 20 * out)
        return im


# ----------------------------------------------------------------------------
# intro: the title, said and slammed in word by word, over real questions
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    TEASE, MONTAGE = 10, (9, 8)

    def __init__(self, ui, tts, rounds):
        super().__init__()
        self.ui, self.rounds = ui, rounds
        self.dur = 6 * B
        hb = 0.5 * B
        clips = [tts.say(w, speed=1.24) for w in INTRO_WORDS] if tts else None
        lens = [len(c) / SR for c in clips] if clips else [0.75, 0.85, 1.0]
        self.slams = [0.0]
        for ln in lens:
            prev = self.slams[-1]
            self.slams.append(max(prev + hb, round((prev + ln - 0.08) / hb) * hb))
        self.slams[-1] = min(self.slams[-1], self.dur - 0.4)
        if clips:
            for at, c in zip(self.slams, clips):
                self.voices.append((at, c))
        self.o3 = join(rtext("answer at the end", 58, fill=GOLD, stroke=7), emoji("👀", 62))
        self.w1 = fit(rtext("GUESS THE COUNTRY", 130, stroke=12), 990)
        self.w2 = fit(join(rtext("BY ITS NEIGHBOURS", 110, fill=CYAN, stroke=11), emoji("🧩", 100), gap=12), 990)
        self.w3 = join(rtext("99% FAIL", 150, fill=PINK, stroke=14), emoji("💀", 140))
        self.l1 = fit(rtext("GUESS THE COUNTRY", 112, stroke=11), 990)
        self.l2 = fit(join(rtext("BY ITS NEIGHBOURS", 96, fill=CYAN, stroke=10), emoji("🧩", 88), gap=12), 990)
        self.l3 = join(rtext("99% FAIL", 116, fill=PINK, stroke=11), emoji("💀", 112))
        self.sounds += [(0.0, sfx_heartbeat(), 0.9), (B, sfx_heartbeat(), 0.7),
                        (self.slams[2], mv.sfx_riser(self.slams[3] - self.slams[2]), 0.6),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.9)]
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
        if k < 3:
            r = self.rounds[(self.TEASE, self.MONTAGE[0], self.MONTAGE[1])[k]]
            im = r.render(r.count_beats[0] * B - 0.1)
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 110)))
            words = [(self.w1, 760, -3), (self.w2, 930, 2), (self.w3, 1130, -2)]
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
        gc = (540, 1270)
        R = 470 * (1 + 0.05 * beat_pulse(T)) * (1.25 - 0.25 * ease_out_cubic(clamp(ts / 0.3)))
        c = G.unit(-10 + 50 * t, 25)
        im = self.ui["big_globe"].render(c, R, gc)
        self.ui["cmap"].draw(im, c, R, gc, None, 0.75 + 0.2 * beat_pulse(T))
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 40)))
        for j, (img, y, rot) in enumerate([(self.l1, 330, -3), (self.l2, 490, 2), (self.l3, 660, -2)]):
            sc = (slam if j == 2 else 1 + 0.12 * (1 - ease_out_cubic(clamp(ts / 0.18)))) * (1 + 0.03 * beat_pulse(T))
            paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
        im = shake(im, 22 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
        if ts < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - ts / 0.08)))))
        whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
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
    ui = {"globe": globe, "big_globe": globe, "shade": mm.shade_overlay(0.8),
          "vig": [mc.red_vignette(i / 10) for i in range(11)], "cmap": mcq.ColourMap(world)}
    rounds, view, prev = [], (G.unit(-10 + 50 * 6 * B, 25), 520.0), ROUNDS[0][4]
    for i, r in enumerate(ROUNDS, 1):
        sc = Round(i, r, view, prev, ui, tts)
        rounds.append(sc)
        view, prev = sc.end_view, r[4]
    intro = Intro(ui, tts, rounds)
    scenes = [intro, *rounds, bq.Ending(ui, intro, tts)]
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(scenes, ui, path):
    r = scenes[1 + 2]                                        # Germany: nine flags around a dark "?"
    im = r.render(r.count_beats[0] * B + 0.43, header=False)   # between beats: no number, no glitch
    im.alpha_composite(Image.new("RGBA", (W, 330), (10, 0, 30, 140)), (0, 0))
    paste_center(im, fit(join(rtext("WHO'S IN THE MIDDLE?", 96, stroke=10), emoji("🧩", 92), gap=10), 1000)
                 .rotate(-3, Image.BICUBIC, expand=True), W / 2, 190)
    paste_center(im, join(rtext("99% FAIL", 100, fill=PINK, stroke=10), emoji("💀", 100)), W / 2, 1760)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_neighbours_quiz.mp4"))
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
        make_cover(scenes, ui, os.path.join(HERE, "neighbours_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"nb_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_neighbours")
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
