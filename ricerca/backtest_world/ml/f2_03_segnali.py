# F2 passo 3: segnali insider a ogni fine trimestre (12/2005 - 09/2026), per codice dei nostri prezzi.
# DEFINIZIONI FISSATE PRIMA DI GUARDARE I RENDIMENTI (09/11/2026). Un insider "conta" in una finestra se i suoi acquisti P
# (Director/Officer, data di deposito nella finestra) sommano almeno 25.000 $. Un segnale e' attivo alla data d se l'evento
# (deposito che lo completa) cade in (d-90 giorni, d]: cioe' noto entro la fine del trimestre.
#   ANY     almeno 1 insider >=25k$ nei 90 giorni (riferimento: "un acquisto qualsiasi")
#   C2_30   almeno 2 insider distinti con depositi entro 30 giorni l'uno dall'altro   } GRAPPOLI
#   C2_90   almeno 2 insider distinti entro 90 giorni                                  }   (C3_90 e' la definizione principale,
#   C3_90   almeno 3 insider distinti entro 90 giorni                                  }    dichiarata prima)
#   BIG1M   un singolo modulo >= 1 M$
#   PCT20   un singolo modulo che aumenta la posizione diretta di almeno il 20%, valore >= 100k$
#   CEO100  CEO/CFO/President, >= 100k$ nei 90 giorni
# Varianti provate in tutto: 7 (queste). Nessuna aggiunta dopo aver visto i risultati, salvo quelle segnate "a posteriori" nel rapporto.
import os, numpy as np, pandas as pd
ML = os.path.dirname(os.path.abspath(__file__)); OUT = f'{ML}/f2'
A = pd.read_pickle(f'{OUT}/acquisti_dirigenti.pkl'); L = pd.read_pickle(f'{OUT}/link_cik_codice.pkl')
X = A.merge(L[['cik', 't', 'first', 'last']], on='cik')
X = X[(X.filed >= X['first'] - pd.Timedelta(days=60)) & (X.filed <= X['last'] + pd.Timedelta(days=60))]
X = X.sort_values(['t', 'filed'])
print('moduli assegnati a un codice', len(X), '| codici', X.t.nunique())
DATES = pd.date_range('2005-12-31', '2026-09-30', freq='QE')
MIN_INS = 25_000
FRESH = int(os.environ.get('FRESH', '90'))   # controllo a posteriori: FRESH=30 = evento negli ultimi 30 giorni prima della data


def events(g):
    """date-evento per ciascun segnale, per un codice"""
    ev = {k: [] for k in ('ANY', 'C2_30', 'C2_90', 'C3_90', 'BIG1M', 'PCT20', 'CEO100')}
    f = g.filed.values; o = g.owner_cik.fillna(g.owner).values; v = g.val.values; ce = g.ceo_cfo.values
    for i in range(len(g)):
        fi = f[i]
        for W, k, lab in ((30, 2, 'C2_30'), (90, 2, 'C2_90'), (90, 3, 'C3_90'), (90, 1, 'ANY')):
            m = (f >= fi - np.timedelta64(W, 'D')) & (f <= fi)
            s = pd.Series(v[m]).groupby(o[m]).sum()
            if (s >= MIN_INS).sum() >= k and s.get(o[i], 0) >= MIN_INS: ev[lab].append(fi)
        if v[i] >= 1e6: ev['BIG1M'].append(fi)
        if g.pct_hold.values[i] >= 0.2 and v[i] >= 1e5: ev['PCT20'].append(fi)
        m = (f >= fi - np.timedelta64(90, 'D')) & (f <= fi) & ce
        if ce[i] and v[m].sum() >= 1e5: ev['CEO100'].append(fi)
    return ev


rows = []
for t, g in X.groupby('t'):
    ev = events(g)
    fv = g.filed.values
    for d in DATES:
        lo = d - pd.Timedelta(days=FRESH)
        r = {'t': t, 'date': d}
        any_on = False
        for k, e in ev.items():
            e = np.array(e, dtype='datetime64[ns]')
            r[k] = bool(((e > np.datetime64(lo)) & (e <= np.datetime64(d))).any()); any_on |= r[k]
        m = (fv > np.datetime64(lo)) & (fv <= np.datetime64(d))
        r['n_ins90'] = int(pd.Series(g.val.values[m]).groupby(g.owner_cik.fillna(g.owner).values[m]).sum().ge(MIN_INS).sum()) if m.any() else 0
        r['val90'] = float(g.val.values[m].sum())
        if any_on or r['val90'] > 0: rows.append(r)
S = pd.DataFrame(rows)
S.to_pickle(f'{OUT}/segnali_trim.pkl' if FRESH == 90 else f'{OUT}/segnali_trim_fresh{FRESH}.pkl')
print('righe (codice, trimestre) con almeno un acquisto:', len(S))
print(S.groupby(S.date.dt.year)[['ANY', 'C2_30', 'C2_90', 'C3_90', 'BIG1M', 'PCT20', 'CEO100']].sum().to_string())
