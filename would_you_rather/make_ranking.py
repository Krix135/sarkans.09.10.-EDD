#!/usr/bin/env python3
"""Vertical "Top 10" ranking Short (1080x1920, under 60 s) about countries.

The list is on screen from the first frame (no intro or outro). Slots are
revealed from #10 up to #1, each with a short "guess now" pause, and #1 gets a
drumroll. Reuses the drawing, audio and TTS engine from make_video.py.

    python3 make_ranking.py                  # biggest countries
    python3 make_ranking.py --list smallest
    python3 make_ranking.py --list populated --stills 3,20,45
"""

import argparse
import math
import multiprocessing as mp
import os
import random
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

import make_video as mv
from make_video import (SR, YELLOW, clamp, ease_out_back, ease_out_cubic, emoji, font, highpass, paste_center,
                        radial_glow, rounded_card, scaled, sfx_ding, sfx_fanfare, sfx_pop, sfx_tick, sfx_whoosh,
                        text_img, tt, vgradient)

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
HERE = os.path.dirname(os.path.abspath(__file__))
NAVY = (20, 22, 45)
GOLD = (255, 200, 40)
MAX_LEN = 59.0

# Each entry: (flag, name on screen, stat on screen, what the narrator says at the reveal)
LISTS = {
    "biggest": {
        "title": "BIGGEST", "subtitle": "COUNTRIES IN THE WORLD", "unit": "by total area",
        "hook": "Can you guess the 10 biggest countries in the world?",
        "items": [  # rank 1 first
            ("🇷🇺", "RUSSIA", "17.1 million km²", "Russia! It's even bigger than the surface of Pluto."),
            ("🇨🇦", "CANADA", "9.98 million km²", "Canada! Just a little bigger than the US."),
            ("🇺🇸", "USA", "9.83 million km²", "The United States!"),
            ("🇨🇳", "CHINA", "9.6 million km²", "China!"),
            ("🇧🇷", "BRAZIL", "8.5 million km²", "Brazil!"),
            ("🇦🇺", "AUSTRALIA", "7.7 million km²", "Australia, a whole continent!"),
            ("🇮🇳", "INDIA", "3.3 million km²", "India!"),
            ("🇦🇷", "ARGENTINA", "2.8 million km²", "Argentina!"),
            ("🇰🇿", "KAZAKHSTAN", "2.7 million km²", "Kazakhstan!"),
            ("🇩🇿", "ALGERIA", "2.4 million km²", "Algeria, the biggest in Africa!"),
        ],
    },
    "smallest": {
        "title": "SMALLEST", "subtitle": "COUNTRIES IN THE WORLD", "unit": "by total area",
        "hook": "Can you guess the 10 smallest countries in the world?",
        "items": [
            ("🇻🇦", "VATICAN CITY", "0.44 km²", "Vatican City! It's about 8 times smaller than Central Park."),
            ("🇲🇨", "MONACO", "2 km²", "Monaco!"),
            ("🇳🇷", "NAURU", "21 km²", "Nauru!"),
            ("🇹🇻", "TUVALU", "26 km²", "Tuvalu!"),
            ("🇸🇲", "SAN MARINO", "61 km²", "San Marino!"),
            ("🇱🇮", "LIECHTENSTEIN", "160 km²", "Liechtenstein!"),
            ("🇲🇭", "MARSHALL ISLANDS", "181 km²", "The Marshall Islands!"),
            ("🇰🇳", "ST KITTS & NEVIS", "261 km²", "Saint Kitts and Nevis!"),
            ("🇲🇻", "MALDIVES", "298 km²", "The Maldives!"),
            ("🇲🇹", "MALTA", "316 km²", "Malta!"),
        ],
    },
    "populated": {
        "title": "MOST PEOPLE", "subtitle": "COUNTRIES BY POPULATION", "unit": "2025 estimates",
        "hook": "Can you guess the 10 countries with the most people?",
        "items": [
            ("🇮🇳", "INDIA", "≈ 1.46 billion", "India! It passed China in 2023."),
            ("🇨🇳", "CHINA", "≈ 1.42 billion", "China!"),
            ("🇺🇸", "USA", "≈ 347 million", "The United States!"),
            ("🇮🇩", "INDONESIA", "≈ 286 million", "Indonesia!"),
            ("🇵🇰", "PAKISTAN", "≈ 255 million", "Pakistan!"),
            ("🇳🇬", "NIGERIA", "≈ 238 million", "Nigeria!"),
            ("🇧🇷", "BRAZIL", "≈ 213 million", "Brazil!"),
            ("🇧🇩", "BANGLADESH", "≈ 176 million", "Bangladesh!"),
            ("🇷🇺", "RUSSIA", "≈ 144 million", "Russia!"),
            ("🇪🇹", "ETHIOPIA", "≈ 135 million", "Ethiopia!"),
        ],
    },
}

