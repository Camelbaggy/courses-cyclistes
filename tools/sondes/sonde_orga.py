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
    probe(L + "/fr/classements/etape-10/ite", nrows=1, ntables=1, ctx=(r"<tbody>.*?</tr>.*?</tr>",), ctxw=2500)
    probe(L + "/fr/mentions-legales", vctx=(r"Propri\u00e9t\u00e9 intellectuelle", r"scrap|aspir|moissonn|extraction|robots?\b|bases? de donn\u00e9es|reproduire"), vw=900)
    probe("https://www.paris-nice.fr/fr/actus/2026/etape-8/vingegaard-la-grande-razzia/25347", vctx=(r"Au matin de la derni\u00e8re",), vw=2500)
    for u in ("https://www.fleche-wallonne.be", "https://www.flechewallonne.be", "https://www.paris-tours.fr",
              "https://www.parisstours.com", "https://www.fleche-wallonne.com"):
        st, ct, b = raw_get(u + "/")
        print("\n===", u, "->", st, ct, len(b) if isinstance(b, str) else "", (b if st <= 0 else visible(b)[:150]))


@groupe
def rcs():
    T = "https://www.tirrenoadriatico.it"
    b = probe(T + "/classifiche/?classifica=CLGEN", nrows=1, ntables=1, ctxw=1800, ctx=(r'<div class="surname p-3 is-bold">',))
    if b:
        print("  surname:", b.count('class="surname'), "| data-tab distincts:", sorted(set(re.findall(r'data-tab="(tab-[^"]+)"', b))))
        v = visible(b)
        k = v.find("Classifica generale")
        print("  VISIBLE autour de 'Classifica generale':", v[k:k + 1200] if k >= 0 else "absent")
    b = probe("https://www.strade-bianche.it/archivio-classifiche/u/2026/", nrows=1, ntables=1, ctx=(r"POGA",), ctxw=1600)
    if b:
        v = visible(b)
        k = v.find("Classifiche Strade Bianche Uomini 2026")
        seg = v[k:k + 30000]
        print("  lignes type temps (approx):", len(re.findall(r"\d:\d\d:\d\d \d?\d?:?\d\d:\d\d", seg)), "| fin de liste:", seg[-600:] if len(seg) < 30000 else "(>30000)")
    b = probe("https://www.giroditalia.it/classifiche/", nrows=1, ntables=1)
    if b:
        print("  surname:", b.count('class="surname'), "| data-tab:", sorted(set(re.findall(r'data-tab="(tab-[^"]+)"', b)))[:12])
        v = visible(b)
        k = v.find("Classifica")
        print("  VISIBLE:", v[k + 1500:k + 2600])


@groupe
def directvelo():
    D = "https://www.directvelo.com"
    probe(D + "/direct/6313/la-polynormande-2026", nrows=3, ntables=2, vctx=(r"Direct",), vw=900, text=0)


@groupe
def lnc():
    L = "https://www.lncpro.fr"
    probe(L + "/resultats/paris-tours-elite", nrows=1, ntables=1, ctxw=1600, ctx=(r'data-result-id="25185"',))
    probe(L + "/index.php/mentions-legales", vctx=(r"scrap|aspir|moissonn|extraction|robots?\b|bases? de donn\u00e9es|reproduction|propri\u00e9t\u00e9 intellectuelle",), vw=700)


@groupe
def cyclingnews():
    b = probe("https://futureplc.com/terms-conditions/", vctx=(r"Intellectual Property", r"licen[cs]e", r"copy|reproduc|redistribut|republish", r"commercial", r"automat|scrap|crawl|spider|bot\b|mining"), vw=700)
    if b:
        v = visible(b)
        print("  longueur texte ToS:", len(v))


if __name__ == "__main__":
    print("UA:", UA)
    for g in (sys.argv[1:] or GROUPES):
        print(f"\n########## GROUPE {g}")
        try:
            GROUPES[g]()
        except Exception as e:  # noqa: BLE001
            print("ERREUR groupe", g, repr(e))
