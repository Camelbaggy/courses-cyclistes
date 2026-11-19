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
    etape = os.environ.get("ETAPE", "1")
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
    if etape == "p4":
        base = "https://web.archive.org/cdx/search/cdx?output=txt&fl=timestamp,original,statuscode&collapse=urlkey&matchType=prefix"
        def cdx(url, limit=20000):
            for essai in range(3):
                time.sleep(6)
                s, h, b = get(base + "&url=" + url + "&limit=%d" % limit, timeout=240)
                if s == 200:
                    return [l.split(" ") for l in b.decode("utf-8", "replace").splitlines() if l.strip()]
                print("[CDX] statut", s, b[:60]); time.sleep(75)
            return []
        def propre(h):
            h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
            h = re.sub(r"(?i)<br\s*/?>", "\n", h)
            h = re.sub(r"(?s)<[^>]+>", "", h)
            return h.replace("&nbsp;", " ").replace("&amp;", "&")
        def montre(ts, u, tete=8, n=7):
            s_, h_, b = get("https://web.archive.org/web/%sid_/%s" % (ts, u))
            t = b.decode("latin-1", "replace")
            print("[PAGE]", u, s_, len(b), "pre=", t.lower().count("<pre"))
            if s_ != 200:
                return
            i = t.lower().find("<pre")
            avant = [l.strip() for l in propre(t[max(0, i - 3000):i]).splitlines() if l.strip()][-tete:]
            for l in avant:
                print("  |", l[:160])
            for k, m in enumerate(re.finditer(r"(?is)<pre[^>]*>(.*?)</pre>", t)):
                if k > 1:
                    break
                lg = propre(m.group(1)).splitlines()
                rg = re.compile(r"^\s*(\d+|DNF|DNS|OTL|DSQ|HD|AB)\s+\S")
                print("  bloc", k, "lignes", len(lg), "classées", sum(1 for x in lg if rg.match(x)), "avec temps", sum(1 for x in lg if re.search(r"\d+[.:]\d\d[.:]\d\d", x)))
                for x in lg[:n]:
                    print("   >", x[:140])
                for x in lg[-3:]:
                    print("   <", x[:140])
        listes = {}
        for an in range(2002, 2009):
            L = cdx("autobus.cyclingnews.com/road.php?id=road/%d/" % an)
            listes[an] = L
            cles = collections.defaultdict(lambda: [0, 0])
            for l in L:
                seg = re.sub(r"^.*id=road/\d{4}/?", "", l[1]).strip("/").split("/")
                if len(seg) >= 2 and re.match(r"^[a-z]{3,4}\d\d$", seg[0]):
                    k = seg[0] + "/" + seg[1]
                    cles[k][0] += 1
                    if l[2] == "200":
                        cles[k][1] += 1
            multi = sum(1 for v in cles.values() if v[0] > 2)
            print("[COUV] %d : %d urls, %d cours/dossiers distincts (dont %d avec >2 pages = par étapes), %d sans aucune page 200" % (
                an, len(L), len(cles), multi, sum(1 for v in cles.values() if v[1] == 0)))
        # index mensuels
        for ts, u in [("2009", "http://autobus.cyclingnews.com/results/?id=2008/may08"), ("2009", "http://autobus.cyclingnews.com/results/?id=2005/apr05")]:
            s_, h_, b = get("https://web.archive.org/web/%sid_/%s" % (ts, u))
            t = b.decode("latin-1", "replace")
            print("[MOIS]", u, s_, len(b))
            liens = re.findall(r'href="([^"]*road[^"]*id=road/[^"]*)"[^>]*>([^<]{0,80})', t, re.I)
            print("[MOIS]   liens courses", len(liens))
            for x in liens[:12]:
                print("[MOIS]   ", x)
            i = t.find("road.php?id=road")
            print("[MOIS]   texte autour du 1er lien :", propre(t[max(0, i - 600):i + 900]).replace("\n", " / ")[:700])
            if "may08" in u:
                cdxk = set()
                for l in listes[2008]:
                    m = re.search(r"road/2008/may08/([^/&]+)", l[1])
                    if m:
                        cdxk.add(m.group(1))
                idxk = set(re.findall(r"road/2008/may08/([A-Za-z0-9_]+)", t))
                print("[MOIS]   may08 : %d courses dans l'index mensuel, %d dans le CDX, communes %d ; manquantes au CDX %s" % (
                    len(idxk), len(cdxk), len(idxk & cdxk), sorted(idxk - cdxk)[:15]))
        # ancien site 1998-1999
        L = cdx("www.cyclingnews.com/results/1999/", limit=3000)
        print("[OLD] 1999 :", len(L))
        dirs = collections.Counter(re.sub(r"^.*results/1999/", "", l[1]).split("/")[0] for l in L)
        print("[OLD]   dossiers", dict(list(dirs.most_common(40))))
        for l in L[:5] + [x for x in L if re.search(r"roub|flanders|sanremo", x[1], re.I)][:6]:
            print("[OLD]   ex", l[0], l[1][:150], l[2])
        cands = [x for x in L if re.search(r"roub", x[1], re.I) and x[2] == "200" and x[1].endswith(("html", "shtml"))]
        for c in cands[:2]:
            montre(c[0], c[1], n=10)
        # échantillon élite
        for an, mots in [(2008, [r"/roubaix08$", r"/flanders08$|/rvv08$|/ronde08$", r"/sanremo08$|/milansanremo08$", r"/lombardia08$"]), (2005, [r"/roubaix05$", r"/flanders05$", r"/lombardia05$"]), (2003, [r"/roubaix03$"])]:
            for mo in mots:
                c = [l for l in listes.get(an, []) if re.search(mo, l[1]) and l[2] == "200"]
                print("[ELITE]", an, mo, c[:1])
                if c:
                    montre(c[0][0], c[0][1])
    if etape == "p5":
        base = "https://web.archive.org/cdx/search/cdx?output=txt&fl=timestamp,original,statuscode&collapse=urlkey&matchType=prefix"
        def cdx(url, limit=20000):
            for essai in range(3):
                time.sleep(6)
                s, h, b = get(base + "&url=" + url + "&limit=%d" % limit, timeout=240)
                if s == 200:
                    return [l.split(" ") for l in b.decode("utf-8", "replace").splitlines() if l.strip()]
                print("[CDX] statut", s, b[:60]); time.sleep(75)
            return []
        def propre(h):
            h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
            h = re.sub(r"(?i)<br\s*/?>", "\n", h)
            h = re.sub(r"(?s)<[^>]+>", "", h)
            return h.replace("&nbsp;", " ").replace("&amp;", "&")
        def montre(ts, u, tete=8, n=12):
            s_, h_, b = get("https://web.archive.org/web/%sid_/%s" % (ts, u))
            t = b.decode("latin-1", "replace")
            print("[PAGE]", u, s_, len(b), "pre=", t.lower().count("<pre"))
            if s_ != 200:
                return
            i = t.lower().find("<pre")
            avant = [l.strip() for l in propre(t[max(0, i - 3000):i]).splitlines() if l.strip()][-tete:]
            for l in avant:
                print("  |", l[:160])
            for k, m in enumerate(re.finditer(r"(?is)<pre[^>]*>(.*?)</pre>", t)):
                if k > 1:
                    break
                lg = propre(m.group(1)).splitlines()
                rg = re.compile(r"^\s*(\d+|DNF|DNS|OTL|DSQ|HD|AB)\s+\S")
                print("  bloc", k, "lignes", len(lg), "classées", sum(1 for x in lg if rg.match(x)), "avec temps", sum(1 for x in lg if re.search(r"\d+[.:]\d\d[.:]\d\d", x)))
                for x in lg[:n]:
                    print("   >", x[:140])
                for x in lg[-3:]:
                    print("   <", x[:140])
        picks = []
        for an, mois in [(2008, "apr08"), (2005, "apr05"), (2003, "apr03")]:
            L = cdx("autobus.cyclingnews.com/road.php?id=road/%d/%s/" % (an, mois), limit=3000)
            dirs = collections.Counter()
            for l in L:
                m = re.search(r"road/\d{4}/[a-z]{3}\d\d/([^/&]+)", l[1])
                if m:
                    dirs[m.group(1)] += 1
            print("[SLUGS]", an, mois, len(L), "urls ;", len(dirs), "dossiers")
            print("[SLUGS]  ", " ".join("%s:%d" % kv for kv in sorted(dirs.items())))
            def p1(mo, excl=r"^u23|junior|women|espoir"):
                c = [l for l in L if l[2] == "200" and "/default" not in l[1] and re.search(mo, l[1].split("/")[-1], re.I) and not re.search(excl, l[1].split("/")[-1], re.I)]
                return c[-1] if c else None
            for mo in [r"roubaix", r"flanders|ronde|vlaanderen", r"amstel", r"liege|lbl", r"^gp[a-z]+\d\d$"]:
                c = p1(mo)
                if c and not any(c[1] == q[1] for q in picks):
                    picks.append(c)
                print("[SLUGS]  motif", mo, "->", c[1][-70:] if c else None)
        for c in picks[:10]:
            montre(c[0], c[1])
    if etape == "p6":
        base = "https://web.archive.org/cdx/search/cdx?output=txt&fl=timestamp,original,statuscode&collapse=urlkey&matchType=prefix"
        def cdx(url, limit=20000):
            for essai in range(3):
                time.sleep(6)
                s, h, b = get(base + "&url=" + url + "&limit=%d" % limit, timeout=240)
                if s == 200:
                    return [l.split(" ") for l in b.decode("utf-8", "replace").splitlines() if l.strip()]
                print("[CDX] statut", s, b[:60]); time.sleep(75)
            return []
        def propre(h):
            h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
            h = re.sub(r"(?i)<br\s*/?>", "\n", h)
            h = re.sub(r"(?s)<[^>]+>", "", h)
            return h.replace("&nbsp;", " ").replace("&amp;", "&")
        def montre(ts, u, tete=8, n=12):
            s_, h_, b = get("https://web.archive.org/web/%sid_/%s" % (ts, u))
            t = b.decode("latin-1", "replace")
            print("[PAGE]", u, s_, len(b), "pre=", t.lower().count("<pre"))
            if s_ != 200:
                return
            i = t.lower().find("<pre")
            avant = [l.strip() for l in propre(t[max(0, i - 3000):i]).splitlines() if l.strip()][-tete:]
            for l in avant:
                print("  |", l[:160])
            for k, m in enumerate(re.finditer(r"(?is)<pre[^>]*>(.*?)</pre>", t)):
                if k > 1:
                    break
                lg = propre(m.group(1)).splitlines()
                rg = re.compile(r"^\s*(\d+|DNF|DNS|OTL|DSQ|HD|AB)\s+\S")
                print("  bloc", k, "lignes", len(lg), "classées", sum(1 for x in lg if rg.match(x)), "avec temps", sum(1 for x in lg if re.search(r"\d+[.:]\d\d[.:]\d\d", x)))
                for x in lg[:n]:
                    print("   >", x[:140])
                for x in lg[-3:]:
                    print("   <", x[:140])
        s_, h_, b = get("https://web.archive.org/web/2009id_/http://autobus.cyclingnews.com/road.php")
        t = b.decode("latin-1", "replace")
        hrefs = re.findall(r'href=["\']?([^"\' >]+)', t)
        cl = collections.Counter(re.sub(r"\d+", "N", "/".join(re.sub(r"^https?://[^/]+", "", h).split("?")[0].split("/")[:3]))[:60] + ("?" + re.sub(r"\d+", "N", h.split("?")[1])[:30] if "?" in h else "") for h in hrefs)
        print("[HOME]", s_, len(b), len(hrefs), "liens")
        for k, v in cl.most_common(45):
            print("[HOME]  ", v, k)
        for h in hrefs:
            if re.search(r"roubaix|flanders|amstel|sanremo|lombard", h, re.I):
                print("[HOME]   course :", h[:150])
        for pre in ["autobus.cyclingnews.com/races", "autobus.cyclingnews.com/results/", "autobus.cyclingnews.com/road.php?id=road/2008/apr08/roubaix", "autobus.cyclingnews.com/road.php?id=road/pro"]:
            L = cdx(pre, limit=4000)
            an = collections.Counter()
            for l in L:
                m = re.search(r"/((?:19|20)\d\d|\d\d)/", l[1])
                an[m.group(1) if m else "?"] += 1
            print("[R] %s : %d urls ; %s" % (pre, len(L), dict(sorted(an.items()))))
            for l in L[:4] + L[len(L)//3:len(L)//3 + 4] + L[-4:]:
                print("[R]   ex", l[0], l[1][:160], l[2])
            c = [l for l in L if re.search(r"roubaix", l[1], re.I) and l[2] == "200"]
            print("[R]   roubaix :", [x[1][-90:] for x in c[:6]])
            for x in c[:1]:
                montre(x[0], x[1])
    if etape == "p7":
        base = "https://web.archive.org/cdx/search/cdx?output=txt&fl=timestamp,original,statuscode&collapse=urlkey&matchType=prefix"
        def cdx(url, limit=20000):
            for essai in range(3):
                time.sleep(6)
                s, h, b = get(base + "&url=" + url + "&limit=%d" % limit, timeout=240)
                if s == 200:
                    return [l.split(" ") for l in b.decode("utf-8", "replace").splitlines() if l.strip()]
                print("[CDX] statut", s, b[:60]); time.sleep(75)
            return []
        def propre(h):
            h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
            h = re.sub(r"(?i)<br\s*/?>", "\n", h)
            h = re.sub(r"(?s)<[^>]+>", "", h)
            return h.replace("&nbsp;", " ").replace("&amp;", "&")
        def montre(ts, u, tete=8, n=12):
            s_, h_, b = get("https://web.archive.org/web/%sid_/%s" % (ts, u))
            t = b.decode("latin-1", "replace")
            print("[PAGE]", u, s_, len(b), "pre=", t.lower().count("<pre"))
            if s_ != 200:
                return
            i = t.lower().find("<pre")
            avant = [l.strip() for l in propre(t[max(0, i - 3000):i]).splitlines() if l.strip()][-tete:]
            for l in avant:
                print("  |", l[:160])
            for k, m in enumerate(re.finditer(r"(?is)<pre[^>]*>(.*?)</pre>", t)):
                if k > 1:
                    break
                lg = propre(m.group(1)).splitlines()
                rg = re.compile(r"^\s*(\d+\.?|DNF|DNS|OTL|DSQ|HD|AB)\s+\S")
                print("  bloc", k, "lignes", len(lg), "classées", sum(1 for x in lg if rg.match(x)), "avec temps", sum(1 for x in lg if re.search(r"\d+[.:]\d\d[.:]\d\d", x)))
                for x in lg[:n]:
                    print("   >", x[:140])
                for x in lg[-3:]:
                    print("   <", x[:140])
        hubs = {}
        for an in (2008, 2005, 2003):
            L = cdx("autobus.cyclingnews.com/road/%d/" % an, limit=6000)
            hubs[an] = L
            cles = collections.defaultdict(set)
            for l in L:
                m = re.search(r"/road/%d/([a-z]{3}\d\d)/([^/?&]+)/?\??(?:id=)?([^&]*)" % an, l[1])
                if m and l[2] == "200":
                    cles[m.group(1) + "/" + m.group(2)].add(m.group(3).split("/")[0] or "(accueil)")
            avec_res = sum(1 for v in cles.values() if "results" in v)
            print("[HUB] %d : %d urls ; %d courses ; %d avec ?id=results capturé" % (an, len(L), len(cles), avec_res))
            print("[HUB]   courses", " ".join(sorted(k.split("/")[1] + ("*" if "results" in v else "") for k, v in cles.items()))[:2500])
        sel = []
        for an, mots in [(2008, [r"amstel08/\?id=results", r"roubaix08/\?id=results|flanders08/\?id=results", r"tirreno08/\?id=results.*|paris-?nice08.*results", r"lombardia08/\?id=results"]),
                         (2005, [r"roubaix05/\?id=results", r"flanders05/\?id=results", r"sanremo05/\?id=results"]), (2003, [r"roubaix03/\?id=results", r"amstel03/\?id=results"])]:
            for mo in mots:
                c = [l for l in hubs.get(an, []) if re.search(mo, l[1]) and l[2] == "200"]
                print("[HUBSEL]", an, mo, [x[1][-80:] for x in c[:3]])
                if c:
                    sel.append(c[0])
        for c in sel[:8]:
            montre(c[0], c[1], n=12)
        for an in (1998, 1999, 2000, 2001, 2002):
            L = cdx("www.cyclingnews.com/results/%d/" % an, limit=6000)
            pages = [l for l in L if re.search(r"\.s?html$", l[1]) and l[2] == "200" and not re.search(r"photo|diary|news|feature|teams|cal\d\d|\d\d\.s?html$", l[1].split("/")[-1].replace(str(an)[2:] + ".", "XX."))]
            print("[OLDN] %d : %d urls ; pages html 200 : %d ; hors news/photos/diary : %d" % (an, len(L), sum(1 for l in L if re.search(r"\.s?html$", l[1]) and l[2] == "200"), len(pages)))
            print("[OLDN]   ex", [l[1].split("/results/")[-1] for l in pages[:14]])
    if etape == "p8":
        for ts, u in [("20121106062214", "http://autobus.cyclingnews.com/road.php?id=road/2008/may08/gpkranj08"),
                      ("2010", "http://autobus.cyclingnews.com/road/2008/apr08/amstel08/?id=results"),
                      ("20150918061335", "http://autobus.cyclingnews.com/road.php?id=road/2008/apr08/alentejo08/alentejo085")]:
            s_, h_, b = get("https://web.archive.org/web/%sid_/%s" % (ts, u))
            t = b.decode("latin-1", "replace")
            print("<<<RAW", u, s_, len(b), "meta:", re.findall(r"(?i)<meta[^>]*charset[^>]*>", t)[:2])
            i = t.lower().find("<pre")
            # en-tête : 2200 caractères avant le premier <pre>, sans scripts
            av = re.sub(r"(?is)<script.*?</script>", "", t[max(0, i - 2600):i])
            print(av[-2000:])
            m = re.search(r"(?is)<pre[^>]*>(.*?)</pre>", t)
            corps = m.group(1)
            print("--- PRE (début)")
            print(corps[:700])
            lg = corps.splitlines()
            print("--- PRE lignes non classées (hors rang / DNF) :")
            n = 0
            for k, x in enumerate(lg):
                if not re.match(r"^\s*(\d+|DNF|DNS|OTL|DSQ|HD|AB)\s", x) and x.strip():
                    print("  [%d] %s" % (k, x[:140])); n += 1
                    if n > 25:
                        break
            print("--- PRE (fin)")
            print("\n".join(lg[-4:]))
            print("--- APRES </pre>")
            j = t.lower().find("</pre>")
            print(re.sub(r"(?is)<script.*?</script>", "", t[j:j + 700]))
            print("FIN>>>")
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
