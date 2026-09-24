#!/usr/bin/env python3
"""
Screener Temi strutturali — i titoli che GARP e Moonshot non vedono
=====================================================================
GARP e Moonshot escludono per costruzione Utilities/Energy/Basic Materials/
Financials/Real Estate, le società in perdita o pre-ricavi e le large cap con
PEG > 1. Così restano fuori proprio i temi che vogliamo seguire: nucleare e
uranio, rete elettrica e generazione per l'AI, fotonica, batterie e stoccaggio.

Non è un filtro "passa/non passa" sull'universo: è un MONITOR su una lista di
temi. Due fonti di ticker:
  1. lista curata in THEMES (i nomi rilevanti, anche europei/asiatici);
  2. scoperta automatica: nei job paralleli, dalla cache .info del GARP, i
     titoli dell'universo con industry tematica e mcap >= DISCOVERY_MCAP_MIN.

Ogni titolo riceve un PROFILO, perché un'utility e un reattore pre-ricavi non
si misurano con lo stesso metro:
  - "pre-ricavi"  ricavi TTM < 50 M (valuta di bilancio): conta sopravvivere
  - "crescita"    ricavi +15% o più: metrica tipo Moonshot
  - "stabile"     il resto (utility, large cap industriali): utili, debito, dividendo

e un SEMAFORO:
  - verde:  supera i filtri di sopravvivenza del suo profilo E ha momentum
            (prezzo sopra la media 200gg e >= 75% del massimo 52 settimane)
  - giallo: sopravvive ma senza momentum, o con campanelli non gravi
  - rosso:  rischio di sopravvivenza (in perdita con runway < 2 anni,
            diluizione > 30%/anno, debito netto/EBITDA > 6x, 8x per le utility)

Il punteggio 0-8 ordina i titoli dentro ogni tema. Output:
results-temi/YYYY-MM-DD.json, latest.json, latest.md
La lettura qualitativa (catalizzatori, licenze, contratti) la fa Claude.
"""

import json
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import yfinance as yf

import garp_screener as base

RESULTS_DIR = "results-temi"
MAX_WORKERS = 4
DISCOVERY_MCAP_MIN = 1e9
DISCOVERY_MAX = 40            # tetto ai titoli scoperti (i più grandi), per i tempi del job

CRITERIA = {
    "pre_revenue_max": 50e6,          # sotto: profilo pre-ricavi
    "growth_profile_min": 0.15,       # sopra: profilo crescita
    "runway_years_min": 2.0,          # sotto: rosso (se brucia cassa)
    "runway_years_ok": 3.0,           # pre-ricavi: serve almeno questo per il verde
    "dilution_red": 0.30,             # diluizione annua oltre cui è rosso
    "dilution_warn": 0.15,
    "net_debt_ebitda_red": 6.0,
    "net_debt_ebitda_warn": 4.0,
    "utility_leverage_bump": 2.0,     # utility: soglie di leva +2x
    "pct_of_52w_high_momentum": 0.75,
}

# Temi seguiti. "industries" = stringhe industry di Yahoo usate per la
# scoperta automatica; "tickers" = lista curata (simboli Yahoo).
THEMES = {
    "nucleare": {
        "label": "Nucleare, SMR e uranio",
        "industries": ["Uranium"],
        "tickers": ["CCJ", "NXE", "UEC", "DNN", "LEU", "KAP.L", "OKLO", "SMR",
                    "NNE", "BWXT", "CEG", "VST", "TLN", "RR.L", "XE", "GFUZ"],
    },
    "rete": {
        "label": "Rete elettrica e generazione per l'AI",
        "industries": ["Utilities - Independent Power Producers",
                       "Utilities - Renewable",
                       "Electrical Equipment & Parts", "Copper"],
        "tickers": ["GEV", "ETN", "HUBB", "PWR", "PRY.MI", "NEX.PA", "6501.T",
                    "SU.PA", "ABBN.SW", "ENR.DE", "NEE", "AEP", "FCX",
                    "VRT", "AMSC", "PLPC", "NVT", "EME"],
    },
    "fotonica": {
        "label": "Fotonica e chip ottici (CPO)",
        "industries": [],
        "tickers": ["LITE", "COHR", "AAOI", "FN", "POET", "LWLG", "MRVL",
                    "ALAB", "CRDO"],
    },
    "batterie": {
        "label": "Batterie oltre il litio e stoccaggio",
        "industries": [],
        "tickers": ["QS", "SLDP", "EOSE", "FLNC", "ALB", "MP", "3750.HK",
                    "300750.SZ"],
    },
}


