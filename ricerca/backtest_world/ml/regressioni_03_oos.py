# regressioni_03: valutazione fuori campione dei punteggi walk-forward (2015-2026).
# - correlazione di rango punteggio vs rk12_reg per data (t NW 4 ritardi), per periodo e per gruppo regionale
# - portafogli trimestrali a pesi uguali, rendimento in euro del trimestre dopo (r_eur), costo 0,5% per acquisto o vendita
#   decile migliore (mondo), top 30 (mondo), top 30 >=2 Mld$, top 30 >=2 Mld$ nei settori GARP; confronto con universo e core
# - esiti a 12 mesi dei titoli scelti: quota top 5% e peggiori 20% della regione, crolli >=50%
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
OUT = rc.HERE + '/reg_out'
M = rc.load().reset_index(drop=True)
PR = pd.read_pickle(f'{OUT}/enet_pred.pkl')
MODELS = ['enet_rk', 'lasso_rk', 'ols37_rk', 'fmcomp', 'enet_t5', 'enet_b20']
for k in MODELS: M[k] = PR[k].values
M['enet_b20'] = -M['enet_b20']           # punteggio "lontano dal disastro": alto = meglio
M = M[M.enet_rk.notna() & (M.date <= '2026-06-30')].copy()   # 30/09/2026: trimestre dopo non ancora chiuso
M['top5_reg'] = M.top5_reg.astype(float); M['bot20_reg'] = M.bot20_reg.astype(float); M['crash50'] = M.crash50.astype(float)
dates = sorted(M.date.unique())
def perlab(d):
    y = pd.Timestamp(d).year
    return '2015-16' if y <= 2016 else ('2017-21' if y <= 2021 else '2022-26')
log = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s); log.append(s)

# ---------- correlazione di rango fuori campione
ic_rows = []
for k in MODELS:
    ser = {}
    for d, g in M[M.rk12_reg.notna()].groupby('date'):
        ser[d] = g[k].rank().corr(g.rk12_reg.rank())
    s = pd.Series(ser)
    row = {'modello': k, 'IC': s.mean(), 't': fv3.nw_t(s, 4), 'quota_pos': (s > 0).mean()}
    for p in ['2015-16', '2017-21', '2022-26']:
        sp = s[[perlab(d) == p for d in s.index]]; row[p] = sp.mean(); row['t_' + p] = fv3.nw_t(sp, 4)
    for rg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia', 'Altri']:
        sr = {}
        for d, g in M[(M.reg_rob == rg) & M.rk12_reg.notna()].groupby('date'):
            sr[d] = g[k].rank().corr(g.rk12_reg.rank())
        sr = pd.Series(sr); row['IC_' + rg] = sr.mean(); row['t_' + rg] = fv3.nw_t(sr, 4)
    ic_rows.append(row)
IC = pd.DataFrame(ic_rows).set_index('modello'); IC.to_csv(f'{OUT}/oos_ic.csv')
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
say(IC.round(3).to_string())

# ---------- portafogli
def port(sel_fn, name):
    prev = pd.Series(dtype=float); rows = []
    for d in dates:
        g = M[M.date == d]
        s = sel_fn(g)
        if len(s) == 0:
            rows.append((d, 0.0, 0.0, 0, np.nan, np.nan, np.nan)); prev = pd.Series(dtype=float); continue
        w = pd.Series(1 / len(s), index=s.t.values)
        dw = w.subtract(prev, fill_value=0).abs().sum()
        r = s.r_eur.mean() - 0.005 * dw
        rows.append((d, r, dw, len(s), s.top5_reg.mean(), s.bot20_reg.mean(), s.crash50.mean()))
        prev = w * (1 + s.set_index('t').r_eur.reindex(w.index).fillna(0)); prev = prev / prev.sum()
    return pd.DataFrame(rows, columns=['date', 'r', 'turn', 'n', 'top5', 'bot20', 'crash']).set_index('date').assign(name=name)

