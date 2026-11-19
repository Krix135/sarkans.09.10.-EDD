#!/usr/bin/env python3
""""ODD ONE OUT" geography Short (1080x1920): four flags, one doesn't belong.

Each round the four flag cards fly in from the corners, the question card gives a hint ("HINT: CONTINENTS"),
and a 3-2-1 runs inside the centre badge. During the countdown a highlight spins round the cards like a
roulette wheel (fast, then slowing down) and lands on the odd one exactly on the drop: that card turns
red with an ODD ONE OUT stamp and shakes, the other three get a green check, and the rule pops up
("3 ARE IN EUROPE / Canada is in North America"). Spoken-title intro (6 beats), EASY -> IMPOSSIBLE plus a
bonus, one like call-out after round 3, looping score screen. Flags: public domain.

    python3 make_odd_one_out_quiz.py
    python3 make_odd_one_out_quiz.py --stills 0,5,9
    python3 make_odd_one_out_quiz.py --cover
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

from PIL import Image, ImageDraw  # noqa: E402

import globe as G  # noqa: E402
import make_bigger_country_quiz as bq  # noqa: E402
import make_club_quiz as cq  # noqa: E402
import make_logo_quiz as lq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_missing_country_quiz as mcq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center, \
    rounded_card, scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
CARD_Y = 465
GRID_X = (280, 800)
GRID_Y = (855, 1215)
GRID_C = (540, 1035)                  # the countdown badge sits where the four cards meet
RULE_Y = 1530
CTA_Y = 1665
CW, CH = 490, 330
ENTRY_BEATS = 2
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
GREEN, RED = (46, 204, 113), (235, 60, 75)
COLS = {"A": PINK, "B": CYAN, "C": GOLD, "D": (170, 110, 255)}
ORDER = (0, 1, 3, 2)                 # clockwise round the grid, for the roulette

NAMES = {
    "FR": "FRANCE", "CA": "CANADA", "DE": "GERMANY", "IT": "ITALY", "CH": "SWITZERLAND", "UA": "UKRAINE",
    "PL": "POLAND", "BR": "BRAZIL", "ES": "SPAIN", "MX": "MEXICO", "CO": "COLOMBIA", "AT": "AUSTRIA",
    "HU": "HUNGARY", "HR": "CROATIA", "JP": "JAPAN", "NO": "NORWAY", "IS": "ICELAND", "NZ": "NEW ZEALAND",
    "CN": "CHINA", "VN": "VIETNAM", "KR": "SOUTH KOREA", "CL": "CHILE", "US": "USA", "GB": "UK",
    "AU": "AUSTRALIA", "IN": "INDIA", "TR": "TURKEY", "SE": "SWEDEN", "FI": "FINLAND", "DK": "DENMARK",
    "KE": "KENYA", "NG": "NIGERIA", "ID": "INDONESIA", "BO": "BOLIVIA", "PH": "PHILIPPINES", "AR": "ARGENTINA",
}
ROUNDS = [  # flags A-D (grid order), odd one, hint, hint emoji, rule, detail, rule emoji, tier, prompt, answer, sticker
    (("FR", "CA", "DE", "IT"), 1, "CONTINENTS", "🌍", "3 ARE IN EUROPE", "Canada is in North America", "🌍", "EASY",
     "Which one doesn't belong? Hint: continents!", "Canada! The others are in Europe!", "😎"),
    (("CA", "CH", "UA", "PL"), 2, "FLAG COLOURS", "🎨", "3 FLAGS ARE RED & WHITE", "Ukraine's is blue and yellow",
     "🎨", "EASY", "Hint: flag colours!", "Ukraine! The others are red and white!", "🔥"),
    (("BR", "ES", "MX", "CO"), 0, "LANGUAGE", "🗣", "3 SPEAK SPANISH", "Brazil speaks Portuguese", "🗣", "EASY",
     "Hint: language!", "Brazil! It speaks Portuguese!", "🤔"),
    (("CH", "AT", "HU", "HR"), 3, "THE SEA", "🌊", "3 HAVE NO SEA", "Croatia has a long coast", "🌊", "MEDIUM",
     "Hint: the sea!", "Croatia! The others have no sea!", "😳"),
    (("JP", "NO", "IS", "NZ"), 1, "ISLANDS", "🏝", "3 ARE ISLAND COUNTRIES", "Norway is on the mainland", "🏝",
     "MEDIUM", "Hint: islands!", "Norway! It's not an island!", "🤯"),
    (("CN", "VN", "KR", "CL"), 2, "LOOK AT THE FLAGS", "👀", "3 FLAGS HAVE A STAR", "South Korea's has a circle", "⭐",
     "MEDIUM", "Hint: look at the flags!", "South Korea! No star on its flag!", "🔥"),
    (("US", "GB", "AU", "IN"), 0, "DRIVING", "🚗", "3 DRIVE ON THE LEFT", "the USA drives on the right", "🚗", "HARD",
     "Hint: driving!", "The USA! It drives on the right!", "😱"),
    (("AU", "CA", "TR", "FR"), 3, "CAPITAL CITIES", "🏙", "3 CAPITALS AREN'T THE BIGGEST CITY",
     "in France, Paris is the biggest", "🏙", "HARD", "Hint: capital cities!", "France! Paris is its biggest city!",
     "💀"),
    (("SE", "FI", "NO", "DK"), 1, "WHO'S IN CHARGE", "🏛", "3 HAVE A KING", "Finland has a president", "👑", "INSANE",
     "Hint: who's in charge!", "Finland! It has a president, not a king!", "🧠"),
    (("BR", "KE", "NG", "ID"), 2, "THE EQUATOR", "🌐", "3 CROSS THE EQUATOR", "Nigeria is fully north of it", "🌐",
     "IMPOSSIBLE", "Hint: the equator!", "Nigeria! It doesn't touch the equator!", "☠"),
    (("CO", "BO", "PH", "AR"), 3, "THE NAMES", "📛", "3 ARE NAMED AFTER A PERSON",
     "Argentina is named after silver", "🥈", "BONUS", "Bonus! Hint: the names!",
     "Argentina! It's named after silver!", "👑"),
]
INTRO_WORDS = ("Odd one out!", "Only one percent", "get them all!")


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


class OddWall(lq.BrandWall):
    EMOJIS = ["🤔", "❓", "🌍", "🚩", "🧩", "🗺", "👀", "🌎"]


def flag_card(code, letter, state=None):
    """A flag with its name. state: None, "ok" (belongs: green check) or "odd" (red, the odd one out)."""
    fill = {None: INK + (238,), "ok": (18, 70, 44, 245), "odd": (120, 16, 34, 250)}[state]
    edge = {None: COLS[letter], "ok": GREEN, "odd": RED}[state]
    card = rounded_card(CW, CH, 40, fill, outline=edge + (255,), width=7)
    fl = Image.open(os.path.join(FLAG_DIR, code + ".png")).convert("RGBA")
    fl.thumbnail((410, 220), Image.LANCZOS)
    fb = Image.new("RGBA", (fl.width + 12, fl.height + 12), (255, 255, 255, 255))
    fb.paste(fl, (6, 6), fl)
    paste_center(card, fb, CW / 2, 26 + 116)
    name = NAMES[code]
    size = 52
    while rfont(size).getlength(name) > CW - 60 and size > 30:
        size -= 2
    paste_center(card, rtext(name, size, stroke=6), CW / 2, CH - 46)
    badge = mv.circle(70, ((COLS[letter] if state is None else edge)) + (255,))
    ImageDraw.Draw(badge).text((35, 37), letter, font=rfont(44), fill=(255, 255, 255), anchor="mm")
    card.alpha_composite(badge, (14, 14))
    if state == "ok":
        paste_center(card, emoji("✅", 62), CW - 44, 46)
    return card


def question_card(hint, em):
    a = join(rtext("WHICH ONE DOESN'T BELONG?", 54, stroke=6), emoji("🤔", 56), gap=10)
    h = join(rtext(f"HINT: {hint}", 46, fill=GOLD, stroke=5), emoji(em, 48), gap=10)
    pill = rounded_card(h.width + 44, h.height + 14, (h.height + 14) // 2, (40, 20, 70, 255), outline=GOLD + (255,),
                        width=3)
    paste_center(pill, h, pill.width / 2, pill.height / 2)
    w = max(a.width, pill.width) + 70
    card = rounded_card(min(1040, w), a.height + pill.height + 52, 46, (14, 6, 40, 232), outline=CYAN + (255,),
                        width=5)
    paste_center(card, a, card.width / 2, 22 + a.height / 2)
    paste_center(card, pill, card.width / 2, 30 + a.height + pill.height / 2)
    return card


def rule_banner(rule, detail, em):
    r_size = 60
    while rfont(r_size).getlength(rule) > 820 and r_size > 38:
        r_size -= 2
    top = join(emoji(em, r_size + 4), rtext(rule, r_size, fill=GREEN, stroke=6), gap=12)
    bot = rtext(detail, 40, fill=(230, 230, 240), stroke=4)
    w = max(top.width, bot.width) + 70
    card = rounded_card(min(1050, w), top.height + bot.height + 40, 44, (12, 10, 30, 242), outline=GREEN + (255,),
                        width=5)
    paste_center(card, top, card.width / 2, 18 + top.height / 2)
    paste_center(card, bot, card.width / 2, 22 + top.height + bot.height / 2 - 4)
    return card


def stamp():
    t = join(rtext("ODD ONE OUT!", 62, fill=(255, 255, 255), stroke=0), emoji("❌", 56), gap=10)
    s = rounded_card(t.width + 46, t.height + 22, 26, RED + (255,), outline=(255, 255, 255, 255), width=5)
    paste_center(s, t, s.width / 2, s.height / 2)
    return s.rotate(-8, Image.BICUBIC, expand=True)


def highlight_frame():
    f = Image.new("RGBA", (CW + 40, CH + 40))
    d = ImageDraw.Draw(f)
    d.rounded_rectangle((4, 4, CW + 35, CH + 35), 52, outline=(255, 255, 255, 255), width=10)
    d.rounded_rectangle((14, 14, CW + 25, CH + 25), 44, outline=GOLD + (255,), width=5)
    return f


# ----------------------------------------------------------------------------
# rounds
# ----------------------------------------------------------------------------
class Round(mv.Scene):
    def __init__(self, idx, r, prev_tier, ui, tts):
        super().__init__()
        flags, odd, hint, hem, rule, detail, rem, tier, prompt, said, stick = r
        self.idx, self.ui, self.tier, self.odd = idx, ui, tier, odd
        self.flags = flags
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = ENTRY_BEATS
        v_q = tts.say(prompt, speed=1.12) if tts else None
        v_a = tts.say(said, speed=1.12) if tts else None
        v_c = tts.say(CTA_LINE, speed=1.1) if (tts and self.cta) else None
        q_len = len(v_q) / SR if v_q is not None else 1.6
        a_len = len(v_a) / SR if v_a is not None else 1.9
        c_len = len(v_c) / SR if v_c is not None else 2.8
        c0 = max(f + 3, math.ceil((0.15 + q_len + 0.2) / B))
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.entry = f * B
        self.reveal = (c0 + n) * B
        self.rule_at = 0.75
        hold = max(5, math.ceil((0.1 + a_len + 0.6) / B), math.ceil((self.rule_at + 1.6) / B))
        self.cta_at = max(5 * B, 0.1 + a_len + 0.3)
        if self.cta:
            hold = max(hold, math.ceil((self.cta_at + c_len + 0.5) / B))
        self.dur = (c0 + n + hold) * B
        self.cards = [flag_card(c, "ABCD"[i]) for i, c in enumerate(flags)]
        self.ok = [flag_card(c, "ABCD"[i], "ok") for i, c in enumerate(flags)]
        self.odd_card = flag_card(flags[odd], "ABCD"[odd], "odd")
        self.card = question_card(hint, hem)
        self.rule = rule_banner(rule, detail, rem)
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
            label = "BONUS: ONLY 1% GET THIS" if self.bonus else f"{tier}!"
            self.banner = join(rtext(label, 62 if self.bonus else 92, fill=self.col, stroke=9), emoji(e, 90))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        self.badge = mv.circle(176, (255, 255, 255, 255))
        ImageDraw.Draw(self.badge).text((88, 92), "?", font=rfont(110), fill=INK, anchor="mm")
        self.ring = mv.circle(214, GOLD + (255,))
        self.nums = {}
        for k in range(1, n + 1):
            bd = mv.circle(176, (255, 255, 255, 255))
            ImageDraw.Draw(bd).text((88, 92), str(k), font=rfont(120), fill=RED if k == 1 else INK, anchor="mm")
            self.nums[k] = bd
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        # the roulette: hops on a 16th-note grid, fast at first and slowing down, landing on the odd one
        K = 16 if self.bonus else 12
        t0, t1 = self.count_beats[0] * B, self.reveal
        q = B / 4
        hops = sorted({round((t0 + (t1 - t0) * (k / K) ** 1.8) / q) * q for k in range(K + 1)})   # slows down
        hops[-1] = t1
        start = next(s for s in range(4) if ORDER[(s + len(hops) - 1) % 4] == odd)
        self.hops = [(at, ORDER[(start + i) % 4]) for i, at in enumerate(hops)]
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8)]
        for i in range(4):
            at = 0.05 + i * 0.1
            self.sounds += [(at + 0.25, mv.sfx_pop(), 0.6), (at + 0.25, mq.sfx_boom(), 0.25)]
        for at, _ in self.hops[:-1]:
            self.sounds.append((at, mv.sfx_click(), 0.7))
        for j, b in enumerate(self.count_beats):
            self.sounds.append((b * B, mq.sfx_tock(high=j == n - 1), 0.9))
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        if self.danger:
            self.sounds.append((self.count_beats[-1] * B, mq.sfx_boom(), 0.6))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        rv0 = self.reveal
        self.sounds += [(rv0, mq.sfx_boom(), 1.0), (rv0, mq.sfx_glitch(), 0.6), (rv0 + 0.03, mv.sfx_ding(), 0.8),
                        (rv0 + 0.3, mq.sfx_pling(), 0.6), (rv0 + self.rule_at, mv.sfx_pop(), 0.8),
                        (rv0 + self.rule_at, mq.sfx_boom(), 0.4), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        for i in range(3):
            self.sounds.append((rv0 + 0.25 + 0.08 * i, mv.sfx_click(), 0.5))
        if tts:
            self.voices.append((0.15, v_q))
            self.voices.append((self.reveal + 0.1, v_a))
            if self.cta:
                self.voices.append((self.reveal + self.cta_at, v_c))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = self.reveal + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, mq.sfx_pling(), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        rr = random.Random(idx * 41)
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1300, -500), rr.randint(12, 26),
                      rr.choice([RED, GOLD, (255, 255, 255), CYAN, PINK]), rr.uniform(0, 3)) for _ in range(60)]

    def lit(self, t):
        """Which card the roulette highlight is on, and how long it has been there."""
        cur = None
        for at, i in self.hops:
            if at <= t:
                cur = (i, t - at)
        return cur

    def render(self, t, header=True):
        T = self.t0 + t
        rv = t - self.reveal
        on_beat = beat_pulse(T) if t > self.entry else 0.0
        im = self.ui["bg"].render(T, self.col, strobe=on_beat * 0.5 + (1 - clamp(rv / 0.25) if rv > 0 else 0),
                                  rays=0.6)
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(Image.new("RGBA", (W, H), (120, 0, 30, 36)))
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        d = ImageDraw.Draw(im)
        if header:
            paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
            x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
            frac = 1.0 if t < self.entry else max(0.0, 1 - (t - self.entry) / (self.reveal - self.entry))
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
        # the four flag cards
        lit = self.lit(t) if rv < 0 else None
        cta_on = self.cta and rv > self.cta_at
        order = [i for i in range(4) if i != self.odd] + [self.odd]       # the odd one on top after the drop
        for i in order:
            gx, gy = GRID_X[i % 2], GRID_Y[i // 2]
            k = clamp((t - 0.05 - i * 0.1) / 0.35)
            if k <= 0:
                continue
            e_ = ease_out_back(k, 1.4)
            sx, sy = (-1 if i % 2 == 0 else 1), (-1 if i < 2 else 1)
            px, py = gx + sx * 700 * (1 - e_), gy + sy * 500 * (1 - e_)
            rot = (1 - e_) * 25 * sx
            if rv <= 0:
                img = self.cards[i]
                s = 1 + 0.012 * on_beat
                if lit and lit[0] == i:
                    s *= 1.05 + 0.04 * (1 - ease_out_cubic(clamp(lit[1] / 0.12)))
                a = 1.0
            elif i == self.odd:
                img = self.odd_card
                s = 1.1 + 0.15 * (1 - ease_out_cubic(clamp(rv / 0.3))) + 0.02 * beat_pulse(T)
                px += 16 * math.sin(rv * 70) * (1 - clamp(rv / 0.45))
                a = 1.0
            else:
                ko = clamp((rv - 0.25 - 0.08 * order.index(i)) / 0.2)
                img = self.ok[i] if ko > 0 else self.cards[i]
                s = 0.95 + 0.06 * (1 - ease_out_cubic(ko)) * (ko > 0)
                a = 1 - 0.25 * ko
            sp = scaled(img, s * (0.6 + 0.4 * e_))
            if rot:
                sp = sp.rotate(rot, Image.BICUBIC, expand=True)
            paste_center(im, sp, px, py, a)
            if lit and lit[0] == i:
                fr = scaled(self.ui["hl"], s)
                paste_center(im, fr, px, py)
        if rv > 0:                                           # stamp, sunburst and shockwaves on the odd one
            gx, gy = GRID_X[self.odd % 2], GRID_Y[self.odd // 2]
            for j in range(3):
                tl = rv - 0.1 * j
                if 0 < tl < 0.55:
                    r_ = 150 + 420 * ease_out_cubic(tl / 0.55)
                    ImageDraw.Draw(im, "RGBA").ellipse((gx - r_, gy - r_, gx + r_, gy + r_),
                                                       outline=RED + (int(255 * (1 - tl / 0.55)),), width=10)
            ks = ease_out_back(clamp((rv - 0.08) / 0.25), 2.4)
            if ks > 0.01:
                paste_center(im, scaled(self.ui["stamp"], 1.6 - 0.6 * ks), gx, gy - CH / 2 + 10, min(1.0, ks))
        # centre badge: ? then the 3-2-1
        if t > 0.4:
            kb = ease_out_back(clamp((t - 0.4) / 0.3), 2.0) * (1 + 0.08 * on_beat)
            fade = 1 - clamp(rv / 0.2) if rv > 0 else 1.0
            if fade > 0.01:
                badge = self.badge
                for j, b in enumerate(self.count_beats):
                    tb = t - b * B
                    if 0 <= tb < B:
                        badge = scaled(self.nums[len(self.count_beats) - j], 1 + 0.15 * (1 - ease_out_cubic(tb / 0.12)))
                paste_center(im, scaled(self.ring, kb * (1 + 0.06 * math.sin(T * 6))), *GRID_C, fade)
                paste_center(im, scaled(badge, kb), *GRID_C, fade)
        if self.banner is not None and 0.05 < t < self.entry + 0.4:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.entry - 0.1) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), *GRID_C, a)
        if rv > 0:
            gx, gy = GRID_X[self.odd % 2], GRID_Y[self.odd // 2]
            for vx, vy, sz, cc, spin in self.conf:
                px, py = gx + vx * rv, gy + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    dd = ImageDraw.Draw(im)
                    dd.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                 outline=INK + (255,))
            kr = ease_out_back(clamp((rv - self.rule_at) / 0.3), 1.8)
            if kr > 0.01 and not cta_on:
                paste_center(im, scaled(self.rule, kr * (1 + 0.015 * beat_pulse(T))), W / 2, RULE_Y)
            sk = ease_out_back((rv - 0.5) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             940, 1690 if not cta_on else 1500)
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(190 * fl))))
            im = shake(im, 30 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 18 * (1 - rv / 0.18))
        else:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 14 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 10 * (1 - tb / 0.15))
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
        if t < 0.16:
            im = rgb_split(mm.zoom_blur(im, 0.6 * (1 - t / 0.16)), 16 * (1 - t / 0.16))
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(im, 20 * out)
        return im


# ----------------------------------------------------------------------------
# intro: the title, said and slammed in word by word
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    TEASE, MONTAGE = 10, (8, 9)

    def __init__(self, ui, tts, rounds):
        super().__init__()
        self.ui, self.rounds = ui, rounds
        self.dur = 6 * B
        hb = 0.5 * B
        clips = [tts.say(w, speed=1.22) for w in INTRO_WORDS] if tts else None
        lens = [len(c) / SR for c in clips] if clips else [0.75, 0.75, 0.7]
        self.slams = [0.0]
        for ln in lens:
            prev = self.slams[-1]
            self.slams.append(max(prev + hb, round((prev + ln - 0.08) / hb) * hb))
        self.slams[-1] = min(self.slams[-1], self.dur - 0.4)
        self.mid = self.slams[0] + max(hb, round(lens[0] * 0.45 / hb) * hb)
        if clips:
            for at, c in zip(self.slams, clips):
                self.voices.append((at, c))
        self.o3 = join(rtext("answer at the end", 58, fill=GOLD, stroke=7), emoji("👀", 62))
        self.w1 = fit(rtext("ODD ONE", 180, fill=(255, 255, 255), stroke=16), 980)
        self.w2 = fit(join(rtext("OUT!", 190, fill=RED, stroke=16), emoji("🤔", 160), gap=16), 980)
        self.w3 = fit(rtext("ONLY 1%", 170, fill=PINK, stroke=15), 980)
        self.w4 = fit(join(rtext("GET THEM ALL", 124, fill=CYAN, stroke=12), emoji("😳", 110), gap=12), 980)
        self.l1 = fit(rtext("ODD ONE OUT", 140, fill=(255, 255, 255), stroke=13), 980)
        self.l2 = fit(join(rtext("WHICH DOESN'T BELONG?", 70, fill=GOLD, stroke=8), emoji("🤔", 70), gap=10), 980)
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
        if k < 3:
            r = self.rounds[(self.TEASE, self.MONTAGE[0], self.MONTAGE[1])[k]]
            im = r.render(r.count_beats[0] * B - 0.1)
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 130)))
            if k == 0:
                im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.5 * beat_pulse(T)))])
                paste_center(im, scaled(self.w1, slam).rotate(-3, Image.BICUBIC, expand=True), W / 2, 880)
                if t >= self.mid:
                    sm = 1 + 0.35 * (1 - ease_out_cubic(clamp((t - self.mid) / 0.18)))
                    paste_center(im, scaled(self.w2, sm * (1 + 0.03 * beat_pulse(T))).rotate(2, Image.BICUBIC,
                                                                                             expand=True), W / 2, 1090)
            else:
                paste_center(im, scaled(self.w3, slam if k == 1 else 1.0).rotate(-3, Image.BICUBIC, expand=True),
                             W / 2, 900)
                if k == 2:
                    paste_center(im, scaled(self.w4, slam).rotate(2, Image.BICUBIC, expand=True), W / 2, 1090)
            paste_center(im, self.o3, W / 2, 1745)
            im = shake(im, 24 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
            im = rgb_split(im, (8 if k == 0 else 16) * (1 - clamp(ts / 0.15)))
            if k > 0:
                im = mm.zoom_blur(im, 0.6 * (1 - clamp(ts / 0.1)))
                if ts < 0.06:
                    im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
            return im
        gc = (540, 1270)
        R = 470 * (1 + 0.05 * beat_pulse(T)) * (1.25 - 0.25 * ease_out_cubic(clamp(ts / 0.3)))
        c = G.unit(10 + 50 * t, 20)
        im = self.ui["big_globe"].render(c, R, gc)
        self.ui["cmap"].draw(im, c, R, gc, None, 0.75 + 0.2 * beat_pulse(T))
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 40)))
        for j, (img, y, rot) in enumerate([(self.l1, 330, -3), (self.l2, 490, 2), (self.l3, 660, -2)]):
            sc = (slam if j == 2 else 1 + 0.12 * (1 - ease_out_cubic(clamp(ts / 0.18)))) * (1 + 0.03 * beat_pulse(T))
            paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
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
    ui = {"bg": OddWall(), "vig": [mc.red_vignette(i / 10) for i in range(11)], "big_globe": globe,
          "cmap": mcq.ColourMap(world), "hl": highlight_frame(), "stamp": stamp()}
    rounds, prev = [], ROUNDS[0][7]
    for i, r in enumerate(ROUNDS, 1):
        rounds.append(Round(i, r, prev, ui, tts))
        prev = r[7]
    intro = Intro(ui, tts, rounds)
    scenes = [intro, *rounds, bq.Ending(ui, intro, tts)]
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(scenes, ui, path):
    r = scenes[1 + 8]                                        # four Nordic-cross flags: which one is different?
    im = r.render(r.count_beats[0] * B - 0.1, header=False)
    paste_center(im, fit(join(rtext("ODD ONE OUT", 120, fill=(255, 255, 255), stroke=12), emoji("🤔", 110), gap=12),
                         1000).rotate(-3, Image.BICUBIC, expand=True), W / 2, 200)
    paste_center(im, join(rtext("99% FAIL", 100, fill=PINK, stroke=10), emoji("💀", 100)), W / 2, 1560)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_odd_one_out_quiz.mp4"))
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
        make_cover(scenes, ui, os.path.join(HERE, "odd_one_out_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"odd_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_odd_one_out")
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
