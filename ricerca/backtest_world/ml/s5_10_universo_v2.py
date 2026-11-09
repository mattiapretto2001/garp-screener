# Storico 2000-2011, 08/11/2026: universo USA v2 dal pannello v2 (s5_09), e conteggi delle societa' uscite che entrano.
# Regole a ogni fine trimestre (12/1999 - 09/2011 per lo storico; il file contiene anche 2012-2024 come la v1):
#   prezzo >=3$, scambi mediani 63 giorni >=3 M$, almeno 200 giorni di prezzi nell'anno, niente warrant/unita'/diritti;
#   capitalizzazione >=300 M$ SOLO dove ci sono le azioni (capitalizzazione vera). Dove le azioni non ci sono non filtro sulla
#   capitalizzazione: la verifica avversariale ha mostrato che la stima dagli scambi non distingue (mette sopra 300 M$ il 97%
#   delle societa' davvero sotto). La stima resta nella colonna cap_est, e per confronto conto anche l'universo con la regola v1.
# Controlli di qualita' (nuovi, per TUTTE le serie, anche le vecchie A e D): tolgo le righe con
#   q1 prezzo corretto EODHD bloccato a 1.000.000 vicino alla data (colonna a_tetto del pannello);
#   q2 prezzo corretto fermo (volatilita' annua <1%: nessuna azione vera scambiata per >=3 M$ al giorno e' cosi');
#   q3 scambi mediani >20 miliardi $ al giorno (impossibili nel 2000-2011: sono volumi o prezzi in valuta sbagliata);
#   q4 prezzo >5.000 $ (tranne Berkshire A): dati sbagliati.
# Doppioni: (a) stessa data, prezzo e scambi identici; (b) NUOVO: stessa data, stesso rendimento a 12 mesi (3 decimali),
#   stesso prezzo/massimo (2 decimali) e prezzo entro lo 0,5%: e' la stessa serie con due codici (per es. BIG e BIGGQ, IAC e
#   MTCH). Tengo la serie nell'ordine A, D, V, W e, a parita', quella piu' lunga.
# Nessuna chiamata EODHD. Scrive storico5/universo_prezzi_us_v2.pkl, storico5/universo_v2_per_anno.csv,
# storico5/famose_37_v2.csv, storico5/doppioni_v2.csv (righe tolte perche' doppioni, con il codice tenuto).
import sys, pandas as pd, numpy as np
from s5_common import OUT
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 200)
FAM = {'LEH': 'Lehman Brothers', 'BSC_old': 'Bear Stearns', 'MER': 'Merrill Lynch', 'WAMUQ': 'Washington Mutual',
       'NCC': 'National City', 'WB_old2': 'Wachovia', 'ENRNQ': 'Enron', 'MCWEQ': 'WorldCom', 'CPQ': 'Compaq', 'PRD': 'Polaroid',
       'GLBC': 'Global Crossing', 'PHA': 'Pharmacia', 'KM': 'Kmart', 'PSFT_old': 'PeopleSoft', 'G_old': 'Gillette',
       'MAY': 'May Department Stores', 'T1': 'AT&T Corp', 'GDT_old': 'Guidant', 'BLS': 'BellSouth', 'PIXR': 'Pixar',
       'PD_old': 'Phelps Dodge', 'AT_old1': 'Alltel', 'BUD_old': 'Anheuser-Busch', 'CCTYQ': 'Circuit City',
       'NWAC': 'Northwest Airlines', 'DNA_old': 'Genentech', 'SGP_old1': 'Schering-Plough', 'GM_old': 'General Motors',
       'JAVA_old': 'Sun Microsystems', 'BNI': 'Burlington Northern', 'WYE': 'Wyeth', 'BDK': 'Black & Decker',
       'SII_old': 'Smith International', 'PALM': 'Palm', 'GENZ_old': 'Genzyme', 'NOVL': 'Novell', 'Q_old': 'Qwest'}
EXTRA = {'WB_old1': 'Wachovia 2001-2008 (ex First Union; WB_old2 e\' la Wachovia prima della fusione del 2001)'}
SRC_ORD = {'A': 0, 'D': 1, 'V': 2, 'W': 3}


