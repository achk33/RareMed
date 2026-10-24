"""Normalize medical identifiers without dropping the source-specific form."""

from __future__ import annotations

import re
from dataclasses import dataclass

PURL_OBO = re.compile(
    r"^https?://purl\.obolibrary\.org/obo/([A-Za-z][A-Za-z0-9]+)_([A-Za-z0-9][A-Za-z0-9.-]*)$",
    re.IGNORECASE,
)
ORPHANET_EXP = re.compile(
    r"^https?://www\.orpha\.net/(?:consor/cgi-bin/OC_Exp\.php\?(?:lng=[^&]+&)?Expert=|ORDO/Orphanet_)(\d+)",
    re.IGNORECASE,
)
CURIE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9._-]*):(.+)$")
UNDERSCORE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]+)_([A-Za-z0-9][A-Za-z0-9.-]*)$")

NAMESPACE_ALIASES = {
    "HP": "HP",
    "HPO": "HP",
    "MONDO": "MONDO",
    "ORPHA": "ORPHA",
    "ORPHANET": "ORPHA",
    "ORPHACODE": "ORPHA",
    "ORDO": "ORPHA",
    "OMIM": "OMIM",
    "MIM": "OMIM",
    "ICD-10": "ICD-10",
    "ICD10": "ICD-10",
    "ICD10CM": "ICD-10",
    "ICD-11": "ICD-11",
    "ICD11": "ICD-11",
    "UMLS": "UMLS",
    "MESH": "MESH",
    "DOID": "DOID",
    "NCIT": "NCIT",
    "SNOMEDCT": "SNOMEDCT",
    "SNOMEDCT_US": "SNOMEDCT",
    "SNOMED": "SNOMEDCT",
    "MEDDRA": "MEDDRA",
    "UMLS_CUI": "UMLS",
    "HGNC": "HGNC",
    "ENSEMBL": "ENSEMBL",
    "GENCC": "GENCC",
    "ORPHA-INH": "ORPHA-INH",
    "INH": "ORPHA-INH",
}

DISEASE_NAMESPACES = frozenset({"ORPHA", "MONDO", "OMIM", "DOID"})
PHENOTYPE_NAMESPACES = frozenset({"HP"})
STUB_NAMESPACES = frozenset(
    {"ICD-10", "ICD-11", "UMLS", "MESH", "NCIT", "SNOMEDCT", "MEDDRA", "HGNC", "ENSEMBL", "GENCC"}
)


@dataclass(frozen=True)
class Identifier:
    namespace: str
    local_id: str
    curie: str
    original: str
    iri: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.namespace, self.local_id)


def canonical_namespace(raw: str) -> str | None:
    token = raw.strip()
    if not token:
        return None
    return NAMESPACE_ALIASES.get(token.upper()) or NAMESPACE_ALIASES.get(token)


def parse_identifier(raw: str, *, default_namespace: str | None = None) -> Identifier | None:
    text = (raw or "").strip()
    if not text:
        return None

    iri: str | None = None
    if text.startswith(("http://", "https://")):
        iri = text
        match = PURL_OBO.match(text)
        if match:
            return _build(match.group(1), match.group(2), original=raw, iri=iri)
        orphan = ORPHANET_EXP.match(text)
        if orphan:
            return _build("ORPHA", orphan.group(1), original=raw, iri=iri)
        return None

    curie = CURIE_RE.match(text)
    if curie:
        return _build(curie.group(1), curie.group(2).strip(), original=raw, iri=iri)

    underscore = UNDERSCORE_RE.match(text)
    if underscore and canonical_namespace(underscore.group(1)):
        return _build(underscore.group(1), underscore.group(2), original=raw, iri=iri)

    if default_namespace:
        namespace = canonical_namespace(default_namespace)
        if namespace:
            return _build(namespace, text, original=raw, iri=iri)
    return None


def _build(namespace: str, local_id: str, *, original: str, iri: str | None) -> Identifier | None:
    resolved = canonical_namespace(namespace)
    local = local_id.strip()
    if not resolved or not local:
        return None
    if local.upper().startswith(f"{resolved}:"):
        local = local.split(":", 1)[1].strip()
    if not local:
        return None
    return Identifier(
        namespace=resolved,
        local_id=local,
        curie=f"{resolved}:{local}",
        original=original,
        iri=iri or _iri_for(resolved, local),
    )


def _iri_for(namespace: str, local_id: str) -> str | None:
    if namespace in {"HP", "MONDO", "DOID"}:
        return f"http://purl.obolibrary.org/obo/{namespace}_{local_id}"
    if namespace == "ORPHA":
        return f"http://www.orpha.net/ORDO/Orphanet_{local_id}"
    return None


def entity_type_for(identifier: Identifier) -> str:
    if identifier.namespace in PHENOTYPE_NAMESPACES:
        return "phenotype"
    if identifier.namespace in DISEASE_NAMESPACES:
        return "disease"
    return "identifier"
