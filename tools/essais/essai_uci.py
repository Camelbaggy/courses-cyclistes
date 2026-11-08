#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Essai réseau de uci.py + selection.py (saison 2026) et exploration du calendrier à venir / des CGU.
Balises du message de commit (variable MSG) : [cal] = exploration calendrier et CGU seulement ; [courses] = courses seulement.
Sans balise : tout."""
import json
import os
import re
import sys
import time

sys.path.insert(0, ".")
import netutil  # noqa: E402
import selection  # noqa: E402
import uci  # noqa: E402

MSG = os.environ.get("MSG", "")
SEULEMENT_CAL = "[cal]" in MSG
SEULEMENT_COURSES = "[courses]" in MSG
DEBUT = time.time()
uci.GARDER_BRUT = True  # diagnostic : valeurs ResultValue brutes dans les Row


def titre(txt):
    print(f"\n######## {txt}  (t+{time.time() - DEBUT:.0f}s)")


def hms(s):
    if s is None:
        return "-"
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def fmt_row(row, riders, cle):
    r = riders.get(row.get("rider_id"), {}) if row.get("rider_id") else {}
    if "team" in row and "rider_id" not in row:
        ident = f"{row['team']} ({row.get('nationality')})"
    else:
        ident = f"{r.get('name')} [{r.get('nationality')}] {r.get('team')} #{row.get('bib')}"
    if cle in uci.CLES_POINTS:
        val = f"{row.get('points')} pts"
    else:
        val = f"{hms(row.get('time_s'))} (+{row.get('gap_s')}s)"
    return f"{row.get('rank')} {row.get('status') or ''} {ident} {val} uci={row.get('uci_points')}"


def trouve(comps, **crit):
    for c in comps:
        if all(str(v).lower() in str(c.get(k, "")).lower() for k, v in crit.items()):
            return c
    return None


def course_complete(comp):
    titre(f"get_race {comp['name']} [{comp['uci_class']}] {comp['start_date']} -> {comp['end_date']} ({comp['country']})")
    t0 = time.time()
    race = uci.get_race(comp)
    if not race:
        print("[ECHEC] get_race a renvoyé None")
        return None
    print(f"durée {time.time() - t0:.0f}s ; type={race['race_type']} ; complet={race['complete']} ; étapes={len(race['stages'])} ; "
          f"coureurs={len(race['riders'])} ; final={'oui' if race['final'] else 'non'}")
    taille = len(json.dumps(race, ensure_ascii=False))
    print(f"JSON sérialisé : {taille} octets ({taille / 1024:.0f} Ko)")
    riders = race["riders"]
    for s in race["stages"]:
        cles = {k: len(v) for k, v in s["results"].items() if v}
        print(f"  étape {s['number']} {s['name']!r} {s['date']} {s['start']}->{s['finish']} type={s['type']} classements={cles}")
    if race["final"]:
        print("  classements finaux :", {k: len(v) for k, v in race["final"].items() if v})
        for cle, rows in race["final"].items():
            print(f"  -- top 5 final '{cle}'")
            for row in rows[:5]:
                print("     ", fmt_row(row, riders, cle))
    dernier = race["stages"][-1] if race["stages"] else None
    if dernier and not race["final"]:
        for cle, rows in dernier["results"].items():
            print(f"  -- top 5 dernière étape '{cle}'")
            for row in rows[:5]:
                print("     ", fmt_row(row, riders, cle))
    # abandons / français
    ref = race["final"] or (dernier["results"] if dernier else {})
    ligne_course = ref.get("stage") or ref.get("gc") or []
    print("  DNF/DNS/OTL/DSQ dans le classement de référence :",
          {st: sum(1 for r in ligne_course if r["status"] == st) for st in ("DNF", "DNS", "OTL", "DSQ", "DNQ")},
          "| classés :", sum(1 for r in ligne_course if not r["status"]))
    francais = [r for r in ligne_course if riders.get(r["rider_id"], {}).get("is_french")]
    print(f"  Français dans le classement de référence : {len(francais)}")
    for row in francais[:6]:
        print("     ", fmt_row(row, riders, "stage"))
    print("  selection.french_top10 :", selection.french_top10(race))
    # contrôles de cohérence
    for s in race["stages"]:
        for cle, rows in s["results"].items():
            if cle in uci.CLES_TEMPS and cle != "teams":
                tps = [r["time_s"] for r in rows if r["time_s"] is not None]
                if tps != sorted(tps):
                    print(f"  [CHECK] temps non croissants : étape {s['number']} {cle}")
                    for i in range(1, len(rows)):
                        a, b = rows[i - 1], rows[i]
                        if a["time_s"] is not None and b["time_s"] is not None and b["time_s"] < a["time_s"]:
                            for r in rows[max(0, i - 3):i + 3]:
                                print("      ", r["rank"], r["status"], r["time_s"], r["gap_s"], repr(r.get("_rv")))
                            break
                rangs = [r["rank"] for r in rows if r["rank"] is not None]
                if rangs != sorted(rangs):
                    print(f"  [CHECK] rangs non croissants : étape {s['number']} {cle}")
    # échantillon complet d'une étape (la 2e si elle existe)
    if race["stages"]:
        s = race["stages"][1 if len(race["stages"]) > 1 else 0]
        print(f"\n  >>> échantillon brut normalisé, étape {s['number']} ({s['name']}) : 5 premières lignes de chaque classement")
        for cle, rows in s["results"].items():
            print(f"  [{cle}] {len(rows)} lignes")
            for row in rows[:5]:
                print("     ", json.dumps(row, ensure_ascii=False))
        pid = next(iter(race["riders"]), None)
        print("  exemple riders :", json.dumps(race["riders"].get(pid), ensure_ascii=False))
    return race


def partie_courses():
    titre("Saison 2026 : liste des compétitions")
    sid = uci.get_season_id(2026)
    print("season_id 2026 =", sid, "| 2027 =", uci.get_season_id(2027))
    comps = uci.list_competitions(sid)
    print("compétitions :", len(comps), "| exemple :", json.dumps(comps[0], ensure_ascii=False) if comps else None)
    from collections import Counter
    print("par classe :", Counter(c["uci_class"] for c in comps).most_common())
    print("pays vides :", sum(1 for c in comps if not c["country"]), "| dates vides :", sum(1 for c in comps if not c["start_date"]))
    sel = selection.select(comps, None)
    titre(f"Sélection (sans liste FDJ) : {len(sel)} retenues sur {len(comps)}")
    print("par catégorie :", Counter(cat for _, cat, _ in sel).most_common())
    print("par raison :", Counter(r for _, _, r in sel).most_common())
    print("par (catégorie, classe) :", Counter((cat, c["uci_class"]) for c, cat, _ in sel).most_common())
    ids = {c["competition_id"] for c, _, _ in sel}
    cand = selection.candidates_top10(comps, [c for c, _, _ in sel])
    print("candidats .1/.2 hors France (sondés par le collecteur) :", len(cand))
    reste = [c for c in comps if c["competition_id"] not in ids and c not in cand]
    print("non retenues, non candidates, par classe :", Counter(c["uci_class"] for c in reste).most_common())
    for cl in ("CN", "CC", "CM", "WC", "CRTP", "JC", "JR", "1.2S", "1.Ncup", "2.2U", "1.2U", "2.Ncup"):
        ex = [(c["name"], c["country"], c["start_date"]) for c in comps if c["uci_class"] == cl][:3]
        if ex:
            print(f"  exemples classe {cl} :", ex)
    print("courses en FRA par classe :", Counter(c["uci_class"] for c in comps if c["country"] == "FRA").most_common())
    print("pays != 3 lettres :", {c["country"] for c in comps if c["country"] and len(c["country"]) != 3})
    print("retenues françaises (hors CN) :", [(c["name"], cat) for c, cat, _ in sel if c["country"] == "FRA" and c["uci_class"] != "CN"][:25])

    pr = trouve(comps, name="roubaix", uci_class="1.UWT", start_date="2026-04-12")
    pn = trouve(comps, name="paris", uci_class="2.UWT") if not trouve(comps, name="paris-nice") else trouve(comps, name="paris-nice")
    fr1 = next((c for c in comps if c["country"] == "FRA" and c["uci_class"] == "1.1"), None) or \
          next((c for c in comps if c["country"] == "FRA" and c["uci_class"] == "2.1"), None)
    print("\nchoix :", [(c["name"], c["uci_class"]) if c else None for c in (pr, pn, fr1)])
    for c in (pr, pn, fr1):
        if c:
            course_complete(c)
    if pn:
        titre("Diagnostic brut Paris-Nice : events de l'étape 3 (CLM par équipes) et 1res lignes")
        races = uci._liste_paginee("/iframe/Races/", taille=100, competitionId=pn["competition_id"], disciplineId=10) or []
        for r in races:
            if r.get("RaceName") == "Stage 3":
                evs = uci._post("/iframe/Events/", {"disciplineId": 10, "raceId": r["Id"]})
                print("Race:", json.dumps(r, ensure_ascii=False))
                for ev in evs:
                    print("EVENT:", json.dumps(ev, ensure_ascii=False)[:500])
                    rep = uci._post("/iframe/Results/", uci._kendo(3, 0, disciplineId=10, eventId=ev["EventId"]))
                    for l in (rep or {}).get("data", [])[:2]:
                        print("   ROW:", json.dumps(l, ensure_ascii=False)[:600])
    titre("Libellés d'events rencontrés (EventName, portée, clé) -> occurrences")
    for (nom, portee, cle), n in sorted(uci.EVENTS_VUS.items(), key=lambda x: -x[1]):
        print(f"  {nom!r:55} portée={portee:8} clé={cle}  x{n}")
    print("Irm vus :", dict(uci.IRM_VUS))


# --------------------------------------------------------------------------------------------------
def texte(html):
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'")
    return re.sub(r"\s+", " ", html)


def liens(html):
    return sorted(set(re.findall(r'''(?:href|src|action|data-src)\s*=\s*["']([^"']+)["']''', html, re.I)))


def absolu(base, l):
    from urllib.parse import urljoin
    return urljoin(base, l)


MOTS_CGU = re.compile(r"scrap|automat|robot|crawl|spider|extract|reproduc|reus|re-us|commerc|data ?mining|bot\b|"
                      r"harvest|systematic|intellectual|copyright|database|prior (written )?(consent|permission|authori)", re.I)


def cgu(url):
    html = netutil.fetch_text(url, headers={"Accept": "text/html"}, retries=2, raw_name="cgu_" + url[-30:])
    if not html:
        print(f"  (rien reçu de {url})")
        return
    t = texte(html)
    print(f"  {url} : {len(t)} caractères de texte ; fin du texte : {t[-700:]}")
    print("   liens documents :", [l for l in liens(html) if re.search(r"\.pdf|document|assets\.ctfassets|legal|terms", l, re.I)][:15])
    phrases = re.split(r"(?<=[.;:])\s+", t)
    n = 0
    for p in phrases:
        if MOTS_CGU.search(p) and 40 < len(p) < 900:
            print("   >", p.strip())
            n += 1
            if n >= 25:
                break
    if n == 0:
        print("   (aucune phrase avec mots-clés ; début du texte :)", t[:600])


def partie_calendrier():
    titre("Exploration du calendrier à venir")
    pages = ["https://www.uci.org/road/calendar", "https://www.uci.org/", "https://dataride.uci.org/iframe/Results/10/",
             "https://dataride.uci.org/"]
    trouves_cgu, trouves_cal = set(), set()
    for url in pages:
        html = netutil.fetch_text(url, headers={"Accept": "text/html"}, retries=2, raw_name="cal_" + url[-25:])
        if not html:
            print(f"-- {url} : rien")
            continue
        print(f"\n-- {url} : {len(html)} octets ; title={re.findall(r'<title[^>]*>(.*?)</title>', html, re.S)[:1]}")
        print("   marqueurs :", [k for k in ("__NEXT_DATA__", "ng-app", "data-reactroot", "__NUXT__", "window.__", "application/json",
                                             "graphql", "kendo", "dataride", "umbraco", "sitecore", "episerver") if k in html.lower() or k in html])
        ls = liens(html)
        for l in ls:
            a = absolu(url, l)
            if re.search(r"terms|legal|condition|privacy|disclaimer|copyright|cookie|imprint|mentions|licen", a, re.I) and "uci" in a:
                trouves_cgu.add(a.split("#")[0])
            if re.search(r"calendar|calendrier|competitionscalendar|upcoming|schedule", a, re.I) and re.search(r"uci\.(org|ch)", a):
                trouves_cal.add(a.split("#")[0])
        interess = [l for l in ls if re.search(r"calendar|api|iframe|\.json|graphql|search|events?", l, re.I)]
        print(f"   {len(ls)} liens ; intéressants ({len(interess)}) :")
        for l in interess[:50]:
            print("     -", l[:180])
        for m in re.finditer(r'(?is)<script[^>]*type="application/(?:ld\+)?json"[^>]*>(.*?)</script>', html):
            print("   JSON intégré :", m.group(1)[:500].replace("\n", " "))
        for m in list(re.finditer(r"(?i)(calendar[^\"'<>\s]{0,80}|/api/[^\"'<>\s]{0,100}|GetCalendar[^\"'<>\s]{0,60})", html))[:25]:
            print("   motif :", m.group(1)[:140])
    titre("Scripts de la page calendrier et motifs d'API")
    html = netutil.fetch_text("https://www.uci.org/road/calendar", headers={"Accept": "text/html"}, retries=2) or ""
    scripts = [absolu("https://www.uci.org/road/calendar", s) for s in re.findall(r'<script[^>]+src=["\']([^"\']+)', html, re.I)]
    for s in scripts:
        print("  script:", s)
    for m in re.finditer(r"(?is)<script(?![^>]+src)[^>]*>(.*?)</script>", html):
        corps = m.group(1)
        if re.search(r"calendar|api|fetch|endpoint|baseUrl", corps, re.I):
            print(f"  script inline ({len(corps)} o) :", re.sub(r"\s+", " ", corps)[:700])
    motifs = re.compile(r"""["'`]((?:https?:)?//[A-Za-z0-9./_-]*(?:api|search|calendar|graphql|contentful|algolia|azure)[A-Za-z0-9./_?=&%{}$-]*|/api/[A-Za-z0-9./_?=&%{}$-]*|/[A-Za-z0-9/_-]*[Cc]alendar[A-Za-z0-9/_?=&%{}$-]*)["'`]""")
    vus = set()
    for s in [x for x in scripts if "uci.org" in x][:8]:
        js = netutil.fetch_text(s, headers={"Accept": "*/*"}, retries=2, raw_name="js_" + s[-30:])
        if not js:
            continue
        trouves = sorted({m.group(1) for m in motifs.finditer(js)} - vus)
        vus |= set(trouves)
        print(f"  {s} : {len(js)} o ; {len(trouves)} motifs")
        for t in trouves[:40]:
            print("     ", t[:160])
    titre("dataride.uci.ch/iframe (pages iframe disponibles ?)")
    for u in ("https://dataride.uci.ch/iframe", "https://dataride.uci.org/iframe/Results/10/"):
        h = netutil.fetch_text(u, headers={"Accept": "text/html"}, retries=2)
        if h:
            print(f"  {u} : {len(h)} o ; liens iframe :", [l for l in liens(h) if "iframe" in l.lower()][:30])
            for m in re.finditer(r"(?i)(calendar[A-Za-z/_?=&.]*|GetCompetitions[A-Za-z]*|Upcoming[A-Za-z]*)", h):
                print("     motif:", m.group(1)[:100])
    titre("Pages calendrier candidates trouvées")
    for a in sorted(trouves_cal)[:12]:
        print(" -", a)
    cibles = [a for a in sorted(trouves_cal) if a not in pages][:6]
    for a in cibles:
        html = netutil.fetch_text(a, headers={"Accept": "text/html,application/json"}, retries=2, raw_name="cal2_" + a[-25:])
        if html:
            print(f"\n-- {a} : {len(html)} octets ; début : {texte(html)[:500]}")
            print("   JSON ?", html.lstrip()[:1].startswith(("{", "[")))
    # endpoints DataRide de calendrier (pages iframe) : on ne teste que les chemins repérés dans les liens
    titre("Conditions d'utilisation / mentions légales")
    print("pages légales repérées :", sorted(trouves_cgu))
    for a in sorted(trouves_cgu)[:6]:
        cgu(a)
    for a in ("https://www.uci.org/terms-of-use", "https://www.uci.org/legal-notice", "https://www.uci.org/privacy-policy"):
        if a not in trouves_cgu:
            cgu(a)
    titre("uci.list_upcoming(2027)")
    up = uci.list_upcoming(2027)
    print(len(up), "courses à venir")
    for u in up[:30]:
        print("  ", json.dumps(u, ensure_ascii=False))


if __name__ == "__main__":
    uci._tests()
    selection._tests()
    if not SEULEMENT_CAL:
        partie_courses()
    if not SEULEMENT_COURSES:
        partie_calendrier()
    print(f"\nFin ({time.time() - DEBUT:.0f}s)")
