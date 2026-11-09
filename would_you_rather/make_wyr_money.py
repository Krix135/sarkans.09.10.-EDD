#!/usr/bin/env python3
""""WOULD YOU RATHER? MONEY EDITION" Short (1080x1920), edited like the crazy quizzes.

Eight money dilemmas on a red / blue split screen. The narrator reads each one (the option being read
lights up), a 3-2-1 runs inside the OR badge on the beat, then the narrator's own pick gets a
"MY PICK" stamp with a cash burst, plus a surprising maths fact where there is one. No made-up
"% of people chose" numbers: viewers are asked to comment A or B instead. Money rain backdrop,
130 BPM phonk, glitches, shakes, RGB split, one like call-out and an ending that loops to the start.

    python3 make_wyr_money.py --voice-pack voice_packs/wyr_adam
    python3 make_wyr_money.py --stills 1,5,8
    python3 make_wyr_money.py --cover
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
    scaled, tt  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
PANEL_W, PANEL_H = 1000, 620
PANEL_Y = (640, 1330)             # centres of A (top) and B (bottom)
BADGE_Y = 985
RED_A, RED_B = (255, 70, 98), (196, 20, 62)
BLUE_A, BLUE_B = (60, 140, 255), (22, 70, 200)
ENTRY_BEATS = 2

QUESTIONS = [  # A text, A emoji, B text, B emoji, spoken question, pick (0/1/None), spoken pick, maths fact
    ("$1,000,000 right now", "💵", "A penny that doubles every day for 30 days", "🪙",
     "A million dollars right now, or a penny that doubles every day for a month?", 1,
     "Take the penny! It ends at over five million!", ("🤯", "Day 30: the penny is worth $5,368,709")),
    ("Billionaire, but no phone ever again", "📵", "Broke, but unlimited Wi-Fi", "📶",
     "Billionaire with no phone, or broke with unlimited Wi-Fi?", 0, "Billionaire. Easy.", None),
    ("$100 every time you sneeze", "🤧", "$1 for every step you take", "👟",
     "A hundred dollars every time you sneeze, or a dollar for every step?", 1, "Steps! Thousands every day!",
     ("👟", "Most people walk thousands of steps a day")),
    ("Free pizza for life", "🍕", "Free flights forever", "✈", "Free pizza for life, or free flights forever?", 1,
     "Free flights!", None),
    ("$50,000 every year, forever", "📅", "$1,000,000 today", "💰",
     "Fifty thousand dollars a year forever, or a million today?", 0, "Fifty K forever!",
     ("🧮", "$50,000 x 30 years = $1,500,000")),
    ("Famous, but poor", "🌟", "Rich, but nobody knows you", "🕶", "Famous but poor, or rich but nobody knows you?", 1,
     "Rich and unknown!", None),
    ("$1,000 a day, always in coins", "🪙", "$100 a day on a card", "💳",
     "A thousand dollars a day in coins, or a hundred on a card?", 0, "Coins! I'll carry them!", None),
    ("$10 million, but you can never leave your country", "🏠", "$1 million + free travel forever", "🌍",
     "Final one. Ten million, but you can never leave your country, or one million and free travel forever?", None,
     "Impossible! Comment your answer!", None),
]
INTRO_LINE = "Would you rather? Money edition! The last one is impossible!"
CTA_LINE = "Smash like if you agree so far!"
END_LINE = "Which one was the hardest? Comment below!"
CTA_AFTER = 3
ALL_LINES = [INTRO_LINE] + [x for q in QUESTIONS for x in (q[4], q[6])] + [CTA_LINE, END_LINE]


def sfx_coins():
    """A little cascade of coin clinks."""
    t = tt(0.7)
    out = np.zeros_like(t)
    r = random.Random(4)
    for k in range(9):
        st = k * 0.055 + r.uniform(0, 0.02)
        f = r.uniform(2600, 4200)
        tt_ = np.clip(t - st, 0, None)
        out += (t >= st) * (np.sin(2 * np.pi * f * tt_) + 0.5 * np.sin(2 * np.pi * f * 1.52 * tt_)) * np.exp(-tt_ * 28) * 0.35
    return np.tanh(out)


# ----------------------------------------------------------------------------
# backdrop: dark gradient with raining money
# ----------------------------------------------------------------------------
class MoneyRain:
    def __init__(self):
        rnd = random.Random(7)
        self.base = mv.vgradient(W, H, (10, 14, 34), (24, 10, 44)).convert("RGBA")
        g = mv.soft_circle(1300, (60, 200, 120, 70), 260)
        paste_center(self.base, g, W / 2, BADGE_Y)
        sprites = []
        for e in ("💵", "💰", "🪙", "💸", "💵", "💵"):
            for s in (70, 96, 124):
                im = emoji(e, s)
                sprites.append(im)
        self.items = []
        for _ in range(46):
            sp = rnd.choice(sprites)
            depth = rnd.uniform(0.4, 1.0)
            spr = scaled(sp, depth)
            a = int(110 * depth)
            spr.putalpha(spr.getchannel("A").point(lambda v, a=a: v * a // 255))
            frames = [spr.rotate(rnd.uniform(-180, 180) + k * 15, Image.BICUBIC, expand=True) for k in range(6)]
            self.items.append((rnd.uniform(0, W), rnd.uniform(0, H + 200), 120 + 260 * depth, frames,
                               rnd.uniform(0, 6.28)))
        ys, xs = np.mgrid[0:H, 0:W]
        dd = np.sqrt(((xs - W / 2) / (W * 0.72)) ** 2 + ((ys - H / 2) / (H * 0.62)) ** 2)
        a = np.zeros((H, W, 4), np.uint8)
        a[..., 3] = (np.clip(dd - 0.62, 0, 1) * 330).clip(0, 170).astype(np.uint8)
        self.vig = Image.fromarray(a, "RGBA")

    def render(self, T, strobe=0.0, tint=None):
        im = self.base.copy()
        for x, y, v, frames, ph in self.items:
            yy = (y + T * v) % (H + 300) - 150
            xx = x + 30 * math.sin(T * 1.3 + ph)
            fr = frames[int(T * 5 + ph * 3) % len(frames)]
            im.alpha_composite(fr, (int(xx - fr.width / 2), int(yy - fr.height / 2)))
        im.alpha_composite(self.vig)
        if tint is not None:
            im.alpha_composite(Image.new("RGBA", (W, H), tint + (40,)))
        if strobe > 0.01:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(40 * strobe))))
        return im


# ----------------------------------------------------------------------------
# panels, badge, stamps
# ----------------------------------------------------------------------------
def wrap_lines(text, size, width):
    f = rfont(size)
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if f.getlength(t) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def text_block(text, width=880, max_lines=3, start=74):
    size = start
    while True:
        lines = wrap_lines(text, size, width)
        if len(lines) <= max_lines or size <= 44:
            break
        size -= 2
    imgs = [rtext(ln, size, stroke=7) for ln in lines]
    step = int(size * 1.12)
    out = Image.new("RGBA", (max(i.width for i in imgs), step * len(imgs) + 20))
    for k, i in enumerate(imgs):
        paste_center(out, i, out.width / 2, step * (k + 0.5) + 10)
    return out


def panel(letter, text, emo, top, bot):
    p = Image.new("RGBA", (PANEL_W + 40, PANEL_H + 40))
    sh = Image.new("L", p.size)
    ImageDraw.Draw(sh).rounded_rectangle((20, 32, 20 + PANEL_W, 32 + PANEL_H), 64, fill=170)
    p.paste(Image.new("RGBA", p.size, (0, 0, 10, 255)), (0, 0), sh.filter(ImageFilter.GaussianBlur(16)))
    face = mv.vgradient(PANEL_W, PANEL_H, top, bot).convert("RGBA")
    sheen = Image.new("RGBA", face.size)
    d = ImageDraw.Draw(sheen)
    for k in range(-PANEL_H, PANEL_W, 110):                     # faint diagonal sheen stripes
        d.polygon([(k, PANEL_H), (k + 44, PANEL_H), (k + 44 + PANEL_H, 0), (k + PANEL_H, 0)],
                  fill=(255, 255, 255, 20))
    face.alpha_composite(sheen)
    m = Image.new("L", (PANEL_W * 2, PANEL_H * 2))
    ImageDraw.Draw(m).rounded_rectangle((0, 0, PANEL_W * 2 - 1, PANEL_H * 2 - 1), 128, fill=255)
    face.putalpha(m.resize((PANEL_W, PANEL_H), Image.LANCZOS))
    edge = Image.new("RGBA", (PANEL_W, PANEL_H))
    ImageDraw.Draw(edge).rounded_rectangle((3, 3, PANEL_W - 4, PANEL_H - 4), 62, outline=(255, 255, 255, 230), width=7)
    face.alpha_composite(edge)
    badge = mv.circle(100, (255, 255, 255, 255))
    ImageDraw.Draw(badge).text((50, 52), letter, font=rfont(64), fill=bot, anchor="mm")
    face.alpha_composite(badge, (34, 30))
    p.alpha_composite(face, (20, 20))
    return p


def stamp(text, col, size=86, ang=-12):
    t = rtext(text, size, fill=col, stroke=0)
    pad = 30
    s = Image.new("RGBA", (t.width + 2 * pad, t.height + 2 * pad))
    d = ImageDraw.Draw(s)
    d.rounded_rectangle((6, 6, s.width - 7, s.height - 7), 24, fill=(255, 255, 255, 240), outline=col + (255,),
                        width=10)
    s.alpha_composite(t, (pad, pad))
    return s.rotate(ang, Image.BICUBIC, expand=True)


def fact_card(emo, text):
    body = join(emoji(emo, 64), text_block(text, 760, 2, 52), gap=16)
    card = rounded_card(body.width + 70, body.height + 40, 46, (255, 214, 10, 255), outline=INK + (255,), width=6)
    paste_center(card, body, card.width / 2, card.height / 2)
    return card


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 7 * B
        self.l1 = rtext("WOULD YOU", 150, stroke=13)
        self.l2 = rtext("RATHER?", 200, fill=GOLD, stroke=16)
        self.l3 = join(rtext("MONEY EDITION", 96, fill=(90, 230, 140), stroke=9), emoji("💰", 100))
        self.l4a = rtext("THE LAST ONE IS", 80, stroke=8)
        self.l4 = join(rtext("IMPOSSIBLE", 104, fill=PINK, stroke=10), emoji("💀", 104), gap=14)
        self.cash = [emoji(e, 260) for e in ("💵", "💰", "🪙", "💸")]
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_coins(), 0.8)]
        for k in range(1, 4):
            self.sounds += [(k * B, mq.sfx_boom(), 0.7), (k * B, mv.sfx_pop(), 0.8)]
        self.sounds += [(4 * B, sfx_coins(), 0.8), (5 * B, mv.sfx_riser(1.6 * B), 0.7),
                        (7 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        if tts:
            self.voices.append((0.05, tts.say(INTRO_LINE, speed=1.15)))

    def render(self, t):
        T = self.t0 + t
        im = self.ui["bg"].render(T * 2.2, strobe=beat_pulse(T))
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 20, 60)))
        for k, c in enumerate(self.cash):                         # cash bursts behind the title on the beats
            tb = t - k * B
            if tb > 0:
                ang = k * 1.6 + 0.7
                r = 260 + 900 * ease_out_cubic(clamp(tb / 0.9))
                x, y = W / 2 + r * math.cos(ang), 760 + r * math.sin(ang) * 0.8
                paste_center(im, scaled(c, 1 - 0.4 * clamp(tb / 0.9)).rotate(tb * 200, Image.BICUBIC, expand=True),
                             x, y, 1 - clamp((tb - 0.5) / 0.4))
        b = int(t / (0.5 * B))
        kk = (t % (0.5 * B)) / (0.5 * B)
        slam = 1 + 0.4 * (1 - ease_out_cubic(kk / 0.4))
        pulse = 1 + 0.04 * beat_pulse(T)
        paste_center(im, scaled(self.l1, (slam if b == 0 else 1.0) * pulse).rotate(-3, Image.BICUBIC, expand=True),
                     W / 2, 600)
        if b >= 1:
            paste_center(im, scaled(self.l2, (slam if b == 1 else 1.0) * pulse).rotate(3, Image.BICUBIC, expand=True),
                         W / 2, 790)
        if b >= 3:
            paste_center(im, scaled(self.l3, slam if b == 3 else 1.0), W / 2, 1000)
        if b >= 5:
            paste_center(im, scaled(self.l4a, slam if b == 5 else 1.0), W / 2, 1160)
        if b >= 6:
            paste_center(im, scaled(self.l4, (slam if b == 6 else 1.0) * (1 + 0.05 * math.sin(t * 14))), W / 2, 1280)
        im = shake(im, 24 * (1 - kk) if kk < 0.4 and b in (0, 1, 3, 5, 6) else 0, t)
        im = rgb_split(im, 12 * (1 - clamp(t / 0.25)))
        whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Question(mv.Scene):
    def __init__(self, idx, q, ui, tts):
        super().__init__()
        a_txt, a_emo, b_txt, b_emo, spoken, pick, said, fact = q
        self.idx, self.ui, self.pick = idx, ui, pick
        self.final = idx == len(QUESTIONS)
        self.cta = idx == CTA_AFTER
        f = ENTRY_BEATS
        v_q = tts.say(spoken, speed=1.08) if tts else None
        v_p = tts.say(said, speed=1.1) if tts else None
        v_c = tts.say(CTA_LINE, speed=1.1) if (tts and self.cta) else None
        q_len = len(v_q) / SR if v_q is not None else 3.5
        p_len = len(v_p) / SR if v_p is not None else 1.2
        c_len = len(v_c) / SR if v_c is not None else 2.0
        self.read = (0.15, 0.15 + q_len)
        c0 = max(f + 4, math.ceil((self.read[1] + 0.25) / B))
        n = 3
        self.count_beats = list(range(c0, c0 + n))
        self.fly = f * B
        self.reveal = (c0 + n) * B
        hold = max(4, math.ceil((0.1 + p_len + 0.45) / B))
        if fact:
            hold = max(hold, 5)
        self.cta_at = max(3, math.ceil((0.1 + p_len + 0.3) / B)) * B
        if self.cta:
            hold = max(hold, math.ceil((self.cta_at + c_len + 0.5) / B))
        self.dur = (c0 + n + hold) * B
        self.panels = [panel("A", a_txt, a_emo, RED_A, RED_B), panel("B", b_txt, b_emo, BLUE_A, BLUE_B)]
        self.emos = [emoji(a_emo, 230), emoji(b_emo, 230)]
        self.texts = [text_block(a_txt), text_block(b_txt)]
        self.dim = Image.new("RGBA", self.panels[0].size)
        ImageDraw.Draw(self.dim).rounded_rectangle((20, 20, 20 + PANEL_W, 20 + PANEL_H), 64, fill=(5, 0, 20, 150))
        self.pick_stamp = stamp("MY PICK", (30, 170, 80), 92)
        self.decide = stamp("YOU DECIDE", PINK, 84, ang=-6)
        self.fact = fact_card(*fact) if fact else None
        self.badge = mv.circle(190, (255, 255, 255, 255))
        ImageDraw.Draw(self.badge).text((95, 98), "OR", font=rfont(84), fill=INK, anchor="mm")
        self.ring = mv.circle(230, GOLD + (255,))
        self.nums = {k: rtext(str(k), 150, fill=PINK if k == 1 else INK, stroke=0) for k in range(1, 4)}
        self.counter = rtext(f"{idx}/{len(QUESTIONS)}", 46, stroke=5)
        self.title = join(rtext("WOULD YOU RATHER", 54, stroke=6), emoji("💰", 54), gap=10)
        self.banner = join(rtext("FINAL ONE", 110, fill=PINK, stroke=11), emoji("💀", 110)) if self.final else None
        self.comment = join(rtext("comment A or B", 50, stroke=5), emoji("👇", 52), gap=10)
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (0.12, mv.sfx_whoosh(0.4), 0.6), (0.3, mv.sfx_pop(), 0.7),
                        (0.45, mv.sfx_pop(), 0.7)]
        if self.final:
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.7), (0.05, sfx_heartbeat(), 0.9)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.final:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        self.sounds += [(self.reveal, mq.sfx_boom(), 0.9), (self.reveal, mv.sfx_ding(), 1.0),
                        (self.reveal + 0.04, sfx_coins(), 0.8), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        if self.fact:
            self.sounds.append((self.reveal + 0.45, mv.sfx_pop(), 0.8))
        if tts:
            self.voices.append((self.read[0], v_q))
            self.voices.append((self.reveal + 0.1, v_p))
            if self.cta:
                self.voices.append((self.reveal + self.cta_at, v_c))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext("AGREE SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = self.reveal + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, mq.sfx_pling(), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        r = random.Random(idx * 17)
        self.burst = [(r.uniform(0, 2 * math.pi), r.uniform(500, 1300), r.choice(ui["cash"]), r.uniform(-400, 400))
                      for _ in range(22)]

    def reading(self, t):
        """Which option the narrator is reading (0 = A, 1 = B), or None."""
        a, b = self.read
        if not a <= t <= b:
            return None
        return 0 if t < a + 0.47 * (b - a) else 1

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        on_beat = beat_pulse(T) if t > self.fly else 0.0
        tint = (120, 0, 30) if self.final and rv < 0 else None
        im = self.ui["bg"].render(T, strobe=on_beat * 0.5 + (1 - clamp(rv / 0.25) if rv > 0 else 0), tint=tint)
        if self.final and 0 < t < self.reveal:
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        # top bar: title, counter, timer
        paste_center(im, self.title, W / 2, 200)
        paste_center(im, self.counter, 100, 270)
        d = ImageDraw.Draw(im)
        x0, x1, y, bh = 180, 1000, 270, 20
        frac = 1.0 if t < self.fly else max(0.0, 1 - (t - self.fly) / (self.reveal - self.fly))
        d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
        colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
        if frac > 0.01:
            d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 10, fill=colr + (255,))
        reading = self.reading(t)
        for side in (0, 1):
            k_in = clamp((t - side * 0.12) / 0.4)
            if k_in <= 0:
                continue
            dx = (1 - ease_out_back(k_in, 1.3)) * (1200 if side == 0 else -1200)
            s = 1.0
            if rv < 0:
                s *= 1 + 0.015 * on_beat
                if reading == side:
                    s *= 1.035
            elif self.pick is not None:
                s *= (1 + 0.06 * (1 - ease_out_cubic(clamp(rv / 0.35)))) if side == self.pick else 0.96
            p = self.panels[side]
            pi = scaled(p, s)
            cx, cy = W / 2 + dx, PANEL_Y[side]
            paste_center(im, pi, cx, cy)
            # emoji and text on the panel (emoji bounces on the beat, wiggles while read)
            ke = ease_out_back(clamp((t - 0.25 - side * 0.12) / 0.3), 2.0)
            if ke > 0.01:
                wig = 8 * math.sin(T * 14) if reading == side else 4 * math.sin(T * 3 + side)
                paste_center(im, scaled(self.emos[side], ke * s * (1 + 0.07 * on_beat)).rotate(wig, Image.BICUBIC,
                                                                                             expand=True),
                             cx, cy - 120 * s)
            paste_center(im, scaled(self.texts[side], s), cx, cy + 150 * s)
            if rv > 0 and self.pick is not None and side != self.pick:
                paste_center(im, scaled(self.dim, s), cx, cy, clamp(rv / 0.2))
            if rv > 0 and side == self.pick:
                ks = ease_out_back(clamp((rv - 0.05) / 0.25), 2.4)
                if ks > 0.01:
                    paste_center(im, scaled(self.pick_stamp, 1.6 - 0.6 * ks), cx + 300, cy - 210, min(1.0, ks))
        # OR badge with the 3-2-1 inside, gold ring pulsing on the beat
        if t > 0.35:
            kb = ease_out_back(clamp((t - 0.35) / 0.3), 2.0) * (1 + 0.08 * on_beat)
            fade = 1 - clamp(rv / 0.2) if rv > 0 else 1.0
            if fade > 0.01:
                paste_center(im, scaled(self.ring, kb * (1 + 0.06 * math.sin(T * 6))), W / 2, BADGE_Y, fade)
                badge = self.badge.copy()
                for j, b in enumerate(self.count_beats):
                    tb = t - b * B
                    if 0 <= tb < B:
                        badge = mv.circle(190, (255, 255, 255, 255))
                        num = self.nums[len(self.count_beats) - j]
                        paste_center(badge, scaled(num, 1.25 - 0.25 * ease_out_cubic(tb / 0.12)), 95, 98)
                paste_center(im, scaled(badge, kb), W / 2, BADGE_Y, fade)
        if self.banner is not None and 0.05 < t < self.fly + 0.6:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly - 0.3) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, BADGE_Y, a)
        if rv > 0:
            src_y = PANEL_Y[self.pick] if self.pick is not None else BADGE_Y
            for ang, sp, spr, spin in self.burst:                # cash flies out of the pick
                k = clamp(rv / 1.2)
                x = W / 2 + math.cos(ang) * sp * k
                y = src_y + math.sin(ang) * sp * k * 0.8 + 900 * k * k
                if k < 1:
                    paste_center(im, spr.rotate(spin * k, Image.BICUBIC, expand=True), x, y, 1 - k)
            if self.pick is None:
                kd = ease_out_back(clamp(rv / 0.25), 2.2)
                paste_center(im, scaled(self.decide, kd * (1 + 0.04 * beat_pulse(T))), W / 2, BADGE_Y)
            cta_on = self.cta and rv > self.cta_at
            if self.fact is not None and not cta_on:
                kf = ease_out_back(clamp((rv - 0.45) / 0.3), 1.8)
                if kf > 0.01:
                    paste_center(im, scaled(self.fact, kf * (1 + 0.015 * beat_pulse(T))), W / 2, BADGE_Y)
            elif self.pick is not None and not cta_on:
                kc = ease_out_back(clamp((rv - 0.5) / 0.3), 1.8)
                if kc > 0.01:
                    paste_center(im, scaled(self.comment, kc), W / 2, BADGE_Y)
            if cta_on:
                ct = rv - self.cta_at
                k = ease_out_back(ct / 0.3, 2.0) * (1 - ease_in_cubic(clamp((t - (self.dur - 0.45)) / 0.25)))
                if k > 0.01:
                    card = self.cta_card.copy()
                    tap = 1 - 0.18 * math.sin(math.pi * clamp((ct - 0.45) / 0.2))
                    th = scaled(self.thumb, tap * (1 + 0.08 * beat_pulse(T))).rotate(10 * math.sin(ct * 7),
                                                                                     Image.BICUBIC, expand=True)
                    paste_center(card, th, 98, 98)
                    paste_center(im, scaled(card, k * (1 + 0.025 * beat_pulse(T))).rotate(-2, Image.BICUBIC,
                                                                                         expand=True), W / 2, BADGE_Y)
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
        if self.final and t < 0.35:
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
        logo = Image.open(brand.round_logo()).convert("RGBA").resize((130, 130), Image.LANCZOS)
        self.brand = join(logo, rtext(brand.NAME, 64, stroke=6), gap=18)
        self.t1 = rtext("WHICH ONE WAS", 104, stroke=10)
        self.t2 = rtext("THE HARDEST?", 124, fill=GOLD, stroke=11)
        self.cta = join(rtext("comment below", 70, stroke=7), emoji("👇", 76))
        self.sub = join(rtext("more would you rather", 56, fill=CYAN, stroke=6), emoji("🔔", 58))
        self.sounds += [(0.0, mv.sfx_whoosh(0.8), 0.7), (B, mq.sfx_levelup(), 0.9), (2 * B, sfx_coins(), 0.7),
                        (3 * B, mv.sfx_pop(), 0.8), (4 * B, mv.sfx_pop(), 0.8)]
        if tts:
            self.voices.append((0.3, tts.say(END_LINE, speed=1.1)))

    def render(self, t):
        T = self.t0 + t
        im = self.ui["bg"].render(T, strobe=0.35 * beat_pulse(T))
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        a = 1 - out
        im.alpha_composite(Image.new("RGBA", (W, H), (8, 4, 24, int(140 * clamp((t - 0.2) / 0.3) * a))))
        paste_center(im, self.brand, W / 2, 420, clamp((t - B) / 0.2) * a)
        paste_center(im, scaled(self.t1, ease_out_back((t - 1.2 * B) / 0.25)), W / 2, 700, a)
        paste_center(im, scaled(self.t2, ease_out_back((t - 1.8 * B) / 0.25) * (1 + 0.04 * beat_pulse(T))),
                     W / 2, 860, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 3 * B) / 0.25) * (1 + 0.03 * math.sin(t * 8))),
                     W / 2, 1080, a)
        paste_center(im, scaled(self.sub, ease_out_back((t - 4 * B) / 0.25)), W / 2, 1220, a)
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
    ui = {"bg": MoneyRain(), "vig": [mc.red_vignette(i / 10) for i in range(11)],
          "cash": [emoji(e, s) for e in ("💵", "🪙", "💰", "💸") for s in (90, 120)]}
    intro = Intro(ui, tts)
    scenes = [intro] + [Question(i, q, ui, tts) for i, q in enumerate(QUESTIONS, 1)]
    scenes.append(Ending(ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    im = ui["bg"].render(3.0)
    q = QUESTIONS[0]
    paste_center(im, panel("A", q[0], q[1], RED_A, RED_B), W / 2, 1040)
    paste_center(im, emoji(q[1], 230), W / 2, 920)
    paste_center(im, text_block(q[0]), W / 2, 1190)
    paste_center(im, panel("B", q[2], q[3], BLUE_A, BLUE_B), W / 2, 1600)
    paste_center(im, emoji(q[3], 200), W / 2, 1500)
    paste_center(im, text_block(q[2]), W / 2, 1700)
    paste_center(im, rtext("WOULD YOU", 140, stroke=12).rotate(-3, Image.BICUBIC, expand=True), W / 2, 230)
    paste_center(im, rtext("RATHER?", 190, fill=GOLD, stroke=15).rotate(3, Image.BICUBIC, expand=True), W / 2, 420)
    paste_center(im, join(rtext("MONEY EDITION", 84, fill=(90, 230, 140), stroke=8), emoji("💰", 88)), W / 2, 610)
    badge = mv.circle(190, (255, 255, 255, 255))
    ImageDraw.Draw(badge).text((95, 98), "OR", font=rfont(84), fill=INK, anchor="mm")
    paste_center(im, mv.circle(230, GOLD + (255,)), W / 2, 1320)
    paste_center(im, badge, W / 2, 1320)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_wyr_money.mp4"))
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
        make_cover(ui, os.path.join(HERE, "wyr_money_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"wyr_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_wyr")
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
