from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class SourceKind(str, Enum):
    LOCAL_FILE="local_file"; PROJECT_FILE="project_file"; REPOSITORY="repository"; MANUAL="manual"; API_REFERENCE="api_reference"; WEB="web"

@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    source_kind: SourceKind
    source_uri: str
    version: str
    retrieved_at: datetime
    content_hash: str
    trusted_for_reference: bool = True
    def __post_init__(self):
        if not all((self.document_id.strip(),self.source_uri.strip(),self.version.strip(),self.content_hash.strip())): raise ValueError("document identity, source, version and hash required")
        if self.retrieved_at.tzinfo is None: raise ValueError("retrieved_at must be timezone-aware")

@dataclass(frozen=True)
class KnowledgeFact:
    fact_id: str
    document_id: str
    statement: str
    locator: str
    observed_at: datetime
    supersedes: tuple[str,...]=()
    def __post_init__(self):
        if not all((self.fact_id.strip(),self.document_id.strip(),self.statement.strip(),self.locator.strip())): raise ValueError("fact provenance fields required")
        if self.observed_at.tzinfo is None: raise ValueError("observed_at must be timezone-aware")
