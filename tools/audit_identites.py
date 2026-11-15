#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit local des identités de coureurs (étape E0 de docs/PLAN_ENCYCLOPEDIE.md) : aucun réseau, lecture seule.

Usage : python tools/audit_identites.py <dossier_archives> [--exemples N] [--json sortie.json]
`dossier_archives` = `data/archives` du dépôt d'archives (ou d'un worktree) : lit `carrieres/*.json`,
`<année>/ranking.json` et `<année>/riders.json`. Rapporte :
  1. un même nom normalisé (rider_id sans la date) avec plusieurs dates de naissance ;
  1b. (complément) mêmes mots du nom dans un autre ordre, même date de naissance, rider_id différents
      (« DUPONT Jean » / « JEAN Dupont ») ;
  2. un même `uci_id` (ranking.json) associé à plusieurs `rider_id` ;
  3. un même `rider_id` associé à plusieurs `uci_id` ;
  4. les coureurs sans date de naissance (rider_id sans suffixe AAAAMMJJ).
Ne modifie rien ; les rapprochements retenus iront dans alias_coureurs.json (jamais devinés)."""

import datetime
import glob
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

_RE_DATE = re.compile(r"-(\d{8})$")


def decouper(rider_id: str) -> Tuple[str, Optional[str]]:
    """'dupont-jean-19900102' -> ('dupont-jean', '19900102') ; sans date -> ('dupont-jean', None)."""
    m = _RE_DATE.search(rider_id)
    return (rider_id[:m.start()], m.group(1)) if m else (rider_id, None)


def _ecart_jours(a: str, b: str) -> Optional[int]:
    try:
        da = datetime.date(int(a[:4]), int(a[4:6]), int(a[6:]))
        db = datetime.date(int(b[:4]), int(b[4:6]), int(b[6:]))
    except ValueError:
        return None
    return abs((da - db).days)


def _proches(dates: List[str]) -> bool:
    """Deux dates à moins de 32 jours d'écart (faute de frappe probable plutôt qu'homonymes)."""
    d = [x for x in dates if x]
    return any((_ecart_jours(a, b) or 999) <= 31 for i, a in enumerate(d) for b in d[i + 1:])


def _lire(chemin: str) -> Any:
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None  # ex. saison 2019 sans classement ni riders.json
    except (OSError, ValueError) as e:
        print(f"[WARN] lecture impossible : {chemin} ({e})")
        return None


def charger(dossier: str) -> Dict[str, Any]:
    """Collecte {ids: {rider_id: {noms, sources}}, uci: [(annee, rider_id, uci_id)]}."""
    ids: Dict[str, Dict[str, Any]] = {}

    def noter(rid: str, nom: Optional[str], source: str) -> None:
        e = ids.setdefault(rid, {"noms": set(), "sources": set()})
        if nom:
            e["noms"].add(nom)
        e["sources"].add(source)

    nb_fichiers = 0
    for f in sorted(glob.glob(os.path.join(dossier, "carrieres", "*.json"))):
        if os.path.basename(f) == "index.json":
            continue
        d = _lire(f)
        if not isinstance(d, dict):
            continue
        nb_fichiers += 1
        for rid, v in d.items():
            noter(rid, v.get("name") if isinstance(v, dict) else None, "carrieres")
    uci: List[Tuple[str, str, Any]] = []
    for sous in sorted(glob.glob(os.path.join(dossier, "[0-9][0-9][0-9][0-9]"))):
        annee = os.path.basename(sous)
        d = _lire(os.path.join(sous, "riders.json"))
        if isinstance(d, dict):
            nb_fichiers += 1
            for rid, v in (d.get("riders") or {}).items():
                noter(rid, v.get("name") if isinstance(v, dict) else None, "riders-" + annee)
        d = _lire(os.path.join(sous, "ranking.json"))
        if isinstance(d, dict):
            nb_fichiers += 1
            for lg in d.get("rows") or []:
                rid = lg.get("rider_id")
                if rid:
                    noter(rid, lg.get("name"), "ranking-" + annee)
                    if lg.get("uci_id") is not None:
                        uci.append((annee, rid, lg["uci_id"]))
    return {"ids": ids, "uci": uci, "fichiers": nb_fichiers}


def _nom(ids: Dict[str, Dict[str, Any]], rid: str) -> str:
    noms = sorted(ids[rid]["noms"]) if rid in ids else []
    return noms[0] if noms else "?"


def auditer(dossier: str, nb_exemples: int = 10) -> Dict[str, Any]:
    c = charger(dossier)
    ids = c["ids"]
    rapport: Dict[str, Any] = {"fichiers_lus": c["fichiers"], "rider_id_distincts": len(ids)}

    # 1. même nom (slug sans date) avec plusieurs dates de naissance
    par_slug: Dict[str, Set[str]] = defaultdict(set)
    for rid in ids:
        slug, date = decouper(rid)
        par_slug[slug].add(date or "")
    r1 = {s: sorted(ds) for s, ds in par_slug.items() if len({d for d in ds if d}) > 1}
    r1_inconnue = {s: sorted(ds) for s, ds in par_slug.items()
                   if "" in ds and any(ds - {""}) and s not in r1}  # une version datée + une non datée
    r1_proches = {s: v for s, v in r1.items() if _proches(v)}
    rapport["1_dont_dates_proches"] = {"n": len(r1_proches), "exemples": sorted(r1_proches.items())[:nb_exemples]}
    rapport["1_noms_a_plusieurs_dates"] = {"n": len(r1), "ids_concernes": sum(len(v) for v in r1.values()),
                                           "exemples": [(s or '(nom vide)', v, _nom(ids, f"{s}-{v[-1]}" if v[-1] else s)) for s, v in sorted(r1.items())[:nb_exemples]]}
    rapport["1_noms_avec_et_sans_date"] = {"n": len(r1_inconnue), "exemples": sorted(r1_inconnue.items())[:nb_exemples]}

    # 1b. mêmes mots dans un autre ordre + même date, ids différents
    par_mots: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    for rid in ids:
        slug, date = decouper(rid)
        if date:
            par_mots[("-".join(sorted(slug.split("-"))), date)].add(rid)
    r1b = {k: sorted(v) for k, v in par_mots.items() if len(v) > 1}
    rapport["1b_ordre_des_mots"] = {"n": len(r1b), "exemples": sorted(r1b.values())[:nb_exemples]}

    # 2 / 3. uci_id <-> rider_id
    uci_vers_ids: Dict[Any, Set[str]] = defaultdict(set)
    id_vers_uci: Dict[str, Set[Any]] = defaultdict(set)
    for _annee, rid, uid in c["uci"]:
        uci_vers_ids[uid].add(rid)
        id_vers_uci[rid].add(uid)
    r2 = {u: sorted(v) for u, v in uci_vers_ids.items() if len(v) > 1}
    r3 = {r: sorted(v) for r, v in id_vers_uci.items() if len(v) > 1}
    rapport["uci_id_distincts"] = len(uci_vers_ids)
    rapport["2_uci_id_a_plusieurs_rider_id"] = {"n": len(r2), "exemples": sorted(r2.items())[:nb_exemples]}
    rapport["3_rider_id_a_plusieurs_uci_id"] = {"n": len(r3), "exemples": sorted(r3.items())[:nb_exemples]}

    # 4. sans date de naissance
    sans = sorted(rid for rid in ids if decouper(rid)[1] is None)
    rapport["4_sans_date_naissance"] = {"n": len(sans), "exemples": [(r, _nom(ids, r), sorted(ids[r]["sources"])[:3]) for r in sans[:nb_exemples]]}
    return rapport


def afficher(r: Dict[str, Any]) -> None:
    print(f"fichiers lus : {r['fichiers_lus']} ; rider_id distincts : {r['rider_id_distincts']} ; uci_id distincts : {r['uci_id_distincts']}")
    for cle in ("1_noms_a_plusieurs_dates", "1_dont_dates_proches", "1_noms_avec_et_sans_date", "1b_ordre_des_mots",
                "2_uci_id_a_plusieurs_rider_id", "3_rider_id_a_plusieurs_uci_id", "4_sans_date_naissance"):
        bloc = r[cle]
        print(f"\n== {cle} : {bloc['n']}")
        for ex in bloc["exemples"]:
            print("  ", ex)


def _tests() -> None:
    assert decouper("dupont-jean-19900102") == ("dupont-jean", "19900102")
    assert decouper("dupont-jean") == ("dupont-jean", None)
    print("tests locaux audit_identites OK")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    if "--test" in args:
        _tests()
        sys.exit(0)
    n = 10
    sortie = None
    if "--exemples" in args:
        i = args.index("--exemples")
        n = int(args[i + 1])
        del args[i:i + 2]
    if "--json" in args:
        i = args.index("--json")
        sortie = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1 or not os.path.isdir(args[0]):
        print(__doc__)
        sys.exit(2)
    rap = auditer(args[0], n)
    afficher(rap)
    if sortie:
        with open(sortie, "w", encoding="utf-8") as f:
            json.dump(rap, f, ensure_ascii=False, indent=1, default=list)
