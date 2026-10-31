# Piano di lavoro: migliorare screener e gestione del portafoglio

Scritto il 31/10/2026. Da eseguire in una sessione cloud con accesso completo alla rete.
Ogni fase si chiude con un commit su un ramo dedicato, una nota "cosa cambia" e, se serve, una PR verso `main`.
**Mai fare push diretto su `main`:** ogni push su `main` fa partire lo screener completo (vedi `.github/workflows/screener.yml`).

## Vincoli da rispettare sempre

- **La routine sul PC fisso** (`report-azionario-mattina`, alle 4:00) legge `results*/latest.json` e `snapshots/` per costruire la Bussola Azionaria.
  - Non rinominare né togliere campi esistenti: si possono solo **aggiungere**.
  - Se un formato deve cambiare, scrivi in `docs/CAMBI_FORMATO.md` cosa adattare nella routine.
- **Yahoo limita gli IP dei server cloud.** I download massivi (più di ~200 titoli) vanno fatti su GitHub Actions, divisi in shard come lo screener serale, non nel container della sessione.
- **Costo di GitHub Actions:** il job serale dura circa 45 minuti × 10 shard. Prima di aggiungere job pesanti, stima i minuti.
- **Il piano del portafoglio** è su OneDrive (`Claude/Cruscotti/piano_portafoglio.md`). Le regole automatiche devono replicarlo, non inventare soglie.

---

## Fase 1: qualità dei dati (priorità massima)

**Problema.** Il 29/10 il 16,5% dei titoli del GARP era in errore (1.660 su 10.041), sopra la soglia del 15%. ZAP.OL è sparita da tutti e tre gli screener per un errore di dati, non perché bocciata.
In `garp_screener.py` ci sono due difetti:
1. In `run_screen` la causa originale dell'errore viene sovrascritta da `"irrecuperabile dopo i retry"`: non sappiamo *perché* falliscono.
2. Un `.info` vuoto o parziale non è un errore. Il titolo viene bocciato in silenzio (settore `None` → `sector_ok` falso). Gli errori reali quindi sono più del 16,5%.

**Lavori.**
1. **Classificare gli errori:**
   - conservare la causa originale (429/limite di frequenza, timeout, ticker delistato, `.info` vuoto, campo mancante);
   - aggiungere a `latest.json` un campo `errori_per_tipo`;
   - trattare come "dato mancante" (non come bocciatura) i titoli con `.info` vuoto o senza i campi chiave.
2. **Distinguere "bocciato" da "non valutabile":** nei risultati, i promossi del giorno prima che oggi sono non valutabili restano in un elenco `sospesi_per_dati` invece di comparire come "usciti".
3. **Ridurre gli errori:**
   - backoff esponenziale con jitter al posto della pausa fissa di 25 s;
   - più shard (10 → 15-20) se i minuti di Actions lo permettono;
   - riuso della cache `.info` del giorno prima per i campi lenti (CAGR pluriennale, numero di azioni);
   - un terzo tentativo solo sui titoli in portafoglio, in watchlist o promossi ieri.
4. **Controllo di qualità automatico:**
   - se gli errori superano il 15%, il report lo scrive in testa;
   - se un titolo in portafoglio o in watchlist è non valutabile, va scritto esplicitamente.
5. **Obiettivo misurabile:** errori sotto il 5% su tutto l'universo e **zero** sui titoli in portafoglio e in watchlist, per 5 sere di fila.

---

## Fase 2: backtest serio e ripetibile

**Problema.** Il backtest del 27/10, che ha cambiato due regole, è stato fatto sul PC e il codice non è nel repository. Non si può rifare né verificare.

**Lavori.**
1. **Archivio dei dati storici:**
   - un job manuale su Actions (`workflow_dispatch`, shard) che scarica prezzi giornalieri rettificati e bilanci annuali e trimestrali per l'universo;
   - salvataggio compresso (parquet) come artifact o in un ramo `data`, non su `main`;
   - aggiornamento incrementale settimanale.
2. **Distorsione da sopravvivenza:**
   - includere i titoli usciti dagli indici o delistati (dalle liste storiche degli indici e dagli snapshot `snapshots/universo/` che già accumuliamo dal 10/10);
   - documentare quanto pesa il bias residuo.
