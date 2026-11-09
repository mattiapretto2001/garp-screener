# Prezzi yfinance a blocchi da 100 (riprendibile): Close (rettificato split), Adj Close, split
import yfinance as yf, pandas as pd, os, time, sys, pickle
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
OUT = f'{BASE}/cache/prices'; os.makedirs(OUT, exist_ok=True)
tick = sorted(set(pd.read_csv(f'{BASE}/cache/universe.csv').ticker.dropna()) | {'SPY'})
B = 100
for i in range(0, len(tick), B):
    fn = f'{OUT}/blk_{i//B:03d}.pkl'
    if os.path.exists(fn): continue
    blk = tick[i:i+B]
    for att in range(4):
        try:
            d = yf.download(blk, start='2010-06-01', end='2026-11-04', auto_adjust=False, actions=True,
                            progress=False, threads=True, group_by='column')
            break
        except Exception as e:
            print('err', e); time.sleep(30)
    keep = {k: d[k] for k in ['Close', 'Adj Close', 'Stock Splits'] if k in d.columns.get_level_values(0)}
    got = keep['Close'].notna().sum().gt(0).sum()
    print(i//B, 'ok', got, '/', len(blk), flush=True)
    if got < len(blk) * 0.3 and att < 3:
        print('pochi dati, pausa'); time.sleep(60)
    pickle.dump(keep, open(fn, 'wb'))
    time.sleep(3)
