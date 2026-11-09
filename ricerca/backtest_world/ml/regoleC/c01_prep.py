# Prova C (08/11/2026): regole di gestione per i "moltiplicatori". Fase 1: liste, prezzi giornalieri in euro, indice mondiale.
# REGOLE DELLE LISTE FISSATE PRIMA DI GUARDARE I RISULTATI (nessun rendimento viene letto in questo script):
#  (i) 2012-2026, liste vere dei backtest esistenti (scr_common, non ritoccate): Crescita = regole Moonshot a ogni taglia (CR)
#      OPPURE Radar A (RADA, >= 2 Mld$). Mondo (USA, Europa, Asia, Canada, Australia). Lista disponibile dal primo giorno di
#      borsa dopo la fine del trimestre.
#  (ii) 2000-2011, PROXY di solo prezzo (non sono le liste vere: i bilanci 2000-2005 non ci sono). A ogni fine trimestre
#      12/1999-09/2011, dentro l'universo USA v2 con la correzione "stimata" dei volumi (Prova A; variante prudente a parte):
#       1. fuori finanza, immobiliare, energia, miniere, servizi pubblici (colonna excl, dal nome: come le esclusioni GARP);
#       2. piccole e medie: capitalizzazione <= 15 Mld$ dove ci sono le azioni; dove non ci sono, fuori dai 300 titoli con
#          piu' scambi in dollari della data (le grandi);
#       3. volatilita' a 1 anno nel 30% piu' alto (dentro l'insieme del punto 2, a quella data);
#       4. momentum forte: media dei percentili del momentum 12-1 e 6-1 nel 20% piu' alto, con entrambi > 0;
#       5. prezzo >= 70% del massimo a 52 settimane (la regola di prezzo del Moonshot).
#      Lo stesso proxy e' calcolato anche sul 2012-2025 (date 12/2011-09/2025) come "ponte" per confrontarlo con le liste vere.
#  Prezzi: corretti per dividendi e frazionamenti, puliti con world_04_features.clean, piu' un controllo dei frazionamenti non
#  corretti (salto di un giorno vicino a un rapporto tondo, con il volume che si muove al contrario). In euro: USA con EURUSD
#  (EODHD, dal 1998); resto del mondo con eod/fx.pkl.
#  Uscita dal listino: la serie finisce prima del 07/10/2026; se l'ultimo prezzo e' sotto il 25% del massimo dell'ultimo anno
#  conta come fallimento (valore 0), altrimenti si incassa l'ultimo prezzo (regola dei rapporti precedenti).
#  Indice mondiale in euro: 50% VTSMX (Vanguard Total US) + 50% VGTSX (Vanguard Total International), ribilanciati ogni mese,
#  fino al 31/12/2009 (PROXY dell'ACWI/FTSE All-World); poi VT (FTSE Global All Cap) fino al 30/09/2019; poi VWCE.
# Crediti EODHD: 3 (VTSMX, VGTSX, EURUSD), gia' scaricati in regoleC/raw.
import os, sys, json, pickle, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); ML = os.path.dirname(HERE); BW = os.path.dirname(ML)
sys.path.insert(0, ML); sys.path.insert(0, BW)
OUT = f'{HERE}/dati'; os.makedirs(OUT, exist_ok=True)
TODAY = pd.Timestamp('2026-11-06')
RATIOS = np.array([2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 75, 100, 150, 200, 250, 500, 1000], float)


def raw_series(name):
    j = json.load(open(f'{HERE}/raw/{name}.json'))
    d = pd.DataFrame(j); d.index = pd.to_datetime(d.date)
    return d.adjusted_close.astype(float)


SPL_US = f'{ML}/storico5/splits_A'
SPL_X = f'{HERE}/raw/splits'
os.makedirs(SPL_X, exist_ok=True)
STATS = dict(cand=0, fixed=0, nolist=0, need=set())
TRUNC = []; TRUNCSET = set()


def split_list(t, us):
    fn = f'{SPL_US}/{t}.json' if us else f'{SPL_X}/{t}.json'
    if not os.path.exists(fn):
        fn2 = f'{SPL_X}/{t}{".US" if us else ""}.json'
        if not os.path.exists(fn2): return None
        fn = fn2
    out = []
    for x in json.load(open(fn)):
        try:
            a, b = [float(z) for z in x['split'].split('/')]
            if a > 0 and b > 0: out.append((pd.Timestamp(x['date']), b / a))   # moltiplicatore del prezzo
        except Exception:
            pass
    return out


