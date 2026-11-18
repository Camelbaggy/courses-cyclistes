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

    python thesports.py --sortie DOSSIER [--avant 2009] [--depuis AAAA] [--courses s43,tour-de-france] [--relire]
                        [--budget-min N] [--decouverte-seule]
                        [--sans-decouverte] [--garder-html]
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

BASE = "https://www.the-sports.org/"
ACCUEIL = BASE + "cycling-s2.html"
USER_AGENT = "courses-cyclistes (accord the-sports.org)"
PAUSE_S = 2.2                      # >= 2 s entre deux requêtes (accord du 18/11/2026)
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

# Code pays du site -> code pays du projet (UCI / CIO, comme netutil.FLAG_CODES). Table explicite : un code absent
# donne None et est compté (`nat_inconnues`) ; elle se complète au fil des lectures réelles, jamais par déduction.
PAYS_SITE_ISO3 = {
    # Table explicite : uniquement des codes VUS sur les pages lues (18/11/2026, éditions 1995-1998 et 2003). Un code absent
    # donne `nat` absent et est compté ; la synthèse de la collecte liste `codes_pays_inconnus` : on les ajoute ici après
    # vérification, jamais par déduction. SCO (Écosse) vu, volontairement NON converti : à décider (GBR à l'UCI ?).
    "AUS": "AUS", "AUT": "AUT", "BEL": "BEL", "CAN": "CAN", "CHI": "CHI", "COL": "COL", "CRC": "CRC", "CRO": "CRO",
    "CZE": "CZE", "DEN": "DEN",
    "EST": "EST", "FIN": "FIN", "FRA": "FRA", "GBR": "GBR", "GER": "GER", "HUN": "HUN", "ITA": "ITA", "JPN": "JPN", "KAZ": "KAZ",
    "LAT": "LAT", "LTU": "LTU", "MDA": "MDA", "MEX": "MEX", "NED": "NED", "NOR": "NOR", "NZL": "NZL", "POL": "POL", "POR": "POR",
    "RUS": "RUS", "SLO": "SLO", "SWE": "SWE", "UKR": "UKR", "USA": "USA", "UZB": "UZB", "VEN": "VEN",
    # codes propres au site, différents des nôtres
    "SPA": "ESP", "SWI": "SUI",
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
        iso = PAYS_SITE_ISO3.get(code)
        if iso:
            ligne["nat"] = iso
    ms = re.search(r"-spf(\d+)\.html", nom_html)
    if ms:
        ligne["id_site"] = int(ms.group(1))
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
    ed["stats"] = stats
    return ed


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
        self.dernier_journal = self.t0

    def epuise(self) -> bool:
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
        if self.epuise():
            return None
        self.requetes += 1
        texte = netutil.fetch_text(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        if texte is None:
            self.echecs += 1
            return None
        if mettre_en_cache:
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            with gzip.open(chemin, "wt", encoding="utf-8") as f:
                f.write(texte)
        return texte

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


def lancer(sortie: str, avant: int = AVANT_DEFAUT, depuis: Optional[int] = None, cibles: Optional[List[str]] = None,
           relire: bool = False, budget_min: float = 0.0, decouverte_seule: bool = False,
           max_pages: int = 0, sans_decouverte: bool = False, garder_html: bool = False) -> Dict[str, Any]:
    """Découverte (calendriers -> courses) puis lecture des éditions de la période. Reprenable."""
    sess = Session(sortie, budget_min, max_pages, garder_html)
    cibles = [c.strip().lower() for c in (cibles or []) if c.strip()]
    chemin_courses = os.path.join(sortie, "courses.json")
    reg = _lire_json(chemin_courses, {"source": "the-sports.org", "courses": {}})
    courses: Dict[str, Dict[str, Any]] = reg.setdefault("courses", {})
    epr_vers_cid = {e["epr"]: cid for cid, c in courses.items() for e in c.get("editions", [])}
    resume = {"calendriers": 0, "courses": 0, "editions_lues": 0, "editions_deja": 0, "echecs": 0, "refus": {},
              "lignes": 0, "temps_ambigus": 0, "temps_illisibles": 0, "temps_non_resolus": 0, "nat_inconnues": 0,
              "codes_pays_inconnus": {}}

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
        print("[THESPORTS] [WARN] liste des années introuvable : découverte impossible")
    for annee in sorted((a for a in annees if a < avant and (depuis is None or a >= depuis)), reverse=True):
        if sess.epuise():
            break
        page = sess.page(annees[annee], mettre_en_cache=True)
        if not page:
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
                break
            # édition inconnue : on la lit (elle est à intégrer de toute façon) pour obtenir l'onglet « Archives »
            page_ed = sess.page(lg["url"], sess.garder_html)
            if not page_ed:
                continue
            editions = lire_archives(page_ed)
            cid = id_course(page_ed, editions)
            if not cid:
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
    resume["echecs"] = sess.echecs
    resume["requetes"] = sess.requetes
    resume["duree_min"] = round((time.monotonic() - sess.t0) / 60, 1)
    resume["budget_epuise"] = sess.epuise()
    sess.journal("synthèse : %s" % json.dumps(resume, ensure_ascii=False, sort_keys=True), force=True)
    return resume


# --------------------------------------------------------------------------------------------------
# Tests sans réseau (pages réelles enregistrées dans tools/fixtures/thesports/)
# --------------------------------------------------------------------------------------------------

def _fixture(nom: str) -> str:
    with open(os.path.join(FIXTURES, nom), encoding="utf-8") as f:
        return f.read()


def _tests() -> None:
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
    ap.add_argument("--max-pages", type=int, default=0, help="plafond de requêtes (0 = illimité)")
    ap.add_argument("--sans-decouverte", action="store_true", help="ne relit pas les calendriers : éditions des courses de courses.json")
    ap.add_argument("--garder-html", action="store_true", help="garde les pages d'édition (gzip, cache/) : relecture sans requête")
    ap.add_argument("--decouverte-seule", action="store_true", help="ne lit que les calendriers et les éditions inconnues")
    a = ap.parse_args()
    if a.test:
        _tests()
        return 0
    lancer(a.sortie, a.avant, a.depuis, a.courses.split(","), a.relire, a.budget_min, a.decouverte_seule, a.max_pages,
           a.sans_decouverte, a.garder_html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
