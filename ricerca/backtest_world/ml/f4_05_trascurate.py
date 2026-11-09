# f4_05: famiglia A, societa' seguite da pochi analisti.
# A1 = n_est4<=2 (proxy: stime presenti in al massimo 2 degli ultimi 4 annunci), tutto l'universo dove n_est4 esiste.
# A2 = numero vero di analisti (EODHD Earnings Trend) nel campione casuale USA di 285 societa': <=3 analisti; variante:
#      terzile piu' basso del residuo di log(1+analisti) su logmcap (pochi analisti PER LA TAGLIA).
import os, json, glob, numpy as np, pandas as pd
from f4_common import load, evaluate, fmt, OUT
F = load()
R = []
has = F.n_est4.notna()
for reg in ['tutte', 'USA', 'Europa', 'Asia', 'Altri']:
    rm = has if reg == 'tutte' else has & (F.reg == reg)
    R.append(evaluate(F, F.n_est4 <= 2, rm, f'A1 n_est4<=2 [{reg}]'))
R.append(evaluate(F, F.n_est4 == 0, has & (F.reg == 'USA'), 'A1b nessuna stima [USA]'))
for lst in ['GARP', 'core']:
    R.append(evaluate(F, F.n_est4 <= 2, has & F[lst], f'A1 n_est4<=2 dentro {lst}'))
# ---- A2
rows = []
for p in glob.glob(f'{OUT}/eodhd_campione/*.US.json'):
    t = os.path.basename(p)[:-5]; j = json.load(open(p))
    tr = j.get('Earnings::Trend'); tr = tr if isinstance(tr, dict) else {}
    for k, v in tr.items():
        if v.get('period') == '0q':
            rows.append((t, pd.Timestamp(v['date']), pd.to_numeric(v.get('earningsEstimateNumberOfAnalysts'), errors='coerce')))
T = pd.DataFrame(rows, columns=['t', 'qd', 'na']).dropna().sort_values('qd')
S = F[F.t.isin(T.t.unique())].sort_values('date')
S = pd.merge_asof(S, T.rename(columns={'qd': 'date'}), on='date', by='t', direction='backward', tolerance=pd.Timedelta(days=120))
S.index = F[F.t.isin(T.t.unique())].sort_values('date').index
F['na'] = S['na']
print('campione: societa', T.t.nunique(), 'righe con analisti', F.na.notna().sum(), 'prima data trend', T.qd.min().date())
print('analisti: quantili', F.na.quantile([.1, .25, .5, .75, .9]).to_dict())
print('correlazione con n_est4 (righe comuni):', round(F[['na', 'n_est4']].corr().iloc[0, 1], 2))
m = F.na.notna()
# residuo log(1+na) ~ logmcap per data
res = pd.Series(np.nan, index=F.index)
for d, x in F[m].groupby('date'):
    if len(x) < 20: continue
    b = np.polyfit(x.logmcap, np.log1p(x.na), 1); res[x.index] = np.log1p(x.na) - np.polyval(b, x.logmcap)
F['na_res'] = res
lowres = F.na_res <= F.groupby('date').na_res.transform(lambda s: s.quantile(1 / 3))
R.append(evaluate(F, F.na <= 3, m, 'A2 <=3 analisti [campione USA]'))
R.append(evaluate(F, lowres & F.na_res.notna(), F.na_res.notna(), 'A2b pochi analisti per la taglia [campione USA]'))
D = pd.concat(R, ignore_index=True)
fmt(D).to_csv(f'{OUT}/f4_05_trascurate.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
print(fmt(D).to_string())
