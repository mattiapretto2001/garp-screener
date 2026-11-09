# Storico 2000-2011, punto 5.2: pannello trimestrale USA di soli prezzi (fine trimestre 12/1999 - 09/2025), societa' uscite comprese.
# Serie: i nostri prezzi dal 1998 (eod_lungo/US, 4.926 titoli dell'universo 2012-2026) + i prezzi scaricati oggi per i codici
# liquidi nelle istantanee 2000-2010 che non avevamo (storico5/raw/prezzi_us). Nessuna chiamata EODHD.
# Per ogni titolo e data: prezzo, scambi (mediana 63 giorni), prezzo/massimo 52 settimane, momentum 12-1 e 6-1, volatilita' 1 anno,
# rendimento a 12 mesi con la regola di uscita gia' usata (ultimo prezzo <25% del massimo dell'anno = -100%),
# azioni (se ci sono i bilanci: fund/fund2, piu' storico5/fond_C.pkl se scaricato) e variazione azioni 1 e 3 anni point-in-time.
import os, sys, glob, pickle, warnings, re, json, pandas as pd, numpy as np
from multiprocessing import Pool
warnings.filterwarnings('ignore')
from s5_common import OUT, ML, BW
sys.path.insert(0, BW); sys.path.insert(0, ML)
from world_common import symbols
from world_04_features import clean, company, sh_at, mi
from fv3_01_extra import share_change
TODAY = pd.Timestamp('2026-11-06')
REB = list(pd.date_range('1999-12-31', '2025-09-30', freq='QE'))
PX = f'{OUT}/raw/prezzi_us'
EXCLPAT = (r'\b(?:Bank|Banc|Bancorp|Bancshares|Financial|Acquisition|Trust|REIT|Realty|Properties|Insurance|Petroleum|Mining|Gold|'
           r'Fund|Capital Corp|Investment|Energy|Oil|Gas|Resources|Utilities|Power|Electric)\b')


def series_pool():
    L = pd.read_pickle(f'{ML}/eod_lungo/US.pkl.gz')
    L['t'] = L.t.astype(str)
    pool = {t: x.drop(columns='t').set_index('date') for t, x in L.groupby('t', sort=False)}
    src = {t: 'A' for t in pool}
    for fn in glob.glob(f'{PX}/*.pkl'):
        t = os.path.basename(fn)[:-7]      # "XYZ.US.pkl" -> "XYZ"
        d = pd.read_pickle(fn)
        if d is None or d.empty or t in pool: continue
        pool[t] = d.set_index('date'); src[t] = 'D'
    return pool, src


FD = None
def load_fd():
    global FD
    if FD is None:
        FD = {**pickle.load(open(f'{BW}/fund/fund.pkl', 'rb')), **pickle.load(open(f'{BW}/fund/fund2.pkl', 'rb'))}
        fc = f'{OUT}/fond_C.pkl'
        if os.path.exists(fc): FD.update(pickle.load(open(fc, 'rb')))
    return FD


