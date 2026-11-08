# Classement UCI individuel hommes élite (route) : endpoints publics DataRide

Date : 8 novembre 2026, depuis GitHub Actions (`tools/essais/essai_classement.py`, 6 passes de sonde puis essai final : 13 requêtes pour 2 classements complets). Pause d'au moins 1,1 s par requête, User-Agent de `netutil`.

## Verdict : source publique trouvée, classement complet avec date de naissance

Les pages iframe `https://dataride.uci.org/iframe/Rankings/10/` (liste des classements) et `/iframe/RankingDetails/{id}?...` (détail) sont publiques et sans jeton. Leur JavaScript appelle les endpoints ci-dessous ; `uci_ranking.py` fait les mêmes appels. L'API privée à jeton Bearer de fr.uci.org n'est pas utilisée.

## Endpoints (base `https://dataride.uci.org`, route = `disciplineId=10`)

| Rôle | Appel | Paramètres |
|---|---|---|
| Saisons | `GET /iframe/GetDisciplineSeasons/` (ou `GetRestrictedResultsDisciplineSeasons`, déjà utilisé par `uci.py`) | `disciplineId=10` ; 2027 = id 477, 2026 = id 464 |
| Catégories | `GET /iframe/GetRankingsCategories/` | `disciplineId`, `disciplineSeasonId` ; 22 = Men Elite |
| Dates de calcul | `GET /iframe/GetRankingMoments/` | `disciplineId`, `disciplineSeasonId`, `rankingId` ; `Id 0` = « Most Recent Ranking », puis un `MomentId` par date (hebdomadaire : 27/10/2026, 03/11/2026 en saison 2027) |
| Liste des classements | `POST /iframe/RankingsDiscipline/` | `disciplineId=10` + grille Kendo, filtres `RaceTypeId=0`, `CategoryId=22`, `SeasonId=<id>` |
| Lignes d'un classement | `POST /iframe/ObjectRankings/` | `rankingId`, `disciplineId=10`, `rankingTypeId=1` + Kendo `take/skip/page/pageSize` + filtres `RaceTypeId=0`, `CategoryId=22`, `SeasonId`, `MomentId` |

Format des POST : `application/x-www-form-urlencoded`, mêmes en-têtes que `uci._post` (réutilisé tel quel). Les filtres Kendo sont obligatoires pour `ObjectRankings` : sans `SeasonId`/`MomentId`, `{"data":[],"total":0}` (testé : `rankingId` seul, avec ou sans `momentId` en champ simple, donne 0 ligne). `CountryId=0` est accepté sans effet.

### `RankingsDiscipline`

Renvoie un **tableau de groupes** (pas d'enveloppe `data`) : `{GroupId, GroupName, Rankings: [{Id, RankingTypeId, RankingName, MomentId, DisciplineSeasonId, CategoryId, ObjectRankings: [aperçu de quelques lignes]}]}`. `RankingTypeId` : 1 = individuel, 2 = nations, 3 = équipes. `MomentId` = date de calcul la plus récente. Groupes hommes élite en 2027 :

| GroupId | Nom | `Id` (individuel) |
|---|---|---|
| 1 | UCI World Ranking | 1 (nations : 238, équipes : 9) |
| 152 | One Day Race World Ranking | 237 |
| 153 | Stage Race World Ranking | 236 |
| 7 à 11 | Africa / America / Asia / Europe / Oceania Tour | 2 / 3 / 4 / 5 / 6 |

**Pas de classement « UCI WorldTour » séparé** : il n'existe pas dans la liste (il a été fusionné dans le World Ranking). Les classements « saison » sont les circuits continentaux et les classements One Day / Stage Race.

### `ObjectRankings`

`{"data": [...], "total": N}` ; **1000 lignes maximum par page** (`take=1000` renvoie 1000), pagination par `skip`. Le World Ranking compte `total = 3408` lignes (2027, du 03/11/2026) et 3402 (2026, au 18/10/2026). Parcours complet : 4 requêtes. Un enregistrement :

```json
{"ObjectId": 149727, "UciId": 10014972740, "Rank": 1, "PrecedingRank": 1, "DisplayName": "POGAČAR Tadej",
 "TeamName": "UAE TEAM EMIRATES XRG", "TeamCode": "UEX", "NationName": "SLO       ", "NationFullName": "SLOVENIA",
 "BirthDate": "/Date(906328800000)/", "Ages": 28, "Points": 9331.75, "SanctionPoints": 25.0,
 "ComputationDate": "/Date(1793667608610)/", "MomentId": 206851, "FlagCode": "si", "CountryIsoCode2": "SI"}
```

- `ComputationDate` : date du calcul (ici 3 novembre 2026). Pour la saison 2026, c'est la fin de saison (18 octobre 2026). C'est la date renvoyée par `get_ranking()["date"]`.
- `BirthDate` : présent pour toutes les lignes observées (0 manquant sur 3408) → clé coureur exacte.
- `NationName` : 3 lettres rembourrées d'espaces (vide pour 21 lignes sur 3408). `TeamName` : majuscules UCI, **vide pour ~1320 lignes** (coureurs sans équipe de la liste, individuels, équipes de club non rattachées) : champ laissé `None`, jamais inventé.
- `Rank` : entier ; les **ex aequo partagent le même rang** (2838 rangs distincts pour 3408 lignes) ; l'ordre de la liste suit le rang.
- `PrecedingRank` : rang au calcul précédent (exposé en `previous_rank`) ; `UciId` : identifiant UCI du coureur (exposé en `uci_id`, utile pour de futurs rapprochements).

## Module `uci_ranking.py`

- `get_ranking(season_year=None, group_id=1)` → `{"name", "date", "source": "uci-dataride", "season", "rows"}` ou `None`. `season_year=None` : saison UCI en cours (`uci.season_for`). Lignes : `rank, rider` (nom UCI brut « POGAČAR Tadej »), `name` (« Tadej Pogačar »), `birth_date`, `nationality`, `team` (`uci.team_name`), `points`, `rider_id`, `uci_id`, `previous_rank`.
- `rider_key(rider, birth_date)` : `"nom-prenom-AAAAMMJJ"`, identique à `uci.rider_ref` (vérifié sur les 3408 + 3402 lignes : 0 écart avec `rider_id`). **`rider` doit être le nom UCI brut** (« NOM Prénom ») ; la forme « Prénom Nom » donnerait une autre clé. Sans date de naissance : `None` (rapprocher alors par `netutil.normalize` du nom).
- `list_rankings(season_id)` : catalogue des classements disponibles (tableau ci-dessus).

## Conformité

- Pages et XHR de l'iframe publique, sans login, cookie, jeton ni contournement ; aucun 403/429/challenge sur `dataride.uci.org`. Le jeton Bearer de uci.org n'est pas touché. Les règles de `sonde_uci.md` (robots.txt sans interdiction, pas de CGU propres aux iframes, attribution « Source : UCI DataRide » recommandée) s'appliquent.
- Charge : 1 requête de liste + 4 pages = 5 requêtes pour le classement complet. Le classement n'est recalculé qu'une fois par semaine (mardi) : une seule collecte par jour suffit.

## Limites

- Pas de classement « UWT » séparé ; pas d'historique exploité (les `MomentId` antérieurs sont listés par `GetRankingMoments`, non utilisés).
- Les points d'un coureur peuvent comprendre des sanctions (`SanctionPoints`), non exposées.
- Défaut hors périmètre constaté : `uci.team_name("RED BULL - BORA - HANSGROHE")` donne « RED Bull - Bora - Hansgrohe » (le mot « RED » de 3 lettres est pris pour un sigle).
