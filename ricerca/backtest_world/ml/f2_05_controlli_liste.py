# F2 passo 5: (a) t su date non sovrapposte CONTRO IL CASO A PARITA' di data, taglia, volatilita' e distanza dal massimo
# (il confronto giusto: gli insider comprano dopo i cali, quando il titolo e' piu' volatile); anche senza banche/finanza/materie
# prime (nomi esclusi dal GARP). (b) Dentro le liste: GARP core, Crescita (regole Moonshot), Qualita' durevole (Q3), 2012-2026
# (panel2 + scr_common, solo USA); core e Crescita anche 2006-2011 (matrice_B della prova B, solo sopravvissute).
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML); OUT = f'{ML}/f2'
sys.path.insert(0, BW); sys.path.insert(0, ML)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 400)
SIG = ['ANY', 'C2_30', 'C2_90', 'C3_90', 'BIG1M', 'PCT20', 'CEO100']
U = pd.read_pickle(f'{OUT}/pannello_f2.pkl')
ex = pd.read_pickle(f'{ML}/storico5/universo_prezzi_us_v2.pkl')[['t', 'date', 'excl']]
U = U.merge(ex, on=['t', 'date'], how='left')
U['ok12'] = U.f12c.notna(); U['ok36'] = U.f36.notna() & (U.date <= '2022-12-31')
CELL = ['date', 'taglia', 'vq', 'pq']


def t_matched(D, s, tgt, okc, step):
    x = D[D[okc] & D.taglia.notna()].copy()
    x['exp'] = x.groupby(CELL, observed=True)[tgt].transform('mean')       # tasso atteso di un nome a caso della stessa cella
    y = x[x[s]]
    g = y.groupby('date').agg(n=(tgt, 'size'), o=(tgt, 'mean'), e=('exp', 'mean'))
    g = g[g.n >= 5]; dif = g.o - g.e
    dd = sorted(x.date.unique()); idx = {d: i for i, d in enumerate(dd)}
    ts, ms = [], []
    for off in range(step):
        v = dif[[idx[d] % step == off for d in dif.index]]
        if len(v) >= 3 and v.std() > 0: ts.append(v.mean() / v.std() * np.sqrt(len(v)))
    return y[tgt].mean(), y.exp.mean(), (np.mean(ts) if ts else np.nan), (min(ts, key=abs) if ts else np.nan), len(dif) // step


rows = []
for lab, D in [('tutto', U), ('senza finanza/materie prime', U[~U.excl.fillna(False)])]:
    for per in ['tutti', '2006-11', '2012-17', '2018-24']:
        for tg in ['tutte', 'piccole 0,3-2', 'medie 2-15', 'grandi >15']:
            X = D if per == 'tutti' else D[D.per == per]
            X = X if tg == 'tutte' else X[X.taglia == tg]
            for s in SIG:
                r = dict(universo=lab, periodo=per, taglia=tg, segnale=s, n=int(X[X.ok12][s].sum()))
                for tgt, okc, step in (('W5', 'ok12', 4), ('X3', 'ok36', 12), ('L50', 'ok12', 4)):
                    if per != 'tutti' and tgt == 'X3': step = 4      # nei sotto-periodi: t su date annuali (sovrapposte a 3 anni)
                    o, e, t, tm, ny = t_matched(X, s, tgt, okc, step)
                    r.update({f'{tgt}': o, f'{tgt}_casoV': e, f'{tgt}_tV': t, f'{tgt}_tVmin': tm})
                rows.append(r)
