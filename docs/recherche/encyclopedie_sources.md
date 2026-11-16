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

## Précisions apportées en E1b (code `wikidata.py`)

- **Occupation** : l'essai n'utilisait que `haswbstatement:P106=Q2309784` (correspondance directe, pas de sous-classes). Le code garde cette recherche
  (une seule requête par coureur) mais vérifie l'occupation du candidat par P106 = Q2309784 OU sous-classe (P279, 4 niveaux, mémorisé) ; au lancement
  il contrôle que Q2309784 porte bien un libellé « cycl… » (sinon les coureurs sont ignorés). Limite : un cycliste dont la SEULE occupation est une
  sous-classe n'est pas trouvé par la recherche filtrée (`FALLBACK_LIBRE`, désactivé : une requête de plus par coureur obscur).
- **« Un seul candidat »** = un seul candidat VÉRIFIÉ (date + nom + occupation) parmi les résultats ; deux candidats vérifiés (homonymes de même date) : rien.
- **Noms composés** : seconde recherche (sans le dernier jeton) uniquement pour les noms de 3 jetons ou plus (« Jonas Vingegaard Hansen » -> « Jonas
  Vingegaard ») ; l'inclusion de jetons exige au moins 2 jetons côté Wikidata.
- **Équipes** : une déclaration P1998 sans période (ni P580 ni P582) ne prouve rien et est refusée ; idem pour un nom P1448 sans période (la preuve par
  le libellé d'un élément « saison » contenant l'année reste possible). Saison UCI = année de fin de saison (2023 = 2023).
- **Premier passage réel (10 min : 273/280 coureurs, 634 équipes-saisons)** : (1) `naissance` (P569) est conservée dans `coureurs.json` pour
  un contrôle a posteriori ; les entrées plus anciennes sans ce champ ne sont pas re-vérifiées. (2) 21 équipes « ambigu » (Movistar, Lidl-Trek,
  Visma…) : l'équipe féminine ou la réserve porte le même code UCI. Les parents dont une classe P31 a un libellé fr/en féminin (women, féminin,
  femmes…) sont écartés ; si plusieurs parents restent prouvés, les équipes de développement (development, devo, U23, réserve, continental) sont
  écartées seulement si EXACTEMENT un parent de premier niveau (WorldTeam, ProTeam, Professional Continental) reste ; sinon « ambigu ». (3) 89 équipes
  « aucune » (libellé UCI différent du nom Wikidata, ex. 7Eleven) : preuve plus faible `code+periode`, acceptée seulement si UN SEUL parent (après
  filtre féminin) a une déclaration P1998 du code dont la période, avec au moins une borne explicite (P580 ou P582), contient la saison ; elle
  n'intervient que si aucun parent n'est prouvé par `code+nom` (qui reste prioritaire), et jamais pour départager plusieurs `code+nom`. L'interface
  peut la nuancer grâce à `preuve`. Les entrées `null` des règles antérieures sont re-tentées (champ `regle`, `REGLE_EQUIPES`). (4) Journal de
  progression toutes les ~5 min et rythme en synthèse. (5) Une licence Commons sans URL (« Public domain ») est conservée (`licence` seule).

## WorldDB (base communautaire PCM)

Analyse locale du 16/11/2026 (aucun réseau, base lue seulement ; `tools/audit_worlddb.py`). **WorldDB** est la base de données communautaire du
jeu Pro Cycling Manager (éditeur Cyanide / Nacon), en CSV (versions « Official Release » et « 2025 Season Start »), saisie à la main par des
bénévoles. Aucune mention de licence, d'auteur ni de crédit dans les fichiers : **droits non établis**. Ce n'est pas une source primaire et elle
n'est jamais citable.

