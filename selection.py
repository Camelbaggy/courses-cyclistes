#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sélection des courses suivies (SPEC §3).

`select(competitions, fdj_races)` ne renvoie que les courses retenues sans lecture des résultats. Les courses
.1 / .2 disputées hors de France ne sont PAS renvoyées : le collecteur les sonde lui-même (`uci.get_race`) puis
appelle `french_top10(probe)` ; si c'est vrai, la raison est « francais_top10 ».
"""

import datetime
import difflib
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import netutil

CLASSES_WT = {"1.UWT", "2.UWT"}
CLASSES_PRO = {"1.Pro", "2.Pro", "1.HC", "2.HC"}   # 1.HC / 2.HC : ancêtres historiques des Pro (archives)
# Classes historiques 2009-2010 : calendrier historique (grands tours, monuments) et ProTour -> rangées en « WT »
# (le libellé d'origine reste dans `uci_class`).
CLASSES_WT_HISTORIQUES = {"1.CH", "2.CH", "CPE", "AU1", "MNM"}
CHAMPIONNATS_LIBRES = {"CC", "CM", "WC", "OG", "JO"}  # continentaux, monde, olympiques : toujours suivis
CHAMPIONNAT_NATIONAL = "CN"                            # seulement si la course est en France


def categorie_classe(classe: str) -> Optional[str]:
    """Classe UCI -> catégorie « de rang » : WT, Pro, .1, .2 (2.2U, 1.2U, 1.Ncup, 1.2S… inclus), sinon None."""
    c = (classe or "").strip()
    if c in CLASSES_WT or c in CLASSES_WT_HISTORIQUES:
        return "WT"
    if c in CLASSES_PRO:
        return "Pro"
    m = re.match(r"^[12]\.(.+)$", c)
    if not m:
        return None
    suffixe = m.group(1)
    if suffixe.startswith("1"):
        return ".1"
    if suffixe.startswith("2") or suffixe.lower().startswith("ncup"):
        return ".2"
    return None


def _date(txt: Optional[str]) -> Optional[datetime.date]:
    try:
        return datetime.date.fromisoformat(txt) if txt else None
    except ValueError:
        return None


def _noms_proches(a: str, b: str) -> bool:
    na, nb = netutil.normalize(a), netutil.normalize(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    court, long_ = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(court.split()) >= 2 and (f" {court} " in f" {long_} "):
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.8


def match_fdj(comp: Dict[str, Any], fdj_races: Optional[Iterable[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """Manche FDJ United Series correspondant à la compétition : nom normalisé proche + date à ± 1 jour de la fenêtre
    [début, fin] de la course."""
    debut = _date(comp.get("start_date"))
    fin = _date(comp.get("end_date")) or debut
    if debut is None:
        return None
    un = datetime.timedelta(days=1)
    for r in fdj_races or []:
        d = _date(r.get("date"))
        if d is None or not (debut - un <= d <= fin + un):
            continue
        if _noms_proches(comp.get("name", ""), r.get("name", "")):
            return r
    return None


def classer(comp: Dict[str, Any], fdj_races: Optional[Iterable[Dict[str, Any]]] = None) -> Optional[Tuple[str, str]]:
    """(catégorie, raison) si la course est retenue d'emblée, sinon None. Ordre des règles : SPEC §3."""
    classe = (comp.get("uci_class") or "").strip()
    cat = categorie_classe(classe)
    if cat in ("WT", "Pro"):
        return cat, "classe"
    if match_fdj(comp, fdj_races):
        return "FDJ", "fdj"
    if cat in (".1", ".2") and comp.get("country") == "FRA":
        return cat, "france"
    if classe in CHAMPIONNATS_LIBRES or (classe == CHAMPIONNAT_NATIONAL and comp.get("country") == "FRA"):
        return "Champ.", "championnat"
    return None


def select(competitions: Iterable[Dict[str, Any]],
           fdj_races: Optional[Iterable[Dict[str, Any]]] = None) -> List[Tuple[Dict[str, Any], str, str]]:
    fdj = list(fdj_races or [])
    sortie = []
    for comp in competitions:
        r = classer(comp, fdj)
        if r:
            sortie.append((comp, r[0], r[1]))
    return sortie


