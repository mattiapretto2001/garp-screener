# Tabelle markdown dai risultati del backtest Svolta -> results/svolta_tabelle.md
import pandas as pd, numpy as np, os
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
R = pd.read_csv(f'{BASE}/results/svolta_risultati.csv')
S = pd.read_csv(f'{BASE}/results/svolta_serie_trimestrali.csv', index_col=0, parse_dates=True)
pc = lambda x: 'n.d.' if pd.isna(x) else f'{x*100:.1f}%'
pp = lambda x: '' if pd.isna(x) else f'{x*100:+.1f}'
tt = lambda x: '' if pd.isna(x) else f'{x:.1f}'
P = ['IS 2012-19', 'OOS 2020-24', 'Recente 2025-26']
out = []
def short(n):
    for a_, b_ in [(' (ricalcolato)', ''), ('B0 filtro base (marg. lordo >=55%, ricavi +20/60%, 1-15 Mld$)', 'B0 filtro base'), ('S0 Svolta completa (tutti gli 8 criteri)', 'S0 Svolta completa (8 criteri)'),
                   (' per punteggio', ''), ('margine operativo', 'marg. op.'), ('margine lordo', 'marg. lordo'), ('capitalizzazione', 'cap.'), ("qualita'", 'qualità'), ('criterio ', ''),
                   (' (livello -15/+20%)', ''), ('(runway >=2 anni, diluizione <10%, debito)', ''), ('minimo 52 sett. e 60-97% del massimo', 'min. 52 sett., 60-97% max')]:
        n = n.replace(a_, b_)
    return n.strip()
def main_table(names):
    out.append('| Strategia | Periodo | Titoli medi (trim. vuoti) | CAGR | CAGR con costi | Extra vs universo (t) | Extra vs SPY | Max DD trim. | Raddoppi 24m |')
    out.append('|---|---|---|---|---|---|---|---|---|')
    for n in names:
        for p in P:
            r = R[(R.esperimento == n) & (R.periodo == p)]
            if r.empty: continue
            r = r.iloc[0]
            out.append(f'| {short(n)} | {p} | {r.n_medio:.1f} ({r.trim_vuoti}) | {pc(r.CAGR)} | {pc(r.CAGR_costi)} | {pp(r.extra_vs_univ)} ({tt(r.t_vs_univ)}) | {pp(r.extra_vs_SPY)} | {pc(r.maxDD)} | {pc(r.hit2x_24m)} |')
    out.append('')
def delta_table(group):
    out.append('| Esperimento | Titoli IS / OOS / Rec. | CAGR IS / OOS / Rec. | Δ vs base IS / OOS / Rec. (pp) | t vs base IS / OOS | Extra vs universo IS / OOS / Rec. | |')
    out.append('|---|---|---|---|---|---|---|')
    for n in R[R.gruppo == group].esperimento.unique():
        x = R[R.esperimento == n].set_index('periodo')
        g = lambda c, p: x.loc[p, c] if p in x.index else np.nan
        ok = '✓' if (g('d_CAGR', P[0]) > 0 and g('d_CAGR', P[1]) > 0) else ''
        out.append(f"| {short(n)} | {g('n_medio',P[0]):.0f} / {g('n_medio',P[1]):.0f} / {g('n_medio',P[2]):.0f} | {pc(g('CAGR',P[0]))} / {pc(g('CAGR',P[1]))} / {pc(g('CAGR',P[2]))} | "
                   f"{pp(g('d_CAGR',P[0]))} / {pp(g('d_CAGR',P[1]))} / {pp(g('d_CAGR',P[2]))} | {tt(g('t_vs_base',P[0]))} / {tt(g('t_vs_base',P[1]))} | "
                   f"{pp(g('extra_vs_univ',P[0]))} / {pp(g('extra_vs_univ',P[1]))} / {pp(g('extra_vs_univ',P[2]))} | {ok} |")
    out.append('')
