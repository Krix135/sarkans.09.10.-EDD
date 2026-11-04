#!/usr/bin/env python3
""""Can you name all 10 capitals?" - flag quiz Short (1080x1920) over a Minecraft-style gameplay background.

A blocky player walks along a road through original voxel worlds (plains,
snowy taiga, desert, Nether) while the quiz runs on top: waving flag,
country name, 4-second countdown, then the capital (plus the common wrong
answer it is often confused with). Reuses the world renderer, UI pieces,
sounds and music from make_minecraft_quiz.py. Flags: public-domain images
from the region-flags set (flags/LICENSE).

    python3 make_capitals_quiz.py
    python3 make_capitals_quiz.py --stills 2,8,30
    python3 make_capitals_quiz.py --cover
    python3 make_capitals_quiz.py --bg-video gameplay.mp4   # use a recorded gameplay clip instead
"""

import argparse
import math
import multiprocessing as mp
import os
import random
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_video import (SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, lowpass, paste_center,  # noqa: E402
                        radial_glow, scaled, sfx_whoosh, tt)
from make_minecraft_quiz import DIFF, YELLOW, bevel_box, bold, mc_button, ptext  # noqa: E402

W, H, FPS = 1080, 1920, 30
FLAG_DIR = os.path.join(HERE, "flags")
T_IN, COUNTDOWN = 0.22, 4.0
FLAG_Y, NAME_Y, PROMPT_Y, TIMER_Y, BAR_Y, ANSWER_Y = 545, 850, 950, 1090, 1225, 1100
CHAR_SCREEN_Y = 1420
ROAD_X0, ROAD_X1 = 8, 50

QUESTIONS = [  # flag code, country, capital, spoken answer, level, trap answer
    ("FR", "FRANCE", "PARIS", "Paris!", "EASY", None),
    ("JP", "JAPAN", "TOKYO", "Tokyo!", "EASY", None),
    ("IT", "ITALY", "ROME", "Rome!", "EASY", None),
    ("EG", "EGYPT", "CAIRO", "Cairo!", "NORMAL", None),
    ("BR", "BRAZIL", "BRASÍLIA", "Brasília! Not Rio!", "NORMAL", "NOT RIO DE JANEIRO!"),
    ("CA", "CANADA", "OTTAWA", "Ottawa! Not Toronto!", "MEDIUM", "NOT TORONTO!"),
    ("AU", "AUSTRALIA", "CANBERRA", "Canberra! Not Sydney!", "MEDIUM", "NOT SYDNEY!"),
    ("TR", "TURKEY", "ANKARA", "Ankara! Not Istanbul!", "MEDIUM", "NOT ISTANBUL!"),
    ("MA", "MOROCCO", "RABAT", "Rabat! Not Casablanca!", "HARD", "NOT CASABLANCA!"),
    ("KZ", "KAZAKHSTAN", "ASTANA", "Astana!", "HARD", None),
]
LEVEL_WORLD = {"EASY": "plains", "NORMAL": "snowy", "MEDIUM": "desert", "HARD": "nether"}

# ----------------------------------------------------------------------------
# worlds with a walkable road
# ----------------------------------------------------------------------------
PATH = 34
TERRAIN = {mq.GRASS, mq.DIRT, mq.STONE, mq.SAND, mq.SANDSTONE, mq.SNOW, mq.GRAVEL, mq.NETHERRACK, mq.SOUL_SAND,
           mq.END_STONE, mq.ICE, mq.WATER, mq.LAVA}


def add_path_textures(tex):
    r = np.random.default_rng(12)
    top = mq._pal(r, [(160, 130, 80), (148, 120, 72), (172, 142, 90), (136, 108, 64)])
    side = mq._pal(r, [(134, 96, 67), (121, 85, 58), (150, 108, 75), (104, 74, 50)])
    side[:2] = top[:2]
    tex["path_top"] = Image.fromarray(top, "RGB").convert("RGBA")
    tex["path_side"] = Image.fromarray(side, "RGB").convert("RGBA")
    mq.BLOCKS[PATH] = ("path_top", "path_side", False)


