"""Sonde UCI (bibliothèque standard uniquement) : découvre les endpoints publics de uci.org / dataride.uci.ch.
User-Agent honnête, pause >= 1 s entre requêtes, aucun contournement (challenge / 403 : on note et on s'arrête)."""
import re, sys, time, json, urllib.request, urllib.error

UA = "courses-cyclistes-sonde/0.1 (projet personnel non commercial)"
_last = [0.0]
STOP = [False]
DEBUT = time.time()
BUDGET = 240  # secondes : on s'arrête proprement au-delà


def get(url, accept="*/*", maxprint=600, show=True, data=None, headers=None):
    if time.time() - DEBUT > BUDGET:
        STOP[0] = True
    if STOP[0]:
        print("ARRET (blocage anti-robot constaté), requête ignorée:", url)
        return None, ""
    d = 1.1 - (time.time() - _last[0])
    if d > 0:
        time.sleep(d)
    h = {"User-Agent": UA, "Accept": accept}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h, data=data)
    try:
        r = urllib.request.urlopen(req, timeout=20)
        code, body, hd = r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        code, body, hd = e.code, e.read(), e.headers
    except Exception as e:
        print(f"\n=== {url}\n  ERREUR {e}")
        return None, ""
    _last[0] = time.time()
    txt = body.decode("utf-8", "replace")
    print(f"\n=== {url}\n  HTTP {code} | {hd.get('content-type')} | {len(body)} o | server={hd.get('server')}")
    if code in (403, 429, 503) or "Just a moment" in txt[:3000] or "cf-chl" in txt[:5000]:
        print("  >>> challenge / blocage : arrêt des requêtes vers ce site")
        STOP[0] = True
    if show:
        print("  " + txt[:maxprint].replace("\n", "\n  "))
    return code, txt


def liens(txt, base=""):
    out = set()
    for m in re.finditer(r'''(?:src|href|action|data-src|data-url)\s*=\s*["']([^"']+)["']''', txt, re.I):
        out.add(m.group(1))
    for m in re.finditer(r'''["'](https?://[^"'\s<>\\]+|/[A-Za-z0-9_\-./?=&%]+)["']''', txt):
        out.add(m.group(1))
    return out


def interessants(txt):
    mots = re.compile(r"iframe|dataride|api|calendar|result|ranking|event|\.json|xhr|fetch\(|axios", re.I)
    return sorted(l for l in liens(txt) if mots.search(l))


def explorer(url, n=60):
    code, txt = get(url, accept="text/html", show=False)
    if not txt:
        return txt
    print("  <title>:", re.findall(r"<title[^>]*>(.*?)</title>", txt, re.S)[:1])
    print("  iframes:", re.findall(r"<iframe[^>]*>", txt, re.I)[:10])
    print("  __NEXT_DATA__/ng/vue:", [k for k in ("__NEXT_DATA__", "ng-app", "data-reactroot", "__NUXT__", "dataride") if k in txt])
    for l in interessants(txt)[:n]:
        print("   -", l[:200])
    return txt


def contexte(txt, motifs, avant=300, apres=500, maxn=4):
    for m in motifs:
        pos = [x.start() for x in re.finditer(re.escape(m), txt)][:maxn]
        for k in pos:
            print(f"  --- contexte de {m!r} @{k}:")
            print("  " + txt[max(0, k - avant):k + apres].replace("\n", "\n  "))


def post(path, champs, base="https://dataride.uci.org", maxprint=1500):
    import urllib.parse
    corps = urllib.parse.urlencode(champs).encode()
    return get(base + path, accept="application/json, text/javascript, */*; q=0.01", data=corps,
               maxprint=maxprint, headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                                           "X-Requested-With": "XMLHttpRequest",
                                           "Referer": base + "/iframe/Results/10/"})


def post_json(path, champs, base="https://dataride.uci.org"):
    import urllib.parse
    c, t = post(path, champs, base=base, maxprint=0)
    try:
        return json.loads(t)
    except Exception:
        return None


def kendo(page=1, taille=40, filtres=None, tri=None, **extra):
    """Paramètres envoyés par une DataSource Kendo (serverPaging / serverFiltering / serverSorting)."""
    d = {"take": taille, "skip": (page - 1) * taille, "page": page, "pageSize": taille}
    if tri:
        d["sort[0][field]"], d["sort[0][dir]"] = tri
    if filtres:
        d["filter[logic]"] = "and"
        for n, (champ, val) in enumerate(filtres):
            d[f"filter[filters][{n}][field]"] = champ
            d[f"filter[filters][{n}][operator]"] = "eq"
            d[f"filter[filters][{n}][value]"] = val
    d.update(extra)
    return d


