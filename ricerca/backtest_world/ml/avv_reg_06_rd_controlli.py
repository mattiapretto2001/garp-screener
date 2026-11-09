# avv_reg_06: quale controllo fa diventare positiva la R&S (USA)? margini o rischio (volatilita', taglia, storia)?
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
warnings.filterwarnings('ignore')
M = rc.load(); M = M[M.fwd12_eur.notna() & (M.reg == 'USA')].reset_index(drop=True)
M['y_rk'] = (M.rk12_reg - 0.5) * rc.S12; M['bot20'] = M.bot20_reg.astype(float) * 100
sets = {'R&S da sola': [], '+ volatilita': ['z_vol1y'], '+ vol, taglia, storia': ['z_vol1y', 'z_logmcap', 'z_hist_y'],
        '+ margini (fcf_m, opm_avg5, roe, ey, fcfy)': ['z_fcf_m', 'z_opm_avg5', 'z_roe', 'z_ey', 'z_fcfy'],
        '+ margini + vol': ['z_fcf_m', 'z_opm_avg5', 'z_roe', 'z_ey', 'z_fcfy', 'z_vol1y'],
        '+ valutazione (ev_sales, pb)': ['z_ev_sales', 'z_pb'], '+ ev_sales + vol': ['z_ev_sales', 'z_vol1y']}
for nm, x in sets.items():
    X = ['z_rd_int'] + x
    out = []
    for y in ['y_rk', 'bot20']:
        C = rc.fm(M[['date'] + X + [y]], X, y); out.append('%s t %.1f' % (y, fv3.nw_t(C['z_rd_int'])))
    print('%-45s %s' % (nm, ' | '.join(out)))