3. **Niente dati dal futuro:** usare i fondamentali solo dalla data di pubblicazione (ritardo prudente di 45 giorni dalla chiusura del trimestre, 90 per l'annuale).
4. **Motore di backtest** (`backtest/` nel repository):
   - ribilanciamento mensile e trimestrale;
   - costi (commissione di 1 € come su Trade Republic, spread, imposta spagnola dello 0,2%, tassazione italiana del 26% sulle plusvalenze realizzate);
   - confronto con VWCE e con l'S&P 500 equipesato.
5. **Cosa misurare per ciascun criterio:**
   - rendimento in eccesso, massimo calo, volatilità, rotazione;
   - stabilità per sottoperiodi (anni buoni e cattivi) e per regione (USA e Europa).
   - Verificare in particolare: PEG ≤1 contro ≤1,2, peso dei riacquisti netti, momentum a 200 giorni, revisione delle stime a 90 giorni.
6. **Rapporto** in `docs/BACKTEST.md`, con il comando per rifarlo. Ogni regola del piano che cambia deve citare il risultato che la giustifica.

---

## Fase 3: le regole del piano diventano controlli automatici

**Problema.** Le condizioni d'ingresso sono scritte solo in prosa nel piano (per esempio ASML ≤1.470 €, Heijmans ordini ≥4,1 Mld). Il 30/10 ASML è scesa a ~1.416 € e nessun sistema l'ha segnalato.

**Lavori.**
1. **`regole.yaml` nel repository**, una voce per candidato e per posizione. Per esempio:
   ```yaml
   - ticker: ASML.AS
     tipo: ingresso
     condizioni: [{campo: prezzo, op: "<=", valore: 1470, valuta: EUR}]
     azione: "prima tranche 150-200 €"
     scadenza: 2027-01-31
     fonte_piano: "§4 Candidati"
   ```
   - Le condizioni che servono dati non automatizzabili (ordini nel trading update, case vendute) restano `manuale: true`. Il sistema le ricorda alla data dell'evento.
2. **Script `controlla_regole.py`**, da far girare dopo il merge serale. Produce `results-regole/latest.md` con: regole scattate, regole vicine alla soglia (entro il 3%), regole scadute.
3. **Tetti di portafoglio:** calcolo ogni sera di blocco AI, NU+KSPI, peso per titolo e volatilità, con allarme se si supera un tetto. Per ogni acquisto proposto, indicare l'effetto sui tetti (nel caso di ASML, il blocco AI dal 35,5% al ~37%).
4. **Avviso:**
   - un riepilogo breve (regole scattate più allarmi) che la routine del PC può includere nella Bussola;
   - in alternativa, una notifica ntfy al topic già usato dal campanello della Regia, se Mattia lo conferma.

---

## Fase 4: un'unica fonte per le posizioni

**Problema.** Esistono tre `portfolio.json` non allineati: quello nel repository, fermo al 05/08; quello letto dalla Bussola, "del 28/10"; quello citato dal piano "su Drive". Le quantità di TSM, AVGO e PRY sono stimate.

**Lavori.**
1. **Censimento:** trovare tutte le copie (repository, OneDrive, Google Drive), confrontarle e proporre a Mattia la versione corretta. **Non sovrascrivere nulla senza conferma.**
2. **Registro delle operazioni come fonte primaria:** `operazioni.csv` con data, ticker, ISIN, quantità, prezzo, valuta, commissioni e nota. Il `portfolio.json` diventa un file **calcolato** da quel registro.
3. **Portafoglio ombra:** gli stessi versamenti investiti ogni volta in VWCE. È il confronto richiesto dal §1 del piano, con verifica ad aprile 2027.
4. **Inserimento semplice da telefono:** un formato di una riga da scrivere in chat ("comprato 0,12 ASML a 1.416 €"), che la sessione converte e registra.

---

## Fase 5: indicatori di rischio di mercato

**Contesto.** Analisi del 30/10/2026, da salvare in `Claude/Cruscotti/schede/MERCATO_2026-10-30.md` su OneDrive (compito della sessione di riferimento). La preoccupazione principale è un panico sul debito legato all'AI.

**Lavori.** Script serale `rischio_mercato.py` → `results-rischio/latest.json` e `latest.md`, con valore, variazione a 1 e 4 settimane e soglia:

| Indicatore | Fonte | Allarme |
|---|---|---|
| VIX | Yahoo `^VIX` | > 25 (panico > 40) |
| Spread ad alto rendimento (ICE BofA HY OAS) | FRED `BAMLH0A0HYM2` | > 4,5% |
| Spread investment grade | FRED `BAMLC0A0CM` | > 1,5% |
| Treasury a 10 anni | FRED `DGS10` | > 5,3% |
| Ampiezza: % S&P 500 sopra la media a 200 giorni | calcolata da `snapshots/universo` | < 40% |
| Ampiezza: mediana della distanza dal massimo a 52 settimane | idem | < 80% |
| Big tech: debito netto/EBITDA, FCF trimestrale | `snapshots/universo` (AMZN, GOOGL, META, MSFT, ORCL, CRWV, NBIS) | ORCL > 4,5x; FCF negativo per 2 trimestri |
| CDS di Oracle e CoreWeave | non disponibili gratis: ricerca web settimanale, `manuale: true` | ORCL > 400 bp o declassamento a junk |

- Aggiungere una sezione "Rischio di mercato" nella Bussola: una riga per indicatore, con semaforo.
- Gli scenari sul portafoglio (correzione tecnologica, crisi del credito AI) vanno ricalcolati con le sensibilità stimate dai prezzi storici della Fase 2, invece delle ipotesi del 30/10.

---

## Ordine consigliato e uso dei crediti

1. **Fase 1** (qualità dei dati) e **Fase 4** (fonte delle posizioni) in parallelo: sono indipendenti e tutto il resto dipende da loro.
2. **Fase 3** (regole automatiche) e **Fase 5** (rischio), appena le posizioni sono affidabili.
3. **Fase 2** (backtest): è la più costosa, da avviare quando l'archivio dei dati è pronto. Si presta a un lavoro con più agenti, uno per criterio da verificare.

Ogni fase si chiude con: test o prova su un campione, run di prova su Actions (`workflow_dispatch` sul ramo), nota per la routine del PC e aggiornamento di questo file con lo stato.
