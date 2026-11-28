#!/usr/bin/env python3
"""Download free-licensed food photos from Wikimedia Commons for make_food_quiz.py.

Step 1 - download candidates (3 per food) into food_images/candidates/:
    python3 fetch_food_images.py
Step 2 - look at them and choose one per food (default: candidate 1):
    python3 fetch_food_images.py --pick pizza=2 sushi=3
This copies the chosen photos to food_images/<food>.jpg and writes
food_images/CREDITS.txt (author + licence), which you should paste into the
video description, as CC BY / CC BY-SA licences require.

Only photos under CC0, Public Domain, CC BY or CC BY-SA are accepted.
Needs network access to commons.wikimedia.org and upload.wikimedia.org.
"""

import argparse
import html
import json
import os
import re
import shutil
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(HERE, "food_images")
CAND_DIR = os.path.join(IMG_DIR, "candidates")
API = "https://commons.wikimedia.org/w/api.php"
UA = "QuizziesShortsGenerator/1.0 (educational quiz video generator)"

QUERIES = {
    "pizza": "pizza margherita",
    "banana": "banana fruit isolated",
    "hamburger": "hamburger cheeseburger",
    "sushi": "sushi nigiri plate",
    "croissant": "croissant",
    "avocado": "avocado halved",
    "dumplings": "jiaozi dumplings",
    "pretzel": "soft pretzel brezel",
    "dragon_fruit": "pitaya dragon fruit cut",
    "artichoke": "artichoke globe",
}
OK_LICENSES = re.compile(r"^(cc0|public domain|pd|cc by(-sa)? ?\d)", re.I)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def strip_html(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def search(query, limit=25):
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f"{query} filetype:bitmap", "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 1400,
    }
    data = json.loads(get(API + "?" + urllib.parse.urlencode(params)))
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = strip_html(meta.get("LicenseShortName", {}).get("value", ""))
        if ii.get("mime") not in ("image/jpeg", "image/png") or not OK_LICENSES.match(lic):
            continue
        if min(ii.get("width", 0), ii.get("height", 0)) < 900:
            continue
        out.append({
            "title": p["title"], "url": ii.get("thumburl") or ii["url"], "page": ii.get("descriptionurl"),
            "license": lic, "author": strip_html(meta.get("Artist", {}).get("value", "unknown")),
        })
    return out


def download():
    os.makedirs(CAND_DIR, exist_ok=True)
    index = {}
    for key, q in QUERIES.items():
        found = search(q)[:3]
        index[key] = found
        for n, c in enumerate(found, 1):
            path = os.path.join(CAND_DIR, f"{key}_{n}.jpg")
            with open(path, "wb") as f:
                f.write(get(c["url"]))
            print(f"{key}_{n}: {c['title']}  [{c['license']}, {c['author']}]")
        if not found:
            print(f"{key}: nothing suitable found, try another query")
    with open(os.path.join(CAND_DIR, "candidates.json"), "w") as f:
        json.dump(index, f, indent=1)


def pick(choices):
    with open(os.path.join(CAND_DIR, "candidates.json")) as f:
        index = json.load(f)
    lines = ["Food photos from Wikimedia Commons:"]
    for key in QUERIES:
        n = int(choices.get(key, 1))
        c = index[key][n - 1]
        shutil.copy(os.path.join(CAND_DIR, f"{key}_{n}.jpg"), os.path.join(IMG_DIR, f"{key}.jpg"))
        lines.append(f"- {key.replace('_', ' ').title()}: \"{c['title'].removeprefix('File:')}\" "
                     f"by {c['author']}, {c['license']}, {c['page']}")
    with open(os.path.join(IMG_DIR, "CREDITS.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pick", nargs="*", metavar="FOOD=N")
    a = ap.parse_args()
    if a.pick is not None:
        pick(dict(x.split("=") for x in a.pick))
    else:
        download()
