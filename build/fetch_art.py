# -*- coding: utf-8 -*-
"""Caches every entry's artwork into the repo at img/entries/<slug>.jpg.

The ledger stores remote image URLs across 80+ hosts — gallery sites, labels,
Bandcamp, one-off designer domains. Hot-linking those is fragile (they rot, and
the card renderer can't reach them from a sandboxed build), so this pulls each
one down once and keeps a local copy.

Runs in GitHub Actions, which has open network. Idempotent: an image already on
disk is never re-fetched, so a run after a new issue only touches the new five.
Failures are logged and skipped — a miss leaves the entry typographic, it never
breaks the build.
"""
import json, os, sys, io, time
from urllib.parse import urlparse
import urllib.request
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "img", "entries")
MAX_EDGE = 1600          # nothing on a card is rendered larger than this
QUALITY = 82
TIMEOUT = 25
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# entries whose image already points at our own fallback mark have no real art
SKIP_HOSTS = {"archive.themusafamily.com", "themusafamily.com"}


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "%s://%s/" % (urlparse(url).scheme, urlparse(url).netloc),
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def main():
    led = json.load(open(os.path.join(ROOT, "ledger.json"), encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)

    want = {}
    for iss in led.get("issues", []):
        for en in iss.get("entries", []):
            slug = en.get("slug")
            url = en.get("image") or ""
            if not slug or not url:
                continue
            if urlparse(url).netloc.lower() in SKIP_HOSTS:
                continue
            want.setdefault(slug, url)

    got = fail = skip = 0
    misses = []
    for slug, url in want.items():
        dest = os.path.join(OUT, slug + ".jpg")
        if os.path.exists(dest) and os.path.getsize(dest) > 1024:
            skip += 1
            continue
        try:
            raw = fetch(url)
            im = Image.open(io.BytesIO(raw))
            if im.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", im.size, (10, 10, 10))
                im = im.convert("RGBA")
                bg.paste(im, mask=im.split()[-1])
                im = bg
            else:
                im = im.convert("RGB")
            if max(im.size) > MAX_EDGE:
                im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
            if min(im.size) < 200:
                raise ValueError("too small: %sx%s" % im.size)
            im.save(dest, "JPEG", quality=QUALITY, optimize=True, progressive=True)
            got += 1
            print("  ok    %s  (%sx%s)" % (slug, *im.size))
        except Exception as ex:
            fail += 1
            misses.append("%s\t%s\t%s" % (slug, url, ex))
            print("  MISS  %s  — %s" % (slug, ex))
        time.sleep(0.3)     # be a decent guest on 80 different hosts

    if misses:
        open(os.path.join(OUT, "_misses.txt"), "w", encoding="utf-8").write(
            "# entries whose art could not be fetched — these stay typographic\n"
            + "\n".join(sorted(misses)) + "\n")

    print("\nart cache: %d new, %d already held, %d missed  (%d entries with art)"
          % (got, skip, fail, len(want)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
