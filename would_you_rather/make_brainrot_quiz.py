#!/usr/bin/env python3
""""GUESS THE BRAINROT BY THE PICTURE!" - vertical quiz Short (1080x1920).

10 famous Italian brainrot characters drawn as original emoji fusions
(brainrot_pictures.py, Noto 3D emoji, Apache 2.0). Questions are asked by the
British narrator, and the names are shouted by an Italian voice. Background:
a recorded parkour gameplay clip (--bg-video), or an animated backdrop.

    python3 make_brainrot_quiz.py --bg-video gameplay.mp4
    python3 make_brainrot_quiz.py --stills 3,9 --bg-video gameplay.mp4
    python3 make_brainrot_quiz.py --cover --bg-video gameplay.mp4
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

import brainrot_pictures as bp  # noqa: E402
import make_capitals_quiz as cq  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_minecraft_quiz import DIFF, YELLOW, bevel_box, bold, mc_button, ptext, rich_block  # noqa: E402
from make_video import (SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center,  # noqa: E402
                        radial_glow, scaled, sfx_whoosh)

W, H, FPS = 1080, 1920, 30
T_IN, COUNTDOWN = 0.22, 4.0
PIC_Y, PROMPT_Y, TIMER_Y, BAR_Y, NAME_Y = 690, 1135, 1265, 1395, 1260
DEFAULT_BG = "/root/.claude/uploads/8099515e-e335-5ef5-8415-d5b64fec78af/36ace3b2-Screen_Recording_compressed_1.mp4"

QUESTIONS = [  # picture key, name on screen, Italian shout, level, British prompt
    ("tralalero", "TRALALERO TRALALA", "Tralalero Tralalà!", "EASY", "Who is this?"),
    ("tungtung", "TUNG TUNG TUNG SAHUR", "Tung tung tung tung sahur!", "EASY", "Name this brainrot!"),
    ("bombardiro", "BOMBARDIRO CROCODILO", "Bombardiro Crocodilo!", "EASY", "Who's this one?"),
    ("ballerina", "BALLERINA CAPPUCCINA", "Ballerina Cappuccina!", "EASY", "Easy one!"),
    ("chimpanzini", "CHIMPANZINI BANANINI", "Chimpanzini Bananini!", "NORMAL", "Who is it?"),
    ("lirili", "LIRILÌ LARILÀ", "Lirilì Larilà!", "NORMAL", "Guess this one!"),
    ("cappuccino", "CAPPUCCINO ASSASSINO", "Cappuccino Assassino!", "NORMAL", "Do you know him?"),
    ("patapim", "BRR BRR PATAPIM", "Brr brr patapim!", "MEDIUM", "This one's tricky!"),
    ("trippi", "TRIPPI TROPPI TROPPA TRIPPA", "Trippi troppi troppa trippa!", "MEDIUM", "Who could this be?"),
    ("lavaca", "LA VACA SATURNO SATURNITA", "La vaca saturno saturnita!", "MEDIUM", "Last one!"),
]
PURPLE = (150, 70, 255)


REAL_DIR = os.path.join(HERE, "brainrot_real")  # real pictures: brainrot_real/<key>.jpg (or .png)


def real_picture(key, size=700):
    """Framed real picture for a character if one was supplied, else None (emoji fusion is used)."""
    import glob
    hits = sorted(glob.glob(os.path.join(REAL_DIR, key + ".*")))
    if not hits:
        return None
    src = Image.open(hits[0]).convert("RGB")
    s = min(size / src.width, size / src.height)
    src = src.resize((int(src.width * s), int(src.height * s)), Image.LANCZOS)
    border, pad = 14, 50
    card = mq.rounded_card(src.width + 2 * border, src.height + 2 * border, 40, (255, 255, 255, 255))
    mask = mq.rounded_card(src.width, src.height, 30, (255, 255, 255, 255)).getchannel("A")
    ph = src.convert("RGBA")
    ph.putalpha(mask)
    card.alpha_composite(ph, (border, border))
    out = Image.new("RGBA", (card.width + 2 * pad, card.height + 2 * pad))
    sh = mq.rounded_card(card.width, card.height, 40, (0, 0, 0, 170))
    out.alpha_composite(sh, (pad + 8, pad + 22))
    from PIL import ImageFilter
    out = out.filter(ImageFilter.GaussianBlur(16))
    out.alpha_composite(card, (pad, pad))
    return out


def pic_for(key):
    return real_picture(key) or bp.picture(key)


def fit_box(im, box):
    s = box / max(im.width, im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def art(name, size):
    return Image.open(os.path.join(bp.ART, name + ".png")).convert("RGBA").resize((size, size), Image.LANCZOS)


def tint_overlay(logo_bg=False):
    """Vignette over the background so the quiz pops (purple for gameplay, soft navy for the logo background)."""
    a = np.zeros((H, W, 4), np.uint8)
    if logo_bg:
        ys, xs = np.mgrid[0:H, 0:W]
        d = np.sqrt(((xs - W / 2) / (W * 0.75)) ** 2 + ((ys - H * 0.45) / (H * 0.65)) ** 2)
        a[..., 0], a[..., 1], a[..., 2] = 4, 8, 28
        a[..., 3] = np.clip(120 * (d - 0.5), 0, 120).astype(np.uint8)
        return Image.fromarray(a, "RGBA")
    a[..., 0], a[..., 1], a[..., 2] = 40, 10, 70
    ys, xs = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xs - W / 2) / (W * 0.75)) ** 2 + ((ys - H * 0.45) / (H * 0.65)) ** 2)
    a[..., 3] = np.clip(70 + 120 * d, 0, 190).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def fallback_bg(t):
    """Animated backdrop when no gameplay clip is given."""
    im = mv.vgradient(W, H, (90, 30, 160), (20, 10, 50)).convert("RGBA")
    rays = mq.sunburst(2200, (255, 120, 220), 18).rotate(t * 12, Image.BICUBIC)
    paste_center(im, rays, W / 2, H * 0.4)
    return im


class Base(cq.Base):
    first = False
    loop_flash = True

    def bg(self, t):
        if self.video:
            return Image.new("RGBA", (W, H), (0, 0, 0, 0))
        return fallback_bg(self.t0 + t)


class Intro(Base):
    def __init__(self, tts, it):
        super().__init__()
        self.cells_init()
        v = tts.say("Guess the brainrot by the picture!", speed=1.15)
        self.voices.append((0.05, v))
        shout = it.say("Tralalero tralalà!", speed=1.05)
        self.voices.append((0.05 + len(v) / SR + 0.05, shout))
        self.dur = max(2.6, 0.05 + len(v) / SR + 0.05 + len(shout) / SR * 0.6)
        self.sounds += [(0.0, mq.sfx_boom(), 0.9), (0.0, sfx_whoosh(0.5), 0.8), (1.0, mq.sfx_levelup(), 0.8)]
        self.lines = [(bold("GUESS THE", 130), 0.08, 330),
                      (bold("BRAINROT", 200, fill=YELLOW, stroke=16), 0.28, 520),
                      (bold("BY THE PICTURE!", 104, fill=(255, 140, 230), stroke=10), 0.5, 700)]
        self.pics = [fit_box(pic_for(k), 340) for k in ("tralalero", "tungtung", "bombardiro")]
        self.brain = art("brain", 220)

    def render(self, t):
        im = self.bg(t)
        im.alpha_composite(self.tint)
        for i, p in enumerate(self.pics):
            k = ease_out_back((t - 0.6 - 0.15 * i) / 0.4)
            x = W / 2 + (i - 1) * 330
            paste_center(im, scaled(p.rotate(8 * math.sin(t * 5 + i), Image.BICUBIC, expand=True), k), x,
                         1020 + 20 * math.sin(t * 4 + i))
        for img, t0, y in self.lines:
            if t >= t0:
                s = 1 + 1.1 * (1 - ease_out_cubic((t - t0) / 0.16))
                paste_center(im, scaled(img.rotate(3 * math.sin(t * 9), Image.BICUBIC, expand=True), s), W / 2, y,
                             clamp((t - t0) / 0.08))
        paste_center(im, scaled(self.brain, ease_out_back((t - 0.9) / 0.3)), W / 2 + 330, 180)
        fl = 1 - clamp(t / 0.3)
        if fl > 0:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))
        self.blocks(im, clamp((t - (self.dur - 0.15)) / 0.15))
        return im


class Question(Base):
    def __init__(self, tts, it, idx, q, prev_level):
        super().__init__()
        self.cells_init()
        key, name, shout, level, prompt = q
        self.idx, self.level = idx, level
        v = tts.say(prompt, speed=1.15)
        self.voices.append((T_IN + 0.05, v))
        s = it.say(shout, speed=1.05)
        self.reveal = T_IN + COUNTDOWN
        self.voices.append((self.reveal + 0.1, s))
        self.dur = self.reveal + max(1.25, 0.1 + len(s) / SR + 0.25)
        self.sounds.append((0.0, sfx_whoosh(0.3), 0.5))
        for k in range(4):
            self.sounds.append((T_IN + k, mq.sfx_tock(high=k >= 2), 1.0))
        self.sounds += [(self.reveal, mq.sfx_boom(), 0.8), (self.reveal, mq.sfx_pling(), 0.9)]
        self.level_change = level != prev_level and idx > 1
        col = DIFF[level]
        if self.level_change:
            self.sounds.append((0.12, mq.sfx_levelup(), 1.0))
            self.banner = mc_button(f"{level} MODE", 700, 120, col, 46)
        self.head = ptext(f"BRAINROT {idx}/10", 40)
        self.badge = mc_button(level, 300, 84, col, 36)
        self.pic = real_picture(key) or bp.picture(key)
        self.glow = radial_glow(900, 900, 450, 450, 450, (255, 255, 255), 0.55)
        self.rays = mq.sunburst(1000, (255, 120, 220) if idx % 2 else (120, 200, 255), 16)
        tq = bold("WHO IS THIS?", 96, fill=YELLOW, stroke=9)
        e = emoji("🤔", 100)
        self.prompt = Image.new("RGBA", (tq.width + e.width + 10, max(tq.height, e.height)))
        self.prompt.alpha_composite(tq, (0, (self.prompt.height - tq.height) // 2))
        self.prompt.alpha_composite(e, (tq.width + 10, (self.prompt.height - e.height) // 2))
        self.frame = bevel_box(190, 190)
        self.nums = {(n, red): ptext(str(n), 104, fill=(255, 80, 70) if red else (255, 255, 255))
                     for n in range(1, 5) for red in (False, True)}
        self.name = rich_block(name, 112, 960, base=YELLOW, stroke=10)
        self.flag = Image.new("RGBA", (360, 22))
        d = ImageDraw.Draw(self.flag)
        for i, c in enumerate(((0, 146, 70), (245, 245, 245), (206, 43, 55))):  # Italian colours
            d.rectangle((i * 120, 0, i * 120 + 119, 21), fill=c + (255,))
        self.plus = ptext("+1", 48, fill=(120, 255, 90))
        r = random.Random(idx)
        bits = [art(n, 96) for n in ("skull", "fire", "brain")]
        self.burst = [(r.choice(bits), r.uniform(-900, 900), r.uniform(-1500, -500), r.uniform(-400, 400))
                      for _ in range(16)]

    def render(self, t):
        rv = t - self.reveal
        shake = (0, 0)
        if 0 < rv < 0.45:
            a = 30 * (1 - rv / 0.45)
            shake = (a * math.sin(rv * 90), a * math.cos(rv * 75))
        im = self.bg(t)
        im.alpha_composite(self.tint)
        ta = t + 0.5 if self.first else t  # first question opens fully formed (no empty first frame)
        hk = ease_out_back(ta / 0.3)
        paste_center(im, scaled(self.head, hk), W / 2, 185)
        paste_center(im, scaled(self.badge, hk), W / 2, 250)
        # picture: spinning rays behind, bouncy pop-in, wobble, big bounce on reveal
        paste_center(im, self.rays.rotate(t * 25, Image.BICUBIC), W / 2 + shake[0], PIC_Y + shake[1], 0.55)
        paste_center(im, self.glow, W / 2, PIC_Y)
        pk = ease_out_back(ta / 0.35, 1.6)
        s = (0.3 + 0.7 * pk) * (1 + 0.025 * math.sin(t * 6))
        if rv > 0:
            s *= 1 + 0.12 * math.sin(math.pi * clamp(rv / 0.3))
        pic = scaled(self.pic, s * 0.95).rotate(4 * math.sin(t * 3.2), Image.BICUBIC, expand=True)
        paste_center(im, pic, W / 2 + shake[0], PIC_Y + shake[1])
        if rv < 0:
            paste_center(im, scaled(self.prompt, ease_out_back((ta - 0.15) / 0.3)), W / 2, PROMPT_Y)
            cd = max(0.0, t - T_IN)
            n = max(1, 4 - int(cd))
            red = n <= 2
            k = ease_out_back((ta - 0.2) / 0.3)
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
            for sg in range(segs):
                sx = x0 + sg * bw / segs
                d.rectangle((sx + 2, BAR_Y - bh / 2, sx + bw / segs - 2, BAR_Y + bh / 2),
                            fill=c + (255,) if sg < on else (45, 45, 45, 255))
        else:
            for spr, vx, vy, vr in self.burst:  # skulls, fire and brains fly out
                px, py = W / 2 + vx * rv, PIC_Y + vy * rv + 2400 * rv * rv
                if py < H + 100:
                    paste_center(im, spr.rotate(vr * rv, Image.BICUBIC, expand=True), px, py)
            nk = ease_out_back(rv / 0.28)
            tilt = -4 + 3 * math.sin(rv * 10) * (1 - clamp(rv / 0.6))
            paste_center(im, scaled(self.name, nk).rotate(tilt, Image.BICUBIC, expand=True), W / 2, NAME_Y)
            paste_center(im, scaled(self.flag, nk), W / 2, NAME_Y + self.name.height / 2 + 30)
            if rv > 0.25:
                paste_center(im, self.plus, W - 110, NAME_Y - self.name.height / 2 - 30, clamp((rv - 0.25) / 0.15))
            f = 1 - clamp(rv / 0.2)
            if f > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(230 * f))))
        if self.level_change and t < 1.0:
            bx = W / 2 + (1 - ease_out_cubic(t / 0.2)) * W - ease_in_cubic((t - 0.8) / 0.2) * W
            paste_center(im, self.banner.rotate(-4, Image.BICUBIC, expand=True), bx, TIMER_Y)
        if not self.first:
            self.blocks(im, 1 - clamp(t / T_IN))
        self.blocks(im, clamp((t - (self.dur - 0.15)) / 0.15))
        return im


class Ending(Base):
    def __init__(self, tts, it):
        super().__init__()
        v = tts.say("How many did you get? Comment your score below!", speed=1.12)
        self.voices.append((0.2, v))
        self.dur = max(4.3, 0.2 + len(v) / SR + 1.4)
        self.sounds += [(0.0, sfx_whoosh(0.4), 0.7), (0.2, mq.sfx_levelup(), 0.9)]
        self.t1 = bold("HOW MANY", 120, fill=YELLOW, stroke=10)
        self.t2 = bold("DID YOU GET?", 120, fill=YELLOW, stroke=10)
        rows = [("0-3", "NORMIE", (120, 120, 130)), ("4-6", "BRAINROT ROOKIE", (60, 170, 70)),
                ("7-9", "BRAINROT PRO", (60, 110, 220)), ("10/10", "MAXIMUM BRAINROT!", (220, 60, 160))]
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
        self.skull = art("skull", 110)
        ct = bold("COMMENT YOUR SCORE!", 62, stroke=7)
        e = emoji("👇", 80)
        self.cta = Image.new("RGBA", (ct.width + e.width + 10, max(ct.height, e.height)))
        self.cta.alpha_composite(ct, (0, (self.cta.height - ct.height) // 2))
        self.cta.alpha_composite(e, (ct.width + 10, (self.cta.height - e.height) // 2))
        self.minis = [fit_box(pic_for(q[0]), 96) for q in QUESTIONS]
        self.sounds.append((1.5, mq.sfx_pling(), 0.8))

    def render(self, t):
        im = self.bg(t)
        im.alpha_composite(self.tint)
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 70)))
        paste_center(im, scaled(self.t1, ease_out_back(t / 0.35)), W / 2, 330)
        paste_center(im, scaled(self.t2, ease_out_back((t - 0.12) / 0.35)), W / 2, 460)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - 0.6 - 0.2 * i) / 0.35)
            paste_center(im, row, W / 2 + (1 - k) * (W if i % 2 else -W), 640 + i * 145)
        paste_center(im, scaled(self.skull, ease_out_back((t - 0.4) / 0.3)), W - 95, 400)
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.5) / 0.4) * (1 + 0.04 * math.sin(t * 8))), W / 2, 1250)
        for i, m in enumerate(self.minis):
            k = ease_out_back((t - 1.0 - 0.05 * i) / 0.3)
            paste_center(im, scaled(m, k), W / 2 + (i - 4.5) * 98, 1390 + 8 * math.sin(t * 5 + i))
        if self.loop_flash:
            fl = clamp((t - (self.dur - 0.35)) / 0.35)  # matches the intro's first frame so the Short loops
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))
        else:
            self.cells_init() if not hasattr(self, "cells") else None
            self.blocks(im, clamp((t - (self.dur - 0.2)) / 0.2))
        return im


def build(video, logo_bg=False, intro=True, voice="am_adam", italian="im_nicola"):
    mq.ensure_pixfont()
    tts = mv.TTS(voice, "en-gb" if voice.startswith("b") else "en-us")
    it = mv.TTS(italian, "it")
    scenes = [Intro(tts, it)] if intro else []
    prev = None
    for i, q in enumerate(QUESTIONS, 1):
        scenes.append(Question(tts, it, i, q, prev))
        prev = q[3]
    scenes.append(Ending(tts, it))
    if not intro:
        scenes[0].first = True          # no block reveal on the very first frame
        scenes[-1].loop_flash = False   # end on a block wipe that loops into question 1
    tint = tint_overlay(logo_bg)
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0, sc.video, sc.tint = t, video, tint
        starts.append(t)
        t += sc.dur
    return scenes, starts, t


def compose(scenes, starts, t, full):
    k = max(0, np.searchsorted(starts, t, side="right") - 1)
    over = scenes[k].render(min(t - starts[k], scenes[k].dur - 1e-4))
    if not full:
        return over.convert("RGB")
    base = cq.bg_frame(full, t).convert("RGBA")
    base.alpha_composite(over)
    return base.convert("RGB")


def make_cover(full, path, logo_bg=False):
    base = cq.bg_frame(full, 5.0).convert("RGBA") if full else fallback_bg(0)
    base.alpha_composite(tint_overlay(logo_bg))
    paste_center(base, mq.sunburst(1600, (255, 120, 220), 16), W / 2, 1000, 0.6)
    paste_center(base, bold("GUESS THE", 130, stroke=12), W / 2, 280)
    paste_center(base, bold("BRAINROT", 220, fill=YELLOW, stroke=18, max_w=1000), W / 2, 480)
    pics = [("tralalero", 260, 930, 480, -8), ("tungtung", 830, 930, 480, 8), ("bombardiro", 540, 1250, 520, 0)]
    for key, x, y, s, rot in pics:
        paste_center(base, fit_box(pic_for(key), s).rotate(rot, Image.BICUBIC, expand=True), x, y)
    paste_center(base, mc_button("99% FAIL", 460, 120, (210, 30, 30), 48).rotate(-6, Image.BICUBIC, expand=True),
                 W / 2, 680)
    paste_center(base, art("skull", 170), 150, 1450)
    paste_center(base, art("brain", 170), W - 150, 1450)
    base.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_brainrot_quiz.mp4"))
    ap.add_argument("--bg-video", default=DEFAULT_BG if os.path.exists(DEFAULT_BG) else None)
    ap.add_argument("--logo-bg", default=None, metavar="COLOR",
                    help="use the scrolling Quizzies logo background (e.g. darkblue, orange) instead of gameplay")
    ap.add_argument("--intro", action="store_true", help="start with the title intro (default: straight to Q1)")
    ap.add_argument("--voice", default="am_adam",
                    help='narrator: a Kokoro voice (bm_george) or an ElevenLabs voice ("eleven:Brian")')
    ap.add_argument("--italian-voice", default="im_nicola",
                    help='voice that shouts the names (im_nicola or e.g. "eleven:Giovanni")')
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    if args.logo_bg:
        args.bg_video = None
    scenes, starts, total = build(bool(args.bg_video or args.logo_bg), bool(args.logo_bg), args.intro,
                                  args.voice, args.italian_voice)
    for sc, st in zip(scenes, starts):
        print(f"  {st:6.2f}s  {type(sc).__name__} {getattr(sc, 'idx', '')}")
    print(f"Duration {total:.1f}s")
    work = os.path.join(mv.CACHE_DIR, "render_brainrot")
    os.makedirs(work, exist_ok=True)
    full = cq.prepare_bg_video(args.bg_video, total, starts[1:], work, crossfade=0.6) if args.bg_video else None
    if args.logo_bg:
        loop = os.path.join(HERE, f"quizzies_background_{args.logo_bg}.mp4")
        if not os.path.exists(loop):
            subprocess.run([sys.executable, "-I", os.path.join(HERE, "make_logo_background.py"), "--color",
                            args.logo_bg, "--video", "12"], check=True)
        full = os.path.join(work, "bg_full.mp4")  # the 12 s loop is seamless, so plain looping never jumps
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", loop, "-t", f"{total:.3f}",
                        "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-g", "30", full], check=True)
    if args.cover:
        make_cover(full, os.path.join(HERE, "brainrot_quiz_cover.jpg"), bool(args.logo_bg))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if args.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in args.stills.split(","):
            p = os.path.join(d, f"br_{float(s):06.2f}.png")
            compose(scenes, starts, float(s), full).save(p)
            print(p)
        return
    for f in os.listdir(work):
        if f.startswith("part") or f.endswith(".wav") or f.endswith(".txt"):
            os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mq.mix(scenes, starts, total, "chiptune"))
    nframes = int(total * FPS)
    n = max(1, args.workers)
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
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", args.out], check=True)
    print(f"Done: {args.out}")


if __name__ == "__main__":
    main()
