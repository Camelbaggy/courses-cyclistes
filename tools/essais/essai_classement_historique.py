#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau de l'historique du classement UCI (E1c) : GetRankingMoments, choix des instantanés, lecture d'un moment.

Pour 2027 (courante) puis 2018 (WorldTour Ranking) : forme brute des moments, choix (fin de mois + après chaque course WT), un
instantané complet (nombre de lignes, date de calcul comparée à celle du moment), taille compactée. Quelques dizaines de requêtes."""
import json
import sys
import time

sys.path.insert(0, ".")
import collector  # noqa: E402
import netutil  # noqa: E402
import uci  # noqa: E402
import uci_ranking  # noqa: E402

netutil.HOST_DELAYS["dataride.uci.org"] = 2.0
t0 = time.time()
for annee in (2027, 2018):
    print(f"\n######## saison {annee}")
    ctx = uci_ranking.contexte_classement(annee)
    if not ctx:
        print("[ECHEC] pas de classement individuel")
        continue
    print("contexte :", ctx)
    brut = netutil.fetch_json(f"{uci.BASE}/iframe/GetRankingMoments/?disciplineId={uci.DISCIPLINE_ROUTE}"
                              f"&disciplineSeasonId={ctx['season_id']}&rankingId={ctx['ranking_id']}", raw_name="essai_mom")
    print("moments bruts :", len(brut) if isinstance(brut, list) else brut, "; 2 premiers :", json.dumps((brut or [])[:2], ensure_ascii=False)[:300])
    moments = uci_ranking.list_moments(ctx["season_id"], ctx["ranking_id"])
    print(f"{len(moments)} moments datés, du {moments[0]['date'] if moments else '?'} au {moments[-1]['date'] if moments else '?'}")
    courses, source = collector.courses_wt_saison(annee)
    wt = [c for c in courses if collector.selection.categorie_classe(c.get("uci_class") or "") == "WT"]
    choix = uci_ranking.choisir_instantanes(moments, courses, None if annee < 2027 else collector.dt.date.today())
    print(f"{len(wt)} courses WT ({source}) -> {len(choix)} instantanés")
    for c in choix[:12]:
        print("  ", c["date"], c["moment_id"], c["raisons"])
    if choix:
        c = choix[len(choix) // 2]
        rk = uci_ranking.get_ranking_moment(annee, c["moment_id"], ctx["group_id"])
        if rk:
            lg = uci_ranking.lignes_instantane(rk["rows"])
            print(f"instantané {c['date']} : {len(rk['rows'])} lignes lues, {len(lg)} gardées, date de calcul {rk['date']} (moment {c['date']}), "
                  f"{len(json.dumps(lg, separators=(',', ':')))} octets compactés ; sans rider_id : {sum(1 for x in lg if not x[1])}")
            print("  top 3 :", lg[:3])
print(f"\nterminé en {time.time() - t0:.0f} s")
