#!/usr/bin/env python3
"""Sonde temporaire (enrich) : structures HTML brutes."""
import re, sys
sys.path.insert(0, ".")
import netutil


def get(u):
    t = netutil.fetch_text(u, retries=1)
    print(f"\n=== {u} -> {'None' if t is None else len(t)}")
    return t


def ctx(t, pat, w=1500, n=1, before=100):
    for m in list(re.finditer(pat, t, re.S | re.I))[:n]:
        a = max(0, m.start() - before)
        print("CTX[%s]: %s" % (pat, " ".join(t[a:a + w].split())))


L = "https://www.letour.fr"
t = get(L + "/fr/classements/etape-10/itg")
if t:
    ctx(t, r"<tbody", 2800)
    ctx(t, r"<h1", 300)
    ctx(t, r"<title", 200)
t = get(L + "/fr/classements/etape-10/img")
if t:
    ctx(t, r"<tbody", 1800)
t = get(L + "/fr/classements/etape-10/etg")
if t:
    ctx(t, r"<tbody", 1500)
t = get(L + "/fr/etape-10")
if t:
    ctx(t, r"Distance|Longueur|D\+|dénivel", 600, 3)
    print("liens actus:", re.findall(r'href="(/fr/actus/[^"]+)"', t)[:8])
    print("liens etape:", sorted(set(re.findall(r'href="(/fr/[^"]*(?:parcours|etape)[^"]*)"', t)))[:15])
t = get(L + "/fr/parcours-general")
if t:
    ctx(t, r"<tbody", 1500)
    ctx(t, r"<title", 200)
for u in ("/fr/classements/2025/etape-10/itg", "/fr/2025/classements/etape-10/itg", "/fr/archives", "/fr/histoire",
          "/fr/classements/etape-10/itg?year=2025", "/fr/palmares"):
    get(L + u)
R = "https://www.paris-roubaix.fr"
t = get(R + "/fr/classements")
if t:
    ctx(t, r"<tbody", 1800)
    ctx(t, r"<title", 200)
    print("tous codes:", sorted(set(re.findall(r'data-types="([^"]+)"', t)))[:5])
t = get(R + "/fr/etape-1")
if t:
    ctx(t, r"secteur", 900, 2)
    ctx(t, r"<tbody", 1500)
get(R + "/fr/parcours")
t = get("https://www.paris-tours.fr/")
if t:
    ctx(t, r"<title", 200)
    print("liens:", sorted(set(re.findall(r'href="([^"]*(?:classement|parcours|course)[^"]*)"', t)))[:10])
t = get("https://www.liege-bastogne-liege.be/fr/classements")
if t:
    ctx(t, r"<title", 200)
    ctx(t, r"<tbody", 1200)
