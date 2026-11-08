#!/usr/bin/env python3
"""Génère le jeu de données FICTIF de test (conforme à docs/SPEC.md §4) dans tools/fixtures/data/.

Tous les coureurs, équipes et courses sont inventés (champ racine "_fixture": true). Le générateur est
déterministe (graine fixe) : relancer le script réécrit les mêmes fichiers.

    python tools/fixtures/generer_fixtures.py
"""
import json
import random
import re
import unicodedata
from pathlib import Path

SORTIE = Path(__file__).resolve().parent / "data"
rnd = random.Random(20260712)

PRENOMS = ["Jean", "Paul", "Louis", "Hugo", "Théo", "Étienne", "Lucas", "Mathis", "Antoine", "Julien", "Maxime",
           "Romain", "Kévin", "Yann", "Océan", "Rémi", "Tom", "Axel", "Nils", "Marco", "Luca", "Pieter", "Jens",
           "Diego"]
NOMS = ["Testeur", "Essayeur", "Fictif", "Maquette", "Brouillon", "Prototype", "Exemple", "Simulé", "Factice",
        "Bidon", "Échantillon", "Pilote", "Démo", "Témoin", "Jaugeur", "Banc", "Sondeur", "Étalon", "Modèle",
        "Gabarit", "Croquis", "Ébauche", "Trame", "Schéma", "Canevas", "Patron", "Spécimen", "Épure", "Calque",
        "Van der Testeur"]
EQUIPES = ["Alpha Racing", "Bravo Cycling", "Charlie Team", "Delta Pro Cycling", "Écho Cycling", "Foxtrot Racing",
           "Golf Team", "Hôtel Cycling", "India Pro Team", "Juliet Racing", "Kilo Team", "Lima Cycling",
           "Mike Racing", "Novembre Pro Cycling Team Fictive", "Oscar Team", "Papa Cycling", "Québec Racing",
           "Roméo Pro", "Sierra Team", "Tango Cycling", "Uniforme Racing", "Victor Team", "Whisky Pro",
           "X-Ray Cycling", "Zoulou Racing"]
NATIONS = [("FRA", "fr", 20), ("BEL", "be", 10), ("NED", "nl", 10), ("ESP", "es", 10), ("ITA", "it", 10),
           ("GBR", "gb", 6), ("GER", "de", 6), ("DEN", "dk", 6), ("SLO", "si", 4), ("NOR", "no", 4),
           ("COL", "co", 4), ("AUS", "au", 4), ("USA", "us", 3), ("SUI", "ch", 3)]
VILLES = ["Villetest", "Bourg-Maquette", "Saint-Fictif", "Essai-les-Bains", "Mont-Brouillon", "Pilotville",
          "Démo-sur-Loire", "Col-du-Témoin", "Port-Prototype", "Sondeville", "Étalon-la-Forêt", "Gabarit-le-Haut"]
MOIS_COURTS = ["", "janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.",
               "déc."]


def slug(texte):
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def tirer_nation():
    total = sum(p for _, _, p in NATIONS)
    x = rnd.uniform(0, total)
    for iso3, iso2, p in NATIONS:
        x -= p
        if x <= 0:
            return iso3, iso2
    return NATIONS[0][0], NATIONS[0][1]


def fmt_date(d):
    return d


def jour(base, n):
    """base 'AAAA-MM-JJ' + n jours (mois de 31 jours maximum suffisant pour ces fixtures)."""
    a, m, j = (int(x) for x in base.split("-"))
    j += n
    mois_len = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    while j > mois_len[m]:
        j -= mois_len[m]
        m += 1
    return f"{a:04d}-{m:02d}-{j:02d}"


