#!/usr/bin/env python3
"""
Moonshot Screener — candidate ad altissimo potenziale di rendimento
====================================================================
Cerca il profilo statistico tipico dei titoli che hanno fatto rendimenti
enormi (es. Palantir, Bloom Energy): small/mid cap in ipercrescita con
momentum di prezzo, MA con filtri di sopravvivenza che riducono la
probabilità di fallimento (cassa, debito, diluizione, traction commerciale).

FILTRI OBBLIGATORI (tutti):
  - Market cap tra 150 M$ e 15 B$ (small/mid cap: lo spazio dei moonshot)
  - Ricavi TTM > 100 M$ (traction commerciale reale, niente story-stock pre-ricavi)
  - Crescita ricavi trimestrale YoY > 25% (ipercrescita)
  - Margine lordo > 25% (economia unitaria scalabile)
  - Momentum: prezzo >= 70% del massimo a 52 settimane E sopra la media a 200 giorni
  - Sopravvivenza:
      * se FCF < 0: cassa sufficiente per > 2 anni al ritmo di burn attuale
      * debito totale <= 2x la cassa
      * current ratio > 1.2 (se disponibile)
  - Diluizione: aumento azioni in circolazione < 15% annuo
  - Settori esclusi come nello screener GARP

PUNTEGGIO BONUS (ordina i candidati, non esclude):
  +2 crescita in accelerazione (ultimo trimestre YoY > CAGR pluriennale)
  +1 margine operativo in miglioramento anno su anno
  +1 FCF già positivo
  +1 posizione di cassa netta (cassa > debito)
  +1 prezzo entro il 10% dal massimo a 52 settimane
  +1 stime EPS riviste al rialzo negli ultimi 30 giorni

Output: results-moonshot/YYYY-MM-DD.json, latest.json, latest.md
La validazione QUALITATIVA (vantaggio competitivo, trend secolare, TAM,
concorrenza) è fatta ogni sera da Claude sui nuovi ingressi.
"""

import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import yfinance as yf

# Riusa universo, intestazioni e helper dello screener GARP (stesso repo)
import garp_screener as base

CRITERIA = {
    "mcap_min": 150e6,
    "mcap_max": 15e9,
    "revenue_ttm_min": 100e6,
    "rev_growth_min": 0.25,
    "gross_margin_min": 0.25,
    "pct_of_52w_high_min": 0.70,
    "runway_years_min": 2.0,
    "debt_to_cash_max": 2.0,
    "current_ratio_min": 1.2,
    "dilution_cagr_max": 0.15,
}

MAX_WORKERS = 8
RESULTS_DIR = "results-moonshot"

# Cache dei dati .info scritta dallo screener GARP nello stesso job: evita
# di rifare ~7.000 chiamate a Yahoo (e i relativi limiti di frequenza)
try:
    with open(base.INFO_CACHE_PATH) as _f:
        INFO_CACHE = json.load(_f)
    print(f"Cache dati GARP caricata: {len(INFO_CACHE)} ticker")
except Exception:
    INFO_CACHE = {}
    print("[WARN] cache dati non trovata: scarico i dati da Yahoo", file=sys.stderr)


def _dilution_cagr(tk):
    """CAGR delle azioni in circolazione dagli stati patrimoniali annuali."""
    try:
        bs = tk.balance_sheet
        row = None
        for name in ("Ordinary Shares Number", "Share Issued"):
            if bs is not None and not bs.empty and name in bs.index:
                row = bs.loc[name].dropna().sort_index()
                break
        if row is None or len(row) < 2 or float(row.iloc[0]) <= 0:
            return None
        years = (row.index[-1] - row.index[0]).days / 365.25
        if years < 0.9:
            return None
        return (float(row.iloc[-1]) / float(row.iloc[0])) ** (1 / years) - 1
    except Exception:
        return None


def _operating_margin_trend(tk):
    """True se il margine operativo dell'ultimo anno fiscale è migliorato."""
    try:
        inc = tk.income_stmt
        if inc is None or inc.empty:
            return None
        if "Operating Income" not in inc.index or "Total Revenue" not in inc.index:
            return None
        oi = inc.loc["Operating Income"].dropna().sort_index()
        rev = inc.loc["Total Revenue"].dropna().sort_index()
        common = oi.index.intersection(rev.index)
        if len(common) < 2:
            return None
        m = (oi[common] / rev[common]).sort_index()
        return bool(m.iloc[-1] > m.iloc[-2])
    except Exception:
        return None


