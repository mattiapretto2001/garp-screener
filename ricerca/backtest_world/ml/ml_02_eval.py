# ml_02: valutazione fuori campione (2016-2026) dei modelli di ml_01 contro i punteggi lineari sulle stesse variabili.
#  - IC (correlazione di rango per data con rk12_reg), AUC per data (top5_reg, bot20_reg, crash50); t di Newey-West 4 ritardi
#  - per periodo (2016, 2017-21, 2022-26) e per gruppo (USA grandi, USA p/m, Europa, Asia, Altri)
#  - differenze appaiate gbm - lineare (stesse date), gbm - gbm1 (valore delle interazioni), gbm1 - lineare (non linearita')
#  - portafogli trimestrali (decile, top 30, top 30 >=2 Mld$ settori GARP), costo 0,5%, euro, fino al 30/06/2026 (+ trimestre)
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3
TAG = sys.argv[1] if len(sys.argv) > 1 else ''
M = mc.load()
P = pd.read_pickle(f'{mc.OUT}/wf_pred{TAG}.pkl')
M = M.loc[P.index].copy()
for c in P.columns: M[c] = P[c]
VARS = mc.GLOBAL + (mc.EXT if TAG == '_us' else [])
# punteggio a priori a pesi uguali (nessuna stima): media dei ranghi con segno atteso, variabili con direzione nota
APR = [v for v in VARS if fv3.DIRECTION.get(v, 0) != 0]
M['apr'] = M[mc.xcols(APR)].mean(axis=1)
for k in ['rk', 't5']: M[f'apr_{k}'] = M['apr']
for k in ['b20', 'c50']: M[f'apr_{k}'] = -M['apr']
if TAG == '':
    E = pd.read_pickle(f'{mc.HERE}/reg_out/enet_pred.pkl').loc[M.index]
    M['enet_rk'] = E.enet_rk; M['enet_t5'] = E.enet_t5; M['enet_b20'] = E.enet_b20
M = M[M.gbm_rk.notna()]
MODELS = ['gbm', 'gbm1', 'lin', 'apr'] + (['enet'] if TAG == '' else [])
TG = ['rk', 't5', 'b20', 'c50'] if TAG == '' else ['rk', 't5', 'b20']
log = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s); log.append(s)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)

L = M[M.rk12_reg.notna()]
def series(k, mdl, D):
    col = f'{mdl}_{k}'
    if col not in D: return None
    y = D[mc.TGT[k]].values
    return mc.ic_by_date(D[col].values, y, D.date.values) if k == 'rk' else mc.auc_by_date(D[col].values, y, D.date.values)

rows = []; SER = {}
for k in TG:
    base = 0 if k == 'rk' else 0.5
    for mdl in MODELS:
        s = series(k, mdl, L)
        if s is None: continue
        SER[(k, mdl)] = s
        r = {'target': k, 'modello': mdl, 'media': s.mean(), 't': fv3.nw_t(s - base, 4), 'quota_buone': (s > base).mean(), 'n_date': len(s)}
        for p in mc.PERS:
            sp = s[[mc.perlab(d) == p for d in s.index]]; r[p] = sp.mean(); r['t_' + p] = fv3.nw_t(sp - base, 4)
        for g in mc.GROUPS:
            sg = series(k, mdl, L[L.reg_rob == g]); r[g] = sg.mean(); r['t_' + g] = fv3.nw_t(sg - base, 4)
        rows.append(r)
TAB = pd.DataFrame(rows); TAB.to_csv(f'{mc.OUT}/eval_metriche{TAG}.csv', index=False)
say(TAB.round(3).to_string())

