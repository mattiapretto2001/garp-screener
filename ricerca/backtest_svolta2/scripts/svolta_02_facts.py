# Estrazione point-in-time da companyfacts.zip (SEC). Per ogni trimestre: PRIMO valore depositato e sua data 'filed'.
# Flussi a 3 mesi diretti o per differenza (6M-3M, 9M-6M, FY-9M). Uscita: cache/quarters.pkl (una riga per cik x trimestre)
# e cache/surv.csv (misura del bias di sopravvivenza). Uso: python svolta_02_facts.py percorso/companyfacts.zip
import zipfile, json, sys, os, pandas as pd, numpy as np
from multiprocessing import Pool
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
ZIP = sys.argv[1]
FLOW = {
 'rev': ['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax',
         'SalesRevenueNet','SalesRevenueGoodsNet','SalesRevenueServicesNet','RevenuesNetOfInterestExpense'],
 'gp': ['GrossProfit'],
 'cogs': ['CostOfRevenue','CostOfGoodsAndServicesSold','CostOfGoodsSold','CostOfServices','CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization'],
 'opinc': ['OperatingIncomeLoss'],
 'ni': ['NetIncomeLoss','ProfitLoss','NetIncomeLossAvailableToCommonStockholdersBasic'],
 'cfo': ['NetCashProvidedByUsedInOperatingActivities','NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'],
 'capex': ['PaymentsToAcquirePropertyPlantAndEquipment','PaymentsToAcquireProductiveAssets'],
 'da': ['DepreciationDepletionAndAmortization','DepreciationAndAmortization','DepreciationAmortizationAndAccretionNet','Depreciation'],
 'acq': ['PaymentsToAcquireBusinessesNetOfCashAcquired'],
}
PERSH = {'eps': ['EarningsPerShareDiluted','EarningsPerShareBasicAndDiluted','EarningsPerShareBasic']}  # EPS: flusso per azione
AVG = {'dilsh': ['WeightedAverageNumberOfDilutedSharesOutstanding','WeightedAverageNumberOfShareOutstandingBasicAndDiluted']}
INST = {
 'cash': ['CashAndCashEquivalentsAtCarryingValue','CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents','Cash'],
 'sti': ['ShortTermInvestments','MarketableSecuritiesCurrent','AvailableForSaleSecuritiesDebtSecuritiesCurrent','AvailableForSaleSecuritiesCurrent'],
 'ltd_nc': ['LongTermDebtNoncurrent','LongTermDebtAndCapitalLeaseObligations','ConvertibleNotesPayableNoncurrent'],
 'ltd': ['LongTermDebt'],
 'std': ['LongTermDebtCurrent','DebtCurrent','LongTermDebtAndCapitalLeaseObligationsCurrent'],
 'stb': ['ShortTermBorrowings'],
 'eq': ['StockholdersEquity','StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
}
def snap(d):  # data di fine periodo -> fine mese piu' vicino (gestisce anni da 52-53 settimane)
    return (d - pd.Timedelta(days=15)) + pd.offsets.MonthEnd(0)
def mi(ts): return ts.year * 12 + ts.month
def facts_of(us, tags, unit):
    rows = []
    for pri, t in enumerate(tags):
        if t not in us: continue
        for u, lst in us[t]['units'].items():
            if u != unit: continue
            for f in lst:
                rows.append((pri, f.get('start'), f['end'], f['filed'], f['val'], f.get('form', '')))
    if not rows: return None
    df = pd.DataFrame(rows, columns=['pri', 'start', 'end', 'filed', 'val', 'form'])
    df['end'] = pd.to_datetime(df.end, errors='coerce'); df['filed'] = pd.to_datetime(df.filed, errors='coerce')
    df = df.dropna(subset=['end', 'filed'])
    df['m'] = df.end.map(snap).map(mi)
    return df
def flow_q(df, summable=True):
    """dizionario m -> (valore trimestrale, filed)"""
    df = df.dropna(subset=['start']).copy()
    df['start'] = pd.to_datetime(df.start, errors='coerce'); df = df.dropna(subset=['start'])
    dur = (df.end - df.start).dt.days
    df['L'] = np.select([dur.between(80, 100), dur.between(170, 195), dur.between(260, 285), dur.between(350, 380)], [3, 6, 9, 12], 0)
    df = df[df.L > 0].sort_values(['filed', 'pri'])
    first = df.drop_duplicates(['m', 'L'])  # primo depositato per (fine periodo, durata)
    D = {(r.m, r.L): (r.val, r.filed) for r in first.itertuples()}
    out = {}
    for (m, L), (v, f) in D.items():
        if L == 3: out[m] = (v, f)
    if summable:
        for (m, L), (v, f) in D.items():
            if L == 3 or m in out: continue
            prev = D.get((m - 3, L - 3))
            if prev is not None:
                out[m] = (v - prev[0], max(f, prev[1]))
    return out
def inst_q(df):
    df = df.sort_values(['filed', 'pri']).drop_duplicates('m')
    return {r.m: (r.val, r.filed) for r in df.itertuples()}
def work(name):
    z = zipfile.ZipFile(ZIP)
    try: j = json.loads(z.read(name))
    except Exception: return None
    cik = int(j.get('cik', 0) or 0)
    fa = j.get('facts', {}); us = fa.get('us-gaap', {}); dei = fa.get('dei', {})
    res = {}; surv = {}
    for k, tags in FLOW.items():
        df = facts_of(us, tags, 'USD')
        if df is not None:
            res[k] = flow_q(df)
            if k == 'rev':  # ricavi annui per misura sopravvivenza
                d = df.dropna(subset=['start']).copy(); d['start'] = pd.to_datetime(d.start, errors='coerce')
                d = d[((d.end - d.start).dt.days).between(350, 380)]
                for y in (2015, 2019):
                    v = d[d.end.dt.year == y].val
                    surv[y] = v.max() if len(v) else np.nan
    for k, tags in PERSH.items():
        df = facts_of(us, tags, 'USD/shares')
        if df is not None: res[k] = flow_q(df, summable=True)
    for k, tags in AVG.items():
        df = facts_of(us, tags, 'shares')
        if df is not None:
            q = flow_q(df, summable=False)
            # se manca il 3M usa qualunque durata con stessa fine
            d2 = df.sort_values(['filed', 'pri']).drop_duplicates('m')
            for r in d2.itertuples():
                if r.m not in q: q[r.m] = (r.val, r.filed)
            res[k] = q
    for k, tags in INST.items():
        df = facts_of(us, tags, 'USD')
        if df is not None: res[k] = inst_q(df)
    # azioni in copertina (dei), con data di deposito
    cov = []
    for t in ['EntityCommonStockSharesOutstanding']:
        if t in dei:
            for u, lst in dei[t]['units'].items():
                for f in lst: cov.append((f['filed'], f['val'], f['end']))
    if not res.get('rev'): return None
    ms = sorted(set().union(*[set(v) for v in res.values()]))
    rows = []
    for m in ms:
        r = {'cik': cik, 'm': m}
        for k, d in res.items():
            if m in d: r[k] = d[m][0]; r[k + '_f'] = d[m][1]
        rows.append(r)
    covdf = pd.DataFrame(cov, columns=['filed', 'val', 'end']); covdf['cik'] = cik
    covdf = covdf.groupby('filed', as_index=False).agg(val=('val', 'sum'), cik=('cik', 'first'))  # piu' classi: somma
    return pd.DataFrame(rows), covdf, (cik, surv.get(2015, np.nan), surv.get(2019, np.nan))
if __name__ == '__main__':
    uni = set(pd.read_csv(f'{BASE}/cache/universe.csv').cik)
    names = [n for n in zipfile.ZipFile(ZIP).namelist() if n.endswith('.json')]
    print(len(names), 'file')
    Q, C, SV = [], [], []
    with Pool(4) as p:
        for i, out in enumerate(p.imap_unordered(work, names, chunksize=20)):
            if out is None: continue
            q, c, s = out
            SV.append(s)
            if s[0] in uni:
                Q.append(q); C.append(c)
            if i % 2000 == 0: print(i, flush=True)
    Q = pd.concat(Q, ignore_index=True); C = pd.concat(C, ignore_index=True)
    Q.to_pickle(f'{BASE}/cache/quarters.pkl'); C.to_pickle(f'{BASE}/cache/cover_shares.pkl')
    pd.DataFrame(SV, columns=['cik', 'rev2015', 'rev2019']).assign(in_univ=lambda d: d.cik.isin(uni)).to_csv(f'{BASE}/cache/surv.csv', index=False)
    print('righe', len(Q), 'cik', Q.cik.nunique())
