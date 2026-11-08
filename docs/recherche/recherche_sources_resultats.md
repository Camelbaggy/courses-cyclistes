# Sources de données de résultats : cyclisme sur route masculin

Date : 2026-11-08. Recherche documentaire uniquement (aucun code écrit dans le dépôt).

## 0. Limites de cette recherche (à lire d'abord)

Le conteneur de recherche n'a pas pu joindre procyclingstats.com, firstcycling.com, wikipedia.org, apify.com,
readthedocs.io ni dataride.uci.org (hôtes hors de la liste réseau autorisée). letour.fr est refusé par WebFetch.
Seul github.com était joignable. Les robots.txt de PCS, FirstCycling, ASO n'ont donc PAS pu être lus ; on s'appuie
sur des extraits de moteur de recherche, des descriptions de scrapers tiers et le code source d'un paquet GitHub.
Tout ce qui est marqué NON VÉRIFIÉ doit être validé par les sondes du §7 depuis GitHub Actions.
Aucun endpoint ci-dessous n'a été appelé réellement.

## 1. ProCyclingStats (PCS)

- Format : HTML uniquement, pas d'API. Pages : /race/{slug}/{année}/stage-N, /race/{slug}/{année}/gc,
  /race/{slug}/{année}/startlist, /race/{slug}/{année}/result (courses d'un jour), /rankings/..., /team/..., /rider/...
- Couverture : la plus complète (WorldTour, ProSeries, .1, .2, Coupe de France). Dossards, équipes, nationalités,
  DNF/DNS, classements annexes, bonifications, écarts, points UCI. Pas de temps aux pointages intermédiaires fiables.
- Paquet open source `themm1/procyclingstats` (MIT) : classes Race, RaceStartlist, RaceClimbs, Ranking, Rider,
  RiderResults, Stage, Team. Utile comme référence de la structure des pages (la lecture du code montre un parseur
  HTML fragile : 4 issues ouvertes, toutes sur des désalignements de tableaux d'étape #79 à #82).
- Anti-robot : le paquet détecte « Just a moment » / HTTP 403 (Cloudflare) et recommande `cloudscraper`
  (imitation de navigateur) : c'est précisément le contournement interdit ici. Un scraper Apify indique que PCS
  bloque les IP de datacenter (GitHub Actions en est une) : vraisemblable, NON VÉRIFIÉ depuis Actions.
- robots.txt (via extrait de recherche) : règle générale « allow » avec content-signal Cloudflare
  `search=yes, ai-train=no`, mais blocage total de nombreux bots nommés, dont ClaudeBot, anthropic-ai,
  Claude-User, Claude-Web.
- CGU (« General terms and conditions », datées du 20 juin 2014) : l'item (f) interdit l'usage du site avec
  des outils de script automatisés ; interdit aussi de surcharger le site ou de le mettre en miroir.
- Verdict : EXCLU comme source automatique. CGU contraires + Cloudflare + IP datacenter. Ne pas l'utiliser en
  production, même poliment. (Consultation manuelle humaine pour recoupement : sans problème.)

## 2. FirstCycling

- Pas d'API officielle trouvée. Le paquet communautaire `baronet2/FirstCyclingAPI` (« unofficial Python API
  wrapper », dernier push ~2023) et le serveur MCP `r-huijts/firstcycling-mcp` scrapent le HTML (BeautifulSoup/lxml)
  : résultats de course, startlist, profils d'étape, palmarès, recherche coureur/course.
- CGU et robots.txt : NON LUS (hôte inaccessible ici), aucun texte trouvé via recherche. À lire avant tout usage.
- Cloudflare : aucune mention trouvée ; NON VÉRIFIÉ.
- Verdict : source de repli potentielle uniquement si robots.txt/CGU l'autorisent et si une sonde depuis Actions
  retourne 200 sans challenge. Le site couvre bien .1/.2 et la Coupe de France.

## 3. UCI (uci.org, DataRide)

- DataRide (dataride.uci.org, ex-« UCI Data Ride ») est le portail officiel de classements/résultats/calendrier,
  adossé à une API interne « BWS » (identifiant UCI de coureur = entier long, document Swagger mentionné en 2022
  par une note de réunion W3C OpenTrack, information de seconde main).
- Aucune documentation d'API publique trouvée ; aucun endpoint public confirmé ; aucun dépôt GitHub qui l'utilise
  retrouvé. Utiliser des appels internes non documentés = risque CGU et fragilité.
- Intérêt : calendrier officiel avec classes (2.UWT, 1.Pro, 2.1...), classements UCI (hebdomadaires, mardi),
  équipes et licences. Pas de résultats d'étape détaillés garantis.
- Verdict : source de RÉFÉRENCE pour le calendrier/classes si un export public existe ; sinon demande formelle
  à l'UCI. NON VÉRIFIÉ : tester dataride.uci.org depuis Actions (§7) et lire ses CGU et robots.txt.

## 4. Organisateurs et sites officiels

- ASO (letour.fr, paris-roubaix.fr, etc.) : pas d'API documentée. Un scraper Apify et le dépôt
  `thomascamminady/LeTourDataSet` (CSV MIT du TdF, colonnes TotalSeconds, GapSeconds, bonification B, pénalité P,
  ResultType) montrent que letour.fr sert les classements via des fragments AJAX (chemin cité :
  `/en/ajax/ranking/...` avec un « subtab » : etape, general, points, montagne, jeune, équipes). Le même scraper
  dit que letour.fr est l'une des rares sources officielles joignables. Chemin exact et paramètres NON VÉRIFIÉS ;
  à retrouver via les sondes. Fragments HTML, pas du JSON pur, d'après ces descriptions.
  Couverture : Tour de France (hommes/femmes) seulement ; les autres épreuves ASO ont leurs propres sites,
  structure inconnue (Paris-Roubaix, Dauphiné, Paris-Nice : tous à examiner un par un).
  robots.txt/CGU ASO : NON LUS (letour.fr refusé par WebFetch).
- RCS Sport (Giro) : pas d'API officielle trouvée. Un acteur Apify dit que les pages publiques bloquent souvent
  le trafic datacenter (proxy résidentiel par défaut) : mauvais signe pour GitHub Actions.
- Unipublic/Vuelta (lavuelta.es) : aucune API trouvée, Eurosport publie des pages HTML de classement.
- Tissot Timing / Swiss Timing : aucun flux JSON public de résultats cyclisme trouvé. Tissot est chronométreur
  officiel (Tour de France, Vuelta, Tour de Suisse, Romandie, Mondiaux) ; les données passent par des systèmes
  propriétaires. Considéré INEXISTANT en accès libre.
- Données de pointages intermédiaires (sprints, cols, temps aux points) : aucune source libre structurée trouvée ;
  uniquement les classements finaux annexes.

## 5. Autres sources

- Wikipedia/Wikidata : Wikidata modélise les éditions de course, leurs étapes et les résultats (propriété P2501
  avec qualificatifs : général, points, montagne, jeune) ; point SPARQL query.wikidata.org en JSON. Utile pour
  vainqueurs/podiums, mais mise à jour manuelle, retard variable, couverture inégale des .1/.2, pas de DNF ni
  de temps complets. API MediaWiki (action=parse / REST) : NON TESTÉE (hôte bloqué ici) ; politique générale
  Wikimedia : User-Agent identifiable obligatoire, usage poli, légal. Bon REPLI pour les grands tours et monuments,
  pas pour le suivi d'une course en direct.
- ESPN : l'API cachée `site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard` existe pour d'autres sports ;
  aucun slug cyclisme confirmé. À sonder (probabilité faible).
- Cyclingnews, Eurosport, Orange, dicodusport.fr (Coupe de France / FDJ United Series, avec classement général après
  chaque course) : articles HTML sans structure garantie, droits d'auteur ; seulement pour recoupement manuel.
- Coupe de France : renommée « FDJ United Series » en 2026 (15 courses, ouverte aux équipes étrangères). Règlement sur
  lncpro.fr et ffc.fr (PDF). 5 classements : individuel, équipes, jeunes, grimpeurs, sprinters. Aucun open data ni
  API trouvés. DirectVélo : aucune page trouvée dans la recherche, NON ÉVALUÉ.
- Commercial : Sportradar (developer.sportradar.com, cyclisme), Enetpulse (JSON, Tour de France ; live selon
  l'événement). Payant, hors périmètre gratuit, à citer comme dernier recours.
- Agrégateurs Apify (PCS, Giro, Vuelta, letour.fr) : payants, ils contournent le blocage par proxy résidentiel :
  à ne pas utiliser (même problème éthique).

## 6. Recommandation

Constat honnête : il n'existe PAS de source unique, gratuite, structurée (JSON), officielle et autorisée pour tout le
périmètre. PCS couvre tout mais est exclu (CGU + Cloudflare).

1. Source principale proposée : pages officielles des organisateurs, course par course (letour.fr pour le TdF et
   sites équivalents pour les autres), UNIQUEMENT après lecture de robots.txt/CGU et sonde réussie. Couvre
   étape/général/annexes sur les grandes courses.
2. Secondaires : FirstCycling (si CGU/robots OK, couvre .1/.2 et startlists) ; UCI DataRide pour calendrier/classes
   et classement UCI (si accès public) ; Wikidata en repli pour vainqueurs et podiums.
3. N'existe nulle part en libre : temps aux pointages intermédiaires, sprints intermédiaires structurés, flux live
   JSON (Tissot/Swiss Timing), API officielle UCI documentée, données de la Coupe de France hors pages HTML.
4. Si le périmètre doit rester fiable : contacter UCI/LNC/FirstCycling pour un accès autorisé, ou acheter un flux
   (Sportradar/Enetpulse). Sinon réduire le périmètre aux courses couvertes par les sources autorisées et laisser
   les champs absents vides (règle cardinale).

## 7. Sondes à lancer depuis GitHub Actions

Workflow temporaire sur branche `ccr-*`, un `urllib.request` avec User-Agent honnête (nom du projet + contact), 1 requête
par URL, afficher code HTTP, 500 premiers caractères, présence de « Just a moment » / « cf-chl » / `cf-ray` /
`server: cloudflare`. Lire d'abord les robots.txt, ne rien interroger si un chemin y est interdit.

robots.txt et CGU (priorité absolue) :
- https://www.procyclingstats.com/robots.txt (confirmer le blocage, ne pas aller plus loin)
- https://firstcycling.com/robots.txt et la page de CGU liée dans le pied de page
- https://www.letour.fr/robots.txt ; https://www.uci.org/robots.txt ; https://dataride.uci.org/robots.txt
- https://www.giroditalia.it/robots.txt ; https://www.lavuelta.es/robots.txt ; https://www.paris-roubaix.fr/robots.txt
- https://www.lncpro.fr/robots.txt

Pages de résultats (HTML, à regarder aussi pour les appels XHR internes) :
- https://www.letour.fr/fr/classement-general ; https://www.letour.fr/en/rankings ;
  https://www.letour.fr/en/ajax/ranking/1/itg/ (hypothèse de forme : /ajax/ranking/{n° étape}/{type}/ ; à ajuster)
- https://firstcycling.com/race.php?r=17&y=2026 (exemple de format ; identifiants à vérifier) et
  https://firstcycling.com/race.php?r=17&y=2026&k=startlist
- https://dataride.uci.org/ ; https://www.uci.org/road/rankings (hors sonde si CGU l'interdit)
- https://www.giroditalia.it/en/classifiche/ ; https://www.lavuelta.es/es/clasificaciones

Repli et API ouvertes :
- https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Tour%20de%20France%202026&language=en&format=json
- https://query.wikidata.org/sparql?format=json&query=SELECT%20%3Fs%20WHERE%20%7B%3Fs%20wdt%3AP31%20wd%3AQ1318941%7D%20LIMIT%203
  (Q1318941 = course par étapes, repéré dans les résultats de recherche)
- https://fr.wikipedia.org/api/rest_v1/page/summary/Tour_de_France_2026
- https://site.api.espn.com/apis/site/v2/sports/cycling/scoreboard (sonde de découverte, probabilité faible)
- Contrôle de joignabilité PCS pour documentation seulement : GET https://www.procyclingstats.com/ (une seule
  requête, noter code 403/challenge ; ne pas insister)

Critères de décision : HTTP 200 + contenu exploitable + pas de challenge + robots.txt permissif + CGU lue et
compatible. Au moindre challenge Cloudflare : abandon de la source, pas de contournement.

## Sources consultées
- https://github.com/themm1/procyclingstats (README, scraper.py, issues)
- https://github.com/thomascamminady/LeTourDataSet
- https://github.com/r-huijts/firstcycling-mcp
- Extraits de recherche sur : PCS robots.txt et CGU, Apify (PCS, letour.fr, Giro, Vuelta), W3C opentrack-cg 2022-02-08,
  Wikidata WikiProject Cycling, enetpulse.com/cycling-data, dicodusport.fr, lncpro.fr/ffc.fr (règlement 2025).
