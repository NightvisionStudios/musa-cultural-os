# -*- coding: utf-8 -*-
"""MUSA share-card renderer. Typographic cards — no source photos, so every card
reads as a MUSA object in a feed rather than as somebody else's artwork."""
import os, re, io
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops
import cairosvg

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
SERIF = os.path.join(FONTS, "InstrumentSerif-Regular.ttf")
MONO  = os.path.join(FONTS, "IBMPlexMono-Regular.ttf")
MONOM = os.path.join(FONTS, "IBMPlexMono-Medium.ttf")

BG="#0a0a0a"; FG="#f2ead5"; MUT="#8c887e"; MUT2="#6d6a62"
LINE="#26241f"; AMBER="#e8c96d"; SAND="#cdbf99"; GREEN="#3fb56b"; RED="#e4533a"
TIER_COLOR={"HEIRWAVE":"#f2ead5","CROWN":"#e8c96d","FLAME":"#e89a5a",
            "TORCH":"#c9b27a","SPARK":"#3fb56b","NOISE":"#e4533a"}
TIER_BORDER={"HEIRWAVE":"#5a5446","CROWN":"#3a2f1c","FLAME":"#3a2a1c",
             "TORCH":"#312b1c","SPARK":"#1f3a28","NOISE":"#3a2020"}

_fc={}
def font(path,size):
    k=(path,size)
    if k not in _fc: _fc[k]=ImageFont.truetype(path,size)
    return _fc[k]

_word=None
def wordmark(height):
    """The real MUSA blackletter, rasterised from the same SVG the site serves —
    so a share card in a feed carries the actual logo, not a serif stand-in."""
    global _word
    if _word is None:
        _word = open(os.path.join(HERE, "..", "musa-wordmark.svg")).read()
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', _word)
    w = int(height * int(m.group(1)) / int(m.group(2)))
    png = cairosvg.svg2png(bytestring=_word.encode(), output_width=w*2, output_height=height*2)
    return Image.open(io.BytesIO(png)).convert("RGBA").resize((w, height), Image.LANCZOS)

_heir=None
def heirwave(height, color=FG):
    """Rasterise the canonical Heirwave mark at a given pixel height."""
    global _heir
    if _heir is None:
        src=open(os.path.join(HERE,"heirwave.svg")).read()
        _heir=re.findall(r'<path[^>]*d="([^"]+)"', src)
    svg=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="180 320 660 360">'
         + "".join('<path fill="%s" d="%s"/>'%(color,d) for d in _heir) + "</svg>")
    w=int(height*660/360)
    png=cairosvg.svg2png(bytestring=svg.encode(), output_width=w*2, output_height=height*2)
    im=Image.open(io.BytesIO(png)).convert("RGBA")
    return im.resize((w,height), Image.LANCZOS)

ART=os.path.join(HERE,"..","img","entries")

def art_for(entry):
    """Local cached artwork for an entry, or None. Never reaches the network —
    build/fetch_art.py fills img/entries/ from CI, where the network is open."""
    slug=entry.get("slug")
    if not slug: return None
    p_=os.path.join(ART, slug+".jpg")
    if not os.path.exists(p_): return None
    try: return Image.open(p_).convert("RGB")
    except Exception: return None

def cover(im,w,h,focus="center"):
    """Crop to fill exactly w x h, the way object-fit:cover does.

    `focus` sets the vertical anchor. The art band on a square card is ~2:1, so a
    portrait source centre-cropped loses both ends — on a photograph that means the
    head. "top" keeps the top of the frame, which is where faces and subjects sit."""
    sw,sh=im.size
    sc=max(w/float(sw), h/float(sh))
    nw,nh=max(w,int(sw*sc+.5)),max(h,int(sh*sc+.5))
    im=im.resize((nw,nh),Image.LANCZOS)
    x=(nw-w)//2
    if focus=="top":      y=0
    elif focus=="bottom": y=nh-h
    else:                 y=(nh-h)//2
    return im.crop((x,y,x+w,y+h))

