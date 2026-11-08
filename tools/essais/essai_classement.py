#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : découverte des endpoints de classement DataRide (phase de sonde 3)."""
import json
import re
import sys

sys.path.insert(0, ".")
import netutil  # noqa: E402
import uci  # noqa: E402

BASE = "https://dataride.uci.org"
H = {"X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/iframe/Rankings/10/"}

f = [("RaceTypeId", 0), ("CategoryId", 22), ("SeasonId", 477)]
rep = uci._post("/iframe/RankingsDiscipline/", uci._kendo(100, 0, f, None, disciplineId=10), "rd")
print("type", type(rep).__name__, "clés", list(rep.keys()) if isinstance(rep, dict) else len(rep))
groupes = rep if isinstance(rep, list) else rep.get("data", [])
for g in groupes:
    print("GROUPE", g.get("GroupId"), g.get("GroupName"))
    for r in g.get("Rankings", []):
        print("   ranking Id", r.get("Id"), r.get("RankingName"), "typeId", r.get("RankingTypeId"), "moment", r.get("MomentId"),
              "cat", r.get("CategoryId"), "nb aperçu", len(r.get("ObjectRankings") or []), "total", r.get("TotalObjectRanking"),
              "active", r.get("Active"), "calendar", r.get("Calendar"), "continent", r.get("Continent"))
        o = (r.get("ObjectRankings") or [])
        if o:
            print("      dernier aperçu rang", o[-1].get("Rank"), o[-1].get("DisplayName"), o[-1].get("Points"))

url = ("/iframe/RankingDetails/1?disciplineId=10&groupId=1&momentId=206851&disciplineSeasonId=477&rankingTypeId=1"
       "&categoryId=22&raceTypeId=0")
t = netutil.fetch_text(BASE + url, headers=H, retries=1)
print("DETAIL taille", len(t or ""))
if t:
    sc = "\n".join(re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", t, re.S))
    sc = re.sub(r"[ \t]+", " ", sc)
    sc = re.sub(r"\n\s*\n+", "\n", sc)
    sc = re.sub(r"\s+", " ", sc)
    for mot in ("/iframe/ObjectRankings/", "/iframe/TypeOfRankings/"):
        for m in re.finditer(re.escape(mot), sc):
            print(f"== JS {mot} @{m.start()}:", sc[max(0, m.start() - 900):m.start() + 700])
