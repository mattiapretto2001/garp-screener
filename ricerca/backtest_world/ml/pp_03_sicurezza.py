# pp_03: effetto delle NUOVE regole di sicurezza sulle liste, periodo pulito (e 2012-17 per confronto).
#  guardia = escludere prezzo < 40% del massimo a 52 sett. o azioni +25% in un anno;
#  stime mancate = retrocedere chi ha battuto al massimo 1 stima su 4 (variante: ultima trimestrale mancata).
from pp_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500); pd.set_option('display.max_columns', 40)
PER = {**PP, '2012-17': OLDP['2012-17']}
REGS = {'Mondo': ALL, 'USA grandi': REG['USA grandi'], 'USA piccole/medie': REG['USA piccole/medie'], 'Europa': REG['Europa'], 'Asia': REG['Asia']}
VARS = {'base': (None, None), 'guardia': (GUARD, None), 'stime mancate': (None, MISS), 'guardia + stime mancate': (GUARD, MISS),
        'variante: ultima trimestrale mancata': (None, MISS2), 'guardia + ultima mancata': (GUARD, MISS2)}


def build(name, m, univ, ex, dm, R):
    """lista con le regole: ex = esclusi, dm = retrocessi (tolti dalle liste intere, in fondo nella top 30)"""
    if name.startswith('Top 30'):
        base = A & B2 & univ & R
        if ex is not None: base = base & ~ex
        return topn(base, 30, demote=dm)
    mm = m & univ & R
    if ex is not None: mm = mm & ~ex
    if dm is not None: mm = mm & ~dm
    return mm


rows, SER = [], {}
for reg, R in REGS.items():
    for name, (m, univ) in list(LISTS.items()) + [('50% core + 50% Q3', (None, None))]:
        if name.startswith('Top 30') and reg != 'Mondo': continue
        if reg != 'Mondo' and not any(k in name for k in ('core', 'Crescita >=2', 'Q3', 'Radar', 'GARP larga', 'Crescita piccole')): continue
        for vn, (ex, dm) in VARS.items():
            if reg != 'Mondo' and vn.startswith('variante'): continue
            if name == '50% core + 50% Q3':
                mc_ = build('GARP core', CORE, UNI, ex, dm, R); mq_ = build('Qualita Q3', Q3, QU & B5, ex, dm, R)
                rc, nc = run(F, mc_); rq, nq = run(F, mq_)
                r = 0.5 * rc + 0.5 * rq; n = nc + nq; mm = mc_ | mq_; univ_ = QU & R
                base_m = (CORE & UNI & R) | (Q3 & QU & B5 & R)
            else:
                mm = build(name, m, univ, ex, dm, R); r, n = run(F, mm); univ_ = univ & R
                base_m = build(name, m, univ, None, None, R)
            u = useries(univ_)
            SER[(reg, name, vn)] = r
            rb = SER[(reg, name, 'base')]
            removed = base_m & ~mm
            for p in PER:
                ds = dates(p); a, b = ALLP[p]
                sel = F.date.between(pd.Timestamp(a), pd.Timestamp(b)) & F.crash50.notna()
                X = F[mm & sel]; Rm = F[removed & sel]; Bm = F[base_m & sel]
                med = F[univ_ & sel].groupby('date').f12.median()
                rows.append(dict(regione=reg, lista=name, variante=vn, periodo=p, n=n.reindex(ds).mean(), cagr=cagr(r, a, b),
                                 diff_univ=cagr(r, a, b) - cagr(u, a, b), vs_base=cagr(r, a, b) - cagr(rb, a, b),
                                 t_vs_base=nw((r - rb)[ds]), maxdd=maxdd(r[ds]), r2022=year_ret(r, 2022),
                                 crolli=X.crash50.mean(), perdenti=X.L20.mean(), eccez=X.W5.mean(),
                                 quota_tolti=len(Rm) / len(Bm) if len(Bm) else np.nan,
                                 tolti_crolli=Rm.crash50.mean() if len(Rm) else np.nan, tolti_eccez=Rm.W5.mean() if len(Rm) else np.nan,
                                 tolti_perdenti=Rm.L20.mean() if len(Rm) else np.nan,
                                 tolti_extra_mediano=(Rm.f12 - Rm.date.map(med)).median() if len(Rm) else np.nan,
                                 tenuti_extra_mediano=(X.f12 - X.date.map(med)).median() if len(X) else np.nan))
    print(reg, flush=True)
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/pp_03_sicurezza.csv', index=False)
W = T[T.regione == 'Mondo']
print(W.pivot_table(index=['lista', 'variante'], columns='periodo', values='vs_base', sort=False).round(3).to_string())
print(W[W.periodo == '2018-26'][['lista', 'variante', 'n', 'diff_univ', 'vs_base', 't_vs_base', 'maxdd', 'r2022', 'crolli', 'perdenti', 'eccez',
                                  'quota_tolti', 'tolti_crolli', 'tolti_eccez', 'tolti_perdenti', 'tolti_extra_mediano', 'tenuti_extra_mediano']].round(3).to_string())
print(W[W.periodo == '2012-17'][['lista', 'variante', 'vs_base', 't_vs_base', 'quota_tolti', 'tolti_crolli']].round(3).to_string())
Z = T[(T.periodo == '2018-26') & (T.variante != 'base')]
print(Z.pivot_table(index=['lista', 'variante'], columns='regione', values='vs_base', sort=False).round(3).to_string())
print(Z.pivot_table(index=['lista', 'variante'], columns='regione', values='t_vs_base', sort=False).round(2).to_string())

# effetto sulle intere popolazioni (universo GARP e >= 2 Mld$): togliere i nomi segnalati
rows = []
for un, U in [('Universo GARP', UNI), ('Universo >=2 Mld$', UNI & B2)]:
    for reg, R in REGS.items():
        ub = useries(U & R)
        for vn, X in [('senza guardia', ~GUARD), ('senza stime mancate', ~MISS), ('senza entrambe', ~GUARD & ~MISS), ('senza ultima mancata', ~MISS2)]:
            ux = useries(U & R & X)
            for p in PER:
                ds = dates(p); a, b = ALLP[p]
                sel = F.date.between(pd.Timestamp(a), pd.Timestamp(b)) & F.crash50.notna()
                rows.append(dict(universo=un, regione=reg, variante=vn, periodo=p, vs_universo=cagr(ux, a, b) - cagr(ub, a, b),
                                 t=nw((ux - ub)[ds]), quota_tolti=1 - F[U & R & X & sel].shape[0] / max(1, F[U & R & sel].shape[0]),
                                 crolli_tolti=F[U & R & ~X & sel].crash50.mean(), crolli_tenuti=F[U & R & X & sel].crash50.mean(),
                                 eccez_tolti=F[U & R & ~X & sel].W5.mean(), eccez_tenuti=F[U & R & X & sel].W5.mean()))
P = pd.DataFrame(rows); P.to_csv(f'{OUT}/pp_03_popolazioni.csv', index=False)
print(P[P.periodo.isin(['2018-26', '2012-17'])].round(3).to_string())
