# scr_05: (a) core e qualita' con e senza esclusioni di settore; (b) screener per i settori esclusi con metriche adatte;
# (c) i "temi" come industrie: si possono provare senza il senno di poi?
import pandas as pd, numpy as np
from scr_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
ROWS = []
CORE_ALL = mask(F, dict(BASE_P, settore=False, revq=0.20)) & (F.hi52 >= 0.8).fillna(False) & (mc >= 2e9) & PEGG
A_ALL = mask(F, dict(BASE_P, settore=False))
# (a) stesse regole, con e senza esclusioni; confronto con lo stesso universo largo (tutti i settori) per entrambe
for nm, m in [('GARP lista CON esclusioni', A), ('GARP lista SENZA esclusioni', A_ALL), ('Core CON esclusioni', CORE), ('Core SENZA esclusioni', CORE_ALL),
              ('Solo i titoli aggiunti togliendo le esclusioni (core)', CORE_ALL & ~UNI),
              ('Q3 con esclusioni GARP', Q3_G), ('Q3 universo qualita\' (senza banche/assic./immob.)', Q3), ('Q3 tutti i settori', Q3_ALL),
              ('Solo i titoli aggiunti (Q3 tutti vs GARP)', Q3_ALL & ~UNI)]:
    o, _ = ev(nm, m, ALL, '(a) vs universo tutti i settori'); ROWS += o
for reg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia']:
    for nm, m in [('Core CON esclusioni', CORE), ('Core SENZA esclusioni', CORE_ALL)]:
        o, _ = ev(nm, m, REG[reg], '(a) ' + reg); ROWS += o
print('quota del core senza esclusioni che viene dai settori esclusi:', round((CORE_ALL & ~UNI).sum() / CORE_ALL.sum(), 2),
      F[CORE_ALL & ~UNI].sector.value_counts(normalize=True).round(2).to_dict())
# (b) settori esclusi
for g, m in [('Utilities', S_UT), ('Energia', S_EM & (GRP == 'Energia')), ('Materie prime', S_EM & (GRP == 'Materie prime')),
             ('Finanza', S_FI), ('Immobiliare', S_RE)]:
    for reg in ['Mondo', 'USA grandi', 'Europa']:
        o, _ = ev('Screener ' + g, m, (GRP == g) & REG[reg], '(b) ' + reg + ' - ' + g); ROWS += o
o, _ = ev('Screener settori esclusi (tutti insieme)', S_ALL, GRP != '', '(b) Mondo - tutti i settori esclusi'); ROWS += o
# GARP classico applicato ai settori esclusi, come termine di paragone
o, _ = ev('GARP lista (stessi filtri del GARP) nei settori esclusi', A_ALL & (GRP != ''), GRP != '', '(b) Mondo - tutti i settori esclusi'); ROWS += o
T = pd.DataFrame(ROWS); T.to_csv(f'{BASE}/res/scr_05_settori.csv', index=False)
print(fmt(T).to_string())
print(T[T.periodo == '2012-26'][['gruppo', 'variante', 'n', 'maxdd', 'W5', 'L20']].round(3).to_string())
C = []
for g, m in [('Utilities', S_UT), ('Energia+Materie', S_EM), ('Finanza', S_FI), ('Immobiliare', S_RE), ('Tutti', S_ALL)]:
    pool = (GRP != '') if g == 'Tutti' else GRP.isin(['Energia', 'Materie prime']) if g == 'Energia+Materie' else (GRP == g)
    C.append(dict(gruppo=g, **caso(m, pool, n_it=300))); print(C[-1], flush=True)
pd.DataFrame(C).to_csv(f'{BASE}/res/scr_05_caso.csv', index=False)
print('titoli per gruppo, ultima data:', {g: int(((GRP == g) & (F.date == REB[-1])).sum()) for g in GRP.unique() if g})
print('promossi ultima data:'); print(F[S_ALL & (F.date == REB[-1])][['t', 'name', 'sector', 'mcap_usd', 'divy', 'pe', 'roe', 'de']].round(3).to_string())
# (c) temi come industrie (classificazione di oggi)
TEMI = {'Uranio': ['Uranium'], 'Produttori indipendenti e rinnovabili': ['Utilities - Independent Power Producers', 'Utilities - Renewable'],
        'Apparecchi elettrici (rete)': ['Electrical Equipment & Parts'], 'Rame': ['Copper'], 'Solare': ['Solar'],
        'Semiconduttori': ['Semiconductors'], 'Apparati di comunicazione (fotonica)': ['Communication Equipment']}
R2 = []
for tm, inds in TEMI.items():
    m = F.industry.str.strip().isin(inds).fillna(False)
    o, _ = ev('Tema: ' + tm + ' (tutta l\'industria)', m, ALL, '(c) temi'); R2 += o
    print(tm, 'titoli medi', round(F[m].groupby('date').size().mean(), 1))
T2 = pd.DataFrame(R2); T2.to_csv(f'{BASE}/res/scr_05_temi.csv', index=False)
print(fmt(T2).to_string())
