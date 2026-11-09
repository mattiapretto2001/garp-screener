# Verifica avversariale prova B: salti giornalieri forti (x>=2 o x<=0,5) del prezzo corretto nei titoli B, 2005-2012,
# che cadono dentro la finestra di 3 mesi di una riga B (quindi entrano nei portafogli trimestrali).
import os, glob, pandas as pd, numpy as np
ML = '${RICERCA_BASE}/backtest_world/ml'
B = pd.read_pickle(f'{ML}/storico5/provaB/matrice_B.pkl'); B = B[(B.anno >= 2006) & (B.anno <= 2011)]
TS = set(B.t); PX = {}
L = pd.read_pickle(f'{ML}/eod_lungo/US.pkl.gz'); L['t'] = L.t.astype(str); L = L[L.t.isin(TS)]
for t, x in L.groupby('t', sort=False): PX[t] = x.drop(columns='t').set_index('date')
del L
for fn in glob.glob(f'{ML}/storico5/raw/prezzi_us/*.pkl'):
    t = os.path.basename(fn)[:-7]
    if t in TS and t not in PX:
        d = pd.read_pickle(fn)
        if d is not None and len(d): PX[t] = d.set_index('date')
N = pd.read_pickle(f'{ML}/eod_lungo/US_uscite.pkl.gz'); N['t'] = N.t.astype(str); N = N[N.t.isin(TS)]
for t, x in N.groupby('t', sort=False):
    if t not in PX: PX[t] = x.drop(columns='t').set_index('date')
ev = []
for t, d in PX.items():
    d = d[~d.index.duplicated(keep='last')].sort_index(); d = d[(d.a > 0) & (d.c > 0)].loc['2005-10-01':'2012-10-31']
    if len(d) < 50: continue
    a = d.a.values.astype(float); c = d.c.values.astype(float); v = d.v.values.astype(float)
    ra = a[1:] / a[:-1]; rc = c[1:] / c[:-1]
    for i in np.where((ra >= 2) | (ra <= 0.5))[0]:
        vb = np.nanmedian(v[max(0, i - 20):i + 1]); va = np.nanmedian(v[i + 1:i + 22])
        ev.append(dict(t=t, giorno=d.index[i + 1], salto_corretto=ra[i], salto_chiusura=rc[i], volume_dopo_su_prima=va / vb if vb > 0 else np.nan))
E = pd.DataFrame(ev)
B2 = B[['t', 'date', 'name', 'f3', 'f12', 'crash50']]
rows = []
for _, e in E.iterrows():
    x = B2[(B2.t == e.t) & (B2.date < e.giorno) & (e.giorno <= B2.date + pd.offsets.MonthEnd(3))]
    for _, r in x.iterrows(): rows.append({**r.to_dict(), **e.to_dict()})
R = pd.DataFrame(rows)
pd.set_option('display.width', 250)
print('salti giornalieri x2 / x0,5 nei titoli B:', len(E), '| che entrano in un f3 di una riga B:', len(R))
print(R.sort_values('giorno').round(3).to_string())
R.to_csv(f'{ML}/avv_B_out/salti_in_f3_B.csv', index=False)
