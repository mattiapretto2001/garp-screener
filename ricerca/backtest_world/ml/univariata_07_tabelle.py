# univariata_07: tabelle markdown per il report R_univariata.md (dai CSV di uni_out/)
import numpy as np, pandas as pd
from univariata_common import *
S = pd.read_csv(f'{OUT}/ic_summary.csv'); Q = pd.read_csv(f'{OUT}/quintili.csv')
SH = {'lineare': 'lin', 'campana (meglio al centro)': '∩', 'U (estremi)': 'U', 'curva: effetto concentrato in un estremo': 'estr', 'irregolare': 'irr'}
FAMN = {'VALUTAZIONE': 'Valutazione', 'QUALITA': 'Qualità', 'CRESCITA': 'Crescita', 'INVESTIMENTO': 'Investimento e capitale',
        'SOPRAVVIVENZA': 'Sopravvivenza', 'PREZZO': 'Prezzo e mercato', 'ANALISTI': 'Analisti', 'INDUSTRIA': 'Industria (temi)'}
W = {tk: S[S.tgt == tk].set_index('var') for tk in TGT}
QS = Q[Q.tgt == 'rk'].set_index('var')


def cell(tk, v):
    r = W[tk].loc[v]; k = 'S' if r.verdetto == 'solida' else ('f' if r.verdetto == 'fragile' else '·')
    if r.p_holm < 0.05: k += '*'
    return f'{100 * r["mean"]:+.1f} ({r.t:.1f}) {k}'.replace('.', ',')


lines = ['| Variabile | a) IC rango | b) Eccezionali | c) Disastri | Forma | WF% |', '|---|---|---|---|---|---|']
for fam, vs in fv3.FAMILIES.items():
    lines.append(f'| **{FAMN[fam]}** | | | | | |')
    for v in sorted(vs, key=lambda v: -abs(W['rk'].loc[v].t)):
        lines.append(f"| `{v}` | {cell('rk', v)} | {cell('top5', v)} | {cell('bot20', v)} | "
                     f"{SH.get(QS.loc[v].forma, '')} | {100 * W['rk'].loc[v].wf_hit:.0f} |")
open(f'{OUT}/tab_principale.md', 'w').write('\n'.join(lines) + '\n')
# variabili a coda asimmetrica, a parita' di volatilita'
A = pd.DataFrame({'t5': W['top5'].t, 't20': W['bot20'].t, 't5v': W['top5'].vol_t, 't20v': W['bot20'].vol_t, 'rk': W['rk'].t, 'rkv': W['rk'].vol_t,
                  'rks': W['rk'].sect_t})
print(A.round(1).sort_values('rkv').to_string())
