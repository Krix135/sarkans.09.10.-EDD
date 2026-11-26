#!/usr/bin/env python3
""""GUESS THE COUNTRY BY ITS FAMOUS LANDMARK" Short (1080x1920), maximum edit.

Each round a real photo of a landmark slams in, heavily pixelated and zoomed into one detail, inside a
camera-viewfinder frame over a blurred backdrop of itself. On every beat of the 3-2-1 it "ENHANCES": a
scanner line sweeps down, the pixels get smaller, the camera pulls back, the screen punches and glitches.
On the drop the photo snaps sharp with a flash and the landmark's name stamps across it. Then a whip to
space: the globe zooms in to the country, which fills with its flag, the photo shrinks into a polaroid,
a pin drops onto the exact spot with a string to the polaroid, the country's name flips in on letter
tiles and a fun fact pops up. Spoken-title intro (6 beats), EASY -> IMPOSSIBLE plus a bonus, one like
call-out after round 3, looping score screen.

Photos: Wikimedia Commons (public domain / CC BY / CC BY-SA, credits in landmark_photos_credits.json and
the description). Borders: Natural Earth (public domain). Flags: public domain.

    python3 make_landmark_quiz.py
    python3 make_landmark_quiz.py --stills 0,5,9
    python3 make_landmark_quiz.py --cover
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
CW, CH = 880, 930                    # the photo inside the card
CARD_C = (540, 1050)
CARD_Y = 438
GC = (540, 1110)                     # globe centre in the reveal
mm.TILE_Y = 1645
FACT_Y = 1765
CTA_Y = 1790
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE = (3,), mc.CTA_LINE
FLAG_DIR = os.path.join(HERE, "flags")
PHOTO_DIR = os.path.join(HERE, "landmark_photos")
GREEN = (46, 204, 113)

ROUNDS = [  # photo, landmark, emoji, map code, flag, country, (lon, lat), focus (fx, fy), start zoom, fact, fact emoji,
    #         tier, prompt, spoken landmark, spoken country, sticker, globe view override (lon, lat, R)
    ("eiffel", "EIFFEL TOWER", "🗼", "FRA", "FR", "FRANCE", (2.2945, 48.8584), (0.5, 0.33), 2.2,
     "it grows about 15 cm taller in the summer heat", "🌡", "EASY", "Which country is this landmark in?",
     "The Eiffel Tower!", "France!", "😎", None),
    ("liberty2", "STATUE OF LIBERTY", "🗽", "USA", "US", "USA", (-74.0445, 40.6892), (0.46, 0.2), 2.2,
     "it was a gift from France in 1886", "🎁", "EASY", "Next one!", "The Statue of Liberty!", "The USA!", "🔥",
     None),
    ("pyramids", "PYRAMIDS OF GIZA", "🔺", "EGY", "EG", "EGYPT", (31.1342, 29.9792), (0.62, 0.5), 2.0,
     "the Great Pyramid was the tallest building for 3,800 years", "🏛", "EASY", "Too easy?",
     "The Pyramids of Giza!", "Egypt!", "🤔", None),
    ("taj", "TAJ MAHAL", "🕌", "IND", "IN", "INDIA", (78.0421, 27.1751), (0.5, 0.33), 2.3,
     "an emperor built it in memory of his wife", "💍", "MEDIUM", "Think fast!", "The Taj Mahal!", "India!", "😳",
     None),
    ("colosseum", "COLOSSEUM", "🏟", "ITA", "IT", "ITALY", (12.4922, 41.8902), (0.45, 0.5), 2.3,
     "it could hold about 50,000 people", "👥", "MEDIUM", "Ooh, tricky!", "The Colosseum!", "Italy!", "🤯",
     None),
    ("christ", "CHRIST THE REDEEMER", "🙏", "BRA", "BR", "BRAZIL", (-43.2105, -22.9519), (0.5, 0.3), 2.4,
     "it gets hit by lightning several times a year", "⚡", "MEDIUM", "Next!", "Christ the Redeemer!",
     "Brazil!", "🔥", None),
    ("machu", "MACHU PICCHU", "🏔", "PER", "PE", "PERU", (-72.5450, -13.1631), (0.5, 0.55), 2.4,
     "it sits about 2,430 m above sea level", "☁", "HARD", "Hard level!", "Machu Peechu!", "Peru!", "😱",
     None),
    ("sagrada", "SAGRADA FAMILIA", "⛪", "ESP", "ES", "SPAIN", (2.1744, 41.4036), (0.6, 0.3), 2.5,
     "it has been under construction since 1882", "🏗", "HARD", "No way!", "The Sagrada Familia!", "Spain!",
     "💀", None),
    ("neuschwanstein", "NEUSCHWANSTEIN CASTLE", "🏰", "DEU", "DE", "GERMANY", (10.7498, 47.5576), (0.45, 0.35),
     2.6, "it inspired Disney's Sleeping Beauty castle", "✨", "INSANE", "Insane level!",
     "Noy schwan stine Castle!", "Germany! Not Disney!", "🧠", None),
    ("moai2", "MOAI, EASTER ISLAND", "🗿", "CHL", "CL", "CHILE", (-109.30, -27.12), (0.78, 0.33), 2.6,
     "Easter Island is 3,500 km from mainland Chile", "🌊", "IMPOSSIBLE", "Impossible level!",
     "The Moai of Easter Island!", "Chile!", "☠", (-90.0, -30.0, 1180.0)),
    ("angkor", "ANGKOR WAT", "🛕", "KHM", "KH", "CAMBODIA", (103.8670, 13.4125), (0.66, 0.35), 2.8,
     "it's on Cambodia's flag!", "🚩", "BONUS", "Bonus! Only one percent!", "Angkor Wat!", "Cambodia!", "👑",
     None),
]
INTRO_WORDS = ("Guess the country", "by its landmark!", "Ninety-nine percent fail!")
BG_CACHE = {}


def fit(im, max_w=920):
    return scaled(im, min(1.0, max_w / im.width))


def rounded_mask(w, h, r):
    m = Image.new("L", (w * 2, h * 2))
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 2 - 1, h * 2 - 1), r * 2, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def viewfinder():
    """Camera-viewfinder corners and a REC dot drawn over the photo during the question."""
    im = Image.new("RGBA", (CW, CH))
    d = ImageDraw.Draw(im)
    L, m, wd = 90, 34, 9
    for (x, y, sx, sy) in ((m, m, 1, 1), (CW - m, m, -1, 1), (m, CH - m, 1, -1), (CW - m, CH - m, -1, -1)):
        d.line((x, y, x + sx * L, y), fill=(255, 255, 255, 235), width=wd)
        d.line((x, y, x, y + sy * L), fill=(255, 255, 255, 235), width=wd)
    cx, cy = CW / 2, CH / 2
    d.line((cx - 34, cy, cx + 34, cy), fill=(255, 255, 255, 150), width=4)
    d.line((cx, cy - 34, cx, cy + 34), fill=(255, 255, 255, 150), width=4)
    return im


def question_card():
    a = join(rtext("WHICH COUNTRY IS THIS IN?", 54, stroke=6), emoji("🌍", 56), gap=10)
    h = join(rtext("FAMOUS LANDMARK", 40, fill=GOLD, stroke=5), emoji("📸", 42), gap=10)
    pill = rounded_card(h.width + 40, h.height + 12, (h.height + 12) // 2, (40, 20, 70, 255), outline=GOLD + (255,),
                        width=3)
    paste_center(pill, h, pill.width / 2, pill.height / 2)
    card = rounded_card(max(a.width, pill.width) + 64, a.height + pill.height + 46, 44, (14, 6, 40, 232),
                        outline=CYAN + (255,), width=5)
    paste_center(card, a, card.width / 2, 20 + a.height / 2)
    paste_center(card, pill, card.width / 2, 27 + a.height + pill.height / 2)
    return card


def sfx_enhance():
    """A short rising digital chirp for each ENHANCE step."""
    t = np.arange(int(0.22 * SR)) / SR
    f = 600 + 2600 * (t / t[-1]) ** 1.5
    x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.35 + np.sin(2 * np.pi * np.cumsum(f * 2) / SR) * 0.3
    return x * np.exp(-t * 6) * np.minimum(1, t / 0.005)


def sfx_shutter():
    t = np.arange(int(0.18 * SR)) / SR
    n = np.random.default_rng(3).standard_normal(len(t))
    clicks = sum(np.exp(-np.maximum(t - d, 0) * 90) * (t >= d) for d in (0.0, 0.07))
    return (mv.highpass(n, 2500) * clicks * 0.8)


# ----------------------------------------------------------------------------
# rounds
# ----------------------------------------------------------------------------
class Round(mv.Scene):
    def __init__(self, idx, r, prev_tier, ui, tts):
        super().__init__()
        (key, lname, lemoji, code, fcode, cname, lonlat, focus, z0, fact, femoji, tier, prompt, said_l, said_c,
         stick, view) = r
        self.idx, self.ui, self.tier, self.key = idx, ui, tier, key
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        v_q = tts.say(prompt, speed=1.15) if tts else None
        v_l = tts.say(said_l, speed=1.15) if tts else None
        v_c = tts.say(said_c, speed=1.12) if tts else None
        q_len = len(v_q) / SR if v_q is not None else 1.4
        l_len = len(v_l) / SR if v_l is not None else 0.9
        c_len = len(v_c) / SR if v_c is not None else 0.6
        c0 = max(5 if self.bonus else 4, math.ceil((0.15 + q_len - 0.05) / B))
        n = 5 if self.bonus else 3
        self.count_beats = list(range(c0, c0 + n))
        self.reveal = (c0 + n) * B
        self.p2 = max(0.62, l_len + 0.12)                    # the whip to the globe, after the landmark's name
        self.dur = self.reveal + self.p2 + max(2.6, c_len + 1.9)
        self.dur = math.ceil(self.dur / B) * B
        self.cta_at = self.p2 + 1.9
        if self.cta:
            self.dur = math.ceil((self.reveal + self.cta_at + 3.0) / B) * B
        # photo
        self.photo = Image.open(os.path.join(PHOTO_DIR, key + ".jpg")).convert("RGB")
        pw, ph = self.photo.size
        a = CW / CH
        fw, fh = (pw, pw / a) if pw / ph < a else (ph * a, ph)
        self.full = (fw, fh)
        self.focus = (focus[0] * pw, focus[1] * ph)
        self.z0 = z0
        self.blocks = ([46, 30, 18, 10] if not self.danger else [62, 40, 24, 13])
        if self.bonus:
            self.blocks = [72, 52, 36, 24, 15, 9]
        self.zooms = [z0 ** (1 - k / (n + 1)) for k in range(n + 1)]
        self.clear = self.photo_at(1.0, 1)
        self.mask = ui["photo_mask"]
        # globe
        world = ui["globe"].world
        self.target = world.codes.index(code)
        cc, near, _ = world.country(code)
        near = list(near)                                   # only land near the main landmass gets the flag
        main = max(near, key=lambda i: world.lens[i])
        mp_ = world.P[world.starts[main]:world.starts[main] + world.lens[main]].mean(0)
        mp_ /= np.linalg.norm(mp_)

        def close(i):
            q = world.P[world.starts[i]:world.starts[i] + world.lens[i]].mean(0)
            return float(q @ mp_) / np.linalg.norm(q) > math.cos(math.radians(18))
        self.near = np.array([i for i in near if close(i)])
        if view is not None:
            self.gc, self.gR = G.unit(view[0], view[1]), view[2]
        else:
            self.gc = cc
            self.gR = float(np.clip(G.zoom_for(world, cc, self.near, W, H, 0.36, 0.22), 600, 9000))
        lon_c = math.degrees(math.atan2(self.gc[1], self.gc[0]))
        lat_c = math.degrees(math.asin(max(-1.0, min(1.0, float(self.gc[2])))))
        self.g_from = G.unit(lon_c - 70, lat_c * 0.4)
        self.spot = G.unit(*lonlat)
        self.flag = Image.open(os.path.join(FLAG_DIR, fcode + ".png")).convert("RGBA")
        self.cols = mm.flag_colours(self.flag)
        self.tiles = mm.Tiles(cname, tier in ("HARD", "INSANE", "IMPOSSIBLE", "BONUS"))
        self.pin = pq.pin_sprite("A", (235, 60, 75), lemoji)
        self.shadow = pq.pin_shadow()
        # name ribbon on the photo, and the polaroid it turns into
        size = 70
        while rfont(size).getlength(lname) > 700 and size > 40:
            size -= 2
        body = join(emoji(lemoji, size + 6), rtext(lname, size, fill=INK, stroke=0), gap=14)
        rb = rounded_card(body.width + 60, body.height + 28, 26, GOLD + (255,), outline=INK + (255,), width=6)
        paste_center(rb, body, rb.width / 2, rb.height / 2)
        self.ribbon = rb.rotate(-3, Image.BICUBIC, expand=True)
        pol = Image.new("RGBA", (CW + 56, CH + 56 + 150), (255, 255, 255, 255))
        pol.paste(self.clear, (28, 28))
        ps = 76
        while rfont(ps).getlength(lname) > CW - 40 and ps > 40:
            ps -= 2
        ImageDraw.Draw(pol).text((pol.width / 2, CH + 56 + 70), lname, font=rfont(ps), fill=INK, anchor="mm")
        self.polaroid = pol
        self.pol_shadow = Image.new("RGBA", (pol.width + 60, pol.height + 60))
        ImageDraw.Draw(self.pol_shadow).rectangle((30, 40, 30 + pol.width, 40 + pol.height), fill=(0, 0, 10, 150))
        self.pol_shadow = self.pol_shadow.filter(ImageFilter.GaussianBlur(14))
        fs = 42
        while rfont(fs).getlength(fact) > 780 and fs > 26:
            fs -= 1
        fb = join(emoji(femoji, 52), rtext(fact, fs, stroke=0), gap=14)
        self.fact = rounded_card(fb.width + 56, fb.height + 22, (fb.height + 22) // 2, INK + (232,))
        paste_center(self.fact, fb, self.fact.width / 2, self.fact.height / 2)
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
            self.banner = join(rtext(label, 66 if self.bonus else 100, fill=self.col, stroke=10), emoji(e, 96))
            self.sounds += [(0.0, mq.sfx_glitch(), 0.9), (0.02, mq.sfx_boom(), 0.6), (0.05, mq.sfx_levelup(), 0.6)]
        self.badge_q = mv.circle(150, (255, 255, 255, 255))
        ImageDraw.Draw(self.badge_q).text((75, 79), "?", font=rfont(100), fill=INK, anchor="mm")
        self.badges = {}
        for k in range(1, n + 1):
            bd = mv.circle(150, (255, 255, 255, 255))
            ImageDraw.Draw(bd).text((75, 79), str(k), font=rfont(104), fill=(235, 60, 75) if k == 1 else INK,
                                    anchor="mm")
            self.badges[k] = bd
        self.enh = {k: join(emoji("🔍", 40), rtext(f"ENHANCE x{k}" if k else "ZOOMED IN", 38, stroke=5), gap=8)
                    for k in range(n + 1)}
        self.streak = {k: join(rtext(f"x{k}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for k in (idx - 1, idx)}
        # sounds
        self.sounds += [(0.0, mq.sfx_boom(), 0.8), (0.0, mv.sfx_whoosh(0.4), 0.7), (0.05, sfx_shutter(), 0.8)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == n - 1), 0.9), (b * B, sfx_enhance(), 0.45),
                            (b * B, mv.sfx_whoosh(0.25), 0.35)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.85))
        if self.danger:
            self.sounds.append((self.count_beats[-1] * B, mq.sfx_boom(), 0.6))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        rv0, p2 = self.reveal, self.reveal + self.p2
        self.sounds += [(rv0, mq.sfx_boom(), 1.0), (rv0, sfx_shutter(), 1.0), (rv0 + 0.02, mv.sfx_ding(), 0.9),
                        (rv0 + 0.1, mv.sfx_pop(), 0.7),
                        (p2, mv.sfx_whoosh(0.6), 0.9), (p2, mq.sfx_glitch(), 0.4), (p2 + 0.55, mq.sfx_boom(), 0.6),
                        (p2 + 0.95, mv.sfx_pop(), 0.9), (p2 + 0.97, mq.sfx_pling(), 0.6),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        for i in range(len(self.tiles.pos)):
            self.sounds.append((p2 + 0.1 + 0.035 * i, mv.sfx_click(), 0.45))
        if tts:
            self.voices.append((0.15, v_q))
            self.voices.append((rv0 + 0.05, v_l))
            self.voices.append((p2 + 0.12, v_c))
            if self.cta:
                self.voices.append((rv0 + self.cta_at, tts.say(CTA_LINE, speed=1.12)))
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            ca = rv0 + self.cta_at
            self.sounds += [(ca, mv.sfx_pop(), 0.9), (ca + 0.02, mq.sfx_pling(), 0.5), (ca + 0.45, mv.sfx_click(), 0.8)]
        rr = random.Random(idx * 59)
        self.conf = [(rr.uniform(-1, 1) * 700, rr.uniform(-1300, -450), rr.randint(12, 26), rr.choice(self.cols),
                      rr.uniform(0, 3)) for _ in range(70)]

    # ---- photo ----
    def photo_at(self, z, block):
        pw, ph = self.photo.size
        fw, fh = self.full
        w, h = fw / z, fh / z
        cx = min(max(self.focus[0], w / 2), pw - w / 2)
        cy = min(max(self.focus[1], h / 2), ph - h / 2)
        if z <= 1.0001:
            cx = min(max(pw / 2 + (self.focus[0] - pw / 2) * 0.0, w / 2), pw - w / 2)
            cy = min(max(ph / 2, h / 2), ph - h / 2)
        im = self.photo.crop((int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2)))
        im = im.resize((CW, CH), Image.BILINEAR)
        if block > 1:
            im = im.resize((max(1, CW // block), max(1, CH // block)), Image.BILINEAR).resize((CW, CH), Image.NEAREST)
        return im

    def step(self, t):
        """How many ENHANCE steps have happened, and how long ago the last one was."""
        k, since = 0, t
        for j, b in enumerate(self.count_beats):
            if t >= b * B:
                k, since = j + 1, t - b * B
        return k, since

    def card_image(self, t, rv):
        if rv > 0:
            img = self.clear
        else:
            k, since = self.step(t)
            zk = self.zooms[k]
            zprev = self.zooms[k - 1] if k > 0 else zk * 1.06
            e = ease_out_cubic(clamp(since / 0.22)) if k > 0 else ease_out_cubic(clamp(t / 0.4))
            z = zprev + (zk - zprev) * e
            z *= 1 + 0.015 * math.sin(t * 2.2)                  # a slow drift while you think
            img = self.photo_at(z, self.blocks[k])
        card = Image.new("RGBA", (CW + 28, CH + 28))
        ImageDraw.Draw(card).rounded_rectangle((0, 0, CW + 27, CH + 27), 42, fill=(255, 255, 255, 255))
        ph = img.convert("RGBA")
        ph.putalpha(self.mask)
        card.alpha_composite(ph, (14, 14))
        if rv <= 0:
            card.alpha_composite(self.ui["finder"], (14, 14))
            k, since = self.step(t)
            if k > 0 and since < 0.3:                        # scanner line sweeping down on each ENHANCE
                y = 14 + CH * ease_in_out(since / 0.3)
                d = ImageDraw.Draw(card, "RGBA")
                d.rectangle((14, y - 40, 14 + CW, y), fill=CYAN + (50,))
                d.line((14, y, 14 + CW, y), fill=(200, 255, 255, 255), width=6)
            if int(t * 2.5) % 2 == 0:                        # blinking REC dot
                ImageDraw.Draw(card).ellipse((CW - 70, 50, CW - 44, 76), fill=(235, 40, 50, 255))
        return card

    def background(self, T):
        if self.idx not in BG_CACHE:
            BG_CACHE.clear()
            pw, ph = self.photo.size
            s = max(W / pw, H / ph)
            bg = self.photo.resize((int(pw * s) + 1, int(ph * s) + 1), Image.BILINEAR)
            bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W,
                          (bg.height - H) // 2 + H)).filter(ImageFilter.GaussianBlur(26)).convert("RGBA")
            bg.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 150)))
            BG_CACHE[self.idx] = bg
        return BG_CACHE[self.idx]

    # ---- globe ----
    def globe_view(self, t2):
        k = ease_in_out(clamp(t2 / 0.85))
        c = G.slerp(self.g_from, self.gc, k)
        R = math.exp(math.log(470) + (math.log(self.gR) - math.log(470)) * k)
        return c, R * (1 + 0.04 * clamp((t2 - 0.85) / 3)), 1 - clamp(abs(k - 0.5) * 2) if t2 < 0.85 else 0.0

    def render(self, t, header=True):
        T = self.t0 + t
        rv = t - self.reveal
        t2 = rv - self.p2
        ui = self.ui
        if t2 < 0.25:                                       # the photo world: blurred backdrop
            im = self.background(T).copy()
            if self.danger and 0 < t < self.reveal:
                im.alpha_composite(ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        else:
            im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        pin_xy = None
        if t2 > 0:                                          # the globe flies in from space
            c, R, blur = self.globe_view(t2)
            hl = clamp((t2 - 0.55) / 0.2)
            fa = 0.95 * clamp((t2 - 0.6) / 0.3)
            lift = 16 * ease_out_back(clamp((t2 - 0.7) / 0.3))
            g = ui["globe"].render(c, R, GC, self.near if hl > 0 else None, hl, self.flag, fa, lift=lift)
            ui["cmap"].draw(g, c, R, GC, self.target if hl > 0 else None, 0.75 * (1 - 0.4 * hl), 0.0,
                            lift=lift)
            g = mm.zoom_blur(g, blur)
            g.alpha_composite(ui["shade"])
            ga = clamp(t2 / 0.25)
            if ga < 1:
                g.putalpha(g.getchannel("A").point(lambda v, a=ga: int(v * a)))
            im.alpha_composite(g)
            if t2 < 0.5:
                im.alpha_composite(cq.speed_lines(1 - t2 / 0.5, self.idx, GC))
            x, y, vis = cap.project(self.spot, c, R, GC)
            if vis and t2 > 0.85:
                pin_xy = (x, y - lift * clamp((t2 - 0.7) / 0.3) * 0)
        # header
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
        qa = 1 - clamp(t2 / 0.3)                             # the question card makes room for the polaroid
        if kc > 0.01 and qa > 0.01:
            paste_center(im, scaled(ui["card"], kc * (1 + 0.015 * beat_pulse(T)) * (0.8 + 0.2 * qa)), W / 2, CARD_Y,
                         qa)
        # the pin (under the polaroid's string end)
        pol_xy = None
        if pin_xy is not None:
            px, py = pin_xy
            kp = clamp((t2 - 0.85) / 0.22)
            fall = (1 - ease_out_back(kp, 2.0)) * 700
            for j in range(3):
                tl = t2 - 0.95 - 0.09 * j
                if 0 < tl < 0.5:
                    cap.ring(im, px, py, 20 + 190 * ease_out_cubic(tl / 0.5), GREEN, 255 * (1 - tl / 0.5), 9, 0.42)
            paste_center(im, self.shadow, px, py, kp)
            sp = scaled(self.pin, 1.15 + 0.04 * beat_pulse(T))
            im.alpha_composite(sp, (int(px - sp.width / 2), int(py - sp.height - fall)))
        # the photo card, then the polaroid
        if t2 <= 0:
            k_in = clamp(t / 0.16)
            s = (1.25 - 0.25 * ease_out_cubic(k_in)) * (1 + 0.01 * beat_pulse(T))
            if rv <= 0:
                for b in self.count_beats:                   # punch on every ENHANCE
                    tb = t - b * B
                    if 0 <= tb < 0.2:
                        s *= 1 + 0.05 * (1 - ease_out_cubic(tb / 0.2))
            else:
                s *= 1 + 0.07 * (1 - ease_out_cubic(clamp(rv / 0.3)))
            card = self.card_image(t, rv)
            rot = 4 * (1 - ease_out_cubic(k_in)) * (1 if self.idx % 2 else -1)
            sc_ = scaled(card, s)
            if abs(rot) > 0.05:
                sc_ = sc_.rotate(rot, Image.BICUBIC, expand=True)
            paste_center(im, sc_, *CARD_C, min(1.0, k_in * 2))
            if rv <= 0:                                      # countdown badge on the card's corner
                badge = self.badge_q
                for j, b in enumerate(self.count_beats):
                    tb = t - b * B
                    if 0 <= tb < B:
                        badge = scaled(self.badges[len(self.count_beats) - j],
                                       1 + 0.25 * (1 - ease_out_cubic(tb / 0.14)))
                paste_center(im, scaled(badge, 1 + 0.06 * beat_pulse(T)), CARD_C[0] + CW / 2 - 40,
                             CARD_C[1] - CH / 2 + 40)
                k, since = self.step(t)
                en = scaled(self.enh[k], 1 + 0.2 * (1 - ease_out_cubic(clamp(since / 0.2))) if k else 1.0)
                pill = rounded_card(en.width + 40, en.height + 16, (en.height + 16) // 2, (12, 10, 30, 220),
                                    outline=CYAN + (255,), width=3)
                paste_center(pill, en, pill.width / 2, pill.height / 2)
                paste_center(im, pill, CARD_C[0], CARD_C[1] + CH / 2 - 50)
            else:                                            # the landmark's name stamps across the photo
                kr = ease_out_back(clamp((rv - 0.05) / 0.22), 2.4)
                if kr > 0.01:
                    paste_center(im, scaled(self.ribbon, 1.6 - 0.6 * kr), CARD_C[0], CARD_C[1] + CH / 2 - 80,
                                 min(1.0, kr))
        else:
            k = ease_in_out(clamp(t2 / 0.5))
            if pin_xy is not None or t2 < 0.9:
                right = (pin_xy[0] if pin_xy else self.side_hint()) < W / 2
            else:
                right = self.side_hint() < W / 2
            tx, ty = (775 if right else 305), 690
            s = 1 + (0.34 - 1) * k
            cx = CARD_C[0] + (tx - CARD_C[0]) * k
            cy = CARD_C[1] + (ty - CARD_C[1]) * k
            rot = (6 if right else -6) * k + 2 * math.sin(T * 1.5) * k
            pol = scaled(self.polaroid, s)
            paste_center(im, scaled(self.pol_shadow, s), cx + 10, cy + 14)
            pol = pol.rotate(rot, Image.BICUBIC, expand=True)
            paste_center(im, pol, cx, cy)
            pol_xy = (cx, cy + self.polaroid.height * s / 2 - 12)
            if pin_xy is not None and t2 > 1.05:             # a string from the pin to the polaroid
                px, py = pin_xy
                hy = py - self.pin.height * 1.15 + 30
                ka = clamp((t2 - 1.05) / 0.2)
                ex, ey = px + (pol_xy[0] - px) * ka, hy + (pol_xy[1] - hy) * ka
                d = ImageDraw.Draw(im)
                d.line((px, hy, ex, ey), fill=INK + (255,), width=9)
                d.line((px, hy, ex, ey), fill=(255, 255, 255, 255), width=5)
                ImageDraw.Draw(im).ellipse((pol_xy[0] - 12, pol_xy[1] - 12, pol_xy[0] + 12, pol_xy[1] + 12),
                                           fill=(235, 60, 75, 255), outline=INK + (255,), width=3) if ka >= 1 else None
        # tiles: hidden length during the question, the country's name after the whip
        self.tiles.draw(im, t - 0.6, t2)
        if self.banner is not None and 0.05 < t < 1.0:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - 0.7) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, CARD_C[1], a)
        cta_on = self.cta and rv > self.cta_at
        if t2 > 0:
            if pin_xy is not None and t2 > 0.95:
                cx_, cy_ = pin_xy
                kc_ = t2 - 0.95
                for vx, vy, sz, cc, spin in self.conf:
                    px, py = cx_ + vx * kc_, cy_ + vy * kc_ + 2400 * kc_ * kc_
                    if py < H:
                        w2 = sz * abs(math.cos(spin + kc_ * 9))
                        dd = ImageDraw.Draw(im)
                        dd.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                     outline=INK + (255,))
            sk = ease_out_back((t2 - 0.6) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(t2 * 7), Image.BICUBIC, expand=True),
                             120 if (pin_xy and pin_xy[0] > W / 2) else 960, 1480)
            fk = ease_out_back((t2 - 1.1) / 0.3)
            if fk > 0.01 and not cta_on:
                paste_center(im, scaled(self.fact, fk), W / 2, FACT_Y)
            if t2 < 0.2:                                     # the whip
                im = rgb_split(mm.zoom_blur(im, 0.7 * (1 - t2 / 0.2)), 20 * (1 - t2 / 0.2))
            if 0.55 < t2 < 0.8:
                im = shake(im, 18 * (1 - (t2 - 0.55) / 0.25), t)
        if 0 < rv and t2 <= 0:                               # the snap to sharp
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(220 * fl))))
            im = shake(im, 30 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 18 * (1 - rv / 0.18))
        elif rv <= 0:
            for b in self.count_beats:
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 14 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 12 * (1 - tb / 0.15))
                if 0 <= tb < 0.05:
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

    def side_hint(self):
        """Screen x of the landmark at the end of the fly-in (where the pin will be)."""
        x, _, _ = cap.project(self.spot, self.gc, self.gR, GC)
        return x


# ----------------------------------------------------------------------------
# intro: the title, said and slammed in word by word over pixelated landmarks, then the title card
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    SHOW = (10, 8, 9)

    def __init__(self, ui, tts, rounds):
        super().__init__()
        self.ui, self.rounds = ui, rounds
        self.dur = 6 * B
        hb = 0.5 * B
        clips = [tts.say(w, speed=1.24) for w in INTRO_WORDS] if tts else None
        lens = [len(c) / SR for c in clips] if clips else [0.75, 0.85, 1.0]
        self.slams = [0.0]
        for ln in lens:
            prev = self.slams[-1]
            self.slams.append(max(prev + hb, round((prev + ln - 0.08) / hb) * hb))
        self.slams[-1] = min(self.slams[-1], self.dur - 0.4)
        if clips:
            for at, c in zip(self.slams, clips):
                self.voices.append((at, c))
        self.o3 = join(rtext("answer at the end", 58, fill=GOLD, stroke=7), emoji("👀", 62))
        self.w1 = fit(rtext("GUESS THE COUNTRY", 130, stroke=12), 990)
        self.w2 = fit(join(rtext("BY ITS LANDMARK", 116, fill=GOLD, stroke=11), emoji("🗼", 104), gap=12), 990)
        self.w3 = join(rtext("99% FAIL", 150, fill=PINK, stroke=14), emoji("💀", 140))
        self.l1 = fit(rtext("GUESS THE COUNTRY", 112, stroke=11), 990)
        self.l2 = fit(join(rtext("BY ITS LANDMARK", 100, fill=GOLD, stroke=10), emoji("🗼", 90), gap=12), 990)
        self.l3 = join(rtext("99% FAIL", 116, fill=PINK, stroke=11), emoji("💀", 112))
        self.minis = [scaled(r.polaroid, 0.24).rotate(random.Random(i).uniform(-12, 12), Image.BICUBIC, expand=True)
                      for i, r in enumerate(rounds[:8])]
        self.sounds += [(0.0, sfx_heartbeat(), 0.8), (0.0, sfx_shutter(), 0.8),
                        (self.slams[2], mv.sfx_riser(self.slams[3] - self.slams[2]), 0.6),
                        (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k, at in enumerate(self.slams):
            self.sounds += [(at, mq.sfx_boom(), 1.0 if k in (0, 3) else 0.75), (at, mv.sfx_whoosh(0.35), 0.6),
                            (at, mv.sfx_pop(), 0.8)]
            if k:
                self.sounds += [(at, mq.sfx_glitch(), 0.45), (at, sfx_shutter(), 0.6)]

    def render(self, t):
        T = self.t0 + t
        k = max(i for i, at in enumerate(self.slams) if at <= t + 1e-9)
        ts = t - self.slams[k]
        slam = 1 + 0.35 * (1 - ease_out_cubic(clamp(ts / 0.18)))
        if k < 3:                                            # word slams over pixelated landmarks
            r = self.rounds[self.SHOW[k]]
            im = r.render(r.count_beats[0] * B - 0.1)
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 120)))
            words = [(self.w1, 820, -3), (self.w2, 990, 2), (self.w3, 1190, -2)]
            for j in range(k + 1):
                img, y, rot = words[j]
                sc = (slam if j == k else 1.0) * (1 + 0.025 * beat_pulse(T))
                paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
            paste_center(im, self.o3, W / 2, 1745)
            im = shake(im, 24 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
            im = rgb_split(im, (8 if k == 0 else 16) * (1 - clamp(ts / 0.15)))
            if k > 0:
                im = mm.zoom_blur(im, 0.6 * (1 - clamp(ts / 0.1)))
                if ts < 0.06:
                    im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 140)))
            return im
        gc = (540, 1270)                                     # title card, polaroids flying out of the globe
        R = 470 * (1 + 0.05 * beat_pulse(T)) * (1.25 - 0.25 * ease_out_cubic(clamp(ts / 0.3)))
        c = G.unit(10 + 50 * t, 25)
        im = self.ui["globe"].render(c, R, gc)
        self.ui["cmap"].draw(im, c, R, gc, None, 0.75 + 0.2 * beat_pulse(T))
        im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 40)))
        for j, mini in enumerate(self.minis):
            ang = j * (2 * math.pi / len(self.minis)) + 0.4
            rr = 150 + 820 * ease_out_cubic(clamp(ts / 0.7))
            paste_center(im, mini, gc[0] + rr * math.cos(ang), gc[1] - 120 + rr * math.sin(ang) * 0.9)
        for j, (img, y, rot) in enumerate([(self.l1, 330, -3), (self.l2, 490, 2), (self.l3, 660, -2)]):
            sc = (slam if j == 2 else 1 + 0.12 * (1 - ease_out_cubic(clamp(ts / 0.18)))) * (1 + 0.03 * beat_pulse(T))
            paste_center(im, scaled(img, sc).rotate(rot, Image.BICUBIC, expand=True), W / 2, y)
        im = shake(im, 22 * (1 - ts / 0.3) if ts < 0.3 else 0, t)
        if ts < 0.08:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - ts / 0.08)))))
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
    ui = {"globe": globe, "big_globe": globe, "shade": mm.shade_overlay(0.7),
          "vig": [mc.red_vignette(i / 10) for i in range(11)], "cmap": mcq.ColourMap(world),
          "card": question_card(), "photo_mask": rounded_mask(CW, CH, 30), "finder": viewfinder()}
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
    c = G.unit(20, 20)
    im = ui["globe"].render(c, 560, (540, 1250))
    ui["cmap"].draw(im, c, 560, (540, 1250), None, 0.8)
    im.alpha_composite(Image.new("RGBA", (W, H), (10, 0, 30, 70)))
    spots = [(0, 270, 960, -9), (3, 800, 900, 8), (8, 290, 1420, 7), (9, 790, 1440, -7)]
    for k, x, y, rot in spots:                               # four polaroids, the Moai one pixelated
        r = rounds[k]
        pol = r.polaroid.copy()
        if k == 9:
            pol.paste(r.photo_at(1.6, 34), (28, 28))
            ImageDraw.Draw(pol).rectangle((0, CH + 60, pol.width, pol.height), fill=(255, 255, 255, 255))
            ImageDraw.Draw(pol).text((pol.width / 2, CH + 56 + 70), "???", font=rfont(90), fill=INK, anchor="mm")
        p = scaled(pol, 0.42)
        paste_center(im, scaled(r.pol_shadow, 0.42), x + 10, y + 14)
        paste_center(im, p.rotate(rot, Image.BICUBIC, expand=True), x, y)
    paste_center(im, fit(rtext("GUESS THE COUNTRY", 112, stroke=11), 1000).rotate(-3, Image.BICUBIC, expand=True),
                 W / 2, 215)
    paste_center(im, fit(join(rtext("BY ITS LANDMARK", 104, fill=GOLD, stroke=10), emoji("🗼", 94), gap=12), 1000)
                 .rotate(2, Image.BICUBIC, expand=True), W / 2, 370)
    paste_center(im, join(rtext("99% FAIL", 104, fill=PINK, stroke=10), emoji("💀", 104)), W / 2, 1790)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_landmark_quiz.mp4"))
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
        make_cover(scenes, ui, os.path.join(HERE, "landmark_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"lm_{float(s):06.2f}.png")
            mv.frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return
    import make_movie_quiz as mmq
    work = os.path.join(mv.CACHE_DIR, "render_landmark")
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
