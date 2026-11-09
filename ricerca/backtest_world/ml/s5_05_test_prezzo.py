# Storico 2000-2011, punto 5.2a-b: prove di solo prezzo (USA, societa' uscite comprese) e diluizione (solo sopravvissute con bilanci).
# Regole fissate prima (REPORT_punteggi_profili, par. 6): prova 1 (prezzo/massimo: sotto il 40% crolli almeno doppi della media
# nel 2000-03, 2004-07, 2008-11), prova 2 (guardia: esclusi con piu' crolli), prova 3 (diluizione: IC negativo, quinto peggiore sotto).
# Universo a ogni fine trimestre: prezzo >=3$, scambi mediani 63 giorni >=3 M$, capitalizzazione >=300 M$ (vera se ci sono le azioni,
# altrimenti stimata dagli scambi con la rotazione mediana della data), almeno 200 giorni di prezzi nell'anno. Doppioni tolti.
# Esiti a 12 mesi: crollo = -50% o peggio; disastro = 20% peggiore della data; eccezionale = 5% migliore.
import sys, pandas as pd, numpy as np
from s5_common import OUT
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
D = pd.read_pickle(f'{OUT}/pannello_prezzi_us.pkl')
D = D[D.date <= '2024-09-30'].copy()
D['anno'] = (D.date + pd.Timedelta(days=1)).dt.year           # anno in cui parte la finestra di 12 mesi
D['blocco'] = pd.cut(D.anno, [1999, 2003, 2007, 2011, 2016, 2020, 2025],
                     labels=['2000-03', '2004-07', '2008-11', '2012-16', '2017-20', '2021-25'])
D['storico'] = D.anno <= 2011
# --- capitalizzazione: vera (azioni x prezzo) o stimata dagli scambi
D['turn'] = D.dv63 / D.cap
D.loc[(D.cap < 1e7) | (D.cap > 5e12), ['cap', 'turn']] = np.nan
D['titolo_speciale'] = D.t.str.contains(r'-(?:WS|WT|W|U|UN|R|RT)(?:-[A-Z]{1,2})?$|-R-W$', regex=True)   # warrant, unita', diritti
base = (D.px >= 3) & (D.dv63 >= 3e6) & (D.n1y >= 200) & D.p52.notna() & D.f12.notna() & ~D.titolo_speciale
med_turn = D[base & D.turn.between(1e-5, 0.5)].groupby('date').turn.median()
D['cap_est'] = D.dv63 / D.date.map(med_turn)
D['cap_use'] = D.cap.where(D.cap.notna(), D.cap_est)
D['cap_vera'] = D.cap.notna()
U = D[base & (D.cap_use >= 300e6)].copy()
U = U.sort_values(['date', 'src']).drop_duplicates(['date', 'px', 'dv63'])     # stessa serie due volte: tengo i nostri prezzi
g = U.groupby('date').f12
U['pct'] = g.rank(pct=True)
U['L50'] = U.f12 <= -0.5; U['L20'] = U.pct <= 0.2; U['W5'] = U.pct >= 0.95
U['uscita'] = U.f12_end
OUTF = open(f'{OUT}/risultati_prezzo.txt', 'w')


def say(*a):
    s = ' '.join(str(x) for x in a); print(s); OUTF.write(s + '\n')


def hh_t(x, lag=3):
    """t di Hansen-Hodrick (finestre di 12 mesi sovrapposte su date trimestrali)"""
    x = pd.Series(x).dropna().values
    n = len(x)
    if n < 6: return np.nan
    e = x - x.mean(); v = (e @ e) / n
    for k in range(1, lag + 1): v += 2 * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(max(v, 1e-12) / n)


def ic_series(X, col):
    return X.groupby('date').apply(lambda z: z[col].rank().corr(z.f12.rank()) if z[col].notna().sum() > 30 else np.nan)


