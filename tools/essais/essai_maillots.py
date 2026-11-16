#!/usr/bin/env python3
"""Sonde : maillots et logos d'équipes saison par saison (Wikipédia fr / en, Wikimedia Commons, Wikidata).

Pour un échantillon d'équipes-saisons, cherche : (a) l'infobox de l'article de saison sur fr.wikipedia (« <Équipe> <année> ») et
en.wikipedia (« <année> <Équipe> season ») et les fichiers qu'elle cite ; (b) les fichiers Commons trouvés par recherche
(« <équipe> <année> jersey / maillot / kit ») avec leur licence ; (c) l'élément Wikidata de la saison et ses propriétés « fichier ».
Lecture seule, 1 requête/s par hôte (netutil), rien n'est écrit.
"""
import re
import sys
import urllib.parse

sys.path.insert(0, ".")
import netutil  # noqa: E402

ECHANTILLON = [
    ("Movistar Team", 2024), ("Movistar Team", 2019), ("Decathlon AG2R La Mondiale", 2024), ("Groupama-FDJ", 2021),
    ("Lotto Dstny", 2024), ("Alpecin-Deceuninck", 2023), ("UAE Team Emirates", 2022), ("TotalEnergies", 2025),
    ("Arkéa-Samsic", 2023), ("Corendon-Circus", 2019), ("Q36.5 Pro Cycling Team", 2025), ("Team Jumbo-Visma", 2022),
]


def api(hote, **p):
    p.update(format="json", formatversion="2")
    return netutil.fetch_json(f"https://{hote}/w/api.php?" + urllib.parse.urlencode(p), attendre_429=True)


def fichiers_wikitexte(txt):
    return sorted(set(m.strip() for m in re.findall(r"([^=|\[\]{}\n:]+\.(?:svg|png|jpg|jpeg|gif))", txt or "", re.I)))


def infobox(hote, page):
    r = api(hote, action="parse", page=page, prop="wikitext|images", section=0, redirects=1)
    if not r or "parse" not in r:
        print(f"  {hote} « {page} » : absent ({(r or {}).get('error', {}).get('code')})")
        return []
    wt = r["parse"].get("wikitext") or ""
    m = re.search(r"\{\{\s*(Infobox[^|\n]*)", wt, re.I)
    print(f"  {hote} « {r['parse']['title']} » : infobox={m.group(1).strip() if m else None}")
    params = re.findall(r"^\s*\|\s*([^=\n]+?)\s*=\s*(.*)$", wt, re.M)
    for k, v in params:
        if re.search(r"maillot|jersey|kit|logo|image|body|arms|shorts|pattern", k, re.I) and v.strip():
            print(f"    | {k} = {v.strip()[:140]}")
    imgs = r["parse"].get("images") or []
    print(f"    images de la section : {imgs[:12]}")
    return imgs


def licences(noms):
    noms = [n if n.startswith("File:") else "File:" + n for n in noms][:50]
    if not noms:
        return
    r = api("commons.wikimedia.org", action="query", titles="|".join(noms), prop="imageinfo", iiprop="url|extmetadata|size")
    for p in (r or {}).get("query", {}).get("pages", []):
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata") or {}
        lic = (md.get("LicenseShortName") or {}).get("value")
        print(f"      {p['title'][:90]} : {'ABSENT de Commons' if p.get('missing') else lic} {ii.get('width')}x{ii.get('height')}")


def recherche_commons(eq, an):
    for q in (f"{eq} {an} jersey", f"{eq} {an} maillot", f"{eq} {an} kit"):
        r = api("commons.wikimedia.org", action="query", list="search", srnamespace=6, srlimit=8, srsearch=q)
        t = [x["title"] for x in (r or {}).get("query", {}).get("search", [])]
        print(f"  Commons « {q} » : {t}")


def wikidata_saison(eq, an):
    r = api("www.wikidata.org", action="wbsearchentities", search=f"{eq} {an}", language="fr", limit=5, type="item")
    for c in (r or {}).get("search", [])[:3]:
        e = api("www.wikidata.org", action="wbgetentities", ids=c["id"], props="claims|descriptions", languages="en|fr")
        ent = ((e or {}).get("entities") or {}).get(c["id"], {})
        med = {pid: [s["mainsnak"].get("datavalue", {}).get("value") for s in v]
               for pid, v in (ent.get("claims") or {}).items() if v and v[0]["mainsnak"].get("datatype") == "commonsMedia"}
        desc = (ent.get("descriptions") or {}).get("en", {}).get("value")
        print(f"  Wikidata {c['id']} « {c.get('label')} » ({desc}) : P31={[s['mainsnak'].get('datavalue', {}).get('value', {}).get('id') for s in (ent.get('claims') or {}).get('P31', [])]} médias={med}")


def main():
    for eq, an in ECHANTILLON:
        print(f"\n##### {eq} {an}")
        f1 = infobox("fr.wikipedia.org", f"{eq} {an}")
        f2 = infobox("en.wikipedia.org", f"{an} {eq} season")
        cand = [x for x in f1 + f2 if re.search(r"maillot|jersey|kit|logo|body|arms|shorts", x, re.I)]
        if cand:
            print("    licences des fichiers candidats :")
            licences(cand)
        recherche_commons(eq, an)
        wikidata_saison(eq, an)


if __name__ == "__main__":
    main()
