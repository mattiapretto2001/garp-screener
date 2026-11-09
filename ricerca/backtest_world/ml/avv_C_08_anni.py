# Verifica avversariale Prova C: il vantaggio della lista sul tempo massimo (e di "meta' a x3" sulla base) da quali anni viene?
import pickle, numpy as np, pandas as pd
ML = '${RICERCA_BASE}/backtest_world/ml'
T = pd.read_pickle(f'{ML}/regoleC/dati/runs.pkl'); T = T[~T.tax]
for key in ['P1', 'P2']:
    D = pickle.load(open(f'{ML}/regoleC/dati/{key}.pkl', 'rb')); cal = D['cal']; W = D['W'].reindex(cal).ffill()
    ms = pd.Series(W.values, index=cal).groupby(cal.year).first()
    wy = ms.shift(-1) / ms - 1; wy.iloc[-1] = W.iloc[-1] / ms.iloc[-1] - 1
    A = {}
    for b, o in [('L', 'none'), ('L', 'TR3'), ('L', 'AD30'), ('T2', 'none'), ('T3', 'none')]:
        g = T[(T.key == key) & (T.base == b) & (T.over == o)].sort_values('seed')
        A[(b, o)] = pd.DataFrame(list(g.ann), index=g.seed.values)
    yrs = A[('L', 'none')].columns
    print(f'==== {key}: differenza mediana sulla meta moltiplicatori, anno per anno (punti)')
    out = pd.DataFrame({f'L-{b}': (A[('L', 'none')] - A[(b, 'none')]).median() for b in ['T2', 'T3']})
    out['TR3-L'] = (A[('L', 'TR3')] - A[('L', 'none')]).median(); out['AD30-L'] = (A[('L', 'AD30')] - A[('L', 'none')]).median()
    out['L'] = A[('L', 'none')].median(); out['W'] = wy.reindex(yrs).values
    print((out * 100).round(1).T.to_string())
    # 50/50 ribilanciato ogni gennaio = media dei due rendimenti annui; CAGR togliendo un anno alla volta
    nyr = (cal[-1] - cal[0]).days / 365.25
    def cagr(df, drop=None):
        r = 0.5 * df + 0.5 * wy.reindex(df.columns).values
        if drop is not None: r = r.drop(columns=drop)
        n = nyr - (1 if drop is not None else 0)
        return ((1 + r).prod(axis=1) ** (1 / n) - 1)
    print('50/50: L meno T3 e L meno T2 (mediana dei portafogli), togliendo un anno alla volta:')
    res = {}
    for y in [None] + list(yrs):
        res['tutti' if y is None else y] = dict(L_T3=(cagr(A[('L', 'none')], y) - cagr(A[('T3', 'none')], y)).median() * 100,
                                                 L_T2=(cagr(A[('L', 'none')], y) - cagr(A[('T2', 'none')], y)).median() * 100,
                                                 TR3_L=(cagr(A[('L', 'TR3')], y) - cagr(A[('L', 'none')], y)).median() * 100)
    print(pd.DataFrame(res).round(2).to_string())
