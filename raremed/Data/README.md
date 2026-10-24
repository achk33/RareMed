# Dataset layout

Medical source files are downloaded manually into `raw/`. Version 0.4 reads them for ingestion and never overwrites them. Version 0.5 loads the current import into Neo4j.

| Path | Role |
| --- | --- |
| `raw/hpo/` | Human Phenotype Ontology. Expected: `hp.obo`, `phenotype.hpoa`. Also parses `hp.json` / `hp.owl` when present. |
| `raw/orphadata/` | Official Orphadata XML exports. Product 1 (diseases/xrefs) and product 4 (HPO associations) are extracted. Product 9 supplies official inheritance. |
| `raw/mondo/` | Mondo Disease Ontology. Parses `mondo.json`, `mondo.obo`, or `mondo.owl`. |
| `raw/literature/` | Local literature files, when you add them. Listed only. |
| `processed/` | Normalized entities, relationships, mappings, warnings, and run manifests. |
| `imports/` | Import-ready graph nodes and edges. Version 0.5 loads the current pointer into Neo4j. |
| `samples/` | Small synthetic UI fixtures. Safe to commit. |

Raw downloads are gitignored. Do not commit them. Do not edit files in `raw/`.
