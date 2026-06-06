from jqdata import *
import pandas as pd, numpy as np
CHECK_DATES = ["2024-03-12", "2024-03-13", "2024-03-15"]
IDX_CODE, IPO_DAYS, LIMIT_TOL = "000852.XSHG", 250, 0.02
CIRC_MIN, CIRC_MAX, MONEY_MIN, MONEY_MAX_BULL = 30.0, 500.0, 6e8, 20e8
def td(s): return pd.to_datetime(s).date()
def ds(d): return pd.to_datetime(d).strftime("%Y-%m-%d")
def prev_day(d):
    days=[pd.to_datetime(x).date() for x in get_all_trade_days()]; d=td(d) if isinstance(d,str) else d
    return days[days.index(d)-1]
def gp(codes,end,count=1,fields=None):
    if not codes: return pd.DataFrame()
    fields=fields or ["open","close","high_limit","money","volume"]
    df=get_price(codes,end_date=end,count=count,frequency="daily",fields=fields,
                 panel=False,fill_paused=False,skip_paused=False,fq=None)
    if df is None or len(df)==0: return pd.DataFrame()
    return df.reset_index() if "time" not in df.columns else df
def one(codes,end,fields=None):
    df=gp(codes,end,1,fields); return {} if df.empty else {r["code"]:r for _,r in df.iterrows()}
def mode(prev,fb=0):
    df=get_price(IDX_CODE,end_date=prev,count=65,frequency="daily",fields=["close"],panel=False,fq=None)
    a=np.asarray(df["close"],float) if df is not None and len(df) else np.array([])
    if len(a)<20 or (a[-1]-a[-20:].max())/a[-20:].max()<=-.12: return "bear"
    if len(a)<60: return "bear"
    ma20,ma60,price=a[-20:].mean(),a[-60:].mean(),a[-1]; above=int((a[-30:]>ma60).sum())
    if price<=ma60 and ma20<=ma60: return "bear"
    if price<=ma60 and ma20>ma60: return "cautious" if fb>0 else "bear"
    if above>=30*.66: return "bull"
    return "cautious" if fb>-.02 else "bear"
def first(day):
    p=prev_day(day); secs=get_all_securities(["stock"],date=p)
    codes=[s for s in secs.index if not s.startswith("688") and not s.startswith("8")]
    df=gp(codes,p,3,["close","high_limit"]); out=[]
    for c,sub in df.groupby("code"):
        sub=sub.sort_values("time")
        if len(sub)<3: continue
        cl=list(sub["close"].astype(float))[-3:]; hl=list(sub["high_limit"].astype(float))[-3:]
        if hl[-1]<=0 or abs(cl[-1]-hl[-1])>LIMIT_TOL: continue
        b=1
        if hl[-2]>0 and abs(cl[-2]-hl[-2])<=LIMIT_TOL:
            b=2
            if hl[-3]>0 and abs(cl[-3]-hl[-3])<=LIMIT_TOL: b=3
        if b==1: out.append(c)
    return out,secs
def v130(cands,prev):
    keep=[]
    for c in cands:
        try:
            m=get_price(c,start_date=ds(prev)+" 09:30:00",end_date=ds(prev)+" 15:00:00",
                        frequency="1m",fields=["close","high_limit"],panel=False)
            if m is None or len(m)==0: keep.append(c); continue
            if "time" in m.columns: m=m.set_index("time")
            hit=m["close"]>=m["high_limit"]-.001
            if not hit.any() or pd.to_datetime(m.index[hit][0]).time().hour<14: keep.append(c)
        except Exception: keep.append(c)
    return keep
def audit(day):
    day=td(day); p=prev_day(day); m=mode(p,0.0); open_hi=.095 if m=="bull" else .03
    fb,secs=first(day); ym=one(fb,p,["close","high_limit","money","volume"])
    q=query(valuation.code,valuation.circulating_market_cap).filter(
      valuation.circulating_market_cap>CIRC_MIN,valuation.circulating_market_cap<CIRC_MAX)
    vdf=get_fundamentals(q,date=p); caps=set(vdf["code"]) if vdf is not None and not vdf.empty else set()
    base=[]
    for c in fb:
        if c in secs.index:
            nm=secs.loc[c,"display_name"]
            if "ST" in nm or "st" in nm or (day-secs.loc[c,"start_date"]).days<IPO_DAYS: continue
        if c not in caps: continue
        r=ym.get(c)
        if r is None or float(r["money"])<MONEY_MIN: continue
        if m=="bull" and float(r["money"])>MONEY_MAX_BULL: continue
        avg=float(r["money"])/float(r["volume"])/float(r["close"])*1.1-1 if float(r["volume"])>0 and float(r["close"])>0 else 0
        if avg<.07: continue
        base.append(c)
    cands=v130(base,p); tm=one(cands,day,["open","close","high_limit"])
    rows=[]; buys=[]
    for c in cands:
        y=float(ym[c]["close"]); r=tm.get(c); reason="ok"; op=hl=opct=np.nan
        if r is None: reason="no_today"
        else:
            op,hl=float(r["open"]),float(r["high_limit"]); opct=op/y-1 if y>0 else np.nan
            if op<=0 or y<=0: reason="bad_price"
            elif op>=hl*.999: reason="open_limit"
            elif opct<0 or opct>open_hi: reason="open_pct"
        rows.append("%s:y=%.2f,op=%.2f,pct=%.2f%%,hl=%.2f,%s"%(c,y,op,opct*100 if opct==opct else np.nan,hl,reason))
        if reason=="ok": buys.append(c)
    print("%s prev=%s mode=%s open_hi=%.1f%% cands=%s"%(ds(day),ds(p),m,open_hi*100,"|".join(cands)))
    print("DETAIL="+" ; ".join(rows))
    print("BUY_TOP2="+"|".join(buys[:2]))
for d in CHECK_DATES: audit(d)
