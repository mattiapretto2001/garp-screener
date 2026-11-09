# Storico 2000-2011, punto 5.2a: controllo del SEGNO in Europa (solo prezzi, SOLO societa' sopravvissute: EODHD non ha
# le uscite prima del 2013-2018). Stesse regole del pannello USA; liquidita' >=3 M$ al giorno (mediana 63 giorni) con cambi
# approssimati costanti (quelli della pre-selezione world_02), prezzo >=1 $; rendimenti in valuta locale. Nessuna chiamata EODHD.
import sys, pandas as pd, numpy as np
from multiprocessing import Pool
from s5_common import OUT, ML, BW
sys.path.insert(0, BW)
from world_04_features import clean
TODAY = pd.Timestamp('2026-11-06')
REB = list(pd.date_range('1999-12-31', '2024-09-30', freq='QE'))
FXA = {'EUR': 1.12, 'SEK': 0.1, 'DKK': 0.15, 'NOK': 0.1, 'CHF': 1.05, 'GBX': 0.013}
EXC = {'XETRA': 'EUR', 'PA': 'EUR', 'AS': 'EUR', 'MC': 'EUR', 'BR': 'EUR', 'HE': 'EUR', 'SW': 'CHF', 'ST': 'SEK', 'CO': 'DKK',
       'OL': 'NOK', 'LSE': 'GBX'}


def one(args):
    t, ex, d = args
    d = d[~d.index.duplicated(keep='last')].sort_index(); d = d[(d.c > 0) & d.a.notna()]
    if len(d) < 260: return []
    try: aa, spx = clean(d)
    except Exception: return []
    fx = FXA[EXC[ex]]
    idx = d.index; av = aa.values; cv = d.c.values.astype(float) * fx; tv = spx.values * d.v.values.astype(float) * fx
    last = idx[-1]; ended_series = last < TODAY - pd.Timedelta(days=30)
    rows = []
    for t0 in REB:
        i = idx.searchsorted(t0, side='right') - 1
        if i < 0 or (t0 - idx[i]).days > 10 or i < 40: continue
        j0 = idx.searchsorted(t0 - pd.Timedelta(days=365), side='left'); win = av[j0:i + 1]
        if len(win) < 200: continue
        w = tv[max(0, i - 62):i + 1]
        r = {'t': f'{t}.{ex}', 'ex': ex, 'date': t0, 'px_usd': cv[i], 'dv63': float(np.nanmedian(w)), 'p52': av[i] / np.nanmax(win)}
        lr = np.diff(np.log(np.clip(win, 1e-9, None))); r['vol'] = float(np.nanstd(lr) * np.sqrt(252))
        k1 = idx.searchsorted(t0 - pd.Timedelta(days=30), side='right') - 1; r['mom12'] = av[k1] / av[j0] - 1
        t1 = t0 + pd.offsets.MonthEnd(12)
        k = idx.searchsorted(t1, side='right') - 1
        ended = idx[k] < t1 - pd.Timedelta(days=10) and ended_series and last <= t1
        if ended:
            h0 = idx.searchsorted(last - pd.Timedelta(days=365), side='left')
            rr = -1.0 if (av[-1] < 0.25 * np.nanmax(av[h0:]) or av[-1] <= 0) else av[-1] / av[i] - 1
        else: rr = av[k] / av[i] - 1
        r['f12'] = float(np.clip(rr, -1, 10)); r['last'] = last
        rows.append(r)
    return rows


if __name__ == '__main__':
    jobs = []
    for ex in EXC:
        L = pd.read_pickle(f'{ML}/eod_lungo/{ex}.pkl.gz'); L['t'] = L.t.astype(str)
        jobs += [(t, ex, x.drop(columns='t').set_index('date')) for t, x in L.groupby('t', sort=False)]
    with Pool(4) as P:
        out = []
        for rr in P.imap_unordered(one, jobs, chunksize=20): out += rr
    E = pd.DataFrame(out)
    E = E[(E.px_usd >= 1) & (E.dv63 >= 3e6)].copy()
    E = E.sort_values('date').drop_duplicates(['date', 'p52', 'f12', 'vol'])
    E['anno'] = (E.date + pd.Timedelta(days=1)).dt.year
    E['blocco'] = pd.cut(E.anno, [1999, 2003, 2007, 2011, 2025], labels=['2000-03', '2004-07', '2008-11', '2012-25'])
    E['pct'] = E.groupby('date').f12.rank(pct=True)
    E['L50'] = E.f12 <= -0.5; E['L20'] = E.pct <= 0.2; E['W5'] = E.pct >= 0.95
    E['p52b'] = pd.cut(E.p52, [0, 0.4, 0.6, 0.75, 0.9, 1.01], labels=['<40%', '40-60%', '60-75%', '75-90%', '>=90%'], right=False)
    E.to_pickle(f'{OUT}/universo_prezzi_europa.pkl')
    f = open(f'{OUT}/risultati_europa.txt', 'w')
    def say(*a):
        s = ' '.join(str(x) for x in a); print(s); f.write(s + '\n')
    say('Europa, solo sopravvissute: titoli per data', E.groupby('blocco', observed=True).apply(lambda x: round(len(x) / x.date.nunique())).to_dict())
    for blk, X in list(E.groupby('blocco', observed=True)) + [('bolla 03/2000-09/2002', E[(E.date >= '2000-03-31') & (E.date <= '2002-09-30')]),
                                                             ('crisi 09/2007-12/2008', E[(E.date >= '2007-09-30') & (E.date <= '2008-12-31')]),
                                                             ('rimbalzo 12/2008-06/2009', E[(E.date >= '2008-12-31') & (E.date <= '2009-06-30')])]:
        t = X.groupby('p52b', observed=True).agg(quota=('t', 'size'), crolli=('L50', 'mean'), disastri=('L20', 'mean'),
                                                eccezionali=('W5', 'mean'), f12_media=('f12', 'mean'))
        t['quota'] = t.quota / t.quota.sum()
        say(f'\n-- {blk}: crolli medi {X.L50.mean():.3f}; sotto 40% = {t.loc["<40%", "crolli"] / X.L50.mean():.2f} volte la media')
        say(t.round(3).to_string())
    for col in ['p52', 'vol', 'mom12']:
        s = E.groupby('date').apply(lambda z: z[col].rank().corr(z.f12.rank()))
        yr = (s.index + pd.Timedelta(days=1)).year
        say(f'IC {col}: 2000-11 {s[yr <= 2011].mean():+.3f} | 2000-03 {s[(yr <= 2003)].mean():+.3f} | 2004-07 {s[(yr >= 2004) & (yr <= 2007)].mean():+.3f} '
            f'| 2008-11 {s[(yr >= 2008) & (yr <= 2011)].mean():+.3f} | 2012-25 {s[yr >= 2012].mean():+.3f}')
    for blk, X in E.groupby('blocco', observed=True):
        X = X.copy(); X['dec'] = X.groupby('date').vol.transform(lambda z: pd.qcut(z.rank(method='first'), 10, labels=False) + 1)
        t = X.groupby('dec').agg(crolli=('L50', 'mean'), f12=('f12', 'mean'))
        say(f'volatilita {blk}: crolli decile 1 {t.crolli.iloc[0]:.3f}, decile 10 {t.crolli.iloc[-1]:.3f}; f12 decile 1 {t.f12.iloc[0]:+.3f}, decile 10 {t.f12.iloc[-1]:+.3f}')
    f.close()