def make_road(vox, ry, fill_block):
    """Clear a 7-wide strip along x at y=ry and lay a smooth (max 1-block steps) path."""
    X, Y, Z = vox.shape
    tops = []
    for x in range(X):
        col = vox[x, ry]
        zs = [z for z in range(Z) if col[z] in TERRAIN]
        tops.append(max(zs) if zs else 4)
    tops = np.array(tops)
    sm = tops.copy()
    for x in range(1, X):
        sm[x] = int(np.clip(sm[x], sm[x - 1] - 1, sm[x - 1] + 1))
    sm = np.maximum(sm, 7)
    for x in range(X):
        h = int(sm[x])
        for dy in range(-3, 4):
            y = ry + dy
            if not 0 <= y < Y:
                continue
            vox[x, y, h + 1:] = 0
            if dy == 0 or abs(dy) == 1:
                vox[x, y, :h] = np.where(vox[x, y, :h] == 0, fill_block, vox[x, y, :h])
                vox[x, y, h] = PATH
            else:
                zs = [z for z in range(Z) if vox[x, y, z] != 0]
                if zs and max(zs) > h + 1:
                    vox[x, y, h + 2:] = 0
    return sm


def build_road_worlds(tex):
    add_path_textures(tex)
    specs = [
        ("plains", lambda: mq.gen_overworld(11, "plains"), 28, mq.DIRT, (1, 1, 1), (205, 225, 255), 0.35, "day",
         None),
        ("snowy", lambda: mq.gen_overworld(23, "snowy"), 28, mq.DIRT, (1, 1, 1.03), (225, 235, 250), 0.38, "snowy",
         None),
        ("desert", lambda: mq.gen_overworld(31, "desert"), 28, mq.SANDSTONE, (1.03, 1, 0.95), (245, 225, 190),
         0.38, "desert", None),
        ("nether", lambda: mq.gen_nether(9)[0], 24, mq.NETHERRACK, (0.88, 0.7, 0.66), (130, 35, 22), 0.45,
         "nether", {mq.LAVA: ((255, 120, 30), 110, 0.25), mq.GLOWSTONE: ((255, 220, 120), 120, 0.35),
                    mq.PORTAL: ((180, 80, 255), 140, 0.5)}),
    ]
    worlds = {}
    for i, (name, gen, ry, fill, amb, fog, fs, sky, glow) in enumerate(specs):
        vox = gen()
        road = make_road(vox, ry, fill)
        canvas, origin = mq.render_voxels(vox, mq.SpriteCache(tex, amb, fog), fs, glow)
        w = mq.World(name if name != "snowy" else "snowy", canvas, origin, mq.sky_image(sky, i + 1), seed=i)
        w.road, w.ry = road, ry
        worlds[name] = w
    return worlds


# ----------------------------------------------------------------------------
# the walking player (original blocky character)
# ----------------------------------------------------------------------------

def player_frames(scale=5):
    skin, hair, eye = (232, 182, 140), (120, 70, 30), (40, 60, 120)
    shirt, shirt_d, pants, shoe = (220, 60, 50), (180, 40, 35), (50, 60, 120), (70, 50, 35)
    frames = []
    for leg in (-1, 0, 1, 0):
        im = Image.new("RGBA", (12, 26))
        d = ImageDraw.Draw(im)
        d.rectangle((3, 0, 8, 1), fill=hair)          # hair
        d.rectangle((3, 2, 8, 5), fill=skin)          # face
        d.rectangle((3, 2, 4, 3), fill=hair)
        d.point((7, 3), fill=eye)
        d.rectangle((4, 6, 7, 13), fill=shirt)        # body
        # legs swing
        d.rectangle((4 + leg, 14, 5 + leg, 21), fill=pants)
        d.rectangle((6 - leg, 14, 7 - leg, 21), fill=pants)
        d.rectangle((4 + leg, 22, 5 + leg, 23), fill=shoe)
        d.rectangle((6 - leg, 22, 7 - leg, 23), fill=shoe)
        # arm swings opposite to the front leg
        d.rectangle((5 - leg, 7, 6 - leg, 12), fill=shirt_d)
        d.rectangle((5 - leg, 12, 6 - leg, 13), fill=skin)
        frames.append(im.resize((12 * scale, 26 * scale), Image.NEAREST))
    return frames


