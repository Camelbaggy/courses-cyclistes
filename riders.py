#!/usr/bin/env python3
"""Fiches coureurs : palmarès de la saison dérivé des fichiers de course + classement UCI individuel.

`build_riders(races, ranking)` produit le contenu de data/riders.json. Tout est calculé de façon déterministe à
partir des classements publiés dans `data/races/*.json` ; rien n'est inventé (champ inconnu = None).

Définitions (documentées aussi dans l'interface) :
- `results` : uniquement les 10 premières places d'une étape / d'une course d'un jour, et des classements FINAUX
  (général, points, montagne, jeunes) d'une course par étapes. Classement final = `race["final"]` ; à défaut, pour
  une course terminée, classement de la dernière étape. Un général provisoire (course en cours) n'est pas un
  résultat final : il n'est pas repris.
- `id` n'est pas répété dans la fiche (c'est la clé de `riders`). Une valeur absente vaut null (champs) / false (is_french) / 0 (stats) : le fichier reste compact.
- `wins` / `podiums` / `top10` : rangs 1 / 1-3 / 1-10 aux classements d'étape ou de course d'un jour
  (les classements finaux ne sont pas comptés ici) ; `gc_wins` : généraux finaux gagnés.
- `race_days` : étapes / courses d'un jour où le coureur figure (classé, DNF, OTL ou DSQ ; pas DNS) ;
  `races` : courses distinctes correspondantes ; `dnf` : abandons (DNF, OTL, DSQ).
- Rapprochement avec le classement UCI : identifiant identique (nom + date de naissance) ; à défaut, nom
  normalisé (indépendant de l'ordre prénom/nom) + nationalité, seulement si l'appariement est unique.
"""
import argparse
import datetime
import glob
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import netutil

FINAUX = (("gc", "Général final"), ("points", "Classement par points final"),
          ("mountain", "Classement de la montagne final"), ("youth", "Classement des jeunes final"))
STATUTS_ABANDON = ("DNF", "OTL", "DSQ")
STATUTS_ABSENT = ("DNS", "DNQ")
TAILLE_MAX = 2_000_000          # octets : au-delà, on allège (voir _alleger)


def _age(naissance: Optional[str], ref: datetime.date) -> Optional[int]:
    try:
        n = datetime.date.fromisoformat(naissance or "")
    except ValueError:
        return None
    a = ref.year - n.year - ((ref.month, ref.day) < (n.month, n.day))
    return a if 0 < a < 100 else None


def _nom_cle(nom: str) -> Tuple[str, ...]:
    """Nom normalisé, jetons triés : « NOM Prénom » et « Prénom Nom » donnent la même clé."""
    return tuple(sorted(netutil.normalize(nom).split()))


def _etapes(race: Dict[str, Any]) -> List[Dict[str, Any]]:
    return sorted(race.get("stages") or [], key=lambda s: -1 if s.get("number") is None else s["number"])


