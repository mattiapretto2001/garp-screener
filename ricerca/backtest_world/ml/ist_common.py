# ist_common (07/11): portafoglio REALE da N titoli con versamenti, costi Trade Republic e tasse italiane.
# Regole fissate PRIMA di guardare i risultati:
#  - capitale iniziale 9.500 EUR (7.500 + 2.000), versamento 1.000 EUR/mese = 3.000 EUR a ogni trimestre (dati trimestrali:
#    il versamento del trimestre entra all'inizio del trimestre, in ordini da circa 1.000 EUR = 3 ordini, come 1 al mese).
#  - costi: 1 EUR per ordine + spread 0,1% (USA/Europa con cap. >= 10 Mld$) o 0,3% (tutto il resto), su ogni acquisto e vendita.
#    Base fiscale = prezzo pagato + commissione; valore = prezzo medio (mid).
#  - tasse: 26% sulle plusvalenze realizzate, minusvalenze compensate per 4 anni oltre quello di realizzo (regime amministrato,
#    costo medio). Dividendi: ritenuta estera 15% + 26% sul netto = 37,1% (rendimenti corretti per i dividendi: il dividendo
#    netto e' reinvestito nel titolo e alza la base fiscale). Alla fine: vendita di tutto (netto "liquidato").
#  - VWCE: stesso capitale e stessi versamenti, 1 EUR per ordine (3 ordini a trimestre), spread 0, 26% sul guadagno alla fine
#    (redditi di capitale: le minusvalenze non si compensano). Prima del 07/2019 VT (FTSE Global All Cap) in euro.
#  - liste e punteggi: core GARP e top 30 per punteggio GARP del repository (SC_A2); Crescita >= 2 Mld$ per punteggio bonus del
#    Moonshot (accelerazione +2, margine operativo in salita +1, FCF > 0 +1, cassa > debito +1, prezzo >= 90% del massimo +1;
#    a parita' crescita dei ricavi del trimestre); Qualita' Q3 per il punteggio "Qualita' durevole" proposto il 07/11
#    (8 variabili a peso uguale). Misto = meta' titoli core e meta' Q3.
#  - regole di rotazione:
#    (a) "oggi": a ogni controllo il portafoglio e' la top N della lista, pesi uguali ripristinati (si opera solo se lo scarto
#        supera il 10% del peso obiettivo e 50 EUR);
#    (a2) top N senza riequilibrio: escono i titoli fuori dalla top N, entrano i nuovi; i versamenti vanno ai sottopesati;
#    (b) isteresi: si compra solo dalla top K; si vende se il titolo e' nella lista ma oltre la posizione M, oppure se e' fuori
#        dalla lista a 2 controlli di fila;
#    (c) tesi: si vende solo se il titolo e' fuori dalla lista E i fondamentali sono peggiorati (o non e' piu' nell'universo),
#        oppure dopo X anni se non e' piu' nella top K (se lo e', l'orologio riparte). Acquisti dalla top K = 15.
#        Peggioramento: GARP = ricavi del trimestre < +5% o ROE < 10% o FCF < 0; Crescita = ricavi del trimestre < +10% o
#        margine lordo < 20% o cassa per meno di 2 anni; Qualita' = ROE < 10% o ricavi 12 mesi in calo.
#  - titolo senza prezzo (uscito dal listino): incassato al valore, senza costi.
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from pp_common import *          # F, REB, maschere (CORE, CR, Q3, TOP30_2B, A, B2, B5, QU, UNI, SC_A2, runway ...)
import fv3
OUTD = f'{HERE}/ist_out'; os.makedirs(OUTD, exist_ok=True)
END = pd.Timestamp('2026-11-06')
NXT = {t: (REB[i + 1] if i + 1 < len(REB) else END) for i, t in enumerate(REB)}
TWKO = F.ex.isin(['TW', 'KO'])

# ------------------------------------------------------------------ punteggi delle liste
V = fv3.load(cols=['t', 'date', 'roic', 'opm_std5', 'hist_y'])
F = F.merge(V, on=['t', 'date'], how='left'); assert len(F) == len(TWKO)
acc = (F.revq > F.rev_cagr).fillna(False)
SC_CR = (2 * acc + (F.d_opm > 0).fillna(False) + (F.fcf_ttm > 0).fillna(False) + (F.cash > F.debt).fillna(False)
         + (F.hi52 >= 0.9).fillna(False)) + F.revq.clip(-1, 5).fillna(0) / 100
