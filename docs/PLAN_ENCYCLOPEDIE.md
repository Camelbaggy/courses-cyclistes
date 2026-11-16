# Plan : encyclopédie du cyclisme sur route (modèle Liquipedia)

Objectif : faire du dashboard une encyclopédie du cyclisme sur route hommes élite, sur le modèle de Liquipedia
(structure étudiée dans `docs/recherche/liquipedia_structure.md`) : une page par coureur, équipe, course, édition,
saison, classement et pays, reliées entre elles, avec un portail d'accueil et une recherche globale. Le dashboard
actuel (résultats du jour, notifications) reste la partie « actualité » du site.

## 0. Principes

- **Zéro hallucination, comme partout dans le projet.** Liquipedia mélange données de base (LPDB) et prose rédigée
  par des contributeurs. Ici, toute page est **générée** à partir des sources (UCI DataRide, archives, plus d'éventuelles
  sources libres validées au §5). Un fait absent n'apparaît pas ; aucune donnée n'est saisie ou corrigée à la main en
  dehors des fichiers d'alias (rapprochements d'identité), qui sont documentés.
- **Rapprochements stricts** : une même personne, équipe ou course n'est reliée entre saisons que par une clé exacte
  (identifiant source ou alias manuel), jamais par ressemblance de nom.
