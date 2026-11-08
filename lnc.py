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
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

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
        races = get_races()
        today = date.today().isoformat()
        past = [r["date"] for r in races if r["date"] <= today]
        return {"source": "lnc", "updated": max(past) if past else None, "individual": [
            {"rank": r["rank"], "rider": r["rider"], "team": r["team"], "points": r["points"]} for r in individual],
            "races": races}
    except Exception as e:
        print(f"[WARN] LNC : page illisible : {e}")
        return None


def get_races(page: str = "") -> List[Dict[str, Any]]:
    """Manches de la FDJ United Series : liste filtrée `/resultats?french_cup=1` (une entrée par course :
    nom, date JJ/MM/AAAA, classe, vainqueur). Triées par date. `page` est ignoré (compatibilité)."""
    lst = netutil.fetch_text(BASE + "/resultats?french_cup=1", raw_name="lnc_french_cup.html")
    if not lst:
        return []
    txt = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", lst, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", "\n", txt)
    lines = [" ".join(html.unescape(x).split()) for x in txt.splitlines()]
    lines = [x for x in lines if x]
    races: List[Dict[str, Any]] = []
    for i, ln in enumerate(lines):
        m = re.fullmatch(r"(\d\d)/(\d\d)/(\d{4})", ln)
        if m and i > 0 and not lines[i - 1].startswith(("Classe", "Vainqueur")):
            races.append({"name": lines[i - 1], "date": f"{m.group(3)}-{m.group(2)}-{m.group(1)}", "race_id": None})
    seen = set()
    out = []
    for r in sorted(races, key=lambda r: r["date"]):
        if (r["name"], r["date"]) not in seen:
            seen.add((r["name"], r["date"]))
            out.append(r)
    return out


_MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
         "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
CALENDAR_PATHS = ["/calendrier?french_cup=1", "/fdj-united-series"]   # « Calendrier FDJ UNITED SERIES », filtre année
_pages_cal: Dict[str, Optional[str]] = {}


def _lignes(page: str) -> List[str]:
    txt = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", "\n", txt)
    return [x for x in (" ".join(html.unescape(l).split()) for l in txt.splitlines()) if x]


def _date_ligne(ln: str, annee: int) -> Optional[str]:
    """« 22/03/2027 », « dimanche 22 mars 2027 » ou « 22 mars » (année de la page) -> ISO ; None sinon."""
    m = re.fullmatch(r"(\d\d)/(\d\d)/(\d{4})", ln)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.fullmatch(r"(?:\w+\.? )?(\d{1,2})(?:er)? ([a-zéèêûô]+)\.?(?: (\d{4}))?", ln.lower())
    if m:
        mois = _MOIS.get(netutil.normalize(m.group(2)))
        if mois:
            return f"{int(m.group(3) or annee):04d}-{mois:02d}-{int(m.group(1)):02d}"
    return None


def get_fdj_calendar(year: int) -> List[Dict[str, Any]]:
    """Manches FDJ United Series de l'année `year` [{"name", "date", "race_id": None}], triées par date : liste des
    résultats LNC (`get_races`, manches déjà courues) complétée, si la LNC publie un calendrier de la saison, par
    les dates annoncées sur ses pages de calendrier. [] si rien n'est publié pour cette année."""
    manches: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in get_races():
        if r["date"].startswith(f"{year}-"):
            manches[(netutil.normalize(r["name"]), r["date"])] = r
    for chemin in CALENDAR_PATHS:
        if chemin not in _pages_cal:
            _pages_cal[chemin] = netutil.fetch_text(BASE + chemin, raw_name="lnc_cal_" + chemin.strip("/").replace("/", "_"))
        page = _pages_cal[chemin]
        if not page:
            continue
        lignes = _lignes(page)
        for i, ln in enumerate(lignes):
            d = _date_ligne(ln, year)
            if d and d.startswith(f"{year}-") and i > 0 and not _date_ligne(lignes[i - 1], year):
                nom = lignes[i - 1]
                if len(nom) > 3 and not nom.lower().startswith(("classe", "vainqueur", "date")):
                    manches.setdefault((netutil.normalize(nom), d), {"name": nom, "date": d, "race_id": None})
    return sorted(manches.values(), key=lambda r: (r["date"], r["name"]))
