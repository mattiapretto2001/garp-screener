# univariata_02: quintili (e decili per alcune variabili) dentro data x regione; Q5-Q1 con t di Newey-West;
# monotonia; termine quadratico di Fama-MacBeth (forme a U / a campana); tasso dei target fra i dati mancanti.
import numpy as np, pandas as pd, time
from univariata_common import *
t0 = time.time()
F = load_dev(); P = fv3.PREDICTORS
F = F.sample(frac=1.0, random_state=7).sort_values('date', kind='stable')          # pareggi rotti a caso ma riproducibili
dates = np.sort(F.date.unique()); DI = {d: i for i, d in enumerate(dates)}; F['di'] = F.date.map(DI).astype(int)
YC = {'rk': 'rk12_reg', 'top5': 'top5_reg', 'bot20': 'bot20_reg', 'crash': 'crash50', 'xs': 'xs12w'}
Y = {k: F[c].astype(float).values for k, c in YC.items()}
g = F.groupby(['date', 'reg'], observed=True)
RF = {}
for v in P:
    gv = F[v].groupby([F.date, F.reg], observed=True)
    RF[v] = ((gv.rank(method='first') - 0.5) / gv.transform('count')).values
print('ranghi', round(time.time() - t0))
ND = len(dates); di = F.di.values
rowsQ, rowsS, rowsD = [], [], []
DEC = ['revq', 'revg_ttm', 'rev_cagr', 'accel_q', 'epsg', 'mom12_1', 'hi52', 'vol1y', 'dsh3', 'pe', 'ev_sales', 'peg', 'roic', 'fcfy',
       'logmcap', 'opm', 'runway_y', 'n_beat4', 'gm', 'rd_int', 'ind_revg_med', 'cash_mcap']
for v in P:
    r = RF[v]; ok = np.isfinite(r)
    q = np.where(ok, np.clip(np.ceil(r * 5), 1, 5), 0).astype(int)              # 0 = mancante
    M = {}
    for k, y in Y.items():
        m = np.isfinite(y)
        cnt = np.bincount(di[m] * 6 + q[m], minlength=ND * 6).reshape(ND, 6)
        s = np.bincount(di[m] * 6 + q[m], y[m], minlength=ND * 6).reshape(ND, 6)
        with np.errstate(all='ignore'): M[k] = s / cnt
        M[k][cnt < 10] = np.nan
    for k in Y:
        mm = np.nanmean(M[k], axis=0)
        d51 = pd.Series(M[k][:, 5] - M[k][:, 1])
        steps = np.diff(mm[1:6]); sp = mm[5] - mm[1]
        rowsQ.append(dict(var=v, tgt=k, Q1=mm[1], Q2=mm[2], Q3=mm[3], Q4=mm[4], Q5=mm[5], NA=mm[0],
                          na_share=1 - ok.mean(), q51=sp, t51=fv3.nw_t(d51, 4),
                          n_mono=int((np.sign(steps) == np.sign(sp)).sum()),
                          top_step=steps[-1] / sp if sp else np.nan, bot_step=steps[0] / sp if sp else np.nan))
    # termine quadratico per data: y = a + b z + c (z^2 - media), z = rango - 0,5
    for k in ['rk', 'top5', 'bot20']:
        y = Y[k]; m = ok & np.isfinite(y)
        z = r[m] - 0.5; z2 = z * z - 1 / 12.; yy = y[m]; dd = di[m]
        cb, cc = [], []
        for i in range(ND):
            w = dd == i
            if w.sum() < 50: cb.append(np.nan); cc.append(np.nan); continue
            X = np.column_stack([np.ones(w.sum()), z[w], z2[w]])
            beta = np.linalg.lstsq(X, yy[w], rcond=None)[0]; cb.append(beta[1]); cc.append(beta[2])
        rowsS.append(dict(var=v, tgt=k, b_lin=np.nanmean(cb), t_lin=fv3.nw_t(cb, 4), c_quad=np.nanmean(cc), t_quad=fv3.nw_t(cc, 4)))
    if v in DEC:
        dq = np.where(ok, np.clip(np.ceil(r * 10), 1, 10), 0).astype(int)
        for k in ['rk', 'top5', 'bot20', 'crash', 'xs']:
            y = Y[k]; m = np.isfinite(y)
            cnt = np.bincount(di[m] * 11 + dq[m], minlength=ND * 11).reshape(ND, 11)
            s = np.bincount(di[m] * 11 + dq[m], y[m], minlength=ND * 11).reshape(ND, 11)
            with np.errstate(all='ignore'): mm = np.nanmean(np.where(cnt >= 5, s / cnt, np.nan), axis=0)
            rowsD.append(dict(var=v, tgt=k, **{f'D{j}': mm[j] for j in range(1, 11)}, NA=mm[0]))
Q = pd.DataFrame(rowsQ); S = pd.DataFrame(rowsS); D = pd.DataFrame(rowsD)
Q = Q.merge(S, on=['var', 'tgt'], how='left')


def shape(r):
    m = [r.Q1, r.Q2, r.Q3, r.Q4, r.Q5]
    if not np.isfinite(r.t_quad) or abs(r.t_quad) < 2.5:
        return 'lineare' if r.n_mono >= 3 else 'irregolare'
    mid = max(m[1:4]) if r.c_quad < 0 else min(m[1:4])
    if r.c_quad < 0 and mid > max(m[0], m[4]): return 'campana (meglio al centro)'
    if r.c_quad > 0 and mid < min(m[0], m[4]): return 'U (estremi)'
    return 'curva: effetto concentrato in un estremo'


Q['forma'] = [shape(r) if r.tgt in ('rk', 'top5', 'bot20') else '' for r in Q.itertuples()]
Q.to_csv(f'{OUT}/quintili.csv', index=False); D.to_csv(f'{OUT}/decili.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 400)
for k in ['rk', 'top5', 'bot20', 'xs']:
    print('\n=====', k)
    d = Q[Q.tgt == k].copy()
    for c in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'NA', 'q51']: d[c] = d[c] * (100 if k != 'rk' else 1)
    print(d[['var', 'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'NA', 'na_share', 'q51', 't51', 'n_mono', 't_quad', 'forma']].round(3).to_string(index=False))
print('fine', round(time.time() - t0))
