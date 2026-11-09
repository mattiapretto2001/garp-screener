# scr_04b: nomi famosi "di qualita'": in quanti trimestri (2016-26) Q3 li ha presi e, quando no, quale regola li ha fermati.
import pandas as pd, numpy as np
from scr_common import *
NOMI = ['MA.US', 'SPGI.US', 'SAF.PA', 'V.US', 'MCO.US', 'MSCI.US', 'RMS.PA', 'MC.PA', 'OR.PA', 'COST.US', 'ASML.AS', 'NOVO-B.CO', 'MSFT.US',
        'AAPL.US', 'GOOG.US', 'NVDA.US', 'ISRG.US', 'ADP.US', 'CPRT.US', 'CSU.TO', 'HEI.US', 'TDG.US', 'ODFL.US', 'ORLY.US', 'AZO.US', 'FICO.US',
        'REL.LSE', 'WKL.AS', 'EXPN.LSE', 'ATCO-A.ST', 'AIR.PA', 'SU.PA', 'DHR.US', 'TMO.US', 'INTU.US', 'ADBE.US', 'LIN.US', 'SHW.US', 'ROP.US',
        'ITX.MC', 'CFR.SW', 'LSEG.LSE', 'TSM.US', '2330.TW', 'NFLX.US', 'META.US', 'AMZN.US', 'LLY.US', 'HLMA.LSE', 'DSY.PA', 'SIKA.SW', 'LONN.SW']
fails = {'cap <5 Mld$': ~(mc >= 5e9), 'storia <5 anni': ~full5, 'ricavi CAGR <8%': ~(F.rev_cagr5 >= 0.08), 'ricavi in calo >1 anno': ~(F.n_down5 <= 1),
         'debito alto': ~lowdebt, 'PEG >3': ~pegok, 'ROE e margine op. insufficienti': ~(q1 | q2), 'settore (banca/assic./immob.)': ~QU}
rows = []
for tk in NOMI:
    z = F[(F.t == tk) & (F.date >= '2016-01-01')]
    if not len(z): rows.append(dict(t=tk, nome='non nel pannello')); continue
    r = dict(t=tk, nome=z.name.iloc[0][:28], trimestri=len(z), in_Q3=Q3[z.index].mean(), in_Q3_ult8=Q3[z.index[-8:]].mean(),
             in_GARP_core=CORE[z.index].mean(), settore_escluso_GARP=bool(z.excl_sector.iloc[-1]))
    nz = z.index[~Q3[z.index]]
    if len(nz):
        c = {k: v[nz].mean() for k, v in fails.items()}
        r['motivo_principale'] = ', '.join(f'{k} {v:.0%}' for k, v in sorted(c.items(), key=lambda x: -x[1])[:2] if v > 0.2)
    rows.append(r)
T = pd.DataFrame(rows); T.to_csv(f'{BASE}/res/scr_04b_nomi.csv', index=False)
pd.set_option('display.width', 250); print(T.round(2).to_string())