R = pd.DataFrame(rows); R.to_csv(f'{OUT}/tab_contro_caso_vol.csv', index=False)
print(R[(R.taglia == 'tutte') | (R.periodo == 'tutti')].round(3).to_string())
# ------------------------------------------------------------------ (b) liste
import scr_common as sc
F = sc.F
us = F.t.str.endswith('.US') & F.liq.fillna(False) & (F.mcap_usd >= 3e8)
LIST = {'GARP core': sc.CORE, 'Crescita': sc.CR, 'Qualita': sc.Q3}
X = F.loc[us, ['t', 'date', 'f12', 'f36', 'mcap_usd']].copy()
for k, m in LIST.items(): X[k] = m[us].values
X['t'] = X.t.str.replace('.US', '', regex=False)
X = X.merge(pd.read_pickle(f'{OUT}/segnali_trim.pkl'), on=['t', 'date'], how='left')
for s in SIG: X[s] = X[s].fillna(False).astype(bool)
X['ok12'] = X.f12.notna(); X['ok36'] = X.f36.notna()
X['W5'] = (X.groupby('date').f12.rank(pct=True) >= 0.95) & X.ok12
X['L50'] = (X.f12 <= -0.5) & X.ok12; X['X3'] = (X.f36 >= 2.0) & X.ok36
X['anno'] = (X.date + pd.Timedelta(days=1)).dt.year
X['per'] = pd.cut(X.anno, [2011, 2017, 2026], labels=['2012-17', '2018-26'])
# 2006-2011: core e Crescita dalla matrice della prova B (solo sopravvissute), esiti dall'universo di soli prezzi
B = pd.read_pickle(f'{ML}/storico5/provaB/matrice_B.pkl')
B = B[(B.date >= '2005-12-31') & (B.date <= '2011-09-30')]
from tune_common import mask, BASE_P
mc = B.mcap_usd; UNI = ~B.excl_sector
fcf, cash, debt = B.fcf_ttm, B.cash, B.debt
runway = (fcf >= 0) | fcf.isna() | ((cash / fcf.abs()) > 2)
debt_ok = (debt <= 0) | debt.isna() | ((cash > 0) & (debt / cash <= 2)) | ((B.opi_ttm > 0) & ((debt - cash.fillna(0)) / B.opi_ttm <= 2.5))
liq_ok = B.cur_ratio.isna() | (B.cur_ratio > 1.2) | (cash >= debt)
dil_ok = B.dshares.isna() | (B.dshares < 0.15)
MB = (UNI & (B.rev_usd > 100e6) & (B.revq > 0.25) & (B.gm > 0.25) & (B.ma200 > 1) & runway & debt_ok & liq_ok & dil_ok).fillna(False)
B['GARP core'] = (mask(B, dict(BASE_P, revq=0.20)) & (B.hi52 >= 0.8).fillna(False) & (mc >= 2e9) & ~(B.peg < 0.05).fillna(False)).values
B['Crescita'] = (MB & (B.hi52 >= 0.70).fillna(False)).values
B['Qualita'] = False
Y = B[['t', 'date', 'GARP core', 'Crescita', 'Qualita']].merge(U[['t', 'date', 'W5', 'L50', 'X3', 'ok12', 'ok36', 'f12c'] + SIG], on=['t', 'date'])
Y['per'] = '2006-11'
Z = pd.concat([Y, X[['t', 'date', 'GARP core', 'Crescita', 'Qualita', 'W5', 'L50', 'X3', 'ok12', 'ok36', 'per'] + SIG]], ignore_index=True)
Z.to_pickle(f'{OUT}/liste_segnali.pkl')
rows = []
for k in LIST:
    for per in ['2006-11', '2012-17', '2018-26', 'tutti']:
        D = Z[Z[k] & ((Z.per == per) if per != 'tutti' else True)]
        if not len(D): continue
        for s in SIG:
            r = dict(lista=k, periodo=per, segnale=s, righe_lista=int(D.ok12.sum()), n_sig=int(D[D.ok12][s].sum()), nomi_sig=D[D[s]].t.nunique())
            for tgt, okc in (('W5', 'ok12'), ('X3', 'ok36'), ('L50', 'ok12')):
                y = D[D[okc]]
                # atteso = media della lista nella stessa data (il "caso" dentro la lista)
                e = y.groupby('date')[tgt].transform('mean')
                r[f'{tgt}_sig'] = y[y[s]][tgt].mean(); r[f'{tgt}_lista'] = e[y[s]].mean(); r[f'{tgt}_nsig'] = int(y[s].sum())
            rows.append(r)
R2 = pd.DataFrame(rows); R2.to_csv(f'{OUT}/tab_liste.csv', index=False)
print(R2.round(3).to_string())
