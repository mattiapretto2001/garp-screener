# fv3_03 (07/11): dizionario delle variabili di features_v3.pkl, con copertura per periodo e regione e controlli anti-sbirciata.
import os, sys, pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fv3
F = fv3.load()
DEF = {
 # VALUTAZIONE
 'pe': "P/E: capitalizzazione / utile netto degli ultimi 12 mesi (TTM). Solo con utile >0.",
 'ey': "Rendimento degli utili: utile netto TTM / capitalizzazione (inverso del P/E, definito anche in perdita).",
 'peg': "PEG storico: P/E / crescita % dell'utile TTM sull'anno prima (corretta per variazione azioni). Solo P/E>0 e crescita>0; PEG <0,05 = mancante (guardia).",
 'ev_ebitda': "EV / EBITDA TTM. EV = capitalizzazione + debito finanziario - cassa e investimenti a breve. Solo EBITDA>0 e EV>0.",
 'ebit_ev': "Utile operativo TTM / EV (rendimento operativo; definito anche in perdita). Solo EV>0.",
 'ev_sales': "EV / ricavi TTM. Solo EV>0.",
 'fcfy': "Free cash flow TTM / capitalizzazione.",
 'pb': "Capitalizzazione / patrimonio netto. Solo patrimonio >0.",
 # QUALITA
 'roe': "Utile netto TTM / patrimonio netto dell'ultimo bilancio. Solo patrimonio >0.",
 'roic': "ROIC approssimato: utile operativo TTM x 0,75 (tasse forfettarie 25%) / (patrimonio + debito - cassa). Solo capitale investito >0. Interessi passivi non disponibili.",
 'gpa': "Utile lordo TTM / totale attivo (redditivita' lorda alla Novy-Marx).",
 'gm': "Margine lordo TTM = utile lordo / ricavi (fra -100% e 99,9%).",
 'opm': "Margine operativo TTM = utile operativo / ricavi.",
 'npm': "Margine netto TTM = utile netto / ricavi.",
 'fcf_m': "Margine di free cash flow = FCF TTM / ricavi.",
 'fcf_ni': "Conversione in cassa = FCF TTM / utile netto TTM. Solo utile >0.",
 'accruals': "(Utile netto - flusso di cassa operativo) TTM / totale attivo. Alto = utili poco sostenuti da cassa.",
 'de': "Debito finanziario / patrimonio netto. Solo patrimonio >0.",
 'nd_ebitda': "(Debito - cassa) / EBITDA TTM. Solo EBITDA >0. Negativo = cassa netta.",
 'cur_ratio': "Attivo corrente / passivo corrente.",
 'neg_eq': "1 se il patrimonio netto e' <=0.",
 'n_loss_5y': "Anni chiusi in perdita negli ultimi 5 bilanci annuali gia' pubblicati (servono almeno 3 anni).",
 'n_loss_10y': "Anni chiusi in perdita negli ultimi 10 bilanci annuali (almeno 5).",
 'opm_avg5': "Media del margine operativo annuale, ultimi 5 bilanci (almeno 4).",
 'opm_std5': "Deviazione standard del margine operativo annuale, ultimi 5 bilanci (almeno 4). Basso = stabile.",
 'gm_std5': "Deviazione standard del margine lordo annuale, ultimi 5 bilanci (almeno 4).",
 'revg_std5': "Deviazione standard della crescita annua dei ricavi, ultimi 5 anni (almeno 4 confronti).",
 'n_revdown_5y': "Anni con ricavi in calo negli ultimi 5 (almeno 4 confronti).",
 # CRESCITA
 'revq': "Ricavi dell'ultimo trimestre (o semestre) / stesso periodo dell'anno prima - 1 (filtro 'ricavi trimestre' del GARP).",
 'revg_ttm': "Ricavi TTM / ricavi TTM di un anno prima - 1.",
 'rev_cagr': "Crescita annua composta dei ricavi su 4 anni (3 se mancano), dai bilanci annuali: e' quella dello screener GARP.",
 'rev_cagr3': "Crescita annua composta dei ricavi su 3 anni esatti (bilanci annuali).",
 'rev_cagr5': "Crescita annua composta dei ricavi su 5 anni esatti (bilanci annuali).",
 'epsg': "Crescita dell'utile per azione TTM sull'anno prima (utile netto corretto per variazione azioni). Solo utile un anno prima >0.",
 'epsq': "Come epsg ma sul singolo trimestre. Solo utile del trimestre un anno prima >0.",
 'accel_q': "Accelerazione: revq di oggi - revq misurata al trimestre precedente.",
 'accel_y': "Accelerazione annua: revg_ttm - la stessa crescita TTM di un anno prima.",
 'oplev': "Leva operativa: crescita dell'utile operativo TTM - crescita dei ricavi TTM. Solo utile operativo un anno prima >0.",
 'd_opm': "Variazione in 1 anno del margine operativo TTM.",
 'd_gm': "Variazione in 1 anno del margine lordo TTM (tendenza del margine lordo).",
 'turn_profit': "1 se utile netto TTM >0 e un anno prima <=0 (svolta verso l'utile).",
 # INVESTIMENTO
 'rd_int': "R&S / ricavi TTM. Mancante spesso = voce non riportata (per molte societa' vuol dire zero).",
 'sga_int': "Spese di vendita, generali e amministrative / ricavi TTM.",
 'capex_int': "Investimenti (capex, valore assoluto) / ricavi TTM.",
 'asset_g': "Crescita del totale attivo in 1 anno.",
 'dsh1': "Variazione delle azioni in circolazione in 1 anno (fra bilanci gia' pubblicati), corretta per frazionamenti visti nei prezzi; fuori da -75%/+300% = mancante. Positivo = diluizione.",
 'dsh3': "Come dsh1 su 3 anni (variazione totale, non annua).",
 # SOPRAVVIVENZA
 'burner': "1 se il FCF TTM e' negativo (la societa' brucia cassa).",
 'cash_mcap': "Cassa e investimenti a breve / capitalizzazione.",
 'burn_mcap': "Cassa bruciata in 12 mesi (-FCF se negativo, altrimenti 0) / capitalizzazione.",
 'runway_y': "Autonomia in anni = cassa / cassa bruciata all'anno; 10 = nessun consumo o oltre 10 anni.",
 'cash_debt': "Cassa / debito finanziario (tetto 10; 10 se debito nullo).",
 'netcash_mcap': "(Cassa - debito) / capitalizzazione.",
 # PREZZO
 'mom12_1': "Rendimento (con dividendi) da 12 mesi a 1 mese prima della data.",
 'mom6': "Rendimento degli ultimi 6 mesi.",
 'mom3': "Rendimento degli ultimi 3 mesi.",
 'mom1': "Rendimento dell'ultimo mese (effetto inversione di breve).",
 'hi52': "Prezzo / massimo delle ultime 52 settimane.",
 'ma200': "Prezzo / media delle ultime 200 sedute.",
 'vol1y': "Volatilita' annualizzata dei rendimenti giornalieri dell'ultimo anno.",
 'logmcap': "log10 della capitalizzazione in USD.",
 'log_adv': "log10 del valore scambiato giornaliero mediano (ultime 63 sedute) in USD.",
 'turnover': "Valore scambiato giornaliero / capitalizzazione.",
 'age_y': "Anni dalla quotazione (IPODate di EODHD; mancante se non dichiarata).",
 'hist_y': "Anni dal primo bilancio annuale nei dati EODHD (storia disponibile; per le vecchie societa' parte dal 1985-2000).",
 'fin_age_d': "Giorni fra la data e la chiusura dell'ultimo bilancio usato (quanto e' 'vecchio' il dato).",
 # ANALISTI
 'surp_last': "Sorpresa % dell'ultimo utile per azione annunciato rispetto alla stima media (solo stima diversa da ~0).",
 'surp_mean4': "Media delle sorprese degli ultimi 4 annunci (tagliate a +-100%).",
 'n_beat4': "Quanti degli ultimi 4 annunci sono stati sopra le stime.",
 'n_est4': "Quanti degli ultimi 4 annunci avevano una stima (copertura degli analisti).",
 # INDUSTRIA
 'ind_n': "Numero di societa' della stessa industria (classificazione EODHD) nell'universo alla data, tutte le regioni.",
 'ind_dshare4': "Variazione in 1 anno della quota dell'industria sul totale dell'universo (ondata di ingressi/quotazioni).",
 'ind_revg_med': "Crescita mediana dei ricavi TTM nell'industria.",
 'ind_revg_agg': "Crescita aggregata dei ricavi TTM dell'industria (somme in USD a cambio della data).",
 'ind_accel_agg': "Crescita aggregata di oggi - crescita aggregata di un anno prima (stesse societa').",
 'ind_accel_med': "Mediana di accel_y nell'industria.",
 'ind_mom_med': "Momentum 12-1 mediano dell'industria.",
 'ind_mom_pos': "Quota di societa' dell'industria con momentum 12-1 positivo.",
 'rel_revg_ind': "revg_ttm della societa' - crescita mediana dell'industria.",
 'rel_mom_ind': "Rango (0-1) del momentum 12-1 della societa' dentro la sua industria.",
 'rel_gm_ind': "Margine lordo della societa' - margine lordo mediano dell'industria.",
}
TDEF = {
 'r': "Rendimento del trimestre successivo (dalla data alla data dopo), valuta locale, dividendi inclusi. Per i backtest di portafoglio.",
 'r_eur': "Come r, in euro.",
 'fwd12_loc': "Rendimento composto dei 4 trimestri successivi, valuta locale. Societa' uscite dal listino: dopo l'uscita liquidita' a 0; fallimento -100%.",
 'fwd12_eur': "Come fwd12_loc, in euro. TARGET PRINCIPALE (a).",
 'xs12_reg': "fwd12_eur - media a pesi uguali di fwd12_eur di tutte le societa' della stessa regione (USA / Europa / Asia / Altri) alla data.",
 'rk12_reg': "Rango (0-1) di fwd12_eur nella regione alla data. Consigliato per le regressioni (target a).",
 'rk12': "Rango (0-1) di fwd12_eur nel mondo alla data.",
 'top5': "1 se rk12 >= 0,95 (5% migliore del mondo a 12 mesi) - 'eccezionale', target (b).",
 'top5_reg': "1 se rk12_reg >= 0,95 (5% migliore della regione).",
 'bot20': "1 se rk12 <= 0,20 (20% peggiore del mondo) - 'disastro', target (c).",
 'bot20_reg': "1 se rk12_reg <= 0,20.",
 'crash50': "1 se fwd12_loc <= -50% o fallimento entro 12 mesi - 'disastro' assoluto, target (c).",
 'bankrupt12': "1 se esce dal listino entro 12 mesi con ultimo prezzo <25% del massimo dell'anno prima (trattata come fallimento, -100%).",
 'delist12': "1 se esce dal listino entro 12 mesi per qualunque motivo (anche acquisizione).",
 'fwd36_loc': "Rendimento composto dei 12 trimestri successivi, valuta locale.",
 'fwd36_eur': "Come fwd36_loc, in euro.",
 'xs36_reg': "fwd36_eur - media della regione alla data.",
 'rk36_reg': "Rango (0-1) di fwd36_eur nella regione alla data.",
 'x3': "1 se fwd36_eur >= +200% (valore triplicato a 3 anni, misurato alla fine dei 3 anni).",
}
CDEF = {
 't': "Codice EODHD (CODICE.BORSA).", 'date': "Data di osservazione (fine trimestre, 2011-12-31 ... 2026-09-30). Tutte le variabili usano solo dati noti a questa data.",
 'name': "Nome.", 'ex': "Borsa EODHD.", 'country': "Paese (ISO).", 'region': "USA, Europa, Asia (Taiwan, Corea), Canada, Australia.",
 'reg': "Regione per i target: USA, Europa, Asia, Altri (Canada+Australia).",
 'reg_rob': "Gruppi per la robustezza: USA grandi (prime 500 USA per capitalizzazione alla data), USA piccole/medie (le altre), Europa, Asia, Altri.",
 'sector': "Settore EODHD (classificazione di OGGI).", 'sector_n': "Settore con i nomi GICS ricondotti a quelli EODHD.",
 'industry': "Industria EODHD (classificazione di OGGI; 256 valori).", 'excl_sector': "True se settore escluso dal GARP (finanza, materie prime, energia, servizi pubblici, immobiliare).",
 'cur_px': "Valuta del prezzo (GBX = pence, gia' corretti).", 'cur_rep': "Valuta di bilancio.",
 'per3': "Periodo per la robustezza, per data di formazione: 2012-16 (2011-12..2016-09), 2017-21 (2016-12..2021-09), 2022-26 (2021-12..2026-09).",
 'size': "Fascia di capitalizzazione alla data: piccola <2 Mld$, media 2-10, grande >10.",
 'delisted': "Societa' oggi uscita dal listino. INFORMAZIONE DAL FUTURO: mai come predittore.",
 'us_new': "Americana aggiunta il 07/11 (lista scelta con la liquidita' 2011-2026). INFORMAZIONE DAL FUTURO: mai come predittore.",
 'ext_fields': "La societa' ha i campi estesi (margine lordo, R&S, spese generali, attivo/passivo corrente, sorprese). USA: ~100%; fuori USA scaricati solo per societa' scelte ex post (vedi avvertenze).",
 'n_fail': "Numero di filtri GARP attuali non superati (0-8).", 'GARP': "Supera tutti i filtri GARP attuali.",
 'core': "GARP + ricavi trimestre >20% + prezzo >=80% del massimo a 52 settimane + capitalizzazione >=2 Mld$.",
}
RAWDEF = ("Grandezze grezze (valuta di bilancio salvo indicazione): px (prezzo corretto per frazionamenti), sh/sh0/sh4 (azioni: ultime note, "
          "alla chiusura dell'ultimo bilancio, un anno prima), mcap (valuta di bilancio), mcap_usd, ev, fx_px/fx_rep (USD per unita'), rev_ttm, rev_ttm4, "
          "rev_ttm8, rev_q, rev_qp, revq_prev, revg_ttm_prev, ni_ttm, ni_ttm4, ni_ttm8, ni_q, ni_qp, opi_ttm, opi_ttm4, ebitda_ttm, gp_ttm, gp_ttm4, "
          "rev_ttm4b, rd_ttm, sga_ttm, fcf_ttm, cfo_ttm, capex_ttm, equity, debt, cash, ta, ta4 (totale attivo ora e un anno prima), cur_a, cur_l, adv_usd, "
          "gm4, opm4, n_prof_y (anni in utile fra i 3 bilanci annuali prima dell'ultimo), n_years (bilanci annuali disponibili), src (Q = trimestrale/semestrale, "
          "Y = annuale), m0 (mese di chiusura dell'ultimo bilancio, indice anno*12+mese-1), cov (mesi coperti dall'ultimo bilancio: 3, 6, 12), "
          "fin_end (chiusura dell'ultimo bilancio usato), fin_av (data da cui e' utilizzabile), bal_end (chiusura dell'ultimo stato patrimoniale).")
