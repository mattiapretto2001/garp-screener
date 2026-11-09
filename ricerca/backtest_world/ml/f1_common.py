# F1 multibagger: regole FISSATE PRIMA di guardare i risultati (09/11/2026). Non ritoccate dopo.
#
# Studio: Yartseva (2025), "The Alchemy of Multibagger Stocks", CAFE Working Paper 33, Birmingham City University.
# 464 titoli USA saliti almeno x10 fra 2009 e 2024; panel dinamico (GMM), rendimento annuo sopra il tasso privo di rischio.
# Variabili e segni trovati dallo studio, come li usiamo:
#   fcfy   FCF / capitalizzazione (FCF/P) ................. +  (il fattore piu' importante dello studio)
#   bm     patrimonio / capitalizzazione (B/M) ............ +  (patrimonio <=0 -> B/M negativo, quindi in fondo)
#   size   log del valore d'impresa (TEV; se EV<=0 la capitalizzazione) ... -  (piu' piccole meglio)
#   roa    utile netto TTM / totale attivo ................ +  (redditivita' dei modelli dinamici)
#   inv    1 se crescita dell'attivo in 1 anno > crescita dell'EBITDA TTM in 1 anno ... -  (EBITDA di un anno prima <=0
#          o mancante -> non definito, valore neutro)
#   prange (prezzo - minimo 12 mesi) / (massimo - minimo) .. -  (entrare vicino al minimo dell'anno)
#   mom    rendimento a 3 e a 6 mesi (media dei due ranghi) . -  (inversione)
#   asset_g crescita dell'attivo ........................... +  (debole: 3 specificazioni su 7) -> solo prova singola
#   tassi  1 se il tasso della Fed e' salito nei 12 mesi prima della data ... -  (variabile di mercato, non di scelta)
# NON usati dallo studio come premio: crescita degli utili/ricavi (non significativa), P/E (scartato).
#
# Punteggio "studio" S = media semplice dei ranghi percentili (0-1) per data e regione delle 7 componenti
# fcfy, bm, size, roa, inv, prange, mom con i segni dello studio; dato mancante = 0,5. Pesi uguali, nessuna stima.
# Selezione: quinto alto di S (20%) per data e regione. Nessuna soglia ottimizzata; si mostrano anche tutti i quinti.
# Dentro le liste (GARP core, Crescita, Qualita' Q3, Radar A): meta' con S sopra la mediana della lista alla data
# contro meta' sotto (e contro la lista intera).
# Target: x3 = valore triplicato alla fine dei 3 anni (euro; 2004-11 dollari); top5 = 5% migliore a 12 mesi nella regione;
# disastri = 20% peggiore nella regione (bot20) e crolli = -50% o peggio a 12 mesi (crash50).
# t: solo rendimenti non sovrapposti (date distanti 12 mesi per i target a 12 mesi, 36 mesi per x3), una serie per
# ciascuna "fase" trimestrale; si riporta la media dei t delle fasi. Caso: estrazioni ipergeometriche esatte con lo
# stesso numero di titoli per data e regione.
import numpy as np, pandas as pd, os
ML = os.path.dirname(os.path.abspath(__file__)); OUT = f'{ML}/f1_out'

COMP = ['fcfy', 'bm', 'size', 'roa', 'inv', 'prange', 'mom']
SIGN = {'fcfy': 1, 'bm': 1, 'size': -1, 'roa': 1, 'inv': -1, 'prange': -1, 'mom3': -1, 'mom6': -1, 'asset_g': 1}

# tasso Fed (limite alto dell'obiettivo) a fine trimestre
FED = {}
_seq = [('2003-06', 1.00), ('2004-06', 1.25), ('2004-09', 1.75), ('2004-12', 2.25), ('2005-03', 2.75), ('2005-06', 3.25),
        ('2005-09', 3.75), ('2005-12', 4.25), ('2006-03', 4.75), ('2006-06', 5.25), ('2007-09', 4.75), ('2007-12', 4.25),
        ('2008-03', 2.25), ('2008-06', 2.00), ('2008-12', 0.25), ('2015-12', 0.50), ('2016-12', 0.75), ('2017-03', 1.00),
        ('2017-06', 1.25), ('2017-12', 1.50), ('2018-03', 1.75), ('2018-06', 2.00), ('2018-09', 2.25), ('2018-12', 2.50),
        ('2019-09', 2.00), ('2019-12', 1.75), ('2020-03', 0.25), ('2022-03', 0.50), ('2022-06', 1.75), ('2022-09', 3.25),
        ('2022-12', 4.50), ('2023-03', 5.00), ('2023-06', 5.25), ('2023-09', 5.50), ('2024-09', 5.00), ('2024-12', 4.50),
        ('2025-09', 4.25), ('2025-12', 3.75)]
