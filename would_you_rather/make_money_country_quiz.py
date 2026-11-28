#!/usr/bin/env python3
""""GUESS THE COUNTRY BY ITS MONEY" Short (1080x1920), maximum edit.

Each round a stylised banknote (our own design: guilloche pattern, portrait window, holographic strip,
serial number, the real currency's symbol, denomination and typical colour; no real note images) spins in
over raining money. Clues unlock on the beat: the currency's name stamps on like a rubber stamp, a
continent hint slides in, then the redacted COUNTRY line glitches. On the drop the note does a 3D flip to
its back, which shows the country's flag and name, with a cash-register cha-ching and a coin explosion.
Then a whip to space: the globe zooms in, the country fills with its flag, money bursts out of it, the
note flies to the corner, the name flips in on letter tiles and a fun fact pops up. Every currency here is
used by one country only. Hook intro that shows the game (8 beats), EASY -> IMPOSSIBLE plus a bonus, one
like call-out after round 3, looping score screen.
Borders: Natural Earth (public domain). Flags: public domain.

    python3 make_money_country_quiz.py
    python3 make_money_country_quiz.py --stills 0,5,9
    python3 make_money_country_quiz.py --cover
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
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

import globe as G  # noqa: E402
import make_bigger_country_quiz as bq  # noqa: E402
import make_club_quiz as cq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_missing_country_quiz as mcq  # noqa: E402
import make_video as mv  # noqa: E402
import make_wyr_money as wm  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_in_out, ease_out_back, ease_out_cubic, emoji, paste_center, \
    rounded_card, scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
NW, NH = 940, 470                    # banknote size
NOTE_C = (540, 990)
CARD_Y = 438
HINT_Y = 1325
GC = (540, 1110)
mm.TILE_Y = 1645
FACT_Y = 1765
CTA_Y = 1790
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
SYMFONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
GREEN = (46, 204, 113)
STAMP_RED = (215, 30, 45)

ROUNDS = [  # map code, flag, country, symbol, currency, denomination, note colour, hint, hint emoji, fact, fact
    #         emoji, tier, prompt, spoken answer, sticker
    ("JPN", "JP", "JAPAN", "¥", "YEN", "10,000", (176, 128, 72), "ASIA", "🍣", "\"yen\" means \"round\" in Japanese",
     "⭕", "EASY", "Which country uses this money?", "Japan!", "😎"),
    ("GBR", "GB", "UNITED KINGDOM", "£", "POUND STERLING", "20", (122, 72, 160), "EUROPE", "☕",
     "the pound sign comes from \"libra\", Latin for pound", "⚖", "EASY", "Next one!", "The United Kingdom!", "🔥"),
    ("IND", "IN", "INDIA", "₹", "RUPEE", "500", (112, 118, 112), "ASIA", "🏏", "its symbol was only designed in 2010",
     "✏", "EASY", "Too easy?", "India!", "🤔"),
    ("BRA", "BR", "BRAZIL", "R$", "REAL", "100", (56, 116, 190), "SOUTH AMERICA", "⚽",
     "every note shows a Brazilian animal on the back", "🐆", "MEDIUM", "Think fast!", "Brazil!", "😳"),
    ("RUS", "RU", "RUSSIA", "₽", "RUBLE", "5,000", (192, 88, 58), "EUROPE & ASIA", "🪆",
     "its symbol was only adopted in 2013", "📅", "MEDIUM", "Ooh, tricky!", "Russia!", "🤯"),
    ("THA", "TH", "THAILAND", "฿", "BAHT", "1,000", (146, 112, 78), "ASIA", "🐘", "every Thai note shows the King",
     "👑", "MEDIUM", "Next!", "Thailand!", "🔥"),
    ("POL", "PL", "POLAND", "zł", "ZŁOTY", "100", (86, 128, 78), "EUROPE", "🥟", "\"złoty\" means \"golden\"", "🥇",
     "HARD", "Hard level!", "Poland!", "😱"),
    ("VNM", "VN", "VIETNAM", "₫", "ĐỒNG", "500,000", (48, 148, 188), "ASIA", "🍜", "most of its notes are made of plastic",
     "♻", "HARD", "No way!", "Vietnam!", "💀"),
    ("NGA", "NG", "NIGERIA", "₦", "NAIRA", "1,000", (150, 96, 128), "AFRICA", "🌍",
     "its name comes from the word \"Nigeria\"", "🔤", "INSANE", "Insane level!", "Nigeria!", "🧠"),
    ("KAZ", "KZ", "KAZAKHSTAN", "₸", "TENGE", "10,000", (56, 136, 150), "ASIA", "🐎",
     "it replaced the Soviet ruble in 1993", "📅", "IMPOSSIBLE", "Impossible level!", "Kazakhstan!", "☠"),
    ("PRY", "PY", "PARAGUAY", "₲", "GUARANÍ", "100,000", (78, 148, 92), "SOUTH AMERICA", "🧉",
     "it's named after the Guaraní people", "🗣", "BONUS", "Bonus! Only one percent!", "Paraguay!", "👑"),
]
INTRO_WORDS = ("Guess the country", "from its money!", "Only one percent get all ten!")
_SF = {}


def sfont(size):
    if size not in _SF:
        _SF[size] = ImageFont.truetype(SYMFONT, size)
    return _SF[size]


def stext(text, size, fill=(255, 255, 255), stroke=0, stroke_fill=INK):
    """Text in DejaVu Sans Bold (has every currency symbol and the diacritics)."""
    f = sfont(size)
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + 4, b - t + 4))
    ImageDraw.Draw(im).text((2 - l, 2 - t), text, font=f, fill=fill, stroke_width=stroke,
                            stroke_fill=stroke_fill + (255,) if len(stroke_fill) == 3 else stroke_fill)
    return im


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


def lighten(c, k):
    return tuple(int(v + (255 - v) * k) for v in c)


def darken(c, k):
    return tuple(int(v * (1 - k)) for v in c)


def note_mask():
    m = Image.new("L", (NW * 2, NH * 2))
    ImageDraw.Draw(m).rounded_rectangle((0, 0, NW * 2 - 1, NH * 2 - 1), 52, fill=255)
    return m.resize((NW, NH), Image.LANCZOS)


def note_front(r, seed):
    """Our own stylised banknote for a currency (front, without the name stamp)."""
    code, fcode, cname, sym, cur, denom, col = r[:7]
    rr = random.Random(seed)
    base = Image.new("RGBA", (NW, NH))
    a = np.zeros((NH, NW, 4), np.uint8)
    yy, xx = np.mgrid[0:NH, 0:NW]
    k = (xx / NW * 0.6 + yy / NH * 0.4)
    c0, c1 = np.array(lighten(col, 0.35)), np.array(darken(col, 0.25))
    a[..., :3] = (c0[None, None, :] * (1 - k[..., None]) + c1[None, None, :] * k[..., None]).astype(np.uint8)
    a[..., 3] = 255
    base = Image.fromarray(a, "RGBA")
    d = ImageDraw.Draw(base, "RGBA")
    pale = lighten(col, 0.6) + (70,)
    for j in range(46):                                      # fine wavy guilloche lines across the note
        y0 = 20 + j * 10
        pts = [(x, y0 + 6 * math.sin(x / 23 + j * 0.7) + 4 * math.sin(x / 9 + j)) for x in range(0, NW + 8, 8)]
        d.line(pts, fill=pale, width=1)
    for (cx, cy, R0) in ((660, 225, 150), (180, 235, 120)):  # two rosettes
        for j in range(18):
            pts = []
            for i in range(181):
                th = i / 180 * 2 * math.pi
                rad = R0 * (0.62 + 0.38 * math.cos(7 * th + j * 0.35)) * (1 - j * 0.012)
                pts.append((cx + rad * math.cos(th + j * 0.17), cy + rad * math.sin(th + j * 0.17)))
            d.line(pts, fill=lighten(col, 0.7) + (85,), width=2)
    d.rounded_rectangle((16, 16, NW - 17, NH - 17), 40, outline=lighten(col, 0.75) + (255,), width=6)
    d.rounded_rectangle((30, 30, NW - 31, NH - 31), 32, outline=darken(col, 0.35) + (200,), width=2)
    for x in range(52, NW - 40, 26):                         # dotted micro-print border
        d.ellipse((x - 3, 37, x + 3, 43), fill=lighten(col, 0.8) + (160,))
        d.ellipse((x - 3, NH - 43, x + 3, NH - 37), fill=lighten(col, 0.8) + (160,))
    ox, oy, ow, oh = 70, 78, 220, 300                        # portrait window with a generic bust
    d.ellipse((ox, oy, ox + ow, oy + oh), fill=lighten(col, 0.55) + (255,), outline=lighten(col, 0.85) + (255,),
              width=6)
    sil = darken(col, 0.15) + (190,)
    d.ellipse((ox + 70, oy + 55, ox + 150, oy + 145), fill=sil)
    d.chord((ox + 30, oy + 150, ox + 190, oy + 330), 180, 360, fill=sil)
    base.alpha_composite(Image.new("RGBA", (NW, NH)))
    sy = stext(sym, 200 if len(sym) == 1 else 150, fill=(255, 255, 255), stroke=9, stroke_fill=darken(col, 0.5))
    paste_center(base, sy, 690, 180)
    dn = stext(denom, 92 if len(denom) <= 5 else 70, fill=(255, 255, 255), stroke=7, stroke_fill=darken(col, 0.5))
    dn = scaled(dn, min(1.0, 400 / dn.width))
    paste_center(base, dn, 690, 340)
    small = stext(denom, 40, fill=lighten(col, 0.85), stroke=3, stroke_fill=darken(col, 0.5))
    base.alpha_composite(small, (52, 34))
    serial = f"{chr(65 + rr.randint(0, 25))}{chr(65 + rr.randint(0, 25))} {rr.randint(1000000, 9999999)}"
    paste_center(base, stext(serial, 30, fill=(200, 30, 40)), NW - 150, 60)
    paste_center(base, stext(serial, 30, fill=(200, 30, 40)), 190, NH - 46)
    lab = stext("COUNTRY:", 30, fill=(255, 255, 255), stroke=3, stroke_fill=darken(col, 0.5))
    base.alpha_composite(lab, (440, NH - 74))
    d.rectangle((388, 0, 420, NH), fill=(205, 210, 220, 210))       # security strip (shimmer drawn later)
    m = note_mask()
    base.putalpha(Image.fromarray(np.minimum(np.asarray(base.getchannel("A")), np.asarray(m))))
    return base


def note_back(r):
    """The back: the country's flag with its name."""
    code, fcode, cname = r[:3]
    fl = Image.open(os.path.join(FLAG_DIR, fcode + ".png")).convert("RGBA").resize((NW, NH), Image.LANCZOS)
    d = ImageDraw.Draw(fl, "RGBA")
    d.rounded_rectangle((16, 16, NW - 17, NH - 17), 40, outline=(255, 255, 255, 255), width=10)
    size = 108
    while rfont(size).getlength(cname) > NW - 120 and size > 50:
        size -= 4
    paste_center(fl, rtext(cname, size, stroke=10), NW / 2, NH / 2)
    m = note_mask()
    fl.putalpha(m)
    return fl


