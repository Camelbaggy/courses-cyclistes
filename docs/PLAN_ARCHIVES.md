# Plan d'action : récupération des saisons passées (archives)

Objectif : constituer une « encyclopédie » personnelle des courses suivies (hommes élite, focus français) en
remontant saison par saison, sans dégrader la lisibilité de la page ni la mise à jour horaire de la saison en cours.

## 1. Découpage en tranches de 5 ans : oui, avec la tranche récente d'abord

Travailler par tranches de 5 saisons est un bon compromis :

- **Validation par époque.** Les règles du cyclisme ont changé (voir §3) : une tranche correspond à peu près à une
  époque homogène de classes UCI, ce qui permet de vérifier la sélection et la qualité des données une fois par
  tranche plutôt qu'une fois par saison.
- **Volume maîtrisé.** Une tranche ≈ 15 à 20 h de collecte et, après compactage, ~50 Mo : on mesure l'effet sur le
  dépôt et la page avant d'aller plus loin.
- **Arrêt possible à tout moment** : chaque tranche publiée est utilisable seule.

Ordre proposé (du plus récent au plus ancien, car les données sont plus complètes et les coureurs encore connus) :

| Tranche | Saisons | Particularités |
|---|---|---|
| T1 | 2021 → 2025 | Époque actuelle (ProSeries depuis 2020) : mêmes classes qu'aujourd'hui ; Coupe de France puis FDJ United Series |
| T2 | 2016 → 2020 | Classes `HC` (1.HC / 2.HC) avant les ProSeries ; 2020 saison réduite (Covid) ; classement mondial UCI actuel depuis 2016 |
| T3 | 2011 → 2015 | UCI WorldTour (depuis 2011), classes HC ; classement mondial différent (WorldTour + circuits continentaux) |
| T4 | 2009 → 2010 | ProTour (`CPE`, `AU1`, `MNM`…) et calendrier historique (`1.CH` / `2.CH` : grands tours, monuments) séparés |

**Étape 0 faite** (`docs/recherche/archives_dataride.md`) : DataRide n'a de courses hommes élite qu'à partir de 2009
(2005-2008 : seulement les championnats du monde) ; T3 et T4 (réduite à 2009-2010) sont engageables, en dernier.
Limites constatées avant 2016 : pas de dossards (2009-2013), pas de championnats nationaux (`CN`), abandons du
général final des grands tours sans code (rang vide, aucune valeur), classement « WorldTour Ranking - Ends 2018 »
(~250 lignes) au lieu du World Ranking. Conditions d'utilisation de DataRide : aucune trouvée (à trancher).

## 2. Étape 0 : sonde de profondeur (préalable, ~1 h)

Essai `[essai:archives]` depuis GitHub Actions, sans rien collecter en masse :

1. Liste des saisons DataRide (`GetRestrictedResultsDisciplineSeasons`) : première année disponible.
2. Pour une saison par tranche (2023, 2018, 2013, 2008) : nombre de courses hommes élite, classes UCI rencontrées,
   et lecture complète de 3 courses témoins (un grand tour, une classique, une course française .1) : classements
   présents (étape, général, points, montagne, jeunes), abandons, dates de naissance, points UCI.
3. Moments disponibles du classement UCI (`GetRankingMoments`) par saison.
4. Lecture des conditions d'utilisation de DataRide avant une collecte de ce volume ; rythme volontairement lent
   (pause ≥ 2 s entre requêtes pour les archives).

Livrable : `docs/recherche/archives_dataride.md` (couverture réelle par époque) et décision sur T3/T4.

## 3. Adaptations du code

### Sélection par époque (`selection.py`)

