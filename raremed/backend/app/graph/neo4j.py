"""Neo4j driver, connectivity probe, and batched parameterized imports."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Iterator

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import Neo4jError

from app.core.config import get_settings
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
from app.graph.schema import CONSTRAINTS, INDEXES
from app.schemas.common import DependencyStatus

logger = logging.getLogger("raremed.neo4j")

BATCH = 500


@lru_cache
def get_driver() -> Driver:
    settings = get_settings()
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        connection_timeout=max(settings.neo4j_timeout_seconds, 5.0),
    )


def probe_neo4j() -> DependencyStatus:
    try:
        driver = get_driver()
        driver.verify_connectivity()
        return DependencyStatus(status="ok", detail=None)
    except (Neo4jError, OSError, TimeoutError) as exc:
        logger.warning("neo4j probe failed", extra={"error_type": exc.__class__.__name__})
        return DependencyStatus(status="unavailable", detail=exc.__class__.__name__)
    except Exception as exc:
        logger.warning("neo4j probe failed", extra={"error_type": exc.__class__.__name__})
        return DependencyStatus(status="unavailable", detail=exc.__class__.__name__)


def reset_driver() -> None:
    get_driver.cache_clear()


class Neo4jGraphStore:
    def __init__(self, driver: Driver | None = None, database: str | None = None) -> None:
        settings = get_settings()
        self.driver = driver or get_driver()
        self.database = database or settings.neo4j_database

    def apply_schema(self) -> None:
        with self.driver.session(database=self.database) as session:
            for statement in CONSTRAINTS + INDEXES:
                session.run(statement)

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
        self.apply_schema()
        self.mark_import(
            run_id,
            "running",
            dataset_run_id=dataset_run_id,
            previous_run_id=previous_run_id,
        )
        for chunk in _chunks(nodes, BATCH):
            self._write_nodes(chunk, run_id)
        by_type: dict[str, list[GraphEdge]] = {}
        for edge in edges:
            by_type.setdefault(edge.type, []).append(edge)
        for rel_type, group in by_type.items():
            for chunk in _chunks(group, BATCH):
                self._write_edges(rel_type, chunk, run_id)
        for chunk in _chunks(evidence, BATCH):
            self._write_evidence(chunk, run_id)
        self.mark_import(
            run_id,
            "succeeded",
            dataset_run_id=dataset_run_id,
            previous_run_id=previous_run_id,
            current=True,
            node_count=len(nodes),
            relationship_count=len(edges),
        )

    def _write_nodes(self, nodes: list[GraphNode], run_id: str) -> None:
        rows = []
        for node in nodes:
            props = {key: _clean(value) for key, value in node.properties.items()}
            props["curie"] = node.curie
            props["kind"] = node.kind
            rows.append({"curie": node.curie, "kind": node.kind, "props": props})
        query = """
        UNWIND $rows AS row
        MERGE (n:Entity {curie: row.curie})
        ON CREATE SET n.created_run_id = $run_id
        SET n += row.props, n.last_seen_run_id = $run_id
        FOREACH (_ IN CASE WHEN row.kind = 'Disease' THEN [1] ELSE [] END | SET n:Disease)
        FOREACH (_ IN CASE WHEN row.kind = 'Phenotype' THEN [1] ELSE [] END | SET n:Phenotype)
        FOREACH (_ IN CASE WHEN row.kind = 'Gene' THEN [1] ELSE [] END | SET n:Gene)
        FOREACH (_ IN CASE WHEN row.kind = 'Variant' THEN [1] ELSE [] END | SET n:Variant)
        FOREACH (_ IN CASE WHEN row.kind = 'InheritancePattern' THEN [1] ELSE [] END | SET n:InheritancePattern)
        FOREACH (_ IN CASE WHEN row.kind = 'DiagnosticTest' THEN [1] ELSE [] END | SET n:DiagnosticTest)
        FOREACH (_ IN CASE WHEN row.kind = 'Identifier' THEN [1] ELSE [] END | SET n:Identifier)
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, rows=rows, run_id=run_id)

    def _write_edges(self, rel_type: str, edges: list[GraphEdge], run_id: str) -> None:
        if rel_type not in {
            "HAS_PHENOTYPE",
            "IS_A",
            "ASSOCIATED_WITH_GENE",
            "HAS_INHERITANCE",
            "INVESTIGATED_BY",
            "XREF",
            "CLASSIFIED_AS",
            "RELATED_DISORDER",
            "ONTOLOGY_EDGE",
        }:
            return
        rows = []
        for edge in edges:
            props = {key: _clean(value) for key, value in edge.properties.items()}
            props["id"] = edge.id
            props["inferred"] = False
            rows.append({"id": edge.id, "start": edge.start, "end": edge.end, "props": props})
        query = f"""
        UNWIND $rows AS row
        MATCH (a:Entity {{curie: row.start}})
        MATCH (b:Entity {{curie: row.end}})
        MERGE (a)-[r:{rel_type} {{id: row.id}}]->(b)
        ON CREATE SET r.created_run_id = $run_id
        SET r += row.props, r.inferred = false, r.last_seen_run_id = $run_id
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, rows=rows, run_id=run_id)

    def _write_evidence(self, items: list[EvidenceRecord], run_id: str) -> None:
        rows = [
            {
                "id": item.id,
                "subject": item.subject,
                "object": item.object,
                "rel_type": item.rel_type,
                "source": item.source,
                "source_file": item.source_file,
                "source_version": item.source_version,
                "source_release_date": item.source_release_date,
                "source_record_id": item.source_record_id,
                "evidence": item.evidence,
                "polarity": item.polarity,
                "frequency": item.frequency,
                "inferred": False,
            }
            for item in items
        ]
        query = """
        UNWIND $rows AS row
        MERGE (e:Evidence {id: row.id})
        ON CREATE SET e.created_run_id = $run_id
        SET e += row, e.last_seen_run_id = $run_id
        WITH e, row
        MERGE (s:Source {key: coalesce(row.source, 'unknown') + '|' + coalesce(row.source_version, '')})
        SET s.name = row.source, s.version = row.source_version, s.release_date = row.source_release_date
        MERGE (e)-[:FROM_SOURCE]->(s)
        WITH e, row
        MATCH (a:Entity {curie: row.subject})
        MERGE (a)-[:SUPPORTED_BY]->(e)
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, rows=rows, run_id=run_id)

    def mark_import(self, run_id: str, status: str, **extra: Any) -> None:
        params = {"run_id": run_id, "status": status, **{key: _clean(value) for key, value in extra.items()}}
        query = """
        MERGE (g:GraphImport {run_id: $run_id})
        SET g.status = $status, g.updated_at = datetime()
        FOREACH (_ IN CASE WHEN $status = 'succeeded' THEN [1] ELSE [] END |
            SET g.current = true
        )
        """
        if extra.get("current"):
            clear = "MATCH (other:GraphImport) WHERE other.run_id <> $run_id SET other.current = false"
        else:
            clear = None
        with self.driver.session(database=self.database) as session:
            if extra.get("dataset_run_id") is not None:
                session.run(
                    "MERGE (g:GraphImport {run_id: $run_id}) SET g.dataset_run_id = $dataset_run_id, "
                    "g.previous_run_id = $previous_run_id, g.node_count = $node_count, "
                    "g.relationship_count = $relationship_count",
                    run_id=run_id,
                    dataset_run_id=extra.get("dataset_run_id"),
                    previous_run_id=extra.get("previous_run_id"),
                    node_count=extra.get("node_count"),
                    relationship_count=extra.get("relationship_count"),
                )
            if clear:
                session.run(clear, run_id=run_id)
            session.run(query, **params)

    def rollback_run(self, run_id: str) -> int:
        query = """
        MATCH ()-[r]-() WHERE r.created_run_id = $run_id DELETE r
        WITH count(*) AS rels
        MATCH (n:Entity) WHERE n.created_run_id = $run_id DETACH DELETE n
        WITH rels, count(*) AS nodes
        MATCH (e:Evidence) WHERE e.created_run_id = $run_id DETACH DELETE e
        WITH rels, nodes, count(*) AS ev
        MATCH (g:GraphImport {run_id: $run_id})
        SET g.status = 'rolled_back', g.current = false
        RETURN rels + nodes + ev AS removed
        """
        with self.driver.session(database=self.database) as session:
            previous = session.run(
                "MATCH (g:GraphImport {run_id: $run_id}) RETURN g.previous_run_id AS prev",
                run_id=run_id,
            ).single()
            result = session.run(query, run_id=run_id).single()
            prev = previous["prev"] if previous else None
            if prev:
                session.run(
                    "MATCH (g:GraphImport {run_id: $prev}) SET g.current = true, g.status = 'succeeded'",
                    prev=prev,
                )
            return int(result["removed"]) if result else 0

    def current_import(self) -> dict[str, Any] | None:
        query = "MATCH (g:GraphImport {current: true}) RETURN g LIMIT 1"
        with self.driver.session(database=self.database) as session:
            row = session.run(query).single()
        if not row:
            return None
        return dict(row["g"])

    def stats(self) -> GraphStats:
        query = """
        OPTIONAL MATCH (n:Entity)
        WITH n.kind AS kind, count(n) AS total
        RETURN collect({kind: kind, total: total}) AS nodes
        """
        rel_query = """
        MATCH ()-[r]->()
        WHERE type(r) IN $types
        RETURN type(r) AS kind, count(r) AS total, sum(CASE WHEN r.inferred THEN 1 ELSE 0 END) AS inferred
        """
        types = [
            "HAS_PHENOTYPE",
            "IS_A",
            "ASSOCIATED_WITH_GENE",
            "HAS_INHERITANCE",
            "INVESTIGATED_BY",
            "XREF",
            "CLASSIFIED_AS",
            "RELATED_DISORDER",
            "ONTOLOGY_EDGE",
        ]
        with self.driver.session(database=self.database) as session:
            node_rows = session.run(query).single()
            rel_rows = list(session.run(rel_query, types=types))
            evidence = session.run("MATCH (e:Evidence) RETURN count(e) AS total").single()
            current = self.current_import()
        node_counts = {
            item["kind"]: item["total"]
            for item in (node_rows["nodes"] if node_rows else [])
            if item.get("kind")
        }
        rel_counts = {item["kind"]: item["total"] for item in rel_rows}
        inferred = sum(int(item["inferred"] or 0) for item in rel_rows)
        return GraphStats(
            loaded=bool(node_counts),
            run_id=current.get("run_id") if current else None,
            dataset_run_id=current.get("dataset_run_id") if current else None,
            node_counts=node_counts,
            relationship_counts=rel_counts,
            evidence_count=int(evidence["total"]) if evidence else 0,
            inferred_relationship_count=inferred,
            note="Version 0.6 explores asserted medical relations from Neo4j. Relations are not invented.",
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
        needle = query.strip()
        if not needle:
            return []
        cypher = """
        MATCH (n:Entity)
        WHERE n.kind IN $kinds
          AND (
            toLower(n.curie) CONTAINS toLower($q)
            OR toLower(coalesce(n.label, '')) CONTAINS toLower($q)
            OR any(syn IN coalesce(n.synonyms, []) WHERE toLower(syn) CONTAINS toLower($q))
          )
          AND ($source IS NULL OR n.source = $source)
          AND ($source_version IS NULL OR n.source_version = $source_version)
        RETURN n.curie AS curie, n.kind AS kind, n.label AS label,
               CASE WHEN toLower(n.curie) = toLower($q) OR toLower(coalesce(n.label,'')) = toLower($q)
                    THEN 1.0 ELSE 0.5 END AS score
        ORDER BY score DESC, n.label
        SKIP $offset
        LIMIT $limit
        """
        with self.driver.session(database=self.database) as session:
            rows = session.run(
                cypher,
                q=needle,
                kinds=kinds,
                limit=limit,
                offset=offset,
                source=source,
                source_version=source_version,
            )
            return [SearchHit(curie=row["curie"], kind=row["kind"], label=row["label"], score=row["score"]) for row in rows]

    def get_node(self, curie: str) -> GraphNode | None:
        with self.driver.session(database=self.database) as session:
            row = session.run("MATCH (n:Entity {curie: $curie}) RETURN n", curie=curie).single()
        if not row:
            return None
        props = dict(row["n"])
        return GraphNode(curie=curie, kind=str(props.get("kind") or "Identifier"), properties=props)

    def disease_phenotypes(
        self,
        curie: str,
        *,
        polarity: str | None = None,
        include_absent: bool = True,
        limit: int = 200,
    ) -> list[GraphEdge]:
        query = """
        MATCH (d:Entity {curie: $curie})-[r:HAS_PHENOTYPE]->(p:Entity)
        WHERE ($polarity IS NULL OR r.polarity = $polarity)
          AND ($include_absent OR r.polarity <> 'absent')
        RETURN r, p.curie AS end
        LIMIT $limit
        """
        with self.driver.session(database=self.database) as session:
            rows = session.run(
                query,
                curie=curie,
                polarity=polarity,
                include_absent=include_absent,
                limit=limit,
            )
            return [_edge_from_rel(row["r"], start=curie, end=row["end"], typ="HAS_PHENOTYPE") for row in rows]

    def neighbors(self, curie: str, *, types: list[str] | None = None, limit: int = 50) -> list[GraphEdge]:
        query = """
        MATCH (n:Entity {curie: $curie})-[r]-(m:Entity)
        WHERE $types IS NULL OR type(r) IN $types
        RETURN r, type(r) AS typ, startNode(r).curie AS start, endNode(r).curie AS end
        LIMIT $limit
        """
        with self.driver.session(database=self.database) as session:
            rows = session.run(query, curie=curie, types=types, limit=limit)
            return [_edge_from_rel(row["r"], start=row["start"], end=row["end"], typ=row["typ"]) for row in rows]

    def neighborhood(
        self,
        curie: str,
        *,
        depth: int = 1,
        limit: int = 40,
        kinds: list[str] | None = None,
        source: str | None = None,
    ) -> Neighborhood | None:
        center = self.get_node(curie)
        if center is None:
            return None
        depth = min(max(depth, 1), 2)
        if depth == 1:
            query = """
            MATCH (n:Entity {curie: $curie})-[r]-(m:Entity)
            WHERE coalesce(r.inferred, false) = false
              AND ($kinds IS NULL OR m.kind IN $kinds)
              AND ($source IS NULL OR r.source = $source OR m.source = $source)
            WITH n, collect(r)[..$cap] AS rels, collect(DISTINCT m)[..$cap] AS others
            RETURN n, rels, others
            """
        else:
            query = """
            MATCH (n:Entity {curie: $curie})-[r1]-(m1:Entity)
            WHERE coalesce(r1.inferred, false) = false
              AND ($kinds IS NULL OR m1.kind IN $kinds)
              AND ($source IS NULL OR r1.source = $source OR m1.source = $source)
            OPTIONAL MATCH (m1)-[r2]-(m2:Entity)
            WHERE coalesce(r2.inferred, false) = false
              AND ($kinds IS NULL OR m2.kind IN $kinds)
              AND ($source IS NULL OR r2.source = $source OR m2.source = $source)
            WITH n, collect(DISTINCT r1) + collect(DISTINCT r2) AS allrels,
                 collect(DISTINCT m1) + collect(DISTINCT m2) AS others
            RETURN n, allrels[..$cap] AS rels, others[..$cap] AS others
            """
        with self.driver.session(database=self.database) as session:
            row = session.run(
                query,
                curie=curie,
                cap=limit + 1,
                kinds=kinds,
                source=source,
            ).single()
        if not row:
            return Neighborhood(center=center, nodes=[center], edges=[], truncated=False)
        nodes = [center]
        seen = {curie}
        for item in row.get("others") or []:
            props = dict(item)
            other_id = str(props.get("curie") or "")
            if other_id and other_id not in seen:
                seen.add(other_id)
                nodes.append(GraphNode(curie=other_id, kind=str(props.get("kind") or "Identifier"), properties=props))
        edges = []
        for rel in row.get("rels") or []:
            start = rel.start_node.get("curie") if hasattr(rel, "start_node") else None
            end = rel.end_node.get("curie") if hasattr(rel, "end_node") else None
            if start and end:
                edges.append(_edge_from_rel(rel, start=start, end=end, typ=rel.type if hasattr(rel, "type") else "RELATED"))
        truncated = len(edges) > limit or len(nodes) > limit + 1
        return Neighborhood(center=center, nodes=nodes[: limit + 1], edges=edges[:limit], truncated=truncated)

    def expand(
        self,
        curie: str,
        *,
        kinds: list[str] | None = None,
        types: list[str] | None = None,
        source: str | None = None,
        limit: int = 24,
    ) -> GraphSlice | None:
        center = self.get_node(curie)
        if center is None:
            return None
        query = """
        MATCH (n:Entity {curie: $curie})-[r]-(m:Entity)
        WHERE coalesce(r.inferred, false) = false
          AND ($kinds IS NULL OR m.kind IN $kinds)
          AND ($types IS NULL OR type(r) IN $types)
          AND ($source IS NULL OR r.source = $source OR m.source = $source)
        RETURN r, type(r) AS typ, startNode(r).curie AS start, endNode(r).curie AS end, m
        LIMIT $cap
        """
        with self.driver.session(database=self.database) as session:
            rows = list(
                session.run(
                    query,
                    curie=curie,
                    kinds=kinds,
                    types=types,
                    source=source,
                    cap=limit + 1,
                )
            )
        truncated = len(rows) > limit
        edges = []
        nodes = [center]
        seen = {curie}
        for row in rows[:limit]:
            edges.append(_edge_from_rel(row["r"], start=row["start"], end=row["end"], typ=row["typ"]))
            props = dict(row["m"])
            other_id = str(props.get("curie") or "")
            if other_id and other_id not in seen:
                seen.add(other_id)
                nodes.append(GraphNode(curie=other_id, kind=str(props.get("kind") or "Identifier"), properties=props))
        return GraphSlice(nodes=nodes, edges=edges, truncated=truncated)

    def path_between(self, start: str, end: str, *, max_hops: int = 4) -> GraphSlice | None:
        if self.get_node(start) is None or self.get_node(end) is None:
            return None
        hops = min(max(max_hops, 1), 4)
        queries = {
            1: """
            MATCH (a:Entity {curie: $start}), (b:Entity {curie: $end})
            MATCH path = shortestPath((a)-[*1..1]-(b))
            WHERE all(r IN relationships(path) WHERE coalesce(r.inferred, false) = false)
            RETURN nodes(path) AS nodes, relationships(path) AS rels
            """,
            2: """
            MATCH (a:Entity {curie: $start}), (b:Entity {curie: $end})
            MATCH path = shortestPath((a)-[*1..2]-(b))
            WHERE all(r IN relationships(path) WHERE coalesce(r.inferred, false) = false)
            RETURN nodes(path) AS nodes, relationships(path) AS rels
            """,
            3: """
            MATCH (a:Entity {curie: $start}), (b:Entity {curie: $end})
            MATCH path = shortestPath((a)-[*1..3]-(b))
            WHERE all(r IN relationships(path) WHERE coalesce(r.inferred, false) = false)
            RETURN nodes(path) AS nodes, relationships(path) AS rels
            """,
            4: """
            MATCH (a:Entity {curie: $start}), (b:Entity {curie: $end})
            MATCH path = shortestPath((a)-[*1..4]-(b))
            WHERE all(r IN relationships(path) WHERE coalesce(r.inferred, false) = false)
            RETURN nodes(path) AS nodes, relationships(path) AS rels
            """,
        }
        with self.driver.session(database=self.database) as session:
            row = session.run(queries[hops], start=start, end=end).single()
        if not row or not row.get("rels"):
            return None
        nodes = []
        for item in row["nodes"] or []:
            props = dict(item)
            curie = str(props.get("curie") or "")
            if curie:
                nodes.append(GraphNode(curie=curie, kind=str(props.get("kind") or "Identifier"), properties=props))
        edges = []
        for rel in row["rels"] or []:
            start_id = rel.start_node.get("curie") if hasattr(rel, "start_node") else None
            end_id = rel.end_node.get("curie") if hasattr(rel, "end_node") else None
            if start_id and end_id:
                edges.append(_edge_from_rel(rel, start=start_id, end=end_id, typ=rel.type if hasattr(rel, "type") else "RELATED"))
        return GraphSlice(nodes=nodes, edges=edges, truncated=False)

    def list_sources(self) -> list[SourceFacet]:
        query = """
        MATCH (n:Entity)
        WHERE n.source IS NOT NULL AND n.source <> ''
        RETURN n.source AS name, n.source_version AS version, count(n) AS total
        ORDER BY total DESC, name
        LIMIT 40
        """
        with self.driver.session(database=self.database) as session:
            return [
                SourceFacet(name=str(row["name"]), version=row["version"], node_count=int(row["total"]))
                for row in session.run(query)
            ]

    def provenance(self, *, curie: str | None = None, evidence_id: str | None = None) -> list[EvidenceRecord]:
        if evidence_id:
            query = "MATCH (e:Evidence {id: $id}) RETURN e"
            params: dict[str, Any] = {"id": evidence_id}
        else:
            query = "MATCH (n:Entity {curie: $curie})-[:SUPPORTED_BY]->(e:Evidence) RETURN e LIMIT 100"
            params = {"curie": curie}
        with self.driver.session(database=self.database) as session:
            rows = session.run(query, **params)
            return [_evidence_from_node(dict(row["e"])) for row in rows]

    def close(self) -> None:
        return None


def _edge_from_rel(rel: Any, *, start: str, end: str, typ: str) -> GraphEdge:
    props = dict(rel)
    return GraphEdge(
        id=str(props.get("id") or f"{typ}|{start}|{end}"),
        type=typ,
        start=start,
        end=end,
        inferred=bool(props.get("inferred")),
        properties=props,
    )


def _evidence_from_node(props: dict[str, Any]) -> EvidenceRecord:
    return EvidenceRecord(
        id=str(props.get("id")),
        subject=str(props.get("subject") or ""),
        object=str(props.get("object") or ""),
        rel_type=str(props.get("rel_type") or ""),
        source=props.get("source"),
        source_file=props.get("source_file"),
        source_version=props.get("source_version"),
        source_release_date=props.get("source_release_date"),
        source_record_id=props.get("source_record_id"),
        evidence=props.get("evidence"),
        polarity=props.get("polarity"),
        frequency=props.get("frequency"),
        inferred=bool(props.get("inferred")),
    )


def _clean(value: Any) -> Any:
    """Neo4j properties accept primitives and arrays of primitives only."""
    if value is None:
        return None
    if isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, dict):
        return json.dumps(
            {str(key): item for key, item in value.items() if item is not None},
            ensure_ascii=False,
            default=str,
        )
    if isinstance(value, list | tuple):
        cleaned = [_clean(item) for item in value]
        if all(item is None or isinstance(item, bool | int | float | str) for item in cleaned):
            return [item for item in cleaned if item is not None]
        return json.dumps(cleaned, ensure_ascii=False, default=str)
    return str(value)


def _chunks(items: list[Any], size: int) -> Iterator[list[Any]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
