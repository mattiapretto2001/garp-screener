# avv_temi_common: ricostruzione INDIPENDENTE (verifica avversariale) del pannello industria x data e delle regole B / MOM / CALDE / BM.
# Non importa temi_01/02: calcolo vettoriale separato. Riusa solo la mappa dei nomi di industria (definizione) e nw_t.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fv3
from temi_common import IND_MAP, EXCL_SECT, MIN_N, holm, tp
OUT = f'{HERE}/avv_temi_out'; os.makedirs(OUT, exist_ok=True)
nw_t = fv3.nw_t
COLS = ['t', 'date', 'reg', 'reg_rob', 'sector_n', 'industry', 'mcap_usd', 'fx_rep', 'rev_ttm', 'rev_ttm4', 'rev_ttm8', 'rev_ttm4b',
        'rev_q', 'rev_qp', 'gp_ttm', 'gp_ttm4', 'opi_ttm', 'opi_ttm4', 'mom12_1', 'mom6', 'vol1y', 'us_new', 'dsh3',
        'fwd12_eur', 'fwd12_loc', 'xs12_reg', 'rk12_reg', 'top5_reg', 'bot20_reg', 'crash50', 'r_eur', 'xs36_reg']


def load():
    F = fv3.load(cols=COLS).copy()
    ind = F.industry.astype('object').where(F.industry.notna(), None).map(lambda x: x.strip() if isinstance(x, str) else x).replace(IND_MAP)
    F['ind'] = ind
    F = F[F.ind.notna() & (F.ind != 'Other')].copy()
    D = sorted(F.date.unique()); F['di'] = F.date.map({d: i for i, d in enumerate(D)})
    return F


def ind_panel(F):
    """aggregati per (ind, date) in forma vettoriale"""
    fx = F.fx_rep.astype(float)
    X = pd.DataFrame({'ind': F.ind, 'date': F.date, 'di': F.di, 'us': F.reg == 'USA'})
    ru, ru4, ru8 = F.rev_ttm * fx, F.rev_ttm4 * fx, F.rev_ttm8 * fx
    rq, rqp = F.rev_q * fx, F.rev_qp * fx
    gp, gp4, ru4b = F.gp_ttm * fx, F.gp_ttm4 * fx, F.rev_ttm4b * fx
    op, op4 = F.opi_ttm * fx, F.opi_ttm4 * fx
    m1 = (ru4 > 0) & ru.notna(); m2 = m1 & (ru8 > 0); mq = (rqp > 0) & rq.notna()
    mg = (ru > 0) & (ru4b > 0) & gp.notna() & gp4.notna(); mo = (ru > 0) & (ru4 > 0) & op.notna() & op4.notna()
    X['a1'], X['b1'], X['c1'] = ru.where(m1), ru4.where(m1), m1.astype(int)
    X['a2'], X['b2'], X['e2'], X['c2'] = ru.where(m2), ru4.where(m2), ru8.where(m2), m2.astype(int)
    X['aq'], X['bq'], X['cq'] = rq.where(mq), rqp.where(mq), mq.astype(int)
    for tag, sub in (('', pd.Series(True, index=F.index)), ('_us', X.us)):
        mm = mg & sub
        X['gp' + tag], X['ru' + tag], X['gp4' + tag], X['ru4b' + tag], X['cg' + tag] = gp.where(mm), ru.where(mm), gp4.where(mm), ru4b.where(mm), mm.astype(int)
    X['op'], X['ruo'], X['op4'], X['ru4o'], X['co'] = op.where(mo), ru.where(mo), op4.where(mo), ru4.where(mo), mo.astype(int)
    X['mom'] = F.mom12_1; X['pos'] = (F.mom12_1 > 0).astype(float).where(F.mom12_1.notna()); X['vol'] = F.vol1y
    G = X.groupby(['ind', 'date'])
    S = G[[c for c in X.columns if c not in ('ind', 'date', 'di', 'us', 'mom', 'pos', 'vol')]].sum(min_count=1)
    P = pd.DataFrame(index=S.index)
    P['n'] = G.size(); P['di'] = G.di.first()
    P['g_agg'] = (S.a1 / S.b1 - 1).where(S.c1 >= 3)
    P['accel_agg'] = (S.a2 / S.b2 - S.b2 / S.e2).where(S.c2 >= 3)
    P['gq_agg'] = (S.aq / S.bq - 1).where(S.cq >= 3)
    P['pos'] = G.pos.mean().where(G.mom.count() >= 3); P['mom_med'] = G.mom.median(); P['vol_med'] = G.vol.median()
    dg_all = (S.gp / S.ru - S.gp4 / S.ru4b).where(S.cg >= 3); dg_us = (S.gp_us / S.ru_us - S.gp4_us / S.ru4b_us).where(S.cg_us >= 3)
    dop = (S.op / S.ruo - S.op4 / S.ru4o).where(S.co >= 3)
    P['d_marg'] = dg_us.where(S.cg_us >= 3, dg_all.where(S.cg >= 5, dop))
    P = P.reset_index()
    L = P[['ind', 'di', 'pos']].copy(); L['di'] += 2
    P = P.merge(L.rename(columns={'pos': 'pos_l2'}), on=['ind', 'di'], how='left')
    P['d_pos2'] = P.pos - P.pos_l2; P['qa'] = P.gq_agg - P.g_agg
    sec = F.groupby('ind').sector_n.agg(lambda s: s.mode().iloc[0])
    P['eligible'] = ~P.ind.map(sec).isin(EXCL_SECT); P['valid'] = P.n >= MIN_N
    return P


def flags(P):
    V = P[P.valid & P.eligible].copy()
    COMP = ['accel_agg', 'qa', 'd_pos2', 'pos', 'd_marg']
    for c in COMP + ['mom_med', 'g_agg', 'vol_med']: V['rk_' + c] = V.groupby('date')[c].rank(pct=True)
    V['scoreB'] = V[['rk_' + c for c in COMP]].mean(axis=1)
    top = lambda s: s.groupby(V.date).rank(pct=True) > 0.9
    V['B'] = top(V.scoreB); V['MOM'] = top(V.mom_med); V['CALDE'] = top(V.g_agg); V['BM'] = V.B & V.MOM; V['VOLI'] = top(V.vol_med)
    return V


def company(F, V, rules):
    C = F.merge(V[['ind', 'date'] + rules], on=['ind', 'date'], how='inner')
    C['xs3'] = C.r_eur - C.groupby(['date', 'reg']).r_eur.transform('mean')
    C.loc[C.date == C.date.max(), 'xs3'] = np.nan
    return C


def spread(C, rule, tgt, lag):
    Y = C[C[tgt].notna()]
    d = (Y[Y[rule]].groupby('date')[tgt].mean() - Y.groupby('date')[tgt].mean()).dropna()
    return d, 100 * d.mean(), nw_t(d, lags=lag)
