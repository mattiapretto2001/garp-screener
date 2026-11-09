# temi_09: PROPOSTA di etichettatura dei temi dalle descrizioni EODHD (General.Description), solo come aiuto per raggruppare.
# Le descrizioni NON sono su disco (fund2.pkl conserva solo Code/Name/Sector/Industry/GicIndustry/IPODate): vanno scaricate dall'agente
# "Dati" (fundamentals con filter=General::Description; costo EODHD: chiamata fondamentali = 10 crediti per titolo).
# REGOLE D'USO (per non usarle a posteriori):
#  1. La descrizione e' il testo di OGGI: dice cosa fa la societa' oggi, non cosa faceva nel 2015. Quindi:
#     - SI': raggruppare le societa' di oggi in temi trasversali alle industrie (es. "data center" = semiconduttori + elettrico + utility);
#     - SI': applicare a questi gruppi la stessa regola ex ante delle industrie (accelerazione ricavi, ampiezza, margini) DA ORA IN AVANTI;
#     - NO: usare l'etichetta in un backtest come se fosse nota nel passato, ne' come segnale per scegliere i vincitori.
#  2. Salvare ogni scarico con la data (es. tags_2026-11.csv) e riscaricare ogni 6-12 mesi: da qui in avanti si costruisce uno storico
#     delle etichette davvero "alla data", che fra qualche anno permettera' un test onesto.
#  3. Un'etichetta richiede almeno 2 parole chiave del tema (o 1 'forte'); parole negative la annullano; controllo a mano dei casi dubbi.
import re, sys, json, pandas as pd
TEMI = {   # tema: (parole forti, parole deboli, parole negative)
    'IA e data center': (['data center', 'datacenter', 'artificial intelligence', 'ai accelerator', 'gpu', 'hyperscale', 'ai server'],
                         ['high-performance computing', 'hpc', 'machine learning', 'cloud infrastructure', 'liquid cooling', 'optical interconnect'],
                         []),
    'Semiconduttori e attrezzature': (['semiconductor', 'wafer', 'lithography', 'foundry'], ['chip', 'integrated circuit', 'memory', 'dram', 'nand'], []),
    'Fotonica e reti ottiche': (['photonic', 'optical transceiver', 'silicon photonics', 'laser'], ['fiber optic', 'optical component', 'coherent'], []),
    'Rete elettrica e trasmissione': (['transmission and distribution', 'power grid', 'grid infrastructure', 'transformer', 'switchgear', 'substation'],
                                      ['high-voltage', 'cable', 'electrification', 'power equipment'], []),
    'Nucleare e uranio': (['nuclear', 'uranium', 'small modular reactor', 'smr'], ['enrichment', 'fuel cycle'], ['nuclear medicine', 'nuclear magnetic']),
    'Rinnovabili e accumulo': (['solar', 'photovoltaic', 'wind turbine', 'energy storage', 'battery storage'], ['renewable', 'inverter', 'hydrogen'], []),
    'Batterie e veicoli elettrici': (['lithium-ion', 'battery cell', 'electric vehicle', 'ev charging'], ['cathode', 'anode', 'lithium'], []),
    'Obesita\' e diabete (GLP-1)': (['glp-1', 'obesity', 'semaglutide', 'tirzepatide', 'incretin'], ['diabetes', 'weight management', 'metabolic'], []),
    'Difesa e spazio': (['defense', 'defence', 'missile', 'military', 'satellite', 'launch vehicle'], ['aerospace', 'radar', 'munitions', 'space'],
                        ['defense mechanism']),
    'Cybersicurezza': (['cybersecurity', 'cyber security', 'endpoint protection', 'zero trust', 'firewall'], ['identity', 'threat', 'security operations'], []),
    'Robotica e automazione': (['robot', 'robotic', 'industrial automation', 'machine vision'], ['automation', 'motion control', 'cobot'], ['robotic process automation']),
    'Rame e metalli per l\'elettrificazione': (['copper'], ['electrification', 'critical minerals'], []),
}
def tag(text):
    t = ' ' + re.sub(r'\s+', ' ', str(text).lower()) + ' '
    out = {}
    for tema, (forti, deboli, neg) in TEMI.items():
        pat = lambda w: r'(?<![a-z])' + re.escape(w) + r'(?:s|es)?(?![a-z])'       # parola intera, plurale ammesso
        hf = [w for w in forti if re.search(pat(w), t)]
        hd = [w for w in deboli if re.search(pat(w), t)]
        hn = [w for w in neg if w in t]
        punti = 2 * len(hf) + len(hd) - 3 * len(hn)
        if punti >= 2: out[tema] = {'punti': punti, 'parole': hf + hd}
    return out
if __name__ == '__main__':
    if len(sys.argv) > 1:   # uso: python -I temi_09_tag_descrizioni.py descrizioni.csv  (colonne: t, description) -> tags_<data>.csv
        D = pd.read_csv(sys.argv[1]); rows = []
        for t, d in zip(D.t, D.description):
            for tema, v in tag(d).items(): rows.append({'t': t, 'tema': tema, 'punti': v['punti'], 'parole': ' | '.join(v['parole'])})
        pd.DataFrame(rows).to_csv(sys.argv[1].replace('.csv', '_tags.csv'), index=False); print(len(rows), 'etichette')
    else:                   # prova su testi inventati (NON societa' reali)
        prove = ['The company designs GPUs and AI accelerators for data center and high-performance computing markets.',
                 'Manufactures switchgear, transformers and substation equipment for power grid operators.',
                 'Develops imaging agents for nuclear medicine.',
                 'Offers robotic process automation software for back offices.',
                 'Biopharmaceutical company focused on GLP-1 therapies for obesity and type 2 diabetes.']
        for p in prove: print(tag(p), '<-', p[:70])
