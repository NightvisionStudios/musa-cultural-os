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

# Filename tells you nobody named this file after what is in it: a Canva export,
# a phone screenshot, a CMS auto-name. These are usually a publication's generic
# article graphic rather than a picture of the subject. Issue 62 shipped
# "Copy-of-Untitled-1200-x-800-px-7-600x403.png" as the Slawn card — Pause Mag's
# og:image is a template, and a size check cannot tell that from a photograph.
# Not fatal on its own: allowed through only when the page ties it to the entry.
GENERIC = re.compile(r"("
                     r"copy[-_ ]of[-_ ]untitled|untitled[-_ ]?design|^untitled|"
                     r"screen[-_ ]?shot|screenshot|unnamed|"
                     r"^(image|img|photo|pic|file|download|upload)[-_ ]?\d*$|"
                     r"^\d{2,4}x\d{2,4}$|^(final|new|temp|draft)\d*$|"
                     r"web[-_ ]?banner|featured[-_ ]?image|hero[-_ ]?image"
                     r")", re.I)

STOP = {"the", "and", "for", "with", "from", "that", "this", "vol", "feat",
        "presents", "records", "gallery", "museum", "foundation", "studio",
        "collective", "project", "issue", "part", "his", "her", "their"}


def tokens(name):
    """Distinctive words from an entry name, for tying an image to its subject."""
    name = re.sub(r"[—–\-|:/,'\u2019]", " ", (name or "").lower())
    out = set()
    for w in re.findall(r"[a-z0-9]{3,}", name):
        if w in STOP or w.isdigit():
            continue
        out.add(w)
    return out


def relevant(url, toks, alts):
    """Does anything tie this image to the entry? URL path, or its alt text."""
    path = urlparse(url).path.lower() + " " + (urlparse(url).query or "").lower()
    slug = re.sub(r"[^a-z0-9]+", " ", path)
    if any(t in slug for t in toks):
        return "url"
    alt = (alts.get(url) or "").lower()
    if alt and any(t in alt for t in toks):
        return "alt"
    return None

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
    """og:image first, then twitter, then the biggest-looking inline image.

    Returns (ordered_urls, alt_by_url) — alt text is how an anonymously named
    image proves it is actually about the entry.
    """
    seen, out, alts = set(), [], {}

    def add(u, alt=None):
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
        if alt:
            alts.setdefault(u, unescape(alt))
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

    # every inline <img>, for its alt text as much as for its src
    for m in re.finditer(r'<img[^>]+>', html[:250_000], re.I):
        tag = m.group(0)
        src = re.search(r'\ssrc=["\']([^"\']+)["\']', tag, re.I)
        alt = re.search(r'\salt=["\']([^"\']*)["\']', tag, re.I)
        if src and not JUNK.search(src.group(1)):
            add(src.group(1), alt.group(1) if alt else None)

    return [u for u in out if not JUNK.search(urlparse(u).path)], alts


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


def suspects(led):
    """Filled entries whose art looks like a template graphic rather than a picture."""
    out = []
    for iss in led.get("issues", []):
        for e in iss.get("entries", []):
            img = (e.get("image") or "").strip()
            if not img or img == MARK:
                continue
            base = re.sub(r"\.[a-z0-9]{2,5}$", "", os.path.basename(urlparse(img).path))
            if GENERIC.search(base) and not relevant(img, tokens(e.get("name")), {}):
                out.append({"issue": iss.get("issue"), "name": e.get("name"),
                            "slug": e.get("slug"), "url": e.get("url"), "image": img})
    return out


def audit(fix=False):
    """Flag already-filled entries the relevance gate would now refuse.

    Pure string work, no network, so it runs anywhere. With --fix the offenders
    go back to the mark and into the review queue, where a session can resolve
    them by hand — which is the only thing that reliably beats a template graphic.
    """
    led = json.load(open(LEDGER, encoding="utf-8"))
    bad = suspects(led)
    byslug = {}
    for iss in led.get("issues", []):
        for e in iss.get("entries", []):
            byslug[e.get("slug") or e.get("name")] = e

    for s_ in bad:
        print("  SUSPECT i%-3s %-40s %s" % (s_["issue"], (s_["name"] or "")[:40],
                                            os.path.basename(urlparse(s_["image"]).path)[:52]))
        if fix:
            byslug[s_["slug"] or s_["name"]]["image"] = MARK
    print("audit: %d filled entr%s look like template art"
          % (len(bad), "y" if len(bad) == 1 else "ies"))
    print("audit: report only by default — a phone-named file on a label's own page is\n"
          "       often the real artwork, so confirm before --fix reverts it to the mark")
    if fix and bad:
        json.dump(led, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("audit: reverted to the mark and queued for review")
    return 0


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

        cands, alts = candidates(html, final)
        toks = tokens(e.get("name"))
        own = urlparse(final).netloc

        # Score before validating: a tie to the entry is worth more than being
        # first in the meta block. An anonymously named file with nothing tying
        # it to the subject is refused outright — that is the Slawn failure, and
        # a wrong picture is worse than the mark, which at least reads as brand.
        ranked = []
        for pos, c in enumerate(cands):
            tie = relevant(c, toks, alts)
            base = re.sub(r"\.[a-z0-9]{2,5}$", "", os.path.basename(urlparse(c).path))
            generic = bool(GENERIC.search(base))
            selfhosted = urlparse(c).netloc.split(".")[-2:] == own.split(".")[-2:]
            if generic and not tie:
                continue
            score = (3 if tie == "url" else 2 if tie == "alt" else 0)
            score += 1 if selfhosted else 0
            score -= pos * 0.1
            ranked.append((-score, pos, c, tie))
        ranked.sort()

        picked = reason = None
        for _, _, cand, tie in ranked[:4]:
            picked, reason = usable(cand)
            if picked:
                reason = "%s tie:%s" % (reason, tie or "none")
                break

        if not picked and not ranked and cands:
            reason = "only generic art on page (%d rejected)" % len(cands)

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

    # Anything still on the mark that HAS a source is a job for a person, not a
    # heuristic: a session can look at a picture and say whether it is the right
    # one. Surfaced here so it can be worked at the top of a run.
    review = []
    for iss in led.get("issues", []):
        for e in iss.get("entries", []):
            if (e.get("image") or "") in ("", MARK) and (e.get("url") or "").strip():
                review.append({"issue": iss.get("issue"), "name": e.get("name"),
                               "slug": e.get("slug"), "url": e.get("url"),
                               "reason": state.get(e.get("slug") or e.get("name", ""), {})
                                              .get("reason", "not attempted yet")})

    json.dump({"note": "misses = auto-resolution failed and stops retrying after %d. "
                       "review = still on the mark but has a source. "
                       "suspects = filled, but the art looks like a template graphic. "
                       "Both want a human eye."
                       % MAX_ATTEMPTS,
               "updated": time.strftime("%Y-%m-%d"),
               "review": review, "suspects": suspects(led), "misses": state},
              open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    still = sum(1 for iss in led.get("issues", []) for e in iss.get("entries", [])
                if (e.get("image") or "") in ("", MARK))
    print("artfill: %d filled, %d missed, %d on the mark, %d queued for review"
          % (filled, failed, still, len(review)))
    return 0


if __name__ == "__main__":
    if "--audit" in sys.argv:
        sys.exit(audit(fix="--fix" in sys.argv))
    sys.exit(main())
