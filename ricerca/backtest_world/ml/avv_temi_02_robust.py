# avv_temi_02: robustezza delle regole B / MOM / BM / CALDE: senza 2025-26, senza 2020, senza Asia, senza us_new, senza l'1% migliore,
# solo >=2 Mld$, senza il solare, senza la migliore industria, industrie a peso uguale, pannello ricostruito senza Asia / senza us_new.
from avv_temi_common import *
F = load(); V = pd.read_pickle(f'{OUT}/V.pkl'); C = pd.read_pickle(f'{OUT}/C.pkl')
RULES = ['B', 'MOM', 'BM', 'CALDE']
TG = [('xs3', 1, '3m'), ('xs12_reg', 4, '12m'), ('top5_reg', 4, 'top5'), ('crash50', 4, 'crollo')]
END = {'xs3': 1, 'xs12_reg': 4, 'top5_reg': 4, 'crash50': 4}   # trimestri di esito


def run(C, lab, mask_fn=None, rules=RULES):
    out = []
    for r in rules:
        o = {'variante': lab, 'regola': r}
        for tgt, lag, l in TG:
            X = C if mask_fn is None else C[mask_fn(C, tgt)]
            d, m, t = spread(X, r, tgt, lag); o[l] = round(m, 2); o['t_' + l] = round(t, 2)
        out.append(o)
    return out


def win_end(d, tgt):
    return d + pd.offsets.QuarterEnd(END[tgt])


rows = []
rows += run(C, 'base')
rows += run(C, 'senza esiti nel 2025-26', lambda X, tg: win_end(X.date, tg) <= pd.Timestamp('2024-12-31'))
rows += run(C, 'senza date 2025-26', lambda X, tg: X.date < '2025-01-01')
rows += run(C, 'senza esiti che toccano il 2020', lambda X, tg: (win_end(X.date, tg) <= pd.Timestamp('2019-12-31')) | (X.date >= '2020-12-31'))
rows += run(C, 'senza 2022-26 (solo 2012-21)', lambda X, tg: X.date <= '2021-09-30')
rows += run(C, 'senza Asia (valutazione)', lambda X, tg: X.reg != 'Asia')
rows += run(C, 'senza us_new (valutazione)', lambda X, tg: ~X.us_new.astype(bool))
rows += run(C, 'solo >=2 Mld$', lambda X, tg: X.mcap_usd >= 2e9)
rows += run(C, 'solo >=10 Mld$', lambda X, tg: X.mcap_usd >= 10e9)
# senza l'1% migliore dei rendimenti (per data, sul rendimento che genera l'esito)
q12 = C.groupby('date').fwd12_eur.transform(lambda s: s.quantile(0.99)); q3 = C.groupby('date').r_eur.transform(lambda s: s.quantile(0.99))
rows += run(C, 'senza 1% migliore', lambda X, tg: (X.r_eur < q3.loc[X.index]) if tg == 'xs3' else (X.fwd12_eur < q12.loc[X.index]))
rows += run(C, 'senza il solare', lambda X, tg: X.ind != 'Solar')
# leave-one-industry-out: togliendo l'industria che pesa di piu' nel risultato a 12 mesi di ciascuna regola
for r in RULES:
    Y = C[C.xs12_reg.notna()]
    base = Y.groupby('date').xs12_reg.mean()
    contrib = Y[Y[r]].groupby(['date', 'ind']).xs12_reg.agg(['sum', 'size'])
    nfl = Y[Y[r]].groupby('date').size()
    cont = contrib['sum'] / nfl.reindex(contrib.index.get_level_values(0)).values
    cont = (cont - contrib['size'] / nfl.reindex(contrib.index.get_level_values(0)).values * base.reindex(contrib.index.get_level_values(0)).values)
    best = cont.groupby(level=1).sum().sort_values(); top_ind = best.index[-1] if r != 'CALDE' else best.index[0]
    rows += run(C, f'senza {top_ind}', lambda X, tg, ti=top_ind: X.ind != ti, rules=[r])
R = pd.DataFrame(rows); pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
print(R.to_string(index=False)); R.to_csv(f'{OUT}/02_robust.csv', index=False)
# industrie a peso uguale: media delle industrie segnalate meno media di tutte le industrie (esito = media delle societa' dell'industria)
print('\nIndustrie a peso uguale (ogni industria conta 1):')
I = C.groupby(['ind', 'date']).agg(xs3=('xs3', 'mean'), xs12=('xs12_reg', 'mean'), top5=('top5_reg', 'mean'), cr=('crash50', 'mean')).reset_index()
I = I.merge(V[['ind', 'date'] + RULES], on=['ind', 'date'])
for r in RULES:
    s = []
    for tgt, lag in (('xs3', 1), ('xs12', 4), ('top5', 4), ('cr', 4)):
        Y = I[I[tgt].notna()]; d = (Y[Y[r]].groupby('date')[tgt].mean() - Y.groupby('date')[tgt].mean()).dropna()
        s.append(f'{tgt} {100*d.mean():+.2f} (t {nw_t(d, lag):.2f})')
    print(r, ' | '.join(s))
# pannello ricostruito escludendo Asia, oppure escludendo us_new (cambia composizione e soglia n>=8)
for lab, m in (('pannello senza Asia', F.reg != 'Asia'), ('pannello senza us_new', ~F.us_new.astype(bool))):
    F2 = F[m]; V2 = flags(ind_panel(F2)); C2 = company(F2, V2, RULES)
    print('\n' + lab); print(pd.DataFrame(run(C2, lab)).to_string(index=False))
# periodi, con t NW anche sulle sole date non sovrapposte (una data ogni 4, 4 fasi) per i 12 mesi
print('\nPer periodo, 12 mesi: t NW(4) sulle date sovrapposte e media/minimo dei t sulle 4 serie annuali non sovrapposte')
for r in RULES:
    d, _, _ = spread(C, r, 'xs12_reg', 4)
    for p, (a, b) in fv3.PER3.items():
        s = d[(d.index >= a) & (d.index <= b)]
        ts = []
        for ph in range(4):
            ss = s.iloc[ph::4]
            ts.append(ss.mean() / (ss.std(ddof=1) / np.sqrt(len(ss))) if len(ss) > 2 else np.nan)
        print(f'{r:6s} {p} n={len(s):2d} pp {100*s.mean():+6.2f} tNW {nw_t(s,4):5.2f} | t non sovrapposti: ' + ' '.join(f'{x:5.2f}' for x in ts))
