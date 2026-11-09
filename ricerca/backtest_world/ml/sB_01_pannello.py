# Prova B (08/11/2026): punteggi congelati sugli USA 2006-2011, solo societa' con bilanci EODHD (in pratica sopravvissute).
# Passo 1: pannello point-in-time dei bilanci alle date di fine trimestre 12/2004 - 09/2011, per i titoli dell'universo di soli
# prezzi della prova A (storico5/universo_prezzi_us_v2.pkl, copiato in provaB/ per avere una fotografia fissa).
# Stesse funzioni del 2012-2026, senza modifiche: world_04_features.features (bilanci, data prudente USA = deposito o
# chiusura + 45 giorni, tetto 180 giorni), tune_01_panel.extra (utile operativo, prezzo/massimo, volatilita', media 200 gg,
# momentum), fv3_01_extra.extra3 (cassa, attivo, storia, diluizione, stime battute, ecc.).
# Bilanci: fund/fund.pkl, poi fund/fund2.pkl, poi storico5/fond_C.pkl (stesso ordine di s5_03). Prezzi: le stesse serie della
# prova A (eod_lungo/US, storico5/raw/prezzi_us, eod_lungo/US_uscite). Nessuna chiamata EODHD.
import os, sys, pickle, json, glob, gc, shutil, warnings, numpy as np, pandas as pd
from multiprocessing import Pool
warnings.filterwarnings('ignore')
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML)
sys.path.insert(0, BW); sys.path.insert(0, ML)
from world_04_features import features, COVERED_OTHER
from tune_01_panel import extra
from fv3_01_extra import extra3
OUT = f'{ML}/storico5/provaB'; os.makedirs(OUT, exist_ok=True)
DATES = list(pd.date_range('2004-12-31', '2011-09-30', freq='QE'))
FDX, PXX = {}, {}


def one(t):
    fd, px = FDX.get(t), PXX.get(t)
    if fd is None or px is None: return [], None
    px = px[~px.index.duplicated(keep='last')].sort_index()
    px = px[(px.c > 0) & (px.a > 0)]
    if len(px) < 100: return [], None
    g = fd.get('gen') or {}
    meta = dict(t=t, name_f=g.get('Name'), sector=g.get('Sector') or g.get('GicSector'), industry=g.get('Industry') or g.get('GicIndustry'),
                country=g.get('CountryISO'), ext_fields='earn' in fd, cur_px=g.get('CurrencyCode') or 'USD')
    dates = NEED[t]
    try:
        fr = features(dates, fd, px, True, 'USD')
        need = [r['date'] for r in fr]
        e1 = extra(fd, px, True, need); e3 = extra3(fd, px, True, need)
    except Exception as e:
        return [], dict(meta, err=repr(e))
    for r in fr:
        r.update(e1.get(r['date'], {})); r.update(e3.get(r['date'], {})); r['t'] = t
    return fr, meta


if __name__ == '__main__':
    src_u = f'{ML}/storico5/universo_prezzi_us_v2.pkl'
    snap = f'{OUT}/universo_A_copia.pkl'
    if not os.path.exists(snap): shutil.copy2(src_u, snap)
    U = pd.read_pickle(snap)
    H = U[U.date.isin(DATES)]
    NEED = H.groupby('t').date.apply(lambda s: sorted(s)).to_dict()
    print('universo A alle date 12/2004-09/2011: righe', len(H), 'titoli', len(NEED), flush=True)
    # bilanci (stesso ordine di s5_03.load_fd)
    for fn in (f'{BW}/fund/fund.pkl', f'{BW}/fund/fund2.pkl', f'{ML}/storico5/fond_C.pkl'):
        D = pickle.load(open(fn, 'rb'))
        for t in NEED:
            v = D.get(f'{t}.US')
            if isinstance(v, dict) and v.get('gen') is not None and v.get('inc_y') is not None: FDX[t] = v
        del D; gc.collect()
    print('con scheda di bilancio', len(FDX), flush=True)
    # Azioni: la serie storica 'sh' di EODHD per molte societa' parte solo dal 2009, mentre lo stato patrimoniale ha le azioni
    # (commonStockSharesOutstanding) da prima. Dove coincidono sono uguali entro il 2% nel 98% dei casi (controllo 2009-2011).
    # world_04.company usa lo stato patrimoniale solo se la serie manca del tutto: qui la serie viene COMPLETATA con lo stato
    # patrimoniale nei mesi che non copre (la serie resta prioritaria). Serve alla capitalizzazione vera e alla diluizione.
    n_aug = 0
    for t, v in list(FDX.items()):
        parts = []
        for k in ('bal_y', 'bal_q'):
            b = v.get(k)
            if b is not None and len(b) and 'commonStockSharesOutstanding' in b:
                x = b[['date', 'commonStockSharesOutstanding']].dropna()
                parts.append(pd.Series(pd.to_numeric(x.commonStockSharesOutstanding, errors='coerce').values, index=pd.to_datetime(x.date)))
        if not parts: continue
        bs = pd.concat(parts); bs = bs[bs > 0]
        sh = v.get('sh')
        sh = pd.to_numeric(sh, errors='coerce').dropna() if sh is not None and len(sh) else pd.Series(dtype=float)
        sh = sh[sh > 0]; sh.index = pd.to_datetime(sh.index)
        if len(sh):
            cov = pd.Series(sh.index).map(lambda d: d.year * 12 + d.month).values
            keep = [not (np.abs(cov - (d.year * 12 + d.month)) <= 3).any() for d in bs.index]
            bs = bs[keep]
        if not len(bs): continue
        comb = pd.concat([bs, sh]); comb = comb[~comb.index.duplicated(keep='last')].sort_index()
        FDX[t] = {**v, 'sh': comb}; n_aug += 1
    print('serie delle azioni completate con lo stato patrimoniale:', n_aug, flush=True)
    # prezzi: stesse serie della prova A
    L = pd.read_pickle(f'{ML}/eod_lungo/US.pkl.gz'); L['t'] = L.t.astype(str); L = L[L.t.isin(FDX.keys())]
    for t, x in L.groupby('t', sort=False): PXX[t] = x.drop(columns='t').set_index('date')
    del L; gc.collect()
    for fn in glob.glob(f'{ML}/storico5/raw/prezzi_us/*.pkl'):
        t = os.path.basename(fn)[:-7]
        if t in FDX and t not in PXX:
            d = pd.read_pickle(fn)
            if d is not None and len(d): PXX[t] = d.set_index('date')
    N = pd.read_pickle(f'{ML}/eod_lungo/US_uscite.pkl.gz'); N['t'] = N.t.astype(str); N = N[N.t.isin(FDX.keys())]
    for t, x in N.groupby('t', sort=False):
        if t not in PXX: PXX[t] = x.drop(columns='t').set_index('date')
    del N; gc.collect()
    print('con prezzi', len(PXX), flush=True)
    todo = sorted(set(FDX) & set(PXX))
    rows, meta = [], []
    with Pool(4) as P:
        for k, (rr, m) in enumerate(P.imap_unordered(one, todo, chunksize=10)):
            rows += rr
            if m is not None: meta.append(m)
            if k % 500 == 0: print(k, len(rows), flush=True)
    R = pd.DataFrame(rows); M = pd.DataFrame(meta)
    R.to_pickle(f'{OUT}/bilanci_pit_raw.pkl'); M.to_pickle(f'{OUT}/meta.pkl')
    print(R.shape, M.shape, 'errori', int(M.get('err', pd.Series(dtype=object)).notna().sum()))
    print(R.groupby(R.date.dt.year).size().to_dict())
