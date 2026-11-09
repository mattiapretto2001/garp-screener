# Storico 2000-2011: download di domani (08/11/2026), in ordine di utilita'. Vedi PIANO_DOMANI_2000_2011.md.
# Chiave EODHD: s5_common (variabile EODHD_API_TOKEN se esiste, altrimenti nulla: la mette il proxy).
# Tetto: si ferma quando il contatore supera (contatore di partenza + BUDGET) o 99.000 assoluti.
# uso:
#   python3 s5_08_domani.py piano                 # solo conti, nessuna chiamata a pagamento
#   python3 s5_08_domani.py tutto [BUDGET]         # passi 1-6 in ordine (BUDGET default 70000)
#   python3 s5_08_domani.py <passo> [BUDGET]       # un passo solo: exusa | snap | mancanti | solofund1 | splits | etf
import os, sys, json, glob, pickle, pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor
from s5_common import get, usage, OUT, ML, BW
sys.path.insert(0, BW)
from world_common import symbols, HOME
import world_11_fund2 as W
SO = f'{ML}/sopravv'
DOM = f'{OUT}/domani'; os.makedirs(DOM, exist_ok=True)
FXA = {'EUR': 1.12, 'SEK': 0.1, 'DKK': 0.15, 'NOK': 0.1, 'CHF': 1.05, 'CAD': 0.76, 'TWD': 0.032, 'KRW': 0.00078, 'GBX': 0.013, 'AUD': 0.72}
CUR = {'XETRA': 'EUR', 'PA': 'EUR', 'AS': 'EUR', 'MC': 'EUR', 'BR': 'EUR', 'HE': 'EUR', 'SW': 'CHF', 'ST': 'SEK', 'CO': 'DKK', 'OL': 'NOK',
       'LSE': 'GBX', 'TO': 'CAD', 'TW': 'TWD', 'KO': 'KRW', 'AU': 'AUD'}
SNAP_DATES = ['2001-06-29', '2005-06-30', '2009-06-30']
ETF = ['SPY', 'MDY', 'IWM', 'QQQ', 'XLK', 'XLF', 'XLE', 'XLV', 'XLI', 'XLY', 'XLP', 'XLU', 'XLB', 'IYW', 'IYF', 'IYH', 'IYE', 'IYR', 'IYZ',
       'IYT', 'IYC', 'IYK', 'IDU', 'IYM', 'IYJ', 'IGV', 'IGN', 'SOXX', 'IBB', 'ITB', 'IHI', 'IAI', 'IAT', 'IEZ', 'IEO', 'XHB', 'XBI', 'KBE', 'XRT']
ARG = sys.argv[1] if len(sys.argv) > 1 else 'piano'
BUDGET = int(sys.argv[2]) if len(sys.argv) > 2 else 70000
U0 = None if ARG == 'piano' else usage()
STOP = None if U0 is None else min(U0 + BUDGET, 99000)


def ok_to_spend(cost):
    if ARG == 'piano': return False
    u = usage()
    if u is None or u + cost > STOP:
        print(f'STOP: contatore {u}, tetto {STOP}, servirebbero altri {cost}', flush=True); return False
    return True


def fetch_fund(tickers, fn, chunk=200):
    D = pickle.load(open(fn, 'rb')) if os.path.exists(fn) else {}
    todo = [t for t in tickers if t not in D]
    print(f'  bilanci: {len(todo)} da scaricare ({10 * len(todo)} crediti) -> {os.path.basename(fn)}', flush=True)
    for i in range(0, len(todo), chunk):
        part = todo[i:i + chunk]
        if not ok_to_spend(10 * len(part)): break
        def one(t):
            j = get(f'fundamentals/{t}')
            if not isinstance(j, dict) or not j: return t, None
            try: return t, W.extract(j)
            except Exception as e: return t, {'err': str(e)}
        with ThreadPoolExecutor(8) as P:
            for t, d in P.map(one, part): D[t] = d
        pickle.dump(D, open(fn, 'wb'))
        print(f'  {i + len(part)} fatti, contatore {usage()}', flush=True)
    return D


