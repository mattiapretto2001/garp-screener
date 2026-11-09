# Storico 2000-2011, punto 5.1: EODHD ha i bilanci delle societa' uscite dal listino prima del 2011?
# 37 americane uscite fra il 2001 e il 2011 (6 banche/finanziarie, 31 industriali) + 15 europee
# (6 famose uscite prima del 2011, codici presunti; 9 grandi uscite fra il 2014 e il 2018 che EODHD elenca).
# 10 crediti a chiamata. Salva il JSON grezzo e un riepilogo campo per campo.
import sys, json, pickle, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from s5_common import get, usage, guard, OUT
RAW = f'{OUT}/raw/fond_verifica'
import os; os.makedirs(RAW, exist_ok=True)
US = ['LEH', 'BSC_old', 'MER', 'WAMUQ', 'NCC', 'WB_old2',
      'ENRNQ', 'MCWEQ', 'CPQ', 'PRD', 'GLBC', 'PHA', 'KM', 'PSFT_old', 'G_old', 'MAY', 'T1', 'GDT_old', 'BLS', 'PIXR',
      'PD_old', 'AT_old1', 'BUD_old', 'CCTYQ', 'NWAC', 'DNA_old', 'SGP_old1', 'GM_old', 'JAVA_old', 'BNI',
      'WYE', 'BDK', 'SII_old', 'PALM', 'GENZ_old', 'NOVL', 'Q_old']
EU = ['CBRY.LSE', 'RTR.LSE', 'AVE.PA', 'LOR.PA', 'SCH.XETRA', 'HVM.XETRA',
      'LG.PA', 'ALU.PA', 'TEC.PA', 'BG.LSE', 'ARM.LSE', 'SCV-B.ST', 'NOBN.SW', 'SYNN.SW', 'ABE.MC']
TICK = [f'{c}.US' for c in US] + EU
guard(95900)
u0 = usage()


def one(t):
    fn = f'{RAW}/{t}.json'
    if os.path.exists(fn): return t, json.load(open(fn))
    j = get(f'fundamentals/{t}')
    if j not in ('ERR', 'LIMIT'): json.dump(j, open(fn, 'w'))
    return t, j


with ThreadPoolExecutor(6) as P: res = dict(P.map(one, TICK))
print('crediti', u0, '->', usage())


def span(d):
    if not d: return 0, None, None
    ks = sorted(k for k in d if k and k[:2] in ('19', '20'))
    return len(ks), (ks[0] if ks else None), (ks[-1] if ks else None)


rows = []
for t in TICK:
    j = res.get(t)
    r = {'t': t}
    if not isinstance(j, dict) or not j:
        r['esito'] = 'nessun dato (404)' if j is None else str(j)[:30]; rows.append(r); continue
    g = j.get('General', {}) or {}
    r.update(nome=g.get('Name'), tipo=g.get('Type'), delisted=g.get('IsDelisted'), data_uscita=g.get('DelistedDate'),
             settore=g.get('Sector'), isin=g.get('ISIN'))
    F = j.get('Financials', {}) or {}
    for st, ab in [('Income_Statement', 'CE'), ('Balance_Sheet', 'SP'), ('Cash_Flow', 'CF')]:
        s = F.get(st, {}) or {}
        for per, pa in [('yearly', 'a'), ('quarterly', 'q')]:
            n, f, l = span(s.get(per))
            r[f'{ab}_{pa}_n'] = n; r[f'{ab}_{pa}_da'] = f; r[f'{ab}_{pa}_a'] = l
    os_ = j.get('outstandingShares', {}) or {}
    r['azioni_storico_n'] = sum(len(v or {}) for v in os_.values())
    E = j.get('Earnings', {}) or {}
    n, f, l = span(E.get('History')); r['utili_stime_n'] = n; r['utili_stime_da'] = f
    hl = j.get('Highlights', {}) or {}; ss = j.get('SharesStats', {}) or {}
    r['cap_attuale'] = hl.get('MarketCapitalization'); r['azioni_attuali'] = ss.get('SharesOutstanding')
    r['ricavi_ttm'] = hl.get('RevenueTTM')
    r['esito'] = 'bilanci presenti' if (r['CE_a_n'] or r['CE_q_n']) else 'scheda vuota (solo anagrafica)'
    rows.append(r)
R = pd.DataFrame(rows)
R.to_csv(f'{OUT}/verifica_bilanci_delisted.csv', index=False)
pd.set_option('display.width', 250)
print(R[['t', 'nome', 'data_uscita', 'esito', 'CE_a_n', 'CE_a_da', 'CE_a_a', 'CE_q_n', 'SP_a_n', 'CF_a_n', 'azioni_storico_n', 'utili_stime_n']].to_string())
