#!/usr/bin/env python3
"""
Moonshot Screener — candidate ad altissimo potenziale di rendimento
====================================================================
Cerca il profilo statistico tipico dei titoli che hanno fatto rendimenti
enormi (es. Palantir, Bloom Energy): small/mid cap in ipercrescita con
momentum di prezzo, MA con filtri di sopravvivenza che riducono la
probabilità di fallimento (cassa, debito, diluizione, traction commerciale).

Dal 08/11/2026 è la lista "Crescita": stesse regole a OGNI taglia, senza il
tetto di 15 Mld$, divisa per fascia (backtest mondiale EODHD 2012-26,
REPORT_screener_tutti_2026-11-07: sopra l'universo della stessa taglia
piccole +6,5, medie +5,3, grandi +9,6 punti l'anno):
  - piccola 0,15-2 Mld$  -> alto_rischio = true (nelle piccole americane le
    regole hanno fatto peggio del mercato, -2 punti l'anno; altrove fragile)
  - media   2-15 Mld$
  - grande  oltre 15 Mld$
Capitalizzazione e ricavi sono convertiti in dollari con cambi indicativi
(FX_USD; prima erano confrontati nella valuta di quotazione). La
capitalizzazione è nella valuta di quotazione (currency), i ricavi in quella
di bilancio (financialCurrency; se manca, quella di quotazione).

FILTRI OBBLIGATORI (tutti):
  - Market cap da 150 M$ in su (nessun tetto dal 08/11/2026; era 150 M$ - 15 B$)
  - Ricavi TTM > 100 M$ (traction commerciale reale, niente story-stock pre-ricavi)
  - Crescita ricavi trimestrale YoY > 25% (ipercrescita)
  - Margine lordo > 25% (economia unitaria scalabile)
  - Momentum: prezzo sopra la media a 200 giorni (il 70% del massimo a 52
    settimane è solo un'etichetta dal 27/10/2026: momentum_solo_200gg)
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
  +0,5 prezzo entro il 10% dal massimo a 52 settimane (era +1 fino al 08/11/2026:
       il momentum non è confermato sul 2000-2011, R_storico_2000_2011)
  +1 stime EPS riviste al rialzo negli ultimi 30 giorni
  +1 stime EPS dell'anno prossimo salite di almeno il 10% in 90 giorni (dal 10/10/2026)

Punteggio massimo 7,5 (era 8). Il dettaglio è in score_componenti.

Output: results-moonshot/YYYY-MM-DD.json, latest.json, latest.md
(dal 08/11/2026 anche crescita_per_fascia: conteggi e liste per fascia)
La validazione QUALITATIVA (vantaggio competitivo, trend secolare, TAM,
concorrenza) è fatta ogni sera da Claude sui nuovi ingressi.
"""

import json
import os
import random
import sys
import time
from types import SimpleNamespace
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import yfinance as yf

# Riusa universo, intestazioni e helper dello screener GARP (stesso repo)
import garp_screener as base

CRITERIA = {
    "mcap_min": 150e6,             # in dollari (convertito con FX_USD dal 08/11/2026)
    # 08/11/2026: nessun tetto (era 15e9). La chiave resta, con null, per non
    # togliere campi dal report
    "mcap_max": None,
    "revenue_ttm_min": 100e6,
    "rev_growth_min": 0.25,
    "gross_margin_min": 0.25,
    "pct_of_52w_high_min": 0.70,
    "runway_years_min": 2.0,
    "debt_to_cash_max": 2.0,
    "net_debt_ebitda_max": 2.5,   # alternativa al debito/cassa per chi ha EBITDA > 0
    "current_ratio_min": 1.2,
    "dilution_cagr_max": 0.15,
    # 08/11/2026: fasce di capitalizzazione in dollari (lista Crescita)
    "fascia_piccola_max": 2e9,
    "fascia_media_max": 15e9,
    # 08/11/2026: peso del prezzo vicino al massimo nel punteggio (era 1)
    "bonus_vicino_massimo": 0.5,
}

