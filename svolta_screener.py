#!/usr/bin/env python3
"""
Screener Svolta (versione B1) — aziende di qualità con il margine operativo in svolta
===================================================================================
Cerca aziende con margine lordo da azienda di qualità, ricavi che crescono in
modo sano e soprattutto un margine operativo che migliora partendo da livelli
bassi (svolta in corso, non finita).

Dal 03/11/2026 i criteri seguono il backtest storico 2012-2026 ("Backtest dei
criteri Svolta", 03/11/2026): la versione completa a 8 criteri non batte
l'universo fuori campione; regge solo il nucleo "B1" (filtro base + margine
operativo in svolta): +10,5 punti annui sull'universo nel 2012-19 e +22 nel
2020-24, ma -6,7 nel 2025-26. È un'ipotesi da seguire in tempo reale, non una
regola provata: l'elenco è di candidate da RADIOGRAFARE, non da comprare.

FILTRI OBBLIGATORI (HARD_CHECKS, tutti):
  - margine lordo degli ultimi 12 mesi >= 55% (>= 40% industria/hardware) e
    non in calo rispetto a 4 trimestri prima
  - ricavi dell'ultimo trimestre tra +20% e +60% sullo stesso trimestre
    dell'anno prima
  - margine operativo in svolta: 12 mesi almeno +5 punti in un anno (oppure
    ultimo trimestre +8 punti sullo stesso trimestre dell'anno prima); livello
    dei 12 mesi tra -15% e +20%; ultimo trimestre non peggiore di due
    trimestri prima
  - capitalizzazione 1-15 Mld$
  - esclusi i settori a margine lordo strutturalmente basso (costruzioni e
    impianti, auto, trasporto marittimo, energia e materie prime: nel backtest
    neutri, tenuti per coerenza) e i titoli con dati non valutabili

NON PIÙ FILTRI (solo informazione, avviso o punteggio): primo utile, solidità
di cassa (avviso in `avvisi` se diluizione > 10%/anno o cassa per meno di 2
anni), revisioni delle stime (punteggio ridotto, non verificabili storicamente),
numero di analisti, posizione del prezzo.

PUNTEGGIO 0-100 (mostrato in decimi, 0-10), solo per ORDINARE, nessuna soglia
d'acquisto: traiettoria del margine operativo 25, margine lordo 10 + 5 se in
salita di >= 2 punti, crescita dei ricavi 10 + 5 se in accelerazione, bilancio
10 (flusso di cassa positivo, cassa netta), posizione del prezzo 10 (1,2-1,8
volte il minimo a 52 settimane; -3 sopra il 95% del massimo), revisioni delle
stime 5 (non testate). Somma su 80 punti riportata su base 100. Niente bonus
per il primo utile.

USO: se i promossi sono 8 o meno si considerano tutti, altrimenti i primi 8 per
punteggio (`da_radiografare`); ricontrollo ogni trimestre, dopo i conti.

Flusso su GitHub Actions (dopo GARP/Moonshot/Temi nello stesso shard):
  - SHARD=N: primo filtro sulla cache .info del GARP (partials/info-N.json,
    nessuna chiamata di rete); solo chi lo supera viene scaricato in dettaglio
    (info completo, trimestrali, bilanci, stime, insider) con pause e retry ->
    partials/svolta-N.json
  - MODE=merge: unisce i parziali (anche se qualcuno manca) e scrive
    results-svolta/AAAA-MM-GG.json, latest.json, latest.md
  - senza variabili: run locale su UNIVERSE_FILE (o sull'universo intero)

Non automatizzati (li valuta Claude nella lettura serale): eventi binari entro
60 giorni (FDA, sentenze), crescita fatta con acquisizioni, temi affollati
(segnalati con il campo tema_affollato, senza penalità).
"""

import glob
import json
import os
import random
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import yfinance as yf

import garp_screener as base

RESULTS_DIR = "results-svolta"
MAX_WORKERS = 2          # stage 2: poche richieste parallele, Yahoo limita
STAGE2_MAX = 90          # tetto ai candidati scaricati in dettaglio per shard
PAUSE_BETWEEN = 1.0      # secondi di pausa tra un titolo e l'altro (per worker)
TOP_N_MD = 15            # titoli in evidenza nel Markdown
TOP_RADIOGRAFIA = 8      # se i promossi sono di più, si considerano i primi 8
TIME_BUDGET = 540        # secondi massimi di stage 2 per shard (lo step ha 12 minuti)
DEADLINE = [float("inf")]
VERSIONE_CRITERI = "B1 (backtest del 03/11/2026)"
SCORE_MAX_RAW = 80       # somma massima delle voci del punteggio, riportata su 100

CRITERIA = {
    "mcap_min_usd": 1e9,             # backtest B1: 1-15 Mld $ (prima 200 M - 20 Mld con penalità)
    "mcap_max_usd": 15e9,
    # svolta del margine operativo
    "op_margin_jump_min": 0.05,      # 12 mesi: +5 punti in un anno
    "op_margin_jump_q_min": 0.08,    # oppure +8 punti trimestre su trimestre di un anno prima
    "op_margin_level_min": -0.15,    # livello dei 12 mesi: svolta in corso...
    "op_margin_level_max": 0.20,     # ...non già finita
    "eps_near_zero_yield": 0.01,     # solo informativo (primo_utile): EPS 12m / prezzo <= 1%
    # ricavi
    "rev_growth_min": 0.20,
    "rev_growth_max": 0.60,          # backtest B1: +20/+60% (prima 100%)
    "accel_min": 0.03,               # +3 punti sul trimestre prima = accelerazione (punteggio)
    "prefilter_slack": 0.75,         # primo filtro allargato (per i near miss)
    # margine lordo (12 mesi)
    "gross_margin_min": 0.55,
    "gross_margin_min_hw": 0.40,     # industria / hardware
    "gross_margin_rising_min": 0.02, # "in salita": +2 punti in un anno (punteggio)
    "gross_margin_drop_max": 0.0,    # "non in calo": nessuna discesa su 4 trimestri
    # revisioni (solo punteggio e informazione: non verificabili storicamente)
    "revision_90d_min": 0.05,
    "revision_30d_cut_max": -0.01,
    # prezzo (solo punteggio e informazione)
    "x_52w_low_score_min": 1.2,      # 1,2-1,8 volte il minimo a 52 settimane: +10
    "x_52w_low_score_max": 1.8,
    "pct_of_52w_high_penalty": 0.95, # sopra il 95% del massimo: -3
    "pct_of_52w_high_min": 0.60,     # solo per il check informativo prezzo_ok
    "pct_of_52w_high_max": 0.97,
    "x_52w_low_max": 2.5,
    # avvisi di rischio (non escludono)
    "runway_years_min": 2.0,
    "dilution_max": 0.10,
    "net_debt_ebitda_max": 3.0,      # solo check informativo leva_ok
    # informativi
    "analysts_max": 25,
    "analysts_few": 8,
    "insider_buy_share_min": 0.5,
    # chiavi della versione precedente, tenute per compatibilità del formato
    # (non più usate: vedi docs/CAMBI_FORMATO.md)
    "mcap_ideal_min_usd": None,
    "mcap_ideal_max_usd": None,
    "gross_margin_floor_rising": None,
    "insider_sell_heavy": None,
}

