#!/usr/bin/env python3
""""FIND THE ODD ONE OUT" emoji puzzle Short (1080x1920) on the channel logo background.

8 levels, grids grow from 4x5 to 8x8 and the difference gets subtler each time.
Emoji art: Noto Emoji 3D by Google (Apache 2.0), cached in odd_art/.

    python3 make_odd_one_out.py
    python3 make_odd_one_out.py --stills 1,4.5 --no-bg
    python3 make_odd_one_out.py --cover
"""

import argparse
import math
import multiprocessing as mp
import os
import random
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import make_capitals_quiz as cq  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_video import (SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, font, paste_center,  # noqa: E402
                        rounded_card, scaled, sfx_ding, sfx_pop, sfx_whoosh, text_img)

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
ART = os.path.join(HERE, "odd_art")
NOTO = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/3D/png/512/emoji_u{}.png"
YELLOW = (255, 222, 40)
T_IN, HOLD = 0.35, 1.35
GRID_C, GRID_MAX = (540, 905), 880
TIMER_Y = 1440

LEVELS = [  # normal, odd, cols, rows, seconds, sub-caption, narration, colour
    ("1f43b", "1f43c", 4, 5, 3, "Warm-up 😎", "Find the odd one out!", (70, 200, 110)),
    ("1f34e", "1f345", 5, 5, 3, "Easy 👌", "Level two.", (70, 200, 110)),
    ("1f34f", "1f350", 5, 6, 4, "Still easy… right? 🤨", "Level three.", (60, 160, 255)),
    ("2b50", "1f31f", 6, 6, 4, "Getting harder…", "Getting harder...", (60, 160, 255)),
    ("1f31b", "1f31c", 6, 7, 5, "Halfway there! 🔥", "Halfway there!", (255, 160, 40)),
    ("1f610", "1f611", 7, 7, 5, "Only geniuses see it 🧠", "Only geniuses see this one.", (255, 160, 40)),
    ("1f600", "1f603", 7, 8, 6, "Almost impossible 😳", "Almost impossible...", (240, 70, 70)),
    ("1f604", "1f601", 8, 8, 7, "FINAL LEVEL 💀", "Final level. Good luck!", (240, 70, 70)),
]


def art(code, size):
    path = os.path.join(ART, code + ".png")
    if not os.path.exists(path):
        os.makedirs(ART, exist_ok=True)
        urllib.request.urlretrieve(NOTO.format(code), path)
    return Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)


def bold(text, size, fill=(255, 255, 255), stroke=9, max_w=None):
    while max_w and font("Black", size).getlength(text) + 2 * stroke > max_w and size > 28:
        size -= 2
    return text_img(text, font("Black", size), fill=fill, stroke=stroke, stroke_fill=(0, 0, 0))


