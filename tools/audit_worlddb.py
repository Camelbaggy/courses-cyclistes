#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrôle croisé de nos données avec WorldDB (base communautaire du jeu Pro Cycling Manager) : aucun réseau, lecture seule.

USAGE LIMITÉ. WorldDB est une base saisie à la main par des bénévoles, dont les droits ne sont pas établis. Cet outil ne sert
QU'À (1) repérer des écarts à revérifier auprès de sources officielles (UCI, Wikipédia, Wikidata) et (2) proposer des
équivalences d'équipes à valider À LA MAIN. Il ne publie, ne copie et ne reprend jamais de contenu de WorldDB :
  - aucune donnée WorldDB ne doit entrer dans un dépôt (le dossier `--sortie` est refusé s'il est dans un dépôt git) ;
  - rien n'est écrit dans `alias_equipes.json` ni dans `entites/` ; une proposition n'est jamais appliquée automatiquement ;
  - champs de jeu, taille / poids, dates de courses, nombre d'étapes, contrats et e-mails d'organisateurs ne sont pas lus.
La base elle-même reste hors des dépôts publics.

    python -I tools/audit_worlddb.py <dossier_worlddb_csv> <dossier_archives> --sortie <dossier>
    python tools/audit_worlddb.py --test

`dossier_worlddb_csv` : dossier des CSV (DYN_cyclist.csv…) ; à défaut, un sous-dossier « 2025 Season Start » (ou le premier
contenant DYN_cyclist.csv). `dossier_archives` : `data/archives` du dépôt d'archives (lit `entites/coureurs`, `courses`,
`equipes`, `wikidata`). Fichiers écrits dans `--sortie` :
  ecarts.json / ecarts.md        dates de naissance différentes, nationalités en conflit, vainqueurs en désaccord, doublons de
                                 `rider_id` probables (contiennent des valeurs WorldDB : usage interne, jamais publié)
  a_verifier.json                liste MINIMALE pour un essai réseau (NOS valeurs seulement : aucune valeur WorldDB)
  equipes_propositions.md        équipes-saisons 2019-2024 sans QID Wikidata, avec QID proposé par la lignée WorldDB (à valider)
Python 3 stdlib uniquement."""

import argparse
import csv
import difflib
import glob
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

csv.field_size_limit(10 ** 9)
DOSSIER_PAR_DEFAUT = "2025 Season Start"
ANNEES_EQUIPES = range(2019, 2025)      # WorldDB couvre les noms d'équipes jusqu'en 2024 (aucune ligne 2025-2026)

# Codes pays du jeu différents des codes UCI / CIO de nos fiches (vérifiés sur les données : table d'alias de 34 codes).
ALIAS_PAYS = {"CHI": "CHN", "CHL": "CHI", "SWI": "SUI", "IDN": "INA", "SAR": "RSA", "DZA": "ALG", "SWD": "SWE", "PHL": "PHI",
              "ROM": "ROU", "IRN": "IRI", "GTM": "GUA", "MUS": "MRI", "SER": "SRB", "TWN": "TPE", "MNG": "MGL", "BFA": "BUR",
              "SAU": "KSA", "VNM": "VIE", "AGO": "ANG", "NGA": "NGR", "SGP": "SIN", "BLZ": "BIZ", "BHR": "BRN", "PRI": "PUR",
              "PRY": "PAR", "CUW": "CUR", "HND": "HON", "GRD": "GRN", "PSE": "PLE", "KHM": "CAM", "MCO": "MON", "MOL": "MDA",
              "LSO": "LES", "BHS": "BAH"}


# --------------------------------------------------------------------------- utilitaires

def norm(s: Optional[str]) -> str:
    """Minuscules ASCII sans ponctuation (équivalent de netutil.normalize ; l'outil reste autonome)."""
    t = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t.lower()).split())


def cle(s: Optional[str]) -> str:
    """Nom normalisé, mots triés (ordre prénom / nom indifférent)."""
    return " ".join(sorted(norm(s).split()))


