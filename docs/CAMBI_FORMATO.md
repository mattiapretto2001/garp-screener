# Cambi di formato dei risultati

Registro dei cambi a `results*/latest.json`, `latest.md` e `snapshots/` che interessano la routine sul PC (`report-azionario-mattina`).
Regola: i campi esistenti non si rinominano e non si tolgono, si aggiungono solo campi nuovi.

## 03/11/2026: Svolta versione B1 (ramo `claude/svolta-b1`)

Lo screener Svolta segue il backtest del 03/11/2026: la versione completa non batte l'universo fuori campione, regge solo il nucleo "B1".
Nessun campo di `results-svolta/latest.json` è stato tolto o rinominato.

### Campi nuovi in `results-svolta/latest.json`

| Campo | Dove | Significato |
|---|---|---|
| `versione_criteri` | in testa | `"B1 (backtest del 03/11/2026)"`. |
| `da_radiografare` | in testa | Ticker da analizzare: tutti i promossi se sono 8 o meno, altrimenti i primi 8 per punteggio. |
| `regola_radiografia`, `punteggio_uso` | in testa | Testo che spiega la regola degli 8 e che il punteggio serve solo a ordinare. |
| `da_radiografare` | in ogni promosso | `true` se il titolo è tra quelli da radiografare. |
| `avvisi` | in ogni titolo | Lista di avvisi di rischio (non escludono): diluizione > 10% l'anno, cassa per meno di 2 anni al consumo attuale. |
| `cosa_fa_en` | in ogni titolo | Descrizione breve originale in inglese. |
| `margine_lordo_metodo` | in ogni titolo | Come è misurata `margine_lordo_variazione` ("12 mesi su 12 mesi", "trimestre sullo stesso dell'anno prima", "anno fiscale"). |
| `margine_lordo_trimestre` | in ogni titolo | Margine lordo dell'ultimo trimestre. |
| `margine_operativo_trimestre_2fa` | in ogni titolo | Margine operativo di due trimestri prima (per il controllo "ultimo trimestre non peggiore"). |
| `primo_utile` | in ogni titolo e in `checks` | Solo informazione: EPS 12 mesi vicino a zero e stima dell'anno prossimo positiva. Non è più un filtro né un bonus. |
| `revisioni_nota` | in ogni titolo | "non verificabile storicamente: solo informazione e punteggio ridotto". |

### Cambi di significato (nessun campo tolto)

1. **`hard_checks`** ora contiene solo `mcap_ok`, `settore_ok`, `svolta_ok`, `crescita_ok`, `margine_lordo_ok`. `passed`, `failed_checks` e `near_miss` si basano solo su questi.
2. **`checks`**: `revisioni_ok`, `prezzo_ok`, `runway_ok`, `diluizione_ok`, `leva_ok`, `copertura_ok` restano, ma sono **solo informativi** (non escludono).
3. **`checks.mcap_ok`**: capitalizzazione 1-15 Mld$ (era 200 M$–20 Mld$).
4. **`checks.crescita_ok`**: ricavi dell'ultimo trimestre +20%/+60% (era fino a +100%).
5. **`checks.svolta_ok`**: margine operativo 12 mesi +5 punti in un anno (o ultimo trimestre +8 sullo stesso dell'anno prima), livello dei **12 mesi** tra -15% e +20% (prima era l'ultimo trimestre), ultimo trimestre non peggiore di due trimestri prima. Non vale più la strada del "primo utile" né il requisito di utile atteso l'anno prossimo.
6. **`checks.margine_lordo_ok`** e **`margine_lordo`**: `margine_lordo` è ora il margine lordo degli **ultimi 12 mesi** (prima: ultimo trimestre; quello è in `margine_lordo_trimestre`). Soglia 55% (40% industria/hardware) e **nessun calo** rispetto a 4 trimestri prima; non vale più la strada "≥ 25% e in salita".
7. **`cosa_fa`**: ora in italiano semplice (traduzione dei primi termini; il resto può restare in inglese). L'originale è in `cosa_fa_en`.
8. **`punteggio`, `punteggio_100`**: servono solo a ordinare, nessuna soglia d'acquisto (tolta la ★ e la soglia 6,5 dal Markdown). Somma delle voci su 80 punti riportata su base 100.
9. **`punteggio_dettaglio`**: stesse chiavi. `revisioni` vale al massimo 5 (era 15). `posizione_prezzo` vale 10 se il prezzo è 1,2-1,8 volte il minimo a 52 settimane, altrimenti 0, con -3 sopra il 95% del massimo. `prezzo_crescita`, `scoperta` e `penalita` valgono sempre 0 (non più nel punteggio). In `margine_operativo` non c'è più il bonus per il primo utile o per il passaggio da perdita a utile.
10. **`criteria`**: nuove chiavi `x_52w_low_score_min`, `x_52w_low_score_max`, `pct_of_52w_high_penalty`; `mcap_ideal_min_usd`, `mcap_ideal_max_usd`, `gross_margin_floor_rising`, `insider_sell_heavy` restano con valore `null` (non più usate). `mcap_min_usd`/`mcap_max_usd` = 1e9/15e9, `rev_growth_max` = 0,60, `gross_margin_drop_max` = 0.
11. Il primo filtro sulla cache non scarta più per posizione del prezzo né per numero di analisti. Le stime mancanti non sono più un errore da ritentare (contano solo nel punteggio).

