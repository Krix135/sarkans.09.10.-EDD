#!/usr/bin/env python3
""""GUESS THE CAR BRAND BY THE LOGO" quiz Short (1080x1920) over Minecraft parkour gameplay.

1.8 s hook intro, then 10 logos + a bonus: the logo card pops in, A/B/C/D
answers with look-alike traps, a draining timer, then the right answer turns
green with confetti, the narrator says the brand, and a 'from <country>' fact
appears. Difficulty banners, score table, seamless loop, phonk + narrator.

Logos: put one picture per brand in car_logos/<key>.jpg (or .png), e.g.
car_logos/mercedes.jpg. They are trademarks of their owners.

    python3 make_car_quiz.py --bg-video gameplay.mp4
    python3 make_car_quiz.py --bg-video gameplay.mp4 --stills 1,4 --placeholders
    python3 make_car_quiz.py --bg-video gameplay.mp4 --cover
"""

import argparse
import glob
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

import brand  # noqa: E402
import make_brainrot_quiz as bq  # noqa: E402
import make_capitals_quiz as cq  # noqa: E402
import make_currency_quiz as cur  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, TIERS, join, rfont, rtext  # noqa: E402
from make_video import clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center, rounded_card, \
    scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
LOGO_DIR = os.path.join(HERE, "car_logos")
LOGO_Y, CARD = 610, 500
cur.OPT_Y0, cur.OPT_DY = 975, 108
TIMER_Y, FACT_Y = 1440, 1440
DRAIN0 = 0.9

CARS = [  # key, answer, 3 look-alike wrong answers, flag, country, fact, tier, spoken answer
    ("mercedes", "Mercedes-Benz", ("Infiniti", "Chrysler", "Smart"), "🇩🇪", "GERMANY",
     "Karl Benz built the first car in 1886", "EASY", "Mercedes-Benz!"),
    ("audi", "Audi", ("Opel", "Seat", "Skoda"), "🇩🇪", "GERMANY",
     "the 4 rings stand for 4 merged companies", "EASY", "Audi!"),
    ("bmw", "BMW", ("Mini", "Rolls-Royce", "Porsche"), "🇩🇪", "GERMANY",
     "it started out building plane engines", "EASY", "B M W!"),
    ("toyota", "Toyota", ("Lexus", "Honda", "Hyundai"), "🇯🇵", "JAPAN",
     "it started out making weaving looms", "MEDIUM", "Toyota!"),
    ("volkswagen", "Volkswagen", ("Skoda", "Vauxhall", "Seat"), "🇩🇪", "GERMANY",
     "its name means 'people's car'", "MEDIUM", "Volkswagen!"),
    ("ferrari", "Ferrari", ("Porsche", "Lamborghini", "Maserati"), "🇮🇹", "ITALY",
     "the horse came from a WW1 pilot's plane", "MEDIUM", "Ferrari!"),
    ("mitsubishi", "Mitsubishi", ("Nissan", "Isuzu", "Suzuki"), "🇯🇵", "JAPAN",
     "the name means 'three diamonds'", "HARD", "Mitsubishi!"),
    ("subaru", "Subaru", ("Mazda", "Infiniti", "Daihatsu"), "🇯🇵", "JAPAN",
     "its 6 stars are the Pleiades star cluster", "HARD", "Subaru!"),
    ("mazda", "Mazda", ("Kia", "Hyundai", "Acura"), "🇯🇵", "JAPAN",
     "named after Ahura Mazda, a god of wisdom", "HARD", "Mazda!"),
    ("alfaromeo", "Alfa Romeo", ("Maserati", "Lancia", "Fiat"), "🇮🇹", "ITALY",
     "its logo shows a serpent swallowing a man", "INSANE", "Alfa Romeo!"),
    ("koenigsegg", "Koenigsegg", ("Pagani", "Bugatti", "McLaren"), "🇸🇪", "SWEDEN",
     "its factory is in old fighter jet hangars", "BONUS", "Koenigsegg!"),
]
PROMPTS = ["Which car brand is this?", "Easy one.", "Next!", "Medium level!", "What's this one?", "Think fast!",
           "Hard level!", "Ooh, tricky.", "Last hard one!", "Insane level!", "Bonus! Only one percent know this."]


