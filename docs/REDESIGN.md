# Refonte du site : point de départ

Préparé le 17 novembre 2026 pour démarrer le projet de refonte (redesign) dans une conversation neuve. À lire avec
`CLAUDE.md` (section « Interface »), `docs/AVANCEMENT.md` et `docs/SPEC.md` (schémas des fichiers lus par la page).
Les objectifs de la refonte restent à fixer avec le propriétaire (questions en fin de document).

## État actuel de l'interface (référence « avant »)

- Un seul fichier `index.html` (3 532 lignes, ~257 Ko) : CSS inline (l. 9-615), JS inline (l. 631-3530), sans dépendance ni build.
  Thème sombre unique, jetons CSS sur `:root` (surfaces `--bg/--s1/--s2/--s3`, texte `--tx/--tx2/--tx3`, `--accent`, catégories
  `--c-wt`…, maillots `--jaune`…, espacements `--sp1..6`, rayons `--r1/--r2`, ombres, `--bar-h`, `--bnav-h`) ; anciens noms gardés en alias.
  Points de rupture : 880 px (menu horizontal, infobox à droite, deux colonnes), 400 px.
- Routeur à hash (`parseRoute` / `routeur` / `PAGES`, l. ~2958) : accueil, courses (+ épreuves), epreuve, course (édition / étape),
  equipes, equipe (lignée ou équipe-saison), coureurs, coureur (+ `wd-Q…` historique), classements, recherche, introuvable.
  Liste complète des routes et paramètres : `CLAUDE.md`, « Routeur ».
