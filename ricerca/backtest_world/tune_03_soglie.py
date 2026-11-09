# tune_03: sensibilita' delle soglie, un filtro alla volta (gli altri restano come oggi).
# Per ogni variante: titoli medi, rendimento annuo netto in EUR (lista intera e top 30 col punteggio attuale),
# differenza dall'universo largo, quota di vincitori (top 5% a 12 mesi) presi, precisione, perdenti.
# Scelta della soglia SOLO sul 2012-19; poi lettura sul 2020-24 e 2025-26 senza ritocchi.
import pandas as pd, numpy as np, sys
from tune_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 400)
F = pd.read_pickle(f'{BASE}/res/tune_panel.pkl')
from tune_common import BASE_P, mask, pct, W0, LOW, score


UNI = ~F.excl_sector
ru, _ = run(F, UNI)
RUN_ALL, _ = run(F, pd.Series(True, index=F.index))
Wtot = F[F.W5].groupby('per').size()


def evaluate(name, p, gruppo, do_top=True):
    m = mask(F, p)
    r, n = run(F, m)
    rows = []
    sc = score(F, m) if do_top else None
    rt = run(F, m, topn=30, score=sc)[0] if do_top else None
    for per, (a, b) in PERIODS.items():
        ds = (F.date >= a) & (F.date <= b)
        X = F[m & ds]
        nn = n[(n.index >= a) & (n.index <= b)]
        d = (r - ru)[(r.index >= a) & (r.index <= b)]
        rows.append(dict(gruppo=gruppo, variante=name, periodo=per, n=nn.mean(), vuoti=int((nn == 0).sum()),
                         cagr=cagr(r, a, b), vs_univ=cagr(r, a, b) - cagr(ru, a, b), t_univ=tstat(d),
                         cagr_top30=cagr(rt, a, b) if do_top else np.nan,
                         prec_W5=X[X.f12.notna()].W5.mean(), prec_L20=X[X.f12.notna()].L20.mean(),
                         recall_W5=X.W5.sum() / Wtot.get(per, np.nan), recall_MB3=X.MB3.sum() / max(F[ds].MB3.sum(), 1)))
    return rows, r


rows, SER = [], {}
VAR = [('ROE', 'roe', [None, 0.0, 0.10, 0.15, 0.20, 0.25]),
       ('D/E', 'de', [0.5, 1.0, 2.0, None]),
       ('PEG', 'peg', [1.0, 1.5, 2.0, 3.0, 5.0, None]),
       ('ricavi_q', 'revq', [None, 0.0, 0.05, 0.10, 0.20]),
       ('EPS_q', 'epsq', [None, 0.0, 0.05, 0.10, 0.20]),
       ('CAGR', 'cagr', [None, 0.0, 0.05, 0.10, 0.15, 0.20]),
       ('FCF', 'fcf', [True, False]),
       ('settore', 'settore', [True, False])]
ntest = 0
for g, k, vals in VAR:
    for v in vals:
        p = dict(BASE_P); p[k] = v
        name = f'{g} {"nessuno" if v is None or v is False else v}'
        if p == BASE_P: name = f'{g} {v} (attuale)'
        else: ntest += 1
        rr, s = evaluate(name, p, g)
        rows += rr; SER[name] = s
        print(name, flush=True)
T = pd.DataFrame(rows)
# t della differenza trimestrale rispetto all'attuale
base_s = SER[[k for k in SER if 'attuale' in k][0]]
T['d_vs_attuale'] = np.nan; T['t_vs_attuale'] = np.nan
for i, r in T.iterrows():
    a, b = PERIODS[r.periodo]
    s = SER[r.variante]
    d = (s - base_s)[(s.index >= a) & (s.index <= b)]
    T.loc[i, 'd_vs_attuale'] = cagr(s, a, b) - cagr(base_s, a, b); T.loc[i, 't_vs_attuale'] = tstat(d)
T.to_csv(f'{BASE}/res/tune_soglie.csv', index=False)
print('varianti diverse dall\'attuale provate:', ntest)
cols = ['variante', 'periodo', 'n', 'cagr', 'vs_univ', 'cagr_top30', 'd_vs_attuale', 't_vs_attuale', 'prec_W5', 'prec_L20', 'recall_W5', 'recall_MB3']
print(T[cols].round(3).to_string())
for per, (a, b) in PERIODS.items(): print('universo', per, round(cagr(ru, a, b), 3), 'tutti i settori', round(cagr(RUN_ALL, a, b), 3))
pd.to_pickle(SER, f'{BASE}/res/tune_soglie_serie.pkl')
