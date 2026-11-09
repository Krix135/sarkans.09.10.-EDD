#!/usr/bin/env python3
""""WHICH CAR COSTS MORE?" Short (1080x1920), edited like the crazy quizzes.

Two real car photos per round (top and bottom card, VS badge in the middle). The narrator names
both cars, a 3-2-1 runs inside the VS badge on the beat, then both price tags count up, the pricier
car gets a gold frame and a MORE EXPENSIVE ribbon and the other dims. EASY -> HARD -> INSANE ->
IMPOSSIBLE, plus a bonus. Prices are approximate US starting prices (rounded); photos are from
Wikimedia Commons under free licences (credits in car_photos_credits.json and the description).

    python3 make_car_price_quiz.py --voice-pack voice_packs/carprice_adam,voice_packs/map3_adam
    python3 make_car_price_quiz.py --stills 1,5,8
    python3 make_car_price_quiz.py --cover
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
import make_club_quiz as cq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center, rounded_card, \
    scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
PHOTO_DIR = os.path.join(HERE, "car_photos")
CARD_W, CARD_H = 1000, 590
CARD_Y = (640, 1320)
VS_Y = 980
TIERS = mc.TIERS
ENTRY_BEATS = 2

# car: photo key, name on the card, approx. US starting price (USD)
CARS = {
    "corolla": ("Toyota Corolla", 23_000), "gclass": ("Mercedes G-Class", 148_000),
    "urus": ("Lamborghini Urus", 250_000), "mustang": ("Ford Mustang", 32_000),
    "modely": ("Tesla Model Y", 45_000), "landcruiser": ("Toyota Land Cruiser", 57_000),
    "rangerover": ("Range Rover", 108_000), "corvette": ("Chevrolet Corvette", 70_000),
    "p911": ("Porsche 911", 122_000), "cybertruck": ("Tesla Cybertruck", 80_000),
    "cullinan": ("Rolls-Royce Cullinan", 400_000), "revuelto": ("Lamborghini Revuelto", 600_000),
    "sf90": ("Ferrari SF90", 530_000), "valkyrie": ("Aston Martin Valkyrie", 3_000_000),
    "chiron_ss": ("Bugatti Chiron Super Sport", 3_900_000), "jesko": ("Koenigsegg Jesko", 3_000_000),
    "voiture_noire": ("Bugatti La Voiture Noire", 18_700_000), "boat_tail": ("Rolls-Royce Boat Tail", 28_000_000),
}
ROUNDS = [  # car A (top), car B (bottom), tier, spoken question, spoken answer, reaction sticker
    ("corolla", "gclass", "EASY", "Toyota Corolla, or Mercedes G-Class?", "The G-Class!", "😎"),
    ("urus", "mustang", "EASY", "Lamborghini Urus, or Ford Mustang?", "The Urus!", "🔥"),
    ("modely", "landcruiser", "MEDIUM", "Tesla Model Y, or Toyota Land Cruiser?", "The Land Cruiser!", "🤯"),
    ("rangerover", "corvette", "MEDIUM", "Range Rover, or Chevy Corvette?", "The Range Rover!", "😳"),
    ("p911", "cybertruck", "HARD", "Porsche 911, or Tesla Cybertruck?", "The 911!", "🔥"),
    ("cullinan", "revuelto", "HARD", "Rolls-Royce Cullinan, or Lamborghini Revuelto?", "The Revuelto!", "😱"),
    ("sf90", "valkyrie", "INSANE", "Ferrari SF90, or Aston Martin Valkyrie?", "The Valkyrie!", "💀"),
    ("chiron_ss", "jesko", "IMPOSSIBLE", "Bugatti Chiron Super Sport, or Koenigsegg Jesko?", "The Bugatti!", "☠"),
    ("voiture_noire", "boat_tail", "BONUS", "Bonus! Bugatti La Voiture Noire, or Rolls-Royce Boat Tail?",
     "The Boat Tail! Twenty-eight million!", "👑"),
]
INTRO_LINE = "Which car costs more? Only real car fans get them all!"
END_LINE = "How many did you get? Comment your score!"
ALL_LINES = [INTRO_LINE] + [x for r in ROUNDS for x in (r[3], r[4])] + [END_LINE]


def money(v):
    return f"${v:,.0f}"


# ----------------------------------------------------------------------------
# cards
# ----------------------------------------------------------------------------
def photo_fit(key, w, h):
    """Cover-crop the photo to w x h; very wide shots are fitted over a blurred copy instead."""
    im = Image.open(os.path.join(PHOTO_DIR, key + ".jpg")).convert("RGB")
    a = im.width / im.height
    if a > (w / h) * 1.18:
        bg = im.resize((int(h * a), h), Image.LANCZOS)
        x = (bg.width - w) // 2
        bg = bg.crop((x, 0, x + w, h)).filter(ImageFilter.GaussianBlur(24))
        bg = Image.blend(bg, Image.new("RGB", bg.size, (10, 10, 20)), 0.35)
        fg = im.resize((w, int(w / a)), Image.LANCZOS)
        bg.paste(fg, (0, (h - fg.height) // 2))
        return bg
    s = max(w / im.width, h / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def card(key, letter, gold=False):
    name, _ = CARS[key]
    pad = 26
    out = Image.new("RGBA", (CARD_W + 2 * pad, CARD_H + 2 * pad))
    sh = Image.new("L", out.size)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 12, pad + CARD_W, pad + CARD_H + 12), 54, fill=180)
    out.paste(Image.new("RGBA", out.size, (0, 0, 8, 255)), (0, 0), sh.filter(ImageFilter.GaussianBlur(16)))
    face = photo_fit(key, CARD_W, CARD_H).convert("RGBA")
    g = np.zeros((CARD_H, CARD_W, 4), np.uint8)
    ys = np.arange(CARD_H)[:, None]
    g[..., 3] = (np.clip((ys - CARD_H * 0.55) / (CARD_H * 0.45), 0, 1) ** 1.3 * 220).astype(np.uint8)
    face.alpha_composite(Image.fromarray(g, "RGBA"))
    size = 64
    while rfont(size).getlength(name) > CARD_W - 120 and size > 40:
        size -= 2
    t = rtext(name, size, stroke=6)
    face.alpha_composite(t, (40, CARD_H - t.height - 26))
    badge = mv.circle(86, (255, 255, 255, 240))
    ImageDraw.Draw(badge).text((43, 45), letter, font=rfont(56), fill=INK, anchor="mm")
    face.alpha_composite(badge, (26, 24))
    m = Image.new("L", (CARD_W * 2, CARD_H * 2))
    ImageDraw.Draw(m).rounded_rectangle((0, 0, CARD_W * 2 - 1, CARD_H * 2 - 1), 108, fill=255)
    face.putalpha(m.resize((CARD_W, CARD_H), Image.LANCZOS))
    edge = Image.new("RGBA", (CARD_W, CARD_H))
    ImageDraw.Draw(edge).rounded_rectangle((3, 3, CARD_W - 4, CARD_H - 4), 52,
                                           outline=(GOLD if gold else (255, 255, 255)) + (255,), width=12 if gold else 6)
    face.alpha_composite(edge)
    out.alpha_composite(face, (pad, pad))
    return out


def price_tag(text, col=GOLD, size=64):
    t = rtext(text, size, fill=col, stroke=6)
    tag = rounded_card(t.width + 60, t.height + 26, (t.height + 26) // 2, (12, 10, 26, 235),
                       outline=col + (255,), width=5)
    paste_center(tag, t, tag.width / 2, tag.height / 2)
    return tag


# ----------------------------------------------------------------------------
# backdrop: dark showroom with racing light streaks
# ----------------------------------------------------------------------------
class Showroom:
    def __init__(self):
        rnd = random.Random(11)
        self.base = mv.vgradient(W, H, (12, 12, 26), (26, 14, 40)).convert("RGBA")
        g = mv.soft_circle(1300, (255, 190, 60, 50), 260)
        paste_center(self.base, g, W / 2, VS_Y)
        self.streaks = [(rnd.uniform(0, H), rnd.uniform(200, 700), rnd.uniform(3, 9), rnd.uniform(900, 2600),
                         rnd.choice([GOLD, CYAN, (255, 255, 255), PINK]), rnd.uniform(0, W)) for _ in range(34)]
        ys, xs = np.mgrid[0:H, 0:W]
        dd = np.sqrt(((xs - W / 2) / (W * 0.72)) ** 2 + ((ys - H / 2) / (H * 0.62)) ** 2)
        a = np.zeros((H, W, 4), np.uint8)
        a[..., 3] = (np.clip(dd - 0.62, 0, 1) * 330).clip(0, 170).astype(np.uint8)
        self.vig = Image.fromarray(a, "RGBA")

    def render(self, T, strobe=0.0, tint=None):
        im = self.base.copy()
        layer = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(layer)
        for y, ln, th, sp, col, x0 in self.streaks:                 # light streaks rushing past
            x = (x0 - T * sp) % (W + ln * 2) - ln
            d.rounded_rectangle((x, y, x + ln, y + th), th / 2, fill=col + (60,))
        im.alpha_composite(layer)
        im.alpha_composite(self.vig)
        if tint is not None:
            im.alpha_composite(Image.new("RGBA", (W, H), tint + (36,)))
        if strobe > 0.01:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(40 * strobe))))
        return im


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    MONTAGE = ("boat_tail", "valkyrie", "cybertruck", "revuelto")

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 6 * B
        self.t1, self.t2 = 1.5 * B, 3.5 * B
        self.cuts = [card(k, "?") for k in self.MONTAGE]
        self.o1 = rtext("WHICH CAR", 150, stroke=13)
        self.o2 = join(rtext("COSTS MORE?", 128, fill=GOLD, stroke=12), emoji("💸", 120))
        self.o3 = join(rtext("99% GET IT WRONG", 76, fill=PINK, stroke=8), emoji("💀", 80))
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9),
                        (B, sfx_heartbeat(), 0.8), (self.t2, mq.sfx_boom(), 0.9), (4 * B, mv.sfx_pop(), 0.9),
                        (4.5 * B, mq.sfx_boom(), 0.6), (4.5 * B, mv.sfx_riser(1.5 * B), 0.7),
                        (6 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k in range(len(self.cuts)):
            at = self.t1 + k * 0.5 * B
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mq.sfx_glitch(), 0.35), (at, mv.sfx_click(), 0.7)]
        if tts:
            self.voices.append((0.04, tts.say(INTRO_LINE, speed=1.15)))

    def render(self, t):
        T = self.t0 + t
        bg = self.ui["bg"]
        im = bg.render(T * 1.6, strobe=beat_pulse(T))
        if t < self.t2:                                           # car montage flashing behind the title
            k = min(len(self.cuts) - 1, int(max(0.0, t - 0.0) / (self.t2 / len(self.cuts))))
            tc = t - k * self.t2 / len(self.cuts)
            paste_center(im, scaled(self.cuts[k], 1.08 - 0.08 * ease_out_cubic(tc / 0.15)).rotate(
                (-4, 3, -3, 4)[k], Image.BICUBIC, expand=True), W / 2, 1180)
            if tc < 0.06:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 110)))
            im = rgb_split(im, 14 * (1 - clamp(tc / 0.12)))
        b = int(t / (0.5 * B))
        kk = (t % (0.5 * B)) / (0.5 * B)
        slam = 1 + 0.35 * (1 - ease_out_cubic(kk / 0.4))
        pulse = 1 + 0.035 * beat_pulse(T)
        paste_center(im, scaled(self.o1, (slam if b == 0 else 1.0) * pulse).rotate(-3, Image.BICUBIC, expand=True),
                     W / 2, 380 if t < self.t2 else 560)
        if b >= 1:
            paste_center(im, scaled(self.o2, (slam if b == 1 else 1.0) * pulse).rotate(2, Image.BICUBIC, expand=True),
                         W / 2, 540 if t < self.t2 else 730)
        if t >= self.t2:
            paste_center(im, scaled(self.o3, slam if b == 7 else 1.0), W / 2, 920)
            paste_center(im, emoji("🏎", 300).rotate(-8 + 6 * math.sin(t * 8), Image.BICUBIC, expand=True), W / 2,
                         1260)
        im = shake(im, 22 * (1 - kk) if kk < 0.4 and b in (0, 1, 7) else 0, t)
        whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Round(mv.Scene):
    def __init__(self, idx, r, prev_tier, ui, tts):
        super().__init__()
        ka, kb, tier, spoken, said, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.keys = (ka, kb)
        self.prices = (CARS[ka][1], CARS[kb][1])
        self.win = 0 if self.prices[0] > self.prices[1] else 1
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        f = ENTRY_BEATS
        v_q = tts.say(spoken, speed=1.08) if tts else None
        v_a = tts.say(said, speed=1.1) if tts else None
        q_len = len(v_q) / SR if v_q is not None else 2.6
        a_len = len(v_a) / SR if v_a is not None else 1.0
        c0 = max(f + 4, math.ceil((0.15 + q_len + 0.25) / B))
        n = 3
        self.count_beats = list(range(c0, c0 + n))
        self.fly = f * B
        self.reveal = (c0 + n) * B
        hold = max(5, math.ceil((0.1 + a_len + 0.5) / B))
        self.dur = (c0 + n + hold) * B
        self.cards = [card(ka, "A"), card(kb, "B")]
        self.gold_card = card(self.keys[self.win], "AB"[self.win], gold=True)
        self.dim = Image.new("RGBA", self.cards[0].size)
        ImageDraw.Draw(self.dim).rounded_rectangle((26, 26, 26 + CARD_W, 26 + CARD_H), 54, fill=(4, 0, 14, 150))
        self.hidden = price_tag("$ ???", (255, 255, 255), 60)
        self.ribbon = join(rtext("MORE EXPENSIVE", 56, fill=INK, stroke=0), emoji("💰", 56), gap=10)
        rb = rounded_card(self.ribbon.width + 50, self.ribbon.height + 24, 24, GOLD + (255,), outline=INK + (255,),
                          width=5)
        paste_center(rb, self.ribbon, rb.width / 2, rb.height / 2)
        self.ribbon = rb.rotate(-6, Image.BICUBIC, expand=True)
        diff = abs(self.prices[0] - self.prices[1])
        self.diff = price_tag(f"+{money(diff)}", (90, 230, 140), 54)
        self.sticker = emoji(stick, 140)
        self.col, e = TIERS[tier]
        self.count = rtext("BONUS" if self.bonus else f"{idx}/8", 46, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, self.col + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.title = join(rtext("WHICH COSTS MORE?", 54, stroke=6), emoji("💸", 54), gap=10)
        self.level_up = tier != prev_tier and idx > 1
        self.banner = None
        if self.level_up:
            label = "BONUS: ONLY 1% KNOW THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 62 if self.bonus else 92, fill=self.col, stroke=9), emoji(e, 90))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        self.badge = mv.circle(190, (255, 255, 255, 255))
        ImageDraw.Draw(self.badge).text((95, 98), "VS", font=rfont(84), fill=(220, 30, 60), anchor="mm")
        self.ring = mv.circle(232, GOLD + (255,))
        self.nums = {k: rtext(str(k), 150, fill=PINK if k == 1 else INK, stroke=0) for k in range(1, 4)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (0.12, mv.sfx_whoosh(0.4), 0.6), (0.35, mv.sfx_pop(), 0.6)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        self.sounds += [(self.reveal, mq.sfx_boom(), 0.9), (self.reveal, mv.sfx_ding(), 1.0),
                        (self.reveal + 0.05, mq.sfx_pling(), 0.6), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        for k in range(10):                                         # price counter ticking up
            self.sounds.append((self.reveal + 0.08 + k * 0.07, mv.sfx_click(), 0.35))
        if tts:
            self.voices.append((0.15, v_q))
            self.voices.append((self.reveal + 0.1, v_a))
        r = random.Random(idx * 23)
        self.conf = [(r.uniform(-1, 1) * 700, r.uniform(-1300, -500), r.randint(12, 26),
                      r.choice([GOLD, (90, 230, 140), (255, 255, 255), CYAN]), r.uniform(0, 3)) for _ in range(60)]
        self.cash = [(r.uniform(0, 2 * math.pi), r.uniform(500, 1200), r.choice(ui["cash"]), r.uniform(-300, 300))
                     for _ in range(16)]

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        on_beat = beat_pulse(T) if t > self.fly else 0.0
        tint = (120, 0, 30) if self.danger and rv < 0 else None
        im = self.ui["bg"].render(T, strobe=on_beat * 0.5 + (1 - clamp(rv / 0.25) if rv > 0 else 0), tint=tint)
        if self.danger and 0 < t < self.reveal:
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
        paste_center(im, self.tag, x0 + self.tag.width / 2, 318)
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
                1 + 0.07 * (1 - ease_out_cubic(clamp(rv / 0.35))) if side == self.win else 0.96)
            cx, cy = W / 2 + dx, CARD_Y[side]
            c = self.gold_card if (rv > 0 and side == self.win) else self.cards[side]
            paste_center(im, scaled(c, s), cx, cy)
            # price tag: hidden until the drop, then counts up to the price
            tx, ty = cx + (CARD_W / 2 - 40) * s, cy - (CARD_H / 2 - 40) * s
            if rv <= 0:
                if t > 0.45:
                    tag = self.hidden
                    paste_center(im, scaled(tag, 1 + 0.05 * on_beat), tx - tag.width / 2, ty + tag.height / 2)
            else:
                k = ease_out_cubic(clamp((rv - 0.05) / 0.9))
                v = self.prices[side] * k
                tag = price_tag(money(v), GOLD if side == self.win else (230, 230, 240), 62)
                pop = 1 + 0.25 * (1 - ease_out_cubic(clamp(rv / 0.25)))
                paste_center(im, scaled(tag, pop), tx - tag.width / 2, ty + tag.height / 2)
            if rv > 0 and side != self.win:
                paste_center(im, scaled(self.dim, s), cx, cy, clamp(rv / 0.2))
            if rv > 0 and side == self.win:
                kr = ease_out_back(clamp((rv - 0.1) / 0.25), 2.2)
                if kr > 0.01:
                    paste_center(im, scaled(self.ribbon, 1.5 - 0.5 * kr), cx - 275, cy - CARD_H / 2 + 56, min(1.0, kr))
                ks = ease_out_back((rv - 0.15) / 0.25, 2.2)
                if ks > 0.01:
                    paste_center(im, scaled(self.sticker, ks).rotate(14 * math.sin(rv * 7), Image.BICUBIC,
                                                                     expand=True), cx + 380, cy + 170)
        # VS badge with the 3-2-1, then the price gap
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
            if rv > 0.7:
                kd = ease_out_back(clamp((rv - 0.7) / 0.3), 1.8)
                paste_center(im, scaled(self.diff, kd * (1 + 0.02 * beat_pulse(T))), W / 2, VS_Y)
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, VS_Y, a)
        if rv > 0:
            cy = CARD_Y[self.win]
            for vx, vy, sz, cc, spin in self.conf:
                px, py = W / 2 + vx * rv, cy + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d = ImageDraw.Draw(im)
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            for ang, sp, spr, spin in self.cash:
                k = clamp(rv / 1.2)
                if k < 1:
                    x = W / 2 + math.cos(ang) * sp * k
                    y = cy + math.sin(ang) * sp * k * 0.8 + 900 * k * k
                    paste_center(im, spr.rotate(spin * k, Image.BICUBIC, expand=True), x, y, 1 - k)
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
        self.title = rtext("HOW MANY?", 124, fill=GOLD, stroke=11)
        tiers = [("0-2", "Bus rider", "🚌"), ("3-4", "Learner driver", "🚗"), ("5-6", "Car guy", "😎"),
                 ("7", "Car expert", "🏎"), ("8", "Petrolhead", "🏆")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            colr = PINK if i == 4 else (255, 255, 255)
            row = rounded_card(800, 104, 52, INK + (215,), outline=(colr if i == 4 else (90, 70, 130)) + (255,),
                               width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 52), sc, font=rfont(60), fill=colr, anchor="lm")
            dr.text((200, 52), label, font=rfont(58, "SemiBold"), fill=colr, anchor="lm")
            row.alpha_composite(emoji(e, 60), (800 - 96, 22))
            self.rows.append(row)
        self.bonus = join(rtext("+ bonus = BILLIONAIRE", 56, fill=GOLD, stroke=6), emoji("💎", 60))
        self.cta = join(rtext("comment your score", 58, stroke=6), emoji("👇", 62))
        self.note = rtext("prices: approx. new-car prices in the US", 34, fill=(200, 200, 215), stroke=3)
        self.sounds += [(0.0, mv.sfx_whoosh(0.8), 0.7), (B, mq.sfx_levelup(), 0.9)]
        for i in range(5):
            self.sounds.append(((1.5 + 0.5 * i) * B, mv.sfx_pop(), 0.7))
        self.sounds.append((5 * B, mq.sfx_pling(), 0.7))
        if tts:
            self.voices.append((0.3, tts.say(END_LINE, speed=1.1)))

    def render(self, t):
        T = self.t0 + t
        im = self.ui["bg"].render(T, strobe=0.35 * beat_pulse(T))
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        a = 1 - out
        im.alpha_composite(Image.new("RGBA", (W, H), INK + (int(150 * clamp((t - 0.2) / 0.3) * a),)))
        paste_center(im, self.brand, W / 2, 300, clamp((t - B) / 0.2) * a)
        paste_center(im, scaled(self.title, ease_out_back((t - B) / 0.25)), W / 2, 460, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - (1.5 + 0.5 * i) * B) / 0.2)
            if k > 0:
                paste_center(im, row, W / 2 + (1 - k) * 160, 620 + i * 122, k * a)
        paste_center(im, scaled(self.bonus, ease_out_back((t - 4.5 * B) / 0.25)), W / 2, 1255, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 5 * B) / 0.25) * (1 + 0.03 * math.sin(t * 8))),
                     W / 2, 1350, a)
        paste_center(im, self.note, W / 2, 1450, clamp((t - 5 * B) / 0.3) * a)
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
    ui = {"bg": Showroom(), "vig": [mc.red_vignette(i / 10) for i in range(11)],
          "cash": [emoji(e, s) for e in ("💵", "💰", "💸") for s in (90, 120)]}
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
    im = ui["bg"].render(2.0)
    paste_center(im, card("rangerover", "A"), W / 2, 980)
    paste_center(im, card("corvette", "B"), W / 2, 1610)
    badge = mv.circle(190, (255, 255, 255, 255))
    ImageDraw.Draw(badge).text((95, 98), "VS", font=rfont(84), fill=(220, 30, 60), anchor="mm")
    paste_center(im, mv.circle(232, GOLD + (255,)), W / 2, 1300)
    paste_center(im, badge, W / 2, 1300)
    paste_center(im, rtext("WHICH CAR", 140, stroke=12).rotate(-3, Image.BICUBIC, expand=True), W / 2, 260)
    paste_center(im, join(rtext("COSTS MORE?", 124, fill=GOLD, stroke=11), emoji("💸", 116)).rotate(
        2, Image.BICUBIC, expand=True), W / 2, 430)
    paste_center(im, join(rtext("99% GET IT WRONG", 70, fill=PINK, stroke=7), emoji("💀", 74)), W / 2, 590)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_car_price_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--music", default="phonk", choices=["phonk", "none"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    scenes, starts, total, ui = build(a.voice if not a.cover else "none", None if a.cover else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    if a.cover:
        make_cover(ui, os.path.join(HERE, "car_price_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"carprice_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_carprice")
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
