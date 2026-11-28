#!/usr/bin/env python3
"""Christmas background music, synthesised note by note: an original instrumental arrangement of the
"Jingle Bells" chorus (James Lord Pierpont, 1857: public domain). Glockenspiel melody, a bright lead on
the second pass, oom-pah bass, piano chord stabs on the off-beats, kick and clap, and sleigh bells on every
eighth note. 130 BPM in 4/4, so it locks to the quiz's beat grid. Also Christmas sound effects.

    python3 christmas_music.py 40      # writes a 40 s preview to .cache/xmas_preview.wav
"""

import math
import os
import sys

import numpy as np

import make_minecraft_quiz as mq
import make_video as mv

SR = mv.SR
BPM = 130
BEAT = 60 / BPM

C4, D4, E4, F4, G4 = 60, 62, 64, 65, 67
_A = [(E4, 1), (E4, 1), (E4, 2), (E4, 1), (E4, 1), (E4, 2), (E4, 1), (G4, 1), (C4, 1.5), (D4, 0.5), (E4, 4)]
HALF1 = _A + [(F4, 1), (F4, 1), (F4, 1.5), (F4, 0.5), (F4, 1), (E4, 1), (E4, 1), (E4, 0.5), (E4, 0.5),
              (E4, 1), (D4, 1), (D4, 1), (E4, 1), (D4, 2), (G4, 2)]
HALF2 = _A + [(F4, 1), (F4, 1), (F4, 1.5), (F4, 0.5), (F4, 1), (E4, 1), (E4, 1), (E4, 0.5), (E4, 0.5),
              (G4, 1), (G4, 1), (F4, 1), (D4, 1), (C4, 4)]
MELODY = HALF1 + HALF2                                   # 16 bars, 64 beats
CHORDS = ["C", "C", "C", "C", "F", "C", "D7", "G7", "C", "C", "C", "C", "F", "C", "G7", "C"]
VOICING = {"C": [60, 64, 67], "F": [60, 65, 69], "D7": [62, 66, 69, 72], "G7": [59, 62, 65, 67]}
ROOT = {"C": (48, 43), "F": (41, 48), "D7": (50, 45), "G7": (43, 50)}     # (root, fifth) for the oom-pah bass


def tt(d):
    return np.arange(max(1, int(d * SR))) / SR


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def glock(m, vel=1.0):
    f, t = hz(m), tt(1.5)
    x = np.zeros_like(t)
    for ratio, amp, dec in ((1, 1.0, 3.2), (2.756, 0.32, 9.0), (5.404, 0.12, 16.0), (8.933, 0.05, 26.0)):
        x += amp * np.sin(2 * np.pi * f * ratio * t) * np.exp(-t * dec)
    return x * np.minimum(1, t / 0.002) * vel


def lead(m, dur, vel=1.0):
    f, t = hz(m), tt(dur + 0.12)
    ph = 2 * np.pi * f * t + 0.004 * np.sin(2 * np.pi * 5.5 * t) * f / 5.5 * np.minimum(1, t / 0.25)
    x = sum(np.sin(k * ph) / k for k in (1, 3, 5, 7, 9))
    env = np.minimum(1, t / 0.012) * np.where(t < dur, 0.85 + 0.15 * np.exp(-t * 6), 0.85 * np.exp(-(t - dur) * 30))
    return mv.lowpass(x * env, 3200) * vel


def bass(m, dur):
    f, t = hz(m), tt(dur)
    x = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
    return x * np.exp(-t * 3.2) * np.minimum(1, t / 0.004) * np.minimum(1, (dur - t) / 0.02)


def chord(name, vel=0.4):
    out = None
    for n in VOICING[name]:
        p = mq.piano_note(hz(n), vel, 0.8)
        out = p if out is None else out[:len(p)] + p[:len(out)]
    return out / len(VOICING[name])


def kick():
    t = tt(0.32)
    f = 48 + 95 * np.exp(-t * 26)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8.5)


def clap(seed=3):
    t = tt(0.22)
    n = np.random.default_rng(seed).standard_normal(len(t))
    body = mv.lowpass(n, 5200) - mv.lowpass(n, 900)
    bursts = sum(np.exp(-np.maximum(t - d, 0) * 38) * (t >= d) for d in (0.0, 0.011, 0.022))
    return body * bursts * 0.9 + 0.2 * np.sin(2 * np.pi * 210 * t) * np.exp(-t * 30)


