# Étape E0 de l'encyclopédie : sources et identités

Date : 15 novembre 2026. Essais `[essai:encyclopedie]` (run 43760291292) et `[essai:encyclopedie2]` (run 43762195990),
audit local `tools/audit_identites.py` sur les archives 2020-2025. Wikimedia : API `wikidata.org` et `wikipedia.org`
(1 requête/s, User-Agent du projet, sans `maxlag` pour ces lectures : le retard de réplication de Wikidata dépassait
5 s et bloquait tout) ; le service SPARQL (`query.wikidata.org`) a répondu HTTP 502 sur les requêtes par date de
naissance : ne pas en dépendre.

## Verdicts

| Question | Réponse |
|---|---|
| Identifiant de coureur stable | `rider_id` (nom + naissance) reste la clé ; `UciId` n'est pas unique (21 coureurs en ont deux) ; P11020 de Wikidata ne correspond pas à l'`UciId` DataRide (40/40 différents) |
| Doublons de coureurs | rares : 5 inversions nom/prénom, 12 coureurs avec et sans date, 4 dates à quelques jours d'écart, 39 sans date, 1 nom vide qui mélange 3 personnes |
| Identifiant d'équipe UCI | `TeamId` toujours vide ; `TeamCode` change avec le sponsor (7 lignées sur 10) et peut être réattribué à une autre équipe (ALM : AG2R puis Almaty) ; absent des lignes de résultats (nom seul) |
| Classement des équipes de marque | inexistant chez l'UCI (les classements « type 3 » sont des classements de nations) |
| Délai du classement UCI | calcul chaque **mardi** ; course WT finie le dimanche → classement du mardi (2 jours), en semaine → mardi suivant (jusqu'à 6 jours) |
| Wikidata coureurs | 40/40 trouvés par nom + date de naissance exacte + occupation cycliste, sans ambiguïté ; lieu de naissance 38/40, taille 35/40, photo 39/40, équipes (P54) 40/40 avec début daté (souvent à l'année) ; article fr 40/40, en 38, it 38, nl 38, de 36, es 34 |
| Wikidata équipes | élément « équipe » stable + éléments « saison » (P5138) ; **noms officiels datés (P1448)** et **codes UCI datés (P1998)** sur l'élément équipe : ex. Quick-Step QSD 2003-04 … DQT 2019-21, QST 2022, SOQ 2023→ ; Decathlon A2R, ALM, ACT, DAT, DCT. La recherche par code seul ramène des homonymes (ALM, ACT…) : il faut **code + période + nom** |
| Wikipédia | intros présentes dans les 6 langues pour les 9 entités testées ; la plus riche varie (fr pour les Français, es ou en pour Pogačar, nl pour Groupama-FDJ, es pour Soudal Quick-Step) ; l'infobox « Dénominations » des équipes reprend l'historique des noms (comme P1448) |

## Décisions proposées pour E1

1. **Coureurs** : clé `rider_id` ; fusions par `alias_coureurs.json`, amorcé avec les cas de l'audit seulement quand une
   preuve les départage (même date et mêmes mots du nom ; ou Wikidata qui confirme la bonne date). Correspondance
   Wikidata (QID) par nom + date exacte + occupation cycliste, sinon rien ; table mise en cache dans le dépôt
   d'archives et complétée chaque nuit (nouveaux coureurs seulement, ~11 000 au départ, à 1 requête/s sur plusieurs
   nuits).
2. **Équipes** : une **équipe-saison** = (libellé, saison, code UCI du classement de la saison quand un coureur classé
   le porte). Une **lignée** = élément Wikidata de l'équipe, retenu seulement si son P1998 contient ce code **pour cette
   saison** et si un nom P1448 de cette année correspond au libellé (normalisé). Sans preuve : équipe-saison seule,
   ou `alias_equipes.json` manuel. L'historique des noms affiché vient de P1448 (daté, comme l'infobox Wikipédia
   « Dénominations ») ; parcours d'un coureur : nos données par saison, complétées par P54 de Wikidata (dates à la
   précision de la source).
3. **Textes** : introduction Wikipédia française (premières phrases, sans IA) quand elle existe ; synthèse Gemini à
   partir de plusieurs langues réservée aux entités les plus consultées (équipes WorldTour / ProTeam, coureurs à forte
   notoriété) et aux pages sans article français, générée une fois puis gardée tant que la source ne change pas
   (quota gratuit ménagé). Toujours 2-4 phrases, source et licence affichées.
4. **Photos** : P18 → Wikimedia Commons, avec auteur et licence lus sur Commons (`imageinfo` / `extmetadata`) ; pas de
   photo sans licence lisible.
5. **Classement UCI historique** : instantané du mardi suivant chaque course WT et du dernier mardi du mois ;
   rattrapage possible pour les saisons archivées (les moments passés sont listés par `GetRankingMoments`) ; stockage
   compact (rang, points, `rider_id`).
