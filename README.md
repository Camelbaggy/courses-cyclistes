# Courses cyclistes

Dashboard mobile des courses cyclistes sur route (hommes élite), centré sur les coureurs français : WorldTour,
ProSeries, FDJ United Series (ex-Coupe de France), courses .1/.2 en France ou avec un Français dans le top 10,
championnats. Mise à jour automatique après chaque étape, résumés rédigés par IA à partir des seuls résultats
officiels, notification ntfy.

- **Données** : UCI DataRide (résultats officiels), sites ASO (bonifications, équipes, parcours), LNC (FDJ United
  Series), récits DirectVélo / Cyclingnews (contexte des résumés uniquement, jamais republiés).
- **Page** : `index.html` (GitHub Pages), lit `data/index.json` puis `data/races/<id>.json`.
- **Automatisation** : `.github/workflows/update.yml`, toutes les heures de 13 h à 22 h UTC + 6 h 41 UTC.
- **Configuration** : secrets `GEMINI_API_KEY`, `NTFY_TOPIC` ; variable `DASHBOARD_URL`.

Documentation technique : `CLAUDE.md`, spécification : `docs/SPEC.md`, recherches sur les sources : `docs/recherche/`.
