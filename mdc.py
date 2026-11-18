#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mémoire du Cyclisme (memoireducyclisme.fr) : palmarès et classements de courses sur route avant 2009 (collecteur,
étape 1 : pas d'intégration).

ACCORD : le 18/11/2026, les administrateurs du site (Dominique Magnier et « Pierrot ») ont donné au propriétaire du
projet leur accord pour lire le site par programme et afficher ses classements, avec le crédit « Mémoire du Cyclisme ».
Politesse : pas de robots.txt (404), mais User-Agent honnête « courses-cyclistes (accord Mémoire du Cyclisme) », >= 3 s
entre deux requêtes (petit serveur associatif), aucune page demandée deux fois (index en cache, courses lues une fois,
éditions écrites une fois sur disque ; `--relire` pour forcer), abandon de l'hôte sur 403 / 429.

Structure du site (refait fin 2024, HTML statique ; constatée le 18/11/2026, docs/recherche/mdc_collecte.md) :
  - accueil `/` -> index par rubrique : `ligne/en_ligne.html` (courses en ligne), `etapes/etapes.html` (courses par étapes),
    `amateurs/amateurs.html`, `disparues/disparues.html` (courses disparues, par nation). Chaque index liste des liens
    vers une page de COURSE (`ligne/cla_<nom>.html`, `etapes/eta_<nom>.html`, `amateurs/<nom>.html`,
    `disparues/anc_<nom>.html`) ; les courses « en gras » ont un classement détaillé.
  - page de course = palmarès de TOUTES les éditions (année en gras, date en petit, « 1. NOM Prénom (Nat) » pour les trois
    premiers, deux colonnes de tableau) ; l'année est un LIEN vers la page de classement de l'édition quand elle existe
    (`../cla_france/<course><année>.html`, `../eta_france/…`, `../anc_france_cla/…` : le dossier varie, on suit le lien lu,
    jamais deviné).
  - page de classement d'une édition : course d'un jour = un classement (« DÉPART - ARRIVÉE, 210 km », puis « 1. Prénom
    <b>NOM</b> (Nat) en 4h49'26" », « 2. Prénom Nom (Nat) à 2" », « m.t. ») ; course par étapes = liste des étapes, top 10
    de chaque étape (ligne `* Nom` après chaque étape), « Classement général » complet, puis pied (« Partants », « Classés »,
    « Distance », « Montagnes : », « Sprints : », « Equipes : »…). Pour les amateurs, « (El.2 - Vendée U) » = catégorie - club.
  - rubriques `criteriums/` et `championnats/` : index lisibles mais pages de détail en HTTP 404 au 18/11/2026 ; `eta_tdf/`
    (Tour de France) : une page par année avec une page par étape, hors périmètre de cette étape.

Règle cardinale du projet : aucune valeur inventée. Un champ absent reste absent. Interprétations (déterministes) :
  - nationalité : code du site tel qu'écrit (`pays_site`) ET `nat` = code canonique de `pays_historiques.json` par `pays.pays_normalise`
    (pays existant : code actuel ; pays disparu : code D'ÉPOQUE, ex. Rfa -> FRG, Urs -> URS, Rda -> GDR, jamais converti ; `Tch` après
    1992 : ambigu, vide ; un code absent de la table : `nat` absent, compté) ; AUCUNE mention = nationalité non écrite (jamais déduite France, même si les pages de
    courses françaises omettent « (Fra) » pour les Français) ;
  - temps : « en <temps> » (1er) -> `temps_s` ; « à <écart> » -> `ecart_s` (écart au 1er, croissant sur toutes les pages
    lues) ; « m.t. » / « s.t. » -> `meme_temps: true` ; une ligne sans mention n'a ni temps ni écart (on n'infère PAS
    « même temps que le précédent ») ; format illisible : texte brut (`temps_brut` / `ecart_brut`), compté ;
  - nom : `affiche` tel que lu ; `nom_famille` / `prenom` seulement quand la typographie le dit (majuscules dans le palmarès,
    gras sur le vainqueur d'un classement) ; aucune date de naissance ni identifiant de coureur sur le site ;
  - `etoile` (ligne « * Nom » après un classement d'étape) : texte brut, signification non confirmée.

Sortie (`--sortie`, défaut ARCHIVES_DIR/sources/mdc) : `courses.json` (index + palmarès de toutes les éditions, podium tel
qu'affiché), `editions/<id course>/<année>.json` (classement de la page de l'édition, `source_url`, `lu_le`), `etat.json`
(`{"termine", "editions_restantes", "courses_restantes"}`, sans horodatage : lu par un workflow pour l'auto-relance),
`introuvables.json` (pages en erreur, abandonnées après 2 essais), `cache/` (accueil et index en gzip).

    python mdc.py --sortie DOSSIER [--avant 2009] [--depuis AAAA] [--courses ligne-morbihan,etapes-td_limousin]
                  [--sections ligne,etapes] [--relire] [--budget-min N] [--max-requetes N] [--decouverte-seule]
                  [--sans-decouverte] [--garder-html]
    python mdc.py --test            # tests sans réseau (pages réelles allégées de tools/fixtures/mdc/)
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
from pays import pays_normalise

BASE = "https://www.memoireducyclisme.fr/"
HOTE = "www.memoireducyclisme.fr"
USER_AGENT = "courses-cyclistes (accord Mémoire du Cyclisme)"
PAUSE_S = 3.2                      # >= 3 s entre deux requêtes (politesse : petit serveur associatif)
netutil.HOST_DELAYS[HOTE] = PAUSE_S
AVANT_DEFAUT = 2009                # classements détaillés des éditions <= 2008 (le palmarès de toutes les années est gardé)
ARCHIVES_DIR = os.environ.get("ARCHIVES_DIR") or os.path.join("data", "archives")
SORTIE_DEFAUT = os.path.join(ARCHIVES_DIR, "sources", "mdc")
RACINE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(RACINE, "tools", "fixtures", "mdc")
ECHECS_MAX = 2                     # une page absente (404) 2 jours différents n'est plus redemandée (reste absente : rien d'inventé)
# Règle de comptage (voir thesports.REGLE_ECHECS) : une panne (réseau, 5xx, site abandonné) ne note rien, au plus un essai compté par page
# et par jour ; une entrée de `introuvables.json` sans `regle` ou de règle plus ancienne est re-tentée, compteur remis à 0.
REGLE_ECHECS = 2


def _essais(manques: Dict[str, Dict[str, Any]], rel: str) -> int:
    """Essais comptés de la page `rel` (0 pour une entrée de règle ancienne : à relire)."""
    m = manques.get(rel) or {}
    return m.get("essais", 0) if m.get("regle", 0) >= REGLE_ECHECS else 0


def _noter_manque(manques: Dict[str, Dict[str, Any]], rel: str) -> bool:
    """Compte un essai raté (page absente) : au plus un par jour. Retourne vrai si l'entrée a changé."""
    maintenant = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n = _essais(manques, rel)
    if n and manques[rel].get("dernier_essai", "")[:10] == maintenant[:10]:
        return False
    manques[rel] = {"essais": n + 1, "dernier_essai": maintenant, "regle": REGLE_ECHECS}
    return True

# Rubriques lues : dossier -> page d'index (relative à la racine, lue sur l'accueil, jamais devinée si absente de l'accueil).
SECTIONS = {"ligne": "ligne/en_ligne.html", "etapes": "etapes/etapes.html", "amateurs": "amateurs/amateurs.html",
            "disparues": "disparues/disparues.html"}
PREFIXES_FICHIER = ("cla_", "eta_", "anc_")

MOIS_FR = {"janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
           "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12}

# Codes pays du site : table `sources.mdc` de pays_historiques.json (voir pays.py). Les parenthèses mêlent pays (casse mixte :
# Fra, Hol, Rfa…) et clubs (ACBB, VCL…) : seuls les codes de la table donnent un `nat`, les autres sont comptés (`codes_pays_inconnus`).


# --------------------------------------------------------------------------------------------------
# Lecture du HTML (expressions régulières : pages très régulières, aucune dépendance)
# --------------------------------------------------------------------------------------------------

def _txt(fragment: str) -> str:
    """HTML -> texte : balises retirées, entités décodées, espaces (dont insécables) réduits."""
    t = _html.unescape(re.sub(r"<[^>]+>", "", fragment or ""))
    return re.sub(r"\s+", " ", t.replace("\xa0", " ")).strip()


def _corps(page: str) -> str:
    """Colonne centrale (td de 472 px) : du début de la cellule à la colonne de droite (147 px) ou à la fin du document."""
    m = re.search(r'<td[^>]*width="472"[^>]*>', page)
    debut = m.end() if m else 0
    fin = re.search(r'<td[^>]*width="147"', page[debut:])
    return page[debut: debut + fin.start()] if fin else page[debut:]


def _chunks(corps: str) -> List[str]:
    return re.split(r"<br\s*/?>|</?(?:table|tbody|tr|td|p|blockquote)\b[^>]*>", corps, flags=re.I)


def parse_duree(brut: str) -> Optional[int]:
    """Temps ou écart en secondes, formats écrits par le site : 4h49'26" ; 8'00" ; 59" (guillemets ", ″, '' ou ’’) ;
    tout autre format -> None (jamais interprété)."""
    s = (brut or "").strip().replace("’", "'").replace("″", '"').replace("”", '"')
    s = s.replace("''", '"')
    m = re.fullmatch(r"(\d{1,3})h(\d{1,2})'(\d{1,2})\"?", s)
    if m:
        h, mi, se = (int(x) for x in m.groups())
        return h * 3600 + mi * 60 + se if mi < 60 and se < 60 else None
    m = re.fullmatch(r"(\d{1,3})'(\d{1,2})\"?", s)
    if m:
        mi, se = int(m.group(1)), int(m.group(2))
        return mi * 60 + se if se < 60 else None
    m = re.fullmatch(r"(\d{1,3})\"", s)
    if m:
        return int(m.group(1))
    return None


def parse_date_fr(txt: str, annee: int) -> Dict[str, str]:
    """« 5 mai », « 1er juin », « du 21 au 24 août », « du 30 juin au 3 juillet » (+ l'année) -> date / date_debut + date_fin ISO.
    Format inconnu : {} (le texte brut reste dans `date_txt`)."""
    t = netutil.normalize(txt or "")

    def iso(j: str, mois: str, a: int) -> Optional[str]:
        mo = MOIS_FR.get(mois)
        if not mo:
            return None
        try:
            return datetime.date(a, mo, int(re.sub(r"\D", "", j))).isoformat()
        except ValueError:
            return None

    m = re.fullmatch(r"(\d{1,2})(?:er)? ([a-z]+)", t)
    if m:
        d = iso(m.group(1), m.group(2), annee)
        return {"date": d} if d else {}
    m = re.fullmatch(r"du (\d{1,2})(?:er)? au (\d{1,2})(?:er)? ([a-z]+)", t)
    if m:
        d1, d2 = iso(m.group(1), m.group(3), annee), iso(m.group(2), m.group(3), annee)
        return {"date_debut": d1, "date_fin": d2} if d1 and d2 else {}
    m = re.fullmatch(r"du (\d{1,2})(?:er)? ([a-z]+) au (\d{1,2})(?:er)? ([a-z]+)", t)
    if m:
        d1, d2 = iso(m.group(1), m.group(2), annee), iso(m.group(3), m.group(4), annee)
        return {"date_debut": d1, "date_fin": d2} if d1 and d2 else {}
    return {}


def id_course(url_rel: str, deja: Optional[Dict[str, Any]] = None) -> str:
    """`ligne/cla_morbihan.html` -> `ligne-morbihan` (préfixes cla_ / eta_ / anc_ retirés sauf collision)."""
    section, _, fichier = url_rel.partition("/")
    stem = re.sub(r"\.html$", "", fichier)
    court = stem
    for p in PREFIXES_FICHIER:
        if stem.startswith(p):
            court = stem[len(p):]
            break
    cid = "%s-%s" % (section, court)
    if deja is not None and cid in deja and deja[cid].get("url") != url_rel:
        cid = "%s-%s" % (section, stem)
    return cid


def lire_sections_accueil(page: str) -> Dict[str, str]:
    """Pages d'index lues sur les liens de l'accueil (seulement les rubriques de SECTIONS, chemin tel qu'écrit)."""
    out: Dict[str, str] = {}
    for h in re.findall(r'href="([^"#]+)"', page):
        chemin = urllib.parse.urljoin(BASE, h)
        rel = chemin[len(BASE):] if chemin.startswith(BASE) else ""
        for s, idx in SECTIONS.items():
            if rel == idx:
                out[s] = rel
    return out


def lire_index(page: str, rel_index: str) -> List[Dict[str, Any]]:
    """Liens de courses d'une page d'index. Chaque entrée : url (relative à la racine), nom, groupe (ancre `<a name>` précédente :
    catégorie ou nation selon la rubrique), gras (classement détaillé annoncé), suffixe (texte lu après le lien : « (Fra) »,
    période « 1989-2015 »…). Les liens de navigation (autre dossier, index lui-même, info_site) sont ignorés."""
    section = rel_index.split("/")[0]
    base = BASE + rel_index
    ancres = [(m.start(), urllib.parse.unquote(m.group(1)))
              for m in re.finditer(r'<a\s+name="([^"]+)"', page)]
    sorties: List[Dict[str, Any]] = []
    vus = set()
    for m in re.finditer(r'<a\s+[^>]*href="([^"#]+\.html)"[^>]*>(.*?)</a>(.*?)(?=<a\s|<br|</sup>|$)', page, flags=re.S):
        href, interieur, suite = m.group(1), m.group(2), m.group(3)
        chemin = urllib.parse.urljoin(base, href)
        if not chemin.startswith(BASE):
            continue
        rel = chemin[len(BASE):]
        if rel == rel_index or not rel.startswith(section + "/") or rel.count("/") != 1:
            continue
        if rel in vus:
            continue
        nom = _txt(interieur)
        if not nom or nom.lower().startswith(("index", "courses ")):
            continue
        groupe = None
        for pos, nm in ancres:
            if pos < m.start():
                groupe = nm
        vus.add(rel)
        pre = page[max(0, m.start() - 12): m.start()]
        sorties.append({"url": rel, "nom": nom, "groupe": groupe, "gras": ("<b>" in interieur.lower()) or pre.endswith("<b>"),
                        "suffixe": _txt(suite).strip(" -") or None})
    return sorties


def _sans_rang(ch: str) -> str:
    """Chunk HTML sans son numéro de rang initial (les balises qui le précèdent sont conservées)."""
    return re.sub(r"^((?:\s|<[^>]+>)*?)\d+\.?\s*", r"\1", ch, count=1)


# --- lignes de classement -------------------------------------------------------------------------

_RE_RANG = re.compile(r"^(\d{1,4})\.?\s+(\S.*)$")
_RE_MT = re.compile(r"\s+(?:m\.t\.|s\.t\.)\s*$", re.I)
_RE_A = re.compile(r"\s+à\s+([0-9hH'’\"″.:]+)\s*$")
_RE_EN = re.compile(r"\s+en\s+([0-9hH'’\"″.:]+)\s*$")
_RE_PAREN = re.compile(r"\s*\(([^()]*)\)\s*")


def lire_ligne(rang: int, reste_html: str, mode_nom: str, stats: Dict[str, Any], annee: Optional[int] = None) -> Dict[str, Any]:
    """`Prénom <b>NOM</b> (Bel) en 4h49'26"` / `NOM Prénom (Bel)` / `Prénom Nom (El.2 - Club) à 2"` -> ligne structurée.
    mode_nom : "gras" (classement : le vainqueur a son NOM en gras) ou "majuscules" (palmarès : NOM en majuscules)."""
    ligne: Dict[str, Any] = {"rang": rang}
    gras = [_txt(g) for g in re.findall(r"<b>(.*?)</b>", reste_html, flags=re.S | re.I) if _txt(g)]
    t = _txt(reste_html)
    if t == "?":
        ligne["inconnu"] = True
        return ligne
    if _RE_MT.search(t):
        ligne["meme_temps"] = True
        t = _RE_MT.sub("", t)
    m = _RE_A.search(t)
    if m:
        brut = m.group(1)
        s = parse_duree(brut)
        if s is None:
            ligne["ecart_brut"] = brut
            stats["temps_illisibles"] += 1
        else:
            ligne["ecart_s"] = s
        t = t[:m.start()]
    m = _RE_EN.search(t)
    if m:
        brut = m.group(1)
        s = parse_duree(brut)
        if s is None:
            ligne["temps_brut"] = brut
            stats["temps_illisibles"] += 1
        else:
            ligne["temps_s"] = s
        t = t[:m.start()]
    autres: List[str] = []
    for g in _RE_PAREN.findall(t):
        g = g.strip()
        if re.fullmatch(r"[A-Za-z]{2,4}", g):
            ligne["pays_site"] = g
            iso = pays_normalise(g, "mdc", annee)
            if iso:
                ligne["nat"] = iso
            else:
                stats["codes_pays_inconnus"][g] = stats["codes_pays_inconnus"].get(g, 0) + 1
        else:
            mm = re.fullmatch(r"(.+?)\s+-\s+(.+)", g)
            if mm:
                ligne["categorie"], ligne["equipe"] = mm.group(1).strip(), mm.group(2).strip()
            else:
                autres.append(g)
    if autres:
        ligne["parentheses"] = autres
    nom = _RE_PAREN.sub(" ", t).strip()
    ligne["affiche"] = nom
    if mode_nom == "gras" and rang == 1 and gras:
        fam = gras[0]
        if fam in nom:
            ligne["nom_famille"] = fam
            pre = nom.split(fam)[0].strip()
            if pre:
                ligne["prenom"] = pre
    elif mode_nom == "majuscules":
        jetons = nom.split()
        i = 0
        while i < len(jetons) and jetons[i] == jetons[i].upper() and re.search(r"[A-ZÀ-Ý]", jetons[i]):
            i += 1
        if i:
            ligne["nom_famille"] = " ".join(jetons[:i])
            if jetons[i:]:
                ligne["prenom"] = " ".join(jetons[i:])
    return ligne


def lire_partant(ch: str, stats: Dict[str, Any], annee: Optional[int] = None) -> Dict[str, Any]:
    """Coureur de la liste « Les partants » : `NOM Prénom (Nat) (ab.4°)` ; les mentions entre parenthèses qui ne sont pas un code
    pays (`ab.4°` = abandon à l'étape 4, `forfait`, `np.3°`) sont gardées telles quelles dans `remarque`."""
    reste = re.sub(r"\s+(?:np|ab)\.\S+\s*$", lambda m: " (" + m.group(0).strip() + ")", _txt(ch))
    l = lire_ligne(0, reste, "majuscules", stats, annee)
    l.pop("rang", None)
    if "parentheses" in l:
        l["remarque"] = " ; ".join(l.pop("parentheses"))
    return l


# --- page de course (palmarès) -------------------------------------------------------------------

def _debut_edition(chunk_html: str) -> Optional[Tuple[int, Optional[str], str]]:
    """Chunk d'en-tête d'édition : année en gras (éventuellement lien), date en petit -> (année, href, texte de date)."""
    if not re.search(r"<b>", chunk_html, re.I):
        return None
    t = _txt(chunk_html)
    m = re.match(r"^(\d{4})(?!\d|\.)\b\s*(.*)$", t)
    if not m or not (1850 <= int(m.group(1)) <= 2100):
        return None
    h = re.search(r'href="([^"#]+)"', chunk_html)
    return int(m.group(1)), (h.group(1) if h else None), m.group(2).strip()


def lire_palmares(page: str, url_course: str, stats: Dict[str, Any]) -> Dict[str, Any]:
    """Page de course -> titre, classe du site, drapeau, éditions [{annee, cle, date_txt, date…, url?, podium[], notes?}]."""
    out: Dict[str, Any] = {}
    mt = re.search(r"<title>(.*?)</title>", page, flags=re.S | re.I)
    if mt:
        titre = _txt(mt.group(1))
        out["titre_page"] = titre
        mc = re.search(r"-\s*Cat\.\s*(\S+)\s*$", titre)
        if mc:
            out["classe_site"] = mc.group(1)
    mf = re.search(r'images/drapeaux/([a-z]+)\.gif', _corps(page))
    if mf:
        out["drapeau"] = mf.group(1)
    editions: List[Dict[str, Any]] = []
    courante: Optional[Dict[str, Any]] = None
    annees_vues: Dict[int, int] = {}
    corps, _, bas = _corps(page).partition("<hr")
    notes_course = [t for t in (_txt(c) for c in _chunks(bas)) if t]
    if notes_course:
        out["notes"] = notes_course                 # remarques sous le tableau (changements de nom, éditions non disputées)
    for ch in _chunks(corps):
        deb = _debut_edition(ch)
        if deb:
            annee, href, date_txt = deb
            annees_vues[annee] = annees_vues.get(annee, 0) + 1
            courante = {"annee": annee, "cle": str(annee) if annees_vues[annee] == 1 else "%d-%d" % (annee, annees_vues[annee]),
                        "podium": []}
            if date_txt:
                courante["date_txt"] = date_txt
                courante.update(parse_date_fr(date_txt, annee))
            if href:
                chemin = urllib.parse.urljoin(url_course, href)
                if chemin.startswith(BASE) and chemin.endswith(".html"):
                    courante["url"] = chemin[len(BASE):]
            editions.append(courante)
            continue
        t = _txt(ch)
        if courante is None or not t:
            continue
        m = _RE_RANG.match(t)
        if m and int(m.group(1)) <= 10:
            courante["podium"].append(lire_ligne(int(m.group(1)), _sans_rang(ch), "majuscules", stats, courante["annee"]))
            stats["lignes_palmares"] += 1
        elif t and not re.fullmatch(r"[&nbsp;\s]*", t):
            courante.setdefault("notes", []).append(t[:120])
            stats["notes_palmares"] += 1
    out["editions"] = sorted(editions, key=lambda e: (e["annee"], e["cle"]))
    return out


# --- page de classement d'une édition -----------------------------------------------------------

_RE_ETAPES_ENTETE = re.compile(r"^Etapes?\s+du\s+(.*)$", re.I)
_RE_PLAGE = re.compile(r"(\d{1,2})(?:/(\d{1,2}))?(?:/(\d{4}))?\s+au\s+(\d{1,2})/(\d{1,2})/(\d{4})")
_RE_ETAPE_LISTE = re.compile(r"^(Prol\.?|Prologue|\d+[a-z]?)\s+(.+?)(?:,?\s*([\d.]+)\s*km\b\s*(.*))?$", re.I)
_RE_TITRE_KM = re.compile(r"^(.*?)(?:,|\s)\s*([\d.]+)\s*km\s*(.*)$", re.I)
_RE_PIED = re.compile(r"^([A-ZÉ][A-Za-zéèêàçÉ' ]{2,24}?)\s*:\s*(.*)$")


def _distance(s: Optional[str]) -> Optional[float]:
    try:
        return float(s) if s else None
    except ValueError:
        return None


def lire_edition(page: str, url_rel: str, annee: Optional[int] = None) -> Dict[str, Any]:
    """Page de classement d'une édition -> {titre, type, etapes?, classements[], resume, annexes, ...} + `stats` (compteurs)."""
    stats: Dict[str, Any] = {"lignes": 0, "temps_illisibles": 0, "codes_pays_inconnus": {}, "lignes_inconnues": 0,
                             "lignes_palmares": 0, "notes_palmares": 0, "partants": 0}
    out: Dict[str, Any] = {}
    mt = re.search(r"<title>(.*?)</title>", page, flags=re.S | re.I)
    if mt:
        out["titre_page"] = _txt(mt.group(1))
    entete = False
    etapes_liste: List[Dict[str, Any]] = []
    sections: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    resume: Dict[str, Any] = {}
    annexes: Dict[str, str] = {}
    remerciements: List[str] = []
    inconnues: List[str] = []
    multi = False
    partants: Optional[List[Dict[str, Any]]] = None
    for ch in _chunks(_corps(page)):
        if re.search(r"<hr", ch, re.I):
            entete = False
        t = _txt(ch)
        if not t:
            continue
        # --- en-tête d'une course par étapes : « Etapes du 19 au 22/08/2003 » puis la liste des étapes
        me = _RE_ETAPES_ENTETE.match(t)
        if me and not sections:
            multi = True
            entete = True
            out["etapes_titre"] = t
            mp = _RE_PLAGE.search(me.group(1))
            if mp:
                j1, m1, a1, j2, m2, a2 = mp.groups()
                try:
                    out["date_debut"] = datetime.date(int(a1 or a2), int(m1 or m2), int(j1)).isoformat()
                    out["date_fin"] = datetime.date(int(a2), int(m2), int(j2)).isoformat()
                except ValueError:
                    pass
            continue
        if entete and multi:
            ml = _RE_ETAPE_LISTE.match(t)
            if ml:
                e: Dict[str, Any] = {"numero": ml.group(1), "parcours": ml.group(2).strip(" ,")}
                if _distance(ml.group(3)) is not None:
                    e["distance_km"] = _distance(ml.group(3))
                if (ml.group(4) or "").strip():
                    e["type_site"] = ml.group(4).strip()
                etapes_liste.append(e)
                continue
        # --- « Les partants » : équipes (ligne en gras) puis coureurs (parfois coupé en deux chunks par la balise <u>)
        if t.lower().startswith("les partants"):
            partants = []
            cur = None
            continue
        if partants is not None and not entete:
            gras_t = "".join(_txt(g) for g in re.findall(r"<b>(.*?)</b>", ch, flags=re.S | re.I))
            if gras_t and gras_t == t:                      # ligne entièrement en gras = nom d'équipe
                partants.append({"nom": t, "coureurs": []})
            elif partants:
                partants[-1]["coureurs"].append(lire_partant(ch, stats, annee))
                stats["partants"] += 1
            else:
                stats["lignes_inconnues"] += 1
            continue
        # --- titre d'un classement (balise <u>)
        if re.search(r"<u>", ch, re.I):
            if cur is not None and cur.get("titre_brut") == t:
                continue                                   # titre répété avant le pied de page : même classement
            cur = {"titre_brut": t, "lignes": []}
            mk = _RE_TITRE_KM.match(t)
            if mk:
                cur["titre"] = mk.group(1).strip(" ,")
                if _distance(mk.group(2)) is not None:
                    cur["distance_km"] = _distance(mk.group(2))
                if mk.group(3).strip():
                    cur["type_site"] = mk.group(3).strip()
            else:
                cur["titre"] = t.rstrip(" :")
            ms = re.match(r"^(Prol\.?|Prologue|\d+[a-z]?)\s+(.*)$", cur["titre"], re.I)
            if re.match(r"classement g[ée]n[ée]ral", t, re.I):
                cur["type"] = "general"
            elif multi and ms:
                cur["type"] = "etape"
                cur["numero"], cur["parcours"] = ms.group(1), ms.group(2).strip()
            elif not multi and not sections:
                cur["type"] = "course"
                cur["parcours"] = cur["titre"]
            else:
                cur["type"] = "autre"                       # grimpeur, points chauds, sprints… (libellé du site dans `titre`)
            sections.append(cur)
            continue
        # --- ligne de classement
        mr = _RE_RANG.match(t)
        if mr and cur is not None and not entete:
            ligne = lire_ligne(int(mr.group(1)), _sans_rang(ch), "gras", stats, annee)
            if cur.get("type") == "autre":
                mp = re.search(r"\s(\d+)(?:\s*points?)?$", ligne.get("affiche") or "")   # ligne sans libellé : rien
                if mp:                                      # classement annexe : « 1. Pierre BAZZO (Fra) 25 points »
                    ligne["points"] = int(mp.group(1))
                    ligne["affiche"] = ligne["affiche"][:mp.start()].strip()
            cur["lignes"].append(ligne)
            stats["lignes"] += 1
            continue
        if t == "...":
            if cur is not None:
                cur["tronque"] = True                       # le site coupe la liste (« ... ») : classement incomplet
            continue
        if t.startswith("*") and cur is not None:
            cur["etoile"] = t.lstrip("* ").strip()
            continue
        # --- pied de page
        md = re.match(r"^Disputé le (.*?)\.?$", t)
        if md:
            resume["date_txt"] = md.group(1)
            mj = re.match(r"^(\d{1,2})(?:er)? (\S+) (\d{4})$", md.group(1))
            if mj:
                d = parse_date_fr("%s %s" % (mj.group(1), mj.group(2)), int(mj.group(3)))
                if d.get("date"):
                    resume["date"] = d["date"]
            continue
        if t.lower().startswith("merci"):
            remerciements.append(t)
            continue
        mp = _RE_PIED.match(t)
        if mp and not entete:
            cle, val = mp.group(1).strip(), mp.group(2).strip()
            if val in ("?", ""):
                continue                                  # « Partants : ? » : valeur inconnue du site, champ absent
            if cle.lower() in ("partants", "classés", "classes"):
                try:
                    resume["partants" if cle.lower() == "partants" else "classes"] = int(val)
                except ValueError:
                    resume[cle.lower() + "_txt"] = val
            elif cle.lower() == "distance":
                mk = re.match(r"^([\d.]+)\s*km", val)
                if mk:
                    resume["distance_km"] = _distance(mk.group(1))
                else:
                    resume["distance_txt"] = val
            elif cle.lower() == "moyenne":
                mk = re.match(r"^([\d.]+)\s*km/h", val)
                if mk:
                    resume["moyenne_kmh"] = _distance(mk.group(1))
                else:
                    resume["moyenne_txt"] = val
            else:
                annexes[cle] = val
            continue
        stats["lignes_inconnues"] += 1
        if len(inconnues) < 5:
            inconnues.append(t[:100])
    out["type"] = "etapes" if multi else "course"
    if etapes_liste:
        out["etapes"] = etapes_liste
    notes_site = [x["titre_brut"] for x in sections if x["type"] == "autre" and not x["lignes"]]
    sections = [x for x in sections if x["lignes"] or x["type"] != "autre"]
    if notes_site:
        out["notes_site"] = notes_site                      # intertitres sans classement (« Source : Vélo n° 146… »)
    out["classements"] = sections
    if partants:
        out["equipes_partantes"] = partants
    if resume:
        out["resume"] = resume
    if annexes:
        out["annexes"] = annexes
    if remerciements:
        out["remerciements"] = remerciements
    if inconnues:
        out["lignes_inconnues"] = inconnues
    out["stats"] = stats
    return out


# --------------------------------------------------------------------------------------------------
# Réseau, stockage, reprise
# --------------------------------------------------------------------------------------------------

class Session:
    """Requêtes polies (pause par hôte, budget, compteur) ; accueil et index en cache gzip sur disque."""

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

    def epuise(self) -> bool:
        if self.budget_s and time.monotonic() - self.t0 >= self.budget_s:
            return True
        return bool(self.max_pages) and self.requetes >= self.max_pages

    def hote_bloque(self) -> bool:
        return HOTE in netutil._blocked_hosts

    def _cache(self, url: str) -> str:
        return os.path.join(self.sortie, "cache", hashlib.sha1(url.encode()).hexdigest()[:16] + ".html.gz")

    def page(self, rel: str, mettre_en_cache: bool = False) -> Optional[str]:
        url = rel if rel.startswith("http") else BASE + rel
        chemin = self._cache(url)
        if mettre_en_cache and os.path.exists(chemin):
            with gzip.open(chemin, "rt", encoding="utf-8") as f:
                return f.read()
        self.absente = False
        if self.epuise() or self.hote_bloque():
            return None
        self.requetes += 1
        texte = netutil.fetch_text(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        if texte is None:
            self.echecs += 1
            self.absente = netutil.page_absente()
            return None
        if mettre_en_cache:
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            with gzip.open(chemin, "wt", encoding="utf-8") as f:
                f.write(texte)
        return texte

    def journal(self, message: str, force: bool = False) -> None:
        if force or time.monotonic() - self.dernier_journal >= 300:
            self.dernier_journal = time.monotonic()
            print("[MDC] %s (%d requêtes, %.1f min)" % (message, self.requetes, (time.monotonic() - self.t0) / 60))


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


def chemin_edition(sortie: str, cid: str, cle: str) -> str:
    return os.path.join(sortie, "editions", cid, "%s.json" % cle)


def _noms_podium(lignes: List[Dict[str, Any]]) -> List[str]:
    """Jetons normalisés (triés) du nom de chaque ligne du podium : comparaison palmarès / classement sans ordre prénom-nom."""
    return [" ".join(sorted(netutil.normalize(l.get("affiche", "")).split())) for l in lignes[:3]]


def lancer(sortie: str, avant: int = AVANT_DEFAUT, depuis: Optional[int] = None, cibles: Optional[List[str]] = None,
           sections: Optional[List[str]] = None, relire: bool = False, budget_min: float = 0.0,
           decouverte_seule: bool = False, max_pages: int = 0, sans_decouverte: bool = False,
           garder_html: bool = False) -> Dict[str, Any]:
    """Découverte (accueil -> index -> courses), puis course par course : page de course (palmarès de toutes les éditions)
    et pages de classement des éditions de la période. Reprenable ; écrit `etat.json` en fin de passage."""
    sess = Session(sortie, budget_min, max_pages, garder_html)
    cibles = [c.strip().lower() for c in (cibles or []) if c.strip()]
    sections = [s.strip().lower() for s in (sections or []) if s.strip()] or list(SECTIONS)
    chemin_courses = os.path.join(sortie, "courses.json")
    reg = _lire_json(chemin_courses, {"source": "memoire-du-cyclisme", "courses": {}})
    courses: Dict[str, Dict[str, Any]] = reg.setdefault("courses", {})
    chemin_manques = os.path.join(sortie, "introuvables.json")
    manques: Dict[str, Dict[str, Any]] = _lire_json(chemin_manques, {})
    decouverte_ok = True
    resume = {"index_lus": 0, "courses": 0, "courses_lues": 0, "editions_lues": 0, "editions_deja": 0, "echecs": 0,
              "lignes": 0, "temps_illisibles": 0, "codes_pays_inconnus": {}, "lignes_inconnues": 0,
              "podiums_divergents": [], "editions_sans_classement": 0}

    def cible_ok(cid: str, c: Dict[str, Any]) -> bool:
        if not cibles:
            return True
        return any(t == cid.lower() or t in (c.get("url") or "").lower() for t in cibles)

    # --- découverte : accueil -> index des rubriques -> courses
    if not sans_decouverte:
        accueil = sess.page("", mettre_en_cache=True)
        idx = lire_sections_accueil(accueil) if accueil else {}
        if not idx:
            decouverte_ok = False
            print("[MDC] [WARN] rubriques introuvables sur l'accueil : découverte impossible")
        for s in sections:
            if s not in idx:
                if idx:
                    decouverte_ok = False
                continue
            page = sess.page(idx[s], mettre_en_cache=True)
            if not page:
                decouverte_ok = False
                continue
            resume["index_lus"] += 1
            for lien in lire_index(page, idx[s]):
                cid = id_course(lien["url"], courses)
                c = courses.setdefault(cid, {"id": cid, "section": s, "url": lien["url"]})
                c.update({"nom": lien["nom"], "groupe": lien["groupe"], "gras": lien["gras"]})
                if lien["suffixe"]:
                    c["suffixe_index"] = lien["suffixe"]
                else:
                    c.pop("suffixe_index", None)
        _ecrire_json(chemin_courses, reg)
    resume["courses"] = len(courses)

    stats_lecture = {"lignes": 0, "temps_illisibles": 0, "codes_pays_inconnus": resume["codes_pays_inconnus"],
                     "lignes_inconnues": 0, "lignes_palmares": 0, "notes_palmares": 0, "partants": 0}

    def a_lire(ed: Dict[str, Any], cid: str) -> bool:
        if not ed.get("url"):
            return False
        if ed["annee"] >= avant or (depuis is not None and ed["annee"] < depuis):
            return False
        if _essais(manques, ed["url"]) >= ECHECS_MAX:
            return False
        return True

    def tente(rel: str) -> Optional[str]:
        page = sess.page(rel, sess.garder_html)
        if page is None and sess.absente and _noter_manque(manques, rel):     # panne passagère : rien n'est noté
            _ecrire_json(chemin_manques, manques)
        return page

    # --- lecture : course par course (palmarès, puis classements de la période)
    if not decouverte_seule:
        for cid, c in sorted(courses.items()):
            if c.get("section") not in sections or not cible_ok(cid, c):
                continue
            if "lu_le" not in c or relire:
                if sess.epuise() or sess.hote_bloque():
                    break
                if _essais(manques, c["url"]) >= ECHECS_MAX and "lu_le" not in c:
                    continue
                page = tente(c["url"])
                if not page:
                    continue
                p = lire_palmares(page, BASE + c["url"], stats_lecture)
                c.update({k: p[k] for k in ("titre_page", "classe_site", "drapeau") if k in p})
                c["editions"] = p["editions"]
                c["lu_le"] = _maintenant()
                resume["courses_lues"] += 1
                _ecrire_json(chemin_courses, reg)
                sess.journal("lecture : %d courses lues" % resume["courses_lues"])
            for ed in c.get("editions", []):
                if not a_lire(ed, cid):
                    continue
                chemin = chemin_edition(sortie, cid, ed["cle"])
                if os.path.exists(chemin) and not relire:
                    resume["editions_deja"] += 1
                    continue
                if sess.epuise() or sess.hote_bloque():
                    break
                page = tente(ed["url"])
                if not page:
                    continue
                contenu = lire_edition(page, ed["url"], ed["annee"])
                st = contenu.pop("stats")
                for k in ("lignes", "temps_illisibles", "lignes_inconnues"):
                    resume[k] += st[k]
                for code, n in st["codes_pays_inconnus"].items():
                    resume["codes_pays_inconnus"][code] = resume["codes_pays_inconnus"].get(code, 0) + n
                contenu.update({"source": "memoire-du-cyclisme", "source_url": BASE + ed["url"], "course_id": cid,
                                "annee": ed["annee"], "lu_le": _maintenant()})
                if ed.get("podium"):
                    contenu["podium_palmares"] = ed["podium"]
                tete = next((s for s in contenu["classements"] if s["lignes"]), None)
                if not tete:
                    resume["editions_sans_classement"] += 1
                elif ed.get("podium") and len(resume["podiums_divergents"]) < 20 and \
                        _noms_podium(tete["lignes"]) != _noms_podium(ed["podium"]) and tete.get("type") in ("course", "general"):
                    resume["podiums_divergents"].append("%s %d" % (cid, ed["annee"]))
                _ecrire_json(chemin, contenu, compact=True)
                resume["editions_lues"] += 1
                sess.journal("lecture : %d éditions lues" % resume["editions_lues"])
            if sess.epuise() or sess.hote_bloque():
                break

    # --- reste à faire (après la lecture : état réel du disque)
    editions_restantes = courses_restantes = 0
    for cid, c in courses.items():
        if c.get("section") not in sections or not cible_ok(cid, c):
            continue
        if "lu_le" not in c:
            if _essais(manques, c["url"]) < ECHECS_MAX:
                courses_restantes += 1
            continue
        for ed in c.get("editions", []):
            if a_lire(ed, cid) and not os.path.exists(chemin_edition(sortie, cid, ed["cle"])):
                editions_restantes += 1
    resume["echecs"] = sess.echecs
    resume["requetes"] = sess.requetes
    resume["duree_min"] = round((time.monotonic() - sess.t0) / 60, 1)
    resume["budget_epuise"] = sess.epuise()
    resume["hote_bloque"] = sess.hote_bloque()
    termine = bool(decouverte_ok and not editions_restantes and not courses_restantes and not decouverte_seule
                   and not sess.hote_bloque())
    _ecrire_json(os.path.join(sortie, "etat.json"), {"termine": termine, "editions_restantes": editions_restantes,
                                                     "courses_restantes": courses_restantes})
    resume["editions_restantes"], resume["courses_restantes"], resume["termine"] = \
        editions_restantes, courses_restantes, termine
    sess.journal("synthèse : %s" % json.dumps(resume, ensure_ascii=False, sort_keys=True), force=True)
    return resume


# --------------------------------------------------------------------------------------------------
# Tests sans réseau (pages réelles allégées dans tools/fixtures/mdc/)
# --------------------------------------------------------------------------------------------------

def _fixture(nom: str) -> str:
    with open(os.path.join(FIXTURES, nom), encoding="utf-8") as f:
        return f.read()


def _stats() -> Dict[str, Any]:
    return {"lignes": 0, "temps_illisibles": 0, "codes_pays_inconnus": {}, "lignes_inconnues": 0, "lignes_palmares": 0,
            "notes_palmares": 0, "partants": 0}


def _tests() -> None:
    # durées
    assert parse_duree("4h49'26\"") == 4 * 3600 + 49 * 60 + 26
    assert parse_duree("8'00\"") == 480 and parse_duree("1'20\"") == 80 and parse_duree("59\"") == 59
    assert parse_duree("2''") == 2 and parse_duree("17h28'30\"") == 17 * 3600 + 28 * 60 + 30
    assert parse_duree("4h49") is None and parse_duree("3'75\"") is None and parse_duree("abc") is None
    # dates
    assert parse_date_fr("1er juin", 2002) == {"date": "2002-06-01"}
    assert parse_date_fr("5 mai", 1974) == {"date": "1974-05-05"}
    assert parse_date_fr("du 21 au 24 août", 1975) == {"date_debut": "1975-08-21", "date_fin": "1975-08-24"}
    assert parse_date_fr("du 30 juin au 3 juillet", 2005) == {"date_debut": "2005-06-30", "date_fin": "2005-07-03"}
    assert parse_date_fr("n'importe quoi", 2000) == {}
    # identifiants
    assert id_course("ligne/cla_morbihan.html") == "ligne-morbihan"
    assert id_course("etapes/eta_td_limousin.html") == "etapes-td_limousin"
    assert id_course("amateurs/td_creuse.html") == "amateurs-td_creuse"
    assert id_course("disparues/anc_circ_limousin.html") == "disparues-circ_limousin"

    # accueil et index
    idx = lire_sections_accueil(_fixture("accueil.html"))
    assert idx == SECTIONS, idx
    liens = lire_index(_fixture("index_ligne.html"), "ligne/en_ligne.html")
    par_url = {l["url"]: l for l in liens}
    assert "ligne/cla_morbihan.html" in par_url and par_url["ligne/cla_morbihan.html"]["nom"] == "G.P du Morbihan"
    assert par_url["ligne/cla_morbihan.html"]["suffixe"] == "(Fra)" and par_url["ligne/cla_morbihan.html"]["gras"]
    assert par_url["ligne/cla_morbihan.html"]["groupe"] == "Hors-Catégorie", par_url["ligne/cla_morbihan.html"]
    assert all(l["url"].startswith("ligne/") and l["url"].count("/") == 1 for l in liens)
    assert len(liens) == len({l["url"] for l in liens}) >= 20
    liens_d = lire_index(_fixture("index_disparues.html"), "disparues/disparues.html")
    pd = {l["url"]: l for l in liens_d}
    assert pd["disparues/anc_bayern_rundfahrt.html"]["groupe"] == "ALL"
    assert pd["disparues/anc_bayern_rundfahrt.html"]["suffixe"] == "1989-2015"
    liens_e = lire_index(_fixture("index_etapes.html"), "etapes/etapes.html")
    assert any(l["url"] == "etapes/eta_td_limousin.html" and l["nom"] == "Tour du Limousin" for l in liens_e)

    # page de course : Morbihan (course d'un jour, podium, liens d'années)
    st = _stats()
    p = lire_palmares(_fixture("course_morbihan.html"), BASE + "ligne/cla_morbihan.html", st)
    assert p["classe_site"] == "1.PS" and p["drapeau"] == "fra"
    eds = {e["annee"]: e for e in p["editions"]}
    assert len(p["editions"]) == 47 and min(eds) == 1974 and max(eds) == 2024, len(p["editions"])
    assert eds[1974]["url"] == "cla_france/morbihan_1974.html" and eds[1974]["date"] == "1974-05-05"
    assert "url" not in eds[1976] and len(eds[1976]["podium"]) == 3
    assert eds[1996]["podium"][0] == {"rang": 1, "affiche": "CAPIOT Johan", "nom_famille": "CAPIOT", "prenom": "Johan",
                                      "pays_site": "Bel", "nat": "BEL"}, eds[1996]["podium"][0]
    assert eds[2002]["date"] == "2002-06-01" and eds[2002]["podium"][0]["nom_famille"] == "LEFEVRE"
    assert "nat" not in eds[2002]["podium"][0] and eds[2024]["podium"][2]["nat"] == "BEL"
    assert eds[1982]["podium"][1]["nom_famille"] == "DUCLOS-LASSALLE"
    assert st["notes_palmares"] == 0 and any("Non organisé en 1979" in n for n in p["notes"]), (st, p.get("notes"))

    # page de course : amateurs (pas de titre de catégorie, dates en plage)
    p = lire_palmares(_fixture("course_creuse.html"), BASE + "amateurs/td_creuse.html", _stats())
    e = {x["annee"]: x for x in p["editions"]}
    assert "classe_site" not in p and e[1997]["date_debut"] == "1997-07-23" and e[1997]["date_fin"] == "1997-07-24"
    assert e[1999]["podium"][2]["nat"] == "RUS" and all("url" not in x for x in p["editions"])

    # classement d'une édition : course d'un jour (Morbihan 1996)
    ed = lire_edition(_fixture("edition_morbihan_1996.html"), "cla_france/morbihan_1996.html")
    assert ed["type"] == "course" and len(ed["classements"]) == 1
    c = ed["classements"][0]
    assert c["parcours"] == "VANNES - SARZEAU" and c["distance_km"] == 210.0 and len(c["lignes"]) == 62
    l1, l2, l19 = c["lignes"][0], c["lignes"][1], c["lignes"][18]
    assert l1["temps_s"] == 4 * 3600 + 49 * 60 + 26 and l1["nom_famille"] == "CAPIOT" and l1["prenom"] == "Johan"
    assert l1["nat"] == "BEL" and l1["affiche"] == "Johan CAPIOT"
    assert l2["ecart_s"] == 2 and l2["nat"] == "EST" and l19["ecart_s"] == 8 and l19["nat"] == "AUS"
    assert "ecart_s" not in c["lignes"][2] and "temps_s" not in c["lignes"][2]      # jamais d'écart inféré
    l14 = c["lignes"][13]
    assert l14["categorie"] == "El.2" and l14["equipe"] == "Vendée U" and l14["affiche"] == "Thierry Bricaud", l14
    assert c["lignes"][41] == {"rang": 42, "inconnu": True}
    assert ed["resume"] == {"classes": 62, "moyenne_kmh": 43.534, "date_txt": "20 avril 1996", "date": "1996-04-20"}, ed["resume"]
    assert ed["remerciements"] == ["Merci à Thierry Faye."] and ed["stats"]["lignes"] == 62

    # classement d'une édition : course par étapes (Limousin 2003)
    ed = lire_edition(_fixture("edition_limousin_2003.html"), "eta_france/limousin2003.html")
    assert ed["type"] == "etapes" and ed["date_debut"] == "2003-08-19" and ed["date_fin"] == "2003-08-22"
    assert [e["numero"] for e in ed["etapes"]] == ["1", "2", "3", "4"] and ed["etapes"][0]["distance_km"] == 157.7
    assert [s["type"] for s in ed["classements"]] == ["etape"] * 4 + ["general"]
    e1, gc = ed["classements"][0], ed["classements"][4]
    assert e1["numero"] == "1" and e1["parcours"] == "Limoges-Saint Junien" and len(e1["lignes"]) == 10 and e1["etoile"] == "Rous"
    assert gc["titre"] == "Classement général" and len(gc["lignes"]) == 72
    assert gc["lignes"][0]["temps_s"] == 17 * 3600 + 28 * 60 + 30 and gc["lignes"][0]["nom_famille"] == "LELLI"
    assert gc["lignes"][3]["meme_temps"] is True and gc["lignes"][2]["ecart_s"] == 47
    assert ed["resume"]["partants"] == 118 and ed["resume"]["classes"] == 72 and ed["resume"]["distance_km"] == 695.7
    assert ed["annexes"]["Sprints"].startswith("Sébastien JOLY") and ed["annexes"]["Equipes"] == "COFIDIS"
    assert ed["stats"]["temps_illisibles"] == 0 and not ed["stats"]["codes_pays_inconnus"], ed["stats"]

    # classement ancien (Paris-Roubaix 1926 : « 23 » sans point, pas d'équipe, écarts)
    ed = lire_edition(_fixture("edition_roubaix_1926.html"), "cla_france/roubaix1926.html")
    c = ed["classements"][0]
    assert c["parcours"] == "LE VESINET - ROUBAIX" and c["distance_km"] == 270.0 and c["lignes"][22]["rang"] == 23
    assert c["lignes"][2]["ecart_s"] == 58 and c["lignes"][4]["ecart_s"] == 248 and c["lignes"][0]["temps_s"] == 7 * 3600 + 34 * 60 + 42
    assert ed["resume"]["partants"] == 147 and ed["resume"]["classes"] == 86 and ed["resume"]["date"] == "1926-04-04"

    # classement ancien par étapes avec listes de partants par équipe et classements annexes (Limousin 1983)
    ed = lire_edition(_fixture("edition_limousin_1983.html"), "eta_france/limousin1983.html", 1983)
    assert [c["type"] for c in ed["classements"]] == ["etape"] * 4 + ["general", "autre", "autre"]
    grimpeur = ed["classements"][5]
    assert grimpeur["titre"] == "Meilleur grimpeur" and grimpeur["lignes"][0]["points"] == 25 and grimpeur["lignes"][0]["nat"] == "FRA"
    eq = {e["nom"]: e["coureurs"] for e in ed["equipes_partantes"]}
    assert len(eq) == 8 and len(eq["COOP-MERCIER-MAVIC"]) == 12 and sum(len(v) for v in eq.values()) == 99
    assert eq["COOP-MERCIER-MAVIC"][1] == {"affiche": "BERTIN Yvon", "nom_famille": "BERTIN", "prenom": "Yvon", "remarque": "ab.4°"}
    assert ed["resume"]["partants"] == 96 and not ed["stats"]["codes_pays_inconnus"]
    rfa = [c for e in ed["equipes_partantes"] for c in e["coureurs"] if c.get("pays_site") == "Rfa"]
    assert rfa and all(c["nat"] == "FRG" for c in rfa), rfa      # pays disparu : code d'époque (RFA), brut conservé

    # comparaison palmarès / classement : mêmes noms, ordre prénom-nom indifférent
    assert _noms_podium([{"affiche": "CAPIOT Johan"}]) == _noms_podium([{"affiche": "Johan CAPIOT"}])

    # reprise : un second passage sur un dossier déjà complet ne fait aucune requête (réseau simulé indisponible)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        orig = netutil.fetch_text
        pages = {BASE: _fixture("accueil.html"), BASE + "ligne/en_ligne.html": _fixture("index_ligne.html"),
                 BASE + "ligne/cla_morbihan.html": _fixture("course_morbihan.html"),
                 BASE + "cla_france/morbihan_1996.html": _fixture("edition_morbihan_1996.html")}
        appels: List[str] = []

        def faux(url: str, *a: Any, **k: Any) -> Optional[str]:
            appels.append(url)
            netutil.dernier_statut = 200 if url in pages else 404
            return pages.get(url)
        netutil.fetch_text = faux
        try:
            r = lancer(d, avant=2000, cibles=["ligne-morbihan"], sections=["ligne"], depuis=1996)
            assert r["courses_lues"] == 1 and r["editions_lues"] == 1 and r["editions_restantes"] == 0, r
            assert _lire_json(os.path.join(d, "etat.json"), {}) == {"termine": r["termine"], "editions_restantes": 0,
                                                                    "courses_restantes": 0}
            ed = _lire_json(chemin_edition(d, "ligne-morbihan", "1996"), {})
            assert ed["source_url"] == BASE + "cla_france/morbihan_1996.html" and ed["podium_palmares"][0]["nat"] == "BEL"
            assert r["podiums_divergents"] == [], r
            n = len(appels)
            r2 = lancer(d, avant=2000, cibles=["ligne-morbihan"], sections=["ligne"], depuis=1996)
            assert len(appels) == n and r2["requetes"] == 0 and r2["editions_deja"] == 1, (len(appels), n, r2)
        finally:
            netutil.fetch_text = orig
    # échecs : 404 = un essai par jour, abandon après ECHECS_MAX jours ; entrée ancienne (sans `regle`) : à relire
    mq: Dict[str, Dict[str, Any]] = {}
    assert _noter_manque(mq, "a.html") and not _noter_manque(mq, "a.html") and mq["a.html"]["essais"] == 1
    mq["a.html"]["dernier_essai"] = "2026-01-01T00:00:00Z"
    assert _noter_manque(mq, "a.html") and _essais(mq, "a.html") >= ECHECS_MAX
    mq["b.html"] = {"essais": 2}
    assert _essais(mq, "b.html") == 0 and _noter_manque(mq, "b.html") and mq["b.html"]["essais"] == 1
    with tempfile.TemporaryDirectory() as d:                    # panne (503 / réseau) : aucun manque noté ; 404 : un manque
        orig = netutil.fetch_text
        pages = {BASE: _fixture("accueil.html"), BASE + "ligne/en_ligne.html": _fixture("index_ligne.html")}

        def faux2(url: str, *a: Any, **k: Any) -> Optional[str]:
            netutil.dernier_statut = 200 if url in pages else statut_faux[0]
            return pages.get(url)
        statut_faux = [503]
        netutil.fetch_text = faux2
        try:
            lancer(d, avant=2000, cibles=["ligne-morbihan"], sections=["ligne"], depuis=1996)
            assert not _lire_json(os.path.join(d, "introuvables.json"), {}), "503 : rien ne doit être noté"
            statut_faux[0] = 404
            lancer(d, avant=2000, cibles=["ligne-morbihan"], sections=["ligne"], depuis=1996)
            m404 = _lire_json(os.path.join(d, "introuvables.json"), {})
            assert m404 and all(v["essais"] == 1 and v["regle"] == REGLE_ECHECS for v in m404.values()), m404
        finally:
            netutil.fetch_text = orig
    print("[MDC] tests OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--test", action="store_true", help="tests sans réseau")
    ap.add_argument("--sortie", default=SORTIE_DEFAUT, help="dossier de sortie (défaut : ARCHIVES_DIR/sources/mdc)")
    ap.add_argument("--avant", type=int, default=AVANT_DEFAUT, help="classements des éditions strictement avant cette année (défaut 2009)")
    ap.add_argument("--depuis", type=int, default=None, help="classements des éditions à partir de cette année")
    ap.add_argument("--courses", default="", help="liste : id de course (ligne-morbihan) ou fragment d'URL (cla_morbihan)")
    ap.add_argument("--sections", default="", help="liste de rubriques : ligne, etapes, amateurs, disparues (défaut : toutes)")
    ap.add_argument("--relire", action="store_true", help="relire aussi les pages déjà lues")
    ap.add_argument("--budget-min", type=float, default=0.0, help="budget de temps en minutes (0 = illimité)")
    ap.add_argument("--max-requetes", "--max-pages", dest="max_requetes", type=int, default=0,
                    help="plafond de requêtes du passage (0 = illimité ; essais)")
    ap.add_argument("--sans-decouverte", action="store_true", help="ne relit pas l'accueil ni les index : courses de courses.json")
    ap.add_argument("--garder-html", action="store_true", help="garde les pages lues (gzip, cache/) : relecture sans requête")
    ap.add_argument("--decouverte-seule", action="store_true", help="ne lit que l'accueil et les index")
    a = ap.parse_args()
    if a.test:
        _tests()
        return 0
    lancer(a.sortie, a.avant, a.depuis, a.courses.split(","), a.sections.split(","), a.relire, a.budget_min,
           a.decouverte_seule, a.max_requetes, a.sans_decouverte, a.garder_html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
