from pathlib import Path

from app.ingestion.identifiers import parse_identifier
from app.ingestion.parsers.hpoa import parse_hpoa
from app.ingestion.parsers.obo_json import parse_obo_graphs_json
from app.ingestion.parsers.obo_text import parse_obo_text
from app.ingestion.parsers.orphadata import parse_orphadata_xml
from app.ingestion.parsers.owl import parse_owl

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion" / "complete" / "raw"


def test_identifier_keeps_source_form():
    iri = parse_identifier("http://purl.obolibrary.org/obo/HP_0000256")
    assert iri is not None
    assert iri.curie == "HP:0000256"
    assert iri.original.startswith("http://")
    compact = parse_identifier("HP:0000256")
    assert compact is not None
    assert compact.curie == iri.curie
    assert compact.original == "HP:0000256"
    orpha = parse_identifier("58", default_namespace="ORPHA")
    assert orpha is not None and orpha.curie == "ORPHA:58"


def test_hpo_obo_and_json_agree_on_synonyms():
    obo = parse_obo_text(
        FIXTURES / "hpo" / "hp.obo",
        source="hpo",
        role="hpo_ontology_obo",
        allowed_prefixes=("HP",),
        entity_type="phenotype",
    )
    json_result = parse_obo_graphs_json(
        FIXTURES / "hpo" / "hp.json",
        source="hpo",
        role="hpo_ontology_json",
        allowed_prefixes=("HP",),
        entity_type="phenotype",
    )
    assert obo.version == "2026-01-01"
    assert json_result.version == "2026-01-01"
    labels = {item.identifier.curie: item.label for item in json_result.entities}
    assert labels["HP:0000256"] == "Macrocephaly"
    synonyms = next(item for item in json_result.entities if item.identifier.curie == "HP:0000256").synonyms
    assert any(item.value == "Large head" and item.scope == "EXACT" for item in synonyms)
    assert any(item.rel_type == "is_a" for item in json_result.relationships)


def test_hpoa_preserves_absent_and_frequency():
    result = parse_hpoa(FIXTURES / "hpo" / "phenotype.hpoa")
    present = next(item for item in result.relationships if item.object.curie == "HP:0000256" and item.subject.curie == "ORPHA:58")
    absent = next(item for item in result.relationships if item.qualifier == "NOT")
    assert present.polarity == "present"
    assert present.frequency == "HP:0040281"
    assert present.frequency_normalized == "very_frequent"
    assert present.evidence == "TAS"
    assert absent.polarity == "absent"
    assert absent.object.curie == "HP:0001250"


def test_orphadata_product1_does_not_merge_multiple_mondo_xrefs():
    result = parse_orphadata_xml(FIXTURES / "orphadata" / "en_product1.xml", role="orphadata_diseases")
    assert result.version.startswith("1.3.42")
    assert result.release_date == "2026-06-23"
    diseases = [item for item in result.entities if item.entity_type == "disease"]
    assert {item.identifier.curie for item in diseases} == {"ORPHA:58", "ORPHA:166024"}
    mondo = [item for item in result.mappings if item.subject.curie == "ORPHA:58" and item.object.namespace == "MONDO"]
    assert {item.object.curie for item in mondo} == {"MONDO:0008762", "MONDO:0000001"}
    assert any("NTBT" in (item.mapping_relation or "") for item in mondo)


def test_orphadata_product4_keeps_frequency_and_excluded_polarity():
    result = parse_orphadata_xml(FIXTURES / "orphadata" / "en_product4.xml", role="orphadata_hpo_associations")
    by_hpo = {item.object.curie: item for item in result.relationships}
    assert by_hpo["HP:0000256"].frequency == "Very frequent (99-80%)"
    assert by_hpo["HP:0000256"].frequency_normalized == "very_frequent"
    assert by_hpo["HP:0000256"].polarity == "present"
    assert by_hpo["HP:0001250"].polarity == "absent"
    assert by_hpo["HP:0001250"].source_record_id == "102"


def test_mondo_json_skips_non_mondo_classes():
    result = parse_obo_graphs_json(
        FIXTURES / "mondo" / "mondo.json",
        source="mondo",
        role="mondo_ontology_json",
        allowed_prefixes=("MONDO",),
        entity_type="disease",
    )
    curies = {item.identifier.curie for item in result.entities}
    assert "MONDO:0008762" in curies
    assert not any(item.startswith("HGNC:") for item in curies)


def test_orphadata_product6_and_product7_use_parent_disorder():
    genes = parse_orphadata_xml(FIXTURES / "orphadata" / "en_product6.xml", role="orphadata_genes")
    assert any(item.identifier.curie == "HGNC:4235" for item in genes.entities)
    assert any(
        item.rel_type == "associated_gene" and item.subject.curie == "ORPHA:58" for item in genes.relationships
    )
    related = parse_orphadata_xml(
        FIXTURES / "orphadata" / "en_product7.xml", role="orphadata_disorder_associations"
    )
    assert any(
        item.rel_type == "related_disorder" and item.object.curie == "ORPHA:98006" for item in related.relationships
    )


def test_mondo_owl_reads_labels_and_subclass():
    result = parse_owl(
        FIXTURES / "mondo" / "mondo.owl",
        source="mondo",
        role="mondo_ontology_owl",
        allowed_prefixes=("MONDO",),
        entity_type="disease",
    )
    assert any(item.identifier.curie == "MONDO:0008762" and item.label == "Alexander disease" for item in result.entities)
    assert any(item.rel_type == "is_a" for item in result.relationships)
