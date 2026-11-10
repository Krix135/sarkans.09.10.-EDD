#!/usr/bin/env python3
""""SPOT THE FAKE FLAG" Short (1080x1920), edited like the crazy quizzes.

Every round shows four labelled flags; one of them has been changed (colour swapped, stripes in the
wrong order, mirrored...). A 3-2-1 runs on the beat, then the fake gets a FAKE stamp, morphs into the
real flag and a short note says what was wrong. Ten rounds, EASY -> IMPOSSIBLE, no intro: a big
SPOT THE FAKE FLAG title sits on the first round from frame one. National flags are public domain.

    python3 make_fake_flag_quiz.py --voice-pack voice_packs/fakeflag_adam,voice_packs/map3_adam
    python3 make_fake_flag_quiz.py --stills 0,3,5
    python3 make_fake_flag_quiz.py --cover
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
from PIL import Image, ImageDraw, ImageFilter, ImageOps  # noqa: E402

import brand  # noqa: E402
import make_club_quiz as cq  # noqa: E402
import make_logo_quiz as lq  # noqa: E402
import make_map_quiz as mm  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_minecraft_quiz as mq  # noqa: E402
import make_video as mv  # noqa: E402
from make_map_quiz import CYAN, GOLD, INK, PINK, join, rfont, rtext  # noqa: E402
from make_map_quiz_crazy import beat_pulse, glitch, rgb_split, sfx_heartbeat, shake  # noqa: E402
from make_video import SR, clamp, ease_in_cubic, ease_out_back, ease_out_cubic, emoji, paste_center, rounded_card, \
    scaled  # noqa: E402

W, H, FPS = 1080, 1920, 30
mv.W, mv.H = W, H
BPM = 130
B = 60 / BPM
FLAG_DIR = os.path.join(HERE, "flags")
TIERS = mc.TIERS
CELL_X = (285, 795)
CELL_Y = (770, 1230)
FLAG_BOX = (440, 290)
GRID_C = (540, 1000)
NOTE_Y = 1560
ENTRY_BEATS = 2

NAMES = {"AR": "ARGENTINA", "AU": "AUSTRALIA", "BR": "BRAZIL", "CL": "CHILE", "CO": "COLOMBIA", "CU": "CUBA",
         "EG": "EGYPT", "ES": "SPAIN", "GR": "GREECE", "HR": "CROATIA", "IE": "IRELAND", "IN": "INDIA",
         "IS": "ICELAND", "NO": "NORWAY", "NZ": "NEW ZEALAND", "PE": "PERU", "PH": "PHILIPPINES",
         "PT": "PORTUGAL", "SE": "SWEDEN", "TH": "THAILAND", "UA": "UKRAINE", "VN": "VIETNAM",
         "ZA": "SOUTH AFRICA", "CN": "CHINA", "JP": "JAPAN", "CA": "CANADA", "US": "USA", "DE": "GERMANY",
         "FR": "FRANCE", "IT": "ITALY", "MX": "MEXICO", "TR": "TURKEY", "GB": "UK", "KR": "SOUTH KOREA"}
POOL = ["AR", "AU", "BR", "CL", "CO", "CU", "EG", "ES", "GR", "HR", "IN", "IS", "NO", "NZ", "PE", "PH", "PT",
        "SE", "TH", "UA", "VN", "ZA", "CN"]

ROUNDS = [  # fake country, how it was changed, what was wrong, emoji, tier, prompt, spoken answer, sticker
    ("JP", "blue", "Japan's sun is red, not blue", "🔴", "EASY", "Spot the fake flag!", "Japan! Its sun is red!",
     "😎"),
    ("CA", "blue", "Canada's flag is red and white", "🍁", "EASY", "Next!", "Canada! It's red and white!", "🔥"),
    ("US", "mirror", "the stars belong in the top left", "⭐", "EASY", "Too easy?", "The USA! Stars go top left!",
     "🤔"),
    ("DE", "swap_bands", "it's black, red, gold - in that order", "🟥", "MEDIUM", "Think fast!",
     "Germany! Black, red, gold!", "😳"),
    ("FR", "mirror", "blue goes next to the flagpole", "🔵", "MEDIUM", "Ooh, tricky!",
     "France! Blue goes by the pole!", "🤯"),
    ("IT", "mirror", "green goes next to the flagpole", "🟢", "MEDIUM", "Next!", "Italy! Green goes by the pole!",
     "🔥"),
    ("MX", "mirror", "green is on the left and the eagle faces left", "🦅", "HARD", "Hard level!",
     "Mexico! It's flipped!", "😱"),
    ("TR", "mirror", "the crescent and star sit by the flagpole", "🌙", "HARD", "No way!",
     "Turkey! The moon is backwards!", "💀"),
    ("GB", "mirror", "it's mirrored: the red diagonals are flipped", "🧐", "INSANE", "Insane level!",
     "The UK! It's mirrored!", "🧠"),
    ("KR", "mirror", "it's mirrored: the symbol is flipped", "☯", "IMPOSSIBLE", "Impossible level!",
     "South Korea! It's mirrored!", "☠"),
]
END_LINE = "How many did you get? Comment your score!"


# ----------------------------------------------------------------------------
# flags and fakes
# ----------------------------------------------------------------------------
def load_flag(code):
    im = Image.open(os.path.join(FLAG_DIR, code + ".png")).convert("RGB")
    im.thumbnail((FLAG_BOX[0] * 2, FLAG_BOX[1] * 2), Image.LANCZOS)
    return im


def recolor_red(im, to):
    """Every clearly red pixel becomes `to` (keeps the shape and edges)."""
    a = np.asarray(im).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    redness = np.clip((r - np.maximum(g, b) - 40) / 80.0, 0, 1)[..., None]
    out = a * (1 - redness) + np.array(to)[None, None, :] * redness
    return Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGB")


def swap_bands(im):
    """Three horizontal stripes: swap the middle and bottom ones."""
    w, h = im.size
    t = h // 3
    top, mid, bot = im.crop((0, 0, w, t)), im.crop((0, t, w, 2 * t)), im.crop((0, 2 * t, w, h))
    out = im.copy()
    out.paste(bot.resize((w, t)), (0, t))
    out.paste(mid.resize((w, h - 2 * t)), (0, 2 * t))
    return out


def make_fake(im, how):
    if how == "mirror":
        return ImageOps.mirror(im)
    if how == "blue":
        return recolor_red(im, (20, 70, 210))
    if how == "swap_bands":
        return swap_bands(im)
    raise ValueError(how)


def flag_tile(im, name, letter):
    """Flag (fitted to the box) with a white edge and shadow, its letter badge and the country name below."""
    fw, fh = FLAG_BOX
    f = im.copy()
    f.thumbnail((fw, fh), Image.LANCZOS)
    pad = 24
    out = Image.new("RGBA", (fw + 2 * pad, fh + 2 * pad + 86))
    cx, cy = out.width / 2, pad + fh / 2
    sh = Image.new("L", out.size)
    ImageDraw.Draw(sh).rounded_rectangle((cx - f.width / 2 - 6, cy - f.height / 2 + 4, cx + f.width / 2 + 6,
                                          cy + f.height / 2 + 16), 18, fill=170)
    out.paste(Image.new("RGBA", out.size, (0, 0, 12, 255)), (0, 0), sh.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((cx - f.width / 2 - 7, cy - f.height / 2 - 7, cx + f.width / 2 + 7, cy + f.height / 2 + 7), 16,
                        fill=(255, 255, 255, 255))
    m = Image.new("L", f.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, f.width - 1, f.height - 1), 10, fill=255)
    out.paste(f, (int(cx - f.width / 2), int(cy - f.height / 2)), m)
    badge = mv.circle(70, INK + (240,))
    ImageDraw.Draw(badge).text((35, 37), letter, font=rfont(46), fill=(255, 255, 255), anchor="mm")
    out.alpha_composite(badge, (int(cx - f.width / 2 - 20), int(cy - f.height / 2 - 22)))
    size = 50
    while rfont(size).getlength(name) > fw and size > 30:
        size -= 2
    t = rtext(name, size, stroke=6)
    paste_center(out, t, cx, pad + fh + 48)
    return out


def stamp(text, col, size=78, ang=-12):
    t = rtext(text, size, fill=col, stroke=0)
    pad = 26
    s = Image.new("RGBA", (t.width + 2 * pad, t.height + 2 * pad))
    ImageDraw.Draw(s).rounded_rectangle((6, 6, s.width - 7, s.height - 7), 22, fill=(255, 255, 255, 235),
                                        outline=col + (255,), width=10)
    s.alpha_composite(t, (pad, pad))
    return s.rotate(ang, Image.BICUBIC, expand=True)


class FlagWall(lq.BrandWall):
    EMOJIS = ["🚩", "🏁", "🌍", "🗺", "🏳", "🧭", "🌎", "📍"]


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Round(mv.Scene):
    def __init__(self, idx, r, prev_tier, ui, tts):
        super().__init__()
        code, how, why, wemoji, tier, prompt, said, stick = r
        self.idx, self.ui, self.tier = idx, ui, tier
        self.danger = tier in ("INSANE", "IMPOSSIBLE")
        f = ENTRY_BEATS
        self.fly = f * B
        self.count_beats = [f + 3, f + 4, f + 5]
        self.reveal = (f + 6) * B
        v_ans = tts.say(said, speed=1.12) if tts else None
        a_len = len(v_ans) / SR if v_ans is not None else 1.5
        self.dur = (f + 6 + max(5, math.ceil((0.1 + a_len + 0.35) / B))) * B   # time for the answer
        rnd = random.Random(idx * 101 + 7)
        others = rnd.sample([c for c in POOL if c != code], 3)
        self.fake_pos = rnd.randrange(4)
        codes = others[:self.fake_pos] + [code] + others[self.fake_pos:]
        real = load_flag(code)
        fake = make_fake(real, how)
        self.tiles = []
        for k, c in enumerate(codes):
            img = fake if k == self.fake_pos else load_flag(c)
            self.tiles.append(flag_tile(img, NAMES[c], "ABCD"[k]))
        self.real_tile = flag_tile(real, NAMES[code], "ABCD"[self.fake_pos])
        self.fake_stamp = stamp("FAKE", (230, 30, 60), 92)
        self.real_stamp = stamp("REAL", (30, 170, 80), 70, ang=8)
        body = join(emoji(wemoji, 56), rtext(why[0].upper() + why[1:], 44 if len(why) < 40 else 38, stroke=0), gap=14)
        self.note = rounded_card(body.width + 60, body.height + 30, (body.height + 30) // 2, INK + (230,),
                                 outline=GOLD + (255,), width=4)
        paste_center(self.note, body, self.note.width / 2, self.note.height / 2)
        self.note = scaled(self.note, min(1.0, 960 / self.note.width))          # always inside the screen
        self.sticker = emoji(stick, 140)
        self.col, e = TIERS[tier]
        self.count = rtext(f"{idx}/{len(ROUNDS)}", 46, stroke=5)
        self.tag = rounded_card(int(rfont(30).getlength(tier)) + 44, 48, 24, self.col + (255,), outline=INK + (255,),
                                width=3)
        ImageDraw.Draw(self.tag).text((self.tag.width / 2, 25), tier, font=rfont(30), fill=INK, anchor="mm")
        self.header = join(rtext("SPOT THE FAKE FLAG", 56, stroke=6), emoji("🚩", 56), gap=10)
        self.level_up = tier != prev_tier and idx > 1
        self.banner = None
        if self.level_up:
            self.banner = join(rtext(f"{tier}!", 92, fill=self.col, stroke=9), emoji(e, 90))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        self.title = None                          # big opening title on round 1
        self.badge = mv.circle(150, (255, 255, 255, 255))
        ImageDraw.Draw(self.badge).text((75, 78), "?", font=rfont(96), fill=INK, anchor="mm")
        self.ring = mv.circle(186, GOLD + (255,))
        self.nums = {k: rtext(str(k), 120, fill=PINK if k == 1 else INK, stroke=0) for k in range(1, 4)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8)]
        for k in range(4):
            self.sounds.append((0.1 + 0.09 * k, mv.sfx_pop(), 0.6))
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == 2), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        self.sounds += [(self.reveal, mq.sfx_boom(), 0.9), (self.reveal, mq.sfx_glitch(), 0.5),
                        (self.reveal + 0.05, mv.sfx_ding(), 0.9), (self.reveal + 0.7, mv.sfx_whoosh(0.3), 0.5),
                        (self.reveal + 0.75, mq.sfx_pling(), 0.6), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        if tts:
            v = tts.say(prompt, speed=1.18)
            self.voices.append((0.12, v))
            if 0.12 + len(v) / SR > self.count_beats[0] * B + 0.1:
                print(f"warning: prompt {idx} runs into the countdown", flush=True)
            self.voices.append((self.reveal + 0.1, v_ans))
        r2 = random.Random(idx * 31)
        self.conf = [(r2.uniform(-1, 1) * 600, r2.uniform(-1200, -400), r2.randint(12, 24),
                      r2.choice([GOLD, CYAN, PINK, (255, 255, 255)]), r2.uniform(0, 3)) for _ in range(50)]

    def cell(self, k):
        return CELL_X[k % 2], CELL_Y[k // 2]

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        on_beat = beat_pulse(T) if t > self.fly else 0.0
        im = self.ui["bg"].render(T, self.col, strobe=on_beat * 0.5 + (1 - clamp(rv / 0.25) if rv > 0 else 0),
                                  rays=0.5 + 0.3 * on_beat if rv < 0 else 0.9)
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        d = ImageDraw.Draw(im)
        paste_center(im, self.header, W / 2, 190)
        paste_center(im, self.count, 92, 262)
        x0, x1, y, bh = 170, 1000, 262, 20
        frac = 1.0 if t < self.fly else max(0.0, 1 - (t - self.fly) / (self.reveal - self.fly))
        d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
        colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
        if frac > 0.01:
            d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 10, fill=colr + (255,))
        paste_center(im, self.tag, x0 + self.tag.width / 2, 318)
        n = self.idx if rv > 0 else self.idx - 1
        if n > 0:
            sc = 1 + 0.5 * (1 - ease_out_cubic(rv / 0.25)) if 0 < rv < 0.25 else 1.0
            stk = self.streak[n]
            paste_center(im, scaled(stk, sc), x1 - stk.width / 2 + 10, 318)
        # the four flags pop in one by one, bob on the beat, then the fake is caught and swapped for the real one
        for k, tile in enumerate(self.tiles):
            kp = ease_out_back(clamp((t - 0.08 - 0.09 * k) / 0.3), 1.8)
            if kp <= 0.01:
                continue
            cx, cy = self.cell(k)
            s = kp * (1 + 0.025 * on_beat * (1 if (k + self.idx) % 2 else -1) + (0.015 if rv < 0 else 0))
            ang = 2.5 * math.sin(T * 2 + k * 1.7) if rv < 0 else 0.0
            if rv > 0 and k == self.fake_pos:
                morph = clamp((rv - 0.6) / 0.35)
                kick = 1 + 0.1 * (1 - ease_out_cubic(clamp(rv / 0.3)))
                dx = 16 * math.sin(rv * 70) * (1 - clamp(rv / 0.4))
                fake_img = scaled(tile, s * kick)
                if morph < 1:
                    paste_center(im, fake_img, cx + dx, cy, 1 - morph)
                if morph > 0:
                    paste_center(im, scaled(self.real_tile, s * kick), cx, cy, morph)
                ks = ease_out_back(clamp(rv / 0.22), 2.4)
                if ks > 0.01 and morph < 1:
                    paste_center(im, scaled(self.fake_stamp, 1.6 - 0.6 * ks), cx, cy - 40, min(1.0, ks) * (1 - morph))
                kr = ease_out_back(clamp((rv - 0.75) / 0.25), 2.4)
                if kr > 0.01:
                    paste_center(im, scaled(self.real_stamp, kr), cx + 150, cy - 140, min(1.0, kr))
            else:
                c = scaled(tile, s)
                if abs(ang) > 0.2:
                    c = c.rotate(ang, Image.BICUBIC, expand=True)
                paste_center(im, c, cx, cy, 0.45 + 0.55 * (1 - clamp(rv / 0.25)) if rv > 0 else 1.0)
        # centre badge: ? then the 3-2-1
        if 0.35 < t and rv < 0.2:
            kb = ease_out_back(clamp((t - 0.35) / 0.3), 2.0) * (1 + 0.08 * on_beat)
            fade = 1 - clamp(rv / 0.2) if rv > 0 else 1.0
            paste_center(im, scaled(self.ring, kb * (1 + 0.06 * math.sin(T * 6))), *GRID_C, fade)
            badge = self.badge
            for j, b in enumerate(self.count_beats):
                tb = t - b * B
                if 0 <= tb < B:
                    badge = mv.circle(150, (255, 255, 255, 255))
                    paste_center(badge, scaled(self.nums[3 - j], 1.25 - 0.25 * ease_out_cubic(tb / 0.12)), 75, 78)
            paste_center(im, scaled(badge, kb), *GRID_C, fade)
        if self.banner is not None and 0.05 < t < self.fly + 0.4:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly - 0.15) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), *GRID_C, a)
        if self.title is not None:                 # opening title, readable from frame one
            t_end = self.count_beats[0] * B - 0.1
            if t < t_end:
                l1, l2 = self.title
                pop = 1 + 0.1 * (1 - ease_out_cubic(clamp(t / 0.25))) + 0.04 * beat_pulse(T)
                out = ease_in_cubic(clamp((t - (t_end - 0.3)) / 0.3))
                im.alpha_composite(Image.new("RGBA", (W, H), (8, 4, 24, int(150 * (1 - out)))))
                paste_center(im, scaled(l1, pop * (1 + 0.3 * out)).rotate(-3, Image.BICUBIC, expand=True), W / 2,
                             880 - 300 * out, 1 - out)
                paste_center(im, scaled(l2, pop * (1 + 0.3 * out)).rotate(2, Image.BICUBIC, expand=True), W / 2,
                             1080 - 300 * out, 1 - out)
        if rv > 0:
            cx, cy = self.cell(self.fake_pos)
            for vx, vy, sz, cc, spin in self.conf:
                px, py = cx + vx * rv, cy + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d = ImageDraw.Draw(im)
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            kn = ease_out_back(clamp((rv - 0.45) / 0.3), 1.8)
            if kn > 0.01:
                paste_center(im, scaled(self.note, kn * (1 + 0.015 * beat_pulse(T))), W / 2, NOTE_Y)
            ks = ease_out_back((rv - 0.15) / 0.25, 2.2)
            if ks > 0.01:
                paste_center(im, scaled(self.sticker, ks).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             W / 2, GRID_C[1])
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 60, 80, int(150 * fl))))
            im = shake(im, 28 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 16 * (1 - rv / 0.18))
        else:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 10 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 7 * (1 - tb / 0.15))
        if self.level_up and t < 0.35:
            im = glitch(im, 1 - t / 0.35, int(t * 30) + self.idx * 7)
        if t < 0.16 and self.idx > 1:
            im = rgb_split(mm.zoom_blur(im, 1 - t / 0.16), 18 * (1 - t / 0.16))
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(mm.zoom_blur(im, out), 22 * out)
        return im


class Ending(mv.Scene):
    def __init__(self, ui, first, tts):
        super().__init__()
        self.ui, self.first = ui, first
        self.dur = 10 * B
        logo = Image.open(brand.round_logo()).convert("RGBA").resize((120, 120), Image.LANCZOS)
        self.brand = join(logo, rtext(brand.NAME, 60, stroke=6), gap=18)
        self.title = rtext("HOW MANY?", 124, fill=CYAN, stroke=11)
        tiers = [("0-3", "Tourist", "📸"), ("4-5", "Flag fan", "🚩"), ("6-7", "Flag spotter", "🔍"),
                 ("8-9", "Flag expert", "🧠"), ("10", "Flag detective", "🕵")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            colr = PINK if i == 4 else (255, 255, 255)
            row = rounded_card(800, 104, 52, INK + (215,), outline=(colr if i == 4 else (90, 70, 130)) + (255,),
                               width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 52), sc, font=rfont(60), fill=colr, anchor="lm")
            dr.text((200, 52), label, font=rfont(58, "SemiBold"), fill=colr, anchor="lm")
            row.alpha_composite(emoji(e, 60), (800 - 96, 22))
            self.rows.append(row)
        self.cta = join(rtext("comment your score", 58, stroke=6), emoji("👇", 62))
        self.sounds += [(0.0, mv.sfx_whoosh(0.8), 0.7), (B, mq.sfx_levelup(), 0.9)]
        for i in range(5):
            self.sounds.append(((1.5 + 0.5 * i) * B, mv.sfx_pop(), 0.7))
        self.sounds.append((5 * B, mq.sfx_pling(), 0.7))
        if tts:
            self.voices.append((0.3, tts.say(END_LINE, speed=1.1)))

    def render(self, t):
        T = self.t0 + t
        im = self.ui["bg"].render(T, GOLD, strobe=0.35 * beat_pulse(T), rays=0.8)
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        a = 1 - out
        im.alpha_composite(Image.new("RGBA", (W, H), INK + (int(150 * clamp((t - 0.2) / 0.3) * a),)))
        paste_center(im, self.brand, W / 2, 300, clamp((t - B) / 0.2) * a)
        paste_center(im, scaled(self.title, ease_out_back((t - B) / 0.25)), W / 2, 460, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - (1.5 + 0.5 * i) * B) / 0.2)
            if k > 0:
                paste_center(im, row, W / 2 + (1 - k) * 160, 620 + i * 122, k * a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 4.5 * B) / 0.25) * (1 + 0.03 * math.sin(t * 8))),
                     W / 2, 1285, a)
        if t < 0.2:
            im = rgb_split(mm.zoom_blur(im, 1 - t / 0.2), 18 * (1 - t / 0.2))
        if out > 0:
            first = self.first.render(0.0)
            first.putalpha(first.getchannel("A").point(lambda v: int(v * out)))
            im.alpha_composite(first)
        return im


def build(voice="am_adam", voice_pack=None):
    if voice_pack:
        tts = cq.Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    ui = {"bg": FlagWall(), "vig": [mc.red_vignette(i / 10) for i in range(11)]}
    scenes, prev = [], ROUNDS[0][4]
    for i, r in enumerate(ROUNDS, 1):
        scenes.append(Round(i, r, prev, ui, tts))
        prev = r[4]
    fit = lambda im: scaled(im, min(1.0, 900 / im.width))  # noqa: E731
    scenes[0].title = (fit(rtext("SPOT THE", 150, stroke=13)),
                       fit(join(rtext("FAKE FLAG", 160, fill=PINK, stroke=14), emoji("🚩", 140), gap=14)))
    scenes.append(Ending(ui, scenes[0], tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    im = ui["bg"].render(1.0, PINK, rays=0.9)
    codes = ["BR", "US", "JP", "IT"]
    for k, c in enumerate(codes):
        img = load_flag(c)
        if c == "US":
            img = make_fake(img, "mirror")
        tile = flag_tile(img, NAMES[c], "ABCD"[k])
        paste_center(im, tile.rotate((-4, 3, 3, -4)[k], Image.BICUBIC, expand=True), CELL_X[k % 2], 820 + 450 * (k // 2))
    paste_center(im, rtext("SPOT THE", 140, stroke=12).rotate(-3, Image.BICUBIC, expand=True), W / 2, 260)
    paste_center(im, join(rtext("FAKE FLAG", 150, fill=PINK, stroke=13), emoji("🚩", 130), gap=12).rotate(
        2, Image.BICUBIC, expand=True), W / 2, 440)
    paste_center(im, join(rtext("99% FAIL", 84, fill=GOLD, stroke=8), emoji("💀", 86)), W / 2, 600)
    ring = mv.circle(186, GOLD + (255,))
    badge = mv.circle(150, (255, 255, 255, 255))
    ImageDraw.Draw(badge).text((75, 78), "?", font=rfont(96), fill=INK, anchor="mm")
    paste_center(im, ring, W / 2, 1045)
    paste_center(im, badge, W / 2, 1045)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_fake_flag_quiz.mp4"))
    ap.add_argument("--stills", default=None)
    ap.add_argument("--cover", action="store_true")
    ap.add_argument("--voice", default="am_adam")
    ap.add_argument("--voice-pack", default=None, help="comma-separated voice pack folders (lines.txt + 00.wav...)")
    ap.add_argument("--audio-only", action="store_true", help="rebuild only the sound and swap it into --out")
    ap.add_argument("--music", default="phonk", choices=["phonk", "none"])
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    quiet = a.stills or a.cover
    scenes, starts, total, ui = build(a.voice if not quiet else "none", None if quiet else a.voice_pack)
    print(f"Duration {total:.1f}s ({total / B:.0f} beats)")
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_fakeflag")
    os.makedirs(work, exist_ok=True)
    if a.audio_only:
        src, wav = os.path.join(work, "video_src.mp4"), os.path.join(work, "audio_only.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.out, "-map", "0:v", "-c", "copy", src], check=True)
        mv.write_wav(wav, mmq.mix_audio(scenes, starts, total, a.music))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-c:a", "aac",
                        "-b:a", "192k", "-movflags", "+faststart", "-shortest", a.out], check=True)
        print(f"Done (audio only): {a.out}")
        return
    if a.cover:
        make_cover(ui, os.path.join(HERE, "fake_flag_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"fakeflag_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
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
