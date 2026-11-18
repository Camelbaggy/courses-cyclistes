#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Museo del Ciclismo (museociclismo.it) : classements de courses sur route avant 2009 (collecteur, étape 1 : pas d'intégration).

ACCORD : le 18/11/2026, l'association Museo del Ciclismo (curateur de l'archive : Paolo Mannini) a donné au propriétaire
du projet son accord pour lire le site par programme et afficher ses données avec le crédit « Museo del Ciclismo ».
Politesse : robots.txt vérifié le 18/11/2026 (n'interdit que /test, /paolo, /aggiornamento, /configuration, /technica_lib,
/rss, /bin, /dev, /etc, /logs, /tmp, /usr, /var, /includes, /technicalib : aucun chemin lu ici), User-Agent honnête
« courses-cyclistes (accord Museo del Ciclismo) », ≥ 3 s entre deux requêtes, aucune page demandée deux fois (listes en
cache gzip, éditions écrites une fois, étapes lues une fois), abandon propre du passage après 8 échecs réseau de suite
(serveur lent ou injoignable : le passage s'arrête, rien n'est perdu, la reprise est immédiate).

Structure du site (constatée le 18/11/2026, docs/recherche/museo_collecte.md) :
  - listes de courses `/content/corse/corse_in_linea/index.html`, `index2.html`… (106 pages de 50), `corse_a_tappe/`
    (24 pages), `campionati_e_altro/` (32 pages : critériums, derny, cyclo-cross… ignorées par défaut) : tableau
    « # (♂|♀) | Corsa (lien `/content/corse/corsa/<id>-<nom>/index.html`) (début - fin) | Tipo | Nazione ». Les liens de
    pagination `index<N>.html` sont construits à partir du motif des liens de la page 1 et du total « Pagina 1 di N » ;
    c'est le seul motif d'URL calculé (toutes les autres URL sont LUES dans les pages).
  - page de course : onglet « Albo oro, edizioni, vincitori » = TOUTES les éditions (lien `…/edizioni/<n>/<cod>.html`,
    année + date, vainqueur et son lien `/content/ciclisti/ciclista/<id>-<nom>/index.html`, longueur, temps).
  - page d'édition : entête (année, date, n°, départ, arrivée, km, partants, arrivés), onglet « Classifica » = ordre
    d'arrivée (courses en ligne) ou classement général final (courses par étapes) : Pos. | Ciclista (NAZ) + id | Tempo |
    Distacco | Punti ; onglet « Tappe » : une ligne par étape (cod, départ, arrivée, km, vainqueur, temps) ; le classement
    de chaque étape est chargé par le JavaScript de la page (`GetTappaData.php?what=tappa_classifica&cod=<cod>`) : même
    tableau. L'URL de ce point d'accès est LUE dans le script de la page.
  - listes de coureurs `/content/ciclisti/<catégorie>/index.html`, `index2.html`… (professionisti : 726 pages, ~36 300
    coureurs) : Cognome | Nome | date de naissance dd.mm.yyyy | lieu | nationalité, avec l'id ; fiche coureur
    (`Ciclista Professionista`, « Nato a VARESE il 11 maggio 1972 », onglet « Squadre » = équipe par année).

Règle cardinale du projet : aucune valeur inventée. Un champ absent reste absent.
  - Temps : seul le format `7h 0' 27"` est interprété (heures, minutes, secondes). Le temps du 1er est absolu ; la colonne
    « Distacco » (écart au vainqueur) est reprise telle quelle en `ecart_s`. Cellule d'écart VIDE sur une ligne autre que
    le 1er : AMBIGU -> `ecart_s` absent, la ligne porte `ecart_vide: true`, jamais interprétée ici. Constaté sur le Tour de
    France 1996 : des écarts vides en tête de tableau (peloton au temps du vainqueur ?) mais AUSSI en fin de tableau
    (coureurs hors délai ou temps inconnu ?) : « vide = même temps » serait faux ; la synthèse compte les tableaux où des
    vides suivent une valeur (`ecarts_vides_non_prefixe`).
  - Équipe : le classement ne donne PAS l'équipe. L'équipe d'un coureur par année vient de sa fiche (`--equipes`).
  - Dates de naissance : seule une date COMPLÈTE (jour, mois, année) donne `precision: "jour"` ; une année seule donne
    `precision: "annee"` ; mois + année ou autre format : pas de date (compté, exemples dans `formats_date_inconnus`).
  - Nationalité d'un coureur : code à 3 lettres du site gardé tel quel (`nat_site`) ET `nat` = code canonique de `pays_historiques.json`
    (`pays.pays_normalise` : pays existant = code actuel ; pays disparu = code D'ÉPOQUE, ex. RFA -> FRG, DDR -> GDR, CSI -> EUN, URS, YUG,
    jamais converti ; TCH après 1992 ambigu : vide) ; un code inconnu de la table : `nat` absent, compté (`codes_pays_inconnus`). Les
    fichiers écrits avant la table n'ont que `nat` (= code brut) : `pays.pays_ligne` refait la normalisation à la lecture. Le `pays` d'une
    course (liste des courses, page de course) reste le code brut du site (il entre dans les clés d'édition).
  - Niveau (professionnel ou amateur) : le site ne le donne ni par course ni par édition, seulement par COUREUR (liste
    `professionisti`, entête de fiche). `coureurs.json` porte `categories` (listes où le coureur figure) / `categorie` (fiche).

Sélection élargie (`--selection`, 18/11/2026 ; règles dans `construire_selection`, selection.json écrit par `--preparer-selection`) :
  1. id dans `alias_museo.json` `_championnats` (liste manuelle, vide au départ) -> `championnat` ; 2. clé d'épreuve (cle_edition + « G.P. » -> « GP » +
  alias_courses.json + alias_museo.json {id Museo : clé d'épreuve}) dans l'index du projet, classe actuelle WT/Pro/.1/.2 -> `epreuve_suivie`, toutes les
  éditions < 2009 ; 3. hors index, course au calendrier CQ Ranking de l'année (1999-2008, rapprochement EXACT) en France -> `calendrier_uci_france` ;
  4. idem à l'étranger -> `calendrier_uci_top10`, édition retenue si un FRA est dans le top 10 (fichier CQ, 0 requête Museo ; sinon page Museo lue,
  décision mémorisée par édition : `lue` / `ecartee` / `ecartee_cq`, jamais redemandée) ; 5. sinon `sans_classe` (non collecté). Aucune classe CQ n'est
  convertie. Ordre : phase `index` puis `calendrier`, années décroissantes ; étapes non lues sans `--etapes`. `etat.json` : termine, albos_restants,
  editions_a_decider, editions_restantes, coureurs_restants, phase.

Sortie (`--sortie`, défaut ARCHIVES_DIR/sources/museo) : `courses.json` (index des courses, éditions des courses lues),
`editions/<id course>/<année>.json`, `coureurs.json`, `etat.json` (`{"termine", "editions_restantes",
"coureurs_restants"}`, sans horodatage), `cache/` (listes en gzip).

    python museo.py --sortie DOSSIER [--avant 2009] [--depuis AAAA] [--courses id,nom exact,...] [--suivies | --cles FICHIER]
                    [--pays ITA,FRA] [--listes linea,tappe] [--relire] [--budget-min N] [--max-requetes N]
                    [--decouverte-seule] [--sans-etapes] [--sans-fiches] [--equipes] [--listes-coureurs professionisti]
    python museo.py --sortie DOSSIER --archives DOSSIER_ARCHIVES --preparer-selection     # hors réseau : selection.json + chiffres
    python museo.py --sortie DOSSIER --archives DOSSIER_ARCHIVES --selection [--etapes] [--raisons epreuve_suivie,...]
    python museo.py --test            # tests sans réseau (pages réelles allégées de tools/fixtures/museo/)
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
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import netutil
from pays import pays_ligne, pays_normalise

HOTE = "www.museociclismo.it"
BASE = "https://" + HOTE
USER_AGENT = "courses-cyclistes (accord Museo del Ciclismo)"
PAUSE_S = 3.2                      # >= 3 s entre deux requêtes (accord du 18/11/2026)
TIMEOUT_S = 90.0                   # serveur parfois lent : délai de lecture généreux
ECHECS_DE_SUITE_MAX = 8            # abandon propre du passage
ECHECS_MAX = 3                     # une page absente (404) ou sans titre 3 jours différents n'est plus redemandée (sans --relire)
# Règle de comptage (voir thesports.REGLE_ECHECS) : une panne (réseau, 5xx, serveur abandonné) ne note rien ; au plus un échec par page et
# par jour ; un compteur sans marque `<clé>_regle` (ou de règle plus ancienne) est ignoré = page re-tentée, remis à 0 au prochain échec.
REGLE_ECHECS = 2


def _echecs(obj: Dict[str, Any], cle: str) -> int:
    """Échecs comptés (clé `cle` de `obj`) selon la règle en vigueur ; 0 pour un compteur de règle ancienne."""
    return obj.get(cle, 0) if obj.get(cle + "_regle", 0) >= REGLE_ECHECS else 0


def _noter_echec(obj: Dict[str, Any], cle: str) -> bool:
    """Compte un échec (page absente ou sans titre) : un seul par jour. Retourne vrai si le compteur a augmenté."""
    jour = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    n = _echecs(obj, cle)
    if n and obj.get(cle + "_jour") == jour:
        return False
    obj[cle], obj[cle + "_jour"], obj[cle + "_regle"] = n + 1, jour, REGLE_ECHECS
    return True
netutil.HOST_DELAYS[HOTE] = PAUSE_S

AVANT_DEFAUT = 2009
ARCHIVES_DIR = os.environ.get("ARCHIVES_DIR") or os.path.join("data", "archives")
SORTIE_DEFAUT = os.path.join(ARCHIVES_DIR, "sources", "museo")
RACINE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(RACINE, "tools", "fixtures", "museo")

# nom de liste -> chemin de la première page (lu sur le menu du site)
LISTES_COURSES = {
    "linea": "/content/corse/corse_in_linea/index.html",
    "tappe": "/content/corse/corse_a_tappe/index.html",
    "campionati": "/content/corse/campionati_e_altro/index.html",
}
LISTES_DEFAUT = ("linea", "tappe")
LISTES_COUREURS = {
    "professionisti": "/content/ciclisti/professionisti/index.html",
    "dilettanti": "/content/ciclisti/dilettanti/index.html",
    "elite": "/content/ciclisti/elite/index.html",
    "under23": "/content/ciclisti/under23/index.html",
    "indipendenti": "/content/ciclisti/indipendenti/index.html",
}

MOIS_IT = {m: i + 1 for i, m in enumerate(
    ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
     "novembre", "dicembre"])}


# --------------------------------------------------------------------------------------------------
# Lecture du HTML (expressions régulières : pages très régulières, aucune dépendance)
# --------------------------------------------------------------------------------------------------

