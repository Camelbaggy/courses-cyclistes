#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : un vrai navigateur sans tête (Chromium de Playwright, sans déguisement) passe-t-il le contrôle
Cloudflare de FirstCycling depuis GitHub Actions ?

Accord écrit des administrateurs de FirstCycling obtenu par le propriétaire du projet (18/11/2026) : robots.txt et
CGU levés pour ce site. Le navigateur exécute le JavaScript de la page comme un visiteur ordinaire ; AUCUNE falsification
d'empreinte, aucun plugin de dissimulation, aucun service de résolution de captcha. 5 pages, 5 s entre chacune."""
import subprocess
import sys
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"], check=True)
    from playwright.sync_api import sync_playwright
subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=True,
               stdout=subprocess.DEVNULL)

URLS = [
    "https://firstcycling.com/race.php?r=30&y=2005",
    "https://firstcycling.com/race.php?r=17&y=1998&e=01",
    "https://firstcycling.com/rider.php?r=1",
]

with sync_playwright() as p:
    nav = p.chromium.launch(headless=True)
    page = nav.new_context().new_page()
    print("User-Agent du navigateur :", page.evaluate("navigator.userAgent"))
    for u in URLS:
        reponse = page.goto(u, wait_until="domcontentloaded", timeout=60000)
        code = reponse.status if reponse else None
        titre = page.title()
        # contrôle Cloudflare : « Just a moment... » ; on laisse le JavaScript de la page s'exécuter jusqu'à 25 s
        attente = 0
        while "Just a moment" in titre and attente < 25:
            time.sleep(1)
            attente += 1
            titre = page.title()
        tables = page.locator("table").count()
        lignes = page.locator("table tr").count()
        case = page.locator("iframe[src*='challenges.cloudflare.com']").count()
        print(f"== {u}\n   code initial={code} titre final={titre[:80]!r} attente={attente}s tableaux={tables} lignes={lignes}"
              f" défi interactif (iframe Turnstile)={case}")
        if tables:
            print("   extrait :", " | ".join(page.locator("table tr").nth(i).inner_text().replace("\n", " ")[:90]
                                            for i in range(min(4, lignes))))
        time.sleep(5)
    nav.close()
