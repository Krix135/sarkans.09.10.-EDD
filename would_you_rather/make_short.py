#!/usr/bin/env python3
"""Vertical YouTube Short (1080x1920, under 60 s): "Would You Rather? Food Edition".

Reuses the drawing, audio and TTS engine from make_video.py. The layout keeps
everything important out of the areas the Shorts player covers: the top bar,
the title/channel text at the bottom and the like/comment buttons on the right.

    python3 make_short.py                     # food, 4 questions
    python3 make_short.py --subject Animals --seed 3
    python3 make_short.py --stills 2,8,12     # preview frames only
"""

import argparse
import math
import os
import random
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

import make_video as mv
from make_video import (ALARM, BLUE_BOT, BLUE_TOP, RED_BOT, RED_TOP, SR, YELLOW, Bokeh, Scene, circle, clamp,
                        dark_bg, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, font, paste_center,
                        radial_glow, rounded_card, scaled, sfx_ding, sfx_fanfare, sfx_pop, sfx_riser, sfx_tick,
                        sfx_whoosh, soft_circle, text_img, vgradient, wrap)
from questions import SUBJECTS

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H  # shared helpers (dark_bg, Bokeh, render_chunk) draw at Shorts size
COUNTDOWN = 3
SPLIT = 880        # red panel 0..SPLIT, blue panel SPLIT..H
BADGE_Y = SPLIT
NAVY = (20, 22, 45)
HERE = os.path.dirname(os.path.abspath(__file__))
MAX_LEN = 59.0


def outlined(text, size, fill=(255, 255, 255), stroke=8):
    return text_img(text, font("Black", size), fill=fill, stroke=stroke, stroke_fill=(0, 0, 0))


