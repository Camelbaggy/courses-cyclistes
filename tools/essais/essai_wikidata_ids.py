#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai « piste 1 » : identifiants externes de Wikidata (CQ Ranking, Museo, the-sports.org, Mémoire du Cyclisme, PCS, FirstCycling…).

Lecture seule, politesse de wikidata.py (UA du projet, 1 requête/s, lots de 50, abandon sur 403/429). Rien n'est écrit dans le dépôt.
Phases (fichier `tools/essais/wikidata_ids.cfg`, lignes `phases: a b c`, `props: cq=P1541 museo=Pxxx thesports=Pxxx`, `taille: 1200`) :

  proprietes   recherche de propriétés (wbsearchentities type=property) + libellé / format des propriétés connues
  couverture   échantillon de coureurs (cache UCI + historique) / séries / éditions : identifiants externes présents, par groupe ;
               propriétés détectées automatiquement par leur formatter URL ; croisement avec nos fichiers (sens Wikidata -> nous)
  sonde_or     test de la syntaxe OU de CirrusSearch (haswbstatement:P=a|P=b)
  inverse_cq / inverse_museo / inverse_thesports   sens nous -> Wikidata : chaque id de nos fichiers est cherché (haswbstatement:P=<id>),
               puis comparé (naissance, nom) et au rapprochement nom + date existant (cache `entites/wikidata/coureurs.json`)

