# Fase 6: tabelle per il rapporto (markdown) + statistiche su societa' tolte dal listino.
import pickle, pandas as pd, numpy as np
from world_common import *
TODAY = pd.Timestamp('2026-11-06')
X = pickle.load(open(f'{BASE}/res/bt.pkl', 'rb'))
R, NET, NS, SELS = X['RES'], X['NET'], X['NS'], X['SELS']
F = pd.read_pickle(f'{BASE}/res/feat.pkl')
FX = pd.read_pickle(f'{BASE}/eod/fx.pkl').sort_index().ffill()
B = pickle.load(open(f'{BASE}/eod/bench.pkl', 'rb'))
REB = sorted(F.date.unique()); NEXT = {t: (REB[i + 1] if i + 1 < len(REB) else TODAY) for i, t in enumerate(REB)}
def f(x, d=1): return '' if pd.isna(x) else f'{x * 100:+.{d}f}%'.replace('.', ',').replace('-', '−')
def fp(x): return '' if pd.isna(x) else f'{x * 100:.0f}%'
def fn(x, d=1): return '' if pd.isna(x) else f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
def annual(r):
    y = r.copy(); y.index = [NEXT[t] for t in r.index]
    y.index = [d.year if (d.month > 1 or d.day > 15) else d.year - 1 for d in pd.to_datetime(y.index)]
    return (1 + y).groupby(level=0).prod() - 1
def fxa(c, t): i = FX.index.searchsorted(t, side='right') - 1; return FX[c].iloc[i]
iw = B['IWDA.AS'].a.astype(float)
IWDA = pd.Series({t: iw[iw.index <= NEXT[t]].iloc[-1] / iw[iw.index <= t].iloc[-1] - 1 for t in REB})
L = []
PERS = ['2012-19', '2020-24', '2025-26', '2012-26']
def table(names, valuta='r_eur', title=''):
    L.append(f'\n{title}\n')
    for p in PERS:
        x0 = R[(R.periodo == p) & (R.variante == names[0])].iloc[0]
        L.append(f'\n**{p}** — universo {f(x0.CAGR_univ)}, VWCE/FTSE All-World {f(x0.CAGR_mondo)}, SPY {f(x0.CAGR_SPY)}\n')
        L.append('| Variante | Titoli | Rend. annuo netto | Volatilità | Perdita max | Anni sopra universo | Rotazione annua | Diff. vs universo (t) |\n|---|---|---|---|---|---|---|---|')
        for nm in names:
            x = R[(R.periodo == p) & (R.variante == nm)].iloc[0]
            L.append(f'| {nm} | {fn(x.n_medio, 0)} | **{f(x.CAGR)}** | {fp(x.vol)} | {f(x.maxDD, 0)} | {fp(x.anni_sopra_univ)} | {fp(x.rotazione)} | {f(x.d_vs_univ)} ({fn(x.t_vs_univ)}) |')
MAIN = ['V1 PEG<1 lista intera', 'V2 PEG<2 lista intera', 'V3 PEG<2 top 30', 'V4 PEG<1 top 30']
table(MAIN, title='## T1 Mondo, in euro')
table([m + ' (valuta locale)' for m in MAIN], title='## T2 Mondo, valuta locale')
REG = ['USA', 'Europa', 'Asia', 'Canada', 'Australia']
L.append('\n## T3 Regioni (variante 3 = PEG<2, top 30 dentro la regione; V2 = lista intera), in euro\n')
L.append('| Regione | Periodo | Titoli V3 | V3 netto | V2 netto | Universo regione | Diff. V3 vs univ. (t) | Perdita max V3 | V3 valuta locale |\n|---|---|---|---|---|---|---|---|---|')
for reg in REG:
    for p in PERS:
        a = R[(R.periodo == p) & (R.variante == f'V3 {reg}')].iloc[0]; b = R[(R.periodo == p) & (R.variante == f'V2 {reg} lista intera')].iloc[0]
        c = R[(R.periodo == p) & (R.variante == f'V3 {reg} (valuta locale)')].iloc[0]
        L.append(f'| {reg} | {p} | {fn(a.n_medio, 0)} | **{f(a.CAGR)}** | {f(b.CAGR)} | {f(a.CAGR_univ)} | {f(a.d_vs_univ)} ({fn(a.t_vs_univ)}) | {f(a.maxDD, 0)} | {f(c.CAGR)} |')
# anno per anno
AN = pd.DataFrame({k: annual(NET[k]) for k in MAIN + [f'V3 {r}' for r in ['USA', 'Europa', 'Asia']]})
AN['Universo'] = annual(X['UNIV']); AN['VWCE/All-World'] = annual(X['WORLD']); AN['MSCI World (IWDA)'] = annual(IWDA); AN['SPY'] = annual(X['SPY'])
L.append('\n## T4 Anno per anno, in euro, al netto dei costi (2026 fino al 06/11)\n')
cols = list(AN.columns)
L.append('| Anno | ' + ' | '.join(cols) + ' |\n|---|' + '---|' * len(cols))
for y in AN.index:
    L.append(f'| {y} | ' + ' | '.join(f(AN.loc[y, c], 0) for c in cols) + ' |')
