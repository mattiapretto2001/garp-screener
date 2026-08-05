#!/usr/bin/env python3
"""
GARP Daily Screener (Growth at a Reasonable Price)
==================================================
Esegue uno screening quantitativo globale con i criteri:
  - Settori esclusi: Financial Services, Basic Materials, Energy, Utilities, Real Estate
  - Crescita ricavi ultimi 5 anni: > 10% annuo (CAGR, calcolato sugli anni disponibili, min 3)
  - Crescita ricavi trimestre su trimestre (YoY): > 5%
  - Crescita utili trimestre su trimestre (YoY): > 5%
  - ROE: > 15%
  - Debt/Equity: < 1
  - PEG: < 1
  - Free Cash Flow: > 0

Universo: S&P 500, NASDAQ-100, FTSE MIB, DAX, CAC 40, FTSE 100, AEX,
IBEX 35, SMI, Nikkei 225, Hang Seng (fonte: Wikipedia).

Output: results/YYYY-MM-DD.json, results/latest.json, results/latest.md
Pensato per girare su GitHub Actions ogni sera dopo la chiusura di Wall Street.
"""

import json
import math
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import pandas as pd
import requests
import yfinance as yf
from io import StringIO

# ----------------------------- Configurazione -----------------------------

EXCLUDED_SECTORS = {
    "Financial Services",
    "Basic Materials",
    "Energy",
    "Utilities",
    "Real Estate",
}

CRITERIA = {
    "sales_growth_5y_min": 0.10,   # CAGR annuo minimo ricavi (orizzonte pluriennale)
    "sales_qoq_min": 0.05,         # crescita ricavi trimestrale YoY
    "eps_qoq_min": 0.05,           # crescita utili trimestrale YoY
    "roe_min": 0.15,
    "debt_equity_max": 1.0,
    "peg_max": 1.0,
    "fcf_min": 0.0,
    "min_market_cap": 0,           # nessun filtro dimensionale: universo massimo
}

MAX_WORKERS = 12
RESULTS_DIR = "results"

WIKI = "https://en.wikipedia.org/wiki/"

# ----------------------------- Universo titoli -----------------------------


UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 GARP-screener/1.0",
    "Accept-Language": "en-US,en;q=0.9",
}


def _read_wiki_tables(page: str):
    """Wikipedia rifiuta lo user-agent di default di urllib: usiamo requests
    con intestazioni da browser e poi parsiamo l'HTML."""
    url = WIKI + page
    resp = requests.get(url, headers=UA_HEADERS, timeout=30)
    resp.raise_for_status()
    return pd.read_html(StringIO(resp.text))


def _first_col(df, candidates):
    for c in candidates:
        for col in df.columns:
            name = str(col[-1] if isinstance(col, tuple) else col).strip().lower()
            if name == c.lower():
                return df[col]
    return None


def _extract(page, candidates, suffix="", transform=None):
    """Estrae i ticker da una pagina Wikipedia, cercando la colonna giusta."""
    tickers = []
    try:
        for df in _read_wiki_tables(page):
            col = _first_col(df, candidates)
            if col is None or len(col) < 10:
                continue
            for raw in col.dropna().astype(str):
                t = raw.strip().split("[")[0].strip()
                if not t or t.lower() == "nan" or len(t) > 12:
                    continue
                if transform:
                    t = transform(t)
                if suffix and not t.endswith(suffix):
                    t = t + suffix
                tickers.append(t)
            if len(tickers) >= 10:
                break
    except Exception as e:
        print(f"[WARN] Universo {page}: {e}", file=sys.stderr)
    return tickers


