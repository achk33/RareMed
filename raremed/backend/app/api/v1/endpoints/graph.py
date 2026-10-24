from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, require_admin, require_staff
from app.core.config import get_settings
from app.core.errors import AppError
from app.graph.jobs import (
    GraphConflictError,
    GraphImportError,
    get_graph_store,
    is_running,
    load_graph,
    rollback_graph,
)
from app.graph.neo4j import probe_neo4j
from app.graph.records import GraphEdge, GraphNode
from app.models import User
from app.schemas.graph import (
    DiseaseDetail,
    EntityDetail,
    GraphEdgeRead,
    GraphEvidenceRead,
    GraphLoadRequest,
    GraphNodeRead,
    GraphSearchHit,
    GraphStatus,
    NeighborhoodRead,
    PhenotypeDetail,
)

router = APIRouter(prefix="/graph", tags=["graph"])

NOTE = (
    "Version 0.6 explores asserted medical relations from Neo4j. "
    "Missing phenotypes are not treated as absent, and relations are not invented."
)


@router.get("/status", response_model=GraphStatus)
def graph_status(_: User = Depends(require_staff)) -> GraphStatus:
    connection = probe_neo4j()
    if connection.status != "ok" and not _memory_loaded():
        return GraphStatus(connection=connection, loaded=False, note=NOTE, running=is_running())
    try:
        stats = get_graph_store().stats()
    except GraphImportError:
        return GraphStatus(connection=connection, loaded=False, note=NOTE, running=is_running())
    return GraphStatus(
        connection=connection,
        loaded=stats.loaded,
        note=stats.note or NOTE,
        run_id=stats.run_id,
        dataset_run_id=stats.dataset_run_id,
        node_counts=stats.node_counts,
        relationship_counts=stats.relationship_counts,
        evidence_count=stats.evidence_count,
        inferred_relationship_count=stats.inferred_relationship_count,
        running=is_running(),
    )


@router.get("/stats", response_model=GraphStatus)
def graph_stats(_: User = Depends(get_current_user)) -> GraphStatus:
    connection = probe_neo4j()
    if connection.status != "ok" and not _memory_loaded():
        return GraphStatus(connection=connection, loaded=False, note=NOTE, running=is_running())
    try:
        stats = get_graph_store().stats()
    except GraphImportError:
        return GraphStatus(connection=connection, loaded=False, note=NOTE, running=is_running())
    return GraphStatus(
        connection=connection,
        loaded=stats.loaded,
        note=stats.note or NOTE,
        run_id=stats.run_id,
        dataset_run_id=stats.dataset_run_id,
        node_counts=stats.node_counts,
        relationship_counts=stats.relationship_counts,
        evidence_count=stats.evidence_count,
        inferred_relationship_count=stats.inferred_relationship_count,
        running=is_running(),
    )


@router.post("/load", response_model=GraphStatus)
def load_operational_graph(
    body: GraphLoadRequest,
    _: User = Depends(require_admin),
) -> GraphStatus:
    try:
        load_graph(get_settings().data_root, dataset_run_id=body.dataset_run_id)
    except GraphConflictError as exc:
        raise AppError("graph_import_running", str(exc), 409) from exc
    except GraphImportError as exc:
        raise AppError("graph_unavailable", str(exc), 503) from exc
    except FileNotFoundError as exc:
        raise AppError("graph_import_missing", str(exc), 400) from exc
    return graph_status(_)


@router.post("/rollback", response_model=GraphStatus)
def rollback_operational_graph(_: User = Depends(require_admin)) -> GraphStatus:
    try:
        rollback_graph()
    except GraphImportError as exc:
        raise AppError("graph_unavailable", str(exc), 503) from exc
    except FileNotFoundError as exc:
        raise AppError("graph_rollback_unavailable", str(exc), 400) from exc
    return graph_status(_)


@router.get("/diseases", response_model=list[GraphSearchHit])
def search_diseases(q: str = Query(min_length=1, max_length=120), _: User = Depends(get_current_user)) -> list[GraphSearchHit]:
    return [_hit(item) for item in _store().search(q, kinds=["Disease"], limit=20)]


@router.get("/phenotypes", response_model=list[GraphSearchHit])
def search_phenotypes(q: str = Query(min_length=1, max_length=120), _: User = Depends(get_current_user)) -> list[GraphSearchHit]:
    return [_hit(item) for item in _store().search(q, kinds=["Phenotype"], limit=20)]


@router.get("/diseases/{curie}", response_model=DiseaseDetail)
def disease_details(curie: str, _: User = Depends(get_current_user)) -> DiseaseDetail:
    store = _store()
    node = store.get_node(curie)
    if node is None or node.kind != "Disease":
        raise AppError("not_found", f"Disease {curie} was not found.", 404)
    return DiseaseDetail(
        disease=_node(node),
        phenotypes=[_edge(item) for item in store.disease_phenotypes(curie, include_absent=True, limit=200)],
        genes=[_edge(item) for item in store.neighbors(curie, types=["ASSOCIATED_WITH_GENE"], limit=50)],
        inheritance=[_edge(item) for item in store.neighbors(curie, types=["HAS_INHERITANCE"], limit=20)],
        tests=[_edge(item) for item in store.neighbors(curie, types=["INVESTIGATED_BY"], limit=20)],
        xrefs=[_edge(item) for item in store.neighbors(curie, types=["XREF"], limit=50)],
    )


