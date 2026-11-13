#!/usr/bin/env python3
""""GUESS THE COUNTRY BY ITS FOOD" Short (1080x1920), part 3 formula with a bigger hook.

Each country is given by four food emojis that slam in on the beat (no flags in the clues). Below them
a globe spins with a big "?"; a 3-2-1 runs on the beat, then on the drop the globe whips to the
country, which fills with its flag, while the name flips in on letter tiles with a fun fact.
Hook intro: cold open on a mystery clue, a rapid clue montage, then GUESS THE COUNTRY / BY ITS FOOD /
99% FAIL slamming over a spinning globe with food orbiting it. EASY -> IMPOSSIBLE plus a bonus, one
like call-out after round 3, looping score screen. Borders: Natural Earth (public domain); flags:
public domain.

    python3 make_food_country_quiz.py
    python3 make_food_country_quiz.py --stills 0,2,5
    python3 make_food_country_quiz.py --cover
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

from PIL import Image, ImageDraw  # noqa: E402

import brand  # noqa: E402
import globe as G  # noqa: E402
import make_bigger_country_quiz as bq  # noqa: E402
import make_club_quiz as cq  # noqa: E402
import make_game_emoji_quiz as ge  # noqa: E402
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
PW, PH = bq.PW, bq.PH              # globe panel 1000 x 600
ROW_Y = 520                        # food clue row
PANEL_Y = 1010
mm.TILE_Y = 1395                   # letter tiles under the globe
FACT_Y = 1490
CTA_Y = 1640
FLY_BEATS = 3
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
SPIN_R = 270                       # the whole globe while you think

ROUNDS = [  # map code, flag, tiles, spoken answer, food emojis, fact, fact emoji, tier, prompt, sticker
    ("ITA", "IT", "ITALY", "Italy!", ["🍕", "🍝", "🧀", "🍷"], "there are about 350 shapes of pasta", "🍝", "EASY",
     "Guess the country!", "😎"),
    ("JPN", "JP", "JAPAN", "Japan!", ["🍣", "🍜", "🍙", "🍵"], "Tokyo has the most Michelin-star restaurants", "⭐",
     "EASY", "Next!", "🔥"),
    ("MEX", "MX", "MEXICO", "Mexico!", ["🌮", "🌯", "🥑", "🌶"], "avocados first grew here", "🥑", "EASY",
     "Too easy?", "🤔"),
    ("FRA", "FR", "FRANCE", "France!", ["🥐", "🥖", "🧀", "🍷"], "it makes over 1,000 kinds of cheese", "🧀", "MEDIUM",
     "Think fast!", "😳"),
    ("IND", "IN", "INDIA", "India!", ["🍛", "🫓", "🍚", "🌶"], "it's the world's biggest spice producer", "🌶",
     "MEDIUM", "Ooh, tricky!", "🤯"),
    ("CHN", "CN", "CHINA", "China!", ["🥟", "🥢", "🍜", "🫖"], "4,000-year-old noodles were found here", "🍜",
     "MEDIUM", "Next!", "🔥"),
    ("ESP", "ES", "SPAIN", "Spain!", ["🥘", "🫒", "🍤", "🍅"], "it makes the most olive oil in the world", "🫒",
     "HARD", "Hard level!", "😱"),
    ("TUR", "TR", "TURKEY", "Turkey!", ["🥙", "☕", "🍯", "🍬"], "its coffee is on UNESCO's heritage list", "☕",
     "HARD", "No way!", "💀"),
    ("BEL", "BE", "BELGIUM", "Belgium!", ["🍟", "🧇", "🍫", "🍺"], "it says it invented French fries", "🍟",
     "INSANE", "Insane level!", "🧠"),
    ("KOR", "KR", "SOUTH KOREA", "South Korea!", ["🥬", "🌶", "🍚", "🥢"], "kimchi-making is on UNESCO's list", "🥬",
     "IMPOSSIBLE", "Impossible level!", "☠"),
    ("PER", "PE", "PERU", "Peru!", ["🐟", "🍋", "🥔", "🌽"], "it grows about 3,000 kinds of potato", "🥔", "BONUS",
     "Bonus! Only one percent!", "👑"),
]
INTRO_LINE = "Only one percent can guess them all!"
END_LINE = "How many did you get? Comment your score!"
ORBIT = ["🍕", "🍣", "🌮", "🥐", "🍜", "🥟", "🍛", "🍔", "🧇", "🥘"]


class FoodWall(lq.BrandWall):
    EMOJIS = ["🍕", "🍣", "🌮", "🥐", "🍜", "🥟", "🍛", "🧀", "🍩", "🍔"]


def fit(im, max_w=920):
    """Shrink an image so it (and its pop-in zoom) stays inside the screen."""
    return scaled(im, min(1.0, max_w / im.width))


def flag_img(code):
    return Image.open(os.path.join(FLAG_DIR, code + ".png")).convert("RGBA")


def draw_row(im, row, y, s=1.0, t=0.0, wobble=True):
    panel, sprites = row
    paste_center(im, scaled(panel, s), W / 2, y)
    for k, sp in enumerate(sprites):
        sk = s * (1 + (0.06 * math.sin(t * 9 + k) if wobble else 0))
        paste_center(im, scaled(sp, sk), W / 2 + (ge.slot_x(k) - W / 2) * s, y)


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    """6 beats. Cold open: a mystery clue slams in on frame one; montage of clues; titles over a globe with
    food orbiting it."""

    TEASE, MONTAGE = 10, (8, 6, 9, 7)

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 6 * B
        self.t1, self.t2 = 1.5 * B, 3.5 * B
        self.tease = ge.clue_row(ROUNDS[self.TEASE][4])
        self.cuts = [ge.clue_row(ROUNDS[k][4]) for k in self.MONTAGE]
        self.o1 = fit(rtext("ONLY 1% CAN GUESS", 100, fill=PINK, stroke=10))
        self.o2 = fit(join(rtext("THIS COUNTRY", 124, stroke=11), emoji("😳", 112), gap=12))
        self.q = rtext("?", 300, stroke=18)
        self.o3 = join(rtext("answer at the end", 60, fill=GOLD, stroke=7), emoji("👀", 64))
        self.m1 = fit(rtext("CAN YOU GUESS", 104, stroke=10))
        self.m2 = fit(rtext("ALL OF THEM?", 120, fill=CYAN, stroke=11))
        self.l1 = fit(rtext("GUESS THE COUNTRY", 112, fill=PINK, stroke=11), 900)
        self.l2 = fit(join(rtext("BY ITS FOOD", 140, stroke=13), emoji("🍽", 130), gap=16), 900)
        self.l3 = join(rtext("99% FAIL", 120, fill=GOLD, stroke=11), emoji("💀", 120))
        self.orbit = [emoji(e, 150) for e in ORBIT]
        self.burst = [emoji(e, 120) for e in ROUNDS[self.TEASE][4]]
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9),
                        (0.02, mq.sfx_glitch(), 0.5), (B, sfx_heartbeat(), 0.8), (B, mq.sfx_boom(), 0.5),
                        (self.t2, mq.sfx_boom(), 0.9), (self.t2, mv.sfx_whoosh(0.5), 0.6),
                        (4 * B, mv.sfx_pop(), 0.9), (4 * B, mq.sfx_boom(), 0.5),
                        (4.5 * B, mq.sfx_boom(), 0.7), (4.5 * B, mv.sfx_riser(1.5 * B), 0.7),
                        (6 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k in range(len(self.cuts)):
            at = self.t1 + k * 0.5 * B
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mq.sfx_glitch(), 0.35), (at, mv.sfx_click(), 0.7)]
        if tts:
            self.voices.append((0.04, tts.say(INTRO_LINE, speed=1.18)))

    def render(self, t):
        T = self.t0 + t
        bg = self.ui["bg"]
        if t < self.t1:                                           # cold open: everything readable on frame one
            im = bg.render(T, GOLD, strobe=beat_pulse(T))
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.5 * beat_pulse(T)))])
            for k, sp in enumerate(self.burst):                   # the clue's food bursts out on the beats
                for b in (0, 1):
                    tb = t - b * B
                    if 0 <= tb < 0.9:
                        ang = (k + 0.5 + b * 0.37) * math.pi / 2
                        r = 200 + 820 * ease_out_cubic(tb / 0.9)
                        paste_center(im, scaled(sp, 1 - 0.5 * tb).rotate(tb * 300, Image.BICUBIC, expand=True),
                                     W / 2 + r * math.cos(ang), 820 + r * math.sin(ang), 1 - tb / 0.9)
            s = 1 + 0.06 * (1 - ease_out_cubic(t / 0.2))
            paste_center(im, scaled(self.o1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 300)
            paste_center(im, scaled(self.o2, s).rotate(2, Image.BICUBIC, expand=True), W / 2, 440)
            draw_row(im, self.tease, 760, (1.03 - 0.07 * ease_out_cubic(t / 0.2)) * (1 + 0.03 * beat_pulse(T)), t)
            paste_center(im, scaled(self.q, 1 + 0.12 * math.sin(t * 12)).rotate(10 * math.sin(t * 6), Image.BICUBIC,
                                                                                   expand=True), W / 2, 1130)
            paste_center(im, self.o3, W / 2, 1460)
            im = shake(im, 28 * (1 - t / 0.3) if t < 0.3 else 0, t)
            im = rgb_split(im, 8 * (1 - clamp(t / 0.25)))
            return im
        if t < self.t2:                                           # rapid montage of clues
            k = min(len(self.cuts) - 1, int((t - self.t1) / (0.5 * B)))
            tc = t - self.t1 - k * 0.5 * B
            col = [PINK, CYAN, GOLD, mm.RED][k % 4]
            im = bg.render(T, col, strobe=1 - clamp(tc / 0.15))
            draw_row(im, self.cuts[k], 820, 1.04 - 0.08 * ease_out_cubic(tc / 0.15), t)
            s = 1 + 0.12 * (1 - ease_out_cubic((t - self.t1) / 0.15))
            paste_center(im, scaled(self.m1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 330)
            paste_center(im, scaled(self.m2, s).rotate(3, Image.BICUBIC, expand=True), W / 2, 480)
            im = rgb_split(im, 18 * (1 - clamp(tc / 0.12)))
            if tc < 0.06:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            return im
        tg = t - self.t2                                          # titles over a spinning globe with food orbiting
        gc = (540, 1270)
        R = 430 * (1 + 0.05 * beat_pulse(T)) * (1.25 - 0.25 * ease_out_cubic(clamp(tg / 0.3)))
        im = self.ui["big_globe"].render(G.unit(-30 + 70 * tg, 20), R, gc)
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 50)))
        for k, sp in enumerate(self.orbit):
            ang = k / len(self.orbit) * 2 * math.pi + tg * 1.6
            rx, ry = 560, 230
            x, y = gc[0] + rx * math.cos(ang), gc[1] + ry * math.sin(ang)
            front = math.sin(ang) > 0
            if front or True:
                sc = (0.75 + 0.35 * (math.sin(ang) + 1) / 2) * (1 + 0.1 * beat_pulse(T))
                paste_center(im, scaled(sp, sc).rotate(15 * math.sin(T * 3 + k), Image.BICUBIC, expand=True), x, y)
        b = int(tg / (0.5 * B))
        kk = (tg % (0.5 * B)) / (0.5 * B)
        slam = 1 + 0.35 * (1 - ease_out_cubic(kk / 0.4))
        paste_center(im, scaled(self.l1, (slam if b == 0 else 1.0) * (1 + 0.03 * beat_pulse(T))).rotate(
            -3, Image.BICUBIC, expand=True), W / 2, 330)
        if b >= 1:
            paste_center(im, scaled(self.l2, slam if b == 1 else 1.0).rotate(2, Image.BICUBIC, expand=True),
                         W / 2, 500)
        if b >= 2:
            paste_center(im, scaled(self.l3, slam if b == 2 else 1.0), W / 2, 670)
        im = shake(im, 22 * (1 - kk) if kk < 0.4 and b <= 2 else 0, t)
        if tg < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(160 * (1 - tg / 0.08)))))
        whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Round(mv.Scene):
    def __init__(self, idx, r, prev_tier, ui, tts):
        super().__init__()
        code, fcode, name, said, foods, fact, femoji, tier, prompt, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = FLY_BEATS
        self.dur = (f + (12 if self.bonus else 8) + (5 if self.cta else 0)) * B
        self.fly = f * B
        self.reveal = (f + (7 if self.bonus else 4)) * B
        self.count_beats = list(range(f + 2, f + 7)) if self.bonus else [f + 1, f + 2, f + 3]
        self.cta_at = 2 * B
        self.pop_at = [0.15 + k * 0.5 * B for k in range(4)]
        self.row = ge.clue_row(foods)
        world = ui["globe"].world
        self.target, self.Rt, self.rings = bq.view_for(world, code, fx=0.36, fy=0.34)
        self.lon0 = random.Random(idx * 7).uniform(-180, 180)
        self.flag = flag_img(fcode)
        self.cols = mm.flag_colours(self.flag)
        self.tiles = mm.Tiles(name, tier in ("INSANE", "IMPOSSIBLE", "BONUS"))
        art = ui["art"]
        lab = Image.new("RGBA", (PW, PH))
        nt = rtext(name, 64, stroke=6)
        lab.alpha_composite(nt, (40, PH - nt.height - 24))
        self.label = lab
        self.qmark = rtext("?", 240, stroke=16)
        self.hint = join(rtext("WHERE IS IT FROM?", 44, stroke=5), emoji("🌍", 46), gap=10)
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
        self.nums = {k: rtext(str(k), 230, fill=PINK if k == 1 else (255, 255, 255), stroke=16) for k in range(1, n + 1)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8)]
        for at in self.pop_at:
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mv.sfx_pop(), 0.8)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        self.sounds += [(self.reveal, mq.sfx_boom(), 0.9), (self.reveal, mv.sfx_whoosh(0.5), 0.7),
                        (self.reveal + 0.5, mv.sfx_ding(), 1.0), (self.reveal + 0.52, mq.sfx_pling(), 0.6),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        for i in range(len(self.tiles.pos)):
            self.sounds.append((self.reveal + 0.55 + 0.035 * i, mv.sfx_click(), 0.5))
        if tts:
            v = tts.say(prompt, speed=1.18)
            self.voices.append((0.12, v))
            if 0.12 + len(v) / SR > self.count_beats[0] * B + 0.1:
                print(f"warning: prompt {idx} runs into the countdown", flush=True)
            self.voices.append((self.reveal + 0.5, tts.say(said, speed=1.12)))
            if self.cta:
                self.voices.append((self.reveal + self.cta_at + 0.5, tts.say(CTA_LINE, speed=1.12)))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = self.reveal + self.cta_at + 0.5
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, mq.sfx_pling(), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        rr = random.Random(idx * 31)
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1350, -450), rr.randint(12, 26), rr.choice(self.cols),
                      rr.uniform(0, 3)) for _ in range(70)]

    def globe_panel(self, t, rv):
        spin = G.unit(self.lon0 + 22 * min(t, self.reveal), 12)
        if rv <= 0:
            c, R, hl, fa, lift = spin, SPIN_R * (1 + 0.03 * beat_pulse(self.t0 + t)), 0.0, 0.0, 0.0
        else:
            k = ease_in_out(clamp(rv / 0.5))
            c = G.slerp(spin, self.target, k)
            R = math.exp(math.log(SPIN_R) + (math.log(self.Rt) - math.log(SPIN_R)) * k)
            hl = clamp((rv - 0.4) / 0.15)
            fa = clamp((rv - 0.5) / 0.25)
            lift = 14 * ease_out_back(clamp((rv - 0.5) / 0.3))
        im = self.ui["globe"].render(c, R, (PW / 2, PH / 2), self.rings if rv > 0 else None, hl, self.flag, fa,
                                     lift=lift, halo=False)
        art = self.ui["art"]
        im.alpha_composite(art.shade)
        if rv > 0.5:
            lab = self.label.copy()
            lab.putalpha(lab.getchannel("A").point(lambda v: int(v * clamp((rv - 0.5) / 0.2))))
            im.alpha_composite(lab)
        im.alpha_composite(art.edge["gold" if rv > 0.5 else "white"])
        im.putalpha(art.mask)
        return im

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        rv5 = rv - 0.5                                            # the moment the globe lands
        on_beat = beat_pulse(T) if t > self.fly else 0.0
        im = self.ui["bg"].render(T, self.col, strobe=on_beat * 0.5 + (1 - clamp(rv5 / 0.25) if rv5 > 0 else 0),
                                  rays=0.55 + 0.45 * on_beat if rv5 < 0 else 1.0)
        if self.danger and 0 < t < self.reveal + 0.5:
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv5 > 0:
            im.alpha_composite(cq.speed_lines(1 - clamp(rv5 / 0.45), self.idx, (540, PANEL_Y)))
        d = ImageDraw.Draw(im)
        paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
        x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
        frac = 1.0 if t < self.fly else max(0.0, 1 - (t - self.fly) / (self.reveal - self.fly))
        d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
        colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
        if frac > 0.01:
            d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 11, fill=colr + (255,))
        paste_center(im, self.tag, x0 + self.tag.width / 2, 285)
        n = self.idx if rv5 > 0 else self.idx - 1
        if n > 0:
            sc = 1 + 0.5 * (1 - ease_out_cubic(rv5 / 0.25)) if 0 < rv5 < 0.25 else 1.0
            stk = self.streak[n]
            paste_center(im, scaled(stk, sc), x1 - stk.width / 2 + 10, 288)
        # food clues: the panel slides in, each emoji slams in on its half beat, then bounces
        panel, sprites = self.row
        kp = ease_out_back(clamp(t / 0.3), 1.5)
        if kp > 0.01:
            paste_center(im, scaled(panel, kp * (1 + 0.02 * on_beat)), W / 2 + (1 - kp) * 600, ROW_Y)
        for k, sp in enumerate(sprites):
            ke = (t - self.pop_at[k]) / 0.22
            if ke <= 0:
                continue
            s = (1.8 - 0.8 * ease_out_back(clamp(ke), 1.6)) if ke < 1 else 1.0
            bob = 1 + 0.07 * (beat_pulse(T) if (k + int(T / B)) % 2 == 0 else 0)
            if rv5 > 0:
                bob *= 1 + 0.2 * max(0.0, math.sin(math.pi * clamp((rv5 - 0.05 * k) / 0.35)))
            paste_center(im, scaled(sp, s * bob).rotate(6 * math.sin(T * 3 + k * 1.3), Image.BICUBIC, expand=True),
                         ge.slot_x(k), ROW_Y)
        # globe panel: spins with a "?", then whips to the country on the drop
        k_in = ease_out_back(clamp((t - 0.1) / 0.35), 1.4)
        if k_in > 0.01:
            gp = self.globe_panel(t, rv)
            s = k_in * (1 + (0.05 * (1 - ease_out_cubic(clamp(rv5 / 0.35))) if rv5 > 0 else 0.01 * on_beat))
            paste_center(im, scaled(gp, s), W / 2, PANEL_Y)
            counting = any(0 <= t - b * B < B for b in self.count_beats)
            if rv <= 0 and not counting:
                paste_center(im, scaled(self.qmark, k_in * (1 + 0.1 * math.sin(t * 10))).rotate(
                    8 * math.sin(t * 5), Image.BICUBIC, expand=True), W / 2, PANEL_Y - 20)
            if rv <= 0:
                paste_center(im, self.hint, W / 2, PANEL_Y + PH / 2 - 50, k_in)
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, PANEL_Y, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, PANEL_Y - 10,
                             a * 0.95)
        self.tiles.draw(im, t - self.fly - B, rv5)
        if rv5 > 0:
            for vx, vy, sz, cc, spin in self.conf:
                px, py = W / 2 + vx * rv5, PANEL_Y + vy * rv5 + 2400 * rv5 * rv5
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv5 * 9))
                    d = ImageDraw.Draw(im)
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            sk = ease_out_back((rv5 - 0.12) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv5 * 7), Image.BICUBIC, expand=True),
                             930, PANEL_Y + PH / 2 - 40)
            fk = ease_out_back((rv5 - 0.35) / 0.3)
            if fk > 0.01:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            fl = 1 - clamp(rv5 / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * fl))))
            im = shake(im, 30 * (1 - rv5 / 0.35) if rv5 < 0.35 else 0, t)
            if rv5 < 0.18:
                im = rgb_split(im, 16 * (1 - rv5 / 0.18))
        elif rv > 0:                                              # the whip to the country
            im = rgb_split(im, 14 * math.sin(math.pi * clamp(rv / 0.5)))
        else:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 12 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 8 * (1 - tb / 0.15))
        if self.cta and rv5 > self.cta_at:
            ct = rv5 - self.cta_at
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
        if t < 0.18:
            im = rgb_split(mm.zoom_blur(im, 1 - t / 0.18), 20 * (1 - t / 0.18))
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(mm.zoom_blur(im, out), 22 * out)
        return im


class Ending(bq.Ending):
    def __init__(self, ui, intro, tts):
        super().__init__(ui, intro, tts)
        tiers = [("0-3", "Picky eater", "🥦"), ("4-5", "Snack lover", "🍿"), ("6-7", "Foodie", "😋"),
                 ("8-9", "Master chef", "👨‍🍳"), ("10", "World chef", "🌍")]
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


def build(voice="am_adam", voice_pack=None):
    if voice_pack:
        tts = cq.Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    world = G.World()
    ui = {"bg": FoodWall(), "vig": [mc.red_vignette(i / 10) for i in range(11)], "art": bq.PanelArt(),
          "globe": G.GlobeRenderer(PW, PH, world), "big_globe": G.GlobeRenderer(W, H, world)}
    intro = Intro(ui, tts)
    scenes, prev = [intro], ROUNDS[0][7]
    for i, r in enumerate(ROUNDS, 1):
        scenes.append(Round(i, r, prev, ui, tts))
        prev = r[7]
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
    paste_center(im, fit(rtext("GUESS THE COUNTRY", 104, fill=PINK, stroke=10), 940).rotate(-3, Image.BICUBIC,
                                                                                          expand=True), W / 2, 270)
    paste_center(im, fit(join(rtext("BY ITS FOOD", 132, stroke=12), emoji("🍽", 120), gap=14), 940).rotate(
        2, Image.BICUBIC, expand=True), W / 2, 440)
    for k, gi in enumerate((1, 2, 10)):
        y = 790 + k * 330
        draw_row(im, ge.clue_row(ROUNDS[gi][4], 160), y, 0.94, 0.0, wobble=False)
        paste_center(im, rtext("?", 120, stroke=10).rotate((10, -10, 10)[k], Image.BICUBIC, expand=True),
                     (990, 90, 990)[k], y - 120)
    paste_center(im, join(rtext("99% FAIL", 96, fill=GOLD, stroke=9), emoji("💀", 98)), W / 2, 1760)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_food_country_quiz.mp4"))
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
        make_cover(ui, os.path.join(HERE, "food_country_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"foodc_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_foodc")
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
