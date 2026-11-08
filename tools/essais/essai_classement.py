#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau de uci_ranking.py : classement UCI individuel hommes élite (saison en cours et précédente)."""
import sys
import time
from collections import Counter

sys.path.insert(0, ".")
import netutil  # noqa: E402
import uci  # noqa: E402
import uci_ranking  # noqa: E402

NB = [0]
_orig = netutil.fetch_text


def _compte(*a, **k):
    NB[0] += 1
    return _orig(*a, **k)


netutil.fetch_text = _compte
t0 = time.time()


def rapport(cl, titre):
    print(f"\n######## {titre}")
    if not cl:
        print("[ECHEC] get_ranking a renvoyé None")
        return
    rows = cl["rows"]
    print(f"nom={cl['name']!r} date={cl['date']} source={cl['source']} saison={cl.get('season')} lignes={len(rows)}")
    print("-- top 20")
    for r in rows[:20]:
        print(f"  {r['rank']:>3} {r['rider']:<28} {r['birth_date']} {r['nationality']} {r['team']} {r['points']} (préc. {r['previous_rank']})")
    fr = [r for r in rows[:100] if r["nationality"] == "FRA"]
    print(f"-- Français du top 100 : {len(fr)}")
    for r in fr:
        print(f"  {r['rank']:>3} {r['name']} ({r['team']}) {r['points']}")
    manq = Counter()
    for r in rows:
        for k in ("rider", "birth_date", "nationality", "team", "points", "rider_id"):
            if r.get(k) in (None, ""):
                manq[k] += 1
    print("champs manquants :", dict(manq) or "aucun")
    rangs = [r["rank"] for r in rows]
    print(f"rangs : min={min(rangs)} max={max(rangs)} uniques={len(set(rangs))} ; ex aequo de points={len(rows) - len({r['points'] for r in rows})}")
    # cohérence de la clé coureur avec uci.rider_ref
    ko = [r for r in rows if r["birth_date"] and uci_ranking.rider_key(r["rider"], r["birth_date"]) != r["rider_id"]]
    print(f"rider_key != rider_id : {len(ko)}")
    print(f"requêtes cumulées : {NB[0]} ; t+{time.time() - t0:.0f}s")


rapport(uci_ranking.get_ranking(), "get_ranking() saison en cours")
rapport(uci_ranking.get_ranking(2026), "get_ranking(2026)")
sid = uci.get_season_id(2027)
print("\nclassements disponibles 2027 :")
for r in uci_ranking.list_rankings(sid):
    print("  ", r)
