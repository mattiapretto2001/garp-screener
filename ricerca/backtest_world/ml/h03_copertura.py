# Storico 2000-2011, fase 3: unisce i blocchi scaricati (un pickle gzip per borsa) e misura la copertura
# di prezzi (dal 1998) e bilanci (fund2) per regione e periodo. Nessuna chiamata a EODHD.
import os, sys, glob, pickle, json, pandas as pd, numpy as np
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML); OUT = f'{ML}/eod_lungo'
sys.path.insert(0, BW)
EUR = ['LSE', 'XETRA', 'PA', 'ST', 'SW', 'MC', 'AS', 'CO', 'OL', 'HE', 'BR']
def regione(ex, us_new):
    if ex == 'US': return 'USA piccole/medie' if us_new else 'USA grandi'
    if ex in EUR: return 'Europa'
    if ex in ('TW', 'KO'): return 'Asia'
    return 'Canada/Australia'

if 'merge' in sys.argv:
    for ex in sorted({os.path.basename(f).split('_')[1] for f in glob.glob(f'{OUT}/part_*.pkl')}):
        parts = sorted(glob.glob(f'{OUT}/part_{ex}_*.pkl'))
        d = pd.concat([pd.read_pickle(f) for f in parts], ignore_index=True)
        d['t'] = d.t.astype(str).astype('category')
        d = d.drop_duplicates(['t', 'date']).sort_values(['t', 'date']).reset_index(drop=True)
        d.to_pickle(f'{OUT}/{ex}.pkl.gz', compression='gzip')
        for f in parts: os.remove(f)
        print(ex, d.t.nunique(), 'ticker', len(d), 'righe', flush=True)

# --- riepilogo per ticker
p = pd.read_pickle(f'{BW}/res/panel2.pkl')
info = p.groupby('t').agg(ex=('ex', 'first'), us_new=('us_new', 'first'), dl=('delisted', 'first'))
f2 = {**pickle.load(open(f'{BW}/fund/fund.pkl', 'rb')), **pickle.load(open(f'{BW}/fund/fund2.pkl', 'rb'))}  # fund2 ha la precedenza
rows = []
for fn in sorted(glob.glob(f'{OUT}/*.pkl.gz')):
    ex = os.path.basename(fn).split('.')[0]
    d = pd.read_pickle(fn)
    g = d.groupby('t', observed=True).date.agg(['min', 'max', 'size'])
    # scambi giornalieri in valuta locale (mediana per anno) per la soglia di liquidita' (solo descrittiva)
    for t, r in g.iterrows():
        rows.append((f'{t}.{ex}', ex, r['min'], r['max'], r['size']))
S = pd.DataFrame(rows, columns=['t', 'ex', 'first', 'last', 'n'])
S['us_new'] = S.t.map(info.us_new).fillna(False).astype(bool)
S['in_panel'] = S.t.isin(info.index)
S['reg'] = [regione(e, u) for e, u in zip(S.ex, S.us_new)]
# fondamentali: prima data trimestrale/annuale e affidabilita' della data di deposito
def fstat(t):
    v = f2.get(t)
    if not v: return (pd.NaT, pd.NaT, np.nan, np.nan, np.nan)
    q = v.get('inc_q'); y = v.get('inc_y')
    fq = pd.to_datetime(q.date).min() if q is not None and len(q) else pd.NaT
    fy = pd.to_datetime(y.date).min() if y is not None and len(y) else pd.NaT
    def lagstat(x):
        if x is None or not len(x) or 'filing_date' not in x: return np.nan
        x = x[pd.to_datetime(x.date) < '2011-01-01']
        if not len(x): return np.nan
        lag = (pd.to_datetime(x.filing_date) - pd.to_datetime(x.date)).dt.days
        return float((lag <= 0).mean())  # quota con data di deposito = data di chiusura (inaffidabile)
    nq = int((pd.to_datetime(q.date) < '2011-01-01').sum()) if q is not None and len(q) else 0
    return (fq, fy, lagstat(q), lagstat(y), nq)
F = pd.DataFrame([fstat(t) for t in S.t], columns=['fq', 'fy', 'lag0_q', 'lag0_y', 'nq_pre2011'])
S = pd.concat([S.reset_index(drop=True), F], axis=1)
S['has_fund2'] = S.t.isin(f2.keys())
S.to_pickle(f'{ML}/eod_lungo/_riepilogo_ticker.pkl')

def cov(x, d):
    d = pd.Timestamp(d); return int(((x['first'] <= d) & (x['last'] >= d)).sum())
out = []
for reg, x in S.groupby('reg'):
    r = {'regione': reg, 'ticker': len(x), 'con_prezzi': int((x.n > 0).sum())}
    for d in ['1998-06-30', '2000-06-30', '2005-06-30', '2010-06-30', '2012-06-30']: r['quotati_' + d[:4]] = cov(x, d)
    xf = x[x.has_fund2]
    for d in ['2000-12-31', '2005-12-31', '2010-12-31']:
        r['bil_trim_' + d[:4]] = int((xf.fq <= pd.Timestamp(d)).sum()); r['bil_ann_' + d[:4]] = int((xf.fy <= pd.Timestamp(d)).sum())
    r['deposito=chiusura_trim_pre2011'] = round(float(xf.lag0_q.mean()), 2) if len(xf) else np.nan
    r['deposito=chiusura_ann_pre2011'] = round(float(xf.lag0_y.mean()), 2) if len(xf) else np.nan
    out.append(r)
T = pd.DataFrame(out).set_index('regione').T
print(T.to_string())
T.to_csv(f'{ML}/copertura_regioni.csv')
