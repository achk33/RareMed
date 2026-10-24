import time
from pathlib import Path

import pytest

from app.graph.jobs import load_graph, rollback_graph
from app.graph.neo4j import _clean
from app.graph.loader import load_import_records, prepare_graph_payload
from app.graph.memory import InMemoryGraphStore
from app.graph.records import GraphEdge, GraphNode
from app.ingestion.parsers.orphadata import parse_orphadata_xml
from app.ingestion.pipeline import IngestionPipeline

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion" / "complete"


def test_neo4j_property_cleaner_serializes_nested_maps():
    assert _clean({"en": "All"}) == '{"en": "All"}'
    assert _clean(["Macrocephaly", "Large head"]) == ["Macrocephaly", "Large head"]
    assert _clean("Macrocephaly") == "Macrocephaly"


def test_orphadata_product9_extracts_official_inheritance():
    result = parse_orphadata_xml(
        FIXTURES / "raw" / "orphadata" / "en_product9_ages.xml",
        role="orphadata_epidemiology",
    )
    assert any(item.entity_type == "inheritance" and item.label == "Autosomal dominant" for item in result.entities)
    assert any(item.rel_type == "has_inheritance" and item.subject.curie == "ORPHA:58" for item in result.relationships)


def test_graph_load_from_fixtures_keeps_integrity_and_evidence(tmp_path: Path):
    root = tmp_path / "data"
    _copy(root)
    IngestionPipeline(root).run(run_id="graph-src")
    store = InMemoryGraphStore()
    payload = load_graph(root, store=store)
    assert payload["status"] == "succeeded"
    assert payload["inferred_relationship_count"] == 0

    curies = [node.curie for node in store.nodes.values()]
    assert len(curies) == len(set(curies))
    assert store.get_node("ORPHA:58").kind == "Disease"
    assert store.get_node("HP:0000256").kind == "Phenotype"
    assert store.get_node("HP:0000256").properties.get("label") == "Macrocephaly"

    isa = [edge for edge in store.edges.values() if edge.type == "IS_A" and edge.start == "HP:0000256"]
    assert any(edge.end == "HP:0000001" for edge in isa)

    present = store.disease_phenotypes("ORPHA:58", polarity="present")
    absent = store.disease_phenotypes("ORPHA:58", polarity="absent")
    assert any(edge.end == "HP:0000256" and edge.properties.get("frequency") for edge in present)
    assert any(edge.end == "HP:0001250" for edge in absent)
    hidden = store.disease_phenotypes("ORPHA:58", include_absent=False)
    assert all(edge.properties.get("polarity") != "absent" for edge in hidden)

    hits = store.search("Alexander", kinds=["Disease"])
    assert any(item.curie == "ORPHA:58" for item in hits)
    pheno = store.search("Macrocephaly", kinds=["Phenotype"])
    assert any(item.curie == "HP:0000256" for item in pheno)

    evidence = store.provenance(curie="ORPHA:58")
    assert evidence
    assert all(item.inferred is False for item in evidence)
    assert any(item.rel_type == "HAS_PHENOTYPE" and item.frequency for item in evidence)
    assert any(item.rel_type == "HAS_INHERITANCE" for item in evidence)

    neighborhood = store.neighborhood("ORPHA:58", depth=1, limit=20)
    assert neighborhood is not None
    assert neighborhood.center.curie == "ORPHA:58"
    assert len(neighborhood.edges) <= 20
    tiny = store.neighborhood("ORPHA:58", depth=1, limit=1)
    assert tiny is not None and tiny.truncated is True
    expanded = store.expand("ORPHA:58", limit=8)
    assert expanded is not None and expanded.edges
    path = store.path_between("ORPHA:58", "HP:0000256")
    assert path is not None
    assert {node.curie for node in path.nodes} >= {"ORPHA:58", "HP:0000256"}
    assert store.list_sources()

    first_count = len(store.edges)
    load_graph(root, store=store)
    assert len(store.nodes) == payload["node_count"] or len(store.edges) >= first_count
    rollback_graph(store=store)


