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

import bisect
import datetime
import re
from typing import Any, Dict, List, Optional, Tuple

import netutil
import selection
import uci

CATEGORY_MEN_ELITE = uci.CATEGORY_MEN_ELITE
GROUPE_WORLD_RANKING = 1      # « UCI World Ranking » (individuel, toutes courses)
TYPE_INDIVIDUEL = 1           # RankingTypeId : 1 individuel, 2 nations, 3 équipes
GROUPE_WORLDTOUR = 3          # « WorldTour Ranking » (saisons anciennes, sans World Ranking)
PAGE = 1000                   # plafond serveur constaté (take=1000 -> 1000 lignes)
TOP_INSTANTANE = 500          # instantanés historiques : 500 premières lignes + tous les Français au-delà


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
            "uci_id": lg.get("UciId"), "previous_rank": lg.get("PrecedingRank"),
            # TeamCode : code UCI de l'équipe À CETTE SAISON (change avec le sponsor, peut être réattribué : jamais une identité seule)
            "team_code": (str(lg.get("TeamCode") or "").strip() or None)}


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


# --------------------------------------------------------------------------------------------------
# Historique : instantanés du classement (E1c, docs/PLAN_ENCYCLOPEDIE.md §8 point 5)
# --------------------------------------------------------------------------------------------------

_CONTEXTES: Dict[Tuple[int, Tuple[int, ...]], Optional[Dict[str, Any]]] = {}   # mémoire d'un passage : (saison, groupes) -> contexte


def contexte_classement(season_year: int, groupes: Tuple[int, ...] = (GROUPE_WORLD_RANKING, GROUPE_WORLDTOUR)
                        ) -> Optional[Dict[str, Any]]:
    """Classement individuel d'une saison, premier groupe disponible (World Ranking, à défaut « WorldTour Ranking » des saisons
    anciennes) -> {"season", "season_id", "group_id", "ranking_id", "name"} ou None. Mémorisé pour la durée du processus (3 requêtes au plus)."""
    cle = (season_year, tuple(groupes))
    if cle not in _CONTEXTES:
        ctx = None
        sid = uci.get_season_id(season_year)
        if sid is not None:
            catalogue = list_rankings(sid)
            for g in groupes:
                choix = [r for r in catalogue if r["group_id"] == g and r["type_id"] == TYPE_INDIVIDUEL and r["id"] is not None]
                if choix:
                    ctx = {"season": season_year, "season_id": sid, "group_id": g, "ranking_id": choix[0]["id"],
                           "name": choix[0]["name"] or "UCI World Ranking"}
                    break
            if ctx is None:
                print(f"[WARN] UCI classement : aucun classement individuel (groupes {list(groupes)}) pour la saison {season_year}")
        _CONTEXTES[cle] = ctx
    return _CONTEXTES[cle]


def _date_du_moment(m: Dict[str, Any]) -> Optional[str]:
    """Date ISO d'une entrée de GetRankingMoments : « 03/11/2026 » (jj/mm/aaaa), « /Date(…)/ » ou ISO, dans n'importe quel champ."""
    for v in m.values():
        txt = str(v)
        trouve = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", txt)
        if trouve:
            try:
                return datetime.date(int(trouve.group(3)), int(trouve.group(2)), int(trouve.group(1))).isoformat()
            except ValueError:
                continue
        if "/Date(" in txt:
            d = uci._date_iso(txt)
            if d:
                return d
        trouve = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", txt)
        if trouve:
            return trouve.group(1)
    return None


