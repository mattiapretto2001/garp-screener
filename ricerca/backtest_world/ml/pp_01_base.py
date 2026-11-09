# pp_01: liste del 07/11 sul periodo pulito 2018-26 (e, per confronto, 2012-17 e 2012-26), mondo e regioni.
from pp_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500); pd.set_option('display.max_columns', 40)
ROWS, SER = [], {}
REGS = {'Mondo': ALL, 'USA grandi': REG['USA grandi'], 'USA piccole/medie': REG['USA piccole/medie'], 'Europa': REG['Europa'], 'Asia': REG['Asia']}
for reg, R in REGS.items():
    for name, (m, univ) in LISTS.items():
        if name.startswith('Top 30') and reg != 'Mondo':
            # membri della top 30 mondiale che stanno nella regione, contro l'universo della regione
            o, r, u = ev(name + ' (membri nella regione)', m, univ & R, ALLP, reg)
        else:
            o, r, u = ev(name, m, univ & R, ALLP, reg)
        ROWS += o; SER[(reg, name)] = r; SER[(reg, 'U ' + name)] = u
    # misto 50/50 core + Q3, contro QU della regione
    rc, rq = SER[(reg, MIX[0])], SER[(reg, MIX[1])]
    mix = 0.5 * rc + 0.5 * rq
    nmix = F[(CORE & UNI & R) | (Q3 & QU & B5 & R)].groupby('date').size().reindex(REB).fillna(0)
    u = useries(QU & R)
    o = measure(mix, nmix, (CORE & UNI & R) | (Q3 & QU & B5 & R), u, QU & R, ALLP, dict(lista='50% core + 50% Q3', regione=reg))
    for x in o: x.update(r2022=year_ret(mix, 2022), u2022=year_ret(u, 2022), dd2022=dd_in(mix, 2022), udd2022=dd_in(u, 2022))
    ROWS += o; SER[(reg, '50% core + 50% Q3')] = mix; SER[(reg, 'U 50% core + 50% Q3')] = u
    print(reg, flush=True)
# definizioni del 07/11 per i radar (senza soglia di taglia), solo mondo
for name, m in [('Radar A 07/11 (senza soglia)', RADA_OLD), ('Radar B 07/11 (senza soglia)', RADB_OLD)]:
    o, r, u = ev(name, m, UNI, ALLP, 'Mondo'); ROWS += o; SER[('Mondo', name)] = r
# universi, per riferimento
for reg, R in REGS.items():
    for un, U in [('Universo GARP', UNI), ('Universo >=2 Mld$', UNI & B2), ('Universo grandi >=5 Mld$ (Q3)', QU & B5)]:
        u = useries(U & R); n = F[U & R].groupby('date').size().reindex(REB).fillna(0)
        o = measure(u, n, U & R, u, U & R, ALLP, dict(lista=un, regione=reg))
        for x in o: x.update(r2022=year_ret(u, 2022), dd2022=dd_in(u, 2022))
        ROWS += o; SER[(reg, un)] = u
T = pd.DataFrame(ROWS); T.to_csv(f'{OUT}/pp_01_base.csv', index=False)
pd.to_pickle(SER, f'{OUT}/pp_01_series.pkl')
W = T[T.regione == 'Mondo']
print(W.pivot_table(index='lista', columns='periodo', values=['diff', 't_nw'], sort=False).round(3).to_string())
print(W[W.periodo == '2018-26'][['lista', 'n', 'cagr', 'univ', 'diff', 't_nw', 't', 'maxdd', 'u_maxdd', 'r2022', 'u2022', 'dd2022', 'crolli', 'u_crolli', 'perdenti', 'eccez']].round(3).to_string())
print(T[T.periodo == '2018-26'].pivot_table(index='lista', columns='regione', values='diff', sort=False).round(3).to_string())
print(T[T.periodo == '2018-26'].pivot_table(index='lista', columns='regione', values='t_nw', sort=False).round(2).to_string())
print(T[T.periodo == '2018-26'].pivot_table(index='lista', columns='regione', values='n', sort=False).round(1).to_string())
# anno per anno (mondo), anno solare del trimestre di possesso
def annual(r):
    nx = {t: (REB[i + 1] if i + 1 < len(REB) else pd.Timestamp('2026-11-06')) for i, t in enumerate(REB)}
    y = r.copy(); y.index = [nx[t] for t in r.index]
    y.index = [d.year if (d.month > 1 or d.day > 15) else d.year - 1 for d in pd.to_datetime(y.index)]
    return (1 + y).groupby(level=0).prod() - 1
names = list(LISTS) + ['50% core + 50% Q3']
Y = pd.DataFrame({k: annual(SER[('Mondo', k)][CLEAN]) - annual(SER[('Mondo', 'U ' + k)][CLEAN]) for k in names})  # 2018 = apr-dic
Y.to_csv(f'{OUT}/pp_01_annuali_diff.csv'); print(Y.loc[2018:].round(3).to_string())
print('anni battuti 2018-2026:', (Y.loc[2018:] > 0).sum().to_dict())
