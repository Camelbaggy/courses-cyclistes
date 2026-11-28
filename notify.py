#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notification push légère via ntfy.sh.
Publie `index["notification"]` (construit par le pipeline) avec la publication JSON de ntfy (POST sur la racine
du serveur) : les accents et apostrophes du titre passent sans souci, contrairement aux en-têtes HTTP.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "").strip()


def _stage_tag(item: dict) -> str:
    """Construit un tag déterministe d'étape/course à partir d'un élément de `latest`."""
    stage_num = item.get("stage_number")
    label = (item.get("label") or "").strip()
    if stage_num is not None:
        m = re.search(r"(?:Étape|Etape)\s*(\d+[a-zA-Z]?)", label, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return str(stage_num)
    if label:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", label).strip("-").lower()
        if slug and slug != "course":
            return slug
    return "final"


def build_app_webhook_events(index_data: dict) -> list[dict]:
    """Construit les événements webhook Sport Hub à partir des résultats récents de `index_data`."""
    if not isinstance(index_data, dict):
        return []

    latest = index_data.get("latest") or []
    if not isinstance(latest, list) or not latest:
        return []

    races_by_id = {
        r["id"]: r
        for r in (index_data.get("races") or [])
        if isinstance(r, dict) and r.get("id")
    }

    events: list[dict] = []
    for item in latest[:5]:
        if not isinstance(item, dict):
            continue
        race_id = (item.get("race_id") or "").strip()
        if not race_id:
            continue

        race = races_by_id.get(race_id, {})
        race_name = item.get("race_name") or race.get("name") or race_id
        label = (item.get("label") or "Course").strip()
        stage_tag = _stage_tag(item)
        categorie = race.get("category") or ""

        winner = item.get("winner") if isinstance(item.get("winner"), dict) else {}
        winner_name = (winner.get("name") or "").strip()
        winner_nat = (winner.get("nationality") or "").strip().upper()
        winner_is_french = bool(winner.get("is_french") is True or winner_nat == "FRA")

        best_french = item.get("best_french") if isinstance(item.get("best_french"), dict) else {}
        bf_rider = best_french.get("rider") if isinstance(best_french.get("rider"), dict) else {}
        bf_name = (bf_rider.get("name") or "").strip()
        raw_bf_rank = best_french.get("rank")
        try:
            francais_top = int(raw_bf_rank) if raw_bf_rank is not None else None
        except (TypeError, ValueError):
            francais_top = None

        coureurs: list[str] = []
        for name in (winner_name, bf_name):
            if name and name not in coureurs:
                coureurs.append(name)

        deep_link = f"sporthub://cycling/race/{race_id}"
        attributes = {
            "categorie": categorie,
            "francais_top": francais_top,
            "coureur": coureurs,
            "vainqueur_pays": winner_nat,
        }

        spoiler_safe_title = f"Résultat disponible : {race_name} ({label})"
        spoiler_safe_body = f"Le classement de {race_name} ({label}) est disponible."

        if winner_name:
            nat_suffix = f" ({winner_nat})" if winner_nat else ""
            title = f"{race_name} ({label}) — {winner_name}{nat_suffix}"
        else:
            title = f"{race_name} ({label})"

        body_parts: list[str] = []
        if winner_name:
            body_parts.append(f"Vainqueur : {winner_name}")
        if bf_name and francais_top is not None:
            body_parts.append(f"Meilleur Français : {bf_name} ({francais_top}e)")
        body = " · ".join(body_parts) if body_parts else spoiler_safe_body

        events.append({
            "event_key": f"cycling:{race_id}:{stage_tag}:stage_result",
            "sport": "cycling",
            "event_type": "stage_result",
            "title": title,
            "body": body,
            "spoiler_safe_title": spoiler_safe_title,
            "spoiler_safe_body": spoiler_safe_body,
            "deep_link": deep_link,
            "is_live": False,
            "attributes": dict(attributes),
        })

        if francais_top is not None and francais_top <= 10:
            fr_title = (
                f"Top 10 français : {bf_name} ({francais_top}e) — {race_name}"
                if bf_name
                else f"Top 10 français ({francais_top}e) — {race_name}"
            )
            fr_body = f"{bf_name} termine {francais_top}e de {race_name} ({label})." if bf_name else body
            events.append({
                "event_key": f"cycling:{race_id}:{stage_tag}:french_top10",
                "sport": "cycling",
                "event_type": "french_top10",
                "title": fr_title,
                "body": fr_body,
                "spoiler_safe_title": spoiler_safe_title,
                "spoiler_safe_body": spoiler_safe_body,
                "deep_link": deep_link,
                "is_live": False,
                "attributes": dict(attributes),
            })

        if winner_is_french:
            win_title = (
                f"Victoire française : {winner_name} — {race_name} ({label})"
                if winner_name
                else f"Victoire française — {race_name} ({label})"
            )
            win_body = (
                f"{winner_name} remporte {race_name} ({label})."
                if winner_name
                else f"Victoire française sur {race_name} ({label})."
            )
            events.append({
                "event_key": f"cycling:{race_id}:{stage_tag}:french_win",
                "sport": "cycling",
                "event_type": "french_win",
                "title": win_title,
                "body": win_body,
                "spoiler_safe_title": spoiler_safe_title,
                "spoiler_safe_body": spoiler_safe_body,
                "deep_link": deep_link,
                "is_live": False,
                "attributes": dict(attributes),
            })

    return events


def send_app_webhooks(index_data: dict) -> bool:
    """Envoie les événements vers le webhook Sport Hub si configuré. 100 % optionnel et non-bloquant."""
    webhook_url = os.environ.get("APP_WEBHOOK_URL", "").strip()
    webhook_secret = os.environ.get("APP_WEBHOOK_SECRET", "").strip()
    if not webhook_url or not webhook_secret:
        return False

    try:
        events = build_app_webhook_events(index_data)
        if not events:
            return False

        req = urllib.request.Request(
            webhook_url,
            data=json.dumps({"events": events}, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": webhook_secret,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[WEBHOOK] {len(events)} événement(s) cyclisme envoyé(s) (HTTP {resp.status}).")
            return True
    except Exception as e:
        print(f"[WEBHOOK] Échec non-bloquant : {e}")
        return False


def send(index_path: str = "data/index.json") -> bool:
    """Envoie la notification si `notification.send` est vrai. Renvoie True si le push est parti."""
    if not os.path.exists(index_path):
        print(f"[WARN] {index_path} introuvable. Aucune notification envoyée.")
        return False
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        notif = data.get("notification") or {}
    except (OSError, ValueError) as e:
        print(f"[WARN] {index_path} illisible ({e}). Aucune notification envoyée.")
        return False

    if not notif.get("send"):
        print("[INFO] Aucun nouveau résultat. Pas de push ntfy.")
        return False

    send_app_webhooks(data)

    payload = {
        "topic": NTFY_TOPIC,
        "title": notif.get("title") or "Cyclisme : nouveaux résultats",
        "message": notif.get("message") or "Nouveaux résultats disponibles.",
        "tags": ["bike", "trophy"],
    }
    if DASHBOARD_URL:
        payload["click"] = DASHBOARD_URL
        payload["actions"] = [{"action": "view", "label": "Ouvrir le dashboard", "url": DASHBOARD_URL, "clear": True}]

    if not NTFY_TOPIC:
        print("[INFO] NTFY_TOPIC non défini. Simulation du push :")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return False

    req = urllib.request.Request(
        NTFY_SERVER,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[OK] Push ntfy envoyé (HTTP {resp.status}).")
            return True
    except (urllib.error.URLError, OSError) as e:
        print(f"[ERREUR] Échec de l'envoi ntfy : {e}")
        return False


if __name__ == "__main__":
    send()

