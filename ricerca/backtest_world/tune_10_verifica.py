# tune_10 (07/11): verifica della proposta del 06/11 sui dati allargati (piccole e medie USA, doppioni tolti, pence corretti).
# Nessuna soglia viene ritoccata: core, radar A e radar B sono quelli fissati ieri. Prove nuove (tutte elencate in fondo):
# tetti di settore/regione nella top 30, guardia sul PEG quasi nullo, margine lordo / R&S / sorprese come segnali.
import math, sys, pandas as pd, numpy as np
from tune_common import run, cagr, tstat, mask, BASE_P, score, PERIODS, BASE
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500); pd.set_option('display.max_columns', 30)
F = pd.read_pickle(f'{BASE}/res/panel2.pkl').reset_index(drop=True)
REB = sorted(F.date.unique())
UNI = ~F.excl_sector
PALL = {**PERIODS, '2012-26': ('2011-12-31', '2026-09-30')}
OLD = ~F.us_new                       # universo del 06/11 (senza le piccole/medie USA aggiunte oggi)
A = mask(F, BASE_P)                   # GARP attuale
CORE = mask(F, dict(BASE_P, revq=0.20)) & (F.hi52 >= 0.8).fillna(False)
RADA = UNI & ~A & (F.revq > 0.40).fillna(False) & (F.rev_cagr > 0.15).fillna(False) & (F.dshares < 0.10).fillna(True)
RADB = UNI & (F.n_fail == 1) & ~F['ok_PEG']
REGS = {'Mondo': UNI, 'USA tutte': UNI & (F.reg == 'USA'), 'USA grandi (06/11)': UNI & (F.reg == 'USA') & OLD,
        'USA piccole/medie (nuove)': UNI & F.us_new, 'Europa': UNI & (F.reg == 'Europa'), 'Asia': UNI & (F.reg == 'Asia'),
        'Mondo senza nuove USA (= 06/11)': UNI & OLD}


def maxdd(r): w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()


def ev(name, m, univ, top=None, tag=''):
    sc = score(F, m & univ) if top else None
    r, n = run(F, m & univ, topn=top, score=sc)
    u, _ = run(F, univ)
    u = pd.Series({t: F.loc[univ & (F.date == t), 'r_eur'].mean() for t in REB})   # universo senza costi
    out = []
    for p, (a, b) in PALL.items():
        ds = [d for d in REB if pd.Timestamp(a) <= d <= pd.Timestamp(b)]
        X = F[m & univ & (F.date >= a) & (F.date <= b) & F.f12.notna()]
        out.append(dict(gruppo=tag, variante=name, periodo=p, n=min(n[ds].mean(), top or 1e9), cagr=cagr(r, a, b), univ=cagr(u, a, b),
                        diff=cagr(r, a, b) - cagr(u, a, b), t=tstat((r - u)[ds]), maxdd=maxdd(r[ds]), W5=X.W5.mean(), L20=X.L20.mean()))
    return out, r, u


ROWS, SER = [], {}
if 'base' in sys.argv or len(sys.argv) == 1:
    for reg, U in REGS.items():
        for name, m, top in [('GARP attuale lista', A, None), ('GARP attuale top 30', A, 30), ('Core', CORE, None),
                             ('Radar A', RADA, None), ('Radar B', RADB, None), ('Universo', U, None)]:
            if reg not in ('Mondo', 'Mondo senza nuove USA (= 06/11)') and top: continue
            o, r, u = ev(name, m, U, top, reg); ROWS += o; SER[(reg, name)] = r
        print(reg, flush=True)
    T = pd.DataFrame(ROWS); T.to_csv(f'{BASE}/res/v10_base.csv', index=False)
    print(T.pivot_table(index=['gruppo', 'variante'], columns='periodo', values=['n', 'cagr', 'diff', 't'], sort=False).round(3).to_string())
    print(T[T.periodo == '2012-26'][['gruppo', 'variante', 'maxdd', 'W5', 'L20']].round(3).to_string())
    # anno per anno, mondo
    def annual(r):
        y = r.copy(); nx = {t: (REB[i + 1] if i + 1 < len(REB) else pd.Timestamp('2026-11-06')) for i, t in enumerate(REB)}
        y.index = [nx[t] for t in r.index]; y.index = [d.year if (d.month > 1 or d.day > 15) else d.year - 1 for d in pd.to_datetime(y.index)]
        return (1 + y).groupby(level=0).prod() - 1
    Y = pd.DataFrame({k[1]: annual(v) for k, v in SER.items() if k[0] == 'Mondo'})
    Y.to_csv(f'{BASE}/res/v10_annuali.csv'); print(Y.round(3).to_string())
    # concentrazione: settori e paesi nel core
    for p in PERIODS:
        X = F[CORE & UNI & (F.per == p)]
        print('core', p, 'settori', X.sector.value_counts(normalize=True).head(3).round(2).to_dict(), 'regioni', X.reg.value_counts(normalize=True).round(2).to_dict())

