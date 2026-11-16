#!/usr/bin/env python3
""""HIGHER OR LOWER? Population edition" Short (1080x1920), part 3 formula with the full effects pack.

The classic chain game: the top country's population is shown, the bottom one is hidden. Does it have
MORE (higher) or FEWER (lower) people? A 3-2-1 runs inside the VS badge between the HIGHER and LOWER
buttons. On the drop the right button flies to the middle with a sunburst and shockwaves, the wrong one
falls off, and the hidden number counts up; the country with more people gets a gold frame and a crown,
then the gap pops up ("3.1x MORE PEOPLE" / "6 MILLION MORE"). Next round the bottom country slides up
to become the new top one. Hook intro (cold open on the bonus, montage, title slams over a colour-lit
globe), EASY -> IMPOSSIBLE plus a bonus, one like call-out after round 3, looping score screen.

Populations: UN World Population Prospects 2024, 2025 estimates, rounded on screen.
Borders: Natural Earth (public domain). Flags: public domain (RU and BD drawn from their official specs).

    python3 make_higher_lower_quiz.py
    python3 make_higher_lower_quiz.py --stills 0,5,9
    python3 make_higher_lower_quiz.py --cover
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
import make_logo_quiz as lq  # noqa: E402
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
PW, PH = bq.PW, bq.PH
PANEL_Y = bq.PANEL_Y
VS_Y = bq.VS_Y
TIERS = mc.TIERS
ENTRY_BEATS = 2
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
GREEN = (46, 204, 113)
RED = (235, 60, 75)
BTN_X = (200, 880)                   # HIGHER on the left, LOWER on the right of the VS badge

POP = {  # map code: name on screen, spoken name, people in millions (UN WPP 2024, 2025), flag file
    "USA": ("USA", "the USA", 347.3, "US"),
    "GBR": ("UNITED KINGDOM", "the UK", 69.6, "GB"),
    "BRA": ("BRAZIL", "Brazil", 212.8, "BR"),
    "CAN": ("CANADA", "Canada", 40.1, "CA"),
    "DEU": ("GERMANY", "Germany", 84.1, "DE"),
    "EGY": ("EGYPT", "Egypt", 118.4, "EG"),
    "VNM": ("VIETNAM", "Vietnam", 101.6, "VN"),
    "PHL": ("PHILIPPINES", "the Philippines", 116.8, "PH"),
    "JPN": ("JAPAN", "Japan", 123.1, "JP"),
    "BGD": ("BANGLADESH", "Bangladesh", 175.7, "BD"),
    "RUS": ("RUSSIA", "Russia", 144.0, "RU"),
    "CHN": ("CHINA", "China", 1416.1, "CN"),
    "IND": ("INDIA", "India", 1463.9, "IN"),
}
ROUNDS = [  # A (shown, top), B (hidden, bottom), tier, spoken question, reaction sticker
    ("USA", "GBR", "EASY", "Does the UK have more people than the USA? Higher, or lower?", "😎"),
    ("GBR", "BRA", "EASY", "Brazil! Higher, or lower?", "🔥"),
    ("BRA", "CAN", "EASY", "Canada! Higher, or lower?", "🤔"),
    ("CAN", "DEU", "MEDIUM", "Germany! Higher, or lower?", "😳"),
    ("DEU", "EGY", "MEDIUM", "Egypt! Higher, or lower?", "🤯"),
    ("EGY", "VNM", "MEDIUM", "Vietnam! Higher, or lower?", "🔥"),
    ("VNM", "PHL", "HARD", "The Philippines! Higher, or lower?", "😱"),
    ("PHL", "JPN", "HARD", "Japan! Higher, or lower?", "💀"),
    ("JPN", "BGD", "INSANE", "Bangladesh! Higher, or lower?", "🧠"),
    ("BGD", "RUS", "IMPOSSIBLE", "Russia! Higher, or lower?", "☠"),
    ("CHN", "IND", "BONUS", "Bonus! Does India have more people than China?", "👑"),
]
MAIN_ONLY = {"USA"}                  # frame and fill only the main landmass (not Alaska and Hawaii)
INTRO_LINE = "Only one percent get them all!"


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


def millions(code):
    return POP[code][2]


def shown(m):
    """The number as it is written on screen (rounded)."""
    return f"{m / 1000:.2f} BILLION" if m >= 1000 else f"{int(round(m))} MILLION"


def spoken(m):
    return f"{m / 1000:.2f} billion" if m >= 1000 else f"{int(round(m))} million"


def gap_text(a, b):
    """How B compares with A, from the rounded numbers people see."""
    ra, rb = (a, b) if a >= 1000 else (round(a), round(b))
    more = rb > ra
    ratio = max(ra, rb) / min(ra, rb)
    if ratio >= 1.3:
        return f"{ratio:.1f}x {'MORE' if more else 'FEWER'} PEOPLE"
    return f"{abs(rb - ra):.0f} MILLION {'MORE' if more else 'FEWER'}"


def view_for(world, code, fx=0.4, fy=0.36):
    ci = world.codes.index(code)
    idx = np.nonzero(world.owner == ci)[0]
    big = max(world.lens[i] for i in idx)
    if code in MAIN_ONLY:
        main = [i for i in idx if world.lens[i] == big]
        idx = np.array(main)
    else:
        main = [i for i in idx if world.lens[i] >= 0.05 * big]
    pts = np.concatenate([world.P[world.starts[i]:world.starts[i] + world.lens[i]] for i in main])
    c = pts.mean(0)
    c /= np.linalg.norm(c)
    east, up, view = G.frame_axes(c)
    sx, sy = np.abs(pts @ east).max(), np.abs(pts @ up).max()
    R = float(np.clip(min(fx * PW / max(sx, 1e-3), fy * PH / max(sy, 1e-3)), 300, 14000))
    return c, R, idx


def pop_tag(text, col, size=56):
    body = join(emoji("👥", int(size * 0.9)), rtext(text, size, fill=col, stroke=6), gap=10)
    card = rounded_card(body.width + 50, body.height + 22, (body.height + 22) // 2, (12, 10, 30, 235),
                        outline=col + (255,), width=5)
    paste_center(card, body, card.width / 2, card.height / 2)
    return card


def button(label, col, up, check=False):
    t = rtext(label, 54, stroke=6)
    extra = 74 if check else 0
    w, h = t.width + 124 + extra, 112
    card = rounded_card(w, h, h // 2, col + (255,), outline=(255, 255, 255, 255), width=6)
    d = ImageDraw.Draw(card)
    cx, cy, s = 56, h / 2, 22
    pts = ([(cx, cy - s), (cx - s, cy + s * 0.8), (cx + s, cy + s * 0.8)] if up else
           [(cx, cy + s), (cx - s, cy - s * 0.8), (cx + s, cy - s * 0.8)])
    d.polygon(pts, fill=INK + (255,))
    d.polygon([(x + (0 if up else 0), y + (-3 if up else 3)) for x, y in pts], fill=(255, 255, 255, 255))
    card.alpha_composite(t, (92, (h - t.height) // 2))
    if check:
        paste_center(card, emoji("✅", 60), w - 56, h / 2)
    return card


def ring(im, x, y, r, col, a, width=8, squash=1.0):
    if a > 2:
        ImageDraw.Draw(im, "RGBA").ellipse((x - r, y - r * squash, x + r, y + r * squash), outline=col + (int(a),),
                                           width=width)


class HLWall(lq.BrandWall):
    EMOJIS = ["👥", "🌍", "📈", "📉", "🏙", "👶", "🗺", "🌎"]


class Panels:
    """Globe panel per country: zoomed so it fills the panel, filled with its flag, name in the corner."""

    def __init__(self, ui):
        self.ui, self.cache = ui, {}

    def get(self, code):
        if code not in self.cache:
            c, R, idx = view_for(self.ui["globe"].world, code)
            flag = Image.open(os.path.join(FLAG_DIR, POP[code][3] + ".png")).convert("RGBA")
            name = POP[code][0]
            size = 66
            while rfont(size).getlength(name) > PW - 140 and size > 40:
                size -= 2
            label = Image.new("RGBA", (PW, PH))
            t = rtext(name, size, stroke=6)
            label.alpha_composite(t, (40, PH - t.height - 24))
            self.cache[code] = (c, R, idx, flag, label)
        return self.cache[code]

    def render(self, code, side, push=1.0, gold=False, lift=5):
        c, R, idx, flag, label = self.get(code)
        G.HILITE, G.HILITE_EDGE, G.HILITE_GLOW = bq.COLORS[side]
        im = self.ui["globe"].render(c, R * push, (PW / 2, PH / 2), idx, 1.0, flag, 1.0, lift=lift, halo=False)
        G.HILITE, G.HILITE_EDGE, G.HILITE_GLOW = bq.COLORS[0]
        art = self.ui["art"]
        im.alpha_composite(art.shade)
        im.alpha_composite(label)
        im.alpha_composite(art.edge["gold" if gold else "white"])
        im.putalpha(art.mask)
        return im


class UI:
    """Static pieces shared by every scene."""

    def __init__(self, ui):
        self.tags = {}
        self.up = button("HIGHER", GREEN, True)
        self.down = button("LOWER", RED, False)
        self.up_ok = button("HIGHER", GREEN, True, True)
        self.down_ok = button("LOWER", GREEN, False, True)
        self.up_no = button("HIGHER", (110, 110, 130), True)
        self.down_no = button("LOWER", (110, 110, 130), False)
        self.badge = mv.circle(190, (255, 255, 255, 255))
        ImageDraw.Draw(self.badge).text((95, 98), "VS", font=rfont(84), fill=(220, 30, 60), anchor="mm")
        self.ring = mv.circle(232, GOLD + (255,))
        self.title = join(rtext("HIGHER OR LOWER?", 54, stroke=6), emoji("👥", 54), gap=10)
        rb = join(rtext("MORE PEOPLE", 50, fill=INK, stroke=0), emoji("👑", 52), gap=10)
        rib = rounded_card(rb.width + 46, rb.height + 22, 24, GOLD + (255,), outline=INK + (255,), width=5)
        paste_center(rib, rb, rib.width / 2, rib.height / 2)
        self.ribbon = rib.rotate(-6, Image.BICUBIC, expand=True)

    def tag(self, text, col):
        key = (text, col)
        if key not in self.tags:
            self.tags[key] = pop_tag(text, col)
        return self.tags[key]


def draw_pair(im, ui, a, b, T, known_b=None):
    """The two panels in their resting place (intro and cover)."""
    for side, code in enumerate((a, b)):
        p = ui["panels"].render(code, side)
        paste_center(im, p, W / 2, PANEL_Y[side])
        tg = ui["ui"].tag(shown(millions(code)) if side == 0 or known_b else "? " + shown(millions(code)).split()[1],
                          GOLD if side == 0 else (255, 255, 255))
        paste_center(im, tg, W / 2 + PW / 2 - 30 - tg.width / 2, PANEL_Y[side] - PH / 2 + 30 + tg.height / 2)


def draw_vs(im, ui, T, s=1.0, a=1.0):
    u = ui["ui"]
    paste_center(im, scaled(u.ring, s * (1 + 0.06 * math.sin(T * 6))), W / 2, VS_Y, a)
    paste_center(im, scaled(u.badge, s), W / 2, VS_Y, a)
    paste_center(im, scaled(u.up, s * (1 + 0.04 * beat_pulse(T))), BTN_X[0], VS_Y, a)
    paste_center(im, scaled(u.down, s * (1 + 0.04 * beat_pulse(T + 0.2))), BTN_X[1], VS_Y, a)


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    TEASE, MONTAGE = 10, (9, 8, 6, 7)

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 6 * B
        self.t1, self.t2 = 1.5 * B, 3.5 * B
        self.o1 = fit(join(rtext("ONLY 1% GET 10/10", 92, fill=PINK, stroke=10), emoji("😳", 88), gap=10), 960)
        self.o3 = join(rtext("answer at the end", 60, fill=GOLD, stroke=7), emoji("👀", 64))
        self.m1 = fit(join(rtext("CAN YOU GET", 96, stroke=10), emoji("🤔", 90), gap=10), 960)
        self.m2 = fit(rtext("ALL 10 RIGHT?", 104, fill=CYAN, stroke=10), 960)
        self.l1 = fit(join(rtext("HIGHER", 150, fill=GREEN, stroke=13), emoji("📈", 130), gap=14), 960)
        self.l2 = fit(join(rtext("OR LOWER?", 140, fill=RED, stroke=13), emoji("📉", 120), gap=14), 960)
        self.l3 = fit(join(rtext("POPULATION EDITION", 74, fill=GOLD, stroke=8), emoji("👥", 72), gap=10), 960)
        self.l4 = join(rtext("99% FAIL", 110, fill=(255, 255, 255), stroke=11), emoji("💀", 110))
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9),
                        (0.02, mq.sfx_glitch(), 0.5), (B, sfx_heartbeat(), 0.8), (B, mq.sfx_boom(), 0.5),
                        (self.t2, mq.sfx_boom(), 0.9), (self.t2, mv.sfx_whoosh(0.5), 0.6),
                        (4.5 * B, mv.sfx_riser(1.5 * B), 0.7), (6 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k in range(len(self.MONTAGE)):
            at = self.t1 + k * 0.5 * B
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mq.sfx_glitch(), 0.35), (at, mv.sfx_click(), 0.7)]
        for k in range(4):
            self.sounds += [(self.t2 + k * 0.5 * B, mv.sfx_pop(), 0.8), (self.t2 + k * 0.5 * B, mq.sfx_boom(), 0.5)]
        if tts:
            self.voices.append((0.04, tts.say(INTRO_LINE, speed=1.15)))

    def render(self, t):
        T = self.t0 + t
        if t < self.t1:                                      # cold open: the bonus question, readable on frame one
            im = self.ui["bg"].render(T, GOLD, strobe=0.3 * beat_pulse(T), rays=0.6)
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.5 * beat_pulse(T)))])
            r = ROUNDS[self.TEASE]
            draw_pair(im, self.ui, r[0], r[1], T)
            draw_vs(im, self.ui, T)
            s = 1 + 0.06 * (1 - ease_out_cubic(t / 0.2))
            paste_center(im, scaled(self.o1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 210)
            paste_center(im, self.o3, W / 2, 1720)
            im = shake(im, 26 * (1 - t / 0.3) if t < 0.3 else 0, t)
            return rgb_split(im, 8 * (1 - clamp(t / 0.25)))
        if t < self.t2:                                      # rapid montage of match-ups
            k = min(len(self.MONTAGE) - 1, int((t - self.t1) / (0.5 * B)))
            tc = t - self.t1 - k * 0.5 * B
            r = ROUNDS[self.MONTAGE[k]]
            im = self.ui["bg"].render(T, TIERS[r[2]][0], strobe=1 - clamp(tc / 0.15), rays=0.8)
            draw_pair(im, self.ui, r[0], r[1], T)
            draw_vs(im, self.ui, T)
            s = 1 + 0.12 * (1 - ease_out_cubic((t - self.t1) / 0.15))
            paste_center(im, scaled(self.m1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 170)
            paste_center(im, scaled(self.m2, s).rotate(2, Image.BICUBIC, expand=True), W / 2, 285)
            im = rgb_split(im, 18 * (1 - clamp(tc / 0.12)))
            im = mm.zoom_blur(im, 0.6 * (1 - clamp(tc / 0.1)))
            if tc < 0.06:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            return im
        tg = t - self.t2                                     # titles over a spinning, colour-lit globe
        gc = (540, 1270)
        R = 470 * (1 + 0.05 * beat_pulse(T)) * (1.25 - 0.25 * ease_out_cubic(clamp(tg / 0.3)))
        c = G.unit(30 + 50 * tg, 20)
        im = self.ui["big_globe"].render(c, R, gc)
        self.ui["cmap"].draw(im, c, R, gc, None, 0.75 + 0.2 * beat_pulse(T))
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 40)))
        b = int(tg / (0.5 * B))
        kk = (tg % (0.5 * B)) / (0.5 * B)
        slam = 1 + 0.35 * (1 - ease_out_cubic(kk / 0.4))
        lines = [(self.l1, 300, -3), (self.l2, 470, 2), (self.l3, 625, -2), (self.l4, 760, 0)]
        for j, (img, y, rot) in enumerate(lines):
            if b >= j:
                sc = (slam if b == j else 1.0) * (1 + 0.03 * beat_pulse(T))
                paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
        im = shake(im, 22 * (1 - kk) if kk < 0.4 and b <= 3 else 0, t)
        if tg < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(160 * (1 - tg / 0.08)))))
        whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Round(mv.Scene):
    def __init__(self, idx, r, prev, prev_tier, ui, tts):
        super().__init__()
        ka, kb, tier, question, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.codes = (ka, kb)
        self.pops = (millions(ka), millions(kb))
        self.higher = self.pops[1] > self.pops[0]
        self.right = 0 if self.higher else 1                 # which button is right
        self.more = 1 if self.higher else 0                  # which panel has more people
        self.chained = prev is not None and prev[1] == ka
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = ENTRY_BEATS
        said = f"{'Higher' if self.higher else 'Lower'}! {spoken(self.pops[1])}!"
        v_q = tts.say(question, speed=1.1) if tts else None
        v_a = tts.say(said, speed=1.12) if tts else None
        v_c = tts.say(CTA_LINE, speed=1.1) if (tts and self.cta) else None
        q_len = len(v_q) / SR if v_q is not None else 2.0
        a_len = len(v_a) / SR if v_a is not None else 1.3
        c_len = len(v_c) / SR if v_c is not None else 2.8
        c0 = max(f + 3, math.ceil((0.15 + q_len + 0.2) / B))
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.fly = f * B
        self.reveal = (c0 + n) * B
        self.done = 0.95                                     # the hidden number has finished counting up
        self.gap_at = 1.3
        hold = max(5, math.ceil((self.gap_at + 1.0) / B), math.ceil((0.1 + a_len + 0.5) / B))
        self.cta_at = max(5 * B, 0.1 + a_len + 0.3)
        if self.cta:
            hold = max(hold, math.ceil((self.cta_at + c_len + 0.5) / B))
        self.dur = (c0 + n + hold) * B
        self.col, e = TIERS[tier]
        self.count = rtext("BONUS" if self.bonus else f"{idx}/10", 46, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        self.tagimg = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, self.col + (255,),
                                   outline=INK + (255,), width=3)
        ImageDraw.Draw(self.tagimg).text((self.tagimg.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.level_up = tier != prev_tier and idx > 1
        self.banner = None
        if self.level_up:
            label = "BONUS: ONLY 1% KNOW THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 62 if self.bonus else 92, fill=self.col, stroke=9), emoji(e, 90))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        self.nums = {k: rtext(str(k), 150, fill=PINK if k == 1 else INK, stroke=0) for k in range(1, n + 1)}
        self.badges = {}
        for k, num in self.nums.items():
            bd = mv.circle(190, (255, 255, 255, 255))
            paste_center(bd, num, 95, 98)
            self.badges[k] = bd
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        gp = join(emoji("📊", 50), rtext(gap_text(*self.pops), 54, fill=(90, 230, 140), stroke=6), gap=12)
        self.gap = rounded_card(gp.width + 56, gp.height + 26, (gp.height + 26) // 2, (12, 10, 30, 240),
                                outline=(90, 230, 140, 255), width=5)
        paste_center(self.gap, gp, self.gap.width / 2, self.gap.height / 2)
        self.unit = shown(self.pops[1]).split()[1]
        self.dim = Image.new("RGBA", (PW, PH), (4, 0, 16, 150))
        self.dim.putalpha(Image.fromarray((np.asarray(ui["art"].mask).astype(np.float32) * 150 / 255).astype(np.uint8)))
        self.sticker = emoji(stick, 140)
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (0.12, mv.sfx_whoosh(0.4), 0.6), (0.4, mv.sfx_pop(), 0.6),
                        (0.45, mv.sfx_click(), 0.6)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        if self.danger:
            self.sounds.append((self.count_beats[-1] * B, mq.sfx_boom(), 0.6))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        rv0 = self.reveal
        self.sounds += [(rv0, mq.sfx_boom(), 0.9), (rv0, mv.sfx_ding(), 1.0), (rv0 + 0.02, mq.sfx_glitch(), 0.4),
                        (rv0 + 0.25, mv.sfx_whoosh(0.35), 0.5), (rv0 + self.done, mq.sfx_pling(), 0.7),
                        (rv0 + self.done, mq.sfx_boom(), 0.5), (rv0 + self.done + 0.1, mv.sfx_pop(), 0.7),
                        (rv0 + self.gap_at, mv.sfx_pop(), 0.8), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        for k in range(13):                                         # the hidden number ticking up
            self.sounds.append((rv0 + 0.08 + k * 0.065, mv.sfx_click(), 0.35))
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
                      rr.choice([GOLD, GREEN, (255, 255, 255), CYAN, PINK]), rr.uniform(0, 3)) for _ in range(70)]

    def panel_pos(self, side, t):
        """Where a panel is during the entry: chained rounds slide the old bottom country up to the top."""
        if self.chained and side == 0:
            k = ease_in_out(clamp(t / 0.45))
            return W / 2, PANEL_Y[1] + (PANEL_Y[0] - PANEL_Y[1]) * k, 1.0 - 0.06 * math.sin(math.pi * k)
        if self.chained:
            k = clamp((t - 0.12) / 0.45)
            return W / 2, PANEL_Y[1] + (1 - ease_out_back(k, 1.2)) * 1100, 1.0
        k = clamp((t - side * 0.12) / 0.4)
        return W / 2 + (1 - ease_out_back(k, 1.3)) * (1200 if side == 0 else -1200), PANEL_Y[side], 1.0

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        on_beat = beat_pulse(T) if t > self.fly else 0.0
        u = self.ui["ui"]
        im = self.ui["bg"].render(T, self.col, strobe=on_beat * 0.5 + (1 - clamp(rv / 0.25) if rv > 0 else 0),
                                  rays=0.6)
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(Image.new("RGBA", (W, H), (120, 0, 30, 36)))
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        d = ImageDraw.Draw(im)
        paste_center(im, u.title, W / 2, 190)
        paste_center(im, self.count, 92 + (20 if self.bonus else 0), 262)
        x0, x1, y, bh = 170 + (40 if self.bonus else 0), 1000, 262, 20
        frac = 1.0 if t < self.fly else max(0.0, 1 - (t - self.fly) / (self.reveal - self.fly))
        d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
        colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
        if frac > 0.01:
            d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 10, fill=colr + (255,))
        paste_center(im, self.tagimg, x0 + self.tagimg.width / 2, 318)
        nk = self.idx if rv > 0 else self.idx - 1
        if nk > 0:
            sc = 1 + 0.5 * (1 - ease_out_cubic(rv / 0.25)) if 0 < rv < 0.25 else 1.0
            stk = self.streak[nk]
            paste_center(im, scaled(stk, sc), x1 - stk.width / 2 + 10, 318)
        punch = 0.0
        if rv < 0:                                           # punch on every count beat
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.22:
                    punch = (0.05 if self.danger else 0.035) * (1 - ease_out_cubic(tb / 0.22))
        # the two panels
        for side in (0, 1):
            cx, cy, s = self.panel_pos(side, t)
            if cy > H + PH / 2:
                continue
            push = 1 + 0.06 * clamp(t / self.reveal) if side == 1 else 1.0
            if rv >= 0:
                s *= 1 + 0.06 * (1 - ease_out_cubic(clamp((rv - self.done) / 0.35))) \
                    if side == self.more and rv > self.done else (0.97 if rv > self.done else 1.0)
            else:
                s *= 1 + 0.012 * on_beat + punch
            gold = rv > self.done and side == self.more
            p = self.ui["panels"].render(self.codes[side], side, push, gold, 10 if gold else 5)
            paste_center(im, scaled(p, s), cx, cy)
            if rv > self.done + 0.1 and side != self.more:
                paste_center(im, scaled(self.dim, s), cx, cy, clamp((rv - self.done - 0.1) / 0.3) * 0.6)
            tx, ty = cx + (PW / 2 - 30) * s, cy - (PH / 2 - 30) * s
            if side == 0:
                tg = u.tag(shown(self.pops[0]), GOLD if (rv > self.done and self.more == 0) or rv <= self.done
                           else (230, 230, 240))
                if not self.chained and t < 0.3:
                    continue
                paste_center(im, tg, tx - tg.width / 2, ty + tg.height / 2)
            elif t > 0.45:
                if rv <= 0:
                    tg = u.tag("? " + self.unit, (255, 255, 255))
                    sc = 1 + 0.05 * on_beat
                else:
                    k = ease_out_cubic(clamp((rv - 0.05) / (self.done - 0.05)))
                    v = self.pops[1] * k
                    txt = f"{v / 1000:.2f} BILLION" if self.pops[1] >= 1000 else f"{int(round(v))} MILLION"
                    col = (GOLD if self.more == 1 else (230, 230, 240)) if rv > self.done else (255, 255, 255)
                    tg = u.tag(txt, col)
                    sc = 1 + 0.25 * (1 - ease_out_cubic(clamp((rv - self.done) / 0.25))) if rv > self.done else 1.08
                paste_center(im, scaled(tg, sc), tx - tg.width / 2 * sc, ty + tg.height / 2 * sc)
            if rv > self.done and side == self.more:
                kr = ease_out_back(clamp((rv - self.done) / 0.25), 2.2)
                if kr > 0.01:
                    rx, ry = (cx - 290, cy - PH / 2 + 62) if side == 0 else (cx + 300, cy + PH / 2 - 60)
                    paste_center(im, scaled(u.ribbon, 1.5 - 0.5 * kr), rx, ry, min(1.0, kr))
            if rv > self.done + 0.05 and side == 1:
                ks = ease_out_back((rv - self.done - 0.05) / 0.25, 2.2)
                if ks > 0.01:
                    paste_center(im, scaled(self.sticker, ks).rotate(14 * math.sin(rv * 7), Image.BICUBIC,
                                                                     expand=True), cx + 410, cy - 70)
        # VS badge with the 3-2-1 between the HIGHER and LOWER buttons
        cta_on = self.cta and rv > self.cta_at
        if t > 0.35:
            kb = ease_out_back(clamp((t - 0.35) / 0.3), 2.0)
            fade = 1 - clamp(rv / 0.2) if rv > 0 else 1.0
            if fade > 0.01:
                badge = u.badge
                for j, b in enumerate(self.count_beats):
                    tb = t - b * B
                    if 0 <= tb < B:
                        badge = scaled(self.badges[len(self.count_beats) - j], 1.0 + 0.15 * (1 - ease_out_cubic(tb / 0.12)))
                paste_center(im, scaled(u.ring, kb * (1 + 0.06 * math.sin(T * 6)) * (1 + 0.08 * on_beat)), W / 2, VS_Y,
                             fade)
                paste_center(im, scaled(badge, kb * (1 + 0.08 * on_beat)), W / 2, VS_Y, fade)
            for side, (img, x) in enumerate(((u.up, BTN_X[0]), (u.down, BTN_X[1]))):
                kin = ease_out_back(clamp((t - 0.4 - 0.08 * side) / 0.3), 2.0)
                if kin <= 0.01:
                    continue
                if rv <= 0:
                    s = kin * (1 + 0.04 * beat_pulse(T + 0.2 * side))
                    for j, b in enumerate(self.count_beats):  # the buttons take turns to bounce on the beats
                        tb = t - b * B
                        if 0 <= tb < 0.3 and j % 2 == side:
                            s *= 1 + 0.14 * (1 - ease_out_cubic(tb / 0.3))
                    paste_center(im, scaled(img, s), x, VS_Y + 4 * math.sin(T * 5 + side * 2))
                elif side == self.right:
                    if cta_on or rv > self.gap_at:
                        continue
                    k = ease_out_cubic(clamp(rv / 0.3))
                    px = x + (W / 2 - x) * k
                    ok = u.up_ok if side == 0 else u.down_ok
                    s = 1 + 0.35 * ease_out_back(clamp(rv / 0.3), 2.0) + 0.04 * beat_pulse(T)
                    out = clamp((rv - (self.gap_at - 0.12)) / 0.12)
                    bs = self.ui["burst"].rotate(rv * 60, Image.BICUBIC)
                    paste_center(im, scaled(bs, min(1.3, 0.6 + k)), px, VS_Y, 0.9 * (1 - out))
                    for j in range(3):                       # green shockwaves
                        tl = rv - 0.1 * j
                        if 0 < tl < 0.55:
                            ring(im, px, VS_Y, 120 + 380 * ease_out_cubic(tl / 0.55), GREEN, 255 * (1 - tl / 0.55), 10)
                    paste_center(im, scaled(ok, s * (1 - 0.4 * out)), px, VS_Y, 1 - out)
                else:                                        # the wrong button shakes, then falls off
                    no = u.up_no if side == 0 else u.down_no
                    if rv < 0.25:
                        paste_center(im, no, x + 14 * math.sin(rv * 70), VS_Y)
                    else:
                        tf = rv - 0.25
                        a = 1 - clamp((tf - 0.05) / 0.5)
                        if a > 0.01:
                            sp = no.rotate((1 if side else -1) * 200 * tf, Image.BICUBIC, expand=True)
                            paste_center(im, sp, x + (1 if side else -1) * 200 * tf, VS_Y + 2600 * tf * tf, a)
            if rv > self.gap_at and not cta_on:
                kd = ease_out_back(clamp((rv - self.gap_at) / 0.3), 1.8)
                paste_center(im, scaled(self.gap, kd * (1 + 0.02 * beat_pulse(T))), W / 2, VS_Y)
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, VS_Y, a)
        if rv > 0:
            cy = PANEL_Y[self.more]
            if rv > self.done:
                kc = rv - self.done
                for vx, vy, sz, cc, spin in self.conf:
                    px, py = W / 2 + vx * kc, cy + vy * kc + 2400 * kc * kc
                    if py < H:
                        w2 = sz * abs(math.cos(spin + kc * 9))
                        d = ImageDraw.Draw(im)
                        d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                    outline=INK + (255,))
                kw = kc / 0.5
                if kw < 1:                                   # gold shockwave from the country with more people
                    ring(im, W / 2, cy, 200 + 560 * ease_out_cubic(kw), GOLD, 255 * (1 - kw), max(1, int(24 * (1 - kw))))
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(190 * fl))))
            im = shake(im, 26 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 16 * (1 - rv / 0.18))
            if self.done < rv < self.done + 0.2:            # second punch when the number lands
                im = shake(im, 16 * (1 - (rv - self.done) / 0.2), t)
                im = rgb_split(im, 8 * (1 - (rv - self.done) / 0.2))
        else:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 14 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 10 * (1 - tb / 0.15))
            tb = t - self.count_beats[-1] * B
            if self.danger and 0 <= tb < 0.2:                # red flash on the last count
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
                                                                                     expand=True), W / 2, VS_Y)
        if self.level_up and t < 0.35:
            im = glitch(im, 1 - t / 0.35, int(t * 30) + self.idx * 7)
        if t < 0.16:
            im = rgb_split(mm.zoom_blur(im, 0.7 * (1 - t / 0.16)), 18 * (1 - t / 0.16))
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(im, 22 * out)
        return im


def build(voice="am_adam", voice_pack=None):
    if voice_pack:
        tts = cq.Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    world = G.World()
    ui = {"bg": HLWall(), "vig": [mc.red_vignette(i / 10) for i in range(11)], "art": bq.PanelArt(),
          "globe": G.GlobeRenderer(PW, PH, world), "big_globe": G.GlobeRenderer(W, H, world),
          "cmap": mcq.ColourMap(world), "burst": mq.sunburst(560, GREEN)}
    ui["panels"] = Panels(ui)
    ui["ui"] = UI(ui)
    intro = Intro(ui, tts)
    scenes, prev, prev_tier = [intro], None, ROUNDS[0][2]
    for i, r in enumerate(ROUNDS, 1):
        scenes.append(Round(i, r, prev, prev_tier, ui, tts))
        prev, prev_tier = r, r[2]
    scenes.append(bq.Ending(ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    r = ROUNDS[9]                                            # Bangladesh vs Russia: the one nobody believes
    im = ui["bg"].render(1.0, TIERS[r[2]][0], strobe=0.3, rays=0.8)
    draw_pair(im, ui, r[0], r[1], 0.0)
    draw_vs(im, ui, 0.0)
    paste_center(im, fit(join(rtext("HIGHER OR LOWER?", 104, fill=GOLD, stroke=10), emoji("👥", 100), gap=10), 980)
                 .rotate(-3, Image.BICUBIC, expand=True), W / 2, 200)
    paste_center(im, join(rtext("99% FAIL", 100, fill=PINK, stroke=10), emoji("💀", 100)), W / 2, 1745)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_higher_lower_quiz.mp4"))
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
        make_cover(ui, os.path.join(HERE, "higher_lower_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"hl_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_higher_lower")
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