def _dilution_cagr(tk):
    try:
        bs = tk.balance_sheet
        for name in ("Ordinary Shares Number", "Share Issued"):
            if bs is not None and not bs.empty and name in bs.index:
                row = bs.loc[name].dropna().sort_index()
                break
        else:
            return None
        if len(row) < 2 or float(row.iloc[0]) <= 0:
            return None
        years = (row.index[-1] - row.index[0]).days / 365.25
        if years < 0.9:
            return None
        return (float(row.iloc[-1]) / float(row.iloc[0])) ** (1 / years) - 1
    except Exception:
        return None


def evaluate(symbol, themes):
    try:
        tk = yf.Ticker(symbol)
        info = tk.info or {}
        if info.get("marketCap") is None and info.get("regularMarketPrice") is None:
            return {"ticker": symbol, "themes": themes, "error": "nessun dato"}

        mcap = info.get("marketCap")
        rev = info.get("totalRevenue")
        rev_g = info.get("revenueGrowth")
        eps_g = info.get("earningsGrowth")
        gm = info.get("grossMargins")
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        high52 = info.get("fiftyTwoWeekHigh")
        ma200 = info.get("twoHundredDayAverage")
        fcf = info.get("freeCashflow")
        cash = info.get("totalCash")
        debt = info.get("totalDebt")
        ebitda = info.get("ebitda")

        pct_high = price / high52 if price and high52 else None
        above_ma200 = bool(price and ma200 and price > ma200)
        momentum = above_ma200 and pct_high is not None and \
            pct_high >= CRITERIA["pct_of_52w_high_momentum"]
        # runway solo per chi è in perdita operativa: le utility e gli industriali
        # redditizi con FCF negativo per capex si misurano col debito/EBITDA
        loss_making = ebitda is None or ebitda <= 0
        runway = cash / abs(fcf) if (loss_making and fcf is not None and fcf < 0 and cash) else None
        net_debt = (debt or 0) - (cash or 0)
        nd_ebitda = net_debt / ebitda if ebitda and ebitda > 0 else None
        dil = _dilution_cagr(tk)

        if rev is not None and rev < CRITERIA["pre_revenue_max"]:
            profile = "pre-ricavi"
        elif rev_g is not None and rev_g >= CRITERIA["growth_profile_min"]:
            profile = "crescita"
        else:
            profile = "stabile"

        red, warn = [], []
        if runway is not None and runway < CRITERIA["runway_years_min"]:
            red.append(f"runway {runway:.1f} anni")
        elif runway is not None and profile == "pre-ricavi" and runway < CRITERIA["runway_years_ok"]:
            warn.append(f"runway {runway:.1f} anni")
        # diluizione pesante tollerata (solo campanello) se la cassa copre 5+ anni
        if dil is not None and dil > CRITERIA["dilution_red"] and not (runway and runway >= 5):
            red.append(f"diluizione {dil*100:.0f}%/anno")
        elif dil is not None and dil > CRITERIA["dilution_warn"]:
            warn.append(f"diluizione {dil*100:.0f}%/anno")
        # le utility reggono strutturalmente più leva
        lev_bump = CRITERIA["utility_leverage_bump"] if info.get("sector") == "Utilities" else 0
        if nd_ebitda is not None and nd_ebitda > CRITERIA["net_debt_ebitda_red"] + lev_bump:
            red.append(f"debito netto/EBITDA {nd_ebitda:.1f}x")
        elif nd_ebitda is not None and nd_ebitda > CRITERIA["net_debt_ebitda_warn"] + lev_bump:
            warn.append(f"debito netto/EBITDA {nd_ebitda:.1f}x")
        if loss_making and fcf is not None and fcf < 0 and not cash:
            red.append("brucia cassa senza cassa nota")
        if profile != "pre-ricavi" and rev_g is not None and rev_g < 0:
            warn.append(f"ricavi {rev_g*100:.0f}%")
        if profile == "stabile" and eps_g is not None and eps_g < 0:
            warn.append(f"utili {eps_g*100:.0f}%")

        if red:
            light = "rosso"
        elif momentum and not warn:
            light = "verde"
        else:
            light = "giallo"

        score = 0
        score += 1 if above_ma200 else 0
        score += 1 if pct_high is not None and pct_high >= 0.90 else 0
        score += 1 if rev_g is not None and rev_g >= 0.20 else 0
        score += 1 if eps_g is not None and eps_g >= 0.15 else 0
        score += 1 if fcf is not None and fcf > 0 else 0
        score += 1 if cash is not None and cash > (debt or 0) else 0
        score += 1 if dil is not None and dil < 0.03 else 0
        score += 1 if gm is not None and gm >= 0.40 else 0

        return {
            "ticker": symbol,
            "name": info.get("longName") or info.get("shortName"),
            "themes": themes,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "currency": info.get("currency"),
            "market_cap": mcap,
            "price": price,
            "pct_of_52w_high": pct_high,
            "above_ma200": above_ma200,
            "revenue_ttm": rev,
            "revenue_growth_qoq_yoy": rev_g,
            "earnings_growth": eps_g,
            "gross_margin": gm,
            "free_cash_flow": fcf,
            "total_cash": cash,
            "total_debt": debt,
            "net_debt_to_ebitda": nd_ebitda,
            "runway_years": runway,
            "dilution_cagr": dil,
            "forward_pe": info.get("forwardPE"),
            "dividend_yield": info.get("dividendYield"),
            "profile": profile,
            "light": light,
            "flags": red + warn,
            "score": score,
        }
    except Exception as e:
        return {"ticker": symbol, "themes": themes, "error": str(e)}


