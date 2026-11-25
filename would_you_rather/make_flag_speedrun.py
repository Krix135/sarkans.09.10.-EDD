#!/usr/bin/env python3
""""FLAG SPEEDRUN" Short (1080x1920): 25 flags back to back on the beat, and it gets faster.

Each flag slams onto the screen on a beat and waves while a timer ring drains with a tick on every beat;
on the last beat its name stamps in, the narrator says it and a little burst of the flag's colours pops.
Three speeds: 8 easy flags at 5 beats each, 8 medium at 4, then 9 hard at 3 (under a second to guess),
each speed-up announced with a SPEED UP slam. A counter and a 25-dot progress bar run along the top,
one like call-out after the first 8, viewers count their own score, and the score screen loops back to the
start. Spoken-title intro (6 beats). Flags: public domain.

    python3 make_flag_speedrun.py
    python3 make_flag_speedrun.py --stills 0,5,9
    python3 make_flag_speedrun.py --cover
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
import make_club_quiz as cq  # noqa: E402
import make_logo_quiz as lq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_no_colour_flag_quiz as ncq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center, \
    rounded_card, scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
FC = (540, 930)                      # flag centre
NAME_Y = 1390
FLAG_DIR = os.path.join(HERE, "flags")
GREEN = (46, 204, 113)
SPEEDS = {1: ("SPEED x1", (90, 200, 255), 5), 2: ("SPEED x1.5", (255, 190, 60), 4), 3: ("SPEED x2", (255, 70, 98), 3)}
CTA_AFTER = 8
CTA_LINE = mc.CTA_LINE

FLAGS = [  # flag, name on screen, spoken name, speed stage
    ("US", "USA", "USA!", 1), ("JP", "JAPAN", "Japan!", 1), ("GB", "UNITED KINGDOM", "UK!", 1),
    ("BR", "BRAZIL", "Brazil!", 1), ("CA", "CANADA", "Canada!", 1), ("IT", "ITALY", "Italy!", 1),
    ("DE", "GERMANY", "Germany!", 1), ("FR", "FRANCE", "France!", 1),
    ("MX", "MEXICO", "Mexico!", 2), ("IN", "INDIA", "India!", 2), ("KR", "SOUTH KOREA", "South Korea!", 2),
    ("AR", "ARGENTINA", "Argentina!", 2), ("SE", "SWEDEN", "Sweden!", 2), ("GR", "GREECE", "Greece!", 2),
    ("TR", "TURKEY", "Turkey!", 2), ("CH", "SWITZERLAND", "Switzerland!", 2),
    ("PT", "PORTUGAL", "Portugal!", 3), ("NG", "NIGERIA", "Nigeria!", 3), ("PE", "PERU", "Peru!", 3),
    ("FI", "FINLAND", "Finland!", 3), ("VN", "VIETNAM", "Vietnam!", 3), ("KE", "KENYA", "Kenya!", 3),
    ("NP", "NEPAL", "Nepal!", 3), ("CU", "CUBA", "Cuba!", 3), ("BT", "BHUTAN", "Bhutan!", 3),
]
N = len(FLAGS)
INTRO_WORDS = ("Flag speedrun!", "Twenty-five flags!", "And it gets faster!")
END_LINE = "How many did you get? Comment your score!"


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


class FlagWall(lq.BrandWall):
    EMOJIS = ["🚩", "🏁", "⚡", "🌍", "🏳", "⏱", "🎌", "🌎"]


def name_card(name):
    size = 104
    while rfont(size).getlength(name) > 860 and size > 56:
        size -= 2
    t = rtext(name, size, stroke=9)
    body = join(t, emoji("✅", int(size * 0.8)), gap=16)
    card = rounded_card(body.width + 70, body.height + 34, (body.height + 34) // 2, (12, 10, 30, 240),
                        outline=GREEN + (255,), width=7)
    paste_center(card, body, card.width / 2, card.height / 2)
    return card


def timer_ring(frac, col, size=150):
    k = 2
    s = size * k
    im = Image.new("RGBA", (s, s))
    d = ImageDraw.Draw(im)
    d.ellipse((6, 6, s - 6, s - 6), fill=(12, 10, 30, 235), outline=(255, 255, 255, 60), width=14)
    if frac > 0.001:
        d.arc((6, 6, s - 6, s - 6), -90, -90 + 360 * frac, fill=col + (255,), width=22)
    return im.resize((size, size), Image.LANCZOS)


def header(im, ui, idx, stage, T, done):
    """Title, counter, speed badge and the 25-dot progress bar."""
    paste_center(im, ui["title"], W / 2, 175)
    label, col, _ = SPEEDS[stage]
    paste_center(im, ui["count"][idx], 112, 262)
    sb = ui["speed"][stage]
    paste_center(im, scaled(sb, 1 + 0.05 * beat_pulse(T)), W - 40 - sb.width / 2, 262)
    d = ImageDraw.Draw(im)
    x0, x1, y = 120, 960, 330
    for i in range(N):
        x = x0 + (x1 - x0) * i / (N - 1)
        r = 11 if i == idx - 1 else 8
        c = GREEN if i < done else ((255, 255, 255) if i == idx - 1 else (80, 70, 120))
        d.ellipse((x - r, y - r, x + r, y + r), fill=c + (255,), outline=INK + (255,), width=2)


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class FlagScene(mv.Scene):
    def __init__(self, idx, f, prev_stage, ui, tts):
        super().__init__()
        code, name, said, stage = f
        self.idx, self.ui, self.stage = idx, ui, stage
        self.beats = SPEEDS[stage][2]
        self.dur = self.beats * B
        self.reveal = (self.beats - 1) * B
        self.col = SPEEDS[stage][1]
        self.flag = ncq.framed_flag(code)
        self.shadow = ncq.shadow_for(self.flag)
        self.cols = mm.flag_colours(Image.open(os.path.join(FLAG_DIR, code + ".png")).convert("RGBA"))
        self.card = name_card(name)
        self.speed_up = stage != prev_stage and idx > 1
        if self.speed_up:
            self.banner = join(rtext("SPEED UP!", 120, fill=self.col, stroke=11), emoji("⚡", 110), gap=10)
            self.sounds += [(0.0, mq.sfx_glitch(), 0.8), (0.0, mq.sfx_levelup(), 0.6)]
        self.sounds += [(0.0, mq.sfx_boom(), 0.55), (0.0, mv.sfx_whoosh(0.3), 0.6), (0.02, mv.sfx_pop(), 0.6)]
        for b in range(1, self.beats - 1):                   # tick on every beat while you guess
            self.sounds.append((b * B, mq.sfx_tock(high=b == self.beats - 2), 0.75))
            if stage == 3:
                self.sounds.append((b * B, sfx_heartbeat(), 0.5))
        self.sounds += [(self.reveal, mv.sfx_ding(), 0.8), (self.reveal, mq.sfx_pling(), 0.5),
                        (self.reveal + 0.02, mv.sfx_click(), 0.6)]
        if tts:
            self.voices.append((self.reveal + 0.03, tts.say(said, speed=1.35)))
        rr = random.Random(idx * 13)
        self.conf = [(rr.uniform(0, 2 * math.pi), rr.uniform(400, 1100), rr.randint(10, 22), rr.choice(self.cols))
                     for _ in range(26)]

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        ui = self.ui
        im = ui["bg"].render(T, self.col, strobe=0.35 * beat_pulse(T) + (0.6 * (1 - clamp(rv / 0.2)) if rv > 0 else 0),
                             rays=0.8)
        done = self.idx if rv > 0 else self.idx - 1
        header(im, ui, self.idx, self.stage, T, done)
        k = clamp(t / 0.14)                                  # the flag slams in
        s = (1.35 - 0.35 * ease_out_cubic(k)) * (1 + 0.012 * beat_pulse(T))
        if rv > 0:
            s *= 1 + 0.06 * (1 - ease_out_cubic(clamp(rv / 0.25)))
        fl = ncq.wave(self.flag, T)
        paste_center(im, scaled(self.shadow, s), FC[0] + 16, FC[1] + 26, k)
        sp = scaled(fl, s)
        rot = 6 * (1 - ease_out_cubic(k)) * (1 if self.idx % 2 else -1)
        if abs(rot) > 0.05:
            sp = sp.rotate(rot, Image.BICUBIC, expand=True)
        paste_center(im, sp, FC[0], FC[1], min(1.0, k * 2))
        if rv <= 0:                                          # the timer ring drains to the reveal
            frac = 1 - clamp(t / self.reveal)
            colr = GREEN if frac > 0.5 else GOLD if frac > 0.25 else (255, 70, 98)
            paste_center(im, scaled(timer_ring(frac, colr), 1 + 0.08 * beat_pulse(T)), W / 2, NAME_Y)
        else:
            kc = ease_out_back(clamp(rv / 0.18), 2.2)
            if kc > 0.01:
                paste_center(im, scaled(self.card, 1.5 - 0.5 * kc).rotate(-3, Image.BICUBIC, expand=True), W / 2,
                             NAME_Y, min(1.0, kc))
            d = ImageDraw.Draw(im)
            for ang, sp_, r_, cc in self.conf:
                kk = clamp(rv / 0.6)
                px = FC[0] + math.cos(ang) * sp_ * kk
                py = FC[1] + math.sin(ang) * sp_ * kk + 900 * kk * kk
                rr_ = r_ * (1 - kk)
                if rr_ > 1:
                    d.ellipse((px - rr_, py - rr_, px + rr_, py + rr_), fill=cc + (255,), outline=INK + (255,), width=2)
        paste_center(im, scaled(ui["hint"], 1 + 0.03 * beat_pulse(T)), W / 2, 1760)
        if self.speed_up and t < 0.9:                        # SPEED UP slam over the first flag of a stage
            tb = t
            sc = 1 + 0.8 * (1 - ease_out_cubic(clamp(tb / 0.15)))
            a = clamp(tb / 0.05) * (1 - clamp((tb - 0.65) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-5, Image.BICUBIC, expand=True), W / 2, 1640, a)
        if t < 0.1:
            im = shake(im, 18 * (1 - t / 0.1), t)
            im = rgb_split(im, 14 * (1 - t / 0.1))
        if self.speed_up and t < 0.3:
            im = glitch(im, 1 - t / 0.3, int(t * 30) + self.idx * 7)
        if 0 < rv < 0.15:
            im = shake(im, 14 * (1 - rv / 0.15), t)
        return im


class Cta(mv.Scene):
    """A short like call-out between the first 8 flags and the speed-up."""

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        v = tts.say(CTA_LINE, speed=1.15) if tts else None
        self.dur = max(5, math.ceil(((len(v) / SR if v is not None else 2.3) + 0.3) / B)) * B
        if v is not None:
            self.voices.append((0.05, v))
        self.card = rounded_card(840, 210, 105, INK + (240,), outline=PINK + (255,), width=6)
        paste_center(self.card, rtext(f"GOT {CTA_AFTER}/{CTA_AFTER} SO FAR?", 54, fill=GOLD, stroke=5), 500, 70)
        paste_center(self.card, rtext("LIKE THIS VIDEO!", 66, stroke=6), 500, 142)
        self.thumb = emoji("👍", 140)
        self.next = join(rtext("NEXT: SPEED x1.5", 64, fill=SPEEDS[2][1], stroke=7), emoji("⚡", 64), gap=10)
        self.sounds += [(0.0, mv.sfx_pop(), 0.9), (0.02, mq.sfx_pling(), 0.5), (0.45, mv.sfx_click(), 0.8),
                        (self.dur - 0.9, mv.sfx_riser(0.9), 0.6)]

    def render(self, t):
        T = self.t0 + t
        im = self.ui["bg"].render(T, PINK, strobe=0.3 * beat_pulse(T), rays=0.8)
        header(im, self.ui, CTA_AFTER, 1, T, CTA_AFTER)
        k = ease_out_back(clamp(t / 0.3), 2.0)
        card = self.card.copy()
        tap = 1 - 0.18 * math.sin(math.pi * clamp((t - 0.45) / 0.2))
        th = scaled(self.thumb, tap * (1 + 0.08 * beat_pulse(T))).rotate(10 * math.sin(t * 7), Image.BICUBIC,
                                                                         expand=True)
        paste_center(card, th, 105, 105)
        paste_center(im, scaled(card, max(0.01, k) * (1 + 0.025 * beat_pulse(T))).rotate(-2, Image.BICUBIC,
                                                                                     expand=True), W / 2, 900)
        kn = ease_out_back(clamp((t - 0.6) / 0.3), 2.0)
        if kn > 0.01:
            paste_center(im, scaled(self.next, kn * (1 + 0.04 * beat_pulse(T))), W / 2, 1200)
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(mm.zoom_blur(im, out), 22 * out)
        return im


class Intro(mv.Scene):
    SHOW = (24, 20, 16)                                      # flags shown behind each phrase

    def __init__(self, ui, tts, flags):
        super().__init__()
        self.ui, self.flags = ui, flags
        self.dur = 6 * B
        hb = 0.5 * B
        clips = [tts.say(w, speed=1.24) for w in INTRO_WORDS] if tts else None
        lens = [len(c) / SR for c in clips] if clips else [0.75, 0.9, 1.0]
        self.slams = [0.0]
        for ln in lens:
            prev = self.slams[-1]
            self.slams.append(max(prev + hb, round((prev + ln - 0.08) / hb) * hb))
        self.slams[-1] = min(self.slams[-1], self.dur - 0.4)
        if clips:
            for at, c in zip(self.slams, clips):
                self.voices.append((at, c))
        self.w1 = fit(join(rtext("FLAG SPEEDRUN", 140, fill=GOLD, stroke=13), emoji("⚡", 120), gap=12), 990)
        self.w2 = fit(rtext("25 FLAGS", 170, stroke=15), 990)
        self.w3 = fit(join(rtext("IT GETS FASTER", 110, fill=PINK, stroke=11), emoji("💀", 100), gap=10), 990)
        self.l1 = fit(rtext("FLAG", 200, stroke=16), 990)
        self.l2 = fit(join(rtext("SPEEDRUN", 170, fill=GOLD, stroke=15), emoji("⚡", 140), gap=12), 990)
        self.l3 = fit(join(rtext("25 FLAGS · 99% FAIL", 76, fill=PINK, stroke=8), emoji("💀", 76), gap=10), 990)
        self.minis = []
        for f in FLAGS[:12]:
            fl = Image.open(os.path.join(FLAG_DIR, f[0] + ".png")).convert("RGBA")
            fl.thumbnail((210, 140), Image.LANCZOS)
            fb = Image.new("RGBA", (fl.width + 10, fl.height + 10), (255, 255, 255, 255))
            fb.paste(fl, (5, 5), fl)
            self.minis.append(fb)
        self.sounds += [(0.0, sfx_heartbeat(), 0.8),
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
        if k < 3:                                            # word slams over flags
            f = self.flags[self.SHOW[k]]
            im = f.render(f.reveal - 0.1)
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 130)))
            words = [(self.w1, 700, -3), (self.w2, 900, 2), (self.w3, 1100, -2)]
            for j in range(k + 1):
                img, y, rot = words[j]
                sc = (slam if j == k else 1.0) * (1 + 0.025 * beat_pulse(T))
                paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
            im = shake(im, 24 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
            im = rgb_split(im, (8 if k == 0 else 16) * (1 - clamp(ts / 0.15)))
            if k > 0:
                im = mm.zoom_blur(im, 0.6 * (1 - clamp(ts / 0.1)))
                if ts < 0.06:
                    im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            return im
        im = self.ui["bg"].render(T, GOLD, strobe=beat_pulse(T), rays=1.0)   # title card, flags flying out
        for j, mini in enumerate(self.minis):
            ang = j * (2 * math.pi / len(self.minis)) + 0.2
            r = 220 + 950 * ease_out_cubic(clamp(ts / 0.8))
            paste_center(im, mini.rotate(ts * 120 * (1 if j % 2 else -1), Image.BICUBIC, expand=True),
                         W / 2 + r * math.cos(ang), 900 + r * math.sin(ang) * 0.9)
        for j, (img, y, rot) in enumerate([(self.l1, 700, -3), (self.l2, 900, 3), (self.l3, 1090, -2)]):
            sc = (slam if j == 2 else 1 + 0.12 * (1 - ease_out_cubic(clamp(ts / 0.18)))) * (1 + 0.03 * beat_pulse(T))
            paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
        im = shake(im, 22 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
        if ts < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - ts / 0.08)))))
        whip = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Ending(mv.Scene):
    """Score screen with ranks out of 25; it fades into the first frame so the Short loops."""

    def __init__(self, ui, intro, tts):
        super().__init__()
        self.ui, self.intro = ui, intro
        self.dur = 10 * B
        logo = Image.open(brand.round_logo()).convert("RGBA").resize((120, 120), Image.LANCZOS)
        self.brand = join(logo, rtext(brand.NAME, 60, stroke=6), gap=18)
        self.title = rtext("HOW MANY?", 124, fill=CYAN, stroke=11)
        tiers = [("0-10", "Tourist", "📸"), ("11-15", "Backpacker", "🎒"), ("16-20", "Explorer", "🧭"),
                 ("21-24", "Flag nerd", "🤓"), ("25", "Flag master", "🏆")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            colr = PINK if i == 4 else (255, 255, 255)
            row = rounded_card(800, 104, 52, INK + (215,), outline=(colr if i == 4 else (90, 70, 130)) + (255,),
                               width=4)
            dr = ImageDraw.Draw(row)
            dr.text((40, 52), sc, font=rfont(56), fill=colr, anchor="lm")
            dr.text((240, 52), label, font=rfont(58, "SemiBold"), fill=colr, anchor="lm")
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
        im = self.ui["bg"].render(T, GOLD, strobe=0.3 * beat_pulse(T), rays=0.6)
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        a = 1 - out
        im.alpha_composite(Image.new("RGBA", (W, H), INK + (int(140 * clamp((t - 0.2) / 0.3) * a),)))
        paste_center(im, self.brand, W / 2, 300, clamp((t - B) / 0.2) * a)
        paste_center(im, scaled(self.title, ease_out_back((t - B) / 0.25) * (1 + 0.03 * beat_pulse(T))), W / 2, 460, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - (1.5 + 0.5 * i) * B) / 0.2)
            if k > 0:
                paste_center(im, row, W / 2 + (1 - k) * 160, 620 + i * 122, k * a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 5 * B) / 0.25) * (1 + 0.03 * math.sin(t * 8))),
                     W / 2, 1290, a)
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
    ui = {"bg": FlagWall(), "title": join(rtext("FLAG SPEEDRUN", 58, fill=GOLD, stroke=6), emoji("⚡", 56), gap=10),
          "count": {i: rtext(f"{i}/{N}", 50, stroke=5) for i in range(N + 1)},
          "hint": join(rtext("say it before the name pops up", 46, fill=GOLD, stroke=5), emoji("🗣", 50), gap=10)}
    ui["speed"] = {}
    for st, (label, col, _) in SPEEDS.items():
        t = rtext(label, 34, fill=INK, stroke=0)
        b = rounded_card(t.width + 40, 56, 28, col + (255,), outline=INK + (255,), width=3)
        paste_center(b, t, b.width / 2, 29)
        ui["speed"][st] = b
    flags, prev = [], 1
    for i, f in enumerate(FLAGS, 1):
        flags.append(FlagScene(i, f, prev, ui, tts))
        prev = f[3]
    intro = Intro(ui, tts, flags)
    scenes = [intro, *flags[:CTA_AFTER], Cta(ui, tts), *flags[CTA_AFTER:], Ending(ui, intro, tts)]
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    im = ui["bg"].render(1.0, GOLD, strobe=0.2, rays=1.0)
    r = random.Random(4)
    for i, f in enumerate(FLAGS):                            # a 5x5 wall of the flags
        fl = Image.open(os.path.join(FLAG_DIR, f[0] + ".png")).convert("RGBA")
        fl = fl.resize((176, 118), Image.LANCZOS)
        fb = Image.new("RGBA", (186, 128), (255, 255, 255, 255))
        fb.paste(fl, (5, 5), fl)
        x = 120 + (i % 5) * 210
        y = 700 + (i // 5) * 175
        paste_center(im, fb.rotate(r.uniform(-7, 7), Image.BICUBIC, expand=True), x, y)
    paste_center(im, fit(rtext("FLAG", 190, stroke=15), 990).rotate(-3, Image.BICUBIC, expand=True), W / 2, 210)
    paste_center(im, fit(join(rtext("SPEEDRUN", 160, fill=GOLD, stroke=14), emoji("⚡", 130), gap=12), 1000)
                 .rotate(3, Image.BICUBIC, expand=True), W / 2, 400)
    paste_center(im, join(rtext("25 FLAGS · 99% FAIL", 80, fill=PINK, stroke=9), emoji("💀", 80), gap=10), W / 2,
                 1660)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_flag_speedrun.mp4"))
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
        make_cover(ui, os.path.join(HERE, "flag_speedrun_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"speed_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_flag_speedrun")
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
