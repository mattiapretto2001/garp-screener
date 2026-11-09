# avv_temi_01: riproduzione indipendente dei numeri chiave (B, MOM, BM, CALDE a 3/12 mesi, eccezionali, crolli) e confronto con temi_out
from avv_temi_common import *
import time; t0 = time.time()
F = load(); P = ind_panel(F); V = flags(P)
Vo = pd.read_pickle(f'{HERE}/temi_out/ind_flags2.pkl')
M = V.merge(Vo[['ind', 'date', 'B', 'MOM', 'CALDE', 'BM', 'scoreB', 'g_agg', 'accel_agg', 'd_marg', 'pos', 'd_pos2', 'qa']], on=['ind', 'date'], suffixes=('', '_o'))
print('righe idonee mie', len(V), 'autore', len(Vo), 'in comune', len(M))
for c in ['g_agg', 'accel_agg', 'qa', 'pos', 'd_pos2', 'd_marg', 'scoreB']:
    a, b = M[c], M[c + '_o']; ok = a.notna() | b.notna()
    print(f'{c:10s} uguali (tol 1e-6) {np.isclose(a[ok], b[ok], atol=1e-6, equal_nan=True).mean():.4f}')
for r in ['B', 'MOM', 'CALDE', 'BM']: print(r, 'segnali coincidenti', (M[r] == M[r + '_o']).mean().round(4), 'n mie', int(M[r].sum()), 'autore', int(M[r + '_o'].sum()))
RULES = ['B', 'MOM', 'BM', 'CALDE']
C = company(F, V, RULES)
rows = []
for r in RULES:
    o = {'regola': r}
    for tgt, lag, lab in (('xs3', 1, '3m'), ('xs12_reg', 4, '12m'), ('xs36_reg', 12, '36m'), ('top5_reg', 4, 'top5'), ('crash50', 4, 'crollo')):
        _, m, t = spread(C, r, tgt, lag); o[lab] = round(m, 2); o['t_' + lab] = round(t, 2)
    rows.append(o)
R = pd.DataFrame(rows); print(R.to_string()); R.to_csv(f'{OUT}/01_repro.csv', index=False)
print('autore (b_varianti):'); print(pd.read_csv(f'{HERE}/temi_out/b_varianti.csv').set_index('regola').loc[RULES, ['3m', 't_3m', '12m', 't_12m', '36m', 't_36m', 'top5', 't_top5', 'crollo', 't_crollo']].round(2).to_string())
# base crolli e quota crolli CALDE
Y = C[C.crash50.notna()]
print('crolli CALDE %.3f base %.3f' % (Y[Y.CALDE].groupby('date').crash50.mean().mean(), Y.groupby('date').crash50.mean().mean()))
V.to_pickle(f'{OUT}/V.pkl'); C.to_pickle(f'{OUT}/C.pkl')
print('secondi', round(time.time() - t0))
