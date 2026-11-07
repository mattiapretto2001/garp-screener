#!/usr/bin/env python3
"""
Lista unificata "da radiografare" (dal 08/11/2026)
==================================================
Gira nel job di merge DOPO tutti gli screener. Legge:
  - results/latest.json           (GARP: core, top 30, radar A, radar B)
  - results-moonshot/latest.json  (Moonshot = lista Crescita per fascia)
  - results-qualita/latest.json   (Qualità durevole, dal 08/11/2026)
  - results-svolta/latest.json    (Svolta)
  - results-temi/latest.json      (Temi: solo etichetta, non testati)
  - disponibilita_tr.csv          (facoltativo: acquistabile su Trade Republic)
e scrive results-lista/latest.json, latest.md e <data>.json.

Una riga per società (ticker normalizzati; le doppie quotazioni con lo stesso
nome sono unite). Famiglie: GARP (core o top 30 contano come UNA famiglia),
Crescita (dal 08/11/2026: Radar A del GARP e Moonshot sono UNA famiglia, una
società conta una volta anche se è in tutte e due), Qualità, Radar B, Svolta.
I Temi danno solo un'etichetta (nessun vantaggio dimostrato).

Trade Republic (dal 08/11/2026): ogni riga ha acquistabile_tr ("probabile",
"incerto", "probabilmente no"; "n.d." se il file manca, è vuoto o non si
legge). Ticker assente dal file = "incerto". Fra i 5 della settimana vengono
prima i "probabile".

Ordine: prima il core GARP, poi i titoli in 2 o più famiglie (più famiglie
prima), poi il punteggio medio come spareggio (percentile del titolo dentro
ciascuna delle sue famiglie, in media).

Guardia di sicurezza, uguale per tutti (REPORT_punteggi_profili_2026-11-07):
chi ha prezzo sotto il 40% del massimo a 52 settimane o azioni oltre +25% in
un anno esce dalla lista e finisce in esclusi_sicurezza. Per le righe che
vengono solo dalla Qualità la diluizione è un sì/no calcolato dai bilanci
EODHD (diluizione_oltre_soglia), perché la licenza non permette di pubblicare
la variazione in numeri.

"settimana": i primi 5 titoli della lista non ancora radiografati
(schede_fatte.txt nella radice del repo, un ticker per riga), prima quelli
"probabile" su Trade Republic, poi gli altri nell'ordine della lista.

Basi dal backtest (REPORT_screener_tutti_2026-11-07): i titoli presi da 2 o
più famiglie hanno fatto +10,2 punti l'anno sull'universo (t 2,7), quelli
presi da una sola circa 0. Non riduce i perdenti: uno su quattro resta tale.
"""

import csv
import json
import math
import os
import re
import sys
import traceback
from datetime import date, datetime, timezone

FONTI = {
    "garp": os.path.join("results", "latest.json"),
    "moonshot": os.path.join("results-moonshot", "latest.json"),
    "qualita": os.path.join("results-qualita", "latest.json"),
    "svolta": os.path.join("results-svolta", "latest.json"),
    "temi": os.path.join("results-temi", "latest.json"),
}
OUT_DIR = "results-lista"
SCHEDE_FATTE = "schede_fatte.txt"
N_SETTIMANA = 5

# 08/11/2026: Radar A e Moonshot sono una sola famiglia, "Crescita"
# (REPORT_screener_tutti_2026-11-07); nuova famiglia "Qualità"
FAMIGLIE = ["GARP", "Crescita", "Qualità", "Radar B", "Svolta"]
# segnale -> famiglia: core e top 30 del GARP valgono una sola famiglia, e
# così Radar A e Moonshot (Crescita)
SEGNALI = {
    "GARP-core": "GARP",
    "GARP-top30": "GARP",
    "Radar A": "Crescita",
    "Moonshot": "Crescita",
    "Qualità": "Qualità",
    "Radar B": "Radar B",
    "Svolta": "Svolta",
}
# famiglie fino al 08/11/2026: in conteggi_famiglie restano come conteggio dei
# segnali, per non togliere chiavi dal report
FAMIGLIE_VECCHIE = ("Radar A", "Moonshot")

# Trade Republic (file creato da aggiorna_disponibilita_tr.py)
DISPONIBILITA_TR = "disponibilita_tr.csv"
TR_VALORI = ("probabile", "incerto", "probabilmente no")
TR_ND = "n.d."
TR_ASSENTE = "incerto"     # ticker non presente nel file
SEMAFORI_TEMA = ("verde", "giallo")

# guardia di sicurezza (stessi valori di garp_screener.CRITERIA; se il report
# GARP li contiene, valgono quelli del report)
SICUREZZA_DEFAULT = {"sicurezza_diluizione_max": 0.25, "sicurezza_pct_max52_min": 0.40}

