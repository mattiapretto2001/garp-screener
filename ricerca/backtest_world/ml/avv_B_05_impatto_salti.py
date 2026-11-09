# Verifica avversariale prova B: impatto dei salti finti (classificati a mano da avv_B_04: frazionamenti/scorpori non corretti,
# serie incollate, ADR con rapporto cambiato; quasi tutti fra il 17 e il 21 dicembre). Le righe B con un salto finto dentro la
# finestra di 3 mesi escono dai portafogli trimestrali; quelle con un salto finto dentro i 12 mesi escono dai conteggi dei crolli.
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
ML = '${RICERCA_BASE}/backtest_world/ml'; BW = os.path.dirname(ML)
sys.path.insert(0, ML); sys.path.insert(0, BW)
import importlib.util
spec = importlib.util.spec_from_file_location('v1', f'{ML}/avv_B_01_verifica.py')
FAKE = [('SLP', '2006-08-14'), ('STAR', '2006-12-14'), ('LFC', '2006-12-18'), ('FLIR', '2006-12-18'), ('GSS', '2006-12-19'), ('CEQP', '2006-12-19'), ('LFC', '2006-12-29'), ('MBT', '2006-12-18'), ('PBCT', '2007-04-16'), ('ANDV', '2007-05-30'),
        ('JCI', '2007-07-02'), ('SLP', '2007-10-02'), ('GOL', '2007-12-19'), ('AINV', '2007-12-19'), ('NXGN', '2007-12-19'), ('IGOI', '2008-05-22'),
        ('SSP', '2008-07-01'), ('REV', '2008-09-15'), ('CY', '2008-09-30'), ('DS', '2008-11-20'), ('DS', '2008-11-21'), ('RRD', '2008-12-17'),
        ('NXGN', '2008-12-17'), ('MBT', '2008-12-18'), ('JRJC', '2008-12-18'), ('CGRN', '2008-12-18'), ('INT', '2009-12-08'), ('CBB', '2009-12-17'),
        ('MBT', '2009-12-17'), ('CORE', '2009-12-17'), ('EBIX', '2009-12-17'), ('STAR', '2009-12-18'), ('TRQ', '2009-12-18'), ('MBT', '2010-05-03'),
        ('GSS', '2010-12-17'), ('ISBC', '2010-12-17'), ('CLR', '2010-12-20'), ('LFC', '2010-12-20'), ('CGRN', '2010-12-20'), ('CBB', '2010-12-20'),
        ('RRD', '2010-12-20'), ('NXGN', '2011-10-27'), ('RRD', '2011-12-19'), ('LFC', '2011-12-19'), ('GSS', '2011-12-19'), ('EXPE', '2011-12-21')]
F = pd.read_pickle(f'{ML}/storico5/provaB/matrice_B.pkl')
F['bad3'] = False; F['bad12'] = False
for t, g in FAKE:
    g = pd.Timestamp(g); m = F.t == t
    F.loc[m & (F.date < g) & (g <= F.date + pd.offsets.MonthEnd(3)), 'bad3'] = True
    F.loc[m & (F.date < g) & (g <= F.date + pd.offsets.MonthEnd(12)), 'bad12'] = True
TEST = (F.anno >= 2006) & (F.anno <= 2011)
D = pd.to_datetime([g for _, g in FAKE]); print('salti finti:', len(FAKE), '| fra il 17 e il 21 dicembre:', int(((D.month == 12) & (D.day >= 17) & (D.day <= 21)).sum()))
print('righe test con f3 finto:', int((F.bad3 & TEST).sum()), '| con f12 finto:', int((F.bad12 & TEST).sum()),
      '| crolli finti:', int((F.bad12 & TEST & (F.crash50 == 1)).sum()), 'su', int(F.crash50[TEST].sum()),
      '| eccezionali finti:', int((F.bad12 & TEST & (F.top5_reg == 1)).sum()))
F[(F.bad3 | F.bad12) & TEST][['t', 'date', 'name', 'f3', 'f12', 'crash50', 'bad3', 'bad12']].to_csv(f'{ML}/avv_B_out/righe_con_salti_finti.csv', index=False)
pd.to_pickle(F[['t', 'date', 'bad3', 'bad12']], f'{ML}/avv_B_out/flag_salti_finti.pkl')