class Gameplay:
    """Continuous background: the player walks through one world per difficulty level."""

    def __init__(self, worlds, segments):
        self.worlds, self.segments = worlds, segments  # (world name, t0, t1)
        self.frames = player_frames()
        self.shadow = Image.new("RGBA", (90, 34))
        ImageDraw.Draw(self.shadow).ellipse((0, 0, 89, 33), fill=(0, 0, 0, 100))

    def segment(self, tg):
        for name, t0, t1 in self.segments:
            if tg < t1:
                return name, t0, t1
        return self.segments[-1]

    def state(self, tg):
        name, t0, t1 = self.segment(tg)
        w = self.worlds[name]
        v = min(2.6, (ROAD_X1 - ROAD_X0) / max(1.0, t1 - t0))
        x = ROAD_X0 + v * (tg - t0)
        i = int(x)
        f = x - i
        h0, h1 = w.road[min(i, len(w.road) - 1)], w.road[min(i + 1, len(w.road) - 1)]
        k = clamp((f - 0.6) / 0.4)  # step up/down near the block edge with a small hop
        z = h0 + (h1 - h0) * (3 * k * k - 2 * k ** 3) + 0.6 * math.sin(math.pi * k) * abs(h1 - h0) + 1
        px, py = mq.iso_xy(x, w.ry + 0.5, z - 1, w.origin)
        return w, px, py, v

    video = False  # True when a recorded gameplay clip is composited underneath by the renderer

    def frame(self, tg, shake=(0, 0)):
        if self.video:
            return Image.new("RGBA", (W, H), (0, 0, 0, 0))
        w, px, py, v = self.state(tg)
        z = 1.22 + 0.03 * math.sin(tg * 0.5)
        cx, cy = px, py - (CHAR_SCREEN_Y - H / 2) / z
        im = w.view(cx, cy, z, tg, shake)
        fr = self.frames[int(tg * v * 2.2) % 4]
        fr = scaled(fr, z)
        bob = abs(math.sin(tg * v * 2.2 * math.pi / 2)) * 6
        sx, sy = W / 2 + shake[0], CHAR_SCREEN_Y + shake[1]
        paste_center(im, scaled(self.shadow, z), sx, sy + 2)
        im.alpha_composite(fr, (int(sx - fr.width / 2), int(sy - fr.height - bob)))
        return im


# ----------------------------------------------------------------------------
# flags
# ----------------------------------------------------------------------------

def wave_frames(code, width=640, n=16):
    src = Image.open(os.path.join(FLAG_DIR, code + ".png")).convert("RGB")
    h = int(width * src.height / src.width)
    if h > 440:
        h = 440
        width = int(h * src.width / src.height)
    arr = np.asarray(src.resize((width, h), Image.LANCZOS)).astype(np.float32)
    xs = np.arange(width)
    pad = 16
    out = []
    for k in range(n):
        ph = 2 * math.pi * k / n
        wave = 2 * math.pi * xs / (width * 0.6) - ph
        off = (11 * (0.25 + 0.75 * xs / width) * np.sin(wave)).astype(int)
        shade = 1 + 0.13 * np.cos(wave) * (0.3 + 0.7 * xs / width)
        img = np.zeros((h + 2 * pad, width, 4), np.uint8)
        for x in range(width):
            y0 = pad + off[x]
            img[y0:y0 + h, x, :3] = np.clip(arr[:, x] * shade[x], 0, 255)
            img[y0:y0 + h, x, 3] = 255
        fl = Image.fromarray(img, "RGBA")
        sh = Image.new("RGBA", (fl.width + 60, fl.height + 60))
        a = fl.getchannel("A").point(lambda v: v * 0.55)
        blk = Image.new("RGBA", fl.size, (0, 0, 0, 255))
        blk.putalpha(a)
        sh.alpha_composite(blk, (36, 42))
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        # thin dark outline for contrast on any background
        ol = Image.new("RGBA", fl.size, (15, 15, 20, 255))
        ol.putalpha(fl.getchannel("A").filter(ImageFilter.MaxFilter(7)))
        sh.alpha_composite(ol, (30, 30))
        sh.alpha_composite(fl, (30, 30))
        out.append(sh)
    return out