def list_moments(season_id: int, ranking_id: int) -> List[Dict[str, Any]]:
    """Dates de calcul d'un classement : [{moment_id, date}] triées par date croissante (GetRankingMoments). L'entrée « Most Recent
    Ranking » (Id 0) est ignorée : sa date figure déjà en tant que moment ordinaire. Liste vide si la réponse est inexploitable."""
    rep = netutil.fetch_json(f"{uci.BASE}/iframe/GetRankingMoments/?disciplineId={uci.DISCIPLINE_ROUTE}"
                             f"&disciplineSeasonId={season_id}&rankingId={ranking_id}", retries=2,
                             raw_name=f"uci_moments_{season_id}_{ranking_id}")
    if isinstance(rep, dict):
        rep = rep.get("data")
    if not isinstance(rep, list):
        print(f"[WARN] UCI classement : moments indisponibles (saison {season_id}, classement {ranking_id})")
        return []
    sortie: Dict[Any, Dict[str, Any]] = {}
    for m in rep:
        if not isinstance(m, dict):
            continue
        mid = m.get("MomentId") if m.get("MomentId") is not None else m.get("Id")
        if isinstance(mid, bool) or not isinstance(mid, int) or mid == 0:
            continue
        if "recent" in " ".join(str(v) for v in m.values()).lower():
            continue
        date = _date_du_moment(m)
        if date and mid not in sortie:
            sortie[mid] = {"moment_id": mid, "date": date}
    return sorted(sortie.values(), key=lambda x: (x["date"], x["moment_id"]))


