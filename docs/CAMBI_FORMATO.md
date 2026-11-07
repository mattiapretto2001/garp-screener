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

## 07/11/2026: GARP core, radar e protezione dal PEG falso

Le scelte vengono da `REPORT_screener_finale_2026-11-07.md` (backtest mondiale EODHD con le aziende uscite dalla Borsa), su OneDrive in Claude/_scratch/backtest_screener.

### Criteri nuovi in `criteria`

- `peg_sospetto_sotto`: 0.05.
- `core_mcap_min`: 2e9.
- `core_ricavi_trim_min`: 0.20.
- `core_pct_max52_min`: 0.80.
- `radar_a_ricavi_trim_min`: 0.40.
- `radar_a_cagr_min`: 0.15.
- `radar_a_azioni_max`: 0.10.

La lista ampia `passed` **non cambia criteri**: resta il GARP con PEG < 2.

### Campi nuovi su ogni titolo analizzato

- `pct_max_52s`: prezzo diviso per il massimo a 52 settimane.

### Campi nuovi sui titoli in `passed`

- `core`: `true` se valgono tutte e tre le condizioni:
  - capitalizzazione ≥ 2 Mld$;
  - ricavi del trimestre oltre +20% sull'anno prima;
  - prezzo ≥ 80% del massimo a 52 settimane.
- `peg_sospetto`: `true` se il PEG è sotto 0,05. In quel caso il PEG conta come dato mancante, cioè come valore mediano, nel `punteggio_garp`.

### Cosa cambia in `top30`

- `top30` ora si calcola **solo fra i titoli con capitalizzazione ≥ 2 Mld$**. Nel backtest il GARP sotto i 2 Mld$ rendeva meno delle aziende della stessa taglia.

### Campi nuovi in testa al report

- `core_count` e `core`: i ticker in ordine di punteggio.
- `radar_a_count` e `radar_a`, fino a 60 titoli. È l'**iper-crescita**, fuori dal GARP:
  - settore ammesso;
  - capitalizzazione ≥ 2 Mld$;
  - ricavi del trimestre oltre +40%;
  - CAGR dei ricavi oltre il 15%;
  - azioni in circolazione al massimo +10% in un anno.
  
  Su ciascuno ci sono `radar_a`, `sales_cagr_multi_year` e `variazione_azioni_1a`.
- `radar_b_count` e `radar_b`, fino a 60 titoli: i titoli **esclusi solo dal PEG** (PEG ≥ 2), con capitalizzazione ≥ 2 Mld$. Su ciascuno c'è `radar_b`.
- `top30_mcap_min` e `nota_radar`.

### `latest.md`

- Tre sezioni nuove in fondo: "Core GARP", "Radar A" e "Radar B".

### `snapshots/garp/*.csv`

- Tre colonne nuove in coda: `core`, `peg_sospetto` e `pct_max_52s`.

### Cosa può usare la routine

- **Proposte d'acquisto:** prima i titoli `core`, poi gli altri `top30`.
- **Radar A e Radar B:** solo candidati per le Radiografie, mai acquisti diretti.
- **`peg_sospetto`:** se è `true`, il PEG va verificato su stockanalysis prima di citarlo.

## 08/11/2026: guardia di sicurezza, lista da radiografare, fotografie di punteggi e stime

Le scelte vengono da `REPORT_punteggi_profili_2026-11-07.md`, `REPORT_screener_finale_2026-11-07.md` e `REPORT_screener_tutti_2026-11-07.md` (backtest mondiale EODHD).
I segnali che hanno retto a tutti i controlli servono soprattutto a evitare i disastri: forte diluizione, prezzo molto sotto il massimo dell'anno, stime degli analisti mancate.
Nessun campo esistente è stato tolto o rinominato.

### 1. Guardia di sicurezza nel GARP (`results/latest.json`)

**Regola.** Un titolo esce da `passed`, da `radar_a` e da `radar_b` se:

