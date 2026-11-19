"""Sonde Cyclingnews (archives de résultats 1995-2008) : accès direct, CDX, captures. Étude seulement, aucun collecteur.
Politesse Internet Archive : >= 4,2 s entre requêtes, UA honnête, arrêt sur 429. Étape pilotée par la variable ETAPE (1 par défaut)."""
import gzip, json, os, re, sys, time, urllib.request, urllib.error, collections
UA = "courses-cyclistes (accord Cyclingnews)"
PAUSE = 4.2
_last = 0.0
N = 0

class _NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None

def get(url, timeout=120, suivre=True):
    global _last, N
    d = PAUSE - (time.time() - _last)
    if d > 0:
        time.sleep(d)
    _last = time.time()
    N += 1
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    try:
        r = (urllib.request.urlopen(req, timeout=timeout) if suivre
             else urllib.request.build_opener(_NoRedir).open(req, timeout=timeout))
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return r.status, dict(r.headers), raw
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("[429] arrêt"); sys.exit(0)
        return e.code, dict(e.headers), e.read()[:500]
    except Exception as e:
        return 0, {}, str(e).encode()

def main():
    etape = os.environ.get("ETAPE", "p3")
    os.makedirs("/tmp/cn", exist_ok=True)
    if etape == "1":
        # accès direct
        for u in ["https://autobus.cyclingnews.com/road.php?id=road/2008/may08/gpkranj08",
                  "https://www.cyclingnews.com/road.php?id=road/2008/may08/gpkranj08"]:
            s, h, b = get(u)
            print("[DIRECT]", u, s, h.get("Location") or h.get("location"), len(b))
        # CDX : toutes les URLs HTML 200 d'autobus
        u = ("https://web.archive.org/cdx/search/cdx?url=autobus.cyclingnews.com&matchType=host&output=txt"
             "&fl=timestamp,original,statuscode,mimetype&collapse=urlkey&filter=statuscode:200&filter=mimetype:text/html&limit=400000")
        s, h, b = get(u, timeout=300)
        print("[CDX] statut", s, "octets", len(b))
        txt = b.decode("utf-8", "replace")
        open("/tmp/cn/cdx.txt", "w").write(txt)
        lignes = [l.split(" ") for l in txt.splitlines() if l.strip()]
        print("[CDX] urls distinctes", len(lignes))
        cl = collections.Counter()
        par_an = collections.Counter()
        for l in lignes:
            if len(l) < 2:
                continue
            o = l[1]
            m = re.search(r"road\.php\?id=road/(\d{4})/([a-z]{3}\d\d)/", o)
            if m:
                cl["road/AAAA/moisAA/<course>"] += 1
                par_an[m.group(1)] += 1
                continue
            m = re.search(r"autobus\.cyclingnews\.com(/[^?]*)\??(.{0,40})", o)
            cl[(m.group(1)[:30] + "?" + m.group(2)[:25]) if m else o[:60]] += 1
        for k, v in cl.most_common(40):
            print("[CDX] classe", v, k)
        print("[CDX] par année", sorted(par_an.items()))
        # exemples de formes d'index
        ex = [l[1] for l in lignes if len(l) > 1 and "road.php" in l[1] and not re.search(r"road/\d{4}/[a-z]{3}\d\d/", l[1])]
        print("[CDX] road.php hors courses :", len(ex))
        for o in ex[:60]:
            print("[CDX] ex", o)
    if etape == "cdx":
        for u in ["https://autobus.cyclingnews.com/road.php?id=road/2008/may08/gpkranj08", "https://autobus.cyclingnews.com/"]:
            s, h, b = get(u, suivre=False)
            print("[DIRECT-SANS-SUIVI]", u, s, h.get("Location"))
        base = "https://web.archive.org/cdx/search/cdx?output=txt&fl=timestamp,original,statuscode&collapse=urlkey&matchType=prefix"
        def cdx(url, extra="", limit=20000):
            for essai in range(3):
                s, h, b = get(base + "&url=" + url + extra + "&limit=%d" % limit, timeout=240)
                if s == 200:
                    return [l.split(" ") for l in b.decode("utf-8", "replace").splitlines() if l.strip()]
                print("[CDX] statut", s, b[:80]); time.sleep(10)
            return []
        for an in range(1995, 2009):
            L = cdx("autobus.cyclingnews.com/road.php?id=road/%d/" % an)
            st = collections.Counter(l[2] for l in L if len(l) > 2)
            mois = collections.Counter()
            profils = collections.Counter()
            for l in L:
                m = re.search(r"road/\d{4}/([^/&]*)/?([^&]*)", l[1])
                if m:
                    mois[m.group(1)] += 1
                    profils["/".join(["M" if m.group(2) else "", "x"]) ] += 1
            print("[CDX] %d : %d urls, statuts %s, dossiers %d" % (an, len(L), dict(st), len(mois)))
            print("[CDX]   dossiers", dict(list(mois.items())[:30]))
            if an in (1998, 2003, 2008):
                for l in L[:25]:
                    print("[CDX]   ex", l[0], l[1], l[2])
            if an == 2008:
                open("/tmp/cn/cdx2008.txt", "w").write("\n".join(" ".join(l) for l in L))
        # autres chemins du site
        L = cdx("autobus.cyclingnews.com/", limit=1500)
        print("[CDX] racine : %d urls (limite 1500)" % len(L))
        cl = collections.Counter()
        for l in L:
            m = re.search(r"autobus\.cyclingnews\.com(/[^?/]*/?[^?/]*)", l[1])
            cl[m.group(1) if m else l[1][:50]] += 1
        for k, v in cl.most_common(40):
            print("[CDX] chemin", v, k)
    if etape == "cdx2":
        base = "https://web.archive.org/cdx/search/cdx?output=txt&fl=timestamp,original,statuscode&collapse=urlkey&matchType=prefix"
        def cdx(url, limit=20000):
            for essai in range(4):
                s, h, b = get(base + "&url=" + url + "&limit=%d" % limit, timeout=240)
                if s == 200:
                    return [l.split(" ") for l in b.decode("utf-8", "replace").splitlines() if l.strip()]
                print("[CDX] statut", s, b[:60]); time.sleep(60)
            return []
        tous = {}
        for an in [1995, 1996, 1997, 1998, 1999, 2000, 2001, 2002, 2006, 2007, 2008]:
            time.sleep(6)
            L = cdx("autobus.cyclingnews.com/road.php?id=road/%d/" % an)
            tous[an] = L
            st = collections.Counter(l[2] for l in L if len(l) > 2)
            mois = collections.Counter()
            for l in L:
                m = re.search(r"road/\d{4}/([^/&]*)", l[1])
                if m:
                    mois[m.group(1)] += 1
            print("[CDX] %d : %d urls, statuts %s" % (an, len(L), dict(st)))
            print("[CDX]   dossiers", dict(mois))
            courts = [l for l in L if len(re.sub(r"^.*id=road/\d{4}/?", "", l[1]).strip("/").split("/")) <= 1]
            print("[CDX]   pages d'index (<= 1 segment) :", [(l[0], l[1][-60:], l[2]) for l in courts[:12]])
            # profondeur : pages avec 3 segments (mois/course/page)
            prof = collections.Counter(len(re.sub(r"^.*id=road/\d{4}/?", "", l[1]).strip("/").split("/")) for l in L)
            print("[CDX]   profondeurs", dict(prof))
            slugs = sorted(set(l[1].split("/")[-1] if l[1].count("/") >= 6 else "" for l in L))
            if an in (1998, 2008):
                for l in L:
                    if "/may" in l[1] or "/may98" in l[1]:
                        print("[CDX]   L", l[0], re.sub(r"^.*id=road/", "", l[1]), l[2])
        # captures de pages connues
        for ts, u in [("20121106062214", "http://autobus.cyclingnews.com/road.php?id=road/2008/may08/gpkranj08"),
                      ("20121106102119", "http://autobus.cyclingnews.com/road.php?id=road/2008/apr08/alentejo08/default"),
                      ("20150918051532", "http://autobus.cyclingnews.com/road.php?id=road/2008/apr08/alentejo08/alentejo081"),
                      ("20121106101903", "http://autobus.cyclingnews.com/road.php?id=road/2008/apr08/bancapopolare08")]:
            s, h, b = get("https://web.archive.org/web/%sid_/%s" % (ts, u))
            print("[PAGE]", u, s, len(b), h.get("Content-Type"))
            open("/tmp/cn/p_%s.html" % u.split("/")[-1], "wb").write(b)
            t = b.decode("latin-1", "replace")
            i = t.find("<pre")
            print("<<<DEBUT", u, "pre=", t.count("<pre"), "i=", i)
            print(t[:1800])
            print("....")
            print(t[max(i, 0):max(i, 0) + 3500] if i >= 0 else t[3000:6500])
            print("FIN>>>")
    if etape == "p3":
        base = "https://web.archive.org/cdx/search/cdx?output=txt&fl=timestamp,original,statuscode&collapse=urlkey&matchType=prefix"
        def cdx(url, limit=4000):
            for essai in range(3):
                s, h, b = get(base + "&url=" + url + "&limit=%d" % limit, timeout=240)
                if s == 200:
                    return [l.split(" ") for l in b.decode("utf-8", "replace").splitlines() if l.strip()]
                print("[CDX] statut", s, b[:60]); time.sleep(60)
            return []
        # A. autres hôtes / chemins pour 1995-2001
        for pre in ["www.cyclingnews.com/results/", "www.cyclingnews.com/road/", "cyclingnews.com/road.php", "autobus.cyclingnews.com/road/",
                    "autobus.cyclingnews.com/archiveindex", "autobus.cyclingnews.com/road.php?id=road/results", "autobus.cyclingnews.com/road.php?id=results"]:
            L = cdx(pre)
            an = collections.Counter()
            for l in L:
                m = re.search(r"/((?:19|20)\d\d)/", l[1])
                an[m.group(1) if m else "?"] += 1
            print("[A] %s : %d urls ; par année %s" % (pre, len(L), dict(sorted(an.items()))))
            for l in L[:6] + L[len(L)//2:len(L)//2 + 3]:
                print("[A]   ex", l[0], l[1][:150], l[2])
        def propre(h):
            h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
            h = re.sub(r"(?i)<br\s*/?>", "\n", h)
            h = re.sub(r"(?s)<[^>]+>", "", h)
            return h.replace("&nbsp;", " ").replace("&amp;", "&")
        def montre(ts, u, tete=40):
            s_, h_, b = get("https://web.archive.org/web/%sid_/%s" % (ts, u))
            t = b.decode("latin-1", "replace")
            print("[PAGE]", u, s_, len(b), h_.get("Content-Type"), "pre=", t.lower().count("<pre"))
            if s_ != 200:
                return
            i = t.lower().find("<pre")
            avant = [l.strip() for l in propre(t[max(0, i - 9000):i]).splitlines() if l.strip()][-tete:]
            print("<<<AVANT", u)
            for l in avant:
                print("  |", l[:160])
            for k, m in enumerate(re.finditer(r"(?is)<pre[^>]*>(.*?)</pre>", t)):
                lg = propre(m.group(1)).splitlines()
                rg = re.compile(r"^\s*(\d+|DNF|DNS|OTL|DSQ|HD|AB)\s+\S")
                print("  bloc", k, "lignes", len(lg), "classées", sum(1 for x in lg if rg.match(x)))
                for x in lg[:6]:
                    print("   >", x[:150])
                print("   ...")
                for x in lg[-9:]:
                    print("   <", x[:150])
            apres = [l.strip() for l in propre(t[t.lower().rfind("</pre>"):t.lower().rfind("</pre>") + 6000]).splitlines() if l.strip()][:12]
            for l in apres:
                print("  apres|", l[:160])
            print("FIN>>>")
        # B. pages d'index
        for u in ["http://autobus.cyclingnews.com/road.php", "http://autobus.cyclingnews.com/archiveindex.php"]:
            s_, h_, b = get("https://web.archive.org/web/2009id_/" + u)
            t = b.decode("latin-1", "replace")
            print("[IDX]", u, s_, len(b))
            liens = sorted(set(re.findall(r'href="([^"]*(?:road|results|archive)[^"]*)"', t, re.I)))
            print("[IDX]   liens", len(liens))
            for x in liens[:70]:
                print("[IDX]   ", x[:140])
        # C. échantillon de pages
        L08 = cdx("autobus.cyclingnews.com/road.php?id=road/2008/", limit=20000)
        L05 = cdx("autobus.cyclingnews.com/road.php?id=road/2005/", limit=20000)
        L03 = cdx("autobus.cyclingnews.com/road.php?id=road/2003/", limit=20000)
        def trouve(L, motif, dernier=False):
            c = [l for l in L if re.search(motif, l[1]) and l[2] == "200" and "/default" not in l[1]]
            return (c[-1] if dernier else c[0]) if c else None
        choix = []
        for L, mots in [(L08, [r"roubaix", r"sanremo|sremo", r"amstel", r"alentejo08/alentejo08\d$", r"tourdefrance08/\w+21$|tdf08/\w+21$"]),
                        (L05, [r"roubaix", r"/gp[a-z]+05$"]), (L03, [r"roubaix", r"/gp[a-z]+03$"])]:
            for mo in mots:
                c = trouve(L, mo, dernier=True)
                if c:
                    choix.append(c)
                else:
                    print("[C] aucun motif", mo)
        for c in choix[:9]:
            print("[C] choix", c)
            montre(c[0], c[1])
    if etape == "2":
        # capture d'une page de course et de pages d'index
        for u in os.environ.get("URLS", "").split("|"):
            if not u:
                continue
            s, h, b = get(u)
            print("[PAGE]", u, s, len(b), h.get("content-type"))
            open("/tmp/cn/p%02d.html" % N, "wb").write(b)
            print("<<<DEBUT", u)
            print(b[:int(os.environ.get("MAXC", "6000"))].decode("latin-1", "replace"))
            print("FIN>>>")
    print("[REQUETES]", N)

main()
