"""Text extraction for local PDF reference sources."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path

from .model import KnowledgeDocument,SourceKind

@dataclass(frozen=True)
class PdfPageText:
    page_number:int
    text:str

def ingest_pdf(path:Path,*,document_id:str,version:str="local",max_pages:int=500):
    resolved=path.resolve(strict=True)
    if resolved.suffix.lower()!=".pdf": raise ValueError("source must be a PDF")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF ingestion requires the optional 'pypdf' package") from exc
    reader=PdfReader(resolved,strict=False)
    if len(reader.pages)>max_pages: raise ValueError("PDF page limit exceeded")
    pages=tuple(PdfPageText(i+1,page.extract_text() or "") for i,page in enumerate(reader.pages))
    document=KnowledgeDocument(
        document_id,SourceKind.MANUAL,resolved.as_uri(),version,
        datetime.now(timezone.utc),sha256(resolved.read_bytes()).hexdigest(),True,
    )
    return document,pages
