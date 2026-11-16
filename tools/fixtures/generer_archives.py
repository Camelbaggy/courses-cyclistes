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
dans riders-2026.json) court en 2022, 2024 et dans le Calendrier -> onglet « Carrière » sur trois saisons. `editions.json`, `carrieres/` et `entites/`
(encyclopédie : coureurs, équipes, courses, saisons, pays, recherche) sont produits par `collector.write_archives_index`
(mêmes fonctions que la production ; `entites/` lit aussi le Calendrier fictif `tools/fixtures/data`).

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


ID_COMMUN = "epure-paul-19970711"     # présent dans tools/fixtures/data/riders-2026.json (Calendrier fictif)


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
    selection_nationale(c)
    c["updated_at"] = "2024-03-15T19:00:00Z"
    return c


def selection_nationale(c, nb=5):
    """Sélection nationale FICTIVE : dans CETTE course seulement, `nb` coureurs français (hors coureur commun) courent sous le libellé
    « France » (un libellé égal au nom d'un pays dont tous les coureurs de la saison ont cette nationalité : `encyclopedie._est_nationale`).
    Les fiches des autres courses gardent leurs équipes de marque."""
    francais = [r for rid, r in sorted(c["riders"].items()) if r["nationality"] == "FRA" and rid != ID_COMMUN][:nb]
    assert len(francais) == nb, "pas assez de Français pour la sélection nationale fictive"
    for r in francais:
        r["team"] = "France"


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




def imposer_coureur_commun(pel):
    """Donne au premier coureur (leader d'équipe) l'identité du coureur commun à plusieurs saisons."""
    c = pel.coureurs[0]
    c["ref"].update(id=ID_COMMUN, name="Paul Épure", nationality="FRA", flag="fr", is_french=True)
    c["birth"] = "1997-07-11"


def ecrire_cache_wikidata(codes):
    """Petit cache Wikidata FICTIF (entites/wikidata/) cohérent avec les entités : un coureur rapproché (identifiants Q99900…, fictifs),
    une lignée portant l'équipe-saison « Alpha Racing 2024 ». Image factice locale (SVG), jamais d'URL réseau."""
    dossier = SORTIE / "entites" / "wikidata"
    shutil.rmtree(dossier, ignore_errors=True)
    (dossier / "fictif").mkdir(parents=True)
    (dossier / "fictif" / "photo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320"><rect width="320" height="320" fill="#2b3a55"/>'
        '<circle cx="160" cy="120" r="56" fill="#8fa3c7"/><rect x="80" y="196" width="160" height="110" rx="50" fill="#8fa3c7"/></svg>', encoding="utf-8")
    v = "2026-11-10"
    photo = {"url": "entites/wikidata/fictif/photo.svg", "page": "entites/wikidata/fictif/photo.svg", "auteur": "Image fictive", "licence": "CC0",
             "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/", "verifie": v}
    collector._dump(str(dossier / "coureurs.json"), {ID_COMMUN: {
        "qid": "Q99900001", "verifie": v, "lieu": {"qid": "Q99900002", "libelle": "Test-sur-Mer (fictif)"}, "taille": 1.78, "image": "Photo fictive.svg",
        "sitelinks": {"fr": "Paul Épure (fictif)", "en": "Paul Epure (fictional)", "nl": "Paul Épure (fictief)"},
        # P54 fictifs à précisions variées (année, mois, jour ; avec ou sans fin) pour la frise « Parcours » de la fiche coureur
        "equipes": [{"qid": "Q99900100", "libelle": "Alpha Racing (fictif)", "debut": "2022", "precision_debut": "annee"},
                    {"qid": "Q99900101", "libelle": "Équipe de développement Alpha (fictive)", "debut": "2016-08", "precision_debut": "mois",
                     "fin": "2017-12-31", "precision_fin": "jour"},
                    {"qid": "Q99900102", "libelle": "Delta Cycling (fictif)", "debut": "2018-03-12", "precision_debut": "jour", "fin": "2021", "precision_fin": "annee"}]}})
    collector._dump(str(dossier / "images.json"), {"Photo fictive.svg": photo, "Logo fictif.svg": dict(photo, auteur="Logo fictif")})
    collector._dump(str(dossier / "equipes.json"), {"alpha-racing-2024": {"qid": "Q99900100", "preuve": f"P1998 {codes['Alpha Racing']} [fictif]", "verifie": v}})
    collector._dump(str(dossier / "lignees.json"), {"Q99900100": {
        "libelle": "Alpha Racing (fictif)", "verifie": v, "logo": "Logo fictif.svg", "pays": {"qid": "Q99900003", "libelle": "France (fictif)"},
        "classes": ["UCI ProTeam (fictif)"], "sitelinks": {"fr": "Alpha Racing (fictif)"},
        "noms": [{"nom": "Alpha Cycling (fictif)", "debut": "2018", "fin": "2021"}, {"nom": "Alpha Racing (fictif)", "debut": "2022"}],
        "codes": [{"code": "FXA", "debut": "2018", "fin": "2021"}, {"code": codes["Alpha Racing"], "debut": "2022"}]}})