def one(args):
    t, d = args
    d = d[~d.index.duplicated(keep='last')].sort_index()
    d = d[(d.c > 0) & d.a.notna()]
    if len(d) < 60: return []
    try:
        aa, spx = clean(d)
    except Exception:
        return []
    idx = d.index; av = aa.values; cv = d.c.values.astype(float); tv = (spx.values * d.v.values.astype(float))
    last = idx[-1]
    ended_series = last < TODAY - pd.Timedelta(days=30)
    fd = load_fd().get(f'{t}.US')
    R = company(fd, True) if isinstance(fd, dict) else None
    sh = R.get('sh') if R else None
    stm = None
    if R:
        mm = [x[['m', 'av']] for x in (R.get('iq'), R.get('iy')) if x is not None and len(x)]
        stm = pd.concat(mm).sort_values('av') if mm else None
    pidx = idx; after = (d.c.astype(float) / spx).values

    def split_at(m_old, m_new):
        d0 = pd.Timestamp(year=m_old // 12, month=m_old % 12 + 1, day=1) + pd.offsets.MonthEnd(0)
        d1 = pd.Timestamp(year=m_new // 12, month=m_new % 12 + 1, day=1) + pd.offsets.MonthEnd(0)
        if d0 < pidx[0]: return None
        i0 = max(pidx.searchsorted(d0, side='right') - 1, 0); i1 = max(pidx.searchsorted(d1, side='right') - 1, 0)
        return after[i0] / after[i1]
    rows = []
    for t0 in REB:
        i = idx.searchsorted(t0, side='right') - 1
        if i < 0 or (t0 - idx[i]).days > 10 or i < 40: continue
        r = {'t': t, 'date': t0, 'px': cv[i], 'spx': float(spx.values[i])}
        w = tv[max(0, i - 62):i + 1]; r['dv63'] = float(np.nanmedian(w)) if len(w) >= 40 else np.nan
        j0 = idx.searchsorted(t0 - pd.Timedelta(days=365), side='left')
        win = av[j0:i + 1]
        r['n1y'] = len(win)
        if len(win) >= 200:
            r['p52'] = av[i] / np.nanmax(win)
            lr = np.diff(np.log(np.clip(win, 1e-9, None)))
            r['vol'] = float(np.nanstd(lr) * np.sqrt(252))
            k1 = idx.searchsorted(t0 - pd.Timedelta(days=30), side='right') - 1
            r['mom12'] = av[k1] / av[j0] - 1
            k6 = idx.searchsorted(t0 - pd.Timedelta(days=182), side='left')
            r['mom6'] = av[k1] / av[k6] - 1
        # rendimento a 12 mesi (e a 3 mesi) con la regola di uscita
        for h, nm in ((12, 'f12'), (3, 'f3')):
            t1 = t0 + pd.offsets.MonthEnd(h)
            if t1 > TODAY: continue
            k = idx.searchsorted(t1, side='right') - 1
            ended = idx[k] < t1 - pd.Timedelta(days=10) and ended_series and last <= t1
            if ended:
                h0 = idx.searchsorted(last - pd.Timedelta(days=365), side='left')
                bk = av[-1] < 0.25 * np.nanmax(av[h0:]) or av[-1] <= 0
                rr = -1.0 if bk else av[-1] / av[i] - 1
            else:
                rr = av[k] / av[i] - 1
            r[nm] = float(np.clip(rr, -1, 10)); r[nm + '_end'] = bool(ended)
        if sh is not None and len(sh):
            s = sh_at(sh, mi(t0) - 2); r['sh'] = s
            if stm is not None:
                m_av = stm[stm.av <= t0]
                if len(m_av):
                    m0 = int(m_av.m.max())
                    r['dsh1'] = share_change(sh, m0, m0 - 12, split_at)
                    r['dsh3'] = share_change(sh, m0, m0 - 36, split_at)
        rows.append(r)
    return rows


if __name__ == '__main__':
    pool, src = series_pool()
    print('serie', len(pool), pd.Series(src).value_counts().to_dict(), flush=True)
    load_fd()
    with Pool(4) as P:
        out = []
        for k, rr in enumerate(P.imap_unordered(one, list(pool.items()), chunksize=20)):
            out += rr
            if k % 2000 == 0: print(k, flush=True)
    D = pd.DataFrame(out)
    s = symbols('US').set_index('Code')
    last = {t: x.index[-1] for t, x in pool.items() if len(x)}
    first = {t: x.index[0] for t, x in pool.items() if len(x)}
    D['src'] = D.t.map(src); D['last'] = D.t.map(last); D['first'] = D.t.map(first)
    D['name'] = D.t.map(s.Name); D['dl_list'] = D.t.map(s.delisted)
    D['excl'] = D.name.fillna('').str.contains(EXCLPAT, case=False, regex=True)
    D['uscita_pre2011'] = D['last'] < pd.Timestamp('2011-06-30')
    D['cap'] = D.sh * D.spx
    D.to_pickle(f'{OUT}/pannello_prezzi_us.pkl')
    print(D.shape, D.groupby(D.date.dt.year).size().to_dict())
