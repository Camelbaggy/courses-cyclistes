#!/usr/bin/env python3
"""Sonde temporaire (enrich) : structures HTML brutes, passe 2."""
import re, sys, collections
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


def head(t):
    for pat in (r"<title[^>]*>(.*?)</title>", r'<meta[^>]+name="description"[^>]+content="([^"]*)"',
                r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"'):
        m = re.search(pat, t, re.S | re.I)
        print("  head:", " ".join(m.group(1).split())[:200] if m else "-")
    yrs = collections.Counter(re.findall(r"\b(20[12]\d)\b", t))
    print("  années:", yrs.most_common(4))


def vis(t):
    b = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    b = re.sub(r"<[^>]+>", " ", b)
    import html
    return " ".join(html.unescape(b).split())


L = "https://www.letour.fr"
t = get(L + "/fr/classements/etape-10/itg")
head(t)
rows(t, (0, 1, 2, 3), 3200)
m = re.search(r"B\s*:", t)
print("CTX bonus:", " ".join(t[max(0, m.start() - 700):m.start() + 300].split()) if m else "pas de 'B :'")
for code in ("ipg", "img", "ijg", "ice", "ite"):
    t = get(f"{L}/fr/classements/etape-10/{code}")
    if t:
        print(" thead:", re.sub(r"\s+", " ", (re.search(r"<thead.*?</thead>", t, re.S) or [""])[0] if re.search(r"<thead.*?</thead>", t, re.S) else "")[:700])
        rows(t, (1, 2), 2200)
t = get(L + "/fr/classements/etape-10/etg")
rows(t, (1,), 1500)
t = get(L + "/fr/etape-10")
head(t)
i = t.find("stageHeader")
print("HEADER:", " ".join(re.sub(r"<[^>]+>", " ", t[i:i + 5000]).split())[:900])
v = vis(t)
k = v.find("Longueur")
print("VIS:", v[max(0, k - 500):k + 2500])
for pat in (r"Col d", r"climb|montée|ascension|difficult"):
    for m in list(re.finditer(pat, t))[:2]:
        print(f"CTX[{pat}]:", " ".join(t[max(0, m.start() - 300):m.start() + 500].split()))
t = get(L + "/fr/actus/2027/etape-10/annecy-sallanches/1356696")
if t:
    head(t)
    for pat in (r'<article', r'class="[^"]*(?:article|story|content)[^"]*"'):
        print(pat, [" ".join(x.split())[:100] for x in re.findall(pat, t)[:5]])
    v = vis(t)
    k = v.find("Annecy")
    print("VIS len", len(v), v[:1200])
    print("nb <p>:", t.count("<p"))
t = get(L + "/fr/actus")
if t:
    print("liens actus:", re.findall(r'href="(/fr/actus/2027/etape-10[^"]*)"', t)[:6])
R = "https://www.paris-roubaix.fr"
t = get(R + "/fr/classements")
head(t)
print(" thead:", re.sub(r"\s+", " ", re.search(r"<thead.*?</thead>", t, re.S).group(0))[:800])
rows(t, (1,), 2000)
t = get(R + "/fr/etape-1")
head(t)
i = t.find("stageHeader")
print("HEADER:", " ".join(re.sub(r"<[^>]+>", " ", t[i:i + 5000]).split())[:700])
for m in list(re.finditer(r"Début du secteur pavé", t))[:2]:
    print("SECT:", " ".join(t[max(0, m.start() - 800):m.start() + 900].split()))
print("thead itineraire:", re.sub(r"\s+", " ", " ".join(re.findall(r"<thead.*?</thead>", t, re.S)))[:800])
v = vis(t)
k = v.find("Secteur")
print("VIS secteurs:", v[k:k + 1500])
for u in ("/fr/classements/ipe", "/fr/etape-1/actus"):
    pass
P = "https://www.paris-nice.fr"
t = get(P + "/fr/etape-8")
if t:
    head(t)
    v = vis(t)
    k = v.find("Col de la Porte")
    print("VIS col:", v[max(0, k - 300):k + 900])
    i = t.find("stageHeader")
    print("HEADER:", " ".join(re.sub(r"<[^>]+>", " ", t[i:i + 5000]).split())[:600])
t = get(P + "/fr/parcours-general")
if t:
    head(t)
    rows(t, (1,), 800)
t = get("https://www.criterium-du-dauphine.fr/fr/classements")
if t:
    head(t)
t = get("https://www.lavuelta.es/fr/classements")
if t:
    head(t)
for d in ("https://www.paris-tours.fr/fr/classements", "https://www.paris-tours.fr/en/rankings",
          "https://www.fleche-wallonne.be/fr/classements", "https://www.fleche-wallonne.be/", "https://www.laflechewallonne.be/fr/classements"):
    t = get(d)
    if t:
        head(t)