# ----------------------------------------------------------------------------
# audio
# ----------------------------------------------------------------------------

def sfx_step(seed):
    n = int(0.07 * SR)
    s = lowpass(np.random.default_rng(seed).standard_normal(n), 900) * np.exp(-np.arange(n) / SR * 55)
    return s * 0.5


def mix_with_steps(scenes, starts, total, gameplay):
    data = mq.mix(scenes, starts, total, "piano").astype(np.float64) / 32767
    if gameplay.video:  # recorded parkour clip: no walking character, so no footsteps
        return (np.clip(data, -1, 1) * 32767).astype(np.int16)
    steps = np.zeros(len(data))
    t = 0.3
    k = 0
    while t < total - 0.2:
        _, _, _, v = gameplay.state(t)
        s = sfx_step(k % 5)
        i = int(t * SR)
        steps[i:i + len(s)] += s[: len(steps) - i]
        t += 1 / (v * 1.1)
        k += 1
    data += np.stack([steps, steps], 1) * 0.25
    return (np.clip(data, -1, 1) * 32767).astype(np.int16)


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------

class Base(mv.Scene):
    t0 = 0.0

    def cells_init(self):
        r = random.Random(5)
        self.cell = 90
        self.cells = [(x, y) for y in range(0, H, 90) for x in range(0, W, 90)]
        r.shuffle(self.cells)

    def blocks(self, im, cov):
        if cov <= 0:
            return
        d = ImageDraw.Draw(im)
        for x, y in self.cells[:int(len(self.cells) * clamp(cov))]:
            d.rectangle((x, y, x + 90, y + 90), fill=(12, 10, 16, 255))


class Intro(Base):
    def __init__(self, tts, flags):
        super().__init__()
        self.cells_init()
        v = tts.say("Can you name all ten capitals? Let's go!", speed=1.15)
        self.voices.append((0.05, v))
        self.dur = max(2.4, 0.05 + len(v) / SR + 0.15)
        self.sounds += [(0.0, mq.sfx_boom(), 0.7), (0.0, sfx_whoosh(0.5), 0.8), (0.9, mq.sfx_levelup(), 0.8)]
        self.lines = [(bold("CAN YOU NAME", 112), 0.08, 380), (bold("ALL 10", 190, fill=YELLOW, stroke=14), 0.28, 545),
                      (bold("CAPITALS?", 150, fill=(110, 230, 90), stroke=12), 0.48, 720)]
        self.mini = [mq.fit(flags[q[0]][0], 190) for q in QUESTIONS]
        self.tag = mc_button("GEOGRAPHY QUIZ", 600, 104, (40, 120, 210), 40).rotate(5, Image.BICUBIC, expand=True)

    def render(self, t):
        im = self.gameplay.frame(self.t0 + t)
        im.alpha_composite(self.gameplay_dim)
        for i, fl in enumerate(self.mini):  # flags orbit in
            a = i / len(self.mini) * 2 * math.pi + t * 0.6
            k = ease_out_back((t - 0.15 - 0.04 * i) / 0.5)
            r = 420 * k
            paste_center(im, fl, W / 2 + r * math.cos(a), 600 + r * 0.95 * math.sin(a), clamp(k) * 0.95)
        for img, t0, y in self.lines:
            if t >= t0:
                s = 1 + 1.1 * (1 - ease_out_cubic((t - t0) / 0.16))
                paste_center(im, scaled(img, s), W / 2, y, clamp((t - t0) / 0.08))
        if t > 0.85:
            paste_center(im, scaled(self.tag, ease_out_back((t - 0.85) / 0.25)), W / 2, 900)
        fl = 1 - clamp(t / 0.3)
        if fl > 0:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))
        self.blocks(im, clamp((t - (self.dur - 0.15)) / 0.15))
        return im


