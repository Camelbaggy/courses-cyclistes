#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Classement UCI individuel hommes élite (route) depuis les pages iframe publiques de DataRide.

Endpoints (docs/recherche/classement_uci.md) : `RankingsDiscipline` (liste des classements d'une saison, avec le
`MomentId` le plus récent) puis `ObjectRankings` (lignes du classement, pagination Kendo, 1000 lignes max par page).
Aucune API privée, aucun jeton : mêmes appels que le JavaScript de /iframe/Rankings/10/ et /iframe/RankingDetails/.
Toutes les valeurs viennent de l'UCI (rang, points) ; rien n'est calculé. Aucune fonction ne lève d'exception :
en cas d'échec, `[WARN]` + `None`.

La clé coureur `rider_key` est la même que `uci.rider_ref` : slug du nom UCI « NOM Prénom » + date de naissance
(`nom-prenom-AAAAMMJJ`). Le champ `rider` des lignes est donc le nom UCI brut (« POGAČAR Tadej ») ; `name` donne
la forme lisible (« Tadej Pogačar »). Sans date de naissance, `rider_key` renvoie None : il faut alors rapprocher
par nom normalisé (`netutil.normalize`).
"""

import datetime
from typing import Any, Dict, List, Optional

import netutil
import uci

CATEGORY_MEN_ELITE = uci.CATEGORY_MEN_ELITE
GROUPE_WORLD_RANKING = 1      # « UCI World Ranking » (individuel, toutes courses)
TYPE_INDIVIDUEL = 1           # RankingTypeId : 1 individuel, 2 nations, 3 équipes
PAGE = 1000                   # plafond serveur constaté (take=1000 -> 1000 lignes)


def rider_key(rider: str, birth_date: Optional[str]) -> Optional[str]:
    """Même clé que `uci.rider_ref` : `rider` = nom UCI « NOM Prénom », `birth_date` = 'AAAA-MM-JJ'.
    None si la date de naissance manque (rapprocher alors par nom normalisé)."""
    brut = " ".join(str(rider or "").split())
    if not brut or not birth_date:
        return None
    return netutil.slugify(brut) + "-" + str(birth_date).replace("-", "")


def _saison_courante() -> Optional[int]:
    return uci.season_for(datetime.date.today())


def _normaliser(lg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    brut = " ".join(str(lg.get("DisplayName") or "").split())
    rang = lg.get("Rank")
    if not brut or not isinstance(rang, int) or isinstance(rang, bool):
        return None
    naissance = uci._date_iso(lg.get("BirthDate"))
    rid, _ref = uci.rider_ref(lg)
    return {"rank": rang, "rider": brut, "name": uci.display_name(brut), "birth_date": naissance,
            "nationality": uci._nation(lg.get("NationName")), "team": uci.team_name(lg.get("TeamName")),
            "points": uci._nombre_propre(uci._nombre(lg.get("Points"))), "rider_id": rid,
            "uci_id": lg.get("UciId"), "previous_rank": lg.get("PrecedingRank")}


def list_rankings(season_id: int) -> List[Dict[str, Any]]:
    """Classements hommes élite d'une saison : [{group_id, group_name, id, type_id, name, moment_id}]."""
    filtres = [("RaceTypeId", 0), ("CategoryId", CATEGORY_MEN_ELITE), ("SeasonId", season_id)]
    rep = uci._post("/iframe/RankingsDiscipline/", uci._kendo(100, 0, filtres, None, disciplineId=uci.DISCIPLINE_ROUTE),
                    f"uci_rankings_{season_id}")
    groupes = rep.get("data") if isinstance(rep, dict) else rep
    if not isinstance(groupes, list):
        return []
    sortie = []
    for g in groupes:
        for r in (g.get("Rankings") or []) if isinstance(g, dict) else []:
            sortie.append({"group_id": g.get("GroupId"), "group_name": g.get("GroupName"), "id": r.get("Id"),
                           "type_id": r.get("RankingTypeId"), "name": r.get("RankingName"), "moment_id": r.get("MomentId")})
    return sortie


def get_ranking(season_year: Optional[int] = None, group_id: int = GROUPE_WORLD_RANKING) -> Optional[Dict[str, Any]]:
    """Classement individuel complet (le plus récent de la saison) -> {"name", "date", "source", "rows"} ou None.
    `season_year` : année de saison UCI (2027 = 19 oct. 2026 -> 18 oct. 2027) ; None = saison en cours.
    `group_id` : 1 = UCI World Ranking (défaut) ; 152 = One Day Race ; 153 = Stage Race ; 7 à 11 = circuits continentaux."""
    annee = season_year or _saison_courante()
    if annee is None:
        print("[WARN] UCI classement : saison courante introuvable")
        return None
    sid = uci.get_season_id(annee)
    if sid is None:
        return None
    choix = [r for r in list_rankings(sid)
             if r["group_id"] == group_id and r["type_id"] == TYPE_INDIVIDUEL and r["id"] is not None]
    if not choix:
        print(f"[WARN] UCI classement : groupe {group_id} introuvable pour la saison {annee}")
        return None
    cl = choix[0]
    filtres = [("RaceTypeId", 0), ("CategoryId", CATEGORY_MEN_ELITE), ("SeasonId", sid), ("MomentId", cl["moment_id"])]
    brutes = uci._liste_paginee("/iframe/ObjectRankings/", filtres, None, taille=PAGE, nom=f"uci_ranking_{sid}_{cl['id']}",
                                rankingId=cl["id"], disciplineId=uci.DISCIPLINE_ROUTE, rankingTypeId=TYPE_INDIVIDUEL)
    if not brutes:
        print("[WARN] UCI classement : aucune ligne reçue")
        return None
    lignes, vus = [], set()
    for lg in brutes:
        row = _normaliser(lg)
        if row and (row["rank"], row["rider_id"]) not in vus:  # une page décalée pourrait répéter une ligne
            vus.add((row["rank"], row["rider_id"]))
            lignes.append(row)
    lignes.sort(key=lambda r: r["rank"])
    dates = [uci._date_iso(lg.get("ComputationDate")) for lg in brutes if lg.get("ComputationDate")]
    return {"name": cl["name"] or "UCI World Ranking", "date": max(dates) if dates else None, "source": "uci-dataride",
            "season": annee, "rows": lignes}


if __name__ == "__main__":
    assert rider_key("POGAČAR Tadej", "1998-09-21") == uci.rider_ref({"DisplayName": "POGAČAR Tadej", "BirthDate": "/Date(906328800000)/"})[0]
    assert rider_key("POGAČAR Tadej", None) is None
    print("tests locaux uci_ranking OK")
