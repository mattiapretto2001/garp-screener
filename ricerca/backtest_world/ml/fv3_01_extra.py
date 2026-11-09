# fv3_01 (07/11): variabili in piu' per la matrice condivisa features_v3, calcolate point-in-time per ogni (titolo, data)
# gia' presente in res/panel2.pkl (universo: liquidita' alla data, >=300 M$, ricavi >0, doppioni tolti, pence corretti).
# Stesse regole di world_04/world_14: un bilancio vale solo dalla data prudente di pubblicazione (USA: deposito o chiusura+45 g;
# resto del mondo: max(deposito, chiusura+75 g); tetto 180 g), TTM da trimestri/semestri contigui controllati con l'annuale.
# Bilanci: fund.pkl (06/11) aggiornato con fund2.pkl (07/11, versione attuale). Prezzi: eod/<EX>.pkl (dal 2010). Nessuna chiamata EODHD.
import os, sys, pickle, warnings, pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); BT = os.path.dirname(HERE); sys.path.insert(0, BT)
from world_common import BASE
from world_04_features import company, last_row, ttm_rows, sh_at, clean, mi
warnings.filterwarnings('ignore')
SPLITS = np.array([2, 3, 4, 5, 10, 1.5, 0.5, 1 / 3, 0.25, 0.2, 0.1])


def nz(v):
    try:
        return float(v) if v is not None and pd.notna(v) else np.nan
    except Exception:
        return np.nan


def share_change(sh, m_new, m_old, split_at):
    """variazione delle azioni fra due mesi di bilancio, al netto dei frazionamenti visti nei prezzi"""
    a, b = sh_at(sh, m_new), sh_at(sh, m_old)
    if not (a > 0 and b > 0): return np.nan
    raw = a / b
    S = split_at(m_old, m_new)
    if S is not None and abs(np.log(S)) > 0.1 and abs(np.log(raw / S)) < abs(np.log(raw)): raw = raw / S
    elif S is None and np.min(np.abs(raw / SPLITS - 1)) < 0.02: return np.nan   # probabile frazionamento non visibile nei prezzi
    return raw - 1 if 0.25 <= raw <= 4 else np.nan


