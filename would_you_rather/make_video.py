#!/usr/bin/env python3
"""Generate a "Would You Rather?" video.

A spinning wheel picks random subjects, then each round asks timed
"would you rather" questions with a countdown, a poll reveal and a fun fact.
Narration uses the Kokoro neural TTS model; music and sound effects are
synthesised here, so nothing is copyrighted.

    python3 make_video.py                 # random seed, 3 rounds x 4 questions
    python3 make_video.py --seed 42       # reproducible video
    python3 make_video.py --rounds 2 --per-round 3 --out short.mp4
"""

import argparse
import hashlib
import math
import multiprocessing as mp
import os
import random
import re
import shutil
import subprocess
import sys
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.signal import lfilter, resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from questions import SUBJECTS  # noqa: E402

W, H, FPS = 1920, 1080, 30
SR = 48000
COUNTDOWN = 5

FONT_DIR = "/usr/share/fonts/opentype/inter"
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
MODEL_DIR = os.path.join(HERE, "models")
CACHE_DIR = os.path.join(HERE, ".cache")
MODEL_URLS = {
    "kokoro.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx",
    "voices.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
VOICE = "af_heart"

BG = (14, 16, 34)
RED_TOP, RED_BOT = (255, 82, 96), (196, 22, 48)
BLUE_TOP, BLUE_BOT = (64, 150, 255), (20, 70, 190)
YELLOW = (255, 214, 10)
ALARM = (255, 69, 58)


# ----------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out_cubic(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_cubic(x):
    x = clamp(x)
    return x ** 3


def ease_out_back(x, s=1.7):
    x = clamp(x)
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


def ease_in_out(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


_fonts = {}


def font(weight, size, display=True):
    key = (weight, size, display)
    if key not in _fonts:
        name = f"{'InterDisplay' if display else 'Inter'}-{weight}.otf"
        _fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    return _fonts[key]


_emoji = {}


def emoji(ch, size):
    """Colour emoji as an RGBA image of the given height."""
    ch = ch.replace("️", "")
    key = (ch, size)
    if key not in _emoji:
        f = ImageFont.truetype(EMOJI_FONT, 109)
        im = Image.new("RGBA", (180, 160))
        ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
        im = im.crop(im.getbbox())
        r = size / im.height
        _emoji[key] = im.resize((max(1, round(im.width * r)), size), Image.LANCZOS)
    return _emoji[key]


def wrap(text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if fnt.getlength(test) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_img(text, fnt, fill=(255, 255, 255), shadow=True, stroke=0, stroke_fill=None):
    """Render a single line of text to a tight RGBA image (with soft shadow)."""
    l, t, r, b = fnt.getbbox(text, stroke_width=stroke)
    pad = 24
    im = Image.new("RGBA", (r - l + pad * 2, b - t + pad * 2))
    d = ImageDraw.Draw(im)
    if shadow:
        sh = Image.new("RGBA", im.size)
        ImageDraw.Draw(sh).text((pad - l + 3, pad - t + 6), text, font=fnt, fill=(0, 0, 0, 120),
                                stroke_width=stroke, stroke_fill=(0, 0, 0, 120))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(5)))
        d = ImageDraw.Draw(im)
    d.text((pad - l, pad - t), text, font=fnt, fill=fill, stroke_width=stroke,
           stroke_fill=stroke_fill or fill)
    return im


def paste_center(dst, src, cx, cy, alpha=1.0):
    if alpha <= 0:
        return
    if alpha < 1:
        src = src.copy()
        src.putalpha(src.getchannel("A").point(lambda v: int(v * alpha)))
    dst.alpha_composite(src, (int(round(cx - src.width / 2)), int(round(cy - src.height / 2))))


def scaled(im, s):
    if abs(s - 1) < 1e-3:
        return im
    s = max(s, 0.01)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)


def vgradient(w, h, top, bot):
    t = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(top)[None, None, :] * (1 - t) + np.array(bot)[None, None, :] * t)
    arr = np.repeat(arr, w, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def radial_glow(w, h, cx, cy, radius, color, strength):
    y, x = np.mgrid[0:h, 0:w]
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / radius
    a = np.clip(1 - d, 0, 1) ** 2 * strength
    im = np.zeros((h, w, 4), np.uint8)
    im[..., :3] = color
    im[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(im, "RGBA")


def rounded_card(w, h, r, fill, outline=None, width=0, ss=3):
    im = Image.new("RGBA", (w * ss, h * ss))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=fill,
                                         outline=outline, width=width * ss)
    return im.resize((w, h), Image.LANCZOS)


def circle(d, fill, ss=4):
    im = Image.new("RGBA", (d * ss, d * ss))
    ImageDraw.Draw(im).ellipse((0, 0, d * ss - 1, d * ss - 1), fill=fill)
    return im.resize((d, d), Image.LANCZOS)


def soft_circle(d, color, blur):
    """Blurred circle on a padded canvas, so the blur never gets clipped into a square."""
    pad = int(blur * 3)
    im = Image.new("RGBA", (d + 2 * pad, d + 2 * pad))
    im.alpha_composite(circle(d, color), (pad, pad))
    return im.filter(ImageFilter.GaussianBlur(blur))


def dark_bg():
    base = vgradient(W, H, (24, 27, 58), (8, 9, 22)).convert("RGBA")
    base.alpha_composite(radial_glow(W, H, W / 2, H * 0.45, 900, (90, 70, 200), 0.35))
    return base


class Bokeh:
    """Slow drifting soft circles for the dark scenes."""

    def __init__(self, seed, n=26):
        r = random.Random(seed)
        self.parts = []
        colors = [(255, 82, 96), (64, 150, 255), (255, 214, 10), (180, 120, 255)]
        for _ in range(n):
            d = r.randint(40, 180)
            c = r.choice(colors)
            spr = soft_circle(d, c + (255,), d / 6)
            self.parts.append((spr, r.uniform(0, W), r.uniform(0, H), r.uniform(8, 30),
                               r.uniform(0, 6.28), r.uniform(0.08, 0.22)))

    def draw(self, im, t):
        for spr, x, y, sp, ph, a in self.parts:
            yy = (y - sp * t) % (H + 200) - 100
            xx = x + 30 * math.sin(t * 0.4 + ph)
            paste_center(im, spr, xx, yy, a)


# ----------------------------------------------------------------------------
# audio
# ----------------------------------------------------------------------------

def tt(dur):
    return np.arange(int(dur * SR)) / SR


def lowpass(x, cutoff):
    a = math.exp(-2 * math.pi * cutoff / SR)
    return lfilter([1 - a], [1, -a], x)


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def sfx_tick(high=False):
    t = tt(0.07)
    f = 2600 if high else 1900
    s = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 1.5 * t)) * np.exp(-t * 70)
    n = highpass(np.random.default_rng(1).standard_normal(len(t)), 3000) * np.exp(-t * 400)
    return (0.5 * s + 0.35 * n) * (0.9 if high else 0.65)


