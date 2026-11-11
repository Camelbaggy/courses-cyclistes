#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau du mode archives (collector.run_archive), sans rien écrire dans data/ :
1) sélection par époque (2023, 2018, 2013, 2010) : nombre de courses retenues par catégorie ; pour 2010, liste des
   courses WT et Pro (grands tours et monuments attendus) ;
2) run_archive([2023], budget_min=10, max_races=6) dans un dossier temporaire : tailles avant / après compactage,
   index.json (résumé), state.json ;
3) fin de saison forcée sur cet échantillon (finish_archive_season) : ranking.json et riders.json.
Rythme de 2 s entre requêtes sur dataride.uci.org. Balise [annees:2023,2018] pour changer les saisons de l'étape 1."""
import json
import os
import re
import sys
import tempfile
from collections import Counter

sys.path.insert(0, os.getcwd())
os.environ["AI_BUDGET_SECONDS"] = "0"
import collector  # noqa: E402
import netutil  # noqa: E402
import selection  # noqa: E402
import uci  # noqa: E402

netutil.HOST_DELAYS["dataride.uci.org"] = 2.0
m = re.search(r"\[annees:([0-9,]+)\]", os.environ.get("MSG", ""))
ANNEES = [int(a) for a in m.group(1).split(",")] if m else [2023, 2018, 2013, 2010]


def taille(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode())


print("=== 1) Sélection par époque ===")
for an in ANNEES:
    sid = uci.get_season_id(an)
    if sid is None:
        print(f"[ESSAI] {an} : saison introuvable")
        continue
    comps = uci.list_competitions(sid)
    sel = selection.select(comps, [])
    par_cat = Counter(cat for _, cat, _ in sel)
    classes_none = Counter(c.get("uci_class") for c in comps if selection.classer(c, []) is None
                           and selection.categorie_classe(c.get("uci_class", "")) is None)
    print(f"[ESSAI] {an} : {len(comps)} courses, {len(sel)} retenues d'office : {dict(par_cat)} ; "
          f"non retenues par classe : {dict(classes_none.most_common(8))}")
    if an == 2010:
        for cat in ("WT", "Pro"):
            noms = sorted(((c.get("start_date"), c["name"], c.get("uci_class")) for c, k, _ in sel if k == cat))
            print(f"[ESSAI] 2010 {cat} ({len(noms)}) :")
            for d, n, cl in noms:
                print(f"    {d}  {cl:5}  {n}")
        attendus = ["giro", "tour de france", "vuelta", "sanremo", "flanders", "vlaanderen", "roubaix", "li[eè]ge",
                    "lombardia"]
        noms_wt = " | ".join(c["name"].lower() for c, k, _ in sel if k == "WT")
        print("[ESSAI] 2010 grands tours / monuments présents :",
              {a: bool(re.search(a, noms_wt)) for a in attendus})

print("=== 2) run_archive([2023], budget 10 min, 6 courses) ===")
tmp = tempfile.mkdtemp()
collector.ARCHIVES_DIR = os.path.join(tmp, "archives")
avant_apres = []
_compact = collector.compact_race


def compact_espion(race):
    out = _compact(race)
    avant_apres.append((race.get("name"), taille(race), taille(out)))
    return out


collector.compact_race = compact_espion
collector.run_archive([2023], budget_min=10, max_races=6)
for nom, a, b in avant_apres:
    print(f"[ESSAI] compactage {nom} : {a/1e3:.0f} Ko -> {b/1e3:.0f} Ko ({100*b/max(a,1):.0f} %)")
for racine, _, fichiers in sorted(os.walk(collector.ARCHIVES_DIR)):
    for f in sorted(fichiers):
        p = os.path.join(racine, f)
        print(f"[ESSAI] fichier {os.path.relpath(p, tmp)} : {os.path.getsize(p)/1e3:.1f} Ko")
d2023 = os.path.join(collector.ARCHIVES_DIR, "2023")
ix = json.load(open(os.path.join(d2023, "index.json"), encoding="utf-8"))
print("[ESSAI] index.json 2023 :", {k: ix[k] for k in ("season", "archive", "complete")},
      f"{len(ix['races'])} courses,", [(r["name"], r["winner"] and r["winner"]["name"], r["status"]) for r in ix["races"]],
      f"latest {len(ix['latest'])}, victoires françaises {len(ix['french_wins'])}")
print("[ESSAI] state.json 2023 :", {k: (v if k == "complete" else f"{len(v)} décisions")
                                    for k, v in json.load(open(os.path.join(d2023, "state.json"))).items()})
print("[ESSAI] archives/index.json :", json.load(open(os.path.join(collector.ARCHIVES_DIR, "index.json"))))

print("=== 3) Fin de saison forcée sur l'échantillon ===")
res = collector.finish_archive_season(2023, d2023)
for nom in ("ranking.json", "riders.json"):
    p = os.path.join(d2023, nom)
    print(f"[ESSAI] {nom} : {os.path.getsize(p)/1e3:.1f} Ko" if os.path.exists(p) else f"[ESSAI] {nom} : absent")
rk = res["ranking"]
if rk:
    print(f"[ESSAI] classement « {rk['name']} » ({rk.get('date')}) : {len(rk['rows'])} lignes ; top 3 :",
          [(r["rank"], r["name"], r["points"]) for r in rk["rows"][:3]])
rd = res["riders"]
print(f"[ESSAI] riders.json : {len(rd['riders'])} coureurs, classement {rd.get('ranking')}, generated_at {rd['generated_at']}")
fr = sorted((f for f in rd["riders"].values() if f.get("uci_rank")), key=lambda f: f["uci_rank"])[:3]
print("[ESSAI] coureurs classés (top 3 de l'échantillon) :", [(f["name"], f["uci_rank"], f.get("age")) for f in fr])
