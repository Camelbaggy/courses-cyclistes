#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Résumé lisible de data/ : comptages, tailles, champs manquants, échantillon de résumés."""

import json
import os
import sys
from collections import Counter


def main(base: str = "data") -> None:
    idx = json.load(open(os.path.join(base, "index.json"), encoding="utf-8"))
    races = idx.get("races") or []
    print(f"[INSPECT] saison {idx.get('season')} · {len(races)} courses · généré {idx.get('generated_at')}")
    print("[INSPECT] par catégorie :", dict(Counter(r.get("category") for r in races)))
    print("[INSPECT] par raison :", dict(Counter(r.get("selection_reason") for r in races)))
    print("[INSPECT] par statut :", dict(Counter(r.get("status") for r in races)))
    print(f"[INSPECT] latest {len(idx.get('latest') or [])} · victoires FR {len(idx.get('french_wins') or [])}"
          f" · à venir {len(idx.get('upcoming') or [])} · FDJ {'oui' if idx.get('fdj_united_series') else 'non'}")
    print(f"[INSPECT] notification : {idx.get('notification')}")
    total, sizes, src, keys, missing_route = 0, [], Counter(), Counter(), 0
    for r in races:
        path = os.path.join(base, "races", f"{r['id']}.json")
        if not os.path.exists(path):
            print(f"[MANQUANT] fichier {path}")
            continue
        sz = os.path.getsize(path)
        total += sz
        sizes.append((sz, r["name"]))
        race = json.load(open(path, encoding="utf-8"))
        for st in race.get("stages") or []:
            src[st.get("summary_source")] += 1
            for k, v in (st.get("results") or {}).items():
                if v:
                    keys[k] += 1
            if not st.get("route"):
                missing_route += 1
    print(f"[INSPECT] fichiers de course : {total/1e6:.1f} Mo au total ; plus gros :",
          ", ".join(f"{n} {s/1e3:.0f} Ko" for s, n in sorted(sizes, reverse=True)[:5]))
    print(f"[INSPECT] étapes par source de résumé : {dict(src)} ; classements présents : {dict(keys)} ;"
          f" étapes sans parcours : {missing_route}")
    for it in (idx.get("latest") or [])[:3]:
        print(f"[RESUME] {it['race_name']} / {it['label']} : {it.get('ai_summary')}")
    for w in (idx.get("french_wins") or [])[:15]:
        print(f"[VICTOIRE FR] {w['date']} {w['rider']} — {w['race_name']} ({w['label']})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data")
