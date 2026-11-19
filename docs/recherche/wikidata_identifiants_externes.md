# Identifiants externes de Wikidata pour rattacher nos sources d'avant 2009 (« piste 1 »)

Mesures du 19/11/2026, essai `tools/essais/essai_wikidata_ids.py` (workflow `essais.yml`, runs 44463864694, 44464148099, 44464989780 ; lecture seule, UA du projet,
1 requête/s). Données d'archives lues dans le dépôt public d'archives (état du 19/11/2026 au matin : CQ Ranking 6 921 coureurs, the-sports.org 17 710 ids,
Museo 9 205 ids ; lectures de fiches encore partielles).

## 1. Propriétés confirmées (libellé et formatter lus sur Wikidata)

| Source | Propriété | Libellé (en) | Formatter (P1630) | Format (P1793) | Statut |
|---|---|---|---|---|---|
| CQ Ranking, coureur (hommes) | **P1541** | CQ Ranking male cyclist ID | `https://cqranking.com/men/asp/gen/rider.asp?riderid=$1` | `[1-9]\d*` | confirmée, identique à notre `riderid` |
| CQ Ranking, coureuse | P2709 | CQ Ranking female cyclist ID | `…/women/asp/gen/rider.asp?riderid=$1` | `[1-9]\d*` | AUTRE espace d'ids (femmes) : ne jamais la mélanger à P1541 |
| CQ Ranking, course | P2648 | CQ Ranking men's race ID | `…/men/asp/gen/race.asp?raceid=$1` | `[1-9]\d*` | confirmée, quasi absente (voir §3) |
| the-sports.org, athlète | **P4391** | The-Sports.org athlete ID | `https://www.the-sports.org/t-spf$1.html` | `\d+` | confirmée, identique à notre `id_site` (`spf<N>`) |
| Mémoire du Cyclisme, coureur | **P4516** | Mémoire du cyclisme cyclist ID | `memoire-du-cyclisme.eu/pelotons/coureurs.php?c=$1` (via wikiwix) | `\d+` | existe, mais c'est l'identifiant de l'ANCIEN site `.eu` ; notre `mdc.py` ne lit aucun id de coureur (noms seuls) : inutilisable aujourd'hui |
| Museo del Ciclismo | aucune | — | — | — | AUCUNE propriété (recherche de propriétés fr/en, plein texte dans l'espace Property « museociclismo », « Museo del Ciclismo ID »… : 0 résultat) |
| Cycling Archives / Site du Cyclisme, coureur | P1409 | Cycling Archives cyclist ID | `siteducyclisme.com/coureurfiche.php?coureurid=$1` | `[1-9][0-9]{0,5}` | confirmée (information) |
| Cycling Archives, course / équipe | P2330 / P2331 | … race ID / team ID | `…/ritfiche.php?ritid=$1` / `…/ploegfiche.php?id=$1` | `\d{5,6}` / `\d{2,5}` | confirmées |
| ProCyclingStats, coureur / course / équipe | P1663 / P2327 / P2328 | ProCyclingStats cyclist / race / team ID | `procyclingstats.com/rider/$1`, `race.php?id=$1`, `team/$1` | coureur `([1-9]\d{0,6})` | confirmées (identifiant seul, site jamais visité) |
| FirstCycling, coureur / course / équipe-saison | P10902 / P13447 / P13448 | FirstCycling rider / race / team season ID | `firstcycling.com/rider.php?r=$1` ; course via toolforge (`race.php?r=`) ; `team.php?l=$1` | `[1-9]\d*` | confirmées (identifiant seul) |
| CycleBase | P4508 (+ P14459 « new ») | CycleBase cyclist ID | `cyclebase.nl/…renner&id=$1` / `…/data/?pageid=renner&id=$1` | `\d+` / `[1-9]\d*` | confirmées (information) |
| Cycling Database (archivé) | P1664 | Cycling Database ID (archived) | `web.archive.org/…cyclingdatabase.com/$1` | `rider/[a-z-]+/\d+` | confirmée, rare (1 %) |
| UCI, coureur | P11020 | UCI rider ID | `uci.org/rider-details/$1` | — | trouvée par l'échantillon, hors demande : 93 % des coureurs « UCI avant 2009 » ; correspond à l'`uci_id` des fiches CQ Ranking (1 745 / 2 769 fiches lues) |
| CyclingRanking | aucune | — | — | — | aucune propriété trouvée (recherche « CyclingRanking » : rien) |

## 2. Couverture (coureurs)

Échantillon : 1 600 coureurs lus en claims (400 par groupe), tirage aléatoire reproductible. « UCI » = cache `entites/wikidata/coureurs.json` (carrière
commencée avant / après 2009 d'après les équipes P54, à défaut né avant 1981) ; « hist » = `entites/historique/coureurs.json` (vainqueurs et podiums d'avant 2009 : nés avant 1950, ou en 1950 et après).

| Identifiant | UCI avant 2009 | UCI après 2009 | hist < 1950 | hist 1950+ |
|---|---|---|---|---|
| ProCyclingStats (P1663) | 97 % | 96 % | 98 % | 98 % |
| Cycling Archives (P1409) | 94 % | 51 % | 94 % | 99 % |
| FirstCycling (P10902) | 80 % | 72 % | 86 % | 92 % |
| UCI rider ID (P11020) | 93 % | 82 % | 0 % | 54 % |
| **CQ Ranking (P1541)** | **78 %** | 31 % | 0 % | 53 % |
| CycleBase (P4508) | 41 % | 10 % | 60 % | 65 % |
| **Mémoire du Cyclisme (P4516)** | 38 % | 2 % | 70 % | 57 % |
| **the-sports.org (P4391)** | 21 % | 5 % | 40 % | 38 % |
| **Museo** | n. d. | n. d. | n. d. | n. d. (aucune propriété) |

Par décennie de naissance (échantillon cumulé, n = effectif) : CQ Ranking présent surtout pour les nés 1970-1989 (1970s : 160/215, 1980s : 321/384, 1990s : 150/273, 2000s : 16/152) et nul avant 1960 (CQ couvre 1999+ seulement) ;
the-sports.org couvre toutes les époques à 20-50 % (1880s 13/28, 1930s 33/80, 1980s 91/384) ; Mémoire du Cyclisme 55-85 % pour les nés avant 1960 puis s'effondre (1990s : 21/273).

Exemples réels : Q980148 (hist) porte P1409 8987, P1663 169810, P4508 4038, P4516 3170, P4391 47362, P10902 3054 ; Q949956 (UCI avant 2009) porte P1541 968, P1409 7115, P4508 15689, P1663 116842, P4516 19026, P10902 11135 ;
Q257126 (Greg Henderson) porte P1541 = 1018.

## 3. Couverture (séries d'épreuves et éditions)

39 QID de série (44 clés de `series_historiques.json`) et 593 éditions (400 d'avant 2009, 200 d'après) lues :

| Propriété | séries | éditions < 2009 | éditions >= 2009 |
|---|---|---|---|
| FirstCycling race (P13447) | 35/39 = 90 % | 97 % | 86 % |
| ProCyclingStats race (P2327) | 0 | 16 % | 78 % |
| Cycling Archives race (P2330) | 0 | 6 % | 7 % |
| **CQ Ranking race (P2648)** | **0** | **0 % (1/400)** | 4 % |
| Museo / the-sports.org / Mémoire du Cyclisme | **aucune propriété « course »** | | |

Conclusion : pour les ÉPREUVES, Wikidata ne relie à aucune de nos quatre sources (ni série, ni édition). Le rattachement des courses (alias_museo, clés d'édition) reste manuel / par nom ; seuls FirstCycling et PCS (identifiants, à titre d'information) sont présents.

## 4. Sens inverse : nos ids -> Wikidata (essais `inverse_cq`, `inverse_thesports`)

Technique : `haswbstatement:P1541=a|P1541=b|…` (syntaxe OU par barre verticale, validée : identique à l'union des requêtes individuelles ; les variantes `OR` / `OR` + guillemets renvoient 0 résultat), 10 ids par recherche, puis `wbgetentities` (claims, labels, aliases) par 50. Coût mesuré : 211 requêtes pour 1 500 ids CQ + lecture des 573 entités ; 1 500 ids the-sports : 169 requêtes.

### CQ Ranking (2 échantillons : 1 500 + 601 ids tirés au hasard parmi 6 921)
- Trouvés : 573/1 500 = 38 % ; 245/601 = 41 % (ensemble 39 %, soit ~2 700 ids sur 6 921). Jamais deux QID pour un même id ; jamais deux ids CQ sur un même QID.
- Parmi les 573 trouvés : date de naissance égale au jour ET nom concordant 538 (94 %) ; date égale mais nom discordant 11 (2 %, translittérations : Vinokurov/Vinokourov, Ignatiev/Ignatjew, Gretchyn/Grechyn, Sedun/Dimitri Sedun, noms arabes) ; date différente et nom concordant 19 (3,3 %, quasi tous une faute d'un chiffre ou jour/mois permutés des deux côtés, 1 vraie divergence d'année : Derganc 1977 / 1972, Delgado 1979 / 1977) ; date différente et nom discordant 1.
- Rapport à l'encyclopédie existante (clé nom + date sur nos fichiers UCI et historique) : 357 déjà rattachés par nom + date au même QID ; 88 « QID déjà connu sous une AUTRE clé » (cas **Greg / Gregory Henderson** : CQ « HENDERSON Gregory » né 1976-09-10 = Q257126 déjà dans le cache sous `henderson-greg-19760910`, que la clé slug du nom n'atteint pas ; autres : Hernâni Brôco, Moisés Dueñas, Jonas Aaen Jørgensen, Cédric Vasseur…) ; 9 « gains » où le cache avait la fiche UCI avec qid `null` (ex. Ivailo Gabrovski, Q599253 ; Dalivier Ospina ; Loto Petrus) ; 119 « nouveaux » (QID inconnu de l'encyclopédie : coureurs 1999-2008 absents des données UCI, que l'ajout des sources d'avant 2009 fera entrer).
- Extrapolation (x 4,6) sur les 6 921 ids : ~2 700 reliés ; dont ~78 % (≈ 2 100) atteignables SANS requête supplémentaire si les ids sont gardés dans le cache (voir §6), ~550 « nouveaux » à chercher par le sens inverse, ~40 gains sur des `null`.

### the-sports.org (1 500 ids tirés parmi 17 710)
- Trouvés : 151/1 500 = 10 % (~1 770 sur 17 710). Les non-trouvés sont en majorité des amateurs et des coureurs obscurs sans élément Wikidata.
- 151 trouvés : date égale + nom 115 ; une seule date connue (the-sports ne donne la date que sur la fiche, lue pour 6 752/17 710 ids) + nom concordant 30 ; date différente + nom concordant 5 (Caput 1923/1921, Ville 1901/1900, Landi jour/mois permutés…) ; date égale + nom discordant 1 (Gandarias Gandarias / Andrés Gandarias).
- 83 déjà connus (autre clé), 20 déjà rattachés, 48 nouveaux.
- **Doublons côté site** : 2 QID portent deux ids the-sports distincts (Q1876114 : 50178 + 256120 ; Q569809 : 1556 + 379320) : Wikidata révèle des fiches dupliquées sur the-sports.org, à fusionner chez nous (règle `_fusion_meme_saison`-like), sans date.
- Discordances de naissance dans le sens Wikidata -> nous (échantillon de 357 coureurs portant P4391 et présents chez nous) : 15 (4 %) ; 11 cas CQ sur 423 (2,6 %). Tous les cas examinés sont une faute de chiffre d'un côté ou de l'autre, quelques cas d'homonymes réels douteux (ex. thesports 50283 « Michel D'Hooghe » né 1909 / Q2576699 né 1912 ; 46472 Romain Maes 1913 / 1912).

### Mise en garde sur l'essai
Premier passage de croisement (couverture) : P2709 (CQ femmes) avait été mélangé à P1541 ; corrigé dans l'essai (les chiffres §4 viennent des phases `inverse_cq` avec P1541 seule). Les 11 « discordances CQ » du premier passage incluent donc quelques faux positifs de ce mélange (ex. Q16201761 pour Zbynek, Q241961 pour Hervé) et ne doivent pas être citées telles quelles.

## 5. Gains (ce que l'identifiant apporte réellement)
1. **Coût** : rattacher un coureur par nom + date coûte au moins 1 recherche + lectures de candidats (~1,5 requête / coureur) ; par id : 0,1 requête / id (lots de 10) + 0,02 (lecture par 50), soit 15 à 20 fois moins ; pour les ids déjà dans le cache : 0.
2. **Exactitude** : l'id lève les homonymes et les variantes de prénom (Greg / Gregory : 88 cas / 573 = 15 % des ids CQ trouvés sont déjà connus sous une clé que le slug du nom n'atteint pas ; 12 « null » récupérables) et les noms translittérés (2 % : nom discordant, date égale). Il permet aussi d'accepter un coureur dont la date Wikidata est fausse d'un chiffre (3 %), à condition de le marquer « à vérifier ».
3. **Couverture** : ~40 % des ids CQ et ~10 % des ids the-sports sont reliés. Le reste n'a pas d'élément Wikidata ou pas l'identifiant ; la méthode nom + date reste nécessaire, l'id est un complément prioritaire, pas un remplaçant.
4. **Détection de doublons de sites** (the-sports : 2 sur 151 trouvés), et jointure CQ <-> UCI (P11020 = `uci_id` CQ) comme preuve indépendante.
5. **Rien pour Museo ni (aujourd'hui) pour Mémoire du Cyclisme ; rien pour les courses.**

## 6. Proposition d'intégration dans `wikidata.py` (NON codée)

1. **Constante** `IDS_EXTERNES = {"cq": "P1541", "thesports": "P4391", "mdc": "P4516", "ca": "P1409", "pcs": "P1663", "fc": "P10902", "cyclebase": ["P4508", "P14459"], "cyclingdb": "P1664", "uci": "P11020"}` ; P2709 (femmes) volontairement absente.
2. **Extraction sans requête supplémentaire** : `extraire_coureur` (cache `coureurs.json`) et `historique.extraire_personne` (`historique/coureurs.json`) lisent déjà `claims` renvoyé par `wbgetentities` (`resoudre_tranche`, `run_lignees` ne sont pas concernées). Nouvelle fonction pure `ids_externes(e)` -> `{"cq": ["1018"], "thesports": ["…"], …}` : valeurs de rang non « deprecated » (`revendications`), chaînes, triées, uniques ; clé absente si vide ; champ `ids` de l'entrée (clé absente si aucun). Les valeurs sont gardées brutes (pas de normalisation), avec la regex Wikidata (`\d+`) pour écarter les valeurs aberrantes (compter et ignorer).
3. **Reprise** : ne PAS incrémenter `REGLE_COUREURS` (re-chercherait tous les `null`) ; ajouter `REGLE_IDS = 1` et le champ `regle_ids` des entrées rattachées ; `besoin_ids(entree)` vrai si `qid` et `regle_ids` < `REGLE_IDS` : relecture des claims par lots de 50 (~230 requêtes pour 11 300 QID du cache + ~55 pour les 2 725 de l'historique, soit ~5 minutes au total, mesuré : 1 600 coureurs en 59 requêtes / 65 s), exécutée en début de `run_coureurs` avant les nouveaux rapprochements ; les re-vérifications de 180 jours mettent à jour `ids` sans coût.
4. **Résolution inverse (nouveau fichier `entites/wikidata/ids_inverse.json`)** pour les ids de sources absents de tout `ids` du cache : `{source: {id_site: {"qid": QID|null, "verifie": date, "regle": N}}}` ; recherche `haswbstatement:P=a|P=b…` par 10 (jamais plus : 50 résultats maximum), puis claims + labels par 50 ; coût one-shot ~700 recherches + ~150 lectures pour les 6 921 ids CQ (~15-20 min), ~1 800 + ~350 pour the-sports (~40 min) ; `null` re-tenté après 60 jours ; budget et abandon 403/429 comme le reste du module.
5. **Règle d'acceptation d'un rattachement par id** (strictement plus fiable que nom + date puisque l'id est une preuve indépendante) : élément P31 = Q5 et cycliste (occupation) ET UN SEUL QID pour l'id ET (date de naissance jour égale à la nôtre, nom indifférent) OU (nom concordant et date absente d'un côté). Date différente + nom concordant (3 %) : mémorisé `{"qid": …, "statut": "a_verifier", "detail": …}` dans `ids_inverse.json`, jamais utilisé tant qu'un humain ne l'a pas validé (`alias_coureurs_wikidata.json`). Plusieurs QID pour un id, ou plusieurs ids sur un QID : `ambigu` / rapport de doublons de site, jamais tranché.
6. **Consommation** : `encyclopedie.construire` lit `ids` et `ids_inverse.json` pour (a) rattacher un coureur d'une source d'avant 2009 à son QID (puis à ses autres sources par l'union des ids : CQ <-> the-sports <-> Mémoire du Cyclisme) ; (b) signaler les `rider_id` UCI et ids de source qui divergent pour un même QID ; (c) exposer sur la fiche les identifiants PCS / FirstCycling / Cycling Archives / CycleBase en simples références (jamais de lien visité, comme les règles du projet).
7. **Tests** : étendre `FauxWikimedia` (déclarations `external-id`, recherche `haswbstatement:P=a|P=b`), cas Greg / Gregory, id sur QID non humain, deux QID pour un id, date différente + nom concordant, valeur deprecated.

## 7. Risques
- **Qualité Wikidata** : ~3 % de dates divergentes (chiffre ou jour/mois permutés), 2 % de noms transcrits autrement, ids erronés possibles (exemples non tranchés ci-dessus) ; l'id seul ne suffit jamais sans date ou nom concordant.
- **Espaces d'ids distincts** : P1541 (hommes) / P2709 (femmes) ; P4516 = ancien site `.eu` (ne pas supposer l'égalité avec l'id de memoireducyclisme.fr sans sonde) ; P14459 « new » de CycleBase.
- **Recherche CirrusSearch** : 50 résultats maximum par requête (lots de 10), latence d'indexation (un id récemment ajouté peut manquer), syntaxe OU = `|` seulement.
- **Couverture** : 10 % seulement pour the-sports.org (amateurs) ; aucun gain pour Museo et pour les courses.
- **Ne pas visiter** PCS / FirstCycling (exclus par CLAUDE.md) : seuls les identifiants sont conservés.
- Les chiffres de §4 sont des échantillons (n = 2 101 pour CQ, 1 500 pour the-sports.org) ; l'état des fiches the-sports (dates connues 6 752 / 17 710) évolue encore.
