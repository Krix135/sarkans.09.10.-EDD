#!/usr/bin/env python3
""""GUESS THE GAME BY EMOJIS" Short (1080x1920), edited like the crazy map quiz (part 3 formula).

Each famous video game is described with four emojis that slam in on the beat; a 3-2-1 runs, then the
name slams in neon with letter tiles, a fun fact, confetti, flash and shake. Hook intro (cold open,
emoji montage, title slams), EASY -> IMPOSSIBLE, one "like this video" call-out after round 3 and a
looping score screen. Only emojis and text: no game art, characters or logos.

    python3 make_game_emoji_quiz.py --voice-pack voice_packs/games_adam,voice_packs/map3_adam
    python3 make_game_emoji_quiz.py --stills 1,5,9
    python3 make_game_emoji_quiz.py --cover
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
import make_club_quiz as cq  # noqa: E402
import make_gta_quiz as gq  # noqa: E402
import make_logo_quiz as lq  # noqa: E402
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
ROW_Y = 880                       # the emoji clue row
NAME_Y = 480                      # where the answer slams in
NUM_Y = 330
FLY_BEATS = 3
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE, CTA_AT, CTA_BEATS, CTA_Y = (3,), mc.CTA_LINE, 2 * B, 5, 1585

GAMES = [  # tiles, spoken answer, emoji clues, fact, fact emoji, tier, prompt, reaction sticker
    ("MINECRAFT", "Minecraft!", ["⛏", "🧱", "🧟", "💎"], "the best-selling video game of all time", "🏆", "EASY",
     "Guess the game!", "😎"),
    ("SUPER MARIO", "Super Mario!", ["🍄", "🪠", "👸", "🏰"], "Mario was first called Jumpman", "🦍", "EASY",
     "Next!", "🔥"),
    ("FORTNITE", "Fortnite!", ["🚌", "🪂", "🏝", "🔫"], "its Battle Royale mode came out in 2017", "📅", "EASY",
     "Too easy?", "🤔"),
    ("AMONG US", "Among Us!", ["🚀", "🔪", "🕵", "🚨"], "it came out in 2018 but blew up in 2020", "📈", "MEDIUM",
     "Think fast!", "😳"),
    ("POKEMON", "Pokémon!", ["⚡", "🐭", "🔴", "⚪"], "the highest-grossing media franchise ever", "💰", "MEDIUM",
     "Ooh, tricky!", "🤯"),
    ("SUBWAY SURFERS", "Subway Surfers!", ["🏃", "🚇", "👮", "🛹"],
     "first Google Play game to hit 1 billion downloads", "📲", "MEDIUM", "Next!", "🔥"),
    ("ANGRY BIRDS", "Angry Birds!", ["😡", "🐦", "🐷", "💥"], "it was made by a company from Finland", "🌲", "HARD",
     "Hard level!", "😱"),
    ("PAC MAN", "Pac-Man!", ["🟡", "👻", "🍒", "🍕"], "its shape came from a pizza missing a slice", "🍕", "HARD",
     "No way!", "💀"),
    ("PLANTS VS ZOMBIES", "Plants versus Zombies!", ["🌻", "🌱", "🧟", "🏡"], "it first came out in 2009", "📅",
     "INSANE", "Insane level!", "🧠"),
    ("FLAPPY BIRD", "Flappy Bird!", ["🐦", "🟩", "👆", "💀"], "its creator took it down in 2014", "🚫",
     "IMPOSSIBLE", "Impossible level!", "☠"),
]
INTRO_LINE = "Only real gamers can guess them all!"
END_LINE = "How many did you get? Comment your score!"


# ----------------------------------------------------------------------------
# backdrop: arcade wall with CRT scanlines
# ----------------------------------------------------------------------------
class ArcadeWall(lq.BrandWall):
    EMOJIS = ["🎮", "🕹", "👾", "🏆", "⭐", "💎", "🪙", "❤"]

    def __init__(self):
        super().__init__()
        a = np.zeros((H, W, 4), np.uint8)
        a[::4, :, 3] = 26                                   # CRT scanlines
        self.scan = Image.fromarray(a, "RGBA")

    def render(self, T, col=CYAN, strobe=0.0, rays=1.0):
        im = super().render(T, col, strobe, rays)
        im.alpha_composite(self.scan)
        return im


def clue_row(emojis, size=170):
    """The four clue emojis as separate sprites, plus the glass panel behind them."""
    panel = rounded_card(1000, 300, 70, (20, 8, 48, 215), outline=CYAN + (255,), width=5)
    plus = rtext("+", 74, fill=(255, 255, 255), stroke=6)
    for k in range(3):
        paste_center(panel, plus, 500 + (k - 1) * 240, 150)
    return panel, [emoji(e, size) for e in emojis]


def slot_x(k):
    return W / 2 + (k - 1.5) * 240


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    TEASE = 9                     # cold open on the impossible one
    MONTAGE = (6, 4, 7, 3)

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 6 * B
        self.t1, self.t2 = 1.5 * B, 3.5 * B
        self.tease = clue_row(GAMES[self.TEASE][2])
        self.cuts = [clue_row(GAMES[k][2]) for k in self.MONTAGE]
        self.o1 = rtext("ONLY 1% CAN GUESS", 96, fill=PINK, stroke=10)
        self.o2 = rtext("THIS GAME", 140, stroke=12)
        self.q = rtext("?", 260, stroke=18)
        self.o3 = join(rtext("answer at the end", 60, fill=GOLD, stroke=7), emoji("👀", 64))
        self.m1 = rtext("CAN YOU GUESS", 104, stroke=10)
        self.m2 = rtext("ALL OF THEM?", 120, fill=CYAN, stroke=11)
        self.l1 = rtext("GUESS THE GAME", 128, fill=PINK, stroke=12)
        self.l2 = join(rtext("BY EMOJIS", 130, stroke=12), emoji("🎮", 120), gap=16)
        self.l3 = join(rtext("99% FAIL", 120, fill=GOLD, stroke=11), emoji("💀", 120))
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9),
                        (B, sfx_heartbeat(), 0.8), (self.t2, mq.sfx_boom(), 0.9), (4 * B, mv.sfx_pop(), 0.9),
                        (4.5 * B, mq.sfx_boom(), 0.6), (4.5 * B, mv.sfx_riser(1.5 * B), 0.7),
                        (6 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k in range(len(self.cuts)):
            at = self.t1 + k * 0.5 * B
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mq.sfx_glitch(), 0.35), (at, mv.sfx_click(), 0.7)]
        if tts:
            self.voices.append((0.04, tts.say(INTRO_LINE, speed=1.18)))

    def draw_row(self, im, row, y, s=1.0, t=0.0):
        panel, sprites = row
        paste_center(im, scaled(panel, s), W / 2, y)
        for k, sp in enumerate(sprites):
            paste_center(im, scaled(sp, s * (1 + 0.06 * math.sin(t * 9 + k))), W / 2 + (slot_x(k) - W / 2) * s, y)

    def render(self, t):
        T = self.t0 + t
        bg = self.ui["bg"]
        if t < self.t1:
            im = bg.render(T, GOLD, strobe=beat_pulse(T))
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.45 * beat_pulse(T)))])
            s = 1 + 0.08 * (1 - ease_out_cubic(t / 0.2))
            paste_center(im, scaled(self.o1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 330)
            paste_center(im, scaled(self.o2, s).rotate(2, Image.BICUBIC, expand=True), W / 2, 480)
            self.draw_row(im, self.tease, ROW_Y, 1.0 + 0.04 * beat_pulse(T), t)
            paste_center(im, scaled(self.q, 1 + 0.12 * math.sin(t * 12)).rotate(10 * math.sin(t * 6), Image.BICUBIC,
                                                                                   expand=True), W / 2, 1150)
            paste_center(im, self.o3, W / 2, 1480)
            im = shake(im, 26 * (1 - t / 0.3) if t < 0.3 else 0, t)
            im = rgb_split(im, 12 * (1 - clamp(t / 0.25)))
        elif t < self.t2:
            k = min(len(self.cuts) - 1, int((t - self.t1) / (0.5 * B)))
            tc = t - self.t1 - k * 0.5 * B
            col = [PINK, CYAN, GOLD, mm.RED][k % 4]
            im = bg.render(T, col, strobe=1 - clamp(tc / 0.15))
            self.draw_row(im, self.cuts[k], ROW_Y, 1.1 - 0.1 * ease_out_cubic(tc / 0.15), t)
            s = 1 + 0.12 * (1 - ease_out_cubic((t - self.t1) / 0.15))
            paste_center(im, scaled(self.m1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 330)
            paste_center(im, scaled(self.m2, s).rotate(3, Image.BICUBIC, expand=True), W / 2, 480)
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
                -3, Image.BICUBIC, expand=True), W / 2, 620)
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


class Round(mv.Scene):
    def __init__(self, idx, g, prev_tier, ui, tts):
        super().__init__()
        name, said, emojis, fact, femoji, tier, prompt, stick = g
        self.idx, self.ui, self.tier = idx, ui, tier
        self.danger = tier in ("INSANE", "IMPOSSIBLE")
        self.cta = idx in CTA_AFTER
        f = FLY_BEATS
        self.dur = (f + 8 + (CTA_BEATS if self.cta else 0)) * B
        self.fly = f * B
        self.reveal = (f + 4) * B
        self.count_beats = [f + 1, f + 2, f + 3]
        self.pop_at = [0.15 + k * 0.5 * B for k in range(4)]
        self.panel, self.sprites = clue_row(emojis)
        self.tiles = mm.Tiles(name, tier in ("INSANE", "IMPOSSIBLE"))
        self.col, e = TIERS[tier]
        shown = said.rstrip("!").upper()
        size = 120
        while rfont(size).getlength(shown) > 940 and size > 60:
            size -= 4
        self.answer = gq.neon(shown, size, self.col, stroke=max(6, size // 12))
        fs = 42
        while rfont(fs).getlength(fact) > 760 and fs > 26:
            fs -= 1
        body = join(emoji(femoji, 52), rtext(fact, fs, stroke=0), gap=14)
        self.fact = rounded_card(body.width + 56, body.height + 22, (body.height + 22) // 2, INK + (225,))
        paste_center(self.fact, body, self.fact.width / 2, self.fact.height / 2)
        self.sticker = emoji(stick, 150)
        self.count = rtext(f"{idx}/{len(GAMES)}", 46, stroke=5)
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, self.col + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.level_up = tier != prev_tier and idx > 1
        self.banner = join(rtext(f"{tier}!", 92, fill=self.col, stroke=9), emoji(e, 90)) if self.level_up else None
        if self.level_up:
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        self.nums = {n: rtext(str(n), 230, fill=PINK if n == 1 else (255, 255, 255), stroke=16) for n in (1, 2, 3)}
        self.streak = {n: join(rtext(f"x{n}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for n in (idx - 1, idx)}
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8)]
        for at in self.pop_at:
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mv.sfx_pop(), 0.8)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == 2), 1.0), (b * B, mv.sfx_click(), 0.5)]
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
            v = tts.say(said, speed=1.12)
            self.voices.append((self.reveal + 0.08, v))
            limit = (self.reveal + CTA_AT) if self.cta else (self.dur - 0.1)
            if self.reveal + 0.08 + len(v) / SR > limit:
                print(f"warning: answer {idx} runs long", flush=True)
            if self.cta:
                v = tts.say(CTA_LINE, speed=1.12)
                self.voices.append((self.reveal + CTA_AT, v))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            self.sounds += [(self.reveal + CTA_AT, mv.sfx_pop(), 0.9), (self.reveal + CTA_AT + 0.02, mq.sfx_pling(), 0.5),
                            (self.reveal + CTA_AT + 0.45, mv.sfx_click(), 0.8)]
        r = random.Random(idx * 31)
        self.conf = [(r.uniform(-1, 1) * 700, r.uniform(-1350, -450), r.randint(12, 26),
                      r.choice([self.col, GOLD, CYAN, PINK, (255, 255, 255)]), r.uniform(0, 3)) for _ in range(70)]

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        on_beat = beat_pulse(T) if t > self.fly else 0.0
        im = self.ui["bg"].render(T, self.col, strobe=on_beat * 0.6 + (1 - clamp(rv / 0.25) if rv > 0 else 0),
                                  rays=0.55 + 0.45 * on_beat if rv < 0 else 1.0)
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv > 0:
            im.alpha_composite(cq.speed_lines(1 - clamp(rv / 0.45), self.idx, (540, ROW_Y)))
        d = ImageDraw.Draw(im)
        paste_center(im, self.count, 92, 222)
        x0, x1, y, bh = 160, 1000, 222, 22
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
        # clue row: the panel slides in, each emoji slams in on its half beat, then bounces on the beat
        kp = ease_out_back(clamp(t / 0.3), 1.5)
        rs = 1 + (0.12 * (1 - ease_out_cubic(clamp(rv / 0.35))) if rv > 0 else 0.02 * on_beat)
        if kp > 0.01:
            paste_center(im, scaled(self.panel, kp * rs), W / 2 + (1 - kp) * 600, ROW_Y)
        for k, sp in enumerate(self.sprites):
            ke = (t - self.pop_at[k]) / 0.22
            if ke <= 0:
                continue
            s = (1.8 - 0.8 * ease_out_back(clamp(ke), 1.6)) if ke < 1 else 1.0
            bob = 1 + 0.07 * (beat_pulse(T) if (k + int(T / B)) % 2 == 0 else 0)
            if rv > 0:
                bob *= 1 + 0.25 * max(0.0, math.sin(math.pi * clamp((rv - 0.05 * k) / 0.35)))
            ang = 6 * math.sin(T * 3 + k * 1.3)
            paste_center(im, scaled(sp, s * bob * rs).rotate(ang, Image.BICUBIC, expand=True),
                         W / 2 + (slot_x(k) - W / 2) * rs, ROW_Y)
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, NAME_Y, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[3 - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NAME_Y, a * 0.9)
        self.tiles.draw(im, t - self.fly - B, rv)
        if rv > 0:
            ka = ease_out_back(clamp(rv / 0.25), 2.2)
            paste_center(im, scaled(self.answer, (1.6 - 0.6 * ka) * (1 + 0.03 * beat_pulse(T))).rotate(
                -3, Image.BICUBIC, expand=True), W / 2, NAME_Y, min(1.0, ka))
            for vx, vy, sz, cc, spin in self.conf:
                px, py = W / 2 + vx * rv, ROW_Y + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d = ImageDraw.Draw(im)
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            sk = ease_out_back((rv - 0.12) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             940, 1090)
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
        self.title = gq.neon("HOW MANY?", 124, CYAN, stroke=11)
        tiers = [("0-3", "Noob", "🐣"), ("4-5", "Casual gamer", "🎮"), ("6-7", "Pro gamer", "😎"),
                 ("8-9", "Speedrunner", "⚡"), ("10", "Gaming legend", "🏆")]
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
        paste_center(im, scaled(self.cta, ease_out_back((t - 4.5 * B) / 0.25) * (1 + 0.03 * math.sin(t * 8))),
                     W / 2, 1285, a)
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
    ui = {"bg": ArcadeWall(), "vig": [mc.red_vignette(i / 10) for i in range(11)]}
    intro = Intro(ui, tts)
    scenes, prev = [intro], GAMES[0][5]
    for i, g in enumerate(GAMES, 1):
        scenes.append(Round(i, g, prev, ui, tts))
        prev = g[5]
    scenes.append(Ending(ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    im = ui["bg"].render(1.0, PINK, rays=1.0)
    im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 50)))
    paste_center(im, rtext("GUESS THE GAME", 118, fill=PINK, stroke=11).rotate(-3, Image.BICUBIC, expand=True),
                 W / 2, 300)
    paste_center(im, join(rtext("BY EMOJIS", 130, stroke=12), emoji("🎮", 118), gap=14).rotate(
        2, Image.BICUBIC, expand=True), W / 2, 470)
    for k, gi in enumerate((0, 6, 9)):
        panel, sprites = clue_row(GAMES[gi][2], 150)
        y = 820 + k * 330
        paste_center(im, scaled(panel, 0.92), W / 2, y)
        for j, sp in enumerate(sprites):
            paste_center(im, sp, W / 2 + (slot_x(j) - W / 2) * 0.92, y)
    paste_center(im, join(rtext("99% FAIL", 96, fill=GOLD, stroke=9), emoji("💀", 98)), W / 2, 1720)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_game_emoji_quiz.mp4"))
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
    work = os.path.join(mv.CACHE_DIR, "render_games")
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
        make_cover(ui, os.path.join(HERE, "game_emoji_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"games_{float(s):06.2f}.png")
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
