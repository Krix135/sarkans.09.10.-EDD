"""Orthographic 3D globe renderer for the map quiz (Natural Earth 1:50m countries, public domain)."""

import json
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "map_data", "ne_50m_admin_0_countries.geojson")

# "Quizzies night" palette
OCEAN = (24, 56, 140)
LAND = (250, 232, 192)
BORDER = (186, 146, 102)
HILITE = (255, 64, 140)
HILITE_EDGE = (130, 0, 60)
HILITE_GLOW = (255, 120, 200)
ATMOSPHERE = (170, 120, 255)
SPACE_TOP, SPACE_BOT = (12, 5, 30), (44, 16, 86)


def unit(lon, lat):
    lon, lat = np.radians(lon), np.radians(lat)
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], -1)


class World:
    def __init__(self):
        d = json.load(open(DATA))
        rings, owner, codes = [], [], []
        for f in d["features"]:
            code = f["properties"].get("ADM0_A3")
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            ci = len(codes)
            codes.append(code)
            for poly in polys:
                ring = np.array(poly[0], np.float64)
                rings.append(ring)
                owner.append(ci)
        self.codes = codes
        self.owner = np.array(owner)
        self.lens = np.array([len(r) for r in rings])
        self.starts = np.concatenate([[0], np.cumsum(self.lens)[:-1]])
        allpts = np.concatenate(rings)
        self.P = unit(allpts[:, 0], allpts[:, 1])
        self.ring_lonlat = rings

    def country(self, code):
        """Centre (largest polygon), and indices of the country's rings."""
        ci = self.codes.index(code)
        idx = np.nonzero(self.owner == ci)[0]
        big = idx[np.argmax(self.lens[idx])]
        s, n = self.starts[big], self.lens[big]
        c = self.P[s:s + n].mean(0)
        c /= np.linalg.norm(c)
        near = [i for i in idx if np.dot(self.P[self.starts[i]:self.starts[i] + self.lens[i]].mean(0), c) > 0.93]
        return c, np.array(near), idx


def frame_axes(c):
    """east / up / view vectors for a camera looking at unit vector c."""
    lon = math.atan2(c[1], c[0])
    lat = math.asin(max(-1, min(1, c[2])))
    east = np.array([-math.sin(lon), math.cos(lon), 0.0])
    up = np.array([-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)])
    view = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])
    return east, up, view


def zoom_for(world, c, near, W, H, fx=0.38, fy=0.25):
    east, up, view = frame_axes(c)
    pts = np.concatenate([world.P[world.starts[i]:world.starts[i] + world.lens[i]] for i in near])
    sx, sy = np.abs(pts @ east).max(), np.abs(pts @ up).max()
    return float(np.clip(min(fx * W / max(sx, 1e-3), fy * H / max(sy, 1e-3)), 650, 12000))


def slerp(a, b, k):
    d = float(np.clip(np.dot(a, b), -1, 1))
    om = math.acos(d)
    if om < 1e-6:
        return a
    return (math.sin((1 - k) * om) * a + math.sin(k * om) * b) / math.sin(om)


def space_bg(W, H, seed=3):
    y = np.linspace(0, 1, H)[:, None, None]
    img = np.array(SPACE_TOP) * (1 - y) + np.array(SPACE_BOT) * y
    im = Image.fromarray(np.repeat(img, W, 1).astype(np.uint8), "RGB").convert("RGBA")
    d = ImageDraw.Draw(im)
    r = random.Random(seed)
    for _ in range(260):
        x, yy, s = r.randrange(W), r.randrange(H), r.choice((1, 1, 2, 2, 3))
        a = r.randrange(120, 255)
        d.ellipse((x - s, yy - s, x + s, yy + s), fill=(255, 255, 255, a))
    return im


def shade_template(n=1024):
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    r = np.hypot(xx - n / 2, yy - n / 2) / (n / 2)
    inside = r <= 1
    limb = np.clip((r - 0.55) / 0.45, 0, 1) ** 2 * 120
    hl = np.clip(1 - np.hypot(xx - n * 0.32, yy - n * 0.28) / (n * 0.55), 0, 1) ** 2 * 70
    a = np.zeros((n, n, 4), np.uint8)
    dark = np.where(inside, limb, 0)
    light = np.where(inside, hl, 0)
    # one RGBA image: white highlight blended over dark limb
    a[..., 0] = a[..., 1] = a[..., 2] = np.where(light > dark, 255, 0).astype(np.uint8)
    a[..., 3] = np.maximum(dark, light).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


