# Posizioni del sostituto 2000-11 (P1) che attraversano un salto al ribasso sospetto (volume basso, volume zero dopo, o frazionamento vicino)
import pickle, numpy as np, pandas as pd
ML = '${RICERCA_BASE}/backtest_world/ml'
E = pd.read_pickle(f'{ML}/avv_C_out/crolli_P1.pkl'); S = E[E.sospetto]
POS = pickle.load(open(f'{ML}/regoleC/dati/posizioni.pkl', 'rb'))
ev = {}
for _, e in S.iterrows(): ev.setdefault(int(e.j), []).append(int(e.k))
for rule in [('L', 'none'), ('L', 'S30'), ('T2', 'none'), ('T3', 'none'), ('T3', 'S30')]:
    P = POS[('P1',) + rule + (False,)].view(np.recarray)
    hold_days = None
    # giorno di uscita non salvato: lo ricavo da d0 + tenuta (anni) in giorni di borsa ~ 261/anno
    d1 = P.d0 + np.round(P.hold * 261).astype(int)
    hit = np.array([any(P.d0[i] < k <= d1[i] + 3 for k in ev.get(int(P.j[i]), [])) for i in range(len(P))])
    z = P.mult <= 0.10
    print(rule, 'posizioni', len(P), '| toccate da un salto sospetto', hit.sum(), f'({hit.mean():.2%})', '| fra quelle "a zero":',
          int((hit & z).sum()), 'su', int(z.sum()), f'({(hit & z).sum() / max(z.sum(), 1):.0%})',
          '| perdita delle toccate sul totale delle perdite', f'{P.pl[hit & (P.pl < 0)].sum() / P.pl[P.pl < 0].sum():.1%}',
          '| p&l netto toccate / p&l netto totale', f'{P.pl[hit].sum():.0f} / {P.pl.sum():.0f}')
