#!/usr/bin/env bash
# Un passage de veille d'update.yml : relance update.yml quand son passage a été sauté. Appelé par veille_update.yml (cron,
# secours) ET par battement.yml (toutes les 10 min). Mêmes règles dans les deux cas :
#   - entre 13 h et 23 h UTC (créneau des courses) : si le dernier passage date d'au moins 50 min ;
#   - entre 7 h et 9 h UTC (heures 7 et 8) : si le dernier passage date d'au moins 3 h (rattrapage du cron matinal de 6 h 41) ;
#   - hors de ces créneaux : rien.
# Rien n'est relancé si un passage d'update.yml est en file ou en cours (vérifié juste avant la relance).
# Environnement : REPO, GH_TOKEN. Surcharges facultatives (essais locaux) : MAINTENANT (secondes epoch), HEURE_UTC.
set -u
RACINE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
. "$RACINE/commun.sh"
: "${REPO:?REPO manquant}"
maintenant=${MAINTENANT:-$(date -u +%s)}
heure=$((10#${HEURE_UTC:-$(date -u +%H)}))
if [ "$heure" -ge 13 ] && [ "$heure" -le 23 ]; then
  seuil=50
elif [ "$heure" -ge 7 ] && [ "$heure" -le 8 ]; then
  seuil=180
else
  echo "[VEILLE] ${heure} h UTC : hors créneau, rien à faire"
  exit 0
fi
wf=update.yml
en_cours=$(nb_en_cours "$wf")
if [ "$en_cours" != "0" ]; then echo "[VEILLE] $wf : un passage est en file ou en cours (ou liste illisible : $en_cours), rien à faire"; exit 0; fi
dernier=$(date_dernier_passage "$wf" createdAt)
if [ "$dernier" = "?" ]; then echo "[VEILLE] $wf : liste des passages illisible, rien à faire"; exit 0; fi
if [ -n "$dernier" ]; then
  age=$(( (maintenant - $(date -u -d "$dernier" +%s)) / 60 ))
else
  age=999999
fi
if [ "$age" -lt "$seuil" ]; then echo "[VEILLE] $wf : dernier passage il y a ${age} min (< ${seuil} min, ${heure} h UTC), rien à faire"; exit 0; fi
# contrôle « en file ou en cours » refait juste avant la relance
if [ "$(nb_en_cours "$wf")" != "0" ]; then echo "[VEILLE] $wf : un passage vient d'être lancé, rien à faire"; exit 0; fi
echo "[VEILLE] $wf : dernier passage il y a ${age} min (>= ${seuil} min, ${heure} h UTC) : relance"
gh workflow run "$wf" --repo "$REPO" --ref "$REF_RELANCE"
