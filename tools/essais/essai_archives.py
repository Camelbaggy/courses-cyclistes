#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Étape 0 du plan archives (docs/PLAN_ARCHIVES.md §2) : profondeur réelle de UCI DataRide.

Lecture seule, sans rien écrire dans data/ : saisons disponibles, nombre de courses hommes élite par saison,
classes UCI rencontrées (une saison par tranche : 2023, 2018, 2013, 2008), lecture de 3 courses témoins par saison
(grand tour en lecture partielle, classique et course française .1 en lecture complète), moments du classement UCI,
recherche des conditions d'utilisation. Pause de 2 s entre requêtes sur dataride.uci.org (rythme « archives »).
Balise [annees:2023,2018] dans le message de commit pour changer les saisons sondées."""
import json
import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, ".")
import netutil  # noqa: E402
import selection  # noqa: E402
import uci  # noqa: E402

MSG = os.environ.get("MSG", "")
m = re.search(r"\[annees:([0-9,]+)\]", MSG)
ANNEES = [int(a) for a in m.group(1).split(",")] if m else [2023, 2018, 2013, 2008]
netutil.HOST_DELAYS["dataride.uci.org"] = 2.0
uci.GARDER_BRUT = True  # diagnostic : ResultValue brut dans `_rv`
DEBUT = time.time()
NB_REQ = Counter()
_fetch = netutil.fetch_text


def _compte(url, *a, **k):
    NB_REQ[url.split("?")[0].rsplit("/iframe/", 1)[-1]] += 1
    return _fetch(url, *a, **k)


netutil.fetch_text = _compte


def titre(txt):
    print(f"\n######## {txt}  (t+{time.time() - DEBUT:.0f}s, {sum(NB_REQ.values())} requêtes)", flush=True)


def total_competitions(sid):
    """Nombre de courses hommes élite d'une saison (une seule ligne demandée : `total`)."""
    filtres = [("RaceTypeId", 0), ("CategoryId", uci.CATEGORY_MEN_ELITE), ("SeasonId", sid)]
    rep = uci._post("/iframe/Competitions/", uci._kendo(1, 0, filtres, ("StartDate", "asc"),
                                                        disciplineId=uci.DISCIPLINE_ROUTE), f"tot_{sid}")
    if not isinstance(rep, dict):
        return None, None
    d = rep.get("data") or [{}]
    return rep.get("total"), d[0] if d else {}


def resume_lignes(rows, riders):
    """Statistiques de qualité d'un classement normalisé."""
    if not rows:
        return "vide"
    if "rider_id" not in rows[0]:
        return f"{len(rows)} équipes, top : {rows[0].get('team')}"
    st = Counter(r["status"] for r in rows if r["status"])
    nais = sum(1 for r in rows if riders.get(r["rider_id"], {}).get("birth_date"))
    nat = sum(1 for r in rows if riders.get(r["rider_id"], {}).get("nationality"))
    eq = sum(1 for r in rows if riders.get(r["rider_id"], {}).get("team"))
    pts = sum(1 for r in rows if r["uci_points"])
    dos = sum(1 for r in rows if r["bib"])
    tps = sum(1 for r in rows if r["time_s"] is not None or r["points"] is not None)
    top = ", ".join(f"{r['rank']}. {riders.get(r['rider_id'], {}).get('name')} ({riders.get(r['rider_id'], {}).get('nationality')})"
                    for r in rows[:3])
    return (f"{len(rows)} lignes ; statuts {dict(st)} ; naissance {nais} ; nationalité {nat} ; équipe {eq} ; "
            f"dossard {dos} ; temps/points {tps} ; points UCI {pts} | {top}")


def trouve(comps, motifs, classe_cat=None, pays=None):
    for motif in motifs:
        for c in comps:
            if re.search(motif, c["name"], re.I) and (pays is None or c["country"] == pays):
                return c
    if classe_cat:
        for c in comps:
            if selection.categorie_classe(c["uci_class"]) == classe_cat and (pays is None or c["country"] == pays):
                return c
    return None


def lecture_complete(comp):
    titre(f"Lecture complète : {comp['name']} [{comp['uci_class']}] {comp['start_date']} ({comp['country']})")
    race = uci.get_race(comp)
    if not race:
        print("[ECHEC] get_race -> None")
        return
    riders = race["riders"]
    print(f"type={race['race_type']} complet={race['complete']} étapes={len(race['stages'])} coureurs={len(riders)} "
          f"taille JSON={len(json.dumps(race, ensure_ascii=False)) // 1024} Ko")
    for s in race["stages"][:3]:
        print(f"  étape {s['number']} {s['name']!r} {s['date']} {s['start']}->{s['finish']} type={s['type']}")
        for cle, rows in s["results"].items():
            print(f"     [{cle}] {resume_lignes(rows, riders)}")
    if race["final"] and race["race_type"] == "stage_race":
        print("  classement final :")
        for cle, rows in race["final"].items():
            print(f"     [{cle}] {resume_lignes(rows, riders)}")
    print("  français classés :", sum(1 for r in riders.values() if r.get("is_french")),
          "| french_top10 :", selection.french_top10(race))
    ex = next(iter(riders.values()), None)
    print("  exemple coureur :", json.dumps(ex, ensure_ascii=False))