u = R[R.esperimento == R.esperimento.iloc[0]].set_index('periodo')
out.append('Riferimenti (CAGR): ' + '; '.join(f'{p}: universo {pc(u.loc[p, "CAGR_univ"])}, SPY {pc(u.loc[p, "CAGR_SPY"])}, max DD universo {pc(u.loc[p, "maxDD_univ"])}, raddoppi 24m universo {pc(u.loc[p, "hit2x_24m_univ"])}' for p in P) + '.\n')
out.append('### Strategie base e confronti\n')
main_table(list(R[R.gruppo == 'base'].esperimento.unique()) + ['M0 Moonshot base (ricalcolato)', 'G0 GARP base (ricalcolato)'])
out.append('### Portafogli concentrati\n')
main_table([n for n in R[R.gruppo == 'concentrati'].esperimento.unique() if 'S0 completa: top' not in n and '>=65' not in n] + [n for n in R[R.gruppo == 'approfondimento'].esperimento.unique() if n.startswith('B1 top')])
for g, tit in [('ablazione', 'Togliere un criterio alla volta (differenze rispetto a S0 completa)'), ('contributo', 'Aggiungere un criterio alla volta al filtro base B0 (differenze rispetto a B0)'), ('qualita', 'Variante "solo qualità"'),
               ('sensibilita', 'Sensibilità sui dati'), ('orizzonte', 'Orizzonti di detenzione'), ('vincitori', 'Regola "non vendere il vincitore"'), ('approfondimento', 'Approfondimento sul margine operativo (test aggiunti dopo aver visto i risultati)')]:
    out.append(f'### {tit}\n'); delta_table(g)
out.append('### Rendimento extra medio per coorte rispetto all\'universo (pp), a 3 / 6 / 12 / 24 mesi\n')
out.append('| Strategia | IS 2012-19 | OOS 2020-24 | Recente 2025-26 |'); out.append('|---|---|---|---|')
for n in ['S0 Svolta completa (tutti gli 8 criteri)', 'S6 Svolta: almeno 6 criteri su 8', 'S6 (>=6 su 8): top 4 per punteggio', 'B0 filtro base (marg. lordo >=55%, ricavi +20/60%, 1-15 Mld$)', 'B0 filtro base: top 4 per punteggio', 'B0 filtro base: top 8 per punteggio', 'B1 = B0 + C1 margine operativo in svolta', 'B1 top 4 per punteggio', "Q solo qualita': margine lordo >=55% non in calo + margine op. +5 pt", 'M0 Moonshot base (ricalcolato)', 'G0 GARP base (ricalcolato)']:
    x = R[R.esperimento == n].set_index('periodo')
    cells = [' / '.join(pp(x.loc[p, f'extra_coorte_{h}m']) for h in (3, 6, 12, 24)) if p in x.index else '' for p in P]
    out.append(f'| {short(n)} | ' + ' | '.join(cells) + ' |')
out.append('')
# rendimenti annui
cols = ['S0 Svolta completa (tutti gli 8 criteri)', 'S6 (>=6 su 8): top 4 per punteggio', 'B0 filtro base: top 4 per punteggio', 'B0 filtro base (marg. lordo >=55%, ricavi +20/60%, 1-15 Mld$)', 'B1 = B0 + C1 margine operativo in svolta', 'M0 Moonshot base (ricalcolato)', 'G0 GARP base (ricalcolato)', 'universo', 'SPY']
Y = S[cols].copy(); Y.index = Y.index + pd.offsets.QuarterEnd(1)   # rendimento attribuito al trimestre in cui matura
A = (1 + Y).groupby(Y.index.year).prod() - 1
out.append('### Rendimenti per anno solare (catena dei trimestri; 2012 = apr-dic, 2026 = fino al 03/11)\n')
out.append('| Anno | ' + ' | '.join(['Svolta completa', 'S6 top 4', 'B0 top 4', 'B0 tutti', 'B1', 'Moonshot', 'GARP', 'Universo EW', 'SPY']) + ' |')
out.append('|' + '---|' * (len(cols) + 1))
for y, r in A.iterrows(): out.append(f'| {y} | ' + ' | '.join(pc(v) for v in r.values) + ' |')
open(f'{BASE}/results/svolta_tabelle.md', 'w').write('\n'.join(out))
print('\n'.join(out))
