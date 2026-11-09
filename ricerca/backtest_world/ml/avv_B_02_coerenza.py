# Verifica avversariale prova B: coerenza fra rendimento a 3 mesi (usato nei portafogli) e a 12 mesi (usato per i crolli).
# Se la serie dei prezzi corretti e' pulita, (1+f3(d))(1+f3(d+1))(1+f3(d+2))(1+f3(d+3)) = 1+f12(d). Una differenza forte
# indica un salto finto (frazionamento non corretto per pochi giorni, serie incollate). Usa il pannello v2 (tutte le date).
import pandas as pd, numpy as np
ML = '${RICERCA_BASE}/backtest_world/ml'
B = pd.read_pickle(f'{ML}/storico5/provaB/matrice_B.pkl'); B = B[(B.anno >= 2006) & (B.anno <= 2011)]
P = pd.read_pickle(f'{ML}/storico5/pannello_prezzi_us_v2.pkl')[['t', 'date', 'f3', 'f12', 'f12_end']]
P = P[P.t.isin(set(B.t))].drop_duplicates(['t', 'date']).sort_values(['t', 'date'])
g = P.groupby('t').f3
P['chain'] = (1 + P.f3) * (1 + g.shift(-1)) * (1 + g.shift(-2)) * (1 + g.shift(-3))
P['ratio'] = P.chain / (1 + P.f12)
X = B[['t', 'date', 'name', 'f3', 'f12', 'crash50']].merge(P[['t', 'date', 'chain', 'ratio']], on=['t', 'date'], how='left')
ok = X.ratio.notna()
bad = ok & ((X.ratio > 1.5) | (X.ratio < 1 / 1.5))
print('righe B 2006-11:', len(X), '| con catena calcolabile:', int(ok.sum()), '| incoerenti (>1,5x):', int(bad.sum()), f'({bad[ok].mean():.2%})',
      '| titoli:', X[bad].t.nunique())
print('crolli fra le incoerenti:', int(X.crash50[bad].sum()), 'su', int(X.crash50.sum()), 'crolli totali')
# trimestri "colpevoli": f3 che compare in >=2 finestre incoerenti dello stesso titolo
T = X[bad].groupby(['t', 'name']).agg(n=('date', 'size'), prima=('date', 'min'), ultima=('date', 'max'), f3_max=('f3', 'max'), f3_min=('f3', 'min'))
print(T.sort_values('n', ascending=False).head(40).to_string())
X[bad].to_csv(f'{ML}/avv_B_out/righe_incoerenti_f3_f12.csv', index=False)
sorted_t = sorted(X[bad].t.unique()); open(f'{ML}/avv_B_out/titoli_incoerenti.txt', 'w').write('\n'.join(sorted_t))
