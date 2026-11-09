# Verifica avversariale Prova C: indice mondiale in euro ricalcolato da me, in modo diverso (ribilanciamento 50/50 mensile sui
# valori di fine mese, invece che giornaliero), dai file grezzi; VWCE 2012-26 dai prezzi di eod/bench.pkl.
import json, pickle, numpy as np, pandas as pd
ML = '${RICERCA_BASE}/backtest_world/ml'; BW = ML.rsplit('/', 1)[0]
def raw(n):
    d = pd.DataFrame(json.load(open(f'{ML}/regoleC/raw/{n}.json'))); d.index = pd.to_datetime(d.date); return d.adjusted_close.astype(float)
vt, vg, fx = raw('VTSMX.US'), raw('VGTSX.US'), raw('EURUSD.FOREX')
m = pd.concat([vt, vg, fx], axis=1, keys=['vt', 'vg', 'fx']).ffill().resample('ME').last()
m = m['1999-12-31':'2011-12-31']
r = 0.5 * m.vt.pct_change() + 0.5 * m.vg.pct_change()
eur = (1 + r).cumprod() / m.fx * m.fx.iloc[0]
yrs = (m.index[-1] - m.index[0]).days / 365.25
print('proxy indice mondiale in euro 31/12/1999-31/12/2011, CAGR', round((eur.iloc[-1]) ** (1 / yrs) - 1, 4))
v = eur.fillna(1.0); print('perdita massima mensile', round((v / v.cummax() - 1).min(), 3))
B = pickle.load(open(f'{BW}/eod/bench.pkl', 'rb')); FX = pd.read_pickle(f'{BW}/eod/fx.pkl').sort_index().ffill()
vtw = B['VT.US'].a.astype(float); vtw = vtw / FX.EUR.reindex(vtw.index).ffill()
vw = B['VWCE.XETRA'].a.astype(float)
a = vtw['2011-12-30':'2019-09-30']; b = vw['2019-09-30':'2026-11-05']
tot = (a.iloc[-1] / a.iloc[0]) * (b.iloc[-1] / b.iloc[0]); y2 = (b.index[-1] - a.index[0]).days / 365.25
print('VT in euro poi VWCE, 30/12/2011 -', b.index[-1].date(), 'CAGR', round(tot ** (1 / y2) - 1, 4))
print('solo VWCE 2019-10 -', b.index[-1].date(), round((b.iloc[-1] / b.iloc[0]) ** (365.25 / (b.index[-1] - b.index[0]).days) - 1, 4))