# Cambi indicativi verso USD (la capitalizzazione di Yahoo è nella valuta di
# quotazione; GBp = pence, ma capitalizzazione e ricavi sono in sterline).
# Stessa tabella dello screener Svolta.
FX_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "GBp": 1.27, "CHF": 1.13,
          "SEK": 0.095, "NOK": 0.092, "DKK": 0.145, "JPY": 0.0066, "HKD": 0.128,
          "CNY": 0.14, "CAD": 0.72, "AUD": 0.65, "KRW": 0.00072, "TWD": 0.031,
          "INR": 0.012, "ILS": 0.27, "PLN": 0.25, "SGD": 0.74, "BRL": 0.18,
          "ZAR": 0.055, "MXN": 0.054}

# Fasce della lista Crescita (08/11/2026). La piccola è "alto rischio":
# nel backtest 2012-26 la fascia piccola batte l'universo nel mondo (+6,5
# punti l'anno) ma è debole proprio dove ci sono più titoli.
FASCE = ("piccola", "media", "grande")
FASCE_LIMITI_MLD = {"piccola": (0.15, 2), "media": (2, 15), "grande": (15, None)}
MOTIVO_RISCHIO_USA = ("piccola americana: nel backtest 2012-26 le regole qui hanno fatto "
                      "peggio del mercato (circa -2 punti l'anno)")
MOTIVO_RISCHIO_ALTRE = ("piccola: nel backtest 2012-26 risultato fragile (sotto il mercato "
                        "in Europa e in Asia)")
MAX_PASSED_JSON = 250   # promossi scritti in "passed" (erano 100: ora ci sono anche le grandi)


def in_usd(valore, valuta):
    """Importo convertito in dollari con i cambi indicativi; None se la
    valuta non è nota o il valore manca."""
    try:
        v = float(valore)
    except (TypeError, ValueError):
        return None
    if v != v:
        return None
    fx = FX_USD.get(valuta or "USD")
    return v * fx if fx else None


def fascia_dimensione(mcap_usd):
    """'piccola' (0,15-2 Mld$), 'media' (2-15), 'grande' (oltre 15) o None."""
    if mcap_usd is None or mcap_usd < CRITERIA["mcap_min"]:
        return None
    if mcap_usd < CRITERIA["fascia_piccola_max"]:
        return "piccola"
    if mcap_usd <= CRITERIA["fascia_media_max"]:
        return "media"
    return "grande"


def rischio_fascia(fascia, country, index_name=None):
    """(alto_rischio, motivo). Alto rischio = fascia piccola; il motivo
    distingue le americane, dove le regole non hanno funzionato."""
    if fascia != "piccola":
        return False, None
    usa = country == "United States" or str(index_name or "").startswith("USA")
    return True, (MOTIVO_RISCHIO_USA if usa else MOTIVO_RISCHIO_ALTRE)

# Dal 10/10/2026 il Moonshot non eredita più le esclusioni di settore del GARP:
# energia e materie prime restano ammesse ma segnalate come cicliche
CYCLICAL_SECTORS = {"Energy", "Basic Materials"}

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


def _fetch_with_retry(getter, tries=3, base_delay=3.0):
    """Legge un dato Yahoo ripetendo se torna vuoto o fallisce (rate limit):
    lo stage 2 parte subito dopo le ~7.400 chiamate del GARP e senza retry
    i campi pluriennali tornavano null in blocco (34 promossi su 47 l'8/10/2026)."""
    for i in range(tries):
        try:
            v = getter()
            if v is not None and not getattr(v, "empty", False):
                return v
        except Exception:
            pass
        if i < tries - 1:
            time.sleep(base_delay * (2 ** i) + random.random())
    return None


