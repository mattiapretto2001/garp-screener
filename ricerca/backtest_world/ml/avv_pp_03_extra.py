# avv_pp_03: portafogli realistici per 8.000 EUR (numero di titoli limitato) per Crescita, Qualita e misto;
# controllo dei tempi di pubblicazione dei bilanci; crolli contati per titolo e non per riga.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    from avv_pp_01_repro import *
def port_n(m, N, seed, cost_fixed=5.0, pct=0.003, capital=8000.0, dates=D18):
    rng = np.random.default_rng(seed)
    X = F[m & F.date.isin(dates)][['t', 'date', 'r_eur']]
    G = {d: x.set_index('t').r_eur for d, x in X.groupby('date')}
    hold, out, V = [], {}, capital
    for d in dates:
        s = G.get(d, pd.Series(dtype=float))
        keep = [t for t in hold if t in s.index]
        cand = [t for t in s.index if t not in keep]
        add = list(rng.choice(cand, min(N - len(keep), len(cand)), replace=False)) if cand and len(keep) < N else []
        new = keep + add
        ns, nb = len(set(hold) - set(new)), len(add)
        g = s[new].mean() if new else 0.0
        cost = (ns + nb) * cost_fixed / V + pct * ((ns / len(hold) if hold else 0) + (nb / len(new) if new else 0))
        r = g - cost; out[d] = r; V *= 1 + r; hold = new
    return pd.Series(out)

print('==================== PARTE 3')
U_g, U_b2, U_q5, U_q = uni(UNI), uni(UNI & B2), uni(QU & B5), uni(QU)
for fx, pc, lab in [(5, 0.003, '5 EUR + 0,3%'), (10, 0.005, '10 EUR + 0,5%')]:
    for nm, m, U, N, cap in [('core 12 titoli', CORE & UNI, U_g, 12, 8000), ('Crescita >=2, 15 titoli', CR & B2 & UNI, U_b2, 15, 8000),
                             ('Qualita Q3, 15 titoli', Q3 & QU & B5, U_q5, 15, 8000)]:
        v = np.array([ann(port_n(m, N, s, fx, pc, capital=cap)) - ann(U) for s in range(150)]) * 100
        print(f'{lab:14s} {nm:26s} mediana {np.median(v):+.1f}  10%-90% [{np.percentile(v,10):+.1f}, {np.percentile(v,90):+.1f}]  sotto zero {np.mean(v<0):.0%}', flush=True)
    # misto: 4.000 EUR core (8 titoli) + 4.000 EUR Q3 (8 titoli)
    v = []
    for s in range(150):
        a = port_n(CORE & UNI, 8, s, fx, pc, capital=4000); b = port_n(Q3 & QU & B5, 8, 1000 + s, fx, pc, capital=4000)
        v.append(ann(0.5 * a + 0.5 * b) - ann(U_q))
    v = np.array(v) * 100
    print(f'{lab:14s} {"misto 8 core + 8 Q3":26s} mediana {np.median(v):+.1f}  10%-90% [{np.percentile(v,10):+.1f}, {np.percentile(v,90):+.1f}]  sotto zero {np.mean(v<0):.0%}', flush=True)

# tempi di pubblicazione: giorni fra fine periodo e data usata, per i bilanci usati dal core (USA e resto)
V = fv3.load(cols=['t', 'date', 'fin_end', 'fin_av'])
X = F[CORE & UNI & F.date.isin(D18)][['t', 'date', 'ex']].merge(V, on=['t', 'date'], how='left')
lag = (pd.to_datetime(X.fin_av) - pd.to_datetime(X.fin_end)).dt.days
print('\nritardo (giorni) fra chiusura del periodo e data in cui il dato e usato, righe del core:')
print(pd.DataFrame({'USA': lag[X.ex == 'US'].describe(percentiles=[.05, .25, .5]), 'altri': lag[X.ex != 'US'].describe(percentiles=[.05, .25, .5])}).round(0).to_string())
print('quota righe USA con ritardo esattamente 45 giorni (data di deposito mancante o anteriore): %.0f%%' % (100 * (lag[X.ex == 'US'] == 45).mean()))
print('quota righe con ritardo < 30 giorni: %.1f%%' % (100 * (lag < 30).mean()))

# crolli contati per titolo
for nm, m in [('Crescita >=2', CR & B2 & UNI), ('Radar A', None), ('core', CORE & UNI), ('Q3', Q3 & QU & B5)]:
    if m is None:
        from pp_common import RADA; m = RADA & UNI & B2
    X = F[m & F.date.isin(D18) & F.crash50.notna()]
    c = X[X.crash50 == 1]
    yr = c.date.dt.year.value_counts().sort_index().to_dict()
    print(f'{nm}: righe {len(X)}, righe in crollo {len(c)}, titoli diversi in crollo {c.t.nunique()}, per anno della data {yr}')
