#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde de conformité cyclingflash.com (robots.txt, CGU, en-têtes) puis, si le module existe, essai de cyclingflash.py."""
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, ".")
import netutil  # noqa: E402


def get(url):
    time.sleep(2)
    req = urllib.request.Request(url, headers={"User-Agent": netutil.USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read(3000).decode("utf-8", "replace")
    except Exception as e:
        return 0, {}, str(e)


def sonde():
    for url in ["https://cyclingflash.com/robots.txt", "https://cyclingflash.com/"]:
        st, h, t = get(url)
        print(f"\n#### {url} -> HTTP {st}, {len(t)} car.")
        print("En-têtes :", {k: v for k, v in h.items() if k.lower() in (
            "server", "cf-ray", "cf-mitigated", "content-type", "x-robots-tag", "set-cookie", "via", "x-powered-by")})
        if url.endswith("robots.txt"):
            print(t[:6000])
        else:
            print("challenge ?", "Just a moment" in t or "challenge-platform" in t)
            liens = sorted(set(re.findall(r'href="([^"#]+)"', t)))
            print("liens:", [l for l in liens if re.search(r"term|cond|legal|privacy|cgu|about|contact|api|imprint", l, re.I)])
            print("liens calendrier:", [l for l in liens if "calendar" in l][:60])
    st, h, t = get("https://cyclingflash.com/calendar/road/2027/uci-world-tour")
    print(f"\n#### calendrier WT 2027 -> HTTP {st}, {len(t)} car., challenge={'Just a moment' in t}")
    print({k: v for k, v in h.items() if k.lower() in ("server", "cf-ray", "cf-mitigated", "content-type")})
    print(t[:1500])


if __name__ == "__main__":
    sonde()