# Controlli obbligatori (versione B1): chi ne fallisce esattamente uno finisce nei near miss
HARD_CHECKS = ["mcap_ok", "settore_ok", "svolta_ok", "crescita_ok", "margine_lordo_ok"]

# Settori con margine lordo strutturalmente basso (analisi casi passati):
# costruzioni e impianti, auto, materie prime grezze
LOW_MARGIN_INDUSTRIES = ("Engineering & Construction", "Infrastructure Operations",
                         "Residential Construction", "Auto Manufacturers", "Auto Parts",
                         "Steel", "Aluminum", "Copper", "Other Industrial Metals & Mining",
                         "Agricultural Inputs", "Chemicals", "Lumber & Wood Production",
                         "Marine Shipping")
# Settori di materie prime/energia: il "margine lordo" e la svolta seguono il
# prezzo della materia prima, non la qualità (prima prova su Actions: petroliere
# e petroliferi in testa alla classifica)
COMMODITY_SECTORS = ("Energy", "Basic Materials")

HW_INDUSTRY_WORDS = ("Semiconductor", "Electronic", "Computer Hardware",
                     "Communication Equipment", "Scientific & Technical",
                     "Electrical Equipment", "Auto", "Solar")

# Tema oggi "affollato" (infrastruttura per l'AI): solo segnalato
CROWDED_INDUSTRY_WORDS = ("Semiconductor", "Communication Equipment",
                          "Computer Hardware", "Electrical Equipment",
                          "Independent Power", "Uranium")

# Cambi indicativi verso USD (la capitalizzazione di Yahoo è nella valuta di
# quotazione; GBp = pence ma la capitalizzazione è in sterline). Aggiornati
# dal vivo in shard quando possibile.
FX_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "GBp": 1.27, "CHF": 1.13,
          "SEK": 0.095, "NOK": 0.092, "DKK": 0.145, "JPY": 0.0066, "HKD": 0.128,
          "CNY": 0.14, "CAD": 0.72, "AUD": 0.65, "KRW": 0.00072, "TWD": 0.031,
          "INR": 0.012, "ILS": 0.27, "PLN": 0.25, "SGD": 0.74, "BRL": 0.18,
          "ZAR": 0.055, "MXN": 0.054}


# ----------------------------- utilità -----------------------------


def _num(x):
    try:
        if x is None:
            return None
        v = float(x)
        return None if v != v else v  # NaN -> None
    except Exception:
        return None


def _fetch(getter, tries=3, base_delay=3.0):
    """Dato Yahoo con retry se vuoto o in errore (limiti di frequenza)."""
    for i in range(tries):
        try:
            v = getter()
            if not (v is None or getattr(v, "empty", False) or (isinstance(v, dict) and not v)):
                return v
        except Exception:
            pass
        if i < tries - 1:
            time.sleep(base_delay * (2 ** i) + random.random())
    return None


def refresh_fx(currencies):
    """Cambi dal vivo per le valute presenti (una sola richiesta); in caso di
    errore restano quelli indicativi di FX_USD."""
    cur = sorted({("GBP" if c == "GBp" else c) for c in currencies
                  if c and c not in ("USD", "GBp")})
    if not cur:
        return
    try:
        syms = [f"{c}USD=X" for c in cur]
        df = yf.download(syms, period="5d", progress=False, auto_adjust=False)["Close"]
        for c, s in zip(cur, syms):
            col = df[s] if s in getattr(df, "columns", []) else df
            v = _num(col.dropna().iloc[-1]) if len(col.dropna()) else None
            if v and v > 0:
                FX_USD[c] = v
                if c == "GBP":
                    FX_USD["GBp"] = v
    except Exception as e:
        print(f"[WARN] cambi non aggiornati ({e}): uso quelli indicativi", file=sys.stderr)


def mcap_usd(info):
    m = _num(info.get("marketCap"))
    fx = FX_USD.get(info.get("currency") or "USD")
    return m * fx if m is not None and fx else None


def is_hardware(info):
    ind = info.get("industry") or ""
    return info.get("sector") == "Industrials" or any(w in ind for w in HW_INDUSTRY_WORDS)


def short_desc(summary, max_len=110, name=None):
    """Riassunto in poche parole del longBusinessSummary (prima frase, senza
    il nome dell'azienda e le formule di rito)."""
    if not summary:
        return ""
    s = summary.strip()
    # nome dell'azienda in testa: tolto prima di spezzare la frase
    # (nomi con punti come "e.l.f. Beauty, Inc." spezzerebbero la frase)
    if name and s.lower().startswith(name.lower()):
        s = s[len(name):].lstrip(" ,")
    # non spezzare la frase dopo le sigle societarie ("Unity Software Inc. operates")
    s = re.sub(r"\b(Inc|Corp|Co|Ltd|Plc|plc|S\.A|N\.V|U\.S|L\.P|Bhd|Ltda|AG|SE)\.(?=[\s,])",
               lambda m: m.group(1).replace(".", "§") + "§", s)
    s = re.split(r"\.\s+(?=[A-Z])", s, maxsplit=1)[0].replace("§", ".")
    s = re.sub(r"^.*?,\s*(together with its subsidiaries|through its subsidiaries)[^,]*,\s*", "", s)
    m = re.search(r"\b(designs|develops|provides|operates|manufactures|offers|engages|"
                  r"produces|sells|focuses|delivers|owns|creates|discovers|makes|"
                  r"supplies|researches|distributes|markets|builds)\b", s)
    if m and m.start() < 120:
        s = s[m.start():]
    s = s.strip().rstrip(".")
    if len(s) > max_len:
        s = s[:max_len].rsplit(" ", 1)[0] + "…"
    return s[:1].upper() + s[1:]


