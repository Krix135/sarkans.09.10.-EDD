#!/usr/bin/env python3
"""Vertical "GUESS THE FOOD BY THE PICTURE" quiz Short (1080x1920, ~75 s).

Intro -> 4 difficulty levels -> 10 photo questions (5-second countdown each,
then an animated reveal) -> score screen. Reuses the drawing, audio and TTS
engine from make_video.py.

Photos: put one real photo per food in food_images/ named after the key in
FOODS (pizza.jpg, banana.jpg, ...) and list where each came from in
food_images/CREDITS.txt. fetch_food_images.py can download free-licensed
photos from Wikimedia Commons for you.

    python3 make_food_quiz.py
    python3 make_food_quiz.py --stills 2,10,15
    python3 make_food_quiz.py --stills 10 --preview-placeholders   # layout test without photos
"""

import argparse
import glob
import math
import multiprocessing as mp
import os
import random
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import make_video as mv  # noqa: E402
from make_video import (SR, YELLOW, clamp, circle, ease_in_cubic, ease_out_back, ease_out_cubic, emoji,  # noqa: E402
                        font, paste_center, radial_glow, rounded_card, scaled, sfx_ding, sfx_fanfare, sfx_pop,
                        sfx_riser, sfx_tick, sfx_whoosh, soft_circle, text_img, vgradient)

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
NAVY = (14, 20, 52)
COUNTDOWN = 5
IMG_DIR = os.path.join(HERE, "food_images")
PHOTO = 800              # photo card size
PX, PY = 520, 850        # photo centre (nudged left of the Shorts like/comment buttons)
TIMER_Y = 1400

LEVELS = [  # name, colour, emoji, spoken
    ("EASY", (46, 204, 113), "🟢", "Level one. Easy!"),
    ("NORMAL", (52, 152, 219), "🔵", "Level two. Normal."),
    ("MEDIUM", (243, 156, 18), "🟠", "Level three. Medium!"),
    ("HARD", (231, 76, 60), "🔴", "Level four. Hard! Only experts get these."),
]

FOODS = [  # key (= picture file name), answer on screen, emoji for the reveal (or None), level, spoken
    ("pizza", "PIZZA", "🍕", 0, "Pizza!"),
    ("burger", "BURGER", "🍔", 0, "Burger!"),
    ("sushi", "SUSHI", "🍣", 0, "Sushi!"),
    ("tacos", "TACOS", "🌮", 1, "Tacos!"),
    ("croissant", "CROISSANT", "🥐", 1, "Croissant!"),
    ("steak", "STEAK", "🥩", 2, "Steak!"),
    ("dumplings", "DUMPLINGS", "🥟", 2, "Dumplings!"),
    ("curry", "CURRY", "🍛", 2, "Curry!"),
    ("paella", "PAELLA", "🥘", 3, "Paella!"),
    ("falafel", "FALAFEL", "🧆", 3, "Falafel!"),
]


# ----------------------------------------------------------------------------
# drawing helpers
# ----------------------------------------------------------------------------

def outlined(text, size, fill=(255, 255, 255), stroke=9, max_w=None, weight="Black"):
    if max_w:
        while font(weight, size).getlength(text) + 2 * stroke > max_w and size > 30:
            size -= 2
    return text_img(text, font(weight, size), fill=fill, stroke=stroke, stroke_fill=(0, 0, 0))


