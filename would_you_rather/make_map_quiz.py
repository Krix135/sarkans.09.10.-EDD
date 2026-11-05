#!/usr/bin/env python3
""""NAME THIS COUNTRY" spinning-globe quiz Short (1080x1920).

The 3D globe spins and zooms from country to country; the country glows yellow,
a timer drains, then the name, flag and a fun fact appear. Borders: Natural
Earth 1:50m (public domain). Flags: public domain (flags/LICENSE).

    python3 make_map_quiz.py
    python3 make_map_quiz.py --stills 0.5,2,5
    python3 make_map_quiz.py --cover
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

import globe as G  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_odd_one_out import bold, pill, with_emoji  # noqa: E402
from make_video import (SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center,  # noqa: E402
                        rounded_card, scaled, sfx_ding, sfx_pop, sfx_whoosh)

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
CENTER = (540, 930)
YELLOW = (255, 222, 40)
CYAN, PINK, VIOLET = (90, 225, 255), (255, 90, 170), (150, 90, 240)
FLIGHT = 1.15
BAR_Y, NAME_Y = 205, 1450
FLAG_DIR = os.path.join(HERE, "flags")
START_VIEW = (G.unit(-20, 25), 640.0)

COUNTRIES = [  # map code, flag, name, seconds, line, spoken answer, fun fact
    ("ITA", "IT", "ITALY", 3, "Name this country!", "Italy!", "It has more UNESCO World Heritage Sites than any other country"),
    ("IND", "IN", "INDIA", 3, "Next one.", "India!", "It has the biggest population on Earth"),
    ("CHL", "CL", "CHILE", 3, "Easy, right?", "Chile!", "It's about 4,300 km long but only 177 km wide on average"),
    ("EGY", "EG", "EGYPT", 3, "What about this one?", "Egypt!", "About 95% of Egyptians live along the Nile"),
    ("MEX", "MX", "MEXICO", 3, "Halfway there!", "Mexico!", "Parts of Mexico City sink up to 50 cm every year"),
    ("MDG", "MG", "MADAGASCAR", 3, "Getting harder...", "Madagascar!",
     "About 90% of its wildlife lives nowhere else on Earth"),
    ("TUR", "TR", "TURKEY", 3, "This one's tricky.", "Turkey!", "Istanbul sits on two continents: Europe and Asia"),
    ("NZL", "NZ", "NEW ZEALAND", 3, "Think fast!", "New Zealand!", "It has about 5 sheep for every person"),
    ("MNG", "MN", "MONGOLIA", 4, "Hard one!", "Mongolia!", "It's the most sparsely populated country in the world"),
    ("KAZ", "KZ", "KAZAKHSTAN", 4, "Final country!", "Kazakhstan!", "It's the biggest landlocked country on Earth"),
]
BANNERS = {5: ("HALFWAY!", "🔥"), 9: ("HARD MODE", "😳"), 10: ("FINAL COUNTRY", "💀")}


def mini_flag(code, h=74):
    src = Image.open(os.path.join(FLAG_DIR, code + ".png")).convert("RGBA")
    w = int(src.width * h / src.height)
    f = src.resize((w, h), Image.LANCZOS)
    out = rounded_card(w + 10, h + 10, 10, (20, 20, 26, 255))
    out.alpha_composite(f, (5, 5))
    return out


def wrap2(text, size, max_w):
    words = text.split()
    f = mv.font("Black", size)
    lines, cur = [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if f.getlength(test) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w_
    lines.append(cur)
    imgs = [bold(ln, size, fill=CYAN, stroke=6) for ln in lines]
    out = Image.new("RGBA", (max(i.width for i in imgs), sum(i.height for i in imgs) - 16 * (len(imgs) - 1)))
    y = 0
    for i in imgs:
        out.alpha_composite(i, ((out.width - i.width) // 2, y))
        y += i.height - 16
    return out


class Camera:
    """Flight path: from view a to view b, zooming out in the middle, then a slow drift-in."""

    def __init__(self, a, b, flight):
        (self.ca, self.Ra), (self.cb, self.Rb) = a, b
        ang = math.acos(float(np.clip(np.dot(self.ca, self.cb), -1, 1)))
        self.Rmid = float(np.clip(780 / (ang + 0.35), 620, min(self.Ra, self.Rb)))
        self.flight = flight

    def at(self, t, hold_len):
        if t < self.flight:
            k = clamp(t / self.flight)
            e = k * k * (3 - 2 * k)
            c = G.slerp(self.ca, self.cb, e)
            la, lb = math.log(self.Ra), math.log(self.Rb)
            base = la + (lb - la) * e
            bump = (math.log(self.Rmid) - (la + lb) / 2) * math.sin(math.pi * k)
            return c, math.exp(base + min(0.0, bump))
        k = clamp((t - self.flight) / max(hold_len, 1e-3))
        return self.cb, self.Rb * (1 + 0.05 * k)


class Question(mv.Scene):
    def __init__(self, tts, idx, q, prev_view, globe, rng):
        super().__init__()
        code, fcode, name, secs, line, said, fact = q
        self.idx, self.secs, self.globe = idx, secs, globe
        c, self.near, _ = globe.world.country(code)
        R = G.zoom_for(globe.world, c, self.near, W, H, 0.36, 0.20)
        self.view = (c, R)
        self.cam = Camera(prev_view, self.view, FLIGHT)
        self.t_cd = FLIGHT + 0.1
        self.reveal = self.t_cd + secs
        v = tts.say(line, speed=1.1)
        self.voices.append((0.2, v))
        a = tts.say(said, speed=1.1)
        self.voices.append((self.reveal + 0.1, a))
        self.dur = self.reveal + max(1.75, 0.1 + len(a) / SR + 0.2)
        self.sounds += [(0.0, sfx_whoosh(FLIGHT * 0.9), 0.8), (FLIGHT - 0.05, sfx_pop(), 0.8)]
        for k in range(secs):
            self.sounds.append((self.t_cd + k, mq.sfx_tock(high=k >= secs - 2), 1.0))
        self.sounds += [(self.reveal, sfx_ding(), 1.0), (self.reveal, mq.sfx_crunch(), 0.6)]
        self.count = bold(f"{idx}/10", 50, stroke=6)
        self.prompt = with_emoji(bold("NAME THIS COUNTRY", 70, stroke=8), "🌍", 70)
        self.hook = with_emoji(bold("90% FAIL THIS", 64, fill=PINK, stroke=7), "😳", 66) if idx == 1 else None
        if idx == 1:
            self.sounds.append((0.05, mq.sfx_boom(), 0.6))
        self.name = bold(name, 128, stroke=12, max_w=980)
        self.flag = mini_flag(fcode)
        self.fact = wrap2(fact, 46, 900)
        self.plus = mq.ptext("+1", 46, fill=CYAN)
        self.banner = None
        if idx in BANNERS:
            t_, e_ = BANNERS[idx]
            self.banner = with_emoji(mq.mc_button(t_, 620, 116, (225, 45, 120) if idx >= 9 else VIOLET, 44),
                                     e_, 96, 6)
            self.sounds.append((0.1, mq.sfx_levelup(), 0.9))
        r = random.Random(idx)
        self.conf = [(r.uniform(-650, 650), r.uniform(-1300, -500), r.randint(14, 24),
                      r.choice([PINK, CYAN, (255, 255, 255), VIOLET])) for _ in range(36)]

    def render(self, t):
        rv = t - self.reveal
        c, R = self.cam.at(t, self.dur - FLIGHT)
        hl = clamp((t - FLIGHT + 0.25) / 0.35)
        if rv > 0:
            hl = 1.0
        im = self.globe.render(c, R, CENTER, self.near, hl)
        if rv > 0:  # reveal flash on the country
            f = 1 - clamp(rv / 0.22)
            if f > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(150 * f))))
        # soft top/bottom shade for readability
        im.alpha_composite(self.globe_shade)
        # header: count + draining bar
        hk = 1.0 if self.idx == 1 else ease_out_back(t / 0.3)
        paste_center(im, scaled(self.count, hk), 100, BAR_Y)
        cd = t - self.t_cd
        frac = 1.0 if cd < 0 else max(0.0, 1 - cd / self.secs)
        d = ImageDraw.Draw(im)
        x0, x1, bh = 175, 1000, 26
        d.rounded_rectangle((x0 - 5, BAR_Y - bh / 2 - 5, x1 + 5, BAR_Y + bh / 2 + 5), 18, fill=(10, 12, 24, 220))
        col = PINK if (0 <= cd and self.secs - cd <= 2) else CYAN
        if frac > 0.01:
            d.rounded_rectangle((x0, BAR_Y - bh / 2, x0 + (x1 - x0) * frac, BAR_Y + bh / 2), 13, fill=col + (255,))
        if rv < 0:
            t0 = t + 1.0 if self.idx == 1 else t  # first frame of the video already shows the hook
            pk = ease_out_back((t0 - 0.1) / 0.3)
            paste_center(im, scaled(self.prompt, pk), W / 2, 310)
            if self.hook is not None:
                paste_center(im, scaled(self.hook, ease_out_back((t0 - 0.35) / 0.3)), W / 2, 395)
        else:
            nk = ease_out_back(rv / 0.28)
            row_w = self.flag.width + 20 + self.name.width
            if row_w > 1040:
                s = 1040 / row_w
            else:
                s = 1.0
            xs = W / 2 - row_w * s / 2
            paste_center(im, scaled(self.flag, nk * s), xs + self.flag.width * s / 2, NAME_Y)
            paste_center(im, scaled(self.name, nk * s), xs + (self.flag.width + 20 + self.name.width / 2) * s, NAME_Y)
            if rv > 0.25:
                paste_center(im, self.plus, min(W - 70, xs + row_w * s + 10), NAME_Y - 80, clamp((rv - 0.25) / 0.15))
            if rv > 0.35:
                paste_center(im, scaled(self.fact, ease_out_back((rv - 0.35) / 0.3)), W / 2,
                             NAME_Y + 95 + self.fact.height / 2)
            for vx, vy, sz, cc in self.conf:
                px, py = W / 2 + vx * rv, CENTER[1] + vy * rv + 2500 * rv * rv
                if py < H:
                    d.rectangle((px, py, px + sz, py + sz), fill=cc + (255,))
        if self.banner is not None and 0.15 < t < 1.15:
            tb = t - 0.15
            bx = W / 2 + (1 - ease_out_cubic(tb / 0.2)) * W - ease_in_cubic((tb - 0.8) / 0.2) * W
            paste_center(im, self.banner.rotate(-4, Image.BICUBIC, expand=True), bx, 560)
        return im


class Ending(mv.Scene):
    def __init__(self, tts, prev_view, globe):
        super().__init__()
        self.globe = globe
        self.cam = Camera(prev_view, START_VIEW, 1.3)
        v = tts.say("How many did you get? Comment your score!", speed=1.1)
        self.voices.append((0.3, v))
        self.dur = max(4.6, 0.3 + len(v) / SR + 1.8)
        self.sounds += [(0.0, sfx_whoosh(1.2), 0.8), (0.4, mq.sfx_levelup(), 0.9)]
        self.t1 = with_emoji(bold("HOW MANY", 120, fill=CYAN, stroke=11), "🤔", 110)
        self.t2 = bold("DID YOU GET?", 116, fill=CYAN, stroke=11)
        rows = [("10/10", "HUMAN GLOBE", "🌍", (225, 45, 120)), ("7-9", "MAP NERD", "🗺", (120, 70, 220)),
                ("4-6", "EXPLORER", "🧭", (20, 150, 190)), ("0-3", "TOURIST", "📸", (90, 90, 120))]
        self.rows = []
        for i, (sc_, label, e, col) in enumerate(rows):
            b = rounded_card(900, 120, 34, col + (245,), outline=(0, 0, 0, 255), width=5)
            st = bold(sc_, 58, stroke=6)
            b.alpha_composite(st, (20, 60 - st.height // 2))
            lb = with_emoji(bold(label, 56, stroke=6), e, 60)
            b.alpha_composite(lb, (900 - 36 - lb.width, 60 - lb.height // 2))
            self.rows.append(b)
            self.sounds.append((0.9 + 0.18 * i, sfx_pop(), 0.7))
        self.cta = with_emoji(bold("COMMENT YOUR SCORE", 66, stroke=7), "👇", 76)
        self.sounds.append((1.8, mq.sfx_pling(), 0.8))

    def render(self, t):
        if t < 1.3:
            c, R = self.cam.at(t, 1.0)
        else:  # keep spinning slowly; ends on the same view the video starts from
            c, R = START_VIEW
            spin = -(self.dur - t) * 0.18
            c = G.unit(-20 + math.degrees(spin), 25)
        im = self.globe.render(c, R, CENTER)
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(110 * clamp((t - 0.6) / 0.4)
                                                                         * (1 - clamp((t - self.dur + 0.5) / 0.4))))))
        a = 1 - clamp((t - (self.dur - 0.45)) / 0.35)
        paste_center(im, scaled(self.t1, ease_out_back((t - 0.5) / 0.35)), W / 2, 330, a)
        paste_center(im, scaled(self.t2, ease_out_back((t - 0.62) / 0.35)), W / 2, 465, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - 0.9 - 0.18 * i) / 0.35)
            paste_center(im, row, W / 2 + (1 - k) * (W if i % 2 else -W), 650 + i * 145, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.8) / 0.4) * (1 + 0.04 * math.sin(t * 8))), W / 2,
                     1290, a)
        return im


def shade_overlay():
    a = np.zeros((H, W, 4), np.uint8)
    ys = np.arange(H)
    v = np.clip(1 - ys / 520, 0, 1) ** 1.4 * 150 + np.clip((ys - 1330) / 590, 0, 1) ** 1.2 * 160
    a[..., 3] = v[:, None].astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def build():
    globe = G.GlobeRenderer(W, H)
    tts = mv.TTS("af_heart", "en-us")
    rng = random.Random(5)
    shade = shade_overlay()
    scenes, view = [], START_VIEW
    for i, q in enumerate(COUNTRIES, 1):
        sc = Question(tts, i, q, view, globe, rng)
        sc.globe_shade = shade
        scenes.append(sc)
        view = sc.view
    scenes.append(Ending(tts, view, globe))
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, globe


def make_cover(globe, path):
    c, near, _ = globe.world.country("MDG")
    im = globe.render(G.unit(30, -12), 1150, (540, 1180), near, 1.0)
    im.alpha_composite(shade_overlay())
    paste_center(im, bold("NAME THIS", 130, stroke=12), W / 2, 230)
    paste_center(im, with_emoji(bold("COUNTRY", 150, fill=CYAN, stroke=13), "🌍", 130), W / 2, 400)
    paste_center(im, mq.mc_button("90% FAIL", 460, 116, (225, 45, 120), 46).rotate(-6, Image.BICUBIC, expand=True),
                 W / 2, 570)
    big = bold("?", 260, fill=(255, 255, 255), stroke=16)
    paste_center(im, big, 810, 1130)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_map_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    scenes, starts, total, globe = build()
    for sc, st in zip(scenes, starts):
        print(f"  {st:6.2f}s  {type(sc).__name__} {getattr(sc, 'idx', '')}")
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
    mv.write_wav(wav, mq.mix(scenes, starts, total, "chiptune"))
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
