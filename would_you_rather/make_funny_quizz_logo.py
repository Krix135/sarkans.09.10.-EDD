#!/usr/bin/env python3
""""FUNNY QUIZZ" popcorn badge, redrawn as vector art and rendered sharp at 2048x2048.

The SVG is built here (procedural popcorn, curved ribbon with folded tails, text on a path) and
rendered with the pre-installed Chromium through Node Playwright. Font: Luckiest Guy (SIL OFL),
fetched from npm (@fontsource/luckiest-guy) on first run.

    python3 make_funny_quizz_logo.py                 # -> funny_quizz_logo.png
    python3 make_funny_quizz_logo.py --size 4096
"""

import argparse
import base64
import math
import os
import random
import subprocess
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache", "logo")
FONT = os.path.join(CACHE, "luckiest-guy.woff2")

INK = "#15203f"          # outlines
TEXT = "FUNNY QUIZZ"


def get_font():
    if os.path.exists(FONT):
        return FONT
    os.makedirs(CACHE, exist_ok=True)
    out = subprocess.run(["npm", "pack", "--silent", "@fontsource/luckiest-guy@5.3.0"], cwd=CACHE,
                         capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    with tarfile.open(os.path.join(CACHE, out)) as tf:
        member = tf.getmember("package/files/luckiest-guy-latin-400-normal.woff2")
        with open(FONT, "wb") as fh:
            fh.write(tf.extractfile(member).read())
    return FONT


# ----------------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------------
def quad(p0, p1, p2, t):
    a = (1 - t) ** 2
    b = 2 * (1 - t) * t
    c = t * t
    return a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]


def quad_tangent(p0, p1, p2, t):
    dx = 2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0])
    dy = 2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])
    n = math.hypot(dx, dy)
    return dx / n, dy / n


