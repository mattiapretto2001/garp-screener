# temi_04: seconda tornata (DICHIARATA DOPO aver visto temi_03): orizzonti 3/12/36 mesi, eccezionali e crolli, varianti
#   BM   = B e MOM insieme ('tema confermato': fondamentali che migliorano + prezzi che seguono)
#   MOM6 = 10% con momentum mediano a 6 mesi piu' alto;  AMP = 10% con ampiezza in aumento (d_pos2) piu' alta
#   B20  = punteggio B, 20% migliore
from temi_common import *
V = pd.read_pickle(f'{OUT}/ind_flags.pkl')
top = lambda s, q=0.9: s.groupby(V.date).rank(pct=True) > q
V['BM'] = V.B & V.MOM; V['MOM6'] = top(V.mom6_med); V['AMP'] = top(V.d_pos2); V['B20'] = top(V.scoreB, 0.8)
RULES = ['A', 'B', 'Bplus', 'W', 'MOM', 'CALDE', 'BM', 'MOM6', 'AMP', 'B20']
V.to_pickle(f'{OUT}/ind_flags2.pkl')
CI = pd.read_pickle(f'{OUT}/comp_ind.pkl')
Fc = fv3.load(cols=['t', 'date', 'reg', 'reg_rob', 'fwd12_eur', 'xs12_reg', 'xs36_reg', 'top5_reg', 'bot20_reg', 'crash50', 'r_eur', 'x3'])
C = CI.merge(Fc, on=['t', 'date'], how='left').merge(V[['ind', 'date'] + RULES], on=['ind', 'date'], how='inner')
for r in RULES: C[r] = C[r].fillna(False).astype(bool)
# esito a 3 mesi: rendimento del trimestre dopo - media della regione (societa' idonee)
C['xs3'] = C.r_eur - C.groupby(['date', 'reg']).r_eur.transform('mean')
C.loc[C.date == C.date.max(), 'xs3'] = np.nan     # ultimo trimestre incompleto
rows = []
for r in RULES:
    o = {'regola': r, 'industrie_per_data': V.groupby('date')[r].sum().mean()}
    for tgt, lag, lab in (('xs3', 1, '3m'), ('xs12_reg', 4, '12m'), ('xs36_reg', 12, '36m'), ('top5_reg', 4, 'top5'), ('crash50', 4, 'crollo'), ('x3', 12, 'x3')):
        Y = C[C[tgt].notna()]
        d = Y[Y[r]].groupby('date')[tgt].mean() - Y.groupby('date')[tgt].mean()
        d = d.dropna()
        o[lab] = 100 * d.mean(); o['t_' + lab] = nw_t(d, lags=max(lag, 1))
    rows.append(o)
R = pd.DataFrame(rows)
pd.set_option('display.width', 250); print(R.round(2).to_string()); R.to_csv(f'{OUT}/b_varianti.csv', index=False)
# per periodo, 3 e 12 mesi
pr = []
for r in RULES:
    for tgt in ('xs3', 'xs12_reg'):
        Y = C[C[tgt].notna()]
        d = (Y[Y[r]].groupby('date')[tgt].mean() - Y.groupby('date')[tgt].mean()).dropna()
        for p in PER3:
            s = d[[per3_of(x) == p for x in d.index]]
            pr.append({'regola': r, 'target': tgt, 'periodo': p, 'pp': 100 * s.mean(), 't': nw_t(s, 4 if tgt != 'xs3' else 1)})
P = pd.DataFrame(pr).pivot_table(index=['target', 'regola'], columns='periodo', values=['pp', 't']).round(2)
print(P.to_string()); pd.DataFrame(pr).to_csv(f'{OUT}/b_varianti_periodi.csv', index=False)
# persistenza: quanti trimestri consecutivi resta segnalata un'industria
for r in ['B', 'MOM', 'BM']:
    s = V.sort_values(['ind', 'di'])
    runs = []
    for ind, g in s.groupby('ind'):
        cnt = 0
        for f in g[r].values:
            if f: cnt += 1
            elif cnt: runs.append(cnt); cnt = 0
        if cnt: runs.append(cnt)
    runs = np.array(runs)
    print(r, 'episodi', len(runs), 'durata media trimestri %.2f' % runs.mean(), 'quota episodi di 1 solo trimestre %.2f' % (runs == 1).mean())
