# Storico 2000-2011, punto 5.2a: universo USA 2000-2011 per i test di solo prezzo, societa' uscite comprese.
#
# VERSIONE 2 (08/11/2026). Corregge l'errore trovato dalla verifica avversariale del 07/11 (la v1 e' in s5_02_universo_usa_v1.py):
#   la v1 teneva solo le righe delle istantanee il cui codice era un codice "base" della lista filtrata sulle borse principali,
#   quindi scartava (a) i codici con "_old" (WB_old2 = Wachovia, SGP_old1 = Schering-Plough...) e (b) i codici che oggi EODHD
#   mette fuori borsa (OTC/PINK) ma che nel 2000-2011 erano a New York: WAMUQ, IDMCQ, BLS, WYE, BDK, FMCC...
# Ora:
#   - la lista e' quella completa di EODHD (attive + uscite, /exchange-symbol-list/US e ?delisted=1, gia' in lists/), tutte le borse;
#   - una riga di istantanea si tiene se il suo codice e' nella lista (anche _old, anche OTC/PINK) oppure se lo e' una sua variante;
#   - per i codici fuori borsa si scartano i titoli esteri (codici di 5 lettere in F/Y, ISIN non americano, ADR, nomi da societa'
#     estera) e le voci della pseudo-borsa "US" senza ISIN americano (azioni vietnamite, turche, thailandesi con prezzi in valuta locale);
#   - fondi, privilegiate, warrant: stesso filtro sul nome di prima, piu' "Pref"/"Perpetual";
#   - "coperto" = c'e' gia' una serie con lo stesso codice base e la stessa chiusura quel giorno, cercando in TUTTE le serie che
#     abbiamo: eod_lungo/US, storico5/raw/prezzi_us, le 214 della verifica avversariale, eod_lungo/US_uscite (scaricate oggi).
# Passo 'lista' (nessuna chiamata): scrive storico5/lista_prezzi_us_v2.csv con le priorita':
#   1 = scambi stimati (chiusura x volume del giorno) >=3 M$ in almeno un'istantanea semestrale 2000-2010;
#   2 = fra 1 e 3 M$;
#   3 = tutte le altre azioni ordinarie uscite da NYSE/Nasdaq/Amex (lista delisted=1) ancora senza prezzi, non fondi.
#       Per queste le istantanee non dicono nulla (EODHD non le mette nelle istantanee): niente stima degli scambi.
# Passo 'scarica' [budget]: scarica i prezzi dal 1998 nell'ordine delle priorita' (1 credito a serie) e li salva in forma compatta
#   in eod_lungo/US_uscite.pkl.gz (formato lungo t, date, c, a, v come eod_lungo/US.pkl.gz), con lo stato in
#   eod_lungo/_stato_US_uscite.json. Tetto: contatore di partenza + budget, mai oltre 99.000. Riprende senza riscaricare.
# Passo 'compatta': unisce le parti scaricate in eod_lungo/US_uscite.pkl.gz e vi aggiunge le 214 serie della verifica
#   avversariale (origine in eod_lungo/_origine_US_uscite.json: 'oggi' o 'avv').
# Esito dell'08/11/2026: 10.462 serie scaricate (10.443 con dati, 19 vuote), 10.463 crediti; dopo il download le righe liquide
#   delle istantanee coperte da una serie salgono dal 97,2% al 99,6% (il resto: chiusure diverse di pochi centesimi o codici
#   senza serie in EODHD). Il pannello v2 e' s5_09_pannello_v2.py, l'universo v2 s5_10_universo_v2.py.
import os, sys, glob, json, time, pickle, pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor
from s5_common import get, usage, guard, OUT, ML, BW
sys.path.insert(0, BW)
from world_common import US_EX
SO = f'{ML}/sopravv'
PX = f'{OUT}/raw/prezzi_us'
AVV = f'{os.path.dirname(BW)}/avv_prezzi_raw'                 # 214 serie della verifica avversariale (json grezzi)
EL = f'{ML}/eod_lungo'
NEWF = f'{EL}/US_uscite.pkl.gz'; PARTS = f'{EL}/_parti_US_uscite'; STATO = f'{EL}/_stato_US_uscite.json'
LISTA = f'{OUT}/lista_prezzi_us_v2.csv'
FUNDPAT = (r'\b(?:Fund|Trust|Income|Municipal|Notes?|Preferred|Pfd|Depositary|Depositor|Warrants?|Units?|ETF|ETN|Portfolio|'
           r'Index|Strategic|Opportunit(?:y|ies) Fund|Closed|Debentures?|Bonds?|Capital Trust|Premium|Dividend|Pref|Perpetual)\b')