QV = {'dsh3': -1, 'hist15': 1, 'hi52': 1, 'n_beat4': 1, 'vol1y': -1, 'roic': 1, 'opm_std5': -1, 'fcf_m': 1}
F['hist15'] = F.hist_y.clip(upper=15)


def score_q(m):
    out = pd.Series(np.nan, index=F.index)
    for t, x in F[m].groupby('date'):
        out[x.index] = sum(pct(x[k], s > 0) for k, s in QV.items()) / len(QV)
    return out


SC_Q = score_q(Q3 & QU & B5)

# ------------------------------------------------------------------ peggioramento dei fondamentali (tesi)
BAD_G = ((F.revq < 0.05) | (F.roe < 0.10) | (F.fcf_ttm < 0)).fillna(False)
BAD_C = ((F.revq < 0.10) | (F.gm < 0.20) | ~runway.fillna(True)).fillna(False)
BAD_Q = ((F.roe < 0.10) | (F.revg_ttm < 0)).fillna(False)

LISTDEF = {   # chiave -> (maschera, punteggio, tipo di tesi)
    'core': (CORE & UNI, SC_A2, 'G'),
    'core_noTWKO': (CORE & UNI & ~TWKO, SC_A2, 'G'),
    'top30': (A & B2 & UNI, SC_A2, 'G'),          # classifica intera della GARP >= 2 Mld$: la top 30 e' la sua testa
    'cr2': (CR & B2 & UNI, SC_CR, 'C'),
    'q3': (Q3 & QU & B5, SC_Q, 'Q'),
}
BADS = {'G': BAD_G, 'C': BAD_C, 'Q': BAD_Q}

ORD, BADSET = {}, {}
for k, (m, sc, th) in LISTDEF.items():
    d = F[m].assign(_s=sc[m]).sort_values(['date', '_s'], ascending=[True, False])
    ORD[k] = {t: list(x.t) for t, x in d.groupby('date')}
    BADSET[k] = {t: set(x.t) for t, x in F[BADS[th]].groupby('date')}
INPANEL = {t: set(x.t) for t, x in F.groupby('date')}

# ------------------------------------------------------------------ rendimenti in euro di TUTTI i titoli toccati (anche fuori pannello)
TICK = set().union(*[set(F[m].t) for m, _, _ in LISTDEF.values()])
RQ = pd.read_pickle(f'{BASE}/res/rq2.pkl')
RQ = RQ[RQ.t.isin(TICK)].drop_duplicates(['t', 'date'])
M2 = pd.read_pickle(f'{BASE}/res/meta2.pkl').drop_duplicates('t').set_index('t')
FX = pd.read_pickle(f'{BASE}/eod/fx.pkl').sort_index().ffill()


def fx_at(c, t):
    if c == 'GBp': c = 'GBX'
    if c not in FX.columns: return np.nan
    i = FX.index.searchsorted(t, side='right') - 1; return FX[c].iloc[max(i, 0)]


RQ['cur'] = RQ.t.map(M2.cur_px)
ce = {}
for c in RQ.cur.dropna().unique():
    for t in REB:
        a = fx_at(c, t) / fx_at('EUR', t); b = fx_at(c, NXT[t]) / fx_at('EUR', NXT[t]); ce[(c, t)] = b / a - 1
RQ['r_eur'] = (1 + RQ.r) * (1 + np.array([ce.get((c, t), np.nan) for c, t in zip(RQ.cur, RQ.date)])) - 1
RQ = RQ[RQ.r_eur.notna()]
RET = {t: dict(zip(x.t, x.r_eur)) for t, x in RQ.groupby('date')}
# controllo: sulle righe del pannello coincide con r_eur del pannello
_chk = F[['t', 'date', 'r_eur']].merge(RQ[['t', 'date', 'r_eur']], on=['t', 'date'], suffixes=('', '_rq'))
CHK = float((_chk.r_eur - _chk.r_eur_rq).abs().max())

