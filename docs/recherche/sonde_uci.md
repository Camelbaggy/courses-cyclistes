# Sonde UCI : endpoints publics DataRide (résultats et calendrier route hommes élite)

Date de la sonde : 8 novembre 2026, depuis GitHub Actions (Python 3.11, bibliothèque standard).
Code : `tools/sondes/sonde_uci.py` (base du futur collecteur). 12 exécutions, quelques centaines de requêtes au total, une pause de 1,1 s ou plus entre requêtes, User-Agent `courses-cyclistes-sonde/0.1 (projet personnel non commercial)`.

## Verdict

**Oui pour les résultats, pas encore démontré pour le calendrier à venir.**

- Résultats : les endpoints « iframe » de DataRide sont publics, sans login, sans cookie, sans challenge Cloudflare. Ils renvoient du JSON structuré (classement, temps ou écarts, nationalité, équipe, date de naissance, dossard, points UCI, code d'abandon). Couverture constatée de la classe 2.UWT aux championnats nationaux (CN). L'UCI peut être la **source principale des résultats**.
- Calendrier : la liste `Competitions` donne classe UCI, dates, pays et identifiant, mais elle ne contient **que les courses déjà courues ou en cours**. La saison 2027 (identifiant 477) ne listait au 8 novembre que 6 courses, toutes déjà commencées, aucune UWT ou Pro ; aucune course à venir dans aucune saison. Cette liste est la vue « Résultats » de DataRide. Le calendrier prévisionnel est ailleurs (`www.uci.org/road/calendar` et `/calendar/road/{id}`, rendus par un CMS, **non explorés**). Il reste à valider.
- Réserve juridique : `robots.txt` n'interdit rien, mais les conditions d'utilisation de DataRide n'ont pas été lues. À faire avant tout usage régulier.

## Conformité robots.txt et usage

| Hôte | robots.txt | Constat |
|---|---|---|
| `www.uci.org` | `User-agent: *` / `Allow: /` | tout autorisé |
| `dataride.uci.ch` | HTTP 200, 1248 octets, uniquement le bloc de commentaires Cloudflare « content signals », aucune directive `Disallow` ni ligne `Content-Signal` | aucune restriction exprimée |
| `dataride.uci.org` | HTTP 404 | aucune règle |

- Aucun 403, 429, 503 ni page de challenge sur `dataride.uci.org` et `www.uci.org` pendant les 12 exécutions. Le seul échec réseau est un 522 (timeout) sur `wwwnew.uci.org`, hôte sans intérêt.
- Les chemins appelés sont ceux des pages « iframe » conçues pour être intégrées chez des tiers (`/iframe/...`). La sonde reproduit ce que fait le JavaScript de ces pages.
- Hôtes : seul `dataride.uci.org` a servi les données. `dataride.uci.ch` (domaine canonique annoncé dans les pages) n'a pas été testé pour `/iframe`.
- Aucun contournement n'a été nécessaire ni tenté.

## Endpoints validés

Base : `https://dataride.uci.org`. Route : `disciplineId=10`. Les POST sont de type `application/x-www-form-urlencoded` (en-têtes envoyés : `X-Requested-With: XMLHttpRequest`, `Referer: .../iframe/Results/10/`, non vérifiés comme obligatoires). Les listes paginées répondent `{"data":[...],"total":N}` (convention Kendo). Les dates sont au format .NET `"/Date(1775944800000)/"` (millisecondes UTC ; 1775944800000 = 11 avril 2026 22:00 UTC = 12 avril 00:00 à Paris). Le champ texte `Date` (« 12 Apr 2026 ») est directement lisible.

### 1. Saisons (GET)

`GET /iframe/GetRestrictedResultsDisciplineSeasons/?disciplineId=10` renvoie un tableau : `{Id, Year, Name, StartDate, EndDate, ...}`.
Identifiants constatés : 2027 = 477 (19 oct 2026 au 18 oct 2027), 2026 = 464 (20 oct 2025 au 18 oct 2026), 2025 = 444, 2024 = 432, 2023 = 414. La « saison 2026 » d'UCI va donc d'octobre 2025 à octobre 2026.

### 2. Catégories et types de course (GET)

- `GET /iframe/GetRestrictedResultsCategories/?disciplineId=10&disciplineSeasonId=464` : `Id 22` = **Men Elite** (code ME) ; 23 = Women Elite ; 26 = Men Under 23 ; 24 = Men Junior ; 0 = All, etc.
- `GET /iframe/GetRestrictedResultsRaceTypes/?disciplineId=10&disciplineSeasonId=464` : 36 = Individual Road Race, 37 = Individual Time Trial, 87 = Team Time Trial, 141 = Team time trial mixed relay, 0 = All.

### 3. Calendrier (courses courues) : `POST /iframe/Competitions/`

Paramètres (réplique exacte de la grille de la page `/iframe/Results/10/`) :

```
disciplineId=10
take=100&skip=0&page=1&pageSize=100        (100 par page vérifié ; la page utilise 40)
sort[0][field]=StartDate&sort[0][dir]=asc
filter[logic]=and
filter[filters][0][field]=RaceTypeId  [operator]=eq  [value]=0
filter[filters][1][field]=CategoryId  [operator]=eq  [value]=22
filter[filters][2][field]=SeasonId    [operator]=eq  [value]=464
```

Les **trois** filtres sont obligatoires : un seul ou deux provoquent une page HTML « Exception occured while executing the controller » avec HTTP 200 (à détecter côté client). Sans filtre : `{"data":[],"total":0}`.

Réponse (`total` = 473 pour 2026 Men Elite), un enregistrement :

```json
{"CompetitionId": 76380, "CompetitionName": "Paris-Roubaix Hauts-de-France",
 "StartDate": "/Date(1775944800000)/", "EndDate": "/Date(1775944800000)/", "Date": "12 Apr 2026",
 "CountryName": "FRANCE", "CountryIsoCode3": "FRA", "CountryIsoCode2": "FR", "FlagCode": "fr",
 "ClassCode": "1.UWT", "IsDone": false, "IsInProgress": false}
```

Classes présentes en 2026 Men Elite (473 courses) : CN 120, 1.2 92, 2.2 64, 1.1 60, 1.Pro 33, 2.1 32, 2.Pro 25, 1.UWT 21, 2.UWT 15, CC 5, CRTP 2, 1.2S, CM, JC, JR 1 chacune. Pas de pagination au-delà de `total` : 5 pages de 100.

Limites : `IsDone` et `IsInProgress` valent `false` pour **toutes** les courses (479 sur 479 passées, y compris celles terminées le jour même) : inutilisables. Le filtre de catégorie n'expose pas de champ `CategoryCode` dans la réponse (déjà filtré). Les identifiants de course sont stables d'une saison à l'autre ? Non vérifié.

### 4. Étapes : `POST /iframe/Races/`

Paramètres : `disciplineId=10&competitionId=76399` (+ pagination Kendo, 60 par page suffisent). Un enregistrement par étape plus un enregistrement « Final Classification ».

```json
{"Id": 256544, "Index": 1, "RaceName": "Final Classification", "RaceCode": "F",
 "RaceTypeCode": "IRR", "CategoryCode": "Men Elite", "DisciplineCode": "ROA",
 "Date": "26 Jul 2026", "StartDate": "/Date(...)/", "StartLocation": "", "EndLocation": null}
```

- Course d'un jour (Paris-Roubaix) : 1 enregistrement « Final Classification » (`Id` 257202).
- Course par étapes : Tour de France 2026 = 22 enregistrements (Index 1 = Final Classification, Index 2 = Stage 21 ... Index 22 = Stage 1). Paris-Nice 2026 = 9. Les villes de départ et d'arrivée sont vides sur les courses testées.
- `RaceTypeCode` vaut `IRR` pour « Final Classification » ; non relevé pour les étapes (le type d'une étape contre-la-montre n'a pas été vérifié).

### 5. Classements d'une étape ou d'une course : `POST /iframe/Events/`

Paramètres : `disciplineId=10&raceId=<Races.Id>`. Réponse : **tableau JSON** (pas d'enveloppe `data`) de `{EventId, EventCode, EventName, WinnerName, IsTeamEvent, CompetitorTypeId, ...}`.

| Race | Events constatés (`EventName`) |
|---|---|
| Final Classification du Tour de France | General Classification (365669, vainqueur « POGAČAR Tadej »), Points Classification, Mountain Classification, Youth Classification |
| Stage 21 du Tour | Stage Classification, Stage Points Classification, Stage Mountain Classification, Stage Youth Classification |
| Stage 1 du Tour (CLM par équipes) | Stage Classification, Stage General Classification, Overall Youth Classification, `IsTeamEvent: true` |
| Final Classification de Paris-Nice | General, Points, Mountain, Youth |
| Course d'un jour | 1 seul event « General Classification » |
| Tour du Faso (2.2) | Stage General Classification, Stage Classification, Overall Points Classification, Stage Points Classification, ... |

Points d'attention : l'**ordre et les libellés varient** d'une course à l'autre (Boucles de la Mayenne : le premier event est « Youth Classification »). Le collecteur doit choisir l'event par `EventName` (avec une table de correspondance), jamais par position. Aucun classement par équipes (« Team Classification ») n'a été vu sur le Tour ni sur Paris-Nice : à confirmer sur d'autres courses. Le classement général après chaque étape intermédiaire n'a pas été vérifié (l'event des étapes intermédiaires est plus gros, 4693 octets pour l'étape 8 contre 2383 pour l'étape 21, ce qui suggère des events supplémentaires : à vérifier).

### 6. Résultats : `POST /iframe/Results/`

Paramètres : `disciplineId=10&eventId=<EventId>&take=40&skip=0&page=1&pageSize=40` (40 par page ; un test à 100 ou plus n'a pas été fait pour cet endpoint). `total` donne le nombre de lignes (Paris-Roubaix 2026 : 175 ; Tour 2026 général : 158 ; étape 8 : 176).

Un enregistrement (général du Tour 2026, rang 1) :

```json
{"ResultId": 10818834, "Rank": "1", "RankNumber": 1, "SortOrder": 1, "Bib": "1",
 "DisplayName": "POGAČAR Tadej", "BirthDate": "/Date(906328800000)/", "Age": "28",
 "NationName": "SLO       ", "IsoCode2": "SI", "IndividualCountryNameText": "SLOVENIA", "FlagCode": "si",
 "TeamName": "UAE TEAM EMIRATES XRG", "ResultValue": "73:56:26", "PointPcR": 1300.0,
 "Irm": null, "TeamType": 3, "Phase": null, "Heat": null}
```

Champs utiles :

- `Rank` (chaîne, vide pour les non-classés) / `RankNumber` (entier ou null), `SortOrder`.
- `ResultValue` : temps du vainqueur en `h:mm:ss` (`5:16:52`, `73:56:26`, ou `28:16.61` pour un contre-la-montre), puis écarts `+6:26`, `+13`, `+00` (secondes ou minutes:secondes) ; pour les classements annexes, **points** (points `559`) ou **nombre de points de montagne** (`156`) dans la même colonne. Le format n'est pas homogène : à normaliser dans le collecteur.
- `DisplayName` au format `NOM Prénom` (casse mixte, accents conservés) ; **aucun identifiant coureur ni équipe dans la réponse** (seulement `ResultId`). Clé de jointure à construire : nom + date de naissance.
- `NationName` (code à 3 lettres rempli d'espaces, `FRA       `), `IsoCode2`, `IndividualCountryNameText` (nom anglais), `FlagCode`.
- `TeamName` : nom UCI en majuscules (`GROUPAMA-FDJ UNITED`, `DECATHLON CMA CGM TEAM`, `COFIDIS`). Vide (null) pour les championnats nationaux ou continentaux.
- `PointPcR` : points UCI attribués (1300 pour le vainqueur du Tour ; `PcRPrefix`/`PcRSuffix` en texte).
- `Bib` : dossard. `BirthDate`, `Age`.
- `Irm` : motif de non-classement. Codes (`GET /iframe/GetIrms/`) : `ABD`, `DNF`, `DNS`, `DOP`, `DSQ`, `LAP`, `OTL`, `OVL`, `REC`, `REL`. Constaté : `DNF` sur 15 des 15 dernières lignes de Paris-Roubaix 2026 (rang vide, `ResultValue` null). Les abandons sont donc **listés en fin de classement avec `Irm`**, mais la minute ou le kilomètre de l'abandon n'existe pas.
- Écarts : donnés en chaîne (cumul depuis le vainqueur), pas en secondes. Pas de bonifications ni de temps intermédiaires.

Exemples réels : Paris-Roubaix 2026 : 1 VAN AERT Wout (TEAM VISMA | LEASE A BIKE, BEL) 5:16:52 ; 2 POGAČAR Tadej +00 ; 3 STUYVEN Jasper +13. Tour 2026, jeune : 1 DEL TORO Isaac, 2 SEIXAS Paul (FRA, DECATHLON CMA CGM TEAM) +2:14.

## Couverture constatée par classe (courses 2026 Men Elite)

Chaque ligne = une course testée de bout en bout (Races, Events, Results avec au moins un classement non vide).

| Classe | Course testée | Résultat |
|---|---|---|
| 1.UWT | Paris-Roubaix (12 avr), Bretagne Classic (30 août) | OK, 175 et 168 classés |
| 2.UWT | Tour de France, Paris-Nice | OK, 4 classements + étapes |
| 1.Pro | Veneto Classic, Japan Cup, Paris-Tours (11 oct) | OK, 141, 110, 165 classés |
| 2.Pro | Boucles de la Mayenne (mai) | OK, 4 classements |
| 1.1 | Chrono des Nations (18 oct) | OK, 21 classés |
| 2.1 | TPC en Nouvelle-Aquitaine (août) | OK, 4 classements d'étape |
| 1.2 | Grand Prix de Plouay, Tour de Okinawa | OK |
| 2.2 | Tour de Guadeloupe, Tour du Faso, Vuelta a Guatemala | OK |
| CN | Championnats nationaux de France (25 au 28 juin), Cuba, Paraguay | OK, `TeamName` vide |
| CC | Championnats d'Europe, Afrique | OK |
| CRTP | Japan Cup Criterium | OK |

Aucune course sans résultat n'a été rencontrée parmi les 479 courses passées échantillonnées, mais seules ~25 ont été ouvertes. Les coureurs et équipes français sont présents (Plouay, France nationaux, Mayenne, TPC).

## Délai de publication

Constaté le 8 novembre 2026 à 06:26 UTC : Tour de Okinawa (1.2, 8 nov, Japon) avec 69 classés et un vainqueur ; dernière étape du Tour du Faso (2.2, 8 nov) présente ; Tour de Guatemala (se terminait le 1er nov) complet. Les résultats apparaissent donc **dans les heures qui suivent l'arrivée**, y compris pour une 1.2. Le délai exact n'est pas mesuré (il faudrait interroger plusieurs fois le jour d'une course). Les classements annexes et le général d'un Grand Tour étaient présents après la dernière étape.

## Limites et points à traiter

1. **Calendrier à venir absent** de `Competitions` (voir verdict). Prochaine sonde : `www.uci.org/road/calendar` et `/calendar/road/{id}` (HTML rendu par le CMS), champ des années 2027, présence des classes UWT/Pro.
2. **Listes de départ indisponibles** : `POST /iframe/GetRiderList/` répond 404 depuis le domaine public (route d'administration). Pas de liste de départ avant la course. Les dossards et les DNS n'existent qu'après coup dans `Results`.
3. `IsDone` / `IsInProgress` inutilisables.
4. Pas d'identifiant coureur ni équipe dans `Results` ; formats de `ResultValue` hétérogènes ; ordre des events variable.
5. Erreurs serveur annoncées avec HTTP 200 et un corps HTML : toujours vérifier que la réponse est du JSON.
6. Latence : une exécution complète de ~120 requêtes a pris environ 1 à 2 minutes ; certaines requêtes `Races`/`Events` sur de gros événements prennent 5 à 6 s. Aucune erreur ni limitation côté UCI observée.
7. Non couvert : classements UCI (`RankingDetails`, `RiderRankingDetails`, `TeamRankingDetails`), fiches coureurs, temps intermédiaires, résultats par équipes (TTT) au-delà de l'événement d'étape, courses femmes.
8. Charge conseillée pour le collecteur : ne requêter que les courses utiles (classes, pays, présence de clubs français), mettre en cache `Competitions` (une fois par jour), 1 à 2 requêtes par seconde au plus, arrêt immédiat au premier 403/429/503.

## Reproduire

```
python tools/sondes/sonde_uci.py        # nécessite un accès réseau à dataride.uci.org (GitHub Actions)
```

Le script exécute `passe11()` : calendriers 2026 et 2027, 6 dernières courses passées, couverture par classe, Paris-Roubaix, abandons, codes `Irm`. Budget interne : 240 s.
