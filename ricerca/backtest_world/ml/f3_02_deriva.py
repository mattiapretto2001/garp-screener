# f3_02 (09/11): DERIVA DOPO L'ANNUNCIO (PEAD) a livello di singolo annuncio.
# Ingresso alla chiusura del 4o giorno dall'annuncio (d0+3), rendimento anomalo (meno la media della borsa) a 3/6/12 mesi.
# Gruppi per trimestre di calendario dell'annuncio e area (USA / resto del mondo). Segnali fissati prima:
#  (a) SUE = sorpresa / dev. std delle 8 sorprese precedenti (variante dichiarata: sorpresa % EODHD)
#  (b) EAR = rendimento anomalo dei 3 giorni dell'annuncio
#  (c) serie di battute consecutive: 0, 1, 2-3, 4-7, 8+
#  (d) combinazione: SUE nel quinto alto E EAR nel quinto alto
# KO e TW esclusi dai segnali con EAR: le date degli annunci non sono affidabili (|EAR| solo 1,1-1,2 volte un giorno qualsiasi).
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fv3
OUT = f'{HERE}/f3_out'
E = pd.read_pickle(f'{OUT}/eventi.pkl')
F = pd.read_pickle(f'{HERE}/features_v3.pkl')[['t', 'date', 'reg_rob', 'mcap_usd']]
# solo annunci di societa' nell'universo (>=300 M$, liquide) all'ultima fine trimestre prima dell'annuncio (entro 95 giorni)
E = E.sort_values('rd'); F = F.sort_values('date')
E = pd.merge_asof(E, F.rename(columns={'date': 'fdate'}), left_on='rd', right_on='fdate', by='t', direction='backward',
                  tolerance=pd.Timedelta(days=95))
E = E[E.fdate.notna() & (E.rd >= '2012-01-01')].copy()
E['area'] = np.where(E.ex == 'US', 'USA', 'Resto')
E['q'] = E.rd.dt.to_period('Q')
E['earok'] = ~E.ex.isin(['KO', 'TW'])
# rendimenti: taglio all'1-99% per area e anno (errori di prezzo)
for h in ['d3m', 'd6m', 'd12m']:
    g = E.groupby(['area', E.rd.dt.year])[h]
    E[h] = E[h].clip(g.transform(lambda s: s.quantile(0.01)), g.transform(lambda s: s.quantile(0.99)))


def quint(col, mask):
    x = E[col].where(mask & np.isfinite(E[col]))
    g = x.groupby([E.area, E.q])
    r = (g.rank(method='first') - 0.5) / g.transform('count')
    return np.floor(r * 5).clip(0, 4) + 1


E['Q_sue'] = quint('sue', E.Est.notna())
E['Q_spct'] = quint('spct', E.Est.abs() > 0.01)
E['Q_ear'] = quint('ear', E.earok)
E['B_streak'] = pd.cut(E.streak, [-1, 0, 1, 3, 7, 99], labels=['0', '1', '2-3', '4-7', '8+'])
E['combo'] = np.where(E.Q_sue.isna() | E.Q_ear.isna(), np.nan, ((E.Q_sue == 5) & (E.Q_ear == 5)).astype(float))
E['combo_neg'] = np.where(E.Q_sue.isna() | E.Q_ear.isna(), np.nan, ((E.Q_sue == 1) & (E.Q_ear == 1)).astype(float))
E['sue_rifiutata'] = np.where(E.Q_sue.isna() | E.Q_ear.isna(), np.nan, ((E.Q_sue == 5) & (E.Q_ear == 1)).astype(float))
E.to_pickle(f'{OUT}/eventi_q.pkl')

PER = {'2012-26': ('2012-01-01', '2026-12-31'), '2012-17': ('2012-01-01', '2017-12-31'), '2018-26': ('2018-01-01', '2026-12-31'),
       '2018-21': ('2018-01-01', '2021-12-31'), '2022-26': ('2022-01-01', '2026-12-31')}
LAG = {'d3m': 1, 'd6m': 2, 'd12m': 4}
rows = []


def spread(X, col, hi, lo, h):
    s = X[X[col] == hi].groupby('q')[h].mean() - X[X[col] == lo].groupby('q')[h].mean()
    return s.mean(), fv3.nw_t(s, LAG[h])


for area in ['USA', 'Resto', 'USA grandi', 'USA piccole/medie']:
    A = E[E.area == area] if area in ('USA', 'Resto') else E[(E.area == 'USA') & (E.reg_rob == area)]
    for pn, (a, b) in PER.items():
        X = A[(A.rd >= a) & (A.rd <= b)]
        for sig, col, hi, lo in [('a SUE', 'Q_sue', 5, 1), ('a2 sorpresa %', 'Q_spct', 5, 1), ('b EAR', 'Q_ear', 5, 1),
                                 ('c serie battute', 'B_streak', '8+', '0'), ('c2 serie 4+ vs 0', 'B_streak', '4-7', '0'),
                                 ('d combo', 'combo', 1.0, 0.0), ('d2 doppio negativo', 'combo_neg', 1.0, 0.0)]:
            r = dict(area=area, per=pn, segnale=sig, n=int((X[col] == hi).sum()))
            for h in ['d3m', 'd6m', 'd12m']:
                m, t = spread(X, col, hi, lo, h)
                r[h] = m; r[h + '_t'] = t
                r[h + '_alto'] = X[X[col] == hi].groupby('q')[h].mean().mean()
            rows.append(r)
R = pd.DataFrame(rows)
R.to_csv(f'{OUT}/f3_02_spread.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
print(R[R.per.isin(['2012-26', '2018-26', '2012-17'])].round(3).to_string())

# profilo per quintile (USA e Resto, 2012-26 e 2018-26): deriva media a 3 e 12 mesi
for area in ['USA', 'Resto']:
    for col in ['Q_sue', 'Q_ear', 'B_streak']:
        X = E[E.area == area]
        print(area, col)
        print(X.groupby([col, X.rd.dt.year >= 2018])[['d3m', 'd12m', 'ear']].mean().unstack().round(4))