def montrer(j, n=2, maxc=900):
    if isinstance(j, dict):
        data = j.get("data") or []
        total = j.get("total")
    elif isinstance(j, list):
        data, total = j, len(j)
    else:
        print("  (pas du JSON)")
        return []
    print(f"  total={total} len={len(data)} cles={sorted(data[0].keys()) if data and isinstance(data[0], dict) else None}")
    for r in data[:n]:
        print("  ex:", json.dumps(r, ensure_ascii=False)[:maxc])
    return data


def calendrier(sid, cat, pages=6):
    flt3 = [("RaceTypeId", 0), ("CategoryId", cat), ("SeasonId", sid)]
    out = []
    for pg in range(1, pages + 1):
        j = post_json("/iframe/Competitions/", kendo(page=pg, taille=100, filtres=flt3, tri=("StartDate", "asc"), disciplineId=10))
        data = (j or {}).get("data") or []
        out += data
        if not data or len(out) >= (j or {}).get("total", 0):
            break
    return out


def chaine(nom, cid, max_events_final=8):
    print(f"\n######## {nom} -> {cid}")
    races = post_json("/iframe/Races/", kendo(taille=60, competitionId=cid, disciplineId=10))
    races = montrer(races, n=0)
    if not races:
        return
    print("  courses/etapes:", [(r["Index"], r["Id"], r["RaceName"], r.get("Date")) for r in races][:30])
    cibles = [races[0]] + ([races[1]] if len(races) > 2 else []) + ([races[-1]] if len(races) > 1 else [])
    for r in cibles:
        print(f"\n  >>> race {r['Id']} {r['RaceName']} ({r.get('Date')})")
        evs = montrer(post_json("/iframe/Events/", {"disciplineId": 10, "raceId": r["Id"]}), n=0)
        for e in evs:
            print("   event:", json.dumps(e, ensure_ascii=False)[:420])
        for e in evs[:max_events_final]:
            eid = e.get("Id") or e.get("EventId")
            print(f"  -- Results eventId={eid} ({e.get('EventName') or e.get('Name')})")
            montrer(post_json("/iframe/Results/", kendo(taille=3, disciplineId=10, eventId=eid)), n=2, maxc=1100)


def maintenant_ms():
    return int(time.time() * 1000)


def ms(x):
    m = re.search(r"-?\d+", str(x or ""))
    return int(m.group()) if m else 0


def resume_competition(c, detail=False):
    """Races -> premier Race -> Events -> Results(take 1) : renvoie une ligne compacte."""
    races = (post_json("/iframe/Races/", kendo(taille=60, competitionId=c["CompetitionId"], disciplineId=10)) or {}).get("data") or []
    if not races:
        return f"{c['CompetitionName']} [{c['ClassCode']}] {c['Date']} : aucune race"
    r = races[0]
    evs = post_json("/iframe/Events/", {"disciplineId": 10, "raceId": r["Id"]})
    if not isinstance(evs, list) or not evs:
        return f"{c['CompetitionName']} [{c['ClassCode']}] {c['Date']} : {len(races)} race(s), AUCUN event ({r['RaceName']})"
    e = evs[0]
    res = post_json("/iframe/Results/", kendo(taille=1, disciplineId=10, eventId=e["EventId"])) or {}
    d = (res.get("data") or [{}])[0]
    return (f"{c['CompetitionName']} [{c['ClassCode']}] {c['Date']} done={c['IsDone']}/prog={c['IsInProgress']} : {len(races)} race(s), "
            f"{len(evs)} event(s) {[x['EventName'] for x in evs][:4]}, {e['EventName']} total={res.get('total')} "
            f"1er={d.get('DisplayName')} {d.get('ResultValue')} ({d.get('TeamName')}, {d.get('IndividualCountryNameText')})")


