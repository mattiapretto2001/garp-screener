# f4_03: quota degli insider (amministratori + dirigenti) point-in-time per le societa' USA, dai dati pubblici SEC
# "Insider Transactions Data Sets" (moduli 3/4/5, 2009-2026). Per ogni persona: azioni possedute dichiarate nell'ultimo
# modulo depositato prima della data (solo titoli azionari ordinari, dirette + indirette), valido al massimo 3 anni.
# Quota = somma sulle persone / azioni in circolazione (sh della matrice). Collegamento per simbolo di borsa al deposito.
import os, glob, zipfile, io, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
SEC = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'f4dl', 'sec')
rows = []
ZS = [] if os.path.exists(f'{HERE}/f4_out/sec_moduli.pkl') else sorted(glob.glob(f'{SEC}/*_form345.zip'))
for z in ZS:
    Z = zipfile.ZipFile(z)
    rd = lambda n, c: pd.read_csv(Z.open(n), sep='\t', usecols=c, dtype=str, quoting=3, on_bad_lines='skip')
    S = rd('SUBMISSION.tsv', ['ACCESSION_NUMBER', 'FILING_DATE', 'DOCUMENT_TYPE', 'ISSUERCIK', 'ISSUERTRADINGSYMBOL'])
    O = rd('REPORTINGOWNER.tsv', ['ACCESSION_NUMBER', 'RPTOWNERCIK', 'RPTOWNER_RELATIONSHIP'])
    c = ['ACCESSION_NUMBER', 'SECURITY_TITLE', 'SHRS_OWND_FOLWNG_TRANS', 'DIRECT_INDIRECT_OWNERSHIP', 'NATURE_OF_OWNERSHIP']
    T = rd('NONDERIV_TRANS.tsv', c); H = rd('NONDERIV_HOLDING.tsv', c)
    X = pd.concat([T, H], ignore_index=True)        # ordine: transazioni nell'ordine del modulo, poi posizioni
    tit = X.SECURITY_TITLE.fillna('').str.lower()
    X = X[~tit.str.contains('prefer|warrant|unit|note|debenture|option|right|depositary|restricted stock unit|rsu|phantom')]
    X['sh'] = pd.to_numeric(X.SHRS_OWND_FOLWNG_TRANS, errors='coerce')
    X['k'] = X.DIRECT_INDIRECT_OWNERSHIP.fillna('D') + '|' + X.NATURE_OF_OWNERSHIP.fillna('').str.lower().str[:40] + '|' + tit.str[:30]
    X = X.dropna(subset=['sh']).groupby(['ACCESSION_NUMBER', 'k']).sh.last().groupby(level=0).sum().rename('hold')
    # una sola persona per modulo: la prima con ruolo di amministratore o dirigente (i moduli congiunti sono spesso fondi)
    rel = O.RPTOWNER_RELATIONSHIP.fillna('')
    O = O[rel.str.contains('Director|Officer')].drop_duplicates('ACCESSION_NUMBER')
    D = S.merge(O, on='ACCESSION_NUMBER').merge(X, left_on='ACCESSION_NUMBER', right_index=True, how='left')
    D = D[D.DOCUMENT_TYPE.isin(['3', '4', '5', '3/A', '4/A', '5/A'])]
    # modulo 3 senza titoli = 0 azioni
    D['hold'] = D.hold.fillna(0.0)
    rows.append(D[['FILING_DATE', 'ISSUERCIK', 'ISSUERTRADINGSYMBOL', 'RPTOWNERCIK', 'hold']])
    print(os.path.basename(z), len(D), flush=True)
if rows:   # prima esecuzione: lettura degli zip SEC (la cache sec_moduli.pkl evita di rifarla)
    A = pd.concat(rows, ignore_index=True)
    A['fd'] = pd.to_datetime(A.FILING_DATE, format='%d-%b-%Y', errors='coerce')
    A['sym'] = A.ISSUERTRADINGSYMBOL.fillna('').str.upper().str.strip().str.replace(r'[^A-Z0-9]', '.', regex=True)
    A = A.dropna(subset=['fd']).sort_values('fd')
    A.to_pickle(f'{HERE}/f4_out/sec_moduli.pkl')
else:
    A = pd.read_pickle(f'{HERE}/f4_out/sec_moduli.pkl')
# simbolo -> CIK (il CIK piu' frequente per quel simbolo e quell'anno)
F = pd.read_pickle(f'{HERE}/features_v3.pkl')[['t', 'date', 'ex', 'sh', 'px', 'mcap']]
F = F[F.ex == 'US'].copy(); F['code'] = F.t.str[:-3].str.upper().str.replace('-', '.')
out = []
AG = {k: g for k, g in A[A.sym.isin(set(F.code))].groupby('sym')}
for code, G in F.groupby('code'):
    a = AG.get(code)
    if a is None: continue
    fd = a.fd.values
    for d, sh, t in zip(G.date.values, G.sh.values, G.t.values):
        w = a[(fd <= d) & (fd > d - np.timedelta64(3 * 365, 'D'))]
        if w.empty: out.append((t, d, 0.0, 0, np.nan)); continue
        cik = w.ISSUERCIK.mode().iloc[0]; w = w[w.ISSUERCIK == cik]
        last = w.groupby('RPTOWNERCIK').hold.last()
        out.append((t, d, last.sum() / sh if sh and sh > 0 else np.nan, len(last), cik))
Q = pd.DataFrame(out, columns=['t', 'date', 'ins_sec', 'n_ins', 'cik'])
Q.to_pickle(f'{HERE}/f4_out/ins_sec.pkl')
print(Q.ins_sec.describe(), (Q.ins_sec > 1).mean())