Les données d'archives sont lues dans $ARCHIVES (dossier `data/archives`), sinon clonées depuis le dépôt public d'archives.
"""
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RACINE)
import netutil  # noqa: E402
import wikidata  # noqa: E402

CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wikidata_ids.cfg")
T0 = time.time()
PROPS_CONNUES = {"P1541": "CQ Ranking coureur", "P2648": "CQ Ranking course", "P1409": "Cycling Archives coureur", "P2330": "Cycling Archives",
                 "P1663": "ProCyclingStats coureur", "P2327": "ProCyclingStats", "P10902": "FirstCycling coureur"}
DOMAINES = {"cq": "cqranking.com", "museo": "museociclismo.it", "thesports": "the-sports.org", "mdc": "memoire", "pcs": "procyclingstats",
            "fc": "firstcycling", "cyclingarchives": "cyclingarchives", "sitducyclisme": "sitducyclisme", "cyclingranking": "cyclingranking",
            "cyclebase": "cyclebase", "cyclingdb": "cyclingdatabase"}
RE_CYCLO = re.compile(r"cycl|cqranking|museo|m[ée]moire|the-sports|v[ée]lo|rider|coureur|ranking|procycl|firstcycl", re.I)
RE_NON_PERSONNE = re.compile(r"race|course|team|[ée]quipe|competition|tour\b|[ée]preuve|edition|[ée]dition", re.I)


def cfg() -> Dict[str, str]:
    d: Dict[str, str] = {}
    if os.path.exists(CFG):
        for l in open(CFG, encoding="utf-8"):
            if ":" in l and not l.startswith("#"):
                k, v = l.split(":", 1)
                d[k.strip()] = v.strip()
    return d


def t() -> str:
    return f"t+{time.time() - T0:.0f}s"


def charger(chemin: str, defaut: Any = None) -> Any:
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def racine_archives() -> str:
    if os.environ.get("ARCHIVES"):
        return os.environ["ARCHIVES"]
    dest = "/tmp/archives_clone"
    if not os.path.isdir(os.path.join(dest, "data", "archives")):
        subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
                        "https://github.com/Camelbaggy/courses-cyclistes-archives", dest], check=True)
        subprocess.run(["git", "-C", dest, "sparse-checkout", "set", "data/archives/sources", "data/archives/entites/wikidata",
                        "data/archives/entites/historique"], check=True)
        subprocess.run(["git", "-C", dest, "checkout"], check=False)
    return os.path.join(dest, "data", "archives")


# --------------------------------------------------------------------------- nos données
def index_cq(A: str) -> Dict[str, Dict[str, Any]]:
    d = charger(f"{A}/sources/cqranking/coureurs.json", {})
    return {k: {"nom": v.get("nom"), "naissance": v.get("naissance")} for k, v in d.items() if isinstance(v, dict) and v.get("nom")}


def index_museo(A: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    base = f"{A}/sources/museo/editions"
    for c in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        for f in os.listdir(f"{base}/{c}"):
            d = charger(f"{base}/{c}/{f}", {})
            for l in d.get("classement") or []:
                if l.get("id") and l.get("nom") and str(l["id"]) not in out:
                    out[str(l["id"])] = {"nom": l["nom"], "naissance": None}
    for c in (charger(f"{A}/sources/museo/courses.json", {}).get("courses") or {}).values():
        for e in c.get("editions") or []:
            v = e.get("vainqueur") or {}
            if v.get("id") and v.get("nom") and str(v["id"]) not in out:
                out[str(v["id"])] = {"nom": v["nom"], "naissance": None}
    return out


def index_thesports(A: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    base = f"{A}/sources/thesports/editions"
    for c in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        for f in os.listdir(f"{base}/{c}"):
            d = charger(f"{base}/{c}/{f}", {})
            for s in d.get("sections") or []:
                for l in s.get("lignes") or []:
                    if l.get("id_site") and l.get("nom") and str(l["id_site"]) not in out:
                        out[str(l["id_site"])] = {"nom": l["nom"], "naissance": None}
    for k, v in (charger(f"{A}/sources/thesports/coureurs.json", {}) or {}).items():
        if k in out and isinstance(v, dict) and v.get("precision") == "jour":
            out[k]["naissance"] = v.get("naissance")
    return out


INDEX = {"cq": index_cq, "museo": index_museo, "thesports": index_thesports}


# --------------------------------------------------------------------------- Wikidata
class Ctx:
    def __init__(self) -> None:
        wikidata.preparer_reseau()
        self.api = wikidata.Api()


def ext_ids(e: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for p, cs in ((e or {}).get("claims") or {}).items():
        for c in cs:
            ms = c.get("mainsnak") or {}
            if ms.get("datatype") == "external-id" and ms.get("snaktype") == "value" and c.get("rank") != "deprecated":
                out.setdefault(p, []).append(str((ms.get("datavalue") or {}).get("value")))
    return out


def meta_props(ctx: Ctx, props: List[str]) -> Dict[str, Dict[str, Any]]:
    res = wikidata.lire_entites(ctx.api, props, "labels|descriptions|claims", "fr|en")
    out: Dict[str, Dict[str, Any]] = {}
    for p, e in res.items():
        if not e:
            continue
        form = [wikidata.valeur(c) for c in wikidata.revendications(e, "P1630")]
        regex = [wikidata.valeur(c) for c in wikidata.revendications(e, "P1793")]
        out[p] = {"fr": ((e.get("labels") or {}).get("fr") or {}).get("value"), "en": ((e.get("labels") or {}).get("en") or {}).get("value"),
                  "desc": (((e.get("descriptions") or {}).get("en") or {}).get("value") or ((e.get("descriptions") or {}).get("fr") or {}).get("value")),
                  "formatter": form[0] if form else None, "regex": regex[0] if regex else None, "datatype": e.get("datatype")}
    return out


def classer_props(meta: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """{source: {"personne": P, "autre": [P…]}} d'après le domaine du formatter et le libellé."""
    out: Dict[str, Dict[str, Any]] = {}
    for p, m in meta.items():
        f = (m.get("formatter") or "").lower()
        for src, dom in DOMAINES.items():
            if dom in f:
                lib = f"{m.get('en') or ''} {m.get('fr') or ''}"
                typ = "autre" if RE_NON_PERSONNE.search(lib) else "personne"
                out.setdefault(src, {}).setdefault(typ, []).append(p)
    return out


