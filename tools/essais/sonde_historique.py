#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde de faisabilité : historique d'avant 2009 de l'encyclopédie (Wikidata + Wikipédia), lecture seule.

Mesure, sur un échantillon d'épreuves, ce que Wikidata donne par édition (vainqueur, podium, date, articles
Wikipédia) et ce que le wikitext des articles d'édition permet d'extraire (tableaux de classement, modèles).
Rien n'est écrit dans le dépôt : sorties dans --sortie (JSON de synthèse, cache des réponses, rapport brut).

    python tools/essais/sonde_historique.py series  [--sortie DIR]   # éléments de série + éditions Wikidata
    python tools/essais/sonde_historique.py wikitext [--sortie DIR]  # wikitext fr/en du sous-échantillon
    python tools/essais/sonde_historique.py stats   [--sortie DIR]   # agrège en chiffres (rapport)

Politesse : User-Agent du projet (netutil), 1 requête/s par hôte, pas de maxlag. Les réponses sont mises en
cache disque (relancer ne coûte rien). Un HTTP 429 (limite par IP partagée, avec Retry-After) est attendu puis
retenté ; un 403 abandonne l'hôte. Aucun contournement. Les données lues sont du texte à mesurer : jamais exécutées.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import netutil  # noqa: E402

SORTIE_DEFAUT = "/tmp/claude-0/-home-user/6e2e0406-5df6-58a6-9dc4-3a5a69463a2b/scratchpad/historique"
WD = "https://www.wikidata.org/w/api.php"
LANGS = ["fr", "en", "it", "nl", "es", "de"]
_dernier: Dict[str, float] = {}
_bloques: set = set()
NB_REQ: Counter = Counter()
CACHE_DIR = ""


# ----------------------------------------------------------------------------------------- réseau (cache + 429)
def _get(url: str) -> Optional[str]:
    host = urllib.parse.urlparse(url).netloc
    if host in _bloques:
        return None
    cle = os.path.join(CACHE_DIR, hashlib.sha1(url.encode()).hexdigest() + ".txt")
    if os.path.exists(cle):
        with open(cle, encoding="utf-8") as f:
            return f.read()
    for essai in range(7):
        att = 1.0 - (time.monotonic() - _dernier.get(host, 0))
        if att > 0:
            time.sleep(att)
        _dernier[host] = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": netutil.USER_AGENT, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read()
                if body[:2] == b"\x1f\x8b":
                    import gzip
                    body = gzip.decompress(body)
                txt = body.decode("utf-8", "replace")
            NB_REQ[host] += 1
            with open(cle, "w", encoding="utf-8") as f:
                f.write(txt)
            return txt
        except urllib.error.HTTPError as e:
            if e.code == 429:
                ra = e.headers.get("Retry-After")
                pause = min(int(ra) if ra and ra.isdigit() else 10 * (essai + 1), 60) + 2
                time.sleep(pause)
                continue
            if e.code == 403:
                print(f"[WARN] {host} : 403, hôte abandonné")
                _bloques.add(host)
                return None
            print(f"[WARN] HTTP {e.code} {url[:140]}")
            if e.code in (400, 404):
                return None
            time.sleep(3)
        except Exception as e:  # réseau
            print(f"[WARN] {e} {url[:120]}")
            time.sleep(3)
    return None


def api(base: str, **p: Any) -> Optional[Dict[str, Any]]:
    p.setdefault("format", "json")
    t = _get(base + "?" + urllib.parse.urlencode(p))
    try:
        return json.loads(t) if t else None
    except ValueError:
        return None


def entites(ids: List[str], props: str = "claims|labels|sitelinks|descriptions") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    ids = sorted(set(ids))
    for i in range(0, len(ids), 50):
        r = api(WD, action="wbgetentities", ids="|".join(ids[i:i + 50]), props=props,
                languages="fr|en", sitefilter="|".join(l + "wiki" for l in LANGS))
        out.update((r or {}).get("entities", {}))
    return out


def recherche_statement(prop: str, qid: str) -> List[str]:
    """Éléments portant prop=qid (CirrusSearch haswbstatement), pagination par 500."""
    res, off = [], 0
    while True:
        r = api(WD, action="query", list="search", srsearch=f"haswbstatement:{prop}={qid}", srlimit=500,
                sroffset=off, srnamespace=0, srprop="")
        if not r:
            break
        lot = [x["title"] for x in r.get("query", {}).get("search", [])]
        res += lot
        nxt = r.get("continue", {}).get("sroffset")
        if not nxt or not lot:
            break
        off = nxt
    return res