def lecture_grand_tour(comp):
    """Grand tour : liste des étapes et des events de chacune, classements lus seulement pour la 1re étape,
    la dernière et le classement final (assez pour juger, sans 150 requêtes)."""
    titre(f"Grand tour (lecture partielle) : {comp['name']} [{comp['uci_class']}] {comp['start_date']} -> {comp['end_date']}")
    cid = comp["competition_id"]
    races = uci._liste_paginee("/iframe/Races/", taille=100, nom=f"r_{cid}", competitionId=cid,
                               disciplineId=uci.DISCIPLINE_ROUTE)
    if not races:
        print("[ECHEC] Races indisponible")
        return
    print(f"{len(races)} races :", ", ".join(f"{r.get('RaceName')}[{r.get('RaceTypeCode')}]" for r in races))
    print("  lieux de la 1re :", races[0].get("StartLocation"), "->", races[0].get("EndLocation"))
    final = [r for r in races if str(r.get("RaceCode") or "").upper() == "F" or
             str(r.get("RaceName") or "").strip().lower() == "final classification"]
    etapes = [r for r in races if r not in final]
    choix = ([etapes[0], etapes[-1]] if len(etapes) > 1 else etapes) + final[:1]
    riders = {}
    for r in choix:
        events = uci._post("/iframe/Events/", {"disciplineId": uci.DISCIPLINE_ROUTE, "raceId": r.get("Id")}, "ev")
        if not isinstance(events, list):
            print(f"  [ECHEC] events de {r.get('RaceName')}")
            continue
        print(f"  {r.get('RaceName')} : events {[e.get('EventName') for e in events]}")
        for ev in events:
            cle, portee = uci.event_key(ev.get("EventName"))
            if cle is None or portee == "stage":
                continue
            rows = uci._classements_event(ev, cle, riders)
            print(f"     [{cle}] {resume_lignes(rows, riders) if rows is not None else 'ÉCHEC'}")
            sans = [r for r in rows or [] if 'rider_id' in r and not r['status'] and r['time_s'] is None and r['points'] is None]
            if sans:
                print(f"        {len(sans)} lignes sans statut ni valeur ; ex. :", [(r['rank'], r.get('_rv')) for r in sans[:5]])


def saison(annee):
    sid = uci.get_season_id(annee)
    titre(f"Saison {annee} (id {sid}) : bornes {uci.season_bounds().get(annee)}")
    if sid is None:
        return
    comps = uci.list_competitions(sid)
    print(f"{len(comps)} courses hommes élite")
    classes = Counter(c["uci_class"] for c in comps)
    print("classes :", classes.most_common())
    print("catégorie actuelle (selection.categorie_classe) :",
          Counter(selection.categorie_classe(c["uci_class"]) for c in comps).most_common())
    inconnues = sorted(k for k in classes if selection.categorie_classe(k) is None)
    for k in inconnues:
        ex = [c["name"] for c in comps if c["uci_class"] == k][:6]
        print(f"   classe non reconnue {k!r} ({classes[k]}) : {ex}")
    print("en France :", sum(1 for c in comps if c["country"] == "FRA"),
          "| par classe :", Counter(c["uci_class"] for c in comps if c["country"] == "FRA").most_common())
    print("dates vides :", sum(1 for c in comps if not c["start_date"]), "| pays vides :", sum(1 for c in comps if not c["country"]))
    sel = selection.select(comps, None)
    print(f"sélection actuelle (sans FDJ) : {len(sel)} ; par catégorie {Counter(cat for _, cat, _ in sel).most_common()}")
    for motif in ("Giro d.Italia", "Tour de France", "Vuelta", "Milano", "Ronde van Vlaanderen|Tour des Flandres", "Roubaix",
                  "Li[eè]ge", "Lombardia", "Championnat|National Championships"):
        c = [x for x in comps if re.search(motif, x["name"], re.I)]
        print(f"   {motif!r} : {[(x['name'], x['uci_class'], x['country'], x['start_date']) for x in c[:4]]}")

    gt = trouve(comps, [r"^Tour de France"], "WT")
    if gt:
        lecture_grand_tour(gt)
    classique = trouve(comps, [r"Roubaix", r"Milano.*Sanremo"])
    if classique:
        lecture_complete(classique)
    fr = trouve(comps, [], ".1", "FRA")
    fr = next((c for c in comps if c["country"] == "FRA" and selection.categorie_classe(c["uci_class"]) == ".1"
               and c["uci_class"].startswith("1.")), fr)
    if fr:
        lecture_complete(fr)
    classement(annee, sid)