def phase_proprietes(ctx: Ctx) -> None:
    print(f"\n######## proprietes ({t()})")
    termes = ["CQ Ranking", "Museo del Ciclismo", "Mémoire du Cyclisme", "the-sports.org", "CyclingRanking", "CycleBase", "Cycling Archives",
              "Site du Cyclisme", "ProCyclingStats", "FirstCycling", "Cycling Database", "cyclist ID", "cycling race ID"]
    vus: Dict[str, str] = {}
    for terme in termes:
        for lang in ("en", "fr"):
            rep = ctx.api.appel(wikidata.WD_API, action="wbsearchentities", search=terme, language=lang, type="property", limit=8)
            for r in (rep or {}).get("search", []):
                vus.setdefault(r["id"], f"{r.get('label')} | {r.get('description')}")
                print(f"  [{terme!r}/{lang}] {r['id']} {r.get('label')} | {r.get('description')}")
    for terme in ("museociclismo", "museociclismo.it", "Museo del Ciclismo ID", "Museo Ciclismo ciclista", "memoireducyclisme", "cyclist ID Italian museum", "Cycling Museum"):
        for ns in (120,):
            rep = ctx.api.appel(wikidata.WD_API, action="query", list="search", srsearch=terme, srnamespace=ns, srlimit=10)
            print(f"  [recherche plein texte espace Property « {terme} »] :", [r["title"] for r in ((rep or {}).get("query") or {}).get("search", [])])
            for r in ((rep or {}).get("query") or {}).get("search", []):
                vus.setdefault(r["title"].replace("Property:", ""), "plein texte")
    meta = meta_props(ctx, list(dict.fromkeys(list(PROPS_CONNUES) + list(vus))))
    print("\n-- propriétés (libellé, datatype, formatter, regex)")
    for p, m in sorted(meta.items(), key=lambda x: int(x[0][1:])):
        if p in PROPS_CONNUES or RE_CYCLO.search(f"{m.get('en')} {m.get('fr')} {m.get('formatter')}"):
            print(f"  {p} {m['datatype']} | en={m['en']!r} fr={m['fr']!r} | {m['formatter']} | regex={m['regex']}")
    print("-- classement automatique :", json.dumps(classer_props(meta), ensure_ascii=False))


# --------------------------------------------------------------------------- couverture
def echantillon(A: str, taille: int) -> Tuple[Dict[str, List[str]], Dict[str, Any], Dict[str, Any]]:
    rnd = random.Random(20261119)
    cache = charger(f"{A}/entites/wikidata/coureurs.json", {})
    hist = charger(f"{A}/entites/historique/coureurs.json", {})
    groupes: Dict[str, List[str]] = {"UCI-avant-2009": [], "UCI-apres-2009": [], "hist-<1950": [], "hist-1950+": []}
    for rid, v in cache.items():
        if not v.get("qid"):
            continue
        debuts = [int(e["debut"][:4]) for e in v.get("equipes") or [] if str(e.get("debut") or "")[:4].isdigit()]
        an = int(v["naissance"][:4]) if v.get("naissance") else None
        pre = (min(debuts) < 2009) if debuts else (an is not None and an <= 1980)
        groupes["UCI-avant-2009" if pre else "UCI-apres-2009"].append(v["qid"])
    for q, v in hist.items():
        an = int(str(v.get("naissance") or "0")[:4] or 0)
        groupes["hist-<1950" if 0 < an < 1950 else "hist-1950+"].append(q)
    vus: set = set()
    for g in groupes:
        l = [q for q in dict.fromkeys(groupes[g]) if q not in vus]
        rnd.shuffle(l)
        groupes[g] = l[:taille]
        vus.update(groupes[g])
    return groupes, cache, hist


def pct(n: int, d: int) -> str:
    return f"{n}/{d} = {100 * n / d:.0f} %" if d else f"{n}/0"


