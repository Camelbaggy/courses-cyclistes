#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai des résumés IA sur les courses de test (tools/fixtures_ia/) : dossier, repli, Gemini, notification.
Lancé depuis la racine du dépôt. Gemini n'est appelé que si GEMINI_API_KEY est défini et AI_BUDGET_SECONDS > 0."""

import json
import os
import sys

sys.path.insert(0, ".")
import agents_flash as af  # noqa: E402

RECIT = ("Brandt attacked on the lower slopes of the final climb and rode alone to the summit, "
         "while Ricci limited his losses to take the overall lead.")


def charger(nom):
    with open(os.path.join("tools", "fixtures_ia", nom), encoding="utf-8") as f:
        return json.load(f)


def main():
    print(f"[ESSAI] clé Gemini : {'présente' if af.GEMINI_API_KEY else 'ABSENTE'} ; budget IA : {af.AI_BUDGET_SECONDS} s")
    etapes, un_jour = charger("course_etapes.json"), charger("course_un_jour.json")
    cas = [(etapes, 2, [RECIT]), (etapes, 0, []), (un_jour, 0, [])]

    # contrôle déterministe des nombres (hors ligne)
    doss = af.build_stage_dossier(etapes, 2, [RECIT])
    print("[ESSAI] contrôle nombres, texte valide :", af.check_numbers("Aksel Brandt gagne à 14 s de Tomás Aguirre.", doss))
    print("[ESSAI] contrôle nombres, texte faux   :", af.check_numbers("Aksel Brandt gagne avec 99 s d'avance.", doss))

    for race, idx, stories in cas:
        print("\n" + "=" * 70)
        print(f"[ESSAI] {race['name']} — indice {idx}")
        print(af.build_stage_dossier(race, idx, stories))
        print("\n--- Repli déterministe\n" + af.build_fallback_summary(race, idx))
        texte, source = af.summarize_stage(race, idx, stories)
        print(f"\n--- summarize_stage -> source={source}\n{texte}")

    print("\n" + "=" * 70)
    for items in ([(etapes, 2)], [(un_jour, 0)], [(etapes, 1), (un_jour, 0)], []):
        print(json.dumps(af.build_notification(items), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
