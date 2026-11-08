#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : découverte des endpoints de classement DataRide (phase de sonde 6 : filtres d'ObjectRankings)."""
import json
import sys

sys.path.insert(0, ".")
import netutil  # noqa: E402
import uci  # noqa: E402

BASE = uci.BASE


def j(x, n=900):
    s = json.dumps(x, ensure_ascii=False)
    return s[:n] + (f"...(+{len(s) - n})" if len(s) > n else "")


def resume(nom, rep):
    if isinstance(rep, dict):
        d = rep.get("data") or []
        print(f"{nom}: total={rep.get('total')} len={len(d)}")
        for r in (d[:2] + d[-1:]):
            print("   ", {k: r.get(k) for k in ("Rank", "DisplayName", "NationName", "TeamName", "Points", "BirthDate", "ComputationDate", "MomentId", "UciId")})
        if d:
            print("    clés:", sorted(d[0].keys()))
    else:
        print(f"{nom}: {type(rep).__name__} {j(rep)}")


for sid in (477, 464):
    m = netutil.fetch_json(f"{BASE}/iframe/GetRankingMoments/?disciplineId=10&disciplineSeasonId={sid}&rankingId=1")
    print(f"MOMENTS saison {sid}:", j(m, 900))

base = [("RaceTypeId", 0), ("CategoryId", 22), ("SeasonId", 477), ("MomentId", 206851)]
args = dict(rankingId=1, disciplineId=10, rankingTypeId=1)
A = uci._post("/iframe/ObjectRankings/", uci._kendo(1000, 0, base, None, **args), "or_a")
resume("V1 filtres RaceType/Category/Season/Moment, take=1000", A)
B = uci._post("/iframe/ObjectRankings/", uci._kendo(100, 0, base + [("CountryId", 0)], None, **args), "or_b")
resume("V2 + CountryId=0, take=100", B)
C = uci._post("/iframe/ObjectRankings/", uci._kendo(100, 100, base, None, **args), "or_c")
resume("V3 V1 skip=100 take=100", C)