for d in pd.date_range('2003-06-30', '2026-12-31', freq='QE'):
    v = [r for m, r in _seq if pd.Timestamp(m) + pd.offsets.MonthEnd(0) <= d]
    FED[d.normalize()] = v[-1]


def fed_rising(d):
    d = pd.Timestamp(d).normalize(); p = (d - pd.DateOffset(years=1)) + pd.offsets.MonthEnd(0)
    return FED.get(d, np.nan) > FED.get(p.normalize(), np.nan)


def add_vars(F, group):
    """F con colonne grezze fcfy, pb, ev, mcap, ni_ttm, ta, asset_g, ebitda_ttm, mom3, mom6, pr. Aggiunge le variabili."""
    F = F.sort_values(['t', 'date']).copy()
    F['bm'] = np.where(F.pb > 0, 1 / F.pb, np.where(F.equity <= 0, -1.0, np.nan))
    F['size'] = np.log(np.where(F.ev > 0, F.ev, F.mcap) * F.fx_rep)
    F['roa'] = (F.ni_ttm / F.ta).where(F.ta > 0)
    lag = F.groupby('t')[['date', 'ebitda_ttm']].shift(4)
    ok = (lag.date - F.date).dt.days.abs().between(330, 400) & (lag.ebitda_ttm > 0)
    F['ebitda_g'] = (F.ebitda_ttm / lag.ebitda_ttm - 1).where(ok)
    F['inv'] = (F.asset_g > F.ebitda_g).astype(float).where(F.asset_g.notna() & F.ebitda_g.notna())
    F['prange'] = F.pr
    for c in ['fcfy', 'bm', 'size', 'roa', 'inv', 'prange', 'mom3', 'mom6', 'asset_g']:
        r = F.groupby(['date', group])[c].rank(pct=True, method='average')
        F[f'k_{c}'] = (r if SIGN[c] > 0 else 1 - r).fillna(0.5)
    F['k_mom'] = (F.k_mom3 + F.k_mom6) / 2
    F['S'] = F[[f'k_{c}' for c in COMP]].mean(axis=1)
    F['qS'] = F.groupby(['date', group]).S.transform(lambda s: np.ceil(s.rank(pct=True, method='first') * 5)).astype(int)
    return F.replace([np.inf, -np.inf], np.nan)


def nov_t(d, step):
    """d: Serie per data (differenza di quota). t medio sulle fasi di serie non sovrapposte (date distanti 'step' trimestri)."""
    d = d.sort_index(); ts = []
    for ph in range(step):
        x = d.iloc[ph::step].dropna()
        if len(x) >= 3 and x.std(ddof=1) > 0: ts.append(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))
    return (np.mean(ts) if ts else np.nan), (min(ts) if ts else np.nan), (max(ts) if ts else np.nan), len(ts)


def rand_pct(F, sel, pool, tgt, group, n_it=2000, seed=11):
    """quota di estrazioni a caso (stesso numero per data e gruppo, dentro pool) con quota di target >= quella reale"""
    rng = np.random.default_rng(seed)
    X = F[pool & F[tgt].notna()]
    g = X.groupby(['date', group])
    N = g.size(); M = g[tgt].sum(); K = X[sel[X.index]].groupby(['date', group]).size().reindex(N.index).fillna(0).astype(int)
    real = X.loc[sel[X.index], tgt].sum() / max(K.sum(), 1)
    sims = np.zeros(n_it)
    for (n, m, k) in zip(N.values, M.values.astype(int), K.values):
        if k: sims += rng.hypergeometric(m, n - m, k, size=n_it)
    sims /= max(K.sum(), 1)
    return real, np.mean(sims >= real), np.percentile(sims, 2.5), np.percentile(sims, 97.5)
