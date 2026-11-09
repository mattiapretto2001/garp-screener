# 07/11: pannello point-in-time esteso (grandi USA + piccole/medie USA + resto del mondo).
# Per ogni societa': metriche GARP (world_04.features), segnali di prezzo e utile operativo (tune_01.extra), rendimenti
# trimestrali futuri (world_04.fwd_returns) e i campi nuovi: margine lordo, R&S, spese generali, attivo/passivo corrente,
# sorprese sugli utili (solo se gia' pubblicate alla data), eta' dalla quotazione.
# Bilanci: fund2.pkl (scaricati il 07/11, con i campi nuovi) se c'e', altrimenti fund.pkl (06/11).
import pickle, sys, warnings, pandas as pd, numpy as np
from world_common import *
from world_04_features import company, last_row, ttm_rows, features, fwd_returns, REB, TODAY, COVERED_OTHER
from tune_01_panel import extra
warnings.filterwarnings('ignore')


def extra2(fd, us, dates):
    R = company(fd, us)
    iq, iy, b = R.get('iq'), R.get('iy'), R.get('b')
    for X in (iq, iy):
        if X is None: continue
        for c in ['grossProfit', 'costOfRevenue', 'researchDevelopment', 'sellingGeneralAdministrative']:
            if c not in X: X[c] = np.nan
        X['gp'] = X.grossProfit.where(X.grossProfit.notna(), X.totalRevenue - X.costOfRevenue)
    if iq is not None:
        A = iy
        for c, tol in [('gp', 0.10), ('researchDevelopment', 0.15), ('sellingGeneralAdministrative', 0.15)]:
            v, bad, _ = ttm_rows(iq, c, A, tol=tol); v[bad] = np.nan; iq[c + '_ttm'] = v
    E = fd.get('earn'); ipo = pd.to_datetime((fd.get('gen') or {}).get('IPODate'), errors='coerce')
    if E is not None and len(E):
        E = E[E.epsActual.notna() & E.reportDate.notna()].copy()
    out = {}
    for t in dates:
        r = {}
        x = last_row(iq, t) if iq is not None else None
        y = last_row(iy, t) if iy is not None else None
        use_q = x is not None and not np.isnan(x.rev_ttm) and not np.isnan(x.ni_ttm) and (y is None or x.m >= y.m)
        if use_q:
            Q = iq.set_index('m'); m0 = int(x.m)
            r['gp_ttm'] = x.gp_ttm; r['rd_ttm'] = x.researchDevelopment_ttm; r['sga_ttm'] = x.sellingGeneralAdministrative_ttm
            p = Q.loc[m0 - 12] if (m0 - 12) in Q.index else None
            r['gp_ttm4'] = p.gp_ttm if p is not None else np.nan; r['rev_ttm4b'] = p.rev_ttm if p is not None else np.nan
        elif y is not None:
            Y = iy.set_index('m'); m0 = int(y.m)
            r['gp_ttm'] = y.gp; r['rd_ttm'] = y.researchDevelopment; r['sga_ttm'] = y.sellingGeneralAdministrative
            p = Y.loc[m0 - 12] if (m0 - 12) in Y.index else None
            r['gp_ttm4'] = p.gp if p is not None else np.nan; r['rev_ttm4b'] = p.totalRevenue if p is not None else np.nan
        bb = last_row(b, t) if b is not None else None
        if bb is not None:
            r['cur_a'] = bb.get('totalCurrentAssets', np.nan); r['cur_l'] = bb.get('totalCurrentLiabilities', np.nan)
        if E is not None and len(E):
            e = E[E.reportDate < t].tail(4)   # pubblicate prima della data
            if len(e) and (t - e.reportDate.iloc[-1]).days <= 200:
                s = e.surprisePercent.where(e.epsEstimate.abs() > 0.01)
                r['surp_last'] = s.iloc[-1]; r['surp_mean4'] = s.clip(-100, 100).mean(); r['n_beat4'] = (e.epsActual > e.epsEstimate).sum()
                r['n_est4'] = e.epsEstimate.notna().sum()
        if pd.notna(ipo): r['age_y'] = (t - ipo).days / 365.25
        out[t] = r
    return out