AN.to_csv(f'{BASE}/res/world_annuali.csv')
# sopravvivenza
L.append('\n## T5 Società tolte dal listino (delisted)\n')
U = F[F.U]
comp = U.groupby('t').delisted.first()
L.append(f'- Società passate nell\'universo: {len(comp)}, di cui tolte dal listino oggi: {comp.mean():.0%} ({int(comp.sum())}).')
L.append(f'- Quota delle posizioni titolo-trimestre nell\'universo: {U.delisted.mean():.0%}. Per regione: ' +
         ', '.join(f'{r} {U[U.region == r].delisted.mean():.0%}' for r in REG))
L.append(f'- Trimestri chiusi con un "fallimento" (−100%) nell\'universo: {int((U.r <= -0.999).sum())}; uscite dal listino a metà trimestre: {int(U.ended.sum())}.')
for nm in MAIN:
    S = SELS[nm]; pos = [(t, x) for t in REB for x in S[t]]
    P = F.set_index(['date', 't']).loc[pos]
    alive = NET[nm + ' [solo vive]'] if nm + ' [solo vive]' in NET else None
    a = R[(R.variante == nm) & (R.periodo == '2012-26')].iloc[0]; b = R[(R.variante == nm + ' [solo vive]') & (R.periodo == '2012-26')].iloc[0]
    L.append(f'- {nm}: posizioni in società poi tolte dal listino {P.delisted.mean():.0%}; loro rendimento medio trimestrale {f(P[P.delisted].r_eur.mean())} '
             f'contro {f(P[~P.delisted].r_eur.mean())} delle altre; fallimenti {int((P.r <= -0.999).sum())}. '
             f'CAGR 2012-26 con tutte {f(a.CAGR)}, solo società ancora quotate {f(b.CAGR)}; universo con tutte {f(a.CAGR_univ)}, solo vive {f(b.CAGR_univ)}.')
L.append('\n| Variante | Periodo | Con tutte | Solo ancora quotate | Differenza |\n|---|---|---|---|---|')
for nm in MAIN + ['V3 USA', 'V3 Europa', 'V3 Asia']:
    for p in PERS:
        a = R[(R.variante == nm) & (R.periodo == p)].iloc[0]; b = R[(R.variante == nm + ' [solo vive]') & (R.periodo == p)].iloc[0]
        L.append(f'| {nm} | {p} | {f(a.CAGR)} | {f(b.CAGR)} | {f(b.CAGR - a.CAGR)} |')
    if nm == 'V3 PEG<2 top 30':
        for p in PERS:
            a = R[(R.variante == nm) & (R.periodo == p)].iloc[0]; b = R[(R.variante == nm + ' [solo vive]') & (R.periodo == p)].iloc[0]
            L.append(f'| Universo | {p} | {f(a.CAGR_univ)} | {f(b.CAGR_univ)} | {f(b.CAGR_univ - a.CAGR_univ)} |')
# caso
L.append('\n## T6 Caso: 30 titoli a sorte fra i promossi PEG<2 (500 estrazioni), rendimento annuo netto in euro: 5° / 50° / 95° percentile\n')
for p in PERS:
    v = np.array(X['RND'][p]); c3 = R[(R.variante == 'V3 PEG<2 top 30') & (R.periodo == p)].iloc[0].CAGR
    L.append(f'- {p}: {f(np.percentile(v, 5))} / {f(np.percentile(v, 50))} / {f(np.percentile(v, 95))}; V3 (punteggio) {f(c3)}, percentile {np.mean(v < c3) * 100:.0f}')
# composizione
L.append('\n## T7 Composizione media (variante 3, mondo)\n')
S = SELS['V3 PEG<2 top 30']; pos = [(t, x) for t in REB for x in S[t]]
P = F.set_index(['date', 't']).loc[pos]
L.append('- Per regione: ' + ', '.join(f'{k} {v:.0%}' for k, v in P.region.value_counts(normalize=True).items()))
L.append('- Per settore: ' + ', '.join(f'{k} {v:.0%}' for k, v in P.sector.value_counts(normalize=True).head(7).items()))
L.append(f'- PEG mediano {P.peg.median():.2f}; quota con PEG 1-2 {(P.peg >= 1).mean():.0%}; capitalizzazione mediana {P.mcap_usd.median() / 1e9:.1f} mld $')
L.append(f'- Dati da bilancio annuale (non trimestrale/semestrale): universo {U.src.eq("Y").mean():.0%}, posizioni V3 {P.src.eq("Y").mean():.0%}; semestrali {P["cov"].eq(6).mean():.0%}')
L.append('- Universo medio per data: ' + ', '.join(f'{r} {U[U.region == r].groupby("date").size().mean():.0f}' for r in REG))
L.append('- Promossi medi per data (PEG<2): ' + ', '.join(f'{r} {F[F.P2 & (F.region == r)].groupby("date").size().reindex(REB).fillna(0).mean():.0f}' for r in REG))
open(f'{BASE}/res/world_tabelle.md', 'w').write('\n'.join(L))
print('\n'.join(L))