**Contenu** (156 tables, 100 non vides ; chiffres « 2025 Season Start ») : coureurs 8 359 (nom, naissance AAAAMMJJ, région → nationalité, taille, poids,
équipe 2025) ; équipes 307 et historique de noms par année 1980-2024 (206 équipes, 1 993 lignes) ; palmarès 44 008 lignes 1997-2024 (classement
général, étapes, points, montagne, jeunes ; exploitable surtout 2007-2024) ; courses 678 (nom, pays, classe de jeu, nombre d'étapes de jeu, jour / mois de
chaque étape SANS année). Le reste est du jeu (caractéristiques, potentiel, popularité, budgets, contrats 2025, coachs, matériel…) ou des données
personnelles (670 e-mails d'organisateurs). Ni distances, ni profils, ni villes, ni dates complètes de courses.

**Concordance mesurée avec nos données** (nos 13 525 coureurs, nos 539 épreuves) :
- coureurs : 5 893 de nos coureurs retrouvés (43,6 %) par date de naissance exacte + noms égaux ou inclus (88 % des coureurs WorldDB de division World
  Tour, 76 % Pro, 69 % Continental) ; nationalité : 99,7 % de concordance après une table d'alias de 34 codes de pays (20 conflits, parfois
  légitimes : nationalité sportive ≠ naissance) ; 79 coureurs de même nom avec une date de naissance différente (49 même année, 7 un chiffre, 5 jour / mois
  inversés, 18 homonymes probables) ; 9 coureurs correspondant à deux de nos `rider_id` (doublons chez nous) ;
- vainqueurs 2019-2024 : 744 éditions comparées, 722 concordantes (97,0 %), 16 variantes de nom, 6 vrais désaccords à arbitrer ; palmarès avant 2007
  absent, 2007-2010 présent mais à 98 % sans date de naissance (rapprochement par nom seul) ;
- équipes : 704 de nos 1 184 équipes-saisons 2019-2024 rapprochées par nom exact et année (0 ambiguïté), 194 lignées de plus d'une saison dont 110 avec
  renommages ; sur 140 lignées comparables avec Wikidata, 139 cohérentes (une contradiction à vérifier, REMBE) ;
- courses : 259 épreuves rapprochées (nom + pays exacts) ; nombre d'étapes identique dans 92 % des cas, jour / mois de début identique dans 20 cas sur 352 ;
- taille : divergence ≥ 3 cm avec Wikidata dans 5 % des cas ; valeur 0 = inconnu (56 % des tailles, 64 % des poids).

**Usages autorisés** (validés par le propriétaire du projet) : (1) contrôle croisé, c'est-à-dire un rapport d'écarts (dates de naissance, nationalités,
vainqueurs, doublons de `rider_id`) à revérifier par des sources officielles (UCI DataRide, Wikidata, Wikipédia, `tools/essais/essai_verif_ecarts.py`)
avant toute correction ; (2) propositions d'équivalences d'équipes-saisons (même lignée WorldDB qu'une équipe déjà rattachée à Wikidata avec preuve
`code+nom` ou `code+periode`), validées à la main une par une avant d'entrer dans `alias_equipes.json` (jamais écrites automatiquement). Dans les deux cas
seul le résultat vérifié à la source officielle est repris, jamais la valeur WorldDB.

**Usages proscrits** : publier ou copier du contenu WorldDB (entités, archives, pages, fichiers de test) tant que les droits ne sont pas établis ;
reprendre un champ de jeu (`value_*`, `charac_*`, `gene_f_*`, potentiel, popularité, budgets, évaluations, contrats) ; taille et poids (arrondis, valeurs de
jeu) ; dates et nombre d'étapes des courses (calendrier de jeu lissé) ; palmarès avant 2011 comme fait publié ; e-mails d'organisateurs et toute donnée
personnelle ; coureurs « libres » non rapprochés (fictifs possibles). La base et les rapports qui en reprennent des valeurs restent **hors des dépôts
publics** (scratchpad ou disque local) ; `tools/audit_worlddb.py` refuse d'écrire dans un dépôt git et ne contient que du code.

## Vérification des écarts WorldDB (16 novembre 2026)

