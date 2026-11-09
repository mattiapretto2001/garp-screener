# Prova A (08/11/2026): regole di solo prezzo, USA 2000-2011, sull'universo completo (societa' uscite comprese).
# Definizioni e criteri congelati il 07/11 (REPORT_punteggi_profili par. 6, codice s5_05_test_prezzo.py), non ritoccati:
#   crollo = rendimento a 12 mesi <= -50% (uscita dal listino con ultimo prezzo <25% del massimo dell'anno = -100%, cioe'
#   fallimento); disastro = 20% peggiore della data; eccezionale = 5% migliore; anno = anno in cui parte la finestra.
#   Prova 1: sotto il 40% del massimo a 52 settimane, crolli >= 2 volte la media in 2000-03, 2004-07 e 2008-11.
#   Prova 2 (guardia, solo prezzo): gli esclusi (sotto il 40%) hanno piu' crolli degli ammessi in tutti e tre i periodi.
#   Volatilita' a 1 anno, momentum 12-1 e 6-1: decili e correlazione di classifica (t di Hansen-Hodrick), come il 07/11.
# Universi confrontati (tutti con lo stesso codice qui sotto):
#   v1      = storico5/universo_prezzi_us.pkl (07/11, universo incompleto, capitalizzazione stimata dagli scambi);
#   v2      = storico5/universo_prezzi_us_v2.pkl (08/11, con le 10.443 serie scaricate oggi; 300 M$ solo dove ci sono le azioni);
#   v2_AD   = v2 senza le serie nuove (solo le serie che c'erano gia' il 07/11): separa l'effetto delle regole da quello delle serie;
#   v2_prud = v2 con prezzo e scambi PRUDENTI (sA_02): entra solo chi supera 3 $ e 3 M$ con qualunque lettura dei frazionamenti;
#   v2_stima= v2 con la stima frazionamento per frazionamento (sA_02).
# Nessuna chiamata EODHD. Scrive storico5/risultati_A_v2.txt e storico5/confronto_A.csv.
import sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from s5_common import OUT
from sA_common import build, finish
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 300)
BLK = ['2000-03', '2004-07', '2008-11']
BANDS = [0, 0.4, 0.6, 0.75, 0.9, 1.01]; BL = ['<40%', '40-60%', '60-75%', '75-90%', '>=90%']
OUTF = open(f'{OUT}/risultati_A_v2.txt', 'w')


def say(*a):
    s = ' '.join(str(x) for x in a); print(s); OUTF.write(s + '\n')


def hh_t(x, lag=3):
    x = pd.Series(x).dropna().values; n = len(x)
    if n < 6: return np.nan
    e = x - x.mean(); v = (e @ e) / n
    for k in range(1, lag + 1): v += 2 * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(max(v, 1e-12) / n)


def ic_series(X, col):
    return X.groupby('date').apply(lambda z: z[col].rank().corr(z.f12.rank()) if z[col].notna().sum() > 30 else np.nan)


def ew(X):           # rendimento medio a pesi uguali: media per data, poi media delle date
    return X.groupby('date').f12.mean().mean() if len(X) else np.nan


def dec(X, col):
    Y = X[X[col].notna()].copy()
    Y['dec'] = Y.groupby('date')[col].transform(lambda z: pd.qcut(z.rank(method='first'), 10, labels=False) + 1)
    return Y


def band_table(X):
    X = X.assign(p52b=pd.cut(X.p52, BANDS, labels=BL, right=False))
    t = X.groupby('p52b', observed=True).agg(n=('t', 'size'), crolli=('L50', 'mean'), fallimenti=('f12', lambda s: (s <= -0.999).mean()),
                                             disastri=('L20', 'mean'), eccezionali=('W5', 'mean'), f12_media=('f12', 'mean'),
                                             f12_mediana=('f12', 'median'))
    t['quota'] = t.n / t.n.sum()
    return t


