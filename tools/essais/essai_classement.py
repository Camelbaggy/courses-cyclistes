#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : découverte des endpoints de classement DataRide (phase de sonde 4)."""
import json
import sys

sys.path.insert(0, ".")
import uci  # noqa: E402

N = 0


def post(chemin, champs, nom):
    global N
    N += 1
    return uci._post(chemin, champs, nom)


def j(x, n=700):
    s = json.dumps(x, ensure_ascii=False)
    return s[:n] + (f"...(+{len(s) - n})" if len(s) > n else "")


def resume(nom, rep):
    if isinstance(rep, dict):
        d = rep.get("data") or []
        print(f"{nom}: clés={list(rep.keys())} total={rep.get('total')} len={len(d)}")
        for r in (d[:1] + d[-1:]):
            print("   ", {k: r.get(k) for k in ("Rank", "DisplayName", "NationName", "TeamName", "Points", "BirthDate", "ComputationDate", "MomentId", "UciId", "ObjectId")})
        if d:
            print("    clés ligne:", sorted(d[0].keys()))
    else:
        print(f"{nom}: {type(rep).__name__} {j(rep)}")


f = [("RaceTypeId", 0), ("CategoryId", 22), ("SeasonId", 477)]
rep = post("/iframe/RankingsDiscipline/", uci._kendo(100, 0, f, None, disciplineId=10), "rd")
for g in rep:
    print("GROUPE", g.get("GroupId"), g.get("GroupName"), [(r.get("Id"), r.get("RankingTypeId"), r.get("RankingName"), r.get("MomentId")) for r in g.get("Rankings", [])])

print("---- TypeOfRankings")
rep = post("/iframe/TypeOfRankings/", uci._kendo(40, 0, None, None, rankingId=1, groupId=1, momentId=206851, disciplineId=10, currentRankingTypeId=1), "tor")
print(j(rep, 1200))

print("---- ObjectRankings")
A = post("/iframe/ObjectRankings/", uci._kendo(100, 0, None, None, rankingId=1, disciplineId=10, rankingTypeId=1), "or_a")
resume("A rankingId=1", A)
B = post("/iframe/ObjectRankings/", uci._kendo(100, 0, None, None, rankingId=1, disciplineId=10, rankingTypeId=1, momentId=206290), "or_b")
resume("B +momentId=206290 (saison 2026)", B)
C = post("/iframe/ObjectRankings/", uci._kendo(1000, 0, None, None, rankingId=1, disciplineId=10, rankingTypeId=1), "or_c")
resume("C pageSize=1000", C)
print("requêtes:", N + 0)
