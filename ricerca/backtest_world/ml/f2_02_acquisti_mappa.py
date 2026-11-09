# F2 passo 2: (a) acquisti P per modulo e dichiarante; (b) collegamento CIK della SEC -> codice dei nostri prezzi (EODHD), uscite incluse.
# Regole fissate PRIMA di guardare i rendimenti:
#  - solo dichiaranti Director o Officer (i soli "TenPercentOwner"/"Other" esclusi); Form 4 e 5, niente emendamenti;
#  - righe P con codice A (acquisizione), azioni >0, prezzo >0; valore = azioni x prezzo, sommato per modulo (accession);
#  - valori > 500 M$ in un modulo = errore di dati, tolti; prezzo > 5.000 $ tolto (tranne Berkshire);
#  - data che conta = data di deposito (filing_date), non la data dell'operazione.
# Collegamento: (1) simbolo del modulo (ISSUERTRADINGSYMBOL, al momento del deposito) = codice EODHD senza "_oldN", con data di
#  deposito dentro la vita della serie di prezzi (+-60 giorni) e nome simile; (2) company_tickers.json della SEC (CIK -> codice di
#  oggi) per le societa' vive che hanno cambiato simbolo. Un CIK collegato vale per tutti i suoi moduli nella vita della serie.
import os, re, glob, json, numpy as np, pandas as pd
ML = os.path.dirname(os.path.abspath(__file__)); OUT = f'{ML}/f2'
RAW = os.path.join(os.path.dirname(os.path.dirname(ML)), 'sec_raw')
_fs = sorted(glob.glob(f'{OUT}/p_*.pkl'))   # dopo il passo 1; poi riuniti in un solo file compresso (acquisti_P_grezzi_2006_2026q1.pkl.gz)
D = pd.concat([pd.read_pickle(f) for f in _fs], ignore_index=True) if _fs else pd.read_pickle(f'{OUT}/acquisti_P_grezzi_2006_2026q1.pkl.gz')
for _c in D.select_dtypes('category').columns: D[_c] = D[_c].astype(str).replace('nan', np.nan)
print('righe P grezze', len(D), '| moduli', D.accession_number.nunique())
D = D.drop_duplicates(['accession_number', 'trans_date', 'trans_shares', 'trans_pricepershare', 'shrs_ownd_folwng_trans', 'direct_indirect_ownership'])
rel = D.rel.fillna('')
D['is_dir'] = rel.str.contains('Director'); D['is_off'] = rel.str.contains('Officer')
D = D[(D.is_dir | D.is_off) & (D.trans_acquired_disp_cd == 'A') & (D.trans_shares > 0) & (D.trans_pricepershare > 0)]
D = D[(D.trans_pricepershare < 5000) | D.issuername.str.contains('BERKSHIRE', case=False, na=False)]
D['val'] = D.trans_shares * D.trans_pricepershare
ti = D.title.fillna('').str.upper()
D['ceo_cfo'] = ti.str.contains(r'\bCEO\b|CHIEF EXECUTIVE|\bCFO\b|CHIEF FINANCIAL|PRESIDENT', regex=True)
dl = D[D.direct_indirect_ownership == 'D']
after = dl.groupby('accession_number').shrs_ownd_folwng_trans.max()
A = D.groupby('accession_number').agg(cik=('issuercik', 'first'), sym=('issuertradingsymbol', 'first'), iname=('issuername', 'first'),
                                       filed=('filing_date', 'first'), tdate=('trans_date', 'min'), owner_cik=('owner_cik', 'first'),
                                       owner=('owner', 'first'), is_dir=('is_dir', 'max'), is_off=('is_off', 'max'), ceo_cfo=('ceo_cfo', 'max'),
                                       title=('title', 'first'), doc=('document_type', 'first'), val=('val', 'sum'), sh=('trans_shares', 'sum'),
                                       px=('trans_pricepershare', 'median')).reset_index()
A['sh_after'] = A.accession_number.map(after)
dsh = D[D.direct_indirect_ownership == 'D'].groupby('accession_number').trans_shares.sum()
A['sh_dir'] = A.accession_number.map(dsh).fillna(0)
A['pct_hold'] = np.where(A.sh_after > A.sh_dir, A.sh_dir / (A.sh_after - A.sh_dir), np.nan)   # aumento della posizione diretta
A = A[A.val <= 5e8]
A['cik'] = A.cik.astype(str).str.lstrip('0').astype(int)
A['lag_d'] = (A.filed - A.tdate).dt.days
print('moduli di acquisto di dirigenti/amministratori:', len(A), '| emittenti', A.cik.nunique(), '| valore mediano', round(A.val.median()),
      '| ritardo deposito mediano gg', A.lag_d.median(), '| >30 gg', round((A.lag_d > 30).mean(), 3))
