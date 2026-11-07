#!/usr/bin/env python3
""""GUESS THE FOOTBALL CLUB" Short (1080x1920), edited like the crazy map quiz.

Every crest starts as a blocky mosaic that sharpens on each beat of the 3-2-1, then snaps into focus
on the drop. Night-stadium background (floodlights, sweeping beams, camera flashes, pitch lines),
130 BPM phonk, level banners, glitches, shakes, RGB split, streak counter, letter tiles, one
"like this video" call-out, and an ending that loops back into the first frame.

Logos: club crests from Wikimedia (club_logos/, not committed: they are the clubs' trademarks).

    python3 make_club_quiz.py --voice-pack voice_packs/club_adam,voice_packs/map3_adam
    python3 make_club_quiz.py --stills 1,9,12
    python3 make_club_quiz.py --cover
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

import brand  # noqa: E402
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
LOGO_DIR = os.path.join(HERE, "club_logos")
LOGO_C = (540, 800)               # where the crest sits
LOGO_BOX = 600
NUM_Y = 330
FLY_BEATS = 3
TIERS = mc.TIERS
CTA_AFTER, CTA_LINE, CTA_AT, CTA_BEATS, CTA_Y = (3,), mc.CTA_LINE, 2 * B, 5, 1585

# mosaic block size (px) before the countdown, then on each count beat
BLOCKS = {"EASY": (72, [50, 33, 22]), "HARD": (84, [62, 44, 30]), "INSANE": (96, [74, 54, 38]),
          "IMPOSSIBLE": (110, [86, 64, 48]), "BONUS": (124, [104, 88, 74, 62, 52])}

CLUBS = [  # logo file, tiles, spoken answer, fact, fact emoji, tier, prompt, reaction sticker
    ("real_madrid", "REAL MADRID", "Real Madrid!", "founded 1902, nicknamed Los Blancos", "👑", "EASY",
     "Guess the club!", "😎"),
    ("barcelona", "BARCELONA", "Barcelona!", "founded 1899, nicknamed Blaugrana", "🔵", "EASY", "Next!", "🔥"),
    ("man_united", "MAN UNITED", "Manchester United!", "founded 1878, the Red Devils", "😈", "EASY", "Too easy?",
     "🤔"),
    ("bayern", "BAYERN MUNICH", "Bayern Munich!", "founded 1900, nicknamed Die Roten", "🥨", "HARD", "Hard level!",
     "😳"),
    ("juventus", "JUVENTUS", "Juventus!", "founded 1897, nicknamed the Old Lady", "🦓", "HARD", "Think fast!", "🤯"),
    ("chelsea", "CHELSEA", "Chelsea!", "founded 1905, nicknamed the Blues", "🦁", "HARD", "Ooh, tricky!", "🔥"),
    ("dortmund", "DORTMUND", "Borussia Dortmund!", "its home stand is the Yellow Wall", "🟡", "INSANE",
     "Insane level!", "😱"),
    ("ajax", "AJAX", "Ajax!", "founded 1900 in Amsterdam", "🌷", "INSANE", "No way!", "💀"),
    ("benfica", "BENFICA", "Benfica!", "founded 1904, nicknamed the Eagles", "🦅", "INSANE", "Only geniuses!", "🧠"),
    ("galatasaray", "GALATASARAY", "Galatasaray!", "founded 1905, nicknamed the Lions", "🦁", "IMPOSSIBLE",
     "Impossible level!", "☠"),
    ("boca", "BOCA JUNIORS", "Boca Juniors!", "they play at La Bombonera", "🏟", "BONUS",
     "Bonus! Only one percent!", "👑"),
]
INTRO_LINE = "Only real football fans can name all ten!"
END_LINE = "How many did you get? Comment your score!"
ALL_LINES = [INTRO_LINE] + [x for c in CLUBS for x in (c[6], c[2])] + [CTA_LINE, END_LINE]


# ----------------------------------------------------------------------------
# crests
# ----------------------------------------------------------------------------
def load_logo(key, box=LOGO_BOX):
    im = Image.open(os.path.join(LOGO_DIR, key + ".png")).convert("RGBA")
    if key == "juventus":                       # the black crest disappears at night: use it in white
        a = np.asarray(im).copy()
        a[..., :3] = 255
        im = Image.fromarray(a, "RGBA")
    im.thumbnail((box, box), Image.LANCZOS)
    return im


def logo_colours(im):
    a = np.asarray(im.convert("RGBA").resize((80, 80)))
    px = a[a[..., 3] > 200][:, :3]
    if len(px) < 10:
        return [(255, 255, 255)]
    q = Image.fromarray(px.reshape(1, -1, 3).astype(np.uint8), "RGB").quantize(5)
    pal = q.getpalette()
    cols = [tuple(pal[i * 3:i * 3 + 3]) for n, i in sorted(q.getcolors(), reverse=True) if n > 0.06 * len(px)]
    return cols or [(255, 255, 255)]


def mosaic(im, b):
    """Blocky pixelation with b-px blocks (alpha included, premultiplied so edges stay clean)."""
    if b <= 1:
        return im
    w, h = im.size
    sw, sh = max(1, math.ceil(w / b)), max(1, math.ceil(h / b))
    small = im.convert("RGBa").resize((sw, sh), Image.BOX)
    big = small.resize((sw * b, sh * b), Image.NEAREST).convert("RGBA")
    ox, oy = (sw * b - w) // 2, (sh * b - h) // 2
    return big.crop((ox, oy, ox + w, oy + h))


def sticker(im, outline=10):
    """The crest on a white sticker edge with a soft dark shadow, so any colour reads on the night sky."""
    pad = outline * 3
    w, h = im.width + 2 * pad, im.height + 2 * pad
    base = Image.new("RGBA", (w, h))
    alpha = Image.new("L", (w, h))
    alpha.paste(im.getchannel("A"), (pad, pad))
    edge = alpha.filter(ImageFilter.MaxFilter(outline * 2 + 1))
    shadow = edge.filter(ImageFilter.GaussianBlur(outline))
    base.paste(Image.new("RGBA", (w, h), (0, 0, 10, 170)), (0, 8), shadow)
    base.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), edge)
    base.alpha_composite(im, (pad, pad))
    return base


# ----------------------------------------------------------------------------
# night stadium
# ----------------------------------------------------------------------------
class Stadium:
    HORIZON = 1240

    def __init__(self):
        rnd = random.Random(5)
        ys = np.arange(H)[:, None]
        sky = np.zeros((H, W, 3), np.float32)
        t = np.clip(ys / self.HORIZON, 0, 1)
        top, mid = np.array([5, 8, 28]), np.array([16, 30, 78])
        sky[:] = top + (mid - top) * (t ** 1.3)[..., None]
        im = Image.fromarray(sky.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
        d = ImageDraw.Draw(im)
        # stands: dark tiers full of tiny crowd lights
        y0, y1 = 880, self.HORIZON
        d.polygon([(0, y0 + 40), (W, y0 + 40), (W, y1), (0, y1)], fill=(9, 12, 32, 255))
        d.polygon([(0, y0), (W, y0), (W, y0 + 40), (0, y0 + 40)], fill=(20, 26, 60, 255))
        for _ in range(2600):
            x, y = rnd.uniform(0, W), rnd.uniform(y0 + 46, y1 - 6)
            c = rnd.choice([(255, 255, 255), (255, 210, 120), (120, 180, 255), (255, 120, 140)])
            a = int(rnd.uniform(25, 110))
            d.ellipse((x - 1.6, y - 1.6, x + 1.6, y + 1.6), fill=c + (a,))
        # pitch in perspective
        pitch = Image.new("RGBA", (W, H))
        pd = ImageDraw.Draw(pitch)
        n = 14
        for i in range(n):
            a0, a1 = (i / n) ** 1.7, ((i + 1) / n) ** 1.7
            ya, yb = y1 + (H - y1) * a0, y1 + (H - y1) * a1
            pd.rectangle((0, ya, W, yb + 1), fill=(18, 92, 44, 255) if i % 2 else (14, 76, 36, 255))
        vx, vy = W / 2, 520                                       # vanishing point
        for sx in (-520, W + 520):                               # touchlines
            k = (y1 - vy) / (H - vy)
            pd.line([(vx + (sx - vx) * k, y1), (sx, H)], fill=(235, 255, 235, 150), width=7)
        hy = 1560
        pd.line([(0, hy), (W, hy)], fill=(235, 255, 235, 170), width=7)
        pd.ellipse((540 - 330, hy - 96, 540 + 330, hy + 96), outline=(235, 255, 235, 170), width=7)
        pd.ellipse((540 - 12, hy - 5, 540 + 12, hy + 5), fill=(235, 255, 235, 200))
        im.alpha_composite(pitch)
        fog = np.zeros((H, W, 4), np.uint8)
        fy = np.clip(1 - np.abs(ys - y1) / 260, 0, 1)
        fog[..., :3] = (60, 90, 160)
        fog[..., 3] = (fy * 90).astype(np.uint8)
        im.alpha_composite(Image.fromarray(fog, "RGBA"))
        # floodlight towers + their glow
        glow = Image.new("RGBA", (W // 4, H // 4))
        gd = ImageDraw.Draw(glow)
        self.lamps = []
        for cx in (120, W - 120):
            gd.ellipse((cx / 4 - 70, 330 / 4 - 50, cx / 4 + 70, 330 / 4 + 50), fill=(200, 220, 255, 120))
            for r in range(3):
                for c in range(4):
                    self.lamps.append((cx - 66 + c * 44, 300 + r * 30))
        glow = glow.filter(ImageFilter.GaussianBlur(14)).resize((W, H), Image.BILINEAR)
        im.alpha_composite(glow)
        d = ImageDraw.Draw(im)
        for x, y in self.lamps:
            d.rounded_rectangle((x - 16, y - 11, x + 16, y + 11), 5, fill=(255, 255, 255, 255))
        for cx in (120, W - 120):
            d.rectangle((cx - 8, 345, cx + 8, 880), fill=(18, 22, 46, 255))
        self.base = im
        self.beams = self._beams()
        self.vig = Image.fromarray(self._vignette(), "RGBA")
        self.rays = {}

    def _beams(self):
        out = []
        for k in range(24):                                      # beams sway slowly; precomputed poses
            ph = k / 24 * 2 * math.pi
            im = Image.new("RGBA", (W // 4, H // 4))
            d = ImageDraw.Draw(im)
            for cx, side in ((120, 1), (W - 120, -1)):
                for j, base_a in enumerate((0.35, 0.75)):
                    a = base_a + 0.12 * math.sin(ph + j * 1.7) * side
                    tx = cx + side * math.tan(a) * 1400
                    pts = [(cx / 4, 330 / 4), ((tx - 160) / 4, 1700 / 4), ((tx + 160) / 4, 1700 / 4)]
                    d.polygon(pts, fill=(190, 215, 255, 38))
            out.append(im.filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR))
        return out

    def _vignette(self):
        ys, xs = np.mgrid[0:H, 0:W]
        dd = np.sqrt(((xs - W / 2) / (W * 0.7)) ** 2 + ((ys - H / 2) / (H * 0.62)) ** 2)
        a = np.zeros((H, W, 4), np.uint8)
        a[..., 3] = (np.clip(dd - 0.6, 0, 1) * 330).clip(0, 190).astype(np.uint8)
        return a

    def ray_layer(self, col):
        if col not in self.rays:
            S = 1500
            im = Image.new("RGBA", (S, S))
            d = ImageDraw.Draw(im)
            for i in range(16):
                a0, a1 = (i - 0.22) * 2 * math.pi / 16, (i + 0.22) * 2 * math.pi / 16
                d.polygon([(S / 2, S / 2), (S / 2 + S * math.cos(a0), S / 2 + S * math.sin(a0)),
                           (S / 2 + S * math.cos(a1), S / 2 + S * math.sin(a1))], fill=col + (46,))
            g = Image.new("L", (S, S))
            ImageDraw.Draw(g).ellipse((S * 0.12, S * 0.12, S * 0.88, S * 0.88), fill=255)
            g = g.filter(ImageFilter.GaussianBlur(160))
            im.putalpha(Image.fromarray((np.asarray(im.getchannel("A")).astype(np.float32) *
                                         np.asarray(g) / 255).astype(np.uint8)))
            glow = mv.soft_circle(760, col + (120,), 120) if hasattr(mv, "soft_circle") else None
            frames = []
            for k in range(12):
                fr = im.rotate(k * 22.5 / 12, Image.BILINEAR)
                if glow is not None:
                    paste_center(fr, glow, S / 2, S / 2)
                frames.append(fr)
            self.rays[col] = frames
        return self.rays[col]

    def render(self, T, col=None, strobe=0.0, rays=1.0):
        im = self.base.copy()
        im.alpha_composite(self.beams[int(T * 3) % len(self.beams)])
        d = ImageDraw.Draw(im)
        r = random.Random(int(T * FPS))
        for _ in range(7):                                       # camera flashes in the crowd
            x, y = r.uniform(0, W), r.uniform(930, 1225)
            s = r.uniform(3, 7)
            d.ellipse((x - s * 2.4, y - s * 2.4, x + s * 2.4, y + s * 2.4), fill=(255, 255, 255, 50))
            d.ellipse((x - s, y - s, x + s, y + s), fill=(255, 255, 255, 230))
        if col is not None and rays > 0.01:
            fr = self.ray_layer(col)[int(T * 12) % 12]
            paste_center(im, fr, LOGO_C[0], LOGO_C[1], rays)
        im.alpha_composite(self.vig)
        if strobe > 0.01:
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(40 * strobe))))
        return im


def speed_lines(k, seed, c=LOGO_C):
    im = Image.new("RGBA", (W, H))
    if k <= 0.02:
        return im
    d = ImageDraw.Draw(im)
    r = random.Random(seed)
    for _ in range(46):
        a = r.uniform(0, 2 * math.pi)
        r0, r1 = r.uniform(430, 620), r.uniform(1100, 1500)
        p0 = (c[0] + r0 * math.cos(a), c[1] + r0 * math.sin(a))
        p1 = (c[0] + r1 * math.cos(a + 0.015), c[1] + r1 * math.sin(a + 0.015))
        p2 = (c[0] + r1 * math.cos(a - 0.015), c[1] + r1 * math.sin(a - 0.015))
        d.polygon([p0, p1, p2], fill=(255, 255, 255, int(170 * k)))
    return im


def shockwave(im, rv, col):
    if not 0 < rv < 0.5:
        return
    k = rv / 0.5
    rr = 300 + 520 * ease_out_cubic(k)
    d = ImageDraw.Draw(im)
    d.ellipse((LOGO_C[0] - rr, LOGO_C[1] - rr, LOGO_C[0] + rr, LOGO_C[1] + rr), outline=col + (int(255 * (1 - k)),),
              width=max(1, int(26 * (1 - k))))


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------
class Intro(mv.Scene):
    """6 beats: cold open on the mosaic bonus crest, a rapid montage of mystery crests, then the title slams."""

    TEASE, MONTAGE = "boca", ("galatasaray", "benfica", "ajax", "dortmund")

    def __init__(self, ui, tts):
        super().__init__()
        self.ui = ui
        self.dur = 6 * B
        self.t1, self.t2 = 1.5 * B, 3.5 * B
        self.tease = sticker(mosaic(load_logo(self.TEASE, 640), 92))
        self.cuts = [sticker(mosaic(load_logo(k, 600), 70)) for k in self.MONTAGE]
        self.o1 = rtext("ONLY 1% KNOW", 124, fill=PINK, stroke=12)
        self.o2 = rtext("THIS CLUB", 128, stroke=11)
        self.q = rtext("?", 300, stroke=18)
        self.o3 = join(rtext("answer at the end", 60, fill=GOLD, stroke=7), emoji("👀", 64))
        self.m1 = rtext("CAN YOU NAME", 108, stroke=10)
        self.m2 = rtext("ALL OF THEM?", 120, fill=CYAN, stroke=11)
        self.l1 = rtext("GUESS THE", 150, stroke=13)
        self.l2 = join(rtext("CLUB", 230, fill=CYAN, stroke=16), emoji("⚽", 190), gap=20)
        self.l3 = join(rtext("99% FAIL", 120, fill=GOLD, stroke=11), emoji("💀", 120))
        self.sounds += [(0.0, mq.sfx_boom(), 1.0), (0.0, mv.sfx_whoosh(0.4), 0.6), (0.02, sfx_heartbeat(), 0.9),
                        (B, sfx_heartbeat(), 0.8), (self.t2, mq.sfx_boom(), 0.9), (4 * B, mv.sfx_pop(), 0.9),
                        (4.5 * B, mq.sfx_boom(), 0.6), (4.5 * B, mv.sfx_riser(1.5 * B), 0.7),
                        (6 * B - 0.3, mv.sfx_whoosh(0.4), 0.9)]
        for k in range(len(self.cuts)):
            at = self.t1 + k * 0.5 * B
            self.sounds += [(at, mq.sfx_boom(), 0.45), (at, mq.sfx_glitch(), 0.35), (at, mv.sfx_click(), 0.7)]
        if tts:
            self.voices.append((0.04, tts.say(INTRO_LINE, speed=1.18)))

    def render(self, t):
        T = self.t0 + t
        st = self.ui["stadium"]
        if t < self.t1:
            im = st.render(T, GOLD, strobe=beat_pulse(T))
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.45 * beat_pulse(T)))])
            s = (1.12 - 0.12 * ease_out_cubic(t / 0.3)) * (1 + 0.05 * beat_pulse(T))
            paste_center(im, scaled(self.tease, s).rotate(4 * math.sin(t * 5), Image.BICUBIC, expand=True), *LOGO_C)
            s = 1 + 0.08 * (1 - ease_out_cubic(t / 0.2))
            paste_center(im, scaled(self.o1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 300)
            paste_center(im, scaled(self.o2, s).rotate(2, Image.BICUBIC, expand=True), W / 2, 440)
            paste_center(im, scaled(self.q, 1 + 0.12 * math.sin(t * 12)).rotate(10 * math.sin(t * 6), Image.BICUBIC,
                                                                                   expand=True), 880, 1080)
            paste_center(im, self.o3, W / 2, 1480)
            im = shake(im, 26 * (1 - t / 0.3) if t < 0.3 else 0, t)
            im = rgb_split(im, 12 * (1 - clamp(t / 0.25)))
        elif t < self.t2:
            k = min(len(self.cuts) - 1, int((t - self.t1) / (0.5 * B)))
            tc = t - self.t1 - k * 0.5 * B
            col = [PINK, CYAN, GOLD, mm.RED][k % 4]
            im = st.render(T, col, strobe=1 - clamp(tc / 0.15))
            paste_center(im, scaled(self.cuts[k], 1.1 - 0.1 * ease_out_cubic(tc / 0.15)).rotate(
                (-6, 5, -4, 6)[k], Image.BICUBIC, expand=True), *LOGO_C)
            s = 1 + 0.12 * (1 - ease_out_cubic((t - self.t1) / 0.15))
            paste_center(im, scaled(self.m1, s).rotate(-3, Image.BICUBIC, expand=True), W / 2, 300)
            paste_center(im, scaled(self.m2, s).rotate(3, Image.BICUBIC, expand=True), W / 2, 440)
            im = rgb_split(im, 18 * (1 - clamp(tc / 0.12)))
            if tc < 0.06:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 120)))
        else:
            tg = t - self.t2
            im = st.render(T, CYAN, strobe=beat_pulse(T), rays=1.0)
            im = rgb_split(im, 10 * (1 - clamp(tg / B)))
            im.alpha_composite(Image.new("RGBA", (W, H), (10, 5, 30, 90)))
            b = int(tg / (0.5 * B))
            kk = (tg % (0.5 * B)) / (0.5 * B)
            slam = 1 + 0.35 * (1 - ease_out_cubic(kk / 0.4))
            paste_center(im, scaled(self.l1, slam if b == 0 else 1.0).rotate(-4, Image.BICUBIC, expand=True), W / 2,
                         560)
            if b >= 1:
                paste_center(im, scaled(self.l2, (slam if b == 1 else 1.0) * (1 + 0.04 * beat_pulse(T))).rotate(
                    3, Image.BICUBIC, expand=True), W / 2, 800)
            if b >= 2:
                paste_center(im, scaled(self.l3, slam if b == 2 else 1.0), W / 2, 1180)
            im = shake(im, 22 * (1 - kk) if kk < 0.4 and b <= 2 else 0, t)
            whip = ease_in_cubic((t - (self.dur - 0.22)) / 0.22)
            if whip > 0:
                im = rgb_split(mm.zoom_blur(im, whip), 24 * whip)
        return im


class Club(mv.Scene):
    def __init__(self, idx, q, prev_tier, ui, tts):
        super().__init__()
        key, name, said, fact, femoji, tier, prompt, stick = q
        self.idx, self.ui, self.tier = idx, ui, tier
        self.bonus = tier == "BONUS"
        self.danger = tier in ("INSANE", "IMPOSSIBLE", "BONUS")
        self.cta = idx in CTA_AFTER
        f = FLY_BEATS
        self.dur = (f + (12 if self.bonus else 8) + (CTA_BEATS if self.cta else 0)) * B
        self.fly = f * B
        self.reveal = (f + (7 if self.bonus else 4)) * B
        self.count_beats = list(range(f + 2, f + 7)) if self.bonus else [f + 1, f + 2, f + 3]
        logo = load_logo(key)
        self.cols = logo_colours(logo)
        pre, steps = BLOCKS[tier]
        self.stages = [sticker(mosaic(logo, b)) for b in [pre] + steps] + [sticker(logo)]
        self.tiles = mm.Tiles(name, tier in ("INSANE", "IMPOSSIBLE", "BONUS"))
        size = 42
        while rfont(size).getlength(fact) > 760 and size > 26:
            size -= 1
        body = join(emoji(femoji, 52), rtext(fact, size, stroke=0), gap=14)
        self.fact = rounded_card(body.width + 56, body.height + 22, (body.height + 22) // 2, INK + (225,))
        paste_center(self.fact, body, self.fact.width / 2, self.fact.height / 2)
        self.sticker = emoji(stick, 150)
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
        self.nums = {n: rtext(str(n), 230, fill=PINK if n == 1 else (255, 255, 255), stroke=16)
                     for n in range(1, len(self.count_beats) + 1)}
        self.streak = {n: join(rtext(f"x{n}", 46, fill=GOLD, stroke=5), emoji("🔥", 46), gap=6) for n in (idx - 1, idx)}
        self.sounds += [(0.0, mv.sfx_whoosh(0.5), 0.8), (self.fly * 0.55, mq.sfx_boom(), 0.7),
                        (self.fly * 0.55, mv.sfx_pop(), 0.8)]
        for j, b in enumerate(self.count_beats):
            self.sounds += [(b * B, mq.sfx_tock(high=j == len(self.count_beats) - 1), 1.0), (b * B, mv.sfx_click(), 0.5)]
            if self.danger:
                self.sounds.append((b * B, sfx_heartbeat(), 0.9))
        self.sounds.append((self.reveal - 1.2 * B, mv.sfx_riser(1.2 * B), 0.6))
        self.sounds += [(self.reveal, mq.sfx_boom(), 0.9), (self.reveal, mv.sfx_ding(), 1.0),
                        (self.reveal + 0.05, mq.sfx_pling(), 0.6), (self.dur - 0.3, mv.sfx_whoosh(0.4), 0.6)]
        for i in range(len(self.tiles.pos)):
            self.sounds.append((self.reveal + 0.07 + 0.035 * i, mv.sfx_click(), 0.5))
        if tts:
            v = tts.say(prompt, speed=1.18)
            self.voices.append((0.12, v))
            if 0.12 + len(v) / SR > self.count_beats[0] * B + 0.1:
                print(f"warning: prompt {idx} runs into the countdown", flush=True)
            self.voices.append((self.reveal + 0.08, tts.say(said, speed=1.12)))
            if self.cta:
                v = tts.say(CTA_LINE, speed=1.12)
                self.voices.append((self.reveal + CTA_AT, v))
                if self.reveal + CTA_AT + len(v) / SR > self.dur - 0.2:
                    print(f"warning: the like line after {idx} runs into the next club", flush=True)
        if self.cta:
            self.cta_card = rounded_card(820, 196, 98, INK + (238,), outline=PINK + (255,), width=6)
            paste_center(self.cta_card, rtext(f"GOT {idx}/{idx} SO FAR?", 52, fill=GOLD, stroke=5), 490, 64)
            paste_center(self.cta_card, rtext("LIKE THIS VIDEO!", 64, stroke=6), 490, 132)
            self.thumb = emoji("👍", 132)
            self.sounds += [(self.reveal + CTA_AT, mv.sfx_pop(), 0.9), (self.reveal + CTA_AT + 0.02, mq.sfx_pling(), 0.5),
                            (self.reveal + CTA_AT + 0.45, mv.sfx_click(), 0.8)]
        r = random.Random(idx * 31)
        self.conf = [(r.uniform(-1, 1) * 700, r.uniform(-1350, -450), r.randint(12, 26), r.choice(self.cols),
                      r.uniform(0, 3)) for _ in range(70)]

    def stage(self, t):
        if t >= self.reveal:
            return self.stages[-1]
        k = sum(1 for b in self.count_beats if t >= b * B)
        return self.stages[k]

    def render(self, t):
        T = self.t0 + t
        rv = t - self.reveal
        st = self.ui["stadium"]
        on_beat = beat_pulse(T) if t > self.fly else 0.0
        rays = 0.55 + 0.45 * on_beat if rv < 0 else 1.0
        im = st.render(T, self.col, strobe=on_beat * 0.6 + (1 - clamp(rv / 0.25) if rv > 0 else 0), rays=rays)
        if self.danger and 0 < t < self.reveal:
            im.alpha_composite(self.ui["vig"][int(10 * (0.35 + 0.65 * beat_pulse(T)))])
        if rv > 0:
            im.alpha_composite(speed_lines(1 - clamp(rv / 0.45), self.idx))
        # the crest: spins in, bounces on the beats, steps sharper on each count, punches on the reveal
        k_in = clamp(t / (self.fly * 0.55))
        s = ease_out_back(k_in, 1.4) if k_in < 1 else 1.0
        ang = 70 * (1 - ease_out_cubic(k_in))
        if t > self.fly:
            s *= 1 + 0.04 * beat_pulse(T)
        for b in self.count_beats:
            tb = t - b * B
            if 0 <= tb < 0.25:
                s *= 1 + 0.08 * (1 - tb / 0.25)
                ang += 4 * (1 - tb / 0.25) * (1 if b % 2 else -1)
        if 0 < rv < 0.4:
            s *= 1 + 0.22 * (1 - ease_out_cubic(rv / 0.4))
        if rv > 0:
            ang += 3 * math.sin(rv * 3)
        if s > 0.02:
            logo = scaled(self.stage(t), s)
            if abs(ang) > 0.3:
                logo = logo.rotate(ang, Image.BICUBIC, expand=True)
            yb = LOGO_C[1] + 10 * math.sin(T * 2.2)
            paste_center(im, logo, LOGO_C[0], yb)
        shockwave(im, rv, self.col)
        d = ImageDraw.Draw(im)
        # top bar: count, timer, tier tag, streak
        paste_center(im, self.count, 92 + (20 if self.bonus else 0), 222)
        x0, x1, y, bh = 160 + (40 if self.bonus else 0), 1000, 222, 22
        frac = 1.0 if t < self.fly else max(0.0, 1 - (t - self.fly) / (self.reveal - self.fly))
        d.rounded_rectangle((x0 - 5, y - bh / 2 - 5, x1 + 5, y + bh / 2 + 5), 16, fill=INK + (235,))
        colr = (255, 255, 255) if frac > 0.6 else CYAN if frac > 0.3 else PINK
        if frac > 0.01:
            d.rounded_rectangle((x0, y - bh / 2, x0 + (x1 - x0) * frac, y + bh / 2), 11, fill=colr + (255,))
        paste_center(im, self.tag, x0 + self.tag.width / 2, 285)
        n = self.idx if rv > 0 else self.idx - 1
        if n > 0:
            sc = 1 + 0.5 * (1 - ease_out_cubic(rv / 0.25)) if 0 < rv < 0.25 else 1.0
            stk = self.streak[n]
            paste_center(im, scaled(stk, sc), x1 - stk.width / 2 + 10, 288)
        if self.banner is not None and 0.05 < t < self.fly + 0.3:
            tb = t - 0.05
            sc = 1 + 1.0 * (1 - ease_out_cubic(tb / 0.16))
            a = clamp(tb / 0.06) * (1 - clamp((tb - self.fly + 0.05) / 0.25))
            paste_center(im, scaled(self.banner, sc).rotate(-4, Image.BICUBIC, expand=True), W / 2, 420, a)
        for j, b in enumerate(self.count_beats):
            tb = t - b * B
            if 0 <= tb < B:
                num = self.nums[len(self.count_beats) - j]
                sc = 1.5 - 0.5 * ease_out_cubic(tb / 0.12)
                a = 1 - clamp((tb - 0.22) / 0.2)
                paste_center(im, scaled(num, sc).rotate(-6 + 4 * j, Image.BICUBIC, expand=True), W / 2, NUM_Y, a * 0.85)
        self.tiles.draw(im, t - self.fly - B, rv)
        if rv > 0:
            for vx, vy, sz, cc, spin in self.conf:
                px, py = LOGO_C[0] + vx * rv, LOGO_C[1] + vy * rv + 2400 * rv * rv
                if py < H:
                    w2 = sz * abs(math.cos(spin + rv * 9))
                    d.rectangle((px - w2 / 2, py - sz / 2, px + w2 / 2, py + sz / 2), fill=cc + (255,),
                                outline=INK + (255,))
            sk = ease_out_back((rv - 0.12) / 0.25, 2.2)
            if sk > 0.01:
                paste_center(im, scaled(self.sticker, sk).rotate(14 * math.sin(rv * 7), Image.BICUBIC, expand=True),
                             905, 1110)
            fk = ease_out_back((rv - 0.35) / 0.3)
            if fk > 0.01:
                paste_center(im, scaled(self.fact, fk), W / 2, mm.FACT_Y)
            fl = 1 - clamp(rv / 0.14)
            if fl > 0:
                im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * fl))))
            im = shake(im, 30 * (1 - rv / 0.35) if rv < 0.35 else 0, t)
            if rv < 0.18:
                im = rgb_split(im, 16 * (1 - rv / 0.18))
        else:
            for b in self.count_beats:                    # a small kick on every count
                tb = t - b * B
                if 0 <= tb < 0.15:
                    im = shake(im, 12 * (1 - tb / 0.15), t)
                    im = rgb_split(im, 8 * (1 - tb / 0.15))
        if self.cta and rv > CTA_AT:
            ct = rv - CTA_AT
            k = ease_out_back(ct / 0.3, 2.0) * (1 - ease_in_cubic(clamp((t - (self.dur - 0.45)) / 0.25)))
            if k > 0.01:
                card = self.cta_card.copy()
                tap = 1 - 0.18 * math.sin(math.pi * clamp((ct - 0.45) / 0.2))
                th = scaled(self.thumb, tap * (1 + 0.08 * beat_pulse(T))).rotate(10 * math.sin(ct * 7), Image.BICUBIC,
                                                                                 expand=True)
                paste_center(card, th, 98, 98)
                sc = k * (1 + 0.025 * beat_pulse(T))
                paste_center(im, scaled(card, sc).rotate(-2, Image.BICUBIC, expand=True), W / 2, CTA_Y)
                rp = (ct - 0.5) / 0.45
                if 0 < rp < 1:
                    d = ImageDraw.Draw(im)
                    rr, cx = 70 + 110 * ease_out_cubic(rp), W / 2 - 312 * sc
                    d.ellipse((cx - rr, CTA_Y - rr, cx + rr, CTA_Y + rr), outline=PINK + (int(255 * (1 - rp)),),
                              width=max(1, int(10 * (1 - rp))))
        if self.level_up and t < 0.35:
            im = glitch(im, 1 - t / 0.35, int(t * 30) + self.idx * 7)
        if t < 0.18:                                        # whip in
            im = rgb_split(mm.zoom_blur(im, 1 - t / 0.18), 20 * (1 - t / 0.18))
        out = ease_in_cubic((t - (self.dur - 0.2)) / 0.2)
        if out > 0:
            im = rgb_split(mm.zoom_blur(im, out), 22 * out)
        return im


class Ending(mv.Scene):
    """Score screen in the stadium; fades into the first frame so the Short loops."""

    def __init__(self, ui, intro, tts):
        super().__init__()
        self.ui, self.intro = ui, intro
        self.dur = 10 * B
        logo = Image.open(brand.round_logo()).convert("RGBA").resize((120, 120), Image.LANCZOS)
        self.brand = join(logo, rtext(brand.NAME, 60, stroke=6), gap=18)
        self.title = rtext("HOW MANY?", 124, fill=CYAN, stroke=11)
        tiers = [("0-3", "Benchwarmer", "🪑"), ("4-5", "Sunday league", "⚽"), ("6-7", "Pro player", "🏃"),
                 ("8-9", "Captain", "🎖"), ("10", "Football GOAT", "🐐")]
        self.rows = []
        for i, (sc, label, e) in enumerate(tiers):
            colr = PINK if i == 4 else (255, 255, 255)
            row = rounded_card(800, 104, 52, INK + (215,), outline=(colr if i == 4 else (90, 70, 130)) + (255,),
                               width=4)
            dr = ImageDraw.Draw(row)
            dr.text((44, 52), sc, font=rfont(60), fill=colr, anchor="lm")
            dr.text((210, 52), label, font=rfont(58, "SemiBold"), fill=colr, anchor="lm")
            row.alpha_composite(emoji(e, 60), (800 - 96, 22))
            self.rows.append(row)
        self.bonus = join(rtext("+ bonus = LEGEND", 58, fill=GOLD, stroke=6), emoji("👑", 62))
        self.cta = join(rtext("comment your score", 58, stroke=6), emoji("👇", 62))
        self.sounds += [(0.0, mv.sfx_whoosh(0.8), 0.7), (B, mq.sfx_levelup(), 0.9)]
        for i in range(5):
            self.sounds.append(((1.5 + 0.5 * i) * B, mv.sfx_pop(), 0.7))
        self.sounds.append((5 * B, mq.sfx_pling(), 0.7))
        if tts:
            self.voices.append((0.3, tts.say(END_LINE, speed=1.12)))

    def render(self, t):
        T = self.t0 + t
        im = self.ui["stadium"].render(T, GOLD, strobe=0.4 * beat_pulse(T), rays=0.8)
        out = clamp((t - (self.dur - 0.45)) / 0.4)
        a = 1 - out
        im.alpha_composite(Image.new("RGBA", (W, H), INK + (int(150 * clamp((t - 0.2) / 0.3) * a),)))
        paste_center(im, self.brand, W / 2, 300, clamp((t - B) / 0.2) * a)
        paste_center(im, scaled(self.title, ease_out_back((t - B) / 0.25)), W / 2, 460, a)
        for i, row in enumerate(self.rows):
            k = ease_out_cubic((t - (1.5 + 0.5 * i) * B) / 0.2)
            if k > 0:
                paste_center(im, row, W / 2 + (1 - k) * 160, 620 + i * 122, k * a)
        paste_center(im, scaled(self.bonus, ease_out_back((t - 4.5 * B) / 0.25)), W / 2, 1255, a)
        paste_center(im, scaled(self.cta, ease_out_back((t - 5 * B) / 0.25) * (1 + 0.03 * math.sin(t * 8))),
                     W / 2, 1350, a)
        if t < 0.2:
            im = rgb_split(mm.zoom_blur(im, 1 - t / 0.2), 18 * (1 - t / 0.2))
        if out > 0:
            first = self.intro.render(0.0)
            first.putalpha(first.getchannel("A").point(lambda v: int(v * out)))
            im.alpha_composite(first)
        return im


class Voices:
    """Recorded narrator lines from one or more voice packs (later folders fill in what earlier ones lack)."""

    def __init__(self, folders, fallback=None):
        self.clips = {}
        for f in folders:
            for text, clip in mc.VoicePack(f).clips.items():
                self.clips.setdefault(text, clip)
        self.fallback = fallback

    def say(self, text, speed=None):
        if text in self.clips:
            return self.clips[text]
        if self.fallback is None:
            raise KeyError(f"no recording of {text!r}")
        return self.fallback.say(text, speed=speed)


def build(voice="am_adam", voice_pack=None):
    if voice_pack:
        tts = Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    ui = {"stadium": Stadium(), "vig": [mc.red_vignette(i / 10) for i in range(11)]}
    intro = Intro(ui, tts)
    scenes, prev = [intro], CLUBS[0][5]
    for i, q in enumerate(CLUBS, 1):
        scenes.append(Club(i, q, prev, ui, tts))
        prev = q[5]
    scenes.append(Ending(ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path):
    T = 0.0
    im = ui["stadium"].render(T, CYAN, rays=1.0)
    logo = sticker(mosaic(load_logo("barcelona", 700), 40))
    paste_center(im, logo.rotate(-6, Image.BICUBIC, expand=True), 540, 1120)
    im.alpha_composite(mm.shade_overlay(0.8))
    paste_center(im, rtext("GUESS THE", 140, stroke=12), W / 2, 250)
    paste_center(im, join(rtext("CLUB", 210, fill=CYAN, stroke=15), emoji("⚽", 170), gap=18), W / 2, 450)
    paste_center(im, join(rtext("99% FAIL", 96, fill=PINK, stroke=9), emoji("💀", 98)).rotate(
        -4, Image.BICUBIC, expand=True), W / 2, 640)
    paste_center(im, rtext("?", 300, stroke=18).rotate(12, Image.BICUBIC, expand=True), 880, 1500)
    im.convert("RGB").save(path, quality=92)
    print(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "short_club_quiz.mp4"))
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
    work = os.path.join(mv.CACHE_DIR, "render_clubs")
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
        make_cover(ui, os.path.join(HERE, "club_quiz_cover.jpg"))
        return
    mv.G["scenes"], mv.G["starts"] = scenes, starts
    if a.stills:
        d = os.path.join(mv.CACHE_DIR, "stills")
        os.makedirs(d, exist_ok=True)
        for s in a.stills.split(","):
            p = os.path.join(d, f"clubs_{float(s):06.2f}.png")
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
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-c:v", "libx264", "-crf", "23", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", a.out], check=True)
    print(f"Done: {a.out}")


if __name__ == "__main__":
    main()
