#!/usr/bin/env python3
""""CHRISTMAS AROUND THE WORLD" Short (1080x1920): guess the country from its Christmas tradition.

No hook intro: round 1 opens with the title slamming in while the globe flies to the first question.
Each round shows a tradition ("Where do people eat KFC on Christmas?"); four lettered dots drop onto four
countries on a colour-lit map, with names and flags in a 2x2 answer grid. A 3-2-1 runs on the beat; on
the drop the right country fills with its flag, a green pin slams down with a light beam and shockwaves,
sleigh bells ring, the camera zooms in, the right card flies to the middle with a sunburst, the wrong ones
fall away, and a fun fact pops up. Snow falls the whole time and a string of Christmas lights twinkles on
the beat. EASY -> IMPOSSIBLE plus a bonus, one like call-out after round 3, Christmas score screen that
loops back to the start.

Music: our own arrangement of "Jingle Bells" (public domain), synthesised in christmas_music.py.
Borders: Natural Earth (public domain). Flags: public domain.

    python3 make_christmas_quiz.py
    python3 make_christmas_quiz.py --stills 0,5,9
    python3 make_christmas_quiz.py --cover
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

import christmas_music as xm  # noqa: E402
import globe as G  # noqa: E402
import make_bigger_country_quiz as bq  # noqa: E402
import make_capital_quiz as cap  # noqa: E402
import make_club_quiz as cq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_missing_country_quiz as mcq  # noqa: E402
import make_pin_country_quiz as pq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_in_out, ease_out_back, ease_out_cubic, emoji, paste_center, \
    rounded_card, scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
GC = (540, 1010)
TITLE_Y = 150
CARD_Y = 440
NUM_Y = 660
GRID_X = (276, 804)
GRID_Y = (1480, 1606)
FACT_Y = 1606
CTA_Y = 1655
FLY_BEATS = 3
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
GREEN, RED = pq.GREEN, pq.RED
XRED = (232, 46, 62)
XGREEN = (40, 190, 100)
COLS = pq.PIN_COLS

COUNTRIES = {  # map code: name, flag, pin point (lon, lat) inside the country
    "JPN": ("JAPAN", "JP", (138.3, 36.2)), "KOR": ("SOUTH KOREA", "KR", (127.9, 36.4)),
    "CHN": ("CHINA", "CN", (112.0, 34.0)), "PHL": ("PHILIPPINES", "PH", (121.0, 16.0)),
    "USA": ("USA", "US", (-99.0, 37.5)), "CUB": ("CUBA", "CU", (-79.0, 21.8)),
    "MEX": ("MEXICO", "MX", (-102.5, 23.9)), "COL": ("COLOMBIA", "CO", (-73.5, 4.0)),
    "ITA": ("ITALY", "IT", (12.5, 42.8)), "ESP": ("SPAIN", "ES", (-3.7, 40.2)),
    "FRA": ("FRANCE", "FR", (2.5, 46.8)), "GRC": ("GREECE", "GR", (22.0, 39.3)),
    "NOR": ("NORWAY", "NO", (9.0, 61.0)), "GBR": ("UK", "GB", (-1.5, 52.5)),
    "IRL": ("IRELAND", "IE", (-8.0, 53.2)), "ISL": ("ICELAND", "IS", (-18.5, 64.9)),
    "PRT": ("PORTUGAL", "PT", (-8.0, 39.6)), "IDN": ("INDONESIA", "ID", (113.9, -0.5)),
    "VNM": ("VIETNAM", "VN", (105.8, 21.0)), "THA": ("THAILAND", "TH", (101.0, 15.5)),
    "SWE": ("SWEDEN", "SE", (15.5, 62.5)), "FIN": ("FINLAND", "FI", (26.0, 63.0)),
    "DNK": ("DENMARK", "DK", (9.3, 56.0)), "POL": ("POLAND", "PL", (19.4, 52.1)),
    "ROU": ("ROMANIA", "RO", (24.9, 45.9)), "UKR": ("UKRAINE", "UA", (31.2, 49.0)),
    "BLR": ("BELARUS", "BY", (28.0, 53.5)), "BRA": ("BRAZIL", "BR", (-51.0, -10.0)),
    "PER": ("PERU", "PE", (-75.0, -9.5)), "VEN": ("VENEZUELA", "VE", (-66.0, 7.0)),
    "CZE": ("CZECHIA", "CZ", (15.5, 49.8)), "DEU": ("GERMANY", "DE", (10.4, 51.1)),
    "AUT": ("AUSTRIA", "AT", (14.5, 47.5)),
}
ROUNDS = [  # lead, clue, clue emoji, options A-D (grid order), answer, fact, fact emoji, tier, prompt, answer, sticker
    ("WHERE DO PEOPLE", "EAT KFC ON CHRISTMAS?", "🍗", ("KOR", "JPN", "CHN", "PHL"), 1,
     "it all started with a 1974 ad campaign", "📺", "EASY",
     "Christmas around the world! Where do people eat KFC on Christmas?", "Japan!", "🎅"),
    ("WHERE DO KIDS", "SMASH PIÑATAS AT CHRISTMAS?", "🪅", ("USA", "CUB", "MEX", "COL"), 2,
     "Las Posadas lasts 9 nights, from December 16 to 24", "🕯", "EASY",
     "Where do kids smash pinyatas at Christmas?", "Mexico!", "🔥"),
    ("WHERE DOES A", "WITCH BRING THE PRESENTS?", "🧹", ("ITA", "ESP", "FRA", "GRC"), 0,
     "La Befana flies in on the night of January 5", "🌙", "EASY",
     "Where does a witch bring the presents?", "Italy!", "🤔"),
    ("WHERE DO", "13 YULE LADS VISIT KIDS?", "🎅", ("NOR", "GBR", "IRL", "ISL"), 3,
     "they come one by one on the 13 nights before Christmas", "🌙", "MEDIUM",
     "Where do thirteen Yule Lads visit kids?", "Iceland!", "😳"),
    ("WHERE DO KIDS HIT A LOG", "UNTIL IT POOPS PRESENTS?", "🪵", ("PRT", "ESP", "FRA", "ITA"), 1,
     "it's called the Caga Tió, and it's from Catalonia", "💩", "MEDIUM",
     "Where do kids hit a log until it poops presents?", "Spain!", "🤯"),
    ("WHERE DOES", "CHRISTMAS START IN SEPTEMBER?", "🗓", ("IDN", "VNM", "THA", "PHL"), 3,
     "it's the longest Christmas season in the world", "🎄", "MEDIUM",
     "Where does Christmas start in September?", "The Philippines!", "🔥"),
    ("WHERE DO PEOPLE HIDE", "THEIR BROOMS ON CHRISTMAS EVE?", "🧙", ("SWE", "NOR", "FIN", "DNK"), 1,
     "so witches can't steal them and fly around", "🧹", "HARD",
     "Where do people hide their brooms on Christmas Eve?", "Norway!", "😱"),
    ("WHERE DO PEOPLE PUT", "SPIDER WEBS ON THE TREE?", "🕸", ("POL", "ROU", "UKR", "BLR"), 2,
     "it comes from a legend about a kind little spider", "🕷", "HARD",
     "Where do people put spider webs on the Christmas tree?", "Ukraine!", "💀"),
    ("WHERE DO PEOPLE", "ROLLER-SKATE TO CHURCH?", "🛼", ("COL", "BRA", "PER", "VEN"), 3,
     "streets in Caracas close to cars for it", "🚗", "INSANE",
     "Where do people roller-skate to church on Christmas?", "Venezuela!", "🧠"),
    ("WHERE DO WOMEN THROW", "A SHOE AT CHRISTMAS?", "👠", ("CZE", "POL", "DEU", "AUT"), 0,
     "if it lands toe to the door, she'll marry soon", "💍", "IMPOSSIBLE",
     "Where do women throw a shoe over their shoulder at Christmas?", "Czechia!", "☠"),
    ("WHERE DOES EVERYONE", "WATCH DONALD DUCK AT 3 PM?", "🦆", ("NOR", "FIN", "SWE", "DNK"), 2,
     "it's been on TV every Christmas Eve since 1960", "📺", "BONUS",
     "Bonus! Where does everyone watch Donald Duck on Christmas Eve?", "Sweden!", "👑"),
]
STICKERS = ["🎅", "🦌", "⛄", "🎁", "🔔", "❄", "🌟", "🍪", "🤶", "🎄"]


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


def point_view(world, codes):
    """Centre on the four countries' pins and zoom in until no two dots touch, keeping all four on screen."""
    pts = np.array([G.unit(*COUNTRIES[k][2]) for k in codes])
    c = pts.mean(0)
    c /= np.linalg.norm(c)
    for _ in range(2):
        east, up, _ = G.frame_axes(c)
        ex, uy = pts @ east, pts @ up
        c = c + east * (ex.max() + ex.min()) / 2 + up * (uy.max() + uy.min()) / 2
        c /= np.linalg.norm(c)
    east, up, _ = G.frame_axes(c)
    r_fit = min(390 / max(np.abs(pts @ east).max(), 1e-3), 280 / max(np.abs(pts @ up).max(), 1e-3))
    sep = min(math.acos(min(1.0, float(pts[i] @ pts[j]))) for i in range(4) for j in range(i + 1, 4))
    return c, float(np.clip(max(r_fit * 0.8, min(r_fit, 70 / max(sep, 1e-4))), 560, 9000))