def extra3(fd, px, us, dates):
    R = company(fd, us)
    iq, iy, cq, cy, b, sh = R.get('iq'), R.get('iy'), R.get('cq'), R.get('cy'), R.get('b'), R.get('sh')
    for X in (iq, iy):
        if X is None: continue
        for c in ['ebitda', 'operatingIncome', 'grossProfit', 'costOfRevenue', 'researchDevelopment', 'sellingGeneralAdministrative']:
            if c not in X: X[c] = np.nan
        X['gp'] = X.grossProfit.where(X.grossProfit.notna(), X.totalRevenue - X.costOfRevenue)
    if iq is not None:
        for c, tol in [('ebitda', 0.15), ('operatingIncome', 0.15), ('gp', 0.10), ('researchDevelopment', 0.15), ('sellingGeneralAdministrative', 0.15)]:
            v, bad, _ = ttm_rows(iq, c, iy, tol=tol); v[bad] = np.nan; iq[c + '_ttm'] = v
    for X in (cq, cy):
        if X is None: continue
        X['cfo'] = X.totalCashFromOperatingActivities.astype(float)
        X['capex'] = X.capitalExpenditures.astype(float).abs()
    if cq is not None:
        for c in ['cfo', 'capex']:
            v, bad, _ = ttm_rows(cq, c, cy, tol=0.15); v[bad] = np.nan; cq[c + '_ttm'] = v
    if b is not None:
        for c in ['totalAssets', 'cash', 'cashAndShortTermInvestments', 'totalCurrentAssets', 'totalCurrentLiabilities']:
            if c not in b: b[c] = np.nan
        b = b.copy(); b['cashx'] = b.cashAndShortTermInvestments.where(b.cashAndShortTermInvestments.notna(), b.cash)
        Bm = b.set_index('m')
    if iy is not None:
        iy = iy.sort_values('m')
    Q = iq.set_index('m') if iq is not None else None
    E = fd.get('earn')
    if E is not None and len(E): E = E[E.epsActual.notna() & E.reportDate.notna()].copy()
    g = fd.get('gen') or {}
    ipo = pd.to_datetime(g.get('IPODate'), errors='coerce')
    first_y = iy.date.min() if iy is not None and len(iy) else pd.NaT
    # prezzi: valore scambiato = prezzo corretto solo per frazionamenti x volume (EODHD da' il volume gia' corretto per frazionamenti)
    aa, spx = clean(px)
    tv = (spx * px.v.astype(float)).values
    after = (px.c.astype(float) / spx).values           # fattore di frazionamento cumulato dopo ogni giorno
    pidx = px.index

    def split_at(m_old, m_new):
        d0, d1 = pd.Timestamp(year=m_old // 12, month=m_old % 12 + 1, day=1) + pd.offsets.MonthEnd(0), pd.Timestamp(year=m_new // 12, month=m_new % 12 + 1, day=1) + pd.offsets.MonthEnd(0)
        if d0 < pidx[0]: return None
        i0 = max(pidx.searchsorted(d0, side='right') - 1, 0); i1 = max(pidx.searchsorted(d1, side='right') - 1, 0)
        return after[i0] / after[i1]
    out = {}
    for t in dates:
        r = {}
        x = last_row(iq, t); y = last_row(iy, t)
        use_q = x is not None and not np.isnan(x.rev_ttm) and not np.isnan(x.ni_ttm) and (y is None or x.m >= y.m)
        if use_q:
            m0 = int(x.m)
            r.update(ebitda_ttm=x.ebitda_ttm, gp_ttm=x.gp_ttm, rd_ttm=x.researchDevelopment_ttm, sga_ttm=x.sellingGeneralAdministrative_ttm)
            p = Q.loc[m0 - 12] if (m0 - 12) in Q.index else None
            if isinstance(p, pd.DataFrame): p = p.iloc[-1]
            r['gp_ttm4'] = p.gp_ttm if p is not None else np.nan
            r['rev_ttm4b'] = p.rev_ttm if p is not None else np.nan
            r['fin_end'] = x.date; r['fin_av'] = x.av
        elif y is not None:
            m0 = int(y.m)
            r.update(ebitda_ttm=nz(y.ebitda), gp_ttm=nz(y.gp), rd_ttm=nz(y.researchDevelopment), sga_ttm=nz(y.sellingGeneralAdministrative))
            p = iy[iy.m == m0 - 12]; p = p.iloc[-1] if len(p) else None
            r['gp_ttm4'] = nz(p.gp) if p is not None else np.nan
            r['rev_ttm4b'] = nz(p.totalRevenue) if p is not None else np.nan
            r['fin_end'] = y.date; r['fin_av'] = y.av
        else:
            continue
        r['m0x'] = m0
        # flussi di cassa
        c1 = last_row(cq, t); c2 = last_row(cy, t)
        if c1 is not None and not np.isnan(c1.cfo_ttm) and (c2 is None or c1.m >= c2.m):
            r['cfo_ttm'] = c1.cfo_ttm; r['capex_ttm'] = c1.capex_ttm
        elif c2 is not None:
            r['cfo_ttm'] = nz(c2.cfo); r['capex_ttm'] = nz(c2.capex)
        # stato patrimoniale
        bb = last_row(b, t) if b is not None else None
        if bb is not None:
            r.update(ta=nz(bb.totalAssets), cash=nz(bb.cashx), cur_a=nz(bb.totalCurrentAssets), cur_l=nz(bb.totalCurrentLiabilities), bal_end=bb.date)
            mb = int(bb.m)
            if (mb - 12) in Bm.index:
                pb = Bm.loc[mb - 12]
                if isinstance(pb, pd.DataFrame): pb = pb.iloc[-1]
                r['ta4'] = nz(pb.totalAssets)
        # storia annuale (solo bilanci gia' pubblicati alla data)
        if iy is not None:
            Y = iy[iy.av <= t].drop_duplicates('m', keep='last').tail(11)
            if len(Y):
                rev = Y.totalRevenue.astype(float).values; ni = Y.ni.astype(float).values; op = Y.operatingIncome.astype(float).values
                gp = Y.gp.astype(float).values; mm = Y.m.values
                n10 = ni[-10:]; n5 = ni[-5:]
                k10, k5 = np.isfinite(n10).sum(), np.isfinite(n5).sum()
                r['n_years'] = int(np.isfinite(ni).sum())
                r['n_loss_5y'] = float((n5[np.isfinite(n5)] < 0).sum()) if k5 >= 3 else np.nan
                r['n_loss_10y'] = float((n10[np.isfinite(n10)] < 0).sum()) if k10 >= 5 else np.nan
                with np.errstate(all='ignore'):
                    om = np.where(rev > 0, op / rev, np.nan)[-5:]; gm = np.where(rev > 0, gp / rev, np.nan)[-5:]
                om = om[np.isfinite(om)]; gm = gm[np.isfinite(gm) & (gm > -1) & (gm < 0.999)]
                r['opm_std5'] = om.std(ddof=1) if len(om) >= 4 else np.nan
                r['opm_avg5'] = om.mean() if len(om) >= 4 else np.nan
                r['gm_std5'] = gm.std(ddof=1) if len(gm) >= 4 else np.nan
                Rm = dict(zip(mm, rev)); mlast = mm[-1]; vlast = rev[-1]
                for k in (3, 5):
                    v0 = Rm.get(mlast - 12 * k)
                    r[f'rev_cagr{k}'] = (vlast / v0) ** (1 / k) - 1 if (v0 is not None and v0 > 0 and vlast > 0) else np.nan
                gr = [Rm[m] / Rm[m - 12] - 1 for m in mm[-5:] if (m - 12) in Rm and Rm[m - 12] > 0 and np.isfinite(Rm[m])]
                r['revg_std5'] = np.std(gr, ddof=1) if len(gr) >= 4 else np.nan
                r['n_revdown_5y'] = float(sum(1 for z in gr if z < 0)) if len(gr) >= 4 else np.nan
        # azioni: variazione 1 e 3 anni fra mesi di bilancio gia' pubblicati (m0), corretta per frazionamenti
        if sh is not None and len(sh):
            r['dsh1'] = share_change(sh, m0, m0 - 12, split_at)
            r['dsh3'] = share_change(sh, m0, m0 - 36, split_at)
        # sorprese sugli utili: solo annunci gia' avvenuti
        if E is not None and len(E):
            e = E[E.reportDate < t].tail(4)
            if len(e) and (t - e.reportDate.iloc[-1]).days <= 200:
                s = e.surprisePercent.where(e.epsEstimate.abs() > 0.01)
                r['surp_last'] = s.iloc[-1]; r['surp_mean4'] = s.clip(-100, 100).mean(); r['n_beat4'] = float((e.epsActual > e.epsEstimate).sum())
                r['n_est4'] = float(e.epsEstimate.notna().sum())
        if pd.notna(ipo) and pd.Timestamp('1900-01-01') < ipo <= t: r['age_y'] = (t - ipo).days / 365.25
        if pd.notna(first_y) and first_y <= t: r['hist_y'] = (t - first_y).days / 365.25
        # prezzo: liquidita' (mediana 63 sedute del valore scambiato, valuta di quotazione) e rendimento dell'ultimo mese
        i = pidx.searchsorted(t, side='right')
        if i > 0 and (t - pidx[i - 1]).days <= 10:
            w = tv[max(0, i - 63):i]; w = w[np.isfinite(w) & (w > 0)]
            r['adv_loc'] = float(np.median(w)) if len(w) >= 20 else np.nan
            j = pidx.searchsorted(t - pd.Timedelta(days=30), side='right')
            if j > 0: r['mom1'] = aa.iloc[i - 1] / aa.iloc[j - 1] - 1
            j3 = pidx.searchsorted(t - pd.Timedelta(days=91), side='right')
            if j3 > 0: r['mom3'] = aa.iloc[i - 1] / aa.iloc[j3 - 1] - 1
        out[t] = r
    return out


def proc(args):
    ex, need, FD = args
    P = pickle.load(open(f'{BASE}/eod/{ex}.pkl', 'rb'))
    rows, err = [], 0
    for t, dates in need.items():
        code = t.rsplit('.', 1)[0]; fd = FD.get(t); px = P.get(code)
        if not fd or 'gen' not in fd or px is None: continue
        px = px[px.a > 0]
        if len(px) < 100: continue
        try:
            e = extra3(fd, px, ex == 'US', dates)
        except Exception as er:
            err += 1; print('errore', t, repr(er), flush=True); continue
        for d, r in e.items():
            r['t'] = t; r['date'] = d; rows.append(r)
    print(ex, len(need), len(rows), 'errori', err, flush=True)
    return rows


if __name__ == '__main__':
    from multiprocessing import Pool
    F = pd.read_pickle(f'{BASE}/res/panel2.pkl')[['t', 'date', 'ex']]
    if len(sys.argv) > 2: F = F[F.t.isin(F.t.drop_duplicates().sample(int(sys.argv[2]), random_state=1))]
    need = F.groupby('t').date.apply(lambda s: sorted(s)).to_dict()
    FD = pickle.load(open(f'{BASE}/fund/fund.pkl', 'rb'))
    F2 = pickle.load(open(f'{BASE}/fund/fund2.pkl', 'rb'))
    FD.update({k: v for k, v in F2.items() if v and 'gen' in v}); del F2
    jobs = []
    for ex in sorted(F.ex.unique()):
        ts = sorted(t for t in need if t.endswith('.' + ex))
        for k in range(0, len(ts), 250):
            sub = ts[k:k + 250]
            jobs.append((ex, {t: need[t] for t in sub}, {t: FD.get(t) for t in sub}))
    del FD
    rows = []
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as P:
        for a in P.imap_unordered(proc, jobs): rows += a
    X = pd.DataFrame(rows)
    sfx = '' if len(sys.argv) <= 2 else '_test'
    X.to_pickle(f'{HERE}/fv3_extra{sfx}.pkl')
    print(X.shape); print(X.notna().mean().round(3).to_string())
