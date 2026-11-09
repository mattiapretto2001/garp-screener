# tune_04: segnali nuovi. Quanta informazione aggiungono rispetto alle voci gia' usate dal GARP.
# Metodo: a ogni data, regressione trasversale del percentile di rendimento a 12 mesi sui percentili delle 7 voci GARP
# + il segnale (Fama-MacBeth); si guarda il coefficiente del segnale e il suo t (errori corretti per la sovrapposizione
# dei 12 mesi: t diviso per 2, cioe' circa sqrt(4) trimestri sovrapposti). Inoltre: probabilita' di essere top 5% / bottom 20%
# nel quinto migliore contro il quinto peggiore del segnale. Universo largo senza settori esclusi; e fra i "quasi GARP".
import pandas as pd, numpy as np
from tune_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 400)
F = pd.read_pickle(f'{BASE}/res/tune_panel.pkl')
F = F[~F.excl_sector & F.f12.notna()].copy()
SIG = {  # nome: (colonna, segno atteso: +1 = piu' alto e' meglio)
    'accelerazione ricavi (trim.)': ('accel_q', 1), 'accelerazione ricavi (12m)': ('accel_y', 1),
    'leva operativa (EBIT vs ricavi)': ('oplev', 1), 'margine operativo: variazione': ('d_opm', 1), 'margine operativo: livello': ('opm', 1),
    'qualita\' utili (FCF/utile)': ('fcf_ni', 1), 'margine FCF': ('fcf_m', 1), 'variazione azioni': ('dshares', -1),
    'momentum 12-1 mesi': ('mom12_1', 1), 'momentum 6 mesi': ('mom6', 1), 'distanza dal max 52 sett.': ('hi52', 1),
    'prezzo/media 200 gg': ('ma200', 1), 'dimensione (capitalizzazione)': ('logmcap', -1), 'crescita ricavi 12m': ('revg_ttm', 1),
    'primo utile (12m)': ('first_profit', 1), 'primo utile annuale': ('first_profit_y', 1), 'prezzo/ricavi': ('ps', -1),
    'volatilita\' 1 anno': ('vol1y', -1)}
CTRL = {'peg': -1, 'revq': 1, 'epsq': 1, 'rev_cagr': 1, 'roe': 1, 'fcfy': 1, 'de': -1}


def prank(s): return ((s.rank(method='average') - 0.5) / s.notna().sum()).fillna(0.5)


def fm(X, col, sgn):
    """Fama-MacBeth: coefficiente del segnale (percentile) sul percentile di rendimento, con controlli GARP"""
    co = []
    for t, x in X.groupby('date'):
        if len(x) < 40 or x[col].notna().sum() < 20: continue
        y = x.f12.rank(pct=True).values
        Z = [np.ones(len(x))] + [prank(x[c] * s).values for c, s in CTRL.items()] + [prank(x[col].astype(float) * sgn).values]
        Z = np.column_stack(Z)
        b = np.linalg.lstsq(Z, y, rcond=None)[0]
        co.append((t, b[-1]))
    s = pd.Series(dict(co))
    return s


def quint(X, col, sgn):
    q = X.groupby('date')[col].transform(lambda s: (s.astype(float) * sgn).rank(pct=True))
    hi, lo = X[q > 0.8], X[q <= 0.2]
    return hi.W5.mean(), lo.W5.mean(), hi.L20.mean(), lo.L20.mean()


rows = []
for name, (col, sgn) in SIG.items():
    binary = F[col].dtype == bool
    for g, X in [('tutto', F)] + [(p, F[F.per == p]) for p in PERIODS] + [(r, F[F.reg == r]) for r in ['USA', 'Europa', 'Asia']]:
        s = fm(X, col, sgn)
        if binary:
            on, off = X[X[col]], X[~X[col]]
            q = (on.W5.mean(), off.W5.mean(), on.L20.mean(), off.L20.mean())
        else:
            q = quint(X, col, sgn)
        rows.append(dict(segnale=name, gruppo=g, copertura=X[col].notna().mean() if not binary else X[col].mean(),
                         coef=s.mean(), t=tstat(s) / 2, W5_alto=q[0], W5_basso=q[1], L20_alto=q[2], L20_basso=q[3]))
    print(name, flush=True)
T = pd.DataFrame(rows)
T.to_csv(f'{BASE}/res/tune_segnali.csv', index=False)
print(T.pivot(index='segnale', columns='gruppo', values='coef').round(3)[['tutto', '2012-19', '2020-24', '2025-26', 'USA', 'Europa', 'Asia']].to_string())
print(T.pivot(index='segnale', columns='gruppo', values='t').round(1)[['tutto', '2012-19', '2020-24', '2025-26', 'USA', 'Europa', 'Asia']].to_string())
print(T[T.gruppo == 'tutto'][['segnale', 'copertura', 'W5_alto', 'W5_basso', 'L20_alto', 'L20_basso']].round(3).to_string())

# stessi segnali solo fra i "quasi GARP" (al massimo 1 filtro fallito, settori ammessi): servono per ordinare/allargare
Q = F[F.n_fail <= 1]
rows = []
for name, (col, sgn) in SIG.items():
    if F[col].dtype == bool:
        for g, X in [('tutto', Q)] + [(p, Q[Q.per == p]) for p in PERIODS]:
            on, off = X[X[col]], X[~X[col]]
            rows.append(dict(segnale=name, gruppo=g, W5_alto=on.W5.mean(), W5_basso=off.W5.mean(), ex=on.f12.median() - off.f12.median()))
        continue
    for g, X in [('tutto', Q)] + [(p, Q[Q.per == p]) for p in PERIODS]:
        q = X.groupby('date')[col].transform(lambda s: (s.astype(float) * sgn).rank(pct=True))
        hi, lo = X[q > 2 / 3], X[q <= 1 / 3]
        rows.append(dict(segnale=name, gruppo=g, W5_alto=hi.W5.mean(), W5_basso=lo.W5.mean(), ex=hi.f12.median() - lo.f12.median()))
TQ = pd.DataFrame(rows); TQ.to_csv(f'{BASE}/res/tune_segnali_quasigarp.csv', index=False)
print(TQ.pivot(index='segnale', columns='gruppo', values='ex').round(3).to_string())
print(TQ.pivot(index='segnale', columns='gruppo', values='W5_alto').round(3).to_string())
print(TQ.pivot(index='segnale', columns='gruppo', values='W5_basso').round(3).to_string())
