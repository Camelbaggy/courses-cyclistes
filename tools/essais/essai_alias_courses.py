#!/usr/bin/env python3
"""Sonde : preuve Wikidata des équivalences de courses renommées (groupes de COURSES_WORLDDB, tools/maillots.py).

Pour chaque groupe de clés d'épreuve (toutes les dénominations d'une même course) : séries Wikidata candidates (recherche par nom sur toutes
les dénominations, P31 = course cycliste), lecture des éditions de chaque candidate, puis concordance des vainqueurs de NOS éditions avec ceux
de Wikidata, sur TOUTES les années (pas seulement 2019-2025 : certaines dénominations n'ont servi qu'un an). Verdict par groupe :
  PROUVÉ = une seule série où CHAQUE clé a au moins une concordance et aucune discordance, et au moins 2 concordances au total ;
  sinon REFUSÉ (raison). Rien n'est écrit dans le dépôt ; le résultat (JSON) est imprimé dans les logs.
Entités lues sur GitHub Pages (entites/courses/, entites/wikidata/coureurs.json), 1 requête/s vers Wikidata, 429 : attente du Retry-After.
"""
import datetime as dt
import json
import os
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "tools")
import collector  # noqa: E402
import historique  # noqa: E402
import maillots  # noqa: E402
import netutil  # noqa: E402

BASE = "https://camelbaggy.github.io/courses-cyclistes-archives/data/archives/entites"


def telecharger(dossier, chemins):
    for c in chemins:
        d = netutil.fetch_json(f"{BASE}/{c}")
        if d is None:
            print(f"[WARN] {c} illisible")
            continue
        os.makedirs(os.path.dirname(os.path.join(dossier, c)), exist_ok=True)
        with open(os.path.join(dossier, c), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)


def main():
    alias = collector.charger_alias(collector.ALIAS_COURSES)
    groupes = {w: [alias.get(k, k) for k in cles] for w, cles in maillots.COURSES_WORLDDB.items()}
    groupes = {w: list(dict.fromkeys(c)) for w, c in groupes.items() if len(set(c)) > 1}
    print(f"[ALIAS] {len(groupes)} groupe(s) à prouver")
    tmp = tempfile.mkdtemp()
    ent = os.path.join(tmp, "entites")
    lettres = sorted({historique._lettre(k) for c in groupes.values() for k in c})
    telecharger(ent, [f"courses/{l}.json" for l in lettres] + ["wikidata/coureurs.json"])
    historique.ANNEES_PREUVE = (1900, 2100)        # toutes les années
    ctx = historique.Ctx(historique.creer_api(), historique.Cache(os.path.join(ent, "historique")), ent, dt.date.today(), 25)
    fiches = {}
    for l in lettres:
        fiches.update(collector._load(os.path.join(ent, "courses", f"{l}.json"), {}) or {})
    nos = historique.nos_vainqueurs(ent)
    lus = {}
    resultats = {}
    for w, cles in sorted(groupes.items()):
        if ctx.hors_budget():
            print("[ALIAS] budget épuisé")
            break
        manq = [k for k in cles if k not in fiches]
        if manq:
            resultats[w] = {"verdict": "REFUSÉ", "raison": "cle_sans_entite", "cles": manq}
            continue
        noms = []
        for k in cles:
            noms += historique.noms_recherche(fiches[k])
        cands = historique.candidats_wikidata(ctx, list(dict.fromkeys(noms))[:6])
        detail = {}
        for q in cands:
            if q not in lus:
                lus[q] = historique.lire_editions(ctx, q)
            if not lus[q]:
                continue
            par_cle = {k: historique.preuve_serie(ctx, lus[q], nos.get(k) or {}) for k in cles}
            detail[q] = {k: {"concordances": p["concordances"], "discordances": p["discordances"]} for k, p in par_cle.items()}
        bonnes = [q for q, d in detail.items() if all(v["concordances"] and not v["discordances"] for v in d.values())
                  and sum(len(v["concordances"]) for v in d.values()) >= 2]
        resultats[w] = {"verdict": "PROUVÉ" if len(bonnes) == 1 else "REFUSÉ", "cles": cles,
                        "qid": bonnes[0] if len(bonnes) == 1 else None,
                        "raison": None if len(bonnes) == 1 else ("ambigu" if bonnes else "aucune_serie_concordante"),
                        "candidats": detail}
        print(f"[ALIAS] {w} : {resultats[w]['verdict']} {resultats[w]['qid'] or resultats[w]['raison']} "
              f"[{ctx.api.requetes} requêtes, {ctx.minutes():.1f} min]", flush=True)
    print("[ALIAS] RESULTATS " + json.dumps(resultats, ensure_ascii=False))


if __name__ == "__main__":
    main()
