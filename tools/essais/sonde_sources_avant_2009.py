#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde de recherche : sources de résultats cyclistes d'avant 2009 (docs/recherche/sources_avant_2009.md).

Lecture seule, rien n'est écrit dans le dépôt : réponses mises en cache dans --sortie.

    python tools/essais/sonde_sources_avant_2009.py robots HOTE [HOTE...]   # robots.txt (texte brut)
    python tools/essais/sonde_sources_avant_2009.py get URL [--max N]       # une page : code, en-têtes, début du corps

Politesse : User-Agent honnête « courses-cyclistes (recherche) », 2 s minimum entre deux requêtes sur un même hôte,
cache disque (relancer ne coûte rien), AUCUN contournement : un 403 / 429 / challenge est noté et l'hôte abandonné.
Les contenus lus sont du texte à mesurer, jamais exécutés.
"""
import argparse
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "courses-cyclistes (recherche)"
SORTIE = os.environ.get("SONDE_SORTIE", "/tmp/claude-0/-home-user/6e2e0406-5df6-58a6-9dc4-3a5a69463a2b/scratchpad/s")
_dernier = {}
_bloques = set()


def get(url, timeout=30):
    """Retourne (code, en-têtes, corps texte). Cache disque ; pause de 2 s par hôte ; hôte abandonné sur 403 / 429."""
    os.makedirs(SORTIE, exist_ok=True)
    cle = os.path.join(SORTIE, hashlib.sha1(url.encode()).hexdigest())
    if os.path.exists(cle + ".body"):
        with open(cle + ".meta", encoding="utf-8") as f:
            meta = f.read().split("\n", 1)
        with open(cle + ".body", encoding="utf-8", errors="replace") as f:
            return int(meta[0]), meta[1], f.read()
    hote = urllib.parse.urlparse(url).netloc
    if hote in _bloques:
        return 0, "hôte abandonné", ""
    att = _dernier.get(hote, 0) + 2.0 - time.time()
    if att > 0:
        time.sleep(att)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code, hdr, raw = r.status, str(r.headers), r.read()
    except urllib.error.HTTPError as e:
        code, hdr, raw = e.code, str(e.headers), e.read() if hasattr(e, "read") else b""
    except Exception as e:  # réseau
        code, hdr, raw = -1, "erreur: %r" % (e,), b""
    _dernier[hote] = time.time()
    if code in (403, 429):
        _bloques.add(hote)
    m = re.search(r"charset=([\w-]+)", hdr, re.I) or re.search(rb'charset=["\']?([\w-]+)', raw[:3000], re.I)
    enc = (m.group(1).decode() if isinstance(m.group(1), bytes) else m.group(1)) if m else "utf-8"
    try:
        corps = raw.decode(enc, errors="replace")
    except LookupError:
        corps = raw.decode("utf-8", errors="replace")
    with open(cle + ".meta", "w", encoding="utf-8") as f:
        f.write("%d\n%s" % (code, hdr))
    with open(cle + ".body", "w", encoding="utf-8") as f:
        f.write(corps)
    return code, hdr, corps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["robots", "get"])
    ap.add_argument("cibles", nargs="+")
    ap.add_argument("--max", type=int, default=1500)
    a = ap.parse_args()
    for c in a.cibles:
        url = ("https://%s/robots.txt" % c) if a.cmd == "robots" else c
        code, hdr, corps = get(url)
        marq = [m for m in ("Just a moment", "cf-chl", "cf-ray", "cloudflare", "captcha") if m.lower() in (hdr + corps[:5000]).lower()]
        print("=== %s -> HTTP %s, %d octets, marqueurs anti-robot: %s" % (url, code, len(corps), marq or "aucun"))
        if a.cmd == "get":
            for l in hdr.splitlines():
                if l.lower().startswith(("server", "content-type", "last-modified", "x-robots")):
                    print("  " + l)
        print(corps[:a.max])


if __name__ == "__main__":
    main()
