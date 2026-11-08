#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : découverte des endpoints de classement DataRide (phase de sonde 5 : JS de RankingDetails)."""
import re
import sys

sys.path.insert(0, ".")
import netutil  # noqa: E402

BASE = "https://dataride.uci.org"
H = {"X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/iframe/Rankings/10/"}
url = ("/iframe/RankingDetails/1?disciplineId=10&groupId=1&momentId=206851&disciplineSeasonId=477&rankingTypeId=1"
       "&categoryId=22&raceTypeId=0")
t = netutil.fetch_text(BASE + url, headers=H, retries=1)
print("DETAIL taille", len(t or ""))
print("hidden:", re.findall(r'<input[^>]*id="fixed[^>]*>', t))
sc = "\n".join(re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", t, re.S))
sc = re.sub(r"\s+", " ", sc)
for mot in ("objectsSource(", "createRankingsSource(", "fixedRankingId", "GetMoments", "dates"):
    for m in list(re.finditer(re.escape(mot), sc))[:4]:
        print(f"== {mot} @{m.start()}:", sc[max(0, m.start() - 250):m.start() + 450])
i = sc.find("$(document)")
print("== READY:", sc[i:i + 6000] if i >= 0 else "absent")
