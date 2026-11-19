#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clics sur le cyclisme (clicssurlecyclisme.net) : fiches de coureurs (état civil, équipe de chaque saison, résultats
choisis), collecteur étape 1 (pas d'intégration). Étude : docs/recherche/clics_collecte.md.

ACCORD : le 19/11/2026, le site a donné au propriétaire du projet son accord pour être lu par programme et pour afficher
ses données, avec le crédit « Clics sur le cyclisme ».
Politesse : robots.txt lu à chaque passage et respecté (règles de `*` ; `Crawl-delay` de `*` repris s'il est plus long),
User-Agent honnête « courses-cyclistes (accord Clics sur le cyclisme) », >= 3,2 s entre requêtes, découverte par le
`sitemap.xml` déclaré dans robots.txt (AUCUNE URL devinée : ni index, ni dossier, ni plage), une page de coureurs n'est
demandée qu'une fois (relue seulement si son `lastmod` du sitemap a changé, ou avec `--relire`), abandon de l'hôte sur
403 / 429 / challenge (`netutil.hote_bloque`) et après 8 échecs de suite. Seules les requêtes de `robots.txt` et du
sitemap se répètent à chaque passage (c'est la source du `lastmod`). Aucun HTML dans le dépôt : seul le JSON est gardé
(une page pèse ~370 Ko, ~30 Ko une fois les `<span>` d'export Excel retirés) ; `--garder-html` écrit un cache gzip local.

Structure (étude du 19/11/2026) : un annuaire de fiches de coureurs, pas une base d'équipes. Une page `pages/<dossier>/<slug>.html`
= un tableau Excel de 4 colonnes, SANS identifiant ni ancre, qui liste tous les coureurs d'une plage alphabétique (~19, 1 à 45)
ou un seul coureur notable. Lecture positionnelle :
  - nouveau coureur : col. 1 = `NOM Prénom` (nom en majuscules ; `X dit Y`), col. 2 = pays en français (`FRANCE`, `G-B`,
    `KENYA/G-B`), col. 3 = code libre éventuel (`CDP 149`), col. 4 = `°jj-mm-aaaa [à lieu]` ;
  - ligne d'état civil : col. 4 = `†jj-mm-aaaa [à lieu]` (décès), col. 2 = variante de nom ;
  - ligne d'année : col. 3 = `1999`, col. 4 = équipe de la saison `SPONSORS[/CLUB (dép.)][/CATÉGORIE][/MM STAGIAIRE ÉQUIPE]` ;
  - ligne de résultat : col. 3 = `jj-mm`, col. 4 = texte libre (`1er du Grand Prix Alanya (Turq)`).
Pièges gérés : les lignes de crédit `Palmarès établi par` / `Claude Chatelier` sont en col. 1 au milieu d'une fiche (avec une année ou
une date en col. 3 : ce sont des lignes de données, pas des coureurs) ; des homonymes figurent dans la même page (deux entrées, jamais
fusionnées : le rang dans la page les distingue) ; coquilles de dates (`°20-10-1190`, `°20-021891`) = pas de date, le brut est gardé et
la coquille comptée ; aucune fusion de coureurs sur le seul nom ; jamais « France » déduit d'un pays absent.

Règle cardinale du projet : aucune valeur inventée. Un champ absent reste absent. Interprétations (déterministes) :
  - pays : `pays_site` = mot du site tel qu'écrit ; `nat` = code canonique de `pays_historiques.json` (`sources.clics`, table explicite)
    seulement si le mot y figure ; un pays double (`KENYA/G-B`, `AFN/FRANCE`) reste brut (`pays_double: true`, pas de `nat`) ; un
    mot inconnu : pas de `nat`, compté (`codes_pays_inconnus`) ;
  - naissance / décès : `AAAA-MM-JJ` seulement pour un jour complet valide (1700 -> année en cours), précision `jour` ; année seule :
    `AAAA`, précision `annee` (`incertaine` si le site met « ? ») ; sinon rien (le texte brut reste dans `naissance_brut` /
    `deces_brut`, coquille comptée dans `dates_invalides`) ; lieu = texte après « à », brut ;
  - équipe de la saison : `equipe_brut` tel qu'écrit + découpage par « / » (sans rapprochement ni interprétation) : `principal` (1er segment,
    sponsors ou club), `club`, `departement` (« (91) »), `categorie`, `stagiaire_depuis` (mois) / `stagiaire_equipe` ; aucun code UCI ni niveau ;
  - résultat : `texte` brut ; `rang` (`1er`, `56è`, `3°`, `2e`), `ex_aequo`, `etape` (« 4è étape ») lus seulement quand ils sont écrits ;
    jamais converti en classement.

Sortie (`--sortie`, défaut ARCHIVES_DIR/sources/clics) : `pages.json` (`{chemin relatif: {lastmod, lastmod_lu, libelle, lu_le,
nb_coureurs, empreinte}}`), `plages/<dossier>/<slug>.json` (coureurs d'une page, dans l'ordre), `etat.json` (`{"termine",
"pages_restantes", "pages_a_relire"}`, sans horodatage : lu par un workflow pour l'auto-relance), `introuvables.json` (pages absentes ou
de structure inconnue : un essai compté par jour, abandon après 2), `cache/` (gzip, seulement avec `--garder-html`).
Ordre de lecture : pages d'un ou deux jetons de slug (coureurs notables), puis pages dont la plage contient le plus de coureurs déjà connus
(`entites/coureurs`, `sources/cqranking/coureurs.json`, calculé au démarrage sans réseau), puis le reste ; heuristique d'ordre seulement.

    python clics.py --sortie DOSSIER [--archives DOSSIER] [--budget-min N] [--max-requetes N] [--pages g/gallopin,pages/b/] [--relire]
                    [--decouverte-seule] [--sans-decouverte] [--garder-html]
    python clics.py --test            # tests sans réseau (pages réelles allégées de tools/fixtures/clics/)
"""
import argparse
import bisect
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
from pays import pays_normalise

BASE = "https://www.clicssurlecyclisme.net/"
HOTE = "www.clicssurlecyclisme.net"
USER_AGENT = "courses-cyclistes (accord Clics sur le cyclisme)"
PAUSE_S = 3.2                      # >= 3 s entre deux requêtes (choix du projet : le site n'impose aucun délai à `*`)
netutil.HOST_DELAYS[HOTE] = PAUSE_S
DELAI_LECTURE_S = 60.0             # pages de ~370 Ko non compressées
ARCHIVES_DIR = os.environ.get("ARCHIVES_DIR") or os.path.join("data", "archives")
SORTIE_DEFAUT = os.path.join(ARCHIVES_DIR, "sources", "clics")
RACINE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(RACINE, "tools", "fixtures", "clics")
ECHECS_MAX = 2                     # une page absente (404) ou de structure inconnue 2 jours différents n'est plus redemandée
ECHECS_DE_SUITE_MAX = 8            # abandon propre du passage
# Règle de comptage (voir mdc.REGLE_ECHECS) : une panne (réseau, 5xx, site abandonné) ne note rien, au plus un essai compté par page et par
# jour ; une entrée de `introuvables.json` sans `regle` ou de règle plus ancienne est re-tentée, compteur remis à 0.
REGLE_ECHECS = 2
SOURCE = "clics-sur-le-cyclisme"
ANNEE_MIN = 1700
RE_PAGE = re.compile(r"^pages/[^/]+/[^/]+\.html$")


def _essais(manques: Dict[str, Dict[str, Any]], rel: str) -> int:
    """Essais comptés de la page `rel` (0 pour une entrée de règle ancienne : à relire)."""
    m = manques.get(rel) or {}
    return m.get("essais", 0) if m.get("regle", 0) >= REGLE_ECHECS else 0


def _noter_manque(manques: Dict[str, Dict[str, Any]], rel: str, motif: str = "absente") -> bool:
    """Compte un essai raté (page absente ou structure inconnue) : au plus un par jour. Vrai si l'entrée a changé."""
    maintenant = _maintenant()
    n = _essais(manques, rel)
    if n and manques[rel].get("dernier_essai", "")[:10] == maintenant[:10]:
        return False
    manques[rel] = {"essais": n + 1, "dernier_essai": maintenant, "regle": REGLE_ECHECS, "motif": motif}
    return True


def _maintenant() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------------------------------
# robots.txt et sitemap
# --------------------------------------------------------------------------------------------------

class Robots:
    """robots.txt : règles du groupe qui nous vise (jeton `courses-cyclistes`), sinon `*`. Règle la plus longue gagne (Allow à
    égalité) ; `*` et `$` des motifs sont gérés. `sitemaps` : lignes `Sitemap:` ; `delai` : Crawl-delay du groupe retenu."""

    def __init__(self, texte: str = ""):
        groupes: List[Tuple[List[str], List[Tuple[bool, str]], Optional[float]]] = []
        self.sitemaps: List[str] = []
        agents: List[str] = []
        regles: List[Tuple[bool, str]] = []
        delai: Optional[float] = None
        en_regles = False
        for brut in (texte or "").splitlines():
            ligne = brut.split("#", 1)[0].strip()
            if ":" not in ligne:
                continue
            cle, _, val = ligne.partition(":")
            cle, val = cle.strip().lower(), val.strip()
            if cle == "sitemap":
                if val:
                    self.sitemaps.append(val)
                continue
            if cle == "user-agent":
                if en_regles:
                    groupes.append((agents, regles, delai))
                    agents, regles, delai, en_regles = [], [], None, False
                agents.append(val.lower())
            elif cle in ("allow", "disallow"):
                en_regles = True
                if val or cle == "allow":
                    regles.append((cle == "allow", val))
            elif cle == "crawl-delay":
                en_regles = True
                try:
                    delai = float(val)
                except ValueError:
                    pass
        if agents:
            groupes.append((agents, regles, delai))
        retenu = None
        for jeton in ("courses-cyclistes", "*"):
            for ag, rg, dl in groupes:
                if any(a == jeton or (jeton != "*" and a and a in jeton) for a in ag):
                    retenu = (rg, dl)
                    break
            if retenu:
                break
        self.regles, self.delai = retenu if retenu else ([], None)

    @staticmethod
    def _motif(motif: str) -> "re.Pattern[str]":
        fin = motif.endswith("$")
        corps = re.escape(motif[:-1] if fin else motif).replace(r"\*", ".*")
        return re.compile("^" + corps + ("$" if fin else ""))

    def autorise(self, chemin: str) -> bool:
        """`chemin` : partie chemin de l'URL (commence par « / »)."""
        meilleur: Tuple[int, bool] = (-1, True)
        for allow, motif in self.regles:
            if not motif:
                continue
            if self._motif(motif).match(chemin):
                taille = len(motif)
                if taille > meilleur[0] or (taille == meilleur[0] and allow):
                    meilleur = (taille, allow)
        return meilleur[1]


def lire_sitemap(xml: str) -> Tuple[Dict[str, Optional[str]], List[str]]:
    """Sitemap -> ({chemin relatif d'une page de coureurs: lastmod}, sous-sitemaps d'un index de sitemaps). Seules les URL de
    `pages/<dossier>/<slug>.html` de notre hôte sont gardées (http normalisé en https) ; ni dossiers, ni autres rubriques."""
    pages: Dict[str, Optional[str]] = {}
    for m in re.finditer(r"<url>\s*<loc>\s*(.*?)\s*</loc>(?:\s*<lastmod>\s*(.*?)\s*</lastmod>)?", xml or "", flags=re.S):
        url = _html.unescape(m.group(1))
        p = urllib.parse.urlparse(url)
        if p.netloc != HOTE:
            continue
        rel = p.path.lstrip("/")
        if RE_PAGE.match(rel):
            pages[rel] = (m.group(2) or "").strip() or None
    sous = [_html.unescape(u) for u in re.findall(r"<sitemap>\s*<loc>\s*(.*?)\s*</loc>", xml or "", flags=re.S)]
    return pages, sous


# --------------------------------------------------------------------------------------------------
# Lecture du HTML (expressions régulières : tableau très régulier, aucune dépendance)
# --------------------------------------------------------------------------------------------------

def _txt(fragment: str) -> str:
    """HTML -> texte : balises retirées, entités décodées, espaces (dont insécables) réduits."""
    t = _html.unescape(re.sub(r"<[^>]+>", "", fragment or ""))
    return re.sub(r"\s+", " ", t.replace("\xa0", " ")).strip()


RE_ANNEE = re.compile(r"^\d{4}$")
RE_JJMM = re.compile(r"^\d{1,2}-\d{1,2}(?:\s*/\s*\d{1,2}-\d{1,2})?$")
RE_DATE_COMPLETE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})(?:\s+(?:à|a)\s+(.+?))?\s*$")
RE_ANNEE_SEULE = re.compile(r"^(\d{4})(\s*\?)?(?:\s+(?:à|a)\s+(.+?))?\s*$")
PARTICULES = {"de", "du", "des", "d", "van", "von", "der", "den", "da", "di", "del", "della", "dos", "le", "la", "ten", "ter", "el", "al"}
RE_RANG = re.compile(r"^(\d{1,3})(?:er|ère|ere|è|ème|eme|e|°|º)(?=[\s.,;:)]|$)", re.I)
RE_ETAPE = re.compile(r"\b(\d{1,2})(?:er|ère|ere|è|ème|eme|e|°|º)\s*[ée]tape\b", re.I)
RE_STAGIAIRE = re.compile(r"^(?:(\d{1,2})\s+)?STAGIAIRES?\b\s*(.*)$", re.I)
RE_DEPARTEMENT = re.compile(r"\((\d{2,3}|2[AB])\)")
RE_CATEGORIE = re.compile(r"^(?:[ée]lite|junior|cadet|espoir|amateur|minime|benjamin|senior|nationale|r[ée]gionale|pass\b|open\b|"
                          r"\d+\S*\s+cat[ée]gorie|\d+\S*\s+cat\b|d[nm]\s?\d)", re.I)


