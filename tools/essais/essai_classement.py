#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : découverte des endpoints de classement DataRide (phase de sonde 2)."""
import json
import re
import sys

sys.path.insert(0, ".")
import netutil  # noqa: E402
import uci  # noqa: E402

BASE = "https://dataride.uci.org"
H = {"X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/iframe/Rankings/10/"}


def j(x, n=1500):
    s = json.dumps(x, ensure_ascii=False)
    return s[:n] + (f"...(+{len(s) - n})" if len(s) > n else "")


saisons = netutil.fetch_json(BASE + "/iframe/GetDisciplineSeasons/?disciplineId=10", headers=None) if False else \
    netutil.fetch_json(BASE + "/iframe/GetDisciplineSeasons/?disciplineId=10")
print("SAISONS", j(saisons, 800))
sid = 464
cats = netutil.fetch_json(f"{BASE}/iframe/GetRankingsCategories/?disciplineId=10&disciplineSeasonId={sid}")
print("CATS", j(cats))
rts = netutil.fetch_json(f"{BASE}/iframe/GetRankingsRaceTypes/?disciplineId=10&disciplineSeasonId={sid}")
print("RACETYPES", j(rts))

# liste des classements disponibles (même grille Kendo que la page)
for sai in (464, 477):
    f = [("RaceTypeId", 0), ("CategoryId", 22), ("SeasonId", sai)]
    rep = uci._post("/iframe/RankingsDiscipline/", uci._kendo(100, 0, f, None, disciplineId=10), f"rd_{sai}")
    print(f"RANKINGSDISCIPLINE saison {sai}:", j(rep, 3500))

# page de détail du premier classement + JS
rep = uci._post("/iframe/RankingsDiscipline/", uci._kendo(100, 0, [("RaceTypeId", 0), ("CategoryId", 22), ("SeasonId", 464)], None, disciplineId=10), "rd")
lignes = rep.get("data") if isinstance(rep, dict) else (rep if isinstance(rep, list) else [])
if lignes:
    d = lignes[0]
    url = (f"/iframe/RankingDetails/{d.get('Id')}?disciplineId={d.get('DisciplineId')}&groupId={d.get('GroupId')}"
           f"&momentId={d.get('MomentId')}&disciplineSeasonId={d.get('DisciplineSeasonId')}&rankingTypeId={d.get('RankingTypeId')}"
           f"&categoryId={d.get('CategoryId')}&raceTypeId={d.get('RaceTypeId')}")
    print("DETAIL URL", url)
    t = netutil.fetch_text(BASE + url, headers=H, retries=1)
    if t:
        print("taille", len(t))
        sc = "\n".join(re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", t, re.S))
        sc = re.sub(r"[ \t]+", " ", sc)
        sc = re.sub(r"\n\s*\n+", "\n", sc)
        i = sc.find("ObjectRankings")
        print("JS ObjectRankings:", sc[max(0, i - 1500):i + 2500] if i >= 0 else "absent")
        print("JS début:", sc[:1500])
