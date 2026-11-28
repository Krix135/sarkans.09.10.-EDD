#!/usr/bin/env python3
""""GUESS THE LOGO WITHOUT THE NAME" Short (1080x1920), edited like the crazy map and club quizzes.

Famous brand logos with their names taken out sit on a white card; a 3-2-1 runs on the beat and on the
drop the card flips over to the real logo, name and all. Animated "brand wall" backdrop (scrolling
emoji wallpaper, rotating light rays and glow in the level colour, floating bokeh), 130 BPM phonk,
level banners, glitches, shakes, RGB split, streak counter, letter tiles, fun facts, one "like this
video" call-out and an ending that loops back into the first frame.

Logos: from Wikimedia (brand_logos/, not committed: they are the brands' trademarks);
brand_logos/notext/ holds the same logos with the lettering removed.

    python3 make_logo_quiz.py --voice-pack voice_packs/logo_adam,voice_packs/map3_adam
    python3 make_logo_quiz.py --stills 1,9,12
    python3 make_logo_quiz.py --cover
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
LOGO_DIR = os.path.join(HERE, "brand_logos")
CARD_C = (540, 800)
CARD = 640
NUM_Y = 330
FLY_BEATS = 3
FLIP = 0.14                       # the card squashes shut over this long before the drop, then opens on it
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE, CTA_AT, CTA_BEATS, CTA_Y = (3,), mc.CTA_LINE, 2 * B, 5, 1585

LOGOS = [  # logo file, tiles, spoken answer, fact, fact emoji, tier, prompt, reaction sticker
    ("mcdonalds", "MCDONALDS", "McDonald's!", "its first restaurant opened in 1940", "🍔", "EASY", "Guess the logo!",
     "😎"),
    ("apple", "APPLE", "Apple!", "co-founded in 1976 by Steve Jobs", "🍎", "EASY", "Next!", "🔥"),
    ("nike", "NIKE", "Nike!", "named after the Greek goddess of victory", "🏛", "EASY", "Too easy?", "🤔"),
    ("starbucks", "STARBUCKS", "Starbucks!", "named after a character in Moby-Dick", "📚", "HARD", "Hard level!", "😳"),
    ("burger_king", "BURGER KING", "Burger King!", "home of the Whopper since 1957", "🍔", "HARD", "Think fast!",
     "🤯"),
    ("dominos", "DOMINOS", "Domino's!", "the dots were meant for its first 3 stores", "🍕", "HARD", "Ooh, tricky!",
     "🔥"),
    ("redbull", "RED BULL", "Red Bull!", "based on a Thai drink, Krating Daeng", "🐂", "INSANE", "Insane level!", "😱"),
    ("adidas", "ADIDAS", "Adidas!", "named after its founder, Adi Dassler", "👟", "INSANE", "No way!", "💀"),
    ("lacoste", "LACOSTE", "Lacoste!", "a tennis star nicknamed 'the Crocodile'", "🎾", "INSANE", "Only geniuses!",
     "🧠"),
    ("tacobell", "TACO BELL", "Taco Bell!", "founded in 1962 by Glen Bell", "🌮", "IMPOSSIBLE", "Impossible level!",
     "☠"),
    ("pizzahut", "PIZZA HUT", "Pizza Hut!", "founded in 1958 in Wichita, Kansas", "🍕", "BONUS",
     "Bonus! Only one percent!", "👑"),
]
INTRO_LINE = "Only one percent can name every logo!"
END_LINE = "How many did you get? Comment your score!"


# ----------------------------------------------------------------------------
# logo cards
# ----------------------------------------------------------------------------
def load_logo(key, notext=False):
    return Image.open(os.path.join(LOGO_DIR, "notext" if notext else "", key + ".png")).convert("RGBA")


def card_face(logo, size=CARD):
    """The logo on a clean white rounded card with a soft shadow."""
    pad = 40
    out = Image.new("RGBA", (size + 2 * pad, size + 2 * pad))
    sh = Image.new("L", out.size)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 14, pad + size, pad + size + 14), size // 7, fill=150)
    out.paste(Image.new("RGBA", out.size, (10, 0, 30, 255)), (0, 0), sh.filter(ImageFilter.GaussianBlur(18)))
    face = mv.vgradient(size, size, (255, 255, 255), (236, 236, 244)).convert("RGBA")
    m = Image.new("L", (size * 3, size * 3))
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size * 3 - 1, size * 3 - 1), size * 3 // 7, fill=255)
    face.putalpha(m.resize((size, size), Image.LANCZOS))
    lg = logo.copy()
    box = int(size * 0.74)
    lg.thumbnail((box, box), Image.LANCZOS)
    face.alpha_composite(lg, ((size - lg.width) // 2, (size - lg.height) // 2))
    edge = Image.new("RGBA", (size, size))
    ImageDraw.Draw(edge).rounded_rectangle((2, 2, size - 3, size - 3), size // 7, outline=(255, 255, 255, 255),
                                           width=6)
    face.alpha_composite(edge)
    out.alpha_composite(face, (pad, pad))
    return out


def flip(img, k):
    """Squash a card horizontally (k = 1 open, 0 edge-on)."""
    w = max(1, int(img.width * max(0.0, k)))
    return img.resize((w, img.height), Image.BILINEAR)


# ----------------------------------------------------------------------------
# animated brand wall
# ----------------------------------------------------------------------------
class BrandWall:
    TILE = 170
    EMOJIS = ["🍔", "🍟", "🥤", "🍕", "☕", "👟", "📱", "🌮", "🍩", "🛍"]

    def __init__(self):
        rnd = random.Random(3)
        top, bot = (24, 8, 64), (66, 14, 104)
        self.base = mv.vgradient(W, H, top, bot).convert("RGBA")
        P = self.TILE
        pat = Image.new("RGBA", (W + 2 * P, H + 4 * P))
        k = 0
        for r, y in enumerate(range(0, pat.height, P)):
            for x in range(-P, pat.width, P):
                e = emoji(self.EMOJIS[k % len(self.EMOJIS)], 78).rotate(rnd.uniform(-20, 20), Image.BICUBIC,
                                                                         expand=True)
                k += 3
                e.putalpha(e.getchannel("A").point(lambda v: v * 30 // 255))
                pat.alpha_composite(e, (int(x + (P // 2 if r % 2 else 0) + (P - e.width) / 2), int(y + (P - e.height) / 2)))
        self.pattern = pat
        self.bokeh = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(10, 34), rnd.uniform(0.2, 0.7),
                       rnd.choice([(255, 255, 255), CYAN, PINK, GOLD])) for _ in range(26)]
        self.rays, self.glows = {}, {}
        ys, xs = np.mgrid[0:H, 0:W]
        dd = np.sqrt(((xs - W / 2) / (W * 0.72)) ** 2 + ((ys - H / 2) / (H * 0.62)) ** 2)
        a = np.zeros((H, W, 4), np.uint8)
        a[..., :3] = (8, 0, 24)
        a[..., 3] = (np.clip(dd - 0.6, 0, 1) * 330).clip(0, 180).astype(np.uint8)
        self.vig = Image.fromarray(a, "RGBA")

    def ray_frames(self, col):
        if col not in self.rays:
            S = 1300
            im = Image.new("RGBA", (S, S))
            d = ImageDraw.Draw(im)
            for i in range(14):
                a0, a1 = (i - 0.24) * 2 * math.pi / 14, (i + 0.24) * 2 * math.pi / 14
                d.polygon([(S / 2, S / 2), (S / 2 + S * math.cos(a0), S / 2 + S * math.sin(a0)),
                           (S / 2 + S * math.cos(a1), S / 2 + S * math.sin(a1))], fill=col + (52,))
            g = Image.new("L", (S, S))
            ImageDraw.Draw(g).ellipse((S * 0.1, S * 0.1, S * 0.9, S * 0.9), fill=255)
            g = g.filter(ImageFilter.GaussianBlur(150))
            im.putalpha(Image.fromarray((np.asarray(im.getchannel("A")).astype(np.float32) *
                                         np.asarray(g) / 255).astype(np.uint8)))
            self.rays[col] = [im.rotate(k * (360 / 14) / 8, Image.BILINEAR) for k in range(8)]
            self.glows[col] = mv.soft_circle(900, col + (130,), 140)
        return self.rays[col], self.glows[col]

    def render(self, T, col=CYAN, strobe=0.0, rays=1.0):
        im = self.base.copy()
        P = self.TILE
        ox, oy = int(T * 40) % P, int(T * 80) % (2 * P)
        im.alpha_composite(self.pattern.crop((P - ox, 2 * P - oy, P - ox + W, 2 * P - oy + H)))
        frames, glow = self.ray_frames(col)
        paste_center(im, glow, *CARD_C)
        if rays > 0.01:
            paste_center(im, frames[int(T * 10) % 8], *CARD_C, rays)
        d = ImageDraw.Draw(im)
        for x, y, r, sp, c in self.bokeh:
            yy = (y - T * 60 * sp) % (H + 80) - 40
            xx = x + 20 * math.sin(T * sp * 2 + y)
            d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=c + (int(40 + 40 * sp),))
        im.alpha_composite(self.vig)
        if strobe > 0.01:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(40 * strobe))))
        return im


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    TEASE, MONTAGE = "pizzahut", ("tacobell", "redbull", "adidas", "lacoste")

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 6 * B
        self.t1, self.t2 = 1.5 * B, 3.5 * B
        self.tease = card_face(load_logo(self.TEASE, True), 600)
        self.cuts = [card_face(load_logo(k, True), 560) for k in self.MONTAGE]
        self.o1 = rtext("ONLY 1% KNOW", 124, fill=PINK, stroke=12)
        self.o2 = rtext("THIS LOGO", 132, stroke=11)
        self.q = rtext("?", 300, stroke=18)
        self.o3 = join(rtext("answer at the end", 60, fill=GOLD, stroke=7), emoji("👀", 64))
        self.m1 = rtext("THE NAMES", 112, stroke=10)
        self.m2 = rtext("ARE GONE...", 124, fill=CYAN, stroke=11)
        self.l1 = rtext("GUESS THE LOGO", 128, stroke=12)
        self.l2 = rtext("WITHOUT THE NAME", 100, fill=CYAN, stroke=10)
        self.l3 = join(rtext("99% FAIL", 130, fill=GOLD, stroke=12), emoji("💀", 130))
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9),
                        (B, sfx_heartbeat(), 0.8), (self.t2, mq.sfx_boom(), 0.9), (4 * B, mv.sfx_pop(), 0.9),
                        (4.5 * B, mq.sfx_boom(), 0.6), (4.5 * B, mv.sfx_riser(1.5 * B), 0.7),
                        (6 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k in range(len(self.cuts)):
            at = self.t1 + k * 0.5 * B
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mq.sfx_glitch(), 0.35), (at, mv.sfx_click(), 0.7)]
        if tts:
            self.voices.append((0.04, tts.say(INTRO_LINE, speed=1.18)))

    def render(self, t):
        T = self.t0 + t
        bg = self.ui["bg"]
        if t < self.t1:
            im = bg.render(T, GOLD, strobe=beat_pulse(T))
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.45 * beat_pulse(T)))])
            s = (1.1 - 0.1 * ease_out_cubic(t / 0.3)) * (1 + 0.05 * beat_pulse(T))
            paste_center(im, scaled(self.tease, s).rotate(4 * math.sin(t * 5), Image.BICUBIC, expand=True), *CARD_C)
            s = 1 + 0.08 * (1 - ease_out_cubic(t / 0.2))
            paste_center(im, scaled(self.o1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 300)
            paste_center(im, scaled(self.o2, s).rotate(2, Image.BICUBIC, expand=True), W / 2, 440)
            paste_center(im, scaled(self.q, 1 + 0.12 * math.sin(t * 12)).rotate(10 * math.sin(t * 6), Image.BICUBIC,
                                                                                   expand=True), 900, 1110)
            paste_center(im, self.o3, W / 2, 1480)
            im = shake(im, 26 * (1 - t / 0.3) if t < 0.3 else 0, t)
            im = rgb_split(im, 12 * (1 - clamp(t / 0.25)))
        elif t < self.t2:
            k = min(len(self.cuts) - 1, int((t - self.t1) / (0.5 * B)))
            tc = t - self.t1 - k * 0.5 * B
            col = [PINK, CYAN, GOLD, mm.RED][k % 4]
            im = bg.render(T, col, strobe=1 - clamp(tc / 0.15))
            paste_center(im, scaled(self.cuts[k], 1.1 - 0.1 * ease_out_cubic(tc / 0.15)).rotate(
                (-7, 6, -5, 7)[k], Image.BICUBIC, expand=True), *CARD_C)
            s = 1 + 0.12 * (1 - ease_out_cubic((t - self.t1) / 0.15))
            paste_center(im, scaled(self.m1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 300)
            paste_center(im, scaled(self.m2, s).rotate(3, Image.BICUBIC, expand=True), W / 2, 440)
            im = rgb_split(im, 18 * (1 - clamp(tc / 0.12)))
            if tc < 0.06:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
        else:
            tg = t - self.t2
            im = bg.render(T, CYAN, strobe=beat_pulse(T))
            im = rgb_split(im, 10 * (1 - clamp(tg / B)))
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 80)))
            b = int(tg / (0.5 * B))
            kk = (tg % (0.5 * B)) / (0.5 * B)
            slam = 1 + 0.35 * (1 - ease_out_cubic(kk / 0.4))
            paste_center(im, scaled(self.l1, (slam if b == 0 else 1.0) * (1 + 0.03 * beat_pulse(T))).rotate(
                -3, Image.BICUBIC, expand=True), W / 2, 640)
            if b >= 1:
                paste_center(im, scaled(self.l2, slam if b == 1 else 1.0).rotate(2, Image.BICUBIC, expand=True),
                             W / 2, 800)
            if b >= 2:
                paste_center(im, scaled(self.l3, slam if b == 2 else 1.0), W / 2, 1010)
            im = shake(im, 22 * (1 - kk) if kk < 0.4 and b <= 2 else 0, t)
            whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
            if whip > 0:
                im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Logo(mv.Scene):
    def __init__(self, idx, q, prev_tier, ui, tts):
        super().__init__()
        key, name, said, fact, femoji, tier, prompt, stick = q
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = FLY_BEATS
        self.dur = (f + (12 if self.bonus else 8) + (CTA_BEATS if self.cta else 0)) * B
        self.fly = f * B
        self.reveal = (f + (7 if self.bonus else 4)) * B
        self.count_beats = list(range(f + 2, f + 7)) if self.bonus else [f + 1, f + 2, f + 3]
        full = load_logo(key)
        self.cols = cq.logo_colours(full) + [(255, 255, 255), GOLD]
        self.quiz_card, self.full_card = card_face(load_logo(key, True)), card_face(full)
        self.tiles = mm.Tiles(name, tier in ("INSANE", "IMPOSSIBLE", "BONUS"))
        size = 42
        while rfont(size).getlength(fact) > 760 and size > 26:
            size -= 1
        body = join(emoji(femoji, 52), rtext(fact, size, stroke=0), gap=14)
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
        self.nums = {n: rtext(str(n), 230, fill=PINK if n == 1 else (255, 255, 255), stroke=16)
                     for n in range(1, len(self.count_beats) + 1)}
        self.streak = {n: join(rtext(f"x{n}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for n in (idx - 1, idx)}
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (self.fly * 0.55, mq.sfx_boom(), 0.7),
                        (self.fly * 0.55, mv.sfx_pop(), 0.8)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == len(self.count_beats) - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        self.sounds += [(self.reveal - FLIP, mv.sfx_whoosh(0.25), 0.7), (self.reveal, mq.sfx_boom(), 0.9),
                        (self.reveal, mv.sfx_ding(), 1.0), (self.reveal + 0.05, mq.sfx_pling(), 0.6),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
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
                    print(f"warning: the like line after {idx} runs into the next logo", flush=True)
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            self.sounds += [(self.reveal + CTA_AT, mv.sfx_pop(), 0.9), (self.reveal + CTA_AT + 0.02, mq.sfx_pling(), 0.5),
                            (self.reveal + CTA_AT + 0.45, mv.sfx_click(), 0.8)]
        r = random.Random(idx * 31)
        self.conf = [(r.uniform(-1, 1) * 700, r.uniform(-1350, -450), r.randint(12, 26), r.choice(self.cols),
                      r.uniform(0, 3)) for _ in range(70)]

    def card(self, t):
        """The card for time t: the name-free face, squashing shut just before the drop, then the real logo."""
        rv = t - self.reveal
        if rv < -FLIP:
            return self.quiz_card
        if rv < 0:
            return flip(self.quiz_card, ease_in_cubic(-rv / FLIP))
        return flip(self.full_card, ease_out_back(rv / 0.2, 1.6))

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        on_beat = beat_pulse(T) if t > self.fly else 0.0
        rays = 0.6 + 0.4 * on_beat if rv < 0 else 1.0
        im = self.ui["bg"].render(T, self.col, strobe=on_beat * 0.6 + (1 - clamp(rv / 0.25) if rv > 0 else 0),
                                  rays=rays)
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv > 0:
            im.alpha_composite(cq.speed_lines(1 - clamp(rv / 0.45), self.idx, CARD_C))
        # the card: spins in, floats, bounces on the beats, kicks on each count, flips on the drop
        k_in = clamp(t / (self.fly * 0.55))
        s = ease_out_back(k_in, 1.4) if k_in < 1 else 1.0
        ang = 80 * (1 - ease_out_cubic(k_in)) + 3 * math.sin(T * 1.7)
        if t > self.fly:
            s *= 1 + 0.035 * beat_pulse(T)
        for b in self.count_beats:
            tb = t - b * B
            if 0 <= tb < 0.25:
                s *= 1 + 0.07 * (1 - tb / 0.25)
                ang += 4 * (1 - tb / 0.25) * (1 if b % 2 else -1)
        if 0 < rv < 0.4:
            s *= 1 + 0.18 * (1 - ease_out_cubic(rv / 0.4))
        if s > 0.02:
            c = scaled(self.card(t), s)
            if abs(ang) > 0.3:
                c = c.rotate(ang, Image.BICUBIC, expand=True)
            paste_center(im, c, CARD_C[0], CARD_C[1] + 10 * math.sin(T * 2.2))
        cq.shockwave(im, rv, self.col)
        d = ImageDraw.Draw(im)
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
            sc = 1 + 0.5 * (1 - ease_out_cubic(rv / 0.25)) if 0 < rv < 0.25 else 1.0
            stk = self.streak[n]
            paste_center(im, scaled(stk, sc), x1 - stk.width / 2 + 10, 288)
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, 420, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a * 0.9)
        self.tiles.draw(im, t - self.fly - B, rv)
        if rv > 0:
            for vx, vy, sz, cc, spin in self.conf:
                px, py = CARD_C[0] + vx * rv, CARD_C[1] + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            sk = ease_out_back((rv - 0.12) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             905, 1120)
            fk = ease_out_back((rv - 0.35) / 0.3)
            if fk > 0.01:
                paste_center(im, scaled(self.fact, fk), W / 2, mm.FACT_Y)
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
                    im = shake(im, 12 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 8 * (1 - tb / 0.15))
        if self.cta and rv > CTA_AT:
            ct = rv - CTA_AT
            k = ease_out_back(ct / 0.3, 2.0) * (1 - ease_in_cubic(clamp((t - (self.dur - 0.45)) / 0.25)))
            if k > 0.01:
                card = self.cta_card.copy()
                tap = 1 - 0.18 * math.sin(math.pi * clamp((ct - 0.45) / 0.2))
                th = scaled(self.thumb, tap * (1 + 0.08 * beat_pulse(T))).rotate(10 * math.sin(ct * 7), Image.BICUBIC,
                                                                                 expand=True)
                paste_center(card, th, 98, 98)
                sc = k * (1 + 0.025 * beat_pulse(T))
                paste_center(im, scaled(card, sc).rotate(-2, Image.BICUBIC, expand=True), W / 2, CTA_Y)
                rp = (ct - 0.5) / 0.45
                if 0 < rp < 1:
                    d = ImageDraw.Draw(im)
                    rr, cx = 70 + 110 * ease_out_cubic(rp), W / 2 - 312 * sc
                    d.ellipse((cx - rr, CTA_Y - rr, cx + rr, CTA_Y + rr), outline=PINK + (int(255 * (1 - rp)),),
                              width=max(1, int(10 * (1 - rp))))
        if self.level_up and t < 0.35:
            im = glitch(im, 1 - t / 0.35, int(t * 30) + self.idx * 7)
        if t < 0.18:
            im = rgb_split(mm.zoom_blur(im, 1 - t / 0.18), 20 * (1 - t / 0.18))
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
        tiers = [("0-3", "Window shopper", "🛒"), ("4-5", "Snack lover", "🍿"), ("6-7", "Brand expert", "🧐"),
                 ("8-9", "Marketing genius", "🧠"), ("10", "Logo legend", "🏆")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            colr = PINK if i == 4 else (255, 255, 255)
            row = rounded_card(820, 104, 52, INK + (215,), outline=(colr if i == 4 else (90, 70, 130)) + (255,),
                               width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 52), sc, font=rfont(60), fill=colr, anchor="lm")
            dr.text((200, 52), label, font=rfont(56, "SemiBold"), fill=colr, anchor="lm")
            row.alpha_composite(emoji(e, 60), (820 - 96, 22))
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
        im = self.ui["bg"].render(T, GOLD, strobe=0.4 * beat_pulse(T), rays=0.8)
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
    ui = {"bg": BrandWall(), "vig": [mc.red_vignette(i / 10) for i in range(11)]}
    intro = Intro(ui, tts)
    scenes, prev = [intro], LOGOS[0][5]
    for i, q in enumerate(LOGOS, 1):
        scenes.append(Logo(i, q, prev, ui, tts))
        prev = q[5]
    scenes.append(Ending(ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    im = ui["bg"].render(0.0, CYAN)
    for key, x, y, ang, sz in (("tacobell", 250, 1190, 12, 470), ("starbucks", 830, 1190, -12, 470),
                               ("redbull", 540, 1080, 0, 560)):
        paste_center(im, card_face(load_logo(key, True), sz).rotate(ang, Image.BICUBIC, expand=True), x, y)
    im.alpha_composite(mm.shade_overlay(0.7))
    paste_center(im, rtext("GUESS THE", 140, stroke=12), W / 2, 250)
    paste_center(im, rtext("LOGO", 230, fill=CYAN, stroke=16), W / 2, 445)
    paste_center(im, join(rtext("NAME REMOVED", 82, fill=PINK, stroke=8), emoji("🚫", 84)).rotate(
        -3, Image.BICUBIC, expand=True), W / 2, 640)
    paste_center(im, rtext("?", 260, stroke=17).rotate(12, Image.BICUBIC, expand=True), 900, 1560)
    paste_center(im, join(rtext("99% FAIL", 100, fill=GOLD, stroke=9), emoji("💀", 100)), W / 2, 1600)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_logo_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--audio-only", action="store_true", help="rebuild only the sound and swap it into --out")
    ap.add_argument("--music", default="phonk", choices=["phonk", "none"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    quiet = a.stills or a.cover
    scenes, starts, total, ui = build(a.voice if not quiet else "none", None if quiet else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_logos")
    os.makedirs(work, exist_ok=True)
    if a.audio_only:
        src, wav = os.path.join(work, "video_src.mp4"), os.path.join(work, "audio_only.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.out, "-map", "0:v", "-c", "copy", src], check=True)
        mv.write_wav(wav, mmq.mix_audio(scenes, starts, total, a.music))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-c:a", "aac",
                        "-b:a", "192k", "-movflags", "+faststart", "-shortest", a.out], check=True)
        print(f"Done (audio only): {a.out}")
        return
    if a.cover:
        make_cover(ui, os.path.join(HERE, "logo_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"logos_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
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
