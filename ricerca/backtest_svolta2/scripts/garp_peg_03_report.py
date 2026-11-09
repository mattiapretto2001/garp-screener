# Compone results/REPORT_garp_peg2_2026-11-06.md: testo (results/garp_peg_testo_*.md) + tabelle dai CSV di garp_peg_01.
import pandas as pd, numpy as np, os
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
OUT = f'{BASE}/results'
R = pd.read_csv(f'{OUT}/garp_peg_risultati.csv')
AN = pd.read_csv(f'{OUT}/garp_peg_annuali_netti.csv', index_col=0)
R = R[R.variante != 'V1t PEG<1 + tolleranza EPS']   # identica a V5a (stessi titoli)
R = R[~R.variante.str.contains('pesi uguali')]       # per brevita': i pesi uguali sono nella tabella delle misure e nel CSV
LAB = {'V1 PEG<1, EPS trim. stretto': '1 · PEG <1, EPS trim. stretto (base)',
       'V2 PEG<2, EPS trim. stretto': '2 · PEG <2, EPS trim. stretto',
       'V3 PEG<2 + tolleranza EPS': '3 · PEG <2 + tolleranza EPS',
       'V5a V3 solo PEG<1': '5a · var. 3, solo PEG <1',
       'V5b V3 solo PEG 1-2': '5b · var. 3, solo PEG 1-2'}
def lab(v):
    if v in LAB: return LAB[v]
    _, n, p, w = [s.strip() for s in v.replace('V4 top', 'V4|top').split('|')]
    return f"4 · {n} · {p} · {'pesi uguali' if w == 'pesi uguali' else 'PEG 30'}"
def f(x, d=1): return '' if pd.isna(x) else f'{x * 100:+.{d}f}%'.replace('.', ',').replace('-', '−')
def fp(x): return '' if pd.isna(x) else f'{x * 100:.0f}%'
def fn(x): return '' if pd.isna(x) else f'{x:.1f}'.replace('.', ',').replace('-', '−')
T = []
for p in ['Calibrazione 2012-19', 'Fuori campione 2020-24', 'Recente 2025-26']:
    x0 = R[R.periodo == p].iloc[0]
    T.append(f'\n### {p} — universo {f(x0.CAGR_univ)}, SPY {f(x0.CAGR_SPY)} l\'anno\n')
    hdr = '| Variante | Titoli | Rend. annuo netto | Volatilità | Perdita max | Anni sopra universo | Rotazione annua |'
    if p != 'Tutto 2012-26': hdr += ' Diff. vs riferimento (t) |'
    T.append(hdr); T.append('|' + '---|' * (hdr.count('|') - 1))
    for r in R[R.periodo == p].itertuples():
        row = f'| {lab(r.variante)} | {r.n_medio:.0f} | **{f(r.CAGR)}** | {fp(r.vol)} | {f(r.maxDD, 0)} | {fp(r.anni_battuto_univ)} | {fp(r.turnover_annuo)} |'
        if p != 'Tutto 2012-26': row += (f' {f(r.d_vs_base)} ({fn(r.t_vs_base)}) |' if pd.notna(r.d_vs_base) else ' |')
        T.append(row)
Y = ['\n| Variante | ' + ' | '.join(str(y) for y in range(2019, 2027)) + ' |', '|---' + '|---' * 8 + '|']
for c in [c for c in AN.columns if c not in ('V1t PEG<1 + tolleranza EPS', 'G0 GARP storico (lordo, controllo)') and 'pesi uguali' not in c]:
    nm = {'universo': 'Universo (equipesato)', 'SPY': 'SPY'}.get(c) or lab(c)
    Y.append(f'| {nm} | ' + ' | '.join(f(AN.loc[y, c], 0) for y in range(2019, 2027)) + ' |')
X = pd.read_csv(f'{OUT}/garp_peg_extra.csv')
X = X[X.variante.str.contains(r' \| top ')]
E = ['| Punteggio | Titoli | Calibrazione 2012-19 | Fuori campione 2020-24 | Recente 2025-26 | Tutto 2012-26 | Volatilità / perdita max (2012-26) | Percentile del sorteggio (fuori campione / recente) | Diff. vs punteggio dei filtri, t (cal. / f.c. / rec.) |',
     '|---|---|---|---|---|---|---|---|---|']
for v, g in X.groupby('variante', sort=False):
    g = g.set_index('periodo'); nm, n = v.split(' | top ')
    isr = nm.startswith('R')
    dd = '—' if isr else ' / '.join(f"{f(g.loc[p, 'd_vs_base'])} ({fn(g.loc[p, 't_vs_base'])})" for p in ['Calibrazione 2012-19', 'Fuori campione 2020-24', 'Recente 2025-26'])
    E.append(f"| {nm} | {n} | {f(g.loc['Calibrazione 2012-19', 'CAGR'])} | {f(g.loc['Fuori campione 2020-24', 'CAGR'])} | {f(g.loc['Recente 2025-26', 'CAGR'])} | **{f(g.loc['Tutto 2012-26', 'CAGR'])}** | "
             f"{fp(g.loc['Tutto 2012-26', 'vol'])} / {f(g.loc['Tutto 2012-26', 'maxDD'], 0)} | {g.loc['Fuori campione 2020-24', 'pct_caso']*100:.0f} / {g.loc['Recente 2025-26', 'pct_caso']*100:.0f} | {dd} |")
XA = pd.read_csv(f'{OUT}/garp_peg_extra_annuali.csv', index_col=0)
E2 = ['', '| Punteggio (anno per anno, netto) | ' + ' | '.join(str(y) for y in range(2019, 2027)) + ' |', '|---' + '|---' * 8 + '|']
for c in [c for c in XA.columns if ' | top ' in c]:
    E2.append(f'| {c} | ' + ' | '.join(f(XA.loc[y, c], 0) for y in range(2019, 2027)) + ' |')
txt = open(f'{OUT}/garp_peg_testo.md').read()
txt = txt.replace('{{TABELLE_PERIODI}}', '\n'.join(T)).replace('{{TABELLA_ANNI}}', '\n'.join(Y)).replace('{{TABELLA_EXTRA}}', '\n'.join(E))
open(f'{OUT}/REPORT_garp_peg2_2026-11-06.md', 'w').write(txt)
print(len(txt.encode()), 'byte')