# suffissi di borsa di Yahoo: "BRK.B" diventa "BRK-B", "ASML.AS" resta com'è
SUFFISSI_BORSA = {
    "L", "ST", "PA", "DE", "OL", "SW", "MI", "MC", "CO", "HK", "HE", "AS", "BR", "VI", "LS",
    "T", "TO", "V", "CN", "NE", "TW", "TWO", "KS", "KQ", "AX", "NZ", "IR", "WA", "F", "BE",
    "DU", "HM", "MU", "SG", "XC", "IL", "TA", "AT", "PR", "BD", "IS", "NS", "BO", "SS", "SZ",
    "SI", "JK", "KL", "BK", "SA", "MX", "BA", "SN", "JO", "CA", "QA", "SR", "AE", "RG", "TL",
    "VS", "IC",
}
FORME_SOCIETARIE = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc",
    "sa", "ag", "nv", "se", "spa", "asa", "ab", "as", "oyj", "abp", "publ", "the", "llc",
    "lp", "sca", "sab", "de", "cv", "kgaa", "a/s", "class", "a", "b", "c", "adr", "ord",
    "shares", "holding", "holdings",
}


# ----------------------------- utilità -----------------------------


def norm_ticker(t):
    """Ticker in forma unica: maiuscolo, senza spazi e commenti; le classi USA
    scritte col punto (BRK.B) diventano col trattino (BRK-B), come in Yahoo."""
    t = str(t or "").split("#")[0].strip().upper()
    if "." in t:
        radice, suf = t.rsplit(".", 1)
        if suf not in SUFFISSI_BORSA and len(suf) == 1 and radice:
            t = f"{radice}-{suf}"
    return t


def norm_nome(nome):
    """Nome della società senza forma societaria e punteggiatura, per unire le
    doppie quotazioni (es. GOOG e GOOGL). '' se troppo corto per fidarsi."""
    s = re.sub(r"[^a-z0-9/ ]+", " ", str(nome or "").lower())
    parole = [p for p in s.split() if p not in FORME_SOCIETARIE]
    s = " ".join(parole)
    return s if len(s) >= 4 else ""