FOREIGN_NAME = (r'\b(?:ADR|ADS|American Depositary|Foreign|plc|PCL|JSC|PJSC|Oyj|Tbk|Bhd|Berhad|Akt|Namen)\b|'
                r'\bS\.A\.|\bN\.V\.|\bS\.p\.A\.|\bA/S\b')            # senza distinzione di maiuscole
FOREIGN_SIGLE = r'\b(?:AG|SA|NV|TAS|AB|ASA|SpA|KK|AS|SE)\b'                  # sigle societarie estere, maiuscole esatte
BASE = r'_old\d*$'


def lista_completa():
    """lista EODHD completa (attive prima, poi uscite), tutte le borse, con i flag per il filtro corretto"""
    out = []
    for d in (0, 1):
        for x in json.load(open(f'{BW}/lists/US_{d}.json')):
            x['delisted'] = d; out.append(x)
    A = pd.DataFrame(out).drop_duplicates('Code', keep='first').reset_index(drop=True)
    A['base'] = A.Code.str.replace(BASE, '', regex=True)
    A['principale'] = A.Exchange.isin(US_EX)
    nm = A.Name.fillna('')
    A['fondo'] = nm.str.contains(FUNDPAT, case=False, regex=True)
    i2 = A.Isin.fillna('').str[:2]
    estero_otc = (A.base.str.match(r'^[A-Z]{4}[FY]$') | ~i2.isin(['US', '']) |
                  ((nm.str.contains(FOREIGN_NAME, case=False, regex=True) | nm.str.contains(FOREIGN_SIGLE, case=True, regex=True)) & (i2 != 'US')))
    A['estero'] = ~A.principale & (estero_otc | ((A.Exchange == 'US') & (i2 != 'US')))
    A['ok'] = ~A.fondo & ~A.estero
    return A


def serie_esistenti():
    """codici con prezzi dal 1998 gia' scaricati, per origine"""
    have = {}
    L = pd.read_pickle(f'{EL}/US.pkl.gz'); L['t'] = L.t.astype(str)
    for t in L.t.unique(): have[t] = 'A'
    for fn in glob.glob(f'{PX}/*.pkl'): have.setdefault(os.path.basename(fn)[:-7], 'D')
    for fn in glob.glob(f'{AVV}/*.json'): have.setdefault(os.path.basename(fn)[:-8], 'V')
    if os.path.exists(STATO):
        for t, s_ in json.load(open(STATO)).items():
            if s_ in ('ok', 'vuoto'): have.setdefault(t, 'W')
    return have, L


def chiusure_alle_date(L, dates):
    """(codice base, data, chiusura in centesimi) di tutte le serie che abbiamo, alle date delle istantanee"""
    dates = set(pd.to_datetime(list(dates)))
    rows = [L[L.date.isin(dates)][['t', 'date', 'c']]]
    for fn in glob.glob(f'{PX}/*.pkl'):
        d = pd.read_pickle(fn)
        if d is None or d.empty: continue
        x = d[d.date.isin(dates)][['date', 'c']].copy(); x['t'] = os.path.basename(fn)[:-7]; rows.append(x)
    for fn in glob.glob(f'{AVV}/*.json'):
        try: j = json.load(open(fn))
        except Exception: continue
        if not isinstance(j, list) or not j: continue
        d = pd.DataFrame(j); d['date'] = pd.to_datetime(d.date)
        x = d[d.date.isin(dates)][['date', 'close']].rename(columns={'close': 'c'}); x['t'] = os.path.basename(fn)[:-8]; rows.append(x)
    if os.path.exists(NEWF):
        N = pd.read_pickle(NEWF); N['t'] = N.t.astype(str); rows.append(N[N.date.isin(dates)][['t', 'date', 'c']])
    X = pd.concat(rows, ignore_index=True)
    X['b'] = X.t.astype(str).str.replace(BASE, '', regex=True)
    return set(zip(X.b, X.date, (X.c.astype('float64') * 100).round().astype('int64')))


