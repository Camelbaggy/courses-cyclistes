#!/usr/bin/env python3
"""Maillots WorldDB (textures Pro Cycling Manager, accord des auteurs) -> `maillots/` publié avec le site.

Les textures d'origine (1200x826, gabarit unique : devant à gauche 134..452 x 0..455, dos à droite, manches en haut, cuissard en bas)
restent dans le dépôt PRIVÉ Camelbaggy/maillots-pcm ; ce script n'en publie qu'une vue de face du buste (sans manches ni cuissard),
en petit (WebP). Il demande Pillow (outil manuel, hors pipeline : la bibliothèque standard ne lit pas le PNG).

    python tools/maillots.py "<dossier Maillots cyclistes>" <equipes/<saison>.json> [--saison 2025] [--sortie maillots]

Fichiers source : `<code>_maillot.png` (équipes, code UCI en minuscules), `<ISO3>_maillot_champion.png` (champions nationaux),
`races/<nom>_maillot_<type>.png` (maillots distinctifs des courses, types time / points / mountain / young…).
Sortie : `equipes/<CODE>.webp`, `nations/<ISO3>.webp`, `courses/<nom>_<type>.webp` et `index.json` :
  {"source": "WorldDB", "saison", "equipes": {CODE: {"nom"?, "slug"?}}, "nations": [ISO3…], "courses": {nom: [types…]}}
`nom` / `slug` = libellé de l'équipe-saison de la saison des maillots portant ce code UCI (unique), à défaut `NOMS_MANUELS`. La page
affiche le maillot d'une équipe-saison de N'IMPORTE QUELLE saison si son libellé a le même slug (même dénomination) et que son
code UCI, quand il est connu, est le même (règle du propriétaire : toute la période de dénomination, tant que le code ne change pas).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import netutil  # noqa: E402
import collector  # noqa: E402

try:
    from PIL import Image, ImageDraw
except ImportError:                     # outil manuel : Pillow requis
    Image = ImageDraw = None

# Codes dont l'équipe-saison n'a pas de code UCI unique dans nos données (anomalie `code_uci_multiple`), validés par le propriétaire.
NOMS_MANUELS = {"GFC": "Groupama-FDJ"}   # GFC = WorldTeam, CGF = équipe continentale (16/11/2026)

# Maillots distinctifs : nom WorldDB -> clés d'épreuve (`collector.cle_edition`, celles de entites/courses/index.json) de TOUTES les dénominations
# de la même course (règle du propriétaire, 17/11/2026 : les maillots restent quand la course change de nom). Table MANUELLE, vérifiée un par un :
# nom, années successives sans chevauchement, et pour les cas non évidents les inscriptions du maillot de leader (Coppi e Bartali, Okolo Slovenska,
# Route d'Occitanie = ex-Route du Sud, CRO Race = Tour of Croatia, Tour of the Alps = ex-Trentino, Renewi Tour = ex-Benelux, Région Pays de la Loire
# Tour = ex-Circuit Sarthe, AlUla Tour = ex-Saudi Tour, Petronas Le Tour de Langkawi = « tourofmalaysia »). Les alias de alias_courses.json sont ajoutés
# automatiquement. Courses non suivies ou douteuses : absentes (ex. Eneco Tour 2026 non relié au Renewi Tour faute de preuve).
COURSES_WORLDDB = {
    "4joursdunkerque": ["4 jours de dunkerque grand prix des hauts de france|FRA", "4 jours de dunkerque tour du nord pas de calais|FRA"],
    "aegean": ["visit south aegean islands|GRE", "south aegean tour|GRE"],
    "articracenorway": ["arctic race of norway|NOR"],
    "beauce": ["tour de beauce|CAN"],
    "beiras": ["grande premio internacional beiras e serra da estrela|POR"],
    "besseges": ["etoile de besseges tour du gard|FRA", "etoile de besseges|FRA"],
    "biya": ["grand prix chantal biya|CMR"],
    "bouclesmayenne": ["boucles de la mayenne credit mutuel|FRA"],
    "bulgaria": ["tour of bulgaria|BUL"],
    "burgos": ["vuelta a burgos|ESP"],
    "circuitardennes": ["circuit des ardennes|FRA", "circuit des ardennes international|FRA"],
    "circuitsarthe": ["region pays de la loire tour|FRA", "circuit cycliste sarthe pays de la loire|FRA"],
    "coppainternazionale": ["settimana internazionale coppi e bartali|ITA"],
    "czechtour": ["czech tour|CZE", "sazka tour|CZE"],
    "dauphinelibere": ["criterium du dauphine|FRA"],
    "deutschlandtour": ["lidl deutschland tour|GER", "deutschland tour|GER"],
    "flechesud": ["fleche du sud|LUX"],
    "giro": ["giro d italia|ITA"],
    "gptorresvedras": ["gp internacional torres vedras trofeu joaquim agostinho|POR"],
    "grancamino": ["o gran camino the historical route|ESP"],
    "hainan": ["tour of hainan|CHN"],
    "hongrie": ["tour de hongrie|HUN"],
    "istrianspringtrophy": ["istrian spring tour|CRO", "istarsko proljece istrian spring trophy|CRO"],
    "kreizbreizh": ["kreiz breizh elites|FRA"],
    "loiretcher": ["tour du loir et cher|FRA", "tour du loir et cher e provost|FRA"],
    "oise": ["ronde de l oise|FRA"],
    "okolo": ["okolo slovenska tour de slovaquie|SVK", "tour de slovaquie|SVK"],
    "olympiastour": ["olympia s tour|NED"],
    "parisnice": ["paris nice|FRA"],
    "qinghai": ["tour of magnificent qinghai|CHN", "tour of qinghai lake|CHN"],
    "rhalpesisere": ["alpes isere tour|FRA", "rhone alpes isere tour|FRA"],
    "rhodestour": ["tour of rhodes powered by rodos palace|GRE", "international tour of rhodes|GRE"],
    "routealsace": ["tour alsace|FRA", "tour d alsace|FRA"],
    "routelimousin": ["tour du limousin nouvelle aquitaine|FRA", "tour du limousin|FRA"],
    "rwanda": ["tour du rwanda|RWA"],
    "sauditour": ["alula tour|KSA", "saudi tour|KSA"],
    "sharjah": ["tour of sharjah|UAE", "sharjah tour|UAE"],
    "taiwan": ["tour de taiwan|TPE"],
    "thailand": ["the princess maha chakri sirindhorn s cup tour of thailand|THA", "the princess maha chakri sirindhorns cup tour of thailand|THA",
                 "the princess maha chackri sirindhorn s cup tour of thailand|THA"],
    "tirrenoadriatico": ["tirreno adriatico|ITA"],
    "tour": ["tour de france|FRA"],
    "tourbelgique": ["baloise belgium tour|BEL"],
    "tourbretagne": ["le tour de bretagne cycliste|FRA"],
    "tourcroatia": ["cro race|CRO", "tour of croatia|CRO"],
    "tourdecatalogne": ["volta ciclista a catalunya|ESP"],
    "tourderomandie": ["tour de romandie|SUI"],
    "tourdesuisse": ["tour de suisse|SUI"],
    "tourdubenelux": ["renewi tour|BEL"],
    "tourdudanemark": ["postnord tour of denmark|DEN", "postnord danmark rundt tour of denmark|DEN"],
    "tourduportugal": ["volta a portugal em bicicleta|POR", "volta a portugal santander|POR", "volta a portugal em bicicleta edicao especial|POR"],
    "tourdusud": ["la route d occitanie la depeche du midi|FRA", "route d occitanie|FRA", "route du sud la depeche du midi|FRA"],
    "tourlaprovence": ["tour de la provence|FRA", "tour cycliste international la provence|FRA"],
    "tourluxembourg": ["skoda tour de luxembourg|LUX", "skoda tour luxembourg|LUX"],
    "tourofbritain": ["lloyds bank tour of britain men|GBR", "tour of britain|GBR", "ovo energy tour of britain|GBR", "lloyds tour of britain men|GBR"],
    "tourofguangxi": ["tour of guangxi|CHN", "gree tour of guangxi|CHN"],
    "tourofiran": ["tour of iran azarbaijan|IRI"],
    "tourofmalaysia": ["petronas le tour de langkawi|MAS", "le tour de langkawi|MAS"],
    "tourofnorway": ["tour of norway|NOR"],
    "tourofoman": ["tour of oman|OMA"],
    "tourofturkey": ["presidential cycling tour of turkiye|TUR", "presidential cycling tour of turkey|TUR"],
    "tourpaysbasque": ["itzulia basque country|ESP", "vuelta ciclista al pais vasco|ESP"],
    "tourpologne": ["tour de pologne|POL"],
    "tourslovenia": ["tour of slovenia|SLO"],
    "tpoitoucharentes": ["tour poitou charentes en nouvelle aquitaine|FRA", "tour du poitou charentes charente charente maritime deux sevres vienne|FRA",
                         "tpc en nouvelle aquitaine|FRA"],
    "trentino": ["tour of the alps|ITA"],
    "uaetour": ["uae tour|UAE"],
    "voltaalgarve": ["volta ao algarve em bicicleta|POR", "volta ao algarve cofidis|POR"],
    "voltavalenciana": ["volta a la comunitat valenciana|ESP", "volta comunitat valenciana|ESP"],
    "vuelta": ["la vuelta ciclista a espana|ESP"],
    "vueltaandalucia": ["vuelta a andalucia ruta ciclista del sol|ESP"],
    "vueltaasturias": ["vuelta asturias julio alvarez mendo|ESP"],
}
TYPES_COURSE = {"time": "gc", "points": "points", "mountain": "mountain", "young": "youth"}   # type WorldDB -> classement

ZONE_AVANT = (134, 0, 452, 400)          # panneau avant, coupé avant le bas du maillot
SILHOUETTE = [(100, 0), (159, 28), (218, 0), (276, 14), (292, 34), (288, 110), (296, 170), (306, 400), (12, 400), (22, 170),
              (30, 110), (26, 34), (42, 14)]
HAUTEUR = 160                            # px (affiché à ~38 px dans la liste, ~120 px dans l'infobox des articles d'équipe)
SUR = 4


def buste(chemin):
    src = Image.open(chemin).convert("RGBA")
    if src.size != (1200, 826):
        raise ValueError(f"gabarit inattendu {src.size}")
    p = src.crop(ZONE_AVANT)
    m = Image.new("L", (p.width * SUR, p.height * SUR), 0)
    ImageDraw.Draw(m).polygon([(x * SUR, y * SUR) for x, y in SILHOUETTE], fill=255)
    p.putalpha(m.resize(p.size, Image.LANCZOS))
    p = p.crop(p.getbbox())
    return p.resize((round(p.width * HAUTEUR / p.height), HAUTEUR), Image.LANCZOS)


def ecrire(im, chemin):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    im.save(chemin, "WEBP", quality=82, method=6)


def noms_par_code(equipes):
    par = {}
    for e in equipes.values():
        c = e.get("code_uci")
        if c and not e.get("nationale"):
            par.setdefault(c, set()).add(e["name"])
    out = {c: next(iter(n)) for c, n in par.items() if len(n) == 1}
    out.update(NOMS_MANUELS)
    return out


def epreuves(chemin_index, courses, erreurs):
    """Clés d'édition BRUTES (toutes les dénominations de la course + sources d'alias_courses.json pointant vers elles) -> nom WorldDB, et clé
    canonique -> nom WorldDB (page épreuve). `chemin_index` = entites/courses/index.json (clés d'épreuve existantes, pour valider la table)."""
    with open(chemin_index, encoding="utf-8") as f:
        connues = {c["k"] for c in json.load(f)}
    alias = collector.charger_alias(collector.ALIAS_COURSES)
    brut, canon = {}, {}
    for w, cles in sorted(COURSES_WORLDDB.items()):
        if w not in courses:
            erreurs.append(f"course WorldDB absente : {w}")
            continue
        for k in cles:
            if k not in connues and k not in alias:
                erreurs.append(f"clé d'épreuve inconnue pour {w} : {k}")
                continue
            for b in [k] + [s for s, c in alias.items() if c == k]:
                if brut.get(b, w) != w:
                    erreurs.append(f"clé {b} reliée à deux maillots : {brut[b]} et {w}")
                brut[b] = w
            canon[alias.get(k, k)] = w
    return brut, canon


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source")
    ap.add_argument("equipes", help="entites/equipes/<saison>.json de la saison des maillots")
    ap.add_argument("--saison", type=int, default=2025)
    ap.add_argument("--sortie", default="maillots")
    ap.add_argument("--courses", help="entites/courses/index.json (clés d'épreuve, pour valider COURSES_WORLDDB)")
    a = ap.parse_args()
    if Image is None:
        sys.exit("Pillow requis (pip install pillow)")
    with open(a.equipes, encoding="utf-8") as f:
        noms = noms_par_code(json.load(f))
    idx = {"source": "WorldDB", "saison": a.saison, "equipes": {}, "nations": [], "courses": {}}
    erreurs = []
    for nom in sorted(os.listdir(a.source)):
        chemin = os.path.join(a.source, nom)
        m_eq = re.fullmatch(r"([a-z0-9]{3})_maillot\.png", nom)
        m_na = re.fullmatch(r"([A-Z]{3})_maillot_champion\.png", nom)
        try:
            if m_eq:
                code = m_eq.group(1).upper()
                ecrire(buste(chemin), os.path.join(a.sortie, "equipes", f"{code}.webp"))
                n = noms.get(code)
                idx["equipes"][code] = {"nom": n, "slug": netutil.slugify(n)} if n else {}
            elif m_na:
                ecrire(buste(chemin), os.path.join(a.sortie, "nations", f"{m_na.group(1)}.webp"))
                idx["nations"].append(m_na.group(1))
        except Exception as e:  # noqa: BLE001
            erreurs.append(f"{nom} : {e}")
    dossier_courses = os.path.join(a.source, "races")
    for nom in sorted(os.listdir(dossier_courses)) if os.path.isdir(dossier_courses) else []:
        m = re.fullmatch(r"([a-z0-9]+)_maillot_([a-z]+)\.png", nom)
        if not m:
            continue
        try:
            ecrire(buste(os.path.join(dossier_courses, nom)), os.path.join(a.sortie, "courses", f"{m.group(1)}_{m.group(2)}.webp"))
            idx["courses"].setdefault(m.group(1), []).append(m.group(2))
        except Exception as e:  # noqa: BLE001
            erreurs.append(f"races/{nom} : {e}")
    if a.courses:
        idx["epreuves"], idx["epreuves_canon"] = epreuves(a.courses, idx["courses"], erreurs)
    with open(os.path.join(a.sortie, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    relies = sum(1 for v in idx["equipes"].values() if v)
    print(f"[MAILLOTS] {len(idx['equipes'])} équipes ({relies} reliées à une équipe-saison {a.saison}), {len(idx['nations'])} nations, "
          f"{sum(len(v) for v in idx['courses'].values())} maillots de {len(idx['courses'])} courses ; {len(erreurs)} erreur(s)")
    for e in erreurs:
        print("  [WARN]", e)


if __name__ == "__main__":
    main()
