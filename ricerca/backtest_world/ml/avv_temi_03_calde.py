# avv_temi_03: le industrie "calde". E' davvero un effetto della crescita dei ricavi o solo volatilita'/lotteria?
from avv_temi_common import *
V = pd.read_pickle(f'{OUT}/V.pkl'); C = pd.read_pickle(f'{OUT}/C.pkl')
C = C.merge(V[['ind', 'date', 'VOLI', 'accel_agg', 'scoreB', 'g_agg', 'vol_med']], on=['ind', 'date'])
Y = C[C.crash50.notna()].copy()
print('Industrie piu\' spesso CALDE (segnalazioni, crolli %, eccezionali %):')
g = Y[Y.CALDE].groupby('ind').agg(n=('date', 'nunique'), soc=('t', 'size'), crollo=('crash50', 'mean'), top5=('top5_reg', 'mean')).sort_values('soc', ascending=False)
print((g.head(15)).round(3).to_string())
# contributo ai crolli in eccesso
Y['base_cr'] = Y.groupby('date').crash50.transform('mean')
ex = Y[Y.CALDE].assign(e=lambda x: x.crash50 - x.base_cr).groupby('ind').e.sum().sort_values(ascending=False)
print('\nquota dei crolli in eccesso dalle prime 3 industrie: %.2f' % (ex.head(3).sum() / ex.sum()), ex.head(5).round(1).to_dict())
print('\nCrolli per regione (CALDE vs base):')
for rg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia', 'Altri']:
    Z = Y[Y.reg_rob == rg]; d = (Z[Z.CALDE].groupby('date').crash50.mean() - Z.groupby('date').crash50.mean()).dropna()
    print(f'  {rg:18s} {100*d.mean():+.2f} pp (t {nw_t(d,4):.2f})')
# controllo volatilita': regressione FM a livello societa' di crash50 / top5 / xs12 su CALDE, VOLI, rango vol1y, rango logmcap
Y['rv'] = Y.groupby('date').vol1y.rank(pct=True) - 0.5; Y['rm'] = Y.groupby('date').mcap_usd.rank(pct=True) - 0.5
for tgt in ['crash50', 'top5_reg', 'xs12_reg']:
    co = []
    for d, z in Y[Y[tgt].notna()].groupby('date'):
        Z = np.c_[np.ones(len(z)), z.CALDE.astype(float), z.rv.fillna(0), z.rm.fillna(0)]
        b = np.linalg.lstsq(Z, z[tgt].astype(float).values, rcond=None)[0]; co.append(b[1:])
    co = pd.DataFrame(co, columns=['CALDE', 'vol', 'mcap'])
    print(f'FM {tgt:9s} CALDE {100*co.CALDE.mean():+.2f} pp (t {nw_t(co.CALDE,4):.2f}) | vol {100*co.vol.mean():+.2f} (t {nw_t(co.vol,4):.2f}) | mcap {100*co.mcap.mean():+.2f} (t {nw_t(co.mcap,4):.2f})')
# confronto con un indicatore di sola volatilita' dell'industria (10% con volatilita' mediana piu' alta), nessun dato di ricavi
for r in ['VOLI']:
    for tgt, lag in (('crash50', 4), ('top5_reg', 4), ('xs12_reg', 4)):
        d, m, t = spread(Y, r, tgt, lag); print(f'{r} {tgt}: {m:+.2f} pp (t {t:.2f})')
print('sovrapposizione CALDE-VOLI (quota di CALDE che e\' anche VOLI): %.2f' % (V[V.CALDE].VOLI.mean()))
for lab, m in (('CALDE e non VOLI', Y.CALDE & ~Y.VOLI), ('CALDE e VOLI', Y.CALDE & Y.VOLI)):
    Y['_r'] = m
    print(lab, {tg: f'{spread(Y, "_r", tg, 4)[1]:+.2f} (t {spread(Y, "_r", tg, 4)[2]:.2f})' for tg in ['crash50', 'top5_reg', 'xs12_reg']})
# la penalita' proposta nel report: CALDE "senza accelerazione" (accel_agg <= 0). Variante MAI testata dall'autore.
C2 = C.copy(); C2['CALDE_noacc'] = C2.CALDE & (C2.accel_agg <= 0); C2['CALDE_acc'] = C2.CALDE & (C2.accel_agg > 0)
print('\nPenalita\' proposta (CALDE senza accelerazione) vs CALDE con accelerazione; industrie per data:',
      round(V[V.CALDE & (V.accel_agg <= 0)].groupby('date').size().mean(), 1), round(V[V.CALDE & (V.accel_agg > 0)].groupby('date').size().mean(), 1))
for r in ['CALDE_noacc', 'CALDE_acc']:
    print(r, ' | '.join(f'{tg} {spread(C2, r, tg, lg)[1]:+.2f} (t {spread(C2, r, tg, lg)[2]:.2f})' for tg, lg in (('xs3', 1), ('xs12_reg', 4), ('xs36_reg', 12), ('top5_reg', 4), ('crash50', 4))))
# 36 mesi: date sovrapposte per 11 trimestri. Serie non sovrapposte (una data ogni 12, 12 fasi): quante osservazioni e che t?
d36, m36, t36 = spread(C, 'CALDE', 'xs36_reg', 12)
print('\nCALDE 36m: n date %d, media %.2f, t NW(12) %.2f' % (len(d36), m36, t36))
ts = []
for ph in range(12):
    s = d36.iloc[ph::12]; ts.append((len(s), 100 * s.mean()))
print('serie non sovrapposte (n, media pp):', [(n, round(m, 1)) for n, m in ts])
print('per anno di formazione (pp):', (100 * d36.groupby(d36.index.year).mean()).round(1).to_dict())
