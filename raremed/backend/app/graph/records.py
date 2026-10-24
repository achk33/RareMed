"""Typed graph records used by the in-memory and Neo4j stores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    curie: str
    kind: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    id: str
    type: str
    start: str
    end: str
    inferred: bool = False
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceRecord:
    id: str
    subject: str
    object: str
    rel_type: str
    source: str | None = None
    source_file: str | None = None
    source_version: str | None = None
    source_release_date: str | None = None
    source_record_id: str | None = None
    evidence: str | None = None
    polarity: str | None = None
    frequency: str | None = None
    inferred: bool = False


@dataclass
class SearchHit:
    curie: str
    kind: str
    label: str | None
    score: float


@dataclass
class Neighborhood:
    center: GraphNode
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool = False


@dataclass
class GraphSlice:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool = False


@dataclass
class SourceFacet:
    name: str
    version: str | None
    node_count: int


@dataclass
class GraphStats:
    loaded: bool
    run_id: str | None
    dataset_run_id: str | None
    node_counts: dict[str, int]
    relationship_counts: dict[str, int]
    evidence_count: int
    inferred_relationship_count: int
    note: str