class Question(Base):
    def __init__(self, tts, idx, q, flags, prev_level):
        super().__init__()
        self.cells_init()
        code, country, capital, said, level, trap = q
        self.idx, self.level, self.trap = idx, level, trap
        self.flag = flags[code]
        v = tts.say(f"What is the capital of {country.title()}?", speed=1.15)
        self.voices.append((T_IN + 0.05, v))
        a = tts.say(said, speed=1.15)
        self.reveal = T_IN + COUNTDOWN
        self.voices.append((self.reveal + 0.1, a))
        self.dur = self.reveal + max(1.05, 0.1 + len(a) / SR + 0.2)
        self.sounds.append((0.0, sfx_whoosh(0.3), 0.5))
        for k in range(4):
            self.sounds.append((T_IN + k, mq.sfx_tock(high=k >= 2), 1.0))
        self.sounds += [(self.reveal, mq.sfx_pling(), 1.0), (self.reveal, mq.sfx_crunch(), 0.7)]
        if trap:
            self.sounds.append((self.reveal + 0.45, mq.sfx_glitch(), 0.7))
        self.level_change = level != prev_level and idx > 1
        col = DIFF[level]
        if self.level_change:
            self.sounds.append((0.12, mq.sfx_levelup(), 1.0))
            txt = f"{level} MODE"
            self.banner = mc_button(("! " + txt + " !") if level == "HARD" else txt, 760, 120, col, 46)
        self.head = ptext(f"QUESTION {idx}/10", 40)
        self.badge = mc_button(level, 300, 84, col, 36)
        self.name = bold(country, 120, stroke=11, max_w=1000)
        self.prompt = ptext("CAPITAL CITY?", 44, fill=YELLOW)
        self.frame = bevel_box(220, 220)
        self.nums = {(n, red): ptext(str(n), 112, fill=(255, 80, 70) if red else (255, 255, 255))
                     for n in range(1, 5) for red in (False, True)}
        self.answer = bold(capital, 150, fill=YELLOW, stroke=12, max_w=1000)
        self.trap_img = ptext(trap, 40, fill=(255, 90, 80)) if trap else None
        self.plus = ptext("+1", 48, fill=(120, 255, 90))
        self.rays = mq.sunburst(760, col)
        r = random.Random(idx)
        cols = [col, YELLOW, (255, 255, 255)]
        self.burst = [(r.uniform(-700, 700), r.uniform(-1100, -300), r.randint(12, 24), r.choice(cols))
                      for _ in range(32)]

    def render(self, t):
        tg = self.t0 + t
        rv = t - self.reveal
        im = self.gameplay.frame(tg)
        im.alpha_composite(self.gameplay_shade)
        hk = ease_out_back(t / 0.3)
        paste_center(im, scaled(self.head, hk), W / 2, 185)
        paste_center(im, scaled(self.badge, hk), W / 2, 250)
        # waving flag drops in
        fl = self.flag[int(tg * 14) % len(self.flag)]
        fk = ease_out_back(t / 0.35, 1.4)
        paste_center(im, scaled(fl, 0.4 + 0.6 * fk), W / 2, FLAG_Y)
        paste_center(im, scaled(self.name, ease_out_back((t - 0.1) / 0.3)), W / 2, NAME_Y)
        if rv < 0:
            paste_center(im, self.prompt, W / 2, PROMPT_Y, clamp((t - 0.2) / 0.2))
        if rv < 0:
            cd = max(0.0, t - T_IN)
            n = max(1, 4 - int(cd))
            red = n <= 2
            k = ease_out_back((t - 0.15) / 0.3)
            paste_center(im, scaled(self.frame, k), W / 2, TIMER_Y)
            pop = 1 + 0.35 * (1 - ease_out_cubic((cd % 1) / 0.3))
            paste_center(im, scaled(self.nums[(n, red)], pop * k), W / 2, TIMER_Y + 4)
            frac = 1 - clamp(cd / COUNTDOWN)
            d = ImageDraw.Draw(im)
            bw, bh, segs = 700, 30, 20
            x0 = W / 2 - bw / 2
            d.rectangle((x0 - 6, BAR_Y - bh / 2 - 6, x0 + bw + 6, BAR_Y + bh / 2 + 6), fill=(0, 0, 0, 255))
            on = int(math.ceil(segs * frac))
            c = (255, 70, 60) if red else (128, 255, 40)
            for s in range(segs):
                sx = x0 + s * bw / segs
                d.rectangle((sx + 2, BAR_Y - bh / 2, sx + bw / segs - 2, BAR_Y + bh / 2),
                            fill=c + (255,) if s < on else (45, 45, 45, 255))
        else:
            rk = ease_out_back(rv / 0.3)
            paste_center(im, scaled(self.rays.rotate(rv * 40, Image.BICUBIC), 0.6 + 0.4 * rk), W / 2, ANSWER_Y)
            for vx, vy, s, c in self.burst:
                px, py = W / 2 + vx * rv, ANSWER_Y + vy * rv + 2200 * rv * rv
                if py < H:
                    ImageDraw.Draw(im).rectangle((px, py, px + s, py + s), fill=c + (255,))
            paste_center(im, scaled(self.answer, rk), W / 2, ANSWER_Y)
            if rv > 0.25:
                paste_center(im, self.plus, W / 2 + self.answer.width / 2 + 10, ANSWER_Y - 80,
                             clamp((rv - 0.25) / 0.15))
            if self.trap_img and rv > 0.4:
                tk = ease_out_back((rv - 0.4) / 0.25)
                paste_center(im, scaled(self.trap_img, tk).rotate(-3, Image.BICUBIC, expand=True), W / 2,
                             ANSWER_Y + 125)
            f = 1 - clamp(rv / 0.18)
            if f > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(220 * f))))
        if self.level_change and t < 1.0:
            bx = W / 2 + (1 - ease_out_cubic(t / 0.2)) * W - ease_in_cubic((t - 0.8) / 0.2) * W
            paste_center(im, self.banner.rotate(-4, Image.BICUBIC, expand=True), bx, TIMER_Y)
        self.blocks(im, 1 - clamp(t / T_IN))
        self.blocks(im, clamp((t - (self.dur - 0.15)) / 0.15))
        return im