def logo_card(key, placeholders=False):
    hits = sorted(glob.glob(os.path.join(LOGO_DIR, key + ".*")))
    card = rounded_card(CARD, CARD, 56, (255, 255, 255, 255), outline=INK + (255,), width=6)
    if hits:
        src = Image.open(hits[0]).convert("RGBA")
        inner = CARD - 90
        s = min(inner / src.width, inner / src.height)
        src = src.resize((max(1, int(src.width * s)), max(1, int(src.height * s))), Image.LANCZOS)
        paste_center(card, src, CARD / 2, CARD / 2)
    elif placeholders:
        paste_center(card, rtext(f"LOGO: {key}", 44, fill=(120, 120, 130), stroke=0), CARD / 2, CARD / 2)
    else:
        raise FileNotFoundError(f"missing logo for {key} in {LOGO_DIR}")
    out = Image.new("RGBA", (CARD + 80, CARD + 80))
    out.alpha_composite(rounded_card(CARD, CARD, 56, (0, 0, 0, 160)), (46, 60))
    out = out.filter(ImageFilter.GaussianBlur(16))
    out.alpha_composite(card, (40, 40))
    return out


class Car(mv.Scene):
    def __init__(self, idx, q, ui, prev_tier, rng, placeholders):
        super().__init__()
        key, name, wrong, flag, country, fact, tier, said = q
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.reveal = 4.3 if self.bonus else 3.4
        self.dur = 5.6 if self.bonus else 4.7
        self.card = logo_card(key, placeholders)
        choices = list(wrong)
        self.right = rng.randrange(4)
        choices.insert(self.right, name)
        self.cards = [{s: cur.option_card("ABCD"[i], i, c, s) for s in ("idle", "right", "wrong")}
                      for i, c in enumerate(choices)]
        col, e = TIERS[tier]
        self.count = rtext("BONUS" if self.bonus else f"LOGO {idx}/10", 44, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, col + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        fsz = 38
        while rfont(fsz).getlength(fact) > 820 and fsz > 26:
            fsz -= 1
        top = join(rtext("FROM", 44, fill=(255, 255, 255), stroke=5), emoji(flag, 50),
                   rtext(country, 44, fill=CYAN, stroke=5), gap=12)
        body = rtext(fact, fsz, stroke=0)
        self.fact = rounded_card(max(top.width, body.width) + 60, top.height + body.height + 10, 40, INK + (230,))
        paste_center(self.fact, top, self.fact.width / 2, 14 + top.height / 2)
        paste_center(self.fact, body, self.fact.width / 2, top.height + body.height / 2 - 4)
        self.banner = None
        if tier != prev_tier and idx > 1:
            label = "BONUS: ONLY 1% KNOW THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 64 if self.bonus else 84, fill=col, stroke=8), emoji(e, 84))
            self.sounds += [(0.05, mq.sfx_boom(), 0.4), (0.05, mq.sfx_levelup(), 0.6)]
        self.sounds += [(0.05, mv.sfx_whoosh(0.35), 0.5), (0.15, mv.sfx_pop(), 0.9)]
        for k in range(4):
            self.sounds.append((0.3 + 0.07 * k, mv.sfx_pop(), 0.3))
        nt = 5 if self.bonus else 3
        for k in range(nt):
            self.sounds.append((self.reveal - 0.4 * (nt - k), mq.sfx_tock(high=k == nt - 1), 0.9))
        if self.bonus:
            self.sounds.append((self.reveal - 1.25, mv.sfx_riser(1.2), 0.7))
        self.sounds += [(self.reveal, mv.sfx_ding(), 1.0), (self.reveal, mq.sfx_boom(), 0.35),
                        (self.dur - 0.25, mv.sfx_whoosh(0.4), 0.5)]
        self.said = said
        cols = [CYAN, PINK, GOLD, (120, 255, 140), (255, 255, 255)]
        self.conf = [(rng.uniform(-1, 1) * 650, rng.uniform(-1250, -450), rng.randint(12, 24), rng.choice(cols),
                      rng.uniform(0, 3)) for _ in range(46)]

    def render(self, t):
        im = Image.new("RGBA", (W, H))
        rv = t - self.reveal
        out = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
        d = ImageDraw.Draw(im)
        paste_center(im, self.count, 70 + self.count.width / 2 - 24, 150)
        paste_center(im, self.tag, W - 70 - self.tag.width / 2, 150)
        paste_center(im, self.ui["title"], W / 2, 250)
        k = ease_out_back(t / 0.35, 1.6) * (1 - out)
        spin = (1 - ease_out_cubic(t / 0.45)) * math.pi  # flips in like a coin
        sx = abs(math.cos(spin))
        if rv > 0:
            k *= 1 + 0.08 * math.sin(math.pi * clamp(rv / 0.3))
        if k > 0.01:
            c = self.card.resize((max(2, int(self.card.width * k * sx)), max(2, int(self.card.height * k))),
                                 Image.BILINEAR)
            paste_center(im, c.rotate(2.5 * math.sin(t * 2), Image.BICUBIC, expand=True), W / 2,
                         LOGO_Y + 8 * math.sin(t * 2.4))
        for i, c in enumerate(self.cards):
            y = cur.OPT_Y0 + i * cur.OPT_DY
            ki = ease_out_back((t - 0.3 - 0.07 * i) / 0.3) * (1 - out)
            if ki <= 0.01:
                continue
            x = cur.OPT_X + (1 - ki) * (-W if i % 2 else W) * 0.3
            if rv <= 0:
                img, s_, a = c["idle"], 1.0, 1.0
            elif i == self.right:
                img, s_, a = c["right"], 1 + 0.1 * math.sin(math.pi * clamp(rv / 0.3)) + 0.03, 1.0
            else:
                img, s_, a = c["wrong"], 1 - 0.05 * clamp(rv / 0.2), 1 - 0.35 * clamp(rv / 0.3)
            paste_center(im, scaled(img, s_ * min(1.0, ki + 1e-4)), x, y, a)
        if rv < 0:
            frac = 1.0 if t < DRAIN0 else max(0.0, 1 - (t - DRAIN0) / (self.reveal - DRAIN0))
            x0, x1, bh = 160, 920, 26
            d.rounded_rectangle((x0 - 5, TIMER_Y - bh / 2 - 5, x1 + 5, TIMER_Y + bh / 2 + 5), 18, fill=INK + (235,))
            colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
            if frac > 0.01:
                d.rounded_rectangle((x0, TIMER_Y - bh / 2, x0 + (x1 - x0) * frac, TIMER_Y + bh / 2), 13,
                                    fill=colr + (255,))
            paste_center(im, self.ui["clock"], x1 + 62, TIMER_Y)
        else:
            for vx, vy, sz, cc, spin_ in self.conf:
                px, py = W / 2 + vx * rv, LOGO_Y + vy * rv + 2300 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin_ + rv * 9))
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            fk = ease_out_back((rv - 0.35) / 0.3) * (1 - out)
            if fk > 0.01:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y + self.fact.height / 2 - 40)
            f = 1 - clamp(rv / 0.18)
            if f > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(120 * f))))
        if self.banner is not None and 0.05 < t < 1.15:
            tb = t - 0.05
            s = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.18))
            a = clamp(tb / 0.08) * (1 - clamp((tb - 0.85) / 0.25))
            paste_center(im, scaled(self.banner, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 380, a)
        return im


class Intro(mv.Scene):
    """1.8 s hook: 'ONLY 1%' slam, rapid-fire logo preview, 'CAN YOU?', open loop, whip into logo 1."""

    def __init__(self, ui, cars):
        super().__init__()
        self.dur = 1.8
        self.l1 = rtext("ONLY 1%", 230, fill=PINK, stroke=16)
        self.l2 = rtext("KNOW ALL 10 LOGOS", 96, fill=CYAN, stroke=9)
        self.can = join(rtext("CAN YOU?", 120, stroke=11), emoji("👀", 120))
        self.tease = join(rtext("the last one is IMPOSSIBLE", 62, fill=GOLD, stroke=7), emoji("💀", 66))
        self.q = rtext("?", 330, fill=INK, stroke=0)
        self.blank = scaled(rounded_card(CARD, CARD, 56, (255, 255, 255, 255), outline=INK + (255,), width=6), 0.95)
        self.rays = mq.sunburst(1700, PINK, 18)
        self.previews = [scaled(c, 0.95) for c in cars]
        self.m0, self.m1 = 0.3, 1.05
        self.step = (self.m1 - self.m0) / len(self.previews)
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.22, mv.sfx_pop(), 1.0),
                        (self.m0, mv.sfx_riser(self.m1 - self.m0 + 0.05), 0.8), (self.m1, mq.sfx_boom(), 0.6),
                        (self.m1, mv.sfx_ding(), 0.5), (1.55, mv.sfx_whoosh(0.35), 0.9)]
        for k in range(len(self.previews)):
            self.sounds.append((self.m0 + k * self.step, mv.sfx_click(), 0.55))

    def render(self, t):
        im = Image.new("RGBA", (W, H))
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 5, 30, 120)))
        whip = ease_in_cubic((t - 1.55) / 0.25)
        paste_center(im, self.rays.rotate(t * 60, Image.BICUBIC), W / 2, 1050, 0.35 * (1 - whip))
        sh = 26 * (1 - clamp(t / 0.3)) + 18 * (1 - clamp((t - self.m1) / 0.25)) * (t >= self.m1)
        dx, dy = int(sh * math.sin(t * 95)), int(sh * math.cos(t * 80))
        layer = Image.new("RGBA", (W, H))
        paste_center(layer, scaled(self.l1, 1 + 0.14 * (1 - ease_out_cubic(t / 0.16))).rotate(-4, Image.BICUBIC,
                                                                                               expand=True), W / 2, 420)
        if t >= 0.22:
            s2 = 1 + 1.3 * (1 - ease_out_cubic((t - 0.22) / 0.16))
            paste_center(layer, scaled(self.l2, s2).rotate(3, Image.BICUBIC, expand=True), W / 2, 590)
        if self.m0 <= t < self.m1:
            k = min(len(self.previews) - 1, int((t - self.m0) / self.step))
            paste_center(layer, self.previews[k], W / 2, 1070)
        elif t >= 0.15:
            if t >= self.m1:
                b = self.blank.copy()
                paste_center(b, scaled(self.q, ease_out_back((t - self.m1) / 0.2)), b.width / 2, b.height / 2)
                paste_center(layer, b, W / 2, 1070)
                paste_center(layer, scaled(self.can, 1 + 0.35 * (1 - ease_out_cubic((t - self.m1) / 0.15))), W / 2,
                             215)
                paste_center(layer, scaled(self.tease, ease_out_back((t - self.m1 - 0.1) / 0.25)), W / 2, 1450)
            else:
                paste_center(layer, scaled(self.blank, ease_out_back((t - 0.15) / 0.2)), W / 2, 1070)
        if whip > 0:
            layer = scaled(layer, 1 + 0.8 * whip)
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * (1 - whip))))
            paste_center(im, layer, W / 2 + dx, H / 2 + dy)
        else:
            im.alpha_composite(layer, (max(0, dx), max(0, dy)), (max(0, -dx), max(0, -dy)))
        f = 1 - clamp(t / 0.2)
        if f > 0:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(55 * f))))
        return im


