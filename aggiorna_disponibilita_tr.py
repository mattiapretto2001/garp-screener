#!/usr/bin/env python3
"""
Disponibilità su Trade Republic: stima "acquistabile su TR" (dal 08/11/2026)
============================================================================
Trade Republic (TR) esegue quasi tutto su LS Exchange (Lang & Schwarz, Borsa
di Amburgo) e non pubblica l'elenco dei titoli: non c'è un'API pubblica. Questo
script fa una STIMA ragionevole, non una verifica. La verifica vera resta una:
cercare l'ISIN nell'app di TR prima di comprare.

Da far girare A MANO una volta al mese (NON è nel workflow notturno, così non
costa crediti ogni sera). Scrive disponibilita_tr.csv nella radice del repo.

Regola (colonna acquistabile_tr)
--------------------------------
  "probabile"        l'ISIN ha una quotazione in Germania (Xetra, Francoforte,
                     Stoccarda, Monaco, Düsseldorf, Amburgo, Hannover, Berlino,
                     Tradegate, Quotrix): LS Exchange tratta le azioni estere
                     che hanno una linea tedesca. Oppure è un'azione quotata su
                     una borsa USA regolamentata (NYSE, Nasdaq, NYSE American,
                     Cboe; ADR compresi): TR copre quasi tutte le large e mid
                     cap USA. Oppure la società ha un'altra linea con lo stesso
                     nome (ADR, GDR, doppia quotazione) che rispetta una delle
                     condizioni: allora isin_tr è l'ISIN da cercare in TR (es.
                     2330.TW -> ADR TSM, US8740391003).
  "incerto"          nessuna quotazione tedesca trovata (fuori dagli USA) o
                     ISIN mancante. Un ticker che NON è nel file va trattato
                     come "incerto".
  "probabilmente no" società quotata solo a Taiwan (TW, TWO) o in Corea (KS,
                     KQ) senza linea tedesca né ADR/GDR.

Azioni USA senza nessuna quotazione tedesca trovata (né su EODHD né su
OpenFIGI; es. ATAT e BLLN al 07/11/2026): restano "probabile" per la regola
USA, ma la fonte lo dice ("nessuna quotazione tedesca trovata ... verificare
in TR"): è la prova più debole del file. Non si declassano a "incerto" perché
la copertura tedesca di OpenFIGI è incompleta: il 07/11/2026 mancavano anche
mid cap USA note e molto scambiate in Germania (Credo, nVent, NuScale, Dutch
Bros). Con --usa-senza-linea-de incerto si declassano lo stesso.

Fonti (tutte pubbliche)
-----------------------
  - EODHD /api/exchange-symbol-list/{BORSA}: 1 credito per borsa, 29 a giro.
    Codice, nome, tipo e ISIN delle azioni di ogni borsa. Nel file NON finisce
    nessun dato EODHD grezzo: solo ticker e ISIN (fatti pubblici) e la nostra
    deduzione. Le liste restano in memoria, o nella cartella di --cache-dir che
    NON va messa nel repository (licenza EODHD); lì finiscono anche le risposte
    OpenFIGI, così un secondo giro entro 7 giorni non rifà le richieste.
  - OpenFIGI (api.openfigi.com, gratuito e pubblico, nessun credito EODHD):
      a) per gli ISIN senza linea tedesca nelle liste EODHD (incomplete: per
         esempio mancano le azioni ABB e Saab B di Francoforte) chiede se
         esiste una quotazione nel composito Germania di Bloomberg ("GR");
      b) per Milano e Tokyo, che EODHD non copre: dagli ISIN italiani,
         olandesi, lussemburghesi e giapponesi con linea tedesca ricava il
         ticker di Milano (.MI) o di Tokyo (.T).
    Senza chiave il server dichiara 25 richieste da 10 ISIN al minuto: nel
    caso peggiore il giro dura 30-40 minuti. Con la variabile OPENFIGI_APIKEY
    (chiave gratuita) le richieste sono da 100 ISIN.
  - LS Exchange pubblica un "Handelsuniversum" (PDF giornaliero) e i file di
    trasparenza post-negoziazione, ma le condizioni d'uso di ls-x.de vietano di
    copiarli, salvarli, elaborarli o ripubblicarli senza permesso scritto
    della BÖAG Börsen AG: NON sono usati. Per un controllo personale si può
    aprire il PDF a mano e cercare l'ISIN.

Limiti noti
-----------
  - Avere una linea tedesca non garantisce che TR la offra, e TR può offrire
    titoli che qui risultano "incerto": è una stima.
  - Né le liste tedesche di EODHD (circa 14.000 ISIN) né OpenFIGI coprono
    tutte le quotazioni tedesche: un "incerto" europeo può essere comprabile.
  - Le altre linee "per nome" (ADR/GDR) si trovano solo se il nome
    normalizzato (almeno due parole) è identico: qualche ADR sfugge.
  - Milano e Tokyo: compaiono solo i titoli con linea tedesca nelle liste
    EODHD (tutti "probabile"); gli altri mancano dal file, quindi "incerto".
  - ISIN mancante nella fonte: "incerto" (non si può controllare).
  - Borse asiatiche locali: non controllate su OpenFIGI (non hanno quasi mai
    linee tedesche); contano le linee tedesche nelle liste EODHD e gli ADR/GDR.

Colonne di disponibilita_tr.csv
-------------------------------
  ticker          ticker Yahoo (come negli screener: AAPL, ASML.AS, 2330.TW)
  isin            ISIN della linea (vuoto se la fonte non lo dà)
  acquistabile_tr "probabile" | "incerto" | "probabilmente no"
  fonte           perché: borse tedesche nelle liste EODHD ("DE: XETRA, F"),
                  composito Germania su OpenFIGI ("DE da OpenFIGI"), altra
                  linea con lo stesso nome, borsa USA senza linea tedesca...
                  Codici: XETRA, F = Francoforte, STU = Stoccarda, MU = Monaco,
                  DU = Düsseldorf, HM = Amburgo, HA = Hannover, BE = Berlino.
  isin_tr         ISIN da cercare nell'app di TR (uguale a isin, oppure quello
                  dell'ADR/GDR o della doppia quotazione; vuoto se non c'è)

Crediti EODHD: prima di partire legge /api/user e non parte se il residuo del
giorno scenderebbe sotto --residuo-min (default 500).

Chiave EODHD: in GitHub Actions è il secret EODHD_API_TOKEN, mandato come
parametro api_token. Se la variabile non c'è (sessioni in cui un proxy
aggiunge la chiave da sé) non si manda nulla.

Uso
---
  python aggiorna_disponibilita_tr.py                    # scrive disponibilita_tr.csv
  python aggiorna_disponibilita_tr.py --controllo NU,TSM,2330.TW,PRY.MI
  python aggiorna_disponibilita_tr.py --cache-dir /tmp/liste_eodhd  # riusa le liste

Per gli altri script: leggi() restituisce {ticker: riga}; ticker assente =
"incerto".
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict

import requests

BASE_URL = "https://eodhd.com/api"
OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
OUT_FILE = "disponibilita_tr.csv"
CAMPI = ["ticker", "isin", "acquistabile_tr", "fonte", "isin_tr"]
TIMEOUT_HTTP = 120
RESIDUO_MIN_DEFAULT = 500
CALO_MAX = 0.30            # non sovrascrive se le righe calano di oltre il 30% (fonte rotta)
OPENFIGI_TEMPO_MAX_S = 3600
CACHE_MAX_GIORNI = 7       # file di --cache-dir più vecchi si riscaricano

# borse tedesche EODHD (Berlino "BE" oggi ha solo 2 righe, la teniamo se cresce)
BORSE_DE = ["XETRA", "F", "STU", "MU", "DU", "HM", "HA", "BE"]

# borsa EODHD -> suffisso Yahoo delle righe scritte nel file ("" = USA)
BORSE_RIGHE = {
    "US": "", "XETRA": "DE", "LSE": "L", "PA": "PA", "AS": "AS", "MC": "MC", "SW": "SW",
    "ST": "ST", "CO": "CO", "HE": "HE", "OL": "OL", "BR": "BR", "VI": "VI", "LS": "LS",
    "IR": "IR", "TO": "TO", "TW": "TW", "TWO": "TWO", "KO": "KS", "KQ": "KQ", "AU": "AX",
    "HK": "HK",
}
# borse asiatiche dove senza linea tedesca né ADR il titolo è "probabilmente no"
BORSE_SOLO_LOCALI = {"TW", "TWO", "KO", "KQ"}
# borse USA regolamentate (fuori le OTC/Pink, che gli screener non usano)
BORSE_USA_QUOTATE = {"NYSE", "NASDAQ", "AMEX", "NYSE MKT", "BATS", "NYSE ARCA"}
# strumenti che nelle liste EODHD risultano "Common Stock" ma non sono azioni
# ("Jupiter Fund Management" e le "LP Unit" delle MLP restano: sono azioni)
NON_AZIONI = re.compile(
    r"\b(etf|etn|rights?|warrants?|notes?|debentures?|preferred|subordinated)\b"
    r"|\bfund\b(?!\s+management)|acquisition.*\bunits?\b|\bunits?\b.*\b(each|consisting)\b"
    r"|%|\bdue \d{4}\b", re.I)

# OpenFIGI: codici borsa Bloomberg
FIGI_GERMANIA = "GR"  # composito Germania: c'è se esiste almeno una quotazione tedesca
OPENFIGI_BORSE = {    # Milano e Tokyo non sono in EODHD
    "IM": {"suffisso": "MI", "prefissi_isin": ("IT", "NL", "LU")},
    "JT": {"suffisso": "T", "prefissi_isin": ("JP",)},
}

FORME_SOCIETARIE = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc",
    "sa", "ag", "nv", "se", "spa", "asa", "ab", "as", "oyj", "abp", "publ", "the", "llc",
    "lp", "sca", "sab", "de", "cv", "kgaa", "class", "a", "b", "ord", "ordinary", "shares",
    "share", "common", "stock", "reg", "registered", "bhd", "tbk", "pt", "pcl", "kk",
    "holding", "holdings", "adr", "ads", "adrs", "gdr", "gdrs", "sponsored", "unsponsored",
    "144a", "regs", "new", "jsc", "pjsc", "oao",
}
NOME_MIN_CARATTERI = 6  # nomi normalizzati più corti non si usano (troppo generici)


# ----------------------------- utilità -----------------------------


def cache_fresca(percorso):
    return bool(percorso) and os.path.exists(percorso) and \
        time.time() - os.path.getmtime(percorso) < CACHE_MAX_GIORNI * 86400


def token_params():
    """api_token solo se la variabile d'ambiente c'è (GitHub Actions)."""
    tok = os.environ.get("EODHD_API_TOKEN", "").strip()
    return {"api_token": tok} if tok else {}


def residuo_eodhd():
    """Crediti rimasti oggi (limite giornaliero meno usati), o None se non leggibile."""
    try:
        r = requests.get(f"{BASE_URL}/user", params={"fmt": "json", **token_params()},
                         timeout=30)
        r.raise_for_status()
        d = r.json()
        return int(d.get("dailyRateLimit") or 0) - int(d.get("apiRequests") or 0)
    except Exception as e:
        print(f"[WARN] contatore EODHD non leggibile: {e}", file=sys.stderr)
        return None


def scarica_lista(borsa, cache_dir=None):
    """(lista dei simboli di una borsa EODHD o None, crediti spesi).
    Con cache_dir riusa il file già scaricato (0 crediti) o lo salva."""
    percorso = os.path.join(cache_dir, f"{borsa}.json") if cache_dir else None
    if cache_fresca(percorso):
        with open(percorso, encoding="utf-8") as fh:
            return json.load(fh), 0
    try:
        r = requests.get(f"{BASE_URL}/exchange-symbol-list/{borsa}",
                         params={"fmt": "json", **token_params()}, timeout=TIMEOUT_HTTP)
        if r.status_code != 200:
            print(f"[WARN] {borsa}: HTTP {r.status_code}", file=sys.stderr)
            return None, 1
        dati = r.json()
        if not isinstance(dati, list):
            print(f"[WARN] {borsa}: risposta inattesa", file=sys.stderr)
            return None, 1
    except Exception as e:
        print(f"[WARN] {borsa}: {e}", file=sys.stderr)
        return None, 1
    if percorso:
        os.makedirs(cache_dir, exist_ok=True)
        with open(percorso, "w", encoding="utf-8") as fh:
            json.dump(dati, fh)
    return dati, 1


def norma_nome(nome):
    """Nome per confrontare linee diverse della stessa società:
    'Taiwan Semiconductor Manufacturing Co. Ltd.' e 'Taiwan Semiconductor
    Manufacturing Company Limited' -> 'taiwan semiconductor manufacturing'."""
    n = (nome or "").lower()
    n = re.sub(r"\b(american|global)\s+depositary\s+(shares?|receipts?)\b.*$", " ", n)
    n = re.sub(r"\bdepositary\s+(shares?|receipts?)\b.*$", " ", n)
    n = re.sub(r"\beach\s+represent\w*\b.*$", " ", n)
    n = re.sub(r"\b(gdr|adr)\b.*$", " ", n)  # 'SK HYNIX GDR 144A/REGS 1' -> 'sk hynix'
    # sigle puntate: 's.p.a.' -> 'spa', 'n.v.' -> 'nv', 'a/s' -> 'as'
    n = re.sub(r"\b([a-z])[./](?=[a-z]\b)", r"\1", n)
    n = re.sub(r"[^a-z0-9& ]+", " ", n)
    return " ".join(p for p in n.split() if p not in FORME_SOCIETARIE)