def with_emoji(text_im, e, size, gap=12):
    """Text image followed by a colour emoji (emoji fonts don't mix with Inter)."""
    em = emoji(e, size)
    out = Image.new("RGBA", (text_im.width + em.width + gap, max(text_im.height, em.height)))
    out.alpha_composite(text_im, (0, (out.height - text_im.height) // 2))
    out.alpha_composite(em, (text_im.width + gap, (out.height - em.height) // 2))
    return out


def caption(text, size, fill):
    """'Some words 😎' -> bold text + emoji."""
    parts = text.rsplit(" ", 1)
    if len(parts) == 2 and not parts[1][0].isalnum() and parts[1][0] not in "…!?.":
        return with_emoji(bold(parts[0], size, fill, stroke=7), parts[1], int(size * 1.05))
    return bold(text, size, fill, stroke=7)


def pill(text, col, size=42):
    t = text_img(text, font("Black", size), fill=(255, 255, 255), shadow=False)
    p = rounded_card(t.width + 70, int(size * 1.8), int(size * 0.9), col + (255,), outline=(0, 0, 0, 255), width=5)
    paste_center(p, t, p.width / 2, p.height / 2 + 1)
    return p


class Level(mv.Scene):
    def __init__(self, tts, idx, lv, rng):
        super().__init__()
        normal, odd, cols, rows, secs, sub, said, col = lv
        self.idx, self.cols, self.rows, self.secs = idx, cols, rows, secs
        cell = int(min(GRID_MAX / cols, GRID_MAX / rows))
        self.cell = cell
        size = int(cell * 0.84)
        self.img_n, self.img_o = art(normal, size), art(odd, size)
        allowed = [(c, r) for r in range(rows) for c in range(cols)
                   if not (c == cols - 1 and r >= rows // 2)]   # keep it clear of the Shorts like/comment buttons
        self.odd = rng.choice(allowed)
        pw, ph = cols * cell + 44, rows * cell + 44
        self.panel = rounded_card(pw, ph, 44, (255, 255, 255, 240), outline=(20, 20, 30, 255), width=6)
        sh = Image.new("RGBA", (pw + 60, ph + 60))
        sh.alpha_composite(rounded_card(pw, ph, 44, (0, 0, 0, 150)), (30, 44))
        self.panel_sh = sh.filter(ImageFilter.GaussianBlur(16))
        self.x0 = GRID_C[0] - cols * cell / 2 + cell / 2
        self.y0 = GRID_C[1] - rows * cell / 2 + cell / 2
        self.level_pill = pill(f"LEVEL {idx}/8", col)
        self.title = with_emoji(bold("FIND THE ODD ONE!", 86), "👀", 92)
        self.sub = caption(sub, 56, YELLOW)
        self.pause = with_emoji(bold("Pause if you need more time", 40, stroke=5), "⏸", 44, 10) if idx >= 5 else None
        self.found = with_emoji(bold("FOUND IT?", 80, fill=(120, 255, 120)), "✅", 80)
        self.nums = {(n, red): bold(str(n), 70, fill=(255, 80, 70) if red else (255, 255, 255), stroke=7)
                     for n in range(1, secs + 1) for red in (False, True)}
        v = tts.say(said, speed=1.1)
        self.voices.append((0.12, v))
        self.reveal = T_IN + secs
        self.dur = self.reveal + HOLD
        self.sounds.append((0.0, sfx_whoosh(0.35), 0.6))
        if idx in (4, 6, 8):
            self.sounds.append((0.05, mq.sfx_levelup(), 0.8))
        for k in range(secs):
            self.sounds.append((T_IN + k, mq.sfx_tock(high=k >= secs - 2), 1.0))
        self.sounds += [(self.reveal, sfx_ding(), 1.0), (self.reveal, sfx_pop(), 0.9)]
        r = random.Random(idx * 7)
        self.conf = [(r.uniform(-1, 1) * 700, r.uniform(-1400, -500), r.randint(14, 26),
                      r.choice([YELLOW, (255, 90, 120), (90, 200, 255), (120, 255, 140)])) for _ in range(40)]

    def render(self, t):
        im = Image.new("RGBA", (W, H))
        rv = t - self.reveal
        out = ease_in_cubic((t - (self.dur - 0.25)) / 0.25)
        hk = ease_out_back(t / 0.3) * (1 - out)
        paste_center(im, scaled(self.level_pill, hk), W / 2, 150)
        paste_center(im, scaled(self.title, ease_out_back((t - 0.05) / 0.3) * (1 - out)), W / 2, 262)
        paste_center(im, scaled(self.sub, ease_out_back((t - 0.12) / 0.3) * (1 - out)), W / 2, 365)
        # panel + grid (the same breathing motion for every emoji, so nothing gives the answer away)
        gk = ease_out_back(t / 0.35) * (1 - out)
        if gk > 0.01:
            paste_center(im, scaled(self.panel_sh, gk), GRID_C[0], GRID_C[1] + 6)
            paste_center(im, scaled(self.panel, gk), *GRID_C)
            breath = 1 + 0.02 * math.sin(t * 4)
            for r in range(self.rows):
                for c in range(self.cols):
                    k = ease_out_back((t - 0.05 - 0.012 * (r + c)) / 0.3) * (1 - out)
                    if k <= 0.01:
                        continue
                    is_odd = (c, r) == self.odd
                    img = self.img_o if is_odd else self.img_n
                    x = GRID_C[0] + (self.x0 + c * self.cell - GRID_C[0]) * gk
                    y = GRID_C[1] + (self.y0 + r * self.cell - GRID_C[1]) * gk
                    s = k * breath * (0.97 + 0.03 * math.sin(t * 4 + (r + c) * 0.5))
                    a = 1.0
                    if rv > 0:
                        if is_odd:
                            s *= 1 + 0.45 * ease_out_back(rv / 0.3) + 0.06 * math.sin(rv * 10)
                        else:
                            a = 1 - 0.75 * clamp(rv / 0.25)
                            s *= 1 - 0.12 * clamp(rv / 0.25)
                    if not is_odd or rv <= 0:
                        paste_center(im, scaled(img, s), x, y, a)
            if rv > 0:  # circle the odd one, drawn on top
                c, r = self.odd
                x, y = self.x0 + c * self.cell, self.y0 + r * self.cell
                s = (1 + 0.45 * ease_out_back(rv / 0.3) + 0.06 * math.sin(rv * 10)) * (1 - out)
                rad = self.cell * 0.72 * s * (1 + 0.05 * math.sin(rv * 12))
                ring = Image.new("RGBA", (int(rad * 2 + 40), int(rad * 2 + 40)))
                ImageDraw.Draw(ring).ellipse((20, 20, 20 + 2 * rad, 20 + 2 * rad), fill=(255, 255, 255, 235),
                                             outline=(240, 40, 40, 255), width=max(6, int(self.cell * 0.09)))
                paste_center(im, ring, x, y, clamp(rv / 0.12) * (1 - out))
                paste_center(im, scaled(self.img_o, s), x, y)
                d = ImageDraw.Draw(im)
                for vx, vy, sz, col in self.conf:
                    px, py = x + vx * rv, y + vy * rv + 2600 * rv * rv
                    if py < H:
                        d.rectangle((px, py, px + sz, py + sz), fill=col + (255,))
        # timer bar, then "found it?"
        if rv < 0:
            cd = max(0.0, t - T_IN)
            n = max(1, self.secs - int(cd))
            red = n <= 2
            frac = 1 - clamp(cd / self.secs)
            bw, bh = 700, 40
            x0 = W / 2 - bw / 2 + 50
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((x0 - 6, TIMER_Y - bh / 2 - 6, x0 + bw + 6, TIMER_Y + bh / 2 + 6), 26,
                                fill=(10, 10, 20, 235))
            col = (255, 70, 60) if red else (110, 230, 90)
            if frac > 0.01:
                d.rounded_rectangle((x0, TIMER_Y - bh / 2, x0 + bw * frac, TIMER_Y + bh / 2), 20, fill=col + (255,))
            pop = 1 + 0.35 * (1 - ease_out_cubic((cd % 1) / 0.3))
            paste_center(im, scaled(self.nums[(n, red)], pop * hk), x0 - 70, TIMER_Y)
            if self.pause:
                paste_center(im, self.pause, W / 2, TIMER_Y + 85, 0.9 * hk)
        else:
            paste_center(im, scaled(self.found, ease_out_back(rv / 0.3) * (1 - out)), W / 2, TIMER_Y + 10)
        return im


class Ending(mv.Scene):
    def __init__(self, tts):
        super().__init__()
        v = tts.say("How many did you find? Comment your score!", speed=1.1)
        self.voices.append((0.15, v))
        self.dur = max(4.2, 0.15 + len(v) / SR + 1.6)
        self.sounds += [(0.0, sfx_whoosh(0.4), 0.7), (0.15, mq.sfx_levelup(), 0.9)]
        self.t1 = with_emoji(bold("HOW MANY DID", 104, fill=YELLOW, stroke=10), "🤔", 100)
        self.t2 = bold("YOU FIND?", 130, fill=YELLOW, stroke=11)
        rows = [("8/8", "GENIUS", "🧠", (230, 150, 20)), ("6-7", "EAGLE EYES", "🦅", (60, 110, 220)),
                ("3-5", "NOT BAD", "👍", (60, 170, 70)), ("0-2", "NEED GLASSES", "👓", (120, 120, 130))]
        self.rows = []
        for i, (sc, label, e, col) in enumerate(rows):
            b = rounded_card(900, 124, 36, col + (245,), outline=(0, 0, 0, 255), width=5)
            st = bold(sc, 62, stroke=6)
            b.alpha_composite(st, (40 - 20, 62 - st.height // 2))
            lb = with_emoji(bold(label, 60, fill=YELLOW if i == 0 else (255, 255, 255), stroke=6), e, 64)
            b.alpha_composite(lb, (900 - 36 - lb.width, 62 - lb.height // 2))
            self.rows.append(b)
            self.sounds.append((0.6 + 0.18 * i, sfx_pop(), 0.7))
        self.cta = with_emoji(bold("COMMENT YOUR SCORE", 66, stroke=7), "👇", 76)
        self.sounds.append((1.5, mq.sfx_pling(), 0.8))

    def render(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 70))
        out = clamp((t - (self.dur - 0.3)) / 0.3)
        a = 1 - out
        paste_center(im, scaled(self.t1, ease_out_back(t / 0.35)), W / 2, 330, a)
        paste_center(im, scaled(self.t2, ease_out_back((t - 0.12) / 0.35)), W / 2, 470, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - 0.6 - 0.18 * i) / 0.35)
            paste_center(im, row, W / 2 + (1 - k) * (W if i % 2 else -W), 660 + i * 150, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.5) / 0.4) * (1 + 0.04 * math.sin(t * 8))), W / 2,
                     1300, a)
        return im


def build():
    rng = random.Random(2026)
    tts = mv.TTS("af_heart", "en-us")
    scenes = [Level(tts, i, lv, rng) for i, lv in enumerate(LEVELS, 1)] + [Ending(tts)]
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t


def logo_bg_full(total, work):
    loop = os.path.join(HERE, "quizzies_background_darkblue.mp4")
    if not os.path.exists(loop):
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "make_logo_background.py"), "--color", "darkblue",
                        "--video", "12"], check=True)
    full = os.path.join(work, "bg_full.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", loop, "-t", f"{total:.3f}",
                    "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-g", "30", full], check=True)
    return full


def compose(scenes, starts, t, full):
    k = max(0, np.searchsorted(starts, t, side="right") - 1)
    over = scenes[k].render(min(t - starts[k], scenes[k].dur - 1e-4))
    base = cq.bg_frame(full, t).convert("RGBA") if full else Image.new("RGBA", (W, H), (20, 40, 100, 255))
    base.alpha_composite(over)
    return base.convert("RGB")


def make_cover(scenes, full, path):
    base = cq.bg_frame(full, 3.0).convert("RGBA") if full else Image.new("RGBA", (W, H), (20, 40, 100, 255))
    lv = scenes[5]  # 😐 / 😑 grid, no answer shown
    lv.level_pill = lv.title = lv.sub = Image.new("RGBA", (1, 1))
    lv.pause = None
    g = lv.render(lv.reveal - 2.5)
    g = g.crop((0, 430, W, 1385))  # grid only, no timer
    base.alpha_composite(g, (0, 560))
    paste_center(base, with_emoji(bold("FIND THE", 120, stroke=12), "👀", 120), W / 2, 230)
    paste_center(base, bold("ODD ONE OUT!", 140, fill=YELLOW, stroke=13), W / 2, 380)
    paste_center(base, mq.mc_button("99% FAIL", 460, 116, (210, 30, 30), 46).rotate(-6, Image.BICUBIC, expand=True),
                 W / 2, 1600)
    base.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_odd_one_out.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--no-bg", action="store_true", help="plain background (fast previews)")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    scenes, starts, total = build()
    for sc, st in zip(scenes, starts):
        print(f"  {st:6.2f}s  {type(sc).__name__} {getattr(sc, 'idx', '')}")
    print(f"Duration {total:.1f}s")
    work = os.path.join(mv.CACHE_DIR, "render_odd")
    os.makedirs(work, exist_ok=True)
    full = None if a.no_bg else logo_bg_full(total, work)
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.cover:
        make_cover(scenes, full, os.path.join(HERE, "odd_one_out_cover.jpg"))
        return
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"odd_{float(s):06.2f}.png")
            compose(scenes, starts, float(s), full).save(p)
            print(p)
        return
    for f in os.listdir(work):
        if f.startswith("part") or f.endswith(".wav") or f.endswith(".txt") or f == "joined.mp4":
            os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mq.mix(scenes, starts, total, "chiptune"))
    nframes = int(total * FPS)
    n = max(1, a.workers)
    bounds = [round(nframes * k / n) for k in range(n + 1)]
    jobs = [(k, bounds[k], bounds[k + 1], os.path.join(work, f"part{k}.mp4")) for k in range(n)]
    cq.BG["full"] = full
    with mp.get_context("fork").Pool(n) as pool:
        parts = pool.map(cq.render_chunk_video if full else mv.render_chunk, jobs)
    lst = os.path.join(work, "parts.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    tmp = os.path.join(work, "joined.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", tmp], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-c:v", "libx264", "-crf", "23", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.out], check=True)
    print(f"Done: {a.out}")


if __name__ == "__main__":
    main()
