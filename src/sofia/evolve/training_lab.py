"""Owner-reviewed resource/security plan for isolated Hephaestus training.

No guest exists yet (Hyper-V VM has no OS), and Artemis has no approved
training GPU. This manifest cannot create a VM, grant GPU time, execute a
trainer, read private chat, enable SSH or promote resulting weights.
"""
from __future__ import annotations
from contextlib import closing
from dataclasses import asdict,dataclass
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID
import json,re
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.evolve.training_sources import TrainingDatasetStore
from sofia.evolve.training_policy import AdaptationPlan,assess_registered_adaptation

_SHA=re.compile(r"^[0-9a-f]{64}$")

@dataclass(frozen=True,slots=True)
class TrainingLabPlan:
    plan_id:str
    artemis_node_id:UUID
    hephaestus_vm_id:UUID
    base_model_sha256:str
    training_data_sha256:str
    heldout_data_sha256:str
    data_use_approval_ref:str
    method:str
    seed:int
    cpu_cores:int
    ram_mb:int
    scratch_disk_gib:int
    max_wall_seconds:int
    max_gpu_seconds:int
    max_gpu_vram_mb:int
    max_external_cost_usd_cents:int
    gpu_worker:str
    created_at:datetime
    expires_at:datetime
    owner_review_receipt:str
    network_mode:str="internal_host_guest_no_lan"
    guest_admin:str="sofia-admin"
    guest_worker:str="sofia-worker"
    guest_ssh_enabled:bool=False
    guest_root_execution:bool=False
    allowed_dataset_origin:str="owner_reviewed_public_only"
    canonical_db_mount:bool=False
    host_secrets_mounted:bool=False
    may_train:bool=False
    may_install_model:bool=False

    def __post_init__(self):
        # Typed manifests must not smuggle truthy values or reuse a host
        # identity as an allegedly independent isolated training guest.
        for field in (
            "guest_ssh_enabled", "guest_root_execution", "canonical_db_mount",
            "host_secrets_mounted", "may_train", "may_install_model",
        ):
            if type(getattr(self, field)) is not bool:
                raise TypeError(f"{field} must be an explicit boolean")
        if not isinstance(self.plan_id, str):
            raise ValueError("bounded unique training plan ID required")
        if not re.fullmatch(r"train:[0-9a-f]{32}",self.plan_id):
            raise ValueError("bounded unique training plan ID required")
        if not isinstance(self.artemis_node_id,UUID) or not isinstance(self.hephaestus_vm_id,UUID):
            raise ValueError("exact enrolled host and existing VM GUID required")
        if self.artemis_node_id == self.hephaestus_vm_id:
            raise PermissionError("training guest cannot reuse enrolled host identity")
        if any(not isinstance(v,str) or not _SHA.fullmatch(v) for v in (
            self.base_model_sha256,self.training_data_sha256,
            self.heldout_data_sha256,
        )):
            raise ValueError("source/model digests must be SHA-256 pinned")
        if self.training_data_sha256==self.heldout_data_sha256:
            raise PermissionError("heldout evaluation cannot reuse training data")
        if self.method not in {"lora","qlora"}:
            raise PermissionError("whole-model training requires separate architecture review")
        if not self.data_use_approval_ref.startswith("owner-ui:"):
            raise PermissionError("owner data-use review required")
        if not self.owner_review_receipt.startswith("owner-ui:"):
            raise PermissionError("independent lab plan review required")
        if (
            self.network_mode!="internal_host_guest_no_lan" or self.guest_admin!="sofia-admin"
            or self.guest_worker!="sofia-worker"
            or self.allowed_dataset_origin!="owner_reviewed_public_only"
            or self.guest_ssh_enabled or self.guest_root_execution
            or self.canonical_db_mount or self.host_secrets_mounted
            or self.may_train or self.may_install_model
        ):
            raise PermissionError("training lab cannot inherit host, SSH, DB or identity authority")
        if self.gpu_worker not in {"none","venus_separately_approved"}:
            raise PermissionError("no unreviewed GPU worker or remote fallback allowed")
        if (
            type(self.seed) is not int or not 0<=self.seed<2**32
            or type(self.cpu_cores) is not int or not 1<=self.cpu_cores<=4
            or type(self.ram_mb) is not int or not 2048<=self.ram_mb<=8192
            or type(self.scratch_disk_gib) is not int or not 1<=self.scratch_disk_gib<=30
            or type(self.max_wall_seconds) is not int or not 60<=self.max_wall_seconds<=28_800
            or type(self.max_gpu_seconds) is not int or not 0<=self.max_gpu_seconds<=14_400
            or type(self.max_gpu_vram_mb) is not int or not 0<=self.max_gpu_vram_mb<=12_288
            or type(self.max_external_cost_usd_cents) is not int
            or not 0<=self.max_external_cost_usd_cents<=2000
        ):
            raise ValueError("bounded per-job CPU/RAM/disk/GPU/wall/cost/seed required")
        if self.gpu_worker=="none" and (self.max_gpu_seconds or self.max_gpu_vram_mb):
            raise PermissionError("GPU resources cannot be reserved without separately approved worker")
        if (
            not isinstance(self.created_at, datetime)
            or not isinstance(self.expires_at, datetime)
            or self.created_at.tzinfo is None or self.created_at.utcoffset() is None
            or self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None
            or not timedelta(0)<self.expires_at-self.created_at<=timedelta(minutes=30)
        ):
            raise ValueError("reviewed plan must expire within 30 minutes")

    def manifest(self)->dict:
        data=asdict(self)
        data["artemis_node_id"]=str(self.artemis_node_id)
        data["hephaestus_vm_id"]=str(self.hephaestus_vm_id)
        for key in ("created_at","expires_at"):
            data[key]=data[key].astimezone(timezone.utc).isoformat()
        return data

    @property
    def fingerprint(self)->str:
        return sha256(json.dumps(
            self.manifest(),sort_keys=True,separators=(",",":"),
        ).encode("utf-8")).hexdigest()


