#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notification push légère via ntfy.sh.
Publie `index["notification"]` (construit par le pipeline) avec la publication JSON de ntfy (POST sur la racine
du serveur) : les accents et apostrophes du titre passent sans souci, contrairement aux en-têtes HTTP.
"""

import json
import os
import urllib.error
import urllib.request

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "").strip()


def send(index_path: str = "data/index.json") -> bool:
    """Envoie la notification si `notification.send` est vrai. Renvoie True si le push est parti."""
    if not os.path.exists(index_path):
        print(f"[WARN] {index_path} introuvable. Aucune notification envoyée.")
        return False
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            notif = json.load(f).get("notification") or {}
    except (OSError, ValueError) as e:
        print(f"[WARN] {index_path} illisible ({e}). Aucune notification envoyée.")
        return False

    if not notif.get("send"):
        print("[INFO] Aucun nouveau résultat. Pas de push ntfy.")
        return False

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