def est_temporel(c3: str) -> bool:
    """Colonne 3 d'une ligne d'année (`1999`) ou de résultat (`01-06`, `30-01/03-02`)."""
    return bool(RE_ANNEE.match(c3) or RE_JJMM.match(c3))


def lire_nom(c1: str) -> Dict[str, Any]:
    """`GABELLI Giovan-Battista` / `GERARDIN` / `DE LA FUENTE Pedro` / `X Y dit Z` -> affiche, nom_famille, prenom, surnom.
    Le nom de famille = jetons en majuscules (et particules en minuscules qui les précèdent) ; le reste = prénom. Aucun jeton en
    majuscules : tout reste dans `affiche`."""
    out: Dict[str, Any] = {"nom_affiche": c1}
    base, _, surnom = re.split(r"(\s+dit\s+)", c1, maxsplit=1) if re.search(r"\s+dit\s+", c1) else (c1, "", "")
    if surnom.strip():
        out["surnom"] = surnom.strip()
    jetons = base.split()
    i = 0
    while i < len(jetons):
        j = jetons[i]
        majuscule = j == j.upper() and re.search(r"[A-ZÀ-Ý]", j) is not None
        if majuscule or (j.lower() in PARTICULES and i + 1 < len(jetons) and i == 0 and
                         jetons[i + 1] == jetons[i + 1].upper() and re.search(r"[A-ZÀ-Ý]", jetons[i + 1])):
            i += 1
        else:
            break
    if i:
        out["nom_famille"] = " ".join(jetons[:i])
        if jetons[i:]:
            out["prenom"] = " ".join(jetons[i:])
    return out


def lire_date_etat(texte: str, stats: Dict[str, Any], contexte: str) -> Dict[str, Any]:
    """`09-10-1992` / `09-06-1980 à (61) Alençon` / `1813 ?` (texte SANS la marque ° / †) -> {date, precision, lieu, incertaine}.
    Jour complet : valide seulement si la date existe et l'année est entre 1700 et l'année en cours ; coquille ou format inconnu :
    {} (compté dans `dates_invalides`, le texte brut est gardé par l'appelant)."""
    t = (texte or "").strip()
    annee_max = datetime.date.today().year
    m = RE_DATE_COMPLETE.match(t)
    if m:
        j, mo, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            if not ANNEE_MIN <= a <= annee_max:
                raise ValueError("siècle")
            d = datetime.date(a, mo, j)
        except ValueError:
            stats["dates_invalides"].append("%s : %s" % (contexte, t))
            return {}
        out = {"date": d.isoformat(), "precision": "jour"}
        if m.group(4):
            out["lieu"] = m.group(4).strip()
        return out
    m = RE_ANNEE_SEULE.match(t)
    if m and ANNEE_MIN <= int(m.group(1)) <= annee_max:
        out = {"date": m.group(1), "precision": "annee"}
        if m.group(2):
            out["incertaine"] = True
        if m.group(3):
            out["lieu"] = m.group(3).strip()
        return out
    stats["dates_invalides"].append("%s : %s" % (contexte, t))
    return {}