def sfx_ding():
    t = tt(2.2)
    out = np.zeros_like(t)
    for base, delay in ((1046.5, 0.0), (1318.5, 0.09)):
        tt_ = np.clip(t - delay, 0, None)
        on = (t >= delay).astype(float)
        for mult, amp, dec in ((1, 1, 1.8), (2.0, 0.45, 2.6), (3.0, 0.25, 3.5), (4.16, 0.12, 5), (5.43, 0.08, 6)):
            out += on * amp * np.sin(2 * np.pi * base * mult * tt_) * np.exp(-tt_ * dec)
    return out / np.abs(out).max() * 0.55


def sfx_whoosh(dur=0.45, up=True):
    n = np.random.default_rng(7).standard_normal(int(dur * SR))
    x = np.linspace(0, 1, len(n))
    cut = 400 + 5000 * (np.sin(np.pi * x) if up else np.sin(np.pi * x) ** 2)
    y = np.zeros_like(n)
    s = 0.0
    alphas = np.exp(-2 * np.pi * cut / SR)
    for i in range(len(n)):
        s = alphas[i] * s + (1 - alphas[i]) * n[i]
        y[i] = s
    env = np.sin(np.pi * x) ** 1.5
    return y * env / (np.abs(y * env).max() + 1e-9) * 0.35


def sfx_pop():
    t = tt(0.12)
    f = 900 * np.exp(-t * 25) + 200
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 40) * 0.5


def sfx_click():
    t = tt(0.025)
    n = np.random.default_rng(3).standard_normal(len(t))
    return (0.6 * highpass(n, 2000) * np.exp(-t * 600) + 0.4 * np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 300)) * 0.45


def tone(freq, dur, harm=((1, 1.0),), decay=3.0, attack=0.005):
    t = tt(dur)
    s = sum(a * np.sin(2 * np.pi * freq * m * t) for m, a in harm)
    env = np.minimum(1, t / attack) * np.exp(-t * decay)
    return s * env


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def sfx_fanfare():
    out = np.zeros(int(1.6 * SR))
    for i, n in enumerate((72, 76, 79, 84)):
        s = tone(midi(n), 1.2, harm=((1, 1), (2, 0.5), (3, 0.3), (4, 0.15)), decay=3.5)
        st = int(i * 0.075 * SR)
        out[st:st + len(s)] += s[: len(out) - st]
    sh = highpass(np.random.default_rng(5).standard_normal(len(out)), 6000) * np.exp(-tt(1.6) * 3) * 0.15
    out += sh
    return out / np.abs(out).max() * 0.5


def sfx_riser(dur=1.2):
    t = tt(dur)
    f = 200 + 1400 * (t / dur) ** 2
    ph = 2 * np.pi * np.cumsum(f) / SR
    n = highpass(np.random.default_rng(9).standard_normal(len(t)), 2500)
    return (0.4 * np.sin(ph) + 0.3 * n) * (t / dur) ** 2 * 0.4


def make_music(total):
    """Upbeat, royalty-free background loop (I-V-vi-IV)."""
    bpm = 104
    beat = 60 / bpm
    bars = [(48, (60, 64, 67)), (43, (59, 62, 67)), (45, (57, 60, 64)), (41, (57, 60, 65))]
    loop_len = beat * 4 * 8
    out = np.zeros(int(loop_len * SR) + SR)
    rng = np.random.default_rng(11)

    def add(sig, at, gain):
        st = int(at * SR)
        e = min(len(out), st + len(sig))
        out[st:e] += sig[: e - st] * gain

    kick = (np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-tt(0.3) * 30)) / SR) * np.exp(-tt(0.3) * 12))
    clap = lowpass(highpass(rng.standard_normal(int(0.15 * SR)), 900), 5000) * np.exp(-tt(0.15) * 28)
    hat = highpass(rng.standard_normal(int(0.04 * SR)), 7000) * np.exp(-tt(0.04) * 120)

    for b in range(8):
        root, chord = bars[b % 4]
        t0 = b * 4 * beat
        for n in chord:  # warm pad
            for det in (-0.12, 0.12):
                s = tone(midi(n + det), 4 * beat + 0.3, harm=((1, 1), (2, 0.25), (3, 0.1)), decay=0.35, attack=0.25)
                add(s, t0, 0.05)
        for k in range(8):  # plucky arpeggio
            n = chord[[0, 1, 2, 1, 0, 2, 1, 2][k]] + 12
            s = tone(midi(n), 0.45, harm=((1, 1), (2, 0.35), (3, 0.12)), decay=9)
            add(s, t0 + k * beat / 2, 0.07 if k % 2 == 0 else 0.05)
        for k, (pos, ln) in enumerate(((0, 0.9), (1.5, 0.4), (2, 0.9), (3.5, 0.4))):  # bass
            s = np.tanh(1.6 * tone(midi(root - 12 + (0 if k != 3 else 7)), ln * beat * 1.2,
                                   harm=((1, 1), (2, 0.3)), decay=2.5, attack=0.01))
            add(s, t0 + pos * beat, 0.22)
        for k in range(4):
            if k in (0, 2):
                add(kick, t0 + k * beat, 0.5)
            else:
                add(clap, t0 + k * beat, 0.16)
        if b % 2 == 1:
            add(kick, t0 + 2.5 * beat, 0.35)
        for k in range(8):
            add(hat, t0 + k * beat / 2, 0.06 if k % 2 else 0.035)

    loop = lowpass(out[: int(loop_len * SR)], 9000)
    reps = int(math.ceil(total / loop_len)) + 1
    music = np.tile(loop, reps)[: int(total * SR)]
    fade = int(2.5 * SR)
    music[-fade:] *= np.linspace(1, 0, fade)
    music[: int(0.5 * SR)] *= np.linspace(0, 1, int(0.5 * SR))
    return music / (np.abs(music).max() + 1e-9)


