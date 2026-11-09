# Storico 2000-2011, punto 5.2a: universo USA 2000-2011 per i test di solo prezzo, societa' uscite comprese.
# Passo 'lista' (nessuna chiamata): dalle 22 istantanee semestrali 2000-2010 prendo ogni azione ordinaria
# NYSE/Nasdaq/NYSE American con prezzo >=3$ e scambi del giorno >=1 M$ (soglia bassa apposta: il filtro vero,
# >=3 M$ di mediana a 3 mesi e capitalizzazione stimata >=300 M$, si applica dopo sui prezzi giornalieri).
# Se il codice e' gia' nei nostri prezzi dal 1998 (eod_lungo) con la stessa chiusura quel giorno, e' coperto;
# altrimenti si scaricano i prezzi dal 1998 del codice e di tutte le sue varianti _old (1 credito l'una).
# Passo 'scarica': scarica la lista (tetto: contatore 95.900).
import os, sys, glob, json, pickle, pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor
from s5_common import get, usage, guard, OUT, ML, BW
sys.path.insert(0, BW)
from world_common import symbols
SO = f'{ML}/sopravv'
PX = f'{OUT}/raw/prezzi_us'; os.makedirs(PX, exist_ok=True)
FUNDPAT = (r'\b(?:Fund|Trust|Income|Municipal|Notes?|Preferred|Pfd|Depositary|Depositor|Warrants?|Units?|ETF|ETN|Portfolio|'
           r'Index|Strategic|Opportunit(?:y|ies) Fund|Closed|Debentures?|Bonds?|Capital Trust|Premium|Dividend)\b')

step = sys.argv[1]
if step == 'lista':
    s = symbols('US'); s['base'] = s.Code.str.replace(r'_old\d*$', '', regex=True)
    s['fondo'] = s.Name.fillna('').str.contains(FUNDPAT, case=False, regex=True)
    variants = s.groupby('base').Code.apply(list).to_dict()
    fondo = s.groupby('base').fondo.min().to_dict()   # fondo solo se TUTTE le varianti hanno nome da fondo
    L = pd.read_pickle(f'{ML}/eod_lungo/US.pkl.gz')
    have_codes = set(L.t.astype(str))
    rows = []
    for fn in sorted(glob.glob(f'{SO}/bulk_US_*.pkl')):
        b = pd.read_pickle(fn); dd = pd.Timestamp(b.date.iloc[0])
        b = b[b.code.isin(variants.keys())]
        b = b[(b.close >= 3) & (b.close * b.volume >= 1e6)].copy()
        b = b[~b.code.map(fondo).fillna(True)]
        x = L[L.date == dd][['t', 'c']]
        have_px = set(zip(x.t.astype(str).str.replace(r'_old\d*$', '', regex=True), (x.c.astype('float64') * 100).round().astype('int64')))
        b['A'] = [(c, int(round(float(p) * 100))) in have_px for c, p in zip(b.code, b.close)]
        b['date'] = dd
        rows.append(b[['date', 'code', 'close', 'adjusted_close', 'volume', 'A']])
    D = pd.concat(rows, ignore_index=True)
    D['dv'] = D.close * D.volume
    D.to_pickle(f'{OUT}/istantanee_liquide_1M.pkl')
    need = D[~D.A]
    todo = set()
    for c in need.code.unique():
        for v in variants.get(c, [c]):
            if v not in have_codes or v != c: todo.add(v)
            # se il codice uguale e' gia' nei nostri dati ma con un'altra chiusura, servono le varianti _old
    todo = sorted(v for v in todo if v not in have_codes)
    open(f'{OUT}/lista_prezzi_us.txt', 'w').write('\n'.join(f'{v}.US' for v in todo))
    print('righe liquide (>=3$, >=1M$)', len(D), '| codici unici', D.code.nunique(), '| coperti dai nostri prezzi', D[D.A].code.nunique())
    print('codici non coperti', need.code.nunique(), '-> ticker da scaricare (con varianti _old)', len(todo))
    print(D.groupby('date').agg(n=('code', 'size'), A=('A', 'mean'), n3=('dv', lambda x: (x >= 3e6).sum())).to_string())
elif step == 'scarica':
    L = [l.strip() for l in open(f'{OUT}/lista_prezzi_us.txt') if l.strip()]
    L = [t for t in L if not os.path.exists(f'{PX}/{t}.pkl')]
    u0 = guard(95900); print('da scaricare', len(L), 'contatore', u0, flush=True)

    def one(t):
        j = get(f'eod/{t}', **{'from': '1998-01-01'})
        if j in ('ERR', 'LIMIT'): return t, j
        if not j or not isinstance(j, list): pd.DataFrame().to_pickle(f'{PX}/{t}.pkl'); return t, 'vuoto'
        d = pd.DataFrame(j)
        d = pd.DataFrame({'date': pd.to_datetime(d.date), 'c': d.close.astype('float32'), 'a': d.adjusted_close.astype('float32'),
                          'v': d.volume.astype('float32')})
        d.to_pickle(f'{PX}/{t}.pkl'); return t, 'ok'

    out = []
    for k in range(0, len(L), 500):
        guard(95900)
        with ThreadPoolExecutor(10) as P: out += list(P.map(one, L[k:k + 500]))
        print(k + 500, 'fatti', flush=True)
    st = pd.Series(dict(out)).value_counts(); print(st)
    print('crediti', u0, '->', usage())