def fetch_px(tickers, folder):
    os.makedirs(folder, exist_ok=True)
    todo = [t for t in tickers if not os.path.exists(f'{folder}/{t}.pkl')]
    print(f'  prezzi: {len(todo)} da scaricare ({len(todo)} crediti)', flush=True)
    for i in range(0, len(todo), 500):
        part = todo[i:i + 500]
        if not ok_to_spend(len(part)): break
        def one(t):
            j = get(f'eod/{t}', **{'from': '1998-01-01'})
            if j in ('ERR', 'LIMIT'): return
            d = pd.DataFrame(j) if isinstance(j, list) and j else pd.DataFrame()
            if len(d): d = pd.DataFrame({'date': pd.to_datetime(d.date), 'c': d.close.astype('float32'), 'a': d.adjusted_close.astype('float32'), 'v': d.volume.astype('float32')})
            d.to_pickle(f'{folder}/{t}.pkl')
        with ThreadPoolExecutor(10) as P: list(P.map(one, part))


# ---------------------------------------------------------------- liste
def lista_exusa():
    return [l.strip() for l in open(f'{SO}/domani_exusa_bilanci_completi.txt') if l.strip()]


def calendario(ex):
    L = pd.read_pickle(f'{ML}/eod_lungo/{ex}.pkl.gz')
    n = L.groupby('date').size()
    return n[n >= 0.5 * n.rolling(20, min_periods=1).median()].index          # solo giorni di borsa veri


def giorno_vero(ex, d, cal=None):
    cal = calendario(ex) if cal is None else cal
    c = cal[cal <= pd.Timestamp(d)]
    return c[-1].strftime('%Y-%m-%d') if len(c) else None


def lista_snap():
    jobs = []
    for ex in CUR:
        cal = calendario(ex)
        for d in SNAP_DATES:
            dd = giorno_vero(ex, d, cal)
            if dd is None: continue
            if os.path.exists(f'{SO}/bulk_{ex}_{d}.pkl') or os.path.exists(f'{DOM}/bulk_{ex}_{dd}.pkl'): continue
            jobs.append((ex, dd))
    return jobs


def lista_mancanti():
    """titoli di casa liquidi (>=3 M$ al giorno, prezzo >=1$) in almeno 2 delle 3 istantanee, che non abbiamo"""
    out = []
    for ex, cur in CUR.items():
        fs = sorted(glob.glob(f'{DOM}/bulk_{ex}_*.pkl')) + sorted(glob.glob(f'{SO}/bulk_{ex}_2005-06-30.pkl'))
        if not fs: continue
        s = symbols(ex); home = set(s.Code)
        have = set(pd.read_pickle(f'{ML}/eod_lungo/{ex}.pkl.gz').t.astype(str))
        hits = {}
        for f in fs:
            b = pd.read_pickle(f); b = b[b.code.isin(home)]
            ok = (b.close * FXA[cur] >= 1) & (b.close * b.volume * FXA[cur] >= 3e6)
            for c in b[ok].code: hits[c] = hits.get(c, 0) + 1
        need = min(2, len(fs))
        out += [f'{c}.{ex}' for c, n in hits.items() if n >= need and c not in have]
    return sorted(out)


def lista_solofund1():
    """titoli presenti solo in fund.pkl (campi vecchi), liquidi nel 2000-2010 secondo i prezzi lunghi"""
    f1 = pickle.load(open(f'{BW}/fund/fund.pkl', 'rb')); f2 = pickle.load(open(f'{BW}/fund/fund2.pkl', 'rb'))
    ex_list = set(lista_exusa())
    cand = [t for t in f1 if t not in f2 and t not in ex_list]
    by_ex = {}
    for t in cand: by_ex.setdefault(t.rsplit('.', 1)[1], []).append(t.rsplit('.', 1)[0])
    out = []
    for ex, codes in by_ex.items():
        if ex not in CUR and ex != 'US': continue
        L = pd.read_pickle(f'{ML}/eod_lungo/{ex}.pkl.gz'); L['t'] = L.t.astype(str)
        L = L[L.t.isin(codes) & (L.date >= '2000-01-01') & (L.date <= '2010-12-31')]
        fx = 1.0 if ex == 'US' else FXA[CUR[ex]]
        L['dv'] = L.c * L.v * fx
        q = L.groupby(['t', pd.Grouper(key='date', freq='QE')]).dv.median()
        n = (q >= 3e6).groupby(level=0).sum()
        out += [f'{t}.{ex}' for t in n[n >= 2].index]
    return sorted(out)


