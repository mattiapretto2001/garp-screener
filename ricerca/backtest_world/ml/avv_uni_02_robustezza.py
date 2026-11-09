# avv_uni_02 (verifica avversariale): (1) rifaccio 3+ numeri chiave; (2) t con errori standard piu' prudenti
# (Newey-West 8 ritardi, Hansen-Hodrick 3 ritardi a pesi uniformi, campioni annuali non sovrapposti);
# (3) sotto-campioni: solo date >=2018 (societa' uscite davvero presenti), senza 2024-25, senza finestre 2020, solo USA,
# senza Asia/Altri, solo >=2 mld$, senza l'1% di rendimenti migliori. Solo 2012-2026, nessun dato 2000-2011.
import numpy as np, pandas as pd, time
from scipy import stats
from univariata_common import *
t0 = time.time()
F = load_dev(); P = fv3.PREDICTORS
dates = np.sort(F.date.unique()); DI = {d: i for i, d in enumerate(dates)}; ND = len(dates)
F['di'] = F.date.map(DI).astype(int)

def hh_t(x, L=3):
    x = pd.Series(x).dropna().values.astype(float); T = len(x)
    if T < 8: return np.nan
    e = x - x.mean(); v = e @ e / T
    for l in range(1, L + 1): v += 2 * (e[l:] @ e[:-l]) / T
    if v <= 0: return fv3.nw_t(x, 8)
    return x.mean() / np.sqrt(v / T)

def nonover_t(s):
    """4 sotto-campioni annuali non sovrapposti (uno per trimestre di formazione): t semplice per ciascuno, poi media dei 4 t / e t della media"""
    s = s.dropna(); q = s.index.month
    ts = []
    for m in [3, 6, 9, 12]:
        z = s[q == m]
        if len(z) >= 6: ts.append(z.mean() / (z.std(ddof=1) / np.sqrt(len(z))))
    return np.mean(ts) if ts else np.nan

def series(mask, v, tk, keys=('date', 'reg')):
    X = F[mask]
    r = pct_rank(X, [v], list(keys))[v].values.astype(float)
    y = X[TGT[tk]].values.astype(float)
    s = group_stat(r, y, X.di.values, 'ic' if tk == 'rk' else 'auc', G=ND)
    return pd.Series(s, index=dates)

# ---------- (1) numeri chiave rifatti
allm = np.ones(len(F), bool)
for v in ['dsh3', 'n_beat4', 'runway_y', 'hist_y']:
    s = series(allm, v, 'rk'); print(f'RIFATTO {v}: IC {s.mean():+.4f}  t NW4 {fv3.nw_t(s,4):+.2f}')
# decile 10 di vol1y: quota eccezionali e disastri (ranghi 'first' come univariata_02)
G = F.sample(frac=1.0, random_state=7).sort_values('date', kind='stable')
for v, nb in [('vol1y', 10), ('dsh3', 5)]:
    gv = G[v].groupby([G.date, G.reg], observed=True)
    rr = (gv.rank(method='first') - 0.5) / gv.transform('count')
    b = np.clip(np.ceil(rr * nb), 1, nb)
    for tk, c in [('top5', 'top5_reg'), ('bot20', 'bot20_reg'), ('crash', 'crash50'), ('xs', 'xs12w')]:
        m = G.groupby([G.date, b]).apply(lambda d: d[c].astype(float).mean()).unstack()
        print(f'RIFATTO {v} bin1 / bin{nb} {tk}: {m[1].mean():.4f} / {m[nb].mean():.4f}', end='')
        if tk == 'xs': print(f'  Q{nb}-Q1 {(m[nb]-m[1]).mean():+.4f} t {fv3.nw_t(m[nb]-m[1],4):+.2f}  t HH {hh_t(m[nb]-m[1]):+.2f}')
        else: print()
print('fase 1', round(time.time() - t0))

# ---------- (2) errori standard prudenti su tutte le 243 prove principali
SER = pd.read_pickle(f'{OUT}/ic_series.pkl')
rows = []
for v in P:
    for tk in TGT_MAIN:
        s = SER[('pool', v, tk)].dropna()
        rows.append(dict(var=v, tgt=tk, mean=s.mean(), t4=fv3.nw_t(s, 4), t8=fv3.nw_t(s, 8), thh=hh_t(s, 3), tno=nonover_t(s), n=len(s)))
