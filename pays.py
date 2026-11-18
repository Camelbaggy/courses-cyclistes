#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codes pays des sources avant 2009 : pays disparus (codes ET drapeaux de l'époque) et normalisation des codes bruts.

Décision du propriétaire (18/11/2026) : pour un pays disparu (URSS, RDA, RFA, Tchécoslovaquie, Yougoslavie, CEI…) on garde
le code et le drapeau DE L'ÉPOQUE ; jamais de conversion vers un pays actuel (les `successeurs` du fichier
`pays_historiques.json` sont une information, pas une règle). Un code brut inconnu reste vide et compté.

`pays_historiques.json` (racine, versionné) :
  - `pays` : pays disparus, clé = code canonique (CIO / UCI d'époque : URS, GDR, FRG, TCH, YUG, SCG, EUN, AHO, ZAI, BOH, VSO),
    avec `nom` (français), `periode`, `successeurs`, `drapeau` {fichier Wikimedia Commons, a_verifier, licence} ;
  - `codes_actuels_supplementaires` : codes CIO / UCI de pays existants absents de `netutil.FLAG_CODES` (code drapeau flagcdn) ;
  - `sources.<source>.conversions` : code brut du site -> code canonique (texte, ou {"code", "jusqu_a"} : valable seulement
    pour une année <= `jusqu_a` ; au-delà, `apres` s'il est donné (correction validée), sinon le code est ambigu et reste vide) ; `identite` : un code brut déjà valide
    (netutil.FLAG_CODES, supplémentaires ou pays disparus) est accepté tel quel (Museo, the-sports, CQ Ranking ; pas Mémoire du
    Cyclisme dont les parenthèses mêlent pays et clubs en casse mixte).

La conversion ne dépend que du code brut (la source a déjà choisi RFA avant 1990, ALL / GER après), sauf l'exception
explicite `jusqu_a` (Museo et Mémoire du Cyclisme réutilisent TCH / Tch pour des Tchèques après 1992 : convertis en CZE,
`apres`, décision du propriétaire du 18/11/2026).

Drapeaux : `drapeau(code)` rend le code flagcdn (« fr ») d'un pays existant, ou « h-urs » pour un pays disparu ; index.html
(`flag()`) sait afficher « h-xxx » avec le fichier Commons (`Special:FilePath/<fichier>?width=40`, drapeaux dans le domaine public :
aucun crédit requis).

Les données déjà collectées gardent le code brut (`pays_site` Mémoire du Cyclisme, `nat_site` the-sports / Museo, `nat` Museo avant
cette table, 3e colonne des lignes et `nationalite` des fiches CQ Ranking) : `pays_ligne` refait la normalisation à la lecture.

Tests : python pays.py --test
"""
import json
import os
import re
import sys
import urllib.parse
from typing import Any, Dict, Optional

import netutil

RACINE = os.path.dirname(os.path.abspath(__file__))
FICHIER = os.path.join(RACINE, "pays_historiques.json")
SOURCES = ("mdc", "museo", "thesports", "cqranking")

_TABLE: Optional[Dict[str, Any]] = None


def table() -> Dict[str, Any]:
    global _TABLE
    if _TABLE is None:
        with open(FICHIER, encoding="utf-8") as f:
            _TABLE = json.load(f)
    return _TABLE


def code_valide(code: Optional[str]) -> bool:
    """Code canonique connu : pays existant (FLAG_CODES + supplémentaires) ou disparu."""
    if not code:
        return False
    t = table()
    return code in netutil.FLAG_CODES or code in t["codes_actuels_supplementaires"] or code in t["pays"]


def est_historique(code: Optional[str]) -> bool:
    return bool(code) and code in table()["pays"]


def pays_normalise(code_brut: Optional[str], source: str, annee: Optional[int] = None) -> Optional[str]:
    """Code brut d'un site -> code canonique (existant ou d'époque), ou None (code inconnu : l'appelant le compte).

    `annee` (année de l'édition) ne sert qu'aux codes ambigus (`jusqu_a`) : sans année, la conversion se fait sur le code seul."""
    if source not in SOURCES:
        raise ValueError("source inconnue : %r" % (source,))
    brut = (code_brut or "").strip()
    if not brut:
        return None
    cfg = table()["sources"][source]
    entree = cfg["conversions"].get(brut)
    if entree is not None:
        if isinstance(entree, dict):
            if annee is not None and annee > entree["jusqu_a"]:
                apres = entree.get("apres")      # code après `jusqu_a` (correction validée), sinon ambigu : vide
                return apres if apres and code_valide(apres) else None
            entree = entree["code"]
        return entree if code_valide(entree) else None
    if cfg.get("identite"):
        haut = brut.upper()
        if haut == brut and code_valide(haut):
            return haut
    return None


def compter_inconnu(stats: Dict[str, int], code_brut: str) -> None:
    """Ajoute un code brut inconnu au compteur `stats` (dictionnaire code -> effectif)."""
    stats[code_brut] = stats.get(code_brut, 0) + 1


def drapeau(code: Optional[str]) -> Optional[str]:
    """Code canonique -> code drapeau : flagcdn (« fr »), « h-urs » (pays disparu, fichier Commons), ou None."""
    if not code:
        return None
    t = table()
    if code in t["pays"]:
        return "h-" + code.lower()
    if code in netutil.FLAG_CODES:
        return netutil.FLAG_CODES[code]
    sup = t["codes_actuels_supplementaires"].get(code)
    return sup["flag"] if sup else None


def nom_historique(code: Optional[str]) -> Optional[str]:
    """Nom français d'un pays disparu (None pour un pays existant)."""
    p = table()["pays"].get(code or "")
    return p["nom"] if p else None


def url_drapeau(code: str, largeur: int = 40) -> Optional[str]:
    """URL Wikimedia Commons (redirection vers la vignette) du drapeau d'un pays disparu."""
    p = table()["pays"].get(code)
    if not p:
        return None
    nom = p["drapeau"]["fichier"].replace(" ", "_")
    return "https://commons.wikimedia.org/wiki/Special:FilePath/%s?width=%d" % (urllib.parse.quote(nom, safe="()_"), largeur)


def pays_ligne(source: str, ligne: Any, annee: Optional[int] = None) -> Optional[str]:
    """Code canonique d'une ligne DÉJÀ COLLECTÉE, refait à partir du code brut conservé (jamais du champ `nat` normalisé) :
    mdc `pays_site` ; museo `nat_site` (fichiers récents) sinon `nat` (brut avant la table) ; thesports `nat_site` ;
    cqranking : liste `lignes` du site (3e colonne) ou dict de fiche (`nationalite`)."""
    if isinstance(ligne, (list, tuple)):
        brut = ligne[2] if len(ligne) > 2 else None
    elif source == "mdc":
        brut = ligne.get("pays_site")
    elif source == "museo":
        brut = ligne.get("nat_site") or ligne.get("nat")
    elif source == "thesports":
        brut = ligne.get("nat_site")
    else:
        brut = ligne.get("nationalite") or ligne.get("nat")
    return pays_normalise(brut, source, annee)


# --------------------------------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------------------------------

def _tests() -> None:
    t = table()
    # structure
    for code, p in t["pays"].items():
        assert re.fullmatch(r"[A-Z]{3}", code) and p["nom"] and len(p["periode"]) == 2 and p["successeurs"], code
        assert p["drapeau"]["fichier"].endswith(".svg") and "a_verifier" in p["drapeau"], code
        assert code not in netutil.FLAG_CODES, code            # un pays disparu n'est pas un pays actuel
    for source, cfg in t["sources"].items():
        assert source in SOURCES, source
        for brut, canon in cfg["conversions"].items():
            c = canon["code"] if isinstance(canon, dict) else canon
            assert code_valide(c), (source, brut, c)
    for code, sup in t["codes_actuels_supplementaires"].items():
        assert code not in netutil.FLAG_CODES and re.fullmatch(r"[a-z]{2}", sup["flag"]), code
    # pays disparus : code d'époque, jamais de conversion
    assert pays_normalise("Rfa", "mdc") == "FRG" and pays_normalise("Rda", "mdc") == "GDR"
    assert pays_normalise("Urs", "mdc") == "URS" and pays_normalise("Urss", "mdc") == "URS"
    assert pays_normalise("Hon", "mdc") == "HUN" and pays_normalise("You", "mdc") == "YUG"
    assert pays_normalise("RFA", "museo") == "FRG" and pays_normalise("DDR", "museo") == "GDR"
    assert pays_normalise("URS", "museo") == "URS" and pays_normalise("YUG", "museo") == "YUG"
    assert pays_normalise("CSI", "museo") == "EUN" and pays_normalise("EUN", "thesports") == "EUN"
    assert pays_normalise("FDR", "thesports") == "FRG" and pays_normalise("DDR", "thesports") == "GDR"
    assert pays_normalise("ANT", "thesports") == "AHO" and pays_normalise("AHO", "cqranking") == "AHO"
    assert pays_normalise("ANT", "cqranking") == "ATG"             # même code brut, autre pays selon la source
    assert pays_normalise("SCG", "cqranking") == "SCG" and pays_normalise("ZAI", "thesports") == "ZAI"
    # codes propres aux sites -> code actuel
    assert [pays_normalise(c, "mdc") for c in ("Hol", "All", "Esp", "Sui", "Sue", "Afs", "Let")] == \
        ["NED", "GER", "ESP", "SUI", "SWE", "RSA", "LAT"]
    assert pays_normalise("SPA", "thesports") == "ESP" and pays_normalise("SWI", "thesports") == "SUI"
    assert pays_normalise("MAL", "thesports") == "MAS" and pays_normalise("SCO", "thesports") == "GBR"
    assert pays_normalise("INO", "thesports") == "INA" and pays_normalise("IRI", "cqranking") == "IRI"
    # identité : seulement pour les sources en codes CIO ; jamais pour Mémoire du Cyclisme (clubs, casse mixte)
    assert pays_normalise("ITA", "museo") == "ITA" and pays_normalise("BEL", "cqranking") == "BEL"
    assert pays_normalise("ITA", "mdc") is None and pays_normalise("ACBB", "mdc") is None and pays_normalise("CSI", "mdc") is None
    # inconnus : vides (jamais devinés)
    assert pays_normalise("APA", "museo") is None and pays_normalise("LIB", "cqranking") is None
    assert pays_normalise("", "museo") is None and pays_normalise(None, "mdc") is None and pays_normalise("xx", "thesports") is None
    # ambigu après 1992 : Tch / TCH
    assert pays_normalise("Tch", "mdc", 1991) == "TCH" and pays_normalise("Tch", "mdc", 1992) == "TCH"
    assert pays_normalise("Tch", "mdc", 2001) == "CZE" and pays_normalise("TCH", "museo", 2000) == "CZE"
    assert pays_normalise("TCH", "museo", 1993) == "CZE" and pays_normalise("TCH", "museo", 1992) == "TCH"
    assert pays_normalise("Tch", "mdc") == "TCH" and pays_normalise("TCH", "museo", None) == "TCH"
    assert pays_normalise("RFA", "museo", 1995) == "FRG"          # la conversion ne dépend pas de la date
    # drapeaux
    assert drapeau("FRA") == "fr" and drapeau("URS") == "h-urs" and drapeau("IRI") == "ir" and drapeau("XXX") is None
    assert nom_historique("GDR") == "République démocratique allemande (RDA)" and nom_historique("FRA") is None
    assert url_drapeau("URS") == "https://commons.wikimedia.org/wiki/Special:FilePath/Flag_of_the_Soviet_Union.svg?width=40"
    assert "%E2%80%93" in url_drapeau("SCG") and url_drapeau("FRA") is None
    # lecture de données déjà collectées (code brut conservé)
    assert pays_ligne("mdc", {"pays_site": "Rfa", "nat": "ALLEMAGNE"}, 1980) == "FRG"
    assert pays_ligne("museo", {"nat": "RFA"}) == "FRG" and pays_ligne("museo", {"nat_site": "CSI", "nat": "EUN"}) == "EUN"
    assert pays_ligne("thesports", {"nat_site": "SPA", "nat": "ESP"}) == "ESP"
    assert pays_ligne("cqranking", [1, 2694, "POR", "DUJ", "3h46'36\"", 0, 25]) == "POR"
    assert pays_ligne("cqranking", {"nationalite": "AHO"}) == "AHO"
    st: Dict[str, int] = {}
    compter_inconnu(st, "XYZ")
    compter_inconnu(st, "XYZ")
    assert st == {"XYZ": 2}
    # index.html : table DRAPEAUX_HIST identique au JSON
    chemin = os.path.join(RACINE, "index.html")
    if os.path.exists(chemin):
        html = open(chemin, encoding="utf-8").read()
        m = re.search(r"const DRAPEAUX_HIST = (\{.*?\});", html, flags=re.S)
        assert m, "DRAPEAUX_HIST absent d'index.html"
        js = json.loads(m.group(1))
        attendu = {c.lower(): {"nom": p["nom"], "fichier": p["drapeau"]["fichier"]} for c, p in t["pays"].items()}
        assert js == attendu, "DRAPEAUX_HIST d'index.html différent de pays_historiques.json"
    print("pays.py : tests OK (%d pays disparus, %s)" % (len(t["pays"]),
          ", ".join("%s %d conversions" % (s, len(c["conversions"])) for s, c in t["sources"].items())))


if __name__ == "__main__":
    if "--test" in sys.argv:
        _tests()
    else:
        print(__doc__)
