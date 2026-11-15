# Structure des pages Liquipedia (modèle de l'encyclopédie)

Date : 15 novembre 2026. Source : API MediaWiki publique de Liquipedia (`/counterstrike/api.php`, `action=parse` et
`action=query&prop=revisions`), User-Agent identifié, au plus une requête toutes les 3 s (30 s pour `parse`), comme le
demandent leurs conditions d'accès. Les pages web elles-mêmes refusent les robots (page « Rate Limited » Cloudflare) :
ne pas les aspirer, ne pas contourner. Seule la **structure** est étudiée ; aucun contenu n'est repris.

Pages : [Main Page](https://liquipedia.net/counterstrike/Main_Page), [Team Vitality](https://liquipedia.net/counterstrike/Team_Vitality)
(wikitext seulement), [ZywOo](https://liquipedia.net/counterstrike/ZywOo), [StarLadder 2025 Major](https://liquipedia.net/counterstrike/StarLadder/2025/Major),
[Valve Regional Standings](https://liquipedia.net/counterstrike/Valve_Regional_Standings).

## Joueur (ZywOo)

- Onglets de sous-pages : Overview · Results (liste complète des résultats).
- Navbox de l'équipe actuelle (effectif, staff, liens équipe) en tête.
- Infobox : nom, nationalité, naissance (+ âge), statut, années d'activité, rôle, équipe, autres pseudos, gains totaux ;
  bloc **History** : « début — fin | équipe », dates à précision variable (`2014-??-??`, `… — Present`).
- Intro courte rédigée, puis : équipement, **Achievements** (tableau triable généré : date, place colorée, tier, type,
  tournoi, équipe, résultat de finale, gains ; lien vers la liste complète), Trivia (récompenses, records, en prose
  sourcée), médias (vidéos, interviews par année), galerie, références.

## Équipe (Team Vitality, wikitext)

- Onglets (équipe / académie), infobox (nom, logos clair/sombre, lieu, région, fondateurs, dirigeants, entraîneurs,
  date de création, liens).
- Sections : **Timeline** (onglets par année, faits datés et sourcés, rédigés), **Player Roster** (Active / Former :
  une ligne par personne avec drapeau, rôle, date d'arrivée, date de départ, nouvelle équipe ; remplaçants par tournoi),
  Organization (staff), **Results** (Achievements et matchs récents, générés), Trivia, interviews, galerie, références,
  navbox d'effectif.

## Tournoi (StarLadder 2025 Major)

- Navbox de la série (à venir / en cours / récents, éditions passées par année) en tête et navbox de l'organisateur en pied.
- Onglets par phase (Overview, Stage 1-3, Playoffs).
- Infobox : organisateur, type, lieu, dates, dotation, nombre d'équipes, niveau (tier), **Chronology** (édition
  précédente ↔ suivante).
- Sections : format (prose), dotation (tableau place → équipe → montant, généré), **Participants** (cartes d'équipe
  avec effectif, source de qualification), **Results** (tableaux de groupes, tableau suisse, bracket avec détail des
  matchs, générés), contenus externes, **Country Representation** (pays, nombre de joueurs, écart avec l'édition
  précédente).

## Classement (Valve Regional Standings)

- Navbox **historique** : instantanés hebdomadaires datés, groupés par année et mois (chaque date = état du classement).
- Prose courte (méthode, statut), onglets de filtre (global / régions), « dernière mise à jour ».
- Tableau : rang, points, équipe, région, effectif (liens joueurs). Entièrement généré.

## Accueil (Main Page)

Entièrement généré (module Lua), en panneaux : compteurs (joueurs, équipes, transferts, tournois) ; tournoi mis en
avant ; top 5 du classement ; transferts récents (date, joueur, ancienne → nouvelle équipe) ; « This day » (tournois
gagnés ce jour-là les années passées, anniversaires) ; matchs à venir / terminés ; tournois à venir / en cours /
terminés avec badge de niveau et filtres ; appel à contribution.

## Motifs communs

- Infobox à droite + onglets de sous-pages + sections stables par type d'entité + navbox de série ou d'équipe.
- Prose rare et localisée (intro, format, chronologie, anecdotes) ; tout le reste (résultats, palmarès, classements,
  effectifs, dotations) est **généré depuis une base** (LPDB) et les liens entre entités ne se saisissent qu'une fois.
- Historiques : chronologie précédent / suivant dans l'infobox, navbox des éditions, instantanés datés du classement.
- Dates à précision variable acceptées partout.