@dataclass(frozen=True,slots=True)
class TrainingLabReview:
    plan_fingerprint:str
    source_review_eligible:bool
    runtime_ready:bool
    hard_blockers:tuple[str,...]
    training_authorized:bool=False
    gpu_lease_granted:bool=False
    weights_promotion_allowed:bool=False


def assess_training_lab(
    plan:TrainingLabPlan,*,dataset_store:TrainingDatasetStore,
    guest_debian_attested:bool=False,
    venus_gpu_job_approved:bool=False,
    workshop_handoff_store=None,
    at:datetime,
)->TrainingLabReview:
    if not isinstance(plan,TrainingLabPlan) or not isinstance(dataset_store,TrainingDatasetStore):
        raise TypeError("typed owner plan and canonical source review required")
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("aware plan review time required")
    source=assess_registered_adaptation(
        AdaptationPlan(
            base_model_digest=plan.base_model_sha256,
            training_data_digest=plan.training_data_sha256,
            heldout_data_digest=plan.heldout_data_sha256,
            data_use_approval_ref=plan.data_use_approval_ref,
            adaptation_kind=plan.method,
            # Dataset rights can be reviewed with no GPU installed.
            # These are validation floor constants, NOT observed resources.
            max_gpu_hours=max(1.0,plan.max_gpu_seconds/3600),
            max_vram_mb=max(512,plan.max_gpu_vram_mb),
            preserve_source_privacy=True,
        ),
        dataset_store=dataset_store,
    )
    blockers=list(source.blockers)
    # An owner-typed GUID is NOT proof that the reviewed guest is Hephaestus.
    # Compare against canonical read-only mTLS host observation evidence.
    if workshop_handoff_store is None:
        blockers.append("no authenticated owner-created VM handoff source")
    else:
        from sofia.ops.workshop_handoff import WorkshopHandoffStore
        if not isinstance(workshop_handoff_store,WorkshopHandoffStore):
            raise TypeError("canonical pinned Fleet handoff owner required")
        observed_guest=workshop_handoff_store.read_model_brief()
        if (
            observed_guest.get("status")!="reviewed_read_only"
            or observed_guest.get("artemis_node_id")!=str(plan.artemis_node_id)
            or observed_guest.get("vm_guid")!=str(plan.hephaestus_vm_id)
            or observed_guest.get("guest_name")!="Hephaestus"
            or observed_guest.get("ready_for_bootstrap_review") is not True
            or observed_guest.get("internal_isolation_observed") is not True
        ):
            blockers.append(
                "exact Hephaestus host/VM identity or independently reviewed "
                "Internal network isolation missing, stale or blocked"
            )
    # A reviewed draft does not acquire guest trust or host GPU availability.
    if not guest_debian_attested:
        blockers.append("no independently attested Debian Hephaestus worker")
    if plan.gpu_worker=="venus_separately_approved" and not venus_gpu_job_approved:
        blockers.append("Venus GPU lease lacks independently approved owner grant")
    if plan.gpu_worker=="none":
        blockers.append("no trained-adapter GPU worker present; CPU-only research not promoted")
    if not plan.created_at<=at<plan.expires_at:
        blockers.append("training plan expired")
    return TrainingLabReview(
        plan_fingerprint=plan.fingerprint,
        source_review_eligible=source.research_eligible,
        runtime_ready=False,
        hard_blockers=tuple(dict.fromkeys(blockers)),
    )


