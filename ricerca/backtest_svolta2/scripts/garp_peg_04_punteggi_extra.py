# GARP: 3 punteggi "migliorati" con variabili fuori dai filtri, DEFINITI PRIMA di vedere i risultati e provati solo con top 15 / top 30
# sui promossi della variante 3 (PEG<2 + tolleranza). Tutte le variabili sono point-in-time (bilanci depositati alla data, prezzi fino alla data).
#  P1 "revisioni e qualita'": PEG 30 | 6 voci dei filtri 5 ciascuna | sorpresa utili 10, accelerazione ricavi 10, trend margine lordo 10, conversione in cassa 10
#  P2 "momentum":             PEG 30 | 6 voci dei filtri 50/6 ciascuna | momentum 12-1 mesi 20
#  P3 "composito snello":     PEG 25, momentum 20, sorpresa utili 15, conversione in cassa 10, riacquisti 10, stabilita' margine 10, ROE 10
import os, glob, pickle
HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(f'{HERE}/garp_peg_01_backtest.py').read().split("ev('G0")[0])
# ---- momentum 12-1: prezzo rettificato 1 mese prima / 12 mesi prima
A = []
for fn_ in sorted(glob.glob(f'{BASE}/cache/prices/blk_*.pkl')):
    A.append(pickle.load(open(fn_, 'rb'))['Adj Close'])
adj = pd.concat(A, axis=1); adj.index = pd.to_datetime(adj.index).tz_localize(None); adj = adj.loc[:, ~adj.columns.duplicated()]
def px_at(t):
    i = adj.index.searchsorted(t, side='right') - 1; return adj.iloc[i]
MOM = {t: px_at(t - pd.DateOffset(months=1)) / px_at(t - pd.DateOffset(months=12)) - 1 for t in DATES}
F['mom'] = [MOM[t].get(k, np.nan) for t, k in zip(F.date, F.key)]
# ---- altre variabili
F['sue'] = (F.ni_ttm - F.ni_ttm1) / F.mcap            # variazione utile del trimestre vs anno prima, in rapporto alla capitalizzazione (proxy revisioni)
F['acc_rev'] = F.yoy0 - F.yoy1                        # accelerazione dei ricavi
F['d_gm'] = F.gm_ttm - F.gm_ttm4                      # trend margine lordo
F['cash_q'] = (F.fcf_ttm / F.ni_ttm).clip(-2, 3)      # conversione utile -> cassa (alto = pochi accantonamenti contabili)
F['buyback'] = -F.dil_yoy                             # azioni diluite in calo = riacquisti netti
F['opm_stab'] = -F[[f'opm_q{k}' for k in (0, 3, 6, 9, 12)]].std(axis=1)
print('copertura variabili fra i promossi V3:', F[V3][['mom', 'sue', 'acc_rev', 'd_gm', 'cash_q', 'buyback', 'opm_stab']].notna().mean().round(2).to_dict())
BASEV = {'peg': ('peg', False), 'rev_q': ('yoy0', True), 'eps_q': ('epsq', True), 'cagr': ('rev_cagr', True), 'fcfy': ('fcfy', True), 'de': ('de', False), 'roe': ('roe', True)}
EXTRA = {'mom': ('mom', True), 'sue': ('sue', True), 'acc_rev': ('acc_rev', True), 'd_gm': ('d_gm', True), 'cash_q': ('cash_q', True),
         'buyback': ('buyback', True), 'opm_stab': ('opm_stab', True)}
ALLV = dict(BASEV, **EXTRA)
f6 = ['rev_q', 'eps_q', 'cagr', 'fcfy', 'de', 'roe']
W = {'P1 revisioni e qualita\'': dict({'peg': 30, 'sue': 10, 'acc_rev': 10, 'd_gm': 10, 'cash_q': 10}, **{k: 5 for k in f6}),
     'P2 momentum': dict({'peg': 30, 'mom': 20}, **{k: 50 / 6 for k in f6}),
     'P3 composito snello': {'peg': 25, 'mom': 20, 'sue': 15, 'cash_q': 10, 'buyback': 10, 'opm_stab': 10, 'roe': 10},
     'R filtri (ROE, PEG 30)': dict({'peg': 30}, **{k: 70 / 6 for k in f6})}
for w in W.values(): assert abs(sum(w.values()) - 100) < 1e-6
def wscore(mask, w):
    out = pd.Series(np.nan, index=F.index)
    for t, x in F[mask].groupby('date'):
        out[x.index] = sum(wt * pct(x[ALLV[k][0]], ALLV[k][1]) for k, wt in w.items())
    return out
ev('V3 PEG<2 + tolleranza EPS', sel(V3), group='rif')
SCX = {nm: wscore(V3, w) for nm, w in W.items()}
for N in (15, 30):
    for nm in sorted(W, key=lambda k: not k.startswith('R')):
        ev(f'{nm} | top {N}', sel(V3, N, SCX[nm]), base=f'R filtri (ROE, PEG 30) | top {N}' if not nm.startswith('R') else 'V3 PEG<2 + tolleranza EPS', group=f'extra{N}')
# diagnostica (non usata per scegliere): ogni variabile nuova da sola, top 30
for k in EXTRA:
    ev(f'diag: top 30 solo {k}', sel(V3, 30, wscore(V3, {k: 100})), base='V3 PEG<2 + tolleranza EPS', group='diag')
# sorteggio
rng = np.random.default_rng(7); V3S = SEL['V3 PEG<2 + tolleranza EPS']; RND = {}
for N in (15, 30):
    out = {p: [] for p in PER}
    for it in range(1000):
        S = {t: (list(rng.choice(V3S[t], N, replace=False)) if len(V3S[t]) > N else V3S[t]) for t in DATES}
        r, n, c, tu = run(S); rn = r - c
        for p, (a, b) in PER.items():
            ds = [d for d in DATES if a <= d <= b]; out[p].append(cagr(rn[ds], ds))
    RND[N] = {p: np.array(v) for p, v in out.items()}
R = pd.DataFrame(RES); R['pct_caso'] = [np.mean(RND[int(v.split('top ')[1][:2])][p] < c) if (' | top ' in v and p in PER) else np.nan
                                        for v, p, c in zip(R.variante, R.periodo, R.CAGR)]
R.to_csv(f'{OUT}/garp_peg_extra.csv', index=False)
AN = pd.DataFrame({k: annual(v) for k, v in NET.items()}); AN.to_csv(f'{OUT}/garp_peg_extra_annuali.csv')
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print(R[['variante', 'periodo', 'n_medio', 'CAGR', 'vol', 'maxDD', 'anni_battuto_univ', 'turnover_annuo', 'd_vs_base', 't_vs_base', 'pct_caso']].round(3).to_string())
print((AN.loc[2019:2026] * 100).round(0).T.to_string())
for N in (15, 30):
    print(N, {p: np.percentile(v, [5, 50, 95]).round(3).tolist() for p, v in RND[N].items()})
