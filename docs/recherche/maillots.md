# Maillots et logos d'équipes par saison (sonde du 16 novembre 2026)

Sonde : `tools/essais/essai_maillots.py` (`[essai:maillots]`), 12 équipes-saisons 2019-2025 (Movistar, Decathlon AG2R, Groupama-FDJ,
Lotto Dstny, Alpecin-Deceuninck, UAE, TotalEnergies, Arkéa, Corendon-Circus, Q36.5, Jumbo-Visma).

## Constats

- **Wikipédia en anglais** (« <année> <équipe> season », Infobox cycling team season) : paramètre `kitimage` présent sur 3 pages sur 12
  (Movistar 2019, Groupama-FDJ 2021, UAE 2022), mais les fichiers sont **absents de Commons** : téléversements locaux non libres
  (usage loyal). Réutilisation impossible.
- **Wikipédia en français** : aucun article « <équipe> <année> » sous ce titre pour l'échantillon.
- **Wikidata** : un élément par saison d'équipe (P31 = Q53534649, « cycling team season ») ; sa seule propriété média est P18 = **photo
  d'équipe** (présentation, peloton), pas un maillot. Pas de propriété « maillot ».
- **Commons** : quelques motifs « Kit body <équipe> <année>.png » (Alpecin-Deceuninck 2023, Arkéa-Samsic 2023, UAE 2023, Jumbo-Visma 2023) :
  calques transparents à colorier (les couleurs sont dans le wikicode des pages qui les utilisent). Couverture partielle (WorldTeams
  récentes), rendu à reconstituer, licence à vérifier fichier par fichier.
- **Logos** (P154 des lignées) : 19 lignées sur 328 en ont un sous licence lisible (les logos sont surtout des marques non libres).

## Mise à jour : maillots WorldDB (16 novembre 2026)

Le propriétaire a obtenu l'accord des auteurs de la base WorldDB (textures Pro Cycling Manager) pour publier leurs maillots, crédit « WorldDB ».
Sources (saison 2025 : 236 équipes, 160 champions nationaux, 494 maillots distinctifs de 123 courses, gabarit unique 1200x826) dans le dépôt privé
Camelbaggy/maillots-pcm ; `tools/maillots.py` n'en publie que le buste vu de face (`maillots/`, 3,6 Mo). Équipes reliées par le code UCI (174 équipes-saisons
2025 sur 204) ; affichage sur toute la période où l'équipe garde le même nom et le même code (décision du propriétaire). Cela remplace la décision ci-dessous
pour les équipes.

Précisions (17 novembre 2026) :
- `<ISO3>_maillot_champion.png` sont les tenues des **équipes nationales** (sponsors de fédération : CIC / Look pour la France, Beobank pour la
  Belgique…), pas les maillots de champion national (le champion porte un maillot tricolore aux couleurs de son équipe de marque). Utilisées
  pour les sélections nationales (Mondiaux 2025 : 43 sélections sur 57 ; les 14 autres n'ont pas de fichier WorldDB). Nos données ne contiennent
  d'ailleurs que les championnats de France (les autres championnats nationaux ne sont pas collectés).
- Maillots distinctifs : 123 courses WorldDB, 66 reliées à la main à une édition 2025 suivie (`COURSES_WORLDDB`, vérification visuelle des cas
  renommés : Coppi e Bartali, Okolo Slovenska, Route d'Occitanie, CRO Race, Tour of the Alps, Renewi Tour, Région Pays de la Loire Tour, AlUla Tour) ;
  les autres sont des courses non suivies en 2025 (U23, Saudi Tour avant renommage…). Affichage sur toute édition de même dénomination.

- 17/11 (règle du propriétaire) : les maillots distinctifs restent quand la course change de nom. `COURSES_WORLDDB` liste toutes les
  dénominations de chaque course (ex. Saudi Tour -> AlUla Tour, Tour of Qinghai Lake -> Tour of Magnificent Qinghai, Circuit Cycliste Sarthe ->
  Région Pays de la Loire Tour, Tour of Britain / OVO Energy / Lloyds) + les alias d'alias_courses.json : 71 courses, 113 clés d'édition. Ajouts :
  `tourofmalaysia` = Petronas Le Tour de Langkawi (inscriptions du maillot), Tour de Beauce, Ronde de l'Oise, Tour of Bulgaria, Tour of Thailand.
  Écarté faute de preuve : Eneco Tour 2026 (successeur possible du Renewi Tour).

## Décision (avant l'accord WorldDB)

- Liste des participants : logo de lignée quand il existe, affiché seulement pour les saisons sous le nom actuel (`logo_depuis`),
  sinon initiales. Aucun maillot pour l'instant.
- Piste éventuelle (à valider avec le propriétaire) : maillots reconstitués à partir des motifs « Kit body » + couleurs du wikicode,
  pour les seules équipes où un motif libre existe ; couverture faible, coût élevé.