# Traduzione semplice dei primi termini di "cosa fa" (verbi iniziali, legami
# e luoghi frequenti): il resto della frase resta in inglese.
_IT_VERBS = {
    "designs": "progetta", "develops": "sviluppa", "provides": "fornisce",
    "operates": "gestisce", "manufactures": "produce", "offers": "offre",
    "engages": "si occupa", "produces": "produce", "sells": "vende",
    "focuses": "si concentra", "delivers": "fornisce", "owns": "possiede",
    "creates": "crea", "discovers": "scopre", "makes": "produce",
    "supplies": "fornisce", "researches": "fa ricerca", "distributes": "distribuisce",
    "markets": "commercializza", "builds": "costruisce", "commercializes": "commercializza",
    "licenses": "concede in licenza", "invests": "investe", "acquires": "acquisisce",
    "explores": "esplora", "installs": "installa", "services": "assiste",
    "leases": "affitta", "is": "è", "serves": "serve",
    "assembles": "assembla", "tests": "collauda", "enables": "permette",
}
_IT_PHRASES = [
    (r"\bin the United States and internationally\b", "negli Stati Uniti e all'estero"),
    (r"\bin the United States\b", "negli Stati Uniti"),
    (r"\binternationally\b", "all'estero"),
    (r"\bworldwide\b", "in tutto il mondo"),
    (r"\bglobally\b", "nel mondo"),
    (r"\bin North America\b", "in Nord America"),
    (r"\bin Europe\b", "in Europa"),
    (r"\bin China\b", "in Cina"),
    (r"\bin Japan\b", "in Giappone"),
    (r"\bengages in\b", "si occupa di"),
    (r"\bfocuses on\b", "si concentra su"),
    (r"\bspecializes in\b", "è specializzata in"),
    (r"\boperates as an?\b", "opera come"),
    (r"\bthe research, development, and commercialization of\b", "ricerca, sviluppo e vendita di"),
    (r"\bthe development and commercialization of\b", "sviluppo e vendita di"),
    (r"\bthe design, development, and sale of\b", "progettazione, sviluppo e vendita di"),
    (r"\bthe discovery, development, and commercialization of\b", "scoperta, sviluppo e vendita di"),
    (r"\bdesign\b", "progettazione"),
    (r"\bdevelopment\b", "sviluppo"),
    (r"\bcommercialization\b", "vendita"),
    (r"\bmanufacture\b", "produzione"),
    (r"\bmanufacturing\b", "produzione"),
    (r"\bsale\b", "vendita"),
    (r"\bresearch\b", "ricerca"),
    (r"\bdistribution\b", "distribuzione"),
    (r"\bsoftware solutions\b", "soluzioni software"),
    (r"\bsoftware platform\b", "piattaforma software"),
    (r"\bcloud-based\b", "in cloud"),
    (r"\bsolutions\b", "soluzioni"),
    (r"\bservices\b", "servizi"),
    (r"\bproducts\b", "prodotti"),
    (r"\bplatforms?\b", "piattaforma"),
    (r"\btherapies\b", "terapie"),
    (r"\btherapeutics\b", "terapie"),
    (r"\bmedical devices\b", "dispositivi medici"),
    (r"\bsemiconductors\b", "semiconduttori"),
    (r"\bcustomers\b", "clienti"),
    (r"\bcompanies\b", "aziende"),
    (r"\bbusinesses\b", "imprese"),
    (r"\bpatients\b", "pazienti"),
    (r"\btreatment of\b", "cura di"),
    (r"\bfor the\b", "per il"),
    (r"\bfor\b", "per"),
    (r"\band\b", "e"),
    (r"\bor\b", "o"),
    (r"\bwith\b", "con"),
    (r"\bof\b", "di"),
    (r"\bthrough\b", "tramite"),
    (r"\bthat\b", "che"),
    (r"\bacross\b", "in"),
]


def cosa_fa_it(desc_en):
    """Versione italiana semplice della descrizione breve: traduce i verbi
    iniziali e le parole più frequenti; il resto resta in inglese."""
    if not desc_en:
        return desc_en
    s = desc_en
    # verbi iniziali, anche in elenco ("Designs, develops, and markets")
    m = re.match(r"^((?:[A-Za-z]+(?:,\s*and\s+|\s+and\s+|,\s*))*[A-Za-z]+)\b(.*)$", s)
    if m:
        words = re.split(r",\s*and\s+|\s+and\s+|,\s*", m.group(1))
        if words and all(w.lower() in _IT_VERBS for w in words):
            it = [_IT_VERBS[w.lower()] for w in words]
            head = it[0] if len(it) == 1 else ", ".join(it[:-1]) + " e " + it[-1]
            s = head + m.group(2)
    s = re.sub(r"^(Si occupa) in\b", r"\1 di", s, flags=re.I)
    s = re.sub(r"^(Si concentra) on\b", r"\1 su", s, flags=re.I)
    for pat, rep in _IT_PHRASES:
        s = re.sub(pat, rep, s)
    s = re.sub(r"\b(a|an|the)\s+", "", s)  # articoli inglesi: tolti
    s = s.replace(", e ", " e ").replace(", o ", " o ")  # virgola prima di "and" all'inglese
    s = re.sub(r"\s+", " ", s).strip()
    return s[:1].upper() + s[1:]


# ----------------------------- primo filtro (cache) -----------------------------


def prefilter(info):
    """Solo dati della cache .info del GARP, nessuna chiamata di rete. Soglie
    allargate di prefilter_slack per poter mostrare anche i near miss.
    Versione B1: solo capitalizzazione, crescita dei ricavi e margine lordo
    (prezzo e analisti non sono più filtri)."""
    if not info or info.get("sector") in COMMODITY_SECTORS:
        return False
    C, k = CRITERIA, CRITERIA["prefilter_slack"]
    m = mcap_usd(info)
    if m is None or not (C["mcap_min_usd"] * k <= m <= C["mcap_max_usd"] / k):
        return False
    rg = _num(info.get("revenueGrowth"))
    if rg is None or not (C["rev_growth_min"] * k <= rg <= C["rev_growth_max"] / k):
        return False
    gm = _num(info.get("grossMargins"))
    if gm is not None and gm < C["gross_margin_min_hw"] * k:
        return False
    return True


# ----------------------------- stage 2 (rete) -----------------------------


def _row(df, *names):
    if df is None or getattr(df, "empty", True):
        return None
    for n in names:
        if n in df.index:
            r = df.loc[n]
            r = r[r.notna()].sort_index()
            return r if len(r) else None
    return None


def quarterly_metrics(q):
    """Dalle trimestrali (Yahoo ne dà ~5): crescite YoY, margini lordo e
    operativo per trimestre, margine operativo degli ultimi 12 mesi."""
    out = {"q_rev_yoy": None, "q_rev_yoy_prev": None, "gm_q": None, "gm_q_1y": None,
           "gm_ttm": None, "gm_ttm_prev": None, "om_q": None, "om_q_1y": None, "om_q_2ago": None, "om_ttm": None,
           "om_ttm_prev": None, "op_cross_zero": False}
    rev = _row(q, "Total Revenue", "Operating Revenue")
    if rev is None:
        return out
    v = [float(x) for x in rev.values]  # dal più vecchio al più recente
    if len(v) >= 5 and v[-5] > 0:
        out["q_rev_yoy"] = v[-1] / v[-5] - 1
    if len(v) >= 6 and v[-6] > 0:
        out["q_rev_yoy_prev"] = v[-2] / v[-6] - 1
    gp = _row(q, "Gross Profit")
    if gp is not None:
        c = gp.index.intersection(rev.index).sort_values()
        mm = [float(gp[d] / rev[d]) for d in c if rev[d] > 0]
        if mm:
            out["gm_q"] = mm[-1]
        if len(mm) >= 5:
            out["gm_q_1y"] = mm[-5]
        c = [d for d in c if rev[d] > 0]
        if len(c) >= 4:
            out["gm_ttm"] = float(sum(gp[d] for d in c[-4:]) / sum(rev[d] for d in c[-4:]))
        if len(c) >= 8:
            out["gm_ttm_prev"] = float(sum(gp[d] for d in c[-8:-4]) / sum(rev[d] for d in c[-8:-4]))
    oi = _row(q, "Operating Income", "EBIT")
    if oi is not None:
        c = [d for d in oi.index.intersection(rev.index).sort_values() if rev[d] > 0]
        mm = [float(oi[d] / rev[d]) for d in c]
        if mm:
            out["om_q"] = mm[-1]
        if len(mm) >= 3:
            out["om_q_2ago"] = mm[-3]
        if len(mm) >= 5:
            out["om_q_1y"] = mm[-5]
        if len(c) >= 4:
            out["om_ttm"] = float(sum(oi[d] for d in c[-4:]) / sum(rev[d] for d in c[-4:]))
        if len(c) >= 8:
            out["om_ttm_prev"] = float(sum(oi[d] for d in c[-8:-4]) / sum(rev[d] for d in c[-8:-4]))
        last5 = [float(oi[d]) for d in c[-5:]]
        out["op_cross_zero"] = len(last5) >= 2 and last5[-1] > 0 and min(last5[:-1]) < 0
    return out