def prep(D):
    D = D[D.date <= '2024-09-30'].copy()
    D['anno'] = (D.date + pd.Timedelta(days=1)).dt.year
    D['blocco'] = pd.cut(D.anno, [1999, 2003, 2007, 2011, 2016, 2020, 2025],
                         labels=['2000-03', '2004-07', '2008-11', '2012-16', '2017-20', '2021-25'])
    D['storico'] = D.anno <= 2011
    D['turn'] = D.dv63 / D.cap
    D.loc[(D.cap < 1e7) | (D.cap > 5e12), ['cap', 'turn']] = np.nan
    D['titolo_speciale'] = D.t.str.contains(r'-(?:WS|WT|W|U|UN|R|RT)(?:-[A-Z]{1,2})?$|-R-W$', regex=True)
    base = (D.px >= 3) & (D.dv63 >= 3e6) & (D.n1y >= 200) & D.p52.notna() & D.f12.notna() & ~D.titolo_speciale
    Q = pd.DataFrame({'q1_tetto': D.a_tetto.astype(bool), 'q2_ferma': D.vol < 0.01, 'q3_scambi': D.dv63 > 2e10,
                      'q4_prezzo': (D.px > 5000) & (D.t != 'BRK-A')})
    D['qualita_ko'] = Q.any(axis=1)
    med_turn = D[base & ~D.qualita_ko & D.turn.between(1e-5, 0.5)].groupby('date').turn.median()
    D['cap_est'] = D.dv63 / D.date.map(med_turn)
    D['cap_use'] = D.cap.where(D.cap.notna(), D.cap_est)
    D['cap_vera'] = D.cap.notna()
    return D, base, Q


def dedup(U, nser):
    U = U.sort_values(['date', 'src']).drop_duplicates(['date', 'px', 'dv63']).copy()
    n_a = len(U)
    U['_o'] = U.src.map(SRC_ORD); U['_n'] = -U.t.map(nser)
    U = U.sort_values(['date', '_o', '_n'])
    U['_k'] = U.f12.round(3).astype(str) + '|' + U.p52.round(2).astype(str)
    C = U[U.duplicated(['date', '_k'], keep=False)]
    drop, of = [], []
    for _, g in C.groupby(['date', '_k'], sort=False):
        kept = []
        for i, p, t in zip(g.index, g.px.values, g.t.values):
            j = next((k for q, k in kept if abs(p / q - 1) < 0.005), None)
            if j is None: kept.append((p, t))
            else: drop.append(i); of.append(j)
    dup_of = U.loc[drop, ['t', 'date']].assign(tenuto=of)
    U = U.drop(index=drop).drop(columns=['_o', '_n', '_k'])
    return U, n_a, dup_of


def finish(U):
    U = U.copy()
    U['pct'] = U.groupby('date').f12.rank(pct=True)
    U['L50'] = U.f12 <= -0.5; U['L20'] = U.pct <= 0.2; U['W5'] = U.pct >= 0.95
    U['uscita'] = U.f12_end
    return U


D, base, Q = prep(pd.read_pickle(f'{OUT}/pannello_prezzi_us_v2.pkl'))
nser = D.groupby('t').size()
B = base & D.storico
print('righe che passano prezzo/scambi/giorni nel 2000-11:', int(B.sum()), '| tolte dai controlli di qualita:', int((B & D.qualita_ko).sum()))
print(pd.DataFrame({c: D[B & Q[c]].groupby('src').t.nunique() for c in Q}).fillna(0).astype(int).T.assign(
      righe=[int((B & Q[c]).sum()) for c in Q]).to_string())
Upre = D[base & ~D.qualita_ko & (D.cap.isna() | (D.cap >= 300e6))]                            # regola v2, prima dei doppioni
U, n_a, DUP = dedup(Upre, nser)
print(f'doppioni tolti: esatti {len(Upre) - n_a}, stessa serie con due codici {len(DUP)} '
      f'(nel 2000-11: {int(Upre.storico.sum()) - int(U.storico.sum())} tolte, {int(U.storico.sum())} righe restano)')
