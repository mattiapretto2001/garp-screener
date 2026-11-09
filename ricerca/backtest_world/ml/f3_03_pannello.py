# f3_03 (09/11): i segnali sugli utili nel PANNELLO TRIMESTRALE (come lo screener): a ogni fine trimestre si usa l'ultimo
# annuncio gia' noto (fine della finestra di 3 giorni prima della data, annuncio entro 120 giorni).
# Target: rendimento 3/6/12 mesi (in eccesso sulla media dell'area alla data), 5% migliore, 20% peggiore, crollo -50%, x3 in 3 anni.
# Confronto con n_beat4 (stime battute, il segnale gia' noto). Poi: dentro le liste, costi (rotazione), scelte a caso.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fv3
from profili_common import profiles
OUT = f'{HERE}/f3_out'
COST = 0.005
E = pd.read_pickle(f'{OUT}/eventi.pkl')
F = fv3.load()
F['area'] = np.where(F.ex == 'US', 'USA', 'Resto')
P, _ = profiles(F)
F['L_GARP'] = F.GARP.fillna(False).astype(bool); F['L_core'] = F.core.fillna(False).astype(bool)
F['L_Crescita'] = P['CRESC']; F['L_Qualita'] = P['QUAL']
# 6 mesi: r del trimestre e del trimestre dopo (stesso titolo, data successiva); manca se il titolo esce dal pannello
F = F.sort_values(['t', 'date'])
nx = F.groupby('t').date.shift(-1); rn = F.groupby('t').r.shift(-1)
F['f6'] = np.where(nx == F.date + pd.offsets.QuarterEnd(1), (1 + F.r) * (1 + rn) - 1, np.nan)
# ultimo annuncio noto alla data
E = E.sort_values('sig_day')[['t', 'sig_day', 'rd', 'sue', 'spct', 'ear', 'streak', 'Est']]
E['spct'] = E.spct.where(E.Est.abs() > 0.01)
F = F.sort_values('date')
F = pd.merge_asof(F, E.rename(columns={'sig_day': 'date_ev'}), left_on='date', right_on='date_ev', by='t',
                  direction='backward', allow_exact_matches=False)
fresh = (F.date - F.rd).dt.days <= 120
for c in ['sue', 'spct', 'ear', 'streak']: F[c] = F[c].where(fresh)
F['ear'] = F.ear.where(~F.ex.isin(['KO', 'TW']))
F.loc[F.Est.isna() | ~fresh, 'sue'] = np.nan
F.loc[F.Est.isna() | ~fresh, 'streak'] = np.nan


def qrank(col, by=('area', 'date')):
    g = F[col].groupby([F[b] for b in by])
    return (g.rank(method='first') - 0.5) / g.transform('count')


for c in ['sue', 'spct', 'ear', 'n_beat4', 'mom12_1']: F['rk_' + c] = qrank(c)
F['combo'] = np.where(F.rk_sue.isna() | F.rk_ear.isna(), np.nan, ((F.rk_sue >= 0.8) & (F.rk_ear >= 0.8)).astype(float))
# eccessi sull'area alla data
for c in ['r', 'f6', 'fwd12_eur']:
    F['x_' + c] = F[c] - F.groupby(['area', 'date'])[c].transform('mean')
F.to_pickle(f'{OUT}/pannello.pkl')

PER = {'2012-26': ('2011-12-31', '2026-09-30'), '2018-26': ('2018-03-31', '2026-09-30'), '2012-17': ('2011-12-31', '2017-12-31')}
SIG = {  # nome: (maschera alto, maschera basso)
    'a SUE': (F.rk_sue >= 0.8, F.rk_sue < 0.2), 'a2 sorpresa %': (F.rk_spct >= 0.8, F.rk_spct < 0.2),
    'b EAR': (F.rk_ear >= 0.8, F.rk_ear < 0.2), 'c serie >=4': (F.streak >= 4, F.streak == 0),
    'd combo': (F.combo == 1, F.combo == 0), 'rif. n_beat4 (4 su 4 vs 0-1)': (F.n_beat4 == 4, F.n_beat4 <= 1)}
RKC = {'a SUE': 'rk_sue', 'a2 sorpresa %': 'rk_spct', 'b EAR': 'rk_ear', 'c serie >=4': 'streak', 'd combo': 'combo',
       'rif. n_beat4 (4 su 4 vs 0-1)': 'n_beat4'}
TG = ['x_r', 'x_f6', 'x_fwd12_eur', 'top5_reg', 'bot20_reg', 'crash50', 'x3']


def ic(X, col):
    s = X.groupby('date').apply(lambda x: x[col].corr(x.rk12_reg, method='spearman') if x[[col, 'rk12_reg']].dropna().shape[0] > 30 else np.nan)
    return s.mean(), fv3.nw_t(s, 4)


rows = []
for area in ['USA', 'Resto']:
    for pn, (a, b) in PER.items():
        M = (F.area == area) & (F.date >= a) & (F.date <= b)
        for s, (hi, lo) in SIG.items():
            X = F[M]; m_ic, t_ic = ic(X, RKC[s])
            r = dict(area=area, per=pn, segnale=s, quota_alto=hi[M].mean(), ic=m_ic, ic_t=t_ic)
            base = M & (hi | lo | F[RKC[s]].notna())
            for tg in TG:
                r[tg + '_alto'] = F.loc[M & hi, tg].mean(); r[tg + '_basso'] = F.loc[M & lo, tg].mean(); r[tg + '_tutti'] = F.loc[base, tg].mean()
            # t della differenza alto-basso, serie per data (12 mesi: NW 4)
            d = F[M & hi].groupby('date').x_fwd12_eur.mean() - F[M & lo].groupby('date').x_fwd12_eur.mean()
            r['dx12_t'] = fv3.nw_t(d, 4)
            d = F[M & hi].groupby('date').x_r.mean() - F[M & lo].groupby('date').x_r.mean()
            r['dx3_t'] = fv3.nw_t(d, 1)
            rows.append(r)
R = pd.DataFrame(rows); R.to_csv(f'{OUT}/f3_03_pannello.csv', index=False)
pd.set_option('display.width', 300); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 300)
print(R.round(3).to_string())

# incremento: Fama-MacBeth di rk12_reg su ranghi (segnale + n_beat4 + momentum 12-1), mancanti = 0,5
inc = []
for area in ['USA', 'Resto']:
    for pn, (a, b) in PER.items():
        X = F[(F.area == area) & (F.date >= a) & (F.date <= b) & F.rk12_reg.notna()]
        for s in ['rk_sue', 'rk_spct', 'rk_ear']:
            co = []
            for d, x in X.groupby('date'):
                Z = x[[s, 'rk_n_beat4', 'rk_mom12_1']].fillna(0.5).values
                if len(x) < 50: continue
                A = np.column_stack([np.ones(len(x)), Z]); co.append(np.linalg.lstsq(A, x.rk12_reg.values, rcond=None)[0][1:])
            co = np.array(co)
            inc.append(dict(area=area, per=pn, segnale=s, coef=co[:, 0].mean(), t=fv3.nw_t(co[:, 0], 4),
                            coef_nbeat=co[:, 1].mean(), t_nbeat=fv3.nw_t(co[:, 1], 4), coef_mom=co[:, 2].mean(), t_mom=fv3.nw_t(co[:, 2], 4)))
I = pd.DataFrame(inc); I.to_csv(f'{OUT}/f3_03_incremento.csv', index=False); print(I.round(3).to_string())
