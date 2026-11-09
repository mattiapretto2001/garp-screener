# Elenco trimestre per trimestre dei promossi B1 dal 12/2024, con settore e una frase sull'attivita' -> results/svolta2_elenco.md
import pandas as pd, os
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
D = pd.read_csv(f'{BASE}/results/svolta2_promossi_recenti.csv')
S = pd.read_csv(f'{BASE}/results/svolta2_serie.csv', index_col=0, parse_dates=True)
COSA = {
 'BCRX': 'farmaco orale per l\'angioedema ereditario', 'VCEL': 'terapie cellulari per cartilagine e ustioni', 'BMRN': 'farmaci per malattie genetiche rare',
 'APPF': 'software cloud per la gestione immobiliare', 'GWRE': 'software per compagnie assicurative', 'AUPH': 'farmaco per la nefrite lupica',
 'INSP': 'impianto per l\'apnea notturna', 'AVPT': 'software di gestione e protezione dei dati Microsoft 365', 'KVYO': 'software di marketing email/SMS per e-commerce',
 'ZETA': 'piattaforma di marketing basata sui dati', 'ALKT': 'software di banca digitale per banche locali', 'LIF': 'app di localizzazione per famiglie',
 'PRM': 'ritardanti di fiamma per incendi boschivi', 'PEGA': 'software di automazione dei processi aziendali', 'EXTR': 'apparati di rete aziendali',
 'NAGE': 'integratori (NAD+)', 'NTNX': 'software per infrastruttura cloud ibrida', 'IMCR': 'farmaci oncologici (recettori T)',
 'TMDX': 'sistemi per il trasporto di organi da trapianto', 'WGS': 'test genetici (esoma e genoma)', 'GTLB': 'piattaforma software per sviluppatori',
 'KNSA': 'farmaco per la pericardite ricorrente', 'XERS': 'farmaci endocrinologici', 'HAS': 'giocattoli e giochi (anche digitali)',
 'AXGN': 'prodotti per la riparazione dei nervi', 'SLAB': 'chip wireless per oggetti connessi', 'GMED': 'dispositivi per chirurgia della colonna',
 'ATEC': 'dispositivi per chirurgia della colonna', 'HROW': 'farmaci oftalmici', 'IRTC': 'monitor cardiaci indossabili',
 'CALX': 'piattaforma per operatori di banda larga', 'APPN': 'software low-code per i processi', 'WK': 'software per bilanci e rendicontazione',
 'MQ': 'piattaforma di emissione di carte di pagamento', 'PEN': 'dispositivi per rimuovere trombi', 'DUOL': 'app per imparare le lingue',
 'FIGS': 'abbigliamento per personale sanitario', 'CGNX': 'visione artificiale industriale', 'BB': 'software di sicurezza e per auto (QNX)',
 'PDFS': 'software di analisi dati per fabbriche di chip', 'TTAN': 'software per imprese di servizi tecnici', 'FROG': 'software per gestire i rilasci del software',
 'VIAV': 'strumenti di test per reti e componenti ottici', 'MXL': 'chip per comunicazioni e ottica nei data center', 'TVTX': 'farmaci per malattie renali rare',
 'FSLY': 'rete di distribuzione dei contenuti (edge cloud)', 'HNGE': 'fisioterapia digitale', 'BRZE': 'software di relazione con i clienti',
 'RDVT': 'dati e analisi per verifiche di identità', 'CHYM': 'banca digitale (fintech)'}
b = D[D.strategia == 'B1']
o = []
for t, g in b.groupby('data', sort=True):
    tt = pd.Timestamp(t)
    rr = S.loc[tt]
    end = min(tt + pd.offsets.QuarterEnd(1), pd.Timestamp('2026-11-03'))
    o.append(f'**Ribilanciamento {tt:%d/%m/%Y}** (rendimento fino al {end:%d/%m/%Y}): B1 {rr["B1"]*100:+.1f}%, Moonshot {rr["Moonshot"]*100:+.1f}%, '
             f'GARP {rr["GARP"]*100:+.1f}%, universo {rr["universo"]*100:+.1f}%, SPY {rr["SPY"]*100:+.1f}%; {len(g)} titoli\n'.replace('.', ','))
    o.append('| Ticker | Società | SIC | Cosa fa | Rend. trim. | P/ricavi | P/MA200 | Moonshot |')
    o.append('|---|---|---|---|---|---|---|---|')
    for r in g.sort_values('r3').itertuples():
        o.append(f'| {r.ticker} | {r.nome} | {int(r.sic) if pd.notna(r.sic) else ""} | {COSA.get(r.ticker, "")} | {r.r3*100:+.0f}% | {r.ps:.1f} | {r.prezzo_su_ma200:.2f} | {"sì" if r.anche_moonshot else ""} |'.replace(f'{r.ps:.1f}', f'{r.ps:.1f}'.replace('.', ',')).replace(f'{r.prezzo_su_ma200:.2f}', f'{r.prezzo_su_ma200:.2f}'.replace('.', ',')))
    o.append('')
open(f'{BASE}/results/svolta2_elenco.md', 'w').write('\n'.join(o)); print('\n'.join(o)[:3000])
