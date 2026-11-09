# tune_01: pannello esteso per l'affinamento dello screener.
# Parte da res/feat.pkl (metriche GARP point-in-time gia' calcolate) e aggiunge, sempre point-in-time:
#  - utile operativo 12 mesi ora e un anno prima, ricavi 12 mesi un anno prima e due anni prima
#  - crescita ricavi del trimestre precedente (per l'accelerazione)
#  - momentum di prezzo (12-1 mesi, 6 mesi), distanza dal massimo a 52 settimane
#  - rendimenti futuri a 12 e 36 mesi (valuta locale, societa' uscite dal listino incluse: dopo l'uscita liquidita' a 0,
#    fallimento -100% come in world_04)
# Nessuna chiamata a EODHD.
import pickle, sys, warnings, pandas as pd, numpy as np
from world_common import *
from world_04_features import company, last_row, clean, REB, TODAY
warnings.filterwarnings('ignore')


def extra(fd, px, us, dates):
    R = company(fd, us)
    iq = R.get('iq'); iy = R.get('iy')
    if iq is not None and 'operatingIncome' in iq:
        from world_04_features import ttm_rows
        A = iy if iy is not None else None
        to, bo, qo = ttm_rows(iq, 'operatingIncome', A, tol=0.15)
        to[bo] = np.nan
        iq['opi_ttm'] = to; iq['opi_qp'] = qo
    a, _ = clean(px)
    out = {}
    for t in dates:
        r = {}
        x = last_row(iq, t) if iq is not None else None
        y = last_row(iy, t) if iy is not None else None
        use_q = x is not None and not np.isnan(x.rev_ttm) and not np.isnan(x.ni_ttm) and (y is None or x.m >= y.m)
        if use_q:
            m0 = int(x.m); Q = iq.set_index('m')
            def g(mm, c):
                return Q[c].get(mm, np.nan) if mm in Q.index else np.nan
            r['opi_ttm'] = x.get('opi_ttm', np.nan); r['opi_ttm4'] = g(m0 - 12, 'opi_ttm') if 'opi_ttm' in Q else np.nan
            r['rev_ttm4'] = g(m0 - 12, 'rev_ttm'); r['rev_ttm8'] = g(m0 - 24, 'rev_ttm')
            r['ni_ttm8'] = g(m0 - 24, 'ni_ttm')
            cv = int(x.cv); pm = m0 - cv
            rq_p, rqp_p = g(pm, 'totalRevenue'), g(pm, 'rev_qp')
            r['revq_prev'] = rq_p / rqp_p - 1 if (rqp_p is not None and rqp_p == rqp_p and rqp_p > 0) else np.nan
        elif y is not None:
            m0 = int(y.m); Y = iy.set_index('m')
            def gy(mm, c):
                return Y[c].get(mm, np.nan) if mm in Y.index else np.nan
            r['opi_ttm'] = y.get('operatingIncome', np.nan); r['opi_ttm4'] = gy(m0 - 12, 'operatingIncome')
            r['rev_ttm4'] = gy(m0 - 12, 'totalRevenue'); r['rev_ttm8'] = gy(m0 - 24, 'totalRevenue')
            r['ni_ttm8'] = gy(m0 - 24, 'ni')
            r['revq_prev'] = np.nan
        # utile annuale positivo negli ultimi 3 bilanci annuali prima di quello corrente (per "primo utile")
        if iy is not None:
            yy = iy[iy.av <= t].sort_values('m')
            r['n_prof_y'] = int((yy.ni.tail(4).iloc[:-1] > 0).sum()) if len(yy) >= 2 else np.nan
        # prezzi
        aa = a[a.index <= t]
        if len(aa) > 260 and (t - aa.index[-1]).days <= 10:
            p0 = aa.iloc[-1]
            def back(days):
                z = aa[aa.index <= t - pd.Timedelta(days=days)]
                return z.iloc[-1] if len(z) else np.nan
            r['mom12_1'] = back(30) / back(365) - 1
            r['mom6'] = p0 / back(182) - 1
            r['mom12'] = p0 / back(365) - 1
            r['hi52'] = p0 / aa[aa.index > t - pd.Timedelta(days=365)].max()
            r['ma200'] = p0 / aa.iloc[-200:].mean()
            r['vol1y'] = np.log(aa[aa.index > t - pd.Timedelta(days=365)]).diff().std() * np.sqrt(252)
        out[t] = r
    return out


def proc(args):
    ex, codes, need = args
    FD = pickle.load(open(f'{BASE}/fund/fund.pkl', 'rb'))
    P = pickle.load(open(f'{BASE}/eod/{ex}.pkl', 'rb'))
    rows = []
    for code in codes:
        t = f'{code}.{ex}'; fd = FD.get(t); px = P.get(code)
        if not fd or 'gen' not in fd or px is None: continue
        px = px[px.a > 0]
        if len(px) < 100: continue
        try:
            e = extra(fd, px, ex == 'US', need[t])
        except Exception as er:
            print('errore', t, er, flush=True); continue
        for d, r in e.items():
            r['t'] = t; r['date'] = d; rows.append(r)
    print(ex, len(rows), flush=True)
    return rows


def fwd(RQ):
    """rendimento composto sui prossimi k trimestri; i trimestri mancanti (titolo uscito) valgono 0"""
    idx = {t: i for i, t in enumerate(REB)}
    out = []
    for t, x in RQ.groupby('t'):
        s = dict(zip(x.date, x.r))
        for d in x.date:
            i = idx[d]; row = [t, d]
            for k in (4, 12):
                if i + k >= len(REB): row.append(np.nan); continue   # orizzonte non ancora completo
                row.append(np.prod([1 + s.get(REB[j], 0.0) for j in range(i, i + k)]) - 1)
            out.append(row)
    return pd.DataFrame(out, columns=['t', 'date', 'f12', 'f36'])


if __name__ == '__main__':
    from multiprocessing import Pool
    F = pd.read_pickle(f'{BASE}/res/feat.pkl')
    need = F.groupby('t').date.apply(list).to_dict()
    jobs = []
    for ex in F.ex.unique():
        cs = sorted({t.rsplit('.', 1)[0] for t in need if t.endswith('.' + ex)})
        for k in range(0, len(cs), 300):
            sub = cs[k:k + 300]
            jobs.append((ex, sub, {f'{c}.{ex}': need[f'{c}.{ex}'] for c in sub}))
    rows = []
    with Pool(4) as P:
        for a in P.imap_unordered(proc, jobs): rows += a
    E = pd.DataFrame(rows)
    RQ = pd.read_pickle(f'{BASE}/res/rq.pkl')
    FW = fwd(RQ)
    E.to_pickle(f'{BASE}/res/tune_extra.pkl'); FW.to_pickle(f'{BASE}/res/tune_fwd.pkl')
    print(E.shape, FW.shape, E.notna().mean().round(2).to_dict())
