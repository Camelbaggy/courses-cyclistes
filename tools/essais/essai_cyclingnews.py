"""Sonde Cyclingnews (archives de résultats 1995-2008) : accès direct, CDX, captures. Étude seulement, aucun collecteur.
Politesse Internet Archive : >= 4,2 s entre requêtes, UA honnête, arrêt sur 429. Étape pilotée par la variable ETAPE (1 par défaut)."""
import gzip, json, os, re, sys, time, urllib.request, urllib.error, collections
UA = "courses-cyclistes (accord Cyclingnews)"
PAUSE = 4.2
_last = 0.0
N = 0

def get(url, timeout=120, suivre=True):
    global _last, N
    d = PAUSE - (time.time() - _last)
    if d > 0:
        time.sleep(d)
    _last = time.time()
    N += 1
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
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