def _us_full_listing():
    """Tutti i titoli quotati USA (NASDAQ + NYSE + AMEX) dal symbol directory
    ufficiale di Nasdaq Trader. Esclude ETF, test issue e strumenti derivati
    (warrant, preferred, unit)."""
    tickers = []
    sources = [
        ("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", "Symbol", "ETF", "Test Issue"),
        ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", "ACT Symbol", "ETF", "Test Issue"),
    ]
    for url, sym_col, etf_col, test_col in sources:
        try:
            resp = requests.get(url, headers=UA_HEADERS, timeout=30)
            resp.raise_for_status()
            lines = resp.text.splitlines()
            header = lines[0].split("|")
            idx_sym = header.index(sym_col)
            idx_etf = header.index(etf_col) if etf_col in header else None
            idx_test = header.index(test_col) if test_col in header else None
            for line in lines[1:]:
                parts = line.split("|")
                if len(parts) <= idx_sym or line.startswith("File Creation"):
                    continue
                if idx_etf is not None and len(parts) > idx_etf and parts[idx_etf] == "Y":
                    continue  # ETF
                if idx_test is not None and len(parts) > idx_test and parts[idx_test] == "Y":
                    continue  # test issue
                sym = parts[idx_sym].strip()
                # esclude preferred/warrant/unit e simboli anomali
                if not sym or len(sym) > 5 or any(c in sym for c in "$^~="):
                    continue
                tickers.append(sym.replace(".", "-"))
        except Exception as e:
            print(f"[WARN] US listing {url}: {e}", file=sys.stderr)
    return tickers


def build_universe():
    """Costruisce l'universo globale. Ogni indice è opzionale: se una fonte
    fallisce si prosegue con le altre."""
    u = {}

    u["S&P 500"] = _extract(
        "List_of_S%26P_500_companies", ["Symbol"],
        transform=lambda t: t.replace(".", "-"),  # BRK.B -> BRK-B
    )
    u["NASDAQ-100"] = _extract(
        "Nasdaq-100", ["Ticker", "Symbol"],
        transform=lambda t: t.replace(".", "-"),
    )
    u["FTSE MIB"] = _extract("FTSE_MIB", ["Ticker", "Symbol"], suffix=".MI",
                             transform=lambda t: t.replace("BIT:", "").strip())
    u["DAX"] = _extract("DAX", ["Ticker", "Symbol"], suffix=".DE")
    u["CAC 40"] = _extract("CAC_40", ["Ticker", "Symbol"], suffix=".PA")
    u["FTSE 100"] = _extract(
        "FTSE_100_Index", ["Ticker", "EPIC", "Symbol"], suffix=".L",
        transform=lambda t: t.replace(".", "-").rstrip("-"),
    )
    u["AEX"] = _extract("AEX_index", ["Ticker symbol", "Ticker", "Symbol"], suffix=".AS")
    u["IBEX 35"] = _extract("IBEX_35", ["Ticker", "Symbol"], suffix=".MC")
    u["SMI"] = _extract("Swiss_Market_Index", ["Ticker", "Symbol"], suffix=".SW")
    u["Nikkei 225"] = _extract(
        "Nikkei_225", ["Ticker symbol", "Ticker", "Symbol", "Code"], suffix=".T",
        transform=lambda t: t.replace("TYO:", "").strip(),
    )
    u["Hang Seng"] = _extract(
        "Hang_Seng_Index", ["Ticker", "Symbol", "Code"], suffix=".HK",
        transform=lambda t: t.replace("SEHK:", "").strip().zfill(4),
    )

    # Per ultimo, così i membri degli indici mantengono l'etichetta dell'indice
    u["USA (altre quotate)"] = _us_full_listing()

    tickers = {}
    for index_name, lst in u.items():
        print(f"  {index_name}: {len(lst)} titoli")
        for t in lst:
            tickers.setdefault(t, index_name)
    return tickers  # {ticker: indice}


# ----------------------------- Screening -----------------------------


def sales_cagr_multi_year(tk: yf.Ticker):
    """CAGR dei ricavi sugli anni fiscali disponibili (yfinance ne espone ~4).
    Richiede almeno 3 anni di dati; ritorna None se non calcolabile."""
    try:
        inc = tk.income_stmt
        if inc is None or inc.empty or "Total Revenue" not in inc.index:
            return None
        rev = inc.loc["Total Revenue"].dropna().sort_index()
        if len(rev) < 3:
            return None
        first, last = float(rev.iloc[0]), float(rev.iloc[-1])
        years = (rev.index[-1] - rev.index[0]).days / 365.25
        if first <= 0 or years < 1.5:
            return None
        return (last / first) ** (1.0 / years) - 1.0
    except Exception:
        return None