# ----------------------------------------------------------------------------
# text to speech
# ----------------------------------------------------------------------------

def ensure_models():
    os.makedirs(MODEL_DIR, exist_ok=True)
    for name, url in MODEL_URLS.items():
        path = os.path.join(MODEL_DIR, name)
        if not os.path.exists(path):
            print(f"Downloading {name} ...")
            urllib.request.urlretrieve(url, path + ".part")
            os.replace(path + ".part", path)


def speakable(text):
    text = re.sub(r"\$([\d,\.]+)( million| billion)?", lambda m: f"{m.group(1)}{m.group(2) or ''} dollars", text)
    text = text.replace("1%", "1 percent")
    return text


class TTS:
    def __init__(self, voice=VOICE, lang="en-us"):
        self.k, self.voice, self.lang = None, voice, lang
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _eleven(self, text, speed):
        """ElevenLabs voice: self.voice is "eleven:<voice name or voice id>". Needs ELEVENLABS_API_KEY."""
        import json
        import urllib.request
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            sys.exit("ELEVENLABS_API_KEY is not set (add it to the environment's settings, not to the chat)")
        api = "https://api.elevenlabs.io/v1"
        voice = self.voice.split(":", 1)[1]
        if not re.fullmatch(r"[A-Za-z0-9]{20}", voice):  # a name like "George": look up its id
            req = urllib.request.Request(f"{api}/voices", headers={"xi-api-key": key})
            voices = json.load(urllib.request.urlopen(req, timeout=60))["voices"]
            match = [v for v in voices if v["name"].lower().startswith(voice.lower())]
            if not match:
                sys.exit(f"No ElevenLabs voice called {voice!r}. Available: {', '.join(v['name'] for v in voices)}")
            voice = match[0]["voice_id"]
        body = json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                           "voice_settings": {"stability": 0.4, "similarity_boost": 0.8, "style": 0.35,
                                              "speed": max(0.7, min(1.2, speed))}}).encode()
        req = urllib.request.Request(f"{api}/text-to-speech/{voice}?output_format=mp3_44100_128", data=body,
                                     headers={"xi-api-key": key, "Content-Type": "application/json"})
        mp3 = urllib.request.urlopen(req, timeout=120).read()
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "-", "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                             input=mp3, capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.float32).astype(np.float64), SR

    def say(self, text, speed=1.04):
        text = speakable(text)
        lang = "" if self.lang == "en-us" else f"|{self.lang}"  # keeps old cache keys valid
        key = hashlib.sha1(f"{self.voice}|{speed}|{text}{lang}".encode()).hexdigest()[:16]
        path = os.path.join(CACHE_DIR, key + ".npy")
        if os.path.exists(path):
            return np.load(path)
        if self.voice.startswith("eleven:"):
            samples, sr = self._eleven(text, speed)
            audio = samples
            nz = np.nonzero(np.abs(audio) > 0.01)[0]  # trim silence
            if len(nz):
                audio = audio[max(0, nz[0] - int(0.03 * SR)): nz[-1] + int(0.08 * SR)]
            audio = audio / (np.abs(audio).max() + 1e-9) * 0.9
            np.save(path, audio)
            return audio
        if self.k is None:
            ensure_models()
            from kokoro_onnx import Kokoro
            self.k = Kokoro(os.path.join(MODEL_DIR, "kokoro.onnx"), os.path.join(MODEL_DIR, "voices.bin"))
        samples, sr = self.k.create(text, voice=self.voice, speed=speed, lang=self.lang)
        audio = resample_poly(samples.astype(np.float64), SR, sr)
        nz = np.nonzero(np.abs(audio) > 0.01)[0]  # trim silence
        if len(nz):
            audio = audio[max(0, nz[0] - int(0.03 * SR)): nz[-1] + int(0.08 * SR)]
        audio = audio / (np.abs(audio).max() + 1e-9) * 0.9
        np.save(path, audio)
        return audio


# ----------------------------------------------------------------------------
# scenes
# ----------------------------------------------------------------------------

class Scene:
    dur = 1.0

    def __init__(self):
        self.sounds = []  # (time, array, gain)
        self.voices = []  # (time, array)

    def render(self, t):
        raise NotImplementedError


