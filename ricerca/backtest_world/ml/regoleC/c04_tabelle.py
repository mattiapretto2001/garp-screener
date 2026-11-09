# Prova C (08/11/2026), fase 4: tabelle dai 300 portafogli per variante. Nessuna chiamata EODHD.
import os, sys, pickle, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60); pd.set_option('display.max_rows', 400)
T = pd.read_pickle(f'{HERE}/dati/runs.pkl')
POS = {k: v.view(np.recarray) for k, v in pickle.load(open(f"{HERE}/dati/posizioni.pkl", "rb")).items()}
SUBN = {'P1': ['2000-05', '2006-11'], 'P1p': ['2000-05', '2006-11'], 'P2': ['2012-17', '2018-26'], 'P2us': ['2012-17', '2018-26'],
        'P3': ['2012-17', '2018-25']}
REF = ('L', 'none')
OUT = open(f'{HERE}/dati/tabelle.txt', 'w')


def say(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')


def summary(key, tax=False):
    X = T[(T.key == key) & (T.tax == tax)]
    ref = X[(X.base == REF[0]) & (X.over == REF[1])].set_index('seed')
    rows = []
    for (b, o), g in X.groupby(['base', 'over'], sort=False):
        g = g.set_index('seed')
        P = POS.get((key, b, o, False)) if not tax else None
        r = dict(base=b, over=o, s_med=g.cagr_s.median(), s_p10=g.cagr_s.quantile(0.1), s_p90=g.cagr_s.quantile(0.9),
                 s_dd=g.dd_s.median(), cr_med=g.cagr_cr.median(), cr_dd=g.dd_cr.median(), c_med=g.cagr_c.median(), c_dd=g.dd_c.median(),
                 w=g.cagr_w.iloc[0], w_dd=g.dd_w.iloc[0], s_gt_w=(g.cagr_s > g.cagr_w).mean(), cr_gt_w=(g.cagr_cr > g.cagr_w).mean(),
                 cr_gt_ref=(g.cagr_cr > ref.cagr_cr.reindex(g.index)).mean(), d_cr=(g.cagr_cr - ref.cagr_cr.reindex(g.index)).median(),
                 top10=g.top10.median(), top10_pos=g.top10_pos.median(), pl_neg=(~g.tot_pl_pos.astype(bool)).mean(),
                 trades=g.trades_y.median(), cash=g.cash.median(), npos=g.npos.median())
        for s in SUBN[key]:
            r[f's|{s}'] = g[f'cagr_s|{s}'].median(); r[f'cr|{s}'] = g[f'cagr_cr|{s}'].median(); r[f'w|{s}'] = g[f'cagr_w|{s}'].iloc[0]
        if tax:
            r.update(s_tax=g.cagr_s_tax.median(), c_tax=g.cagr_c_tax.median(), w_tax=g.cagr_w_tax.iloc[0])
        if P is not None:
            m = P.mult
            r.update(zero=(m <= 0.10).mean(), fall=(P.why == 'fallimento').mean(), half=(m <= 0.5).mean(), x2=(m >= 2).mean(),
                     x3=(m >= 3).mean(), x5=(m >= 5).mean(), x10=(m >= 10).mean(), pk3=(P.peak >= 3).mean(), pk5=(P.peak >= 5).mean(),
                     pk10=(P.peak >= 10).mean(), hold=float(np.median(P.hold)), mult_med=float(np.median(m)), winrate=(m > 1).mean())
        rows.append(r)
    return pd.DataFrame(rows)


ALL = {}
for key in ['P1', 'P2', 'P3', 'P1p', 'P2us']:
    ALL[key] = summary(key)
    say(f'\n================ {key}')
    say(ALL[key].round(3).to_string())
TX = {}
for key in ['P1', 'P2']:
    TX[key] = summary(key, True)
    say(f'\n================ {key} con tasse')
    say(TX[key][['base', 'over', 's_med', 's_tax', 'c_med', 'c_tax', 'w', 'w_tax', 'cr_gt_ref', 'trades']].round(3).to_string())
pickle.dump(dict(ALL=ALL, TX=TX), open(f'{HERE}/dati/sintesi.pkl', 'wb'))

# ------------------------------------------------------------------ criterio fissato prima
say('\n================ criterio (fissato prima)')
A, B = ALL['P1'].set_index(['base', 'over']), ALL['P2'].set_index(['base', 'over'])
R = []
for k in A.index:
    c1 = A.loc[k, 'cr_med'] > A.loc[REF, 'cr_med'] and B.loc[k, 'cr_med'] > B.loc[REF, 'cr_med']
    subs = [A.loc[k, f's|{s}'] > A.loc[REF, f's|{s}'] for s in SUBN['P1']] + [B.loc[k, f's|{s}'] > B.loc[REF, f's|{s}'] for s in SUBN['P2']]
    c2 = sum(subs) >= 3
    c3 = (A.loc[k, 'cr_dd'] >= A.loc[REF, 'cr_dd'] - 0.05) and (B.loc[k, 'cr_dd'] >= B.loc[REF, 'cr_dd'] - 0.05)
    adv = ((A.loc[k, 'cr_med'] - A.loc[REF, 'cr_med']) + (B.loc[k, 'cr_med'] - B.loc[REF, 'cr_med'])) / 2
    R.append(dict(base=k[0], over=k[1], c1=c1, sub_wins=sum(subs), c2=c2, c3=c3, regge=c1 and c2 and c3, vantaggio_medio=adv,
                  d1=A.loc[k, 'cr_med'] - A.loc[REF, 'cr_med'], d2=B.loc[k, 'cr_med'] - B.loc[REF, 'cr_med'],
                  dd1=A.loc[k, 'cr_dd'] - A.loc[REF, 'cr_dd'], dd2=B.loc[k, 'cr_dd'] - B.loc[REF, 'cr_dd'],
                  p1=A.loc[k, 'cr_gt_ref'], p2=B.loc[k, 'cr_gt_ref']))
CR = pd.DataFrame(R).sort_values('vantaggio_medio', ascending=False)
say(CR.round(4).to_string())
CR.to_csv(f'{HERE}/dati/criterio.csv', index=False)

# ------------------------------------------------------------------ i titoli migliori (controllo dei dati)
aux = pickle.load(open(f'{os.path.dirname(HERE)}/regoleC/dati/aux.pkl', 'rb'))
for key in ['P1', 'P2']:
    D = pickle.load(open(f'{HERE}/dati/{key}.pkl', 'rb'))
    tick, cal = D['tick'], D['cal']
    P = POS[(key, 'T3', 'none', False)]
    df = pd.DataFrame({'t': [tick[j] for j in P.j], 'd0': cal[P.d0], 'mult': P.mult, 'peak': P.peak, 'why': P.why})
    g = df.groupby('t').agg(n=('mult', 'size'), mult_max=('mult', 'max'), mult_med=('mult', 'median'), peak_max=('peak', 'max'),
                            prima=('d0', 'min')).sort_values('mult_max', ascending=False)
    g['nome'] = [aux['names'].get(t, aux['names'].get(t.split('.')[0], '')) for t in g.index]
    say(f'\n{key} T3/none: i 25 titoli con il multiplo piu alto'); say(g.head(25).round(2).to_string())

# ------------------------------------------------------------------ anno per anno, riferimento e regole principali
for key in ['P1', 'P2']:
    X = T[(T.key == key) & ~T.tax]
    say(f'\n{key}: anno per anno, mediana della meta moltiplicatori')
    rows = {}
    for (b, o), g in X.groupby(['base', 'over'], sort=False):
        if o not in ('none', 'S30', 'S50', 'TR2'): continue
        A_ = pd.DataFrame(list(g.ann)); rows[f'{b}/{o}'] = A_.median()
    W = pd.Series(X.iloc[0].ann)  # placeholder
    say(pd.DataFrame(rows).round(3).to_string())
OUT.close()