ROW_Y0, ROW_H = 470, 106   # 10 rows: 470 .. 1530 (kept clear of the Shorts title area)
X_NUM, X_FLAG, X_NAME, X_MAX = 172, 257, 327, 880   # stays left of the like/comment buttons


def outlined(text, size, fill=(255, 255, 255), stroke=7, weight="Black"):
    return text_img(text, font(weight, size), fill=fill, stroke=stroke, stroke_fill=(0, 0, 0))


def sfx_drumroll(dur=2.4):
    """Snare roll that speeds up, for the #1 reveal."""
    out = np.zeros(int(dur * SR))
    rng = np.random.default_rng(4)
    t, gap = 0.0, 0.09
    while t < dur - 0.05:
        n = int(0.06 * SR)
        hit = highpass(rng.standard_normal(n), 1500) * np.exp(-tt(0.06) * 60)
        hit += 0.4 * np.sin(2 * np.pi * 190 * tt(0.06)) * np.exp(-tt(0.06) * 40)
        i = int(t * SR)
        amp = 0.35 + 0.65 * (t / dur)
        out[i:i + n] += hit[: len(out) - i] * amp
        t += gap
        gap = max(0.035, gap * 0.96)
    return out / (np.abs(out).max() + 1e-9) * 0.6


def make_bg():
    bg = vgradient(W, H, (28, 56, 140), (10, 18, 60)).convert("RGBA")
    bg.alpha_composite(radial_glow(W, H, W / 2, 700, 900, (90, 150, 255), 0.35))
    # faint globe pattern for texture
    tile = emoji("🌍", 90)
    tile.putalpha(tile.getchannel("A").point(lambda v: v * 0.07))
    for row, y in enumerate(range(-40, H + 100, 150)):
        for x in range(-60 + (75 if row % 2 else 0), W + 100, 150):
            paste_center(bg, tile, x, y)
    return bg


