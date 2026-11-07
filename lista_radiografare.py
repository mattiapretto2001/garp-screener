#!/usr/bin/env python3
"""
Lista unificata "da radiografare" (dal 08/11/2026)
==================================================
Gira nel job di merge DOPO tutti gli screener. Legge:
  - results/latest.json           (GARP: core, top 30, radar A, radar B)
  - results-moonshot/latest.json  (Moonshot)
  - results-svolta/latest.json    (Svolta)
  - results-temi/latest.json      (Temi: solo etichetta)
e scrive results-lista/latest.json, latest.md e <data>.json.

Una riga per società (ticker normalizzati; le doppie quotazioni con lo stesso
nome sono unite). Famiglie: GARP (core o top 30 contano come UNA famiglia),
Radar A, Radar B, Moonshot, Svolta. I Temi danno solo un'etichetta.

Ordine: prima il core GARP, poi i titoli in 2 o più famiglie (più famiglie
prima), poi il punteggio medio come spareggio (percentile del titolo dentro
ciascuna delle sue famiglie, in media).

Guardia di sicurezza, uguale per tutti (REPORT_punteggi_profili_2026-11-07):
chi ha prezzo sotto il 40% del massimo a 52 settimane o azioni oltre +25% in
un anno esce dalla lista e finisce in esclusi_sicurezza.

"settimana": i primi 5 titoli della lista non ancora radiografati
(schede_fatte.txt nella radice del repo, un ticker per riga).

Basi dal backtest (REPORT_screener_tutti_2026-11-07): i titoli presi da 2 o
più famiglie hanno fatto +10,2 punti l'anno sull'universo (t 2,7), quelli
presi da una sola circa 0. Non riduce i perdenti: uno su quattro resta tale.
"""

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
    "svolta": os.path.join("results-svolta", "latest.json"),
    "temi": os.path.join("results-temi", "latest.json"),
}
OUT_DIR = "results-lista"
SCHEDE_FATTE = "schede_fatte.txt"
N_SETTIMANA = 5