# ------------------------------------------------------------------ spread e dividendi (ultimo dato noto per i titoli fuori pannello)
F['spread'] = np.where(F.reg.isin(['USA', 'Europa']) & (F.mcap_usd >= 10e9), 0.001, 0.003)
SPR, DIV = {}, {}
_ls, _ld = {}, {}
for t in REB:
    x = F[F.date == t]
    _ls.update(dict(zip(x.t, x.spread))); _ld.update(dict(zip(x.t, x.divy.fillna(0.0))))
    SPR[t] = dict(_ls); DIV[t] = dict(_ld)

# ------------------------------------------------------------------ indice VWCE in euro (VT prima del 07/2019)
import pickle
_B = pickle.load(open(f'{BASE}/eod/bench.pkl', 'rb'))
_eur = FX.EUR


def _at(s, d): return float(s[s.index <= d].iloc[-1])


_vw = _B['VWCE.XETRA'].a.astype(float); _vt = _B['VT.US'].a.astype(float)
_vte = _vt / _eur.reindex(_vt.index).ffill()
VW = {}
for t in REB:
    s = _vw if t >= pd.Timestamp('2019-09-30') else _vte
    VW[t] = _at(s, NXT[t]) / _at(s, t) - 1
VW = pd.Series(VW)
UNIV_EW = F[UNI].groupby('date').r_eur.mean().reindex(REB)

FEE, TAX, TAXDIV = 1.0, 0.26, 1 - 0.85 * 0.74


# ------------------------------------------------------------------ simulatore
class Book:
    def __init__(s, tax):
        s.tax = tax; s.cash = 0.0; s.pos = {}; s.loss = []; s.taxpaid = 0.0; s.fees = 0.0; s.spread = 0.0; s.orders = 0
        s.traded = 0.0; s.year = None

    def value(s): return s.cash + sum(p['v'] for p in s.pos.values())

    def _realize(s, g):
        if not s.tax: return
        if g < 0: s.loss.append([s.year, -g]); return
        for b in s.loss:
            if g <= 0: break
            u = min(b[1], g); b[1] -= u; g -= u
        s.loss = [b for b in s.loss if b[1] > 1e-9]
        t = TAX * g; s.cash -= t; s.taxpaid += t

    def new_year(s, y):
        s.year = y; s.loss = [b for b in s.loss if b[0] >= y - 4]

    def sell(s, t, frac=1.0, d=None, free=False):
        p = s.pos[t]; v = p['v'] * frac; b = p['b'] * frac
        if free: proc = v
        else:
            sp = SPR[d].get(t, 0.003); proc = v * (1 - sp) - FEE
            s.fees += FEE; s.spread += v * sp; s.orders += 1; s.traded += v
        s.cash += proc; s._realize(proc - b)
        if frac >= 0.999: del s.pos[t]
        else: p['v'] -= v; p['b'] -= b

    def buy(s, t, amt, d, sleeve=0):
        if amt <= FEE + 1: return
        sp = SPR[d].get(t, 0.003); val = (amt - FEE) * (1 - sp)
        s.cash -= amt; s.fees += FEE; s.spread += (amt - FEE) * sp; s.orders += 1; s.traded += amt
        if t in s.pos: s.pos[t]['v'] += val; s.pos[t]['b'] += amt
        else: s.pos[t] = dict(v=val, b=amt, sl=sleeve, d0=d, out=0)