def _stage2_data(tk):
    """Scarica una volta sola, con retry, i dati annuali usati dallo stage 2."""
    return SimpleNamespace(
        balance_sheet=_fetch_with_retry(lambda: tk.balance_sheet),
        income_stmt=_fetch_with_retry(lambda: tk.income_stmt),
        eps_trend=_fetch_with_retry(lambda: tk.eps_trend),
        earnings_history=_fetch_with_retry(lambda: tk.earnings_history),
    )


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


# ticker in errore nel GARP dello stesso shard: la loro cache .info è parziale
GARP_ERRORS = set()


def screen_ticker(symbol, index_name):
    try:
        tk = None
        info = None if symbol in GARP_ERRORS else INFO_CACHE.get(symbol)
        from_cache = bool(info)
        if not info:
            tk = yf.Ticker(symbol)
            info, yf_msgs = base.fetch_info(tk)
            missing = base.check_info(info, yf_msgs)  # .info vuoto o parziale: non valutabile
        else:
            missing = base.check_info(info)

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
        ebitda = info.get("ebitda")

        pct_high = (price / high52) if price and high52 else None
        currency = info.get("currency")
        # Revisione 08/11/2026: Yahoo dà i ricavi nella valuta di BILANCIO
        # (financialCurrency), la capitalizzazione in quella di quotazione.
        # Troax (TROAX.ST) quota in corone ma pubblica in euro; molte ADR
        # quotano in dollari e pubblicano in CNY, INR, CAD... Se la valuta di
        # bilancio manca (cache vecchia) si usa quella di quotazione, come prima.
        fin_currency = info.get("financialCurrency") or currency
        mcap_usd = in_usd(mcap, currency)
        rev_usd = in_usd(rev_ttm, fin_currency)
        fascia = fascia_dimensione(mcap_usd)
        alto_rischio, rischio_motivo = rischio_fascia(fascia, info.get("country"), index_name)
        runway = None
        if fcf is not None and fcf < 0 and cash:
            runway = cash / abs(fcf)

        gm_ok = gm is not None and gm > CRITERIA["gross_margin_min"]
        debt_cash_ok = (debt is None or debt == 0
                        or (cash is not None and cash > 0
                            and debt / cash <= CRITERIA["debt_to_cash_max"]))
        debt_ebitda_ok = (debt is not None and ebitda is not None and ebitda > 0
                          and (debt - (cash or 0)) / ebitda <= CRITERIA["net_debt_ebitda_max"])
        cur_ok = cur_ratio is None or cur_ratio > CRITERIA["current_ratio_min"]
        net_cash = cash is not None and debt is not None and cash >= debt

        checks = {
            "sector_ok": sector is not None,
            # 08/11/2026: in dollari e senza tetto (mcap_max = None)
            "mcap_ok": (mcap_usd is not None and mcap_usd >= CRITERIA["mcap_min"]
                        and (CRITERIA["mcap_max"] is None or mcap_usd <= CRITERIA["mcap_max"])),
            "revenue_scale_ok": rev_usd is not None and rev_usd > CRITERIA["revenue_ttm_min"],
            "hypergrowth_ok": rev_g is not None and rev_g > CRITERIA["rev_growth_min"],
            "gross_margin_ok": gm_ok,
            "momentum_ok": price is not None and ma200 is not None and price > ma200,
            "runway_ok": (fcf is None or fcf >= 0
                          or (runway is not None and runway > CRITERIA["runway_years_min"])),
            "debt_ok": debt_cash_ok or debt_ebitda_ok,
            # il current ratio conta solo per chi ha debito netto (falsato dai
            # fondi dei clienti nei pagamenti)
            "liquidity_ok": cur_ok or net_cash,
        }

        if base.missing_is_decisive(missing, checks):
            e = base.DataError("campi_mancanti", f"campi_mancanti: {', '.join(missing)}")
            # dalla cache: il GARP ha già ritentato nello stesso job
            return base.error_result(symbol, index_name, e, _no_retry=from_cache)

        # Criteri introdotti il 10/10/2026: in osservazione parallela, il titolo
        # resta marcato finché non si decide se tenerli
        criteri_nuovi = []
        if index_name == "Europa (mid/small)":
            criteri_nuovi.append("universo_europa")
        if sector in base.EXCLUDED_SECTORS:
            criteri_nuovi.append("settore")
        if not debt_cash_ok:
            criteri_nuovi.append("debito_ebitda")
        if not cur_ok:
            criteri_nuovi.append("liquidita_cassa_netta")
        # backtest 27/10/2026: la soglia del 70% del massimo e' ridondante,
        # basta il prezzo sopra la media a 200 giorni
        if pct_high is None or pct_high < CRITERIA["pct_of_52w_high_min"]:
            criteri_nuovi.append("momentum_solo_200gg")

        result = {
            "ticker": symbol,
            "name": info.get("longName") or info.get("shortName"),
            "index": index_name,
            "sector": sector,
            "industry": info.get("industry"),
            "country": info.get("country"),
            "market_cap": mcap,
            # 08/11/2026: lista Crescita per fascia
            "currency": currency,
            "market_cap_usd": mcap_usd,
            "fascia_dimensione": fascia,
            "alto_rischio": alto_rischio,
            "alto_rischio_motivo": rischio_motivo,
            "revenue_ttm": rev_ttm,
            # revisione 08/11/2026: valuta dei ricavi e ricavi in dollari
            "financial_currency": fin_currency,
            "revenue_ttm_usd": rev_usd,
            "revenue_growth_qoq_yoy": rev_g,
            "gross_margin": gm,
            "price": price,
            "pct_of_52w_high": pct_high,
            "free_cash_flow": fcf,
            "fcf_yield": base.fcf_yield(fcf, mcap),
            "total_cash": cash,
            "total_debt": debt,
            "runway_years": runway,
            "current_ratio": cur_ratio,
            "checks": checks,
            "criteri_nuovi": criteri_nuovi,
            "ciclico": sector in CYCLICAL_SECTORS or "Shipping" in (info.get("industry") or ""),
        }

        if not all(checks.values()):
            result["passed"] = False
            return result

        # Stage 2: diluizione (filtro) + punteggio bonus
        # (solo qui servono le chiamate di rete: pochi ticker superstiti)
        if tk is None:
            tk = yf.Ticker(symbol)
        tk = _stage2_data(tk)
        result["multi_year_data_ok"] = (tk.balance_sheet is not None
                                        and tk.income_stmt is not None)
        dil = _dilution_cagr(tk)
        result["dilution_cagr"] = dil
        checks["dilution_ok"] = dil is None or dil < CRITERIA["dilution_cagr_max"]
        if not checks["dilution_ok"]:
            result["passed"] = False
            return result

        score = 0
        comp = {}   # 08/11/2026: dettaglio del punteggio (score_componenti)
        cagr = base.sales_cagr_multi_year(tk)
        result["sales_cagr_multi_year"] = cagr
        accel = cagr is not None and rev_g is not None and rev_g > cagr
        if accel:
            comp["accelerazione"] = 2
        margin_up = _operating_margin_trend(tk)
        if margin_up:
            comp["margine_operativo_in_salita"] = 1
        if fcf is not None and fcf > 0:
            comp["fcf_positivo"] = 1
        if cash is not None and debt is not None and cash > debt:
            comp["cassa_netta"] = 1
        if pct_high is not None and pct_high >= 0.90:
            # 08/11/2026: mezzo punto (era 1): il momentum non è confermato
            # sul 2000-2011 (R_storico_2000_2011); resta come freno ai crolli
            comp["vicino_al_massimo"] = CRITERIA["bonus_vicino_massimo"]
        eps_up = _eps_revised_up(tk)
        if eps_up:
            comp["stime_eps_al_rialzo_30g"] = 1
        # dal 10/10/2026: conta anche QUANTO salgono le stime (score max 7,5)
        est = base.estimate_metrics(tk, info)
        result.update(est)
        if (est["revisione_stime_90g"] or 0) >= 0.10:
            comp["stime_anno_prossimo_10pct_90g"] = 1
        score = sum(comp.values())
        if score == int(score):
            score = int(score)

        result.update({
            "passed": True,
            "score": score,
            "score_componenti": comp,
            "accelerating": accel,
            "operating_margin_improving": margin_up,
            "eps_estimates_revised_up": eps_up,
        })
        return result
    except Exception as e:
        return base.error_result(symbol, index_name, e)


