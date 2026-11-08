#!/usr/bin/env python3
""""ONLY REAL GTA FANS GET 10/10" multiple-choice quiz Short (1080x1920), edited like the crazy map quiz.

Ten questions plus a bonus about GTA 6 and the earlier games, four answers each; the narrator reads
every question, a 3-2-1 runs on the beat, then the right answer lights up green on the drop.
Original neon-sunset beach backdrop (synthwave sun, palms, skyline, sea reflections, a scrolling
grid floor) - no game footage, art or logos. 130 BPM phonk, level banners, glitches, shakes,
RGB split, streak counter, one "like this video" call-out and a looping ending.

    python3 make_gta_quiz.py --voice-pack voice_packs/gta_adam,voice_packs/map3_adam
    python3 make_gta_quiz.py --stills 1,5,8
    python3 make_gta_quiz.py --cover
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
TIERS = mc.TIERS
GREEN = (46, 204, 113)
CARD_Y, EMOJI_Y, NUM_Y = 470, 765, 765
PILL_Y = [995, 1135, 1275, 1415]
PILL_W, PILL_H = 900, 116
CTA_AFTER, CTA_LINE, CTA_Y = (3,), mc.CTA_LINE, 1590
ENTRY_BEATS = 2

QUESTIONS = [  # shown, spoken, answers, right one, spoken answer, emoji, tier, reaction sticker
    ("Which city is GTA 6 set in?", "Which city is GTA 6 set in?",
     ["Los Santos", "Vice City", "Liberty City", "San Fierro"], 1, "Vice City!", "🌴", "EASY", "😎"),
    ("Who are GTA 6's two main characters?", "Who are GTA 6's two main characters?",
     ["Michael & Trevor", "Tommy & Lance", "Lucia & Jason", "Niko & Roman"], 2, "Lucia and Jason!", "👫", "EASY", "🔥"),
    ("Which company makes GTA?", "Which company makes GTA?",
     ["Rockstar Games", "Ubisoft", "EA", "Activision"], 0, "Rockstar Games!", "🎮", "EASY", "🤔"),
    ("What year did GTA 5 come out?", "What year did GTA 5 come out?",
     ["2010", "2013", "2015", "2017"], 1, "Twenty thirteen!", "📅", "HARD", "😳"),
    ("Who is the hero of GTA San Andreas?", "Who is the hero of San Andreas?",
     ["Franklin", "Niko Bellic", "Claude", "CJ"], 3, "CJ!", "🚲", "HARD", "🤯"),
    ("Which state is GTA 6 set in?", "Which state is GTA 6 set in?",
     ["San Andreas", "Leonida", "Alderney", "North Yankton"], 1, "Leonida!", "🗺", "HARD", "🔥"),
    ("Who is the hero of GTA Vice City?", "Who is the hero of Vice City?",
     ["Toni Cipriani", "Victor Vance", "Tommy Vercetti", "Huang Lee"], 2, "Tommy Vercetti!", "🕶", "INSANE", "😱"),
    ("Which song plays in GTA 6's first trailer?", "Which song plays in GTA 6's first trailer?",
     ["Tom Petty - Love Is a Long Road", "Pointer Sisters - Hot Together", "Michael Jackson - Billie Jean",
      "Toto - Africa"], 0, "Love Is a Long Road, by Tom Petty!", "🎵", "INSANE", "💀"),
    ("Which of these places is in GTA 6?", "Which of these places is in GTA 6?",
     ["Paleto Bay", "Port Gellhorn", "Sandy Shores", "Bohan"], 1, "Port Gellhorn!", "📍", "INSANE", "🧠"),
    ("How many views did GTA 6's first trailer get in one day?",
     "How many views did the first trailer get in one day?",
     ["10 million", "40 million", "90+ million", "500 million"], 2, "Over ninety million!", "📈", "IMPOSSIBLE", "☠"),
    ("What year did the very first GTA come out?", "Bonus! What year did the very first GTA come out?",
     ["1994", "1997", "2001", "2004"], 1, "Nineteen ninety-seven!", "🕹", "BONUS", "👑"),
]
INTRO_LINE = "Only real GTA fans get ten out of ten!"
END_LINE = "How many did you get? Comment your score!"


# ----------------------------------------------------------------------------
# neon-sunset backdrop (original art: synthwave sun, palms, skyline, sea, grid)
# ----------------------------------------------------------------------------
HORIZON, GRID_TOP = 1180, 1460
SUN = (540, 1010, 330)


def palm(h, lean, sway):
    """A palm-tree silhouette (trunk + fronds) as an RGBA image, about h px tall."""
    S = int(h * 1.4)
    im = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(im)
    col = (24, 6, 40, 255)
    bx, by = S * 0.5, S - 4
    pts_l, pts_r = [], []
    top = None
    for i in range(41):
        k = i / 40
        x = bx + lean * h * k ** 1.8 + sway * h * 0.05 * k ** 2
        y = by - h * k
        w = 26 * (1 - 0.55 * k) * h / 700
        pts_l.append((x - w, y))
        pts_r.append((x + w, y))
        top = (x, y)
    d.polygon(pts_l + pts_r[::-1], fill=col)
    for i in range(0, 40, 3):                      # trunk rings
        k = i / 40
        x = bx + lean * h * k ** 1.8 + sway * h * 0.05 * k ** 2
        y = by - h * k
        w = 26 * (1 - 0.55 * k) * h / 700
        d.line([(x - w, y), (x + w, y - 4)], fill=(60, 20, 70, 255), width=3)
    tx, ty = top
    for j, a in enumerate((-170, -140, -110, -70, -40, -10, 15, 200)):
        a = math.radians(a + sway * 6)
        L = h * (0.42 + 0.06 * math.sin(j * 2.1))
        pts_a, pts_b = [], []
        for i in range(21):
            k = i / 20
            droop = 0.55 * k * k * L
            x = tx + math.cos(a) * L * k
            y = ty + math.sin(a) * L * k + droop
            w = math.sin(math.pi * k) * L * 0.08
            nx, ny = -math.sin(a), math.cos(a)
            pts_a.append((x + nx * w, y + ny * w))
            pts_b.append((x - nx * w, y - ny * w))
        d.polygon(pts_a + pts_b[::-1], fill=col)
    d.ellipse((tx - 16 * h / 700, ty - 12 * h / 700, tx + 16 * h / 700, ty + 18 * h / 700), fill=col)
    return im


class Neon:
    def __init__(self):
        rnd = random.Random(9)
        ys = np.arange(H, dtype=np.float32)[:, None]
        stops = [(0, (18, 4, 46)), (520, (70, 12, 96)), (900, (200, 36, 120)), (HORIZON, (255, 140, 70))]
        sky = np.zeros((H, W, 3), np.float32)
        for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
            m = (ys >= y0) & (ys < y1)
            k = ((ys - y0) / (y1 - y0)).clip(0, 1)
            col = np.array(c0) + (np.array(c1) - np.array(c0)) * k[..., None]
            sky = np.where(m[..., None], col, sky)
        im = Image.fromarray(sky.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
        d = ImageDraw.Draw(im)
        for _ in range(160):                               # stars
            x, y, s = rnd.uniform(0, W), rnd.uniform(0, 650), rnd.uniform(1, 2.6)
            d.ellipse((x - s, y - s, x + s, y + s), fill=(255, 255, 255, int(rnd.uniform(80, 230))))
        # synthwave sun with cut stripes
        cx, cy, r = SUN
        sun = Image.new("RGBA", (2 * r, 2 * r))
        sa = np.zeros((2 * r, 2 * r, 4), np.uint8)
        yy, xx = np.mgrid[0:2 * r, 0:2 * r]
        inside = (xx - r) ** 2 + (yy - r) ** 2 <= r * r
        k = yy / (2 * r)
        sa[..., 0] = 255
        sa[..., 1] = (230 - 170 * k).clip(0, 255).astype(np.uint8)
        sa[..., 2] = (90 + 60 * k).astype(np.uint8)
        band = np.zeros_like(inside)
        for i in range(7):
            y0 = r + 30 + i * 46
            band |= (yy >= y0) & (yy < y0 + 6 + i * 3)
        sa[..., 3] = np.where(inside & ~band, 255, 0)
        sun = Image.fromarray(sa, "RGBA")
        glow = mv.soft_circle(2 * r + 300, (255, 120, 140, 150), 90)
        paste_center(im, glow, cx, cy)
        paste_center(im, sun, cx, cy)
        # skyline on the horizon
        x = -10
        while x < W + 10:
            bw, bh = rnd.uniform(36, 90), rnd.uniform(40, 230) * (1.4 if 380 < x < 700 else 1.0)
            d.rectangle((x, HORIZON - bh, x + bw, HORIZON), fill=(40, 10, 60, 255))
            for wy in range(int(HORIZON - bh + 12), HORIZON - 8, 16):
                for wx in range(int(x + 8), int(x + bw - 8), 14):
                    if rnd.random() < 0.3:
                        c = rnd.choice([(255, 90, 200), (90, 230, 255), (255, 210, 120)])
                        d.rectangle((wx, wy, wx + 5, wy + 7), fill=c + (200,))
            x += bw + rnd.uniform(2, 10)
        # sea
        sea = np.zeros((GRID_TOP - HORIZON, W, 4), np.uint8)
        k = np.linspace(0, 1, GRID_TOP - HORIZON)[:, None]
        sea[..., 0] = (60 - 40 * k).astype(np.uint8)
        sea[..., 1] = (20 + 10 * k).astype(np.uint8)
        sea[..., 2] = (110 - 30 * k).astype(np.uint8)
        sea[..., 3] = 255
        im.paste(Image.fromarray(sea, "RGBA"), (0, HORIZON))
        # grid floor
        floor = np.zeros((H - GRID_TOP, W, 4), np.uint8)
        k = np.linspace(0, 1, H - GRID_TOP)[:, None]
        floor[..., 0] = (34 - 20 * k).astype(np.uint8)
        floor[..., 1] = 4
        floor[..., 2] = (52 - 26 * k).astype(np.uint8)
        floor[..., 3] = 255
        im.paste(Image.fromarray(floor, "RGBA"), (0, GRID_TOP))
        d = ImageDraw.Draw(im)
        vx, vy = W / 2, HORIZON - 90
        for i in range(-12, 13):                            # grid rays
            bx = W / 2 + i * 150
            kk = (GRID_TOP - vy) / (H - vy)
            d.line([(vx + (bx - vx) * kk, GRID_TOP), (bx, H)], fill=(255, 60, 200, 200), width=3)
        d.line([(0, GRID_TOP), (W, GRID_TOP)], fill=(255, 120, 230, 255), width=4)
        self.base = im
        self.vy = vy
        self.reflect = [self._reflection(rnd) for _ in range(8)]
        self.palms = [(palm(760, 0.16, math.sin(i / 8 * 2 * math.pi)), palm(640, -0.13, math.cos(i / 8 * 2 * math.pi)))
                      for i in range(8)]
        ys2, xs2 = np.mgrid[0:H, 0:W]
        dd = np.sqrt(((xs2 - W / 2) / (W * 0.72)) ** 2 + ((ys2 - H / 2) / (H * 0.62)) ** 2)
        a = np.zeros((H, W, 4), np.uint8)
        a[..., :3] = (20, 0, 30)
        a[..., 3] = (np.clip(dd - 0.62, 0, 1) * 330).clip(0, 170).astype(np.uint8)
        self.vig = Image.fromarray(a, "RGBA")

    def _reflection(self, rnd):
        im = Image.new("RGBA", (W, GRID_TOP - HORIZON))
        d = ImageDraw.Draw(im)
        for i in range(16):
            y = 6 + i * 17
            half = (230 - i * 11) * rnd.uniform(0.75, 1.1)
            off = rnd.uniform(-20, 20)
            d.rounded_rectangle((540 - half + off, y, 540 + half + off, y + 5), 2,
                                fill=(255, 150 - i * 4, 160, int(200 - i * 9)))
        return im

    def render(self, T, strobe=0.0, tint=None):
        im = self.base.copy()
        im.alpha_composite(self.reflect[int(T * 8) % 8], (0, HORIZON))
        d = ImageDraw.Draw(im)
        ph = (T / B) % 1.0                                  # grid lines rush toward you, one step per beat
        for i in range(10):
            z = (i + 1 - ph) / 10
            y = GRID_TOP + (H - GRID_TOP) * z ** 2.2
            d.line([(0, y), (W, y)], fill=(255, 70, 210, int(120 + 120 * z)), width=max(2, int(5 * z)))
        lp, rp = self.palms[int(T * 4) % 8]
        im.alpha_composite(lp, (-int(lp.width * 0.38), H - 330 - lp.height + 120))
        rp2 = rp.transpose(Image.FLIP_LEFT_RIGHT)
        im.alpha_composite(rp2, (W - int(rp2.width * 0.62), H - 420 - rp2.height + 120))
        im.alpha_composite(self.vig)
        if tint is not None:
            im.alpha_composite(Image.new("RGBA", (W, H), tint + (30,)))
        if strobe > 0.01:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(40 * strobe))))
        return im


def neon(text, size, col, stroke=None):
    """Bold text with a coloured glow."""
    t = rtext(text, size, fill=(255, 255, 255), stroke=stroke)
    pad = size // 2
    g = Image.new("RGBA", (t.width + 2 * pad, t.height + 2 * pad))
    a = Image.new("L", g.size)
    a.paste(t.getchannel("A"), (pad, pad))
    glow = Image.new("RGBA", g.size, col + (255,))
    glow.putalpha(a.filter(ImageFilter.GaussianBlur(size / 7)).point(lambda v: min(255, int(v * 1.6))))
    g.alpha_composite(glow)
    c = rtext(text, size, fill=col, stroke=stroke)
    g.alpha_composite(c, (pad, pad))
    hl = rtext(text, size, fill=(255, 255, 255), stroke=0)
    hl.putalpha(hl.getchannel("A").point(lambda v: v // 3))
    g.alpha_composite(hl, (pad, pad - 2))
    return g


def wrap(text, size, width):
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


def question_card(text):
    size = 66
    while True:
        lines = wrap(text, size, 860)
        if len(lines) <= 3 or size <= 44:
            break
        size -= 2
    imgs = [rtext(ln, size, stroke=6) for ln in lines]
    step = int(size * 1.12)                       # line spacing from the font size, not the padded image
    h = step * len(imgs) + 56
    card = rounded_card(980, h, 40, (26, 8, 46, 230), outline=PINK + (255,), width=5)
    for k, i in enumerate(imgs):
        paste_center(card, i, 490, 28 + step * (k + 0.5) + 2)
    return card


def pill(letter, text, state):
    """Answer pill: state is 'idle', 'right' or 'wrong'."""
    fill = {"idle": (26, 8, 46, 235), "right": GREEN + (255,), "wrong": (120, 24, 54, 230)}[state]
    out = {"idle": CYAN, "right": (255, 255, 255), "wrong": (200, 60, 90)}[state]
    p = rounded_card(PILL_W, PILL_H, PILL_H // 2, fill, outline=out + (255,), width=5)
    bc = {"idle": PINK, "right": (255, 255, 255), "wrong": (200, 60, 90)}[state]
    badge = mv.circle(84, bc + (255,))
    ImageDraw.Draw(badge).text((42, 44), letter, font=rfont(50), fill=GREEN if state == "right" else INK,
                               anchor="mm")
    p.alpha_composite(badge, (18, (PILL_H - 84) // 2))
    size = 50
    room = PILL_W - 140 - (110 if state == "right" else 40)
    while rfont(size).getlength(text) > room and size > 30:
        size -= 1
    t = rtext(text, size, fill=(255, 255, 255) if state != "wrong" else (230, 190, 200), stroke=5)
    p.alpha_composite(t, (128, (PILL_H - t.height) // 2))
    if state == "right":
        p.alpha_composite(emoji("✅", 64), (PILL_W - 96, (PILL_H - 64) // 2))
    return p


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    """6 beats: ONLY REAL GTA FANS GET 10/10 cold open, an emoji montage, then GTA 6 / QUIZ / 99% FAIL slams."""

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 7 * B
        self.t1, self.t2 = 1.5 * B, 4.5 * B
        self.o1 = rtext("ONLY REAL", 120, stroke=11)
        self.o2 = neon("GTA FANS", 150, PINK, stroke=12)
        self.o3 = join(rtext("GET 10/10", 130, fill=GOLD, stroke=12), emoji("💀", 120))
        self.cuts = [emoji(e, 380) for e in ("🚗", "💰", "🚁", "🌴", "🏎", "💸")]
        self.m1 = rtext("CAN YOU GET", 108, stroke=10)
        self.m2 = rtext("ALL TEN?", 140, fill=CYAN, stroke=12)
        self.l1 = neon("GTA 6", 250, PINK, stroke=16)
        self.l2 = neon("QUIZ", 200, CYAN, stroke=14)
        self.l3 = join(rtext("99% FAIL", 120, fill=GOLD, stroke=11), emoji("💀", 120))
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9),
                        (B, sfx_heartbeat(), 0.8), (self.t2, mq.sfx_boom(), 0.9), (5 * B, mv.sfx_pop(), 0.9),
                        (5.5 * B, mq.sfx_boom(), 0.6), (5.5 * B, mv.sfx_riser(1.5 * B), 0.7),
                        (7 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        self.cut_len = (self.t2 - self.t1) / 6
        for k in range(6):
            at = self.t1 + k * self.cut_len
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mq.sfx_glitch(), 0.35), (at, mv.sfx_click(), 0.7)]
        if tts:
            self.voices.append((0.04, tts.say(INTRO_LINE, speed=1.18)))

    def render(self, t):
        T = self.t0 + t
        bg = self.ui["bg"]
        if t < self.t1:
            im = bg.render(T, strobe=beat_pulse(T))
            im.alpha_composite(self.ui["vig"][int(10 * (0.3 + 0.4 * beat_pulse(T)))])
            s = 1 + 0.1 * (1 - ease_out_cubic(t / 0.2))
            paste_center(im, scaled(self.o1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 520)
            paste_center(im, scaled(self.o2, s * (1 + 0.04 * beat_pulse(T))).rotate(2, Image.BICUBIC, expand=True),
                         W / 2, 720)
            paste_center(im, scaled(self.o3, s).rotate(-2, Image.BICUBIC, expand=True), W / 2, 930)
            im = shake(im, 26 * (1 - t / 0.3) if t < 0.3 else 0, t)
            im = rgb_split(im, 12 * (1 - clamp(t / 0.25)))
        elif t < self.t2:
            k = min(len(self.cuts) - 1, int((t - self.t1) / self.cut_len))
            tc = t - self.t1 - k * self.cut_len
            im = bg.render(T, strobe=1 - clamp(tc / 0.15))
            paste_center(im, scaled(self.cuts[k], 1.15 - 0.15 * ease_out_cubic(tc / 0.15)).rotate(
                (-8, 6, -5, 7, -6, 5)[k], Image.BICUBIC, expand=True), W / 2, 820)
            s = 1 + 0.12 * (1 - ease_out_cubic((t - self.t1) / 0.15))
            paste_center(im, scaled(self.m1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 330)
            paste_center(im, scaled(self.m2, s).rotate(3, Image.BICUBIC, expand=True), W / 2, 480)
            im = rgb_split(im, 18 * (1 - clamp(tc / 0.12)))
            if tc < 0.06:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
        else:
            tg = t - self.t2
            im = bg.render(T, strobe=beat_pulse(T))
            im = rgb_split(im, 10 * (1 - clamp(tg / B)))
            im.alpha_composite(Image.new("RGBA", (W, H), (20, 0, 30, 70)))
            b = int(tg / (0.5 * B))
            kk = (tg % (0.5 * B)) / (0.5 * B)
            slam = 1 + 0.35 * (1 - ease_out_cubic(kk / 0.4))
            paste_center(im, scaled(self.l1, (slam if b == 0 else 1.0) * (1 + 0.04 * beat_pulse(T))).rotate(
                -4, Image.BICUBIC, expand=True), W / 2, 560)
            if b >= 1:
                paste_center(im, scaled(self.l2, slam if b == 1 else 1.0).rotate(3, Image.BICUBIC, expand=True),
                             W / 2, 800)
            if b >= 2:
                paste_center(im, scaled(self.l3, slam if b == 2 else 1.0), W / 2, 1010)
            im = shake(im, 22 * (1 - kk) if kk < 0.4 and b <= 2 else 0, t)
            whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
            if whip > 0:
                im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Question(mv.Scene):
    def __init__(self, idx, q, prev_tier, ui, tts):
        super().__init__()
        shown, spoken, answers, right, said, emo, tier, stick = q
        self.idx, self.ui, self.tier, self.right = idx, ui, tier, right
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = ENTRY_BEATS
        v_q = tts.say(spoken, speed=1.1) if tts else None
        v_a = tts.say(said, speed=1.12) if tts else None
        v_c = tts.say(CTA_LINE, speed=1.12) if (tts and self.cta) else None
        read_end = 0.12 + (len(v_q) / SR if v_q is not None else 2.0)
        ans_len = len(v_a) / SR if v_a is not None else 1.0
        cta_len = len(v_c) / SR if v_c is not None else 2.8
        c0 = max(f + 4, math.ceil((read_end + 0.2) / B))      # the count starts once the question is read
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.fly = f * B
        self.reveal = (c0 + n) * B
        hold = max(4, math.ceil((0.08 + ans_len + 0.35) / B))  # the answer is said before the next question
        self.cta_at = max(2, math.ceil((0.08 + ans_len + 0.2) / B)) * B
        if self.cta:
            hold = max(hold, math.ceil((self.cta_at + cta_len + 0.4) / B))
        self.dur = (c0 + n + hold) * B
        self.pill_at = [(f + 0.5 * k) * B for k in range(4)]
        self.card = question_card(shown)
        self.emo = emoji(emo, 220)
        self.pills = {s: [pill("ABCD"[k], a, s) for k, a in enumerate(answers)] for s in ("idle", "right", "wrong")}
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
        self.nums = {k: rtext(str(k), 230, fill=PINK if k == 1 else (255, 255, 255), stroke=16) for k in range(1, n + 1)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (0.05, mq.sfx_boom(), 0.6)]
        for at in self.pill_at:
            self.sounds.append((at, mv.sfx_pop(), 0.7))
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        self.sounds += [(self.reveal, mq.sfx_boom(), 0.9), (self.reveal, mv.sfx_ding(), 1.0),
                        (self.reveal + 0.05, mq.sfx_pling(), 0.6), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        if tts:
            self.voices.append((0.12, v_q))
            self.voices.append((self.reveal + 0.08, v_a))
            if self.cta:
                self.voices.append((self.reveal + self.cta_at, v_c))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = self.reveal + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, mq.sfx_pling(), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        r = random.Random(idx * 31)
        self.conf = [(r.uniform(-1, 1) * 600, r.uniform(-1300, -500), r.randint(12, 26),
                      r.choice([GREEN, GOLD, PINK, CYAN, (255, 255, 255)]), r.uniform(0, 3)) for _ in range(60)]

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        on_beat = beat_pulse(T) if t > self.fly else 0.0
        im = self.ui["bg"].render(T, strobe=on_beat * 0.5 + (1 - clamp(rv / 0.25) if rv > 0 else 0))
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv > 0:
            im.alpha_composite(cq.speed_lines(1 - clamp(rv / 0.45), self.idx, (540, PILL_Y[self.right])))
        d = ImageDraw.Draw(im)
        # top bar
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
        # question card slams in
        kc = ease_out_back(t / 0.3, 1.6)
        if kc > 0.01:
            paste_center(im, scaled(self.card, kc * (1 + 0.015 * on_beat)).rotate(-1.5, Image.BICUBIC, expand=True),
                         W / 2, CARD_Y)
        # big emoji bounces on the beat; the 3-2-1 slams over it
        ke = ease_out_back((t - 0.25) / 0.3, 2.0)
        counting = any(0 <= t - b * B < B for b in self.count_beats)
        if ke > 0.01:
            a = 0.35 if counting else 1.0
            paste_center(im, scaled(self.emo, ke * (1 + 0.08 * on_beat)).rotate(8 * math.sin(T * 3), Image.BICUBIC,
                                                                                  expand=True), W / 2, EMOJI_Y, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a)
        # answer pills pop in one by one, then light up on the drop
        for k in range(4):
            kp = ease_out_back((t - self.pill_at[k]) / 0.25, 1.8)
            if kp <= 0.01:
                continue
            if rv > 0:
                if k == self.right:
                    p = self.pills["right"][k]
                    sc = 1 + 0.12 * (1 - ease_out_cubic(rv / 0.35)) + 0.02 * beat_pulse(T)
                    paste_center(im, scaled(p, sc), W / 2, PILL_Y[k])
                else:
                    p = self.pills["wrong"][k]
                    dx = 14 * math.sin(rv * 60) * (1 - clamp(rv / 0.4))
                    paste_center(im, p, W / 2 + dx, PILL_Y[k], 0.55 + 0.45 * (1 - clamp(rv / 0.4)))
            else:
                bump = 1 + 0.03 * on_beat
                paste_center(im, scaled(self.pills["idle"][k], kp * bump), W / 2 + (1 - min(1, kp)) * 120 * (
                    1 if k % 2 else -1), PILL_Y[k])
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, EMOJI_Y, a)
        if rv > 0:
            cy = PILL_Y[self.right]
            for vx, vy, sz, cc, spin in self.conf:
                px, py = 540 + vx * rv, cy + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d = ImageDraw.Draw(im)
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            sk = ease_out_back((rv - 0.12) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             880, EMOJI_Y)
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
        if self.cta and rv > self.cta_at:
            ct = rv - self.cta_at
            k = ease_out_back(ct / 0.3, 2.0) * (1 - ease_in_cubic(clamp((t - (self.dur - 0.45)) / 0.25)))
            if k > 0.01:
                card = self.cta_card.copy()
                tap = 1 - 0.18 * math.sin(math.pi * clamp((ct - 0.45) / 0.2))
                th = scaled(self.thumb, tap * (1 + 0.08 * beat_pulse(T))).rotate(10 * math.sin(ct * 7), Image.BICUBIC,
                                                                                 expand=True)
                paste_center(card, th, 98, 98)
                sc = k * (1 + 0.025 * beat_pulse(T))
                paste_center(im, scaled(card, sc).rotate(-2, Image.BICUBIC, expand=True), W / 2, CTA_Y)
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
        self.title = neon("HOW MANY?", 124, CYAN, stroke=11)
        tiers = [("0-3", "Pedestrian", "🚶"), ("4-5", "Street racer", "🏎"), ("6-7", "Big boss", "😎"),
                 ("8-9", "Kingpin", "💰"), ("10", "GTA legend", "🌴")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            colr = PINK if i == 4 else (255, 255, 255)
            row = rounded_card(800, 104, 52, (26, 8, 46, 225), outline=(colr if i == 4 else (110, 60, 150)) + (255,),
                               width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 52), sc, font=rfont(60), fill=colr, anchor="lm")
            dr.text((210, 52), label, font=rfont(58, "SemiBold"), fill=colr, anchor="lm")
            row.alpha_composite(emoji(e, 60), (800 - 96, 22))
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
        im = self.ui["bg"].render(T, strobe=0.35 * beat_pulse(T))
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        a = 1 - out
        im.alpha_composite(Image.new("RGBA", (W, H), (14, 4, 28, int(150 * clamp((t - 0.2) / 0.3) * a))))
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
    ui = {"bg": Neon(), "vig": [mc.red_vignette(i / 10) for i in range(11)]}
    intro = Intro(ui, tts)
    scenes, prev = [intro], QUESTIONS[0][6]
    for i, q in enumerate(QUESTIONS, 1):
        scenes.append(Question(i, q, prev, ui, tts))
        prev = q[6]
    scenes.append(Ending(ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    im = ui["bg"].render(0.0)
    im.alpha_composite(Image.new("RGBA", (W, H), (20, 0, 30, 40)))
    paste_center(im, rtext("ONLY REAL", 120, stroke=11).rotate(-3, Image.BICUBIC, expand=True), W / 2, 300)
    paste_center(im, neon("GTA FANS", 170, PINK, stroke=13).rotate(2, Image.BICUBIC, expand=True), W / 2, 500)
    paste_center(im, join(rtext("GET 10/10", 140, fill=GOLD, stroke=12), emoji("💀", 130)).rotate(
        -2, Image.BICUBIC, expand=True), W / 2, 720)
    paste_center(im, emoji("🌴", 300).rotate(-8, Image.BICUBIC, expand=True), 280, 1080)
    paste_center(im, rtext("?", 320, stroke=18).rotate(12, Image.BICUBIC, expand=True), 800, 1080)
    paste_center(im, question_card(QUESTIONS[0][0]), W / 2, 1420)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_gta_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--music", default="phonk", choices=["phonk", "none"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    quiet = a.cover
    scenes, starts, total, ui = build(a.voice if not quiet else "none", None if quiet else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    if a.cover:
        make_cover(ui, os.path.join(HERE, "gta_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"gta_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_gta")
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
