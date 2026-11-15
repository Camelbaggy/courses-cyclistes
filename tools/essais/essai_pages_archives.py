#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vérifie que le site GitHub Pages du dépôt d'archives sert les fichiers lus par la page (statut, CORS, contenu)."""
import json
import urllib.request

BASE = "https://camelbaggy.github.io/courses-cyclistes-archives/data/archives"
for chemin in ("index.json", "editions.json", "carrieres/index.json", "2025/index.json", "2025/ranking.json"):
    url = f"{BASE}/{chemin}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "courses-cyclistes-essai", "Origin": "https://camelbaggy.github.io"})
        with urllib.request.urlopen(req, timeout=30) as r:
            corps = r.read()
            print(f"{chemin} : HTTP {r.status}, {len(corps)} octets, CORS={r.headers.get('Access-Control-Allow-Origin')}, "
                  f"type={r.headers.get('Content-Type')}")
            if chemin == "index.json":
                print("   ", [(s["season"], s["complete"], s["races"]) for s in json.loads(corps)["seasons"]])
    except Exception as e:
        print(f"{chemin} : ÉCHEC {e}")
