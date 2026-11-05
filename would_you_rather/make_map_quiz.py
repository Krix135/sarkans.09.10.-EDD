#!/usr/bin/env python3
""""name this country" spinning-globe quiz Short (1080x1920), fast 3.5 s rhythm.

Each country: the globe zooms out, spins and zooms in (1 s), the country glows,
a thin timer drains white -> cyan -> pink with three ticks, then the flag fills
the country's shape and the name + a fun fact appear. SFX only, no music.
Borders: Natural Earth 1:50m (public domain). Flags: public domain.

    python3 make_map_quiz.py
    python3 make_map_quiz.py --stills 0,1,2.9
    python3 make_map_quiz.py --cover
"""

import argparse
import math
import multiprocessing as mp
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import globe as G  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_video import SR, clamp, ease_out_back, ease_out_cubic, paste_center, scaled, text_img  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
FONT = os.path.join(HERE, "models", "Fredoka.ttf")
FLAG_DIR = os.path.join(HERE, "flags")
CENTER = (540, 860)
INK = (34, 18, 52)
CYAN, PINK = (90, 225, 255), (255, 90, 170)
Q_LEN, FLY, DRAIN0, REVEAL = 3.5, 1.0, 1.0, 2.65
TICKS = (1.4, 1.85, 2.25)
START_VIEW = (G.unit(-25, 30), 620.0)

COUNTRIES = [  # map code, flag file, name, fun fact (none of these are in the reference video)
    ("ITA", "IT", "ITALY", "it has more UNESCO sites than any other country"),
    ("GBR", "GB", "UNITED KINGDOM", "nowhere is more than 113 km from the sea"),
    ("MEX", "MX", "MEXICO", "parts of its capital sink 50 cm every year"),
    ("EGY", "EG", "EGYPT", "95% of people live along the Nile"),
    ("CHL", "CL", "CHILE", "4,300 km long, only 177 km wide on average"),
    ("TUR", "TR", "TURKEY", "its biggest city sits on two continents"),
    ("MDG", "MG", "MADAGASCAR", "90% of its wildlife lives nowhere else"),
    ("NZL", "NZ", "NEW ZEALAND", "there are about 5 sheep per person"),
    ("MNG", "MN", "MONGOLIA", "the emptiest country on Earth"),
    ("KAZ", "KZ", "KAZAKHSTAN", "the biggest landlocked country on Earth"),
]

_f = {}


FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/fredoka/Fredoka%5Bwdth%2Cwght%5D.ttf"


def rfont(size, weight="Bold"):
    key = (size, weight)
    if not os.path.exists(FONT):
        import urllib.request
        os.makedirs(os.path.dirname(FONT), exist_ok=True)
        urllib.request.urlretrieve(FONT_URL, FONT)
    if key not in _f:
        f = ImageFont.truetype(FONT, size)
        f.set_variation_by_name(weight)
        _f[key] = f
    return _f[key]


def rtext(text, size, fill=(255, 255, 255), stroke=None, weight="Bold"):
    return text_img(text, rfont(size, weight), fill=fill, stroke=stroke if stroke is not None else max(4, size // 11),
                    stroke_fill=INK)


def fit_text(text, size, max_w, **kw):
    while rfont(size).getlength(text) > max_w and size > 30:
        size -= 2
    return rtext(text, size, **kw)


class Camera:
    """Zoom out to the whole planet, spin, zoom in; then a slow push-in."""

    def __init__(self, a, b):
        (self.ca, self.Ra), (self.cb, self.Rb) = a, b
        self.Rmid = min(620.0, self.Ra, self.Rb)

    def at(self, t):
        if t < FLY:
            k = clamp(t / FLY)
            e = k * k * (3 - 2 * k)
            c = G.slerp(self.ca, self.cb, e)
            la, lb, lm = math.log(self.Ra), math.log(self.Rb), math.log(self.Rmid)
            if k < 0.5:  # out for the first half, in for the second
                R = math.exp(la + (lm - la) * ease_out_cubic(k / 0.5))
            else:
                R = math.exp(lm + (lb - lm) * ease_out_cubic((k - 0.5) / 0.5))
            return c, R
        return self.cb, self.Rb * (1 + 0.07 * clamp((t - FLY) / (Q_LEN - FLY)))


class Question(mv.Scene):
    dur = Q_LEN

    def __init__(self, idx, q, prev_view, globe, ui):
        super().__init__()
        code, fcode, name, fact = q
        self.idx, self.globe, self.ui = idx, globe, ui
        c, self.near, _ = globe.world.country(code)
        self.view = (c, G.zoom_for(globe.world, c, self.near, W, H, 0.36, 0.22))
        self.cam = Camera(prev_view, self.view)
        self.flag = Image.open(os.path.join(FLAG_DIR, fcode + ".png")).convert("RGBA")
        self.name = fit_text(name, 112, 860)
        self.fact = fit_text(fact, 46, 860, fill=CYAN, stroke=5)
        self.count = rtext(f"{idx}/10", 46, stroke=5)
        for k, tk in enumerate(TICKS):
            self.sounds.append((tk, mq.sfx_tock(high=k == 2), 0.9))
        self.sounds += [(REVEAL, mv.sfx_ding(), 1.0), (REVEAL, mv.sfx_pop(), 0.8),
                        (Q_LEN - 0.25, mv.sfx_whoosh(0.5), 0.55)]
        if idx == 1:
            self.sounds.append((0.0, mv.sfx_pop(), 0.9))

    def render(self, t):
        rv = t - REVEAL
        c, R = self.cam.at(t)
        hl = clamp((t - FLY + 0.35) / 0.35)
        fa = clamp(rv / 0.2) if rv > 0 else 0.0
        im = self.globe.render(c, R, CENTER, self.near, hl, self.flag, fa)
        im.alpha_composite(self.ui["shade"])
        paste_center(im, self.count, 92, 222)  # count + thin draining timer bar
        d = ImageDraw.Draw(im)
        x0, x1, y, bh = 160, 1000, 222, 22
        frac = 1.0 if t < DRAIN0 else max(0.0, 1 - (t - DRAIN0) / (REVEAL - DRAIN0))
        d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
        col = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
        if frac > 0.01:
            d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 11, fill=col + (255,))
        if self.idx == 1 and t < 2.6:  # hook, gone before the first reveal
            a = 1 - clamp((t - 2.2) / 0.4)
            paste_center(im, self.ui["hook1"], W / 2, 330, a)
            paste_center(im, self.ui["hook2"], W / 2, 405, a)
        if rv > 0:
            k = ease_out_cubic(rv / 0.3)
            paste_center(im, scaled(self.name, 1.15 - 0.15 * k), W / 2, 1290, clamp(rv / 0.25))
            paste_center(im, self.fact, W / 2, 1375, clamp((rv - 0.1) / 0.25))
        return im