def passe11():
    from collections import Counter
    c26 = calendrier(464, 22, pages=6)
    c27 = calendrier(477, 22, pages=6)
    now = maintenant_ms()
    print(f"  2026: {len(c26)} courses ; 2027: {len(c27)} courses")
    print("  2026 par classe:", Counter(c["ClassCode"] for c in c26).most_common())
    print("  2027 par classe:", Counter(c["ClassCode"] for c in c27).most_common())
    passes = [c for c in c26 + c27 if ms(c["EndDate"]) < now]
    print("  passees:", len(passes), "IsDone parmi passees:", Counter(c["IsDone"] for c in passes))
    print("  futures IsDone:", Counter(c["IsDone"] for c in c26 + c27 if ms(c["EndDate"]) >= now))
    print("  2027 premieres:", [(c["CompetitionName"], c["Date"], c["ClassCode"]) for c in c27[:6]])
    print("  2027 UWT/Pro:", [(c["CompetitionName"], c["Date"], c["ClassCode"]) for c in c27 if c["ClassCode"] in ("1.UWT", "2.UWT", "1.Pro", "2.Pro")][:12])
    # 1) derniers evenements passes (delai de publication)
    passes.sort(key=lambda c: ms(c["EndDate"]), reverse=True)
    print("\n  ==== 8 dernieres courses passees (aujourd'hui = %s) ====" % time.strftime("%Y-%m-%d", time.gmtime()))
    for c in passes[:6]:
        print("  *", resume_competition(c))
    # 2) couverture par classe (une course passee 2026 par classe, de preference francaise)
    print("\n  ==== couverture par classe ====")
    vus = set()
    for cl in ("1.Pro", "2.Pro", "1.1", "2.1", "1.2", "2.2", "CN", "CC"):
        cands = [c for c in c26 if c["ClassCode"] == cl and ms(c["EndDate"]) < now]
        cands.sort(key=lambda c: (c["CountryIsoCode3"] != "FRA", -ms(c["EndDate"])))
        if cands:
            print("  *", resume_competition(cands[0]))
    # 3) Paris-Roubaix + abandons + startlist
    print("\n  ==== Paris-Roubaix 2026 ====")
    races = (post_json("/iframe/Races/", kendo(taille=10, competitionId=76380, disciplineId=10)) or {}).get("data") or []
    rid = races[0]["Id"]
    evs = post_json("/iframe/Events/", {"disciplineId": 10, "raceId": rid})
    for e in evs:
        print("   event:", json.dumps({k: e[k] for k in ("EventId", "EventName", "WinnerName", "IsTeamEvent")}, ensure_ascii=False))
    eid = evs[0]["EventId"]
    j = post_json("/iframe/Results/", kendo(taille=3, disciplineId=10, eventId=eid))
    print("   total", j.get("total"))
    for r in j["data"]:
        print("   ", r["Rank"], r["DisplayName"], r["TeamName"], r["NationName"], r["ResultValue"], r["Irm"], r["Bib"])
    tot = j["total"]
    j2 = post_json("/iframe/Results/", kendo(page=max(1, tot // 40 + 1), taille=40, disciplineId=10, eventId=eid))
    print("   dernieres lignes :", [(r["Rank"], r["DisplayName"], r["ResultValue"], r["Irm"]) for r in j2["data"][-6:]])
    print("   Irm distincts page:", Counter(r["Irm"] for r in j2["data"]))
    for lt in (1, 2):
        c, t = post("/iframe/GetRiderList/", {"listTypeId": lt, "raceId": rid, "eventId": eid, "take": 3, "skip": 0, "page": 1, "pageSize": 3}, maxprint=700)
    # 4) abandons sur une etape du Tour
    print("\n  ==== TdF 2026 etape 8 (256552) : abandons / Irm ====")
    evs = post_json("/iframe/Events/", {"disciplineId": 10, "raceId": 256552})
    e0 = evs[0]
    j = post_json("/iframe/Results/", kendo(taille=1, disciplineId=10, eventId=e0["EventId"]))
    tot = j["total"]
    print("   ", e0["EventName"], "total", tot)
    j2 = post_json("/iframe/Results/", kendo(page=tot // 40 + 1, taille=40, disciplineId=10, eventId=e0["EventId"]))
    print("   dernieres lignes :", [(r["Rank"], r["DisplayName"], r["ResultValue"], r["Irm"]) for r in j2["data"][-6:]])
    print("   Irm distincts:", Counter(r["Irm"] for r in j2["data"]))
    # 5) Irm connus
    c, t = get("https://dataride.uci.org/iframe/GetIrms/", accept="application/json", maxprint=900)


if __name__ == "__main__":
    passe11()