def name_stamp(cur):
    size = 92
    while sfont(size).getlength(cur) > 460 and size > 44:
        size -= 4
    t = stext(cur, size, fill=STAMP_RED + (255,))
    w, h = t.width + 60, t.height + 40
    s = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(s)
    d.rounded_rectangle((4, 4, w - 5, h - 5), 18, outline=STAMP_RED + (255,), width=7)
    d.rounded_rectangle((14, 14, w - 15, h - 15), 12, outline=STAMP_RED + (160,), width=2)
    s.alpha_composite(t, (30, 20))
    a = np.asarray(s.getchannel("A")).astype(np.float32)        # rubber-stamp speckle
    noise = np.random.default_rng(len(cur) * 7).random(a.shape)
    a *= np.where(noise < 0.12, 0.35, 1.0)
    s.putalpha(Image.fromarray(a.astype(np.uint8)))
    under = Image.new("RGBA", (w + 20, h + 20))
    ImageDraw.Draw(under).rounded_rectangle((10, 10, w + 9, h + 9), 20, fill=(255, 255, 255, 215))
    under.alpha_composite(s, (10, 10))
    return under.rotate(-9, Image.BICUBIC, expand=True)


def question_card():
    a = join(rtext("WHICH COUNTRY USES THIS MONEY?", 50, stroke=6), emoji("💸", 54), gap=10)
    h = join(rtext("CLUES UNLOCK EVERY BEAT", 38, fill=GOLD, stroke=5), emoji("🔓", 40), gap=10)
    pill = rounded_card(h.width + 40, h.height + 12, (h.height + 12) // 2, (40, 20, 70, 255), outline=GOLD + (255,),
                        width=3)
    paste_center(pill, h, pill.width / 2, pill.height / 2)
    card = rounded_card(min(1040, max(a.width, pill.width) + 60), a.height + pill.height + 46, 44, (14, 6, 40, 232),
                        outline=(90, 230, 140, 255), width=5)
    paste_center(card, a, card.width / 2, 20 + a.height / 2)
    paste_center(card, pill, card.width / 2, 27 + a.height + pill.height / 2)
    return card