def sim(sleeves, rule, dates, K=10, M=40, X=None, freq=1, tax=True, init=9500.0, contrib=3000.0, band=0.10, Kc=15,
        liquidate=True, grace=2, rebal=False):
    """sleeves = [(chiave lista, quota, N)]; rule in 'a','a2','b','c'. Torna dict con serie trimestrale e misure."""
    bk = Book(tax); twr = {}; flows = []; hold_n = []; vprev = 0.0; vals = []
    for i, d in enumerate(dates):
        # anno fiscale: la data 31/12 apre il trimestre dell'anno dopo
        fy = d.year + 1 if d.month == 12 else d.year
        if bk.year != fy: bk.new_year(fy)
        c = init if i == 0 else contrib
        bk.cash += c; flows.append((d, -c))
        R = RET.get(d, {})
        # 1) titoli senza prezzo (usciti): incassati
        for t in [t for t in bk.pos if t not in R]: bk.sell(t, d=d, free=True)
        check = (i % freq == 0)
        if check:
            # 2) vendite secondo la regola
            for si, (lk, sh, N) in enumerate(sleeves):
                L = ORD[lk].get(d, []); rk = {t: j + 1 for j, t in enumerate(L)}
                mine = [t for t, p in bk.pos.items() if p['sl'] == si]
                if rule in ('a', 'a2'):
                    top = set(L[:N])
                    for t in mine:
                        if t not in top: bk.sell(t, d=d)
                elif rule == 'b':
                    for t in mine:
                        p = bk.pos[t]
                        if t in rk:
                            p['out'] = 0
                            if M is not None and rk[t] > M: bk.sell(t, d=d)
                        else:
                            p['out'] += 1
                            if p['out'] >= grace: bk.sell(t, d=d)
                elif rule == 'c':
                    bad = BADSET[lk].get(d, set()); inp = INPANEL.get(d, set())
                    for t in mine:
                        p = bk.pos[t]
                        if t not in rk and (t in bad or t not in inp): bk.sell(t, d=d); continue
                        if X is not None and (d - p['d0']).days >= X * 365.25 - 20:
                            if rk.get(t, 10 ** 9) <= Kc: p['d0'] = d
                            else: bk.sell(t, d=d)
            # 3) acquisti di nomi nuovi
            Vt = bk.value()
            held_all = set(bk.pos)
            for si, (lk, sh, N) in enumerate(sleeves):
                L = ORD[lk].get(d, [])
                n_have = sum(1 for p in bk.pos.values() if p['sl'] == si)
                kk = N if rule in ('a', 'a2') else (Kc if rule == 'c' else K)
                cand = [t for t in L[:kk] if t not in held_all and t in R]
                new = cand[:max(0, N - n_have)]
                if not new: continue
                tgt = Vt * sh / min(N, max(len(L), 1))   # lista piu' corta di N: pesi uguali fra i nomi disponibili
                each = min(tgt, bk.cash / len(new)) if bk.cash > 0 else 0
                for t in new:
                    if each > 50: bk.buy(t, each, d, si); held_all.add(t)
            # 4) (a): riequilibrio ai pesi uguali (vendite dei sovrappesati, poi acquisti dei sottopesati)
            if rule == 'a' or rebal:
                Vt = bk.value()
                for si, (lk, sh, N) in enumerate(sleeves):
                    mine = [t for t, p in bk.pos.items() if p['sl'] == si]
                    if not mine: continue
                    tgt = Vt * sh / max(min(N, len(ORD[lk].get(d, []))), len(mine), 1)
                    for t in mine:
                        v = bk.pos[t]['v']
                        if v - tgt > max(band * tgt, 50): bk.sell(t, frac=(v - tgt) / v, d=d)
                Vt = bk.value()
                defs = []
                for si, (lk, sh, N) in enumerate(sleeves):
                    mine = [t for t, p in bk.pos.items() if p['sl'] == si]
                    if not mine: continue
                    tgt = Vt * sh / max(min(N, len(ORD[lk].get(d, []))), len(mine), 1)
                    defs += [(tgt - bk.pos[t]['v'], t, tgt) for t in mine if tgt - bk.pos[t]['v'] > max(band * tgt, 50)]
                defs.sort(reverse=True)
                for df, t, tgt in defs:
                    a = min(df, bk.cash)
                    if a > 50: bk.buy(t, a, d, bk.pos[t]['sl'])
        # 5) cassa residua (versamento) ai sottopesati: ordini da almeno 1.000 EUR (massimo ~3-4 a trimestre)
        if bk.pos and bk.cash > 50:
            Vt = bk.value()
            nsl = {si: sum(1 for p in bk.pos.values() if p['sl'] == si) for si in range(len(sleeves))}
            size = max(1000.0, bk.cash / 3)
            while bk.cash > 50:
                def deficit(t):
                    p = bk.pos[t]; sh = sleeves[p['sl']][1]
                    return Vt * sh / max(nsl[p['sl']], 1) - p['v']
                t = max(bk.pos, key=deficit)
                a = min(size, bk.cash)
                if a < 50: break
                bk.buy(t, a, d, bk.pos[t]['sl'])
        # 6) dividendi tassati e rendimento del trimestre
        for t, p in bk.pos.items():
            if bk.tax:
                D = p['v'] * DIV[d].get(t, 0.0) / 4; tx = TAXDIV * D
                p['v'] -= tx; p['b'] += D - tx; bk.taxpaid += tx
            p['v'] *= 1 + R.get(t, 0.0)
        hold_n.append(len(bk.pos)); vals.append(bk.value())
        # rendimento del trimestre al netto di costi e tasse pagate: valore finale / (valore iniziale + versamento) - 1
        twr[d] = bk.value() / (vprev + c) - 1 if i > 0 else bk.value() / c - 1
        vprev = bk.value()
    W_gross_end = bk.value()
    if liquidate:
        last = dates[-1]
        for t in list(bk.pos): bk.sell(t, d=last)
    W = bk.value()
    flows.append((NXT[dates[-1]], W))
    return dict(twr=pd.Series(twr), W=W, W_pre=W_gross_end, irr=xirr(flows), taxpaid=bk.taxpaid, fees=bk.fees, spread=bk.spread,
                orders=bk.orders, traded=bk.traded, nhold=np.mean(hold_n), vmean=np.mean(vals), contrib=init + contrib * (len(dates) - 1))


