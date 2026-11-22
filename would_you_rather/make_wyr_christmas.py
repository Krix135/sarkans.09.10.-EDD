#!/usr/bin/env python3
""""WOULD YOU RATHER? CHRISTMAS EDITION" Short (1080x1920), the popular split-screen format.

Eight Christmas dilemmas on a red / green split screen with snow-capped cards. The narrator reads each
one (the option being read lights up), a 3-2-1 runs inside the OR badge (with a candy-cane ring) on the
beat, then a poll fills both cards and counts up to the split (made-up, "for fun" numbers, noted in the
description), the losing side dims, sleigh bells ring and presents burst out, and the narrator says the
result. Snow falls the whole time, Christmas lights twinkle on the beat and Christmas emojis drift in the
background, all to our own Jingle Bells arrangement. Spoken-title intro, one like call-out after
question 3 and an ending that loops to the start. Only text and emojis.

    python3 make_wyr_christmas.py
    python3 make_wyr_christmas.py --stills 1,5,8
    python3 make_wyr_christmas.py --cover
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

import christmas_music as xm  # noqa: E402
import make_christmas_quiz as xq  # noqa: E402
import make_club_quiz as cq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
import make_wyr_money as wm  # noqa: E402
from make_map_quiz import GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center, scaled  # noqa

W, H, FPS = wm.W, wm.H, 30
B = wm.B
XRED, XGREEN = xq.XRED, xq.XGREEN
GREEN_A, GREEN_B = (74, 205, 112), (16, 118, 58)

QUESTIONS = [  # A text, A emoji, B text, B emoji, spoken question, pick, spoken result, fact, % who chose A
    ("Unlimited presents, but no snow", "🎁", "A white Christmas, but no presents", "❄",
     "Unlimited presents but no snow, or a white Christmas with no presents?", None,
     "64 percent want the presents!", None, 64),
    ("Be Santa for a day", "🎅", "Be one of his elves for a year", "🧝",
     "Be Santa for a day, or one of his elves for a whole year?", None, "71 percent would be Santa!", None, 71),
    ("Christmas every month", "🎄", "Your birthday every month", "🎂",
     "Christmas every month, or your birthday every month?", None, "55 percent picked Christmas!", None, 55),
    ("Only eat Christmas dinner forever", "🍗", "Only eat Christmas cookies forever", "🍪",
     "Only eat Christmas dinner forever, or only Christmas cookies forever?", None,
     "58 percent picked Christmas dinner!", None, 58),
    ("Open all your presents on December 1st", "📦", "Get double presents, but wait until New Year", "⏳",
     "Open all your presents on December first, or get double presents but wait until New Year?", None,
     "61 percent would wait for double!", None, 39),
    ("A real reindeer as a pet", "🦌", "A snowman that comes to life", "⛄",
     "A real reindeer as a pet, or a snowman that comes to life?", None, "68 percent want the reindeer!", None, 68),
    ("Christmas in a snowy cabin", "🏔", "Christmas on a sunny beach", "🏖",
     "Christmas in a snowy cabin, or on a sunny beach?", None, "52 percent picked the snowy cabin!", None, 52),
    ("$10,000, but you skip Christmas this year", "💰", "A normal Christmas at home", "🏠",
     "Final one. Ten thousand dollars but you skip Christmas this year, or a normal Christmas at home?", None,
     "Only 51 percent took the money! So close!", None, 51),
]
INTRO_WORDS = ("Would you rather?", "Christmas edition!", "Last one is impossible!")
END_LINE = wm.END_LINE

# the money edition's scenes read these module values
wm.QUESTIONS = QUESTIONS
wm.BLUE_A, wm.BLUE_B = GREEN_A, GREEN_B                  # card B is green instead of blue
wm.sfx_coins = xm.sfx_jingle                              # sleigh bells instead of coins


class ChristmasWall(wm.MoneyRain):
    """Night-blue backdrop with drifting Christmas emojis, falling snow and twinkling lights on top."""

    def __init__(self):
        rnd = random.Random(12)
        self.base = mv.vgradient(W, H, (10, 16, 44), (30, 10, 40)).convert("RGBA")
        paste_center(self.base, mv.soft_circle(1300, (255, 80, 90, 55), 260), W / 2, wm.BADGE_Y)
        sprites = [emoji(e, s) for e in ("🎄", "🎁", "⛄", "❄", "🔔", "⭐", "🍬", "🦌") for s in (70, 96, 124)]
        self.items = []
        for _ in range(42):
            depth = rnd.uniform(0.4, 1.0)
            spr = scaled(rnd.choice(sprites), depth)
            a = int(95 * depth)
            spr.putalpha(spr.getchannel("A").point(lambda v, a=a: v * a // 255))
            frames = [spr.rotate(rnd.uniform(-40, 40) + k * 8, Image.BICUBIC, expand=True) for k in range(6)]
            self.items.append((rnd.uniform(0, W), rnd.uniform(0, H + 200), 80 + 170 * depth, frames,
                               rnd.uniform(0, 6.28)))
        ys, xs = np.mgrid[0:H, 0:W]
        dd = np.sqrt(((xs - W / 2) / (W * 0.72)) ** 2 + ((ys - H / 2) / (H * 0.62)) ** 2)
        a = np.zeros((H, W, 4), np.uint8)
        a[..., 3] = (np.clip(dd - 0.62, 0, 1) * 330).clip(0, 170).astype(np.uint8)
        self.vig = Image.fromarray(a, "RGBA")
        self.snow = xq.Snow(110, seed=5)
        self.lights = xq.light_string()

    def render(self, T, strobe=0.0, tint=None):
        im = super().render(T, strobe, tint)
        self.snow.draw(im, T, 0.8)
        im.alpha_composite(self.lights[int(T / (0.5 * B)) % 2])
        return im


def snowcap(p):
    """Snow piled along the top edge of a card, with a few icicles, and a soft glow where the emoji sits."""
    p = p.copy()
    paste_center(p, mv.soft_circle(420, (255, 255, 255, 70), 130), p.width / 2, p.height / 2 - 120)
    cap = Image.new("RGBA", p.size)
    d = ImageDraw.Draw(cap)
    r = random.Random(p.width)
    x0, x1 = 190, 20 + wm.PANEL_W - 70
    for x in range(x0, x1, 40):
        h = r.uniform(26, 40)
        d.ellipse((x - 38, 22 - h * 0.55, x + 38, 22 + h * 0.75), fill=(250, 253, 255, 255))
    for x in range(x0 + 30, x1, 140):                         # icicles
        ln = r.uniform(26, 52)
        d.polygon([(x - 9, 40), (x + 9, 40), (x, 40 + ln)], fill=(225, 242, 255, 255))
    sh = cap.getchannel("A").filter(ImageFilter.GaussianBlur(5))
    shadow = Image.new("RGBA", p.size, (120, 150, 200, 0))
    shadow.putalpha(sh.point(lambda v: v * 90 // 255))
    p.alpha_composite(shadow, (0, 5))
    p.alpha_composite(cap)
    return p


def candy_ring(size=230):
    k = 2
    s = size * k
    im = Image.new("RGBA", (s, s))
    d = ImageDraw.Draw(im)
    n = 16
    for i in range(n):
        a0, a1 = 360 * i / n, 360 * (i + 1) / n
        d.pieslice((0, 0, s - 1, s - 1), a0, a1, fill=(XRED if i % 2 == 0 else (255, 255, 255)) + (255,))
    d.ellipse((0, 0, s - 1, s - 1), outline=(120, 10, 30, 255), width=6)
    return im.resize((size, size), Image.LANCZOS)


class Question(wm.Question):
    def __init__(self, idx, q, ui, tts):
        super().__init__(idx, q, ui, tts)
        self.title = join(rtext("WOULD YOU RATHER", 54, stroke=6), emoji("🎄", 56), gap=10)
        self.panels = [snowcap(p) for p in self.panels]
        self.ring = ui["ring"]
        if self.final:
            self.banner = join(rtext("FINAL ONE", 110, fill=XRED, stroke=11), emoji("💀", 110))


# ----------------------------------------------------------------------------
# intro: the title, said and slammed in word by word over real questions, then the title card
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    SHOW = (7, 1, 4)                                          # questions shown behind each phrase

    def __init__(self, ui, tts, questions):
        super().__init__()
        self.ui, self.questions = ui, questions
        self.dur = 6 * B
        hb = 0.5 * B
        clips = [tts.say(w, speed=1.24) for w in INTRO_WORDS] if tts else None
        lens = [len(c) / SR for c in clips] if clips else [0.8, 0.85, 1.1]
        self.slams = [0.0]
        for ln in lens:
            prev = self.slams[-1]
            self.slams.append(max(prev + hb, round((prev + ln - 0.08) / hb) * hb))
        self.slams[-1] = min(self.slams[-1], self.dur - 0.4)
        if clips:
            for at, c in zip(self.slams, clips):
                self.voices.append((at, c))
        e1 = rtext("WOULD YOU RATHER?", 140, stroke=13)
        self.w1 = scaled(e1, min(1.0, 990 / e1.width))
        e2 = join(rtext("CHRISTMAS EDITION", 112, fill=XRED, stroke=11), emoji("🎄", 104), gap=12)
        self.w2 = scaled(e2, min(1.0, 990 / e2.width))
        e3 = join(rtext("LAST ONE IS IMPOSSIBLE", 84, fill=GOLD, stroke=9), emoji("💀", 84), gap=10)
        self.w3 = scaled(e3, min(1.0, 990 / e3.width))
        self.l1 = rtext("WOULD YOU", 150, stroke=13)
        self.l2 = rtext("RATHER?", 200, fill=GOLD, stroke=16)
        self.l3 = scaled(e2, min(1.0, 960 / e2.width))
        self.burst = [emoji(e, 230) for e in ("🎅", "🎁", "⛄", "🎄", "🦌", "🔔")]
        self.sounds += [(0.0, sfx_heartbeat(), 0.8), (0.0, xm.sfx_jingle(), 0.7),
                        (self.slams[2], mv.sfx_riser(self.slams[3] - self.slams[2]), 0.6),
                        (self.slams[3], xm.sfx_jingle(), 0.9), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.9)]
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
        if k < 3:                                            # word slams over real questions
            q = self.questions[self.SHOW[k]]
            im = q.render(q.count_beats[0] * B - 0.1).filter(ImageFilter.GaussianBlur(7))
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 150)))
            words = [(self.w1, 760, -3), (self.w2, 930, 2), (self.w3, 1110, -2)]
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
        im = self.ui["bg"].render(T * 1.5, strobe=beat_pulse(T))  # the title card, Christmas emojis bursting out
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 20, 50)))
        for j, e in enumerate(self.burst):
            ang = j * (2 * math.pi / len(self.burst)) + 0.3
            r = 200 + 900 * ease_out_cubic(clamp(ts / 0.8))
            paste_center(im, scaled(e, 1 - 0.3 * clamp(ts / 0.8)).rotate(ts * 160, Image.BICUBIC, expand=True),
                         W / 2 + r * math.cos(ang), 860 + r * math.sin(ang) * 0.85)
        for j, (img, y, rot) in enumerate([(self.l1, 640, -3), (self.l2, 830, 3), (self.l3, 1030, -2)]):
            sc = (slam if j == 2 else 1 + 0.12 * (1 - ease_out_cubic(clamp(ts / 0.18)))) * (1 + 0.03 * beat_pulse(T))
            paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
        im = shake(im, 22 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
        if ts < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - ts / 0.08)))))
        whip = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


def build(voice="am_adam", voice_pack=None):
    if voice_pack:
        tts = cq.Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    ui = {"bg": ChristmasWall(), "vig": [mc.red_vignette(i / 10) for i in range(11)], "ring": candy_ring(),
          "cash": [emoji(e, s) for e in ("🎁", "⭐", "❄", "🍬", "🎄") for s in (90, 120)]}
    questions = [Question(i, q, ui, tts) for i, q in enumerate(QUESTIONS, 1)]
    intro = Intro(ui, tts, questions)
    scenes = [intro, *questions, wm.Ending(ui, intro, tts)]
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    im = ui["bg"].render(3.0)
    q = QUESTIONS[0]
    paste_center(im, snowcap(wm.panel("A", q[0], q[1], wm.RED_A, wm.RED_B)), W / 2, 1040)
    paste_center(im, emoji(q[1], 210), W / 2, 880)
    paste_center(im, wm.text_block(q[0]), W / 2, 1095)
    paste_center(im, snowcap(wm.panel("B", q[2], q[3], GREEN_A, GREEN_B)), W / 2, 1600)
    paste_center(im, emoji(q[3], 200), W / 2, 1490)
    paste_center(im, wm.text_block(q[2]), W / 2, 1700)
    paste_center(im, rtext("WOULD YOU", 140, stroke=12).rotate(-3, Image.BICUBIC, expand=True), W / 2, 240)
    paste_center(im, rtext("RATHER?", 190, fill=GOLD, stroke=15).rotate(3, Image.BICUBIC, expand=True), W / 2, 430)
    paste_center(im, join(rtext("CHRISTMAS EDITION", 84, fill=XRED, stroke=8), emoji("🎄", 88)), W / 2, 620)
    badge = mv.circle(190, (255, 255, 255, 255))
    ImageDraw.Draw(badge).text((95, 98), "OR", font=rfont(84), fill=INK, anchor="mm")
    paste_center(im, ui["ring"], W / 2, 1320)
    paste_center(im, badge, W / 2, 1320)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_wyr_christmas.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    quiet = a.stills or a.cover
    scenes, starts, total, ui = build(a.voice if not quiet else "none", None if quiet else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    if a.cover:
        make_cover(ui, os.path.join(HERE, "wyr_christmas_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"wyrx_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    work = os.path.join(mv.CACHE_DIR, "render_wyr_christmas")
    os.makedirs(work, exist_ok=True)
    for f in os.listdir(work):
        os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, xq.mix_audio(scenes, starts, total))
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
