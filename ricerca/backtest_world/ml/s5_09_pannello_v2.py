# Storico 2000-2011, 08/11/2026: pannello trimestrale USA v2 (fine trimestre 12/1999 - 09/2025), con le societa' uscite che
# mancavano. Stesso calcolo di s5_03_pannello.py (funzione one: prezzo, scambi mediani 63 giorni, prezzo/massimo 52 settimane,
# momentum, volatilita', rendimento a 12 e 3 mesi con la regola di uscita, azioni e capitalizzazione dove ci sono i bilanci).
# Serie:
#   A = eod_lungo/US.pkl.gz (nostri prezzi dal 1998, 4.926 titoli)
#   D = storico5/raw/prezzi_us (3.604 serie del 07/11, codici liquidi nelle istantanee)
#   V = le 214 serie della verifica avversariale del 07/11 (ora dentro eod_lungo/US_uscite.pkl.gz, origine "avv")
#   W = le serie scaricate oggi con s5_02 v2 (eod_lungo/US_uscite.pkl.gz, origine "oggi")
# Nomi, borsa e flag "uscita" dalla lista EODHD COMPLETA (anche fuori borsa): la v1 usava solo le borse principali.
# Per i titoli che oggi sono fuori borsa (OTC/PINK) tengo solo le date fino al 30/09/2011: non so quando hanno lasciato
# New York, e dopo il 2011 entrerebbero nel confronto 2012-2025 con scambi fuori borsa (es. Fannie Mae e Freddie Mac nel 2013-14).
# Colonna a_tetto: il prezzo corretto di EODHD e' bloccato a 1.000.000 vicino alla data (riga da non usare: vedi s5_10).
# Nessuna chiamata EODHD. Scrive storico5/pannello_prezzi_us_v2.pkl.
import os, sys, json, glob, warnings, pandas as pd, numpy as np
from multiprocessing import Pool
warnings.filterwarnings('ignore')
from s5_common import OUT, ML, BW
sys.path.insert(0, BW); sys.path.insert(0, ML)
import s5_03_pannello as P3
from world_common import US_EX
EL = f'{ML}/eod_lungo'
FINE_OTC = pd.Timestamp('2011-09-30')


def lista_completa():
    out = []
    for d in (0, 1):
        for x in json.load(open(f'{BW}/lists/US_{d}.json')):
            x['delisted'] = d; out.append(x)
    return pd.DataFrame(out).drop_duplicates('Code', keep='first').set_index('Code')


def series_pool():
    pool, src = P3.series_pool()                 # A e D, come nella v1
    N = pd.read_pickle(f'{EL}/US_uscite.pkl.gz'); N['t'] = N.t.astype(str)
    orig = json.load(open(f'{EL}/_origine_US_uscite.json'))
    for t, x in N.groupby('t', sort=False):
        if t in pool: continue
        pool[t] = x.drop(columns='t').set_index('date'); src[t] = 'V' if orig.get(t) == 'avv' else 'W'
    return pool, src


if __name__ == '__main__':
    pool, src = series_pool()
    print('serie', len(pool), pd.Series(src).value_counts().to_dict(), flush=True)
    P3.load_fd()
    with Pool(4) as P:
        out = []
        for k, rr in enumerate(P.imap_unordered(P3.one, list(pool.items()), chunksize=20)):
            out += rr
            if k % 4000 == 0: print(k, flush=True)
    D = pd.DataFrame(out)
    S = lista_completa()
    last = {t: x.index[-1] for t, x in pool.items() if len(x)}
    first = {t: x.index[0] for t, x in pool.items() if len(x)}
    D['src'] = D.t.map(src); D['last'] = D.t.map(last); D['first'] = D.t.map(first)
    D['name'] = D.t.map(S.Name); D['dl_list'] = D.t.map(S.delisted); D['borsa'] = D.t.map(S.Exchange)
    D['fuori_borsa'] = D.borsa.notna() & ~D.borsa.isin(US_EX)
    D['codice_old'] = D.t.str.contains(r'_old\d*$', regex=True)
    D['excl'] = D.name.fillna('').str.contains(P3.EXCLPAT, case=False, regex=True)
    D['uscita_pre2011'] = D['last'] < pd.Timestamp('2011-06-30')
    D['cap'] = D.sh * D.spx
    # prezzo corretto bloccato al tetto di EODHD (1.000.000: raggruppamenti enormi) da un anno prima a 12 mesi dopo la data:
    # rendimenti, massimo a 52 settimane e volatilita' di quella riga non valgono
    capd = {t: x.index[x.a.values >= 999000] for t, x in pool.items() if len(x) and x.a.max() >= 999000}
    D['a_tetto'] = False
    m = D.t.isin(capd.keys())
    D.loc[m, 'a_tetto'] = [bool(((capd[t] >= d - pd.Timedelta(days=366)) & (capd[t] <= d + pd.Timedelta(days=376))).any())
                           for t, d in zip(D.t[m], D.date[m])]
    print('serie con prezzo corretto al tetto:', len(capd), '| righe toccate:', int(D.a_tetto.sum()), flush=True)
    n0 = len(D)
    D = D[~(D.fuori_borsa & D.src.isin(['V', 'W']) & (D.date > FINE_OTC))].reset_index(drop=True)
    print('righe tolte (fuori borsa dopo 09/2011, solo serie nuove):', n0 - len(D), flush=True)
    D.to_pickle(f'{OUT}/pannello_prezzi_us_v2.pkl')
    print(D.shape, D.groupby('src').size().to_dict())
    print(D.groupby(D.date.dt.year).size().to_dict())