class Ending(Base):
    def __init__(self, tts, flags):
        super().__init__()
        v = tts.say("How many did you get? Comment your score below!", speed=1.12)
        self.voices.append((0.2, v))
        self.dur = max(4.2, 0.2 + len(v) / SR + 1.4)
        self.sounds += [(0.0, sfx_whoosh(0.4), 0.7), (0.2, mq.sfx_levelup(), 0.9)]
        self.t1 = bold("HOW MANY", 120, fill=YELLOW, stroke=10)
        self.t2 = bold("DID YOU GET?", 120, fill=YELLOW, stroke=10)
        rows = [("0-3", "TOURIST", (120, 120, 130)), ("4-6", "TRAVELER", (60, 170, 70)),
                ("7-9", "EXPLORER", (60, 110, 220)), ("10/10", "GEOGRAPHY GENIUS!", (220, 150, 20))]
        self.rows = []
        for i, (rng_, label, col) in enumerate(rows):
            b = bevel_box(940, 120, fill=col + (235,), light=tuple(min(255, c + 70) for c in col),
                          dark=tuple(int(c * 0.5) for c in col), border=6)
            ri = ptext(rng_, 40)
            b.alpha_composite(ri, (40, 60 - ri.height // 2))
            li = bold(label, 60, fill=(255, 255, 255) if i < 3 else YELLOW, stroke=6, max_w=640)
            b.alpha_composite(li, (940 - 30 - li.width, 60 - li.height // 2))
            self.rows.append(b)
            self.sounds.append((0.6 + 0.2 * i, mq.sfx_crunch(), 0.7))
        ct = bold("COMMENT YOUR SCORE!", 62, stroke=7)
        e = emoji("👇", 80)
        self.cta = Image.new("RGBA", (ct.width + e.width + 10, max(ct.height, e.height)))
        self.cta.alpha_composite(ct, (0, (self.cta.height - ct.height) // 2))
        self.cta.alpha_composite(e, (ct.width + 10, (self.cta.height - e.height) // 2))
        self.minis = [mq.fit(flags[q[0]][0], 92) for q in QUESTIONS]
        self.sounds.append((1.5, mq.sfx_pling(), 0.8))

    def render(self, t):
        im = self.gameplay.frame(self.t0 + t)
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 110)))
        paste_center(im, scaled(self.t1, ease_out_back(t / 0.35)), W / 2, 330)
        paste_center(im, scaled(self.t2, ease_out_back((t - 0.12) / 0.35)), W / 2, 460)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - 0.6 - 0.2 * i) / 0.35)
            paste_center(im, row, W / 2 + (1 - k) * (W if i % 2 else -W), 640 + i * 145)
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.5) / 0.4) * (1 + 0.04 * math.sin(t * 8))), W / 2, 1250)
        for i, m in enumerate(self.minis):
            k = ease_out_back((t - 1.0 - 0.05 * i) / 0.3)
            paste_center(im, scaled(m, k), W / 2 + (i - 4.5) * 100, 1380)
        fl = clamp((t - (self.dur - 0.35)) / 0.35)  # matches the intro's first frame so the Short loops
        if fl > 0:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))
        return im