def option_text(text, top):
    """Pre-render an option caption, shrinking until it fits in 2-3 lines."""
    size = 70
    while True:
        f = font("ExtraBold", size)
        lines = wrap(text, f, 860)
        if (len(lines) <= 2 and all(f.getlength(l) <= 880 for l in lines)) or size <= 46:
            break
        size -= 4
    lh = int(size * 1.15)
    imgs = [text_img(l, f, stroke=3, stroke_fill=(0, 0, 0)) for l in lines]
    out = Image.new("RGBA", (max(i.width for i in imgs), lh * (len(imgs) - 1) + imgs[0].height))
    for k, i in enumerate(imgs):
        out.alpha_composite(i, ((out.width - i.width) // 2, k * lh))
    return out


class HookScene(Scene):
    def __init__(self, tts, subject):
        super().__init__()
        v = tts.say(f"Would you rather? {subject} edition! You get {COUNTDOWN} seconds. Go!", speed=1.12)
        self.voices.append((0.15, v))
        self.dur = max(2.6, 0.15 + len(v) / SR + 0.25)
        self.sounds += [(0.0, sfx_whoosh(0.5), 0.9), (0.3, sfx_pop(), 1.0), (0.55, sfx_pop(), 1.0),
                        (0.9, sfx_fanfare(), 0.7)]
        self.bg = dark_bg()
        self.bokeh = Bokeh(5, n=18)
        self.l1 = outlined("WOULD YOU", 150, stroke=10)
        self.l2 = outlined("RATHER?", 190, fill=YELLOW, stroke=12)
        e = emoji(SUBJECTS[subject]["emoji"], 80)
        st = text_img(f"{subject.upper()} EDITION", font("Black", 64), fill=NAVY, shadow=False)
        chip = rounded_card(st.width + e.width + 90, 120, 60, (255, 255, 255, 255))
        paste_center(chip, e, 40 + e.width / 2, 60)
        paste_center(chip, st, 60 + e.width + st.width / 2, 62)
        self.chip = chip
        r = random.Random(8)
        foods = [q[i] for q in SUBJECTS[subject]["questions"] for i in (1, 3)] + ["🍔", "🍟", "🌮", "🍩", "🍣"]
        self.floaters = [(emoji(f, r.randint(110, 170)), r.uniform(80, W - 80), r.uniform(200, H - 200),
                          r.uniform(0, 6.28)) for f in foods[:12]]

    def render(self, t):
        im = self.bg.copy()
        self.bokeh.draw(im, t)
        for spr, x, y, ph in self.floaters:
            s = ease_out_back((t - 0.1) / 0.5)
            paste_center(im, scaled(spr.rotate(10 * math.sin(t * 2 + ph), expand=True), s),
                         x + 20 * math.sin(t * 1.5 + ph), y - 40 * t, 0.45)
        paste_center(im, scaled(self.l1, ease_out_back((t - 0.2) / 0.4)), W / 2, 760)
        paste_center(im, scaled(self.l2, ease_out_back((t - 0.4) / 0.45) * (1 + 0.03 * math.sin(t * 8))), W / 2, 950)
        paste_center(im, scaled(self.chip, ease_out_back((t - 0.75) / 0.4)), W / 2, 1160)
        fade = clamp((t - (self.dur - 0.25)) / 0.25)
        if fade > 0:
            im.alpha_composite(Image.new("RGBA", (W, H), mv.BG + (int(255 * fade),)))
        return im


class ShortQuestion(Scene):
    def __init__(self, tts, q, pct_a, qi, total, prefix):
        super().__init__()
        a, ea, b, eb = q[:4]
        self.pct = (pct_a, 100 - pct_a)
        self.win = 0 if pct_a >= 50 else 1
        low = lambda s: s[0].lower() + s[1:]
        v1 = tts.say(f"{prefix}Would you rather {low(a)}... or {low(b)}?", speed=1.1)
        v2 = tts.say(f"{max(self.pct)} percent said {low(a if self.win == 0 else b)}!", speed=1.12)
        self.cd_start = 0.35 + len(v1) / SR + 0.2
        self.reveal = self.cd_start + COUNTDOWN
        self.voices += [(0.35, v1), (self.reveal + 0.45, v2)]
        self.t_out = max(self.reveal + 0.45 + len(v2) / SR + 0.35, self.reveal + 2.2)
        self.dur = self.t_out + 0.3
        self.sounds += [(0.0, sfx_whoosh(0.4), 0.8), (0.3, sfx_pop(), 0.9)]
        for k in range(COUNTDOWN):
            self.sounds.append((self.cd_start + k, sfx_tick(high=True), 1.0))
        self.sounds += [(self.reveal - 1.2, sfx_riser(1.15), 0.6), (self.reveal, sfx_ding(), 1.0),
                        (self.t_out, sfx_whoosh(0.35), 0.7)]

        # panels: red on top, blue below; percentages sit next to the OR badge
        top = vgradient(W, SPLIT, RED_TOP, RED_BOT).convert("RGBA")
        top.alpha_composite(radial_glow(W, SPLIT, W / 2, 380, 420, (255, 255, 255), 0.22))
        self._stripes(top)
        paste_center(top, emoji(ea, 205), W / 2, 355)
        ot = option_text(a, True)
        paste_center(top, ot, W / 2, 470 + ot.height / 2)  # top-anchored so it never hits the %
        bot = vgradient(W, H - SPLIT, BLUE_TOP, BLUE_BOT).convert("RGBA")
        bot.alpha_composite(radial_glow(W, H - SPLIT, W / 2, 360, 420, (255, 255, 255), 0.22))
        self._stripes(bot)
        paste_center(bot, emoji(eb, 230), W / 2, 365)
        paste_center(bot, option_text(b, False), W / 2, 580)
        self.panels = (top, bot)
        self.pct_y = (722, SPLIT + 178)

        self.title = outlined("WOULD YOU RATHER?", 64, stroke=6)
        self.dots = (qi, total)
        self.badge = circle(180, (255, 255, 255, 255))
        self.badge_ring = circle(200, NAVY + (255,))
        self.badge_shadow = soft_circle(190, (0, 0, 0, 150), 12)
        self.or_txt = text_img("OR", font("Black", 72), fill=NAVY, shadow=False)
        self.crown = emoji("👑", 90)
        self.bg = Image.new("RGBA", (W, H), mv.BG + (255,))
        self._cache = {}

    @staticmethod
    def _stripes(p):
        ov = Image.new("RGBA", p.size)
        d = ImageDraw.Draw(ov)
        for x in range(-p.height, p.width, 60):
            d.line((x, p.height, x + p.height, 0), fill=(255, 255, 255, 9), width=22)
        p.alpha_composite(ov)

    def _txt(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def render(self, t):
        im = self.bg.copy()
        e = ease_out_cubic(t / 0.45) if t < self.t_out else 1 - ease_in_cubic((t - self.t_out) / 0.3)
        ty = int(-SPLIT * (1 - e))
        by = int(SPLIT + (H - SPLIT) * (1 - e))
        im.alpha_composite(self.panels[0], (0, ty))
        im.alpha_composite(self.panels[1], (0, by))
        rv = t - self.reveal
        if rv > 0:
            k = ease_out_cubic(rv / 0.8)
            for side, (y0, hgt) in enumerate(((ty, SPLIT), (by, H - SPLIT))):
                pct = self.pct[side]
                fill_w = int(W * pct / 100 * k)  # poll bar sweeping across each panel
                im.alpha_composite(Image.new("RGBA", (max(1, fill_w), hgt), (255, 255, 255, 38)), (0, y0))
                if side != self.win:
                    dk = clamp((rv - 0.8) / 0.3)
                    im.alpha_composite(Image.new("RGBA", (W, hgt), (0, 0, 0, int(110 * dk))), (0, y0))
                shown = int(round(pct * k))
                col = YELLOW if side == self.win and rv > 0.8 else (255, 255, 255)
                pi = self._txt(("p", shown, col), lambda: outlined(f"{shown}%", 120, fill=col, stroke=8))
                pop = 1 + 0.15 * math.sin(math.pi * clamp(rv / 0.45))
                cx = W / 2 + (60 if side == self.win else 0)
                py = self.pct_y[side] + (y0 - (0 if side == 0 else SPLIT))
                paste_center(im, scaled(pi, pop), cx, py)
                if side == self.win:
                    cs = ease_out_back((rv - 0.8) / 0.35)
                    paste_center(im, scaled(self.crown, cs), cx - pi.width / 2 - 30, py - 6)
        # OR badge + countdown ring
        bs = ease_out_back((t - 0.25) / 0.35) * e
        cx, cy = W / 2, BADGE_Y
        if bs > 0.01:
            paste_center(im, scaled(self.badge_shadow, bs), cx, cy + 10)
            paste_center(im, scaled(self.badge_ring, bs), cx, cy)
            paste_center(im, scaled(self.badge, bs), cx, cy)
            cd = t - self.cd_start
            if 0 <= cd < COUNTDOWN:
                n = COUNTDOWN - int(cd)
                ring = Image.new("RGBA", (500, 500))
                d = ImageDraw.Draw(ring)
                d.ellipse((20, 20, 480, 480), outline=(255, 255, 255, 110), width=28)
                d.arc((20, 20, 480, 480), -90, -90 + 360 * (1 - cd / COUNTDOWN), fill=ALARM + (255,), width=28)
                paste_center(im, ring.resize((250, 250), Image.LANCZOS), cx, cy)
                num = self._txt(("n", n), lambda: text_img(str(n), font("Black", 100), fill=ALARM, shadow=False))
                pop = 1 + 0.35 * (1 - ease_out_cubic((cd % 1) / 0.3))
                paste_center(im, scaled(num, pop * bs), cx, cy + 2)
            else:
                paste_center(im, scaled(self.or_txt, bs), cx, cy + 2)
        # title + progress dots (below the Shorts top bar)
        hy = -160 * (1 - ease_out_cubic(t / 0.35))
        paste_center(im, self.title, W / 2, 165 + hy)
        qi, total = self.dots
        d = ImageDraw.Draw(im)
        for i in range(total):
            x = W / 2 + (i - (total - 1) / 2) * 46
            on = i < qi - 1 or (i == qi - 1 and rv > 0)
            r = 13 if i == qi - 1 else 10
            d.ellipse((x - r, 235 + hy - r, x + r, 235 + hy + r),
                      fill=(YELLOW if on else (255, 255, 255)) + (255 if on else 120,),
                      outline=(0, 0, 0, 160), width=3)
        return im


class ShortOutro(Scene):
    def __init__(self, tts, total):
        super().__init__()
        v = tts.say("How many did you match with the majority? Comment your score, "
                    "and subscribe to Quizzies for more!", speed=1.1)
        self.voices.append((0.25, v))
        self.dur = 0.25 + len(v) / SR + 0.9
        self.sounds += [(0.0, sfx_whoosh(0.5), 0.8), (0.2, sfx_fanfare(), 0.8), (0.9, sfx_pop(), 0.8)]
        self.bg = dark_bg()
        self.bokeh = Bokeh(12, n=18)
        self.l1 = outlined("YOUR SCORE?", 130, fill=YELLOW, stroke=10)
        self.l2 = text_img(f"How many of the {total} did you", font("Bold", 56), fill=(220, 224, 245))
        self.l3 = text_img("match with the majority?", font("Bold", 56), fill=(220, 224, 245))
        ct = text_img("COMMENT YOUR SCORE", font("Black", 60), fill=NAVY, shadow=False)
        self.cta = rounded_card(ct.width + 200, 130, 65, YELLOW + (255,))
        paste_center(self.cta, ct, 50 + ct.width / 2 + 10, 66)
        paste_center(self.cta, emoji("👇", 70), self.cta.width - 75, 65)
        pp = os.path.join(HERE, "profile_picture.png")
        logo = Image.open(pp).convert("RGBA").resize((340, 340), Image.LANCZOS) if os.path.exists(pp) else \
            circle(340, YELLOW + (255,))
        logo.putalpha(circle(340, (255, 255, 255, 255)).getchannel("A"))
        ring = circle(364, (255, 255, 255, 255))
        ring.alpha_composite(logo, (12, 12))
        self.logo = ring
        self.sub = text_img("SUBSCRIBE TO QUIZZIES", font("Black", 58))

    def render(self, t):
        im = self.bg.copy()
        self.bokeh.draw(im, t)
        paste_center(im, scaled(self.l1, ease_out_back((t - 0.1) / 0.4) * (1 + 0.02 * math.sin(t * 5))), W / 2, 470)
        a = clamp((t - 0.4) / 0.3)
        paste_center(im, self.l2, W / 2, 610, a)
        paste_center(im, self.l3, W / 2, 680, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 0.9) / 0.4)), W / 2, 850)
        paste_center(im, scaled(self.logo, ease_out_back((t - 1.4) / 0.45)), W / 2, 1140)
        paste_center(im, self.sub, W / 2, 1380, clamp((t - 1.7) / 0.3))
        return im