Le rapport d'écarts (usage 1 ci-dessus) a été vérifié sur Wikidata (`tools/essais/essai_verif_ecarts.py`, 240 requêtes, 3,9 min). Aucune valeur WorldDB n'est
reprise : seules les valeurs Wikidata confirmées par une 2e source indépendante (concordance avec WorldDB) sont entrées dans `corrections_coureurs.json`.

**Chiffres.** Écarts de date de naissance : 99 coureurs contrôlés (79 écarts WorldDB + coureurs des contrôles de nationalité) : 48 notre date confirmée par
Wikidata, 10 date Wikidata différente, 41 non trouvés ou ambigus (aucun candidat vérifié). Nationalités : 20 contrôles. Éditions : 6 (4 confirmées dont 1
faux positif du script, 2 indéterminées). Doublons de `rider_id` : 9.

**Corrections faites (9, `corrections_coureurs.json`)** : naissance, quand Wikidata (précision jour) et WorldDB concordent contre l'UCI : Souleymane Koné
(1997-06-15 -> 06-14, Q55714714), Tobias Lund Andresen (2002-02-08 -> 08-20, Q98918621), Ariya Phounsavath (1991-02-03 -> 03-02, Q22893639), Andrew Ramsay
(1998-09-24 -> 04-24, Q134087532), Abel Rosado Arroyo (2003-05-08 -> 08-05, Q136841423 ; nationalité PUR chez l'UCI, USA sur Wikidata : non corrigée),
Aliaksandr Sychuhou (2002-12-19 -> 02-19, Q118444544), Kajetan Wąsowicz (2004-01-05 -> 06-03, Q124432575) ; nationalité, la date de naissance étant égale :
Tiano Da Silva (CHN -> RSA, Q112656245), Roman Ermakov (SLO -> RUS, Q124388036).

**Cas laissés tels quels** : Amir Ansari (Wikidata 1999-08-26, WorldDB sans écart, nationalité REF / SWE / Afghanistan : trois sources, aucune concordance) ;
Martin Popov (trois dates distinctes) ; João Silva 2007 (homonyme probable, Wikidata 2002, WorldDB 2003) ; nationalités d'athlètes sous bannière
particulière (Macao : Kam Chin Pok MAC / CHN ; réfugiés : REF / SYR, Wais Ahmad Badreddin) et doubles nationalités (De Fabritiis, Meunier Sow, Poulard,
Frislie : nationalité sportive de la licence ≠ nationalité de naissance, pas une erreur de l'UCI) ; 41 coureurs non retrouvés sur Wikidata (pas de
contre-preuve : non modifiés). Éditions : Circuit des Ardennes 2023, Turul României 2024 (Wikidata confirme l'UCI), Tour de l'Ain 2024 (variante de nom),
Tour de Wallonie 2022 et Tour of Thailand 2022 (indéterminés). **La Polynormande 2022** : l'UCI classe Rota 1er, Wikidata Bonnamour (Rota 2e) ; on garde l'UCI
(source officielle du projet), aucune correction de classement.

**Doublons de `rider_id` (9 paires, mêmes date de naissance, nationalité et mots du nom, saisons cohérentes)** : 4 ajoutés à `alias_coureurs.json`
(canonique = id aux saisons les plus nombreuses) : `solhaug-hansen-martin-20030511` -> `hansen-martin-solhaug-20030511`, `assis-moreira-lino-guilherme-20060808` ->
`lino-guilherme-20060808`, `kamena-tshiyana-loick-20000525` -> `kamena-tshiyana-20000525`, `teshome-meron-19920713` -> `teshome-hagos-meron-19920713`.
5 paires non ajoutées : les deux identifiants figurent la même saison (la règle de contradiction ignorerait l'alias, sans effet et avec un `[WARN]` à chaque
génération) : D'Unienville (2023), D'Aquila Silva (2022), Zegklis (2025), Haikkal (2022), Harvey (2023).
