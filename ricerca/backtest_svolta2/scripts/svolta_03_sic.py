# Codice SIC per CIK dalle API submissions SEC (riprendibile, <=8 richieste/s)
import requests, pandas as pd, os, time, json
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
UA = {'User-Agent': 'garp-screener research contact: research@example.com'}
fn = f'{BASE}/cache/sic.json'
done = json.load(open(fn)) if os.path.exists(fn) else {}
ciks = pd.read_csv(f'{BASE}/cache/universe.csv').cik.tolist()
s = requests.Session()
for i, c in enumerate(ciks):
    if str(c) in done: continue
    t0 = time.time()
    for a in range(3):
        try:
            r = s.get(f'https://data.sec.gov/submissions/CIK{c:010d}.json', headers=UA, timeout=30)
            if r.status_code == 200:
                j = r.json(); done[str(c)] = [j.get('sic'), j.get('sicDescription')]; break
            time.sleep(2)
        except Exception: time.sleep(2)
    if i % 200 == 0:
        json.dump(done, open(fn, 'w')); print(i, flush=True)
    time.sleep(max(0, 0.13 - (time.time() - t0)))
json.dump(done, open(fn, 'w')); print('fine', len(done))
