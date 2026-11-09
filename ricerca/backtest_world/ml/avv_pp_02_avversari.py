# avv_pp_02: prove avversariali sul rapporto del periodo pulito
#  a) regioni USA definite con il futuro? (us_new = lista costruita con gli scambi 2011-2026)
#  b) titoli di Taiwan e Corea (non comprabili con i broker italiani comuni)
#  c) costi realistici per un portafoglio da 8.000 EUR (commissione fissa + cambio/spread)
#  d) portafoglio realistico da 10-12 titoli invece di tutta la lista
#  e) quanti titoli ha il core a ogni data
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from avv_pp_01_repro import *   # rifà anche la parte 1 (veloce)
print('\n==================== PARTE 2')

# ---------------------------------------------------------------- e) numero di titoli del core
n = F[CORE & UNI & F.date.isin(D18)].groupby('date').size().reindex(D18).fillna(0)
print('core, titoli per data 2018-26: min %d, mediana %d, max %d; date con meno di 10 titoli: %d su %d' % (n.min(), n.median(), n.max(), (n < 10).sum(), len(n)))
ncr = F[CR & B2 & UNI & F.date.isin(D18)].groupby('date').size().reindex(D18).fillna(0)
print('Crescita >=2: min %d, mediana %d, max %d' % (ncr.min(), ncr.median(), ncr.max()))

# ---------------------------------------------------------------- a) regioni USA e sguardo al futuro
US = (F.ex == 'US')
S = F[US & UNI & F.date.isin(D18) & F.mcap_usd.between(2e9, 10e9)]
g = S.groupby('us_new').agg(n=('r_eur', 'size'), r_trim=('r_eur', 'mean'), f12=('f12', 'mean'))
print('\nUSA 2-10 Mld$ (stessa taglia alla data): rendimento trimestrale medio per gruppo (us_new=True -> "piccole/medie")')
print(g.round(4).to_string())
# core USA diviso per taglia ALLA DATA invece che per gruppo us_new
for nm, R in [('USA grandi (us_new=False)', US & ~F.us_new), ('USA piccole/medie (us_new=True)', US & F.us_new),
              ('USA >=10 Mld$ alla data', US & (F.mcap_usd >= 10e9)), ('USA 2-10 Mld$ alla data', US & F.mcap_usd.between(2e9, 10e9)), ('USA tutti', US)]:
    r = port(CORE & UNI & R); u = uni(UNI & R & B2)
    k = F[CORE & UNI & R & F.date.isin(D18)].groupby('date').size().reindex(D18).fillna(0).mean()
    print(f'core {nm:34s} {100*(ann(r)-ann(u)):+6.1f} vs universo >=2 Mld$ della stessa fascia; t {nwt((r-u).reindex(D18)):5.2f}; titoli medi {k:.1f}')

# ---------------------------------------------------------------- b) Taiwan e Corea
TWKO = F.ex.isin(['TW', 'KO'])
X = F[CORE & UNI & F.date.isin(D18)]
print('\ncore: quota di righe a Taiwan/Corea %.0f%%' % (100 * X.ex.isin(['TW', 'KO']).mean()))
contrib = (X.r_eur / X.groupby('date').t.transform('size')).groupby(X.t).sum().sort_values(ascending=False)
print('core: primi 10 contributori', [t for t in contrib.index[:10]])
print('quota dei primi 10 contributori a Taiwan/Corea: %d' % sum(t.endswith(('.TW', '.KO')) for t in contrib.index[:10]))
r_noas = port(CORE & UNI & ~TWKO); u_noas = uni(UNI & ~TWKO)
print(f'core senza Taiwan e Corea (lista e universo): {100*(ann(r_noas)-ann(u_noas)):+.1f}, t {nwt((r_noas-u_noas).reindex(D18)):.2f}')
r_mix2 = 0.5 * r_noas + 0.5 * port(Q3 & QU & B5 & ~TWKO)
print(f'misto senza Taiwan e Corea: {100*(ann(r_mix2)-ann(uni(QU & ~TWKO))):+.1f}')
rcr2 = port(CR & B2 & UNI & ~TWKO)
print(f'Crescita >=2 senza Taiwan e Corea: {100*(ann(rcr2)-ann(uni(UNI & B2 & ~TWKO))):+.1f}')

