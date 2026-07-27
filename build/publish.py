# -*- coding: utf-8 -*-
"""Builds the static, shareable layer of the MUSA magazine from ledger.json:
   /i/<slug>/index.html  — one addressable page per read, with real OG meta
   /cards/<slug>-og.jpg  — 1200x630 unfurl card (iMessage, X, everything else)
   /cards/<slug>-sq.jpg  — 1080x1350 card (Instagram)
   /sitemap.xml, /robots.txt
Writes the slug back onto each ledger entry so the magazine can link to it."""
import json, os, re, sys, unicodedata, html, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cards

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BASE = "https://archive.themusafamily.com"
MARK = "https://archive.themusafamily.com/img/musa-mark.png"  # every entry carries art; missing/broken images fall back to the MUSA mark
MONTHS=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]

def slugify(s, maxlen=64):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    s = re.sub(r"-{2,}", "-", s)
    if len(s) > maxlen: s = s[:maxlen].rstrip("-")
    return s or "entry"

def fmt_date(d):
    try:
        y,m,dd = str(d).split("-")[:3]
        return "%s %d %s" % (MONTHS[int(m)-1], int(dd), y)
    except Exception:
        return str(d or "")

def e(x): return html.escape(str(x if x is not None else ""), quote=True)

TIER_CLASS={"HEIRWAVE":"t-heir","CROWN":"t-crown","FLAME":"t-flame",
            "TORCH":"t-torch","SPARK":"t-spark","NOISE":"t-noise"}

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} — MUSA · The Index</title>
<link rel="canonical" href="{url}">
<meta name="description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="MUSA — The Index">
<meta property="og:title" content="{name}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{card}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{name}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{card}">
<meta name="theme-color" content="#0a0a0a">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Instrument+Serif&family=Newsreader:opsz,wght@6..72,300;6..72,400&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0a0a;--panel:#111110;--line:#26241f;--fg:#f2ead5;--fg2:#d6cdb8;--mut:#8c887e;--mut2:#6d6a62;
--green:#3fb56b;--red:#e4533a;--amber:#e8c96d;--sand:#cdbf99;--yellow:#f4d93e;--yellow2:#fff2a0;
--serif:"Instrument Serif",Georgia,serif;--text:"Newsreader",Georgia,serif;
--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:var(--bg);color:var(--fg);font-family:var(--mono);-webkit-font-smoothing:antialiased}}
body{{max-width:760px;margin:0 auto;padding:22px 20px 70px;position:relative;overflow-x:hidden}}
body::before{{content:"";position:fixed;inset:0;pointer-events:none;z-index:99;
background:repeating-linear-gradient(0deg,rgba(255,255,255,.013) 0 1px,transparent 1px 3px)}}
a{{color:inherit}}
.masthead{{display:flex;align-items:center;gap:14px;padding-bottom:18px;border-bottom:1px solid var(--line)}}
.mark{{width:42px;height:42px;color:var(--fg);flex:none}}
.lockup{{display:flex;align-items:center;gap:14px;text-decoration:none;color:inherit;transition:opacity .15s}}
.lockup:hover{{opacity:.78}}
.lockup:focus-visible{{outline:1px solid var(--amber);outline-offset:6px}}
.lock{{display:block}}
.wordmark{{display:block;height:30px;width:auto}}
.mh-sub{{display:block;font-family:var(--mono);font-size:8.5px;letter-spacing:.32em;color:var(--mut);margin-top:6px}}
.back{{margin-left:auto;font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;color:var(--mut);text-decoration:none}}
.back:hover{{color:var(--fg)}}
.eyebrow{{font-family:var(--mono);font-size:9.5px;letter-spacing:.22em;color:var(--mut);margin:34px 0 14px}}
.eyebrow .a{{color:var(--amber)}}
h1{{font-family:var(--serif);font-size:clamp(30px,6vw,46px);line-height:1.13;font-weight:400}}
.art{{margin-top:26px;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#151412}}
.art img{{display:block;width:100%;height:auto}}
.read{{font-family:var(--text);font-size:19px;line-height:1.62;color:var(--fg2);margin-top:26px}}
.rail{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:28px;padding:15px 0;
border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}
.sc{{font-family:var(--serif);font-size:34px;line-height:1}}
.sc small{{font-family:var(--mono);font-size:9px;letter-spacing:.18em;color:var(--mut);margin-left:6px;vertical-align:7px}}
.tier{{font-family:var(--mono);font-size:9px;letter-spacing:.14em;padding:4px 9px;border-radius:3px;border:1px solid var(--line)}}
.t-heir{{color:#f2ead5;border-color:#5a5446}}.t-crown{{color:var(--amber);border-color:#3a2f1c}}
.t-flame{{color:#e89a5a;border-color:#3a2a1c}}.t-torch{{color:#c9b27a;border-color:#312b1c}}
.t-spark{{color:var(--green);border-color:#1f3a28}}.t-noise{{color:var(--red);border-color:#3a2020}}
.flag{{font-family:var(--mono);font-size:8.5px;letter-spacing:.12em;color:var(--green);
border:1px solid #2f3a28;border-radius:3px;padding:3px 7px}}
.flag.held{{color:var(--amber);border-color:#3a2f1c}}.flag.heat{{color:var(--red);border-color:#3a2020}}
.heatwrap{{display:flex;align-items:center;gap:8px;font-family:var(--mono);font-size:9.5px;
letter-spacing:.12em;color:var(--mut);margin-left:auto}}
.heatbar{{width:74px;height:5px;background:#1c1a16;border-radius:3px;overflow:hidden}}
.heatfill{{height:100%;background:linear-gradient(90deg,#7a6f4a,var(--amber))}}
.dir{{font-size:11px}}.dir.u{{color:var(--green)}}.dir.d{{color:var(--red)}}.dir.f{{color:var(--mut)}}
.bench{{font-family:var(--mono);font-size:10px;letter-spacing:.16em;color:var(--mut);margin-top:16px}}
.bench b{{color:var(--sand);font-weight:500}}
.benchlink{{color:var(--sand);text-decoration:none;border-bottom:1px dotted #5a5446;transition:.15s}}
.benchlink:hover{{color:var(--yellow2);border-bottom-color:var(--yellow2)}}
.src{{display:inline-block;margin-top:22px;font-family:var(--mono);font-size:10px;letter-spacing:.16em;
color:var(--yellow);border:1px solid #4a3f22;border-radius:4px;padding:10px 16px;text-decoration:none}}
.src:hover{{color:var(--yellow2);border-color:var(--yellow2)}}
.also{{margin-top:52px;border-top:1px solid var(--line);padding-top:20px}}
.also .lbl{{font-family:var(--mono);font-size:9px;letter-spacing:.22em;color:var(--mut);margin-bottom:14px}}
.also a{{display:block;font-family:var(--serif);font-size:19px;color:var(--fg2);text-decoration:none;
padding:11px 0;border-top:1px solid var(--line)}}
.also a:first-of-type{{border-top:none}}
.also a:hover{{color:var(--yellow2)}}
.also a span{{font-family:var(--mono);font-size:9px;letter-spacing:.16em;color:var(--mut);margin-left:10px}}
footer{{margin-top:48px;border-top:1px solid var(--line);padding-top:18px;
font-family:var(--text);font-size:14px;color:var(--mut);line-height:1.7}}
footer b{{font-family:var(--mono);font-size:9px;color:#b8b09c;letter-spacing:.2em;display:block;margin-bottom:7px}}
</style>
<script type="application/ld+json">{jsonld}</script>
</head><body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs><g id="heirwave-paths">{heir}</g></defs></svg>
<header class="masthead">
<a class="lockup" href="/" aria-label="MUSA — The Index, home">
  <svg class="mark" viewBox="180 320 660 360" aria-hidden="true"><use href="#heirwave-paths"/></svg>
  <span class="lock">
    <img class="wordmark" src="/musa-wordmark.svg" alt="MUSA" width="104" height="30">
    <span class="mh-sub">THE MUSA FAMILY · HEIRWAVE</span>
  </span>
</a>
<a class="back" href="/">← THE INDEX</a>
</header>
<div class="eyebrow">ISSUE {issue} &nbsp;·&nbsp; <span class="a">{date}</span> &nbsp;·&nbsp; {domain}</div>
<h1>{name}</h1>
{art}
<div class="read">{read}</div>
<div class="rail">
  <span class="sc">{score}<small>SCORE</small></span>
  <span class="tier {tclass}">{tier}</span>
  {flags}
  <span class="heatwrap"><span>HEAT {heat}</span>
    <span class="heatbar"><span class="heatfill" style="width:{heatw}%"></span></span>
    <span class="dir {dc}">{dg}</span></span>
</div>
{bench}
{srclink}
<div class="also"><div class="lbl">ALSO IN ISSUE {issue}</div>{also}</div>
<footer><b>THE MUSA FAMILY · HEIRWAVE</b>
Scores and heat are editorial taste reads, not metrics. Every call is dated, kept, and never quietly rewritten.
Read against <a href="/#the50">THE 50</a> — the canon and the gate.</footer>
</body></html>
"""



# ── Domain taxonomy ────────────────────────────────────────────────────────────
# Domains had drifted into 41 distinct strings — case variants ("ART" / "Art") and
# free-text sub-labels ("MUSIC · UNDERGROUND RAP") each spawned their own filter
# chip. Canon is the part before the "·", uppercased, run through the alias table.
# The sub-label is kept as `domain_detail` because it's good editorial texture —
# it just shouldn't be a filter.
DOMAIN_ALIAS = {
    "INTERNET": "SCENE",        # the skill's pool calls this lane Internet/Scene
    "CREATOR-AI": "TECH",
    "PUBLIC ART": "ART",
    "PHOTOGRAPHY": "ART",
    "SPORT": "SPORTS",
}
DOMAINS = ["ARCHITECTURE","ART","BOOKS","CRAFT","DESIGN","EDITORIAL","FASHION",
           "FILM","GAMES","IDEAS","MUSIC","SCENE","SPORTS","TECH","TV"]

def canon_domain(s):
    head = re.split(r"[·|/]", str(s or ""))[0].strip().upper()
    head = DOMAIN_ALIAS.get(head, head)
    return head if head in DOMAINS else (head or "")

def normalise_domains(led):
    changed = 0
    for iss in led.get("issues", []):
        for en in iss.get("entries", []):
            raw = str(en.get("domain","") or "").strip()
            canon = canon_domain(raw)
            if not canon: continue
            detail = " · ".join(p.strip().upper() for p in re.split(r"·", raw)[1:]).strip()
            if detail: en["domain_detail"] = "%s · %s" % (canon, detail)
            elif "domain_detail" in en and canon_domain(en["domain_detail"]) == canon and "·" not in en["domain_detail"]:
                en.pop("domain_detail", None)
            if raw != canon: changed += 1
            en["domain"] = canon
    return changed


def normalise_issue_numbers(led):
    """`issue` started life as a timestamp string ("2026-06-17-0638") and only became
    a number at issue 30, so 14 issues rendered as "ISSUE " with nothing after it.
    Number every issue chronologically and keep the timestamp in `issue_id`, which is
    what the holding registry references."""
    rows = sorted(led.get("issues", []),
                  key=lambda i: str(i.get("date","")) + str(i.get("time","")))
    fixed = 0
    for n, iss in enumerate(rows, 1):
        old = iss.get("issue")
        if isinstance(old, str) and not str(old).isdigit():
            iss.setdefault("issue_id", old)
        iss.setdefault("issue_id", "%s-%s" % (iss.get("date",""), str(iss.get("time","")).replace(":","")[:4]))
        if iss.get("issue") != n:
            iss["issue"] = n; fixed += 1
    return fixed

def bench_map(canon):
    """A benchmark names somebody on THE 50 — build a longest-match lookup so the
    name is clickable on the permalink page too."""
    out=[]
    for grp in (canon.get("entries") or [], canon.get("alumni") or []):
        for c in grp:
            k=bench_norm(c.get("name",""))
            if c.get("url") and len(k)>=4: out.append((k, c["name"], c["url"]))
    out.sort(key=lambda t: -len(t[0]))
    return out

def bench_norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def bench_html(b, bmap):
    if not b: return ""
    hay = " " + bench_norm(b) + " "
    for k, name, url in bmap:
        if (" " + k + " ") in hay:
            i = b.lower().find(name.lower())
            a = ('<a class="benchlink" href="%s" target="_blank" rel="noopener" '
                 'title="On THE MUSA 50">%s</a>') % (e(url), e(name))
            return a if i < 0 else e(b[:i]) + a + e(b[i+len(name):])
    return e(b)

def build(commit_slugs=True):
    led = json.load(open(os.path.join(ROOT, "ledger.json"), encoding="utf-8"))
    canon = json.load(open(os.path.join(ROOT, "musa-50.json"), encoding="utf-8"))
    n = normalise_domains(led)
    if n: print("domains normalised on %d entries" % n)
    f = normalise_issue_numbers(led)
    if f: print("issue numbers assigned/corrected on %d issues" % f)
    bmap = bench_map(canon)
    heir = open(os.path.join(ROOT, "build", "heirwave.svg"), encoding="utf-8").read()
    paths = re.findall(r'<path[^>]*d="([^"]+)"', heir)
    heir_defs = "".join('<path fill="currentColor" d="%s"/>' % d for d in paths)

    outdir = os.path.join(ROOT, "i"); carddir = os.path.join(ROOT, "cards")
    if os.path.isdir(outdir): shutil.rmtree(outdir)      # pages are cheap, always rebuild
    os.makedirs(outdir); os.makedirs(carddir, exist_ok=True)

    seen = {}
    issues = sorted(led.get("issues", []), key=lambda i: str(i.get("date","")) + str(i.get("time","")), reverse=True)

    # pass 1 — assign a stable slug to every entry
    for iss in issues:
        for en in iss.get("entries", []):
            base = slugify(en.get("name",""))
            slug = base; n = 2
            while slug in seen: slug = "%s-%d" % (base, n); n += 1
            seen[slug] = (iss, en)
            en["slug"] = slug

    # pass 2 — render cards + pages
    urls = []
    for slug, (iss, en) in seen.items():
        # cards are deterministic — only render the ones that don't exist yet, so a
        # rebuild doesn't churn 35MB of new blobs into git every run.
        ogp=os.path.join(carddir, slug + "-og.jpg"); sqp=os.path.join(carddir, slug + "-sq.jpg")
        if not os.path.exists(ogp): cards.og(en, iss, ogp)
        if not os.path.exists(sqp): cards.sq(en, iss, sqp)

        sibs = [s for s in iss.get("entries", []) if s.get("slug") != slug]
        also = "".join(
            '<a href="/i/%s/">%s<span>%s · %s</span></a>' % (
                e(s.get("slug")), e(s.get("name")),
                e(str(s.get("domain","")).upper()), e("%.1f" % float(s.get("score",0))))
            for s in sibs) or '<a href="/">See the full archive</a>'

        read = str(en.get("read","") or "")
        desc = (read[:185] + "…") if len(read) > 185 else read
        if not desc:
            desc = "%s — scored %s against THE MUSA 50." % (en.get("name",""), en.get("score",""))
        url = "%s/i/%s/" % (BASE, slug)
        tier = str(en.get("tier","") or "")
        flags = "".join(
            '<span class="flag %s">%s</span>' % (
                "heat" if "HEAT" in str(f).upper() else ("" if "FIND" in str(f).upper() else "held"),
                e(str(f).replace("_"," ")))
            for f in (en.get("flags") or []) if "BLADE" not in str(f).upper())
        d = en.get("direction","flat")
        # Rule 8: every entry carries art. Backfilled entries already point AT the mark, so their
        # onerror never fires — apply the letterbox styling up front for those, not just on failure.
        src = en.get("image") or MARK
        is_mark = (src == MARK)
        art = ('<figure class="art"><img src="%s" alt="%s" loading="lazy"%s '
               'onerror="this.onerror=null;this.src=\'%s\';this.style.objectFit=\'contain\';this.style.background=\'#0a0a0a\'"></figure>'
               % (e(src), e(en.get("name","")),
                  ' style="height:320px;object-fit:contain;background:#0a0a0a"' if is_mark else '',
                  MARK))
        srclink = ('<a class="src" href="%s" target="_blank" rel="noopener">GO TO THE SOURCE ↗</a>' % e(en["url"])) if en.get("url") else ""
        bench = ('<div class="bench">BENCHMARK IN THE 50 · <b>%s</b></div>' % bench_html(en["benchmark"], bmap)) if en.get("benchmark") else ""
        jsonld = json.dumps({
            "@context":"https://schema.org","@type":"Article",
            "headline": en.get("name",""), "description": desc,
            "datePublished": iss.get("date",""), "url": url,
            "image": "%s/cards/%s-og.jpg" % (BASE, slug),
            "publisher":{"@type":"Organization","name":"The Musa Family"},
            "isPartOf":{"@type":"PublicationIssue","issueNumber": iss.get("issue","")}
        }, ensure_ascii=False)

        page = PAGE.format(
            name=e(en.get("name","")), desc=e(desc), url=e(url),
            card=e("%s/cards/%s-og.jpg" % (BASE, slug)),
            issue=e(iss.get("issue","")), date=e(fmt_date(iss.get("date"))),
            domain=e(str(en.get("domain_detail") or en.get("domain","")).upper()),
            art=art, read=e(read), score=e("%.1f" % float(en.get("score",0))),
            tier=e(tier), tclass=TIER_CLASS.get(tier,""), flags=flags,
            heat=e(en.get("heat",0)), heatw=min(100,int(en.get("heat",0) or 0)),
            dc={"up":"u","down":"d"}.get(d,"f"), dg={"up":"▲","down":"▼"}.get(d,"▮"),
            bench=bench, srclink=srclink, also=also, heir=heir_defs, jsonld=jsonld)

        pdir = os.path.join(outdir, slug); os.makedirs(pdir, exist_ok=True)
        open(os.path.join(pdir, "index.html"), "w", encoding="utf-8").write(page)
        urls.append((url, iss.get("date","")))

    # homepage share card = the current cover story
    if issues:
        lead = sorted(issues[0].get("entries", []), key=lambda x: x.get("rank", 99))[0]
        cards.og(lead, issues[0], os.path.join(carddir, "home-og.jpg"))

    # sitemap + robots
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
          '<url><loc>%s/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>' % BASE]
    for u, dt in urls:
        sm.append('<url><loc>%s</loc>%s<priority>0.8</priority></url>' % (u, ("<lastmod>%s</lastmod>" % dt) if dt else ""))
    sm.append('</urlset>')
    open(os.path.join(ROOT,"sitemap.xml"),"w",encoding="utf-8").write("\n".join(sm))
    open(os.path.join(ROOT,"robots.txt"),"w",encoding="utf-8").write(
        "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % BASE)

    if commit_slugs:
        json.dump(led, open(os.path.join(ROOT,"ledger.json"),"w",encoding="utf-8"), indent=2, ensure_ascii=False)
        open(os.path.join(ROOT,"ledger.json"),"a",encoding="utf-8").write("\n")

    print("pages: %d  cards: %d  sitemap urls: %d" % (len(seen), len(seen)*2+1, len(urls)+1))
    return seen

if __name__ == "__main__":
    build()