# ----------------------------------------------------------------------------

def shade_top():
    a = np.zeros((H, W, 4), np.uint8)
    ys = np.arange(H)
    a[..., 3] = (np.clip(1 - ys / 1300, 0, 1) ** 1.2 * 120)[:, None].astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def build(voice):
    mq.ensure_pixfont()
    tex = mq.make_textures()
    print("Rendering worlds ...", flush=True)
    worlds = build_road_worlds(tex)
    flags = {q[0]: wave_frames(q[0]) for q in QUESTIONS}
    tts = mv.TTS(voice, "en-gb" if voice.startswith("b") else "en-us")
    scenes = [Intro(tts, flags)]
    prev = None
    for i, q in enumerate(QUESTIONS, 1):
        scenes.append(Question(tts, i, q, flags, prev))
        prev = q[4]
    scenes.append(Ending(tts, flags))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    # background segments: one world per difficulty level
    segs, cur, seg_start = [], "plains", 0.0
    for sc in scenes[1:-1]:
        wname = LEVEL_WORLD[sc.level]
        if wname != cur:
            segs.append((cur, seg_start, sc.t0))
            cur, seg_start = wname, sc.t0
    segs.append((cur, seg_start, t))
    gp = Gameplay(worlds, segs)
    dim, shade = Image.new("RGBA", (W, H), (0, 0, 0, 70)), shade_top()
    for sc in scenes:
        sc.gameplay, sc.gameplay_dim, sc.gameplay_shade = gp, dim, shade
    return scenes, starts, t, gp, flags


def make_cover(gp, flags, path, base=None):
    im = base.convert("RGBA") if base is not None else gp.frame(3.0)
    im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 90)))
    for i, (code, x, y, s, rot) in enumerate((("FR", 230, 960, 290, 10), ("JP", 850, 960, 290, -10),
                                              ("BR", 200, 1250, 270, -8), ("CA", 880, 1250, 270, 8),
                                              ("AU", 540, 1400, 260, 3))):
        fl = mq.fit(flags[code][i * 3 % 16], s).rotate(rot, Image.BICUBIC, expand=True)
        paste_center(im, fl, x, y)
    paste_center(im, bold("CAN YOU NAME", 120, stroke=11), W / 2, 330)
    paste_center(im, bold("ALL 10", 230, fill=YELLOW, stroke=16), W / 2, 530)
    paste_center(im, bold("CAPITALS?", 170, fill=(110, 230, 90), stroke=14), W / 2, 740)
    paste_center(im, mc_button("99% FAIL", 460, 120, (210, 30, 30), 48).rotate(6, Image.BICUBIC, expand=True),
                 W / 2, 1110)
    im.convert("RGB").save(path, quality=92)
    print(path)


# ----------------------------------------------------------------------------
# recorded gameplay background
# ----------------------------------------------------------------------------
BG_CROP = "855:1520:20:205"  # clean 9:16 area of the screen recording (no YouTube buttons, title or comments)