def place_art(im,d,tile_src,x,y,w,h,radius,focus="center"):
    """Paste artwork with rounded corners and the house hairline border."""
    tile=cover(tile_src,w,h,focus)
    mask=Image.new("L",(w,h),0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,w-1,h-1],radius=radius,fill=255)
    im.paste(tile,(x,y),mask)
    d.rounded_rectangle([x,y,x+w-1,y+h-1],radius=radius,outline=LINE,width=2)

def tw(d,txt,f,ls=0):
    if not txt: return 0
    w=d.textlength(txt,font=f)
    return w + ls*(len(txt)-1)

def tracked(d,xy,txt,f,fill,ls=0):
    """Draw text with letter-spacing (Pillow has no native tracking)."""
    x,y=xy
    if ls==0:
        d.text((x,y),txt,font=f,fill=fill); return x+d.textlength(txt,font=f)
    for ch in txt:
        d.text((x,y),ch,font=f,fill=fill)
        x+=d.textlength(ch,font=f)+ls
    return x

def wrap(d,txt,f,maxw,maxlines,ls=0):
    words=str(txt).split(); lines=[]; cur=""
    for w_ in words:
        t=(cur+" "+w_).strip()
        if tw(d,t,f,ls)<=maxw: cur=t
        else:
            if cur: lines.append(cur)
            cur=w_
            if len(lines)==maxlines: break
    if cur and len(lines)<maxlines: lines.append(cur)
    if len(lines)==maxlines and len(" ".join(lines).split())<len(words):
        last=lines[-1]
        while tw(d,last+" …",f,ls)>maxw and " " in last: last=last.rsplit(" ",1)[0]
        lines[-1]=last+" …"
    return lines

def chip(d,x,y,label,color,border,fs=20,padx=13,pady=9,ls=1.6):
    f=font(MONOM,fs)
    w=tw(d,label,f,ls)+padx*2
    h=fs+pady*2
    d.rounded_rectangle([x,y,x+w,y+h],radius=5,outline=border,width=2)
    tracked(d,(x+padx,y+pady-int(fs*0.13)),label,f,color,ls)
    return x+w

def heatbar(d,x,y,heat,w=150,h=8):
    d.rounded_rectangle([x,y,x+w,y+h],radius=4,fill="#1c1a16")
    fw=int(w*max(0,min(100,heat))/100)
    if fw>4: d.rounded_rectangle([x,y,x+fw,y+h],radius=4,fill=AMBER)
    return x+w

def scanlines(im,alpha=5,step=3):
    ov=Image.new("RGBA",im.size,(0,0,0,0)); od=ImageDraw.Draw(ov)
    for y in range(0,im.size[1],step): od.line([(0,y),(im.size[0],y)],fill=(255,255,255,alpha))
    return Image.alpha_composite(im.convert("RGBA"),ov).convert("RGB")

DIRC={"up":GREEN,"down":RED,"flat":MUT}

def arrow(d,x,y,size,direction):
    """Draw the heat-direction glyph as a polygon — the mono face has no arrow glyphs."""
    c=DIRC.get(direction,MUT); h=size
    if direction=="up":     d.polygon([(x,y+h),(x+h,y+h),(x+h/2,y)],fill=c)
    elif direction=="down": d.polygon([(x,y),(x+h,y),(x+h/2,y+h)],fill=c)
    else:                   d.rectangle([x+h*0.22,y+h*0.1,x+h*0.78,y+h*0.9],fill=c)

# ── redesigned share cards (2026-07-31) ────────────────────────────────────
# Direction: art edge-to-edge, duotoned into the MUSA palette, hard gold rule,
# editorial block below. Anton replaces Instrument Serif as the display face —
# it is already the display font on og_50.py, and Instrument Serif had become the
# house style of AI-generated design, which is the one thing a MUSA card can't read as.

ANTON = os.path.join(FONTS, "Anton-Regular.ttf")
READ_FG = "#bdb6a6"          # was #a39e90 — too dim to survive a feed
CHROME  = "#9a9488"          # labels and footer, lifted from #6d6a62


def duotone(im, strength=0.55):
    """Push source art toward the house palette so a card reads as a MUSA object
    in a feed rather than as somebody else's artwork (Rule: cards are ours)."""
    if strength <= 0: return im.convert("RGB")
    g = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=1)
    tone = ImageOps.colorize(g, black="#0a0908", mid="#6b5a38", white="#f4ecd8")
    return Image.blend(im.convert("RGB"), tone, strength)


