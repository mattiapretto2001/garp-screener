# avv_reg_01 (verifica avversariale delle regressioni): rifà il Fama-MacBeth principale (37 variabili) e lo ripete
# con varianti di robustezza: t con piu' ritardi / solo date annuali non sovrapposte, senza 2025-26, senza 2020,
# senza Asia/Altri, senza l'1% dei rendimenti migliori, solo >=2 Mld$, rappresentanti scelti con la regola stretta.
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
warnings.filterwarnings('ignore')
OUT = rc.HERE + '/avv_reg_out'
M0 = rc.load(); M0 = M0[M0.fwd12_eur.notna()].reset_index(drop=True)
G = rc.GLOBAL; ZG = ['z_' + c for c in G]
KEY = ['hist_y', 'fcf_m', 'dsh1', 'hi52', 'fin_age_d', 'mom12_1', 'ev_sales', 'cash_mcap', 'vol1y', 'logmcap', 'rev_cagr', 'accruals', 'fcfy']

def prep(S, by=('date', 'reg'), rerank=True, xcols=ZG):
    S = S.copy()
    if rerank:
        S[xcols] = rc.rank_z(S, xcols, list(by)).values
    S['y_rk'] = rc.rank_z(S.assign(f=S.fwd12_eur), ['f'], list(by))['f']
    gq = S.groupby(list(by)).fwd12_eur; rk = (gq.rank() - 0.5) / gq.transform('count')
    S['top5'] = (rk >= 0.95) * 100.; S['bot20'] = (rk <= 0.20) * 100.
    return S

def run(S, name, xcols=ZG, lags=4, ys=('y_rk', 'top5', 'bot20')):
    out = {}
    for y in ys:
        C = rc.fm(S[['date'] + xcols + [y]], xcols, y); C.columns = [c[2:] for c in xcols]
        out[y] = C.apply(lambda s: fv3.nw_t(s, lags))
    df = pd.DataFrame(out); df['variante'] = name
    return df, C

res = []
# 0. riproduzione (target originali: rk12_reg, top5_reg, bot20_reg)
B = M0.copy(); B['y_rk'] = (B.rk12_reg - 0.5) * rc.S12; B['top5'] = B.top5_reg.astype(float) * 100; B['bot20'] = B.bot20_reg.astype(float) * 100
df, _ = run(B, '0 base (riproduzione)'); res.append(df)
Cb = {y: rc.fm(B[['date'] + ZG + [y]], ZG, y) for y in ['y_rk', 'top5', 'bot20']}
for y in Cb: Cb[y].columns = G
# 1. t con 8 ritardi
res.append(pd.DataFrame({y: Cb[y].apply(lambda s: fv3.nw_t(s, 8)) for y in Cb}).assign(variante='1 NW 8 ritardi'))
# 2. solo date di dicembre (osservazioni annuali non sovrapposte), t semplice (lags 0)
dec = [d for d in Cb['y_rk'].index if d.month == 12]
res.append(pd.DataFrame({y: Cb[y].loc[dec].apply(lambda s: fv3.nw_t(s, 0)) for y in Cb}).assign(variante='2 solo dicembre (annuale, n=%d)' % len(dec)))
# 2b. media dei 4 t ottenuti con le 4 'fasi' trimestrali non sovrapposte (min |t|)
ph = {}
for mth in (3, 6, 9, 12):
    dd = [d for d in Cb['y_rk'].index if d.month == mth]
    ph[mth] = Cb['y_rk'].loc[dd].apply(lambda s: fv3.nw_t(s, 0))
res.append(pd.DataFrame({'y_rk': pd.DataFrame(ph).min(1), 'top5': np.nan, 'bot20': np.nan}).assign(variante='2b min t sulle 4 fasi annuali (rango)'))
# 3. senza rendimenti 2025-26 (date <= 2023-12-31) e senza date >= 2025
for nm, msk in [('3a senza finestre che toccano 2025-26 (date<=2023-12)', B.date <= '2023-12-31'),
                ('3b senza date 2025', B.date < '2025-01-01'),
                ('4 senza finestre che toccano 2020 (date 2019-2020 tolte)', ~B.date.between('2019-01-01', '2020-12-31')),
                ('4b senza 2020-21 (bolla e crollo: date 2019-03..2021-12 tolte)', ~B.date.between('2019-01-01', '2021-12-31'))]:
    df, _ = run(B[msk], nm); res.append(df)
# 5. senza Asia / senza Asia e Altri (ranghi restano per regione: togliere una regione non cambia i ranghi delle altre)
for nm, msk in [('5a senza Asia', B.reg != 'Asia'), ('5b solo USA+Europa', B.reg.isin(['USA', 'Europa'])), ('5c solo USA', B.reg == 'USA')]:
    df, _ = run(B[msk], nm); res.append(df)
# 6. senza l'1% migliore dei rendimenti per data x regione (target rifatti)
q99 = B.groupby(['date', 'reg']).fwd12_eur.transform(lambda s: s.quantile(0.99))
df, _ = run(prep(B[B.fwd12_eur < q99], rerank=False), '6 senza 1% rendimenti migliori'); res.append(df)
# 6b senza il 5% migliore (il rango non dipende piu' dalle eccezionali)
q95 = B.groupby(['date', 'reg']).fwd12_eur.transform(lambda s: s.quantile(0.95))
df, _ = run(prep(B[B.fwd12_eur < q95], rerank=False), '6b senza 5% rendimenti migliori', ys=('y_rk', 'bot20')); res.append(df)
# 7. solo >=2 Mld$ e >=1 Mld$ (ranghi e target rifatti dentro)
for thr in (1e9, 2e9, 10e9):
    df, _ = run(prep(B[B.mcap_usd >= thr]), '7 solo >=%g Mld$' % (thr / 1e9)); res.append(df)
# 8. regola stretta dei rappresentanti: cluster 29 -> npm (copertura 1.0); cluster 32 -> burn_mcap; cluster 36 -> ma200
STRICT = [c for c in G if c not in ('opm_avg5', 'fcfy', 'fcf_m', 'hi52', 'mom12_1')] + ['npm', 'burn_mcap', 'ma200']
ZS = ['z_' + c for c in STRICT]
df, _ = run(B, '8 regola stretta (npm, burn_mcap, ma200 al posto di opm_avg5, fcfy, fcf_m, hi52, mom12_1)', xcols=ZS); res.append(df)
R = pd.concat(res)
R.index.name = 'var'
R.to_csv(f'{OUT}/fm_robusto.csv')
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
for y in ['y_rk', 'top5', 'bot20']:
    T = R.reset_index().pivot_table(index='var', columns='variante', values=y)
    keep = [k for k in KEY + ['burn_mcap', 'ma200', 'npm'] if k in T.index]
    print('\n=== target', y); print(T.loc[keep].round(1).T.to_string())