### `latest.md` (Svolta)

- In testa: è un elenco da radiografare, non da comprare; risultati del backtest (+10,5 / +22 / -6,7 punti annui sull'universo nel 2012-19, 2020-24, 2025-26); regola degli 8; ricontrollo ogni trimestre.
- Riga "Da radiografare (N): ..." e segno "da radiografare" accanto ai titoli in classifica.
- Riga "⚠ Avvisi" sotto i titoli con diluizione o cassa insufficiente.

## 03/11/2026: Fase 1, qualità dei dati (ramo `claude/fase1-qualita-dati`)

### Campi nuovi in `results/latest.json` (GARP) e `results-moonshot/latest.json` (Moonshot)

| Campo | Tipo | Significato |
|---|---|---|
| `errori_per_tipo` | oggetto `{tipo: conteggio}` | Titoli non valutabili per causa, dal più frequente. |
| `errori_pct` | numero (0-1) | `errors / analyzed`, arrotondato a 4 decimali. |
| `sospesi_per_dati` | lista di ticker | Promossi del report precedente che oggi sono **non valutabili per errore di dati**: non sono stati bocciati. |
| `watchlist_non_valutabili` | lista di `{ticker, tipo, errore}` | Titoli di `watchlist.txt` (e di `portafoglio.txt`, se esiste) presenti nell'universo e oggi non valutabili. |

Tipi di errore possibili:

- `limite_frequenza`: Yahoo ha risposto 429 o 401 "Invalid Crumb" (blocco dell'IP), con `.info` vuoto o parziale;
- `timeout`: la richiesta è scaduta (anche con `.info` parziale);
- `non_trovato`: 404, ticker non trovato o delistato;
- `info_vuoto`: `.info` vuoto (ticker inesistente o delistato, oppure risposta vuota di Yahoo: di solito è un limite di frequenza mascherato);
- `campi_mancanti`: `.info` presente ma senza prezzo, o senza settore o capitalizzazione quando decidono il verdetto (vedi sotto), oppure bilancio annuale non scaricabile per un titolo che ha passato lo stadio 1;
- `rete`: errore di connessione;
- `altro`: qualsiasi altra eccezione;
- `sconosciuto`: solo per parziali vecchi, scritti prima di questo cambio.

### Campi nuovi in `results-temi/latest.json` (Temi)

Gli stessi quattro: `errori_per_tipo`, `errori_pct`, `sospesi_per_dati`, `watchlist_non_valutabili`.
Per i Temi, `sospesi_per_dati` contiene i titoli **seguiti** (in `tracked`) nel report precedente che oggi sono in errore.
Il campo esistente `errors` resta la lista dei ticker in errore.

### Cambi di significato da conoscere (nessun campo rinominato)

1. **`errors` (GARP e Moonshot) conta anche i dati vuoti o parziali.**
   Prima un titolo con `.info` vuoto, o senza settore, capitalizzazione o prezzo, era bocciato in silenzio (`sector_ok` falso).
   Ora è un errore, cioè "non valutabile", in questi casi:
   - `.info` vuoto (tipo `info_vuoto`, `non_trovato` o `limite_frequenza`, secondo la risposta HTTP);
   - campi chiave mancanti mentre yfinance ha avuto un errore 401/429/timeout: è un `.info` parziale (tipo `limite_frequenza` o `timeout`);
   - prezzo mancante (`campi_mancanti`);
   - settore o capitalizzazione mancanti **e decisivi**, cioè il titolo supera tutti gli altri controlli dello stadio 1 (`campi_mancanti`).
   Settore o capitalizzazione mancanti e non decisivi restano una bocciatura, come prima.
   Sono warrant, unit di SPAC, obbligazioni quotate e investment trust che non hanno quei campi per costruzione.
   Nel run di prova del 03/11 erano circa 1.300: contarli come errori avrebbe portato gli errori al 13% senza alcun problema di scarico.
   Fondi ed ETF (`quoteType` diverso da `EQUITY`) restano bocciati come prima, non sono errori.
2. **`dropped_since_yesterday` non cambia.**
   Contiene ancora tutti i promossi di ieri che oggi non sono promossi, **compresi** quelli in `sospesi_per_dati`.
   Per avere gli usciti veri, cioè bocciati: `set(dropped_since_yesterday) - set(sospesi_per_dati)`.
3. **GARP, stadio 2:** se il bilancio annuale non si scarica dopo 3 tentativi, il titolo è un errore `campi_mancanti` invece di essere bocciato sul CAGR dei ricavi.
4. **Temi:** la scoperta automatica considera le capitalizzazioni da 300 M (era 1 Mld) e fino a 120 titoli (erano 40), i più grandi per primi. In `tracked` compaiono più titoli con `discovered: true`.

### `latest.md`

- In testa, se gli errori superano il 15% dei titoli analizzati, compare un avviso "Qualità dati insufficiente" con la ripartizione per tipo.
- Se un titolo di watchlist o portafoglio è non valutabile, c'è una riga esplicita che lo nomina.
- Se ci sono sospesi per dati, c'è una riga che li elenca.
- La riga di riepilogo del GARP e del Moonshot termina con "| Non valutabili: N".

### `snapshots/`

- `snapshots/universo/*.csv.gz` (fotografia del venerdì): nuova colonna `quoteType`, in coda. Le altre colonne non cambiano.
- Gli altri snapshot non cambiano.

### Cosa può usare la routine

- **Allarme di qualità:** `errori_pct > 0.15`, oppure l'avviso in testa a `latest.md`.
- **Usciti veri:** `dropped_since_yesterday` meno `sospesi_per_dati`. Un titolo sospeso non va segnalato come "uscito": va scritto "non valutabile oggi".
- **Portafoglio e watchlist:** `watchlist_non_valutabili` dice quali titoli seguiti non hanno dati oggi.

### Comportamento interno (non cambia i file)

- Tra una passata e l'altra c'è una pausa a backoff esponenziale con jitter (circa 15-30 s, poi 30-45 s, poi 60-75 s), al posto dei 25 s fissi.
- I titoli di watchlist, portafoglio e i promossi di ieri hanno un quarto tentativo, a concorrenza 2.
- Un ticker con risposta 404 "quote not found" (`non_trovato`) non viene ritentato, salvo se prioritario. Se una passata successiva dà 401/429, resta `non_trovato`.
- yfinance non solleva gli errori HTTP di `.info`: restituisce un dizionario vuoto e scrive l'errore nel suo logger. Lo screener legge quel logger per dire se un `.info` vuoto viene da un limite di frequenza (401 "Invalid Crumb", 429) o da un ticker inesistente (404).
- `portafoglio.txt` è facoltativo, un ticker per riga, `#` per i commenti. Non è nel repository: le posizioni non vanno nel repository pubblico.
- Nei parziali (`partials/*.json`) i titoli in errore hanno `error` con la causa originale, più `error_type` e `tentativi`. Prima `error` valeva "irrecuperabile dopo i retry".

## 06/11/2026: GARP con PEG fino a 2, punteggio e top 30

Le scelte vengono dal backtest `REPORT_garp_peg2_2026-11-06.md`, su OneDrive in Claude/_scratch/backtest_screener.

### Cosa cambia nel filtro

- `criteria.peg_max` passa da 1.0 a **2.0**.
- Nuovo `criteria.peg_classico_max` = 1.0, che separa le due fasce.
- Il filtro sugli utili trimestrali **non cambia**. La tolleranza provata il 06/11 è stata tolta: nel backtest toglieva circa 6 punti l'anno nel 2025-26.

### `results/latest.json`: campi nuovi (nessuno tolto o rinominato)

- Su ogni titolo di `passed`:
  - `fascia_peg`: `"classica"` (PEG < 1) oppure `"allargata"` (PEG 1-2).
  - `punteggio_garp`: da 0 a 100, percentile pesato fra i promossi del giorno, solo sulle variabili dei filtri. Pesi: PEG 30 (più basso è meglio), crescita dei ricavi trimestrale 12, crescita degli utili trimestrale 12, CAGR dei ricavi 12, ROE 12, rendimento del FCF 11, D/E 11 (più basso è meglio). Un dato mancante vale come mediano.
  - `top30`: `true` per i primi 30 per punteggio.
- In testa al report:
  - `passed_fascia_classica` e `passed_fascia_allargata`: i conteggi delle due fasce.
  - `pesi_punteggio`: i pesi qui sopra.
  - `top_n`: vale 30.
  - `ordinamento_passed`: spiega l'ordine di `passed`.

### Cosa cambia nel comportamento

- **`passed` è ordinato per `punteggio_garp` decrescente**, non più per PEG crescente.
- **`latest.md`:** una riga con i conteggi delle due fasce e tre colonne nuove nella tabella: "Punteggio", "Top 30" e "Fascia".
- **`snapshots/garp/*.csv`:** tre colonne nuove in coda, `fascia_peg`, `punteggio_garp` e `top30`. Nel Moonshot restano vuote.

### Cosa può usare la routine

- **Le proposte dal GARP vengono dai titoli con `top30` = true.** Nel backtest il portafoglio dei primi 30 ha battuto la lista intera dal 2020, con la perdita massima più bassa. La fascia PEG 1-2 da sola rendeva meno.
- Un titolo in fascia "allargata" richiede di verificare il PEG prospettico, come prima.
- **`new_today` aumenta il primo giorno**, perché entrano i titoli con PEG fra 1 e 2. Non sono "nuovi" in senso stretto.
