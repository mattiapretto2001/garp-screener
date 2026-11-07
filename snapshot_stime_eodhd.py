#!/usr/bin/env python3
"""
Fotografia notturna delle stime degli analisti da EODHD (dal 08/11/2026)
=====================================================================
Ogni notte scarica i fondamentali EODHD (solo le sezioni Earnings::Trend e
Earnings::History) di un QUINTO dell'universo, a rotazione: ogni titolo ha un
gruppo fisso (0-4) e il gruppo del giorno è il giorno della settimana (lun = 0,
ven = 4), quindi ogni titolo è aggiornato una volta a settimana. In più, ogni
notte, i titoli "prioritari" (watchlist, schede fatte, promossi GARP, lista da
radiografare) se STIME_PRIORITARI non vale 0.

LICENZA: il repository è pubblico e il piano personale EODHD non permette di
ridistribuire i dati grezzi. Il file salva SOLO valori derivati calcolati qui:
  - revisione della stima EPS dell'anno in corso (0y) e del prossimo (+1y) a
    7, 30 e 90 giorni, in %;
  - trimestrali sopra / sotto le stime fra le ultime 4 e segno dell'ultima
    sorpresa;
  - crescita EPS attesa in % (stima anno prossimo su stima anno in corso);
  - numero di analisti;
  - date dell'ultima e della prossima trimestrale (fatti pubblici).
Nessuna stima, nessun EPS, nessun importo EODHD finisce nel file.

Uscita: snapshots/stime/<data>.csv.gz e snapshots/stime/ultimo_run.json.

Crediti: 10 per titolo (anche se il titolo non esiste). Tetto per notte
EODHD_CAP_CREDITI (default 25.000); tempo massimo EODHD_TEMPO_MAX_S (900 s).
Prima di partire, e ogni 200 titoli, legge il contatore /api/user: si ferma
se i crediti rimasti nel giorno scendono sotto EODHD_RESIDUO_MIN (default
20.000), per lasciare margine al lavoro manuale.

Chiave: su GitHub Actions è nel secret EODHD_API_TOKEN e va nel parametro
api_token. Se la variabile non c'è (sessioni in cui un proxy aggiunge la
chiave da sé) non si manda nulla.

Borse: suffisso Yahoo -> borsa EODHD (vedi BORSE). Milano, Tokyo, Hong Kong e
le altre non mappate sono saltate e contate.

Uso locale:  python snapshot_stime_eodhd.py --tickers AAPL,ASML.AS --out-dir /tmp/x
"""

import argparse
import csv
import glob
import gzip
import io
import json
import math
import os
import sys
import threading
import time
import traceback
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import requests

BASE_URL = "https://eodhd.com/api"
CREDITI_PER_TITOLO = 10
GRUPPI = 5
OUT_DIR = os.path.join("snapshots", "stime")
FILTRO = "Earnings::Trend,Earnings::History"
CONTROLLO_OGNI = 200          # titoli fra un controllo del contatore e l'altro
TIMEOUT_HTTP = 30

# suffisso Yahoo -> borsa EODHD ("" = USA)
BORSE = {
    "": "US", "DE": "XETRA", "PA": "PA", "AS": "AS", "MC": "MC", "L": "LSE", "SW": "SW",
    "ST": "ST", "CO": "CO", "HE": "HE", "OL": "OL", "BR": "BR", "TO": "TO", "TW": "TW",
    "KS": "KO", "AX": "AU",
}

# cambi indicativi verso USD, solo per ordinare per capitalizzazione
FX_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "GBp": 1.27, "CHF": 1.13, "SEK": 0.095,
          "NOK": 0.092, "DKK": 0.145, "JPY": 0.0066, "HKD": 0.128, "CAD": 0.72, "AUD": 0.65,
          "KRW": 0.00072, "TWD": 0.031}

CAMPI = [
    "date", "ticker", "codice_eodhd", "gruppo", "prioritario", "esito", "n_analisti",
    "rev_eps_0y_7g_pct", "rev_eps_0y_30g_pct", "rev_eps_0y_90g_pct",
    "rev_eps_1y_7g_pct", "rev_eps_1y_30g_pct", "rev_eps_1y_90g_pct",
    "crescita_eps_attesa_pct", "trend_0y_coerente",
    "n_trimestri_4t", "n_beat_4t", "n_miss_4t", "segno_ultima_sorpresa",
    "ultima_trimestrale", "prossima_trimestrale", "fine_anno_0y",
]


