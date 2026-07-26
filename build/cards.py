# -*- coding: utf-8 -*-
"""MUSA share-card renderer. Typographic cards — no source photos, so every card
reads as a MUSA object in a feed rather than as somebody else's artwork."""
import os, re, io
from PIL import Image, ImageDraw, ImageFont
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

def card(entry, issue, W, H, out, name_size, read_lines, read_size=19, anchor="center"):
    S=W/1200.0                                   # scale everything off the OG width
    p=lambda v:int(round(v*S))
    im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im)
    M=p(64)                                      # margin
    d.rectangle([M-p(22),M-p(22),W-M+p(22),H-M+p(22)],outline=LINE,width=max(1,p(1)))

    # ── masthead
    hh=p(38); mark=heirwave(hh); im.paste(mark,(M,M),mark)
    fs=font(SERIF,p(40))
    d.text((M+mark.size[0]+p(14), M-p(6)),"MUSA",font=fs,fill=FG)
    fm=font(MONO,p(15))
    right="THE INDEX  ·  ISSUE %s"%issue.get("issue","")
    tracked(d,(W-M-tw(d,right,fm,2.2), M+p(11)),right,fm,MUT,2.2)
    ly=M+hh+p(24)
    d.line([(M,ly),(W-M,ly)],fill=LINE,width=max(1,p(1)))

    # ── measure the editorial block first so it can sit optically centred
    by=H-M-p(124)                                # bottom rail (score row)
    fd=font(MONOM,p(17))
    fn=font(SERIF,p(name_size)); lh=int(p(name_size)*1.05)
    fr=font(MONO,p(read_size)); rlh=int(p(read_size)*1.72)
    nlines=wrap(d,entry.get("name",""),fn,W-2*M,3)
    rlines=wrap(d,entry.get("read",""),fr,W-2*M,read_lines)
    blockH=p(38)+len(nlines)*lh+p(14)+len(rlines)*rlh
    top=ly+p(40)
    if anchor=="bottom":                          # headline sits low, editorial-cover style
        y=max(top, by-p(48)-blockH)
    else:
        y=top; slack=(by-p(30))-(y+blockH)
        if slack>0: y+=int(slack*0.46)

    tracked(d,(M,y),str(entry.get("domain","")).upper(),fd,AMBER,4.2)
    y+=p(38)
    for ln in nlines:
        d.text((M,y),ln,font=fn,fill=FG); y+=lh
    y+=p(14)
    for ln in rlines:
        d.text((M,y),ln,font=fr,fill="#a39e90"); y+=rlh

    d.line([(M,by),(W-M,by)],fill=LINE,width=max(1,p(1)))
    sy=by+p(22)
    sc=("%.1f"%float(entry.get("score",0)))
    fsc=font(SERIF,p(72))
    d.text((M,sy-p(14)),sc,font=fsc,fill=FG)
    x=M+d.textlength(sc,font=fsc)+p(14)
    fl=font(MONO,p(14))
    tracked(d,(x,sy+p(30)),"SCORE",fl,MUT,2.4); x+=tw(d,"SCORE",fl,2.4)+p(18)
    t=str(entry.get("tier","")).upper()
    if t: x=chip(d,x,sy+p(6),t,TIER_COLOR.get(t,FG),TIER_BORDER.get(t,LINE),fs=p(17))+p(10)
    for f_ in [f for f in (entry.get("flags") or []) if "BLADE" not in str(f).upper()]:
        lbl=str(f_).replace("_"," ").upper()
        col=RED if "HEAT" in lbl else (GREEN if "FIND" in lbl else AMBER)
        bor="#3a2020" if "HEAT" in lbl else ("#2f3a28" if "FIND" in lbl else "#3a2f1c")
        x=chip(d,x,sy+p(6),lbl,col,bor,fs=p(17))+p(10)

    # heat, right aligned
    heat=int(entry.get("heat",0) or 0)
    fh=font(MONO,p(16)); ht="HEAT %d"%heat
    bw=p(150); asz=p(15)
    hx=W-M-bw-p(14)-asz
    tracked(d,(hx-tw(d,ht,fh,2.2)-p(12), sy+p(16)),ht,fh,MUT,2.2)
    heatbar(d,hx,sy+p(22),heat,w=bw,h=p(8))
    arrow(d,hx+bw+p(14),sy+p(19),asz,entry.get("direction","flat"))

    # ── footer
    fy=H-M-p(14)
    ff=font(MONO,p(15))
    bench=entry.get("benchmark","")
    if bench: tracked(d,(M,fy),("BENCHMARK  ·  "+bench).upper(),ff,MUT2,2.6)
    site="ARCHIVE.THEMUSAFAMILY.COM"
    tracked(d,(W-M-tw(d,site,ff,2.6),fy),site,ff,MUT2,2.6)

    im=scanlines(im)
    im.save(out,"JPEG",quality=84,optimize=True,progressive=True)
    return out

def og(entry,issue,out):  return card(entry,issue,1200,630,out,name_size=60,read_lines=3,read_size=19)
def sq(entry,issue,out):  return card(entry,issue,1080,1350,out,name_size=104,read_lines=10,read_size=29,anchor="bottom")