def sfx_cash():
    """A cash-register cha-ching: two bell strikes and a coin cascade."""
    t = np.arange(int(0.9 * SR)) / SR
    out = np.zeros_like(t)
    for at, f in ((0.0, 2350.0), (0.11, 3150.0)):
        tt = np.clip(t - at, 0, None)
        out += (t >= at) * (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 2.76 * tt)) * np.exp(-tt * 9)
    c = wm.sfx_coins()
    out[int(0.1 * SR):int(0.1 * SR) + len(c)] += c[:len(out) - int(0.1 * SR)] * 0.8
    return out / (np.abs(out).max() + 1e-9)


def sfx_stamp():
    t = np.arange(int(0.25 * SR)) / SR
    thud = np.sin(2 * np.pi * np.cumsum(70 + 160 * np.exp(-t * 40)) / SR) * np.exp(-t * 18)
    n = np.random.default_rng(2).standard_normal(len(t))
    slap = mv.highpass(n, 1200) * np.exp(-t * 60) * 0.6
    return (thud + slap) / 1.6


def sfx_flip():
    t = np.arange(int(0.3 * SR)) / SR
    n = np.random.default_rng(8).standard_normal(len(t))
    flap = (mv.lowpass(n, 4000) - mv.lowpass(n, 500)) * (np.sin(np.pi * np.clip(t / 0.3, 0, 1)) ** 2)
    flap *= 1 + 0.6 * np.sin(2 * np.pi * 28 * t)
    return flap / (np.abs(flap).max() + 1e-9)


def flip_view(front, back, ang):
    """A 3D-ish flip about the vertical axis: squash by |cos|, shade toward the edge, swap faces at 90 deg."""
    c = math.cos(ang)
    img = front if c >= 0 else back
    w = max(2, int(NW * abs(c)))
    sq = img.resize((w, NH), Image.BILINEAR)
    shade = int(110 * (1 - abs(c)))
    if shade > 2:
        sh = Image.new("RGBA", sq.size, (0, 0, 20, shade))
        sh.putalpha(Image.fromarray(np.minimum(np.asarray(sh.getchannel("A")), np.asarray(sq.getchannel("A")))))
        sq.alpha_composite(sh)
    return sq