def metrics(U):
    H = U[U.storico]
    m = {}
    m['titoli_per_data'] = len(H) / H.date.nunique()
    m['quota_uscite_pre2011'] = H.uscita_pre2011.mean()
    for per, X in [('2000-11', H)] + [(b, H[H.blocco == b]) for b in BLK]:
        ex = X.p52 < 0.4
        m[f'{per}|crolli'] = X.L50.mean()
        m[f'{per}|fallimenti_-100%'] = (X.f12 <= -0.999).mean()
        m[f'{per}|f12_pesi_uguali'] = ew(X)
        m[f'{per}|f12_mediana'] = X.f12.median()
        m[f'{per}|quota_sotto40'] = ex.mean()
        m[f'{per}|crolli_sotto40'] = X[ex].L50.mean()
        m[f'{per}|crolli_sopra90'] = X[X.p52 >= 0.9].L50.mean()
        m[f'{per}|rapporto_sotto40'] = X[ex].L50.mean() / X.L50.mean()
        m[f'{per}|guardia_crolli_esclusi'] = X[ex].L50.mean(); m[f'{per}|guardia_crolli_ammessi'] = X[~ex].L50.mean()
        m[f'{per}|guardia_ecc_esclusi'] = X[ex].W5.mean(); m[f'{per}|guardia_ecc_ammessi'] = X[~ex].W5.mean()
        m[f'{per}|guardia_f12_esclusi'] = X[ex].f12.mean(); m[f'{per}|guardia_f12_ammessi'] = X[~ex].f12.mean()
        m[f'{per}|guardia_f12pu_ammessi'] = ew(X[~ex])
        for col in ['vol', 'mom12', 'mom6']:
            Y = dec(X, col); g = Y.groupby('dec')
            m[f'{per}|{col}_crolli_d1'] = g.L50.mean()[1]; m[f'{per}|{col}_crolli_d10'] = g.L50.mean()[10]
            m[f'{per}|{col}_crolli_centro'] = Y[Y.dec.isin([5, 6])].L50.mean()
            m[f'{per}|{col}_f12_d1'] = g.f12.mean()[1]; m[f'{per}|{col}_f12_d10'] = g.f12.mean()[10]
            m[f'{per}|{col}_f12_centro'] = Y[Y.dec.isin([5, 6])].f12.mean()
            m[f'{per}|{col}_ecc_d10'] = g.W5.mean()[10]
            s = ic_series(X, col); m[f'{per}|{col}_IC'] = s.mean(); m[f'{per}|{col}_IC_t'] = hh_t(s)
    # rimbalzo: partenze da 12/2008 a 06/2009; anno 2009 = partenze 12/2008-09/2009
    for lab, a, b in [('rimbalzo', '2008-12-31', '2009-06-30'), ('bolla', '2000-03-31', '2002-09-30'), ('crisi2008', '2007-09-30', '2008-12-31')]:
        Y = H[(H.date >= a) & (H.date <= b)]; ex = Y.p52 < 0.4
        m[f'{lab}|quota_sotto40'] = ex.mean()
        m[f'{lab}|crolli_sotto40'] = Y[ex].L50.mean(); m[f'{lab}|crolli_sopra90'] = Y[Y.p52 >= 0.9].L50.mean(); m[f'{lab}|crolli'] = Y.L50.mean()
        m[f'{lab}|f12_sotto40'] = Y[ex].f12.mean(); m[f'{lab}|f12_sopra90'] = Y[Y.p52 >= 0.9].f12.mean(); m[f'{lab}|f12_tutti'] = ew(Y)
        m[f'{lab}|f12_ammessi'] = ew(Y[~ex])
        for col in ['vol', 'mom12']:
            Z = dec(Y, col); g = Z.groupby('dec')
            m[f'{lab}|{col}_f12_d1'] = g.f12.mean()[1]; m[f'{lab}|{col}_f12_d10'] = g.f12.mean()[10]
            m[f'{lab}|{col}_crolli_d1'] = g.L50.mean()[1]; m[f'{lab}|{col}_crolli_d10'] = g.L50.mean()[10]
    for d in ['2008-12-31', '2009-03-31']:
        Y = H[H.date == d]; ex = Y.p52 < 0.4
        m[f'{d}|n_sotto40'] = int(ex.sum()); m[f'{d}|quota_sotto40'] = ex.mean()
        m[f'{d}|f12_sotto40'] = Y[ex].f12.mean(); m[f'{d}|f12_altri'] = Y[~ex].f12.mean()
        m[f'{d}|crolli_sotto40'] = Y[ex].L50.mean(); m[f'{d}|crolli_altri'] = Y[~ex].L50.mean()
    yt = H.groupby('anno').apply(lambda z: z[z.p52 < 0.4].L50.mean() / z.L50.mean())
    for y, v in yt.items(): m[f'anno{y}|rapporto_sotto40'] = v
    S = H[~H.uscita_pre2011]
    m['sopravvissute|f12_pesi_uguali'] = ew(S); m['sopravvissute|crolli'] = S.L50.mean()
    m['sopravvissute|rapporto_sotto40'] = S[S.p52 < 0.4].L50.mean() / S.L50.mean()
    return m