def _refetch_missing_multi_year(results):
    """Nel job di merge (IP diverso, nessuna raffica di chiamate alle spalle)
    rielabora i promossi rimasti senza dati annuali: negli shard Yahoo blocca
    l'IP dopo le ~900 chiamate del GARP (8/10/2026: dati completi 8 su 45)."""
    todo = [r for r in results if r.get("passed") and not r.get("multi_year_data_ok")]
    if not todo:
        return results
    print(f"Ricarico i dati annuali di {len(todo)} promossi dal job di merge")
    fixed = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(screen_ticker, r["ticker"], r.get("index", "?")): r["ticker"]
                for r in todo}
        for fut in as_completed(futs):
            try:
                nr = fut.result()
            except Exception:
                continue
            if nr.get("multi_year_data_ok"):
                fixed[futs[fut]] = nr
    print(f"Dati annuali recuperati per {len(fixed)} su {len(todo)}")
    return [fixed.get(r.get("ticker"), r) for r in results]


def crescita_per_fascia(passed):
    """Campo crescita_per_fascia del report (08/11/2026): per ogni fascia il
    conteggio e la lista completa dei promossi (non solo i primi del campo
    passed), nell'ordine del punteggio."""
    out = {
        "regola": "Regole Moonshot a ogni taglia (lista Crescita). Fasce di capitalizzazione "
                  "in dollari: piccola 0,15-2 Mld, media 2-15, grande oltre 15. La fascia "
                  "piccola è ad alto rischio: va radiografata titolo per titolo.",
    }
    for k in FASCE:
        rows = [r for r in passed if r.get("fascia_dimensione") == k]
        da, a = FASCE_LIMITI_MLD[k]
        out[k] = {
            "da_mld_usd": da,
            "a_mld_usd": a,
            "conteggio": len(rows),
            "alto_rischio": k == "piccola",
            "ticker": [r["ticker"] for r in rows],
            "titoli": [{"ticker": r["ticker"], "name": r.get("name"), "score": r.get("score"),
                        "country": r.get("country"), "market_cap_usd": r.get("market_cap_usd"),
                        "alto_rischio": bool(r.get("alto_rischio")),
                        "alto_rischio_motivo": r.get("alto_rischio_motivo")} for r in rows],
        }
    senza = [r["ticker"] for r in passed if r.get("fascia_dimensione") not in FASCE]
    out["senza_fascia"] = {"conteggio": len(senza), "ticker": senza}
    return out


