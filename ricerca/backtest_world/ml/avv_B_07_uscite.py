# Verifica avversariale prova B (par. 7): la regola di uscita "-100% se l'ultimo prezzo e' sotto il 25% del massimo
# dell'ultimo anno" guarda il massimo dei 365 giorni prima dell'ULTIMO prezzo, che puo' cadere PRIMA della data di acquisto.
# Conto le righe dell'universo A 2006-2011 con f12 = -100% in cui l'ultimo prezzo e' sopra il 50% del prezzo alla data
# (quindi, senza la regola, non sarebbero nemmeno un crollo).
import os, glob, pandas as pd, numpy as np
ML = '${RICERCA_BASE}/backtest_world/ml'
U = pd.read_pickle(f'{ML}/storico5/provaB/universo_A_copia.pkl'); A = U[(U.anno >= 2006) & (U.anno <= 2011)]
K = A[(A.f12 <= -0.999) & A.f12_end]
print('righe A 2006-11:', len(A), '| f12 = -100% per uscita:', len(K), '| titoli:', K.t.nunique(), '| crolli totali A:', int((A.f12 <= -0.5).sum()))
TS = set(K.t); PX = {}
for fn in (f'{ML}/eod_lungo/US.pkl.gz', f'{ML}/eod_lungo/US_uscite.pkl.gz'):
    L = pd.read_pickle(fn); L['t'] = L.t.astype(str); L = L[L.t.isin(TS)]
    for t, x in L.groupby('t', sort=False):
        if t not in PX: PX[t] = x.drop(columns='t').set_index('date')
for fn in glob.glob(f'{ML}/storico5/raw/prezzi_us/*.pkl'):
    t = os.path.basename(fn)[:-7]
    if t in TS and t not in PX:
        d = pd.read_pickle(fn)
        if d is not None and len(d): PX[t] = d.set_index('date')
rows = []
for _, r in K.iterrows():
    d = PX.get(r.t)
    if d is None: continue
    d = d[~d.index.duplicated(keep='last')].sort_index(); d = d[d.a > 0]
    i = d.index.searchsorted(r.date, side='right') - 1
    if i < 0: continue
    a = d.a.values; last = d.index[-1]
    h0 = d.index.searchsorted(last - pd.Timedelta(days=365), side='left')
    mx_all = np.nanmax(a[h0:]); mx_after = np.nanmax(a[max(h0, i):])
    rows.append(dict(t=r.t, date=r.date, name=r['name'], ultimo=last, ratio_ultimo_su_acquisto=a[-1] / a[i],
                     sotto25_max_dopo_acquisto=a[-1] < 0.25 * mx_after, mesi_a_uscita=(last - r.date).days / 30.4))
R = pd.DataFrame(rows)
print('ricostruite:', len(R))
print('ultimo prezzo / prezzo alla data: quantili', R.ratio_ultimo_su_acquisto.quantile([.1, .25, .5, .75, .9]).round(3).to_dict())
print('con ultimo prezzo > 50% di quello alla data (non sarebbero crolli):', int((R.ratio_ultimo_su_acquisto > 0.5).sum()),
      '| > 100% (in guadagno):', int((R.ratio_ultimo_su_acquisto > 1).sum()),
      '| che con il massimo calcolato solo dopo l acquisto NON sarebbero -100%:', int((~R.sotto25_max_dopo_acquisto).sum()))
R.to_csv(f'{ML}/avv_B_out/uscite_meno100_A.csv', index=False)
print(R.sort_values('ratio_ultimo_su_acquisto', ascending=False).head(15).round(3).to_string())