def nome_utile(k):
    """Solo nomi di almeno due parole e 6 caratteri: 'universal' o
    'continental' da soli legherebbero società diverse."""
    return len(k) >= NOME_MIN_CARATTERI and len(k.split()) >= 2


def e_azione(x):
    """Azione ordinaria. Alcune classi di azioni USA sono segnate "Preferred
    Stock" per errore (MOG-B, AGM-A): si tengono solo quelle con codice
    'RADICE-LETTERA' e nome senza parole da privilegiata."""
    nome = x.get("Name") or ""
    if NON_AZIONI.search(nome):
        return False
    if x.get("Type") == "Common Stock":
        return True
    return (x.get("Type") == "Preferred Stock"
            and bool(re.fullmatch(r"[A-Z]{1,5}-[A-OQ-Z]", str(x.get("Code") or "")))
            and not re.search(r"\b(pref\w*|pfd|series|depositary)\b", nome, re.I))


def isin_valido(s):
    return bool(re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", s or ""))


# ----------------------------- OpenFIGI -----------------------------


class OpenFigi:
    """Mappatura ISIN -> ticker su una borsa Bloomberg, rispettando i limiti."""

    def __init__(self, tempo_max_s=OPENFIGI_TEMPO_MAX_S, cache_dir=None):
        self.cache_dir = cache_dir
        chiave = os.environ.get("OPENFIGI_APIKEY", "").strip()
        self.intest = {"Content-Type": "application/json"}
        if chiave:
            self.intest["X-OPENFIGI-APIKEY"] = chiave
        self.blocco = 100 if chiave else 10
        self.scadenza = time.time() + tempo_max_s
        self.richieste = 0
        self.fallito = False

    def _post(self, lavori):
        for _ in range(5):
            if time.time() > self.scadenza:
                return None
            try:
                r = requests.post(OPENFIGI_URL, headers=self.intest, json=lavori, timeout=60)
            except Exception as e:
                print(f"[WARN] OpenFIGI: {e}", file=sys.stderr)
                time.sleep(10)
                continue
            self.richieste += 1
            if r.status_code == 429:
                time.sleep(int(r.headers.get("ratelimit-reset") or 60) + 1)
                continue
            if r.status_code != 200:
                print(f"[WARN] OpenFIGI HTTP {r.status_code}", file=sys.stderr)
                time.sleep(10)
                continue
            if r.headers.get("ratelimit-remaining") == "0":
                time.sleep(int(r.headers.get("ratelimit-reset") or 60) + 1)
            return r.json()
        return None

    def mappa(self, isin_list, borsa_bbg):
        """({isin: ticker} sulla borsa indicata, set degli ISIN controllati)."""
        trovati, controllati, creato = {}, set(), time.time()
        cache = os.path.join(self.cache_dir, f"openfigi_{borsa_bbg}.json") if self.cache_dir else None
        if cache and os.path.exists(cache):
            with open(cache, encoding="utf-8") as fh:
                c = json.load(fh)
            # la data è quella del primo giro: riscritture successive non la allungano
            if time.time() - c.get("creato", 0) < CACHE_MAX_GIORNI * 86400:
                trovati, controllati = dict(c["trovati"]), set(c["controllati"])
                creato = c["creato"]
        richiesti = set(isin_list)
        isin_list = [i for i in isin_list if isin_valido(i) and i not in controllati]
        for i in range(0, len(isin_list), self.blocco):
            parte = isin_list[i:i + self.blocco]
            esiti = self._post([{"idType": "ID_ISIN", "idValue": s, "exchCode": borsa_bbg}
                                for s in parte])
            if esiti is None:
                print(f"[WARN] OpenFIGI {borsa_bbg}: interrotto dopo {i} ISIN su "
                      f"{len(isin_list)}", file=sys.stderr)
                self.fallito = True
                break
            for isin, esito in zip(parte, esiti):
                if "error" in esito:
                    continue
                controllati.add(isin)
                for d in esito.get("data") or []:
                    tk = (d.get("ticker") or "").strip()
                    if tk and d.get("marketSector") == "Equity" and d.get("exchCode") == borsa_bbg:
                        trovati.setdefault(isin, tk.replace(" ", "-").replace("/", "-"))
        if cache:
            with open(cache, "w", encoding="utf-8") as fh:
                json.dump({"creato": creato, "trovati": trovati,
                           "controllati": sorted(controllati)}, fh)
        return ({k: v for k, v in trovati.items() if k in richiesti},
                controllati & richiesti)


# ----------------------------- costruzione -----------------------------


def costruisci(liste, usa_openfigi=True, usa_senza_linea_de="probabile", cache_dir=None):
    """Righe del file a partire dalle liste EODHD già scaricate {borsa: [..]}."""
    # 1) ISIN sulle borse tedesche (liste EODHD)
    isin_de = defaultdict(set)
    for b in BORSE_DE:
        for x in liste.get(b) or []:
            if x.get("Isin") and x.get("Type") in ("Common Stock", "Preferred Stock"):
                isin_de[x["Isin"]].add(b)

    # 2) azioni quotate su borse USA regolamentate
    isin_usa = {}
    for x in liste.get("US") or []:
        if x.get("Isin") and x.get("Exchange") in BORSE_USA_QUOTATE and e_azione(x):
            isin_usa.setdefault(x["Isin"], (x["Code"], x["Exchange"]))

    # 3) indice per nome delle linee tedesche e USA (per ADR/GDR e doppie quotazioni)
    per_nome = {}
    for b in BORSE_DE:
        for x in liste.get(b) or []:
            if x.get("Isin") and e_azione(x):
                k = norma_nome(x.get("Name"))
                if nome_utile(k):
                    per_nome.setdefault(k, x["Isin"])
    for x in liste.get("US") or []:
        if x.get("Isin") and x.get("Exchange") in BORSE_USA_QUOTATE and e_azione(x):
            k = norma_nome(x.get("Name"))
            if nome_utile(k):
                per_nome.setdefault(k, x["Isin"])

    # 4) righe grezze: una per ticker Yahoo
    grezze = {}
    for borsa, suffisso in BORSE_RIGHE.items():
        for x in liste.get(borsa) or []:
            if not e_azione(x):
                continue
            if borsa == "US" and x.get("Exchange") not in BORSE_USA_QUOTATE:
                continue  # OTC/Pink: fuori dagli screener
            codice = str(x.get("Code") or "").strip().upper()
            if not codice:
                continue
            if borsa == "HK":
                if not codice.isdigit():
                    continue  # linee secondarie di Hong Kong ('0020-OL')
                codice = codice.zfill(4)  # Yahoo: 0700.HK
            if borsa == "LSE" and re.fullmatch(r"0[A-Z0-9]{3}", codice):
                continue  # linee estere del London IOB ('0R2X'), fuori dagli screener
            if borsa in ("TW", "TWO") and codice.startswith("00"):
                continue  # ETF di Taiwan ('0050', '00939')
            tk = f"{codice}.{suffisso}" if suffisso else codice
            isin = (x.get("Isin") or "").strip()
            alt = None
            if borsa != "US" and isin not in isin_de and isin not in isin_usa:
                k = norma_nome(x.get("Name"))
                alt = per_nome.get(k) if nome_utile(k) else None
                # con l'ISIN locale noto, l'altra linea deve essere dello stesso
                # paese o un ADR/GDR (ISIN US): 'Antimony Resources Ltd' (AU) non
                # è 'Antimony Resources Corp' (CA)
                if alt and (alt == isin or (isin and alt[:2] not in (isin[:2], "US"))):
                    alt = None
            nuova = {"tk": tk, "borsa": borsa, "isin": isin, "alt": alt,
                     "ex_usa": x.get("Exchange") if borsa == "US" else None}
            vecchia = grezze.get(tk)
            if vecchia is None or (not vecchia["isin"] and isin):
                grezze[tk] = nuova

    # 5) OpenFIGI: quotazione tedesca per gli ISIN che le liste EODHD non hanno
    figi_de, figi_controllati = set(), set()
    figi = OpenFigi(cache_dir=cache_dir) if usa_openfigi else None
    if figi:
        da_controllare = set()
        for g in grezze.values():
            if g["borsa"] in BORSE_DE:
                continue
            if g["isin"] and g["isin"] not in isin_de and g["borsa"] not in BORSE_SOLO_LOCALI:
                da_controllare.add(g["isin"])
            if g["alt"] and g["alt"] not in isin_de:
                da_controllare.add(g["alt"])
        da_controllare = sorted(da_controllare)
        print(f"  OpenFIGI {FIGI_GERMANIA}: {len(da_controllare)} ISIN senza linea tedesca "
              "nelle liste EODHD")
        trovati, figi_controllati = figi.mappa(da_controllare, FIGI_GERMANIA)
        figi_de = set(trovati)
        print(f"  OpenFIGI {FIGI_GERMANIA}: {len(figi_controllati)} controllati, "
              f"{len(figi_de)} con quotazione tedesca")

    def linea_de(isin):
        """Testo della linea tedesca dell'ISIN, o None."""
        if isin and isin in isin_de:
            return "DE: " + ", ".join(sorted(isin_de[isin], key=BORSE_DE.index))
        if isin and isin in figi_de:
            return "DE da OpenFIGI"
        return None

    def usa_senza_de(isin, descr):
        """Azione USA quotata senza linea tedesca nelle liste EODHD."""
        if isin in figi_controllati:
            return (usa_senza_linea_de, f"{descr}, nessuna quotazione tedesca trovata (EODHD "
                    "e OpenFIGI): verificare in TR",
                    isin if usa_senza_linea_de == "probabile" else "")
        return "probabile", f"{descr}, linea DE non verificata", isin

    def valuta(g):
        isin, borsa = g["isin"], g["borsa"]
        de = linea_de(isin)
        if de:
            return "probabile", de, isin
        if borsa in BORSE_DE:  # quotata su Xetra anche se la fonte non dà l'ISIN
            return "probabile", f"DE: {borsa}", isin
        if borsa == "US":
            return usa_senza_de(isin, f"USA ({g['ex_usa']})")
        if isin and isin in isin_usa:
            cod, ex = isin_usa[isin]
            return usa_senza_de(isin, f"stesso ISIN in USA: {cod} ({ex})")
        alt = g["alt"]
        if alt:
            dove = []
            if alt in isin_usa:
                dove.append(f"USA: {isin_usa[alt][0]} ({isin_usa[alt][1]})")
            de_alt = linea_de(alt)
            if de_alt:
                dove.append(de_alt)
            testo = f"altra linea con lo stesso nome (ADR/GDR o doppia quotazione) {alt}"
            if de_alt:
                return "probabile", testo + "; " + "; ".join(dove), alt
            if alt in isin_usa:
                flag, fonte, isin_tr = usa_senza_de(alt, testo + "; " + "; ".join(dove))
                if flag == "probabile":
                    return flag, fonte, isin_tr
        motivo = "senza linea DE" if isin else "ISIN mancante nei dati"
        if isin and isin in figi_controllati:
            motivo += " (EODHD e OpenFIGI)"
        elif isin:
            motivo += " nei dati EODHD"
        if borsa in BORSE_SOLO_LOCALI:
            return "probabilmente no", motivo + ", né ADR/GDR: solo borsa asiatica", ""
        return "incerto", motivo, ""

    righe = {}
    for tk, g in grezze.items():
        flag, fonte, isin_tr = valuta(g)
        righe[tk] = {"ticker": tk, "isin": g["isin"], "acquistabile_tr": flag,
                     "fonte": fonte, "isin_tr": isin_tr}

    # 6) Milano e Tokyo da OpenFIGI (solo ISIN con linea tedesca nelle liste EODHD)
    if figi:
        for bbg, conf in OPENFIGI_BORSE.items():
            candidati = sorted(i for i in isin_de if i.startswith(conf["prefissi_isin"]))
            mappa, _ = figi.mappa(candidati, bbg)
            n = 0
            for isin, cod in mappa.items():
                tk = f"{cod.upper()}.{conf['suffisso']}"
                if tk not in righe:
                    righe[tk] = {"ticker": tk, "isin": isin, "acquistabile_tr": "probabile",
                                 "fonte": linea_de(isin) + "; ticker da OpenFIGI",
                                 "isin_tr": isin}
                    n += 1
            print(f"  OpenFIGI {bbg}: {len(candidati)} ISIN, {n} ticker .{conf['suffisso']}")
        print(f"  OpenFIGI: {figi.richieste} richieste"
              + (" (INCOMPLETO: vedi avvisi)" if figi.fallito else ""))
    return [righe[k] for k in sorted(righe)]


def scrivi(righe, percorso):
    tmp = percorso + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPI, lineterminator="\n")
        w.writeheader()
        w.writerows(righe)
    os.replace(tmp, percorso)