# ------------------------------------------------------------------ 0. universo e distorsione da sopravvivenza
say('=== 0. Universo USA (azioni ordinarie, >=3$, >=3 M$/giorno, >=300 M$) ===')
T0 = U.groupby('anno').agg(titoli=('t', 'size'), date=('date', 'nunique'), cap_vera=('cap_vera', 'mean'),
                           usciti_pre2011=('uscita_pre2011', 'mean'), finestra_con_uscita=('uscita', 'mean'),
                           f12_media=('f12', 'mean'), crolli=('L50', 'mean'))
T0['titoli'] = (T0.titoli / T0.date).round(0)
say(T0.round(3).to_string())
# rendimento a 12 mesi: uscite prima del 2011 contro sopravvissute (misura della distorsione)
H = U[U.storico]
T0b = H.groupby(['anno', 'uscita_pre2011']).f12.agg(['mean', 'median', 'size']).unstack()
say('\nRendimento medio a 12 mesi: sopravvissute (False) contro uscite prima di meta 2011 (True)')
say(T0b.round(3).to_string())
for lab, X in [('tutte', H), ('solo sopravvissute', H[~H.uscita_pre2011])]:
    say(f'  {lab}: f12 medio {X.f12.mean():.3f}, crolli {X.L50.mean():.3f}, rendimento medio a pesi uguali per data {X.groupby("date").f12.mean().mean():.3f}')
# controllo della stima di capitalizzazione: fra chi ha le azioni, accordo fra stima e vera sulla soglia 300 M$
k = D[base & D.cap.notna() & D.storico]
say(f'\nStima della capitalizzazione dagli scambi (controllo su {len(k)} righe con azioni vere, 2000-2011): '
    f'accordo sulla soglia 300 M$ {((k.cap >= 300e6) == (k.cap_est >= 300e6)).mean():.3f}; '
    f'quota sopra 300 M$ vera {(k.cap >= 300e6).mean():.3f}, stimata {(k.cap_est >= 300e6).mean():.3f}')

# ------------------------------------------------------------------ 1. prezzo / massimo 52 settimane
BANDS = [0, 0.4, 0.6, 0.75, 0.9, 1.01]; BL = ['<40%', '40-60%', '60-75%', '75-90%', '>=90%']
U['p52b'] = pd.cut(U.p52, BANDS, labels=BL, right=False)


def band_table(X, by='p52b'):
    t = X.groupby(by, observed=True).agg(quota=('t', 'size'), crolli=('L50', 'mean'), disastri=('L20', 'mean'),
                                        eccezionali=('W5', 'mean'), f12_media=('f12', 'mean'), f12_mediana=('f12', 'median'),
                                        uscite_nella_finestra=('uscita', 'mean'))
    t['quota'] = t.quota / t.quota.sum()
    return t


say('\n=== 1. Prezzo / massimo a 52 settimane: crolli (-50%), disastri (20% peggiore), eccezionali (5% migliore) ===')
for blk in ['2000-03', '2004-07', '2008-11', '2012-16', '2017-20', '2021-25']:
    X = U[U.blocco == blk]
    t = band_table(X)
    say(f'\n-- {blk}: titoli per data {len(X) / X.date.nunique():.0f}, crolli medi {X.L50.mean():.3f}, disastri {X.L20.mean():.3f}')
    say(t.round(3).to_string())
    r = t.loc['<40%', 'crolli'] / X.L50.mean()
    say(f'   sotto il 40%: crolli = {r:.2f} volte la media  -> criterio (>=2) {"SUPERATO" if r >= 2 else "NON superato"}')
X = U[U.storico]
say('\n-- 2000-2011 intero'); say(band_table(X).round(3).to_string())
say('\n-- 2000-2011 senza banche, finanza, immobiliare, energia, miniere (filtro sul nome)'); say(band_table(X[~X.excl]).round(3).to_string())
yt = U.groupby('anno').apply(lambda z: pd.Series({'quota_sotto40': (z.p52 < 0.4).mean(), 'crolli_sotto40': z[z.p52 < 0.4].L50.mean(),
                                                  'crolli_media': z.L50.mean(), 'f12_sotto40': z[z.p52 < 0.4].f12.mean(), 'f12_media': z.f12.mean()}))
