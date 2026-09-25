"""Root-confined documentation writer with optimistic concurrency checks."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

@dataclass(frozen=True)
class DocumentationWriteReceipt:
    path:str
    before_sha256:str|None
    after_sha256:str

class DocumentationWriter:
    def __init__(self,root:Path)->None:
        self.root=root.resolve()

    def _target(self,relative_path:str)->Path:
        if not isinstance(relative_path,str) or not relative_path.strip():
            raise ValueError("relative_path is required")
        candidate=(self.root/relative_path).resolve()
        try: candidate.relative_to(self.root)
        except ValueError as exc: raise PermissionError("documentation path escapes authorized root") from exc
        return candidate

    def write(
        self,
        relative_path:str,
        content:str,
        *,
        authorized:bool,
        expected_sha256:str|None=None,
    )->DocumentationWriteReceipt:
        if not authorized: raise PermissionError("documentation write requires host authorization")
        if not isinstance(content,str): raise TypeError("documentation content must be text")
        target=self._target(relative_path)
        before=None
        if target.exists():
            if not target.is_file(): raise ValueError("documentation target must be a file")
            before=sha256(target.read_bytes()).hexdigest()
            if expected_sha256 is not None and before!=expected_sha256:
                raise RuntimeError("documentation changed since review")
        elif expected_sha256 is not None:
            raise RuntimeError("expected existing documentation source is missing")
        target.parent.mkdir(parents=True,exist_ok=True)
        data=content.encode("utf-8")
        tmp=target.with_suffix(target.suffix+".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
        after=sha256(data).hexdigest()
        return DocumentationWriteReceipt(str(target.relative_to(self.root)),before,after)
