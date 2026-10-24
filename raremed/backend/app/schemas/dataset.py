from pydantic import BaseModel, Field


class DiscoveredFile(BaseModel):
    name: str
    relative_path: str
    size_bytes: int
    suffix: str


class SourceDiscovery(BaseModel):
    source: str
    relative_directory: str
    present: bool
    file_count: int
    truncated: bool
    files: list[DiscoveredFile]


class ReservedDirectory(BaseModel):
    name: str
    present: bool
    purpose: str


class DiscoveryReport(BaseModel):
    readable: bool
    note: str
    sources: list[SourceDiscovery]
    sample_files: list[str]
    reserved_directories: list[ReservedDirectory]


class UiFixture(BaseModel):
    id: str
    locale: str
    text: str
    notice: str


class SampleList(BaseModel):
    fixtures: list[UiFixture] = Field(default_factory=list)
    note: str
