#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orchestration de la collecte : sélection des courses de la saison (UCI + LNC), récupération des
résultats UCI, enrichissement (ASO, récits), résumés, calculs dérivés déterministes, écriture de
data/index.json et data/races/<id>.json (voir docs/SPEC.md §4).

Les fichiers de course sont conservés d'un passage à l'autre : seules les courses nouvelles, en cours ou
terminées depuis moins de REFRESH_DAYS jours sont recollectées."""

import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import agents_flash
import aso
import cyclingnews
import directvelo
import lnc
import selection
import uci

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
                 cn_items: List[Dict], fetched: Optional[Dict] = None) -> Optional[Dict]:
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
    aso_ref = aso.match_race(race["name"], race["start_date"])
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
        if old and old.get("ai_summary") and _stage_fingerprint(old) == _stage_fingerprint(st) \
                and not (old.get("summary_source") == "fallback" and _is_recent(st, today, AI_DAYS)):
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

def run(season: int, today: Optional[dt.date] = None, only: str = "", max_races: int = 0) -> Dict:
    today = today or dt.date.today()
    os.makedirs(RACES_DIR, exist_ok=True)
    state = _load(os.path.join(DATA_DIR, "state.json"), {})
    notified = set(state.get("notified") or [])
    top10_cache = state.get("top10_checked") or {}   # competition_id -> bool (courses terminées seulement)

    season_id = uci.get_season_id(season)
    if season_id is None:
        raise SystemExit(f"[ERREUR] Saison UCI {season} introuvable")
    comps = uci.list_competitions(season_id)
    print(f"[UCI] {len(comps)} courses hommes élite courues ou en cours en {season}")
    fdj = lnc.get_fdj_united_series()
    picked = selection.select(comps, (fdj or {}).get("races") or [])
    picked_ids = {c["competition_id"] for c, _, _ in picked}
    if only:
        picked = [p for p in picked if only.lower() in p[0]["name"].lower()]
    print(f"[SELECTION] {len(picked)} courses retenues d'office")

    cn_items = cyclingnews.fetch_items()
    races: Dict[str, Dict] = {}
    new_items: List[Tuple[Dict, int]] = []

    def handle(comp: Dict, category: str, reason: str, fetched: Optional[Dict] = None) -> None:
        rid = f"uci-{comp['competition_id']}"
        previous = _load(race_path(rid), None)
        if fetched is None and not _needs_refresh(comp, previous, today):
            races[rid] = previous
            return
        print(f"[COURSE] {comp['name']} ({comp.get('uci_class')}, {comp.get('start_date')})")
        race = collect_race(comp, category, reason, previous, today, cn_items, fetched)
        if not race:
            return
        race["season"] = season
        races[rid] = race
        _dump(race_path(rid), race)
        for idx in range(len(race["stages"])):
            key = stage_key(race, idx)
            if key not in notified:
                notified.add(key)
                if _is_recent(race["stages"][idx], today, NOTIFY_DAYS):
                    new_items.append((race, idx))

    count = 0
    for comp, category, reason in picked:
        handle(comp, category, reason)
        count += 1
        if max_races and count >= max_races:
            break

    # .1 / .2 hors de France : retenues si un Français termine dans les 10 premiers.
    if not only and not (max_races and count >= max_races):
        for comp in comps:
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

    upcoming = uci.list_upcoming(season + 1 if today.month >= 11 else season)
    # Garde les fichiers de courses non revues ce passage (index complet de la saison)
    for fname in os.listdir(RACES_DIR):
        rid = fname[:-5]
        if fname.endswith(".json") and rid not in races and not only:
            prev = _load(os.path.join(RACES_DIR, fname), None)
            if prev and prev.get("season") == season:
                races[rid] = prev
    index = build_index(list(races.values()), season, upcoming, fdj)
    if new_items:
        index["notification"] = agents_flash.build_notification(new_items)
    _dump(os.path.join(DATA_DIR, "index.json"), index)
    state.update({"notified": sorted(notified), "top10_checked": top10_cache,
                  "last_run": index["generated_at"]})
    _dump(os.path.join(DATA_DIR, "state.json"), state)
    print(f"[FIN] {len(races)} courses dans l'index, {len(new_items)} nouveauté(s) à notifier")
    return index
