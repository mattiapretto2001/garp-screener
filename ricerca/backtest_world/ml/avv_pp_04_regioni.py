# avv_pp_04: liste nelle USA divise con la regola "grande scambio" applicata ALLA DATA (senza futuro)
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    from avv_pp_01_repro import *
    from world_common import symbols, BASE
b = pd.read_pickle(f'{BASE}/eod/bulk_US.pkl'); s = symbols('US')
mm = dict(zip(s.Code.str.replace('_old', ''), s.Code)); mm.update(dict(zip(s.Code, s.Code)))
b = b[b.code.isin(mm)].copy(); b['code'] = b.code.map(mm)
H = b[(b.close * b.volume >= 5e7) & (b.close >= 3)].groupby('code').date.apply(sorted).to_dict()
US = F.ex == 'US'
F['big_pit'] = False
F.loc[US, 'big_pit'] = [sum(1 for x in H.get(c, []) if x <= d) >= 3 for c, d in zip(F.t[US].str[:-3], F.date[US])]
print('==================== PARTE 4 (regioni USA senza futuro)')
for lname, m, size in [('core', CORE & UNI, B2), ('Crescita >=2', CR & B2 & UNI, B2), ('Q3', Q3 & QU & B5, B5)]:
    base = UNI if lname != 'Q3' else QU
    for rn, R in [('USA grandi (rapporto, con futuro)', US & ~F.us_new), ('USA piccole/medie (rapporto, con futuro)', US & F.us_new),
                  ('USA grandi alla data', US & F.big_pit), ('USA piccole/medie alla data', US & ~F.big_pit)]:
        r = port(m & R); u = uni(base & size & R)
        k = F[m & R & F.date.isin(D18)].groupby('date').size().reindex(D18).fillna(0).mean()
        print(f'{lname:13s} {rn:42s} {100*(ann(r)-ann(u)):+6.1f}  t {nwt((r-u).reindex(D18)):5.2f}  titoli medi {k:4.1f}', flush=True)
