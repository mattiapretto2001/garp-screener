# Cambi di formato dei risultati

Registro dei cambi a `results*/latest.json`, `latest.md` e `snapshots/` che interessano la routine sul PC (`report-azionario-mattina`).
Regola: i campi esistenti non si rinominano e non si tolgono, si aggiungono solo campi nuovi.

## 03/11/2026: Fase 1, qualità dei dati (ramo `claude/fase1-qualita-dati`)

### Campi nuovi in `results/latest.json` (GARP) e `results-moonshot/latest.json` (Moonshot)

| Campo | Tipo | Significato |
|---|---|---|
| `errori_per_tipo` | oggetto `{tipo: conteggio}` | Titoli non valutabili per causa, dal più frequente. |
| `errori_pct` | numero (0-1) | `errors / analyzed`, arrotondato a 4 decimali. |
| `sospesi_per_dati` | lista di ticker | Promossi del report precedente che oggi sono **non valutabili per errore di dati**: non sono stati bocciati. |
| `watchlist_non_valutabili` | lista di `{ticker, tipo, errore}` | Titoli di `watchlist.txt` (e di `portafoglio.txt`, se esiste) presenti nell'universo e oggi non valutabili. |

Tipi di errore possibili:

- `limite_frequenza`: Yahoo ha risposto 429 o "Too Many Requests";
- `timeout`: la richiesta è scaduta;
- `non_trovato`: 404, ticker non trovato o delistato;
- `info_vuoto`: `.info` vuoto (ticker inesistente o delistato, oppure risposta vuota di Yahoo: di solito è un limite di frequenza mascherato);
- `campi_mancanti`: `.info` presente ma senza settore, capitalizzazione o prezzo, oppure bilancio annuale non scaricabile per un titolo che ha passato lo stadio 1;
- `rete`: errore di connessione;
- `altro`: qualsiasi altra eccezione;
- `sconosciuto`: solo per parziali vecchi, scritti prima di questo cambio.

### Campi nuovi in `results-temi/latest.json` (Temi)

Gli stessi quattro: `errori_per_tipo`, `errori_pct`, `sospesi_per_dati`, `watchlist_non_valutabili`.
Per i Temi, `sospesi_per_dati` contiene i titoli **seguiti** (in `tracked`) nel report precedente che oggi sono in errore.
Il campo esistente `errors` resta la lista dei ticker in errore.

### Cambi di significato da conoscere (nessun campo rinominato)

1. **`errors` (GARP e Moonshot) conta di più.**
   Prima un titolo con `.info` vuoto, o senza settore, capitalizzazione o prezzo, era bocciato in silenzio (`sector_ok` falso).
   Ora è un errore di tipo `info_vuoto` o `campi_mancanti`.
   Il numero di errori può quindi salire anche a parità di qualità dello scarico: è il numero vero.
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
- `portafoglio.txt` è facoltativo, un ticker per riga, `#` per i commenti. Non è nel repository: le posizioni non vanno nel repository pubblico.
- Nei parziali (`partials/*.json`) i titoli in errore hanno `error` con la causa originale, più `error_type` e `tentativi`. Prima `error` valeva "irrecuperabile dopo i retry".
