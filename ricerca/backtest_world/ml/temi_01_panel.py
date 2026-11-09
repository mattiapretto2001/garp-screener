# temi_01: pannello industria x data con i "segni di tema emergente" (solo dati noti alla data) e gli esiti a 12 mesi
from temi_common import *
cols = ['t', 'date', 'name', 'reg', 'reg_rob', 'region', 'sector_n', 'industry', 'mcap_usd', 'fx_rep', 'rev_ttm', 'rev_ttm4', 'rev_ttm8',
        'rev_ttm4b', 'rev_q', 'rev_qp', 'gp_ttm', 'gp_ttm4', 'opi_ttm', 'opi_ttm4', 'capex_ttm', 'rd_ttm', 'accel_y', 'd_gm', 'mom12_1',
        'mom6', 'ma200', 'ind_dshare4', 'fwd12_eur', 'xs12_reg', 'rk12_reg', 'top5_reg', 'bot20_reg', 'crash50', 'r_eur']
F = fv3.load(cols=cols).copy()
F['ind'] = norm_ind(F.industry)
F = F[F.ind.notna() & (F.ind != 'Other')].copy()
D = sorted(F.date.unique()); IX = {d: i for i, d in enumerate(D)}
F['di'] = F.date.map(IX)
# settore prevalente dell'industria (classificazione di oggi) -> idoneita' a "tema"
sec = F.groupby('ind').sector_n.agg(lambda s: s.mode().iloc[0])
F['ind_sector'] = F.ind.map(sec)
fx = F.fx_rep.astype(float)
F['ru'], F['ru4'], F['ru8'] = F.rev_ttm * fx, F.rev_ttm4 * fx, F.rev_ttm8 * fx
F['rq'], F['rqp'] = F.rev_q * fx, F.rev_qp * fx
F['gpu'], F['gpu4'], F['ru4b'] = F.gp_ttm * fx, F.gp_ttm4 * fx, F.rev_ttm4b * fx
F['opu'], F['opu4'] = F.opi_ttm * fx, F.opi_ttm4 * fx
F['inv'] = (F.capex_ttm.abs() + F.rd_ttm.fillna(0)) * fx
# stessa societa' 4 trimestri prima (riga gia' nota allora): investimenti (capex + R&S) a cambio di oggi
L = F[['t', 'di', 'capex_ttm', 'rd_ttm']].copy(); L['di'] = L.di + 4
F = F.merge(L.rename(columns={'capex_ttm': 'capex_l4', 'rd_ttm': 'rd_l4'}), on=['t', 'di'], how='left')
F['inv4'] = (F.capex_l4.abs() + F.rd_l4.fillna(0)) * F.fx_rep
F['us'] = F.reg == 'USA'


def agg(g):
    o = {}
    o['n'] = len(g); o['n_us'] = int(g.us.sum()); o['mcap'] = g.mcap_usd.sum()
    m = (g.ru4 > 0) & g.ru.notna(); o['g_agg'] = g.ru[m].sum() / g.ru4[m].sum() - 1 if m.sum() >= 3 else np.nan
    m2 = m & (g.ru8 > 0)
    o['accel_agg'] = (g.ru[m2].sum() / g.ru4[m2].sum() - g.ru4[m2].sum() / g.ru8[m2].sum()) if m2.sum() >= 3 else np.nan
    mq = (g.rqp > 0) & g.rq.notna(); o['gq_agg'] = g.rq[mq].sum() / g.rqp[mq].sum() - 1 if mq.sum() >= 3 else np.nan
    o['accel_med'] = g.accel_y.median()
    mm = g.mom12_1.notna(); o['pos'] = (g.mom12_1[mm] > 0).mean() if mm.sum() >= 3 else np.nan
    o['pos_ma'] = (g.ma200 > 1).mean(); o['mom_med'] = g.mom12_1.median(); o['mom6_med'] = g.mom6.median()
    for tag, sub in (('', g), ('_us', g[g.us])):
        mg = (sub.ru > 0) & (sub.ru4b > 0) & sub.gpu.notna() & sub.gpu4.notna()
        o['d_gm_agg' + tag] = (sub.gpu[mg].sum() / sub.ru[mg].sum() - sub.gpu4[mg].sum() / sub.ru4b[mg].sum()) if mg.sum() >= 3 else np.nan
        o['n_gm' + tag] = int(mg.sum())
    mo = (g.ru > 0) & (g.ru4 > 0) & g.opu.notna() & g.opu4.notna()
    o['d_opm_agg'] = (g.opu[mo].sum() / g.ru[mo].sum() - g.opu4[mo].sum() / g.ru4[mo].sum()) if mo.sum() >= 3 else np.nan
    o['dgm_pos'] = (g.d_gm.dropna() > 0).mean() if g.d_gm.notna().sum() >= 3 else np.nan
    mi = (g.inv > 0) & (g.inv4 > 0); o['inv_g'] = g.inv[mi].sum() / g.inv4[mi].sum() - 1 if mi.sum() >= 3 else np.nan
    o['dshare4'] = g.ind_dshare4.iloc[0]
    # esiti (12 mesi dopo; mai usati come segnali)
    o['n_tgt'] = int(g.xs12_reg.notna().sum())
    o['y_xs'] = g.xs12_reg.mean(); o['y_rk'] = g.rk12_reg.mean(); o['y_top5'] = g.top5_reg.mean(); o['y_bot20'] = g.bot20_reg.mean()
    o['y_crash'] = g.crash50.mean(); o['y_ret'] = g.fwd12_eur.mean(); o['y_r1q'] = g.r_eur.mean()
    o['y_xs_med'] = g.xs12_reg.median()
    return pd.Series(o)


