#!/usr/bin/env python3
"""Génère le jeu d'archives FICTIF (docs/SPEC.md §4.4) dans tools/fixtures/data/archives/.

Trois saisons passées cohérentes avec tools/fixtures/data (saison courante 2026 : N-1 = 2025, donc archives <= 2024) :
- 2024 : complète, avec ranking.json et riders.json ;
- 2023 : `complete` = false (collecte en cours), sans riders.json ni ranking.json ;
- 2022 : complète, avec riders.json mais sans ranking.json (classement UCI indisponible).
Les courses passent par les vraies fonctions du collecteur (`finalize_race`, `compact_race`, `build_index`,
`riders.build_riders`) : le schéma est celui des archives réelles (clés null absentes). Déterministe (graine fixe).
Ne touche pas au reste de tools/fixtures/data.

Cohérence éditions / carrières (docs/SPEC.md §4.4) : le « Grand Prix de Test-sur-Mer (fictif) » (FRA) existe en 2022, 2023, 2024 et dans le Calendrier fictif (saison 2026) -> encart « Éditions précédentes » ; le coureur « Paul Épure » (même rider_id que
dans riders-2026.json) court en 2022, 2024 et dans le Calendrier -> onglet « Carrière » sur trois saisons. `editions.json` et `carrieres/` sont
produits par `collector.write_archives_index` (mêmes fonctions que la production).

    python tools/fixtures/generer_archives.py
"""
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import collector  # noqa: E402
import generer_fixtures as gf  # noqa: E402
import riders as riders_mod  # noqa: E402

SORTIE = Path(__file__).resolve().parent / "data" / "archives"
AUJOURDHUI = dt.date(2026, 11, 11)


def etape(pel, partants, profil, date, num, nom, dist, vitesse, start, finish, typ="road"):
    res, t0 = gf.simuler_etape(pel, profil, partants, vitesse, dist)
    rows = [gf.ligne(i + 1, None, c, time_s=t0 + g, gap_s=g) for i, (c, g) in enumerate(res)]
    return rows, {"number": num, "date": date, "name": nom, "start": start, "finish": finish, "type": typ, "route": None}