def _txt(fragment: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ")).strip()


def url_absolue(rel: str) -> str:
    """URL absolue, chemin percent-encodé (noms accentués, espaces) sans toucher aux %XX déjà présents."""
    if rel.startswith("http://www.museociclismo.it"):
        rel = rel[len("http://www.museociclismo.it"):]
    elif rel.startswith("https://" + HOTE):
        rel = rel[len("https://" + HOTE):]
    if rel.startswith("http"):
        return rel
    return BASE + urllib.parse.quote(rel, safe="/:?=&%+'()!,;@$*~.-_")


def chemin_relatif(href: str) -> str:
    """Lien lu dans une page -> chemin relatif au site, sans requête (`?t_corse=…` : suivi de navigation inutile)."""
    h = _html.unescape(href).strip()
    h = re.sub(r"^https?://(www\.)?museociclismo\.it", "", h)
    return h.split("?")[0]


def total_pages(page: str) -> int:
    m = re.search(r"Pagina\s+\d+\s+di\s+(\d+)", page)
    return int(m.group(1)) if m else 1


def lire_liste_courses(page: str) -> List[Dict[str, Any]]:
    """Lignes d'une page de liste de courses : id, slug (lu dans le lien), nom, début, fin, type, pays, sexe."""
    out = []
    for tr in re.findall(r"<tr><th scope=\"row\">(.*?)</tr>", page, flags=re.S):
        m = re.match(r"\s*(\d+)\s*(♂|♀)?\s*</th>\s*<td>\s*<a href=\"([^\"]*?/corsa/(\d+)-([^/\"]*)/index\.html[^\"]*)\">(.*?)</a>"
                     r"\s*(?:\((\d{4})\s*-\s*(\d{4})\))?\s*</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>", tr, flags=re.S)
        if not m:
            continue
        c = {"id": m.group(4), "slug": m.group(5), "nom": _txt(m.group(6)), "type": _txt(m.group(9)),
             "pays": _txt(m.group(10)), "sexe": "F" if m.group(2) == "♀" else "M"}
        if m.group(7):                      # une course sans années (aucune édition en archive) n'a ni début ni fin
            c["debut"], c["fin"] = int(m.group(7)), int(m.group(8))
        out.append(c)
    return out


def lire_albo(page: str) -> Dict[str, Any]:
    """Page de course : nom, pays, type, et TOUTES les éditions de l'onglet « Albo oro » (n°, année, date, URL de
    l'édition lue dans le lien, vainqueur, longueur, temps brut, vitesse)."""
    out: Dict[str, Any] = {"editions": []}
    m = re.search(r"<h2>(.*?)</h2>", page, flags=re.S)
    if m:
        out["nom"] = _txt(m.group(1))
    m = re.search(r"Tipo di corsa:\s*([^<(]+?)\s*\(Cod:\s*(\d+)\)", page)
    if m:
        out["type"] = m.group(1).strip()
    m = re.search(r"/media/flag/([A-Za-z]{3})\.gif", page)
    if m:
        out["pays"] = m.group(1).upper()
    i = page.find('id="albooro"')
    j = page.find('id="statistiche"', i)
    if i < 0:
        return out
    for tr in re.findall(r"<tr>(.*?)</tr>", page[i:j if j > 0 else None], flags=re.S):
        m = re.search(r'<a href="([^"]*?/edizioni/(\d+)/(\d+)\.html[^"]*)">(\d+)</a>', tr)
        if not m:
            continue
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
        if len(tds) < 4:
            continue
        ma = re.match(r"\s*(\d{4})(?:\s*\((\d{2})\.(\d{2})\.(\d{4})\))?", _txt(tds[1]))
        if not ma:
            continue
        ed: Dict[str, Any] = {"n": int(m.group(2)), "cod": m.group(3), "annee": int(ma.group(1)),
                              "url": chemin_relatif(m.group(1))}
        if ma.group(2):
            ed["date"] = "%s-%s-%s" % (ma.group(4), ma.group(3), ma.group(2))
        mv = re.search(r'/ciclisti/ciclista/(\d+)-[^"]*"[^>]*>(.*?)</a>', tds[3], flags=re.S)
        if mv:
            ed["vainqueur"] = {"id": mv.group(1), "nom": _txt(mv.group(2))}
        out["editions"].append(ed)
    return out


def parse_temps(brut: str) -> Optional[int]:
    """`7h 0' 27"` / `95h 57' 16"` / `0h 0' 1"` -> secondes. Tout autre format : None (compté par l'appelant)."""
    m = re.fullmatch(r"\s*(\d+)\s*h\s*(\d+)\s*'\s*(\d+)\s*(?:\"|'')?\s*", (brut or "").replace("\xa0", " "))
    if not m or int(m.group(2)) >= 60 or int(m.group(3)) >= 60:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def lire_lignes(fragment: str, stats: Dict[str, Any], annee: Optional[int] = None) -> List[Dict[str, Any]]:
    """Lignes d'un tableau de classement (Pos., Ciclista (NAZ), Tempo, Distacco, Punti)."""
    lignes: List[Dict[str, Any]] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", fragment, flags=re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
        if len(tds) < 3:
            continue
        rang_brut = _txt(tds[0])
        l: Dict[str, Any] = {}
        m = re.fullmatch(r"(\d+)\s*°?", rang_brut)
        if m:
            l["rang"] = int(m.group(1))
        else:
            l["rang_brut"] = rang_brut
            stats["rangs_non_numeriques"] = stats.get("rangs_non_numeriques", 0) + 1
        mc = re.search(r'<a href="[^"]*?/ciclista/(\d+)-[^"]*"[^>]*>(.*?)</a>\s*(?:\(([A-Za-z]{2,4})\))?', tds[1], flags=re.S)
        if mc:
            l["id"] = mc.group(1)
            l["nom"] = _txt(mc.group(2))
            if mc.group(3):
                l["nat_site"] = mc.group(3).upper()
                iso = pays_normalise(l["nat_site"], "museo", annee)
                if iso:
                    l["nat"] = iso
                else:
                    stats.setdefault("codes_pays_inconnus", {})[l["nat_site"]] = stats.get("codes_pays_inconnus", {}).get(l["nat_site"], 0) + 1
            else:
                stats["nat_absentes"] = stats.get("nat_absentes", 0) + 1
        else:
            l["nom"] = _txt(tds[1])
            stats["sans_id"] = stats.get("sans_id", 0) + 1
        tempo = _txt(tds[2]) if len(tds) > 2 else ""
        ecart = _txt(tds[3]) if len(tds) > 3 else ""
        pts = _txt(tds[4]) if len(tds) > 4 else ""
        if tempo:
            s = parse_temps(tempo)
            if s is None:
                l["temps_brut"] = tempo
                stats["temps_illisibles"] = stats.get("temps_illisibles", 0) + 1
            else:
                l["temps_s"] = s
        if ecart:
            s = parse_temps(ecart)
            if s is None:
                l["ecart_brut"] = ecart
                stats["ecarts_illisibles"] = stats.get("ecarts_illisibles", 0) + 1
            else:
                l["ecart_s"] = s
        elif l.get("rang") != 1 and not tempo:
            l["ecart_vide"] = True
        if pts:
            l["points_brut"] = pts
        lignes.append(l)
    stats["lignes"] = stats.get("lignes", 0) + len(lignes)
    # les écarts vides forment-ils un préfixe du tableau (hypothèse « même temps que le vainqueur ») ?
    vus_valeur = False
    for l in lignes:
        if "ecart_s" in l or "ecart_brut" in l:
            vus_valeur = True
        elif l.get("ecart_vide") and vus_valeur:
            stats["ecarts_vides_non_prefixe"] = stats.get("ecarts_vides_non_prefixe", 0) + 1
            break
    stats["ecarts_vides"] = stats.get("ecarts_vides", 0) + sum(1 for l in lignes if l.get("ecart_vide"))
    return lignes


def _volet(page: str, ident: str) -> str:
    """Contenu de l'onglet `ident` (jusqu'à l'onglet suivant)."""
    i = page.find('id="%s" role="tabpanel"' % ident)
    if i < 0:
        return ""
    j = page.find('class="tab-pane', i + 20)
    return page[i:j if j > 0 else None]


def lire_etapes(page: str, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Onglet « Tappe » : une ligne par étape (cod = identifiant du classement d'étape, numéro, départ, arrivée, km,
    vainqueur, temps brut, vitesse, contre-la-montre si l'icône chronomètre est présente)."""
    out = []
    seg = _volet(page, "tappe")
    for m in re.finditer(r"<tr>\s*<td>\s*<button[^>]*onclick=\"tappa\((\d+),\d+\)\"[^>]*>\s*<a href=\"#row\d+\">([^<]*)</a>\s*</button>"
                         r"(.*?)</td>(.*?)</tr>", seg, flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(4), flags=re.S)
        e: Dict[str, Any] = {"cod": m.group(1), "numero": _txt(m.group(2))}
        if "stopwatch" in m.group(3):
            e["clm"] = True
        if len(cells) >= 6:
            champs = [_txt(c) for c in cells]
            if champs[0]:
                e["date_brut"] = champs[0]
            if champs[1]:
                e["depart"] = champs[1]
            if champs[2]:
                e["arrivee"] = champs[2]
            if champs[3]:
                try:
                    e["km"] = float(champs[3])
                except ValueError:
                    e["km_brut"] = champs[3]
            mv = re.search(r'/ciclista/(\d+)-[^"]*"[^>]*>(.*?)</a>', cells[4], flags=re.S)
            if mv:
                e["vainqueur"] = {"id": mv.group(1), "nom": _txt(mv.group(2))}
            elif champs[4]:
                e["vainqueur"] = {"nom": champs[4]}
            if champs[5]:
                s = parse_temps(champs[5])
                if s is None:
                    e["temps_brut"] = champs[5]
                    stats["temps_illisibles"] = stats.get("temps_illisibles", 0) + 1
                else:
                    e["temps_s"] = s
            if len(champs) > 6 and champs[6]:
                try:
                    e["vitesse_kmh"] = float(champs[6])
                except ValueError:
                    pass
        out.append(e)
    return out


def lire_endpoint_etapes(page: str) -> Optional[str]:
    """URL du point d'accès des classements d'étape, LUE dans le script de la page (`…GetTappaData.php?what=tappa_classifica&cod=`)."""
    m = re.search(r"\.load\(\"(https?://[^\"]*GetTappaData\.php\?what=tappa_classifica&cod=)\"", page)
    return chemin_relatif(m.group(1)) + "?what=tappa_classifica&cod=" if m else None


def lire_edition(page: str, stats: Dict[str, Any], annee: Optional[int] = None) -> Dict[str, Any]:
    """Page d'édition : entête, classement, étapes. Rien d'inventé : un champ absent reste absent."""
    ed: Dict[str, Any] = {}
    m = re.search(r"<h2>(.*?)</h2>", page, flags=re.S)
    if m:
        ed["nom"] = _txt(m.group(1))
    m = re.search(r"Tipo di corsa:\s*([^<(]+?)\s*\(Cod:\s*(\d+)\)", page)
    if m:
        ed["type"] = m.group(1).strip()
        ed["cod"] = m.group(2)
    m = re.search(r"Anno:\s*<b>(\d{4})</b>\s*Data:\s*<b>(\d{2})\.(\d{2})\.(\d{4})</b>", page)
    if m:
        ed["annee"] = int(m.group(1))
        ed["date"] = "%s-%s-%s" % (m.group(4), m.group(3), m.group(2))
    else:
        m = re.search(r"Anno:\s*<b>(\d{4})</b>", page)
        if m:
            ed["annee"] = int(m.group(1))
    m = re.search(r"Edizione n\.\s*<b>(\d+)</b>", page)
    if m:
        ed["n"] = int(m.group(1))
    m = re.search(r"Partenza da\s*<b>(.*?)</b>", page)
    if m:
        ed["depart"] = _txt(m.group(1))
    m = re.search(r"arrivo a\s*<b>(.*?)</b>", page)
    if m:
        ed["arrivee"] = _txt(m.group(1))
    m = re.search(r"lunghezza totale di\s*<span><b>([\d.]+)</b>\s*km", page)
    if m:
        ed["km"] = float(m.group(1))
    m = re.search(r"Partenti\s*<b>(\d+)</b>\s*ciclisti\s*arrivati\s*<b>(\d+)</b>", page)
    if m:
        ed["partants"] = int(m.group(1))
        ed["arrives"] = int(m.group(2))
    m = re.search(r"/media/flag/([A-Za-z]{3})\.gif", page)
    if m:
        ed["pays"] = m.group(1).upper()
    classe = _volet(page, "classifica")
    ed["classement"] = lire_lignes(classe, stats, annee) if classe else []
    ed["etapes"] = lire_etapes(page, stats)
    ep = lire_endpoint_etapes(page)
    if ep and ed["etapes"]:
        ed["etapes_endpoint"] = ep
    return ed


def lire_classement_etape(fragment: str, stats: Dict[str, Any], annee: Optional[int] = None) -> List[Dict[str, Any]]:
    return lire_lignes(fragment, stats, annee)


def lire_liste_coureurs(page: str) -> List[Dict[str, Any]]:
    """Page de liste de coureurs : id, cognome, nome, naissance (date complète ou année seule), lieu, nationalité."""
    out = []
    for tr in re.findall(r"<tr><th scope=\"row\">(.*?)</tr>", page, flags=re.S):
        m = re.match(r"\s*\d+\s*(♂|♀)?\s*</th>\s*<td>\s*<a href=\"[^\"]*?/ciclista/(\d+)-[^\"]*\">(.*?)</a>\s*</td>"
                     r"\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>", tr, flags=re.S)
        if not m:
            continue
        c: Dict[str, Any] = {"id": m.group(2), "cognome": _txt(m.group(3)), "sexe": "F" if m.group(1) == "♀" else "M"}
        if _txt(m.group(4)):
            c["nome"] = _txt(m.group(4))
        naiss, prec, brut = parse_naissance_liste(_txt(m.group(5)))
        if naiss:
            c["naissance"], c["precision"] = naiss, prec
        elif brut:
            c["naissance_brut"] = brut
        if _txt(m.group(6)):
            c["lieu"] = _txt(m.group(6))
        if _txt(m.group(7)):
            c["nat_site"] = _txt(m.group(7)).upper()
            iso = pays_normalise(c["nat_site"], "museo")
            if iso:
                c["nat"] = iso
        out.append(c)
    return out


def parse_naissance_liste(texte: str) -> Tuple[Optional[str], str, str]:
    """`28.10.1990` -> (AAAA-MM-JJ, jour) ; `1936` -> (AAAA, annee) ; vide -> (None, "", "") ; autre -> (None, "", brut).
    Une date impossible (31.02, 00.00.1900) n'est pas une date."""
    t = (texte or "").strip()
    if not t:
        return None, "", ""
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", t)
    if m:
        try:
            datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)), "jour", t
        except ValueError:
            return None, "", t
    if re.fullmatch(r"\d{4}", t):
        return t, "annee", t
    return None, "", t


def parse_naissance_fiche(texte: str) -> Tuple[Optional[str], str, str]:
    """Fragment `<b>11 maggio 1972</b>` (texte) -> (date, precision, brut). Jour + mois en toutes lettres italiennes + année :
    précision « jour » ; une année seule : « annee » ; mois + année ou autre : pas de date."""
    t = (texte or "").strip().lower()
    m = re.fullmatch(r"(\d{1,2})\s+([a-zì]+)\s+(\d{4})", t)
    if m and m.group(2) in MOIS_IT:
        try:
            d = datetime.date(int(m.group(3)), MOIS_IT[m.group(2)], int(m.group(1)))
            return d.isoformat(), "jour", t
        except ValueError:
            return None, "", t
    if re.fullmatch(r"\d{4}", t):
        return t, "annee", t
    return None, "", t


def lire_fiche(page: str) -> Dict[str, Any]:
    """Fiche coureur : nom, catégorie (entête), naissance, lieu, nationalité, équipes par année."""
    f: Dict[str, Any] = {}
    m = re.search(r'<span itemprop="name">(.*?)</span>', page, flags=re.S)
    if m:
        f["nom"] = _txt(m.group(1))
    m = re.search(r"<div>\s*Ciclista\s*([^<(]*?)\s*\(Cod:\s*(\d+)\)\s*</div>", page)
    if m:
        f["id"] = m.group(2)
        if m.group(1).strip():
            f["categorie"] = m.group(1).strip()
    m = re.search(r"<p>\s*Nat[oa]\s*(?:a\s*<b>(.*?)</b>\s*)?(?:il\s*<b>(.*?)</b>)?\s*</p>", page, flags=re.S)
    if m:
        if m.group(1) and _txt(m.group(1)):
            f["lieu"] = _txt(m.group(1))
        if m.group(2):
            naiss, prec, brut = parse_naissance_fiche(_txt(m.group(2)))
            if naiss:
                f["naissance"], f["precision"] = naiss, prec
            else:
                f["naissance_brut"] = brut
    m = re.search(r"/media/flag/([A-Za-z]{3})\.gif[^>]*/>\s*</div>\s*<div class=\"text-center\">([A-Za-z]{3})</div>", page)
    if m:
        f["nat_site"] = m.group(2).upper()
        iso = pays_normalise(f["nat_site"], "museo")
        if iso:
            f["nat"] = iso
    equipes = []
    seg = _volet(page, "squadre")
    for tr in re.findall(r"<tr>(.*?)</tr>", seg, flags=re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
        if len(tds) < 3 or not re.fullmatch(r"\d{4}", _txt(tds[0])):
            continue
        e: Dict[str, Any] = {"annee": int(_txt(tds[0]))}
        ma = re.search(r"/squadra/(\d+)-[^'\"]*['\"][^>]*>(.*?)</a>", tds[1], flags=re.S)
        if ma:
            e["id"], e["nom"] = ma.group(1), _txt(ma.group(2))
        else:
            e["nom"] = _txt(tds[1])
        if _txt(tds[2]):
            e["pays"] = _txt(tds[2]).upper()
        equipes.append(e)
    if equipes:
        f["equipes"] = equipes
    return f


# --------------------------------------------------------------------------------------------------
# Réseau, stockage, reprise
# --------------------------------------------------------------------------------------------------

class Session:
    """Requêtes polies (pause par hôte, budget, compteur, abandon après des échecs de suite) ; listes en cache gzip."""

    def __init__(self, sortie: str, budget_min: float = 0.0, max_requetes: int = 0):
        self.sortie = sortie
        self.t0 = time.monotonic()
        self.budget_s = budget_min * 60 if budget_min else 0.0
        self.max_requetes = max_requetes
        self.requetes = 0
        self.echecs = 0
        self.absente = False        # dernière page demandée : 404 / 410 (vrai échec) ; faux = lue, ou panne passagère
        self.echecs_de_suite = 0
        self.abandon = False
        self.dernier_journal = self.t0

    def epuise(self) -> bool:
        if self.abandon:
            return True
        if self.budget_s and time.monotonic() - self.t0 >= self.budget_s:
            return True
        return bool(self.max_requetes) and self.requetes >= self.max_requetes

    def _cache(self, url: str) -> str:
        return os.path.join(self.sortie, "cache", hashlib.sha1(url.encode()).hexdigest()[:16] + ".html.gz")

    def page(self, rel: str, mettre_en_cache: bool = False) -> Optional[str]:
        url = url_absolue(rel)
        chemin = self._cache(url)
        if mettre_en_cache and os.path.exists(chemin):
            with gzip.open(chemin, "rt", encoding="utf-8") as f:
                return f.read()
        self.absente = False
        if self.epuise():
            return None
        self.requetes += 1
        texte = netutil.fetch_text(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, retries=3,
                                   timeout=TIMEOUT_S)
        if texte is None:
            self.echecs += 1
            self.absente = netutil.page_absente()
            self.echecs_de_suite += 1
            if self.echecs_de_suite >= ECHECS_DE_SUITE_MAX and not self.abandon:
                self.abandon = True
                print("[MUSEO] [WARN] %d échecs de suite : serveur injoignable, passage arrêté (reprise au prochain passage)"
                      % self.echecs_de_suite)
            return None
        self.echecs_de_suite = 0
        if mettre_en_cache:
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            with gzip.open(chemin, "wt", encoding="utf-8") as f:
                f.write(texte)
        return texte

    def journal(self, message: str, force: bool = False) -> None:
        if force or time.monotonic() - self.dernier_journal >= 300:
            self.dernier_journal = time.monotonic()
            print("[MUSEO] %s (%d requêtes, %.1f min)" % (message, self.requetes, (time.monotonic() - self.t0) / 60))


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


def chemin_edition(sortie: str, cid: str, annee: int, cod: str) -> str:
    """editions/<id course>/<année>.json ; deux éditions la même année : suffixe -<cod> sur la seconde."""
    base = os.path.join(sortie, "editions", cid, "%d.json" % annee)
    ex = _lire_json(base, None) if os.path.exists(base) else None
    if isinstance(ex, dict) and ex.get("cod") not in (None, cod):
        return os.path.join(sortie, "editions", cid, "%d-%s.json" % (annee, cod))
    return base


def _cle_nom(nom: str) -> str:
    return netutil.normalize(nom)


def cles_suivies(chemin: Optional[str] = None) -> set:
    """Clés d'édition (`collector.cle_edition`, « nom normalisé|PAYS ») des courses à retenir : par défaut les séries de
    series_historiques.json ; `chemin` = fichier JSON (dictionnaire dont les clés sont des clés d'édition, ou liste de clés)."""
    d = _lire_json(chemin or os.path.join(RACINE, "series_historiques.json"), {})
    if isinstance(d, dict):
        return set(d)
    return {x for x in d if isinstance(x, str)} if isinstance(d, list) else set()


def course_retenue(c: Dict[str, Any], cibles: List[str], pays: List[str], avant: int, depuis: Optional[int],
                   suivies: Optional[set], cle_fn: Any = None) -> bool:
    """Filtre d'une course de la liste : hommes, au moins une édition dans [depuis, avant[, pays, cibles (id numérique ou
    nom exact normalisé), séries suivies (clé d'édition exacte)."""
    if c.get("sexe") == "F" or "debut" not in c:
        return False
    if c["debut"] >= avant or (depuis is not None and c["fin"] < depuis):
        return False
    if pays and c.get("pays", "") not in pays:
        return False
    if cibles and not any(t == c["id"] or t == _cle_nom(c["nom"]) for t in cibles):
        return False
    if suivies is not None:
        cle = cle_fn(c["nom"], c.get("pays")) if cle_fn else None
        if not cle or cle not in suivies:
            return False
    return True


def decouvrir_courses(sess: Session, listes: Tuple[str, ...], reg: Dict[str, Any], resume: Dict[str, Any]) -> bool:
    """Pages de liste (cache gzip) -> `reg["courses"]`. Retourne False si une page manque (budget, réseau)."""
    complet = True
    courses = reg.setdefault("courses", {})
    suivi = reg.setdefault("listes", {})
    for nom in listes:
        p1 = sess.page(LISTES_COURSES[nom], mettre_en_cache=True)
        if not p1:
            complet = False
            continue
        n = total_pages(p1)
        suivi[nom] = {"pages": n}
        base = LISTES_COURSES[nom].rsplit("/", 1)[0]
        for i in range(1, n + 1):
            page = p1 if i == 1 else sess.page("%s/index%d.html" % (base, i), mettre_en_cache=True)
            if not page:
                complet = False
                if sess.epuise():
                    break
                continue
            resume["pages_listes"] += 1
            lignes = lire_liste_courses(page)
            attendu = len(re.findall(r'<tr><th scope="row">', page))
            if len(lignes) != attendu:
                resume["lignes_liste_illisibles"] += attendu - len(lignes)
            for l in lignes:
                c = courses.setdefault(l["id"], {})
                c.update({k: l[k] for k in ("slug", "nom", "debut", "fin", "type", "pays", "sexe") if k in l})
                c["liste"] = nom
            sess.journal("découverte %s : page %d/%d" % (nom, i, n))
    return complet


def lire_albo_course(sess: Session, cid: str, c: Dict[str, Any], resume: Dict[str, Any]) -> bool:
    """Onglet « Albo oro » de la course : éditions (une seule requête, mémorisée dans courses.json)."""
    if c.get("editions") is not None:
        return True
    page = sess.page("/content/corse/corsa/%s-%s/index.html" % (cid, c["slug"]))
    if not page:
        if sess.absente:
            _noter_echec(c, "albo_echecs")
        return False
    a = lire_albo(page)
    c["editions"] = [{k: v for k, v in e.items()} for e in a["editions"]]
    resume["albos_lus"] += 1
    if not a["editions"]:
        resume["albos_sans_edition"] += 1
    return True


def ecrire_edition(sess: Session, cid: str, e: Dict[str, Any], page: str, resume: Dict[str, Any]) -> Dict[str, Any]:
    stats: Dict[str, Any] = {}
    contenu = lire_edition(page, stats, e["annee"])
    contenu.update({"source": "museociclismo.it", "source_url": url_absolue(e["url"]), "course_id": cid,
                    "lu_le": _maintenant()})
    if e.get("vainqueur"):
        contenu["vainqueur_albo"] = e["vainqueur"]
    contenu.setdefault("annee", e["annee"])
    contenu["stats"] = stats
    _ecrire_json(chemin_edition(sess.sortie, cid, e["annee"], e["cod"]), contenu, compact=True)
    resume["editions_lues"] += 1
    resume["profondeurs"].append(len(contenu["classement"]))
    for k in ("lignes", "temps_illisibles", "ecarts_illisibles", "ecarts_vides", "ecarts_vides_non_prefixe", "sans_id",
              "nat_absentes", "rangs_non_numeriques"):
        resume[k] = resume.get(k, 0) + stats.get(k, 0)
    for code, n in stats.get("codes_pays_inconnus", {}).items():
        resume["codes_pays_inconnus"][code] = resume["codes_pays_inconnus"].get(code, 0) + n
    return contenu


def lire_etapes_edition(sess: Session, chemin: str, resume: Dict[str, Any], urls: Optional[Dict[str, str]] = None) -> int:
    """Lit le classement de chaque étape non encore lue d'une édition écrite (un appel par étape, une fois).
    `urls` : liens de fiche coureur lus dans les classements d'étape (complété). Retourne le nombre d'étapes à lire."""
    ed = _lire_json(chemin, None)
    if not isinstance(ed, dict) or not ed.get("etapes") or not ed.get("etapes_endpoint"):
        return 0
    restant = 0
    modif = False
    for e in ed["etapes"]:
        if "classement" in e or _echecs(e, "echecs") >= ECHECS_MAX:
            continue
        if sess.epuise():
            restant += 1
            continue
        page = sess.page(ed["etapes_endpoint"] + e["cod"])
        if page is None:
            if sess.absente:
                modif = _noter_echec(e, "echecs") or modif
            restant += 1
            continue
        stats: Dict[str, Any] = {}
        e["classement"] = lire_classement_etape(page, stats, ed.get("annee"))
        if urls is not None:
            memoriser_urls(sess.sortie, page, urls)
        modif = True
        resume["etapes_lues"] += 1
        for k in ("lignes", "temps_illisibles", "ecarts_illisibles", "ecarts_vides", "ecarts_vides_non_prefixe", "sans_id"):
            resume[k] = resume.get(k, 0) + stats.get(k, 0)
        for code, n in stats.get("codes_pays_inconnus", {}).items():
            resume["codes_pays_inconnus"][code] = resume["codes_pays_inconnus"].get(code, 0) + n
    if modif:
        _ecrire_json(chemin, ed, compact=True)
    return restant


def coureurs_attendus(sortie: str) -> List[str]:
    """Identifiants des coureurs qui figurent dans les éditions écrites (classements et étapes)."""
    ids = set()
    racine = os.path.join(sortie, "editions")
    for dossier, _, fichiers in os.walk(racine):
        for nom in fichiers:
            if not nom.endswith(".json"):
                continue
            ed = _lire_json(os.path.join(dossier, nom), None)
            if not isinstance(ed, dict):
                continue
            for l in ed.get("classement", []):
                if l.get("id"):
                    ids.add(l["id"])
            for e in ed.get("etapes", []):
                for l in e.get("classement", []):
                    if l.get("id"):
                        ids.add(l["id"])
    return sorted(ids, key=int)


def lire_listes_coureurs(sess: Session, sortie: str, noms: Tuple[str, ...], resume: Dict[str, Any]) -> None:
    """Parcourt les listes de coureurs (une requête par page de 50) -> `coureurs.json` (date de naissance de chacun)."""
    chemin = os.path.join(sortie, "coureurs.json")
    cache: Dict[str, Any] = _lire_json(chemin, {})
    etat_l = _lire_json(os.path.join(sortie, "listes_coureurs.json"), {})
    depuis_ecriture = 0
    try:
        for nom in noms:
            base = LISTES_COUREURS[nom]
            e = etat_l.setdefault(nom, {"pages": 0, "lues": 0})
            if e["pages"] and e["lues"] >= e["pages"]:
                continue
            p1 = sess.page(base, mettre_en_cache=True)
            if not p1:
                continue
            e["pages"] = total_pages(p1)
            for i in range(e["lues"] + 1, e["pages"] + 1):
                if sess.epuise():
                    break
                page = p1 if i == 1 else sess.page("%s/index%d.html" % (base.rsplit("/", 1)[0], i))
                if not page:
                    break
                for c in lire_liste_coureurs(page):
                    cid = c.pop("id")
                    entree = cache.setdefault(cid, {})
                    for k, v in c.items():
                        entree[k] = v
                    cats = entree.setdefault("categories", [])
                    if nom not in cats:
                        cats.append(nom)
                    if c.get("naissance"):
                        resume["listes_naissances"][c["precision"]] = resume["listes_naissances"].get(c["precision"], 0) + 1
                    else:
                        resume["listes_naissances"]["absente"] = resume["listes_naissances"].get("absente", 0) + 1
                e["lues"] = i
                resume["pages_coureurs"] += 1
                depuis_ecriture += 1
                if depuis_ecriture >= 20:
                    _ecrire_json(chemin, cache, compact=True)
                    _ecrire_json(os.path.join(sortie, "listes_coureurs.json"), etat_l)
                    depuis_ecriture = 0
                sess.journal("listes de coureurs %s : page %d/%d" % (nom, i, e["pages"]))
    finally:
        if depuis_ecriture or (cache and not os.path.exists(chemin)):
            _ecrire_json(chemin, cache, compact=True)
        if etat_l:
            _ecrire_json(os.path.join(sortie, "listes_coureurs.json"), etat_l)


def _fiche_a_lire(entree: Optional[Dict[str, Any]], equipes: bool) -> bool:
    if entree is None:
        return True
    if _echecs(entree, "fiche_echecs") >= ECHECS_MAX:
        return False
    if entree.get("fiche_lue"):
        return False
    # coureur connu par une liste : fiche seulement si les équipes sont demandées
    return equipes


def lire_fiches(sess: Session, sortie: str, equipes: bool, relire: bool, resume: Dict[str, Any]) -> int:
    """Fiche de chaque coureur des éditions écrites absent de `coureurs.json` (ou, avec --equipes, sans fiche lue) :
    une requête par coureur. URL construite depuis l'id lu dans les classements : `/content/ciclisti/ciclista/<id>-<nom>/`
    est REÇUE depuis le classement (`url` de la ligne) ; à défaut d'URL lue, le coureur n'est pas lu."""
    chemin = os.path.join(sortie, "coureurs.json")
    cache: Dict[str, Any] = _lire_json(chemin, {})
    urls = urls_fiches(sortie)
    a_lire = [i for i in coureurs_attendus(sortie) if i in urls and (relire or _fiche_a_lire(cache.get(i), equipes))]
    lues, depuis_ecriture = 0, 0
    try:
        for i in a_lire:
            if sess.epuise():
                break
            page = sess.page(urls[i])
            entree = cache.setdefault(i, {})
            depuis_ecriture += 1
            if not page:
                if sess.absente:                     # 404 / 410 : vrai échec ; sinon panne passagère, rien n'est noté
                    _noter_echec(entree, "fiche_echecs")
                continue
            f = lire_fiche(page)
            lues += 1
            if not f.get("nom"):
                _noter_echec(entree, "fiche_echecs")
                continue
            f.pop("id", None)
            if f.get("naissance"):
                resume["fiches_naissances"][f["precision"]] = resume["fiches_naissances"].get(f["precision"], 0) + 1
            else:
                resume["fiches_naissances"]["absente"] = resume["fiches_naissances"].get("absente", 0) + 1
                if f.get("naissance_brut") and len(resume["formats_date_inconnus"]) < 20:
                    resume["formats_date_inconnus"].append(f["naissance_brut"])
            if entree.get("naissance") and f.get("naissance") and entree["naissance"] != f["naissance"] \
                    and entree.get("precision") == f.get("precision"):
                resume["naissances_discordantes"] += 1
                entree["naissance_fiche"] = f.pop("naissance")
                f.pop("precision", None)
            for k, v in f.items():
                if k in ("naissance", "precision", "lieu", "nat", "nat_site"):
                    entree.setdefault(k, v)          # la liste fait foi quand elle a déjà une valeur
                else:
                    entree[k] = v
            entree["fiche_lue"] = True
            entree["url"] = url_absolue(urls[i])
            entree["lu_le"] = _maintenant()
            if depuis_ecriture >= 100:
                _ecrire_json(chemin, cache, compact=True)
                depuis_ecriture = 0
            sess.journal("fiches coureurs : %d lues, %d restantes" % (lues, len(a_lire) - lues))
    finally:
        if depuis_ecriture or (cache and not os.path.exists(chemin)):
            _ecrire_json(chemin, cache, compact=True)
    restantes = len([i for i in coureurs_attendus(sortie) if i in urls and _fiche_a_lire(cache.get(i), equipes)])
    resume["fiches_lues"] = lues
    sess.journal("fiches coureurs : %d lues, %d restantes" % (lues, restantes), force=True)
    return restantes


def urls_fiches(sortie: str) -> Dict[str, str]:
    """{id coureur : chemin de sa fiche}, lu dans `urls_coureurs.json` (alimenté à l'écriture des éditions)."""
    return _lire_json(os.path.join(sortie, "urls_coureurs.json"), {})


def memoriser_urls(sortie: str, page: str, deja: Dict[str, str]) -> bool:
    """Retient les liens de fiche coureur lus dans une page (jamais devinés)."""
    nouveau = False
    for href in re.findall(r'href="([^"]*?/ciclisti/ciclista/(\d+)-[^"]*)"', page):
        rel, i = chemin_relatif(href[0]), href[1]
        if i not in deja:
            deja[i] = rel
            nouveau = True
    return nouveau


def lancer(sortie: str, avant: int = AVANT_DEFAUT, depuis: Optional[int] = None, cibles: Optional[List[str]] = None,
           pays: Optional[List[str]] = None, suivies: bool = False, listes: Tuple[str, ...] = LISTES_DEFAUT,
           relire: bool = False, budget_min: float = 0.0, max_requetes: int = 0, decouverte_seule: bool = False,
           etapes: bool = True, fiches: bool = True, equipes: bool = False,
           listes_coureurs: Tuple[str, ...] = (), cles: Optional[str] = None) -> Dict[str, Any]:
    """Découverte (listes -> courses) -> albo des courses retenues -> éditions (+ étapes) -> listes de coureurs -> fiches.
    Reprenable ; écrit `etat.json` (termine, editions_restantes, coureurs_restants) en fin de passage."""
    sess = Session(sortie, budget_min, max_requetes)
    cibles = [_cle_nom(c) if not c.strip().isdigit() else c.strip() for c in (cibles or []) if c.strip()]
    pays = [p.strip().upper() for p in (pays or []) if p.strip()]
    reg = _lire_json(os.path.join(sortie, "courses.json"), {"source": "museociclismo.it"})
    courses = reg.setdefault("courses", {})
    resume: Dict[str, Any] = {"pages_listes": 0, "lignes_liste_illisibles": 0, "albos_lus": 0, "albos_sans_edition": 0,
                              "editions_lues": 0, "etapes_lues": 0, "echecs": 0, "profondeurs": [], "codes_pays_inconnus": {},
                              "pages_coureurs": 0, "listes_naissances": {}, "fiches_naissances": {},
                              "formats_date_inconnus": [], "naissances_discordantes": 0}
    cle_fn = None
    ens_suivies = None
    if suivies or cles:
        import collector
        cle_fn = collector.cle_edition
        ens_suivies = cles_suivies(cles)
    pages_ok = decouvrir_courses(sess, listes, reg, resume)
    _ecrire_json(os.path.join(sortie, "courses.json"), reg, compact=True)
    retenues = sorted((cid for cid, c in courses.items()
                       if c.get("liste") in listes and course_retenue(dict(c, id=cid), cibles, pays, avant, depuis,
                                                                      ens_suivies, cle_fn)),
                      key=lambda x: (courses[x]["nom"].lower(), int(x)))
    resume["courses_retenues"] = len(retenues)
    editions_restantes = 0
    urls = urls_fiches(sortie)
    if not decouverte_seule:
        for cid in retenues:
            c = courses[cid]
            if sess.epuise():
                editions_restantes += 1
                continue
            if not lire_albo_course(sess, cid, c, resume):
                resume["echecs"] += 1
                editions_restantes += 1
                continue
            for e in sorted(c["editions"], key=lambda x: -x["annee"]):
                if e["annee"] >= avant or (depuis is not None and e["annee"] < depuis):
                    continue
                chemin = chemin_edition(sortie, cid, e["annee"], e["cod"])
                if os.path.exists(chemin) and not relire:
                    if etapes:
                        editions_restantes += lire_etapes_edition(sess, chemin, resume, urls)
                    continue
                if _echecs(e, "echecs") >= ECHECS_MAX and not relire:
                    continue
                if sess.epuise():
                    editions_restantes += 1
                    continue
                page = sess.page(e["url"])
                if not page:
                    if sess.absente:
                        _noter_echec(e, "echecs")
                    resume["echecs"] += 1
                    editions_restantes += 1
                    continue
                ed = ecrire_edition(sess, cid, e, page, resume)
                memoriser_urls(sortie, page, urls)
                if etapes and ed.get("etapes"):
                    editions_restantes += lire_etapes_edition(sess, chemin_edition(sortie, cid, e["annee"], e["cod"]),
                                                              resume, urls)
                sess.journal("éditions : %d lues (%s)" % (resume["editions_lues"], c["nom"]))
            _ecrire_json(os.path.join(sortie, "courses.json"), reg, compact=True)
            _ecrire_json(os.path.join(sortie, "urls_coureurs.json"), urls, compact=True)
    _ecrire_json(os.path.join(sortie, "courses.json"), reg, compact=True)
    coureurs_restants = 0
    if not decouverte_seule:
        if listes_coureurs:
            lire_listes_coureurs(sess, sortie, listes_coureurs, resume)
        if fiches:
            coureurs_restants = lire_fiches(sess, sortie, equipes, relire, resume)
    termine = pages_ok and editions_restantes == 0 and coureurs_restants == 0 and not sess.abandon \
        and not decouverte_seule
    _ecrire_json(os.path.join(sortie, "etat.json"),
                 {"termine": bool(termine), "editions_restantes": editions_restantes,
                  "coureurs_restants": coureurs_restants})
    prof = sorted(resume.pop("profondeurs"))
    if prof:
        resume["profondeur_mediane"] = prof[len(prof) // 2]
        resume["profondeur_min"], resume["profondeur_max"] = prof[0], prof[-1]
    resume["requetes"] = sess.requetes
    resume["echecs_reseau"] = sess.echecs
    resume["abandon"] = sess.abandon
    print("[MUSEO] synthèse : " + json.dumps(resume, ensure_ascii=False, sort_keys=True))
    return resume


# --------------------------------------------------------------------------------------------------
# Sélection élargie (18/11/2026, décision du propriétaire : élargir en suivant les règles du projet)
# --------------------------------------------------------------------------------------------------

REGLE_SELECTION = 1                # à incrémenter quand les règles changent : les décisions `ecartee*` mémorisées sont alors refaites
ALIAS_MUSEO = os.path.join(RACINE, "alias_museo.json")
CQ_ANNEES = (1999, 2008)           # calendrier CQ Ranking disponible : bornes incluses (avant 1999 : règles 1 et 2 seulement)
CLASSES_INDEX = ("WT", "Pro", ".1", ".2")      # `cat` de entites/courses/index.json : classe ACTUELLE de l'épreuve (None = championnat)
# classes CQ jamais prises pour des courses sur route ordinaires : championnats (NC*, WC*, CC*, XX*), classement final de Coupe du monde, NE
CLASSES_CQ_EXCLUES = ("NC", "WC", "CC", "XX", "CDMF", "NE")
RAISONS = ("championnat", "epreuve_suivie", "calendrier_uci_france", "calendrier_uci_top10")
PHASE_DE = {"championnat": "index", "epreuve_suivie": "index", "calendrier_uci_france": "calendrier",
            "calendrier_uci_top10": "calendrier"}
TAUX_EDITIONS = 0.88               # éditions réelles / borne (fin - début + 1), mesuré sur les 15 courses déjà lues (étude du 18/11/2026)


def gp(cle: Optional[str]) -> Optional[str]:
    """Clé d'édition `collector.cle_edition` avec « G.P. » -> « GP » (« g p » -> « gp » sur le nom normalisé) : seule retouche
    admise (rapprochement CQ 336 -> 409 courses, aucun faux positif connu) ; `cle_edition` elle-même n'est pas modifiée
    (alignement avec `cleEdition` d'index.html). Les articles et « grand prix » ne sont PAS supprimés (collisions de clés)."""
    if not cle or "|" not in cle:
        return cle
    nom, pays = cle.rsplit("|", 1)
    return " ".join(re.sub(r"\bg p\b", "gp", nom).split()) + "|" + pays


def cle_museo(nom: Optional[str], pays: Optional[str]) -> Optional[str]:
    import collector
    return gp(collector.cle_edition(nom, pays))


def charger_alias_museo(chemin: Optional[str] = None) -> Tuple[Dict[str, str], List[str]]:
    """`alias_museo.json` (manuel, jamais deviné) : {id course Museo : clé d'épreuve du projet} + clé `_championnats` (liste d'ids Museo
    des championnats retenus, à valider un par un). Retourne (alias, championnats)."""
    brut = _lire_json(chemin or ALIAS_MUSEO, {})
    brut = brut if isinstance(brut, dict) else {}
    ch = brut.get("_championnats")
    championnats = [str(x) for x in ch] if isinstance(ch, list) else []
    alias = {str(k): gp(v) for k, v in brut.items() if not k.startswith("_") and isinstance(v, str) and v}
    return alias, championnats


def charger_index_epreuves(archives_dir: str) -> Dict[str, Dict[str, Any]]:
    """`entites/courses/index.json` -> {clé (G.P. normalisé) : entrée}. `cat` = classe ACTUELLE (WT / Pro / .1 / .2 ; None = championnat)."""
    liste = _lire_json(os.path.join(archives_dir, "entites", "courses", "index.json"), [])
    return {gp(e["k"]): e for e in liste if isinstance(e, dict) and e.get("k")}


def charger_calendriers_cq(archives_dir: str, alias_courses: Dict[str, str]) -> Dict[int, Dict[str, List[Dict[str, Any]]]]:
    """Calendriers CQ Ranking 1999-2008 : {année : {clé canonique : [entrées]}}. Championnats (NC*, WC*, CC*, XX*), classement final de
    Coupe du monde et NE exclus ; clé = `cle_museo` puis alias_courses ; `categorie` gardée telle quelle (aucune conversion de classe)."""
    out: Dict[int, Dict[str, List[Dict[str, Any]]]] = {}
    dossier = os.path.join(archives_dir, "sources", "cqranking", "calendrier")
    if not os.path.isdir(dossier):
        return out
    for nom in sorted(os.listdir(dossier)):
        d = _lire_json(os.path.join(dossier, nom), None)
        if not isinstance(d, dict) or not isinstance(d.get("annee"), int):
            continue
        an = d["annee"]
        for mois in sorted(d.get("mois", {}), key=lambda m: int(m)):
            for x in d["mois"][mois].get("courses", []):
                if (x.get("categorie") or "").upper().startswith(CLASSES_CQ_EXCLUES):
                    continue
                k = cle_museo(x.get("nom"), x.get("pays"))
                if k:
                    out.setdefault(an, {}).setdefault(alias_courses.get(k, k), []).append(x)
    return out


def francais_top10_museo(classement: List[Dict[str, Any]], annee: Optional[int] = None) -> bool:
    """Un coureur de nationalité FRA (code normalisé par pays.py) classé rang entier <= 10 (général final pour une course par étapes)."""
    return any(isinstance(l.get("rang"), int) and l["rang"] <= 10 and pays_ligne("museo", l, annee) == "FRA" for l in classement)


def francais_top10_cq(lignes: List[Any], annee: Optional[int] = None) -> bool:
    """Idem sur les `lignes` d'un fichier CQ : [rang, id coureur, nat, équipe, brut, écart_s, points]."""
    return any(isinstance(l[0], int) and l[0] <= 10 and pays_ligne("cqranking", l, annee) == "FRA" for l in lignes if l)


def top10_cq_fichier(archives_dir: str, annee: int, entree: Dict[str, Any]) -> Optional[bool]:
    """Décision « Français dans le top 10 » d'une entrée du calendrier CQ d'après son fichier `courses/<année>/<id>.json` (pour une course par
    étapes, l'id du calendrier est celui du classement général). None : fichier absent ou sans lignes (pas encore collecté)."""
    d = _lire_json(os.path.join(archives_dir, "sources", "cqranking", "courses", str(annee), "%s.json" % entree.get("id")), None)
    if not isinstance(d, dict) or not d.get("lignes"):
        return None
    return francais_top10_cq(d["lignes"], annee)


def _borne(c: Dict[str, Any], avant: int, depuis: Optional[int] = None) -> Tuple[int, int]:
    return max(c["debut"], depuis or 0), min(c["fin"], avant - 1)


def construire_selection(courses: Dict[str, Dict[str, Any]], index: Dict[str, Dict[str, Any]],
                         calendriers: Dict[int, Dict[str, List[Dict[str, Any]]]], top10_cq: Any,
                         alias_courses: Dict[str, str], alias_museo: Dict[str, str], championnats: List[str],
                         avant: int = AVANT_DEFAUT) -> Dict[str, Any]:
    """Règle de sélection (pure, sans réseau ni fichier ; déterministe). Pour chaque course d'homme avec au moins une édition avant `avant` :
      1. id dans `championnats` (liste manuelle)                      -> `championnat`, toutes les éditions < avant ;
      2. clé (cle_museo, alias_courses, alias_museo) dans notre index avec une classe actuelle WT/Pro/.1/.2
                                                                          -> `epreuve_suivie`, toutes les éditions < avant ;
      3. sinon, 1999-2008 seulement : clé présente au calendrier CQ de l'année Y (Y dans [début, fin] de la course) :
           pays FRA                      -> `calendrier_uci_france` : édition de l'année Y retenue ;
           pays étranger                 -> `calendrier_uci_top10`  : édition Y retenue si un FRA est dans le top 10 (décision `retenue` /
                                            `ecartee_cq` d'après le fichier CQ, 0 requête Museo ; `a_decider` : fichier CQ absent, la page
                                            Museo sera lue puis la décision mémorisée) ;
      4. sinon `sans_classe` (niveau inconnu, PAS « amateur ») : non collectée.
    Aucune classe n'est convertie ni devinée : `classe_actuelle` (index) ou `classe_cq` brute, seulement à titre d'information."""
    sel_courses: Dict[str, Dict[str, Any]] = {}
    sans_classe: List[str] = []
    exclues = {"femmes": 0, "sans_edition": 0, "apres": 0}
    cles: Dict[str, List[str]] = {}
    championnats_set = set(championnats)
    utilises_alias = set()
    for cid in sorted(courses, key=lambda x: (len(x), x)):
        c = courses[cid]
        if c.get("sexe") == "F":
            exclues["femmes"] += 1
            continue
        if "debut" not in c:
            exclues["sans_edition"] += 1
            continue
        if c["debut"] >= avant:
            exclues["apres"] += 1
            continue
        brut = cle_museo(c.get("nom"), c.get("pays"))
        via = "cle"
        if cid in alias_museo:
            ck, via = alias_museo[cid], "alias_museo"
            utilises_alias.add(cid)
        elif brut and brut in alias_courses:
            ck, via = alias_courses[brut], "alias_courses"
        else:
            ck = brut
        if ck:
            cles.setdefault(ck, []).append(cid)
        base = {"nom": c.get("nom"), "pays": c.get("pays") or None, "type": c.get("type"), "debut": c["debut"], "fin": c["fin"]}
        if ck:
            base["cle"] = ck
        if cid in championnats_set:
            sel_courses[cid] = dict(base, raison="championnat")
            continue
        e = index.get(ck) if ck else None
        if e is not None and e.get("cat") in CLASSES_INDEX:
            sel_courses[cid] = dict(base, raison="epreuve_suivie", via=via, classe_actuelle=e["cat"], classe_uci=e.get("cl"))
            continue
        annees: Dict[str, Any] = {}
        france = pays_normalise(c.get("pays"), "museo") == "FRA" or c.get("pays") == "FRA"
        if ck:
            for y in range(max(c["debut"], CQ_ANNEES[0]), min(c["fin"], avant - 1, CQ_ANNEES[1]) + 1):
                entrees = calendriers.get(y, {}).get(ck)
                if not entrees:
                    continue
                a: Dict[str, Any] = {"classe_cq": sorted({x.get("categorie") for x in entrees if x.get("categorie")})}
                if france:
                    a["decision"] = "retenue"
                else:
                    r = [top10_cq(y, x) for x in entrees]
                    if any(v is True for v in r):
                        a["decision"] = "retenue"
                    elif all(v is False for v in r):
                        a["decision"] = "ecartee_cq"
                    else:
                        a["decision"] = "a_decider"
                annees[str(y)] = a
        if annees:
            sel_courses[cid] = dict(base, raison="calendrier_uci_france" if france else "calendrier_uci_top10", annees=annees)
        else:
            sans_classe.append(cid)
    index_utiles = {s["cle"] for s in sel_courses.values() if s["raison"] == "epreuve_suivie"}
    return {
        "regle": REGLE_SELECTION, "avant": avant, "courses": sel_courses, "sans_classe": sans_classe,
        "exclues": exclues,
        "collisions": {k: sorted(v, key=int) for k, v in sorted(cles.items())
                       if len(v) > 1 and any(i in sel_courses for i in v)},
        "alias_museo_orphelins": sorted([i for i, k in alias_museo.items() if i not in courses or k not in index], key=int),
        "championnats_inconnus": sorted([i for i in championnats_set if i not in courses], key=int),
        "epreuves_sans_course": sorted(k for k, e in index.items() if e.get("cat") in CLASSES_INDEX and k not in index_utiles),
    }


def resumer_selection(sel: Dict[str, Any], taux: float = TAUX_EDITIONS) -> Dict[str, Any]:
    """Chiffres de la sélection (état-indépendants) : courses et éditions par raison ; requêtes si RIEN n'était encore collecté
    (1 albo par course, 1 page par édition ; les éditions des règles 1-2 sont estimées par la borne x `taux`)."""
    r: Dict[str, Any] = {}
    for raison in RAISONS:
        cs = {i: s for i, s in sel["courses"].items() if s["raison"] == raison}
        d: Dict[str, Any] = {"courses": len(cs)}
        if PHASE_DE[raison] == "index":
            borne = sum(max(0, min(s["fin"], sel["avant"] - 1) - s["debut"] + 1) for s in cs.values())
            d["editions_borne"], d["editions_estimees"] = borne, round(borne * taux)
        else:
            dec: Dict[str, int] = {}
            for s in cs.values():
                for a in s["annees"].values():
                    dec[a["decision"]] = dec.get(a["decision"], 0) + 1
            d["editions"] = sum(dec.values())
            d["decisions"] = dict(sorted(dec.items()))
        r[raison] = d
    r["sans_classe"] = len(sel["sans_classe"])
    return r


def _unites_course(s: Dict[str, Any], c: Dict[str, Any], avant: int, depuis: Optional[int]
                   ) -> List[Tuple[int, str, Optional[Dict[str, Any]]]]:
    """Unités de travail d'une course sélectionnée : (année, décision de la sélection, édition de l'albo ou None si l'albo n'est pas
    encore lu). Règles 1-2 : une unité par édition de l'albo (aucune tant que l'albo est inconnu)."""
    editions = c.get("editions")
    if PHASE_DE[s["raison"]] == "index":
        return [(e["annee"], "retenue", e) for e in (editions or []) if e["annee"] < avant and (depuis is None or e["annee"] >= depuis)]
    out: List[Tuple[int, str, Optional[Dict[str, Any]]]] = []
    for a, d in sorted(s["annees"].items()):
        y = int(a)
        if y >= avant or (depuis is not None and y < depuis):
            continue
        if editions is None:
            out.append((y, d["decision"], None))
        else:
            out.extend((y, d["decision"], e) for e in editions if e["annee"] == y)
    return out


def _etat_edition(sortie: str, cid: str, e: Dict[str, Any], decision: str, relire: bool) -> str:
    """ecrite | ecartee | ecartee_cq | abandon | a_lire | a_decider (une édition `ecartee` par la page Museo n'est jamais redemandée
    tant que la règle de sélection ne change pas ou sans --relire ; `ecartee_cq` n'est respectée que si CQ décide toujours)."""
    if os.path.exists(chemin_edition(sortie, cid, e["annee"], e["cod"])) and not relire:
        return "ecrite"
    memo = e.get("decision") if e.get("decision_regle") == REGLE_SELECTION else None
    if not relire and (memo == "ecartee" or (memo == "ecartee_cq" and decision == "ecartee_cq")):
        return memo
    if _echecs(e, "echecs") >= ECHECS_MAX and not relire:
        return "abandon"
    return decision if decision in ("a_decider", "ecartee_cq") else "a_lire"


def restant_selection(sel: Dict[str, Any], courses: Dict[str, Dict[str, Any]], sortie: str, avant: int, depuis: Optional[int] = None,
                      relire: bool = False, raisons: Optional[Tuple[str, ...]] = None) -> Dict[str, int]:
    """Travail restant d'après l'état courant (courses.json + fichiers écrits) : `albos_restants`, `editions_a_decider`, `editions_restantes`."""
    r = {"albos_restants": 0, "editions_a_decider": 0, "editions_restantes": 0}
    for cid, s in sel["courses"].items():
        if raisons and s["raison"] not in raisons:
            continue
        c = courses.get(cid) or {}
        us = _unites_course(s, c, avant, depuis)
        if c.get("editions") is None and (PHASE_DE[s["raison"]] == "index" or any(d != "ecartee_cq" for _, d, _ in us)):
            if _echecs(c, "albo_echecs") < ECHECS_MAX or relire:
                r["albos_restants"] += 1
        for _, d, e in us:
            if e is None:
                if d == "retenue":
                    r["editions_restantes"] += 1
                elif d == "a_decider":
                    r["editions_a_decider"] += 1
                continue
            st = _etat_edition(sortie, cid, e, d, relire)
            if st == "a_lire":
                r["editions_restantes"] += 1
            elif st == "a_decider":
                r["editions_a_decider"] += 1
    return r


def estimer_requetes(sel: Dict[str, Any], courses: Dict[str, Dict[str, Any]], sortie: str, taux: float = TAUX_EDITIONS) -> Dict[str, Any]:
    """Requêtes restantes estimées (hors réseau) : albos manquants + éditions restantes (éditions inconnues des règles 1-2 : borne x taux,
    moins les fichiers déjà écrits) ; `a_decider` compté au maximum (toutes lues) ; passages de 50 min (~900 pages à 3,2 s)."""
    avant = sel["avant"]
    r = restant_selection(sel, courses, sortie, avant)
    inconnues = 0.0
    for cid, s in sel["courses"].items():
        c = courses.get(cid) or {}
        if PHASE_DE[s["raison"]] == "index" and c.get("editions") is None:
            ecrites = len(os.listdir(os.path.join(sortie, "editions", cid))) if os.path.isdir(os.path.join(sortie, "editions", cid)) else 0
            borne = max(0, min(s["fin"], avant - 1) - s["debut"] + 1)
            inconnues += max(0.0, borne * taux - ecrites)
    total = r["albos_restants"] + r["editions_restantes"] + round(inconnues)
    r.update({"editions_index_inconnues_estimees": round(inconnues), "requetes_sans_a_decider": total,
              "requetes_avec_a_decider_max": total + r["editions_a_decider"]})
    r["passages_50min"] = round((total + r["editions_a_decider"]) * PAUSE_S / 3000, 1)
    return r


def _ecrire_si_change(chemin: str, obj: Any) -> bool:
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    texte = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    try:
        with open(chemin, encoding="utf-8") as f:
            if f.read() == texte:
                return False
    except OSError:
        pass
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texte)
    os.replace(tmp, chemin)
    return True


def preparer_selection(sortie: str, archives_dir: str, avant: int = AVANT_DEFAUT, alias_chemin: Optional[str] = None,
                       ecrire: bool = True) -> Dict[str, Any]:
    """Hors réseau : lit courses.json (découverte déjà faite), l'index des épreuves, les alias, le calendrier et les fichiers CQ ;
    écrit `<sortie>/selection.json` (déterministe : aucun horodatage, ordre trié, réécrit seulement s'il change)."""
    import collector
    reg = _lire_json(os.path.join(sortie, "courses.json"), {})
    alias_courses = collector.charger_alias(os.path.join(RACINE, "alias_courses.json"))
    alias_museo, championnats = charger_alias_museo(alias_chemin)
    index = charger_index_epreuves(archives_dir)
    calendriers = charger_calendriers_cq(archives_dir, alias_courses)
    sel = construire_selection(reg.get("courses", {}), index, calendriers,
                               lambda y, x: top10_cq_fichier(archives_dir, y, x), alias_courses, alias_museo, championnats, avant)
    sel["resume"] = resumer_selection(sel)
    if ecrire:
        _ecrire_si_change(os.path.join(sortie, "selection.json"), sel)
    est = estimer_requetes(sel, reg.get("courses", {}), sortie)
    print("[MUSEO] sélection : " + json.dumps({"resume": sel["resume"], "exclues": sel["exclues"],
                                                "collisions": len(sel["collisions"]),
                                                "alias_museo_orphelins": len(sel["alias_museo_orphelins"]),
                                                "championnats_inconnus": len(sel["championnats_inconnus"]),
                                                "epreuves_sans_course": len(sel["epreuves_sans_course"]),
                                                "estimation": est}, ensure_ascii=False, sort_keys=True))
    return sel


def _traiter_edition(sess: Session, sortie: str, cid: str, e: Dict[str, Any], decision: str, relire: bool, etapes: bool,
                     urls: Dict[str, str], resume: Dict[str, Any]) -> int:
    """Une édition de la sélection. Retourne le nombre d'étapes restantes (si `etapes`)."""
    st = _etat_edition(sortie, cid, e, decision, relire)
    if st == "ecrite":
        return lire_etapes_edition(sess, chemin_edition(sortie, cid, e["annee"], e["cod"]), resume, urls) if etapes else 0
    if st == "ecartee_cq":
        if e.get("decision") != "ecartee_cq" or e.get("decision_regle") != REGLE_SELECTION:
            e["decision"], e["decision_regle"] = "ecartee_cq", REGLE_SELECTION
            resume["ecartees_cq"] += 1
        return 0
    if st in ("ecartee", "abandon") or sess.epuise():
        return 0
    page = sess.page(e["url"])
    if not page:
        if sess.absente:
            _noter_echec(e, "echecs")
        resume["echecs"] += 1
        return 0
    if st == "a_decider":
        ed = lire_edition(page, {}, e["annee"])
        if not francais_top10_museo(ed["classement"], e["annee"]):
            e["decision"], e["decision_regle"] = "ecartee", REGLE_SELECTION
            if len(ed["classement"]) < 10:
                e["top10_incomplet"] = True
                resume["ecartees_incompletes"] += 1
            resume["ecartees"] += 1
            return 0
    ed = ecrire_edition(sess, cid, e, page, resume)
    e["decision"], e["decision_regle"] = "lue", REGLE_SELECTION
    memoriser_urls(sortie, page, urls)
    if etapes and ed.get("etapes"):
        return lire_etapes_edition(sess, chemin_edition(sortie, cid, e["annee"], e["cod"]), resume, urls)
    return 0


def lancer_selection(sortie: str, archives_dir: str, avant: int = AVANT_DEFAUT, depuis: Optional[int] = None,
                     listes: Tuple[str, ...] = LISTES_DEFAUT, relire: bool = False, budget_min: float = 0.0, max_requetes: int = 0,
                     decouverte_seule: bool = False, etapes: bool = False, fiches: bool = True, equipes: bool = False,
                     listes_coureurs: Tuple[str, ...] = (), raisons: Optional[Tuple[str, ...]] = None) -> Dict[str, Any]:
    """Collecte suivant `selection.json` (recalculée en début de passage, hors réseau). Ordre : découverte, puis phase `index` (albos des
    courses des règles 1-2, puis leurs éditions, années décroissantes), puis phase `calendrier` (règles 3-4, années décroissantes ; albo
    lu au besoin ; décision `a_decider` prise sur la page Museo lue), listes de coureurs, fiches. Étapes NON lues par défaut."""
    sess = Session(sortie, budget_min, max_requetes)
    reg = _lire_json(os.path.join(sortie, "courses.json"), {"source": "museociclismo.it"})
    courses = reg.setdefault("courses", {})
    resume: Dict[str, Any] = {"pages_listes": 0, "lignes_liste_illisibles": 0, "albos_lus": 0, "albos_sans_edition": 0,
                              "editions_lues": 0, "etapes_lues": 0, "echecs": 0, "profondeurs": [], "codes_pays_inconnus": {},
                              "pages_coureurs": 0, "listes_naissances": {}, "fiches_naissances": {},
                              "formats_date_inconnus": [], "naissances_discordantes": 0,
                              "ecartees": 0, "ecartees_incompletes": 0, "ecartees_cq": 0, "annees_sans_edition": 0}
    chemin_reg = os.path.join(sortie, "courses.json")
    pages_ok = decouvrir_courses(sess, listes, reg, resume)
    _ecrire_json(chemin_reg, reg, compact=True)
    sel = preparer_selection(sortie, archives_dir, avant)
    resume["selection"] = sel["resume"]
    urls = urls_fiches(sortie)
    etapes_restantes = 0
    depuis_ecriture = 0
    try:
        if not decouverte_seule:
            for phase in ("index", "calendrier"):
                cids = [i for i, s in sel["courses"].items() if PHASE_DE[s["raison"]] == phase and i in courses
                        and (not raisons or s["raison"] in raisons)]
                if phase == "index":
                    for cid in sorted(cids, key=int):
                        if courses[cid].get("editions") is None and (_echecs(courses[cid], "albo_echecs") < ECHECS_MAX or relire) \
                                and not sess.epuise() and not lire_albo_course(sess, cid, courses[cid], resume):
                            resume["echecs"] += 1
                        depuis_ecriture += 1
                        if depuis_ecriture >= 50:
                            _ecrire_json(chemin_reg, reg, compact=True)
                            depuis_ecriture = 0
                        sess.journal("phase index : albos, %d lus" % resume["albos_lus"])
                unites = []
                for cid in cids:
                    for annee, d, e in _unites_course(sel["courses"][cid], courses[cid], avant, depuis):
                        unites.append((-annee, int(cid), cid, annee, d, e))
                unites.sort(key=lambda u: u[:2])
                for _, _, cid, annee, d, e in unites:
                    c = courses[cid]
                    if e is None:                    # albo encore inconnu (phase calendrier) : lu seulement s'il y a quelque chose à lire
                        if c.get("editions") is None:
                            if d == "ecartee_cq" or sess.epuise() or (_echecs(c, "albo_echecs") >= ECHECS_MAX and not relire):
                                continue
                            if not lire_albo_course(sess, cid, c, resume):
                                resume["echecs"] += 1
                                continue
                        eds = [x for x in c["editions"] if x["annee"] == annee]
                        if not eds:
                            resume["annees_sans_edition"] += 1
                        for x in eds:
                            etapes_restantes += _traiter_edition(sess, sortie, cid, x, d, relire, etapes, urls, resume)
                    else:
                        etapes_restantes += _traiter_edition(sess, sortie, cid, e, d, relire, etapes, urls, resume)
                    depuis_ecriture += 1
                    if depuis_ecriture >= 50:
                        _ecrire_json(chemin_reg, reg, compact=True)
                        _ecrire_json(os.path.join(sortie, "urls_coureurs.json"), urls, compact=True)
                        depuis_ecriture = 0
                    sess.journal("phase %s : %d éditions lues, %d écartées" % (phase, resume["editions_lues"],
                                                                                resume["ecartees"] + resume["ecartees_cq"]))
    finally:
        _ecrire_json(chemin_reg, reg, compact=True)
        _ecrire_json(os.path.join(sortie, "urls_coureurs.json"), urls, compact=True)
    rest = restant_selection(sel, courses, sortie, avant, depuis, relire)
    coureurs_restants = 0
    if not decouverte_seule:
        if listes_coureurs:
            lire_listes_coureurs(sess, sortie, listes_coureurs, resume)
        if fiches:
            coureurs_restants = lire_fiches(sess, sortie, equipes, relire, resume)
    editions_restantes = rest["editions_restantes"] + etapes_restantes
    termine = pages_ok and rest["albos_restants"] == 0 and editions_restantes == 0 and rest["editions_a_decider"] == 0 \
        and coureurs_restants == 0 and not sess.abandon and not decouverte_seule
    if not pages_ok:
        phase_etat = "decouverte"
    elif any(restant_selection(sel, courses, sortie, avant, depuis, relire, (r,)) != {"albos_restants": 0, "editions_a_decider": 0,
                                                                                        "editions_restantes": 0}
             for r in ("championnat", "epreuve_suivie")) and not raisons:
        phase_etat = "index"
    elif rest["albos_restants"] or editions_restantes or rest["editions_a_decider"]:
        phase_etat = "calendrier"
    elif coureurs_restants:
        phase_etat = "fiches"
    else:
        phase_etat = "termine" if termine else "fin_de_passage"
    _ecrire_json(os.path.join(sortie, "etat.json"),
                 {"termine": bool(termine), "albos_restants": rest["albos_restants"],
                  "editions_a_decider": rest["editions_a_decider"], "editions_restantes": editions_restantes,
                  "coureurs_restants": coureurs_restants, "phase": phase_etat})
    prof = sorted(resume.pop("profondeurs"))
    if prof:
        resume["profondeur_mediane"] = prof[len(prof) // 2]
        resume["profondeur_min"], resume["profondeur_max"] = prof[0], prof[-1]
    resume["requetes"] = sess.requetes
    resume["echecs_reseau"] = sess.echecs
    resume["abandon"] = sess.abandon
    print("[MUSEO] synthèse : " + json.dumps(resume, ensure_ascii=False, sort_keys=True))
    return resume


# --------------------------------------------------------------------------------------------------
# Tests (sans réseau, pages réelles allégées)
# --------------------------------------------------------------------------------------------------

def _fixture(nom: str) -> str:
    with open(os.path.join(FIXTURES, nom), encoding="utf-8") as f:
        return f.read()


def _tests() -> None:
    # temps
    assert parse_temps("7h 0' 27\"") == 25227 and parse_temps("95h 57' 16\"") == 345436 and parse_temps("0h 0' 1\"") == 1
    assert parse_temps("07h\xa000' 27''") == 25227 and parse_temps("4:57:265") is None and parse_temps("") is None
    assert parse_temps("1h 61' 0\"") is None
    # naissance
    assert parse_naissance_liste("28.10.1990") == ("1990-10-28", "jour", "28.10.1990")
    assert parse_naissance_liste("1936")[:2] == ("1936", "annee") and parse_naissance_liste("")[0] is None
    assert parse_naissance_liste("31.02.1990")[0] is None and parse_naissance_liste("00.00.1950")[0] is None
    assert parse_naissance_fiche("11 maggio 1972")[:2] == ("1972-05-11", "jour")
    assert parse_naissance_fiche("maggio 1972")[0] is None and parse_naissance_fiche("1972")[:2] == ("1972", "annee")
    # liste de courses (Milano-…, cas ♀ et pays vide)
    page = _fixture("liste_courses.html")
    assert total_pages(page) == 106
    l = lire_liste_courses(page)
    assert len(l) == len(re.findall(r'<tr><th scope="row">', page)) and len(l) >= 6
    msr = [x for x in l if x["id"] == "459"][0]
    assert msr["nom"] == "Milano-Sanremo" and (msr["debut"], msr["fin"]) == (1907, 2026) and msr["sexe"] == "M"
    assert msr["slug"] == "Milano-Sanremo" and msr["pays"] == "ITA" and msr["type"] == "Linea"
    assert [x["sexe"] for x in l if x["id"] == "233900"] == ["F"] and [x["pays"] for x in l if x["id"] == "233900"] == [""]
    assert not course_retenue(dict([x for x in l if x["id"] == "233900"][0]), [], [], 2009, None, None)
    assert course_retenue(dict(msr), ["459"], ["ITA"], 2009, None, None)
    assert course_retenue(dict(msr), ["milano sanremo"], [], 2009, None, None)
    assert not course_retenue(dict(msr), ["giro di lombardia"], [], 2009, None, None)
    assert not course_retenue(dict(msr), [], ["FRA"], 2009, None, None) and not course_retenue(dict(msr), [], [], 1907, None, None)
    # albo
    a = lire_albo(_fixture("albo_milano_sanremo.html"))
    assert a["nom"] == "Milano-Sanremo" and a["type"] == "Linea" and a["pays"] == "ITA"
    e96 = [e for e in a["editions"] if e["annee"] == 1996][0]
    assert e96["n"] == 87 and e96["cod"] == "832" and e96["url"].endswith("/edizioni/87/832.html")
    assert e96.get("vainqueur", {}).get("id") == "2636" or "vainqueur" not in e96
    assert a["editions"][0]["date"] == "2026-03-21" and a["editions"][0]["vainqueur"]["nom"] == "Tadej POGACAR"
    # édition en ligne (Milano-Sanremo 1996) : ordre d'arrivée
    st: Dict[str, Any] = {}
    ed = lire_edition(_fixture("edition_milano_sanremo_1996.html"), st)
    assert (ed["annee"], ed["date"], ed["n"], ed["km"], ed["partants"], ed["arrives"]) == (1996, "1996-03-23", 87, 294.0, 198, 175)
    assert ed["depart"] == "Milano" and ed["arrivee"] == "Sanremo" and ed["type"] == "Linea" and ed["cod"] == "832"
    cl = ed["classement"]
    assert cl[0] == {"rang": 1, "id": "2636", "nom": "Gabriele COLOMBO", "nat": "ITA", "nat_site": "ITA", "temps_s": 25227}
    assert cl[1]["ecart_s"] == 1 and cl[1]["nat"] == "UKR" and cl[1]["id"] == "7911" and "ecart_vide" not in cl[1]
    assert cl[-1]["ecart_s"] == 987 and not ed["etapes"] and "etapes_endpoint" not in ed
    assert st.get("ecarts_vides_non_prefixe", 0) == 0 and st["lignes"] == len(cl)
    # édition par étapes (Tour de France 1996) : classement général, 22 étapes, point d'accès lu dans le script
    st = {}
    ed = lire_edition(_fixture("edition_tour_de_france_1996.html"), st)
    assert ed["type"] == "Tappe" and ed["cod"] == "5218" and ed["partants"] == 197 and ed["km"] == 3764.9
    assert ed["classement"][0]["nom"] == "Bjarne RIIS" and ed["classement"][0]["temps_s"] == 345436
    assert ed["classement"][1]["ecart_s"] == 101 and ed["classement"][2]["nat"] == "FRA"
    assert len(ed["etapes"]) == 22 and ed["etapes_endpoint"].endswith("GetTappaData.php?what=tappa_classifica&cod=")
    e = {x["cod"]: x for x in ed["etapes"]}
    assert e["23924"]["numero"] == "21" and e["23924"]["depart"] == "Palaiseau" and e["23924"]["km"] == 147.5
    assert e["23924"]["vainqueur"] == {"id": "950", "nom": "Fabio BALDATO"} and e["23924"]["temps_s"] == 12644
    assert e["23923"]["clm"] and e["23903"]["numero"] == "Prologo" and e["23903"]["clm"] and "clm" not in e["23922"]
    assert e["23911"]["vitesse_kmh"] == 23.707
    # classement d'étape (chargé par le JavaScript) : même tableau, écarts vides conservés tels quels
    st = {}
    cs = lire_classement_etape(_fixture("etape_23924_classifica.html"), st)
    assert cs[0]["rang"] == 1 and cs[0]["temps_s"] == 12644 and cs[1] == {"rang": 2, "id": "9743", "nom": "Frédéric MONCASSIN",
                                                                         "nat": "FRA", "nat_site": "FRA", "ecart_vide": True}
    assert st["ecarts_vides"] >= 2 and st.get("ecarts_vides_non_prefixe", 0) == 0
    # liste de coureurs (professionisti)
    lc = lire_liste_coureurs(_fixture("liste_coureurs_professionisti.html"))
    assert lc[0] == {"id": "72231", "cognome": "AADEL", "sexe": "M", "nome": "Reda", "naissance": "1990-10-28",
                     "precision": "jour", "nat": "MAR", "nat_site": "MAR"}
    assert lc[2]["lieu"] == "TONSBERG" and lc[2]["nat"] == "NOR" and lc[2]["nat_site"] == "NOR"
    assert any(c.get("precision") == "annee" for c in lc) or any("naissance" not in c for c in lc)
    # fiche coureur : naissance complète, équipes par année
    f = lire_fiche(_fixture("fiche_colombo.html"))
    assert f["nom"] == "Gabriele COLOMBO" and f["id"] == "2636" and f["categorie"] == "Professionista"
    assert f["naissance"] == "1972-05-11" and f["precision"] == "jour" and f["lieu"] == "VARESE" and f["nat"] == "ITA"
    eq = {e["annee"]: e for e in f["equipes"]}
    assert eq[1996] == {"annee": 1996, "id": "1512", "nom": "Gewiss - Playbus", "pays": "ITA"} and eq[2005]["pays"] == "SUI"
    # écarts vides : en tête (même temps ?) et en fin de tableau (inconnu ?) -> jamais interprétés, signalés non-préfixe
    st = {}
    cas = [("5h 0' 0\"", ""), ("", ""), ("", "0h 0' 9\""), ("", ""), ("", "bizarre")]
    html_l = "".join('<tr><td><span>%d°</span></td><td><a href="/content/ciclisti/ciclista/%d-X/index.html">C%d</a> (ITA)</td>'
                     '<td>%s</td><td>%s</td><td></td></tr>' % (i + 1, i + 1, i + 1, t, g) for i, (t, g) in enumerate(cas))
    lg = lire_lignes("<table>" + html_l + "</table>", st)
    assert lg[0]["temps_s"] == 18000 and lg[1]["ecart_vide"] and lg[2]["ecart_s"] == 9 and lg[3]["ecart_vide"]
    assert lg[4]["ecart_brut"] == "bizarre" and "ecart_s" not in lg[4]
    assert st["ecarts_vides"] == 2 and st["ecarts_vides_non_prefixe"] == 1 and st["ecarts_illisibles"] == 1
    # pays disparus : code d'époque dans `nat`, code brut dans `nat_site` ; TCH après 1992 ambigu ; inconnu compté
    st = {}
    pl = "".join('<tr><td><span>%d°</span></td><td><a href="/content/ciclisti/ciclista/%d-X/index.html">C%d</a> (%s)</td>'
                 '<td>1h 0\' 0"</td><td></td><td></td></tr>' % (i + 1, i + 1, i + 1, n) for i, n in enumerate(["RFA", "CSI", "TCH", "APA"]))
    lg = lire_lignes("<table>" + pl + "</table>", st, 1992)
    assert [(l["nat_site"], l.get("nat")) for l in lg] == [("RFA", "FRG"), ("CSI", "EUN"), ("TCH", "TCH"), ("APA", None)], lg
    assert st["codes_pays_inconnus"] == {"APA": 1}
    assert lire_lignes("<table>" + pl + "</table>", {}, 2000)[2].get("nat") == "CZE"   # Tchèque étiqueté TCH après 1992 : CZE (décision du 18/11/2026)
    # clés des courses retenues : liste ou dictionnaire
    import tempfile as _t
    with _t.TemporaryDirectory() as d0:
        for contenu in (["milano sanremo|ITA"], {"milano sanremo|ITA": {}}):
            with open(os.path.join(d0, "c.json"), "w", encoding="utf-8") as f:
                json.dump(contenu, f)
            assert cles_suivies(os.path.join(d0, "c.json")) == {"milano sanremo|ITA"}
    assert "amstel gold race|NED" in cles_suivies()
    # URL : accents et espaces encodés, liens http du site ramenés en relatif
    assert url_absolue("/content/corse/corsa/97251-Coppa-Ardigò/index.html") == BASE + "/content/corse/corsa/97251-Coppa-Ardig%C3%B2/index.html"
    assert url_absolue("/a/b%20c.html") == BASE + "/a/b%20c.html"
    assert chemin_relatif("http://www.museociclismo.it/content/ciclisti/ciclista/1-X/index.html?t=1") == "/content/ciclisti/ciclista/1-X/index.html"
    # dossier de sortie : une édition lue n'est jamais relue, étapes reprises
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        sess = Session(d)
        resume = {"editions_lues": 0, "etapes_lues": 0, "profondeurs": [], "codes_pays_inconnus": {}}
        page = _fixture("edition_tour_de_france_1996.html")
        c = ecrire_edition(sess, "5208", {"annee": 1996, "cod": "5218", "url": "/x.html"}, page, resume)
        chemin = chemin_edition(d, "5208", 1996, "5218")
        assert os.path.exists(chemin) and c["course_id"] == "5208" and resume["editions_lues"] == 1
        assert chemin_edition(d, "5208", 1996, "9999").endswith("1996-9999.json")
        sess.max_requetes = 1
        sess.requetes = 1                      # budget épuisé : aucune requête, étapes restantes comptées
        assert lire_etapes_edition(sess, chemin, resume) == 22
        ids = coureurs_attendus(d)
        assert "10915" in ids and ids == sorted(ids, key=int)
        urls: Dict[str, str] = {}
        assert memoriser_urls(d, page, urls) and "10915" in urls and urls["10915"].startswith("/content/ciclisti/ciclista/10915-")
    # échecs : un par jour, abandon après ECHECS_MAX jours ; compteur sans marque de règle = à relire ; panne = rien de noté
    o: Dict[str, Any] = {}
    assert _noter_echec(o, "echecs") and not _noter_echec(o, "echecs") and o["echecs"] == 1
    for _ in range(ECHECS_MAX - 1):
        o["echecs_jour"] = "2026-01-01"
        assert _noter_echec(o, "echecs")
    assert _echecs(o, "echecs") >= ECHECS_MAX
    ancien = {"echecs": 3}
    assert _echecs(ancien, "echecs") == 0 and _noter_echec(ancien, "echecs") and ancien["echecs"] == 1
    with tempfile.TemporaryDirectory() as d:
        class Panne(Session):
            def page(self, rel, mettre_en_cache=False):
                self.requetes += 1
                self.absente = self.statut_faux in (404, 410)
                return None
        sp = Panne(d)
        e = {"echecs": 3, "cod": "1"}
        sp.statut_faux = 503
        edd = {"etapes": [e], "etapes_endpoint": "/x?"}
        _ecrire_json(os.path.join(d, "ed.json"), edd)
        lire_etapes_edition(sp, os.path.join(d, "ed.json"), {"etapes_lues": 0})
        assert _lire_json(os.path.join(d, "ed.json"), {})["etapes"][0] == e    # 503 : rien noté
        sp.statut_faux = 404
        lire_etapes_edition(sp, os.path.join(d, "ed.json"), {"etapes_lues": 0})
        assert _lire_json(os.path.join(d, "ed.json"), {})["etapes"][0]["echecs"] == 1       # 404 : règle neuve, 1 échec
    # --- sélection élargie : clés, règles 1 à 5, décisions mémorisées (aucune requête) ---
    assert gp("gp de plouay|FRA") == "gp de plouay|FRA" and cle_museo("G.P. Ouest-France", "FRA") == "gp ouest france|FRA"
    assert cle_museo("Tour de France 1996", "FRA") == "tour de france|FRA" and cle_museo("X", "") is None
    assert francais_top10_museo([{"rang": 11, "nat": "FRA", "nat_site": "FRA"}, {"rang": 3, "nat": "ITA", "nat_site": "ITA"}]) is False
    assert francais_top10_museo([{"rang": 1, "nat": "ITA", "nat_site": "ITA"}, {"rang": 10, "nat": "FRA", "nat_site": "FRA"}]) is True
    assert francais_top10_cq([[11, 1, "FRA", "X", "", 0, 1], [2, 2, "BEL", "X", "", 0, 1]]) is False
    assert francais_top10_cq([[10, 1, "FRA", "X", "", 0, 1]]) is True
    cs = {"1": {"nom": "Milano-Sanremo", "pays": "ITA", "debut": 1907, "fin": 2026, "type": "Linea", "sexe": "M"},
          "2": {"nom": "G.P. Foo", "pays": "FRA", "debut": 1999, "fin": 2005, "type": "Linea", "sexe": "M"},
          "3": {"nom": "Trofeo Bar", "pays": "ITA", "debut": 1999, "fin": 2008, "type": "Linea", "sexe": "M"},
          "4": {"nom": "Locale", "pays": "FRA", "debut": 1960, "fin": 1980, "type": "Linea", "sexe": "M"},
          "5": {"nom": "Dames", "pays": "ITA", "debut": 1999, "fin": 2008, "type": "Linea", "sexe": "F"},
          "6": {"nom": "Championnat X", "pays": "FRA", "debut": 1907, "fin": 2026, "type": "Linea", "sexe": "M"},
          "7": {"nom": "Ancien nom", "pays": "BEL", "debut": 1950, "fin": 2008, "type": "Linea", "sexe": "M"},
          "8": {"nom": "Futur", "pays": "BEL", "debut": 2010, "fin": 2012, "type": "Linea", "sexe": "M"},
          "9": {"nom": "Sans date", "pays": "BEL", "type": "Linea", "sexe": "M"}}
    idx = {"milano sanremo|ITA": {"cat": "WT", "cl": "1.UWT"}, "nouveau nom|BEL": {"cat": "Pro", "cl": "1.Pro"},
           "championnat x|FRA": {"cat": None, "cl": "CN"}}
    cal = {2003: {"gp foo|FRA": [{"id": 10, "categorie": "1.3"}], "trofeo bar|ITA": [{"id": 11, "categorie": "1.2"}]},
           2004: {"trofeo bar|ITA": [{"id": 12, "categorie": "1.1"}]}, 2005: {"trofeo bar|ITA": [{"id": 13, "categorie": "1.1"}]},
           2007: {"trofeo bar|ITA": [{"id": 14, "categorie": "1.HC"}]}, 2000: {"locale|FRA": [{"id": 15, "categorie": "CDM"}]}}
    t10 = {10: None, 11: True, 12: False, 13: None, 14: None}
    sel = construire_selection(cs, idx, cal, lambda y, x: t10[x["id"]], {}, {"7": "nouveau nom|BEL"}, ["6"], 2009)
    r = {i: s["raison"] for i, s in sel["courses"].items()}
    assert r == {"1": "epreuve_suivie", "2": "calendrier_uci_france", "3": "calendrier_uci_top10", "6": "championnat",
                 "7": "epreuve_suivie"}, r
    assert sel["courses"]["1"]["classe_actuelle"] == "WT" and sel["courses"]["7"]["via"] == "alias_museo"
    assert sel["courses"]["2"]["annees"] == {"2003": {"classe_cq": ["1.3"], "decision": "retenue"}}
    assert {a: d["decision"] for a, d in sel["courses"]["3"]["annees"].items()} == {
        "2003": "retenue", "2004": "ecartee_cq", "2005": "a_decider", "2007": "a_decider"}
    assert sel["courses"]["3"]["annees"]["2007"]["classe_cq"] == ["1.HC"]       # classe CQ brute, jamais convertie
    assert sel["sans_classe"] == ["4"] and sel["exclues"] == {"femmes": 1, "sans_edition": 1, "apres": 1}
    assert sel["alias_museo_orphelins"] == [] and sel["championnats_inconnus"] == []
    assert construire_selection(cs, idx, cal, lambda y, x: t10[x["id"]], {}, {"7": "inconnu|BEL"}, ["99"], 2009)["alias_museo_orphelins"] == ["7"]
    # avant 1999 : règles 1 et 2 seulement (course 3 hors calendrier CQ avant 1999 : aucune année)
    assert construire_selection({"3": dict(cs["3"], debut=1990, fin=1998)}, idx, cal, lambda y, x: True, {}, {}, [], 2009)["sans_classe"] == ["3"]
    sel2 = construire_selection(cs, idx, cal, lambda y, x: t10[x["id"]], {}, {"7": "nouveau nom|BEL"}, ["6"], 2009)
    assert json.dumps(sel, sort_keys=True) == json.dumps(sel2, sort_keys=True)          # déterminisme
    rs = resumer_selection(sel)
    assert rs["calendrier_uci_top10"]["decisions"] == {"a_decider": 2, "ecartee_cq": 1, "retenue": 1} and rs["sans_classe"] == 1
    assert rs["epreuve_suivie"]["editions_borne"] == (2008 - 1907 + 1) + (2008 - 1950 + 1)
    # travail restant et décisions mémorisées
    with tempfile.TemporaryDirectory() as d1:
        courses = {i: dict(c) for i, c in cs.items()}
        assert restant_selection(sel, courses, d1, 2009) == {"albos_restants": 5, "editions_a_decider": 2, "editions_restantes": 2}
        ed = lambda a, **k: dict({"annee": a, "cod": str(a), "url": "/e/%d" % a}, **k)
        courses["3"]["editions"] = [ed(2003), ed(2004), ed(2005), ed(2007, decision="ecartee", decision_regle=REGLE_SELECTION)]
        assert restant_selection(sel, courses, d1, 2009, None, False, ("calendrier_uci_top10",)) == {
            "albos_restants": 0, "editions_a_decider": 1, "editions_restantes": 1}                 # 2004 ecartee_cq : pas de travail
        assert restant_selection(sel, courses, d1, 2009, None, True, ("calendrier_uci_top10",))["editions_a_decider"] == 2   # --relire
        e04 = courses["3"]["editions"][1]
        class Fausse(Session):
            def page(self, rel, mettre_en_cache=False):
                self.requetes += 1
                p = _fixture("edition_milano_sanremo_1996.html")
                return p.replace("(FRA)", "(BEL)") if "e/2005" in rel else p
        fs = Fausse(d1)
        res = {"editions_lues": 0, "etapes_lues": 0, "profondeurs": [], "codes_pays_inconnus": {}, "ecartees": 0, "ecartees_incompletes": 0,
               "ecartees_cq": 0, "echecs": 0}
        # a_decider : page sans Français dans son top 10 (FRA remplacé par BEL) -> écartée, rien écrit, mémorisée, jamais redemandée
        e05 = courses["3"]["editions"][2]
        _traiter_edition(fs, d1, "3", e05, "a_decider", False, False, {}, res)
        assert e05["decision"] == "ecartee" and res["ecartees"] == 1 and fs.requetes == 1 and not os.path.exists(chemin_edition(d1, "3", 2005, "2005"))
        _traiter_edition(fs, d1, "3", e05, "a_decider", False, False, {}, res)
        assert fs.requetes == 1                                                                    # pas de seconde requête
        # ecartee_cq : décision mémorisée sans requête ; retenue : page écrite, décision `lue`
        _traiter_edition(fs, d1, "3", e04, "ecartee_cq", False, False, {}, res)
        assert e04["decision"] == "ecartee_cq" and fs.requetes == 1 and res["ecartees_cq"] == 1
        e03 = courses["3"]["editions"][0]
        e03["cod"] = "832"                       # cod de la page de la fixture : le fichier écrit est reconnu ensuite
        _traiter_edition(fs, d1, "3", e03, "retenue", False, False, {}, res)
        assert e03["decision"] == "lue" and fs.requetes == 2 and os.path.exists(os.path.join(d1, "editions", "3", "2003.json")) and res["editions_lues"] == 1
        _traiter_edition(fs, d1, "3", e03, "retenue", False, False, {}, res)
        assert fs.requetes == 2
        # ancienne règle : une décision `ecartee` d'une autre version est refaite
        e05["decision_regle"] = REGLE_SELECTION - 1
        assert _etat_edition(d1, "3", e05, "a_decider", False) == "a_decider"
        # a_decider avec un Français 9e (Milano-Sanremo 1996) : page écrite, décision `lue`
        e07 = courses["3"]["editions"][3]
        e07.pop("decision"), e07.pop("decision_regle")
        _traiter_edition(fs, d1, "3", e07, "a_decider", False, False, {}, res)
        assert e07["decision"] == "lue" and os.path.exists(os.path.join(d1, "editions", "3", "2007.json"))
        # preparer_selection : fichiers lus, selection.json écrit une fois (réécriture identique = False)
        assert _ecrire_si_change(os.path.join(d1, "s.json"), sel) and not _ecrire_si_change(os.path.join(d1, "s.json"), sel)
    # alias_museo.json (validé par le propriétaire le 18/11/2026) : 11 alias d'épreuves + 4 championnats ; 41416 (Vlaamse Pijl, pas E3) jamais aliasée
    al, ch = charger_alias_museo(os.path.join(RACINE, "alias_museo.json"))
    assert len(al) == 11 and sorted(ch) == ["176524", "20739", "2634", "58073"] and "41416" not in al and al["2751"] == "donostia san sebastian klasikoa|ESP"
    print("[MUSEO] tests : OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--test", action="store_true", help="tests sans réseau")
    ap.add_argument("--sortie", default=SORTIE_DEFAUT, help="dossier de sortie (défaut : ARCHIVES_DIR/sources/museo)")
    ap.add_argument("--avant", type=int, default=AVANT_DEFAUT, help="éditions strictement avant cette année (défaut 2009)")
    ap.add_argument("--depuis", type=int, default=None, help="éditions à partir de cette année")
    ap.add_argument("--courses", default="", help="liste : id de course (459) ou nom exact (Milano-Sanremo ; casse et ponctuation ignorées)")
    ap.add_argument("--suivies", action="store_true", help="seulement les courses dont la clé d'édition figure dans series_historiques.json")
    ap.add_argument("--cles", default=None, help="fichier JSON de clés d'édition (« nom normalisé|PAYS », dictionnaire ou liste) : seulement ces courses (rapprochement exact)")
    ap.add_argument("--pays", default="", help="liste de codes pays de la course (ITA,FRA)")
    ap.add_argument("--listes", default=",".join(LISTES_DEFAUT), help="listes de courses : linea,tappe,campionati")
    ap.add_argument("--relire", action="store_true", help="relire aussi les éditions et fiches déjà écrites")
    ap.add_argument("--budget-min", type=float, default=0.0, help="budget de temps en minutes (0 = illimité)")
    ap.add_argument("--max-requetes", type=int, default=0, help="plafond de requêtes du passage (0 = illimité ; essais)")
    ap.add_argument("--decouverte-seule", action="store_true", help="ne lit que les listes de courses")
    ap.add_argument("--sans-etapes", action="store_true", help="ne lit pas les classements d'étape")
    ap.add_argument("--sans-fiches", action="store_true", help="ne lit pas les fiches des coureurs")
    ap.add_argument("--equipes", action="store_true", help="lit aussi la fiche des coureurs connus par une liste (équipes par année)")
    ap.add_argument("--preparer-selection", action="store_true", help="HORS RÉSEAU : écrit selection.json (règles de sélection élargie, raison de chaque course / édition) et affiche les chiffres")
    ap.add_argument("--selection", action="store_true", help="collecte suivant selection.json (recalculée en début de passage) au lieu de --suivies ; étapes non lues par défaut")
    ap.add_argument("--archives", default=ARCHIVES_DIR, help="dossier des archives (entites/courses/index.json, sources/cqranking) pour la sélection")
    ap.add_argument("--etapes", action="store_true", help="avec --selection : lit aussi les classements d'étape (non lus par défaut)")
    ap.add_argument("--raisons", default="", help="avec --selection : sous-ensemble de " + ",".join(RAISONS))
    ap.add_argument("--listes-coureurs", default="", help="parcourt ces listes de coureurs (professionisti,dilettanti…) : dates de naissance")
    a = ap.parse_args()
    if a.test:
        _tests()
        return 0
    listes = tuple(x.strip() for x in a.listes.split(",") if x.strip() in LISTES_COURSES) or LISTES_DEFAUT
    lc = tuple(x.strip() for x in a.listes_coureurs.split(",") if x.strip() in LISTES_COUREURS)
    if a.preparer_selection:
        preparer_selection(a.sortie, a.archives, a.avant)
        return 0
    if a.selection:
        lancer_selection(a.sortie, a.archives, a.avant, a.depuis, listes, a.relire, a.budget_min, a.max_requetes, a.decouverte_seule,
                         a.etapes and not a.sans_etapes, not a.sans_fiches, a.equipes, lc,
                         tuple(x.strip() for x in a.raisons.split(",") if x.strip() in RAISONS) or None)
        return 0
    lancer(a.sortie, a.avant, a.depuis, a.courses.split(","), a.pays.split(","), a.suivies, listes, a.relire,
           a.budget_min, a.max_requetes, a.decouverte_seule, not a.sans_etapes, not a.sans_fiches, a.equipes, lc, a.cles)
    return 0


if __name__ == "__main__":
    sys.exit(main())