step = sys.argv[1]
if step == 'lista':
    A = lista_completa()
    Aok = A[A.ok]
    ok_codes = set(Aok.Code)
    variants = Aok.groupby('base').Code.apply(list).to_dict()
    have, L = serie_esistenti()
    snaps = sorted(glob.glob(f'{SO}/bulk_US_*.pkl'))
    B = []
    for fn in snaps:
        b = pd.read_pickle(fn)[['code', 'date', 'close', 'adjusted_close', 'volume']]
        b['date'] = pd.Timestamp(b.date.iloc[0])
        b = b[(b.close >= 3) & (b.close * b.volume >= 1e6)].copy()
        b['base'] = b.code.str.replace(BASE, '', regex=True)
        # CORREZIONE: si tiene il codice se e' nella lista (anche _old, anche fuori borsa) o se lo e' una sua variante
        b = b[b.code.isin(ok_codes) | b.base.isin(variants.keys())]
        B.append(b)
    D = pd.concat(B, ignore_index=True)
    D['dv'] = D.close * D.volume
    hp = chiusure_alle_date(L, D.date.unique())
    D['A'] = [(bs, dd, int(round(float(p) * 100))) in hp for bs, dd, p in zip(D.base, D.date, D.close)]
    D['in_lista'] = D.code.isin(set(A.Code))
    D = D.merge(A[['Code', 'Exchange', 'delisted', 'Name']].rename(columns={'Code': 'code'}), on='code', how='left')
    D.to_pickle(f'{OUT}/istantanee_liquide_1M_v2.pkl')
    need = D[~D.A]
    # codici da scaricare: il codice stesso (se e' nella lista e passa i filtri) e le sue varianti _old; stima = scambi massimi
    est = {}
    for c, bs, dv in zip(need.code, need.base, need.dv):
        for v in ({c} & ok_codes) | set(variants.get(bs, [])):
            if v in have: continue
            est[v] = max(est.get(v, 0.0), float(dv))
    T = pd.DataFrame({'t': list(est), 'dv_stima': list(est.values())})
    T['prio'] = np.where(T.dv_stima >= 3e6, 1, 2)
    # priorita' 3: le altre azioni ordinarie uscite dalle borse principali, senza prezzi e non fondi
    R = A[(A.delisted == 1) & A.principale & ~A.fondo & ~A.Code.isin(have) & ~A.Code.isin(list(est))]
    R = R.assign(o=~R.Code.str.contains('_old')).sort_values(['o', 'Code'])     # prima i codici _old (societa' vecchie)
    T = pd.concat([T.sort_values(['prio', 'dv_stima'], ascending=[True, False]),
                   pd.DataFrame({'t': R.Code, 'dv_stima': np.nan, 'prio': 3})], ignore_index=True)
    Ai = A.set_index('Code')
    for c in ['Name', 'Exchange', 'delisted', 'Isin']: T[c] = T.t.map(Ai[c])
    T['old'] = T.t.str.contains('_old'); T['fuori_borsa'] = ~T.Exchange.isin(US_EX)
    T.to_csv(LISTA, index=False)
    print('righe liquide (>=3$, >=1M$) tenute', len(D), '| codici', D.code.nunique(), '| coperte', round(D.A.mean(), 3),
          '| non coperte', len(need), 'righe,', need.code.nunique(), 'codici')
    print('  di cui non coperte con >=3M$:', (need.dv >= 3e6).sum(), 'righe; codici _old', need[need.code.str.contains('_old')].code.nunique(),
          '| fuori borsa', need[~need.Exchange.isin(US_EX)].code.nunique())
    print('da scaricare per priorita:', T.prio.value_counts().sort_index().to_dict(), '| _old', T.old.sum(),
          '| fuori borsa', T.fuori_borsa.sum(), '| totale', len(T))
    print(T[T.prio < 3].groupby(['prio', 'fuori_borsa']).size().to_string())
