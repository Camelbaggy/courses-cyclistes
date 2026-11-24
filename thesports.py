#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""the-sports.org : résultats de courses sur route hommes avant 2009 (collecteur, étape 1 : pas d'intégration).

ACCORD : le 18/11/2026, l'éditeur du site (Vincent Duplessy) a donné au propriétaire du projet son accord pour
collecter par programme les résultats cyclistes de the-sports.org et les afficher avec le crédit « the-sports.org ».
Politesse : robots.txt respecté (jamais /accueil.php, /index.php, /admin.php, /go.php, /calendrier.php, /tmp/, /zz,
/how-to-, /*.html/), User-Agent honnête « courses-cyclistes (accord the-sports.org) », ≥ 2 s entre deux requêtes,
une page n'est jamais redemandée (calendriers en cache, éditions écrites une fois sur disque).

Structure du site (constatée le 18/11/2026, docs/recherche/thesports_collecte.md) :
  - `cycling-s2.html` (accueil cyclisme) -> lien « Calendar <année> » -> `cycling-calendar-<année>-s2-c0-b0-u<id>.html` :
    calendrier de TOUTE la saison (tableau Date / Lieu / Course / Competition / Classe / Vainqueur) et une liste
    déroulante de toutes les années (la valeur de chaque option est l'URL du calendrier de l'année).
  - page d'édition `cycling-<nom>-results-<année>-epr<id>.html` (`-epm<id>` = hommes, `-epf` femmes, `-epi` mixte) :
    classements (un `<h4 class="nomargin">` par classement ou étape suivi d'un tableau `table-style-2`), onglet
    « Archives » = liste de TOUTES les éditions de la course (`<li><a href="…">1998 - Tour de France</a></li>`), et
    l'identifiant de la course (`…-presentation-medal-winners-sup<N>.html`, « Prize list »).
  - ligne de classement : rang | nom (code pays du site) + lien `…-cycling-spf<id>.html` | équipe | temps ou points.

Règle cardinale du projet : aucune valeur inventée. Un champ absent reste absent ; un temps de format ambigu ou
inconnu est conservé en texte brut (`brut`) sans valeur numérique, et compté dans la synthèse.

Interprétation des temps (documentée, déterministe) :
  - 1re ligne d'un classement en temps = temps absolu du premier ; marqueur « s.t. » / « m.t. » (écrit par le site) =
    même temps que la ligne PRÉCÉDENTE du tableau (`meme_temps: true`, écart repris de cette ligne) ;
  - autre ligne : valeur >= temps du premier = temps absolu (contre-la-montre, prologue : le site publie alors les
    temps), valeur < temps du premier = écart au premier. Un écart supérieur au temps du vainqueur est impossible.
  - formats lus : `4h18'56` `4h18'56''` `4u05'23"` `55'30''` `1'20` `35''` `8` (secondes, classement en temps
    seulement) `H:MM:SS` `MM:SS` ; suffixe « (40.116 km/h) » séparé (`vitesse_kmh`). Format à points séparés
    (`8.17.00`, `5.36.14`) : AMBIGU (H.MM.SS ou MM.SS.cc), jamais interprété.

Fiches coureurs (décision du propriétaire, 18/11/2026) : les classements ne donnent ni date de naissance ni identifiant
UCI. Après les éditions (donc dans le MÊME budget, les éditions manquantes d'abord), le collecteur lit la fiche de chaque
coureur (id du site `spf<N>`, URL lue dans les classements et gardée dans `fiches` de l'édition, jamais devinée) qui
figure dans une édition écrite et n'est pas encore dans `coureurs.json` : une requête par coureur, jamais relue
(`--relire` : tout relire). Sur la fiche, la ligne sous le titre (« Italy - 11 December 1964 ») et la phrase « (born 11
December 1964 [in Wien]) » portent la naissance. Seule une date COMPLÈTE (jour, mois en toutes lettres anglaises, année)
donne `precision: "jour"` ; un millésime seul donne `precision: "annee"` (`naissance` = « AAAA ») ; mois + année,
format inconnu, numérique ambigu, ou deux sources qui se contredisent : pas de date (compté dans la synthèse,
exemples dans `formats_date_inconnus`). `coureurs.json` = `{id site: {"nom" (tel qu'affiché sur la fiche), "naissance",
"precision", "nationalite" (ISO3 du nom de pays de la fiche, `NOMS_PAYS_ISO3`), "url", "lu_le"}}`, écrit tous les 100
coureurs et à l'arrêt. Code pays du site `SCO` -> `GBR` (nationalité sportive UCI).
Sortie : `courses.json`, `editions/<course>/<année>.json`, `coureurs.json`, `etat.json`
(`{"termine", "editions_restantes", "coureurs_restants"}` : lu par le workflow thesports.yml pour l'auto-relance, sans
horodatage pour qu'un passage sans effet ne change rien), `cache/` (calendriers en gzip).

    python thesports.py --sortie DOSSIER [--avant 2009] [--depuis AAAA] [--courses s43,tour-de-france] [--relire]
                        [--budget-min N] [--max-requetes N] [--decouverte-seule]
                        [--sans-decouverte] [--sans-fiches] [--garder-html]
    python thesports.py --test            # tests sans réseau (pages réelles de tools/fixtures/thesports/)
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

BASE = "https://www.the-sports.org/"
ACCUEIL = BASE + "cycling-s2.html"
USER_AGENT = "courses-cyclistes (accord the-sports.org)"
PAUSE_S = 3.0                      # >= 2 s exigé ; 3 s depuis un 503 du site le 18/11/2026 (accord du 18/11/2026)
netutil.HOST_DELAYS["www.the-sports.org"] = PAUSE_S

AVANT_DEFAUT = 2009                # éditions <= 2008
ARCHIVES_DIR = os.environ.get("ARCHIVES_DIR") or os.path.join("data", "archives")
SORTIE_DEFAUT = os.path.join(ARCHIVES_DIR, "sources", "thesports")
RACINE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(RACINE, "tools", "fixtures", "thesports")

# Colonne « Competition » du calendrier : épreuves sur route hommes élite retenues. Tout autre libellé est refusé
# et compté (« competition_refusee » dans la synthèse) ; les libellés refusés vus sont listés par la découverte.
COMPETITIONS_RETENUES = {
    "World Tour", "UCI Europe Tour", "UCI Asia Tour", "UCI America Tour", "UCI Africa Tour", "UCI Oceania Tour",
    "Grand Tour", "National Championships", "World Championships", "Olympic Games", "Continental Championships",
}
# Libellés vus et écartés exprès (pas route hommes élite) : femmes, juniors, moins de 23 ans.
COMPETITIONS_ECARTEES = {"Women's events", "Juniors events", "U23 events"}
MOTS_EXCLUS_NOM = re.compile(r"junior|u-?23|espoir|amateur|women|femin|mixed|youth", re.I)
FAMILLES_RETENUES = ("epr", "epm")          # epf = femmes, epi = mixte : écartés

MOIS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
     "december"])}

# Code pays du site -> code canonique : table `sources.thesports` de pays_historiques.json (voir pays.py) ; codes propres au site
# (SPA, SWI, MAL, INO…) convertis, pays disparus en code d'époque (FDR -> FRG, DDR -> GDR, URS, YUG, SCG, EUN, ZAI, BOH, VSO),
# SCO -> GBR (nationalité sportive UCI, décision du propriétaire, 18/11/2026). Un code absent donne `nat` absent et est compté
# (`codes_pays_inconnus`) ; le code brut reste dans `nat_site`.

# Nom de pays anglais lu en tête d'une fiche coureur (« Great Britain - 28 April 1980 ») -> code projet. Table explicite,
# sans déduction : un nom absent donne `nationalite` absente et est compté (`pays_fiche_inconnus`).
NOMS_PAYS_ISO3 = {
    "australia": "AUS", "austria": "AUT", "belgium": "BEL", "canada": "CAN", "chile": "CHI", "colombia": "COL",
    "costa rica": "CRC", "croatia": "CRO", "czech republic": "CZE", "denmark": "DEN", "estonia": "EST",
    "finland": "FIN", "france": "FRA", "great britain": "GBR", "scotland": "GBR", "germany": "GER", "hungary": "HUN",
    "ireland": "IRL", "italy": "ITA", "japan": "JPN", "kazakhstan": "KAZ", "latvia": "LAT", "lithuania": "LTU",
    "moldova": "MDA", "mexico": "MEX", "netherlands": "NED", "norway": "NOR", "new zealand": "NZL", "poland": "POL",
    "portugal": "POR", "russia": "RUS", "slovenia": "SLO", "spain": "ESP", "sweden": "SWE", "switzerland": "SUI",
    "ukraine": "UKR", "united states": "USA", "uzbekistan": "UZB", "venezuela": "VEN", "brazil": "BRA",
    "argentina": "ARG", "luxembourg": "LUX", "slovakia": "SVK", "south africa": "RSA",
}

STATUTS = {"DNF", "DNS", "OTL", "DSQ", "DQ", "HD", "AB", "NP", "DNQ", "LAP"}


# --------------------------------------------------------------------------------------------------
# Lecture du HTML (expressions régulières : pages très régulières, aucune dépendance)
# --------------------------------------------------------------------------------------------------

def _corps(texte: str) -> str:
    """Corps de la page sans scripts ni commentaires."""
    i = texte.find("<body")
    c = texte[i:] if i >= 0 else texte
    c = re.sub(r"<script.*?</script>", "", c, flags=re.S)
    return re.sub(r"<!--.*?-->", "", c, flags=re.S)


def _txt(fragment: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def lire_annees_calendrier(page: str) -> Dict[int, str]:
    """Liste déroulante des années d'une page de calendrier : {année: URL relative du calendrier de l'année}."""
    out: Dict[int, str] = {}
    for val, lib in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', _corps(page)):
        if re.fullmatch(r"\d{4}", lib.strip()) and re.match(r"cycling-calendar-\d{4}-s2-c0-b0-u\d+\.html$", val):
            out[int(lib)] = val
    return out


def lien_calendrier(page_accueil: str) -> Optional[str]:
    """Premier lien « Calendar <année> » de la page d'accueil du cyclisme."""
    m = re.search(r'href="(cycling-calendar-\d{4}-s2-c0-b0-u\d+\.html)"', page_accueil)
    return m.group(1) if m else None


def _ids_epr(url: str) -> Tuple[Optional[str], Optional[int]]:
    m = re.search(r"-(ep[a-z])(\d+)\.html$", url)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def lire_calendrier(page: str, annee: int) -> List[Dict[str, Any]]:
    """Lignes d'un calendrier annuel : course, épreuve (famille + id), compétition, classe, lieu, dates, vainqueur."""
    out = []
    for r in re.findall(r'<tr>\s*(<td class="tdcol-15">.*?)</tr>', _corps(page), flags=re.S):
        m = re.search(r'<a href="([^"]*-ep[a-z]\d+\.html)"[^>]*>([^<]*)</a>', r)
        if not m:
            continue
        cellules = [_txt(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S)]
        if len(cellules) < 6:
            continue
        fam, ident = _ids_epr(m.group(1))
        pays = re.search(r'alt="([A-Z]{3})"', r)
        out.append({"annee": annee, "url": m.group(1), "famille": fam, "epr": ident, "nom": _txt(m.group(2)),
                    "date": cellules[0], "lieu": cellules[1], "pays_site": pays.group(1) if pays else None,
                    "competition": cellules[-3], "classe": cellules[-2] or None, "vainqueur": cellules[-1] or None})
    return out


def ligne_retenue(ligne: Dict[str, Any]) -> Tuple[bool, str]:
    """Une ligne de calendrier est-elle une course sur route hommes élite ? (retenue, raison)."""
    if ligne["famille"] not in FAMILLES_RETENUES:
        return False, "famille " + str(ligne["famille"])
    if ligne["competition"] in COMPETITIONS_ECARTEES:
        return False, "competition ecartee"
    if ligne["competition"] not in COMPETITIONS_RETENUES:
        return False, "competition_refusee:" + ligne["competition"]
    if MOTS_EXCLUS_NOM.search(ligne["nom"]):
        return False, "nom exclu"
    return True, ""


def lire_archives(page: str) -> List[Dict[str, Any]]:
    """Onglet « Archives » : TOUTES les éditions de la course (hommes / sans genre ; femmes et mixte écartés)."""
    out, vus = [], set()
    for url, an, nom in re.findall(r'<li><a href="([^"]*-ep[a-z]\d+\.html)">(\d{4}) - ([^<]*)</a></li>', page):
        fam, ident = _ids_epr(url)
        if fam not in FAMILLES_RETENUES or url in vus:
            continue
        vus.add(url)
        out.append({"annee": int(an), "epr": "%s%d" % (fam, ident), "url": url, "nom": _txt(nom)})
    return sorted(out, key=lambda e: (e["annee"], e["epr"]))


def id_course(page: str, editions: List[Dict[str, Any]]) -> Optional[str]:
    """Identifiant de la course : `s<N>` du lien « Prize list » de l'onglet de la page (`…-presentation-medal-winners-sup<N>`),
    à défaut `e<plus petit epr>` des éditions. Le menu général du site contient d'autres liens `sup` : on ne lit que la
    barre d'onglets de la page."""
    nav = re.search(r'<ul class="tab-nav.*?</ul>', page, flags=re.S)
    if nav:
        m = re.search(r"presentation-medal-winners-sup(\d+)\.html", nav.group(0))
        if m:
            return "s" + m.group(1)
    if editions:
        return "e%d" % min(int(re.sub(r"\D", "", e["epr"])) for e in editions)
    return None


# --------------------------------------------------------------------------------------------------
# Temps
# --------------------------------------------------------------------------------------------------

_RE_KM_PREFIXE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*km\s+", re.I)
_RE_VITESSE = re.compile(r"\s*\(([\d.,]+)\s*km/h\)\s*$", re.I)
_MEME_TEMPS = {"s.t", "st", "m.t", "mt"}
_RE_HMS_MARQUES = re.compile(r"^(\d{1,3})[hu](\d{1,2})['’:](\d{1,2})(?:''|\"|’’|'|’)?$")
_RE_MS_MARQUES = re.compile(r"^(\d{1,3})['’](\d{1,2})(?:''|\"|’’|'|’)?$")
_RE_S_MARQUES = re.compile(r"^(\d{1,3})(?:''|\"|’’)$")
_RE_HMS_DEUX_POINTS = re.compile(r"^(\d{1,3}):(\d{2}):(\d{2})$")
_RE_MS_DEUX_POINTS = re.compile(r"^(\d{1,2}):(\d{2})$")
_RE_POINTS_SEPARES = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")


def parse_temps(brut: str, en_temps: bool = True) -> Tuple[str, Optional[float], Optional[float]]:
    """Cellule temps -> (nature, secondes, vitesse km/h).
    nature : 'vide' | 'meme' (s.t. / m.t.) | 'valeur' | 'ambigu' (points séparés) | 'illisible'."""
    txt = _html.unescape(brut or "").strip()
    txt = _RE_KM_PREFIXE.sub("", txt)                         # « 1412 km 37h35'39'' » : distance totale en tête
    vitesse = None
    m = _RE_VITESSE.search(txt)
    if m:
        try:
            vitesse = float(m.group(1).replace(",", "."))
        except ValueError:
            vitesse = None
        txt = txt[:m.start()].strip()
    txt = re.sub(r"\s+", "", txt.lstrip("+ "))                # « + 00' 00 » -> « 00'00 », « 5h 49' 18 » -> « 5h49'18 »
    if not txt:
        return "vide", None, vitesse
    if txt.lower().rstrip(".") in _MEME_TEMPS:
        return "meme", None, vitesse
    for motif, poids in ((_RE_HMS_MARQUES, (3600, 60, 1)), (_RE_HMS_DEUX_POINTS, (3600, 60, 1)),
                         (_RE_MS_MARQUES, (60, 1)), (_RE_MS_DEUX_POINTS, (60, 1)), (_RE_S_MARQUES, (1,))):
        mm = motif.match(txt)
        if mm:
            vals = [int(g) for g in mm.groups()]
            if any(v >= 60 for v in vals[1:]):
                return "illisible", None, vitesse            # minutes ou secondes hors plage : on ne devine pas
            return "valeur", float(sum(v * p for v, p in zip(vals, poids))), vitesse
    if en_temps and re.fullmatch(r"\d{1,5}", txt):
        return "valeur", float(txt), vitesse                  # secondes seules (écart), classement en temps seulement
    if _RE_POINTS_SEPARES.match(txt):
        return "ambigu", None, vitesse
    return "illisible", None, vitesse


# --------------------------------------------------------------------------------------------------
# Classements et étapes
# --------------------------------------------------------------------------------------------------

_RE_DATE_FIN = re.compile(r"\s-\s(\d{1,2}) ([A-Za-z]+) (\d{4})\s*$")
_RE_DATE = re.compile(r"(\d{1,2}) ([A-Za-z]+) (\d{4})")


def date_iso(j: str, mois: str, a: str) -> Optional[str]:
    m = MOIS.get(mois.lower())
    if not m:
        return None
    try:
        return datetime.date(int(a), m, int(j)).isoformat()
    except ValueError:
        return None


def type_section(base: str) -> str:
    """Type d'un classement d'après son titre (sans la date) : prologue, etape, points, montagne, jeunes, equipes,
    combine, general, ou autre (conservé tel quel, le titre brut est toujours gardé)."""
    b = base.lower()
    if re.match(r"prologue\b", b):
        return "prologue"
    if re.match(r"stage\b", b):
        return "etape"
    if re.search(r"\bteams?\b|equipe|équipe", b):
        return "equipes"
    if re.search(r"point|sprint", b):
        return "points"
    if re.search(r"mountain|climb|grimp|kom\b", b):
        return "montagne"
    if re.search(r"young|youth|white|jeune|neo|rookie", b):
        return "jeunes"
    if re.search(r"combin", b):
        return "combine"
    if re.search(r"general|final ranking|overall|final classification", b):
        return "general"
    return "autre"


def lire_titre_section(titre: str, alts: List[str]) -> Dict[str, Any]:
    """Titre d'un `<h4>` : « Stage 8a - Mandelieu-Nice - 91.4 km - 12 March 1995 », « Prologue - Dublin (Irl), 5.6 kM - … »,
    « General Classification - 3 August 1998 », « Paris-Roubaix - 9 April 1995 »."""
    out: Dict[str, Any] = {"titre": titre}
    base = titre
    m = _RE_DATE_FIN.search(base)
    if m:
        d = date_iso(m.group(1), m.group(2), m.group(3))
        if d:
            out["date"] = d
        base = base[:m.start()].strip()
    out["type"] = type_section(base)
    if out["type"] in ("etape", "prologue"):
        if out["type"] == "prologue":
            out["etape"] = "P"
            reste = re.sub(r"^prologue\b\s*-?\s*", "", base, flags=re.I)
        else:
            mm = re.match(r"stage\s+(\w+)\s*(?:-\s*(.*))?$", base, flags=re.I)
            out["etape"] = mm.group(1) if mm else None
            reste = (mm.group(2) or "") if mm else ""
        md = re.search(r"[,\s-]*\s(\d+(?:[.,]\d+)?)\s*k[mM]\s*$", " " + reste)
        if md:
            out["distance_km"] = float(md.group(1).replace(",", "."))
            reste = reste[:len(reste) - (len(" " + reste) - md.start())].rstrip(" ,-")
        reste = reste.strip(" ,-")
        if reste:
            out["parcours"] = reste
            parts = [p.strip() for p in reste.split(" - ")]
            if len(parts) == 2 and all(parts):
                out["depart"], out["arrivee"] = parts
    if alts:
        out["profil"] = alts[0]
        if alts[0].lower() == "time trial":
            out["contre_la_montre"] = True
    return out


def lire_ligne(tr: str) -> Optional[Dict[str, Any]]:
    cells = re.findall(r"<td([^>]*)>(.*?)</td>", tr, flags=re.S)
    if len(cells) < 3:
        return None
    rang_txt = _txt(cells[0][1])
    ligne: Dict[str, Any] = {}
    if re.fullmatch(r"\d+", rang_txt):
        ligne["rang"] = int(rang_txt)
    elif rang_txt.upper().rstrip(".") in STATUTS:
        ligne["statut"] = rang_txt.upper().rstrip(".")
    else:
        ligne["rang_brut"] = rang_txt
    nom_html = cells[1][1]
    nom = _txt(nom_html)
    mc = re.search(r"\s*\(([A-Z]{3})\)\s*$", nom)
    code = mc.group(1) if mc else None
    if mc:
        nom = nom[:mc.start()].strip()
    if not code:
        ma = re.search(r'<img[^>]*alt="([A-Z]{3})"', nom_html)
        code = ma.group(1) if ma else None
    ligne["nom"] = nom
    if code:
        ligne["nat_site"] = code
        iso = pays_normalise(code, "thesports")
        if iso:
            ligne["nat"] = iso
    ms = re.search(r"-spf(\d+)\.html", nom_html)
    if ms:
        ligne["id_site"] = int(ms.group(1))
        mu = re.search(r'href="([^"]*-cycling-spf%s\.html)"' % ms.group(1), nom_html)
        if mu:
            ligne["_url"] = mu.group(1)           # URL lue dans le classement (retirée par lire_edition -> `fiches`)
    equipe = _txt(cells[2][1])
    if equipe:
        ligne["equipe"] = equipe
    if len(cells) >= 4:
        brut = _txt(cells[3][1])
        if brut:
            ligne["brut"] = brut
    return ligne


def calculer_valeurs(section: Dict[str, Any], stats: Dict[str, int]) -> None:
    """Pose `points` (classements à points) ou `temps_s` / `ecart_s` / `meme_temps` / `vitesse_kmh` (classements en
    temps) sur chaque ligne ; règles dans la docstring du module."""
    lignes = section["lignes"]
    if section["type"] in ("points", "montagne", "combine"):
        for l in lignes:
            if "brut" not in l:
                continue
            if re.fullmatch(r"-?\d+(?:[.,]\d+)?", l["brut"]):
                v = float(l["brut"].replace(",", "."))
                l["points"] = int(v) if v == int(v) else v
            else:
                stats["temps_illisibles"] += 1
        return
    ref: Optional[float] = None
    prec: Optional[Dict[str, Any]] = None
    for i, l in enumerate(lignes):
        brut = l.get("brut", "")
        mk = _RE_KM_PREFIXE.match(_html.unescape(brut))
        if mk:
            l["distance_km"] = float(mk.group(1).replace(",", "."))
        nature, sec, vit = parse_temps(brut, True)
        if vit is not None:
            l["vitesse_kmh"] = vit
        explicite = _html.unescape(brut).lstrip().startswith("+")
        if nature == "meme":
            l["meme_temps"] = True
            if prec is not None:
                if "ecart_s" in prec:
                    l["ecart_s"] = prec["ecart_s"]
                if "temps_s" in prec:
                    l["temps_s"] = prec["temps_s"]
            prec = l
            continue
        if nature in ("ambigu", "illisible"):
            stats["temps_ambigus" if nature == "ambigu" else "temps_illisibles"] += 1
            prec = l
            continue
        if nature == "valeur" and sec is not None:
            if explicite:
                l["ecart_s"] = sec                       # « + MM' SS » : écart écrit comme tel par le site
            elif i == 0:
                ref = sec                                # seule la 1re ligne donne le temps de référence
                l["temps_s"] = sec
                l["ecart_s"] = 0.0
            elif ref is None:
                stats["temps_non_resolus"] += 1          # temps du premier absent : absolu ou écart, on ne devine pas
            elif sec >= ref:
                l["temps_s"] = sec
                l["ecart_s"] = sec - ref
            else:
                l["ecart_s"] = sec
        prec = l


def lire_sections(page: str, stats: Dict[str, int]) -> List[Dict[str, Any]]:
    c = _corps(page)
    i = c.find('<div class="tab-contents">')
    c = c[i:] if i >= 0 else c
    sections = []
    for bloc in re.split(r'(?=<h4 class="nomargin">)', c)[1:]:
        h = re.match(r'<h4 class="nomargin"><a[^>]*>(.*?)</a>(.*?)</h4>', bloc, flags=re.S)
        if not h:
            continue
        sec = lire_titre_section(_txt(h.group(1)), re.findall(r'alt="([^"]*)"', h.group(2)))
        fin = bloc.find("</table>")
        tableau = bloc[h.end():fin] if fin > 0 else ""
        lignes = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tableau, flags=re.S):
            l = lire_ligne(tr)
            if l:
                lignes.append(l)
                if "nat_site" in l and "nat" not in l:
                    stats["nat_inconnues"] += 1
                    stats["codes_inconnus"][l["nat_site"]] = stats["codes_inconnus"].get(l["nat_site"], 0) + 1
                if "nat_site" not in l:
                    stats["nat_absentes"] += 1
                if "rang_brut" in l:
                    stats["rangs_illisibles"] += 1
        sec["lignes"] = lignes
        stats["lignes"] += len(lignes)
        calculer_valeurs(sec, stats)
        sections.append(sec)
    # course d'un jour : une seule section sans mot-clé = classement final
    if sections and all(s["type"] in ("autre",) for s in sections) and len(sections) == 1:
        sections[0]["type"] = "final"
    return sections


def lire_edition(page: str, url: str) -> Dict[str, Any]:
    """Page d'édition -> dict (contenu lu ; `source_url` et `lu_le` posés par l'appelant)."""
    stats = {"lignes": 0, "temps_ambigus": 0, "temps_illisibles": 0, "nat_inconnues": 0, "nat_absentes": 0,
             "rangs_illisibles": 0, "temps_non_resolus": 0,
             "codes_inconnus": {}}
    c = _corps(page)
    ed: Dict[str, Any] = {}
    fam, ident = _ids_epr(url)
    if ident:
        ed["epr"] = "%s%d" % (fam, ident)
    m = re.search(r'<h2 class="centre">(.*?)</h2>', c, flags=re.S)
    ed["nom"] = _txt(m.group(1)) if m else None
    m = re.search(r'<p class="p_centre"[^>]*>(.*?)</p>', c, flags=re.S)
    if m:
        ligne = _txt(m.group(1))
        dates = [date_iso(*d) for d in _RE_DATE.findall(ligne)]
        dates = [d for d in dates if d]
        if dates:
            ed["date_debut"], ed["date_fin"] = dates[0], dates[-1]
        sans_dates = _RE_DATE.sub("", ligne)
        parts = [p.strip() for p in sans_dates.split(" - ") if p.strip(" -")]
        if parts:
            ed["pays"] = parts[0]
            if len(parts) > 1:
                ed["lieu"] = " - ".join(parts[1:])
    ed["sections"] = lire_sections(page, stats)
    fiches: Dict[str, str] = {}
    for sec in ed["sections"]:
        for l in sec["lignes"]:
            u = l.pop("_url", None)
            if u and "id_site" in l:
                fiches[str(l["id_site"])] = u
    if fiches:
        ed["fiches"] = fiches                     # {id site: URL de la fiche coureur lue dans les classements}
    ed["stats"] = stats
    return ed


# --------------------------------------------------------------------------------------------------
# Fiches coureurs (identification des coureurs d'avant 2009 : décision du propriétaire du 18/11/2026)
# --------------------------------------------------------------------------------------------------

_RE_JMA = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)? ([A-Za-z]+) (\d{4})$")
_RE_MJA = re.compile(r"^([A-Za-z]+) (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})$")
_RE_MA = re.compile(r"^([A-Za-z]+),? (\d{4})$")
_RE_ANNEE = re.compile(r"^(\d{4})$")
ANNEE_MIN, ANNEE_MAX = 1800, 2010


def parse_naissance(texte: str) -> Tuple[Optional[str], str]:
    """Date de naissance écrite par le site -> (valeur, statut).
    statut : 'jour' (« 11 December 1964 » ou « December 11, 1964 » : date COMPLÈTE, mois en toutes lettres anglaises ->
    AAAA-MM-JJ), 'annee' (« 1893 » seule -> AAAA), 'mois' (mois + année sans jour : jamais complété), 'absent' (vide),
    'inconnu' (tout autre format, dont les dates numériques ambiguës type 03/04/1960 : jamais devinées)."""
    t = re.sub(r"\s+", " ", _html.unescape(texte or "")).strip().strip(".")
    if not t:
        return None, "absent"
    m = _RE_JMA.match(t)
    if m:
        iso = date_iso(m.group(1), m.group(2), m.group(3))
    else:
        m = _RE_MJA.match(t)
        iso = date_iso(m.group(2), m.group(1), m.group(3)) if m else None
    if iso:
        return (iso, "jour") if ANNEE_MIN <= int(iso[:4]) <= ANNEE_MAX else (None, "inconnu")
    m = _RE_ANNEE.match(t)
    if m and ANNEE_MIN <= int(m.group(1)) <= ANNEE_MAX:
        return m.group(1), "annee"
    m = _RE_MA.match(t)
    if m and m.group(1).lower() in MOIS:
        return None, "mois"
    return None, "inconnu"


def lire_fiche(page: str) -> Tuple[Dict[str, Any], str, str]:
    """Fiche coureur -> (contenu, statut de la date, texte brut de la date si format inconnu).
    Deux endroits portent la naissance : la ligne sous le titre (« Italy - 11 December 1964 ») et la phrase de
    présentation (« Franco Ballerini (born 11 December 1964) is… »). Les deux sont lues ; si elles se contredisent
    (ou si l'une est un simple millésime et l'autre une autre année), aucune date n'est retenue (statut 'conflit').
    Contenu : `nom` (tel qu'affiché), `naissance` + `precision` ('jour' | 'annee') si lue, `nationalite` (ISO3, nom de
    pays de la ligne d'en-tête converti par NOMS_PAYS_ISO3) ; `pays_site` (nom anglais lu) pour les statistiques."""
    c = _corps(page)
    out: Dict[str, Any] = {}
    m = re.search(r"<h1[^>]*>(.*?)</h1>\s*<p class=\"p_centre\"[^>]*>(.*?)</p>", c, flags=re.S)
    if not m:
        return out, "absent", ""
    nom = re.sub(r"^Cycling\s*-\s*", "", _txt(m.group(1)))
    if nom:
        out["nom"] = nom
    entete = _txt(m.group(2))
    pays, _, date_txt = entete.partition(" - ")
    if pays.strip():
        out["pays_site"] = pays.strip()
        iso3 = NOMS_PAYS_ISO3.get(pays.strip().lower())
        if iso3:
            out["nationalite"] = iso3
    cand = [parse_naissance(date_txt)]
    mb = re.search(r"\(born ([^)]*)\)", _txt(c[m.end():m.end() + 1500]))
    if mb:
        cand.append(parse_naissance(re.split(r"\s+in\s+", mb.group(1), maxsplit=1)[0]))
    valides = [(v, st) for v, st in cand if v]
    statuts = [st for _, st in cand]
    brut = ""
    if valides:
        distinctes = set(valides)
        if len(distinctes) == 1:
            v, st = valides[0]
        elif len(distinctes) == 2 and {st for _, st in valides} == {"annee", "jour"} and \
                next(v for v, st in valides if st == "annee") == next(v for v, st in valides if st == "jour")[:4]:
            v, st = next((v, st) for v, st in valides if st == "jour")
        else:
            v, st = None, "conflit"
        if v:
            out["naissance"], out["precision"] = v, st
        statut = st
    else:
        for pref in ("inconnu", "mois"):
            if pref in statuts:
                statut = pref
                break
        else:
            statut = "absent"
        if statut == "inconnu":
            brut = date_txt if cand[0][1] == "inconnu" else mb.group(1)
    return out, statut, brut[:80]


# --------------------------------------------------------------------------------------------------
# Réseau, stockage, reprise
# --------------------------------------------------------------------------------------------------

class Session:
    """Requêtes polies (pause par hôte, budget, compteur) ; calendriers et accueil en cache gzip sur disque."""

    def __init__(self, sortie: str, budget_min: float = 0.0, max_pages: int = 0, garder_html: bool = False):
        self.sortie = sortie
        self.garder_html = garder_html      # True : les pages d'édition aussi sont gardées (gzip) -> relecture sans requête
        self.t0 = time.monotonic()
        self.budget_s = budget_min * 60 if budget_min else 0.0
        self.max_pages = max_pages
        self.requetes = 0
        self.echecs = 0
        self.absente = False        # dernière page demandée : 404 / 410 (vrai échec) ; faux = lue, ou panne passagère
        self.statut: Optional[int] = None   # dernier statut HTTP d'une page non lue (404, 503…) ; None = réseau
        self.reussies = 0           # pages lues avec succès pendant ce passage (le site répond : une 5xx est alors propre à la page)
        self.dernier_journal = self.t0

    def epuise(self) -> bool:
        """Budget ou plafond atteint, OU site abandonné pour ce passage (403 / 429 / défi : netutil bloque l'hôte) :
        le passage s'arrête alors net au lieu de parcourir toute la liste en comptant des échecs."""
        if netutil.hote_bloque(BASE):
            return True
        if self.budget_s and time.monotonic() - self.t0 >= self.budget_s:
            return True
        return bool(self.max_pages) and self.requetes >= self.max_pages

    def _cache(self, url: str) -> str:
        return os.path.join(self.sortie, "cache", hashlib.sha1(url.encode()).hexdigest()[:16] + ".html.gz")

    def page(self, rel: str, mettre_en_cache: bool = False) -> Optional[str]:
        url = rel if rel.startswith("http") else BASE + rel
        if mettre_en_cache:
            chemin = self._cache(url)
            if os.path.exists(chemin):
                with gzip.open(chemin, "rt", encoding="utf-8") as f:
                    return f.read()
        self.absente = False
        if self.epuise():
            return None
        self.requetes += 1
        texte = netutil.fetch_text(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        if texte is None:
            self.echecs += 1
            self.absente = netutil.page_absente()
            self.statut = netutil.dernier_statut
            return None
        self.reussies += 1
        if mettre_en_cache:
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            with gzip.open(chemin, "wt", encoding="utf-8") as f:
                f.write(texte)
        return texte

    def echec_de_page(self) -> bool:
        """Vrai si la dernière page non lue est un vrai échec de la page : absente (404 / 410), ou 5xx alors que le site a lu
        d'autres pages pendant ce passage (une 503 permanente sur une seule URL, constatée le 24/11/2026). Une panne générale
        (réseau, site abandonné, aucune page lue) n'en est pas un."""
        if self.absente:
            return True
        return bool(self.statut and self.statut >= 500 and self.reussies > 0)

    def journal(self, message: str, force: bool = False) -> None:
        if force or time.monotonic() - self.dernier_journal >= 300:
            self.dernier_journal = time.monotonic()
            print("[THESPORTS] %s (%d requêtes, %.1f min)" % (message, self.requetes,
                                                              (time.monotonic() - self.t0) / 60))


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


def chemin_edition(sortie: str, cid: str, annee: int, epr: str, deja: Optional[Dict[str, str]] = None) -> str:
    """editions/<id course>/<année>.json ; deux éditions la même année (rare) : suffixe -<epr> sur la seconde."""
    base = os.path.join(sortie, "editions", cid, "%d.json" % annee)
    ex = _lire_json(base, None) if os.path.exists(base) else None
    if ex is not None and ex.get("epr") not in (None, epr):
        return os.path.join(sortie, "editions", cid, "%d-%s.json" % (annee, epr))
    return base


def lire_et_ecrire_edition(sess: Session, cid: str, ed: Dict[str, Any], page: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    url = BASE + ed["url"]
    contenu = lire_edition(page, ed["url"])
    contenu.update({"source": "the-sports.org", "source_url": url, "course_id": cid, "annee": ed["annee"],
                    "lu_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    for k in ("competition", "classe", "vainqueur_calendrier"):
        if meta.get(k):
            contenu[k] = meta[k]
    _ecrire_json(chemin_edition(sess.sortie, cid, ed["annee"], ed["epr"]), contenu, compact=True)
    return contenu


def _maintenant() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fiches_attendues(sortie: str) -> Tuple[Dict[int, str], int]:
    """Coureurs apparaissant dans les éditions collectées : ({id site: URL de la fiche lue dans les classements},
    nombre d'éditions écrites sans `fiches` (anciennes : leurs coureurs ne sont atteignables qu'avec --relire))."""
    out: Dict[int, str] = {}
    sans = 0
    racine = os.path.join(sortie, "editions")
    for dossier, _, fichiers in sorted(os.walk(racine)):
        for nom in sorted(fichiers):
            if not nom.endswith(".json"):
                continue
            ed = _lire_json(os.path.join(dossier, nom), None)
            if not isinstance(ed, dict):
                continue
            f = ed.get("fiches")
            if not f:
                if any("id_site" in l for sec in ed.get("sections", []) for l in sec.get("lignes", [])):
                    sans += 1
                continue
            for k, u in f.items():
                if k.isdigit() and re.fullmatch(r"[A-Za-z0-9._%%-]*-cycling-spf%s\.html" % k, u):
                    out.setdefault(int(k), u)
    return out, sans


ECHECS_MAX = 3   # une fiche absente (404) ou sans titre 3 jours différents n'est plus redemandée (reste sans date : rien d'inventé)
# Règle de comptage des échecs. Seuls comptent une page absente (404 / 410) et une page lue sans titre reconnu ; une panne
# (réseau, 5xx, site abandonné) ne note rien ; au plus un échec par fiche et par jour. Une entrée d'échec sans `regle` ou de
# règle plus ancienne (incident 503 du 18/11/2026 : 2 320 fiches à 3 échecs en un jour) est re-tentée, compteur remis à 0.
REGLE_ECHECS = 2


def _fiche_a_lire(entree: Optional[Dict[str, Any]]) -> bool:
    """Vrai si la fiche est absente du cache, ou en échec de règle ancienne, ou en échec moins de ECHECS_MAX fois (entrée sans `nom`)."""
    if entree is None:
        return True
    if entree.get("nom"):
        return False
    if entree.get("regle", 0) < REGLE_ECHECS:
        return True
    return entree.get("echecs", 0) < ECHECS_MAX


def _noter_echec(cache: Dict[str, Any], i: int) -> None:
    """Compte un échec de la fiche `i` (page absente ou sans titre ; PAS une panne réseau) : `{"echecs", "dernier_essai", "regle"}`.
    Un seul échec par jour (date de `dernier_essai`) ; un compteur de règle ancienne repart de 0."""
    e = cache.get(str(i))
    if e and e.get("nom"):
        return
    maintenant = _maintenant()
    n = (e or {}).get("echecs", 0) if (e or {}).get("regle", 0) >= REGLE_ECHECS else 0
    if n and (e or {}).get("dernier_essai", "")[:10] == maintenant[:10]:
        return
    cache[str(i)] = {"echecs": n + 1, "dernier_essai": maintenant, "regle": REGLE_ECHECS}


def _noter_echec_url(cache: Dict[str, Any], url: str) -> None:
    """Compte un échec de la page de découverte `url` (même règle que les fiches : un par jour, `REGLE_ECHECS`)."""
    e = cache.get(url)
    maintenant = _maintenant()
    n = (e or {}).get("echecs", 0) if (e or {}).get("regle", 0) >= REGLE_ECHECS else 0
    if n and (e or {}).get("dernier_essai", "")[:10] == maintenant[:10]:
        return
    cache[url] = {"echecs": n + 1, "dernier_essai": maintenant, "regle": REGLE_ECHECS}


def decouverte_a_demander(cache: Dict[str, Any], url: str) -> bool:
    """Faux si la page de découverte est abandonnée (ECHECS_MAX jours d'échec, règle à jour) : plus redemandée, ne bloque plus `termine`."""
    e = cache.get(url)
    return e is None or e.get("regle", 0) < REGLE_ECHECS or e.get("echecs", 0) < ECHECS_MAX


def lire_fiches(sess: Session, sortie: str, relire: bool, resume: Dict[str, Any]) -> int:
    """Lit la fiche de chaque coureur des éditions collectées absent de `coureurs.json` (une requête chacun, URL lue
    dans les classements, jamais devinée). Cache écrit tous les 100 coureurs et à l'arrêt. Retourne le nombre restant."""
    chemin = os.path.join(sortie, "coureurs.json")
    cache: Dict[str, Any] = _lire_json(chemin, {})
    attendues, sans = fiches_attendues(sortie)
    resume["editions_sans_fiches"] = sans
    a_lire = [i for i in sorted(attendues) if relire or _fiche_a_lire(cache.get(str(i)))]
    lues, depuis_ecriture = 0, 0
    st = {"jour": 0, "annee": 0, "mois": 0, "absent": 0, "inconnu": 0, "conflit": 0, "pays_inconnus": 0, "echecs": 0, "pannes": 0}
    inconnus: List[str] = []
    try:
        for i in a_lire:
            if sess.epuise():
                break
            page = sess.page(attendues[i])
            if not page:
                if sess.absente:                     # 404 / 410 : vrai échec de la fiche ; sinon panne passagère, rien n'est noté
                    st["echecs"] += 1
                    _noter_echec(cache, i)
                    depuis_ecriture += 1
                else:
                    st["pannes"] += 1
                continue
            fiche, statut, brut = lire_fiche(page)
            lues += 1
            st[statut] += 1
            if "pays_site" in fiche and "nationalite" not in fiche:
                st["pays_inconnus"] += 1
                resume["codes_pays_inconnus"]["fiche:" + fiche["pays_site"]] = \
                    resume["codes_pays_inconnus"].get("fiche:" + fiche["pays_site"], 0) + 1
            fiche.pop("pays_site", None)
            if statut == "inconnu" and len(inconnus) < 20:
                inconnus.append(brut)
            if not fiche.get("nom"):
                st["echecs"] += 1                    # page lue mais sans titre reconnu : échec compté, relue au plus ECHECS_MAX fois
                _noter_echec(cache, i)
                depuis_ecriture += 1
                continue
            fiche["url"] = BASE + attendues[i]
            fiche["lu_le"] = _maintenant()
            cache[str(i)] = fiche
            depuis_ecriture += 1
            if depuis_ecriture >= 100:
                _ecrire_json(chemin, cache, compact=True)
                depuis_ecriture = 0
            sess.journal("fiches coureurs : %d lues, %d restantes" % (lues, len(a_lire) - lues - st["echecs"] - st["pannes"]))
    finally:
        if depuis_ecriture or (cache and not os.path.exists(chemin)):
            _ecrire_json(chemin, cache, compact=True)
    restantes = len([i for i in attendues if _fiche_a_lire(cache.get(str(i)))])
    resume["fiches_lues"] = lues
    resume["fiches_dates"] = st
    if inconnus:
        resume["formats_date_inconnus"] = inconnus
    sess.journal("fiches coureurs : %d lues, %d restantes" % (lues, restantes), force=True)
    return restantes


def lancer(sortie: str, avant: int = AVANT_DEFAUT, depuis: Optional[int] = None, cibles: Optional[List[str]] = None,
           relire: bool = False, budget_min: float = 0.0, decouverte_seule: bool = False,
           max_pages: int = 0, sans_decouverte: bool = False, garder_html: bool = False,
           fiches: bool = True) -> Dict[str, Any]:
    """Découverte (calendriers -> courses), lecture des éditions de la période, puis des fiches des coureurs qui y figurent.
    Reprenable ; écrit `etat.json` (termine, editions_restantes, coureurs_restants) en fin de passage."""
    sess = Session(sortie, budget_min, max_pages, garder_html)
    cibles = [c.strip().lower() for c in (cibles or []) if c.strip()]
    chemin_courses = os.path.join(sortie, "courses.json")
    reg = _lire_json(chemin_courses, {"source": "the-sports.org", "courses": {}})
    courses: Dict[str, Dict[str, Any]] = reg.setdefault("courses", {})
    epr_vers_cid = {e["epr"]: cid for cid, c in courses.items() for e in c.get("editions", [])}
    decouverte_ok = True               # False dès qu'un calendrier ou une page de découverte manque (budget, panne), sauf page abandonnée
    chemin_dec = os.path.join(sortie, "decouverte_echecs.json")
    dec_echecs: Dict[str, Any] = _lire_json(chemin_dec, {})
    dec_modifie = [False]

    def echec_decouverte(url: str, raison: str) -> None:
        """Page de découverte non lue : vrai échec (404 / 410, 5xx isolée, structure illisible) = noté, une fois par jour ;
        panne passagère = rien noté. Dans les deux cas la découverte n'est pas complète pour ce passage."""
        nonlocal decouverte_ok
        decouverte_ok = False
        resume["decouverte_incomplete"][raison] = resume["decouverte_incomplete"].get(raison, 0) + 1
        if raison == "structure illisible" or sess.echec_de_page():
            avant_n = dec_echecs.get(url, {}).get("echecs", 0)
            _noter_echec_url(dec_echecs, url)
            dec_modifie[0] = True
            if dec_echecs[url]["echecs"] > avant_n:
                print("[THESPORTS] [WARN] découverte : échec %d/%d de %s (%s)" % (dec_echecs[url]["echecs"], ECHECS_MAX, url, raison))
    resume = {"calendriers": 0, "courses": 0, "editions_lues": 0, "editions_deja": 0, "echecs": 0, "refus": {},
              "lignes": 0, "temps_ambigus": 0, "temps_illisibles": 0, "temps_non_resolus": 0, "nat_inconnues": 0,
              "codes_pays_inconnus": {}, "decouverte_incomplete": {}, "decouverte_abandonnees": 0}

    def cible_ok(cid: str, texte: str) -> bool:
        if not cibles:
            return True
        return any(t == cid.lower() or (not re.fullmatch(r"[se]\d+", t) and t in texte.lower()) for t in cibles)

    def enregistrer(cid: str, ed: Dict[str, Any], page: str, meta: Dict[str, Any]) -> None:
        c = lire_et_ecrire_edition(sess, cid, ed, page, meta)
        resume["editions_lues"] += 1
        for k in ("lignes", "temps_ambigus", "temps_illisibles", "temps_non_resolus", "nat_inconnues"):
            resume[k] += c["stats"][k]
        for code, n in c["stats"].get("codes_inconnus", {}).items():
            resume["codes_pays_inconnus"][code] = resume["codes_pays_inconnus"].get(code, 0) + n

    # --- découverte : calendriers annuels (du plus récent au plus ancien) -> courses
    accueil = None if sans_decouverte else sess.page(ACCUEIL, mettre_en_cache=True)
    lien = lien_calendrier(accueil) if accueil else None
    annees = {}
    if lien:
        p = sess.page(lien, mettre_en_cache=True)
        annees = lire_annees_calendrier(p) if p else {}
    if not annees and not sans_decouverte:
        decouverte_ok = False
        print("[THESPORTS] [WARN] liste des années introuvable : découverte impossible")
    for annee in sorted((a for a in annees if a < avant and (depuis is None or a >= depuis)), reverse=True):
        if sess.epuise():
            decouverte_ok = False
            break
        if not decouverte_a_demander(dec_echecs, annees[annee]):
            resume["decouverte_abandonnees"] += 1
            continue
        page = sess.page(annees[annee], mettre_en_cache=True)
        if not page:
            echec_decouverte(annees[annee], "calendrier %d" % annee)
            continue
        resume["calendriers"] += 1
        for lg in lire_calendrier(page, annee):
            ok, raison = ligne_retenue(lg)
            if not ok:
                resume["refus"][raison] = resume["refus"].get(raison, 0) + 1
                continue
            cle = "%s%d" % (lg["famille"], lg["epr"])
            if cle in epr_vers_cid:
                cid = epr_vers_cid[cle]
                if courses[cid].get("competition") is None:
                    courses[cid]["competition"] = lg["competition"]
                continue
            if cibles and not any(t in lg["url"].lower() for t in cibles if not re.fullmatch(r"[se]\d+", t)):
                if not any(re.fullmatch(r"[se]\d+", t) for t in cibles):
                    continue
            if sess.epuise():
                decouverte_ok = False
                break
            # édition inconnue : on la lit (elle est à intégrer de toute façon) pour obtenir l'onglet « Archives »
            if not decouverte_a_demander(dec_echecs, lg["url"]):
                resume["decouverte_abandonnees"] += 1
                continue
            page_ed = sess.page(lg["url"], sess.garder_html)
            if not page_ed:
                echec_decouverte(lg["url"], "page d'édition")
                continue
            editions = lire_archives(page_ed)
            cid = id_course(page_ed, editions)
            if not cid:
                echec_decouverte(lg["url"], "structure illisible")
                resume["refus"]["course sans id"] = resume["refus"].get("course sans id", 0) + 1
                continue
            if cibles and not cible_ok(cid, lg["url"] + " " + lg["nom"]):
                continue
            c = courses.setdefault(cid, {"id": cid, "nom": lg["nom"], "pays_site": lg["pays_site"],
                                         "competition": lg["competition"], "editions": []})
            c["nom"] = lg["nom"]
            c["noms"] = sorted({e["nom"] for e in editions})
            c["editions"] = editions
            c["url_edition_vue"] = lg["url"]
            for e in editions:
                epr_vers_cid[e["epr"]] = cid
            ed = next((e for e in editions if e["epr"] == cle), None)
            if ed and ed["annee"] < avant and (depuis is None or ed["annee"] >= depuis):
                enregistrer(cid, ed, page_ed, {"competition": lg["competition"], "classe": lg["classe"],
                                               "vainqueur_calendrier": lg["vainqueur"]})
            _ecrire_json(chemin_courses, reg)
            sess.journal("découverte : %d courses" % len(courses))
    resume["courses"] = len(courses)
    _ecrire_json(chemin_courses, reg)
    if dec_modifie[0]:
        _ecrire_json(chemin_dec, dec_echecs)
    abandonnees = sorted(u for u in dec_echecs if not decouverte_a_demander(dec_echecs, u))
    if abandonnees:
        resume["decouverte_pages_abandonnees"] = abandonnees
        print("[THESPORTS] [WARN] %d page(s) de découverte abandonnée(s) après %d jours d'échec : %s"
              % (len(abandonnees), ECHECS_MAX, ", ".join(abandonnees)))

    # --- lecture des éditions restantes
    if not decouverte_seule:
        for cid, c in sorted(courses.items()):
            if not cible_ok(cid, c.get("nom", "") + " " + c.get("url_edition_vue", "")):
                continue
            for ed in c.get("editions", []):
                if ed["annee"] >= avant or (depuis is not None and ed["annee"] < depuis):
                    continue
                chemin = chemin_edition(sortie, cid, ed["annee"], ed["epr"])
                if os.path.exists(chemin) and not relire:
                    resume["editions_deja"] += 1
                    continue
                if sess.epuise():
                    break
                page = sess.page(ed["url"], sess.garder_html)
                if not page:
                    continue
                enregistrer(cid, ed, page, {})
                sess.journal("lecture : %d éditions lues" % resume["editions_lues"])
            if sess.epuise():
                break
    # --- éditions restantes (après la lecture : chemins réels sur disque)
    editions_restantes = 0
    for cid, c in courses.items():
        if not cible_ok(cid, c.get("nom", "") + " " + c.get("url_edition_vue", "")):
            continue
        for ed in c.get("editions", []):
            if ed["annee"] >= avant or (depuis is not None and ed["annee"] < depuis):
                continue
            if not os.path.exists(chemin_edition(sortie, cid, ed["annee"], ed["epr"])):
                editions_restantes += 1

    # --- fiches des coureurs (après les éditions : les éditions manquantes passent d'abord)
    if fiches and not decouverte_seule:
        coureurs_restants = lire_fiches(sess, sortie, relire, resume)
    else:
        attendues, _ = fiches_attendues(sortie)
        cache = _lire_json(os.path.join(sortie, "coureurs.json"), {})
        coureurs_restants = len([i for i in attendues if _fiche_a_lire(cache.get(str(i)))])
    resume["echecs"] = sess.echecs
    resume["requetes"] = sess.requetes
    resume["duree_min"] = round((time.monotonic() - sess.t0) / 60, 1)
    resume["budget_epuise"] = sess.epuise()
    termine = bool(decouverte_ok and not editions_restantes and not coureurs_restants and fiches and not decouverte_seule)
    # etat.json : lu par le workflow (auto-relance) ; aucun horodatage, pour qu'un passage sans effet ne change rien
    _ecrire_json(os.path.join(sortie, "etat.json"), {"termine": termine, "editions_restantes": editions_restantes,
                                                     "coureurs_restants": coureurs_restants})
    resume["editions_restantes"], resume["coureurs_restants"], resume["termine"] = \
        editions_restantes, coureurs_restants, termine
    sess.journal("synthèse : %s" % json.dumps(resume, ensure_ascii=False, sort_keys=True), force=True)
    return resume


# --------------------------------------------------------------------------------------------------
# Tests sans réseau (pages réelles enregistrées dans tools/fixtures/thesports/)
# --------------------------------------------------------------------------------------------------

def _fixture(nom: str) -> str:
    with open(os.path.join(FIXTURES, nom), encoding="utf-8") as f:
        return f.read()


def _tests() -> None:
    # 503 : indisponibilité passagère (page d'erreur Cloudflare « cf- ») != défi anti-robot ; un vrai défi bloque toujours l'hôte
    assert not netutil._looks_like_challenge(503, "<html>cf-ray 12ab Service Unavailable</html>")
    assert netutil._looks_like_challenge(503, "<title>Just a moment...</title>")
    assert netutil._looks_like_challenge(403, "cf-error-details") and not netutil._looks_like_challenge(404, "Just a moment")
    netutil._blocked_hosts.add("hote-test.invalid")
    assert netutil.hote_bloque("https://hote-test.invalid/x") and not netutil.hote_bloque(BASE)
    netutil._blocked_hosts.discard("hote-test.invalid")
    # temps
    assert parse_temps("6h27'08\"")[:2] == ("valeur", 6 * 3600 + 27 * 60 + 8)
    assert parse_temps("4h18'56")[:2] == ("valeur", 4 * 3600 + 18 * 60 + 56)
    assert parse_temps("4h35'42''")[:2] == ("valeur", 4 * 3600 + 35 * 60 + 42)
    assert parse_temps("6u05'23\"")[:2] == ("valeur", 6 * 3600 + 5 * 60 + 23)
    assert parse_temps("1'56\"")[:2] == ("valeur", 116)
    assert parse_temps("4h12'51' (48.764 km/h)") == ("valeur", 4 * 3600 + 12 * 60 + 51, 48.764)
    assert parse_temps("t.s.t.")[0] == "illisible"
    assert parse_temps("1'20")[:2] == ("valeur", 80)
    assert parse_temps("35''")[:2] == ("valeur", 35)
    assert parse_temps("8")[:2] == ("valeur", 8)
    assert parse_temps("8", en_temps=False)[0] == "illisible"
    assert parse_temps("0:06:12")[:2] == ("valeur", 372)
    assert parse_temps("89:40:27")[:2] == ("valeur", 89 * 3600 + 40 * 60 + 27)
    assert parse_temps("00:13")[:2] == ("valeur", 13)
    assert parse_temps("4h29'58'' (40.116 km/h)") == ("valeur", 4 * 3600 + 29 * 60 + 58, 40.116)
    assert parse_temps("s.t.")[0] == "meme" and parse_temps("s.t..")[0] == "meme" and parse_temps("m.t.")[0] == "meme"
    assert parse_temps("8.17.00 (51.43 km/h)") == ("ambigu", None, 51.43)
    assert parse_temps("0.00.73")[0] == "ambigu"
    assert parse_temps("-1 Lap")[0] == "illisible"
    assert parse_temps("3'75")[0] == "illisible"              # secondes hors plage
    assert parse_temps("")[0] == "vide"
    assert parse_temps("+ 00' 00")[:2] == ("valeur", 0) and parse_temps("+ 01' 05")[:2] == ("valeur", 65)
    assert parse_temps("5h 49' 18")[:2] == ("valeur", 5 * 3600 + 49 * 60 + 18)
    assert parse_temps("57' 34")[:2] == ("valeur", 57 * 60 + 34)
    assert parse_temps("1412 km 37h35'39''")[:2] == ("valeur", 37 * 3600 + 35 * 60 + 39)

    # titres
    t = lire_titre_section("Stage 8a - Mandelieu la Napoule-Nice - 91.4 km - 12 March 1995", ["Sprint"])
    assert (t["type"], t["etape"], t["distance_km"], t["date"], t["profil"]) == ("etape", "8a", 91.4, "1995-03-12", "Sprint")
    assert t["parcours"] == "Mandelieu la Napoule-Nice" and "depart" not in t   # tiret sans espaces : pas de découpage
    t = lire_titre_section("Stage 1 - Dublin - Dublin, 180.5 km - 12 July 1998", ["Sprint"])
    assert (t["depart"], t["arrivee"], t["distance_km"]) == ("Dublin", "Dublin", 180.5)
    t = lire_titre_section("Prologue - Dublin (Irl), 5.6 kM - 11 July 1998", ["Time Trial"])
    assert (t["type"], t["etape"], t["distance_km"], t["parcours"], t["contre_la_montre"]) == \
        ("prologue", "P", 5.6, "Dublin (Irl)", True)
    t = lire_titre_section("Stage 1 - 2 July 2006", ["Sprint"])
    assert t["type"] == "etape" and "parcours" not in t and t["date"] == "2006-07-02"
    assert lire_titre_section("General Classification - 3 August 1998", [])["type"] == "general"
    assert lire_titre_section("Final Ranking - 23 July 2006", [])["type"] == "general"
    assert lire_titre_section("Ranking by points - 3 August 1998", [])["type"] == "points"
    assert lire_titre_section("Mountains classification - 23 July 2006", [])["type"] == "montagne"

    # calendrier 1995
    cal = lire_calendrier(_fixture("calendrier_1995.html"), 1995)
    assert len(cal) >= 90, len(cal)
    pr = [x for x in cal if x["epr"] == 9234][0]
    assert (pr["nom"], pr["competition"], pr["famille"], pr["date"].strip(), pr["pays_site"]) == \
        ("Paris-Roubaix", "World Tour", "epr", "09/04", "FRA"), pr
    assert ligne_retenue(pr)[0]
    assert not ligne_retenue({"famille": "epm", "competition": "World Championships", "nom": "World Junior Championships - Road"})[0]
    assert not ligne_retenue({"famille": "epr", "competition": "U23 events", "nom": "Ronde"})[0]
    assert not ligne_retenue({"famille": "epf", "competition": "World Tour", "nom": "X"})[0]
    assert lien_calendrier('<a href="cycling-calendar-2024-s2-c0-b0-u329.html">Calendar 2024</a>') == \
        "cycling-calendar-2024-s2-c0-b0-u329.html"
    annees = lire_annees_calendrier(_fixture("calendrier_1995.html"))
    assert annees[1995] == "cycling-calendar-1995-s2-c0-b0-u24.html"
    assert 1990 in annees and 2008 in annees

    # Paris-Roubaix 1995 : course d'un jour
    page = _fixture("paris_roubaix_1995.html")
    arch = lire_archives(page)
    assert arch[0]["annee"] == 1896 and arch[-1]["annee"] == 2026 and len(arch) >= 120
    assert [a for a in arch if a["annee"] == 1995][0]["epr"] == "epr9234"
    assert id_course(page, arch) == "s43"
    ed = lire_edition(page, "cycling-paris-roubaix-results-1995-epr9234.html")
    assert (ed["nom"], ed["date_debut"], ed["date_fin"], ed["pays"]) == ("Paris-Roubaix 1995", "1995-04-09", "1995-04-09", "France")
    assert len(ed["sections"]) == 1 and ed["sections"][0]["type"] == "final"
    lg = ed["sections"][0]["lignes"]
    assert len(lg) == 90, len(lg)
    assert [l["nom"] for l in lg[:3]] == ["Franco Ballerini", "Andrei Tchmil", "Johan Museeuw"]
    assert [l["nat"] for l in lg[:3]] == ["ITA", "MDA", "BEL"]
    assert lg[0]["equipe"] == "Mapei - GB" and lg[0]["id_site"] == 46384
    assert lg[0]["temps_s"] == 6 * 3600 + 27 * 60 + 8 and lg[0]["ecart_s"] == 0
    assert lg[1]["ecart_s"] == 116 and "temps_s" not in lg[1]
    assert lg[2]["meme_temps"] and lg[2]["ecart_s"] == 116        # s.t. = écart de la ligne précédente
    assert lg[5]["ecart_s"] == 120
    assert ed["stats"]["temps_illisibles"] == 0 and ed["stats"]["nat_inconnues"] == 0, ed["stats"]

    # Tour de France 1998 : classement général + points + montagne + prologue + étapes (extrait des étapes 1 à 5)
    page = _fixture("tour_de_france_1998.html")
    ed = lire_edition(page, "cycling-tour-de-france-results-1998-epr15611.html")
    types = [s["type"] for s in ed["sections"]]
    assert types[:5] == ["general", "points", "montagne", "prologue", "etape"], types
    gc = ed["sections"][0]["lignes"]
    assert [l["nom"] for l in gc[:3]] == ["Marco Pantani", "Jan Ullrich", "Bobby Julich"] and len(gc) == 96
    assert gc[0]["temps_s"] == 92 * 3600 + 49 * 60 + 46 and gc[1]["ecart_s"] == 201 and gc[2]["ecart_s"] == 248
    assert gc[94]["ecart_s"] == 2 * 3600 + 44 * 60 + 42 and gc[94]["nom"] == "Mario Traversoni"
    assert gc[95]["ecart_s"] == 3 * 3600 + 12 * 60 + 15 and gc[95]["nom"] == "Damien Nazon"
    pts = ed["sections"][1]["lignes"]
    assert pts[0]["nom"] == "Erik Zabel" and pts[0]["points"] == 327 and "ecart_s" not in pts[0]
    pro = ed["sections"][3]
    assert pro["etape"] == "P" and pro["lignes"][0]["temps_s"] == 372 and pro["lignes"][1]["temps_s"] == 376
    assert pro["lignes"][1]["ecart_s"] == 4                          # temps absolu publié : écart recalculé
    e1 = ed["sections"][4]
    assert (e1["etape"], e1["depart"], e1["arrivee"], e1["distance_km"], e1["date"]) == \
        ("1", "Dublin", "Dublin", 180.5, "1998-07-12")
    assert e1["lignes"][0]["nom"] == "Tom Steels" and e1["lignes"][0]["vitesse_kmh"] == 40.116
    assert e1["lignes"][0]["temps_s"] == 4 * 3600 + 29 * 60 + 58 and e1["lignes"][1]["meme_temps"]
    assert e1["lignes"][1]["ecart_s"] == 0
    assert [l["nat"] for l in gc[:4]] == ["ITA", "GER", "USA", "FRA"]
    assert ed["date_debut"] == "1998-07-11" and ed["date_fin"] == "1998-08-03"
    assert id_course(page, lire_archives(page)) == "s94"
    arch = lire_archives(page)
    assert len(arch) >= 100 and [a["annee"] for a in arch if a["annee"] in (1998, 1999, 2005)] == [1998, 1999, 2005]

    # Paris-Nice 1995 : « 4h18'56 », « 1'20 », « 8 » (secondes), « s.t.. », étape sans résultat
    page = _fixture("paris_nice_1995.html")
    ed = lire_edition(page, "cycling-paris-nice-results-1995-epr34463.html")
    st = {s["etape"]: s for s in ed["sections"] if s["type"] == "etape"}
    assert st["1"]["lignes"][0]["temps_s"] == 4 * 3600 + 18 * 60 + 56 and st["1"]["lignes"][1]["meme_temps"]
    assert st["2"]["lignes"][1]["ecart_s"] == 80
    assert st["5"]["lignes"][1]["ecart_s"] == 8 and st["5"]["lignes"][0]["nat"] == "USA"
    assert st["4"]["lignes"] == []
    assert st["8b"]["profil"] == "Time Trial" and st["8b"]["lignes"][0]["temps_s"] == 22 * 60 + 32
    assert st["8b"]["distance_km"] == 12.5 and st["8a"]["distance_km"] == 91.4
    gc = [s for s in ed["sections"] if s["type"] == "general"][0]["lignes"]
    assert gc[0]["nom"] == "Laurent Jalabert" and gc[1]["ecart_s"] == 100 and len(gc) == 99

    # Championnats du monde 1995 (plusieurs courses sur la page ; « -1 Lap », lignes sans temps) et nationaux de France
    ed = lire_edition(_fixture("championnats_monde_1995.html"), "cycling-world-championships-results-1995-men-epm11957.html")
    assert [s["type"] for s in ed["sections"]] == ["autre", "autre", "autre"]
    clm, route, amateur = ed["sections"]
    assert clm["lignes"][0]["nom"] == "Miguel Indurain Larraya" and clm["lignes"][1]["temps_s"] == 56 * 60 + 19
    assert clm["lignes"][1]["ecart_s"] == 49
    assert route["lignes"][0]["temps_s"] == 7 * 3600 + 9 * 60 + 55 and route["lignes"][1]["ecart_s"] == 35
    assert amateur["lignes"][-1].get("brut") is None             # ligne sans temps : rien d'inventé
    assert ed["pays"] == "Colombia" and ed["lieu"] == "Tunja"
    ed = lire_edition(_fixture("championnat_france_1995.html"), "cycling-french-national-championships-results-1995-epr21736.html")
    l0 = ed["sections"][0]["lignes"]
    assert l0[0]["nom"] == "Eddy Seigneur" and l0[0]["temps_s"] == 6 * 3600 + 5 * 60 + 23 and l0[1]["ecart_s"] == 1

    # Tour 2006 : points séparés ambigus, jamais interprétés
    ed = lire_edition(_fixture("tour_de_france_2006.html"), "cycling-tour-de-france-results-2006-epr3759.html")
    gc = ed["sections"][0]["lignes"]
    assert gc[0]["temps_s"] == 89 * 3600 + 40 * 60 + 27 and gc[1]["ecart_s"] == 32
    pro = [s for s in ed["sections"] if s["type"] == "prologue"][0]
    assert "temps_s" not in pro["lignes"][0] and pro["lignes"][0]["brut"].startswith("8.17.00")
    assert ed["stats"]["temps_ambigus"] > 0

    # stockage : une édition écrite n'est jamais relue (chemin stable), deux éditions la même année séparées
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = chemin_edition(d, "s43", 1995, "epr9234")
        assert p.endswith(os.path.join("editions", "s43", "1995.json"))
        _ecrire_json(p, {"epr": "epr9234"})
        assert chemin_edition(d, "s43", 1995, "epr9234") == p
        assert chemin_edition(d, "s43", 1995, "epr1").endswith("1995-epr1.json")

    # fiches coureurs : dates complètes seulement
    assert parse_naissance("11 December 1964") == ("1964-12-11", "jour")
    assert parse_naissance("7 September 1973") == ("1973-09-07", "jour")
    assert parse_naissance("December 11, 1964") == ("1964-12-11", "jour")
    assert parse_naissance("1 march 1950") == ("1950-03-01", "jour")
    assert parse_naissance("1893") == ("1893", "annee")
    assert parse_naissance("March 1950") == (None, "mois")
    assert parse_naissance("") == (None, "absent")
    assert parse_naissance("31 February 1950") == (None, "inconnu")          # date impossible
    assert parse_naissance("03/04/1960") == (None, "inconnu")                # numérique : ambigu, jamais deviné
    assert parse_naissance("11 Dec 1964") == (None, "inconnu")               # mois abrégé : format inconnu
    assert parse_naissance("11 December 1064") == (None, "inconnu")
    f, st, _ = lire_fiche(_fixture("fiche_ballerini.html"))
    assert st == "jour" and f == {"nom": "Franco Ballerini", "naissance": "1964-12-11", "precision": "jour",
                                  "nationalite": "ITA", "pays_site": "Italy"}, f
    f, st, _ = lire_fiche(_fixture("fiche_wiggins.html"))                    # « (born 28 April 1980 in Ghent) »
    assert st == "jour" and f["naissance"] == "1980-04-28" and f["nationalite"] == "GBR", f
    f, st, _ = lire_fiche(_fixture("fiche_sans_date.html"))
    assert st == "absent" and "naissance" not in f and "precision" not in f and f["nom"] == "Jean De Busscher" \
        and f["nationalite"] == "BEL", f
    base = _fixture("fiche_ballerini.html")
    f, st, _ = lire_fiche(base.replace("(born 11 December 1964)", "(born 12 December 1964)"))
    assert st == "conflit" and "naissance" not in f                          # deux sources discordantes : rien
    f, st, _ = lire_fiche(base.replace("Italy - 11 December 1964", "Italy - 1964"))
    assert st == "jour" and f["naissance"] == "1964-12-11"                   # millésime + jour de la même année
    f, st, brut = lire_fiche(base.replace("11 December 1964", "11/12/64").replace("(born 11/12/64)", "(born unknown)"))
    assert st == "inconnu" and "naissance" not in f and brut == "11/12/64", (st, f, brut)
    assert lire_fiche("<html>rien</html>")[1] == "absent"
    # SCO -> GBR (nationalité sportive UCI)
    assert pays_normalise("SCO", "thesports") == "GBR"
    tr = ('<tr><td>1</td><td><img alt="SCO" src="x"/><a href="https://www.the-sports.org/jean-dupont-cycling-spf12.html">'
          'Jean Dupont</a> (SCO)</td><td>Equipe</td><td>1h00\'00</td></tr>')
    l = lire_ligne(tr)
    assert l["nat"] == "GBR" and l["nat_site"] == "SCO" and l["id_site"] == 12 and l["_url"].endswith("-cycling-spf12.html")
    # l'édition porte les URL des fiches lues dans les classements
    ed = lire_edition(_fixture("paris_roubaix_1995.html"), "cycling-paris-roubaix-results-1995-epr9234.html")
    assert ed["fiches"]["46384"].endswith("franco-ballerini-cycling-spf46384.html") and len(ed["fiches"]) == 90
    assert all("_url" not in l for s_ in ed["sections"] for l in s_["lignes"])

    # phase fiches : éditions sans réseau, fiches servies par un Session simulé ; jamais relues ; budget ; cache ; etat
    with tempfile.TemporaryDirectory() as d:
        ed_min = {"epr": "epr1", "fiches": {"46384": "franco-ballerini-cycling-spf46384.html",
                                            "54603": "jean-de-busscher-cycling-spf54603.html",
                                            "952": "bradley-wiggins-cycling-spf952.html", "7": "../evil.html"},
                  "sections": [{"lignes": [{"id_site": 46384}]}]}
        _ecrire_json(os.path.join(d, "editions", "s43", "1995.json"), ed_min)
        _ecrire_json(os.path.join(d, "editions", "s43", "1993.json"), {"epr": "epr0", "sections": [{"lignes": [{"id_site": 5}]}]})
        att, sans = fiches_attendues(d)
        assert sorted(att) == [952, 46384, 54603] and sans == 1, (att, sans)     # URL douteuse écartée

        class Faux(Session):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.demandees = []

            def page(self, rel, mettre_en_cache=False):
                if self.epuise():
                    return None
                self.requetes += 1
                self.demandees.append(rel)
                self.absente = False
                return _fixture({"46384": "fiche_ballerini.html", "54603": "fiche_sans_date.html"}.get(
                    re.search(r"spf(\d+)", rel).group(1), "fiche_wiggins.html"))

        res = {"codes_pays_inconnus": {}}
        sess = Faux(d, max_pages=2)
        assert lire_fiches(sess, d, False, res) == 1 and sess.requetes == 2          # plafond de requêtes : 1 reste
        cache = _lire_json(os.path.join(d, "coureurs.json"), {})
        assert sorted(cache) == ["46384", "952"], sorted(cache)                      # ordre d'id croissant
        sess = Faux(d)
        assert lire_fiches(sess, d, False, res) == 0 and len(sess.demandees) == 1    # la fiche déjà lue n'est pas relue
        cache = _lire_json(os.path.join(d, "coureurs.json"), {})
        assert cache["46384"]["naissance"] == "1964-12-11" and cache["46384"]["precision"] == "jour"
        assert cache["46384"]["url"].endswith("franco-ballerini-cycling-spf46384.html") and cache["46384"]["lu_le"]
        assert "naissance" not in cache["54603"] and cache["54603"]["nom"] == "Jean De Busscher"
        # fiche en échec : un seul échec par jour ; ECHECS_MAX jours différents puis abandonnée (jamais de date inventée)
        c2: Dict[str, Any] = {}
        _noter_echec(c2, 7)
        _noter_echec(c2, 7)                                                          # 2e essai le même jour : pas de 2e échec
        assert c2["7"]["echecs"] == 1 and c2["7"]["regle"] == REGLE_ECHECS and _fiche_a_lire(c2["7"])
        for _ in range(ECHECS_MAX - 1):
            c2["7"]["dernier_essai"] = "2026-01-01T00:00:00Z"                        # jours précédents
            _noter_echec(c2, 7)
        assert c2["7"]["echecs"] == ECHECS_MAX and not _fiche_a_lire(c2["7"]) and "naissance" not in c2["7"]
        # entrée ancienne (sans `regle`, ou règle plus ancienne) : à relire, compteur remis à 0 au prochain échec
        ancien = {"echecs": 3, "dernier_essai": "2026-11-18T11:00:00Z"}
        assert _fiche_a_lire(ancien) and _fiche_a_lire(dict(ancien, regle=REGLE_ECHECS - 1))
        assert not _fiche_a_lire(dict(ancien, regle=REGLE_ECHECS))
        c2["9"] = dict(ancien)
        _noter_echec(c2, 9)
        assert c2["9"]["echecs"] == 1 and c2["9"]["regle"] == REGLE_ECHECS
        # panne (503, réseau) : rien n'est noté ; 404 : un échec
        class Panne(Session):
            def __init__(self, *a, statut=None, **k):
                super().__init__(*a, **k)
                self.statut = statut

            def page(self, rel, mettre_en_cache=False):
                self.requetes += 1
                self.absente = self.statut in (404, 410)
                return None
        d2 = os.path.join(d, "pannes")
        _ecrire_json(os.path.join(d2, "editions", "s43", "1995.json"), ed_min)
        _ecrire_json(os.path.join(d2, "coureurs.json"), {"952": dict(ancien)})
        sp = Panne(d2, statut=503)
        assert lire_fiches(sp, d2, False, res) == 3                                   # 952 (ancienne) + 2 autres, toutes à lire
        assert _lire_json(os.path.join(d2, "coureurs.json"), {}) == {"952": dict(ancien)}   # 503 : rien noté, ancienne intacte
        sp = Panne(d2, statut=404)
        assert lire_fiches(sp, d2, False, res) == 3
        c404 = _lire_json(os.path.join(d2, "coureurs.json"), {})
        assert all(c404[k]["echecs"] == 1 and c404[k]["regle"] == REGLE_ECHECS for k in ("952", "46384", "54603")), c404
        sp = Panne(d2, statut=404)
        lire_fiches(sp, d2, False, res)                                               # même jour : toujours 1 échec
        assert _lire_json(os.path.join(d2, "coureurs.json"), {})["952"]["echecs"] == 1
        c2["8"] = {"nom": "X Y"}
        _noter_echec(c2, 8)
        assert c2["8"] == {"nom": "X Y"} and not _fiche_a_lire(c2["8"])
        sess = Faux(d)
        assert lire_fiches(sess, d, False, res) == 0 and not sess.demandees
        sess = Faux(d)
        lire_fiches(sess, d, True, res)
        assert len(sess.demandees) == 3                                              # --relire : tout est relu
        # --- découverte : une page de découverte en échec ne bloque plus `termine` une fois abandonnée
        globals_ = globals()
        orig = {k: globals_[k] for k in ("lien_calendrier", "lire_annees_calendrier", "lire_fiches")}
        orig_fetch, orig_stat = netutil.fetch_text, netutil.dernier_statut
        globals_["lien_calendrier"] = lambda page: "cal"
        globals_["lire_annees_calendrier"] = lambda page: {1995: "cal1995", 1994: "cal1994"}
        globals_["lire_fiches"] = lambda sess, sortie, relire, resume: 0
        statut_1994 = [404]
        demandees: List[str] = []

        def faux_fetch(url, **kw):
            demandees.append(url)
            if url.endswith("/cal1994"):
                netutil.dernier_statut = statut_1994[0]
                return None
            netutil.dernier_statut = 200
            if url.endswith("/cal1995"):
                return _fixture("calendrier_1995.html")
            return _fixture("paris_roubaix_1995.html")
        netutil.fetch_text = faux_fetch
        try:
            def passage(dossier):
                del demandees[:]
                r = lancer(dossier, avant=2009, fiches=True)
                return r, _lire_json(os.path.join(dossier, "decouverte_echecs.json"), {}), \
                    _lire_json(os.path.join(dossier, "etat.json"), {})
            d3 = os.path.join(d, "decouverte")
            r, ech, etat = passage(d3)
            assert not r["termine"] and not etat["termine"] and ech["cal1994"]["echecs"] == 1, (r, ech)
            assert ech["cal1994"]["regle"] == REGLE_ECHECS
            r, ech, etat = passage(d3)                                                  # même jour : toujours 1 échec
            assert ech["cal1994"]["echecs"] == 1 and not etat["termine"]
            for _ in range(ECHECS_MAX - 1):                                              # jours précédents
                ech["cal1994"]["dernier_essai"] = "2026-01-01T00:00:00Z"
                _ecrire_json(os.path.join(d3, "decouverte_echecs.json"), ech)
                r, ech, etat = passage(d3)
            assert ech["cal1994"]["echecs"] == ECHECS_MAX and not etat["termine"], ech   # 3e échec : abandonnée à la fin
            r, ech, etat = passage(d3)
            assert etat["termine"] and r["decouverte_abandonnees"] == 1, (r, etat)      # abandonnée : ne bloque plus termine
            assert not any(u.endswith("/cal1994") for u in demandees) and r["decouverte_pages_abandonnees"] == ["cal1994"]
            # 503 isolée alors que d'autres pages sont lues : un vrai échec ; panne sans statut (réseau) : rien noté
            statut_1994[0] = 503
            r, ech, etat = passage(os.path.join(d, "decouverte503"))
            assert ech["cal1994"]["echecs"] == 1 and not etat["termine"]
            statut_1994[0] = None
            r, ech, etat = passage(os.path.join(d, "decouverte_reseau"))
            assert ech == {} and not etat["termine"], ech
        finally:
            netutil.fetch_text, netutil.dernier_statut = orig_fetch, orig_stat
            globals_.update(orig)
    print("thesports : tests OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--test", action="store_true", help="tests sans réseau")
    ap.add_argument("--sortie", default=SORTIE_DEFAUT, help="dossier de sortie (défaut : ARCHIVES_DIR/sources/thesports)")
    ap.add_argument("--avant", type=int, default=AVANT_DEFAUT, help="éditions strictement avant cette année (défaut 2009)")
    ap.add_argument("--depuis", type=int, default=None, help="éditions à partir de cette année")
    ap.add_argument("--courses", default="", help="liste : id de course (s43) ou fragment d'URL (paris-roubaix)")
    ap.add_argument("--relire", action="store_true", help="relire aussi les éditions déjà écrites")
    ap.add_argument("--budget-min", type=float, default=0.0, help="budget de temps en minutes (0 = illimité)")
    ap.add_argument("--max-requetes", "--max-pages", dest="max_requetes", type=int, default=0,
                    help="plafond de requêtes du passage, découverte + éditions + fiches (0 = illimité ; essais)")
    ap.add_argument("--sans-fiches", action="store_true", help="ne lit pas les fiches des coureurs (éditions seulement)")
    ap.add_argument("--sans-decouverte", action="store_true", help="ne relit pas les calendriers : éditions des courses de courses.json")
    ap.add_argument("--garder-html", action="store_true", help="garde les pages d'édition (gzip, cache/) : relecture sans requête")
    ap.add_argument("--decouverte-seule", action="store_true", help="ne lit que les calendriers et les éditions inconnues")
    a = ap.parse_args()
    if a.test:
        _tests()
        return 0
    lancer(a.sortie, a.avant, a.depuis, a.courses.split(","), a.relire, a.budget_min, a.decouverte_seule, a.max_requetes,
           a.sans_decouverte, a.garder_html, not a.sans_fiches)
    return 0


if __name__ == "__main__":
    sys.exit(main())