# ----------------------------- utilità -----------------------------


def env_int(nome, default):
    try:
        return int(float(os.environ.get(nome, "") or default))
    except ValueError:
        return default


def token_params():
    """api_token solo se la variabile d'ambiente c'è (GitHub Actions)."""
    tok = os.environ.get("EODHD_API_TOKEN", "").strip()
    return {"api_token": tok} if tok else {}


def codice_eodhd(ticker):
    """(codice EODHD o None, suffisso Yahoo). AAPL -> AAPL.US, SAP.DE -> SAP.XETRA."""
    t = str(ticker or "").strip()
    if not t:
        return None, ""
    radice, suf = (t.rsplit(".", 1) + [""])[:2] if "." in t else (t, "")
    suf = suf.upper()
    if suf not in BORSE or not radice:
        return None, suf or "?"
    return f"{radice}.{BORSE[suf]}", suf


def gruppo_di(ticker):
    """Gruppo fisso 0-4 del titolo (crc32: stabile fra macchine e versioni)."""
    return zlib.crc32(str(ticker).encode("utf-8")) % GRUPPI


def gruppo_del_giorno(oggi=None):
    return (oggi or date.today()).weekday() % GRUPPI


def f(x):
    """Numero da stringa EODHD ('8.8445') o None."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def var_pct(cur, prima):
    """Variazione % rispetto al valore di prima (sul valore assoluto, così
    una perdita attesa che si riduce è una revisione positiva)."""
    cur, prima = f(cur), f(prima)
    if cur is None or prima is None or prima == 0:
        return None
    return round((cur - prima) / abs(prima) * 100.0, 2)


def leggi_tickers(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [l.split("#")[0].strip() for l in fh if l.split("#")[0].strip()]


def leggi_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


# ----------------------------- universo -----------------------------


def carica_universo():
    """Ticker dell'universo: UNIVERSE_FILE / universe.json, poi i parziali del
    GARP, poi results/latest.json. Ritorna (lista ticker, fonte)."""
    for path in (os.environ.get("UNIVERSE_FILE", "").strip(), "universe.json"):
        if path and os.path.exists(path):
            u = leggi_json(path)
            if isinstance(u, dict) and u:
                return sorted(u), path
            if isinstance(u, list) and u:
                return sorted(set(map(str, u))), path
    pdir = os.environ.get("PARTIALS_DIR", "partials")
    tick = set()
    for fp in glob.glob(os.path.join(pdir, "garp-*.json")):
        d = leggi_json(fp) or {}
        tick |= {r.get("ticker") for r in d.get("results") or [] if r.get("ticker")}
    if tick:
        return sorted(tick), f"{pdir}/garp-*.json"
    rep = leggi_json(os.path.join("results", "latest.json")) or {}
    for k in ("passed", "near_miss", "radar_a", "radar_b"):
        tick |= {r.get("ticker") for r in rep.get(k) or [] if r.get("ticker")}
    return sorted(tick), "results/latest.json"


def capitalizzazioni_usd():
    """Capitalizzazione indicativa in USD dai dati .info degli shard (per
    ordinare: se i crediti non bastano restano fuori i più piccoli)."""
    pdir = os.environ.get("PARTIALS_DIR", "partials")
    out = {}
    for fp in glob.glob(os.path.join(pdir, "info-*.json")):
        for t, info in (leggi_json(fp) or {}).items():
            m = f((info or {}).get("marketCap"))
            if m:
                out[t] = m * FX_USD.get((info or {}).get("currency"), 1.0)
    return out


def prioritari():
    """Titoli da aggiornare ogni notte: watchlist, schede fatte, promossi GARP
    (con core, radar ed esclusi per sicurezza) e lista da radiografare."""
    out = set(leggi_tickers("watchlist.txt")) | set(leggi_tickers("schede_fatte.txt"))
    rep = leggi_json(os.path.join("results", "latest.json")) or {}
    for k in ("passed", "radar_a", "radar_b", "esclusi_sicurezza"):
        out |= {r.get("ticker") for r in rep.get(k) or [] if r.get("ticker")}
    lista = leggi_json(os.path.join("results-lista", "latest.json")) or {}
    out |= {r.get("ticker") for r in lista.get("lista") or [] if r.get("ticker")}
    out |= set(lista.get("settimana") or [])
    return {t for t in out if t}


# ----------------------------- EODHD -----------------------------


class Contatore:
    """Crediti usati in questo run e controllo del residuo giornaliero."""

    def __init__(self, cap, residuo_min, sessione, tempo_max_s=None):
        self.cap, self.residuo_min, self.s = cap, residuo_min, sessione
        self.scadenza = time.time() + tempo_max_s if tempo_max_s else None
        self.lock = threading.Lock()
        self.chiamate = 0
        self.stop = None          # motivo dell'interruzione
        self.ultimo_controllo = 0

    def residuo(self):
        """(crediti rimasti oggi, risposta di /api/user) o (None, None)."""
        try:
            r = self.s.get(f"{BASE_URL}/user", params={"fmt": "json", **token_params()},
                           timeout=TIMEOUT_HTTP)
            if r.status_code != 200:
                return None, None
            d = r.json()
            return int(d["dailyRateLimit"]) - int(d["apiRequests"]), d
        except Exception:
            return None, None

    def prenota(self):
        """True se si può fare un'altra chiamata (e la conta)."""
        with self.lock:
            if self.stop:
                return False
            if (self.chiamate + 1) * CREDITI_PER_TITOLO > self.cap:
                self.stop = f"tetto di {self.cap} crediti raggiunto"
                return False
            if self.scadenza and time.time() > self.scadenza:
                self.stop = "tempo massimo del passo raggiunto"
                return False
            if self.chiamate - self.ultimo_controllo >= CONTROLLO_OGNI:
                self.ultimo_controllo = self.chiamate
                res, _ = self.residuo()
                if res is not None and res < self.residuo_min:
                    self.stop = f"crediti rimasti {res} sotto la soglia {self.residuo_min}"
                    return False
            self.chiamate += 1
            return True


