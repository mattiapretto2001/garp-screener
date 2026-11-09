# f4_06: famiglia B. B1 quota insider point-in-time dalla SEC (f4_03); B2 fondatore alla guida, flag di OGGI (EODHD
# General::Officers del campione casuale USA f4_02), provato solo su date recenti 2023-09..2025-09 (e, come variante
# dichiarata e distorta, dal 2018).
import os, json, glob, numpy as np, pandas as pd
from f4_common import load, evaluate, fmt, OUT
F = load()
Q = pd.read_pickle(f'{OUT}/ins_sec.pkl')
F = F.merge(Q[['t', 'date', 'ins_sec', 'n_ins']], on=['t', 'date'], how='left').set_index(F.index)
F.loc[F.ins_sec > 1, 'ins_sec'] = np.nan            # piu' del 100%: doppi conteggi o simbolo sbagliato
us = (F.reg == 'USA')
print('copertura USA ins_sec:', round(F.loc[us, 'ins_sec'].notna().mean(), 3), 'quantili', F.loc[us, 'ins_sec'].quantile([.25, .5, .75, .9]).round(3).to_dict())
print('quota >=10%:', round((F.loc[us, 'ins_sec'] >= .1).mean(), 3), '>=25%:', round((F.loc[us, 'ins_sec'] >= .25).mean(), 3))
R = []
b = us & F.ins_sec.notna()
R.append(evaluate(F, F.ins_sec >= 0.10, b, 'B1 insider >=10% [USA]'))
R.append(evaluate(F, F.ins_sec >= 0.25, b, 'B1b insider >=25% [USA]'))
R.append(evaluate(F, F.ins_sec < 0.01, b, 'B1c insider <1% [USA] (controllo)'))
for lst in ['GARP', 'core']:
    R.append(evaluate(F, F.ins_sec >= 0.10, b & F[lst], f'B1 insider >=10% dentro {lst}'))
# ---- validazione con il dato di oggi (EODHD SharesStats.PercentInsiders, campione)
rows = []
for p in glob.glob(f'{OUT}/eodhd_campione/*.US.json'):
    t = os.path.basename(p)[:-5]; j = json.load(open(p))
    ss = j.get('SharesStats') if isinstance(j.get('SharesStats'), dict) else {}
    of = j.get('General::Officers') if isinstance(j.get('General::Officers'), dict) else {}
    tits = [str(o.get('Title', '')).lower() for o in of.values()]
    fceo = any('founder' in x and ('ceo' in x or 'chief executive' in x) for x in tits)
    fany = any('founder' in x for x in tits)
    rows.append((t, ss.get('PercentInsiders'), fceo, fany, len(of) > 0))
O = pd.DataFrame(rows, columns=['t', 'ins_oggi', 'founder_ceo', 'founder_any', 'has_off'])
last = F[us & F.ins_sec.notna()].sort_values('date').groupby('t').tail(1)[['t', 'date', 'ins_sec']]
V = O.merge(last, on='t'); V = V[V.date >= '2025-06-30']
print('validazione SEC vs EODHD oggi: n', len(V), 'Spearman', round(V[['ins_oggi', 'ins_sec']].corr('spearman').iloc[0, 1], 2),
      'mediana SEC', round(V.ins_sec.median() * 100, 1), '% oggi', round(V.ins_oggi.median(), 1), '%')
print('campione con dirigenti:', O.has_off.sum(), 'fondatore-CEO:', O.founder_ceo.sum(), 'fondatore fra i dirigenti:', O.founder_any.sum())
F = F.merge(O, on='t', how='left').set_index(F.index)
hb = F.has_off.fillna(False).astype(bool)
rec = (F.date >= '2023-09-30')
R.append(evaluate(F, F.founder_ceo.fillna(False).astype(bool), hb & rec, 'B2 fondatore-CEO (oggi) date 2023-25 [campione USA]'))
R.append(evaluate(F, F.founder_any.fillna(False).astype(bool), hb & rec, 'B2b fondatore fra i dirigenti (oggi) 2023-25 [campione USA]'))
R.append(evaluate(F, F.founder_ceo.fillna(False).astype(bool), hb & (F.date >= '2018-03-31'), 'B2 fondatore-CEO (oggi) dal 2018 - DISTORTO [campione USA]'))
ins_t = F.ins_oggi.astype(float) >= 10
R.append(evaluate(F, ins_t, F.ins_oggi.notna() & rec, 'B1d insider >=10% (dato di oggi) 2023-25 [campione USA]'))
# controlli aggiunti DOPO aver visto i risultati (dichiarati come tali): togliere le quotate da meno di 3 anni
old = ~(F.age_y < 3)
R.append(evaluate(F, F.ins_sec >= 0.10, b & old, 'B1 insider >=10% senza quotate <3 anni [USA] (controllo a posteriori)'))
R.append(evaluate(F, F.founder_ceo.fillna(False).astype(bool), hb & rec & old, 'B2 fondatore-CEO 2023-25 senza quotate <3 anni (controllo a posteriori)'))
print('sovrapposizione: fondatore-CEO con eta<3 anni', round((F.founder_ceo.fillna(False).astype(bool) & rec & (F.age_y < 3)).sum() / max((F.founder_ceo.fillna(False).astype(bool) & rec).sum(), 1), 2),
      '; insider>=10% con eta<3', round(((F.ins_sec >= .1) & (F.age_y < 3)).sum() / (F.ins_sec >= .1).sum(), 2))
D = pd.concat(R, ignore_index=True); fmt(D).to_csv(f'{OUT}/f4_06_insider_fondatori.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
print(fmt(D).to_string())
