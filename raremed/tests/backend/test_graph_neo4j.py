import os

import pytest

from app.graph.neo4j import Neo4jGraphStore, probe_neo4j
from app.graph.records import GraphEdge, GraphNode


@pytest.mark.integration
def test_neo4j_batched_import_and_rollback():
    if probe_neo4j().status != "ok" and not os.environ.get("NEO4J_URI"):
        pytest.skip("Neo4j is not available.")
    if probe_neo4j().status != "ok":
        pytest.skip("Neo4j is not available.")

    store = Neo4jGraphStore()
    run_id = "test-graph-batch"
    nodes = [
        GraphNode(curie="ORPHA:58", kind="Disease", properties={"label": "Alexander disease", "curie": "ORPHA:58"}),
        GraphNode(curie="HP:0000256", kind="Phenotype", properties={"label": "Macrocephaly", "curie": "HP:0000256"}),
    ]
    edges = [
        GraphEdge(
            id="has_phenotype|ORPHA:58|HP:0000256|present|test|1",
            type="HAS_PHENOTYPE",
            start="ORPHA:58",
            end="HP:0000256",
            properties={"polarity": "present", "frequency": "Very frequent (99-80%)", "source": "orphadata"},
        )
    ]
    store.load_batch(
        run_id=run_id,
        nodes=nodes,
        edges=edges,
        evidence=[],
        dataset_run_id="fixture",
        previous_run_id=None,
    )
    found = store.get_node("ORPHA:58")
    assert found is not None
    rels = store.disease_phenotypes("ORPHA:58")
    assert rels
    store.rollback_run(run_id)
