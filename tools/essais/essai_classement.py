#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : découverte des pages iframe DataRide « classements » (phase de sonde)."""
import re
import sys

sys.path.insert(0, ".")
import netutil  # noqa: E402

BASE = "https://dataride.uci.org"
H = {"Referer": BASE + "/iframe/Rankings/10/"}
t = netutil.fetch_text(BASE + "/iframe/Rankings/10/", headers=H, retries=1)
sc = re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", t, re.S)
txt = "\n".join(sc)
txt = re.sub(r"[ \t]+", " ", txt)
txt = re.sub(r"\n\s*\n+", "\n", txt)
for mot in ("RankingsDiscipline", "TypeOfRankings", "ObjectRankings", "GetRankingsCategories", "GetRankingsRaceTypes",
            "GetDisciplineSeasons"):
    for m in re.finditer(mot, txt):
        print(f"\n===== {mot} @ {m.start()}")
        print(txt[max(0, m.start() - 700):m.start() + 900])
        break
# aussi tout le HTML visible (selects, ids)
print("\n===== éléments HTML")
print(re.findall(r'<(?:select|input|div)[^>]+id="([^"]+)"', t)[:60])
