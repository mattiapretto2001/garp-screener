# Prova di fattibilita': societa' estere (tassonomia ifrs-full) nel bulk SEC companyfacts.zip.
# Per ogni societa' con fatti ifrs-full: moduli (20-F/40-F/6-K), durate dei periodi dei ricavi, presenza di utile lordo e
# risultato operativo, anni coperti. Uscita: cache/ifrs_summary.csv e results/svolta2_ifrs.txt
# Uso: python -I svolta2_10_ifrs.py percorso/companyfacts.zip
import zipfile, json, sys, os, pandas as pd, numpy as np
from multiprocessing import Pool
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
ZIP = sys.argv[1]
REV = ['Revenue', 'RevenueFromContractsWithCustomers']
GP = ['GrossProfit']; OP = ['ProfitLossFromOperatingActivities']
def dur(f):
    if not f.get('start'): return None
    d = (pd.Timestamp(f['end']) - pd.Timestamp(f['start'])).days
    return 3 if 80 <= d <= 100 else 6 if 170 <= d <= 195 else 9 if 260 <= d <= 285 else 12 if 350 <= d <= 380 else None
def facts(ifrs, tags):
    out = []
    for t in tags:
        if t in ifrs:
            for u, lst in ifrs[t]['units'].items():
                out += lst
    return out
def work(name):
    z = zipfile.ZipFile(ZIP)
    try: j = json.loads(z.read(name))
    except Exception: return None
    ifrs = j.get('facts', {}).get('ifrs-full')
    if not ifrs: return None
    rv = facts(ifrs, REV); gp = facts(ifrs, GP); op = facts(ifrs, OP)
    forms = sorted(set(f.get('form', '') for t in ifrs.values() for lst in t['units'].values() for f in lst))
    d = [dur(f) for f in rv]
    yrs = sorted(set(pd.Timestamp(f['end']).year for f in rv if dur(f) == 12))
    # periodi infrannuali depositati entro 1 anno dalla fine (non solo comparativi)
    q = [f for f in rv if dur(f) in (3, 6, 9)]
    return dict(cik=j.get('cik'), nome=j.get('entityName'), moduli='|'.join(forms), n_ricavi=len(rv),
                ricavi_12m=d.count(12), ricavi_6m=d.count(6), ricavi_3m=d.count(3), ricavi_9m=d.count(9),
                ha_utile_lordo=len(gp) > 0, ha_ris_operativo=len(op) > 0, anno_min=min(yrs) if yrs else np.nan,
                anno_max=max(yrs) if yrs else np.nan, n_anni=len(yrs),
                forms_infrannuali='|'.join(sorted(set(f.get('form', '') for f in q))),
                usd=any(u == 'USD' for t in REV if t in ifrs for u in ifrs[t]['units']))
if __name__ == '__main__':
    names = [n for n in zipfile.ZipFile(ZIP).namelist() if n.endswith('.json')]
    with Pool(2) as p: R = [x for x in p.imap_unordered(work, names, chunksize=50) if x]
    D = pd.DataFrame(R); D.to_csv(f'{BASE}/cache/ifrs_summary.csv', index=False)
    uni = pd.read_csv(f'{BASE}/cache/universe.csv'); D['quotata_NYSE_Nasdaq'] = D.cik.isin(uni.cik)
    rec = D[D.anno_max >= 2024]
    o = [f'Societa con fatti ifrs-full: {len(D)}; con ricavi annui recenti (anno >= 2024): {len(rec)}; di cui quotate NYSE/Nasdaq oggi: {rec.quotata_NYSE_Nasdaq.sum()}',
         f'Moduli: 20-F in {D.moduli.str.contains("20-F").sum()}, 40-F in {D.moduli.str.contains("40-F").sum()}, 6-K in {D.moduli.str.contains("6-K").sum()}',
         f'Fra le recenti: con utile lordo {rec.ha_utile_lordo.mean():.0%}, con risultato operativo {rec.ha_ris_operativo.mean():.0%}',
         f'Fra le recenti: con almeno un dato ricavi a 3 mesi {(rec.ricavi_3m > 0).mean():.0%}, a 6 mesi {(rec.ricavi_6m > 0).mean():.0%}; con >=8 dati a 3 mesi {(rec.ricavi_3m >= 8).mean():.0%}',
         f'Anni di ricavi annui (mediana, recenti): {rec.n_anni.median():.0f}; primo anno mediano {rec.anno_min.median():.0f}',
         'Moduli dei dati infrannuali (recenti): ' + str(rec.forms_infrannuali.value_counts().head(6).to_dict())]
    open(f'{BASE}/results/svolta2_ifrs.txt', 'w').write('\n'.join(o)); print('\n'.join(o))