def discover_from_cache():
    """Titoli dell'universo con industry tematica, dalla cache .info del GARP."""
    try:
        with open(base.INFO_CACHE_PATH) as f:
            cache = json.load(f)
    except Exception:
        print("[WARN] cache GARP non trovata: nessuna scoperta automatica", file=sys.stderr)
        return {}
    by_industry = {}
    for key, th in THEMES.items():
        for ind in th["industries"]:
            by_industry.setdefault(ind, []).append(key)
    found = {}
    for sym, info in cache.items():
        keys = by_industry.get((info or {}).get("industry"))
        if keys and (info.get("marketCap") or 0) >= DISCOVERY_MCAP_MIN:
            found[sym] = {"themes": keys, "mcap": info.get("marketCap")}
    return found


def build_watch(discovered):
    watch = {}
    for key, th in THEMES.items():
        for t in th["tickers"]:
            watch.setdefault(t, set()).add(key)
    for t, keys in discovered.items():
        watch.setdefault(t, set()).update(keys)
    return {t: sorted(k) for t, k in watch.items()}


def run(watch):
    results = {}
    pending = dict(watch)
    for attempt in range(3):
        errored = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS if attempt == 0 else 2) as ex:
            futs = {ex.submit(evaluate, t, k): t for t, k in pending.items()}
            for fut in as_completed(futs):
                r = fut.result()
                if r.get("error"):
                    errored[r["ticker"]] = pending[r["ticker"]]
                results[r["ticker"]] = r
        if not errored:
            break
        pending = errored
        time.sleep(20)
    return list(results.values())


