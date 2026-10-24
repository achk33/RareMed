# Processed data

Version 0.4 writes normalized medical records here. Version 0.5 reads the current pointer when loading Neo4j:

- `current.json` — pointer to the latest successful import
- `runs/<run_id>/entities.jsonl`
- `runs/<run_id>/relationships.jsonl`
- `runs/<run_id>/mappings.jsonl`
- `runs/<run_id>/warnings.jsonl`
- `runs/<run_id>/manifest.json`

Raw downloads stay in `data/raw/` and are never written here.