def flag_img(code, box=(66, 44)):
    fl = Image.open(os.path.join(FLAG_DIR, COUNTRIES[code][1] + ".png")).convert("RGBA")
    fl = fl.resize(box, Image.LANCZOS)
    fb = Image.new("RGBA", (box[0] + 6, box[1] + 6), (255, 255, 255, 255))
    fb.paste(fl, (3, 3))
    return fb


def answer_card(letter, code, col, state=None):
    w, h = 512, 112
    fill = {None: INK + (238,), "ok": (24, 150, 80, 255), "no": (150, 30, 50, 255)}[state]
    edge = {None: col, "ok": (255, 255, 255), "no": (255, 120, 130)}[state]
    card = rounded_card(w, h, h // 2, fill, outline=edge + (255,), width=6)
    badge = mv.circle(78, (col if state is None else (255, 255, 255)) + (255,))
    ImageDraw.Draw(badge).text((39, 41), letter, font=rfont(48), fill=(255, 255, 255) if state is None else INK,
                               anchor="mm")
    card.alpha_composite(badge, (17, (h - 78) // 2))
    fb = flag_img(code)
    card.alpha_composite(fb, (106, (h - fb.height) // 2))
    name = COUNTRIES[code][0]
    size = 48
    room = w - 196 - (64 if state else 22)
    while rfont(size).getlength(name) > room and size > 28:
        size -= 2
    t = rtext(name, size, stroke=5)
    card.alpha_composite(t, (188, (h - t.height) // 2))
    if state == "ok":
        paste_center(card, emoji("✅", 54), w - 46, h / 2)
    elif state == "no":
        paste_center(card, emoji("❌", 50), w - 46, h / 2)
    return card


def question_card(lead, clue, em):
    a = rtext(lead, 46, fill=(220, 220, 240), stroke=5)
    lines, size = [clue], 80
    while rfont(size).getlength(clue) > 790 and size > 58:
        size -= 2
    if rfont(size).getlength(clue) > 790:                    # two balanced lines
        words = clue.split()
        best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
        lines = [" ".join(words[:best]), " ".join(words[best:])]
        size = 64
        while max(rfont(size).getlength(x) for x in lines) > 720 and size > 46:
            size -= 2
    imgs = [rtext(x, size, fill=GOLD, stroke=8) for x in lines]
    e = emoji(em, 118)
    text_w = max([a.width] + [i.width for i in imgs])
    text_h = a.height + sum(i.height for i in imgs) - 6 * len(imgs)
    w = min(1040, text_w + e.width + 100)
    h = text_h + 50
    card = rounded_card(w, h, 50, (14, 6, 40, 232), outline=XRED + (255,), width=6)
    x0 = (w - (text_w + e.width + 30)) // 2
    card.alpha_composite(a, (x0, 22))
    y = 22 + a.height - 6
    for i in imgs:
        card.alpha_composite(i, (x0, y))
        y += i.height - 6
    paste_center(card, e, x0 + text_w + 30 + e.width / 2, h / 2)
    return card


class Snow:
    def __init__(self, n=140, seed=7):
        r = random.Random(seed)
        self.flakes = [(r.uniform(0, W), r.uniform(0, H), r.uniform(50, 150), r.uniform(2.0, 6.5), r.uniform(0, 6),
                        r.uniform(0.55, 1.0)) for _ in range(n)]

    def draw(self, im, T, a=1.0):
        d = ImageDraw.Draw(im, "RGBA")
        for x0, y0, sp, r, ph, al in self.flakes:
            y = (y0 + sp * T) % (H + 30) - 15
            x = x0 + 22 * math.sin(T * 0.9 + ph) + 8 * math.sin(T * 2.3 + ph * 2)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, int(220 * al * a)))


def light_string():
    """Two frames of a string of Christmas lights across the top (bulbs swap on the beat)."""
    cols = [(255, 60, 70), (60, 220, 110), (255, 205, 60), (80, 170, 255)]
    frames = []
    for phase in (0, 1):
        im = Image.new("RGBA", (W, 130))
        d = ImageDraw.Draw(im)
        pts = [(x, 30 + 34 * (1 - math.cos(2 * math.pi * x / 270)) / 2) for x in range(-10, W + 11, 6)]
        d.line(pts, fill=(30, 60, 30, 255), width=5)
        glow = Image.new("RGBA", (W, 130))
        gd = ImageDraw.Draw(glow)
        for i, x in enumerate(range(15, W, 67)):
            y = 30 + 34 * (1 - math.cos(2 * math.pi * x / 270)) / 2
            col = cols[i % 4]
            lit = (i + phase) % 2 == 0
            if lit:
                gd.ellipse((x - 26, y - 6, x + 26, y + 46), fill=col + (150,))
            d.rectangle((x - 6, y - 2, x + 6, y + 8), fill=(90, 90, 90, 255))
            c2 = col if lit else tuple(int(v * 0.45) for v in col)
            d.ellipse((x - 11, y + 4, x + 11, y + 34), fill=c2 + (255,), outline=INK + (255,), width=2)
            if lit:
                d.ellipse((x - 5, y + 9, x + 1, y + 17), fill=(255, 255, 255, 200))
        glow = glow.filter(ImageFilter.GaussianBlur(10))
        glow.alpha_composite(im)
        frames.append(glow)
    return frames


def festive_title(size=44):
    return join(emoji("🎄", size + 6), rtext("CHRISTMAS AROUND THE WORLD", size, fill=GOLD, stroke=5),
                emoji("🎅", size + 6), gap=10)


def decorate(im, ui, T, title=True, title_a=1.0):
    """Lights across the top, the festive title strip."""
    lights = ui["lights"][int(T / (0.5 * B)) % 2]
    im.alpha_composite(lights, (0, 0))
    if title and title_a > 0.01:
        paste_center(im, ui["title"], W / 2, TITLE_Y, title_a)


# ----------------------------------------------------------------------------
# rounds
# ----------------------------------------------------------------------------
class Round(mv.Scene):
    def __init__(self, idx, r, prev_view, prev_tier, ui, tts):
        super().__init__()
        lead, clue, cem, opts, ans, fact, femoji, tier, prompt, said, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.first = idx == 1
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = FLY_BEATS
        self.fly = f * B
        v_q = tts.say(prompt, speed=1.16) if tts else None
        q_len = len(v_q) / SR if v_q is not None else (3.2 if self.first else 2.2)
        c0 = max(f + 1, math.ceil((0.12 + q_len + 0.15) / B))
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.reveal = (c0 + n) * B
        self.dur = self.reveal + ((6 if self.bonus else 5) + (5 if self.cta else 0)) * B
        self.cta_at = 2.2 * B
        world = ui["globe"].world
        self.opts, self.ans = opts, ans
        code = opts[ans]
        self.target = world.codes.index(code)
        cc, self.near, _ = world.country(code)
        c, R = point_view(world, opts)
        self.view = (c, R)
        self.cam = mm.Camera(prev_view, self.view, self.fly, self.reveal)
        Rc = G.zoom_for(world, cc, self.near, W, H, 0.34, 0.2)
        self.end_view = (G.slerp(c, cc, 0.85), float(np.clip(Rc, R * 1.15, R * 4)))
        self.points = [(L, k, G.unit(*COUNTRIES[k][2])) for L, k in zip("ABCD", opts)]
        self.dots = {L: cap.dot_sprite(L, COLS[L]) for L in "ABCD"}
        self.grey = {L: cap.dot_sprite(L, (110, 110, 130)) for L in "ABCD"}
        self.pin = pq.pin_sprite("A", GREEN, "✅")
        self.shadow = pq.pin_shadow()
        self.cards = {L: answer_card(L, k, COLS[L]) for L, k in zip("ABCD", opts)}
        La = "ABCD"[ans]
        self.ok_card = answer_card(La, code, COLS[La], "ok")
        self.no_cards = {L: answer_card(L, k, COLS[L], "no") for L, k in zip("ABCD", opts)}
        self.name_tag = cap.capital_tag(COUNTRIES[code][0])
        self.flag = Image.open(os.path.join(FLAG_DIR, COUNTRIES[code][1] + ".png")).convert("RGBA")
        self.card = question_card(lead, clue, cem)
        self.card_y = max(CARD_Y, 322 + self.card.height / 2)   # tall cards sit lower, clear of the tier tag
        self.num_y = max(NUM_Y, self.card_y + self.card.height / 2 + 95)   # numbers and banners below the card
        fs = 42
        while rfont(fs).getlength(fact) > 780 and fs > 26:
            fs -= 1
        body = join(emoji(femoji, 52), rtext(fact, fs, stroke=0), gap=14)
        self.fact = rounded_card(body.width + 56, body.height + 22, (body.height + 22) // 2, INK + (232,))
        paste_center(self.fact, body, self.fact.width / 2, self.fact.height / 2)
        self.sticker = emoji(stick, 140)
        self.col, e = TIERS[tier]
        self.count = rtext("BONUS" if self.bonus else f"{idx}/10", 46, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, self.col + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.level_up = tier != prev_tier and idx > 1
        self.banner = None
        if self.level_up:
            label = "BONUS: ONLY 1% KNOW THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 62 if self.bonus else 92, fill=self.col, stroke=9), emoji(e, 90))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.7), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        if self.first:                                       # no intro: the title slams in over the first fly-in
            self.t1 = fit(rtext("CHRISTMAS", 160, fill=XRED, stroke=15), 980)
            self.t2 = fit(join(rtext("AROUND THE WORLD", 104, fill=(255, 255, 255), stroke=11), emoji("🌍", 96),
                               gap=12), 980)
            self.t3 = join(rtext("GUESS THE COUNTRY", 70, fill=GOLD, stroke=8), emoji("🎄", 70), gap=10)
            self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, xm.sfx_jingle(), 0.8), (0.5 * B, mq.sfx_boom(), 0.6),
                            (1.0 * B, mv.sfx_pop(), 0.8), (1.0 * B, mq.sfx_pling(), 0.5)]
        n = len(self.count_beats)
        self.nums = {k: rtext(str(k), 170, fill=XRED if k == 1 else (255, 255, 255), stroke=14) for k in range(1, n + 1)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self.drop_at = [self.fly - 0.35 + i * 0.1 for i in range(4)]
        self.card_at = [self.fly * 0.5 + i * 0.08 for i in range(4)]
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.7)]
        for at in self.drop_at:
            self.sounds += [(at + 0.12, mv.sfx_pop(), 0.7), (at + 0.12, xm.sleigh(int(at * 100), 0.6), 0.5)]
        for at in self.card_at:
            self.sounds.append((at + 0.1, mv.sfx_click(), 0.45))
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 0.9), (b * B, xm.sfx_chime(79 + 2 * j), 0.35)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.8))
        if self.danger:
            self.sounds.append((self.count_beats[-1] * B, mq.sfx_boom(), 0.6))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.5))
        rv0 = self.reveal
        self.sounds += [(rv0, mq.sfx_boom(), 0.9), (rv0, mv.sfx_ding(), 1.0), (rv0 + 0.02, xm.sfx_jingle(), 0.9),
                        (rv0 + 0.05, xm.sfx_chime(88), 0.6), (rv0 + 0.25, mv.sfx_whoosh(0.35), 0.5),
                        (rv0 + 0.3, mq.sfx_boom(), 0.5), (rv0 + 0.45, mv.sfx_pop(), 0.7),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        if tts:
            self.voices.append((0.12, v_q))
            self.voices.append((self.reveal + 0.08, tts.say(f"{La}! {said}", speed=1.12)))
            if self.cta:
                self.voices.append((self.reveal + self.cta_at, tts.say(CTA_LINE, speed=1.12)))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=XRED + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = self.reveal + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, xm.sfx_chime(84), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        rr = random.Random(idx * 31)
        palette = [XRED, XGREEN, GOLD, (255, 255, 255)]
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1350, -450), rr.randint(12, 26), rr.choice(palette),
                      rr.uniform(0, 3)) for _ in range(70)]

    def camera(self, t):
        rv = t - self.reveal
        if rv <= 0:
            return self.cam.at(t)
        c0, R0, _ = self.cam.at(self.reveal - 1e-3)
        k = ease_in_out(clamp((rv - 0.25) / 0.7))
        c1, R1 = self.end_view
        return G.slerp(c0, c1, k), math.exp(math.log(R0) + (math.log(R1) - math.log(R0)) * k), 0.0

    def render(self, t, header=True):
        T = self.t0 + t
        rv = t - self.reveal
        ui = self.ui
        c, R, blur = self.camera(t)
        if t > self.fly and rv < 0:
            R *= 1 + 0.03 * beat_pulse(T)
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.25:
                    R *= 1 + (0.09 if self.danger else 0.06) * (1 - ease_out_cubic(tb / 0.25))
        hl = clamp((rv - 0.3) / 0.2) if rv > 0 else 0.0
        fa = 0.95 * clamp((rv - 0.4) / 0.3) if rv > 0 else 0.0
        lift = 16 * ease_out_back(clamp((rv - 0.5) / 0.3)) if rv > 0 else 0.0
        im = ui["globe"].render(c, R, GC, self.near if hl > 0 else None, hl, self.flag, fa, lift=lift)
        if hl > 0:
            ui["cmap"].draw(im, c, R, GC, self.target, 0.8 * (1 - 0.5 * clamp((rv - 0.3) / 0.4)), 0.0, lift=lift)
        else:
            ui["cmap"].draw(im, c, R, GC, None, 0.8, 0.0)
        im = mm.zoom_blur(im, blur)
        im = rgb_split(im, 22 * blur)
        im.alpha_composite(ui["shade"])
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv > 0:
            im.alpha_composite(cq.speed_lines(1 - clamp(rv / 0.45), self.idx, GC))
        # country dots
        pin_xy = None
        for i, (L, k, p) in enumerate(self.points):
            td = t - self.drop_at[i]
            if td <= 0:
                continue
            x, y, vis = cap.project(p, c, R, GC)
            if not vis:
                continue
            right = i == self.ans
            if right:
                pin_xy = (x, y)
            tl = td - 0.12
            if 0 < tl < 0.45:
                cap.ring(im, x, y, 14 + 90 * ease_out_cubic(tl / 0.45), COLS[L], 255 * (1 - tl / 0.45), 6)
            if rv <= 0:
                for b in self.count_beats:
                    tb = t - b * B
                    if 0 <= tb < 0.4:
                        cap.ring(im, x, y, 26 + 70 * ease_out_cubic(tb / 0.4), (255, 255, 255), 200 * (1 - tb / 0.4), 5)
                s = ease_out_back(clamp(td / 0.25), 2.4) * (1 + 0.1 * beat_pulse(T + i * 0.1))
                if s > 0.01:
                    paste_center(im, scaled(self.dots[L], s), x, y)
            elif not right:
                a = 1 - 0.6 * clamp(rv / 0.3)
                paste_center(im, scaled(self.grey[L], 1 - 0.3 * clamp(rv / 0.3)),
                             x + 10 * math.sin(rv * 60) * (1 - clamp(rv / 0.3)), y, a)
        if rv > 0 and pin_xy is not None:                    # beam, shockwaves, and a pin slams onto the country
            x, y = pin_xy
            y -= lift
            ba = clamp(rv / 0.05) * (1 - clamp(rv / 0.9))
            if ba > 0.01:
                paste_center(im, ui["beam"], x, y - 650, ba)
            for j in range(3):
                tl = rv - 0.09 * j
                if 0 < tl < 0.5:
                    cap.ring(im, x, y, 20 + 190 * ease_out_cubic(tl / 0.5), GREEN, 255 * (1 - tl / 0.5), 9, 0.42)
            kp = clamp(rv / 0.22)
            fall = (1 - ease_out_back(kp, 2.0)) * 700
            paste_center(im, self.shadow, x, y, kp)
            sp = scaled(self.pin, 1.1 + 0.04 * beat_pulse(T))
            im.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height - fall)))
            kt = ease_out_back(clamp((rv - 0.4) / 0.25), 2.0)
            if kt > 0.01:
                ty = max(self.card_y + self.card.height / 2 + 50, y - sp.height - 60)
                tx = min(max(x, self.name_tag.width / 2 + 20), W - self.name_tag.width / 2 - 20)
                paste_center(im, scaled(self.name_tag, kt), tx, ty)
        ui["snow"].draw(im, T)
        d = ImageDraw.Draw(im)
        title_a = 1.0 if not self.first else clamp((t - self.fly + 0.1) / 0.25)
        decorate(im, ui, T, header, title_a)
        if header:
            paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
            x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
            frac = 1.0 if t < self.fly else max(0.0, 1 - (t - self.fly) / (self.reveal - self.fly))
            d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
            colr = (255, 255, 255) if frac > 0.6 else XGREEN if frac > 0.3 else XRED
            if frac > 0.01:
                d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 11, fill=colr + (255,))
            paste_center(im, self.tag, x0 + self.tag.width / 2, 285)
            nk = self.idx if rv > 0 else self.idx - 1
            if nk > 0:
                sc = 1 + 0.5 * (1 - ease_out_cubic(rv / 0.25)) if 0 < rv < 0.25 else 1.0
                stk = self.streak[nk]
                paste_center(im, scaled(stk, sc), x1 - stk.width / 2 + 10, 288)
        kc = ease_out_back(clamp((t - (self.fly - 0.3 if self.first else 0.05)) / 0.3), 1.6)
        if kc > 0.01:
            paste_center(im, scaled(self.card, kc * (1 + 0.015 * beat_pulse(T))), W / 2, self.card_y)
        # the answer grid
        cta_on = self.cta and rv > self.cta_at
        for i, L in enumerate("ABCD"):
            gx, gy = GRID_X[i % 2], GRID_Y[i // 2]
            kin = ease_out_back(clamp((t - self.card_at[i]) / 0.3), 1.8)
            if kin <= 0.01:
                continue
            if rv <= 0:
                s = kin
                for j, b in enumerate(self.count_beats):
                    tb = t - b * B
                    if 0 <= tb < 0.3 and (i + j) % 2 == 0:
                        s *= 1 + 0.07 * (1 - ease_out_cubic(tb / 0.3))
                paste_center(im, scaled(self.cards[L], s), gx, gy)
            elif i == self.ans:
                k = ease_out_cubic(clamp(rv / 0.3))
                px, py = gx + (W / 2 - gx) * k, gy + (GRID_Y[0] - gy) * k
                s = 1 + 0.18 * ease_out_back(clamp(rv / 0.3), 2.0) + 0.02 * beat_pulse(T)
                bs = ui["burst"].rotate(rv * 50, Image.BICUBIC)
                paste_center(im, scaled(bs, 0.9), px, py, 0.85 * clamp(rv / 0.15))
                paste_center(im, scaled(self.ok_card, s), px, py)
            else:
                no = self.no_cards[L]
                if rv < 0.25:
                    paste_center(im, no, gx + 12 * math.sin(rv * 70), gy)
                else:
                    tf = rv - 0.25
                    a = 1 - clamp((tf - 0.05) / 0.5)
                    if a > 0.01:
                        sp = no.rotate((1 if i % 2 else -1) * 120 * tf, Image.BICUBIC, expand=True)
                        paste_center(im, sp, gx + (1 if i % 2 else -1) * 150 * tf, gy + 2400 * tf * tf, a)
        if self.first and t < self.fly + 0.15:              # the title, since there is no intro
            out = clamp((t - (self.fly - 0.2)) / 0.35)
            a = 1 - out
            b_ = int(t / (0.5 * B))
            kk = (t % (0.5 * B)) / (0.5 * B)
            slam = 1 + 0.35 * (1 - ease_out_cubic(kk / 0.4))
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, int(110 * a))))
            for j, (img, y, rot) in enumerate([(self.t1, 700, -3), (self.t2, 860, 2), (self.t3, 1000, -2)]):
                if b_ >= j:
                    sc = (slam if b_ == j else 1.0) * (1 - 0.3 * out) * (1 + 0.03 * beat_pulse(T))
                    paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2,
                                 y - (y - TITLE_Y) * ease_in_cubic(out) * (1 if j == 0 else 0), a)
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, self.num_y, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, self.num_y, a * 0.9)
        if rv > 0:
            if pin_xy is not None:
                cx, cy = pin_xy
                for vx, vy, sz, cc, spin in self.conf:
                    px, py = cx + vx * rv, cy + vy * rv + 2400 * rv * rv
                    if py < H:
                        w2 = sz * abs(math.cos(spin + rv * 9))
                        d = ImageDraw.Draw(im)
                        d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                    outline=INK + (255,))
            sk = ease_out_back((rv - 0.5) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             930, 1300)
            fk = ease_out_back((rv - 0.7) / 0.3)
            if fk > 0.01 and not cta_on:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(190 * fl))))
            im = shake(im, 28 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 16 * (1 - rv / 0.18))
            if 0.22 < rv < 0.4:
                im = shake(im, 14 * (1 - (rv - 0.22) / 0.18), t)
        else:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 14 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 10 * (1 - tb / 0.15))
            tb = t - self.count_beats[-1] * B
            if self.danger and 0 <= tb < 0.2:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 30, 60, int(90 * (1 - tb / 0.2)))))
            if self.first and t < 0.3:
                im = shake(im, 26 * (1 - t / 0.3), t)
                im = rgb_split(im, 12 * (1 - t / 0.3))
        if cta_on:
            ct = rv - self.cta_at
            k = ease_out_back(ct / 0.3, 2.0) * (1 - ease_in_cubic(clamp((t - (self.dur - 0.45)) / 0.25)))
            if k > 0.01:
                card = self.cta_card.copy()
                tap = 1 - 0.18 * math.sin(math.pi * clamp((ct - 0.45) / 0.2))
                th = scaled(self.thumb, tap * (1 + 0.08 * beat_pulse(T))).rotate(10 * math.sin(ct * 7), Image.BICUBIC,
                                                                                 expand=True)
                paste_center(card, th, 98, 98)
                paste_center(im, scaled(card, k * (1 + 0.025 * beat_pulse(T))).rotate(-2, Image.BICUBIC,
                                                                                     expand=True), W / 2, CTA_Y)
        if self.level_up and t < 0.35:
            im = glitch(im, 1 - t / 0.35, int(t * 30) + self.idx * 7)
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(im, 20 * out)
        return im


