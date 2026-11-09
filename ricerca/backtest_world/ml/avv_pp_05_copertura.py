# avv_pp_05: (1) quante societa' uscite dal listino entrano davvero nel pannello, per anno dell'ultimo prezzo;
# (2) crolli 2021 contro altri anni; (3) rendimenti delle americane 2-10 Mld$ per gruppo del rapporto e per regola alla data.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    from pp_common import *
    from world_common import symbols, BASE
P = set(F.t); M = pd.read_pickle(f'{BASE}/res/meta2.pkl').drop_duplicates('t').set_index('t')
C = pd.concat([pd.read_csv(f'{BASE}/res/candidates.csv'), pd.read_csv(f'{BASE}/res/candidates_us2.csv')]).drop_duplicates('t')
rows = []
for ex in C.ex.unique():
    s = symbols(ex); dl = dict(zip(s.Code.astype(str), s.delisted)); c = C[C.ex == ex].copy(); c['dl'] = c.code.astype(str).map(dl); rows.append(c)
C = pd.concat(rows); C['last'] = C.t.map(M.last_px); C['inp'] = C.t.isin(P)
C['grp'] = np.select([C.ex == 'US', C.ex.isin(['TW', 'KO']), C.ex.isin(['TO', 'AU'])], ['USA', 'Asia', 'Altri'], 'Europa')
D = C[C.dl == 1]
print('quota delle uscite che entrano nel pannello, per anno dell ultimo prezzo')
print(D.groupby(['grp', D['last'].dt.year]).inp.agg(['mean', 'size']).round(2).unstack(0).to_string())
print('attive nel pannello', C[C.dl == 0].groupby('grp').inp.mean().round(2).to_dict())
D18 = [d for d in REB if pd.Timestamp('2018-03-31') <= d <= pd.Timestamp('2026-09-30')]
for nm, m in [('Crescita >=2', CR & B2 & UNI), ('Radar A', RADA & UNI & B2), ('core', CORE & UNI), ('universo >=2', UNI & B2)]:
    X = F[m & F.date.isin(D18) & F.crash50.notna()]; y = X.date.dt.year == 2021
    print(f'{nm}: crolli, date 2021 {X[y].crash50.mean():.1%} ({y.sum()} righe); altri anni {X[~y].crash50.mean():.1%}')
b = pd.read_pickle(f'{BASE}/eod/bulk_US.pkl'); s = symbols('US')
mm = dict(zip(s.Code.str.replace('_old', ''), s.Code)); mm.update(dict(zip(s.Code, s.Code)))
b = b[b.code.isin(mm)].copy(); b['code'] = b.code.map(mm)
H = b[(b.close * b.volume >= 5e7) & (b.close >= 3)].groupby('code').date.apply(sorted).to_dict()
S = F[(F.ex == 'US') & UNI & F.date.isin(D18) & F.mcap_usd.between(2e9, 10e9)].copy()
S['big_pit'] = [sum(1 for x in H.get(c, []) if x <= d) >= 3 for c, d in zip(S.t.str[:-3], S.date)]
print('USA 2-10 Mld$: per gruppo del rapporto (us_new=True -> piccole/medie)'); print(S.groupby('us_new')[['r_eur', 'f12']].mean().round(4).to_string())
print('per regola alla data (big_pit)'); print(S.groupby('big_pit')[['r_eur', 'f12']].mean().round(4).to_string())
print('solo chi alla data non aveva ancora il grande scambio, per gruppo del rapporto'); print(S[~S.big_pit].groupby('us_new')[['r_eur', 'f12']].agg(['mean', 'size']).round(4).to_string())
