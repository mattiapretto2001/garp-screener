# Ricerca: programmi dei backtest (27/10 - 09/11/2026)

These are the programs behind the backtests and analyses whose reports are on OneDrive in `Claude/_scratch/backtest_screener/` (and some in `Claude/Cruscotti/schede/`). The folder holds **only code**: no data is included. The EODHD data cannot be redistributed under the personal plan, and the repository is public. To use the programs, the data has to be downloaded again with your own EODHD key.

## Before you start

- Python 3.11+, with: `pip install pandas numpy pyarrow yfinance requests scipy statsmodels scikit-learn lightgbm`.
- **EODHD key.** The scripts do not contain it. In the original cloud session a network proxy added it automatically. On another machine, add `api_token=<key>` to the eodhd.com URLs, or use a wrapper that adds the `Authorization: Bearer <key>` header, which EODHD accepts. Never commit the key.
- **Paths.** Absolute paths are written as `${RICERCA_BASE}`. Run once:
  `python prepara_percorsi.py "<folder where the data will go>"`.
  Some scripts also contain paths relative to the folder they run from: run them from their own folder (`backtest_world/`, `backtest_world/ml/`, `backtest_svolta2/scripts/`).
- **Credits.** Rebuilding everything takes about 250,000 EODHD credits, i.e. 3 days of the plan. Each download script checks `https://eodhd.com/api/user` and stops below its own cap.

## Pipelines, in order

| Folder | Scripts in order | Data produced | Reports (OneDrive) |
|---|---|---|---|
| `backtest_svolta2/scripts` | `svolta_01`…`svolta_08`, then `svolta2_09`…`13`, `garp_peg_01`…`04` | SEC companyfacts, US prices, features | REPORT_backtest_svolta_2026-11-03, REPORT_svolta_affinamento_2026-11-03, REPORT_garp_peg2_2026-11-06 |
| `backtest_world` (world base) | `world_01_prices`, `world_01b_fx_bench`, `world_02_candidates`, `world_02b_select`, `world_03_fund`, `world_04_features`, `world_04b_liq_pit`, `world_05_backtest`, `world_06_tables` | `eod/`, `fund/fund.pkl`, `res/panel.pkl` | REPORT_garp_mondo_2026-11-06 |
| `backtest_world` (expansion 07/11) | `world_10_us_candidates`, `world_11_fund2`, `world_14_features2`, `world_14b_liq2`, `world_15_prep` | `fund/fund2.pkl`, `res/panel2.pkl` (removes duplicate listings and fixes UK prices quoted in pence; see `tune_common.py`) | — |
| `backtest_world` (tuning) | `tune_01`…`tune_08`, `tune_10_verifica`, `tune_11_dimensione` | `res/tune_*` | REPORT_affinamento_screener_2026-11-06, REPORT_screener_finale_2026-11-07 |
| `backtest_world` (all screeners) | `scr_01`…`scr_06b` (rules in `scr_common.py`) | `res/scr_*` | REPORT_screener_tutti_2026-11-07 |
| `backtest_world/ml` (features and models) | `fv3*` (feature matrix), `univariata_*`, `regressioni_*`, `ml_*`, `profili_*`, `temi_*`, `sint_*` | `ml/features_v3.pkl` | REPORT_punteggi_profili_2026-11-07 |
| `backtest_world/ml` (clean period) | `pp_*` | — | R_periodo_pulito_2018_2026 |
| `backtest_world/ml` (2000-2011 history) | `s5_*` (prices from 1998, US delisted universe), `sA_*`, `sB_*`, `h0*` | `ml/eod_lungo/` | R_storico_2000_2011 and _v2 |
| `backtest_world/ml` (rotation and sizing) | `ist_*` | — | R_isteresi_dimensione |
| `backtest_world/ml` (multiplier rules) | `regoleC/`, `regcommon.py` | — | R_C_regole_moltiplicatori |
| `backtest_world/ml` (factors) | `f1_*` (multibagger), `f2_*` (SEC insiders, free data), `f3_*` (earnings surprises), `f4_*` (neglected, founders, spin-offs; rules written beforehand in `REGOLE_PRIMA.txt`) | `ml/f2/` etc. | R_F1…R_F4 |
| `backtest_world/ml` (checks) | `avv_*` | — | sections "Verifica avversariale" in the reports |
| `backtest_world/ml` (register) | `registro_*` | — | R_registro_radiografie |

Notes:
- Scripts marked in the reports as "controllo aggiunto dopo aver visto i risultati" were written after seeing the results. They are labelled as such: do not use them to choose rules.
- Survivorship: EODHD has no financial statements for companies delisted before 2011, and outside the US it has almost no data on companies delisted before 2013-2018. The clean period starts in 2018-2021 (see the reports).