def phase_couverture(ctx: Ctx, A: str, taille: int) -> None:
    print(f"\n######## couverture ({t()})")
    groupes, cache, hist = echantillon(A, taille)
    print("groupes :", {g: len(v) for g, v in groupes.items()}, "| cache avec qid :", sum(1 for v in cache.values() if v.get("qid")), "| historique :", len(hist))
    tous = [q for v in groupes.values() for q in v]
    ents = wikidata.lire_entites(ctx.api, tous, "claims")
    print(f"coureurs lus : {len(ents)}/{len(tous)} ({t()}, {ctx.api.requetes} requêtes)")
    # séries et éditions
    series = sorted({v["qid"] for v in charger(f"{RACINE}/series_historiques.json", {}).values()})
    eds_pre: List[str] = []
    eds_post: List[str] = []
    base = f"{A}/entites/historique/editions"
    for f in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        for lst in charger(f"{base}/{f}", {}).values():
            for e in lst:
                if e.get("qid"):
                    (eds_pre if int(e.get("annee") or 0) < 2009 else eds_post).append(e["qid"])
    rnd = random.Random(7)
    rnd.shuffle(eds_pre)
    rnd.shuffle(eds_post)
    eds = eds_pre[:min(400, taille)] + eds_post[:200]
    ents_s = wikidata.lire_entites(ctx.api, series, "claims")
    ents_e = wikidata.lire_entites(ctx.api, eds, "claims")
    print(f"séries lues {len(ents_s)}/{len(series)} ; éditions lues {len(ents_e)}/{len(eds)} (échantillon : {min(400, taille)} avant 2009 sur {len(eds_pre)}, 200 après sur {len(eds_post)}) ({t()})")
    # propriétés présentes
    cnt: Dict[str, Counter] = defaultdict(Counter)
    tailles: Dict[str, int] = {}
    for g, qs in groupes.items():
        tailles[g] = sum(1 for q in qs if ents.get(q))
        for q in qs:
            for p in ext_ids(ents.get(q)):
                cnt[p][g] += 1
    tailles["series"] = len(ents_s)
    for q, e in ents_s.items():
        for p in ext_ids(e):
            cnt[p]["series"] += 1
    tailles["editions<2009"] = sum(1 for q in eds_pre[:min(400, taille)] if ents_e.get(q))
    tailles["editions>=2009"] = sum(1 for q in eds_post[:200] if ents_e.get(q))
    for q in eds_pre[:min(400, taille)]:
        for p in ext_ids(ents_e.get(q)):
            cnt[p]["editions<2009"] += 1
    for q in eds_post[:200]:
        for p in ext_ids(ents_e.get(q)):
            cnt[p]["editions>=2009"] += 1
    a_meta = [p for p in cnt if sum(cnt[p].values()) >= 2]
    meta = meta_props(ctx, list(dict.fromkeys(a_meta + list(PROPS_CONNUES))))
    cl = classer_props(meta)
    print("-- classement automatique par formatter :", json.dumps(cl, ensure_ascii=False))
    print("-- propriétés cyclistes / connues (nombre d'entités portant la propriété, par groupe)  [tailles :", tailles, "]")
    for p in sorted(meta, key=lambda p: -sum(cnt[p].values())):
        m = meta[p]
        domaine = any(d in (m.get("formatter") or "").lower() for d in DOMAINES.values())
        if p in PROPS_CONNUES or domaine or RE_CYCLO.search(f"{m.get('en')} {m.get('fr')}"):
            ligne = ", ".join(f"{g}={pct(cnt[p][g], tailles[g])}" for g in tailles if cnt[p][g] or g in ("UCI-avant-2009", "hist-<1950"))
            print(f"  {p} [{m['en']} / {m['fr']}] fmt={m['formatter']}\n      {ligne}")
    print("-- confirmation des propriétés demandées :")
    for p, nom in PROPS_CONNUES.items():
        m = meta.get(p)
        print(f"  {p} ({nom}) -> {'ABSENTE de l échantillon / introuvable' if not m else json.dumps(m, ensure_ascii=False)}")
    # exemples
    print("-- exemples (4 coureurs « hist-<1950 » et 4 « UCI-avant-2009 »)")
    for g in ("hist-<1950", "UCI-avant-2009"):
        for q in groupes[g][:4]:
            print(f"  {g} {q} : {json.dumps({p: v for p, v in ext_ids(ents.get(q)).items() if p in meta and (p in PROPS_CONNUES or any(d in (meta[p].get('formatter') or '').lower() for d in DOMAINES.values()))}, ensure_ascii=False)}")
    # couverture par décennie de naissance (au moins une source « cyclisme »)
    props_cq = set(cl.get("cq", {}).get("personne", [])) - {"P2709"}
    props_mu = set(cl.get("museo", {}).get("personne", []))
    props_ts = set(cl.get("thesports", {}).get("personne", []))
    props_md = set(cl.get("mdc", {}).get("personne", []))
    dec: Dict[str, Counter] = defaultdict(Counter)
    for g, qs in groupes.items():
        for q in qs:
            e = ents.get(q)
            if not e:
                continue
            naiss = wikidata.parse_temps(wikidata.valeur(next(iter(wikidata.revendications(e, "P569")), {})))
            dd = f"{naiss[0][:3]}0s" if naiss else "?"
            dec[dd]["n"] += 1
            ids = ext_ids(e)
            for nom, ps in (("cq", props_cq), ("museo", props_mu), ("thesports", props_ts), ("mdc", props_md)):
                if any(p in ids for p in ps):
                    dec[dd][nom] += 1
    print("-- couverture par décennie de naissance (échantillon cumulé)")
    for dd in sorted(dec):
        c = dec[dd]
        print(f"  {dd}: n={c['n']} cq={c['cq']} museo={c['museo']} thesports={c['thesports']} mdc={c['mdc']}")
    # séries / éditions : exemples
    print("-- séries : identifiants par série (props de classement « autre » / « personne » pour tout domaine)")
    exte = {q: ext_ids(e) for q, e in ents_s.items()}
    am = charger(f"{RACINE}/alias_museo.json", {})
    am = {k: v for k, v in am.items() if not k.startswith("_")} if isinstance(am, dict) else {}
    cle_par_qid: Dict[str, List[str]] = defaultdict(list)
    for cle, v in charger(f"{RACINE}/series_historiques.json", {}).items():
        cle_par_qid[v["qid"]].append(cle)
    for q in series[:60]:
        ids = {p: v for p, v in exte.get(q, {}).items() if p in meta and (p in PROPS_CONNUES or any(d in (meta[p].get("formatter") or "").lower() for d in DOMAINES.values()))}
        print(f"  {q} {cle_par_qid[q][:1]} : {json.dumps(ids, ensure_ascii=False)}")
    # croisement avec nos fichiers
    for src in ("cq", "museo", "thesports"):
        ps = [p for p in cl.get(src, {}).get("personne", []) if p != "P2709"]   # P2709 = CQ Ranking FEMMES : autre espace d'ids
        if not ps:
            print(f"-- croisement {src} : propriété « coureur » non trouvée")
            continue
        idx = INDEX[src](A)
        print(f"-- croisement {src} (propriétés {ps}) : {len(idx)} ids dans nos fichiers")
        trouves = presents = 0
        disc: List[str] = []
        accord = 0
        for g, qs in groupes.items():
            for q in qs:
                e = ents.get(q)
                vals = [v for p in ps for v in ext_ids(e).get(p, [])]
                if not vals:
                    continue
                trouves += 1
                hits = [v for v in vals if v in idx]
                if hits:
                    presents += 1
                    v = hits[0]
                    notre = idx[v]
                    noms = wikidata.noms_entite(ents[q]) if ents.get(q) and ents[q].get("labels") else []
                    nai = wikidata.naissance_jour(ents[q])
                    if notre.get("naissance") and nai and notre["naissance"] != nai:
                        disc.append(f"{src} {v} : {notre['nom']} né {notre['naissance']} / {q} né {nai}")
                    else:
                        accord += 1
        print(f"   échantillon : {trouves} coureurs portent l'id, dont {presents} dans nos fichiers ; discordances de naissance : {len(disc)} ; sans contradiction : {accord}")
        for l in disc[:15]:
            print("   DISCORDANCE", l)
    print(f"fin couverture {t()} ({ctx.api.requetes} requêtes)")


