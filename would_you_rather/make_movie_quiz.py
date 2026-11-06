#!/usr/bin/env python3
""""GUESS THE MOVIE BY EMOJIS" quiz Short (1080x1920) on the Quizzies logo background.

Emoji clues pop up one by one on a cinema screen with curtains, a timer drains,
Wordle-style letter tiles hint the title, then the tiles flip to the answer
with confetti and a short fact. 10 movies + a bonus, difficulty banners, and an
ending that loops back into the first frame. Non-verbal (music + SFX only).
Emoji art: Noto Emoji 3D by Google (Apache 2.0), in movie_art/.

    python3 make_movie_quiz.py
    python3 make_movie_quiz.py --stills 0,1,3.6 --no-bg
    python3 make_movie_quiz.py --cover
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
import make_map_quiz as mm  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_odd_one_out as oo  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, RED, VIOLET, join, rfont, rtext  # noqa: E402
from make_video import clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center, rounded_card, \
    scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
ART = os.path.join(HERE, "movie_art")
NOTO = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/{}/png/512/emoji_u{}.png"
SCREEN_C, SCREEN_W, SCREEN_H = (540, 760), 900, 540
TIMER_Y, TILE_Y, FACT_Y = 1180, 1300, 1415
EMOJI_T0, EMOJI_DT, DRAIN0, HINT = 0.15, 0.25, 0.9, 1.6
TIERS = mm.TIERS

MOVIES = [  # title, emoji codes, fact line, tier
    ("FINDING NEMO", ["1f50d", "1f420"], "2003 · Dory can't remember anything", "EASY"),
    ("THE LION KING", ["1f981", "1f451"], "1994 · 'Simba' means lion in Swahili", "EASY"),
    ("FROZEN", ["2744", "1f478", "26c4"], "2013 · 'Let It Go' won an Oscar", "EASY"),
    ("TOY STORY", ["1f9f8", "1f4d6"], "1995 · the first fully computer-animated film", "MEDIUM"),
    ("UP", ["1f3e0", "1f388", "1f474"], "2009 · it opened the Cannes Film Festival", "MEDIUM"),
    ("HARRY POTTER", ["1f453", "26a1", "1f9d9"], "2001 · the series has 8 movies", "MEDIUM"),
    ("JURASSIC PARK", ["1f996", "1f334", "1f3de"], "1993 · directed by Steven Spielberg", "HARD"),
    ("TITANIC", ["1f6a2", "1f9ca", "1f494"], "1997 · it won 11 Oscars", "HARD"),
    ("THE HUNGER GAMES", ["1f3f9", "1f467", "1f525"], "2012 · Katniss is an expert archer", "HARD"),
    ("BACK TO THE FUTURE", ["1f519", "1f697", "23f0"], "1985 · the DeLorean needs 88 mph", "INSANE"),
    ("SHREK", ["1f7e2", "1f479", "1f9c5"], "2001 · won the first Oscar for Best Animated Film", "BONUS"),
]


def art(code, size):
    path = os.path.join(ART, code + ".png")
    if not os.path.exists(path):
        os.makedirs(ART, exist_ok=True)
        try:
            urllib.request.urlretrieve(NOTO.format("3D", code), path)
        except Exception:
            urllib.request.urlretrieve(NOTO.format("2D", code), path)
    return Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)


def cinema_screen():
    """Cinema screen with a gold frame, red curtains and a top valance (drawn once)."""
    ss = 2
    w, h = SCREEN_W + 140, SCREEN_H + 150
    im = Image.new("RGBA", (w * ss, h * ss))
    d = ImageDraw.Draw(im)
    x0, y0 = 70 * ss, 95 * ss
    x1, y1 = x0 + SCREEN_W * ss, y0 + SCREEN_H * ss
    d.rounded_rectangle((x0 - 16 * ss, y0 - 16 * ss, x1 + 16 * ss, y1 + 16 * ss), 34 * ss, fill=(255, 196, 60, 255),
                        outline=INK + (255,), width=6 * ss)
    scr = np.zeros(((y1 - y0), (x1 - x0), 4), np.uint8)
    yy, xx = np.mgrid[0:y1 - y0, 0:x1 - x0].astype(np.float32)
    r = np.hypot((xx - (x1 - x0) / 2) / ((x1 - x0) / 2), (yy - (y1 - y0) / 2) / ((y1 - y0) / 2))
    g = np.clip(1 - r * 0.8, 0, 1)
    scr[..., 0] = (250 * g + 30 * (1 - g)).astype(np.uint8)
    scr[..., 1] = (246 * g + 28 * (1 - g)).astype(np.uint8)
    scr[..., 2] = (236 * g + 60 * (1 - g)).astype(np.uint8)
    scr[..., 3] = 255
    s = Image.fromarray(scr, "RGBA")
    m = Image.new("L", s.size)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, s.width - 1, s.height - 1), 22 * ss, fill=255)
    im.paste(s, (x0, y0), m)
    for side in (0, 1):  # curtains with folds
        cw = 130 * ss
        cx0 = 0 if side == 0 else w * ss - cw
        for k in range(6):
            fx = cx0 + k * cw / 6
            shade = 0.75 + 0.25 * math.sin(k * 1.9)
            col = (int(205 * shade), int(28 * shade), int(52 * shade), 255)
            bottom = h * ss if side == 0 else h * ss
            sway = (k + 1) * 6 * ss * (1 if side == 0 else -1)
            d.polygon([(fx, 40 * ss), (fx + cw / 6, 40 * ss), (fx + cw / 6 + sway, bottom), (fx + sway, bottom)],
                      fill=col)
        d.line([(cx0 + (cw if side == 0 else 0), 40 * ss), (cx0 + (cw if side == 0 else 0), h * ss)],
               fill=INK + (255,), width=4 * ss)
    d.rounded_rectangle((0, 0, w * ss - 1, 70 * ss), 20 * ss, fill=(170, 20, 44, 255), outline=INK + (255,),
                        width=5 * ss)
    for k in range(14):  # valance scallops
        cx = (k + 0.5) * w * ss / 14
        d.ellipse((cx - 42 * ss, 40 * ss, cx + 42 * ss, 100 * ss), fill=(170, 20, 44, 255), outline=INK + (255,),
                  width=4 * ss)
    d.rectangle((0, 30 * ss, w * ss, 70 * ss), fill=(170, 20, 44, 255))
    for k in range(9):  # gold bulbs
        cx = 60 * ss + k * (w - 120) * ss / 8
        d.ellipse((cx - 11 * ss, 24 * ss, cx + 11 * ss, 46 * ss), fill=(255, 230, 120, 255), outline=INK + (255,),
                  width=3 * ss)
    out = im.resize((w, h), Image.LANCZOS)
    sh = Image.new("RGBA", (w + 80, h + 80))
    sh.alpha_composite(rounded_card(w, h, 40, (0, 0, 0, 170)), (40, 58))
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    sh.alpha_composite(out, (40, 40))
    return sh


class Movie(mv.Scene):
    def __init__(self, idx, q, ui, prev_tier, rng):
        super().__init__()
        title, codes, fact, tier = q
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.reveal = 4.2 if self.bonus else 3.4
        self.dur = 5.4 if self.bonus else 4.6
        n = len(codes)
        size = 290 if n == 2 else 245
        self.size = size
        self.emojis = [art(c, size) for c in codes]
        self.gap = 30 if n == 3 else 50
        self.tiles = mm.Tiles(title, tier in ("HARD", "INSANE", "BONUS"))
        fsz = 40
        while rfont(fsz).getlength(fact) > 780 and fsz > 26:
            fsz -= 1
        body = join(emoji("🎬", 48), rtext(fact, fsz, stroke=0), gap=12)
        self.fact = rounded_card(body.width + 56, body.height + 22, (body.height + 22) // 2, INK + (225,))
        paste_center(self.fact, body, self.fact.width / 2, self.fact.height / 2)
        col, e = TIERS[tier]
        self.count = rtext("BONUS" if self.bonus else f"MOVIE {idx}/10", 44, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, col + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.banner = None
        if tier != prev_tier and idx > 1:
            label = "BONUS: ONLY 1% GET THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 64 if self.bonus else 84, fill=col, stroke=8), emoji(e, 84))
            self.sounds += [(0.05, mq.sfx_boom(), 0.4), (0.05, mq.sfx_levelup(), 0.6)]
        for i in range(n):
            self.sounds.append((EMOJI_T0 + EMOJI_DT * i, mv.sfx_pop(), 0.9))
        self.sounds.append((HINT, mv.sfx_whoosh(0.3), 0.3))
        nt = 5 if self.bonus else 3
        for k in range(nt):
            self.sounds.append((self.reveal - 0.4 * (nt - k), mq.sfx_tock(high=k == nt - 1), 0.9))
        if self.bonus:
            self.sounds.append((self.reveal - 1.25, mv.sfx_riser(1.2), 0.7))
        self.sounds += [(self.reveal, mv.sfx_ding(), 1.0), (self.reveal, mq.sfx_boom(), 0.3),
                        (self.dur - 0.25, mv.sfx_whoosh(0.4), 0.5)]
        for i in range(len(self.tiles.pos)):
            self.sounds.append((self.reveal + 0.07 + 0.035 * i, mv.sfx_click(), 0.45))
        cols = [CYAN, PINK, GOLD, VIOLET, (255, 255, 255)]
        self.conf = [(rng.uniform(-1, 1) * 650, rng.uniform(-1250, -450), rng.randint(12, 24), rng.choice(cols),
                      rng.uniform(0, 3)) for _ in range(46)]

    def render(self, t):
        im = Image.new("RGBA", (W, H))
        rv = t - self.reveal
        out = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
        ta = t + 0.6 if self.idx == 1 else t  # the very first frame already shows the screen and the hook
        d = ImageDraw.Draw(im)
        # header: count, tag, title
        paste_center(im, self.count, 70 + self.count.width / 2 - 24, 150)
        paste_center(im, self.tag, W - 70 - self.tag.width / 2, 150)
        paste_center(im, self.ui["title"], W / 2, 250)
        # the cinema screen slides in; emoji clues pop on it
        k = ease_out_back(ta / 0.35) * (1 - out)
        paste_center(im, scaled(self.ui["screen"], 0.9 + 0.1 * k), SCREEN_C[0], SCREEN_C[1] + 30 * (1 - k), k)
        n = len(self.emojis)
        total = n * self.size + (n - 1) * self.gap
        for i, e in enumerate(self.emojis):
            ke = ease_out_back((ta - EMOJI_T0 - EMOJI_DT * i) / 0.3, 2.0) * (1 - out)
            if ke <= 0.01:
                continue
            x = W / 2 - total / 2 + self.size / 2 + i * (self.size + self.gap)
            bob = 8 * math.sin(t * 4 + i * 1.3)
            if rv > 0:
                bob -= 40 * math.sin(math.pi * clamp((rv - 0.05 * i) / 0.35))
            paste_center(im, scaled(e, ke).rotate(5 * math.sin(t * 3 + i), Image.BICUBIC, expand=True), x,
                         SCREEN_C[1] + 40 + bob)
        # timer
        frac = 1.0 if t < DRAIN0 else max(0.0, 1 - (t - DRAIN0) / (self.reveal - DRAIN0))
        if rv < 0:
            x0, x1, bh = 160, 920, 26
            d.rounded_rectangle((x0 - 5, TIMER_Y - bh / 2 - 5, x1 + 5, TIMER_Y + bh / 2 + 5), 18, fill=INK + (235,))
            colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
            if frac > 0.01:
                d.rounded_rectangle((x0, TIMER_Y - bh / 2, x0 + (x1 - x0) * frac, TIMER_Y + bh / 2), 13,
                                    fill=colr + (255,))
            paste_center(im, self.ui["clock"], x1 + 62, TIMER_Y)
        if self.idx == 1 and ta < 2.6:  # hook
            a = 1 - clamp((ta - 2.2) / 0.4)
            paste_center(im, self.ui["hook"], W / 2, 375, a)
        if self.banner is not None and 0.05 < t < 1.15:
            tb = t - 0.05
            s = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.18))
            a = clamp(tb / 0.08) * (1 - clamp((tb - 0.85) / 0.25))
            paste_center(im, scaled(self.banner, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 375, a)
        if out < 1:
            self.tiles.draw(im, t - HINT, rv)
        if rv > 0:
            for vx, vy, sz, cc, spin in self.conf:
                px, py = W / 2 + vx * rv, SCREEN_C[1] + vy * rv + 2300 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            fk = ease_out_back((rv - 0.4) / 0.3) * (1 - out)
            if fk > 0.01:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            f = 1 - clamp(rv / 0.18)
            if f > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(120 * f))))
        return im


class Ending(mv.Scene):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.dur = 4.6
        logo = Image.open(os.path.join(HERE, "profile_picture.png")).convert("RGBA").resize((120, 120), Image.LANCZOS)
        logo.putalpha(mv.circle(120, (255, 255, 255, 255)).getchannel("A"))
        self.brand = join(logo, rtext("QUIZZIES", 60, stroke=6), gap=18)
        self.title = rtext("HOW MANY?", 124, fill=CYAN, stroke=11)
        tiers = [("0-3", "Never watches movies", "😴"), ("4-6", "Casual viewer", "🍿"),
                 ("7-9", "Movie buff", "🎬"), ("10", "Film genius", "🏆")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            col = PINK if i == 3 else (255, 255, 255)
            row = rounded_card(860, 110, 55, INK + (215,), outline=(col if i == 3 else (90, 70, 130)) + (255,),
                               width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 55), sc, font=rfont(60), fill=col, anchor="lm")
            size = 56
            while rfont(size, "SemiBold").getlength(label) > 520 and size > 36:
                size -= 2
            dr.text((190, 55), label, font=rfont(size, "SemiBold"), fill=col, anchor="lm")
            row.alpha_composite(emoji(e, 62), (860 - 100, 24))
            self.rows.append(row)
            self.sounds.append((0.2 + 0.13 * i, mv.sfx_pop(), 0.7))
        self.bonus = join(rtext("+ Shrek = LEGEND", 58, fill=GOLD, stroke=6), emoji("👑", 62))
        self.cta = join(rtext("comment your score", 58, stroke=6), emoji("👇", 62))
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.6), (0.05, mq.sfx_levelup(), 0.9), (1.05, mq.sfx_pling(), 0.7)]

    def render(self, t):
        im = Image.new("RGBA", (W, H))
        out = clamp((t - (self.dur - 0.45)) / 0.4)  # hand over to the first frame of the video
        a = 1 - out
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(80 * a))))
        paste_center(im, self.brand, W / 2, 330, clamp(t / 0.15) * a)
        paste_center(im, scaled(self.title, ease_out_back((t + 0.1) / 0.3)), W / 2, 490, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - 0.2 - 0.13 * i) / 0.3)
            if k > 0:
                paste_center(im, row, W / 2 + (1 - k) * 120, 660 + i * 128, k * a)
        paste_center(im, scaled(self.bonus, ease_out_back((t - 0.85) / 0.3)), W / 2, 1200, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.05) / 0.3) * (1 + 0.03 * math.sin(t * 8))), W / 2,
                     1300, a)
        if out > 0:
            first = self.ui["first"].render(0.0)
            first.putalpha(first.getchannel("A").point(lambda v: int(v * out)))
            im.alpha_composite(first)
        return im


def mix_audio(scenes, starts, total, kind="phonk"):
    """SFX + background music: 'phonk' (original, music.py), 'chiptune', or 'none' (add a trending sound in-app)."""
    if kind == "chiptune":
        return mq.mix(scenes, starts, total, "chiptune")
    import music
    n = int(total * mv.SR) + mv.SR
    fx = np.zeros(n)
    for sc, st in zip(scenes, starts):
        for at, arr, g in sc.sounds:
            i = int((st + at) * mv.SR)
            fx[i:i + len(arr)] += arr[: n - i] * g
    fx /= np.abs(fx).max() + 1e-9
    if kind == "none":
        mix = 0.9 * fx
    else:
        mus = np.zeros(n)
        m = music.make_phonk(total)
        mus[:len(m)] = m
        mix = np.tanh(1.1 * (0.55 * mus + 0.6 * fx)) / np.tanh(1.1)
    return (np.clip(np.stack([mix, mix], 1), -1, 1) * 32767).astype(np.int16)


def build():
    ui = {"screen": cinema_screen(), "title": join(rtext("GUESS THE MOVIE", 82, stroke=8), emoji("🎬", 84)),
          "hook": join(rtext("only 1% get 10/10", 64, fill=PINK, stroke=7), emoji("😳", 68)),
          "clock": emoji("⏰", 64)}
    rng = random.Random(9)
    scenes, prev = [], None
    for i, q in enumerate(MOVIES, 1):
        scenes.append(Movie(i, q, ui, prev, rng))
        prev = q[3]
    ui["first"] = scenes[0]
    scenes.append(Ending(ui))
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(full, ui, path):
    base = cq.bg_frame(full, 2.0).convert("RGBA") if full else Image.new("RGBA", (W, H), (20, 40, 100, 255))
    paste_center(base, rtext("GUESS THE", 130, stroke=12), W / 2, 240)
    paste_center(base, join(rtext("MOVIE", 210, fill=CYAN, stroke=16), emoji("🎬", 170)), W / 2, 420)
    paste_center(base, join(rtext("only 1% get 10/10", 74, fill=PINK, stroke=8), emoji("😳", 78)), W / 2, 590)
    paste_center(base, ui["screen"], SCREEN_C[0], 1020)
    for i, c in enumerate(("1f519", "1f697", "23f0")):
        paste_center(base, art(c, 210), W / 2 + (i - 1) * 250, 1060 + 10 * (i % 2))
    tiles = mm.Tiles("BACK TO THE FUTURE", True)
    mm.TILE_Y = 1480
    tiles.draw(base, 1.0, -1.0)
    mm.TILE_Y = TILE_Y
    base.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_movie_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--no-bg", action="store_true")
    ap.add_argument("--music", default="phonk", choices=["phonk", "chiptune", "none"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    mm.TILE_Y = TILE_Y
    scenes, starts, total, ui = build()
    print(f"Duration {total:.1f}s")
    work = os.path.join(mv.CACHE_DIR, "render_movie")
    os.makedirs(work, exist_ok=True)
    full = None if a.no_bg else oo.logo_bg_full(total, work)
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.cover:
        make_cover(full, ui, os.path.join(HERE, "movie_quiz_cover.jpg"))
        return
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"mov_{float(s):06.2f}.png")
            oo.compose(scenes, starts, float(s), full).save(p)
            print(p)
        return
    for f in os.listdir(work):
        if f.startswith("part") or f.endswith(".wav") or f.endswith(".txt") or f == "joined.mp4":
            os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mix_audio(scenes, starts, total, a.music))
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
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(mv.SR), "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", tmp], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-c:v", "libx264", "-crf", "23", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.out], check=True)
    print(f"Done: {a.out}")


if __name__ == "__main__":
    main()
