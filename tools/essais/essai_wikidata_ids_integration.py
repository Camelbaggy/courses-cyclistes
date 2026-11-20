#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réel de l'intégration des identifiants externes Wikidata (wikidata.py / historique.py), sur un petit échantillon et dans un dossier temporaire.

Rien n'est écrit dans le dépôt ni dans les archives : les données publiques d'archives sont clonées (lecture seule), un échantillon reproductible est copié
dans un dossier temporaire, puis :
  1. REPRISE : ~100 coureurs rattachés du cache `entites/wikidata/coureurs.json` (sans `ids`) sont relus par `wikidata.relire_ids` (lots de 50) ;
     ~100 coureurs de `entites/historique/coureurs.json` par `historique.relire_ids_coureurs` ;
  2. SENS INVERSE : ~50 ids CQ Ranking / the-sports.org (`sources/`) résolus par `wikidata.run_ids_inverse` (OU par lots de 10, lecture par 50) ;
  3. contrôles : couverture des ids, naissance de nos fiches CQ / the-sports contre celle de Wikidata pour les ids relus, exemples de chaque statut.
Politesse de wikidata.py : UA du projet, 1 requête/s, abandon de l'hôte sur 403/429. Durée visée : quelques minutes.
"""
import datetime as dt
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter
from typing import Any, Dict, List

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RACINE)
import collector  # noqa: E402
import historique  # noqa: E402
import wikidata  # noqa: E402

N_COUREURS, N_HIST, N_CQ, N_TS = 100, 100, 30, 20
T0 = time.time()


def t() -> str:
    return f"t+{time.time() - T0:.0f}s"


def charger(chemin: str, defaut: Any) -> Any:
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def racine_archives() -> str:
    if os.environ.get("ARCHIVES"):
        return os.environ["ARCHIVES"]
    dest = tempfile.mkdtemp(prefix="archives_clone_")
    subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
                    "https://github.com/Camelbaggy/courses-cyclistes-archives", dest], check=True)
    subprocess.run(["git", "-C", dest, "sparse-checkout", "set", "data/archives/sources/cqranking", "data/archives/sources/thesports",
                    "data/archives/entites/wikidata", "data/archives/entites/historique"], check=True)
    subprocess.run(["git", "-C", dest, "checkout"], check=False)
    return os.path.join(dest, "data", "archives")


def ecrire(chemin: str, data: Any) -> None:
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def main() -> None:
    A = racine_archives()
    rnd = random.Random(20261119)
    tmp = tempfile.mkdtemp(prefix="essai_ids_")
    ent, src = os.path.join(tmp, "entites"), os.path.join(tmp, "sources")
    print(f"[ESSAI] {t()} archives lues dans {A}, travail dans {tmp}")

    # --- échantillons (sans `ids` : l'état réel des archives avant intégration)
    wd = charger(os.path.join(A, "entites", "wikidata", "coureurs.json"), {})
    rattaches = sorted(k for k, v in wd.items() if isinstance(v, dict) and v.get("qid"))
    ech_wd = {k: {c: x for c, x in wd[k].items() if c not in ("ids", "regle_ids")} for k in rnd.sample(rattaches, min(N_COUREURS, len(rattaches)))}
    hi = charger(os.path.join(A, "entites", "historique", "coureurs.json"), {})
    ech_hi = {k: {c: x for c, x in hi[k].items() if c not in ("ids", "regle_ids")} for k in rnd.sample(sorted(hi), min(N_HIST, len(hi)))}
    cq = charger(os.path.join(A, "sources", "cqranking", "coureurs.json"), {})
    ts = charger(os.path.join(A, "sources", "thesports", "coureurs.json"), {})
    cq_ok = sorted(k for k, v in cq.items() if isinstance(v, dict) and v.get("nom"))
    ts_ok = sorted(k for k, v in ts.items() if isinstance(v, dict) and v.get("nom"))
    ech_cq = {k: cq[k] for k in rnd.sample(cq_ok, min(N_CQ, len(cq_ok)))}
    ech_ts = {k: ts[k] for k in rnd.sample(ts_ok, min(N_TS, len(ts_ok)))}
    print(f"[ESSAI] échantillons : {len(ech_wd)} coureurs UCI, {len(ech_hi)} historiques, {len(ech_cq)} ids CQ (de {len(cq)}), {len(ech_ts)} ids the-sports (de {len(ts)})")
    if not (ech_wd and ech_hi and ech_cq and ech_ts):
        print("[ECHEC] données d'archives introuvables")
        sys.exit(1)
    ecrire(os.path.join(ent, "wikidata", "coureurs.json"), ech_wd)
    ecrire(os.path.join(ent, "historique", "coureurs.json"), ech_hi)
    ecrire(os.path.join(src, "cqranking", "coureurs.json"), ech_cq)
    ecrire(os.path.join(src, "thesports", "coureurs.json"), ech_ts)

    wikidata.preparer_reseau()
    api = wikidata.Api()
    today = dt.date.today()

    # --- 1. reprise REGLE_IDS : cache UCI
    ctx = wikidata.Contexte(api, wikidata.Cache(os.path.join(ent, "wikidata")), ent, today, 0)
    a_lire = {k: v["qid"] for k, v in ctx.cache.d["coureurs"].items() if wikidata.besoin_ids(v)}
    r0 = api.requetes
    n = wikidata.relire_ids(ctx, a_lire, ctx.cache.d["coureurs"])
    ctx.cache.ecrire()
    c = ctx.cache.d["coureurs"]
    cnt = Counter(cle for v in c.values() for cle in (v.get("ids") or {}))
    print(f"[ESSAI] {t()} reprise UCI : {n}/{len(a_lire)} relus en {api.requetes - r0} requête(s) ; avec ids : {sum(1 for v in c.values() if v.get('ids'))} ; par source : {dict(cnt)}")
    assert n == len(a_lire) and all(v.get("regle_ids") == wikidata.REGLE_IDS for v in c.values()), "reprise incomplète"
    assert not any("P2709" in json.dumps(v) for v in c.values())
    # contrôle croisé : ids CQ de Wikidata contre nos fiches CQ complètes (naissance)
    ok = diff = inconnu = 0
    for k, v in c.items():
        for i in (v.get("ids") or {}).get("cq", []):
            f = cq.get(i)
            if f and f.get("naissance") and v.get("naissance"):
                ok, diff = ok + (f["naissance"] == v["naissance"]), diff + (f["naissance"] != v["naissance"])
            else:
                inconnu += 1
    print(f"[ESSAI] contrôle P1541 : naissance CQ = Wikidata {ok}, différente {diff}, non comparable {inconnu}")

    # --- 1b. reprise REGLE_IDS : cache historique
    hctx = historique.Ctx(api, historique.Cache(os.path.join(ent, "historique")), ent, today, 0)
    r0 = api.requetes
    nh = historique.relire_ids_coureurs(hctx)
    hctx.cache.ecrire()
    h = hctx.cache.coureurs
    cnth = Counter(cle for v in h.values() for cle in (v.get("ids") or {}))
    print(f"[ESSAI] {t()} reprise historique : {nh} relus en {api.requetes - r0} requête(s) ; avec ids : {sum(1 for v in h.values() if v.get('ids'))} ; par source : {dict(cnth)}")
    assert nh == len(ech_hi) and all(v.get("regle_ids") == wikidata.REGLE_IDS for v in h.values())

    # --- 2. sens inverse
    ctx = wikidata.Contexte(api, wikidata.Cache(os.path.join(ent, "wikidata")), ent, today, 0)
    r0 = api.requetes
    b = wikidata.run_ids_inverse(ctx)
    ctx.cache.ecrire()
    inv = ctx.cache.d["ids_inverse"]
    print(f"[ESSAI] {t()} sens inverse : {b} ({api.requetes - r0} requêtes)")
    par = Counter((s, e["statut"]) for s, d in inv.items() for e in d.values())
    print(f"[ESSAI] statuts : {dict(sorted(par.items()))}")
    for s, d in sorted(inv.items()):
        for i, e in sorted(d.items()):
            if e["statut"] in ("ok", "a_verifier", "ambigu"):
                nom = (cq if s == "cq" else ts).get(i, {}).get("nom")
                print(f"[ESSAI]   {s} {i} {nom!r} -> {e['qid']} {e['statut']} {e.get('preuve') or json.dumps(e.get('detail'), ensure_ascii=False)}")
    # cohérence : un id déjà porté par `ids` n'est jamais cherché
    connus, _ = wikidata.ids_connus(ctx)
    assert not any(i in connus[s] for s, d in inv.items() for i in d), "id déjà connu cherché"
    assert all(e["regle"] == wikidata.REGLE_INVERSE for d in inv.values() for e in d.values())
    # relance : aucun nouvel appel
    r0 = api.requetes
    ctx2 = wikidata.Contexte(api, wikidata.Cache(os.path.join(ent, "wikidata")), ent, today, 0)
    wikidata.run_ids_inverse(ctx2)
    assert api.requetes == r0, "relance : requêtes inutiles"
    print(f"[ESSAI] {t()} total {api.requetes} requêtes ; valeurs hors format ignorées : {wikidata.IDS_IGNORES['valeurs']}")
    print("[OK] essai wikidata_ids_integration terminé")


if __name__ == "__main__":
    main()