def _eps_revised_up(tk):
    """True se le stime EPS per l'anno corrente sono state riviste al rialzo
    negli ultimi 30 giorni (dato analisti, se disponibile)."""
    try:
        trend = tk.eps_trend
        if trend is None or trend.empty or "0y" not in trend.index:
            return None
        row = trend.loc["0y"]
        cur, ago30 = row.get("current"), row.get("30daysAgo")
        if cur is None or ago30 is None or ago30 == 0:
            return None
        return bool(cur > ago30)
    except Exception:
        return None


def screen_ticker(symbol, index_name):
    try:
        tk = None
        info = INFO_CACHE.get(symbol)
        if not info:
            tk = yf.Ticker(symbol)
            info = tk.info or {}

        sector = info.get("sector")
        mcap = info.get("marketCap")
        rev_ttm = info.get("totalRevenue")
        rev_g = info.get("revenueGrowth")
        gm = info.get("grossMargins")
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        high52 = info.get("fiftyTwoWeekHigh")
        ma200 = info.get("twoHundredDayAverage")
        fcf = info.get("freeCashflow")
        cash = info.get("totalCash")
        debt = info.get("totalDebt")
        cur_ratio = info.get("currentRatio")

        pct_high = (price / high52) if price and high52 else None
        runway = None
        if fcf is not None and fcf < 0 and cash:
            runway = cash / abs(fcf)

        checks = {
            "sector_ok": sector is not None and sector not in base.EXCLUDED_SECTORS,
            "mcap_ok": mcap is not None and CRITERIA["mcap_min"] <= mcap <= CRITERIA["mcap_max"],
            "revenue_scale_ok": rev_ttm is not None and rev_ttm > CRITERIA["revenue_ttm_min"],
            "hypergrowth_ok": rev_g is not None and rev_g > CRITERIA["rev_growth_min"],
            "gross_margin_ok": gm is not None and gm > CRITERIA["gross_margin_min"],
            "momentum_ok": (pct_high is not None and pct_high >= CRITERIA["pct_of_52w_high_min"]
                            and price is not None and ma200 is not None and price > ma200),
            "runway_ok": (fcf is None or fcf >= 0
                          or (runway is not None and runway > CRITERIA["runway_years_min"])),
            "debt_ok": (debt is None or debt == 0
                        or (cash is not None and cash > 0
                            and debt / cash <= CRITERIA["debt_to_cash_max"])),
            "liquidity_ok": cur_ratio is None or cur_ratio > CRITERIA["current_ratio_min"],
        }

        result = {
            "ticker": symbol,
            "name": info.get("longName") or info.get("shortName"),
            "index": index_name,
            "sector": sector,
            "industry": info.get("industry"),
            "country": info.get("country"),
            "market_cap": mcap,
            "revenue_ttm": rev_ttm,
            "revenue_growth_qoq_yoy": rev_g,
            "gross_margin": gm,
            "price": price,
            "pct_of_52w_high": pct_high,
            "free_cash_flow": fcf,
            "total_cash": cash,
            "total_debt": debt,
            "runway_years": runway,
            "current_ratio": cur_ratio,
            "checks": checks,
        }

        if not all(checks.values()):
            result["passed"] = False
            return result

        # Stage 2: diluizione (filtro) + punteggio bonus
        # (solo qui servono le chiamate di rete: pochi ticker superstiti)
        if tk is None:
            tk = yf.Ticker(symbol)
        dil = _dilution_cagr(tk)
        result["dilution_cagr"] = dil
        checks["dilution_ok"] = dil is None or dil < CRITERIA["dilution_cagr_max"]
        if not checks["dilution_ok"]:
            result["passed"] = False
            return result

        score = 0
        cagr = base.sales_cagr_multi_year(tk)
        result["sales_cagr_multi_year"] = cagr
        accel = cagr is not None and rev_g is not None and rev_g > cagr
        if accel:
            score += 2
        margin_up = _operating_margin_trend(tk)
        if margin_up:
            score += 1
        if fcf is not None and fcf > 0:
            score += 1
        if cash is not None and debt is not None and cash > debt:
            score += 1
        if pct_high is not None and pct_high >= 0.90:
            score += 1
        eps_up = _eps_revised_up(tk)
        if eps_up:
            score += 1

        result.update({
            "passed": True,
            "score": score,
            "accelerating": accel,
            "operating_margin_improving": margin_up,
            "eps_estimates_revised_up": eps_up,
        })
        return result
    except Exception as e:
        return {"ticker": symbol, "index": index_name, "error": str(e), "passed": False}


