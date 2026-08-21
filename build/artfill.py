# -*- coding: utf-8 -*-
"""Resolves real artwork for ledger entries that are sitting on the MUSA mark.

Rule 8 says the mark is the floor, not the default — an entry only keeps it when
there is genuinely no usable image behind its source URL. Sessions are supposed
to work the ladder (fetch the source page, read its og:image, try a second page)
before falling back, but a session that is running long tends to skip it, and
71 of 315 archive entries ended up typographic for no better reason than that.

This is the sweep that catches them. It runs in GitHub Actions, where the
network is open, ahead of fetch_art.py:

    artfill.py   ledger MARK entry -> real image URL   (this file)
    fetch_art.py real image URL    -> img/entries/<slug>.jpg
    publish.py   local copy        -> permalink hero + share cards

Idempotent and cheap. An entry with real art is never touched. A URL that fails
is recorded in build/artfill.json with an attempt count and is retried at most
MAX_ATTEMPTS times ever, so a dead source costs one request and then nothing.
A miss is never fatal: the entry keeps the mark and the build carries on.
"""
import json, os, re, sys, time
import urllib.request, urllib.error
from urllib.parse import urlparse, urljoin
from html import unescape

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LEDGER = os.path.join(ROOT, "ledger.json")
STATE = os.path.join(ROOT, "build", "artfill.json")

MARK = "https://archive.themusafamily.com/img/musa-mark.png"
OURS = {"archive.themusafamily.com", "themusafamily.com", "50.themusafamily.com"}

MAX_ATTEMPTS = 3          # per entry, ever — a dead source stops costing requests
# Every entry this fills gains cached artwork, which changes its card digest and
# re-renders two share images. Filling the whole 70-entry backlog in one run would
# stage ~140 images and churn tens of megabytes into a single commit, which is the
# exact thing that slowed the deploy to minutes on 2026-08-01. So it drains a slice
# per push instead, newest issues first. MUSA_ARTFILL_ALL=1 lifts the cap.
MAX_PER_RUN = int(os.environ.get("MUSA_ARTFILL_MAX", "12"))
TIMEOUT = 20
PAGE_CAP = 400_000        # bytes of HTML to read; meta lives in the head
MIN_BYTES = 12_000        # smaller than this is a logo or a spacer
MIN_EDGE = 400            # smaller than this looks bad as a permalink hero
POLITE = 1.0              # seconds between requests to the same host

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# filename tells you it is chrome, not artwork
JUNK = re.compile(r"(logo|favicon|sprite|placeholder|default[-_.]|avatar|"
                  r"share[-_]?default|og[-_]?default|social[-_]?card|blank|"
                  r"spacer|1x1|pixel)", re.I)

# ordered by how much we trust them
META_PATTERNS = [
    r'<meta[^>]+property=["\']og:image:secure_url["\'][^>]+content=["\']([^"\']+)',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image:secure_url["\']',
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']',
    r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)',
]


def get(url, cap=None, accept="*/*"):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "%s://%s/" % (urlparse(url).scheme, urlparse(url).netloc),
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(cap) if cap else r.read(), dict(r.headers), r.geturl()


def candidates(html, base):
    """og:image first, then twitter, then the biggest-looking inline image."""
    seen, out = set(), []

    def add(u):
        if not u:
            return
        u = unescape(u.strip())
        if u.startswith("//"):
            u = "https:" + u
        u = urljoin(base, u)
        if not u.lower().startswith(("http://", "https://")):
            return
        if urlparse(u).netloc in OURS:
            return
        if u not in seen:
            seen.add(u)
            out.append(u)

    head = html[:120_000]
    for pat in META_PATTERNS:
        for m in re.finditer(pat, head, re.I):
            add(m.group(1))

    # JSON-LD "image": can be a string, an object with url, or a list
    for m in re.finditer(r'"image"\s*:\s*(\[[^\]]{0,2000}\]|\{[^}]{0,2000}\}|"[^"]{0,600}")', head):
        for u in re.findall(r'https?://[^"\'\\\s]+', m.group(1)):
            add(u)

    # last resort: inline <img> that isn't obviously chrome
    if not out:
        for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html[:250_000], re.I):
            u = m.group(1)
            if not JUNK.search(u):
                add(u)
            if len(out) >= 8:
                break

    return [u for u in out if not JUNK.search(urlparse(u).path)]