@router.get("/phenotypes/{curie}", response_model=PhenotypeDetail)
def phenotype_details(curie: str, _: User = Depends(get_current_user)) -> PhenotypeDetail:
    store = _store()
    node = store.get_node(curie)
    if node is None or node.kind != "Phenotype":
        raise AppError("not_found", f"Phenotype {curie} was not found.", 404)
    incoming = store.neighbors(curie, types=["IS_A", "HAS_PHENOTYPE"], limit=100)
    return PhenotypeDetail(
        phenotype=_node(node),
        parents=[_edge(item) for item in incoming if item.type == "IS_A" and item.start == curie],
        children=[_edge(item) for item in incoming if item.type == "IS_A" and item.end == curie],
        diseases=[_edge(item) for item in incoming if item.type == "HAS_PHENOTYPE"],
    )


@router.get("/diseases/{curie}/phenotypes", response_model=list[GraphEdgeRead])
def disease_phenotype_evidence(
    curie: str,
    polarity: str | None = None,
    include_absent: bool = True,
    _: User = Depends(get_current_user),
) -> list[GraphEdgeRead]:
    store = _store()
    if store.get_node(curie) is None:
        raise AppError("not_found", f"Disease {curie} was not found.", 404)
    return [
        _edge(item)
        for item in store.disease_phenotypes(curie, polarity=polarity, include_absent=include_absent, limit=300)
    ]


@router.get("/neighborhood", response_model=NeighborhoodRead)
def graph_neighborhood(
    curie: str = Query(min_length=3, max_length=80),
    depth: int = Query(default=1, ge=1, le=2),
    limit: int = Query(default=40, ge=1, le=80),
    _: User = Depends(get_current_user),
) -> NeighborhoodRead:
    found = _store().neighborhood(curie, depth=depth, limit=limit)
    if found is None:
        raise AppError("not_found", f"Graph node {curie} was not found.", 404)
    return NeighborhoodRead(
        center=_node(found.center),
        nodes=[_node(item) for item in found.nodes],
        edges=[_edge(item) for item in found.edges],
        depth=depth,
        bounded=True,
        truncated=found.truncated,
        read_only=True,
    )


@router.get("/entities/{curie}", response_model=EntityDetail)
def entity_details(curie: str, _: User = Depends(get_current_user)) -> EntityDetail:
    store = _store()
    node = store.get_node(curie)
    if node is None:
        raise AppError("not_found", f"Graph node {curie} was not found.", 404)
    return EntityDetail(
        entity=_node(node),
        relationships=[_edge(item) for item in store.neighbors(curie, limit=40) if not item.inferred],
        evidence=[
            GraphEvidenceRead(
                id=item.id,
                subject=item.subject,
                object=item.object,
                rel_type=item.rel_type,
                inferred=item.inferred,
                source=item.source,
                source_file=item.source_file,
                source_version=item.source_version,
                source_release_date=item.source_release_date,
                source_record_id=item.source_record_id,
                evidence=item.evidence,
                polarity=item.polarity,
                frequency=item.frequency,
            )
            for item in store.provenance(curie=curie)
        ],
        read_only=True,
    )


@router.get("/provenance", response_model=list[GraphEvidenceRead])
def graph_provenance(
    curie: str | None = None,
    evidence_id: str | None = None,
    _: User = Depends(get_current_user),
) -> list[GraphEvidenceRead]:
    if not curie and not evidence_id:
        raise AppError("validation_error", "Provide a curie or evidence_id.", 422)
    return [
        GraphEvidenceRead(
            id=item.id,
            subject=item.subject,
            object=item.object,
            rel_type=item.rel_type,
            inferred=item.inferred,
            source=item.source,
            source_file=item.source_file,
            source_version=item.source_version,
            source_release_date=item.source_release_date,
            source_record_id=item.source_record_id,
            evidence=item.evidence,
            polarity=item.polarity,
            frequency=item.frequency,
        )
        for item in _store().provenance(curie=curie, evidence_id=evidence_id)
    ]


def _store():
    try:
        return get_graph_store()
    except GraphImportError as exc:
        raise AppError("graph_unavailable", str(exc), 503) from exc


def _memory_loaded() -> bool:
    from app.graph import jobs

    return jobs._USE_MEMORY and bool(jobs._MEMORY.nodes)


def _node(node: GraphNode) -> GraphNodeRead:
    props = node.properties
    return GraphNodeRead(
        curie=node.curie,
        kind=node.kind,
        label=props.get("label"),
        definition=props.get("definition"),
        synonyms=list(props.get("synonyms") or []),
        namespace=props.get("namespace"),
        source=props.get("source"),
        source_version=props.get("source_version"),
        obsolete=bool(props.get("obsolete")),
        properties=props,
    )


def _edge(edge: GraphEdge) -> GraphEdgeRead:
    props = edge.properties
    return GraphEdgeRead(
        id=edge.id,
        type=edge.type,
        start=edge.start,
        end=edge.end,
        inferred=edge.inferred,
        polarity=props.get("polarity"),
        frequency=props.get("frequency"),
        frequency_normalized=props.get("frequency_normalized"),
        evidence=props.get("evidence"),
        source=props.get("source"),
        source_file=props.get("source_file"),
        source_version=props.get("source_version"),
        source_record_id=props.get("source_record_id"),
        properties=props,
    )


def _hit(item) -> GraphSearchHit:
    return GraphSearchHit(curie=item.curie, kind=item.kind, label=item.label, score=item.score)
