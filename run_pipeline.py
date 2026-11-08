#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Point d'entrée : collecte + résumés + écriture de data/ + notification ntfy."""

import argparse
import datetime as dt

import collector
import netutil
import notify


def main() -> None:
    p = argparse.ArgumentParser(description="Dashboard des courses cyclistes : mise à jour des données")
    p.add_argument("--season", type=int, default=None, help="saison UCI (défaut : saison UCI en cours, déterminée par l'UCI)")
    p.add_argument("--today", default="", help="date de référence AAAA-MM-JJ (tests)")
    p.add_argument("--only", default="", help="ne traiter que les courses dont le nom contient ce texte")
    p.add_argument("--max-races", type=int, default=0, help="limite le nombre de courses traitées (tests)")
    p.add_argument("--save-raw", default="", help="dossier où sauvegarder les réponses brutes")
    p.add_argument("--budget-min", type=float, default=40,
                   help="durée max de collecte en minutes (0 = illimitée) ; la suite au passage suivant")
    p.add_argument("--no-notify", action="store_true", help="ne pas envoyer de push ntfy")
    a = p.parse_args()
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    netutil.set_raw_dir(a.save_raw or None)
    collector.run(a.season, today=today, only=a.only, max_races=a.max_races,
                  budget_min=a.budget_min)
    if not a.no_notify:
        notify.send("data/index.json")


if __name__ == "__main__":
    main()