def scrim(im, start=0.66, power=2.4, top=0.24):
    """Vertical gradients top and bottom so the masthead and the gold rule always
    land on a dark floor, whatever the artwork is doing underneath."""
    w, h = im.size
    ramp = Image.new("L", (1, h)); px = ramp.load()
    for y in range(h):
        t = y / float(h - 1)
        px[0, y] = int(255 * min(1.0, ((t - start) / (1 - start)) ** power)) if t > start else 0
    mask = ramp.resize((w, h))
    if top:
        tr = Image.new("L", (1, h)); tp = tr.load()
        for y in range(h):
            t = y / float(h - 1)
            tp[0, y] = int(255 * (max(0.0, 1 - t / top) ** 1.6) * 0.85) if t < top else 0
        mask = ImageChops.lighter(mask, tr.resize((w, h)))
    return Image.composite(Image.new("RGB", (w, h), (6, 6, 5)), im, mask)


def grain(im, sigma=8, opacity=20):
    n = Image.effect_noise(im.size, sigma).convert("L")
    return Image.blend(im, ImageChops.overlay(im, Image.merge("RGB", (n, n, n))), opacity / 100.0)


_mark = None
def art_panel(entry, w, h):
    """Artwork cropped to fill, or the MUSA mark contained on black. Rule 8: the
    image field is never empty, and the mark is never stretched."""
    global _mark
    src = art_for(entry)
    if src is not None:
        sw, sh = src.size
        foc = entry.get("art_focus")
        if foc not in ("top", "center", "bottom"):
            foc = "top" if sh / float(sw) >= 1.2 else "center"
        return duotone(cover(src, w, h, foc), 0.55), False
    if _mark is None:
        m = Image.open(os.path.join(HERE, "..", "img", "musa-mark.png")).convert("RGBA")
        _mark = m
    tile = Image.new("RGB", (w, h), BG)
    s = min(w * 0.40 / _mark.size[0], h * 0.40 / _mark.size[1])
    m = _mark.resize((max(1, int(_mark.size[0] * s)), max(1, int(_mark.size[1] * s))), Image.LANCZOS)
    tile.paste(m, ((w - m.size[0]) // 2, (h - m.size[1]) // 2), m)
    return tile, True


def short_bench(b):
    """RETIRED 2026-07-31 — no longer called; benchmarks are off the cards entirely.
    Kept only so an older caller fails loudly rather than silently. See _footer.

    Just the canon name. The full benchmark sentence never fit, and on every
    card it ran straight through the site URL — overlapping glyphs, shipped 431 times."""
    b = str(b or "").strip()
    for s in (" — ", " – ", " - ", ", ", " · "):
        if s in b:
            b = b.split(s)[0]; break
    return b.strip().rstrip(".")


def _masthead(im, d, W, M, y, issue, hh=40, wmh=32, fs=17):
    mark = heirwave(hh); im.paste(mark, (M, y), mark)
    wm = wordmark(wmh); im.paste(wm, (M + mark.size[0] + int(hh * 0.4), y + int(hh * 0.13)), wm)
    fm = font(MONO, fs)
    r = "ISSUE %s" % issue.get("issue", "")
    tracked(d, (W - M - tw(d, r, fm, 2.4), y + int(hh * 0.3)), r, fm, CHROME, 2.4)


def _fit(d, name, read, boxw, top, floor, sizes, read_sizes=(3, 2), name_lines=3,
         read_px=26, lhf=0.95):
    """Step the headline down until the editorial block clears the rail. 431 cards
    with titles from 6 to 90 characters — the layout has to fit itself or it breaks."""
    for size in sizes:
        fn = font(ANTON, size); lh = int(size * lhf)
        nl = wrap(d, name.upper(), fn, boxw, name_lines)
        for rmax in read_sizes:
            fr = font(MONO, read_px); rlh = int(read_px * 1.6)
            rl = wrap(d, read, fr, boxw, rmax)
            if top + int(size * 0.42) + len(nl) * lh + 24 + len(rl) * rlh <= floor:
                return fn, nl, lh, fr, rl, rlh, size
    fn = font(ANTON, sizes[-1]); lh = int(sizes[-1] * lhf)
    fr = font(MONO, read_px)
    return (fn, wrap(d, name.upper(), fn, boxw, name_lines), lh,
            fr, wrap(d, read, fr, boxw, 1), int(read_px * 1.6), sizes[-1])


def _score_rail(d, entry, x, y, boxw, score_px=96, chip_fs=21, heat=True, bw=160):
    sc = "%.1f" % float(entry.get("score", 0))
    fsc = font(ANTON, score_px)
    d.text((x, y - int(score_px * 0.20)), sc, font=fsc, fill=AMBER)
    cx = x + d.textlength(sc, font=fsc) + int(score_px * 0.19)
    fl = font(MONO, 18)
    tracked(d, (cx, y + int(score_px * 0.46)), "SCORE", fl, CHROME, 2.6)
    c2 = cx + tw(d, "SCORE", fl, 2.6) + 22
    t = str(entry.get("tier", "")).upper()
    if t: c2 = chip(d, c2, y + 16, t, TIER_COLOR.get(t, FG), TIER_BORDER.get(t, LINE), fs=chip_fs) + 12
    for f_ in [z for z in (entry.get("flags") or []) if "BLADE" not in str(z).upper()]:
        lbl = str(f_).replace("_", " ").upper()
        col = GREEN if "FIND" in lbl else AMBER
        bor = "#2f3a28" if "FIND" in lbl else "#3a2f1c"
        c2 = chip(d, c2, y + 16, lbl, col, bor, fs=chip_fs) + 12
    if heat:
        h = int(entry.get("heat", 0) or 0)
        fh = font(MONO, 19); ht = "HEAT %d" % h; asz = 17
        hx = x + boxw - bw - 18 - asz
        tracked(d, (hx - tw(d, ht, fh, 2.4) - 14, y + 20), ht, fh, CHROME, 2.4)
        heatbar(d, hx, y + 26, h, w=bw, h=10)
        arrow(d, hx + bw + 18, y + 23, asz, entry.get("direction", "flat"))


def _footer(d, entry, x, y, boxw, fs=20):
    """Site URL only, right-aligned.

    BENCHMARK IS RETIRED FROM CARDS (2026-07-31). A card travels alone — into a
    feed, a group chat, somebody's DMs — with none of the framing the archive
    gives it. Stripped to a canon surname it read as a flat comparison rather
    than a placement, which is a good way to confuse a reader and insult a
    subject. The benchmark still runs on the permalink and in the Card Room,
    where THE KEY and the linked 50 are right there to carry it. Do not add it
    back to the image."""
    ff = font(MONO, fs)
    site = "ARCHIVE.THEMUSAFAMILY.COM"
    sw = tw(d, site, ff, 2.8)
    tracked(d, (x + boxw - sw, y), site, ff, CHROME, 2.8)


def sq(entry, issue, out, W=1080, H=1350):
    """Instagram card — art on top, gold rule, editorial below."""
    M, AH = 68, 700
    im = Image.new("RGB", (W, H), BG)
    panel, is_mark = art_panel(entry, W, AH)
    im.paste(scrim(panel, 0.66, 2.4, 0.24) if not is_mark else panel, (0, 0))
    d = ImageDraw.Draw(im)
    d.line([(0, AH), (W, AH)], fill=AMBER, width=3)
    _masthead(im, d, W, M, M, issue)

    rail = H - M - 158
    top = AH + 52
    boxw = W - 2 * M
    fk = font(MONOM, 21)
    tracked(d, (M, top), str(entry.get("domain_detail") or entry.get("domain", "")).upper(),
            fk, AMBER, 4.6)
    fn, nl, lh, fr, rl, rlh, _ = _fit(d, str(entry.get("name", "")), str(entry.get("read", "")),
                                      boxw, top, rail - 26, (108, 98, 90, 82, 74, 66, 60))
    y = top + 42
    for ln in nl:
        d.text((M, y), ln, font=fn, fill=FG); y += lh
    y += 24
    for ln in rl:
        d.text((M, y), ln, font=fr, fill=READ_FG); y += rlh

    d.line([(M, rail), (W - M, rail)], fill="#33302a", width=1)
    _score_rail(d, entry, M, rail + 26, boxw)
    _footer(d, entry, M, H - M - 4, boxw)
    return _save(grain(scanlines(im, 6)), out)


def og(entry, issue, out, W=1200, H=630):
    """Link-unfurl card — same language, rotated: art left, gold rule, editorial right."""
    M, AW = 52, 470
    im = Image.new("RGB", (W, H), BG)
    panel, is_mark = art_panel(entry, AW, H)
    if not is_mark:
        panel = scrim(panel, 0.72, 2.2, 0.0)
    im.paste(panel, (0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([AW, 0, AW + 2, H], fill=AMBER)

    x = AW + 3 + 46
    boxw = W - M - x
    mark = heirwave(32); im.paste(mark, (x, M), mark)
    wm = wordmark(26); im.paste(wm, (x + mark.size[0] + 13, M + 4), wm)
    fm = font(MONO, 16)
    r = "ISSUE %s" % issue.get("issue", "")
    tracked(d, (x + boxw - tw(d, r, fm, 2.4), M + 10), r, fm, CHROME, 2.4)

    rail = H - M - 120
    top = M + 32 + 34
    fk = font(MONOM, 18)
    tracked(d, (x, top), str(entry.get("domain_detail") or entry.get("domain", "")).upper(),
            fk, AMBER, 4.2)
    fn, nl, lh, fr, rl, rlh, _ = _fit(d, str(entry.get("name", "")), str(entry.get("read", "")),
                                      boxw, top, rail - 20, (76, 68, 60, 54, 48, 42),
                                      read_sizes=(2, 1), read_px=20)
    y = top + 36
    for ln in nl:
        d.text((x, y), ln, font=fn, fill=FG); y += lh
    y += 18
    for ln in rl:
        d.text((x, y), ln, font=fr, fill=READ_FG); y += rlh

    d.line([(x, rail), (x + boxw, rail)], fill="#33302a", width=1)
    _score_rail(d, entry, x, rail + 20, boxw, score_px=68, chip_fs=18, heat=False)
    _footer(d, entry, x, H - M - 2, boxw, fs=16)
    return _save(grain(scanlines(im, 6)), out)


def _save(im, out):
    im.save(out, "JPEG", quality=88, optimize=True, progressive=True)
    return out


# ── THE KEY card ────────────────────────────────────────────────────────────
# A permanent explainer card, pinned to the top of /share/. Built to be saved
# and posted as slide two behind any entry card, so it has to teach the whole
# premise cold: the gap between SCORE and HEAT is the read, and a high score
# sitting on low heat is the point of the whole board.

KEY_FLAGS = [
    ("FIND",         GREEN, "#2f3a28", "the score is ahead of the room."),
    ("ROOM'S RIGHT", AMBER, "#3a2f1c", "the room is loud, and the room is correct."),
    ("ROOM'S EARLY", AMBER, "#3a2f1c", "the room got here before the work did."),
]


def _key_masthead(im, d, W, M, y, right="THE KEY", hh=40, wmh=32, fs=17):
    mark = heirwave(hh); im.paste(mark, (M, y), mark)
    wm = wordmark(wmh); im.paste(wm, (M + mark.size[0] + int(hh * 0.4), y + int(hh * 0.13)), wm)
    fm = font(MONO, fs)
    tracked(d, (W - M - tw(d, right, fm, 2.4), y + int(hh * 0.3)), right, fm, AMBER, 2.4)


def _gapdemo(d, x, y, boxw):
    """The premise, drawn rather than argued: a tall score over a short heat bar."""
    fl = font(MONOM, 22); fv = font(MONOM, 26)
    barx, barw = x + 132, boxw - 132 - 96
    for i, (lab, val, pct, col) in enumerate(
            [("SCORE", "8.4", 84, AMBER), ("HEAT", "22", 22, MUT)]):
        yy = y + i * 62
        tracked(d, (x, yy + 3), lab, fl, MUT if i else FG, 3.0)
        d.rounded_rectangle([barx, yy + 4, barx + barw, yy + 20], radius=8, fill="#1c1a16")
        fw = int(barw * pct / 100)
        d.rounded_rectangle([barx, yy + 4, barx + fw, yy + 20], radius=8,
                            fill=AMBER if i == 0 else "#4a463d")
        tracked(d, (barx + barw + 22, yy), val, fv, col, 1.4)
    return y + 124


def keycard(out, W=1080, H=1350):
    M = 68
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    boxw = W - 2 * M

    _key_masthead(im, d, W, M, M)
    d.line([(M, M + 74), (W - M, M + 74)], fill=AMBER, width=3)

    y = M + 118
    tracked(d, (M, y), "HOW TO READ THE INDEX", font(MONOM, 21), MUT, 4.6)

    # Hero. Anton, tight leading, the payoff line in green.
    y += 58
    fh = font(ANTON, 140)
    for line, col in [("HIGH SCORE.", FG), ("LOW HEAT.", FG), ("THAT'S A FIND.", GREEN)]:
        d.text((M, y), line, font=fh, fill=col)
        y += 132

    y += 46
    fb = font(MONO, 27)
    body = ("The work already holds up. The room hasn't arrived yet. "
            "You get put onto it before it gets loud, which is the entire point of the board.")
    for ln in wrap(d, body, fb, boxw, 4):
        d.text((M, y), ln, font=fb, fill=SAND); y += 40

    # Draw the gap so it reads without the paragraph.
    y += 34
    d.rounded_rectangle([M, y, W - M, y + 196], radius=10, outline=LINE, width=2)
    yy = _gapdemo(d, M + 34, y + 34, boxw - 68)
    tracked(d, (M + 34, yy + 6), "THE GAP IS THE READ", font(MONOM, 19), AMBER, 4.0)
    y += 196 + 44

    # The other two calls, so a stranger can read any card in the feed.
    fg_ = font(MONO, 22)
    for lab, col, bor, gloss in KEY_FLAGS:
        endx = chip(d, M, y, lab, col, bor, fs=19, padx=11, pady=8, ls=1.6)
        d.text((endx + 18, y + 8), gloss, font=fg_, fill=MUT)
        y += 56

    ff = font(MONO, 20)
    tracked(d, (M, H - M - 14), "ARCHIVE.THEMUSAFAMILY.COM", ff, MUT2, 3.4)
    return _save(grain(scanlines(im, 6)), out)


def keycard_og(out, W=1200, H=630):
    """Landscape twin of the key card, for X / iMessage unfurl."""
    M = 56
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    split = 620
    d.line([(split, 0), (split, H)], fill=AMBER, width=3)

    _key_masthead(im, d, split - 24, M, M, right="THE KEY", hh=34, wmh=27, fs=15)

    y = M + 96
    fh = font(ANTON, 92)
    for line, col in [("HIGH SCORE.", FG), ("LOW HEAT.", FG), ("THAT'S A FIND.", GREEN)]:
        d.text((M, y), line, font=fh, fill=col)
        y += 88

    fb = font(MONO, 21)
    y += 26
    for ln in wrap(d, "The room hasn't arrived yet. You hear it before it gets loud.",
                   fb, split - M - 40, 2):
        d.text((M, y), ln, font=fb, fill=SAND); y += 31

    tracked(d, (M, H - M - 6), "ARCHIVE.THEMUSAFAMILY.COM", font(MONO, 17), MUT2, 3.0)

    # Right column: the gap, then the three calls.
    rx = split + 46
    rw = W - rx - M
    tracked(d, (rx, M + 6), "HOW TO READ THE INDEX", font(MONOM, 17), MUT, 3.8)
    yy = _gapdemo(d, rx, M + 54, rw)
    tracked(d, (rx, yy + 2), "THE GAP IS THE READ", font(MONOM, 16), AMBER, 3.4)

    y = yy + 56
    fg_ = font(MONO, 17)
    for lab, col, bor, gloss in KEY_FLAGS:
        chip(d, rx, y, lab, col, bor, fs=15, padx=9, pady=6, ls=1.4)
        for ln in wrap(d, gloss, fg_, rw, 1):
            d.text((rx, y + 36), ln, font=fg_, fill=MUT)
        y += 74
    return _save(grain(scanlines(im, 6)), out)