def fix_splits(aa, t, us):
    """salti di un giorno (x > 1,8 o < 0,55) che coincidono (entro 5 giorni, rapporto entro il 15%) con un frazionamento
    della lista EODHD: frazionamento non corretto nel prezzo, lo tolgo. Senza lista non correggo nulla (e lo conto)."""
    a = aa.values.copy(); idx = aa.index
    r = a[1:] / a[:-1]
    cand = np.where((r > 1.8) | (r < 0.55))[0] + 1
    if not len(cand): return aa, 0
    SP = split_list(t, us)
    n = 0
    for k in cand:
        x = a[k] / a[k - 1]
        STATS['cand'] += 1
        if SP is None:
            q = x if x > 1 else 1 / x
            if np.min(np.abs(q / RATIOS - 1)) < 0.04: STATS['nolist'] += 1; STATS['need'].add((t, us))
            continue
        ok = any(abs((idx[k] - d).days) <= 5 and abs(np.log(x) - np.log(m)) < np.log(1.15) for d, m in SP)
        if ok:
            a[k:] = a[k:] / x; n += 1; STATS['fixed'] += 1
    return pd.Series(a, index=idx), n


def clean_series(d, t, us):
    from world_04_features import clean
    d = d[~d.index.duplicated(keep='last')].sort_index()
    d = d[(d.c > 0) & d.a.notna() & (d.a > 0)]
    if len(d) < 60: return None, 0
    aa, _ = clean(d)
    aa, n = fix_splits(aa, t, us)
    # dati impossibili: salto di un giorno oltre x4 senza aumento del volume (o oltre x20), non spiegato da un frazionamento (es. TRA 2010, NXGN 2002: codici con la
    # storia di due titoli diversi). La serie si ferma il giorno prima: si incassa l'ultimo prezzo buono (non e' un fallimento).
    r = aa.values[1:] / aa.values[:-1]
    vv = d.v.reindex(aa.index).values.astype(float)
    bad = []
    for k in np.where(r > 4)[0] + 1:
        vb = np.nanmedian(vv[max(0, k - 20):k]) if k > 0 else np.nan
        va = np.nanmedian(vv[k:k + 10])
        # i salti veri (AMC 2021, Amarin 2018) arrivano con il volume che esplode; i codici "mescolati" no
        if r[k - 1] > 20 or not (va > vb): bad.append(k)
    if bad:
        k = bad[0]
        TRUNC.append((t, str(aa.index[k].date()), float(r[k - 1])))
        aa = aa.iloc[:k]
        if len(aa) < 60: return None, n
        TRUNCSET.add(t)
    return aa, n


def ended_info(aa, t=None):
    last = aa.index[-1]
    if t in TRUNCSET: return last, True, False
    ended = last < TODAY - pd.Timedelta(days=30)
    bk = False
    if ended:
        h = aa[aa.index >= last - pd.Timedelta(days=365)]
        bk = bool(aa.iloc[-1] < 0.25 * h.max() or aa.iloc[-1] <= 0)
    return last, ended, bk


def matrix(series, cal):
    """matrice titoli x giorni (float32), riempita in avanti fino a 10 giorni dentro la serie, NaN fuori"""
    tick = sorted(series)
    M = np.full((len(tick), len(cal)), np.nan, np.float32)
    for i, t in enumerate(tick):
        s = series[t]
        s = s[(s.index >= cal[0] - pd.Timedelta(days=15)) & (s.index <= cal[-1])]
        if not len(s): continue
        x = s.reindex(cal.union(s.index)).ffill(limit=10).reindex(cal)
        x[(cal < s.index[0]) | (cal > s.index[-1])] = np.nan
        M[i] = x.values.astype(np.float32)
    return tick, M