class Ending(mv.Scene):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.dur = 4.6
        logo = Image.open(brand.round_logo()).convert("RGBA").resize((120, 120), Image.LANCZOS)
        logo.putalpha(mv.circle(120, (255, 255, 255, 255)).getchannel("A"))
        self.brand = join(logo, rtext(brand.NAME, 60, stroke=6), gap=18)
        self.title = rtext("HOW MANY?", 124, fill=CYAN, stroke=11)
        tiers = [("0-3", "Learner driver", "🚲"), ("4-6", "Weekend driver", "🚗"), ("7-9", "Car expert", "🏎"),
                 ("10", "Petrolhead", "🏆")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            col = PINK if i == 3 else (255, 255, 255)
            row = rounded_card(860, 110, 55, INK + (220,), outline=(col if i == 3 else (90, 70, 130)) + (255,), width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 55), sc, font=rfont(60), fill=col, anchor="lm")
            dr.text((190, 55), label, font=rfont(56, "SemiBold"), fill=col, anchor="lm")
            row.alpha_composite(emoji(e, 62), (860 - 100, 24))
            self.rows.append(row)
            self.sounds.append((0.2 + 0.13 * i, mv.sfx_pop(), 0.7))
        self.bonus = join(rtext("+ bonus = LEGEND", 58, fill=GOLD, stroke=6), emoji("👑", 62))
        self.cta = join(rtext("comment your score", 58, stroke=6), emoji("👇", 62))
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.6), (0.05, mq.sfx_levelup(), 0.9), (1.05, mq.sfx_pling(), 0.7)]

    def render(self, t):
        im = Image.new("RGBA", (W, H))
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        a = 1 - out
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(90 * a))))
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


