#!/usr/bin/env python3
"""
Qualità durevole (dal 08/11/2026)
=================================
Regola Q3 del backtest mondiale EODHD (REPORT_screener_tutti_2026-11-07,
regole in scr_common.py, fissate prima di guardare i risultati).

Base comune:
  - capitalizzazione >= 5 Mld$;
  - ricavi cresciuti almeno dell'8% l'anno in 5 anni (6 bilanci annuali), con
    al massimo 1 anno in calo su 5;
  - debito basso: cassa netta, oppure debito netto non oltre 2,5 volte
    l'utile operativo degli ultimi 12 mesi;
  - PEG <= 3, oppure PEG non calcolabile.
Q1 "rendimento del capitale": ROE (utile / patrimonio) >= 15% in almeno 4 degli
   ultimi 5 anni fiscali, e margine operativo dell'ultimo anno non sotto la
   media dei 5 anni di oltre 2 punti.
Q2 "margini": margine operativo >= 20% in almeno 4 anni su 5, stessa
   stabilità, e margine lordo non sceso di oltre 2 punti in 4 anni (se noto).
Q3 = Q1 oppure Q2: è la lista. Servono 5 anni completi di ROE, margine
   operativo e crescita dei ricavi (patrimonio negativo = ROE non calcolabile
   = fuori, come nel backtest).

Settori: esclusioni del GARP (finanza, materie prime, energia, servizi
pubblici, immobiliare), con l'eccezione di pagamenti e dati finanziari
(industrie Yahoo "Credit Services" e "Financial Data & Stock Exchanges":
Mastercard, Visa, S&P Global), raccomandata dal backtest (effetto nullo sul
passato: +0,9 contro +0,8 punti l'anno). QUALITA_ECCEZIONE_PAGAMENTI=0 la toglie.

Cosa aspettarsi (backtest): Q3 NON batte il mercato (+0,6 punti l'anno sulle
grandi nel 2012-26, +3,4 nel 2018-26), ma oscilla meno (15,6% contro 17,3%)
e ha meno crolli. È la parte "stabile" del portafoglio, accanto al core GARP
(metà e metà: +4,9 punti l'anno sull'universo con un quinto di oscillazioni
in meno del solo core). In Europa non ha funzionato (-3 punti l'anno).

Dati:
  - Yahoo, dalla cache .info del GARP (nel job di merge partials/info-*.json;
    se mancano, l'ultima fotografia snapshots/universo/*.csv.gz): settore,
    industria, capitalizzazione, ROE 12 mesi, PEG, prezzo.
  - EODHD, solo per i candidati del primo filtro (capitalizzazione >= 5 Mld$,
    settore ammesso, ROE Yahoo oltre 15% OPPURE margine lordo Yahoo oltre il
    50%; circa 800 società): bilanci annuali e trimestrali, 10 crediti a
    società. Yahoo dà solo 4 bilanci annuali, Q3 ne vuole 6. Le doppie
    quotazioni con lo stesso nome si scaricano una volta.
    Il primo filtro serve solo a risparmiare crediti. Con il solo ROE perdeva
    circa l'8-9% delle società Q3, quelle che passano con i margini (Q2) e
    hanno il ROE di Yahoo appena sotto il 15% (Veeva, Richemont, Descartes,
    Birkenstock): dalla revisione del 08/11/2026 entra anche chi ha il margine
    lordo oltre il 50% (se Yahoo lo dà). Circa 215 società in più, circa
    2.200 crediti in più la prima notte e circa 430 a notte poi.

LICENZA: il repository è pubblico e il piano EODHD non permette di
ridistribuire i dati grezzi. Dai bilanci EODHD si salvano SOLO valori derivati
calcolati qui: esiti sì/no delle regole, numero di anni sopra soglia (0-5),
punteggio e data di chiusura dell'ultimo bilancio annuale. Nessun importo né
rapporto EODHD finisce nei file. Anche la diluizione è solo un sì/no
(azioni_oltre_25_1a: azioni in circolazione oltre +25% in un anno), per la
guardia di sicurezza della lista da radiografare.

Cache dei derivati (results-qualita/derivati_eodhd.json): ogni società ha un
giorno feriale fisso di rinnovo (crc32 del ticker, modulo 5) e si riscarica
quel giorno se il dato ha almeno QUALITA_RINNOVO_GIORNI - 4 giorni (default 7,
quindi 3), oppure in qualunque giorno dopo QUALITA_RINNOVO_GIORNI + 2 giorni
(turno saltato). Così ogni notte si rinnova circa un quinto delle società
(circa 1.200 crediti) invece di tutte nella stessa notte (circa 5.800). La
prima notte si scarica tutto. Codici che EODHD non conosce: dopo 28 giorni.
Prima le mai scaricate e le più vecchie, poi per capitalizzazione. Un dato con
più di QUALITA_SCADENZA_GIORNI giorni (default 45) non si usa.

Crediti: tetto QUALITA_CAP_CREDITI (default 15.000) per notte; si ferma se i
crediti rimasti nel giorno scendono sotto QUALITA_RESIDUO_MIN (default 5.000);
tempo massimo QUALITA_TEMPO_MAX_S (default 900 s). Chiave come in
snapshot_stime_eodhd.py: EODHD_API_TOKEN su GitHub Actions (parametro
api_token); senza la variabile non si manda nulla (proxy).

Uscita: results-qualita/latest.json, latest.md, <data>.json e la cache
derivati_eodhd.json.

Uso locale:
  python qualita_screener.py --tickers MA,ASML.AS,SPGI --out-dir /tmp/x
"""

import argparse
import csv
import glob
import gzip
import json
import math
import os
import sys
import time
import traceback
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import requests

import garp_screener as base
import snapshot_stime_eodhd as sse
from lista_radiografare import norm_nome

RESULTS_DIR = "results-qualita"
CACHE_FILE = "derivati_eodhd.json"
FILTRO = ("General::CurrencyCode,Financials::Income_Statement,"
          "Financials::Balance_Sheet")
MAX_WORKERS = 4