def _classement_course(race: Dict[str, Any], etape: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Classement d'étape ; pour une course d'un jour, repli sur le classement final (comme la page)."""
    rows = (etape.get("results") or {}).get("stage") or []
    if not rows and race.get("race_type") != "stage_race":
        rows = (race.get("final") or {}).get("stage") or []
    return rows


def _resultat(race: Dict[str, Any], date: str, numero: Optional[int], label: str, classification: str,
              rank: int) -> Dict[str, Any]:
    # race_name / uci_class / category : dans la table "races" du fichier (une seule fois par course)
    return {"date": date, "race_id": race.get("id"), "stage_number": numero, "label": label,
            "classification": classification, "rank": rank}


def _classements_finaux(race: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    if race.get("race_type") != "stage_race":
        return {}
    fin = race.get("final")
    if fin and any(fin.get(k) for k, _ in FINAUX):
        return fin
    if race.get("status") == "finished" and race.get("stages"):
        return _etapes(race)[-1].get("results") or {}
    return {}


def _agreger(races: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    def fiche(rid: str, ref: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        f = out.get(rid)
        if f is None:
            f = out[rid] = {"id": rid, "name": None, "nationality": None, "flag": None, "is_french": False,
                            "team": None, "birth_date": None,
                            "stats": {"wins": 0, "podiums": 0, "top10": 0, "race_days": 0, "races": 0,
                                      "gc_wins": 0, "dnf": 0},
                            "results": [], "_courses": set()}
        if ref:   # les courses arrivent par date croissante : la plus récente l'emporte, sans effacer par du vide
            for k in ("name", "nationality", "flag", "team", "birth_date"):
                if ref.get(k):
                    f[k] = ref[k]
            f["is_french"] = bool(ref.get("is_french")) or f["is_french"]
        return f

    for race in sorted(races, key=lambda r: (r.get("start_date") or "", r.get("id") or "")):
        refs = race.get("riders") or {}
        # présence dans n'importe quel classement : la fiche existe (nom cliquable)
        for cl in [race.get("final") or {}] + [(s.get("results") or {}) for s in race.get("stages") or []]:
            for lignes in cl.values():
                for r in lignes:
                    if r.get("rider_id") in refs:
                        fiche(r["rider_id"], refs[r["rider_id"]])
        for s in _etapes(race):
            numero = s.get("number")
            label = "Course" if numero is None else (s.get("name") or f"Étape {numero}")
            for r in _classement_course(race, s):
                rid = r.get("rider_id")
                if not rid:
                    continue
                f = fiche(rid, refs.get(rid))
                st, rk = r.get("status"), r.get("rank")
                if st in STATUTS_ABSENT:
                    continue
                f["stats"]["race_days"] += 1
                f["_courses"].add(race.get("id"))
                if st in STATUTS_ABANDON:
                    f["stats"]["dnf"] += 1
                if st is None and rk is not None and rk <= 10:
                    f["stats"]["top10"] += 1
                    f["stats"]["podiums"] += rk <= 3
                    f["stats"]["wins"] += rk == 1
                    f["results"].append(_resultat(race, s.get("date") or race.get("start_date") or "",
                                                  numero, label, "stage", rk))
        fin = _classements_finaux(race)
        date_fin = (_etapes(race)[-1].get("date") if race.get("stages") else None) or race.get("end_date") or ""
        for cle, label in FINAUX:
            for r in fin.get(cle) or []:
                rk, rid = r.get("rank"), r.get("rider_id")
                if rid and rk is not None and rk <= 10 and r.get("status") is None:
                    f = fiche(rid, refs.get(rid))
                    if cle == "gc" and rk == 1:
                        f["stats"]["gc_wins"] += 1
                    f["results"].append(_resultat(race, date_fin, None, label, cle, rk))
    for f in out.values():
        f["stats"]["races"] = len(f.pop("_courses"))
        # plus récent d'abord ; à date égale, classements finaux avant l'étape, étapes décroissantes
        f["results"].sort(key=lambda x: (x["date"], x["stage_number"] is None, x["stage_number"] or 0,
                                         x["classification"] == "gc"), reverse=True)
    return out


def _rapprocher(riders: Dict[str, Dict[str, Any]], ranking: Dict[str, Any]) -> int:
    """Renseigne uci_rank / uci_points. Retourne le nombre de coureurs appariés."""
    for f in riders.values():
        f["uci_rank"] = None
        f["uci_points"] = None
    rows = [r for r in (ranking.get("rows") or []) if r.get("rider") and r.get("rank") is not None]
    if not rows:
        return 0
    par_nom: Dict[Tuple, List[str]] = {}
    for rid, f in riders.items():
        par_nom.setdefault((_nom_cle(f["name"] or ""), f["nationality"]), []).append(rid)
    rows_par_nom: Dict[Tuple, int] = {}
    cles = []
    for r in rows:
        k = (_nom_cle(r["rider"]), r.get("nationality"))
        cles.append(k)
        rows_par_nom[k] = rows_par_nom.get(k, 0) + 1
    pris = set()
    n = 0
    for r, k in zip(rows, cles):
        naiss = r.get("birth_date")
        rid = None
        if naiss:
            cand = netutil.slugify(r["rider"]) + "-" + naiss.replace("-", "")
            if cand in riders:
                rid = cand
        if rid is None:
            # repli par nom : appariement unique des deux côtés, et dates de naissance jamais contradictoires
            c = par_nom.get(k, [])
            if len(c) == 1 and rows_par_nom[k] == 1:
                f = riders[c[0]]
                if not (naiss and f["birth_date"] and naiss != f["birth_date"]):
                    rid = c[0]
        if rid is None or rid in pris:
            continue
        pris.add(rid)
        riders[rid]["uci_rank"] = int(r["rank"])
        riders[rid]["uci_points"] = r.get("points")
        n += 1
    return n


def _alleger(riders: Dict[str, Dict[str, Any]]) -> None:
    """Dernier recours si le fichier dépasse la taille visée : palmarès détaillé conservé seulement pour
    les Français et les coureurs ayant un résultat sur le podium ; les stats restent pour tous."""
    for f in riders.values():
        if not f.get("is_french") and not any(x["rank"] <= 3 for x in f.get("results", [])):
            f["results"] = []


def _meilleurs(races: List[Dict[str, Any]], fiches: Dict[str, Dict[str, Any]], n: int = 3) -> None:
    """Pour chaque Français : ses `n` résultats de la saison ayant rapporté le plus de points UCI (champ `best`,
    même forme que `results` + `uci_points`). Points tels que publiés par l'UCI (PointPcR), sans recalcul."""
    cands: Dict[str, List[Dict[str, Any]]] = {}

    def ajouter(rid: Optional[str], r: Dict[str, Any], res: Dict[str, Any]) -> None:
        pts = r.get("uci_points")
        if rid in fiches and fiches[rid].get("is_french") and pts and r.get("status") is None and r.get("rank"):
            cands.setdefault(rid, []).append(dict(res, uci_points=pts))

    for race in races:
        for s in _etapes(race):
            numero = s.get("number")
            label = "Course" if numero is None else (s.get("name") or f"Étape {numero}")
            date = s.get("date") or race.get("start_date") or ""
            for r in _classement_course(race, s):
                ajouter(r.get("rider_id"), r, _resultat(race, date, numero, label, "stage", r.get("rank")))
        fin = _classements_finaux(race)
        date_fin = (_etapes(race)[-1].get("date") if race.get("stages") else None) or race.get("end_date") or ""
        for cle, label in FINAUX:
            for r in fin.get(cle) or []:
                ajouter(r.get("rider_id"), r, _resultat(race, date_fin, None, label, cle, r.get("rank")))
    for rid, lst in cands.items():
        lst.sort(key=lambda x: (-x["uci_points"], x["rank"], x["date"]))
        fiches[rid]["best"] = lst[:n]


def build_riders(races: List[Dict[str, Any]], ranking: Optional[Dict[str, Any]],
                 now: Optional[datetime.datetime] = None, season: Optional[int] = None) -> Dict[str, Any]:
    """`season` : saison UCI visée ; si fournie, seules les courses de cette saison sont prises en compte
    (les courses sans champ `season` sont conservées). Sinon, saison la plus représentée."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if season is not None:
        races = [r for r in races if r.get("season") in (None, season)]
    riders = _agreger(races)
    _meilleurs(races, riders)
    for f in riders.values():
        f["age"] = _age(f["birth_date"], now.date())
    appaires = _rapprocher(riders, ranking or {})
    courses = {r["id"]: {"name": r.get("name"), "uci_class": r.get("uci_class"), "category": r.get("category")}
               for r in races if r.get("id")}
    for f in riders.values():     # compacité : une valeur absente / fausse vaut null / false
        for k in [k for k, v in f.items() if v is None or v is False]:
            del f[k]
        f.pop("id", None)         # identique à la clé du dictionnaire
        if not f["results"]:
            del f["results"]
        f["stats"] = {k: v for k, v in f["stats"].items() if v}      # statistique absente = 0
    saisons = [r["season"] for r in races if r.get("season")]
    out = {"season": season if season is not None else (max(set(saisons), key=saisons.count) if saisons else now.year),   # saison la plus représentée
           "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "ranking": ({"name": ranking.get("name"), "date": ranking.get("date"), "source": ranking.get("source")}
                       if ranking and ranking.get("rows") else None),
           "races": courses, "riders": riders}
    if ranking and ranking.get("rows"):
        print(f"[RIDERS] classement UCI : {appaires}/{len(ranking['rows'])} lignes appariées")
    if len(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode()) > TAILLE_MAX:
        _alleger(riders)
        print("[RIDERS] fichier > 2 Mo : palmarès détaillé limité aux Français et aux coureurs ayant un podium")
    return out


def write_riders(chemin: str, races: List[Dict[str, Any]], ranking: Optional[Dict[str, Any]],
                 season: Optional[int] = None) -> Dict[str, Any]:
    """Écrit la fiche de la saison dans `chemin` (nom choisi par l'appelant, ex. data/riders-2026.json)."""
    d = build_riders(races, ranking, season=season)
    os.makedirs(os.path.dirname(os.path.abspath(chemin)), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
    return d


def charger_courses(dossier: str) -> List[Dict[str, Any]]:
    out = []
    for p in sorted(glob.glob(os.path.join(dossier, "*.json"))):
        try:
            with open(p, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (OSError, ValueError) as e:
            print(f"[WARN] {p} illisible : {e}")
    return out


def _fiche_texte(f: Dict[str, Any], noms: Dict[str, Any]) -> str:
    s = {k: f["stats"].get(k, 0) for k in ("wins", "podiums", "top10", "race_days", "races", "gc_wins", "dnf")}
    f.setdefault("results", [])
    lignes = [f"{f['name']} ({f['nationality']}, {f['team']}, {f.get('age')} ans) · UCI {f.get('uci_rank')} / {f.get('uci_points')} pts",
              f"  victoires {s['wins']} · podiums {s['podiums']} · top10 {s['top10']} · jours {s['race_days']} · "
              f"courses {s['races']} · généraux {s['gc_wins']} · abandons {s['dnf']}"]
    for x in f["results"][:12]:
        lignes.append(f"  {x['date']} {x['rank']:>2}e {noms[x['race_id']]['name']} · {x['label']}")
    if len(f["results"]) > 12:
        lignes.append(f"  … {len(f['results']) - 12} autres résultats")
    return "\n".join(lignes)


def _test() -> None:
    """Tests locaux sans réseau."""
    def ligne(rid, rank, status=None):
        return {"rank": rank, "status": status, "bib": None, "rider_id": rid, "time_s": None, "gap_s": None,
                "points": None, "bonus_s": None, "penalty_s": None, "uci_points": None}

    def ref(rid, nom, nat, team, naiss):
        return {"id": rid, "name": nom, "nationality": nat, "flag": "fr", "is_french": nat == "FRA", "team": team,
                "birth_date": naiss}
    a, b, c = "dupont-jean-20000101", "durand-luc", "martin-paul-19990505"
    course = {"id": "c1", "name": "Tour Test", "uci_class": "2.1", "category": ".1", "race_type": "stage_race",
              "status": "finished", "start_date": "2026-03-01", "end_date": "2026-03-02", "season": 2026,
              "riders": {a: ref(a, "Jean Dupont", "FRA", "Équipe A", "2000-01-01"),
                         b: ref(b, "Luc Durand", "BEL", "Équipe B", None),
                         c: ref(c, "Paul Martin", "FRA", "Équipe C", "1999-05-05")},
              "stages": [{"number": 1, "date": "2026-03-01", "name": "Étape 1",
                          "results": {"stage": [ligne(a, 1), ligne(b, 2), ligne(c, None, "DNS")], "gc": [ligne(a, 1)]}},
                         {"number": 2, "date": "2026-03-02", "name": "Étape 2",
                          "results": {"stage": [ligne(b, 1), ligne(a, 11), ligne(c, None, "DNF")],
                                      "gc": [ligne(b, 1), ligne(a, 2)]}}],
              "final": None}
    unjour = {"id": "c2", "name": "Classique", "uci_class": "1.1", "category": ".1", "race_type": "one_day",
              "status": "finished", "start_date": "2026-03-10", "end_date": "2026-03-10", "season": 2026,
              "riders": {a: ref(a, "Jean Dupont", "FRA", "Équipe A2", "2000-01-01")},
              "stages": [{"number": None, "date": "2026-03-10", "name": "Course", "results": {"stage": [ligne(a, 3)]}}],
              "final": None}
    en_cours = dict(course, id="c3", status="in_progress", start_date="2026-04-01")
    ranking = {"name": "Classement UCI individuel", "date": "2026-03-15", "source": "uci",
               "rows": [{"rank": 5, "rider": "DUPONT Jean", "birth_date": "2000-01-01", "nationality": "FRA",
                         "team": "X", "points": 1234.5},
                        {"rank": 9, "rider": "DURAND Luc", "birth_date": None, "nationality": "BEL", "team": "Y",
                         "points": 800},
                        {"rank": 12, "rider": "MARTIN Paul", "birth_date": "1980-05-05", "nationality": "FRA",
                         "team": "Z", "points": 50}]}
    d = build_riders([course, unjour, en_cours], ranking, now=datetime.datetime(2026, 6, 1))
    R = d["riders"]
    assert d["season"] == 2026 and d["ranking"]["date"] == "2026-03-15"
    ja = R[a]
    assert d["races"]["c1"]["name"] == "Tour Test" and "race_name" not in ja["results"][0]
    assert ja["age"] == 26 and ja["team"] == "Équipe A" and ja["uci_rank"] == 5 and ja["uci_points"] == 1234.5
    # c3 (en cours) compte pour les étapes mais son général provisoire n'est pas un résultat final
    assert ja["stats"] == {"wins": 2, "podiums": 3, "top10": 3, "race_days": 5, "races": 3}, ja["stats"]
    assert [x["label"] for x in ja["results"] if x["race_id"] == "c1"] == ["Général final", "Étape 1"]
    assert not [x for x in ja["results"] if x["race_id"] == "c3" and x["classification"] != "stage"]
    assert R[b]["stats"]["gc_wins"] == 1 and "wins" in R[b]["stats"]
    assert R[b]["uci_rank"] == 9 and "age" not in R[b]            # repli par nom, unique
    assert "uci_rank" not in R[c]                                  # naissance contradictoire : pas d'attribution
    assert R[c]["stats"] == {"dnf": 2, "race_days": 2, "races": 2}   # le DNS n'est pas un jour de course
    assert d["riders"][a]["results"][0]["date"] >= d["riders"][a]["results"][-1]["date"] and "id" not in ja
    ambigu = {"name": "x", "date": "d", "source": "s", "rows": [
        {"rank": 1, "rider": "DURAND Luc", "birth_date": None, "nationality": "BEL", "points": 1},
        {"rank": 2, "rider": "Luc DURAND", "birth_date": None, "nationality": "BEL", "points": 2}]}
    assert build_riders([course], ambigu)["riders"][b].get("uci_rank") is None
    assert build_riders([course], None)["ranking"] is None
    autre = dict(course, id="c9", season=2027)
    assert build_riders([course, autre], None, season=2026)["races"].keys() == {"c1"}
    print("riders.py : tests OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Construit data/riders.json depuis data/races/*.json (sans classement UCI)")
    ap.add_argument("--courses", default="data/races")
    ap.add_argument("--sortie", default=None, help="défaut : data/riders-<saison>.json")
    ap.add_argument("--saison", type=int, default=None)
    ap.add_argument("--test", action="store_true", help="tests locaux uniquement")
    args = ap.parse_args()
    _test()
    if args.test:
        sys.exit(0)
    courses = charger_courses(args.courses)
    if args.sortie is None:
        args.sortie = f"data/riders-{args.saison}.json" if args.saison else "data/riders.json"
    d = write_riders(args.sortie, courses, None, args.saison)
    R = d["riders"]
    print(f"{args.sortie} : {os.path.getsize(args.sortie) / 1e6:.2f} Mo, {len(R)} coureurs, "
          f"{sum(len(f.get('results', [])) for f in R.values())} résultats")
    print("Top 10 des vainqueurs (étapes et courses d'un jour) :")
    for f in sorted(R.values(), key=lambda f: (-f["stats"].get("wins", 0), f["name"] or ""))[:10]:
        print(f"  {f['stats']['wins']:>2} · {f['name']} ({f['nationality']}, {f['team']})")
    for mot in ("Magnier", "Seixas"):
        for f in R.values():
            if f["name"] and mot in f["name"]:
                print(_fiche_texte(f, d['races']))