def make_report(results, universe_size, started):
    errors = sum(1 for r in results if r.get("error"))

    passed = sorted(
        [r for r in results if r.get("passed")],
        key=lambda r: (-(r.get("score") or 0), -(r.get("revenue_growth_qoq_yoy") or 0)),
    )

    today = date.today().isoformat()
    latest_path = os.path.join(RESULTS_DIR, "latest.json")
    prev_tickers = base.previous_passed(RESULTS_DIR)
    quality = base.quality_summary(results, prev_tickers)
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
        "passed_old_criteria": sum(1 for r in passed if not r.get("criteri_nuovi")),
        "passed": passed[:MAX_PASSED_JSON],
        # 08/11/2026: lista Crescita divisa per fascia di capitalizzazione
        "crescita_per_fascia": crescita_per_fascia(passed),
        **quality,
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"{today}.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)
    with open(latest_path, "w") as f:
        json.dump(report, f, indent=1, default=str)
    base.write_snapshot("moonshot", [dict(r, stato="passed") for r in passed])

    def pct(x):
        return f"{x*100:.0f}%" if isinstance(x, (int, float)) else "n/d"

    lines = [
        f"# Screening Moonshot — {today}",
        "",
        *base.quality_md_lines(quality, errors, len(results)),
        f"Universo: {universe_size} | Candidate: **{len(passed)}** | Nuove oggi: **{len(new_today)}** | Uscite: {len(dropped)}"
        f" | Non valutabili: {errors}",
        "",
        "† = passa solo coi criteri nuovi del 10/10/2026 (Europa mid/small, settori, debito/EBITDA, liquidità); ⟳ = ciclico",
        "",
        "Dal 08/11/2026 è la lista **Crescita**: stesse regole a ogni taglia, divisa per fascia "
        "(capitalizzazione in dollari). ⚠ = fascia piccola, alto rischio: va radiografata "
        "titolo per titolo. Nel punteggio il prezzo vicino al massimo vale mezzo punto (era 1).",
        "",
        "Per fascia: " + ", ".join(
            f"{k} {report['crescita_per_fascia'][k]['conteggio']}" for k in FASCE),
        "",
        "| Ticker | Nome | Fascia | Score | Ricavi q/q | Margine lordo | % dal max 52w | FCF+ | Accel. | Nuovo |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in passed[:40]:
        lines.append(
            "| {t} | {n} | {fa} | {sc} | {rg} | {gm} | {ph} | {fcf} | {ac} | {new} |".format(
                t=r["ticker"] + (" †" if r.get("criteri_nuovi") else "") + (" ⟳" if r.get("ciclico") else ""),
                n=(r.get("name") or "")[:30],
                fa=(r.get("fascia_dimensione") or "n/d") + (" ⚠" if r.get("alto_rischio") else ""),
                sc=r.get("score"),
                rg=pct(r.get("revenue_growth_qoq_yoy")), gm=pct(r.get("gross_margin")),
                ph=pct(r.get("pct_of_52w_high")),
                fcf="✓" if (r.get("free_cash_flow") or 0) > 0 else "–",
                ac="✓" if r.get("accelerating") else "–",
                new="🆕" if r["ticker"] in new_today else "",
            )
        )
    for k in FASCE:
        fx = report["crescita_per_fascia"][k]
        da, a = FASCE_LIMITI_MLD[k]
        lim = f"{da:g}-{a:g} Mld$".replace(".", ",") if a else f"oltre {da:g} Mld$"
        lines += ["", f"## Crescita {k} ({lim}): {fx['conteggio']}"
                  + (" — ⚠ alto rischio" if fx["alto_rischio"] else ""), ""]
        lines.append(", ".join(
            f"{t['ticker']} ({t['score']})" for t in fx["titoli"]) or "nessuna")
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
        results = _refetch_missing_multi_year(results)
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
            GARP_ERRORS.update(r["ticker"] for r in gp["results"] if r.get("error"))
            universe_size = int(gp.get("universe_size", 0))
            print(f"Fetta di universo ripresa dal GARP: {len(sub)} ticker")
        except Exception:
            universe = base.load_universe_checked()
            universe_size = len(universe)
            sub = base.shard_of(universe, shard, shards)
        print(f"Job parallelo {shard+1}/{shards}: {len(sub)} ticker "
              f"(cache GARP: {len(INFO_CACHE)})")
        results = base.run_screen(sub, screen_ticker, workers=MAX_WORKERS,
                                  priority=base.priority_tickers(RESULTS_DIR))
        os.makedirs("partials", exist_ok=True)
        with open(os.path.join("partials", f"moon-{shard}.json"), "w") as f:
            json.dump({"universe_size": universe_size, "results": results},
                      f, default=str)
        errors = sum(1 for r in results if r.get("error"))
        print(f"Shard completato: {len(results)} risultati, {errors} errori")
        return

    universe = base.load_universe_checked()
    results = base.run_screen(universe, screen_ticker, workers=MAX_WORKERS,
                              priority=base.priority_tickers(RESULTS_DIR))
    make_report(results, len(universe), started)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
