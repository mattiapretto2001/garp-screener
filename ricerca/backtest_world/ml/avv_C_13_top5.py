# 2012-26, regola base: togliendo dalle liste solo i 5 (e i 10) nomi che hanno guadagnato di piu' con la regola base
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, 'regoleC'); import c02_sim as S, c03_run as R
import avv_C_07_robusto as V
from multiprocessing import Pool
POS = pickle.load(open('regoleC/dati/posizioni.pkl', 'rb')); P = POS[('P2', 'L', 'none', False)].view(np.recarray); del POS
s = pd.Series(P.pl).groupby(P.j).sum().sort_values(ascending=False)
tick = pickle.load(open('regoleC/dati/P2.pkl', 'rb'))['tick']
print('quota del guadagno netto totale dei 300 portafogli:', {n: round(s.iloc[:n].sum() / s.sum(), 3) for n in [5, 10, 20, 50]})
print('primi 10:', [(tick[j], round(v / 300, 2)) for j, v in s.iloc[:10].items()])
def job(n):
    D = V.drop_names(S.load('P2'), list(s.index[:n])); out = []
    for sd in range(300):
        m, _ = R.metrics('P2', S.run(D, 'L', 'none', sd, False), D, False); out.append((m['cagr_s'], m['cagr_cr']))
    return n, np.median(np.array(out), axis=0)
if __name__ == '__main__':
    with Pool(2) as Pp:
        for n, m in Pp.imap(job, [5, 10]): print(f'senza i primi {n}: meta {m[0]:.4f} | 50/50 {m[1]:.4f} | VWCE 0.1234')
