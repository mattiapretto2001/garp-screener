# Prova C (08/11/2026), fase 2: simulatore dei portafogli "moltiplicatori". REGOLE FISSATE PRIMA DI GUARDARE I RISULTATI.
#  Portafoglio: 100 = 50 in VWCE (indice mondiale in euro, vedi c01) + 50 nella meta' moltiplicatori, che parte in contanti.
#  Nessun ribilanciamento fra le due meta' nella simulazione (il 50/50 ribilanciato ogni gennaio e' calcolato dopo, dalle
#  serie mensili). Contanti fermi a rendimento 0.
#  Meta' moltiplicatori: 14 titoli obiettivo (12-15). Ogni acquisto = 1/14 del valore della meta' (titoli + contanti), cioe'
#  circa il 3,6% del totale quando le due meta' sono pari. Si compra il primo giorno di borsa di ogni mese, al massimo 2 nomi
#  nuovi al mese, scelti A CASO fra i nomi della lista piu' recente (la Radiografia non si puo' simulare), esclusi quelli gia'
#  in portafoglio e quelli venduti negli ultimi 12 mesi. Se i contanti non bastano per meta' di un acquisto, non si compra.
#  Costi: 0,5% su ogni acquisto e ogni vendita. Prezzi di chiusura giornalieri in euro, corretti per dividendi.
#  Uscita dal listino: si incassa l'ultimo prezzo, oppure 0 se e' sotto il 25% del massimo dell'ultimo anno (fallimento).
#  Sempre attivo: taglio sopra il 10% del portafoglio totale (controllo mensile, si vende la parte oltre il 10%).
#  Regole di uscita (base), una alla volta:
#   L  = uscita dalla lista al controllo trimestrale (primo giorno di borsa dopo la nuova lista);
#   T2 = tempo massimo 2 anni (controllo mensile), la lista non conta dopo l'acquisto;
#   T3 = tempo massimo 3 anni.
#  Regole aggiunte alla base, una alla volta:
#   none = nessuna (lasciar correre, solo il taglio sopra il 10%);
#   S30 / S50 = stop: vendita di tutto alla chiusura del primo giorno a -30% / -50% dal prezzo d'acquisto;
#   TR2 / TR3 = vendita di meta' alla chiusura del primo giorno a x2 / x3 dal prezzo d'acquisto (una volta);
#   AD30 = mediare al ribasso: al controllo mensile, se il prezzo e' a -30% o peggio dal prezzo d'acquisto, si compra una
#          seconda volta la stessa somma del primo acquisto (una volta sola, se ci sono i contanti; prima dei nomi nuovi).
#  Tasse (variante): 26% sulle plusvalenze realizzate, minusvalenze compensabili nei 4 anni successivi (regime amministrato),
#  vendita di tutto alla fine; VWCE: 26% sul guadagno alla fine.
import os, sys, pickle, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); DAT = f'{HERE}/dati'
COST = 0.005; N = 14; MAXNEW = 2; TAX = 0.26
BASES = ['L', 'T2', 'T3']; OVERS = ['none', 'S30', 'S50', 'TR2', 'TR3', 'AD30']
VARIANTS = [(b, o) for b in BASES for o in OVERS]


def load(key):
    P = pickle.load(open(f'{DAT}/{key}.pkl', 'rb'))
    cal = P['cal']; M = P['M'].astype(np.float64); tick = P['tick']
    nT, nD = M.shape
    first = np.full(nT, -1); last = np.full(nT, -1)
    for j in range(nT):
        ok = np.where(~np.isnan(M[j]))[0]
        if len(ok):
            first[j], last[j] = ok[0], ok[-1]
            row = M[j, first[j]:last[j] + 1]
            s = pd.Series(row).ffill().values; M[j, first[j]:last[j] + 1] = s
    ended = np.zeros(nT, bool); bk = np.zeros(nT, bool)
    for j, t in enumerate(tick):
        lt, en, b = P['info'][t]
        if en and last[j] >= 0 and last[j] < nD - 1 and lt <= cal[-1]:
            ended[j] = True; bk[j] = b
        elif last[j] >= 0 and last[j] < nD - 1:          # buco finale nei dati ma serie non finita: prezzo fermo
            M[j, last[j] + 1:] = M[j, last[j]]; last[j] = nD - 1
    W = P['W'].reindex(cal).ffill().values
    ms = np.array([np.where((cal.year == y) & (cal.month == m))[0][0] for y, m in sorted(set(zip(cal.year, cal.month)))])
    # lista valida a ogni inizio mese
    qd = sorted(P['L'])
    avail = {q: int(np.searchsorted(cal.values, np.datetime64(q), side='right')) for q in qd}
    cur = []; newq = []
    lastq = None
    for i in ms:
        qs = [q for q in qd if avail[q] <= i]
        q = qs[-1] if qs else None
        cur.append(P['L'][q] if q is not None else np.array([], int))
        newq.append(q is not None and q != lastq); lastq = q
    sets = [set(x.tolist()) for x in cur]
    return dict(cal=cal, M=M, tick=tick, first=first, last=last, ended=ended, bk=bk, W=W, ms=ms, cur=cur, sets=sets, newq=newq)