FAMIGLIE = ["GARP", "Radar A", "Radar B", "Moonshot", "Svolta"]
# segnale -> famiglia: core e top 30 del GARP valgono una sola famiglia
SEGNALI = {
    "GARP-core": "GARP",
    "GARP-top30": "GARP",
    "Radar A": "Radar A",
    "Radar B": "Radar B",
    "Moonshot": "Moonshot",
    "Svolta": "Svolta",
}
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
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[WARN] {path} non leggibile: {e}", file=sys.stderr)
        return None


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

    def riga(self, ticker):
        t = norm_ticker(ticker)
        if not t:
            return None
        if t not in self.righe:
            self.righe[t] = {
                "ticker": t, "altri_ticker": [], "nome": None, "settore": None, "paese": None,
                "valuta": None, "market_cap": None, "prezzo": None,
                "segnali": [], "famiglie": [], "n_famiglie": 0, "core": False,
                "etichette": [], "temi": [], "punteggio_garp": None, "punteggi": {},
                "punteggio_medio": None, "pct_max_52s": None, "pct_max_52s_fonte": None,
                "diluizione": None, "diluizione_fonte": None, "stime_mancate": None,
                "peg_sospetto": None, "sicurezza_ok": None, "sicurezza_motivi": [],
                "gia_radiografato": False, "settimana": False, "posizione": None,
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
        if punteggio is not None and fam not in r["punteggi"]:
            r["punteggi"][fam] = punteggio

    def sicurezza(self, r, pct=None, pct_fonte=None, dil=None, dil_fonte=None):
        if r["pct_max_52s"] is None and num(pct) is not None:
            r["pct_max_52s"], r["pct_max_52s_fonte"] = num(pct), pct_fonte
        if r["diluizione"] is None and num(dil) is not None:
            r["diluizione"], r["diluizione_fonte"] = num(dil), dil_fonte


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
        acc.sicurezza(row, r.get("pct_max_52s"), "GARP", r.get("variazione_azioni_1a"),
                      "GARP, ultimo anno")
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
            acc.sicurezza(row, r.get("pct_max_52s"), "GARP", r.get("variazione_azioni_1a"),
                          "GARP, ultimo anno")


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
        acc.sicurezza(row, r.get("pct_of_52w_high"), "Moonshot", r.get("dilution_cagr"),
                      "Moonshot, media annua pluriennale")


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
        acc.sicurezza(row, r.get("pct_of_52w_high"), "Svolta", r.get("diluizione"),
                      "Svolta, ultimo anno")


def aggiungi_temi(acc, rep):
    """Solo etichette sui titoli già in lista: i Temi non sono una famiglia."""
    nomi = rep.get("themes") or {}
    for r in rep.get("tracked") or []:
        t = norm_ticker(r.get("ticker"))
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
        for k2 in ("punteggio_garp", "stime_mancate", "peg_sospetto", "pct_max_52s",
                   "pct_max_52s_fonte", "diluizione", "diluizione_fonte", "nome", "settore",
                   "paese", "valuta", "market_cap", "prezzo"):
            if a.get(k2) is None and r.get(k2) is not None:
                a[k2] = r[k2]
    return out


def valuta_sicurezza(r, soglie):
    motivi = []
    if r["diluizione"] is not None and r["diluizione"] > soglie["sicurezza_diluizione_max"]:
        motivi.append("diluizione")
    if r["pct_max_52s"] is not None and r["pct_max_52s"] < soglie["sicurezza_pct_max52_min"]:
        motivi.append("lontano_dal_massimo")
    r["sicurezza_motivi"] = motivi
    if motivi:
        r["sicurezza_ok"] = False
    elif r["diluizione"] is None and r["pct_max_52s"] is None:
        r["sicurezza_ok"] = None   # nessun dato: non esclude, ma lo dice
    else:
        r["sicurezza_ok"] = True


def chiave_ordine(r):
    """1) core GARP; 2) 2 o più famiglie (più famiglie prima); 3) punteggio medio."""
    return (not r["core"], r["n_famiglie"] < 2, -r["n_famiglie"],
            -(r["punteggio_medio"] if r["punteggio_medio"] is not None else -1),
            r["ticker"])


def costruisci_lista(reports, schede_fatte=frozenset(), n_settimana=N_SETTIMANA):
    """Funzione pura: dai report degli screener (dizionari, o None se mancanti)
    alla lista unificata. Ritorna (lista, esclusi_sicurezza, settimana)."""
    acc = Accumulatore()
    if reports.get("garp"):
        aggiungi_garp(acc, reports["garp"])
    if reports.get("moonshot"):
        aggiungi_moonshot(acc, reports["moonshot"])
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
        valuta_sicurezza(r, soglie)
        (esclusi if r["sicurezza_ok"] is False else lista).append(r)

    lista.sort(key=chiave_ordine)
    esclusi.sort(key=chiave_ordine)
    settimana = []
    for i, r in enumerate(lista, 1):
        r["posizione"] = i
        if len(settimana) < n_settimana and not r["gia_radiografato"]:
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


def scrivi_report(lista, esclusi, settimana, reports, fatte, out_dir=OUT_DIR, oggi=None):
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
    garp = reports.get("garp") or {}

    report = {
        "screener": "lista_radiografare",
        "date": oggi,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fonti": fonti,
        "avvisi": avvisi,
        "famiglie": FAMIGLIE,
        "regola_famiglie": "GARP-core e GARP-top30 contano come una sola famiglia (GARP). "
                           "I Temi (semaforo verde o giallo) danno solo l'etichetta 'tema: <nome>'.",
        "regola_ordine": "1) core GARP; 2) 2 o più famiglie, più famiglie prima; "
                         "3) punteggio_medio (media dei percentili dentro ogni famiglia).",
        "regola_sicurezza": "Esce dalla lista chi ha prezzo sotto il 40% del massimo a 52 "
                            "settimane o azioni oltre +25% in un anno (Moonshot e Temi: media "
                            "annua pluriennale). Dato mancante: resta, con sicurezza_ok null.",
        "regola_settimana": f"I primi {N_SETTIMANA} della lista non ancora radiografati "
                            f"({SCHEDE_FATTE}).",
        "n_righe": len(lista),
        "n_2_famiglie": sum(1 for r in lista if r["n_famiglie"] >= 2),
        "n_core": sum(1 for r in lista if r["core"]),
        "conteggi_famiglie": conteggi,
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
                + (f" · {et}" if et else "")
                + (f" · punteggio GARP {r['punteggio_garp']}" if r["punteggio_garp"] is not None else "")
                + (" · ⚠ sicurezza non verificabile (dati mancanti)" if r["sicurezza_ok"] is None else ""))

    L = [f"# Lista da radiografare — {oggi}", "",
         "> **Elenco di aziende da analizzare a mano (Radiografia), non da comprare.** "
         "Una riga per società, dai segnali di GARP (core o top 30), Radar A, Radar B, "
         "Moonshot e Svolta. Nel passato i titoli presi da 2 o più famiglie di screener "
         "hanno reso di più (circa +10 punti l'anno sull'universo, 2012-26), ma i perdenti "
         "restano circa uno su quattro.", ""]
    for a in avvisi:
        L += [f"> ⚠️ {a}", ""]
    L += [f"Titoli in lista: **{len(lista)}** | Core GARP: {report['n_core']} | "
          f"In 2+ famiglie: {report['n_2_famiglie']} | Esclusi per sicurezza: {len(esclusi)} | "
          f"Già radiografati (in {SCHEDE_FATTE}): {len(fatte)}",
          "Per famiglia: " + ", ".join(f"{k} {v}" for k, v in conteggi.items()), "",
          f"## Questa settimana ({len(settimana)})", ""]
    per_t = {r["ticker"]: r for r in lista}
    L += [f"{i}. {riga_breve(per_t[t])}" for i, t in enumerate(settimana, 1)] or ["- nessuno"]
    L += ["", "## Lista completa", "",
          "| # | Ticker | Nome | Segnali | Fam. | Etichette | Punt. GARP | Punt. medio | % max 52s | Cap. (Mld) | Fatto |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in lista:
        L.append("| {p} | {t} | {n} | {s} | {nf} | {e} | {pg} | {pm} | {pc} | {mc} | {f} |".format(
            p=r["posizione"], t=r["ticker"] + (" ⭐" if r["settimana"] else ""),
            n=(r.get("nome") or "")[:30], s=", ".join(r["segnali"]), nf=r["n_famiglie"],
            e="; ".join(r["etichette"]) or "—",
            pg=r["punteggio_garp"] if r["punteggio_garp"] is not None else "—",
            pm=r["punteggio_medio"] if r["punteggio_medio"] is not None else "—",
            pc=_pct(r["pct_max_52s"]), mc=_mld(r["market_cap"], r.get("valuta")),
            f="✓" if r["gia_radiografato"] else ""))
    L += ["", f"## Esclusi per sicurezza ({len(esclusi)})", ""]
    for r in esclusi:
        motivi = []
        if "lontano_dal_massimo" in r["sicurezza_motivi"]:
            motivi.append(f"prezzo al {_pct(r['pct_max_52s'])} del massimo a 52 settimane")
        if "diluizione" in r["sicurezza_motivi"]:
            motivi.append(f"azioni +{_pct(r['diluizione'])} l'anno ({r['diluizione_fonte']})")
        L.append(f"- {r['ticker']} ({(r.get('nome') or '')[:30]}; {', '.join(r['segnali'])}): "
                 + "; ".join(motivi))
    if not esclusi:
        L.append("- nessuno")
    if report["garp_esclusi_sicurezza"]:
        L += ["", "Esclusi già dal GARP (vedi results/latest.md): "
              + ", ".join(report["garp_esclusi_sicurezza"])]
    L += ["", "Regole: core e top 30 del GARP valgono una sola famiglia; ordine = core GARP, poi "
          "2+ famiglie (più famiglie prima), poi punteggio medio (media dei percentili del titolo "
          "dentro ciascuna famiglia). Etichette: \"margine in svolta\" (Svolta), \"tema: …\" "
          "(Temi con semaforo verde o giallo). ⭐ = nei 5 della settimana. Le società quotate su più "
          "borse con lo stesso nome sono unite in una riga (altri ticker nel JSON)."]
    with open(os.path.join(out_dir, "latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return report


def main():
    reports = {k: leggi_json(p) for k, p in FONTI.items()}
    if not any(reports.values()):
        print("ERRORE: nessun report degli screener trovato", file=sys.stderr)
        sys.exit(1)
    fatte = leggi_schede_fatte()
    lista, esclusi, settimana = costruisci_lista(reports, fatte)
    scrivi_report(lista, esclusi, settimana, reports, fatte)
    print(f"Lista da radiografare: {len(lista)} titoli, {len(esclusi)} esclusi per sicurezza; "
          f"settimana: {', '.join(settimana) or '—'}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