yt['rapporto'] = yt.crolli_sotto40 / yt.crolli_media
say('\n-- anno per anno (anno = inizio della finestra di 12 mesi)'); say(yt.round(3).to_string())
fz = X[X.f12_end]
say(f'\nfinestre chiuse da un uscita dal listino (2000-2011): {X.f12_end.mean():.1%} delle righe; di queste valutate -100% '
    f'(ultimo prezzo <25% del massimo): {(fz.f12 <= -0.999).mean():.1%}. Sotto il 40%: {(X[X.p52 < 0.4].f12 <= -0.999).mean():.1%} delle righe a -100%, '
    f'sopra il 90%: {(X[X.p52 >= 0.9].f12 <= -0.999).mean():.1%}')
# sola sopravvissute (come Europa/Asia in EODHD): quanto cambia
say('\n-- 2000-2011, SOLO sopravvissute al 2011 (cio che vedremmo con dati come quelli europei)')
say(band_table(X[~X.uscita_pre2011]).round(3).to_string())

# crisi
say('\n=== Crisi: date di partenza dentro le due crisi ===')
for lab, a, b in [('bolla internet: partenza 03/2000-09/2002', '2000-03-31', '2002-09-30'),
                  ('crisi 2008: partenza 09/2007-12/2008', '2007-09-30', '2008-12-31'),
                  ('rimbalzo: partenza 12/2008-06/2009', '2008-12-31', '2009-06-30')]:
    Y = U[(U.date >= a) & (U.date <= b)]
    say(f'\n-- {lab}: titoli per data {len(Y) / Y.date.nunique():.0f}, crolli medi {Y.L50.mean():.3f}')
    say(band_table(Y).round(3).to_string())
for d in ['2000-03-31', '2000-12-31', '2001-06-30', '2002-03-31', '2007-12-31', '2008-06-30', '2008-09-30', '2008-12-31', '2009-03-31']:
    Y = U[U.date == d]
    a = Y[Y.p52 < 0.4]; b = Y[Y.p52 >= 0.4]
    say(f'  {d}: sotto 40% = {len(a)} titoli ({len(a) / max(len(Y), 1):.0%}), crolli {a.L50.mean():.2f} contro {b.L50.mean():.2f}, '
        f'f12 medio {a.f12.mean():+.2f} contro {b.f12.mean():+.2f}, eccezionali {a.W5.mean():.2f} contro {b.W5.mean():.2f}')

# ------------------------------------------------------------------ correlazioni di classifica (IC) per anno
say('\n=== IC (correlazione di classifica con il rendimento a 12 mesi), media per blocco e t di Hansen-Hodrick ===')
for col in ['p52', 'mom12', 'mom6', 'vol']:
    s = ic_series(U, col)
    yr = (s.index + pd.Timedelta(days=1)).year
    say(f'{col:6s}', ' | '.join(f'{blk}: {s[(yr >= a) & (yr <= b)].mean():+.3f} (t {hh_t(s[(yr >= a) & (yr <= b)]):+.1f})'
                                for blk, a, b in [('2000-11', 2000, 2011), ('2000-03', 2000, 2003), ('2004-07', 2004, 2007), ('2008-11', 2008, 2011), ('2012-25', 2012, 2025)]))
    say('        per anno: ' + ' '.join(f'{y}:{v:+.2f}' for y, v in s.groupby(yr).mean().items() if y <= 2011))
say('IC solo sopravvissute 2000-2011: ' + ' | '.join(f'{c} {ic_series(X[~X.uscita_pre2011], c).mean():+.3f}' for c in ['p52', 'mom12', 'vol']))

# decili di momentum e volatilita'
for col, lab in [('mom12', 'Momentum 12-1'), ('vol', 'Volatilita 1 anno')]:
    say(f'\n=== {lab}: decili (1 = piu basso) ===')
    for per, Y in [('2000-11', U[U.storico]), ('2000-03', U[U.blocco == '2000-03']), ('2008-11', U[U.blocco == '2008-11']), ('2012-25', U[~U.storico])]:
        Y = Y[Y[col].notna()].copy()
        Y['dec'] = Y.groupby('date')[col].transform(lambda z: pd.qcut(z.rank(method='first'), 10, labels=False) + 1)
        t = Y.groupby('dec').agg(f12=('f12', 'mean'), crolli=('L50', 'mean'), disastri=('L20', 'mean'), eccezionali=('W5', 'mean'))
        say(f'-- {per}'); say(t.T.round(3).to_string())

