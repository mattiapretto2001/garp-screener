# Prova C: tabelle in markdown per il rapporto (dai file di c04 e c05). Nessuna chiamata EODHD.
import pickle, pandas as pd, numpy as np
S = pickle.load(open('dati/sintesi.pkl', 'rb')); ALL, TX = S['ALL'], S['TX']
CV = pd.read_csv('dati/cassa_vwce.csv')
NM = {('L','none'): 'Lista, lasciar correre (base)', ('L','S30'): 'Lista + stop −30%', ('L','S50'): 'Lista + stop −50%',
      ('L','TR2'): 'Lista + metà a ×2', ('L','TR3'): 'Lista + metà a ×3', ('L','AD30'): 'Lista + mediare a −30%'}
for b, y in [('T2', '2 anni'), ('T3', '3 anni')]:
    NM.update({(b,'none'): f'{y}, lasciar correre', (b,'S30'): f'{y} + stop −30%', (b,'S50'): f'{y} + stop −50%',
               (b,'TR2'): f'{y} + metà a ×2', (b,'TR3'): f'{y} + metà a ×3', (b,'AD30'): f'{y} + mediare a −30%'})
ORDER = [(b, o) for b in ['L', 'T2', 'T3'] for o in ['none', 'S30', 'S50', 'TR2', 'TR3', 'AD30']]
def p(x, d=1, sign=True):
    if x is None or pd.isna(x): return 'n.d.'
    s = f'{x*100:+.{d}f}%' if sign else f'{x*100:.{d}f}%'
    return s.replace('.', ',').replace('-', '−')
def q(x): return f'{x*100:.0f}%'
out = []
for key, lab in [('P1', '2000-2011, proxy USA'), ('P2', '2012-2026, liste vere (mondo)')]:
    A = ALL[key].set_index(['base', 'over'])
    out.append(f'\n### {lab}\n')
    out.append('| Regola | Metà moltiplicatori: mediana (10% peggiore – 10% migliore dei portafogli) | Perdita massima della metà | 50/50 ribilanciato | Perdita massima 50/50 | Batte la base (stessi portafogli) |')
    out.append('|---|---|---|---|---|---|')
    for k in ORDER:
        r = A.loc[k]
        nm = f'**{NM[k]}**' if k in [('L','none'), ('L','TR3')] else NM[k]
        out.append(f"| {nm} | {p(r.s_med)} ({p(r.s_p10)} / {p(r.s_p90)}) | {p(r.s_dd,0)} | {p(r.cr_med)} | {p(r.cr_dd,0)} | {'–' if k==('L','none') else q(r.cr_gt_ref)} |")
    r = A.loc[('L','none')]
    out.append(f"| *VWCE da solo* | {p(r.w)} | {p(r.w_dd,0)} | | | |")
# esiti per posizione
out.append('\n### Esiti per posizione\n')
out.append('| Periodo | Regola | Posizioni per portafoglio | Tenute in media (mesi) | In guadagno | A zero (−90% o peggio) | Perdono metà o più | ×2 | ×3 | ×5 | ×10 | Arrivate almeno una volta a ×3 / ×5 / ×10 |')
out.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
def pc(x): 
    if x < 0.0005 and x > 0: return '<0,1%'
    return f'{x*100:.1f}%'.replace('.', ',')
for key, lab in [('P1', '2000-11'), ('P2', '2012-26')]:
    A = ALL[key].set_index(['base', 'over'])
    for k in [('L','none'), ('L','S30'), ('L','TR3'), ('T3','none'), ('T3','S30'), ('T3','S50')]:
        r = A.loc[k]
        out.append(f"| {lab} | {NM[k]} | {r.npos:.0f} | {r.hold*12:.0f} | {pc(r.winrate)} | {pc(r.zero)} | {pc(r.half)} | {pc(r.x2)} | {pc(r.x3)} | {pc(r.x5)} | {pc(r.x10)} | {pc(r.pk3)} / {pc(r.pk5)} / {pc(r.pk10)} |")