def scarica(sessione, codice, contatore, tentativi=3):
    """JSON delle sezioni Earnings del titolo. Ritorna (dati o None, esito)."""
    for i in range(tentativi):
        if not contatore.prenota():
            return None, "non_scaricato"
        try:
            r = sessione.get(f"{BASE_URL}/fundamentals/{codice}",
                             params={"fmt": "json", "filter": FILTRO, **token_params()},
                             timeout=TIMEOUT_HTTP)
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
            time.sleep(10 * (i + 1))
            continue
        time.sleep(2 * (i + 1))
    return None, "errore_rete"


# ----------------------------- valori derivati -----------------------------


def ultimi_per_periodo(trend):
    """Per ogni periodo (0y, +1y, ...) la voce con la data più recente."""
    out = {}
    for v in (trend or {}).values() if isinstance(trend, dict) else []:
        p, d = (v or {}).get("period"), (v or {}).get("date") or ""
        if p and (p not in out or d > (out[p].get("date") or "")):
            out[p] = v
    return out


def derivati(dati, oggi=None):
    """Solo valori calcolati qui (vedi docstring del modulo)."""
    oggi = (oggi or date.today()).isoformat()
    out = {k: None for k in CAMPI}
    if not isinstance(dati, dict):
        return out
    per = ultimi_per_periodo(dati.get("Earnings::Trend"))
    y0, y1 = per.get("0y") or {}, per.get("+1y") or {}
    for nome, voce in (("0y", y0), ("1y", y1)):
        cur = voce.get("epsTrendCurrent")
        out[f"rev_eps_{nome}_7g_pct"] = var_pct(cur, voce.get("epsTrend7daysAgo"))
        out[f"rev_eps_{nome}_30g_pct"] = var_pct(cur, voce.get("epsTrend30daysAgo"))
        out[f"rev_eps_{nome}_90g_pct"] = var_pct(cur, voce.get("epsTrend90daysAgo"))
    a0, a1 = f(y0.get("earningsEstimateAvg")), f(y1.get("earningsEstimateAvg"))
    if a0 is not None and a1 is not None and a0 > 0:
        out["crescita_eps_attesa_pct"] = round((a1 / a0 - 1) * 100.0, 2)
    t0 = f(y0.get("epsTrendCurrent"))
    if a0 and t0 is not None:
        # subito dopo la chiusura dell'anno EODHD può avere la media già
        # sull'anno nuovo e il trend ancora sul vecchio: lo segnaliamo
        out["trend_0y_coerente"] = abs(t0 / a0 - 1) <= 0.05
    n = f(y0.get("earningsEstimateNumberOfAnalysts")) or f(y1.get("earningsEstimateNumberOfAnalysts"))
    out["n_analisti"] = int(n) if n is not None else None
    out["fine_anno_0y"] = y0.get("date") or None

    storia = dati.get("Earnings::History")
    voci = list(storia.values()) if isinstance(storia, dict) else []
    fatte = sorted([v for v in voci if f((v or {}).get("epsActual")) is not None],
                   key=lambda v: v.get("date") or "", reverse=True)
    confronti = [(f(v["epsActual"]), f(v.get("epsEstimate"))) for v in fatte]
    ultime4 = [(a, e) for a, e in confronti if e is not None][:4]
    if ultime4:
        out["n_trimestri_4t"] = len(ultime4)
        out["n_beat_4t"] = sum(1 for a, e in ultime4 if a > e)
        out["n_miss_4t"] = sum(1 for a, e in ultime4 if a < e)
        a, e = ultime4[0]
        out["segno_ultima_sorpresa"] = (a > e) - (a < e)
    if fatte:
        out["ultima_trimestrale"] = fatte[0].get("reportDate") or fatte[0].get("date")
    future = sorted(v.get("reportDate") for v in voci
                    if f((v or {}).get("epsActual")) is None and (v or {}).get("reportDate")
                    and v["reportDate"] >= oggi)
    out["prossima_trimestrale"] = future[0] if future else None
    return out


