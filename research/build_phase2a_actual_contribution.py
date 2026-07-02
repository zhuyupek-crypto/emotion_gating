from __future__ import annotations
import argparse, hashlib, json, math, subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
ACC=ROOT/'coordination'/'attribution'; PHASE2=ACC/'master_phase2a'; DETAIL=PHASE2/'full_detail'
INITIAL_VALUE=1000000.0; FINAL_VALUE=1258307.590000002; PORTFOLIO_NET_CHANGE=FINAL_VALUE-INITIAL_VALUE
BRANCHES=['Auction','YJJ','Scorpion','RZQ','ZB']; BLOCK_STATES={'SLOT_BLOCKED','CASH_BLOCKED','POSITION_BLOCKED','NOT_EVALUATED_AFTER_STOP'}
def git(*a):
    try: return subprocess.check_output(['git',*a],cwd=ROOT,text=True,encoding='utf-8',errors='replace').strip()
    except Exception: return 'unknown'
def sha_file(p:Path):
    h=hashlib.sha256();
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()
def wj(p,o): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(o,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def wc(p,df): p.parent.mkdir(parents=True,exist_ok=True); df.to_csv(p,index=False,encoding='utf-8-sig')
def wp(p,df):
    p.parent.mkdir(parents=True,exist_ok=True); x=df.copy()
    for c in x.columns:
        if x[c].dtype=='object': x[c]=x[c].map(lambda v: json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v)
    x.to_parquet(p,index=False)
def hcode(c): return str(c).replace('.XSHE','.SZ').replace('.XSHG','.SH')
def end_prices(codes,date='20231229'):
    p=Path(r'D:\work space\hdata\data\processed\1d_stock\2023.parquet')
    d=pd.read_parquet(p,columns=['date','code','close']); need={hcode(c) for c in codes}
    d=d[d.date.astype(str).eq(date)&d.code.isin(need)]
    return {str(r.code):round(float(r.close),2) for r in d.itertuples(index=False)}
def b(s): return s.fillna(False).astype(bool)
def signal_ledger(facts:Path):
    sig=pd.read_parquet(facts/'SIGNAL_EVENT.parquet'); oi=pd.read_parquet(facts/'ORDER_INTENT.parquet'); tr=pd.read_parquet(facts/'TRADE_OUTCOME.parquet')
    bo=oi[oi.side.eq('buy')&oi.signal_id.notna()]
    bt=tr[tr.actual_traded.fillna(False).astype(bool)]
    oa=bo.groupby('signal_id',dropna=False).agg(order_created=('order_returned','max'),order_id=('order_id',lambda x:';'.join(str(v) for v in x.dropna())))
    ta=bt.groupby('signal_id',dropna=False).agg(buy_filled=('actual_traded','max'),buy_trade_count=('trade_ids','count'),buy_amount=('entry_amount','sum'),buy_value=('entry_value','sum'),buy_commission=('commission','sum'))
    cols=['signal_id','trade_date','code','branch','signal_variant','market_mode','raw_market_mode','active_route','fb_pct','first_board_perf','raw_candidate_rank','final_candidate_rank','branch_candidate_count','handler_reached','candidate_loop_reached','handler_eligible','branch_eligible','qualified_for_ranking','participated_in_ranking','selected_for_order','terminal_state','terminal_reason_code']
    led=sig[cols].copy().merge(oa,how='left',left_on='signal_id',right_index=True).merge(ta,how='left',left_on='signal_id',right_index=True)
    led.order_created=led.order_created.fillna(False).astype(bool); led.buy_filled=led.buy_filled.fillna(False).astype(bool); led.order_id=led.order_id.fillna('')
    for c in ['buy_trade_count','buy_amount','buy_value','buy_commission']: led[c]=led[c].fillna(0)
    led['has_closed_outcome']=False; led['has_open_position_at_year_end']=False; led['evidence_scope']='PREPARED_PARENT_ONLY'; led['outcome_scope']='MASTER_ACTUAL'
    return led
def lifecycle(snapshot:Path,led:pd.DataFrame):
    facts=snapshot/'facts'; obs=snapshot/'observer'; oi=pd.read_parquet(facts/'ORDER_INTENT.parquet'); trades=pd.read_csv(obs/'trades.csv'); eq=pd.read_csv(obs/'equity.csv')
    tidx={d:i for i,d in enumerate(eq.date.astype(str))}; sig=led.set_index('signal_id').to_dict('index')
    buy_sig={str(int(r.order_id)):str(r.signal_id) for r in oi[oi.side.eq('buy')&oi.signal_id.notna()].itertuples(index=False)}
    prices=end_prices(set(trades.code.astype(str))); open_lots=defaultdict(list); lots=[]; n=0
    for r in trades.itertuples(index=False):
        amt=int(r.amount); code=str(r.code); oid=str(int(r.order_id)); tm=str(r.time)
        if amt>0:
            sid=buy_sig.get(oid)
            if not sid: raise SystemExit(f'buy order {oid} lacks signal lineage')
            s=sig[sid]; n+=1
            lot=dict(lot_id=f'lot_{n:04d}',signal_id=sid,branch=s['branch'],code=code,entry_date=tm.split()[0],entry_time=tm,entry_price=float(r.price),entry_amount=amt,entry_value=amt*float(r.price),entry_commission=float(r.commission),exit_status='OPEN',exit_date=None,exit_time=None,exit_price=None,exit_amount=0,exit_value=0.0,exit_commission=0.0,exit_tax=0.0,gross_pnl=0.0,net_pnl=0.0,return_on_entry_cost=None,holding_trading_days=None,market_mode_at_entry=s['market_mode'],active_route_at_entry=s['active_route'],terminal_state=s['terminal_state'],lifecycle_status='OPEN_AT_YEAR_END',remaining_amount=amt,entry_trade_id=str(r.trade_id),exit_trade_ids=[])
            lots.append(lot); open_lots[code].append(lot); continue
        rem=-amt
        for lot in list(open_lots[code]):
            if rem<=0: break
            take=min(rem,int(lot['remaining_amount'])); frac=take/(-amt); sale=take*float(r.price)
            lot['remaining_amount']-=take; lot['exit_amount']+=take; lot['exit_value']+=sale; lot['exit_commission']+=float(r.commission)*frac; lot['exit_tax']+=float(r.tax)*frac; lot['gross_pnl']+=sale-take*float(lot['entry_price']); lot['exit_time']=tm; lot['exit_date']=tm.split()[0]; lot['exit_price']=float(r.price); lot['exit_trade_ids'].append(str(r.trade_id)); rem-=take
            if int(lot['remaining_amount'])==0: lot['exit_status']='CLOSED'; open_lots[code].remove(lot)
        if rem: raise SystemExit(f'sell trade {r.trade_id} exceeds open lots for {code}')
    rows=[]
    for lot in lots:
        rem=int(lot.pop('remaining_amount')); sold_frac=(int(lot['entry_amount'])-rem)/int(lot['entry_amount']); open_frac=rem/int(lot['entry_amount'])
        ed=str(lot['entry_date']); xd=str(lot['exit_date']) if lot['exit_date'] else '2023-12-29'; hold=max(0,tidx.get(xd,tidx['2023-12-29'])-tidx.get(ed,0))
        closed_entry_fee=float(lot['entry_commission'])*sold_frac; net=float(lot['gross_pnl'])-closed_entry_fee-float(lot['exit_commission'])-float(lot['exit_tax'])
        px=prices.get(hcode(lot['code']),math.nan) if rem else None; mtm=0.0 if not rem else rem*px; open_cost=rem*float(lot['entry_price'])+float(lot['entry_commission'])*open_frac
        status='CLOSED' if rem==0 else ('OPEN_AT_YEAR_END' if lot['exit_amount']==0 else 'PARTIALLY_OPEN_AT_YEAR_END')
        lot.update(exit_trade_ids=';'.join(lot['exit_trade_ids']),exit_status='CLOSED' if rem==0 else 'OPEN_AT_YEAR_END',exit_amount=int(lot['exit_amount']),gross_pnl=round(float(lot['gross_pnl']),10),net_pnl=round(net,10),return_on_entry_cost=(round(net/(float(lot['entry_value'])*sold_frac+closed_entry_fee),10) if sold_frac else None),holding_trading_days=hold,lifecycle_status=status,remaining_amount_at_year_end=rem,mark_to_market_price=px,mark_to_market_value=mtm,unrealized_gross_pnl=mtm-rem*float(lot['entry_price']),unrealized_net_pnl=mtm-open_cost,valuation_scope='PERIOD_END_MARK' if rem else None)
        rows.append(lot)
    return pd.DataFrame(rows)
def reconcile(lc):
    closed_gross=float(lc.gross_pnl.sum()); comm=float(lc.entry_commission.sum()+lc.exit_commission.sum()); tax=float(lc.exit_tax.sum()); closed_net=float(lc.net_pnl.sum())
    open_cost=float((lc.remaining_amount_at_year_end*lc.entry_price+lc.entry_commission*(lc.remaining_amount_at_year_end/lc.entry_amount)).sum()); open_mv=float(lc.mark_to_market_value.sum()); open_un=float(lc.unrealized_net_pnl.sum())
    attr=closed_net+open_un; resid=PORTFOLIO_NET_CHANGE-attr
    return dict(initial_value=INITIAL_VALUE,final_value=FINAL_VALUE,portfolio_net_change=PORTFOLIO_NET_CHANGE,closed_gross_pnl=closed_gross,closed_commission=comm,closed_tax=tax,closed_net_pnl=closed_net,open_position_cost=open_cost,open_position_market_value=open_mv,open_unrealized_pnl=open_un,attributed_net_change=attr,reconciliation_residual=resid,reconciliation_pass=abs(resid)<=0.01)
def branch_table(led,lc):
    rows=[]
    for br in BRANCHES:
        s=led[led.branch.eq(br)]; lots=lc[lc.branch.eq(br)]; closed=lots[lots.lifecycle_status.eq('CLOSED')]; total=float(lots.net_pnl.sum()+lots.unrealized_net_pnl.sum())
        rows.append(dict(branch=br,prepared_signal_count=len(s),filled_signal_count=int(s.buy_filled.sum()),buy_fill_rate=float(s.buy_filled.mean()) if len(s) else 0,closed_lot_count=len(closed),year_end_open_lot_count=int((lots.lifecycle_status!='CLOSED').sum()),gross_pnl=float(lots.gross_pnl.sum()),commission=float(lots.entry_commission.sum()+lots.exit_commission.sum()),tax=float(lots.exit_tax.sum()),closed_net_pnl=float(lots.net_pnl.sum()),open_unrealized_pnl=float(lots.unrealized_net_pnl.sum()),total_actual_contribution=total,contribution_share_of_portfolio_net_change=total/PORTFOLIO_NET_CHANGE,closed_win_count=int((closed.net_pnl>0).sum()),closed_loss_count=int((closed.net_pnl<0).sum()),closed_win_rate=float((closed.net_pnl>0).mean()) if len(closed) else None,average_closed_return=float(closed.return_on_entry_cost.mean()) if len(closed) else None,median_closed_return=float(closed.return_on_entry_cost.median()) if len(closed) else None,average_holding_days=float(closed.holding_trading_days.mean()) if len(closed) else None,median_holding_days=float(closed.holding_trading_days.median()) if len(closed) else None))
    return pd.DataFrame(rows)
def monthly(led,lc):
    rows=[]
    for scope in ['ENTRY_COHORT','REALIZATION_MONTH']:
        for br in BRANCHES:
            s=led[led.branch.eq(br)].copy(); s['month']=s.trade_date.astype(str).str[:7]; lots=lc[lc.branch.eq(br)].copy(); months=sorted(set(s.month)|set(lots.entry_date.astype(str).str[:7]))
            key=lots.entry_date.astype(str).str[:7] if scope=='ENTRY_COHORT' else lots.exit_date.fillna('2023-12-29').astype(str).str[:7]
            for m in months:
                sel=lots[key.eq(m)]; cl=sel[sel.lifecycle_status.eq('CLOSED')]
                rows.append(dict(scope=scope,month=m,branch=br,prepared_signals=int((s.month==m).sum()),filled_signals=int((s.month.eq(m)&s.buy_filled).sum()),closed_net_pnl=float(sel.net_pnl.sum()),open_mark_change=float(sel.unrealized_net_pnl.sum()),total_actual_contribution=float(sel.net_pnl.sum()+sel.unrealized_net_pnl.sum()),win_rate=float((cl.net_pnl>0).mean()) if len(cl) else None,average_holding_days=float(cl.holding_trading_days.mean()) if len(cl) else None))
    return pd.DataFrame(rows)
def dim(lc,col,name):
    rows=[]
    for (br,v),g in lc.groupby(['branch',col],dropna=False): rows.append(dict(branch=br,**{name:v},state_scope='MOTHERBOARD_ACTUAL_ENTRY_STATE',lot_count=len(g),closed_net_pnl=float(g.net_pnl.sum()),open_unrealized_pnl=float(g.unrealized_net_pnl.sum()),total_actual_contribution=float(g.net_pnl.sum()+g.unrealized_net_pnl.sum())))
    return pd.DataFrame(rows)
def funnels(led):
    rows=[]
    for br in BRANCHES:
        s=led[led.branch.eq(br)]; rows.append(dict(branch=br,prepared=len(s),handler_reached=int(b(s.handler_reached).sum()),candidate_loop_reached=int(b(s.candidate_loop_reached).sum()),handler_eligible=int(b(s.handler_eligible).sum()),branch_eligible=int(b(s.branch_eligible).sum()),qualified_for_ranking=int(b(s.qualified_for_ranking).sum()),participated_in_ranking=int(b(s.participated_in_ranking).sum()),selected_for_order=int(b(s.selected_for_order).sum()),filled=int(b(s.buy_filled).sum())))
    return led.groupby(['branch','terminal_state'],dropna=False).size().reset_index(name='count'),pd.DataFrame(rows),led.groupby(['branch','terminal_state','terminal_reason_code'],dropna=False).size().reset_index(name='count')
def blocks(led,facts):
    snaps=pd.read_parquet(facts/'HANDLER_RESOURCE_SNAPSHOT.parquet').sort_values(['date','time']).groupby('date',dropna=False).tail(1).set_index('date')
    pos=pd.read_parquet(facts/'POSITION_BLOCK_AUDIT.parquet') if (facts/'POSITION_BLOCK_AUDIT.parquet').exists() else pd.DataFrame(); posd=pos.set_index('signal_id').to_dict('index') if len(pos) else {}
    rows=[]
    for r in led[led.terminal_state.isin(BLOCK_STATES)].itertuples(index=False):
        sn=snaps.loc[r.trade_date] if r.trade_date in snaps.index else None; status='EXPLICIT' if r.signal_id in posd else 'RESOURCE_STATE_ONLY'; reason=posd.get(r.signal_id,{}).get('reason_code',r.terminal_reason_code)
        rows.append(dict(trade_date=r.trade_date,time=None,signal_id=r.signal_id,branch=r.branch,code=r.code,terminal_state=r.terminal_state,reason_code=reason,available_cash=None if sn is None else float(sn.available_cash),locked_cash=None if sn is None else float(sn.locked_cash),positions_count=None if sn is None else int(sn.positions_count),branch_slots_total=None,branch_slots_used=None,branch_slots_remaining=None,blocking_signal_id=None,blocking_branch=None,blocking_code=None,blocking_order_id=None,blocker_identity_status=status))
    ev=pd.DataFrame(rows); summ=ev.groupby(['branch','terminal_state','reason_code','blocker_identity_status'],dropna=False).size().reset_index(name='count') if len(ev) else pd.DataFrame()
    return ev,summ
def overlaps(led):
    rows=[]
    for (d,c),g in led.groupby(['trade_date','code']):
        br=sorted(g.branch.dropna().unique())
        if len(br)>1:
            filled=sorted(g[g.buy_filled].branch.unique()); rows.append(dict(trade_date=d,code=c,branch_count=len(br),branches=';'.join(br),signal_ids=';'.join(g.signal_id.astype(str)),terminal_states=';'.join(g.terminal_state.astype(str)),filled_branch=';'.join(filled),multiple_filled_flag=len(filled)>1))
    ov=pd.DataFrame(rows); mx=[]
    for i,a in enumerate(BRANCHES):
        for b2 in BRANCHES[i+1:]:
            pair=ov[ov.branches.map(lambda x: a in x.split(';') and b2 in x.split(';'))] if len(ov) else pd.DataFrame(); filled=pair.filled_branch.astype(str).map(bool) if len(pair) else pd.Series(dtype=bool)
            mx.append(dict(branch_a=a,branch_b=b2,overlap_date_code_count=len(pair),at_least_one_filled_count=int(filled.sum()) if len(pair) else 0,both_not_filled_count=int((~filled).sum()) if len(pair) else 0))
    return ov,pd.DataFrame(mx)
def daily(led,snapshot):
    st=pd.read_csv(snapshot/'observer'/'state_snapshots.csv').set_index('date'); rows=[]
    for (d,br),g in led.groupby(['trade_date','branch']):
        s=st.loc[d] if d in st.index else None; rows.append(dict(trade_date=d,branch=br,prepared_count=len(g),eligible_count=int(b(g.branch_eligible).sum()),selected_count=int(b(g.selected_for_order).sum()),filled_count=int(b(g.buy_filled).sum()),slot_blocked_count=int(g.terminal_state.eq('SLOT_BLOCKED').sum()),cash_blocked_count=int(g.terminal_state.eq('CASH_BLOCKED').sum()),position_blocked_count=int(g.terminal_state.eq('POSITION_BLOCKED').sum()),start_available_cash=None if s is None else float(s.available_cash),end_available_cash=None if s is None else float(s.available_cash),start_positions=None if s is None else int(s.positions_count),end_positions=None if s is None else int(s.positions_count)))
    return pd.DataFrame(rows)
def curve(lc,snapshot):
    dates=list(pd.read_csv(snapshot/'observer'/'equity.csv').date.astype(str)); rows=[]
    for br in BRANCHES:
        cum=0.0; lots=lc[lc.branch.eq(br)]
        for d in dates:
            cl=lots[lots.exit_date.fillna('').astype(str).eq(d)]; op=lots[(lots.entry_date.astype(str).eq(d))&(lots.lifecycle_status!='CLOSED')]
            real=float(cl.gross_pnl.sum()); fees=-float(cl.entry_commission.sum()+cl.exit_commission.sum()+cl.exit_tax.sum()+op.entry_commission.sum()); mark=float(op.unrealized_gross_pnl.sum()); total=real+fees+mark; cum+=total
            rows.append(dict(branch=br,date=d,realized_pnl_today=real,mark_to_market_change_today=mark,fees_today=fees,total_pnl_today=total,cumulative_actual_contribution=cum))
    return pd.DataFrame(rows)
def validate(led,lc,recon):
    issues=[]
    if len(led)!=2524: issues.append(f'SIGNAL_EVENT rows {len(led)} != 2524')
    if led.signal_id.duplicated().any(): issues.append('signal_id is not unique')
    if int(led.terminal_state.eq('UNRESOLVED').sum())!=0: issues.append('UNRESOLVED exists')
    if int(led.branch.isna().sum())!=0: issues.append('branch null exists')
    if int(led.terminal_state.isna().sum())!=0: issues.append('terminal_state null exists')
    if len(lc)!=int(led.buy_filled.sum()): issues.append('buy-filled signal count and lifecycle lot count diverge')
    if not recon['reconciliation_pass']: issues.append(f"reconciliation residual {recon['reconciliation_residual']} exceeds 0.01")
    return issues
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input-snapshot',default=str(PHASE2/'input_snapshot')); a=ap.parse_args(); snap=Path(a.input_snapshot).resolve(); facts=snap/'facts'; PHASE2.mkdir(parents=True,exist_ok=True); DETAIL.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((PHASE2/'INPUT_SNAPSHOT_MANIFEST.json').read_text(encoding='utf-8')); led=signal_ledger(facts); lc=lifecycle(snap,led); led.loc[led.signal_id.isin(set(lc[lc.lifecycle_status.eq('CLOSED')].signal_id)),'has_closed_outcome']=True; led.loc[led.signal_id.isin(set(lc[lc.lifecycle_status.ne('CLOSED')].signal_id)),'has_open_position_at_year_end']=True
    recon=reconcile(lc); term,dec,reason=funnels(led); be,bs=blocks(led,facts); ov,om=overlaps(led); cv=curve(lc,snap); br=branch_table(led,lc); mon=monthly(led,lc); mk=dim(lc,'market_mode_at_entry','market_mode'); rt=dim(lc,'active_route_at_entry','active_route'); dy=daily(led,snap); issues=validate(led,lc,recon); concl='PASS_ACTUAL_BASELINE' if not issues else 'PARTIAL_ACCOUNTING_GAP'
    for name,df in [('MASTER_ACTUAL_SIGNAL_LEDGER',led),('TRADE_LIFECYCLE_LEDGER',lc),('RESOURCE_BLOCK_EVENT',be),('CROSS_BRANCH_SIGNAL_OVERLAP',ov),('BRANCH_ACTUAL_PNL_CURVE',cv)]: wp(DETAIL/f'{name}.parquet',df)
    wj(PHASE2/'PORTFOLIO_PNL_RECONCILIATION.json',recon); wc(PHASE2/'BRANCH_ACTUAL_CONTRIBUTION.csv',br); wc(PHASE2/'BRANCH_MONTHLY_ACTUAL_CONTRIBUTION.csv',mon); wc(PHASE2/'BRANCH_MARKET_MODE_CONTRIBUTION.csv',mk); wc(PHASE2/'BRANCH_ACTIVE_ROUTE_CONTRIBUTION.csv',rt); wc(PHASE2/'BRANCH_TERMINAL_FUNNEL.csv',term); wc(PHASE2/'BRANCH_DECISION_FUNNEL.csv',dec); wc(PHASE2/'BRANCH_BLOCK_REASON_MATRIX.csv',reason); wc(PHASE2/'RESOURCE_BLOCK_SUMMARY.csv',bs); wc(PHASE2/'CROSS_BRANCH_OVERLAP_MATRIX.csv',om); wc(PHASE2/'DAILY_BRANCH_RESOURCE_SUMMARY.csv',dy)
    (PHASE2/'ACTUAL_CONTRIBUTION_LIMITATIONS.md').write_text('# ACTUAL_CONTRIBUTION_LIMITATIONS\n\n- Phase 2A is MASTER_ACTUAL only.\n- It is not an independent branch alpha, bare branch return, or counterfactual result.\n- No future return is calculated for unfilled candidates.\n- No fixed-N-day proxy return is used.\n- Market mode and active route are motherboard actual entry states.\n- The contribution curve is not an independently funded branch NAV.\n',encoding='utf-8')
    rm=dict(phase='Phase 2A',conclusion=concl,created_at_utc=datetime.now(timezone.utc).isoformat(),git_commit=git('rev-parse','HEAD'),input_snapshot_manifest_sha256=sha_file(PHASE2/'INPUT_SNAPSHOT_MANIFEST.json'),signal_event_count=len(led),actual_order_count=len(pd.read_csv(snap/'observer'/'orders.csv')),actual_trade_record_count=len(pd.read_csv(snap/'observer'/'trades.csv')),buy_lot_count=len(lc),year_end_open_lot_count=int((lc.lifecycle_status!='CLOSED').sum()),unfilled_candidate_future_return_calculation_count=0,counterfactual_run_count=0,optimization_experiment_count=0,validation_issues=issues)
    wj(PHASE2/'RUN_MANIFEST.json',rm); h=manifest['canonical_2023_stable_business_hashes']; lines=['# Phase 2A Report','',f'Conclusion: `{concl}`','','`MASTER_ACTUAL_CONTRIBUTION_BASELINE`: actual 2023 motherboard contribution and resource competition only.','','## Input Identity',f"- signal hash: `{h['signal_key_sha256']}`",f"- terminal hash: `{h['terminal_state_sha256']}`",f"- source hash: `{h['source_mode_sha256']}`",f"- observer contract: `{manifest.get('observer_contract_version')}`",'','## Accounting',f'- SIGNAL_EVENT: `{len(led)}`',f"- actual orders/trades: `{rm['actual_order_count']}` / `{rm['actual_trade_record_count']}`",f"- buy lots: `{len(lc)}`; year-end open lots: `{rm['year_end_open_lot_count']}`",f"- portfolio net change: `{recon['portfolio_net_change']:.6f}`",f"- attributed net change: `{recon['attributed_net_change']:.6f}`",f"- reconciliation residual: `{recon['reconciliation_residual']:.6f}`",'','## Branch ACTUAL_CONTRIBUTION']
    for r in br.itertuples(index=False): lines.append(f'- {r.branch}: `{r.total_actual_contribution:.6f}` from `{r.filled_signal_count}` filled signals')
    lines += ['','## Boundary','Can answer: actual branch PnL, actual opportunity occupation, terminal/resource states, overlaps, months, and motherboard states.','Cannot answer yet: branch native alpha, gate/no-gate value, unlimited resources, alternative handler order, or remove-one-branch effects.','No unfilled candidate future returns, counterfactual records, optimization experiments, or bare-branch runs are included.']
    (PHASE2/'PHASE2A_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
if __name__=='__main__': main()