CRITERIA = {
    "mcap_min_usd": 5e9,
    "prefiltro_roe_min": 0.15,        # ROE 12 mesi di Yahoo: solo per risparmiare crediti
    # revisione 08/11/2026: in alternativa al ROE, margine lordo 12 mesi di Yahoo
    # (recupera le società Q2 con il ROE appena sotto il 15%)
    "prefiltro_margine_lordo_min": 0.50,
    "ricavi_cagr5_min": 0.08,
    "anni_in_calo_max": 1,
    "debito_netto_utile_operativo_max": 2.5,
    "peg_max": 3.0,
    "roe_min": 0.15,
    "anni_roe_min": 4,
    "margine_operativo_min": 0.20,
    "anni_margine_min": 4,
    "stabilita_margine_punti": 0.02,
    "margine_lordo_calo_max_punti": 0.02,
    "bilancio_annuale_eta_max_mesi": 15,
    # solo per il sì/no azioni_oltre_25_1a (guardia della lista da radiografare)
    "diluizione_1a_soglia": base.CRITERIA.get("sicurezza_diluizione_max", 0.25),
}

# rapporti fra le azioni di oggi e di un anno prima che sembrano un
# frazionamento non corretto da EODHD (es. Amphenol 2:1 nel 2024): il sì/no
# della diluizione resta "non noto" invece di segnare una falsa diluizione
# (tolleranza 3%: in un anno si aggiungono riacquisti ed emissioni normali)
RAPPORTI_FRAZIONAMENTO = (1.5, 2.0, 3.0, 4.0)
TOLLERANZA_FRAZIONAMENTO = 0.03
# giorni feriali dei turni di rinnovo della cache (lo screener gira lun-ven)
GIORNI_TURNO = 5

# Pagamenti e dati finanziari: riammessi nonostante il settore "Financial
# Services" (prova del backtest scr_04c: effetto nullo sul passato)
ECCEZIONE_INDUSTRIE = ("Credit Services", "Financial Data & Stock Exchanges")

# Cambi indicativi verso USD (stessa tabella di Moonshot e Svolta)
FX_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "GBp": 1.27, "CHF": 1.13,
          "SEK": 0.095, "NOK": 0.092, "DKK": 0.145, "JPY": 0.0066, "HKD": 0.128,
          "CNY": 0.14, "CAD": 0.72, "AUD": 0.65, "KRW": 0.00072, "TWD": 0.031,
          "INR": 0.012, "ILS": 0.27, "PLN": 0.25, "SGD": 0.74, "BRL": 0.18,
          "ZAR": 0.055, "MXN": 0.054}

# suffisso Yahoo -> borsa EODHD: quelle della fotografia delle stime più Hong
# Kong, Vienna, Lisbona e Dublino (presenti nelle liste simboli EODHD). Milano
# non c'è: EODHD non la copre (le società con doppia quotazione si scaricano
# dall'altra borsa).
BORSE = {**sse.BORSE, "HK": "HK", "VI": "VI", "LS": "LS", "IR": "IR"}

ESITI_DA_TENERE = {"ok", "non_trovato", "senza_bilanci", "storico_corto", "bilancio_vecchio"}
CAMPI_TESTO = {"ticker", "date", "index", "sector", "industry", "country", "currency",
               "longName", "shortName", "quoteType", "financialCurrency"}


# ----------------------------- utilità -----------------------------


def env_int(nome, default):
    return sse.env_int(nome, default)