def compute_peg(info):
    peg = info.get("trailingPegRatio")
    if peg is not None and not (isinstance(peg, float) and math.isnan(peg)):
        return float(peg), "trailingPegRatio"
    # Fallback: PE / crescita utili attesa (in %)
    pe = info.get("trailingPE") or info.get("forwardPE")
    growth = info.get("earningsGrowth")
    if pe and growth and growth > 0:
        return float(pe) / (float(growth) * 100.0), "PE/earningsGrowth"
    return None, None


def screen_ticker(symbol, index_name):
    """Stage 1: filtri da .info. Ritorna dict con esito e metriche."""
    try:
        tk = yf.Ticker(symbol)
        info = tk.info or {}

        sector = info.get("sector")
        mcap = info.get("marketCap")
        roe = info.get("returnOnEquity")
        de = info.get("debtToEquity")  # in percento (es. 45.3)
        fcf = info.get("freeCashflow")
        rev_g = info.get("revenueGrowth")           # trimestrale YoY (frazione)
        eps_g = info.get("earningsQuarterlyGrowth")  # trimestrale YoY (frazione)
        peg, peg_src = compute_peg(info)

        checks = {}
        checks["sector_ok"] = sector is not None and sector not in EXCLUDED_SECTORS
        checks["mcap_ok"] = mcap is not None and mcap >= CRITERIA["min_market_cap"]
        checks["roe_ok"] = roe is not None and roe > CRITERIA["roe_min"]
        checks["de_ok"] = de is not None and (de / 100.0) < CRITERIA["debt_equity_max"]
        checks["fcf_ok"] = fcf is not None and fcf > CRITERIA["fcf_min"]
        checks["rev_qoq_ok"] = rev_g is not None and rev_g > CRITERIA["sales_qoq_min"]
        checks["eps_qoq_ok"] = eps_g is not None and eps_g > CRITERIA["eps_qoq_min"]
        checks["peg_ok"] = peg is not None and 0 < peg < CRITERIA["peg_max"]

        stage1_pass = all(checks.values())

        result = {
            "ticker": symbol,
            "name": info.get("longName") or info.get("shortName"),
            "index": index_name,
            "sector": sector,
            "industry": info.get("industry"),
            "country": info.get("country"),
            "currency": info.get("currency"),
            "market_cap": mcap,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "roe": roe,
            "debt_to_equity": (de / 100.0) if de is not None else None,
            "free_cash_flow": fcf,
            "revenue_growth_qoq_yoy": rev_g,
            "eps_growth_qoq_yoy": eps_g,
            "peg": peg,
            "peg_source": peg_src,
            "checks": checks,
            "stage1_pass": stage1_pass,
        }

        # Stage 2 (solo per chi passa lo stage 1): CAGR pluriennale dei ricavi
        if stage1_pass:
            cagr = sales_cagr_multi_year(tk)
            result["sales_cagr_multi_year"] = cagr
            result["checks"]["sales_5y_ok"] = (
                cagr is not None and cagr > CRITERIA["sales_growth_5y_min"]
            )
            result["passed"] = result["checks"]["sales_5y_ok"]
        else:
            result["passed"] = False

        return result
    except Exception as e:
        return {"ticker": symbol, "index": index_name, "error": str(e), "passed": False}


# ----------------------------- Main -----------------------------