def test_graph_does_not_merge_distinct_concepts_by_name():
    store = InMemoryGraphStore()
    store.load_batch(
        run_id="a",
        nodes=[
            GraphNode(curie="ORPHA:58", kind="Disease", properties={"label": "Alexander disease", "created_run_id": "a"}),
            GraphNode(curie="MONDO:0008762", kind="Disease", properties={"label": "Alexander disease", "created_run_id": "a"}),
        ],
        edges=[],
        evidence=[],
        dataset_run_id="src",
        previous_run_id=None,
    )
    assert store.get_node("ORPHA:58").curie != store.get_node("MONDO:0008762").curie
    with pytest.raises(ValueError):
        store.load_batch(
            run_id="b",
            nodes=[GraphNode(curie="ORPHA:58", kind="Phenotype", properties={"label": "Alexander disease"})],
            edges=[],
            evidence=[],
            dataset_run_id="src",
            previous_run_id="a",
        )


def test_referential_integrity_skips_dangling_edges(tmp_path: Path):
    path = tmp_path / "imports"
    path.mkdir()
    (path / "nodes.jsonl").write_text(
        '{"id":"HP:0000256","labels":["Phenotype"],"properties":{"label":"Macrocephaly","curie":"HP:0000256"}}\n',
        encoding="utf-8",
    )
    (path / "edges.jsonl").write_text(
        '{"id":"has_phenotype|ORPHA:58|HP:0000256|present|x|1","type":"HAS_PHENOTYPE","start":"ORPHA:58","end":"HP:0000256","properties":{"polarity":"present"}}\n',
        encoding="utf-8",
    )
    nodes, edges, evidence, warnings = load_import_records(path)
    assert [item.curie for item in nodes] == ["HP:0000256"]
    assert edges == []
    assert any("missing endpoint" in item for item in warnings)


def test_large_batch_import_performance():
    store = InMemoryGraphStore()
    nodes = [
        GraphNode(curie=f"HP:{index:07d}", kind="Phenotype", properties={"label": f"Term {index}", "created_run_id": "perf"})
        for index in range(4000)
    ]
    nodes.extend(
        GraphNode(curie=f"ORPHA:{index}", kind="Disease", properties={"label": f"Disease {index}", "created_run_id": "perf"})
        for index in range(2000)
    )
    edges = [
        GraphEdge(
            id=f"has_phenotype|ORPHA:{index}|HP:{index:07d}|present|x|{index}",
            type="HAS_PHENOTYPE",
            start=f"ORPHA:{index}",
            end=f"HP:{index:07d}",
            properties={"polarity": "present", "created_run_id": "perf", "frequency": "Frequent (79-30%)"},
        )
        for index in range(2000)
    ]
    started = time.perf_counter()
    store.load_batch(
        run_id="perf",
        nodes=nodes,
        edges=edges,
        evidence=[],
        dataset_run_id="perf",
        previous_run_id=None,
    )
    elapsed = time.perf_counter() - started
    assert len(store.nodes) == 6000
    assert len(store.edges) == 2000
    assert elapsed < 2.0
    assert store.search("Disease 12", kinds=["Disease"])


def test_prepare_payload_from_fixture_imports(tmp_path: Path):
    root = tmp_path / "data"
    _copy(root)
    IngestionPipeline(root).run(run_id="prep")
    payload = prepare_graph_payload(root)
    kinds = {node.kind for node in payload["nodes"]}
    types = {edge.type for edge in payload["edges"]}
    assert "Disease" in kinds and "Phenotype" in kinds
    assert "HAS_PHENOTYPE" in types and "IS_A" in types
    assert all(edge.inferred is False for edge in payload["edges"])


def _copy(root: Path) -> None:
    import shutil

    shutil.copytree(FIXTURES, root, dirs_exist_ok=True)