class GlobeRenderer:
    def __init__(self, W, H, world=None, ss=1.5):
        self.W, self.H, self.ss = W, H, ss
        self.world = world or World()
        self.bg = space_bg(W, H)
        self.shade = shade_template()
        g = Image.new("RGBA", (512, 512))
        ImageDraw.Draw(g).ellipse((56, 56, 456, 456), fill=ATMOSPHERE + (255,))
        self.atmo = g.filter(ImageFilter.GaussianBlur(26))

    def render(self, c, R, center, hilite=None, hilite_a=0.0):
        W, H, ss = self.W, self.H, self.ss
        w = self.world
        east, up, view = frame_axes(c)
        cx, cy = center
        im = self.bg.copy()
        if R < 1600:  # atmosphere glow around the globe
            s = int(2 * R * 1.28)
            a = self.atmo.resize((s, s), Image.BILINEAR)
            x0, y0 = int(cx - s / 2), int(cy - s / 2)
            im.alpha_composite(a.crop((max(0, -x0), max(0, -y0), s, s)), (max(0, x0), max(0, y0)))
        # map layer (supersampled for smooth coastlines)
        SW, SH = int(W * ss), int(H * ss)
        layer = Image.new("RGBA", (SW, SH))
        d = ImageDraw.Draw(layer)
        scx, scy, sR = cx * ss, cy * ss, R * ss
        d.ellipse((scx - sR, scy - sR, scx + sR, scy + sR), fill=OCEAN + (255,))
        sx, sy, dep = w.P @ east, w.P @ up, w.P @ view
        hidden = dep < 0
        nrm = np.hypot(sx, sy)
        nrm[nrm == 0] = 1
        sx = np.where(hidden, sx / nrm, sx)
        sy = np.where(hidden, sy / nrm, sy)
        X, Y = scx + sR * sx, scy - sR * sy
        vis = np.maximum.reduceat(dep, w.starts) > 0
        minx, maxx = np.minimum.reduceat(X, w.starts), np.maximum.reduceat(X, w.starts)
        miny, maxy = np.minimum.reduceat(Y, w.starts), np.maximum.reduceat(Y, w.starts)
        onscreen = vis & (maxx > 0) & (minx < SW) & (maxy > 0) & (miny < SH) & ((maxx - minx) + (maxy - miny) > 1.5)
        lw = max(1, int(1.6 * ss))
        hl_set = set(hilite.tolist()) if hilite is not None else set()
        for i in np.nonzero(onscreen)[0]:
            s, n = w.starts[i], w.lens[i]
            pts = list(zip(X[s:s + n].tolist(), Y[s:s + n].tolist()))
            d.polygon(pts, fill=LAND + (255,))
            d.line(pts + [pts[0]], fill=BORDER + (255,), width=lw)
        if hl_set and hilite_a > 0:
            glow = Image.new("L", (SW // 4, SH // 4))
            gd = ImageDraw.Draw(glow)
            hl_layer = Image.new("RGBA", (SW, SH))
            hd = ImageDraw.Draw(hl_layer)
            for i in hl_set:
                if not onscreen[i]:
                    continue
                s, n = w.starts[i], w.lens[i]
                pts = list(zip(X[s:s + n].tolist(), Y[s:s + n].tolist()))
                gd.polygon([(x / 4, y / 4) for x, y in pts], fill=255)
                hd.polygon(pts, fill=HILITE + (255,))
                hd.line(pts + [pts[0]], fill=HILITE_EDGE + (255,), width=max(2, int(3 * ss)))
            glow = glow.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(5)).resize((SW, SH),
                                                                                                    Image.BILINEAR)
            gl = Image.new("RGBA", (SW, SH), HILITE_GLOW + (0,))
            gl.putalpha(glow.point(lambda v: int(v * 0.85 * hilite_a)))
            layer.alpha_composite(gl)
            if hilite_a < 1:
                hl_layer.putalpha(hl_layer.getchannel("A").point(lambda v: int(v * hilite_a)))
            layer.alpha_composite(hl_layer)
        layer = layer.resize((W, H), Image.LANCZOS) if ss != 1 else layer
        im.alpha_composite(layer)
        k = min(1.0, max(0.0, (1300 - R) / 500))  # sphere shading fades out as we zoom in
        if k > 0:
            s = int(2 * R)
            sh = self.shade.resize((s, s), Image.BILINEAR)
            if k < 1:
                sh.putalpha(sh.getchannel("A").point(lambda v: int(v * k)))
            x0, y0 = int(cx - R), int(cy - R)
            im.alpha_composite(sh.crop((max(0, -x0), max(0, -y0), s, s)), (max(0, x0), max(0, y0)))
        return im
