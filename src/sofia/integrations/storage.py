"""Local storage inspection helpers."""
from __future__ import annotations
from pathlib import Path
import shutil

class StorageAdapter:
    def __init__(self,roots:tuple[Path,...])->None:
        if not roots: raise ValueError("at least one storage root required")
        self.roots=tuple(root.resolve() for root in roots)
    def usage(self)->tuple[dict[str,int|str],...]:
        out=[]
        for root in self.roots:
            usage=shutil.disk_usage(root)
            out.append({"path":str(root),"total_bytes":usage.total,"used_bytes":usage.used,"free_bytes":usage.free})
        return tuple(out)
