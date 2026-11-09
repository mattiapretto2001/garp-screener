# Universo: ticker NYSE/Nasdaq <-> CIK (SEC company_tickers_exchange.json)
import requests, json, pandas as pd, os, sys
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
UA = {'User-Agent': 'garp-screener research contact: research@example.com'}
r = requests.get('https://www.sec.gov/files/company_tickers_exchange.json', headers=UA, timeout=60)
j = r.json()
df = pd.DataFrame(j['data'], columns=j['fields'])
df = df[df.exchange.isin(['NYSE', 'Nasdaq'])].copy()
df['ticker'] = df.ticker.str.replace('.', '-', regex=False)
# una riga per CIK: il ticker piu' corto (classe principale)
df = df.sort_values(['cik', 'ticker'], key=lambda s: s.str.len() if s.name == 'ticker' else s).drop_duplicates('cik')
df.to_csv(f'{BASE}/cache/universe.csv', index=False)
print(len(df), 'CIK')