# differenze appaiate
drows = []
for k in TG:
    for a, b in [('gbm', 'lin'), ('gbm', 'gbm1'), ('gbm1', 'lin'), ('gbm', 'apr'), ('lin', 'apr'), ('gbm', 'enet')]:
        if (k, a) not in SER or (k, b) not in SER: continue
        d = (SER[(k, a)] - SER[(k, b)]).dropna()
        r = {'target': k, 'confronto': f'{a}-{b}', 'diff': d.mean(), 't': fv3.nw_t(d, 4), 'quota_a_meglio': (d > 0).mean()}
        for p in mc.PERS:
            dp = d[[mc.perlab(x) == p for x in d.index]]; r[p] = dp.mean(); r['t_' + p] = fv3.nw_t(dp, 4)
        for g in mc.GROUPS:
            sa, sb = series(k, a, L[L.reg_rob == g]), series(k, b, L[L.reg_rob == g])
            dg = (sa - sb).dropna(); r[g] = dg.mean(); r['t_' + g] = fv3.nw_t(dg, 4)
        drows.append(r)
DT = pd.DataFrame(drows); DT.to_csv(f'{mc.OUT}/eval_differenze{TAG}.csv', index=False)
say(DT.round(3).to_string())

# IC sul rango dei punteggi stimati per le code (eccezionali; disastri e crolli con il segno girato = "sicurezza")
xr = []
for mdl in MODELS:
    for k, sg in [('rk', 1), ('t5', 1), ('b20', -1), ('c50', -1)]:
        c = f'{mdl}_{k}'
        if c not in L or k not in TG: continue
        s = mc.ic_by_date(sg * L[c].values, L.rk12_reg.values, L.date.values)
        r = {'modello': mdl, 'punteggio': k if sg > 0 else '-' + k, 'IC_rango': s.mean(), 't': fv3.nw_t(s, 4)}
        for p in mc.PERS:
            r[p] = s[[mc.perlab(d) == p for d in s.index]].mean()
        xr.append(r)
XR = pd.DataFrame(xr); XR.to_csv(f'{mc.OUT}/eval_ic_incrociati{TAG}.csv', index=False); say(XR.round(3).to_string())

# per anno (IC del rango) per vedere la stabilita'
yr = pd.DataFrame({m: SER[('rk', m)].groupby(SER[('rk', m)].index.year).mean() for m in MODELS if ('rk', m) in SER})
yr.to_csv(f'{mc.OUT}/eval_ic_anno{TAG}.csv'); say(yr.round(3).to_string())

# decili del modello di rango (esiti medi) - gbm e lin
dec = []
for mdl in ['gbm', 'lin', 'gbm1']:
    q = L.groupby('date')[f'{mdl}_rk'].transform(lambda s: pd.qcut(s.rank(method='first'), 10, labels=False))
    g = L.assign(dec=q).groupby('dec')
    dec.append(pd.DataFrame({'modello': mdl, 'rango_medio': g.rk12_reg.mean(), 'rend_medio': g.fwd12_eur.mean(), 'rend_mediano': g.fwd12_eur.median(),
                             'eccez': g.top5_reg.mean(), 'disastri': g.bot20_reg.mean(), 'crolli': g.crash50.mean()}))
DEC = pd.concat(dec); DEC.to_csv(f'{mc.OUT}/eval_decili{TAG}.csv'); say(DEC.round(3).to_string())