# ------------------------------------------------------------------ collegamento CIK -> codice
P = pd.read_pickle(f'{ML}/storico5/pannello_prezzi_us_v2.pkl')
TK = P.groupby('t').agg(first=('first', 'first'), last=('last', 'first'), name=('name', 'first')).reset_index()
TK['base'] = TK.t.str.replace(r'_old\d*$', '', regex=True)
STOP = set('INC CORP CORPORATION CO COMPANY LTD PLC HOLDINGS HOLDING GROUP THE INCORPORATED LP LLC NEW DE CLASS A B CL COM TRUST INTL'.split())
tok = lambda s: set(w for w in re.sub(r'[^A-Z0-9 ]', ' ', str(s).upper().replace('&', ' ')).split() if w not in STOP and len(w) > 1)


def sim(a, b):
    x, y = tok(a), tok(b)
    return len(x & y) / min(len(x), len(y)) if x and y else 0.0


A['symn'] = A.sym.fillna('').str.upper().str.strip().str.replace('.', '-', regex=False).str.replace(' ', '', regex=False)
S = A[['cik', 'symn', 'iname', 'filed']]
J = S.merge(TK, left_on='symn', right_on='base')
J = J[(J.filed >= J['first'] - pd.Timedelta(days=60)) & (J.filed <= J['last'] + pd.Timedelta(days=60))]
LA = J.groupby(['cik', 't']).agg(n=('filed', 'size'), iname=('iname', 'first'), name=('name', 'first')).reset_index()
LA['sim'] = [sim(a, b) for a, b in zip(LA.iname, LA.name)]
LA['via'] = 'simbolo'
ct = json.load(open(f'{RAW}/company_tickers.json'))
CT = pd.DataFrame(ct.values()).rename(columns={'cik_str': 'cik', 'ticker': 'tk', 'title': 'ct_name'})
CT['tk'] = CT.tk.str.replace('.', '-', regex=False)
LB = CT.merge(TK[~TK.t.str.contains('_old')], left_on='tk', right_on='t')[['cik', 't', 'ct_name', 'name']]
LB = LB[LB.cik.isin(A.cik)]
LB['sim'] = [sim(a, b) for a, b in zip(LB.ct_name, LB.name)]; LB['via'] = 'sec_oggi'
L = pd.concat([LA[['cik', 't', 'sim', 'via', 'n']], LB[['cik', 't', 'sim', 'via']]]).groupby(['cik', 't']).agg(sim=('sim', 'max'), via=('via', lambda s: '+'.join(sorted(set(s)))), n=('n', 'sum')).reset_index()
# accetto: SEC di oggi con nome simile (>=0,34), oppure simbolo con nome simile (>=0,5), oppure simbolo con >=3 moduli e nome >=0,34
# oppure SEC di oggi E simbolo insieme (due fonti concordi), oppure simbolo con >=10 moduli quando codice e CIK sono un'unica coppia
uni = L.t.map(L.groupby('t').cik.nunique()).eq(1) & L.cik.map(L.groupby('cik').t.nunique()).eq(1)
ok = ((L.via.str.contains('sec_oggi')) & (L.sim >= 0.34)) | ((L.via.str.contains('simbolo')) & ((L.sim >= 0.5) | ((L.n >= 3) & (L.sim >= 0.34)))) \
     | (L.via == 'sec_oggi+simbolo') | ((L.via == 'simbolo') & (L.n >= 10) & uni)
print('coppie candidate', len(L), '| accettate', int(ok.sum()), '| scartate per nome diverso', int((~ok).sum()))
print(L[~ok].sort_values('n', ascending=False).head(12).merge(TK[['t', 'name']], on='t').to_string())
L = L[ok]
L = L.merge(TK[['t', 'first', 'last']], on='t')
L.to_pickle(f'{OUT}/link_cik_codice.pkl')
A.drop(columns=['symn']).to_pickle(f'{OUT}/acquisti_dirigenti.pkl')
cov = A.cik.isin(L.cik)
print('moduli collegati a un codice:', round(cov.mean(), 3), '| valore collegato', round(A.val[cov].sum() / A.val.sum(), 3), '| codici', L.t.nunique(), '| CIK', L.cik.nunique())
print('CIK con piu codici:', int((L.groupby('cik').t.nunique() > 1).sum()), '| codici con piu CIK:', int((L.groupby('t').cik.nunique() > 1).sum()))