class Ending(bq.Ending):
    """The score screen with Christmas ranks and snow; it fades into the first frame so the Short loops."""

    def __init__(self, ui, first, tts):
        super().__init__(ui, first, tts)
        tiers = [("0-3", "Grinch", "💚"), ("4-5", "Snowman", "⛄"), ("6-7", "Elf", "🧝"), ("8-9", "Reindeer", "🦌"),
                 ("10", "Santa", "🎅")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            colr = GOLD if i == 4 else (255, 255, 255)
            row = rounded_card(780, 104, 52, INK + (210,), outline=(XRED if i == 4 else (90, 70, 130)) + (255,), width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 52), sc, font=rfont(60), fill=colr, anchor="lm")
            dr.text((210, 52), label, font=rfont(60, "SemiBold"), fill=colr, anchor="lm")
            row.alpha_composite(emoji(e, 60), (780 - 96, 22))
            self.rows.append(row)
        self.bonus = join(rtext("+ bonus = CHRISTMAS LEGEND", 50, fill=GOLD, stroke=6), emoji("👑", 54))

    def render(self, t):
        im = super().render(t)
        T = self.t0 + t
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        if out < 1:
            self.ui["snow"].draw(im, T, 1 - out)
            im.alpha_composite(self.ui["lights"][int(T / (0.5 * B)) % 2])
        return im


