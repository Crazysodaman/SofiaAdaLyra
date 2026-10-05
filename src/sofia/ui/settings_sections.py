"""Working settings controls and owner review panels for the tray UI."""
from __future__ import annotations

from contextlib import closing
from dataclasses import fields
import json
import os
import sqlite3

from sofia.config.user_settings import OutreachSettings, RuntimeUserSettingsStore
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
        self.variables = {}
        self.groups = {}
        self.messagebox = messagebox

        def boolean(section, field, label, default):
            variable = tk.BooleanVar(root, value=default)
            self.variables[field] = variable
            ttk.Checkbutton(frames[section], text=label, variable=variable).pack(anchor="w", pady=5)

        boolean("Chat", "adaptive_theme", "Adapt desktop colors to Sofía’s state", runtime.adaptive_theme)
        boolean("Sofía", "idle_reflections_enabled", "Enable idle reflection", runtime.idle_reflections_enabled if runtime.idle_reflections_enabled is not None else os.environ.get("SOFIA_IDLE_REFLECTIONS", "").lower() in ("1", "true", "on"))
        boolean("Sofía", "habit_learning_enabled", "Learn habits from supported observations", runtime.habit_learning_enabled if runtime.habit_learning_enabled is not None else os.environ.get("SOFIA_HABIT_LEARNING", "1").lower() in ("1", "true", "on"))
        boolean("Avatar", "avatar_routines_enabled", "Automatically select attire for supported routines", runtime.avatar_routines_enabled)

        for field, label in (("provider_temperature", "Generation temperature (blank uses provider default)"), ("provider_seed", "Generation seed (blank uses provider default)"), ("provider_max_output_tokens", "Maximum output tokens (blank uses provider default)")):
            value = getattr(runtime, field)
            variable = tk.StringVar(root, value="" if value is None else str(value))
            self.variables[field] = variable
            ttk.Label(frames["Models"], text=label).pack(anchor="w", pady=(8, 2))
            ttk.Entry(frames["Models"], textvariable=variable).pack(fill="x")

        outreach = runtime.outreach or OutreachSettings(
            enabled=os.environ.get("SOFIA_ACT_DELIVERY_ENABLED", "").lower() in ("1", "true", "yes", "on"),
            notification_service=os.environ.get("SOFIA_NOTIFICATION_HA_SERVICE", "").strip(),
            quiet_start_local=int(os.environ.get("SOFIA_ACT_QUIET_START_LOCAL", "22")),
            quiet_end_local=int(os.environ.get("SOFIA_ACT_QUIET_END_LOCAL", "8")),
            min_interval_minutes=int(os.environ.get("SOFIA_ACT_MIN_INTERVAL_MINUTES", "360")),
            max_daily=int(os.environ.get("SOFIA_ACT_MAX_DAILY", "1")),
        )
        self.group(frames["ACT"], "outreach", "Proactive outreach to Sparks via Home Assistant", outreach)
        ttk.Label(frames["ACT"], text="Enabling outreach requires a Home Assistant URL and protected token under Integrations. Quiet hours use the selected timezone; delivery still checks recipient, evidence, quotas and operator stop.", wraplength=660).pack(anchor="w", pady=8)
        self.group(frames["Fleet"], "fleet_cognition", "Cognitive placement", runtime.fleet_cognition or config.fleet_cognition)
        self.group(frames["Fleet"], "fleet_bootstrap", "Agent provisioning", runtime.fleet_bootstrap or config.fleet_bootstrap)
        ttk.Label(frames["Fleet"], text="Host IDs, targets and scopes are comma-separated. Discovery does not enroll hosts; provisioning requires the existing reviewed authority, package digest and signer.", wraplength=660).pack(anchor="w", pady=8)
        self.sql_panel(frames["Fleet"], "Enrolled nodes", "distributed_node_identity")
        self.identity_panel(frames["Sofía"])
        self.avatar_panel(frames["Avatar"])
        from .wardrobe_panel import WardrobePanel, current_mood
        self.wardrobe = WardrobePanel(self, frames["Wardrobe"])
        self.viewer(frames["Mood & Emotion"], "Current mood and emotions toward Sparks", lambda: current_mood(config.state_path), interval_ms=15000)
        self.memory_panel(frames["Memory"])
        self.sql_panel(frames["EVOLVE"], "Reviewed revisions", "evolve_reviewed_revisions")
        self.sql_panel(frames["EVOLVE"], "Configuration authority records", "state_plane_record", where="namespace='configuration'")
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
            if isinstance(default, tuple):
                label += " (comma-separated)"
            if type(default) is bool:
                variable = tk.BooleanVar(self.root, value=default)
                ttk.Checkbutton(frame, text=label, variable=variable).pack(anchor="w", pady=3)
            else:
                variable = tk.StringVar(self.root, value=", ".join(default) if isinstance(default, tuple) else "" if default is None else str(default))
                ttk.Label(frame, text=label).pack(anchor="w", pady=(6, 2))
                if field.name == "authority":
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

    def sql_panel(self, parent, title, table, *, where="1=1"):
        # Names and predicates originate solely from the static callers above.
        def read():
            with closing(sqlite3.connect(self.config.state_path, timeout=10)) as db:
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
        self.viewer(parent, "Public wardrobe presets", lambda: "\n\n".join(f"{plan.outfit_id}\nGarments: {', '.join(plan.item_ids)}" for plan in catalog.presets if not plan.private_only))

    def memory_panel(self, parent):
        from sofia.memory.provenance_store import DurableMemoryCandidateStore
        from sofia.social.principals import SPARKS_PRINCIPAL_ID
        from uuid import UUID
        self.ttk.Label(parent, text="Review exact evidence before promoting a candidate. Reject and revoke preserve the conversation originals.", wraplength=660).pack(anchor="w")
        choice = self.tk.StringVar(self.root)
        combo = self.ttk.Combobox(parent, textvariable=choice, state="readonly")
        combo.pack(fill="x", pady=8)
        def candidates(action):
            store = DurableMemoryCandidateStore(self.config.state_path)
            try:
                return action(store)
            finally:
                store.close()
        def refresh():
            ids = candidates(lambda store: store.list_ids(principal_id=SPARKS_PRINCIPAL_ID))
            combo.configure(values=tuple(str(value) for value in ids))
            if choice.get() not in tuple(str(value) for value in ids):
                choice.set(str(ids[0]) if ids else "")
            if not choice.get():
                return "No owner memory candidates."
            def read(store):
                key = UUID(choice.get())
                candidate = store.get(key)
                return f"Status: {store.status(key).value}\nContent: {candidate.content}\n\nOriginal evidence:\n" + "\n\n".join(f"{source.message_id} ({source.role})\n{source.content}" for source in candidate.sources)
            return candidates(read)
        frame = self.viewer(parent, "Candidate and original evidence", refresh)
        combo.bind("<<ComboboxSelected>>", lambda event: frame.refresh())
        def change(action):
            refresh()
            if not choice.get():
                raise ValueError("Select a candidate")
            if self.messagebox.askyesno("Confirm memory review", f"{action.capitalize()} candidate {choice.get()}?\n\nReview the original evidence in the panel before confirming.", parent=self.root):
                def transition(store):
                    key = UUID(choice.get())
                    if key not in store.list_ids(principal_id=SPARKS_PRINCIPAL_ID):
                        raise PermissionError("Candidate is outside owner scope")
                    getattr(store, action)(key)
                candidates(transition)
                self.messagebox.showinfo("Memory review", "Review recorded durably. Refresh to see its status.", parent=self.root)
        for action in ("promote", "reject", "revoke"):
            self.ttk.Button(frame, text=action.capitalize(), command=self.guarded(lambda action=action: change(action))).pack(side="left", padx=4)

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

    def advanced_panel(self, parent):
        from tkinter import filedialog
        self.viewer(parent, "Database diagnostics", lambda: database_diagnostics(self.config.state_path))
        self.viewer(parent, "Saved settings (protected token values excluded)", lambda: json.dumps(json.loads(RuntimeUserSettingsStore._encode(RuntimeUserSettingsStore(self.config.state_path).load())), indent=2))
        def export():
            target = filedialog.asksaveasfilename(parent=self.root, title="Export saved settings", defaultextension=".json", filetypes=(("JSON", "*.json"),))
            if target:
                from pathlib import Path
                from sofia.state.atomic_file import atomic_write_text
                atomic_write_text(Path(target), RuntimeUserSettingsStore._encode(RuntimeUserSettingsStore(self.config.state_path).load()))
        self.ttk.Button(parent, text="Export saved settings…", command=self.guarded(export)).pack(anchor="w", pady=6)
