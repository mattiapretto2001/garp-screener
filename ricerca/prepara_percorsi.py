#!/usr/bin/env python3
"""Sostituisce il segnaposto ${RICERCA_BASE} negli script con la cartella dove
vuoi tenere i dati (per esempio la cartella OneDrive _dati_backtest).

Uso:  python prepara_percorsi.py "C:/Users/<utente>/OneDrive - ITALFRIGO SRL/Claude/_dati_backtest"

Gli script vengono riscritti sul posto: lancialo una volta sola su una copia."""
import pathlib, sys
if len(sys.argv) != 2:
    sys.exit(__doc__)
base = sys.argv[1].replace("\\", "/").rstrip("/")
n = 0
for p in pathlib.Path(__file__).parent.rglob("*.py"):
    t = p.read_text(encoding="utf-8")
    if "${RICERCA_BASE}" in t:
        p.write_text(t.replace("${RICERCA_BASE}", base), encoding="utf-8"); n += 1
print(f"Percorsi aggiornati in {n} script: {base}")
