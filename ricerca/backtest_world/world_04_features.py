# Fase 4: metriche point-in-time a ogni fine trimestre + rendimenti del trimestre successivo.
# Regole: dato usabile solo dalla data prudente di pubblicazione; TTM da trimestri o semestri contigui,
# controllati contro il bilancio annuale; se i trimestrali non tornano si usa l'annuale.
import pickle, sys, warnings, pandas as pd, numpy as np
from world_common import *
warnings.filterwarnings('ignore')
TODAY = pd.Timestamp('2026-11-06')
REB = list(pd.date_range('2011-12-31', '2026-09-30', freq='QE'))
FX = pd.read_pickle(f'{BASE}/eod/fx.pkl').sort_index().ffill()
EXCL_S = {'Financial Services', 'Financial', 'Financials', 'Basic Materials', 'Materials', 'Energy', 'Utilities', 'Real Estate'}
COVERED_OTHER = {'DE', 'FR', 'NL', 'ES', 'BE', 'CH', 'SE', 'DK', 'FI', 'NO', 'GB', 'JE', 'GG', 'IM', 'CA', 'TW', 'KR', 'AU'}


def mi(d): d = d + pd.Timedelta(days=16); return d.year * 12 + d.month - 2   # mese di chiusura (indice), tollera 52-53 settimane
def m2ts(m): return pd.Timestamp(year=m // 12, month=m % 12 + 1, day=1) + pd.offsets.MonthEnd(0)


def avail(dates, filing, us):
    f = pd.to_datetime(filing)
    if us:
        a = np.where(f > dates, f, dates + pd.Timedelta(days=45))
    else:
        a = np.maximum(f.fillna(dates), dates + pd.Timedelta(days=75))
    a = pd.to_datetime(a)
    return pd.Series(np.minimum(a, dates + pd.Timedelta(days=180)), index=dates.index)  # date di deposito assurde (riedizioni): tetto a 6 mesi


def fxv(cur, t):
    c = cur if cur in FX.columns else None
    if c is None: return np.nan
    i = FX.index.searchsorted(t, side='right') - 1
    return FX[c].iloc[max(i, 0)]


def prep(tab, cols, us):
    """righe pulite: indice mese, disponibilita', copertura in mesi, valori"""
    if tab is None or tab.empty: return None
    x = tab.copy()
    x = x[x[cols].notna().any(axis=1)]
    if x.empty: return None
    x['m'] = x.date.map(mi)
    x['nn'] = x[cols].notna().sum(axis=1)
    x = x.sort_values(['m', 'nn', 'date']).groupby('m').tail(1).reset_index(drop=True)   # doppioni (es. 30/3 e 31/3)
    x['av'] = avail(x.date, x.filing_date, us).values
    g = x.m.diff()
    typ = g[g.isin([3, 6])].mode()
    typ = int(typ.iloc[0]) if len(typ) else 3
    cov = g.where(g.isin([3, 6, 12]), typ)
    cov.iloc[0] = typ
    x['cv'] = cov.astype(int)
    return x


def ttm_rows(x, col, annual=None, tol=0.05):
    """per ogni riga: somma su 12 mesi contigui (NaN se buchi), valore stesso periodo un anno prima, e controllo con l'annuale"""
    m = x.m.values; cov = x['cv'].values; v = x[col].values.astype(float)
    pos = {mm: i for i, mm in enumerate(m)}
    ttm = np.full(len(x), np.nan)
    for i in range(len(x)):
        s, tot, j, ok = 0.0, 0, i, True
        while True:
            if np.isnan(v[j]): ok = False; break
            s += v[j]; tot += cov[j]
            if tot >= 12: break
            j = pos.get(m[j] - cov[j], -1)
            if j < 0: ok = False; break
        if ok and tot == 12: ttm[i] = s
    bad = np.zeros(len(x), bool)
    if annual is not None and col in annual:
        A = dict(zip(annual.m, annual[col]))
        for i in range(len(x)):
            a = A.get(m[i])
            if a is not None and not np.isnan(a) and not np.isnan(ttm[i]):
                if abs(ttm[i] - a) > tol * max(abs(a), 1e-9):
                    # righe della finestra non affidabili
                    for k in range(len(x)):
                        if m[i] - 12 < m[k] <= m[i]: bad[k] = True
    q_prev = np.array([v[pos[mm - 12]] if (mm - 12) in pos and cov[pos[mm - 12]] == c else np.nan for mm, c in zip(m, cov)])
    return ttm, bad, q_prev


def company(fd, us):
    out = {}
    inc_y = prep(fd.get('inc_y'), ['totalRevenue', 'netIncome'], us)
    cf_y = prep(fd.get('cf_y'), ['totalCashFromOperatingActivities', 'freeCashFlow'], us)
    if inc_y is not None: inc_y['cv'] = 12
    # ---- conto economico trimestrale/semestrale
    iq = prep(fd.get('inc_q'), ['totalRevenue', 'netIncome'], us)
    R = {}
    if iq is not None:
        iq['ni'] = iq.netIncome.fillna(iq.netIncomeApplicableToCommonShares)
        A = inc_y.assign(ni=inc_y.netIncome) if inc_y is not None else None
        tr, b1, qr = ttm_rows(iq, 'totalRevenue', A)
        tn, b2, qn = ttm_rows(iq, 'ni', A, tol=0.10)
        bad = b1 | b2
        tr[bad] = np.nan; tn[bad] = np.nan
        iq['rev_ttm'] = tr; iq['ni_ttm'] = tn; iq['rev_qp'] = qr; iq['ni_qp'] = qn
        R['iq'] = iq
    if inc_y is not None:
        inc_y['ni'] = inc_y.netIncome.fillna(inc_y.netIncomeApplicableToCommonShares)
        R['iy'] = inc_y
    cq = prep(fd.get('cf_q'), ['totalCashFromOperatingActivities', 'freeCashFlow'], us)
    if cq is not None:
        cq['fcf'] = cq.freeCashFlow.fillna(cq.totalCashFromOperatingActivities - cq.capitalExpenditures.astype(float).abs())
        Ay = None
        if cf_y is not None:
            cf_y['fcf'] = cf_y.freeCashFlow.fillna(cf_y.totalCashFromOperatingActivities - cf_y.capitalExpenditures.astype(float).abs())
            Ay = cf_y
        tf, bf, _ = ttm_rows(cq, 'fcf', Ay, tol=0.15)
        tf[bf] = np.nan; cq['fcf_ttm'] = tf; R['cq'] = cq
    if cf_y is not None and 'fcf' not in cf_y:
        cf_y['fcf'] = cf_y.freeCashFlow.fillna(cf_y.totalCashFromOperatingActivities - cf_y.capitalExpenditures.astype(float).abs())
    R['cy'] = cf_y
    bq = prep(fd.get('bal_q'), ['totalStockholderEquity'], us)
    by = prep(fd.get('bal_y'), ['totalStockholderEquity'], us)
    R['b'] = pd.concat([z for z in (bq, by) if z is not None]).sort_values(['m', 'nn']).groupby('m').tail(1) if (bq is not None or by is not None) else None
    sh = fd.get('sh')
    if sh is not None and len(sh):
        sh = pd.to_numeric(sh, errors='coerce').dropna(); sh = sh[sh > 0]
        sh.index = [mi(d) for d in sh.index]; sh = sh[~sh.index.duplicated(keep='last')].sort_index()
    if (sh is None or not len(sh)) and R['b'] is not None:
        s2 = R['b'].set_index('m').commonStockSharesOutstanding.dropna(); sh = s2[s2 > 0]
    R['sh'] = sh
    return R


def last_row(x, t):
    if x is None: return None
    y = x[x.av <= t]
    if y.empty: return None
    return y.iloc[int(np.argmax(y.m.values))]


def sh_at(sh, m):
    if sh is None or not len(sh): return np.nan
    s = sh[sh.index <= m]
    return s.iloc[-1] if len(s) and m - s.index[-1] <= 6 else np.nan


def clean(d):
    """serie pulita: (prezzo corretto per dividendi e frazionamenti, prezzo corretto solo per frazionamenti).
    Errori tipici EODHD: salti del solo prezzo 'adjusted' (corretto male) e picchi di un giorno che rientrano."""
    c = d.c.astype(float); a = d.a.astype(float)
    ra = (a / a.shift(1)).fillna(1.0); rc = (c / c.shift(1)).fillna(1.0)
    la = np.abs(np.log(ra.clip(1e-6))); lc = np.abs(np.log(rc.clip(1e-6)))
    glitch = (la > 0.4) & (lc < 0.15)
    split = (lc > 0.25) & (la < 0.15)
    r = ra.where(~glitch, rc).values.copy()
    lr = np.log(np.clip(r, 1e-6, None))
    cc = c.values.copy()
    for k in range(1, len(r) - 1):   # picco di un giorno che rientra il giorno dopo
        if abs(lr[k]) > 0.4 and abs(lr[k + 1]) > 0.4 and abs(lr[k] + lr[k + 1]) < 0.2:
            r[k] = r[k] * r[k + 1]; r[k + 1] = 1.0; lr[k] = np.log(max(r[k], 1e-6)); lr[k + 1] = 0.0
            cc[k] = cc[k - 1]; split.iloc[k] = False; split.iloc[k + 1] = False
    aa = pd.Series(np.cumprod(r), index=d.index)
    f = pd.Series(1.0, index=d.index); f[split] = (ra / rc)[split]
    after = f[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
    return aa, pd.Series(cc, index=d.index) / after


def features(t_list, fd, px, us, cur_px):
    R = company(fd, us)
    _, spx = clean(px)
    rows = []
    for t in t_list:
        r = {'date': t}
        a = px.a[px.index <= t]
        if not len(a) or (t - a.index[-1]).days > 10: continue
        r['px'] = float(spx[spx.index <= t].iloc[-1])
        iq = last_row(R.get('iq'), t); iy = last_row(R.get('iy'), t)
        # scelta della fonte: trimestrale/semestrale se valida e non piu' vecchia dell'annuale
        use_q = iq is not None and not np.isnan(iq.rev_ttm) and not np.isnan(iq.ni_ttm) and (iy is None or iq.m >= iy.m)
        if use_q:
            m0 = int(iq.m); q = R['iq']; p = q[(q.m == m0 - 12)]
            p = p.iloc[0] if len(p) else None
            r.update(src='Q', m0=m0, cov=int(iq.cv), rev_ttm=iq.rev_ttm, ni_ttm=iq.ni_ttm, rev_q=iq.totalRevenue, rev_qp=iq.rev_qp,
                     ni_q=iq.ni, ni_qp=iq.ni_qp, ni_ttm4=p.ni_ttm if p is not None else np.nan, cur=iq.cur)
        elif iy is not None:
            m0 = int(iy.m); y = R['iy']; p = y[y.m == m0 - 12]; p = p.iloc[0] if len(p) else None
            r.update(src='Y', m0=m0, cov=12, rev_ttm=iy.totalRevenue, ni_ttm=iy.ni, rev_q=iy.totalRevenue,
                     rev_qp=p.totalRevenue if p is not None else np.nan, ni_q=iy.ni, ni_qp=p.ni if p is not None else np.nan,
                     ni_ttm4=p.ni if p is not None else np.nan, cur=iy.cur)
        else:
            continue
        if mi(t) - r['m0'] > (15 if r['src'] == 'Y' else 9): continue  # dati troppo vecchi
        # crescita ricavi pluriennale dall'annuale: 4 anni se c'e', altrimenti 3
        if iy is not None:
            y = R['iy'].set_index('m').totalRevenue
            for k in (4, 3):
                v0 = y.get(int(iy.m) - 12 * k)
                if v0 is not None and v0 > 0 and iy.totalRevenue > 0:
                    r['rev_cagr'] = (iy.totalRevenue / v0) ** (1 / k) - 1; break
        # FCF TTM
        cq = last_row(R.get('cq'), t); cy = last_row(R.get('cy'), t)
        if cq is not None and not np.isnan(cq.fcf_ttm) and (cy is None or cq.m >= cy.m): r['fcf_ttm'] = cq.fcf_ttm
        elif cy is not None: r['fcf_ttm'] = cy.fcf
        b = last_row(R.get('b'), t)
        if b is not None:
            r['equity'] = b.totalStockholderEquity
            debt = b.shortLongTermDebtTotal
            if pd.isna(debt):
                debt = np.nansum([b.shortTermDebt if pd.notna(b.shortTermDebt) else b.shortLongTermDebt,
                                  b.longTermDebt if pd.notna(b.longTermDebt) else b.longTermDebtTotal])
            r['debt'] = debt
            if pd.isna(r.get('cur')): r['cur'] = b.cur
        s0 = sh_at(R['sh'], r['m0']); s4 = sh_at(R['sh'], r['m0'] - 12)
        sl = sh_at(R['sh'], mi(t) - 2)  # azioni piu' recenti note
        r['sh'] = sl if not np.isnan(sl) else s0
        r['sh0'] = s0; r['sh4'] = s4
        rows.append(r)
    return rows


def fwd_returns(px, delisted):
    """rendimento di ogni trimestre di detenzione (prezzi corretti); fallimento = -100%"""
    a, _ = clean(px)
    out = {}
    last = a.index[-1]
    bk = False
    if delisted and last < TODAY - pd.Timedelta(days=30):
        hist = a[a.index >= last - pd.Timedelta(days=365)]
        bk = a.iloc[-1] < 0.25 * hist.max() or a.iloc[-1] <= 0
    for i, t in enumerate(REB):
        t1 = REB[i + 1] if i + 1 < len(REB) else TODAY
        a0 = a[a.index <= t]
        if not len(a0) or (t - a0.index[-1]).days > 10: continue
        p0 = a0.iloc[-1]
        a1 = a[a.index <= t1]
        p1 = a1.iloc[-1]
        ended = a1.index[-1] < t1 - pd.Timedelta(days=10) and last <= t1
        if ended and bk: rr = -1.0
        else: rr = float(np.clip(p1 / p0 - 1, -1, 10))
        out[t] = (rr, a1.index[-1], ended)
    return out


def proc(args):
    ex, codes, part = args
    FD = pickle.load(open(f'{BASE}/fund/fund.pkl', 'rb'))
    s = symbols(ex); DL = dict(zip(s.Code, s.delisted))
    P = pickle.load(open(f'{BASE}/eod/{ex}.pkl', 'rb'))
    rows, rets, meta = [], [], []
    for code in codes:
        t = f'{code}.{ex}'; fd = FD.get(t); px = P.get(code)
        if not fd or 'gen' not in fd or px is None or len(px) < 100: continue
        px = px[px.a > 0]
        if len(px) < 100: continue
        g = fd['gen']
        if ex == 'US' and g.get('CountryISO') in COVERED_OTHER: continue   # doppione (ADR / doppia quotazione)
        us = ex == 'US'
        sector = g.get('Sector') or g.get('GicSector')
        cur_px = g.get('CurrencyCode') or ('GBX' if ex == 'LSE' else None)
        delisted = bool(DL.get(code, 0)) or bool(g.get('IsDelisted')) or px.index[-1] < TODAY - pd.Timedelta(days=30)
        meta.append(dict(t=t, ex=ex, region=REGION[ex], name=g.get('Name'), sector=sector, country=g.get('CountryISO'), cur_px=cur_px,
                         delisted=delisted, last_px=px.index[-1]))
        try:
            fr = features(REB, fd, px, us, cur_px)
        except Exception as e:
            print('errore', t, e, flush=True); continue
        for r in fr: r['t'] = t
        rows += fr
        for d, (rr, ld, ended) in fwd_returns(px, delisted).items():
            rets.append((t, d, rr, ended))
    print(ex, part, len(rows), flush=True)
    return rows, rets, meta


if __name__ == '__main__':
    from multiprocessing import Pool
    C = pd.read_csv(f'{BASE}/res/candidates.csv')
    jobs = []
    for ex in C.ex.unique():
        cs = list(C[C.ex == ex].code)
        for k in range(0, len(cs), 250): jobs.append((ex, cs[k:k + 250], k))
    rows, rets, meta = [], [], []
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as P:
        for a, b, c in P.imap_unordered(proc, jobs): rows += a; rets += b; meta += c
    F = pd.DataFrame(rows); M = pd.DataFrame(meta); RQ = pd.DataFrame(rets, columns=['t', 'date', 'r', 'ended'])
    F.to_pickle(f'{BASE}/res/feat_raw.pkl'); M.to_pickle(f'{BASE}/res/meta.pkl'); RQ.to_pickle(f'{BASE}/res/rq.pkl')
    print(F.shape, M.shape, RQ.shape)