# --------------------------------------------------------------------------- sens inverse
def variantes_or(prop: str, ids: List[str]) -> Dict[str, str]:
    return {"pipe": "haswbstatement:" + "|".join(f"{prop}={i}" for i in ids),
            "or": " OR ".join(f"haswbstatement:{prop}={i}" for i in ids),
            "or_quote": " OR ".join(f'haswbstatement:"{prop}={i}"' for i in ids)}


def phase_sonde_or(ctx: Ctx, prop: str, ids_test: List[str]) -> Optional[str]:
    print(f"\n-- sonde OU (prop {prop}, ids {ids_test}) ({t()})")
    indiv: Dict[str, List[str]] = {}
    for i in ids_test:
        indiv[i] = wikidata.recherche(ctx.api, f"haswbstatement:{prop}={i}", 5) or []
    attendu = sorted({q for v in indiv.values() for q in v})
    print(f"   individuel : {indiv}")
    retenu = None
    for nom, req in variantes_or(prop, ids_test).items():
        rep = wikidata.recherche(ctx.api, req, 50)
        ok = sorted(rep or []) == attendu
        print(f"   variante {nom} : {len(rep or [])} résultats, identique à l'union individuelle : {ok}  [{req[:90]}]")
        if ok and retenu is None and len(attendu) >= 2:
            retenu = nom
    print(f"   -> variante retenue : {retenu}")
    return retenu