DIRW = {1: 'alto meglio', -1: 'basso meglio', 0: 'dipende'}
FAMNAME = {'VALUTAZIONE': 'Valutazione', 'QUALITA': 'Qualita', 'CRESCITA': 'Crescita', 'INVESTIMENTO': 'Investimento e capitale',
           'SOPRAVVIVENZA': 'Sopravvivenza (pre-utile)', 'PREZZO': 'Prezzo e mercato', 'ANALISTI': 'Analisti', 'INDUSTRIA': 'Industria (per i temi)'}


def pc(x): return f'{100 * x:.0f}'


def cov_table(cols, defs, direction=True):
    L = ['| Variabile | Definizione | ' + ('Direzione a priori | ' if direction else '') + 'Tot. | 2012-16 | 2017-21 | 2022-26 | USA grandi | USA p/m | Europa | Asia | Altri |',
         '|---|---|' + ('---|' if direction else '') + '---|---|---|---|---|---|---|---|---|']
    for c in cols:
        nn = F[c].notna()
        bp = nn.groupby(F.per3, observed=True).mean(); br = nn.groupby(F.reg_rob, observed=True).mean()
        d = (DIRW[fv3.DIRECTION.get(c, 0)] + ' | ') if direction else ''
        L.append(f"| `{c}` | {defs[c]} | {d}{pc(nn.mean())} | " + ' | '.join(pc(bp.get(p, np.nan)) for p in fv3.PER3) + ' | '
                 + ' | '.join(pc(br.get(r, np.nan)) for r in fv3.REG_ROB) + ' |')
    return '\n'.join(L)