# ----------------------------------------------------------------------------
# rounds
# ----------------------------------------------------------------------------
class Round(mv.Scene):
    def __init__(self, idx, r, prev_tier, ui, tts):
        super().__init__()
        (code, fcode, cname, sym, cur, denom, col, hint, hem, fact, femoji, tier, prompt, said, stick) = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        v_q = tts.say(prompt, speed=1.15) if tts else None
        v_a = tts.say(said, speed=1.12) if tts else None
        q_len = len(v_q) / SR if v_q is not None else 1.4
        c0 = max(5 if self.bonus else 4, math.ceil((0.15 + q_len - 0.05) / B))
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.reveal = (c0 + n) * B
        self.p2 = 1.05                                       # the whip to the globe
        self.dur = math.ceil((self.reveal + self.p2 + 2.6) / B) * B
        self.cta_at = self.p2 + 1.9
        if self.cta:
            self.dur = math.ceil((self.reveal + self.cta_at + 3.0) / B) * B
        self.stamp_at = self.count_beats[0] * B
        self.hint_at = self.count_beats[1] * B
        self.glitch_at = self.count_beats[2] * B
        self.front = note_front(r, idx * 11)
        self.back = note_back(r)
        self.stamp = name_stamp(cur)
        self.col = col
        self.cname = cname
        hb = join(rtext(f"HINT: {hint}", 50, fill=GOLD, stroke=6), emoji(hem, 54), gap=12)
        self.hint = rounded_card(hb.width + 50, hb.height + 22, (hb.height + 22) // 2, (12, 10, 30, 240),
                                 outline=GOLD + (255,), width=5)
        paste_center(self.hint, hb, self.hint.width / 2, self.hint.height / 2)
        self.shadow = Image.new("RGBA", (NW + 80, NH + 80))
        ImageDraw.Draw(self.shadow).rounded_rectangle((40, 50, 40 + NW, 50 + NH), 40, fill=(0, 0, 10, 170))
        self.shadow = self.shadow.filter(ImageFilter.GaussianBlur(18))
        self.redact = {}
        self.country_txt = stext(cname, 34, fill=(255, 255, 255), stroke=3, stroke_fill=darken(col, 0.5))
        # globe
        world = ui["globe"].world
        self.target = world.codes.index(code)
        cc, near, _ = world.country(code)
        near = list(near)
        main = max(near, key=lambda i: world.lens[i])
        mp_ = world.P[world.starts[main]:world.starts[main] + world.lens[main]].mean(0)
        mp_ /= np.linalg.norm(mp_)

        def close(i):
            q = world.P[world.starts[i]:world.starts[i] + world.lens[i]].mean(0)
            return float(q @ mp_) / np.linalg.norm(q) > math.cos(math.radians(18))
        self.near = np.array([i for i in near if close(i)])
        self.gc = cc
        self.gR = float(np.clip(G.zoom_for(world, cc, self.near, W, H, 0.36, 0.22), 600, 9000))
        lon_c = math.degrees(math.atan2(cc[1], cc[0]))
        lat_c = math.degrees(math.asin(max(-1.0, min(1.0, float(cc[2])))))
        self.g_from = G.unit(lon_c - 70, lat_c * 0.4)
        self.flag = Image.open(os.path.join(FLAG_DIR, fcode + ".png")).convert("RGBA")
        self.cols = mm.flag_colours(self.flag)
        self.tiles = mm.Tiles(cname, tier in ("HARD", "INSANE", "IMPOSSIBLE", "BONUS"))
        fs = 42
        while rfont(fs).getlength(fact) > 780 and fs > 26:
            fs -= 1
        fb = join(emoji(femoji, 52), rtext(fact, fs, stroke=0), gap=14)
        self.fact = rounded_card(fb.width + 56, fb.height + 22, (fb.height + 22) // 2, INK + (232,))
        paste_center(self.fact, fb, self.fact.width / 2, self.fact.height / 2)
        self.sticker = emoji(stick, 140)
        self.tcol, e = TIERS[tier]
        self.count = rtext("BONUS" if self.bonus else f"{idx}/10", 46, fill=GOLD if self.bonus else (255, 255, 255),
                           stroke=5)
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, self.tcol + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.level_up = tier != prev_tier and idx > 1
        self.banner = None
        if self.level_up:
            label = "BONUS: ONLY 1% KNOW THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 66 if self.bonus else 100, fill=self.tcol, stroke=10), emoji(e, 96))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        self.badge_q = mv.circle(140, (255, 255, 255, 255))
        ImageDraw.Draw(self.badge_q).text((70, 74), "?", font=rfont(96), fill=INK, anchor="mm")
        self.badges = {}
        for k in range(1, n + 1):
            bd = mv.circle(140, (255, 255, 255, 255))
            ImageDraw.Draw(bd).text((70, 74), str(k), font=rfont(100), fill=(235, 60, 75) if k == 1 else INK,
                                    anchor="mm")
            self.badges[k] = bd
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        # sounds
        self.sounds += [(0.0, mq.sfx_boom(), 0.8), (0.0, mv.sfx_whoosh(0.45), 0.8), (0.05, sfx_flip(), 0.7),
                        (0.22, sfx_flip(), 0.5), (0.4, wm.sfx_coins(), 0.5)]
        self.sounds += [(self.stamp_at, sfx_stamp(), 1.0), (self.hint_at, mv.sfx_pop(), 0.8),
                        (self.hint_at, mv.sfx_whoosh(0.3), 0.5), (self.glitch_at, mq.sfx_glitch(), 0.6)]
        for j, b in enumerate(self.count_beats):
            self.sounds.append((b * B, mq.sfx_tock(high=j == n - 1), 0.9))
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.85))
        if self.danger:
            self.sounds.append((self.count_beats[-1] * B, mq.sfx_boom(), 0.6))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        rv0, p2 = self.reveal, self.reveal + self.p2
        self.sounds += [(rv0, mq.sfx_boom(), 1.0), (rv0, sfx_flip(), 0.9), (rv0 + 0.12, sfx_cash(), 1.0),
                        (p2, mv.sfx_whoosh(0.6), 0.9), (p2, mq.sfx_glitch(), 0.4), (p2 + 0.55, mq.sfx_boom(), 0.6),
                        (p2 + 0.6, wm.sfx_coins(), 0.8), (p2 + 0.62, mq.sfx_pling(), 0.6),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        for i in range(len(self.tiles.pos)):
            self.sounds.append((rv0 + 0.1 + 0.035 * i, mv.sfx_click(), 0.45))
        if tts:
            self.voices.append((0.15, v_q))
            self.voices.append((rv0 + 0.1, v_a))
            if self.cta:
                self.voices.append((rv0 + self.cta_at, tts.say(CTA_LINE, speed=1.12)))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = rv0 + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, mq.sfx_pling(), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        rr = random.Random(idx * 71)
        self.coins = [(rr.uniform(0, 2 * math.pi), rr.uniform(500, 1400), rr.choice(ui["cash"]), rr.uniform(-500, 500))
                      for _ in range(26)]
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1300, -450), rr.randint(12, 26), rr.choice(self.cols),
                      rr.uniform(0, 3)) for _ in range(60)]

    def front_at(self, t, T):
        """The front of the note with the stamp, the shimmering strip and the COUNTRY line for this moment."""
        f = self.front.copy()
        d = ImageDraw.Draw(f, "RGBA")
        ph = (T * 1.7) % 1.0                                 # holographic strip shimmer
        for y in range(0, NH, 6):
            hue = (y / NH + ph) % 1.0
            rgb = tuple(int(255 * (0.55 + 0.45 * math.sin(2 * math.pi * (hue + o)))) for o in (0, 0.33, 0.66))
            d.rectangle((388, y, 420, y + 6), fill=rgb + (120,))
        gx = int((T * 600) % (NW + 400)) - 200               # a light sweep across the note
        sweep = Image.new("RGBA", (NW, NH))
        ImageDraw.Draw(sweep).polygon([(gx, 0), (gx + 70, 0), (gx - 90, NH), (gx - 160, NH)], fill=(255, 255, 255, 40))
        sweep.putalpha(Image.fromarray(np.minimum(np.asarray(sweep.getchannel("A")),
                                                  np.asarray(f.getchannel("A")))))
        f.alpha_composite(sweep)
        x0, y0 = 610, NH - 76                                 # COUNTRY: ████, glitching on the last beats
        bw = min(NW - 60 - x0, 26 + 17 * len(self.cname))
        if t >= self.glitch_at and int(t * 20) % 3 != 0:
            rr = random.Random(int(t * 20))
            txt = "".join(rr.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ#@%?") for _ in self.cname)
            key = txt
            if key not in self.redact:
                self.redact[key] = stext(txt, 34, fill=(255, 255, 255), stroke=3, stroke_fill=darken(self.col, 0.5))
            d.rectangle((x0 - 6, y0 - 4, x0 + bw, y0 + 44), fill=(10, 10, 20, 200))
            f.alpha_composite(scaled(self.redact[key], min(1.0, bw / max(1, self.redact[key].width))), (x0, y0))
        else:
            d.rounded_rectangle((x0 - 6, y0 - 2, x0 + bw, y0 + 42), 6, fill=(10, 10, 20, 255))
        if t >= self.stamp_at:                               # the name stamp slams on
            ks = clamp((t - self.stamp_at) / 0.12)
            st = scaled(self.stamp, 1.8 - 0.8 * ease_out_cubic(ks))
            paste_center(f, st, 390, 190, min(1.0, ks * 1.5))
        return f

    def note_image(self, t, T, rv):
        if rv <= 0:
            k = clamp(t / 0.45)
            ang = (1 - ease_out_cubic(k)) * 4 * math.pi       # spins in, two full flips
            return flip_view(self.front_at(t, T), self.back, ang) if k < 1 else self.front_at(t, T)
        k = ease_in_out(clamp(rv / 0.35))
        if k < 1:
            return flip_view(self.front_at(t, T), self.back, math.pi * k)
        return self.back

    def globe_view(self, t2):
        k = ease_in_out(clamp(t2 / 0.85))
        c = G.slerp(self.g_from, self.gc, k)
        R = math.exp(math.log(470) + (math.log(self.gR) - math.log(470)) * k)
        return c, R * (1 + 0.04 * clamp((t2 - 0.85) / 3)), (1 - clamp(abs(k - 0.5) * 2)) if t2 < 0.85 else 0.0

    def render(self, t, header=True):
        T = self.t0 + t
        rv = t - self.reveal
        t2 = rv - self.p2
        ui = self.ui
        if t2 < 0.25:
            im = ui["bg"].render(T * 1.6, strobe=0.35 * beat_pulse(T) + (0.8 * (1 - clamp(rv / 0.25)) if rv > 0 else 0))
            if self.danger and 0 < t < self.reveal:
                im.alpha_composite(ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        else:
            im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        hl_c = None
        if t2 > 0:                                           # the globe zooms in from space
            c, R, blur = self.globe_view(t2)
            hl = clamp((t2 - 0.55) / 0.2)
            fa = 0.95 * clamp((t2 - 0.6) / 0.3)
            lift = 16 * ease_out_back(clamp((t2 - 0.7) / 0.3))
            g = ui["globe"].render(c, R, GC, self.near if hl > 0 else None, hl, self.flag, fa, lift=lift)
            ui["cmap"].draw(g, c, R, GC, self.target if hl > 0 else None, 0.75 * (1 - 0.4 * hl), 0.0, lift=lift)
            g = mm.zoom_blur(g, blur)
            g.alpha_composite(ui["shade"])
            ga = clamp(t2 / 0.25)
            if ga < 1:
                g.putalpha(g.getchannel("A").point(lambda v, a=ga: int(v * a)))
            im.alpha_composite(g)
            if hl > 0:
                hl_c = getattr(ui["globe"], "last_hl_center", GC)
            if t2 < 0.5:
                im.alpha_composite(cq.speed_lines(1 - t2 / 0.5, self.idx, GC))
        d = ImageDraw.Draw(im)
        if header:
            paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
            x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
            frac = 1.0 if t < 0.3 else max(0.0, 1 - (t - 0.3) / (self.reveal - 0.3))
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
        qa = 1 - clamp(t2 / 0.3)
        if kc > 0.01 and qa > 0.01:
            paste_center(im, scaled(ui["card"], kc * (1 + 0.015 * beat_pulse(T)) * (0.8 + 0.2 * qa)), W / 2, CARD_Y,
                         qa)
        # the banknote
        if t2 <= 0:
            k_in = clamp(t / 0.45)
            s = (0.35 + 0.65 * ease_out_back(k_in, 1.3)) * (1 + 0.012 * beat_pulse(T))
            fy = -700 * (1 - ease_out_cubic(k_in))
            if rv <= 0:
                for b in self.count_beats:
                    tb = t - b * B
                    if 0 <= tb < 0.2:
                        s *= 1 + 0.05 * (1 - ease_out_cubic(tb / 0.2))
            else:
                s *= 1 + 0.08 * math.sin(math.pi * clamp(rv / 0.35))
            rot = 3 * math.sin(T * 1.3) * clamp((t - 0.45) / 0.3) + (1 - ease_out_cubic(k_in)) * 25
            bob = 10 * math.sin(T * 2.1)
            note = self.note_image(t, T, rv)
            paste_center(im, scaled(self.shadow, s * note.width / NW, ), NOTE_C[0] + 16, NOTE_C[1] + 30 + fy)
            sp = scaled(note, s)
            if abs(rot) > 0.05:
                sp = sp.rotate(rot, Image.BICUBIC, expand=True)
            paste_center(im, sp, NOTE_C[0], NOTE_C[1] + fy + bob)
            if rv <= 0 and t > 0.45:                          # countdown badge on the note's corner
                badge = self.badge_q
                for j, b in enumerate(self.count_beats):
                    tb = t - b * B
                    if 0 <= tb < B:
                        badge = scaled(self.badges[len(self.count_beats) - j], 1 + 0.25 * (1 - ease_out_cubic(tb / 0.14)))
                paste_center(im, scaled(badge, 1 + 0.06 * beat_pulse(T)), NOTE_C[0] + NW / 2 - 30,
                             NOTE_C[1] - NH / 2 - 10 + bob)
            if t >= self.hint_at and rv <= 0.9:              # the continent hint slides in
                kh = ease_out_back(clamp((t - self.hint_at) / 0.3), 1.8)
                paste_center(im, scaled(self.hint, max(0.01, kh)), W / 2 + (1 - min(1.0, kh)) * 600, HINT_Y)
        else:
            k = ease_in_out(clamp(t2 / 0.5))
            right = self.side() < W / 2
            tx, ty = (770 if right else 310), 640
            s = 1 + (0.4 - 1) * k
            cx = NOTE_C[0] + (tx - NOTE_C[0]) * k
            cy = NOTE_C[1] + (ty - NOTE_C[1]) * k
            rot = (8 if right else -8) * k + 2 * math.sin(T * 1.5) * k
            paste_center(im, scaled(self.shadow, s), cx + 10, cy + 14)
            paste_center(im, scaled(self.back, s).rotate(rot, Image.BICUBIC, expand=True), cx, cy)
        self.tiles.draw(im, t - 0.6, rv)
        if self.banner is not None and 0.05 < t < 1.0:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - 0.7) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, HINT_Y, a)
        cta_on = self.cta and rv > self.cta_at
        if rv > 0:
            if t2 < 0.4:                                     # money explodes out of the flipped note
                k = clamp((rv - 0.1) / 1.1)
                for ang, sp_, spr, spin in self.coins:
                    if 0 < k < 1:
                        x = NOTE_C[0] + math.cos(ang) * sp_ * k
                        y = NOTE_C[1] + math.sin(ang) * sp_ * k * 0.8 + 900 * k * k
                        paste_center(im, spr.rotate(spin * k, Image.BICUBIC, expand=True), x, y, 1 - k)
            if hl_c is not None and t2 > 0.6:                # money bursts out of the country
                kc_ = t2 - 0.6
                cx_, cy_ = hl_c
                for vx, vy, sz, cc, spin in self.conf:
                    px, py = cx_ + vx * kc_, cy_ + vy * kc_ + 2400 * kc_ * kc_
                    if py < H:
                        w2 = sz * abs(math.cos(spin + kc_ * 9))
                        dd = ImageDraw.Draw(im)
                        dd.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                     outline=INK + (255,))
                kk = clamp(kc_ / 1.1)
                for ang, sp_, spr, spin in self.coins[:14]:
                    if kk < 1:
                        x = cx_ + math.cos(ang) * sp_ * 0.7 * kk
                        y = cy_ + math.sin(ang) * sp_ * 0.6 * kk + 700 * kk * kk
                        paste_center(im, scaled(spr, 0.8).rotate(spin * kk, Image.BICUBIC, expand=True), x, y, 1 - kk)
            sk = ease_out_back((rv - 0.4) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             940 if self.side() < W / 2 else 140, 1480)
            fk = ease_out_back((t2 - 1.0) / 0.3)
            if fk > 0.01 and not cta_on:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            if 0 < t2 < 0.2:
                im = rgb_split(mm.zoom_blur(im, 0.7 * (1 - t2 / 0.2)), 20 * (1 - t2 / 0.2))
            if 0.55 < t2 < 0.8:
                im = shake(im, 18 * (1 - (t2 - 0.55) / 0.25), t)
            if t2 <= 0:
                fl = 1 - clamp(rv / 0.14)
                if fl > 0:
                    im.alpha_composite(Image.new("RGBA", (W, H), (255, 240, 180, int(200 * fl))))
                im = shake(im, 30 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
                if rv < 0.18:
                    im = rgb_split(im, 18 * (1 - rv / 0.18))
        else:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 14 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 12 * (1 - tb / 0.15))
            if 0 <= t - self.stamp_at < 0.1:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 70)))
            tb = t - self.count_beats[-1] * B
            if self.danger and 0 <= tb < 0.2:
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
        if t < 0.12:
            im = rgb_split(mm.zoom_blur(im, 0.6 * (1 - t / 0.12)), 16 * (1 - t / 0.12))
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(mm.zoom_blur(im, 0.6 * out), 20 * out)
        return im

    def side(self):
        """Where the country ends up on screen (so the note flies to the other side)."""
        return GC[0]