elif step == 'scarica':
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 15000
    T = pd.read_csv(LISTA)
    st = json.load(open(STATO)) if os.path.exists(STATO) else {}
    todo = [t for t in T.t if t not in st]
    os.makedirs(PARTS, exist_ok=True)
    u0 = usage(); cap = min(u0 + budget, 99000)
    print('da scaricare', len(todo), '| contatore', u0, '| tetto', cap, flush=True)

    def one(t):
        j = get(f'eod/{t}.US', **{'from': '1998-01-01'})
        if j in ('ERR', 'LIMIT'): return t, j, None
        if not j or not isinstance(j, list): return t, 'vuoto', None
        d = pd.DataFrame(j)
        if d.empty or 'adjusted_close' not in d: return t, 'vuoto', None
        return t, 'ok', pd.DataFrame({'t': t, 'date': pd.to_datetime(d.date), 'c': d.close.astype('float32'),
                                      'a': d.adjusted_close.astype('float32'), 'v': d.volume.astype('float32')})
    for k in range(0, len(todo), 500):
        part = todo[k:k + 500]
        u = usage()
        if u is None or u + len(part) > cap:
            print('mi fermo: contatore', u, '+', len(part), '> tetto', cap, flush=True); break
        R = []
        with ThreadPoolExecutor(10) as P:
            for t, s_, d in P.map(one, part):
                if s_ == 'LIMIT': print('limite EODHD raggiunto', flush=True)
                if s_ in ('ok', 'vuoto'): st[t] = s_
                if d is not None: R.append(d)
        if R:
            n = len(glob.glob(f'{PARTS}/part_*.pkl'))
            pd.concat(R, ignore_index=True).to_pickle(f'{PARTS}/part_{n:03d}.pkl')
        json.dump(st, open(STATO, 'w'))
        print(k + len(part), 'fatti | ok', sum(v == 'ok' for v in st.values()), '| vuoti', sum(v == 'vuoto' for v in st.values()),
              '| contatore', usage(), time.strftime('%H:%M:%S'), flush=True)
    print('crediti', u0, '->', usage(), flush=True)
elif step == 'compatta':
    # unisce le parti in eod_lungo/US_uscite.pkl.gz; aggiunge le 214 serie della verifica avversariale (origine nel file _origine)
    fr = [pd.read_pickle(f) for f in sorted(glob.glob(f'{PARTS}/part_*.pkl'))]
    if os.path.exists(NEWF): fr.insert(0, pd.read_pickle(NEWF))
    orig = json.load(open(f'{EL}/_origine_US_uscite.json')) if os.path.exists(f'{EL}/_origine_US_uscite.json') else {}
    for fn in sorted(glob.glob(f'{AVV}/*.json')):
        t = os.path.basename(fn)[:-8]
        if orig.get(t) == 'avv': continue
        j = json.load(open(fn))
        if not isinstance(j, list) or not j: continue
        d = pd.DataFrame(j)
        fr.append(pd.DataFrame({'t': t, 'date': pd.to_datetime(d.date), 'c': d.close.astype('float32'),
                                'a': d.adjusted_close.astype('float32'), 'v': d.volume.astype('float32')}))
        orig[t] = 'avv'
    N = pd.concat(fr, ignore_index=True); N['t'] = N.t.astype(str)
    N = N.drop_duplicates(['t', 'date'], keep='last').sort_values(['t', 'date']).reset_index(drop=True)
    for t in N.t.unique(): orig.setdefault(t, 'oggi')
    N['t'] = N.t.astype('category')
    N.to_pickle(NEWF)
    json.dump(orig, open(f'{EL}/_origine_US_uscite.json', 'w'))
    chk = pd.read_pickle(NEWF)
    assert len(chk) == len(N)
    for f in glob.glob(f'{PARTS}/part_*.pkl'): os.remove(f)
    print('serie', N.t.nunique(), '| righe', len(N), '| MB', round(os.path.getsize(NEWF) / 1e6, 1),
          '| origine', pd.Series(orig).value_counts().to_dict())
