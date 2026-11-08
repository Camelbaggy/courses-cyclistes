#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LNC (lncpro.fr) : classement général individuel de la FDJ United Series et liste des manches.

Pages HTML rendues côté serveur (Drupal) ; lignes en <div> (pas de <table>) :
  <div class="result-item-header …"> <div class="result-rang">1</div> <div class="result-racer-name">VENTURINI, Clément</div>
  <div class="result-country"><img alt="France"></div> <div class="result-team">Unibet Rose Rockets</div>
  <div class="result-time">263</div></div>
robots.txt : seuls /core/, /profiles/ et les README sont interdits.
"""

import html
import re
from typing import Any, Dict, List, Optional

import netutil

BASE = "https://www.lncpro.fr"


def _clean(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def _display_name(raw: str) -> str:
    """« VENTURINI, Clément » -> « Clément VENTURINI »."""
    if "," in raw:
        nom, prenom = [x.strip() for x in raw.split(",", 1)]
        return f"{prenom} {nom}".strip()
    return raw.strip()


def parse_ranking(page: str) -> List[Dict[str, Any]]:
    """Premier bloc de classement de la page (s'arrête quand le rang repart à 1)."""
    out: List[Dict[str, Any]] = []
    for blk in page.split("result-item-header")[1:]:
        def field(cls: str) -> str:
            m = re.search(r'class="%s[^"]*"[^>]*>(.*?)</div>' % cls, blk, re.S)
            return _clean(m.group(1)) if m else ""
        rank = field("result-rang")
        if not rank.isdigit():
            continue
        if out and int(rank) == 1:
            break
        pts = field("result-time").replace(" ", "")
        country = re.search(r'<img[^>]*alt="([^"]*)"', blk)
        out.append({"rank": int(rank), "rider": _display_name(field("result-racer-name")),
                    "team": field("result-team") or None, "country": html.unescape(country.group(1)) if country else None,
                    "points": int(pts) if pts.isdigit() else None})
    return out


def get_fdj_united_series() -> Optional[Dict[str, Any]]:
    """Bloc `fdj_united_series` de l'index (SPEC §4.1) ou None. `race_id` des manches : None (rapprochement fait
    par le collecteur, par nom normalisé + date)."""
    page = netutil.fetch_text(BASE + "/fdj-united-series", raw_name="lnc_fdj.html")
    if not page:
        return None
    try:
        individual = parse_ranking(page)
        if not individual:
            print("[WARN] LNC : classement FDJ United Series introuvable dans la page")
            return None
        return {"source": "lnc", "updated": None, "individual": [
            {"rank": r["rank"], "rider": r["rider"], "team": r["team"], "points": r["points"]} for r in individual],
            "races": get_races(page)}
    except Exception as e:
        print(f"[WARN] LNC : page illisible : {e}")
        return None


def get_races(page: str) -> List[Dict[str, Any]]:
    return []
