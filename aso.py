#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enrichissement des courses ASO (accord obtenu par le propriétaire du projet).

Sites ASO couverts (pages HTML rendues côté serveur, vérifiées par sonde le 8 novembre 2026) :
  tdf        letour.fr                       Tour de France
  parisnice  paris-nice.fr                   Paris-Nice
  dauphine   criterium-du-dauphine.fr        Critérium du Dauphiné (servi sous « Tour Auvergne-Rhône-Alpes »)
  roubaix    paris-roubaix.fr                Paris-Roubaix
  liege      liege-bastogne-liege.be         Liège-Bastogne-Liège
  paristours paris-tours.fr                  Paris-Tours
  vuelta     lavuelta.es                     Vuelta a España
Non couverts : Flèche wallonne (fleche-wallonne.be, flechewallonne.be, laflechewallonne.be : DNS inexistant),
Tour de Burgos (organisé par la Diputación de Burgos, pas par ASO), courses ASO hors Europe (non sondées).

URL utilisées (toutes autorisées par robots.txt ; /api, /graphql, /*/ajax, /*/block ne sont JAMAIS appelées) :
  {base}/fr/classements/etape-N/<code>   codes ite (étape) itg (général) ipg (points) img (montagne)
                                         ijg (jeunes) etg (équipes) ice (combativité)
  {base}/fr/etape-N                      en-tête de l'étape (distance, profil, D+), cols, secteurs pavés, liens d'articles
  {base}/fr/parcours-general             repli : tableau étape / type / date / départ > arrivée / distance
  {base}/fr/actus/AAAA/etape-N/...       articles de récit (HTML complet, pas le fil /ajax)
Une course d'un jour est l'« étape 1 ».