def num(x):
    """Numero da numero o stringa; None se manca, non è un numero o è NaN."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def in_usd(valore, valuta):
    v = num(valore)
    fx = FX_USD.get(valuta or "USD")
    return v * fx if v is not None and fx else None


def codice_eodhd(ticker):
    """Codice EODHD (es. MA.US, ASML.AS, 0700.HK) o None se la borsa non è coperta."""
    t = str(ticker or "").strip()
    if not t:
        return None
    radice, suf = t.rsplit(".", 1) if "." in t else (t, "")
    suf = suf.upper()
    if suf not in BORSE or not radice:
        return None
    return f"{radice}.{BORSE[suf]}"


def mese_indice(d):
    """Indice del mese di chiusura, come nel backtest (tollera gli anni
    fiscali di 52-53 settimane)."""
    try:
        dt = datetime.strptime(str(d)[:10], "%Y-%m-%d")
    except ValueError:
        return None
    o = dt.toordinal() + 16
    dt = date.fromordinal(o)
    return dt.year * 12 + dt.month - 2


def leggi_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def leggi_tickers(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for riga in f:
            t = riga.split("#")[0].strip()
            if t:
                out.append(t)
    return out


# ----------------------------- dati Yahoo -----------------------------


def carica_info(path=None):
    """Dati .info per ticker. Ordine: path esplicito (json o csv.gz), poi
    partials/info-*.json (job di merge), poi l'ultima fotografia
    snapshots/universo/*.csv.gz. Ritorna (dizionario, fonte)."""
    if path:
        return _leggi_info_file(path), path
    pdir = os.environ.get("PARTIALS_DIR", "partials")
    info = {}
    for fp in sorted(glob.glob(os.path.join(pdir, "info-*.json"))):
        d = leggi_json(fp)
        if isinstance(d, dict):
            info.update(d)
    if info:
        return info, f"{pdir}/info-*.json"
    foto = sorted(glob.glob(os.path.join("snapshots", "universo", "*.csv.gz")))
    if foto:
        return _leggi_info_file(foto[-1]), foto[-1]
    return {}, None


def _leggi_info_file(path):
    if path.endswith(".json"):
        d = leggi_json(path)
        return d if isinstance(d, dict) else {}
    opener = gzip.open if path.endswith(".gz") else open
    out = {}
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = r.get("ticker")
            if not t:
                continue
            out[t] = {k: (v if k in CAMPI_TESTO else num(v)) if v != "" else None
                      for k, v in r.items()}
    return out


def settore_ammesso(info, eccezione=True):
    """(ammesso, eccezione_settore): esclusioni del GARP, con pagamenti e dati
    finanziari riammessi se eccezione è attiva."""
    sector = info.get("sector")
    if not sector:
        return False, None
    if sector not in base.EXCLUDED_SECTORS:
        return True, None
    if eccezione and (info.get("industry") or "").strip() in ECCEZIONE_INDUSTRIE:
        return True, "pagamenti e dati finanziari"
    return False, None


def primo_filtro(info_all, eccezione=True, roe_min=None, solo=None, scartati=None,
                 gm_min=None):
    """Candidati da scaricare: azioni, settore ammesso, capitalizzazione >= 5
    Mld$, ROE Yahoo oltre la soglia OPPURE margine lordo Yahoo oltre la sua
    soglia (dalla revisione del 08/11/2026; solo se Yahoo dà grossMargins).
    solo = insieme di ticker (prove locali). scartati = dizionario da riempire
    con il motivo di ogni scarto. Ritorna (candidati, contatori): "roe" conta
    gli scartati da questa regola (né ROE né margine lordo sopra soglia),
    "solo_margine_lordo" i candidati entrati soltanto per il margine lordo."""
    roe_min = CRITERIA["prefiltro_roe_min"] if roe_min is None else roe_min
    gm_min = CRITERIA["prefiltro_margine_lordo_min"] if gm_min is None else gm_min
    cont = {"universo": len(info_all), "non_azioni": 0, "settore": 0, "capitalizzazione": 0,
            "roe": 0, "solo_margine_lordo": 0}
    scartati = {} if scartati is None else scartati
    out = []
    for t, info in info_all.items():
        if solo is not None and t not in solo:
            scartati[t] = "non fra i ticker richiesti (prova locale)"
            continue
        info = info or {}
        qt = info.get("quoteType")
        if qt and qt != "EQUITY":
            cont["non_azioni"] += 1
            scartati[t] = "non è un'azione"
            continue
        ok, ecc = settore_ammesso(info, eccezione)
        if not ok:
            cont["settore"] += 1
            scartati[t] = f"settore escluso ({info.get('sector') or 'n/d'})"
            continue
        mcap_usd = in_usd(info.get("marketCap"), info.get("currency"))
        if mcap_usd is None or mcap_usd < CRITERIA["mcap_min_usd"]:
            cont["capitalizzazione"] += 1
            scartati[t] = ("capitalizzazione non nota" if mcap_usd is None else
                           f"capitalizzazione {mcap_usd / 1e9:.1f} Mld$, sotto 5".replace(".", ","))
            continue
        roe = num(info.get("returnOnEquity"))
        gm = num(info.get("grossMargins"))
        roe_ok = roe is not None and roe > roe_min
        gm_ok = gm is not None and gm > gm_min
        if not (roe_ok or gm_ok):
            cont["roe"] += 1
            scartati[t] = (("ROE Yahoo non calcolabile (patrimonio negativo o dato mancante)"
                            if roe is None else f"ROE Yahoo {roe * 100:.0f}%, non oltre "
                            f"{roe_min * 100:.0f}%")
                           + (", margine lordo non noto" if gm is None else
                              f", margine lordo {gm * 100:.0f}%, non oltre {gm_min * 100:.0f}%"))
            continue
        if not roe_ok:
            cont["solo_margine_lordo"] += 1
        out.append({"ticker": t, "info": info, "mcap_usd": mcap_usd, "eccezione_settore": ecc})
    cont["candidati"] = len(out)
    return out, cont


def _casa(c):
    """True se il ticker è la quotazione di casa (USA senza suffisso per le
    americane, con suffisso di borsa per le altre)."""
    usa = (c["info"].get("country") == "United States")
    return usa == ("." not in c["ticker"])


def raggruppa(candidati):
    """Una voce per società: le quotazioni con lo stesso nome sono unite.
    Principale = quotazione coperta da EODHD, poi di casa, poi la più grande."""
    gruppi, senza_nome = {}, []
    for c in candidati:
        k = norm_nome(c["info"].get("longName") or c["info"].get("shortName"))
        if k:
            gruppi.setdefault(k, []).append(c)
        else:
            senza_nome.append([c])
    out = []
    for g in list(gruppi.values()) + senza_nome:
        g = sorted(g, key=lambda c: (codice_eodhd(c["ticker"]) is None, not _casa(c),
                                     -(c["mcap_usd"] or 0), c["ticker"]))
        p = dict(g[0])
        p["altri_ticker"] = sorted(c["ticker"] for c in g[1:])
        # per il download: la prima quotazione coperta da EODHD
        p["codice_eodhd"] = next((codice_eodhd(c["ticker"]) for c in g
                                  if codice_eodhd(c["ticker"])), None)
        out.append(p)
    return out


# ----------------------------- EODHD -----------------------------


def scarica(sessione, codice, contatore, tentativi=3):
    """Bilanci EODHD del titolo. Ritorna (dati o None, esito)."""
    esito = "errore_rete"
    for i in range(tentativi):
        contatore.attendi()
        if not contatore.prenota():
            return None, "non_scaricato"
        try:
            r = sessione.get(f"{sse.BASE_URL}/fundamentals/{codice}",
                             params={"fmt": "json", "filter": FILTRO, **sse.token_params()},
                             timeout=sse.TIMEOUT_HTTP)
        except requests.RequestException:
            time.sleep(2 * (i + 1))
            continue
        if r.status_code == 200:
            try:
                return r.json(), "ok"
            except ValueError:
                return None, "risposta_non_valida"
        if r.status_code == 404:
            return None, "non_trovato"
        if r.status_code in (401, 402, 403):
            with contatore.lock:
                contatore.stop = contatore.stop or f"EODHD ha risposto {r.status_code} (chiave o limite)"
            return None, f"http_{r.status_code}"
        if r.status_code == 429:
            esito = "limite_frequenza"
            attesa = 10 * (i + 1)
            try:
                attesa = max(attesa, int(float(r.headers.get("Retry-After") or 0)))
            except (TypeError, ValueError):
                pass
            contatore.rallenta(attesa)
            continue
        esito = "errore_rete"
        time.sleep(2 * (i + 1))
    return None, esito


def _righe(tab):
    """Righe di una tabella EODHD (dizionario data -> voci) per mese di
    chiusura; a parità di mese resta la più completa."""
    out = {}
    for k, v in (tab or {}).items() if isinstance(tab, dict) else []:
        if not isinstance(v, dict):
            continue
        m = mese_indice(v.get("date") or k)
        if m is None:
            continue
        n = sum(1 for x in v.values() if num(x) is not None)
        if m not in out or n > out[m][0]:
            out[m] = (n, v)
    return {m: v for m, (n, v) in out.items()}


def _debito_cassa(b):
    """Debito e cassa di una riga di stato patrimoniale, come nel backtest."""
    debt = num(b.get("shortLongTermDebtTotal"))
    if debt is None:
        st = num(b.get("shortTermDebt"))
        st = num(b.get("shortLongTermDebt")) if st is None else st
        lt = num(b.get("longTermDebt"))
        lt = num(b.get("longTermDebtTotal")) if lt is None else lt
        debt = (st or 0.0) + (lt or 0.0)
    cash = num(b.get("cashAndShortTermInvestments"))
    if cash is None:
        cash = num(b.get("cash"))
    return debt, cash


def _ricavi(v):
    return num(v.get("totalRevenue"))


def azioni_oltre_soglia(fin_b, oggi, soglia=None):
    """Sì/no: azioni in circolazione (commonStockSharesOutstanding dello stato
    patrimoniale EODHD, trimestrale e se manca annuale) cresciute oltre la
    soglia (25%) in un anno. Ultimo dato contro il più recente fra 12 e 18
    mesi prima, come nel backtest. None se mancano i dati, se l'ultimo ha più
    di 15 mesi, o se il rapporto sembra un frazionamento (multiplo semplice) o
    un errore di unità (oltre 4,5 volte o sotto un quinto)."""
    soglia = CRITERIA["diluizione_1a_soglia"] if soglia is None else soglia
    sh = {}
    for tab in ("yearly", "quarterly"):      # il trimestrale vale più dell'annuale
        for m, v in _righe((fin_b or {}).get(tab)).items():
            x = num(v.get("commonStockSharesOutstanding"))
            if x is not None and x > 0:
                sh[m] = x
    if not sh:
        return None
    m1 = max(sh)
    if mese_indice(oggi.isoformat()) - m1 > CRITERIA["bilancio_annuale_eta_max_mesi"]:
        return None
    prima = [m for m in sh if m1 - 18 <= m <= m1 - 12]
    if not prima:
        return None
    rapporto = sh[m1] / sh[max(prima)]
    if rapporto > 4.5 or rapporto < 0.2:
        return None
    oltre = rapporto - 1 > soglia
    if oltre and any(abs(rapporto / k - 1) <= TOLLERANZA_FRAZIONAMENTO
                     for k in RAPPORTI_FRAZIONAMENTO):
        return None
    return oltre


def derivati(dati, oggi=None):
    """Dai bilanci EODHD ai soli valori derivati (vedi docstring). Ritorna un
    dizionario con 'esito' e, se 'ok', gli esiti delle regole."""
    oggi = oggi or date.today()
    fin_i = (dati or {}).get("Financials::Income_Statement") or {}
    fin_b = (dati or {}).get("Financials::Balance_Sheet") or {}
    iy = {m: v for m, v in _righe(fin_i.get("yearly")).items()
          if _ricavi(v) is not None or num(v.get("netIncome")) is not None}
    if not iy:
        return {"esito": "senza_bilanci"}
    m0 = max(iy)
    out = {"esito": "ok", "ultimo_anno_fiscale": str(iy[m0].get("date") or "")[:10] or None}
    if mese_indice(oggi.isoformat()) - m0 > CRITERIA["bilancio_annuale_eta_max_mesi"]:
        out["esito"] = "bilancio_vecchio"
    bal = _righe(fin_b.get("quarterly"))
    for m, v in _righe(fin_b.get("yearly")).items():
        if m not in bal or (sum(1 for x in v.values() if num(x) is not None)
                            > sum(1 for x in bal[m].values() if num(x) is not None)):
            bal[m] = v

    # ---- 6 anni consecutivi (y0 = ultimo bilancio annuale)
    anni = []
    for k in range(6):
        v = iy.get(m0 - 12 * k)
        if v is None:
            break
        ni = num(v.get("netIncome"))
        if ni is None:
            ni = num(v.get("netIncomeApplicableToCommonShares"))
        rev = _ricavi(v)
        gp = num(v.get("grossProfit"))
        if gp is None and rev is not None and num(v.get("costOfRevenue")) is not None:
            gp = rev - num(v.get("costOfRevenue"))
        b = bal.get(m0 - 12 * k) or {}
        anni.append({"rev": rev, "ni": ni, "op": num(v.get("operatingIncome")), "gp": gp,
                     "eq": num(b.get("totalStockholderEquity"))})

    def anno(k, campo):
        return anni[k][campo] if k < len(anni) else None

    roe, opm, gmy, gro = [], [], [], []
    for k in range(5):
        eq, ni, rev = anno(k, "eq"), anno(k, "ni"), anno(k, "rev")
        roe.append(ni / eq if (ni is not None and eq is not None and eq > 0) else None)
        op = anno(k, "op")
        opm.append(op / rev if (op is not None and rev is not None and rev > 0) else None)
        gp = anno(k, "gp")
        g = gp / rev if (gp is not None and rev is not None and rev > 0) else None
        gmy.append(g if g is not None and -1 <= g <= 0.999 else None)
        r1 = anno(k + 1, "rev")
        gro.append(rev / r1 - 1 if (rev is not None and r1 is not None and r1 != 0) else None)

    storico = (out["esito"] == "ok" and all(x is not None for x in roe)
               and all(x is not None for x in opm) and all(x is not None for x in gro))
    if out["esito"] == "ok" and len(anni) < 6:
        out["esito"] = "storico_corto"
    r0, r5 = anno(0, "rev"), anno(5, "rev")
    cagr5 = ((r0 / r5) ** (1 / 5) - 1) if (r0 is not None and r5 is not None
                                           and r0 > 0 and r5 > 0) else None
    n_calo = sum(1 for g in gro if g is not None and g < 0)
    opm_ok = [x for x in opm if x is not None]
    stab = (opm[0] is not None and bool(opm_ok)
            and opm[0] >= sum(opm_ok) / len(opm_ok) - CRITERIA["stabilita_margine_punti"])
    if gmy[0] is None or gmy[4] is None:
        gm_st = None
    else:
        gm_st = gmy[0] >= gmy[4] - CRITERIA["margine_lordo_calo_max_punti"]

    # ---- debito netto su utile operativo degli ultimi 12 mesi
    debt = cash = None
    if bal:
        mb = max(bal)
        debt, cash = _debito_cassa(bal[mb])
    iq = _righe(fin_i.get("quarterly"))
    opi = None
    if iq and max(iq) >= m0:
        q0 = max(iq)
        for passo, n in ((3, 4), (6, 2)):
            vals = [num((iq.get(q0 - passo * j) or {}).get("operatingIncome")) for j in range(n)]
            if all(v is not None for v in vals):
                opi = sum(vals)
                break
    if opi is None:
        opi = anno(0, "op")
    nd = (debt or 0.0) - (cash or 0.0)
    debito_basso = nd <= 0 or (opi is not None and opi > 0
                               and nd / opi <= CRITERIA["debito_netto_utile_operativo_max"])

    n_roe = sum(1 for x in roe if x is not None and x >= CRITERIA["roe_min"])
    n_mar = sum(1 for x in opm if x is not None and x >= CRITERIA["margine_operativo_min"])
    crescita_ok = cagr5 is not None and cagr5 >= CRITERIA["ricavi_cagr5_min"]
    calo_ok = n_calo <= CRITERIA["anni_in_calo_max"]
    base_ok = storico and crescita_ok and calo_ok and debito_basso
    out.update({
        "storico_5_anni": storico,
        "crescita_ricavi_ok": crescita_ok,
        "anni_in_calo": n_calo,
        "anni_in_calo_ok": calo_ok,
        "debito_basso": debito_basso,
        "cassa_netta": (debt is not None or cash is not None) and nd <= 0,
        "anni_roe_15": n_roe,
        "roe_stabile": n_roe >= CRITERIA["anni_roe_min"],
        "anni_margine_20": n_mar,
        "margini_alti": n_mar >= CRITERIA["anni_margine_min"],
        "margine_non_in_calo": bool(stab),
        "margine_lordo_stabile": gm_st,
        "q1_bilanci": bool(base_ok and n_roe >= CRITERIA["anni_roe_min"] and stab),
        "q2_bilanci": bool(base_ok and n_mar >= CRITERIA["anni_margine_min"] and stab
                           and gm_st is not False),
        # solo sì/no (licenza): per la guardia di sicurezza della lista
        "azioni_oltre_25_1a": azioni_oltre_soglia(fin_b, oggi),
    })
    return out


# ----------------------------- cache dei derivati -----------------------------


def leggi_cache(path):
    d = leggi_json(path)
    if not isinstance(d, dict):
        return {}
    t = d.get("titoli")
    return t if isinstance(t, dict) else {}


def eta_giorni(voce, oggi):
    try:
        return (oggi - date.fromisoformat(str(voce.get("data"))[:10])).days
    except (TypeError, ValueError):
        return 10 ** 6


def turno(ticker):
    """Giorno feriale del rinnovo (0 = lunedì … 4 = venerdì), fisso per ogni
    società: i rinnovi si spargono sulla settimana."""
    return zlib.crc32(str(ticker).encode("utf-8")) % GIORNI_TURNO


def da_rinnovare(voce, ticker, oggi, rinnovo, rinnovo_non_trovato):
    """True se il dato in cache va riscaricato stanotte (vedi docstring del
    modulo): nel giorno del turno se ha almeno rinnovo - 4 giorni, in ogni
    caso dopo rinnovo + 2 giorni (turno saltato)."""
    eta = eta_giorni(voce, oggi)
    if voce.get("esito") == "non_trovato":
        return eta >= rinnovo_non_trovato
    if rinnovo < 7:                 # rinnovo più frequente di una settimana: solo l'età
        return eta >= rinnovo
    if eta >= rinnovo + 2:
        return True
    return oggi.weekday() == turno(ticker) and eta >= rinnovo - 4


def da_scaricare(gruppi, cache, oggi, rinnovo, rinnovo_non_trovato):
    """Società da (ri)scaricare, nell'ordine: mai scaricate, più vecchie,
    più grandi."""
    out = []
    for g in gruppi:
        if not g.get("codice_eodhd"):
            continue
        v = cache.get(g["ticker"])
        if v is None or v.get("codice_eodhd") != g["codice_eodhd"]:
            out.append((0, -10 ** 6, -(g["mcap_usd"] or 0), g))
            continue
        if da_rinnovare(v, g["ticker"], oggi, rinnovo, rinnovo_non_trovato):
            out.append((1, -eta_giorni(v, oggi), -(g["mcap_usd"] or 0), g))
    out.sort(key=lambda x: x[:3])
    return [x[3] for x in out]


# ----------------------------- valutazione -----------------------------


def _anni(n):
    return f"{n} anno" if n == 1 else f"{n} anni"


def valuta(g, der, eccezione=True):
    """Riga del report per una società: esiti delle regole Q1, Q2, Q3 con i
    dati di stanotte (capitalizzazione, PEG, settore) e i derivati EODHD."""
    info = g["info"]
    peg, peg_src = base.compute_peg({k: num(v) if k in ("trailingPegRatio", "trailingPE",
                                                         "forwardPE", "earningsGrowth") else v
                                     for k, v in info.items()})
    peg_ok = not (peg is not None and peg > CRITERIA["peg_max"])
    mcap_ok = g["mcap_usd"] is not None and g["mcap_usd"] >= CRITERIA["mcap_min_usd"]
    sett_ok, _ = settore_ammesso(info, eccezione)
    price = num(info.get("currentPrice")) or num(info.get("regularMarketPrice"))
    high = num(info.get("fiftyTwoWeekHigh"))
    der = der or {}
    q1 = bool(der.get("q1_bilanci")) and mcap_ok and peg_ok and sett_ok
    q2 = bool(der.get("q2_bilanci")) and mcap_ok and peg_ok and sett_ok
    punteggio = sum([q1, q2, der.get("anni_roe_15") == 5, der.get("anni_margine_20") == 5,
                     der.get("anni_in_calo") == 0, bool(der.get("cassa_netta"))])
    motivi = []
    if der.get("esito") != "ok":
        motivi.append({"senza_bilanci": "EODHD senza bilanci annuali",
                       "storico_corto": "meno di 6 bilanci annuali",
                       "bilancio_vecchio": "ultimo bilancio annuale oltre 15 mesi fa",
                       "non_trovato": "EODHD non conosce il titolo"}.get(der.get("esito"),
                                                                         "dati EODHD mancanti"))
    else:
        if not der.get("storico_5_anni"):
            motivi.append("5 anni non completi (es. patrimonio negativo)")
        if not der.get("crescita_ricavi_ok"):
            motivi.append("ricavi sotto +8% l'anno in 5 anni")
        if not der.get("anni_in_calo_ok"):
            motivi.append(f"ricavi in calo in {_anni(der.get('anni_in_calo'))} su 5")
        if not der.get("debito_basso"):
            motivi.append("debito netto oltre 2,5 volte l'utile operativo")
        if not der.get("margine_non_in_calo"):
            motivi.append("margine operativo dell'ultimo anno sotto la media dei 5 anni")
        # le due strade, Q1 (ROE) e Q2 (margini), solo se sono chiuse tutte e due
        if not der.get("q1_bilanci") and not der.get("q2_bilanci"):
            if not der.get("roe_stabile"):
                motivi.append(f"Q1: ROE >= 15% solo in {_anni(der.get('anni_roe_15'))} su 5")
            if not der.get("margini_alti"):
                motivi.append(f"Q2: margine operativo >= 20% solo in "
                              f"{_anni(der.get('anni_margine_20'))} su 5")
            elif der.get("margine_lordo_stabile") is False:
                motivi.append("Q2: margine lordo sceso di oltre 2 punti in 4 anni")
    if not peg_ok:
        motivi.append(f"PEG {peg:.1f} oltre 3".replace(".", ","))
    if not mcap_ok:
        motivi.append("capitalizzazione sotto 5 Mld$")
    if not sett_ok:
        motivi.append("settore escluso")
    return {
        "ticker": g["ticker"],
        "altri_ticker": g.get("altri_ticker") or [],
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "country": info.get("country"),
        "currency": info.get("currency"),
        "market_cap": num(info.get("marketCap")),
        "market_cap_usd": g["mcap_usd"],
        "price": price,
        "pct_of_52w_high": (price / high) if (price and high and high > 0) else None,
        "roe_yahoo": num(info.get("returnOnEquity")),
        "peg": peg,
        "peg_source": peg_src,
        "eccezione_settore": g.get("eccezione_settore"),
        "codice_eodhd": g.get("codice_eodhd"),
        "dati_eodhd_del": der.get("data"),
        "esito_eodhd": der.get("esito"),
        "ultimo_anno_fiscale": der.get("ultimo_anno_fiscale"),
        "q1": q1,
        "q2": q2,
        "q3": q1 or q2,
        "passed": q1 or q2,
        "punteggio": punteggio,
        "roe_stabile": der.get("roe_stabile"),
        "anni_roe_15": der.get("anni_roe_15"),
        "margini_alti": der.get("margini_alti"),
        "anni_margine_20": der.get("anni_margine_20"),
        "margine_non_in_calo": der.get("margine_non_in_calo"),
        "margine_lordo_stabile": der.get("margine_lordo_stabile"),
        "crescita_ricavi_ok": der.get("crescita_ricavi_ok"),
        "anni_in_calo": der.get("anni_in_calo"),
        "debito_basso": der.get("debito_basso"),
        "cassa_netta": der.get("cassa_netta"),
        "peg_ok": peg_ok,
        "storico_5_anni": der.get("storico_5_anni"),
        "motivi_no": [] if (q1 or q2) else motivi,
        # sì/no, non esclude qui: lo usa la guardia della lista da radiografare
        "azioni_oltre_25_1a": der.get("azioni_oltre_25_1a"),
    }


# ----------------------------- report -----------------------------


def _mld(x):
    return f"{x / 1e9:.0f}" if isinstance(x, (int, float)) else "n/d"


def _sn(x):
    return "sì" if x is True else ("no" if x is False else "n/d")


def esito_seguiti(seguiti, righe, senza_dati, scartati):
    """Esito di ogni titolo seguito (watchlist e schede fatte): in lista, no
    (con i motivi), senza dati EODHD o fuori dal primo filtro (con il motivo)."""
    per_t, per_t_senza = {}, {}
    for r in righe:
        for t in [r["ticker"], *r["altri_ticker"]]:
            per_t[t] = r
    for s_ in senza_dati:
        for t in [s_["ticker"], *s_.get("altri_ticker", [])]:
            per_t_senza[t] = s_
    out = []
    for t in seguiti:
        r = per_t.get(t)
        if r is not None and r["passed"]:
            out.append({"ticker": t, "esito": "in lista",
                        "regole": [k.upper() for k in ("q1", "q2") if r[k]], "motivi": []})
        elif r is not None:
            out.append({"ticker": t, "esito": "no", "motivi": r["motivi_no"]})
        elif t in per_t_senza:
            out.append({"ticker": t, "esito": "senza dati EODHD",
                        "motivi": [per_t_senza[t]["motivo"]]})
        else:
            out.append({"ticker": t, "esito": "fuori dal primo filtro",
                        "motivi": [scartati.get(t, "non nell'universo di stanotte")]})
    return out


def scrivi_report(righe, senza_dati, cont, riep, fonte, out_dir, oggi, started,
                  seguiti=(), eccezione=True, scartati=None):
    passed = sorted([r for r in righe if r["passed"]],
                    key=lambda r: (-r["punteggio"], -(r["market_cap_usd"] or 0), r["ticker"]))
    bocciati = sorted([r for r in righe if not r["passed"]],
                      key=lambda r: -(r["market_cap_usd"] or 0))
    prev = base.previous_passed(out_dir)
    tick = {r["ticker"] for r in passed}
    report = {
        "screener": "qualita",
        "date": oggi.isoformat(),
        "generated_at_utc": started.isoformat(),
        "duration_seconds": round((datetime.now(timezone.utc) - started).total_seconds()),
        "criteria": CRITERIA,
        "eccezione_industrie": list(ECCEZIONE_INDUSTRIE) if eccezione else [],
        "regola": "Q3 = Q1 oppure Q2. Base: capitalizzazione >= 5 Mld$, ricavi +8% l'anno in 5 "
                  "anni con al massimo 1 anno in calo, debito netto <= 2,5 volte l'utile "
                  "operativo (o cassa netta), PEG <= 3 o non calcolabile. Q1: ROE >= 15% in "
                  "almeno 4 anni su 5 e margine operativo non sotto la media dei 5 anni di "
                  "oltre 2 punti. Q2: margine operativo >= 20% in almeno 4 anni su 5, stessa "
                  "stabilità, margine lordo non sceso di oltre 2 punti in 4 anni. Settori: "
                  "esclusioni del GARP" + (", con pagamenti e dati finanziari riammessi." if eccezione
                                           else "."),
        "nota": "Lista difensiva: nel backtest 2012-26 non batte il mercato delle grandi "
                "(+0,6 punti l'anno; +3,4 nel 2018-26) ma oscilla meno e ha meno crolli. "
                "Ha senso accanto al core GARP, non al suo posto. In Europa non ha funzionato.",
        "punteggio_uso": "Solo per ordinare (0-6: Q1, Q2, ROE >= 15% in tutti e 5 gli anni, "
                         "margine >= 20% in tutti e 5, nessun anno di ricavi in calo, cassa "
                         "netta). Non è stato provato nel backtest.",
        "licenza": "Dai bilanci EODHD sono salvati solo valori derivati (esiti sì/no, anni "
                   "sopra soglia, punteggio, data dell'ultimo bilancio, sì/no azioni oltre "
                   "+25% in un anno): nessun importo.",
        "fonte_info": fonte,
        "primo_filtro": cont,
        "societa_valutate": len(righe),
        "senza_dati_count": len(senza_dati),
        "senza_dati": senza_dati,
        "passed_count": len(passed),
        "q1_count": sum(1 for r in passed if r["q1"]),
        "q2_count": sum(1 for r in passed if r["q2"]),
        "new_today": sorted(tick - prev),
        "dropped_since_yesterday": sorted(prev - tick),
        "eodhd": riep,
        "seguiti": esito_seguiti(seguiti, righe, senza_dati, scartati or {}),
        "passed": passed,
        "bocciati": [{k: r[k] for k in ("ticker", "name", "market_cap_usd", "motivi_no",
                                        "esito_eodhd")} for r in bocciati],
    }
    os.makedirs(out_dir, exist_ok=True)
    for p in (os.path.join(out_dir, f"{oggi.isoformat()}.json"),
              os.path.join(out_dir, "latest.json")):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1, ensure_ascii=False, default=str)

    L = [f"# Qualità durevole — {oggi.isoformat()}", "",
         "> **Lista difensiva, non per battere il mercato.** Nel backtest 2012-26 queste "
         "società hanno reso come il mercato delle grandi (+0,6 punti l'anno; +3,4 nel "
         "2018-26), ma con meno oscillazioni e meno crolli. Hanno senso accanto al core GARP "
         "(metà e metà nel passato: +4,9 punti l'anno sull'universo). In Europa non ha "
         "funzionato.", ""]
    if riep.get("interrotto"):
        L += [f"> ⚠️ Download EODHD interrotto: {riep['interrotto']}. Per le società senza "
              "dati recenti l'esito resta quello dell'ultimo download (o manca).", ""]
    L += [f"Candidate dopo il primo filtro (cap. ≥ 5 Mld$, settore ammesso, ROE Yahoo > 15% "
          f"o margine lordo > 50%): {cont.get('candidati', 0)} (solo per il margine lordo: "
          f"{cont.get('solo_margine_lordo', 0)}) | Società valutate: {len(righe)} | "
          f"**In lista: {len(passed)}** (Q1 {report['q1_count']}, Q2 {report['q2_count']}) | "
          f"Nuove: {', '.join(report['new_today']) or '—'} | "
          f"Uscite: {', '.join(report['dropped_since_yesterday']) or '—'} | "
          f"Senza dati EODHD: {len(senza_dati)}", "",
          "| # | Ticker | Nome | Paese | Cap. (Mld$) | Q1 ROE | Q2 margini | Punt. | "
          "Anni ROE ≥15% | Anni margine ≥20% | Anni ricavi in calo | Cassa netta | Note |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(passed, 1):
        note = []
        if r["eccezione_settore"]:
            note.append(r["eccezione_settore"])
        if r["altri_ticker"]:
            note.append("anche " + ", ".join(r["altri_ticker"]))
        if r.get("azioni_oltre_25_1a"):
            note.append("⚠ azioni oltre +25% in un anno")
        L.append(f"| {i} | {r['ticker']} | {(r['name'] or '')[:30]} | {r['country'] or ''} | "
                 f"{_mld(r['market_cap_usd'])} | {'✓' if r['q1'] else '–'} | "
                 f"{'✓' if r['q2'] else '–'} | {r['punteggio']} | {r['anni_roe_15']}/5 | "
                 f"{r['anni_margine_20']}/5 | {r['anni_in_calo']} | {_sn(r['cassa_netta'])} | "
                 f"{'; '.join(note) or '—'} |")
    if not passed:
        L.append("| — | nessuna | | | | | | | | | | | |")
    if report["seguiti"]:
        L += ["", "## Titoli seguiti (watchlist e schede fatte)", ""]
        for s_ in report["seguiti"]:
            if s_["esito"] == "in lista":
                L.append(f"- {s_['ticker']}: **in lista** ({' e '.join(s_['regole'])})")
            else:
                L.append(f"- {s_['ticker']}: {s_['esito']} — " + ("; ".join(s_["motivi"]) or "n/d"))
    if senza_dati:
        L += ["", f"## Senza dati EODHD ({len(senza_dati)})", "",
              ", ".join(f"{s['ticker']} ({s['motivo']})" for s in senza_dati[:80])
              + (" …" if len(senza_dati) > 80 else "")]
    L += ["", f"Crediti EODHD usati stanotte: {riep.get('crediti_usati', 0)} "
          f"({riep.get('scaricati', 0)} società; tetto {riep.get('tetto')}, riserva "
          f"{riep.get('riserva')}). Fonte dati Yahoo: {fonte}.",
          "", "Punteggio: solo per ordinare (0-6), non provato nel backtest. Bilanci "
          "pubblicati (non i dati \"rettificati\" delle società): chi ha patrimonio negativo "
          "per i riacquisti di azioni (Moody's, AutoZone) resta fuori. Il primo filtro (ROE di "
          "Yahoo oltre il 15% o margine lordo oltre il 50%) serve a risparmiare crediti e può "
          "perdere qualche società che passerebbe solo con i margini (Q2) con margine lordo "
          "fino al 50%."]
    with open(os.path.join(out_dir, "latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return report


def scrivi_cache(path, cache, oggi):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"nota": "Solo valori derivati dai bilanci EODHD (esiti sì/no, anni sopra "
                           "soglia, data dell'ultimo bilancio annuale): nessun importo.",
                   "aggiornato": oggi.isoformat(),
                   "titoli": {k: cache[k] for k in sorted(cache)}},
                  f, indent=0, ensure_ascii=False, sort_keys=False)


# ----------------------------- main -----------------------------


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--tickers", help="solo questi ticker (prove locali), separati da virgola")
    ap.add_argument("--info", help="file .info (json o csv.gz) al posto della cache del GARP")
    ap.add_argument("--out-dir", default=RESULTS_DIR)
    ap.add_argument("--senza-download", action="store_true", help="usa solo la cache dei derivati")
    args = ap.parse_args(argv)
    started = datetime.now(timezone.utc)
    oggi = date.today()
    eccezione = os.environ.get("QUALITA_ECCEZIONE_PAGAMENTI", "1").strip() != "0"
    cap = env_int("QUALITA_CAP_CREDITI", 15000)
    riserva = env_int("QUALITA_RESIDUO_MIN", 5000)
    tempo_max = env_int("QUALITA_TEMPO_MAX_S", 900)
    rinnovo = env_int("QUALITA_RINNOVO_GIORNI", 7)
    scadenza = env_int("QUALITA_SCADENZA_GIORNI", 45)

    info_all, fonte = carica_info(args.info)
    if not info_all:
        print("ERRORE: nessun dato .info (partials/info-*.json o snapshots/universo)",
              file=sys.stderr)
        sys.exit(1)
    solo = {t.strip() for t in args.tickers.split(",") if t.strip()} if args.tickers else None
    scartati = {}
    candidati, cont = primo_filtro(info_all, eccezione, solo=solo, scartati=scartati)
    gruppi = raggruppa(candidati)
    print(f"Qualità: {len(info_all)} titoli da {fonte}; primo filtro {len(candidati)} "
          f"candidati, {len(gruppi)} società")

    cache_path = os.path.join(args.out_dir, CACHE_FILE)
    cache = leggi_cache(cache_path)
    todo = [] if args.senza_download else da_scaricare(gruppi, cache, oggi, rinnovo, 28)
    riep = {"tetto": cap, "riserva": riserva, "da_scaricare": len(todo), "scaricati": 0,
            "crediti_usati": 0, "esiti": {}, "interrotto": None, "residuo_inizio": None,
            "residuo_fine": None}
    if todo:
        sess = requests.Session()
        cont_e = sse.Contatore(cap, riserva, sess, tempo_max)
        res, _ = cont_e.residuo()
        riep["residuo_inizio"] = res
        if res is None:
            riep["interrotto"] = "contatore /api/user non leggibile"
        elif res < riserva:
            riep["interrotto"] = f"crediti rimasti {res} sotto la riserva {riserva}"
        else:
            # il contatore si rilegge ogni 200 chiamate: il tetto di stanotte non
            # supera i crediti che restano sopra la riserva
            cont_e.cap = min(cap, res - riserva)
            riep["tetto_effettivo"] = cont_e.cap
            def lavoro(g):
                dati, esito = scarica(sess, g["codice_eodhd"], cont_e)
                d = derivati(dati, oggi) if esito == "ok" else {"esito": esito}
                return g, d

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                futs = [ex.submit(lavoro, g) for g in todo]
                for fut in as_completed(futs):
                    try:
                        g, d = fut.result()
                    except Exception as e:
                        print(f"[WARN] errore su un titolo ({type(e).__name__})",
                              file=sys.stderr)
                        continue
                    riep["esiti"][d["esito"]] = riep["esiti"].get(d["esito"], 0) + 1
                    if d["esito"] in ESITI_DA_TENERE:
                        d.update({"data": oggi.isoformat(), "codice_eodhd": g["codice_eodhd"]})
                        cache[g["ticker"]] = d
            riep["interrotto"] = cont_e.stop
            riep["scaricati"] = cont_e.chiamate
            riep["crediti_usati"] = cont_e.chiamate * sse.CREDITI_PER_TITOLO
            riep["risposte_429"] = cont_e.n_429
            riep["residuo_fine"], _ = cont_e.residuo()
        scrivi_cache(cache_path, cache, oggi)
        print(f"EODHD: {riep['scaricati']} chiamate, {riep['crediti_usati']} crediti, "
              f"esiti {riep['esiti']}" + (f", interrotto: {riep['interrotto']}"
                                           if riep["interrotto"] else ""))

    righe, senza_dati = [], []
    for g in gruppi:
        d = cache.get(g["ticker"])
        if d and d.get("codice_eodhd") != g.get("codice_eodhd"):
            d = None
        motivo = None
        if not g.get("codice_eodhd"):
            motivo = "borsa non coperta da EODHD"
        elif d is None:
            motivo = "non ancora scaricato"
        elif eta_giorni(d, oggi) > scadenza:
            motivo = f"dato EODHD oltre {scadenza} giorni"
        elif d.get("esito") == "non_trovato":
            motivo = "EODHD non conosce il titolo"
        elif d.get("esito") == "senza_bilanci":
            motivo = "EODHD senza bilanci annuali"
        if motivo:
            senza_dati.append({"ticker": g["ticker"], "altri_ticker": g.get("altri_ticker") or [],
                               "name": g["info"].get("longName") or g["info"].get("shortName"),
                               "motivo": motivo})
            continue
        righe.append(valuta(g, d, eccezione))
    seguiti = []
    for t in leggi_tickers("watchlist.txt") + leggi_tickers("schede_fatte.txt"):
        if t not in seguiti:
            seguiti.append(t)
    rep = scrivi_report(righe, senza_dati, cont, riep, fonte, args.out_dir, oggi, started,
                        seguiti=seguiti, eccezione=eccezione, scartati=scartati)
    print(f"Qualità durevole: {rep['passed_count']} in lista su {len(righe)} valutate "
          f"({len(senza_dati)} senza dati EODHD)")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
