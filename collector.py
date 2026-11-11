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
import subprocess
import sys
import time
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
    calendrier à venir, en gardant leur dernier classement FDJ connu."""
    if not isinstance(computed, dict) or "races" in computed:   # compatibilité : un seul index (saison courante)
        computed = {current: computed}
    by_season: Dict[int, List[Dict]] = {}
    for fname in os.listdir(RACES_DIR):
        if fname.endswith(".json"):
            r = _load(os.path.join(RACES_DIR, fname), None)
            if r and isinstance(r.get("season"), int):
                by_season.setdefault(r["season"], []).append(r)
    seasons = sorted({y for y in by_season if y <= current} | set(computed), reverse=True)
    for y in seasons:
        path = os.path.join(DATA_DIR, f"index-{y}.json")
        if y in computed:
            _dump_if_changed(path, computed[y])
            continue
        old = _load(path, {})
        _dump_if_changed(path, build_index(by_season.get(y, []), y, [], old.get("fdj_united_series")))
    write_riders_files(seasons, current, by_season, today or dt.date.today())
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
    return data


def run_archive(years: List[int], today: Optional[dt.date] = None, budget_min: float = 40,
                max_races: int = 0, only: str = "") -> None:
    """Collecte les saisons passées `years` (de la plus récente à la plus ancienne) dans data/archives/<année>/ :
    courses compactées, index, et, la saison terminée, classement UCI de fin de saison + fiches coureurs.
    Sans ASO, récits ni Gemini. Une saison `complete` n'est plus jamais recollectée (aucune requête réseau).
    Ne touche jamais à data/index*.json, data/races, data/state.json, seasons.json."""
    today = today or dt.date.today()
    t0 = time.monotonic()
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
            _dump(os.path.join(rdir, f"uci-{comp['competition_id']}.json"), compact_race(race))
            return True

        for comp, category, reason in picked:
            if over_budget():
                stopped = True
                break
            existant = _load(os.path.join(rdir, f"uci-{comp['competition_id']}.json"), None)
            if existant is not None and existant.get("_complete") is not False:
                continue
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
                if existant is not None and existant.get("_complete") is not False:
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
    print("[OK] collector.py : tests locaux réussis")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _tests()
    else:
        print("usage : python collector.py --test (le collecteur se lance via run_pipeline.py)")