def course_etapes(pel):
    base = "2024-03-12"
    c = {"id": "fx-a24-tour-hc", "name": "Tour des Maquettes (fictif)", "country": "FRA", "flag": "fr", "uci_class": "2.HC",
         "category": "Pro", "race_type": "stage_race", "start_date": base, "end_date": "2024-03-15", "stages_total": 4,
         "selection_reason": "classe", "sources": ["uci"], "season": 2024, "_complete": True, "_fixture": True}
    profils = [("vallonne", "road", 168, 41, "Villetest", "Bourg-Maquette"), ("plat", "road", 154, 44, "Bourg-Maquette", "Saint-Fictif"),
               ("clm", "itt", 18, 50, "Saint-Fictif", "Saint-Fictif"), ("montagne", "road", 142, 36, "Essai-les-Bains", "Col-du-Témoin")]
    stages, cumul, tous = [], {}, pel.coureurs
    abandons = {2: tous[5], 3: tous[9]}
    pts_cum, kom_cum = {}, {}
    partants = list(tous)
    for i, (prof, typ, dist, vit, dep, arr) in enumerate(profils):
        date = gf.jour(base, i)
        if i in abandons:
            partants = [x for x in partants if x is not abandons[i]]
        rows, st = etape(pel, partants, prof, date, i + 1, f"Étape {i + 1}", dist, vit, dep, arr, typ)
        t0 = rows[0]["time_s"]
        for r in rows:
            cumul[r["rider_id"]] = cumul.get(r["rider_id"], 0) + r["time_s"]
        classes = sorted(partants, key=lambda x: cumul[x["ref"]["id"]])
        gc = [gf.ligne(k + 1, None, x, time_s=cumul[x["ref"]["id"]], gap_s=cumul[x["ref"]["id"]] - cumul[classes[0]["ref"]["id"]])
              for k, x in enumerate(classes)]
        ordre = [next(x for x in partants if x["ref"]["id"] == r["rider_id"]) for r in rows]
        for k, x in enumerate(ordre[:10]):
            pts_cum[x["ref"]["id"]] = pts_cum.get(x["ref"]["id"], 0) + (50, 30, 20, 18, 16, 14, 12, 10, 8, 7)[k]
            if prof == "montagne" or i == 0:
                kom_cum[x["ref"]["id"]] = kom_cum.get(x["ref"]["id"], 0) + (10, 8, 6, 4, 2, 1, 1, 1, 1, 1)[k]
        par_id = {x["ref"]["id"]: x for x in tous}
        pts = [gf.ligne(k + 1, None, par_id[rid], points=v) for k, (rid, v) in enumerate(sorted(pts_cum.items(), key=lambda t: -t[1]))]
        kom = [gf.ligne(k + 1, None, par_id[rid], points=v) for k, (rid, v) in enumerate(sorted(kom_cum.items(), key=lambda t: -t[1]))]
        jeunes = [gf.ligne(k + 1, None, x, time_s=cumul[x["ref"]["id"]], gap_s=cumul[x["ref"]["id"]] - cumul[classes[0]["ref"]["id"]])
                  for k, x in enumerate([y for y in classes if 1999 <= int(y["birth"][:4])][:12])]
        st["results"] = {"stage": rows, "gc": gc, "points": pts, "mountain": kom, "youth": jeunes}
        for k in range(1, 4):   # quelques points UCI au vainqueur des 3 premières places
            rows[k - 1]["uci_points"] = (20, 12, 8)[k - 1]
        st["ai_summary"] = f"{ordre[0]['ref']['name']} remporte l'étape devant {ordre[1]['ref']['name']} et {ordre[2]['ref']['name']}."
        st["summary_source"] = "fallback"
        stages.append(st)
    # abandons : lignes DNF en fin de classement de l'étape suivant leur abandon
    for i, x in abandons.items():
        stages[i]["results"]["stage"].append(gf.ligne(None, "DNF", x))
    dernier = stages[-1]["results"]
    c["final"] = {k: [dict(r) for r in v] for k, v in dernier.items() if k != "stage"}
    c["stages"] = stages
    c["riders"] = {k: v for k, v in pel.riders_dict().items()}
    c["updated_at"] = "2024-03-15T19:00:00Z"
    return c


def course_un_jour(pel, id_, nom, pays, flag, classe, cat, date, raison, profil, dist, vitesse, nb=None, forcer=None):
    partants = pel.coureurs[:nb] if nb else pel.coureurs
    res, t0 = gf.simuler_etape(pel, profil, partants, vitesse, dist, forcer=forcer)
    rows = [gf.ligne(i + 1, None, c, time_s=t0 + g, gap_s=g) for i, (c, g) in enumerate(res)]
    for k, uci in enumerate((125, 80, 50)):
        rows[k]["uci_points"] = uci
    rows.append(gf.ligne(None, "DNF", pel.coureurs[-1]))
    a = int(date[:4])
    ordre = rows[0]
    gagnant = next(x for x in pel.coureurs if x["ref"]["id"] == ordre["rider_id"])["ref"]["name"]
    return {"id": id_, "name": nom, "country": pays, "flag": flag, "uci_class": classe, "category": cat, "race_type": "one_day",
            "start_date": date, "end_date": date, "stages_total": 1, "selection_reason": raison, "sources": ["uci"], "season": a,
            "_complete": True, "_fixture": True, "updated_at": f"{date}T18:00:00Z",
            "stages": [{"number": None, "date": date, "name": "Course", "start": None, "finish": None, "type": "road", "route": None,
                        "results": {"stage": rows}, "ai_summary": f"{gagnant} s'impose.", "summary_source": "fallback"}],
            "final": None, "riders": pel.riders_dict()}


def ecrire_saison(annee, courses, complete, ranking=None):
    dossier = SORTIE / str(annee)
    shutil.rmtree(dossier, ignore_errors=True)
    for c in courses:
        collector.finalize_race(c, AUJOURDHUI)
        collector._dump(str(dossier / "races" / f"{c['id']}.json"), collector.compact_race(c))
    ch = collector.charger_courses_archive(str(dossier))
    idx = collector.build_index(ch, annee, [], None)
    idx.update({"archive": True, "complete": complete, "_fixture": True, "generated_at": f"{annee + 1}-01-15T04:00:00Z"})
    collector._dump(str(dossier / "index.json"), idx)
    collector._dump(str(dossier / "state.json"), {"complete": complete, "top10_checked": {}})
    if ranking:
        collector._dump(str(dossier / "ranking.json"), ranking)
    if complete:
        fiches = riders_mod.build_riders(ch, ranking, now=dt.datetime(annee, 10, 14, 23, 59, tzinfo=dt.timezone.utc), season=annee)
        fiches["_fixture"] = True
        collector._dump(str(dossier / "riders.json"), fiches)