def usable(url):
    """Download far enough to prove it is a real image of a decent size."""
    try:
        data, hdrs, _ = get(url, accept="image/avif,image/webp,image/apng,image/*,*/*;q=0.8")
    except Exception as e:
        return None, "fetch:%s" % type(e).__name__

    ctype = (hdrs.get("Content-Type") or "").split(";")[0].strip().lower()
    if ctype and not ctype.startswith("image/"):
        return None, "not-image:%s" % ctype
    if len(data) < MIN_BYTES:
        return None, "tiny:%db" % len(data)

    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(data))
        w, h = im.size
    except Exception:
        # SVG and a few AVIF variants won't open in Pillow but still render fine
        if ctype in ("image/svg+xml", "image/avif"):
            return url, "ok:%s(unverified-dims)" % ctype
        return None, "undecodable"

    if min(w, h) < MIN_EDGE:
        return None, "small:%dx%d" % (w, h)
    return url, "ok:%dx%d" % (w, h)


def main():
    led = json.load(open(LEDGER, encoding="utf-8"))
    state = {}
    if os.path.exists(STATE):
        try:
            state = json.load(open(STATE, encoding="utf-8")).get("misses", {})
        except Exception:
            state = {}

    targets = []
    for iss in led.get("issues", []):
        for e in iss.get("entries", []):
            img = (e.get("image") or "").strip()
            if img and img != MARK:
                continue
            url = (e.get("url") or "").strip()
            key = e.get("slug") or e.get("name", "")
            if not url:
                state.setdefault(key, {})["reason"] = "no source url"
                state[key]["attempts"] = MAX_ATTEMPTS
                continue
            if state.get(key, {}).get("attempts", 0) >= MAX_ATTEMPTS:
                continue
            targets.append((iss.get("issue"), e, key, url))

    # newest first: a fresh issue's art matters more than issue 4's
    targets.sort(key=lambda t: -(t[0] or 0))
    backlog = len(targets)
    if not os.environ.get("MUSA_ARTFILL_ALL") and len(targets) > MAX_PER_RUN:
        targets = targets[:MAX_PER_RUN]

    print("artfill: %d entr%s on the mark and worth a try; attempting %d this run"
          % (backlog, "y" if backlog == 1 else "ies", len(targets)))

    filled = failed = 0
    last_host = {}
    for issue, e, key, url in targets:
        host = urlparse(url).netloc
        gap = POLITE - (time.time() - last_host.get(host, 0))
        if gap > 0:
            time.sleep(gap)
        last_host[host] = time.time()

        try:
            raw, hdrs, final = get(url, cap=PAGE_CAP, accept="text/html,*/*;q=0.8")
            html = raw.decode("utf-8", "replace")
        except Exception as ex:
            reason = "page:%s" % type(ex).__name__
            st = state.setdefault(key, {"attempts": 0})
            st["attempts"] = st.get("attempts", 0) + 1
            st["reason"] = reason
            print("  MISS  i%s  %-42s %s" % (issue, (e.get("name") or "")[:42], reason))
            failed += 1
            continue

        picked = reason = None
        for cand in candidates(html, final)[:4]:
            picked, reason = usable(cand)
            if picked:
                break

        if picked:
            e["image"] = picked
            state.pop(key, None)
            filled += 1
            print("  FILL  i%s  %-42s %s" % (issue, (e.get("name") or "")[:42], reason))
        else:
            st = state.setdefault(key, {"attempts": 0})
            st["attempts"] = st.get("attempts", 0) + 1
            st["reason"] = reason or "no candidate on page"
            failed += 1
            print("  MISS  i%s  %-42s %s" % (issue, (e.get("name") or "")[:42], st["reason"]))

    if filled:
        json.dump(led, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    json.dump({"note": "entries artfill could not resolve; retried at most %d times ever" % MAX_ATTEMPTS,
               "updated": time.strftime("%Y-%m-%d"), "misses": state},
              open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    still = sum(1 for iss in led.get("issues", []) for e in iss.get("entries", [])
                if (e.get("image") or "") in ("", MARK))
    print("artfill: %d filled, %d missed, %d entries still on the mark" % (filled, failed, still))
    return 0


if __name__ == "__main__":
    sys.exit(main())
