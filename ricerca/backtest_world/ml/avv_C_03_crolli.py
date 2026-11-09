# Verifica avversariale Prova C: salti al ribasso di un giorno (<= -45%) nelle serie del sostituto 2000-2011 (P1), che c01 non
# ferma (ferma solo i salti al rialzo). Classifico con il volume (criteri della verifica della prova A) e conto le posizioni toccate.
import sys, os, json, pickle, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML); sys.path.insert(0, ML); sys.path.insert(0, BW); sys.path.insert(0, f'{ML}/regoleC')
OUT = f'{ML}/avv_C_out'
P = pickle.load(open(f'{ML}/regoleC/dati/P1.pkl', 'rb'))
cal, tick, M = P['cal'], P['tick'], P['M'].astype(float)
POS = pickle.load(open(f'{ML}/regoleC/dati/posizioni.pkl', 'rb'))
held = set()
for k in [('P1', 'L', 'none', False), ('P1', 'T3', 'none', False), ('P1', 'T2', 'none', False)]:
    held |= set(np.unique(POS[k]['j']).tolist())
ev = []
for j in held:
    x = pd.Series(M[j]).ffill().values
    r = x[1:] / x[:-1]
    for k in np.where(r < 0.55)[0] + 1:
        ev.append((j, tick[j], k, cal[k], float(r[k - 1]), float(x[k - 1]), float(x[k])))
E = pd.DataFrame(ev, columns=['j', 't', 'k', 'giorno', 'rapporto', 'prima', 'dopo'])
print('titoli tenuti almeno una volta', len(held), '| salti di un giorno <= -45%:', len(E), 'in', E.t.nunique(), 'titoli', flush=True)
# volumi dalla serie originale
import s5_09_pannello_v2 as S9
pool, src = S9.series_pool()
spl_dir = f'{ML}/storico5/splits_A'
rows = []
for _, e in E.iterrows():
    d = pool.get(e.t)
    if d is None: rows.append(dict(vol_ratio=np.nan, zero_after=np.nan, split_near=False)); continue
    d = d[~d.index.duplicated(keep='last')].sort_index()
    v = d.v.astype(float)
    i = v.index.searchsorted(e.giorno)
    vb = np.nanmedian(v.values[max(0, i - 20):i]) if i > 0 else np.nan
    vd = v.values[i] if i < len(v) else np.nan
    za = np.mean(v.values[i + 1:i + 21] == 0) if i + 1 < len(v) else np.nan
    sp = False
    fn = f'{spl_dir}/{e.t}.json'
    if os.path.exists(fn):
        for s in json.load(open(fn)):
            try:
                if abs((pd.Timestamp(s['date']) - e.giorno).days) <= 3: sp = True
            except Exception: pass
    rows.append(dict(vol_ratio=vd / vb if vb and vb > 0 else np.nan, zero_after=za, split_near=sp))
E = pd.concat([E.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
E['sospetto'] = (E.zero_after >= 0.5) | E.split_near | (E.vol_ratio < 2)
E['nome'] = E.t.map(lambda t: '')
E.to_pickle(f'{OUT}/crolli_P1.pkl')
print(E.sospetto.value_counts().to_dict())
print(E[E.sospetto].sort_values('rapporto').head(60).to_string())
