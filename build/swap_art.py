# -*- coding: utf-8 -*-
"""Swap your own image into an entry, for when a pull couldn't find usable art.

    python3 build/swap_art.py <image-file> <entry>

<entry> can be a slug, a fragment of the name, or issue/rank:

    python3 build/swap_art.py ~/kabeh.jpg janett-kabeh
    python3 build/swap_art.py ~/kabeh.jpg kabeh
    python3 build/swap_art.py ~/kabeh.jpg 41/3

Two surfaces read art and they read it from different places, which is why this
is a script rather than a drag-and-drop:

  * the square share card (build/cards.py -> art_for) reads img/entries/<slug>.jpg
  * the homepage cover and the permalink hero read the entry's `image` URL

So this does three things: writes the normalised file to img/entries/<slug>.jpg,
repoints `image` at that file on our own domain (the repo IS the site, so it is a
real public URL once pushed), and deletes the stale square card so it re-renders.

build/fetch_art.py never touches it afterwards: it skips any image already on
disk, and it skips our own domain via SKIP_HOSTS. A manual swap is permanent.

Then, as with any pull: python3 build/publish.py && commit && push.
"""
import json, os, re, sys, shutil
from PIL import Image, ImageOps

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ART = os.path.join(ROOT, "img", "entries")
CARDS = os.path.join(ROOT, "cards")
LEDGER = os.path.join(ROOT, "ledger.json")
PUBLIC = "https://archive.themusafamily.com/img/entries/%s.jpg"
MAX_EDGE = 1600          # matches build/fetch_art.py so swapped art looks native
QUALITY = 82
MIN_EDGE = 400           # below this it renders soft on a 1080x1350 card


def die(msg, code=1):
    print("swap_art: " + msg, file=sys.stderr)
    sys.exit(code)


def load():
    with open(LEDGER, encoding="utf-8") as fh:
        return json.load(fh)


def all_entries(led):
    out = []
    for iss in led.get("issues", []):
        for en in iss.get("entries", []):
            out.append((iss, en))
    return out


def resolve(led, q):
    """Slug, name fragment, or issue/rank. Refuses to guess when ambiguous."""
    ents = all_entries(led)

    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", q.strip())
    if m:
        iss_no, rank = int(m.group(1)), int(m.group(2))
        hits = [(i, e) for i, e in ents
                if int(i.get("issue", -1)) == iss_no and int(e.get("rank", -1)) == rank]
        if not hits:
            die("no entry at issue %d rank %d" % (iss_no, rank))
        return hits[0]

    exact = [(i, e) for i, e in ents if (e.get("slug") or "") == q]
    if len(exact) == 1:
        return exact[0]

    ql = q.lower()
    loose = [(i, e) for i, e in ents
             if ql in (e.get("slug") or "").lower() or ql in (e.get("name") or "").lower()]
    if not loose:
        die("nothing matches %r. Pass a slug, a name fragment, or issue/rank." % q)
    if len(loose) > 1:
        print("swap_art: %r matches %d entries:" % (q, len(loose)), file=sys.stderr)
        for i, e in loose[:12]:
            print("   issue %-3s rank %s  %-42s  %s"
                  % (i.get("issue"), e.get("rank"), (e.get("name") or "")[:42], e.get("slug")),
                  file=sys.stderr)
        die("be more specific.")
    return loose[0]


def normalise(src, dest):
    try:
        im = Image.open(src)
    except Exception as exc:
        die("cannot read %s (%s)" % (src, exc))
    im = ImageOps.exif_transpose(im)          # honor phone rotation, then drop EXIF
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    elif im.mode == "L":
        im = im.convert("RGB")
    w, h = im.size
    if min(w, h) < MIN_EDGE:
        print("swap_art: WARNING %dx%d is small; it will look soft on the square card." % (w, h))
    if max(w, h) > MAX_EDGE:
        im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    clean = Image.new("RGB", im.size)         # new canvas = no metadata carried over
    clean.paste(im)
    clean.save(dest, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return clean.size


def main():
    args = [a for a in sys.argv[1:] if a != "--"]
    if len(args) != 2:
        print(__doc__)
        die("need exactly two arguments: <image-file> <entry>")

    # tolerate either order — whichever one is a file on disk is the image
    a, b = args
    if os.path.isfile(a) and not os.path.isfile(b):
        img, query = a, b
    elif os.path.isfile(b) and not os.path.isfile(a):
        img, query = b, a
    else:
        die("could not tell which argument is the image file. %r and %r" % (a, b))

    led = load()
    iss, en = resolve(led, query)
    slug = en.get("slug")
    if not slug:
        die("that entry has no slug yet. Run build/publish.py once, then retry.")

    dest = os.path.join(ART, slug + ".jpg")
    had = os.path.exists(dest)
    size = normalise(img, dest)

    old = en.get("image") or ""
    en["image"] = PUBLIC % slug
    with open(LEDGER, "w", encoding="utf-8") as fh:
        json.dump(led, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    sq = os.path.join(CARDS, slug + "-sq.jpg")
    if os.path.exists(sq):
        os.remove(sq)

    print("swapped art for issue %s rank %s — %s" % (iss.get("issue"), en.get("rank"), en.get("name")))
    print("  file    img/entries/%s.jpg  (%dx%d%s)" % (slug, size[0], size[1], ", replaced" if had else ""))
    print("  image   %s" % en["image"])
    print("  was     %s" % (old or "(empty)"))
    print("  card    cards/%s-sq.jpg deleted, will re-render" % slug)
    print("")
    print("next:  python3 build/publish.py")
    print("       git add -A && git commit -m 'art: %s' && git push" % slug)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass          # piped into head/less; the work already completed