def charger_json(chemin: str, defaut: Any = None) -> Any:
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def lire_csv(dossier: str, table: str) -> List[Dict[str, str]]:
    chemin = os.path.join(dossier, table + ".csv")
    with open(chemin, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def trouver_dossier_csv(d: str) -> str:
    if os.path.exists(os.path.join(d, "DYN_cyclist.csv")):
        return d
    sous = os.path.join(d, DOSSIER_PAR_DEFAUT)
    if os.path.exists(os.path.join(sous, "DYN_cyclist.csv")):
        return sous
    for p in sorted(glob.glob(os.path.join(d, "*", "DYN_cyclist.csv"))):
        return os.path.dirname(p)
    raise SystemExit(f"[ERREUR] aucun DYN_cyclist.csv dans {d}")


def dans_un_depot_git(chemin: str) -> bool:
    p = os.path.abspath(chemin)
    while True:
        if os.path.exists(os.path.join(p, ".git")):
            return True
        parent = os.path.dirname(p)
        if parent == p:
            return False
        p = parent


def ecrire_json(chemin: str, obj: Any) -> None:
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def cell(s: Any) -> str:
    return str(s if s is not None else "").replace("|", "/").replace("\n", " ")


# --------------------------------------------------------------------------- nos données

def charger_coureurs(arch: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for p in sorted(glob.glob(os.path.join(arch, "entites", "coureurs", "*.json"))):
        out.update(charger_json(p, {}) or {})
    return out


def charger_courses(arch: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for p in sorted(glob.glob(os.path.join(arch, "entites", "courses", "*.json"))):
        out.update(charger_json(p, {}) or {})
    return out


def chiffres_differents(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))


def type_ecart_date(w: str, n: str) -> str:
    """Nature de l'écart entre deux dates AAAAMMJJ (w : WorldDB, n : nôtre)."""
    if w[:4] == n[:4] and w[4:6] == n[6:8] and w[6:8] == n[4:6]:
        return "jour/mois inversés"
    if w[:4] == n[:4]:
        return "même année (jour ou mois)"
    if chiffres_differents(w, n) == 1:
        return "un chiffre"
    return "autre (homonymes probables)"


# --------------------------------------------------------------------------- coureurs

def audit_coureurs(wdb: str, nos: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    cy = lire_csv(wdb, "DYN_cyclist")
    regions = {r["IDregion"]: r for r in lire_csv(wdb, "STA_region")}
    pays = {r["IDcountry"]: r for r in lire_csv(wdb, "STA_country")}
    par_nom: Dict[str, List[str]] = defaultdict(list)
    par_date: Dict[str, List[str]] = defaultdict(list)
    for rid, r in nos.items():
        bd = (r.get("birth_date") or "").replace("-", "")
        par_nom[cle(r.get("name"))].append(rid)
        if bd:
            par_date[bd].append(rid)

    def bd_de(rid: str) -> str:
        return (nos[rid].get("birth_date") or "").replace("-", "")

    dates: List[Dict[str, Any]] = []
    nats: List[Dict[str, Any]] = []
    ambigus: List[Dict[str, Any]] = []
    rapproches = strict = 0
    sans_date_retrouves = 0
    vus_rid = set()
    for r in cy:
        nom = (r["gene_sz_firstname"] + " " + r["gene_sz_lastname"]).strip()
        wd = r["gene_i_birthdate"]
        cands = par_nom.get(cle(nom), [])
        datees = [c for c in cands if bd_de(c)]
        if cands and not datees:
            sans_date_retrouves += 1
        elif datees and not any(bd_de(c) == wd for c in datees):
            proche = min(datees, key=lambda c: chiffres_differents(wd, bd_de(c)))
            dates.append({"rider_id": proche, "nom": nos[proche]["name"], "naissance_nous": bd_de(proche),
                          "naissance_worlddb": wd, "type": type_ecart_date(wd, bd_de(proche)),
                          "homonymes_chez_nous": len(datees) > 1, "nationalite_nous": nos[proche].get("nationality")})
        # rapprochement date exacte + noms égaux ou inclus (nos noms UCI portent seconds prénoms et particules)
        tw = set(norm(nom).split())
        c2 = []
        for rid in par_date.get(wd, []):
            to = set(norm(nos[rid].get("name")).split())
            if cle(nos[rid].get("name")) == cle(nom) or (tw and to and (tw <= to or to <= tw)):
                c2.append(rid)
        if len(c2) == 1:
            rapproches += 1
            rid = c2[0]
            vus_rid.add(rid)
            strict += cle(nos[rid].get("name")) == cle(nom)
            code = (pays.get((regions.get(r["fkIDregion"]) or {}).get("fkIDcountry", ""), {}) or {}).get("CONSTANT")
            if code:
                code = ALIAS_PAYS.get(code, code)
                if code != nos[rid].get("nationality"):
                    nats.append({"rider_id": rid, "nom": nos[rid]["name"], "naissance": bd_de(rid),
                                 "nationalite_nous": nos[rid].get("nationality"), "nationalite_worlddb": code})
        elif len(c2) > 1:
            ambigus.append({"nom_worlddb": nom, "naissance": wd, "nos_rider_id": sorted(c2)})
    # doublons probables chez nous : même date, noms égaux ou inclus (révélés par un coureur WorldDB à deux candidats)
    return {"total_worlddb": len(cy), "rapproches": rapproches, "rapproches_nom_exact": strict, "nos_coureurs": len(nos),
            "nos_retrouves": len(vus_rid), "sans_date_chez_nous_retrouves_par_nom": sans_date_retrouves,
            "ecarts_naissance": sorted(dates, key=lambda x: (x["type"], x["nom"])),
            "ecarts_nationalite": sorted(nats, key=lambda x: x["nom"]),
            "doublons_probables": ambigus}


# --------------------------------------------------------------------------- vainqueurs

def variante_de_nom(a: str, b: str) -> bool:
    """Deux noms de vainqueur qui ne sont probablement qu'une variante d'écriture (Izaguirre / Izagirre, Wouter / Wout, Joe /
    Joseph) : ressemblance globale forte des chaînes triées, ou chaque mot du nom le plus court a un mot proche dans l'autre."""
    ta, tb = norm(a).split(), norm(b).split()
    if not ta or not tb:
        return False
    if difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio() >= 0.8:
        return True
    court, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)

    def proche(x: str) -> bool:
        return any(difflib.SequenceMatcher(None, x, y).ratio() >= 0.8 or (len(x) >= 3 and len(y) >= 3 and (x.startswith(y) or y.startswith(x)))
                   for y in long_)
    return all(proche(x) for x in court)


def audit_vainqueurs(wdb: str, courses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    courses_w = {r["IDrace"]: r for r in lire_csv(wdb, "STA_race")}
    ctry = {r["IDcountry"]: r["CONSTANT"] for r in lire_csv(wdb, "STA_country")}
    types = {r["IDpalmares_type"]: r["CONSTANT"] for r in lire_csv(wdb, "STA_palmares_type")}
    noms_p = {r["IDpalmares_cyclist"]: r for r in lire_csv(wdb, "DYN_palmares_cyclist")}
    pal = lire_csv(wdb, "DYN_palmares")
    nom_cle: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for k, v in courses.items():
        for n in (v.get("noms") or {}):
            nom_cle[norm(n)].append((k, v.get("pays")))
    rapproche: Dict[str, str] = {}
    for i, r in courses_w.items():
        cc = ctry.get(r["fkIDcountry"])
        cc = ALIAS_PAYS.get(cc, cc)
        ks = sorted({k for k, p in nom_cle.get(norm(r["gene_sz_race_name"]), []) if p == cc})
        if len(ks) == 1:
            rapproche[i] = ks[0]
    gagnants: Dict[str, Dict[int, List[str]]] = defaultdict(dict)
    for p in pal:
        if types.get(p["fkIDpalmares_type"]) == "GENERAL_TEMPS" and p["value_i_rank"] == "1" and p["fkIDrace"] in rapproche:
            c = noms_p.get(p["fkIDpalmares_cyclist"])
            if c:
                gagnants[p["fkIDrace"]].setdefault(int(p["value_i_year"]), []).append(c["gene_sz_full_name"])
    compares = concordants = sans_vainqueur = 0
    variantes: List[Dict[str, Any]] = []
    desaccords: List[Dict[str, Any]] = []
    for i, k in rapproche.items():
        v = courses[k]
        noms = v.get("noms") or {}
        nom_course = max(noms, key=lambda n: max(noms[n] or [0])) if noms else k
        for ed in v.get("editions") or []:
            y = ed.get("season")
            if not ed.get("podium") or not isinstance(y, int) or y > 2024:
                continue
            w = gagnants.get(i, {}).get(y)
            if not w:
                sans_vainqueur += 1
                continue
            compares += 1
            nous = ed["podium"][0]["name"]
            tn = set(norm(nous).split())
            if any(set(norm(x).split()) <= tn or tn <= set(norm(x).split()) for x in w):
                concordants += 1
                continue
            ligne = {"race_id": ed.get("race_id"), "saison": y, "course": nom_course, "cle_epreuve": k,
                     "vainqueur_nous": nous, "vainqueur_worlddb": w}
            (variantes if any(variante_de_nom(nous, x) for x in w) else desaccords).append(ligne)

    def tri(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(lst, key=lambda x: (x["course"], x["saison"]))
    return {"courses_worlddb": len(courses_w), "courses_rapprochees": len(rapproche), "editions_comparees": compares,
            "concordantes": concordants, "editions_sans_vainqueur_worlddb": sans_vainqueur,
            "desaccords_variantes_de_nom": tri(variantes), "desaccords_reels": tri(desaccords)}


# --------------------------------------------------------------------------- équipes

def classe_preuve(e: Dict[str, Any]) -> Optional[str]:
    """Force de l'appui d'une équipe-saison déjà rattachée dans notre cache Wikidata. Le cache écrit avant `REGLE_EQUIPES` 2 garde un
    texte libre (`P1998 CODE [période] ; P1448 « … »` ou `; saison « … »`) : c'est la preuve code+nom."""
    if not e.get("qid"):
        return None
    p = str(e.get("preuve") or "")
    if p == "alias":
        return "alias"
    if p == "code+periode" or "nom non concordant" in p:
        return "code+periode"
    if p == "code+nom" or "P1448" in p or "saison «" in p:
        return "code+nom"
    return None


def statut_cache(e: Optional[Dict[str, Any]]) -> str:
    if e is None:
        return "non interrogée"
    if e.get("qid"):
        return "rattachée"
    return str(e.get("raison") or "aucune")


def periode_nom(lignee: Dict[str, Any], annee: int) -> Optional[str]:
    for n in lignee.get("noms") or []:
        d, f = str(n.get("debut") or "")[:4], str(n.get("fin") or "")[:4]
        if d.isdigit() and int(d) <= annee and (not f.isdigit() or annee <= int(f)):
            return n.get("nom")
    return None


def proposer_equipes(nos: Dict[str, Tuple[int, str, Optional[str]]], cache: Dict[str, Dict[str, Any]], lignees: Dict[str, Dict[str, Any]],
                     histo: Dict[Tuple[int, str], set], noms_w: Dict[str, str], annees: Any = ANNEES_EQUIPES) -> Dict[str, Any]:
    """Pur (testable). nos : {id équipe-saison: (année, libellé, code UCI|None)} ; histo : {(année, libellé normalisé): {fkIDteam}} ;
    noms_w : {« fkIDteam|année »: libellé WorldDB}."""
    rattache: Dict[str, str] = {}
    for tid, (an, lib, code) in nos.items():
        if an in annees:
            c = histo.get((an, norm(lib)), set())
            if len(c) == 1:
                rattache[tid] = next(iter(c))
    par_ligne: Dict[str, List[str]] = defaultdict(list)
    for tid, f in rattache.items():
        par_ligne[f].append(tid)
    props, conflits, sans_appui = [], [], []
    for tid, (an, lib, code) in sorted(nos.items(), key=lambda kv: (kv[1][1].lower(), kv[1][0])):
        if an not in annees or statut_cache(cache.get(tid)) == "rattachée":
            continue
        f = rattache.get(tid)
        if f is None:
            continue                      # WorldDB ne connaît pas (de façon unique) cette équipe-saison
        appuis = [(nos[x][0], cache[x]["qid"], classe_preuve(cache[x])) for x in par_ligne[f]
                  if x != tid and classe_preuve(cache.get(x) or {}) in ("code+nom", "code+periode", "alias")]
        qids = sorted({q for _, q, _ in appuis})
        ligne = {"id": tid, "libelle": lib, "annee": an, "statut_cache": statut_cache(cache.get(tid)), "code_uci": code,
                 "libelle_worlddb": noms_w.get(f"{f}|{an}", ""), "fk_team": f}
        if len(qids) > 1:
            ligne["appuis"] = sorted(appuis)
            conflits.append(ligne)
        elif qids:
            q = qids[0]
            proche = min((a for a, qq, _ in appuis if qq == q), key=lambda a: (abs(a - an), a))
            pr = next(p for a, qq, p in appuis if qq == q and a == proche)
            ligne.update({"qid": q, "libelle_wikidata": (lignees.get(q) or {}).get("libelle"), "appui_annee": proche, "appui_preuve": pr,
                          "appuis": sum(1 for _, qq, _ in appuis if qq == q),
                          "nom_wikidata_cette_annee": periode_nom(lignees.get(q) or {}, an)})
            props.append(ligne)
        else:
            sans_appui.append(ligne)
    dup = Counter((p["annee"], p["qid"]) for p in props)
    for p in props:
        p["doublon_meme_annee"] = dup[(p["annee"], p["qid"])] > 1
    return {"propositions": props, "conflits": conflits, "sans_appui": sans_appui, "rattachees_worlddb": len(rattache)}


def audit_equipes(wdb: str, arch: str) -> Dict[str, Any]:
    ent = os.path.join(arch, "entites")
    cache = charger_json(os.path.join(ent, "wikidata", "equipes.json"), {}) or {}
    lignees = charger_json(os.path.join(ent, "wikidata", "lignees.json"), {}) or {}
    nos: Dict[str, Tuple[int, str, Optional[str]]] = {}
    for an in ANNEES_EQUIPES:
        for tid, e in (charger_json(os.path.join(ent, "equipes", f"{an}.json"), {}) or {}).items():
            if not e.get("nationale"):
                nos[tid] = (an, e.get("name") or "", e.get("code_uci"))
    histo: Dict[Tuple[int, str], set] = defaultdict(set)
    noms_w: Dict[str, str] = {}
    for h in lire_csv(wdb, "DYN_team_history"):
        if h["value_i_year"].isdigit():
            histo[(int(h["value_i_year"]), norm(h["value_sz_name"]))].add(h["fkIDteam"])
            noms_w.setdefault(f"{h['fkIDteam']}|{h['value_i_year']}", h["value_sz_name"])
    res = proposer_equipes(nos, cache, lignees, histo, noms_w)
    # lignées WorldDB couvrant deux QID (conflit global, y compris sans équipe cible) et un QID sur deux lignées. 2025 : WorldDB n'a pas
    # d'historique, on le rapproche du nom courant de DYN_team (confiance plus faible, utilisé seulement pour signaler un conflit).
    histo_c = defaultdict(set, {k: set(v) for k, v in histo.items()})
    for t in lire_csv(wdb, "DYN_team"):
        histo_c[(2025, norm(t["gene_sz_name"]))].add(t["IDteam"])
    nos_c = dict(nos)
    for tid, e in (charger_json(os.path.join(ent, "equipes", "2025.json"), {}) or {}).items():
        if not e.get("nationale"):
            nos_c[tid] = (2025, e.get("name") or "", e.get("code_uci"))
    qid_par_ligne: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    ligne_par_qid: Dict[str, set] = defaultdict(set)
    for tid, (an, lib, code) in nos_c.items():
        c = histo_c.get((an, norm(lib)), set())
        e = cache.get(tid) or {}
        if len(c) == 1 and e.get("qid"):
            f = next(iter(c))
            qid_par_ligne[f][e["qid"]].append(f"{lib} {an}")
            ligne_par_qid[e["qid"]].add(f)
    res["lignees_a_deux_qid"] = {f: {q: sorted(v) for q, v in d.items()} for f, d in qid_par_ligne.items() if len(d) > 1}
    res["qid_sur_deux_lignees"] = {q: sorted(v) for q, v in ligne_par_qid.items() if len(v) > 1}
    res["cache_equipes"] = Counter(statut_cache(cache.get(t)) for t in nos)
    res["nos_equipes_2019_2024"] = len(nos)
    return res


# --------------------------------------------------------------------------- sorties

def tableau(entetes: List[str], lignes: List[List[Any]]) -> List[str]:
    out = ["| " + " | ".join(entetes) + " |", "|" + "---|" * len(entetes)]
    out += ["| " + " | ".join(cell(c) for c in l) + " |" for l in lignes]
    return out


def ecarts_md(c: Dict[str, Any], v: Dict[str, Any]) -> str:
    L = ["# Écarts WorldDB / nos données (USAGE INTERNE : contient des valeurs WorldDB, ne pas publier)", "",
         "Chaque ligne est un SIGNAL à revérifier auprès d'une source officielle (UCI, Wikipédia, Wikidata) ; WorldDB n'est jamais une source.", ""]
    ed = c["ecarts_naissance"]
    L += [f"## 1. Dates de naissance différentes ({len(ed)})", "",
          f"Coureurs WorldDB {c['total_worlddb']}, rapprochés (date exacte + noms égaux ou inclus) {c['rapproches']} ; "
          f"nos coureurs retrouvés {c['nos_retrouves']} / {c['nos_coureurs']}. Types : "
          + ", ".join(f"{k} {n}" for k, n in sorted(Counter(x['type'] for x in ed).items())) + ".", ""]
    L += tableau(["rider_id", "nom", "notre date", "date WorldDB", "type", "homonymes chez nous"],
                 [[x["rider_id"], x["nom"], x["naissance_nous"], x["naissance_worlddb"], x["type"], "oui" if x["homonymes_chez_nous"] else ""] for x in ed])
    en = c["ecarts_nationalite"]
    L += ["", f"## 2. Nationalités en conflit ({len(en)}) — après table d'alias de codes ; nationalité sportive UCI ≠ naissance : écart parfois légitime", ""]
    L += tableau(["rider_id", "nom", "naissance", "notre nationalité", "WorldDB"],
                 [[x["rider_id"], x["nom"], x["naissance"], x["nationalite_nous"], x["nationalite_worlddb"]] for x in en])
    vr, vv = v["desaccords_reels"], v["desaccords_variantes_de_nom"]
    L += ["", f"## 3. Vainqueurs en désaccord ({len(vr)} à vérifier, {len(vv)} variantes de nom)", "",
          f"Épreuves rapprochées par nom + pays exact : {v['courses_rapprochees']} ; éditions comparées (2019-2024) {v['editions_comparees']}, "
          f"concordantes {v['concordantes']}, sans vainqueur WorldDB {v['editions_sans_vainqueur_worlddb']}.", "", "### À vérifier", ""]
    L += tableau(["course", "saison", "race_id", "notre vainqueur", "WorldDB"],
                 [[x["course"], x["saison"], x["race_id"], x["vainqueur_nous"], " / ".join(x["vainqueur_worlddb"])] for x in vr])
    L += ["", "### Variantes de nom (même personne probable, rien à corriger sauf si notre graphie est fautive)", ""]
    L += tableau(["course", "saison", "notre vainqueur", "WorldDB"],
                 [[x["course"], x["saison"], x["vainqueur_nous"], " / ".join(x["vainqueur_worlddb"])] for x in vv])
    dp = c["doublons_probables"]
    L += ["", f"## 4. Coureur WorldDB correspondant à plusieurs de nos rider_id ({len(dp)})", "",
          "Même date de naissance, noms égaux ou inclus : doublons probables chez nous (candidats pour `alias_coureurs.json`, à valider à la main) "
          "ou homonymes de même date (rare).", ""]
    L += tableau(["nom WorldDB", "date", "nos rider_id"], [[x["nom_worlddb"], x["naissance"], " ; ".join(x["nos_rider_id"])] for x in dp])
    return "\n".join(L) + "\n"


def propositions_md(r: Dict[str, Any]) -> str:
    P, C, S = r["propositions"], r["conflits"], r["sans_appui"]
    L = ["# Propositions d'équivalences d'équipes (WorldDB -> QID Wikidata) : À VALIDER À LA MAIN", "",
         "USAGE INTERNE : contient des libellés WorldDB. Une proposition vient de l'appartenance à une même lignée WorldDB (même `fkIDteam`) "
         "qu'une autre de nos équipes-saisons déjà rattachée par Wikidata (preuve code+nom ou code+période). Ce n'est PAS une preuve : "
         "contrôler le QID sur Wikidata (code UCI, période, nom) avant de l'ajouter à `alias_equipes.json`. Rien n'est écrit automatiquement.", "",
         f"Équipes-saisons non nationales 2019-2024 : {r['nos_equipes_2019_2024']} (cache Wikidata : "
         + ", ".join(f"{k} {n}" for k, n in sorted(r["cache_equipes"].items())) + f"). Rapprochées à WorldDB par nom exact + année : "
         f"{r['rattachees_worlddb']}. **Propositions : {len(P)} ; conflits : {len(C)} ; rattachées à WorldDB sans appui : {len(S)}.**", "",
         f"## Propositions ({len(P)})", ""]
    L += tableau(["valider", "équipe-saison (libellé, année)", "id", "statut cache", "QID proposé (lignée Wikidata)", "appui déjà prouvé",
                  "libellé WorldDB de l'année", "code UCI de la saison", "nom Wikidata de la lignée cette année"],
                 [["[ ] valider", f"{p['libelle']}, {p['annee']}", p["id"], p["statut_cache"],
                   f"{p['qid']} ({p['libelle_wikidata'] or '?'})" + (" /!\\ même QID proposé à une autre équipe la même année" if p["doublon_meme_annee"] else ""),
                   f"{p['appui_annee']} ({p['appui_preuve']}" + (f", {p['appuis']} saisons)" if p["appuis"] > 1 else ")"),
                   p["libelle_worlddb"], p["code_uci"] or "", p["nom_wikidata_cette_annee"] or "(hors périodes de noms connues)"] for p in P])
    L += ["", f"## Conflits ({len(C)}) : lignée WorldDB couvrant plusieurs QID Wikidata, aucune proposition", ""]
    L += tableau(["équipe-saison", "id", "statut cache", "libellé WorldDB", "code UCI", "appuis (année, QID, preuve)"],
                 [[f"{p['libelle']}, {p['annee']}", p["id"], p["statut_cache"], p["libelle_worlddb"], p["code_uci"] or "",
                   " ; ".join(f"{a} {q} {pr}" for a, q, pr in p["appuis"])] for p in C])
    gl = r["lignees_a_deux_qid"]
    L += ["", f"### Lignées WorldDB à plusieurs QID parmi les équipes déjà rattachées ({len(gl)})", ""]
    for f, d in gl.items():
        L.append(f"- fkIDteam {f} : " + " ; ".join(f"{q} <- {', '.join(v)}" for q, v in d.items()))
    L += ["", f"### QID Wikidata réparti sur plusieurs lignées WorldDB ({len(r['qid_sur_deux_lignees'])})", ""]
    for q, v in r["qid_sur_deux_lignees"].items():
        L.append(f"- {q} : fkIDteam {', '.join(v)}")
    L += ["", f"## Rattachées à WorldDB mais sans appui Wikidata ({len(S)}) : lignée entièrement sans QID, rien à proposer", ""]
    L += tableau(["équipe-saison", "id", "statut cache", "libellé WorldDB", "code UCI"],
                 [[f"{p['libelle']}, {p['annee']}", p["id"], p["statut_cache"], p["libelle_worlddb"], p["code_uci"] or ""] for p in S])
    return "\n".join(L) + "\n"


def _iso(b: str) -> Optional[str]:
    return f"{b[:4]}-{b[4:6]}-{b[6:]}" if len(b) == 8 else None


def a_verifier(c: Dict[str, Any], v: Dict[str, Any]) -> Dict[str, Any]:
    """Liste MINIMALE pour l'essai réseau : uniquement NOS valeurs (aucune valeur WorldDB)."""
    cor: Dict[str, Dict[str, Any]] = {}
    for motif, lst, champ in (("naissance", c["ecarts_naissance"], "naissance_nous"), ("nationalite", c["ecarts_nationalite"], "naissance")):
        for x in lst:
            e = cor.setdefault(x["rider_id"], {"rider_id": x["rider_id"], "nom": x["nom"], "naissance": _iso(x[champ]),
                                               "nationalite": x["nationalite_nous"], "controles": []})
            e["controles"].append(motif)
    vain = [{"race_id": x["race_id"], "saison": x["saison"], "course": x["course"], "vainqueur": x["vainqueur_nous"]} for x in v["desaccords_reels"]]
    return {"coureurs": sorted(cor.values(), key=lambda e: e["rider_id"]), "vainqueurs": vain}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Contrôle croisé WorldDB (écarts à revérifier, propositions d'équipes à valider) ; usage limité, jamais de publication.")
    ap.add_argument("worlddb")
    ap.add_argument("archives")
    ap.add_argument("--sortie", required=True)
    ap.add_argument("--force", action="store_true", help="écrire malgré un dossier de sortie dans un dépôt git (déconseillé)")
    a = ap.parse_args(argv)
    if dans_un_depot_git(a.sortie) and not a.force:
        raise SystemExit("[ERREUR] --sortie est dans un dépôt git : les sorties contiennent des valeurs WorldDB (jamais publiées). Choisir un dossier hors dépôt.")
    os.makedirs(a.sortie, exist_ok=True)
    wdb = trouver_dossier_csv(a.worlddb)
    arch = a.archives
    if not os.path.isdir(os.path.join(arch, "entites")):
        raise SystemExit(f"[ERREUR] {arch}/entites introuvable (attendu : data/archives du dépôt d'archives)")
    print(f"[WORLDDB] CSV : {wdb}")
    c = audit_coureurs(wdb, charger_coureurs(arch))
    v = audit_vainqueurs(wdb, charger_courses(arch))
    e = audit_equipes(wdb, arch)
    ecrire_json(os.path.join(a.sortie, "ecarts.json"), {"coureurs": c, "vainqueurs": v})
    with open(os.path.join(a.sortie, "ecarts.md"), "w", encoding="utf-8") as f:
        f.write(ecarts_md(c, v))
    ecrire_json(os.path.join(a.sortie, "a_verifier.json"), a_verifier(c, v))
    with open(os.path.join(a.sortie, "equipes_propositions.md"), "w", encoding="utf-8") as f:
        f.write(propositions_md(e))
    print(f"[WORLDDB] coureurs rapprochés {c['rapproches']}/{c['total_worlddb']} ; nos retrouvés {c['nos_retrouves']}/{c['nos_coureurs']}")
    print(f"[WORLDDB] écarts de naissance {len(c['ecarts_naissance'])} ({dict(Counter(x['type'] for x in c['ecarts_naissance']))}) ; "
          f"nationalités {len(c['ecarts_nationalite'])} ; coureurs à plusieurs rider_id {len(c['doublons_probables'])}")
    print(f"[WORLDDB] vainqueurs : {v['editions_comparees']} éditions comparées, {v['concordantes']} concordantes, "
          f"{len(v['desaccords_variantes_de_nom'])} variantes de nom, {len(v['desaccords_reels'])} désaccords à vérifier")
    print(f"[WORLDDB] équipes : {len(e['propositions'])} propositions, {len(e['conflits'])} conflits, {len(e['sans_appui'])} sans appui")
    return 0


def _test() -> None:
    assert cle("Wout POELS") == cle("poels wout")
    assert type_ecart_date("20020228", "20020828") == "même année (jour ou mois)"
    assert type_ecart_date("19960520", "20220520") == "autre (homonymes probables)"
    assert type_ecart_date("19980112", "19981201") == "jour/mois inversés"
    assert type_ecart_date("20030414", "20030904") == "même année (jour ou mois)"
    assert variante_de_nom("Ion Izaguirre", "Ion Izagirre") and variante_de_nom("Wouter Poels", "Wout Poels")
    assert variante_de_nom("Eddie Dunbar", "Edward Dunbar") and not variante_de_nom("Lorenzo Rota", "Franck Bonnamour")
    assert not variante_de_nom("Mathias Bregnhøj", "Thibaud Gruel")
    nos = {"a-2019": (2019, "Equipe A", "AAA"), "a-2020": (2020, "Equipe A bis", "AAA"), "b-2021": (2021, "Autre", None),
           "c-2019": (2019, "Equipe C", None), "c-2020": (2020, "Equipe C", None), "c-2021": (2021, "Equipe C 2", None)}
    cache = {"a-2020": {"qid": "Q1", "preuve": "P1998 AAA [2020→…] ; P1448 « Equipe A bis »"},
             "a-2019": {"qid": None, "raison": "aucune"},
             "c-2019": {"qid": "Q2", "preuve": "code+periode"}, "c-2021": {"qid": "Q3", "preuve": "code+nom"}}
    histo = {(2019, "equipe a"): {"10"}, (2020, "equipe a bis"): {"10"}, (2021, "autre"): {"11"},
             (2019, "equipe c"): {"12"}, (2020, "equipe c"): {"12"}, (2021, "equipe c 2"): {"12"}}
    r = proposer_equipes(nos, cache, {"Q1": {"libelle": "Equipe A", "noms": [{"nom": "Equipe A", "debut": "2015"}]}}, histo, {"10|2019": "Equipe A"})
    assert [p["id"] for p in r["propositions"]] == ["a-2019"] and r["propositions"][0]["qid"] == "Q1"
    assert r["propositions"][0]["nom_wikidata_cette_annee"] == "Equipe A"
    assert [p["id"] for p in r["conflits"]] == ["c-2020"] and [p["id"] for p in r["sans_appui"]] == ["b-2021"]
    print("[OK] audit_worlddb --test")


if __name__ == "__main__":
    if "--test" in sys.argv[1:]:
        _test()
        sys.exit(0)
    sys.exit(main())
