# Recherche cyclisme : récits, parcours, télémétrie, fiches coureurs, météo

## Limites de cette recherche (à lire d'abord)

- WebFetch n'a pu joindre AUCUN site cible : letour.fr (refusé), procyclingstats.com, open-meteo.com, fr.wikipedia.org, wikidata.org et cyclingnews.com ne se résolvent pas dans cette session (réseau restreint). Aucune réponse d'API n'a donc été vue directement.
- Tout ce qui suit vient de WebSearch (extraits de pages). Le niveau de confiance est indiqué par piste.
  Rien n'est vérifié sur le format réel des réponses : d'où la liste de sondes en fin de document, à lancer depuis GitHub Actions.
- Aucun endpoint JSON officiel de live n'a été trouvé pour letour.fr, ASO, RCS ou Unipublic. Ne pas en supposer.

## A. Fil narratif / live texte

| Piste | URL / endpoint | Format | Langue | Anti-robot / CGU | Intérêt | Confiance |
|---|---|---|---|---|---|---|
| ProCyclingStats, page live | `https://www.procyclingstats.com/race/tour-de-france/2025/stage-17/live` (modèle `/race/<slug>/<année>/stage-<n>/live`) | HTML ; la page indique « KM to go », vitesse moyenne du jour | EN | robots.txt : `Allow: /` pour tous, Content-Signal `search=yes, ai-train=no`, crawlers IA nommés (dont ClaudeBot) bloqués. CGU (dernière MAJ 2014) interdisent les « automated scripting tool » et limitent l'usage à du personnel non commercial. Conflit, risque juridique réel. | Cadre de course (km restants, écarts) plus que du récit. À n'utiliser qu'après accord du site. | moyenne |
| Cyclingnews, live report | Anciennes pages : `/races/<course>-<année>/stage-<n>/live-report`. Nouveau schéma 2026 : `/pro-cycling/live/tour-de-france-2026-stage-12-live/` | HTML, texte chronologique rédigé (« As it happened ») | EN | Non testé. Le texte est protégé par le droit d'auteur : pas de republication, usage comme matière première pour un résumé IA = zone grise à valider. | Meilleur récit anglophone (échappée, chutes, écarts). | moyenne (URL vues dans les résultats) |
| Cyclingnews, RSS | `https://www.cyclingnews.com/rss/` (page index supposée) | RSS | EN | Non vérifié | Titres et chapôs seulement, pas le live. | faible |
| Cycling Weekly | page « RSS feeds from Cycling Weekly » : `https://cyclingweekly.com/newsfeeds/rss-feeds-from-cycling-weekly-70384` | RSS | EN | Non testé | Titres et chapôs. En 2009-2010 ils relayaient le live texte officiel du Tour, pas de preuve que cela existe encore. | faible |
| letour.fr | Pas de JSON live officiel trouvé. Des scrapers tiers (Apify) lisent des endpoints AJAX `/en/ajax/ranking/<étape>/…` avec segment haché qui change ; ils renvoient du HTML, pas du JSON. | HTML | FR/EN | robots.txt inaccessible depuis cette session. Les hash rotatifs indiquent une volonté de ne pas être scrapé. À ne pas contourner. | Classements et métadonnées d'étape (ville, distance, dénivelé, type), pas de récit. | moyenne |
| L'Équipe, DirectVélo | Aucun flux RSS confirmé. Seule une entrée « L'Équipe - actualité du sport en continu » existe dans l'annuaire feeder.co. DirectVélo a des pages catégorie (`/actualites/equipe/…`) sans RSS repéré. | HTML | FR | Non testé. Contenu payant/protégé en partie. | Comptes rendus FR, mais licence de réutilisation incertaine. | faible |
| Wikipedia (après coup) | API MediaWiki `https://fr.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=…&format=json`. L'endpoint REST `/api/rest_v1/page/summary/{titre}` ne renvoie que l'intro, pas les sections. Pour une section : `action=parse&page=…&prop=wikitext&section=N`. | JSON | FR | Libre (CC BY-SA, attribution obligatoire). Respecter l'en-tête User-Agent. | Seulement pour les grands tours et classiques majeures, délai de quelques jours, et seulement la forme finale : pas pour le « soir même ». Bon complément. | moyenne |
| Communiqués d'équipes | Non explorés | HTML | FR/EN | — | Utile pour les clubs français (Groupama-FDJ, Decathlon-CMA CGM, Cofidis, Arkéa-B&B, TotalEnergies…), mais pas de format commun. | non évalué |
| Fournisseurs de données sportives | Statscore (SportsAPI) liste le Tour dans ses compétitions cyclisme | API payante | EN | Commercial | Hors périmètre gratuit. | faible |