def num(x):
    """Numero o None (scarta NaN, stringhe e booleani)."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    return None if (isinstance(x, float) and math.isnan(x)) else x


def leggi_json(path):
    """Report di uno screener, o None (con avviso) se manca, è rotto, vuoto
    ('{}') o non è un dizionario."""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[WARN] {path} non leggibile: {e}", file=sys.stderr)
        return None
    if not isinstance(d, dict) or not d:
        print(f"[WARN] {path} vuoto o senza report: ignorato", file=sys.stderr)
        return None
    return d


def pct_garp(r):
    """Prezzo/massimo dal GARP o dalla Svolta: il valore verificato sullo
    storico prezzi (`pct_max_52s_verificato`, frazionamenti) se c'è.
    Ritorna (valore, verificato sì/no)."""
    v = num(r.get("pct_max_52s_verificato"))
    if v is not None:
        return v, True
    return num(r.get("pct_max_52s", r.get("pct_of_52w_high"))), False


def leggi_schede_fatte(path=SCHEDE_FATTE):
    """Ticker già radiografati (uno per riga, # per i commenti)."""
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {norm_ticker(l) for l in f if norm_ticker(l)}


def percentili_per_posizione(tickers):
    """Percentile 0-100 dalla posizione in una lista già ordinata (primo = alto)."""
    n = len(tickers)
    return {t: round(100.0 * (1 - (i + 0.5) / n), 1) for i, t in enumerate(tickers)} if n else {}


# ----------------------------- costruzione -----------------------------


class Accumulatore:
    """Raccoglie i segnali per ticker normalizzato."""

    def __init__(self):
        self.righe = {}
        # 08/11/2026: altri ticker della stessa società (dalla Qualità) -> ticker della riga
        self.alias = {}

    def riga(self, ticker):
        t = norm_ticker(ticker)
        if not t:
            return None
        t = self.alias.get(t, t)
        if t not in self.righe:
            self.righe[t] = {
                "ticker": t, "altri_ticker": [], "nome": None, "settore": None, "paese": None,
                "valuta": None, "market_cap": None, "prezzo": None,
                "segnali": [], "famiglie": [], "n_famiglie": 0, "core": False,
                "etichette": [], "temi": [], "punteggio_garp": None, "punteggi": {},
                "punteggio_medio": None, "pct_max_52s": None, "pct_max_52s_fonte": None,
                "diluizione": None, "diluizione_fonte": None, "stime_mancate": None,
                "peg_sospetto": None, "sicurezza_ok": None, "sicurezza_motivi": [],
                "sicurezza_dati_mancanti": [],
                "gia_radiografato": False, "settimana": False, "posizione": None,
                # 08/11/2026
                "crescita_fascia": None, "alto_rischio": False,
                "acquistabile_tr": TR_ND, "isin": None, "isin_tr": None,
                # sì/no dalla Qualità (azioni oltre +25% in un anno, bilanci
                # EODHD): vale solo se manca "diluizione"
                "diluizione_oltre_soglia": None,
            }
        return self.righe[t]

    def dati(self, r, nome=None, settore=None, paese=None, valuta=None, mcap=None, prezzo=None):
        """Dati di base: vale il primo valore trovato (le fonti sono lette in
        ordine GARP, Moonshot, Svolta, Temi)."""
        for k, v in (("nome", nome), ("settore", settore), ("paese", paese), ("valuta", valuta),
                     ("market_cap", num(mcap)), ("prezzo", num(prezzo))):
            if r[k] is None and v not in (None, ""):
                r[k] = v

    def segnale(self, r, segnale, punteggio=None):
        if segnale not in r["segnali"]:
            r["segnali"].append(segnale)
        fam = SEGNALI[segnale]
        if fam not in r["famiglie"]:
            r["famiglie"].append(fam)
        # Crescita viene da due segnali (Radar A, Moonshot): vale il migliore
        if punteggio is not None:
            r["punteggi"][fam] = max(r["punteggi"].get(fam, punteggio), punteggio)
            # chiavi di prima del 08/11/2026 (Radar A, Moonshot): restano in
            # punteggi col percentile del segnale; punteggio_medio usa solo le
            # famiglie, quindi non cambia
            if segnale in FAMIGLIE_VECCHIE and segnale not in r["punteggi"]:
                r["punteggi"][segnale] = punteggio

    def sicurezza(self, r, pct=None, pct_fonte=None, dil=None, dil_fonte=None, dil_oltre=None):
        if r["pct_max_52s"] is None and num(pct) is not None:
            r["pct_max_52s"], r["pct_max_52s_fonte"] = num(pct), pct_fonte
        if r["diluizione"] is None and num(dil) is not None:
            r["diluizione"], r["diluizione_fonte"] = num(dil), dil_fonte
        if r["diluizione_oltre_soglia"] is None and isinstance(dil_oltre, bool):
            r["diluizione_oltre_soglia"] = dil_oltre


def aggiungi_garp(acc, rep):
    passed = rep.get("passed") or []
    core_set = {norm_ticker(t) for t in rep.get("core") or []}
    ordinati = sorted(passed, key=lambda r: -(num(r.get("punteggio_garp")) or 0))
    perc = percentili_per_posizione([norm_ticker(r.get("ticker")) for r in ordinati])
    for r in passed:
        t = norm_ticker(r.get("ticker"))
        is_core = bool(r.get("core")) or t in core_set
        is_top = bool(r.get("top30"))
        if not (is_core or is_top):
            continue
        row = acc.riga(t)
        if row is None:     # riga senza ticker: si salta, non blocca la lista
            continue
        acc.dati(row, r.get("name"), r.get("sector"), r.get("country"), r.get("currency"),
                 r.get("market_cap"), r.get("price"))
        if is_core:
            acc.segnale(row, "GARP-core", perc.get(t))
            row["core"] = True
        if is_top:
            acc.segnale(row, "GARP-top30", perc.get(t))
        row["punteggio_garp"] = num(r.get("punteggio_garp"))
        row["stime_mancate"] = r.get("stime_mancate")
        row["peg_sospetto"] = r.get("peg_sospetto")
        pm, ver = pct_garp(r)
        acc.sicurezza(row, pm, "GARP, verificato sullo storico" if ver else "GARP",
                      r.get("variazione_azioni_1a"), "GARP, ultimo anno")
    for chiave, segnale in (("radar_a", "Radar A"), ("radar_b", "Radar B")):
        lista = rep.get(chiave) or []
        perc = percentili_per_posizione([norm_ticker(r.get("ticker")) for r in lista])
        for r in lista:
            row = acc.riga(r.get("ticker"))
            if row is None:
                continue
            acc.dati(row, r.get("name"), r.get("sector"), r.get("country"), r.get("currency"),
                     r.get("market_cap"), r.get("price"))
            acc.segnale(row, segnale, perc.get(row["ticker"]))
            pm, ver = pct_garp(r)
            acc.sicurezza(row, pm, "GARP, verificato sullo storico" if ver else "GARP",
                          r.get("variazione_azioni_1a"), "GARP, ultimo anno")


def aggiungi_moonshot(acc, rep):
    lista = rep.get("passed") or []
    perc = percentili_per_posizione([norm_ticker(r.get("ticker")) for r in lista])
    for r in lista:
        row = acc.riga(r.get("ticker"))
        if row is None:
            continue
        acc.dati(row, r.get("name"), r.get("sector"), r.get("country"), None,
                 r.get("market_cap"), r.get("price"))
        acc.segnale(row, "Moonshot", perc.get(row["ticker"]))
        # 08/11/2026: fascia della lista Crescita; la piccola è ad alto rischio
        if row["crescita_fascia"] is None and r.get("fascia_dimensione"):
            row["crescita_fascia"] = r.get("fascia_dimensione")
        if r.get("alto_rischio"):
            row["alto_rischio"] = True
            if "crescita piccola: alto rischio" not in row["etichette"]:
                row["etichette"].append("crescita piccola: alto rischio")
        acc.sicurezza(row, r.get("pct_of_52w_high"), "Moonshot", r.get("dilution_cagr"),
                      "Moonshot, media annua pluriennale")


def aggiungi_qualita(acc, rep):
    """Famiglia Qualità (dal 08/11/2026): i promossi Q3 di qualita_screener.py,
    già ordinati per punteggio."""
    lista = [r for r in rep.get("passed") or [] if r.get("passed", True)]
    perc = percentili_per_posizione([norm_ticker(r.get("ticker")) for r in lista])
    for r in lista:
        tutti = [t for t in (norm_ticker(x) for x in [r.get("ticker"), *(r.get("altri_ticker") or [])])
                 if t]
        # se un altro screener ha già la società con un altro ticker, si usa quella riga
        esistente = next((acc.alias.get(t, t) for t in tutti if acc.alias.get(t, t) in acc.righe),
                         None)
        row = acc.riga(esistente or r.get("ticker"))
        if row is None:
            continue
        acc.dati(row, r.get("name"), r.get("sector"), r.get("country"), r.get("currency"),
                 r.get("market_cap"), r.get("price"))
        acc.segnale(row, "Qualità", perc.get(norm_ticker(r.get("ticker"))))
        for t in tutti:
            if t != row["ticker"]:
                acc.alias.setdefault(t, row["ticker"])
                if t not in row["altri_ticker"]:
                    row["altri_ticker"].append(t)
        # la Qualità non pubblica la variazione delle azioni (licenza EODHD), solo
        # il sì/no "azioni oltre +25% in un anno"
        acc.sicurezza(row, r.get("pct_of_52w_high"), "Qualità", None, None,
                      dil_oltre=r.get("azioni_oltre_25_1a"))


def aggiungi_svolta(acc, rep):
    lista = sorted(rep.get("passed") or [], key=lambda r: -(num(r.get("punteggio")) or 0))
    perc = percentili_per_posizione([norm_ticker(r.get("ticker")) for r in lista])
    for r in lista:
        row = acc.riga(r.get("ticker"))
        if row is None:
            continue
        acc.dati(row, r.get("nome"), r.get("settore"), r.get("paese"), r.get("valuta"),
                 r.get("capitalizzazione"), r.get("prezzo"))
        acc.segnale(row, "Svolta", perc.get(row["ticker"]))
        if "margine in svolta" not in row["etichette"]:
            row["etichette"].append("margine in svolta")
        pm, ver = pct_garp(r)
        acc.sicurezza(row, pm, "Svolta, verificato sullo storico" if ver else "Svolta",
                      r.get("diluizione"), "Svolta, ultimo anno")


def aggiungi_temi(acc, rep):
    """Solo etichette sui titoli già in lista: i Temi non sono una famiglia."""
    nomi = rep.get("themes") or {}
    for r in rep.get("tracked") or []:
        t = norm_ticker(r.get("ticker"))
        t = acc.alias.get(t, t)
        if t not in acc.righe or r.get("light") not in SEMAFORI_TEMA:
            continue
        row = acc.righe[t]
        for k in r.get("themes") or []:
            nome = nomi.get(k, k) if isinstance(nomi, dict) else k
            et = f"tema: {nome}"
            if et not in row["etichette"]:
                row["etichette"].append(et)
                row["temi"].append({"tema": nome, "semaforo": r.get("light")})
        acc.sicurezza(row, r.get("pct_of_52w_high"), "Temi", r.get("dilution_cagr"),
                      "Temi, media annua pluriennale")


def unisci_doppie_quotazioni(righe):
    """Unisce le righe con lo stesso nome di società (es. GOOG e GOOGL): resta
    il ticker con più segnali (a pari merito il primo letto), gli altri vanno
    in altri_ticker."""
    per_nome, out = {}, []
    for r in righe:
        k = norm_nome(r.get("nome"))
        if not k or k not in per_nome:
            if k:
                per_nome[k] = r
            out.append(r)
            continue
        a = per_nome[k]
        if len(r["segnali"]) > len(a["segnali"]):
            # la nuova riga diventa principale: scambio dei contenuti
            a_copia = dict(a)
            a.clear()
            a.update(r)
            r = a_copia
        a["altri_ticker"] = sorted(set(a["altri_ticker"]) | {r["ticker"]} | set(r["altri_ticker"]))
        for s in r["segnali"]:
            if s not in a["segnali"]:
                a["segnali"].append(s)
        for f in r["famiglie"]:
            if f not in a["famiglie"]:
                a["famiglie"].append(f)
        for fam, p in r["punteggi"].items():
            a["punteggi"][fam] = max(a["punteggi"].get(fam, p), p)
        for e in r["etichette"]:
            if e not in a["etichette"]:
                a["etichette"].append(e)
        for tm in r["temi"]:
            if tm not in a["temi"]:
                a["temi"].append(tm)
        a["core"] = a["core"] or r["core"]
        a["alto_rischio"] = a.get("alto_rischio") or r.get("alto_rischio")
        for k2 in ("crescita_fascia", "punteggio_garp", "stime_mancate", "peg_sospetto", "pct_max_52s",
                   "pct_max_52s_fonte", "diluizione", "diluizione_fonte", "nome", "settore",
                   "paese", "valuta", "market_cap", "prezzo", "diluizione_oltre_soglia"):
            if a.get(k2) is None and r.get(k2) is not None:
                a[k2] = r[k2]
    return out


# nomi dei due dati della guardia in sicurezza_dati_mancanti: gli stessi del
# GARP e della Svolta (qui la diluizione è nel campo "diluizione")
DATI_SICUREZZA_IT = {"pct_max_52s": "prezzo/massimo a 52 settimane",
                     "variazione_azioni_1a": "variazione delle azioni"}


def valuta_sicurezza(r, soglie):
    motivi = []
    # la variazione in numeri (GARP, Moonshot, Svolta, Temi) prima del sì/no
    # della Qualità, che usa sempre la soglia del 25%
    oltre = r.get("diluizione_oltre_soglia")
    if r["diluizione"] is not None:
        oltre = r["diluizione"] > soglie["sicurezza_diluizione_max"]
    if oltre:
        motivi.append("diluizione")
    if r["pct_max_52s"] is not None and r["pct_max_52s"] < soglie["sicurezza_pct_max52_min"]:
        motivi.append("lontano_dal_massimo")
    r["sicurezza_motivi"] = motivi
    # dato mancante (anche uno solo dei due): non esclude, ma lo dice
    r["sicurezza_dati_mancanti"] = [k for k, v in (("pct_max_52s", r["pct_max_52s"]),
                                                   ("variazione_azioni_1a", oltre))
                                    if v is None]
    if motivi:
        r["sicurezza_ok"] = False
    elif len(r["sicurezza_dati_mancanti"]) == 2:
        r["sicurezza_ok"] = None   # nessun dato: non verificabile
    else:
        r["sicurezza_ok"] = True


def testo_dati_mancanti(r, breve=False):
    """'manca la variazione delle azioni' e simili; '' se non manca nulla."""
    m = r.get("sicurezza_dati_mancanti") or []
    if not m:
        return ""
    if breve:
        return "⚠ non verificabile" if len(m) == 2 else (
            "⚠ manca " + ("prezzo/max" if m == ["pct_max_52s"] else "diluizione"))
    nomi = [DATI_SICUREZZA_IT.get(k, k) for k in m]
    return ("manca " if len(nomi) == 1 else "mancano ") + " e ".join(nomi)


def leggi_disponibilita_tr(path=DISPONIBILITA_TR):
    """Disponibilità su Trade Republic dal file facoltativo (colonne ticker,
    isin e acquistabile_tr, oppure flag; isin_tr se c'è). None se il file
    manca, non si legge, è vuoto o non ha righe con un ticker: allora ogni
    riga ha "n.d." e il report lo dice in avvisi."""
    if not os.path.exists(path):
        return None
    out = {}
    try:
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                t = norm_ticker(r.get("ticker"))
                flag = (r.get("acquistabile_tr") or r.get("flag") or "").strip().lower()
                if not t:
                    continue
                out[t] = {"acquistabile_tr": flag if flag in TR_VALORI else TR_ASSENTE,
                          "isin": (r.get("isin") or "").strip() or None,
                          "isin_tr": (r.get("isin_tr") or "").strip() or None}
    except Exception as e:
        print(f"[WARN] {path} non leggibile: {e}", file=sys.stderr)
        return None
    if not out:
        print(f"[WARN] {path} vuoto o senza righe valide: ignorato", file=sys.stderr)
        return None
    return out


def applica_tr(r, disp):
    """acquistabile_tr della riga: il migliore fra il ticker principale e gli
    altri ticker della stessa società (probabile > incerto > probabilmente no)."""
    if disp is None:
        r["acquistabile_tr"] = TR_ND
        return
    voci = [disp[t] for t in [r["ticker"], *r["altri_ticker"]] if t in disp]
    if not voci:
        r["acquistabile_tr"] = TR_ASSENTE
        return
    best = min(voci, key=lambda v: TR_VALORI.index(v["acquistabile_tr"]))
    r["acquistabile_tr"] = best["acquistabile_tr"]
    r["isin"] = (disp.get(r["ticker"]) or best)["isin"]
    r["isin_tr"] = best["isin_tr"]


def chiave_ordine(r):
    """1) core GARP; 2) 2 o più famiglie (più famiglie prima); 3) punteggio medio."""
    return (not r["core"], r["n_famiglie"] < 2, -r["n_famiglie"],
            -(r["punteggio_medio"] if r["punteggio_medio"] is not None else -1),
            r["ticker"])


def costruisci_lista(reports, schede_fatte=frozenset(), n_settimana=N_SETTIMANA, disp_tr=None):
    """Funzione pura: dai report degli screener (dizionari, o None se mancanti)
    alla lista unificata. disp_tr = disponibilità su Trade Republic
    (leggi_disponibilita_tr) o None. Ritorna (lista, esclusi_sicurezza, settimana)."""
    acc = Accumulatore()
    if reports.get("garp"):
        aggiungi_garp(acc, reports["garp"])
    if reports.get("moonshot"):
        aggiungi_moonshot(acc, reports["moonshot"])
    if reports.get("qualita"):
        aggiungi_qualita(acc, reports["qualita"])
    if reports.get("svolta"):
        aggiungi_svolta(acc, reports["svolta"])
    if reports.get("temi"):
        aggiungi_temi(acc, reports["temi"])

    soglie = dict(SICUREZZA_DEFAULT)
    crit = (reports.get("garp") or {}).get("criteria") or {}
    for k in soglie:
        if num(crit.get(k)) is not None:
            soglie[k] = crit[k]

    righe = unisci_doppie_quotazioni(list(acc.righe.values()))
    fatte = {norm_ticker(t) for t in schede_fatte}
    lista, esclusi = [], []
    for r in righe:
        r["famiglie"] = [f for f in FAMIGLIE if f in r["famiglie"]]
        r["segnali"] = [s for s in SEGNALI if s in r["segnali"]]
        r["n_famiglie"] = len(r["famiglie"])
        vals = [r["punteggi"][f] for f in r["famiglie"] if r["punteggi"].get(f) is not None]
        r["punteggio_medio"] = round(sum(vals) / len(vals), 1) if vals else None
        r["gia_radiografato"] = bool({r["ticker"], *r["altri_ticker"]} & fatte)
        applica_tr(r, disp_tr)
        valuta_sicurezza(r, soglie)
        (esclusi if r["sicurezza_ok"] is False else lista).append(r)

    lista.sort(key=chiave_ordine)
    esclusi.sort(key=chiave_ordine)
    for i, r in enumerate(lista, 1):
        r["posizione"] = i
    # 08/11/2026: prima i "probabile" su Trade Republic, poi gli altri
    liberi = [r for r in lista if not r["gia_radiografato"]]
    scelti = ([r for r in liberi if r["acquistabile_tr"] == "probabile"]
              + [r for r in liberi if r["acquistabile_tr"] != "probabile"])[:n_settimana]
    settimana = []
    for r in scelti:
        r["settimana"] = True
        settimana.append(r["ticker"])
    return lista, esclusi, settimana


# ----------------------------- report -----------------------------


def _pct(x):
    return f"{x * 100:.0f}%" if isinstance(x, (int, float)) else "n/d"


def _mld(x, valuta=None):
    if not isinstance(x, (int, float)):
        return "n/d"
    v = {"GBp": "GBP", "ILA": "ILS", "ZAc": "ZAR"}.get(valuta, valuta)
    return f"{x / 1e9:.1f}" + (f" {v}" if v else "")


def scrivi_report(lista, esclusi, settimana, reports, fatte, out_dir=OUT_DIR, oggi=None,
                  disp_tr=None, path_tr=DISPONIBILITA_TR):
    oggi = oggi or date.today().isoformat()
    fonti, avvisi = {}, []
    date_fonti = set()
    for k, path in FONTI.items():
        rep = reports.get(k)
        d = (rep or {}).get("date")
        fonti[k] = {"file": path, "letto": rep is not None, "date": d}
        if rep is None:
            avvisi.append(f"{k}: file {path} assente o non leggibile, famiglia ignorata")
        elif d:
            date_fonti.add(d)
    if len(date_fonti) > 1:
        avvisi.append("le fonti hanno date diverse: " + ", ".join(
            f"{k} {v['date']}" for k, v in fonti.items() if v["date"]))
    conteggi = {f: sum(1 for r in lista if f in r["famiglie"]) for f in FAMIGLIE}
    conteggi_segnali = {s: sum(1 for r in lista if s in r["segnali"]) for s in SEGNALI}
    # chiavi delle famiglie di prima (Radar A, Moonshot): conteggio per segnale
    conteggi_famiglie = dict(conteggi, **{f: conteggi_segnali[f] for f in FAMIGLIE_VECCHIE})
    conteggi_tr = {v: sum(1 for r in lista if r.get("acquistabile_tr") == v)
                   for v in (*TR_VALORI, TR_ND)}
    if disp_tr is None:
        avvisi.append(f"{path_tr} assente, vuoto o non leggibile: acquistabile_tr = \"{TR_ND}\"")
    garp = reports.get("garp") or {}

    report = {
        "screener": "lista_radiografare",
        "date": oggi,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fonti": fonti,
        "avvisi": avvisi,
        "famiglie": FAMIGLIE,
        "regola_famiglie": "GARP-core e GARP-top30 contano come una sola famiglia (GARP). "
                           "Dal 08/11/2026 Radar A e Moonshot contano come una sola famiglia "
                           "(Crescita) e c'è la famiglia Qualità. I Temi (semaforo verde o "
                           "giallo) danno solo l'etichetta 'tema: <nome>': non testati, nessun "
                           "vantaggio dimostrato.",
        "regola_ordine": "1) core GARP; 2) 2 o più famiglie, più famiglie prima; "
                         "3) punteggio_medio (media dei percentili dentro ogni famiglia).",
        "regola_sicurezza": "Esce dalla lista chi ha prezzo sotto il 40% del massimo a 52 "
                            "settimane o azioni oltre +25% in un anno (Moonshot e Temi: media "
                            "annua pluriennale; Qualità: solo sì/no in "
                            "diluizione_oltre_soglia, usato se manca il numero). Per GARP e "
                            "Svolta, sotto soglia, il massimo è "
                            "verificato sullo storico prezzi (frazionamenti). Dato mancante: "
                            "resta, con l'elenco in sicurezza_dati_mancanti (sicurezza_ok null "
                            "se mancano entrambi).",
        "regola_settimana": f"I primi {N_SETTIMANA} della lista non ancora radiografati "
                            f"({SCHEDE_FATTE}): prima quelli \"probabile\" su Trade Republic, "
                            "poi gli altri nell'ordine della lista.",
        "regola_tr": f"acquistabile_tr da {path_tr} (aggiorna_disponibilita_tr.py): "
                     "\"probabile\", \"incerto\", \"probabilmente no\"; per una società "
                     "con più ticker vale il migliore. Ticker assente dal file = \"incerto\"; "
                     f"file assente, vuoto o non leggibile = \"{TR_ND}\". È una deduzione "
                     "dalle quotazioni tedesche: "
                     "va controllata nell'app.",
        "disponibilita_tr": {"file": path_tr, "letto": disp_tr is not None,
                             "righe": len(disp_tr) if disp_tr is not None else 0},
        "conteggi_tr": conteggi_tr,
        "conteggi_segnali": conteggi_segnali,
        "n_righe": len(lista),
        "n_2_famiglie": sum(1 for r in lista if r["n_famiglie"] >= 2),
        "n_core": sum(1 for r in lista if r["core"]),
        "conteggi_famiglie": conteggi_famiglie,
        "schede_fatte_count": len(fatte),
        "settimana": settimana,
        "lista": lista,
        "esclusi_sicurezza_count": len(esclusi),
        "esclusi_sicurezza": esclusi,
        "garp_esclusi_sicurezza": [r.get("ticker") for r in garp.get("esclusi_sicurezza") or []],
    }
    os.makedirs(out_dir, exist_ok=True)
    for p in (os.path.join(out_dir, f"{oggi}.json"), os.path.join(out_dir, "latest.json")):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1, ensure_ascii=False, default=str)

    def riga_breve(r):
        et = "; ".join(r["etichette"])
        return (f"**{r['ticker']}** — {(r.get('nome') or '')[:40]} · {', '.join(r['segnali'])}"
                + f" · Trade Republic: {r.get('acquistabile_tr', TR_ND)}"
                + (f" (ISIN da cercare: {r['isin_tr']})" if r.get("isin_tr") else "")
                + (f" · {et}" if et else "")
                + (f" · punteggio GARP {r['punteggio_garp']}" if r["punteggio_garp"] is not None else "")
                + (f" · ⚠ sicurezza non verificabile: {testo_dati_mancanti(r)}"
                   if r.get("sicurezza_dati_mancanti") else ""))

    L = [f"# Lista da radiografare — {oggi}", "",
         "> **Elenco di aziende da analizzare a mano (Radiografia), non da comprare.** "
         "Una riga per società, dai segnali di GARP (core o top 30), Crescita (Radar A e "
         "Moonshot, una sola famiglia), Qualità, Radar B e Svolta. Nel passato i titoli presi "
         "da 2 o più famiglie di screener hanno reso di più (circa +10 punti l'anno "
         "sull'universo, 2012-26), ma i perdenti restano circa uno su quattro.", ""]
    for a in avvisi:
        L += [f"> ⚠️ {a}", ""]
    L += [f"Titoli in lista: **{len(lista)}** | Core GARP: {report['n_core']} | "
          f"In 2+ famiglie: {report['n_2_famiglie']} | Esclusi per sicurezza: {len(esclusi)} | "
          f"Già radiografati (in {SCHEDE_FATTE}): {len(fatte)}",
          "Per famiglia: " + ", ".join(f"{k} {v}" for k, v in conteggi.items()),
          "Trade Republic: " + ", ".join(f"{k} {v}" for k, v in conteggi_tr.items() if v), "",
          f"## Questa settimana ({len(settimana)})", ""]
    per_t = {r["ticker"]: r for r in lista}
    L += [f"{i}. {riga_breve(per_t[t])}" for i, t in enumerate(settimana, 1)] or ["- nessuno"]
    L += ["", "## Lista completa", "",
          "| # | Ticker | Nome | Segnali | Fam. | Etichette | Punt. GARP | Punt. medio | % max 52s | Cap. (Mld) | Sicurezza | TR | Fatto |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in lista:
        L.append("| {p} | {t} | {n} | {s} | {nf} | {e} | {pg} | {pm} | {pc} | {mc} | {sic} | {tr} | {f} |".format(
            p=r["posizione"], t=r["ticker"] + (" ⭐" if r["settimana"] else ""),
            n=(r.get("nome") or "")[:30], s=", ".join(r["segnali"]), nf=r["n_famiglie"],
            e="; ".join(r["etichette"]) or "—",
            pg=r["punteggio_garp"] if r["punteggio_garp"] is not None else "—",
            pm=r["punteggio_medio"] if r["punteggio_medio"] is not None else "—",
            pc=_pct(r["pct_max_52s"]), mc=_mld(r["market_cap"], r.get("valuta")),
            sic=testo_dati_mancanti(r, breve=True) or "ok",
            tr=r.get("acquistabile_tr", TR_ND),
            f="✓" if r["gia_radiografato"] else ""))
    L += ["", f"## Esclusi per sicurezza ({len(esclusi)})", ""]
    for r in esclusi:
        motivi = []
        if "lontano_dal_massimo" in r["sicurezza_motivi"]:
            motivi.append(f"prezzo al {_pct(r['pct_max_52s'])} del massimo a 52 settimane")
        if "diluizione" in r["sicurezza_motivi"] and r["diluizione"] is None:
            motivi.append("azioni oltre +25% in un anno (Qualità, bilanci EODHD)")
        elif "diluizione" in r["sicurezza_motivi"]:
            motivi.append(f"azioni +{_pct(r['diluizione'])} l'anno ({r['diluizione_fonte']})")
        L.append(f"- {r['ticker']} ({(r.get('nome') or '')[:30]}; {', '.join(r['segnali'])}): "
                 + "; ".join(motivi))
    if not esclusi:
        L.append("- nessuno")
    if report["garp_esclusi_sicurezza"]:
        L += ["", "Esclusi già dal GARP (vedi results/latest.md): "
              + ", ".join(report["garp_esclusi_sicurezza"])]
    L += ["", "Regole: core e top 30 del GARP valgono una sola famiglia, e così Radar A e Moonshot "
          "(Crescita); ordine = core GARP, poi "
          "2+ famiglie (più famiglie prima), poi punteggio medio (media dei percentili del titolo "
          "dentro ciascuna famiglia). Etichette: \"margine in svolta\" (Svolta), \"crescita "
          "piccola: alto rischio\" (Crescita sotto 2 Mld$), \"tema: …\" "
          "(Temi con semaforo verde o giallo: non testati, nessun vantaggio dimostrato, solo "
          "etichetta). ⭐ = nei 5 della settimana (prima i \"probabile\" su Trade Republic). "
          "Colonna TR: acquistabile su Trade Republic secondo "
          f"{path_tr} (deduzione, da controllare nell'app). Le società quotate su più "
          "borse con lo stesso nome sono unite in una riga (altri ticker nel JSON). Colonna "
          "Sicurezza: \"ok\" = guardia superata; \"⚠ manca …\" o \"⚠ non verificabile\" = "
          "manca un dato della guardia (o tutti e due), il titolo resta in lista ma va "
          "controllato a mano."]
    with open(os.path.join(out_dir, "latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return report


def main():
    reports = {k: leggi_json(p) for k, p in FONTI.items()}
    if not any(reports.values()):
        print("ERRORE: nessun report degli screener trovato", file=sys.stderr)
        sys.exit(1)
    fatte = leggi_schede_fatte()
    disp_tr = leggi_disponibilita_tr()
    lista, esclusi, settimana = costruisci_lista(reports, fatte, disp_tr=disp_tr)
    scrivi_report(lista, esclusi, settimana, reports, fatte, disp_tr=disp_tr)
    print(f"Lista da radiografare: {len(lista)} titoli, {len(esclusi)} esclusi per sicurezza; "
          f"settimana: {', '.join(settimana) or '—'}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
