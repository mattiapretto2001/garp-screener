# Tabelle markdown per il rapporto svolta2 (da results/svolta2_*.csv) -> results/svolta2_tabelle.md
import pandas as pd, os
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
R = pd.read_csv(f'{BASE}/results/svolta2_varianti.csv')
A = pd.read_csv(f'{BASE}/results/svolta2_annuali.csv', index_col=0)
D = pd.read_csv(f'{BASE}/results/svolta2_promossi_recenti.csv')
pc = lambda v: '' if pd.isna(v) else f'{v*100:.1f}%'.replace('.', ',')
pp = lambda v: '' if pd.isna(v) else f'{v*100:+.1f}'.replace('.', ',')
nf = lambda v, d=1: '' if pd.isna(v) else f'{v:.{d}f}'.replace('.', ',')
o = []
# anno per anno
T1 = [('B1', 'B1'), ('B1 top 8', 'B1 top 8'), ('B0', 'B0'), ('Moonshot', 'Moonshot'), ('GARP', 'GARP'), ('universo', 'Universo EW'), ('SPY', 'SPY')]
T2 = [('a) B1 + prezzo sopra media 200 gg', 'a) +MA200'), ('b) B1 max 2 per settore SIC2', 'b) max 2/sett.'), ('b) B1 max 3 per settore SIC2', 'b) max 3/sett.'),
      ('c) B1 e Moonshot (entrambi)', 'c) B1∩Moon'), ('c) B1 oppure Moonshot (unione)', 'c) B1∪Moon'), ('e) B1 senza software applicativo (SIC 7372)', 'e) senza 7372'),
      ('e) B1 senza tutto il software/IT (SIC 737x)', 'e) senza 737x'), ('a+b) B1 + media 200 gg + max 3 per settore', 'a+b'),
      ('d) +5 pt, alternativa trimestrale +12', 'd) alt. trim. +12'), ('d) +5 pt, livello -15/+15%', 'd) +5, -15/+15'), ('d) +5 pt, livello -20/+20%', 'd) +5, -20/+20'),
      ('d) +3 pt, livello -15/+20%', 'd) +3, -15/+20'), ('d) +8 pt, livello -15/+20%', 'd) +8, -15/+20')]
for T, title in [(T1, 'Strategie di riferimento'), (T2, 'Varianti nuove')]:
    o.append(f'#### {title}\n')
    o.append('| Anno | ' + ' | '.join(l for _, l in T) + ' |'); o.append('|' + '---|' * (len(T) + 1))
    for y, r in A.iterrows(): o.append(f'| {y} | ' + ' | '.join(pc(r[c]) for c, _ in T) + ' |')
    o.append('')
# varianti
o.append('#### Varianti: metriche per periodo\n')
o.append('| Variante | Periodo | Titoli medi (trim. vuoti) | CAGR | CAGR con costi | Extra vs universo (t) | Δ vs B1 pp (t) | Max DD trim. | Credibile |')
o.append('|---|---|---|---|---|---|---|---|---|')
names = ['B1', 'B1 top 8', 'B0', 'Moonshot', 'GARP'] + [c for c, _ in T2] + ['d) +5 pt senza alternativa trimestrale +8', 'd) +5 pt, alternativa trimestrale +5', 'd) +4 pt, livello -15/+20%', 'd) +5 pt, livello -15/+25%']
B1 = R[R.variante == 'B1'].set_index('periodo').CAGR
for n in names:
    x = R[R.variante == n].set_index('periodo')
    cred = ''
    if n not in ('B1',):
        ok = x.loc['IS 2012-19', 'CAGR'] > B1['IS 2012-19'] and x.loc['OOS 2020-24', 'CAGR'] > B1['OOS 2020-24']
        cred = '✓' if ok else ''
    for p, r in x.iterrows():
        dv = '' if n == 'B1' else f"{pp(r.d_vs_base)} ({nf(r.t_vs_base)})"
        o.append(f'| {n} | {p} | {nf(r.n_medio)} ({int(r.trim_vuoti)}) | {pc(r.CAGR)} | {pc(r.CAGR_costi)} | {pp(r.CAGR - r.CAGR_univ)} ({nf(r.t_vs_univ)}) | {dv} | {pc(r.maxDD)} | {cred if p.startswith("IS") else ""} |')
o.append('')
# griglia
d = R[R.gruppo == 'd'].copy()
d[['dmin', 'lo', 'hi']] = d.variante.str.extract(r'\+(\d+) pt, livello (-\d+)/\+(\d+)').astype(int)
for p in ['IS 2012-19', 'OOS 2020-24', 'Recente 2025-26']:
    x = d[d.periodo == p].pivot_table(index=['dmin', 'lo'], columns='hi', values='CAGR')
    o.append(f'#### Griglia CAGR {p} (righe: aumento minimo margine op. in punti, livello minimo; colonne: livello massimo)\n')
    o.append('| +pt | min | ' + ' | '.join(f'+{h}%' for h in x.columns) + ' |'); o.append('|---|---|' + '---|' * len(x.columns))
    for (a, b), r in x.iterrows(): o.append(f'| +{a} | {b}% | ' + ' | '.join(pc(v) for v in r.values) + ' |')
    o.append('')
open(f'{BASE}/results/svolta2_tabelle.md', 'w').write('\n'.join(o)); print('\n'.join(o))