IP = F.groupby(['ind', 'date']).apply(agg).reset_index()
IP['sector'] = IP.ind.map(sec); IP['eligible'] = ~IP.sector.isin(EXCL_SECT)
IP['di'] = IP.date.map(IX)
IP = IP.sort_values(['ind', 'di'])
for k in (1, 2, 4):
    lag = IP[['ind', 'di', 'pos', 'pos_ma', 'gq_agg', 'g_agg', 'mom_med']].copy(); lag['di'] = lag.di + k
    IP = IP.merge(lag, on=['ind', 'di'], how='left', suffixes=('', f'_l{k}'))
IP['d_pos2'] = IP.pos - IP.pos_l2; IP['d_pos4'] = IP.pos - IP.pos_l4; IP['d_posma2'] = IP.pos_ma - IP.pos_ma_l2
IP['qa'] = IP.gq_agg - IP.g_agg                  # crescita dell'ultimo trimestre sopra quella a 12 mesi = accelerazione recente
IP['d_gq1'] = IP.gq_agg - IP.gq_agg_l1
IP['inv_rel'] = IP.inv_g - IP.g_agg              # investimenti che crescono piu' dei ricavi
# margine lordo: USA se l'industria ha >=3 americane con il dato, altrimenti tutte; fallback margine operativo
IP['d_marg'] = IP.d_gm_agg_us.where(IP.n_gm_us >= 3, IP.d_gm_agg.where(IP.n_gm >= 5, IP.d_opm_agg))
# universo di riferimento per data (tutte le societa' con esito)
U = F.groupby('date').agg(u_xs=('xs12_reg', 'mean'), u_top5=('top5_reg', 'mean'), u_bot20=('bot20_reg', 'mean'),
                          u_crash=('crash50', 'mean'), u_ret=('fwd12_eur', 'mean'))
IP = IP.merge(U, left_on='date', right_index=True, how='left')
IP['valid'] = (IP.n >= MIN_N)
IP.to_pickle(f'{OUT}/ind_panel.pkl')
F[['t', 'date', 'di', 'ind', 'ind_sector']].to_pickle(f'{OUT}/comp_ind.pkl')
v = IP[IP.valid & IP.eligible]
print('righe industria x data', len(IP), 'valide e idonee', len(v), 'industrie idonee per data (media/min/max)',
      v.groupby('date').size().agg(['mean', 'min', 'max']).round(0).to_dict())
print(v[['g_agg', 'accel_agg', 'gq_agg', 'qa', 'pos', 'd_pos2', 'd_marg', 'd_opm_agg', 'inv_g', 'inv_rel', 'y_xs']].describe().round(3).to_string())
print('copertura', v[['accel_agg', 'qa', 'd_pos2', 'd_marg', 'd_gm_agg_us', 'inv_rel', 'y_xs']].notna().mean().round(3).to_dict())
