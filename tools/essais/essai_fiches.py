"""Essai réseau : classement UCI réel (DataRide) rapproché des fiches coureurs calculées sur data/races."""
import sys
sys.path.insert(0, ".")
import riders
import uci_ranking

ranking = uci_ranking.get_ranking()
print(f"[ESSAI] classement : {ranking and ranking.get('name')} au {ranking and ranking.get('date')}, "
      f"{len((ranking or {}).get('rows') or [])} lignes")
courses = riders.charger_courses("data/races")
data = riders.build_riders(courses, ranking, season=2026)
fiches = data["riders"]
classes = [f for f in fiches.values() if f.get("uci_rank")]
print(f"[ESSAI] {len(fiches)} coureurs, {len(classes)} avec un rang UCI")
for rid, f in sorted(fiches.items(), key=lambda x: x[1].get("uci_rank") or 99999)[:10]:
    print(f"  {f['uci_rank']:>4} {f['name']:<28} {f['uci_points']} pts · {f.get('stats', {}).get('wins', 0)} victoires")
fr = sorted((f for f in fiches.values() if f.get("is_french") and f.get("uci_rank")), key=lambda f: f["uci_rank"])[:10]
print("[ESSAI] meilleurs Français :", ", ".join(f"{f['name']} ({f['uci_rank']}e)" for f in fr))
top = {r["rider_id"] for r in ranking["rows"] if r.get("rank") and r["rank"] <= 100}
manquants = [r["name"] for r in ranking["rows"] if r.get("rank") and r["rank"] <= 100 and r["rider_id"] not in fiches]
print(f"[ESSAI] top 100 UCI sans fiche (non vus dans nos courses ou nom différent) : {len(manquants)} {manquants[:10]}")
