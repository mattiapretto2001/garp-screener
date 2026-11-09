# sint_02_oggi: conteggi descrittivi alla data piu' recente con le liste snelle (nessuna misura di rendimento). Esempio, non consigli.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src=open(f'{HERE}/sint_01_coerenza.py').read()
exec(src.split('SC = pd.read_pickle')[0])
exec('def score' + src.split('def score')[1].split('def quint_stats')[0])
d = F.date.max(); print('data', d.date())
X = F[F.date == d].copy()
S = {}
for gname in ['QUAL', 'GARP_c', 'CRESC', 'PREPROF', 'TEMI_ex']:
    m = G[gname][X.index]
    Xi = X[m]; s = score(Xi, L[LIST_OF[gname]]); S[gname] = s.rank(pct=True)
S = pd.DataFrame(S).reindex(X.index)
ok = GUARD[X.index] & (X.mcap_usd >= 2e9) & ~X.reg_rob.isin(['Asia'])
hi = (S >= 0.8) & ok.values[:, None]
print('profilo: nel profilo / top20% / top20% con guardia, >=2 Mld$, fuori Asia')
for c in S.columns: print(c, int(S[c].notna().sum()), int((S[c] >= 0.8).sum()), int(hi[c].sum()))
n = hi.sum(axis=1); print('alti in n profili (filtrati):', n.value_counts().sort_index().to_dict())
core = X.get('core')
top = X.assign(n=n, media=S.where(hi).mean(axis=1))[n >= 2].sort_values(['n', 'media'], ascending=False)
print(top[['t', 'name', 'reg_rob', 'n', 'media']].head(30).to_string())
if core is not None: print('core oggi:', int(core.sum()), 'di cui alti in >=1 profilo:', int((core.astype(bool) & (n >= 1)).sum()))