def stats(df, bench):
    r = df.r; b = bench.reindex(r.index)
    out = {'titoli': df.n.mean(), 'CAGR': (1 + r).prod() ** (4 / len(r)) - 1}
    out['diff'] = out['CAGR'] - ((1 + b).prod() ** (4 / len(b)) - 1)
    out['t'] = fv3.nw_t(r - b, 2)
    for p in ['2015-16', '2017-21', '2022-26']:
        m = np.array([perlab(d) == p for d in r.index])
        out[p] = (1 + r[m]).prod() ** (4 / m.sum()) - 1 - ((1 + b[m]).prod() ** (4 / m.sum()) - 1)
    cum = (1 + r).cumprod(); out['perdita_max'] = (cum / cum.cummax() - 1).min()
    out['rotaz_annua'] = df.turn.mean() * 4 / 2
    out['top5'] = df.top5.mean(); out['bot20'] = df.bot20.mean(); out['crash50'] = df.crash.mean()
    out['anni_vinti'] = np.mean([(1 + r[r.index.year == y]).prod() > (1 + b[b.index.year == y]).prod() for y in sorted(set(r.index.year))])
    return out

uni = M.groupby('date').r_eur.mean()
uni_garp = M[~M.excl_sector].groupby('date').r_eur.mean()
P = {}
P['universo'] = pd.DataFrame({'r': uni, 'turn': 0, 'n': M.groupby('date').size(), 'top5': M.groupby('date').top5_reg.mean(),
                              'bot20': M.groupby('date').bot20_reg.mean(), 'crash': M.groupby('date').crash50.mean()})
P['universo GARP (settori)'] = pd.DataFrame({'r': uni_garp, 'turn': 0, 'n': M[~M.excl_sector].groupby('date').size(),
                              'top5': M[~M.excl_sector].groupby('date').top5_reg.mean(), 'bot20': M[~M.excl_sector].groupby('date').bot20_reg.mean(),
                              'crash': M[~M.excl_sector].groupby('date').crash50.mean()})
P['core di oggi'] = port(lambda g: g[g.core], 'core')
P['GARP di oggi (lista)'] = port(lambda g: g[g.GARP], 'garp')
for k in MODELS:
    P[f'{k} | decile'] = port(lambda g, k=k: g[g[k] >= g[k].quantile(0.9)], k)
    P[f'{k} | top30'] = port(lambda g, k=k: g.nlargest(30, k), k)
    P[f'{k} | top30 >=2Mld'] = port(lambda g, k=k: g[g.mcap_usd >= 2e9].nlargest(30, k), k)
    P[f'{k} | top30 >=2Mld settori GARP'] = port(lambda g, k=k: g[(g.mcap_usd >= 2e9) & ~g.excl_sector].nlargest(30, k), k)
ST = pd.DataFrame({k: stats(v, uni) for k, v in P.items()}).T
ST.to_csv(f'{OUT}/oos_portafogli.csv')
fmt = ST.copy()
for c in ['CAGR', 'diff', '2015-16', '2017-21', '2022-26', 'perdita_max', 'top5', 'bot20', 'crash50', 'rotaz_annua', 'anni_vinti']:
    fmt[c] = (fmt[c] * 100).round(1)
fmt['t'] = fmt.t.round(2); fmt['titoli'] = fmt.titoli.round(0)
say(fmt.to_string())
# confronto diretto con il core (stessi trimestri)
core_r = P['core di oggi'].r
for k in ['enet_rk | top30 >=2Mld settori GARP', 'fmcomp | top30 >=2Mld settori GARP', 'enet_rk | top30 >=2Mld', 'enet_rk | decile']:
    d = P[k].r - core_r
    say('vs core', k, 'diff CAGR %.1f punti, t %.2f' % (100 * (((1 + P[k].r).prod() ** (4 / len(d))) - ((1 + core_r).prod() ** (4 / len(d)))), fv3.nw_t(d, 2)))
pd.concat({k: v.r for k, v in P.items()}, axis=1).to_csv(f'{OUT}/oos_rendimenti_trimestrali.csv')
open(f'{OUT}/regressioni_03.log', 'w').write('\n'.join(log))
