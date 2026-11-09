# Verifica avversariale prova B: Crescita (regole Moonshot) con e senza le righe con salti finti; peso dei singoli nomi.
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
ML = '${RICERCA_BASE}/backtest_world/ml'; BW = os.path.dirname(ML)
sys.path.insert(0, ML); sys.path.insert(0, BW)
F = pd.read_pickle(f'{ML}/storico5/provaB/matrice_B.pkl').merge(pd.read_pickle(f'{ML}/avv_B_out/flag_salti_finti.pkl'), on=['t', 'date'], how='left')
TEST = (F.anno >= 2006) & (F.anno <= 2011); UNI = ~F.excl_sector; mc = F.mcap_usd
fcf, cash, debt = F.fcf_ttm, F.cash, F.debt
runway = (fcf >= 0) | fcf.isna() | ((cash / fcf.abs()) > 2)
debt_ok = (debt <= 0) | debt.isna() | ((cash > 0) & (debt / cash <= 2)) | ((F.opi_ttm > 0) & ((debt - cash.fillna(0)) / F.opi_ttm <= 2.5))
liq_ok = F.cur_ratio.isna() | (F.cur_ratio > 1.2) | (cash >= debt); dil_ok = F.dshares.isna() | (F.dshares < 0.15)
MB = (UNI & (F.rev_usd > 100e6) & (F.revq > 0.25) & (F.gm > 0.25) & (F.ma200 > 1) & runway & debt_ok & liq_ok & dil_ok).fillna(False)
CR = MB & (F.hi52 >= 0.70).fillna(False)
DT = sorted(F.date[TEST].unique())
def geo(r): r = np.asarray(r, float); return np.prod(1 + r) ** (4 / len(r)) - 1
def port(m, cost=0.005):
    d = F[m & TEST]; Gd = {t: x for t, x in d.groupby('date')}; r, prev = [], set()
    for t in DT:
        x = Gd.get(t); k = set(x.t) if x is not None else set(); g = x.f3.mean() if x is not None and len(x) else 0.0
        sold = len(prev - k) / len(prev) if prev else 0; bought = len(k - prev) / len(k) if k else 0
        r.append(g - cost * (sold + bought)); prev = k
    return np.array(r)
for lab, ex in [('principale', pd.Series(False, index=F.index)), ('senza salti finti', F.bad3.fillna(False))]:
    rc = port(CR & ~ex); ru = F[UNI & TEST & ~ex].groupby('date').f3.mean().reindex(DT).values
    print(f'Crescita tutte le taglie, {lab}: {geo(rc) - geo(ru):+.4f}')
d = F[CR & TEST].copy(); d['contr'] = d.f3 / d.groupby('date').t.transform('count')
c = d.groupby(['t', 'name']).contr.sum()
print('peggiori 5:', c.nsmallest(5).round(3).to_dict()); print('migliori 5:', c.nlargest(5).round(3).to_dict())
print('righe con salto finto nella lista Crescita:', int((CR & TEST & F.bad3.fillna(False)).sum()))
