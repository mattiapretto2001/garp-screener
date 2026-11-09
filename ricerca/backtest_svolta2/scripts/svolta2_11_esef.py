# Prova di fattibilita' dati europei: filings.xbrl.org (bilanci ESEF in XBRL, API JSON).
# Per 10 societa': elenco depositi, scarica l'xBRL-JSON di ciascuno, estrae ricavi / utile lordo / risultato operativo
# con la durata del periodo (12 o 6 mesi). Uscita: results/svolta2_esef.csv e results/svolta2_esef.txt
# Uso: python -I svolta2_11_esef.py  (i JSON scaricati vanno in ../dl_esef, separati dagli script)
# Nota: in xBRL-JSON la fine periodo e' esclusiva (es. 2026-01-01 = esercizio chiuso il 31/12/2025).
import requests, json, os, time, urllib.parse, pandas as pd
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
DL = f'{BASE}/dl_esef'; os.makedirs(DL, exist_ok=True)
H = 'https://filings.xbrl.org'
UA = {'User-Agent': 'garp-screener research contact: research@example.com'}
NAMES = {'ASML': '%ASML%', 'AIXTRON': '%AIXTRON%', 'Heijmans': '%Heijmans%', 'CAF': '%Auxiliar de Ferrocarriles%',
         'Orion': 'Orion Oyj%', 'Prysmian': '%Prysmian%', 'Siemens Energy': '%Siemens Energy%', 'Basler': 'Basler%',
         'BESI': '%BE Semiconductor%', 'Infineon': '%Infineon%'}
CONC = {'ricavi': ['ifrs-full:Revenue', 'ifrs-full:RevenueFromContractsWithCustomers'],
        'utile_lordo': ['ifrs-full:GrossProfit'],
        'costo_venduto': ['ifrs-full:CostOfSales'],
        'ris_operativo': ['ifrs-full:ProfitLossFromOperatingActivities']}
def get(url, **kw):
    for a in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            if r.status_code == 200: return r
        except Exception: pass
        time.sleep(3)
    return None
rows, info = [], []
for lab, pat in NAMES.items():
    flt = json.dumps([{'name': 'entity.name', 'op': 'ilike', 'val': pat}])
    r = get(f'{H}/api/filings?filter={urllib.parse.quote(flt)}&page[size]=100')
    fl = r.json()['data'] if r else []
    info.append(f'{lab}: {len(fl)} depositi ({", ".join(sorted(set(f["attributes"]["period_end"] for f in fl)))})')
    for f in fl:
        a = f['attributes']
        if not a.get('json_url'): continue
        fn = f'{DL}/{lab.replace(" ", "_")}_{a["period_end"]}_{f["id"]}.json'
        if not os.path.exists(fn):
            rr = get(H + a['json_url'])
            if rr is None: continue
            open(fn, 'wb').write(rr.content)
        try: j = json.load(open(fn))
        except Exception: continue
        for fid, fact in j.get('facts', {}).items():
            d = fact.get('dimensions', {})
            c = d.get('concept')
            k = next((kk for kk, v in CONC.items() if c in v), None)
            if k is None: continue
            if any(x for x in d if x not in ('concept', 'entity', 'period', 'unit', 'language')): continue  # solo totali, senza segmenti
            per = d.get('period', '')
            if '/' not in per: continue
            s, e = per.split('/')
            mesi = round((pd.Timestamp(e[:10]) - pd.Timestamp(s[:10])).days / 30.4)
            try: v = float(fact.get('value'))
            except Exception: continue
            rows.append(dict(societa=lab, deposito=a['period_end'], campo=k, concetto=c, inizio=s[:10], fine=e[:10], mesi=mesi,
                             valore=v, unita=d.get('unit')))
    time.sleep(1)
D = pd.DataFrame(rows).drop_duplicates(['societa', 'campo', 'inizio', 'fine'])
D.to_csv(f'{BASE}/results/svolta2_esef.csv', index=False)
out = info + ['']
for lab in NAMES:
    x = D[D.societa == lab] if len(D) else D
    if not len(x): out.append(f'{lab}: nessun dato estratto'); continue
    parts = []
    for k in CONC:
        y = x[x.campo == k]
        if not len(y): parts.append(f'{k}: assente'); continue
        parts.append(f'{k}: {len(y)} periodi, durate {sorted(y.mesi.unique().tolist())} mesi, {y.fine.min()}..{y.fine.max()}')
    out.append(f'{lab}: ' + '; '.join(parts))
open(f'{BASE}/results/svolta2_esef.txt', 'w').write('\n'.join(out)); print('\n'.join(out))
