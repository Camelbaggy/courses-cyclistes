#!/usr/bin/env python3
"""Sonde temporaire (enrich) : structures HTML brutes, passe 3."""
import re, sys, html
sys.path.insert(0, ".")
import netutil


def get(u):
    t = netutil.fetch_text(u, retries=1)
    print(f"\n=== {u} -> {'None' if t is None else len(t)}")
    return t


def rows(t, idxs=(0,), w=3000):
    trs = re.findall(r"<tr\b.*?</tr>", t, re.S | re.I)
    print("nb tr:", len(trs))
    for i in idxs:
        if i < len(trs):
            print(f"TR[{i}]:", re.sub(r"\s+", " ", trs[i])[:w])


def cells(t, i):
    trs = re.findall(r"<tr\b.*?</tr>", t, re.S | re.I)
    tds = re.findall(r"<t[dh]\b.*?</t[dh]>", trs[i], re.S)
    print(f"CELLS[{i}]:", [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in tds])


def vis(t):
    b = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    b = re.sub(r"<[^>]+>", " ", b)
    return " ".join(html.unescape(b).split())


def ctx(t, pat, w=1200, n=1, before=300):
    for m in list(re.finditer(pat, t, re.S | re.I))[:n]:
        print(f"CTX[{pat}]:", " ".join(t[max(0, m.start() - before):m.start() + w].split()))


L = "https://www.letour.fr"
for code in ("itg", "ipg", "img"):
    t = get(f"{L}/fr/classements/etape-10/{code}")
    print(" thead:", [" ".join(x.split()) for x in re.findall(r"<th[^>]*>(.*?)</th>", t, re.S)])
    cells(t, 1); cells(t, 2)
    m = re.search(r"P\s*:\s*\d", t)
    print(" penalty ctx:", " ".join(t[max(0, m.start() - 200):m.start() + 100].split()) if m else "aucun 'P :'")
t = get(L + "/fr/classements/etape-10/ite")
m = re.search(r"P\s*:\s*\d", t)
print(" penalty ite ctx:", " ".join(t[max(0, m.start() - 300):m.start() + 100].split()) if m else "aucun 'P :'")
print(" ite nb 'B :'", len(re.findall(r"B\s*:", t)))
# dernières lignes (abandons ?)
trs = re.findall(r"<tr\b.*?</tr>", t, re.S)
cells(t, len(trs) - 1)
P = "https://www.paris-nice.fr"
t = get(P + "/fr/etape-8")
ctx(t, r"7\s*km de mont", 900, 2, 1200)
ctx(t, r"<h1", 400)
print("liens actus:", sorted(set(re.findall(r'href="(/fr/actus/[^"]+)"', t)))[:8])
for u in re.findall(r'href="(/fr/actus/2026/etape-8/[^"]+)"', t)[:1]:
    a = get(P + u)
    if a:
        ctx(a, r"Au matin de la", 700, 1, 900)
        print("nb <p>:", a.count("<p"), "| h1:", re.findall(r"<h1[^>]*>(.*?)</h1>", a, re.S)[:1])
        print("classes parents des p:", sorted(set(re.findall(r'<div class="([^"]*)">\s*<p', a)))[:8])
        print("bloc article:", [x for x in re.findall(r'class="([^"]*(?:text|body|article|chapo|wysiwyg)[^"]*)"', a)][:10])
R = "https://www.paris-roubaix.fr"
t = get(R + "/fr/etape-1")
trs = [x for x in re.findall(r"<tr\b.*?</tr>", t, re.S) if "secteur" in x.lower()]
print("lignes secteur:", len(trs))
for x in trs[:2] + trs[-1:]:
    print("  ", " ".join(html.unescape(re.sub(r"<[^>]+>", " ", x)).split()))
ctx(t, r"[Ss]ecteurs? pav", 700, 3, 100)
ctx(t, r"\*\*|étoile|star|difficult", 500, 2, 200)
print("liens actus:", sorted(set(re.findall(r'href="(/fr/actus/[^"]+)"', t)))[:6])
print("pictos:", sorted(set(re.findall(r'class="(itinerary__picto[^"]*|picto[^"]*)"', t)))[:12])
T = "https://www.paris-tours.fr"
t = get(T + "/fr/etape-1")
if t:
    print("title:", re.findall(r"<title>(.*?)</title>", t, re.S)[:1], "| nb tr:", t.count("<tr"))
    print("VIS:", vis(t)[600:1500])
t = get(T + "/fr/classements")
cells(t, 1)
D = "https://www.criterium-du-dauphine.fr"
t = get(D + "/fr/etape-8")
if t:
    print("title:", re.findall(r"<title>(.*?)</title>", t, re.S)[:1])
    ctx(t, r"Longueur", 300)
t = get(D + "/fr/parcours-general")
if t:
    rows(t, (1,), 700)
# LNC
N = "https://www.lncpro.fr"
t = get(N + "/fdj-united-series")
if t:
    print("title:", re.findall(r"<title>(.*?)</title>", t, re.S)[:1])
    v = vis(t)
    k = v.find("Classement")
    print("VIS:", v[k:k + 1500])
    ctx(t, r"result-item", 1500, 2, 100)
    print("liens courses:", sorted(set(re.findall(r'href="(/resultats/[^"]+)"', t)))[:12])
t = get(N + "/resultats/paris-tours-elite")
if t:
    v = vis(t)
    k = v.find("Paris-Tours")
    print("VIS:", v[k:k + 600])
# DirectVélo
V = "https://www.directvelo.com"
t = get(V + "/epreuve/48914/paris-tours-2026")
if t:
    print("title:", re.findall(r"<title>(.*?)</title>", t, re.S)[:1])
    print("liens actu:", sorted(set(re.findall(r'href="([^"]*(?:actualite|compte|recit|reportage)[^"]*)"', t)))[:15])
    print("tous liens uniques types:", sorted(set(re.sub(r"\d+", "N", x) for x in re.findall(r'href="(/[^"]*)"', t)))[:40])
    v = vis(t)
    for kw in ("Résumé", "résumé", "compte rendu", "Récit", "Le récit", "Présentation"):
        k = v.find(kw)
        if k >= 0:
            print(f"VIS[{kw}]:", v[max(0, k - 100):k + 500])
