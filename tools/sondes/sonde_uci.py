"""Sonde UCI (bibliothèque standard uniquement) : découvre les endpoints publics de uci.org / dataride.uci.ch.
User-Agent honnête, pause >= 1 s entre requêtes, aucun contournement (challenge / 403 : on note et on s'arrête)."""
import re, sys, time, json, urllib.request, urllib.error

UA = "courses-cyclistes-sonde/0.1 (projet personnel non commercial)"
_last = [0.0]
STOP = [False]


def get(url, accept="*/*", maxprint=600, show=True, data=None, headers=None):
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
        r = urllib.request.urlopen(req, timeout=30)
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
    if not isinstance(j, dict):
        print("  (pas du JSON)")
        return []
    data = j.get("data") or []
    print(f"  total={j.get('total')} len(data)={len(data)} cles={sorted(data[0].keys()) if data else None}")
    for r in data[:n]:
        print("  ex:", json.dumps(r, ensure_ascii=False)[:maxc])
    return data


def passe8():
    from collections import Counter
    base = "https://dataride.uci.org"
    code, t = get(base + "/iframe/GetRestrictedResultsDisciplineSeasons/?disciplineId=10", accept="application/json", maxprint=1200)
    try:
        saisons = json.loads(t)
    except Exception:
        return
    cible = {}
    for x in saisons:
        for an in ("2025", "2026", "2027"):
            if an in str(x.get("Name")):
                cible[an] = x["Id"]
    print("  saisons retenues:", cible)
    sid = cible.get("2026")
    if sid is None:
        return
    code, t = get(f"{base}/iframe/GetRestrictedResultsCategories/?disciplineId=10&disciplineSeasonId={sid}", accept="application/json", maxprint=1500)
    get(f"{base}/iframe/GetRestrictedResultsRaceTypes/?disciplineId=10&disciplineSeasonId={sid}", accept="application/json", maxprint=1500)
    try:
        cat = next(c["Id"] for c in json.loads(t) if c.get("Name") == "Men Elite")
    except Exception:
        cat = None
    print("  categorie Men Elite:", cat)
    flt = [("SeasonId", sid)] + ([("CategoryId", cat)] if cat is not None else [])
    comps = []
    essais = {
        "A kendo filtres sans tri": lambda pg: kendo(page=pg, taille=100, filtres=flt),
        "B kendo filtres + tri": lambda pg: kendo(page=pg, taille=100, filtres=flt, tri=("StartDate", "asc")),
        "C compact DataSourceRequest": lambda pg: {"page": pg, "pageSize": 100, "sort": "StartDate-asc",
                                                    "filter": "~and~".join(f"{c}~eq~{v}" for c, v in flt)},
        "D champs a plat": lambda pg: {"page": pg, "pageSize": 100, "take": 100, "skip": (pg - 1) * 100,
                                        **{c: v for c, v in flt}, "disciplineId": 10},
        "E kendo filtres, operateur contains-free (sans logic)": lambda pg: {k: v for k, v in kendo(page=pg, taille=100, filtres=flt).items() if k != "filter[logic]"},
    }
    choisi = None
    for nom, f in essais.items():
        print("\n  ### essai", nom)
        code, t = post("/iframe/Competitions/", f(1), maxprint=0)
        try:
            j = json.loads(t)
        except Exception:
            print("  non JSON :", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))[:500])
            continue
        print("  JSON total =", j.get("total"))
        if j.get("total"):
            choisi = f
            break
    if choisi:
        for pg in (1, 2, 3, 4):
            j = post_json("/iframe/Competitions/", choisi(pg))
            data = montrer(j, n=2 if pg == 1 else 0)
            comps += data
            if not data or len(comps) >= (j or {}).get("total", 0):
                break
    print("  total recupere:", len(comps))
    print("  par ClassCode:", Counter(c.get("ClassCode") for c in comps).most_common())
    print("  par CategoryCode:", Counter(c.get("CategoryCode") for c in comps).most_common(6))
    cles = {}
    for mot in ("paris-roubaix", "tour de france", "paris-nice", "paris - nice"):
        for c in comps:
            nom = str(c.get("CompetitionName")).lower()
            if mot in nom and "women" not in nom and "femmes" not in nom:
                print("  >>", json.dumps(c, ensure_ascii=False)[:500])
                cles.setdefault(mot, c)
    for mot, c in cles.items():
        cid = c.get("CompetitionId")
        print(f"\n######## {mot} -> {cid}")
        j = post_json("/iframe/Races/", kendo(taille=60, competitionId=cid, disciplineId=10))
        races = montrer(j, n=1, maxc=700)
        if not races:
            continue
        for r in ((races[0], races[-1]) if len(races) > 1 else (races[0],)):
            j = post_json("/iframe/Events/", {"disciplineId": 10, "raceId": r["Id"]})
            evs = montrer(j, n=3, maxc=500)
            for e in evs[:2]:
                eid = e.get("Id") or e.get("EventId")
                jr = post_json("/iframe/Results/", kendo(taille=5, disciplineId=10, eventId=eid))
                print(f"  -- Results eventId={eid}")
                montrer(jr, n=2, maxc=900)


if __name__ == "__main__":
    passe8()