class Pos:
    __slots__ = ('j', 'sh', 'px0', 'inv', 'proc', 'd0', 'basis', 'avg', 'trim', 'peak')


def run(D, base, over, seed, tax=False, cash_w=False):
    M, ms, W = D['M'], D['ms'], D['W']; nD = M.shape[1]
    rng = np.random.default_rng(seed)
    cash = 50.0; uw = 50.0 / W[ms[0]]
    pos = {}; soldday = {}; recs = []; bank = []; taxpaid = 0.0; ntrade = 0
    vals = []; days = []
    stop = {'S30': 0.70, 'S50': 0.50}.get(over); trimx = {'TR2': 2.0, 'TR3': 3.0}.get(over)
    tcap = {'T2': 730, 'T3': 1095}.get(base)
    cal = D['cal']; yr = cal.year.values
    ends = D['last']; ended = D['ended']; bk = D['bk']

    def realize(g, d):
        nonlocal cash, taxpaid, bank
        if not tax: return
        y = yr[d]
        bank = [b for b in bank if b[0] >= y - 4]
        if g < 0: bank.append([y, -g]); return
        for b in bank:
            if g <= 0: break
            u = min(b[1], g); b[1] -= u; g -= u
        bank = [b for b in bank if b[1] > 1e-12]
        t = TAX * g; cash -= t; taxpaid += t

    def sell(p, frac, d, why, free=False, zero=False):
        nonlocal cash, ntrade
        px = 0.0 if zero else M[p.j, d]
        v = p.sh * frac * px
        proc = v if free else v * (1 - COST)
        if not free: ntrade += 1
        cash += proc; p.proc += proc
        b = p.basis * frac; p.basis -= b
        realize(proc - b, d)
        if frac >= 0.999:
            recs.append((p.j, p.d0, d, p.inv, p.proc, why, p.peak, p.avg, p.trim))
            del pos[p.j]; soldday[p.j] = d
        else:
            p.sh *= (1 - frac)

    def buy(j, amt, d, p=None):
        nonlocal cash, ntrade
        sh = amt * (1 - COST) / M[j, d]; cash -= amt; ntrade += 1
        if p is None:
            p = Pos(); p.j = j; p.sh = sh; p.px0 = M[j, d]; p.inv = amt; p.proc = 0.0; p.d0 = d; p.basis = amt
            p.avg = False; p.trim = False; p.peak = 1.0; pos[j] = p
        else:
            p.sh += sh; p.inv += amt; p.basis += amt

    def sleeve(d): return cash + sum(p.sh * M[p.j, d] for p in pos.values())

    c_prev = 0.0
    dE = nD - 1
    chk = list(ms) + ([dE] if dE > ms[-1] else [])
    for k, d in enumerate(chk):
        # ---- giorni dal controllo precedente a oggi: uscite dal listino, stop, tagli a x2/x3
        if k > 0:
            a = chk[k - 1] + 1
            for p in list(pos.values()):
                seg = M[p.j, a:d + 1]
                e = ends[p.j]
                endk = e - a if (ended[p.j] and e < d + 1) else None
                if endk is not None: seg = seg[:endk + 1]
                if len(seg): p.peak = max(p.peak, float(np.nanmax(seg)) / p.px0)
                hit = None
                if stop is not None:
                    w = np.where(seg <= stop * p.px0)[0]
                    if len(w): hit = ('stop', w[0])
                elif trimx is not None and not p.trim:
                    w = np.where(seg >= trimx * p.px0)[0]
                    if len(w): hit = ('trim', w[0])
                if hit is not None and (endk is None or hit[1] <= endk):
                    if hit[0] == 'stop':
                        sell(p, 1.0, a + hit[1], 'stop'); continue
                    else:
                        p.trim = True; sell(p, 0.5, a + hit[1], 'taglio x')
                if endk is not None and p.j in pos:
                    sell(p, 1.0, e, 'fallimento' if bk[p.j] else 'uscita dal listino', free=True, zero=bool(bk[p.j]))
        if cash_w and k > 0: cash += c_prev * (W[d] / W[chk[k - 1]] - 1)   # controllo dichiarato dopo: contanti parcheggiati in VWCE
        vals.append((sleeve(d), uw * W[d], cash)); days.append(d)
        if k >= len(ms): break
        L = D['sets'][k]
        # ---- uscita dalla lista (trimestrale) o tempo massimo
        if base == 'L' and D['newq'][k]:
            for p in list(pos.values()):
                if p.j not in L: sell(p, 1.0, d, 'fuori lista')
        if tcap is not None:
            for p in list(pos.values()):
                if (cal[d] - cal[p.d0]).days >= tcap - 15: sell(p, 1.0, d, 'tempo')
        # ---- taglio sopra il 10% del totale
        tot = sleeve(d) + uw * W[d]
        for p in list(pos.values()):
            v = p.sh * M[p.j, d]
            if v > 0.10 * tot: sell(p, (v - 0.10 * tot) / v, d, 'taglio 10%')
        # ---- mediare al ribasso
        if over == 'AD30':
            for p in list(pos.values()):
                if not p.avg and M[p.j, d] <= 0.70 * p.px0:
                    amt = min(p.inv, cash)
                    if amt >= 0.5 * p.inv: buy(p.j, amt, d, p); p.avg = True
        # ---- nomi nuovi
        free = N - len(pos)
        if free > 0 and d < nD - 21:
            S = sleeve(d); size = S / N
            cand = [j for j in D['cur'][k] if j not in pos and not np.isnan(M[j, d]) and ends[j] > d
                    and (j not in soldday or (cal[d] - cal[soldday[j]]).days > 365)]
            nb = min(MAXNEW, free, len(cand))
            if nb:
                pick = rng.choice(len(cand), nb, replace=False)
                for i in pick:
                    amt = min(size, cash)
                    if amt < 0.5 * size: break
                    buy(cand[i], amt, d)
        c_prev = cash
    # ---- fine: posizioni aperte valutate all'ultimo prezzo
    open_recs = []
    for p in pos.values():
        v = p.sh * M[p.j, dE]
        open_recs.append((p.j, p.d0, dE, p.inv, p.proc + v, 'aperta', p.peak, p.avg, p.trim))
    Wv = uw * W[dE]
    if days[-1] != dE: vals.append((sleeve(dE), Wv, cash)); days.append(dE)
    out = dict(vals=np.array(vals), days=np.array(days), recs=recs + open_recs, ntrade=ntrade)
    if tax:
        # liquidazione finale tassata
        for p in list(pos.values()): sell(p, 1.0, dE, 'fine')
        S_net = cash
        g = Wv - 50.0
        W_net = Wv - TAX * max(g, 0) if True else Wv
        out.update(S_net=S_net, W_net=W_net, taxpaid=taxpaid)
    return out


def job(args):
    key, base, over, seeds, tax = args
    D = load(key) if key not in _CACHE else _CACHE[key]
    _CACHE[key] = D
    res = []
    for s in seeds:
        r = run(D, base, over, s, tax)
        res.append(r)
    return (key, base, over, tax), res


_CACHE = {}

if __name__ == '__main__':
    import time
    from multiprocessing import Pool
    key = sys.argv[1] if len(sys.argv) > 1 else 'P1'
    t0 = time.time(); D = load(key); print('load', round(time.time() - t0, 1), 's', flush=True)
    for b, o in [('L', 'none'), ('T3', 'S30'), ('L', 'AD30')]:
        t0 = time.time(); r = run(D, b, o, 1)
        from collections import Counter
        print(b, o, 'run', round(time.time() - t0, 2), 's | posizioni', len(r['recs']), 'scambi', r['ntrade'],
              Counter(x[5] for x in r['recs']), 'titoli medi', round(np.mean([0]), 1), flush=True)