PREFIXES = ["", "Okay. ", "Next! ", "Hmm. "]


def build(seed, subject, n):
    rng = random.Random(seed)
    tts = mv.TTS()
    qs = rng.sample(SUBJECTS[subject]["questions"], n)
    scenes = [HookScene(tts, subject)]
    for i, q in enumerate(qs, 1):
        pct = int(clamp(q[4] + rng.randint(-3, 3), 5, 95))
        prefix = "Last one! " if i == n else ("" if i == 1 else rng.choice(PREFIXES))
        scenes.append(ShortQuestion(tts, q, pct, i, n, prefix))
    scenes.append(ShortOutro(tts, n))
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, qs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", default="Food", choices=list(SUBJECTS))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--questions", type=int, default=4)
    ap.add_argument("--out", default=None)
    ap.add_argument("--stills", default=None)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    out = args.out or os.path.join(HERE, f"short_{args.subject.lower().replace(' ', '_')}.mp4")

    scenes, starts, total, qs = build(args.seed, args.subject, args.questions)
    for sc, st in zip(scenes, starts):
        print(f"  {st:6.2f}s  {type(sc).__name__}")
    print(f"Duration {total:.1f}s")
    if total > MAX_LEN:
        sys.exit(f"Too long for a Short ({total:.1f}s). Use fewer --questions.")
    mv.G["scenes"], mv.G["starts"] = scenes, starts

    if args.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in args.stills.split(","):
            p = os.path.join(d, f"short_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return

    work = os.path.join(mv.CACHE_DIR, "render_short")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mv.mix_audio(scenes, starts, total))
    nframes = int(total * FPS)
    n = max(1, args.workers)
    bounds = [round(nframes * k / n) for k in range(n + 1)]
    jobs = [(k, bounds[k], bounds[k + 1], os.path.join(work, f"part{k}.mp4")) for k in range(n)]
    import multiprocessing as mp
    with mp.get_context("fork").Pool(n) as pool:
        parts = pool.map(mv.render_chunk, jobs)
    lst = os.path.join(work, "parts.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", out], check=True)
    print("Questions:")
    for q in qs:
        print(f"  {q[0]}  vs  {q[2]}")
    print(f"Done: {out}")


if __name__ == "__main__":
    main()
