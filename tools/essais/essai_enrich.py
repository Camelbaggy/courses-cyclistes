#!/usr/bin/env python3
"""Essai réseau des modules d'enrichissement : aso, lnc, directvelo, cyclingnews (cas réels, extraits compacts)."""
import html
import re
import sys

sys.path.insert(0, ".")
import netutil  # noqa: E402
import aso  # noqa: E402
import lnc  # noqa: E402
import directvelo  # noqa: E402
import cyclingnews  # noqa: E402


def titre(t):
    print(f"\n##### {t}")


def show_rows(rows, n=5):
    print(f"  {len(rows)} lignes")
    for r in rows[:n]:
        print("   ", {k: v for k, v in r.items() if v is not None})
    vides = {k: sum(1 for r in rows if r.get(k) is None) for k in ("rank", "bib", "name", "team", "nationality", "time_s", "gap_s", "bonus_s", "penalty_s", "points")}
    print("  champs vides:", {k: v for k, v in vides.items() if v})


def show_route(r):
    if not r:
        print("  route: None")
        return
    print("  route:", {k: v for k, v in r.items() if k not in ("climbs", "cobbles")})
    print(f"  cols: {len(r['climbs'])}", r["climbs"][:2])
    print(f"  pavés: {len(r['cobbles'])}", r["cobbles"][:3], "...", r["cobbles"][-1:] if r["cobbles"] else "")


def show_text(t):
    print("  texte:", None if t is None else f"{len(t)} caractères")
    if t:
        print("  >", t[:300].replace("\n", " ⏎ "))


# ---------------------------------------------------------------- ASO
titre("ASO : édition servie / match_race")
for site in ("tdf", "parisnice", "dauphine", "roubaix", "liege", "paristours", "vuelta"):
    print(f"  {site}: édition servie {aso.edition_year(site)}")
print("  match Tour 2026 :", aso.match_race("Tour de France", "2026-07-04"))
tdf = aso.match_race("Tour de France", "2027-07-02")
print("  match Tour 2027 :", tdf)
print("  match Paris-Roubaix Hauts-de-France 2026 :", aso.match_race("Paris-Roubaix Hauts-de-France", "2026-04-12"))
print("  match Tour de Burgos :", aso.match_race("Vuelta a Burgos", "2026-08-04"), "| Tour de France Femmes :", aso.match_race("Tour de France Femmes avec Zwift", "2026-08-01"))
tdf = tdf or {"site": "tdf", "base": aso.SITES["tdf"]["base"], "slug": "tdf", "year": 2027}

titre("ASO Tour (édition servie) étape 10 : classements")
for code in ("ite", "itg", "ipg", "img", "ijg", "etg", "ice"):
    print(f" -- {code}")
    show_rows(aso.get_classification(tdf, 10, code), 3 if code != "itg" else 5)
titre("ASO Tour étape 10 : parcours et récit")
show_route(aso.get_route(tdf, 10))
show_text(aso.get_story(tdf, 10))
titre("ASO Tour : enrich_stage sur une étape synthétique (lignes UCI simulées par dossard/nom)")
ite = aso.get_classification(tdf, 10, "ite")
itg = aso.get_classification(tdf, 10, "itg")


def fake(rows, n):
    out = []
    for r in rows[:n]:
        out.append({"rank": r["rank"], "status": None, "bib": r["bib"], "rider_id": netutil.slugify(r["name"]) + "-19900101",
                    "time_s": r["time_s"], "gap_s": r["gap_s"], "points": None, "bonus_s": None, "penalty_s": None, "uci_points": None})
    return out


stg = {"number": 10, "results": {"stage": fake(ite, 40), "gc": fake(itg, 40), "teams": []}, "route": None}
stg["results"]["stage"][0]["bib"] = None  # force le rapprochement par nom
stg["results"]["stage"][1]["bonus_s"] = 1  # force une divergence
aso.enrich_stage(tdf, 10, stg)
print("  bonus étape (10 premiers):", [r["bonus_s"] for r in stg["results"]["stage"][:10]])
print("  pénalités gc non nulles:", [(r["rider_id"], r["penalty_s"]) for r in stg["results"]["gc"] if r["penalty_s"]][:3])
print("  teams:", len(stg["results"]["teams"]), stg["results"]["teams"][:2], "| route:", bool(stg["route"]))

titre("ASO Paris-Roubaix (course d'un jour)")
rx = aso.match_race("Paris-Roubaix Hauts-de-France", "2026-04-12") or {"site": "roubaix", "base": aso.SITES["roubaix"]["base"]}
show_rows(aso.get_classification(rx, None, "ite"), 5)
show_route(aso.get_route(rx, None))
show_text(aso.get_story(rx, None))

