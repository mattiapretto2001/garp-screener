# tune_08: verifica finale delle proposte. Core: scelta walk-forward (griglia tune_05) e versione prudente; confronto con
# l'attuale (lista e top 30): periodi, anni, perdita massima, regioni, sfoltimento a caso. Radar (tune_06): quanti nomi,
# quota di eccezionali, quota di tutti gli eccezionali catturati, sovrapposizione con una regola tipo Moonshot.
import pandas as pd, numpy as np
from tune_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
F = pd.read_pickle(f'{BASE}/res/tune_panel.pkl')
UNI = ~F.excl_sector
REB = sorted(F.date.unique())


def core(hi, rq, roe, peg):
    return mask(F, dict(BASE_P, revq=rq, roe=roe, peg=peg)) & ((F.hi52 >= hi).fillna(False) if hi else True)


A = mask(F, BASE_P)
C = {'Attuale (lista intera)': (A, None),
     'Attuale top 30 (punteggio)': (A, 30),
     'Walk-forward: max52>=80%, ricavi_q>20%, ROE>10%, PEG<3': (core(0.8, 0.20, 0.10, 3.0), None),
     'Prudente: max52>=80%, ricavi_q>20%, ROE>15%, PEG<2': (core(0.8, 0.20, 0.15, 2.0), None),
     'Solo ricavi_q>20% (resto attuale)': (core(None, 0.20, 0.15, 2.0), None),
     'Solo max52>=80% (resto attuale)': (core(0.8, 0.05, 0.15, 2.0), None)}
ru, _ = run(F, UNI)


def annual(r):
    y = r.copy(); y.index = [nextd(t, REB) for t in r.index]
    y.index = [d.year if (d.month > 1 or d.day > 15) else d.year - 1 for d in pd.to_datetime(y.index)]
    return (1 + y).groupby(level=0).prod() - 1


def maxdd(r): w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()


rows, ANN, SER = [], {}, {}
for name, (m, top) in C.items():
    sc = score(F, m) if top else None
    r, n = run(F, m, topn=top, score=sc)
    SER[name] = r; ANN[name] = annual(r)
    for per, (a, b) in list(PERIODS.items()) + [('2012-26', ('2011-12-31', '2026-09-30'))]:
        ds = [d for d in REB if pd.Timestamp(a) <= d <= pd.Timestamp(b)]
        rows.append(dict(variante=name, periodo=per, n=n[ds].mean() if not top else min(30, n[ds].mean()), cagr=cagr(r, a, b),
                         vs_univ=cagr(r, a, b) - cagr(ru, a, b), t_univ=tstat((r - ru)[ds]), maxdd=maxdd(r[ds]), vol=r[ds].std() * 2))
ANN['Universo'] = annual(ru)
T = pd.DataFrame(rows); T.to_csv(f'{BASE}/res/tune_finale.csv', index=False)
print(T.round(3).to_string())
Y = pd.DataFrame(ANN); Y.to_csv(f'{BASE}/res/tune_finale_annuali.csv'); print(Y.round(3).to_string())
# regioni (portafoglio dentro la regione contro universo della regione)
rows = []
for name, (m, top) in C.items():
    if top: continue
    for reg in ['USA', 'Europa', 'Asia']:
        rm = F.reg == reg
        r, n = run(F, m & rm); u, _ = run(F, UNI & rm)
        for per, (a, b) in PERIODS.items():
            ds = [d for d in REB if pd.Timestamp(a) <= d <= pd.Timestamp(b)]
            rows.append(dict(variante=name, regione=reg, periodo=per, n=n[ds].mean(), cagr=cagr(r, a, b), vs_univ=cagr(r, a, b) - cagr(u, a, b)))
