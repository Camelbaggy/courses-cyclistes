#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : FirstCycling est-il joignable depuis GitHub Actions par de simples requêtes HTTP ?

Accord des administrateurs de FirstCycling obtenu par le propriétaire du projet (18/11/2026). La règle « aucun
contournement anti-robot » reste valable : cet essai ne fait que des requêtes ordinaires (User-Agent honnête, pas de
faux navigateur, pas de jeton) et constate la réponse (code, protection Cloudflare, titre de la page). 3 s entre requêtes."""
import re
import time
import urllib.error
import urllib.request

UA = "courses-cyclistes/1.0 (collecte autorisee par les administrateurs de FirstCycling ; https://github.com/Camelbaggy/courses-cyclistes)"
URLS = [
    "https://firstcycling.com/robots.txt",
    "https://firstcycling.com/",
    "https://firstcycling.com/race.php?r=30&y=2005",          # course, année 2005
    "https://firstcycling.com/race.php?r=17&y=1998&e=01",     # étape d'une course par étapes, 1998
    "https://firstcycling.com/rider.php?r=1",                 # fiche coureur
]

for u in URLS:
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html,text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code, h, corps = r.status, r.headers, r.read(200_000)
    except urllib.error.HTTPError as e:
        code, h, corps = e.code, e.headers, e.read(200_000)
    except Exception as e:  # réseau
        print(f"== {u}\n   ERREUR {e!r}")
        time.sleep(3)
        continue
    texte = corps.decode("utf-8", "replace")
    titre = re.search(r"<title>(.*?)</title>", texte, re.S | re.I)
    print(f"== {u}\n   code={code} server={h.get('server')} cf-mitigated={h.get('cf-mitigated')} taille={len(corps)}"
          f" titre={titre.group(1).strip()[:80] if titre else '-'}")
    if u.endswith("robots.txt"):
        print("   " + texte.strip().replace("\n", " | ")[:400])
    elif code == 200 and "Just a moment" not in texte:
        tables = len(re.findall(r"<table", texte, re.I))
        print(f"   page servie : {tables} tableau(x) HTML ; extrait : {re.sub(r'<[^>]+>', ' ', texte)[:300].split()!r}"[:500])
    time.sleep(3)
