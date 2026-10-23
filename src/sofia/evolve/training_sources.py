"""Owner-reviewed public training dataset intake; never raw private conversations.

A source-inspection receipt is not permission to train or deploy weights.
Reviewed JSONL remains at its original owner-selected path, not in sofia.db.
"""
from __future__ import annotations
from contextlib import closing
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import os
import json,re
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.platform.state.path_policy import inside_git_worktree

TRAINING_METHODS={
    "modelfile_prompt":{"weights_modified":False,"dataset_required":False,
        "cost":"low, no training","output":"reviewed prompt configuration",
        "limit":"cannot learn new weights","may_deploy":False},
    "lora_qlora":{"weights_modified":True,"dataset_required":True,
        "cost":"bounded adapter GPU/VRAM job","output":"candidate adapter weights",
        "limit":"license, memorization, privacy, resource and quality risks",
        "may_deploy":False},
    "from_scratch":{"weights_modified":True,"dataset_required":True,
        "cost":"new base model; substantially larger data and GPU budget",
        "output":"new base weights",
        "limit":"not admitted while OS-less Hephaestus has no verified trainer",
        "may_deploy":False},
}
SOURCE_CLASSES=frozenset({"licensed_public","owner_original_nonprivate","synthetic_nonsensitive"})
LICENSES=frozenset({"CC0-1.0","CC-BY-4.0","MIT","Apache-2.0","OWNER-ORIGINAL"})
# A conservative denylist, not a proof of complete secret/PII detection.
SENSITIVE=re.compile(r"(?i)(?:@|-----BEGIN|authorization:\s*bearer|password\s*[=:]|"
                     r"api_key\s*[=:]|access_token\s*[=:]|\b(?:discord|dm_channel|"
                     r"conversation_id|session_id|role\s*:\s*user|chat_history|"
                     r"emotion_journal|health_record|screenshot|voice_recording|"
                     r"intimate_journal|social_security|private_key)\b)")
MAX_BYTES=16*1024*1024
MAX_LINE=8192
MAX_ROWS=100_000


def _rights_class_matches_source(
    source_class:str, license_id:str, source_ref:str,
)->bool:
    """Validate claimed source-rights CATEGORY, not the external license itself."""
    if (
        source_class not in SOURCE_CLASSES or license_id not in LICENSES
        or not isinstance(source_ref,str)
        or not 1<=len(source_ref)<=300
        or not source_ref.startswith(("public-source:","owner-source:"))
    ):
        return False
    if source_ref.startswith("owner-source:"):
        return (
            license_id=="OWNER-ORIGINAL"
            and source_class in {"owner_original_nonprivate","synthetic_nonsensitive"}
            and len(source_ref)>len("owner-source:")
        )
    return (
        license_id!="OWNER-ORIGINAL"
        and source_class in {"licensed_public","synthetic_nonsensitive"}
        and len(source_ref)>len("public-source:")
    )


@dataclass(frozen=True,slots=True)
class TrainingDatasetReview:
    digest:str
    source_class:str
    license_id:str
    source_ref:str
    approval_ref:str
    source_path:str
    reviewed_at:datetime
    unique_rows:int
    duplicate_rows:int
    bytes_observed:int
    training_authorized:bool=False
    deployment_authorized:bool=False
    private_data_authorized:bool=False

    def __post_init__(self):
        if (
            not re.fullmatch(r"[0-9a-f]{64}",self.digest)
            or not _rights_class_matches_source(
                self.source_class,self.license_id,self.source_ref
            )
            or not isinstance(self.approval_ref,str)
            or not self.approval_ref.startswith("owner-ui:")
            or self.training_authorized or self.deployment_authorized
            or self.private_data_authorized
        ):
            raise PermissionError("public dataset evidence is not training permission")
        if self.unique_rows<20 or self.bytes_observed<=0 or self.bytes_observed>MAX_BYTES:
            raise ValueError("bounded unique examples required")
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("review time must be timezone-aware")