def ajouter_grands_tours_fictifs():
    """Le jeu fictif n'a aucun grand tour (clés d'édition exactes « tour de france|FRA »…) : on ajoute à la main, dans entites/coureurs/e.json
    UNIQUEMENT, des entrées `grands_tours` et `corrections` FICTIVES pour le coureur commun (grille Giro / Tour / Vuelta de la fiche : rang, abandon, hors délai).
    Les race_id pointent vers des fiches fictives existantes ; ces entrées ne sont pas produites par encyclopedie.construire."""
    chemin = SORTIE / "entites" / "coureurs" / "e.json"
    d = json.loads(chemin.read_text(encoding="utf-8"))
    d[ID_COMMUN]["grands_tours"] = [
        {"season": 2024, "course": "tour", "race_id": "fx-a24-tour-hc", "rank": 2},
        {"season": 2024, "course": "vuelta", "status": "DNF", "race_id": "fx-a24-classique-hc"},
        {"season": 2023, "course": "giro", "race_id": "fx-a23-omloop", "rank": 14},
        {"season": 2023, "course": "tour", "status": "OTL", "race_id": "fx-a23-gp-fr"},
        {"season": 2022, "course": "vuelta", "race_id": "fx-a22-gp-fr", "rank": 41}]
    # correction de source FICTIVE (corrections_coureurs.json en production) : la fiche affiche la valeur UCI d'origine et la source
    d[ID_COMMUN]["corrections"] = [{"champ": "birth_date", "uci": "1997-07-12", "source": "Wikidata Q99900 (P569)"}]
    collector._dump(str(chemin), d)


def ecrire_historique_fictif():
    """Petit cache FICTIF de palmarès Wikidata (entites/historique/) pour le « Grand Prix de Test-sur-Mer (fictif) » : années absentes de nos éditions UCI,
    avec les quatre statuts (ok, non_attribue, conflit, inconnu) et des coureurs historiques `wd-Q…` (identifiants fictifs Q9900…)."""
    dossier = SORTIE / "entites" / "historique"
    shutil.rmtree(dossier, ignore_errors=True)
    cle = "grand prix de test sur mer fictif|FRA"
    pod = lambda *q: [{"rang": r, "qid": x} for r, x in q]
    editions = [
        {"annee": 1925, "qid": "Q99900201", "date": "1925-04-12", "vainqueur": "Q99900301", "podium": pod((1, "Q99900301"), (2, "Q99900302"), (3, "Q99900303")), "statut": "ok", "verifie": "2026-11-16"},
        {"annee": 1926, "qid": "Q99900202", "date": "1926", "vainqueur": "Q99900302", "podium": pod((1, "Q99900302"), (2, "Q99900301")), "statut": "ok", "verifie": "2026-11-16"},
        {"annee": 1927, "qid": "Q99900203", "date": "1927-04-10", "podium": pod((2, "Q99900303"), (3, "Q99900301")), "statut": "non_attribue", "detail": {"p2321": ["Q99900304"]}, "verifie": "2026-11-16"},
        {"annee": 1928, "qid": "Q99900204", "date": "1928-04-08", "podium": pod((2, "Q99900303")), "statut": "conflit", "detail": {"p1346": ["Q99900301"], "p2321": ["Q99900302"]}, "verifie": "2026-11-16"},
        {"annee": 1929, "qid": "Q99900205", "date": "1929-04-07", "podium": pod((2, "Q99900303")), "statut": "inconnu", "verifie": "2026-11-16"},
        {"annee": 1930, "qid": "Q99900206", "date": "1930-04-06", "podium": [], "statut": "inconnu", "verifie": "2026-11-16"},
    ]
    collector._dump(str(dossier / "editions" / "g.json"), {cle: editions})
    noms = {"Q99900301": ("Pierre Ancien", "FRA"), "Q99900302": ("Jules Vieux", "FRA"), "Q99900303": ("Gaston Lointain", "BEL"), "Q99900304": ("Émile Déclassé", "ITA")}
    coureurs = {q: {"nom": n, "nationalite": nat, "naissance": f"19{i:02d}-05-17", "naissance_precision": "jour", "verifie": "2026-11-16"}
                for i, (q, (n, nat)) in enumerate(noms.items(), 1)}
    coureurs["Q99900303"] = {"nom": "Paul Démo", "rider_id": "demo-paul-19961228", "verifie": "2026-11-16"}   # coureur rattaché à nos données : palmarès historique sur sa fiche
    collector._dump(str(dossier / "coureurs.json"), coureurs)