def candidates_top10(competitions: Iterable[Dict[str, Any]],
                     deja: Optional[Iterable[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Courses .1 / .2 hors de France non retenues par `select` (à sonder puis tester avec `french_top10`)."""
    ids = {c.get("competition_id") for c in (deja or [])}
    return [c for c in competitions if c.get("competition_id") not in ids
            and categorie_classe(c.get("uci_class", "")) in (".1", ".2") and c.get("country") != "FRA"]


def french_top10(race: Optional[Dict[str, Any]]) -> bool:
    """Un coureur français (nationalité FRA) est-il dans les 10 premiers ? Course d'un jour : classement de la course ;
    course par étapes : classement de n'importe quelle étape, ou général final (général de la dernière étape publiée
    si le classement final n'existe pas encore). `race` = résultat de `uci.get_race` (stages / final / riders)."""
    if not race:
        return False
    riders = race.get("riders") or {}

    def dans_top10(lignes: Optional[List[Dict[str, Any]]]) -> bool:
        for row in lignes or []:
            rang = row.get("rank")
            if row.get("status") or not isinstance(rang, int) or rang > 10:
                continue
            if (riders.get(row.get("rider_id")) or {}).get("is_french"):
                return True
        return False

    stages = race.get("stages") or []
    final = race.get("final") or {}
    if race.get("race_type") == "one_day":
        res = final or (stages[0].get("results") if stages else {}) or {}
        return dans_top10(res.get("stage")) or dans_top10(res.get("gc"))
    if any(dans_top10((s.get("results") or {}).get("stage")) for s in stages):
        return True
    if final:
        return dans_top10(final.get("gc"))
    return bool(stages) and dans_top10((stages[-1].get("results") or {}).get("gc"))


def _tests() -> None:
    def C(cls, pays="FRA", nom="Course", d="2026-05-01", f=None, cid=1):
        return {"competition_id": cid, "name": nom, "country": pays, "uci_class": cls, "start_date": d, "end_date": f or d}

    for classe, att in [("1.UWT", "WT"), ("2.UWT", "WT"), ("1.Pro", "Pro"), ("2.Pro", "Pro"), ("1.1", ".1"), ("2.1", ".1"),
                        ("1.2", ".2"), ("2.2", ".2"), ("2.2U", ".2"), ("1.2U", ".2"), ("1.Ncup", ".2"), ("2.Ncup", ".2"),
                        ("CN", None), ("CC", None), ("CM", None), ("", None), ("1.HC", "Pro"), ("2.HC", "Pro"),
                        ("1.CH", "WT"), ("2.CH", "WT"), ("CPE", "WT"), ("AU1", "WT"), ("MNM", "WT")]:
        assert categorie_classe(classe) == att, classe
    assert select([C("1.UWT", "BEL")])[0][1:] == ("WT", "classe")
    assert select([C("2.Pro", "ITA")])[0][1:] == ("Pro", "classe")
    assert select([C("1.HC", "BEL")])[0][1:] == ("Pro", "classe")
    assert select([C("2.CH", "ITA")])[0][1:] == ("WT", "classe")
    assert select([C("MNM", "BEL")])[0][1:] == ("WT", "classe")
    assert select([C("1.2", "FRA")])[0][1:] == (".2", "france")
    assert select([C("2.2U", "FRA")])[0][1:] == (".2", "france")
    assert select([C("1.Ncup", "FRA")])[0][1:] == (".2", "france")
    assert select([C("1.1", "BEL")]) == [] and select([C("2.2", "ESP")]) == []   # sondés par le collecteur
    assert select([C("CN", "FRA")])[0][1:] == ("Champ.", "championnat")
    assert select([C("CN", "ESP")]) == []
    for cl in ("CC", "CM", "WC"):
        assert select([C(cl, "ITA")])[0][1:] == ("Champ.", "championnat")
    assert select([C("CRTP", "JPN")]) == []
    fdj = [{"name": "Tour de Vendée", "date": "2026-10-11"}, {"name": "Cholet-Pays de la Loire", "date": "2026-03-22"}]
    assert select([C("1.Pro", "FRA", "Tour de Vendée", "2026-10-11")], fdj)[0][1:] == ("Pro", "classe")
    assert select([C("1.1", "BEL", "Tour de Vendee", "2026-10-12")], fdj)[0][1:] == ("FDJ", "fdj")
    assert select([C("1.1", "FRA", "Cholet Pays de Loire", "2026-03-22")], fdj)[0][1:] == ("FDJ", "fdj")
    assert select([C("1.1", "BEL", "Tour de Vendée", "2026-10-20")], fdj) == []
    assert select([C("2.1", "FRA", "Autre course", "2026-03-22")], fdj)[0][1:] == (".1", "france")
    assert len(candidates_top10([C("1.1", "BEL", cid=2), C("1.2", "FRA", cid=3), C("CN", "ESP", cid=4)])) == 1

    riders = {"a": {"is_french": True}, "b": {"is_french": False}}
    def R(rid, rang, st=None):
        return {"rank": rang, "status": st, "rider_id": rid}
    un_jour = {"race_type": "one_day", "riders": riders, "stages": [{"results": {"stage": [R("b", 1), R("a", 10)]}}]}
    un_jour["final"] = un_jour["stages"][0]["results"]
    assert french_top10(un_jour)
    un_jour["stages"][0]["results"]["stage"][1]["rank"] = 11
    assert not french_top10(un_jour)
    etapes = {"race_type": "stage_race", "riders": riders, "final": None,
              "stages": [{"results": {"stage": [R("b", 1), R("a", 20)], "gc": [R("b", 1), R("a", 9)]}}]}
    assert french_top10(etapes)                                      # général de la dernière étape, pas de final
    etapes["final"] = {"gc": [R("b", 1), R("a", 15)]}
    assert not french_top10(etapes)
    etapes["stages"].append({"results": {"stage": [R("a", 3)]}})
    assert french_top10(etapes)
    assert not french_top10(None) and not french_top10({"race_type": "one_day", "stages": [], "final": None, "riders": {}})
    print("[OK] selection.py : tests locaux réussis")


if __name__ == "__main__":
    _tests()