def build(placeholders=False, voice="af_heart"):
    ui = {"title": join(rtext("GUESS THE CAR BRAND", 74, stroke=8), emoji("🚗", 78)), "clock": emoji("⏰", 64)}
    rng = random.Random(21)
    cars = [Car(i, q, ui, None if i == 1 else CARS[i - 2][6], rng, placeholders) for i, q in enumerate(CARS, 1)]
    intro = Intro(ui, [c.card for c in cars])
    ui["first"] = intro
    scenes = [intro] + cars + [Ending(ui)]
    tint = bq.tint_overlay()
    for sc in scenes:
        sc.tint = tint
    if voice != "none":
        tts = mv.TTS(voice, "en-gb" if voice.startswith("b") else "en-us")
        intro.voices.append((0.05, tts.say("Only one percent know all ten car logos!", speed=1.15)))
        for i, c in enumerate(cars):
            v = tts.say(PROMPTS[i], speed=1.15)
            c.voices.append((0.2, v))
            if 0.2 + len(v) / mv.SR > c.reveal - 1.3:
                print(f"warning: prompt {i + 1} runs into the ticks", flush=True)
            c.voices.append((c.reveal + 0.05, tts.say(c.said, speed=1.1)))
        scenes[-1].voices.append((0.1, tts.say("How many did you get? Comment your score!", speed=1.12)))
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t


