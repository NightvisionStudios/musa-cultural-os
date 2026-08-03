#!/usr/bin/env python3
"""
Renders the MUSA 50 share card -> the-50/og-image.png (1200x630).

The 50's own display face is Anton (the page runs Anton / Fraunces / Plex Mono),
so this card follows the PAGE rather than the archive's Instrument Serif entry
cards. Palette, Heirwave, letter-tracking and grain all come from cards.py, so
the object still reads as a MUSA card in a feed.

Typographic only — never a source photo. Every position is derived from a
measured glyph box, not a guessed baseline, because Anton carries a deep blank
ascender that makes eyeballed layouts collide.

Run: python build/og_50.py
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cards as C

ANTON = os.path.join(C.FONTS, "Anton-Regular.ttf")
OUT   = os.path.abspath(os.path.join(HERE, "..", "the-50", "og-image.png"))

W, H  = 1200, 630
M     = 64
TITLE = "MUSA 50"
SUB   = "50 people, places, and things worth your attention."


def build():
    im = Image.new("RGB", (W, H), C.BG)
    d  = ImageDraw.Draw(im)

    # Heirwave, top left — same mark and height as the entry cards
    mark = C.heirwave(40)
    im.paste(mark, (M, M), mark)

    # masthead kicker, top right, optically level with the mark
    kick = C.font(C.MONOM, 17)
    kw   = C.tw(d, "THE MUSA FAMILY", kick, 2.6)
    C.tracked(d, (W - M - kw, M + 12), "THE MUSA FAMILY", kick, C.MUT, 2.6)

    # display lockup, placed by measured visual top
    title  = ImageFont.truetype(ANTON, 248)
    tb     = d.textbbox((0, 0), TITLE, font=title)
    t_top  = 172
    d.text((M - 3, t_top - tb[1]), TITLE, font=title, fill=C.FG)
    t_bot  = t_top + (tb[3] - tb[1])
    t_right = M - 3 + tb[2]

    # gold hairline — the only color on the card, used sparingly
    r_y = t_bot + 37
    d.rectangle([M, r_y, M + 96, r_y + 2], fill=C.AMBER)

    # the line the site itself uses
    sub   = C.font(C.MONO, 25)
    sb    = d.textbbox((0, 0), SUB, font=sub)
    s_top = r_y + 2 + 34
    d.text((M, s_top - sb[1]), SUB, font=sub, fill=C.SAND)
    s_bot = s_top + (sb[3] - sb[1])

    # footer rule + chrome. Root domain only: it outlives any subdomain move.
    f_rule = H - 108
    d.rectangle([M, f_rule, W - M, f_rule + 1], fill=C.LINE)
    foot = C.font(C.MONOM, 17)
    C.tracked(d, (M, H - 82), "CURATED BY NIGHTVISION", foot, C.MUT2, 2.4)
    dw = C.tw(d, "THEMUSAFAMILY.COM", foot, 2.4)
    C.tracked(d, (W - M - dw, H - 82), "THEMUSAFAMILY.COM", foot, C.MUT2, 2.4)

    # layout guards — fail loudly rather than shipping a broken card
    assert t_right < W - M,        f"title overruns right margin ({t_right})"
    assert M + 96 < W - M
    assert t_bot < r_y,            "title collides with rule"
    assert s_top > r_y + 2,        "subtitle collides with rule"
    assert sb[2] < W - 2 * M,      f"subtitle too wide ({sb[2]})"
    assert s_bot < f_rule - 16,    f"subtitle crowds the footer ({s_bot} vs {f_rule})"

    C.scanlines(im)
    im.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} {im.size}")
    print(f"  title {t_top}..{t_bot} (w {tb[2]})  rule {r_y}  sub {s_top}..{s_bot}  footrule {f_rule}")


if __name__ == "__main__":
    build()
