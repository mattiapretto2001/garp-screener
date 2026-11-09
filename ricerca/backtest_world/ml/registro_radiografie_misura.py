"""Misura del registro Radiografie (lettura a 6 e 12 mesi).

Uso:
  python3 registro_radiografie_misura.py --mesi 6   [--repo /home/user/garp-screener] [--senza-paniere]
  python3 registro_radiografie_misura.py --mesi 0   (prova: rendimenti fino a oggi)

Prezzi da yfinance (nessun credito EODHD). Rendimenti in euro, prezzo di chiusura.
Per ogni riga: rendimento del titolo dalla data del prezzo di riferimento alla data +N mesi,
rendimento di VWCE.DE nello stesso periodo, e (se l'origine e' uno screener) rendimento del
paniere a pesi uguali di tutti i titoli promossi dallo stesso screener quel giorno.
Stampa le cifre della guida R_registro_radiografie.md e scrive registro_radiografie_misura_<N>m.csv.
"""
import argparse, json, os, sys
import pandas as pd
import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
CARTELLE = {"GARP": "results", "Moonshot": "results-moonshot", "Svolta": "results-svolta", "Temi": "results-temi"}


def scarica(tickers, inizio, fine):
    import yfinance as yf
    d = yf.download(sorted(set(tickers)), start=inizio, end=fine, progress=False, auto_adjust=False)["Close"]
    if isinstance(d, pd.Series):
        d = d.to_frame(sorted(set(tickers))[0])
    return d.ffill()


def prezzo_al(serie, giorno):
    s = serie.dropna()
    s = s[s.index <= pd.Timestamp(giorno)]
    return float(s.iloc[-1]) if len(s) else np.nan


def valuta_fx(valuta):
    return {"EUR": None, "USD": "EURUSD=X", "NOK": "EURNOK=X", "GBP": "EURGBP=X", "CHF": "EURCHF=X",
            "SEK": "EURSEK=X", "DKK": "EURDKK=X"}.get(valuta)


SUFFISSI = {"OL": "NOK", "ST": "SEK", "CO": "DKK", "L": "GBP", "SW": "CHF"}
EURO = {"DE", "PA", "AS", "MC", "MI", "HE", "BR", "LS", "VI", "IR", "F"}


def valuta_da_suffisso(t):
    """Valuta dal suffisso Yahoo; None = rendimento in valuta locale (borse asiatiche: approssimazione)."""
    if "." not in t:
        return "USD"
    suf = t.rsplit(".", 1)[1]
    return "EUR" if suf in EURO else SUFFISSI.get(suf)