def swirl_bg(top=(30, 64, 160), bot=(10, 22, 78)):
    """Dark blue background with a subtle repeating swirl pattern."""
    bg = vgradient(W, H, top, bot).convert("RGBA")
    ss = 2
    pat = Image.new("RGBA", (W * ss, H * ss))
    d = ImageDraw.Draw(pat)
    step = 150 * ss
    for row, cy in enumerate(range(-step // 2, H * ss + step, step)):
        for cx in range(-step // 2 + (step // 2 if row % 2 else 0), W * ss + step, step):
            pts = []
            for k in range(0, 200):
                a = k * 0.14
                r = 4 * ss + a * 3.3 * ss
                if r > step * 0.42:
                    break
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            d.line(pts, fill=(170, 200, 255, 34), width=5 * ss, joint="curve")
    bg.alpha_composite(pat.resize((W, H), Image.LANCZOS))
    bg.alpha_composite(radial_glow(W, H, W / 2, 820, 800, (120, 170, 255), 0.30))
    vign = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vign).ellipse((-300, -200, W + 300, H + 200), fill=255)
    dark = Image.new("RGBA", (W, H), (0, 0, 20, 120))
    dark.putalpha(Image.eval(vign.filter(ImageFilter.GaussianBlur(160)), lambda v: int((255 - v) * 0.55)))
    bg.alpha_composite(dark)
    return bg


def pill(text, size, fill, text_col=NAVY, icon=None, pad=44, h=None, outline=(0, 0, 0, 255)):
    ti = text_img(text, font("Black", size), fill=text_col, shadow=False)
    ic = emoji(icon, int(size * 1.1)) if icon else None
    w = ti.width + 2 * pad - 30 + (ic.width + 14 if ic else 0)
    h = h or int(size * 1.9)
    card = rounded_card(w, h, h // 2, fill + (255,), outline=outline, width=5)
    x = pad - 15
    if ic:
        paste_center(card, ic, x + ic.width / 2, h / 2)
        x += ic.width + 14
    paste_center(card, ti, x + ti.width / 2, h / 2 + 1)
    return card


def photo_card(path, label):
    """Square, centre-cropped photo with rounded corners, white frame and shadow."""
    if path and Image.open(path).mode in ("RGBA", "LA", "P"):
        # transparent illustration: place it on a warm, softly lit "plate"
        art = Image.open(path).convert("RGBA")
        src = vgradient(PHOTO, PHOTO, (255, 247, 232), (246, 214, 172)).convert("RGBA")
        src.alpha_composite(radial_glow(PHOTO, PHOTO, PHOTO / 2, PHOTO * 0.42, PHOTO * 0.6, (255, 255, 255), 0.85))
        art = art.resize((640, 640), Image.LANCZOS)
        sh = Image.new("RGBA", art.size, (90, 50, 10, 0))
        sh.putalpha(art.getchannel("A").point(lambda v: v * 0.35))
        paste_center(src, sh.filter(ImageFilter.GaussianBlur(16)), PHOTO / 2 + 8, PHOTO / 2 + 30)
        paste_center(src, art, PHOTO / 2, PHOTO / 2)
        src = src.convert("RGB")
    elif path:
        src = Image.open(path).convert("RGB")
        s = min(src.size)
        src = src.crop(((src.width - s) // 2, (src.height - s) // 2, (src.width + s) // 2, (src.height + s) // 2))
        src = src.resize((PHOTO, PHOTO), Image.LANCZOS)
    else:  # layout preview only, never used for a real render
        src = vgradient(PHOTO, PHOTO, (120, 120, 130), (70, 70, 80))
        tmp = src.convert("RGBA")
        paste_center(tmp, text_img(f"PHOTO: {label}", font("Black", 60)), PHOTO / 2, PHOTO / 2)
        src = tmp.convert("RGB")
    border, rad = 14, 46
    full = PHOTO + 2 * border
    card = rounded_card(full, full, rad + border, (255, 255, 255, 255))
    mask = rounded_card(PHOTO, PHOTO, rad, (255, 255, 255, 255)).getchannel("A")
    ph = src.convert("RGBA")
    ph.putalpha(mask)
    card.alpha_composite(ph, (border, border))
    pad = 60
    out = Image.new("RGBA", (full + 2 * pad, full + 2 * pad))
    sh = rounded_card(full, full, rad + border, (0, 0, 0, 170))
    out.alpha_composite(sh, (pad + 6, pad + 22))
    out = out.filter(ImageFilter.GaussianBlur(18))
    out.alpha_composite(card, (pad, pad))
    return out


def star(size, color):
    ss = 4
    n = size * ss
    im = Image.new("RGBA", (n, n))
    pts = []
    for i in range(10):
        a = math.pi / 5 * i - math.pi / 2
        r = n / 2 if i % 2 == 0 else n * 0.21
        pts.append((n / 2 + r * math.cos(a), n / 2 + r * math.sin(a)))
    ImageDraw.Draw(im).polygon(pts, fill=color)
    return im.resize((size, size), Image.LANCZOS)


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------

class FoodIntro(mv.Scene):
    def __init__(self, tts, bg):
        super().__init__()
        v = tts.say("How many foods can you name? Let's see how good you are!", speed=1.15)
        self.voices.append((0.15, v))
        self.dur = max(3.1, 0.15 + len(v) / SR + 0.1)
        self.sounds += [(0.0, sfx_whoosh(0.5), 0.8), (0.25, sfx_pop(), 1.0), (0.45, sfx_pop(), 1.0),
                        (0.65, sfx_pop(), 1.0), (1.0, sfx_fanfare(), 0.6)]
        self.bg = bg
        self.burger = emoji("🍔", 250)
        self.lines = [outlined("HOW MANY", 140, fill=YELLOW, stroke=11),
                      outlined("FOODS CAN", 140, stroke=11),
                      outlined("YOU NAME?", 140, stroke=11)]
        self.chip = pill("10 QUESTIONS – 4 DIFFICULTY LEVELS!", 42, YELLOW)
        self.tag = outlined("Let's see how good you are!", 58, stroke=6, weight="ExtraBold")
        r = random.Random(4)
        self.float = [(emoji(e, r.randint(90, 130)), x, y, r.uniform(0, 6.3))
                      for e, x, y in (("🍕", 130, 330), ("🍣", 950, 300), ("🥐", 110, 1380), ("🍌", 960, 1350),
                                      ("🥑", 150, 1560), ("🥨", 930, 1580))]

    def render(self, t):
        im = self.bg.copy()
        for spr, x, y, ph in self.float:
            s = ease_out_back((t - 0.2) / 0.5)
            paste_center(im, scaled(spr.rotate(12 * math.sin(t * 2 + ph), expand=True), s),
                         x, y + 14 * math.sin(t * 2.2 + ph), 0.8)
        bs = ease_out_back(t / 0.5) * (1 + 0.04 * math.sin(t * 6))
        paste_center(im, scaled(self.burger.rotate(6 * math.sin(t * 3), expand=True), bs), W / 2, 470)
        for i, ln in enumerate(self.lines):
            paste_center(im, scaled(ln, ease_out_back((t - 0.2 - 0.18 * i) / 0.4)), W / 2, 700 + i * 150)
        paste_center(im, scaled(self.chip, ease_out_back((t - 0.9) / 0.4)), W / 2, 1150)
        paste_center(im, self.tag, W / 2, 1270, clamp((t - 1.2) / 0.3))
        return im


class LevelCard(mv.Scene):
    def __init__(self, tts, level, bg):
        super().__init__()
        name, col, emo, spoken = LEVELS[level]
        self.level, self.col = level, col
        v = tts.say(spoken, speed=1.12)
        self.voices.append((0.12, v))
        self.dur = 0.95 if level < 3 else 1.25
        self.sounds += [(0.0, sfx_whoosh(0.45), 1.0), (0.25, sfx_pop(), 1.0)]
        if level == 3:
            self.sounds.append((0.05, sfx_riser(0.9), 0.7))
        self.bg = bg
        panel = vgradient(W, H, tuple(min(255, c + 40) for c in col), tuple(int(c * 0.55) for c in col)).convert("RGBA")
        st = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(st)
        for x in range(-H, W, 90):
            d.line((x, H, x + H, 0), fill=(255, 255, 255, 22), width=34)
        panel.alpha_composite(st)
        self.panel = panel
        self.big = outlined(f"LEVEL {level + 1}", 190, stroke=13)
        self.name = pill(name, 92, (255, 255, 255), text_col=tuple(int(c * 0.6) for c in col), h=170)
        self.dot = emoji(emo, 170)
        self.bars = [outlined("●" * (i + 1) + "○" * (3 - i), 60, fill=YELLOW, stroke=5) for i in range(4)]

    def render(self, t):
        im = self.bg.copy()
        win = ease_out_cubic(t / 0.25)
        wout = ease_in_cubic((t - (self.dur - 0.25)) / 0.25)
        x = int(W * (1 - win) - W * wout)
        shake = 0
        if self.level == 3 and 0.25 < t < 0.75:
            shake = int(14 * math.sin(t * 90) * (1 - (t - 0.25) / 0.5))
        im.alpha_composite(self.panel, (x + shake, 0))
        cx = x + W / 2 + shake
        paste_center(im, scaled(self.dot, ease_out_back((t - 0.15) / 0.35)), cx, 640)
        paste_center(im, scaled(self.big, ease_out_back((t - 0.2) / 0.35)), cx, 880)
        paste_center(im, scaled(self.name, ease_out_back((t - 0.3) / 0.35)), cx, 1080)
        paste_center(im, self.bars[self.level], cx, 1240, clamp((t - 0.4) / 0.2))
        return im


class FoodQuestion(mv.Scene):
    def __init__(self, tts, idx, food, bg, placeholders):
        super().__init__()
        key, answer, emo, level, spoken = food
        self.level = level
        path = None
        hits = sorted(glob.glob(os.path.join(IMG_DIR, key + ".*")))
        if hits:
            path = hits[0]
        elif not placeholders:
            raise FileNotFoundError(f"missing photo for {key} in {IMG_DIR}")
        self.photo = photo_card(path, answer)
        self.t_in, self.cd = 0.0, 0.3
        self.reveal = self.cd + COUNTDOWN
        self.dur = self.reveal + 1.0
        v = tts.say(spoken, speed=1.1)
        self.voices.append((self.reveal + 0.15, v))
        for k in range(COUNTDOWN):
            self.sounds.append((self.cd + k, sfx_tick(high=k >= COUNTDOWN - 3), 1.0))
        self.sounds += [(0.0, sfx_whoosh(0.35), 0.6), (self.reveal, sfx_ding(), 1.0),
                        (self.reveal + 0.02, sfx_pop(), 1.0)]
        self.bg = bg
        name, col, lemo, _ = LEVELS[level]
        self.title = outlined("WHAT FOOD IS THIS?", 92, fill=YELLOW, stroke=9, max_w=1000)
        self.lvl = pill(f"LEVEL {level + 1} · {name}", 44, col, text_col=(255, 255, 255), icon=lemo)
        self.num = pill(f"{idx}/10", 48, (255, 255, 255))
        self.answer = outlined(answer, 128, stroke=11, max_w=820 if emo else 960)
        self.ans_emoji = emoji(emo, 120) if emo else None
        self.check = circle(110, (46, 204, 113, 255))
        paste_center(self.check, outlined("✓", 80, stroke=0, weight="Black"), 55, 52)
        self.timer_bg = circle(190, NAVY + (255,))
        self.timer_shadow = soft_circle(190, (0, 0, 0, 150), 12)
        self.nums = {n: outlined(str(n), 100, stroke=6) for n in range(1, COUNTDOWN + 1)}
        self.red_nums = {n: outlined(str(n), 100, fill=(255, 80, 70), stroke=6) for n in range(1, COUNTDOWN + 1)}
        r = random.Random(idx)
        self.burst = [(star(r.randint(26, 46), r.choice([YELLOW + (255,), (255, 255, 255, 255), col + (255,)])),
                       r.uniform(0, 2 * math.pi), r.uniform(260, 520)) for _ in range(16)]

    def render(self, t):
        im = self.bg.copy()
        ex = ease_in_cubic((t - (self.dur - 0.25)) / 0.25)
        # header
        hk = ease_out_back(t / 0.35)
        paste_center(im, scaled(self.title, hk), W / 2, 250 - 200 * ex)
        gap = 24
        tw = self.lvl.width + gap + self.num.width
        x0 = W / 2 - tw / 2
        paste_center(im, scaled(self.lvl, hk), x0 + self.lvl.width / 2, 368 - 200 * ex)
        paste_center(im, scaled(self.num, hk), x0 + self.lvl.width + gap + self.num.width / 2, 368 - 200 * ex)
        # photo: pops in, floats gently, bounces on reveal, slides out
        rv = t - self.reveal
        s = 0.55 + 0.45 * ease_out_back(t / 0.4)
        if rv > 0:
            s *= 1 + 0.05 * math.sin(math.pi * clamp(rv / 0.3))
        ph = scaled(self.photo, s)
        rot = 3 * math.sin(t * 1.3) * (1 - clamp(rv / 0.3)) if rv < 0.3 else 0
        if abs(rot) > 0.05:
            ph = ph.rotate(rot, Image.BICUBIC, expand=True)
        py = PY + 8 * math.sin(t * 2)
        paste_center(im, ph, PX - 1200 * ex, py, clamp(t / 0.2))
        if 0 < rv < 0.35:  # flash
            fl = rounded_card(PHOTO, PHOTO, 46, (255, 255, 255, int(200 * (1 - rv / 0.35))))
            paste_center(im, scaled(fl, s), PX, py)
        if rv > 0:
            paste_center(im, scaled(self.check, ease_out_back((rv - 0.1) / 0.3)),
                         PX + PHOTO / 2 - 20 - 1200 * ex, py - PHOTO / 2 + 20)
        # timer, then the answer in the same spot
        if rv < 0:
            cd = t - self.cd
            tk = ease_out_back((t - 0.2) / 0.3)
            paste_center(im, scaled(self.timer_shadow, tk), PX, TIMER_Y + 10)
            paste_center(im, scaled(self.timer_bg, tk), PX, TIMER_Y)
            frac = 1 - clamp(cd / COUNTDOWN)
            n = max(1, COUNTDOWN - int(max(cd, 0)))
            red = n <= 2
            ring = Image.new("RGBA", (440, 440))
            d = ImageDraw.Draw(ring)
            d.ellipse((14, 14, 426, 426), outline=(255, 255, 255, 60), width=24)
            d.arc((14, 14, 426, 426), -90, -90 + 360 * frac, fill=((255, 69, 58) if red else YELLOW) + (255,), width=24)
            paste_center(im, scaled(ring.resize((220, 220), Image.LANCZOS), tk), PX, TIMER_Y)
            pop = 1 + 0.3 * (1 - ease_out_cubic((max(cd, 0) % 1) / 0.3))
            paste_center(im, scaled((self.red_nums if red else self.nums)[n], pop * tk), PX, TIMER_Y + 2)
        else:
            ak = ease_out_back(rv / 0.35)
            ay = TIMER_Y + 10
            for spr, ang, dist in self.burst:  # star burst behind the answer
                k = ease_out_cubic(rv / 0.6)
                a = 1 - clamp((rv - 0.35) / 0.4)
                if a > 0:
                    paste_center(im, spr, PX + math.cos(ang) * dist * k, ay + math.sin(ang) * dist * 0.45 * k, a)
            ans = scaled(self.answer, ak)
            if self.ans_emoji:
                e = scaled(self.ans_emoji, ak)
                total = e.width + 14 + ans.width
                x = W / 2 - total / 2 - 1200 * ex
                paste_center(im, e, x + e.width / 2, ay)
                paste_center(im, ans, x + e.width + 14 + ans.width / 2, ay)
            else:
                paste_center(im, ans, W / 2 - 1200 * ex, ay)
        return im


class FoodEnding(mv.Scene):
    def __init__(self, tts, bg):
        super().__init__()
        v = tts.say("How many did you get right? Comment your score below!", speed=1.12)
        self.voices.append((0.2, v))
        self.dur = max(4.6, 0.2 + len(v) / SR + 1.6)
        self.sounds += [(0.0, sfx_whoosh(0.5), 0.8), (0.15, sfx_fanfare(), 0.8)]
        self.bg = bg
        self.t1 = outlined("HOW MANY DID YOU", 96, fill=YELLOW, stroke=9)
        self.t2 = outlined("GET RIGHT?", 130, fill=YELLOW, stroke=11)
        rows = [("0–3", "Beginner", (120, 130, 160)), ("4–6", "Food Explorer", (46, 160, 90)),
                ("7–9", "Food Expert", (40, 120, 210)), ("10/10", "FOOD MASTER!", (230, 160, 20))]
        self.rows = []
        for i, (rng_, label, col) in enumerate(rows):
            card = rounded_card(900, 120, 34, col + (255,), outline=(255, 255, 255, 220), width=4)
            paste_center(card, emoji("🏆", 72), 72, 60)
            ri = outlined(rng_, 58, stroke=5)
            card.alpha_composite(ri, (130 - 24, 60 - ri.height // 2))
            li = outlined(label, 56 if i < 3 else 60, fill=(255, 255, 255) if i < 3 else YELLOW, stroke=5)
            card.alpha_composite(li, (900 - 40 - li.width + 24, 60 - li.height // 2))
            self.rows.append(card)
            self.sounds.append((0.7 + 0.2 * i, sfx_pop(), 0.8))
        self.cta = pill("COMMENT YOUR SCORE BELOW!", 44, YELLOW, icon="👇")
        self.sub = outlined("SUBSCRIBE FOR MORE QUIZZES!", 56, stroke=6, max_w=960)
        self.sounds.append((1.6, sfx_pop(), 0.8))
        pp = os.path.join(HERE, "profile_picture.png")
        self.logo = None
        if os.path.exists(pp):
            logo = Image.open(pp).convert("RGBA").resize((150, 150), Image.LANCZOS)
            logo.putalpha(circle(150, (255, 255, 255, 255)).getchannel("A"))
            ring = circle(164, (255, 255, 255, 255))
            ring.alpha_composite(logo, (7, 7))
            self.logo = ring

    def render(self, t):
        im = self.bg.copy()
        paste_center(im, scaled(self.t1, ease_out_back(t / 0.4)), W / 2, 330)
        paste_center(im, scaled(self.t2, ease_out_back((t - 0.15) / 0.4) * (1 + 0.02 * math.sin(t * 5))), W / 2, 460)
        for i, c in enumerate(self.rows):
            k = ease_out_cubic((t - 0.7 - 0.2 * i) / 0.4)
            paste_center(im, c, W / 2 + (1 - k) * (W if i % 2 else -W), 640 + i * 145, clamp(k * 1.5))
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.6) / 0.4)), W / 2, 1250)
        if self.logo:
            paste_center(im, scaled(self.logo, ease_out_back((t - 1.9) / 0.4)), W / 2, 1400)
            paste_center(im, self.sub, W / 2, 1530, clamp((t - 2.0) / 0.3))
        else:
            paste_center(im, self.sub, W / 2, 1400, clamp((t - 2.0) / 0.3))
        return im


# ----------------------------------------------------------------------------

def build(placeholders):
    tts = mv.TTS()
    bg = swirl_bg()
    scenes = [FoodIntro(tts, bg)]
    level = -1
    for i, food in enumerate(FOODS, 1):
        if food[3] != level:
            level = food[3]
            scenes.append(LevelCard(tts, level, bg))
        scenes.append(FoodQuestion(tts, i, food, bg, placeholders))
    scenes.append(FoodEnding(tts, bg))
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_guess_the_food.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--preview-placeholders", action="store_true",
                    help="grey boxes instead of photos (layout test only, stills only)")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    if args.preview_placeholders and not args.stills:
        sys.exit("--preview-placeholders is only for --stills; a real video needs real photos")
    try:
        scenes, starts, total = build(args.preview_placeholders)
    except FileNotFoundError as e:
        sys.exit(f"{e}\nAdd photos to {IMG_DIR} (see fetch_food_images.py).")
    for sc, st in zip(scenes, starts):
        print(f"  {st:6.2f}s  {type(sc).__name__}")
    print(f"Duration {total:.1f}s")
    mv.G["scenes"], mv.G["starts"] = scenes, starts

    if args.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in args.stills.split(","):
            p = os.path.join(d, f"food_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return

    work = os.path.join(mv.CACHE_DIR, "render_food")
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
                    "-movflags", "+faststart", "-shortest", args.out], check=True)
    print(f"Done: {args.out}")


if __name__ == "__main__":
    main()