# ---------- portafogli (solo per il modello mondiale)
if TAG == '':
    Q = M[M.date <= mc.LAST_PORT_DATE].copy()
    dates = sorted(Q.date.unique())
    uni = Q.groupby('date').r_eur.mean()
    big = Q[(Q.mcap_usd >= 2e9) & ~Q.excl_sector]
    uni_big = big.groupby('date').r_eur.mean()
    def bench(D):
        return pd.DataFrame({'r': D.groupby('date').r_eur.mean(), 'turn': 0, 'n': D.groupby('date').size(), 'top5': D.groupby('date').top5_reg.mean(),
                             'bot20': D.groupby('date').bot20_reg.mean(), 'crash': D.groupby('date').crash50.mean()})
    PO = {'universo': (bench(Q), uni), 'universo >=2Mld settori GARP': (bench(big), uni_big),
          'core di oggi': (mc.port(Q, lambda g: g[g.core], dates), uni)}
    for c, nm in [('gbm_rk', 'GBM rango'), ('gbm1_rk', 'GBM additivo rango'), ('lin_rk', 'Ridge rango'), ('apr_rk', 'A priori pesi uguali'),
                  ('enet_rk', 'Elastic net (regressioni)'), ('gbm_t5', 'GBM eccezionali'), ('lin_t5', 'Logit eccezionali'),
                  ('gbm_b20', 'GBM disastri (sicuri)'), ('lin_b20', 'Logit disastri (sicuri)')]:
        sgn = -1 if c.endswith('b20') else 1
        Q['_s'] = sgn * Q[c]
        PO[f'{nm} | decile'] = (mc.port(Q, lambda g: g[g._s >= g._s.quantile(0.9)], dates), uni)
        PO[f'{nm} | top30'] = (mc.port(Q, lambda g: g.nlargest(30, '_s'), dates), uni)
        PO[f'{nm} | top30 >=2Mld GARP'] = (mc.port(Q, lambda g: g[(g.mcap_usd >= 2e9) & ~g.excl_sector].nlargest(30, '_s'), dates), uni_big)
    # due lati: media dei ranghi per data di eccezionali e sicurezza (come il "due lati" delle regressioni)
    for pre, nm in [('gbm', 'GBM'), ('lin', 'Logit')]:
        Q['_s'] = Q.groupby('date')[f'{pre}_t5'].rank(pct=True) + Q.groupby('date')[f'{pre}_b20'].rank(pct=True, ascending=False)
        PO[f'{nm} due lati | top30 >=2Mld GARP'] = (mc.port(Q, lambda g: g[(g.mcap_usd >= 2e9) & ~g.excl_sector].nlargest(30, '_s'), dates), uni_big)
        PO[f'{nm} due lati | decile'] = (mc.port(Q, lambda g: g[g._s >= g._s.quantile(0.9)], dates), uni)
    ST = pd.DataFrame({k: mc.pstats(v, b) for k, (v, b) in PO.items()}).T
    ST.to_csv(f'{mc.OUT}/eval_portafogli.csv')
    fmt = ST.copy()
    for c in ['CAGR', 'diff', '2016', '2017-21', '2022-26', 'perdita_max', 'top5', 'bot20', 'crash50', 'rotaz_annua']:
        fmt[c] = (fmt[c] * 100).round(1)
    fmt['t'] = fmt.t.round(2); fmt['titoli'] = fmt.titoli.round(0)
    say(fmt.to_string())
    # confronti appaiati fra portafogli GBM e lineari
    R = pd.concat({k: v.r for k, (v, b) in PO.items()}, axis=1); R.to_csv(f'{mc.OUT}/eval_port_trimestrali.csv')
    for a, b in [('GBM rango | decile', 'Ridge rango | decile'), ('GBM rango | top30', 'Ridge rango | top30'),
                 ('GBM rango | top30 >=2Mld GARP', 'Ridge rango | top30 >=2Mld GARP'),
                 ('GBM rango | top30 >=2Mld GARP', 'A priori pesi uguali | top30 >=2Mld GARP'),
                 ('GBM eccezionali | decile', 'Logit eccezionali | decile'), ('GBM disastri (sicuri) | decile', 'Logit disastri (sicuri) | decile'),
                 ('GBM due lati | top30 >=2Mld GARP', 'Logit due lati | top30 >=2Mld GARP'), ('GBM rango | top30 >=2Mld GARP', 'core di oggi')]:
        d = R[a] - R[b]; n = len(d)
        say(f'{a} vs {b}: diff CAGR {100*((1+R[a]).prod()**(4/n)-(1+R[b]).prod()**(4/n)):+.1f} punti, t {fv3.nw_t(d, 2):.2f}')
open(f'{mc.OUT}/ml_02{TAG}.log', 'w').write('\n'.join(log))
