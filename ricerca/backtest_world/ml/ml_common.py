# ml_common: funzioni condivise degli script ml_*.py (benchmark non lineare: gradient boosting walk-forward)
# Base: reg_Z.pkl (ranghi per data x regione delle 81 variabili di features_v3, con segno a priori; z=(rango-0.5)*sqrt(12),
# mancanti = NaN). Il gradient boosting e' invariante al segno; i modelli lineari usano NaN -> 0 (= mediana).
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3
HERE = fv3.HERE
OUT = f'{HERE}/ml_out'
os.makedirs(OUT, exist_ok=True)

# campi estesi: affidabili solo negli USA (fuori dagli USA scaricati per societa' scelte ex post -> mancanza non casuale)
EXT = ['gpa', 'gm', 'd_gm', 'gm_std5', 'rel_gm_ind', 'cur_ratio', 'rd_int', 'sga_int', 'accel_q',
       'n_beat4', 'surp_mean4', 'surp_last', 'n_est4', 'age_y']
GLOBAL = [c for c in fv3.PREDICTORS if c not in EXT]          # 67 variabili usate nel modello mondiale
FAM = {v: f for f, vs in fv3.FAMILIES.items() for v in vs}
TGT = {'rk': 'rk12_reg', 't5': 'top5_reg', 'b20': 'bot20_reg', 'c50': 'crash50'}
LAST_PORT_DATE = '2026-06-30'     # il trimestre dopo il 30/09/2026 non e' ancora chiuso


def load():
    M = pd.read_pickle(f'{HERE}/reg_Z.pkl').reset_index(drop=True)
    for c in ['top5_reg', 'bot20_reg', 'crash50', 'top5', 'bot20']:
        M[c] = M[c].astype(float)
    M.loc[M.rk12_reg.isna(), ['top5_reg', 'bot20_reg', 'crash50']] = np.nan
    return M


def xcols(names):
    return ['z_' + c for c in names]


def splits(dates, first=2016, emb=4):
    """split annuali di fv3 + validazione interna: ultime nval date della finestra di stima, con 4 trimestri di distacco"""
    for y, train, test in fv3.walk_forward_splits(dates, first, emb):
        nval = min(8, max(4, len(train) // 4))
        val = train[-nval:]
        inner = [d for d in train if d <= val[0] - pd.offsets.QuarterEnd(emb)]
        yield y, inner, val, train, test


def ic_by_date(pred, y, dates):
    df = pd.DataFrame({'p': pred, 'y': y, 'd': dates}).dropna()
    return df.groupby('d').apply(lambda g: g.p.rank().corr(g.y.rank()) if len(g) > 30 else np.nan, include_groups=False).dropna()


def auc_by_date(pred, y, dates):
    from sklearn.metrics import roc_auc_score
    df = pd.DataFrame({'p': pred, 'y': y, 'd': dates}).dropna()
    out = {}
    for d, g in df.groupby('d'):
        if g.y.nunique() == 2 and g.y.sum() >= 5: out[d] = roc_auc_score(g.y, g.p)
    return pd.Series(out)


def perlab(d):
    y = pd.Timestamp(d).year
    return '2016' if y <= 2016 else ('2017-21' if y <= 2021 else '2022-26')
PERS = ['2016', '2017-21', '2022-26']
GROUPS = ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia', 'Altri']


def port(M, sel_fn, dates, cost=0.005):
    """come regcommon.port: trimestrale a pesi uguali, r_eur del trimestre dopo, 0,5% per acquisto/vendita"""
    prev = pd.Series(dtype=float); rows = []
    for d in dates:
        g = M[M.date == d]; s = sel_fn(g)
        if len(s) == 0:
            rows.append((d, 0.0, 0.0, 0, np.nan, np.nan, np.nan)); prev = pd.Series(dtype=float); continue
        w = pd.Series(1 / len(s), index=s.t.values)
        dw = w.subtract(prev, fill_value=0).abs().sum()
        rows.append((d, s.r_eur.mean() - cost * dw, dw, len(s), s.top5_reg.mean(), s.bot20_reg.mean(), s.crash50.mean()))
        prev = w * (1 + s.set_index('t').r_eur.reindex(w.index).fillna(0)); prev = prev / prev.sum()
    return pd.DataFrame(rows, columns=['date', 'r', 'turn', 'n', 'top5', 'bot20', 'crash']).set_index('date')


def pstats(df, bench):
    r = df.r; b = bench.reindex(r.index)
    out = {'titoli': df.n.mean(), 'CAGR': (1 + r).prod() ** (4 / len(r)) - 1}
    out['diff'] = out['CAGR'] - ((1 + b).prod() ** (4 / len(b)) - 1)
    out['t'] = fv3.nw_t(r - b, 2)
    for p in PERS:
        m = np.array([perlab(d) == p for d in r.index])
        out[p] = (1 + r[m]).prod() ** (4 / m.sum()) - 1 - ((1 + b[m]).prod() ** (4 / m.sum()) - 1)
    cum = (1 + r).cumprod(); out['perdita_max'] = (cum / cum.cummax() - 1).min()
    out['rotaz_annua'] = df.turn.mean() * 4 / 2
    out['top5'] = df.top5.mean(); out['bot20'] = df.bot20.mean(); out['crash50'] = df.crash.mean()
    return out