def annual_metrics(a):
    out = {"rev_growth_fy": None, "om_fy": None, "om_fy_prev": None,
           "gm_fy": None, "gm_fy_prev": None}
    rev = _row(a, "Total Revenue", "Operating Revenue")
    if rev is None:
        return out
    if len(rev) >= 2 and rev.iloc[-2] > 0:
        out["rev_growth_fy"] = float(rev.iloc[-1] / rev.iloc[-2] - 1)
    for key, names in (("gm", ("Gross Profit",)), ("om", ("Operating Income", "EBIT"))):
        r = _row(a, *names)
        if r is None:
            continue
        common = r.index.intersection(rev.index)
        mm = (r[common] / rev[common]).sort_index()
        if len(mm):
            out[f"{key}_fy"] = float(mm.iloc[-1])
        if len(mm) >= 2:
            out[f"{key}_fy_prev"] = float(mm.iloc[-2])
    return out


def dilution_1y(bs):
    """Variazione annua delle azioni tra gli ultimi due bilanci annuali."""
    r = _row(bs, "Ordinary Shares Number", "Share Issued")
    if r is None:
        return None
    try:
        if len(r) >= 2 and float(r.iloc[-2]) > 0:
            years = max((r.index[-1] - r.index[-2]).days / 365.25, 0.5)
            return (float(r.iloc[-1]) / float(r.iloc[-2])) ** (1 / years) - 1
    except Exception:
        pass
    return None


def eps_estimates(tr):
    """EPS stimato anno corrente/prossimo, revisione in 90 giorni (ripiego a 60:
    Yahoo a volte mette 0 nel campo 90daysAgo) e variazione in 30 giorni."""
    out = {"eps_next_y": None, "eps_cur_y": None, "revision_90d": None,
           "revision_base": None, "revision_30d": None}
    if tr is None or getattr(tr, "empty", True):
        return out
    try:
        if "0y" in tr.index:
            out["eps_cur_y"] = _num(tr.loc["0y"].get("current"))
        if "+1y" in tr.index:
            row = tr.loc["+1y"]
            cur = _num(row.get("current"))
            out["eps_next_y"] = cur
            for col, lab in (("90daysAgo", "90g"), ("60daysAgo", "60g")):
                old = _num(row.get(col))
                if cur is not None and old not in (None, 0.0):
                    out["revision_90d"] = (cur - old) / abs(old)
                    out["revision_base"] = lab
                    break
            old30 = _num(row.get("30daysAgo"))
            if cur is not None and old30 not in (None, 0.0):
                out["revision_30d"] = (cur - old30) / abs(old30)
    except Exception:
        pass
    return out


def insider_buy_share(ip):
    """Quota di azioni comprate dagli insider sul totale scambiato (6 mesi)."""
    if ip is None or getattr(ip, "empty", True):
        return None
    try:
        col0 = ip.columns[0]
        rows = {str(r[col0]).strip(): _num(r.get("Shares")) for _, r in ip.iterrows()}
        b, s = rows.get("Purchases") or 0, rows.get("Sales") or 0
        return b / (b + s) if (b + s) > 0 else None
    except Exception:
        return None


def evaluate(symbol, cached, index_name=None, strict=False):
    """Valutazione completa di un candidato (dopo il primo filtro)."""
    if time.time() > DEADLINE[0]:
        return {"ticker": symbol, "error": "tempo dello shard esaurito", "timeout": True}
    try:
        tk = yf.Ticker(symbol)
        full = _fetch(lambda: tk.info) or {}
        info = dict(cached or {})
        info.update({k: v for k, v in full.items() if v is not None})
        if info.get("marketCap") is None:
            return {"ticker": symbol, "error": "nessun dato"}
        q = _fetch(lambda: tk.quarterly_income_stmt)
        a = _fetch(lambda: tk.income_stmt)
        bs = _fetch(lambda: tk.balance_sheet)
        tr = _fetch(lambda: tk.eps_trend)
        ip = _fetch(lambda: tk.insider_purchases, tries=1)
        time.sleep(PAUSE_BETWEEN + random.random() * 0.5)
        if not full and q is None and a is None:
            # niente di nuovo da Yahoo oltre alla cache: errore, verrà ritentato
            return {"ticker": symbol, "error": "dettagli non scaricati (limite Yahoo?)"}
        if strict and q is None:
            # le trimestrali decidono i filtri B1; le stime contano solo nel punteggio
            return {"ticker": symbol, "error": "dati incompleti (trimestrali)"}
        r = score_one(symbol, info, quarterly_metrics(q), annual_metrics(a),
                      dilution_1y(bs), eps_estimates(tr), insider_buy_share(ip),
                      index_name)
        r["dati_mancanti"] = [n for n, v in (("info", full), ("trimestrali", q), ("annuali", a),
                                             ("bilancio", bs), ("stime", tr))
                              if v is None or (isinstance(v, dict) and not v)]
        return r
    except Exception as e:
        return {"ticker": symbol, "error": str(e)}


