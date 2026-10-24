"""In-memory graph used by tests and when Neo4j is not required."""

from __future__ import annotations

from typing import Any

from app.graph.records import (
    EvidenceRecord,
    GraphEdge,
    GraphNode,
    GraphSlice,
    GraphStats,
    Neighborhood,
    SearchHit,
    SourceFacet,
)


class InMemoryGraphStore:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}
        self.evidence: dict[str, EvidenceRecord] = {}
        self.imports: dict[str, dict[str, Any]] = {}
        self._current: str | None = None

    def apply_schema(self) -> None:
        return None

    def load_batch(
        self,
        *,
        run_id: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        evidence: list[EvidenceRecord],
        dataset_run_id: str | None,
        previous_run_id: str | None,
    ) -> None:
        for node in nodes:
            existing = self.nodes.get(node.curie)
            if existing and existing.kind != node.kind:
                raise ValueError(f"Refusing to merge distinct concepts {node.curie}: {existing.kind} vs {node.kind}")
            props = {**(existing.properties if existing else {}), **node.properties}
            props["created_run_id"] = props.get("created_run_id") or run_id
            props["last_seen_run_id"] = run_id
            self.nodes[node.curie] = GraphNode(curie=node.curie, kind=node.kind, properties=props)
        skipped = 0
        for edge in edges:
            if edge.start not in self.nodes or edge.end not in self.nodes:
                skipped += 1
                continue
            props = {**edge.properties, "last_seen_run_id": run_id}
            props.setdefault("created_run_id", run_id)
            self.edges[edge.id] = GraphEdge(
                id=edge.id,
                type=edge.type,
                start=edge.start,
                end=edge.end,
                inferred=bool(edge.inferred),
                properties=props,
            )
        for item in evidence:
            self.evidence[item.id] = item
        self.imports[run_id] = {
            "run_id": run_id,
            "status": "succeeded",
            "dataset_run_id": dataset_run_id,
            "previous_run_id": previous_run_id,
            "skipped_edges": skipped,
            "current": True,
        }
        if self._current and self._current in self.imports:
            self.imports[self._current]["current"] = False
        self._current = run_id

    def mark_import(self, run_id: str, status: str, **extra: Any) -> None:
        row = self.imports.setdefault(run_id, {"run_id": run_id})
        row["status"] = status
        row.update(extra)

    def rollback_run(self, run_id: str) -> int:
        removed = 0
        for key in [item for item, edge in self.edges.items() if edge.properties.get("created_run_id") == run_id]:
            del self.edges[key]
            removed += 1
        for key in [item for item, node in self.nodes.items() if node.properties.get("created_run_id") == run_id]:
            del self.nodes[key]
            removed += 1
        stale = [key for key in self.evidence if key not in self.edges]
        for key in stale:
            del self.evidence[key]
            removed += 1
        if run_id in self.imports:
            self.imports[run_id]["status"] = "rolled_back"
            self.imports[run_id]["current"] = False
        previous = self.imports.get(run_id, {}).get("previous_run_id")
        self._current = previous if previous in self.imports else None
        if self._current:
            self.imports[self._current]["current"] = True
        return removed

    def current_import(self) -> dict[str, Any] | None:
        if not self._current:
            return None
        return self.imports.get(self._current)

    def stats(self) -> GraphStats:
        node_counts: dict[str, int] = {}
        for node in self.nodes.values():
            node_counts[node.kind] = node_counts.get(node.kind, 0) + 1
        rel_counts: dict[str, int] = {}
        inferred = 0
        for edge in self.edges.values():
            rel_counts[edge.type] = rel_counts.get(edge.type, 0) + 1
            if edge.inferred:
                inferred += 1
        current = self.current_import()
        return GraphStats(
            loaded=bool(self.nodes),
            run_id=current.get("run_id") if current else None,
            dataset_run_id=current.get("dataset_run_id") if current else None,
            node_counts=node_counts,
            relationship_counts=rel_counts,
            evidence_count=len(self.evidence),
            inferred_relationship_count=inferred,
            note="In-memory operational graph for tests.",
        )

    def search(
        self,
        query: str,
        *,
        kinds: list[str],
        limit: int = 20,
        offset: int = 0,
        source: str | None = None,
        source_version: str | None = None,
    ) -> list[SearchHit]:
        needle = query.strip().lower()
        if not needle:
            return []
        hits: list[SearchHit] = []
        for node in self.nodes.values():
            if kinds and node.kind not in kinds:
                continue
            if source and str(node.properties.get("source") or "") != source:
                continue
            if source_version and str(node.properties.get("source_version") or "") != source_version:
                continue
            label = str(node.properties.get("label") or "")
            synonyms = node.properties.get("synonyms") or []
            haystacks = [node.curie.lower(), label.lower(), *[str(item).lower() for item in synonyms]]
            if any(needle in item for item in haystacks):
                score = 1.0 if needle == node.curie.lower() or needle == label.lower() else 0.5
                hits.append(SearchHit(curie=node.curie, kind=node.kind, label=label or None, score=score))
        hits.sort(key=lambda item: (-item.score, item.label or item.curie))
        return hits[offset : offset + limit]

    def get_node(self, curie: str) -> GraphNode | None:
        return self.nodes.get(curie)

    def disease_phenotypes(
        self,
        curie: str,
        *,
        polarity: str | None = None,
        include_absent: bool = True,
        limit: int = 200,
    ) -> list[GraphEdge]:
        rows = [edge for edge in self.edges.values() if edge.type == "HAS_PHENOTYPE" and edge.start == curie]
        if polarity:
            rows = [edge for edge in rows if edge.properties.get("polarity") == polarity]
        elif not include_absent:
            rows = [edge for edge in rows if edge.properties.get("polarity") != "absent"]
        return rows[:limit]

    def neighbors(self, curie: str, *, types: list[str] | None = None, limit: int = 50) -> list[GraphEdge]:
        rows = [edge for edge in self.edges.values() if edge.start == curie or edge.end == curie]
        if types:
            allowed = set(types)
            rows = [edge for edge in rows if edge.type in allowed]
        return rows[:limit]

    def neighborhood(
        self,
        curie: str,
        *,
        depth: int = 1,
        limit: int = 40,
        kinds: list[str] | None = None,
        source: str | None = None,
    ) -> Neighborhood | None:
        center = self.nodes.get(curie)
        if center is None:
            return None
        depth = min(max(depth, 1), 2)
        allowed = set(kinds or [])
        seen = {curie}
        frontier = {curie}
        collected: list[GraphEdge] = []
        truncated = False
        for _ in range(depth):
            nxt: set[str] = set()
            for edge in self.edges.values():
                if edge.inferred:
                    continue
                if edge.start not in frontier and edge.end not in frontier:
                    continue
                other = edge.end if edge.start in frontier else edge.start
                node = self.nodes.get(other)
                if node is None:
                    continue
                if allowed and node.kind not in allowed and other != curie:
                    continue
                if source and str(edge.properties.get("source") or node.properties.get("source") or "") != source:
                    continue
                if edge.id in {item.id for item in collected}:
                    continue
                if len(collected) >= limit:
                    truncated = True
                    break
                collected.append(edge)
                nxt.add(edge.start)
                nxt.add(edge.end)
            seen.update(nxt)
            frontier = nxt - {curie}
            if truncated:
                break
        nodes = [self.nodes[item] for item in seen if item in self.nodes]
        return Neighborhood(center=center, nodes=nodes, edges=collected, truncated=truncated)

    def expand(
        self,
        curie: str,
        *,
        kinds: list[str] | None = None,
        types: list[str] | None = None,
        source: str | None = None,
        limit: int = 24,
    ) -> GraphSlice | None:
        if curie not in self.nodes:
            return None
        allowed_kinds = set(kinds or [])
        allowed_types = set(types or [])
        edges: list[GraphEdge] = []
        truncated = False
        for edge in self.edges.values():
            if edge.inferred:
                continue
            if edge.start != curie and edge.end != curie:
                continue
            if allowed_types and edge.type not in allowed_types:
                continue
            other = edge.end if edge.start == curie else edge.start
            node = self.nodes.get(other)
            if node is None:
                continue
            if allowed_kinds and node.kind not in allowed_kinds:
                continue
            if source and str(edge.properties.get("source") or node.properties.get("source") or "") != source:
                continue
            if len(edges) >= limit:
                truncated = True
                break
            edges.append(edge)
        nodes = [self.nodes[curie]]
        seen = {curie}
        for edge in edges:
            for item in (edge.start, edge.end):
                if item not in seen and item in self.nodes:
                    seen.add(item)
                    nodes.append(self.nodes[item])
        return GraphSlice(nodes=nodes, edges=edges, truncated=truncated)

    def path_between(self, start: str, end: str, *, max_hops: int = 4) -> GraphSlice | None:
        if start not in self.nodes or end not in self.nodes:
            return None
        max_hops = min(max(max_hops, 1), 4)
        queue: list[tuple[str, list[GraphEdge]]] = [(start, [])]
        visited = {start}
        while queue:
            current, trail = queue.pop(0)
            if current == end:
                nodes = []
                seen: set[str] = set()
                for edge in trail:
                    for curie in (edge.start, edge.end):
                        if curie not in seen and curie in self.nodes:
                            seen.add(curie)
                            nodes.append(self.nodes[curie])
                return GraphSlice(nodes=nodes, edges=trail, truncated=False)
            if len(trail) >= max_hops:
                continue
            for edge in self.edges.values():
                if edge.inferred:
                    continue
                nxt = edge.end if edge.start == current else edge.start if edge.end == current else None
                if nxt is None or nxt in visited:
                    continue
                visited.add(nxt)
                queue.append((nxt, [*trail, edge]))
        return None

    def list_sources(self) -> list[SourceFacet]:
        counts: dict[tuple[str, str | None], int] = {}
        for node in self.nodes.values():
            name = str(node.properties.get("source") or "").strip()
            if not name:
                continue
            version = node.properties.get("source_version")
            key = (name, str(version) if version else None)
            counts[key] = counts.get(key, 0) + 1
        return [
            SourceFacet(name=name, version=version, node_count=total)
            for (name, version), total in sorted(counts.items(), key=lambda item: (-item[1], item[0][0]))
        ]

    def provenance(self, *, curie: str | None = None, evidence_id: str | None = None) -> list[EvidenceRecord]:
        if evidence_id:
            item = self.evidence.get(evidence_id)
            return [item] if item else []
        if curie:
            return [item for item in self.evidence.values() if item.subject == curie or item.object == curie][:100]
        return list(self.evidence.values())[:100]

    def close(self) -> None:
        return None
