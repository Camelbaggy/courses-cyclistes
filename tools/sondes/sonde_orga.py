#!/usr/bin/env python3
"""Sonde 2 : sites d'organisateurs (ASO, RCS), DirectVélo, Cyclingnews RSS.

Bibliothèque standard uniquement. Respecte robots.txt (vérifié avant chaque requête, jokers * et $ gérés),
User-Agent honnête, pause >= 1 s entre requêtes, aucun contournement : un 403/challenge est noté, on n'insiste pas.
Usage : python tools/sondes/sonde_orga.py [groupe ...]   (sans argument : tous les groupes)
"""
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

UA = "courses-cyclistes-sonde/0.1 (projet personnel non commercial)"
PAUSE = 1.2
MAX_BYTES = 1_500_000
_robots = {}
_last = [0.0]
DELAYS = {"www.directvelo.com": 10.5}  # Crawl-delay: 10 déclaré dans robots.txt


def _rules(host_url):
    """Règles robots.txt du groupe '*' (ou du groupe nommé contenant 'courses-cyclistes')."""
    if host_url in _robots:
        return _robots[host_url]
    rules = []
    try:
        st, _, body = raw_get(host_url + "/robots.txt", check=False)
        if st == 200:
            applies = False
            seen_rule = False
            for line in body.splitlines():
                line = line.split("#")[0].strip()
                if ":" not in line:
                    continue
                k, v = [x.strip() for x in line.split(":", 1)]
                k = k.lower()
                if k == "user-agent":
                    if seen_rule:
                        applies = False
                        seen_rule = False
                    if v == "*":
                        applies = True
                elif applies and k in ("disallow", "allow"):
                    seen_rule = True
                    if v:
                        rules.append((k, v))
    except Exception as e:  # noqa: BLE001
        print(f"  [robots] erreur {host_url}: {e}")
    _robots[host_url] = rules
    return rules


def _match(pattern, path):
    rx = re.escape(pattern).replace(r"\*", ".*")
    if rx.endswith(r"\$"):
        rx = rx[:-2] + "$"
    return re.match(rx, path) is not None


def allowed(url):
    p = urllib.parse.urlparse(url)
    path = p.path + ("?" + p.query if p.query else "")
    best = ("allow", "")
    for kind, pat in _rules(f"{p.scheme}://{p.netloc}"):
        if _match(pat, path) and len(pat) >= len(best[1]):
            if len(pat) > len(best[1]) or kind == "allow":
                best = (kind, pat)
    return best[0] == "allow", best[1]


