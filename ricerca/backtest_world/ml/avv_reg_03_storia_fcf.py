# avv_reg_03: (1) hist_y regge senza l'artefatto dell'archivio piu' corto per le societa' uscite? (2) margine FCF senza il triangolo
# fcf_m / fcfy / ev_sales (quasi un'identita'); (3) interazione ricavi x prezzo/max: sottocampioni.
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
warnings.filterwarnings('ignore')
M = rc.load(); M = M[M.fwd12_eur.notna()].reset_index(drop=True)
H = fv3.load(cols=['hist_y', 'age_y', 'delisted', 'fwd12_eur']); H = H[H.fwd12_eur.notna()].reset_index(drop=True)
M['hist_raw'] = H.hist_y.values; M['age_raw'] = H.age_y.values; M['delisted'] = H.delisted.values
G = rc.GLOBAL; ZG = ['z_' + c for c in G]

def prep(S, by=('date', 'reg'), xcols=ZG):
    S = S.copy(); S[xcols] = rc.rank_z(S, xcols, list(by)).values
    S['y_rk'] = rc.rank_z(S.assign(f=S.fwd12_eur), ['f'], list(by))['f']
    gq = S.groupby(list(by)).fwd12_eur; rk = (gq.rank() - 0.5) / gq.transform('count')
    S['top5'] = (rk >= 0.95) * 100.; S['bot20'] = (rk <= 0.20) * 100.
    return S

def show(S, xcols, name, keys, ys=('y_rk', 'bot20')):
    parts = []
    for y in ys:
        C = rc.fm(S[['date'] + xcols + [y]], xcols, y)
        parts.append('%s: ' % y + ', '.join('%s %.1f' % (k[2:] if k.startswith('z_') else k, fv3.nw_t(C[k])) for k in keys))
    print('%-62s n/data %4d | %s' % (name, len(S) / S.date.nunique(), ' || '.join(parts)))

print('--- (1) hist_y e artefatto delle uscite')
show(prep(M), ZG, 'tutti (ranghi rifatti, controllo)', ['z_hist_y'])
show(prep(M[~M.delisted.astype(bool)]), ZG, 'solo societa ancora quotate oggi', ['z_hist_y'])
show(prep(M[M.delisted.astype(bool)]), ZG, 'solo societa poi uscite', ['z_hist_y'])
U = M[M.reg == 'USA'].copy()
show(prep(U), ZG, 'USA', ['z_hist_y'])
U2 = U[~((U.hist_raw < U.age_raw - 2) & U.delisted.astype(bool))]
show(prep(U2), ZG, 'USA senza uscite con archivio corto (hist<eta-2)', ['z_hist_y'])
U3 = U[U.age_raw.notna()].copy(); U3['age_y'] = U3.age_raw
X3 = [c for c in ZG if c != 'z_hist_y'] + ['z_age_y']
U3['z_age_y'] = 0.0
show(prep(U3, xcols=[c for c in ZG if c != 'z_hist_y'] + ['z_age_y']).pipe(lambda S: S), X3, 'USA: eta dalla quotazione AL POSTO di hist_y', ['z_age_y']) if False else None
S3 = U3.copy(); S3['z_age_y'] = rc.rank_z(S3, ['age_y'], ['date'])['age_y']
S3 = prep(S3, xcols=X3)
show(S3, X3, 'USA: eta dalla quotazione (IPODate) al posto di hist_y', ['z_age_y'])
U4 = U[U.age_raw.notna() & (U.age_raw <= 15)]
show(prep(U4), ZG, 'USA quotate da <=15 anni (archivio uguale fra uscite e attive)', ['z_hist_y'])

print('\n--- (2) margine FCF e il triangolo fcf_m / fcfy / ev_sales')
B = prep(M)
for drop in [[], ['z_fcfy'], ['z_ev_sales'], ['z_fcfy', 'z_ev_sales']]:
    X = [c for c in ZG if c not in drop]
    show(B, X, 'senza ' + (','.join(d[2:] for d in drop) or 'niente'), [k for k in ['z_fcf_m', 'z_fcfy', 'z_ev_sales'] if k in X])
# per anno: coefficiente fcf_m sul rango
C = rc.fm(B[['date'] + ZG + ['y_rk']], ZG, 'y_rk')
yr = C['z_fcf_m'].groupby(C.index.year).mean()
print('coef fcf_m sul rango per anno della data:', ' '.join('%d:%+.3f' % (k, v) for k, v in yr.items()))
yr = C['z_hist_y'].groupby(C.index.year).mean()
print('coef hist_y sul rango per anno della data:', ' '.join('%d:%+.3f' % (k, v) for k, v in yr.items()))

print('\n--- (3) interazione ricavi trimestre x prezzo/max (universo settori GARP, come regressioni_05)')
S0 = M[~M.excl_sector].copy()
for nm, msk in [('settori GARP (riproduzione)', None), ('>=2 Mld$', S0.mcap_usd >= 2e9), ('senza date 2019-2021', ~S0.date.between('2019-01-01', '2021-12-31')),
                ('date <=2023-12', S0.date <= '2023-12-31'), ('senza Asia', S0.reg != 'Asia'), ('solo USA', S0.reg == 'USA')]:
    S = prep(S0 if msk is None else S0[msk])
    S['i_rh'] = S.z_revq.fillna(0) * S.z_hi52.fillna(0)
    q99 = S.groupby(['date', 'reg']).fwd12_eur.transform(lambda s: s.quantile(0.99))
    show(S, ZG + ['i_rh'], 'revq x hi52 | ' + nm, ['i_rh'], ys=('y_rk', 'top5'))
S = prep(S0); q99 = S.groupby(['date', 'reg']).fwd12_eur.transform(lambda s: s.quantile(0.99))
S = prep(S0[(S.fwd12_eur < q99).values]); S['i_rh'] = S.z_revq.fillna(0) * S.z_hi52.fillna(0)
show(S, ZG + ['i_rh'], 'revq x hi52 | senza 1% rendimenti migliori', ['i_rh'], ys=('y_rk', 'top5'))
