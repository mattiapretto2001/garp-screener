# Controlli aggiuntivi: bias di sopravvivenza, robustezza senza l'anno migliore, promossi all'ultima data -> results/svolta_extra.txt
import pandas as pd, numpy as np, os
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
out = []
sv = pd.read_csv(f'{BASE}/cache/surv.csv')
for y in (2015, 2019):
    x = sv[sv[f'rev{y}'] >= 100e6]
    out.append(f'Societa con ricavi annui >=100 M$ nel {y}: {len(x)}; non nell\'universo di oggi: {1 - x.in_univ.mean():.0%}')
R = pd.read_csv(f'{BASE}/results/svolta_risultati.csv')
S = pd.read_csv(f'{BASE}/results/svolta_serie_trimestrali.csv', index_col=0, parse_dates=True)
def cagr(r): return (1 + r).prod() ** (4 / len(r)) - 1
oos = S[(S.index >= '2020-01-01') & (S.index <= '2024-09-30')]
for n in ['B1 = B0 + C1 margine operativo in svolta', 'B1 top 4 per punteggio', 'B0 filtro base (marg. lordo >=55%, ricavi +20/60%, 1-15 Mld$)', 'M0 Moonshot base (ricalcolato)', 'G0 GARP base (ricalcolato)', 'S6 (>=6 su 8): top 4 per punteggio']:
    for excl, lab in [(['2020-03-31', '2020-06-30', '2020-09-30'], 'senza apr-dic 2020'), (['2024-03-31', '2024-06-30', '2024-09-30'], 'senza apr-dic 2024')]:
        o = oos.drop(pd.to_datetime(excl))
        out.append(f'OOS {lab}: {n}: CAGR {cagr(o[n]):.1%} vs universo {cagr(o.universo):.1%}')
# quota di trimestri in cui B1 batte l'universo
for p in ['IS 2012-19', 'OOS 2020-24', 'Recente 2025-26']:
    x = R[(R.esperimento == 'B1 = B0 + C1 margine operativo in svolta') & (R.periodo == p)].iloc[0]
    out.append(f'B1 {p}: trimestri vuoti {x.trim_vuoti}, trimestri battuto universo {x.trim_battuto_univ:.0%}, costo annuo stimato {x.costo_annuo:.1%}')
P = pd.read_csv(f'{BASE}/results/svolta_promossi.csv', parse_dates=['date'])
last = P[P.date == P.date.max()]
uni = pd.read_csv(f'{BASE}/cache/universe.csv').set_index('cik').name
last = last.assign(nome=last.cik.map(uni)).sort_values('score', ascending=False)
out.append(f'\nPromossi B1 al {P.date.max().date()} (dati depositati entro quella data):')
for r in last[last.B1].itertuples():
    out.append(f'  {r.ticker} {r.nome}: punteggio {r.score:.0f}, criteri {r.n_criteri}/8, cap {r.mcap/1e9:.1f} Mld$, ricavi a/a {r.yoy0:.0%}, marg. lordo {r.gm_ttm:.0%}, marg. op. {r.opm_ttm4:.0%} -> {r.opm_ttm:.0%}')
out.append('Primi 8 S6 (>=6 criteri) per punteggio:')
for r in last[last.n_criteri >= 6].head(8).itertuples():
    out.append(f'  {r.ticker} {r.nome}: punteggio {r.score:.0f}, criteri {r.n_criteri}/8')
open(f'{BASE}/results/svolta_extra.txt', 'w').write('\n'.join(out)); print('\n'.join(out))
