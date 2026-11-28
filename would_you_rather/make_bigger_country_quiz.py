#!/usr/bin/env python3
""""WHICH COUNTRY IS BIGGER?" Short (1080x1920), part 3 formula.

Two globe panels per round, each zoomed so its country fills the frame (so the sizes look the same).
A 3-2-1 runs inside the VS badge on the beat; on the drop both globes zoom to the SAME scale, so the
real size difference shows at once, the areas count up, the bigger one gets a gold frame and a
BIGGER ribbon, and the gap pops up ("1.7x BIGGER" / "+57,000 km2"). Hook intro over a spinning globe,
EASY -> IMPOSSIBLE plus a bonus, one like call-out after round 3, looping score screen.
Areas: total area in km2 (CIA World Factbook figures, rounded to the nearest 1,000 on screen).
Borders: Natural Earth 1:50m (public domain).

    python3 make_bigger_country_quiz.py
    python3 make_bigger_country_quiz.py --stills 1,5,9
    python3 make_bigger_country_quiz.py --cover
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

import brand  # noqa: E402
import globe as G  # noqa: E402
import make_club_quiz as cq  # noqa: E402
import make_logo_quiz as lq  # noqa: E402
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
PW, PH = 1000, 600
PANEL_Y = (650, 1330)
VS_Y = 990
TIERS = mc.TIERS
ENTRY_BEATS = 2
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
COLORS = {0: ((255, 64, 140), (130, 0, 60), (255, 120, 200)),      # A: pink (the globe's own highlight)
          1: ((40, 190, 255), (0, 60, 130), (120, 215, 255))}     # B: cyan

COUNTRIES = {  # map code: name on screen, total area km2
    "RUS": ("RUSSIA", 17_098_242), "CAN": ("CANADA", 9_984_670), "BRA": ("BRAZIL", 8_515_770),
    "AUS": ("AUSTRALIA", 7_741_220), "IND": ("INDIA", 3_287_263), "EGY": ("EGYPT", 1_001_450),
    "GRL": ("GREENLAND", 2_166_086), "COD": ("DR CONGO", 2_344_858), "GBR": ("UNITED KINGDOM", 243_610),
    "NZL": ("NEW ZEALAND", 268_838), "JPN": ("JAPAN", 377_915), "DEU": ("GERMANY", 357_022),
    "MEX": ("MEXICO", 1_964_375), "IDN": ("INDONESIA", 1_904_569), "TUR": ("TURKEY", 783_562),
    "CHL": ("CHILE", 756_102), "ESP": ("SPAIN", 505_370), "SWE": ("SWEDEN", 450_295),
    "IRN": ("IRAN", 1_648_195), "MNG": ("MONGOLIA", 1_564_116), "ARG": ("ARGENTINA", 2_780_400),
    "KAZ": ("KAZAKHSTAN", 2_724_900),
}
ROUNDS = [  # A (top), B (bottom), tier, spoken question, spoken answer, reaction sticker
    ("CAN", "RUS", "EASY", "Which is bigger? Canada, or Russia?", "Russia! By a lot!", "😎"),
    ("BRA", "AUS", "EASY", "Brazil, or Australia?", "Brazil!", "🔥"),
    ("EGY", "IND", "EASY", "Egypt, or India?", "India! Over three times bigger!", "🤔"),
    ("COD", "GRL", "MEDIUM", "DR Congo, or Greenland?", "DR Congo! Greenland only looks huge!", "🤯"),
    ("NZL", "GBR", "MEDIUM", "New Zealand, or the UK?", "New Zealand!", "😳"),
    ("DEU", "JPN", "MEDIUM", "Germany, or Japan?", "Japan!", "🔥"),
    ("MEX", "IDN", "HARD", "Mexico, or Indonesia?", "Mexico! Just barely!", "😱"),
    ("CHL", "TUR", "HARD", "Chile, or Turkey?", "Turkey!", "💀"),
    ("ESP", "SWE", "INSANE", "Spain, or Sweden?", "Spain!", "🧠"),
    ("MNG", "IRN", "IMPOSSIBLE", "Mongolia, or Iran?", "Iran!", "☠"),
    ("KAZ", "ARG", "BONUS", "Bonus! Kazakhstan, or Argentina?", "Argentina! By a tiny bit!", "👑"),
]
INTRO_LINE = "Which country is bigger? Only one percent get them all!"
END_LINE = "How many did you get? Comment your score!"


def km2(v):
    return f"{int(round(v / 1000.0)) * 1000:,} km²"


# ----------------------------------------------------------------------------
# globe panels
# ----------------------------------------------------------------------------
def view_for(world, code, fx=0.4, fy=0.36):
    """Centre on the whole country and the zoom that makes it fill a PW x PH panel."""
    ci = world.codes.index(code)
    idx = np.nonzero(world.owner == ci)[0]
    big = max(world.lens[i] for i in idx)
    main = [i for i in idx if world.lens[i] >= 0.05 * big]   # ignore specks of island when framing
    pts = np.concatenate([world.P[world.starts[i]:world.starts[i] + world.lens[i]] for i in main])
    c = pts.mean(0)
    c /= np.linalg.norm(c)
    east, up, view = G.frame_axes(c)
    sx, sy = np.abs(pts @ east).max(), np.abs(pts @ up).max()
    R = float(np.clip(min(fx * PW / max(sx, 1e-3), fy * PH / max(sy, 1e-3)), 300, 14000))
    return c, R, idx


def rounded_mask(w, h, r):
    m = Image.new("L", (w * 2, h * 2))
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 2 - 1, h * 2 - 1), r * 2, fill=255)
    return m.resize((w, h), Image.LANCZOS)


class PanelArt:
    """Static parts of a panel: rounded mask, name strip, letter badge, white and gold edges."""

    def __init__(self):
        self.mask = rounded_mask(PW, PH, 52)
        g = np.zeros((PH, PW, 4), np.uint8)
        ys = np.arange(PH)[:, None]
        g[..., 3] = (np.clip((ys - PH * 0.62) / (PH * 0.38), 0, 1) ** 1.3 * 200).astype(np.uint8)
        self.shade = Image.fromarray(g, "RGBA")
        self.edge = {}
        for key, col, wd in (("white", (255, 255, 255), 6), ("gold", GOLD, 14)):
            e = Image.new("RGBA", (PW, PH))
            ImageDraw.Draw(e).rounded_rectangle((3, 3, PW - 4, PH - 4), 50, outline=col + (255,), width=wd)
            self.edge[key] = e

    def label(self, code, letter, col):
        name = COUNTRIES[code][0]
        out = Image.new("RGBA", (PW, PH))
        size = 66
        while rfont(size).getlength(name) > PW - 140 and size > 40:
            size -= 2
        t = rtext(name, size, stroke=6)
        out.alpha_composite(t, (40, PH - t.height - 24))
        badge = mv.circle(86, col + (255,))
        ImageDraw.Draw(badge).text((43, 45), letter, font=rfont(56), fill=(255, 255, 255), anchor="mm")
        out.alpha_composite(badge, (26, 24))
        return out


def tag(text, col=GOLD, size=58):
    t = rtext(text, size, fill=col, stroke=6)
    b = rounded_card(t.width + 56, t.height + 24, (t.height + 24) // 2, (12, 10, 30, 235), outline=col + (255,),
                     width=5)
    paste_center(b, t, b.width / 2, b.height / 2)
    return b


class GeoWall(lq.BrandWall):
    EMOJIS = ["🌍", "🗺", "🧭", "📍", "✈", "🌎", "🏔", "🌏"]


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    """6 beats over a spinning globe: WHICH COUNTRY / IS BIGGER? / 99% GET IT WRONG / the last one is IMPOSSIBLE."""

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 6 * B
        self.l1 = rtext("WHICH COUNTRY", 128, stroke=12)
        self.l2 = join(rtext("IS BIGGER?", 160, fill=GOLD, stroke=14), emoji("🌍", 140), gap=16)
        self.l3 = join(rtext("99% GET IT WRONG", 78, fill=PINK, stroke=8), emoji("💀", 82))
        self.l4a = rtext("the last one is", 62, stroke=6)
        self.l4 = rtext("IMPOSSIBLE", 96, fill=CYAN, stroke=9)
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9)]
        for k in range(1, 6):
            self.sounds += [(k * 0.5 * B * 2, mq.sfx_boom(), 0.6), (k * B, mv.sfx_pop(), 0.8)]
        self.sounds += [(4.5 * B, mv.sfx_riser(1.5 * B), 0.7), (6 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        if tts:
            self.voices.append((0.04, tts.say(INTRO_LINE, speed=1.15)))

    def render(self, t):
        T = self.t0 + t
        lon = -60 + 40 * t
        R = 520 * (1 + 0.04 * beat_pulse(T))
        im = self.ui["big_globe"].render(G.unit(lon, 18), R, (540, 1220))
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 60)))
        b = int(t / B)
        kk = (t % B) / B
        slam = 1 + 0.35 * (1 - ease_out_cubic(kk / 0.25))
        pulse = 1 + 0.035 * beat_pulse(T)
        paste_center(im, scaled(self.l1, (slam if b == 0 else 1.0) * pulse).rotate(-3, Image.BICUBIC, expand=True),
                     W / 2, 330)
        if b >= 1:
            paste_center(im, scaled(self.l2, (slam if b == 1 else 1.0) * pulse).rotate(2, Image.BICUBIC, expand=True),
                         W / 2, 500)
        if b >= 2:
            paste_center(im, scaled(self.l3, slam if b == 2 else 1.0), W / 2, 660)
        if b >= 4:
            paste_center(im, scaled(self.l4a, slam if b == 4 else 1.0), W / 2, 1720)
            paste_center(im, scaled(self.l4, (slam if b == 4 else 1.0) * (1 + 0.05 * math.sin(t * 14))), W / 2,
                         1810)
        im = shake(im, 22 * (1 - kk / 0.3) if kk < 0.3 and b in (0, 1, 2, 4) else 0, t)
        im = rgb_split(im, 12 * (1 - clamp(t / 0.25)))
        whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Round(mv.Scene):
    def __init__(self, idx, r, prev_tier, ui, tts):
        super().__init__()
        ka, kb, tier, spoken, said, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.codes = (ka, kb)
        self.areas = (COUNTRIES[ka][1], COUNTRIES[kb][1])
        self.win = 0 if self.areas[0] > self.areas[1] else 1
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        world = ui["globe"].world
        self.views = [view_for(world, k) for k in self.codes]
        self.Rc = min(v[1] for v in self.views) * 0.96       # common scale: the bigger country still fits
        f = ENTRY_BEATS
        v_q = tts.say(spoken, speed=1.08) if tts else None
        v_a = tts.say(said, speed=1.1) if tts else None
        v_c = tts.say(CTA_LINE, speed=1.1) if (tts and self.cta) else None
        q_len = len(v_q) / SR if v_q is not None else 2.2
        a_len = len(v_a) / SR if v_a is not None else 1.2
        c_len = len(v_c) / SR if v_c is not None else 2.8
        c0 = max(f + 3, math.ceil((0.15 + q_len + 0.2) / B))
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.fly = f * B
        self.reveal = (c0 + n) * B
        hold = max(5, math.ceil((0.1 + a_len + 0.6) / B))
        self.cta_at = max(3, math.ceil((0.1 + a_len + 0.3) / B)) * B
        if self.cta:
            hold = max(hold, math.ceil((self.cta_at + c_len + 0.5) / B))
        self.dur = (c0 + n + hold) * B
        art = ui["art"]
        self.labels = [art.label(k, "AB"[s], COLORS[s][0]) for s, k in enumerate(self.codes)]
        self.dim = Image.new("RGBA", (PW, PH), (4, 0, 16, 150))
        self.dim.putalpha(Image.fromarray((np.asarray(art.mask).astype(np.float32) * 150 / 255).astype(np.uint8)))
        self.hidden = tag("? km²", (255, 255, 255), 54)
        rb = join(rtext("BIGGER", 58, fill=INK, stroke=0), emoji("👑", 58), gap=10)
        rib = rounded_card(rb.width + 50, rb.height + 24, 24, GOLD + (255,), outline=INK + (255,), width=5)
        paste_center(rib, rb, rib.width / 2, rib.height / 2)
        self.ribbon = rib.rotate(-6, Image.BICUBIC, expand=True)
        big, small = max(self.areas), min(self.areas)
        ratio = big / small
        self.diff = tag(f"{ratio:.1f}x BIGGER" if ratio >= 1.3 else f"+{int(round((big - small) / 1000)) * 1000:,} km²",
                        (90, 230, 140), 54)
        sn = join(emoji("📏", 44), rtext("SAME SCALE", 44, stroke=5), gap=10)
        self.scale_note = rounded_card(sn.width + 50, sn.height + 22, (sn.height + 22) // 2, (12, 10, 30, 235),
                                       outline=(255, 255, 255, 255), width=4)
        paste_center(self.scale_note, sn, self.scale_note.width / 2, self.scale_note.height / 2)
        self.sticker = emoji(stick, 140)
        self.col, e = TIERS[tier]
        self.count = rtext("BONUS" if self.bonus else f"{idx}/10", 46, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        self.tagimg = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, self.col + (255,),
                                   outline=INK + (255,), width=3)
        ImageDraw.Draw(self.tagimg).text((self.tagimg.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.title = join(rtext("WHICH IS BIGGER?", 54, stroke=6), emoji("🌍", 54), gap=10)
        self.level_up = tier != prev_tier and idx > 1
        self.banner = None
        if self.level_up:
            label = "BONUS: ONLY 1% KNOW THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 62 if self.bonus else 92, fill=self.col, stroke=9), emoji(e, 90))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        self.badge = mv.circle(190, (255, 255, 255, 255))
        ImageDraw.Draw(self.badge).text((95, 98), "VS", font=rfont(84), fill=(220, 30, 60), anchor="mm")
        self.ring = mv.circle(232, GOLD + (255,))
        self.nums = {k: rtext(str(k), 150, fill=PINK if k == 1 else INK, stroke=0) for k in range(1, n + 1)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self._tags = {}
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (0.12, mv.sfx_whoosh(0.4), 0.6), (0.35, mv.sfx_pop(), 0.6)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        self.sounds += [(self.reveal, mq.sfx_boom(), 0.9), (self.reveal, mv.sfx_ding(), 1.0),
                        (self.reveal + 0.05, mv.sfx_whoosh(0.6), 0.6), (self.reveal + 0.65, mq.sfx_pling(), 0.6),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        for k in range(10):                                         # the areas ticking up
            self.sounds.append((self.reveal + 0.1 + k * 0.07, mv.sfx_click(), 0.35))
        if tts:
            self.voices.append((0.15, v_q))
            self.voices.append((self.reveal + 0.1, v_a))
            if self.cta:
                self.voices.append((self.reveal + self.cta_at, v_c))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = self.reveal + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, mq.sfx_pling(), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        rr = random.Random(idx * 23)
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1300, -500), rr.randint(12, 26),
                      rr.choice([GOLD, COLORS[self.win][0], (255, 255, 255), CYAN]), rr.uniform(0, 3))
                     for _ in range(60)]

    def panel(self, side, t, rv):
        c, R0, rings = self.views[side]
        Rs = R0 * (1 + 0.05 * clamp(t / self.reveal))              # slow push-in while you think
        if rv > 0:
            k = ease_in_out(clamp((rv - 0.05) / 0.6))
            R = math.exp(math.log(Rs) + (math.log(self.Rc) - math.log(Rs)) * k)
        else:
            R = Rs
        G.HILITE, G.HILITE_EDGE, G.HILITE_GLOW = COLORS[side]
        im = self.ui["globe"].render(c, R, (PW / 2, PH / 2), rings, 1.0, lift=10 if rv > 0 else 5, halo=False)
        G.HILITE, G.HILITE_EDGE, G.HILITE_GLOW = COLORS[0]
        art = self.ui["art"]
        im.alpha_composite(art.shade)
        im.alpha_composite(self.labels[side])
        im.alpha_composite(art.edge["gold" if (rv > 0 and side == self.win) else "white"])
        im.putalpha(art.mask)
        return im

    def area_tag(self, side, k):
        v = int(round(self.areas[side] * k / 1000)) * 1000
        key = (side, v)
        if key not in self._tags:
            self._tags[key] = tag(km2(v), GOLD if side == self.win else (230, 230, 240), 56)
        return self._tags[key]

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        on_beat = beat_pulse(T) if t > self.fly else 0.0
        im = self.ui["bg"].render(T, self.col, strobe=on_beat * 0.5 + (1 - clamp(rv / 0.25) if rv > 0 else 0),
                                  rays=0.6)
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(Image.new("RGBA", (W, H), (120, 0, 30, 36)))
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        d = ImageDraw.Draw(im)
        paste_center(im, self.title, W / 2, 190)
        paste_center(im, self.count, 92 + (20 if self.bonus else 0), 262)
        x0, x1, y, bh = 170 + (40 if self.bonus else 0), 1000, 262, 20
        frac = 1.0 if t < self.fly else max(0.0, 1 - (t - self.fly) / (self.reveal - self.fly))
        d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
        colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
        if frac > 0.01:
            d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 10, fill=colr + (255,))
        paste_center(im, self.tagimg, x0 + self.tagimg.width / 2, 318)
        n = self.idx if rv > 0 else self.idx - 1
        if n > 0:
            sc = 1 + 0.5 * (1 - ease_out_cubic(rv / 0.25)) if 0 < rv < 0.25 else 1.0
            stk = self.streak[n]
            paste_center(im, scaled(stk, sc), x1 - stk.width / 2 + 10, 318)
        for side in (0, 1):
            k_in = clamp((t - side * 0.12) / 0.4)
            if k_in <= 0:
                continue
            dx = (1 - ease_out_back(k_in, 1.3)) * (1200 if side == 0 else -1200)
            s = 1 + 0.012 * on_beat if rv < 0 else (
                1 + 0.06 * (1 - ease_out_cubic(clamp(rv / 0.35))) if side == self.win else 0.97)
            cx, cy = W / 2 + dx, PANEL_Y[side]
            p = self.panel(side, t, rv)
            paste_center(im, scaled(p, s), cx, cy)
            if rv > 0.6 and side != self.win:
                paste_center(im, scaled(self.dim, s), cx, cy, clamp((rv - 0.6) / 0.3) * 0.6)
            tx, ty = cx + (PW / 2 - 30) * s, cy - (PH / 2 - 30) * s
            if rv <= 0:
                if t > 0.45:
                    tg = self.hidden
                    paste_center(im, scaled(tg, 1 + 0.05 * on_beat), tx - tg.width / 2, ty + tg.height / 2)
            else:
                k = ease_out_cubic(clamp((rv - 0.1) / 0.9))
                tg = self.area_tag(side, k)
                pop = 1 + 0.25 * (1 - ease_out_cubic(clamp(rv / 0.25)))
                paste_center(im, scaled(tg, pop), tx - tg.width / 2, ty + tg.height / 2)
            if rv > 0.65 and side == self.win:
                kr = ease_out_back(clamp((rv - 0.65) / 0.25), 2.2)
                if kr > 0.01:
                    paste_center(im, scaled(self.ribbon, 1.5 - 0.5 * kr), cx + 300, cy + PH / 2 - 60, min(1.0, kr))
                ks = ease_out_back((rv - 0.7) / 0.25, 2.2)
                if ks > 0.01:
                    paste_center(im, scaled(self.sticker, ks).rotate(14 * math.sin(rv * 7), Image.BICUBIC,
                                                                     expand=True), cx + 400, cy - 60)
        # VS badge with the 3-2-1, then the size gap (or the like call-out)
        cta_on = self.cta and rv > self.cta_at
        if t > 0.35:
            kb = ease_out_back(clamp((t - 0.35) / 0.3), 2.0) * (1 + 0.08 * on_beat)
            fade = 1 - clamp(rv / 0.2) if rv > 0 else 1.0
            if fade > 0.01:
                paste_center(im, scaled(self.ring, kb * (1 + 0.06 * math.sin(T * 6))), W / 2, VS_Y, fade)
                badge = self.badge
                for j, b in enumerate(self.count_beats):
                    tb = t - b * B
                    if 0 <= tb < B:
                        badge = mv.circle(190, (255, 255, 255, 255))
                        paste_center(badge, scaled(self.nums[len(self.count_beats) - j],
                                                   1.25 - 0.25 * ease_out_cubic(tb / 0.12)), 95, 98)
                paste_center(im, scaled(badge, kb), W / 2, VS_Y, fade)
            if 0.12 < rv < 0.9:                                      # both globes now share one scale
                kn = ease_out_back(clamp((rv - 0.12) / 0.2), 1.8) * (1 - clamp((rv - 0.75) / 0.15))
                paste_center(im, scaled(self.scale_note, max(0.01, kn)), W / 2, VS_Y, min(1.0, kn))
            if rv > 0.8 and not cta_on:
                kd = ease_out_back(clamp((rv - 0.8) / 0.3), 1.8)
                paste_center(im, scaled(self.diff, kd * (1 + 0.02 * beat_pulse(T))), W / 2, VS_Y)
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, VS_Y, a)
        if rv > 0:
            cy = PANEL_Y[self.win]
            if rv > 0.65:
                kc = rv - 0.65
                for vx, vy, sz, cc, spin in self.conf:
                    px, py = W / 2 + vx * kc, cy + vy * kc + 2400 * kc * kc
                    if py < H:
                        w2 = sz * abs(math.cos(spin + kc * 9))
                        d = ImageDraw.Draw(im)
                        d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                    outline=INK + (255,))
                kw = (rv - 0.65) / 0.5
                if 0 < kw < 1:                                       # shockwave from the bigger country
                    d = ImageDraw.Draw(im)
                    rr = 200 + 560 * ease_out_cubic(kw)
                    d.ellipse((W / 2 - rr, cy - rr, W / 2 + rr, cy + rr), outline=GOLD + (int(255 * (1 - kw)),),
                              width=max(1, int(24 * (1 - kw))))
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(190 * fl))))
            im = shake(im, 26 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 16 * (1 - rv / 0.18))
            if 0.65 < rv < 0.85:                                     # second punch when the gap is clear
                im = shake(im, 14 * (1 - (rv - 0.65) / 0.2), t)
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
                                                                                     expand=True), W / 2, VS_Y)
        if self.level_up and t < 0.35:
            im = glitch(im, 1 - t / 0.35, int(t * 30) + self.idx * 7)
        if t < 0.16:
            im = rgb_split(mm.zoom_blur(im, 1 - t / 0.16), 18 * (1 - t / 0.16))
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(mm.zoom_blur(im, out), 22 * out)
        return im


class Ending(mv.Scene):
    def __init__(self, ui, intro, tts):
        super().__init__()
        self.ui, self.intro = ui, intro
        self.dur = 10 * B
        logo = Image.open(brand.round_logo()).convert("RGBA").resize((120, 120), Image.LANCZOS)
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
            self.voices.append((0.3, tts.say(END_LINE, speed=1.12)))

    def render(self, t):
        T = self.t0 + t
        im = self.ui["big_globe"].render(G.unit(-60 - 30 * (self.dur - t), 18), 520, (540, 1220))
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        a = 1 - out
        im.alpha_composite(Image.new("RGBA", (W, H), INK + (int(160 * clamp((t - 0.2) / 0.3) * a),)))
        paste_center(im, self.brand, W / 2, 300, clamp((t - B) / 0.2) * a)
        paste_center(im, scaled(self.title, ease_out_back((t - B) / 0.25) * (1 + 0.03 * beat_pulse(T))), W / 2, 460,
                     a)
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
    world = G.World()
    ui = {"bg": GeoWall(), "vig": [mc.red_vignette(i / 10) for i in range(11)], "art": PanelArt(),
          "globe": G.GlobeRenderer(PW, PH, world), "big_globe": G.GlobeRenderer(W, H, world)}
    intro = Intro(ui, tts)
    scenes, prev = [intro], ROUNDS[0][2]
    for i, r in enumerate(ROUNDS, 1):
        scenes.append(Round(i, r, prev, ui, tts))
        prev = r[2]
    scenes.append(Ending(ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    im = ui["bg"].render(1.0, CYAN, rays=0.8)
    r = Round(4, ROUNDS[3], "EASY", ui, None)
    for side in (0, 1):
        paste_center(im, r.panel(side, 0.5 * r.reveal, -1.0), W / 2, (980, 1610)[side])
        tg = r.hidden
        paste_center(im, tg, W / 2 + PW / 2 - 30 - tg.width / 2, (980, 1610)[side] - PH / 2 + 30 + tg.height / 2)
    paste_center(im, mv.circle(232, GOLD + (255,)), W / 2, 1295)
    paste_center(im, r.badge, W / 2, 1295)
    paste_center(im, rtext("WHICH COUNTRY", 124, stroke=11).rotate(-3, Image.BICUBIC, expand=True), W / 2, 250)
    paste_center(im, join(rtext("IS BIGGER?", 150, fill=GOLD, stroke=13), emoji("🌍", 128), gap=14).rotate(
        2, Image.BICUBIC, expand=True), W / 2, 430)
    paste_center(im, join(rtext("99% GET IT WRONG", 72, fill=PINK, stroke=7), emoji("💀", 76)), W / 2, 590)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_bigger_country_quiz.mp4"))
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
        make_cover(ui, os.path.join(HERE, "bigger_country_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"bigger_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_bigger")
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