DUP.to_csv(f'{OUT}/doppioni_v2.csv', index=False)
U = finish(U)
U1n = finish(dedup(D[base & ~D.qualita_ko & (D.cap_use >= 300e6)], nser)[0])                  # regola v1 sul pannello nuovo
U0 = pd.read_pickle(f'{OUT}/universo_prezzi_us.pkl')                                          # universo v1 (07/11)
U['nuova'] = U.src.isin(['V', 'W'])
U.to_pickle(f'{OUT}/universo_prezzi_us_v2.pkl')

H = U[U.storico]; H0 = U0[U0.storico]; H1 = U1n[U1n.storico]
nd = lambda X: X.groupby('anno').date.nunique()
T = pd.DataFrame({
    'date': nd(H),
    'v1_titoli_per_data': (H0.groupby('anno').size() / nd(H0)).round(0),
    'v1regola_pannello_nuovo': (H1.groupby('anno').size() / nd(H1)).round(0),
    'v2_titoli_per_data': (H.groupby('anno').size() / nd(H)).round(0),
    'v2_titoli_distinti': H.groupby('anno').t.nunique(),
    'v1_uscite_distinte': H0[H0.uscita_pre2011].groupby('anno').t.nunique(),
    'v2_uscite_distinte': H[H.uscita_pre2011].groupby('anno').t.nunique(),
    'v2_quota_uscite': H.groupby('anno').uscita_pre2011.mean().round(3),
    'nuove_distinte': H[H.nuova].groupby('anno').t.nunique(),
    'nuove_per_data': (H[H.nuova].groupby('anno').size() / nd(H)).round(0),
    'nuove_uscite_pre2011': H[H.nuova & H.uscita_pre2011].groupby('anno').t.nunique(),
    'nuove_fuori_borsa': H[H.nuova & H.fuori_borsa].groupby('anno').t.nunique(),
    'nuove_old': H[H.nuova & H.codice_old].groupby('anno').t.nunique(),
    'cap_vera': H.groupby('anno').cap_vera.mean().round(3),
}).fillna(0)
tot = {'date': H.date.nunique(), 'v1_titoli_per_data': round(len(H0) / H0.date.nunique()),
       'v1regola_pannello_nuovo': round(len(H1) / H1.date.nunique()), 'v2_titoli_per_data': round(len(H) / H.date.nunique()),
       'v2_titoli_distinti': H.t.nunique(), 'v1_uscite_distinte': H0[H0.uscita_pre2011].t.nunique(),
       'v2_uscite_distinte': H[H.uscita_pre2011].t.nunique(), 'v2_quota_uscite': round(H.uscita_pre2011.mean(), 3),
       'nuove_distinte': H[H.nuova].t.nunique(), 'nuove_per_data': round(H.nuova.sum() / H.date.nunique()),
       'nuove_uscite_pre2011': H[H.nuova & H.uscita_pre2011].t.nunique(), 'nuove_fuori_borsa': H[H.nuova & H.fuori_borsa].t.nunique(),
       'nuove_old': H[H.nuova & H.codice_old].t.nunique(), 'cap_vera': round(H.cap_vera.mean(), 3)}
T.loc['2000-11'] = pd.Series(tot)
T.index = T.index.astype(str)
T.to_csv(f'{OUT}/universo_v2_per_anno.csv')
print(T.to_string())
print('\nnuove per origine (2000-11, titoli distinti):', H[H.nuova].groupby('src').t.nunique().to_dict(),
      '| righe', H.nuova.sum(), 'su', len(H), f'({H.nuova.mean():.1%})')
print('per fascia di scambi stimati nella lista (prio):')
try:
    L = pd.read_csv(f'{OUT}/lista_prezzi_us_v2.csv').set_index('t')
    W = H[H.src == 'W'].copy(); W['prio'] = W.t.map(L.prio)
    print('  titoli W entrati per priorita:', W.groupby('prio').t.nunique().to_dict(), '| scaricati per priorita:', L.prio.value_counts().sort_index().to_dict())
