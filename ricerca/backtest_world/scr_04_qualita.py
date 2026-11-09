# scr_04: nuovo screener "qualita' durevole" (Q1, Q2, Q3 fissati in scr_common prima dei test).
import pandas as pd, numpy as np
from scr_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
ROWS, SER = [], {}
B5 = mc >= 5e9
for reg, R in REG.items():
    for nm, m in [('Q1 ROE', Q1), ('Q2 margini', Q2), ('Q3 = Q1 o Q2', Q3)]:
        if reg != 'Mondo' and nm != 'Q3 = Q1 o Q2': continue
        o, r = ev(nm, m, QU & R, reg); ROWS += o; SER[(reg, nm)] = r
        o, _ = ev(nm + ' vs universo >=5 Mld$', m, QU & R & B5, reg, r=r); ROWS += o
o, rc = ev('Core (>=2 Mld$, guardia PEG)', CORE, UNI, 'Mondo'); ROWS += o
o, _ = ev('Base qualita\' senza ROE/margini (solo crescita, debito, PEG, >=5 Mld$)', QB, QU, 'Mondo'); ROWS += o
o, _ = ev('Q3 con esclusioni GARP', Q3_G, UNI, 'Mondo'); ROWS += o
o, _ = ev('Q3 tutti i settori', Q3_ALL, ALL, 'Mondo'); ROWS += o
# portafoglio misto: meta' core, meta' Q3 (ribilanciato ogni trimestre)
rq = SER[('Mondo', 'Q3 = Q1 o Q2')]
mix = 0.5 * rc + 0.5 * rq
o, _ = ev('50% core + 50% Q3', CORE | Q3, QU, 'Mondo', r=mix); ROWS += o
T = pd.DataFrame(ROWS); T.to_csv(f'{BASE}/res/scr_04_qualita.csv', index=False)
print(fmt(T).to_string())
print(T[T.periodo == '2012-26'][['gruppo', 'variante', 'n', 'maxdd', 'W5', 'L20']].round(3).to_string())
u = useries(QU)
print('correlazione extra-rendimenti trimestrali core vs Q3:', round(np.corrcoef((rc - u)[1:], (rq - u)[1:])[0, 1], 2))
print('volatilita annua core, Q3, misto, universo:', [round(s.std() * 2, 3) for s in (rc, rq, mix, u)])
yr = lambda s: (1 + s).groupby(pd.Index([d.year for d in s.index])).prod() - 1
print(pd.DataFrame({'core': yr(rc), 'Q3': yr(rq), 'misto': yr(mix), 'universo': yr(u), 'univ>=5': yr(useries(QU & B5))}).round(3).to_string())
c = caso(Q3, QU & B5); print('caso Q3 dentro universo >=5 Mld$', c)
c2 = caso(Q3, QB); print('caso Q3 dentro la base qualita\' (stessa crescita/debito/PEG)', c2)
pd.DataFrame([dict(pool='univ>=5', **c), dict(pool='base qualita', **c2)]).to_csv(f'{BASE}/res/scr_04_caso.csv', index=False)
print('Q3 regioni', F[Q3].reg.value_counts(normalize=True).round(2).to_dict(), 'settori', F[Q3].sector.value_counts(normalize=True).head(6).round(2).to_dict())
print('sovrapposizione Q3 con core', F[Q3 & CORE].shape[0] / Q3.sum(), 'con GARP lista', F[Q3 & A].shape[0] / Q3.sum())
# i tre nomi di Mattia
for tk in ['MA.US', 'SPGI.US', 'SAF.PA', 'V.US', 'MCO.US']:
    z = F[F.t == tk]
    if not len(z): print(tk, 'non nel pannello'); continue
    z = z.assign(Q1=Q1[z.index], Q2=Q2[z.index], QB=QB[z.index], roe5=F.roe5_n15[z.index], opm5=F.opm5_n20[z.index])
    print(tk, z[z.date >= '2019-01-01'][['date', 'Q1', 'Q2', 'QB', 'roe5', 'opm5', 'rev_cagr5', 'n_down5', 'peg', 'mcap_usd']].round(2).to_string())
# nomi piu' presenti negli ultimi 8 trimestri, con rendimento a 12 mesi dove noto
R8 = F[Q3 & (F.date >= REB[-8])]
top = R8.groupby(['t', 'name']).agg(trimestri=('date', 'size'), f12_medio=('f12', 'mean'), cap=('mcap_usd', 'last')).sort_values('trimestri', ascending=False)
print(top.head(80).round(2).to_string())
print('ultima data', REB[-1], 'Q3 n=', (Q3 & (F.date == REB[-1])).sum())
print(F[Q3 & (F.date == REB[-1])][['t', 'name', 'sector', 'mcap_usd']].sort_values('mcap_usd', ascending=False).to_string())
# vincitori 2012-26: chi e' stato preso e ha reso di piu' (rendimento a 3 anni)
W = F[Q3 & F.f36.notna()].sort_values('f36', ascending=False).drop_duplicates('t').head(25)[['t', 'name', 'date', 'f36']]
print(W.round(2).to_string())