def _first(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def score_one(symbol, info, qm, am, dil, est, ins, index_name=None):
    C = CRITERIA
    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    high = _num(info.get("fiftyTwoWeekHigh"))
    low = _num(info.get("fiftyTwoWeekLow"))
    pct_high = price / high if price and high else None
    x_low = price / low if price and low and low > 0 else None
    m_usd = mcap_usd(info)
    hw = is_hardware(info)

    # ---------------- utili (solo informazione: il primo utile non è più un filtro) ----------------
    eps_ttm = _num(info.get("trailingEps"))
    eps_next = _first(est["eps_next_y"], _num(info.get("forwardEps")))
    near_zero = eps_ttm is not None and (eps_ttm <= 0 or bool(price and eps_ttm / price <= C["eps_near_zero_yield"]))
    eps_turn = bool(near_zero and eps_next is not None and eps_next > 0 and eps_next > eps_ttm)

    # ---------------- margine operativo in svolta ----------------
    om = _first(qm["om_ttm"], _num(info.get("operatingMargins")), am["om_fy"])
    # variazione su un anno: 12 mesi su 12 mesi se ci sono 8 trimestri,
    # altrimenti ultimo anno fiscale sul precedente
    if qm["om_ttm"] is not None and qm["om_ttm_prev"] is not None:
        om_delta, om_src = qm["om_ttm"] - qm["om_ttm_prev"], "12 mesi su 12 mesi"
    elif am["om_fy"] is not None and am["om_fy_prev"] is not None:
        om_delta, om_src = am["om_fy"] - am["om_fy_prev"], "anno fiscale"
    else:
        om_delta, om_src = None, None
    om_delta_q = qm["om_q"] - qm["om_q_1y"] if qm["om_q"] is not None and qm["om_q_1y"] is not None else None
    # variazioni oltre 50 punti = trimestre anomalo (quotazione, svalutazioni): ignorate
    clip = lambda x: None if x is None or abs(x) > 0.5 else x
    om_delta, om_delta_q = clip(om_delta), clip(om_delta_q)
    jump = bool((om_delta is not None and om_delta >= C["op_margin_jump_min"])
                or (om_delta_q is not None and om_delta_q >= C["op_margin_jump_q_min"]))
    # variazione "efficace" per il punteggio: +8 punti sul trimestre valgono come +5 annui
    d_eff = max([x for x in (om_delta, None if om_delta_q is None else om_delta_q - 0.03)
                 if x is not None], default=None)
    # livello: margine operativo degli ultimi 12 mesi (backtest B1)
    level_ok = om is not None and C["op_margin_level_min"] <= om <= C["op_margin_level_max"]
    worsening = qm["om_q"] is not None and qm["om_q_2ago"] is not None and qm["om_q"] < qm["om_q_2ago"]
    svolta_ok = bool(jump and level_ok and not worsening)

    # ---------------- ricavi ----------------
    rg = _first(qm["q_rev_yoy"], _num(info.get("revenueGrowth")))
    if qm["q_rev_yoy"] is not None and qm["q_rev_yoy_prev"] is not None:
        accel, accel_src = qm["q_rev_yoy"] - qm["q_rev_yoy_prev"], "trimestre su trimestre precedente"
    elif rg is not None and am["rev_growth_fy"] is not None:
        accel, accel_src = rg - am["rev_growth_fy"], "trimestre su ultimo anno fiscale"
    else:
        accel, accel_src = None, None
    accelerating = accel is not None and accel >= C["accel_min"]

    # ---------------- margine lordo (12 mesi) ----------------
    gm = _first(qm["gm_ttm"], _num(info.get("grossMargins")), am["gm_fy"])
    # "non in calo rispetto a 4 trimestri prima": 12 mesi su 12 mesi se ci sono
    # 8 trimestri, altrimenti ultimo trimestre sullo stesso dell'anno prima,
    # altrimenti anno fiscale sul precedente
    if qm["gm_ttm"] is not None and qm["gm_ttm_prev"] is not None:
        gm_d, gm_src = qm["gm_ttm"] - qm["gm_ttm_prev"], "12 mesi su 12 mesi"
    elif qm["gm_q"] is not None and qm["gm_q_1y"] is not None:
        gm_d, gm_src = qm["gm_q"] - qm["gm_q_1y"], "trimestre sullo stesso dell'anno prima"
    elif am["gm_fy"] is not None and am["gm_fy_prev"] is not None:
        gm_d, gm_src = am["gm_fy"] - am["gm_fy_prev"], "anno fiscale"
    else:
        gm_d, gm_src = None, None
    gm_min = C["gross_margin_min_hw"] if hw else C["gross_margin_min"]
    gm_rising = gm_d is not None and gm_d >= C["gross_margin_rising_min"]
    gm_not_falling = gm_d is None or gm_d >= -C["gross_margin_drop_max"]

    # ---------------- bilancio (avvisi, non filtri) ----------------
    cash = _num(info.get("totalCash"))
    debt = _num(info.get("totalDebt"))
    fcf = _num(info.get("freeCashflow"))
    ebitda = _num(info.get("ebitda"))
    runway = (cash or 0) / abs(fcf) if fcf is not None and fcf < 0 else None
    nd_ebitda = ((debt or 0) - (cash or 0)) / ebitda if ebitda and ebitda > 0 else None
    analysts = info.get("numberOfAnalystOpinions")
    rv, rv30 = est["revision_90d"], est["revision_30d"]
    avvisi = []
    if dil is not None and dil > C["dilution_max"]:
        avvisi.append(f"diluizione {dil*100:.0f}% l'anno (oltre 10%)")
    if runway is not None and runway < C["runway_years_min"]:
        avvisi.append(f"cassa per {runway:.1f} anni al consumo attuale (meno di 2)")
    # guardia di sicurezza del GARP (08/11/2026): qui solo etichetta, non esclude
    sic_dati = {"variazione_azioni_1a": dil, "pct_max_52s": pct_high}
    sic_motivi = base.safety_reasons(sic_dati)

    checks = {
        # filtri obbligatori B1
        "mcap_ok": m_usd is not None and C["mcap_min_usd"] <= m_usd <= C["mcap_max_usd"],
        "settore_ok": (info.get("industry") or "") not in LOW_MARGIN_INDUSTRIES
                      and info.get("sector") not in COMMODITY_SECTORS,
        "svolta_ok": svolta_ok,
        "crescita_ok": rg is not None and C["rev_growth_min"] <= rg <= C["rev_growth_max"],
        "margine_lordo_ok": gm is not None and gm >= gm_min and gm_not_falling,
        # informativi (non più filtri dal backtest del 03/11/2026)
        "revisioni_ok": rv is not None and rv >= C["revision_90d_min"]
                        and not (rv30 is not None and rv30 < C["revision_30d_cut_max"]),
        "prezzo_ok": pct_high is not None and C["pct_of_52w_high_min"] <= pct_high <= C["pct_of_52w_high_max"]
                     and not (x_low is not None and x_low > C["x_52w_low_max"]),
        "runway_ok": runway is None or runway >= C["runway_years_min"],
        "diluizione_ok": dil is None or dil <= C["dilution_max"],
        "leva_ok": nd_ebitda is None or nd_ebitda < C["net_debt_ebitda_max"],
        "copertura_ok": analysts is None or analysts <= C["analysts_max"],
        "accelerazione_ok": accelerating,
        "pochi_analisti_ok": analysts is not None and analysts <= C["analysts_few"],
        "insider_ok": ins is not None and ins >= C["insider_buy_share_min"],
        "primo_utile": eps_turn,
    }

    # ---------------- punteggio (solo per ordinare) ----------------
    pts, motivi = {}, []
    s = 0
    if d_eff is not None and jump:
        s = 25 if d_eff >= 0.15 else 18 if d_eff >= 0.10 else 10
    pts["margine_operativo"] = s
    if om_delta is not None and om_delta >= C["op_margin_jump_min"]:
        motivi.append(f"margine operativo {om_delta*100:+.0f} punti ({om_src}), 12 mesi {om*100:.0f}%")
    elif om_delta_q is not None and om_delta_q >= C["op_margin_jump_q_min"]:
        motivi.append(f"margine operativo dell'ultimo trimestre {om_delta_q*100:+.0f} punti sull'anno prima"
                      + (f", 12 mesi {om*100:.0f}%" if om is not None else ""))

    s = 0
    if gm is not None:
        s = 10 if gm >= 0.75 else 7 if gm >= 0.60 else 4 if gm >= 0.55 else 2 if gm >= 0.40 else 0
        if hw and s:
            s -= 1  # margini da hardware: un punto in meno (come nel backtest)
        if gm_rising:
            s += 5
            motivi.append(f"margine lordo {gm*100:.0f}% in salita ({gm_d*100:+.0f} punti)")
        elif gm >= gm_min:
            motivi.append(f"margine lordo {gm*100:.0f}%")
    pts["margine_lordo"] = s

    s = 0
    if rg is not None and rg >= C["rev_growth_min"]:
        s = 6 if rg < 0.30 else 10 if rg < 0.45 else 8
        if accelerating:
            s += 5
            motivi.append(f"ricavi +{rg*100:.0f}% e in accelerazione ({accel*100:+.0f} punti)")
        else:
            motivi.append(f"ricavi +{rg*100:.0f}%")
    pts["crescita"] = s

    # revisioni: peso ridotto (5 su 80), non verificabili su dati storici
    s = 0
    if rv is not None:
        s = 5 if rv >= 0.20 else 3 if rv >= 0.10 else 2 if rv >= 0.05 else 0
        if rv >= 0.05:
            motivi.append(f"stime anno prossimo {rv*100:+.0f}% in {est['revision_base'] or '90g'} (non testato)")
    pts["revisioni"] = s

    s = 0
    if fcf is not None and fcf > 0:
        s += 5
    elif runway is not None and runway >= 3:
        s += 2
    if cash is not None and cash > (debt or 0):
        s += 3
    if dil is not None and dil < 0.02:
        s += 2
    pts["bilancio"] = s
    if fcf is not None and fcf > 0 and cash is not None and cash > (debt or 0):
        motivi.append("cassa netta e flusso di cassa positivo")

    # prezzo rispetto alla crescita: solo informazione (non nel punteggio dal 03/11/2026)
    pe_next = price / eps_next if price and eps_next and eps_next > 0 else None
    g = None
    if est["eps_cur_y"] and est["eps_cur_y"] > 0 and eps_next:
        g = eps_next / est["eps_cur_y"] - 1
    if g is None or g <= 0:
        g = rg
    peg_next = pe_next / (g * 100) if pe_next and g and g > 0 else None
    pts["prezzo_crescita"] = 0

    s = 0
    if x_low is not None and C["x_52w_low_score_min"] <= x_low <= C["x_52w_low_score_max"]:
        s = 10
        motivi.append(f"prezzo {x_low:.1f} volte il minimo a 52 settimane")
    if pct_high is not None and pct_high > C["pct_of_52w_high_penalty"]:
        s -= 3
    pts["posizione_prezzo"] = s

    pts["scoperta"] = 0   # non più nel punteggio (numero analisti, insider: solo informazione)
    pts["penalita"] = 0   # non più penalità per capitalizzazione o vendite degli insider

    raw = max(0, sum(pts.values()))
    total = max(0, min(100, round(raw * 100 / SCORE_MAX_RAW)))
    hard_fail = [k for k in HARD_CHECKS if not checks[k]]
    ind = info.get("industry") or ""
    desc_en = short_desc(info.get("longBusinessSummary"),
                         name=info.get("longName") or info.get("shortName")) or ind

    return {
        "ticker": symbol,
        "nome": info.get("longName") or info.get("shortName"),
        "indice": index_name,
        "settore": info.get("sector"),
        "industria": info.get("industry"),
        "paese": info.get("country"),
        "valuta": info.get("currency"),
        "cosa_fa": cosa_fa_it(desc_en),
        "cosa_fa_en": desc_en,
        "capitalizzazione": _num(info.get("marketCap")),
        "capitalizzazione_usd": m_usd,
        "prezzo": price,
        "pct_of_52w_high": pct_high,
        "volte_minimo_52w": x_low,
        "crescita_ricavi": rg,
        "accelerazione": accel,
        "accelerazione_metodo": accel_src,
        "margine_lordo": gm,
        "margine_lordo_variazione": gm_d,
        "margine_lordo_metodo": gm_src,
        "margine_lordo_trimestre": qm["gm_q"],
        "margine_operativo": om,
        "margine_operativo_variazione": om_delta,
        "margine_operativo_metodo": om_src,
        "margine_operativo_var_trimestre": om_delta_q,
        "margine_operativo_trimestre": qm["om_q"],
        "margine_operativo_trimestre_2fa": qm["om_q_2ago"],
        "eps_ttm": eps_ttm,
        "eps_prossimo_anno": eps_next,
        "primo_utile": eps_turn,
        "revisione_stime_90g": rv,
        "revisione_base": est["revision_base"],
        "revisione_stime_30g": rv30,
        "revisioni_nota": "non verificabile storicamente: solo informazione e punteggio ridotto",
        "pe_anno_prossimo": pe_next,
        "peg_anno_prossimo": peg_next,
        "numero_analisti": analysts,
        "cassa": cash,
        "debito": debt,
        "free_cash_flow": fcf,
        "debito_netto_ebitda": nd_ebitda,
        "runway": runway,
        "diluizione": dil,
        "insider_quota_acquisti": ins,
        "avvisi": avvisi,
        "sicurezza_ok": base.safety_flag(sic_dati, sic_motivi),
        "sicurezza_motivi": sic_motivi,
        "sicurezza_nota": base.safety_note(sic_dati, sic_motivi),
        "tema_affollato": any(w in ind for w in CROWDED_INDUSTRY_WORDS),
        "punteggio_100": total,
        "punteggio": round(total / 10, 1),
        "punteggio_dettaglio": pts,
        "motivi": motivi,
        "checks": checks,
        "failed_checks": hard_fail,
        "passed": not hard_fail,
    }


def run_stage2(cands, cache):
    """Stage 2 sui candidati, con retry a concorrenza ridotta per gli errori."""
    results, pending = {}, dict(cands)
    DEADLINE[0] = time.time() + TIME_BUDGET
    for attempt in range(3):
        if time.time() > DEADLINE[0]:
            print("  svolta: tempo esaurito, salvo quello che ho", file=sys.stderr)
            break
        errored = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS if attempt == 0 else 1) as ex:
            # alle prime passate i dati incompleti (stime/trimestrali) sono un
            # errore da ritentare; all'ultima si tiene quello che c'è
            futs = {ex.submit(evaluate, t, cache.get(t), i, attempt < 2): t
                    for t, i in pending.items()}
            for fut in as_completed(futs):
                t = futs[fut]
                r = fut.result()
                results[t] = r
                if r.get("error"):
                    errored[t] = pending[t]
        if not errored:
            break
        print(f"  svolta: {len(errored)} errori alla passata {attempt+1}, riprovo")
        pending = errored
        time.sleep(20 + 10 * attempt)
    return list(results.values())


