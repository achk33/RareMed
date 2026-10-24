from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import DependencyStatus


class GraphStatus(BaseModel):
    connection: DependencyStatus
    loaded: bool
    note: str
    run_id: str | None = None
    dataset_run_id: str | None = None
    node_counts: dict[str, int] = Field(default_factory=dict)
    relationship_counts: dict[str, int] = Field(default_factory=dict)
    evidence_count: int = 0
    inferred_relationship_count: int = 0
    running: bool = False


class GraphLoadRequest(BaseModel):
    dataset_run_id: str | None = None


class GraphSearchHit(BaseModel):
    curie: str
    kind: str
    label: str | None
    score: float


class GraphNodeRead(BaseModel):
    curie: str
    kind: str
    label: str | None = None
    definition: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    namespace: str | None = None
    source: str | None = None
    source_version: str | None = None
    obsolete: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeRead(BaseModel):
    id: str
    type: str
    start: str
    end: str
    inferred: bool = False
    polarity: str | None = None
    frequency: str | None = None
    frequency_normalized: str | None = None
    evidence: str | None = None
    source: str | None = None
    source_file: str | None = None
    source_version: str | None = None
    source_record_id: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEvidenceRead(BaseModel):
    id: str
    subject: str
    object: str
    rel_type: str
    inferred: bool = False
    source: str | None = None
    source_file: str | None = None
    source_version: str | None = None
    source_release_date: str | None = None
    source_record_id: str | None = None
    evidence: str | None = None
    polarity: str | None = None
    frequency: str | None = None


class DiseaseDetail(BaseModel):
    disease: GraphNodeRead
    phenotypes: list[GraphEdgeRead] = Field(default_factory=list)
    genes: list[GraphEdgeRead] = Field(default_factory=list)
    inheritance: list[GraphEdgeRead] = Field(default_factory=list)
    tests: list[GraphEdgeRead] = Field(default_factory=list)
    xrefs: list[GraphEdgeRead] = Field(default_factory=list)


class PhenotypeDetail(BaseModel):
    phenotype: GraphNodeRead
    parents: list[GraphEdgeRead] = Field(default_factory=list)
    children: list[GraphEdgeRead] = Field(default_factory=list)
    diseases: list[GraphEdgeRead] = Field(default_factory=list)


class NeighborhoodRead(BaseModel):
    center: GraphNodeRead
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]
    depth: int
    bounded: bool = True
    truncated: bool = False
    read_only: bool = True


class GraphSearchPage(BaseModel):
    items: list[GraphSearchHit]
    offset: int
    limit: int
    has_more: bool


class GraphSliceRead(BaseModel):
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]
    truncated: bool = False
    read_only: bool = True


class SourceFacetRead(BaseModel):
    name: str
    version: str | None = None
    node_count: int


class EntityDetail(BaseModel):
    entity: GraphNodeRead
    relationships: list[GraphEdgeRead] = Field(default_factory=list)
    evidence: list[GraphEvidenceRead] = Field(default_factory=list)
    read_only: bool = True
