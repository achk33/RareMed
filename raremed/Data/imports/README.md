# Imports

Version 0.4 writes import-ready graph records here:

- `current.json` — pointer to the latest successful import
- `runs/<run_id>/nodes.jsonl`
- `runs/<run_id>/edges.jsonl`
- `runs/<run_id>/manifest.json`

Version 0.5 loads `current.json` into Neo4j. Version 0.6 explores that graph through bounded admin endpoints. Raw downloads stay in `data/raw/`.