if 'caso' in sys.argv or len(sys.argv) == 1:
    # estrazioni a caso, stessa numerosita' per data, rendimento lordo (senza costi) per non penalizzare la rotazione del caso
    rng = np.random.default_rng(7)
    R = F.r_eur.values
    def gross(mm):
        g = F[mm].groupby('date').r_eur.mean().reindex(REB).fillna(0.0); return g
    rows = []
    for name, m, pools in [('Core', CORE, [('dentro GARP attuale', A), ('dentro universo', UNI)]),
                           ('Radar A', RADA, [('dentro universo fuori GARP', UNI & ~A)]), ('Radar B', RADB, [('dentro universo', UNI)])]:
        for reg in ['Mondo', 'USA tutte', 'USA piccole/medie (nuove)', 'Europa', 'Asia']:
            U = REGS[reg]
            cnt = F[m & U].groupby('date').size()
            real = gross(m & U)
            for pn, pool in pools:
                G = {t: x.index.values for t, x in F[pool & U].groupby('date')}
                sims = {p: [] for p in PALL}
                for it in range(400):
                    g = {}
                    for t in REB:
                        k = cnt.get(t, 0); idx = G.get(t, np.array([]))
                        g[t] = R[rng.choice(idx, min(k, len(idx)), replace=False)].mean() if k and len(idx) else 0.0
                    g = pd.Series(g)
                    for p, (a, b) in PALL.items(): sims[p].append(cagr(g, a, b))
                for p, (a, b) in PALL.items():
                    v = cagr(real, a, b); s = np.array(sims[p])
                    rows.append(dict(variante=name, regione=reg, pool=pn, periodo=p, reale_lordo=v, caso_mediana=np.median(s),
                                     caso_p5=np.percentile(s, 5), caso_p95=np.percentile(s, 95), batte=np.mean(s < v)))
            print(name, reg, flush=True)
    C = pd.DataFrame(rows); C.to_csv(f'{BASE}/res/v10_caso.csv', index=False)
    print(C.round(3).to_string())