# ------------------------------------------------------------------ indice mondiale in euro
def world_index():
    eurusd = raw_series('EURUSD.FOREX')
    vt = raw_series('VTSMX.US'); vg = raw_series('VGTSX.US')
    cal = pd.bdate_range('1999-12-01', '2026-11-06')
    vt = vt.reindex(cal).ffill(); vg = vg.reindex(cal).ffill(); fx = eurusd.reindex(cal).ffill()
    # 50/50 ribilanciato a ogni inizio mese (in USD), poi in euro
    rv = vt.pct_change().fillna(0); rg = vg.pct_change().fillna(0)
    val = [1.0]
    v1, v2 = 0.5, 0.5
    for k in range(1, len(cal)):
        v1 *= 1 + rv.iloc[k]; v2 *= 1 + rg.iloc[k]
        if k + 1 < len(cal) and cal[k + 1].month != cal[k].month:   # fine mese: ribilancio
            tot = v1 + v2; v1 = v2 = tot / 2
        val.append(v1 + v2)
    prox_usd = pd.Series(val, index=cal)
    prox_eur = prox_usd / fx
    B = pickle.load(open(f'{BW}/eod/bench.pkl', 'rb'))
    FX = pd.read_pickle(f'{BW}/eod/fx.pkl').sort_index().ffill()
    vtw = B['VT.US'].a.astype(float); vtw = vtw / FX.EUR.reindex(vtw.index).ffill()
    vw = B['VWCE.XETRA'].a.astype(float)
    vtw = vtw.reindex(cal).ffill(); vw = vw.reindex(cal).ffill()
    r = prox_eur.pct_change()
    c1 = pd.Timestamp('2009-12-31'); c2 = pd.Timestamp('2019-09-30')
    r_vt = vtw.pct_change(); r_vw = vw.pct_change()
    rr = pd.Series(np.where(cal <= c1, r, np.where(cal <= c2, r_vt, r_vw)), index=cal).fillna(0)
    W = (1 + rr).cumprod()
    # controllo del proxy sul periodo di sovrapposizione con VT (2010-2011 e 2010-2019)
    chk = {}
    for a, b in [('2010-01-04', '2011-12-30'), ('2010-01-04', '2019-09-30')]:
        x = prox_eur[a:b]; y = vtw[a:b]
        yrs = (pd.Timestamp(b) - pd.Timestamp(a)).days / 365.25
        mx = x.resample('ME').last().pct_change().dropna(); my = y.resample('ME').last().pct_change().dropna()
        chk[f'{a[:4]}-{b[:4]}'] = dict(proxy=(x.iloc[-1] / x.iloc[0]) ** (1 / yrs) - 1, VT=(y.iloc[-1] / y.iloc[0]) ** (1 / yrs) - 1,
                                       corr_mensile=float(mx.corr(my)), te_annuo=float((mx - my).std() * np.sqrt(12)))
    return W, prox_eur, eurusd, chk


# ------------------------------------------------------------------ proxy (ii)
def build_univ(P, cutoff):
    import sA_common as SC
    # copia di sA_common.build con la data finale come parametro (prep taglia al 30/09/2024)
    D = P[P.date <= cutoff].copy()
    D['anno'] = (D.date + pd.Timedelta(days=1)).dt.year
    D['storico'] = D.anno <= 2011
    D['turn'] = D.dv63 / D.cap
    D.loc[(D.cap < 1e7) | (D.cap > 5e12), ['cap', 'turn']] = np.nan
    D['titolo_speciale'] = D.t.str.contains(r'-(?:WS|WT|W|U|UN|R|RT)(?:-[A-Z]{1,2})?$|-R-W$', regex=True)
    base = (D.px >= 3) & (D.dv63 >= 3e6) & (D.n1y >= 200) & D.p52.notna() & D.f12.notna() & ~D.titolo_speciale
    Q = pd.DataFrame({'q1': D.a_tetto.astype(bool), 'q2': D.vol < 0.01, 'q3': D.dv63 > 2e10, 'q4': (D.px > 5000) & (D.t != 'BRK-A')})
    D['qualita_ko'] = Q.any(axis=1)
    nser = D.groupby('t').size()
    Upre = D[base & ~D.qualita_ko & (D.cap.isna() | (D.cap >= 300e6))]
    U, _, _ = SC.dedup(Upre, nser)
    return U