# ----------------------------------------------------------------------------------------- lecture Wikidata
def decl(e: Dict[str, Any], prop: str) -> List[Dict[str, Any]]:
    return [c for c in (e.get("claims") or {}).get(prop, []) if c.get("rank") != "deprecated"]


def val(c: Dict[str, Any]) -> Any:
    return ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")


def qids(e: Dict[str, Any], prop: str) -> List[str]:
    return [v["id"] for v in map(val, decl(e, prop)) if isinstance(v, dict) and "id" in v]


def annee(v: Any) -> Optional[int]:
    m = re.match(r"([+-])(\d+)-", (v or {}).get("time", "")) if isinstance(v, dict) else None
    return int(m.group(2)) * (1 if m.group(1) == "+" else -1) if m else None


def precision(v: Any) -> int:
    return int((v or {}).get("precision") or 0) if isinstance(v, dict) else 0


def lib(e: Dict[str, Any], lang: str = "fr") -> str:
    l = e.get("labels", {})
    return (l.get(lang) or l.get("en") or {}).get("value", "")


# Épreuves : (clé, recherche fr, recherche en, catégorie)
EPREUVES = [
    ("tdf", "Tour de France", "Tour de France", "GT"), ("giro", "Tour d'Italie", "Giro d'Italia", "GT"),
    ("vuelta", "Tour d'Espagne", "Vuelta a España", "GT"),
    ("msr", "Milan-San Remo", "Milan–San Remo", "Monument"), ("rvv", "Tour des Flandres", "Tour of Flanders", "Monument"),
    ("pr", "Paris-Roubaix", "Paris–Roubaix", "Monument"), ("lbl", "Liège-Bastogne-Liège", "Liège–Bastogne–Liège", "Monument"),
    ("lom", "Tour de Lombardie", "Giro di Lombardia", "Monument"),
    ("pn", "Paris-Nice", "Paris–Nice", "WT"), ("dau", "Critérium du Dauphiné", "Critérium du Dauphiné", "WT"),
    ("tds", "Tour de Suisse", "Tour de Suisse", "WT"), ("tir", "Tirreno-Adriatico", "Tirreno–Adriatico", "WT"),
    ("fw", "Flèche wallonne", "La Flèche Wallonne", "WT"), ("gw", "Gand-Wevelgem", "Gent–Wevelgem", "WT"),
    ("amstel", "Amstel Gold Race", "Amstel Gold Race", "WT"), ("cat", "Tour de Catalogne", "Volta a Catalunya", "WT"),
    ("pb", "Tour du Pays basque", "Tour of the Basque Country", "WT"), ("rom", "Tour de Romandie", "Tour de Romandie", "WT"),
    ("pt", "Paris-Tours", "Paris–Tours", "WT"), ("bc", "Bretagne Classic", "Bretagne Classic", "WT"),
    ("css", "Clasica San Sebastian", "Clásica de San Sebastián", "WT"), ("omloop", "Omloop Het Nieuwsblad", "Omloop Het Nieuwsblad", "WT"),
    ("e3", "E3 Saxo Classic", "E3 Saxo Classic", "WT"),
    ("ain", "Tour de l'Ain", "Tour de l'Ain", "FR"), ("occ", "Route d'Occitanie", "Route d'Occitanie", "FR"),
    ("mayenne", "Boucles de la Mayenne", "Boucles de la Mayenne", "FR"), ("limousin", "Tour du Limousin", "Tour du Limousin", "FR"),
    ("camembert", "Paris-Camembert", "Paris–Camembert", "FR"), ("plumelec", "Grand Prix de Plumelec-Morbihan", "Grand Prix de Plumelec-Morbihan", "FR"),
    ("tbl", "Tro-Bro Leon", "Tro-Bro Léon", "FR"), ("polynormande", "Polynormande", "Polynormande", "FR"),
    ("doubs", "Tour du Doubs", "Tour du Doubs", "FR"), ("cla", "Classic Loire-Atlantique", "Classic Loire-Atlantique", "FR"),
    ("cholet", "Cholet-Pays de la Loire", "Cholet-Pays de Loire", "FR"), ("denain", "Grand Prix de Denain", "Grand Prix de Denain", "FR"),
    ("vendee", "Tour de Vendée", "Tour de Vendée", "FR"), ("bourges", "Paris-Bourges", "Paris–Bourges", "FR"),
    ("cdn", "Chrono des Nations", "Chrono des Nations", "FR"), ("champfr", "Championnat de France de cyclisme sur route", "French National Road Race Championships", "FR"),
]


