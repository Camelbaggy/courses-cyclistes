#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CQ Ranking (cqranking.com) : résultats de courses sur route hommes 1999-2008 et fiches coureurs (collecteur, étape 1 :
pas d'intégration).

ACCORD : le 18/11/2026, CQ Ranking a donné au propriétaire du projet son accord pour lire le site par programme et
afficher ses données, avec le crédit « CQ Ranking ». Pas de robots.txt (404). Politesse : User-Agent honnête
« courses-cyclistes (accord CQ Ranking) », >= 2,5 s entre deux requêtes (`PAUSE_S` 2,6), aucune page demandée deux fois
(chaque page lue est écrite sur disque ; `--relire` pour forcer). Hommes seulement (`/men/`).

Pourquoi cette source : seule source trouvée avec, pour chaque coureur, la DATE DE NAISSANCE COMPLÈTE et (souvent) l'ID UCI
(fiche `rider.asp?riderid=N`), sur les saisons 1999-2008 : elle sert d'abord à IDENTIFIER les coureurs de ces années (les
classements de the-sports.org et de Wikipédia n'ont pas de naissance), ensuite à compléter les résultats des courses UCI
(classements limités aux places utiles : voir la profondeur dans docs/recherche/cqranking_collecte.md).

Structure du site (constatée le 18/11/2026) — pages ASP sous `https://cqranking.com/men/asp/gen/`, jamais devinées :
  - `RaceCal.asp?year=AAAA&month=M` : calendrier d'UN mois (liens « < octobre », « décembre > » et formulaire year / month) ;
    tableau Nbr | début | fin | catégorie | pays (drapeau) | nom (lien `race.asp?raceid=N`) | « Stages »
    (lien `tour.asp?tourid=N`, courses par étapes seulement). Une saison = 12 requêtes. Avant 1999 le calendrier ne
    contient que les Coupes du monde et quelques courses HC ; c'est de 1999 que la base est complète.
  - `race.asp?raceid=N` : un classement (course d'un jour, étape, général, annexe). Catégorie en en-tête (`Category: 1.1`) :
    suffixe `s` = étape (`2.1s`, `GT1s`), `r` = classement annexe (`GT1r` : points, montagne…), sinon course d'un jour ou
    général. Tableau Rank | pays | coureur (lien `rider.asp?riderid=N`) | équipe (code, lien `team.asp?year&teamcode`) |
    Time (ou Points) | CQ (points CQ). Contre-la-montre par équipes : lignes d'équipe + liste des coureurs + « Late arrivals ».
  - `tour.asp?tourid=N` : toutes les étapes d'une course par étapes (date jj/mm, libellé, lien `race.asp?raceid=N`, vainqueur),
    puis général, points, montagne… (chacun avec son raceid).
  - `rider.asp?riderid=N` : fiche (nom, drapeau, `jj/mm/aaaa`, `UCI ID: …` quand il existe, statut, équipes par année).
  - `downloads.asp` : archives hebdomadaires `cqAAAAMMJJ.zip` = CLASSEMENTS CQ (xls BIFF binaire, 2007->) : inutiles ici
    (pas de résultats de course, format non lisible en bibliothèque standard). Les pages HTML suffisent.
  Les pages sont en ISO-8859-1 sans jeu de caractères annoncé : décodage forcé en cp1252 (`netutil.fetch_text(encoding=…)`).

Règle cardinale du projet : aucune valeur inventée. Une valeur absente reste absente ; un format inconnu est conservé brut
et compté dans la synthèse.

Interprétation des temps (documentée, déterministe) — vérifiée sur des courses réelles (Milan-San Remo 2005 : Petacchi
7h11'39" puis Hondo, même temps, cellule vide ; Tour de France 2005 : Basso +4'40") :
  - la colonne `Time` du 1er est un temps ABSOLU ; celle des suivants est un ÉCART au 1er (jamais à la ligne précédente :
    trois coureurs du même groupe affichent tous `12"`) ; cellule vide chez un coureur de rang >= 2 = même temps que le 1er
    (écart 0, la cellule vide reste visible dans `brut`) ;
  - formats : `4h19'41"` `1h10'39"` `04'40"` `06"` ; autre format : `ecart_s` absent et compté (`temps_illisibles`) ;
  - classement « Points » (annexe) : `brut` = points du classement, pas de temps ; lignes « Late arrivals » d'un
    contre-la-montre par équipes (rang `-`) : `brut` seul, jamais interprété (référence incertaine).
Colonnes d'un fichier course : `lignes: [[rang, coureur, nat, equipe, brut, ecart_s, points_cq]]` (valeurs absentes = null) ;
`temps_s` du fichier = temps absolu du 1er, `noms` = {id coureur: nom tel qu'affiché}.

Fiches coureurs : une requête par coureur lu dans un classement collecté, du plus notable (meilleur rang, puis le plus
fréquent) au moins notable, jamais relue sans `--relire`. `coureurs.json` = {id CQ: {nom, nom_famille, prenom, naissance
AAAA-MM-JJ (date COMPLÈTE seulement), nationalite (code UCI du site, gardé brut ; `pays.pays_normalise(code, "cqranking")` donne le code canonique de pays_historiques.json : AHO, SCG… en code d'époque, ANT -> ATG), uci_id, statut, marque_nom ("*" final du nom affiché, sens non documenté), equipes [[année, code]], url, lu_le}} ;
une fiche sans date reconnue n'a pas de `naissance` (comptée, exemples dans `formats_date_inconnus`). `nom_famille` / `prenom`
= découpe déterministe du nom affiché (« DE MAAR Marc » : jetons tout en majuscules d'abord). `equipes.json` =
{année: {code équipe: nom}} lu sur les fiches.

Sortie (défaut `ARCHIVES_DIR/sources/cqranking/`) : `calendrier/<année>.json`, `courses/<année>/<raceid>.json`,
`tours/<tourid>.json`, `coureurs.json`, `equipes.json`, `etat.json` (`{"termine", "calendriers_restants",
"pages_restantes", "coureurs_restants"}`, sans horodatage : lu par un workflow d'auto-relance, comme thesports).

    python cqranking.py --sortie DOSSIER [--avant 2009] [--depuis AAAA] [--relire] [--budget-min N] [--max-requetes N]
                        [--decouverte-seule] [--sans-fiches] [--sans-etapes] [--max-courses N] [--courses roubaix,1821]
                        [--garder-html]
    python cqranking.py --test            # tests sans réseau (pages réelles allégées de tools/fixtures/cqranking/)
"""
import argparse
import datetime
import gzip
import hashlib
import html as _html
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import netutil
from pays import pays_normalise

BASE = "https://cqranking.com/men/asp/gen/"
USER_AGENT = "courses-cyclistes (accord CQ Ranking)"
HOTE = "cqranking.com"
PAUSE_S = 2.6                      # >= 2,5 s entre deux requêtes (accord du 18/11/2026)
netutil.HOST_DELAYS[HOTE] = PAUSE_S
ENCODAGE = "cp1252"                # pages ISO-8859-1 sans charset annoncé (cp1252 = sur-ensemble utilisé par les navigateurs)

AVANT_DEFAUT = 2009                # saisons <= 2008
DEPUIS_DEFAUT = 1999               # début de la base complète (mesuré : avant, seulement Coupes du monde / HC)
ARCHIVES_DIR = os.environ.get("ARCHIVES_DIR") or os.path.join("data", "archives")
SORTIE_DEFAUT = os.path.join(ARCHIVES_DIR, "sources", "cqranking")
RACINE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(RACINE, "tools", "fixtures", "cqranking")
ECHECS_MAX = 3                     # une fiche absente (404) ou sans titre 3 jours différents n'est plus redemandée (rien d'inventé)
# Règle de comptage (voir thesports.REGLE_ECHECS) : une panne (réseau, 5xx, site abandonné) ne note rien, au plus un échec par fiche et
# par jour ; une entrée d'échec sans `regle` ou de règle plus ancienne est re-tentée, compteur remis à 0.
REGLE_ECHECS = 2


# --------------------------------------------------------------------------------------------------
# Lecture des pages (fonctions pures)
# --------------------------------------------------------------------------------------------------

def _txt(fragment: str) -> str:
    """Texte brut d'un fragment HTML (balises ôtées, entités décodées, espaces insécables et multiples réduits)."""
    t = re.sub(r"(?s)<!--.*?-->", "", fragment)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    return " ".join(t.split())


def _cellules(tr: str) -> List[str]:
    return re.findall(r"(?s)<td[^>]*>(.*?)</td>", tr)


def _corps(page: str) -> str:
    i = page.find("<!--BODY-->")
    return page[i:] if i >= 0 else page


def date_iso(texte: str) -> Optional[str]:
    """`1/04/2005` (jj/mm/aaaa, jour sans zéro possible) -> `2005-04-01` ; date impossible ou autre format : None."""
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*", texte or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def parse_duree(brut: str) -> Tuple[str, Optional[int]]:
    """Durée du site (`4h19'41"`, `1h10'39"`, `04'40"`, `06"`) -> ("valeur", secondes) ; "" -> ("vide", None) ; autre -> ("illisible", None)."""
    b = (brut or "").strip()
    if not b:
        return "vide", None
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d{1,2})')?(?:(\d{1,2})\")?", b)
    if not m or not any(m.groups()):
        return "illisible", None
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    if mi >= 60 or s >= 60:
        return "illisible", None
    return "valeur", h * 3600 + mi * 60 + s


def lire_calendrier(page: str) -> Tuple[Optional[int], List[Dict[str, Any]]]:
    """Calendrier d'un mois -> (nombre annoncé « Number of results found: N », courses). Colonnes lues par position (le
    texte des cellules vides ne décale rien) : 3 début, 5 fin, 7 catégorie, 9 pays (drapeau), 11 nom + raceid, 13 tourid."""
    m = re.search(r"Number of results found:\s*(\d+)", page)
    attendu = int(m.group(1)) if m else None
    out: List[Dict[str, Any]] = []
    debut = page.find("Number of results found")
    if debut < 0:
        return attendu, out
    for tr in re.findall(r"(?s)<tr>.*?</tr>", page[debut:]):
        c = _cellules(tr)
        lien = re.search(r"race\.asp\?raceid=(\d+)", tr)
        if len(c) < 14 or not lien or not re.fullmatch(r"\d+", _txt(c[1])):
            continue
        tour = re.search(r"tour\.asp\?tourid=(\d+)", c[13])
        pays = re.search(r"flags/(\w+)\.gif", c[9])
        course = {"id": int(lien.group(1)), "nom": _txt(c[11]), "categorie": _txt(c[7]) or None,
                  "pays": pays.group(1).upper() if pays else None, "debut": date_iso(_txt(c[3])),
                  "fin": date_iso(_txt(c[5])), "tour": int(tour.group(1)) if tour else None}
        out.append({k: v for k, v in course.items() if v is not None})
    return attendu, out


def _entete(corps: str) -> Dict[str, Any]:
    """Titre, pays, dates, catégorie d'une page course / tour (zone avant « Category: »)."""
    cat = re.search(r"Category:\s*([^<\n]+)", corps)
    zone = corps[:cat.start()] if cat else corps[:3000]
    titre = None
    for th in re.findall(r"(?s)<th[^>]*class=\"?raceheader\"?[^>]*>(.*?)</th>", zone):
        t = _txt(th)
        if re.search(r"[A-Za-z]", t):
            titre = t
            break
    pays = re.search(r"flags/(\w+)\.gif", zone)
    dates = [d for d in (date_iso(x) for x in re.findall(r"\d{1,2}/\d{1,2}/\d{4}", zone)) if d]
    out: Dict[str, Any] = {}
    if titre:
        out["titre"] = titre
        km = re.search(r"\(([\d]+(?:[.,]\d+)?)\s*km\)\s*$", titre)
        if km:
            out["km"] = float(km.group(1).replace(",", "."))
    if pays:
        out["pays"] = pays.group(1).upper()
    if dates:
        out["debut"], out["fin"] = dates[0], dates[-1]
    if cat:
        out["categorie"] = _txt(cat.group(1))
    return out


def type_classement(categorie: Optional[str], tour: Optional[int]) -> str:
    """Suffixe minuscule après une majuscule / un chiffre : `s` = `etape` (`2.1s`, `GT1s`), `r` = `annexe` (`GT1r` : points,
    montagne…) ; sinon `general` (page d'une course par étapes) ou `jour` (course d'un jour)."""
    m = re.search(r"[A-Z0-9]([sr])$", categorie or "")
    if m:
        return "etape" if m.group(1) == "s" else "annexe"
    return "general" if tour else "jour"


def lire_tour(page: str) -> Dict[str, Any]:
    """Page `tour.asp` : en-tête + liste des classements (étapes, général, annexes) avec leur raceid et leur vainqueur."""
    corps = _corps(page)
    out = _entete(corps)
    annee = int(out["debut"][:4]) if out.get("debut") else None
    etapes: List[Dict[str, Any]] = []
    zone = corps[corps.find("Results</th>"):] if "Results</th>" in corps else ""
    for tr in re.findall(r"(?s)<tr>.*?</tr>", zone):
        lien = re.search(r"race\.asp\?raceid=(\d+)>?\"?>([^<]*)", tr)
        if not lien:
            continue
        c = _cellules(tr)
        e: Dict[str, Any] = {"id": int(lien.group(1)), "libelle": _txt(lien.group(2))}
        jm = re.fullmatch(r"(\d{1,2})/(\d{1,2})", _txt(c[1])) if len(c) > 1 else None
        if jm and annee:
            mois, jour = int(jm.group(2)), int(jm.group(1))
            a = annee + (1 if out.get("debut") and mois < int(out["debut"][5:7]) else 0)   # course à cheval sur deux années
            try:
                e["date"] = datetime.date(a, mois, jour).isoformat()
            except ValueError:
                pass
        gagnant = re.search(r"rider\.asp\?riderid=(\d+)>?\"?>([^<]*)", tr)
        if gagnant:
            e["vainqueur"] = {"id": int(gagnant.group(1)), "nom": _txt(gagnant.group(2))}
        elif len(c) > 11 and _txt(c[11]):
            e["vainqueur_equipe"] = _txt(c[11])
        etapes.append(e)
    out["etapes"] = etapes
    return out


def _ligne(tr: str) -> Optional[Dict[str, Any]]:
    """Ligne individuelle d'un classement. Positions relatives à la cellule du coureur : équipe à +2, valeur (temps ou
    points) à +4, points CQ à +6 (13 cellules : coureur en 5 ; ligne « Late arrivals » : 3). Dans les petites courses
    l'équipe est un simple « - » sans lien : `equipe` absent (compté par l'appelant via `equipe` None)."""
    c = _cellules(tr)
    k = next((i for i, x in enumerate(c) if re.search(r"rider\.asp\?riderid=\d+", x)), None)
    if k is None:
        return None
    rider = re.search(r"rider\.asp\?riderid=(\d+)>?\"?>([^<]*)</a>", c[k])
    rang_txt = next((_txt(x) for x in c[:k] if re.fullmatch(r"\d+\.|-", _txt(x))), None)
    if not rider or rang_txt is None:
        return None                                    # ligne « leader » (maillot) ou autre : pas un classé
    nat = re.search(r"flags/(\w+)\.gif", tr)
    eq = re.search(r"teamcode=([^\"'>\s&]+)", c[k + 2]) if len(c) > k + 2 else None
    equipe = eq.group(1) if eq else None
    brut = _txt(c[k + 4]) if len(c) > k + 4 else None
    cq = _txt(c[k + 6]) if len(c) > k + 6 else ""
    return {"rang": int(rang_txt[:-1]) if rang_txt != "-" else None, "coureur": int(rider.group(1)),
            "nom": _txt(rider.group(2)), "nat": nat.group(1).upper() if nat else None, "equipe": equipe,
            "brut": brut, "points_cq": int(cq) if re.fullmatch(r"-?\d+", cq) else None}


def lire_course(page: str) -> Dict[str, Any]:
    """Page `race.asp` -> {titre, pays, debut, fin, categorie, km, type, tour, colonne ("temps" / "points" / "equipes"),
    temps_s, noms, lignes [[rang, coureur, nat, equipe, brut, ecart_s, points_cq]], stats}. Voir le docstring du module."""
    corps = _corps(page)
    out: Dict[str, Any] = _entete(corps)
    tour = re.search(r"tour\.asp\?tourid=(\d+)", corps)
    out["tour"] = int(tour.group(1)) if tour else None
    out["type"] = type_classement(out.get("categorie"), out["tour"])
    stats = {"lignes": 0, "lignes_illisibles": 0, "temps_illisibles": 0, "temps_vides": 0, "late": 0, "sans_equipe": 0}
    i = corps.find(">Rank<")
    zone = corps[i:] if i >= 0 else ""
    entetes = [_txt(h) for h in re.findall(r"(?s)<th[^>]*class=\"?tabheader\"?[^>]*>(.*?)</th>", corps[i:i + 2500] if i >= 0 else "")]
    equipes = "Team" in entetes and "Rider" not in entetes
    colonne = "equipes" if equipes else ("points" if "Points" in entetes else "temps" if "Time" in entetes else "inconnue")
    out["colonne"] = colonne
    noms: Dict[str, str] = {}
    lignes: List[List[Any]] = []
    teams: List[Dict[str, Any]] = []
    tardives: List[List[Any]] = []
    premier = True
    for tr in re.findall(r"(?s)<tr>.*?</tr>", zone):
        txt = _txt(tr)
        if equipes:
            eq = re.search(r"teamcode=([^\"'>\s&]+)", tr)
            if "rider.asp" in tr and not re.search(r"<i>\s*<a", tr):                  # coureur en retard (rang « - »)
                lg = _ligne(tr)
                if lg:
                    stats["late"] += 1
                    noms[str(lg["coureur"])] = lg["nom"]
                    tardives.append([None, lg["coureur"], lg["nat"], lg["equipe"], lg["brut"], None, lg["points_cq"]])
                continue
            rang = re.search(r"(?s)<td[^>]*>\s*(\d+)\.\s*</td>", tr)
            if rang and eq and "rider.asp" not in tr:                                 # ligne d'équipe
                cs = _cellules(tr)
                nom_eq = re.search(r"<!--\s*,\s*([^,]+),\s*([^>]*?)\s*-->", tr)
                brut = _txt(cs[5]) if len(cs) > 5 else ""
                cq = _txt(cs[7]) if len(cs) > 7 else ""
                etat, sec = parse_duree(brut)
                t: Dict[str, Any] = {"rang": int(rang.group(1)), "equipe": nom_eq.group(1).strip() if nom_eq else eq.group(1),
                                     "nom": nom_eq.group(2).strip() if nom_eq else _txt(cs[3]) if len(cs) > 3 else None,
                                     "brut": brut, "points_cq": int(cq) if re.fullmatch(r"-?\d+", cq) else None,
                                     "coureurs": []}
                if etat == "valeur":
                    if premier:
                        out["temps_s"] = sec
                        t["ecart_s"] = 0
                    else:
                        t["ecart_s"] = sec
                elif etat == "vide" and not premier:
                    t["ecart_s"] = 0
                    stats["temps_vides"] += 1
                elif etat == "illisible":
                    stats["temps_illisibles"] += 1
                premier = False
                teams.append(t)
                stats["lignes"] += 1
                continue
            ids = re.findall(r"<i>\s*<a href=\"?rider\.asp\?riderid=(\d+)\"?>([^<]*)</a>", tr)
            if ids and teams and "leader" not in txt:
                for rid, nom in ids:
                    teams[-1]["coureurs"].append(int(rid))
                    noms[rid] = _txt(nom)
            continue
        lg = _ligne(tr)
        if lg is None:
            continue
        stats["lignes"] += 1
        stats["sans_equipe"] += 1 if lg["equipe"] is None else 0
        noms[str(lg["coureur"])] = lg["nom"]
        ecart: Optional[int] = None
        if colonne == "temps":
            etat, sec = parse_duree(lg["brut"] or "")
            if etat == "valeur":
                if lg["rang"] == 1 and premier:
                    out["temps_s"] = sec
                    ecart = 0
                elif not premier:
                    ecart = sec
            elif etat == "vide" and not premier and lg["rang"] is not None:
                ecart = 0                                  # cellule vide = même temps que le 1er (voir le docstring)
                stats["temps_vides"] += 1
            elif etat == "illisible":
                stats["temps_illisibles"] += 1
            elif etat == "vide" and premier:
                ecart = 0
        if lg["brut"] is None:
            stats["lignes_illisibles"] += 1
        premier = False
        lignes.append([lg["rang"], lg["coureur"], lg["nat"], lg["equipe"], lg["brut"], ecart, lg["points_cq"]])
    if equipes:
        out["equipes"] = teams
        if tardives:
            out["arrivees_tardives"] = tardives
    else:
        out["lignes"] = lignes
    com = re.search(r"(?s)<a name=\"?RaceComments\"?></a>.*?<tr>\s*<td[^>]*>&nbsp;</td>\s*<td[^>]*>(.*?)</td>", corps)
    if com and _txt(com.group(1)):
        out["commentaire"] = _txt(com.group(1))           # ex. « Stage race was cancelled due to bad weather. »
    out["noms"] = noms
    out["stats"] = stats
    return out


def nom_famille_prenom(nom: str) -> Tuple[str, str]:
    """« DE MAAR Marc » -> ("DE MAAR", "Marc") : les jetons tout en majuscules d'abord forment le nom de famille, le reste
    le prénom ; un nom sans jeton en majuscules reste entier en nom de famille. Découpe déterministe, pas une identité."""
    jetons = nom.split()
    i = 0
    while i < len(jetons) and jetons[i].upper() == jetons[i] and any(ch.isalpha() for ch in jetons[i]):
        i += 1
    if i == 0 or i == len(jetons) and i == 1:
        return nom, ""
    return " ".join(jetons[:i]), " ".join(jetons[i:])


def parse_naissance(texte: str) -> Optional[str]:
    """`15/08/1974` (jj/mm/aaaa COMPLÈTE et possible) -> `1974-08-15` ; tout autre format : None."""
    return date_iso(texte)


def lire_fiche(page: str) -> Tuple[Dict[str, Any], str, str]:
    """Fiche `rider.asp` -> (fiche, statut, brut). Statut : "jour" (naissance complète), "inconnu" (une date d'allure
    différente est écrite : conservée dans `brut`, pas de naissance), "absent" (pas de date). La fiche est vide si le titre manque."""
    corps = _corps(page)
    i = max(corps.find("raceheader") - 7, -1)
    if i < 0:
        return {}, "absent", ""
    zone = corps[i:i + 8000]
    nom_m = re.search(r"(?s)class=\"?raceheader\"?[^>]*>\s*<b>(.*?)</b>", zone)
    nom = _txt(nom_m.group(1)) if nom_m else ""
    if not nom:
        return {}, "absent", ""
    out: Dict[str, Any] = {"nom": nom}
    if nom.endswith("*"):                          # « DI LUCA Danilo* » : marque ajoutée par le site, sens non documenté (conservée)
        out["marque_nom"] = "*"
    out["nom_famille"], out["prenom"] = nom_famille_prenom(nom.rstrip("*").strip())
    nat = re.search(r"flags/(\w+)\.gif", nom_m.group(1)) if nom_m else None
    if nat:
        out["nationalite"] = nat.group(1).upper()
    suite = zone[nom_m.end():] if nom_m else zone
    fin_id = suite.find("Current CQ-value")
    ident = suite[:fin_id] if fin_id > 0 else suite[:1500]
    gras = [_txt(x) for x in re.findall(r"(?s)<b>(.*?)</b>", ident)]
    statut, brut = "absent", ""
    for g in gras:
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", g):
            d = parse_naissance(g)
            if d:
                out["naissance"], statut, brut = d, "jour", g
            else:
                statut, brut = "inconnu", g
            break
        if re.fullmatch(r"[\d/.\- ]{4,}", g) and statut == "absent":
            statut, brut = "inconnu", g
    uci = re.search(r"UCI\s*ID:\s*(\d+)", _txt(ident))
    if uci:
        out["uci_id"] = uci.group(1)
    for g in gras:
        if re.fullmatch(r"[A-Za-z][A-Za-z ]{2,30}", g) and not g.startswith("UCI"):
            out["statut"] = g
            break
    equipes = []
    for m in re.finditer(r"(?s)<td\s+class=tabrow\d\s+align=left>(\d{4})</td>(?:(?!</tr>).)*?teamcode=([^\"'>\s&]+)[^>]*>([^<]*)</a>", corps):
        equipes.append([int(m.group(1)), m.group(2), _txt(m.group(3))])
    if equipes:
        out["equipes"] = equipes
    return out, statut, brut[:80]


# --------------------------------------------------------------------------------------------------
# Réseau, stockage, reprise
# --------------------------------------------------------------------------------------------------

class Session:
    """Requêtes polies (pause par hôte, budget, compteur). Par défaut aucun cache HTML : chaque page lue est écrite en JSON.
    `garder_html` : chaque page est aussi gardée (gzip, `cache/`) et relue sans requête (corriger l'analyseur sans retélécharger)."""

    def __init__(self, sortie: str, budget_min: float = 0.0, max_pages: int = 0, garder_html: bool = False):
        self.sortie = sortie
        self.garder_html = garder_html
        self.t0 = time.monotonic()
        self.budget_s = budget_min * 60 if budget_min else 0.0
        self.max_pages = max_pages
        self.requetes = 0
        self.echecs = 0
        self.absente = False        # dernière page demandée : 404 / 410 (vrai échec) ; faux = lue, ou panne passagère
        self.dernier_journal = self.t0

    def epuise(self, fraction: float = 1.0) -> bool:
        """Budget de temps (ou plafond de requêtes) atteint ; `fraction` < 1 : seulement cette part du budget de temps."""
        if self.budget_s and time.monotonic() - self.t0 >= self.budget_s * fraction:
            return True
        return bool(self.max_pages) and self.requetes >= self.max_pages

    def page(self, rel: str) -> Optional[str]:
        url = rel if rel.startswith("http") else BASE + rel
        chemin = os.path.join(self.sortie, "cache", hashlib.sha1(url.encode()).hexdigest()[:16] + ".html.gz")
        if self.garder_html and os.path.exists(chemin):
            with gzip.open(chemin, "rt", encoding="utf-8") as f:
                return f.read()
        self.absente = False
        if self.epuise():
            return None
        self.requetes += 1
        texte = netutil.fetch_text(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, encoding=ENCODAGE)
        if texte is None:
            self.echecs += 1
            self.absente = netutil.page_absente()
        elif self.garder_html:
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            with gzip.open(chemin, "wt", encoding="utf-8") as f:
                f.write(texte)
        return texte

    def journal(self, message: str, force: bool = False) -> None:
        if force or time.monotonic() - self.dernier_journal >= 300:
            self.dernier_journal = time.monotonic()
            print("[CQRANKING] %s (%d requêtes, %.1f min)" % (message, self.requetes, (time.monotonic() - self.t0) / 60))


def _ecrire_json(chemin: str, obj: Any, compact: bool = False) -> None:
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, chemin)


def _lire_json(chemin: str, defaut: Any) -> Any:
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def _maintenant() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def chemin_course(sortie: str, annee: int, rid: int) -> str:
    return os.path.join(sortie, "courses", str(annee), "%d.json" % rid)


def chemin_tour(sortie: str, tid: int) -> str:
    return os.path.join(sortie, "tours", "%d.json" % tid)


def lire_calendriers(sess: Session, annee: int, relire: bool, resume: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """Lit (et écrit) les mois d'une saison encore absents ; retourne (calendrier de l'année, mois restants). Un mois du
    futur n'est pas lu ; un mois lu est figé (`relire` pour le relire)."""
    chemin = os.path.join(sess.sortie, "calendrier", "%d.json" % annee)
    cal = _lire_json(chemin, {"annee": annee, "mois": {}})
    auj = datetime.date.today()
    for mois in range(1, 13):
        if (str(mois) in cal["mois"] and not relire) or (annee, mois) > (auj.year, auj.month):
            continue
        page = sess.page("RaceCal.asp?year=%d&month=%d" % (annee, mois))
        if page is None:
            continue
        attendu, courses = lire_calendrier(page)
        resume["calendriers"] += 1
        if attendu is None or attendu != len(courses):
            resume["calendriers_incoherents"] = resume.get("calendriers_incoherents", 0) + 1
            print("[CQRANKING] [WARN] %d-%02d : %s courses annoncées, %d lues" % (annee, mois, attendu, len(courses)))
        cal["mois"][str(mois)] = {"attendu": attendu, "courses": courses}
        _ecrire_json(chemin, cal, compact=True)
    restants = sum(1 for mois in range(1, 13) if str(mois) not in cal["mois"] and (annee, mois) <= (auj.year, auj.month))
    return cal, restants


def courses_du_calendrier(cal: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Courses du calendrier d'une saison, dédoublonnées par raceid, par date de début."""
    vu: Dict[int, Dict[str, Any]] = {}
    for mois in sorted(cal.get("mois", {}), key=int):
        for c in cal["mois"][mois]["courses"]:
            vu.setdefault(c["id"], c)
    return sorted(vu.values(), key=lambda c: (c.get("debut") or "", c["id"]))


def enregistrer_course(sess: Session, annee: int, rid: int, page: str, resume: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    c = lire_course(page)
    c.update({"source": "cqranking.com", "id": rid, "saison": annee,
              "source_url": BASE + "race.asp?raceid=%d" % rid, "lu_le": _maintenant()})
    for k in ("nom", "pays"):
        if meta.get(k) and k not in c:
            c[k] = meta[k]
    if "categorie" not in c and meta.get("categorie"):
        c["categorie"] = meta["categorie"]
    resume["pages_lues"] += 1
    for k, v in c["stats"].items():
        resume["stats"][k] = resume["stats"].get(k, 0) + v
    resume["colonnes"][c["colonne"]] = resume["colonnes"].get(c["colonne"], 0) + 1
    if not c.get("titre") or (c["colonne"] == "inconnue"):
        resume["pages_illisibles"] += 1
    _ecrire_json(chemin_course(sess.sortie, annee, rid), c, compact=True)
    return c


def pages_de_la_course(sess: Session, annee: int, c: Dict[str, Any], sans_etapes: bool, relire: bool,
                       resume: Dict[str, Any]) -> Tuple[List[int], bool]:
    """Raceid à lire pour une course du calendrier : la course seule, ou toutes les pages de son `tour` (étapes, général,
    annexes). Lit la page `tour` si besoin. Retourne (raceid, tour_connu)."""
    if not c.get("tour") or sans_etapes:
        return [c["id"]], True
    chemin = chemin_tour(sess.sortie, c["tour"])
    tour = _lire_json(chemin, None) if not relire else None
    if tour is None:
        page = sess.page("tour.asp?tourid=%d" % c["tour"])
        if page is None:
            return [c["id"]], False
        tour = lire_tour(page)
        tour.update({"source": "cqranking.com", "tour": c["tour"], "saison": annee, "lu_le": _maintenant(),
                     "source_url": BASE + "tour.asp?tourid=%d" % c["tour"]})
        resume["tours_lus"] += 1
        _ecrire_json(chemin, tour, compact=True)
    ids = [e["id"] for e in tour.get("etapes", [])]
    if c["id"] not in ids:
        ids.append(c["id"])
    return ids, True


def fiches_attendues(sortie: str) -> List[int]:
    """Coureurs des classements collectés, du plus notable au moins notable : (meilleur rang, nombre d'apparitions
    décroissant, id). Les lignes sans rang (retards) comptent comme apparition seulement."""
    meilleur: Dict[int, int] = {}
    fois: Dict[int, int] = {}
    racine = os.path.join(sortie, "courses")
    for dossier, _, fichiers in sorted(os.walk(racine)):
        for nom in sorted(fichiers):
            if not nom.endswith(".json"):
                continue
            c = _lire_json(os.path.join(dossier, nom), None)
            if not isinstance(c, dict):
                continue
            lignes = list(c.get("lignes", [])) + list(c.get("arrivees_tardives", []))
            for e in c.get("equipes", []):
                for rid in e.get("coureurs", []):
                    lignes.append([e.get("rang"), rid])
            for lg in lignes:
                rid = lg[1]
                fois[rid] = fois.get(rid, 0) + 1
                if lg[0] is not None and lg[0] < meilleur.get(rid, 10 ** 6):
                    meilleur[rid] = lg[0]
    return sorted(fois, key=lambda r: (meilleur.get(r, 10 ** 6), -fois[r], r))


def _fiche_a_lire(entree: Optional[Dict[str, Any]]) -> bool:
    if entree is None:
        return True
    if entree.get("nom"):
        return False
    if entree.get("regle", 0) < REGLE_ECHECS:
        return True
    return entree.get("echecs", 0) < ECHECS_MAX


def _noter_echec(cache: Dict[str, Any], i: int) -> None:
    e = cache.get(str(i))
    if e and e.get("nom"):
        return
    maintenant = _maintenant()
    n = (e or {}).get("echecs", 0) if (e or {}).get("regle", 0) >= REGLE_ECHECS else 0
    if n and (e or {}).get("dernier_essai", "")[:10] == maintenant[:10]:
        return                                  # un seul échec par fiche et par jour
    cache[str(i)] = {"echecs": n + 1, "dernier_essai": maintenant, "regle": REGLE_ECHECS}


def lire_fiches(sess: Session, sortie: str, relire: bool, resume: Dict[str, Any]) -> int:
    """Lit la fiche de chaque coureur collecté absent de `coureurs.json` (une requête chacun, URL composée avec l'id lu dans
    un lien du classement). Cache écrit tous les 100 coureurs et à l'arrêt. Retourne le nombre restant."""
    chemin = os.path.join(sortie, "coureurs.json")
    chemin_eq = os.path.join(sortie, "equipes.json")
    cache: Dict[str, Any] = _lire_json(chemin, {})
    equipes: Dict[str, Dict[str, str]] = _lire_json(chemin_eq, {})
    attendus = fiches_attendues(sortie)
    a_lire = [i for i in attendus if relire or _fiche_a_lire(cache.get(str(i)))]
    lues, depuis = 0, 0
    st = {"jour": 0, "inconnu": 0, "absent": 0, "echecs": 0, "pannes": 0, "avec_uci_id": 0, "sans_uci_id": 0}
    inconnus: List[str] = []
    try:
        for i in a_lire:
            if sess.epuise():
                break
            page = sess.page("rider.asp?riderid=%d" % i)
            if not page:
                if sess.absente:                     # 404 / 410 : vrai échec ; sinon panne passagère, rien n'est noté
                    st["echecs"] += 1
                    _noter_echec(cache, i)
                    depuis += 1
                else:
                    st["pannes"] += 1
                continue
            fiche, statut, brut = lire_fiche(page)
            if not fiche.get("nom"):
                st["echecs"] += 1
                _noter_echec(cache, i)
                depuis += 1
                continue
            lues += 1
            st[statut] += 1
            st["avec_uci_id" if fiche.get("uci_id") else "sans_uci_id"] += 1
            if statut == "inconnu" and len(inconnus) < 20:
                inconnus.append(brut)
            if fiche.get("nationalite") and pays_normalise(fiche["nationalite"], "cqranking") is None:
                k = "fiche:" + fiche["nationalite"]
                resume["codes_pays_inconnus"][k] = resume["codes_pays_inconnus"].get(k, 0) + 1
            for annee, code, nom in fiche.pop("equipes", []):
                equipes.setdefault(str(annee), {}).setdefault(code, nom)
                fiche.setdefault("equipes", []).append([annee, code])
            fiche["url"] = BASE + "rider.asp?riderid=%d" % i
            fiche["lu_le"] = _maintenant()
            cache[str(i)] = fiche
            depuis += 1
            if depuis >= 100:
                _ecrire_json(chemin, cache, compact=True)
                _ecrire_json(chemin_eq, equipes, compact=True)
                depuis = 0
            sess.journal("fiches coureurs : %d lues, %d restantes" % (lues, len(a_lire) - lues - st["echecs"] - st["pannes"]))
    finally:
        if depuis or (cache and not os.path.exists(chemin)):
            _ecrire_json(chemin, cache, compact=True)
            _ecrire_json(chemin_eq, equipes, compact=True)
    restantes = len([i for i in attendus if _fiche_a_lire(cache.get(str(i)))])
    resume["fiches_lues"] = lues
    resume["fiches_dates"] = st
    if inconnus:
        resume["formats_date_inconnus"] = inconnus
    sess.journal("fiches coureurs : %d lues, %d restantes" % (lues, restantes), force=True)
    return restantes


def lancer(sortie: str, avant: int = AVANT_DEFAUT, depuis: int = DEPUIS_DEFAUT, relire: bool = False,
           budget_min: float = 0.0, max_pages: int = 0, decouverte_seule: bool = False, fiches: bool = True,
           sans_etapes: bool = False, max_courses: int = 0, session: Optional[Session] = None,
           cibles: Optional[List[str]] = None, garder_html: bool = False) -> Dict[str, Any]:
    """Calendriers (12 mois par saison, du plus récent au plus ancien) -> pages des courses -> fiches des coureurs.
    Reprenable : une page écrite n'est jamais relue (sans `relire`). Avec des fiches à lire, les pages de courses ne
    prennent que 70 % du budget de temps : le reste va aux fiches (l'identification des coureurs est la priorité).
    Écrit `etat.json`. `session` : session déjà construite (tests)."""
    sess = session or Session(sortie, budget_min, max_pages, garder_html)
    cibles = [netutil.normalize(t) for t in (cibles or []) if t.strip()]
    resume: Dict[str, Any] = {"calendriers": 0, "courses_calendrier": 0, "tours_lus": 0, "pages_lues": 0, "pages_deja": 0,
                              "pages_illisibles": 0, "stats": {}, "colonnes": {}, "codes_pays_inconnus": {}}
    calendriers_restants = 0
    pages_restantes = 0
    lues_courses = 0
    saisons = [a for a in range(avant - 1, depuis - 1, -1)]
    cals: Dict[int, Dict[str, Any]] = {}
    for annee in saisons:
        if sess.epuise():
            calendriers_restants += 12
            continue
        cals[annee], r = lire_calendriers(sess, annee, relire, resume)
        calendriers_restants += r
        resume["courses_calendrier"] += len(courses_du_calendrier(cals[annee]))
        sess.journal("calendrier %d lu" % annee)
    if not decouverte_seule:
        limite = 0.7 if fiches else 1.0
        arret = False
        for annee in saisons:
            if annee not in cals:
                continue
            for c in courses_du_calendrier(cals[annee]):
                if cibles and not any(t == str(c["id"]) or t in netutil.normalize(c["nom"]) for t in cibles):
                    continue
                if arret:
                    pages_restantes += 1 if not os.path.exists(chemin_course(sortie, annee, c["id"])) else 0
                    continue
                if max_courses and lues_courses >= max_courses:
                    arret = True
                    pages_restantes += 1 if not os.path.exists(chemin_course(sortie, annee, c["id"])) else 0
                    continue
                ids, _ = pages_de_la_course(sess, annee, c, sans_etapes, relire, resume) \
                    if not sess.epuise(limite) else ([c["id"]], False)
                manquants = [rid for rid in ids if relire or not os.path.exists(chemin_course(sortie, annee, rid))]
                resume["pages_deja"] += len(ids) - len(manquants)
                if manquants:
                    lues_courses += 1
                for rid in manquants:
                    if sess.epuise(limite):
                        arret = True
                        pages_restantes += 1
                        continue
                    page = sess.page("race.asp?raceid=%d" % rid)
                    if page is None:
                        pages_restantes += 1
                        continue
                    enregistrer_course(sess, annee, rid, page, resume, c if rid == c["id"] else {})
                    sess.journal("lecture : %d pages lues" % resume["pages_lues"])
                if c.get("tour") and not sans_etapes and not os.path.exists(chemin_tour(sortie, c["tour"])):
                    pages_restantes += 1
    if fiches and not decouverte_seule:
        coureurs_restants = lire_fiches(sess, sortie, relire, resume)
    else:
        cache = _lire_json(os.path.join(sortie, "coureurs.json"), {})
        coureurs_restants = len([i for i in fiches_attendues(sortie) if _fiche_a_lire(cache.get(str(i)))])
    resume["echecs"] = sess.echecs
    resume["requetes"] = sess.requetes
    resume["duree_min"] = round((time.monotonic() - sess.t0) / 60, 1)
    resume["budget_epuise"] = sess.epuise()
    termine = bool(not calendriers_restants and not pages_restantes and not coureurs_restants and fiches
                   and not decouverte_seule and not max_courses and not sans_etapes)
    _ecrire_json(os.path.join(sortie, "etat.json"), {"termine": termine, "calendriers_restants": calendriers_restants,
                                                     "pages_restantes": pages_restantes, "coureurs_restants": coureurs_restants})
    resume["calendriers_restants"], resume["pages_restantes"], resume["coureurs_restants"], resume["termine"] = \
        calendriers_restants, pages_restantes, coureurs_restants, termine
    sess.journal("synthèse : %s" % json.dumps(resume, ensure_ascii=False, sort_keys=True), force=True)
    return resume


# --------------------------------------------------------------------------------------------------
# Tests sans réseau (pages réelles allégées de tools/fixtures/cqranking/)
# --------------------------------------------------------------------------------------------------

def _fixture(nom: str) -> str:
    with open(os.path.join(FIXTURES, nom), encoding="utf-8") as f:
        return f.read()


def _tests() -> None:
    import tempfile
    # durées
    assert parse_duree("4h19'41\"") == ("valeur", 4 * 3600 + 19 * 60 + 41)
    assert parse_duree("86h15'02\"") == ("valeur", 86 * 3600 + 15 * 60 + 2)
    assert parse_duree("04'40\"") == ("valeur", 280) and parse_duree("06\"") == ("valeur", 6)
    assert parse_duree("01'33\"") == ("valeur", 93) and parse_duree("1h10'39\"") == ("valeur", 4239)
    assert parse_duree("") == ("vide", None) and parse_duree("   ")[0] == "vide"
    assert parse_duree("s.t.")[0] == "illisible" and parse_duree("12:30")[0] == "illisible"
    assert parse_duree("75'10\"")[0] == "illisible" and parse_duree("5h")[1] == 18000
    # dates
    assert date_iso("1/04/2005") == "2005-04-01" and date_iso("15/08/1974") == "1974-08-15"
    assert date_iso("31/02/2005") is None and date_iso("2005-04-01") is None and date_iso("") is None
    # noms
    assert nom_famille_prenom("DE MAAR Marc") == ("DE MAAR", "Marc")
    assert nom_famille_prenom("O'LOUGHLIN David") == ("O'LOUGHLIN", "David")
    assert nom_famille_prenom("GONZALEZ DE GALDEANO ARANZABAL Igor") == ("GONZALEZ DE GALDEANO ARANZABAL", "Igor")
    assert nom_famille_prenom("Anonyme") == ("Anonyme", "")
    # types
    assert type_classement("2.1s", None) == "etape" and type_classement("GT1s", 84) == "etape"
    assert type_classement("GT1r", 84) == "annexe" and type_classement("GT1", 84) == "general"
    assert type_classement("1.1", None) == "jour" and type_classement("CDM", None) == "jour"
    assert type_classement("2.2", 234) == "general" and type_classement("NC4", None) == "jour"
    assert type_classement("1.2U", None) == "jour" and type_classement("1.HC", None) == "jour"

    # calendrier d'avril 2005 (page réelle allégée : 9 lignes sur les 64 annoncées)
    attendu, cs = lire_calendrier(_fixture("calendrier_2005_04.html"))
    assert attendu == 64 and len(cs) == 9, (attendu, len(cs))
    assert cs[0] == {"id": 1821, "nom": "Route Adélie de Vitré", "categorie": "1.1", "pays": "FRA", "debut": "2005-04-01"}, cs[0]
    assert cs[1]["tour"] == 234 and cs[1]["fin"] == "2005-04-03" and cs[1]["nom"].startswith("Triptyque des Monts"), cs[1]

    # course d'un jour : Route Adélie de Vitré 2005
    c = lire_course(_fixture("course_1821_vitre_2005.html"))
    assert c["titre"] == "Route Adélie de Vitré (185,3 km)" and c["km"] == 185.3 and c["pays"] == "FRA"
    assert c["debut"] == c["fin"] == "2005-04-01" and c["categorie"] == "1.1" and c["type"] == "jour" and c["tour"] is None
    assert c["colonne"] == "temps" and c["temps_s"] == 4 * 3600 + 19 * 60 + 41 and len(c["lignes"]) == 13
    assert c["lignes"][0] == [1, 2568, "ITA", "LPR", "4h19'41\"", 0, 80], c["lignes"][0]
    assert c["lignes"][1] == [2, 2095, "MEX", "PAN", "06\"", 6, 48]                   # écart au 1er
    assert c["lignes"][3][5] == 12 and c["lignes"][4][5] == 12                        # même groupe : même écart (pas cumulé)
    assert c["noms"]["2568"] == "CONTRINI Daniele" and c["noms"]["2095"] == "ALDAPE CHAVEZ Moises"
    assert c["stats"]["lignes"] == 13 and c["stats"]["temps_illisibles"] == 0

    # Milan-San Remo 2005 : cellule vide = même temps que le 1er ; points CQ ; accents de la page (cp1252 lu en UTF-8 ici)
    c = lire_course(_fixture("course_1752_sanremo_2005.html"))
    assert c["categorie"] == "1.PT1" and c["km"] == 294.0 and c["type"] == "jour"
    assert c["lignes"][0][:2] == [1, c["lignes"][0][1]] and c["lignes"][0][4] == "7h11'39\"" and c["temps_s"] == 25899
    assert c["lignes"][1][4] == "" and c["lignes"][1][5] == 0 and c["lignes"][1][6] == 150     # Hondo, vide -> 0
    assert c["stats"]["temps_vides"] >= 1
    # Milan-San Remo 1999 (Coupe du monde, 169 classés, première saison de la base)
    c = lire_course(_fixture("course_10886_sanremo_1999.html"))
    assert c["categorie"] == "CDM" and c["debut"] == "1999-03-20" and c["lignes"][0][1] == 11753 and c["lignes"][0][2] == "BEL"
    assert c["noms"]["11753"] == "TCHMIL Andrei"

    # petite course : équipe « - » sans lien (coureurs sans équipe UCI), ligne « leader » ignorée, 5 places seulement
    c = lire_course(_fixture("etape_1550_tachira_2005.html"))
    assert c["type"] == "etape" and c["tour"] == 214 and c["pays"] == "VEN" and len(c["lignes"]) == 5, c["lignes"]
    assert c["lignes"][0][:4] == [1, 2953, "VEN", None] and c["lignes"][0][4] == "3h23'36\"" and c["temps_s"] == 12216
    assert c["lignes"][1][3] is None and c["lignes"][1][5] == 13 and c["stats"]["sans_equipe"] == 5

    # course annulée : aucune ligne, commentaire de la page conservé
    c = lire_course(_fixture("general_1656_annule_2005.html"))
    assert c["lignes"] == [] and c["commentaire"] == "Stage race was cancelled due to bad weather." and c["type"] == "general"

    # étape (Tour de France 2005, étape 2), général, classement par points
    c = lire_course(_fixture("etape_2570_tdf_2005.html"))
    assert c["type"] == "etape" and c["categorie"] == "GT1s" and c["tour"] == 84 and c["titre"].startswith("Tour de France, Stage 2")
    assert c["lignes"][0][1] == 11 and c["noms"]["11"] == "BOONEN Tom" and c["lignes"][1][5] == 0
    c = lire_course(_fixture("general_2590_tdf_2005.html"))
    assert c["type"] == "general" and c["tour"] == 84 and c["temps_s"] == 86 * 3600 + 15 * 60 + 2
    assert c["lignes"][1][5] == 280 and c["lignes"][1][6] == 375                      # Basso +4'40", 375 points CQ
    c = lire_course(_fixture("points_2592_tdf_2005.html"))
    assert c["type"] == "annexe" and c["colonne"] == "points" and c["lignes"][0][4] == "194" and c["lignes"][0][5] is None
    assert "temps_s" not in c and c["lignes"][-1][4] != ""

    # contre-la-montre par équipes : équipes, coureurs, arrivées tardives (pas d'écart interprété)
    c = lire_course(_fixture("clm_equipes_2572_tdf_2005.html"))
    assert c["colonne"] == "equipes" and c["type"] == "etape" and "lignes" not in c
    e = c["equipes"]
    assert [x["rang"] for x in e] == [1, 2, 3, 4] and e[0]["nom"] == "Discovery Channel Pro Cycling Team" and e[0]["equipe"] == "DSC"
    assert e[0]["ecart_s"] == 0 and e[1]["ecart_s"] == 2 and c["temps_s"] == 4239 and e[0]["points_cq"] == 14
    assert len(e[0]["coureurs"]) == 9 and 7 in e[0]["coureurs"] and c["noms"]["7"] == "ARMSTRONG Lance"
    assert len(c["arrivees_tardives"]) == 3 and c["arrivees_tardives"][0][0] is None and c["arrivees_tardives"][0][4] == "08'53\"" \
        and c["arrivees_tardives"][0][5] is None, c["arrivees_tardives"][0]

    # page tour : étapes, général, annexes, vainqueurs (et équipe gagnante d'un CLM par équipes)
    t = lire_tour(_fixture("tour_234_triptyque_2005.html"))
    assert t["titre"] == "Triptyque des Monts et Châteaux" and t["debut"] == "2005-04-01" and t["fin"] == "2005-04-03"
    assert [e["id"] for e in t["etapes"]] == [1822, 1824, 1825, 1826, 1827] and t["etapes"][0]["date"] == "2005-04-01"
    assert t["etapes"][0]["vainqueur"] == {"id": 3257, "nom": "POULHIES Stéphane"} and t["etapes"][4]["libelle"] == "General classification"
    t = lire_tour(_fixture("tour_84_tdf_2005.html"))
    assert any(e.get("vainqueur_equipe") == "Discovery Channel Pro Cycling Team" and e["id"] == 2572 for e in t["etapes"]), t["etapes"]
    assert t["etapes"][-1]["id"] == 2591 or any(e["id"] == 2590 for e in t["etapes"])

    # fiches coureurs : date complète + ID UCI, date sans ID UCI
    f, st, brut = lire_fiche(_fixture("fiche_2568_contrini.html"))
    assert st == "jour" and f["naissance"] == "1974-08-15" and f["uci_id"] == "10001146907" and f["nationalite"] == "ITA"
    assert f["nom"] == "CONTRINI Daniele" and f["nom_famille"] == "CONTRINI" and f["prenom"] == "Daniele" and f["statut"] == "Retired"
    assert f["equipes"][0] == [2008, "TCS", "Tinkoff Credit Systems"], f["equipes"][:2]
    f, st, brut = lire_fiche(_fixture("fiche_2568_contrini.html").replace("CONTRINI Daniele", "CONTRINI Daniele*"))
    assert f["nom"] == "CONTRINI Daniele*" and f["marque_nom"] == "*" and f["prenom"] == "Daniele" and f["nom_famille"] == "CONTRINI"
    f, st, brut = lire_fiche(_fixture("fiche_11753_tchmil.html"))
    assert st == "jour" and f["naissance"] == "1963-01-22" and "uci_id" not in f and f["nom"] == "TCHMIL Andrei"
    # date d'allure inconnue ou impossible : pas de naissance, jamais d'inférence
    base = _fixture("fiche_11753_tchmil.html")
    f, st, brut = lire_fiche(base.replace("22/01/1963", "1963"))
    assert st == "inconnu" and "naissance" not in f and brut == "1963", (st, brut)
    f, st, brut = lire_fiche(base.replace("22/01/1963", "31/02/1963"))
    assert st == "inconnu" and "naissance" not in f
    f, st, brut = lire_fiche(base.replace("<b>22/01/1963</b>", "<b></b>"))
    assert st == "absent" and "naissance" not in f
    assert lire_fiche("<html>rien</html>")[0] == {}

    # phase d'écriture et de reprise, sans réseau (Session simulée : pages réelles allégées)
    class Faux(Session):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.demandees: List[str] = []

        def page(self, rel):
            if self.epuise():
                return None
            self.requetes += 1
            self.demandees.append(rel)
            self.absente = False
            if rel.startswith("RaceCal.asp?year=2005&month=4"):
                return _fixture("calendrier_2005_04.html")
            if rel.startswith("RaceCal"):
                return "<html>Number of results found: 0.<br></html>"
            if rel == "tour.asp?tourid=234":
                return _fixture("tour_234_triptyque_2005.html")
            if rel == "race.asp?raceid=1821":
                return _fixture("course_1821_vitre_2005.html")
            if rel.startswith("race.asp?raceid="):
                return _fixture("etape_2570_tdf_2005.html")
            if "riderid=2568" in rel:
                return _fixture("fiche_2568_contrini.html")
            if "riderid=11753" in rel:
                return _fixture("fiche_11753_tchmil.html")
            self.absente = True
            return None                                                       # tour ou fiche inconnu : échec compté (404)

    with tempfile.TemporaryDirectory() as d:
        sess = Faux(d, max_pages=15)
        res = lancer(d, avant=2006, depuis=2005, fiches=False, session=sess)
        assert sess.requetes == 15 and os.path.exists(chemin_course(d, 2005, 1821)), res
        cal = _lire_json(os.path.join(d, "calendrier", "2005.json"), {})
        assert len(cal["mois"]) == 12 and cal["mois"]["4"]["attendu"] == 64 and len(cal["mois"]["4"]["courses"]) == 9
        assert _lire_json(chemin_tour(d, 234), {})["etapes"][0]["id"] == 1822
        ed = _lire_json(chemin_course(d, 2005, 1821), {})
        assert ed["saison"] == 2005 and ed["source"] == "cqranking.com" and ed["lignes"][0][1] == 2568 and ed["lu_le"]
        etat = _lire_json(os.path.join(d, "etat.json"), {})
        assert etat["termine"] is False and etat["pages_restantes"] > 0 and etat["calendriers_restants"] == 0, etat
        # reprise : aucune page déjà écrite (calendrier, tour, course) n'est redemandée
        deja = list(sess.demandees)
        sess2 = Faux(d, max_pages=40)
        lancer(d, avant=2006, depuis=2005, fiches=False, session=sess2)
        assert not [r for r in sess2.demandees if r in deja], [r for r in sess2.demandees if r in deja]
        assert sess2.requetes == 40 or _lire_json(os.path.join(d, "etat.json"), {})["pages_restantes"] == 0
        assert not [r for r in sess2.demandees if r.startswith("RaceCal")]

    # fiches : ordre = meilleur rang, puis fréquence ; jamais relues ; plafond ; échecs ; naissance seulement si complète
    with tempfile.TemporaryDirectory() as d:
        _ecrire_json(chemin_course(d, 2005, 1), {"lignes": [[1, 2568, "ITA", "LPR", "4h", 0, 80], [2, 11753, "BEL", "LOT", "", 0, 50],
                                                          [3, 500, "GER", "GST", "1'", 60, 30]]})
        _ecrire_json(chemin_course(d, 2005, 2), {"lignes": [[1, 11753, "BEL", "LOT", "4h", 0, 80], [9, 500, "GER", "GST", "1'", 60, 30]],
                                                 "arrivees_tardives": [[None, 77, "ESP", "EUS", "09'31\"", None, 0]],
                                                 "equipes": [{"rang": 2, "coureurs": [2568, 88]}]})
        att = fiches_attendues(d)
        assert att == [2568, 11753, 88, 500, 77], att      # meilleur rang d'abord (ex æquo : plus fréquent, puis id) ; sans rang en dernier
        res = {"codes_pays_inconnus": {}}
        sess = Faux(d, max_pages=2)
        assert lire_fiches(sess, d, False, res) == 3 and sess.requetes == 2     # plafond : 3 restantes
        cache = _lire_json(os.path.join(d, "coureurs.json"), {})
        assert sorted(cache) == ["11753", "2568"], sorted(cache)
        assert cache["2568"]["naissance"] == "1974-08-15" and cache["2568"]["uci_id"] == "10001146907"
        assert cache["2568"]["equipes"][0] == [2008, "TCS"] and cache["2568"]["url"].endswith("rider.asp?riderid=2568")
        assert "uci_id" not in cache["11753"] and cache["11753"]["naissance"] == "1963-01-22"
        assert _lire_json(os.path.join(d, "equipes.json"), {})["2008"]["TCS"] == "Tinkoff Credit Systems"
        sess = Faux(d)
        restantes = lire_fiches(sess, d, False, res)
        assert "riderid=2568" not in " ".join(sess.demandees) and restantes == 3, (sess.demandees, restantes)  # 500, 88, 77 : échec
        cache = _lire_json(os.path.join(d, "coureurs.json"), {})
        assert cache["500"]["echecs"] == 1 and "naissance" not in cache["500"]
        # échecs : un par jour, abandonnés après ECHECS_MAX jours, jamais de date inventée ; entrée de règle ancienne : à relire
        c2: Dict[str, Any] = {}
        _noter_echec(c2, 9)
        _noter_echec(c2, 9)
        assert c2["9"]["echecs"] == 1 and _fiche_a_lire(c2["9"])
        for _ in range(ECHECS_MAX - 1):
            c2["9"]["dernier_essai"] = "2026-01-01T00:00:00Z"
            _noter_echec(c2, 9)
        assert not _fiche_a_lire(c2["9"]) and "naissance" not in c2["9"]
        ancien = {"echecs": 3, "dernier_essai": "2026-11-18T11:00:00Z"}
        assert _fiche_a_lire(ancien) and not _fiche_a_lire(dict(ancien, regle=REGLE_ECHECS))
        c2["7"] = dict(ancien)
        _noter_echec(c2, 7)
        assert c2["7"]["echecs"] == 1 and c2["7"]["regle"] == REGLE_ECHECS
        # panne passagère (503, réseau) : rien n'est noté
        class Panne(Session):
            def page(self, rel):
                self.requetes += 1
                self.absente = False
                return None
        c3 = os.path.join(d, "p")
        _ecrire_json(chemin_course(c3, 2005, 1), {"lignes": [[1, 2568, "ITA", "LPR", "4h", 0, 80]]})
        assert lire_fiches(Panne(c3), c3, False, res) == 1
        assert not os.path.exists(os.path.join(c3, "coureurs.json")) or _lire_json(os.path.join(c3, "coureurs.json"), {}) == {}
        c2["8"] = {"nom": "X Y"}
        _noter_echec(c2, 8)
        assert c2["8"] == {"nom": "X Y"} and not _fiche_a_lire(c2["8"])
    print("cqranking : tests OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--test", action="store_true", help="tests sans réseau")
    ap.add_argument("--sortie", default=SORTIE_DEFAUT, help="dossier de sortie (défaut : ARCHIVES_DIR/sources/cqranking)")
    ap.add_argument("--avant", type=int, default=AVANT_DEFAUT, help="saisons strictement avant cette année (défaut 2009)")
    ap.add_argument("--depuis", type=int, default=DEPUIS_DEFAUT, help="saisons à partir de cette année (défaut 1999)")
    ap.add_argument("--relire", action="store_true", help="relire aussi les pages et fiches déjà écrites")
    ap.add_argument("--budget-min", type=float, default=0.0, help="budget de temps en minutes (0 = illimité)")
    ap.add_argument("--max-requetes", "--max-pages", dest="max_requetes", type=int, default=0,
                    help="plafond de requêtes du passage, calendriers + pages + fiches (0 = illimité ; essais)")
    ap.add_argument("--max-courses", type=int, default=0, help="plafond de courses du calendrier lues (0 = illimité ; essais)")
    ap.add_argument("--courses", default="", help="liste : raceid ou fragment de nom (ex. roubaix,sanremo,1821) ; essais")
    ap.add_argument("--garder-html", action="store_true", help="garde les pages lues (gzip, cache/) : relecture sans requête")
    ap.add_argument("--sans-fiches", action="store_true", help="ne lit pas les fiches des coureurs")
    ap.add_argument("--sans-etapes", action="store_true", help="courses par étapes : seulement la page du calendrier (général)")
    ap.add_argument("--decouverte-seule", action="store_true", help="ne lit que les calendriers")
    a = ap.parse_args()
    if a.test:
        _tests()
        return 0
    lancer(a.sortie, a.avant, a.depuis, a.relire, a.budget_min, a.max_requetes, a.decouverte_seule, not a.sans_fiches,
           a.sans_etapes, a.max_courses, None, a.courses.split(","), a.garder_html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