- **Précision honnête** : quand une date n'est connue qu'à la saison près (ex. un changement d'équipe), la page
  l'écrit ainsi (« 2023 → 2024 »), comme Liquipedia accepte `2014-??-??`.
- Mobile d'abord (390 px), thème sombre, même page `index.html` sans dépendance ni étape de build (§8).

## 1. Correspondance Liquipedia → cyclisme

| Liquipedia | Encyclopédie cycliste | Données disponibles aujourd'hui |
|---|---|---|
| Joueur | **Coureur** | identité, nationalité, naissance, équipe par saison, résultats, stats, rang UCI de fin de saison (2019→, puis 2011→) |
| Équipe | **Équipe** | libellé seulement, qui change avec les sponsors : il faut des **lignées** (§2) |
| Série de tournois | **Course** (toutes ses éditions) | `editions.json` : 471 courses, 186 avec ≥ 3 éditions |
| Tournoi | **Édition** | fiche course actuelle (étapes, classements, coureurs) |
| — | **Saison** | index de saison (courses, victoires françaises) |
| Classement VRS | **Classement UCI** | instantané de fin de saison ; historique hebdomadaire disponible chez l'UCI (`GetRankingMoments`), pas encore collecté |
| Représentation par pays | **Pays** | code ISO3 + drapeau sur coureurs et courses |
| Accueil | **Portail** | Récents, calendrier, classement, victoires françaises |

## 2. Identités (le cœur du chantier)

- **Coureur** : `rider_id` actuel (nom + date de naissance). Risque connu : une même personne peut avoir deux
  `rider_id` si l'UCI change l'orthographe ou la date (cas repéré sur un coureur à vérifier). Le classement UCI fournit un
  identifiant stable (`UciId`, déjà conservé dans `ranking.json`) : il servira à fusionner les doublons quand il est
  présent ; sinon `alias_coureurs.json`. Un audit des doublons fait partie de l'étape E0.
- **Équipe** : les résultats ne donnent qu'un libellé (755 libellés depuis 2019) ; une même équipe change de nom
  (ex. Deceuninck - Quick-Step → Quick-Step Alpha Vinyl → Soudal Quick-Step). Trois pistes, à sonder en E0 :
  `TeamCode` du classement UCI (ignoré aujourd'hui, peut changer avec la licence), classements par équipes UCI, et
  Wikidata (lignées « remplace / remplacé par », domaine public). À défaut : `alias_equipes.json` manuel
  (libellé → lignée). Une **équipe-saison** (libellé, saison) est toujours sûre ; la **lignée** n'est affichée que si
  elle est établie. Les sélections nationales (« France ») ne sont pas des équipes de marque : pages à part ou exclues.
- **Course** : `cle_edition` + `alias_courses.json` (déjà en place). **Édition** : `race_id` UCI.

## 3. Pages

Disposition commune : bandeau titre + onglets de sous-pages ; infobox en tête sur mobile, à droite sur grand écran ;
sections fixes par type ; liens partout (coureur, équipe, course, pays) ; navigation « édition précédente / suivante ».

- **Coureur** — infobox : nom, drapeau, naissance et âge, équipe actuelle, présent dans nos données depuis, rang UCI,
  victoires ; **parcours en équipes** (équipe par saison, à la saison près) ; **palmarès** (victoires, podiums, par
  catégorie de course) ; **grands tours** (place au général par édition) ; **résultats par saison** (onglets par
  année, tableau triable) ; **classement UCI** (rang de fin de saison par année) ; liens externes si validés (§5).
- **Équipe** — infobox : nom actuel, noms précédents (si lignée établie), pays et catégorie si une source les donne ;
  **effectif par saison** (coureurs, jours de course) ; **arrivées / départs** constatés entre deux saisons ;
  **palmarès** par saison ; meilleurs résultats en grands tours ; coureurs français.
- **Course** (série) — infobox : pays, classe actuelle et classes passées, type, éditions présentes ; **palmarès**
  (édition → vainqueur, 2e, 3e, meilleur Français) ; **records** (plus de victoires, par pays, par équipe) ; navbox des
  éditions.
- **Édition** — la fiche course actuelle, plus : chronologie précédente / suivante, **participants par équipe** (cartes
  d'effectif avec dossard et résultat, comme les cartes de Liquipedia), podium en tête, représentation par pays.
- **Saison** — calendrier par mois et catégorie, vainqueurs, statistiques (victoires par pays et par équipe,
  coureurs les plus victorieux), victoires françaises, classement UCI final.
- **Classement UCI** — tableau du classement à une date, filtres (pays, équipe), **historique** par instantanés
  (à collecter : fin de mois ou hebdomadaire, à décider), évolution d'un coureur.
- **Pays** — coureurs, victoires par saison, courses organisées, meilleur coureur par saison.
- **Portail (accueil)** — compteurs (coureurs, équipes, courses, éditions) ; courses en cours / à venir / terminées
  (l'actuel « Récents ») ; top 5 UCI ; changements d'équipe récents ; « ce jour-là » (victoires du même jour les années
  passées, anniversaires de coureurs) ; recherche globale.

## 4. Données

- Fichiers d'entités **générés chaque nuit dans le dépôt d'archives** par le workflow existant (qui lit déjà le
  `data/` du dépôt principal) : ils couvrent toutes les saisons, y compris celles du Calendrier, à un jour près ; les
  pages d'actualité restent en temps réel.
- Arborescence prévue : `entites/coureurs/<lettre>.json` (extension de `carrieres/`), `entites/equipes/<id>.json`
  + index, `entites/courses/<clé>.json` (extension d'`editions.json`), `entites/saisons/<année>.json`,
  `entites/pays/<iso>.json`, `entites/recherche/<lettre>.json` (nom → type, id). Chargement à la demande, fichier par
  entité ou par initiale pour garder chaque page légère.
- Estimation à mesurer en E1 : quelques dizaines de Mo de plus dans le dépôt d'archives (bien sous la limite Pages).

## 5. Sources complémentaires (à sonder, à valider)

- **UCI DataRide** : `TeamCode` et classements par équipes (lignées), historique des moments du classement.
- **Wikidata** (domaine public, CC0) : lignées d'équipes, lieu de naissance, liens Wikipédia, photo Commons. Rapprochement
  strict (nom + date de naissance, ou identifiant UCI si Wikidata le porte).
- **Wikipédia FR** (CC BY-SA) : extrait d'introduction des articles coureur / équipe / course, crédité et lié.
- **Wikimedia Commons** : photos sous licence libre, avec auteur et licence affichés.
- Exclus : ProCyclingStats, FirstCycling (conditions d'utilisation), pages web de Liquipedia (refus des robots ; seule
  la structure a été étudiée via l'API).

## 6. Interface

- Routes : `#coureur/<id>`, `#equipe/<id>`, `#course/<clé>`, `#edition/<race_id>` (l'actuel `#course/<id>` reste
  accepté), `#saison/<année>`, `#classement/uci/<date>`, `#pays/<iso>`, `#recherche/<texte>`.
- En-tête : recherche globale toujours visible ; onglets principaux revus (Accueil · Courses · Coureurs · Équipes ·
  Classements · Archives, à trancher).
- Composants communs : infobox, onglets de sous-pages, tableau triable, navbox repliable, carte d'équipe, badge de
  catégorie (WT, Pro, .1, .2, anciennes classes avec équivalence).

## 7. Étapes

| Étape | Contenu | Livrable |
|---|---|---|
| E0 (fait) | Sondes : `TeamCode` sur plusieurs saisons, classements par équipes UCI, couverture Wikidata (coureurs, équipes), audit des doublons de coureurs ; décisions du §8 | `docs/recherche/encyclopedie_sources.md` |
| E1a (fait) | Socle de données sans réseau : `encyclopedie.py` génère `entites/` (coureurs, équipes-saisons, courses, saisons, pays, recherche, index) à partir des archives + Calendrier, alias coureurs / courses appliqués | fichiers `entites/` (schéma : SPEC §4.5), tests, mesures |
| E1b (fait côté code, non testé en réel) | `TeamCode` conservé dans `ranking.json` (relecture unique des saisons archivées), `code_uci` des équipes-saisons ; `wikidata.py` : QID des coureurs (nom + date de naissance exacte + occupation cycliste), images Commons sous licence, lignées d'équipes (code + période + nom), `alias_equipes.json` ; cache `entites/wikidata/`, workflow dédié `--wikidata` | lignées, correspondances (à mesurer au premier remplissage : taux de rapprochement coureurs / équipes) |
| E1c (fait côté code pour l'historique, non testé en réel ; audit des doublons restant) | Historique du classement UCI : `uci_ranking.list_moments` / `get_ranking_moment` / `choisir_instantanes`, `collector.collecter_classements` (appelé par `run_archive`), champs `historique_uci` (coureur) et `instantanes_uci` (saison) | `entites/classements/<année>/…` (SPEC §4.5), essai `[essai:classement_historique]` |
| Historique (fait côté code ; mesures réelles : docs/recherche/historique_avant_2009.md §10) | Palmarès (vainqueur + podium) de toute l'histoire des épreuves suivies depuis Wikidata : `series_historiques.json` (séries prouvées par concordance des vainqueurs 2019-2025), `historique.py` (cache `entites/historique/`, `run_pipeline.py --historique`), `encyclopedie.construire` fusionne les années absentes de nos éditions UCI (`historique`, `records_historique`, coureurs historiques `wd-Q…`, `palmares_historique`) | cache, entités, sondages vérifiés |
| E2 (fait) | Pages coureur + recherche globale + première couche du design (jetons, composants : voir CLAUDE.md « Design et composants ») | captures 390 px et 1024 px (`tools/apercu.py`) |
| E3 (fait) | Page épreuve (`#epreuve/<clé>` : palmarès, records, historique) et fiche d'édition enrichie (podium, navigation, participants, pays) | captures 390 px et 1024 px (`tools/apercu.py`) |
| R1 (fait) | Refonte « encyclopédie » : coquille (menu, barre du bas), routeur à pages plein écran, gabarit d'article, accueil portail, Courses (toutes saisons, épreuves), liste des équipes-saisons, annuaire des coureurs, Classements (UCI, saisons, instantanés) | captures `tools/apercu.py` (fictif et réel) |
| R2 | Articles équipe (lignées) : les noms d'équipe deviennent des liens | captures |
| R3 | Articles saison, navbox de série et de classement, pays | captures |
| E7 | Enrichissements externes validés (Wikidata, Wikipédia, photos) | captures, crédits |

### Historique du classement UCI : estimations (E1c)

Hypothèses : classement complet de ~3 400 lignes pour un World Ranking moderne (4 pages de 1 000), ~250 pour un « WorldTour Ranking » ancien (1 page) ;
~35 courses WorldTour par saison moderne, dont plusieurs se terminent la même semaine ; 12 fins de mois ; pause DataRide de 2 s.

| | Saison moderne (World Ranking) | Saison ancienne (WorldTour Ranking) |
|---|---|---|
| Instantanés (fins de mois + après chaque course WT, dédoublonnés) | ~30-35 | ~25 |
| Requêtes | 3 de cadrage (saison, classements, moments) + 4 par instantané, soit ~130-145 | 3 + 1 par instantané, soit ~30 |
| Durée à 2 s / requête | ~4-5 min | ~1 min |
| Lignes gardées par instantané | ~600 (500 + ~100 Français au-delà) | ~250 |
| Taille d'un instantané compact (~48 octets / ligne) | ~29 Ko | ~12 Ko |
| Taille par saison | ~1 Mo | ~0,3 Mo |

Premier remplissage 2011-2027 (≈ 10 saisons modernes à confirmer : le World Ranking existe depuis 2016 environ, les saisons antérieures utilisent le
WorldTour Ranking) : ~1 600 requêtes, ~55 min de DataRide, ~12 Mo ; réparti sur 2 passages nocturnes de 50 min en tenant compte des courses. Régime
établi : ~3 requêtes de cadrage + 4 par nouvel instantané par saison en cours (deux saisons du Calendrier), soit ~15 requêtes par nuit, quelques centaines d'octets
à 30 Ko écrits. `historique_uci` ajoute ~20 octets par point (≈ 180 000 points sur toutes les saisons) : ~+3 à 4 Mo dans `coureurs/*.json` (10,6 Mo aujourd'hui) et ~25 Mo
de mémoire transitoire dans `encyclopedie.construire`. Les estimations sont à confronter à la mesure du premier passage réel (journal `[CLASSEMENT]`).

Chaque étape : PR vérifiée (tests, captures), fusionnée, puis bilan.

## 8. Décisions (15 novembre 2026)

1. **Périmètre** : tout le peloton (une fiche par coureur et par équipe présents dans nos courses) ; les Français restent
   mis en avant sur l'accueil.
2. **Texte** : **Wikipédia en source principale**, en consultant plusieurs langues (fr, en, es, it, nl, be… : la page
   espagnole de Movistar ou néerlandaise d'une équipe belge peut être la plus complète) ; Gemini seulement en dernier
   recours, à partir des faits, avec contrôle des chiffres et en ménageant le quota gratuit. **Rester synthétique** :
   quelques phrases par page, jamais de longs pavés ; le texte complète les tableaux, il ne les remplace pas. Source et
   licence (CC BY-SA) affichées et liées.
3. **Wikidata et Wikimedia Commons** : oui (sonde d'abord en E0, rapprochements stricts).
4. **Livraison** : dans la page actuelle (`index.html`, nouvelles routes, sans build).
5. **Historique du classement UCI** : un instantané en **fin de mois** et **après chaque course WorldTour** (après la
   dernière étape pour une course par étapes), en tenant compte du délai de publication de l'UCI (mesuré en E0).
6. **Design** : plus moderne que Liquipedia (pas de copie de son apparence), très lisible sur mobile (390 px d'abord),
   thème sombre soigné ; hiérarchie visuelle nette, tableaux compacts et défilables, infobox en cartes, typographie
   et espacements généreux, peu de texte.

## 9. Limites assumées

- Pas de gains ni de dotations (non publiés par la source), pas de dates exactes de transfert (saison près), pas de
  biographie sans source, catégorie d'équipe seulement si une source la donne.
- Profondeur : saisons collectées dans les archives (2011 → aujourd'hui, 2009-2010 éventuellement), courses suivies
  selon les règles de sélection (pas toutes les courses UCI).