# ----------------------------------------------------------------------------------------- partie « series »
RANGS = {"Q20882667": 1, "Q20882668": 2, "Q20882669": 3}   # P2501 « résultat » : vainqueur / 2e / 3e du classement général
EXCLUS = re.compile(r"women|femme|féminin|junior|espoir|u23|under|stage of|^\d{4}|edition|video game|song|film|chanson|jeu", re.I)
LIENS_EDITION = ("P31", "P179", "P3450", "P361")
# Séries que la recherche par nom ne propose pas (description « recurring sporting event » écartée ou absente) : QID vérifiés à la main
SURCHARGES = {"omloop": "Q506447", "camembert": "Q1400788"}


def candidats_serie(fr: str, en: str) -> List[Dict[str, Any]]:
    vus, res = set(), []
    for lang, q in (("fr", fr), ("en", en)):
        r = api(WD, action="wbsearchentities", search=q, language=lang, limit=7, type="item")
        for x in (r or {}).get("search", []):
            if x["id"] in vus:
                continue
            vus.add(x["id"])
            d = x.get("description") or ""
            if EXCLUS.search(d) or EXCLUS.search(x.get("label") or ""):
                continue
            if not re.search(r"cycl|bicycle|race|course|wielr|ciclis|sporting event", d, re.I):
                continue
            res.append({"qid": x["id"], "label": x.get("label"), "desc": d})
    return res[:4]


def annee_edition(e: Dict[str, Any]) -> Dict[str, Any]:
    for p in ("P585", "P580", "P582"):
        d = decl(e, p)
        if d and annee(val(d[0])):
            return {"annee": annee(val(d[0])), "src": p, "prec": precision(val(d[0]))}
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", lib(e) + " " + lib(e, "en"))
    return {"annee": int(m.group(1)), "src": "libelle", "prec": 9} if m else {"annee": None, "src": None, "prec": 0}


def resume_edition(qid: str, e: Dict[str, Any]) -> Dict[str, Any]:
    rangs: Dict[int, List[str]] = defaultdict(list)
    sans_q = []
    for c in decl(e, "P1346"):
        v = val(c)
        if not isinstance(v, dict):
            continue
        qs = [(x.get("datavalue") or {}).get("value", {}).get("id") for x in (c.get("qualifiers") or {}).get("P2501", [])]
        r = [RANGS[q] for q in qs if q in RANGS]
        if r:
            rangs[r[0]].append(v["id"])
        else:
            sans_q.append(v["id"])
    cl = decl(e, "P2321")   # classement général : un coureur par déclaration, qualificatifs P1352 rang, P2781 temps, P2911 écart, P2912 équipe
    p2321 = [val(c)["id"] for c in cl if isinstance(val(c), dict)][:3]
    qs = lambda c, pr: (c.get("qualifiers") or {}).get(pr, [])
    classement = {"n": len(cl), "avec_rang": sum(1 for c in cl if qs(c, "P1352")),
                  "avec_temps_ou_ecart": sum(1 for c in cl if qs(c, "P2781") or qs(c, "P2911")),
                  "avec_equipe": sum(1 for c in cl if qs(c, "P2912")),
                  "rang1": [val(c)["id"] for c in cl if isinstance(val(c), dict) and any(
                      (x.get("datavalue") or {}).get("value", {}).get("amount") == "+1" for x in qs(c, "P1352"))][:2]}
    out = {"qid": qid, "label": lib(e), **annee_edition(e), "rangs": {str(k): v for k, v in sorted(rangs.items())},
           "p1346_sans_rang": sans_q, "p2321": p2321, "classement": classement, "nb_p1923": len(decl(e, "P1923")),
           "nb_p527": len(decl(e, "P527")),
           "langues": sorted(k[:-4] for k in (e.get("sitelinks") or {}) if k[:-4] in LANGS),
           "titres": {k[:-4]: v.get("title") for k, v in (e.get("sitelinks") or {}).items() if k[:-4] in LANGS},
           "p31": qids(e, "P31")[:3]}
    return out


