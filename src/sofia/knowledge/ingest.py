from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from .model import KnowledgeDocument,SourceKind

def ingest_local_file(path:Path,*,document_id:str,version:str="local")->tuple[KnowledgeDocument,str]:
    resolved=path.resolve(strict=True)
    if not resolved.is_file(): raise ValueError("knowledge source must be a file")
    raw=resolved.read_bytes(); text=raw.decode("utf-8")
    doc=KnowledgeDocument(document_id,SourceKind.LOCAL_FILE,resolved.as_uri(),version,datetime.now(timezone.utc),sha256(raw).hexdigest(),True)
    return doc,text