def build(voice="am_adam", voice_pack=None):
    if voice_pack:
        tts = cq.Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    world = G.World()
    globe = G.GlobeRenderer(W, H, world)
    ui = {"globe": globe, "big_globe": globe, "shade": mm.shade_overlay(0.8),
          "vig": [mc.red_vignette(i / 10) for i in range(11)], "cmap": mcq.ColourMap(world),
          "beam": pq.light_beam(), "burst": mq.sunburst(620, GREEN), "snow": Snow(), "lights": light_string(),
          "title": festive_title()}
    rounds, view, prev = [], (G.unit(-30, 30), 520.0), ROUNDS[0][7]
    for i, r in enumerate(ROUNDS, 1):
        sc = Round(i, r, view, prev, ui, tts)
        rounds.append(sc)
        view, prev = sc.end_view, r[7]
    scenes = [*rounds, Ending(ui, rounds[0], tts)]
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def mix_audio(scenes, starts, total):
    """SFX + narrator + the Jingle Bells track (ducked under the voice)."""
    n = int(total * SR) + SR
    fx = np.zeros(n)
    voice = np.zeros(n)
    for sc, st in zip(scenes, starts):
        for at, arr, g in sc.sounds:
            i = int((st + at) * SR)
            fx[i:i + len(arr)] += arr[: n - i] * g
        for at, arr in sc.voices:
            i = int((st + at) * SR)
            voice[i:i + len(arr)] += arr[: n - i]
    fx /= np.abs(fx).max() + 1e-9
    env = mv.lowpass(np.abs(voice), 8)
    duck = mv.lowpass(1 - 0.55 * np.clip(env / 0.05, 0, 1), 3)
    mus = np.zeros(n)
    m = xm.make_jingle(total)
    mus[:len(m)] = m
    mix = np.tanh(1.1 * (0.6 * mus * duck + 0.55 * fx * (0.6 + 0.4 * duck) + voice)) / np.tanh(1.1)
    return (np.clip(np.stack([mix, mix], 1), -1, 1) * 32767).astype(np.int16)