def raw_get(url, check=True):
    if check:
        ok, pat = allowed(url)
        if not ok:
            return -1, "", f"INTERDIT par robots.txt (règle {pat})"
    host = urllib.parse.urlparse(url).netloc
    wait = (DELAYS.get(host, PAUSE)) - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml,*/*;q=0.8",
                                               "Accept-Encoding": "gzip", "Accept-Language": "fr,en;q=0.7"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            data, status, ctype, hdr = r.read(MAX_BYTES), r.status, r.headers.get("Content-Type", ""), r.headers
    except urllib.error.HTTPError as e:
        data, status, ctype, hdr = e.read(MAX_BYTES), e.code, e.headers.get("Content-Type", ""), e.headers
    except Exception as e:  # noqa: BLE001
        _last[0] = time.time()
        return 0, "", f"ERREUR {e}"
    _last[0] = time.time()
    if hdr.get("Content-Encoding") == "gzip":
        try:
            data = gzip.decompress(data)
        except Exception:  # noqa: BLE001
            pass
    return status, ctype, data.decode("utf-8", "replace")


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.cur, self.row, self.cell, self.depth = [], None, None, None, 0
        self.rank_tags = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cl = (a.get("class") or "") + " " + (a.get("id") or "")
        if re.search(r"rank|classement|result|standing", cl, re.I) and len(self.rank_tags) < 12:
            self.rank_tags.append(f"<{tag} class/id=\"{cl.strip()[:80]}\">")
        if tag == "table":
            self.cur = []
        elif tag == "tr" and self.cur is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None and self.cur is not None:
            self.cur.append(self.row)
            self.row = None
        elif tag == "table" and self.cur is not None:
            self.tables.append(self.cur)
            self.cur = None

    def handle_data(self, d):
        if self.cell is not None:
            self.cell.append(d)


def analyse(body, nrows=4, ntables=4):
    out = []
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    out.append("  titre: " + (" ".join(m.group(1).split())[:150] if m else "-"))
    p = Tables()
    try:
        p.feed(body)
    except Exception as e:  # noqa: BLE001
        out.append(f"  parse HTML: {e}")
    out.append(f"  <table>: {len(p.tables)}")
    for i, t in enumerate(p.tables[:ntables]):
        out.append(f"   table {i}: {len(t)} lignes")
        for r in t[:nrows]:
            out.append("    | " + " | ".join(c[:28] for c in r)[:240])
    if p.rank_tags:
        out.append("  balises rank/classement/result: " + " ".join(p.rank_tags[:8])[:600])
    for pat, nom in ((r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.{0,300})', "__NEXT_DATA__"),
                     (r'<script[^>]*application/ld\+json[^>]*>(.{0,300})', "ld+json"),
                     (r'(window\.__[A-Z_]+__\s*=\s*.{0,200})', "state global"),
                     (r'(data-(?:ranking|results?|url|href)[^=]*="[^"]{0,120}")', "data-attr")):
        ms = re.findall(pat, body, re.S)
        if ms:
            out.append(f"  {nom} ({len(ms)}): " + " ".join(ms[0].split())[:300])
    return "\n".join(out)


def links(body, base, pattern, limit=40):
    seen = []
    for h in re.findall(r'href="([^"#]+)"', body):
        u = urllib.parse.urljoin(base, h.replace("&amp;", "&"))
        if re.search(pattern, u, re.I) and u not in seen:
            seen.append(u)
    return seen[:limit]


def probe(url, link_pat=None, raw_re=None, text=0, ctx=(), maxlinks=40, ctxw=600, vctx=(), vw=700, **kw):
    print(f"\n=== {url}")
    st, ct, body = raw_get(url)
    if st <= 0:
        print("  ", body if isinstance(body, str) else st)
        return None
    if st == -1:
        pass
    print(f"  HTTP {st} | {ct} | {len(body)} o")
    if st != 200 or not body:
        print("  extrait:", " ".join(body[:200].split()))
        if re.search(r"just a moment|captcha|access denied|challenge", body[:3000], re.I):
            print("  -> challenge/anti-robot : on s'arrête sur cette source")
        return None
    print(analyse(body, **kw))
    if link_pat:
        ls = links(body, url, link_pat, maxlinks)
        print(f"  liens ({link_pat}): {len(ls)}")
        for l in ls:
            print("    ", l)
    if raw_re:
        for m in re.findall(raw_re, body, re.S | re.I)[:6]:
            print("  motif:", " ".join(str(m).split())[:300])
    if text:
        print("  TEXTE:", visible(body)[:text])
    for c in ctx:
        for m in list(re.finditer(c, body, re.S | re.I))[:3]:
            a = max(0, m.start() - 150)
            print(f"  CTX[{c}]:", " ".join(body[a:m.end() + 350].split())[:ctxw])
    if vctx:
        v = visible(body)
        for c in vctx:
            for m in list(re.finditer(c, v, re.I))[:3]:
                a = max(0, m.start() - 200)
                print(f"  VCTX[{c}]:", v[a:m.end() + vw])
    return body


def visible(body):
    b = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    b = re.sub(r"<[^>]+>", " ", b)
    import html
    return " ".join(html.unescape(b).split())


def robots_dump(host):
    print(f"\n=== {host}/robots.txt")
    st, ct, body = raw_get(host + "/robots.txt", check=False)
    print(f"  HTTP {st} | {len(body)} o")
    print("\n".join("  " + l for l in body.splitlines()[:45]))


GROUPES = {}


def groupe(f):
    GROUPES[f.__name__] = f
    return f


@groupe
def aso_tour():
    L = "https://www.letour.fr"
    probe(L + "/fr/classements/etape-10/ite", nrows=1, ntables=1, ctx=(r"<tbody",), ctxw=1800)
    probe(L + "/en/stage-10", nrows=1, ntables=1, ctx=(r"mountain__infos", r"Km \d+"), ctxw=500,
          vctx=(r"Length 171 km", r"Presentation"), vw=1200)
    probe(L + "/en/news/2027/stage-10/annecy-sallanches-2/1356730", vctx=(r"Annecy > Sallanches[^.]{0,40}\.",), vw=1800)
    probe(L + "/fr/", maxlinks=60, link_pat=r"letour\.fr/(fr|en)/[a-z0-9-]+/?$")
    # robots : /fr/ajax interdit -> on ne touche pas


@groupe
def aso_autres():
    P = "https://www.paris-nice.fr"
    probe(P + "/fr/etape-8", nrows=1, ntables=1, vctx=(r"Film de l.étape", r"Enjeux|Col de la Porte"), vw=1500)
    probe(P + "/fr/actus/2026/etape-8/vingegaard-la-grande-razzia/25347", vctx=(r"Vingegaard, la grande razzia (?!--)[A-Z]",), vw=2200)
    probe(P + "/fr/classements/etape-1/ite", nrows=3, ntables=1)
    probe(P + "/fr/classements/etape-8/ijg", nrows=3, ntables=1)
    probe(P + "/fr/classements/etape-8/img", nrows=3, ntables=1)
    probe(P + "/fr/classements/etape-8/ite", nrows=3, ntables=1)
    probe("https://www.paris-roubaix.fr/fr/etape-1", nrows=1, ntables=1, vctx=(r"Film de l.étape", r"Secteurs? pav", r"Mons-en-Pévèle"), vw=1000)
    for h in ("https://www.letour.fr", "https://www.paris-nice.fr"):
        probe(h + "/fr/mentions-legales", vctx=(r"extraction|reproduction|robot|donn\u00e9es|propri\u00e9t\u00e9 intellectuelle",), vw=500)
        probe(h + "/fr/conditions-generales-d-utilisation", vctx=(r"extraction|reproduction|robot|propri\u00e9t\u00e9 intellectuelle",), vw=500)
    probe("https://www.letour.fr/fr/", maxlinks=30, link_pat=r"(cgu|mentions|conditions|legal|cookies|donnees)")


@groupe
def rcs():
    T = "https://www.tirrenoadriatico.it"
    probe(T + "/classifiche/?classifica=CLGEN", nrows=1, ntables=1, ctxw=500, maxlinks=15,
          link_pat=r"\.(pdf|json|xml)(\?|$)|wp-json|admin-ajax|/live|api\.",
          ctx=(r"admin-ajax", r"wp-json", r"fetch\(", r"\.json", r"Milan\b", r"JONATHAN", r"classifica-"))
    probe(T + "/classifiche/di-tappa/7", nrows=3, ntables=2, ctxw=500, ctx=(r"admin-ajax", r"MILAN"), vctx=(r"MILAN",), vw=600)
    probe(T + "/archivio-2026/", nrows=3, ntables=2, maxlinks=20, link_pat=r"\.(pdf|json)|archivio|classifica", vctx=(r"MILAN|Milan",), vw=500)
    probe("https://www.milanosanremo.it/live/tappa/1", nrows=3, ntables=2, ctxw=500, ctx=(r"admin-ajax", r"\.json", r"fetch\("), vctx=(r"Km|km",), vw=400)
    probe("https://www.milanosanremo.it/archivio-men-2026/", nrows=3, ntables=2, maxlinks=15, link_pat=r"\.(pdf|json)|classifica", vctx=(r"Pogacar|POGACAR|Pogačar",), vw=400)
    probe("https://www.strade-bianche.it/archivio-classifiche/u/2026/", nrows=3, ntables=2, maxlinks=15, link_pat=r"\.(pdf|json)|classifica", vctx=(r"Pogacar|POGACAR|Pogačar|Pidcock",), vw=400)


@groupe
def directvelo():
    D = "https://www.directvelo.com"
    probe(D + "/mentions-legales", vctx=(r"Conditions d.utilisation|propri\u00e9t\u00e9|reproduction|utilisation du site",), vw=1200)
    b = probe(D + "/resultats/2026-10-11", nrows=3, ntables=1, maxlinks=15, link_pat=r"directvelo\.com/(epreuve|actualite)")
    if b:
        for u in links(b, D, r"/epreuve/\d+/paris-tours"):
            probe(u, nrows=8, ntables=3, maxlinks=15, link_pat=r"directvelo\.com/(actualite|epreuve|course)", vctx=(r"Classement",), vw=500)
            break
    b = probe(D + "/calendrier/2026/08", maxlinks=5, link_pat=r"polynormande")
    if b:
        for u in links(b, D, r"/epreuve/\d+/[^/]*polynormande"):
            probe(u, nrows=8, ntables=3, maxlinks=15, link_pat=r"directvelo\.com/(actualite|epreuve|course)", vctx=(r"Classement",), vw=500)
            break


@groupe
def lnc():
    L = "https://www.lncpro.fr"
    probe(L + "/resultats/la-polynormande", nrows=8, ntables=3, text=1500, maxlinks=15, link_pat=r"lncpro\.fr/(resultats|actualites)")
    probe(L + "/resultats/paris-tours-elite", nrows=8, ntables=3, text=1000)
    probe(L + "/", maxlinks=15, link_pat=r"(mention|cgu|conditions|legal|cookies|donnees)")


@groupe
def cyclingnews():
    robots_dump("https://www.cyclingnews.com")
    st, ct, body = raw_get("https://www.cyclingnews.com/feeds.xml")
    print(f"\n=== feeds.xml HTTP {st} {len(body)} o")
    items = re.findall(r"<item>(.*?)</item>", body, re.S)
    print("  items:", len(items))
    cats = {}
    for it in items:
        for c in re.findall(r"<category[^>]*>(.*?)</category>", it, re.S):
            c = " ".join(re.sub(r"<!\[CDATA\[|\]\]>", "", c).split())
            cats[c] = cats.get(c, 0) + 1
    print("  catégories:", sorted(cats.items(), key=lambda x: -x[1])[:25])
    for it in items[:12]:
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        cs = [" ".join(re.sub(r"<!\[CDATA\[|\]\]>", "", c).split()) for c in re.findall(r"<category[^>]*>(.*?)</category>", it, re.S)]
        print("  ITEM", " ".join(re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1) if t else "").split())[:70], "|", cs)
    probe("https://www.futureplc.com/terms-conditions/", vctx=(r"scrap|crawl|automat|data mining|machine learning|artificial intelligence|extract|commercial purposes?|permission",), vw=500)
    ds = re.findall(r"<pubDate>(.*?)</pubDate>", body)
    print("  pubDate premier/dernier:", ds[:1], ds[-1:])
    pick = None
    for it in items:
        if "<category><![CDATA[ Racing ]]>" in it.replace("\n", "") or "Racing" in it[:3000]:
            m = re.search(r"<link>(.*?)</link>", it, re.S)
            d = re.search(r"<dc:content[^>]*>(.*?)</dc:content>", it, re.S)
            if m and d and "cyclo-cross" not in m.group(1):
                pick = (m.group(1).strip(), len(visible(d.group(1))))
                break
    print("  article témoin:", pick)
    if pick:
        b2 = probe(pick[0].replace("<![CDATA[", "").replace("]]>", "").strip(), vctx=(r"Subscribe to the Cyclingnews",), vw=100)
        if b2:
            print("  longueur texte visible page:", len(visible(b2)), "| dc:content (texte):", pick[1])
    probe("https://www.cyclingnews.com/", maxlinks=15, link_pat=r"(terms|conditions|privacy|legal)")
    for it in items[:3]:
        print("  --- item (balises présentes):", sorted(set(re.findall(r"<([a-zA-Z:]+)[ >/]", it))))
        print("  ", " ".join(it.split())[:900])
    for it in items[:2]:
        for tag in ("description", "dc:description", "dc:content", "content:encoded", "media:description", "media:text"):
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", it, re.S)
            print(f"   [{tag}] {len(m.group(1)) if m else 0} car. |", visible(m.group(1))[:200] if m else "")
    for it in items[:2]:
        print("   [dc:source/link/guid]", re.findall(r"<(?:dc:source|link|guid)[^>]*>(.*?)</", it, re.S)[:3])
    for it in items:
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        c = re.search(r"<dc:content[^>]*>(.*?)</dc:content>", it, re.S)
        d = re.search(r"<description>(.*?)</description>", it, re.S)
        print("  *", " ".join(re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1) if t else "").split())[:90],
              "| desc", len(d.group(1)) if d else 0, "| content", len(c.group(1)) if c else 0)


if __name__ == "__main__":
    print("UA:", UA)
    for g in (sys.argv[1:] or GROUPES):
        print(f"\n########## GROUPE {g}")
        try:
            GROUPES[g]()
        except Exception as e:  # noqa: BLE001
            print("ERREUR groupe", g, repr(e))
