"""Repository-file ingestion with root confinement and revision provenance."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from .model import KnowledgeDocument,SourceKind

class RepositoryIngestError(RuntimeError): pass

def ingest_repository_file(repo_root:Path,relative_path:str,*,document_id:str,revision:str)->tuple[KnowledgeDocument,str]:
    root=repo_root.resolve(strict=True)
    candidate=(root/relative_path).resolve(strict=True)
    try: candidate.relative_to(root)
    except ValueError as exc: raise RepositoryIngestError("repository source escapes root") from exc
    if not candidate.is_file(): raise RepositoryIngestError("repository source must be a file")
    if not revision.strip(): raise ValueError("revision required")
    raw=candidate.read_bytes()
    try: text=raw.decode("utf-8")
    except UnicodeDecodeError as exc: raise RepositoryIngestError("repository text source must be UTF-8") from exc
    doc=KnowledgeDocument(document_id,SourceKind.REPOSITORY,candidate.as_uri(),revision,
        datetime.now(timezone.utc),sha256(raw).hexdigest(),True)
    return doc,text
