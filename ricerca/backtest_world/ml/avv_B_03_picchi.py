# Verifica avversariale prova B: picchi finti nei prezzi corretti (salto giornaliero >=x2 o <=x0,5 che rientra entro 60 sedute
# con un salto opposto di simile ampiezza): tipico di un frazionamento applicato in ritardo/anticipo. Per i titoli della prova B,
# 2005-2012, dalle stesse serie usate da sB_01 (eod_lungo/US, raw/prezzi_us, US_uscite). Poi: quali righe B (trimestri) hanno
# il picco dentro la finestra di 3 mesi o di 12 mesi.
import os, glob, pandas as pd, numpy as np
ML = '${RICERCA_BASE}/backtest_world/ml'
B = pd.read_pickle(f'{ML}/storico5/provaB/matrice_B.pkl'); B = B[(B.anno >= 2006) & (B.anno <= 2011)]
TS = set(B.t)
PX = {}
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
print('serie', len(PX), 'di', len(TS))
ev = []
for t, d in PX.items():
    d = d[~d.index.duplicated(keep='last')].sort_index(); d = d[(d.a > 0)]
    d = d.loc['2005-01-01':'2012-12-31']
    if len(d) < 50: continue
    a = d.a.values.astype(float); lr = np.diff(np.log(a)); idx = d.index[1:]
    big = np.where(np.abs(lr) >= np.log(2))[0]
    for i in big:
        w = lr[i + 1:i + 61]
        j = np.where((np.sign(w) == -np.sign(lr[i])) & (np.abs(w) >= 0.6 * abs(lr[i])))[0]
        if len(j):
            ev.append(dict(t=t, inizio=idx[i], fine=idx[i + 1 + j[0]], salto=float(np.exp(lr[i])), rientro=float(np.exp(w[j[0]]))))
E = pd.DataFrame(ev)
print('picchi trovati:', len(E), '| titoli:', E.t.nunique() if len(E) else 0)
if len(E):
    E = E.drop_duplicates(['t', 'inizio'])
    print(E.sort_values('inizio').to_string())
    E.to_csv(f'{ML}/avv_B_out/picchi_prezzi_B.csv', index=False)
    # righe B toccate: picco che inizia dentro (d, d+3m] -> f3 sbagliato; dentro (d, d+12m] -> f12/crollo sbagliati
    rows = []
    for _, e in E.iterrows():
        x = B[B.t == e.t]
        for _, r in x.iterrows():
            in3 = r.date < e.inizio <= r.date + pd.offsets.MonthEnd(3) and not (r.date < e.fine <= r.date + pd.offsets.MonthEnd(3))
            in12 = r.date < e.inizio <= r.date + pd.offsets.MonthEnd(12) and not (r.date < e.fine <= r.date + pd.offsets.MonthEnd(12))
            if in3 or in12: rows.append(dict(t=r.t, date=r.date, f3=r.f3, f12=r.f12, crash50=r.crash50, f3_toccato=in3, f12_toccato=in12))
    R = pd.DataFrame(rows).drop_duplicates(['t', 'date'])
    print('righe B con f3 toccato:', int(R.f3_toccato.sum()), '| con f12 toccato:', int(R.f12_toccato.sum()), '| crolli finti possibili:', int((R.f12_toccato & (R.crash50 == 1)).sum()))
    R.to_csv(f'{ML}/avv_B_out/righe_B_toccate_da_picchi.csv', index=False)
    print(R.to_string())
