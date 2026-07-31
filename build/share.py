# -*- coding: utf-8 -*-
"""Builds /share/ — the card room.

Every call ever made, newest first, as a browsable grid of its Instagram card.
Tap a card to open it: share straight to IG via the native sheet, save the file,
or copy a pre-written caption. Filter by lane, by issue, or by name.

Fed entirely from ledger.json — no separate state, nothing to maintain. Runs at
the tail of publish.py so a new issue lands here automatically.
"""
import json, os, html

BASE = "https://archive.themusafamily.com"
MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]


def fmt_date(d):
    try:
        y, m, dd = str(d).split("-")[:3]
        return "%s %d %s" % (MONTHS[int(m)-1], int(dd), y)
    except Exception:
        return str(d or "")


def e(x):
    return html.escape(str(x if x is not None else ""), quote=True)


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>The Card Room — MUSA · The Index</title>
<link rel="canonical" href="{base}/share/">
<meta name="description" content="Every call from THE INDEX as a ready-to-post share card. {count} cards, newest first.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="MUSA — The Index">
<meta property="og:title" content="The Card Room — THE INDEX">
<meta property="og:description" content="Every call from THE INDEX as a ready-to-post share card. {count} cards, newest first.">
<meta property="og:url" content="{base}/share/">
<meta property="og:image" content="{base}/cards/home-og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="The Card Room — THE INDEX">
<meta name="twitter:image" content="{base}/cards/home-og.jpg">
<meta name="robots" content="noindex">
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
body{{max-width:1080px;margin:0 auto;padding:22px 18px 90px;position:relative;overflow-x:hidden}}
body::before{{content:"";position:fixed;inset:0;pointer-events:none;z-index:99;
background:repeating-linear-gradient(0deg,rgba(255,255,255,.013) 0 1px,transparent 1px 3px)}}
a{{color:inherit}}
.masthead{{display:flex;align-items:center;gap:14px;padding-bottom:18px;border-bottom:1px solid var(--line)}}
.mark{{width:42px;height:42px;color:var(--fg);flex:none}}
.lockup{{display:flex;align-items:center;gap:14px;text-decoration:none;color:inherit;transition:opacity .15s}}
.lockup:hover{{opacity:.78}}
.wordmark{{display:block;height:30px;width:auto}}
.mh-sub{{display:block;font-family:var(--mono);font-size:8.5px;letter-spacing:.32em;color:var(--mut);margin-top:6px}}
.back{{margin-left:auto;font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;color:var(--mut);text-decoration:none}}
.back:hover{{color:var(--fg)}}
h1{{font-family:var(--serif);font-size:clamp(30px,6vw,46px);line-height:1.13;font-weight:400;margin-top:32px}}
.lede{{font-family:var(--text);font-size:17px;line-height:1.6;color:var(--fg2);margin-top:12px;max-width:56ch}}