# ---------------------------------------------------------------- c) costi per 8.000 EUR
def port_fee(m, capital=8000.0, fixed=5.0, pct=0.003, dates=D18, nmax=None, seed=None):
    """costo per operazione = fisso EUR + pct (cambio + spread); capitale che cresce col portafoglio; solo entrate/uscite"""
    X = F[m & F.date.isin(dates)][['t', 'date', 'r_eur']]
    G = dict(tuple(X.groupby('date')))
    out, prev, V = {}, set(), capital
    for d in dates:
        x = G.get(d); cur = set(x.t) if x is not None else set()
        g = x.r_eur.mean() if x is not None and len(x) else 0.0
        ns, nb = len(prev - cur), len(cur - prev)
        cost = (ns + nb) * fixed / V + pct * ((ns / len(prev) if prev else 0) + (nb / len(cur) if cur else 0))
        r = g - cost; out[d] = r; V *= 1 + r; prev = cur
    return pd.Series(out)

print('\nCosti per un portafoglio che parte da 8.000 EUR (solo entrate e uscite; il ribilanciamento ai pesi uguali escluso):')
for nm, m, U in [('core', CORE & UNI, uni(UNI)), ('Crescita >=2', CR & B2 & UNI, uni(UNI & B2)), ('Qualita Q3', Q3 & QU & B5, uni(QU & B5))]:
    res = [f'0,5% {100*(ann(port(m))-ann(U)):+.1f}']
    for fx, pc in [(0, 0.01), (5, 0.003), (10, 0.003)]:
        r = port_fee(m, fixed=fx, pct=pc); res.append(f'{fx} EUR + {pc*100:.1f}%: {100*(ann(r)-ann(U)):+.1f}')
    print(f'  {nm:14s}', ' | '.join(res))
# operazioni l'anno
for nm, m in [('core', CORE & UNI), ('Crescita >=2', CR & B2 & UNI), ('Q3', Q3 & QU & B5)]:
    X = F[m & F.date.isin(D18)]; S_ = {d: set(x.t) for d, x in X.groupby('date')}
    tr, prev = 0, set()
    for d in D18:
        cur = S_.get(d, set()); tr += len(prev - cur) + len(cur - prev); prev = cur
    print(f'  {nm}: operazioni (acquisti + vendite) in media {tr / ((END - D18[0]).days / 365.25):.0f} l anno')

# ---------------------------------------------------------------- d) portafoglio da N titoli presi dalla lista
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

U = uni(UNI)
for N in (10, 15):
    for fx, pc, lab in [(0, 0.005, '0,5%'), (5, 0.003, '5 EUR + 0,3%')]:
        v = np.array([ann(port_n(CORE & UNI, N, s, fx, pc)) - ann(U) for s in range(200)]) * 100
        print(f'core tenendo al massimo {N} titoli (estratti a caso fra quelli in lista, tenuti finche restano), costi {lab}: '
              f'mediana {np.median(v):+.1f}, 10%-90% [{np.percentile(v,10):+.1f}, {np.percentile(v,90):+.1f}], quota sotto lo zero {np.mean(v<0):.0%}')
v = np.array([ann(port_n(CORE & UNI & ~TWKO, 12, s, 5, 0.003)) - ann(uni(UNI & ~TWKO)) for s in range(200)]) * 100
print(f'core senza Taiwan/Corea, 12 titoli, 5 EUR + 0,3%: mediana {np.median(v):+.1f}, 10%-90% [{np.percentile(v,10):+.1f}, {np.percentile(v,90):+.1f}], quota sotto zero {np.mean(v<0):.0%}')

# ---------------------------------------------------------------- f) anno per anno del core (vantaggio)
def yearly(r):
    s = r.reindex(D18).copy(); s.index = [NXT[d] for d in D18]
    y = [d.year if (d.month > 1 or d.day > 15) else d.year - 1 for d in s.index]
    return (1 + s).groupby(y).prod() - 1
Y = (yearly(rc) - yearly(u_g)) * 100
print('\ncore, vantaggio per anno:', Y.round(1).to_dict())
lr = np.log1p(rc.reindex(D18)) - np.log1p(u_g.reindex(D18))
yy = pd.Series([NXT[d].year if (NXT[d].month > 1 or NXT[d].day > 15) else NXT[d].year - 1 for d in D18], index=D18)
share = lr.groupby(yy.values).sum()
print('core, quota del vantaggio cumulato (log) per anno:', (share / share.sum() * 100).round(0).to_dict())