def make_report(results, universe_size, started):
    errors = sum(1 for r in results if r.get("error"))

    passed = sorted(
        [r for r in results if r.get("passed")],
        key=lambda r: (-(r.get("score") or 0), -(r.get("revenue_growth_qoq_yoy") or 0)),
    )

    today = date.today().isoformat()
    prev_tickers = set()
    latest_path = os.path.join(RESULTS_DIR, "latest.json")
    if os.path.exists(latest_path):
        try:
            with open(latest_path) as f:
                prev_tickers = {p["ticker"] for p in json.load(f).get("passed", [])}
        except Exception:
            pass
    new_today = [r["ticker"] for r in passed if r["ticker"] not in prev_tickers]
    dropped = sorted(prev_tickers - {r["ticker"] for r in passed})

    report = {
        "screener": "moonshot",
        "date": today,
        "generated_at_utc": started.isoformat(),
        "duration_seconds": round((datetime.now(timezone.utc) - started).total_seconds()),
        "criteria": CRITERIA,
        "universe_size": universe_size,
        "analyzed": len(results),
        "errors": errors,
        "passed_count": len(passed),
        "new_today": new_today,
        "dropped_since_yesterday": dropped,
        "passed": passed[:60],
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"{today}.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)
    with open(latest_path, "w") as f:
        json.dump(report, f, indent=1, default=str)

    def pct(x):
        return f"{x*100:.0f}%" if isinstance(x, (int, float)) else "n/d"

    lines = [
        f"# Screening Moonshot — {today}",
        "",
        f"Universo: {universe_size} | Candidate: **{len(passed)}** | Nuove oggi: **{len(new_today)}** | Uscite: {len(dropped)}",
        "",
        "| Ticker | Nome | Score | Ricavi q/q | Margine lordo | % dal max 52w | FCF+ | Accel. | Nuovo |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in passed[:40]:
        lines.append(
            "| {t} | {n} | {sc} | {rg} | {gm} | {ph} | {fcf} | {ac} | {new} |".format(
                t=r["ticker"], n=(r.get("name") or "")[:30], sc=r.get("score"),
                rg=pct(r.get("revenue_growth_qoq_yoy")), gm=pct(r.get("gross_margin")),
                ph=pct(r.get("pct_of_52w_high")),
                fcf="✓" if (r.get("free_cash_flow") or 0) > 0 else "–",
                ac="✓" if r.get("accelerating") else "–",
                new="🆕" if r["ticker"] in new_today else "",
            )
        )
    with open(os.path.join(RESULTS_DIR, "latest.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nCompletato: {len(passed)} candidate moonshot ({len(new_today)} nuove). Errori: {errors}.")


def main():
    """Stesse tre modalità dello screener GARP: SHARD (job parallelo),
    MODE=merge (unione parziali e report), oppure run completo locale."""
    started = datetime.now(timezone.utc)
    mode = os.environ.get("MODE", "").strip().lower()
    shard_env = os.environ.get("SHARD", "").strip()

    if mode == "merge":
        results, usize = base.load_partials("moon")
        make_report(results, usize, started)
        return

    if shard_env != "":
        shard = int(shard_env)
        shards = int(os.environ.get("SHARDS", "8"))
        # Riusa la fetta di universo del GARP nello stesso job (evita che una
        # fonte indisponibile sposti i confini delle fette tra i due screener)
        garp_partial = os.path.join("partials", f"garp-{shard}.json")
        universe_size = None
        try:
            with open(garp_partial) as f:
                gp = json.load(f)
            sub = {r["ticker"]: r.get("index", "?") for r in gp["results"]}
            universe_size = int(gp.get("universe_size", 0))
            print(f"Fetta di universo ripresa dal GARP: {len(sub)} ticker")
        except Exception:
            universe = base.load_universe_checked()
            universe_size = len(universe)
            sub = base.shard_of(universe, shard, shards)
        print(f"Job parallelo {shard+1}/{shards}: {len(sub)} ticker "
              f"(cache GARP: {len(INFO_CACHE)})")
        results = base.run_screen(sub, screen_ticker, workers=MAX_WORKERS)
        os.makedirs("partials", exist_ok=True)
        with open(os.path.join("partials", f"moon-{shard}.json"), "w") as f:
            json.dump({"universe_size": universe_size, "results": results},
                      f, default=str)
        errors = sum(1 for r in results if r.get("error"))
        print(f"Shard completato: {len(results)} risultati, {errors} errori")
        return

    universe = base.load_universe_checked()
    results = base.run_screen(universe, screen_ticker, workers=MAX_WORKERS)
    make_report(results, len(universe), started)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
