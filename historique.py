#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Historique de l'encyclopédie (palmarès de toute l'histoire des épreuves suivies, depuis Wikidata) : cache dans `entites/historique/`.

Wikidata est en CC0. Aucun fait n'est inventé : chaque donnée vient d'un élément Wikidata cité (`qid` de l'édition, `source_qid` côté entités) ;
une valeur absente reste absente ; un désaccord entre propriétés est CONSERVÉ avec ses deux valeurs, jamais tranché.

Fichiers de `ARCHIVES_DIR/entites/historique/` (écrits au fil de l'eau, une série à la fois, reprenables ; ce module n'écrit QUE là) :
    editions/<lettre>.json  {clé d'édition: [{annee, qid, date?, vainqueur?, podium, statut, detail?, wikipedia?, verifie, ...}]}
    coureurs.json           {QID: {nom, naissance?, naissance_precision?, deces?, deces_precision?, nationalite?, wikipedia?, rider_id?, verifie}}
    pays.json               {QID de pays: {code CIO (P984) | null, verifie}}
    non_personnes.json      {QID: date de vérification} (valeurs de P1346 qui ne sont pas des humains : équipes, ignorées)
    etat.json               {QID de série: {verifie, editions, cles}}

Modèle Wikidata (constaté, docs/recherche/historique_avant_2009.md) : une série = élément « course » ; CHAQUE ÉDITION est une instance de la série
(P31 = QID de la série, trouvée par CirrusSearch `haswbstatement:P31=<série>`, 500 résultats par requête). Date : P585, sinon P580 / P582, sinon
l'année lue dans le libellé (`annee_source: "libelle"`). Vainqueur et podium : P1346 répété avec le qualificatif P2501 = Q20882667 / Q20882668 /
Q20882669 (vainqueur / 2e / 3e du classement général). RÈGLES RETENUES (voir aussi docs/recherche/historique_avant_2009.md §9) :
- P1346 SANS aucun P2501 = le vainqueur (P1346 signifie « vainqueur ») ; P1346 avec un P2501 autre que ces trois valeurs (maillots, classements
  annexes) : ignoré ; deux déclarations identiques : une seule.
- Seuls les HUMAINS (P31 = Q5) sont des coureurs ; un P1346 vers une équipe (« ONCE-Eroski 2001 ») est IGNORÉ (`detail.ignores`).
- statut `ok` : un seul vainqueur humain, et P2321 (classement) n'a pas de rang 1 différent ; `non_attribue` : P1346 rang 1 = Q66666778 (« non
  attribué », ex. Tour de France 1999-2005), `detail` garde le rang 1 de P2321 ; `conflit` : plusieurs vainqueurs, ou rang 1 de P2321 différent de
  P1346 (les deux valeurs dans `detail`) ; `inconnu` : aucun vainqueur humain (ni tranché ni deviné). Le podium (rangs 2 et 3, et 1 si `ok`) est celui de P1346.
- Championnat de France (série dont l'édition est un CONTENEUR) : l'épreuve est l'élément P527 de l'édition dont un libellé (toutes langues lues) est
  « course en ligne masculine » / « men's (elite) road race » / « course en ligne hommes (élite) » et aucun n'est féminin / junior / espoir / U23 /
  amateur / contre-la-montre / relais ; zéro ou plusieurs éléments retenus : `statut: "inconnu"` (`detail.raison`), jamais de choix arbitraire.
- SÉRIE retenue (`series_historiques.json`) seulement avec la PREUVE : au moins 2 éditions 2019-2025 pour lesquelles le vainqueur Wikidata (statut
  `ok`) est notre vainqueur (même rider_id par le cache Wikidata `entites/wikidata/coureurs.json`, ou nom concordant + date de naissance P569 exacte
  égale à celle de notre rider_id) ; une année n'est comparée que si Wikidata et nos données n'ont chacun qu'UNE édition cette année-là.
- Politesse : 1 requête/s par hôte, User-Agent du projet, HTTP 429 : attente du `Retry-After` puis reprise (netutil `attendre_429`), sans abandonner
  l'hôte ; 403 : abandon. Re-vérification d'une série (et de ses coureurs) après 180 jours.

    python historique.py --test
    python historique.py <archives_dir> [--budget-min N]          (équivaut à run_pipeline.py --historique ; n'écrit que le cache)
    python historique.py --verifier-series candidats.json <archives_dir> [--sortie DIR]    (preuve des séries candidates {clé: QID | {qid, conteneur}})
    python historique.py --proposer <archives_dir> [--sortie DIR] [--budget-min N]          (étend series_historiques.json aux épreuves suivies, même preuve)
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

import collector
import netutil
import wikidata
from wikidata import HoteAbandonne

WD_API = wikidata.WD_API
SERIES_FICHIER = os.path.join(collector.RACINE, "series_historiques.json")
REFUSEES_FICHIER = os.path.join(collector.RACINE, "series_historiques_refusees.json")
RESULTAT = {"Q20882667": 1, "Q20882668": 2, "Q20882669": 3}          # P2501 : vainqueur / 2e / 3e du classement général
NON_ATTRIBUE = "Q66666778"
HUMAIN = "Q5"
COURSE_CYCLISTE = "Q15091377"                                         # « course cycliste » : classe racine des séries (P31 -> P279*)
PAGE_RECHERCHE = 500
LOT = wikidata.LOT
JOURS_VERIF = wikidata.JOURS_VERIF
REGLE_SERIE = 1                                                       # version de la règle de preuve
CONCORDANCES_MIN = 2
ANNEES_PREUVE = (2019, 2025)
LANGUES = "fr|en|es|it|nl|de"
MAX_CANDIDATS = 4
MIN_EDITIONS_PROPOSITION = 3
PERIODE_JOURNAL = 300
STATUTS = ("ok", "non_attribue", "conflit", "inconnu")
RE_MASCULIN = re.compile(r"course en ligne (?:masculine|hommes?)|men'?s (?:elite )?(?:road race|individual road race)|elite men'?s road race|"
                         r"herren.*stra[sß]enrennen|road race.*\bmen\b|\bmen\s+rr\b|\bhommes? [ée]lite\b.*en ligne", re.I)
RE_EXCLU = re.compile(r"femme|f[ée]minin|women|female|donne|dames|junior|espoir|u-?23|under|amateur|sans contrat|contre[- ]la[- ]montre|time trial|"
                      r"relais|relay|\bteam\b|[ée]quipes?\b|\bi?tt\b", re.I)


# --------------------------------------------------------------------------- outils

def _lettre(txt: Optional[str]) -> str:
    c = (txt or "")[:1]
    return c if "a" <= c <= "z" else "_"


def _sans_vide(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v not in (None, {}, [], "")}


def _fetch_429(base: str, params: Dict[str, Any]) -> Optional[Any]:
    return netutil.fetch_json(base + "?" + urllib.parse.urlencode(params), retries=2, attendre_429=True)


def creer_api(fetch: Optional[Callable[[str, Dict[str, Any]], Optional[Any]]] = None) -> wikidata.Api:
    """Accès Wikidata qui ATTEND les 429 (Retry-After) au lieu d'abandonner l'hôte."""
    if fetch is None:
        wikidata.preparer_reseau()
    return wikidata.Api(fetch or _fetch_429)


def est_humain(e: Optional[Dict[str, Any]]) -> bool:
    return bool(e) and any(wikidata.qid_de(c) == HUMAIN for c in wikidata.revendications(e, "P31"))


def _qualifs_qid(c: Dict[str, Any], prop: str) -> List[str]:
    out = []
    for s in (c.get("qualifiers") or {}).get(prop, []):
        v = (s.get("datavalue") or {}).get("value")
        if isinstance(v, dict) and re.fullmatch(r"Q\d+", str(v.get("id") or "")):
            out.append(v["id"])
    return out


def _uniques(xs: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(xs))


# --------------------------------------------------------------------------- cache

class Cache:
    """Cache `entites/historique/` : écriture seulement des fichiers modifiés (marqués par `sale`)."""

    def __init__(self, dossier: str):
        self.dossier = dossier
        self.editions: Dict[str, List[Dict[str, Any]]] = {}
        d_ed = os.path.join(dossier, "editions")
        for f in sorted(os.listdir(d_ed)) if os.path.isdir(d_ed) else []:
            data = collector._load(os.path.join(d_ed, f), {}) if f.endswith(".json") else {}
            if isinstance(data, dict):
                self.editions.update({k: v for k, v in data.items() if isinstance(v, list)})
        self.fichiers: Dict[str, Dict[str, Any]] = {}
        for n in ("coureurs", "pays", "non_personnes", "etat"):
            v = collector._load(os.path.join(dossier, n + ".json"), {})
            self.fichiers[n] = v if isinstance(v, dict) else {}
        self.sale: Set[str] = set()

    @property
    def coureurs(self) -> Dict[str, Dict[str, Any]]:
        return self.fichiers["coureurs"]

    @property
    def pays(self) -> Dict[str, Dict[str, Any]]:
        return self.fichiers["pays"]

    @property
    def non_personnes(self) -> Dict[str, str]:
        return self.fichiers["non_personnes"]

    @property
    def etat(self) -> Dict[str, Dict[str, Any]]:
        return self.fichiers["etat"]

    def poser_editions(self, cle: str, editions: List[Dict[str, Any]]) -> None:
        self.editions[cle] = editions
        self.sale.add("editions/" + _lettre(cle))

    def retirer_cle(self, cle: str) -> None:
        if self.editions.pop(cle, None) is not None:
            self.sale.add("editions/" + _lettre(cle))

    def marquer(self, nom: str) -> None:
        self.sale.add(nom)

    def ecrire(self) -> int:
        n = 0
        for nom in sorted(self.sale):
            if nom.startswith("editions/"):
                lettre = nom.split("/", 1)[1]
                contenu = dict(sorted((k, v) for k, v in self.editions.items() if _lettre(k) == lettre))
                chemin = os.path.join(self.dossier, "editions", lettre + ".json")
                if not contenu:                              # plus aucune édition pour cette lettre : fichier supprimé
                    if os.path.exists(chemin):
                        os.remove(chemin)
                        n += 1
                    continue
            else:
                contenu = dict(sorted(self.fichiers[nom].items()))
                chemin = os.path.join(self.dossier, nom + ".json")
            n += bool(collector._dump_if_changed(chemin, contenu, ignore=()))
        self.sale.clear()
        return n


def charger_cache(dossier: str) -> Dict[str, Any]:
    """Cache en lecture (pour encyclopedie.construire) : {"editions": {clé: [...]}, "coureurs": {QID: {...}}}, vides si absent."""
    c = Cache(dossier)
    return {"editions": c.editions, "coureurs": c.coureurs}


# --------------------------------------------------------------------------- extraction (fonctions pures)

def date_et_annee(e: Dict[str, Any]) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """(date AAAA[-MM[-JJ]] selon la précision, année, source de l'année si elle ne vient pas d'une date). P585, puis P580, puis P582 ;
    à défaut une année (1800-2099) lue dans le libellé fr / en."""
    for p in ("P585", "P580", "P582"):
        for c in wikidata.revendications(e, p):
            t = wikidata.parse_temps(wikidata.valeur(c))
            if t and t[1] >= 9:
                return wikidata.date_texte(t), int(t[0][:4]), None
    lab = (e.get("labels") or {})
    txt = " ".join((lab.get(l) or {}).get("value", "") for l in ("fr", "en"))
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", txt)
    return (None, int(m.group(1)), "libelle") if m else (None, None, None)


def rangs_p1346(e: Dict[str, Any]) -> Dict[int, List[str]]:
    """{1: [...], 2: [...], 3: [...]} (QID, ordre d'apparition, sans doublon) lus dans P1346 / P2501 selon les règles du module."""
    out: Dict[int, List[str]] = {1: [], 2: [], 3: []}
    for c in wikidata.revendications(e, "P1346"):
        q = wikidata.qid_de(c)
        if not q:
            continue
        quals = _qualifs_qid(c, "P2501")
        if not quals:
            out[1].append(q)
            continue
        for r in sorted({RESULTAT[x] for x in quals if x in RESULTAT}):
            out[r].append(q)
    return {r: _uniques(v) for r, v in out.items()}


def p2321_rang1(e: Dict[str, Any]) -> List[str]:
    """QID des coureurs de P2321 (classement) dont le qualificatif P1352 (rang) vaut 1."""
    out = []
    for c in wikidata.revendications(e, "P2321"):
        q = wikidata.qid_de(c)
        if not q:
            continue
        for s in (c.get("qualifiers") or {}).get("P1352", []):
            v = (s.get("datavalue") or {}).get("value")
            if isinstance(v, dict) and str(v.get("amount")) in ("+1", "1"):
                out.append(q)
                break
    return _uniques(out)


def brut_edition(qid: str, e: Dict[str, Any], conteneur: Optional[str] = None) -> Dict[str, Any]:
    """Faits bruts d'une édition (QID non encore classés en humains / équipes)."""
    date, annee, src = date_et_annee(e)
    return {"qid": qid, "annee": annee, "date": date, "annee_source": src, "rangs": rangs_p1346(e), "p2321": p2321_rang1(e),
            "wikipedia": wikidata.sitelinks(e), "conteneur": conteneur}


def qids_personnes(b: Dict[str, Any]) -> List[str]:
    q = [x for r in (1, 2, 3) for x in b["rangs"][r]] + list(b["p2321"])
    return _uniques(x for x in q if x != NON_ATTRIBUE)


def finaliser_edition(b: Dict[str, Any], humains: Set[str], verifie: str) -> Dict[str, Any]:
    """Enregistrement du cache d'une édition (statut, vainqueur, podium, détail) ; `humains` = QID reconnus comme humains."""
    rangs = {r: [q for q in b["rangs"][r] if q in humains] for r in (1, 2, 3)}
    ignores = _uniques(q for r in (1, 2, 3) for q in b["rangs"][r] if q not in humains and q != NON_ATTRIBUE)
    p2321 = [q for q in b["p2321"] if q in humains]
    non_attribue = NON_ATTRIBUE in b["rangs"][1]
    detail: Dict[str, Any] = {}
    vainqueur: Optional[str] = None
    r1 = rangs[1]
    if non_attribue:
        statut = "non_attribue"
        detail = {"p1346": r1, "p2321": p2321}
    elif len(r1) > 1:
        statut = "conflit"
        detail = {"p1346": r1, "p2321": p2321}
    elif len(r1) == 1:
        if p2321 and set(p2321) != {r1[0]}:
            statut = "conflit"
            detail = {"p1346": r1, "p2321": p2321}
        else:
            statut, vainqueur = "ok", r1[0]
    else:
        statut = "inconnu"
        detail = {"p2321": p2321}
    detail = {k: v for k, v in detail.items() if v}
    if ignores:
        detail["ignores"] = ignores
    podium = ([{"rang": 1, "qid": vainqueur}] if vainqueur else []) + [{"rang": r, "qid": q} for r in (2, 3) for q in rangs[r]]
    if b.get("detail_extra"):
        detail.update(b["detail_extra"])
    return _sans_vide({"annee": b["annee"], "qid": b["qid"], "date": b["date"], "annee_source": b.get("annee_source"),
                       "qid_conteneur": b.get("conteneur"), "vainqueur": vainqueur, "podium": podium, "statut": statut,
                       "detail": detail, "wikipedia": b["wikipedia"], "verifie": verifie})


def date_unique(e: Dict[str, Any], prop: str) -> Optional[Tuple[str, str]]:
    """(date AAAA[-MM[-JJ]], précision) d'une propriété de date (P569 / P570) : une seule valeur, ou plusieurs dont chacune est un préfixe de la plus
    précise (même date à des précisions différentes) ; None si absente ou contradictoire."""
    vals = []
    for c in wikidata.revendications(e, prop):
        t = wikidata.parse_temps(wikidata.valeur(c))
        if t and t[1] >= 9:
            vals.append((wikidata.date_texte(t), wikidata.precision_texte(t)))
    if not vals:
        return None
    plus = max(vals, key=lambda v: len(v[0]))
    return plus if all(plus[0].startswith(v[0]) for v in vals) else None


def code_pays(e: Optional[Dict[str, Any]]) -> Optional[str]:
    """Code CIO (P984) d'un pays : valeur préférée, sinon première ; None si absent."""
    for c in wikidata.revendications(e, "P984"):
        v = wikidata.valeur(c)
        if isinstance(v, str) and v.strip():
            return v.strip().upper()
    return None


def nom_personne(e: Dict[str, Any]) -> Optional[str]:
    lab = e.get("labels") or {}
    for l in ("fr", "en", "es", "it", "nl", "de"):
        v = (lab.get(l) or {}).get("value")
        if v:
            return v
    return next((v["value"] for v in lab.values() if isinstance(v, dict) and v.get("value")), None)


def extraire_personne(e: Dict[str, Any], pays: Dict[str, Dict[str, Any]], verifie: str) -> Dict[str, Any]:
    """Entrée `coureurs.json` d'un humain. `pays` = cache {QID: {code}}. Clés absentes si inconnues (jamais de valeur de substitution)."""
    nais, dec = date_unique(e, "P569"), date_unique(e, "P570")
    codes = _uniques(c for c in ((pays.get(q) or {}).get("code") for q in (wikidata.qid_de(x) for x in wikidata.revendications(e, "P27")) if q) if c)
    return _sans_vide({"nom": nom_personne(e), "naissance": nais and nais[0], "naissance_precision": nais and nais[1],
                       "deces": dec and dec[0], "deces_precision": dec and dec[1],
                       "nationalite": (codes[0] if len(codes) == 1 else codes) if codes else None,
                       "wikipedia": wikidata.sitelinks(e), "verifie": verifie})


def choisir_conteneur(parts: Dict[str, Optional[Dict[str, Any]]]) -> Tuple[Optional[str], str]:
    """(QID, raison) de la course en ligne masculine parmi les éléments P527 d'un conteneur ; règle du module. Raison : ok | aucune | plusieurs."""
    ok = []
    for q, e in parts.items():
        if not e:
            continue
        noms = [v.get("value", "") for v in (e.get("labels") or {}).values() if isinstance(v, dict)]
        if any(RE_MASCULIN.search(n) for n in noms) and not any(RE_EXCLU.search(n) for n in noms):
            ok.append(q)
    return (ok[0], "ok") if len(ok) == 1 else (None, "aucune" if not ok else "plusieurs")


# --------------------------------------------------------------------------- réseau

class Ctx:
    def __init__(self, api: wikidata.Api, cache: Cache, entites_dir: str, aujourdhui: dt.date, budget_min: float,
                 horloge: Callable[[], float] = time.monotonic):
        self.api, self.cache, self.entites_dir, self.aujourdhui = api, cache, entites_dir, aujourdhui
        self.horloge, self.t0 = horloge, horloge()
        self.budget_s = budget_min * 60
        self.derniere_ligne = self.t0
        self._sous: Optional[wikidata.Sousclasses] = None
        self._wd: Optional[Dict[str, Dict[str, Any]]] = None
        self._index: Optional[Dict[str, List[Tuple[str, str]]]] = None

    def minutes(self) -> float:
        return (self.horloge() - self.t0) / 60

    def hors_budget(self) -> bool:
        return bool(self.budget_s) and self.horloge() - self.t0 >= self.budget_s

    def sous(self) -> wikidata.Sousclasses:
        if self._sous is None:
            self._sous = wikidata.Sousclasses(self.api, COURSE_CYCLISTE)
        return self._sous

    def wd_coureurs(self) -> Dict[str, Dict[str, Any]]:
        """Cache Wikidata des coureurs (rider_id -> {qid, ...}) ; vide s'il n'existe pas."""
        if self._wd is None:
            self._wd = collector._load(os.path.join(self.entites_dir, "wikidata", "coureurs.json"), {}) or {}
        return self._wd

    def index_naissance(self) -> Dict[str, List[Tuple[str, str]]]:
        """{date de naissance: [(rider_id, nom)]} de nos coureurs (entites/coureurs)."""
        if self._index is None:
            self._index = collections.defaultdict(list)
            for f in wikidata.lister_coureurs(self.entites_dir)[0]:
                self._index[f["birth"]].append((f["id"], f["name"]))
        return self._index


def recherche_toutes(api: wikidata.Api, requete: str) -> Optional[List[str]]:
    """Tous les QID d'une recherche CirrusSearch (pages de PAGE_RECHERCHE) ; None si une page échoue (on ne conclut pas sur une liste partielle)."""
    res: List[str] = []
    off = 0
    while True:
        rep = api.appel(WD_API, action="query", list="search", srsearch=requete, srlimit=PAGE_RECHERCHE, sroffset=off, srnamespace=0, srprop="")
        if rep is None:
            return None
        lot = [r["title"] for r in (rep.get("query") or {}).get("search", []) if re.fullmatch(r"Q\d+", str(r.get("title") or ""))]
        res += lot
        nxt = (rep.get("continue") or {}).get("sroffset")
        if not nxt or not lot:
            break
        off = int(nxt)
    return _uniques(res)


def lire_editions(ctx: Ctx, qid: str, conteneur: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Faits bruts de toutes les éditions d'une série (instances de `qid`) ; None si une lecture échoue (série non écrite, retentée)."""
    ids = recherche_toutes(ctx.api, f"haswbstatement:P31={qid}")
    if ids is None:
        return None
    ents = wikidata.lire_entites(ctx.api, ids, "claims|labels|sitelinks", "fr|en")
    if any(q not in ents for q in ids):
        return None
    editions = {q: e for q, e in ents.items() if e}
    if not conteneur:
        return [brut_edition(q, e) for q, e in editions.items()]
    parts_de = {q: _uniques(x for x in (wikidata.qid_de(c) for c in wikidata.revendications(e, "P527")) if x) for q, e in editions.items()}
    parts = wikidata.lire_entites(ctx.api, [x for v in parts_de.values() for x in v], "claims|labels|sitelinks", "fr|en|es|it|nl|de")
    if any(x not in parts for v in parts_de.values() for x in v):
        return None
    out = []
    for q, e in editions.items():
        choix, raison = choisir_conteneur({x: parts[x] for x in parts_de[q]})
        if choix:
            b = brut_edition(choix, parts[choix], conteneur=q)
            d, a, s = date_et_annee(e)                    # date et année : celles du conteneur (l'élément de l'épreuve n'en porte pas toujours)
            if b["annee"] is None or b["date"] is None:
                b.update(date=b["date"] or d, annee=b["annee"] or a, annee_source=b["annee_source"] or s)
        else:
            d, a, s = date_et_annee(e)
            b = {"qid": q, "annee": a, "date": d, "annee_source": s, "rangs": {1: [], 2: [], 3: []}, "p2321": [],
                 "wikipedia": wikidata.sitelinks(e), "conteneur": None,
                 "detail_extra": {"raison": "course_en_ligne_masculine_" + ("introuvable" if raison == "aucune" else "non_unique"),
                                  "parts": len(parts_de[q])}}
        out.append(b)
    return out


def lire_pays(ctx: Ctx, qids: Iterable[str]) -> None:
    """Codes CIO (P984) des pays manquants ou périmés, dans le cache `pays`."""
    manque = [q for q in _uniques(qids) if wikidata.besoin(ctx.cache.pays.get(q), ctx.aujourdhui, "code")]
    if not manque:
        return
    ents = wikidata.lire_entites(ctx.api, manque, "claims")
    for q in manque:
        if q in ents:
            ctx.cache.pays[q] = {"code": code_pays(ents[q]), "verifie": ctx.aujourdhui.isoformat()}
    ctx.cache.marquer("pays")


def rider_strict(e: Optional[Dict[str, Any]], qid: str, index: Dict[str, List[Tuple[str, str]]],
                 wd: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """rider_id de NOTRE coureur correspondant à l'élément Wikidata, ou None : (1) le cache Wikidata (entites/wikidata/coureurs.json) le rattache à ce
    QID ; sinon (2) UN SEUL de nos coureurs a la même date de naissance (jour, P569) ET un nom concordant."""
    liens = sorted(rid for rid, v in wd.items() if isinstance(v, dict) and v.get("qid") == qid)
    if liens:
        return liens[0]
    nais = wikidata.naissance_jour(e) if e else None
    if not nais:
        return None
    cands = [rid for rid, nom in index.get(nais, []) if wikidata.nom_concorde(nom, wikidata.noms_entite(e))]
    return cands[0] if len(cands) == 1 else None


def lire_personnes(ctx: Ctx, qids: Iterable[str]) -> Optional[Set[str]]:
    """Classe les QID en humains (cache `coureurs`) et non-humains (cache `non_personnes`) ; lit seulement les manquants ou périmés (> 180 jours).
    Renvoie l'ensemble des humains, ou None si une lecture a échoué."""
    today = ctx.aujourdhui
    qids = _uniques(qids)
    manque = [q for q in qids if wikidata.besoin(ctx.cache.coureurs.get(q), today, "nom") and wikidata.besoin(
        {"verifie": ctx.cache.non_personnes.get(q), "qid": True}, today)]
    if manque:
        ents = wikidata.lire_entites(ctx.api, manque, "claims|labels|aliases|sitelinks", LANGUES)
        if any(q not in ents for q in manque):
            return None
        humains = {q: e for q, e in ents.items() if q in manque and e and est_humain(e)}
        lire_pays(ctx, (wikidata.qid_de(c) for e in humains.values() for c in wikidata.revendications(e, "P27")))
        for q in manque:
            e = ents.get(q)
            if q in humains:
                entree = extraire_personne(e, ctx.cache.pays, today.isoformat())
                rid = rider_strict(e, q, ctx.index_naissance(), ctx.wd_coureurs())
                if rid:
                    entree["rider_id"] = rid
                ctx.cache.coureurs[q] = entree
                ctx.cache.non_personnes.pop(q, None)
            else:                                          # équipe, élément supprimé ou sans P31 = Q5 : ignoré
                ctx.cache.non_personnes[q] = today.isoformat()
                ctx.cache.coureurs.pop(q, None)
        ctx.cache.marquer("coureurs")
        ctx.cache.marquer("non_personnes")
    return {q for q in qids if q in ctx.cache.coureurs}


# --------------------------------------------------------------------------- séries : traitement d'une série

def traiter_serie(ctx: Ctx, qid: str, cles: List[str], conteneur: bool = False) -> Optional[Dict[str, int]]:
    """Lit toutes les éditions de la série, classe les vainqueurs / podiums, écrit le cache sous chaque clé. None si une lecture a échoué."""
    brut = lire_editions(ctx, qid, conteneur)
    if brut is None:
        return None
    humains = lire_personnes(ctx, (q for b in brut for q in qids_personnes(b)))
    if humains is None:
        return None
    today = ctx.aujourdhui.isoformat()
    editions = sorted((finaliser_edition(b, humains, today) for b in brut), key=lambda r: (r.get("annee") or 0, r["qid"]))
    for cle in cles:
        ctx.cache.poser_editions(cle, editions)
    ctx.cache.etat[qid] = {"verifie": today, "editions": len(editions), "cles": sorted(cles)}
    ctx.cache.marquer("etat")
    compte = collections.Counter(r["statut"] for r in editions)
    return {"editions": len(editions), **{s: compte.get(s, 0) for s in STATUTS}}


def charger_series(chemin: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    brut = collector._load(chemin or SERIES_FICHIER, {})
    return {k: v for k, v in (brut.items() if isinstance(brut, dict) else [])
            if isinstance(v, dict) and re.fullmatch(r"Q\d+", str(v.get("qid") or ""))}


def regrouper(series: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """{QID de série: {"cles": [...], "conteneur": bool}} (plusieurs clés d'épreuve peuvent désigner la même série Wikidata)."""
    g: Dict[str, Dict[str, Any]] = {}
    for cle, s in sorted(series.items()):
        e = g.setdefault(s["qid"], {"cles": [], "conteneur": False})
        e["cles"].append(cle)
        e["conteneur"] = e["conteneur"] or bool(s.get("conteneur"))
    return g


def a_traiter(etat: Dict[str, Any], qid: str, cles: List[str], aujourdhui: dt.date) -> bool:
    e = etat.get(qid)
    if not isinstance(e, dict) or not set(cles) <= set(e.get("cles") or []):
        return True
    d = collector._date(e.get("verifie"))
    return d is None or (aujourdhui - d).days > JOURS_VERIF


def synchroniser_cles(cache: Cache, groupes: Dict[str, Dict[str, Any]], aujourdhui: dt.date) -> Tuple[int, int]:
    """Aligne le cache sur `series_historiques.json` SANS requête : (clés propagées, clés retirées). Une clé nouvelle d'une série déjà lue (et fraîche)
    reçoit les éditions de sa clé sœur ; une clé qui n'est plus dans le fichier (série refusée ou retirée) perd ses éditions, pour que les entités ne
    publient pas un palmarès dont la série n'est plus prouvée."""
    voulues = {c for g in groupes.values() for c in g["cles"]}
    retirees = 0
    for cle in sorted(set(cache.editions) - voulues):
        cache.retirer_cle(cle)
        retirees += 1
    for q in sorted(set(cache.etat) - set(groupes)):
        del cache.etat[q]
        cache.marquer("etat")
    propagees = 0
    for q, g in groupes.items():
        e = cache.etat.get(q)
        d = collector._date((e or {}).get("verifie"))
        if not e or d is None or (aujourdhui - d).days > JOURS_VERIF:
            continue
        connues = [c for c in e.get("cles") or [] if c in cache.editions]
        if not connues:
            continue
        for c in g["cles"]:
            if c not in e["cles"]:
                cache.poser_editions(c, cache.editions[connues[0]])
                propagees += 1
        e["cles"] = sorted(set(e["cles"]) & voulues | set(g["cles"]))
        cache.marquer("etat")
    return propagees, retirees


def maj_rider_ids(ctx: Ctx) -> int:
    """Recalcule, sans réseau, le lien `rider_id` des coureurs du cache à partir du cache Wikidata des coureurs (le rapprochement par nom a eu lieu à la lecture)."""
    liens: Dict[str, List[str]] = collections.defaultdict(list)
    for rid, v in ctx.wd_coureurs().items():
        if isinstance(v, dict) and v.get("qid"):
            liens[v["qid"]].append(rid)
    n = 0
    for q, c in ctx.cache.coureurs.items():
        if q in liens and c.get("rider_id") != sorted(liens[q])[0]:
            c["rider_id"] = sorted(liens[q])[0]
            n += 1
    if n:
        ctx.cache.marquer("coureurs")
    return n


def run_historique(budget_min: float = 300, archives_dir: Optional[str] = None, now: Optional[dt.date] = None,
                   api: Optional[wikidata.Api] = None, horloge: Callable[[], float] = time.monotonic,
                   series: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Un passage : pour chaque série de `series_historiques.json` jamais lue ou lue il y a plus de 180 jours (les plus anciennes d'abord), lit ses éditions,
    leurs vainqueurs et podiums, et écrit le cache SÉRIE PAR SÉRIE (un arrêt ne perd que la série en cours). N'écrit QUE `<archives_dir>/entites/historique/`.
    Budget en minutes (0 = illimité)."""
    archives_dir = archives_dir or collector.ARCHIVES_DIR
    entites = os.path.join(archives_dir, "entites")
    api = api or creer_api()
    cache = Cache(os.path.join(entites, "historique"))
    ctx = Ctx(api, cache, entites, now or dt.date.today(), budget_min, horloge)
    groupes = regrouper(charger_series() if series is None else series)
    propagees, retirees = synchroniser_cles(cache, groupes, ctx.aujourdhui)
    if propagees or retirees:
        print(f"[HISTORIQUE] cache aligné sur series_historiques.json : {propagees} clé(s) propagée(s), {retirees} retirée(s)")
        cache.ecrire()
    attente = sorted((q for q, g in groupes.items() if a_traiter(cache.etat, q, g["cles"], ctx.aujourdhui)),
                     key=lambda q: ((cache.etat.get(q) or {}).get("verifie") or "", q))
    faites, echecs, total = 0, 0, collections.Counter()
    try:
        for q in attente:
            if ctx.hors_budget():
                break
            res = traiter_serie(ctx, q, groupes[q]["cles"], groupes[q]["conteneur"])
            if res is None:
                echecs += 1
                print(f"[WARN] [HISTORIQUE] série {q} ({groupes[q]['cles'][0]}) : lecture incomplète, retentée au prochain passage")
                continue
            faites += 1
            total.update(res)
            cache.ecrire()
            if ctx.horloge() - ctx.derniere_ligne >= PERIODE_JOURNAL:
                ctx.derniere_ligne = ctx.horloge()
                print(f"[HISTORIQUE] en cours : {faites}/{len(attente)} séries, {total['editions']} éditions, {api.requetes} requêtes, {ctx.minutes():.0f} min")
        maj_rider_ids(ctx)
    except HoteAbandonne as e:
        print(f"[WARN] [HISTORIQUE] passage interrompu ({e}) : cache conservé, reprise au prochain passage")
    finally:
        cache.ecrire()
    restantes = sum(1 for q, g in groupes.items() if a_traiter(cache.etat, q, g["cles"], ctx.aujourdhui))
    rapproches = sum(1 for c in cache.coureurs.values() if c.get("rider_id"))
    print(f"[HISTORIQUE] {faites} série(s) lue(s) ({restantes} restante(s), {echecs} échec(s)), {total['editions']} édition(s) "
          f"(ok {total['ok']}, non attribuées {total['non_attribue']}, conflits {total['conflit']}, inconnues {total['inconnu']}), "
          f"{len(cache.coureurs)} coureur(s) en cache ({rapproches} rattaché(s) à un rider_id), {api.requetes} requête(s) en {ctx.minutes():.1f} min"
          f" ({api.requetes / ctx.minutes() if ctx.minutes() > 0 else 0:.1f} requêtes/min)")
    return {"series": faites, "restantes": restantes, "echecs": echecs, "editions": total["editions"],
            "statuts": {s: total[s] for s in STATUTS}, "coureurs": len(cache.coureurs), "requetes": api.requetes}


# --------------------------------------------------------------------------- preuve d'une série (acceptation / refus)

def nos_vainqueurs(entites_dir: str, cles: Optional[Iterable[str]] = None) -> Dict[str, Dict[int, List[Tuple[str, str]]]]:
    """{clé d'épreuve: {année (de start_date): [(rider_id, nom)]}} : vainqueurs (rang 1 du podium) de NOS éditions ; clés limitées à `cles` si donné."""
    voulues = set(cles) if cles is not None else None
    out: Dict[str, Dict[int, List[Tuple[str, str]]]] = {}
    dossier = os.path.join(entites_dir, "courses")
    for f in sorted(os.listdir(dossier)) if os.path.isdir(dossier) else []:
        data = collector._load(os.path.join(dossier, f), {}) if f.endswith(".json") and f != "index.json" else {}
        for cle, c in (data if isinstance(data, dict) else {}).items():
            if voulues is not None and cle not in voulues:
                continue
            par: Dict[int, List[Tuple[str, str]]] = {}
            for e in c.get("editions") or []:
                an = int(str(e.get("start_date") or "")[:4] or 0) or e.get("season")
                gagnants = [(p["id"], p.get("name") or "") for p in (e.get("podium") or []) if p.get("rank") == 1 and p.get("id")]
                par.setdefault(an, [])
                par[an] += gagnants if gagnants else [("", "")]      # une édition sans vainqueur compte (année non comparable)
            out[cle] = par
    return out


def _naissance_de_rider_id(rid: str) -> Optional[str]:
    m = re.search(r"-(\d{4})(\d\d)(\d\d)$", rid or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def meme_personne(ctx: Ctx, qid: str, e: Optional[Dict[str, Any]], rid: str, nom: str) -> bool:
    """Le QID Wikidata est-il NOTRE coureur `rid` ? (1) cache Wikidata : rider_id -> QID (s'il existe, il tranche) ; sinon (2) date de naissance P569
    à précision jour ÉGALE à celle de notre rider_id ET nom concordant."""
    lien = (ctx.wd_coureurs().get(rid) or {}).get("qid")
    if lien:
        return lien == qid
    nais = _naissance_de_rider_id(rid)
    return bool(e and nais and wikidata.naissance_jour(e) == nais and wikidata.nom_concorde(nom, wikidata.noms_entite(e)))


def preuve_serie(ctx: Ctx, brut: List[Dict[str, Any]], nos: Dict[int, List[Tuple[str, str]]]) -> Dict[str, Any]:
    """Preuve par concordance des vainqueurs 2019-2025 (règle du module). Renvoie {"concordances": [années], "comparees": [années],
    "discordances": [années]}."""
    a0, a1 = ANNEES_PREUVE
    par_annee: Dict[int, List[Dict[str, Any]]] = collections.defaultdict(list)
    for b in brut:
        if b["annee"] is not None and a0 <= b["annee"] <= a1:
            par_annee[b["annee"]].append(b)
    retenus = {an: bs[0] for an, bs in par_annee.items() if len(bs) == 1 and len(nos.get(an) or []) == 1 and nos[an][0][0]
               and len(bs[0]["rangs"][1]) == 1}
    qids = _uniques(q for b in retenus.values() for q in qids_personnes(b))
    ents = wikidata.lire_entites(ctx.api, qids, "claims|labels|aliases", LANGUES)
    humains = {q for q, e in ents.items() if e and est_humain(e)}
    res: Dict[str, List[int]] = {"concordances": [], "comparees": [], "discordances": []}
    for an in sorted(retenus):
        b = retenus[an]
        fin = finaliser_edition(b, humains, "")
        if fin["statut"] != "ok":
            continue
        q = fin["vainqueur"]
        rid, nom = nos[an][0]
        res["comparees"].append(an)
        res["concordances" if meme_personne(ctx, q, ents.get(q), rid, nom) else "discordances"].append(an)
    return res


def evaluer_serie(ctx: Ctx, cle: str, qid: str, conteneur: bool, nos: Dict[int, List[Tuple[str, str]]],
                  brut: Optional[List[Dict[str, Any]]] = None) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """(entrée retenue | None, rapport) pour une clé d'épreuve candidate : preuve par au moins 2 concordances."""
    if brut is None:
        brut = lire_editions(ctx, qid, conteneur)
    if brut is None:
        return None, {"qid": qid, "raison": "lecture_incomplete"}
    if len([an for an in nos if ANNEES_PREUVE[0] <= an <= ANNEES_PREUVE[1]]) < CONCORDANCES_MIN:
        return None, {"qid": qid, "raison": "moins_de_2_editions_2019_2025", "editions_wikidata": len(brut)}
    p = preuve_serie(ctx, brut, nos)
    rapport = {"qid": qid, "editions_wikidata": len(brut), "concordances": len(p["concordances"]), "comparees": len(p["comparees"])}
    if len(p["concordances"]) < CONCORDANCES_MIN:
        return None, dict(rapport, raison="preuve_insuffisante", discordances=p["discordances"])
    entree = {"qid": qid, "preuve": {"regle": REGLE_SERIE, "annees": p["concordances"], "comparees": len(p["comparees"]),
                                     "discordantes": p["discordances"], "verifie": ctx.aujourdhui.isoformat()}}
    if conteneur:
        entree["conteneur"] = True
    return entree, rapport


def verifier_series(ctx: Ctx, candidats: Dict[str, Any], nos: Dict[str, Dict[int, List[Tuple[str, str]]]]
                    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Preuve de chaque couple {clé d'épreuve: QID | {qid, conteneur}} : (retenues, refusées). Les éditions d'un même QID ne sont lues qu'une fois."""
    retenues: Dict[str, Dict[str, Any]] = {}
    refusees: Dict[str, Dict[str, Any]] = {}
    lus: Dict[str, Optional[List[Dict[str, Any]]]] = {}
    for cle, c in sorted(candidats.items()):
        qid = c if isinstance(c, str) else c["qid"]
        cont = False if isinstance(c, str) else bool(c.get("conteneur"))
        if qid not in lus:
            lus[qid] = lire_editions(ctx, qid, cont)
        e, r = evaluer_serie(ctx, cle, qid, cont, nos.get(cle) or {}, lus[qid])
        if e:
            retenues[cle] = e
        else:
            refusees[cle] = dict(r, verifie=ctx.aujourdhui.isoformat())
        print(f"[HISTORIQUE] preuve {cle} ({qid}) : {'retenue' if e else 'refusée (' + str(r.get('raison')) + ')'} "
              f"[{ctx.api.requetes} requêtes, {ctx.minutes():.1f} min]", flush=True)
    return retenues, refusees


def ecrire_series(retenues: Dict[str, Any], refusees: Dict[str, Any], sortie_series: str, sortie_refusees: str) -> None:
    """Fichiers versionnés relus par des humains : une ligne par épreuve, clés triées."""
    for chemin, contenu in ((sortie_series, retenues), (sortie_refusees, refusees)):
        lignes = [f" {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(contenu.items())]
        with open(chemin, "w", encoding="utf-8") as f:
            f.write("{\n" + ",\n".join(lignes) + "\n}\n" if lignes else "{}\n")


# --------------------------------------------------------------------------- proposition automatique (même preuve)

def noms_recherche(c: Dict[str, Any]) -> List[str]:
    """Noms à chercher pour une épreuve : les noms connus, du plus récent au plus ancien, plus leur partie avant « - » (sponsors) ; 4 au plus."""
    noms = sorted((c.get("noms") or {}).items(), key=lambda kv: (-max(kv[1] or [0]), kv[0]))
    out: List[str] = []
    for n, _ in noms:
        for v in (n, re.split(r"\s+[-–|]\s+", n)[0]):
            v = re.sub(r"\s*\((?:[^)]*)\)\s*", " ", v).strip()
            v = re.sub(r"^\d+\s*(?:e|er|eme|ème|°)?\s+", "", v).strip()
            if v and v not in out:
                out.append(v)
    return out[:4]


def candidats_wikidata(ctx: Ctx, noms: List[str]) -> List[str]:
    """QID d'éléments dont la classe P31 est (sous-classe de) « course cycliste », trouvés par recherche de nom (fr puis en)."""
    vus: List[str] = []
    for lang in ("fr", "en"):
        for n in noms:
            rep = ctx.api.appel(WD_API, action="wbsearchentities", search=n, language=lang, uselang=lang, limit=7, type="item")
            vus += [x["id"] for x in (rep or {}).get("search", []) if re.fullmatch(r"Q\d+", str(x.get("id") or ""))]
        if vus:
            break
    vus = _uniques(vus)
    ents = wikidata.lire_entites(ctx.api, vus, "claims|labels", "fr|en")
    ok = []
    for q in vus:
        classes = [x for x in (wikidata.qid_de(c) for c in wikidata.revendications(ents.get(q), "P31")) if x]
        if any(ctx.sous().est(x) for x in classes):
            ok.append(q)
    return ok[:MAX_CANDIDATS]


def proposer_series(ctx: Ctx, entites_dir: str, deja: Iterable[str] = (), epreuves: Optional[Iterable[str]] = None,
                    min_editions: int = 2) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Étend les séries aux épreuves suivies avec la MÊME preuve : pour chaque clé (de `epreuves`, défaut : épreuves de plus de `min_editions` éditions
    de nos données, hors `deja`), recherche par nom des séries candidates (P31 = course cycliste ou sous-classe, au moins MIN_EDITIONS_PROPOSITION
    éditions), puis preuve de concordance des vainqueurs 2019-2025. Une seule candidate prouvée est retenue ; deux candidates prouvées différentes :
    refus « ambigu » (jamais tranché). Renvoie (retenues, refusées)."""
    deja = set(deja)
    nos = nos_vainqueurs(entites_dir)
    fiches: Dict[str, Dict[str, Any]] = {}
    dossier = os.path.join(entites_dir, "courses")
    for f in sorted(os.listdir(dossier)) if os.path.isdir(dossier) else []:
        data = collector._load(os.path.join(dossier, f), {}) if f.endswith(".json") and f != "index.json" else {}
        fiches.update(data if isinstance(data, dict) else {})
    cles = [c for c in (sorted(epreuves) if epreuves is not None else sorted(fiches))
            if c in fiches and c not in deja and len(fiches[c].get("editions") or []) >= min_editions]
    retenues: Dict[str, Dict[str, Any]] = {}
    refusees: Dict[str, Dict[str, Any]] = {}
    lus: Dict[str, Optional[List[Dict[str, Any]]]] = {}
    today = ctx.aujourdhui.isoformat()
    for cle in cles:
        if ctx.hors_budget():
            break
        cands = candidats_wikidata(ctx, noms_recherche(fiches[cle]))
        prouvees: List[Tuple[str, Dict[str, Any]]] = []
        raisons: Dict[str, str] = {}
        for q in cands:
            if q not in lus:
                rep = ctx.api.appel(WD_API, action="query", list="search", srsearch=f"haswbstatement:P31={q}", srlimit=1, srnamespace=0)
                total = int(((rep or {}).get("query") or {}).get("searchinfo", {}).get("totalhits") or 0)
                lus[q] = lire_editions(ctx, q) if total >= MIN_EDITIONS_PROPOSITION else []
            if not lus[q]:
                raisons[q] = "moins_de_3_editions"
                continue
            e, r = evaluer_serie(ctx, cle, q, False, nos.get(cle) or {}, lus[q])
            if e:
                prouvees.append((q, e))
            else:
                raisons[q] = r.get("raison", "?")
        if len(prouvees) == 1:
            retenues[cle] = prouvees[0][1]
        else:
            refusees[cle] = {"raison": "ambigu" if prouvees else ("aucune_candidate" if not cands else "preuve_insuffisante"),
                             "candidats": raisons or None, "prouvees": [q for q, _ in prouvees] or None, "verifie": today}
            refusees[cle] = {k: v for k, v in refusees[cle].items() if v is not None}
    return retenues, refusees


# --------------------------------------------------------------------------- intégration dans les entités (appelée par encyclopedie.construire)

def id_leger(qid: str) -> str:
    return "wd-" + qid


def fichier_leger(wdid: str) -> str:
    """Fichier `coureurs_historiques/` d'un coureur historique : les deux derniers chiffres du QID (déterminé par l'identifiant seul)."""
    n = re.sub(r"\D", "", wdid)
    return n[-2:].rjust(2, "0")


def _groupes_cles(editions_par_cle: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Set[str]]:
    """Pour chaque clé, l'ensemble des clés qui partagent au moins une édition Wikidata (même série sous des noms différents)."""
    par_qid: Dict[str, Set[str]] = collections.defaultdict(set)
    for cle, eds in editions_par_cle.items():
        for e in eds:
            par_qid[e["qid"]].add(cle)
    parent = {c: c for c in editions_par_cle}

    def trouver(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for ks in par_qid.values():
        ks = sorted(ks)
        for k in ks[1:]:
            parent[trouver(k)] = trouver(ks[0])
    groupes: Dict[str, Set[str]] = collections.defaultdict(set)
    for c in editions_par_cle:
        groupes[trouver(c)].add(c)
    return {c: groupes[trouver(c)] for c in editions_par_cle}


def edition_future(e: Dict[str, Any], aujourdhui: Optional[str]) -> bool:
    """Édition annoncée (date postérieure au jour, comparée à sa précision ; sans date, année postérieure à l'année en cours) : jamais publiée."""
    if not aujourdhui:
        return False
    d = e.get("date")
    if d:
        return d > aujourdhui[:len(d)]          # à la précision de la date : année seule = futur seulement si l'année est postérieure
    return bool(e.get("annee")) and e["annee"] > int(aujourdhui[:4])


def appliquer_historique(hist: Dict[str, Any], courses: Dict[str, Dict[str, Any]], coureurs: Dict[str, Dict[str, Any]],
                         alias_coureurs: Dict[str, str], wd_coureurs: Dict[str, Dict[str, Any]], aujourdhui: Optional[str] = None) -> Dict[str, Any]:
    """Fusionne le cache historique avec NOS données (fonction pure, sans réseau).

    `courses` : {clé: {"editions": [éditions UCI : season, start_date, podium]}} ; `coureurs` : {rider_id canonique: {name, nationality, flag}} ;
    `wd_coureurs` : cache Wikidata des coureurs {rider_id: {qid}}. Renvoie
      par_cle  {clé: {"historique": [{annee, date?, vainqueur, podium, statut, detail?, source_qid, wikipedia?}], "info": {...}, "records": {...}}}
      attaches {rider_id: [palmarès historique]}, legers {id « wd-Q… »: entité légère}, recherche [entrées de recherche], rapport.
    Années : une année n'entre dans `historique` que si AUCUNE de nos éditions UCI (de la clé ou d'une clé qui désigne la même série Wikidata) ne la
    couvre (année de start_date). Le coureur d'un podium est NOTRE coureur (rider_id canonique, après alias) si le cache le rattache (rider_id
    du cache historique ou lien Wikidata), sinon un coureur historique léger « wd-<QID> ». Les éditions annoncées (postérieures à `aujourdhui`, AAAA-MM-JJ)
    ne sont pas publiées."""
    editions_h: Dict[str, List[Dict[str, Any]]] = {c: e for c, e in (hist.get("editions") or {}).items() if c in courses}
    coureurs_h: Dict[str, Dict[str, Any]] = hist.get("coureurs") or {}
    inverse: Dict[str, str] = {}
    for rid, v in sorted(wd_coureurs.items()):
        if isinstance(v, dict) and v.get("qid"):
            inverse.setdefault(v["qid"], alias_coureurs.get(rid, rid))
    groupes = _groupes_cles(editions_h)

    def annee_uci(e: Dict[str, Any]) -> Optional[int]:
        sd = str(e.get("start_date") or "")[:4]
        return int(sd) if sd.isdigit() else e.get("season")

    memo: Dict[str, Dict[str, Any]] = {}

    def personne(q: str) -> Dict[str, Any]:
        if q in memo:
            return memo[q]
        h = coureurs_h.get(q) or {}
        rid = h.get("rider_id")
        rid = alias_coureurs.get(rid, rid) if rid else None
        if rid not in coureurs:
            rid = inverse.get(q) if inverse.get(q) in coureurs else None
        if rid:
            c = coureurs[rid]
            p = _sans_vide({"id": rid, "name": c.get("name"), "nat": c.get("nationality"), "flag": c.get("flag"), "qid": q, "attache": True})
        else:
            nat = h.get("nationalite")
            nat1 = nat if isinstance(nat, str) else None
            p = _sans_vide({"id": id_leger(q), "name": h.get("nom"), "nat": nat1, "flag": netutil.flag_code(nat1) if nat1 else None, "qid": q})
        memo[q] = p
        return p

    def ref(q: str, rang: Optional[int] = None) -> Dict[str, Any]:
        p = personne(q)
        return _sans_vide({"rang": rang, "id": p["id"], "name": p.get("name"), "nat": p.get("nat"), "flag": p.get("flag")})

    par_cle: Dict[str, Any] = {}
    attaches: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    palmares_leger: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    vus_legers: Set[str] = set()
    stats = collections.Counter()
    for cle in sorted(editions_h):
        annees_uci = {a for k in groupes[cle] for a in (annee_uci(e) for e in (courses.get(k) or {}).get("editions") or []) if a}
        utiles = [e for e in editions_h[cle] if e.get("annee") and e["annee"] not in annees_uci and not edition_future(e, aujourdhui)]
        if not utiles:
            continue
        sortie = []
        for e in sorted(utiles, key=lambda e: (e["annee"], e["qid"]), reverse=True):
            det = e.get("detail") or {}
            d_out: Dict[str, Any] = {}
            for k in ("p1346", "p2321"):
                if det.get(k):
                    d_out[k] = [ref(q) for q in det[k]]
            for k in ("raison", "parts", "ignores"):
                if det.get(k):
                    d_out[k] = det[k]
            podium = [ref(p["qid"], p["rang"]) for p in e.get("podium") or []]
            sortie.append(_sans_vide({"annee": e["annee"], "date": e.get("date"), "vainqueur": personne(e["vainqueur"])["id"] if e.get("vainqueur") else None,
                                      "podium": podium, "statut": e["statut"], "detail": d_out, "source_qid": e["qid"],
                                      "wikipedia": e.get("wikipedia")}))
            stats[e["statut"]] += 1
            personnes_ed = [p["qid"] for p in e.get("podium") or []] + [q for k in ("p1346", "p2321") for q in det.get(k) or []]
            for q in personnes_ed:
                p = personne(q)
                if not p.get("attache"):
                    vus_legers.add(q)
            for p in e.get("podium") or []:
                pp = personne(p["qid"])
                item = {"annee": e["annee"], "course": cle, "rang": p["rang"], "source_qid": e["qid"]}
                if e.get("date"):
                    item["date"] = e["date"]
                (attaches[pp["id"]] if pp.get("attache") else palmares_leger[pp["id"]]).append(item)
        # records : UCI + historique (années couvertes mentionnées)
        gagnants: Dict[str, Dict[str, Any]] = {}
        victoires: collections.Counter = collections.Counter()
        pays: collections.Counter = collections.Counter()
        indetermines = 0
        annees_cou: Set[int] = set()
        nb = 0
        for e in (courses.get(cle) or {}).get("editions") or []:
            a = annee_uci(e)
            w = next((p for p in e.get("podium") or [] if p.get("rank") == 1 and p.get("id")), None)
            if a:
                annees_cou.add(a)
            if w:
                nb += 1
                gagnants[w["id"]] = _sans_vide({"id": w["id"], "name": w.get("name")})
                victoires[w["id"]] += 1
                if w.get("nat"):
                    pays[w["nat"]] += 1
                else:
                    indetermines += 1
        for s in sortie:
            annees_cou.add(s["annee"])
            if s["statut"] == "ok" and s.get("vainqueur"):
                nb += 1
                w = next(p for p in s["podium"] if p["rang"] == 1)
                gagnants.setdefault(w["id"], _sans_vide({"id": w["id"], "name": w.get("name")}))
                victoires[w["id"]] += 1
                if w.get("nat"):
                    pays[w["nat"]] += 1
                else:
                    indetermines += 1
        par_cle[cle] = {
            "historique": sortie,
            "info": {"source": "wikidata", "annees": [min(s["annee"] for s in sortie), max(s["annee"] for s in sortie)], "editions": len(sortie)},
            "records": _sans_vide({
                "annees_couvertes": [min(annees_cou), max(annees_cou)], "editions_avec_vainqueur": nb,
                "victoires_par_coureur": [_sans_vide({"id": i, "name": gagnants[i].get("name"), "wins": n})
                                           for i, n in sorted(victoires.items(), key=lambda kv: (-kv[1], gagnants[kv[0]].get("name") or "", kv[0])) if n >= 2],
                "victoires_par_pays": dict(sorted(pays.items(), key=lambda kv: (-kv[1], kv[0]))),
                "victoires_pays_indeterminees": indetermines or None,
                "non_attribuees": stats_cle(sortie, "non_attribue"), "conflits": stats_cle(sortie, "conflit")})}
    legers: Dict[str, Dict[str, Any]] = {}
    recherche: List[Dict[str, Any]] = []
    for q in sorted(vus_legers):
        h = coureurs_h.get(q) or {}
        wid = id_leger(q)
        pal = _dedoublonner(palmares_leger.get(wid, []))
        nat = h.get("nationalite")
        flag = netutil.flag_code(nat) if isinstance(nat, str) else None
        fiche = _sans_vide({"name": h.get("nom"), "nationality": nat, "flag": flag, "birth_date": h.get("naissance"),
                            "birth_precision": h.get("naissance_precision"), "death_date": h.get("deces"),
                            "death_precision": h.get("deces_precision"), "wikidata": {"qid": q, "wikipedia": h.get("wikipedia")},
                            "source": "wikidata", "palmares_historique": pal,
                            "totaux": {"wins": sum(1 for x in pal if x["rang"] == 1), "podiums": len(pal)}})
        legers[wid] = fiche
        if h.get("nom"):
            ys = sorted(x["annee"] for x in pal)
            recherche.append(_sans_vide({"n": h["nom"], "t": "c", "id": wid, "f": flag, "y": [ys[0], ys[-1]] if ys else None}))
    return {"par_cle": par_cle,
            "attaches": {k: _dedoublonner(v) for k, v in sorted(attaches.items())},
            "legers": dict(sorted(legers.items())), "recherche": recherche,
            "rapport": {"editions_historiques": sum(stats.values()), "statuts": dict(stats), "series_cles": len(par_cle),
                        "coureurs_legers": len(legers), "coureurs_attaches": len(attaches)}}


def _dedoublonner(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Palmarès historique trié (récent d'abord) ; une même édition Wikidata vue sous plusieurs clés (même série, noms différents) n'est comptée qu'une fois
    (la clé retenue est la première par ordre alphabétique)."""
    vus: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for x in sorted(items, key=lambda x: (x["course"], x["annee"], x["rang"])):
        vus.setdefault((x["source_qid"], x["rang"]), x)
    return sorted(vus.values(), key=lambda x: (x["annee"], x["course"], x["rang"]), reverse=True)


def stats_cle(sortie: List[Dict[str, Any]], statut: str) -> Optional[int]:
    return sum(1 for s in sortie if s["statut"] == statut) or None


# --------------------------------------------------------------------------- tests (réponses simulées)

class FauxHist:
    """Serveur Wikidata simulé : recherche `haswbstatement:P31=…` (avec pagination), wbgetentities, wbsearchentities. Compte les requêtes."""

    def __init__(self, entites: Dict[str, Dict[str, Any]], series: Dict[str, List[str]], noms: Optional[Dict[str, List[str]]] = None):
        self.entites, self.series, self.noms = entites, series, noms or {}
        self.log: List[Tuple[str, str]] = []

    def __call__(self, base: str, p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        a = p["action"]
        if a == "query":
            m = re.fullmatch(r"haswbstatement:P31=(Q\d+)", p["srsearch"])
            self.log.append(("search", p["srsearch"]))
            tous = self.series.get(m.group(1), []) if m else []
            off, lim = int(p.get("sroffset") or 0), int(p["srlimit"])
            rep: Dict[str, Any] = {"query": {"searchinfo": {"totalhits": len(tous)}, "search": [{"title": q} for q in tous[off:off + lim]]}}
            if off + lim < len(tous):
                rep["continue"] = {"sroffset": off + lim}
            return rep
        if a == "wbsearchentities":
            self.log.append(("nom", p["search"]))
            return {"search": [{"id": q} for q in self.noms.get(p["search"], [])]}
        self.log.append(("entites", p["ids"]))
        assert len(p["ids"].split("|")) <= LOT
        return {"entities": {q: (self.entites[q] if q in self.entites else {"id": q, "missing": ""}) for q in p["ids"].split("|")}}

    def n(self, genre: str) -> int:
        return sum(1 for g, _ in self.log if g == genre)


def _claim_p1346(q: str, resultat: Optional[str] = None, rank: str = "normal") -> Dict[str, Any]:
    c = wikidata._cl(wikidata._eid(q), rank=rank)
    if resultat:
        c["qualifiers"] = {"P2501": [wikidata._snak(wikidata._eid(resultat))]}
    return c


def _claim_p2321(q: str, rang: int) -> Dict[str, Any]:
    c = wikidata._cl(wikidata._eid(q))
    c["qualifiers"] = {"P1352": [wikidata._snak({"amount": f"+{rang}", "unit": "1"})]}
    return c


def _edition(q: str, annee: int, vainqueurs: Optional[List[str]] = None, podium: Tuple[Optional[str], Optional[str]] = (None, None),
             p2321_r1: Optional[List[str]] = None, serie: str = "Q1000", sans_date: bool = False, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    claims: Dict[str, Any] = {"P31": [wikidata._cl(wikidata._eid(serie))]}
    if not sans_date:
        claims["P585"] = [wikidata._cl(wikidata._t(f"{annee}-07-01"))]
    p = [_claim_p1346(v, "Q20882667") for v in (vainqueurs or [])]
    if podium[0]:
        p.append(_claim_p1346(podium[0], "Q20882668"))
    if podium[1]:
        p.append(_claim_p1346(podium[1], "Q20882669"))
    if p:
        claims["P1346"] = p
    if p2321_r1:
        claims["P2321"] = [_claim_p2321(v, 1) for v in p2321_r1]
    claims.update(extra or {})
    return {"id": q, "labels": {"fr": {"language": "fr", "value": f"Course {annee}"}}, "claims": claims,
            "sitelinks": {"frwiki": {"site": "frwiki", "title": f"Course {annee}"}}}


def _personne(q: str, nom: str, naiss: Optional[str] = None, pays: Optional[str] = None, humain: bool = True) -> Dict[str, Any]:
    e = wikidata._item(q, nom, naiss, occ=None)
    e["claims"]["P31"] = [wikidata._cl(wikidata._eid(HUMAIN if humain else "Q327245"))]
    if pays:
        e["claims"]["P27"] = [wikidata._cl(wikidata._eid(pays))]
    return e


def _tests() -> None:
    import shutil
    # --- fonctions pures
    assert _lettre("tour") == "t" and _lettre("1x") == "_" and fichier_leger("wd-Q5") == "05" and fichier_leger("wd-Q1234567") == "67"
    assert id_leger("Q9") == "wd-Q9"
    e = _edition("Q10", 1903, ["Q1"], ("Q2", "Q3"))
    assert rangs_p1346(e) == {1: ["Q1"], 2: ["Q2"], 3: ["Q3"]}
    # P1346 sans qualificatif = vainqueur ; avec un P2501 inconnu (maillot) = ignoré ; doublon = une fois
    e2 = _edition("Q11", 1950, extra={"P1346": [_claim_p1346("Q7"), _claim_p1346("Q7"), _claim_p1346("Q8", "Q99999"), _claim_p1346("Q5", "Q20882668")]})
    assert rangs_p1346(e2) == {1: ["Q7"], 2: ["Q5"], 3: []}, rangs_p1346(e2)
    assert rangs_p1346(_edition("Q12", 1, extra={"P1346": [_claim_p1346("Q7", "Q20882667", rank="deprecated")]})) == {1: [], 2: [], 3: []}
    assert p2321_rang1(_edition("Q13", 1999, p2321_r1=["Q4", "Q6"])) == ["Q4", "Q6"]
    assert date_et_annee(e) == ("1903-07-01", 1903, None)
    ed_lab = _edition("Q14", 1898, sans_date=True)
    ed_lab["labels"] = {"fr": {"language": "fr", "value": "Course historique 1898"}}
    assert date_et_annee(ed_lab) == (None, 1898, "libelle")
    ed_nu = _edition("Q15", 1, sans_date=True)
    ed_nu["labels"] = {"fr": {"language": "fr", "value": "Course sans année"}}
    assert date_et_annee(ed_nu) == (None, None, None)
    # --- statuts d'édition
    H = {"Q1", "Q2", "Q3", "Q4", "Q6"}

    def fin(ed, humains=H):
        return finaliser_edition(brut_edition(ed["id"], ed), humains, "2026-11-16")
    r = fin(_edition("Q10", 1903, ["Q1"], ("Q2", "Q3")))
    assert r["statut"] == "ok" and r["vainqueur"] == "Q1" and [p["qid"] for p in r["podium"]] == ["Q1", "Q2", "Q3"] and "detail" not in r, r
    assert r["wikipedia"] == {"fr": "Course 1903"} and r["date"] == "1903-07-01"
    r = fin(_edition("Q20", 1999, ["Q66666778"], ("Q2", "Q3"), p2321_r1=["Q4"]))
    assert r["statut"] == "non_attribue" and "vainqueur" not in r and r["detail"] == {"p2321": ["Q4"]}, r
    assert [p["qid"] for p in r["podium"]] == ["Q2", "Q3"]                                  # podium de P1346 conservé, rang 1 absent
    r = fin(_edition("Q21", 1974, ["Q1"], p2321_r1=["Q4"]))                                 # divergence P1346 / P2321 : jamais tranché
    assert r["statut"] == "conflit" and r["detail"] == {"p1346": ["Q1"], "p2321": ["Q4"]} and "vainqueur" not in r
    r = fin(_edition("Q22", 1981, ["Q1", "Q2"]))                                            # plusieurs rang 1
    assert r["statut"] == "conflit" and r["detail"]["p1346"] == ["Q1", "Q2"]
    r = fin(_edition("Q23", 1973, ["Q1"], p2321_r1=["Q1"]))                                 # P2321 concorde
    assert r["statut"] == "ok" and r["vainqueur"] == "Q1"
    r = fin(_edition("Q24", 2001, ["Q99"], ("Q2", None)))                                    # P1346 vers une équipe (Q99 non humain) : ignorée
    assert r["statut"] == "inconnu" and r["detail"]["ignores"] == ["Q99"] and "vainqueur" not in r and [p["qid"] for p in r["podium"]] == ["Q2"], r
    r = fin(_edition("Q25", 2002, ["Q1"], ("Q99", None)))                                    # équipe au 2e rang : ignorée, vainqueur conservé
    assert r["statut"] == "ok" and r["detail"] == {"ignores": ["Q99"]} and [p["qid"] for p in r["podium"]] == ["Q1"]
    r = fin(_edition("Q26", 2003))
    assert r["statut"] == "inconnu" and "detail" not in r and "podium" not in r, r
    r = fin(_edition("Q27", 1898, ["Q1"], sans_date=True))
    assert "date" not in r and r["annee"] == 1898 and r["annee_source"] == "libelle" and r["statut"] == "ok", r
    # --- dates de personne
    assert date_unique(_personne("Q1", "A", "1945-06-17"), "P569") == ("1945-06-17", "jour")
    e_p = _personne("Q1", "A")
    e_p["claims"]["P569"] = [wikidata._cl(wikidata._t("1945-06-17")), wikidata._cl(wikidata._t("1945-01-01", 9))]
    assert date_unique(e_p, "P569") == ("1945-06-17", "jour")                              # année seule + jour cohérents : le jour
    e_p["claims"]["P569"] = [wikidata._cl(wikidata._t("1945-06-17")), wikidata._cl(wikidata._t("1946-06-17"))]
    assert date_unique(e_p, "P569") is None                                                 # contradictoire : rien
    assert date_unique(_personne("Q1", "A"), "P569") is None
    # --- conteneur : règle de choix de l'épreuve masculine en ligne
    def part(q, lab):
        return {"id": q, "labels": {"fr": {"language": "fr", "value": lab}}}
    assert choisir_conteneur({"Q1": part("Q1", "Course en ligne masculine aux championnats de France 1990"), "Q2": part("Q2", "Course en ligne féminine aux championnats de France 1990"),
                              "Q3": part("Q3", "Course en ligne masculine juniors aux championnats de France 1990")}) == ("Q1", "ok")
    assert choisir_conteneur({"Q2": part("Q2", "Course en ligne féminine 1990")}) == (None, "aucune")
    assert choisir_conteneur({"Q1": part("Q1", "2025 France National Road Cycling Championships - Men RR"), "Q2": part("Q2", "2025 France National Road Cycling Championships - Men ITT"),
                              "Q3": part("Q3", "2025 France National Road Cycling Championships - Women RR")}) == ("Q1", "ok")
    assert choisir_conteneur({"Q1": part("Q1", "Course en ligne masculine 1990"), "Q4": part("Q4", "Men's road race 1990")}) == (None, "plusieurs")
    # --- 429 : netutil attend le Retry-After puis reprend, sans bloquer l'hôte
    _test_429()

    # ---------------------------------------------------------------- run_historique complet sur un faux Wikidata
    P = {
        "Q1": _personne("Q1", "Jean Dupont", "1930-01-02", "Q31"), "Q2": _personne("Q2", "Luc Durand", "1931-02-03", "Q142"),
        "Q3": _personne("Q3", "Ana Lopez", "1932-03-04", "Q29"), "Q4": _personne("Q4", "Paul Martin", "1940-05-06", "Q31"),
        "Q6": _personne("Q6", "Marc Double", "1941-07-08", "Q31"), "Q99": _personne("Q99", "Équipe Test 2001", humain=False),
        "Q70": _personne("Q70", "Jean Moderne", "1995-05-05", "Q31"),
        "Q31": {"id": "Q31", "claims": {"P984": [wikidata._cl("BEL")]}, "labels": {}},
        "Q142": {"id": "Q142", "claims": {"P984": [wikidata._cl("FRA")]}, "labels": {}},
        "Q29": {"id": "Q29", "claims": {}, "labels": {}},                                      # pays sans code CIO : nationalité absente
    }
    P["Q6"]["claims"]["P27"] = [wikidata._cl(wikidata._eid("Q31")), wikidata._cl(wikidata._eid("Q142"))]
    E = {
        "Q101": _edition("Q101", 1903, ["Q1"], ("Q2", "Q3")),
        "Q102": _edition("Q102", 1999, ["Q66666778"], ("Q2", "Q3"), p2321_r1=["Q4"]),
        "Q103": _edition("Q103", 1974, ["Q1"], p2321_r1=["Q4"]),
        "Q104": _edition("Q104", 2001, ["Q99"], ("Q2", None)),
        "Q105": _edition("Q105", 2022, ["Q70"]), "Q106": _edition("Q106", 2023, ["Q70"]),
        "Q107": _edition("Q107", 1950, ["Q6"]),
        "Q108": _edition("Q108", 2024, ["Q70"]),
    }
    series = {"Q1000": list(E)}
    faux = FauxHist({**P, **E}, series)
    tmp = tempfile.mkdtemp(prefix="hist_")
    try:
        ent = os.path.join(tmp, "entites")
        os.makedirs(os.path.join(ent, "coureurs"))
        collector._dump(os.path.join(ent, "coureurs", "m.json"), {"moderne-jean-19950505": {"name": "Jean Moderne", "birth_date": "1995-05-05"},
                                                                  "dupont-jean-19300102": {"name": "Jean Dupont", "birth_date": "1930-01-02"},
                                                                  "dupond-jean-19300102": {"name": "Jean Dupond", "birth_date": "1930-01-02"}})
        collector._dump(os.path.join(ent, "wikidata", "coureurs.json"), {"martin-paul-19400506": {"qid": "Q4", "verifie": "2026-01-01"}})
        today = dt.date(2026, 11, 16)
        horloge = [0.0]
        series_cfg = {"tour test|FRA": {"qid": "Q1000"}, "tour test ancien nom|FRA": {"qid": "Q1000"}}
        res = run_historique(5, tmp, today, creer_api(faux), lambda: horloge[0], series_cfg)
        assert res["series"] == 1 and res["editions"] == 8 and res["restantes"] == 0 and res["echecs"] == 0, res
        assert res["statuts"] == {"ok": 5, "non_attribue": 1, "conflit": 1, "inconnu": 1}, res
        c = Cache(os.path.join(ent, "historique"))
        eds = c.editions["tour test|FRA"]
        assert c.editions["tour test ancien nom|FRA"] == eds and len(eds) == 8
        par = {e["annee"]: e for e in eds}
        assert par[1903]["statut"] == "ok" and par[1903]["vainqueur"] == "Q1" and par[1903]["verifie"] == "2026-11-16"
        assert par[1999]["statut"] == "non_attribue" and par[1999]["detail"]["p2321"] == ["Q4"]
        assert par[1974]["statut"] == "conflit" and par[2001]["statut"] == "inconnu" and par[2001]["detail"]["ignores"] == ["Q99"]
        assert "Q99" in c.non_personnes and "Q99" not in c.coureurs and "Q70" in c.coureurs
        # coureurs : nationalité (CIO via P984), liste pour plusieurs, absente si le pays n'a pas de code, rider_id strict
        assert c.coureurs["Q1"]["nationalite"] == "BEL" and c.coureurs["Q1"]["naissance"] == "1930-01-02" and c.coureurs["Q1"]["naissance_precision"] == "jour"
        assert c.coureurs["Q2"]["nationalite"] == "FRA" and "nationalite" not in c.coureurs["Q3"] and c.coureurs["Q6"]["nationalite"] == ["BEL", "FRA"]
        assert c.coureurs["Q70"]["rider_id"] == "moderne-jean-19950505"                  # nom + date exacte, un seul candidat
        assert c.coureurs["Q1"]["rider_id"] == "dupont-jean-19300102"                    # "Jean Dupont" ≠ "Jean Dupond" : un seul nom concorde
        assert c.coureurs["Q4"]["rider_id"] == "martin-paul-19400506"                    # lien du cache Wikidata
        assert "rider_id" not in c.coureurs["Q2"]
        # reprise : rien à refaire, aucune requête
        n_avant = len(faux.log)
        res = run_historique(5, tmp, today + dt.timedelta(days=10), creer_api(faux), lambda: 0.0, series_cfg)
        assert res["series"] == 0 and len(faux.log) == n_avant, res
        # re-vérification après 180 jours
        res = run_historique(5, tmp, today + dt.timedelta(days=181), creer_api(faux), lambda: 0.0, series_cfg)
        assert res["series"] == 1 and len(faux.log) > n_avant
        # nouvelle clé d'une série déjà lue : éditions copiées SANS requête ; clé retirée du fichier de séries : éditions retirées du cache
        n_avant = len(faux.log)
        res = run_historique(5, tmp, today + dt.timedelta(days=1), creer_api(faux), lambda: 0.0,
                             {**series_cfg, "tour test troisieme nom|FRA": {"qid": "Q1000"}})
        assert res["series"] == 0 and len(faux.log) == n_avant, res
        c = Cache(os.path.join(ent, "historique"))
        assert c.editions["tour test troisieme nom|FRA"] == c.editions["tour test|FRA"] and "troisieme nom|FRA" in " ".join(c.etat["Q1000"]["cles"])
        res = run_historique(5, tmp, today + dt.timedelta(days=1), creer_api(faux), lambda: 0.0, {"tour test|FRA": {"qid": "Q1000"}})
        c = Cache(os.path.join(ent, "historique"))
        assert set(c.editions) == {"tour test|FRA"} and c.etat["Q1000"]["cles"] == ["tour test|FRA"], (set(c.editions), c.etat)
        res = run_historique(5, tmp, today + dt.timedelta(days=1), creer_api(faux), lambda: 0.0, {})                 # plus aucune série : cache d'éditions vidé
        assert not Cache(os.path.join(ent, "historique")).editions and not os.path.exists(os.path.join(ent, "historique", "editions", "t.json"))
        run_historique(5, tmp, today, creer_api(faux), lambda: 0.0, series_cfg)                                  # remet l'état pour la suite des tests
        # budget : budget épuisé avant toute série -> rien d'écrit, restantes
        tmpb = tempfile.mkdtemp(prefix="hist_b_")
        try:
            t = [0.0]

            def horloge_b():
                t[0] += 100.0
                return t[0]
            res = run_historique(1, tmpb, today, creer_api(FauxHist({**P, **E}, series)), horloge_b, series_cfg)
            assert res["series"] == 0 and res["restantes"] == 1 and not os.path.exists(os.path.join(tmpb, "entites", "historique", "etat.json"))
        finally:
            shutil.rmtree(tmpb, ignore_errors=True)
        # lecture incomplète (échec réseau en cours de série) : rien n'est écrit pour la série, retentée
        tmpc = tempfile.mkdtemp(prefix="hist_c_")
        try:
            faux_c = FauxHist({**P, **E}, series)
            vrai = faux_c.__call__
            etat_c = {"n": 0}

            def casse(base, p):
                etat_c["n"] += 1
                return None if p["action"] == "wbgetentities" and etat_c["n"] > 1 else vrai(base, p)
            res = run_historique(5, tmpc, today, creer_api(casse), lambda: 0.0, series_cfg)
            assert res["series"] == 0 and res["echecs"] == 1 and res["restantes"] == 1
            assert not os.path.exists(os.path.join(tmpc, "entites", "historique", "etat.json"))
        finally:
            shutil.rmtree(tmpc, ignore_errors=True)
        # pagination de la recherche (PAGE_RECHERCHE = 3 : 8 éditions en 3 pages)
        global PAGE_RECHERCHE
        ancien = PAGE_RECHERCHE
        PAGE_RECHERCHE = 3
        try:
            assert recherche_toutes(creer_api(FauxHist({**P, **E}, series)), "haswbstatement:P31=Q1000") == list(E)
        finally:
            PAGE_RECHERCHE = ancien

        # ------------------------------------------------------------ conteneur (championnat)
        EC = {"Q500": {"id": "Q500", "labels": {"fr": {"language": "fr", "value": "Championnats 1990"}},
                       "claims": {"P585": [wikidata._cl(wikidata._t("1990-06-24"))],
                                  "P527": [wikidata._cl(wikidata._eid("Q501")), wikidata._cl(wikidata._eid("Q502"))]}, "sitelinks": {}},
              "Q510": {"id": "Q510", "labels": {"fr": {"language": "fr", "value": "Championnats 1991"}},
                       "claims": {"P585": [wikidata._cl(wikidata._t("1991-06-24"))], "P527": [wikidata._cl(wikidata._eid("Q511"))]}, "sitelinks": {}},
              "Q501": {"id": "Q501", "labels": {"fr": {"language": "fr", "value": "Course en ligne masculine aux championnats de France 1990"}},
                       "claims": {"P1346": [_claim_p1346("Q1", "Q20882667")]}, "sitelinks": {}},
              "Q502": {"id": "Q502", "labels": {"fr": {"language": "fr", "value": "Course en ligne féminine aux championnats de France 1990"}},
                       "claims": {"P1346": [_claim_p1346("Q2", "Q20882667")]}, "sitelinks": {}},
              "Q511": {"id": "Q511", "labels": {"fr": {"language": "fr", "value": "Contre-la-montre masculin 1991"}}, "claims": {}, "sitelinks": {}}}
        ctx = Ctx(creer_api(FauxHist({**P, **EC}, {"Q2000": ["Q500", "Q510"]})), Cache(os.path.join(tmp, "x")), ent, today, 0)
        brut = {b["qid"] if not b["conteneur"] else b["conteneur"]: b for b in lire_editions(ctx, "Q2000", True)}
        assert brut["Q500"]["qid"] == "Q501" and brut["Q500"]["annee"] == 1990 and brut["Q500"]["date"] == "1990-06-24" and brut["Q500"]["rangs"][1] == ["Q1"]
        assert brut["Q510"]["detail_extra"]["raison"] == "course_en_ligne_masculine_introuvable" and brut["Q510"]["annee"] == 1991
        f = finaliser_edition(brut["Q510"], H, "x")
        assert f["statut"] == "inconnu" and f["detail"]["raison"] == "course_en_ligne_masculine_introuvable"
        f = finaliser_edition(brut["Q500"], H, "x")
        assert f["statut"] == "ok" and f["qid"] == "Q501" and f["qid_conteneur"] == "Q500"

        # ------------------------------------------------------------ preuve de série : acceptée / refusée
        carte = lambda an, rid, nom: {"season": an, "start_date": f"{an}-07-01", "podium": [{"rank": 1, "id": rid, "name": nom}]}   # noqa: E731
        collector._dump(os.path.join(ent, "courses", "t.json"), {
            "tour test|FRA": {"editions": [carte(2022, "moderne-jean-19950505", "Jean Moderne"), carte(2023, "moderne-jean-19950505", "Jean Moderne"),
                                           carte(2024, "autre-gars-19900101", "Autre Gars")]},
            "faux tour|FRA": {"editions": [carte(2022, "autre-gars-19900101", "Autre Gars"), carte(2023, "moderne-jean-19950505", "Jean Moderne")]},
            "seul tour|FRA": {"editions": [carte(2022, "moderne-jean-19950505", "Jean Moderne")]}})
        ctx = Ctx(creer_api(FauxHist({**P, **E}, series)), Cache(os.path.join(tmp, "y")), ent, today, 0)
        nos = nos_vainqueurs(ent)
        ret, ref = verifier_series(ctx, {"tour test|FRA": "Q1000", "faux tour|FRA": "Q1000", "seul tour|FRA": "Q1000"}, nos)
        assert set(ret) == {"tour test|FRA"} and ret["tour test|FRA"]["preuve"]["annees"] == [2022, 2023] and ret["tour test|FRA"]["preuve"]["discordantes"] == [2024], ret
        assert ref["faux tour|FRA"]["raison"] == "preuve_insuffisante" and ref["faux tour|FRA"]["concordances"] == 1, ref
        assert ref["seul tour|FRA"]["raison"] == "moins_de_2_editions_2019_2025"
        # le cache Wikidata tranche : rider_id lié à un autre QID -> pas de concordance même si nom et naissance concordent
        collector._dump(os.path.join(ent, "wikidata", "coureurs.json"), {"moderne-jean-19950505": {"qid": "Q1234", "verifie": "2026-01-01"}})
        ctx2 = Ctx(creer_api(FauxHist({**P, **E}, series)), Cache(os.path.join(tmp, "z")), ent, today, 0)
        assert verifier_series(ctx2, {"tour test|FRA": "Q1000"}, nos)[0] == {}
        # proposition automatique : recherche par nom + classe de la série + même preuve
        P2 = dict(P, Q1000={"id": "Q1000", "labels": {}, "claims": {"P31": [wikidata._cl(wikidata._eid("Q2912397"))]}},
                  Q2912397={"id": "Q2912397", "labels": {}, "claims": {"P279": [wikidata._cl(wikidata._eid(COURSE_CYCLISTE))]}},
                  Q777={"id": "Q777", "labels": {}, "claims": {"P31": [wikidata._cl(wikidata._eid("Q4167410"))]}}, Q4167410={"id": "Q4167410", "labels": {}, "claims": {}},
                  Q1000000={"id": "Q1000000", "labels": {}, "claims": {}})
        faux_p = FauxHist({**P2, **E}, {"Q1000": list(E), "Q777": list(E)}, {"Tour Test": ["Q777", "Q1000"], "Faux Tour": ["Q1000"]})
        ctx3 = Ctx(creer_api(faux_p), Cache(os.path.join(tmp, "w")), ent, today, 0)
        collector._dump(os.path.join(ent, "wikidata", "coureurs.json"), {})
        ctx3._wd = {}
        fiches = {"tour test|FRA": {"noms": {"Tour Test": [2022, 2023, 2024]}, "editions": [1, 2, 3]},
                  "faux tour|FRA": {"noms": {"Faux Tour": [2022, 2023]}, "editions": [1, 2]}}
        collector._dump(os.path.join(ent, "courses", "t.json"), {
            "tour test|FRA": dict(fiches["tour test|FRA"], editions=[carte(2022, "moderne-jean-19950505", "Jean Moderne"), carte(2023, "moderne-jean-19950505", "Jean Moderne")]),
            "faux tour|FRA": dict(fiches["faux tour|FRA"], editions=[carte(2022, "autre-gars-19900101", "Autre Gars"), carte(2023, "moderne-jean-19950505", "Jean Moderne")])})
        ret, ref = proposer_series(ctx3, ent)
        assert ret["tour test|FRA"]["qid"] == "Q1000" and "faux tour|FRA" in ref and ref["faux tour|FRA"]["raison"] == "preuve_insuffisante", (ret, ref)
        assert ref["faux tour|FRA"]["candidats"] == {"Q1000": "preuve_insuffisante"}
        assert noms_recherche({"noms": {"Bretagne Classic - Ouest-France": [2022], "56° Giro X": [2019]}}) == ["Bretagne Classic - Ouest-France", "Bretagne Classic", "Giro X"]
        assert charger_series(os.path.join(tmp, "absent.json")) == {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---------------------------------------------------------------- appliquer_historique (fusion avec nos données)
    hist = {"editions": {
        "tour test|FRA": [
            {"annee": 1903, "qid": "Q101", "date": "1903-07-01", "vainqueur": "Q1", "podium": [{"rang": 1, "qid": "Q1"}, {"rang": 2, "qid": "Q2"}, {"rang": 3, "qid": "Q3"}],
             "statut": "ok", "wikipedia": {"fr": "Course 1903"}, "verifie": "2026-11-16"},
            {"annee": 1904, "qid": "Q102", "vainqueur": "Q1", "podium": [{"rang": 1, "qid": "Q1"}], "statut": "ok", "verifie": "x"},
            {"annee": 1999, "qid": "Q103", "podium": [{"rang": 2, "qid": "Q2"}], "statut": "non_attribue", "detail": {"p2321": ["Q4"]}, "verifie": "x"},
            {"annee": 2022, "qid": "Q105", "vainqueur": "Q70", "podium": [{"rang": 1, "qid": "Q70"}], "statut": "ok", "verifie": "x"},
            {"annee": 2015, "qid": "Q106", "vainqueur": "Q70", "podium": [{"rang": 1, "qid": "Q70"}], "statut": "ok", "verifie": "x"}],
        "tour test ancien nom|FRA": [
            {"annee": 1903, "qid": "Q101", "vainqueur": "Q1", "podium": [{"rang": 1, "qid": "Q1"}], "statut": "ok", "verifie": "x"},
            {"annee": 2023, "qid": "Q109", "vainqueur": "Q70", "podium": [{"rang": 1, "qid": "Q70"}], "statut": "ok", "verifie": "x"}],
        "absent|FRA": [{"annee": 1950, "qid": "Q9", "vainqueur": "Q1", "podium": [], "statut": "ok", "verifie": "x"}]},
        "coureurs": {"Q1": {"nom": "Jean Dupont", "naissance": "1930-01-02", "naissance_precision": "jour", "nationalite": "BEL", "verifie": "x"},
                     "Q2": {"nom": "Luc Durand", "nationalite": ["BEL", "FRA"], "verifie": "x"}, "Q3": {"nom": "Ana Lopez", "verifie": "x"},
                     "Q4": {"nom": "Paul Martin", "rider_id": "martin-paul-19400506", "verifie": "x"},
                     "Q70": {"nom": "Jean Moderne", "rider_id": "moderne-jean-alias", "verifie": "x"}}}
    ed_uci = lambda an, rid, nom, nat: {"season": an, "start_date": f"{an}-07-01", "podium": [{"rank": 1, "id": rid, "name": nom, "nat": nat, "flag": "fr"}]}   # noqa: E731
    courses = {"tour test|FRA": {"editions": [ed_uci(2022, "moderne-jean-1995", "Jean Moderne", "BEL"), ed_uci(2025, "moderne-jean-1995", "Jean Moderne", "BEL")]},
               "tour test ancien nom|FRA": {"editions": [ed_uci(2019, "moderne-jean-1995", "Jean Moderne", "BEL")]}}
    coureurs = {"moderne-jean-1995": {"name": "Jean Moderne", "nationality": "BEL", "flag": "be"}, "martin-paul-19400506": {"name": "Paul Martin", "nationality": "BEL", "flag": "be"}}
    out = appliquer_historique(hist, courses, coureurs, {"moderne-jean-alias": "moderne-jean-1995"}, {})
    h = out["par_cle"]["tour test|FRA"]["historique"]
    assert [x["annee"] for x in h] == [2015, 1999, 1904, 1903], [x["annee"] for x in h]       # 2022 présent en UCI ; 2023 couvert par une clé sœur (même série)
    assert h[3]["vainqueur"] == "wd-Q1" and h[3]["podium"][0] == {"rang": 1, "id": "wd-Q1", "name": "Jean Dupont", "nat": "BEL", "flag": "be"}
    assert h[3]["podium"][1] == {"rang": 2, "id": "wd-Q2", "name": "Luc Durand"}                # nationalités multiples : ni nat ni flag
    assert h[0]["vainqueur"] == "moderne-jean-1995"                                            # rattaché via l'alias de rider_id
    assert h[1]["statut"] == "non_attribue" and "vainqueur" not in h[1] and h[1]["detail"]["p2321"][0]["id"] == "martin-paul-19400506"
    assert h[3]["source_qid"] == "Q101" and h[3]["wikipedia"] == {"fr": "Course 1903"}
    assert "absent|FRA" not in out["par_cle"]
    assert out["par_cle"]["tour test|FRA"]["info"] == {"source": "wikidata", "annees": [1903, 2015], "editions": 4}
    rec = out["par_cle"]["tour test|FRA"]["records"]
    assert rec["annees_couvertes"] == [1903, 2025] and rec["editions_avec_vainqueur"] == 5 and rec["non_attribuees"] == 1, rec
    assert rec["victoires_par_coureur"][0] == {"id": "moderne-jean-1995", "name": "Jean Moderne", "wins": 3} and \
        {"id": "wd-Q1", "name": "Jean Dupont", "wins": 2} in rec["victoires_par_coureur"], rec["victoires_par_coureur"]
    assert rec["victoires_par_pays"] == {"BEL": 5}
    assert out["attaches"]["moderne-jean-1995"] == [{"annee": 2023, "course": "tour test ancien nom|FRA", "rang": 1, "source_qid": "Q109"},
                                                     {"annee": 2015, "course": "tour test|FRA", "rang": 1, "source_qid": "Q106"}], out["attaches"]
    assert "martin-paul-19400506" not in out["attaches"]                                      # Q4 n'est que dans un détail (pas de palmarès)
    leger = out["legers"]["wd-Q1"]
    assert len(leger["palmares_historique"]) == 2 and leger["totaux"] == {"wins": 2, "podiums": 2} and leger["source"] == "wikidata" and leger["wikidata"]["qid"] == "Q1" and leger["nationality"] == "BEL"
    assert "wd-Q4" not in out["legers"] and "wd-Q70" not in out["legers"] and "wd-Q3" in out["legers"]     # Q4 / Q70 : nos coureurs
    assert {"n": "Jean Dupont", "t": "c", "id": "wd-Q1", "f": "be", "y": [1903, 1904]} in out["recherche"]
    assert out["rapport"]["editions_historiques"] == 6 and out["rapport"]["coureurs_legers"] == 3
    # éditions annoncées : jamais publiées (date postérieure au jour, ou année postérieure sans date)
    assert edition_future({"annee": 2027, "date": "2027-07-02"}, "2026-11-16") and edition_future({"annee": 2028, "date": "2028"}, "2026-11-16")
    assert edition_future({"annee": 2027}, "2026-11-16") and not edition_future({"annee": 2026, "date": "2026"}, "2026-11-16")
    assert edition_future({"annee": 2026, "date": "2026-12"}, "2026-11-16") and not edition_future({"annee": 2026, "date": "2026-11"}, "2026-11-16")
    assert not edition_future({"annee": 2027}, None)
    hist_f = {"editions": {"tour test|FRA": [{"annee": 2027, "qid": "Q200", "date": "2027-07-02", "statut": "inconnu", "verifie": "x"},
                                             {"annee": 1904, "qid": "Q102", "vainqueur": "Q1", "podium": [{"rang": 1, "qid": "Q1"}], "statut": "ok", "verifie": "x"}]},
              "coureurs": hist["coureurs"]}
    assert [x["annee"] for x in appliquer_historique(hist_f, courses, coureurs, {}, {}, "2026-11-16")["par_cle"]["tour test|FRA"]["historique"]] == [1904]
    assert [x["annee"] for x in appliquer_historique(hist_f, courses, coureurs, {}, {})["par_cle"]["tour test|FRA"]["historique"]] == [2027, 1904]
    out2 = appliquer_historique({"editions": {}, "coureurs": {}}, courses, coureurs, {}, {})
    assert out2["par_cle"] == {} and out2["legers"] == {}
    print("[OK] historique.py : tests locaux réussis")


def _test_429() -> None:
    """netutil.fetch_text(attendre_429=True) : Retry-After respecté, hôte conservé ; sans l'option : comportement historique (hôte abandonné)."""
    import io
    import urllib.error
    import urllib.request

    class Rep:
        def __init__(self, corps: bytes):
            self.corps = corps
            self.headers = type("H", (), {"get_content_charset": lambda s: "utf-8"})()

        def read(self):
            return self.corps

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    appels: List[float] = []
    dormis: List[float] = []

    def faux_urlopen(req, timeout=0):
        appels.append(1)
        if len(appels) <= 2:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {"Retry-After": "7"}, io.BytesIO(b"too many"))  # type: ignore[arg-type]
        return Rep(b'{"ok": 1}')
    vrai_urlopen, vrai_sleep, vrai_wait = urllib.request.urlopen, time.sleep, netutil._wait_for_host
    urllib.request.urlopen, time.sleep, netutil._wait_for_host = faux_urlopen, lambda s: dormis.append(s), lambda h: None
    try:
        assert netutil.fetch_json("https://exemple.test/a", attendre_429=True) == {"ok": 1}
        assert dormis == [7.0, 7.0] and "exemple.test" not in netutil._blocked_hosts, dormis
        appels.clear()
        assert netutil.fetch_json("https://exemple2.test/a") is None and "exemple2.test" in netutil._blocked_hosts   # défaut : hôte abandonné
        netutil._blocked_hosts.discard("exemple2.test")
        appels.clear()
        dormis.clear()
        netutil.MAX_REPRISES_429, ancien = 2, netutil.MAX_REPRISES_429
        urllib.request.urlopen = lambda req, timeout=0: (_ for _ in ()).throw(urllib.error.HTTPError(req.full_url, 429, "x", {}, io.BytesIO(b"x")))  # type: ignore[arg-type]
        try:
            assert netutil.fetch_json("https://exemple3.test/a", attendre_429=True) is None and "exemple3.test" not in netutil._blocked_hosts
            assert dormis == [15.0, 15.0], dormis    # sans en-tête Retry-After : 15 s
        finally:
            netutil.MAX_REPRISES_429 = ancien
        assert netutil._retry_after("abc") == 15.0 and netutil._retry_after("9999") == netutil.MAX_ATTENTE_429 and netutil._retry_after(None) == 15.0
    finally:
        urllib.request.urlopen, time.sleep, netutil._wait_for_host = vrai_urlopen, vrai_sleep, vrai_wait


def main() -> None:
    ap = argparse.ArgumentParser(description="Historique (palmarès Wikidata) : alimente entites/historique/ (cache seul)")
    ap.add_argument("archives_dir", nargs="?")
    ap.add_argument("--budget-min", type=float, default=300)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--verifier-series", metavar="CANDIDATS", help="JSON {clé: QID | {qid, conteneur}} : preuve de chaque série, écrit series_historiques(.json / _refusees.json)")
    ap.add_argument("--proposer", action="store_true", help="étend series_historiques.json aux épreuves suivies (même preuve)")
    ap.add_argument("--sortie", default=None, help="dossier d'écriture des fichiers de séries (défaut : racine du code)")
    a = ap.parse_args()
    if a.test or not a.archives_dir:
        _tests()
        if not a.test:
            ap.error("archives_dir obligatoire")
        return
    entites = os.path.join(a.archives_dir, "entites")
    if a.verifier_series or a.proposer:
        sortie = a.sortie or collector.RACINE
        f_ret, f_ref = os.path.join(sortie, "series_historiques.json"), os.path.join(sortie, "series_historiques_refusees.json")
        ctx = Ctx(creer_api(), Cache(os.path.join(entites, "historique")), entites, dt.date.today(), a.budget_min)
        try:
            if a.verifier_series:
                cand = collector._load(a.verifier_series, {})
                ret, ref = verifier_series(ctx, cand, nos_vainqueurs(entites, cand))
                ecrire_series(ret, ref, f_ret, f_ref)
            else:
                deja = collector._load(f_ret, {})
                ret, ref = proposer_series(ctx, entites, deja=list(deja) + list(collector._load(f_ref, {})))
                ecrire_series({**deja, **ret}, {**collector._load(f_ref, {}), **ref}, f_ret, f_ref)
        except HoteAbandonne as e:
            print(f"[WARN] [HISTORIQUE] interrompu ({e})")
            return
        print(f"[HISTORIQUE] séries retenues : {len(ret)}, refusées : {len(ref)}, {ctx.api.requetes} requête(s) en {ctx.minutes():.1f} min")
        for k, v in sorted(ref.items()):
            print(f"  refusée {k} : {v.get('raison')} {json.dumps({x: y for x, y in v.items() if x not in ('raison', 'verifie')}, ensure_ascii=False)}")
        return
    run_historique(a.budget_min, a.archives_dir)


if __name__ == "__main__":
    main()
