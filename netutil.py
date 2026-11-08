#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accès HTTP commun à toutes les sources : politesse (pause minimale par hôte, User-Agent honnête),
reprises, détection des pages anti-robot (abandon sans contournement), sauvegarde brute optionnelle."""

import gzip
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

USER_AGENT = "courses-cyclistes/1.0 (+https://github.com/Camelbaggy/courses-cyclistes)"
DEFAULT_DELAY = 1.2
HOST_DELAYS = {"www.directvelo.com": 10.5}  # Crawl-delay: 10 déclaré dans robots.txt

_last_call: Dict[str, float] = {}
_blocked_hosts: set = set()
_RAW_DIR: Optional[str] = None


def set_raw_dir(path: Optional[str]) -> None:
    """Si défini, chaque réponse est aussi sauvegardée dans ce dossier (debug)."""
    global _RAW_DIR
    if path:
        os.makedirs(path, exist_ok=True)
    _RAW_DIR = path


def _wait_for_host(host: str) -> None:
    delay = HOST_DELAYS.get(host, DEFAULT_DELAY)
    elapsed = time.monotonic() - _last_call.get(host, 0.0)
    if elapsed < delay:
        time.sleep(delay - elapsed)
    _last_call[host] = time.monotonic()


def _save_raw(raw_name: str, text: str) -> None:
    if _RAW_DIR and raw_name:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name)[:150]
        with open(os.path.join(_RAW_DIR, safe), "w", encoding="utf-8") as f:
            f.write(text)


def _looks_like_challenge(status: int, text: str) -> bool:
    return status in (403, 429, 503) and ("Just a moment" in text or "challenge-platform" in text or "cf-" in text)


def fetch_text(url: str, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None,
               retries: int = 3, raw_name: str = "") -> Optional[str]:
    """GET (ou POST si `data`) poli ; renvoie le corps décodé ou None. Un hôte qui renvoie un challenge
    anti-robot, un 403 ou un 429 est abandonné pour toute la durée du passage."""
    host = urllib.parse.urlparse(url).netloc
    if host in _blocked_hosts:
        return None
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "gzip"}
    hdrs.update(headers or {})
    for attempt in range(retries):
        _wait_for_host(host)
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method="POST" if data else "GET")
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                if body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
                text = body.decode(resp.headers.get_content_charset() or "utf-8", "replace")
            _save_raw(raw_name, text)
            return text
        except urllib.error.HTTPError as e:
            try:
                txt = e.read(4000).decode("utf-8", "replace")
            except Exception:
                txt = ""
            if e.code in (403, 429) or _looks_like_challenge(e.code, txt):
                print(f"[WARN] {host} refuse l'accès (HTTP {e.code}) : source abandonnée pour ce passage")
                _blocked_hosts.add(host)
                return None
            print(f"[WARN] HTTP {e.code} sur {url}")
            if e.code in (400, 404, 410):
                return None
        except Exception as e:
            print(f"[WARN] Erreur réseau sur {url} : {e}")
        time.sleep(2 ** attempt)
    return None


def fetch_json(url: str, retries: int = 3, raw_name: str = "") -> Optional[Any]:
    text = fetch_text(url, headers={"Accept": "application/json"}, retries=retries, raw_name=raw_name)
    return _parse_json(text, url)


def post_form_json(url: str, fields: Any, headers: Optional[Dict[str, str]] = None,
                   retries: int = 3, raw_name: str = "") -> Optional[Any]:
    """POST application/x-www-form-urlencoded (dict ou liste de paires), réponse JSON attendue."""
    body = urllib.parse.urlencode(fields).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Accept": "application/json"}
    hdrs.update(headers or {})
    return _parse_json(fetch_text(url, data=body, headers=hdrs, retries=retries, raw_name=raw_name), url)


def _parse_json(text: Optional[str], url: str) -> Optional[Any]:
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        print(f"[WARN] Réponse non JSON sur {url} : {text[:120]!r}")
        return None


def normalize(name: str) -> str:
    """Minuscules ASCII sans ponctuation, espaces simples (rapprochements de noms)."""
    txt = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    txt = re.sub(r"[^a-z0-9]+", " ", txt.lower())
    return " ".join(txt.split())


def slugify(name: str) -> str:
    return normalize(name).replace(" ", "-")


def flag_code(code3: Optional[str]) -> Optional[str]:
    """Code pays 3 lettres (CIO/UCI) -> code flagcdn.com, ou None."""
    return FLAG_CODES.get((code3 or "").strip().upper())


# Code pays CIO/UCI (3 lettres) -> code drapeau flagcdn.com (ISO 3166-1 ; sous-divisions pour le Royaume-Uni).
# Les 55 fédérations UEFA + les nationalités les plus fréquentes hors d'Europe.
FLAG_CODES = {
    "ALB": "al", "AND": "ad", "ARM": "am", "AUT": "at", "AZE": "az", "BLR": "by", "BEL": "be", "BIH": "ba",
    "BUL": "bg", "CRO": "hr", "CYP": "cy", "CZE": "cz", "DEN": "dk", "ENG": "gb-eng", "EST": "ee", "FRO": "fo",
    "FIN": "fi", "FRA": "fr", "GEO": "ge", "GER": "de", "GIB": "gi", "GRE": "gr", "HUN": "hu", "ISL": "is",
    "IRL": "ie", "ISR": "il", "ITA": "it", "KAZ": "kz", "KOS": "xk", "LVA": "lv", "LIE": "li", "LTU": "lt",
    "LUX": "lu", "MLT": "mt", "MDA": "md", "MNE": "me", "NED": "nl", "MKD": "mk", "NIR": "gb-nir", "NOR": "no",
    "POL": "pl", "POR": "pt", "ROU": "ro", "RUS": "ru", "SMR": "sm", "SCO": "gb-sct", "SRB": "rs", "SVK": "sk",
    "SVN": "si", "SLO": "si", "GBR": "gb", "ERI": "er", "ESP": "es", "SWE": "se", "SUI": "ch", "TUR": "tr", "UKR": "ua", "WAL": "gb-wls", "MON": "mc",
    # Amériques
    "ARG": "ar", "BRA": "br", "URU": "uy", "PAR": "py", "CHI": "cl", "COL": "co", "ECU": "ec", "PER": "pe",
    "VEN": "ve", "BOL": "bo", "MEX": "mx", "USA": "us", "CAN": "ca", "JAM": "jm", "CRC": "cr", "HON": "hn",
    "PAN": "pa", "HAI": "ht", "SUR": "sr", "CUW": "cw", "GUA": "gt", "SLV": "sv", "TRI": "tt", "DOM": "do",
    "CUB": "cu", "GRN": "gd", "MTQ": "mq", "GLP": "gp", "GUF": "gf",
    # Afrique
    "MAR": "ma", "ALG": "dz", "TUN": "tn", "EGY": "eg", "LBY": "ly", "SEN": "sn", "CIV": "ci", "CMR": "cm",
    "NGA": "ng", "GHA": "gh", "MLI": "ml", "BFA": "bf", "GUI": "gn", "COD": "cd", "CGO": "cg", "GAB": "ga",
    "GAM": "gm", "CPV": "cv", "ZAM": "zm", "ZIM": "zw", "RSA": "za", "ANG": "ao", "MOZ": "mz", "KEN": "ke",
    "TOG": "tg", "BEN": "bj", "NIG": "ne", "GNB": "gw", "SLE": "sl", "LBR": "lr", "MTN": "mr", "MAD": "mg",
    "COM": "km", "CTA": "cf", "EQG": "gq", "BDI": "bi", "RWA": "rw", "TAN": "tz", "UGA": "ug", "ETH": "et",
    "SUD": "sd", "MWI": "mw", "NAM": "na", "BOT": "bw",
    # Asie / Océanie
    "JPN": "jp", "KOR": "kr", "CHN": "cn", "AUS": "au", "NZL": "nz", "IRN": "ir", "IRQ": "iq", "KSA": "sa",
    "QAT": "qa", "UAE": "ae", "UZB": "uz", "JOR": "jo", "SYR": "sy", "LBN": "lb", "PLE": "ps", "IND": "in",
    "IDN": "id", "THA": "th", "MAS": "my", "OMA": "om", "BRN": "bh", "RWA": "rw", "ERI": "er", "SGP": "sg", "TPE": "tw", "HKG": "hk", "MGL": "mn", "LAO": "la", "CAM": "kh", "BAN": "bd", "SRI": "lk", "NEP": "np", "VIE": "vn", "PHI": "ph", "KGZ": "kg", "TJK": "tj", "TKM": "tm", "PAK": "pk",
    # Variantes de codes rencontrées
    "TGO": "tg", "NCL": "nc", "REU": "re", "MYT": "yt", "MRI": "mu", "CHA": "td", "DJI": "dj", "ERI": "er",
    "SSD": "ss", "SOM": "so", "LES": "ls", "SWZ": "sz", "SEY": "sc", "STP": "st", "GUY": "gy", "BRB": "bb",
    "LCA": "lc", "SKN": "kn", "ATG": "ag", "BLZ": "bz", "NCA": "ni", "ARU": "aw", "BER": "bm", "PUR": "pr",
}