# ----------------------------------------------------------------------------
# intro: show the game first
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    """8 beats. Frame one is already a question: the bonus banknote with its "?" badge under GUESS THE COUNTRY /
    FROM ITS MONEY (each line slams in as the narrator says it), with "answer at the end" below; its name
    stamps on and the hint slides in so viewers see how the clues work; then a montage of four more notes
    spinning in under ONLY 1% GET 10/10; then CAN YOU? over the money rain with notes fanning out."""
    HOOK, MONTAGE = 10, (9, 7, 4, 2)

    def __init__(self, ui, tts, rounds):
        super().__init__()
        self.ui, self.rounds = ui, rounds
        self.dur = 8 * B
        hb = 0.5 * B
        clips = [tts.say(w, speed=1.25) for w in INTRO_WORDS] if tts else None
        lens = [len(c) / SR for c in clips] if clips else [0.8, 0.85, 1.45]
        self.slams = [0.0]
        for ln in lens[:2]:
            prev = self.slams[-1]
            self.slams.append(max(prev + hb, math.ceil((prev + ln - 0.04) / hb - 1e-6) * hb))
        self.slams.append(self.dur - 0.75)
        if clips:
            for at, c in zip(self.slams, clips):
                self.voices.append((at, c))
        s0, s1, s2, s3 = self.slams
        self.cut = (s3 - s2) / len(self.MONTAGE)
        self.c1 = fit(rtext("GUESS THE COUNTRY", 112, stroke=11), 900)
        self.c2 = fit(join(rtext("FROM ITS MONEY", 104, fill=(90, 230, 140), stroke=10), emoji("💸", 92), gap=12), 900)
        self.c3 = fit(join(rtext("ONLY 1% GET 10/10", 112, fill=PINK, stroke=11), emoji("💀", 104), gap=12), 900)
        self.c4 = fit(rtext("10 COUNTRIES · 10 BANKNOTES", 60, fill=(255, 255, 255), stroke=7), 900)
        self.o3 = join(rtext("answer at the end", 60, fill=GOLD, stroke=7), emoji("👀", 64))
        self.l1 = fit(rtext("GUESS THE COUNTRY", 112, stroke=11), 990)
        self.l2 = fit(join(rtext("BY ITS MONEY", 104, fill=(90, 230, 140), stroke=10), emoji("💸", 92), gap=12), 990)
        self.l3 = join(rtext("CAN YOU?", 170, fill=PINK, stroke=15), emoji("👀", 150), gap=14)
        self.minis = [scaled(r.front, 0.34).rotate(random.Random(i).uniform(-14, 14), Image.BICUBIC, expand=True)
                      for i, r in enumerate(rounds[:8])]
        hk = rounds[self.HOOK]
        self.stamp_t, self.hint_t = s1, s1 + max(hb, (s2 - s1) / 2)
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, sfx_flip(), 0.8), (0.05, wm.sfx_coins(), 0.6),
                        (0.02, sfx_heartbeat(), 0.8), (self.stamp_t, sfx_stamp(), 1.0), (self.hint_t, mv.sfx_pop(), 0.8),
                        (s2, mq.sfx_boom(), 0.9), (s2, mq.sfx_glitch(), 0.5),
                        (s3 - 0.9, mv.sfx_riser(0.9), 0.6), (s3, mq.sfx_boom(), 1.0), (s3, sfx_cash(), 0.9),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for j in range(len(self.MONTAGE)):
            at = s2 + j * self.cut
            self.sounds += [(at, sfx_flip(), 0.7), (at, mv.sfx_click(), 0.6)]
        self.hook = hk

    def render(self, t):
        T = self.t0 + t
        s0, s1, s2, s3 = self.slams
        slam_at = max(at for at in self.slams if at <= t + 1e-9)
        ts = t - slam_at
        slam = 1 + (0.12 if slam_at == 0 else 0.3) * (1 - ease_out_cubic(clamp(ts / 0.18)))
        im = self.ui["bg"].render(T * 1.6, strobe=0.35 * beat_pulse(T))
        if t < s3:
            if t < s2:                                       # the hook: one note, clues unlocking
                r = self.hook
                f = r.front.copy()
                if t >= self.stamp_t:
                    ks = clamp((t - self.stamp_t) / 0.12)
                    paste_center(f, scaled(r.stamp, 1.8 - 0.8 * ease_out_cubic(ks)), 390, 190, min(1.0, ks * 1.5))
                ang = 0.0
                ky = 0.0
            else:
                j = min(len(self.MONTAGE) - 1, int((t - s2) / self.cut))
                r = self.rounds[self.MONTAGE[j]]
                f = r.front.copy()
                paste_center(f, r.stamp, 390, 190)
                ct = t - s2 - j * self.cut
                ang = (1 - ease_out_cubic(clamp(ct / 0.18))) * 2 * math.pi
                ky = 0.0
            note = flip_view(f, r.back, ang) if ang > 0.01 else f
            s = 1.0 + 0.012 * beat_pulse(T)
            if t >= self.stamp_t and t < s2 and t - self.stamp_t < 0.2:
                s *= 1 + 0.05 * (1 - ease_out_cubic((t - self.stamp_t) / 0.2))
            paste_center(im, scaled(r.shadow, s * note.width / NW), NOTE_C[0] + 16, NOTE_C[1] + 30)
            paste_center(im, scaled(note, s).rotate(3 * math.sin(T * 1.3), Image.BICUBIC, expand=True), NOTE_C[0],
                         NOTE_C[1] + ky)
            paste_center(im, scaled(r.badge_q, 1 + 0.08 * beat_pulse(T)), NOTE_C[0] + NW / 2 - 30, NOTE_C[1] - NH / 2 - 10)
            if t < s2:
                paste_center(im, scaled(self.c1, slam if slam_at == s0 else 1.0).rotate(-2, Image.BICUBIC, expand=True),
                             W / 2, 330)
                if t >= s1:
                    paste_center(im, scaled(self.c2, slam if slam_at == s1 else 1.0).rotate(2, Image.BICUBIC,
                                                                                         expand=True), W / 2, 480)
                if t >= self.hint_t:
                    kh = ease_out_back(clamp((t - self.hint_t) / 0.3), 1.8)
                    paste_center(im, scaled(r.hint, max(0.01, kh)), W / 2 + (1 - min(1.0, kh)) * 600, HINT_Y)
            else:
                paste_center(im, scaled(self.c3, slam if slam_at == s2 else 1.0).rotate(-2, Image.BICUBIC,
                                                                                     expand=True), W / 2, 330)
                paste_center(im, self.c4, W / 2, 465)
            paste_center(im, scaled(self.o3, 1 + 0.04 * beat_pulse(T)), W / 2, 1720)
            im = shake(im, 22 * (1 - ts / 0.25) if ts < 0.25 else 0, t)
            if 0 <= t - self.stamp_t < 0.12 and t < s2:
                im = rgb_split(im, 12 * (1 - (t - self.stamp_t) / 0.12))
            if t >= s2:
                ct = (t - s2) % self.cut
                if ct < 0.1:
                    im = rgb_split(mm.zoom_blur(im, 0.5 * (1 - ct / 0.1)), 14 * (1 - ct / 0.1))
                    if ct < 0.05:
                        im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 110)))
            return im
        tc = t - s3                                          # the challenge, notes fanning out
        spots = [(200, 980), (880, 980), (180, 1300), (900, 1300), (230, 1620), (850, 1620), (420, 1800), (660, 1800)]
        for j, (mini, (x, y)) in enumerate(zip(self.minis, spots)):
            kf = ease_out_back(clamp((tc - 0.03 * j) / 0.4), 1.4)
            paste_center(im, scaled(mini, max(0.01, 0.4 + 0.6 * min(1.0, kf))), W / 2 + (x - W / 2) * kf,
                         1300 + (y - 1300) * kf)
        k = 1 + 0.12 * (1 - ease_out_cubic(clamp(tc / 0.18)))
        paste_center(im, scaled(self.l1, k).rotate(-3, Image.BICUBIC, expand=True), W / 2, 330)
        paste_center(im, scaled(self.l2, k).rotate(2, Image.BICUBIC, expand=True), W / 2, 480)
        paste_center(im, scaled(self.l3, slam * (1 + 0.04 * beat_pulse(T))).rotate(-3, Image.BICUBIC, expand=True),
                     W / 2, 680)
        im = shake(im, 22 * (1 - tc / 0.3) if tc < 0.3 else 0, t)
        if tc < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - tc / 0.08)))))
        whip = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
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
    ui = {"globe": globe, "big_globe": globe, "bg": wm.MoneyRain(), "shade": mm.shade_overlay(0.7),
          "vig": [mc.red_vignette(i / 10) for i in range(11)], "cmap": mcq.ColourMap(world), "card": question_card(),
          "cash": [emoji(e, s) for e in ("💵", "🪙", "💰", "💸") for s in (90, 120)]}
    rounds, prev = [], ROUNDS[0][11]
    for i, r in enumerate(ROUNDS, 1):
        rounds.append(Round(i, r, prev, ui, tts))
        prev = r[11]
    intro = Intro(ui, tts, rounds)
    scenes = [intro, *rounds, bq.Ending(ui, intro, tts)]
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(scenes, ui, path):
    rounds = [s for s in scenes if isinstance(s, Round)]
    im = ui["bg"].render(2.0, strobe=0.2)
    spots = [(2, 290, 900, -12), (0, 790, 880, 10), (9, 300, 1330, 8), (10, 790, 1350, -9)]
    for k, x, y, rot in spots:
        r = rounds[k]
        f = r.front.copy()
        paste_center(f, r.stamp, 390, 190)
        paste_center(im, scaled(r.shadow, 0.5), x + 10, y + 14)
        paste_center(im, scaled(f, 0.5).rotate(rot, Image.BICUBIC, expand=True), x, y)
    paste_center(im, mv.circle(170, (255, 255, 255, 255)), W / 2, 1120)
    q = rtext("?", 140, fill=INK, stroke=0)
    paste_center(im, q, W / 2, 1126)
    paste_center(im, fit(rtext("GUESS THE COUNTRY", 112, stroke=11), 1000).rotate(-3, Image.BICUBIC, expand=True),
                 W / 2, 250)
    paste_center(im, fit(join(rtext("BY ITS MONEY", 120, fill=(90, 230, 140), stroke=11), emoji("💸", 110), gap=12),
                         1000).rotate(2, Image.BICUBIC, expand=True), W / 2, 420)
    paste_center(im, join(rtext("99% FAIL", 104, fill=PINK, stroke=10), emoji("💀", 104)), W / 2, 1720)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_money_country_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--music", default="phonk", choices=["phonk", "none"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    quiet = a.stills or a.cover
    scenes, starts, total, ui = build(a.voice if not quiet else "none", None if quiet else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    if a.cover:
        make_cover(scenes, ui, os.path.join(HERE, "money_country_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"money_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_money_country")
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