def full_tables(U, lab):
    H = U[U.storico]
    say(f'\n################ {lab}: {len(H) / H.date.nunique():.0f} titoli per data, {H.t.nunique()} titoli distinti, '
        f'{H.uscita_pre2011.mean():.1%} righe di societa uscite prima di meta 2011 ################')
    for blk in BLK + ['2000-11']:
        X = H if blk == '2000-11' else H[H.blocco == blk]
        t = band_table(X); r = t.loc['<40%', 'crolli'] / X.L50.mean()
        say(f'\n-- {blk}: crolli medi {X.L50.mean():.3f}, a -100% {(X.f12 <= -0.999).mean():.3f}, rendimento a pesi uguali {ew(X):+.3f}')
        say(t.round(3).to_string())
        say(f'   sotto il 40%: crolli = {r:.2f} volte la media -> criterio (>=2) {"SUPERATO" if r >= 2 else "NON superato"}')
    for lab2, a, b in [('bolla internet 03/2000-09/2002', '2000-03-31', '2002-09-30'), ('crisi 2008: 09/2007-12/2008', '2007-09-30', '2008-12-31'),
                       ('rimbalzo 12/2008-06/2009', '2008-12-31', '2009-06-30')]:
        Y = H[(H.date >= a) & (H.date <= b)]
        say(f'\n-- {lab2}: titoli per data {len(Y) / Y.date.nunique():.0f}, crolli {Y.L50.mean():.3f}, rendimento a pesi uguali {ew(Y):+.3f}')
        say(band_table(Y).round(3).to_string())
    say('\n-- date singole')
    for d in ['2000-03-31', '2000-12-31', '2001-06-30', '2002-03-31', '2007-12-31', '2008-06-30', '2008-09-30', '2008-12-31', '2009-03-31', '2009-06-30']:
        Y = H[H.date == d]; a = Y[Y.p52 < 0.4]; b = Y[Y.p52 >= 0.4]
        say(f'  {d}: sotto 40% = {len(a)} ({len(a) / max(len(Y), 1):.0%}), crolli {a.L50.mean():.2f} / {b.L50.mean():.2f}, '
            f'f12 {a.f12.mean():+.2f} / {b.f12.mean():+.2f}, eccezionali {a.W5.mean():.2f} / {b.W5.mean():.2f}')
    for col, lab2 in [('vol', 'Volatilita 1 anno'), ('mom12', 'Momentum 12-1'), ('mom6', 'Momentum 6-1')]:
        say(f'\n=== {lab2}: decili (1 = piu basso) ===')
        s = ic_series(H, col); yr = (s.index + pd.Timedelta(days=1)).year
        say('IC ' + ' | '.join(f'{p}: {s[(yr >= a) & (yr <= b)].mean():+.3f} (t {hh_t(s[(yr >= a) & (yr <= b)]):+.1f})'
                               for p, a, b in [('2000-11', 2000, 2011), ('2000-03', 2000, 2003), ('2004-07', 2004, 2007), ('2008-11', 2008, 2011)]))
        say('   per anno: ' + ' '.join(f'{y}:{v:+.2f}' for y, v in s.groupby(yr).mean().items()))
        for per in ['2000-11'] + BLK + ['rimbalzo']:
            X = H if per == '2000-11' else (H[(H.date >= '2008-12-31') & (H.date <= '2009-06-30')] if per == 'rimbalzo' else H[H.blocco == per])
            Y = dec(X, col)
            t = Y.groupby('dec').agg(f12=('f12', 'mean'), crolli=('L50', 'mean'), disastri=('L20', 'mean'), eccezionali=('W5', 'mean'))
            say(f'-- {per}'); say(t.T.round(3).to_string())
    say('\n=== Guardia (solo prezzo) ===')
    for per in BLK:
        Y = H[H.blocco == per]; ex = Y.p52 < 0.4
        say(f'{per}: esclusi {ex.mean():.1%}, crolli {Y[ex].L50.mean():.3f} / {Y[~ex].L50.mean():.3f}, eccezionali {Y[ex].W5.mean():.3f} / '
            f'{Y[~ex].W5.mean():.3f}, f12 medio {Y[ex].f12.mean():+.3f} / {Y[~ex].f12.mean():+.3f}, ammessi a pesi uguali {ew(Y[~ex]):+.3f} contro tutti {ew(Y):+.3f}')
    yt = H.groupby('anno').apply(lambda z: pd.Series({'quota_sotto40': (z.p52 < 0.4).mean(), 'crolli_sotto40': z[z.p52 < 0.4].L50.mean(),
                                                      'crolli_media': z.L50.mean(), 'f12_sotto40': z[z.p52 < 0.4].f12.mean(), 'f12_pu': ew(z)}))
    yt['rapporto'] = yt.crolli_sotto40 / yt.crolli_media
    say('\n-- anno per anno'); say(yt.round(3).to_string())