def leggi(percorso=OUT_FILE):
    """Per gli altri script: {ticker: riga}. Ticker assente = "incerto"."""
    try:
        with open(percorso, encoding="utf-8") as fh:
            return {r["ticker"]: r for r in csv.DictReader(fh)}
    except OSError:
        return {}


# ----------------------------- main -----------------------------


def main():
    ap = argparse.ArgumentParser(description="Stima dei titoli acquistabili su Trade Republic")
    ap.add_argument("--out", default=OUT_FILE)
    ap.add_argument("--cache-dir", default=None,
                    help="cartella FUORI dal repo dove salvare/riusare le liste EODHD")
    ap.add_argument("--residuo-min", type=int, default=RESIDUO_MIN_DEFAULT)
    ap.add_argument("--senza-openfigi", action="store_true")
    ap.add_argument("--usa-senza-linea-de", choices=["probabile", "incerto"], default="probabile",
                    help="azioni USA senza nessuna quotazione tedesca (default probabile)")
    ap.add_argument("--forza", action="store_true",
                    help="scrive anche se le righe calano di oltre il 30%%")
    ap.add_argument("--controllo", default="",
                    help="ticker separati da virgola da stampare a fine giro")
    args = ap.parse_args()

    borse = list(dict.fromkeys(BORSE_DE + list(BORSE_RIGHE)))
    da_scaricare = [b for b in borse if not (
        args.cache_dir and cache_fresca(os.path.join(args.cache_dir, f"{b}.json")))]
    if da_scaricare:
        residuo = residuo_eodhd()
        print(f"Crediti EODHD rimasti oggi: {residuo}; servono {len(da_scaricare)}")
        if residuo is not None and residuo - len(da_scaricare) < args.residuo_min:
            print(f"[STOP] il residuo scenderebbe sotto {args.residuo_min}", file=sys.stderr)
            return 2

    liste, mancanti, crediti = {}, [], 0
    for b in borse:
        dati, spesi = scarica_lista(b, args.cache_dir)
        crediti += spesi
        if dati is None:
            mancanti.append(b)
            continue
        liste[b] = dati
    print(f"Liste EODHD: {len(liste)} borse, crediti spesi circa {crediti}")
    if mancanti:
        print(f"[WARN] liste mancanti: {', '.join(mancanti)}", file=sys.stderr)
    if "F" not in liste or "XETRA" not in liste or "US" not in liste:
        print("[STOP] mancano Francoforte, Xetra o USA: il file non si aggiorna", file=sys.stderr)
        return 3

    righe = costruisci(liste, usa_openfigi=not args.senza_openfigi,
                       usa_senza_linea_de=args.usa_senza_linea_de, cache_dir=args.cache_dir)
    prima = len(leggi(args.out))
    if prima and len(righe) < prima * (1 - CALO_MAX) and not args.forza:
        print(f"[STOP] righe {prima} -> {len(righe)}: calo sospetto, file non toccato "
              "(usa --forza se è voluto)", file=sys.stderr)
        return 4
    scrivi(righe, args.out)

    conteggi = defaultdict(lambda: defaultdict(int))
    for r in righe:
        suf = r["ticker"].rsplit(".", 1)[1] if "." in r["ticker"] else "USA"
        conteggi[suf][r["acquistabile_tr"]] += 1
    print(f"Scritto {args.out}: {len(righe)} righe (prima {prima})")
    for suf in sorted(conteggi):
        c = conteggi[suf]
        print(f"  {suf:4} probabile {c['probabile']:6}  incerto {c['incerto']:6}  "
              f"probabilmente no {c['probabilmente no']:6}")
    if args.controllo:
        indice = {r["ticker"]: r for r in righe}
        for tk in [t.strip() for t in args.controllo.split(",") if t.strip()]:
            r = indice.get(tk)
            print(f"  {tk:10} " + (f"{r['acquistabile_tr']:17} {r['isin']:13} {r['fonte']}"
                                    if r else "assente dal file -> incerto"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