def lire_pays(brut: str, stats: Dict[str, Any]) -> Dict[str, Any]:
    """Mot(s) du site -> `pays_site` (brut), `nat` (code canonique si le mot est dans la table `sources.clics`), `pays_double`."""
    out: Dict[str, Any] = {"pays_site": brut}
    if "/" in brut:                                   # double nationalité (`KENYA/G-B`, `AFN/FRANCE`) : laissée brute
        out["pays_double"] = True
        stats["pays_doubles"] += 1
        return out
    iso = pays_normalise(brut, "clics") or pays_normalise(brut.upper(), "clics")
    if iso:
        out["nat"] = iso
    else:
        stats["codes_pays_inconnus"][brut] = stats["codes_pays_inconnus"].get(brut, 0) + 1
    return out


def lire_equipe(brut: str) -> Dict[str, Any]:
    """`COFIDIS-LOOK-VITTORIA/VC ETAMPES (91)` / `GO PASS ABX/Elite 2/08 STAGIAIRE FDJ.COM` / `/Piacenza` / `UC PARIS (75)Amateur`
    -> equipe_brut + découpage par « / » (aucun rapprochement). Un 1er segment qui est une catégorie (`Junior Nationale`) est la
    catégorie, pas une équipe."""
    out: Dict[str, Any] = {}
    if not brut:
        return out
    out["equipe_brut"] = brut
    coupe = re.sub(r"(\((?:\d{2,3}|2[AB])\))(?=[A-Za-zÀ-ÿ])", r"\1/", brut)      # `(75)Amateur` : segments collés dans le tableau
    segments = [s.strip() for s in coupe.split("/")]
    for i, s in enumerate(segments):
        if not s:
            continue
        mst = RE_STAGIAIRE.match(s)
        if mst:
            if mst.group(1):
                out["stagiaire_depuis"] = mst.group(1)
            if mst.group(2).strip():
                out["stagiaire_equipe"] = mst.group(2).strip()
            out.setdefault("stagiaire", True)
        elif RE_CATEGORIE.match(s) and not RE_DEPARTEMENT.search(s):
            out.setdefault("categorie", s)
        elif i == 0:
            out["principal"] = s
        else:
            out.setdefault("club", s)
        dep = RE_DEPARTEMENT.search(s)
        if dep and "departement" not in out and not mst:
            out["departement"] = dep.group(1)
    return out


def lire_resultat(annee: Optional[int], date_txt: str, texte: str) -> Dict[str, Any]:
    """Résultat en texte libre : `texte` brut ; `rang` (`1er`, `56è`, `3°`), `ex_aequo`, `etape` lus seulement s'ils sont écrits."""
    r: Dict[str, Any] = {"date_txt": date_txt, "texte": texte}
    if annee is not None:
        r["annee"] = annee
    m = RE_RANG.match(texte)
    if m:
        r["rang"] = int(m.group(1))
    if re.search(r"ex[\s-]?aequo", texte, re.I):
        r["ex_aequo"] = True
    me = RE_ETAPE.search(texte)
    if me:
        r["etape"] = int(me.group(1))
    return r


def _stats_vides() -> Dict[str, Any]:
    return {"coureurs": 0, "lignes": 0, "lignes_orphelines": 0, "dates_invalides": [], "codes_pays_inconnus": {}, "pays_doubles": 0,
            "colonnes_inconnues": 0, "credits": 0}