def pts(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def star(cx, cy, r, fill, opacity=1.0):
    k = r * 0.22
    d = (f"M{cx},{cy - r} Q{cx + k},{cy - k} {cx + r},{cy} Q{cx + k},{cy + k} {cx},{cy + r} "
         f"Q{cx - k},{cy + k} {cx - r},{cy} Q{cx - k},{cy - k} {cx},{cy - r}Z")
    return f'<path d="{d}" fill="{fill}" opacity="{opacity}"/>'


# ----------------------------------------------------------------------------
# popcorn
# ----------------------------------------------------------------------------
def kernel(x, y, s, rnd):
    """One puffy kernel: a cluster of lobes, each with its own highlight, outlined as one shape."""
    lobes = [(x, y, s * 0.52)]
    n = rnd.choice([4, 5, 5, 6])
    a0 = rnd.uniform(0, math.tau)
    for i in range(n):
        a = a0 + i * math.tau / n + rnd.uniform(-0.35, 0.35)
        dist = s * rnd.uniform(0.38, 0.5)
        lobes.append((x + dist * math.cos(a), y + dist * math.sin(a) * 0.9, s * rnd.uniform(0.3, 0.42)))
    lobes.sort(key=lambda c: c[1])                      # lower lobes drawn last (in front)
    outline = "".join(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r + 6:.1f}"/>' for cx, cy, r in lobes)
    fill = "".join(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="url(#pop)"/>' for cx, cy, r in lobes)
    shine = ""
    for cx, cy, r in lobes[:2]:
        shine += (f'<ellipse cx="{cx - r * 0.32:.1f}" cy="{cy - r * 0.38:.1f}" rx="{r * 0.26:.1f}" '
                  f'ry="{r * 0.16:.1f}" fill="#fffbe6" opacity="0.85" '
                  f'transform="rotate(-30 {cx - r * 0.32:.1f} {cy - r * 0.38:.1f})"/>')
    return f'<g><g fill="{INK}">{outline}</g>{fill}{shine}</g>'


def popcorn_heap(rnd):
    rows = [  # y, half width, count, size
        (238, 52, 2, 64),
        (268, 100, 4, 66),
        (306, 140, 5, 68),
        (345, 165, 6, 66),
        (384, 170, 6, 62),
    ]
    out = []
    for y, hw, n, s in rows:
        for i in range(n):
            x = 500 - hw + (2 * hw) * (i / (n - 1) if n > 1 else 0.5)
            out.append(kernel(x + rnd.uniform(-9, 9), y + rnd.uniform(-8, 8), s * rnd.uniform(0.9, 1.08), rnd))
    return "".join(out)


def flying(rnd):
    spots = [(222, 330, 58, -25), (205, 418, 50, 20), (276, 432, 44, 0),
             (778, 330, 58, 25), (795, 418, 50, -20), (724, 432, 44, 0)]
    out = []
    for x, y, s, rot in spots:
        out.append(f'<g transform="rotate({rot} {x} {y})">{kernel(x, y, s, rnd)}</g>')
    return "".join(out)


# ----------------------------------------------------------------------------
# bucket
# ----------------------------------------------------------------------------
def bucket():
    top_y, bot_y, top_hw, bot_hw = 400, 650, 150, 112
    sag = 16                                            # the top edge bows down (it is round)
    edge = [(500 + top_hw * (i / 20 * 2 - 1), top_y + sag * (1 - (i / 20 * 2 - 1) ** 2)) for i in range(21)]
    body = edge + [(500 + bot_hw, bot_y), (500 - bot_hw, bot_y)]
    stripes = []
    n = 7
    for i in range(n):
        a, b = i / n, (i + 1) / n
        xt0, xt1 = 500 - top_hw + 2 * top_hw * a, 500 - top_hw + 2 * top_hw * b
        xb0, xb1 = 500 - bot_hw + 2 * bot_hw * a, 500 - bot_hw + 2 * bot_hw * b
        col = "url(#red)" if i % 2 == 0 else "url(#cream)"
        stripes.append(f'<polygon points="{pts([(xt0, top_y - 40), (xt1, top_y - 40), (xb1, bot_y), (xb0, bot_y)])}" fill="{col}"/>')
    rim_top = [(500 + 162 * (i / 20 * 2 - 1), 372 + sag * (1 - (i / 20 * 2 - 1) ** 2)) for i in range(21)]
    rim_bot = [(500 + 156 * (i / 20 * 2 - 1), 408 + sag * (1 - (i / 20 * 2 - 1) ** 2)) for i in range(21)][::-1]
    return f"""
  <clipPath id="bucketClip"><polygon points="{pts(body)}"/></clipPath>
  <polygon points="{pts(body)}" fill="{INK}" stroke="{INK}" stroke-width="16" stroke-linejoin="round"/>
  <g clip-path="url(#bucketClip)">
    {''.join(stripes)}
    <rect x="300" y="350" width="400" height="320" fill="url(#cyl)"/>
  </g>
  <polygon points="{pts(rim_top + rim_bot)}" fill="url(#rim)" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>
  <polyline points="{pts([(x, y + 7) for x, y in rim_top[2:-2]])}" fill="none" stroke="#ffffff" stroke-width="4"
            stroke-linecap="round" opacity="0.45"/>"""


# ----------------------------------------------------------------------------
# ribbon + text
# ----------------------------------------------------------------------------
P0, P1, P2 = (160, 572), (500, 668), (840, 572)       # ribbon centre line (a smile)
HALF = 63                                             # half thickness


def ribbon():
    top, bot = [], []
    N = 64
    for i in range(N + 1):
        t = i / N
        x, y = quad(P0, P1, P2, t)
        tx, ty = quad_tangent(P0, P1, P2, t)
        nx, ny = -ty, tx                                 # points down-ish
        top.append((x - nx * HALF, y - ny * HALF))
        bot.append((x + nx * HALF, y + ny * HALF))
    band = top + bot[::-1]

    def end_piece(t, outward):
        x, y = quad(P0, P1, P2, t)
        tx, ty = quad_tangent(P0, P1, P2, t)
        ux, uy = (tx * outward, ty * outward)            # along the ribbon, pointing out of the band
        vx, vy = -ty, tx                                 # down

        def P(u, v):
            return x + ux * u + vx * v, y + uy * u + vy * v
        f, w, d, notch = 52, 104, 40, 36
        tail = [P(-f, -HALF + d), P(w, -HALF + d), P(w - notch, d), P(w, HALF + d), P(-f, HALF + d)]
        fold = [P(0, HALF), P(-f, HALF), P(-f, HALF + d)]
        return (f'<polygon points="{pts(tail)}" fill="url(#tail)" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>'
                f'<polygon points="{pts(fold)}" fill="#6a1431" stroke="{INK}" stroke-width="8" stroke-linejoin="round"/>')

    hl = [(x, y + 13) for x, y in top[3:-3]]
    shadow = [(x, y + 16) for x, y in band]
    return f"""
  <polygon points="{pts(shadow)}" fill="#0b1230" opacity="0.35" filter="url(#soft)"/>
  {end_piece(0.0, -1)}{end_piece(1.0, 1)}
  <polygon points="{pts(band)}" fill="url(#band)" stroke="{INK}" stroke-width="9" stroke-linejoin="round"/>
  <polyline points="{pts(hl)}" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.35"/>
  <polyline points="{pts([(x, y - 12) for x, y in bot[3:-3]])}" fill="none" stroke="#7d1534" stroke-width="5"
            stroke-linecap="round" opacity="0.5"/>"""


def text_path_d(offset):
    """The ribbon centre line moved down by `offset` (the text baseline)."""
    a = (P0[0], P0[1] + offset)
    b = (P1[0], P1[1] + offset)
    c = (P2[0], P2[1] + offset)
    return f"M{a[0]},{a[1]} Q{b[0]},{b[1]} {c[0]},{c[1]}"


def lettering(size):
    tp = f'<textPath href="#base" startOffset="50%" text-anchor="middle">{TEXT}</textPath>'
    style = f'font-family="Lucky" font-size="{size}" letter-spacing="3"'
    return f"""
  <path id="base" d="{text_path_d(size * 0.36)}" fill="none"/>
  <text {style} fill="{INK}" stroke="{INK}" stroke-width="20" stroke-linejoin="round" transform="translate(0 9)">{tp}</text>
  <text {style} fill="{INK}" stroke="{INK}" stroke-width="20" stroke-linejoin="round">{tp}</text>
  <text {style} fill="url(#letters)" stroke="#ffffff" stroke-width="1.5">{tp}</text>
  <g clip-path="url(#lowerHalf)"><text {style} fill="url(#lines)">{tp}</text></g>"""


def lower_half_clip(size):
    d = text_path_d(-size * 0.02)
    return f'<clipPath id="lowerHalf"><path d="{d} L860,800 L140,800 Z"/></clipPath>'


# ----------------------------------------------------------------------------
def build_svg():
    rnd = random.Random(7)
    size = 88
    font64 = base64.b64encode(open(get_font(), "rb").read()).decode()
    swoosh = "".join(
        f'<path d="M{620 + i * 26},1010 C{760 + i * 20},{820 - i * 10} {930 + i * 8},{700 - i * 12} 1010,{560 - i * 18}" '
        f'fill="none" stroke="#5fb7ff" stroke-width="3" opacity="{0.16 - i * 0.008:.3f}"/>' for i in range(14))
    swoosh += "".join(
        f'<path d="M-10,{430 - i * 22} C{60 + i * 6},{300 - i * 14} {170 + i * 14},{140 - i * 8} {360 + i * 24},-10" '
        f'fill="none" stroke="#5fb7ff" stroke-width="3" opacity="{0.12 - i * 0.007:.3f}"/>' for i in range(12))
    grid = "".join(f'<line x1="{x}" y1="0" x2="{x}" y2="1000"/>' for x in range(14, 1000, 44)) + \
        "".join(f'<line x1="0" y1="{y}" x2="1000" y2="{y}"/>' for y in range(14, 1000, 44))
    sparkles = "".join([
        star(318, 262, 22, "#ffffff", 0.95), star(694, 240, 16, "#fff3b0", 0.9), star(752, 512, 12, "#ffffff", 0.8),
        star(252, 560, 11, "#fff3b0", 0.75), star(540, 196, 11, "#ffffff", 0.85), star(350, 846, 12, "#ffffff", 0.55),
        star(664, 862, 9, "#fff3b0", 0.5), star(842, 330, 14, "#bdf6ff", 0.9), star(160, 330, 12, "#bdf6ff", 0.8),
    ])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="100%" height="100%">
<defs>
  <style>@font-face {{ font-family: Lucky; src: url(data:font/woff2;base64,{font64}) format("woff2"); }}</style>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0d4a96"/><stop offset="0.55" stop-color="#082d66"/><stop offset="1" stop-color="#051a42"/>
  </linearGradient>
  <radialGradient id="bgGlow" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#2f8bff" stop-opacity="0.55"/><stop offset="1" stop-color="#2f8bff" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="ring" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#5ff0ff"/><stop offset="0.5" stop-color="#19c6ec"/><stop offset="1" stop-color="#0a97cf"/>
  </linearGradient>
  <linearGradient id="disk" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#5a2690"/><stop offset="0.42" stop-color="#4a4fb3"/>
    <stop offset="0.75" stop-color="#2d93cf"/><stop offset="1" stop-color="#23d3df"/>
  </linearGradient>
  <radialGradient id="spot" cx="0.5" cy="0.36" r="0.5">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0.32"/><stop offset="0.6" stop-color="#ffffff" stop-opacity="0.05"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="vig" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0.72" stop-color="#140a3a" stop-opacity="0"/><stop offset="1" stop-color="#140a3a" stop-opacity="0.45"/>
  </radialGradient>
  <radialGradient id="pop" cx="0.36" cy="0.3" r="0.8">
    <stop offset="0" stop-color="#fff3bd"/><stop offset="0.32" stop-color="#ffd25e"/>
    <stop offset="0.74" stop-color="#f29a2c"/><stop offset="1" stop-color="#b65e18"/>
  </radialGradient>
  <linearGradient id="red" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#f04766"/><stop offset="1" stop-color="#c8264a"/>
  </linearGradient>
  <linearGradient id="cream" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fffaf0"/><stop offset="1" stop-color="#f6e2c4"/>
  </linearGradient>
  <linearGradient id="cyl" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0.12" stop-color="#2a0b25" stop-opacity="0.45"/><stop offset="0.38" stop-color="#ffffff" stop-opacity="0.18"/>
    <stop offset="0.5" stop-color="#ffffff" stop-opacity="0.05"/><stop offset="0.88" stop-color="#2a0b25" stop-opacity="0.5"/>
  </linearGradient>
  <linearGradient id="rim" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ff6b86"/><stop offset="1" stop-color="#c8264a"/>
  </linearGradient>
  <linearGradient id="band" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#f6506f"/><stop offset="1" stop-color="#c3234a"/>
  </linearGradient>
  <linearGradient id="tail" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#c22b50"/><stop offset="1" stop-color="#8f1a3b"/>
  </linearGradient>
  <linearGradient id="letters" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffffff"/><stop offset="0.55" stop-color="#fff6d8"/><stop offset="1" stop-color="#ffd76a"/>
  </linearGradient>
  <pattern id="lines" width="20" height="9" patternUnits="userSpaceOnUse">
    <rect width="20" height="3.2" y="5" fill="#e9a530"/>
  </pattern>
  <filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="8"/></filter>
  <filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14"/></filter>
  <clipPath id="diskClip"><circle cx="500" cy="500" r="404"/></clipPath>
  {lower_half_clip(size)}
</defs>

<rect width="1000" height="1000" fill="url(#bg)"/>
{swoosh}
<circle cx="500" cy="500" r="500" fill="url(#bgGlow)"/>

<circle cx="500" cy="514" r="470" fill="#020818" opacity="0.5" filter="url(#glow)"/>
<circle cx="500" cy="500" r="472" fill="url(#ring)"/>
<circle cx="500" cy="500" r="466" fill="none" stroke="#ffffff" stroke-width="4" opacity="0.35"/>
<circle cx="500" cy="500" r="410" fill="#0b6fa6"/>

<g clip-path="url(#diskClip)">
  <rect width="1000" height="1000" fill="url(#disk)"/>
  <g stroke="#ffffff" stroke-width="1.6" opacity="0.13">{grid}</g>
  <rect width="1000" height="1000" fill="url(#spot)"/>
  <rect width="1000" height="1000" fill="url(#vig)"/>
</g>
<circle cx="500" cy="500" r="404" fill="none" stroke="#0a5c8f" stroke-width="5" opacity="0.6"/>

{sparkles}
<g font-family="Lucky" fill="#ffffff" opacity="0.13" clip-path="url(#diskClip)">
  <text x="318" y="852" font-size="112" transform="rotate(-14 318 815)">?</text>
  <text x="482" y="884" font-size="88" transform="rotate(6 505 850)">?</text>
  <text x="640" y="850" font-size="114" transform="rotate(16 668 812)">?</text>
</g>
<g transform="translate(0 38)">
  <ellipse cx="500" cy="330" rx="230" ry="150" fill="#ffd36b" opacity="0.22" filter="url(#glow)"/>
  {bucket()}
  {popcorn_heap(rnd)}
  {flying(rnd)}
  {ribbon()}
  {lettering(size)}
</g>
</svg>"""


RENDER_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const [html, out, size] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1024, height: 1024 }, deviceScaleFactor: size / 1024 });
  await page.goto('file://' + html);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  await page.screenshot({ path: out });
  await browser.close();
})();
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "funny_quizz_logo.png"))
    ap.add_argument("--size", type=int, default=2048)
    a = ap.parse_args()
    os.makedirs(CACHE, exist_ok=True)
    html = os.path.join(CACHE, "logo.html")
    with open(html, "w") as fh:
        fh.write('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:1024px;'
                 'height:1024px;overflow:hidden;background:#051a42}</style></head><body>' + build_svg() + '</body></html>')
    js = os.path.join(CACHE, "render.js")
    with open(js, "w") as fh:
        fh.write(RENDER_JS)
    subprocess.run(["node", js, html, os.path.abspath(a.out), str(a.size)], check=True)
    print(a.out)


if __name__ == "__main__":
    main()
