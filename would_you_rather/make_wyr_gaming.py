#!/usr/bin/env python3
""""WOULD YOU RATHER? GAMING EDITION" Short (1080x1920), same format as the money edition.

Eight gaming dilemmas on the red / blue split screen (GTA 6 early or free, skins or coins, Minecraft
or GTA for a week...). The narrator reads each one, a 3-2-1 runs inside the OR badge on the beat,
then a poll fills both cards and counts up to the split (made-up, "for fun" numbers, noted in the
description) and the narrator says the result. Falling gaming-emoji
backdrop, hook intro, one like call-out after question 3 and a looping ending. Only text and emojis:
no game art, characters or logos.

    python3 make_wyr_gaming.py --voice-pack voice_packs/wyrgaming_adam
    python3 make_wyr_gaming.py --stills 1,5,8
    python3 make_wyr_gaming.py --cover
"""

import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import make_club_quiz as cq  # noqa: E402
import make_map_quiz_crazy as mc  # noqa: E402
import make_video as mv  # noqa: E402
import make_wyr_money as wm  # noqa: E402
from make_map_quiz import CYAN, GOLD, PINK, join, rfont, rtext  # noqa: E402
from make_video import emoji, paste_center, scaled  # noqa: E402

W, H = wm.W, wm.H
PURPLE = (190, 120, 255)

QUESTIONS = [  # A text, A emoji, B text, B emoji, spoken question, pick, spoken result, fact, % who chose A
    ("Play GTA 6 a week before everyone", "🌴", "Get GTA 6 for free", "🎁",
     "Play GTA 6 a week before everyone, or get it for free?", None, "58 percent would play it early!", None, 58),
    ("The rarest pirate skin in your favourite game", "🏴‍☠", "Unlimited in-game coins forever", "🪙",
     "The rarest pirate skin in your favourite game, or unlimited coins forever?", None,
     "81 percent took unlimited coins!", None, 19),
    ("Never lag again", "📶", "Never lose an online match", "🏆",
     "Never lag again, or never lose an online match?", None, "67 percent never want to lag again!", None, 67),
    ("Live inside Minecraft for a week", "⛏", "Live inside GTA 6 for a week", "🚔",
     "Live inside Minecraft for a week, or inside GTA 6 for a week?", None, "62 percent would live in Minecraft!",
     None, 62),
    ("A $5,000 gaming PC", "🖥", "Every console ever made", "🎮",
     "A five thousand dollar gaming PC, or every console ever made?", None, "57 percent want the gaming PC!", None,
     57),
    ("Unlimited Robux", "🧱", "Unlimited V-Bucks", "🪂", "Unlimited Robux, or unlimited V-Bucks?", None,
     "53 percent picked Robux!", None, 53),
    ("10 million subscribers", "📹", "Best player in the world, but nobody knows", "🥇",
     "Ten million subscribers, or be the best player in the world, but nobody knows?", None,
     "74 percent want the subscribers!", None, 74),
    ("Never play video games again + $1,000,000", "💰", "Every game free forever, but stay broke", "🎮",
     "Final one. Never play video games again and get a million dollars, or play every game free forever but "
     "stay broke?", None, "Only 52 percent took the million! So close!", None, 52),
]
INTRO_LINE = "Would you rather? Gaming edition! The last one is impossible!"
CTA_LINE = wm.CTA_LINE
END_LINE = wm.END_LINE

# the money edition's scenes read these module values
wm.QUESTIONS, wm.INTRO_LINE = QUESTIONS, INTRO_LINE
wm.ALL_LINES = [INTRO_LINE] + [x for q in QUESTIONS for x in (q[4], q[6])] + [CTA_LINE, END_LINE]