# controlli anti-sbirciata
us = F.ex == 'US'
lag_fin = (F.date - F.fin_end).dt.days; lag_bal = (F.date - F.bal_end).dt.days
chk = dict(fin_av_after=int((F.fin_av > F.date).sum()), nonus_lt75=int(((~us) & (lag_fin < 75)).sum()), nonus_bal_lt75=int(((~us) & (lag_bal < 75)).sum()),
           us_min=int(lag_fin[us].min()), nonus_min=int(lag_fin[~us].min()), med=int(lag_fin.median()))
# IC descrittivo
V = F[F.rk12_reg.notna()]
R = fv3.xs_rank(V, fv3.PREDICTORS); y = V.rk12_reg.astype(float)
rows = []
for c in fv3.PREDICTORS:
    d = pd.DataFrame({'x': R[c], 'y': y, 'date': V.date}).dropna()
    ic = d.groupby('date').apply(lambda z: np.corrcoef(z.x, z.y)[0, 1] if len(z) > 30 and z.x.std() > 0 else np.nan).dropna()
    pr = {p: ic[(ic.index >= a) & (ic.index <= b)].mean() for p, (a, b) in fv3.PER3.items()}
    rows.append(dict(var=c, ic=ic.mean(), t=fv3.nw_t(ic, 4), **pr))
