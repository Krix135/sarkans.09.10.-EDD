"""Original, copyright-free background music for the Shorts.

make_phonk(): a phonk-style loop (cowbell melody, gliding 808 bass, punchy kick,
half-time clap and rolling hi-hats) in F minor at 130 BPM.
"""

import math

import numpy as np
from scipy.signal import fftconvolve, lfilter

SR = 48000


def tt(d):
    return np.arange(int(d * SR)) / SR


def lowpass(x, fc):
    a = math.exp(-2 * math.pi * fc / SR)
    return lfilter([1 - a], [1, -a], x)


def highpass(x, fc):
    return x - lowpass(x, fc)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def square(f, d):
    t = tt(d)
    return np.sign(np.sin(2 * np.pi * f * t))


def cowbell(f, d=0.22):
    """808-style cowbell: two detuned squares (ratio ~1.48), band-passed, fast decay."""
    t = tt(d)
    s = 0.6 * square(f, d) + 0.4 * square(f * 1.48, d)
    s = lowpass(highpass(s, 380), 3800)
    env = np.minimum(1, t / 0.002) * (0.65 * np.exp(-t * 28) + 0.35 * np.exp(-t * 9))
    return s * env


def kick(d=0.45):
    t = tt(d)
    f = 48 + 140 * np.exp(-t * 32)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    click = highpass(np.random.default_rng(1).standard_normal(len(t)), 2000) * np.exp(-t * 300) * 0.3
    return np.tanh(2.2 * (s + click))


def clap(d=0.4):
    t = tt(d)
    rng = np.random.default_rng(2)
    n = lowpass(highpass(rng.standard_normal(len(t)), 900), 6000)
    env = np.zeros_like(t)
    for off in (0.0, 0.011, 0.022):  # the classic triple-hit clap
        env += (t >= off) * np.exp(-np.maximum(t - off, 0) * 70)
    env += np.exp(-t * 9) * 0.35  # tail
    return n * env * 0.8


def hat(d=0.05, open_=False):
    t = tt(d if not open_ else 0.25)
    n = highpass(np.random.default_rng(3).standard_normal(len(t)), 7500)
    return n * np.exp(-t * (110 if not open_ else 14))


def bass808(f0, d, glide_to=None):
    t = tt(d)
    f = np.full_like(t, f0)
    if glide_to:
        k = np.clip((t - d * 0.55) / (d * 0.3), 0, 1)
        f = f0 * (glide_to / f0) ** k
    s = np.sin(2 * np.pi * np.cumsum(f) / SR)
    env = np.minimum(1, t / 0.004) * np.exp(-t * 1.6)
    env[-int(0.02 * SR):] *= np.linspace(1, 0, int(0.02 * SR))
    return np.tanh(2.6 * s * env) * 0.9


def make_phonk(total, bpm=130):
    beat = 60 / bpm
    st = beat / 4  # sixteenth
    bars = 8
    L = bars * 4 * beat
    out = {k: np.zeros(int((L + 2) * SR)) for k in ("kick", "clap", "hat", "bass", "bell")}

    def add(track, sig, at, g=1.0):
        i = int(at * SR)
        e = min(len(out[track]), i + len(sig))
        out[track][i:e] += sig[: e - i] * g

    K, C, Hc, Ho = kick(), clap(), hat(), hat(open_=True)
    roots = [29, 37, 39, 36]  # F1, Db2, Eb2, C2  (i - VI - VII - V in F minor)
    bell_a = [72, None, None, 72, None, None, 72, None, 75, None, 72, None, 70, None, 68, None]
    bell_b = [72, None, None, 72, None, None, 72, None, 77, None, 75, None, 72, None, 70, None]
    bells = {}
    for b in range(bars):
        t0 = b * 4 * beat
        for s16 in (0, 6, 10):  # syncopated kick
            add("kick", K, t0 + s16 * st)
        if b % 2 == 1:
            add("kick", K, t0 + 14 * st, 0.7)
        add("clap", C, t0 + 8 * st)  # half-time snare on beat 3
        for s16 in range(16):
            roll = b % 2 == 1 and s16 >= 12
            if roll:  # hi-hat roll into the next bar
                for r in range(2):
                    add("hat", Hc, t0 + s16 * st + r * st / 2, 0.55)
            else:
                add("hat", Hc, t0 + s16 * st, 0.75 if s16 % 2 == 0 else 0.45)
        if b % 4 == 3:
            add("hat", Ho, t0 + 15 * st, 0.4)
        r = roots[b % 4]
        nxt = roots[(b + 1) % 4]
        add("bass", bass808(midi(r), 6 * st), t0)
        add("bass", bass808(midi(r), 4 * st), t0 + 6 * st)
        add("bass", bass808(midi(r), 6 * st, glide_to=midi(nxt)), t0 + 10 * st)
        pat = bell_a if b % 2 == 0 else bell_b
        shift = {29: 0, 37: -4, 39: -2, 36: -5}[r]  # follow the chords
        for s16, n in enumerate(pat):
            if n is None:
                continue
            key = n + shift
            if key not in bells:
                bells[key] = cowbell(midi(key))
            add("bell", bells[key], t0 + s16 * st, 1.0 if s16 % 4 == 0 else 0.8)
    mixd = {"kick": 0.95, "clap": 0.55, "hat": 0.16, "bass": 0.75, "bell": 0.32}
    full = sum(out[k] * g for k, g in mixd.items())
    # short room reverb on clap + bell for space
    ir_t = tt(0.9)
    ir = lowpass(np.random.default_rng(8).standard_normal(len(ir_t)), 5000) * np.exp(-ir_t / 0.22)
    ir /= np.sqrt(np.sum(ir ** 2))
    wet = fftconvolve(out["clap"] * 0.5 + out["bell"] * 0.3, ir)[: len(full)]
    full = full + 0.18 * wet
    n = int(L * SR)
    loop = full[:n].copy()
    loop[: len(full) - n] += full[n:]  # wrap the tail so the loop is seamless
    loop = np.tanh(1.3 * loop / (np.abs(loop).max() + 1e-9)) / np.tanh(1.3)
    music = np.tile(loop, int(math.ceil(total / L)) + 1)[: int(total * SR)]
    music[: int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))
    return music / (np.abs(music).max() + 1e-9)
