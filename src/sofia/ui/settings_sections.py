"""Working settings controls and owner review panels for the tray UI."""
from __future__ import annotations

from contextlib import closing
from dataclasses import fields, replace
from datetime import datetime, timezone
import json
import os
import sqlite3

from sofia.config.user_settings import OutreachSettings, RuntimeUserSettingsStore
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard
from .settings_service import database_diagnostics


def parse_field(raw, default, name: str):
    """Translate form text into the type validated by its owning dataclass."""
    if type(default) is bool:
        return bool(raw)
    text = str(raw).strip()
    if isinstance(default, tuple):
        return tuple(dict.fromkeys(part.strip() for part in text.split(",") if part.strip()))
    if type(default) is int:
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError(f"{name.replace('_', ' ')} must be an integer") from exc
    if default is None:
        return text or None
    return text


class SettingsSections:
    """Bind additional forms to existing configuration and durable owners."""

    def __init__(self, *, tk, ttk, frames, config, runtime, root):
        from tkinter import messagebox
        self.tk, self.ttk, self.root = tk, ttk, root
        self.config, self.runtime = config, runtime
        self._canonical_state = CanonicalSQLiteGuard(config.state_path)
        self.variables = {}
        self.groups = {}
        self.messagebox = messagebox

        def boolean(section, field, label, default):
            variable = tk.BooleanVar(root, value=default)
            self.variables[field] = variable
            ttk.Checkbutton(frames[section], text=label, variable=variable).pack(anchor="w", pady=5)

        boolean("NEURO", "neuro_competition_enabled", "Enable connectome-inspired attention (uncheck for deterministic salience)", runtime.neuro_competition_enabled)
        boolean(
            "NEURO", "neuro_association_enabled",
            "Allow opt-in, audience-scoped associative memory reranking",
            runtime.neuro_association_enabled,
        )
        from uuid import UUID, uuid4
        from sofia.social.principals import local_sparks_principal
        from sofia.neuro.connectome.association_store import ReviewedAssociationStore
        from sofia.safe.operator_stop import OperatorStopStore

        association_target = tk.StringVar(root, value="")
        association_query = tk.StringVar(root, value="")
        ttk.Label(
            frames["NEURO"],
            text="Teach a reviewed memory association (candidate UUID only)",
        ).pack(anchor="w", pady=(8, 2))
        ttk.Entry(frames["NEURO"], textvariable=association_target).pack(fill="x")
        ttk.Label(
            frames["NEURO"],
            text="Query words that should favor this already-promoted memory",
        ).pack(anchor="w", pady=(4, 2))
        ttk.Entry(frames["NEURO"], textvariable=association_query).pack(fill="x")

        def review_association():
            # User interaction is a human control, not a cognitive tool. Raw
            # query text is hashed to sparse units before canonical storage.
            if OperatorStopStore(config.state_path).current().active:
                raise PermissionError("operator stop blocks associative learning")
            if not RuntimeUserSettingsStore(config.state_path).load().neuro_association_enabled:
                raise PermissionError(
                    "Save the NEURO association opt-in in Settings first"
                )
            candidate_id = UUID(association_target.get().strip())
            raw_query = association_query.get().strip()
            if not raw_query or len(raw_query) > 500:
                raise ValueError("bounded review query of 1..500 characters required")
            from sofia.memory.provenance_store import DurableMemoryCandidateStore
            from sofia.memory.provenance import CandidateStatus
            candidate_store = DurableMemoryCandidateStore(config.state_path)
            try:
                candidate = candidate_store.get(candidate_id)
                if (
                    candidate is None
                    or candidate_store.status(candidate_id) is not CandidateStatus.PROMOTED
                ):
                    raise PermissionError("only promoted MEM candidates can be taught")
                principal = local_sparks_principal()
                if (
                    candidate.principal_id != principal.principal_id
                    or candidate.audience_id not in (None, principal.audience_id)
                ):
                    raise PermissionError("reviewed memory scope does not match owner")
                description = (
                    "Reinforce retrieval tie-breaks for the reviewed memory?\n\n"
                    f"Candidate: {candidate_id}\n"
                    f"Principal: {principal.principal_id}\n"
                    f"Audience: {principal.audience_id}\n"
                    f"Words: {raw_query}\n\n"
                    "The raw query will not be persisted by NEURO. "
                    "This action cannot make a memory eligible or public."
                )
                if not self.messagebox.askyesno(
                    "Approve one NEURO association?", description, parent=root,
                ):
                    return
                ReviewedAssociationStore(config.state_path).reinforce_reviewed(
                    principal_id=principal.principal_id,
                    audience_id=principal.audience_id,
                    candidate_id=candidate_id,
                    query=raw_query,
                    approval_ref="operator-ui:" + uuid4().hex,
                    amount=0.1,
                    at=datetime.now(timezone.utc),
                )
                self.messagebox.showinfo(
                    "Association reviewed",
                    "Bounded private tie-breaker saved in sofia.db.",
                    parent=root,
                )
            finally:
                candidate_store.close()

        ttk.Button(
            frames["NEURO"],
            text="Review and reinforce promoted memory...",
            command=self.guarded(review_association),
        ).pack(anchor="w", pady=(5, 4))

        def reset_reviewed_associations():
            if OperatorStopStore(config.state_path).current().active:
                raise PermissionError("operator stop blocks associative reset")
            principal = local_sparks_principal()
            if not self.messagebox.askyesno(
                "Reset reviewed associations?",
                "Delete all learned NEURO association weights and teaching "
                "receipts for this principal/audience? Reviewed MEM facts, "
                "source transcripts and other principals remain unchanged.",
                parent=root,
            ):
                return
            deleted = ReviewedAssociationStore(config.state_path).reset_scope(
                principal_id=principal.principal_id,
                audience_id=principal.audience_id,
            )
            self.messagebox.showinfo(
                "Association reset", f"Removed {deleted} scope-bound weights.",
                parent=root,
            )

        ttk.Button(
            frames["NEURO"],
            text="Reset my reviewed associations",
            command=self.guarded(reset_reviewed_associations),
        ).pack(anchor="w", pady=(4, 8))

        # Falsifiable science is kept distinct from NEURO's runtime controls.
        # Preregistering a protocol does not execute any research or label
        # Sofía conscious, and measured outcomes require human source review.
        from sofia.neuro.research_registry import (
            ResearchEvidenceRegistry, reviewed_baseline_studies,
            EvaluatedResearchOutcome,
        )
        science = ResearchEvidenceRegistry(config.state_path)
        science_view = self.viewer(
            frames["NEURO"],
            "Functional awareness research (no consciousness claims)",
            lambda: science.report(),
        )

        def preregister_research():
            if OperatorStopStore(config.state_path).current().active:
                raise PermissionError("operator stop blocks research registry writes")
            studies = reviewed_baseline_studies(
                at=datetime.now(timezone.utc),
            )
            text = (
                "Preregister three observable, falsifiable studies?\n\n"
                "1. Eligible attention broadcast vs deterministic retrieval\n"
                "2. Calibrated self-model vs static capability table\n"
                "3. Recurrent error review vs feed-forward baseline\n\n"
                "This creates no experiment, model load or subjective "
                "experience claim. Future outcomes require separate evidence."
            )
            if not self.messagebox.askyesno(
                "Approve research preregistration?", text, parent=root,
            ):
                return
            for study in studies:
                science.preregister(study)
            science_view.refresh()

        ttk.Button(
            frames["NEURO"],
            text="Review & preregister three baseline studies",
            command=self.guarded(preregister_research),
        ).pack(anchor="w", pady=(4, 8))

        evidence_study = tk.StringVar(root, value="science:attention:v1")
        evidence_kind = tk.StringVar(root, value="inconclusive")
        evidence_source = tk.StringVar(root, value="")
        evidence_samples = tk.StringVar(root, value="0")
        evidence_adverse = tk.StringVar(root, value="No adverse effects observed in supplied evidence")
        evidence_limits = tk.StringVar(root, value="Only functional outcomes; subjective experience unverified")

        ttk.Label(
            frames["NEURO"],
            text="Record independent research outcome: registered study ID",
        ).pack(anchor="w")
        ttk.Entry(frames["NEURO"], textvariable=evidence_study).pack(fill="x")
        ttk.Combobox(
            frames["NEURO"], textvariable=evidence_kind,
            values=(
                "supported", "refuted", "null", "inconclusive",
                "adverse", "protocol_violation",
            ),
            state="readonly",
        ).pack(fill="x", pady=(3, 3))
        for label, var in (
            ("External evidence receipt ID", evidence_source),
            ("Actual observed sample count", evidence_samples),
            ("Adverse findings, including none with supporting evidence", evidence_adverse),
            ("Uncertainty and limitations", evidence_limits),
        ):
            ttk.Label(frames["NEURO"], text=label).pack(anchor="w", pady=(3, 2))
            ttk.Entry(frames["NEURO"], textvariable=var).pack(fill="x")

        def record_science_result():
            if OperatorStopStore(config.state_path).current().active:
                raise PermissionError("operator stop blocks research registry writes")
            observed = EvaluatedResearchOutcome(
                protocol_id=evidence_study.get().strip(),
                observed_at=datetime.now(timezone.utc),
                actual_sample_size=int(evidence_samples.get().strip()),
                result=evidence_kind.get(),
                evidence_ref=evidence_source.get().strip(),
                adverse_observations=evidence_adverse.get().strip(),
                limitations=evidence_limits.get().strip(),
                reviewed_by="Sparks",
            )
            if not self.messagebox.askyesno(
                "Approve independent study outcome?",
                (
                    "Record this reviewed functional study result?\n\n"
                    f"Protocol: {observed.protocol_id}\n"
                    f"Outcome: {observed.result}\n"
                    f"Sample: {observed.actual_sample_size}\n"
                    f"Evidence: {observed.evidence_ref}\n\n"
                    "It cannot establish subjective consciousness, even "
                    "if the measured hypothesis is supported."
                ),
                parent=root,
            ):
                return
            science.record_reviewed_result(observed)
            science_view.refresh()

        ttk.Button(
            frames["NEURO"],
            text="Review & record independent study result",
            command=self.guarded(record_science_result),
        ).pack(anchor="w", pady=(4, 8))

        def request_neuro_reset():
            # Only the single canonical runtime applies the generation change.
            # This control does not remove inputs, memories or operator policy.
            store = RuntimeUserSettingsStore(config.state_path)
            current = store.load()
            generation = (current.neuro_competition_reset_generation + 1) % 1_000_001
            store.save(replace(
                current, neuro_competition_reset_generation=generation,
            ))
            messagebox.showinfo(
                "NEURO recurrence reset requested",
                "Saved to canonical settings. The running runtime will restore "
                "the bounded circuit's reviewed parameters on its next "
                "foreground/background refresh. Trusted observations remain.",
                parent=root,
            )

        ttk.Button(
            frames["NEURO"],
            text="Reset attention circuit parameters",
            command=self.guarded(request_neuro_reset),
        ).pack(anchor="w", pady=(4, 8))
        boolean("Chat", "adaptive_theme", "Adapt desktop colors to Sofía’s state", runtime.adaptive_theme)
        boolean("Sofía", "idle_reflections_enabled", "Enable idle reflection", runtime.idle_reflections_enabled if runtime.idle_reflections_enabled is not None else os.environ.get("SOFIA_IDLE_REFLECTIONS", "").lower() not in ("0", "false", "off"))
        boolean("Sofía", "habit_learning_enabled", "Learn habits from supported observations", runtime.habit_learning_enabled if runtime.habit_learning_enabled is not None else os.environ.get("SOFIA_HABIT_LEARNING", "1").lower() in ("1", "true", "on"))
        boolean("Avatar", "avatar_routines_enabled", "Automatically select attire for supported routines", runtime.avatar_routines_enabled)
        boolean("Avatar", "avatar_renderer_enabled", "Show the optional desktop avatar renderer", runtime.avatar_renderer_enabled)
        boolean("Voice", "voice_output_enabled", "Enable local speech output", runtime.voice_output_enabled)
        boolean("Voice", "voice_input_enabled", "Enable push-to-talk microphone input", runtime.voice_input_enabled)
        boolean("Voice", "voice_muted", "Mute microphone and speaker presentation", runtime.voice_muted)
        for field, label in (
            ("voice_output_name", "Preferred installed voice (blank uses host default)"),
            ("voice_input_device", "Microphone device ID (blank uses host default)"),
        ):
            variable = tk.StringVar(root, value=getattr(runtime, field) or "")
            self.variables[field] = variable
            ttk.Label(frames["Voice"], text=label).pack(anchor="w", pady=(8, 2))
            ttk.Entry(frames["Voice"], textvariable=variable).pack(fill="x")
        self.sql_panel(frames["Voice"], "Cross-modal output receipts", "expression_output_receipt")
        self.sql_panel(frames["Voice"], "Microphone input receipts", "voice_input_receipt")
        ttk.Label(
            frames["Voice"],
            text=(
                "Microphone capture is push-to-talk and disabled by default. "
                "Text remains authoritative when speech or rendering fails."
            ),
            wraplength=660,
        ).pack(anchor="w", pady=8)

        restart_mode = tk.StringVar(root, value=runtime.update_restart_mode)
        self.variables["update_restart_mode"] = restart_mode
        ttk.Label(frames["Sofía"], text="After an installed update is detected").pack(anchor="w", pady=(8, 2))
        ttk.Combobox(
            frames["Sofía"],
            textvariable=restart_mode,
            values=("automatic", "ask"),
            state="readonly",
        ).pack(fill="x")

        for field, label in (("provider_temperature", "Generation temperature (blank uses provider default)"), ("provider_seed", "Generation seed (blank uses provider default)"), ("provider_max_output_tokens", "Maximum output tokens (blank uses provider default)")):
            value = getattr(runtime, field)
            variable = tk.StringVar(root, value="" if value is None else str(value))
            self.variables[field] = variable
            ttk.Label(frames["Models"], text=label).pack(anchor="w", pady=(8, 2))
            ttk.Entry(frames["Models"], textvariable=variable).pack(fill="x")

        # Read-only, real Ollama discovery. The button never pulls, wakes,
        # provisions, accepts licenses or changes a configured model role.
        from queue import Empty, Queue
        from threading import Thread
        from sofia.cognition.model_inventory import ModelInventoryStore
        from sofia.machine.discovery import create_machine_discovery
        from sofia.config import create_production_configuration
        from sofia.config.cognitive_models import CognitiveModelSelection
        from sofia.integrations.ollama import OllamaAdapter
        from datetime import datetime, timezone

        inventory_store = ModelInventoryStore(config.state_path)
        try:
            host_id = (
                create_machine_discovery().discover().identity.machine_id
            )
        except Exception:
            # Model inspection is unavailable, not a reason to hide every
            # other owner setting or invent a local host identity.
            host_id = None
        inventory_view = self.viewer(
            frames["Models"],
            "Observed installed/configured model inventory (local host)",
            lambda: (
                inventory_store.readable(host_id=host_id)
                if host_id is not None
                else "Local machine identity unverified; inventory denied."
            ),
        )
        self.viewer(
            frames["Models"],
            "Local candidate review (installed only, independent evaluation needed)",
            lambda: (
                inventory_store.candidate_review(host_id=host_id)
                if host_id is not None
                else "Local host identity unverified; candidate review denied."
            ),
        )

        # The same observed, local API license text is reviewable in Settings,
        # without licensing acceptance, model pulls or network/cloud routing.
        selected_license_model = tk.StringVar(
            root, value=runtime.cognitive_primary_model,
        )
        ttk.Label(
            frames["Models"],
            text="License review: exact observed model name",
        ).pack(anchor="w", pady=(4, 2))
        ttk.Entry(
            frames["Models"],
            textvariable=selected_license_model,
        ).pack(fill="x")
        self.viewer(
            frames["Models"],
            "Observed license text (read only; no acceptance implied)",
            lambda: (
                inventory_store.license_text(
                    host_id=host_id,
                    model=selected_license_model.get(),
                ) if host_id is not None
                else "Local host identity unverified; license lookup denied."
            ),
        )
        inventory_responses = Queue()
        inventory_busy = {"active": False}

        def refresh_model_inventory():
            if host_id is None:
                raise PermissionError(
                    "local host identity unavailable; cannot inspect models"
                )
            if inventory_busy["active"]:
                return
            inventory_busy["active"] = True
            inventory_button.configure(state="disabled")

            def collect():
                try:
                    actual = (
                        create_machine_discovery().discover().identity.machine_id
                    )
                    if actual != host_id:
                        raise PermissionError(
                            "observed local machine changed during inventory"
                        )
                    current_config = create_production_configuration(
                        state_path=config.state_path
                    )
                    observations = collect_local_model_inventory(
                        selection=CognitiveModelSelection.from_configuration(
                            current_config
                        ),
                        backend=OllamaAdapter(),
                        host_id=host_id,
                        at=datetime.now(timezone.utc),
                    )
                    inventory_store.replace_host(
                        host_id=host_id, observations=observations,
                    )
                    inventory_responses.put(
                        ("success", f"Observed {len(observations)} model entries.")
                    )
                except Exception as exc:
                    inventory_responses.put(
                        ("error", f"{type(exc).__name__}: {exc}")
                    )

            Thread(
                target=collect, name="sofia-readonly-model-inventory",
                daemon=False,
            ).start()

        from sofia.cognition.model_inventory import collect_local_model_inventory
        inventory_button = ttk.Button(
            frames["Models"],
            text="Refresh local Ollama inventory (read only)",
            command=self.guarded(refresh_model_inventory),
        )
        inventory_button.pack(anchor="w", pady=6)
        if host_id is None:
            inventory_button.configure(state="disabled")

        def poll_model_inventory():
            try:
                outcome, detail = inventory_responses.get_nowait()
            except Empty:
                pass
            else:
                inventory_busy["active"] = False
                inventory_button.configure(state="normal")
                if outcome == "error":
                    self.messagebox.showerror(
                        "Model inspection failed", detail, parent=root,
                    )
                inventory_view.refresh()
            if root.winfo_exists():
                root.after(300, poll_model_inventory)

        root.after(300, poll_model_inventory)

        legacy_notification_service = os.environ.get(
            "SOFIA_NOTIFICATION_HA_SERVICE", ""
        ).strip()
        outreach = runtime.outreach or OutreachSettings(
            enabled=os.environ.get("SOFIA_ACT_DELIVERY_ENABLED", "").lower() not in ("0", "false", "off"),
            delivery_channel=(
                os.environ.get("SOFIA_ACT_DELIVERY_CHANNEL", "").strip()
                or (
                    "home_assistant"
                    if legacy_notification_service
                    else "desktop"
                )
            ),
            notification_service=legacy_notification_service,
            quiet_start_local=int(os.environ.get("SOFIA_ACT_QUIET_START_LOCAL", "22")),
            quiet_end_local=int(os.environ.get("SOFIA_ACT_QUIET_END_LOCAL", "8")),
            min_interval_minutes=int(os.environ.get("SOFIA_ACT_MIN_INTERVAL_MINUTES", "360")),
            max_daily=int(os.environ.get("SOFIA_ACT_MAX_DAILY", "1")),
        )
        self.group(frames["ACT"], "outreach", "Proactive outreach to Sparks", outreach)
        ttk.Label(frames["ACT"], text="Outreach is enabled by default. Desktop delivery uses Sofía’s tray. Mobile delivers to the authenticated paired Android app. Discord uses only the verified Sparks DM; Home Assistant remains available when configured. Quiet hours, recipient checks, evidence, quotas, busy state and operator stop still apply.", wraplength=660).pack(anchor="w", pady=8)
        self.sql_panel(frames["ACT"], "Outreach decision and delivery trace", "act_outreach_trace")
        self.sql_panel(frames["ACT"], "Presence initiative opportunities", "presence_initiative_opportunity")
        self.sql_panel(frames["ACT"], "Evidence-backed world observations", "presence_world_observation")
        self.group(frames["Fleet"], "fleet_cognition", "Cognitive placement", runtime.fleet_cognition or config.fleet_cognition)
        self.group(frames["Fleet"], "fleet_bootstrap", "Agent provisioning", runtime.fleet_bootstrap or config.fleet_bootstrap)
        ttk.Label(frames["Fleet"], text="Host IDs, targets and scopes are comma-separated. Discovery does not enroll hosts; provisioning requires the existing reviewed authority, package digest and signer.", wraplength=660).pack(anchor="w", pady=8)
        self.sql_panel(frames["Fleet"], "Enrolled nodes", "distributed_node_identity")
        self.sql_panel(frames["Fleet"], "Software and capability health evidence", "ops_dependency_observation")
        self.sql_panel(frames["Fleet"], "Verified platform installation receipts", "ops_platform_install_receipt")
        # Owner-created blank VM handoff. No generic Artemis PowerShell or
        # auto-provision route; only pinned Fleet read-only VM/media operations.
        from queue import Empty, Queue
        from threading import Thread
        from sofia.distributed.capability import create_configured_remote_fleet_service
        from sofia.ops.workshop_handoff import (
            WorkshopHandoffStore, preview_owner_created_vm,
        )

        ttk.Label(
            frames["Fleet"],
            text="HEPHAESTUS: OWNER-CREATED BLANK VM HANDOFF (Hyper-V)",
        ).pack(anchor="w", pady=(10, 2))
        ttk.Label(
            frames["Fleet"],
            text=(
                "First, you create an OFF, Generation-2 VM named Hephaestus "
                "with one 60-128 GiB empty VHDX and a PRIVATE switch named "
                "Sofia-Hephaestus-Private. Then Sofía can inspect it. "
                "Booting/installing Debian requires a separate Level-4 approval; "
                "Fleet enrollment is separate after verified OS installation."
            ),
            wraplength=660,
        ).pack(anchor="w", pady=4)
        handoff_node = tk.StringVar(root, value="")
        handoff_vm = tk.StringVar(root, value="")
        handoff_disk = tk.StringVar(root, value="")
        handoff_media = tk.StringVar(root, value="")
        handoff_digest = tk.StringVar(root, value="")
        handoff_empty = tk.BooleanVar(root, value=False)
        for text, var in (
            ("Exact enrolled Artemis Fleet node UUID", handoff_node),
            ("Exact Hyper-V Hephaestus VM GUID, not only its display name", handoff_vm),
            ("Exact existing OS VHDX on Artemis", handoff_disk),
            ("Host-approved OFFLINE unattended Debian ISO path", handoff_media),
            ("Independent SHA-256 of unattended boot ISO", handoff_digest),
        ):
            ttk.Label(frames["Fleet"], text=text).pack(anchor="w", pady=(4, 2))
            ttk.Entry(frames["Fleet"], textvariable=var).pack(fill="x")
        ttk.Checkbutton(
            frames["Fleet"], variable=handoff_empty,
            text=(
                "I created this VM and confirm its exact OS disk is EMPTY "
                "(installation may overwrite it). This is my declaration, "
                "not independent proof that the disk is blank."
            ),
        ).pack(anchor="w", pady=(4, 7))
        handoff_text = {"value":(
            "No owner-provided Hephaestus VM observed. Host, disk, switch, "
            "image, permissions and guest OS status remain UNKNOWN."
        )}
        handoff_view=self.viewer(
            frames["Fleet"],
            "Owner-created Hephaestus handoff review (read only)",
            lambda:handoff_text["value"],
        )
        handoff_queue=Queue()
        handoff_busy={"active":False}

        def preview_blank_hephaestus():
            if handoff_busy["active"]:
                return
            inputs=(
                handoff_node.get().strip(),handoff_vm.get().strip(),
                handoff_disk.get().strip(),handoff_media.get().strip(),
                handoff_digest.get().strip().lower(),
            )
            if not all(inputs):
                raise ValueError("Complete the exact Artemis/VM/disk/ISO handoff fields")
            if not handoff_empty.get():
                raise PermissionError("Owner must confirm the reviewed OS disk is empty")
            handoff_busy["active"]=True
            handoff_button.configure(state="disabled")

            def inspect_handoff_worker():
                service=None
                try:
                    service=create_configured_remote_fleet_service(config.state_path)
                    if service is None:
                        raise PermissionError("pinned-mTLS Artemis Fleet connection unavailable")
                    preview=preview_owner_created_vm(
                        remote_service=service,artemis_node_id=inputs[0],
                        exact_vm_id=inputs[1],disk_path=inputs[2],
                        boot_media_path=inputs[3],boot_media_sha256=inputs[4],
                        owner_confirms_blank_disk=True,
                        at=datetime.now(timezone.utc),
                    )
                    WorkshopHandoffStore(config.state_path).record(preview)
                    handoff_queue.put((
                        "ok",preview.readable(),preview.handoff.plan_id,
                    ))
                except Exception as exc:
                    handoff_queue.put((
                        "error", f"{type(exc).__name__}: {exc}. "
                        "No Hyper-V changes or guest installation authorized.",
                    ))
                finally:
                    if service is not None:
                        service.close()

            Thread(
                target=inspect_handoff_worker,
                name="sofia-owner-created-hephaestus-preflight",
                daemon=False,
            ).start()

        handoff_button=ttk.Button(
            frames["Fleet"],
            text="Inspect my blank Hephaestus VM (read only)",
            command=self.guarded(preview_blank_hephaestus),
        )
        handoff_button.pack(anchor="w", pady=(3, 8))

        def poll_handoff():
            try:
                response=handoff_queue.get_nowait()
                status,detail=response[:2]
                handoff_text["last_plan_id"]=(
                    response[2] if status=="ok" and len(response)>2 else None
                )
            except Empty:
                pass
            else:
                handoff_busy["active"]=False
                handoff_button.configure(state="normal")
                handoff_text["value"]=detail
                handoff_view.refresh()
                if status=="error":
                    self.messagebox.showerror(
                        "Hephaestus handoff blocked",detail,parent=root,
                    )
            if root.winfo_exists():
                root.after(350,poll_handoff)

        root.after(350,poll_handoff)

        # Separate explicit owner boot authorization. This button never
        # appears as a model-facing tool and is never invoked by RUN.
        from datetime import timedelta
        from uuid import uuid4
        from sofia.safe.execution_approval import (
            ExecutionApproval, ExecutionApprovalVerifier,
            execution_fingerprint,
        )
        from sofia.safe.operator_stop import OperatorStopStore
        from sofia.ops.workshop_guest_bootstrap import (
            reviewed_handoff_from_store,
            start_owner_approved_installer,
            WorkshopInstallerBootStore,
        )
        boot_busy={"active":False}
        boot_queue=Queue()
        boot_view=self.viewer(
            frames["Fleet"],
            "Hephaestus installer boot receipt (NOT OS installation proof)",
            lambda:(
                "No installer boot has been requested on this handoff."
                if not handoff_text.get("last_plan_id")
                else (
                    str(WorkshopInstallerBootStore(config.state_path).inspect(
                        plan_id=handoff_text["last_plan_id"],
                    ))
                )
            ),
        )

        def owner_install_debian():
            if boot_busy["active"] or handoff_busy["active"]:
                return
            if OperatorStopStore(config.state_path).current().active:
                raise PermissionError("operator stop blocks Debian bootstrap")
            plan_id=handoff_text.get("last_plan_id")
            if not plan_id:
                raise PermissionError("inspect your existing blank Hephaestus first")
            now=datetime.now(timezone.utc)
            handoff,_=reviewed_handoff_from_store(
                config.state_path,plan_id=plan_id,now=now,
            )
            if WorkshopInstallerBootStore(config.state_path).inspect(
                plan_id=plan_id,
            ) is not None:
                raise PermissionError(
                    "installer attempt already reserved; no automatic replay"
                )
            exact={
                "artemis_node_id":str(handoff.artemis_node_id),
                "vm_id":str(handoff.hyperv_vm_id),
                "disk_path":handoff.expected_os_disk_path,
                "iso_path":handoff.installer_iso_path,
                "iso_sha256":handoff.installer_sha256,
                "handoff_fingerprint":handoff.fingerprint,
            }
            review=(
                "START AN UNATTENDED DEBIAN INSTALLER ON ARTEMIS?\n\n"
                f"Existing VM: Hephaestus / {handoff.hyperv_vm_id}\n"
                f"Artemis: {handoff.artemis_node_id}\n"
                f"Existing OS VHDX: {handoff.expected_os_disk_path}\n"
                f"Unattended ISO: {handoff.installer_iso_path}\n"
                f"SHA-256: {handoff.installer_sha256}\n"
                f"Plan fingerprint: {handoff.fingerprint}\n\n"
                "This can FORMAT the reviewed empty disk. Hyper-V will "
                "attach the reviewed ISO and START this exact VM. "
                "It does NOT confirm Debian finished installing. "
                "Fleet enrollment requires a SEPARATE owner approval. "
                "No sibling VMs, switches, host OS, LAN or databases may be changed."
            )
            if not self.messagebox.askyesno(
                "Level-4: authorize exactly one Debian installer boot?",
                review,parent=root,
            ):
                return
            approval=ExecutionApproval(
                approval_id=str(uuid4()),
                capability="workshop.guest.bootstrap",
                request_fingerprint=execution_fingerprint(
                    "workshop.guest.bootstrap",exact,
                ),
                approved_by="Sparks",
                approved_at=now,
                expires_at=now+timedelta(minutes=10),
            )
            ExecutionApprovalVerifier(config.state_path).record(approval)
            boot_busy["active"]=True
            boot_button.configure(state="disabled")

            def boot_worker():
                service=None
                try:
                    service=create_configured_remote_fleet_service(config.state_path)
                    if service is None:
                        raise PermissionError(
                            "pinned Artemis Fleet connection unavailable"
                        )
                    settled=start_owner_approved_installer(
                        state_path=config.state_path,
                        remote_service=service,
                        plan_id=plan_id,
                        approval_id=approval.approval_id,
                        now=datetime.now(timezone.utc),
                    )
                    boot_queue.put(("ok",
                        f"Installer status: {settled.status}. "
                        f"Observed VM: {settled.observed_vm_state or 'UNKNOWN'}. "
                        "Debian installation NOT YET VERIFIED; no guest trusted."
                    ))
                except Exception as exc:
                    boot_queue.put((
                        "error",f"{type(exc).__name__}: {exc}. "
                        "A timeout may mean UNCERTAIN host state: inspect Artemis "
                        "before any new attempt.",
                    ))
                finally:
                    if service is not None:
                        service.close()

            Thread(
                target=boot_worker,
                name="sofia-approved-hephaestus-debian-installer",
                daemon=False,
            ).start()

        boot_button=ttk.Button(
            frames["Fleet"],
            text="Review & approve one Debian installer boot (protected)",
            command=self.guarded(owner_install_debian),
        )
        boot_button.pack(anchor="w",pady=(6,8))

        def poll_boot():
            try:
                state,detail=boot_queue.get_nowait()
            except Empty:
                pass
            else:
                boot_busy["active"]=False
                boot_button.configure(state="normal")
                boot_view.refresh()
                handoff_text["value"]=detail
                handoff_view.refresh()
                if state=="error":
                    self.messagebox.showerror(
                        "Hephaestus installer requires review",detail,parent=root,
                    )
                else:
                    self.messagebox.showinfo(
                        "Installer boot request recorded",detail,parent=root,
                    )
            if root.winfo_exists():
                root.after(350,poll_boot)

        root.after(350,poll_boot)

        from sofia.ops.workshop_guest_bootstrap import (
            inspect_existing_vm_installer,
        )
        installer_observation_queue=Queue()
        installer_observation_busy={"active":False}

        def inspect_hephaestus_after_boot():
            if installer_observation_busy["active"]:
                return
            plan_id=handoff_text.get("last_plan_id")
            if not plan_id:
                raise PermissionError(
                    "select and review the exact Hephaestus handoff first"
                )
            installer_observation_busy["active"]=True
            observe_boot_button.configure(state="disabled")

            def observe_worker():
                service=None
                try:
                    service=create_configured_remote_fleet_service(config.state_path)
                    if service is None:
                        raise PermissionError("pinned Artemis Fleet service unavailable")
                    host=inspect_existing_vm_installer(
                        state_path=config.state_path,
                        remote_service=service,
                        plan_id=plan_id,
                        now=datetime.now(timezone.utc),
                    )
                    installer_observation_queue.put((
                        "ok",json.dumps(host,indent=2,default=str),
                    ))
                except Exception as exc:
                    installer_observation_queue.put((
                        "error",f"{type(exc).__name__}: {exc}",
                    ))
                finally:
                    if service is not None:
                        service.close()
            Thread(
                target=observe_worker,
                name="sofia-hephaestus-postboot-readonly-observation",
                daemon=False,
            ).start()

        observe_boot_button=ttk.Button(
            frames["Fleet"],
            text="Inspect Hephaestus installer and VM status (read only)",
            command=self.guarded(inspect_hephaestus_after_boot),
        )
        observe_boot_button.pack(anchor="w",pady=(4,8))

        def poll_installer_observation():
            try:
                kind,detail=installer_observation_queue.get_nowait()
            except Empty:
                pass
            else:
                installer_observation_busy["active"]=False
                observe_boot_button.configure(state="normal")
                handoff_text["value"]=detail
                handoff_view.refresh()
                if kind=="error":
                    self.messagebox.showerror(
                        "Installer state inspection unavailable",
                        detail,parent=root,
                    )
            if root.winfo_exists():
                root.after(350,poll_installer_observation)

        root.after(350,poll_installer_observation)
        # Synthetic homelab twin uses ONLY existing OPS hosts and owner-
        # declared dependencies. No network scan, VM launch or simulated
        # result may become an authorization for a real operation.
        from sofia.ops.digital_twin import (
            TwinDependencyStore,TwinReviewedDependency,
            read_digital_twin_fleet,run_digital_twin_scenario,
        )
        from sofia.ops.capability import OpsToolService
        from uuid import uuid4
        dependency_store=TwinDependencyStore(config.state_path)
        ttk.Label(
            frames["Fleet"],
            text="HOMELAB DIGITAL TWIN: source-grounded synthetic scenarios",
        ).pack(anchor="w",pady=(12,2))
        ttk.Label(
            frames["Fleet"],
            text=(
                "Only OPS Fleet-enrolled host identities are modeled. "
                "Dependency links are owner declarations, NOT discovered "
                "network links. Simulation cannot trigger host/robot/rail "
                "actions, enrollment or permissions."
            ),wraplength=660,
        ).pack(anchor="w",pady=3)
        twin_dependent=tk.StringVar(root,value="")
        twin_prerequisite=tk.StringVar(root,value="")
        twin_kind=tk.StringVar(root,value="service")
        twin_target=tk.StringVar(root,value="")
        twin_scenario=tk.StringVar(root,value="dns_outage")
        for label,var in (
            ("Dependent OPS host ID",twin_dependent),
            ("Prerequisite OPS host ID",twin_prerequisite),
        ):
            ttk.Label(frames["Fleet"],text=label).pack(anchor="w",pady=(3,1))
            ttk.Entry(frames["Fleet"],textvariable=var).pack(fill="x")
        ttk.Combobox(
            frames["Fleet"],textvariable=twin_kind,
            values=("dns","fleet_transport","data","service","storage"),
            state="readonly",
        ).pack(fill="x",pady=(2,5))
        twin_result={"value":"No synthetic scenario run or Fleet graph observed."}
        twin_view=self.viewer(
            frames["Fleet"],
            "Digital twin: reviewed sources, unknowns and simulation-only output",
            lambda:twin_result["value"],
        )

        def owner_review_twin_dependency():
            service=OpsToolService(config.state_path)
            host_ids=tuple(host.host_id for host in service.registry.hosts())
            proposed=TwinReviewedDependency(
                dependent_host_id=twin_dependent.get().strip(),
                prerequisite_host_id=twin_prerequisite.get().strip(),
                kind=twin_kind.get(),
                reviewed_at=datetime.now(timezone.utc),
                approval_ref="owner-ui:"+uuid4().hex,
            )
            if not self.messagebox.askyesno(
                "Record owner-declared simulation dependency?",
                (
                    "This is a modeling assumption, not a discovered "
                    "real-world route.\n\n"
                    f"Dependent: {proposed.dependent_host_id}\n"
                    f"Prerequisite: {proposed.prerequisite_host_id}\n"
                    f"Category: {proposed.kind}\n\n"
                    "It will never grant authority or cause a real action."
                ),
                parent=root,
            ):
                return
            dependency_store.record_owner_review(
                proposed,known_host_ids=host_ids,
            )
            twin_result["value"]=json.dumps(
                read_digital_twin_fleet(
                    service=service,at=datetime.now(timezone.utc),
                ),
                indent=2,default=str,
            )
            twin_view.refresh()

        ttk.Button(
            frames["Fleet"],text="Review modeled dependency (no host writes)",
            command=self.guarded(owner_review_twin_dependency),
        ).pack(anchor="w",pady=(4,7))
        ttk.Label(
            frames["Fleet"],text="Synthetic failure target: existing OPS host ID",
        ).pack(anchor="w",pady=(3,1))
        ttk.Entry(frames["Fleet"],textvariable=twin_target).pack(fill="x")
        ttk.Combobox(
            frames["Fleet"],textvariable=twin_scenario,
            values=(
                "dns_outage","fleet_agent_unreachable","disk_pressure",
                "sqlite_lock","container_crash","stale_clock",
                "weather_sensor_failure","conflicting_node_identity",
            ),state="readonly",
        ).pack(fill="x",pady=(3,5))

        def run_homelab_twin():
            service=OpsToolService(config.state_path)
            now=datetime.now(timezone.utc)
            if not twin_target.get().strip():
                report=read_digital_twin_fleet(service=service,at=now)
            else:
                report=run_digital_twin_scenario(
                    service=service,scenario=twin_scenario.get(),
                    target_host_id=twin_target.get().strip(),at=now,
                )
            twin_result["value"]=json.dumps(
                report,indent=2,default=str,
            )
            twin_view.refresh()

        ttk.Button(
            frames["Fleet"],
            text="Inspect sources / run synthetic failure (read only)",
            command=self.guarded(run_homelab_twin),
        ).pack(anchor="w",pady=(4,8))

        self.identity_panel(frames["Sofía"])
        self.avatar_panel(frames["Avatar"])
        from .wardrobe_panel import WardrobePanel, current_mood
        self.wardrobe = WardrobePanel(self, frames["Wardrobe"])
        self.viewer(frames["Mood & Emotion"], "Current mood and emotions toward Sparks", lambda: current_mood(config.state_path), interval_ms=15000)
        from sofia.neuro.store import neuro_observability_text
        self.viewer(
            frames["NEURO"],
            "Live attention, homeostasis, routing, and recent signals",
            lambda: neuro_observability_text(config.state_path),
            interval_ms=5000,
        )
        ttk.Label(
            frames["NEURO"],
            text=(
                "NEURO ranks bounded observations only. A high score is not "
                "evidence, consent, permission, memory promotion, or authority."
            ),
            wraplength=660,
        ).pack(anchor="w", pady=8)
        from .goals_panel import GoalsPanel
        self.goals = GoalsPanel(self, frames["Goals"])
        self.memory_panel(frames["Memory"])
        self.sql_panel(frames["World"], "Persistent spaces", "world_space")
        self.sql_panel(frames["World"], "Scene objects and inventory", "world_object")
        self.sql_panel(frames["World"], "World revision history", "world_revision")
        self.sql_panel(frames["World"], "Avatar and object interaction receipts", "world_interaction_receipt")
        from .creative_panel import CreativePanel
        self.creative = CreativePanel(self, frames["Creative"])
        self.viewer(
            frames["Life & Projects"],
            "Canonical LIFE / NEURO / ACT operator snapshot",
            self.autonomy_snapshot,
            interval_ms=15000,
        )
        self.sql_panel(frames["Life & Projects"], "Independent projects", "life_project")
        self.sql_panel(frames["Life & Projects"], "Project decisions and history", "life_project_event")
        self.sql_panel(frames["Life & Projects"], "Milestones", "life_project_milestone")
        self.sql_panel(frames["Life & Projects"], "Artifact critiques", "life_artifact_evaluation")
        self.sql_panel(frames["Life & Projects"], "Experience journal and scrapbook", "life_experience")
        self.sql_panel(frames["Life & Projects"], "Activity and inactivity choices", "life_selection")
        self.sql_panel(frames["Life & Projects"], "Resource usage", "life_resource_usage")
        self.sql_panel(frames["Preferences"], "Evidence-backed preference revisions", "personality_preference_revision")
        self.sql_panel(frames["Preferences"], "Nickname proposals and feedback", "rel_nickname_proposal")
        self.sql_panel(frames["Preferences"], "Nickname lifecycle evidence", "rel_nickname_event")
        self.sql_panel(frames["EVOLVE"], "Reviewed revisions", "evolve_reviewed_revisions")
        self.sql_panel(frames["EVOLVE"], "Configuration authority records", "state_plane_record", where="namespace='configuration'")
        self.sql_panel(frames["EVOLVE"], "Autonomous activity queue", "autonomous_work_job")
        self.sql_panel(frames["EVOLVE"], "Autonomous work plans", "autonomous_work_plan")
        self.sql_panel(frames["EVOLVE"], "Autonomous plan steps", "autonomous_work_plan_step")
        self.sql_panel(frames["EVOLVE"], "Autonomous work history", "autonomous_work_event")
        self.sql_panel(frames["EVOLVE"], "Improvement diagnostics", "autonomous_improvement_diagnostic")
        self.sql_panel(frames["EVOLVE"], "Development candidates", "state_plane_record", where="namespace='dev-candidate'")
        ttk.Label(frames["EVOLVE"], text="Inspect recorded revision evidence and configuration authority above. Changes to governed configuration continue through the reviewed EVOLVE approval workflow.", wraplength=660).pack(anchor="w", pady=8)
        self.safety_panel(frames["Safety & Authority"])
        self.advanced_panel(frames["Advanced"])

    def group(self, parent, key, title, value):
        ttk, tk = self.ttk, self.tk
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.pack(fill="x", pady=6)
        variables = {}
        for field in fields(value):
            default = getattr(value, field.name)
            label = field.name.replace("_", " ").capitalize()
            if key == "outreach" and field.name == "quiet_start_local":
                label = "Quiet hours start (local hour, 0–23)"
            elif key == "outreach" and field.name == "quiet_end_local":
                label = "Quiet hours end (local hour, 0–23)"
            elif key == "outreach" and field.name == "delivery_channel":
                label = "Delivery channel"
            if isinstance(default, tuple):
                label += " (comma-separated)"
            if type(default) is bool:
                variable = tk.BooleanVar(self.root, value=default)
                ttk.Checkbutton(frame, text=label, variable=variable).pack(anchor="w", pady=3)
            else:
                variable = tk.StringVar(self.root, value=", ".join(default) if isinstance(default, tuple) else "" if default is None else str(default))
                ttk.Label(frame, text=label).pack(anchor="w", pady=(6, 2))
                if key == "outreach" and field.name == "delivery_channel":
                    ttk.Combobox(frame, textvariable=variable, values=("desktop", "mobile", "discord", "home_assistant"), state="readonly").pack(fill="x")
                elif key == "outreach" and field.name in {"quiet_start_local", "quiet_end_local"}:
                    ttk.Combobox(frame, textvariable=variable, values=tuple(str(hour) for hour in range(24)), state="readonly").pack(fill="x")
                elif field.name == "authority":
                    ttk.Combobox(frame, textvariable=variable, values=("none", "operator_approved", "standing_policy"), state="readonly").pack(fill="x")
                else:
                    ttk.Entry(frame, textvariable=variable).pack(fill="x")
            variables[field.name] = variable
        self.groups[key] = (value, variables)

    def updates(self):
        result = {name: variable.get() for name, variable in self.variables.items()}
        for name, kind in (("provider_temperature", float), ("provider_seed", int), ("provider_max_output_tokens", int)):
            value = result[name].strip()
            try:
                result[name] = kind(value) if value else None
            except ValueError as exc:
                raise ValueError(f"{name.replace('_', ' ')} must be numeric") from exc
        result["avatar_daily_outfit"] = result["avatar_daily_outfit"] or None
        result["voice_output_name"] = result["voice_output_name"] or None
        result["voice_input_device"] = result["voice_input_device"] or None
        for key, (initial, variables) in self.groups.items():
            result[key] = type(initial)(**{name: parse_field(variable.get(), getattr(initial, name), name) for name, variable in variables.items()})
        return result

    def guarded(self, action):
        def invoke():
            try:
                return action()
            except Exception as exc:
                self.messagebox.showerror("Operation failed", f"{type(exc).__name__}: {exc}", parent=self.root)
        return invoke

    def viewer(self, parent, title, read, *, interval_ms=None):
        frame = self.ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(fill="x", pady=8)
        text = self.tk.Text(frame, height=9, wrap="word")
        scroll = self.ttk.Scrollbar(frame, command=text.yview)
        scroll.pack(side="right", fill="y")
        text.configure(yscrollcommand=scroll.set)
        text.pack(fill="x")
        def refresh():
            value = read()
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", value)
            text.configure(state="disabled")
        self.ttk.Button(frame, text="Refresh", command=self.guarded(refresh)).pack(anchor="w", pady=4)
        frame.refresh = self.guarded(refresh)
        frame.refresh()
        if interval_ms is not None:
            def tick():
                if frame.winfo_exists():
                    frame.refresh()
                    self.root.after(interval_ms, tick)
            self.root.after(interval_ms, tick)
        return frame

    def identity_panel(self, parent):
        def read():
            parts = []
            for label, path in (("Identity", self.config.identity_path), ("Personality", self.config.personality_path)):
                parts.append(f"{label}:\n" + (path.read_text(encoding="utf-8-sig") if path.is_file() else "No persisted definition"))
            return "\n\n".join(parts)
        self.viewer(parent, "Current identity and personality", read)

    def autonomy_snapshot(self) -> str:
        """Read-only status from existing owners, without a shadow truth store.

        Everything historical is labelled as a last recorded observation,
        never as an unverified claim of current execution or delivery.
        """
        output = ["Source: canonical sofia.db; no actions performed."]
        with closing(self._canonical_state.connect(timeout=10)) as db:
            def present(table: str) -> bool:
                return db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone() is not None

            if present("safe_operator_stop"):
                state = db.execute(
                    "SELECT active, updated_at, reason FROM safe_operator_stop "
                    "WHERE singleton=1"
                ).fetchone()
                output.append(
                    ("Owner stop: " + ("PAUSED" if state[0] else "not active")
                     + f" (recorded {state[1]}; {state[2]})")
                    if state else "Owner stop: UNKNOWN (no canonical row)"
                )
            else:
                output.append("Owner stop: UNKNOWN (no canonical row)")

            selection = None
            if present("life_selection"):
                selection = db.execute(
                    "SELECT kind, project_id, reason, resource_pressure, "
                    "busy, selected_at FROM life_selection "
                    "ORDER BY selected_at DESC, selection_id DESC LIMIT 1"
                ).fetchone()
            if selection is None:
                output.append("LIFE last selection: UNKNOWN (no recorded selection)")
                output.append("Resource pressure: UNKNOWN (no recorded sample)")
            else:
                kind, project_id, reason, pressure, busy, at = selection
                output.append(
                    f"LIFE last selection: {kind}, project={project_id or 'none'}; "
                    f"recorded={at}; reason={str(reason)[:250]}"
                )
                output.append(
                    f"Resource pressure at selection: {pressure}; busy={bool(busy)} "
                    f"(historical, not a live measurement)"
                )

            if present("life_project"):
                from sofia.life.coordinator import SOFIA_PROJECT_OWNER, LOCAL_AUDIENCE
                project = db.execute(
                    "SELECT project_id, name, status, updated_at "
                    "FROM life_project WHERE owner_principal_id=? AND audience_id=? "
                    "ORDER BY updated_at DESC,project_id DESC LIMIT 1",
                    (SOFIA_PROJECT_OWNER, LOCAL_AUDIENCE),
                ).fetchone()
                output.append(
                    f"LIFE last project: {project[1]} [{project[2]}], "
                    f"id={project[0]}, recorded={project[3]}"
                    if project else "LIFE projects: none recorded"
                )
                if project and present("life_project_milestone"):
                    milestone = db.execute(
                        "SELECT title,status,updated_at FROM life_project_milestone "
                        "WHERE project_id=? ORDER BY updated_at DESC, ordinal DESC LIMIT 1",
                        (project[0],),
                    ).fetchone()
                    output.append(
                        f"Latest milestone: {milestone[0]} [{milestone[1]}], "
                        f"recorded={milestone[2]}"
                        if milestone else "Milestones: none recorded"
                    )

            if present("act_system_notice"):
                queued = db.execute(
                    "SELECT COUNT(*) FROM act_system_notice WHERE status='queued'"
                ).fetchone()[0]
                output.append(f"ACT pending system notices: {queued} (queue records)")
            else:
                output.append("ACT pending system notices: UNKNOWN (no source table)")
            if present("interact_queued_messages"):
                queued = db.execute(
                    "SELECT COUNT(*) FROM interact_queued_messages WHERE status='queued'"
                ).fetchone()[0]
                output.append(f"INTERACT pending messages: {queued} (queue records)")
            if present("act_outreach_trace"):
                decision = db.execute(
                    "SELECT stage,reason,recorded_at,receipt_id,recipient_confirmed "
                    "FROM act_outreach_trace ORDER BY trace_id DESC LIMIT 1"
                ).fetchone()
                output.append(
                    f"ACT last decision: stage={decision[0]}, reason={decision[1]}, "
                    f"recorded={decision[2]}, transport_receipt={decision[3] or 'none'}, "
                    f"recipient_confirmed={bool(decision[4])}"
                    if decision else "ACT last decision: none recorded"
                )

        from sofia.neuro.store import neuro_observability_text
        try:
            neuro = neuro_observability_text(self.config.state_path)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
            output.append(
                f"NEURO projection unavailable: {type(exc).__name__} (UNKNOWN)"
            )
        else:
            output.append("NEURO recorded projection:\n" + str(neuro)[:1600])
        return "\n".join(output)

    def sql_panel(self, parent, title, table, *, where="1=1"):
        # Names and predicates originate solely from the static callers above.
        def read():
            with closing(self._canonical_state.connect(timeout=10)) as db:
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is None:
                    return "No records yet."
                db.row_factory = sqlite3.Row
                rows = db.execute(f'SELECT * FROM "{table}" WHERE {where} LIMIT 200').fetchall()
            return json.dumps([dict(row) for row in rows], indent=2, default=lambda value: value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)) if rows else "No records yet."
        self.viewer(parent, title + " (up to 200 records)", read)

    def avatar_panel(self, parent):
        from sofia.avatar.wardrobe_review import WardrobeReviewStore
        catalog = WardrobeReviewStore(self.config.state_path).catalog()
        outfits = tuple(plan.outfit_id for plan in catalog.presets if not plan.private_only)
        value = self.tk.StringVar(self.root, value=self.runtime.avatar_daily_outfit or "")
        self.variables["avatar_daily_outfit"] = value
        self.ttk.Label(parent, text="Daily outfit on restart (blank retains current daily attire)").pack(anchor="w", pady=(8, 2))
        self.ttk.Combobox(parent, textvariable=value, values=("", *outfits), state="readonly").pack(fill="x")
        self.sql_panel(parent, "Current presentation", "avatar_presentation_state")
        self.sql_panel(parent, "Cross-modal expression decisions", "expression_decision")
        self.viewer(parent, "Public wardrobe presets", lambda: "\n\n".join(f"{plan.outfit_id}\nGarments: {', '.join(plan.item_ids)}" for plan in catalog.presets if not plan.private_only))

    def memory_panel(self, parent):
        from sofia.memory.provenance import CandidateStatus
        from sofia.memory.provenance_store import DurableMemoryCandidateStore
        from sofia.application.memory_review import MemoryReviewService
        from sofia.conversation.store import ConversationStore
        from sofia.social.principals import (
            SPARKS_PRINCIPAL_ID, local_sparks_principal,
        )
        from uuid import UUID
        self.ttk.Label(
            parent,
            text="Review original evidence before promotion. Corrections preserve "
                 "both versions and atomically revoke the superseded fact.",
            wraplength=660,
        ).pack(anchor="w")
        choice = self.tk.StringVar(self.root)
        combo = self.ttk.Combobox(parent, textvariable=choice, state="readonly")
        combo.pack(fill="x", pady=8)
        superseded_choice = self.tk.StringVar(self.root)
        self.ttk.Label(
            parent, text="Promoted fact to supersede with selected proposal"
        ).pack(anchor="w")
        original_combo = self.ttk.Combobox(
            parent, textvariable=superseded_choice, state="readonly",
        )
        original_combo.pack(fill="x", pady=8)
        self.ttk.Label(
            parent, text="Memory expires at (ISO 8601 timezone-aware; blank to clear)"
        ).pack(anchor="w")
        expiration_input = self.tk.StringVar(self.root)
        self.ttk.Entry(parent, textvariable=expiration_input).pack(fill="x")
        self.ttk.Label(
            parent, text="Review reason (required, 500 characters maximum)"
        ).pack(anchor="w")
        expiration_reason = self.tk.StringVar(self.root)
        self.ttk.Entry(parent, textvariable=expiration_reason).pack(fill="x", pady=6)

        def candidates(action):
            store = DurableMemoryCandidateStore(self.config.state_path)
            try:
                return action(store)
            finally:
                store.close()

        def refresh():
            ids, promoted = candidates(lambda store: (
                store.list_ids(
                    principal_id=SPARKS_PRINCIPAL_ID,
                    audience_id="local:text",
                ),
                store.list_ids(
                    status=CandidateStatus.PROMOTED,
                    principal_id=SPARKS_PRINCIPAL_ID,
                    audience_id="local:text",
                ),
            ))
            choices = tuple(str(value) for value in ids)
            combo.configure(values=choices)
            if choice.get() not in choices:
                choice.set(choices[0] if choices else "")
            older = tuple(str(value) for value in promoted)
            original_combo.configure(values=older)
            if superseded_choice.get() not in older:
                superseded_choice.set(older[0] if older else "")
            if not choice.get():
                return "No owner memory candidates."

            def read(store):
                key = UUID(choice.get())
                candidate = store.get(key)
                lineage = store.correction_link(key)
                return (
                    f"Status: {store.status(key).value}\n"
                    f"Content: {candidate.content}\n"
                    f"Correction lineage: {lineage or 'none'}\n"
                    f"Reviewed expiry: {store.expiration(key) or 'none'}\n"
                    f"Eligible now: {store.is_recall_eligible(key)}\n\n"
                    "Original evidence:\n" +
                    "\n\n".join(
                        f"{source.message_id} ({source.role})\n{source.content}"
                        for source in candidate.sources
                    )
                )
            return candidates(read)

        frame = self.viewer(parent, "Candidate and original evidence", refresh)
        combo.bind("<<ComboboxSelected>>", lambda event: frame.refresh())

        def change(action):
            refresh()
            if not choice.get():
                raise ValueError("Select a candidate")
            if self.messagebox.askyesno(
                "Confirm memory review",
                f"{action.capitalize()} candidate {choice.get()}?\n\n"
                "Review the original evidence in the panel before confirming.",
                parent=self.root,
            ):
                def transition(store):
                    key = UUID(choice.get())
                    if key not in store.list_ids(
                        principal_id=SPARKS_PRINCIPAL_ID,
                        audience_id="local:text",
                    ):
                        raise PermissionError("Candidate is outside owner scope")
                    if action == "promote":
                        originals = ConversationStore(self.config.state_path)
                        try:
                            review = MemoryReviewService(
                                conversation_store=originals,
                                candidate_store=store,
                                state_path=self.config.state_path,
                            )
                            review.promote(
                                key, approved_by=local_sparks_principal(),
                            )
                        finally:
                            originals.close()
                    else:
                        getattr(store, action)(key)
                candidates(transition)
                self.messagebox.showinfo(
                    "Memory review", "Review recorded durably. Refresh to see its status.",
                    parent=self.root,
                )

        def link_correction():
            refresh()
            if not choice.get() or not superseded_choice.get():
                raise ValueError("Select a proposed replacement and promoted original")
            replacement_id = UUID(choice.get())
            old_id = UUID(superseded_choice.get())
            def evidence(store):
                new = store.get(replacement_id)
                old = store.get(old_id)
                if new is None or old is None:
                    raise LookupError("Correction source candidate is missing")
                if (
                    replacement_id not in store.list_ids(
                        status=CandidateStatus.PROPOSED,
                        principal_id=SPARKS_PRINCIPAL_ID,
                        audience_id="local:text",
                    )
                    or old_id not in store.list_ids(
                        status=CandidateStatus.PROMOTED,
                        principal_id=SPARKS_PRINCIPAL_ID,
                        audience_id="local:text",
                    )
                ):
                    raise PermissionError("Correction candidates are not eligible")
                return old.content, new.content
            old_text, new_text = candidates(evidence)
            if self.messagebox.askyesno(
                "Review memory correction",
                "Link these exact facts for atomic correction upon later promotion?\n\n"
                f"CURRENT: {old_text[:700]}\n\n"
                f"PROPOSED: {new_text[:700]}\n\n"
                "No status changes occur until the replacement is promoted.",
                parent=self.root,
            ):
                candidates(lambda store: store.link_correction(replacement_id, old_id))
                self.messagebox.showinfo(
                    "Memory correction",
                    "Correction evidence linked. Promote the proposed replacement "
                    "after final review to supersede the old fact atomically.",
                    parent=self.root,
                )

        def update_expiration():
            from datetime import datetime
            selected = choice.get()
            if not selected:
                raise ValueError("Select a promoted memory")
            raw_deadline = expiration_input.get().strip()
            reason = expiration_reason.get().strip()
            if not 1 <= len(reason) <= 500:
                raise ValueError("Review reason must be 1..500 characters")
            deadline = None if not raw_deadline else datetime.fromisoformat(
                raw_deadline.replace("Z", "+00:00")
            )
            if deadline is not None and (
                deadline.tzinfo is None or deadline.utcoffset() is None
            ):
                raise ValueError("Expiration requires an explicit timezone")
            candidate_id = UUID(selected)

            def check_candidate(store):
                if candidate_id not in store.list_ids(
                    status=CandidateStatus.PROMOTED,
                    principal_id=SPARKS_PRINCIPAL_ID,
                    audience_id="local:text",
                ):
                    raise PermissionError("Only reviewed, promoted owner memory can expire")
                return store.get(candidate_id).content

            original = candidates(check_candidate)
            described = (
                "Clear the reviewed expiration"
                if deadline is None else f"Expire this fact at {deadline.isoformat()}"
            )
            if self.messagebox.askyesno(
                "Confirm memory validity review",
                f"{described}?\n\nMemory: {original[:700]}\n\n"
                f"Reason: {reason[:500]}\n\nOriginal source evidence is retained.",
                parent=self.root,
            ):
                candidates(lambda store: store.set_expiration(
                    candidate_id,
                    expires_at=deadline,
                    reviewed_by=SPARKS_PRINCIPAL_ID,
                    reason=reason,
                ))
                self.messagebox.showinfo(
                    "Memory validity",
                    "Reviewed time validity recorded in canonical memory; "
                    "original evidence remains unchanged.",
                    parent=self.root,
                )
                frame.refresh()

        for action in ("promote", "reject", "revoke"):
            self.ttk.Button(
                frame, text=action.capitalize(),
                command=self.guarded(lambda action=action: change(action)),
            ).pack(side="left", padx=4)
        self.ttk.Button(
            frame, text="Link correction", command=self.guarded(link_correction),
        ).pack(side="left", padx=4)
        self.ttk.Button(
            frame, text="Review expiration",
            command=self.guarded(update_expiration),
        ).pack(side="left", padx=4)

    def safety_panel(self, parent):
        from sofia.safe.operator_stop import OperatorStopStore
        store = OperatorStopStore(self.config.state_path)
        self.viewer(parent, "Operator stop", lambda: str(store.current()))
        reason = self.tk.StringVar(self.root, value="Owner request from Settings")
        self.ttk.Label(parent, text="Reason for changing operator stop").pack(anchor="w")
        self.ttk.Entry(parent, textvariable=reason).pack(fill="x")
        def change(active):
            if self.messagebox.askyesno("Operator stop", "Pause consequential actions?" if active else "Resume actions subject to their existing approvals?", parent=self.root):
                store.set(active=active, updated_by="Sparks", reason=reason.get())
                self.messagebox.showinfo("Operator stop", "Stop state saved. Refresh to see the current state.", parent=self.root)
        for active, label in ((True, "Pause actions"), (False, "Resume actions")):
            self.ttk.Button(parent, text=label, command=self.guarded(lambda active=active: change(active))).pack(anchor="w", pady=4)
        self.viewer(parent, "Standing inspected capabilities", lambda: "\n".join(self.config.standing_allowed_capabilities))
        from sofia.safe.review import compact_policy_review
        from sofia.safe.permissions import PermissionStore, grantable_capabilities
        self.viewer(
            parent, "SAFE declared capability and standing-grant audit",
            lambda: compact_policy_review(
                tuple(sorted(
                    set(grantable_capabilities())
                    | set(self.config.standing_allowed_capabilities)
                )),
                PermissionStore(self.config.state_path),
            ),
        )

    def advanced_panel(self, parent):
        from pathlib import Path
        from tkinter import filedialog
        self.viewer(parent, "Database diagnostics", lambda: database_diagnostics(self.config.state_path))
        from sofia.ops.state_mobility import describe_state_candidates
        self.viewer(
            parent, "Known local state candidates (not verified canonical homes)",
            lambda: describe_state_candidates(Path(self.config.state_path)),
        )
        def preview_relocation():
            from pathlib import Path
            from sofia.ops.state_mobility import relocation_preflight_text
            directory = filedialog.askdirectory(
                parent=self.root, title="Select proposed local Sofía state home",
            )
            if directory:
                self.messagebox.showinfo(
                    "Sofía state relocation preflight (read only)",
                    relocation_preflight_text(
                        Path(self.config.state_path), Path(directory),
                    ),
                    parent=self.root,
                )
        self.ttk.Button(
            parent, text="Preview state relocation (does not move files)…",
            command=self.guarded(preview_relocation),
        ).pack(anchor="w", pady=6)
        self.viewer(parent, "Saved settings (protected token values excluded)", lambda: json.dumps(json.loads(RuntimeUserSettingsStore._encode(RuntimeUserSettingsStore(self.config.state_path).load())), indent=2))
        def export():
            target = filedialog.asksaveasfilename(parent=self.root, title="Export saved settings", defaultextension=".json", filetypes=(("JSON", "*.json"),))
            if target:
                from pathlib import Path
                from sofia.state.atomic_file import atomic_write_text
                atomic_write_text(Path(target), RuntimeUserSettingsStore._encode(RuntimeUserSettingsStore(self.config.state_path).load()))
        self.ttk.Button(parent, text="Export saved settings…", command=self.guarded(export)).pack(anchor="w", pady=6)