def lire_page(page: str, stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Page de coureurs -> {libelle, coureurs: [...]} (dans l'ordre de la page ; `rang` = position 1-based dans la page).
    Page sans tableau : coureurs vide (structure inconnue, l'appelant la signale)."""
    st = stats if stats is not None else _stats_vides()
    libelle = None
    for balise in ("h1", "title"):                      # le libellé « PREMIER - DERNIER » ; titre de l'onglet si le h1 est vide
        m = re.search(r"<%s[^>]*>(.*?)</%s>" % (balise, balise), page, flags=re.S | re.I)
        if m and _txt(m.group(1)):
            libelle = _txt(m.group(1))
            break
    coureurs: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    annee: Optional[int] = None
    credit: List[str] = []

    def clore() -> None:
        if cur is not None and credit:
            cur["credit"] = " ".join(credit)
            st["credits"] += 1

    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S | re.I):
        cells = [_txt(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S | re.I)]
        if not any(cells):
            continue
        if len(cells) != 4:
            st["colonnes_inconnues"] += 1
            cells = (cells + ["", "", "", ""])[:4]
        c1, c2, c3, c4 = cells
        st["lignes"] += 1
        entete = bool(c1) and not est_temporel(c3)          # c1 + date / année en c3 = ligne de crédit (donnée), pas un coureur
        if entete:
            clore()
            credit = []
            annee = None
            cur = {"rang": len(coureurs) + 1}
            cur.update(lire_nom(c1))
            if c2:
                cur.update(lire_pays(c2, st))
            if c3:
                cur["code_site"] = c3
            cur["annees"] = []
            cur["resultats"] = []
            coureurs.append(cur)
            st["coureurs"] += 1
        else:
            if cur is None:
                st["lignes_orphelines"] += 1
                continue
            if c1:
                credit.append(c1)
            if c2 and c2 != cur.get("nom_affiche"):
                v = cur.setdefault("variantes", [])
                if c2 not in v:
                    v.append(c2)
        # col. 4 d'une ligne d'état civil (naissance sur la ligne du coureur, décès sur la suivante)
        if c4 and c4[0] in "°º†" and not (not entete and c3):
            cle = "naissance" if c4[0] in "°º" else "deces"
            d = lire_date_etat(c4[1:].strip(), st, "%s %s" % (cur.get("nom_affiche"), c4))
            if d:
                cur[cle] = d["date"]
                cur[cle + "_precision"] = d["precision"]
                if d.get("lieu"):
                    cur[cle + "_lieu"] = d["lieu"]
                if d.get("incertaine"):
                    cur[cle + "_incertaine"] = True
            else:
                cur[cle + "_brut"] = c4                         # coquille : pas de date, texte brut gardé (le brut d'une date valide est redondant)
                cur[cle + "_precision"] = None
            continue
        if entete:
            if c4:
                cur["col4_brut"] = c4                          # texte inattendu sur la ligne du coureur : gardé
            continue
        if not c3:
            if c4:
                cur.setdefault("notes", []).append(c4)         # col. 4 sans année ni date : gardé tel quel
            continue
        if RE_ANNEE.match(c3):
            annee = int(c3)
            e = {"annee": annee}
            e.update(lire_equipe(c4))
            cur["annees"].append(e)
        elif RE_JJMM.match(c3):
            if c4:
                cur["resultats"].append(lire_resultat(annee, c3, c4))
    clore()
    return {"libelle": libelle, "coureurs": coureurs}


# --------------------------------------------------------------------------------------------------
# Ordre de lecture (sans réseau)
# --------------------------------------------------------------------------------------------------

def _slug(rel: str) -> str:
    return os.path.splitext(os.path.basename(rel))[0].strip("-")


SLUGS_SANS_SENS = {"fake"}         # slug de remplissage d'e-monsite (`pages/m/fake.html` : plage réelle, nom inconnu) : aucune information d'ordre


def noms_connus(archives: Optional[str]) -> List[str]:
    """Clés « famille prénom » normalisées (triées) des coureurs déjà connus : `entites/coureurs/*.json` (clé = slug du rider_id,
    sans la date) et `sources/cqranking/coureurs.json` (`nom_famille` + `prenom`). Vide si les dossiers sont absents."""
    cles: List[str] = []
    if not archives:
        return cles
    dossier = os.path.join(archives, "entites", "coureurs")
    if os.path.isdir(dossier):
        for f in sorted(os.listdir(dossier)):
            if not f.endswith(".json") or f == "index.json":        # index.json = annuaire (liste), pas un fichier de coureurs
                continue
            try:
                with open(os.path.join(dossier, f), encoding="utf-8") as fh:
                    d = json.load(fh)
            except (OSError, ValueError):
                continue
            for rid in (d if isinstance(d, dict) else ()):
                cles.append(re.sub(r"-\d{8}$", "", rid).replace("-", " "))
    chemin = os.path.join(archives, "sources", "cqranking", "coureurs.json")
    if os.path.exists(chemin):
        try:
            with open(chemin, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            d = {}
        for v in d.values():
            cles.append(netutil.normalize("%s %s" % (v.get("nom_famille") or "", v.get("prenom") or "")))
    return sorted(c for c in cles if c)


def ordre_lecture(rels: List[str], connus: List[str]) -> List[str]:
    """(1) pages d'un ou deux jetons de slug (coureurs notables), (2) pages dont la plage (de son 1er mot de slug au 1er mot de la
    page suivante du même dossier) contient le plus de coureurs connus, (3) le reste ; ex aequo : ordre des chemins. Heuristique
    d'ordre seulement : n'écrit rien dans les données."""
    par_dossier: Dict[str, List[str]] = {}
    for rel in rels:
        par_dossier.setdefault(rel.split("/")[1], []).append(rel)
    poids: Dict[str, int] = {}
    for dossier, rs in par_dossier.items():
        rs = [r for r in rs if _slug(r) not in SLUGS_SANS_SENS]
        rs.sort(key=lambda r: _slug(r))
        bornes = [_slug(r).split("-")[0] for r in rs]
        fin = dossier[-1] + "\uffff"                       # fin de la dernière plage = fin de la lettre du dossier (`g`, `q-r` -> `r`)
        for i, r in enumerate(rs):
            haut = bornes[i + 1] if i + 1 < len(rs) else fin
            poids[r] = bisect.bisect_left(connus, haut) - bisect.bisect_left(connus, bornes[i]) if haut > bornes[i] else 0

    def cle(rel: str) -> Tuple[int, int, str]:
        notable = len(_slug(rel).split("-")) <= 2 and _slug(rel) not in SLUGS_SANS_SENS
        return (0 if notable else 1 if poids.get(rel, 0) > 0 else 2, -poids.get(rel, 0), rel)
    return sorted(rels, key=cle)


# --------------------------------------------------------------------------------------------------
# Réseau, stockage, reprise
# --------------------------------------------------------------------------------------------------

class Session:
    """Requêtes polies (pause par hôte, budget, compteur, échecs de suite)."""

    def __init__(self, sortie: str, budget_min: float = 0.0, max_pages: int = 0, garder_html: bool = False):
        self.sortie = sortie
        self.garder_html = garder_html
        self.t0 = time.monotonic()
        self.budget_s = budget_min * 60 if budget_min else 0.0
        self.max_pages = max_pages
        self.requetes = 0
        self.echecs = 0
        self.echecs_de_suite = 0
        self.absente = False        # dernière page demandée : 404 / 410 (vrai échec) ; faux = lue, ou panne passagère
        self.dernier_journal = self.t0

    def epuise(self) -> bool:
        if self.budget_s and time.monotonic() - self.t0 >= self.budget_s:
            return True
        if self.max_pages and self.requetes >= self.max_pages:
            return True
        return self.echecs_de_suite >= ECHECS_DE_SUITE_MAX

    def hote_bloque(self) -> bool:
        return HOTE in netutil._blocked_hosts

    def page(self, rel: str, garder: bool = False) -> Optional[str]:
        url = rel if rel.startswith("http") else BASE + rel
        self.absente = False
        if self.epuise() or self.hote_bloque():
            return None
        self.requetes += 1
        texte = netutil.fetch_text(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xml,text/plain"},
                                   timeout=DELAI_LECTURE_S)
        if texte is None:
            self.echecs += 1
            self.echecs_de_suite += 1
            self.absente = netutil.page_absente()
            return None
        self.echecs_de_suite = 0
        if garder:
            chemin = os.path.join(self.sortie, "cache", hashlib.sha1(url.encode()).hexdigest()[:16] + ".html.gz")
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            with gzip.open(chemin, "wt", encoding="utf-8") as f:
                f.write(texte)
        return texte

    def journal(self, message: str, force: bool = False) -> None:
        if force or time.monotonic() - self.dernier_journal >= 300:
            self.dernier_journal = time.monotonic()
            print("[CLICS] %s (%d requêtes, %.1f min)" % (message, self.requetes, (time.monotonic() - self.t0) / 60))


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


def chemin_plage(sortie: str, rel: str) -> str:
    """`pages/g/gabbai-tal-gabica-francesco.html` -> `<sortie>/plages/g/gabbai-tal-gabica-francesco.json`."""
    parts = rel.split("/")
    return os.path.join(sortie, "plages", parts[1], os.path.splitext(parts[2])[0] + ".json")


def _a_lire(e: Dict[str, Any], relire: bool) -> bool:
    """Jamais lue, ou `lastmod` du sitemap différent de celui de la dernière lecture (ou `--relire`)."""
    if "lu_le" not in e:
        return True
    return relire or e.get("lastmod") != e.get("lastmod_lu")


def archives_depuis_sortie(sortie: str) -> str:
    """`<archives>/sources/clics` -> `<archives>` ; sinon ARCHIVES_DIR."""
    s = os.path.abspath(sortie)
    if os.path.basename(os.path.dirname(s)) == "sources":
        return os.path.dirname(os.path.dirname(s))
    return ARCHIVES_DIR


def lancer(sortie: str, archives: Optional[str] = None, budget_min: float = 0.0, max_pages: int = 0,
           cibles: Optional[List[str]] = None, relire: bool = False, decouverte_seule: bool = False,
           sans_decouverte: bool = False, garder_html: bool = False, connus: Optional[List[str]] = None) -> Dict[str, Any]:
    """Découverte (robots.txt -> sitemap), puis lecture des pages à lire dans l'ordre de l'étude. Reprenable ; écrit `etat.json`."""
    sess = Session(sortie, budget_min, max_pages, garder_html)
    cibles = [c.strip().lower() for c in (cibles or []) if c.strip()]
    chemin_pages = os.path.join(sortie, "pages.json")
    pages: Dict[str, Dict[str, Any]] = _lire_json(chemin_pages, {})
    chemin_manques = os.path.join(sortie, "introuvables.json")
    manques: Dict[str, Dict[str, Any]] = _lire_json(chemin_manques, {})
    resume: Dict[str, Any] = {"pages_sitemap": 0, "pages_lues": 0, "pages_deja": 0, "coureurs": 0, "echecs": 0,
                              "pages_refusees_robots": 0, "structure_inconnue": 0, "dates_invalides": [], "codes_pays_inconnus": {},
                              "pays_doubles": 0, "lignes_orphelines": 0, "credits": 0}
    decouverte_ok = True
    robots = Robots("")

    # --- robots.txt (toujours lu : aucune page n'est demandée sans lui), puis sitemap déclaré (aucune URL devinée)
    robots_ok = False
    txt = sess.page("robots.txt")
    if txt is None:
        decouverte_ok = False
        if sess.absente:
            print("[CLICS] [WARN] robots.txt absent : pas de sitemap déclaré, découverte impossible")
        else:
            print("[CLICS] [WARN] robots.txt illisible : rien n'est lu pour ce passage")
    else:
        robots_ok = True
        robots = Robots(txt)
        if robots.delai and robots.delai > PAUSE_S:
            netutil.HOST_DELAYS[HOTE] = robots.delai
        if not sans_decouverte:
            vus: Dict[str, Optional[str]] = {}
            a_suivre = [u for u in robots.sitemaps if urllib.parse.urlparse(u).netloc == HOTE]
            if not a_suivre:
                decouverte_ok = False
                print("[CLICS] [WARN] aucun sitemap de notre hôte déclaré dans robots.txt : découverte impossible")
            deja_sm = set()
            while a_suivre and decouverte_ok:
                u = a_suivre.pop(0)
                if u in deja_sm or len(deja_sm) >= 20:
                    continue
                deja_sm.add(u)
                xml = sess.page(u)
                if xml is None:
                    decouverte_ok = False
                    break
                trouvees, sous = lire_sitemap(xml)
                vus.update(trouvees)
                a_suivre.extend(s for s in sous if urllib.parse.urlparse(s).netloc == HOTE)
            if decouverte_ok:
                if not vus:
                    decouverte_ok = False
                    print("[CLICS] [WARN] sitemap sans page de coureurs : découverte impossible")
                else:
                    for rel, lm in vus.items():
                        e = pages.setdefault(rel, {})
                        e.pop("hors_sitemap", None)
                        if lm:
                            e["lastmod"] = lm
                        else:
                            e.pop("lastmod", None)
                    for rel, e in pages.items():
                        if rel not in vus:
                            e["hors_sitemap"] = True
                    _ecrire_json(chemin_pages, pages)
    resume["pages_sitemap"] = sum(1 for e in pages.values() if not e.get("hors_sitemap"))

    def interdite(rel: str) -> bool:
        return not robots.autorise("/" + rel)

    def retenue(rel: str) -> bool:
        return not cibles or any(t in rel.lower() for t in cibles)

    # --- lecture
    if not decouverte_seule and robots_ok:
        stats = _stats_vides()
        a_faire = [r for r, e in pages.items() if not e.get("hors_sitemap") and retenue(r) and _a_lire(e, relire)]
        if connus is None:
            connus = noms_connus(archives if archives is not None else archives_depuis_sortie(sortie))
        for rel in ordre_lecture(a_faire, connus):
            e = pages[rel]
            if interdite(rel):
                resume["pages_refusees_robots"] += 1
                continue
            if _essais(manques, rel) >= ECHECS_MAX and "lu_le" not in e:
                continue
            if sess.epuise() or sess.hote_bloque():
                break
            page = sess.page(rel, garder_html)
            if page is None:
                if sess.absente and _noter_manque(manques, rel):     # panne passagère : rien n'est noté
                    _ecrire_json(chemin_manques, manques)
                continue
            lu = lire_page(page, stats)
            if not lu["coureurs"]:
                resume["structure_inconnue"] += 1
                if _noter_manque(manques, rel, "structure inconnue"):
                    _ecrire_json(chemin_manques, manques)
                continue
            contenu = {"source": SOURCE, "source_url": BASE + rel, "libelle": lu["libelle"], "lu_le": _maintenant(),
                       "nb_coureurs": len(lu["coureurs"]), "coureurs": lu["coureurs"]}
            if e.get("lastmod"):
                contenu["lastmod"] = e["lastmod"]
            _ecrire_json(chemin_plage(sortie, rel), contenu, compact=True)
            empreinte = hashlib.sha1(json.dumps(lu["coureurs"], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
            e.update({"libelle": lu["libelle"], "lu_le": contenu["lu_le"], "nb_coureurs": len(lu["coureurs"]), "empreinte": empreinte})
            if e.get("lastmod"):
                e["lastmod_lu"] = e["lastmod"]
            else:
                e.pop("lastmod_lu", None)
            if rel in manques:
                del manques[rel]
                _ecrire_json(chemin_manques, manques)
            _ecrire_json(chemin_pages, pages)
            resume["pages_lues"] += 1
            sess.journal("lecture : %d pages lues" % resume["pages_lues"])
        resume["pages_deja"] = sum(1 for r, e in pages.items() if not e.get("hors_sitemap") and "lu_le" in e and not _a_lire(e, relire))
        for k in ("coureurs", "lignes_orphelines", "credits", "pays_doubles"):
            resume[k] = stats[k]
        resume["dates_invalides"] = stats["dates_invalides"][:20]
        resume["codes_pays_inconnus"] = stats["codes_pays_inconnus"]

    # --- reste à faire (après la lecture : état réel)
    restantes = a_relire = 0
    for rel, e in pages.items():
        if e.get("hors_sitemap") or not retenue(rel) or interdite(rel):
            continue
        if _essais(manques, rel) >= ECHECS_MAX and "lu_le" not in e:
            continue
        if "lu_le" not in e:
            restantes += 1
        elif _a_lire(e, False):
            restantes += 1
            a_relire += 1
    resume["echecs"] = sess.echecs
    resume["requetes"] = sess.requetes
    resume["duree_min"] = round((time.monotonic() - sess.t0) / 60, 1)
    resume["budget_epuise"] = sess.epuise()
    resume["hote_bloque"] = sess.hote_bloque()
    termine = bool(decouverte_ok and not restantes and not decouverte_seule and not sess.hote_bloque())
    _ecrire_json(os.path.join(sortie, "etat.json"), {"termine": termine, "pages_restantes": restantes, "pages_a_relire": a_relire})
    resume["pages_restantes"], resume["pages_a_relire"], resume["termine"] = restantes, a_relire, termine
    sess.journal("synthèse : %s" % json.dumps(resume, ensure_ascii=False, sort_keys=True), force=True)
    return resume


# --------------------------------------------------------------------------------------------------
# Tests sans réseau (pages réelles allégées dans tools/fixtures/clics/)
# --------------------------------------------------------------------------------------------------

def _fixture(nom: str) -> str:
    with open(os.path.join(FIXTURES, nom), encoding="utf-8") as f:
        return f.read()


def _tests() -> None:
    import tempfile
    # robots.txt réel : `*` autorisé, sitemap déclaré, exclusions d'autres robots sans effet sur nous
    r = Robots(_fixture("robots.txt"))
    assert r.sitemaps == ["https://www.clicssurlecyclisme.net/sitemap.xml"] and r.autorise("/pages/g/gallopin-tony.html") and r.delai is None
    r = Robots("User-agent: *\nDisallow: /pages/g/\nAllow: /pages/g/gallopin-tony.html\nDisallow: /*.pdf$\nCrawl-delay: 7\n"
               "User-agent: courses-cyclistes\nDisallow: /prive/\n")
    assert not r.autorise("/prive/x.html") and r.autorise("/pages/g/x.html") and r.delai is None      # groupe nommé : seul lui s'applique
    r = Robots("User-agent: *\nDisallow: /pages/g/\nAllow: /pages/g/gallopin-tony.html\nDisallow: /*.pdf$\nCrawl-delay: 7\n")
    assert not r.autorise("/pages/g/x.html") and r.autorise("/pages/g/gallopin-tony.html") and not r.autorise("/a/b.pdf")
    assert r.autorise("/a/b.pdfx") and r.delai == 7.0 and Robots("").autorise("/n'importe") and Robots("User-agent: *\nDisallow: /").autorise("/") is False

    # sitemap réel (extrait) : seules les pages de coureurs, avec lastmod ; dossiers / rubriques / autres hôtes ignorés
    pages, sous = lire_sitemap(_fixture("sitemap_extrait.xml"))
    assert pages and all(RE_PAGE.match(p) for p in pages) and not sous, pages
    assert pages["pages/g/gallon-gallopin-andre.html"] == "2026-04-06T23:42:35+02:00"
    assert "pages/a/" not in pages and "contact/contacter-clics.html" not in pages
    p2, s2 = lire_sitemap("<sitemapindex><sitemap><loc>https://www.clicssurlecyclisme.net/sitemap-2.xml</loc></sitemap></sitemapindex>")
    assert not p2 and s2 == ["https://www.clicssurlecyclisme.net/sitemap-2.xml"]
    p3, _ = lire_sitemap("<url><loc>https://www.clicssurlecyclisme.net/pages/a/x-y.html</loc></url><url><loc>https://autre.net/pages/a/z.html</loc></url>")
    assert list(p3) == ["pages/a/x-y.html"] and p3["pages/a/x-y.html"] is None

    # noms
    assert lire_nom("GABELLI Giovan-Battista") == {"nom_affiche": "GABELLI Giovan-Battista", "nom_famille": "GABELLI", "prenom": "Giovan-Battista"}
    assert lire_nom("GABBAI Tal")["prenom"] == "Tal" and "prenom" not in lire_nom("GERARDIN") and lire_nom("GERARDIN")["nom_famille"] == "GERARDIN"
    n = lire_nom("GABICAGOGEASCOA IBARRA Francisco")
    assert n["nom_famille"] == "GABICAGOGEASCOA IBARRA" and n["prenom"] == "Francisco"
    n = lire_nom("DE LA FUENTE Pedro dit PEDRITO")
    assert n["nom_famille"] == "DE LA FUENTE" and n["prenom"] == "Pedro" and n["surnom"] == "PEDRITO", n
    n = lire_nom("de GRIBALDY Jean")
    assert n["nom_famille"] == "de GRIBALDY" and n["prenom"] == "Jean", n

    # dates : coquilles = pas de date, comptées ; année seule ; lieu brut
    st = _stats_vides()
    assert lire_date_etat("09-10-1992", st, "x") == {"date": "1992-10-09", "precision": "jour"}
    assert lire_date_etat("11-09-1930 à (49) La Prévière ?", st, "x") == {"date": "1930-09-11", "precision": "jour", "lieu": "(49) La Prévière ?"}
    assert lire_date_etat("1813 ?", st, "x") == {"date": "1813", "precision": "annee", "incertaine": True}
    assert not st["dates_invalides"]
    assert lire_date_etat("20-10-1190", st, "a") == {} and lire_date_etat("20-021891", st, "b") == {} and lire_date_etat("31-02-1950", st, "c") == {}
    assert lire_date_etat("01-01-2999", st, "d") == {} and len(st["dates_invalides"]) == 4, st["dates_invalides"]

    # équipes : découpage par « / », sans rapprochement
    assert lire_equipe("") == {}
    assert lire_equipe("COFIDIS-LOOK-VITTORIA/VC ETAMPES (91)") == {
        "equipe_brut": "COFIDIS-LOOK-VITTORIA/VC ETAMPES (91)", "principal": "COFIDIS-LOOK-VITTORIA", "club": "VC ETAMPES (91)", "departement": "91"}
    e = lire_equipe("GO PASS ABX/Elite 2/08 STAGIAIRE FDJ.COM")
    assert e["principal"] == "GO PASS ABX" and e["categorie"] == "Elite 2" and e["stagiaire_depuis"] == "08" and e["stagiaire_equipe"] == "FDJ.COM", e
    e = lire_equipe("/08 STAGIAIRE FLAMINIA-FONDRIEST")
    assert "principal" not in e and e["stagiaire_depuis"] == "08" and e["stagiaire_equipe"] == "FLAMINIA-FONDRIEST", e
    assert lire_equipe("/Piacenza") == {"equipe_brut": "/Piacenza", "club": "Piacenza"}
    e = lire_equipe("UC PARIS (75)Amateur")
    assert e["principal"] == "UC PARIS (75)" and e["departement"] == "75" and e["categorie"] == "Amateur", e
    assert lire_equipe("Junior Nationale") == {"equipe_brut": "Junior Nationale", "categorie": "Junior Nationale"}
    e = lire_equipe("VENDEE U (85)/Elite 2/STAGIAIRE BONJOUR")
    assert e["principal"] == "VENDEE U (85)" and e["departement"] == "85" and e["stagiaire_equipe"] == "BONJOUR" and "stagiaire_depuis" not in e, e

    # résultats : rang / étape / ex aequo seulement quand ils sont écrits
    assert lire_resultat(2014, "01-06", "56è du Tour de Berlin espoirs (All)") == {
        "annee": 2014, "date_txt": "01-06", "texte": "56è du Tour de Berlin espoirs (All)", "rang": 56}
    r = lire_resultat(1999, "00-00", "1er de la 4è étape du Tour d'Istambul (Turq)")
    assert r["rang"] == 1 and r["etape"] == 4
    r = lire_resultat(1999, "30-01/03-02", "abandon 13è étape du Tour de France")
    assert "rang" not in r and r["etape"] == 13
    assert "rang" not in lire_resultat(1993, "00-00", "4 victoires en 1993 (North)") and "rang" not in lire_resultat(1993, "00-00", "Leader du Tour du Qatar")
    assert lire_resultat(1950, "16-04", "1° GP de Congrier (53)")["rang"] == 1 and lire_resultat(1950, "23-04", "2° GP")["rang"] == 2
    assert lire_resultat(1950, "23-04", "3è ex aequo du GP")["ex_aequo"] is True

    # pays : table explicite, pays doubles laissés bruts, inconnus comptés
    st = _stats_vides()
    assert lire_pays("FRANCE", st) == {"pays_site": "FRANCE", "nat": "FRA"} and lire_pays("ISRAËL", st)["nat"] == "ISR"
    assert lire_pays("G-B", st)["nat"] == "GBR" and lire_pays("PAYS-BAS", st)["nat"] == "NED"
    assert lire_pays("KENYA/G-B", st) == {"pays_site": "KENYA/G-B", "pays_double": True} and lire_pays("AFN/FRANCE", st)["pays_double"]
    assert lire_pays("ATLANTIDE", st) == {"pays_site": "ATLANTIDE"} and st["codes_pays_inconnus"] == {"ATLANTIDE": 1} and st["pays_doubles"] == 2

    # page de plage (Gabbai : 27 coureurs, code libre, décès, variantes) --------------------------------------
    st = _stats_vides()
    p = lire_page(_fixture("plage_gabbai.html"), st)
    cs = p["coureurs"]
    assert p["libelle"] == "GABBAI Tal - GABICA Francesco" and len(cs) == 27 and st["coureurs"] == 27 and [c["rang"] for c in cs] == list(range(1, 28))
    tal = cs[0]
    assert tal["nom_famille"] == "GABBAI" and tal["prenom"] == "Tal" and tal["nat"] == "ISR" and tal["naissance"] == "1992-10-09" and tal["naissance_precision"] == "jour"
    assert [a["annee"] for a in tal["annees"]] == list(range(2009, 2016)) and all("equipe_brut" not in a for a in tal["annees"])
    assert {"annee": 2014, "date_txt": "01-06", "texte": "56è du Tour de Berlin espoirs (All)", "rang": 56} in tal["resultats"]
    assert cs[1]["annees"] == [{"annee": 2002, "equipe_brut": "Junior", "categorie": "Junior"}]
    mario = cs[2]
    assert "naissance" not in mario and "naissance_precision" not in mario and "pays_site" in mario        # pas de date : rien d'inventé
    assert mario["annees"][0] == {"annee": 1909, "equipe_brut": "/Piacenza", "club": "Piacenza"} and mario["resultats"][0]["rang"] == 189
    gabelli = next(c for c in cs if c["nom_famille"] == "GABELLI")
    assert gabelli["code_site"] == "CDP 149" and gabelli["naissance"] == "1933-04-05" and gabelli["naissance_lieu"] == "Castellazzo Bormida"
    assert next(c for c in cs if c.get("prenom") == "Raymond")["naissance_lieu"] == "(92) Colombes"
    assert next(c for c in cs if c["nom_affiche"] == "GABBURO Davide")["naissance_lieu"] == "Turin ou Bovolone"
    assert [c for c in cs if c["nom_affiche"] == "GABET"].__len__() == 2 and not st["dates_invalides"] and st["lignes_orphelines"] == 0
    assert all("nat" in c for c in cs) and not st["codes_pays_inconnus"], st["codes_pays_inconnus"]
    gab = next(c for c in cs if c["nom_famille"] == "GABELLA")
    assert gab["nat"] == "SUI" and gab["annees"] == [{"annee": 1905}] and "equipe_brut" not in gab["annees"][0]      # année sans équipe : pas d'équipe

    # coureurs sans prénom, homonymes de la même page (jamais fusionnés), variante de nom
    cs = lire_page(_fixture("plage_gerardin.html"), _stats_vides())["coureurs"]
    assert [c["nom_affiche"] for c in cs[:3]] == ["GERARDIN", "GERARDIN", "GERARDIN Alain"] and [c["rang"] for c in cs[:3]] == [1, 2, 3]
    assert "prenom" not in cs[0] and cs[2]["variantes"] == ["Gerardin"] and cs[2]["prenom"] == "Alain"
    assert cs[3]["naissance"] == "1947-07-08" and cs[3]["naissance_lieu"] == "(08) Aiglemont" and cs[0]["annees"][0]["annee"] == 1901
    assert cs[0]["annees"][0]["principal"] == "UC PARIS (75)" and cs[0]["annees"][0]["categorie"] == "Amateur"
    cs = lire_page(_fixture("plage_geslin_homonymes.html"), _stats_vides())["coureurs"]
    assert [c["nom_affiche"] for c in cs] == ["GESLIN", "GESLIN André", "GESLIN Anthony"] and cs[2]["naissance"] == "1980-06-09"
    geslins = cs[2:]
    ligne = '<tr><td>%s</td><td>FRANCE</td><td></td><td>%s</td></tr><tr><td></td><td></td><td>2001</td><td>X</td></tr>'
    deux = lire_page("<h1>X</h1><table>" + ligne % ("GESLIN Anthony", "&deg;09-06-1980 &agrave; Alen&ccedil;on") + ligne % ("GESLIN Anthony", "&deg;02-03-1983") +
                     ligne % ("GESLIN Anthony", "") + "</table>")["coureurs"]
    assert [c["rang"] for c in deux] == [1, 2, 3] and [c.get("naissance") for c in deux] == ["1980-06-09", "1983-03-02", None]   # jamais fusionnés
    a = geslins[0]["annees"][3]
    assert a["annee"] == 2000 and a["principal"] == "VENDEE U-PAYS DE LA LOIRE" and a["categorie"] == "Nationale" and a["stagiaire_depuis"] == "09"

    # ligne de crédit « Palmarès établi par » : donnée de la fiche, pas deux faux coureurs
    st = _stats_vides()
    p = lire_page(_fixture("plage_gault_credit.html"), st)
    noms = [c["nom_affiche"] for c in p["coureurs"]]
    assert "Palmarès établi par" not in noms and "Claude Chatelier" not in noms and st["credits"] >= 1, noms
    c = next(c for c in p["coureurs"] if c.get("credit"))
    assert c["credit"] == "Palmarès établi par Claude Chatelier"
    assert any(r["texte"] == "3° Prix de Chailland (53)" and r["rang"] == 3 for r in c["resultats"])
    assert {"annee": 1951, "equipe_brut": "PEDALE ANGEVINE (49)", "principal": "PEDALE ANGEVINE (49)", "departement": "49"} in c["annees"]
    assert next(c for c in p["coureurs"] if c["nom_affiche"] == "GAULTIER Maurice")["deces"] == "2022-09-20"
    assert st["lignes_orphelines"] > 0 or p["coureurs"][0]["rang"] == 1       # lignes avant le 1er coureur : comptées, jamais rattachées

    # coureur notable seul : décès, lieux, catégories
    p = lire_page(_fixture("coureur_fignon_laurent.html"), _stats_vides())
    f = p["coureurs"][0]
    assert p["libelle"] == "FIGNON Laurent" and len(p["coureurs"]) == 1 and f["naissance"] == "1960-08-12" and f["naissance_lieu"] == "(75) Paris 18è"
    assert f["deces"] == "2010-08-31" and f["deces_lieu"] == "(75) Paris Pitié-Salpétrière 13è" and f["deces_precision"] == "jour"
    assert f["annees"][0] == {"annee": 1976, "equipe_brut": "PEDALE COMBS-LA-VILLAISE (77)/Cadet", "principal": "PEDALE COMBS-LA-VILLAISE (77)",
                              "categorie": "Cadet", "departement": "77"}
    assert f["resultats"][0]["annee"] == 1976 and f["resultats"][0]["rang"] == 1 and f["resultats"][1]["rang"] == 5
    g = lire_page(_fixture("coureur_gallopin_tony.html"), _stats_vides())["coureurs"][0]
    assert g["annees"][0] == {"annee": 2003, "equipe_brut": "VC ETAMPES (91)/Cadet", "principal": "VC ETAMPES (91)", "categorie": "Cadet", "departement": "91"}
    assert any(a.get("categorie") == "Junior Régionale" for a in g["annees"])
    assert lire_page("<html><body>Page d'erreur</body></html>")["coureurs"] == []                            # structure inconnue
    assert lire_page("<title>X - Y</title><h1> </h1>")["libelle"] == "X - Y"

    # coquilles de dates dans une page
    page = ("<h1>A - B</h1><table>" + "".join('<tr><td>%s</td><td>FRANCE</td><td></td><td>%s</td></tr>' % x for x in (
        ("AAA Un", "&deg;20-10-1190"), ("BBB Deux", "&deg;20-021891"), ("CCC Trois", "&deg;1813 ?"), ("DDD Quatre", "&deg;12-12-1960"))) + "</table>")
    st = _stats_vides()
    cs = lire_page(page, st)["coureurs"]
    assert "naissance" not in cs[0] and cs[0]["naissance_brut"] == "°20-10-1190" and "naissance_brut" not in cs[3] and cs[0]["naissance_precision"] is None
    assert "naissance" not in cs[1] and cs[2]["naissance"] == "1813" and cs[2]["naissance_precision"] == "annee" and cs[2]["naissance_incertaine"]
    assert cs[3]["naissance"] == "1960-12-12" and len(st["dates_invalides"]) == 2

    # ordre de lecture : notables d'abord, puis plus de coureurs connus, puis le reste
    rels = ["pages/g/gabbai-tal-gabica-francesco.html", "pages/g/gallon-gallopin-andre.html", "pages/g/gallopin-tony.html",
            "pages/g/gai-andro-gailhac.html", "pages/b/boocock-dan-bozzola-luc.html"]
    connus = sorted(["gallon andre", "gallon bruno", "gallon carl", "gabbai tal", "gabbai yann"])
    o = ordre_lecture(rels, connus)
    assert o[0] == "pages/g/gallopin-tony.html", o                 # 2 jetons : coureur notable
    assert o.index("pages/g/gallon-gallopin-andre.html") < o.index("pages/g/gabbai-tal-gabica-francesco.html") < o.index("pages/b/boocock-dan-bozzola-luc.html"), o
    assert ordre_lecture(rels, []) == ordre_lecture(list(reversed(rels)), [])
    o2 = ordre_lecture(rels + ["pages/g/fake.html"], connus)
    assert o2.index("pages/g/fake.html") > o2.index("pages/g/gabbai-tal-gabica-francesco.html") and o2[0] == o[0]     # slug de remplissage : ni notable ni borne
    assert noms_connus(None) == [] and noms_connus("/chemin/inexistant") == []

    # chemins de sortie
    assert chemin_plage("S", "pages/g/gallopin-tony.html") == os.path.join("S", "plages", "g", "gallopin-tony.json")
    assert archives_depuis_sortie("/x/data/archives/sources/clics") == "/x/data/archives"

    # reprise sans réseau réel : lastmod inchangé = aucune requête de page ; lastmod changé = relue ; pas de contournement du robots.txt
    sm = ("<urlset><url><loc>%spages/g/gallopin-tony.html</loc><lastmod>2026-04-06T10:00:00+02:00</lastmod></url>"
          "<url><loc>%spages/g/gabbai-tal-gabica-francesco.html</loc></url>"
          "<url><loc>%spages/z/interdit-page.html</loc></url></urlset>") % (BASE, BASE, BASE)
    robots_txt = "User-agent: *\nDisallow: /pages/z/\nSitemap: %ssitemap.xml\n" % BASE
    contenu = {BASE + "robots.txt": robots_txt, BASE + "sitemap.xml": sm,
               BASE + "pages/g/gallopin-tony.html": _fixture("coureur_gallopin_tony.html"),
               BASE + "pages/g/gabbai-tal-gabica-francesco.html": _fixture("plage_gabbai.html")}
    orig = netutil.fetch_text
    appels: List[str] = []
    statut_faux = [404]

    def faux(url: str, *a: Any, **k: Any) -> Optional[str]:
        appels.append(url)
        netutil.dernier_statut = 200 if url in contenu else statut_faux[0]
        return contenu.get(url)
    netutil.fetch_text = faux
    try:
        with tempfile.TemporaryDirectory() as d:
            r1 = lancer(d, connus=[])
            assert r1["pages_lues"] == 2 and r1["pages_refusees_robots"] == 1 and r1["pages_sitemap"] == 3, r1
            assert BASE + "pages/z/interdit-page.html" not in appels                          # robots.txt respecté
            assert [u for u in appels if "/pages/" in u][0].endswith("gallopin-tony.html")     # notable d'abord
            assert r1["pages_restantes"] == 0 and r1["termine"] is True and r1["coureurs"] == 28, r1
            assert _lire_json(os.path.join(d, "etat.json"), {}) == {"termine": True, "pages_restantes": 0, "pages_a_relire": 0}
            pg = _lire_json(os.path.join(d, "pages.json"), {})
            e = pg["pages/g/gallopin-tony.html"]
            assert e["lastmod"] == e["lastmod_lu"] == "2026-04-06T10:00:00+02:00" and e["libelle"] == "GALLOPIN Tony" and e["nb_coureurs"] == 1 and e["empreinte"]
            assert "lastmod" not in pg["pages/g/gabbai-tal-gabica-francesco.html"] and "lu_le" in pg["pages/g/gabbai-tal-gabica-francesco.html"]
            plage = _lire_json(chemin_plage(d, "pages/g/gabbai-tal-gabica-francesco.html"), {})
            assert plage["nb_coureurs"] == 27 and plage["source_url"].endswith("gabbai-tal-gabica-francesco.html") and plage["coureurs"][0]["naissance"] == "1992-10-09"
            assert not os.path.exists(os.path.join(d, "cache"))                                # aucun HTML conservé par défaut
            n = len([u for u in appels if "/pages/" in u])
            r2 = lancer(d, connus=[])                                                          # rien n'a changé : seules robots + sitemap
            assert len([u for u in appels if "/pages/" in u]) == n and r2["pages_lues"] == 0 and r2["pages_deja"] == 2 and r2["termine"] is True, r2
            contenu[BASE + "sitemap.xml"] = sm.replace("2026-04-06T10:00:00+02:00", "2026-11-19T10:00:00+01:00")
            r3 = lancer(d, connus=[], decouverte_seule=True)
            assert r3["pages_a_relire"] == 1 and r3["termine"] is False and r3["pages_lues"] == 0
            r3 = lancer(d, connus=[])
            assert r3["pages_lues"] == 1 and r3["pages_a_relire"] == 0 and r3["termine"] is True
            assert _lire_json(os.path.join(d, "pages.json"), {})["pages/g/gallopin-tony.html"]["lastmod_lu"] == "2026-11-19T10:00:00+01:00"
            n = len(appels)
            r4 = lancer(d, connus=[], relire=True, cibles=["gabbai"])
            assert r4["pages_lues"] == 1 and len(appels) == n + 3, (r4, len(appels) - n)       # robots + sitemap + 1 page
            # --max-requetes : bornes de budget (robots + sitemap comptent) et reprise
        with tempfile.TemporaryDirectory() as d:
            r = lancer(d, connus=[], max_pages=3)
            assert r["pages_lues"] == 1 and r["pages_restantes"] == 1 and r["termine"] is False, r
            r = lancer(d, connus=[])
            assert r["pages_lues"] == 1 and r["termine"] is True, r
        # sans sitemap déclaré : aucune URL devinée, aucune page demandée
        contenu[BASE + "robots.txt"] = "User-agent: *\nAllow: /\n"
        with tempfile.TemporaryDirectory() as d:
            n = len(appels)
            r = lancer(d, connus=[])
            assert len(appels) == n + 1 and r["termine"] is False and r["pages_lues"] == 0, r
        contenu[BASE + "robots.txt"] = robots_txt
        # échecs : 503 / réseau = rien de noté ; 404 = un essai par jour, abandon après ECHECS_MAX jours ; structure inconnue = noté
        del contenu[BASE + "pages/g/gallopin-tony.html"]
        del contenu[BASE + "pages/g/gabbai-tal-gabica-francesco.html"]
        with tempfile.TemporaryDirectory() as d:
            statut_faux[0] = 503
            r = lancer(d, connus=[])
            assert not _lire_json(os.path.join(d, "introuvables.json"), {}) and r["pages_lues"] == 0 and r["termine"] is False, r
            statut_faux[0] = 404
            contenu[BASE + "pages/g/gabbai-tal-gabica-francesco.html"] = "<html>pas de tableau</html>"
            r = lancer(d, connus=[])
            m = _lire_json(os.path.join(d, "introuvables.json"), {})
            assert set(m) == {"pages/g/gallopin-tony.html", "pages/g/gabbai-tal-gabica-francesco.html"} and r["structure_inconnue"] == 1, m
            assert all(v["essais"] == 1 and v["regle"] == REGLE_ECHECS for v in m.values()), m
            assert m["pages/g/gabbai-tal-gabica-francesco.html"]["motif"] == "structure inconnue" and not os.path.exists(os.path.join(d, "plages"))
            n = len([u for u in appels if "/pages/" in u])
            lancer(d, connus=[])                                                               # même jour : un seul essai compté
            assert _lire_json(os.path.join(d, "introuvables.json"), {})["pages/g/gallopin-tony.html"]["essais"] == 1
            for v in m.values():
                v["dernier_essai"] = "2026-01-01T00:00:00Z"
            _ecrire_json(os.path.join(d, "introuvables.json"), m)
            r = lancer(d, connus=[])
            assert r["pages_restantes"] == 0 and r["termine"] is True, r                       # abandonnées après 2 jours : plus redemandées
            assert len([u for u in appels if "/pages/" in u]) > n
            n = len([u for u in appels if "/pages/" in u])
            lancer(d, connus=[])
            assert len([u for u in appels if "/pages/" in u]) == n
    finally:
        netutil.fetch_text = orig
        netutil._blocked_hosts.discard(HOTE)
    mq: Dict[str, Dict[str, Any]] = {}
    assert _noter_manque(mq, "a.html") and not _noter_manque(mq, "a.html") and mq["a.html"]["essais"] == 1
    mq["b.html"] = {"essais": 2}
    assert _essais(mq, "b.html") == 0 and _noter_manque(mq, "b.html") and mq["b.html"]["essais"] == 1      # règle ancienne : re-tentée

    # abandon de l'hôte (403 / 429) : le passage s'arrête net, rien n'est noté, termine = False
    contenu2 = {BASE + "robots.txt": robots_txt, BASE + "sitemap.xml": sm}

    def bloque(url: str, *a: Any, **k: Any) -> Optional[str]:
        if url in contenu2:
            netutil.dernier_statut = 200
            return contenu2[url]
        netutil._blocked_hosts.add(HOTE)
        netutil.dernier_statut = 403
        return None
    netutil.fetch_text = bloque
    try:
        with tempfile.TemporaryDirectory() as d:
            r = lancer(d, connus=[])
            assert r["hote_bloque"] is True and r["termine"] is False and r["pages_lues"] == 0 and r["requetes"] == 3, r
            assert not _lire_json(os.path.join(d, "introuvables.json"), {})
    finally:
        netutil.fetch_text = orig
        netutil._blocked_hosts.discard(HOTE)
    print("[CLICS] tests OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--test", action="store_true", help="tests sans réseau")
    ap.add_argument("--sortie", default=SORTIE_DEFAUT, help="dossier de sortie (défaut : ARCHIVES_DIR/sources/clics)")
    ap.add_argument("--archives", default=None, help="dossier d'archives pour l'ordre de lecture (défaut : déduit de --sortie)")
    ap.add_argument("--pages", default="", help="liste de fragments de chemin (pages/g/gallopin-tony, pages/b/) : seules ces pages")
    ap.add_argument("--relire", action="store_true", help="relire aussi les pages déjà lues dont le lastmod n'a pas changé")
    ap.add_argument("--budget-min", type=float, default=0.0, help="budget de temps en minutes (0 = illimité)")
    ap.add_argument("--max-requetes", "--max-pages", dest="max_requetes", type=int, default=0,
                    help="plafond de requêtes du passage, robots.txt et sitemap compris (0 = illimité ; essais)")
    ap.add_argument("--sans-decouverte", action="store_true", help="ne lit pas le sitemap : pages de pages.json (robots.txt lu et appliqué)")
    ap.add_argument("--garder-html", action="store_true", help="garde les pages lues (gzip, cache/) : relecture locale ; ne jamais committer")
    ap.add_argument("--decouverte-seule", action="store_true", help="ne lit que robots.txt et le sitemap, écrit pages.json")
    a = ap.parse_args()
    if a.test:
        _tests()
        return 0
    lancer(a.sortie, a.archives, a.budget_min, a.max_requetes, a.pages.split(","), a.relire, a.decouverte_seule, a.sans_decouverte,
           a.garder_html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
