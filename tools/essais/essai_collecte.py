"""Essai réseau : passage complet du collecteur sur une COPIE de data/ (rien n'est commité), puis contrôle des index
par saison (intersaison : saison affichée + saison suivante), du classement UCI et des fiches coureurs."""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.getcwd())
os.environ["AI_BUDGET_SECONDS"] = "0"
src = os.path.abspath("data")
tmp = tempfile.mkdtemp()
shutil.copytree(src, os.path.join(tmp, "data"))
os.chdir(tmp)
import collector  # noqa: E402

collector.run(None, budget_min=12)
lire = lambda n: json.load(open(os.path.join("data", n), encoding="utf-8"))  # noqa: E731
saisons = lire("seasons.json")
print("[ESSAI] seasons.json :", saisons)
for y in saisons["available"]:
    ix = lire(f"index-{y}.json")
    print(f"[ESSAI] index-{y} : {len(ix['races'])} courses, {len(ix['upcoming'])} à venir, "
          f"FDJ {'oui' if ix.get('fdj_united_series') else 'non'}, latest {len(ix['latest'])} ; "
          f"courses : {[r['name'] for r in ix['races']][:5]}")
rk = lire("ranking.json") if os.path.exists("data/ranking.json") else {}
print(f"[ESSAI] ranking.json : {rk.get('name')} {rk.get('date')} {len(rk.get('rows') or [])} lignes")
for y in saisons["available"]:
    p = f"data/riders-{y}.json"
    if os.path.exists(p):
        d = lire(f"riders-{y}.json")
        fr = sorted((f for f in d["riders"].values() if f.get("is_french") and f.get("uci_rank")),
                    key=lambda f: f["uci_rank"])[:5]
        print(f"[ESSAI] riders-{y} : {len(d['riders'])} coureurs, {os.path.getsize(p)/1e6:.2f} Mo ; Français :",
              [(f["name"], f["uci_rank"], [(d["races"][b["race_id"]]["name"], b["label"], b["rank"], b["uci_points"])
                                           for b in f.get("best", [])]) for f in fr])
print("[ESSAI] index.json saison :", lire("index.json")["season"])
