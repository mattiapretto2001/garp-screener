# scr_01 (07/11): campi in piu' alla data, per tutte le societa' del pannello panel2, senza sbirciare nel futuro
# (stesse date di disponibilita' prudenti di world_04: deposito USA o chiusura+45 gg, resto del mondo chiusura+75 gg):
#  - cassa (per Moonshot: autonomia di cassa, debito/cassa);
#  - margine operativo dell'ultimo trimestre, dello stesso trimestre un anno prima e di due trimestri prima (Svolta);
#  - storico degli ultimi 6 bilanci annuali: ricavi, utile, utile operativo, margine lordo, patrimonio, debito, cassa
#    (Qualita' durevole, P/E su utili medi per energia e materie prime);
#  - margine lordo 12 mesi per le 347 societa' fuori USA scaricate oggi (fund2) che nel pannello non l'avevano;
#  - rendimento da dividendo degli ultimi 12 mesi, ricavato dai prezzi (rapporto prezzo corretto / prezzo grezzo):
#    nessun credito EODHD in piu'.
import pickle, sys, warnings, pandas as pd, numpy as np
from world_common import *
from world_04_features import company, last_row, mi
from world_14_features2 import extra2
warnings.filterwarnings('ignore')
P2 = pd.read_pickle(f'{BASE}/res/panel2.pkl')[['t', 'date', 'ex', 'gm']]
FD = pickle.load(open(f'{BASE}/fund/fund.pkl', 'rb'))
F2 = pickle.load(open(f'{BASE}/fund/fund2.pkl', 'rb'))
FD.update({k: v for k, v in F2.items() if v and 'gen' in v}); del F2
NEED_GM = set(P2[P2.gm.isna()].t)


def divyield(px, dates):
    c = px.c.astype(float); a = px.a.astype(float)
    k = (a / a.shift(1)) / (c / c.shift(1))
    # allo stacco il prezzo corretto scende meno del grezzo: k > 1 (frazionamenti ed errori cadono fuori dall'intervallo)
    ev = k.where((k > 1.0005) & (k < 1.25))
    lg = np.log(ev).fillna(0.0)
    out = {}
    for t in dates:
        z = lg[(lg.index > t - pd.Timedelta(days=365)) & (lg.index <= t)]
        out[t] = np.exp(z.sum()) - 1 if len(z) > 150 else np.nan
    return out


def annual_hist(fd, us):
    R = company(fd, us)
    iy = R.get('iy'); b = R.get('b'); iq = R.get('iq')
    if iy is not None:
        for c in ['operatingIncome', 'grossProfit', 'costOfRevenue']:
            if c not in iy: iy[c] = np.nan
        iy['gp'] = iy.grossProfit.where(iy.grossProfit.notna(), iy.totalRevenue - iy.costOfRevenue)
    return R, iy, b, iq


def proc(args):
    ex, tick = args
    P = pickle.load(open(f'{BASE}/eod/{ex}.pkl', 'rb'))
    rows = []
    for t in tick:
        fd = FD.get(t); code = t.rsplit('.', 1)[0]
        if not fd or 'gen' not in fd: continue
        us = ex == 'US'
        dates = sorted(P2.date[P2.t == t])
        try:
            R, iy, b, iq = annual_hist(fd, us)
            if b is not None:
                b = b.copy(); b['cash_'] = b.cashAndShortTermInvestments.where(b.cashAndShortTermInvestments.notna(), b.cash)
                debt = b.shortLongTermDebtTotal.copy()
                alt = b.shortTermDebt.where(b.shortTermDebt.notna(), b.shortLongTermDebt).fillna(0) + b.longTermDebt.where(b.longTermDebt.notna(), b.longTermDebtTotal).fillna(0)
                b['debt_'] = debt.where(debt.notna(), alt)
                B = b.set_index('m')
            if iq is not None and 'operatingIncome' in iq:
                iq = iq.copy(); iq['om'] = (iq.operatingIncome / iq.totalRevenue).where(iq.totalRevenue > 0)
                Q = iq.set_index('m')
            dy = divyield(P[code], dates) if code in P and P[code] is not None else {}
            e2 = extra2(fd, us, dates) if t in NEED_GM else {}
        except Exception as e:
            print('errore', t, e, flush=True); continue
        for d in dates:
            r = {'t': t, 'date': d, 'divy': dy.get(d, np.nan)}
            if b is not None:
                bb = last_row(b, d)
                if bb is not None: r['cash'] = bb.cash_
            if iq is not None and 'om' in iq:
                x = last_row(iq, d)
                if x is not None and mi(d) - x.m <= 9:
                    m0, cv = int(x.m), int(x.cv)
                    r['om_q'] = x.om
                    r['om_q_1y'] = Q.om.get(m0 - 12, np.nan) if (m0 - 12) in Q.index else np.nan
                    r['om_q_2ago'] = Q.om.get(m0 - 2 * cv, np.nan) if (m0 - 2 * cv) in Q.index else np.nan
            if iy is not None:
                y = iy[iy.av <= d].sort_values('m')
                if len(y) and mi(d) - y.m.iloc[-1] <= 15:
                    m0 = int(y.m.iloc[-1]); Y = y.set_index('m')
                    for k in range(6):
                        mm = m0 - 12 * k
                        if mm not in Y.index: break
                        z = Y.loc[mm]
                        r[f'rev_y{k}'] = z.totalRevenue; r[f'ni_y{k}'] = z.ni; r[f'op_y{k}'] = z.operatingIncome; r[f'gp_y{k}'] = z.gp
                        if b is not None and mm in B.index:
                            r[f'eq_y{k}'] = B.totalStockholderEquity.get(mm); r[f'debt_y{k}'] = B.debt_.get(mm); r[f'cash_y{k}'] = B.cash_.get(mm)
            if t in NEED_GM:
                g = e2.get(d, {})
                r['gp_ttm_n'] = g.get('gp_ttm', np.nan); r['gp_ttm4_n'] = g.get('gp_ttm4', np.nan); r['rev_ttm4b_n'] = g.get('rev_ttm4b', np.nan)
            rows.append(r)
    print(ex, len(tick), len(rows), flush=True)
    return rows


if __name__ == '__main__':
    from multiprocessing import Pool
    T = P2.drop_duplicates('t')
    if len(sys.argv) > 2: T = T.groupby('ex').head(int(sys.argv[2]))
    jobs = []
    for ex, g in T.groupby('ex'):
        ts = list(g.t)
        for k in range(0, len(ts), 250): jobs.append((ex, ts[k:k + 250]))
    rows = []
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as Pp:
        for a in Pp.imap_unordered(proc, jobs): rows += a
    X = pd.DataFrame(rows)
    X.to_pickle(f'{BASE}/res/scr_extra{"_test" if len(sys.argv) > 2 else ""}.pkl')
    print(X.shape); print(X.notna().mean().round(2).to_string())