def prepare_bg_video(src, total, boundaries, work):
    """Crop/scale the clip and loop it so the loop point lands exactly on a question change."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                               capture_output=True, text=True, check=True).stdout)
    cands = [b for b in boundaries if b <= dur - 0.05]
    seam = min(cands, key=lambda b: dur - b) if cands else dur
    offset = dur - seam
    seg, full = os.path.join(work, "bg_seg.mp4"), os.path.join(work, "bg_full.mp4")
    vf = f"crop={BG_CROP},scale={W}:{H}:flags=lanczos,fps={FPS},eq=saturation=1.08"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{offset:.3f}", "-i", src, "-vf", vf, "-an",
                    "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-g", "30", seg], check=True)
    loops = int(math.ceil(total / (dur - offset)))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", str(loops), "-i", seg, "-t", f"{total:.3f}",
                    "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-g", "30", full], check=True)
    print(f"Background: {dur:.2f}s clip, loop seam at {seam:.2f}s (start offset {offset:.2f}s)")
    return full


def bg_frame(full, t):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", full, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return Image.frombytes("RGB", (W, H), raw[:W * H * 3])


BG = {}


def render_chunk_video(args):
    idx, a, b, path = args
    dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-ss", f"{a / FPS:.4f}", "-i", BG["full"],
                            "-frames:v", str(b - a), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                            "-crf", "20", "-pix_fmt", "yuv420p", "-g", "60", path], stdin=subprocess.PIPE)
    last = None
    scenes, starts = mv.G["scenes"], mv.G["starts"]
    for i in range(a, b):
        raw = dec.stdout.read(W * H * 3)
        if len(raw) == W * H * 3:
            last = raw
        base = Image.frombytes("RGB", (W, H), last).convert("RGBA")
        t = i / FPS
        k = max(0, np.searchsorted(starts, t, side="right") - 1)
        sc = scenes[k]
        base.alpha_composite(sc.render(min(t - starts[k], sc.dur - 1e-4)))
        enc.stdin.write(base.convert("RGB").tobytes())
        if idx == 0 and (i - a) % 150 == 0:
            print(f"  chunk 0: {i - a}/{b - a} frames", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.wait()
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_capitals_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="bm_george")
    ap.add_argument("--bg-video", default=None, help="recorded gameplay clip to use as the background")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    scenes, starts, total, gp, flags = build(args.voice)
    work = os.path.join(mv.CACHE_DIR, "render_cap")
    full = None
    if args.bg_video:
        os.makedirs(work, exist_ok=True)
        gp.video = True
        full = prepare_bg_video(args.bg_video, total, starts[1:], work)
        BG["full"] = full
    for sc, st in zip(scenes, starts):
        print(f"  {st:6.2f}s  {type(sc).__name__} {getattr(sc, 'idx', '')}")
    print(f"Duration {total:.1f}s; worlds: {gp.segments}")
    if args.cover:
        make_cover(gp, flags, os.path.join(HERE, "capitals_quiz_cover.jpg"), bg_frame(full, 3.0) if full else None)
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if args.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in args.stills.split(","):
            p = os.path.join(d, f"cap_{float(s):06.2f}.png")
            fr = mv.frame_at(int(float(s) * FPS))
            if full:
                base = bg_frame(full, float(s)).convert("RGBA")
                k = max(0, np.searchsorted(starts, float(s), side="right") - 1)
                base.alpha_composite(scenes[k].render(min(float(s) - starts[k], scenes[k].dur - 1e-4)))
                fr = base.convert("RGB")
            fr.save(p)
            print(p)
        return
    for f in os.listdir(work) if os.path.isdir(work) else []:
        if f.startswith("part") or f.endswith(".wav") or f.endswith(".txt"):
            os.remove(os.path.join(work, f))
    os.makedirs(work, exist_ok=True)
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mix_with_steps(scenes, starts, total, gp))
    nframes = int(total * FPS)
    n = max(1, args.workers)
    bounds = [round(nframes * k / n) for k in range(n + 1)]
    jobs = [(k, bounds[k], bounds[k + 1], os.path.join(work, f"part{k}.mp4")) for k in range(n)]
    with mp.get_context("fork").Pool(n) as pool:
        parts = pool.map(render_chunk_video if full else mv.render_chunk, jobs)
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