def phase_inverse(ctx: Ctx, A: str, src: str, prop: str, taille: int, budget_s: float, cibles: Optional[List[str]] = None) -> None:
    print(f"\n######## inverse_{src} (prop {prop}) ({t()})")
    idx = INDEX[src](A)
    cache = charger(f"{A}/entites/wikidata/coureurs.json", {})
    hist = charger(f"{A}/entites/historique/coureurs.json", {})
    connus = {v["qid"] for v in cache.values() if v.get("qid")} | set(hist)
    par_cle: Dict[Tuple[str, frozenset], Tuple[str, Optional[str]]] = {}
    for rid, v in cache.items():
        m = re.fullmatch(r"(.+)-(\d{8})", rid)
        if m:
            par_cle[(m.group(2), frozenset(m.group(1).split("-")))] = (rid, v.get("qid"))
    ids = sorted(idx)
    print(f"nos ids : {len(ids)} ; avec naissance : {sum(1 for v in idx.values() if v['naissance'])} ; QID déjà connus de l'encyclopédie : {len(connus)}")
    rnd = random.Random(42)
    rnd.shuffle(ids)
    ech = list(dict.fromkeys([i for i in (cibles or []) if i in idx] + ids[:taille]))
    print("cibles :", [(i, idx[i]["nom"], idx[i]["naissance"]) for i in (cibles or []) if i in idx])
    variante = phase_sonde_or(ctx, prop, [i for i in ech[:40]][:12]) if len(ech) >= 12 else None
    if not variante:
        # repli : lot de 1 (une requête par id) sur un petit échantillon
        ech = ech[:min(taille, 250)]
    lot = 10 if variante else 1
    trouves: Dict[str, List[str]] = {}   # id nôtre -> qids candidats (après lecture des claims)
    qids_par_lot: List[str] = []
    for i in range(0, len(ech), lot):
        if time.time() > budget_s:
            print(f"[BUDGET] arrêt de la recherche après {i} ids")
            ech = ech[:i]
            break
        grp = ech[i:i + lot]
        req = variantes_or(prop, grp)[variante] if variante else f"haswbstatement:{prop}={grp[0]}"
        qs = wikidata.recherche(ctx.api, req, 50) or []
        qids_par_lot += qs
        if len(qs) >= 50:
            print(f"[WARN] lot saturé (50 résultats) : {grp}")
        if (i // lot) % 40 == 0:
            print(f"  ... {i}/{len(ech)} ids cherchés, {len(set(qids_par_lot))} QID ({t()}, {ctx.api.requetes} requêtes)")
    qids = list(dict.fromkeys(qids_par_lot))
    ents = wikidata.lire_entites(ctx.api, qids, "claims|labels|aliases", "fr|en|it|es|nl|de")
    par_id: Dict[str, List[str]] = defaultdict(list)
    ids_par_qid: Dict[str, List[str]] = {}
    for q, e in ents.items():
        vals = []
        for p in [prop]:
            vals += ext_ids(e).get(p, [])
        ids_par_qid[q] = vals
        for v in vals:
            par_id[v].append(q)
    ech_set = set(ech)
    n = len(ech)
    f1 = [i for i in ech if len(par_id.get(i, [])) == 1]
    fm = [i for i in ech if len(par_id.get(i, [])) > 1]
    print(f"\nids cherchés : {n} ; trouvés (1 QID) : {pct(len(f1), n)} ; plusieurs QID : {len(fm)} ; introuvables : {n - len(f1) - len(fm)}")
    cat: Counter = Counter()
    ex: Dict[str, List[str]] = defaultdict(list)
    for i in f1:
        q = par_id[i][0]
        e = ents[q]
        notre = idx[i]
        nai = wikidata.naissance_jour(e)
        nom_ok = wikidata.nom_concorde(notre["nom"], wikidata.noms_entite(e))
        humain = any(wikidata.qid_de(c) == "Q5" for c in wikidata.revendications(e, "P31"))
        cle = (notre["naissance"].replace("-", ""), frozenset(wikidata.jetons(notre["nom"]))) if notre.get("naissance") else None
        ent_cache = par_cle.get(cle) if cle else None
        if ent_cache and ent_cache[1] == q:
            deja = "connu_cache"
        elif ent_cache and ent_cache[1]:
            deja = "cache_discordant"
        elif ent_cache:
            deja = "cache_null_GAIN"            # fiche UCI connue, nom + date n'avait rien rapproché
        elif q in connus:
            deja = "qid_connu_autre_cle"
        else:
            deja = ""
        if not humain:
            c = "non_humain"
        elif notre.get("naissance") and nai:
            c = "date_egale_nom_ok" if (notre["naissance"] == nai and nom_ok) else ("date_egale_nom_KO" if notre["naissance"] == nai else ("date_differente_nom_ok" if nom_ok else "date_differente_nom_KO"))
        elif nai or notre.get("naissance"):
            c = "une_seule_date_nom_ok" if nom_ok else "une_seule_date_nom_KO"
        else:
            c = "aucune_date_nom_ok" if nom_ok else "aucune_date_nom_KO"
        cat[c] += 1
        cat["rapprochement:" + (deja or "nouveau")] += 1
        if (i in (cibles or [])) or c.endswith("nom_KO") or c.startswith("date_diff") or deja in ("cache_discordant", "cache_null_GAIN", "qid_connu_autre_cle") or c == "non_humain":
            if len(ex[c + "/" + deja]) < 14 or i in (cibles or []):
                c = c + "/" + deja
                lab = ((e.get("labels") or {}).get("en") or (e.get("labels") or {}).get("fr") or {}).get("value")
                ex[c].append(f"{src} {i} : {notre['nom']} ({notre.get('naissance')}) <-> {q} {lab!r} ({nai}) cache={deja or 'non'}")
    print("verdicts (sur les ids trouvés avec un seul QID) :", dict(cat))
    nouveaux_ok = sum(v for k, v in cat.items() if k == "rapprochement:nouveau")
    print(f"=> rattachements NOUVEAUX (QID absent du cache coureurs et de l'historique, ou clé nom+date non rapprochée) : {nouveaux_ok}")
    for c, l in ex.items():
        print(f"-- exemples {c}")
        for x in l:
            print("   ", x)
    multi_qid = [(q, v) for q, v in ids_par_qid.items() if len(set(v)) > 1]
    print(f"QID portant plusieurs ids {src} : {len(multi_qid)} (ex. {multi_qid[:5]})")
    for i in fm[:8]:
        print(f"   id {i} -> plusieurs QID {par_id[i]}")
    print(f"fin inverse_{src} {t()} ({ctx.api.requetes} requêtes)")


def main() -> None:
    c = cfg()
    phases = c.get("phases", "proprietes couverture").split()
    taille = int(c.get("taille", "400"))
    budget = float(c.get("budget_s", "780"))
    props = dict(kv.split("=") for kv in c.get("props", "").split() if "=" in kv)
    ctx = Ctx()
    A = racine_archives()
    print(f"archives : {A} ; phases {phases} ; taille {taille} ; props {props}")
    try:
        if "proprietes" in phases:
            phase_proprietes(ctx)
        if "couverture" in phases:
            phase_couverture(ctx, A, taille)
        for src in ("cq", "museo", "thesports"):
            if f"inverse_{src}" in phases and props.get(src):
                phase_inverse(ctx, A, src, props[src], int(c.get("taille_inverse", "1200")), T0 + budget, c.get(f"cibles_{src}", "").split())
    except wikidata.HoteAbandonne as e:
        print(f"[ABANDON] hôte refusé : {e}")
    print(f"\nTotal : {ctx.api.requetes} requêtes en {time.time() - T0:.0f}s")


if __name__ == "__main__":
    main()