def faire_series(sortie: str, seulement: Optional[List[str]] = None) -> None:
    chemin = os.path.join(sortie, "series.json")
    res: Dict[str, Any] = json.load(open(chemin)) if os.path.exists(chemin) else {}
    for cle, fr, en, cat in EPREUVES:
        if seulement and cle not in seulement:
            continue
        if cle in res and res[cle].get("editions") is not None:
            continue
        cands = candidats_serie(fr, en)
        if cle in SURCHARGES and SURCHARGES[cle] not in [c["qid"] for c in cands]:
            cands.insert(0, {"qid": SURCHARGES[cle], "label": cle, "desc": "surcharge"})
        meilleur = None
        for c in cands:
            c["comptes"] = {}
            for prop in LIENS_EDITION:
                c["comptes"][prop] = len(recherche_statement(prop, c["qid"]))
                if c["comptes"][prop] >= 3 and prop == "P31":
                    break   # P31 est le lien observé ; les autres ne sont testés que s'il échoue
            c["total"] = max(c["comptes"].values())
            if not meilleur or c["total"] > meilleur["total"]:
                meilleur = c
        r = {"cat": cat, "recherche": [fr, en], "candidats": cands, "choix": meilleur and meilleur["qid"], "editions": None}
        if meilleur and meilleur["total"] > 0:
            prop = max(meilleur["comptes"], key=lambda p: meilleur["comptes"][p])
            lst = recherche_statement(prop, meilleur["qid"])
            E = entites(lst)
            S = entites([meilleur["qid"]], props="claims|labels|descriptions|sitelinks")[meilleur["qid"]]
            incep = [annee(val(c)) for c in decl(S, "P571")]
            r.update({"lien": prop, "serie_label": lib(S), "inception": incep[:1], "pays": qids(S, "P17")[:1],
                      "serie_sitelinks": sorted(k[:-4] for k in S.get("sitelinks", {}) if k[:-4] in LANGS),
                      "editions": sorted((resume_edition(k, e) for k, e in E.items()), key=lambda x: (x["annee"] or 0, x["qid"]))})
        res[cle] = r
        json.dump(res, open(chemin, "w"), ensure_ascii=False, indent=1)
        n = len(r["editions"] or [])
        print(f"[series] {cle:12} -> {r['choix']} {meilleur and meilleur['label']!r} lien={r.get('lien')} editions={n} (req wd={NB_REQ['www.wikidata.org']})", flush=True)

    # coureurs : vainqueurs / podiums des éditions <= 2008
    ids = set()
    for r in res.values():
        for ed in r.get("editions") or []:
            if ed["annee"] and ed["annee"] <= 2008:
                for l in ed["rangs"].values():
                    ids.update(l)
                ids.update(ed["p1346_sans_rang"])
    chemin_c = os.path.join(sortie, "coureurs.json")
    cour: Dict[str, Any] = json.load(open(chemin_c)) if os.path.exists(chemin_c) else {}
    restants = sorted(i for i in ids if i not in cour)
    print(f"[coureurs] {len(ids)} ids distincts, {len(restants)} à lire", flush=True)
    for i in range(0, len(restants), 50):
        E = entites(restants[i:i + 50], props="claims|labels|sitelinks")
        for k, e in E.items():
            nais = decl(e, "P569")
            cour[k] = {"label": lib(e), "naissance": (nais and ((val(nais[0]) or {}).get("time"))) or None,
                       "prec": precision(val(nais[0])) if nais else 0, "p106": qids(e, "P106")[:4],
                       "langues": sorted(x[:-4] for x in e.get("sitelinks", {}) if x[:-4] in LANGS)}
        json.dump(cour, open(chemin_c, "w"), ensure_ascii=False)
        print(f"[coureurs] {min(i + 50, len(restants))}/{len(restants)}", flush=True)


