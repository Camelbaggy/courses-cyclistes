#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orchestration de la collecte : sélection des courses de la saison (UCI + LNC), récupération des
résultats UCI, enrichissement (ASO, récits), résumés, calculs dérivés déterministes, écriture de
data/index.json et data/races/<id>.json (voir docs/SPEC.md §4).

Les fichiers de course sont conservés d'un passage à l'autre : seules les courses nouvelles, en cours ou
terminées depuis moins de REFRESH_DAYS jours sont recollectées."""

import copy
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import agents_flash
import aso
import cyclingnews
import directvelo
import lnc
import netutil
import riders
import selection
import uci
import uci_ranking
import wikipedia_cal

DATA_DIR = "data"
RACES_DIR = os.path.join(DATA_DIR, "races")
REFRESH_DAYS = 3          # une course terminée est recollectée pendant ce nombre de jours (corrections UCI)
NOTIFY_DAYS = 2           # seules les nouveautés de moins de 2 jours déclenchent un push (pas le rattrapage)
AI_DAYS = 3               # Gemini seulement pour les étapes récentes ; repli déterministe pour l'historique
LATEST_COUNT = 20
SUMMARY_KEYS = ("id", "name", "country", "flag", "uci_class", "category", "race_type", "start_date",
                "end_date", "status", "stages_done", "stages_total", "selection_reason", "winner", "leader",
                "best_french", "sources")
TOP10_CLASSES = ("1.1", "2.1", "1.2", "2.2")
ARCHIVES_DIR = os.path.join(DATA_DIR, "archives")   # saisons passées compactées (data/archives/<année>/…)
RACINE = os.path.dirname(os.path.abspath(__file__))
ALIAS_COURSES = os.path.join(RACINE, "alias_courses.json")      # {"clé source": "clé canonique"} : manuel, jamais deviné
ALIAS_COUREURS = os.path.join(RACINE, "alias_coureurs.json")    # {"rider_id source": "rider_id canonique"} : idem
ANNEX_TOP = 30            # archives : lignes conservées dans les classements annexes (hors dernière étape)


# --------------------------------------------------------------------------- utilitaires fichiers

def _load(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _dump(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def _date(s: Optional[str]) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(s) if s else None
    except ValueError:
        return None


def _dump_if_changed(path: str, data: Dict, ignore: Tuple[str, ...] = ("generated_at",)) -> bool:
    """Écrit `data` seulement si son contenu (hors clés `ignore`) diffère du fichier existant : pas de commit vide."""
    old = _load(path, None)
    if isinstance(old, dict) and {k: v for k, v in old.items() if k not in ignore} == \
            {k: v for k, v in data.items() if k not in ignore}:
        return False
    _dump(path, data)
    return True


def _ranking_du_jour(today: dt.date) -> Optional[Dict]:
    """Classement UCI (module uci_ranking, s'il existe), mis en cache dans data/ranking.json et rafraîchi une fois
    par jour seulement. Aucun classement : None (les fiches affichent « non publié »)."""
    path = os.path.join(DATA_DIR, "ranking.json")
    cached = _load(path, None)
    if cached and cached.get("_fetched") == today.isoformat():
        return cached
    try:
        import uci_ranking
        ranking = uci_ranking.get_ranking()
    except Exception as e:  # source secondaire : jamais bloquante
        print(f"[WARN] classement UCI indisponible : {e}")
        ranking = None
    if ranking and ranking.get("rows"):
        ranking["_fetched"] = today.isoformat()
        _dump(path, ranking)
        return ranking
    return cached


ROTATION_DELAI_JOURS = 14   # une saison S est archivée quand S+1 est terminée depuis plus de 14 jours


def fin_de_saison_index(index: Optional[Dict]) -> Optional[dt.date]:
    """Date de fin de la dernière course d'un index de saison : max des `end_date` (à défaut `start_date`) des
    courses courues et des courses à venir. Index absent, vide ou sans date exploitable : None (rien n'est deviné)."""
    if not isinstance(index, dict):
        return None
    dates = []
    for r in list(index.get("races") or []) + list(index.get("upcoming") or []):
        d = _date((r.get("end_date") or r.get("start_date")) if isinstance(r, dict) else None)
        if d:
            dates.append(d)
    return max(dates) if dates else None


def saisons_a_archiver(seasons_dispo: List[int], index_par_saison: Dict[int, Dict], today: dt.date) -> List[int]:
    """Rotation du calendrier vers les archives : une saison S de `seasons_dispo` est à archiver quand la saison S+1
    est terminée, c'est-à-dire quand `today` dépasse de plus de ROTATION_DELAI_JOURS la fin de la dernière course
    (courue ou à venir) de l'index de S+1. Une course à venir encore dans le futur, un index de S+1 absent ou vide :
    pas de rotation. Fonction pure, résultat trié par ordre croissant."""
    out = []
    for s in sorted(set(seasons_dispo)):
        ix = index_par_saison.get(s + 1)
        fin = fin_de_saison_index(ix)
        if fin is None:
            continue
        if any((_date(u.get("end_date") or u.get("start_date")) or dt.date.min) >= today
               for u in (ix.get("upcoming") or []) if isinstance(u, dict)):
            continue
        if today > fin + dt.timedelta(days=ROTATION_DELAI_JOURS):
            out.append(s)
    return out


def write_riders_files(seasons: List[int], current: int, by_season: Dict[int, List[Dict]],
                       today: dt.date) -> None:
    """Fiches coureurs (data/riders-<année>.json) : saison courante recalculée à chaque passage avec le classement
    UCI du jour (ainsi que la suivante pendant l'intersaison) ; saisons passées calculées une seule fois."""
    ranking = _ranking_du_jour(today)
    for y in seasons:
        path = os.path.join(DATA_DIR, f"riders-{y}.json")
        if y < current and os.path.exists(path):
            continue
        data = riders.build_riders(by_season.get(y, []), ranking if y >= current else None, season=y)
        _dump_if_changed(path, data)


def write_season_indexes(current: int, computed: Dict[int, Dict], today: Optional[dt.date] = None) -> None:
    """Un index par saison (data/index-<année>.json) pour le calendrier de la page, plus data/seasons.json.
    Les saisons calculées ce passage (`computed`, dont la courante et, pendant l'intersaison, la suivante) sont écrites
    telles quelles ; les saisons passées sont reconstruites depuis leurs fichiers de course (conservés), sans
    calendrier à venir, en gardant leur dernier classement FDJ connu. Les saisons à archiver (`saisons_a_archiver`) ne
    sont plus listées (`seasons.json.available`) ni réécrites : elles rejoignent les archives
    (`migrer_saisons_anciennes`), leurs fichiers restent en place jusqu'à la migration."""
    if not isinstance(computed, dict) or "races" in computed:   # compatibilité : un seul index (saison courante)
        computed = {current: computed}
    by_season: Dict[int, List[Dict]] = {}
    for fname in os.listdir(RACES_DIR):
        if fname.endswith(".json"):
            r = _load(os.path.join(RACES_DIR, fname), None)
            if r and isinstance(r.get("season"), int):
                by_season.setdefault(r["season"], []).append(r)
    candidates = sorted({y for y in by_season if y <= current} | set(computed), reverse=True)
    today = today or dt.date.today()
    indexes: Dict[int, Dict] = {}
    for y in candidates:
        if y in computed:
            indexes[y] = computed[y]
        else:
            old = _load(os.path.join(DATA_DIR, f"index-{y}.json"), {})
            indexes[y] = build_index(by_season.get(y, []), y, [], old.get("fdj_united_series"))
    # Rotation : une saison S quitte le calendrier quand S+1 est terminée depuis plus de 14 jours (voir
    # saisons_a_archiver) ; ses fichiers restent en place jusqu'à la migration (migrer_saisons_anciennes).
    for y in range(min(candidates, default=current), current + 2):   # S+1 d'une saison présente
        if y not in indexes:
            ix = _load(os.path.join(DATA_DIR, f"index-{y}.json"), None)
            if ix:
                indexes[y] = ix
    a_archiver = set(saisons_a_archiver([y for y in candidates if y < current], indexes, today))
    seasons = [y for y in candidates if y not in a_archiver]
    for y in seasons:
        _dump_if_changed(os.path.join(DATA_DIR, f"index-{y}.json"), indexes[y])
    write_riders_files(seasons, current, by_season, today)
    _dump_if_changed(os.path.join(DATA_DIR, "seasons.json"), {"current": current, "available": seasons}, ignore=())


def race_path(race_id: str) -> str:
    return os.path.join(RACES_DIR, f"{race_id}.json")


# --------------------------------------------------------------------------- calculs dérivés

def _ref(race: Dict, rider_id: Optional[str]) -> Optional[Dict]:
    return (race.get("riders") or {}).get(rider_id) if rider_id else None


def _first(rows: List[Dict]) -> Optional[Dict]:
    for r in rows or []:
        if r.get("rank") == 1:
            return r
    return None


def _main_classif(stage: Dict, race_type: str) -> List[Dict]:
    return (stage.get("results") or {}).get("stage") or []


def _gc_after(race: Dict, idx: int) -> List[Dict]:
    """Général après l'étape idx ; pour la dernière étape d'une course terminée, repli sur le final."""
    gc = ((race["stages"][idx].get("results") or {}).get("gc")) or []
    if not gc and idx == len(race["stages"]) - 1 and race.get("final"):
        gc = race["final"].get("gc") or []
    return gc


def _french(race: Dict, row: Dict) -> bool:
    ref = _ref(race, row.get("rider_id"))
    return bool(ref and ref.get("is_french"))


def _best_french_row(race: Dict, rows: List[Dict]) -> Optional[Dict]:
    ranked = [r for r in rows if r.get("rank") and _french(race, r)]
    return min(ranked, key=lambda r: r["rank"]) if ranked else None


def compute_stage_highlights(race: Dict, idx: int) -> List[Dict]:
    """Français du top 20 de l'étape ou du top 20 du général (rangs et écarts tels que publiés)."""
    stage = race["stages"][idx]
    st_rows = _main_classif(stage, race["race_type"])
    gc_rows = _gc_after(race, idx) if race["race_type"] == "stage_race" else []
    st_rank = {r["rider_id"]: r for r in st_rows if r.get("rank")}
    gc_rank = {r["rider_id"]: r for r in gc_rows if r.get("rank")}
    ids = [rid for rid, r in st_rank.items() if r["rank"] <= 20] + \
          [rid for rid, r in gc_rank.items() if r["rank"] <= 20]
    out, seen = [], set()
    for rid in ids:
        if rid in seen or not (_ref(race, rid) or {}).get("is_french"):
            continue
        seen.add(rid)
        out.append({
            "rider": _ref(race, rid),
            "stage_rank": (st_rank.get(rid) or {}).get("rank"),
            "gc_rank": (gc_rank.get(rid) or {}).get("rank"),
            "gc_gap_s": (gc_rank.get(rid) or {}).get("gap_s"),
        })
    out.sort(key=lambda h: (h["stage_rank"] or 999, h["gc_rank"] or 999))
    return out


def finalize_race(race: Dict, today: dt.date) -> None:
    """Statut, vainqueur, leader, meilleur Français (déterministe, depuis les classements publiés)."""
    stages = race.get("stages") or []
    race["stages_done"] = len(stages)
    end = _date(race.get("end_date"))
    finished = bool(race.get("final")) or (end is not None and end < today)
    race["status"] = "finished" if finished else "in_progress"
    race["winner"] = race["leader"] = race["best_french"] = None
    if not stages:
        return
    if race["race_type"] == "one_day":
        rows = (race.get("final") or {}).get("stage") or _main_classif(stages[-1], "one_day")
        win = _first(rows)
        race["winner"] = _ref(race, win["rider_id"]) if win else None
        bf = _best_french_row(race, rows)
        if bf:
            race["best_french"] = {"rider": _ref(race, bf["rider_id"]), "rank": bf["rank"], "classification": "stage"}
    else:
        gc = _gc_after(race, len(stages) - 1)
        lead = _first(gc)
        if lead:
            race["leader"] = _ref(race, lead["rider_id"])
            if finished:
                race["winner"] = race["leader"]
        bf = _best_french_row(race, gc)
        if bf:
            race["best_french"] = {"rider": _ref(race, bf["rider_id"]), "rank": bf["rank"], "classification": "gc"}
    for i in range(len(stages)):
        stages[i]["french_highlights"] = compute_stage_highlights(race, i)


def stage_key(race: Dict, idx: int) -> str:
    st = race["stages"][idx]
    return f"{race['id']}:{'F' if st.get('number') is None else st['number']}"


def stage_label(st: Dict) -> str:
    if st.get("number") is None:
        return "Course"
    lab = st.get("name") or (f"Étape {st['number']}" if st["number"] else "Prologue")
    if st.get("start") and st.get("finish"):
        lab += f" · {st['start']} → {st['finish']}"
    return lab


def _stage_fingerprint(st: Dict) -> Tuple:
    rows = (st.get("results") or {}).get("stage") or []
    return (len(rows), tuple((r.get("rider_id"), r.get("rank")) for r in rows[:5]))


# --------------------------------------------------------------------------- collecte d'une course

def _stories(race: Dict, idx: int, aso_ref: Optional[Dict], cn_items: List[Dict]) -> List[str]:
    st = race["stages"][idx]
    out = []
    if aso_ref:
        txt = aso.get_story(aso_ref, st.get("number"))
        if txt:
            out.append(txt)
    if race.get("country") == "FRA" and race["category"] not in ("WT",):
        txt = directvelo.find_story(race["name"], st.get("date"))
        if txt:
            out.append(txt)
    txt = cyclingnews.find_story(cn_items, race["name"], st.get("date"), st.get("number"))
    if txt:
        out.append(txt)
    return out


def collect_race(comp: Dict, category: str, reason: str, previous: Optional[Dict], today: dt.date,
                 cn_items: List[Dict], fetched: Optional[Dict] = None, archive: bool = False) -> Optional[Dict]:
    """`archive` : saison passée (mode archives) : ni ASO, ni récits, ni Gemini ; résumé de repli déterministe."""
    data = fetched if fetched is not None else uci.get_race(comp)
    if not data or not data.get("stages"):
        print(f"[WARN] {comp['name']} : aucun résultat UCI exploitable")
        return previous
    race_type = data.get("race_type") or ("one_day" if len(data["stages"]) == 1 else "stage_race")
    race = {
        "id": f"uci-{comp['competition_id']}", "name": comp["name"], "country": comp.get("country"),
        "flag": comp.get("flag"), "uci_class": comp.get("uci_class"), "category": category,
        "race_type": race_type,
        "start_date": comp.get("start_date"), "end_date": comp.get("end_date"),
        "stages_total": data.get("stages_total"), "selection_reason": reason, "sources": ["uci"],
        "stages": data["stages"],
        # course d'un jour : uci.py fait pointer `final` vers stages[0].results -> inutile de le dupliquer
        "final": None if race_type == "one_day" else data.get("final"),
        "riders": data.get("riders") or {}, "_complete": data.get("complete", True),
    }
    aso_ref = None if archive else aso.match_race(race["name"], race["start_date"])
    prev_stages = {s.get("number"): s for s in (previous or {}).get("stages") or []}
    for idx, st in enumerate(race["stages"]):
        old = prev_stages.get(st.get("number"))
        if old and old.get("route") and not st.get("route"):
            st["route"] = old["route"]
        if aso_ref and not (old and old.get("_aso_done")):
            aso.enrich_stage(aso_ref, st.get("number"), st)
            st["_aso_done"] = True
            if "aso" not in race["sources"]:
                race["sources"].append("aso")
        elif old and old.get("_aso_done"):
            st["_aso_done"] = True
            if "aso" not in race["sources"]:
                race["sources"].append("aso")
    finalize_race(race, today)

    # Résumés : conservés si l'étape n'a pas changé ; Gemini seulement pour les étapes récentes.
    for idx, st in enumerate(race["stages"]):
        old = prev_stages.get(st.get("number"))
        # Seuls les résumés Gemini sont conservés ; le repli déterministe est toujours recalculé (gratuit).
        if archive:
            txt, src = agents_flash.build_fallback_summary(race, idx), "fallback"
            st["ai_summary"], st["summary_source"] = (txt, src) if txt else (None, None)
            continue
        if old and old.get("ai_summary") and old.get("summary_source") == "gemini" \
                and _stage_fingerprint(old) == _stage_fingerprint(st):
            st["ai_summary"], st["summary_source"] = old["ai_summary"], old.get("summary_source")
            continue
        if _is_recent(st, today, AI_DAYS):
            stories = _stories(race, idx, aso_ref, cn_items)
            txt, src = agents_flash.summarize_stage(race, idx, stories)
        else:
            txt, src = agents_flash.build_fallback_summary(race, idx), "fallback"
        st["ai_summary"], st["summary_source"] = (txt, src) if txt else (None, None)
    race["updated_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return race


def _is_recent(st: Dict, today: dt.date, days: int) -> bool:
    d = _date(st.get("date"))
    return d is not None and (today - d).days <= days


def _needs_refresh(comp: Dict, previous: Optional[Dict], today: dt.date) -> bool:
    if previous is None:
        return True
    end = _date(comp.get("end_date"))
    return (end is None or (today - end).days <= REFRESH_DAYS or previous.get("status") != "finished"
            or previous.get("_complete") is False)


# --------------------------------------------------------------------------- index

def build_index(races: List[Dict], season: int, upcoming: List[Dict], fdj: Optional[Dict]) -> Dict:
    races = sorted(races, key=lambda r: (r.get("start_date") or "", r["name"]))
    latest, wins = [], []
    for race in races:
        for idx, st in enumerate(race.get("stages") or []):
            win = _first(_main_classif(st, race["race_type"]))
            if not win:
                continue
            ref = _ref(race, win["rider_id"])
            bf = _best_french_row(race, _main_classif(st, race["race_type"]))
            latest.append({
                "race_id": race["id"], "race_name": race["name"], "stage_number": st.get("number"),
                "date": st.get("date"), "label": stage_label(st), "winner": ref,
                "best_french": {"rider": _ref(race, bf["rider_id"]), "rank": bf["rank"]} if bf else None,
                "ai_summary": st.get("ai_summary"),
            })
            if ref and ref.get("is_french"):
                wins.append({"date": st.get("date"), "race_id": race["id"], "stage_number": st.get("number"),
                             "rider": ref["name"], "rider_id": ref["id"], "race_name": race["name"],
                             "label": stage_label(st)})
        if race["race_type"] == "stage_race" and race.get("status") == "finished" and \
                (race.get("winner") or {}).get("is_french"):
            w = race["winner"]
            wins.append({"date": race.get("end_date"), "race_id": race["id"], "stage_number": None,
                         "rider": w["name"], "rider_id": w["id"], "race_name": race["name"],
                         "label": "Classement général final"})
    latest.sort(key=lambda x: (x["date"] or "", x["stage_number"] or 0), reverse=True)
    wins.sort(key=lambda x: x["date"] or "", reverse=True)
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season,
        "races": [{k: r.get(k) for k in SUMMARY_KEYS} for r in races],
        "upcoming": upcoming,
        "latest": latest[:LATEST_COUNT],
        "fdj_united_series": fdj,
        "french_wins": wins,
        "notification": {"send": False, "title": "", "message": ""},
    }


# --------------------------------------------------------------------------- point d'entrée

def _saison_de(date_iso: Optional[str]) -> Optional[int]:
    """Saison UCI d'une date (bornes officielles) ; repli : année civile, ou la suivante après le 18 octobre."""
    if not date_iso:
        return None
    y = uci.season_for(date_iso)
    if y:
        return y
    d = _date(date_iso)
    return d.year + 1 if d and (d.month, d.day) > (10, 18) else (d.year if d else None)


def run(season: Optional[int], today: Optional[dt.date] = None, only: str = "", max_races: int = 0,
        budget_min: float = 0) -> Dict:
    """Collecte la saison affichée et, pendant l'intersaison (nouvelle saison UCI commencée mais sans course
    WT / Pro / FDJ courue), aussi la nouvelle saison, proposée dans le calendrier sans être affichée par défaut.
    budget_min > 0 : au-delà de ce temps, plus aucune nouvelle course n'est collectée ; le passage suivant reprend."""
    today = today or dt.date.today()
    t0 = time.monotonic()

    def over_budget() -> bool:
        return bool(budget_min) and (time.monotonic() - t0) / 60 > budget_min
    os.makedirs(RACES_DIR, exist_ok=True)
    state = _load(os.path.join(DATA_DIR, "state.json"), {})
    notified = set(state.get("notified") or [])
    top10_cache = state.get("top10_checked") or {}   # competition_id -> bool (courses terminées seulement)

    fdj = lnc.get_fdj_united_series()
    fdj_races = (fdj or {}).get("races") or []

    # Saisons à collecter : [saison affichée] (+ la nouvelle pendant l'intersaison)
    plan: List[Tuple[int, List[Dict]]] = []
    if season:
        sid = uci.get_season_id(season)
        if sid is None:
            raise SystemExit(f"[ERREUR] Saison UCI {season} introuvable")
        plan.append((season, uci.list_competitions(sid)))
    else:
        s0 = uci.season_for(today) or today.year
        sid = uci.get_season_id(s0)
        if sid is None:
            raise SystemExit(f"[ERREUR] Saison UCI {s0} introuvable")
        comps0 = uci.list_competitions(sid)
        majeures = [p for p in selection.select(comps0, fdj_races) if p[1] in ("WT", "Pro", "FDJ")]
        if majeures:
            plan.append((s0, comps0))
        else:
            print(f"[SAISON] aucune course WT/Pro/FDJ courue en {s0} : saison {s0 - 1} affichée, {s0} collectée aussi")
            sid_prec = uci.get_season_id(s0 - 1)
            plan.append((s0 - 1, uci.list_competitions(sid_prec) if sid_prec else []))
            plan.append((s0, comps0))
    season = plan[0][0]
    for y, comps in plan:
        print(f"[UCI] {len(comps)} courses hommes élite courues ou en cours en {y}")

    cn_items = cyclingnews.fetch_items()
    races_by_season: Dict[int, Dict[str, Dict]] = {y: {} for y, _ in plan}
    new_items: List[Tuple[Dict, int]] = []
    stopped = False
    count = 0

    for y, comps in plan:
        races = races_by_season[y]
        picked = selection.select(comps, fdj_races)
        # Une manche FDJ United Series est rangée en « FDJ » même si sa classe (1.Pro) la retenait déjà,
        # et l'index relie chaque manche à sa fiche.
        for i, (comp, category, reason) in enumerate(picked):
            manche = selection.match_fdj(comp, fdj_races)
            if manche is not None:
                picked[i] = (comp, "FDJ", "fdj")
                manche["race_id"] = f"uci-{comp['competition_id']}"
        picked_ids = {c["competition_id"] for c, _, _ in picked}
        if only:
            picked = [p for p in picked if only.lower() in p[0]["name"].lower()]
        print(f"[SELECTION] {y} : {len(picked)} courses retenues d'office")

        def handle(comp: Dict, category: str, reason: str, fetched: Optional[Dict] = None) -> None:
            rid = f"uci-{comp['competition_id']}"
            previous = _load(race_path(rid), None)
            if fetched is None and not _needs_refresh(comp, previous, today):
                if previous.get("category") != category or previous.get("selection_reason") != reason \
                        or previous.get("season") != y:
                    previous["category"], previous["selection_reason"], previous["season"] = category, reason, y
                    _dump(race_path(rid), previous)
                races[rid] = previous
                return
            print(f"[COURSE] {comp['name']} ({comp.get('uci_class')}, {comp.get('start_date')})")
            race = collect_race(comp, category, reason, previous, today, cn_items, fetched)
            if not race:
                return
            race["season"] = y
            races[rid] = race
            _dump(race_path(rid), race)
            for idx in range(len(race["stages"])):
                key = stage_key(race, idx)
                if key not in notified:
                    notified.add(key)
                    if _is_recent(race["stages"][idx], today, NOTIFY_DAYS):
                        new_items.append((race, idx))

        # les plus récentes d'abord : ce sont elles qui comptent si le budget de temps est atteint
        picked.sort(key=lambda p: p[0].get("start_date") or "", reverse=True)
        for comp, category, reason in picked:
            if over_budget():
                stopped = True
                break
            handle(comp, category, reason)
            count += 1
            if max_races and count >= max_races:
                break

        # .1 / .2 hors de France : retenues si un Français termine dans les 10 premiers.
        if not only and not stopped and not (max_races and count >= max_races):
            for comp in sorted(comps, key=lambda c: c.get("start_date") or "", reverse=True):
                if over_budget():
                    stopped = True
                    break
                if comp["competition_id"] in picked_ids or comp.get("uci_class") not in TOP10_CLASSES:
                    continue
                cid = str(comp["competition_id"])
                rid = f"uci-{cid}"
                if top10_cache.get(cid) is False:
                    continue
                previous = _load(race_path(rid), None)
                if previous and not _needs_refresh(comp, previous, today):
                    races[rid] = previous
                    continue
                data = uci.get_race(comp)
                if not data or not data.get("stages"):
                    continue
                probe = {"stages": data["stages"], "final": data.get("final"), "riders": data.get("riders") or {},
                         "race_type": data.get("race_type")}
                ok = selection.french_top10(probe)
                end = _date(comp.get("end_date"))
                if end and (today - end).days > REFRESH_DAYS and data.get("complete", True):
                    top10_cache[cid] = ok
                if ok:
                    cat = "." + comp["uci_class"].split(".")[1][0]
                    handle(comp, cat, "francais_top10", fetched=data)

    # Calendrier prévisionnel : Wikipédia (EN + FR), complété par les manches FDJ de la LNC ; réparti par saison UCI.
    try:
        upcoming = wikipedia_cal.list_upcoming(today)
    except Exception as e:  # une source secondaire ne doit jamais faire échouer le passage
        print(f"[WARN] calendrier Wikipédia indisponible : {e}")
        upcoming = []
    upcoming_by_season: Dict[int, List[Dict]] = {}
    for u in upcoming:
        upcoming_by_season.setdefault(_saison_de(u.get("start_date")) or season, []).append(u)
    print(f"[CALENDRIER] à venir par saison : " + ", ".join(f"{y} : {len(v)}" for y, v in sorted(upcoming_by_season.items())))

    # Fichiers de courses non revus ce passage : gardés dans l'index de leur saison
    if not only:
        for fname in os.listdir(RACES_DIR):
            rid = fname[:-5]
            if not fname.endswith(".json"):
                continue
            for y, races in races_by_season.items():
                if rid not in races:
                    prev = _load(os.path.join(RACES_DIR, fname), None)
                    if prev and prev.get("season") == y:
                        races[rid] = prev
    indexes = {y: build_index(list(r.values()), y, upcoming_by_season.get(y, []), fdj if y == season else None)
               for y, r in races_by_season.items()}
    # Saison suivante sans aucune course collectée mais avec un calendrier publié : proposée quand même
    for y, ups in upcoming_by_season.items():
        if y > season and y not in indexes:
            indexes[y] = build_index([], y, ups, None)
    index = indexes[season]
    if new_items:
        index["notification"] = agents_flash.build_notification(new_items)
    if not only:
        write_season_indexes(season, indexes, today)
    # Rien de neuf (hors horodatage) : fichiers inchangés, donc pas de commit inutile à chaque passage horaire.
    old_index = _load(os.path.join(DATA_DIR, "index.json"), {})
    unchanged = {k: v for k, v in old_index.items() if k != "generated_at"} == \
                {k: v for k, v in index.items() if k != "generated_at"}
    new_state = dict(state, notified=sorted(notified), top10_checked=top10_cache)
    if unchanged and {k: v for k, v in new_state.items() if k != "last_run"} == \
            {k: v for k, v in state.items() if k != "last_run"}:
        print("[INFO] aucune donnée nouvelle : index et état inchangés")
    else:
        _dump(os.path.join(DATA_DIR, "index.json"), index)
        new_state["last_run"] = index["generated_at"]
        _dump(os.path.join(DATA_DIR, "state.json"), new_state)
    if stopped:
        print(f"[BUDGET] budget de {budget_min:.0f} min atteint : collecte interrompue, reprise au prochain passage")
    print(f"[FIN] saison {season} : {len(races_by_season[season])} courses ; saisons dans le calendrier : "
          f"{sorted(indexes, reverse=True)} ; {len(new_items)} nouveauté(s) à notifier")
    return index


# --------------------------------------------------------------------------- mode archives (saisons passées)

def _sans_none(d: Dict) -> Dict:
    return {k: v for k, v in d.items() if v is not None}


def _compacter_classements(res: Optional[Dict], tronquer: bool) -> Optional[Dict]:
    """Classements d'une étape ou du final : lignes sans clé à None ; annexes (hors « stage » et « gc ») tronquées
    au top ANNEX_TOP si `tronquer`."""
    if not isinstance(res, dict):
        return res
    out = {}
    for nom, lignes in res.items():
        if isinstance(lignes, list):
            if tronquer and nom not in ("stage", "gc"):
                lignes = lignes[:ANNEX_TOP]
            lignes = [_sans_none(r) if isinstance(r, dict) else r for r in lignes]
        out[nom] = lignes
    return out


def compact_race(race: Dict) -> Dict:
    """Version compacte d'une fiche course pour les archives (copie profonde, `race` n'est pas modifié) : clés à None
    supprimées (absent = null), classements annexes tronqués à ANNEX_TOP lignes sauf à la dernière étape, `final`
    complet, clés internes `_aso_done` supprimées. Le schéma reste celui de data/races/<id>.json."""
    out = copy.deepcopy(race)
    stages = out.get("stages") or []
    for i, st in enumerate(stages):
        st.pop("_aso_done", None)
        if "results" in st:
            st["results"] = _compacter_classements(st["results"], tronquer=(i != len(stages) - 1))
    if out.get("final"):
        out["final"] = _compacter_classements(out["final"], tronquer=False)
    out["riders"] = {rid: (_sans_none(r) if isinstance(r, dict) else r) for rid, r in (out.get("riders") or {}).items()}
    return out


TEMPS_VERSION = 2   # 2 : formats « h ' '' » et « H M S » reconnus (uci.parse_duree) ; marque `_temps_v` des archives écrites


def _classement_sans_temps(lignes: Any) -> bool:
    """Vrai si un classement compacté contient une ligne classée (rang entier, sans statut) sans `time_s`."""
    for r in lignes if isinstance(lignes, list) else []:
        if (isinstance(r, dict) and isinstance(r.get("rank"), int) and not isinstance(r.get("rank"), bool)
                and not r.get("status") and r.get("time_s") is None):
            return True
    return False


def archive_a_recollecter(race: Dict) -> bool:
    """Fiche d'archive compactée (clé absente = null) à recollecter parce que des temps manquent : un classement
    `stage` ou `gc` d'une étape route / contre-la-montre individuel (pas par équipes), ou du classement final, a une
    ligne classée sans `time_s`. Les fiches déjà recollectées avec le format de temps courant (`_temps_v` >=
    TEMPS_VERSION) ne le sont pas à nouveau : un format qui reste illisible ne provoque pas de recollecte sans fin."""
    if not isinstance(race, dict) or (race.get("_temps_v") or 0) >= TEMPS_VERSION:
        return False
    classements = [(st.get("results") or {}) for st in race.get("stages") or []
                   if isinstance(st, dict) and st.get("type", "road") in ("road", "itt")]
    classements.append(race.get("final") or {})
    return any(_classement_sans_temps(res.get(cle)) for res in classements if isinstance(res, dict)
               for cle in ("stage", "gc"))


def _taille_dossier(dossier: str) -> int:
    total = 0
    for racine, _, fichiers in os.walk(dossier):
        for f in fichiers:
            try:
                total += os.path.getsize(os.path.join(racine, f))
            except OSError:
                pass
    return total


def _fin_de_saison(annee: int) -> dt.datetime:
    """Instant de référence d'une saison close : fin officielle UCI de la saison, à défaut le 31/12."""
    fin = (uci.season_bounds().get(annee) or (None, None))[1]
    d = _date(fin) or dt.date(annee, 12, 31)
    return dt.datetime(d.year, d.month, d.day, 23, 59, tzinfo=dt.timezone.utc)


def charger_courses_archive(dossier: str) -> List[Dict]:
    """Fiches de course (compactées) déjà écrites pour une saison d'archive."""
    rdir = os.path.join(dossier, "races")
    if not os.path.isdir(rdir):
        return []
    sortie = []
    for f in sorted(os.listdir(rdir)):
        r = _load(os.path.join(rdir, f), None) if f.endswith(".json") else None
        if r:
            sortie.append(r)
    return sortie


def finish_archive_season(annee: int, dossier: str, courses: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Fin de saison : classement UCI de fin de saison (World Ranking, à défaut « WorldTour Ranking », groupe 3) dans
    `ranking.json`, puis fiches coureurs `riders.json` calculées à la date de fin de saison. Aucun classement
    disponible : pas de ranking.json (rien d'inventé), fiches sans rang UCI."""
    courses = charger_courses_archive(dossier) if courses is None else courses
    ranking = None
    for groupe in (uci_ranking.GROUPE_WORLD_RANKING, 3):
        try:
            ranking = uci_ranking.get_ranking(season_year=annee, group_id=groupe)
        except Exception as e:  # source secondaire : jamais bloquante
            print(f"[WARN] classement UCI {annee} (groupe {groupe}) indisponible : {e}")
            ranking = None
        if ranking and ranking.get("rows"):
            break
        ranking = None
    if ranking:
        _dump_if_changed(os.path.join(dossier, "ranking.json"), ranking, ignore=())
        print(f"[ARCHIVES] {annee} : classement « {ranking.get('name')} » ({len(ranking['rows'])} lignes)")
    else:
        print(f"[ARCHIVES] {annee} : aucun classement UCI de fin de saison disponible")
    fiches = riders.build_riders(courses, ranking, now=_fin_de_saison(annee), season=annee)
    _dump_if_changed(os.path.join(dossier, "riders.json"), fiches, ignore=())
    return {"ranking": ranking, "riders": fiches}


# --------------------------------------------------------------------------- éditions et carrières (archives)

def cle_edition(nom: Optional[str], pays: Optional[str]) -> Optional[str]:
    """Clé d'une « édition » d'une course : nom normalisé + « |PAYS ». Rapprochement EXACT sur cette clé, jamais flou.
    Nom en minuscules, sans accents, ponctuation (tirets, apostrophes…) remplacée par une espace, sans année
    (1900-2099) ni numéro d'édition isolé (« 107e », « 3rd »), espaces normalisées. Nom ou pays vide : None (pas de
    clé, donc aucun rapprochement). DOIT RESTER ALIGNÉE avec `cleEdition` de index.html."""
    pays = (pays or "").strip().upper()
    t = unicodedata.normalize("NFKD", nom or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    t = re.sub(r"[\W_]+", " ", t)
    mots = [m for m in t.split() if not (re.fullmatch(r"(19|20)\d\d", m) or re.fullmatch(r"\d+(e|er|ere|eme|th|st|nd|rd)", m))]
    if not mots or not pays:
        return None
    return " ".join(mots) + "|" + pays


def charger_alias(chemin: str) -> Dict[str, str]:
    """Fichier d'alias manuel {source: canonique}. Seules les paires texte -> texte, source != canonique, sont gardées ;
    pas de chaînage (une cible qui est elle-même une source est ignorée avec un avertissement)."""
    brut = _load(chemin, {})
    alias = {k: v for k, v in (brut.items() if isinstance(brut, dict) else [])
             if isinstance(k, str) and isinstance(v, str) and k and v and k != v}
    for k, v in list(alias.items()):
        if v in alias:
            print(f"[WARN] alias {os.path.basename(chemin)} : « {k} » -> « {v} » ignoré (la cible est elle-même un alias, pas de chaînage)")
            del alias[k]
    return alias


def _ref_reduit(ref: Optional[Dict]) -> Optional[Dict]:
    if not ref:
        return None
    return {k: ref.get(k) for k in ("id", "name", "nationality", "flag", "is_french") if ref.get(k) is not None}


def construire_editions(archives_dir: str, alias: Dict[str, str], now: Optional[str] = None) -> Dict:
    """editions.json : pour chaque clé d'édition (après alias), les éditions archivées, saison décroissante."""
    courses: Dict[str, List[Dict]] = {}
    if os.path.isdir(archives_dir):
        for nom in os.listdir(archives_dir):
            ix = _load(os.path.join(archives_dir, nom, "index.json"), None) if nom.isdigit() else None
            if not ix:
                continue
            for r in ix.get("races") or []:
                if r.get("status") not in (None, "finished"):
                    continue          # course en cours : pas encore une édition
                cle = cle_edition(r.get("name"), r.get("country"))
                if not cle or not r.get("id"):
                    continue
                cle = alias.get(cle, cle)
                bf = r.get("best_french")
                courses.setdefault(cle, []).append({
                    "season": int(nom), "race_id": r["id"], "name": r.get("name"), "uci_class": r.get("uci_class"),
                    "category": r.get("category"), "race_type": r.get("race_type"), "start_date": r.get("start_date"),
                    "winner": _ref_reduit(r.get("winner")),
                    "best_french": {"rider": _ref_reduit(bf.get("rider")), "rank": bf.get("rank"),
                                    "classification": bf.get("classification")} if bf and bf.get("rider") else None})
    for lst in courses.values():
        lst.sort(key=lambda e: (-e["season"], e.get("start_date") or "", e["race_id"]))
    return {"generated_at": now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "alias": alias, "courses": dict(sorted(courses.items()))}


def lettre_carriere(rider_id: str) -> str:
    c = (rider_id or "")[:1]
    return c if "a" <= c <= "z" else "_"


def construire_carrieres(archives_dir: str, alias: Dict[str, str]) -> Dict[str, Dict]:
    """{lettre: {rider_id: carrière}} d'après les riders.json des saisons d'archive. Rapprochement par rider_id exact
    (slug du nom + date de naissance) après alias manuel. Un alias qui ferait apparaître deux fois le même coureur la
    même saison est ignoré pour cette saison (contradiction : la fiche garde son propre identifiant, rien n'est fusionné)."""
    par_coureur: Dict[str, Dict] = {}
    annees = sorted(int(n) for n in os.listdir(archives_dir) if n.isdigit()) if os.path.isdir(archives_dir) else []
    vus: Dict[Tuple[str, int], str] = {}
    for an in annees:
        D = _load(os.path.join(archives_dir, str(an), "riders.json"), None)
        if not D or not isinstance(D.get("riders"), dict):
            continue
        noms_courses = D.get("races") or {}
        # coureurs de la saison dans l'ordre : identifiants canoniques d'abord (alias contradictoires écartés)
        for rid in sorted(D["riders"], key=lambda k: (k in alias, k)):
            f = D["riders"][rid]
            cid = alias.get(rid, rid)
            if (cid, an) in vus:
                print(f"[WARN] carrières : alias « {rid} » -> « {cid} » ignoré en {an} (le coureur canonique y figure déjà)")
                cid = rid
                if (cid, an) in vus:
                    continue
            vus[(cid, an)] = rid
            c = par_coureur.setdefault(cid, {"seasons": {}})
            for k in ("name", "nationality", "flag", "birth_date"):    # saisons parcourues par année croissante : la plus récente l'emporte
                if f.get(k) is not None:
                    c[k] = f[k]
            saison: Dict[str, Any] = {}
            if f.get("team"):
                saison["team"] = f["team"]
            stats = {k: v for k, v in (f.get("stats") or {}).items() if v}
            if stats:
                saison["stats"] = stats
            if f.get("uci_rank") is not None:
                saison["uci_rank"] = f["uci_rank"]
            res = []
            for x in sorted(f.get("results") or [], key=lambda x: (x.get("date") or "", x.get("race_id") or ""), reverse=True):
                if x.get("rank") is None or x["rank"] > 3:
                    continue
                e = {"date": x.get("date"), "race_id": x.get("race_id"), "label": x.get("label"),
                     "classification": x.get("classification"), "rank": x["rank"]}
                if x.get("stage_number") is not None:
                    e["stage_number"] = x["stage_number"]
                nom_course = (noms_courses.get(x.get("race_id")) or {}).get("name")
                if nom_course:
                    e["race"] = nom_course
                res.append(e)
            if res:
                saison["results"] = res
            c["seasons"][str(an)] = saison
    lettres: Dict[str, Dict] = {}
    for cid in sorted(par_coureur):
        c = par_coureur[cid]
        c["seasons"] = dict(sorted(c["seasons"].items(), reverse=True))
        lettres.setdefault(lettre_carriere(cid), {})[cid] = c
    return lettres


def write_archives_editions_carrieres(archives_dir: Optional[str] = None, now: Optional[str] = None,
                                      alias_courses: Optional[Dict[str, str]] = None,
                                      alias_coureurs: Optional[Dict[str, str]] = None) -> None:
    """Écrit archives/editions.json, archives/carrieres/<lettre>.json et archives/carrieres/index.json (seulement s'ils
    changent). Les fichiers de lettre devenus sans coureur sont supprimés (données dérivées)."""
    archives_dir = archives_dir or ARCHIVES_DIR
    ac = charger_alias(ALIAS_COURSES) if alias_courses is None else alias_courses
    ar = charger_alias(ALIAS_COUREURS) if alias_coureurs is None else alias_coureurs
    ed = construire_editions(archives_dir, ac, now)
    _dump_if_changed(os.path.join(archives_dir, "editions.json"), ed)
    dossier = os.path.join(archives_dir, "carrieres")
    lettres = construire_carrieres(archives_dir, ar)
    for lettre, contenu in lettres.items():
        _dump_if_changed(os.path.join(dossier, f"{lettre}.json"), contenu, ignore=())
    # index.json : alias manuels (copie d'alias_coureurs.json) et lettres présentes (la page ne demande que celles-là : pas de 404)
    _dump_if_changed(os.path.join(dossier, "index.json"), {"alias": ar, "lettres": sorted(lettres)}, ignore=())
    if lettres and os.path.isdir(dossier):
        for f in os.listdir(dossier):
            if f.endswith(".json") and f != "index.json" and f[:-5] not in lettres:
                os.remove(os.path.join(dossier, f))
    print(f"[ARCHIVES] éditions : {sum(len(v) for v in ed['courses'].values())} pour {len(ed['courses'])} course(s) ; "
          f"carrières : {sum(len(v) for v in lettres.values())} coureur(s) dans {len(lettres)} fichier(s)")


def write_archives_index(now: Optional[str] = None) -> Dict:
    """data/archives/index.json : récapitulatif des saisons présentes dans data/archives/."""
    saisons = []
    if os.path.isdir(ARCHIVES_DIR):
        for nom in os.listdir(ARCHIVES_DIR):
            dossier = os.path.join(ARCHIVES_DIR, nom)
            if not (nom.isdigit() and os.path.isdir(dossier)):
                continue
            etat = _load(os.path.join(dossier, "state.json"), {})
            idx = _load(os.path.join(dossier, "index.json"), {})
            saisons.append({"season": int(nom), "complete": bool(etat.get("complete")),
                            "races": len(idx.get("races") or []), "size_bytes": _taille_dossier(dossier)})
    saisons.sort(key=lambda s: s["season"], reverse=True)
    data = {"generated_at": now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "seasons": saisons}
    _dump_if_changed(os.path.join(ARCHIVES_DIR, "index.json"), data)
    write_archives_editions_carrieres(ARCHIVES_DIR, now)
    return data


def migrer_saisons_anciennes(today: Optional[dt.date] = None) -> List[int]:
    """Rotation du calendrier vers les archives : les saisons désignées par `saisons_a_archiver` (S+1 terminée depuis
    plus de 14 jours d'après data/index-<S+1>.json ; seules les saisons < `current` de data/seasons.json) sont
    déplacées de data/ vers data/archives/<année>/ : courses compactées (une course déjà présente en archive n'est
    jamais écrasée), index (archive, complete), classement UCI de fin de saison + riders.json
    (`finish_archive_season`), state complete. Les fichiers de data/ (races/<id>.json, index-<année>.json,
    riders-<année>.json) ne sont supprimés qu'après l'écriture réussie de toute la saison. Pas de seasons.json ou
    index de S+1 absent / vide : ne fait rien. Aucune requête réseau pour décider (lecture de fichiers). Appelée par
    run_archive seulement (archives.yml a un checkout complet ; update.yml n'a pas data/archives/). Renvoie les
    saisons migrées."""
    today = today or dt.date.today()
    sj = _load(os.path.join(DATA_DIR, "seasons.json"), None)
    current = sj.get("current") if isinstance(sj, dict) else None
    if not isinstance(current, int) or not os.path.isdir(RACES_DIR):
        return []
    tous: Dict[int, List[Tuple[str, Dict]]] = {}
    for fname in sorted(os.listdir(RACES_DIR)):
        if not fname.endswith(".json"):
            continue
        r = _load(os.path.join(RACES_DIR, fname), None)
        if isinstance(r, dict) and isinstance(r.get("season"), int):
            tous.setdefault(r["season"], []).append((fname, r))
    dispo = {y for y in tous if y < current} | {y for y in (sj.get("available") or []) if isinstance(y, int) and y < current}
    indexes = {y + d: _load(os.path.join(DATA_DIR, f"index-{y + d}.json"), None) for y in dispo for d in (0, 1)}
    a_archiver = saisons_a_archiver(sorted(dispo), {y: ix for y, ix in indexes.items() if ix}, today)
    par_saison = {y: tous[y] for y in a_archiver if y in tous}
    migrees = []
    for annee in sorted(par_saison, reverse=True):
        try:
            dossier = os.path.join(ARCHIVES_DIR, str(annee))
            rdir = os.path.join(dossier, "races")
            os.makedirs(rdir, exist_ok=True)
            for fname, r in par_saison[annee]:
                dest = os.path.join(rdir, fname)
                if not os.path.exists(dest):
                    _dump(dest, compact_race(r))
            courses = charger_courses_archive(dossier)
            idx = build_index(courses, annee, [], None)
            idx["archive"], idx["complete"] = True, True
            _dump_if_changed(os.path.join(dossier, "index.json"), idx)
            finish_archive_season(annee, dossier, courses)
            _dump_if_changed(os.path.join(dossier, "state.json"), {"complete": True, "top10_checked": {}}, ignore=())
            manquants = [f for f, _ in par_saison[annee] if not os.path.exists(os.path.join(rdir, f))]
            manquants += [n for n in ("index.json", "riders.json", "state.json")
                          if not os.path.exists(os.path.join(dossier, n))]
        except Exception as e:   # rien n'est supprimé : la saison reste dans data/ et sera retentée
            print(f"[WARN] [ROTATION] saison {annee} non migrée : {e}")
            continue
        if manquants:
            print(f"[WARN] [ROTATION] saison {annee} non migrée, fichiers manquants : {manquants}")
            continue
        for fname, _ in par_saison[annee]:
            os.remove(os.path.join(RACES_DIR, fname))
        for nom in (f"index-{annee}.json", f"riders-{annee}.json"):
            try:
                os.remove(os.path.join(DATA_DIR, nom))
            except FileNotFoundError:
                pass
        print(f"[ROTATION] saison {annee} -> archives ({len(par_saison[annee])} courses)")
        migrees.append(annee)
    return migrees


def run_archive(years: List[int], today: Optional[dt.date] = None, budget_min: float = 40,
                max_races: int = 0, only: str = "") -> None:
    """Collecte les saisons passées `years` (de la plus récente à la plus ancienne) dans data/archives/<année>/ :
    courses compactées, index, et, la saison terminée, classement UCI de fin de saison + fiches coureurs.
    Sans ASO, récits ni Gemini. Une saison `complete` n'est plus jamais recollectée (aucune requête réseau).
    Commence par la rotation du calendrier (`migrer_saisons_anciennes`, seule écriture hors data/archives/ : suppression
    des fichiers des saisons migrées). Ne touche pas aux autres saisons, à data/state.json ni à seasons.json."""
    today = today or dt.date.today()
    t0 = time.monotonic()
    migrer_saisons_anciennes(today)
    netutil.HOST_DELAYS["dataride.uci.org"] = 2.0   # rythme « archives » : 1 requête / 2 s

    def over_budget() -> bool:
        return bool(budget_min) and (time.monotonic() - t0) / 60 > budget_min

    stopped = False
    count = 0
    limite = False
    for annee in sorted(set(years), reverse=True):
        dossier = os.path.join(ARCHIVES_DIR, str(annee))
        rdir = os.path.join(dossier, "races")
        spath = os.path.join(dossier, "state.json")
        state = _load(spath, {})
        if state.get("complete"):
            print(f"[ARCHIVES] {annee} : déjà complète, ignorée")
            continue
        if stopped or limite:
            break
        sid = uci.get_season_id(annee)
        if sid is None:
            print(f"[WARN] [ARCHIVES] saison UCI {annee} introuvable : ignorée")
            continue
        comps = uci.list_competitions(sid)
        picked = selection.select(comps, [])
        picked_ids = {c["competition_id"] for c, _, _ in picked}
        if only:
            picked = [p for p in picked if only.lower() in p[0]["name"].lower()]
        picked.sort(key=lambda p: p[0].get("start_date") or "", reverse=True)
        top10_cache = dict(state.get("top10_checked") or {})
        os.makedirs(rdir, exist_ok=True)
        collectees = sondees = echecs = 0

        def ecrire(comp: Dict, category: str, reason: str, fetched: Optional[Dict] = None) -> bool:
            race = collect_race(comp, category, reason, None, today, [], fetched, archive=True)
            if not race:
                return False
            race["season"] = annee
            race["_temps_v"] = TEMPS_VERSION
            _dump(os.path.join(rdir, f"uci-{comp['competition_id']}.json"), compact_race(race))
            return True

        for comp, category, reason in picked:
            if over_budget():
                stopped = True
                break
            existant = _load(os.path.join(rdir, f"uci-{comp['competition_id']}.json"), None)
            if existant is not None and existant.get("_complete") is not False:
                if not archive_a_recollecter(existant):
                    continue
                print(f"[ARCHIVES] {annee} · {comp['name']} : temps manquants, recollecte")
            print(f"[COURSE] {annee} · {comp['name']} ({comp.get('uci_class')}, {comp.get('start_date')})")
            if ecrire(comp, category, reason):
                collectees += 1
            else:
                echecs += 1
            count += 1
            if max_races and count >= max_races:
                limite = True
                break

        # .1 / .2 hors de France : retenues si un Français termine dans les 10 premiers (décision mémorisée).
        if not only and not stopped and not limite:
            for comp in sorted(comps, key=lambda c: c.get("start_date") or "", reverse=True):
                if over_budget():
                    stopped = True
                    break
                if comp["competition_id"] in picked_ids or comp.get("uci_class") not in TOP10_CLASSES:
                    continue
                cid = str(comp["competition_id"])
                if top10_cache.get(cid) is False:
                    continue
                existant = _load(os.path.join(rdir, f"uci-{cid}.json"), None)
                if existant is not None and existant.get("_complete") is not False and not archive_a_recollecter(existant):
                    continue
                data = uci.get_race(comp)
                sondees += 1
                if not data or not data.get("stages"):
                    continue
                probe = {"stages": data["stages"], "final": data.get("final"), "riders": data.get("riders") or {},
                         "race_type": data.get("race_type")}
                ok = selection.french_top10(probe)
                end = _date(comp.get("end_date"))
                if end and end < today and data.get("complete", True):
                    top10_cache[cid] = ok
                if ok:
                    cat = "." + comp["uci_class"].split(".")[1][0]
                    print(f"[COURSE] {annee} · {comp['name']} ({comp.get('uci_class')}, {comp.get('start_date')}) "
                          f"· Français dans le top 10")
                    if ecrire(comp, cat, "francais_top10", fetched=data):
                        collectees += 1
                    else:
                        echecs += 1
                    count += 1
                    if max_races and count >= max_races:
                        limite = True
                        break
                # sauvegarde régulière des décisions (reprise après interruption)
                if sondees % 20 == 0:
                    _dump_if_changed(spath, {"complete": False, "top10_checked": top10_cache}, ignore=())

        print(f"[ARCHIVES] {annee} : {len(picked)} retenues, {collectees} collectées, {sondees} sondées, "
              f"{echecs} sans résultat exploitable")
        courses = charger_courses_archive(dossier)
        # Saison terminée : tout parcouru sans arrêt (budget, limite, filtre) et saison close à la date du jour
        fin = (uci.season_bounds().get(annee) or (None, None))[1]
        close = (fin < today.isoformat()) if fin else annee < today.year   # bornes inconnues : année civile révolue
        termine = not (stopped or limite or only) and close
        if not (stopped or limite or only) and not close:
            print(f"[ARCHIVES] {annee} : saison pas encore close (fin {fin}) : non marquée complète")
        if termine:
            finish_archive_season(annee, dossier, courses)
        idx = build_index(courses, annee, [], None)
        idx["archive"], idx["complete"] = True, termine
        _dump_if_changed(os.path.join(dossier, "index.json"), idx)
        _dump_if_changed(spath, {"complete": termine, "top10_checked": top10_cache}, ignore=())

    recap = write_archives_index()
    print(f"[ARCHIVES] récapitulatif : {[(s['season'], s['complete'], s['races']) for s in recap['seasons']]}")
    if stopped:
        print(f"[BUDGET] budget de {budget_min:.0f} min atteint : collecte interrompue, reprise au prochain passage")
    print(f"[FIN] archives {sorted(set(years), reverse=True)} : {count} course(s) collectée(s) ce passage")


# --------------------------------------------------------------------------- tests locaux

def _tests_editions() -> None:
    """cle_edition, alias, editions.json et carrières sur un dossier temporaire (aucun réseau)."""
    import tempfile
    k = cle_edition
    assert k("Paris - Roubaix", "FRA") == k("Paris-Roubaix", "fra") == "paris roubaix|FRA"
    assert k("Paris-Roubaix 2023", "FRA") == k("107e Paris-Roubaix", "FRA") == k("Paris–Roubaix", "FRA")
    assert k("Tour de France", "FRA") != k("Tour de France Saitama Criterium", "FRA")
    assert k("Tour de France", "FRA") != k("Tour de France", "BEL")
    assert k("Grand Prix de l'Essai", "BEL") == k("Grand Prix de l’Essai", "BEL") == k("GRAND PRIX DE L'ESSAI (2024)", "BEL")
    assert k("Liège-Bastogne-Liège", "BEL") == k("Liege - Bastogne - Liege", "BEL")
    assert k("Tour 2.1", "FRA") == "tour 2 1|FRA"          # un numéro sans suffixe d'ordinal n'est pas retiré
    assert k("", "FRA") is None and k("2023", "FRA") is None and k("Paris-Roubaix", "") is None
    with tempfile.TemporaryDirectory() as tmp:
        arch = os.path.join(tmp, "archives")
        def race(i, nom, pays, an, gagnant, fr=None, statut="finished"):
            ref = lambda rid, nm: {"id": rid, "name": nm, "nationality": "FRA", "flag": "fr", "is_french": True, "team": "T"}
            return {"id": i, "name": nom, "country": pays, "uci_class": "1.UWT", "category": "WT", "race_type": "one_day",
                    "start_date": f"{an}-04-10", "status": statut, "winner": ref(*gagnant) if gagnant else None,
                    "best_french": {"rider": ref(*fr), "rank": 2, "classification": "stage"} if fr else None}
        _dump(os.path.join(arch, "2023", "index.json"), {"races": [
            race("a", "Paris - Roubaix", "FRA", 2023, ("x-1", "X Un"), ("f-1", "F Un")),
            race("b", "Tour de France", "FRA", 2023, ("x-1", "X Un")),
            race("c", "Course en cours", "FRA", 2023, None, statut="in_progress")]})
        _dump(os.path.join(arch, "2024", "index.json"), {"races": [
            race("d", "Paris-Roubaix", "FRA", 2024, ("x-2", "X Deux")),
            race("e", "Roubaix Classique", "FRA", 2024, ("x-1", "X Un"))]})
        _dump(os.path.join(arch, "2022", "index.json"), {"races": []})
        ed = construire_editions(arch, {}, "t")
        assert [e["season"] for e in ed["courses"]["paris roubaix|FRA"]] == [2024, 2023]
        assert ed["courses"]["paris roubaix|FRA"][1]["best_french"]["rank"] == 2
        assert ed["courses"]["paris roubaix|FRA"][0]["best_french"] is None
        assert "course en cours|FRA" not in ed["courses"] and "tour de france|FRA" in ed["courses"]
        assert set(ed["courses"]["paris roubaix|FRA"][0]["winner"]) == {"id", "name", "nationality", "flag", "is_french"}
        ed2 = construire_editions(arch, {"roubaix classique|FRA": "paris roubaix|FRA"}, "t")       # alias : changement de nom
        assert [e["race_id"] for e in ed2["courses"]["paris roubaix|FRA"]] == ["d", "e", "a"] and ed2["alias"]
        # carrières
        def fiche(an, **ridrs):
            return {"season": an, "races": {"a": {"name": "Paris - Roubaix"}}, "riders": ridrs}
        def r(nom, team, stats, rang=None, results=()):
            d = {"name": nom, "nationality": "FRA", "flag": "fr", "team": team, "birth_date": "1990-01-01", "stats": stats, "results": list(results)}
            if rang:
                d["uci_rank"] = rang
            return d
        pod = lambda rk, d="2023-04-10": {"date": d, "race_id": "a", "stage_number": None, "label": "Course", "classification": "stage", "rank": rk}
        _dump(os.path.join(arch, "2023", "riders.json"), fiche(2023, **{
            "x-1": r("X Un", "T1", {"wins": 1, "top10": 3, "race_days": 9}, 4, [pod(1), pod(7)]), "z-9": r("Z Neuf", "T9", {"races": 2})}))
        _dump(os.path.join(arch, "2024", "riders.json"), fiche(2024, **{
            "x-1": r("X Un", "T2", {"podiums": 2}, None, [pod(3, "2024-04-10")]), "xx-1": r("X Un Bis", "T3", {"wins": 5}),
            "_bizarre": r("Bizarre", "T4", {})}))
        car = construire_carrieres(arch, {})
        assert set(car) == {"x", "z", "_"} and set(car["x"]) == {"x-1", "xx-1"}
        x = car["x"]["x-1"]
        assert list(x["seasons"]) == ["2024", "2023"] and x["name"] == "X Un" and x["birth_date"] == "1990-01-01"
        assert x["seasons"]["2023"] == {"team": "T1", "stats": {"wins": 1, "top10": 3, "race_days": 9}, "uci_rank": 4,
                                        "results": [{"date": "2023-04-10", "race_id": "a", "label": "Course", "classification": "stage",
                                                     "rank": 1, "race": "Paris - Roubaix"}]}      # le 7e n'est pas un podium
        assert "uci_rank" not in x["seasons"]["2024"] and x["seasons"]["2024"]["results"][0]["rank"] == 3
        # alias coureur : « xx-1 » est « x-1 » ; contradiction en 2024 (x-1 y figure déjà) : ignoré, rien de fusionné
        car2 = construire_carrieres(arch, {"xx-1": "x-1"})
        assert "xx-1" in car2["x"] and car2["x"]["x-1"]["seasons"]["2024"]["team"] == "T2"
        car3 = construire_carrieres(arch, {"z-9": "x-1"})       # x-1 figure déjà en 2023 : z-9 écarté (jamais deux fiches fusionnées)
        assert "z-9" in car3["z"] and list(car3["x"]["x-1"]["seasons"]) == ["2024", "2023"] and car3["x"]["x-1"]["seasons"]["2023"]["team"] == "T1"
        car4 = construire_carrieres(arch, {"xx-1": "y-7"})      # alias vers un id sans autre fiche : renommage
        assert "y-7" in car4["y"] and "xx-1" not in car4["x"] and car4["y"]["y-7"]["seasons"]["2024"]["stats"] == {"wins": 5}
        assert lettre_carriere("_bizarre") == "_" and lettre_carriere("é-1") == "_" and lettre_carriere("a") == "a"
        assert charger_alias(os.path.join(tmp, "absent.json")) == {}
        _dump(os.path.join(tmp, "al.json"), {"a": "b", "b": "c", "d": "d", "e": 3, "f": "g"})
        assert charger_alias(os.path.join(tmp, "al.json")) == {"b": "c", "f": "g"}      # chaînage a->b->c refusé
        # écriture : seuls les fichiers qui changent sont réécrits ; lettre devenue vide supprimée
        write_archives_editions_carrieres(arch, "t1", {}, {})
        chemins = [os.path.join(arch, "editions.json")] + [os.path.join(arch, "carrieres", f) for f in ("x.json", "z.json", "_.json", "index.json")]
        assert all(os.path.exists(c) for c in chemins)
        os.utime(chemins[1], (1, 1))
        write_archives_editions_carrieres(arch, "t2", {}, {})
        assert os.path.getmtime(chemins[1]) == 1 and _load(chemins[0], {})["generated_at"] == "t1"
        os.remove(os.path.join(arch, "2023", "riders.json")); os.remove(os.path.join(arch, "2024", "riders.json"))
        _dump(os.path.join(arch, "2024", "riders.json"), fiche(2024, **{"x-1": r("X Un", "T2", {"podiums": 2})}))
        write_archives_editions_carrieres(arch, "t3", {}, {})
        assert not os.path.exists(chemins[2]) and not os.path.exists(chemins[3]) and os.path.exists(chemins[1])
        assert _load(chemins[4], {}) == {"alias": {}, "lettres": ["x"]}
    print("[OK] collector.py : éditions et carrières")


def _tests() -> None:
    # 1) aucun appel réseau à l'import (sous-processus dont les fonctions réseau lèvent une exception)
    code = ("import netutil\n"
            "def _non(*a, **k): raise RuntimeError('appel réseau à l import')\n"
            "netutil.fetch_text = netutil.fetch_json = netutil.post_form_json = _non\n"
            "import urllib.request\nurllib.request.urlopen = _non\n"
            "import collector\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.abspath(__file__)))
    assert r.returncode == 0, r.stderr
    # 1b) archive_a_recollecter
    ok = {"rank": 1, "rider_id": "a", "time_s": 100, "gap_s": 0}
    sans = {"rank": 2, "rider_id": "b", "gap_s": 5}                       # classé, ni statut ni time_s
    abandon = {"status": "DNF", "rider_id": "c"}                            # statut : normal sans temps
    assert not archive_a_recollecter({"stages": [{"type": "road", "results": {"stage": [ok, abandon], "gc": [ok]}}], "final": {"gc": [ok]}})
    assert archive_a_recollecter({"stages": [{"type": "road", "results": {"stage": [ok, sans]}}]})
    assert archive_a_recollecter({"stages": [{"type": "itt", "results": {"gc": [ok, sans]}}]})
    assert archive_a_recollecter({"stages": [{"results": {"gc": [sans]}}]})                       # type absent = route
    assert not archive_a_recollecter({"stages": [{"type": "ttt", "results": {"stage": [sans], "gc": [sans]}}]})
    assert not archive_a_recollecter({"stages": [{"type": "road", "results": {"points": [sans], "teams": [sans]}}]})
    assert archive_a_recollecter({"stages": [], "final": {"gc": [ok, sans]}})
    assert archive_a_recollecter({"stages": [], "final": {"stage": [sans]}})
    assert not archive_a_recollecter({"stages": [{"type": "road", "results": {"gc": [{"rank": None, "rider_id": "d"}]}}]})
    assert not archive_a_recollecter({"stages": [{"type": "road", "results": {"gc": [sans]}}], "_temps_v": TEMPS_VERSION})
    assert archive_a_recollecter({"stages": [{"type": "road", "results": {"gc": [sans]}}], "_temps_v": TEMPS_VERSION - 1})
    assert not archive_a_recollecter({}) and not archive_a_recollecter({"stages": None, "final": None})
    # 2) compact_race
    def L(n, **extra):
        return [dict({"rank": i + 1, "rider_id": f"r{i}", "gap_s": None, "status": None, "time_s": i}, **extra) for i in range(n)]
    race = {
        "id": "uci-1", "name": "Test", "_complete": True, "season": 2023,
        "stages": [
            {"number": 1, "_aso_done": True, "route": None,
             "results": {"stage": L(100), "gc": L(100), "points": L(80), "kom": L(50), "vide": []}},
            {"number": 2, "_aso_done": True, "results": {"stage": L(100), "gc": L(100), "points": L(80)}},
        ],
        "final": {"gc": L(100), "points": L(80)},
        "riders": {"r0": {"id": "r0", "name": "A", "bib": None, "is_french": False}},
    }
    avant = copy.deepcopy(race)
    c = compact_race(race)
    assert race == avant                                              # entrée intacte
    e1, e2 = c["stages"]
    assert len(e1["results"]["stage"]) == 100 and len(e1["results"]["gc"]) == 100
    assert len(e1["results"]["points"]) == ANNEX_TOP and len(e1["results"]["kom"]) == ANNEX_TOP
    assert e1["results"]["vide"] == []
    assert len(e2["results"]["points"]) == 80                         # dernière étape : annexes complètes
    assert len(c["final"]["points"]) == 80 and len(c["final"]["gc"]) == 100
    assert "_aso_done" not in e1 and "_aso_done" not in e2
    assert all(None not in r.values() for res in (e1["results"], e2["results"], c["final"]) for lg in res.values() for r in lg)
    assert "gap_s" not in e1["results"]["stage"][0] and e1["results"]["stage"][0]["time_s"] == 0
    assert c["riders"]["r0"] == {"id": "r0", "name": "A", "is_french": False}
    assert c["_complete"] is True and c["season"] == 2023
    assert "route" in e1 and e1["route"] is None                      # seules les lignes de classement et riders sont nettoyées
    assert compact_race({"id": "x", "stages": [], "final": None, "riders": {}})["final"] is None
    # 3) rotation N / N-1 sur un dossier temporaire (aucun réseau : classement UCI et fin de saison remplacés)
    import tempfile
    sauve = (DATA_DIR, RACES_DIR, ARCHIVES_DIR, finish_archive_season, _ranking_du_jour)
    globals_ = globals()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            globals_["DATA_DIR"] = tmp
            globals_["RACES_DIR"] = os.path.join(tmp, "races")
            globals_["ARCHIVES_DIR"] = os.path.join(tmp, "archives")

            def course(cid, annee, vainqueur_fr=False):
                rid = "a-b-19900101"
                return {"id": cid, "name": f"Course {cid}", "season": annee, "race_type": "one_day", "uci_class": "1.UWT",
                        "category": "WT", "start_date": f"{annee}-03-01", "end_date": f"{annee}-03-01", "status": "finished",
                        "stages": [{"number": None, "date": f"{annee}-03-01", "name": "Course",
                                    "results": {"stage": [{"rank": 1, "status": None, "bib": None, "rider_id": rid, "time_s": 100}]}}],
                        "final": None, "_complete": True,
                        "riders": {rid: {"id": rid, "name": "A B", "nationality": "FRA" if vainqueur_fr else "BEL",
                                         "flag": "fr", "is_french": vainqueur_fr, "team": None}}}

            def bouchon_fin(annee, dossier, courses=None):
                _dump(os.path.join(dossier, "riders.json"), {"season": annee, "riders": {}})
                return {"ranking": None, "riders": {}}

            globals_["finish_archive_season"] = bouchon_fin
            globals_["_ranking_du_jour"] = lambda today: None
            auj = dt.date(2028, 6, 1)
            assert migrer_saisons_anciennes(auj) == []                   # pas de seasons.json : rien
            for cid, an in (("uci-1", 2028), ("uci-2", 2027), ("uci-3", 2026), ("uci-4", 2026)):
                _dump(os.path.join(RACES_DIR, f"{cid}.json"), course(cid, an, vainqueur_fr=(cid == "uci-3")))
            def idx(an, fin, avenir=()):
                _dump(os.path.join(tmp, f"index-{an}.json"),
                      {"season": an, "races": [{"id": "x", "start_date": f"{an}-03-01", "end_date": fin}],
                       "upcoming": [{"name": "U", "start_date": d, "end_date": d} for d in avenir]})
                _dump(os.path.join(tmp, f"riders-{an}.json"), {"season": an, "riders": {}})
            idx(2028, "2028-03-01", avenir=("2028-09-01",))   # 2028 : course à venir -> pas terminée
            idx(2027, "2027-10-20")                            # 2027 : terminée depuis longtemps
            idx(2026, "2026-10-20")
            _dump(os.path.join(tmp, "seasons.json"), {"current": 2028, "available": [2028, 2027, 2026]})
            # fonction pure : règle des 14 jours, courses à venir, index absent ou vide
            d = dt.date
            ix_ = {2027: {"races": [{"end_date": "2027-10-20"}], "upcoming": []}}
            assert saisons_a_archiver([2026], ix_, d(2027, 11, 3)) == []                  # 14 jours exactement : pas encore
            assert saisons_a_archiver([2026], ix_, d(2027, 11, 4)) == [2026]
            assert saisons_a_archiver([2026], {2027: {"races": [{"start_date": "2027-10-20"}]}}, d(2027, 11, 4)) == [2026]   # start_date à défaut
            assert saisons_a_archiver([2026], {2027: {"races": [{"end_date": "2027-03-01"}], "upcoming": [{"end_date": "2027-12-01"}]}}, d(2027, 11, 4)) == []
            assert saisons_a_archiver([2026], {2027: {"races": [{"end_date": "2027-03-01"}], "upcoming": [{"end_date": "2027-12-01"}]}}, d(2028, 1, 1)) == [2026]   # tout est passé
            assert saisons_a_archiver([2026], {}, d(2030, 1, 1)) == []                      # index absent
            assert saisons_a_archiver([2026], {2027: {"races": [], "upcoming": []}}, d(2030, 1, 1)) == []   # index vide
            assert saisons_a_archiver([2025, 2026, 2027], {2026: ix_[2027], 2027: ix_[2027]}, d(2028, 1, 1)) == [2025, 2026]
            # une course de 2026 déjà présente en archive ne doit pas être écrasée
            _dump(os.path.join(ARCHIVES_DIR, "2026", "races", "uci-4.json"), {"id": "uci-4", "marque": "existante", "season": 2026,
                                                                              "name": "X", "race_type": "one_day", "stages": [], "riders": {}})
            assert migrer_saisons_anciennes(auj) == [2026]               # 2027 terminée ; 2028 non -> 2027 reste
            assert not os.path.exists(os.path.join(RACES_DIR, "uci-3.json")) and not os.path.exists(os.path.join(RACES_DIR, "uci-4.json"))
            assert os.path.exists(os.path.join(RACES_DIR, "uci-1.json")) and os.path.exists(os.path.join(RACES_DIR, "uci-2.json"))
            assert not os.path.exists(os.path.join(tmp, "index-2026.json")) and not os.path.exists(os.path.join(tmp, "riders-2026.json"))
            assert os.path.exists(os.path.join(tmp, "index-2027.json")) and os.path.exists(os.path.join(tmp, "riders-2028.json"))
            a26 = os.path.join(ARCHIVES_DIR, "2026")
            assert _load(os.path.join(a26, "races", "uci-4.json"), {}).get("marque") == "existante"
            assert _load(os.path.join(a26, "races", "uci-3.json"), {})["riders"]["a-b-19900101"].get("team", "absent") == "absent"   # compacté
            ix = _load(os.path.join(a26, "index.json"), {})
            assert ix["archive"] is True and ix["complete"] is True and ix["season"] == 2026
            assert _load(os.path.join(a26, "state.json"), {}) == {"complete": True, "top10_checked": {}}
            assert os.path.exists(os.path.join(a26, "riders.json"))
            assert migrer_saisons_anciennes(auj) == []                   # idempotent
            # 2028 terminée depuis plus de 14 jours -> 2027 part aussi ; échec de la fin de saison : rien n'est supprimé
            idx(2028, "2028-10-25")
            def echec(annee, dossier, courses=None):
                raise RuntimeError("panne")
            globals_["finish_archive_season"] = echec
            assert migrer_saisons_anciennes(dt.date(2028, 11, 8)) == []          # 14 jours exactement : pas encore
            assert migrer_saisons_anciennes(dt.date(2028, 11, 9)) == [] and os.path.exists(os.path.join(RACES_DIR, "uci-2.json"))   # panne
            globals_["finish_archive_season"] = bouchon_fin
            assert migrer_saisons_anciennes(dt.date(2028, 11, 9)) == [2027]
            assert not os.path.exists(os.path.join(RACES_DIR, "uci-2.json")) and os.path.exists(os.path.join(ARCHIVES_DIR, "2027", "races", "uci-2.json"))
            recap = write_archives_index("2028-01-01T00:00:00Z")
            assert [s["season"] for s in recap["seasons"]] == [2027, 2026] and all(s["complete"] for s in recap["seasons"])
            # write_season_indexes : une saison dont la suivante est terminée n'est plus listée
            _dump(os.path.join(RACES_DIR, "uci-6.json"), course("uci-6", 2026))
            _dump(os.path.join(RACES_DIR, "uci-7.json"), course("uci-7", 2027))
            futur = {"name": "U", "start_date": "2028-09-01", "end_date": "2028-09-01"}
            cal = {2028: build_index([course("uci-1", 2028)], 2028, [futur], None)}
            write_season_indexes(2028, cal, auj)
            assert _load(os.path.join(tmp, "seasons.json"), {}) == {"current": 2028, "available": [2028, 2027]}   # 2027 terminée -> 2026 sortie
            assert not os.path.exists(os.path.join(tmp, "riders-2026.json"))
            cal = {2028: build_index([course("uci-1", 2028)], 2028, [], None)}
            write_season_indexes(2028, cal, dt.date(2028, 6, 1))    # 2028 sans course à venir, terminée depuis le 2028-03-01
            assert _load(os.path.join(tmp, "seasons.json"), {})["available"] == [2028]   # 2027 sortie à son tour
            write_season_indexes(2028, cal, dt.date(2028, 3, 10))   # moins de 14 jours après la dernière course de 2028
            assert _load(os.path.join(tmp, "seasons.json"), {})["available"] == [2028, 2027]
            # intersaison : la saison suivante (calculée) reste listée
            write_season_indexes(2027, {2027: build_index([course("uci-7", 2027)], 2027, [], None),
                                        2028: build_index([], 2028, [futur], None)}, dt.date(2027, 12, 1))
            assert _load(os.path.join(tmp, "seasons.json"), {})["available"] == [2028, 2027]
    finally:
        globals_["DATA_DIR"], globals_["RACES_DIR"], globals_["ARCHIVES_DIR"], globals_["finish_archive_season"], globals_["_ranking_du_jour"] = sauve
    _tests_editions()
    print("[OK] collector.py : tests locaux réussis")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _tests()
    else:
        print("usage : python collector.py --test (le collecteur se lance via run_pipeline.py)")