def screen_subset(sub, cache):
    """Primo filtro dalla cache + stage 2 sui candidati. Ritorna il parziale."""
    analyzed = {t: cache[t] for t in sub if cache.get(t)}
    refresh_fx({(i or {}).get("currency") for i in analyzed.values()})
    cands = [t for t, i in analyzed.items() if prefilter(i)]
    cands.sort(key=lambda t: -(_num(analyzed[t].get("revenueGrowth")) or 0))
    if len(cands) > STAGE2_MAX:
        print(f"  svolta: {len(cands)} candidati, tengo i {STAGE2_MAX} a crescita più alta")
        cands = cands[:STAGE2_MAX]
    print(f"Svolta: {len(analyzed)} con dati, {len(cands)} superano il primo filtro")
    results = run_stage2({t: sub.get(t) for t in cands}, analyzed) if cands else []
    return {"analyzed": len(analyzed), "no_data": len(sub) - len(analyzed),
            "prefilter_passed": len(cands), "results": results}


# ----------------------------- report -----------------------------


def load_svolta_partials():
    pdir = os.environ.get("PARTIALS_DIR", "partials")
    files = sorted(glob.glob(os.path.join(pdir, "svolta-*.json")))
    if not files:
        print(f"ERRORE: nessun parziale svolta-*.json in {pdir}: non sovrascrivo i risultati",
              file=sys.stderr)
        sys.exit(1)
    by_t, usize, analyzed, prefilt, no_data, shards = {}, 0, 0, 0, 0, []
    for fp in files:
        try:
            with open(fp) as f:
                d = json.load(f)
        except Exception as e:
            print(f"[WARN] parziale {fp} illeggibile: {e}", file=sys.stderr)
            continue
        shards.append(d.get("shard"))
        usize = max(usize, int(d.get("universe_size") or 0))
        analyzed += int(d.get("analyzed") or 0)
        prefilt += int(d.get("prefilter_passed") or 0)
        no_data += int(d.get("no_data") or 0)
        for r in d.get("results") or []:
            t = r.get("ticker")
            if t not in by_t or (by_t[t].get("error") and not r.get("error")):
                by_t[t] = r
    print(f"Uniti {len(files)} parziali svolta: {len(by_t)} candidati valutati")
    return list(by_t.values()), {"universe_size": usize, "analyzed": analyzed,
                                 "prefilter_passed": prefilt, "no_data": no_data,
                                 "shards": sorted(s for s in shards if s is not None)}