class Ending(mv.Scene):
    def __init__(self):
        super().__init__()
        self.dur = 3.6
        self.bg = mv.vgradient(W, H, (255, 240, 212), (250, 222, 182)).convert("RGBA")
        logo = Image.open(os.path.join(HERE, "profile_picture.png")).convert("RGBA").resize((150, 150), Image.LANCZOS)
        logo.putalpha(mv.circle(150, (255, 255, 255, 255)).getchannel("A"))
        self.bg.alpha_composite(logo, (225, 225))
        brand = rtext("QUIZZIES", 64, stroke=6)
        self.bg.alpha_composite(brand, (395 - 24, 252 - brand.height // 2))
        sub = rtext("subscribe for more!", 38, fill=PINK, stroke=4)
        self.bg.alpha_composite(sub, (397 - 24, 330 - sub.height // 2))
        self.title = rtext("HOW MANY?", 120, stroke=10)
        tiers = [("0-3", "Tourist"), ("4-5", "Backpacker"), ("6-7", "Explorer"), ("8-9", "Map nerd"),
                 ("10", "Human globe")]
        self.rows = []
        for i, (sc, label) in enumerate(tiers):
            col = PINK if i == 4 else INK
            row = Image.new("RGBA", (760, 110))
            d = ImageDraw.Draw(row)
            d.text((0, 55), sc, font=rfont(66), fill=col, anchor="lm")
            d.text((200, 55), label, font=rfont(66, "SemiBold"), fill=col, anchor="lm")
            self.rows.append(row)
            self.sounds.append((0.25 + 0.15 * i, mv.sfx_pop(), 0.7))

    def render(self, t):
        im = self.bg.copy()
        paste_center(im, scaled(self.title, ease_out_back(t / 0.3)), W / 2, 560)
        for i, r in enumerate(self.rows):
            a = clamp((t - 0.25 - 0.15 * i) / 0.25)
            if a > 0:
                paste_center(im, r, 180 + r.width / 2, 755 + i * 130 + (1 - a) * 20, a)
        return im


def shade_overlay():
    a = np.zeros((H, W, 4), np.uint8)
    ys = np.arange(H)
    v = np.clip(1 - ys / 420, 0, 1) ** 1.5 * 120 + np.clip((ys - 1200) / 720, 0, 1) ** 1.3 * 120
    a[..., 3] = v[:, None].astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def build():
    globe = G.GlobeRenderer(W, H)
    ui = {"shade": shade_overlay(), "hook1": rtext("name this country", 84, stroke=8),
          "hook2": rtext("90% will fail", 52, fill=PINK, stroke=6)}
    scenes, view = [], START_VIEW
    for i, q in enumerate(COUNTRIES, 1):
        sc = Question(i, q, view, globe, ui)
        scenes.append(sc)
        c, R = sc.view
        view = (c, R * 1.07)
    scenes.append(Ending())
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, globe, ui


def mix_fx(scenes, starts, total):
    n = int(total * SR) + SR
    fx = np.zeros(n)
    for sc, st in zip(scenes, starts):
        for at, arr, g in sc.sounds:
            i = int((st + at) * SR)
            fx[i:i + len(arr)] += arr[: n - i] * g
    fx = fx / (np.abs(fx).max() + 1e-9) * 0.9
    return (np.stack([fx, fx], 1) * 32767).astype(np.int16)


def make_cover(globe, path):
    c, near, _ = globe.world.country("MDG")
    im = globe.render(G.unit(32, -14), 1250, (540, 1150), near, 1.0)
    im.alpha_composite(shade_overlay())
    paste_center(im, rtext("name this", 140, stroke=12), W / 2, 260)
    paste_center(im, rtext("country", 170, fill=CYAN, stroke=14), W / 2, 430)
    paste_center(im, rtext("90% will fail", 80, fill=PINK, stroke=8), W / 2, 590)
    paste_center(im, rtext("?", 300, stroke=18), 820, 1110)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_map_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    scenes, starts, total, globe, ui = build()
    print(f"Duration {total:.1f}s")
    if a.cover:
        make_cover(globe, os.path.join(HERE, "map_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"map_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    work = os.path.join(mv.CACHE_DIR, "render_map")
    os.makedirs(work, exist_ok=True)
    for f in os.listdir(work):
        os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mix_fx(scenes, starts, total))
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
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-c:v", "libx264", "-crf", "23", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.out], check=True)
    print(f"Done: {a.out}")


if __name__ == "__main__":
    main()
