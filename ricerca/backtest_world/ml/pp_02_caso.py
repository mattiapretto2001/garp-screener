# pp_02: liste contro scelte a caso dello stesso numero di titoli (dentro l'universo di confronto), periodo pulito, lordo.
from pp_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
REGS = {'Mondo': ALL, 'USA grandi': REG['USA grandi'], 'USA piccole/medie': REG['USA piccole/medie'], 'Europa': REG['Europa'], 'Asia': REG['Asia']}
rows = []
for reg, R in REGS.items():
    for name, (m, univ) in LISTS.items():
        if name.startswith('Top 30') and reg != 'Mondo': continue
        if F[m & univ & R & F.date.isin(CLEAN)].groupby('date').size().mean() < 1: continue
        res = caso(m & univ & R, univ & R, PP, n_it=400 if reg == 'Mondo' else 200)
        for p, x in res.items(): rows.append(dict(lista=name, regione=reg, periodo=p, **x))
        print(reg, name, {p: round(x['batte'], 3) for p, x in res.items()}, flush=True)
C = pd.DataFrame(rows); C.to_csv(f'{OUT}/pp_02_caso.csv', index=False)
print(C.pivot_table(index=['regione', 'lista'], columns='periodo', values='batte', sort=False).round(3).to_string())
print(C[C.periodo == '2018-26'][['regione', 'lista', 'reale_lordo', 'caso_mediana', 'caso_p5', 'caso_p95', 'batte']].round(3).to_string())
