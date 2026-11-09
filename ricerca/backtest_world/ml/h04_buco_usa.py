# Storico 2000-2011, fase 4: quanto manca dell'universo USA 2000-2010 (istantanee semestrali EODHD, nessuna chiamata).
# Per ogni data: azioni ordinarie NYSE/Nasdaq/NYSE American con prezzo >=3$ e scambi del giorno >=3 M$,
# esclusi nomi tipici di banche/REIT/SPAC/minerarie/energia (come world_10). Ogni titolo e' messo in una di tre classi:
#   A = gia' nei nostri dati (prezzi dal 1998 + bilanci in fund/fund2), riconosciuto dal prezzo di chiusura identico;
#   B = uscito dal listino prima di meta' 2011 (EODHD ha i prezzi ma NON i bilanci: verificato su 10 nomi);
#   C = ancora quotato dopo il 2011 ma non nei nostri dati (bilanci scaricabili domani, 10 crediti l'uno).
import os, sys, glob, json, pickle, pandas as pd, numpy as np
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML); sys.path.insert(0, BW)
from world_common import symbols
SO = f'{ML}/sopravv'
s = symbols('US'); s['base'] = s.Code.str.replace(r'_old\d*', '', regex=True)
pat = r'\b(?:Bank|Banc|Bancorp|Bancshares|Financial|Acquisition|Trust|REIT|Realty|Properties|Insurance|Petroleum|Mining|Gold|Fund|Capital Corp|Investment|Energy|Oil|Gas|Resources|Utilities|Power|Electric)\b'
s['escl'] = s.Name.fillna('').str.contains(pat, case=False, regex=True)
b11 = pd.read_pickle(f'{BW}/eod/bulk_US.pkl'); codes11 = set(b11.code)
dl = s[s.delisted == 1]
pre11 = set(dl[~dl.Code.str.contains('_old') & ~dl.Code.isin(codes11)].Code) | set(dl[dl.Code.str.contains('_old')].base)
base_codes = set(s.base)
escl_base = s.groupby('base').escl.max()
# prezzi di chiusura dei nostri ticker alle date delle istantanee
L = pd.read_pickle(f'{ML}/eod_lungo/US.pkl.gz')
rows = []; detail = []
for fn in sorted(glob.glob(f'{SO}/bulk_US_*.pkl')):
    d0 = pd.Timestamp(os.path.basename(fn)[8:18])
    b = pd.read_pickle(fn); dd = pd.Timestamp(b.date.iloc[0])
    b = b[b.code.isin(base_codes)]
    b = b[(b.close >= 3) & (b.close * b.volume >= 3e6)].copy()
    b['escl'] = b.code.map(escl_base).fillna(False).astype(bool)
    x = L[L.date == dd][['t', 'c']]
    have_px = set(zip(x.t.astype(str).str.replace(r'_old\d*', '', regex=True), (x.c.astype('float64') * 100).round().astype('int64')))
    b['A'] = [(c, int(round(float(p) * 100))) in have_px for c, p in zip(b.code, b.close)]
    b['B'] = ~b.A & b.code.isin(pre11)
    b['C'] = ~b.A & ~b.B
    b['date'] = d0
    detail.append(b[['date', 'code', 'close', 'volume', 'escl', 'A', 'B', 'C']])
    k = b[~b.escl]
    rows.append({'data': d0.strftime('%Y-%m'), 'liquidi': len(k), 'A_gia_nostri': int(k.A.sum()), 'B_usciti_pre2011': int(k.B.sum()),
                 'C_scaricabili': int(k.C.sum()), 'quota_A': round(k.A.mean(), 2), 'quota_B': round(k.B.mean(), 2)})
R = pd.DataFrame(rows); print(R.to_string(index=False))
D = pd.concat(detail, ignore_index=True); D.to_pickle(f'{SO}/buco_usa_dettaglio.pkl'); R.to_csv(f'{SO}/buco_usa.csv', index=False)
# candidati per domani: titoli liquidi in >=3 istantanee 2000-2010 (stessa regola usata per il 2011+)
k = D[~D.escl]
n = k.groupby('code').agg(n=('date', 'size'), A=('A', 'max'), B=('B', 'max'), C=('C', 'max'))
cand = n[n.n >= 3]
print('titoli unici liquidi in >=3 istantanee (esclusi settori):', len(cand), '| gia nostri', int(cand.A.sum()),
      '| usciti pre-2011 (solo prezzi)', int((cand.B & ~cand.A).sum()), '| scaricabili (classe C, mai A)', int((cand.C & ~cand.A & ~cand.B).sum()))
cand.to_pickle(f'{SO}/candidati_usa_2000_2010.pkl')
