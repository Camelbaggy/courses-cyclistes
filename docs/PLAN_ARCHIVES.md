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

> **État d'avancement du §3** : FAIT (code, tests locaux ; essai réseau `[essai:archives_collecte]` à lancer) :
> sélection par époque (`1.HC`/`2.HC` -> Pro ; `1.CH`, `2.CH`, `CPE`, `AU1`, `MNM` -> WT), `collector.run_archive`
> + `compact_race` (annexes top 30, clés null supprimées), `run_pipeline.py --archive`, `archives.yml`, checkout
> partiel d'`update.yml`, classement UCI de fin de saison (`ranking.json`) et fiches coureurs par saison
> (`riders.json`), rotation calendrier -> archives (`saisons_a_archiver`, `migrer_saisons_anciennes`), dépôt dédié
> `courses-cyclistes-archives` (FAIT, voir « Seuil de bascule »). RESTE À FAIRE :
> Coupe de France historique (liste par année), `tools/inspect_data.py --archive`.
> **FAIT ensuite** : fiches carrière (`carrieres/`, `alias_coureurs.json`) et éditions précédentes (`editions.json`,
> `alias_courses.json`), avec l'interface correspondante (§4).

### Sélection par époque (`selection.py`)

| Aujourd'hui | Équivalent historique |
|---|---|
| `1.UWT` / `2.UWT` → WT | idem depuis 2011 ; `1.UWT`/`2.UWT` ou codes ProTour (`PT`) avant |
| `1.Pro` / `2.Pro` → Pro | `1.HC` / `2.HC` avant 2020 (rangées en « Pro », libellé d'origine conservé) **[fait]** |
| — | 2009-2010 : `1.CH` / `2.CH` (calendrier historique : grands tours, monuments) et classes ProTour (`CPE`, `AU1`, `MNM`) → WT **[fait]** |
| FDJ United Series | Coupe de France (liste par année : LNC si disponible, sinon Wikipédia « Coupe de France de cyclisme sur route {année} ») |
| .1 / .2, championnats | identiques |

La règle « .1/.2 étrangère avec un Français dans le top 10 » s'applique telle quelle.

### Collecte (`collector.py`, nouveau mode archive)

- `run_pipeline.py --archive 2021-2025` : collecte des saisons demandées **sans** toucher à la saison courante, sans
  notification, sans Gemini (résumés de repli déterministes), sans enrichissement ASO ni récits (les sites ne
  servent que l'édition en cours ; Cyclingnews/DirectVélo n'ont pas l'historique).
- Reprise : budget de temps par passage (déjà en place), décisions « top 10 français » mémorisées ; une saison est
  marquée « archivée » une fois complète et n'est plus jamais recollectée.
- **[fait]** Workflow `archives.yml` (`workflow_dispatch`, entrée « saisons »), séparé de `update.yml`, aujourd'hui hébergé dans le
  dépôt d'archives (groupe de concurrence `archives-data` propre à ce dépôt).

### Stockage et compactage

Aujourd'hui une saison pèse ~40 Mo (225 fichiers). Sans compactage, 20 saisons feraient ~800 Mo : trop pour un dépôt
servi par GitHub Pages et cloné à chaque passage horaire.

- **Fichiers d'archive compactés** (`<année>/races/<id>.json`, dépôt d'archives) : classement complet de chaque étape / course
  d'un jour, général complet, mais classements annexes (points, montagne, jeunes) limités au top 30 par étape
  (complets au classement final), clés courtes. Objectif ≤ 10 Mo par saison, ~50 Mo par tranche.
- **Seuil de bascule : FAIT.** Les archives T1 (2021-2025, ~120 Mo, 1040 fichiers) ont quitté le dépôt principal pour le
  dépôt dédié `Camelbaggy/courses-cyclistes-archives` (GitHub Pages propre, lu à la demande par la page, CORS ouvert),
  avant de collecter T2. `archives.yml` y vit désormais : il checkout le code du dépôt principal et écrit dans le
  `data/archives/` du dépôt d'archives (`ARCHIVES_DIR`). La rotation calendrier -> archives est scindée : la migration
  s'écrit côté archives sans rien supprimer, le dépôt principal retire ses fichiers de la saison quand l'index public des
  archives la déclare `complete` (CLAUDE.md, SPEC §4.4). **T2 (2016-2020) est en cours** via la plage par défaut
  `2016-2025` du workflow (run_archive traite de la plus récente à la plus ancienne et ignore les saisons complètes).
- Classement UCI historique : un instantané de fin de saison par année (`<année>/ranking.json` du dépôt d'archives).

### Coureurs : de la fiche saison à la fiche carrière

`rider_id` (slug du nom + date de naissance) est stable d'une saison à l'autre :

- **[fait]** `carrieres/<lettre>.json` (dépôt d'archives) (regroupé par initiale du nom, pour limiter le nombre de fichiers) :
  par coureur, saisons courues, équipes successives (déduites des résultats), victoires et podiums par saison,
  rang UCI de fin de saison.
- Points d'attention : homonymes (la date de naissance les distingue), changement d'orthographe d'un nom entre
  saisons (rapprochement manuel listé dans un fichier d'alias, jamais deviné).

## 4. Interface : rester claire et lisible

Principe : **la saison en cours reste la porte d'entrée** ; les archives se consultent, elles ne s'imposent pas.

- **Récents, Classements** : inchangés (saison en cours uniquement).
- **Calendrier** : les chips de saison n'affichent que `seasons.json.available` (rotation : une saison S en sort quand
  S+1 est terminée depuis plus de 14 jours, voir SPEC §4.4). **[fait]**
- **Onglet Archives** (5e onglet principal, à la place de la chip « Archives ▾ » initialement prévue) : menu déroulant
  des saisons (`archives/index.json`), `?archive=AAAA`, vue « Résultats » du Calendrier réutilisée (mêmes filtres de
  catégorie), « Victoires françaises », classement UCI de fin de saison (top 10), fiches course et coureur d'archive,
  chargement paresseux. **[fait]** (base des archives : `?archives=` / `?data=` / dépôt d'archives ; jeu d'essai : `tools/fixtures/data/archives/`, captures `tools/apercu.py`).
- **Fiche course** : encart « Éditions précédentes » (vainqueurs et meilleur Français de chaque édition archivée et des
  saisons du Calendrier), chargé à la demande, rapprochement exact par `cle_edition` + alias manuels. **[fait]**
- **Fiche coureur** : onglets « Saison » (actuel) et « Carrière » (tableau par saison : équipe, victoires, podiums,
  rang UCI ; palmarès complet replié par saison). **[fait]**
- **Français** : inchangé (saison en cours) ; plus tard éventuellement un filtre « Saison » réutilisant les archives.
- Libellés d'époque affichés tels quels (« 2.HC », « Coupe de France ») avec une info-bulle d'équivalence. **[fait pour
  les classes HC / CH / CPE / AU1 / MNM]**
- Chargement paresseux partout : aucune archive n'est téléchargée tant qu'on ne l'ouvre pas ; la page d'accueil
  garde le même poids qu'aujourd'hui.

## 5. Déroulé et contrôle qualité par tranche

Pour chaque tranche :

1. **Collecte** : `archives.yml` (dépôt d'archives) lancé avec les 5 saisons, 4 à 5 passages par saison (budget 40 min).
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