def lista_splits():
    U = pd.read_pickle(f'{OUT}/universo_prezzi_us.pkl')
    return sorted(set(U[U.storico & (U.src == 'D')].t))


# ---------------------------------------------------------------- passi
def passo_exusa():
    print('PASSO 1: bilanci completi dei 1.027 titoli non americani del pannello', flush=True)
    fetch_fund(lista_exusa(), f'{DOM}/fond_exusa.pkl')


def passo_snap():
    jobs = lista_snap()
    print(f'PASSO 2: istantanee di borsa fuori dagli USA, {len(jobs)} ({100 * len(jobs)} crediti)', flush=True)
    for ex, dd in jobs:
        if not ok_to_spend(100): break
        x = get(f'eod-bulk-last-day/{ex}', date=dd)
        if isinstance(x, list) and x:
            pd.DataFrame(x).to_pickle(f'{DOM}/bulk_{ex}_{dd}.pkl'); print(' ', ex, dd, len(x), flush=True)
        else:
            print(' ', ex, dd, 'vuota', flush=True)


def passo_mancanti():
    L = lista_mancanti()
    print(f'PASSO 3: titoli liquidi fuori dagli USA che non avevamo: {len(L)} (prezzi + bilanci, {11 * len(L)} crediti)', flush=True)
    fetch_px(L, f'{DOM}/prezzi_exusa'); fetch_fund(L, f'{DOM}/fond_mancanti_exusa.pkl')


def passo_solofund1():
    L = lista_solofund1()
    print(f'PASSO 4: titoli solo in fund.pkl liquidi nel 2000-2010: {len(L)} ({10 * len(L)} crediti)', flush=True)
    fetch_fund(L, f'{DOM}/fond_solofund1.pkl')


def passo_splits():
    L = lista_splits()
    print(f'PASSO 5: frazionamenti delle {len(L)} serie americane scaricate il 07/11 (controllo qualita, {len(L)} crediti)', flush=True)
    fn = f'{DOM}/splits_us.pkl'; D = pickle.load(open(fn, 'rb')) if os.path.exists(fn) else {}
    todo = [t for t in L if t not in D]
    for i in range(0, len(todo), 500):
        part = todo[i:i + 500]
        if not ok_to_spend(len(part)): break
        with ThreadPoolExecutor(10) as P:
            for t, j in zip(part, P.map(lambda t: get(f'splits/{t}.US', **{'from': '1998-01-01'}), part)): D[t] = j
        pickle.dump(D, open(fn, 'wb'))


def passo_etf():
    print(f'PASSO 6: prezzi dal 1998 di {len(ETF)} fondi indice di settore e industria USA (prova dei temi "M" con le uscite incluse)', flush=True)
    fetch_px([f'{e}.US' for e in ETF], f'{DOM}/prezzi_etf')


PASSI = {'exusa': passo_exusa, 'snap': passo_snap, 'mancanti': passo_mancanti, 'solofund1': passo_solofund1, 'splits': passo_splits, 'etf': passo_etf}
if ARG == 'piano':
    n1 = len(lista_exusa()); n2 = len(lista_snap()); n4 = len(lista_solofund1()); n5 = len(lista_splits())
    print(f'1 exusa: {n1} -> {10 * n1} crediti')
    print(f'2 snap: {n2} istantanee -> {100 * n2} crediti')
    print('3 mancanti: dipende dalle istantanee (stima 250-400 titoli -> 2.750-4.400 crediti)')
    print(f'4 solofund1: {n4} -> {10 * n4} crediti')
    print(f'5 splits: {n5} -> {n5} crediti')
    print(f'6 etf: {len(ETF)} -> {len(ETF)} crediti')
elif ARG == 'tutto':
    for k in ['exusa', 'snap', 'mancanti', 'solofund1', 'splits', 'etf']: PASSI[k]()
    print('fine; contatore', usage(), 'partenza', U0)
else:
    PASSI[ARG](); print('fine; contatore', usage(), 'partenza', U0)