R = pd.DataFrame(rows); R.to_csv(f'{BASE}/res/tune_finale_regioni.csv', index=False)
print(R.pivot_table(index=['variante', 'regione'], columns='periodo', values=['n', 'vs_univ'], sort=False).round(3).to_string())
# sfoltimento a caso: stessa numerosita' per data estratta dalla lista di partenza (attuale per la prudente; ROE>10 PEG<3 per la walk-forward)
rng = np.random.default_rng(5)
for name, pool in [('Prudente: max52>=80%, ricavi_q>20%, ROE>15%, PEG<2', A),
                   ('Walk-forward: max52>=80%, ricavi_q>20%, ROE>10%, PEG<3', mask(F, dict(BASE_P, roe=0.10, peg=3.0)))]:
    m = C[name][0]; cnt = F[m].groupby('date').size()
    P = F[pool]; G = {t: x.index.values for t, x in P.groupby('date')}
    res = {per: [] for per in PERIODS}
    for it in range(500):
        mm = np.zeros(len(F), bool); pos = pd.Series(np.arange(len(F)), index=F.index)
        for t, k in cnt.items():
            idx = G.get(t, np.array([]))
            if len(idx): mm[pos[rng.choice(idx, min(k, len(idx)), replace=False)].values] = True
        r, _ = run(F, pd.Series(mm, index=F.index))
        for per, (a, b) in PERIODS.items(): res[per].append(cagr(r, a, b))
    for per, (a, b) in PERIODS.items():
        v = cagr(SER[name], a, b)
        print(name, per, 'reale', round(v, 3), 'caso 5-50-95', np.percentile(res[per], [5, 50, 95]).round(3), 'batte', round(np.mean(np.array(res[per]) < v), 3))
# settori nella proposta prudente e nell'attuale
for name in ['Attuale (lista intera)', 'Prudente: max52>=80%, ricavi_q>20%, ROE>15%, PEG<2']:
    m = C[name][0]
    print(name); print(F[m].groupby('per').sector.value_counts(normalize=True).groupby(level=0).head(4).round(2).to_string())
# radar scelto (tune_06) e regola tipo Moonshot
best = pd.read_pickle(f'{BASE}/res/tune_radar_best.pkl')['best']
rq, cg, hi, prof, dsh, dop, mc = best
POOL = UNI & ~A
rad = POOL & (F.revq > rq).fillna(False) & (F.rev_cagr > cg).fillna(False) & (F.dshares < dsh).fillna(True)
moon = UNI & (F.revq > 0.25).fillna(False) & (F.hi52 >= 0.7).fillna(False) & (F.ma200 > 1).fillna(False) & F.mcap_usd.between(150e6, 15e9) & (F.dshares < 0.15).fillna(True) & (F.rev_ttm > 100e6 / 1.0)
for name, m in [('Radar', rad), ('Tipo Moonshot', moon), ('Radar non Moonshot', rad & ~moon), ('GARP attuale', A), ('Prudente', C['Prudente: max52>=80%, ricavi_q>20%, ROE>15%, PEG<2'][0])]:
    for per, (a, b) in list(PERIODS.items()) + [('2012-26', ('2011-12-31', '2026-09-30'))]:
        ds = (F.date >= a) & (F.date <= b) & F.f12.notna()
        X = F[m & ds]; tot = F[UNI & ds].W5.sum(); totm = F[UNI & ds & F.f36.notna()].MB3.sum()
        print(f'{name:22s} {per} n/data {X.groupby("date").size().reindex(F[ds].date.unique()).fillna(0).mean():6.1f} W5 {X.W5.mean():.3f} L20 {X.L20.mean():.3f} '
              f'L50 {X.L50.mean():.3f} MB3 {F[m & ds & F.f36.notna()].MB3.mean():.3f} cattura_W5 {X.W5.sum() / tot:.3f} cattura_MB3 {F[m & ds & F.f36.notna()].MB3.sum() / max(totm, 1):.3f}')
print('sovrapposizione radar/moonshot (quota radar anche in moonshot):', round((rad & moon).sum() / rad.sum(), 3))
print('unione GARP+radar cattura W5:', round(F[(A | rad) & UNI & F.f12.notna()].W5.sum() / F[UNI & F.f12.notna()].W5.sum(), 3))