def main():
    started = datetime.now(timezone.utc)
    print("Costruzione universo…")
    universe = build_universe()
    print(f"Universo totale: {len(universe)} ticker unici")
    if len(universe) < 200:
        print(f"ERRORE: universo troppo piccolo ({len(universe)} ticker): "
              "le fonti degli indici non sono raggiungibili. Interrompo senza "
              "sovrascrivere i risultati.", file=sys.stderr)
        sys.exit(1)

    results, errors = [], 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {
            ex.submit(screen_ticker, t, idx): t for t, idx in universe.items()
        }
        done = 0
        for fut in as_completed(futures):
            r = fut.result()
            done += 1
            if done % 100 == 0:
                print(f"  analizzati {done}/{len(universe)}…")
            if r.get("error"):
                errors += 1
            results.append(r)

    passed = sorted(
        [r for r in results if r.get("passed")],
        key=lambda r: (r.get("peg") if r.get("peg") is not None else 9e9),
    )
    # "Quasi": passano tutto tranne UN criterio (utile come watchlist)
    near_miss = []
    for r in results:
        ch = r.get("checks")
        if ch and not r.get("passed"):
            fails = [k for k, v in ch.items() if not v]
            if len(fails) == 1:
                r["failed_check"] = fails[0]
                near_miss.append(r)
    near_miss = sorted(near_miss, key=lambda r: r.get("failed_check") or "")

    today = date.today().isoformat()

    # Confronto con il run precedente per individuare i NUOVI ingressi
    prev_tickers = set()
    latest_path = os.path.join(RESULTS_DIR, "latest.json")
    if os.path.exists(latest_path):
        try:
            with open(latest_path) as f:
                prev = json.load(f)
            prev_tickers = {p["ticker"] for p in prev.get("passed", [])}
        except Exception:
            pass
    new_today = [r for r in passed if r["ticker"] not in prev_tickers]
    dropped = sorted(prev_tickers - {r["ticker"] for r in passed})

    report = {
        "date": today,
        "generated_at_utc": started.isoformat(),
        "duration_seconds": round((datetime.now(timezone.utc) - started).total_seconds()),
        "criteria": CRITERIA,
        "excluded_sectors": sorted(EXCLUDED_SECTORS),
        "universe_size": len(universe),
        "analyzed": len(results),
        "errors": errors,
        "passed_count": len(passed),
        "new_today": [r["ticker"] for r in new_today],
        "dropped_since_yesterday": dropped,
        "passed": passed,
        "near_miss_count": len(near_miss),
        "near_miss": near_miss[:60],
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"{today}.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)
    with open(latest_path, "w") as f:
        json.dump(report, f, indent=1, default=str)

    # Riepilogo leggibile in Markdown
    def fmt_pct(x):
        return f"{x*100:.1f}%" if isinstance(x, (int, float)) else "n/d"

    lines = [
        f"# Screening GARP — {today}",
        "",
        f"Universo: {len(universe)} titoli | Superano tutti i filtri: **{len(passed)}**"
        f" | Nuovi oggi: **{len(new_today)}** | Usciti: {len(dropped)}",
        "",
        "| Ticker | Nome | Indice | Settore | PEG | ROE | D/E | Ricavi q/q | EPS q/q | CAGR ricavi | Nuovo |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in passed:
        lines.append(
            "| {t} | {n} | {i} | {s} | {peg:.2f} | {roe} | {de:.2f} | {rg} | {eg} | {cagr} | {new} |".format(
                t=r["ticker"], n=(r.get("name") or "")[:34], i=r["index"],
                s=r.get("sector") or "", peg=r.get("peg") or 0,
                roe=fmt_pct(r.get("roe")), de=r.get("debt_to_equity") or 0,
                rg=fmt_pct(r.get("revenue_growth_qoq_yoy")),
                eg=fmt_pct(r.get("eps_growth_qoq_yoy")),
                cagr=fmt_pct(r.get("sales_cagr_multi_year")),
                new="🆕" if r["ticker"] in report["new_today"] else "",
            )
        )
    if dropped:
        lines += ["", f"Usciti dalla lista rispetto al run precedente: {', '.join(dropped)}"]
    with open(os.path.join(RESULTS_DIR, "latest.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nCompletato: {len(passed)} titoli passano tutti i filtri "
          f"({len(new_today)} nuovi). Errori dati: {errors}.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