Constat : il n'existe pas d'équivalent gratuit, ouvert et structuré du fil ESPN en cyclisme. Le « live texte » est du contenu éditorial protégé. Les options réalistes sont (1) un fil construit à partir des classements officiels (échappée = noms des premiers aux points intermédiaires, écarts aux pointages), (2) Wikipedia pour le récit différé, (3) un accord éditorial si un média accepte.

## B. Données de parcours

| Piste | Détail | Confiance |
|---|---|---|
| PCS « All stage profiles » | `https://www.procyclingstats.com/race/dauphine/2024/route/stage-profiles` : par étape distance, `vertical meters`, `ProfileScore`, `PS final 25k`, icône de type (5 icônes : plat → montagne arrivée en côte). Exemple vu : Tour of Oman 2024 étape 2 = 2 140 m D+, ProfileScore 96. Page explicative : `/info/profile-score-explained`. | bonne sur le contenu, mêmes réserves CGU que ci-dessus |
| Bibliothèque PyPI `procyclingstats` (v0.2.8) | Classes Race, RaceStartlist, RaceClimbs, Ranking, Rider, RiderResults, Stage, Team. Scrape du HTML, fragile. Utile surtout pour connaître les sélecteurs, pas pour l'importer (dépendances, bibliothèque standard uniquement). | bonne |
| letour.fr | Pages d'étape : villes, distance, dénivelé, type. Pas de profil téléchargeable trouvé. | moyenne |
| la-flamme-rouge.eu, cyclingstage.com | Non explorés (réseau). Connus pour des profils images ; pas de données de points ouvertes. | faible |
| GPX | Aucun GPX officiel ouvert confirmé. Les organisateurs publient parfois un tracé (carte) mais pas sous licence ouverte. | faible |
| Profil dessiné côté navigateur | Faisable si on dispose de points (distance, altitude). Sans GPX, la voie ouverte est : tracé approché → altitudes via Open-Meteo Elevation (`/v1/elevation?latitude=a,b,…&longitude=…`, MNT 90 m, non commercial, attribution Copernicus + Open-Meteo) ou OpenTopoData (`https://api.opentopodata.org/v1/srtm30m?locations=lat,lon|lat,lon`, couverture ±60° de latitude). Mais sans tracé officiel, le profil serait inventé : à proscrire pour respecter la règle cardinale. | bonne pour le principe |
| Alternative sûre | Ne pas dessiner de profil. Afficher des champs textuels : distance, D+, type d'étape, cols (nom, catégorie, km) si une source les fournit, sinon champ vide. | recommandation |

## C. Données en course / télémétrie