# concentrazione
out.append('\n### Concentrazione\n')
out.append('| Periodo | Regola | Il 10% migliore delle posizioni, sul guadagno netto | … sulla somma dei soli guadagni | Portafogli con guadagno netto negativo |')
out.append('|---|---|---|---|---|')
for key, lab in [('P1', '2000-11'), ('P2', '2012-26')]:
    A = ALL[key].set_index(['base', 'over'])
    for k in [('L','none'), ('L','TR3'), ('T3','none'), ('T3','TR2')]:
        r = A.loc[k]
        t = 'n.d.' if pd.isna(r.top10) or r.pl_neg > 0.5 else f'{r.top10*100:.0f}%'
        out.append(f"| {lab} | {NM[k]} | {t} | {r.top10_pos*100:.0f}% | {r.pl_neg*100:.0f}% |")
# controlli
out.append('\n### Controlli: la base contro "Lista + metà a ×3" e contro "3 anni"\n')
out.append('| Universo | VWCE | Base: metà / 50/50 | Lista + metà a ×3: 50/50 (batte la base) | Lista + stop −30%: 50/50 | 3 anni: 50/50 | 2 anni: 50/50 |')
out.append('|---|---|---|---|---|---|---|')
for key, lab in [('P1', '2000-11 proxy (correzione stimata, principale)'), ('P1p', '2000-11 proxy, correzione prudente'), ('P2', '2012-26 liste vere, mondo'),
                 ('P2us', '2012-26 liste vere, solo USA'), ('P3', '2012-25 proxy (ponte)')]:
    A = ALL[key].set_index(['base', 'over'])
    b = A.loc[('L','none')]
    out.append(f"| {lab} | {p(b.w)} | {p(b.s_med)} / {p(b.cr_med)} | {p(A.loc[('L','TR3')].cr_med)} ({q(A.loc[('L','TR3')].cr_gt_ref)}) | {p(A.loc[('L','S30')].cr_med)} | {p(A.loc[('T3','none')].cr_med)} | {p(A.loc[('T2','none')].cr_med)} |")
out.append('\n### Contanti parcheggiati in VWCE (controllo dichiarato dopo)\n')
out.append('| Periodo | Regola | Metà moltiplicatori | 50/50 | Perdita massima 50/50 | Contanti medi nella metà | Batte la base |')
out.append('|---|---|---|---|---|---|---|')
for key, lab in [('P1', '2000-11'), ('P2', '2012-26'), ('P3', '2012-25 ponte')]:
    X = CV[CV.key == key].set_index(['base', 'over'])
    for k in [('L','none'), ('L','TR3'), ('L','S30'), ('L','AD30'), ('T2','none'), ('T3','none')]:
        r = X.loc[k]
        out.append(f"| {lab} | {NM[k]} | {p(r.s_med)} | {p(r.cr_med)} | {p(r.cr_dd,0)} | {q(r.cash)} | {'–' if k==('L','none') else q(r.gt_ref)} |")
out.append('\n### Tasse (2012-2026)\n')
out.append('| Regola | Metà moltiplicatori dopo le tasse | 50/50 senza ribilanciamento, dopo le tasse | Operazioni all\'anno |')
out.append('|---|---|---|---|')
X = TX['P2'].set_index(['base', 'over'])
for k in [('L','none'), ('L','TR3'), ('L','S30'), ('L','AD30'), ('T2','none'), ('T3','none')]:
    r = X.loc[k]
    out.append(f"| {NM[k]} | {p(r.s_tax)} | {p(r.c_tax)} | {r.trades:.0f} |")
out.append(f"| *VWCE da solo* | {p(X.loc[('L','none')].w_tax)} | | |")
open('dati/tabelle_md.txt', 'w').write('\n'.join(out))
print('\n'.join(out))
