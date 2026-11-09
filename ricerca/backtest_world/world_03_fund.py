# Fase 3: fondamentali (10 crediti l'uno). Si tengono solo le serie utili; il JSON completo non viene salvato.
import sys, pickle, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from world_common import *
STOP = 79000  # tetto di sicurezza crediti giornalieri
INC = ['totalRevenue', 'netIncome', 'netIncomeApplicableToCommonShares', 'ebitda', 'operatingIncome']
BAL = ['totalStockholderEquity', 'shortLongTermDebtTotal', 'shortTermDebt', 'longTermDebt', 'shortLongTermDebt', 'longTermDebtTotal',
       'cash', 'cashAndShortTermInvestments', 'commonStockSharesOutstanding', 'totalAssets']
CF = ['totalCashFromOperatingActivities', 'capitalExpenditures', 'freeCashFlow']


def tab(d, cols):
    if not isinstance(d, dict) or not d: return None
    rows = []
    for k, v in d.items():
        if not isinstance(v, dict): continue
        r = {'date': v.get('date') or k, 'filing_date': v.get('filing_date'), 'cur': v.get('currency_symbol')}
        for c in cols: r[c] = pd.to_numeric(v.get(c), errors='coerce')
        rows.append(r)
    if not rows: return None
    x = pd.DataFrame(rows)
    x['date'] = pd.to_datetime(x.date, errors='coerce'); x['filing_date'] = pd.to_datetime(x.filing_date, errors='coerce')
    return x.dropna(subset=['date']).sort_values('date').reset_index(drop=True)


def extract(j):
    G = j.get('General', {}) or {}
    F = j.get('Financials', {}) or {}
    g = {k: G.get(k) for k in ['Code', 'Name', 'Exchange', 'CurrencyCode', 'CountryISO', 'ISIN', 'Sector', 'GicSector', 'Industry',
                                'GicIndustry', 'IsDelisted', 'DelistedDate', 'IPODate', 'Type']}
    out = {'gen': g}
    for key, sec, cols in [('inc', 'Income_Statement', INC), ('bal', 'Balance_Sheet', BAL), ('cf', 'Cash_Flow', CF)]:
        s = F.get(sec, {}) or {}
        out[key + '_q'] = tab(s.get('quarterly'), cols); out[key + '_y'] = tab(s.get('yearly'), cols)
    os_ = (j.get('outstandingShares') or {}).get('quarterly')
    if isinstance(os_, dict):
        out['sh'] = pd.Series({pd.Timestamp(v['dateFormatted']): v.get('shares') for v in os_.values() if v.get('dateFormatted')}).sort_index()
    eh = (j.get('Earnings') or {}).get('History')
    if isinstance(eh, dict):  # date di pubblicazione dichiarate (solo per controllo)
        out['rep'] = pd.Series({pd.Timestamp(k): v.get('reportDate') for k, v in eh.items() if v.get('reportDate')})
    return out


if __name__ == '__main__':
    C = pd.read_csv(f'{BASE}/res/candidates.csv')
    fn = f'{BASE}/fund/fund.pkl'
    D = pickle.load(open(fn, 'rb')) if os.path.exists(fn) else {}
    todo = [t for t in C.t if t not in D]
    print('da scaricare', len(todo), 'crediti ora', usage(), flush=True)
    def one(t):
        j = get(f'https://eodhd.com/api/fundamentals/{t}?fmt=json')
        if not j or not isinstance(j, dict): return t, None
        try: return t, extract(j)
        except Exception as e: return t, {'err': str(e)}
    for i in range(0, len(todo), 200):
        u = usage()
        if u and u > STOP - 2000: print('STOP crediti', u); break
        with ThreadPoolExecutor(10) as P:
            for t, d in P.map(one, todo[i:i + 200]): D[t] = d
        pickle.dump(D, open(fn, 'wb'))
        print(i + 200, 'fatti; crediti', usage(), flush=True)