except Exception as e:
    print('  ', e)
# esiti: le nuove contro le altre
for lab, X in [('nuove', H[H.nuova]), ('gia presenti', H[~H.nuova])]:
    print(f'{lab:12s}: righe {len(X):6d} | f12 medio {X.f12.mean():+.3f} | crolli (-50%) {X.L50.mean():.3f} | finestra chiusa da uscita {X.uscita.mean():.3f}')
print(f'tutte 2000-11: rendimento medio a pesi uguali per data {H.groupby("date").f12.mean().mean():.3f}, crolli {H.L50.mean():.3f} | '
      f'solo sopravvissute {H[~H.uscita_pre2011].groupby("date").f12.mean().mean():.3f}, {H[~H.uscita_pre2011].L50.mean():.3f}')
print(f'v1 (07/11):    rendimento medio {H0.groupby("date").f12.mean().mean():.3f}, crolli {H0.L50.mean():.3f} | '
      f'solo sopravvissute {H0[~H0.uscita_pre2011].groupby("date").f12.mean().mean():.3f}, {H0[~H0.uscita_pre2011].L50.mean():.3f}')
# le 37 famose
P = set(D.t)
rows = []
for t, nm in {**FAM, **EXTRA}.items():
    x = Upre[(Upre.t == t) & Upre.storico]; p = D[D.t == t]; dd = DUP[DUP.t == t]
    rows.append({'codice': t, 'nome': nm, 'nel_pannello': t in P, 'righe_universo_2000_11': len(x),
                 'di_cui_col_suo_codice': int(((H.t == t)).sum()),
                 'altro_codice': ','.join(sorted(dd.tenuto.unique())) if len(dd) else '',
                 'prima': x.date.min().date() if len(x) else None, 'ultima': x.date.max().date() if len(x) else None,
                 'origine': p.src.iloc[0] if len(p) else None, 'ultimo_prezzo': p['last'].iloc[0].date() if len(p) else None,
                 'nell_universo_v1': t in set(H0.t)})
F = pd.DataFrame(rows); F.to_csv(f'{OUT}/famose_37_v2.csv', index=False)
F37 = F[F.codice.isin(FAM)]
print(f'\n37 famose: nel pannello {F37.nel_pannello.sum()} | nell universo 2000-11 {(F37.righe_universo_2000_11 > 0).sum()} '
      f'(v1: {F37.nell_universo_v1.sum()})')
print(F.to_string())
# controllo a occhio: le nuove con piu' trimestri nell'universo
g = H[H.nuova].groupby('t').agg(nome=('name', 'first'), borsa=('borsa', 'first'), src=('src', 'first'), n=('date', 'size'),
                                prima=('date', 'min'), ultima=('date', 'max'), dv63=('dv63', 'median'), px=('px', 'median'),
                                cap=('cap', 'median'), crolli=('L50', 'sum'))
print('\nnuove con piu trimestri:'); print(g.sort_values('n', ascending=False).head(40).to_string())
print('\nnuove fuori borsa:'); print(g[g.borsa.notna() & ~g.borsa.isin(['NYSE', 'NASDAQ', 'NYSE MKT', 'AMEX', 'NYSE ARCA', 'BATS'])].sort_values('dv63', ascending=False).head(40).to_string())
# da dove vengono le righe tolte come doppioni (2000-11), e l'universo con le sole serie vecchie (A+D) e le regole v2
src_t = D.drop_duplicates('t').set_index('t').src
Dh = DUP[(DUP.date + pd.Timedelta(days=1)).dt.year <= 2011]
print('\ndoppioni tolti nel 2000-11, per origine riga tolta -> tenuta:',
      (Dh.t.map(src_t) + '->' + Dh.tenuto.map(src_t)).value_counts().to_dict())
print('universo 2000-11 con le sole serie A+D e le regole v2: titoli per data', round((~H.nuova).sum() / H.date.nunique()),
      '| con le nuove', round(len(H) / H.date.nunique()), '| v1', round(len(H0) / H0.date.nunique()))
