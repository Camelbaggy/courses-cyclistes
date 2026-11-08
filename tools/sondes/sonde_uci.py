"""Sonde UCI (bibliothèque standard uniquement) : découvre les endpoints publics de uci.org / dataride.uci.ch.
User-Agent honnête, pause >= 1 s entre requêtes, aucun contournement (challenge / 403 : on note et on s'arrête)."""
import re, sys, time, json, urllib.request, urllib.error

UA = "courses-cyclistes-sonde/0.1 (projet personnel non commercial)"
_last = [0.0]
STOP = [False]


def get(url, accept="*/*", maxprint=600, show=True, data=None, headers=None):
    if STOP[0]:
        print("ARRET (blocage anti-robot constaté), requête ignorée:", url)
        return None, ""
    d = 1.1 - (time.time() - _last[0])
    if d > 0:
        time.sleep(d)
    h = {"User-Agent": UA, "Accept": accept}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h, data=data)
    try:
        r = urllib.request.urlopen(req, timeout=30)
        code, body, hd = r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        code, body, hd = e.code, e.read(), e.headers
    except Exception as e:
        print(f"\n=== {url}\n  ERREUR {e}")
        return None, ""
    _last[0] = time.time()
    txt = body.decode("utf-8", "replace")
    print(f"\n=== {url}\n  HTTP {code} | {hd.get('content-type')} | {len(body)} o | server={hd.get('server')}")
    if code in (403, 429, 503) or "Just a moment" in txt[:3000] or "cf-chl" in txt[:5000]:
        print("  >>> challenge / blocage : arrêt des requêtes vers ce site")
        STOP[0] = True
    if show:
        print("  " + txt[:maxprint].replace("\n", "\n  "))
    return code, txt


def liens(txt, base=""):
    out = set()
    for m in re.finditer(r'''(?:src|href|action|data-src|data-url)\s*=\s*["']([^"']+)["']''', txt, re.I):
        out.add(m.group(1))
    for m in re.finditer(r'''["'](https?://[^"'\s<>\\]+|/[A-Za-z0-9_\-./?=&%]+)["']''', txt):
        out.add(m.group(1))
    return out


def interessants(txt):
    mots = re.compile(r"iframe|dataride|api|calendar|result|ranking|event|\.json|xhr|fetch\(|axios", re.I)
    return sorted(l for l in liens(txt) if mots.search(l))


def explorer(url, n=60):
    code, txt = get(url, accept="text/html", show=False)
    if not txt:
        return txt
    print("  <title>:", re.findall(r"<title[^>]*>(.*?)</title>", txt, re.S)[:1])
    print("  iframes:", re.findall(r"<iframe[^>]*>", txt, re.I)[:10])
    print("  __NEXT_DATA__/ng/vue:", [k for k in ("__NEXT_DATA__", "ng-app", "data-reactroot", "__NUXT__", "dataride") if k in txt])
    for l in interessants(txt)[:n]:
        print("   -", l[:200])
    return txt


def passe1():
    get("https://dataride.uci.ch/robots.txt", maxprint=1500)
    get("https://www.uci.org/robots.txt", maxprint=500)
    for u in ("https://www.uci.org/", "https://www.uci.org/discipline/road",
              "https://www.uci.org/calendar", "https://www.uci.org/results",
              "https://www.uci.org/discipline/road/calendar"):
        explorer(u)


if __name__ == "__main__":
    passe1()
