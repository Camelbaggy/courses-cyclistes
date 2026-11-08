#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DirectVélo (accord obtenu ; Crawl-delay 10 s géré par netutil) : article de compte rendu d'une course française.

Parcours : /resultats/AAAA-MM-JJ (liste du jour, liens /epreuve/ID/slug) -> page de la course (liens
/actualite/ID/slug) -> article. 3 requêtes par appel (~31 s). La recherche interne (/recherche/) est interdite
par robots.txt et n'est jamais appelée.
"""

import html
import re
from typing import Dict, List, Optional

import netutil

BASE = "https://www.directvelo.com"
STOP = {"de", "du", "la", "le", "les", "des", "d", "l", "et", "en", "a", "au", "aux", "grand", "prix", "gp", "tour",
        "course", "elite", "hommes", "2024", "2025", "2026", "2027"}
BAD_SLUG = {"classement", "partants", "engages", "espoirs", "femmes", "juniors", "photos", "videos", "direct"}

_PAGES: Dict[str, Optional[str]] = {}


def _page(url: str) -> Optional[str]:
    if url not in _PAGES:
        _PAGES[url] = netutil.fetch_text(url, retries=2)
    return _PAGES[url]


def _words(s: str) -> List[str]:
    return [w for w in netutil.normalize(s).split() if w not in STOP and len(w) > 1]


def _best_epreuve(day_page: str, race_name: str) -> Optional[str]:
    rw = set(_words(race_name))
    if not rw:
        return None
    best, best_score = None, 0.0
    for href in dict.fromkeys(re.findall(r'href="(/epreuve/\d+/[^"#]+)"', day_page)):
        slug = href.rsplit("/", 1)[-1]
        sw = set(netutil.normalize(slug.replace("-", " ")).split())
        hit = len(rw & sw)
        if hit == 0 or hit < (len(rw) + 1) // 2:
            continue
        penalty = len(sw & BAD_SLUG - set(netutil.normalize(race_name).split()))
        score = hit / len(rw) - 0.5 * penalty - 0.01 * len(sw)
        if score > best_score:
            best, best_score = href, score
    return best


def _best_article(epreuve_page: str, race_name: str) -> Optional[str]:
    rw = set(_words(race_name))
    own = set(netutil.normalize(race_name).split())
    cands = []
    for href, aid in re.findall(r'href="(/actualite/(\d+)/[^"#]+)"', epreuve_page):
        sw = set(netutil.normalize(href.rsplit("/", 1)[-1].replace("-", " ")).split())
        if rw and rw <= sw and not ((sw & BAD_SLUG) - own):
            cands.append((int(aid), href))
    return max(cands)[1] if cands else None


def _article_text(page: str) -> str:
    txt = re.sub(r"<(script|style|noscript|svg|nav|header|footer|form|aside)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    m = re.search(r"<h1", txt)
    if m:
        txt = txt[m.start():]
    txt = re.sub(r"</(p|div|h[1-6]|li|blockquote)>|<br\s*/?>", "\n", txt, flags=re.I)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", txt)).replace("\xa0", " ")
    lines = [" ".join(l.split()) for l in txt.splitlines()]
    junk = ("une course, un coureur, une actualit", "Button added", "Commentaires", "Lire aussi", "Partager")
    kept: List[str] = []
    for l in lines:
        if len(l) >= 40 and not any(j in l for j in junk) and (not kept or kept[-1] != l):
            kept.append(l)
    return "\n".join(kept)


def find_story(race_name: str, date: str) -> Optional[str]:
    """Texte brut de l'article de compte rendu de la course du `date` (AAAA-MM-JJ), ou None."""
    try:
        day = _page(f"{BASE}/resultats/{date}")
        if not day:
            return None
        epreuve = _best_epreuve(day, race_name)
        if not epreuve:
            print(f"[INFO] DirectVélo : course « {race_name} » absente de la liste du {date}")
            return None
        page = _page(BASE + epreuve)
        art = _best_article(page, race_name) if page else None
        if not art:
            print(f"[INFO] DirectVélo : pas d'article de compte rendu trouvé pour {race_name} ({epreuve})")
            return None
        body = _page(BASE + art)
        text = _article_text(body) if body else ""
        return text[:6000] or None
    except Exception as e:
        print(f"[WARN] DirectVélo : {e}")
        return None