def classement(annee, sid):
    titre(f"Classement UCI, saison {annee}")
    import uci_ranking
    lst = uci_ranking.list_rankings(sid)
    print(f"{len(lst)} classements :", [(r["group_id"], r["group_name"], r["type_id"], r["id"]) for r in lst if r["type_id"] == 1])
    indiv = [r for r in lst if r["type_id"] == 1 and r["id"] is not None]
    if not indiv:
        return
    cl = next((r for r in indiv if r["group_id"] == 1), indiv[0])
    mom = netutil.fetch_json(f"{uci.BASE}/iframe/GetRankingMoments/?disciplineId={uci.DISCIPLINE_ROUTE}"
                             f"&disciplineSeasonId={sid}&rankingId={cl['id']}", raw_name="mom")
    if isinstance(mom, list):
        print(f"moments de {cl['name']!r} : {len(mom)} ; premiers {[m.get('Name') for m in mom[:3]]} ; "
              f"derniers {[m.get('Name') for m in mom[-3:]]}")
        if mom:
            print("   exemple :", json.dumps(mom[-1], ensure_ascii=False)[:300])
    else:
        print("moments indisponibles :", str(mom)[:200])
    filtres = [("RaceTypeId", 0), ("CategoryId", uci.CATEGORY_MEN_ELITE), ("SeasonId", sid), ("MomentId", cl["moment_id"])]
    rep = uci._post("/iframe/ObjectRankings/", uci._kendo(5, 0, filtres, None, rankingId=cl["id"],
                    disciplineId=uci.DISCIPLINE_ROUTE, rankingTypeId=1), "rk")
    if isinstance(rep, dict):
        print(f"{cl['name']!r} (moment {cl['moment_id']}) : total {rep.get('total')} lignes ; top 5 :")
        for lg in rep.get("data") or []:
            print(f"   {lg.get('Rank')} {lg.get('DisplayName')} {lg.get('NationName')} {lg.get('Points')} "
                  f"naissance={uci._date_iso(lg.get('BirthDate'))} calcul={uci._date_iso(lg.get('ComputationDate'))}")


def conditions():
    titre("Conditions d'utilisation de DataRide")
    for url in ("https://dataride.uci.org/", "https://dataride.uci.org/iframe/Results/10/"):
        html = netutil.fetch_text(url, raw_name="cgu")
        if not html:
            print(f"{url} : indisponible")
            continue
        liens = sorted(set(re.findall(r'href="([^"]*(?:term|legal|condition|privacy|cgu|disclaimer|mention)[^"]*)"', html, re.I)))
        print(f"{url} : {len(html)} octets ; liens juridiques : {liens}")
        for mot in ("terms", "conditions", "copyright", "©", "reproduc", "licen"):
            for mm in list(re.finditer(re.escape(mot), html, re.I))[:2]:
                extrait = re.sub(r"<[^>]+>", " ", html[max(0, mm.start() - 150):mm.end() + 200])
                print(f"   [{mot}] …{' '.join(extrait.split())}…")
    for url in ("https://www.uci.org/terms-of-use", "https://www.uci.org/legal-notice", "https://dataride.uci.ch/robots.txt"):
        txt = netutil.fetch_text(url, raw_name="cgu2")
        if txt:
            propre = " ".join(re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", txt, flags=re.S).split())
            print(f"{url} : {len(txt)} octets")
            for mot in ("data", "reproduc", "commercial", "extract", "database", "permission", "automated", "robot", "scrap"):
                for mm in list(re.finditer(mot, propre, re.I))[:2]:
                    print(f"   [{mot}] …{propre[max(0, mm.start() - 200):mm.end() + 250]}…")
        else:
            print(f"{url} : indisponible")


def main():
    if m:  # saisons choisies : liste complète déjà documentée (docs/recherche/archives_dataride.md)
        for a in ANNEES:
            saison(a)
        titre("Bilan")
        print("requêtes par endpoint :", NB_REQ.most_common())
        print("codes Irm :", uci.IRM_VUS.most_common())
        return
    titre("Saisons DataRide disponibles (route)")
    saisons = netutil.fetch_json(f"{uci.BASE}/iframe/GetRestrictedResultsDisciplineSeasons/?disciplineId={uci.DISCIPLINE_ROUTE}")
    if not isinstance(saisons, list):
        print("[ECHEC] liste des saisons")
        return
    saisons = sorted((s for s in saisons if isinstance(s, dict)), key=lambda s: s.get("Year") or 0)
    print(f"{len(saisons)} saisons : {saisons[0].get('Year')} -> {saisons[-1].get('Year')}")
    for s in saisons:
        tot, premiere = total_competitions(s.get("Id"))
        print(f"   {s.get('Year')} id={s.get('Id')} {uci._date_iso(s.get('StartDate'))} -> {uci._date_iso(s.get('EndDate'))} : "
              f"{tot} courses ME ; 1re : {(premiere or {}).get('CompetitionName')} {uci._date_iso((premiere or {}).get('StartDate'))}")
    for a in ANNEES:
        try:
            saison(a)
        except Exception as e:  # une saison en échec ne doit pas empêcher les autres
            print(f"[ECHEC] saison {a} : {type(e).__name__} {e}")
    try:
        conditions()
    except Exception as e:
        print(f"[ECHEC] conditions : {e}")
    titre("Bilan")
    print("requêtes par endpoint :", NB_REQ.most_common())
    print("events vus :", uci.EVENTS_VUS.most_common(40))
    print("codes Irm :", uci.IRM_VUS.most_common())


if __name__ == "__main__":
    main()