def inspect_public_dataset(*,path:str|Path,source_class:str,license_id:str,
                           source_ref:str,approval_ref:str,at:datetime)->TrainingDatasetReview:
    if source_class not in SOURCE_CLASSES or license_id not in LICENSES:
        raise PermissionError("raw private conversation/Discord/screen data are prohibited")
    if not _rights_class_matches_source(source_class,license_id,source_ref):
        raise PermissionError("training rights class, license and origin receipt conflict")
    requested=Path(path).expanduser()
    if any(
        component.is_symlink()
        or getattr(component,"is_junction",lambda:False)()
        for component in (requested,*requested.parents)
    ):
        raise PermissionError("training source path cannot follow symbolic links or junctions")
    source=requested.resolve(strict=True)
    if any(
        component.is_symlink()
        or getattr(component,"is_junction",lambda:False)()
        for component in (source,*source.parents)
    ):
        raise PermissionError("resolved training path contains a redirected component")
    if (
        not source.is_file() or source.suffix.casefold()!=".jsonl"
        or str(source.anchor).startswith(("\\\\","//"))
    ):
        raise ValueError("regular local JSONL file required")
    if inside_git_worktree(source):
        raise PermissionError("datasets must not be sourced from this Git checkout")
    before=source.stat()
    if not 1<=before.st_size<=MAX_BYTES:
        raise ValueError("dataset outside admission size bound")
    digest=sha256()
    seen=set()
    duplicates=0
    nbytes=0
    with source.open("rb") as stream:
        opened=os.fstat(stream.fileno())
        if (
            (opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino)
            or opened.st_size!=before.st_size
            or opened.st_mtime_ns!=before.st_mtime_ns
        ):
            raise PermissionError("training source changed before inspection")
        for i,line in enumerate(stream,1):
            nbytes+=len(line)
            if i>MAX_ROWS or len(line)>MAX_LINE or nbytes>MAX_BYTES:
                raise PermissionError("row count, row size or total bytes exceeded")
            digest.update(line)
            try:
                row=json.loads(line.decode("utf-8"))
            except (ValueError,UnicodeError) as exc:
                raise ValueError("valid public UTF-8 JSONL required") from exc
            if (
                not isinstance(row,dict)
                or set(row)!={"instruction","response"}
                or any(not isinstance(row[k],str) or not 1<=len(row[k])<=3000
                       or not row[k].strip()
                       for k in ("instruction","response"))
                or SENSITIVE.search(json.dumps(row,ensure_ascii=False))
            ):
                raise PermissionError("potential secrets, chat or unsafe source data rejected")
            fingerprint=sha256(json.dumps(
                row,sort_keys=True,ensure_ascii=False,
                separators=(",",":")).encode("utf-8")).digest()
            if fingerprint in seen:duplicates+=1
            else:seen.add(fingerprint)
        finished=os.fstat(stream.fileno())
    after=source.stat()
    for observed in (opened,finished,after):
        if (
            (observed.st_dev,observed.st_ino)!=(before.st_dev,before.st_ino)
            or observed.st_size!=before.st_size
            or observed.st_mtime_ns!=before.st_mtime_ns
        ):
            raise PermissionError("training source changed during review")
    if nbytes!=before.st_size:
        raise PermissionError("training source byte count changed during review")
    return TrainingDatasetReview(
        digest.hexdigest(),source_class,license_id,source_ref,approval_ref,
        str(source),at,len(seen),duplicates,nbytes,
    )

