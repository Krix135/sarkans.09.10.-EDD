#!/usr/bin/env python3
""""GUESS THE CAPITAL CITY" Short (1080x1920), part 3 formula with the full effects pack.

Each round the globe flies to a country (colour-lit map, flag on the question card) and four lettered
dots drop onto four of its real cities; the names sit in a 2x2 answer grid below. A 3-2-1 runs on the
beat (rings from every dot, camera punches, the answer cards bounce, red flash on danger levels). On the
drop the country fills with its flag, a green pin slams onto the capital with a light beam and
shockwaves, the camera pushes in on it, the right card flies to the middle with a sunburst, the wrong
cards turn red and fall away, and a fun fact pops up. The trap answer is the famous big city.

Intro: the narrator says the title and every word slams in as it is spoken, each a hard cut to another
question, then the full title card over a spinning, colour-lit globe (6 beats). EASY -> IMPOSSIBLE plus
a bonus, one like call-out after round 3, looping score screen.
Borders: Natural Earth (public domain). Flags: public domain.

    python3 make_capital_quiz.py
    python3 make_capital_quiz.py --stills 0,5,9
    python3 make_capital_quiz.py --cover
    python3 make_capital_quiz.py --episode 2      # part 2: new countries and traps
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
import make_bigger_country_quiz as bq  # noqa: E402
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
GC = (540, 1010)                     # map centre during the rounds
CARD_Y = 430
NUM_Y = 650
GRID_X = (276, 804)
GRID_Y = (1480, 1606)
FACT_Y = 1606
CTA_Y = 1655
FLY_BEATS = 3
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
GREEN, RED = pq.GREEN, pq.RED
COLS = pq.PIN_COLS

CITIES = {  # (lon, lat)
    "NEW YORK": (-74.01, 40.71), "WASHINGTON, D.C.": (-77.04, 38.91), "LOS ANGELES": (-118.24, 34.05),
    "CHICAGO": (-87.63, 41.88),
    "BARCELONA": (2.17, 41.39), "SEVILLE": (-5.98, 37.39), "MADRID": (-3.70, 40.42), "VALENCIA": (-0.38, 39.47),
    "OTTAWA": (-75.70, 45.42), "TORONTO": (-79.38, 43.65), "VANCOUVER": (-123.12, 49.28), "CALGARY": (-114.07, 51.05),
    "SYDNEY": (151.21, -33.87), "MELBOURNE": (144.96, -37.81), "PERTH": (115.86, -31.95),
    "CANBERRA": (149.13, -35.28),
    "ISTANBUL": (28.98, 41.01), "ANKARA": (32.85, 39.93), "IZMIR": (27.14, 38.42), "ANTALYA": (30.71, 36.90),
    "RIO DE JANEIRO": (-43.17, -22.91), "SÃO PAULO": (-46.63, -23.55), "BRASÍLIA": (-47.88, -15.79),
    "SALVADOR": (-38.50, -12.97),
    "ZURICH": (8.54, 47.37), "GENEVA": (6.14, 46.20), "BASEL": (7.59, 47.56), "BERN": (7.45, 46.95),
    "RABAT": (-6.84, 34.02), "CASABLANCA": (-7.59, 33.57), "MARRAKESH": (-7.99, 31.63), "FEZ": (-5.00, 34.03),
    "LAGOS": (3.38, 6.52), "KANO": (8.52, 12.00), "ABUJA": (7.49, 9.06), "IBADAN": (3.90, 7.38),
    "ALMATY": (76.89, 43.24), "ASTANA": (71.43, 51.13), "SHYMKENT": (69.60, 42.32), "AKTOBE": (57.21, 50.28),
    "YANGON": (96.16, 16.84), "MANDALAY": (96.08, 21.97), "SITTWE": (92.90, 20.15), "NAYPYIDAW": (96.13, 19.75),
}
ROUNDS = [  # map code, flag, country, options A-D (grid order), answer, fact, emoji, tier, spoken answer, sticker
    ("USA", "US", "THE USA", ("NEW YORK", "WASHINGTON, D.C.", "LOS ANGELES", "CHICAGO"), 1,
     "Washington, D.C. isn't part of any state", "🏛", "EASY", "Washington, D.C.! Not New York!", "😎"),
    ("ESP", "ES", "SPAIN", ("BARCELONA", "SEVILLE", "MADRID", "VALENCIA"), 2,
     "Madrid sits almost exactly in the middle of Spain", "🎯", "EASY", "Madrid!", "🔥"),
    ("CAN", "CA", "CANADA", ("OTTAWA", "TORONTO", "VANCOUVER", "CALGARY"), 0,
     "Queen Victoria picked Ottawa as the capital", "👑", "EASY", "Ottawa! Not Toronto!", "🤔"),
    ("AUS", "AU", "AUSTRALIA", ("SYDNEY", "MELBOURNE", "PERTH", "CANBERRA"), 3,
     "it was built as a compromise between Sydney and Melbourne", "🤝", "MEDIUM", "Canberra! Not Sydney!", "😳"),
    ("TUR", "TR", "TURKEY", ("ISTANBUL", "ANKARA", "IZMIR", "ANTALYA"), 1,
     "Istanbul is bigger, but Ankara has been the capital since 1923", "📜", "MEDIUM", "Ankara! Not Istanbul!",
     "🤯"),
    ("BRA", "BR", "BRAZIL", ("RIO DE JANEIRO", "SÃO PAULO", "BRASÍLIA", "SALVADOR"), 2,
     "it was built from scratch in under 4 years", "🏗", "MEDIUM", "Brasilia! Not Rio!", "🔥"),
    ("CHE", "CH", "SWITZERLAND", ("ZURICH", "GENEVA", "BASEL", "BERN"), 3,
     "officially, Bern is only the \"federal city\"", "🧀", "HARD", "Bern!", "😱"),
    ("MAR", "MA", "MOROCCO", ("RABAT", "CASABLANCA", "MARRAKESH", "FEZ"), 0,
     "Casablanca is bigger, but Rabat is the capital", "🕌", "HARD", "Rabat! Not Casablanca!", "💀"),
    ("NGA", "NG", "NIGERIA", ("LAGOS", "KANO", "ABUJA", "IBADAN"), 2,
     "Abuja replaced Lagos as the capital in 1991", "🏙", "INSANE", "Aboojah! Not Lagos!", "🧠"),
    ("KAZ", "KZ", "KAZAKHSTAN", ("ALMATY", "ASTANA", "SHYMKENT", "AKTOBE"), 1,
     "it was called Nur-Sultan from 2019 to 2022", "🔄", "IMPOSSIBLE", "Astana! Not Almaty!", "☠"),
    ("MMR", "MM", "MYANMAR", ("YANGON", "MANDALAY", "SITTWE", "NAYPYIDAW"), 3,
     "Yangon was the capital until 2005", "🏯", "BONUS", "Nay-pyi-daw!", "👑"),
]
ROUNDS_1 = ROUNDS
CITIES.update({
    "SHANGHAI": (121.47, 31.23), "BEIJING": (116.40, 39.90), "XI'AN": (108.94, 34.34), "GUANGZHOU": (113.26, 23.13),
    "MUMBAI": (72.88, 19.08), "KOLKATA": (88.36, 22.57), "NEW DELHI": (77.21, 28.61), "BANGALORE": (77.59, 12.97),
    "TOKYO": (139.69, 35.69), "SAPPORO": (141.35, 43.06), "KYOTO": (135.77, 35.01), "HIROSHIMA": (132.46, 34.39),
    "AUCKLAND": (174.76, -36.85), "CHRISTCHURCH": (172.64, -43.53), "QUEENSTOWN": (168.66, -45.03),
    "WELLINGTON": (174.78, -41.29),
    "HO CHI MINH CITY": (106.63, 10.82), "HANOI": (105.85, 21.03), "DA NANG": (108.22, 16.05),
    "NHA TRANG": (109.19, 12.24),
    "DUBAI": (55.27, 25.20), "AL AIN": (55.76, 24.21), "ABU DHABI": (54.37, 24.45), "RAS AL KHAIMAH": (55.94, 25.79),
    "GUAYAQUIL": (-79.89, -2.19), "CUENCA": (-79.00, -2.90), "MANTA": (-80.72, -0.95), "QUITO": (-78.47, -0.18),
    "RIYADH": (46.68, 24.71), "JEDDAH": (39.17, 21.54), "MECCA": (39.83, 21.42), "MEDINA": (39.61, 24.47),
    "LUANG PRABANG": (102.13, 19.89), "PAKSE": (105.78, 15.12), "VIENTIANE": (102.63, 17.97),
    "SAVANNAKHET": (104.75, 16.56),
    "ABIDJAN": (-4.03, 5.36), "YAMOUSSOUKRO": (-5.28, 6.83), "BOUAKÉ": (-5.03, 7.69), "SAN-PÉDRO": (-6.64, 4.75),
    "PARO": (89.41, 27.43), "PHUNTSHOLING": (89.39, 26.85), "JAKAR": (90.75, 27.55), "THIMPHU": (89.64, 27.47),
})
ROUNDS_2 = [
    ("CHN", "CN", "CHINA", ("SHANGHAI", "BEIJING", "XI'AN", "GUANGZHOU"), 1,
     "its name means \"northern capital\"", "🧭", "EASY", "Beijing! Not Shanghai!", "😎"),
    ("IND", "IN", "INDIA", ("MUMBAI", "KOLKATA", "NEW DELHI", "BANGALORE"), 2,
     "Kolkata was the capital until 1911", "📜", "EASY", "New Delhi! Not Mumbai!", "🔥"),
    ("JPN", "JP", "JAPAN", ("TOKYO", "SAPPORO", "KYOTO", "HIROSHIMA"), 0,
     "Kyoto was the capital for over 1,000 years", "⛩", "EASY", "Tokyo!", "🤔"),
    ("NZL", "NZ", "NEW ZEALAND", ("AUCKLAND", "CHRISTCHURCH", "QUEENSTOWN", "WELLINGTON"), 3,
     "it's the southernmost capital in the world", "🧭", "MEDIUM", "Wellington! Not Auckland!", "😳"),
    ("VNM", "VN", "VIETNAM", ("HO CHI MINH CITY", "HANOI", "DA NANG", "NHA TRANG"), 1,
     "Ho Chi Minh City used to be called Saigon", "🛵", "MEDIUM", "Hanoi! Not Ho Chee Min City!", "🤯"),
    ("ARE", "AE", "THE UAE", ("DUBAI", "AL AIN", "ABU DHABI", "RAS AL KHAIMAH"), 2,
     "Dubai is more famous, but Abu Dhabi is the capital", "🏙", "MEDIUM", "Abu Dhabi! Not Dubai!", "🔥"),
    ("ECU", "EC", "ECUADOR", ("GUAYAQUIL", "CUENCA", "MANTA", "QUITO"), 3,
     "it sits 2,850 m above sea level", "🏔", "HARD", "Quito! Not Guayaquil!", "😱"),
    ("SAU", "SA", "SAUDI ARABIA", ("RIYADH", "JEDDAH", "MECCA", "MEDINA"), 0,
     "Riyadh means \"the gardens\"", "🌴", "HARD", "Riyadh! Not Jeddah!", "💀"),
    ("LAO", "LA", "LAOS", ("LUANG PRABANG", "PAKSE", "VIENTIANE", "SAVANNAKHET"), 2,
     "Luang Prabang was the royal capital", "👑", "INSANE", "Vientiane!", "🧠"),
    ("CIV", "CI", "IVORY COAST", ("ABIDJAN", "YAMOUSSOUKRO", "BOUAKÉ", "SAN-PÉDRO"), 1,
     "Abidjan is bigger, but Yamoussoukro became the capital in 1983", "📜", "IMPOSSIBLE",
     "Yam-oo-soo-kro! Not Ab-ih-jahn!", "☠"),
    ("BTN", "BT", "BHUTAN", ("PARO", "PHUNTSHOLING", "JAKAR", "THIMPHU"), 3,
     "Thimphu has no traffic lights", "🚦", "BONUS", "Tim-poo!", "👑"),
]
SPOKEN = {"THE USA": "the USA", "THE UAE": "the United Arab Emirates"}
EPISODES = {  # rounds, part, file name, cover round, cover line, max zoom, intro phrases
    1: (ROUNDS_1, None, "capital_quiz", 3, "99% SAY SYDNEY", 9000, ("Guess the capital!", "Only one percent",
                                                                     "get them all!")),
    2: (ROUNDS_2, 2, "capital_quiz_2", 5, "99% SAY DUBAI", 17000, ("Guess the capital!", "Part two!",
                                                                   "Get them all!")),
}
PART, NAME, COVER, COVER_LINE, MAX_R, INTRO_WORDS = EPISODES[1][1:]
END_LINE = "How many did you get? Comment your score!"


def set_episode(ep):
    global ROUNDS, PART, NAME, COVER, COVER_LINE, MAX_R, INTRO_WORDS
    ROUNDS, PART, NAME, COVER, COVER_LINE, MAX_R, INTRO_WORDS = EPISODES[ep]


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


def city_view(world, code, names):
    """Centre on the four cities and zoom in until no two dots touch, but keep all four on screen; small
    countries zoom in further so the whole country fills the map area."""
    pts = np.array([G.unit(*CITIES[n]) for n in names])
    c = pts.mean(0)
    c /= np.linalg.norm(c)
    for _ in range(2):                                       # centre on the middle of the cities' bounding box
        east, up, _ = G.frame_axes(c)
        ex, uy = pts @ east, pts @ up
        c = c + east * (ex.max() + ex.min()) / 2 + up * (uy.max() + uy.min()) / 2
        c /= np.linalg.norm(c)
    east, up, _ = G.frame_axes(c)
    r_cities = min(400 / max(np.abs(pts @ east).max(), 1e-3), 290 / max(np.abs(pts @ up).max(), 1e-3))
    sep = min(math.acos(min(1.0, float(pts[i] @ pts[j]))) for i in range(4) for j in range(i + 1, 4))
    ci = world.codes.index(code)
    idx = np.nonzero(world.owner == ci)[0]
    big = max(world.lens[i] for i in idx)
    cp = np.concatenate([world.P[world.starts[i]:world.starts[i] + world.lens[i]] for i in idx
                         if world.lens[i] >= 0.05 * big])
    r_country = min(430 / max(np.abs(cp @ east).max(), 1e-3), 330 / max(np.abs(cp @ up).max(), 1e-3))
    return c, float(np.clip(min(r_cities, max(r_country, 66 / max(sep, 1e-4))), 600, MAX_R))


def project(p, c, R, center):
    east, up, view = G.frame_axes(c)
    return center[0] + R * float(p @ east), center[1] - R * float(p @ up), float(p @ view) > 0.05


def dot_sprite(letter, col):
    k = 3
    s = 52 * k
    im = Image.new("RGBA", (s, s))
    d = ImageDraw.Draw(im)
    d.ellipse((2 * k, 2 * k, s - 2 * k, s - 2 * k), fill=INK + (255,))
    d.ellipse((5 * k, 5 * k, s - 5 * k, s - 5 * k), fill=(255, 255, 255, 255))
    d.ellipse((10 * k, 10 * k, s - 10 * k, s - 10 * k), fill=col + (255,))
    im = im.resize((52, 52), Image.LANCZOS)
    paste_center(im, rtext(letter, 30, fill=(255, 255, 255), stroke=4), 26, 27)
    return im


def answer_card(letter, name, col, state=None):
    """state: None (question), "ok" (green with a check) or "no" (red with a cross)."""
    w, h = 512, 112
    fill = {None: INK + (238,), "ok": (24, 150, 80, 255), "no": (150, 30, 50, 255)}[state]
    edge = {None: col, "ok": (255, 255, 255), "no": (255, 120, 130)}[state]
    card = rounded_card(w, h, h // 2, fill, outline=edge + (255,), width=6)
    badge = mv.circle(78, (col if state is None else (255, 255, 255)) + (255,))
    ImageDraw.Draw(badge).text((39, 41), letter, font=rfont(48), fill=(255, 255, 255) if state is None else INK,
                               anchor="mm")
    card.alpha_composite(badge, (17, (h - 78) // 2))
    size = 50
    room = w - 130 - (66 if state else 24)
    while rfont(size).getlength(name) > room and size > 28:
        size -= 2
    t = rtext(name, size, stroke=5)
    card.alpha_composite(t, (110, (h - t.height) // 2))
    if state == "ok":
        paste_center(card, emoji("✅", 54), w - 48, h / 2)
    elif state == "no":
        paste_center(card, emoji("❌", 50), w - 48, h / 2)
    return card


def question_card(name, flag):
    q = rtext("WHAT'S THE CAPITAL OF", 46, fill=(220, 220, 240), stroke=5)
    size = 100
    while rfont(size).getlength(name + "?") > 620 and size > 56:
        size -= 4
    parts = (name + "?").replace("IV", "I\0V").split("\0")     # the I and V run together in this font
    imgs = [rtext(x, size, fill=GOLD, stroke=9) for x in parts]
    n = imgs[0]
    for nxt in imgs[1:]:                                     # overlap the outline padding, keep a small gap
        solid = [im_.getchannel("A").point(lambda v: 255 if v > 200 else 0).getbbox() for im_ in (n, nxt)]
        ov = (n.width - solid[0][2]) + solid[1][0] + 18 - int(size * 0.07)   # outlines overlap
        both = Image.new("RGBA", (n.width + nxt.width - ov, max(n.height, nxt.height)))
        both.alpha_composite(n, (0, 0))
        both.alpha_composite(nxt, (n.width - ov, 0))
        n = both
    fl = flag.copy()
    fl.thumbnail((150, 100), Image.LANCZOS)
    fb = Image.new("RGBA", (fl.width + 10, fl.height + 10), (255, 255, 255, 255))
    fb.paste(fl, (5, 5))
    body_w = max(q.width, n.width) + 30 + fb.width
    card = rounded_card(min(1010, body_w + 70), 200, 50, (14, 6, 40, 228), outline=CYAN + (255,), width=5)
    x0 = (card.width - body_w) // 2
    card.alpha_composite(q, (x0, 22))
    card.alpha_composite(n, (x0, 66 + (100 - size) // 3))
    card.alpha_composite(fb, (x0 + max(q.width, n.width) + 30, (200 - fb.height) // 2))
    return card


def ring(im, x, y, r, col, a, width=7, squash=1.0):
    if a > 2:
        ImageDraw.Draw(im, "RGBA").ellipse((x - r, y - r * squash, x + r, y + r * squash), outline=col + (int(a),),
                                           width=width)


def capital_tag(name):
    body = join(emoji("⭐", 52), rtext(name, 56, fill=GOLD, stroke=6), gap=10)
    card = rounded_card(body.width + 50, body.height + 22, (body.height + 22) // 2, (12, 10, 30, 240),
                        outline=GOLD + (255,), width=5)
    paste_center(card, body, card.width / 2, card.height / 2)
    return card


# ----------------------------------------------------------------------------
# rounds
# ----------------------------------------------------------------------------
class Round(mv.Scene):
    def __init__(self, idx, r, prev_view, prev_tier, ui, tts):
        super().__init__()
        code, fcode, cname, opts, ans, fact, femoji, tier, said, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = FLY_BEATS
        self.fly = f * B
        spoken_name = SPOKEN.get(cname, cname.title())
        v_q = tts.say(("Bonus! " if self.bonus else "") + f"What's the capital of {spoken_name}?", speed=1.18) \
            if tts else None
        q_len = len(v_q) / SR if v_q is not None else 1.6
        c0 = max(f + (2 if self.bonus else 1), math.ceil((0.12 + q_len - 0.1) / B))   # long questions wait
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.reveal = (c0 + n) * B
        self.dur = self.reveal + ((6 if self.bonus else 5) + (5 if self.cta else 0)) * B
        self.cta_at = 2.2 * B
        world = ui["globe"].world
        self.target = world.codes.index(code)
        _, self.near, _ = world.country(code)
        c, R = city_view(world, code, opts)
        self.view = (c, R)
        self.cam = mm.Camera(prev_view, self.view, self.fly, self.reveal)
        self.ans = ans
        self.cap = G.unit(*CITIES[opts[ans]])
        self.end_view = (G.slerp(c, self.cap, 0.6), R * 1.35)
        self.cities = [(L, name, G.unit(*CITIES[name])) for L, name in zip("ABCD", opts)]
        self.dots = {L: dot_sprite(L, COLS[L]) for L in "ABCD"}
        self.grey = {L: dot_sprite(L, (110, 110, 130)) for L in "ABCD"}
        self.pin = pq.pin_sprite(opts[ans][0], GREEN, "✅")
        self.shadow = pq.pin_shadow()
        self.cards = {L: answer_card(L, name, COLS[L]) for L, name in zip("ABCD", opts)}
        L_ans = "ABCD"[ans]
        self.ok_card = answer_card(L_ans, opts[ans], COLS[L_ans], "ok")
        self.no_cards = {L: answer_card(L, name, COLS[L], "no") for L, name in zip("ABCD", opts)}
        self.cap_tag = capital_tag(opts[ans])
        self.flag = Image.open(os.path.join(FLAG_DIR, fcode + ".png")).convert("RGBA")
        self.fcols = mm.flag_colours(self.flag)
        self.card = question_card(cname, self.flag)
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
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        n = len(self.count_beats)
        self.nums = {k: rtext(str(k), 170, fill=PINK if k == 1 else (255, 255, 255), stroke=14) for k in range(1, n + 1)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self.drop_at = [self.fly - 0.35 + i * 0.1 for i in range(4)]
        self.card_at = [self.fly * 0.5 + i * 0.08 for i in range(4)]
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8)]
        for at in self.drop_at:
            self.sounds += [(at + 0.12, mv.sfx_pop(), 0.7), (at + 0.12, mv.sfx_click(), 0.4)]
        for at in self.card_at:
            self.sounds.append((at + 0.1, mv.sfx_click(), 0.45))
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        if self.danger:
            self.sounds.append((self.count_beats[-1] * B, mq.sfx_boom(), 0.6))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        rv0 = self.reveal
        self.sounds += [(rv0, mq.sfx_boom(), 0.9), (rv0, mv.sfx_ding(), 1.0), (rv0 + 0.02, mq.sfx_glitch(), 0.4),
                        (rv0 + 0.05, mq.sfx_pling(), 0.6), (rv0 + 0.25, mv.sfx_whoosh(0.35), 0.5),
                        (rv0 + 0.3, mq.sfx_boom(), 0.5), (rv0 + 0.45, mv.sfx_pop(), 0.7),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        if tts:
            self.voices.append((0.12, v_q))
            self.voices.append((self.reveal + 0.08, tts.say(said, speed=1.12)))
            if self.cta:
                self.voices.append((self.reveal + self.cta_at, tts.say(CTA_LINE, speed=1.12)))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = self.reveal + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, mq.sfx_pling(), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        rr = random.Random(idx * 31)
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1350, -450), rr.randint(12, 26), rr.choice(self.fcols),
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
            for b in self.count_beats:                       # camera punch on every count beat
                tb = t - b * B
                if 0 <= tb < 0.25:
                    R *= 1 + (0.09 if self.danger else 0.06) * (1 - ease_out_cubic(tb / 0.25))
        hl = clamp((rv - 0.3) / 0.2) if rv > 0 else 0.0
        fa = 0.92 * clamp((rv - 0.4) / 0.3) if rv > 0 else 0.0
        im = ui["globe"].render(c, R, GC, self.near if hl > 0 else None, hl, self.flag, fa)
        if hl > 0:
            ui["cmap"].draw(im, c, R, GC, self.target, 0.8 * (1 - 0.5 * clamp((rv - 0.3) / 0.4)), 0.0)
        else:
            ui["cmap"].draw(im, c, R, GC, None, 0.8, 0.0)
        im = mm.zoom_blur(im, blur)
        im = rgb_split(im, 22 * blur)
        im.alpha_composite(ui["shade"])
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv > 0:
            im.alpha_composite(cq.speed_lines(1 - clamp(rv / 0.45), self.idx, GC))
        # city dots
        cap_xy = None
        for i, (L, name, p) in enumerate(self.cities):
            td = t - self.drop_at[i]
            if td <= 0:
                continue
            x, y, vis = project(p, c, R, GC)
            if not vis:
                continue
            right = i == self.ans
            if right:
                cap_xy = (x, y)
            tl = td - 0.12
            if 0 < tl < 0.45:
                ring(im, x, y, 14 + 90 * ease_out_cubic(tl / 0.45), COLS[L], 255 * (1 - tl / 0.45), 6, 1.0)
            if rv <= 0:
                for b in self.count_beats:
                    tb = t - b * B
                    if 0 <= tb < 0.4:
                        ring(im, x, y, 26 + 70 * ease_out_cubic(tb / 0.4), (255, 255, 255), 200 * (1 - tb / 0.4), 5,
                                1.0)
                s = ease_out_back(clamp(td / 0.25), 2.4) * (1 + 0.1 * beat_pulse(T + i * 0.1))
                if s > 0.01:
                    paste_center(im, scaled(self.dots[L], s), x, y)
            elif not right:
                a = 1 - 0.6 * clamp(rv / 0.3)
                paste_center(im, scaled(self.grey[L], 1 - 0.3 * clamp(rv / 0.3)), x + 10 * math.sin(rv * 60) *
                             (1 - clamp(rv / 0.3)), y, a)
            else:
                paste_center(im, self.dots[L], x, y)
        if rv > 0 and cap_xy is not None:                    # the capital: beam, shockwaves, a pin slams down
            x, y = cap_xy
            ba = clamp(rv / 0.05) * (1 - clamp(rv / 0.9))
            if ba > 0.01:
                paste_center(im, ui["beam"], x, y - 650, ba)
            for j in range(3):
                tl = rv - 0.09 * j
                if 0 < tl < 0.5:
                    ring(im, x, y, 20 + 190 * ease_out_cubic(tl / 0.5), GREEN, 255 * (1 - tl / 0.5), 9, 0.42)
            kp = clamp(rv / 0.22)
            fall = (1 - ease_out_back(kp, 2.0)) * 700
            paste_center(im, self.shadow, x, y, kp)
            sp = scaled(self.pin, 1.1 + 0.04 * beat_pulse(T))
            im.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height - fall)))
            kt = ease_out_back(clamp((rv - 0.4) / 0.25), 2.0)
            if kt > 0.01:
                ty = max(150 + CARD_Y, y - sp.height - 60)
                tx = min(max(x, self.cap_tag.width / 2 + 20), W - self.cap_tag.width / 2 - 20)
                paste_center(im, scaled(self.cap_tag, kt), tx, ty)
        d = ImageDraw.Draw(im)
        if header:
            paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
            x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
            frac = 1.0 if t < self.fly else max(0.0, 1 - (t - self.fly) / (self.reveal - self.fly))
            d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
            colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
            if frac > 0.01:
                d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 11, fill=colr + (255,))
            paste_center(im, self.tag, x0 + self.tag.width / 2, 285)
            nk = self.idx if rv > 0 else self.idx - 1
            if nk > 0:
                sc = 1 + 0.5 * (1 - ease_out_cubic(rv / 0.25)) if 0 < rv < 0.25 else 1.0
                stk = self.streak[nk]
                paste_center(im, scaled(stk, sc), x1 - stk.width / 2 + 10, 288)
        kc = ease_out_back(clamp((t - 0.05) / 0.3), 1.6)
        if kc > 0.01:
            paste_center(im, scaled(self.card, kc * (1 + 0.015 * beat_pulse(T))), W / 2, CARD_Y)
        # the answer grid
        cta_on = self.cta and rv > self.cta_at
        for i, L in enumerate("ABCD"):
            gx, gy = GRID_X[i % 2], GRID_Y[i // 2]
            kin = ease_out_back(clamp((t - self.card_at[i]) / 0.3), 1.8)
            if kin <= 0.01:
                continue
            if rv <= 0:
                s = kin
                for j, b in enumerate(self.count_beats):     # the cards take turns to bounce on the beats
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
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, NUM_Y, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a * 0.9)
        if rv > 0:
            if cap_xy is not None:
                cx, cy = cap_xy
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
            if 0.22 < rv < 0.4:                              # second punch when the pin lands
                im = shake(im, 14 * (1 - (rv - 0.22) / 0.18), t)
        else:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 14 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 10 * (1 - tb / 0.15))
            tb = t - self.count_beats[-1] * B
            if self.danger and 0 <= tb < 0.2:                # red flash on the last count
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 30, 60, int(90 * (1 - tb / 0.2)))))
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


# ----------------------------------------------------------------------------
# intro: the title, said and slammed in word by word
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    """6 beats. "Guess the capital!" over the bonus question (readable on frame one), "Only one percent" and
    "get them all!" each a hard cut to another question, then the full title card with 99% FAIL over a
    spinning, colour-lit globe and a whip into round 1."""
    TEASE, MONTAGE = 10, (9, 8, 7)

    def __init__(self, ui, tts, rounds):
        super().__init__()
        self.ui, self.rounds = ui, rounds
        self.dur = 6 * B
        hb = 0.5 * B
        clips = [tts.say(w, speed=1.22) for w in INTRO_WORDS] if tts else None
        lens = [len(c) / SR for c in clips] if clips else [0.9, 0.75, 0.7]
        self.slams = [0.0]                                   # each phrase starts on the nearest half beat
        for ln in lens:
            prev = self.slams[-1]
            self.slams.append(max(prev + hb, round((prev + ln - 0.08) / hb) * hb))
        self.slams[-1] = min(self.slams[-1], self.dur - 0.4)
        self.mid = self.slams[0] + max(hb, round(lens[0] * 0.45 / hb) * hb)   # "...capital!" lands
        if clips:
            for at, c in zip(self.slams, clips):
                self.voices.append((at, c))
        self.o3 = join(rtext("answer at the end", 58, fill=GOLD, stroke=7), emoji("👀", 62))
        self.w1 = fit(rtext("GUESS THE", 150, fill=(255, 255, 255), stroke=14), 980)
        self.w2 = fit(join(rtext("CAPITAL", 170, fill=GOLD, stroke=15), emoji("🏙", 140), gap=14), 980)
        self.w3 = mcq.part_badge(PART, 150).rotate(-4, Image.BICUBIC, expand=True) if PART else \
            fit(rtext("ONLY 1%", 170, fill=PINK, stroke=15), 980)
        self.part = mcq.part_badge(PART, 84) if PART else None
        self.w4 = fit(join(rtext("GET THEM ALL", 124, fill=CYAN, stroke=12), emoji("😳", 110), gap=12), 980)
        self.l1 = fit(rtext("GUESS THE", 130, stroke=12), 960)
        self.l2 = fit(join(rtext("CAPITAL CITY", 128, fill=GOLD, stroke=12), emoji("🏙", 112), gap=12), 980)
        self.l3 = join(rtext("99% FAIL", 116, fill=PINK, stroke=11), emoji("💀", 112))
        self.sounds += [(0.0, sfx_heartbeat(), 0.9), (B, sfx_heartbeat(), 0.7),
                        (self.mid, mq.sfx_boom(), 0.8), (self.mid, mv.sfx_pop(), 0.8),
                        (self.slams[2], mv.sfx_riser(self.slams[3] - self.slams[2]), 0.6),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k, at in enumerate(self.slams):
            self.sounds += [(at, mq.sfx_boom(), 1.0 if k in (0, 3) else 0.75), (at, mv.sfx_whoosh(0.35), 0.6),
                            (at, mv.sfx_pop(), 0.8)]
            if k:
                self.sounds.append((at, mq.sfx_glitch(), 0.45))

    def render(self, t):
        T = self.t0 + t
        k = max(i for i, at in enumerate(self.slams) if at <= t + 1e-9)
        ts = t - self.slams[k]
        slam = 1 + 0.35 * (1 - ease_out_cubic(clamp(ts / 0.18)))
        if k < 3:                                            # word slams over real questions
            sc_r = self.rounds[(self.TEASE, self.MONTAGE[0], self.MONTAGE[1])[k]]
            im = sc_r.render(sc_r.fly + 0.3)
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 120)))
            if k == 0:
                im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.5 * beat_pulse(T)))])
                paste_center(im, scaled(self.w1, slam).rotate(-3, Image.BICUBIC, expand=True), W / 2, 760)
                if t >= self.mid:
                    sm = 1 + 0.35 * (1 - ease_out_cubic(clamp((t - self.mid) / 0.18)))
                    paste_center(im, scaled(self.w2, sm * (1 + 0.03 * beat_pulse(T))).rotate(2, Image.BICUBIC,
                                                                                             expand=True), W / 2, 950)
            else:
                paste_center(im, scaled(self.w3, slam if k == 1 else 1.0).rotate(-3, Image.BICUBIC, expand=True),
                             W / 2, 780)
                if k == 2:
                    paste_center(im, scaled(self.w4, slam).rotate(2, Image.BICUBIC, expand=True), W / 2, 960)
            paste_center(im, self.o3, W / 2, 1745)
            im = shake(im, 24 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
            im = rgb_split(im, (8 if k == 0 else 16) * (1 - clamp(ts / 0.15)))
            if k > 0:
                im = mm.zoom_blur(im, 0.6 * (1 - clamp(ts / 0.1)))
                if ts < 0.06:
                    im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            return im
        gc = (540, 1270)                                     # the full title card over a colour-lit globe
        R = 470 * (1 + 0.05 * beat_pulse(T)) * (1.25 - 0.25 * ease_out_cubic(clamp(ts / 0.3)))
        c = G.unit(-20 + 50 * t, 25)
        im = self.ui["big_globe"].render(c, R, gc)
        self.ui["cmap"].draw(im, c, R, gc, None, 0.75 + 0.2 * beat_pulse(T))
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 40)))
        for j, (img, y, rot) in enumerate([(self.l1, 330, -3), (self.l2, 500, 2), (self.l3, 680, -2)]):
            sc = (slam if j == 2 else 1 + 0.12 * (1 - ease_out_cubic(clamp(ts / 0.18)))) * (1 + 0.03 * beat_pulse(T))
            paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
        if self.part is not None:
            paste_center(im, scaled(self.part, slam * (1 + 0.04 * beat_pulse(T))).rotate(5, Image.BICUBIC, expand=True),
                         W / 2, 830)
        im = shake(im, 22 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
        if ts < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - ts / 0.08)))))
        whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
        if whip > 0:
            im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
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
          "beam": pq.light_beam(), "burst": mq.sunburst(620, GREEN)}
    rounds, view, prev = [], (G.unit(-20 + 50 * 6 * B, 25), 600.0), ROUNDS[0][7]
    for i, r in enumerate(ROUNDS, 1):
        sc = Round(i, r, view, prev, ui, tts)
        rounds.append(sc)
        view, prev = sc.end_view, r[7]
    intro = Intro(ui, tts, rounds)
    scenes = [intro, *rounds, bq.Ending(ui, intro, tts)]
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(scenes, ui, path):
    r = scenes[1 + COVER]                                    # the famous-city trap (Sydney, Dubai)
    im = r.render(r.count_beats[0] * B + 0.43, header=False)   # between beats: no number, no glitch
    paste_center(im, fit(join(rtext("GUESS THE CAPITAL", 100, fill=PINK, stroke=10), emoji("🏙", 96), gap=10), 990)
                 .rotate(-3, Image.BICUBIC, expand=True), W / 2, 215)
    paste_center(im, join(rtext(COVER_LINE, 92, fill=GOLD, stroke=9), emoji("💀", 92)), W / 2, 1765)
    if PART:
        paste_center(im, mcq.part_badge(PART, 80).rotate(-5, Image.BICUBIC, expand=True), W / 2, 1335)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", type=int, default=1, choices=sorted(EPISODES))
    ap.add_argument("--out", default=None)
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--music", default="phonk", choices=["phonk", "none"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    set_episode(a.episode)
    a.out = a.out or os.path.join(HERE, f"short_{NAME}.mp4")
    quiet = a.stills or a.cover
    scenes, starts, total, ui = build(a.voice if not quiet else "none", None if quiet else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    if a.cover:
        make_cover(scenes, ui, os.path.join(HERE, f"{NAME}_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"cap{a.episode}_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, f"render_{NAME}")
    os.makedirs(work, exist_ok=True)
    for f in os.listdir(work):
        os.remove(os.path.join(work, f))
    wav = os.path.join(work, "audio.wav")
    mv.write_wav(wav, mmq.mix_audio(scenes, starts, total, a.music))
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
