# -*- coding: utf-8 -*-
"""
프로모션 보드 + 청평댐 실시간(수위·방류량) 생성기
- 프로모션.png 를 배경으로, 하단 빈공간에 실시간 수위/방류량 패널을 그림
- 15분마다 이 스크립트를 돌려 board.png 를 덮어쓰면 자동 갱신 보드가 됨
필요: pip install requests pillow
"""
import os, sys
from datetime import datetime, timedelta
import requests
from PIL import Image, ImageDraw, ImageFont

# ── 설정 ──────────────────────────────────────────────
API_KEY  = os.environ.get("HRFCO_KEY", "여기에_발급받은_인증키")
DAM_CODE = os.environ.get("DAM_CODE", "1015310")          # 청평댐 (확인 완료)
BG_PATH  = os.environ.get("BG_PATH", "프로모션.png")       # 배경(스크립트와 같은 폴더)
OUT_PATH = os.environ.get("OUT_PATH", "board.png")
BASE     = "https://api.hrfco.go.kr"

# 색 (이미지 팔레트)
NAVY=(27,58,95); GREEN=(30,86,49); BLUE=(40,86,224); MAROON=(158,59,48)
INK=(34,40,56); GRAY=(120,130,150); LINE=(210,216,226); WHITE=(255,255,255)

def find_font(bold):
    cands = ([
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "C:/Windows/Fonts/malgunbd.ttf",
    ] if bold else [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/malgun.ttf",
    ])
    for p in cands:
        if os.path.exists(p):
            return p
    raise SystemExit("한글 폰트를 못 찾음. 나눔/맑은고딕/Noto 설치 필요.")

FONT_B = find_font(True)
FONT_R = find_font(False)
def F(p,s): return ImageFont.truetype(p,s)

# ── 데이터 ────────────────────────────────────────────
def fetch():
    import time
    now = datetime.now()
    sdt = (now - timedelta(hours=24)).strftime("%Y%m%d%H%M")
    edt = now.strftime("%Y%m%d%H%M")
    url = f"{BASE}/{API_KEY}/dam/list/10M/{DAM_CODE}/{sdt}/{edt}.json"
    headers = {"User-Agent": "Mozilla/5.0"}
    last_err = None
    for attempt in range(5):                       # 최대 5번까지 다시 시도
        try:
            resp = requests.get(url, timeout=60, headers=headers)   # 60초까지 기다림
            rows = resp.json().get("content", [])
            break
        except Exception as e:
            last_err = e
            print(f"시도 {attempt+1} 실패: {e} — 10초 후 재시도")
            time.sleep(10)
    else:
        raise SystemExit(f"5번 시도 모두 실패. 마지막 오류: {last_err}")
    out = []
    for r in rows:
        try:
            t = datetime.strptime(r["ymdhm"], "%Y%m%d%H%M")
        except Exception:
            continue
        def num(k):
            v = r.get(k)
            try: return float(v)
            except (TypeError, ValueError): return None
        out.append((t, num("swl"), num("tototf")))
    out.sort(key=lambda x: x[0])
    return out

# ── 그리기 ────────────────────────────────────────────
def rrect(d,box,r,fill=None,outline=None,width=1):
    d.rounded_rectangle(box,radius=r,fill=fill,outline=outline,width=width)

def draw(level, delta, discharge, updated, series):
    img = Image.open(BG_PATH).convert("RGB"); d = ImageDraw.Draw(img)
    W,H = img.size
    Px0,Px1 = 150, W-150; Py0 = 1990; band=200
    rrect(d,(Px0,Py0,Px1,Py0+band),30,fill=NAVY)
    d.text((Px0+70,Py0+band//2),"청평댐 실시간 현황",font=F(FONT_B,120),fill=WHITE,anchor="lm")
    d.text((Px1-60,Py0+band//2),f"기준시각  {updated}",font=F(FONT_R,72),fill=(200,212,230),anchor="rm")

    top=Py0+band+70; bot=H-120; gap=80; mid=(Px0+Px1)//2
    cardL=(Px0,top,mid-gap//2,bot); cardR=(mid+gap//2,top,Px1,bot)

    def card(box,label,accent,big,unit,sub=None,sub_color=GRAY,spark=None):
        x0,y0,x1,y1=box
        rrect(d,box,36,fill=WHITE,outline=LINE,width=4)
        d.rounded_rectangle((x0,y0,x0+26,y1),radius=13,fill=accent)
        d.text((x0+90,y0+70),label,font=F(FONT_B,96),fill=accent,anchor="lt")
        cy=(y0+y1)//2+40
        d.text(((x0+x1)//2-120,cy),big,font=F(FONT_B,360),fill=INK,anchor="mm")
        d.text(((x0+x1)//2+380,cy+60),unit,font=F(FONT_R,110),fill=GRAY,anchor="lm")
        if sub:
            d.text((x0+90,y1-110),sub,font=F(FONT_B,84),fill=sub_color,anchor="lt")
        if spark and len(spark)>1:
            sx0,sy0,sx1,sy1=x1-760,y1-230,x1-90,y1-90
            mn,mx=min(spark),max(spark); rng=(mx-mn) or 1
            pts=[(sx0+(sx1-sx0)*i/(len(spark)-1), sy1-(sy1-sy0)*(v-mn)/rng)
                 for i,v in enumerate(spark)]
            d.line(pts,fill=accent,width=8,joint="curve")
            d.ellipse((pts[-1][0]-16,pts[-1][1]-16,pts[-1][0]+16,pts[-1][1]+16),fill=accent)

    arrow="▲" if delta>0 else ("▼" if delta<0 else "―")
    sc = MAROON if delta>0 else (BLUE if delta<0 else GRAY)
    card(cardL,"실시간 수위",NAVY,f"{level:.2f}","EL.m",
         sub=f"{arrow} {abs(delta):.2f} m (전 시각 대비)",sub_color=sc,spark=series)
    dtxt = f"{discharge:,.0f}" if discharge is not None else "—"
    card(cardR,"실시간 방류량",GREEN,dtxt,"m³/s")
    img.save(OUT_PATH)
    print(f"saved {OUT_PATH}  수위 {level:.2f} / 방류 {dtxt} / {updated}")

def main():
    data = fetch()
    lv  = [(t,s) for t,s,_ in data if s is not None]
    if not lv:
        print("수위 데이터를 못 받음 (인증키/댐코드 확인)"); sys.exit(1)
    series=[s for _,s in lv]
    level=series[-1]; delta=series[-1]-series[-2] if len(series)>1 else 0.0
    discharge=next((q for t,s,q in reversed(data) if q is not None), None)
    updated=lv[-1][0].strftime("%Y-%m-%d %H:%M")
    draw(level,delta,discharge,updated,series)

if __name__=="__main__":
    main()