# ------------------------------------------------------------------ 2. guardia (solo prezzo, e prezzo+diluizione dove ci sono le azioni)
say('\n=== 2. Guardia minima ===')
for per, Y in [('2000-03', U[U.blocco == '2000-03']), ('2004-07', U[U.blocco == '2004-07']), ('2008-11', U[U.blocco == '2008-11']), ('2012-25', U[~U.storico])]:
    ex = Y.p52 < 0.4
    say(f'{per} solo prezzo: esclusi {ex.mean():.1%}, crolli esclusi {Y[ex].L50.mean():.3f} contro ammessi {Y[~ex].L50.mean():.3f}; '
        f'eccezionali esclusi {Y[ex].W5.mean():.3f} contro {Y[~ex].W5.mean():.3f}; f12 medio {Y[ex].f12.mean():+.3f} contro {Y[~ex].f12.mean():+.3f}')
    Z = Y[Y.dsh1.notna()]
    ex2 = (Z.p52 < 0.4) | (Z.dsh1 > 0.25)
    say(f'        prezzo+diluizione (solo chi ha le azioni, {len(Z) / max(len(Y), 1):.0%} delle righe): esclusi {ex2.mean():.1%}, '
        f'crolli {Z[ex2].L50.mean():.3f} contro {Z[~ex2].L50.mean():.3f}; eccezionali {Z[ex2].W5.mean():.3f} contro {Z[~ex2].W5.mean():.3f}')

# ------------------------------------------------------------------ 3. diluizione (sopravvissute con bilanci)
say('\n=== 3. Diluizione a 3 anni (solo titoli con azioni nei bilanci: sopravvissute) ===')
for per, Y in [('2000-05', U[U.storico & (U.anno <= 2005)]), ('2006-11', U[U.storico & (U.anno >= 2006)]), ('2012-25', U[~U.storico])]:
    Z = Y[Y.dsh3.notna()].copy()
    s = ic_series(Z, 'dsh3')
    Z['q'] = Z.groupby('date').dsh3.transform(lambda z: pd.qcut(z.rank(method='first'), 5, labels=False) + 1)
    Z['rel'] = Z.f12 - Z.groupby('date').f12.transform('mean')
    t = Z.groupby('q').agg(n=('t', 'size'), dsh3_med=('dsh3', 'median'), f12_vs_media=('rel', 'mean'), crolli=('L50', 'mean'),
                           disastri=('L20', 'mean'), eccezionali=('W5', 'mean'))
    cov = len(Z) / max(len(Y), 1)
    say(f'-- {per}: copertura {cov:.0%} delle righe dell universo; IC {s.mean():+.3f} (t HH {hh_t(s):+.1f}); quinto 5 = piu diluito')
    say(t.round(3).to_string())
    q5 = Z[Z.q == 5].groupby('date').rel.mean()
    say(f'   quinto piu diluito contro media: {q5.mean():+.3f} l anno (t HH {hh_t(q5):+.1f})')
    say(f'   da dove vengono le azioni: nostri dati {(Z.src == "A").mean():.0%}, classe C scaricata oggi {(Z.src == "D").mean():.0%}; '
        f'chi non ha le azioni (escluso): crolli {Y[Y.dsh3.isna()].L50.mean():.3f} contro {Z.L50.mean():.3f} di chi le ha')
    d1 = Z[Z.dsh1.notna()]
    say(f'   diluizione >25% in 1 anno: {(d1.dsh1 > 0.25).mean():.1%} delle righe, crolli {d1[d1.dsh1 > 0.25].L50.mean():.3f} contro {d1[d1.dsh1 <= 0.25].L50.mean():.3f}')
U.to_pickle(f'{OUT}/universo_prezzi_us.pkl')
OUTF.close()