if 'tetti' in sys.argv or len(sys.argv) == 1:
    def capped(m, keys, cap=0.4, n=30):
        sc = score(F, m)
        d = F[m].assign(_s=sc[m]).sort_values(['date', '_s'], ascending=[True, False])
        keep = []
        for t, x in d.groupby('date'):
            N = min(n, len(x)); lim = max(1, math.floor(cap * N)); cnt = {}; sel = []
            for i, vals in zip(x.index, x[keys].fillna('NA').itertuples(index=False)):
                if all(cnt.get((k, v), 0) < lim for k, v in zip(keys, vals)):
                    sel.append(i)
                    for k, v in zip(keys, vals): cnt[(k, v)] = cnt.get((k, v), 0) + 1
                if len(sel) == N: break
            keep += sel
        out = pd.Series(False, index=F.index); out[keep] = True; return out
    G = F.peg >= 0.05
    rows = []
    for base, m in [('GARP attuale', A), ('Core', CORE)]:
        for nm, mm in [('top 30 senza tetti', None), ('tetto settore 40%', ['sector']), ('tetto regione 40%', ['reg']),
                       ('tetto settore e regione 40%', ['sector', 'reg']), ('tetto industria 40%', ['industry']),
                       ('guardia PEG<0,05 = mancante', 'G')]:
            if mm is None: sel = capped(m, ['ex'], cap=1.0)
            elif mm == 'G': sel = capped(m & G.fillna(False), ['ex'], cap=1.0)
            else: sel = capped(m, mm)
            r, n = run(F, sel); u, _ = run(F, UNI)
            for p, (a, b) in PALL.items():
                ds = [d for d in REB if pd.Timestamp(a) <= d <= pd.Timestamp(b)]
                X = F[sel & (F.date >= a) & (F.date <= b)]
                rows.append(dict(base=base, variante=nm, periodo=p, n=n[ds].mean(), cagr=cagr(r, a, b), diff_univ=cagr(r, a, b) - cagr(u, a, b),
                                 maxdd=maxdd(r[ds]), quota_tech=(X.sector == 'Technology').mean(), quota_usa=(X.reg == 'USA').mean(),
                                 vol=r[ds].std() * 2))
            SER[(base, nm)] = r
        print(base, flush=True)
    T = pd.DataFrame(rows)
    for base in ['GARP attuale', 'Core']:
        ref = T[(T.base == base) & (T.variante == 'top 30 senza tetti')].set_index('periodo').cagr
        T.loc[T.base == base, 'vs_senza_tetti'] = T[T.base == base].apply(lambda x: x.cagr - ref[x.periodo], axis=1)
    for base in ['GARP attuale', 'Core']:   # t della differenza trimestrale rispetto a "senza tetti"
        for nm in T.variante.unique():
            d = SER[(base, nm)] - SER[(base, 'top 30 senza tetti')]
            for p, (a, b) in PALL.items():
                ds = [x for x in REB if pd.Timestamp(a) <= x <= pd.Timestamp(b)]
                T.loc[(T.base == base) & (T.variante == nm) & (T.periodo == p), 't_vs_senza'] = tstat(d[ds])
    T.to_csv(f'{BASE}/res/v10_tetti.csv', index=False)
    print(T.round(3).to_string())
    # PEG quasi nullo: quanti e come vanno
    X = F[A & F.f12.notna()]
    lo = X.peg < 0.05
    med = F.groupby('date').f12.transform('median')
    print('PEG<0,05 fra i promossi: quota', round(lo.mean(), 3), 'per data', round(F[A & (F.peg < 0.05)].groupby('date').size().mean(), 1))
    for k, Z in [('PEG<0,05', X[lo]), ('PEG 0,05-2', X[~lo])]:
        print(k, 'extra f12 vs mediana: media', round((Z.f12 - med[Z.index]).mean(), 3), 'mediana', round((Z.f12 - med[Z.index]).median(), 3),
              'W5', round(Z.W5.mean(), 3), 'L20', round(Z.L20.mean(), 3), 'crescita EPS mediana', round(Z.epsg.median(), 2))
    sc = score(F, A); top = F[A].assign(_s=sc[A]).sort_values(['date', '_s'], ascending=[True, False]).groupby('date').head(30)
    print('nella top 30 attuale quota PEG<0,05:', round((top.peg < 0.05).mean(), 3))