ID_COMMUN = "epure-paul-19970711"     # présent dans tools/fixtures/data/riders-2026.json (Calendrier fictif)


def imposer_coureur_commun(pel):
    """Donne au premier coureur (leader d'équipe) l'identité du coureur commun à plusieurs saisons."""
    c = pel.coureurs[0]
    c["ref"].update(id=ID_COMMUN, name="Paul Épure", nationality="FRA", flag="fr", is_french=True)
    c["birth"] = "1997-07-11"


def main():
    gf.rnd.seed(20240315)
    pel = gf.Peloton(8, 5, forcer_francais=9)
    imposer_coureur_commun(pel)
    tour = course_etapes(pel)
    classique = course_un_jour(pel, "fx-a24-classique-hc", "Grand Prix de l'Essai (fictif)", "BEL", "be", "1.HC", "Pro",
                               "2024-03-02", "classe", "vallonne", 196, 42)
    gp_fr = course_un_jour(pel, "fx-a24-gp-fr", "Grand Prix de Test-sur-Mer (fictif)", "FRA", "fr", "1.1", ".1",
                           "2024-04-07", "france", "plat", 181, 43, nb=30)
    pel2 = gf.Peloton(6, 5, forcer_francais=8)
    imposer_coureur_commun(pel2)
    omloop = course_un_jour(pel2, "fx-a23-omloop", "Omloop de Démonstration (fictif)", "BEL", "be", "1.UWT", "WT",
                            "2023-02-25", "classe", "accidente", 203, 41)
    gp23 = course_un_jour(pel2, "fx-a23-gp-fr", "Grand Prix de Test-sur-Mer 2023 (fictif)", "FRA", "fr", "1.1", ".1",
                          "2023-03-19", "france", "plat", 176, 43, nb=28)
    pel3 = gf.Peloton(6, 5, forcer_francais=7)
    imposer_coureur_commun(pel3)
    gp22 = course_un_jour(pel3, "fx-a22-gp-fr", "Grand Prix de Test-sur-Mer (fictif)", "FRA", "fr", "1.1", ".1",
                          "2022-03-27", "france", "plat", 179, 43, nb=30, forcer=ID_COMMUN)
    trophee22 = course_un_jour(pel3, "fx-a22-trophee", "Trophée de Brouillon-les-Bains (fictif)", "FRA", "fr", "1.2", ".2",
                               "2022-05-08", "france", "vallonne", 168, 41, nb=25)
    # classement UCI de fin de saison 2024 : coureurs du peloton 2024, points décroissants
    rows = []
    for k, c in enumerate(sorted(pel.coureurs, key=lambda x: -sum(x["comp"].values()))):
        ref = c["ref"]
        rows.append({"rank": k + 1, "previous_rank": k + 2 if k % 3 else k, "rider": ref["name"].split()[-1].upper() + " " + ref["name"].split()[0],
                     "name": ref["name"], "birth_date": c["birth"], "nationality": ref["nationality"], "team": ref["team"],
                     "points": 3400 - k * 71, "rider_id": ref["id"], "uci_id": 20000000 + k})
    ranking = {"_fixture": True, "name": "UCI World Ranking (fictif)", "date": "2024-10-14", "source": "fixture", "rows": rows}
    ecrire_saison(2024, [tour, classique, gp_fr], True, ranking)
    ecrire_saison(2023, [omloop, gp23], False)
    ecrire_saison(2022, [gp22, trophee22], True)
    collector.ARCHIVES_DIR = str(SORTIE)
    recap = collector.write_archives_index("2026-11-11T00:00:00Z")
    print([(s["season"], s["complete"], s["races"], s["size_bytes"]) for s in recap["seasons"]])


if __name__ == "__main__":
    main()
