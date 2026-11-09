# Metriche point-in-time per ogni data di ribilanciamento e rendimenti futuri -> cache/features.pkl
import pandas as pd, numpy as np, os, glob, pickle, json
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
TODAY = pd.Timestamp('2026-11-03')
Q = pd.read_pickle(f'{BASE}/cache/quarters.pkl')
COV = pd.read_pickle(f'{BASE}/cache/cover_shares.pkl')
uni = pd.read_csv(f'{BASE}/cache/universe.csv')
sic = json.load(open(f'{BASE}/cache/sic.json'))
uni['sic'] = uni.cik.map(lambda c: pd.to_numeric((sic.get(str(c)) or [None])[0], errors='coerce'))
# ---- prezzi
C, A, SP = [], [], []
for fn in sorted(glob.glob(f'{BASE}/cache/prices/blk_*.pkl')):
    d = pickle.load(open(fn, 'rb'))
    C.append(d['Close']); A.append(d['Adj Close']); SP.append(d.get('Stock Splits'))
close = pd.concat(C, axis=1); adj = pd.concat(A, axis=1); spl = pd.concat([s for s in SP if s is not None], axis=1)
for x in (close, adj, spl): x.index = pd.to_datetime(x.index).tz_localize(None)
close = close.loc[:, ~close.columns.duplicated()]; adj = adj.loc[:, ~adj.columns.duplicated()]; spl = spl.loc[:, ~spl.columns.duplicated()]
spl = spl.fillna(0).replace(0, 1.0)
# fattore split: prodotto degli split successivi alla data (per riportare azioni dichiarate alla base di oggi)
fac = spl[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
hi52 = close.rolling(252, min_periods=200).max(); lo52 = close.rolling(252, min_periods=200).min()
ma200 = close.rolling(200, min_periods=180).mean()
# ---- date di ribilanciamento: fine trimestre 03/2012 .. 09/2026
REB = list(pd.date_range('2012-03-31', '2026-09-30', freq='QE'))
def px_at(df, t):
    i = df.index.searchsorted(t, side='right') - 1
    return df.iloc[i]
def fwd(t, months):
    t2 = min(t + pd.DateOffset(months=months), TODAY)
    p0 = px_at(adj, t)
    win = adj.loc[(adj.index > t) & (adj.index <= t2)]
    p1 = win.ffill().iloc[-1] if len(win) else p0  # ultimo prezzo disponibile (se il titolo smette di quotare)
    r = (p1 / p0 - 1).clip(-1, 10)
    return r, win.max() / p0
Qi = Q.set_index(['cik', 'm']).sort_index()
conc = ['rev', 'gp', 'cogs', 'opinc', 'ni', 'cfo', 'capex', 'da', 'acq', 'eps', 'dilsh', 'cash', 'sti', 'ltd_nc', 'ltd', 'std', 'stb', 'eq']
COV['filed'] = pd.to_datetime(COV.filed)
COV = COV.sort_values('filed')
tick_of = dict(zip(uni.cik, uni.ticker))
rows = []
RQ = {}
for t in REB:
    RQ[t] = fwd(t, 3)[0]
    A_ = Q[Q.rev_f <= t]
    m0 = A_.groupby('cik').m.max()
    m0 = m0[m0 >= (t - pd.Timedelta(days=200)).year * 12 + (t - pd.Timedelta(days=200)).month]
    ciks = m0.index.values
    L = {}
    for k in range(0, 25, 3):
        idx = pd.MultiIndex.from_arrays([ciks, m0.values - k])
        v = Qi.reindex(idx)
        out = {}
        for c in conc:
            if c in v:
                x = v[c].values.astype(float)
                f = v[c + '_f'].values
                x[~(pd.to_datetime(f) <= t)] = np.nan
                out[c] = x
        L[k] = pd.DataFrame(out, index=ciks)
    def ttm(c, k0):
        s = sum(L[k0 + j][c] for j in (0, 3, 6, 9)) if k0 + 9 <= 24 else np.nan
        return s
    f = pd.DataFrame(index=ciks); f['date'] = t; f['m0'] = m0.values
    for k in (0, 3, 6, 9, 12):  # GP: dichiarato oppure ricavi - costo del venduto
        L[k]['gp2'] = L[k]['gp'].fillna(L[k]['rev'] - L[k]['cogs']) if 'cogs' in L[k] else L[k]['gp']
    for k in (15, 18, 21, 24):
        L[k]['gp2'] = L[k]['gp'].fillna(L[k]['rev'] - L[k].get('cogs', np.nan))
    for c in ['rev', 'gp2', 'opinc', 'ni', 'cfo', 'capex', 'da', 'acq', 'eps']:
        f[c + '_ttm'] = ttm(c, 0); f[c + '_ttm1'] = ttm(c, 3); f[c + '_ttm4'] = ttm(c, 12)
    f['rev_ttm2'] = ttm('rev', 6)
    for k in (0, 3, 6, 9, 12):
        f[f'rev_q{k}'] = L[k]['rev']; f[f'opm_q{k}'] = L[k]['opinc'] / L[k]['rev']; f[f'gm_q{k}'] = L[k]['gp2'] / L[k]['rev']
        f[f'opinc_q{k}'] = L[k]['opinc']; f[f'eps_q{k}'] = L[k]['eps']
    for j, k in enumerate((0, 3, 6, 9)):
        f[f'yoy{j}'] = L[k]['rev'] / L[k + 12]['rev'] - 1
    f['opm_ttm'] = f.opinc_ttm / f.rev_ttm; f['opm_ttm1'] = f.opinc_ttm1 / f.rev_ttm1; f['opm_ttm4'] = f.opinc_ttm4 / f.rev_ttm4
    f['opm_ttm2'] = ttm('opinc', 6) / f.rev_ttm2
    f['gm_ttm'] = f.gp2_ttm / f.rev_ttm; f['gm_ttm4'] = f.gp2_ttm4 / f.rev_ttm4
    f['fcf_ttm'] = f.cfo_ttm - f.capex_ttm.fillna(0)
    f['ebitda_ttm'] = f.opinc_ttm + f.da_ttm.fillna(0)
    f['cash'] = L[0]['cash'].values; f['sti'] = L[0]['sti'].values
    f['liq'] = f.cash.fillna(0) + f.sti.fillna(0)
    ltd = L[0]['ltd_nc'].fillna(L[0]['ltd']); f['debt'] = ltd.fillna(0) + L[0]['std'].fillna(0) + L[0]['stb'].fillna(0)
    f['eq'] = L[0]['eq']
    f['dil_yoy'] = L[0]['dilsh'] / L[12]['dilsh'] - 1
    # crescita ricavi pluriennale (5 anni se possibile, altrimenti 4/3) per GARP
    f['rev_cagr'] = np.nan
    # ---- prezzo e capitalizzazione
    tk = pd.Series([tick_of.get(c) for c in ciks], index=ciks)
    ok = tk.isin(close.columns)
    f = f[ok.values]; tk = tk[ok]
    c_t = px_at(close, t)[tk.values].values
    f['ticker'] = tk.values; f['price'] = c_t
    f['hi52'] = px_at(hi52, t)[tk.values].values; f['lo52'] = px_at(lo52, t)[tk.values].values
    f['ma200'] = px_at(ma200, t)[tk.values].values
    # azioni: max(copertina dei, diluite medie), riportate alla base split di oggi con il fattore alla data di deposito
    cv = COV[COV.filed <= t].groupby('cik').tail(1).set_index('cik')
    sh_cov = cv.val.reindex(f.index); fil_cov = cv.filed.reindex(f.index)
    sh_dil = L[0]['dilsh'].reindex(f.index)
    fil_dil = Qi.reindex(pd.MultiIndex.from_arrays([f.index.values, f.m0.values]))['dilsh_f'].values
    def adjsh(sh, fil):
        out = np.full(len(f), np.nan)
        for i, (s, d, tt) in enumerate(zip(sh.values, pd.to_datetime(fil), f.ticker.values)):
            if pd.notna(s) and pd.notna(d) and tt in fac.columns:
                out[i] = s * px_at(fac[[tt]], d).iloc[0]
        return out
    a1 = adjsh(sh_cov, fil_cov); a2 = adjsh(sh_dil, pd.Series(fil_dil, index=f.index))
    ratio = np.fmax(a1, a2) / np.fmin(a1, a2)
    f['sh'] = np.where(ratio > 3, np.fmin(a1, a2), np.fmax(a1, a2))  # valori incoerenti: si tiene il piu' piccolo
    for H in (3, 6, 12, 24):
        r, mx = fwd(t, H)
        f[f'r{H}'] = r[tk.values].values
        if H in (12, 24): f[f'max{H}'] = mx[tk.values].values
    rs, _ = fwd(t, 3)
    f['spy3'] = rs.get('SPY', np.nan)
    for H in (6, 12, 24): f[f'spy{H}'] = fwd(t, H)[0].get('SPY', np.nan)
    f['cik'] = f.index
    rows.append(f.reset_index(drop=True))
    print(t.date(), len(f), flush=True)
F = pd.concat(rows, ignore_index=True)
F['sic'] = F.cik.map(dict(zip(uni.cik, uni.sic)))
F = F.rename(columns={'eq': 'equity'})
# azioni: errori di scala nei dati XBRL -> se lontane >4x dalla mediana della societa', si usa la mediana
med = F.groupby('cik').sh.transform('median')
bad = (F.sh > 4 * med) | (F.sh < med / 4)
F.loc[bad, 'sh'] = med[bad]
F['mcap'] = F.price * F.sh
F = F.replace([np.inf, -np.inf], np.nan)
# CAGR ricavi pluriennale: dai TTM di 5 (o 4/3) anni prima, ricostruiti dalla tabella trimestrale
Qt = Q[['cik', 'm', 'rev', 'rev_f']].dropna().sort_values(['cik', 'm'])
Qt['ttm'] = Qt.groupby('cik').rev.transform(lambda s: s.rolling(4).sum())
Qt.loc[Qt.groupby('cik').m.diff(3).ne(9).values, 'ttm'] = np.nan
TT = Qt.set_index(['cik', 'm']).ttm
for yrs in (5, 4, 3):
    v = TT.reindex(pd.MultiIndex.from_arrays([F.cik.values, F.m0.values - 12 * yrs])).values
    g = (F.rev_ttm / v) ** (1 / yrs) - 1
    F['rev_cagr'] = F.rev_cagr.fillna(pd.Series(np.where(v > 0, g, np.nan)))
F.to_pickle(f'{BASE}/cache/features.pkl')
pd.DataFrame(RQ).T.to_pickle(f'{BASE}/cache/rq.pkl')  # rendimento trimestrale di ogni ticker a ogni data
print(F.shape)