# ---------------------------------------------------------------- peloton
class Peloton:
    def __init__(self, nb_equipes, par_equipe, forcer_francais=0):
        self.coureurs = []
        self.equipes = rnd.sample(EQUIPES, nb_equipes)
        combos = [(p, n) for p in PRENOMS for n in NOMS]
        rnd.shuffle(combos)
        self.team_nat = {e: tirer_nation()[0] for e in self.equipes}
        bib = 0
        for ie, eq in enumerate(self.equipes):
            for k in range(par_equipe):
                bib += 1
                prenom, nom = combos.pop()
                iso3, iso2 = tirer_nation()
                naiss = f"{rnd.randint(1989, 2005)}-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}"
                typ = "leader" if k == 0 else rnd.choice(["sprinter", "grimpeur", "rouleur", "puncheur",
                                                          "domestique", "domestique"])
                niveau = rnd.gauss(0, 0.8) + (1.4 if k == 0 else 0) - (0.6 if typ == "domestique" else 0)
                comp = {"plat": niveau * 0.3, "vallonne": niveau * 0.5, "accidente": niveau * 0.6,
                        "montagne": niveau * 0.7, "clm": niveau * 0.4}
                bonus = {"sprinter": {"plat": 1.8, "vallonne": 0.6, "montagne": -1.2},
                         "grimpeur": {"montagne": 1.8, "accidente": 0.6, "plat": -0.5, "clm": -0.6},
                         "rouleur": {"clm": 1.8, "plat": 0.7},
                         "puncheur": {"accidente": 1.5, "vallonne": 1.2},
                         "leader": {"montagne": 0.8, "clm": 0.6, "accidente": 0.5}}.get(typ, {})
                for cle, v in bonus.items():
                    comp[cle] += v
                rid = f"{slug(nom)}-{slug(prenom)}-{naiss.replace('-', '')}"
                ref = {"id": rid, "name": f"{prenom} {nom}", "nationality": iso3, "flag": iso2,
                       "is_french": iso3 == "FRA", "team": eq}
                self.coureurs.append({"ref": ref, "birth": naiss, "bib": 100 + bib + (ie // 1) * 0,
                                      "comp": comp, "type": typ})
        # numéros de dossard par tranches de 10 comme sur une vraie course
        for i, c in enumerate(self.coureurs):
            c["bib"] = (i // par_equipe + 1) * 10 + (i % par_equipe) + 1
        if forcer_francais:
            n = sum(c["ref"]["is_french"] for c in self.coureurs)
            for c in self.coureurs:
                if n >= forcer_francais:
                    break
                if not c["ref"]["is_french"]:
                    c["ref"].update(nationality="FRA", flag="fr", is_french=True)
                    n += 1

    def riders_dict(self):
        return {c["ref"]["id"]: {**c["ref"], "birth_date": c["birth"]} for c in self.coureurs}


def ligne(rank=None, status=None, c=None, **kw):
    row = {"rank": rank, "status": status, "bib": c["bib"] if c else None,
           "rider_id": c["ref"]["id"] if c else None, "time_s": None, "gap_s": None, "points": None,
           "bonus_s": None, "penalty_s": None, "uci_points": None}
    row.update(kw)
    return row


def simuler_etape(pel, profil, partants, vitesse, distance, forcer=None, bunch=15, echelle=6):
    """Retourne la liste (coureur, écart en s) triée, et le temps du vainqueur."""
    perfs = []
    for c in partants:
        p = c["comp"][profil] + rnd.gauss(0, 0.7)
        if forcer is not None and c["ref"]["id"] == forcer:
            p += 12
        perfs.append((p, c))
    perfs.sort(key=lambda t: -t[0])
    meilleur = perfs[0][0]
    res, g0 = [], 0
    for i, (p, c) in enumerate(perfs):
        raw = int(round((meilleur - p) * echelle))
        if i == 0:
            g0, gap = 0, 0
        elif bunch and raw - g0 <= bunch:
            gap = g0
        else:
            g0 = gap = raw
        res.append((c, gap))
    t_vainqueur = int(distance / vitesse * 3600)
    return res, t_vainqueur


def ordinal(n):
    return "1er" if n == 1 else f"{n}e"


def nom_court(c):
    return c["ref"]["name"]


# ---------------------------------------------------------------- course par étapes
def generer_course_etapes():
    pel = Peloton(25, 6, forcer_francais=30)
    coureurs = pel.coureurs
    francais = [c for c in coureurs if c["ref"]["is_french"]]
    sprinter_fr = next(c for c in francais if c["type"] == "sprinter")
    grimpeur_fr = next(c for c in francais if c["type"] in ("grimpeur", "leader") and c is not sprinter_fr)

    debut = "2026-07-04"
    # (numéro, nom, type, profil, distance, D+, vitesse, départ, arrivée, forcé, bunch, échelle, cols, route?)
    plan = [
        (0, "Prologue", "itt", "clm", 5.6, 40, 54.0, "Villetest", "Villetest", None, 0, 14, [], True),
        (1, "Étape 1", "road", "plat", 178.0, 900, 43.5, "Villetest", "Bourg-Maquette", None, 15, 6, [], True),
        (2, "Étape 2", "road", "vallonne", 161.5, 2100, 41.0, "Bourg-Maquette", "Saint-Fictif",
         sprinter_fr["ref"]["id"], 10, 9, [], False),
        (3, "Étape 3", "road", "montagne", 172.4, 3600, 36.5, "Saint-Fictif", "Mont-Brouillon", None, 6, 55,
         [("Col de la Maquette", 62.0, "3", 740, 6.2, 5.1), ("Col du Témoin", 118.5, "2", 1180, 9.8, 6.4),
          ("Col de la Couillole (fictif)", 154.0, "1", 1678, 15.7, 7.1)], True),
        (4, "Étape 4", "road", "plat", 190.2, 700, 44.0, "Mont-Brouillon", "Essai-les-Bains", None, 15, 6, [], True),
        (5, "Étape 5", "itt", "clm", 34.8, 350, 52.0, "Essai-les-Bains", "Essai-les-Bains", None, 0, 16, [], True),
        (6, "Étape 6", "road", "montagne", 158.3, 4300, 34.5, "Essai-les-Bains", "Col-du-Témoin", None, 6, 70,
         [("Côte de l'Épure", 41.0, "4", 520, 1.8, 6.0), ("Col de Calque", 83.2, "2", 1320, 11.4, 6.9),
          ("Col du Brouillon", 121.7, "1", 1890, 14.2, 7.8), ("Hors-catégorie de Gabarit", 158.3, "HC", 2410,
                                                              19.0, 8.1)], True),
        (7, "Étape 7", "road", "accidente", 143.9, 2600, 40.0, "Col-du-Témoin", "Gabarit-le-Haut",
         grimpeur_fr["ref"]["id"], 8, 40, [("Côte des Spécimens", 96.0, "3", 610, 2.4, 7.5)], False),
    ]
    # abandons : numéro d'étape -> [(statut, indice coureur)]
    domestiques = [c for c in coureurs if c["type"] == "domestique"]
    rnd.shuffle(domestiques)
    abandons = {2: [("DNF", domestiques[0]), ("DNF", domestiques[1])],
                3: [("DNF", domestiques[2]), ("OTL", domestiques[3]), ("OTL", domestiques[4])],
                4: [("DNS", domestiques[5]), ("DNF", domestiques[6])],
                5: [("DSQ", domestiques[7])],
                6: [("DNF", domestiques[8]), ("DNF", domestiques[9]), ("DNS", domestiques[10])],
                7: [("DNF", domestiques[11])]}
    # un Français leader qui abandonne tardivement
    ab_ids = {c["ref"]["id"] for lst in abandons.values() for _, c in lst}

    stages, cumul, bonus_cum, ranksum = [], {}, {}, {}
    pts_cum, mont_cum, prev_gc_rang = {}, {}, {}
    en_course = list(coureurs)
    maillots_iter = []
    cumul_equipes = {}
    for (num, nom, typ, profil, dist, dplus, vit, dep, arr, forcer, bunch, ech, cols, avec_route) in plan:
        partants = [c for c in en_course]
        # DNS avant le départ
        dns = [c for st, c in abandons.get(num, []) if st == "DNS"]
        partants = [c for c in partants if c not in dns]
        # DNF/DSQ ne finissent pas (OTL finissent hors délai)
        non_finisseurs = [(st, c) for st, c in abandons.get(num, []) if st in ("DNF", "DSQ")]
        hors_delai = [c for st, c in abandons.get(num, []) if st == "OTL"]
        finisseurs = [c for c in partants if c not in [x for _, x in non_finisseurs]]
        res, t0 = simuler_etape(pel, profil, [c for c in finisseurs if c not in hors_delai], vit, dist, forcer,
                                bunch, ech)
        # temps des hors délai : +25 min environ
        t_stage = {}
        rows_stage = []
        bonif = {} if typ == "itt" or num == 0 else {0: 10, 1: 6, 2: 4}
        for i, (c, gap) in enumerate(res):
            rid = c["ref"]["id"]
            t_stage[rid] = t0 + gap
            b = bonif.get(i)
            rows_stage.append(ligne(i + 1, None, c, time_s=t0 + gap, gap_s=gap, bonus_s=b,
                                    uci_points={0: 125, 1: 100, 2: 80, 3: 70, 4: 60}.get(i)
                                    if num == 7 else None))
        for c in hors_delai:
            gap = int(t0 * 0.12) + rnd.randint(0, 120)
            t_stage[c["ref"]["id"]] = t0 + gap
            rows_stage.append(ligne(None, "OTL", c, time_s=t0 + gap, gap_s=gap))
        for st, c in non_finisseurs:
            rows_stage.append(ligne(None, st, c))
        for c in dns:
            rows_stage.append(ligne(None, "DNS", c))
        # ---- cumul général
        for i, (c, gap) in enumerate(res):
            rid = c["ref"]["id"]
            cumul[rid] = cumul.get(rid, 0) + t_stage[rid]
            bonus_cum[rid] = bonus_cum.get(rid, 0) + (bonif.get(i) or 0)
            ranksum[rid] = ranksum.get(rid, 0) + i
        for c in hors_delai:
            cumul[c["ref"]["id"]] = cumul.get(c["ref"]["id"], 0) + t_stage[c["ref"]["id"]]
        sortants = {c["ref"]["id"] for st, c in abandons.get(num, [])}
        en_course = [c for c in en_course if c["ref"]["id"] not in sortants]
        gc_ordre = sorted(en_course, key=lambda c: (cumul[c["ref"]["id"]] - bonus_cum.get(c["ref"]["id"], 0),
                                                   ranksum[c["ref"]["id"]]))
        net = {c["ref"]["id"]: cumul[c["ref"]["id"]] - bonus_cum.get(c["ref"]["id"], 0) for c in gc_ordre}
        t_lead = net[gc_ordre[0]["ref"]["id"]]
        gc_rows = []
        for i, c in enumerate(gc_ordre):
            rid = c["ref"]["id"]
            gc_rows.append(ligne(i + 1, None, c, time_s=net[rid], gap_s=net[rid] - t_lead,
                                 bonus_s=bonus_cum.get(rid) or None))
        gc_rang = {r["rider_id"]: r["rank"] for r in gc_rows}
        # ---- points (maillot vert)
        if typ != "itt":
            for i, (c, _) in enumerate(res[:15]):
                p = [50, 30, 20, 18, 16, 14, 12, 10, 8, 7, 6, 5, 4, 3, 2][i]
                pts_cum[c["ref"]["id"]] = pts_cum.get(c["ref"]["id"], 0) + p
        pts_ids = [rid for rid in sorted(pts_cum, key=lambda r: -pts_cum[r]) if rid in gc_rang]
        par_id = {c["ref"]["id"]: c for c in coureurs}
        pts_rows = [ligne(i + 1, None, par_id[rid], points=pts_cum[rid]) for i, rid in enumerate(pts_ids)]
        # ---- montagne
        bareme = {"4": [1], "3": [2, 1], "2": [5, 3, 2, 1], "1": [10, 8, 6, 4, 2, 1],
                  "HC": [20, 15, 12, 8, 6, 4, 2, 1]}
        for (_, _, cat, *_r) in cols:
            tops = sorted(finisseurs, key=lambda c: -(c["comp"]["montagne"] + rnd.gauss(0, 1.0)))
            for i, p in enumerate(bareme[cat]):
                rid = tops[i]["ref"]["id"]
                mont_cum[rid] = mont_cum.get(rid, 0) + p
        m_ids = [rid for rid in sorted(mont_cum, key=lambda r: -mont_cum[r]) if rid in gc_rang]
        mont_rows = [ligne(i + 1, None, par_id[rid], points=mont_cum[rid]) for i, rid in enumerate(m_ids)]
        # ---- jeunes
        jeunes = [c for c in gc_ordre if int(c["birth"][:4]) >= 2001]
        t_j = net[jeunes[0]["ref"]["id"]] if jeunes else 0
        youth_rows = [ligne(i + 1, None, c, time_s=net[c["ref"]["id"]], gap_s=net[c["ref"]["id"]] - t_j)
                      for i, c in enumerate(jeunes)]
        # ---- équipes (3 meilleurs temps généraux par équipe)
        par_eq = {}
        for c in gc_ordre:
            par_eq.setdefault(c["ref"]["team"], []).append(net[c["ref"]["id"]])
        eq_tot = {e: sum(sorted(v)[:3]) for e, v in par_eq.items() if len(v) >= 3}
        eq_ordre = sorted(eq_tot, key=lambda e: eq_tot[e])
        teams_rows = [{"rank": i + 1, "team": e, "nationality": pel.team_nat[e], "time_s": eq_tot[e],
                       "gap_s": eq_tot[e] - eq_tot[eq_ordre[0]]} for i, e in enumerate(eq_ordre)]
        # ---- combativité
        comb_rows = []
        if num not in (0, 5):
            cb = rnd.choice(finisseurs[10:60])
            comb_rows = [ligne(1, None, cb)]
        # ---- Français en vue
        highlights = []
        for r in rows_stage:
            if r["rank"] and par_id[r["rider_id"]]["ref"]["is_french"] and r["rank"] <= 25:
                gcr = gc_rang.get(r["rider_id"])
                highlights.append({"rider": par_id[r["rider_id"]]["ref"], "stage_rank": r["rank"],
                                   "gc_rank": gcr,
                                   "gc_gap_s": net[r["rider_id"]] - t_lead if gcr else None})
        highlights = highlights[:5]
        # ---- résumé
        gagnant = res[0][0]
        d2, d3 = res[1][0], res[2][0]
        fr_best = highlights[0] if highlights else None
        leader = gc_ordre[0]
        txt = (f"[Résumé fictif] {nom_court(gagnant)} ({gagnant['ref']['team']}) s'impose à {arr} en "
               f"{t0 // 3600}h{(t0 % 3600) // 60:02d}'{t0 % 60:02d}\", devant {nom_court(d2)} et {nom_court(d3)}. ")
        if fr_best:
            txt += (f"Meilleur Français du jour, {fr_best['rider']['name']} termine {ordinal(fr_best['stage_rank'])}. ")
        txt += (f"{nom_court(leader)} occupe la tête du général"
                + (" après le prologue." if num == 0 else f" avec {gc_rows[1]['gap_s']} secondes d'avance."))
        source = {3: None, 7: "fallback"}.get(num, "gemini")
        if source is None:
            txt = None
        if source == "fallback":
            txt = (f"{nom_court(gagnant)} gagne l'étape. {nom_court(d2)} est deuxième, {nom_court(d3)} "
                   f"troisième. {nom_court(leader)} est leader du classement général.")
        # ---- route
        route = None
        if avec_route:
            route = {"distance_km": dist, "elevation_m": dplus, "profile": "clm" if typ == "itt" else
                     {"plat": "plat", "vallonne": "vallonné", "accidente": "accidenté",
                      "montagne": "montagne"}[profil],
                     "climbs": [{"name": n, "km": km, "category": cat, "altitude_m": alt, "length_km": ln,
                                 "gradient_pct": gr} for (n, km, cat, alt, ln, gr) in cols],
                     "cobbles": [], "source": "aso"}
        cls = {"stage": rows_stage, "gc": gc_rows, "points": pts_rows if typ != "itt" or pts_rows else [],
               "mountain": mont_rows if mont_cum else [], "youth": youth_rows, "teams": teams_rows,
               "combativity": comb_rows}
        if num == 0:  # prologue : pas de points ni de montagne
            cls["points"], cls["mountain"] = [], []
        stages.append({"number": num, "date": jour(debut, num), "name": nom, "start": dep, "finish": arr,
                       "type": typ, "route": route, "results": cls, "ai_summary": txt,
                       "summary_source": source, "french_highlights": highlights})
        prev_gc_rang = gc_rang
    dernier = stages[-1]["results"]["gc"]
    par_id = {c["ref"]["id"]: c for c in coureurs}
    leader = par_id[dernier[0]["rider_id"]]["ref"]
    bf = next(r for r in dernier if par_id[r["rider_id"]]["ref"]["is_french"])
    resume = {
        "id": "fx-tour-test", "name": "Tour de Test (fictif)", "country": "FRA", "flag": "fr",
        "uci_class": "2.UWT", "category": "WT", "race_type": "stage_race", "start_date": debut,
        "end_date": jour(debut, 22), "status": "in_progress", "stages_done": len(stages), "stages_total": 9,
        "selection_reason": "classe", "winner": None, "leader": leader,
        "best_french": {"rider": par_id[bf["rider_id"]]["ref"], "rank": bf["rank"], "classification": "gc"},
        "sources": ["uci", "aso"]}
    detail = {**resume, "_fixture": True, "stages": stages, "final": None, "riders": pel.riders_dict(),
              "updated_at": "2026-07-11T19:40:00Z"}
    return resume, detail, pel


# ---------------------------------------------------------------- courses d'un jour
def generer_un_jour(id_, nom, pays, flag, classe, cat, date, raison, nb_eq, par_eq, route=None, equipes=True,
                    distance=200.0, vitesse=43.0, forcer_fr=6, profil="accidente", sources=("uci",),
                    ai=True, avec_final=True):
    pel = Peloton(nb_eq, par_eq, forcer_francais=forcer_fr)
    par_id = {c["ref"]["id"]: c for c in pel.coureurs}
    res, t0 = simuler_etape(pel, profil, pel.coureurs[:-3], vitesse, distance, bunch=8, echelle=10)
    rows = []
    for i, (c, gap) in enumerate(res):
        rows.append(ligne(i + 1, None, c, time_s=t0 + gap, gap_s=gap,
                          uci_points=[500, 400, 325, 275, 225, 175, 150, 125, 100, 90][i]
                          if i < 10 and classe.endswith("UWT") else None))
    for c in pel.coureurs[-3:-1]:
        rows.append(ligne(None, "DNF", c))
    rows.append(ligne(None, "DNS", pel.coureurs[-1]))
    teams = []
    if equipes:
        par = {}
        for r in rows:
            if r["rank"]:
                par.setdefault(par_id[r["rider_id"]]["ref"]["team"], []).append(r["time_s"])
        tot = {e: sum(sorted(v)[:3]) for e, v in par.items() if len(v) >= 3}
        ordre = sorted(tot, key=lambda e: tot[e])
        teams = [{"rank": i + 1, "team": e, "nationality": pel.team_nat[e], "time_s": tot[e],
                  "gap_s": tot[e] - tot[ordre[0]]} for i, e in enumerate(ordre)]
    gagnant = res[0][0]
    francais = [r for r in rows if r["rank"] and par_id[r["rider_id"]]["ref"]["is_french"]]
    bf = francais[0] if francais else None
    highlights = [{"rider": par_id[r["rider_id"]]["ref"], "stage_rank": r["rank"], "gc_rank": None,
                   "gc_gap_s": None} for r in francais[:5] if r["rank"] <= 25]
    txt = None
    if ai:
        txt = (f"[Résumé fictif] {gagnant['ref']['name']} remporte {nom} en {t0 // 3600}h{(t0 % 3600) // 60:02d}'"
               f"{t0 % 60:02d}\". " + (f"Premier Français, {bf and par_id[bf['rider_id']]['ref']['name']} "
                                        f"termine {bf and ordinal(bf['rank'])}." if bf else
                                        "Aucun Français dans le top 10."))
    cls = {"stage": rows, "gc": [], "points": [], "mountain": [], "youth": [], "teams": teams,
           "combativity": []}
    stage = {"number": None, "date": date, "name": "Course", "start": None, "finish": None, "type": "road",
             "route": route, "results": cls, "ai_summary": txt, "summary_source": "gemini" if ai else None,
             "french_highlights": highlights}
    bf_ref = {"rider": par_id[bf["rider_id"]]["ref"], "rank": bf["rank"], "classification": "stage"} if bf else None
    resume = {"id": id_, "name": nom, "country": pays, "flag": flag, "uci_class": classe, "category": cat,
              "race_type": "one_day", "start_date": date, "end_date": date, "status": "finished",
              "stages_done": 1, "stages_total": 1, "selection_reason": raison, "winner": gagnant["ref"],
              "leader": None, "best_french": bf_ref, "sources": list(sources)}
    detail = {**resume, "_fixture": True, "stages": [stage], "final": cls if avec_final else None,
              "riders": pel.riders_dict(), "updated_at": f"{date}T18:30:00Z"}
    return resume, detail


def main():
    (SORTIE / "races").mkdir(parents=True, exist_ok=True)
    for f in (SORTIE / "races").glob("*.json"):
        f.unlink()
    courses = []

    r_tour, d_tour, pel = generer_course_etapes()
    courses.append((r_tour, d_tour))

    pave = {"distance_km": 257.0, "elevation_m": 1100, "profile": "plat", "climbs": [],
            "cobbles": [{"name": "Trouée d'Arenberg (fictive)", "km": 162.4, "length_km": 2.3, "difficulty": 5},
                        {"name": "Mons-en-Pévèle (fictif)", "km": 205.5, "length_km": 3.0, "difficulty": 5},
                        {"name": "Carrefour de l'Arbre (fictif)", "km": 240.1, "length_km": 2.1, "difficulty": 5},
                        {"name": "Secteur de l'Essai", "km": 120.0, "length_km": 1.4, "difficulty": 2},
                        {"name": "Secteur du Témoin", "km": 131.7, "length_km": 0.9, "difficulty": 1}],
            "source": "aso"}
    courses.append(generer_un_jour("fx-classique-paves", "Classique des Pavés (fictive)", "FRA", "fr", "1.UWT",
                                   "WT", "2026-04-12", "classe", 22, 7, route=pave, distance=257.0, vitesse=44.5,
                                   profil="plat", sources=("uci", "aso")))
    courses.append(generer_un_jour("fx-gp-test-sur-mer", "Grand Prix de Test-sur-Mer (fictif)", "FRA", "fr",
                                   "1.1", ".1", "2026-06-21", "france", 12, 5, route=None, equipes=False,
                                   distance=186.0, ai=False, forcer_fr=25))
    courses.append(generer_un_jour("fx-omloop-fictif", "Omloop Fictif", "BEL", "be", "1.UWT", "WT", "2026-02-28",
                                   "classe", 18, 6, distance=200.0, vitesse=42.0))
    courses.append(generer_un_jour("fx-trophee-fdj-1", "Trophée FDJ de Maquette", "FRA", "fr", "1.Pro", "FDJ",
                                   "2026-03-07", "fdj", 16, 6, distance=195.0))
    courses.append(generer_un_jour("fx-champ-france", "Championnats de France (fictifs)", "FRA", "fr", "CN",
                                   "Champ.", "2026-06-28", "championnat", 10, 6, distance=240.0, forcer_fr=60,
                                   equipes=False))
    courses.append(generer_un_jour("fx-gp-hors-france", "Grand Prix de l'Étranger (fictif)", "ITA", "it", "1.1",
                                   ".1", "2026-05-17", "francais_top10", 14, 6, distance=190.0, forcer_fr=10))

    for resume, detail in courses:
        (SORTIE / "races" / f"{resume['id']}.json").write_text(
            json.dumps(detail, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- index
    resumes = sorted((r for r, _ in courses), key=lambda r: r["start_date"])
    latest, wins = [], []
    for resume, detail in courses:
        par_id = detail["riders"]
        for st in detail["stages"]:
            premiere = st["results"]["stage"][0]
            gagnant = par_id[premiere["rider_id"]]
            ref = {k: gagnant[k] for k in ("id", "name", "nationality", "flag", "is_french", "team")}
            if st["number"] is None:
                label = "Course"
            elif st["number"] == 0:
                label = f"Prologue · {st['start']}"
            else:
                label = f"Étape {st['number']} · {st['start']} → {st['finish']}"
            bf = next(({"rider": {k: par_id[r['rider_id']][k] for k in ref}, "rank": r["rank"],
                        "classification": "stage"} for r in st["results"]["stage"]
                       if r["rank"] and par_id[r["rider_id"]]["is_french"]), None)
            latest.append({"race_id": resume["id"], "race_name": resume["name"], "stage_number": st["number"],
                           "date": st["date"], "label": label, "winner": ref, "best_french": bf,
                           "ai_summary": st["ai_summary"]})
            if ref["is_french"]:
                wins.append({"date": st["date"], "race_id": resume["id"], "stage_number": st["number"],
                             "rider": ref["name"], "rider_id": ref["id"], "race_name": resume["name"],
                             "label": "Course" if st["number"] is None else st["name"]})
    latest.sort(key=lambda x: x["date"], reverse=True)
    latest = latest[:20]
    wins.sort(key=lambda x: x["date"], reverse=True)

    # classement FDJ United Series fictif
    indiv = []
    noms = [(c["ref"]["name"], c["ref"]["team"]) for c in pel.coureurs if c["ref"]["is_french"]][:20]
    pts = 312
    for i, (n, t) in enumerate(noms):
        pts -= rnd.randint(8, 22)
        indiv.append({"rank": i + 1, "rider": n, "team": t, "points": pts})
    fdj = {"source": "lnc", "updated": "2026-07-11", "individual": indiv, "races": [
        {"name": "Trophée FDJ de Maquette", "date": "2026-03-07", "race_id": "fx-trophee-fdj-1"},
        {"name": "Classique des Pavés (fictive)", "date": "2026-04-12", "race_id": "fx-classique-paves"},
        {"name": "Grand Prix de Test-sur-Mer (fictif)", "date": "2026-06-21", "race_id": "fx-gp-test-sur-mer"},
        {"name": "Tour de Test (fictif) — manche non suivie", "date": "2026-07-04", "race_id": None},
        {"name": "Nocturne de Simulation", "date": "2026-08-15", "race_id": None}]}
    upcoming = [
        {"name": "Classique d'Août (fictive)", "country": "ESP", "flag": "es", "uci_class": "1.Pro",
         "category": "Pro", "start_date": "2026-07-29", "end_date": "2026-07-29"},
        {"name": "Tour du Bout du Monde (fictif)", "country": "FRA", "flag": "fr", "uci_class": "2.1",
         "category": ".1", "start_date": "2026-08-04", "end_date": "2026-08-08"},
        {"name": "Nocturne de Simulation", "country": "FRA", "flag": "fr", "uci_class": "1.1", "category": "FDJ",
         "start_date": "2026-08-15", "end_date": "2026-08-15"},
        {"name": "Vuelta de Prueba", "country": "ESP", "flag": "es", "uci_class": "2.UWT", "category": "WT",
         "start_date": "2026-08-22", "end_date": "2026-09-13"},
        {"name": "Championnats d'Europe (fictifs)", "country": "BEL", "flag": "be", "uci_class": "CC",
         "category": "Champ.", "start_date": "2026-09-20", "end_date": "2026-09-20"}]
    index = {"_fixture": True, "generated_at": "2026-07-11T19:42:00Z", "season": 2026, "races": resumes,
             "upcoming": upcoming, "latest": latest, "fdj_united_series": fdj, "french_wins": wins,
             "notification": {"send": False, "title": "Données fictives", "message": "Jeu de test"}}
    (SORTIE / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(courses)} courses, {len(pel.coureurs)} coureurs sur le Tour de Test -> {SORTIE}")


if __name__ == "__main__":
    main()