- Rien d'ouvert trouvé. La télémétrie du Tour (GPS, vitesse, écarts) est produite par NTT Data (précédemment Dimension Data) pour ASO et diffusée via l'appli/site officiels et les diffuseurs. Aucune API publique ni documentation trouvée.
- Tissot (chronométrage) et Velon : aucune information publique sur une API ouverte trouvée.
- Statscore propose du cyclisme en API commerciale.
- Conclusion : à considérer comme inaccessible. Les seuls « écarts » exploitables sont ceux des classements officiels (arrivée, pointages intermédiaires s'ils sont publiés).

## D. Fiches coureurs

- Wikidata : propriétés confirmées par recherche : P1663 = identifiant ProCyclingStats, P11020 = identifiant UCI (P1664 = ancien cyclingdatabase, archivé ; P2096 non confirmée, ne pas l'utiliser). Nationalité (P27), date de naissance (P569), équipe (P54), photo (P18, Wikimedia Commons). Interrogeable via SPARQL `https://query.wikidata.org/sparql?query=…&format=json` (non testé). Données CC0, photos sous licences Commons variables (vérifier par image : attribution, parfois CC BY-SA).
- PCS : nationalité, date de naissance, taille, poids, spécialité (sprinteur, grimpeur…), équipe, photo. Mêmes réserves CGU. Photos : droits non libres, ne pas les republier.
- UCI : classements et fiches sur uci.org / dataride.uci.ch ; pas d'API ouverte confirmée.
- Recommandation : Wikidata pour nationalité, âge, équipe (si renseignée) et photo Commons avec licence stockée. Couverture partielle pour les coureurs peu connus. Photo absente = avatar à initiales, pas de photo substituée.

## E. Météo / vent

- Open-Meteo : sans clé, gratuit pour usage non commercial, environ 10 000 appels/jour, données sous CC BY 4.0 (attribution obligatoire). Nous n'avons pas pu l'appeler.
  - Prévision : `https://api.open-meteo.com/v1/forecast?latitude=45.5&longitude=6.5&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&timezone=Europe/Paris`
  - Historique (ERA5, depuis 1940) : `https://archive-api.open-meteo.com/v1/archive?latitude=…&longitude=…&start_date=…&end_date=…&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation&timezone=Europe/Paris`. Variables horaires de vent dans l'archive : probable, non confirmé. Noter que les noms exacts peuvent être `windspeed_10m` (ancien) ou `wind_speed_10m` (récent) : à vérifier à la sonde.
  - Les valeurs sont des réanalyses/modèles, pas des mesures de course. À libeller « météo modélisée au départ/à l'arrivée » ; ne pas parler d'un vent de face précis sans tracé.
- Interêt : bon, simple, déterministe. Nécessite des coordonnées de départ et d'arrivée (géocodage Open-Meteo : `https://geocoding-api.open-meteo.com/v1/search?name=Albertville&language=fr&count=1`, non testé).

## Recommandation priorisée

1. Base factuelle : classements et métadonnées d'étape de la source qui sera retenue pour le « classement brut » (hors périmètre ici). Construire un dossier factuel déterministe : résultat, top 10, coureurs français, abandons si présents dans la source, écarts.
2. Météo : Open-Meteo (forecast + archive) pour départ et arrivée. Faible risque, gratuit, attribution à afficher.
3. Fiches coureurs : Wikidata (SPARQL) avec cache dans le dépôt ; photos Commons avec licence. Pas de photos PCS.
4. Parcours : ne retenir que des chiffres publiés par une source (distance, D+, type, cols). Pas de profil reconstruit. Si on tient au dessin, le faire uniquement à partir d'un tracé officiel obtenu avec autorisation.
5. Récit : Wikipedia (différé) pour les grandes courses ; pour le reste, résumés fondés sur le seul dossier factuel (comme le repli déterministe actuel). Demander une autorisation écrite à Cyclingnews/PCS avant tout usage de leur texte ou de leurs pages live.
6. Télémétrie : abandonner.

Point de vigilance : l'interdiction PCS (CGU « automated scripting » + crawlers IA bloqués) est incompatible avec « respect des CGU » sans accord. Idem pour Cyclingnews et L'Équipe par défaut.

## Sondes à lancer depuis GitHub Actions (workflow temporaire sur branche ccr-*)

Pour chaque URL : relever code HTTP, Content-Type, 500 premiers octets, et vérifier le robots.txt avant.

1. `https://www.letour.fr/robots.txt` puis `https://www.letour.fr/fr/` (repérer les `<link rel=alternate>`, appels XHR dans le HTML/JS).
2. `https://www.procyclingstats.com/robots.txt` et `https://www.procyclingstats.com/race/dauphine/2024/route/stage-profiles` (seulement si l'accord est obtenu ; sinon se limiter au robots.txt).
3. `https://www.cyclingnews.com/robots.txt`, `https://www.cyclingnews.com/rss/`, `https://www.cyclingnews.com/pro-cycling/live/tour-de-france-2026-stage-12-live/`
4. `https://www.directvelo.com/robots.txt` et la page d'accueil (chercher `rss`), `https://www.lequipe.fr/rss/` (annuaire de flux L'Équipe, hypothèse).
5. Wikipedia : `https://fr.wikipedia.org/w/api.php?action=parse&page=Tour_de_France_2025&prop=sections&format=json` puis `…&prop=wikitext&section=<n>&format=json` ; `https://fr.wikipedia.org/api/rest_v1/page/summary/Tour_de_France_2025`
6. Wikidata : `https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Paul+Seixas&language=fr&format=json` ; SPARQL `https://query.wikidata.org/sparql?format=json&query=SELECT%20%3Fp%20WHERE%20%7B%3Fp%20wdt%3AP1663%20%3Fid%7D%20LIMIT%203`
7. Open-Meteo : `https://api.open-meteo.com/v1/forecast?latitude=45.5&longitude=6.5&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m&forecast_days=1&timezone=Europe/Paris` ; `https://archive-api.open-meteo.com/v1/archive?latitude=45.5&longitude=6.5&start_date=2025-07-10&end_date=2025-07-10&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation&timezone=Europe/Paris` ; `https://geocoding-api.open-meteo.com/v1/search?name=Albertville&language=fr&count=1` ; `https://api.open-meteo.com/v1/elevation?latitude=45.5&longitude=6.5`
8. `https://api.opentopodata.org/v1/srtm30m?locations=45.5,6.5` (alternative altitude).
9. Wikimedia Commons (licence photo) : `https://commons.wikimedia.org/w/api.php?action=query&titles=File:<nom>&prop=imageinfo&iiprop=extmetadata|url&format=json`

Remarque réseau : les hôtes ci-dessus (sauf éventuellement ceux déjà autorisés) doivent être permis dans l'environnement pour les tests locaux ; sur GitHub Actions ce n'est pas un problème.