/* ── controls ── */
.controls{{position:sticky;top:0;z-index:40;background:var(--bg);padding:16px 0 12px;
margin-top:20px;border-bottom:1px solid var(--line)}}
.searchrow{{display:flex;gap:8px;align-items:stretch}}
#q{{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:5px;color:var(--fg);
font-family:var(--mono);font-size:13px;letter-spacing:.04em;padding:11px 13px;-webkit-appearance:none}}
#q::placeholder{{color:var(--mut2);letter-spacing:.14em;font-size:11px}}
#q:focus{{outline:none;border-color:#4a4436}}
.fmt{{display:flex;border:1px solid var(--line);border-radius:5px;overflow:hidden;flex:none}}
.fmt button{{background:transparent;border:0;color:var(--mut);font-family:var(--mono);font-size:9px;
letter-spacing:.14em;padding:0 12px;cursor:pointer}}
.fmt button.on{{background:#1b1913;color:var(--amber)}}
.chips{{display:flex;gap:6px;overflow-x:auto;margin-top:10px;padding-bottom:3px;-webkit-overflow-scrolling:touch;
scrollbar-width:none}}
.chips::-webkit-scrollbar{{display:none}}
.chip{{flex:none;background:transparent;border:1px solid var(--line);border-radius:3px;color:var(--mut);
font-family:var(--mono);font-size:9px;letter-spacing:.14em;padding:6px 10px;cursor:pointer;white-space:nowrap}}
.chip:hover{{color:var(--fg2)}}
.chip.on{{color:var(--amber);border-color:#3a2f1c;background:#16140f}}
.tally{{font-family:var(--mono);font-size:9px;letter-spacing:.22em;color:var(--mut2);margin-top:10px}}

/* ── the key, pinned ── */
.keypin{{display:flex;gap:18px;align-items:center;margin-top:22px;padding:16px;
background:var(--panel);border:1px dashed var(--line);border-radius:10px}}
.keypin img{{display:block;width:112px;flex:none;border-radius:6px;border:1px solid var(--line)}}
.keypin .kbody{{min-width:0}}
.keypin .klab{{font-family:var(--mono);font-size:9px;letter-spacing:.22em;color:var(--amber)}}
.keypin .ktxt{{font-family:var(--mono);font-size:11px;line-height:1.65;color:var(--mut);margin-top:7px}}
.keypin .ktxt b{{color:var(--fg2);font-weight:400}}
.keypin .kacts{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}}
.keypin .kacts a{{font-family:var(--mono);font-size:9px;letter-spacing:.14em;color:var(--mut);
text-decoration:none;border:1px solid var(--line);border-radius:3px;padding:7px 11px;white-space:nowrap}}
.keypin .kacts a:hover{{color:var(--amber);border-color:#3a2f1c}}
@media(max-width:520px){{.keypin{{flex-direction:column;align-items:flex-start}}
.keypin img{{width:100%;max-width:220px;align-self:center}}}}

/* ── grid ── */
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(158px,1fr));gap:14px;margin-top:22px}}
.tile{{display:block;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--panel);
cursor:pointer;padding:0;text-align:left;font:inherit;color:inherit;transition:border-color .15s}}
.tile:hover{{border-color:#4a4436}}
.tile:focus-visible{{outline:1px solid var(--amber);outline-offset:3px}}
.tile img{{display:block;width:100%;aspect-ratio:4/5;object-fit:cover;background:#151412}}
.tile.og img{{aspect-ratio:1200/630}}
.tmeta{{padding:9px 10px 11px;border-top:1px solid var(--line)}}
.tnm{{font-family:var(--serif);font-size:15px;line-height:1.2;color:var(--fg2);
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.tsub{{font-family:var(--mono);font-size:8px;letter-spacing:.16em;color:var(--mut2);margin-top:6px;
display:flex;gap:7px;align-items:center}}
.tsub .sc{{color:var(--sand)}}
.empty{{font-family:var(--text);font-size:17px;color:var(--mut);margin-top:40px;text-align:center}}

/* ── sheet ── */
.sheet{{position:fixed;inset:0;z-index:100;background:rgba(6,6,6,.93);
-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);
display:none;align-items:flex-start;justify-content:center;overflow-y:auto;padding:22px 16px 40px}}
.sheet.open{{display:flex}}
.sbox{{width:100%;max-width:440px}}
.sclose{{display:block;margin-left:auto;background:transparent;border:1px solid var(--line);border-radius:4px;
color:var(--mut);font-family:var(--mono);font-size:10px;letter-spacing:.18em;padding:8px 12px;cursor:pointer}}
.sclose:hover{{color:var(--fg);border-color:#4a4436}}
.simg{{width:100%;margin-top:12px;border:1px solid var(--line);border-radius:8px;background:#151412;display:block}}
.snm{{font-family:var(--serif);font-size:24px;line-height:1.18;margin-top:18px}}
.ssub{{font-family:var(--mono);font-size:9px;letter-spacing:.18em;color:var(--mut);margin-top:9px}}
.ssub .a{{color:var(--amber)}}
.acts{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:18px}}
.acts button,.acts a{{display:flex;align-items:center;justify-content:center;text-align:center;
font-family:var(--mono);font-size:10px;letter-spacing:.14em;padding:13px 8px;border-radius:4px;
border:1px solid var(--line);background:transparent;color:var(--fg2);cursor:pointer;text-decoration:none}}
.acts button:hover,.acts a:hover{{border-color:#4a4436;color:var(--fg)}}
.acts .primary{{grid-column:1/-1;color:var(--yellow);border-color:#4a3f22}}
.acts .primary:hover{{color:var(--yellow2);border-color:var(--yellow2)}}
.acts .done{{color:var(--green);border-color:#1f3a28}}
.cap{{margin-top:16px;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:13px;
font-family:var(--text);font-size:14px;line-height:1.6;color:var(--fg2);white-space:pre-wrap;
max-height:220px;overflow-y:auto}}
.caplbl{{font-family:var(--mono);font-size:8.5px;letter-spacing:.22em;color:var(--mut2);margin-top:20px}}
.hint{{font-family:var(--mono);font-size:8.5px;letter-spacing:.1em;color:var(--mut2);margin-top:12px;line-height:1.7}}

footer{{margin-top:52px;border-top:1px solid var(--line);padding-top:18px;
font-family:var(--text);font-size:14px;color:var(--mut);line-height:1.7}}
footer b{{font-family:var(--mono);font-size:9px;color:#b8b09c;letter-spacing:.2em;display:block;margin-bottom:7px}}
@media(max-width:520px){{
  .grid{{grid-template-columns:repeat(2,1fr);gap:10px}}
  body{{padding:20px 14px 80px}}
}}
</style>
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

<h1>The Card Room</h1>
<div class="lede">Every call ever made, already cut to size. Tap one to send it straight to the feed, save the file, or take the caption with it.</div>

<section class="keypin">
  <a href="/cards/the-key-sq.jpg" target="_blank" rel="noopener">
    <img src="/cards/the-key-sq.jpg" alt="THE KEY — how to read a MUSA score" loading="eager" decoding="async">
  </a>
  <div class="kbody">
    <div class="klab">THE KEY · SLIDE TWO</div>
    <div class="ktxt">Save this and run it behind any card. <b>A high score sitting on low heat is a FIND</b> — the work already holds up, the room hasn't arrived, and you're getting put onto it before it gets loud. That gap is the whole board.</div>
    <div class="kacts">
      <a href="/cards/the-key-sq.jpg" download="musa-the-key-sq.jpg">SAVE 1080×1350</a>
      <a href="/cards/the-key-og.jpg" download="musa-the-key-og.jpg">SAVE 1200×630</a>
      <a href="/#key">READ THE FULL KEY ↗</a>
    </div>
  </div>
</section>

<div class="controls">
  <div class="searchrow">
    <input id="q" type="search" placeholder="SEARCH A NAME" autocomplete="off" autocorrect="off" spellcheck="false">
    <div class="fmt">
      <button type="button" data-fmt="sq" class="on">IG</button>
      <button type="button" data-fmt="og">X</button>
    </div>
  </div>
  <div class="chips" id="chips"></div>
  <div class="tally" id="tally"></div>
</div>

<div class="grid" id="grid"></div>
<div class="empty" id="empty" style="display:none">Nothing in the room under that.</div>

<footer><b>THE MUSA FAMILY · HEIRWAVE</b>
IG cards run 1080×1350. X cards run 1200×630 and unfurl on their own when you post the link.
Browse <a href="/issues/">every issue</a> or read against <a href="/#the50">THE 50</a>.</footer>

<div class="sheet" id="sheet" role="dialog" aria-modal="true" aria-label="Share card">
  <div class="sbox">
    <button class="sclose" type="button" id="sclose">CLOSE ✕</button>
    <img class="simg" id="simg" alt="">
    <div class="snm" id="snm"></div>
    <div class="ssub" id="ssub"></div>
    <div class="acts">
      <button type="button" class="primary" id="a-share">SHARE ↗</button>
      <a id="a-save" download>SAVE IMAGE</a>
      <button type="button" id="a-cap">COPY CAPTION</button>
      <button type="button" id="a-link">COPY LINK</button>
      <a id="a-page" href="#">OPEN THE PAGE</a>
    </div>
    <div class="caplbl">CAPTION</div>
    <div class="cap" id="cap"></div>
    <div class="hint" id="hint"></div>
  </div>
</div>

<script>
const DATA = {data};
const BASE = "{base}";

const grid=document.getElementById("grid"), empty=document.getElementById("empty"),
      tally=document.getElementById("tally"), chips=document.getElementById("chips"),
      q=document.getElementById("q"), sheet=document.getElementById("sheet");
let fmt="sq", lane="", term="", current=null;

/* lane chips, most-used first */
const counts={{}};
DATA.forEach(d=>{{ if(d.domain) counts[d.domain]=(counts[d.domain]||0)+1; }});
const lanes=Object.keys(counts).sort((a,b)=>counts[b]-counts[a]||a.localeCompare(b));
chips.innerHTML='<button class="chip on" data-lane="">ALL</button>'+
  lanes.map(l=>'<button class="chip" data-lane="'+l+'">'+l+' '+counts[l]+'</button>').join("");

function caption(d){{
  const L=[];
  L.push(d.name);
  L.push(d.domain_detail||d.domain);
  L.push("");
  if(d.read) {{ L.push(d.read); L.push(""); }}
  let rail=d.score.toFixed(1)+" · "+d.tier;
  if(d.flags && d.flags.length) rail+=" · "+d.flags.join(" · ");
  L.push(rail);
  if(d.benchmark) L.push("Benchmark in THE 50 — "+d.benchmark);
  L.push("");
  L.push("THE INDEX · Issue "+d.issue+" · "+d.date);
  L.push(BASE.replace("https://","")+"/i/"+d.slug+"/");
  return L.join("\\n");
}}

function render(){{
  const t=term.trim().toLowerCase();
  const rows=DATA.filter(d=>
    (!lane||d.domain===lane) &&
    (!t||d.name.toLowerCase().includes(t)||(d.read||"").toLowerCase().includes(t)||
        (d.benchmark||"").toLowerCase().includes(t)||String(d.issue)===t));
  grid.innerHTML=rows.map((d,i)=>
    '<button class="tile '+fmt+'" data-i="'+DATA.indexOf(d)+'">'+
    '<img loading="lazy" decoding="async" src="/cards/'+d.slug+'-'+fmt+'.jpg" alt="'+d.name.replace(/"/g,"&quot;")+'">'+
    '<div class="tmeta"><div class="tnm">'+d.name+'</div>'+
    '<div class="tsub"><span class="sc">'+d.score.toFixed(1)+'</span><span>'+d.domain+'</span>'+
    '<span style="margin-left:auto">#'+d.issue+'</span></div></div></button>').join("");
  empty.style.display=rows.length?"none":"block";
  tally.textContent=rows.length+" CARD"+(rows.length===1?"":"S")+
    (lane?" · "+lane:"")+" · "+(fmt==="sq"?"1080×1350 INSTAGRAM":"1200×630 X / IMESSAGE");
}}

grid.addEventListener("click",ev=>{{
  const t=ev.target.closest(".tile"); if(t) openCard(DATA[+t.dataset.i]);
}});
chips.addEventListener("click",ev=>{{
  const c=ev.target.closest(".chip"); if(!c) return;
  lane=c.dataset.lane;
  [...chips.children].forEach(x=>x.classList.toggle("on",x===c));
  render();
}});
document.querySelectorAll(".fmt button").forEach(b=>b.addEventListener("click",()=>{{
  fmt=b.dataset.fmt;
  document.querySelectorAll(".fmt button").forEach(x=>x.classList.toggle("on",x===b));
  render();
}}));
q.addEventListener("input",()=>{{term=q.value;render();}});

/* ── the sheet ── */
function openCard(d){{
  current=d;
  const file="/cards/"+d.slug+"-"+fmt+".jpg";
  document.getElementById("simg").src=file;
  document.getElementById("simg").alt=d.name;
  document.getElementById("snm").textContent=d.name;
  document.getElementById("ssub").innerHTML=
    'ISSUE '+d.issue+' &nbsp;·&nbsp; <span class="a">'+d.date+'</span> &nbsp;·&nbsp; '+
    (d.domain_detail||d.domain)+' &nbsp;·&nbsp; '+d.score.toFixed(1)+' '+d.tier;
  const save=document.getElementById("a-save");
  save.href=file; save.setAttribute("download",d.slug+"-"+fmt+".jpg");
  document.getElementById("a-page").href="/i/"+d.slug+"/";
  document.getElementById("cap").textContent=caption(d);
  document.getElementById("hint").textContent = navigator.canShare
    ? "SHARE OPENS THE NATIVE SHEET — PICK INSTAGRAM, THE IMAGE GOES WITH IT. CAPTION STILL NEEDS A PASTE."
    : "ON DESKTOP: SAVE IMAGE, THEN COPY THE CAPTION. SHARE FALLS BACK TO A DOWNLOAD.";
  ["a-share","a-cap","a-link"].forEach(id=>reset(document.getElementById(id)));
  sheet.classList.add("open"); document.body.style.overflow="hidden";
}}
function closeCard(){{ sheet.classList.remove("open"); document.body.style.overflow=""; current=null; }}
document.getElementById("sclose").addEventListener("click",closeCard);
sheet.addEventListener("click",ev=>{{ if(ev.target===sheet) closeCard(); }});
document.addEventListener("keydown",ev=>{{ if(ev.key==="Escape"&&sheet.classList.contains("open")) closeCard(); }});

const LABEL={{"a-share":"SHARE ↗","a-cap":"COPY CAPTION","a-link":"COPY LINK"}};
function reset(b){{ b.textContent=LABEL[b.id]; b.classList.remove("done"); }}
function ok(b,msg){{ b.textContent=msg||"COPIED ✓"; b.classList.add("done");
  setTimeout(()=>reset(b),1800); }}
async function copy(text){{
  try{{ await navigator.clipboard.writeText(text); return true; }}
  catch(e){{
    const ta=document.createElement("textarea"); ta.value=text;
    ta.style.position="fixed"; ta.style.opacity="0"; document.body.appendChild(ta);
    ta.select(); let r=false; try{{ r=document.execCommand("copy"); }}catch(_){{}}
    document.body.removeChild(ta); return r;
  }}
}}
document.getElementById("a-cap").addEventListener("click",async ev=>{{
  if(await copy(caption(current))) ok(ev.currentTarget);
}});
document.getElementById("a-link").addEventListener("click",async ev=>{{
  if(await copy(BASE+"/i/"+current.slug+"/")) ok(ev.currentTarget);
}});
document.getElementById("a-share").addEventListener("click",async ev=>{{
  const b=ev.currentTarget, d=current, file="/cards/"+d.slug+"-"+fmt+".jpg";
  b.textContent="PREPARING…";
  try{{
    const res=await fetch(file);
    const blob=await res.blob();
    const f=new File([blob],d.slug+"-"+fmt+".jpg",{{type:"image/jpeg"}});
    if(navigator.canShare && navigator.canShare({{files:[f]}})){{
      await navigator.share({{files:[f],title:d.name,text:caption(d)}});
      reset(b); return;
    }}
  }}catch(err){{ if(err && err.name==="AbortError"){{ reset(b); return; }} }}
  document.getElementById("a-save").click();
  ok(b,"SAVED ↓");
}});

render();
</script>
</body></html>
"""


def build_share(led, heir_defs, root):
    """Render /share/index.html from the ledger. Returns the card count."""
    issues = sorted(led.get("issues", []),
                    key=lambda i: str(i.get("date", "")) + str(i.get("time", "")),
                    reverse=True)
    rows = []
    for iss in issues:
        ents = sorted(iss.get("entries", []), key=lambda x: x.get("rank", 99))
        for en in ents:
            if not en.get("slug"):
                continue
            rows.append({
                "slug": en["slug"],
                "name": str(en.get("name", "")),
                "domain": str(en.get("domain", "")).upper(),
                "domain_detail": str(en.get("domain_detail") or en.get("domain", "")).upper(),
                "score": float(en.get("score", 0) or 0),
                "tier": str(en.get("tier", "") or ""),
                "flags": [str(f).replace("_", " ") for f in (en.get("flags") or [])
                          if "BLADE" not in str(f).upper()],
                "read": str(en.get("read", "") or ""),
                "benchmark": str(en.get("benchmark", "") or ""),
                "issue": iss.get("issue", ""),
                "date": fmt_date(iss.get("date")),
            })

    outdir = os.path.join(root, "share")
    os.makedirs(outdir, exist_ok=True)
    page = PAGE.format(
        base=BASE,
        count=len(rows),
        heir=heir_defs,
        data=json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
    )
    open(os.path.join(outdir, "index.html"), "w", encoding="utf-8").write(page)
    return len(rows)