- le azioni in circolazione sono cresciute di **oltre il 25% in un anno** (`variazione_azioni_1a`), oppure
- il prezzo è **sotto il 40% del massimo a 52 settimane** (`pct_max_52s_verificato` se c'è, altrimenti `pct_max_52s`).

**Frazionamenti.** Il massimo a 52 settimane di Yahoo (`fiftyTwoWeekHigh`) dopo un frazionamento delle azioni resta per mesi sul prezzo vecchio.
Esempio: FCIT.L (frazionamento 4:1 l'11/05/2026) ha massimo 1.351 contro 356 reale, quindi 24% invece di 92%; lo stesso per CGT.L (10:1) e BRSC.L (5:1).
Per questo, prima di escludere un candidato (promosso, radar A o radar B) sotto il 40%, lo screener ricalcola il rapporto sullo storico prezzi di un anno, che è rettificato per i frazionamenti (una chiamata a Yahoo in più, solo per questi pochi titoli).
Il risultato va nel campo nuovo `pct_max_52s_verificato`; `pct_max_52s` resta il valore di prima.
Se lo storico non c'è, vale `pct_max_52s` e la nota lo dice.
Un crollo vero (es. WGS) resta escluso: lo storico conferma il massimo.

Un dato mancante non esclude, ma viene segnalato: `sicurezza_dati_mancanti` dice quale dato manca (anche uno solo dei due).
Gli esclusi non spariscono: finiscono nella lista nuova `esclusi_sicurezza`, con il motivo, **una riga per titolo** anche se esce da più liste.

**Stime mancate.** Se almeno 3 delle ultime 4 trimestrali sono sotto le stime degli analisti, il titolo **resta in `passed`** ma **non può essere in `top30` né in `core`**.
Il posto in top 30 passa al titolo successivo per punteggio.

#### Criteri nuovi in `criteria`

- `sicurezza_diluizione_max`: 0.25.
- `sicurezza_pct_max52_min`: 0.40.
- `stime_mancate_min`: 3.

#### Campi nuovi in testa al report

| Campo | Significato |
|---|---|
| `regola_sicurezza` | La regola della guardia, in italiano. |
| `esclusi_sicurezza_count` | Quanti titoli la guardia ha tolto (GARP, radar A e radar B insieme). |
| `esclusi_sicurezza` | I titoli tolti, con tutti i loro campi più quelli sotto. |
| `regola_stime_mancate` | La regola delle stime mancate, in italiano. |
| `con_stime_mancate_count`, `con_stime_mancate` | Quanti e quali promossi hanno `stime_mancate` = true. |
| `sicurezza_non_verificabile_count`, `sicurezza_non_verificabile` | Quanti e quali titoli di `passed`, `radar_a` e `radar_b` hanno almeno un dato della guardia mancante (ticker, una volta sola). Restano in lista. |

#### Campi nuovi sui titoli

| Campo | Dove | Significato |
|---|---|---|
| `sicurezza_ok` | `passed`, `radar_a`, `radar_b`, `esclusi_sicurezza` | `true` = guardia superata con i dati che ci sono (se ne manca uno lo dice `sicurezza_dati_mancanti`); `false` = escluso; `null` = mancano sia prezzo/massimo sia diluizione (non verificabile, resta in lista). |
| `sicurezza_motivi` | stessi | Lista di motivi: `"diluizione"`, `"lontano_dal_massimo"`. Vuota se nessuno. |
| `sicurezza_dati_mancanti` | stessi | Dati della guardia che mancano: lista con `"pct_max_52s"` (prezzo/massimo a 52 settimane) e/o `"variazione_azioni_1a"` (variazione delle azioni). Vuota se ci sono tutti e due. Il titolo non viene escluso per questo. |
| `sicurezza_nota` | `esclusi_sicurezza` | Il motivo in italiano, con i numeri (es. "prezzo al 34% del massimo a 52 settimane (soglia 40%, verificato sullo storico prezzi)"). |
| `lista_origine` | `esclusi_sicurezza` | Da quale lista è uscito: `"garp"`, `"radar_a"` o `"radar_b"`. Se esce da più liste (radar A e radar B insieme) è la prima, nell'ordine garp, radar_a, radar_b. |
| `liste_origine` | `esclusi_sicurezza` | Tutte le liste da cui è uscito, es. `["radar_a", "radar_b"]`. |
| `pct_max_52s_verificato` | ogni risultato del GARP (`passed`, `near_miss`, radar, esclusi) | Prezzo/massimo a 52 settimane ricalcolato sullo storico prezzi di un anno (rettificato per i frazionamenti). Calcolato solo per i candidati (promossi, radar A, radar B) con `pct_max_52s` sotto 0.40; `null` negli altri casi o se lo storico non c'è. |
| `esclusa_sicurezza` | `esclusi_sicurezza` | Sempre `true`. |
| `stime_mancate` | `passed` | `true` se almeno 3 delle ultime 4 trimestrali sono sotto le stime. |
| `stime_mancate_4t` | `passed` (e `esclusi_sicurezza` del GARP) | Quante delle ultime 4 trimestrali sono sotto le stime (utile effettivo meno stima; una perdita minore del previsto conta come battuta). `null` se Yahoo non ha lo storico. |
| `sorprese_4t_n` | stessi | Su quante trimestrali è fatto il conto (al massimo 4). |
| `variazione_azioni_1a` | `radar_b` | Ora calcolata anche per i candidati al radar B (prima solo per promossi e radar A). |

#### Cambi di significato

1. **`passed` e `passed_count` escludono gli esclusi per sicurezza.** Nei titoli esclusi `passed` vale `false`.
2. **`radar_a` e `radar_b` escludono gli esclusi per sicurezza.** Il radar A aveva già il tetto di diluizione al 10%: lì conta solo il prezzo.
3. **`top30` e `core`** includono anche i titoli con `stime_mancate` = true: l'etichetta è solo un avviso (decisione del 08/11/2026 dopo il backtest 2018-2026, dove escluderli peggiorava i risultati).
   Per la soglia del core (prezzo ≥ 80% del massimo) si usa `pct_max_52s_verificato` quando c'è, altrimenti `pct_max_52s` come prima.
4. **Il primo giorno** gli esclusi compaiono anche in `dropped_since_yesterday`: sono usciti per la guardia, non per i filtri GARP.
   Con i prezzi del 06/11 la guardia avrebbe tolto circa 12 promossi su 144, tutti per il prezzo: SNDK, WDC, CRDO, ALAB, RDDT, ALNY, STRL, AGX, IESC, RSI, INOD, POWL.
5. **`near_miss`** non cambia. Un candidato al radar B escluso resta nei `near_miss`, con `sicurezza_ok` = false.
6. **`esclusi_sicurezza_count`** conta ogni titolo una volta sola: un titolo che è sia in radar A sia in radar B ed esce dalla guardia compare in una riga, con `liste_origine` = `["radar_a", "radar_b"]`.

#### `latest.md` (GARP)

Tre sezioni nuove in fondo: "Esclusi per sicurezza" (con il motivo e la lista d'origine, es. "da Radar A e Radar B"), "Sicurezza non verificabile" (titoli rimasti in lista con un dato della guardia mancante, e quale) e "Stime mancate".

#### `snapshots/garp/*.csv` e `snapshots/moonshot/*.csv`

- Cinque colonne nuove in coda: `sicurezza_ok`, `stime_mancate`, `stime_mancate_4t`, `variazione_azioni_1a`, `pct_max_52s_verificato`.
- Nel GARP ci sono anche le righe degli esclusi, con `stato` = `"esclusa_sicurezza"`.
- Nel Moonshot è valorizzata solo `stime_mancate_4t`; le altre restano vuote.

### 2. Moonshot e Svolta

**Moonshot (`results-moonshot/latest.json`): regole non toccate.**
- La diluizione è già un filtro: azioni al massimo +15% l'anno, in media sugli anni di bilancio disponibili.
- Il prezzo ≥ 70% del massimo **non è un filtro** dal 27/10/2026: il filtro è prezzo sopra la media a 200 giorni; sotto il 70% c'è solo l'etichetta `momentum_solo_200gg` in `criteri_nuovi`. Il 07/11 erano 9 su 100 sotto il 70%, nessuno sotto il 40%.
- Campi nuovi sui promossi, solo informativi: `stime_mancate_4t` e `sorprese_4t_n` (vengono dalla funzione delle stime condivisa con il GARP).

**Svolta (`results-svolta/latest.json`): solo un'etichetta, nessuna esclusione.**

| Campo | Dove | Significato |
|---|---|---|
| `sicurezza_ok` | ogni titolo | Stessa guardia del GARP (diluizione dell'ultimo anno, prezzo/massimo): `true`, `false` o `null`. |
| `sicurezza_motivi` | ogni titolo | `"diluizione"`, `"lontano_dal_massimo"`. |
| `sicurezza_nota` | ogni titolo | Il motivo in italiano, vuoto se non ce n'è. |
| `sicurezza_dati_mancanti` | ogni titolo | Come nel GARP: `"pct_max_52s"` e/o `"variazione_azioni_1a"` se mancano (qui la diluizione è il campo `diluizione`). |
| `pct_max_52s_verificato` | ogni titolo | Come nel GARP: per i promossi sotto il 40% del massimo, prezzo/massimo ricalcolato sullo storico prezzi (frazionamenti); `null` negli altri casi. L'etichetta usa questo valore quando c'è. |

`passed`, `hard_checks`, `checks` e punteggio non cambiano.
In `latest.md`, sotto i titoli che non superano la guardia, c'è la riga "⚠ Guardia di sicurezza non superata (solo etichetta)"; se manca un dato, la riga "⚠ Sicurezza non verificabile: manca …".
Nella tabella "Gli altri promossi" gli stessi avvisi sono nella colonna Avvisi.

### 3. Lista unica da radiografare (`results-lista/`, nuova cartella)

Script `lista_radiografare.py`, nel job di merge dopo tutti gli screener.
File: `results-lista/latest.json`, `latest.md` e `<data>.json`.

**Chi entra.** I titoli segnalati da almeno una di queste **famiglie**:

- **GARP**: core o top 30 (contano come **una sola** famiglia; i segnali `GARP-core` e `GARP-top30` restano distinti);
- **Radar A**;
- **Radar B**;
- **Moonshot**;
- **Svolta**.

I **Temi** non sono una famiglia: danno solo l'etichetta `"tema: <nome>"` ai titoli già in lista, se il semaforo è verde o giallo.
Una riga per società: i ticker sono normalizzati (maiuscole; `BRK.B` diventa `BRK-B`) e le quotazioni con lo stesso nome di società sono unite (es. GOOG e GOOGL; gli altri ticker vanno in `altri_ticker`).

**Guardia di sicurezza, uguale per tutti.** Esce dalla lista chi ha prezzo sotto il 40% del massimo o azioni oltre +25% in un anno.
Per Moonshot e Temi la diluizione disponibile è la media annua su più anni.
Per GARP e Svolta si usa `pct_max_52s_verificato` quando c'è (frazionamenti, vedi sopra).
Un dato mancante non esclude: lo dice `sicurezza_dati_mancanti` e, in `latest.md`, la colonna Sicurezza.
Gli esclusi vanno in `esclusi_sicurezza`.
Con i file del 07/11 sarebbero usciti ALGM (Svolta) e CRDO (top 30 GARP), entrambi con il prezzo al 39% del massimo.

**Ordine.**
1. core GARP;
2. 2 o più famiglie (più famiglie prima);
3. `punteggio_medio` come spareggio.

**Settimana.** `settimana` = i primi 5 della lista non ancora radiografati.
I già radiografati sono in `schede_fatte.txt`, nella radice del repo: un ticker per riga, `#` per i commenti.
Va aggiornato dopo ogni Radiografia (non fa partire lo screening).

#### Campi in testa

| Campo | Significato |
|---|---|
| `screener`, `date`, `generated_at_utc` | Come negli altri report; `screener` = `"lista_radiografare"`. |
| `fonti` | Per ogni screener: `file`, `letto` (true/false), `date` del suo report. |
| `avvisi` | Fonte mancante, illeggibile o vuota (un file che contiene solo `{}` conta come mancante) o fonti con date diverse. |
| `famiglie` | `["GARP", "Radar A", "Radar B", "Moonshot", "Svolta"]`. |
| `regola_famiglie`, `regola_ordine`, `regola_sicurezza`, `regola_settimana` | Le regole, in italiano. |
| `n_righe`, `n_2_famiglie`, `n_core` | Quanti titoli in lista, quanti in 2+ famiglie, quanti core. |
| `conteggi_famiglie` | Titoli in lista per famiglia. |
| `schede_fatte_count` | Quanti ticker ci sono in `schede_fatte.txt`. |
| `settimana` | I 5 ticker della settimana. |
| `lista` | Le righe, già in ordine. |
| `esclusi_sicurezza_count`, `esclusi_sicurezza` | Le righe tolte dalla guardia (stessi campi). |
| `garp_esclusi_sicurezza` | Ticker già tolti dalla guardia dentro il GARP (dettagli in `results/latest.json`). |

#### Campi di ogni riga

| Campo | Significato |
|---|---|
| `ticker`, `altri_ticker` | Ticker Yahoo principale e altre quotazioni della stessa società. |
| `nome`, `settore`, `paese`, `valuta`, `market_cap`, `prezzo` | Dati di base dal primo screener che li ha (GARP, Moonshot, Svolta). `market_cap` è nella valuta di quotazione. |
| `segnali` | Quali screener lo segnalano: `GARP-core`, `GARP-top30`, `Radar A`, `Radar B`, `Moonshot`, `Svolta`. |
| `famiglie`, `n_famiglie` | Famiglie distinte (core e top 30 = GARP). |
| `core` | `true` se è nel core GARP. |
| `etichette` | `"margine in svolta"` (Svolta), `"tema: <nome>"` (Temi verde o giallo). |
| `temi` | Dettaglio dei temi: `{tema, semaforo}`. |
| `punteggio_garp` | Dal GARP, se c'è. |
| `punteggi` | Percentile 0-100 del titolo dentro ciascuna sua famiglia (dalla posizione nella lista di quello screener). |
| `punteggio_medio` | Media di `punteggi`: serve solo a ordinare. |
| `pct_max_52s`, `pct_max_52s_fonte` | Prezzo/massimo a 52 settimane e da quale screener viene ("GARP", "GARP, verificato sullo storico", "Svolta", "Svolta, verificato sullo storico", "Moonshot", "Temi"). |
| `diluizione`, `diluizione_fonte` | Variazione delle azioni usata per la guardia e da dove viene ("GARP, ultimo anno", "Svolta, ultimo anno", "Moonshot, media annua pluriennale", "Temi, media annua pluriennale"). |
| `stime_mancate`, `peg_sospetto` | Dal GARP, se c'è. |
| `sicurezza_ok`, `sicurezza_motivi` | Esito della guardia (`null` = nessun dato). |
| `sicurezza_dati_mancanti` | Dati della guardia che mancano: `"pct_max_52s"` e/o `"variazione_azioni_1a"` (stessi nomi del GARP; qui la diluizione è il campo `diluizione`). Vuota se ci sono tutti e due. |
| `gia_radiografato` | `true` se il ticker (o un altro ticker della stessa società) è in `schede_fatte.txt`. |
| `settimana` | `true` per i 5 della settimana. |
| `posizione` | Posizione nella lista (1 = primo). |

`latest.md`: i 5 della settimana, la tabella completa (⭐ = settimana, ✓ = già radiografato) e gli esclusi per sicurezza.
La tabella completa ha la colonna nuova **Sicurezza** (prima di "Fatto"): "ok", "⚠ manca prezzo/max", "⚠ manca diluizione" o "⚠ non verificabile" (mancano tutti e due).
Nei 5 della settimana l'avviso "⚠ sicurezza non verificabile: manca …" compare anche quando manca un solo dato.
Una riga core o top 30 senza ticker viene saltata (prima faceva fallire lo script).

### 4. Fotografie notturne nuove

#### `snapshots/punteggi/<data>.csv.gz` (scritto da `garp_screener.py`)

Ogni sera, una riga per **ogni titolo analizzato dal GARP senza errore** (circa 10.000; circa 100 KB compressi).
Solo valori derivati, nessun dato grezzo: servono a verificare in futuro punteggio e guardia sui dati di allora.

Colonne: `date`, `ticker`, `stato` (`passed`, `esclusa_sicurezza`, `near_miss`, `bocciato`), `punteggio_garp`, `core`, `top30`, `radar_a`, `radar_b`, `fascia_peg`, `peg_sospetto`, `stime_mancate`, `stime_mancate_4t`, `sorprese_4t_n`, `riacquisti_netti`, `sicurezza_ok` (vuoto = nessun dato), `sicurezza_motivi`, `pct_max_52s`, `variazione_azioni_1a`, `n_check_falliti`, `check_falliti` (separati da virgola), `pct_max_52s_verificato`, `sicurezza_dati_mancanti` (separati da virgola).

#### `snapshots/stime/<data>.csv.gz` e `snapshots/stime/ultimo_run.json` (script `snapshot_stime_eodhd.py`)

Ogni notte i fondamentali EODHD (solo le sezioni sulle stime e sugli utili) di **un quinto dell'universo a rotazione**.
Ogni titolo ha un gruppo fisso da 0 a 4; il gruppo del giorno è il giorno della settimana (lunedì = 0, venerdì = 4).
Così ogni titolo è aggiornato una volta a settimana.
In più, ogni notte, i titoli prioritari: watchlist, `schede_fatte.txt`, promossi e radar GARP, esclusi per sicurezza, lista da radiografare.
**Recupero.** Con i crediti che avanzano (fino al tetto) lo script scarica anche titoli degli altri gruppi: prima quelli mai fotografati o con la fotografia più vecchia (fra le ultime 40), poi per capitalizzazione.
Così un gruppo saltato (crediti finiti per il lavoro manuale) si recupera nei giorni dopo, invece di aspettare una settimana.
`STIME_RECUPERO=0` lo spegne.

**Licenza.** Il repository è pubblico e il piano personale EODHD non permette di ridistribuire i dati grezzi.
Il file contiene valori calcolati da noi più due informazioni copiate tali e quali, che non sono stime né importi: il numero di analisti e le date delle trimestrali (fatti pubblici).
Nessuna stima, nessun utile per azione, nessuna sorpresa in valore.

| Colonna | Significato |
|---|---|
| `date`, `ticker`, `codice_eodhd`, `gruppo`, `prioritario` | Data, ticker Yahoo, codice EODHD usato, gruppo di rotazione (0-4), titolo prioritario. |
| `esito` | `ok`, `senza_stime` (nessun analista né storico), `non_trovato`, `errore_rete`, `risposta_non_valida` (risposta non in JSON), `http_<codice>`; dal 08/11/2026 anche `limite_frequenza` (EODHD ha risposto 429 a tutti i tentativi), `dati_non_validi` (risposta con una forma inattesa: il titolo resta senza valori, gli altri vengono salvati) ed `errore_interno` (errore imprevisto su quel titolo). |
| `n_analisti` | Analisti che stimano l'utile dell'anno in corso (numero copiato da EODHD, `earningsEstimateNumberOfAnalysts`). |
| `rev_eps_0y_7g_pct`, `rev_eps_0y_30g_pct`, `rev_eps_0y_90g_pct` | Revisione in % della stima dell'utile per azione dell'anno in corso rispetto a 7, 30 e 90 giorni fa (sul valore assoluto: una perdita attesa che si riduce è una revisione positiva). |
| `rev_eps_1y_7g_pct`, `rev_eps_1y_30g_pct`, `rev_eps_1y_90g_pct` | Lo stesso per l'anno prossimo. |
| `crescita_eps_attesa_pct` | Crescita attesa in %: stima dell'anno prossimo su stima dell'anno in corso. |
| `trend_0y_coerente` | `false` se la stima media dell'anno in corso e la sua serie di revisioni non coincidono (succede subito dopo la chiusura dell'anno fiscale, es. Apple): le revisioni 0y vanno lette con cautela. |
| `n_trimestri_4t`, `n_beat_4t`, `n_miss_4t` | Fra le ultime 4 trimestrali con stima: quante considerate, quante sopra e quante sotto le stime. |
| `segno_ultima_sorpresa` | 1 = ultima trimestrale sopra le stime, -1 = sotto, 0 = in linea. |
| `ultima_trimestrale`, `prossima_trimestrale` | Data dell'ultima trimestrale pubblicata e della prossima annunciata (se EODHD la conosce). |
| `fine_anno_0y` | Fine dell'anno fiscale a cui si riferisce "anno in corso". |
| `recupero` | `True` se il titolo è di un altro gruppo, scaricato con i crediti avanzati (vedi Recupero). |

`ultimo_run.json`: riepilogo dell'ultimo run (titoli scaricati, saltati per borsa, esiti, crediti prima e dopo, eventuale interruzione).
`da_scaricare` conta il gruppo del giorno più i prioritari. Chiavi nuove: `recupero_in_coda` (titoli di altri gruppi in coda), `recupero_mai_fotografati` (quanti di questi non hanno ancora una fotografia), `recupero_scaricati` (quanti recuperati in questo run), `risposte_429` (risposte "troppe richieste" di EODHD).

**Borse.** Nessun suffisso → `.US`; `.DE` → `.XETRA`; `.L` → `.LSE`; `.KS` → `.KO`; `.AX` → `.AU`; `.PA`, `.AS`, `.MC`, `.SW`, `.ST`, `.CO`, `.HE`, `.OL`, `.BR`, `.TO`, `.TW` uguali.
Milano, Tokyo, Hong Kong, Vienna, Lisbona e le altre sono saltate e contate in `saltati_per_borsa` (circa 300 titoli dell'universo).

**Crediti.** 10 per titolo, anche se il ticker non esiste.
Un quinto dell'universo più i prioritari sono circa 2.000-2.300 titoli, cioè 20.000-23.000 crediti a notte; il resto fino al tetto va al recupero.
- Tetto per notte: `EODHD_CAP_CREDITI` (25.000).
- Prima di partire e ogni 200 titoli lo script legge il contatore EODHD e si ferma se i crediti rimasti nel giorno scendono sotto `EODHD_RESIDUO_MIN` (**5.000**; era 20.000: i crediti sono pagati ogni giorno e vanno usati, resta solo un piccolo margine per il lavoro manuale della sera).
- Se EODHD risponde 429 (troppe richieste), tutti i thread fanno una pausa comune (al massimo 60 secondi) prima di riprovare.
- Tempo massimo `EODHD_TEMPO_MAX_S` (900 s).
- Prima i prioritari, poi il gruppo del giorno per capitalizzazione decrescente, poi il recupero: se i crediti non bastano restano fuori prima i titoli del recupero, poi i più piccoli del gruppo del giorno (che il recupero riprende nei giorni dopo).
- Se il file del giorno esiste già (secondo run), i titoli già scaricati non si riscaricano.

**Chiave.** Su GitHub Actions è nel secret `EODHD_API_TOKEN`. Senza secret il passo fallisce senza bloccare il commit (`ultimo_run.json` lo dice).

**Limiti dei dati.** Fuori dagli USA lo storico delle trimestrali EODHD è meno affidabile (società semestrali come LVMH o Nestlé: date e conteggi da prendere con cautela). Il backtest considera le stime battute affidabili solo per gli USA.

### 5. Workflow (`.github/workflows/screener.yml`)

- Job di merge, dopo "Merge Svolta results": "Build radiography list" (`lista_radiografare.py`), "Download universe (EODHD snapshot)" e "Snapshot analyst estimates (EODHD)" (`snapshot_stime_eodhd.py`, con il secret `EODHD_API_TOKEN`). Tutti con `continue-on-error`.
- Il commit aggiunge `results-lista/`; `snapshots/` era già compresa.
- `paths-ignore`: aggiunti `results-lista/**`, `results-svolta/**` e `schede_fatte.txt`.
- Tempo massimo del job di merge: 45 minuti (era 30).
- `EODHD_RESIDUO_MIN` = 5000 (era 20000).

### Cosa può usare la Regia

- **Proposte d'acquisto:** come prima, prima `core` e poi `top30`. Ora escludono già la guardia di sicurezza e le stime mancate.
- **Esclusi per sicurezza:** se in `esclusi_sicurezza` (GARP o lista) compare un titolo in portafoglio o in watchlist, va segnalato con il motivo (`sicurezza_nota`). Non è un ordine di vendita automatico.
- **Radiografie della settimana:** `results-lista/latest.json` → `settimana`. Per ogni nome mostrare `segnali`, `n_famiglie` ed `etichette`. Dopo la Radiografia aggiungere il ticker a `schede_fatte.txt`.
- **Stime degli analisti:** `snapshots/stime/<data più recente>.csv.gz`, unendo per `ticker`. Avvisi utili: revisioni dell'anno prossimo negative a 30 e 90 giorni; `n_miss_4t` ≥ 3; `prossima_trimestrale` vicina. Il file del giorno contiene un quinto dell'universo, i prioritari e i titoli recuperati: per gli altri usare il file più recente in cui compaiono (di solito al massimo una settimana prima).
- **Sicurezza non verificabile:** se `sicurezza_dati_mancanti` non è vuota, il titolo è rimasto in lista senza un controllo completo: verificare a mano prezzo/massimo o diluizione prima di proporlo.
- **Svolta:** `sicurezza_ok` = false è un avviso da citare accanto al nome.

### Correzioni dopo la revisione del 07/11/2026

Già comprese nelle sezioni sopra; qui l'elenco, per chi aveva letto la prima versione.

1. **Frazionamenti:** campo nuovo `pct_max_52s_verificato` (GARP e Svolta); la guardia, il core e la lista lo usano quando c'è. `pct_max_52s` non cambia.
2. **Dato mancante parziale:** campo nuovo `sicurezza_dati_mancanti` (GARP, Svolta, lista); in testa al GARP `sicurezza_non_verificabile_count` e `sicurezza_non_verificabile`; sezione "Sicurezza non verificabile" nel `latest.md` del GARP, righe di avviso nella Svolta, colonna Sicurezza nella tabella completa della lista.
3. **Doppioni negli esclusi:** una riga per titolo; campo nuovo `liste_origine`; `esclusi_sicurezza_count` conta il titolo una volta.
4. **Lista:** una riga core o top 30 senza ticker viene saltata; un file sorgente con solo `{}` dà un avviso.
5. **Stime EODHD:** un record di forma inattesa non fa perdere il file della notte (esito `dati_non_validi`); esito `limite_frequenza` dopo i 429 e pausa comune ai thread; riserva di crediti 5.000 invece di 20.000 e recupero dei titoli con la fotografia più vecchia; colonna nuova `recupero`.
