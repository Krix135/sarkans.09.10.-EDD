#!/usr/bin/env python3
""""GUESS THE CURRENCY!" quiz Short (1080x1920) on the channel logo background.

A spinning gold coin shows a currency symbol; pick A/B/C/D (with look-alike
traps), then see which country uses it. 10 coins fill a collection bar.

    python3 make_currency_quiz.py
    python3 make_currency_quiz.py --stills 2,4 --no-bg
    python3 make_currency_quiz.py --cover
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
from make_video import (SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, font, paste_center,  # noqa: E402
                        radial_glow, rounded_card, scaled, sfx_ding, sfx_pop, sfx_whoosh, tt)

W, H, FPS = 1080, 1920, 30
YELLOW = (255, 222, 40)
T_IN = 0.3
COIN_Y, PROG_Y, OPT_X, OPT_Y0, OPT_DY, TIMER_Y = 610, 345, 500, 905, 112, 1355
OPT_W, OPT_H = 820, 96
COIN = 400
LEVEL_COL = {"EASY": (70, 200, 110), "NORMAL": (60, 160, 255), "MEDIUM": (255, 160, 40), "HARD": (240, 70, 70)}
LETTER_COL = [(255, 95, 95), (70, 150, 255), (255, 190, 40), (90, 200, 120)]

COINS = [  # symbol, answer, level, seconds, line before, spoken answer, country flag, country, 3 wrong, extra, banner
    ("$", "US Dollar", "EASY", 3, "Guess the currency!", "The U.S. dollar!", "🇺🇸", "USA & more",
     ("Japanese Yen", "Swiss Franc", "Chinese Yuan"), None, None),
    ("€", "Euro", "EASY", 3, "Next one.", "The euro!", "🇪🇺", "20+ COUNTRIES",
     ("Swiss Franc", "Swedish Krona", "Norwegian Krone"), None, None),
    ("£", "British Pound", "EASY", 3, "Easy, right?", "The British pound!", "🇬🇧", "UK",
     ("Euro", "Swiss Franc", "Danish Krone"), None, None),
    ("¥", "Japanese Yen", "NORMAL", 4, "Normal level.", "The Japanese yen!", "🇯🇵", "JAPAN",
     ("Singapore Dollar", "Hong Kong Dollar", "Malaysian Ringgit"), None, ("NORMAL MODE", None)),
    ("₹", "Indian Rupee", "NORMAL", 4, "What about this one?", "The Indian rupee!", "🇮🇳", "INDIA",
     ("Indonesian Rupiah", "Iranian Rial", "Nepalese Rupee"), None, None),
    ("₩", "South Korean Won", "NORMAL", 4, "Halfway there!", "The South Korean won!", "🇰🇷", "SOUTH KOREA",
     ("Japanese Yen", "Chinese Yuan", "Vietnamese Dong"), None, ("HALFWAY!", "🔥")),
    ("₽", "Russian Ruble", "MEDIUM", 4, "Getting harder...", "The Russian ruble!", "🇷🇺", "RUSSIA",
     ("Philippine Peso", "Polish Złoty", "Kazakh Tenge"), "NOT THE PHILIPPINE PESO!", ("MEDIUM MODE", None)),
    ("₺", "Turkish Lira", "MEDIUM", 4, "This one's tricky.", "The Turkish lira!", "🇹🇷", "TURKEY",
     ("Azerbaijani Manat", "Georgian Lari", "Israeli Shekel"), None, None),
    ("฿", "Thai Baht", "HARD", 5, "Hard level!", "The Thai baht! Not Bitcoin!", "🇹🇭", "THAILAND",
     ("Bitcoin", "Bangladeshi Taka", "Brazilian Real"), "NOT BITCOIN! 😅", ("HARD MODE", "😳")),
    ("₴", "Ukrainian Hryvnia", "HARD", 5, "Final coin!", "The Ukrainian hryvnia!", "🇺🇦", "UKRAINE",
     ("Russian Ruble", "Polish Złoty", "Georgian Lari"), "Named after an old unit of weight! 🤯",
     ("FINAL COIN", "💀")),
]


# ----------------------------------------------------------------------------
# coin art
# ----------------------------------------------------------------------------

def coin_sprite(symbol, d=COIN):
    """Shiny gold coin with an embossed currency symbol."""
    ss = 2
    n = d * ss
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    cx = cy = n / 2
    r = np.hypot(xx - cx, yy - cy) / (n / 2)
    light = np.clip(1 - np.hypot(xx - n * 0.35, yy - n * 0.3) / (n * 0.9), 0, 1)
    base = np.array((200, 145, 30), np.float32)
    hi = np.array((255, 230, 120), np.float32)
    col = base[None, None] * (1 - light[..., None]) + hi[None, None] * light[..., None]
    rim = (r > 0.86) & (r <= 1.0)
    col[rim] = col[rim] * 0.78
    ring = (r > 0.80) & (r <= 0.84)
    col[ring] = col[ring] * 0.7
    a = np.where(r <= 1.0, 255, 0).astype(np.uint8)
    arr = np.dstack([np.clip(col, 0, 255).astype(np.uint8), a])
    im = Image.fromarray(arr, "RGBA")
    d0 = ImageDraw.Draw(im)
    for k in range(48):  # milled edge
        ang = 2 * math.pi * k / 48
        x1, y1 = cx + 0.88 * n / 2 * math.cos(ang), cy + 0.88 * n / 2 * math.sin(ang)
        x2, y2 = cx + 0.99 * n / 2 * math.cos(ang), cy + 0.99 * n / 2 * math.sin(ang)
        d0.line((x1, y1, x2, y2), fill=(150, 100, 15, 255), width=3 * ss)
    f = font("Black", int(n * 0.5), display=False)
    for off, c in (((5 * ss, 6 * ss), (120, 80, 10)), ((-3 * ss, -3 * ss), (255, 245, 190)), ((0, 0), (215, 160, 35))):
        d0.text((cx + off[0], cy + off[1] + n * 0.02), symbol, font=f, fill=c + (255,), anchor="mm")
    d0.ellipse((2, 2, n - 3, n - 3), outline=(90, 60, 5, 255), width=4 * ss)
    im = im.resize((d, d), Image.LANCZOS)
    glare = radial_glow(d, d, d * 0.33, d * 0.28, d * 0.35, (255, 255, 255), 0.45)
    glare.putalpha(Image.fromarray(np.minimum(np.asarray(glare.getchannel("A")), np.asarray(im.getchannel("A")))))
    im.alpha_composite(glare)
    return im


def coin_shadow(d=COIN):
    sh = Image.new("RGBA", (d + 80, d + 80))
    ImageDraw.Draw(sh).ellipse((40, 40, d + 40, d + 40), fill=(0, 0, 0, 150))
    return sh.filter(ImageFilter.GaussianBlur(18))


def flip(im, c):
    """Fake 3D coin spin: squash horizontally by |cos|."""
    w = max(2, int(im.width * abs(c)))
    out = im.resize((w, im.height), Image.BILINEAR)
    if c < 0:  # back side: darker
        out = Image.fromarray((np.asarray(out).astype(np.float32) * np.array((0.8, 0.8, 0.8, 1))).astype(np.uint8))
    return out


def option_card(letter, i, text, state):
    fill = {"idle": (255, 255, 255, 245), "right": (55, 195, 95, 255), "wrong": (230, 70, 70, 255)}[state]
    card = rounded_card(OPT_W, OPT_H, 28, fill, outline=(0, 0, 0, 255), width=5)
    d = ImageDraw.Draw(card)
    bc = LETTER_COL[i] if state == "idle" else (255, 255, 255)
    d.ellipse((14, 12, 86, 84), fill=bc + (255,), outline=(0, 0, 0, 255), width=4)
    d.text((50, 49), letter, font=font("Black", 44), fill=(255, 255, 255) if state == "idle" else (20, 22, 45),
           anchor="mm")
    size = 48
    while font("Black", size).getlength(text) > OPT_W - 200 and size > 30:
        size -= 2
    d.text((108, 49), text, font=font("Black", size), fill=(20, 22, 45) if state == "idle" else (255, 255, 255),
           anchor="lm")
    if state != "idle":
        card.alpha_composite(emoji("✅" if state == "right" else "❌", 54), (OPT_W - 76, 21))
    return card


def row(*parts, gap=14):
    h = max(p.height for p in parts)
    out = Image.new("RGBA", (sum(p.width for p in parts) + gap * (len(parts) - 1), h))
    x = 0
    for p in parts:
        out.alpha_composite(p, (x, (h - p.height) // 2))
        x += p.width + gap
    return out


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------

class Coin(mv.Scene):
    def __init__(self, tts, idx, q, minis, rng):
        super().__init__()
        sym, name, level, secs, before, said, flag, country, wrong, extra, banner = q
        self.idx, self.level, self.secs, self.minis = idx, level, secs, minis
        self.coin, self.shadow = coin_sprite(sym), coin_shadow()
        col = LEVEL_COL[level]
        self.pill = pill(f"COIN {idx}/10 · {level}", col)
        self.title = with_emoji(bold("GUESS THE CURRENCY!", 74), "💰", 80)
        choices = list(wrong)
        self.right = rng.randrange(4)
        choices.insert(self.right, name)
        self.cards = [{s: option_card("ABCD"[i], i, c, s) for s in ("idle", "right", "wrong")}
                      for i, c in enumerate(choices)]
        lines = [row(bold("USED IN", 56, stroke=7), emoji(flag, 60), bold(country, 56, fill=YELLOW, stroke=7))]
        if extra:
            parts = extra.rsplit(" ", 1)
            if len(parts) == 2 and not parts[1].isascii():
                lines.append(with_emoji(bold(parts[0], 50, fill=(255, 100, 90), stroke=6, max_w=880), parts[1], 52))
            else:
                lines.append(bold(extra, 50, fill=(255, 100, 90), stroke=6, max_w=900))
        hh = sum(m.height for m in lines) - 14 * (len(lines) - 1)
        self.used = Image.new("RGBA", (max(m.width for m in lines), hh))
        y = 0
        for m in lines:
            self.used.alpha_composite(m, ((self.used.width - m.width) // 2, y))
            y += m.height - 14
        self.rays = mq.sunburst(1100, (255, 200, 60), 18)
        self.nums = {(n, red): bold(str(n), 70, fill=(255, 80, 70) if red else (255, 255, 255), stroke=7)
                     for n in range(1, secs + 1) for red in (False, True)}
        self.pause = with_emoji(bold("Pause if you need more time", 36, stroke=5), "⏸", 40, 10) \
            if level == "HARD" else None
        self.plus = mq.ptext("+1", 46, fill=(120, 255, 90))
        self.slot = rounded_card(80, 80, 40, (10, 12, 30, 200), outline=(120, 150, 220, 255), width=3)
        self.banner = None
        if banner:
            b = mq.mc_button(banner[0], 640, 120, col, 46)
            self.banner = with_emoji(b, banner[1], 100, 6) if banner[1] else b
            self.sounds.append((0.1, mq.sfx_levelup(), 1.0))
        self.hook = with_emoji(bold("CAN YOU GET 10/10?", 78, fill=(255, 90, 80), stroke=9), "😳", 80) \
            if idx == 1 else None
        if self.hook is not None:
            self.sounds.append((0.1, mq.sfx_boom(), 0.7))
        v = tts.say(before, speed=1.1)
        self.voices.append((0.12, v))
        a = tts.say(said, speed=1.1)
        self.reveal = T_IN + secs
        self.voices.append((self.reveal + 0.1, a))
        self.dur = self.reveal + max(1.95 if extra else 1.5, 0.1 + len(a) / SR + 0.15)
        self.sounds += [(0.0, sfx_whoosh(0.35), 0.6), (0.05, sfx_coin(), 0.9)]
        for k in range(4):
            self.sounds.append((0.2 + 0.07 * k, sfx_pop(), 0.3))
        for k in range(secs):
            self.sounds.append((T_IN + k, mq.sfx_tock(high=k >= secs - 2), 1.0))
        self.sounds += [(self.reveal, sfx_ding(), 1.0), (self.reveal, mq.sfx_boom(), 0.45),
                        (self.reveal + 0.05, sfx_coin(), 0.8), (self.reveal + 1.0, sfx_coin(), 0.5)]
        if extra:
            self.sounds.append((self.reveal + 0.55, mq.sfx_glitch(), 0.6))
        r = random.Random(idx)
        self.burst = [(r.uniform(-700, 700), r.uniform(-1300, -400), r.randint(14, 26),
                       r.choice([YELLOW, (255, 255, 255), (255, 180, 40), (120, 255, 140)])) for _ in range(40)]

    def slot_x(self, i):
        return W / 2 + (i - 4.5) * 92

    def render(self, t):
        im = Image.new("RGBA", (W, H))
        rv = t - self.reveal
        out = ease_in_cubic((t - (self.dur - 0.25)) / 0.25)
        hk = ease_out_back(t / 0.3) * (1 - out)
        paste_center(im, scaled(self.pill, hk), W / 2, 150)
        paste_center(im, scaled(self.title, ease_out_back((t - 0.05) / 0.3) * (1 - out)), W / 2, 248)
        if self.hook is not None and t < 1.9:
            s = 1 + 1.2 * (1 - ease_out_cubic((t - 0.1) / 0.18))
            a = clamp((t - 0.1) / 0.08) * (1 - clamp((t - 1.6) / 0.3))
            paste_center(im, scaled(self.hook, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, PROG_Y + 14, a)
        bar_a = clamp((t - 1.9) / 0.3) if self.hook is not None else 1.0
        if bar_a > 0:  # coin collection bar
            for i in range(10):
                x = self.slot_x(i)
                filled = i < self.idx - 1 or (i == self.idx - 1 and rv > 1.0)
                paste_center(im, self.minis[i] if filled else self.slot, x, PROG_Y, bar_a)
                if not filled and i == self.idx - 1:
                    pulse = 0.5 + 0.5 * math.sin(t * 8)
                    ImageDraw.Draw(im).ellipse((x - 42, PROG_Y - 42, x + 42, PROG_Y + 42),
                                               outline=(255, 222, 40, int(255 * pulse * bar_a)), width=4)
        # the coin: spins in, wobbles, spins again on the reveal
        if rv > 0:
            paste_center(im, scaled(self.rays.rotate(rv * 30, Image.BICUBIC), 0.7 + 0.3 * ease_out_cubic(rv / 0.4)),
                         W / 2, COIN_Y, 0.8 * (1 - out))
        k_in = ease_out_cubic(t / 0.6)
        ang = (1 - k_in) * 3 * math.pi
        if rv > 0:
            ang += 2 * math.pi * ease_out_cubic(rv / 0.7)
        ang += 0.25 * math.sin(t * 2.2)
        s = (0.5 + 0.5 * k_in) * (1 - out) * (1 + 0.06 * math.sin(math.pi * clamp(rv / 0.3)) if rv > 0 else 1)
        bob = 10 * math.sin(t * 2.5)
        if s > 0.01:
            paste_center(im, scaled(self.shadow, s * max(0.3, abs(math.cos(ang)))), W / 2, COIN_Y + 30 + bob)
            paste_center(im, scaled(flip(self.coin, math.cos(ang)), s), W / 2, COIN_Y + bob)
        # answers
        for i, c in enumerate(self.cards):
            y = OPT_Y0 + i * OPT_DY
            k = ease_out_back((t - 0.15 - 0.07 * i) / 0.3) * (1 - out)
            if k <= 0.01:
                continue
            x = OPT_X + (1 - k) * (-W if i % 2 else W) * 0.3
            if rv <= 0:
                img, sc_, a = c["idle"], 1.0, 1.0
            elif i == self.right:
                img, sc_, a = c["right"], 1 + 0.1 * math.sin(math.pi * clamp(rv / 0.3)) + 0.03, 1.0
            else:
                img, sc_, a = c["wrong"], 1 - 0.05 * clamp(rv / 0.2), 1 - 0.35 * clamp(rv / 0.3)
            paste_center(im, scaled(img, sc_ * min(1.0, k + 0.0001)), x, y, a)
        if rv > 0.25:
            paste_center(im, self.plus, OPT_X + OPT_W / 2 - 20, OPT_Y0 + self.right * OPT_DY - 58,
                         clamp((rv - 0.25) / 0.15) * (1 - out))
        if rv < 0:
            cd = max(0.0, t - T_IN)
            n = max(1, self.secs - int(cd))
            red = n <= 2
            frac = 1 - clamp(cd / self.secs)
            bw, bh = 680, 38
            x0 = OPT_X - bw / 2 + 40
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((x0 - 6, TIMER_Y - bh / 2 - 6, x0 + bw + 6, TIMER_Y + bh / 2 + 6), 25,
                                fill=(10, 10, 20, 235))
            col = (255, 70, 60) if red else (110, 230, 90)
            if frac > 0.01:
                d.rounded_rectangle((x0, TIMER_Y - bh / 2, x0 + bw * frac, TIMER_Y + bh / 2), 19, fill=col + (255,))
            pop = 1 + 0.35 * (1 - ease_out_cubic((cd % 1) / 0.3))
            paste_center(im, scaled(self.nums[(n, red)], pop * hk), x0 - 68, TIMER_Y)
            if self.pause:
                paste_center(im, self.pause, OPT_X, TIMER_Y + 72, 0.9 * hk)
        else:
            d = ImageDraw.Draw(im)
            for vx, vy, sz, c in self.burst:
                px, py = W / 2 + vx * rv, COIN_Y + vy * rv + 2400 * rv * rv
                if py < H:
                    d.rectangle((px, py, px + sz, py + sz), fill=c + (255,))
            if rv > 0.4:
                paste_center(im, scaled(self.used, ease_out_back((rv - 0.4) / 0.3) * (1 - out)), OPT_X,
                             TIMER_Y + self.used.height / 2 - 30)
            if 0.6 < rv < 1.0:  # the coin flies into the collection bar
                k = ease_in_cubic((rv - 0.6) / 0.4)
                tx = self.slot_x(self.idx - 1)
                x = W / 2 + (tx - W / 2) * k
                y = COIN_Y + (PROG_Y - COIN_Y) * k - math.sin(math.pi * k) * 120
                paste_center(im, scaled(self.minis[self.idx - 1], 5.0 - 4.0 * k), x, y)
            f = 1 - clamp(rv / 0.18)
            if f > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * f))))
        if self.banner is not None and t < 1.0:
            bx = W / 2 + (1 - ease_out_cubic(t / 0.2)) * W - ease_in_cubic((t - 0.8) / 0.2) * W
            paste_center(im, self.banner.rotate(-4, Image.BICUBIC, expand=True), bx, 1010)
        if 0 < rv < 0.35:
            a = 22 * (1 - rv / 0.35)
            dx, dy = int(a * math.sin(rv * 90)), int(a * math.cos(rv * 75))
            shaken = Image.new("RGBA", (W, H))
            shaken.alpha_composite(im, (max(0, dx), max(0, dy)), (max(0, -dx), max(0, -dy)))
            im = shaken
        return im


def sfx_coin():
    """Bright 'cha-ching' coin clink."""
    out = np.zeros(int(0.6 * SR))
    for st, base in ((0.0, 2637.0), (0.07, 3520.0)):
        t = tt(0.5)
        s = sum(a * np.sin(2 * np.pi * base * m * t) * np.exp(-t * d) for m, a, d in
                ((1, 1.0, 9), (2.76, 0.5, 14), (5.4, 0.25, 20)))
        i = int(st * SR)
        out[i:i + len(s)] += s[: len(out) - i]
    return out / np.abs(out).max() * 0.35


class Ending(mv.Scene):
    def __init__(self, tts, minis):
        super().__init__()
        self.minis = minis
        v = tts.say("How many did you get? Comment your score!", speed=1.1)
        self.voices.append((0.15, v))
        self.dur = max(4.2, 0.15 + len(v) / SR + 1.6)
        self.sounds += [(0.0, sfx_whoosh(0.4), 0.7), (0.15, mq.sfx_levelup(), 0.9), (0.9, sfx_coin(), 0.8)]
        self.t1 = bold("HOW MANY", 120, fill=YELLOW, stroke=11)
        self.t2 = with_emoji(bold("DID YOU GET?", 116, fill=YELLOW, stroke=11), "🤔", 110)
        rows = [("10/10", "MONEY GENIUS", "🧠", (230, 150, 20)), ("7-9", "WORLD TRAVELER", "✈", (60, 110, 220)),
                ("4-6", "TOURIST", "📸", (60, 170, 70)), ("0-3", "BROKE", "💸", (120, 120, 130))]
        self.rows = []
        for i, (sc_, label, e, col) in enumerate(rows):
            b = rounded_card(920, 124, 36, col + (245,), outline=(0, 0, 0, 255), width=5)
            st = bold(sc_, 60, stroke=6)
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
        for i, r_ in enumerate(self.rows):
            k = ease_out_cubic((t - 0.6 - 0.18 * i) / 0.35)
            paste_center(im, r_, W / 2 + (1 - k) * (W if i % 2 else -W), 660 + i * 150, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.5) / 0.4) * (1 + 0.04 * math.sin(t * 8))), W / 2,
                     1300, a)
        for i, m in enumerate(self.minis):
            k = ease_out_back((t - 0.9 - 0.05 * i) / 0.3)
            paste_center(im, scaled(m, k), W / 2 + (i - 4.5) * 92, 1425 + 6 * math.sin(t * 5 + i), a)
        return im


def build():
    tts = mv.TTS("af_heart", "en-us")
    minis = [coin_sprite(q[0], 80) for q in COINS]
    rng = random.Random(31)
    scenes = [Coin(tts, i, q, minis, rng) for i, q in enumerate(COINS, 1)] + [Ending(tts, minis)]
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t


def make_cover(full, path):
    base = cq.bg_frame(full, 3.0).convert("RGBA") if full else Image.new("RGBA", (W, H), (20, 40, 100, 255))
    paste_center(base, mq.sunburst(1700, (255, 200, 60), 18), W / 2, 1050, 0.6)
    paste_center(base, bold("GUESS THE", 120, stroke=12), W / 2, 230)
    paste_center(base, bold("CURRENCY", 180, fill=YELLOW, stroke=15), W / 2, 400)
    paste_center(base, with_emoji(bold("BY THE SYMBOL!", 92, stroke=10), "💰", 96), W / 2, 560)
    for sym, x, y, d, rot in (("₩", 270, 860, 300, -10), ("₹", 810, 860, 300, 10), ("₽", 270, 1240, 300, 8),
                              ("฿", 810, 1240, 300, -8), ("₴", 540, 1050, 380, 0)):
        c = coin_sprite(sym, d).rotate(rot, Image.BICUBIC, expand=True)
        paste_center(base, coin_shadow(d), x, y + 24)
        paste_center(base, c, x, y)
    paste_center(base, mq.mc_button("99% FAIL", 460, 116, (210, 30, 30), 46).rotate(-6, Image.BICUBIC, expand=True),
                 W / 2, 1530)
    base.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_currency_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--no-bg", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    scenes, starts, total = build()
    for sc, st in zip(scenes, starts):
        print(f"  {st:6.2f}s  {type(sc).__name__} {getattr(sc, 'idx', '')}")
    print(f"Duration {total:.1f}s")
    work = os.path.join(mv.CACHE_DIR, "render_currency")
    os.makedirs(work, exist_ok=True)
    full = None if a.no_bg else oo.logo_bg_full(total, work)
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.cover:
        make_cover(full, os.path.join(HERE, "currency_quiz_cover.jpg"))
        return
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"cur_{float(s):06.2f}.png")
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