def make_cover(scenes, ui, path):
    r = scenes[0]
    im = r.render(r.count_beats[0] * B + 0.43, header=False)
    im.alpha_composite(Image.new("RGBA", (W, 330), (10, 0, 30, 120)), (0, 0))
    paste_center(im, fit(rtext("CHRISTMAS", 120, fill=XRED, stroke=12), 980).rotate(-3, Image.BICUBIC, expand=True),
                 W / 2, 150)
    paste_center(im, fit(join(rtext("AROUND THE WORLD", 76, stroke=8), emoji("🎄", 72), gap=10), 980)
                 .rotate(2, Image.BICUBIC, expand=True), W / 2, 262)
    paste_center(im, join(rtext("99% FAIL", 96, fill=GOLD, stroke=9), emoji("💀", 96)), W / 2, 1770)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_christmas_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    quiet = a.stills or a.cover
    scenes, starts, total, ui = build(a.voice if not quiet else "none", None if quiet else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    if a.cover:
        make_cover(scenes, ui, os.path.join(HERE, "christmas_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"xmas_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    work = os.path.join(mv.CACHE_DIR, "render_christmas")
    os.makedirs(work, exist_ok=True)
    for f in os.listdir(work):
        os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mix_audio(scenes, starts, total))
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
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-c:v", "libx264", "-crf", "24", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.out], check=True)
    print(f"Done: {a.out}")


if __name__ == "__main__":
    main()