class TrainingDatasetStore:
    def __init__(self,path:Path|str):
        self._guard=CanonicalSQLiteGuard(Path(path))
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute("CREATE TABLE IF NOT EXISTS evolve_training_dataset_review("
                       "digest TEXT PRIMARY KEY,approval_ref TEXT NOT NULL UNIQUE,"
                       "metadata TEXT NOT NULL,reviewed_at TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS evolve_training_dataset_revocation("
                       "digest TEXT PRIMARY KEY,revoked_at TEXT NOT NULL,"
                       "owner_receipt TEXT NOT NULL UNIQUE,reason TEXT NOT NULL)")
    def record(self,review:TrainingDatasetReview)->None:
        if not isinstance(review,TrainingDatasetReview):
            raise TypeError("reviewed typed source required")
        data=asdict(review)
        data["reviewed_at"]=review.reviewed_at.astimezone(timezone.utc).isoformat()
        raw=json.dumps(data,sort_keys=True,separators=(",",":"))
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute("BEGIN IMMEDIATE")
            revoked=db.execute(
                "SELECT 1 FROM evolve_training_dataset_revocation WHERE digest=?",
                (review.digest,),
            ).fetchone()
            if revoked is not None:
                raise PermissionError(
                    "permanently revoked dataset cannot be re-recorded as reviewed"
                )
            found=db.execute("SELECT metadata FROM evolve_training_dataset_review WHERE digest=?",
                             (review.digest,)).fetchone()
            if found is not None:
                if found[0]!=raw:raise PermissionError("immutable review already exists")
                return
            db.execute("INSERT INTO evolve_training_dataset_review VALUES(?,?,?,?)",
                       (review.digest,review.approval_ref,raw,data["reviewed_at"]))
    def revoke(self,*,digest:str,at:datetime,owner_receipt:str,
               reason:str="owner_withdrew_training_data_permission")->None:
        """Append owner withdrawal; reapproving the old digest is forbidden."""
        if not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest):
            raise ValueError("exact reviewed dataset SHA-256 required")
        if (
            not isinstance(owner_receipt,str)
            or not owner_receipt.startswith("owner-ui:")
            or not isinstance(reason,str)
            or reason!="owner_withdrew_training_data_permission"
            or not isinstance(at,datetime) or at.tzinfo is None
            or at.utcoffset() is None
        ):
            raise PermissionError("exact owner dataset withdrawal required")
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute("BEGIN IMMEDIATE")
            source=db.execute(
                "SELECT 1 FROM evolve_training_dataset_review WHERE digest=?",
                (digest,),
            ).fetchone()
            if source is None:
                raise LookupError("cannot revoke unknown training dataset")
            existing=db.execute(
                "SELECT 1 FROM evolve_training_dataset_revocation WHERE digest=?",
                (digest,),
            ).fetchone()
            if existing:
                raise PermissionError("reviewed source is already permanently revoked")
            db.execute(
                "INSERT INTO evolve_training_dataset_revocation VALUES(?,?,?,?)",
                (digest,at.astimezone(timezone.utc).isoformat(),owner_receipt,reason),
            )

    def find(self,digest:str)->TrainingDatasetReview|None:
        if not re.fullmatch(r"[0-9a-f]{64}",digest):
            raise ValueError("exact source SHA-256 required")
        with closing(self._guard.connect(timeout=10)) as db:
            row=db.execute(
                "SELECT r.metadata FROM evolve_training_dataset_review r "
                "LEFT JOIN evolve_training_dataset_revocation v ON v.digest=r.digest "
                "WHERE r.digest=? AND v.digest IS NULL",
                (digest,),
            ).fetchone()
        if row is None:return None
        data=json.loads(row[0]);data["reviewed_at"]=datetime.fromisoformat(data["reviewed_at"])
        return TrainingDatasetReview(**data)
    def model_brief(self)->dict:
        with closing(self._guard.connect(timeout=10)) as db:
            rows=db.execute(
                "SELECT r.metadata,v.revoked_at FROM evolve_training_dataset_review r "
                "LEFT JOIN evolve_training_dataset_revocation v ON v.digest=r.digest "
                "ORDER BY r.reviewed_at DESC LIMIT 12",
            ).fetchall()
        return {"methods":TRAINING_METHODS,
                "reviewed":tuple({
                    "digest":json.loads(row[0])["digest"],
                    "license":json.loads(row[0])["license_id"],
                    "source_class":json.loads(row[0])["source_class"],
                    "status":"revoked" if row[1] is not None else "reviewed_not_authorized",
                } for row in rows),
                "raw_chat_screen_discord_training":False,
                "actual_training_authorized":False,
                "model_switch_authorized":False}