IC = pd.DataFrame(rows).set_index('var'); IC.to_csv(f'{HERE}/fv3_ic_check.csv')
nu = F[(~us) & F.fwd12_eur.notna()]
sel = nu.groupby('ext_fields')[['rk12_reg', 'top5_reg', 'bot20_reg']].mean()
n_rows, n_co, n_dates = len(F), F.t.nunique(), F.date.nunique()
n_pred = len(fv3.PREDICTORS)
fam_cov = {f: F[c].notna().mean().mean() for f, c in fv3.FAMILIES.items()}
per_date = F.groupby('date').size()

md = []
md.append(f"""# Matrice delle variabili `features_v3`: dizionario

*Preparato il 07/11/2026. File: `ml/features_v3.pkl` (DataFrame pandas, una riga per societa' e trimestre). Script: `ml/fv3_01_extra.py`, `ml/fv3_02_build.py`, `ml/fv3_03_dizionario.py`; funzioni comuni in `ml/fv3.py`.*

## In breve

- **{n_rows:,} righe, {n_co:,} societa', {n_dates} date trimestrali** (31/12/2011 - 30/09/2026), da {per_date.min():,} a {per_date.max():,} societa' per data. Comprese le societa' uscite dal listino.
- **{n_pred} variabili predittive** in 8 famiglie, **{len(fv3.TARGETS)} target**, {len(CDEF)} colonne di contesto e una cinquantina di grandezze grezze ({F.shape[1]} colonne in tutto).
- Universo: lo stesso di `res/panel2.pkl` (liquidita' verificata alla data, capitalizzazione >=300 M$, ricavi TTM >0, pence di Londra corretti, doppioni tolti). **Tutti i settori sono inclusi**: `excl_sector` segna quelli esclusi dal GARP.
- Copertura media per famiglia: """ + '; '.join(f"{FAMNAME[f].lower()} {pc(v)}%" for f, v in fam_cov.items()) + f""".
- Target a 12 mesi disponibili fino alla data 30/09/2025; a 36 mesi fino al 30/09/2023.

## Come si carica

```python
import sys; sys.path.insert(0, '${RICERCA_BASE}/backtest_world/ml')
import fv3
F = fv3.load()                                   # tutto
R = fv3.xs_rank(F, fv3.PREDICTORS)               # ranghi 0-1 per data (consigliati: le variabili grezze hanno code estreme)
T = fv3.retarget(F, ~F.excl_sector)              # target ricalcolati dentro un sotto-universo
t = fv3.nw_t(serie_coefficienti, lags=4)         # t di Newey-West
for anno, train, test in fv3.walk_forward_splits(F.date, 2016, embargo_q=4): ...
```

`fv3.FAMILIES`, `fv3.PREDICTORS`, `fv3.DIRECTION` (direzione attesa a priori), `fv3.TARGETS`, `fv3.NOT_PREDICTORS`, `fv3.PER3`, `fv3.REG_ROB`.

## Regole usate (nessuna sbirciata nel futuro)

- **Bilanci:** un bilancio vale solo dalla data prudente di pubblicazione (`fin_av`): USA = data di deposito, o chiusura + 45 giorni se manca; resto del mondo = il piu' tardi fra deposito e chiusura + 75 giorni; tetto a 180 giorni per date di deposito assurde. Le variabili pluriennali (perdite in 5-10 anni, stabilita' dei margini, crescite a 3-5 anni) usano solo bilanci annuali gia' pubblicati alla data.
- **Prezzi:** solo sedute fino alla data. **Sorprese:** solo annunci avvenuti prima della data.
- **Azioni:** variazioni misurate fra le chiusure di bilanci gia' pubblicati, corrette per i frazionamenti.
- **Verifiche fatte:**
  - nessuna riga con `fin_av` successiva alla data ({chk['fin_av_after']} casi);
  - fuori dagli USA nessuna riga usa un bilancio chiuso da meno di 75 giorni ({chk['nonus_lt75']} casi; minimo osservato {chk['nonus_min']} giorni; stato patrimoniale: {chk['nonus_bal_lt75']} casi);
  - USA: minimo {chk['us_min']} giorni dalla chiusura (deposito rapido gia' avvenuto); mediana generale {chk['med']} giorni;
  - `fwd12_loc` coincide con `f12` di `panel2` nel 100% delle 187.850 righe;
  - ricalcolo indipendente (senza le funzioni di `world_04`) su 300 righe a caso: anni in perdita su 5 e crescita dei ricavi a 3 anni identici nel 100% dei casi; data dell'ultimo stato patrimoniale identica in 299 casi su 300 (nell'altro la matrice usa un bilancio piu' vecchio, quindi piu' prudente);
  - nessuna variabile ha una correlazione sospetta con il rendimento futuro: la piu' forte, in valore assoluto, e' {IC.ic.abs().max():.3f} (`{IC.ic.abs().idxmax()}`). Un errore di sbirciata di solito da' valori molto piu' alti (vedi tabella in fondo).

## Avvertenze (leggere prima di usare)

1. **Mai come predittori:** `delisted` e `us_new` (contengono il futuro), i target, `ended`. `sector` e `industry` sono la classificazione di oggi: usarle per raggruppare, non come segnale.
2. **Campi estesi fuori dagli USA scelti a posteriori.** Margine lordo (`gm`, `gpa`, `d_gm`, `gm_std5`, `rel_gm_ind`), R&S, spese generali, attivo/passivo corrente e sorprese esistono:
   - per quasi tutte le americane;
   - fuori dagli USA solo per le societa' scaricate il 07/11 perche' "vicine al GARP" in qualche data 2012-2026 o richieste dagli screener: circa 62% delle righe europee, 83% asiatiche, 40% Canada/Australia.
   
   La scelta e' stata fatta guardando tutto il periodo: il fatto che il dato manchi **non e' casuale**. Fuori dagli USA le societa' con campi estesi hanno rango medio {sel.loc[True, 'rk12_reg']:.3f} contro {sel.loc[False, 'rk12_reg']:.3f}, ma piu' estremi (top 5%: {100 * sel.loc[True, 'top5_reg']:.1f}% contro {100 * sel.loc[False, 'top5_reg']:.1f}%; peggiori 20%: {100 * sel.loc[True, 'bot20_reg']:.1f}% contro {100 * sel.loc[False, 'bot20_reg']:.1f}%). **Consiglio:** stimare queste variabili sugli USA; fuori dagli USA non usare mai "dato mancante" come informazione (colonna `ext_fields`).
3. **Code estreme:** le variabili sono grezze (ad esempio P/E fino a 10^10, crescite di migliaia di %). Usare i ranghi per data (`fv3.xs_rank`) o tagliare all'1-99% per data (`fv3.winsor`).
4. **Mancanti con significato:** `pe`, `peg`, `ev_ebitda`, `fcf_ni`, `epsg`, `oplev` mancano quando il denominatore e' <=0 (perdite). Per i profili "non ancora profittevoli" usare `ey`, `ebit_ev`, `fcfy`, `npm`, che restano definiti.
5. **Target sovrapposti:** con date trimestrali e orizzonte 12 mesi le osservazioni si sovrappongono per 3 trimestri: t di Newey-West con almeno 3-4 ritardi; nel walk-forward lasciare 4 trimestri di distacco fra addestramento e test (12 per i target a 36 mesi).
6. **Prove multiple:** con {n_pred} variabili, 3 target e 5 regioni, per puro caso ci si aspetta circa il 5% di t sopra 2 in valore assoluto ({n_pred * 3 * 5} prove -> circa {round(n_pred * 3 * 5 * 0.05)} falsi positivi). Contare le varianti provate e correggere (Bonferroni/Holm o soglia t >=3).
7. **Eta' dalla quotazione:** `age_y` c'e' quasi solo per gli USA (EODHD non dichiara la data di quotazione per ~90% delle societa' non americane): fuori dagli USA usare `hist_y`.
8. **Non disponibili:** copertura degli interessi (il campo interessi passivi non e' stato scaricato), stime degli analisti sul futuro (solo sorprese passate), dati prima del 2010 per i prezzi.
9. **Societa' senza ricavi** (biotech prima del lancio) **escluse** dall'universo (filtro ricavi TTM >0 di `panel2`). I "non ancora profittevoli" presenti sono quelle con ricavi e perdite: {pc((F.ni_ttm < 0).mean())}% delle righe hanno utile TTM negativo, {pc((F.fcf_ttm < 0).mean())}% FCF negativo.
10. **Dati rivisti:** EODHD fornisce i bilanci nella versione attuale (eventuali rettifiche successive incluse). Le azioni usate per la capitalizzazione sono quelle di fine trimestre di 2 mesi prima della data (come in `panel2`), non sempre gia' pubblicate fuori dagli USA: effetto piccolo.
11. **Fallimenti:** regola dei report precedenti (uscita con ultimo prezzo <25% del massimo dell'anno = -100%). E' approssimata: {int(F.bankrupt12.sum())} casi a 12 mesi su {int(F.fwd12_eur.notna().sum()):,} righe.
12. **Due righe** (GRF-P.MC, 30/09 e 31/12/2025) hanno un bilancio aggiornato dopo `panel2`: le variabili nuove di bilancio sono lasciate vuote.
""")
for f, cols in fv3.FAMILIES.items():
    md.append(f"## {FAMNAME[f]}\n\nCopertura in % delle righe (tutte le societa', tutti i settori).\n\n" + cov_table(cols, DEF) + '\n')