- Composants : `htmlArticle` (fil d'Ariane, infobox, colonne principale, navbox), `htmlInfobox`, `htmlTuiles`, `htmlOnglets`,
  `htmlTableau`, `htmlParticipants` (cartes d'équipe repliables), `htmlParcours`, `sparkRang`, squelettes `.sk`, `htmlVide`, `catBadge`,
  maillots (`maillotPourEquipe`, `maillotNation`, `maillotsCourse`, `renderMaillots`).
- Captures de référence : `python tools/apercu.py <dossier>` (jeu fictif, 72 captures 390 px `-m` et 1024 px `-d`, + contrôles
  automatiques). Passage du 17/11 : tout OK, aucune erreur console, aucun débordement. Le refaire en début de projet pour garder
  les images « avant » (le dossier de captures n'est pas versionné). Vraies données : `--reel <dossier servi>`.

## Contrats à ne pas casser

- **URL** : les liens ntfy (`#course/<race_id>[/<étape|F>]`) et les anciennes URL (`?archive=`, `?saison=` -> `redirigerAncienneUrl`)
  doivent continuer de marcher ; toute route existante doit rester valide (ou être redirigée).
- **Sécurité** : toute donnée insérée dans le HTML passe par `esc()`.
- **Fonctions miroirs du Python** (à garder alignées, testées par `tools/apercu.py`) : `cleEdition` = `collector.cle_edition`,
  `categorieClasse` = `selection.categorie_classe`, `normIdx` = `netutil.normalize`, `slugEquipe` = `netutil.slugify`.
- **Données lues** (aucune ne change avec une refonte purement visuelle) : `data/` (`seasons.json`, `index[-<année>].json`,
  `races/<id>.json`, `riders-<année>.json`, `ranking.json`) ; archives (`BASE_ARCHIVES`, Pages du dépôt d'archives : `<année>/…`,
  `editions.json`, `carrieres/`, `entites/…` dont `recherche/<lettre>.json`, `classements/`, `coureurs_historiques/`) ; maillots
  (`maillots/index.json`, `maillots/pcmmod/…`). Paramètres de test : `?data=`, `?archives=`, `?maillots=`.
- **Crédits obligatoires** : « WorldDB » et « PCM Mod » (maillots ; images PCM chargées depuis pcmmod.com, accord des administrateurs),
  auteur + licence Commons pour chaque photo / logo, Wikipédia CC BY-SA pour le calendrier à venir.
- **Règles produit** : zéro valeur inventée (un champ absent n'affiche rien, pas de ligne vide) ; mobile ~390 px d'abord puis 1024 px ;
  simplicité voulue par le propriétaire (pas de lignes redondantes, pas de liens en double, listes simples) ; tout en français.
- Drapeaux flagcdn.com (`flag()`), pas d'autre dépendance externe sans accord.

## Outils et méthode

- Jeu fictif : `tools/fixtures/data/` (+ `archives/`, produit par `tools/fixtures/generer_archives.py`) et `tools/fixtures/maillots/`.
- Contrôles : `tools/apercu.py` (captures, erreurs console, débordements, retour arrière, barre du bas, cas de maillots, slugs) ;
  ajouter les nouveaux contrôles au même script. `python -m py_compile *.py tools/*/*.py` si du Python change.
- Travail sur la branche `ccr-*`, PR puis fusion par Claude après vérification (règle du projet) ; GitHub Pages publie `main` directement.
- Agents Sonnet pour l'écriture de code et les contrôles, conception et vérification finale gardées (CLAUDE.md).
- Piste : refonte par étapes (jetons et coquille, puis composants, puis pages une à une), chaque étape publiable seule,
  captures avant / après à 390 et 1024 px.

## Décisions du propriétaire (17/11/2026)

1. Objectif : **style visuel ET navigation** (réorganisation des pages et menus là où c'est utile ; toute route existante reste
   valide ou est redirigée).
2. Thème : **sombre + clair**, choisi selon la préférence du système, avec un bouton pour forcer l'un ou l'autre.
3. Référence : **Liquipedia modernisé** (infobox, navbox, tableaux denses, avec une finition plus soignée).
4. Pages prioritaires : accueil, fiche de course, fiche coureur, articles d'équipe et pages d'épreuve (toutes).
5. Non tranché, par défaut : page unique `index.html` sans build (pas de découpage en fichiers).

## Étapes (chacune publiable seule, captures avant / après 390 et 1024 px, `tools/apercu.py` tout OK)

1. **Jetons et thème clair** (faite, PR #55) : thème clair complet, bouton auto / clair / sombre, passe claire et contrôle des contrastes dans
   `tools/apercu.py`.
2. **Composants Liquipedia modernisés** (faite, PR #56 : infobox en lignes + bandeaux, wikitable zébré `--zebra` / `--hover`, onglets, tuiles compactes, navbox en grille, `o.bandeau` optionnel, touches d'accent) : typographie (échelle, chiffres tabulaires), infobox à bandeau de titre et lignes
   libellé / valeur, tableaux « wikitable » denses, onglets, tuiles plus compactes, navbox ; mêmes fonctions JS
   (`htmlInfobox`, `htmlTableau`, `htmlOnglets`, `htmlTuiles`, `htmlNavbox`), pages inchangées sur le fond.
3. **Navigation** (faite, PR #57 : recherche inline `#hsearch` + raccourci « / » dès 880 px, bouton retour mobile `#back-btn`, `htmlSousNav` / `.secnav` pour Courses, Classements et Coureurs, `#to-top`, pied de page soigné) : en-tête et menus, fil d'Ariane, accès direct à la saison courante, liens entre pages ; routes inchangées.
4. **Pages une à une** : accueil (4a, faite, PR #58 : bandeau « À la une », prochaine course, cartes à filet de catégorie, résumés repliés, maillots + crédit, tuiles de compteurs) ; fiche de course /
   étape (4b, fiche de course faite : bandeau coloré, infobox sans redondance et après le contenu sur mobile, podium 2-1-3 avec maillots, puces d'étapes, carte d'étape, crédit unique) ; à venir : fiche coureur, article d'équipe, page d'épreuve.

## Questions posées au démarrage (tranchées ci-dessus)

1. Objectif : nouveau style visuel seulement, ou aussi navigation / organisation des pages ?
2. Thème : rester sombre seul, ou ajouter un thème clair (et suivre la préférence système) ?
3. Références visuelles souhaitées (Liquipedia reste-t-il le modèle ? autres sites à imiter ?).
4. Pages prioritaires (accueil, fiche de course, fiche coureur…).
5. Garder la page unique sans build, ou accepter un découpage en fichiers (CSS / JS séparés, toujours sans dépendance) ?

## Travaux en cours à ne pas oublier pendant la refonte

- Collecte des archives 2015-2011 (automatique, jour et nuit pendant l'intersaison) ; bilan quotidien programmé à 11 h 20 UTC
  (prochain le 18/11 : contrôles des vainqueurs, lignées manquantes dont Cofidis 2022-2024) ; voir `docs/AVANCEMENT.md`.
- Reprise des courses mi-janvier 2027 (Tour Down Under le 19/01) : `update.yml` doit tourner normalement d'ici là.