def lista_screener(repo, nome, giorno):
    cart = os.path.join(repo, CARTELLE[nome])
    file = sorted(f for f in os.listdir(cart) if f[:4].isdigit() and f[:10] <= giorno)
    if not file:
        return []
    j = json.load(open(os.path.join(cart, file[-1]), encoding="utf-8"))
    if nome == "Temi":
        return [x["ticker"] for x in j.get("tracked", []) if x.get("light") == "verde"]
    return [x["ticker"] for x in j.get("passed", [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesi", type=int, default=12)
    ap.add_argument("--repo", default="/home/user/garp-screener")
    ap.add_argument("--senza-paniere", action="store_true")
    a = ap.parse_args()
    reg = pd.read_csv(os.path.join(QUI, "registro_radiografie.csv"), dtype=str)
    reg["prezzo_rif"] = reg["prezzo_rif"].astype(float)
    reg["d0"] = pd.to_datetime(reg["data_prezzo_rif"])
    oggi = pd.Timestamp.today().normalize()
    reg["d1"] = [min(d + pd.DateOffset(months=a.mesi), oggi) if a.mesi else oggi for d in reg["d0"]]
    inizio = (reg["d0"].min() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    fine = (reg["d1"].max() + pd.Timedelta(days=2)).strftime("%Y-%m-%d")

    # panieri degli screener alla data (solo righe con origine da screener)
    panieri = {}
    if not a.senza_paniere:
        for _, r in reg.iterrows():
            nomi = [n for n in CARTELLE if n in str(r["origine"]) and not str(r["origine"]).startswith("Portafoglio")]
            for n in nomi:
                panieri.setdefault((n, r["data_prezzo_rif"]), lista_screener(a.repo, n, r["data_prezzo_rif"]))
    tutti = set(reg["ticker"]) | {"VWCE.DE", "EURUSD=X", "EURNOK=X", "EURGBP=X", "EURCHF=X", "EURSEK=X", "EURDKK=X"}
    for v in panieri.values():
        tutti |= set(v)
    px = scarica(list(tutti), inizio, fine)

    def rend_eur(t, d0, d1, p0=None, valuta=None):
        if t not in px:
            return np.nan
        a0 = p0 if p0 is not None else prezzo_al(px[t], d0)
        a1 = prezzo_al(px[t], d1)
        fx = valuta_fx(valuta) if valuta else None
        if fx and fx in px:
            return (a1 / prezzo_al(px[fx], d1)) / (a0 / prezzo_al(px[fx], d0)) - 1
        return a1 / a0 - 1

    out = []
    for _, r in reg.iterrows():
        rt = rend_eur(r["ticker"], r["d0"], r["d1"], r["prezzo_rif"], r["valuta"])
        rv = rend_eur("VWCE.DE", r["d0"], r["d1"])
        rp = []
        nomi = [] if str(r["origine"]).startswith("Portafoglio") else [n for n in CARTELLE if n in str(r["origine"])]
        for n in nomi:
            lst = panieri.get((n, r["data_prezzo_rif"]), [])
            if lst:
                rr = [rend_eur(t, r["d0"], r["d1"], None, valuta_da_suffisso(t)) for t in lst]
                rp.append(np.nanmean(rr))
        lim = float(r["prezzo_limite"]) if r["prezzo_limite"] else np.nan
        toccato = np.nan
        if r["ticker"] in px and not np.isnan(lim):
            s = px[r["ticker"]].dropna()
            s = s[(s.index > r["d0"]) & (s.index <= r["d1"])]  # semplificato: finestra fino alla data di lettura, senza le condizioni della regola
            toccato = bool((s >= lim).any()) if "vendita" in str(r["note"]) else bool((s <= lim).any())
        p1 = prezzo_al(px[r["ticker"]], r["d1"]) if r["ticker"] in px else np.nan
        out.append(dict(id=r["id"], ticker=r["ticker"], tipo=r["tipo"], verdetto=r["verdetto"],
                        data_fine=r["d1"].date(), prezzo_fine=p1,
                        s_aut=r["punt_senza_vincoli_autore"], s_ver=r["punt_senza_vincoli_verifica"],
                        rend_eur=rt, rend_vwce=rv, extra_vwce=rt - rv,
                        rend_paniere=np.nanmean(rp) if rp else np.nan,
                        extra_paniere=rt - np.nanmean(rp) if rp else np.nan, limite_toccato=toccato))
    m = pd.DataFrame(out)
    m.to_csv(os.path.join(QUI, f"registro_radiografie_misura_{a.mesi}m.csv"), index=False)
    rad = m[m["tipo"] == "Radiografia"]
    pd.set_option("display.width", 200)
    print(m.round(3).to_string(index=False))
    print("\n== Per verdetto (solo Radiografie, in euro) ==")
    print(rad.groupby("verdetto")[["rend_eur", "extra_vwce", "extra_paniere"]].agg(["mean", "count"]).round(3))
    c = rad.loc[rad.verdetto == "compra", "extra_vwce"].mean()
    w = rad.loc[rad.verdetto.isin(["aspetta", "evita"]), "extra_vwce"].mean()
    print(f"\nScarto compra - aspetta/evita: {c - w:+.3f}")
    print(f"Quota che batte VWCE: {(rad.extra_vwce > 0).mean():.0%}")
    print(f"Radiografie (screener) contro il proprio paniere: {rad.extra_paniere.mean():+.3f} su {rad.extra_paniere.notna().sum()} righe")
    for col in ["s_aut", "s_ver"]:
        x = pd.to_numeric(rad[col], errors="coerce")
        ok = x.notna() & rad.extra_vwce.notna()
        if ok.sum() >= 5:
            print(f"Spearman {col} vs extra VWCE: {x[ok].rank().corr(rad.extra_vwce[ok].rank()):+.2f} (n={ok.sum()})")
    print(f"Limiti toccati: {m.limite_toccato.mean():.0%} delle righe con limite")


if __name__ == "__main__":
    main()