class IntroScene(Scene):
    def __init__(self, tts, rounds, total_q, sample_emojis):
        super().__init__()
        line = (f"Welcome to Would You Rather! Today, a wheel picks {rounds} random subjects, "
                f"and every question gives you just {COUNTDOWN} seconds to choose. "
                "Keep count of how many times you side with the majority, "
                "and drop your score in the comments at the end. Let's go!")
        v = tts.say(line)
        self.voices.append((0.9, v))
        self.dur = 0.9 + len(v) / SR + 0.7
        self.sounds += [(0.0, sfx_whoosh(0.6), 0.9), (0.55, sfx_pop(), 1.0), (0.75, sfx_pop(), 1.0),
                        (1.3, sfx_pop(), 0.6), (1.5, sfx_pop(), 0.6), (1.7, sfx_pop(), 0.6)]
        self.bg = dark_bg()
        self.left = vgradient(W // 2, H, RED_TOP, RED_BOT).convert("RGBA")
        self.right = vgradient(W // 2, H, BLUE_TOP, BLUE_BOT).convert("RGBA")
        self.l1 = text_img("WOULD YOU", font("Black", 150))
        self.l2 = text_img("RATHER?", font("Black", 230), fill=(255, 255, 255))
        chips = [f"{rounds} RANDOM SUBJECTS", f"{total_q} IMPOSSIBLE CHOICES", f"{COUNTDOWN} SECONDS EACH"]
        self.chips = []
        for c in chips:
            ti = text_img(c, font("Bold", 40), shadow=False, fill=(20, 22, 45))
            card = rounded_card(ti.width + 40, 84, 42, (255, 255, 255, 240))
            paste_center(card, ti, card.width / 2, card.height / 2)
            self.chips.append(card)
        self.floaters = []
        r = random.Random(3)
        for i, e in enumerate(sample_emojis):
            self.floaters.append((emoji(e, r.randint(90, 150)), r.uniform(80, W - 80), r.uniform(0, H),
                                  r.uniform(25, 55), r.uniform(0, 6.28)))

    def render(self, t):
        im = self.bg.copy()
        e = ease_out_cubic(t / 0.6)
        im.alpha_composite(self.left, (int(-W / 2 * (1 - e)), 0))
        im.alpha_composite(self.right, (int(W / 2 + W / 2 * (1 - e)), 0))
        for spr, x, y, sp, ph in self.floaters:
            yy = (y - sp * t) % (H + 300) - 150
            rot = spr.rotate(12 * math.sin(t * 0.8 + ph), Image.BICUBIC, expand=True)
            paste_center(im, rot, x + 25 * math.sin(t * 0.5 + ph), yy, 0.35 * clamp((t - 0.4) / 0.6))
        pulse = 1 + 0.02 * math.sin(t * 3)
        paste_center(im, scaled(self.l1, ease_out_back((t - 0.5) / 0.45) * pulse), W / 2, 330)
        paste_center(im, scaled(self.l2, ease_out_back((t - 0.7) / 0.5) * pulse), W / 2, 520)
        for i, c in enumerate(self.chips):
            s = ease_out_back((t - 1.3 - 0.2 * i) / 0.4)
            x = W / 2 + (i - 1) * 560
            paste_center(im, scaled(c, s), x, 780)
        fade_out = clamp((t - (self.dur - 0.35)) / 0.35)
        if fade_out > 0:
            im.alpha_composite(Image.new("RGBA", (W, H), BG + (int(255 * fade_out),)))
        return im


class WheelScene(Scene):
    R = 380

    def __init__(self, tts, round_no, rounds, subject, rng):
        super().__init__()
        self.subject = subject
        names = list(SUBJECTS)
        rng.shuffle(names)
        self.names = names
        n = len(names)
        self.seg = 360 / n
        idx = names.index(subject)
        # wheel image: segment i spans [i*seg, (i+1)*seg) measured clockwise from 12 o'clock
        self.wheel = self.draw_wheel()
        target_mod = (-(idx + 0.5) * self.seg + rng.uniform(-0.3, 0.3) * self.seg) % 360
        self.turns = 5
        self.final_rot = 360 * self.turns + target_mod
        self.spin_start, self.spin_len = 1.0, 5.2

        ordinal = ["one", "two", "three", "four", "five", "six"][round_no - 1]
        intro = "Final round!" if round_no == rounds and rounds > 1 else f"Round {ordinal}!"
        v1 = tts.say(f"{intro} Let's spin the wheel for a random subject.")
        v2 = tts.say(rng.choice([f"{subject}! Let's go.", f"It's {subject}! Here we go.",
                                 f"{subject}! Oh, this should be good."]))
        self.voices.append((0.3, v1))
        self.land = self.spin_start + self.spin_len
        self.voices.append((self.land + 0.45, v2))
        self.dur = self.land + 0.45 + len(v2) / SR + 1.1

        self.clicks = []
        last = None
        for ms in range(int(self.spin_len * 1000)):
            a = self.angle(self.spin_start + ms / 1000)
            k = int((a + 1e-6) // self.seg)
            if last is not None and k != last:
                self.clicks.append(self.spin_start + ms / 1000)
            last = k
        for c in self.clicks:
            self.sounds.append((c, sfx_click(), 0.9))
        self.sounds += [(self.spin_start - 0.05, sfx_whoosh(0.5), 0.6), (self.land, sfx_fanfare(), 1.0),
                        (self.land + 0.15, sfx_pop(), 0.9), (self.dur - 0.5, sfx_whoosh(0.45), 0.7)]

        self.bg = dark_bg()
        self.bokeh = Bokeh(round_no)
        self.title = text_img(f"ROUND {round_no} OF {rounds}", font("Black", 72))
        self.sub1 = text_img("Spinning for a random subject...", font("SemiBold", 40), fill=(200, 205, 235))
        self.sub2 = text_img("Your subject is...", font("SemiBold", 40), fill=(200, 205, 235))
        self.hub = circle(150, (255, 255, 255, 255))
        hq = text_img("?", font("Black", 90), fill=(20, 22, 45), shadow=False)
        paste_center(self.hub, hq, 75, 72)
        rim = circle(2 * self.R + 36, (255, 255, 255, 255))
        dots = Image.new("RGBA", rim.size)
        for i in range(n * 2):
            a = math.radians(i * 180 / n)
            cx = rim.width / 2 + (self.R + 9) * math.sin(a)
            cy = rim.height / 2 - (self.R + 9) * math.cos(a)
            paste_center(dots, circle(14, (255, 214, 10, 255)), cx, cy)
        rim.alpha_composite(dots)
        self.rim = rim
        self.rim_shadow = soft_circle(2 * self.R + 40, (0, 0, 0, 170), 18)
        self.pointer = self.draw_pointer()
        col = SUBJECTS[subject]["color"]
        e = emoji(SUBJECTS[subject]["emoji"], 200)
        name = text_img(subject.upper(), font("Black", 130))
        cw = max(name.width, e.width) + 160
        card = rounded_card(cw, 470, 60, col + (255,), outline=(255, 255, 255, 255), width=8)
        paste_center(card, e, cw / 2, 150)
        paste_center(card, name, cw / 2, 345)
        self.card = card

    def angle(self, t):
        x = clamp((t - self.spin_start) / self.spin_len)
        return self.final_rot * (1 - (1 - x) ** 4)

    def draw_wheel(self):
        ss = 2
        R = self.R * ss
        im = Image.new("RGBA", (2 * R, 2 * R))
        d = ImageDraw.Draw(im)
        for i, nm in enumerate(self.names):
            col = SUBJECTS[nm]["color"]
            d.pieslice((0, 0, 2 * R - 1, 2 * R - 1), -90 + i * self.seg, -90 + (i + 1) * self.seg,
                       fill=col + (255,), outline=(255, 255, 255, 255), width=6)
        im = im.resize((2 * self.R, 2 * self.R), Image.LANCZOS)
        for i, nm in enumerate(self.names):
            label = Image.new("RGBA", (330, 90))
            e = emoji(SUBJECTS[nm]["emoji"], 62)
            fsize = 38 if len(nm) < 9 else 32
            tx = text_img(nm, font("ExtraBold", fsize), shadow=True)
            label.alpha_composite(e, (300 - e.width, (90 - e.height) // 2))
            label.alpha_composite(tx, (max(0, 300 - e.width - 8 - tx.width), (90 - tx.height) // 2))
            mid = (i + 0.5) * self.seg  # clockwise from top
            # label reads from rim (right end = emoji at rim) towards center
            rot = label.rotate(90 - mid, Image.BICUBIC, expand=True)
            a = math.radians(mid)
            r = self.R * 0.58
            paste_center(im, rot, self.R + r * math.sin(a), self.R - r * math.cos(a))
        return im

    def draw_pointer(self):
        ss = 4
        w, h = 90, 110
        im = Image.new("RGBA", (w * ss, h * ss))
        d = ImageDraw.Draw(im)
        d.polygon([(0, 0), (w * ss, 0), (w * ss / 2, h * ss)], fill=(255, 255, 255, 255))
        d.polygon([(14 * ss, 8 * ss), (w * ss - 14 * ss, 8 * ss), (w * ss / 2, h * ss - 26 * ss)],
                  fill=(255, 69, 58, 255))
        return im.resize((w, h), Image.LANCZOS)

    def render(self, t):
        im = self.bg.copy()
        self.bokeh.draw(im, t)
        cx, cy = W / 2, 640
        intro = ease_out_back(t / 0.6)
        paste_center(im, self.title, W / 2, 85, clamp(t / 0.4))
        landed = t >= self.land
        paste_center(im, self.sub2 if landed else self.sub1, W / 2, 150, clamp(t / 0.4))
        s = 0.6 + 0.4 * intro
        paste_center(im, scaled(self.rim_shadow, s), cx, cy + 14 * s)
        paste_center(im, scaled(self.rim, s), cx, cy)
        wheel = self.wheel.rotate(-self.angle(t), Image.BICUBIC)
        paste_center(im, scaled(wheel, s), cx, cy)
        if landed:  # highlight the winning slice
            k = clamp((t - self.land) / 0.25) * (0.55 + 0.25 * math.sin((t - self.land) * 14))
            hl = Image.new("RGBA", (2 * self.R, 2 * self.R))
            ImageDraw.Draw(hl).pieslice((0, 0, 2 * self.R - 1, 2 * self.R - 1), -90 - self.seg / 2,
                                        -90 + self.seg / 2, fill=(255, 255, 255, int(110 * k)))
            paste_center(im, hl, cx, cy)
        paste_center(im, scaled(self.hub, s), cx, cy)
        # pointer flicks back on every click, like a real wheel
        flick = 0.0
        for c in self.clicks:
            if c <= t:
                flick = max(flick, 22 * math.exp(-(t - c) * 25))
        p = self.pointer.rotate(flick, Image.BICUBIC, expand=True)
        paste_center(im, p, cx, cy - self.R * s - 2)
        if landed:
            k = clamp((t - self.land - 0.25) / 0.35)
            im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(140 * k))))
            paste_center(im, scaled(self.card, ease_out_back((t - self.land - 0.25) / 0.5)), W / 2, 590)
        fade = clamp((t - (self.dur - 0.35)) / 0.35)
        if fade > 0:
            im.alpha_composite(Image.new("RGBA", (W, H), BG + (int(255 * fade),)))
        return im


def make_panel(top, bot, emo, text):
    w = W // 2
    p = vgradient(w, H, top, bot).convert("RGBA")
    p.alpha_composite(radial_glow(w, H, w / 2, 340, 420, (255, 255, 255), 0.22))
    # subtle diagonal stripes for texture
    stripes = Image.new("RGBA", (w, H))
    d = ImageDraw.Draw(stripes)
    for x in range(-H, w, 60):
        d.line((x, H, x + H, 0), fill=(255, 255, 255, 9), width=22)
    p.alpha_composite(stripes)
    e = emoji(emo, 230)
    sh = Image.new("RGBA", (e.width + 80, e.height + 80))
    sh.alpha_composite(e, (40, 40))
    shadow = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    shadow.putalpha(sh.getchannel("A").point(lambda v: v * 0.35))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    paste_center(p, shadow, w / 2, 345 + 14)
    paste_center(p, e, w / 2, 330)
    size = 64
    while True:
        f = font("ExtraBold", size)
        lines = wrap(text, f, 690)
        fits = len(lines) <= 3 and all(f.getlength(ln) <= 700 for ln in lines)
        if fits or size <= 40:
            break
        size -= 4
    lh = int(size * 1.18)
    y0 = 560 - (len(lines) - 1) * lh / 2
    for i, ln in enumerate(lines):
        paste_center(p, text_img(ln, font("ExtraBold", size)), w / 2, y0 + i * lh)
    return p


class QuestionScene(Scene):
    def __init__(self, tts, q, pct_a, subject, round_no, rounds, qi, per_round, overall, total, prefix, rng):
        super().__init__()
        a, ea, b, eb, _, fact = q
        self.pct = (pct_a, 100 - pct_a)
        self.win = 0 if pct_a >= 50 else 1
        win_text = (a if self.win == 0 else b)
        win_text = win_text[0].lower() + win_text[1:]
        v1 = tts.say(f"{prefix}Would you rather {a.lower()[0] + a[1:]}... or {b.lower()[0] + b[1:]}?")
        v2 = tts.say(f"{max(self.pct)} percent would rather {win_text}! {fact}")
        self.t_in = 0.5
        self.cd_start = self.t_in + len(v1) / SR + 0.35
        self.reveal = self.cd_start + COUNTDOWN
        self.voices += [(self.t_in, v1), (self.reveal + 0.75, v2)]
        self.t_out = max(self.reveal + 0.75 + len(v2) / SR + 0.8, self.reveal + 3.5)
        self.dur = self.t_out + 0.45
        self.sounds += [(0.0, sfx_whoosh(0.45), 0.8), (0.4, sfx_pop(), 0.9)]
        for k in range(COUNTDOWN):
            self.sounds.append((self.cd_start + k, sfx_tick(high=k >= COUNTDOWN - 3), 1.0))
        self.sounds += [(self.reveal - 1.25, sfx_riser(1.2), 0.6), (self.reveal, sfx_ding(), 1.0),
                        (self.reveal + 1.0, sfx_pop(), 0.6), (self.t_out, sfx_whoosh(0.45), 0.7)]

        self.panels = (make_panel(RED_TOP, RED_BOT, ea, a), make_panel(BLUE_TOP, BLUE_BOT, eb, b))
        self.bg = Image.new("RGBA", (W, H), BG + (255,))
        # header
        hdr = Image.new("RGBA", (W, 100), (8, 9, 22, 150))
        col = SUBJECTS[subject]["color"]
        st = text_img(subject.upper(), font("Black", 38), shadow=False)
        chip = rounded_card(st.width + 90, 64, 32, (16, 18, 40, 255), outline=col + (255,), width=4)
        paste_center(chip, emoji(SUBJECTS[subject]["emoji"], 40), 38, 32)
        paste_center(chip, st, 50 + st.width / 2, 32)
        hdr.alpha_composite(chip, (36, 18))
        paste_center(hdr, text_img("WOULD YOU RATHER...?", font("Black", 40)), W / 2, 50)
        rt = text_img(f"ROUND {round_no}/{rounds}  •  Q{qi}/{per_round}", font("Bold", 34), fill=(225, 228, 245))
        hdr.alpha_composite(rt, (W - 36 - rt.width + 24, 50 - rt.height // 2))
        self.header = hdr
        self.progress = (overall - 1) / total, overall / total
        self.badge = circle(200, (255, 255, 255, 255))
        self.badge_shadow = soft_circle(210, (0, 0, 0, 150), 12)
        self.or_txt = text_img("OR", font("Black", 78), fill=(20, 22, 45), shadow=False)
        self.majority = []
        for side in (0, 1):
            ti = text_img("MAJORITY", font("Black", 34), fill=(RED_BOT, BLUE_BOT)[side], shadow=False)
            card = rounded_card(ti.width + 90, 70, 35, (255, 255, 255, 250))
            paste_center(card, emoji("👑", 40), 42, 35)
            paste_center(card, ti, 58 + ti.width / 2, 35)
            self.majority.append(card)
        # fact card
        ftxt = font("SemiBold", 36, display=False)
        lines = wrap(fact, ftxt, 1410)
        ch = 64 + 46 * len(lines)
        card = rounded_card(1560, ch, 30, (12, 14, 32, 235), outline=(255, 214, 10, 255), width=3)
        paste_center(card, emoji("💡", 60), 66, ch / 2)
        lab = text_img("FUN FACT", font("Black", 24), fill=YELLOW, shadow=False)
        card.alpha_composite(lab, (110 - 24, 12 - 24 + 8))
        for i, ln in enumerate(lines):
            li = text_img(ln, ftxt, shadow=False)
            card.alpha_composite(li, (110 - 24, 44 + i * 46 - 24 + 4))
        self.fact = card
        self._num = {}

    def number(self, n, color):
        key = (n, color)
        if key not in self._num:
            self._num[key] = text_img(str(n), font("Black", 110), fill=color, shadow=False)
        return self._num[key]

    def render(self, t):
        im = self.bg.copy()
        if t < self.t_out:
            e = ease_out_cubic(t / 0.55)
        else:
            e = 1 - ease_in_cubic((t - self.t_out) / 0.45)
        offx = (W / 2) * (1 - e)
        rv = t - self.reveal
        for side in (0, 1):
            x = int(-offx) if side == 0 else int(W / 2 + offx)
            im.alpha_composite(self.panels[side], (x, 0))
            if rv > 0:
                pct = self.pct[side]
                k = ease_out_cubic(rv / 1.0)
                fill_h = int((H - 100) * pct / 100 * k)
                ov = Image.new("RGBA", (W // 2, fill_h), (255, 255, 255, 34))
                im.alpha_composite(ov, (x, H - fill_h))
                if side != self.win:
                    dk = clamp((rv - 1.0) / 0.4)
                    im.alpha_composite(Image.new("RGBA", (W // 2, H), (0, 0, 0, int(105 * dk))), (x, 0))
                shown = int(round(pct * k))
                pi = text_img(f"{shown}%", font("Black", 150), stroke=0)
                paste_center(im, scaled(pi, 1 + 0.15 * math.sin(math.pi * clamp(rv / 0.5))), x + W / 4, 790)
                if side == self.win:
                    paste_center(im, scaled(self.majority[side], ease_out_back((rv - 1.0) / 0.4)), x + W / 4, 160)
        # OR badge + countdown ring
        bs = ease_out_back((t - 0.35) / 0.4) * e
        cx, cy = W / 2, 560
        if bs > 0.01:
            paste_center(im, scaled(self.badge_shadow, bs), cx, cy + 10)
            paste_center(im, scaled(self.badge, bs), cx, cy)
            cd = t - self.cd_start
            if 0 <= cd < COUNTDOWN:
                n = COUNTDOWN - int(cd)
                alarm = n <= 3
                col = ALARM if alarm else (20, 22, 45)
                frac = 1 - cd / COUNTDOWN
                ring = Image.new("RGBA", (520, 520))
                d = ImageDraw.Draw(ring)
                d.ellipse((20, 20, 500, 500), outline=(255, 255, 255, 90), width=26)
                d.arc((20, 20, 500, 500), -90, -90 + 360 * frac, fill=(ALARM if alarm else YELLOW) + (255,), width=26)
                paste_center(im, ring.resize((260, 260), Image.LANCZOS), cx, cy)
                pop = 1 + 0.35 * (1 - ease_out_cubic((cd % 1) / 0.35))
                paste_center(im, scaled(self.number(n, col), pop * bs), cx, cy + 2)
            else:
                paste_center(im, scaled(self.or_txt, bs), cx, cy + 2)
        # header + progress bar
        hy = int(-100 * (1 - ease_out_cubic(t / 0.4)))
        im.alpha_composite(self.header, (0, hy))
        p0, p1 = self.progress
        pr = p0 + (p1 - p0) * clamp((t - self.reveal) / 0.8)
        d = ImageDraw.Draw(im)
        d.rectangle((0, hy + 100, W, hy + 106), fill=(255, 255, 255, 40))
        d.rectangle((0, hy + 100, int(W * pr), hy + 106), fill=YELLOW + (255,))
        # fun fact card
        fk = ease_out_back((rv - 0.7) / 0.5) if rv > 0.7 else 0
        if fk > 0 and t < self.t_out + 0.2:
            fy = H + self.fact.height - (self.fact.height + 40 + self.fact.height / 2) * fk
            fy += (H - fy + self.fact.height) * ease_in_cubic((t - self.t_out) / 0.2) if t > self.t_out else 0
            paste_center(im, self.fact, W / 2, fy)
        return im


class OutroScene(Scene):
    def __init__(self, tts, total):
        super().__init__()
        hi, mid = math.ceil(total * 0.75), math.ceil(total * 0.4)
        self.rows = [("🧠", f"{hi}–{total}", "You ARE the majority"),
                     ("⚖", f"{mid}–{hi - 1}", "Perfectly balanced"),
                     ("🦄", f"0–{mid - 1}", "A total original")]
        line = (f"That's a wrap! So, how many times did you side with the majority? "
                f"If you got {hi} or more, you basically are the majority. "
                f"{mid} to {hi - 1}? Perfectly balanced. "
                f"And fewer than {mid}? You're a total original. "
                "Comment your score below, and subscribe for another random spin!")
        v = tts.say(line)
        self.voices.append((0.6, v))
        self.dur = 0.6 + len(v) / SR + 2.5
        self.sounds += [(0.0, sfx_whoosh(0.6), 0.8), (0.3, sfx_fanfare(), 0.8)]
        self.bg = dark_bg()
        self.bokeh = Bokeh(99)
        self.title = text_img("THAT'S A WRAP!", font("Black", 140))
        self.q = text_img("How many times did you pick the majority?", font("Bold", 48), fill=(210, 214, 240))
        self.cards = []
        for i, (e, rng_, label) in enumerate(self.rows):
            card = rounded_card(1100, 120, 30, ((RED_BOT, (130, 70, 220), BLUE_BOT)[i]) + (255,),
                                outline=(255, 255, 255, 200), width=3)
            paste_center(card, emoji(e, 72), 80, 60)
            ri = text_img(rng_, font("Black", 56))
            card.alpha_composite(ri, (150 - 24, 60 - ri.height // 2))
            li = text_img(label, font("Bold", 50))
            card.alpha_composite(li, (1100 - 50 - li.width + 24, 60 - li.height // 2))
            self.cards.append(card)
            self.sounds.append((1.0 + 0.25 * i, sfx_pop(), 0.8))
        cta = text_img("COMMENT YOUR SCORE  ·  SUBSCRIBE FOR MORE", font("Black", 44), fill=(20, 22, 45), shadow=False)
        self.cta = rounded_card(cta.width + 80, 100, 50, YELLOW + (255,))
        paste_center(self.cta, cta, self.cta.width / 2, 50)
        self.sounds.append((1.9, sfx_pop(), 0.8))

    def render(self, t):
        im = self.bg.copy()
        self.bokeh.draw(im, t)
        paste_center(im, scaled(self.title, ease_out_back((t - 0.2) / 0.5) * (1 + 0.015 * math.sin(t * 3))), W / 2, 190)
        paste_center(im, self.q, W / 2, 320, clamp((t - 0.6) / 0.4))
        for i, c in enumerate(self.cards):
            k = ease_out_cubic((t - 1.0 - 0.25 * i) / 0.45)
            paste_center(im, c, W / 2 + (1 - k) * (W * (1 if i % 2 else -1)), 470 + i * 145, clamp(k * 1.5))
        paste_center(im, scaled(self.cta, ease_out_back((t - 1.9) / 0.5)), W / 2, 950)
        fade = clamp((t - (self.dur - 1.2)) / 1.2)
        if fade > 0:
            im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * fade))))
        return im


# ----------------------------------------------------------------------------
# building + rendering
# ----------------------------------------------------------------------------

PREFIXES_FIRST = ["First question. ", "Let's start easy. ", "Okay, first one. "]
PREFIXES = ["", "Next up. ", "Okay. ", "Hmm, this one's tough. ", "Think fast. ", "Here's a hard one. ",
            "Alright. ", "Oh, I like this one. "]


def build(seed, rounds, per_round):
    rng = random.Random(seed)
    tts = TTS()
    subjects = rng.sample(list(SUBJECTS), rounds)
    total = rounds * per_round
    plan = []
    for s in subjects:
        qs = rng.sample(SUBJECTS[s]["questions"], per_round)
        plan.append((s, [(q, int(clamp(q[4] + rng.randint(-3, 3), 5, 95))) for q in qs]))
    print(f"Seed {seed}: subjects = {', '.join(subjects)}")

    sample_emojis = [SUBJECTS[s]["emoji"] for s in SUBJECTS] + ["🤔", "❓", "😱"]
    scenes = [IntroScene(tts, rounds, total, sample_emojis)]
    overall = 0
    for r, (s, qs) in enumerate(plan, 1):
        scenes.append(WheelScene(tts, r, rounds, s, rng))
        for i, (q, pct) in enumerate(qs, 1):
            overall += 1
            if overall == total:
                prefix = "Final question! "
            elif i == 1:
                prefix = rng.choice(PREFIXES_FIRST)
            else:
                prefix = rng.choice(PREFIXES)
            scenes.append(QuestionScene(tts, q, pct, s, r, rounds, i, per_round, overall, total, prefix, rng))
    scenes.append(OutroScene(tts, total))
    starts, t = [], 0.0
    for sc in scenes:
        starts.append(t)
        t += sc.dur
    return scenes, starts, t


def mix_audio(scenes, starts, total):
    n = int(total * SR) + SR
    voice = np.zeros(n)
    fx = np.zeros(n)
    for sc, st in zip(scenes, starts):
        for at, arr in sc.voices:
            i = int((st + at) * SR)
            voice[i:i + len(arr)] += arr[: n - i]
        for at, arr, g in sc.sounds:
            i = int((st + at) * SR)
            fx[i:i + len(arr)] += arr[: n - i] * g
    music = np.zeros(n)
    m = make_music(total)
    music[: len(m)] = m
    # sidechain: duck music while the narrator talks
    env = lowpass(np.abs(voice), 8)
    duck = 1 - 0.6 * np.clip(env / 0.05, 0, 1)
    duck = lowpass(duck, 3)
    mix = voice * 1.0 + fx * 0.55 + music * 0.22 * duck
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    stereo = np.stack([mix, mix], axis=1)
    return (np.clip(stereo, -1, 1) * 32767).astype(np.int16)


def write_wav(path, data):
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


G = {}


def frame_at(i):
    scenes, starts = G["scenes"], G["starts"]
    t = i / FPS
    k = max(0, np.searchsorted(starts, t, side="right") - 1)
    sc = scenes[k]
    return sc.render(min(t - starts[k], sc.dur - 1e-4)).convert("RGB")


def render_chunk(args):
    idx, a, b, path = args
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "22",
           "-pix_fmt", "yuv420p", "-g", "60", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(a, b):
        p.stdin.write(frame_at(i).tobytes())
        if idx == 0 and (i - a) % 150 == 0:
            print(f"  chunk 0: {i - a}/{b - a} frames", flush=True)
    p.stdin.close()
    p.wait()
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=None, help="random seed (default: random)")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--per-round", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(HERE, "would_you_rather.mp4"))
    ap.add_argument("--stills", default=None, help="only render PNG stills at these comma-separated seconds")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    if args.rounds > len(SUBJECTS):
        sys.exit(f"At most {len(SUBJECTS)} rounds")
    if args.per_round > 5:
        sys.exit("At most 5 questions per round")
    seed = args.seed if args.seed is not None else random.randrange(1_000_000)

    scenes, starts, total = build(seed, args.rounds, args.per_round)
    G["scenes"], G["starts"] = scenes, starts
    nframes = int(total * FPS)
    for sc, st in zip(scenes, starts):
        print(f"  {st:7.2f}s  {type(sc).__name__}")
    print(f"Duration {total:.1f}s, {nframes} frames")

    if args.stills:
        os.makedirs(os.path.join(CACHE_DIR, "stills"), exist_ok=True)
        for s in args.stills.split(","):
            p = os.path.join(CACHE_DIR, "stills", f"still_{float(s):07.2f}.png")
            frame_at(int(float(s) * FPS)).save(p)
            print(p)
        return

    work = os.path.join(CACHE_DIR, "render")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    wav = os.path.join(work, "audio.wav")
    write_wav(wav, mix_audio(scenes, starts, total))

    n = max(1, args.workers)
    bounds = [round(nframes * k / n) for k in range(n + 1)]
    jobs = [(k, bounds[k], bounds[k + 1], os.path.join(work, f"part{k}.mp4")) for k in range(n)]
    with mp.get_context("fork").Pool(n) as pool:
        parts = pool.map(render_chunk, jobs)
    lst = os.path.join(work, "parts.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-15:TP=-1.5:LRA=11", "-ar", str(SR), "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", args.out], check=True)
    print(f"Done: {args.out}  (seed {seed})")


if __name__ == "__main__":
    main()
