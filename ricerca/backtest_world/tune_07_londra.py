# tune_07: effetto dell'errore pence/sterline su Londra nel backtest mondiale (world_05). Confronto prima/dopo la correzione.
import pandas as pd, numpy as np
import tune_common as TC
from tune_common import *
out = []
for fix in (False, True):
    TC.FIX_PENCE = fix
    F = TC.load()
    m = mask(F, BASE_P); sc = score(F, m)
    for reg, rm in [('Mondo', pd.Series(True, index=F.index)), ('Europa', F.reg == 'Europa'), ('Londra', F.ex == 'LSE')]:
        r, n = run(F, m & rm); rt, _ = run(F, m & rm, topn=30, score=score(F, m & rm))
        ru, _ = run(F, ~F.excl_sector & rm)
        for per, (a, b) in list(PERIODS.items()) + [('2012-26', ('2011-12-31', '2026-09-30'))]:
            out.append(dict(corretto=fix, zona=reg, periodo=per, n=n[(n.index >= a) & (n.index <= b)].mean(), lista=cagr(r, a, b),
                            top30=cagr(rt, a, b), universo=cagr(ru, a, b)))
T = pd.DataFrame(out); T.to_csv(f'{BASE}/res/tune_londra.csv', index=False)
pd.set_option('display.width', 200); print(T.round(3).to_string())