def sim_vwce(dates, tax=True, init=9500.0, contrib=3000.0):
    v = b = 0.0; twr = {}; flows = []; fees = 0.0; vprev = 0
    for i, d in enumerate(dates):
        c = init if i == 0 else contrib; n = 1 if i == 0 else 3
        v += c - n * FEE; b += c; fees += n * FEE; flows.append((d, -c))
        v *= 1 + VW[d]
        twr[d] = v / (vprev + c) - 1; vprev = v
    W_pre = v
    v -= FEE
    if tax and v - b > 0: v -= TAX * (v - b)
    flows.append((NXT[dates[-1]], v))
    return dict(twr=pd.Series(twr), W=v, W_pre=W_pre, irr=xirr(flows), fees=fees, contrib=init + contrib * (len(dates) - 1))


def xirr(flows):
    t0 = flows[0][0]
    ts = np.array([(d - t0).days / 365.25 for d, _ in flows]); cf = np.array([c for _, c in flows])
    f = lambda r: np.sum(cf / (1 + r) ** ts)
    lo, hi = -0.9, 3.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0: lo = mid
        else: hi = mid
    return mid


def ann_twr(r):
    ds = list(r.index); yrs = (NXT[ds[-1]] - ds[0]).days / 365.25
    return (1 + r).prod() ** (1 / yrs) - 1


def nwt(x, L=2):
    x = np.asarray(pd.Series(x).dropna(), float); T = len(x)
    if T < 4: return np.nan
    e = x - x.mean(); v = e @ e / T
    for l in range(1, L + 1): v += 2 * (1 - l / (L + 1)) * (e[l:] @ e[:-l]) / T
    return x.mean() / np.sqrt(v / T) if v > 0 else np.nan


PER = {'2018-26': ('2018-03-31', '2026-09-30'), '2012-17': ('2011-12-31', '2017-12-31'),
       '2018-21': ('2018-03-31', '2021-09-30'), '2022-24': ('2021-12-31', '2024-09-30'), '2025-26': ('2024-12-31', '2026-09-30')}


def pdates(p):
    a, b = PER[p]; return [d for d in REB if pd.Timestamp(a) <= d <= pd.Timestamp(b)]


CFG = {   # nome -> sleeves (N viene scalato)
    'core': lambda N: [('core', 1.0, N)],
    'core_noTWKO': lambda N: [('core_noTWKO', 1.0, N)],
    'top30': lambda N: [('top30', 1.0, N)],
    'cr2': lambda N: [('cr2', 1.0, N)],
    'mix': lambda N: [('core', 0.5, (N + 1) // 2), ('q3', 0.5, N // 2)],
}
