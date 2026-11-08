#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : découverte des pages iframe DataRide « classements » (phase de sonde)."""
import re
import sys
import time

sys.path.insert(0, ".")
import netutil  # noqa: E402

BASE = "https://dataride.uci.org"
H = {"Referer": BASE + "/iframe/Results/10/"}
NB = 0


def get(chemin):
    global NB
    NB += 1
    return netutil.fetch_text(BASE + chemin, headers=H, retries=1)


def explore(chemin):
    print(f"\n######## GET {chemin}")
    t = get(chemin)
    if t is None:
        print("  -> aucune réponse")
        return None
    print(f"  {len(t)} octets ; titre: {re.findall(r'<title>(.*?)</title>', t, re.S)[:1]}")
    print("  scripts:", re.findall(r'<script[^>]+src="([^"]+)"', t)[:15])
    urls = sorted(set(re.findall(r'["\'](/?(?:iframe/)?[A-Za-z]*(?:Rank|rank)[A-Za-z/_?=&0-9]*)["\']', t)))
    print("  chaînes *Rank*:", urls[:40])
    for m in re.finditer(r'url\s*:\s*["\']([^"\']+)["\']', t):
        print("  url:", m.group(1), "|", t[max(0, m.start() - 80):m.start()].replace("\n", " ")[-80:])
    for m in re.finditer(r'(?:href|action)="([^"]*iframe[^"]*)"', t):
        print("  lien:", m.group(1))
    print("  extrait corps:", re.sub(r"\s+", " ", re.sub(r"<script.*?</script>", "", t, flags=re.S))[:600])
    return t


for c in ["/iframe/Rankings/10/", "/iframe/Rankings/10", "/iframe/RankingDetails/10/", "/iframe/Ranking/10/",
          "/iframe/Rankings/", "/iframe/"]:
    explore(c)
print(f"\nrequêtes: {NB}")