def ecrire_classements(rows):
    """Trois instantanés FICTIFS du classement UCI 2024 (entites/classements/2024/, format de collector.collecter_classements) : mêmes coureurs que
    le classement de fin de saison, rangs et points décalés d'un instantané à l'autre (déterministe)."""
    import uci_ranking
    dossier = SORTIE / "entites" / "classements" / "2024"
    shutil.rmtree(dossier, ignore_errors=True)
    instantanes = [("2024-03-26", 1001, ["fin de mois"]), ("2024-06-25", 1002, ["fin de mois", "après Course de démonstration (fictive)"]),
                   ("2024-10-15", 1003, ["fin de mois"])]
    index = []
    for n, (date, moment, raisons) in enumerate(instantanes):
        k = len(rows)
        ordre = list(range(k))
        if n < 2:                                                  # petites permutations de rang ; le dernier instantané = classement final
            ordre[n], ordre[n + 1] = ordre[n + 1], ordre[n]
        lignes = [dict(rows[i], rank=r + 1, points=max(rows[i]["points"] - (2 - n) * 40 - i, 1), team_code=rows[i]["team_code"])
                  for r, i in enumerate(ordre)]
        collector._dump(str(dossier / f"{date}.json"), {"date": date, "nom": "UCI World Ranking (fictif)", "moment_id": moment, "raisons": raisons,
                                                       "lignes": uci_ranking.lignes_instantane(lignes)})
        index.append({"date": date, "raisons": raisons, "fichier": f"{date}.json"})
    collector._dump(str(dossier / "index.json"), index)


def main():
    gf.rnd.seed(20240315)
    pel = gf.Peloton(8, 5, forcer_francais=9)
    imposer_coureur_commun(pel)
    tour = course_etapes(pel)
    classique = course_un_jour(pel, "fx-a24-classique-hc", "Grand Prix de l'Essai (fictif)", "BEL", "be", "1.HC", "Pro",
                               "2024-03-02", "classe", "vallonne", 196, 42)
    gp_fr = course_un_jour(pel, "fx-a24-gp-fr", "Grand Prix de Test-sur-Mer (fictif)", "FRA", "fr", "1.1", ".1",
                           "2024-04-07", "france", "plat", 181, 43, nb=30, forcer=ID_COMMUN)
    pel2 = gf.Peloton(6, 5, forcer_francais=8)
    imposer_coureur_commun(pel2)
    omloop = course_un_jour(pel2, "fx-a23-omloop", "Omloop de Démonstration (fictif)", "BEL", "be", "1.UWT", "WT",
                            "2023-02-25", "classe", "accidente", 203, 41)
    gp23 = course_un_jour(pel2, "fx-a23-gp-fr", "Grand Prix de Test-sur-Mer 2023 (fictif)", "FRA", "fr", "1.1", ".1",
                          "2023-03-19", "france", "plat", 176, 43, nb=28)
    pel3 = gf.Peloton(6, 5, forcer_francais=7)
    imposer_coureur_commun(pel3)
    # 2022 : ancienne classe 1.HC (rangée en Pro) -> historique des classes de l'épreuve (page « épreuve », onglet Historique)
    gp22 = course_un_jour(pel3, "fx-a22-gp-fr", "Grand Prix de Test-sur-Mer (fictif)", "FRA", "fr", "1.HC", "Pro",
                          "2022-03-27", "france", "plat", 179, 43, nb=30, forcer=ID_COMMUN)
    trophee22 = course_un_jour(pel3, "fx-a22-trophee", "Trophée de Brouillon-les-Bains (fictif)", "FRA", "fr", "1.2", ".2",
                               "2022-05-08", "france", "vallonne", 168, 41, nb=25)
    # classement UCI de fin de saison 2024 : coureurs du peloton 2024, points décroissants
    rows = []
    CODES_EQUIPES = {t: f"FX{i + 1}" for i, t in enumerate(sorted({c["ref"]["team"] for c in pel.coureurs}))}   # codes fictifs
    for k, c in enumerate(sorted(pel.coureurs, key=lambda x: -sum(x["comp"].values()))):
        ref = c["ref"]
        rows.append({"rank": k + 1, "previous_rank": k + 2 if k % 3 else k, "rider": ref["name"].split()[-1].upper() + " " + ref["name"].split()[0],
                     "name": ref["name"], "birth_date": c["birth"], "nationality": ref["nationality"], "team": ref["team"],
                     "points": 3400 - k * 71, "rider_id": ref["id"], "uci_id": 20000000 + k, "team_code": CODES_EQUIPES[ref["team"]]})
    ranking = {"_fixture": True, "name": "UCI World Ranking (fictif)", "date": "2024-10-14", "source": "fixture", "rows": rows}
    ecrire_saison(2024, [tour, classique, gp_fr], True, ranking)
    ecrire_saison(2023, [omloop, gp23], False)
    ecrire_saison(2022, [gp22, trophee22], True)
    collector.ARCHIVES_DIR = str(SORTIE)
    ecrire_cache_wikidata(CODES_EQUIPES)
    ecrire_classements(rows)
    ecrire_historique_fictif()
    collector.DATA_DIR = str(SORTIE.parent)    # Calendrier fictif (et non data/ réel) pour entites/ (module encyclopedie)
    recap = collector.write_archives_index("2026-11-11T00:00:00Z")
    ajouter_grands_tours_fictifs()
    print([(s["season"], s["complete"], s["races"], s["size_bytes"]) for s in recap["seasons"]])


if __name__ == "__main__":
    main()