# ----------------------------------------------------------------------------------------- partie « wikitext »
# (série, année, titres de repli par langue si l'élément Wikidata n'a pas d'article ou d'élément)
SOUS_ECHANTILLON = [("tdf", 1985), ("tdf", 1995), ("tdf", 2005), ("pr", 1990), ("pr", 2000), ("ain", 2003),
                    ("pt", 1998), ("dau", 2002), ("bc", 2005)]
REPLI = {"ain": {"fr": "Tour de l'Ain 2003", "en": "2003 Tour de l'Ain", "de": "Tour de l’Ain 2003"},
         "bc": {"fr": "Grand Prix de Plouay 2005", "en": "2005 GP Ouest-France", "de": "GP Ouest-France 2005"}}
RE_TEMPS = re.compile(r"\d+\s*h\s*\d+|\d{1,2}:\d\d:\d\d|\d+['’′]\s*\d*|\bm\.?\s*t\.?\b|\bs\.?\s*t\.?\b|\+\s*\d|\d+\s*(?:min|sec|s)\b|\bsame time\b|\bzelfde tijd\b", re.I)
RE_TITRE = re.compile(r"^(=+)\s*(.*?)\s*\1\s*$")
RE_GC = re.compile(r"g[ée]n[ée]ral|general|gesamt|algemeen|generale|final|uitslag|classification|ergebnis|result|resultat|r[ée]sultat|classement|ranking|ordine", re.I)
RE_ETAPES = re.compile(r"[ée]tape|stage|etappe|tappa|stages", re.I)
RE_MAILLOTS = re.compile(r"maillot|jersey|trikot|maglia|trui|polka|pois|vert|green|points|montagne|mountain|jeune|young|combin", re.I)


def wikitext(lang: str, titre: str) -> Optional[str]:
    r = api(f"https://{lang}.wikipedia.org/w/api.php", action="query", prop="revisions", rvprop="content",
            rvslots="main", titles=titre, redirects=1, formatversion=2)
    pages = ((r or {}).get("query") or {}).get("pages") or []
    if not pages or pages[0].get("missing"):
        return None
    revs = pages[0].get("revisions") or []
    return ((revs[0].get("slots") or {}).get("main") or {}).get("content") if revs else None


