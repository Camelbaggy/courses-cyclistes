#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau : classement de fin de saison 2026 (data/ranking-2026.json) pour la saison encore au Calendrier.
Aucune écriture dans le vrai data/ : `classements_fin_calendrier` travaille sur une copie temporaire."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from collections import defaultdict

sys.path.insert(0, ".")
import collector  # noqa: E402
import netutil  # noqa: E402
import uci_ranking  # noqa: E402

ANNEE = 2026

print(f"######## get_ranking(season_year={ANNEE})")
rk = uci_ranking.get_ranking(season_year=ANNEE)
if not rk:
    print("[ECHEC] get_ranking a renvoyé None")
else:
    rows = rk["rows"]
    avec = [r for r in rows if r.get("team_code")]
    print(f"nom={rk['name']!r} date={rk['date']} season={rk.get('season')} lignes={len(rows)} avec team_code={len(avec)}")
    for r in rows[:5]:
        print(f"  {r['rank']:>3} {r['rider']:<28} {r['team']} [{r.get('team_code')}]")
    codes = defaultdict(set)
    for r in avec:
        codes[netutil.slugify(r["team"])].add(r["team_code"])
    uniques = sum(1 for c in codes.values() if len(c) == 1)
    print(f"libellés d'équipe distincts (slug) : {len(codes)} dont {uniques} avec un code unique")

print("\n######## classements_fin_calendrier sur une copie temporaire de data/")
tmp = tempfile.mkdtemp(prefix="essai_classement_fin_")
try:
    copie = os.path.join(tmp, "data")
    shutil.copytree(collector.DATA_DIR, copie, ignore=shutil.ignore_patterns("races", "archives")) if os.path.isdir(collector.DATA_DIR) else os.makedirs(copie)
    vrai = collector.DATA_DIR
    collector.DATA_DIR = copie
    try:
        ecrites = collector.classements_fin_calendrier(dt.date.today(), [ANNEE, ANNEE + 1])
    finally:
        collector.DATA_DIR = vrai
    print("saisons écrites :", ecrites)
    chemin = os.path.join(copie, f"ranking-{ANNEE}.json")
    if os.path.exists(chemin):
        d = json.load(open(chemin, encoding="utf-8"))
        print(f"{chemin} : {os.path.getsize(chemin)} octets, season={d.get('season')} date={d.get('date')} lignes={len(d.get('rows') or [])}")
        print(json.dumps({**d, "rows": d["rows"][:3]}, ensure_ascii=False, indent=1))
    else:
        print("[ECHEC] fichier non écrit")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
