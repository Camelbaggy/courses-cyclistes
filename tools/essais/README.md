# Essais réseau

Le conteneur de développement n'a pas d'accès réseau aux sources. Pour tester un module sur les vraies données :
écrire `tools/essais/essai_<nom>.py` (exécuté depuis la racine du dépôt : `sys.path.insert(0, ".")` puis
`import <module>`), puis pousser sur une branche `ccr-*` un commit dont le message contient `[essai:<nom>]`
(plusieurs balises possibles). Ajouter `[avec-ia]` pour autoriser Gemini (sinon `AI_BUDGET_SECONDS=0`).
Lire ensuite les logs du job « Essais réseau ».

## Essais disponibles

- `archives`, `archives_collecte`, `pages_archives` : saisons passées (DataRide) et archives.
- `classement_historique` (E1c) : moments du classement UCI (forme brute), choix des instantanés, un instantané complet (2027 et 2018).
- `calendrier`, `classement`, `collecte`, `enrich`, `fiches`, `ia`, `uci` : modules du collecteur.
- `encyclopedie` (étape E0 de `docs/PLAN_ENCYCLOPEDIE.md`) : `TeamCode` DataRide sur plusieurs saisons, classements par
  équipes, ligne brute de `Results`, délai de publication du classement UCI, couverture Wikidata (40 coureurs,
  10 lignées d'équipes) et longueur des introductions Wikipédia en six langues. Durée visée < 20 min ; chaque partie
  est isolée (une panne n'arrête pas les suivantes) et la synthèse finale résume les mesures. Politesse Wikimedia :
  User-Agent de `netutil` (URL du projet), ≤ 1 requête/s, `maxlag=5`, pas d'insistance sur un 429.
- `encyclopedie2` (second passage de l'étape E0, sans SPARQL) : `TeamId` DataRide (stabilité sur 5 saisons, noms changeants,
  réutilisation), coureurs Wikidata retrouvés par l'API de recherche (`haswbstatement:P11020=<UciId>`, sinon nom + date de
  naissance vérifiée), équipes par `haswbstatement:P1998=<code UCI>` (P31, P5138, P1448, P1365/P1366). Importe
  `essai_encyclopedie.py`. Durée visée < 14 min, ≤ 1 requête/s, `maxlag=5`.

Audit local sans réseau, hors essais : `python tools/audit_identites.py <data/archives du dépôt d'archives>`
(doublons de coureurs : noms à plusieurs dates, `uci_id` ↔ `rider_id`, coureurs sans date de naissance).
