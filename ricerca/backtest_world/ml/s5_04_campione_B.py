# Storico 2000-2011, punto 5.1 (allargato): quota di societa' americane uscite prima del 2011 con i bilanci in EODHD.
# Campione: per ogni anno di uscita 1999-2011, le 10 piu' scambiate (mediana degli scambi giornalieri nell'ultimo anno di quotazione),
# fra i prezzi scaricati oggi (storico5/raw/prezzi_us). Esclusi i nomi gia' provati (s5_01, h02). 10 crediti l'una.
import os, glob, json, pickle, pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor
from s5_common import get, usage, guard, OUT, ML
RAW = f'{OUT}/raw/fond_B'; os.makedirs(RAW, exist_ok=True)
done = {os.path.basename(f)[:-5] for f in glob.glob(f'{OUT}/raw/fond_verifica/*.json')}
done |= set(pickle.load(open(f'{ML}/sopravv/fond_campione.pkl', 'rb')).keys())
rows = []
for fn in glob.glob(f'{OUT}/raw/prezzi_us/*.pkl'):
    d = pd.read_pickle(fn)
    if d is None or d.empty: continue
    last = d.date.max()
    if last >= pd.Timestamp('2011-06-30') or last < pd.Timestamp('1999-01-01'): continue
    x = d[d.date >= last - pd.Timedelta(days=365)]
    rows.append((os.path.basename(fn)[:-4], last, float((x.c * x.v).median()), float(x.c.median())))
S = pd.DataFrame(rows, columns=['t', 'last', 'dv', 'px'])
S = S[~S.t.isin(done) & (S.px >= 3)]
S['yr'] = S['last'].dt.year
pick = S.sort_values('dv', ascending=False).groupby('yr').head(10).sort_values(['yr', 'dv'], ascending=[True, False])
print('candidati per anno', S.groupby('yr').size().to_dict(), '| scelti', len(pick))
guard(95900); u0 = usage()


def one(t):
    fn = f'{RAW}/{t}.json'
    if os.path.exists(fn): return t, json.load(open(fn))
    j = get(f'fundamentals/{t}')
    if j not in ('ERR', 'LIMIT'): json.dump(j, open(fn, 'w'))
    return t, j


with ThreadPoolExecutor(6) as P: res = dict(P.map(one, pick.t))
print('crediti', u0, '->', usage())
out = []
for r in pick.itertuples():
    j = res.get(r.t); g = (j or {}).get('General', {}) if isinstance(j, dict) else {}
    F = (j or {}).get('Financials', {}) if isinstance(j, dict) else {}
    iy = (F.get('Income_Statement', {}) or {}).get('yearly') or {}
    iq = (F.get('Income_Statement', {}) or {}).get('quarterly') or {}
    by = (F.get('Balance_Sheet', {}) or {}).get('yearly') or {}
    sh = [v.get('commonStockSharesOutstanding') for v in by.values() if v.get('commonStockSharesOutstanding')]
    fil = [v.get('filing_date') for v in list(iy.values()) + list(iq.values()) if v.get('filing_date')]
    ni = [v.get('netIncome') for v in iy.values() if v.get('netIncome')]
    osh = sum(len(v or {}) for v in ((j or {}).get('outstandingShares') or {}).values()) if isinstance(j, dict) else 0
    out.append({'t': r.t, 'nome': g.get('Name'), 'ultimo_prezzo': r.last.date(), 'anno': r.yr, 'scambi_M$': round(r.dv / 1e6, 1),
                'CE_annuali': len(iy), 'CE_trimestrali': len(iq), 'SP_annuali': len(by), 'con_utile_netto': len(ni),
                'con_azioni_SP': len(sh), 'storico_azioni': osh, 'con_data_deposito': len(fil),
                'primo_anno': min(iy) if iy else None, 'ultimo_anno': max(iy) if iy else None})
O = pd.DataFrame(out); O.to_csv(f'{OUT}/campione_B_bilanci.csv', index=False)
O['ha_bilanci'] = O.CE_annuali > 0
print(O.groupby('anno').agg(n=('t', 'size'), con_bilanci=('ha_bilanci', 'sum'), con_azioni=('con_azioni_SP', lambda x: (x > 0).sum()),
                            con_data=('con_data_deposito', lambda x: (x > 0).sum())).to_string())
print(O[O.ha_bilanci].to_string())