class RankingScene(mv.Scene):
    def __init__(self, tts, spec):
        super().__init__()
        self.items = spec["items"]
        n = len(self.items)
        self.bg = make_bg()
        self.title = outlined(spec["title"], 150 if len(spec["title"]) < 9 else 120, fill=YELLOW, stroke=10)
        self.subtitle = outlined(spec["subtitle"], 54, stroke=5)
        self.unit = text_img(spec["unit"].upper(), font("Bold", 30), fill=(200, 215, 255))

        hook = tts.say(spec["hook"], speed=1.12)
        self.voices.append((0.1, hook))
        self.sounds.append((0.0, sfx_whoosh(0.5), 0.8))
        t = 0.1 + len(hook) / SR + 0.15
        self.events = []  # (rank, t_ask, t_reveal)
        for rank in range(n, 0, -1):
            final = rank == 1
            ask = tts.say("And number one..." if final else f"Number {rank}.", speed=1.15)
            say = tts.say(self.items[rank - 1][3], speed=1.12)
            self.voices.append((t, ask))
            pause = 2.4 if final else 1.25  # time to guess
            t_rev = t + len(ask) / SR + pause
            if final:
                self.sounds.append((t_rev - 2.4, sfx_drumroll(2.4), 1.0))
            else:
                self.sounds += [(t_rev - 1.0, sfx_tick(), 0.8), (t_rev - 0.5, sfx_tick(high=True), 0.9)]
            self.sounds += [(t_rev, sfx_ding() if not final else sfx_fanfare(), 0.9), (t_rev, sfx_pop(), 0.8)]
            self.voices.append((t_rev + 0.1, say))
            self.events.append((rank, t, t_rev))
            t = t_rev + 0.1 + len(say) / SR + 0.12
        self.dur = t + 1.6
        self.reveal_at = {r: tr for r, _, tr in self.events}
        self.ask_at = {r: ta for r, ta, _ in self.events}

        self.nums, self.names, self.stats, self.flags = {}, {}, {}, {}
        for rank in range(1, n + 1):
            flag, name, stat, _ = self.items[rank - 1]
            col = GOLD if rank == 1 else (255, 255, 255)
            self.nums[rank] = outlined(f"{rank})", 78, fill=col, stroke=7)
            size = 64
            while font("Black", size).getlength(name) > X_MAX - X_NAME and size > 36:
                size -= 2
            self.names[rank] = outlined(name, size, fill=col, stroke=6)
            self.stats[rank] = text_img(stat, font("Bold", 30, display=False), fill=(255, 226, 120))
            self.flags[rank] = emoji(flag, 66)
        self.qmark = outlined("?", 70, fill=(255, 255, 255), stroke=6)
        self.guess = rounded_card(250, 64, 32, YELLOW + (255,))
        paste_center(self.guess, text_img("GUESS!", font("Black", 40), fill=NAVY, shadow=False), 125, 33)
        self.confetti = self._confetti()

    @staticmethod
    def _confetti():
        r = random.Random(2)
        cols = [(255, 82, 96), (64, 150, 255), (255, 214, 10), (46, 204, 113), (255, 255, 255)]
        parts = []
        for _ in range(90):
            pc = Image.new("RGBA", (18, 30), r.choice(cols) + (255,))
            parts.append((pc, r.uniform(0, W), r.uniform(-500, -20), r.uniform(-120, 120), r.uniform(500, 900),
                          r.uniform(0, 360), r.uniform(-400, 400)))
        return parts

    def render(self, t):
        im = self.bg.copy()
        k = ease_out_back(t / 0.45)
        paste_center(im, scaled(self.title, k * (1 + 0.02 * math.sin(t * 4))), W / 2, 225)
        paste_center(im, self.subtitle, W / 2, 335, clamp((t - 0.2) / 0.3))
        paste_center(im, self.unit, W / 2, 395, clamp((t - 0.3) / 0.3))
        d = ImageDraw.Draw(im)
        current = None
        for rank, ta, tr in self.events:
            if ta <= t < tr:
                current = rank
        for rank in range(1, len(self.items) + 1):
            cy = ROW_Y0 + (rank - 0.5) * ROW_H
            rows_in = ease_out_cubic((t - 0.15 - 0.04 * rank) / 0.35)
            x_off = -400 * (1 - rows_in)
            tr = self.reveal_at[rank]
            if rank == current:  # highlight the slot being guessed
                pulse = 0.5 + 0.5 * math.sin(t * 10)
                bar = rounded_card(W - 100, ROW_H - 10, 26, (255, 214, 10, int(40 + 40 * pulse)),
                                   outline=YELLOW + (255,), width=4)
                im.alpha_composite(bar, (50, int(cy - (ROW_H - 10) / 2)))
            elif t >= tr and rank == 1:
                glow = 0.5 + 0.5 * math.sin(t * 6)
                bar = rounded_card(W - 100, ROW_H - 10, 26, (255, 200, 40, int(50 + 40 * glow)),
                                   outline=GOLD + (255,), width=5)
                im.alpha_composite(bar, (50, int(cy - (ROW_H - 10) / 2)))
            num = self.nums[rank]
            im.alpha_composite(num, (int(X_NUM - num.width + 24 + x_off), int(cy - num.height / 2)))
            if t >= tr:
                rv = t - tr
                fs = ease_out_back(rv / 0.35)
                paste_center(im, scaled(self.flags[rank], fs), X_FLAG + 10, cy)
                nm = self.names[rank]
                slide = (1 - ease_out_cubic(rv / 0.3)) * 120
                pop = 1 + 0.25 * (1 - ease_out_cubic(rv / 0.35))
                nmi = scaled(nm, pop)
                im.alpha_composite(nmi, (int(X_NAME - 24 + slide), int(cy - 14 - nmi.height / 2)))
                st = self.stats[rank]
                a = clamp((rv - 0.2) / 0.3)
                if a > 0:
                    paste_center(im, st, X_NAME - 24 + st.width / 2 + 2, cy + 33, a)
            elif rank == current:
                paste_center(im, self.qmark, X_FLAG + 10, cy, 0.9)
                gk = ease_out_back((t - self.ask_at[rank]) / 0.3)
                paste_center(im, scaled(self.guess, gk), X_NAME + 125, cy)
        # confetti for #1
        r1 = t - self.reveal_at[1]
        if r1 > 0:
            for pc, x, y, vx, vy, rot, vr in self.confetti:
                yy = y + vy * r1
                if yy > H + 40:
                    continue
                spr = pc.rotate(rot + vr * r1, expand=True)
                paste_center(im, spr, x + vx * r1 + 30 * math.sin(r1 * 5 + rot), yy)
        return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", default="biggest", choices=list(LISTS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--stills", default=None)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    out = args.out or os.path.join(HERE, f"short_countries_{args.list}.mp4")

    tts = mv.TTS()
    scene = RankingScene(tts, LISTS[args.list])
    scenes, starts, total = [scene], [0.0], scene.dur
    print(f"Duration {total:.1f}s")
    if total > MAX_LEN:
        sys.exit(f"Too long for a Short ({total:.1f}s)")
    mv.G["scenes"], mv.G["starts"] = scenes, starts

    if args.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in args.stills.split(","):
            p = os.path.join(d, f"rank_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return

    work = os.path.join(mv.CACHE_DIR, "render_rank")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mv.mix_audio(scenes, starts, total))
    nframes = int(total * FPS)
    n = max(1, args.workers)
    bounds = [round(nframes * k / n) for k in range(n + 1)]
    jobs = [(k, bounds[k], bounds[k + 1], os.path.join(work, f"part{k}.mp4")) for k in range(n)]
    with mp.get_context("fork").Pool(n) as pool:
        parts = pool.map(mv.render_chunk, jobs)
    lst = os.path.join(work, "parts.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", out], check=True)
    print(f"Done: {out}")


if __name__ == "__main__":
    main()
