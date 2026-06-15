# shared/

Cross-service constants shared (by reference) between the API, worker and web
app. `sections.json` is the single source of truth for IELTS section names,
difficulty bands, card states, pattern categories and supported AI providers.

The backend mirrors these in `api/extraction/ielts_markers.py` and
`shared/sections.json`; the frontend mirrors them in `web/types/index.ts` and
the page-level filter lists. Keep them in sync when adding a new section or
category.