if __name__ == '__main__':
    U1 = pd.read_pickle(f'{OUT}/universo_prezzi_us.pkl')
    U2 = pd.read_pickle(f'{OUT}/universo_prezzi_us_v2.pkl')
    P = pd.read_pickle(f'{OUT}/pannello_prezzi_us_v2.pkl')
    P = P[P.date <= '2011-09-30'].reset_index(drop=True)
    U2r = build(P)
    say(f'controllo: v2 ricostruito {int(U2r.storico.sum())} righe 2000-11, file {int(U2.storico.sum())}')
    C = pd.read_pickle(f'{OUT}/volumi_corretti_A.pkl').set_index(['t', 'date'])
    k = pd.MultiIndex.from_frame(P[['t', 'date']])
    j = C.reindex(k)
    Pp = P.copy(); has = j.dv_raw.notna().values
    Pp.loc[has, 'dv63'] = np.minimum(P.dv63.values[has], j.dv_raw.values[has])
    Pp.loc[has, 'px'] = np.minimum(P.px.values[has], j.px_p.values[has])
    Pv = P.copy(); hv = j.dv63_v.notna().values
    Pv.loc[hv, 'dv63'] = j.dv63_v.values[hv]; Pv.loc[hv, 'px'] = j.px_v.values[hv]
    U2p = build(Pp); U2v = build(Pv)
    U2ad = finish(U2[~U2.nuova])
    UN = {'v1': U1, 'v2': U2, 'v2_AD': U2ad, 'v2_prud': U2p, 'v2_stima': U2v}
    for nm, U in UN.items():
        H = U[U.storico]
        say(f'{nm:9s}: righe 2000-11 {len(H):6d}, titoli per data {len(H) / H.date.nunique():.0f}, distinti {H.t.nunique()}')
    # chi esce con i valori prudenti
    H2 = U2[U2.storico]; Hp = U2p[U2p.storico]
    kk = lambda X: list(zip(X.date, X.f12.round(3), X.p52.round(2)))      # stessa riga anche se tenuta con un altro codice
    keyp = set(kk(Hp))
    out_rows = H2[[x not in keyp for x in kk(H2)]]
    say(f'\nrighe v2 che escono con i valori prudenti: {len(out_rows)} ({len(out_rows) / len(H2):.1%}); per origine '
        f'{out_rows.src.value_counts().to_dict()}; crolli {out_rows.L50.mean():.3f} contro {H2.L50.mean():.3f}; f12 medio {out_rows.f12.mean():+.3f}')
    g = out_rows.groupby('t').agg(nome=('name', 'first'), borsa=('borsa', 'first'), src=('src', 'first'), n=('date', 'size'),
                                  crolli=('L50', 'sum'))
    say(g.sort_values('n', ascending=False).head(25).to_string())
    M = pd.DataFrame({nm: metrics(U) for nm, U in UN.items()})
    M.to_csv(f'{OUT}/confronto_A.csv')
    say('\n=== CONFRONTO ==='); say(M.round(3).to_string())
    for nm in ['v2', 'v2_prud', 'v1']:
        full_tables(UN[nm], nm)
    OUTF.close()
