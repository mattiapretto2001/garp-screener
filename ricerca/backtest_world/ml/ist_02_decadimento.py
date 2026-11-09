# ist_02: quanto rende un titolo DOPO l'ingresso / l'uscita dalla lista e secondo la posizione in classifica (diagnosi delle regole)
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from ist_common import *
UQ = UNIV_EW
rows = []
for lk in ['core', 'core_noTWKO', 'top30', 'cr2', 'q3']:
    for p in ['2018-26', '2012-17']:
        ds = pdates(p); acc = {}
        for i, d in enumerate(ds):
            L = ORD[lk].get(d, []); rk = {t: j + 1 for j, t in enumerate(L)}; R = RET.get(d, {}); u = UQ[d]
            j0 = REB.index(d)
            prev = [set(ORD[lk].get(REB[j0 - k], [])) if j0 - k >= 0 else set() for k in (1, 2, 3, 4)]
            # dentro la lista per fascia di classifica
            for t, r in rk.items():
                if t not in R: continue
                b = '1-10' if r <= 10 else ('11-20' if r <= 20 else ('21-30' if r <= 30 else ('31-60' if r <= 60 else '61+')))
                acc.setdefault(('in lista, posizione ' + b), []).append(R[t] - u)
                age = 'nuovo (assente 1 trim. fa)' if t not in prev[0] else ('in lista da 2-4 trim.' if t not in prev[3] else 'in lista da 5+ trim.')
                acc.setdefault(age, []).append(R[t] - u)
            # usciti: non in lista ora, in lista k trimestri fa (e non rientrati in mezzo)
            for k in (1, 2, 3, 4):
                was = prev[k - 1] - set(rk)
                for kk in range(k - 1): was -= prev[kk]
                for t in was:
                    if t in R: acc.setdefault(f'uscito da {k} trim.', []).append(R[t] - u)
        for g, v in acc.items():
            v = np.array(v); rows.append(dict(lista=lk, periodo=p, gruppo=g, n=len(v), xs_trim=v.mean(), xs_anno=(1 + v.mean()) ** 4 - 1,
                                             t=v.mean() / (v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 2 else np.nan))
T = pd.DataFrame(rows)
T.to_csv(f'{OUTD}/ist_02_decadimento.csv', index=False)
pd.set_option('display.width', 200)
for lk in T.lista.unique():
    print(T[T.lista == lk].pivot_table(index='gruppo', columns='periodo', values=['xs_anno', 'n']).round(3).to_string(), '\n')
