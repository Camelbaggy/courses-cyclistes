#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CyclingRanking (cyclingranking.com) : vue d'ensemble des séries de courses et calendriers annuels 1869-2008 (collecteur,
étape 1 : pas d'intégration, ni résultats, ni équipes, ni fiches coureurs).

ACCORD : le 19/11/2026, l'auteur du site (Stephan van Uijtregt) a donné au propriétaire du projet son accord pour lire le
site par programme et afficher ses données, avec le crédit « CyclingRanking » (https://www.cyclingranking.com). Étude :
docs/recherche/cyclingranking_collecte.md. Le site est une COMPILATION (Mémoire du Cyclisme, Museo, CQ Ranking, PCS…) : il ne
remplace pas nos sources, il apporte un NIVEAU par édition (étoiles 0-5, code de challenge) pour 1869-1998.

Politesse : robots.txt (19/11/2026, bloc `User-agent: *`) = `Crawl-Delay: 20` (respecté : `PAUSE_S` 21), interdits `/cyclist*`,
`/riders/search`, `/teams/search`, `/races/search`, `*?highlight=*`, `*&highlight=*` (`chemin_autorise` vérifie chaque URL avant la
requête). User-Agent « courses-cyclistes (accord CyclingRanking) ». Seules deux familles d'URL sont demandées : `/races` et
`/races/<année>` ; les liens lus dans les pages (historique d'une série, édition, étapes, fiche coureur) sont GARDÉS comme texte,
JAMAIS suivis. Aucune page demandée deux fois : chaque page lue est écrite en gzip dans `cache/` et relue de là (`--relire` pour
forcer) ; un calendrier écrit n'est jamais redemandé. Hôte abandonné (403 / 429 / défi anti-robot : `netutil.hote_bloque`) ou 8
échecs de suite : le passage s'arrête net.

Règle cardinale du projet : aucune valeur inventée. Une valeur absente reste absente ; un format inconnu est conservé brut et compté.

Pages (rendues côté serveur, HTML décodé avec `html.unescape`) :
  - `/races` : une page (~1,7 Mo), séries groupées par pays (ligne d'en-tête avec drapeau), colonnes Race (lien
    `/races/<slug>/history`) | étoiles (`cr-race-category-small-N`, étoile « actuelle ou dominante » de la série : lire les étoiles de
    l'ÉDITION dans le calendrier de l'année) | From (lien `/races/<année>/<slug>`) | To. -> `series.json`.
  - `/races/<année>` : « Season Calendar <année> », tableau par mois (lignes d'en-tête de mois ignorées), 5 cellules : date (`jj/mm` ou
    `jj/mm - jj/mm`, année = celle de la page ; fin < début = fin l'année suivante, comptée) | nom (drapeau du pays de la course =
    pays de départ, lien `/races/<année>/<slug>`, puis éventuellement `(<abbr title="Coupe du Monde">CdM</abbr>)` ou `(<span>1.HC</span>)`
    = code de challenge ou classe UCI) | lien `stages` (courses par étapes) | vainqueur (drapeau + lien `/rider/<id>/<slug>`) | étoiles
    de l'édition. -> `calendriers/<année>.json`.
  Pays : le code du drapeau du site (ISO 3166-1 alpha-2 minuscule, `ioc` = « World ») est gardé brut (`pays_site`, nom anglais du
  drapeau `pays_nom`) ; `pays` = code 3 lettres canonique SEULEMENT quand le drapeau correspond à un pays existant
  (`netutil.FLAG_CODES` inversé) ; drapeau inconnu ou pays disparu : `pays` absent, compté (codes d'époque : décision du propriétaire du
  18/11/2026, jamais convertis ; les drapeaux d'époque éventuels sont à mesurer sur les vraies pages).

Sortie (défaut `ARCHIVES_DIR/sources/cyclingranking/`) : `series.json`, `calendriers/<année>.json`, `etat.json`
(`{"termine", "calendriers_restants"}`, sans horodatage : lu par un workflow d'auto-relance), `cache/`.

    python cyclingranking.py --sortie DOSSIER [--avant 2009] [--depuis 1869] [--relire] [--budget-min N] [--max-requetes N]
    python cyclingranking.py --test            # tests sans réseau (pages réelles allégées de tools/fixtures/cyclingranking/)
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
import tempfile
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import netutil

BASE = "https://www.cyclingranking.com"
USER_AGENT = "courses-cyclistes (accord CyclingRanking)"
HOTE = "www.cyclingranking.com"
PAUSE_S = 21.0                     # Crawl-Delay: 20 déclaré par robots.txt, respecté malgré l'accord (marge de 1 s)
netutil.HOST_DELAYS[HOTE] = PAUSE_S
DELAI_LECTURE_S = 60.0             # délai de lecture d'une page (/races pèse ~1,7 Mo)
ECHECS_DE_SUITE_MAX = 8            # abandon propre du passage

DEPUIS_DEFAUT = 1869               # premier calendrier du site
AVANT_DEFAUT = 2009                # années <= 2008 (l'UCI DataRide couvre la suite)
ARCHIVES_DIR = os.environ.get("ARCHIVES_DIR") or os.path.join("data", "archives")
SORTIE_DEFAUT = os.path.join(ARCHIVES_DIR, "sources", "cyclingranking")
RACINE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(RACINE, "tools", "fixtures", "cyclingranking")

# Chemins interdits par robots.txt (bloc `User-agent: *`, 19/11/2026) ; `*` = suite quelconque. Vérifiés par le test contre la copie
# réelle `tools/fixtures/cyclingranking/robots.txt`.
INTERDITS = ("/cyclist", "/riders/search", "/teams/search", "/races/search", "/*?highlight=*", "/*&highlight=*")


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


def _lignes(page: str) -> List[str]:
    return re.findall(r"(?s)<tr[^>]*>.*?</tr>", page)


def _inverse_drapeaux() -> Dict[str, str]:
    """Code drapeau flagcdn -> code pays 3 lettres (le premier de `netutil.FLAG_CODES` : SVN avant SLO)."""
    inv: Dict[str, str] = {}
    for code3, flag in netutil.FLAG_CODES.items():
        inv.setdefault(flag, code3)
    return inv


_INV: Optional[Dict[str, str]] = None


def pays_du_drapeau(flag: Optional[str]) -> Optional[str]:
    """Code drapeau du site (`fr`, `gb-eng`) -> code 3 lettres d'un pays EXISTANT, sinon None (`ioc`, drapeau inconnu ou d'époque)."""
    global _INV
    if _INV is None:
        _INV = _inverse_drapeaux()
    return _INV.get((flag or "").strip().lower())


def _drapeau(fragment: str) -> Tuple[Optional[str], Optional[str]]:
    """(code du drapeau, nom anglais du drapeau) du premier `<div class="flag flag-xx" title="…">` du fragment."""
    m = re.search(r'<div class="flag flag-([A-Za-z0-9-]+)"(?: title="([^"]*)")?', fragment)
    if not m:
        return None, None
    return m.group(1).lower(), (_html.unescape(m.group(2)) if m.group(2) else None)


def _champs_pays(fragment: str, comptes: Optional[Dict[str, int]]) -> Dict[str, Any]:
    flag, nom = _drapeau(fragment)
    out: Dict[str, Any] = {}
    if flag:
        out["pays_site"] = flag
        if nom:
            out["pays_nom"] = nom
        p = pays_du_drapeau(flag)
        if p:
            out["pays"] = p
        elif comptes is not None and flag != "ioc":
            comptes[flag] = comptes.get(flag, 0) + 1
    return out


def etoiles(fragment: str) -> Optional[int]:
    """Étoiles 0-5 (classe `cr-race-category-small-N`), None si le badge manque ou si le nombre d'étoiles pleines le contredit."""
    m = re.search(r'cr-race-category-small-(\d)\b', fragment)
    if not m:
        return None
    n = int(m.group(1))
    m2 = re.search(r'(?s)<span class="cr-race-stars">(.*?)</span>', fragment)
    if m2 and len(re.findall(r'fa-star"', m2.group(1))) != n:
        return None
    return n


def dates_course(brut: str, annee: int) -> Tuple[Optional[str], Optional[str], bool]:
    """`jj/mm` ou `jj/mm - jj/mm` + année de la page -> (début, fin, à cheval) en AAAA-MM-JJ ; fin < début : fin l'année suivante
    (à cheval = True). Format ou date impossible : (None, None, False), la valeur brute reste dans `date_brut`."""
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})(?:\s*-\s*(\d{1,2})/(\d{1,2}))?\s*", brut or "")
    if not m:
        return None, None, False
    try:
        debut = datetime.date(annee, int(m.group(2)), int(m.group(1)))
        if m.group(3) is None:
            return debut.isoformat(), debut.isoformat(), False
        fin = datetime.date(annee, int(m.group(4)), int(m.group(3)))
        cheval = False
        if fin < debut:
            fin = datetime.date(annee + 1, int(m.group(4)), int(m.group(3)))
            cheval = True
        return debut.isoformat(), fin.isoformat(), cheval
    except ValueError:
        return None, None, False


def lire_calendrier(page: str, annee: int, stats: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
    """Calendrier d'une année -> liste des éditions, ou None si la page n'est pas le calendrier demandé (titre « Season Calendar
    <année> » absent : page d'erreur, autre année) : rien n'est alors écrit. `stats` : compteurs de la synthèse."""
    st = stats if stats is not None else {}
    m = re.search(r"Season Calendar\s+(\d{4})", _txt(page))
    if not m or int(m.group(1)) != annee:
        return None
    pays_inconnus = st.setdefault("drapeaux_inconnus", {})
    courses: List[Dict[str, Any]] = []
    for tr in _lignes(page):
        cel = _cellules(tr)
        if not cel or (len(cel) == 1 and "colspan" in tr):
            continue                                   # en-tête de mois (<td colspan="5">) ou ligne sans cellule
        if len(cel) != 5:
            st["lignes_illisibles"] = st.get("lignes_illisibles", 0) + 1
            continue
        mnom = re.search(r'<a href="/races/(\d{4})/([^"/?#]+)"[^>]*>(.*?)</a>', cel[1], re.S)
        if not mnom:
            st["lignes_illisibles"] = st.get("lignes_illisibles", 0) + 1
            continue
        if int(mnom.group(1)) != annee:
            st["liens_autre_annee"] = st.get("liens_autre_annee", 0) + 1
        slug = mnom.group(2)
        date_brut = _txt(cel[0])
        debut, fin, cheval = dates_course(date_brut, annee)
        if debut is None:
            st["dates_illisibles"] = st.get("dates_illisibles", 0) + 1
        if cheval:
            st["dates_a_cheval"] = st.get("dates_a_cheval", 0) + 1
        c: Dict[str, Any] = {"slug": slug, "nom": _txt(mnom.group(3)), "date_brut": date_brut}
        if debut:
            c["date_debut"], c["date_fin"] = debut, fin
        c.update(_champs_pays(cel[1], pays_inconnus))
        mcode = re.search(r"\(\s*<(abbr|span)([^>]*)>([^<]*)</\1>\s*\)", cel[1])
        if mcode and _txt(mcode.group(3)):
            c["code"] = _txt(mcode.group(3))
            mt = re.search(r'title="([^"]*)"', mcode.group(2))
            if mt:
                c["code_nom"] = _html.unescape(mt.group(1))
        mst = re.search(r'<a href="(/races/\d{4}/[^"]+/stages)"', cel[2])
        c["etapes"] = bool(mst)
        e = etoiles(cel[4])
        if e is None:
            st["etoiles_illisibles"] = st.get("etoiles_illisibles", 0) + 1
        else:
            c["etoiles"] = e
        mv = re.search(r'<a href="/rider/(\d+)/([^"/?#]*)"[^>]*>(.*?)</a>', cel[3], re.S)
        if mv:
            v: Dict[str, Any] = {"id": int(mv.group(1)), "nom": _txt(mv.group(3)),
                                 "url": BASE + "/rider/%s/%s" % (mv.group(1), mv.group(2))}
            v.update(_champs_pays(cel[3], pays_inconnus))
            c["vainqueur"] = v
        else:
            st["sans_vainqueur"] = st.get("sans_vainqueur", 0) + 1
        c["url"] = BASE + "/races/%s/%s" % (mnom.group(1), slug)
        if mst:
            c["url_etapes"] = BASE + mst.group(1)
        courses.append(c)
    st["codes"] = st.get("codes", {})
    for c in courses:
        if c.get("code"):
            st["codes"][c["code"]] = st["codes"].get(c["code"], 0) + 1
    return courses


def lire_apercu(page: str, stats: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Page `/races` -> {slug de série: {nom, etoiles, pays_site, pays_nom, pays, premiere_annee, derniere_annee, url_historique,
    url_premiere, url_derniere}} (lien de l'historique : jamais suivi). Slug dupliqué (rare) : la 1re ligne est gardée et la suivante comptée."""
    st = stats if stats is not None else {}
    pays_inconnus = st.setdefault("drapeaux_inconnus", {})
    series: Dict[str, Dict[str, Any]] = {}
    courant: Dict[str, Any] = {}
    for tr in _lignes(page):
        mth = re.search(r'(?s)<th colspan="\d+">(.*?)</th>', tr)
        if mth:                                         # ligne de groupe : drapeau + nom du pays
            courant = _champs_pays(mth.group(1), None)
            continue
        cel = _cellules(tr)
        if len(cel) != 4:
            continue
        mh = re.search(r'<a href="/races/([^"/?#]+)/history"[^>]*>(.*?)</a>', cel[0], re.S)
        if not mh:
            continue
        slug = mh.group(1)
        if slug in series:
            st["series_doublons"] = st.get("series_doublons", 0) + 1
            continue
        s: Dict[str, Any] = {"nom": _txt(mh.group(2)), "url_historique": BASE + "/races/%s/history" % slug}
        s.update(courant)
        if courant.get("pays_site") and "pays" not in courant and courant["pays_site"] != "ioc":
            pays_inconnus[courant["pays_site"]] = pays_inconnus.get(courant["pays_site"], 0) + 1
        e = etoiles(cel[1])
        if e is None:
            st["etoiles_illisibles"] = st.get("etoiles_illisibles", 0) + 1
        else:
            s["etoiles"] = e
        for cle, cell in (("premiere_annee", cel[2]), ("derniere_annee", cel[3])):
            ma = re.search(r'<a href="(/races/(\d{4})/[^"]+)"', cell)
            if ma:
                s[cle] = int(ma.group(2))
                s["url_" + cle.split("_")[0]] = BASE + ma.group(1)
        series[slug] = s
    return series


def chemin_autorise(url_ou_chemin: str) -> bool:
    """Vrai si le chemin n'est interdit par aucune règle `Disallow` de `User-agent: *` (préfixe, `*` = suite quelconque)."""
    u = urllib.parse.urlparse(url_ou_chemin)
    cible = u.path + ("?" + u.query if u.query else "")
    for regle in INTERDITS:
        motif = "".join(".*" if ch == "*" else re.escape(ch) for ch in regle)
        if re.match(motif, cible):
            return False
    return True


# --------------------------------------------------------------------------------------------------
# Réseau, stockage, reprise
# --------------------------------------------------------------------------------------------------

class Session:
    """Requêtes polies (pause par hôte, budget, compteur). Chaque page lue est écrite en gzip dans `cache/` et relue de là."""

    def __init__(self, sortie: str, budget_min: float = 0.0, max_pages: int = 0, relire: bool = False):
        self.sortie = sortie
        self.relire = relire
        self.t0 = time.monotonic()
        self.budget_s = budget_min * 60 if budget_min else 0.0
        self.max_pages = max_pages
        self.requetes = 0
        self.echecs = 0
        self.echecs_de_suite = 0
        self.arret = False                 # hôte abandonné ou échecs de suite : plus aucune requête ce passage
        self.dernier_journal = self.t0

    def epuise(self) -> bool:
        """Budget de temps, plafond de requêtes ou abandon atteint."""
        if self.arret:
            return True
        if self.budget_s and time.monotonic() - self.t0 >= self.budget_s:
            return True
        return bool(self.max_pages) and self.requetes >= self.max_pages

    def _telecharger(self, url: str) -> Optional[str]:
        return netutil.fetch_text(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, timeout=DELAI_LECTURE_S)

    def page(self, chemin: str) -> Optional[str]:
        """Page du site (`/races`, `/races/1995`) : depuis le cache si présente (sauf `relire`), sinon une requête."""
        url = BASE + chemin
        assert chemin_autorise(chemin) and re.fullmatch(r"/races(/\d{4})?", chemin), "chemin non prévu : %s" % chemin
        cache = os.path.join(self.sortie, "cache", hashlib.sha1(url.encode()).hexdigest()[:16] + ".html.gz")
        if not self.relire and os.path.exists(cache):
            with gzip.open(cache, "rt", encoding="utf-8") as f:
                return f.read()
        if self.epuise():
            return None
        self.requetes += 1
        texte = self._telecharger(url)
        if texte is None:
            self.echecs += 1
            self.echecs_de_suite += 1
            if netutil.hote_bloque(url) or self.echecs_de_suite >= ECHECS_DE_SUITE_MAX:
                self.arret = True
                print("[CYCLINGRANKING] [WARN] passage arrêté (%s)" % ("hôte abandonné" if netutil.hote_bloque(url) else "%d échecs de suite" % self.echecs_de_suite))
            return None
        self.echecs_de_suite = 0
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with gzip.open(cache, "wt", encoding="utf-8") as f:
            f.write(texte)
        return texte

    def journal(self, message: str, force: bool = False) -> None:
        if force or time.monotonic() - self.dernier_journal >= 300:
            self.dernier_journal = time.monotonic()
            print("[CYCLINGRANKING] %s (%d requêtes, %.1f min)" % (message, self.requetes, (time.monotonic() - self.t0) / 60))


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


def chemin_calendrier(sortie: str, annee: int) -> str:
    return os.path.join(sortie, "calendriers", "%d.json" % annee)


def lancer(sortie: str, avant: int = AVANT_DEFAUT, depuis: int = DEPUIS_DEFAUT, relire: bool = False, budget_min: float = 0.0,
           max_pages: int = 0, session: Optional[Session] = None) -> Dict[str, Any]:
    """`/races` (une page) puis les calendriers de `avant - 1` à `depuis` (du plus récent au plus ancien). Reprenable : un fichier
    écrit n'est jamais redemandé (sans `relire`). Écrit `etat.json`. `session` : session déjà construite (tests)."""
    sess = session or Session(sortie, budget_min, max_pages, relire)
    resume: Dict[str, Any] = {"calendriers_lus": 0, "calendriers_deja": 0, "calendriers_illisibles": 0, "editions": 0}
    stats: Dict[str, Any] = {}
    chemin_series = os.path.join(sortie, "series.json")
    series_restantes = 0
    if os.path.exists(chemin_series) and not relire:
        resume["series_deja"] = True
    else:
        page = sess.page("/races")
        series = lire_apercu(page, stats) if page else {}
        if series:
            _ecrire_json(chemin_series, {"series": series}, compact=True)
            resume["series"] = len(series)
            sess.journal("séries lues")
        else:
            series_restantes = 1
            if page:
                resume["series_illisibles"] = True
    restants = 0
    for annee in range(avant - 1, depuis - 1, -1):
        chemin = chemin_calendrier(sortie, annee)
        if os.path.exists(chemin) and not relire:
            resume["calendriers_deja"] += 1
            continue
        page = sess.page("/races/%d" % annee)
        if page is None:
            restants += 1
            continue
        courses = lire_calendrier(page, annee, stats)
        if courses is None:
            resume["calendriers_illisibles"] += 1
            restants += 1
            print("[CYCLINGRANKING] [WARN] %d : page qui n'est pas le calendrier demandé, rien écrit" % annee)
            continue
        _ecrire_json(chemin, {"annee": annee, "courses": courses}, compact=True)
        resume["calendriers_lus"] += 1
        resume["editions"] += len(courses)
        sess.journal("calendrier %d lu (%d éditions)" % (annee, len(courses)))
    restants += series_restantes
    resume["stats"] = stats
    resume["echecs"] = sess.echecs
    resume["requetes"] = sess.requetes
    resume["duree_min"] = round((time.monotonic() - sess.t0) / 60, 1)
    resume["budget_epuise"] = sess.epuise()
    # `termine` seulement pour la plage complète par défaut : un essai partiel (--depuis / --avant) ne clôt rien
    termine = bool(not restants and avant >= AVANT_DEFAUT and depuis <= DEPUIS_DEFAUT)
    _ecrire_json(os.path.join(sortie, "etat.json"), {"termine": termine, "calendriers_restants": restants})
    resume["calendriers_restants"], resume["termine"] = restants, termine
    sess.journal("synthèse : %s" % json.dumps(resume, ensure_ascii=False, sort_keys=True), force=True)
    return resume


# --------------------------------------------------------------------------------------------------
# Tests sans réseau (pages réelles allégées de tools/fixtures/cyclingranking/)
# --------------------------------------------------------------------------------------------------

def _fixture(nom: str) -> str:
    with open(os.path.join(FIXTURES, nom), encoding="utf-8") as f:
        return f.read()


def _tests() -> None:
    # robots.txt réel : toutes nos règles y figurent (bloc User-agent: *), nos deux familles d'URL sont autorisées
    bloc = _fixture("robots.txt").split("\n\n")[0]
    assert "User-agent: *" in bloc and "Crawl-Delay: 20" in bloc and PAUSE_S > 20
    for regle in INTERDITS:
        assert "Disallow: " + regle in bloc, regle
    assert chemin_autorise("/races") and chemin_autorise("/races/1995") and chemin_autorise("https://www.cyclingranking.com/races/1869")
    assert not chemin_autorise("/cyclist/1") and not chemin_autorise("/cyclists") and not chemin_autorise("/races/search?q=a")
    assert not chemin_autorise("/races/1995?highlight=3") and not chemin_autorise("/races/1995?page=2&highlight=3")
    assert chemin_autorise("/rider/4500/laurent-jalabert")

    # dates
    assert dates_course("18/03", 1995) == ("1995-03-18", "1995-03-18", False)
    assert dates_course("01/02 - 05/02", 1995) == ("1995-02-01", "1995-02-05", False)
    assert dates_course("29/12 - 02/01", 1994) == ("1994-12-29", "1995-01-02", True)
    assert dates_course("31/02", 1995) == (None, None, False) and dates_course("mars", 1995) == (None, None, False)
    assert dates_course("29/02", 1900) == (None, None, False) and dates_course("29/02", 1904)[0] == "1904-02-29"

    # pays : drapeau -> code 3 lettres d'un pays existant seulement
    assert pays_du_drapeau("fr") == "FRA" and pays_du_drapeau("si") == "SVN" and pays_du_drapeau("gb-eng") == "ENG"
    assert pays_du_drapeau("ioc") is None and pays_du_drapeau("su") is None and pays_du_drapeau(None) is None

    # calendrier 1995 : 19 éditions, Milan-San Remo = CdM, 5 étoiles, vainqueur Jalabert
    st: Dict[str, Any] = {}
    c95 = lire_calendrier(_fixture("calendrier_1995.html"), 1995, st)
    assert c95 is not None and len(c95) == 19, len(c95 or [])
    assert lire_calendrier(_fixture("calendrier_1995.html"), 1996) is None          # titre d'une autre année : refusé
    ms = [c for c in c95 if c["slug"] == "milano-sanremo"]
    assert len(ms) == 1
    ms = ms[0]
    assert ms["nom"] == "Milano - Sanremo" and ms["code"] == "CdM" and ms["code_nom"] == "Coupe du Monde" and ms["etoiles"] == 5
    assert ms["date_debut"] == ms["date_fin"] == "1995-03-18" and ms["pays"] == "ITA" and ms["pays_site"] == "it" and ms["pays_nom"] == "Italy"
    assert ms["etapes"] is False and "url_etapes" not in ms and ms["url"] == BASE + "/races/1995/milano-sanremo"
    assert ms["vainqueur"] == {"id": 4500, "nom": "Laurent JALABERT", "url": BASE + "/rider/4500/laurent-jalabert",
                               "pays_site": "fr", "pays_nom": "France", "pays": "FRA"}, ms["vainqueur"]
    eb = [c for c in c95 if c["slug"] == "etoile-de-besseges"][0]
    assert eb["nom"] == "Etoile de Bessèges" and eb["etapes"] is True and eb["url_etapes"] == BASE + "/races/1995/etoile-de-besseges/stages"
    assert eb["date_debut"] == "1995-02-01" and eb["date_fin"] == "1995-02-05" and eb["vainqueur"]["pays"] == "UKR"
    assert [c for c in c95 if c["slug"] == "gp-d-ouverture-la-marseillaise"][0]["nom"] == "G.P. d'Ouverture - La Marseillaise"
    assert [c for c in c95 if c["slug"] == "circuito-de-getxo"][0]["etoiles"] == 1
    assert st["codes"] == {"CdM": 1} and not st.get("lignes_illisibles") and not st.get("etoiles_illisibles"), st
    assert all("etoiles" in c and "vainqueur" in c and "date_debut" in c for c in c95)
    assert len({c["slug"] for c in c95}) == 19

    # 1930 : pas de code ; étapes ; 2005 : classes UCI en <span>, étoiles selon le niveau
    c30 = lire_calendrier(_fixture("calendrier_1930.html"), 1930)
    assert c30 is not None and len(c30) == 8 and not any("code" in c for c in c30)
    assert [c for c in c30 if c["slug"] == "milano-sanremo"][0]["vainqueur"]["nom"] == "Michele MARA"
    assert [c for c in c30 if c["slug"] == "gp-de-l-echo-d-alger"][0]["pays_site"] == "dz"
    st5: Dict[str, Any] = {}
    c05 = lire_calendrier(_fixture("calendrier_2005.html"), 2005, st5)
    assert c05 is not None and len(c05) == 12 and st5["codes"], st5
    tl = [c for c in c05 if c["slug"] == "trofeo-laigueglia"][0]
    assert tl["code"] == "1.HC" and "code_nom" not in tl and tl["etoiles"] == 2 and tl["vainqueur"]["nom"] == "Kim KIRCHEN"

    # vue d'ensemble /races
    sta: Dict[str, Any] = {}
    ser = lire_apercu(_fixture("apercu_courses.html"), sta)
    assert len(ser) > 5 and "challenge-desgrange-colombo" in ser, len(ser)
    a = ser["african-continental-championships-road-race"]
    assert a["nom"] == "African Continental Championships Road Race" and a["etoiles"] == 2 and a["pays_site"] == "ioc" and a["pays_nom"] == "World"
    assert "pays" not in a and a["premiere_annee"] == 2001 and a["derniere_annee"] == 2024
    assert a["url_historique"] == BASE + "/races/african-continental-championships-road-race/history"
    assert ser["challenge-desgrange-colombo"]["nom"] == 'Challenge "Desgrange-Colombo"'
    assert all("etoiles" in s and "premiere_annee" in s for s in ser.values()) and not sta.get("etoiles_illisibles"), sta

    # session : cache, plafond, abandon, reprise ; aucune page demandée deux fois
    pages = {"/races": _fixture("apercu_courses.html"), "/races/1995": _fixture("calendrier_1995.html"),
             "/races/1930": _fixture("calendrier_1930.html"), "/races/2005": _fixture("calendrier_2005.html")}

    class Faux(Session):
        demandes: List[str] = []

        def _telecharger(self, url: str) -> Optional[str]:
            chemin = url[len(BASE):]
            Faux.demandes.append(chemin)
            return pages.get(chemin)

    with tempfile.TemporaryDirectory() as d:
        r = lancer(d, 2006, 1995, session=Faux(d))
        assert r["series"] == len(ser), r
        # 8 échecs de suite (2004..1997) : passage arrêté net, 1996 et la page 1995 (pourtant disponible) ne sont pas demandées
        assert Faux.demandes == ["/races", "/races/2005"] + ["/races/%d" % a for a in range(2004, 1996, -1)], Faux.demandes
        assert r["budget_epuise"] and r["calendriers_lus"] == 1 and r["editions"] == 12 and r["calendriers_restants"] == 10, r
        etat = json.load(open(os.path.join(d, "etat.json")))
        assert etat["termine"] is False and etat["calendriers_restants"] > 0, etat
        assert os.path.exists(os.path.join(d, "series.json")) and os.path.exists(chemin_calendrier(d, 2005))
        # reprise : séries et 2005 ne sont pas redemandés ; 1995 est lu
        Faux.demandes = []
        r1 = lancer(d, 2006, 1995, max_pages=0, session=Faux(d))
        assert "/races" not in Faux.demandes and "/races/2005" not in Faux.demandes and Faux.demandes[:2] == ["/races/2004", "/races/2003"], Faux.demandes
        assert r1["calendriers_lus"] == 0 and r1["calendriers_deja"] == 1 and r1["requetes"] == 8, r1
        Faux.demandes = []
        r1 = lancer(d, 1996, 1995, session=Faux(d))
        assert Faux.demandes == ["/races/1995"] and r1["calendriers_lus"] == 1 and r1["editions"] == 19 and r1["calendriers_restants"] == 0, r1
        # relecture du cache sans requête (--relire : requête) ; le contenu écrit est déterministe
        brut1 = open(chemin_calendrier(d, 2005), "rb").read()
        Faux.demandes = []
        lancer(d, 2006, 2005, session=Faux(d))
        assert Faux.demandes == [] and open(chemin_calendrier(d, 2005), "rb").read() == brut1
        Faux.demandes = []
        lancer(d, 2006, 2005, relire=True, session=Faux(d, relire=True))
        assert Faux.demandes == ["/races", "/races/2005"] and open(chemin_calendrier(d, 2005), "rb").read() == brut1
        # plafond de requêtes
        d2 = os.path.join(d, "p")
        Faux.demandes = []
        r2 = lancer(d2, 2006, 1995, max_pages=2, session=Faux(d2, 0, 2))
        assert len(Faux.demandes) == 2 and not r2["termine"]
        # plage complète terminée : termine vrai seulement avec 1869-2008 entièrement lus
        d3 = os.path.join(d, "t")
        pages.update({"/races/%d" % a: pages["/races/1930"].replace("Season Calendar 1930", "Season Calendar %d" % a)
                      for a in range(DEPUIS_DEFAUT, AVANT_DEFAUT) if "/races/%d" % a not in pages})
        r3 = lancer(d3, AVANT_DEFAUT, DEPUIS_DEFAUT, session=Faux(d3))
        assert r3["termine"] and r3["calendriers_restants"] == 0 and r3["calendriers_lus"] == 140, r3
        assert json.load(open(os.path.join(d3, "etat.json"))) == {"termine": True, "calendriers_restants": 0}
        # une page qui n'est pas le calendrier de l'année : rien écrit, annoncé restant
        d4 = os.path.join(d, "u")
        pages["/races/1931"] = pages["/races/1930"]
        r4 = lancer(d4, 1932, 1931, session=Faux(d4))
        assert r4["calendriers_illisibles"] == 1 and not os.path.exists(chemin_calendrier(d4, 1931))
        # hôte abandonné
        class Bloque(Session):
            def _telecharger(self, url: str) -> Optional[str]:
                netutil._blocked_hosts.add(HOTE)
                return None
        d5 = os.path.join(d, "b")
        try:
            r5 = lancer(d5, 2006, 1995, session=Bloque(d5))
            assert r5["requetes"] == 1 and r5["budget_epuise"] and not r5["termine"], r5
        finally:
            netutil._blocked_hosts.discard(HOTE)
    print("cyclingranking : tests OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--test", action="store_true", help="tests sans réseau")
    ap.add_argument("--sortie", default=SORTIE_DEFAUT, help="dossier de sortie (défaut : ARCHIVES_DIR/sources/cyclingranking)")
    ap.add_argument("--avant", type=int, default=AVANT_DEFAUT, help="années strictement avant cette année (défaut 2009)")
    ap.add_argument("--depuis", type=int, default=DEPUIS_DEFAUT, help="années à partir de celle-ci (défaut 1869)")
    ap.add_argument("--relire", action="store_true", help="redemander aussi les pages déjà lues (cache et fichiers écrits)")
    ap.add_argument("--budget-min", type=float, default=0.0, help="budget de temps en minutes (0 = illimité)")
    ap.add_argument("--max-requetes", type=int, default=0, help="plafond de requêtes du passage (0 = illimité ; essais)")
    a = ap.parse_args()
    if a.test:
        _tests()
        return 0
    lancer(a.sortie, a.avant, a.depuis, a.relire, a.budget_min, a.max_requetes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