md.append("## Target\n\nNon usare mai come predittori. Ranghi ed eccessi calcolati su **tutte** le societa' della matrice (tutti i settori); per un sotto-universo usare `fv3.retarget`.\n\n"
          + cov_table(fv3.TARGETS, TDEF, direction=False) + '\n')
md.append("Medie: " + ', '.join(f"`{c}` {F[c].astype(float).mean():.3f}" for c in ['fwd12_eur', 'top5', 'bot20', 'crash50', 'bankrupt12', 'delist12', 'x3']) + '.\n')
md.append("## Contesto\n\n| Colonna | Significato |\n|---|---|\n" + '\n'.join(f"| `{c}` | {d} |" for c, d in CDEF.items()) + '\n')
cnt = F.groupby(['per3', 'reg_rob'], observed=True).size().unstack()[fv3.REG_ROB]
md.append("Righe per periodo e gruppo:\n\n| Periodo | " + ' | '.join(fv3.REG_ROB) + ' |\n|---|' + '---|' * len(fv3.REG_ROB) + '\n'
          + '\n'.join(f"| {p} | " + ' | '.join(f"{int(cnt.loc[p, r]):,}" for r in fv3.REG_ROB) + ' |' for p in cnt.index) + '\n')
md.append("## Grandezze grezze\n\n" + RAWDEF + '\n')
md.append("## Controllo di coerenza: correlazione con il rendimento futuro\n\n"
          "**Solo per scovare errori di sbirciata e segni sbagliati, non per scegliere le variabili** (non tiene conto delle altre variabili ne' delle regioni). "
          "Correlazione di rango, data per data, fra la variabile e `rk12_reg`, media 2012-2026; t di Newey-West con 4 ritardi. "
          f"Con {n_pred} variabili ci si aspettano circa {round(n_pred * 0.05)} |t| >2 per caso.\n\n"
          "| Variabile | Correlazione media | t | 2012-16 | 2017-21 | 2022-26 |\n|---|---|---|---|---|---|\n"
          + '\n'.join(f"| `{v}` | {r.ic:+.3f} | {r.t:+.1f} | {r['2012-16']:+.3f} | {r['2017-21']:+.3f} | {r['2022-26']:+.3f} |" for v, r in IC.sort_values('ic').iterrows()) + '\n')
open(f'{HERE}/features_v3_dizionario.md', 'w').write('\n'.join(md))
print('scritto', len('\n'.join(md)), 'caratteri'); print(chk); print(sel.round(3)); print({k: round(v, 3) for k, v in fam_cov.items()})