if 'segnali' in sys.argv or len(sys.argv) == 1:
    CTRL = {'peg': -1, 'revq': 1, 'epsq': 1, 'rev_cagr': 1, 'roe': 1, 'fcfy': 1, 'de': -1}
    F['rd0'] = F.rd_int.where(F.rd_int.notna(), np.where(F.gm.notna(), 0.0, np.nan))
    SIG = {'margine lordo (livello)': ('gm', 1), 'margine lordo (variazione 1 anno)': ('d_gm', 1), 'R&S / ricavi': ('rd0', 1),
           'spese generali / ricavi': ('sga_int', -1), 'liquidita\' corrente (att./pass. correnti)': ('cur_ratio', 1),
           'sorpresa utili ultima': ('surp_last', 1), 'sorpresa utili media 4 trim.': ('surp_mean4', 1),
           'trimestri sopra le stime (su 4)': ('n_beat4', 1), 'anni dalla quotazione': ('age_y', 1), 'variazione azioni (controllo)': ('dshares', -1)}
    def prank(s): return ((s.rank(method='average') - 0.5) / s.notna().sum()).fillna(0.5)
    def fm(X, col, sgn, mn=25):
        co = []
        for t, x in X.groupby('date'):
            if len(x) < mn or x[col].notna().sum() < mn * 0.6: continue
            y = x.f12.rank(pct=True).values
            Z = np.column_stack([np.ones(len(x))] + [prank(x[c] * s).values for c, s in CTRL.items()] + [prank(x[col].astype(float) * sgn).values])
            co.append((t, np.linalg.lstsq(Z, y, rcond=None)[0][-1]))
        return pd.Series(dict(co), dtype=float)
    def quint(X, col, sgn):
        q = X.groupby('date')[col].transform(lambda s: (s.astype(float) * sgn).rank(pct=True))
        hi, lo = X[q > 0.8], X[q <= 0.2]
        med = X.groupby('date').f12.transform('median')
        return hi.W5.mean(), lo.W5.mean(), hi.L20.mean(), lo.L20.mean(), (hi.f12 - med[hi.index]).median() - (lo.f12 - med[lo.index]).median()
    POPS = {'USA universo': UNI & (F.reg == 'USA') & F.new_fields.astype(bool), 'Quasi-GARP mondo (<=2 filtri falliti)': UNI & (F.n_fail <= 2) & F.new_fields.astype(bool)}
    rows = []
    for pop, P in POPS.items():
        D = F[P & F.f12.notna()]
        groups = [('tutto', D)] + [(p, D[D.per == p]) for p in PERIODS]
        groups += [(r, D[D.reg == r]) for r in ['USA', 'Europa', 'Asia']] if pop.startswith('Quasi') else [('USA piccole/medie', D[D.mcap_usd < 10e9]), ('USA grandi', D[D.mcap_usd >= 10e9])]
        for name, (col, sgn) in SIG.items():
            for g, X in groups:
                s = fm(X, col, sgn, 25 if pop.startswith('Quasi') or g != 'USA grandi' else 15)
                q = quint(X, col, sgn)
                rows.append(dict(popolazione=pop, segnale=name, gruppo=g, copertura=X[col].notna().mean(), coef=s.mean(), t=tstat(s) / 2,
                                 W5_alto=q[0], W5_basso=q[1], L20_alto=q[2], L20_basso=q[3], spread_mediano=q[4], n_date=len(s)))
            print(pop, name, flush=True)
    S = pd.DataFrame(rows); S.to_csv(f'{BASE}/res/v10_segnali.csv', index=False)
    for pop in POPS:
        Z = S[S.popolazione == pop]
        print(pop); print(Z.pivot(index='segnale', columns='gruppo', values='coef').round(3).to_string())
        print(Z[Z.gruppo == 'tutto'][['segnale', 'copertura', 't', 'W5_alto', 'W5_basso', 'L20_alto', 'L20_basso', 'spread_mediano']].round(3).to_string())
    # filtri di portafoglio con margine lordo e R&S, sopra il core e il GARP attuale (soglie semplici, fissate prima di guardare)
    gmed = F[UNI].groupby('date').gm.transform('median').reindex(F.index)
    gmed = F.date.map(F[UNI].groupby('date').gm.median())
    rows = []
    for base, m in [('GARP attuale', A), ('Core', CORE)]:
        cov = F[m].gm.notna().mean()
        for nm, extra in [('nessun filtro in piu\'', True), ('margine lordo sopra la mediana', (F.gm >= gmed).fillna(False)),
                          ('margine lordo in aumento', (F.d_gm > 0).fillna(False)), ('R&S > 0', (F.rd0 > 0).fillna(False))]:
            r, n = run(F, m & extra); u, _ = run(F, UNI)
            for p, (a, b) in PALL.items():
                ds = [d for d in REB if pd.Timestamp(a) <= d <= pd.Timestamp(b)]
                rows.append(dict(base=base, filtro=nm, copertura_gm=cov, periodo=p, n=n[ds].mean(), cagr=cagr(r, a, b), diff_univ=cagr(r, a, b) - cagr(u, a, b)))
            SER[(base, nm)] = r
        for nm in ['margine lordo sopra la mediana', 'margine lordo in aumento', 'R&S > 0']:
            d = SER[(base, nm)] - SER[(base, "nessun filtro in piu'")]
            for p, (a, b) in PALL.items():
                ds = [x for x in REB if pd.Timestamp(a) <= x <= pd.Timestamp(b)]
                rows.append(dict(base=base, filtro=nm + ' [t vs base]', periodo=p, cagr=tstat(d[ds])))
    P = pd.DataFrame(rows); P.to_csv(f'{BASE}/res/v10_filtri_gm.csv', index=False)
    print(P.pivot_table(index=['base', 'filtro'], columns='periodo', values=['n', 'cagr', 'diff_univ'], sort=False).round(3).to_string())