def _pct(x, d=0):
    return f"{x*100:.{d}f}%" if isinstance(x, (int, float)) else "n/d"


def _eps(x):
    return f"{x:.2f}" if isinstance(x, (int, float)) else "n/d"


def _money(x):
    if not isinstance(x, (int, float)):
        return "n/d"
    a = abs(x)
    return f"{x/1e9:.1f} Mld" if a >= 1e9 else f"{x/1e6:.0f} M"


def make_report(results, meta, started):
    ok = [r for r in results if not r.get("error")]
    errors = [r["ticker"] for r in results if r.get("error")]
    passed = sorted([r for r in ok if r.get("passed")], key=lambda r: -r["punteggio"])
    for k, r in enumerate(passed, 1):
        r["posizione"] = k
    near = sorted([r for r in ok if not r.get("passed") and len(r.get("failed_checks") or []) == 1],
                  key=lambda r: -r["punteggio"])
    for r in near:
        r["failed_check"] = r["failed_checks"][0]
    # da radiografare: tutti se sono 8 o meno, altrimenti i primi 8 per punteggio
    radio = passed if len(passed) <= TOP_RADIOGRAFIA else passed[:TOP_RADIOGRAFIA]
    radio_set = {r["ticker"] for r in radio}
    for r in passed:
        r["da_radiografare"] = r["ticker"] in radio_set

    latest_path = os.path.join(RESULTS_DIR, "latest.json")
    prev = set()
    if os.path.exists(latest_path):
        try:
            with open(latest_path) as f:
                prev = {p["ticker"] for p in json.load(f).get("passed", [])}
        except Exception:
            pass
    tickers = {r["ticker"] for r in passed}
    new_today = [r["ticker"] for r in passed if r["ticker"] not in prev] if prev else []

    today = date.today().isoformat()
    report = {
        "screener": "svolta",
        "date": today,
        "generated_at_utc": started.isoformat(),
        "duration_seconds": round((datetime.now(timezone.utc) - started).total_seconds()),
        "versione_criteri": VERSIONE_CRITERI,
        "criteria": CRITERIA,
        "hard_checks": HARD_CHECKS,
        "universe_size": meta["universe_size"],
        "analyzed": meta["analyzed"],
        "no_data": meta["no_data"],
        "prefilter_passed": meta["prefilter_passed"],
        "shards_merged": meta["shards"],
        "errors": len(errors),
        "error_tickers": errors,
        "passed_count": len(passed),
        "new_today": new_today,
        "dropped_since_yesterday": sorted(prev - tickers),
        "da_radiografare": [r["ticker"] for r in radio],
        "regola_radiografia": f"tutti i promossi se sono {TOP_RADIOGRAFIA} o meno, altrimenti "
                              f"i primi {TOP_RADIOGRAFIA} per punteggio; ricontrollo ogni trimestre",
        "punteggio_uso": "solo per ordinare: nessuna soglia d'acquisto",
        "passed": passed,
        "near_miss_count": len(near),
        "near_miss": near[:40],
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    for p in (os.path.join(RESULTS_DIR, f"{today}.json"), latest_path):
        with open(p, "w") as f:
            json.dump(report, f, indent=1, default=str)

    nomi_check = {"mcap_ok": "capitalizzazione fuori 1-15 Mld$",
                  "settore_ok": "settore a margine basso",
                  "svolta_ok": "margine operativo non in svolta (o fuori -15%/+20%, o ultimo trimestre in calo)",
                  "crescita_ok": "ricavi dell'ultimo trimestre fuori +20%/+60%",
                  "margine_lordo_ok": "margine lordo basso o in calo"}
    n_radio = len(radio)
    L = [f"# Screener Svolta — {today}", "",
         "> **Elenco di candidate da RADIOGRAFARE, non da comprare.** Sono aziende con margine "
         "lordo alto, ricavi in crescita sana e margine operativo in svolta (versione B1). "
         "Ognuna va analizzata a mano prima di qualsiasi decisione.", "",
         "> **Cosa dice il backtest storico (2012-2026, 03/11/2026).** Il nucleo B1 ha battuto "
         "l'universo di **+10,5 punti annui nel 2012-19** e **+22 nel 2020-24**, ma ha fatto "
         "**-6,7 punti nel 2025-26**. Pochi titoli e criteri scelti dopo molti test: è "
         "un'ipotesi da seguire in tempo reale, non una regola provata. Quota satellite piccola.", "",
         f"> **Come si usa.** Se i promossi sono {TOP_RADIOGRAFIA} o meno si considerano tutti; "
         f"altrimenti i primi {TOP_RADIOGRAFIA} per punteggio. Il punteggio serve **solo a "
         "ordinare** (nessuna soglia d'acquisto). **Ricontrollo ogni trimestre**, dopo i conti: "
         "chi esce dai filtri esce, senza aspettare.", "",
         f"Universo: {meta['universe_size']} | Con dati: {meta['analyzed']} | Primo filtro: "
         f"{meta['prefilter_passed']} | **Promossi: {len(passed)}** | Da radiografare: {n_radio} | "
         f"Errori: {len(errors)} | "
         f"Nuovi: {', '.join(new_today) or '—'} | Usciti: {', '.join(report['dropped_since_yesterday']) or '—'}",
         ""]
    if radio:
        L += [f"**Da radiografare ({n_radio}):** " + ", ".join(r["ticker"] for r in radio), ""]
    L += [f"## Classifica (prime {min(TOP_N_MD, len(passed))})", ""]
    if not passed:
        L.append("Nessun titolo supera oggi tutti i filtri obbligatori.")
    for r in passed[:TOP_N_MD]:
        omv = r.get("margine_operativo_variazione")
        omv_s = "n/d" if omv is None else f"{omv*100:+.0f} punti"
        tag = " · **da radiografare**" if r.get("da_radiografare") else ""
        crowd = " · tema AI affollato" if r.get("tema_affollato") else ""
        L += [f"**{r['posizione']}. {r['ticker']} — {r.get('nome') or ''}** · punteggio "
              f"{r['punteggio']:.1f}/10{tag} · {r.get('settore') or 'n/d'}, {r.get('paese') or 'n/d'} · "
              f"cap. {_money(r.get('capitalizzazione_usd'))} ${crowd}",
              f"- Cosa fa: {r.get('cosa_fa') or 'n/d'}",
              f"- Perché: {'; '.join(r.get('motivi') or []) or '—'}",
              f"- Numeri: ricavi {_pct(r.get('crescita_ricavi'))}, margine lordo 12 mesi "
              f"{_pct(r.get('margine_lordo'))}, margine operativo 12 mesi {_pct(r.get('margine_operativo'))}"
              f" ({omv_s}), ultimo trimestre {_pct(r.get('margine_operativo_trimestre'))}, "
              f"EPS 12m {_eps(r.get('eps_ttm'))} → anno prossimo {_eps(r.get('eps_prossimo_anno'))}, "
              f"stime {_pct(r.get('revisione_stime_90g'))} in 90g (non testato), "
              f"analisti {r.get('numero_analisti') if r.get('numero_analisti') is not None else 'n/d'}, "
              f"{_pct(r.get('pct_of_52w_high'))} del massimo 52 sett."
              + (f" (dati mancanti: {', '.join(r['dati_mancanti'])})" if r.get("dati_mancanti") else "")]
        if r.get("avvisi"):
            L.append(f"- ⚠ Avvisi: {'; '.join(r['avvisi'])}")
        if r.get("sicurezza_ok") is False:
            L.append(f"- ⚠ Guardia di sicurezza non superata (solo etichetta): {r.get('sicurezza_nota')}")
        L.append("")
    if len(passed) > TOP_N_MD:
        L += ["## Gli altri promossi", "",
              "| # | Ticker | Nome | Punteggio | Ricavi | Margine lordo | Margine op. 12m | Avvisi |",
              "|---|---|---|---|---|---|---|---|"]
        for r in passed[TOP_N_MD:]:
            L.append(f"| {r['posizione']} | {r['ticker']} | {(r.get('nome') or '')[:30]} | "
                     f"{r['punteggio']:.1f} | {_pct(r.get('crescita_ricavi'))} | "
                     f"{_pct(r.get('margine_lordo'))} | {_pct(r.get('margine_operativo'))} | "
                     f"{'; '.join(r.get('avvisi') or []) or '—'} |")
        L.append("")
    if near:
        L += ["## Quasi (manca un solo filtro)", "",
              "| Ticker | Nome | Punteggio | Cosa manca | Cosa fa |", "|---|---|---|---|---|"]
        for r in near[:15]:
            L.append(f"| {r['ticker']} | {(r.get('nome') or '')[:30]} | {r['punteggio']:.1f} | "
                     f"{nomi_check.get(r['failed_check'], r['failed_check'])} | "
                     f"{(r.get('cosa_fa') or '')[:70]} |")
        L.append("")
    L += ["Filtri obbligatori (versione B1, backtest del 03/11/2026): margine lordo degli ultimi "
          "12 mesi ≥ 55% (≥ 40% industria/hardware) e non in calo rispetto a 4 trimestri prima; "
          "ricavi dell'ultimo trimestre +20%/+60% sull'anno prima; margine operativo in svolta "
          "(12 mesi almeno +5 punti in un anno, oppure ultimo trimestre +8 punti sullo stesso "
          "trimestre dell'anno prima; livello dei 12 mesi tra -15% e +20%; ultimo trimestre non "
          "peggiore di due trimestri prima); capitalizzazione 1-15 Mld$; esclusi costruzioni, auto, "
          "trasporto marittimo, energia e materie prime e i titoli con dati non valutabili.", "",
          "Non sono più filtri: primo utile, solidità di cassa (solo avviso se diluizione > 10% "
          "l'anno o cassa per meno di 2 anni), revisioni delle stime (punteggio ridotto: non "
          "verificabili su dati storici), numero di analisti, posizione del prezzo. Punteggio: "
          "margine operativo, margine lordo (+5 se in salita di ≥ 2 punti), crescita (+5 se in "
          "accelerazione), flusso di cassa positivo e cassa netta, prezzo 1,2-1,8 volte il minimo "
          "a 52 settimane (+10; -3 sopra il 95% del massimo), revisioni (peso ridotto). Da "
          "verificare a mano: eventi binari vicini (FDA, sentenze), crescita da acquisizioni, "
          "temi affollati. \"Cosa fa\" è una traduzione semplice dei primi termini della "
          "descrizione di Yahoo."]
    with open(os.path.join(RESULTS_DIR, "latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"Svolta: {len(passed)} promossi ({n_radio} da radiografare), {len(near)} quasi, "
          f"{len(errors)} errori")


# ----------------------------- main -----------------------------


def _load_cache(shard):
    for p in (os.path.join("partials", f"info-{shard}.json"), base.INFO_CACHE_PATH):
        try:
            with open(p) as f:
                c = json.load(f)
            if c:
                print(f"Cache .info da {p}: {len(c)} ticker")
                return c
        except Exception:
            continue
    return {}


def main():
    started = datetime.now(timezone.utc)
    mode = os.environ.get("MODE", "").strip().lower()
    shard_env = os.environ.get("SHARD", "").strip()

    if mode == "merge":
        results, meta = load_svolta_partials()
        make_report(results, meta, started)
        return

    if shard_env != "":
        shard = int(shard_env)
        shards = int(os.environ.get("SHARDS", "8"))
        try:  # stessa fetta di universo del GARP nello stesso job
            with open(os.path.join("partials", f"garp-{shard}.json")) as f:
                gp = json.load(f)
            sub = {r["ticker"]: r.get("index", "?") for r in gp["results"]}
            usize = int(gp.get("universe_size", 0))
        except Exception:
            universe = base.load_universe_checked()
            usize = len(universe)
            sub = base.shard_of(universe, shard, shards)
        cache = _load_cache(shard)
        part = screen_subset(sub, cache)
        part.update({"shard": shard, "universe_size": usize})
        os.makedirs("partials", exist_ok=True)
        with open(os.path.join("partials", f"svolta-{shard}.json"), "w") as f:
            json.dump(part, f, default=str)
        n_err = sum(1 for r in part["results"] if r.get("error"))
        n_ok = sum(1 for r in part["results"] if r.get("passed"))
        print(f"Shard svolta {shard}: {n_ok} promossi, {n_err} errori")
        return

    # run locale: cache GARP se c'è, altrimenti .info scaricato qui
    universe = base.load_universe_checked()
    cache = _load_cache("none")
    missing = [t for t in universe if t not in cache]
    for t in missing:
        info = _fetch(lambda: yf.Ticker(t).info, tries=2) or {}
        if info:
            cache[t] = {k: info.get(k) for k in base.CACHE_KEYS}
        time.sleep(0.3)
    part = screen_subset(universe, cache)
    meta = {"universe_size": len(universe), "analyzed": part["analyzed"],
            "prefilter_passed": part["prefilter_passed"], "no_data": part["no_data"], "shards": []}
    make_report(part["results"], meta, started)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
