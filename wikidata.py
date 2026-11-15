#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wikidata et Wikimedia Commons pour l'encyclopédie (étape E1b) : rapprochements STRICTS, cache dans `entites/wikidata/`.

Aucun fait n'est inventé : un coureur ou une équipe n'est relié à Wikidata que si une preuve précise le permet ; sinon la
valeur `null` est mise en cache (re-tentée plus tard). Wikidata est en CC0 ; les images viennent de Commons avec auteur et
licence lus sur Commons (pas de licence lisible = pas d'image).

Fichiers de `ARCHIVES_DIR/entites/wikidata/` (écrits au fil de l'eau, reprenables) :
    coureurs.json  {rider_id: {"qid": QID|null, "verifie": AAAA-MM-JJ, ...}}   (null : "raison" = aucune | ambigu)
    images.json    {nom de fichier Commons: {"url", "page", "auteur"?, "licence", "licence_url"?, "verifie"} | {"url": null, "raison", "verifie"}}
    equipes.json   {id d'équipe-saison: {"qid": QID|null, "preuve", "verifie"}}
    lignees.json   {QID: {"libelle", "noms", "codes", "pays", "classes", "sitelinks", "logo", "verifie"}}
    libelles.json  {QID: libellé fr, sinon en | null}   (lieux, équipes de carrière, pays, classes)

Règles (docs/recherche/encyclopedie_sources.md, E1b) :
- COUREUR retenu seulement si, parmi les candidats trouvés par la recherche « nom + occupation cycliste » (CirrusSearch
  `haswbstatement:P106=Q2309784`), UN SEUL candidat vérifié a (1) une date de naissance P569 à précision jour ÉGALE à la nôtre,
  (2) un nom concordant (jetons normalisés d'un libellé ou alias, toutes langues, égaux aux nôtres dans n'importe quel ordre ; ou jetons
  Wikidata (au moins 2) strictement inclus dans les nôtres), (3) une occupation cycliste (P106 = Q2309784 ou sous-classe par P279). Sans date
  de naissance : jamais rapproché. Deux candidats vérifiés (homonymes de même date) : rien.
- ÉQUIPE-SAISON (avec `code_uci`) : éléments portant `haswbstatement:P1998=<code>` ; les éléments « saison » remontent à leur parent par
  P5138 ; parent retenu seulement si (i) une déclaration P1998 du parent vaut le code avec une période DATÉE (P580/P582, à l'année) qui contient
  la saison, ET (ii) un nom officiel P1448 daté valable cette année, ou le libellé d'un élément saison de ce parent contenant l'année, concorde avec
  notre libellé (jetons égaux, ou l'un inclus dans l'autre avec au moins 2 jetons), ET (iii) un seul parent satisfait. Équipes sans code ou non
  prouvées : seul `alias_equipes.json` (manuel) peut les rattacher.
- Politesse : 1 requête/s par hôte, User-Agent du projet (netutil), pas de `maxlag`, abandon de l'hôte sur 403/429.

    python wikidata.py --test
    python wikidata.py <archives_dir> [--budget-min N]       (équivaut à run_pipeline.py --wikidata ; n'écrit que le cache)
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import collector
import netutil

WD_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HOTES = ("www.wikidata.org", "commons.wikimedia.org")
OCC_CYCLISTE = "Q2309784"                 # « cycliste » : vérifié au lancement (libellé), les sous-classes passent par P279
SITES = {"fr": "frwiki", "en": "enwiki", "es": "eswiki", "it": "itwiki", "nl": "nlwiki", "de": "dewiki"}
SITEFILTER = "|".join(SITES.values())
LOT = 50                                  # wbgetentities / Commons : 50 ids ou titres par requête
LOT_COUREURS = 40                         # coureurs résolus par tranche (une recherche chacun, puis lectures par lots de 50)
LOT_CODES = 20
ECRIRE_TOUS = 200                         # cache écrit au moins tous les N coureurs résolus (arrêt brutal sans perte)
JOURS_VERIF = 180                         # re-vérification d'une correspondance
JOURS_NULL = 60                           # `null` re-tenté après ce délai
PART_EQUIPES = 0.5                        # part maximale du budget pour les équipes (les coureurs ont le reste)
MAX_ECHECS = 8                            # échecs consécutifs avant d'abandonner le passage
PROFONDEUR_P279 = 4
FALLBACK_LIBRE = False                    # 2e recherche sans filtre d'occupation si aucun candidat (coûte ~1 requête de plus par coureur obscur)
MOTS_SAISON = {"season", "saison", "stagione", "temporada", "seizoen", "sezon", "sasong"}
FICHIERS = ("coureurs", "equipes", "lignees", "images", "libelles")


class HoteAbandonne(Exception):
    """Hôte refusé (403/429/challenge) ou trop d'échecs consécutifs : le passage s'arrête, le cache déjà écrit est conservé."""


# --------------------------------------------------------------------------- accès réseau

def _fetch_reseau(base: str, params: Dict[str, Any]) -> Optional[Any]:
    return netutil.fetch_json(base + "?" + urllib.parse.urlencode(params), retries=2)


class Api:
    """Accès MediaWiki. `fetch(base, params) -> dict|None` est injectable (tests : réponses simulées)."""

    def __init__(self, fetch: Optional[Callable[[str, Dict[str, Any]], Optional[Any]]] = None):
        self.fetch = fetch or _fetch_reseau
        self.requetes = 0
        self.echecs = 0

    def appel(self, base: str, **params: Any) -> Optional[Dict[str, Any]]:
        hote = urllib.parse.urlparse(base).netloc
        if hote in netutil._blocked_hosts:
            raise HoteAbandonne(hote)
        params.setdefault("format", "json")
        rep = self.fetch(base, params)
        self.requetes += 1
        if hote in netutil._blocked_hosts:
            raise HoteAbandonne(hote)
        if not isinstance(rep, dict) or "error" in rep:
            self.echecs += 1
            print(f"[WARN] Wikimedia : requête échouée ({params.get('action')}/{params.get('list') or params.get('prop') or ''})")
            if self.echecs >= MAX_ECHECS:
                raise HoteAbandonne("trop d'échecs consécutifs")
            return None
        self.echecs = 0
        return rep


def preparer_reseau() -> None:
    for h in HOTES:
        netutil.HOST_DELAYS[h] = 1.0


# --------------------------------------------------------------------------- cache

class Cache:
    def __init__(self, dossier: str):
        self.dossier = dossier
        self.d: Dict[str, Dict[str, Any]] = {}
        for n in FICHIERS:
            v = collector._load(os.path.join(dossier, n + ".json"), {})
            self.d[n] = v if isinstance(v, dict) else {}

    def ecrire(self) -> int:
        n = 0
        for nom in FICHIERS:
            chemin = os.path.join(self.dossier, nom + ".json")
            if not self.d[nom] and not os.path.exists(chemin):
                continue
            n += bool(collector._dump_if_changed(chemin, dict(sorted(self.d[nom].items())), ignore=()))
        return n


def charger_cache(dossier: str) -> Dict[str, Dict[str, Any]]:
    """Cache en lecture (pour encyclopedie.construire) : {fichier: dict}, dicts vides si absent."""
    return Cache(dossier).d


def besoin(entree: Any, aujourdhui: dt.date, cle: str = "qid") -> bool:
    """Vrai si l'entrée est absente, sans date, ou périmée (correspondance > 180 jours, `null` > 60 jours)."""
    if not isinstance(entree, dict):
        return True
    d = collector._date(entree.get("verifie"))
    if d is None:
        return True
    return (aujourdhui - d).days > (JOURS_VERIF if entree.get(cle) else JOURS_NULL)


# --------------------------------------------------------------------------- lecture des revendications (fonctions pures)

def revendications(e: Optional[Dict[str, Any]], prop: str) -> List[Dict[str, Any]]:
    """Déclarations d'une propriété, hors « deprecated », rang préféré d'abord."""
    cs = [c for c in ((e or {}).get("claims") or {}).get(prop, []) if c.get("rank") != "deprecated"]
    return sorted(cs, key=lambda c: 0 if c.get("rank") == "preferred" else 1)


def valeur(c: Dict[str, Any]) -> Any:
    return ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")


def qid_de(c: Dict[str, Any]) -> Optional[str]:
    v = valeur(c)
    return v.get("id") if isinstance(v, dict) and re.fullmatch(r"Q\d+", str(v.get("id") or "")) else None


def parse_temps(v: Any) -> Optional[Tuple[str, int]]:
    """Valeur « time » de Wikidata -> ('AAAA-MM-JJ', précision) ; None si illisible ou avant J.-C."""
    if not isinstance(v, dict):
        return None
    m = re.fullmatch(r"\+(\d{1,})-(\d\d)-(\d\d)T.*", str(v.get("time") or ""))
    if not m:
        return None
    return f"{int(m.group(1)):04d}-{m.group(2)}-{m.group(3)}", int(v.get("precision") or 0)


def date_texte(t: Optional[Tuple[str, int]]) -> Optional[str]:
    """'AAAA' (précision année), 'AAAA-MM' (mois), 'AAAA-MM-JJ' (jour) ; None si précision insuffisante."""
    if not t or t[1] < 9:
        return None
    return t[0][:{9: 4, 10: 7}.get(t[1], 10)]


def precision_texte(t: Optional[Tuple[str, int]]) -> Optional[str]:
    return None if not t or t[1] < 9 else {9: "annee", 10: "mois"}.get(t[1], "jour")


def qualif_temps(c: Dict[str, Any], prop: str) -> Optional[Tuple[str, int]]:
    for s in (c.get("qualifiers") or {}).get(prop, []):
        t = parse_temps((s.get("datavalue") or {}).get("value"))
        if t:
            return t
    return None


def bornes(c: Dict[str, Any]) -> Tuple[Optional[Tuple[str, int]], Optional[Tuple[str, int]]]:
    return qualif_temps(c, "P580"), qualif_temps(c, "P582")


def periode_contient(c: Dict[str, Any], saison: int) -> bool:
    """Période DATÉE (au moins une borne exploitable à l'année) qui contient `saison`. Sans borne : non."""
    d, f = bornes(c)
    ya = int(d[0][:4]) if d and d[1] >= 9 else None
    yf = int(f[0][:4]) if f and f[1] >= 9 else None
    if ya is None and yf is None:
        return False
    return (ya is None or ya <= saison) and (yf is None or saison <= yf)


def naissance_jour(e: Dict[str, Any]) -> Optional[str]:
    """Date de naissance à précision jour ; None si absente, imprécise ou contradictoire entre déclarations."""
    jours = set()
    for c in revendications(e, "P569"):
        t = parse_temps(valeur(c))
        if t and t[1] >= 11:
            jours.add(t[0])
    return next(iter(jours)) if len(jours) == 1 else None


def noms_entite(e: Dict[str, Any]) -> List[str]:
    """Libellés et alias de toutes les langues."""
    out = [v.get("value") for v in (e.get("labels") or {}).values() if isinstance(v, dict)]
    for lst in (e.get("aliases") or {}).values():
        out += [a.get("value") for a in lst if isinstance(a, dict)]
    return [n for n in out if n]


def jetons(s: str) -> List[str]:
    return netutil.normalize(s).split()


def nom_concorde(notre: str, candidats: Iterable[str]) -> bool:
    """Jetons égaux (ordre indifférent), ou jetons Wikidata (au moins 2) strictement inclus dans les nôtres."""
    nous = jetons(notre)
    if not nous:
        return False
    sn = set(nous)
    for c in candidats:
        j = jetons(c)
        if not j:
            continue
        if sorted(j) == sorted(nous) or (len(set(j)) >= 2 and set(j) < sn):
            return True
    return False


def nom_equipe_concorde(notre: str, candidat: str) -> bool:
    """Jetons égaux, ou l'un inclus dans l'autre avec au moins 2 jetons pour le plus petit."""
    a, b = set(jetons(notre)), set(jetons(candidat))
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 2 and (a <= b or b <= a))


def libelle_langue(e: Optional[Dict[str, Any]]) -> Optional[str]:
    lab = (e or {}).get("labels") or {}
    return ((lab.get("fr") or lab.get("en") or {}).get("value")) or None


# --------------------------------------------------------------------------- requêtes groupées

def recherche(api: Api, requete: str, limite: int = 10) -> Optional[List[str]]:
    rep = api.appel(WD_API, action="query", list="search", srsearch=requete, srlimit=limite, srnamespace=0)
    if rep is None:
        return None
    return [r["title"] for r in (rep.get("query") or {}).get("search", []) if re.fullmatch(r"Q\d+", str(r.get("title") or ""))]


def lire_entites(api: Api, ids: Iterable[str], props: str, langues: Optional[str] = None) -> Dict[str, Optional[Dict[str, Any]]]:
    """wbgetentities par lots de 50. {qid: entité | None (inexistante)} ; un id absent du résultat = lecture échouée."""
    out: Dict[str, Optional[Dict[str, Any]]] = {}
    ids = list(dict.fromkeys(i for i in ids if i))
    for i in range(0, len(ids), LOT):
        p: Dict[str, Any] = dict(action="wbgetentities", ids="|".join(ids[i:i + LOT]), props=props)
        if "sitelinks" in props:
            p["sitefilter"] = SITEFILTER
        if langues:
            p["languages"] = langues
        rep = api.appel(WD_API, **p)
        if rep is None:
            continue
        for q, e in (rep.get("entities") or {}).items():
            out[q] = None if (not isinstance(e, dict) or "missing" in e) else e
    return out


def charger_libelles(api: Api, cache: Cache, qids: Iterable[str]) -> None:
    manque = [q for q in dict.fromkeys(qids) if q and q not in cache.d["libelles"]]
    for q, e in lire_entites(api, manque, "labels", "fr|en").items():
        cache.d["libelles"][q] = libelle_langue(e)


class Sousclasses:
    """« Cette occupation est-elle un cycliste ? » : OCC_CYCLISTE lui-même ou sous-classe (P279, 4 niveaux), mémorisé."""

    def __init__(self, api: Api, racine: str = OCC_CYCLISTE):
        self.api, self.racine = api, racine
        self.memo: Dict[str, bool] = {racine: True}

    def est(self, q: str) -> bool:
        if q in self.memo:
            return self.memo[q]
        vus = {q}
        front = [q]
        trouve = False
        for _ in range(PROFONDEUR_P279):
            ents = lire_entites(self.api, front, "claims")
            suivants = []
            for x in front:
                for c in revendications(ents.get(x), "P279"):
                    p = qid_de(c)
                    if p == self.racine or self.memo.get(p):
                        trouve = True
                    elif p and p not in vus and p not in self.memo:
                        vus.add(p)
                        suivants.append(p)
            if trouve or not suivants:
                break
            front = suivants
        self.memo[q] = trouve
        return trouve


# --------------------------------------------------------------------------- coureurs

def est_cycliste(e: Dict[str, Any], sous: Sousclasses) -> bool:
    return any(q and sous.est(q) for q in (qid_de(c) for c in revendications(e, "P106")))


def candidat_valide(e: Optional[Dict[str, Any]], nom: str, naissance: str, sous: Sousclasses) -> bool:
    if not e or naissance_jour(e) != naissance:
        return False
    return nom_concorde(nom, noms_entite(e)) and est_cycliste(e, sous)


def choisir_coureur(candidats: Dict[str, Optional[Dict[str, Any]]], nom: str, naissance: str, sous: Sousclasses) -> Tuple[Optional[str], str]:
    """(qid, raison) : un seul candidat vérifié -> 'ok' ; aucun -> 'aucune' ; plusieurs -> 'ambigu'."""
    valides = [q for q, e in candidats.items() if candidat_valide(e, nom, naissance, sous)]
    if len(valides) == 1:
        return valides[0], "ok"
    return None, ("ambigu" if valides else "aucune")


def _fichier(nom: str) -> str:
    return " ".join(str(nom).replace("_", " ").split())


def _choisir_valeur(cs: List[Dict[str, Any]]) -> Any:
    """Valeur du premier rang préféré, sinon de la première déclaration ; None s'il n'y en a pas."""
    return valeur(cs[0]) if cs else None


def taille_metres(e: Dict[str, Any]) -> Optional[float]:
    vals = set()
    for c in revendications(e, "P2048"):
        v = valeur(c)
        if not isinstance(v, dict):
            continue
        try:
            x = float(str(v.get("amount")))
        except ValueError:
            continue
        unite = str(v.get("unit") or "").rsplit("/", 1)[-1]
        x = x if unite == "Q11573" else x / 100 if unite == "Q174728" else None
        if x is not None and 1.2 <= x <= 2.4:
            vals.add(round(x, 2))
    return next(iter(vals)) if len(vals) == 1 else None


def sitelinks(e: Dict[str, Any]) -> Dict[str, str]:
    sl = e.get("sitelinks") or {}
    return {lg: sl[site]["title"] for lg, site in SITES.items() if isinstance(sl.get(site), dict) and sl[site].get("title")}


def _sans_vide(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v not in (None, {}, [], "")}


def qids_a_libeller(e: Dict[str, Any]) -> List[str]:
    return [q for p in ("P19", "P54") for q in (qid_de(c) for c in revendications(e, p)) if q]


def extraire_coureur(e: Dict[str, Any], libelles: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """Champs conservés (clés absentes si inconnues) : lieu de naissance, taille (m), image P18, sitelinks, équipes P54 datées."""
    lieu = next(((q, libelles.get(q)) for q in (qid_de(c) for c in revendications(e, "P19")) if q), None)
    img = _choisir_valeur(revendications(e, "P18"))
    equipes = []
    for c in revendications(e, "P54"):
        q = qid_de(c)
        if not q:
            continue
        d, f = bornes(c)
        equipes.append(_sans_vide({"qid": q, "libelle": libelles.get(q), "debut": date_texte(d), "fin": date_texte(f),
                                   "precision_debut": precision_texte(d), "precision_fin": precision_texte(f)}))
    equipes.sort(key=lambda x: (x.get("debut") or "9999", x.get("fin") or "9999", x["qid"]))
    return _sans_vide({"lieu": _sans_vide({"qid": lieu[0], "libelle": lieu[1]}) if lieu else None, "taille": taille_metres(e),
                       "image": _fichier(img) if isinstance(img, str) and img.strip() else None,
                       "sitelinks": sitelinks(e), "equipes": equipes})


def requetes_coureur(nom: str) -> List[Tuple[str, str]]:
    """[(type, texte)] : nom complet avec filtre d'occupation ; nom sans son dernier jeton (noms composés : « Jonas Vingegaard Hansen » ->
    « Jonas Vingegaard ») pour 3 jetons ou plus ; recherche libre seulement si FALLBACK_LIBRE et qu'aucun candidat n'est apparu."""
    j = nom.split()
    out = [("filtre", nom)]
    if len(j) >= 3:
        out.append(("filtre", " ".join(j[:-1])))
    if FALLBACK_LIBRE:
        out.append(("libre", nom))
    return out


def _texte_requete(typ: str, nom: str) -> str:
    return f"{nom} haswbstatement:P106={OCC_CYCLISTE}" if typ == "filtre" else nom


def resoudre_tranche(ctx: "Contexte", tranche: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Résout une tranche de coureurs : une recherche chacun (+ rondes de repli rares), puis lectures GROUPÉES par lots de 50.
    Renvoie {rider_id: entrée de cache}. Un coureur dont une lecture a échoué n'est pas renvoyé (retenté au prochain passage)."""
    api, today = ctx.api, ctx.aujourdhui.isoformat()
    etat: Dict[str, Dict[str, Any]] = {f["id"]: {"f": f, "res": None, "vu": False, "echec": False,
                                                  "rondes": requetes_coureur(f["name"])} for f in tranche}
    sortie: Dict[str, Dict[str, Any]] = {}
    ents_tous: Dict[str, Optional[Dict[str, Any]]] = {}
    for i in range(max(len(s["rondes"]) for s in etat.values())):
        actifs = [r for r, s in etat.items() if s["res"] is None and not s["echec"] and i < len(s["rondes"])
                  and (s["rondes"][i][0] != "libre" or not s["vu"])]
        if actifs and i > 0 and ctx.hors_budget():
            for rid in actifs:                    # ronde de repli non tentée : on ne conclut pas « aucune » (retenté plus tard)
                etat[rid]["echec"] = True
            continue
        if not actifs:
            continue
        cands: Dict[str, List[str]] = {}
        for rid in actifs:
            typ, nom = etat[rid]["rondes"][i]
            res = recherche(api, _texte_requete(typ, nom))
            if res is None:
                etat[rid]["echec"] = True
                continue
            cands[rid] = res
            etat[rid]["vu"] = etat[rid]["vu"] or bool(res)
        ents_tous.update(lire_entites(api, [q for v in cands.values() for q in v if q not in ents_tous],
                                      "claims|labels|aliases|sitelinks"))
        for rid, qs in cands.items():
            if any(q not in ents_tous for q in qs):     # lecture échouée : on ne tranche pas sur des données partielles
                etat[rid]["echec"] = True
                continue
            f = etat[rid]["f"]
            qid, raison = choisir_coureur({q: ents_tous[q] for q in qs}, f["name"], f["birth"], ctx.sous)
            if qid:
                etat[rid]["res"] = ("ok", qid)
            elif raison == "ambigu":
                etat[rid]["res"] = ("ambigu", None)
    a_libeller = [q for s in etat.values() if s["res"] and s["res"][1] for q in qids_a_libeller(ents_tous[s["res"][1]])]
    charger_libelles(api, ctx.cache, a_libeller)
    for rid, s in etat.items():
        if s["echec"]:
            continue
        if s["res"] and s["res"][0] == "ok":
            qid = s["res"][1]
            sortie[rid] = dict(qid=qid, verifie=today, **extraire_coureur(ents_tous[qid], ctx.cache.d["libelles"]))
        else:
            sortie[rid] = {"qid": None, "verifie": today, "raison": "ambigu" if s["res"] else "aucune"}
    return sortie


def lister_coureurs(entites_dir: str) -> Tuple[List[Dict[str, Any]], int]:
    """([{id, name, birth, prio}] des coureurs AVEC date de naissance, nombre sans date). `prio` : meilleur rang UCI, victoires,
    saison la plus récente (les plus notables d'abord)."""
    dossier = os.path.join(entites_dir, "coureurs")
    out, sans = [], 0
    for f in sorted(os.listdir(dossier)) if os.path.isdir(dossier) else []:
        data = collector._load(os.path.join(dossier, f), {}) if f.endswith(".json") else {}
        for rid, c in (data or {}).items():
            if not c.get("name"):
                continue
            if not c.get("birth_date"):
                sans += 1
                continue
            sais = c.get("saisons") or {}
            rangs = [s["uci_rank"] for s in sais.values() if isinstance(s, dict) and isinstance(s.get("uci_rank"), int)]
            wins = (c.get("totaux") or {}).get("wins") or 0
            last = max((int(a) for a in sais if str(a).isdigit()), default=0)
            out.append({"id": rid, "name": c["name"], "birth": c["birth_date"],
                        "prio": (min(rangs) if rangs else 99999, -wins, -last, rid)})
    return out, sans


# --------------------------------------------------------------------------- images (Commons)

def texte_brut(s: Any) -> Optional[str]:
    t = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", str(s or ""))).split())
    return t or None


def lire_imageinfo(rep: Dict[str, Any], noms: List[str]) -> Dict[str, Dict[str, Any]]:
    """{nom de fichier: {url, page, auteur?, licence, licence_url?} | {url: None, raison}} depuis une réponse `prop=imageinfo`."""
    q = rep.get("query") or {}
    renvois: Dict[str, str] = {}
    for lst in (q.get("normalized") or [], q.get("redirects") or []):
        for r in lst:
            if r.get("from") and r.get("to"):
                renvois[r["from"]] = r["to"]
    pages = {p.get("title"): p for p in (q.get("pages") or {}).values() if isinstance(p, dict)}
    out: Dict[str, Dict[str, Any]] = {}
    for nom in noms:
        t = "File:" + nom
        for _ in range(4):
            t = renvois.get(t, renvois.get(t.replace(" ", "_"), t))
        p = pages.get(t)
        info = ((p or {}).get("imageinfo") or [None])[0]
        if not p or "missing" in p or not info:
            out[nom] = {"url": None, "raison": "absent"}
            continue
        meta = info.get("extmetadata") or {}
        val = lambda k: texte_brut((meta.get(k) or {}).get("value"))   # noqa: E731
        licence = val("LicenseShortName")
        url = info.get("thumburl") or info.get("url")
        if not licence or not url or str(val("NonFree") or "").lower() == "true":
            out[nom] = {"url": None, "raison": "licence"}
            continue
        out[nom] = _sans_vide({"url": url, "page": info.get("descriptionurl"), "auteur": val("Artist"), "licence": licence,
                               "licence_url": val("LicenseUrl")})
    return out


def resoudre_images(ctx: "Contexte", noms: Iterable[str]) -> None:
    """Licences Commons des fichiers `noms` (par lots de 50) ; seules les entrées à (re)vérifier sont demandées."""
    noms = [n for n in dict.fromkeys(_fichier(n) for n in noms if n)
            if besoin(ctx.cache.d["images"].get(n), ctx.aujourdhui, "url")]
    for i in range(0, len(noms), LOT):
        lot = noms[i:i + LOT]
        rep = ctx.api.appel(COMMONS_API, action="query", titles="|".join("File:" + n for n in lot), prop="imageinfo",
                            iiprop="url|extmetadata", iiurlwidth=320)
        if rep is None:
            continue
        for n, info in lire_imageinfo(rep, lot).items():
            ctx.cache.d["images"][n] = dict(info, verifie=ctx.aujourdhui.isoformat())


# --------------------------------------------------------------------------- équipes

def preuve_equipe(parent: Dict[str, Any], elements_saison: List[Dict[str, Any]], code: str, saison: int, libelle: str) -> Optional[str]:
    """Texte de preuve si (i) P1998 = code sur une période datée contenant la saison ET (ii) nom P1448 daté valable cette année, ou
    libellé d'élément saison (contenant l'année) concordant avec `libelle` ; sinon None."""
    periode = None
    for c in revendications(parent, "P1998"):
        if str(valeur(c) or "").strip().upper() == code.upper() and periode_contient(c, saison):
            d, f = bornes(c)
            periode = f"{date_texte(d) or '…'}→{date_texte(f) or '…'}"
            break
    if periode is None:
        return None
    for c in revendications(parent, "P1448"):
        v = valeur(c)
        if isinstance(v, dict) and v.get("text") and periode_contient(c, saison) and nom_equipe_concorde(libelle, v["text"]):
            return f"P1998 {code} [{periode}] ; P1448 « {v['text']} »"
    for el in elements_saison:
        for nom in noms_entite(el):
            if re.search(rf"(?<!\d){saison}(?!\d)", nom):
                reste = " ".join(t for t in jetons(nom) if not t.isdigit() and t not in MOTS_SAISON)
                if reste and nom_equipe_concorde(libelle, reste):
                    return f"P1998 {code} [{periode}] ; saison « {nom} »"
    return None


def rapprocher_equipe(code: str, saison: int, libelle: str, items: Dict[str, Dict[str, Any]],
                      parents: Dict[str, Optional[Dict[str, Any]]]) -> Tuple[Optional[str], str]:
    """(qid du parent, preuve) ; (None, 'aucune' | 'ambigu'). `items` : éléments trouvés par P1998=code ; `parents` : entités des parents."""
    cand: Dict[str, List[Dict[str, Any]]] = {}
    for q, e in items.items():
        pars = [p for p in (qid_de(c) for c in revendications(e, "P5138")) if p]
        if pars:
            for p in pars:
                cand.setdefault(p, []).append(e)
        else:
            cand.setdefault(q, [])
    valides = []
    for p, saisons_el in cand.items():
        ep = parents.get(p) or items.get(p)
        pr = preuve_equipe(ep, saisons_el, code, saison, libelle) if ep else None
        if pr:
            valides.append((p, pr))
    if len(valides) == 1:
        return valides[0]
    return None, ("ambigu" if valides else "aucune")


def lister_equipes(entites_dir: str) -> List[Dict[str, Any]]:
    """[{id, name, season, code}] de toutes les équipes-saisons (hors sélections nationales) ; `code` None si absent."""
    dossier = os.path.join(entites_dir, "equipes")
    out = []
    for f in sorted(os.listdir(dossier)) if os.path.isdir(dossier) else []:
        if not re.fullmatch(r"\d{4}\.json", f):
            continue
        for tid, e in (collector._load(os.path.join(dossier, f), {}) or {}).items():
            if not e.get("nationale"):
                out.append({"id": tid, "name": e.get("name") or "", "season": int(f[:4]), "code": e.get("code_uci")})
    return out


def run_equipes(ctx: "Contexte", alias: Dict[str, str]) -> Dict[str, int]:
    today = ctx.aujourdhui.isoformat()
    cache = ctx.cache.d["equipes"]
    equipes = lister_equipes(ctx.entites_dir)
    for tid, q in alias.items():                 # alias manuels : toujours prioritaires, sans requête
        if re.fullmatch(r"Q\d+", q) and any(e["id"] == tid for e in equipes):
            cache[tid] = {"qid": q, "preuve": "alias", "verifie": today}
    attente = sorted((e for e in equipes if e["code"] and re.fullmatch(r"[A-Za-z0-9]{2,6}", e["code"]) and e["id"] not in alias
                      and besoin(cache.get(e["id"]), ctx.aujourdhui)), key=lambda e: (-e["season"], e["name"], e["id"]))
    par_code: Dict[str, List[Dict[str, Any]]] = {}
    for e in attente:
        par_code.setdefault(e["code"].upper(), []).append(e)
    codes = list(par_code)
    for i in range(0, len(codes), LOT_CODES):
        if ctx.hors_budget(PART_EQUIPES):
            break
        lot = codes[i:i + LOT_CODES]
        trouves = {c: recherche(ctx.api, f"haswbstatement:P1998={c}", 30) for c in lot}
        ents = lire_entites(ctx.api, [q for v in trouves.values() for q in (v or [])], "claims|labels|aliases")
        pars = {p for v in trouves.values() for q in (v or []) for p in (qid_de(c) for c in revendications(ents.get(q), "P5138")) if p}
        parents = lire_entites(ctx.api, [p for p in pars if p not in ents], "claims|labels|aliases")
        parents.update({p: ents[p] for p in pars if p in ents})
        for c in lot:
            qs = trouves[c]
            peres = {p for q in (qs or []) for p in (qid_de(x) for x in revendications(ents.get(q), "P5138")) if p}
            if qs is None or any(q not in ents for q in qs) or any(p not in parents for p in peres):
                continue                                  # lecture échouée : retenté au prochain passage
            items = {q: ents[q] for q in qs if ents.get(q)}
            for e in par_code[c]:
                qid, pr = rapprocher_equipe(c, e["season"], e["name"], items, parents)
                cache[e["id"]] = {"qid": qid, "preuve": pr, "verifie": today} if qid else {"qid": None, "raison": pr, "verifie": today}
        ctx.cache.ecrire()
    return bilan_equipes(ctx, alias)


def bilan_equipes(ctx: "Contexte", alias: Dict[str, str]) -> Dict[str, int]:
    cache = ctx.cache.d["equipes"]
    equipes = lister_equipes(ctx.entites_dir)
    return {"rapprochees": sum(1 for e in equipes if (cache.get(e["id"]) or {}).get("qid")),
            "sans": sum(1 for e in equipes if e["code"] and cache.get(e["id"]) is not None and not cache[e["id"]].get("qid")),
            "restantes": sum(1 for e in equipes if e["code"] and e["id"] not in alias and besoin(cache.get(e["id"]), ctx.aujourdhui))}


def extraire_lignee(e: Dict[str, Any], libelles: Dict[str, Optional[str]]) -> Dict[str, Any]:
    noms = []
    for c in revendications(e, "P1448"):
        v = valeur(c)
        if isinstance(v, dict) and v.get("text"):
            d, f = bornes(c)
            noms.append(_sans_vide({"nom": v["text"], "debut": date_texte(d), "fin": date_texte(f)}))
    noms.sort(key=lambda x: (x.get("debut") or "0000", x.get("fin") or "9999", x["nom"]))
    codes = []
    for c in revendications(e, "P1998"):
        if valeur(c):
            d, f = bornes(c)
            codes.append(_sans_vide({"code": str(valeur(c)), "debut": date_texte(d), "fin": date_texte(f)}))
    codes.sort(key=lambda x: (x.get("debut") or "0000", x.get("fin") or "9999", x["code"]))
    pays = next(((q, libelles.get(q)) for q in (qid_de(c) for c in revendications(e, "P17")) if q), None)
    classes = [libelles[q] for q in (qid_de(c) for c in revendications(e, "P31")) if q and libelles.get(q)]
    logo = _choisir_valeur(revendications(e, "P154"))
    return _sans_vide({"libelle": libelle_langue(e), "noms": noms, "codes": codes,
                       "pays": _sans_vide({"qid": pays[0], "libelle": pays[1]}) if pays else None,
                       "classes": classes, "sitelinks": sitelinks(e),
                       "logo": _fichier(logo) if isinstance(logo, str) and logo.strip() else None})


def run_lignees(ctx: "Contexte") -> int:
    today = ctx.aujourdhui.isoformat()
    cache = ctx.cache.d["lignees"]
    qids = sorted({e["qid"] for e in ctx.cache.d["equipes"].values() if e.get("qid")})
    a_lire = [q for q in qids if besoin(cache.get(q), ctx.aujourdhui, "libelle")]
    for i in range(0, len(a_lire), LOT):
        if ctx.hors_budget():
            break
        lot = a_lire[i:i + LOT]
        ents = lire_entites(ctx.api, lot, "claims|labels|sitelinks")
        charger_libelles(ctx.api, ctx.cache, [q for e in ents.values() if e for p in ("P17", "P31")
                                              for q in (qid_de(c) for c in revendications(e, p)) if q])
        for q, e in ents.items():
            if e:
                cache[q] = dict(extraire_lignee(e, ctx.cache.d["libelles"]), verifie=today)
        resoudre_images(ctx, [v["logo"] for q, v in cache.items() if q in lot and v.get("logo")])
        ctx.cache.ecrire()
    return len(qids)


# --------------------------------------------------------------------------- orchestration

class Contexte:
    def __init__(self, api: Api, cache: Cache, entites_dir: str, aujourdhui: dt.date, budget_min: float,
                 horloge: Callable[[], float] = time.monotonic):
        self.api, self.cache, self.entites_dir, self.aujourdhui = api, cache, entites_dir, aujourdhui
        self.horloge, self.t0 = horloge, horloge()
        self.budget_s = budget_min * 60
        self.sous = Sousclasses(api)

    def hors_budget(self, part: float = 1.0) -> bool:
        """Budget (ou part du budget) dépassé ; budget 0 = illimité."""
        return bool(self.budget_s) and self.horloge() - self.t0 >= self.budget_s * part


def verifier_occupation(api: Api) -> bool:
    """Contrôle (une requête) que Q2309784 est bien « cycliste » : sinon on ne devine pas, les coureurs sont ignorés."""
    ents = lire_entites(api, [OCC_CYCLISTE], "labels", "en|fr")
    e = ents.get(OCC_CYCLISTE)
    ok = bool(e) and bool(re.search(r"cycl", json.dumps(e.get("labels") or {}, ensure_ascii=False), re.I))
    if not ok:
        print(f"[WARN] [WIKIDATA] {OCC_CYCLISTE} n'a pas le libellé attendu (cycliste) : coureurs ignorés")
    return ok


def run_coureurs(ctx: "Contexte") -> Dict[str, int]:
    fiches, sans_date = lister_coureurs(ctx.entites_dir)
    cache = ctx.cache.d["coureurs"]
    attente = sorted((f for f in fiches if besoin(cache.get(f["id"]), ctx.aujourdhui)), key=lambda f: f["prio"])
    traites = 0
    if attente and verifier_occupation(ctx.api):
        depuis_ecriture = 0
        for i in range(0, len(attente), LOT_COUREURS):
            if ctx.hors_budget():
                break
            res = resoudre_tranche(ctx, attente[i:i + LOT_COUREURS])
            cache.update(res)
            resoudre_images(ctx, [v["image"] for v in res.values() if v.get("image")])
            traites += len(res)
            depuis_ecriture += len(res)
            if depuis_ecriture >= ECRIRE_TOUS:
                ctx.cache.ecrire()
                depuis_ecriture = 0
    return bilan_coureurs(ctx, traites)


def bilan_coureurs(ctx: "Contexte", traites: int = 0) -> Dict[str, int]:
    fiches, sans_date = lister_coureurs(ctx.entites_dir)
    cache = ctx.cache.d["coureurs"]
    courants = [cache[f["id"]] for f in fiches if f["id"] in cache and not besoin(cache[f["id"]], ctx.aujourdhui)]
    return {"rapproches": sum(1 for v in courants if v.get("qid")), "sans": sum(1 for v in courants if not v.get("qid")),
            "restants": sum(1 for f in fiches if besoin(cache.get(f["id"]), ctx.aujourdhui)), "sans_date": sans_date, "traites": traites}


def run_wikidata(budget_min: float = 300, archives_dir: Optional[str] = None, now: Optional[dt.date] = None,
                 api: Optional[Api] = None, horloge: Callable[[], float] = time.monotonic,
                 alias_equipes: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Un passage : équipes (au plus la moitié du budget), lignées, puis coureurs (les plus notables d'abord) dans le budget (minutes,
    0 = illimité). N'écrit QUE `<archives_dir>/entites/wikidata/` (cache, écrit au fil de l'eau : un arrêt ne perd rien) ; les fichiers
    d'entités sont reconstruits par collector.write_entites (passage d'archives). Lit `entites/coureurs` et `entites/equipes`."""
    archives_dir = archives_dir or collector.ARCHIVES_DIR
    entites = os.path.join(archives_dir, "entites")
    if api is None:
        preparer_reseau()
    api = api or Api()
    cache = Cache(os.path.join(entites, "wikidata"))
    ctx = Contexte(api, cache, entites, now or dt.date.today(), budget_min, horloge)
    alias = collector.charger_alias(collector.ALIAS_EQUIPES) if alias_equipes is None else alias_equipes
    try:
        run_equipes(ctx, alias)
        run_lignees(ctx)
        run_coureurs(ctx)
    except HoteAbandonne as e:
        print(f"[WARN] [WIKIDATA] passage interrompu ({e}) : cache conservé, reprise au prochain passage")
    finally:
        cache.ecrire()
    eq, co = bilan_equipes(ctx, alias), bilan_coureurs(ctx)
    print(f"[WIKIDATA] coureurs : {co['rapproches']} rapprochés, {co['sans']} sans correspondance, {co['restants']} restants"
          f" ({co['sans_date']} sans date de naissance ignorés) ; équipes : {eq['rapprochees']} rapprochées, {eq['sans']} sans correspondance,"
          f" {eq['restantes']} restantes ; {api.requetes} requête(s)")
    return {"coureurs": co, "equipes": eq, "requetes": api.requetes}


# --------------------------------------------------------------------------- lecture par encyclopedie.py

def fiche_wikidata(entree: Dict[str, Any], images: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Champ `wikidata` d'un coureur (None si pas de correspondance) ; l'image n'y figure que si une licence lisible a été trouvée."""
    if not isinstance(entree, dict) or not entree.get("qid"):
        return None
    im = images.get(entree.get("image") or "") or {}
    return _sans_vide({"qid": entree["qid"], "lieu": entree.get("lieu"), "taille": entree.get("taille"),
                       "image": _sans_vide({k: im.get(k) for k in ("url", "page", "auteur", "licence", "licence_url")}) if im.get("url") else None,
                       "wikipedia": entree.get("sitelinks"), "equipes_wd": entree.get("equipes")})


def fiche_lignee(entree: Optional[Dict[str, Any]], images: Dict[str, Any]) -> Dict[str, Any]:
    """Champs d'une lignée lus dans le cache (sans `verifie`) ; le logo n'y figure que s'il a une licence lisible."""
    e = {k: v for k, v in (entree or {}).items() if k not in ("verifie", "logo")}
    im = images.get((entree or {}).get("logo") or "") or {}
    if im.get("url"):
        e["logo"] = _sans_vide({k: im.get(k) for k in ("url", "page", "auteur", "licence", "licence_url")})
    return e


# --------------------------------------------------------------------------- tests (réponses simulées)

class FauxWikimedia:
    """Serveur simulé : recherche CirrusSearch (haswbstatement), wbgetentities, Commons imageinfo. Compte les requêtes."""

    def __init__(self, entites: Dict[str, Dict[str, Any]], recherches: Dict[str, List[str]], commons: Dict[str, Any],
                 echec_apres: Optional[int] = None):
        self.entites, self.recherches, self.commons = entites, recherches, commons
        self.log: List[Tuple[str, str]] = []
        self.echec_apres = echec_apres

    def __call__(self, base: str, p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.echec_apres is not None and len(self.log) >= self.echec_apres:
            return None
        if "commons" in base:
            self.log.append(("commons", p["titles"]))
            titres = p["titles"].split("|")
            pages = {str(i): self.commons[t] for i, t in enumerate(titres) if t in self.commons}
            return {"query": {"normalized": [], "pages": pages}}
        if p["action"] == "query":
            self.log.append(("search", p["srsearch"]))
            return {"query": {"search": [{"title": q} for q in self.recherches.get(p["srsearch"], [])]}}
        self.log.append(("entites", p["ids"]))
        assert len(p["ids"].split("|")) <= LOT
        return {"entities": {q: (self.entites[q] if q in self.entites else {"id": q, "missing": ""}) for q in p["ids"].split("|")}}

    def n(self, genre: str) -> int:
        return sum(1 for g, _ in self.log if g == genre)


def _t(iso: str, prec: int = 11) -> Dict[str, Any]:
    return {"time": "+" + iso + "T00:00:00Z", "precision": prec, "timezone": 0, "before": 0, "after": 0, "calendarmodel": "x"}


def _snak(v: Any) -> Dict[str, Any]:
    return {"datavalue": {"value": v, "type": "x"}, "snaktype": "value"}


def _cl(v: Any, quals: Optional[Dict[str, str]] = None, rank: str = "normal") -> Dict[str, Any]:
    c: Dict[str, Any] = {"mainsnak": _snak(v), "rank": rank}
    if quals:
        c["qualifiers"] = {p: [_snak(_t(t[0], t[1]))] for p, t in quals.items()}
    return c


def _item(q: str, nom: str, naiss: Optional[str] = None, occ: Optional[str] = "Q2309784", extra: Optional[Dict[str, Any]] = None,
          alias: Optional[List[str]] = None, labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    claims: Dict[str, Any] = {}
    if naiss:
        claims["P569"] = [_cl(_t(naiss))]
    if occ:
        claims["P106"] = [_cl({"entity-type": "item", "id": occ})]
    claims.update(extra or {})
    lab = {"fr": {"language": "fr", "value": nom}}
    lab.update({k: {"language": k, "value": v} for k, v in (labels or {}).items()})
    return {"id": q, "labels": lab, "aliases": {"en": [{"language": "en", "value": a} for a in (alias or [])]}, "claims": claims,
            "sitelinks": {}}


def _eid(q: str) -> Dict[str, Any]:
    return {"entity-type": "item", "id": q}


def _tests() -> None:
    # --- fonctions pures
    assert nom_concorde("Paul Épure", ["Paul Epure"]) and nom_concorde("Paul Épure", ["Épure Paul"])         # ordre et accents indifférents
    assert nom_concorde("Jonas Vinterfjord Hansen", ["Jonas Vinterfjord"])                                  # inclusion stricte (≥ 2 jetons)
    assert not nom_concorde("Jonas Vinterfjord Hansen", ["Vinterfjord"])                                    # un seul jeton : pas d'inclusion
    assert not nom_concorde("Paul Épure", ["Paul Épure Jr"]) and not nom_concorde("Paul Épure", ["Pierre Épure"])
    assert nom_concorde("Jonas Vinterfjord", ["Jonas Vinterfjord"]) and not nom_concorde("", ["x y"])
    assert nom_equipe_concorde("Soudal Quick Step", "Soudal Quick-Step") and nom_equipe_concorde("Team Aurore Pro", "Aurore Pro")
    assert not nom_equipe_concorde("Aurore", "Team Aurore") and not nom_equipe_concorde("Aurore Pro", "Boreale Pro")   # 1 jeton : pas d'inclusion
    assert parse_temps(_t("1997-07-11")) == ("1997-07-11", 11) and parse_temps({"time": "-0100-01-01T00:00:00Z"}) is None
    assert date_texte(("1997-00-00", 9)) == "1997" and date_texte(("1997-05-00", 10)) == "1997-05" and date_texte(("1990-00-00", 8)) is None
    aujourdhui = dt.date(2026, 11, 15)
    assert besoin(None, aujourdhui) and besoin({"qid": "Q1"}, aujourdhui)
    assert not besoin({"qid": "Q1", "verifie": "2026-06-01"}, aujourdhui) and besoin({"qid": "Q1", "verifie": "2026-05-01"}, aujourdhui)   # 180 jours
    assert not besoin({"qid": None, "verifie": "2026-10-01"}, aujourdhui) and besoin({"qid": None, "verifie": "2026-09-01"}, aujourdhui)  # 60 jours
    assert texte_brut('<a href="x">Jean &amp; Co</a> <b></b>') == "Jean & Co" and texte_brut("<p></p>") is None

    # --- monde simulé : coureurs
    P54a = _cl(_eid("Q500"), {"P580": ("2019-00-00", 9), "P582": ("2021-12-31", 11)})
    P54b = _cl(_eid("Q501"), {"P580": ("2022-03-00", 10)})
    exact = _item("Q101", "Paul Épure", "1997-07-11", extra={
        "P19": [_cl(_eid("Q300"))], "P2048": [_cl({"amount": "+178", "unit": "http://www.wikidata.org/entity/Q174728"})],
        "P18": [_cl("Paul Epure 2024.jpg")], "P54": [P54a, P54b]})
    exact["sitelinks"] = {"frwiki": {"site": "frwiki", "title": "Paul Épure"}, "enwiki": {"site": "enwiki", "title": "Paul Epure"}}
    ents = {
        "Q2309784": _item("Q2309784", "cycliste", occ=None, labels={"en": "cyclist"}),
        "Q101": exact,
        "Q102": _item("Q102", "Jonas Vinterfjord", "1996-12-10"),                                   # inclusion (nous : « … Hansen »)
        "Q103": _item("Q103", "Luc Doublon", "1995-05-05"), "Q104": _item("Q104", "Luc Doublon", "1995-05-05"),   # homonymes, même date
        "Q105": _item("Q105", "Marc Daté", "1990-01-01"),                                           # date différente de la nôtre
        "Q106": _item("Q106", "Ana Seule", "1999-09-09"), "Q107": _item("Q107", "Ana Seule", "1980-01-01"),     # 2 candidats, 1 seul vérifié
        "Q108": _item("Q108", "Tom Footeux", "1993-03-03", occ="Q937857"),                          # footballeur : pas cycliste
        "Q109": _item("Q109", "Eli Sousclasse", "1992-02-02", occ="Q5000"),                          # occupation = sous-classe de cycliste
        "Q5000": {"id": "Q5000", "claims": {"P279": [_cl(_eid("Q5001"))]}}, "Q5001": {"id": "Q5001", "claims": {"P279": [_cl(_eid("Q2309784"))]}},
        "Q937857": {"id": "Q937857", "claims": {"P279": [_cl(_eid("Q2066131"))]}}, "Q2066131": {"id": "Q2066131", "claims": {}},
        "Q110": _item("Q110", "Nom Autre", "1991-01-01", alias=["Ida Alias"]),                       # nom concordant par alias
        "Q111": _item("Q111", "Zoé Imprécise", None, extra={"P569": [_cl(_t("1994-00-00", 9))]}),   # naissance à l'année : rejetée
        "Q300": {"id": "Q300", "labels": {"fr": {"language": "fr", "value": "Test-sur-Mer"}}},
        "Q500": {"id": "Q500", "labels": {"en": {"language": "en", "value": "Équipe Un"}}},
        "Q501": {"id": "Q501", "labels": {"fr": {"language": "fr", "value": "Équipe Deux"}}},
    }
    filtre = lambda n: f"{n} haswbstatement:P106={OCC_CYCLISTE}"   # noqa: E731
    recherches = {filtre("Paul Épure"): ["Q101"], filtre("Jonas Vinterfjord Hansen"): [], filtre("Jonas Vinterfjord"): ["Q102"],
                  filtre("Luc Doublon"): ["Q103", "Q104"], filtre("Marc Daté"): ["Q105"], filtre("Ana Seule"): ["Q106", "Q107"],
                  filtre("Tom Footeux"): ["Q108"], filtre("Eli Sousclasse"): ["Q109"], filtre("Ida Alias"): ["Q110"],
                  filtre("Zoé Imprécise"): ["Q111"], filtre("Nom Introuvable"): []}
    commons = {
        "File:Paul Epure 2024.jpg": {"title": "File:Paul Epure 2024.jpg", "imageinfo": [{
            "thumburl": "https://upload.example/thumb/320px-Paul_Epure_2024.jpg", "descriptionurl": "https://commons.example/wiki/File:Paul_Epure_2024.jpg",
            "extmetadata": {"Artist": {"value": '<a href="//x/User:Jo">Jo &amp; Fils</a>'}, "LicenseShortName": {"value": "CC BY-SA 4.0"},
                            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"}}}]},
        "File:Sans licence.jpg": {"title": "File:Sans licence.jpg", "imageinfo": [{"thumburl": "https://upload.example/x.jpg", "extmetadata": {}}]},
    }
    liste = [{"id": "epure-paul-19970711", "name": "Paul Épure", "birth": "1997-07-11", "prio": (1, 0, 0, "a")},
             {"id": "vinterfjord-jonas-19961210", "name": "Jonas Vinterfjord Hansen", "birth": "1996-12-10", "prio": (2, 0, 0, "b")},
             {"id": "doublon-luc-19950505", "name": "Luc Doublon", "birth": "1995-05-05", "prio": (3, 0, 0, "c")},
             {"id": "date-marc-19900202", "name": "Marc Daté", "birth": "1990-02-02", "prio": (4, 0, 0, "d")},
             {"id": "seule-ana-19990909", "name": "Ana Seule", "birth": "1999-09-09", "prio": (5, 0, 0, "e")},
             {"id": "footeux-tom-19930303", "name": "Tom Footeux", "birth": "1993-03-03", "prio": (6, 0, 0, "f")},
             {"id": "sousclasse-eli-19920202", "name": "Eli Sousclasse", "birth": "1992-02-02", "prio": (7, 0, 0, "g")},
             {"id": "alias-ida-19910101", "name": "Ida Alias", "birth": "1991-01-01", "prio": (8, 0, 0, "h")},
             {"id": "imprecise-zoe-19940101", "name": "Zoé Imprécise", "birth": "1994-01-01", "prio": (9, 0, 0, "i")},
             {"id": "introuvable-nom-19800101", "name": "Nom Introuvable", "birth": "1980-01-01", "prio": (10, 0, 0, "j")}]
    faux = FauxWikimedia(ents, recherches, commons)
    api = Api(faux)
    with tempfile.TemporaryDirectory() as tmp:
        ctx = Contexte(api, Cache(os.path.join(tmp, "wikidata")), tmp, aujourdhui, 0)
        res = resoudre_tranche(ctx, liste)
        assert faux.n("search") == len(liste) + 1, faux.log          # une recherche chacun + 1 repli (« Jonas Vinterfjord »)
        assert faux.n("entites") <= 12, faux.log                     # lectures groupées (+ occupations / libellés), jamais une par coureur
        q = {r: v.get("qid") for r, v in res.items()}
        assert q["epure-paul-19970711"] == "Q101"                                                          # exact
        assert q["vinterfjord-jonas-19961210"] == "Q102"                                                   # inclusion stricte, 2e ronde
        assert q["doublon-luc-19950505"] is None and res["doublon-luc-19950505"]["raison"] == "ambigu"     # homonymes de même date : rien
        assert q["date-marc-19900202"] is None and res["date-marc-19900202"]["raison"] == "aucune"         # date différente : rien
        assert q["seule-ana-19990909"] == "Q106"                                                           # 2 candidats, un seul vérifié
        assert q["footeux-tom-19930303"] is None                                                           # pas cycliste
        assert q["sousclasse-eli-19920202"] == "Q109"                                                      # occupation = sous-classe (P279)
        assert q["alias-ida-19910101"] == "Q110"                                                           # alias
        assert q["imprecise-zoe-19940101"] is None                                                         # naissance à l'année seulement
        assert q["introuvable-nom-19800101"] is None
        e = res["epure-paul-19970711"]
        assert e["lieu"] == {"qid": "Q300", "libelle": "Test-sur-Mer"} and e["taille"] == 1.78 and e["image"] == "Paul Epure 2024.jpg"
        assert e["sitelinks"] == {"fr": "Paul Épure", "en": "Paul Epure"} and e["verifie"] == "2026-11-15"
        assert e["equipes"] == [{"qid": "Q500", "libelle": "Équipe Un", "debut": "2019", "fin": "2021-12-31", "precision_debut": "annee",
                                 "precision_fin": "jour"},
                                {"qid": "Q501", "libelle": "Équipe Deux", "debut": "2022-03", "precision_debut": "mois"}], e["equipes"]
        # images : licence et auteur lus ; sans licence -> pas d'image
        resoudre_images(ctx, ["Paul Epure 2024.jpg", "Sans licence.jpg", "Absente.jpg", "Paul_Epure_2024.jpg"])
        im = ctx.cache.d["images"]
        assert im["Paul Epure 2024.jpg"] == {"url": "https://upload.example/thumb/320px-Paul_Epure_2024.jpg",
                                             "page": "https://commons.example/wiki/File:Paul_Epure_2024.jpg", "auteur": "Jo & Fils",
                                             "licence": "CC BY-SA 4.0", "licence_url": "https://creativecommons.org/licenses/by-sa/4.0",
                                             "verifie": "2026-11-15"}
        assert im["Sans licence.jpg"]["url"] is None and im["Sans licence.jpg"]["raison"] == "licence" and im["Absente.jpg"]["raison"] == "absent"
        assert faux.n("commons") == 1                                                                      # un seul lot de 3 (doublon fusionné)
        fw = fiche_wikidata(dict(e, qid="Q101"), im)
        assert fw["image"]["licence"] == "CC BY-SA 4.0" and fw["wikipedia"]["fr"] == "Paul Épure" and fw["lieu"]["libelle"] == "Test-sur-Mer"
        assert "image" not in fiche_wikidata({"qid": "Q1", "image": "Sans licence.jpg"}, im)
        # échec de lecture : le coureur n'est pas tranché (pas de `null` à tort)
        faux2 = FauxWikimedia(ents, recherches, commons, echec_apres=1)
        ctx2 = Contexte(Api(faux2), Cache(os.path.join(tmp, "w2")), tmp, aujourdhui, 0)
        assert resoudre_tranche(ctx2, liste[:2]) == {}

    # --- équipes : code + période + nom
    def equipe(q, nom, codes, noms=(), parent=None, label=None):
        extra = {"P1998": [_cl(c, qu) for c, qu in codes], "P1448": [_cl({"text": t, "language": "fr"}, qu) for t, qu in noms]}
        if parent:
            extra["P5138"] = [_cl(_eid(parent))]
        return _item(q, label or nom, occ=None, extra=extra)
    A = lambda a: (f"{a}-01-01", 11)   # noqa: E731
    mondeq = {
        # équipe Aurore Pro : code AUR 2020-2023, nom Aurore Pro 2020-2023 puis Boreale 2024-
        "Q700": equipe("Q700", "Aurore", [("AUR", {"P580": A(2020), "P582": A(2023)}), ("BOR", {"P580": A(2024)})],
                       [("Aurore Pro", {"P580": A(2020), "P582": A(2023)}), ("Boreale Pro", {"P580": A(2024)})]),
        "Q701": equipe("Q701", "2022 Aurore Pro season", [("AUR", None)], parent="Q700"),
        # homonyme du code : autre équipe (Q710 : AUR en 2005-2008)
        "Q710": equipe("Q710", "Aurelia", [("AUR", {"P580": A(2005), "P582": A(2008)})], [("Aurelia Team", {"P580": A(2005), "P582": A(2008)})]),
        # équipe sans nom daté : preuve par l'élément saison seulement
        "Q720": equipe("Q720", "Cirrus", [("CIR", {"P580": A(2015)})]),
        "Q721": equipe("Q721", "2021 Cirrus Racing season", [], parent="Q720"),
        # deux parents satisfaisants pour le même code et la même saison
        "Q730": equipe("Q730", "Delta", [("DEL", {"P580": A(2018)})], [("Delta Cycling", {"P580": A(2018)})]),
        "Q731": equipe("Q731", "Delta bis", [("DEL", {"P580": A(2018)})], [("Delta Cycling", {"P580": A(2018)})]),
        # code sans période : jamais accepté
        "Q740": equipe("Q740", "Echo", [("ECH", None)], [("Echo Team", {"P580": A(2010)})]),
    }
    rech = {"haswbstatement:P1998=AUR": ["Q700", "Q701", "Q710"], "haswbstatement:P1998=CIR": ["Q720", "Q721"],
            "haswbstatement:P1998=DEL": ["Q730", "Q731"], "haswbstatement:P1998=ECH": ["Q740"], "haswbstatement:P1998=BOR": ["Q700"],
            "haswbstatement:P1998=ZZZ": []}
    ex = FauxWikimedia(mondeq, rech, {})
    a = Api(ex)

    def rap(code, saison, lib):
        qs = recherche(a, f"haswbstatement:P1998={code}", 30)
        items = lire_entites(a, qs, "claims")
        pars = {p for e in items.values() for p in (qid_de(c) for c in revendications(e, "P5138")) if p}
        parents = lire_entites(a, [p for p in pars if p not in items], "claims")
        parents.update({p: items[p] for p in pars if p in items})
        return rapprocher_equipe(code, saison, lib, {q: e for q, e in items.items() if e}, parents)
    r = rap("AUR", 2022, "Aurore Pro")
    assert r[0] == "Q700" and "P1998 AUR [2020-01-01→2023-01-01]" in r[1] and "Aurore Pro" in r[1], r         # code + période + nom : OK
    assert rap("AUR", 2007, "Aurelia Team")[0] == "Q710"                                          # le code homonyme n'est retenu que pour SA période
    assert rap("AUR", 2022, "Aurelia Team")[0] is None                                             # code valable mais nom d'une autre équipe
    assert rap("AUR", 2025, "Aurore Pro")[0] is None                                               # code valable mais hors période
    assert rap("AUR", 2022, "Autre Equipe") == (None, "aucune")                                    # nom différent
    assert rap("BOR", 2025, "Boreale Pro")[0] == "Q700" and rap("BOR", 2022, "Boreale Pro")[0] is None
    r = rap("CIR", 2021, "Cirrus Racing")
    assert r[0] == "Q720" and "saison « 2021 Cirrus Racing season »" in r[1], r                    # preuve par élément saison de l'année
    assert rap("CIR", 2022, "Cirrus Racing")[0] is None                                            # pas d'élément saison pour 2022
    assert rap("DEL", 2019, "Delta Cycling") == (None, "ambigu")                                   # deux parents : rien
    assert rap("ECH", 2012, "Echo Team") == (None, "aucune")                                       # code sans période : jamais accepté

    # --- run_wikidata complet, reprise sur budget, priorité, alias (fichiers d'entités simulés)
    with tempfile.TemporaryDirectory() as tmp:
        ent = os.path.join(tmp, "entites")
        collector._dump(os.path.join(ent, "coureurs", "e.json"), {
            "epure-paul-19970711": {"name": "Paul Épure", "birth_date": "1997-07-11", "saisons": {"2024": {"uci_rank": 40}}, "totaux": {"wins": 2}},
            "doublon-luc-19950505": {"name": "Luc Doublon", "birth_date": "1995-05-05", "saisons": {"2023": {}}, "totaux": {"wins": 9}},
            "sansdate-x": {"name": "Sans Date", "saisons": {}}})
        collector._dump(os.path.join(ent, "equipes", "2022.json"), {
            "aurore-pro-2022": {"name": "Aurore Pro", "season": 2022, "code_uci": "AUR"},
            "sans-code-2022": {"name": "Sans Code", "season": 2022},
            "france-2022": {"name": "France", "season": 2022, "nationale": True, "code_uci": "FRA"}})
        collector._dump(os.path.join(ent, "equipes", "index.json"), [])
        monde = dict(ents)
        monde.update(mondeq)
        monde["Q700"] = dict(monde["Q700"], sitelinks={"frwiki": {"site": "frwiki", "title": "Aurore Pro (équipe)"}})
        monde["Q700"]["claims"].update({"P17": [_cl(_eid("Q142"))], "P31": [_cl(_eid("Q1"))], "P154": [_cl("Logo Aurore.svg")]})
        monde["Q142"] = {"id": "Q142", "labels": {"fr": {"language": "fr", "value": "Pays Fictif"}}}
        monde["Q1"] = {"id": "Q1", "labels": {"en": {"language": "en", "value": "cycling team"}}}
        commons2 = dict(commons)
        commons2["File:Logo Aurore.svg"] = {"title": "File:Logo Aurore.svg", "imageinfo": [{
            "url": "https://upload.example/logo.svg", "extmetadata": {"LicenseShortName": {"value": "Public domain"}}}]}
        rech2 = dict(recherches)
        rech2.update(rech)
        # horloge simulée : chaque requête coûte 1 s ; budget 1 min = ~60 requêtes
        faux = FauxWikimedia(monde, rech2, commons2)
        t = [0.0]
        horloge = lambda: t[0]   # noqa: E731
        def fetch(b, p):
            t[0] += 1.0
            return faux(b, p)
        bilan = run_wikidata(1, tmp, aujourdhui, Api(fetch), horloge, alias_equipes={"sans-code-2022": "Q730"})
        w = os.path.join(ent, "wikidata")
        cc, ee, ll = (collector._load(os.path.join(w, n + ".json"), {}) for n in ("coureurs", "equipes", "lignees"))
        assert ee["aurore-pro-2022"]["qid"] == "Q700" and ee["sans-code-2022"] == {"qid": "Q730", "preuve": "alias", "verifie": "2026-11-15"}
        assert "france-2022" not in ee                                                              # sélection nationale : jamais
        assert ll["Q700"]["libelle"] == "Aurore" and ll["Q700"]["pays"] == {"qid": "Q142", "libelle": "Pays Fictif"} and ll["Q700"]["classes"] == ["cycling team"]
        assert [n["nom"] for n in ll["Q700"]["noms"]] == ["Aurore Pro", "Boreale Pro"] and ll["Q700"]["codes"][0] == {"code": "AUR", "debut": "2020-01-01", "fin": "2023-01-01"}
        assert ll["Q700"]["sitelinks"] == {"fr": "Aurore Pro (équipe)"} and ll["Q700"]["logo"] == "Logo Aurore.svg"
        assert collector._load(os.path.join(w, "images.json"), {})["Logo Aurore.svg"]["licence"] == "Public domain"
        assert cc["epure-paul-19970711"]["qid"] == "Q101" and cc["doublon-luc-19950505"]["qid"] is None and "sansdate-x" not in cc
        assert bilan["coureurs"]["rapproches"] == 1 and bilan["coureurs"]["sans"] == 1 and bilan["coureurs"]["restants"] == 0
        assert bilan["coureurs"]["sans_date"] == 1
        # n'écrit que entites/wikidata/ : rien d'autre n'a bougé
        assert sorted(os.listdir(ent)) == ["coureurs", "equipes", "wikidata"]
        # reprise : second passage sans changement = aucune nouvelle recherche de coureur ni d'équipe
        faux.log.clear()
        run_wikidata(1, tmp, aujourdhui, Api(fetch), horloge, alias_equipes={"sans-code-2022": "Q730"})
        assert faux.n("search") == 0, faux.log
        # re-vérification : au-delà de 180 jours, les entrées sont relues
        faux.log.clear()
        run_wikidata(1, tmp, aujourdhui + dt.timedelta(days=181), Api(fetch), horloge, alias_equipes={})
        assert faux.n("search") >= 3, faux.log
    # budget : un budget épuisé laisse le travail restant, un passage suivant le termine ; les plus notables passent d'abord
    with tempfile.TemporaryDirectory() as tmp:
        ent = os.path.join(tmp, "entites")
        beaucoup = {}
        monde = {"Q2309784": ents["Q2309784"]}
        rech3 = {}
        for i in range(100):
            beaucoup[f"coureur-{i:03d}-19900101"] = {"name": f"Cyc{i:03d} Test", "birth_date": "1990-01-01",
                                                      "saisons": {"2024": {"uci_rank": 1 + (99 - i)}}, "totaux": {"wins": 0}}   # i=99 : rang 1
            q = f"Q{9000 + i}"
            monde[q] = _item(q, f"Cyc{i:03d} Test", "1990-01-01")
            rech3[filtre(f"Cyc{i:03d} Test")] = [q]
        collector._dump(os.path.join(ent, "coureurs", "c.json"), beaucoup)
        faux = FauxWikimedia(monde, rech3, {})
        t = [0.0]
        def fetch3(b, p):
            t[0] += 1.0
            return faux(b, p)
        run_wikidata(1.0, tmp, aujourdhui, Api(fetch3), lambda: t[0], alias_equipes={})     # ~60 s : environ 1 tranche de 40 (41 recherches + 1-2 lectures)
        c1 = collector._load(os.path.join(ent, "wikidata", "coureurs.json"), {})
        assert 0 < len(c1) < 100, len(c1)
        assert "coureur-099-19900101" in c1 and "coureur-000-19900101" not in c1        # meilleur rang d'abord
        n1 = len(c1)
        for _ in range(3):      # chaque passage lit son propre t0 : reprise immédiate à partir du cache
            run_wikidata(1.0, tmp, aujourdhui, Api(fetch3), lambda: t[0], alias_equipes={})
        c2 = collector._load(os.path.join(ent, "wikidata", "coureurs.json"), {})
        assert len(c2) == 100 and n1 < 100 and all(v["qid"] for v in c2.values()), (n1, len(c2))
        assert faux.n("search") == 100                                                       # aucune recherche en double entre passages
        assert faux.n("entites") <= 12, faux.log                                              # lectures par lots de 50
        # abandon de l'hôte (403/429) : passage interrompu proprement, cache déjà acquis conservé
        netutil._blocked_hosts.add("www.wikidata.org")
        try:
            avant = faux.n("search")
            run_wikidata(1.0, tmp, aujourdhui + dt.timedelta(days=200), Api(fetch3), lambda: 0.0, alias_equipes={})
            assert faux.n("search") == avant and len(collector._load(os.path.join(ent, "wikidata", "coureurs.json"), {})) == 100
        finally:
            netutil._blocked_hosts.discard("www.wikidata.org")
    print("[OK] wikidata.py : tests locaux réussis")


def main() -> None:
    ap = argparse.ArgumentParser(description="Wikidata / Commons pour l'encyclopédie : alimente entites/wikidata/ (cache seul)")
    ap.add_argument("archives_dir", nargs="?")
    ap.add_argument("--budget-min", type=float, default=300)
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test or not a.archives_dir:
        _tests()
        if not a.test:
            ap.error("archives_dir obligatoire")
        return
    run_wikidata(a.budget_min, a.archives_dir)


if __name__ == "__main__":
    main()