titre("ASO Paris-Nice 2026 étape 8 / Paris-Tours 2026 / Dauphiné 2026 étape 8")
pn = aso.match_race("Paris-Nice", "2026-03-08")
print("  match Paris-Nice:", pn)
pn = pn or {"site": "parisnice", "base": aso.SITES["parisnice"]["base"]}
show_route(aso.get_route(pn, 8))
show_rows(aso.get_classification(pn, 8, "itg"), 3)
show_text(aso.get_story(pn, 8))
pt = aso.match_race("Paris-Tours", "2026-10-11")
print("  match Paris-Tours:", pt)
pt = pt or {"site": "paristours", "base": aso.SITES["paristours"]["base"]}
show_route(aso.get_route(pt, None))
show_rows(aso.get_classification(pt, None, "ite"), 3)
show_text(aso.get_story(pt, None))
dp = {"site": "dauphine", "base": aso.SITES["dauphine"]["base"]}
show_route(aso.get_route(dp, 8))
show_rows(aso.get_classification(dp, 8, "itg"), 3)

# ---------------------------------------------------------------- LNC
titre("LNC")
res = lnc.get_fdj_united_series()
if res:
    print("  individuel:", len(res["individual"]), res["individual"][:5])
    print("  manches:", len(res["races"]), res["races"][:5])
else:
    print("  None")
page = netutil.fetch_text(lnc.BASE + "/fdj-united-series")
if page:
    hrefs = sorted(set(re.findall(r'href="([^"#]+)"', page)))
    print("  hrefs (hors médias):", [h for h in hrefs if not re.search(r"\.(png|jpg|webp|css|js|svg)", h)][:60])
    v = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S))).split())
    k = v.find("Calendrier")
    print("  VIS 'Calendrier':", v[k:k + 600] if k >= 0 else "absent")
    for m in list(re.finditer(r"20\d\d-\d\d-\d\d|\d\d/\d\d/20\d\d|\d{1,2} (?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre)", v))[:3]:
        print("  date ctx:", v[max(0, m.start() - 200):m.start() + 200])
lst = netutil.fetch_text(lnc.BASE + "/resultats?french_cup=1")
if lst:
    v = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", lst, flags=re.S))).split())
    k = v.find("Polynormande")
    print("  liste french_cup VIS:", v[max(0, k - 400):k + 500] if k >= 0 else v[:800])
    print("  hrefs resultats:", sorted(set(re.findall(r'href="(/resultats/[^"#]+)"', lst)))[:15])

# ---------------------------------------------------------------- DirectVélo
titre("DirectVélo : Paris-Tours 2026-10-11")
t = directvelo.find_story("Paris-Tours", "2026-10-11")
show_text(t)
for u, p in directvelo._PAGES.items():
    print("  page:", u, None if p is None else len(p))
arts = [u for u in directvelo._PAGES if "/actualite/" in u]
if arts and directvelo._PAGES[arts[0]] and not t:
    p = directvelo._PAGES[arts[0]]
    i = p.find("<h1")
    print("  RAW article:", " ".join(p[i:i + 1800].split()))
elif arts and directvelo._PAGES[arts[0]]:
    p = directvelo._PAGES[arts[0]]
    i = p.find("<h1")
    print("  RAW article (extrait):", " ".join(p[i:i + 700].split()))

# ---------------------------------------------------------------- Cyclingnews
titre("Cyclingnews")
items = cyclingnews.fetch_items()
print(f"  {len(items)} articles ; dates {sorted(set(i['date'] for i in items if i['date']))}")
lens = [len(i["text"]) for i in items]
print("  longueurs texte min/médiane/max:", min(lens) if lens else None, sorted(lens)[len(lens) // 2] if lens else None, max(lens) if lens else None)
for i in items[:5]:
    print("   ", i["date"], i["categories"][:3], i["title"][:80])
tested = 0
for i in items:
    if "Racing" in i["categories"] and tested < 3:
        name = " ".join(re.findall(r"[A-Za-zÀ-ÿ']+", i["title"])[:3])
        s = cyclingnews.find_story(items, name, i["date"], None)
        print(f"  find_story('{name}', {i['date']}) ->", None if s is None else (len(s), s[:80].replace("\n", " ")))
        tested += 1
print("  find_story Paris-Roubaix 2026-04-12 ->", cyclingnews.find_story(items, "Paris-Roubaix", "2026-04-12", None))
