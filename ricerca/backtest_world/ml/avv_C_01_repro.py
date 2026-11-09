# Verifica avversariale Prova C (08/11/2026): rifaccio i numeri principali da runs.pkl / posizioni.pkl con un calcolo mio.
import pickle, numpy as np, pandas as pd
D = 'regoleC/dati'
T = pd.read_pickle(f'{D}/runs.pkl'); T = T[~T.tax]
def med(key, b, o, col): return T[(T.key == key) & (T.base == b) & (T.over == o)][col].median()
def paired(key, b, o, col='cagr_cr'):
    a = T[(T.key == key) & (T.base == b) & (T.over == o)].set_index('seed')[col]
    r = T[(T.key == key) & (T.base == 'L') & (T.over == 'none')].set_index('seed')[col]
    d = (a - r).dropna(); return d.median(), (d > 0).mean(), d.mean(), d.std() / np.sqrt(len(d))
for key in []:
    print(f'--- {key}  VWCE {T[T.key==key].cagr_w.iloc[0]:.4f}  ddW {T[T.key==key].dd_w.iloc[0]:.3f}')
    for b, o in [('L','none'),('L','TR3'),('L','TR2'),('L','S30'),('L','AD30'),('T2','none'),('T3','none')]:
        dm, p, mu, se = paired(key, b, o)
        print(f'{b:3}{o:5} s_med {med(key,b,o,"cagr_s"):+.4f} cr_med {med(key,b,o,"cagr_cr"):+.4f} dd_s {med(key,b,o,"dd_s"):+.3f} dd_cr {med(key,b,o,"dd_cr"):+.3f} '
              f'| diff mediana appaiata {dm:+.4f} media {mu:+.4f} (es {se:.4f}) quota>base {p:.2f} | top10 {med(key,b,o,"top10"):.2f} top10pos {med(key,b,o,"top10_pos"):.2f} cash {med(key,b,o,"cash"):.2f} trades {med(key,b,o,"trades_y"):.1f}')
POS = pickle.load(open(f'{D}/posizioni.pkl', 'rb'))
for key, b, o in [('P2','L','none'),('P2','T3','none'),('P1','T3','none'),('P1','L','none')]:
    P = POS[(key, b, o, False)].view(np.recarray); m = P.mult
    print(key, b, o, 'n', len(P), 'per portafoglio', len(P)/300, 'hold med mesi', np.median(P.hold)*12, 'win', (m>1).mean().round(4), 'zero', (m<=0.1).mean().round(4),
          'x3', (m>=3).mean().round(4), 'x5', (m>=5).mean().round(4), 'x10', (m>=10).mean().round(5), 'pk10', (P.peak>=10).mean().round(4),
          'fall', (P.why=='fallimento').mean().round(4))
