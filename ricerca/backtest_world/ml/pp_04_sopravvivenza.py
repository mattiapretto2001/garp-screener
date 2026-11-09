# pp_04: quanto gonfia la sopravvivenza? Nel periodo pulito tolgo le societa' uscite dal listino (entro 3 anni dalla
# data, come mancano nel 2012-17; variante: tutte quelle oggi non quotate) e rifaccio liste e universi.
from pp_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
REGS = {'Mondo': ALL, 'USA grandi': REG['USA grandi'], 'USA piccole/medie': REG['USA piccole/medie'], 'Europa': REG['Europa'], 'Asia': REG['Asia']}
rows = []
for sim, KEEP in [('completo', ALL), ('senza uscite entro 3 anni', ~DEL3), ('senza tutte le uscite', ~DELALL)]:
    sc = score_g(A & B2 & KEEP) if sim != 'completo' else SC_A2
    for reg, R in REGS.items():
        out = {}
        for name, (m, univ) in LISTS.items():
            if name.startswith('Top 30'):
                if reg != 'Mondo': continue
                mm = topn(A & B2 & KEEP, 30, sc=sc)
            else:
                mm = m & univ & R & KEEP
            r, n = run(F, mm); u = useries(univ & R & KEEP); out[name] = (r, u)
            for p in ['2018-26', '2018-21', '2022-24', '2025-26']:
                a, b = ALLP[p]
                rows.append(dict(sim=sim, regione=reg, lista=name, periodo=p, cagr=cagr(r, a, b), univ=cagr(u, a, b), diff=cagr(r, a, b) - cagr(u, a, b)))
        r = 0.5 * out['GARP core'][0] + 0.5 * out['Qualita Q3'][0]; u = useries(QU & R & KEEP)
        for p in ['2018-26', '2018-21', '2022-24', '2025-26']:
            a, b = ALLP[p]
            rows.append(dict(sim=sim, regione=reg, lista='50% core + 50% Q3', periodo=p, cagr=cagr(r, a, b), univ=cagr(u, a, b), diff=cagr(r, a, b) - cagr(u, a, b)))
        for un, U in [('Universo GARP', UNI), ('Universo >=2 Mld$', UNI & B2)]:
            u = useries(U & R & KEEP)
            for p in ['2018-26', '2018-21', '2022-24', '2025-26']:
                a, b = ALLP[p]; rows.append(dict(sim=sim, regione=reg, lista=un, periodo=p, cagr=cagr(u, a, b), univ=cagr(u, a, b), diff=0.0))
        print(sim, reg, flush=True)
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/pp_04_sopravvivenza.csv', index=False)
X = T[T.periodo == '2018-26'].pivot_table(index=['regione', 'lista'], columns='sim', values=['diff', 'cagr'], sort=False)
X[('gonfiatura diff', '3 anni')] = X[('diff', 'senza uscite entro 3 anni')] - X[('diff', 'completo')]
X[('gonfiatura diff', 'tutte')] = X[('diff', 'senza tutte le uscite')] - X[('diff', 'completo')]
X[('gonfiatura cagr', '3 anni')] = X[('cagr', 'senza uscite entro 3 anni')] - X[('cagr', 'completo')]
print(X.round(3).to_string())
# quote di righe tolte e rendimento a 12 mesi delle uscite contro le altre, per regione (periodo pulito)
S = F[UNI & F.date.isin(CLEAN) & F.f12.notna()]
print('quota righe tolte (3 anni) per regione', S.groupby('reg').apply(lambda d: DEL3[d.index].mean()).round(3).to_dict())
print('f12 medio uscite entro 3 anni vs altre', S.groupby(DEL3[S.index]).f12.agg(['mean', 'median', 'size']).round(3).to_string())
print('rendimento trimestrale medio r_eur: uscite entro 3 anni vs altre', S.groupby(DEL3[S.index]).r_eur.mean().round(4).to_dict())
