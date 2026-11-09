# Storico 2000-2011 (punto 5): funzioni comuni per le chiamate EODHD.
# Chiave: se esiste la variabile d'ambiente EODHD_API_TOKEN (GitHub Actions) va nel parametro api_token;
# altrimenti non si manda nulla (in questa sessione la chiave la aggiunge il proxy come Bearer).
import os, json, time, urllib.request, urllib.error, urllib.parse
ML = os.path.dirname(os.path.abspath(__file__))
BW = os.path.dirname(ML)
OUT = f'{ML}/storico5'
os.makedirs(OUT, exist_ok=True)


def url(path, **params):
    tok = os.environ.get('EODHD_API_TOKEN')
    if tok: params['api_token'] = tok
    params.setdefault('fmt', 'json')
    return f'https://eodhd.com/api/{path}?' + urllib.parse.urlencode(params)


def get(path, tries=4, timeout=180, **params):
    u = url(path, **params)
    for i in range(tries):
        try:
            with urllib.request.urlopen(u, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if e.code == 402: return 'LIMIT'
            time.sleep(20 if e.code == 429 else 2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return 'ERR'


def usage():
    j = get('user')
    return j.get('apiRequests') if isinstance(j, dict) else None


def guard(limit_abs):
    """ferma il lavoro se il contatore di oggi supera limit_abs"""
    u = usage()
    if u is not None and u >= limit_abs:
        raise SystemExit(f'contatore {u} >= tetto {limit_abs}: mi fermo')
    return u