class GameRain(wm.MoneyRain):
    """Dark purple backdrop with falling gaming emojis."""

    def __init__(self):
        rnd = random.Random(9)
        self.base = mv.vgradient(W, H, (14, 8, 40), (34, 10, 56)).convert("RGBA")
        paste_center(self.base, mv.soft_circle(1300, PURPLE + (70,), 260), W / 2, wm.BADGE_Y)
        sprites = [emoji(e, s) for e in ("🎮", "🕹", "👾", "🏆", "⭐", "💎", "🪙", "❤") for s in (70, 96, 124)]
        self.items = []
        for _ in range(46):
            depth = rnd.uniform(0.4, 1.0)
            spr = scaled(rnd.choice(sprites), depth)
            a = int(110 * depth)
            spr.putalpha(spr.getchannel("A").point(lambda v, a=a: v * a // 255))
            frames = [spr.rotate(rnd.uniform(-180, 180) + k * 15, Image.BICUBIC, expand=True) for k in range(6)]
            self.items.append((rnd.uniform(0, W), rnd.uniform(0, H + 200), 120 + 260 * depth, frames,
                               rnd.uniform(0, 6.28)))
        ys, xs = np.mgrid[0:H, 0:W]
        dd = np.sqrt(((xs - W / 2) / (W * 0.72)) ** 2 + ((ys - H / 2) / (H * 0.62)) ** 2)
        a = np.zeros((H, W, 4), np.uint8)
        a[..., 3] = (np.clip(dd - 0.62, 0, 1) * 330).clip(0, 170).astype(np.uint8)
        self.vig = Image.fromarray(a, "RGBA")


class Intro(wm.Intro):
    def __init__(self, ui, tts):
        super().__init__(ui, tts)
        self.l3 = join(rtext("GAMING EDITION", 96, fill=PURPLE, stroke=9), emoji("🎮", 100))
        self.cash = [emoji(e, 260) for e in ("🎮", "🕹", "👾", "🏆")]


class Question(wm.Question):
    def __init__(self, idx, q, ui, tts):
        super().__init__(idx, q, ui, tts)
        self.title = join(rtext("WOULD YOU RATHER", 54, stroke=6), emoji("🎮", 54), gap=10)


def build(voice="am_adam", voice_pack=None):
    if voice_pack:
        tts = cq.Voices(voice_pack.split(","))
    else:
        tts = mv.TTS(voice, "en-us") if voice != "none" else None
    ui = {"bg": GameRain(), "vig": [mc.red_vignette(i / 10) for i in range(11)],
          "cash": [emoji(e, s) for e in ("🎮", "🏆", "⭐", "💎", "🪙") for s in (90, 120)]}
    intro = Intro(ui, tts)
    scenes = [intro] + [Question(i, q, ui, tts) for i, q in enumerate(QUESTIONS, 1)]
    scenes.append(wm.Ending(ui, intro, tts))
    starts, t = [], 0.0
    for sc in scenes:
        sc.t0 = t
        starts.append(t)
        t += sc.dur
    return scenes, starts, t, ui


def make_cover(ui, path=None):
    path = os.path.join(HERE, "wyr_gaming_cover.jpg")
    im = ui["bg"].render(3.0)
    q = QUESTIONS[0]
    paste_center(im, wm.panel("A", q[0], q[1], wm.RED_A, wm.RED_B), W / 2, 1040)
    paste_center(im, emoji(q[1], 210), W / 2, 880)
    paste_center(im, wm.text_block(q[0]), W / 2, 1110)
    paste_center(im, wm.panel("B", q[2], q[3], wm.BLUE_A, wm.BLUE_B), W / 2, 1600)
    paste_center(im, emoji(q[3], 200), W / 2, 1500)
    paste_center(im, wm.text_block(q[2]), W / 2, 1700)
    paste_center(im, rtext("WOULD YOU", 140, stroke=12).rotate(-3, Image.BICUBIC, expand=True), W / 2, 230)
    paste_center(im, rtext("RATHER?", 190, fill=GOLD, stroke=15).rotate(3, Image.BICUBIC, expand=True), W / 2, 420)
    paste_center(im, join(rtext("GAMING EDITION", 84, fill=PURPLE, stroke=8), emoji("🎮", 88)), W / 2, 610)
    badge = mv.circle(190, (255, 255, 255, 255))
    ImageDraw.Draw(badge).text((95, 98), "OR", font=rfont(84), fill=(20, 22, 45), anchor="mm")
    paste_center(im, mv.circle(230, GOLD + (255,)), W / 2, 1320)
    paste_center(im, badge, W / 2, 1320)
    im.convert("RGB").save(path, quality=92)
    print(path)


wm.build, wm.make_cover = build, make_cover

if __name__ == "__main__":
    if "--out" not in sys.argv:
        sys.argv += ["--out", os.path.join(HERE, "short_wyr_gaming.mp4")]
    wm.main()
