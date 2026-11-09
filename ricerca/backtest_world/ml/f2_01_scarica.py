# F2 passo 1 (09/11/2026): scarica gli "Insider Transactions Data Sets" della SEC (Form 3/4/5, trimestrali dal 2006),
# tiene SOLO le righe non derivate con codice P (acquisto sul mercato aperto) di Form 4 e 5 (emendamenti 4/A, 5/A esclusi),
# con i dati del dichiarante (relazione: Director/Officer/TenPercentOwner/Other). Ogni zip viene cancellato dopo l'estrazione.
# User-Agent generico come da regole SEC. Uscita: ml/f2/p_<anno>q<n>.pkl (compatto).
import os, sys, io, time, zipfile, urllib.request, pandas as pd
ML = os.path.dirname(os.path.abspath(__file__)); OUT = f'{ML}/f2'; os.makedirs(OUT, exist_ok=True)
RAW = os.path.join(os.path.dirname(os.path.dirname(ML)), 'sec_raw'); os.makedirs(RAW, exist_ok=True)
UA = 'garp-research contact@example.com'
URL = 'https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip'


def rd(z, name, cols):
    with z.open(name) as f:
        return pd.read_csv(f, sep='\t', dtype=str, usecols=cols, quoting=3, on_bad_lines='skip', encoding_errors='replace')


def one(q):
    out = f'{OUT}/p_{q}.pkl'
    if os.path.exists(out): return 'gia'
    fz = f'{RAW}/{q}.zip'
    for i in range(4):
        try:
            req = urllib.request.Request(URL.format(q=q), headers={'User-Agent': UA, 'Accept-Encoding': 'identity'})
            with urllib.request.urlopen(req, timeout=300) as r, open(fz, 'wb') as w: w.write(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code == 404: return '404'
            time.sleep(5 + 10 * i)
        except Exception:
            time.sleep(5 + 10 * i)
    else:
        return 'ERR'
    z = zipfile.ZipFile(fz)
    nm = {n.split('/')[-1]: n for n in z.namelist()}
    T = rd(z, nm['NONDERIV_TRANS.tsv'], ['ACCESSION_NUMBER', 'SECURITY_TITLE', 'TRANS_DATE', 'TRANS_CODE', 'TRANS_SHARES',
                                          'TRANS_PRICEPERSHARE', 'TRANS_ACQUIRED_DISP_CD', 'SHRS_OWND_FOLWNG_TRANS', 'DIRECT_INDIRECT_OWNERSHIP'])
    ntot = len(T)
    T = T[T.TRANS_CODE == 'P']
    S = rd(z, nm['SUBMISSION.tsv'], ['ACCESSION_NUMBER', 'FILING_DATE', 'PERIOD_OF_REPORT', 'DOCUMENT_TYPE', 'ISSUERCIK', 'ISSUERNAME', 'ISSUERTRADINGSYMBOL'])
    S = S[S.DOCUMENT_TYPE.isin(['4', '5'])]
    O = rd(z, nm['REPORTINGOWNER.tsv'], ['ACCESSION_NUMBER', 'RPTOWNERCIK', 'RPTOWNERNAME', 'RPTOWNER_RELATIONSHIP', 'RPTOWNER_TITLE'])
    O = O[O.ACCESSION_NUMBER.isin(T.ACCESSION_NUMBER)]
    # piu' dichiaranti nello stesso modulo (es. dirigente + suo veicolo): una riga per modulo, con l'insieme delle relazioni
    O = O.sort_values('RPTOWNERCIK').groupby('ACCESSION_NUMBER').agg(owner_cik=('RPTOWNERCIK', 'first'), owner=('RPTOWNERNAME', 'first'),
                                                                      rel=('RPTOWNER_RELATIONSHIP', lambda s: ','.join(sorted(set(','.join(s.fillna('')).split(',')) - {''}))),
                                                                      title=('RPTOWNER_TITLE', lambda s: ';'.join(s.dropna().unique())), n_owners=('RPTOWNERCIK', 'size')).reset_index()
    D = T.merge(S, on='ACCESSION_NUMBER').merge(O, on='ACCESSION_NUMBER', how='left')
    D.columns = [c.lower() for c in D.columns]
    for c in ('trans_shares', 'trans_pricepershare', 'shrs_ownd_folwng_trans'): D[c] = pd.to_numeric(D[c], errors='coerce')
    for c in ('trans_date', 'filing_date', 'period_of_report'): D[c] = pd.to_datetime(D[c], format='%d-%b-%Y', errors='coerce')
    D['q'] = q
    D.to_pickle(out)
    z.close(); os.remove(fz)
    return f'righe NONDERIV {ntot}, P tenute {len(D)}'


if __name__ == '__main__':
    qs = [f'{y}q{k}' for y in range(2006, 2027) for k in range(1, 5)]
    for q in qs:
        t0 = time.time(); r = one(q); print(q, r, f'{time.time() - t0:.0f}s', flush=True); time.sleep(1)
