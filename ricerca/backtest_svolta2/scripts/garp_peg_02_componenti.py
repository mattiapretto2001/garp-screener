# GARP: da dove viene l'effetto del punteggio. Top 30 per una sola variabile, punteggio senza una variabile,
# punteggio applicato ai promossi V1 / V2 / V3. Riusa definizioni e motore di garp_peg_01_backtest.py.
import os
HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(f'{HERE}/garp_peg_01_backtest.py').read().split("ev('G0")[0])
ev('V3 PEG<2 + tolleranza EPS', sel(V3), group='rif')
COMP = {'PEG (basso)': ('peg', False), 'Ricavi trim.': ('yoy0', True), 'EPS trim.': ('epsq', True), 'CAGR ricavi': ('rev_cagr', True),
        'FCF yield': ('fcfy', True), 'D/E (basso)': ('de', False), 'ROE': ('roe', True), 'Margine EBITDA': ('ebitda_m', True), 'EBITDA/EV': ('ebitda_ev', True)}
def single(mask, col, higher):
    out = pd.Series(np.nan, index=F.index)
    for t, x in F[mask].groupby('date'): out[x.index] = pct(x[col], higher)
    return out
for nm, (c, h) in COMP.items():
    ev(f'top 30 solo {nm}', sel(V3, 30, single(V3, c, h)), base='V3 PEG<2 + tolleranza EPS', group='singola')
# punteggio ROE / PEG 30 senza una componente (pesi ridistribuiti)
def score_wo(mask, drop, prof='roe', wpeg=30):
    out = pd.Series(np.nan, index=F.index)
    for t, x in F[mask].groupby('date'):
        comp = {'peg': pct(x.peg, False), 'rev_q': pct(x.yoy0), 'eps_q': pct(x.epsq), 'cagr': pct(x.rev_cagr),
                'fcfy': pct(x.fcfy), 'de': pct(x.de, False), 'prof': pct(x[prof])}
        comp.pop(drop, None)
        others = [k for k in comp if k != 'peg']
        w = {k: (100 - wpeg) / len(others) for k in others}
        if 'peg' in comp: w['peg'] = wpeg
        else: w = {k: 100 / len(comp) for k in comp}
        out[x.index] = sum(w[k] * comp[k] for k in comp)
    return out
for d in ('peg', 'rev_q', 'eps_q', 'cagr', 'fcfy', 'de', 'prof'):
    ev(f'top 30 ROE/PEG30 senza {d}', sel(V3, 30, score_wo(V3, d)), base='V3 PEG<2 + tolleranza EPS', group='senza')
for wp in (15, 45):
    ev(f'top 30 ROE, peso PEG {wp}', sel(V3, 30, score_wo(V3, None, wpeg=wp)), base='V3 PEG<2 + tolleranza EPS', group='pesoPEG')
# il punteggio sugli altri insiemi di promossi
for nm, m in (('V1', V1), ('V2', V2), ('V3', V3)):
    ev(f'{nm}: top 30 ROE/PEG30', sel(m, 30, scores(m, 'roe')), base='V3 PEG<2 + tolleranza EPS', group='insiemi')
    ev(f'{nm}: top 15 ROE/PEG30', sel(m, 15, scores(m, 'roe')), base='V3 PEG<2 + tolleranza EPS', group='insiemi')
R = pd.DataFrame(RES); R.to_csv(f'{OUT}/garp_peg_componenti.csv', index=False)
AN = pd.DataFrame({k: annual(v) for k, v in NET.items()})
P = R[R.periodo != 'Tutto 2012-26'].pivot_table(index='variante', columns='periodo', values='CAGR', sort=False)
T = R[R.periodo != 'Tutto 2012-26'].pivot_table(index='variante', columns='periodo', values='t_vs_base', sort=False)
pd.set_option('display.width', 250)
print((P * 100).round(1).join((T).round(1), rsuffix=' t').to_string())
print((AN.loc[2019:2026] * 100).round(0).T.to_string())
