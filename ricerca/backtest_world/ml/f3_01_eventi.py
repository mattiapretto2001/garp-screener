# f3_01 (09/11): tabella degli ANNUNCI DI UTILI (eventi) per le societa' dell'universo features_v3.
# Per ogni annuncio: sorpresa (A-E), SUE (sorpresa / dev. std delle 8 sorprese precedenti, min 4), sorpresa % EODHD,
# serie di battute consecutive, reazione del prezzo nei 3 giorni dell'annuncio (EAR, al netto della media della borsa)
# e deriva successiva (abnormal buy-and-hold) a 63/126/252 sedute, partendo dalla chiusura del 4o giorno (d0+3).
# Definizioni FISSATE PRIMA di guardare i risultati. Nessuna chiamata EODHD: fund/fund2.pkl (earn) + eod/<EX>.pkl.
import os, sys, zlib, pickle, warnings, numpy as np, pandas as pd
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__)); BT = os.path.dirname(HERE); sys.path.insert(0, BT)
from world_common import BASE
from world_04_features import clean
warnings.filterwarnings('ignore')
OUT = f'{HERE}/f3_out'; os.makedirs(OUT, exist_ok=True)
H = {'d3m': 63, 'd6m': 126, 'd12m': 252}


def proc(args):
    ex, tickers, EARN = args
    P = pickle.load(open(f'{BASE}/eod/{ex}.pkl', 'rb'))
    ser = {}
    for t in tickers:
        px = P.get(t.rsplit('.', 1)[0])
        if px is None: continue
        px = px[(px.a > 0) & (px.c > 0)]
        if len(px) < 100: continue
        aa, _ = clean(px)
        ser[t] = aa.pct_change()
    del P
    R = pd.DataFrame(ser).sort_index()
    R = R[R.index >= '2010-01-01']
    mkt = R.clip(-0.5, 1.0).mean(axis=1).where(R.notna().sum(axis=1) >= 20, 0.0).fillna(0.0)
    D = R.index; M = np.log1p(mkt.values).cumsum()
    # placebo: |rendimento anomalo 3 giorni| medio su finestre qualsiasi, per verificare che le date degli annunci siano giuste
    rows, plac = [], []
    for t in R.columns:
        r = R[t]; lv = r.last_valid_index(); fv = r.first_valid_index()
        rf = r.copy(); rf[D > lv] = mkt[D > lv]; rf = rf.fillna(0.0).clip(-0.9, 5.0)
        L = np.log1p(rf.values).cumsum()
        valid = r.notna().values
        i_first, i_last = D.get_loc(fv), D.get_loc(lv)

        def abn(i0, i1):
            if i0 < 0 or i1 >= len(D): return np.nan
            return np.exp(L[i1] - L[i0]) - np.exp(M[i1] - M[i0])

        def raw(i0, i1):
            if i0 < 0 or i1 >= len(D): return np.nan
            return np.exp(L[i1] - L[i0]) - 1
        # placebo: 12 finestre a caso per titolo
        rng = np.random.default_rng(zlib.crc32(t.encode()))
        if i_last - i_first > 300:
            for i in rng.integers(i_first + 1, i_last - 3, 12): plac.append((ex, abs(abn(i - 1, i + 2))))
        E = EARN.get(t)
        if E is None or not len(E): continue
        E = E[E.epsActual.notna() & E.reportDate.notna()].sort_values('reportDate').drop_duplicates('reportDate', keep='last')
        E = E[E.reportDate >= '2009-01-01'].reset_index(drop=True)
        s = (E.epsActual - E.epsEstimate).astype(float)
        sd = s.shift(1).rolling(8, min_periods=4).std()
        beat = (E.epsActual > E.epsEstimate).where(E.epsEstimate.notna())
        streak, k = [], 0
        for b in beat:
            if pd.isna(b): k = 0; streak.append(np.nan)
            else: k = k + 1 if b else 0; streak.append(k)
        for i, e in E.iterrows():
            rd = e.reportDate
            if rd < pd.Timestamp('2011-06-01') or rd > D[-1]: continue
            j = D.searchsorted(rd, 'left')
            if j >= len(D): continue
            if e.bam == 'AfterMarket' and D[j] == rd: j += 1
            if j - 1 < i_first or j + 2 > i_last: continue
            if valid[j - 1:j + 3].sum() < 3: continue
            st = j + 3
            r0 = dict(t=t, ex=ex, per=e.date, rd=rd, bam=e.bam, d0=D[j] if j < len(D) else pd.NaT,
                      sig_day=D[min(j + 2, len(D) - 1)], A=e.epsActual, Est=e.epsEstimate, spct=e.surprisePercent,
                      surp=s.iloc[i], sue=s.iloc[i] / sd.iloc[i] if sd.iloc[i] > 0 else np.nan,
                      streak=streak[i], ear=abn(j - 1, j + 2), ear_raw=raw(j - 1, j + 2), pre=abn(j - 22, j - 1))
            for h, n in H.items():
                r0[h] = abn(st, st + n); r0[h + '_raw'] = raw(st, st + n)
            rows.append(r0)
    print(ex, len(rows), flush=True)
    return pd.DataFrame(rows), pd.DataFrame(plac, columns=['ex', 'absab'])


if __name__ == '__main__':
    F = pd.read_pickle(f'{HERE}/features_v3.pkl')[['t', 'ex']].drop_duplicates('t')
    FD = pd.read_pickle(f'{BASE}/fund/fund2.pkl')
    EARN = {t: v['earn'] for t, v in FD.items() if v and v.get('earn') is not None and len(v['earn'])}
    del FD
    jobs = [(ex, g.t.tolist(), {t: EARN[t] for t in g.t if t in EARN}) for ex, g in F.groupby('ex')]
    jobs.sort(key=lambda j: -len(j[1]))
    with Pool(4) as p: res = p.map(proc, jobs)
    EV = pd.concat([r[0] for r in res], ignore_index=True)
    PL = pd.concat([r[1] for r in res], ignore_index=True)
    EV.to_pickle(f'{OUT}/eventi.pkl'); PL.to_pickle(f'{OUT}/placebo.pkl')
    print(EV.shape); print(EV.groupby('ex').size())