def _normaliser_lignes(brutes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lignes, vus = [], set()
    for lg in brutes:
        row = _normaliser(lg)
        if row and (row["rank"], row["rider_id"]) not in vus:
            vus.add((row["rank"], row["rider_id"]))
            lignes.append(row)
    lignes.sort(key=lambda r: r["rank"])
    return lignes


def get_ranking_moment(season_year: int, moment_id: int, group_id: int = GROUPE_WORLD_RANKING,
                       taille: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Classement individuel à un moment donné -> {"name", "date", "moment_id", "group_id", "rows"} ou None. Mêmes lignes que
    `get_ranking` (`team_code` compris). `taille` : ne garde que les `taille` premières lignes et ne lit que les pages nécessaires
    (pagination Kendo, 1000 par page) ; None = classement complet."""
    ctx = contexte_classement(season_year, (group_id,))
    if ctx is None:
        return None
    filtres = [("RaceTypeId", 0), ("CategoryId", CATEGORY_MEN_ELITE), ("SeasonId", ctx["season_id"]), ("MomentId", moment_id)]
    extra = {"rankingId": ctx["ranking_id"], "disciplineId": uci.DISCIPLINE_ROUTE, "rankingTypeId": TYPE_INDIVIDUEL}
    nom = f"uci_ranking_{ctx['season_id']}_{ctx['ranking_id']}_{moment_id}"
    if taille is None:
        brutes = uci._liste_paginee("/iframe/ObjectRankings/", filtres, None, taille=PAGE, nom=nom, **extra)
    else:
        brutes, total = [], None
        while len(brutes) < taille:
            rep = uci._post("/iframe/ObjectRankings/", uci._kendo(PAGE, len(brutes), filtres, None, **extra), f"{nom}_{len(brutes)}")
            data = rep.get("data") if isinstance(rep, dict) else None
            if not isinstance(data, list) or not data:
                break
            brutes += [d for d in data if isinstance(d, dict)]
            total = rep.get("total", total)
            if isinstance(total, int) and len(brutes) >= total:
                break
        brutes = brutes or None
    if not brutes:
        print(f"[WARN] UCI classement : aucune ligne pour le moment {moment_id} (saison {season_year})")
        return None
    lignes = _normaliser_lignes(brutes)
    if taille is not None:
        lignes = lignes[:taille]
    dates = [uci._date_iso(lg.get("ComputationDate")) for lg in brutes if lg.get("ComputationDate")]
    return {"name": ctx["name"], "date": max(dates) if dates else None, "moment_id": moment_id,
            "group_id": ctx["group_id"], "rows": lignes}


def choisir_instantanes(moments: List[Dict[str, Any]], courses: List[Dict[str, Any]],
                        aujourdhui: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
    """Fonction pure : instantanés à conserver pour une saison -> [{moment_id, date, raisons}] triés par date.
    - le DERNIER moment de chaque mois civil (un mois n'est « fini » que s'il est antérieur au mois de `aujourdhui` ; None = tous finis,
      saison close) -> raison « fin de mois » ;
    - le PREMIER moment STRICTEMENT postérieur à la date de fin de chaque course WorldTour (`uci_class` rangée WT par
      `selection.categorie_classe`, `end_date` à défaut `start_date` ; dernière étape pour une course par étapes) -> « après <nom> » :
      course finie un dimanche -> moment du mardi suivant ; finie un mardi -> mardi d'après (jamais le même jour). Pas de moment
      postérieur : pas d'instantané pour cette course.
    Un moment retenu pour plusieurs raisons n'apparaît qu'une fois, avec toutes ses raisons (fins de mois d'abord, puis courses par date)."""
    ms = sorted((m for m in moments if m.get("date") and m.get("moment_id") is not None), key=lambda m: (m["date"], m["moment_id"]))
    dates = [m["date"] for m in ms]
    raisons: Dict[Any, List[str]] = {}

    def ajouter(m: Dict[str, Any], raison: str) -> None:
        liste = raisons.setdefault(m["moment_id"], [])
        if raison not in liste:
            liste.append(raison)

    dernier_du_mois: Dict[str, Dict[str, Any]] = {}
    for m in ms:
        dernier_du_mois[m["date"][:7]] = m          # croissant : le dernier écrase
    limite = aujourdhui.isoformat()[:7] if aujourdhui else None
    for mois in sorted(dernier_du_mois):
        if limite is None or mois < limite:
            ajouter(dernier_du_mois[mois], "fin de mois")
    wt = [c for c in courses if selection.categorie_classe(str(c.get("uci_class") or "")) == "WT"]
    wt.sort(key=lambda c: (c.get("end_date") or c.get("start_date") or "", c.get("name") or ""))
    for c in wt:
        fin = c.get("end_date") or c.get("start_date")
        if not fin or not c.get("name"):
            continue
        i = bisect.bisect_right(dates, fin)         # premier moment strictement après la fin
        if i < len(ms):
            ajouter(ms[i], f"après {c['name']}")
    index = {m["moment_id"]: m for m in ms}
    sortie = [{"moment_id": mid, "date": index[mid]["date"], "raisons": r} for mid, r in raisons.items()]
    # dédoublonnage par date (deux moments le même jour : on garde le plus grand identifiant, le plus récent)
    par_date: Dict[str, Dict[str, Any]] = {}
    for x in sorted(sortie, key=lambda x: (x["date"], x["moment_id"])):
        prec = par_date.get(x["date"])
        par_date[x["date"]] = x if prec is None else {**x, "raisons": prec["raisons"] + [r for r in x["raisons"] if r not in prec["raisons"]]}
    return sorted(par_date.values(), key=lambda x: x["date"])


def lignes_instantane(rows: List[Dict[str, Any]], top: int = TOP_INSTANTANE) -> List[List[Any]]:
    """Lignes compactes d'un instantané : [[rang, rider_id, points, team_code]] pour les `top` premières lignes (ordre du classement)
    et tous les Français (nationalité FRA) au-delà. `rider_id` = `rider_key` (nom UCI + date de naissance), None sans date de naissance."""
    sortie = []
    for i, r in enumerate(rows):
        if i >= top and r.get("nationality") != "FRA":
            continue
        sortie.append([r["rank"], rider_key(r.get("rider"), r.get("birth_date")), r.get("points"), r.get("team_code")])
    return sortie


def _tests_historique() -> None:
    """Instantanés : choix (fonction pure), moments, lecture d'un moment limitée à `taille` (réponses simulées, sans réseau)."""
    mardis = [(datetime.date(2026, 10, 27) + datetime.timedelta(days=7 * k)).isoformat() for k in range(14)]   # 27/10/2026 -> 26/01/2027
    moments = [{"moment_id": 1000 + k, "date": d} for k, d in enumerate(mardis)]
    courses = [
        {"name": "Course dimanche", "uci_class": "1.UWT", "start_date": "2026-11-15", "end_date": "2026-11-15"},   # dimanche -> mardi 17/11
        {"name": "Course mardi", "uci_class": "1.UWT", "start_date": "2026-11-17", "end_date": "2026-11-17"},       # mardi -> mardi 24/11 (pas le même jour)
        {"name": "Tour par étapes", "uci_class": "2.UWT", "start_date": "2026-11-18", "end_date": "2026-11-22"},    # fin dimanche 22 -> mardi 24/11 (= fin de mois)
        {"name": "Classique Pro", "uci_class": "1.Pro", "start_date": "2026-11-29", "end_date": "2026-11-29"},      # pas WorldTour : ignorée
        {"name": "Course historique", "uci_class": "1.HC", "start_date": "2026-12-05", "end_date": "2026-12-05"},   # HC : Pro, ignorée
        {"name": "Course sans date", "uci_class": "1.UWT", "start_date": None, "end_date": None},
        {"name": "Course finale", "uci_class": "2.UWT", "start_date": "2027-01-24", "end_date": "2027-01-27"},      # aucun moment strictement après
        {"name": "Course ancienne WT", "uci_class": "2.CH", "start_date": "2026-12-12", "end_date": "2026-12-13"},  # classe historique rangée WT
    ]
    ch = choisir_instantanes(moments, courses)
    par_date = {c["date"]: c["raisons"] for c in ch}
    assert par_date == {"2026-10-27": ["fin de mois"], "2026-11-17": ["après Course dimanche"],
                        "2026-11-24": ["fin de mois", "après Course mardi", "après Tour par étapes"],
                        "2026-12-15": ["après Course ancienne WT"], "2026-12-29": ["fin de mois"],
                        "2027-01-26": ["fin de mois"]}, par_date
    assert [c["date"] for c in ch] == sorted(par_date) and ch[0]["moment_id"] == 1000
    # saison en cours au 10/12/2026 : décembre et janvier ne sont pas finis
    en_cours = choisir_instantanes(moments, courses, datetime.date(2026, 12, 10))
    assert [c["date"] for c in en_cours] == ["2026-10-27", "2026-11-17", "2026-11-24", "2026-12-15"], en_cours
    assert en_cours[-1]["raisons"] == ["après Course ancienne WT"]
    assert choisir_instantanes([], courses) == [] and choisir_instantanes(moments, [])[0]["raisons"] == ["fin de mois"]
    # un moment sans date ou sans identifiant est ignoré ; entrée non triée acceptée
    assert choisir_instantanes([{"moment_id": 2, "date": None}, {"moment_id": 4, "date": "2020-03-31"}, {"moment_id": 3, "date": "2020-03-03"}], []) == \
        [{"moment_id": 4, "date": "2020-03-31", "raisons": ["fin de mois"]}]

    # list_moments : « Most Recent Ranking » (Id 0) ignoré, dates jj/mm/aaaa ou /Date()/, doublons écartés
    sauve = netutil.fetch_json
    try:
        netutil.fetch_json = lambda url, **k: [{"Id": 0, "Name": "Most Recent Ranking"}, {"Id": 206851, "Name": "03/11/2026"},
                                              {"Id": 205000, "Name": "27/10/2026"}, {"Id": 205000, "Name": "27/10/2026"},
                                              {"MomentId": 204000, "Name": "x", "Date": "/Date(1792540800000)/"}, {"Id": 7, "Name": "?"}, "x"]
        assert list_moments(477, 1) == [{"moment_id": 204000, "date": "2026-10-21"}, {"moment_id": 205000, "date": "2026-10-27"},
                                        {"moment_id": 206851, "date": "2026-11-03"}]
        netutil.fetch_json = lambda url, **k: None
        assert list_moments(477, 1) == []
    finally:
        netutil.fetch_json = sauve

    # lignes compactes : top N + Français au-delà ; rider_id par rider_key, None sans date de naissance
    rows = [{"rank": k + 1, "rider": f"NOM{k} Pre", "birth_date": "1990-01-02" if k != 1 else None, "points": 100 - k, "team_code": "AAA",
             "nationality": "FRA" if k in (1, 4) else "BEL"} for k in range(6)]
    lg = lignes_instantane(rows, top=3)
    assert [x[0] for x in lg] == [1, 2, 3, 5] and lg[0] == [1, "nom0-pre-19900102", 100, "AAA"] and lg[1][1] is None, lg

    # get_ranking_moment : pagination limitée à `taille`, filtres Kendo avec MomentId
    appels: List[Any] = []

    def fausse_page(chemin, champs, nom=""):
        d = dict(champs)
        appels.append((chemin, d["skip"], d["take"], d.get("filter[filters][3][value]")))
        base = int(d["skip"])
        data = [{"DisplayName": f"NOM{base + i} Pre", "Rank": base + i + 1, "BirthDate": "/Date(906328800000)/", "NationName": "FRA ",
                 "Points": 10.5, "TeamCode": "AAA", "ComputationDate": "/Date(1793667608610)/"} for i in range(PAGE)]
        return {"data": data, "total": 2500}

    sv = (uci.get_season_id, list_rankings, uci._post)
    _CONTEXTES.clear()
    try:
        uci.get_season_id = lambda annee: 477
        globals()["list_rankings"] = lambda sid: [{"group_id": 3, "group_name": "WT", "id": 7, "type_id": 1, "name": "WorldTour Ranking", "moment_id": 1},
                                                  {"group_id": 1, "group_name": "W", "id": 1, "type_id": 2, "name": "nations", "moment_id": 1}]
        uci._post = fausse_page
        assert contexte_classement(2027, (1,)) is None                           # le groupe 1 n'existe qu'en nations
        ctx = contexte_classement(2027)                                           # repli sur le groupe 3
        assert ctx["group_id"] == 3 and ctx["ranking_id"] == 7 and ctx["name"] == "WorldTour Ranking"
        r = get_ranking_moment(2027, 555, 3, taille=1200)
        assert [a[1] for a in appels] == [0, 1000] and all(a[3] == 555 for a in appels), appels   # 2 pages pour 1200 lignes
        assert len(r["rows"]) == 1200 and r["rows"][0]["team_code"] == "AAA" and r["date"] == "2026-11-03" and r["moment_id"] == 555
        assert r["rows"][0]["rider_id"] == rider_key("NOM0 Pre", "1998-09-21")
        appels.clear()
        assert len(get_ranking_moment(2027, 555, 3, taille=10)["rows"]) == 10 and len(appels) == 1
        appels.clear()
        assert len(get_ranking_moment(2027, 555, 3)["rows"]) == 3000 and len(appels) == 3   # complet : 3 pages (la fausse page ignore `total`)
    finally:
        uci.get_season_id, uci._post = sv[0], sv[2]
        globals()["list_rankings"] = sv[1]
        _CONTEXTES.clear()


if __name__ == "__main__":
    assert rider_key("POGAČAR Tadej", "1998-09-21") == uci.rider_ref({"DisplayName": "POGAČAR Tadej", "BirthDate": "/Date(906328800000)/"})[0]
    assert rider_key("POGAČAR Tadej", None) is None
    lg = {"DisplayName": "POGAČAR Tadej", "Rank": 1, "TeamName": "UAE Team Emirates", "TeamCode": " UEX "}
    assert _normaliser(lg)["team_code"] == "UEX" and _normaliser(dict(lg, TeamCode=""))["team_code"] is None and "team_code" in _normaliser(dict(lg, TeamCode=None))
    _tests_historique()
    print("tests locaux uci_ranking OK")

