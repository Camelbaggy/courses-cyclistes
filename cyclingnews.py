#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cyclingnews : flux RSS (texte intégral des articles, en anglais).

Usage strictement interne : le texte alimente les résumés IA, il n'est JAMAIS republié.
Le flux ne couvre que ~3 jours (50 articles) : à interroger souvent pendant les courses.
"""

import html
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

import netutil

FEED_URL = "https://www.cyclingnews.com/feeds.xml"
NS_CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
NS_DC_CONTENT = "{http://purl.org/dc/elements/1.1/}content"
STOPWORDS = {"de", "du", "la", "le", "les", "des", "d", "l", "et", "the", "of", "a", "tour", "grand", "prix",
             "gp", "race", "classic", "men", "elite", "hommes"}
NUMBER_WORDS = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven"}


def _html_to_text(raw: str) -> str:
    """HTML -> texte brut : retire scripts/styles, tableaux conservés en lignes, entités décodées."""
    txt = re.sub(r"<(script|style|noscript|figure|svg)[^>]*>.*?</\1>", " ", raw or "", flags=re.S | re.I)
    txt = re.sub(r"</(p|div|h[1-6]|li|tr|table|ul|ol|blockquote)>|<br\s*/?>", "\n", txt, flags=re.I)
    txt = re.sub(r"</t[dh]>", " | ", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = html.unescape(txt).replace("\xa0", " ")
    lines = [" ".join(l.split()) for l in txt.splitlines()]
    return "\n".join(l for l in lines if l)


def _parse_date(s: Optional[str]) -> Optional[str]:
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:
        return None


def fetch_items() -> List[Dict]:
    """Articles du flux : [{"title","date" (ISO),"categories","text","link"}]. [] en cas d'échec."""
    xml = netutil.fetch_text(FEED_URL, headers={"Accept": "application/rss+xml, application/xml"},
                             raw_name="cyclingnews_feed.xml")
    if not xml:
        return []
    try:
        root = ET.fromstring(xml.encode("utf-8"))
    except ET.ParseError as e:
        print(f"[WARN] Flux Cyclingnews illisible : {e}")
        return []
    items = []
    for it in root.iter("item"):
        body = it.findtext(NS_CONTENT) or it.findtext(NS_DC_CONTENT) or it.findtext("description") or ""
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "date": _parse_date(it.findtext("pubDate")),
            "categories": [c.text.strip() for c in it.findall("category") if c.text],
            "text": _html_to_text(body),
            "link": (it.findtext("link") or "").strip(),
        })
    return items


def _words(s: str) -> set:
    return {w for w in netutil.normalize(s).split() if w not in STOPWORDS and len(w) > 1}


def _stage_markers(stage_number: int) -> List[str]:
    marks = [f"stage {stage_number}"]
    if str(stage_number) in NUMBER_WORDS:
        marks.append(f"stage {NUMBER_WORDS[str(stage_number)]}")
    return marks


def find_story(items: List[Dict], race_name: str, date_iso: str, stage_number: Optional[int] = None) -> Optional[str]:
    """Meilleur article pour une course / étape : recouvrement de mots du nom de course dans le titre
    (ou dans le début du texte), date de publication à ±1 jour, numéro d'étape si présent.
    Renvoie le texte brut (titre + corps) ou None."""
    if not items or not race_name:
        return None
    try:
        day = date.fromisoformat(date_iso)
    except (TypeError, ValueError):
        return None
    rwords = _words(race_name)
    if not rwords:
        return None
    best, best_score = None, 0.0
    for it in items:
        try:
            d = date.fromisoformat(it["date"]) if it.get("date") else None
        except ValueError:
            d = None
        if d is None or abs((d - day).days) > 1:
            continue
        title_n = netutil.normalize(it["title"])
        head_n = netutil.normalize(it["text"][:400])
        tw = set(title_n.split())
        hw = set(head_n.split())
        score = len(rwords & tw) / len(rwords) + 0.5 * len(rwords & hw) / len(rwords)
        if len(rwords & (tw | hw)) < max(1, (len(rwords) + 1) // 2) or score < 0.5:
            continue
        cats = " ".join(it.get("categories") or []).lower()
        if "racing" in cats:
            score += 0.2
        if stage_number is not None:
            blob = title_n + " " + head_n
            if any(m in blob for m in _stage_markers(stage_number)):
                score += 0.6
            elif re.search(r"\bstage \w+", blob):
                score -= 0.6
        if score > best_score:
            best, best_score = it, score
    if best is None or best_score < 0.5:
        return None
    return best["title"] + "\n\n" + best["text"]
