"""Graph store protocol shared by Neo4j and the in-memory test store."""

from __future__ import annotations

from typing import Any, Protocol

from app.graph.records import EvidenceRecord, GraphEdge, GraphNode, GraphSlice, GraphStats, Neighborhood, SearchHit, SourceFacet


class GraphStore(Protocol):
    def apply_schema(self) -> None: ...

    def load_batch(
        self,
        *,
        run_id: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        evidence: list[EvidenceRecord],
        dataset_run_id: str | None,
        previous_run_id: str | None,
    ) -> None: ...

    def mark_import(self, run_id: str, status: str, **extra: Any) -> None: ...

    def rollback_run(self, run_id: str) -> int: ...

    def current_import(self) -> dict[str, Any] | None: ...

    def stats(self) -> GraphStats: ...

    def search(
        self,
        query: str,
        *,
        kinds: list[str],
        limit: int = 20,
        offset: int = 0,
        source: str | None = None,
        source_version: str | None = None,
    ) -> list[SearchHit]: ...

    def get_node(self, curie: str) -> GraphNode | None: ...

    def disease_phenotypes(
        self,
        curie: str,
        *,
        polarity: str | None = None,
        include_absent: bool = True,
        limit: int = 200,
    ) -> list[GraphEdge]: ...

    def neighbors(self, curie: str, *, types: list[str] | None = None, limit: int = 50) -> list[GraphEdge]: ...

    def neighborhood(
        self,
        curie: str,
        *,
        depth: int = 1,
        limit: int = 40,
        kinds: list[str] | None = None,
        source: str | None = None,
    ) -> Neighborhood | None: ...

    def expand(
        self,
        curie: str,
        *,
        kinds: list[str] | None = None,
        types: list[str] | None = None,
        source: str | None = None,
        limit: int = 24,
    ) -> GraphSlice | None: ...

    def path_between(self, start: str, end: str, *, max_hops: int = 4) -> GraphSlice | None: ...

    def list_sources(self) -> list[SourceFacet]: ...

    def provenance(self, *, curie: str | None = None, evidence_id: str | None = None) -> list[EvidenceRecord]: ...

    def close(self) -> None: ...