def make_report(results, curated, started):
    ok = [r for r in results if not r.get("error")]
    errors = [r["ticker"] for r in results if r.get("error")]
    greens = {r["ticker"] for r in ok if r["light"] == "verde"}

    latest_path = os.path.join(RESULTS_DIR, "latest.json")
    prev_greens = set()
    if os.path.exists(latest_path):
        try:
            with open(latest_path) as f:
                prev = json.load(f)
            prev_greens = {r["ticker"] for r in prev.get("tracked", []) if r.get("light") == "verde"}
        except Exception:
            pass

    order = {"verde": 0, "giallo": 1, "rosso": 2}
    ok.sort(key=lambda r: (order[r["light"]], -r["score"], -(r.get("market_cap") or 0)))
    for r in ok:
        r["discovered"] = r["ticker"] not in curated

    today = date.today().isoformat()
    report = {
        "screener": "temi",
        "date": today,
        "generated_at_utc": started.isoformat(),
        "duration_seconds": round((datetime.now(timezone.utc) - started).total_seconds()),
        "criteria": CRITERIA,
        "themes": {k: v["label"] for k, v in THEMES.items()},
        "tracked_count": len(ok),
        "errors": errors,
        "green_count": len(greens),
        "new_green": sorted(greens - prev_greens),
        "lost_green": sorted(prev_greens - greens),
        "tracked": ok,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    for p in (os.path.join(RESULTS_DIR, f"{today}.json"), latest_path):
        with open(p, "w") as f:
            json.dump(report, f, indent=1, default=str)

    def pct(x):
        return f"{x*100:.0f}%" if isinstance(x, (int, float)) else "n/d"

    dot = {"verde": "🟢", "giallo": "🟡", "rosso": "🔴"}
    lines = [f"# Temi strutturali — {today}", "",
             f"Seguiti: {len(ok)} | Verdi: **{len(greens)}** | "
             f"Nuovi verdi: {', '.join(report['new_green']) or '—'} | "
             f"Persi: {', '.join(report['lost_green']) or '—'}", ""]
    for key, th in THEMES.items():
        rows = [r for r in ok if key in r["themes"]]
        lines += [f"## {th['label']}", "",
                  "| | Ticker | Nome | Profilo | Score | Ricavi q/q | % max 52w | Campanelli |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in rows:
            lines.append("| {d} | {t}{s} | {n} | {p} | {sc} | {rg} | {ph} | {fl} |".format(
                d=dot[r["light"]], t=r["ticker"], s=" ·" if r["discovered"] else "",
                n=(r.get("name") or "")[:28], p=r["profile"], sc=r["score"],
                rg=pct(r.get("revenue_growth_qoq_yoy")), ph=pct(r.get("pct_of_52w_high")),
                fl="; ".join(r["flags"]) or "—"))
        lines.append("")
    lines.append("· = trovato dalla scoperta automatica (non in lista curata)")
    with open(os.path.join(RESULTS_DIR, "latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Temi: {len(ok)} seguiti, {len(greens)} verdi, {len(errors)} errori")


def main():
    """SHARD: scoperta dalla cache (nessuna chiamata di rete) -> partials/temi-N.json
    MODE=merge: unisce scoperte + lista curata, valuta e scrive il report.
    Senza variabili: solo lista curata (test locale)."""
    started = datetime.now(timezone.utc)
    mode = os.environ.get("MODE", "").strip().lower()
    shard_env = os.environ.get("SHARD", "").strip()
    curated = {t for th in THEMES.values() for t in th["tickers"]}

    if shard_env != "":
        found = discover_from_cache()
        os.makedirs("partials", exist_ok=True)
        with open(os.path.join("partials", f"temi-{shard_env}.json"), "w") as f:
            json.dump(found, f)
        print(f"Scoperta temi (shard {shard_env}): {len(found)} titoli")
        return

    discovered = {}
    if mode == "merge":
        import glob
        pdir = os.environ.get("PARTIALS_DIR", "partials")
        for fp in sorted(glob.glob(os.path.join(pdir, "temi-*.json"))):
            with open(fp) as f:
                for t, d in json.load(f).items():
                    if t not in curated:
                        discovered[t] = d
        top = sorted(discovered, key=lambda t: -(discovered[t].get("mcap") or 0))
        discovered = {t: discovered[t]["themes"] for t in top[:DISCOVERY_MAX]}
    watch = build_watch(discovered)
    print(f"Titoli da valutare: {len(watch)} ({len(curated)} curati)")
    make_report(run(watch), curated, started)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
