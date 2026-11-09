# Prova A (08/11/2026), controllo dei dati: prezzo e scambi "veri" (come scambiati allora) per le serie in cui EODHD e'
# incoerente. Il pannello calcola gli scambi come prezzo corretto per frazionamenti x volume: e' giusto solo se il volume di
# EODHD e' corretto per i frazionamenti (come per AAPL). Per molte societa' uscite non lo e':
#   - chiusura grezza e volume grezzo (es. MATN, raggruppamenti 1:20 e 1:12 nel 2011-12): scambi gonfiati 240 volte;
#   - chiusura gia' corretta e volume grezzo (es. SYNI, raggruppamento 1:50 nel 2007): prezzo e scambi gonfiati 50 volte.
# Frazionamenti: lista EODHD (sA_01, titoli dell'universo) e salti della sola chiusura visibili nei dati (regola di clean).
#   f = azioni nuove / vecchie (2:1 -> 2; raggruppamento 1:50 -> 0,02); conta solo |log f| >= log 1,4.
#   chiusura: grezza se in +-2 giorni c'e' un salto vicino a 1/f, altrimenti gia' corretta (solo per la lista EODHD).
# Due versioni dei valori corretti, per ogni riga del pannello 12/1999-09/2011 delle serie con almeno un frazionamento:
#   PRUDENTE (px_p, dv63_p): il minimo fra le due letture possibili del volume (tutto corretto = pannello; tutto grezzo =
#     chiusura x volume, con il fattore f per i frazionamenti a chiusura gia' corretta); prezzo diviso per i raggruppamenti a
#     chiusura gia' corretta. Non sopravvaluta mai: entra solo chi supera le soglie con qualunque lettura.
#   STIMA (px_v, dv63_v): lettura frazionamento per frazionamento dal salto del volume (mediana 23 giorni dopo/prima, x = salto
#     / log f: grezzo se x > 0,75, corretto se < 0,25; per |f| >= 3 soglia 0,5; incerto = come il pannello). Rumorosa.
# Nessuna chiamata EODHD. Scrive storico5/volumi_corretti_A.pkl e storico5/volumi_eventi_A.csv (un rigo per frazionamento).
import os, sys, json, warnings, numpy as np, pandas as pd
from multiprocessing import Pool
warnings.filterwarnings('ignore')
from s5_common import OUT, ML, BW
sys.path.insert(0, BW); sys.path.insert(0, ML)
import s5_09_pannello_v2 as P9
REB = [d for d in pd.date_range('1999-12-31', '2025-09-30', freq='QE') if d <= pd.Timestamp('2011-09-30')]
SPL = f'{OUT}/splits_A'
LOG14 = np.log(1.4)


def api_splits(t):
    fn = f'{SPL}/{t}.json'
    if not os.path.exists(fn): return []
    out = []
    for s in json.load(open(fn)):
        try:
            x, y = s['split'].split('/'); f = float(x) / float(y)
            if f > 0: out.append((pd.Timestamp(s['date']), f))
        except Exception:
            pass
    return out


def vol_jump(v, i):
    b = v[max(0, i - 25):max(0, i - 2)]; a = v[i + 2:i + 25]
    b = b[b > 0]; a = a[a > 0]
    if len(b) < 8 or len(a) < 8: return np.nan
    return float(np.log(np.median(a) / np.median(b)))


def vol_state(jv, f):
    lf = np.log(f)
    if np.isnan(jv): return 'amb'
    x = jv / lf                                  # 0 = volume corretto, 1 = volume grezzo
    if abs(lf) >= np.log(3): return 'raw' if x > 0.5 else 'adj'
    if x > 0.75: return 'raw'
    if x < 0.25: return 'adj'
    return 'amb'


