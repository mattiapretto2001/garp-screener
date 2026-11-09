# ml_08: tabelle di sintesi dell'interpretazione (output di ml_03): SHAP, permutazione, interazioni, forme
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3, regcommon as rc
TAG = sys.argv[1] if len(sys.argv) > 1 else ''
O = mc.OUT
IMP = pd.read_pickle(f'{O}/int_imp{TAG}.pkl'); SGN = pd.read_pickle(f'{O}/int_sgn{TAG}.pkl')
PERM = pd.read_pickle(f'{O}/int_perm{TAG}.pkl'); INT = pd.read_pickle(f'{O}/int_pairs{TAG}.pkl'); DIAG = pd.read_pickle(f'{O}/int_diag{TAG}.pkl')
CEL = pd.read_pickle(f'{O}/int_cells{TAG}.pkl'); SH = pd.read_pickle(f'{O}/int_shapes{TAG}.pkl')
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
TG = sorted(set(k for k, y in IMP.columns), key=['rk', 't5', 'b20', 'c50'].index)
out = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s); out.append(s)
for k in TG:
    cols = [c for c in IMP.columns if c[0] == k]
    I = IMP[cols]; S = SGN[[c for c in SGN.columns if c[0] == k]]
    top10 = I.rank(ascending=False) <= 10
    T = pd.DataFrame({'quota_shap': I.mean(1), 'anni_top10': top10.sum(1), 'segno_med': S.median(1), 'segno_concorde': (np.sign(S).eq(np.sign(S.median(1)), axis=0)).mean(1)})
    # permutazione
    P = PERM[PERM.target == k].set_index(['gruppo', 'anno']).drop(columns='target')
    ser = P.groupby(level=0).apply(lambda g: g.droplevel(0).stack())  # gruppo x data
    pm = {}
    for gname in P.index.get_level_values(0).unique():
        s = P.loc[gname].stack().dropna() if gname in P.index.get_level_values(0) else pd.Series(dtype=float)
        pm[gname] = (s.mean(), fv3.nw_t(s.values, 4), (P.loc[gname].mean(1) > 0).mean())
    PM = pd.DataFrame(pm, index=['perm_calo', 'perm_t', 'perm_anni_pos']).T
    T = T.join(PM)
    T['famiglia'] = [mc.FAM.get(v, '') for v in T.index]; T['nome'] = [rc.LAB.get(v, v) for v in T.index]
    T = T.sort_values('quota_shap', ascending=False); T.to_csv(f'{O}/tab_importanza_{k}{TAG}.csv')
    say(f'\n=== {k}: importanza (SHAP fuori campione, media 2016-2026) ===')
    say(T.head(18).round(3).to_string())
    stab = [I.iloc[:, i].corr(I.iloc[:, i + 1], method='spearman') for i in range(I.shape[1] - 1)]
    say('stabilita importanza anno su anno (Spearman): media %.2f min %.2f' % (np.mean(stab), np.min(stab)))
    F = I.groupby(lambda v: mc.FAM.get(v, '')).sum().mean(1).sort_values(ascending=False)
    FP = PM[PM.index.str.startswith('FAM:')]
    say('famiglie quota SHAP:', ', '.join(f'{f} {v:.2f}' for f, v in F.items()))
    say('famiglie permutazione (calo, t):', ', '.join(f'{f[4:]} {r.perm_calo:+.4f} ({r.perm_t:.1f})' for f, r in FP.sort_values('perm_calo', ascending=False).iterrows()))
    # interazioni
    Ik = INT[[c for c in INT.columns if c[0] == k]]; D = DIAG[[c for c in DIAG.columns if c[0] == k]]
    say(f'quota effetti principali (diagonale SHAP) {D.values.mean():.2f}; quota di tutte le interazioni {1 - D.values.mean():.2f}')
    m = Ik.mean(1).sort_values(ascending=False)
    say('coppie piu forti (quota media del totale, anni nei primi 10):')
    rk = Ik.rank(ascending=False)
    for p in m.index[:10]: say(f'   {p}: {m[p]:.4f} ({(rk.loc[p] <= 10).sum()} anni)')
    for a, b in [('revq', 'ev_sales'), ('revq', 'hi52'), ('logmcap', 'mom12_1'), ('rev_cagr', 'mom12_1'), ('revq', 'roe'), ('vol1y', 'logmcap'), ('fcf_m', 'revq'), ('rev_cagr', 'ev_sales')]:
        key = f'{a} x {b}' if f'{a} x {b}' in m.index else f'{b} x {a}'
        say(f'   a priori {key}: quota {m[key]:.4f}, posto {int((m > m[key]).sum()) + 1} su {len(m)}')
    C = CEL[CEL.target == k].groupby(['coppia', 'ta', 'tb']).inter.mean().unstack('tb')
    C.to_csv(f'{O}/tab_celle_{k}{TAG}.csv')
    say('celle 3x3 (terzo basso/medio/alto della prima x della seconda, valore = termine di interazione medio, ranghi con segno a priori):')
    say(C.round(4).to_string())
    # forme dal modello additivo per le prime 10 variabili
    Sk = SH[SH.target == k]
    prof = Sk.groupby('var')[[f'd{j}' for j in range(-1, 10)]].mean()
    prof = prof.loc[T.index[:12]]
    prof.to_csv(f'{O}/tab_forme_{k}{TAG}.csv')
    say('forme (modello additivo, SHAP medio per decile della variabile con segno a priori; d-1 = mancante):')
    say(prof.round(4).to_string())
open(f'{O}/ml_08{TAG}.log', 'w').write('\n'.join(out))
