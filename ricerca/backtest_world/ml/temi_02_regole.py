# temi_02: regole ex ante "tema emergente" a livello di industria, FISSATE PRIMA di guardare i risultati.
# Componenti (piu' alto = piu' "emergente"), tutte note alla data:
#   accel_agg  ricavi aggregati a 12 mesi: crescita di oggi - crescita di un anno fa (stesse societa', cambio costante)
#   qa         crescita aggregata dell'ultimo trimestre - crescita aggregata a 12 mesi (accelerazione recente)
#   d_pos2     ampiezza: quota di societa' con momentum 12-1 >0, oggi - 2 trimestri fa
#   pos        ampiezza: livello della quota in rialzo
#   d_marg     margine lordo aggregato, variazione in 1 anno (USA se possibile; altrimenti tutte; poi margine operativo)
#   inv_rel    crescita di capex + R&S - crescita dei ricavi (si investe piu' di quanto si vende)
# Regole:
#   A   'semaforo'  : g_agg>0 & accel_agg>0 & d_pos2>0 & pos>=0.5 & d_marg>0
#   A+  A & inv_rel>0
#   B   'punteggio' : media dei ranghi (fra industrie, alla data) di accel_agg, qa, d_pos2, pos, d_marg -> 10% migliore
#   B+  come B con anche inv_rel (6 componenti)
#   W   pesi stimati in walk-forward (regressione delle componenti sull'esito dell'industria, solo dati <= anno-1 meno 4 trimestri) -> 10% migliore
# Confronti (non 'temi'): MOM = 10% con momentum mediano piu' alto; CALDE = 10% con crescita aggregata dei ricavi piu' alta
from temi_common import *
IP = pd.read_pickle(f'{OUT}/ind_panel.pkl')
V = IP[IP.valid & IP.eligible].copy()
COMP = ['accel_agg', 'qa', 'd_pos2', 'pos', 'd_marg']
COMP6 = COMP + ['inv_rel']
for c in COMP6 + ['mom_med', 'g_agg']:
    V['rk_' + c] = V.groupby('date')[c].rank(pct=True)
V['scoreB'] = V[['rk_' + c for c in COMP]].mean(axis=1, skipna=True)
V['scoreB6'] = V[['rk_' + c for c in COMP6]].mean(axis=1, skipna=True)
top = lambda s: s.groupby(V.date).rank(pct=True, ascending=True) > 0.9
V['A'] = (V.g_agg > 0) & (V.accel_agg > 0) & (V.d_pos2 > 0) & (V.pos >= 0.5) & (V.d_marg > 0)
V['Aplus'] = V.A & (V.inv_rel > 0)
V['B'] = top(V.scoreB); V['Bplus'] = top(V.scoreB6)
V['MOM'] = top(V.mom_med); V['CALDE'] = top(V.g_agg)
# --- W: walk-forward. Esito = rango dell'eccesso dell'industria alla data; regressione Fama-MacBeth sui ranghi delle componenti.
V['y_rkind'] = V.groupby('date').y_xs.rank(pct=True)
D = sorted(V.date.unique())
V['scoreW'] = np.nan; WLOG = []
coefs = {}
for d in D:
    X = V[(V.date == d) & V.y_rkind.notna()]
    Z = X[['rk_' + c for c in COMP6]].fillna(0.5).values; Z = np.c_[np.ones(len(Z)), Z - 0.5]
    if len(X) > 20: coefs[d] = np.linalg.lstsq(Z, X.y_rkind.values - 0.5, rcond=None)[0][1:]
C = pd.DataFrame(coefs, index=COMP6).T
for y in range(2014, 2027):
    test = [d for d in D if pd.Timestamp(d).year == y]
    if not test: continue
    cut = pd.Timestamp(test[0]) - pd.offsets.QuarterEnd(4)
    tr = C[C.index <= cut]
    if len(tr) < 8: continue
    b = tr.mean().values
    m = V.date.isin(test)
    V.loc[m, 'scoreW'] = (V.loc[m, ['rk_' + c for c in COMP6]].fillna(0.5).values - 0.5) @ b
    WLOG.append({'anno_test': y, 'n_date_train': len(tr), **{c: round(v, 3) for c, v in zip(COMP6, b)}})
V['W'] = V.scoreW.notna() & (V.scoreW.groupby(V.date).rank(pct=True) > 0.9)
V.to_pickle(f'{OUT}/ind_flags.pkl')
pd.DataFrame(WLOG).to_csv(f'{OUT}/W_pesi.csv', index=False)
print(pd.DataFrame(WLOG).to_string())
print('coefficienti FM su tutto 2012-2025 (solo descrittivo), t NW:')
print(pd.DataFrame({'media': C.mean(), 't': [nw_t(C[c]) for c in C]}).round(3).to_string())
for r in ['A', 'Aplus', 'B', 'Bplus', 'W', 'MOM', 'CALDE']:
    n = V.groupby('date')[r].sum()
    print(r, 'industrie segnalate per data: media %.1f min %d max %d' % (n.mean(), n.min(), n.max()))