def one(args):
    t, d = args
    d = d[~d.index.duplicated(keep='last')].sort_index()
    d = d[(d.c > 0) & d.a.notna()]
    if len(d) < 60: return [], []
    idx = d.index; c = d.c.values.astype(float); a = d.a.values.astype(float); v = np.nan_to_num(d.v.values.astype(float))
    lc = np.r_[0, np.diff(np.log(c))]; la = np.r_[0, np.diff(np.log(np.clip(a, 1e-9, None)))]
    ev = []                                   # (indice, f, chiusura_gia_corretta, origine)
    used = set()
    for ds, f in api_splits(t):
        if abs(np.log(f)) < LOG14 or ds <= idx[0] or ds > idx[-1]: continue
        i = idx.searchsorted(ds)
        if i < 5 or i > len(idx) - 5: continue
        lf = np.log(f)
        ks = [k for k in range(i - 2, i + 3) if abs(lc[k] + lf) < 0.35 * abs(lf)]
        k = ks[0] if ks else i
        ev.append((k, f, not ks, 'api')); used.update(range(k - 5, k + 6))
    for k in np.where((np.abs(lc) > 0.25) & (np.abs(la) < 0.15))[0]:       # salti della sola chiusura (regola di clean)
        if k in used or k < 5 or k > len(idx) - 5: continue
        if k + 1 < len(lc) and abs(lc[k + 1]) > 0.4 and abs(lc[k] + lc[k + 1]) < 0.2: continue      # picco di un giorno
        f = float(np.exp(-lc[k]))
        if abs(np.log(f)) < LOG14: continue
        ev.append((k, f, False, 'dati')); used.update(range(k - 5, k + 6))
    evrows = []
    for k, f, cc, o in ev:
        jv = vol_jump(v, k)
        evrows.append({'t': t, 'date': idx[k], 'f': f, 'chiusura_corretta': cc, 'jv': jv, 'volume': vol_state(jv, f), 'origine': o})
    if not ev: return [], evrows
    n = len(idx)
    raw_f = np.ones(n)      # lettura "volume grezzo": chiusura x volume, x f per i frazionamenti a chiusura gia' corretta
    adj_f = np.ones(n)      # lettura "volume corretto" (= pannello): / f per i frazionamenti a chiusura grezza
    est_f = np.ones(n)      # stima frazionamento per frazionamento
    pxp_f = np.ones(n); pxv_f = np.ones(n)
    for (k, f, cc, o), e in zip(ev, evrows):
        if cc:
            raw_f[:k] *= f
            pxp_f[:k] *= min(1.0, f)
            if e['volume'] == 'raw': est_f[:k] *= f; pxv_f[:k] *= f
        else:
            adj_f[:k] /= f
            if e['volume'] != 'raw': est_f[:k] /= f
    cv = c * v
    rows = []
    for t0 in REB:
        i = idx.searchsorted(t0, side='right') - 1
        if i < 0 or (t0 - idx[i]).days > 10 or i < 40: continue
        j = max(0, i - 62)
        if i + 1 - j < 40: continue
        w = slice(j, i + 1)
        rows.append({'t': t, 'date': t0, 'dv_adj': float(np.nanmedian(cv[w] * adj_f[w])), 'dv_raw': float(np.nanmedian(cv[w] * raw_f[w])),
                     'dv63_v': float(np.nanmedian(cv[w] * est_f[w])), 'px_p': c[i] * pxp_f[i], 'px_v': c[i] * pxv_f[i]})
    return rows, evrows


if __name__ == '__main__':
    pool, src = P9.series_pool()
    print('serie', len(pool), flush=True)
    R, E = [], []
    with Pool(4) as P:
        for k, (rr, ee) in enumerate(P.imap_unordered(one, list(pool.items()), chunksize=40)):
            R += rr; E += ee
    R = pd.DataFrame(R); E = pd.DataFrame(E)
    R['dv63_p'] = R[['dv_adj', 'dv_raw']].min(axis=1)
    R.to_pickle(f'{OUT}/volumi_corretti_A.pkl'); E.to_csv(f'{OUT}/volumi_eventi_A.csv', index=False)
    print('righe con almeno un frazionamento dopo', len(R), '| serie', R.t.nunique())
    print(E.groupby(['origine', 'chiusura_corretta', 'volume']).size().to_string())
