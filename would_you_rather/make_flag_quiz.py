#!/usr/bin/env python3
""""GUESS THE COUNTRY BY THE FLAG" quiz Short (1080x1920) on the Quizzies logo background.

10 waving flags from easy to hard, a countdown, then the answer (with a trap
or fun fact for the tricky ones). Flags: public-domain images (flags/LICENSE).

    python3 make_flag_quiz.py
    python3 make_flag_quiz.py --stills 2,4 --no-bg
    python3 make_flag_quiz.py --cover
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

import make_capitals_quiz as cq  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_odd_one_out as oo  # noqa: E402
import make_video as mv  # noqa: E402
from make_odd_one_out import bold, pill, with_emoji  # noqa: E402
from make_video import (SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, paste_center, scaled,  # noqa: E402
                        sfx_ding, sfx_pop, sfx_whoosh)

W, H, FPS = 1080, 1920, 30
FLAG_DIR = os.path.join(HERE, "flags")
YELLOW = (255, 222, 40)
T_IN = 0.3
FLAG_Y, OPT_Y, TIMER_Y, PROG_Y = 650, (1000, 1130), 1262, 345
OPT_X, OPT_W, OPT_H = (295, 745), 430, 112
LEVEL_COL = {"EASY": (70, 200, 110), "NORMAL": (60, 160, 255), "MEDIUM": (255, 160, 40), "HARD": (240, 70, 70)}
LETTER_COL = [(255, 95, 95), (70, 150, 255), (255, 190, 40), (90, 200, 120)]

FLAGS = [  # code, option name, level, seconds, line before, spoken answer, extra line, 3 look-alike options, banner
    ("US", "USA", "EASY", 3, "Guess the country by its flag!", "The U.S.A.!", None,
     ("Liberia", "Australia", "UK"), None),
    ("GB", "UK", "EASY", 3, "Next one.", "The United Kingdom!", None,
     ("Australia", "New Zealand", "Iceland"), None),
    ("MX", "Mexico", "EASY", 3, "Easy, right?", "Mexico!", None, ("Italy", "Ireland", "Hungary"), None),
    ("DE", "Germany", "NORMAL", 4, "Normal level.", "Germany!", None, ("Belgium", "Spain", "Austria"),
     ("NORMAL MODE", None)),
    ("IN", "India", "NORMAL", 4, "What about this one?", "India!", None, ("Niger", "Ireland", "Ivory Coast"), None),
    ("KR", "South Korea", "NORMAL", 4, "Halfway there!", "South Korea!", None, ("Japan", "China", "Taiwan"),
     ("HALFWAY!", "🔥")),
    ("AR", "Argentina", "MEDIUM", 4, "Getting harder...", "Argentina!", None, ("Uruguay", "Greece", "Honduras"),
     ("MEDIUM MODE", None)),
    ("GR", "Greece", "MEDIUM", 4, "This one's tricky.", "Greece!", None, ("Uruguay", "Finland", "Israel"), None),
    ("ID", "Indonesia", "HARD", 5, "Hard level!", "Indonesia! Not Monaco!",
     "NOT MONACO!|Their flags are almost identical 🤯", ("Monaco", "Poland", "Singapore"), ("HARD MODE", "😳")),
    ("NP", "Nepal", "HARD", 5, "Final flag!", "Nepal!", "The only national flag|that isn't a rectangle! 🤯",
     ("Bhutan", "Sri Lanka", "Bangladesh"), ("FINAL FLAG", "💀")),
]


def wave_frames(code, max_w=860, max_h=560, n=16):
    """Waving flag frames; keeps transparency so non-rectangular flags (Nepal) look right."""
    src = Image.open(os.path.join(FLAG_DIR, code + ".png")).convert("RGBA")
    s = min(max_w / src.width, max_h / src.height)
    w, h = int(src.width * s), int(src.height * s)
    arr = np.asarray(src.resize((w, h), Image.LANCZOS)).astype(np.float32)
    xs = np.arange(w)
    pad = 18
    out = []
    for k in range(n):
        ph = 2 * math.pi * k / n
        wave = 2 * math.pi * xs / (w * 0.6) - ph
        off = (13 * (0.25 + 0.75 * xs / w) * np.sin(wave)).astype(int)
        shade = 1 + 0.13 * np.cos(wave) * (0.3 + 0.7 * xs / w)
        img = np.zeros((h + 2 * pad, w, 4), np.uint8)
        for x in range(w):
            y0 = pad + off[x]
            img[y0:y0 + h, x, :3] = np.clip(arr[:, x, :3] * shade[x], 0, 255)
            img[y0:y0 + h, x, 3] = arr[:, x, 3]
        fl = Image.fromarray(img, "RGBA")
        canvas = Image.new("RGBA", (fl.width + 70, fl.height + 70))
        sh = Image.new("RGBA", fl.size, (0, 0, 0, 255))
        sh.putalpha(fl.getchannel("A").point(lambda v: v * 0.55))
        canvas.alpha_composite(sh, (41, 48))
        canvas = canvas.filter(ImageFilter.GaussianBlur(14))
        ol = Image.new("RGBA", fl.size, (15, 15, 20, 255))
        ol.putalpha(fl.getchannel("A").filter(ImageFilter.MaxFilter(9)))
        canvas.alpha_composite(ol, (35, 35))
        canvas.alpha_composite(fl, (35, 35))
        out.append(canvas)
    return out


def mini_flag(code, w=68, h=46):
    src = Image.open(os.path.join(FLAG_DIR, code + ".png")).convert("RGBA")
    s = min(w / src.width, h / src.height)
    return src.resize((max(1, int(src.width * s)), max(1, int(src.height * s))), Image.LANCZOS)


def option_card(letter, i, text, state):
    """A/B/C/D answer button. state: idle, right or wrong."""
    fill = {"idle": (255, 255, 255, 245), "right": (55, 195, 95, 255), "wrong": (230, 70, 70, 255)}[state]
    card = mv.rounded_card(OPT_W, OPT_H, 30, fill, outline=(0, 0, 0, 255), width=5)
    d = ImageDraw.Draw(card)
    bc = LETTER_COL[i] if state == "idle" else (255, 255, 255)
    d.ellipse((16, 16, 96, 96), fill=bc + (255,), outline=(0, 0, 0, 255), width=4)
    d.text((56, 57), letter, font=mv.font("Black", 48), fill=(255, 255, 255) if state == "idle" else (20, 22, 45),
           anchor="mm")
    room = OPT_W - 124 - 62  # same size in every state
    size = 44
    while mv.font("Black", size).getlength(text) > room and size > 26:
        size -= 2
    d.text((114, 57), text, font=mv.font("Black", size), fill=(20, 22, 45) if state == "idle" else (255, 255, 255),
           anchor="lm")
    if state != "idle":
        card.alpha_composite(mv.emoji("✅" if state == "right" else "❌", 50), (OPT_W - 68, 31))
    return card


class Flag(mv.Scene):
    def __init__(self, tts, idx, q, prev_level, minis, rng):
        super().__init__()
        code, name, level, secs, before, said, extra, wrong, banner = q
        self.idx, self.level, self.secs, self.minis = idx, level, secs, minis
        self.frames = wave_frames(code, 800, 400)
        col = LEVEL_COL[level]
        self.pill = pill(f"FLAG {idx}/10 · {level}", col)
        self.title = with_emoji(bold("GUESS THE COUNTRY!", 76), "🌍", 80)
        choices = list(wrong)
        self.right = rng.randrange(4)
        choices.insert(self.right, name)
        self.cards = [{s: option_card("ABCD"[i], i, c, s) for s in ("idle", "right", "wrong")}
                      for i, c in enumerate(choices)]
        self.extra = None
        if extra:
            imgs = []
            for i, ln in enumerate(extra.split("|")):
                fill = (255, 90, 80) if i == 0 and ln.isupper() else (255, 255, 255)
                words, e = (ln.rsplit(" ", 1) + [""])[:2] if not ln[-1].isascii() else (ln, "")
                t = bold(words, 54, fill=fill, stroke=7, max_w=880)
                imgs.append(with_emoji(t, e, 56) if e else t)
            hh = sum(m.height for m in imgs) - 18 * (len(imgs) - 1)
            self.extra = Image.new("RGBA", (max(m.width for m in imgs), hh))
            y = 0
            for m in imgs:
                self.extra.alpha_composite(m, ((self.extra.width - m.width) // 2, y))
                y += m.height - 18
        self.rays = mq.sunburst(1000, col, 16)
        self.nums = {(n, red): bold(str(n), 70, fill=(255, 80, 70) if red else (255, 255, 255), stroke=7)
                     for n in range(1, secs + 1) for red in (False, True)}
        self.pause = with_emoji(bold("Pause if you need more time", 38, stroke=5), "⏸", 42, 10) \
            if level == "HARD" else None
        self.plus = mq.ptext("+1", 46, fill=(120, 255, 90))
        self.slot = mv.rounded_card(78, 56, 12, (10, 12, 30, 200), outline=(120, 150, 220, 255), width=3)
        self.slot_on = mv.rounded_card(78, 56, 12, (255, 255, 255, 255), outline=(255, 222, 40, 255), width=4)
        self.banner = None
        if banner:
            b = mq.mc_button(banner[0], 640, 120, col, 46)
            self.banner = with_emoji(b, banner[1], 100, 6) if banner[1] else b
            self.sounds.append((0.1, mq.sfx_levelup(), 1.0))
        self.hook = None
        if idx == 1:
            self.hook = with_emoji(bold("CAN YOU GET 10/10?", 78, fill=(255, 90, 80), stroke=9), "😳", 80)
            self.sounds.append((0.1, mq.sfx_boom(), 0.7))
        v = tts.say(before, speed=1.1)
        self.voices.append((0.12, v))
        a = tts.say(said, speed=1.1)
        self.reveal = T_IN + secs
        self.voices.append((self.reveal + 0.1, a))
        self.dur = self.reveal + max(2.0 if extra else 1.35, 0.1 + len(a) / SR + 0.15)
        self.sounds.append((0.0, sfx_whoosh(0.35), 0.6))
        for k in range(4):
            self.sounds.append((0.15 + 0.07 * k, sfx_pop(), 0.35))
        for k in range(secs):
            self.sounds.append((T_IN + k, mq.sfx_tock(high=k >= secs - 2), 1.0))
        self.sounds += [(self.reveal, sfx_ding(), 1.0), (self.reveal, mq.sfx_boom(), 0.45),
                        (self.reveal + 0.95, sfx_pop(), 0.6)]
        if extra:
            self.sounds.append((self.reveal + 0.55, mq.sfx_glitch(), 0.6))
        r = random.Random(idx)
        cols = [col, YELLOW, (255, 255, 255), (120, 255, 140)]
        self.burst = [(r.uniform(-700, 700), r.uniform(-1300, -400), r.randint(14, 26), r.choice(cols))
                      for _ in range(40)]

    def slot_x(self, i):
        return W / 2 + (i - 4.5) * 88

    def render(self, t):
        im = Image.new("RGBA", (W, H))
        rv = t - self.reveal
        out = ease_in_cubic((t - (self.dur - 0.25)) / 0.25)
        hk = ease_out_back(t / 0.3) * (1 - out)
        paste_center(im, scaled(self.pill, hk), W / 2, 150)
        paste_center(im, scaled(self.title, ease_out_back((t - 0.05) / 0.3) * (1 - out)), W / 2, 248)
        # flag collection bar (fills up as you go)
        hook_on = self.hook is not None and t < 1.9
        if hook_on:
            s = 1 + 1.2 * (1 - ease_out_cubic((t - 0.1) / 0.18))
            a = clamp((t - 0.1) / 0.08) * (1 - clamp((t - 1.6) / 0.3))
            paste_center(im, scaled(self.hook, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, PROG_Y + 14, a)
        bar_a = clamp((t - 1.9) / 0.3) if self.hook is not None else 1.0
        if bar_a > 0:
            for i in range(10):
                x = self.slot_x(i)
                filled = i < self.idx - 1 or (i == self.idx - 1 and rv > 0.95)
                paste_center(im, self.slot_on if filled else self.slot, x, PROG_Y, bar_a)
                if filled:
                    paste_center(im, self.minis[i], x, PROG_Y, bar_a)
                elif i == self.idx - 1:
                    pulse = 0.5 + 0.5 * math.sin(t * 8)
                    ImageDraw.Draw(im).rounded_rectangle((x - 41, PROG_Y - 30, x + 41, PROG_Y + 30), 14,
                                                         outline=(255, 222, 40, int(255 * pulse * bar_a)), width=4)
        # waving flag
        if rv > 0:
            paste_center(im, scaled(self.rays.rotate(rv * 30, Image.BICUBIC), 0.7 + 0.3 * ease_out_cubic(rv / 0.4)),
                         W / 2, FLAG_Y, 0.8 * (1 - out))
        fk = ease_out_back(t / 0.4, 1.5) * (1 - out)
        if rv > 0:
            fk *= 1 + 0.08 * math.sin(math.pi * clamp(rv / 0.3))
        fl = self.frames[int(t * 14) % len(self.frames)]
        paste_center(im, scaled(fl, max(0.01, fk)).rotate(2 * math.sin(t * 1.7), Image.BICUBIC, expand=True),
                     W / 2, FLAG_Y)
        # answer buttons
        for i, c in enumerate(self.cards):
            x, y = OPT_X[i % 2], OPT_Y[i // 2]
            k = ease_out_back((t - 0.15 - 0.07 * i) / 0.3) * (1 - out)
            if k <= 0.01:
                continue
            if rv <= 0:
                img, s, a = c["idle"], k, 1.0
            elif i == self.right:
                img = c["right"]
                s = k * (1 + 0.14 * math.sin(math.pi * clamp(rv / 0.3)) + 0.04)
                a = 1.0
            else:
                img, s, a = c["wrong"], k * (1 - 0.06 * clamp(rv / 0.2)), 1 - 0.35 * clamp(rv / 0.3)
            paste_center(im, scaled(img, s), x, y, a)
        if rv > 0.25:
            x, y = OPT_X[self.right % 2], OPT_Y[self.right // 2]
            paste_center(im, self.plus, x + OPT_W / 2 - 10, y - 70, clamp((rv - 0.25) / 0.15) * (1 - out))
        # timer, or the trap / fun fact after the reveal
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
            c = (255, 70, 60) if red else (110, 230, 90)
            if frac > 0.01:
                d.rounded_rectangle((x0, TIMER_Y - bh / 2, x0 + bw * frac, TIMER_Y + bh / 2), 20, fill=c + (255,))
            pop = 1 + 0.35 * (1 - ease_out_cubic((cd % 1) / 0.3))
            paste_center(im, scaled(self.nums[(n, red)], pop * hk), x0 - 70, TIMER_Y)
            if self.pause:
                paste_center(im, self.pause, W / 2, TIMER_Y + 80, 0.9 * hk)
        else:
            d = ImageDraw.Draw(im)
            for vx, vy, sz, c in self.burst:
                px, py = W / 2 + vx * rv, FLAG_Y + vy * rv + 2400 * rv * rv
                if py < H:
                    d.rectangle((px, py, px + sz, py + sz), fill=c + (255,))
            if self.extra and rv > 0.5:
                paste_center(im, scaled(self.extra, ease_out_back((rv - 0.5) / 0.3) * (1 - out)), W / 2,
                             TIMER_Y + self.extra.height / 2 - 20)
            if 0.55 < rv < 0.95:  # mini flag flies into the collection bar
                k = ease_in_cubic((rv - 0.55) / 0.4)
                tx = self.slot_x(self.idx - 1)
                x = W / 2 + (tx - W / 2) * k
                y = FLAG_Y + (PROG_Y - FLAG_Y) * k - math.sin(math.pi * k) * 120
                paste_center(im, scaled(self.minis[self.idx - 1], 5.5 - 4.5 * k), x, y)
            f = 1 - clamp(rv / 0.18)
            if f > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * f))))
        if self.banner is not None and t < 1.0:
            bx = W / 2 + (1 - ease_out_cubic(t / 0.2)) * W - ease_in_cubic((t - 0.8) / 0.2) * W
            paste_center(im, self.banner.rotate(-4, Image.BICUBIC, expand=True), bx, 1065)
        if 0 < rv < 0.35:  # screen shake on the reveal
            a = 22 * (1 - rv / 0.35)
            dx, dy = int(a * math.sin(rv * 90)), int(a * math.cos(rv * 75))
            shaken = Image.new("RGBA", (W, H))
            shaken.alpha_composite(im, (max(0, dx), max(0, dy)), (max(0, -dx), max(0, -dy)))
            im = shaken
        return im


class Ending(mv.Scene):
    def __init__(self, tts, minis):
        super().__init__()
        self.minis = minis
        self.slot_on = mv.rounded_card(78, 56, 12, (255, 255, 255, 255), outline=(255, 222, 40, 255), width=4)
        v = tts.say("How many did you get? Comment your score!", speed=1.1)
        self.voices.append((0.15, v))
        self.dur = max(4.2, 0.15 + len(v) / SR + 1.6)
        self.sounds += [(0.0, sfx_whoosh(0.4), 0.7), (0.15, mq.sfx_levelup(), 0.9)]
        self.t1 = bold("HOW MANY", 120, fill=YELLOW, stroke=11)
        self.t2 = with_emoji(bold("DID YOU GET?", 116, fill=YELLOW, stroke=11), "🤔", 110)
        rows = [("10/10", "GEOGRAPHY GENIUS", "🧠", (230, 150, 20)), ("7-9", "WORLD TRAVELER", "✈", (60, 110, 220)),
                ("4-6", "TOURIST", "📸", (60, 170, 70)), ("0-3", "NEED A MAP", "🗺", (120, 120, 130))]
        self.rows = []
        for i, (sc, label, e, col) in enumerate(rows):
            b = mv.rounded_card(920, 124, 36, col + (245,), outline=(0, 0, 0, 255), width=5)
            st = bold(sc, 60, stroke=6)
            b.alpha_composite(st, (20, 62 - st.height // 2))
            lb = with_emoji(bold(label, 56, fill=YELLOW if i == 0 else (255, 255, 255), stroke=6, max_w=560), e, 62)
            b.alpha_composite(lb, (920 - 36 - lb.width, 62 - lb.height // 2))
            self.rows.append(b)
            self.sounds.append((0.6 + 0.18 * i, sfx_pop(), 0.7))
        self.cta = with_emoji(bold("COMMENT YOUR SCORE", 66, stroke=7), "👇", 76)
        self.sounds.append((1.5, mq.sfx_pling(), 0.8))

    def render(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 70))
        a = 1 - clamp((t - (self.dur - 0.3)) / 0.3)
        paste_center(im, scaled(self.t1, ease_out_back(t / 0.35)), W / 2, 330, a)
        paste_center(im, scaled(self.t2, ease_out_back((t - 0.12) / 0.35)), W / 2, 470, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - 0.6 - 0.18 * i) / 0.35)
            paste_center(im, row, W / 2 + (1 - k) * (W if i % 2 else -W), 660 + i * 150, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.5) / 0.4) * (1 + 0.04 * math.sin(t * 8))), W / 2,
                     1300, a)
        for i, m in enumerate(self.minis):  # the full collection
            k = ease_out_back((t - 0.9 - 0.05 * i) / 0.3)
            x = W / 2 + (i - 4.5) * 88
            paste_center(im, scaled(self.slot_on, k), x, 1420 + 6 * math.sin(t * 5 + i), a)
            paste_center(im, scaled(m, k), x, 1420 + 6 * math.sin(t * 5 + i), a)
        return im


def build():
    tts = mv.TTS("af_heart", "en-us")
    minis = [mini_flag(q[0]) for q in FLAGS]
    rng = random.Random(77)
    scenes, prev = [], None
    for i, q in enumerate(FLAGS, 1):
        scenes.append(Flag(tts, i, q, prev, minis, rng))
        prev = q[2]
    scenes.append(Ending(tts, minis))
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t


def make_cover(full, path):
    base = cq.bg_frame(full, 3.0).convert("RGBA") if full else Image.new("RGBA", (W, H), (20, 40, 100, 255))
    paste_center(base, mq.sunburst(1700, (90, 170, 255), 16), W / 2, 1050, 0.6)
    paste_center(base, bold("GUESS THE", 120, stroke=12), W / 2, 230)
    paste_center(base, bold("COUNTRY", 190, fill=YELLOW, stroke=15), W / 2, 400)
    paste_center(base, with_emoji(bold("BY THE FLAG!", 100, stroke=10), "🌍", 100), W / 2, 560)
    for code, x, y, s, rot in (("KR", 270, 850, 0.48, -8), ("AR", 810, 850, 0.48, 8), ("IN", 270, 1210, 0.48, 6),
                               ("GR", 810, 1210, 0.48, -6), ("NP", 540, 1030, 0.62, 0)):
        paste_center(base, scaled(wave_frames(code, n=2)[0], s).rotate(rot, Image.BICUBIC, expand=True), x, y)
    paste_center(base, mq.mc_button("99% FAIL", 460, 116, (210, 30, 30), 46).rotate(-6, Image.BICUBIC, expand=True),
                 W / 2, 1520)
    base.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_flag_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--no-bg", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    scenes, starts, total = build()
    for sc, st in zip(scenes, starts):
        print(f"  {st:6.2f}s  {type(sc).__name__} {getattr(sc, 'idx', '')}")
    print(f"Duration {total:.1f}s")
    work = os.path.join(mv.CACHE_DIR, "render_flags")
    os.makedirs(work, exist_ok=True)
    full = None if a.no_bg else oo.logo_bg_full(total, work)
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.cover:
        make_cover(full, os.path.join(HERE, "flag_quiz_cover.jpg"))
        return
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"flag_{float(s):06.2f}.png")
            oo.compose(scenes, starts, float(s), full).save(p)
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
