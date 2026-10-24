# RareMed AI Version 0.6 graph schema

The operational graph is loaded from Version 0.4 import records in `data/imports/`. Relations are asserted source facts. The loader never adds an edge because a language model suggested it, and it never merges two concepts because their labels look similar.

## Node labels

Every medical node also carries `:Entity` with a unique `curie`.

| Label | When created | Key properties |
| --- | --- | --- |
| `Disease` | ORPHA, MONDO, OMIM disease records | `curie`, `label`, `definition`, `synonyms`, `source`, `source_version` |
| `Phenotype` | HPO terms | same, plus `obsolete`, `alt_ids` |
| `Gene` | Official Orphadata gene records | `curie`, `label`, `source` |
| `Variant` | Only if an import record exists | `curie`, `label` |
| `InheritancePattern` | Official Orphadata `TypeOfInheritance` | `curie` (`ORPHA-INH:{id}`), `label` |
| `DiagnosticTest` | Only if an import record exists | `curie`, `label` |
| `Identifier` | Cross-reference stubs (ICD, UMLS, …) | `curie`, `namespace` |
| `Evidence` | One record per asserted edge | `id`, `source`, `source_file`, `source_version`, `source_record_id`, `polarity`, `frequency` |
| `Source` | Dataset name + version | `key`, `name`, `version`, `release_date` |
| `GraphImport` | Import job | `run_id`, `status`, `current`, `dataset_run_id` |

This checkout has no genetic-variant or diagnostic-test records. Those labels stay unused until a verified source supplies them.

## Relationship types

| Type | Meaning | Notes |
| --- | --- | --- |
| `HAS_PHENOTYPE` | Disease → Phenotype | `polarity` is `present`, `absent`, or `unknown`. `frequency` keeps the source string. Absence is not inferred from a missing row. |
| `IS_A` | Phenotype → Phenotype or Disease → Disease | Ontology hierarchy only |
| `ASSOCIATED_WITH_GENE` | Disease → Gene | From official gene-disease associations |
| `HAS_INHERITANCE` | Disease → InheritancePattern | From official `TypeOfInheritance` only |
| `INVESTIGATED_BY` | Disease → DiagnosticTest | Created only with verified source evidence |
| `XREF` | Cross-identifier mapping | Never treated as identity |
| `CLASSIFIED_AS` | Orphadata classification | Asserted parent classification |
| `RELATED_DISORDER` | Official disorder–disorder link | |
| `ONTOLOGY_EDGE` | Other documented ontology predicates | Predicate kept in properties |
| `SUPPORTED_BY` | Entity → Evidence | Provenance |
| `FROM_SOURCE` | Evidence → Source | Dataset version |

Every clinical relationship stores `inferred: false` in this version. Inferred edges, if added later, must use a different flag and must not be mixed into asserted retrieval.

## Constraints and indexes

- Unique `Entity.curie`, `Evidence.id`, `Source.key`, `GraphImport.run_id`
- Indexes on `label`, `namespace`, `kind`
- Relationship indexes on `HAS_PHENOTYPE.id` / `polarity` and gene/hierarchy ids
- Full-text index on disease, phenotype, gene, and inheritance labels

## Import and rollback

`python -m app.graph load` reads the current Version 0.4 `nodes.jsonl` / `edges.jsonl`, optionally adds official inheritance from Orphadata product 9, and writes batched parameterized `UNWIND` Cypher. Repeated loads `MERGE` on `curie` and relationship `id`.

A failed job deletes nodes and relationships whose `created_run_id` matches that job and restores the previous `GraphImport` pointer.

## Retrieval

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/graph/stats` | Node and relationship counts |
| `GET /api/v1/graph/diseases?q=` | Disease search |
| `GET /api/v1/graph/phenotypes?q=` | HPO search |
| `GET /api/v1/graph/diseases/{curie}` | Disease details |
| `GET /api/v1/graph/phenotypes/{curie}` | Phenotype details |
| `GET /api/v1/graph/diseases/{curie}/phenotypes` | Disease–phenotype evidence |
| `GET /api/v1/graph/neighborhood?curie=` | Bounded 1–2 hop neighborhood |
| `GET /api/v1/graph/provenance` | Source provenance |
| `GET /api/v1/graph/entities/{curie}` | Generic entity, relations, and provenance |
| `POST /api/v1/graph/load` | Admin-only load |
| `POST /api/v1/graph/rollback` | Admin-only rollback |
| `GET /api/v1/graph/explore/search` | Staff paginated explorer search |
| `GET /api/v1/graph/explore/neighborhood` | Staff bounded neighborhood |
| `GET /api/v1/graph/explore/expand` | Staff lazy neighbor expansion |
| `GET /api/v1/graph/explore/path` | Staff asserted shortest path (1–4 hops) |
| `GET /api/v1/graph/explore/sources` | Staff source/version facets |

Explorer responses are read-only and may set `truncated` when the neighborhood exceeds the requested limit. The admin Cytoscape canvas never loads the full graph.
