"""Staff-only bounded graph explorer. Read-only. Never returns the full graph."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_staff
from app.api.v1.endpoints.graph import _edge, _hit, _node, _store
from app.core.errors import AppError
from app.models import User
from app.schemas.graph import (
    GraphSearchPage,
    GraphSliceRead,
    NeighborhoodRead,
    SourceFacetRead,
)

router = APIRouter(prefix="/graph/explore", tags=["graph-explorer"])

ALLOWED_KINDS = {"Disease", "Phenotype", "Gene", "InheritancePattern", "Variant", "DiagnosticTest", "Identifier"}
MAX_SEARCH = 20
MAX_NEIGHBORHOOD = 80
MAX_EXPAND = 24


@router.get("/search", response_model=GraphSearchPage)
def explore_search(
    q: str = Query(min_length=1, max_length=120),
    kinds: str | None = None,
    source: str | None = None,
    source_version: str | None = None,
    offset: int = Query(default=0, ge=0, le=2000),
    limit: int = Query(default=12, ge=1, le=MAX_SEARCH),
    _: User = Depends(require_staff),
) -> GraphSearchPage:
    selected = _kinds(kinds)
    rows = _store().search(
        q,
        kinds=selected,
        limit=limit + 1,
        offset=offset,
        source=source,
        source_version=source_version,
    )
    return GraphSearchPage(
        items=[_hit(item) for item in rows[:limit]],
        offset=offset,
        limit=limit,
        has_more=len(rows) > limit,
    )


@router.get("/neighborhood", response_model=NeighborhoodRead)
def explore_neighborhood(
    curie: str = Query(min_length=3, max_length=80),
    depth: int = Query(default=1, ge=1, le=2),
    limit: int = Query(default=40, ge=1, le=MAX_NEIGHBORHOOD),
    kinds: str | None = None,
    source: str | None = None,
    _: User = Depends(require_staff),
) -> NeighborhoodRead:
    found = _store().neighborhood(curie, depth=depth, limit=limit, kinds=_kinds(kinds), source=source)
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


@router.get("/expand", response_model=GraphSliceRead)
def explore_expand(
    curie: str = Query(min_length=3, max_length=80),
    limit: int = Query(default=16, ge=1, le=MAX_EXPAND),
    kinds: str | None = None,
    types: str | None = None,
    source: str | None = None,
    _: User = Depends(require_staff),
) -> GraphSliceRead:
    found = _store().expand(curie, kinds=_kinds(kinds), types=_types(types), source=source, limit=limit)
    if found is None:
        raise AppError("not_found", f"Graph node {curie} was not found.", 404)
    return GraphSliceRead(
        nodes=[_node(item) for item in found.nodes],
        edges=[_edge(item) for item in found.edges],
        truncated=found.truncated,
        read_only=True,
    )


@router.get("/path", response_model=GraphSliceRead)
def explore_path(
    start: str = Query(min_length=3, max_length=80),
    end: str = Query(min_length=3, max_length=80),
    max_hops: int = Query(default=4, ge=1, le=4),
    _: User = Depends(require_staff),
) -> GraphSliceRead:
    found = _store().path_between(start, end, max_hops=max_hops)
    if found is None:
        raise AppError("not_found", "No asserted path exists between those identifiers.", 404)
    return GraphSliceRead(
        nodes=[_node(item) for item in found.nodes],
        edges=[_edge(item) for item in found.edges],
        truncated=False,
        read_only=True,
    )


@router.get("/sources", response_model=list[SourceFacetRead])
def explore_sources(_: User = Depends(require_staff)) -> list[SourceFacetRead]:
    return [
        SourceFacetRead(name=item.name, version=item.version, node_count=item.node_count)
        for item in _store().list_sources()
    ]


def _kinds(raw: str | None) -> list[str]:
    if not raw:
        return ["Disease", "Phenotype", "Gene", "InheritancePattern"]
    selected = [item.strip() for item in raw.split(",") if item.strip() in ALLOWED_KINDS]
    return selected or ["Disease", "Phenotype", "Gene", "InheritancePattern"]


def _types(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [item.strip().upper() for item in raw.split(",") if item.strip()]