def tables(wt: str) -> List[Dict[str, Any]]:
    """Tableaux wikitable : titre de section précédent, lignes, colonnes, liens, temps, modèles dans les cellules."""
    out, titre, cur, depth = [], "", None, 0
    for ln in wt.split("\n"):
        m = RE_TITRE.match(ln.strip())
        if m and cur is None:
            titre = re.sub(r"[\[\]']|<.*?>", "", m.group(2))
        s = ln.strip()
        if s.startswith("{|"):
            if cur is None:
                cur = {"titre": titre, "lignes": [[]], "entete": s}
            depth += 1
        elif s.startswith("|}") and cur is not None:
            depth -= 1
            if depth == 0:
                out.append(cur)
                cur = None
        elif cur is not None and depth == 1:
            if s.startswith("|-"):
                cur["lignes"].append([])
            elif s[:1] in "|!" and not s.startswith("|+"):
                cells = re.split(r"\|\||!!", s[1:])
                cur["lignes"][-1].extend(cells)
    res = []
    for t in out:
        L = [l for l in t["lignes"] if l]
        if not L:
            continue
        corps = [l for l in L if not all(c.strip().startswith(("scope", "style", "class")) or "!" in c for c in l[:1]) or True]
        res.append({"titre": t["titre"], "lignes": len(L), "colonnes_max": max(len(l) for l in L),
                    "colonnes_mediane": sorted(len(l) for l in L)[len(L) // 2],
                    "avec_lien": sum(1 for l in L if any("[[" in c for c in l)),
                    "avec_temps": sum(1 for l in L if any(RE_TEMPS.search(c) for c in l)),
                    "avec_modele": sum(1 for l in L if any("{{" in c for c in l)),
                    "avec_rang_num": sum(1 for l in L if l and re.fullmatch(r"\W*\d{1,3}\W*(?:er|e|ème|º|°)?\W*", re.sub(r"^[^|]*\|(?!\|)", "", l[0]).strip() or "x")),
                    "entete": t["entete"][:80], "premiere_ligne": [c.strip()[:50] for c in L[0][:6]],
                    "exemple": [c.strip()[:60] for c in (L[min(2, len(L) - 1)])[:6]]})
    return res


def analyser(wt: str) -> Dict[str, Any]:
    mods = Counter(re.sub(r"\s+", " ", m.group(1).strip().lower()) for m in re.finditer(r"\{\{\s*([^{}|\n#]+?)\s*(?=\||\}\})", wt))
    T = tables(wt)
    gc = [t for t in T if RE_GC.search(t["titre"]) and t["lignes"] >= 10]
    gc.sort(key=lambda t: -t["lignes"])
    et = [t for t in T if RE_ETAPES.search(t["titre"]) and t["lignes"] >= 4]
    et.sort(key=lambda t: -t["lignes"])
    mai = [t for t in T if RE_MAILLOTS.search(t["titre"])]
    titres = [m.group(2) for m in (RE_TITRE.match(l.strip()) for l in wt.split("\n")) if m]
    return {"octets": len(wt), "n_tableaux": len(T), "modeles_top": mods.most_common(14),
            "n_liens": wt.count("[["), "sections": titres[:40],
            "tableau_classement": gc[0] if gc else None, "tableaux_candidats": [(t["titre"], t["lignes"]) for t in gc[:5]],
            "tableau_etapes": et[0] if et else None, "tableaux_maillots": [(t["titre"], t["lignes"]) for t in mai[:6]],
            "tous_tableaux": [(t["titre"], t["lignes"], t["colonnes_mediane"], t["avec_temps"]) for t in T[:25]]}


def faire_wikitext(sortie: str) -> None:
    ser = json.load(open(os.path.join(sortie, "series.json")))
    chemin = os.path.join(sortie, "wikitext.json")
    res: Dict[str, Any] = {}
    for cle, an in SOUS_ECHANTILLON:
        ed = next((e for e in (ser.get(cle, {}).get("editions") or []) if e["annee"] == an), None)
        rep = REPLI.get(cle, {})
        ligne: Dict[str, Any] = {"edition_wikidata": ed and ed["qid"]}
        for lang in ("fr", "en", "de"):
            titre = (ed or {}).get("titres", {}).get(lang) or rep.get(lang)
            if not titre:
                ligne[lang] = {"titre": None}
                continue
            wt = wikitext(lang, titre)
            if wt is None:
                ligne[lang] = {"titre": titre, "absent": True}
                continue
            ligne[lang] = {"titre": titre, **analyser(wt)}
        res[f"{cle}-{an}"] = ligne
        json.dump(res, open(chemin, "w"), ensure_ascii=False, indent=1)
        for lang in ("fr", "en", "de"):
            x = ligne[lang]
            gc = x.get("tableau_classement") or {}
            print(f"[wikitext] {cle}-{an} {lang}: {x.get('titre')!r} {x.get('octets')} o, {x.get('n_tableaux')} tableaux, "
                  f"classement={gc.get('titre')!r} {gc.get('lignes')} l. {gc.get('colonnes_mediane')} col, liens={gc.get('avec_lien')}, "
                  f"temps={gc.get('avec_temps')}", flush=True)


def faire_stats(sortie: str) -> None:
    """Agrège series.json + coureurs.json en chiffres (tableau texte + stats.json)."""
    ser = json.load(open(os.path.join(sortie, "series.json")))
    cour = json.load(open(os.path.join(sortie, "coureurs.json")))
    GUERRES = set(range(1915, 1919)) | set(range(1940, 1946))
    pct = lambda a, b: round(100 * a / b) if b else None
    glob: Dict[str, Counter] = defaultdict(Counter)
    out: Dict[str, Any] = {}
    lignes = []
    for cle, r in ser.items():
        eds = [e for e in (r.get("editions") or []) if e["annee"]]
        eds_av = [e for e in eds if e["annee"] <= 2008]
        if not eds:
            lignes.append(f"{cle:12} AUCUNE ÉDITION")
            continue
        annees = Counter(e["annee"] for e in eds)
        premiere = min(annees)
        attendues = [y for y in range(premiere, 2009) if y not in GUERRES]
        manquantes = [y for y in attendues if y not in annees]
        doublons = sum(1 for y, n in annees.items() if n > 1)

        def gagnant(e):
            return bool(e["rangs"].get("1") or e["classement"]["rang1"] or len(e["p1346_sans_rang"]) == 1)
        d = {"serie": r["choix"], "libelle": r.get("serie_label"), "cat": r["cat"], "premiere_edition_wd": premiere,
             "inception_serie": (r.get("inception") or [None])[0], "n_editions_avant_2009": len(eds_av),
             "annees_attendues_manquantes": len(manquantes), "annees_attendues": len(attendues), "doublons_annee": doublons,
             "pct_vainqueur": pct(sum(gagnant(e) for e in eds_av), len(eds_av)),
             "pct_podium_p1346": pct(sum(all(e["rangs"].get(k) for k in "123") for e in eds_av), len(eds_av)),
             "pct_classement_top10": pct(sum(e["classement"]["n"] >= 10 for e in eds_av), len(eds_av)),
             "pct_classement_avec_temps": pct(sum(e["classement"]["avec_temps_ou_ecart"] >= 3 for e in eds_av), len(eds_av)),
             "pct_fr": pct(sum("fr" in e["langues"] for e in eds_av), len(eds_av)),
             "pct_en": pct(sum("en" in e["langues"] for e in eds_av), len(eds_av)),
             "pct_fr_ou_en": pct(sum(bool({"fr", "en"} & set(e["langues"])) for e in eds_av), len(eds_av)),
             "pct_it": pct(sum("it" in e["langues"] for e in eds_av), len(eds_av)),
             "pct_nl": pct(sum("nl" in e["langues"] for e in eds_av), len(eds_av)),
             "pct_es": pct(sum("es" in e["langues"] for e in eds_av), len(eds_av)),
             "pct_de": pct(sum("de" in e["langues"] for e in eds_av), len(eds_av)),
             "pct_date_jour": pct(sum(e["prec"] >= 11 for e in eds_av), len(eds_av)), "sans_date_wd": sum(1 for e in r["editions"] if not e["annee"])}
        out[cle] = d
        lignes.append(f"{cle:12} {d['libelle'][:26]:26} 1re={premiere} av.2009={len(eds_av):3} manq={len(manquantes):3}/{len(attendues):3} "
                      f"vq={d['pct_vainqueur']}% pod={d['pct_podium_p1346']}% top10={d['pct_classement_top10']}% tps={d['pct_classement_avec_temps']}% "
                      f"fr={d['pct_fr']}% en={d['pct_en']}% fr|en={d['pct_fr_ou_en']}% it={d['pct_it']} nl={d['pct_nl']} es={d['pct_es']} de={d['pct_de']}")
        for e in eds_av:
            dec = e["annee"] // 10 * 10
            c = glob[dec]
            c["n"] += 1
            c["vainqueur"] += gagnant(e)
            c["podium"] += all(e["rangs"].get(k) for k in "123")
            c["top10"] += e["classement"]["n"] >= 10
            c["fr"] += "fr" in e["langues"]
            c["en"] += "en" in e["langues"]
            c["fr_ou_en"] += bool({"fr", "en"} & set(e["langues"]))
            c["any_lang"] += bool(e["langues"])
    print("\n".join(lignes))
    print("\nPar décennie (toutes épreuves, éditions avec élément Wikidata) :")
    dec_out = {}
    for dec in sorted(glob):
        c = glob[dec]
        dec_out[dec] = {k: (pct(v, c["n"]) if k != "n" else v) for k, v in c.items()}
        print(dec, dec_out[dec])
    # coureurs
    ids = {"gagnants": set(), "podium": set()}
    for r in ser.values():
        for e in r.get("editions") or []:
            if e["annee"] and e["annee"] <= 2008:
                for k, l in e["rangs"].items():
                    (ids["gagnants"] if k == "1" else ids["podium"]).update(l)
                ids["gagnants"].update(e["p1346_sans_rang"][:1] if len(e["p1346_sans_rang"]) == 1 else [])
    rc: Dict[str, Any] = {}
    for nom, st in ids.items():
        L = [cour[i] for i in st if i in cour]
        rc[nom] = {"distincts": len(st), "lus": len(L), "avec_naissance": sum(1 for c in L if c["naissance"]),
                   "naissance_jour": sum(1 for c in L if c["prec"] >= 11), "naissance_annee_seule": sum(1 for c in L if c["naissance"] and c["prec"] < 11),
                   "p106_cycliste": sum(1 for c in L if "Q2309784" in c["p106"] or c["p106"]), "avec_fr": sum(1 for c in L if "fr" in c["langues"]),
                   "avec_en": sum(1 for c in L if "en" in c["langues"])}
    print("\nCoureurs (vainqueurs / 2e-3e) :", json.dumps(rc, ensure_ascii=False))
    # naissance_jour par décennie de l'édition la plus ancienne (approx) : sur les vainqueurs
    parde: Dict[int, Counter] = defaultdict(Counter)
    for r in ser.values():
        for e in r.get("editions") or []:
            if e["annee"] and e["annee"] <= 2008:
                for q in e["rangs"].get("1", []):
                    c = cour.get(q)
                    if c:
                        parde[e["annee"] // 10 * 10]["n"] += 1
                        parde[e["annee"] // 10 * 10]["jour"] += c["prec"] >= 11
    print("Vainqueurs avec naissance au jour, par décennie :", {d: f"{pct(c['jour'], c['n'])}% ({c['n']})" for d, c in sorted(parde.items())})
    volume = sum(len(r.get("editions") or []) for r in ser.values())
    print("Éditions Wikidata totales (toutes années) :", volume, "| avant 2009 :", sum(v['n_editions_avant_2009'] for v in out.values()))
    json.dump({"epreuves": out, "decennies": dec_out, "coureurs": rc}, open(os.path.join(sortie, "stats.json"), "w"), ensure_ascii=False, indent=1)


def faire_souseditions(sortie: str, cle: str) -> None:
    """Séries dont l'élément d'édition est un « championnat » : épreuve masculine en ligne = élément P527 de l'édition."""
    ser = json.load(open(os.path.join(sortie, "series.json")))
    eds = [e for e in ser[cle]["editions"] if e["annee"] and e["annee"] <= 2008]
    E = entites([e["qid"] for e in eds])
    parts = {q: qids(e, "P527") for q, e in E.items()}
    P = entites([x for l in parts.values() for x in l])
    res = []
    for ed in eds:
        hom = [P[x] for x in parts.get(ed["qid"], []) if x in P and "Course en ligne masculine" in lib(P[x]) + lib(P[x], "en") or
               (x in P and re.search(r"men'?s? .*road race|masculine", lib(P[x]) + lib(P[x], "en"), re.I) and not re.search(r"wom|f[ée]min", lib(P[x]) + lib(P[x], "en"), re.I))]
        if hom:
            r = resume_edition(hom[0].get("id", ""), hom[0])
            res.append({"annee": ed["annee"], "sous_edition": hom[0].get("id"), "rangs": r["rangs"], "classement": r["classement"], "langues": r["langues"]})
        else:
            res.append({"annee": ed["annee"], "sous_edition": None, "parts": len(parts.get(ed["qid"], []))})
    json.dump(res, open(os.path.join(sortie, f"souseditions_{cle}.json"), "w"), ensure_ascii=False, indent=1)
    ok = [r for r in res if r.get("sous_edition")]
    print(f"[souseditions] {cle}: {len(res)} éditions <=2008, {len(ok)} avec épreuve masculine en ligne, "
          f"vainqueur={sum(1 for r in ok if r['rangs'].get('1'))}, podium={sum(1 for r in ok if all(r['rangs'].get(k) for k in '123'))}, "
          f"classement>=10={sum(1 for r in ok if r['classement']['n'] >= 10)}, fr|en={sum(1 for r in ok if {'fr','en'} & set(r['langues']))}")


def main() -> None:
    global CACHE_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["series", "wikitext", "stats", "souseditions"])
    ap.add_argument("--sortie", default=SORTIE_DEFAUT)
    ap.add_argument("--only", default="", help="clés d'épreuves séparées par des virgules")
    a = ap.parse_args()
    os.makedirs(a.sortie, exist_ok=True)
    CACHE_DIR = os.path.join(a.sortie, "cache")
    os.makedirs(CACHE_DIR, exist_ok=True)
    if a.cmd == "series":
        faire_series(a.sortie, [x for x in a.only.split(",") if x])
    elif a.cmd == "souseditions":
        faire_souseditions(a.sortie, "champfr")
    elif a.cmd == "wikitext":
        faire_wikitext(a.sortie)
    else:
        faire_stats(a.sortie)


if __name__ == "__main__":
    main()