class TrainingLabReviewStore:
    """Owner review and source manifest only; no training job scheduler."""
    def __init__(self,state_path:Path|str):
        self._guard=CanonicalSQLiteGuard(Path(state_path))
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS evolve_training_lab_review("
                "plan_id TEXT PRIMARY KEY,plan_hash TEXT NOT NULL,"
                "review_json TEXT NOT NULL,created_at TEXT NOT NULL)"
            )
    def record(self,plan:TrainingLabPlan,review:TrainingLabReview)->None:
        if plan.fingerprint!=review.plan_fingerprint:
            raise PermissionError("lab plan and reviewed source facts diverge")
        body=json.dumps({
            "plan":plan.manifest(),"review":asdict(review),
            "job_executed":False,"model_weights_generated":False,
        },sort_keys=True,separators=(",",":"))
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute("BEGIN IMMEDIATE")
            existing=db.execute(
                "SELECT review_json FROM evolve_training_lab_review WHERE plan_id=?",
                (plan.plan_id,),
            ).fetchone()
            if existing is not None:
                if existing[0]!=body:raise PermissionError("owner lab review cannot be rewritten")
                return
            db.execute("INSERT INTO evolve_training_lab_review VALUES(?,?,?,?)",
                       (plan.plan_id,plan.fingerprint,body,
                        plan.created_at.astimezone(timezone.utc).isoformat()))
    def latest_status(self)->dict:
        with closing(self._guard.connect(timeout=10)) as db:
            row=db.execute(
                "SELECT review_json FROM evolve_training_lab_review "
                "ORDER BY created_at DESC LIMIT 1",
            ).fetchone()
        if row is None:
            return {"status":"no_reviewed_lab_plan","training_authorized":False}
        parsed=json.loads(row[0])
        return {
            "status":"owner_review_only",
            "plan_id":parsed["plan"]["plan_id"],
            "method":parsed["plan"]["method"],
            "source_eligible":parsed["review"]["source_review_eligible"],
            "blockers":tuple(parsed["review"]["hard_blockers"]),
            "may_execute_training":False,
            "may_promote_model":False,
            "guest_os_attested":False,
            "gpu_lease_granted":False,
        }