T = pd.DataFrame(rows)
for c in ['t4', 't8', 'thh', 'tno']:
    df = T.n - 1 if c != 'tno' else 13
    T['p_' + c] = 2 * stats.t.sf(T[c].abs(), df)
    T['holm_' + c] = holm(T['p_' + c].fillna(1).values)
print('\n|t|>=2,5 per target con SE diversi:')
print(T.groupby('tgt').apply(lambda d: pd.Series({c: int((d[c].abs() >= 2.5).sum()) for c in ['t4', 't8', 'thh', 'tno']})))
print('Holm <0,05 per target:')
print(T.groupby('tgt').apply(lambda d: pd.Series({c: int((d['holm_' + c] < 0.05).sum()) for c in ['t4', 't8', 'thh', 'tno']})))
S0 = pd.read_csv(f'{OUT}/ic_summary.csv')
solid = S0[(S0.tgt == 'rk') & (S0.verdetto == 'solida')]['var'].tolist()
print('solide su rango:', len(solid), solid)
print(T[(T.tgt == 'rk') & T['var'].isin(solid)].sort_values('t4')[['var', 'mean', 't4', 't8', 'thh', 'tno', 'holm_t4', 'holm_thh']].round(3).to_string(index=False))
T.to_csv(f'{OUT}/avv_t_prudenti.csv', index=False)
print('fase 2', round(time.time() - t0))

# ---------- (3) sotto-campioni per le variabili solide su a) e i freni/lotteria principali
EXTRA = ['hi52', 'vol1y', 'rev_cagr', 'cash_mcap', 'rd_int', 'mom12_1', 'peg', 'pe']
VV = solid + [v for v in EXTRA if v not in solid]
fwdq = F.groupby('date').fwd12_eur.transform(lambda s: s.rank(pct=True))
SUBS = {
    'tutto': allm,
    'date>=2018 (uscite presenti)': (F.date >= '2018-03-31').values,
    'date<=2017 (sopravvissute)': (F.date <= '2017-12-31').values,
    'senza 2024-25': (F.date < '2024-03-31').values,
    'senza finestre 2020': ~F.date.between('2019-03-31', '2020-12-31').values,
    'solo USA': (F.reg == 'USA').values,
    'USA, date>=2018': ((F.reg == 'USA') & (F.date >= '2018-03-31')).values,
    'senza Asia e Altri': (~F.reg.isin(['Asia', 'Altri'])).values,
    'Europa, date>=2018': ((F.reg == 'Europa') & (F.date >= '2018-03-31')).values,
    '>=2 mld $': (F.mcap_usd >= 2e9).values,
    'senza top 1% rendimenti': (fwdq <= 0.99).values,
    'senza Sanita': (F.sector_n.astype(str) != 'Healthcare').values,
}
out = []
for v in VV:
    for sn, m in SUBS.items():
        for tk in TGT_MAIN:
            s = series(m, v, tk).dropna()
            if len(s) < 8: continue
            out.append(dict(var=v, sub=sn, tgt=tk, mean=s.mean(), t4=fv3.nw_t(s, 4), thh=hh_t(s, 3), n=len(s)))
O = pd.DataFrame(out); O.to_csv(f'{OUT}/avv_sottocampioni.csv', index=False)
pd.set_option('display.width', 300); pd.set_option('display.max_rows', 500); pd.set_option('display.max_columns', 30)
for tk in TGT_MAIN:
    W = O[O.tgt == tk].pivot(index='var', columns='sub', values='t4')[list(SUBS)]
    M = O[O.tgt == tk].pivot(index='var', columns='sub', values='mean')[list(SUBS)]
    print(f'\n==== t NW4 per sotto-campione, target {tk}'); print(W.loc[VV].round(1).to_string())
    print(f'---- media x100, target {tk}'); print((100 * M.loc[VV]).round(1).to_string())
print('fine', round(time.time() - t0))
