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

## Décision

- Liste des participants : logo de lignée quand il existe, affiché seulement pour les saisons sous le nom actuel (`logo_depuis`),
  sinon initiales. Aucun maillot pour l'instant.
- Piste éventuelle (à valider avec le propriétaire) : maillots reconstitués à partir des motifs « Kit body » + couleurs du wikicode,
  pour les seules équipes où un motif libre existe ; couverture faible, coût élevé.