def proxy_lists(U):
    out = {}
    for d, x in U.groupby('date'):
        x = x[~x.excl.fillna(False).astype(bool)]
        rk = x.dv63.rank(ascending=False)
        sm = (x.cap.notna() & (x.cap <= 15e9)) | (x.cap.isna() & (rk > 300))
        x = x[sm & x.vol.notna() & x.mom12.notna() & x.mom6.notna()]
        if len(x) < 50: continue
        vp = x.vol.rank(pct=True)
        ms = (x.mom12.rank(pct=True) + x.mom6.rank(pct=True)) / 2
        mp = ms.rank(pct=True)
        sel = x[(vp > 0.70) & (mp > 0.80) & (x.mom12 > 0) & (x.mom6 > 0) & (x.p52 >= 0.70)]
        out[d] = sorted(sel.t)
    return out


def main():
    W, prox_eur, eurusd, chk = world_index()
    print('indice mondiale, controllo proxy vs VT:', json.dumps(chk, indent=1), flush=True)
    # ---------------- proxy: universi (stimata = principale, prudente = variante)
    from s5_common import OUT as S5
    P = pd.read_pickle(f'{S5}/pannello_prezzi_us_v2.pkl')
    C = pd.read_pickle(f'{S5}/volumi_corretti_A.pkl').set_index(['t', 'date'])
    j = C.reindex(pd.MultiIndex.from_frame(P[['t', 'date']]))
    Pv = P.copy(); hv = j.dv63_v.notna().values
    Pv.loc[hv, 'dv63'] = j.dv63_v.values[hv]; Pv.loc[hv, 'px'] = j.px_v.values[hv]
    Pp = P.copy(); hp = j.dv_raw.notna().values
    Pp.loc[hp, 'dv63'] = np.minimum(P.dv63.values[hp], j.dv_raw.values[hp]); Pp.loc[hp, 'px'] = np.minimum(P.px.values[hp], j.px_p.values[hp])
    Uv = build_univ(Pv, '2025-09-30'); Up = build_univ(Pp, '2011-09-30')
    U0 = pd.read_pickle(f'{S5}/universo_prezzi_us_v2.pkl')
    print('controllo universo: stimata 2000-11 righe', int(Uv.storico.sum()), '| v2 completo', int(U0.storico.sum()), '| prudente', int(Up.storico.sum()))
    LV = proxy_lists(Uv); LP = proxy_lists(Up)
    L_p1 = {d: v for d, v in LV.items() if d <= pd.Timestamp('2011-09-30')}
    L_p1p = {d: v for d, v in LP.items() if d <= pd.Timestamp('2011-09-30')}
    L_p3 = {d: v for d, v in LV.items() if d >= pd.Timestamp('2011-12-31')}
    for nm, L in [('proxy 2000-11', L_p1), ('proxy prudente', L_p1p), ('proxy 2012-25', L_p3)]:
        n = pd.Series({d: len(v) for d, v in L.items()})
        print(nm, 'date', len(n), 'titoli per data: media', round(n.mean(), 1), 'min', n.min(), 'max', n.max(), 'distinti', len(set().union(*L.values())), flush=True)
    # ---------------- liste vere 2012-2026
    import scr_common as S
    F = S.F
    m_cr = S.CR & S.UNI; m_ra = S.RADA & S.UNI
    m = m_cr | m_ra
    X = F[m][['t', 'date', 'ex', 'reg', 'mcap_usd', 'name', 'cur_px', 'delisted']].copy()
    X['cr'] = m_cr[m].values; X['ra'] = m_ra[m].values
    X['size'] = S.SIZE3[m].values
    L_p2 = {d: sorted(x.t) for d, x in X.groupby('date')}
    L_p2us = {d: sorted(x[x.ex == 'US'].t) for d, x in X.groupby('date')}
    n = pd.Series({d: len(v) for d, v in L_p2.items()})
    print('liste vere 2012-26: date', len(n), 'titoli per data media', round(n.mean(), 1), 'min', n.min(), 'max', n.max(),
          '| solo Crescita', round(X.cr.groupby(X.date).sum().mean(), 1), 'solo Radar A', round(X.ra.groupby(X.date).sum().mean(), 1),
          '| USA', round(pd.Series({d: len(v) for d, v in L_p2us.items()}).mean(), 1), flush=True)
    X.to_pickle(f'{OUT}/liste_vere_righe.pkl')
    # ---------------- prezzi: proxy (serie USA dal 1998)
    import s5_09_pannello_v2 as S9
    pool, src = S9.series_pool()
    need = set().union(*L_p1.values(), *L_p1p.values(), *L_p3.values())
    ser, info, nfix = {}, {}, {}
    fx = eurusd.reindex(pd.bdate_range('1997-12-01', '2026-11-06')).ffill()
    for t in sorted(need):
        d = pool.get(t)
        if d is None: continue
        aa, nf = clean_series(d, t, True)
        if aa is None: continue
        info[t] = ended_info(aa, t); nfix[t] = nf
        ser[t] = aa / fx.reindex(aa.index).ffill().bfill().values
    print('proxy: titoli richiesti', len(need), 'con prezzi', len(ser), '| frazionamenti corretti in', sum(v > 0 for v in nfix.values()), 'titoli', flush=True)
    del pool
    cal1 = pd.bdate_range('2000-01-03', '2011-12-30'); cal3 = pd.bdate_range('2012-01-02', '2025-12-31')
    t1, M1 = matrix(ser, cal1); t3, M3 = matrix(ser, cal3)
    # ---------------- prezzi: liste vere (eod/{borsa}.pkl, dal 2010), in euro
    FX = pd.read_pickle(f'{BW}/eod/fx.pkl').sort_index()
    calw = pd.bdate_range('2012-01-02', '2026-11-05')
    FXc = FX.reindex(FX.index.union(calw)).ffill()
    ser2, info2, nfix2 = {}, {}, {}
    meta = X.drop_duplicates('t').set_index('t')
    for ex, g in meta.groupby('ex'):
        E = pickle.load(open(f'{BW}/eod/{ex}.pkl', 'rb'))
        for t, row in g.iterrows():
            code = t.rsplit('.', 1)[0]
            d = E.get(code)
            if d is None: continue
            aa, nf = clean_series(d, (code if ex == 'US' else t), ex == 'US')
            if aa is None: continue
            cur = row.cur_px if isinstance(row.cur_px, str) else 'USD'
            cur = 'GBX' if cur == 'GBp' else cur
            if cur not in FXc.columns: continue
            k = (FXc[cur] / FXc['EUR']).reindex(aa.index.union(FXc.index)).ffill().reindex(aa.index)
            info2[t] = ended_info(aa, (code if ex == 'US' else t)); nfix2[t] = nf
            ser2[t] = aa * k.values
        del E
    print('liste vere: titoli', len(meta), 'con prezzi', len(ser2), '| frazionamenti corretti in', sum(v > 0 for v in nfix2.values()), flush=True)
    t2, M2 = matrix(ser2, calw)
    # ---------------- salva
    def ilists(L, tick):
        pos = {t: i for i, t in enumerate(tick)}
        return {d: np.array([pos[t] for t in v if t in pos], int) for d, v in L.items()}
    names = dict(zip(P.t, P.name)); names.update(dict(zip(meta.index, meta.name)))
    pack = {
        'P1': dict(cal=cal1, tick=t1, M=M1, L=ilists(L_p1, t1), info=info, W=W),
        'P1p': dict(cal=cal1, tick=t1, M=M1, L=ilists(L_p1p, t1), info=info, W=W),
        'P3': dict(cal=cal3, tick=t3, M=M3, L=ilists(L_p3, t3), info=info, W=W),
        'P2': dict(cal=calw, tick=t2, M=M2, L=ilists(L_p2, t2), info=info2, W=W),
        'P2us': dict(cal=calw, tick=t2, M=M2, L=ilists(L_p2us, t2), info=info2, W=W),
    }
    for k, v in pack.items():
        pickle.dump(v, open(f'{OUT}/{k}.pkl', 'wb'), protocol=4)
    pickle.dump(dict(names=names, nfix=nfix, nfix2=nfix2, chk=chk, meta=meta[['ex', 'reg', 'cur_px', 'delisted']]), open(f'{OUT}/aux.pkl', 'wb'))
    print('frazionamenti: salti candidati', STATS['cand'], 'corretti', STATS['fixed'], '| vicini a un rapporto tondo ma senza lista', STATS['nolist'], 'in', len(STATS['need']), 'titoli')
    print('serie fermate per salti impossibili:', len(TRUNC), TRUNC[:60])
    json.dump(TRUNC, open(f'{OUT}/serie_fermate.json', 'w'))
    json.dump(sorted(STATS['need']), open(f'{OUT}/split_mancanti.json', 'w'))
    print('salvato', {k: (len(v['tick']), v['M'].shape, len(v['L'])) for k, v in pack.items()})


if __name__ == '__main__':
    main()
