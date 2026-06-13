# App configuration files

This folder holds **application reference data** used by ETL and cleaning — not user upload datasets.

| File | Purpose |
|------|---------|
| `delete_description.csv` | Description blacklist for ETL (`OrderDataPipeline` rows filter) |
| `list_remove.csv` | Optional words/phrases to strip from descriptions (via `load_words_to_remove`) |

User CSV/Excel uploads and default analysis files belong in **`data/`** only.