def proc(args):
    ex, codes, FD, DL = args
    P = pickle.load(open(f'{BASE}/eod/{ex}.pkl', 'rb'))
    rows, rets, meta = [], [], []
    for code in codes:
        t = f'{code}.{ex}'; fd = FD.get(t); px = P.get(code)
        if not fd or 'gen' not in fd or px is None or len(px) < 100: continue
        px = px[px.a > 0]
        if len(px) < 100: continue
        g = fd['gen']
        if ex == 'US' and g.get('CountryISO') in COVERED_OTHER: continue   # ADR / doppia quotazione
        us = ex == 'US'
        sector = g.get('Sector') or g.get('GicSector')
        cur_px = g.get('CurrencyCode') or ('GBX' if ex == 'LSE' else None)
        delisted = bool(DL.get(code, 0)) or bool(g.get('IsDelisted')) or px.index[-1] < TODAY - pd.Timedelta(days=30)
        meta.append(dict(t=t, ex=ex, region=REGION[ex], name=g.get('Name'), sector=sector, industry=g.get('Industry') or g.get('GicIndustry'),
                         country=g.get('CountryISO'), cur_px=cur_px, delisted=delisted, last_px=px.index[-1], isin=g.get('ISIN'),
                         new_fields='earn' in fd))
        try:
            fr = features(REB, fd, px, us, cur_px)
            need = [r['date'] for r in fr]
            e1 = extra(fd, px, us, need); e2 = extra2(fd, us, need)
        except Exception as e:
            print('errore', t, e, flush=True); continue
        for r in fr:
            r.update(e1.get(r['date'], {})); r.update(e2.get(r['date'], {})); r['t'] = t
        rows += fr
        for d, (rr, ld, ended) in fwd_returns(px, delisted).items(): rets.append((t, d, rr, ended))
    print(ex, len(codes), len(rows), flush=True)
    return rows, rets, meta


if __name__ == '__main__':
    from multiprocessing import Pool
    C = pd.concat([pd.read_csv(f'{BASE}/res/candidates.csv'), pd.read_csv(f'{BASE}/res/candidates_us2.csv')]).drop_duplicates('t')
    if len(sys.argv) > 2: C = C[C.ex.isin(sys.argv[2].split(','))].head(int(os.environ.get('NTEST', 10**6)))
    FD = pickle.load(open(f'{BASE}/fund/fund.pkl', 'rb'))
    F2 = pickle.load(open(os.environ.get('FUND2', f'{BASE}/fund/fund2.pkl'), 'rb'))
    FD.update({k: v for k, v in F2.items() if v and 'gen' in v})
    del F2
    print('bilanci', len(FD), flush=True)
    jobs = []
    for ex in C.ex.unique():
        s = symbols(ex); DL = dict(zip(s.Code, s.delisted))
        cs = list(C[C.ex == ex].code)
        for k in range(0, len(cs), 300):
            sub = cs[k:k + 300]
            jobs.append((ex, sub, {f'{c}.{ex}': FD.get(f'{c}.{ex}') for c in sub}, DL))
    del FD
    rows, rets, meta = [], [], []
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as P:
        for a, b, c in P.imap_unordered(proc, jobs): rows += a; rets += b; meta += c
    F = pd.DataFrame(rows); M = pd.DataFrame(meta); RQ = pd.DataFrame(rets, columns=['t', 'date', 'r', 'ended'])
    sfx = '' if len(sys.argv) <= 2 else '_test'
    F.to_pickle(f'{BASE}/res/feat2_raw{sfx}.pkl'); M.to_pickle(f'{BASE}/res/meta2{sfx}.pkl'); RQ.to_pickle(f'{BASE}/res/rq2{sfx}.pkl')
    print(F.shape, M.shape, RQ.shape)