def sleigh(seed=0, vel=1.0):
    """A shake of sleigh bells: a few tiny metallic jingles a few milliseconds apart."""
    r = np.random.default_rng(seed)
    t = tt(0.16)
    x = np.zeros_like(t)
    for d in (0.0, 0.012 + r.uniform(0, 0.006), 0.026 + r.uniform(0, 0.008), 0.045 + r.uniform(0, 0.01)):
        tj = np.maximum(t - d, 0)
        on = t >= d
        for f in (5200, 6900, 8400, 10100):
            x += on * np.sin(2 * np.pi * f * r.uniform(0.97, 1.03) * tj + r.uniform(0, 6)) * np.exp(-tj * 70) * 0.25
    noise = mv.highpass(r.standard_normal(len(t)), 7000) * np.exp(-t * 45) * 0.35
    return (x + noise) * vel


def add(buf, at, x, g=1.0):
    i = int(at * SR)
    if i >= len(buf) or i < 0:
        return
    buf[i:i + len(x)] += x[:len(buf) - i] * g


def make_jingle(total):
    """Background track of `total` seconds: the chorus loops, every other pass gets the bright lead too."""
    n = int(total * SR) + SR
    tracks = {k: np.zeros(n) for k in ("mel", "lead", "keys", "bass", "kick", "clap", "bells")}
    bars = int(math.ceil(total / (4 * BEAT))) + 1
    for bar in range(bars):
        t0 = bar * 4 * BEAT
        ch = CHORDS[bar % 16]
        root, fifth = ROOT[ch]
        add(tracks["bass"], t0, bass(root, 1.9 * BEAT))
        add(tracks["bass"], t0 + 2 * BEAT, bass(fifth, 1.9 * BEAT))
        for b in (1, 3):                                   # piano stabs on the off-beats: oom-PAH
            add(tracks["keys"], t0 + b * BEAT, chord(ch))
        for b in (0, 2):
            add(tracks["kick"], t0 + b * BEAT, kick())
        for b in (1, 3):
            add(tracks["clap"], t0 + b * BEAT, clap(bar * 4 + b))
        for e in range(8):                                 # sleigh bells on every eighth, accents on the beat
            add(tracks["bells"], t0 + e * BEAT / 2, sleigh(bar * 8 + e, 1.0 if e % 2 == 0 else 0.6))
    beat = 0.0
    passes = int(math.ceil(total / (64 * BEAT))) + 1
    for p in range(passes):
        for m, d in MELODY:
            at = beat * BEAT
            add(tracks["mel"], at, glock(m + 12))
            if p % 2 == 1:
                add(tracks["lead"], at, lead(m, d * BEAT * 0.92))
            beat += d
    mix = (0.55 * tracks["mel"] + 0.22 * tracks["lead"] + 0.5 * tracks["keys"] + 0.6 * tracks["bass"] +
           0.75 * tracks["kick"] + 0.32 * tracks["clap"] + 0.16 * tracks["bells"])
    mix = mix[:int(total * SR)]
    fade = np.ones_like(mix)
    k = int(0.6 * SR)
    fade[-k:] = np.linspace(1, 0, k)
    mix *= fade
    return mix / (np.abs(mix).max() + 1e-9) * 0.9


def sfx_jingle():
    """A longer sleigh-bell shake for the reveal."""
    out = np.zeros(int(0.7 * SR))
    for k in range(9):
        add(out, k * 0.055, sleigh(100 + k, 1.0 - k * 0.07))
    return out / (np.abs(out).max() + 1e-9)


def sfx_chime(m=84):
    x = glock(m) + 0.6 * np.concatenate([np.zeros(int(0.09 * SR)), glock(m + 7)])[:len(glock(m))]
    return x / (np.abs(x).max() + 1e-9)


if __name__ == "__main__":
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    out = make_jingle(secs)
    os.makedirs(mv.CACHE_DIR, exist_ok=True)
    p = os.path.join(mv.CACHE_DIR, "xmas_preview.wav")
    mv.write_wav(p, (np.clip(np.stack([out, out], 1), -1, 1) * 32767).astype(np.int16))
    print(p)
