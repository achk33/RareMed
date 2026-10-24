"""Operational knowledge-graph schema for Version 0.6.

Asserted source relations are stored separately from inferred ones. This
release writes only asserted relations that appear in Version 0.4 imports or
official Orphadata fields. Genetic variants and diagnostic tests are created
only when those records exist.
"""

from __future__ import annotations

CONSTRAINTS = (
    "CREATE CONSTRAINT entity_curie IF NOT EXISTS FOR (n:Entity) REQUIRE n.curie IS UNIQUE",
    "CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (n:Evidence) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT source_key IF NOT EXISTS FOR (n:Source) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT graph_import_run IF NOT EXISTS FOR (n:GraphImport) REQUIRE n.run_id IS UNIQUE",
)

INDEXES = (
    "CREATE INDEX entity_kind IF NOT EXISTS FOR (n:Entity) ON (n.kind)",
    "CREATE INDEX entity_label IF NOT EXISTS FOR (n:Entity) ON (n.label)",
    "CREATE INDEX entity_namespace IF NOT EXISTS FOR (n:Entity) ON (n.namespace)",
    "CREATE INDEX disease_label IF NOT EXISTS FOR (n:Disease) ON (n.label)",
    "CREATE INDEX phenotype_label IF NOT EXISTS FOR (n:Phenotype) ON (n.label)",
    "CREATE INDEX gene_label IF NOT EXISTS FOR (n:Gene) ON (n.label)",
    "CREATE INDEX has_phenotype_id IF NOT EXISTS FOR ()-[r:HAS_PHENOTYPE]-() ON (r.id)",
    "CREATE INDEX has_phenotype_polarity IF NOT EXISTS FOR ()-[r:HAS_PHENOTYPE]-() ON (r.polarity)",
    "CREATE INDEX associated_gene_id IF NOT EXISTS FOR ()-[r:ASSOCIATED_WITH_GENE]-() ON (r.id)",
    "CREATE INDEX is_a_id IF NOT EXISTS FOR ()-[r:IS_A]-() ON (r.id)",
    "CREATE FULLTEXT INDEX entity_name_search IF NOT EXISTS FOR (n:Disease|Phenotype|Gene|InheritancePattern) ON EACH [n.label, n.curie]",
)

NODE_KINDS = {
    "Disease": "Disease",
    "Phenotype": "Phenotype",
    "Gene": "Gene",
    "Variant": "Variant",
    "InheritancePattern": "InheritancePattern",
    "DiagnosticTest": "DiagnosticTest",
    "Identifier": "Identifier",
    "Evidence": "Evidence",
    "Source": "Source",
}

RELATION_TYPES = {
    "HAS_PHENOTYPE": "HAS_PHENOTYPE",
    "IS_A": "IS_A",
    "ASSOCIATED_GENE": "ASSOCIATED_WITH_GENE",
    "ASSOCIATED_WITH_GENE": "ASSOCIATED_WITH_GENE",
    "HAS_INHERITANCE": "HAS_INHERITANCE",
    "INVESTIGATED_BY": "INVESTIGATED_BY",
    "XREF": "XREF",
    "CLASSIFIED_AS": "CLASSIFIED_AS",
    "RELATED_DISORDER": "RELATED_DISORDER",
    "ONTOLOGY_EDGE": "ONTOLOGY_EDGE",
}

LABEL_TO_KIND = {
    "Disease": "Disease",
    "Phenotype": "Phenotype",
    "Gene": "Gene",
    "Variant": "Variant",
    "InheritancePattern": "InheritancePattern",
    "DiagnosticTest": "DiagnosticTest",
    "Identifier": "Identifier",
}


def canonical_rel_type(raw: str) -> str | None:
    token = (raw or "").strip().upper().replace(" ", "_")
    return RELATION_TYPES.get(token)


def kind_from_labels(labels: list[str]) -> str:
    for label in labels:
        if label in LABEL_TO_KIND:
            return LABEL_TO_KIND[label]
    return "Identifier"
