"""Append-only invocation receipt ledger with output digests, not raw payloads."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from .model import ToolReceipt

@dataclass(frozen=True)
class ReceiptRecord:
    invocation_id:str; tool_id:str; version:str; started_at:datetime; finished_at:datetime
    succeeded:bool; output_digest:str|None; error:str|None

def _digest(value:Any)->str|None:
    if value is None: return None
    try: raw=json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode("utf-8")
    except Exception: raw=repr(value).encode("utf-8")
    return sha256(raw).hexdigest()

class JsonlReceiptLedger:
    def __init__(self,path:Path)->None:
        self.path=path; self._records:dict[str,ReceiptRecord]={}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip(): continue
                raw=json.loads(line)
                rec=ReceiptRecord(raw["invocation_id"],raw["tool_id"],raw["version"],
                    datetime.fromisoformat(raw["started_at"]),datetime.fromisoformat(raw["finished_at"]),
                    bool(raw["succeeded"]),raw.get("output_digest"),raw.get("error"))
                self._records[rec.invocation_id]=rec
    def get(self,invocation_id:str)->ReceiptRecord|None: return self._records.get(invocation_id)
    def append(self,receipt:ToolReceipt)->ReceiptRecord:
        if receipt.invocation_id in self._records: raise ValueError("duplicate invocation_id")
        rec=ReceiptRecord(receipt.invocation_id,receipt.tool_id,receipt.version,receipt.started_at,receipt.finished_at,
            receipt.succeeded,_digest(receipt.output),receipt.error)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        raw={"invocation_id":rec.invocation_id,"tool_id":rec.tool_id,"version":rec.version,
             "started_at":rec.started_at.isoformat(),"finished_at":rec.finished_at.isoformat(),
             "succeeded":rec.succeeded,"output_digest":rec.output_digest,"error":rec.error}
        with self.path.open("a",encoding="utf-8") as fh:
            fh.write(json.dumps(raw,sort_keys=True)+"\n"); fh.flush()
        self._records[rec.invocation_id]=rec; return rec