| Aujourd'hui | Équivalent historique |
|---|---|
| `1.UWT` / `2.UWT` → WT | idem depuis 2011 ; `1.UWT`/`2.UWT` ou codes ProTour (`PT`) avant |
| `1.Pro` / `2.Pro` → Pro | `1.HC` / `2.HC` avant 2020 (rangées en « Pro », libellé d'origine conservé) |
| — | 2009-2010 : `1.CH` / `2.CH` (calendrier historique : grands tours, monuments) et classes ProTour (`CPE`, `AU1`, `MNM`) → WT |
| FDJ United Series | Coupe de France (liste par année : LNC si disponible, sinon Wikipédia « Coupe de France de cyclisme sur route {année} ») |
| .1 / .2, championnats | identiques |

La règle « .1/.2 étrangère avec un Français dans le top 10 » s'applique telle quelle.

### Collecte (`collector.py`, nouveau mode archive)

- `run_pipeline.py --archive 2021-2025` : collecte des saisons demandées **sans** toucher à la saison courante, sans
  notification, sans Gemini (résumés de repli déterministes), sans enrichissement ASO ni récits (les sites ne
  servent que l'édition en cours ; Cyclingnews/DirectVélo n'ont pas l'historique).
- Reprise : budget de temps par passage (déjà en place), décisions « top 10 français » mémorisées ; une saison est
  marquée « archivée » une fois complète et n'est plus jamais recollectée.
- Nouveau workflow `archives.yml` (`workflow_dispatch`, entrée « saisons »), séparé de `update.yml`, même groupe de
  concurrence pour ne jamais committer en même temps que la mise à jour horaire.

### Stockage et compactage

Aujourd'hui une saison pèse ~40 Mo (225 fichiers). Sans compactage, 20 saisons feraient ~800 Mo : trop pour un dépôt
servi par GitHub Pages et cloné à chaque passage horaire.

- **Fichiers d'archive compactés** (`data/archives/<année>/<id>.json`) : classement complet de chaque étape / course
  d'un jour, général complet, mais classements annexes (points, montagne, jeunes) limités au top 30 par étape
  (complets au classement final), clés courtes. Objectif ≤ 10 Mo par saison, ~50 Mo par tranche.
- **Seuil de bascule** : au-delà de ~200 Mo d'archives (après T2 ou T3), déplacement vers un dépôt dédié
  `courses-cyclistes-archives` (GitHub Pages propre, lu à la demande par la page). Le dépôt principal reste léger.
- Classement UCI historique : un instantané de fin de saison par année (`data/archives/<année>/ranking.json`).

### Coureurs : de la fiche saison à la fiche carrière

`rider_id` (slug du nom + date de naissance) est stable d'une saison à l'autre :

- `data/archives/carrieres/<lettre>.json` (regroupé par initiale du nom, pour limiter le nombre de fichiers) :
  par coureur, saisons courues, équipes successives (déduites des résultats), victoires et podiums par saison,
  rang UCI de fin de saison.
- Points d'attention : homonymes (la date de naissance les distingue), changement d'orthographe d'un nom entre
  saisons (rapprochement manuel listé dans un fichier d'alias, jamais deviné).

## 4. Interface : rester claire et lisible

Principe : **la saison en cours reste la porte d'entrée** ; les archives se consultent, elles ne s'imposent pas.

- **Récents, Classements** : inchangés (saison en cours uniquement).
- **Calendrier** : les chips de saison n'affichent que les 2–3 dernières saisons ; une chip « Archives ▾ » ouvre une
  liste groupée par tranche (2021–2025, 2016–2020…). Le reste de l'onglet (Résultats / À venir, filtres) est
  identique quelle que soit la saison.
- **Fiche course** : nouvel encart « Éditions précédentes » (vainqueurs et meilleur Français de chaque édition
  archivée), chargé à la demande.
- **Fiche coureur** : onglets « Saison » (actuel) et « Carrière » (tableau par saison : équipe, victoires, podiums,
  rang UCI ; palmarès complet replié par saison).
- **Français** : inchangé (saison en cours) ; plus tard éventuellement un filtre « Saison » réutilisant les archives.
- Libellés d'époque affichés tels quels (« 2.HC », « Coupe de France ») avec une info-bulle d'équivalence.
- Chargement paresseux partout : aucune archive n'est téléchargée tant qu'on ne l'ouvre pas ; la page d'accueil
  garde le même poids qu'aujourd'hui.

## 5. Déroulé et contrôle qualité par tranche

Pour chaque tranche :

1. **Collecte** : `archives.yml` lancé avec les 5 saisons, 4 à 5 passages par saison (budget 40 min).
2. **Validation automatique** (`tools/inspect_data.py --archive`) : nombre de courses par catégorie et par saison,
   classements manquants, coureurs sans date de naissance, tailles de fichiers.
3. **Contrôle par sondage** : vainqueurs des grands tours, des 5 monuments et du championnat de France de chaque
   saison comparés à une référence connue ; tout écart est documenté (jamais corrigé à la main dans les données).
4. **Compactage et publication**, puis captures Playwright de l'interface (Archives, fiche course « Éditions
   précédentes », fiche coureur « Carrière »).
5. **Bilan** : volume, durée, écarts ; décision de passer à la tranche suivante.

Estimation : étape 0 + T1 + interface ≈ 3 à 4 jours de travail ; chaque tranche suivante ≈ 1 jour (collecte
étalée sur 2–3 jours de passages automatiques).

## 6. Limites assumées

- Pas de résumés IA ni de récits pour les archives (résumés déterministes uniquement), pas de parcours ni de
  bonifications (sources ASO limitées à l'édition en cours).
- Couverture limitée aux courses suivies (règles du §3) : ce n'est pas une base exhaustive de toutes les courses UCI.
- La profondeur réelle dépend de DataRide (étape 0) ; avant les archives UCI, seul Wikipédia pourrait compléter les
  podiums des grandes courses (hors périmètre de ce plan).