class Tinted:
    """Puts the purple vignette between the gameplay and each scene."""

    def __init__(self, sc):
        self.sc, self.dur = sc, sc.dur

    def render(self, t):
        im = self.sc.tint.copy()
        im.alpha_composite(self.sc.render(t))
        return im


def mix(scenes, starts, total, kind="phonk"):
    import make_movie_quiz as mmq
    return mmq.mix_audio(scenes, starts, total, kind)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bg-video", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "short_car_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--placeholders", action="store_true", help="grey boxes instead of logos (layout test, stills)")
    ap.add_argument("--music", default="phonk", choices=["phonk", "chiptune", "none"])
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    if a.placeholders and not a.stills:
        sys.exit("--placeholders is only for --stills; the real video needs the real logos")
    try:
        scenes, starts, total = build(a.placeholders, a.voice if not a.stills else "none")
    except FileNotFoundError as e:
        sys.exit(f"{e}\nAdd the logo pictures to {LOGO_DIR}.")
    print(f"Duration {total:.1f}s")
    work = os.path.join(mv.CACHE_DIR, "render_car")
    os.makedirs(work, exist_ok=True)
    full = cq.prepare_bg_video(a.bg_video, total, starts[1:], work, crossfade=0.6)
    tinted = [Tinted(sc) for sc in scenes]
    mv.G["scenes"], mv.G["starts"] = tinted, starts
    if a.cover:
        make_cover(full, scenes, os.path.join(HERE, "car_quiz_cover.jpg"))
        return
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        import make_odd_one_out as oo
        for s in a.stills.split(","):
            p = os.path.join(d, f"car_{float(s):06.2f}.png")
            oo.compose(tinted, starts, float(s), full).save(p)
            print(p)
        return
    for f in os.listdir(work):
        if f.startswith("part") or f.endswith(".wav") or f.endswith(".txt") or f == "joined.mp4":
            os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mix(scenes, starts, total, a.music))
    nframes = int(total * FPS)
    n = max(1, a.workers)
    bounds = [round(nframes * k / n) for k in range(n + 1)]
    jobs = [(k, bounds[k], bounds[k + 1], os.path.join(work, f"part{k}.mp4")) for k in range(n)]
    cq.BG["full"] = full
    with mp.get_context("fork").Pool(n) as pool:
        parts = pool.map(cq.render_chunk_video, jobs)
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


def make_cover(full, scenes, path):
    base = cq.bg_frame(full, 6.0).convert("RGBA")
    base.alpha_composite(bq.tint_overlay())
    paste_center(base, mq.sunburst(1700, PINK, 18), W / 2, 1060, 0.5)
    paste_center(base, rtext("GUESS THE", 130, stroke=12), W / 2, 240)
    paste_center(base, join(rtext("CAR LOGO", 146, fill=CYAN, stroke=13), emoji("🚗", 124)), W / 2, 410)
    paste_center(base, join(rtext("only 1% get 10/10", 74, fill=PINK, stroke=8), emoji("😳", 78)), W / 2, 580)
    cars = [sc for sc in scenes if isinstance(sc, Car)]
    for c, (x, y, s, r) in zip((cars[6], cars[9], cars[7]), ((280, 930, 0.62, -8), (800, 930, 0.62, 8),
                                                             (540, 1230, 0.7, 0))):
        paste_center(base, scaled(c.card, s).rotate(r, Image.BICUBIC, expand=True), x, y)
    base.convert("RGB").save(path, quality=92)
    print(path)


if __name__ == "__main__":
    main()