ÉDITIONS : chaque site ne sert que son édition courante (le Tour affiche « 2027 » alors que l'on est en novembre 2026) ;
aucune URL d'archive n'a été trouvée (/fr/classements/2025/…, /fr/archives, ?year=… : 404 ou ignorés). L'année de
l'édition servie est lue dans le <title> de la page /fr/etape-1 ; match_race renvoie None si elle diffère de l'année
de la course demandée (aucune donnée d'une autre édition n'est jamais mélangée).
"""

import html
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

import netutil

SITES = {
    "tdf": {"base": "https://www.letour.fr", "label": "Tour de France",
            "any": ["tour de france"], "none": ["femmes", "women", "avenir", "espoirs"]},
    "parisnice": {"base": "https://www.paris-nice.fr", "label": "Paris-Nice",
                  "any": ["paris nice"], "none": ["femmes", "women"]},
    "dauphine": {"base": "https://www.criterium-du-dauphine.fr", "label": "Critérium du Dauphiné",
                 "any": ["criterium du dauphine", "dauphine", "tour auvergne rhone alpes"], "none": ["femmes", "women"]},
    "roubaix": {"base": "https://www.paris-roubaix.fr", "label": "Paris-Roubaix",
                "any": ["paris roubaix"], "none": ["femmes", "women", "espoirs", "juniors"]},
    "liege": {"base": "https://www.liege-bastogne-liege.be", "label": "Liège-Bastogne-Liège",
              "any": ["liege bastogne liege"], "none": ["femmes", "women", "espoirs", "juniors"]},
    "paristours": {"base": "https://www.paris-tours.fr", "label": "Paris-Tours",
                   "any": ["paris tours"], "none": ["femmes", "women", "espoirs", "juniors"]},
    "vuelta": {"base": "https://www.lavuelta.es", "label": "Vuelta a España",
               "any": ["vuelta a espana", "la vuelta", "vuelta ciclista a espana"], "none": ["femenina", "femmes", "women", "juvenil"]},
}

CODES = {"stage": "ite", "gc": "itg", "points": "ipg", "mountain": "img", "youth": "ijg", "teams": "etg",
         "combativity": "ice"}
PROFILES = {"plat": "plat", "montagne": "montagne", "haute montagne": "montagne", "moyenne montagne": "vallonné",
            "vallonne": "vallonné", "vallonnee": "vallonné", "accidente": "accidenté", "accidentee": "accidenté",
            "contre la montre": "clm", "contre la montre individuel": "clm", "clm": "clm",
            "contre la montre par equipes": "clm"}

_PAGES: Dict[str, Optional[str]] = {}
_YEARS: Dict[str, Optional[int]] = {}


def _page(url: str) -> Optional[str]:
    if url not in _PAGES:
        _PAGES[url] = netutil.fetch_text(url, retries=2)
    return _PAGES[url]


def _stage_n(stage_number: Optional[int]) -> int:
    return 1 if stage_number is None else int(stage_number)


# ---------------------------------------------------------------- reconnaissance de la course / de l'édition

def edition_year(site: str) -> Optional[int]:
    """Année de l'édition servie par le site (dernier millésime du <title> de /fr/etape-1)."""
    if site not in _YEARS:
        txt = _page(SITES[site]["base"] + "/fr/etape-1")
        year = None
        if txt:
            m = re.search(r"<title[^>]*>(.*?)</title>", txt, re.S | re.I)
            years = re.findall(r"\b(20\d\d)\b", html.unescape(m.group(1))) if m else []
            year = int(years[-1]) if years else None
        _YEARS[site] = year
    return _YEARS[site]


def match_race(name: str, start_date: str) -> Optional[Dict[str, Any]]:
    """Référence ASO {"site","base","slug","year","label"} si la course est ASO ET si le site sert l'édition de
    `start_date` ; sinon None."""
    n = netutil.normalize(name)
    for key, s in SITES.items():
        if any(k in n for k in s["any"]) and not any(x in n.split() for x in s["none"]):
            try:
                year = int((start_date or "")[:4])
            except ValueError:
                return None
            served = edition_year(key)
            if served != year:
                print(f"[INFO] ASO {key} : édition servie {served}, demandée {year} ({name}) : pas d'enrichissement")
                return None
            return {"site": key, "base": s["base"], "slug": key, "year": year, "label": s["label"]}
    return None


# ---------------------------------------------------------------- tableaux de classement

class _Tables(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: List[Dict[str, Any]] = []
        self._t: Optional[Dict[str, Any]] = None
        self._row: Optional[Dict[str, Any]] = None
        self._cell: Optional[List[str]] = None
        self._is_th = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._t = {"head": [], "rows": []}
        elif tag == "tr" and self._t is not None:
            self._row = {"cells": [], "flag": None, "bib_attr": None, "team_code": None}
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._is_th = tag == "th"
        elif self._row is not None:
            dc = a.get("data-class") or ""
            if dc.startswith("flag--") and self._row["flag"] is None:
                self._row["flag"] = dc[6:].upper()
            if a.get("data-bib") and self._row["bib_attr"] is None:
                self._row["bib_attr"] = a["data-bib"].lstrip("#")
            m = re.match(r"/fr/equipe/([A-Za-z0-9]+)/", a.get("href") or "")
            if m and self._row["team_code"] is None:
                self._row["team_code"] = m.group(1)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            txt = " ".join("".join(self._cell).split())
            if self._is_th:
                if self._t is not None and not self._t["rows"]:
                    self._t["head"].append(txt)
            else:
                self._row["cells"].append(txt)
            self._cell = None
        elif tag == "tr" and self._row is not None and self._t is not None:
            if self._row["cells"]:
                self._t["rows"].append(self._row)
            self._row = None
        elif tag == "table" and self._t is not None:
            self.tables.append(self._t)
            self._t = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _duration(txt: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*h\s*(\d+)\s*'\s*(\d+)", txt or "")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None


def _seconds_tag(txt: str, letter: str) -> Optional[int]:
    m = re.search(r"\b%s\s*:\s*(\d+)" % letter, txt or "")
    return int(m.group(1)) if m else None


def parse_ranking_html(page: str) -> List[Dict[str, Any]]:
    """Tableau de classement ASO -> lignes normalisées. Colonnes repérées par leur libellé d'en-tête."""
    p = _Tables()
    try:
        p.feed(page)
    except Exception as e:  # HTML mal formé
        print(f"[WARN] ASO : HTML illisible ({e})")
    if not p.tables:
        return []
    table = max(p.tables, key=lambda t: len(t["rows"]))
    labels = [netutil.normalize(h) for h in table["head"]]
    idx = {}
    for i, lab in enumerate(labels):
        key = {"rang": "rank", "coureur": "name", "dossard": "bib", "equipe": "team", "temps": "time",
               "ecart": "gap", "b": "bonus", "p": "penalty", "points": "points"}.get(lab)
        if key and key not in idx:
            idx[key] = i
    out = []
    for r in table["rows"]:
        c = r["cells"]

        def cell(k: str) -> str:
            i = idx.get(k)
            return c[i] if i is not None and i < len(c) else ""
        rank_txt = cell("rank")
        bib_txt = cell("bib") or (r["bib_attr"] or "")
        time_s = _duration(cell("time"))
        gap_txt = cell("gap")
        gap_s = _duration(gap_txt) if gap_txt.strip("- ") else None
        rank = int(rank_txt) if rank_txt.isdigit() else None
        if rank == 1 and time_s is not None and gap_s is None:
            gap_s = 0
        pts = re.search(r"(\d+)\s*PTS", cell("points"), re.I)
        out.append({
            "rank": rank,
            "bib": int(bib_txt) if bib_txt.isdigit() else None,
            "name": cell("name") or None,
            "team": cell("team") or None,
            "nationality": r["flag"],
            "time_s": time_s,
            "gap_s": gap_s,
            "bonus_s": _seconds_tag(cell("bonus"), "B"),
            "penalty_s": _seconds_tag(cell("penalty"), "P"),
            "points": int(pts.group(1)) if pts else None,
        })
    return out


def get_classification(aso_ref: Dict[str, Any], stage_number: Optional[int], code: str) -> List[Dict[str, Any]]:
    """Classement ASO brut normalisé (liste vide si indisponible). `code` : ite itg ipg img ijg etg ice."""
    n = _stage_n(stage_number)
    page = _page(f"{aso_ref['base']}/fr/classements/etape-{n}/{code}")
    if page is None and n == 1 and code == "ite":
        page = _page(f"{aso_ref['base']}/fr/classements")
    if not page:
        return []
    try:
        return parse_ranking_html(page)
    except Exception as e:
        print(f"[WARN] ASO : classement {code} étape {n} illisible : {e}")
        return []


# ---------------------------------------------------------------- parcours

def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def _profile(word: str) -> Optional[str]:
    return PROFILES.get(netutil.normalize(word or ""))


def _num(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def parse_stage_route(page: str, n: int) -> Optional[Dict[str, Any]]:
    """Distance, profil, D+, cols et secteurs pavés d'une page /fr/etape-N. Champ introuvable -> None / []."""
    dist = elev = profile = None
    # Tour : bloc « Étape N … Longueur 171 km Type Montagne D+ 3750 m »
    flat = _text(re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I))
    m = re.search(r"[ÉE]tape\s+%d\b.{0,160}?Longueur\s+([\d.,]+)\s*km(?:\s+Type\s+(.+?))?(?:\s+D\+\s*(\d+)\s*m|\s+[A-Za-zÉé]{3,4}\.\s|$)"
                  % n, flat)
    if m:
        dist, profile = _num(m.group(1)), _profile((m.group(2) or "").strip())
        elev = int(m.group(3)) if m.group(3) else None
    if dist is None:
        # autres sites : <h2 class="pageHeader__subheading">15/03/2026 - Étape 8 - 129,2 km - Accidentée</h2>
        m = re.search(r'pageHeader__subheading[^>]*>(.*?)</h2>', page, re.S)
        if m:
            sub = _text(m.group(1))
            mk = re.search(r"([\d.,]+)\s*km(?:\s*-\s*(.+))?$", sub)
            if mk:
                dist, profile = _num(mk.group(1)), _profile((mk.group(2) or "").strip())
    # cols (blocs « mountain__item »)
    climbs = []
    for blk in page.split("mountain__item")[1:]:
        blk = blk[:1500]
        nm = re.search(r"<h3[^>]*>(.*?)</h3>", blk, re.S)
        km = re.search(r'class="km">\s*Km\s*([\d.,]+)\s*-\s*(\d+)\s*m', blk)
        pc = re.search(r'class="percent">\s*([\d.,]+)\s*km de mont[^<]*?([\d.,]+)\s*%', html.unescape(blk))
        cat = re.search(r'class="category">\s*([^<]+)<', blk)
        if not nm or not km:
            continue
        cat_txt = _text(cat.group(1)) if cat else ""
        mc = re.search(r"(\d)\s*$", cat_txt)
        climbs.append({
            "name": _text(nm.group(1)), "km": _num(km.group(1)),
            "category": mc.group(1) if mc else ("HC" if "hors" in cat_txt.lower() else None),
            "altitude_m": int(km.group(2)),
            "length_km": _num(pc.group(1)) if pc else None,
            "gradient_pct": _num(pc.group(2)) if pc else None,
        })
    uniq = {(c["name"], c["km"]): c for c in climbs}
    climbs = sorted(uniq.values(), key=lambda c: c["km"] or 0)
    # secteurs pavés : « Début du secteur pavé de X à Y (N° 30) » puis « Fin du secteur pavé 2174 m »
    cobbles: List[Dict[str, Any]] = []
    cur = None
    for tr in re.findall(r"<tr\b.*?</tr>", page, re.S | re.I):
        tds = [_text(x) for x in re.findall(r"<td\b.*?</td>", tr, re.S | re.I)]
        label = next((t for t in tds if "secteur pav" in t.lower()), "")
        if not label:
            continue
        mb = re.search(r"Début du secteur pavé de\s+(.*?)\s*\(N°\s*(\d+)\)", label, re.I)
        mf = re.search(r"Fin du secteur pavé\s+(\d+)\s*m", label, re.I)
        try:
            km_from_start = _num(tds[tds.index(label) + 2])
        except (ValueError, IndexError):
            km_from_start = None
        if mb:
            cur = {"name": mb.group(1), "km": km_from_start, "length_km": None, "difficulty": None}
        elif mf and cur is not None:
            cur["length_km"] = round(int(mf.group(1)) / 1000, 3)
            cobbles.append(cur)
            cur = None
    if dist is None and not climbs and not cobbles:
        return None
    return {"distance_km": dist, "elevation_m": elev, "profile": profile, "climbs": climbs,
            "cobbles": cobbles, "source": "aso"}


def get_route(aso_ref: Dict[str, Any], stage_number: Optional[int]) -> Optional[Dict[str, Any]]:
    n = _stage_n(stage_number)
    page = _page(f"{aso_ref['base']}/fr/etape-{n}")
    route = None
    try:
        route = parse_stage_route(page, n) if page else None
        if route is None or route["distance_km"] is None:
            route = _route_from_general(aso_ref, n, route)
    except Exception as e:
        print(f"[WARN] ASO : parcours étape {n} illisible : {e}")
    return route


def _route_from_general(aso_ref: Dict[str, Any], n: int, route: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Repli : tableau /fr/parcours-general (n° | type | date | départ > arrivée | distance)."""
    page = _page(f"{aso_ref['base']}/fr/parcours-general")
    if not page:
        return route
    p = _Tables()
    p.feed(page)
    for t in p.tables:
        for r in t["rows"]:
            c = r["cells"]
            if len(c) >= 5 and c[0].strip() == str(n):
                dist = _num((re.search(r"([\d.,]+)\s*km", c[4]) or [None, ""])[1])
                base = route or {"distance_km": None, "elevation_m": None, "profile": None, "climbs": [],
                                 "cobbles": [], "source": "aso"}
                base["distance_km"] = base["distance_km"] if base["distance_km"] is not None else dist
                base["profile"] = base["profile"] or _profile(c[1])
                return base if base["distance_km"] is not None else route
    return route


# ---------------------------------------------------------------- récit

def _article_text(page: str) -> str:
    txt = re.sub(r"<(script|style|noscript|svg|form)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    txt = re.sub(r'<div class="consentPlaceholder.*?</div>\s*</div>', " ", txt, flags=re.S)
    i = txt.find("article__content")
    if i < 0:
        i = txt.find("<article")
    if i >= 0:
        txt = txt[i:]
    j = re.search(r"</article>|<footer|pushs--|class=\"pushs", txt[200:])
    if j:
        txt = txt[:200 + j.start()]
    txt = re.sub(r"</(p|div|h[1-6]|li|blockquote)>|<br\s*/?>", "\n", txt, flags=re.I)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", txt)).replace("\xa0", " ")
    lines = [" ".join(l.split()) for l in txt.splitlines()]
    bad = ("cookie", "consent", "__CONSENT", "Partager", "Lire aussi")
    return "\n".join(l for l in lines if len(l) >= 30 and not any(b in l for b in bad))


def get_story(aso_ref: Dict[str, Any], stage_number: Optional[int]) -> Optional[str]:
    """Texte brut des articles de récit de l'étape (jusqu'à 3, ~6000 caractères), ou None."""
    n = _stage_n(stage_number)
    page = _page(f"{aso_ref['base']}/fr/etape-{n}")
    if not page:
        return None
    links = []
    for u in re.findall(r'href="(/fr/actus/\d{4}/etape-%d/[^"#]+)"' % n, page):
        if u not in links:
            links.append(u)
    parts = []
    for u in links[:3]:
        art = _page(aso_ref["base"] + u)
        if not art:
            continue
        t = _article_text(art)
        title = re.search(r"<title[^>]*>(.*?)</title>", art, re.S)
        if len(t) >= 200:
            parts.append((_text(title.group(1)) + "\n" if title else "") + t)
    text = "\n\n".join(parts)[:6000]
    return text or None


# ---------------------------------------------------------------- enrichissement

def _name_matches(aso_name: str, rider_id: str) -> bool:
    """« T. POGACAR » / « JONAS VINGEGAARD » contre un id « pogacar-tadej-19980921 »."""
    ids = [t for t in (rider_id or "").split("-") if not t.isdigit()]
    toks = netutil.normalize(aso_name).split()
    if not toks or not ids:
        return False
    full = [t for t in toks if len(t) > 1]
    initials = [t for t in toks if len(t) == 1]
    if not full or not all(t in ids for t in full):
        return False
    rest = [t for t in ids if t not in full]
    return all(any(t.startswith(i) for t in rest) for i in initials)


def _index_rows(rows: List[Dict[str, Any]], aso_rows: List[Dict[str, Any]]) -> List[tuple]:
    by_bib = {r["bib"]: r for r in aso_rows if r["bib"] is not None}
    pairs = []
    for row in rows:
        a = by_bib.get(row.get("bib")) if row.get("bib") is not None else None
        if a is None:
            a = next((x for x in aso_rows if x["name"] and _name_matches(x["name"], row.get("rider_id") or "")), None)
        if a is not None:
            pairs.append((row, a))
    return pairs


def _fill(row: Dict[str, Any], key: str, value: Optional[int], ctx: str) -> bool:
    if value is None:
        return False
    cur = row.get(key)
    if cur is None:
        row[key] = value
        return True
    if cur != value:
        print(f"[DIVERGENCE] {ctx} {row.get('rider_id')} {key} : UCI {cur} / ASO {value} (UCI conservé)")
    return False


def enrich_stage(aso_ref: Dict[str, Any], stage_number: Optional[int], stage: Dict[str, Any]) -> None:
    """Complète `stage` en place : bonifications / pénalités (étape et général), classement par équipes manquant,
    parcours. Ne remplace jamais une valeur UCI différente ([DIVERGENCE])."""
    res = stage.setdefault("results", {})
    ctx = f"{aso_ref.get('site')} étape {stage_number}"
    for key, code in (("stage", "ite"), ("gc", "itg")):
        rows = res.get(key) or []
        if not rows:
            continue
        aso_rows = get_classification(aso_ref, stage_number, code)
        if not aso_rows:
            continue
        filled = 0
        for row, a in _index_rows(rows, aso_rows):
            filled += _fill(row, "bonus_s", a["bonus_s"], ctx + " " + key)
            filled += _fill(row, "penalty_s", a["penalty_s"], ctx + " " + key)
            if a["time_s"] is not None and row.get("time_s") is not None and key == "stage" and row["rank"] == a["rank"] == 1 \
                    and row["time_s"] != a["time_s"]:
                print(f"[DIVERGENCE] {ctx} vainqueur temps : UCI {row['time_s']} / ASO {a['time_s']}")
        print(f"[ASO] {ctx} {code} : {len(aso_rows)} lignes ASO, {filled} valeurs bonus/pénalité ajoutées")
    if not res.get("teams"):
        teams = get_classification(aso_ref, stage_number, "etg")
        if teams:
            res["teams"] = [{"rank": t["rank"], "team": t["team"], "nationality": None, "time_s": t["time_s"],
                             "gap_s": t["gap_s"]} for t in teams]
    route = get_route(aso_ref, stage_number)
    if route:
        cur = stage.get("route")
        if not cur:
            stage["route"] = route
        else:
            for k, v in route.items():
                if cur.get(k) in (None, [], "") and v not in (None, []):
                    cur[k] = v
                elif k in ("distance_km", "elevation_m") and cur.get(k) not in (None, v) and v is not None:
                    print(f"[DIVERGENCE] {ctx} route.{k} : existant {cur.get(k)} / ASO {v} (existant conservé)")