# ----------------------------- main -----------------------------


def scegli_titoli(args, oggi):
    """(lista di (ticker, codice, gruppo, prioritario), saltati per borsa, info)."""
    if args.tickers:
        universo = [t.strip() for t in args.tickers.split(",") if t.strip()]
        fonte, gruppo, prio = "--tickers", None, set(universo)
    else:
        universo, fonte = carica_universo()
        gruppo = gruppo_del_giorno(oggi) if args.gruppo is None else args.gruppo
        prio = prioritari() if os.environ.get("STIME_PRIORITARI", "1") != "0" else set()
        universo = sorted(set(universo) | prio)
    caps = capitalizzazioni_usd()
    saltati, scelti = {}, []
    for t in universo:
        codice, suf = codice_eodhd(t)
        g = gruppo_di(t)
        if gruppo is not None and g != gruppo and t not in prio:
            continue
        if codice is None:
            saltati[suf] = saltati.get(suf, 0) + 1
            continue
        scelti.append((t, codice, g, t in prio))
    # prima i prioritari, poi per capitalizzazione decrescente
    scelti.sort(key=lambda x: (not x[3], -(caps.get(x[0]) or 0), x[0]))
    if args.limite:
        scelti = scelti[:args.limite]
    return scelti, saltati, {"fonte_universo": fonte, "universo": len(universo),
                             "gruppo_del_giorno": gruppo, "prioritari": len(prio)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--tickers", help="elenco di ticker Yahoo separati da virgola (prova)")
    ap.add_argument("--gruppo", type=int, default=None, help="gruppo 0-4 da forzare")
    ap.add_argument("--limite", type=int, default=0, help="al massimo N titoli")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--workers", type=int, default=env_int("EODHD_WORKERS", 6))
    args = ap.parse_args(argv)

    oggi = date.today()
    cap = env_int("EODHD_CAP_CREDITI", 25000)
    residuo_min = env_int("EODHD_RESIDUO_MIN", 20000)
    tempo_max = env_int("EODHD_TEMPO_MAX_S", 900)   # il job di merge ha un tempo limite
    s = requests.Session()
    s.headers["User-Agent"] = "garp-screener/1.0 (snapshot stime)"

    scelti, saltati, info = scegli_titoli(args, oggi)
    cont = Contatore(cap, residuo_min, s, tempo_max)
    prima, d_prima = cont.residuo()
    riepilogo = {"date": oggi.isoformat(), **info, "da_scaricare": len(scelti),
                 "saltati_per_borsa": dict(sorted(saltati.items())),
                 "saltati_totale": sum(saltati.values()), "cap_crediti": cap,
                 "residuo_min": residuo_min, "crediti_rimasti_prima": prima}
    print(f"Stime EODHD: {len(scelti)} titoli da scaricare (gruppo {info['gruppo_del_giorno']}, "
          f"prioritari {info['prioritari']}), saltati per borsa {riepilogo['saltati_totale']} "
          f"{riepilogo['saltati_per_borsa']}; crediti rimasti oggi: {prima}")
    if prima is None:
        if d_prima is None and not token_params():
            print("[WARN] contatore EODHD non leggibile e nessuna chiave in EODHD_API_TOKEN",
                  file=sys.stderr)
        print("[WARN] contatore EODHD non leggibile: interrompo per prudenza", file=sys.stderr)
        riepilogo["interrotto"] = "contatore /api/user non leggibile"
        scrivi_riepilogo(args.out_dir, riepilogo)
        return 1   # probabile chiave mancante: il passo risulta fallito (continue-on-error)
    budget = min(cap, prima - residuo_min)
    if budget < CREDITI_PER_TITOLO:
        msg = f"crediti rimasti {prima}, soglia {residuo_min}: nessuno scarico oggi"
        print(f"[WARN] {msg}", file=sys.stderr)
        riepilogo["interrotto"] = msg
        scrivi_riepilogo(args.out_dir, riepilogo)
        return 0
    cont.cap = budget

    path = os.path.join(args.out_dir, f"{oggi.isoformat()}.csv.gz")
    righe = {}
    if os.path.exists(path):   # secondo run nello stesso giorno: non riscaricare
        with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("esito") == "ok":
                    righe[r["ticker"]] = r
    da_fare = [x for x in scelti if x[0] not in righe]

    def lavoro(x):
        t, codice, g, pr = x
        dati, esito = scarica(s, codice, cont)
        r = derivati(dati, oggi) if dati is not None else {k: None for k in CAMPI}
        if esito == "ok" and r["n_analisti"] is None and r["n_trimestri_4t"] is None:
            esito = "senza_stime"
        r.update(date=oggi.isoformat(), ticker=t, codice_eodhd=codice, gruppo=g,
                 prioritario=pr, esito=esito)
        return r

    esiti = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        for fut in as_completed([ex.submit(lavoro, x) for x in da_fare]):
            r = fut.result()
            esiti[r["esito"]] = esiti.get(r["esito"], 0) + 1
            if r["esito"] != "non_scaricato":
                righe[r["ticker"]] = r

    os.makedirs(args.out_dir, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CAMPI, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for t in sorted(righe):
        w.writerow({k: ("" if righe[t].get(k) is None else righe[t].get(k)) for k in CAMPI})
    with open(path, "wb") as fh:
        fh.write(gzip.compress(buf.getvalue().encode("utf-8"), mtime=0))

    dopo, _ = cont.residuo()
    riepilogo.update({"esiti": dict(sorted(esiti.items())), "righe_nel_file": len(righe),
                      "chiamate": cont.chiamate, "crediti_stimati": cont.chiamate * CREDITI_PER_TITOLO,
                      "crediti_rimasti_dopo": dopo,
                      "crediti_usati": (prima - dopo) if dopo is not None else None,
                      "interrotto": cont.stop, "file": path})
    scrivi_riepilogo(args.out_dir, riepilogo)
    print(f"Stime EODHD: {len(righe)} righe in {path}; esiti {riepilogo['esiti']}; "
          f"chiamate {cont.chiamate}; crediti usati {riepilogo['crediti_usati']} "
          f"(rimasti {dopo})" + (f"; interrotto: {cont.stop}" if cont.stop else ""))
    return 0


def scrivi_riepilogo(out_dir, riepilogo):
    os.makedirs(out_dir, exist_ok=True)
    riepilogo["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    with open(os.path.join(out_dir, "ultimo_run.json"), "w", encoding="utf-8") as fh:
        json.dump(riepilogo, fh, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
