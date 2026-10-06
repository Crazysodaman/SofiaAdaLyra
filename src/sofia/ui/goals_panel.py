"""Authenticated local-owner projection and lifecycle controls for goals."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from sofia.goals import GoalEvidenceIndex, GoalEvidenceLedger, GoalService, GoalStore
from sofia.goals.model import GoalOrigin, GoalRunState, GoalStatus
from sofia.goals.policy import effective_priority
from sofia.social.principals import local_sparks_principal
from sofia.state.sqlite_plane import SQLiteStatePlane


class GoalsPanel:
    def __init__(self, sections, parent) -> None:
        self.sections = sections
        self.tk, self.ttk, self.root = sections.tk, sections.ttk, sections.root
        self.path = sections.config.state_path
        self.principal = local_sparks_principal()
        self.service = GoalService(
            GoalStore(SQLiteStatePlane(self.path)),
            evidence_verifier=GoalEvidenceIndex(self.path),
        )
        self.ledger = GoalEvidenceLedger(self.path)
        self.rows = {}
        self.status = self.tk.StringVar(self.root, value="")
        self.ttk.Label(
            parent,
            text=(
                "Canonical goals visible to the authenticated local Sparks audience. "
                "These controls use GoalService lifecycle validation and never grant "
                "capability permission."
            ),
            wraplength=680,
        ).pack(anchor="w", pady=6)
        columns = ("status", "origin", "priority", "run", "title")
        self.tree = self.ttk.Treeview(
            parent, columns=columns, show="headings", height=12,
        )
        for name, label, width in (
            ("status", "Status", 90), ("origin", "Origin", 80),
            ("priority", "Priority", 75), ("run", "RUN state", 140),
            ("title", "Goal", 310),
        ):
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, stretch=name == "title")
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.details.refresh())
        buttons = self.ttk.Frame(parent)
        buttons.pack(fill="x", pady=5)
        for label, action in (
            ("Pause USER", lambda: self.change("pause")),
            ("Resume USER", lambda: self.change("resume")),
            ("Cancel USER", lambda: self.change("cancel")),
            ("Approve SELF", lambda: self.change("approve")),
            ("Reject SELF", lambda: self.change("reject")),
            ("Refresh", self.refresh),
        ):
            self.ttk.Button(
                buttons, text=label, command=sections.guarded(action),
            ).pack(side="left", padx=(0, 5))
        self.details = sections.viewer(
            parent, "Selected goal details", self.detail_text,
        )
        self.ttk.Label(parent, textvariable=self.status, wraplength=680).pack(anchor="w")
        self.refresh()

    def _selected(self):
        selected = self.tree.selection()
        if len(selected) != 1 or selected[0] not in self.rows:
            raise ValueError("select exactly one visible goal")
        return self.rows[selected[0]]

    def _evidence(self, now: datetime) -> str:
        ref = f"goal-ui:{uuid4()}"
        self.ledger.record(
            evidence_ref=ref,
            kind="authenticated_ui_action",
            observed_at=now,
            source="tray-settings",
            principal_id=self.principal.principal_id,
            audience=(
                f"{self.principal.audience_kind.value}:"
                f"{self.principal.audience_id}"
            ),
        )
        return ref

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.rows = {goal.id: goal for goal in self.service.list_visible(self.principal)}
        now = datetime.now(timezone.utc)
        for goal in sorted(
            self.rows.values(),
            key=lambda item: (-self._priority(item, now).value, item.id),
        ):
            priority = self._priority(goal, now)
            self.tree.insert("", "end", iid=goal.id, values=(
                goal.status.value, goal.origin.value, f"{priority.value:.3f}",
                goal.run_state.value, goal.title,
            ))
        self.status.set(f"{len(self.rows)} visible canonical goal(s).")

    def detail_text(self) -> str:
        try:
            goal = self._selected()
        except ValueError:
            return "Select a goal."
        now = datetime.now(timezone.utc)
        priority = self._priority(goal, now)
        children = tuple(
            item.id for item in self.rows.values() if item.parent_goal_id == goal.id
        )
        return "\n".join((
            f"ID: {goal.id}", f"Title: {goal.title}",
            f"Origin / owner: {goal.origin.value} / {goal.owner_principal_id}",
            f"Status / RUN: {goal.status.value} / {goal.run_state.value}",
            f"Base / effective priority: {goal.base_priority:.3f} / {priority.value:.3f}",
            "Priority reasons: " + "; ".join(priority.reasons),
            f"Reason: {goal.reason}", f"Created: {goal.created_at.isoformat()}",
            f"Deadline/expiration: {goal.expires_at.isoformat() if goal.expires_at else 'none'}",
            f"Completion: {goal.completion.kind.value} — {goal.completion.description}",
            f"Current blocker: {goal.blocked_reason or 'none'}",
            f"Parent: {goal.parent_goal_id or 'none'}",
            "Children: " + (", ".join(children) or "none"),
            f"Evidence count: {len(goal.evidence_refs)}",
        ))

    def _priority(self, goal, now):
        fallback = effective_priority(goal, now=now)
        with sqlite3.connect(self.path, timeout=10) as db:
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='goal_priority_evaluation'"
            ).fetchone() is None:
                return fallback
            row = db.execute(
                "SELECT score,reasons_json FROM goal_priority_evaluation "
                "WHERE goal_id=? AND principal_id=? AND audience=?",
                (goal.id, goal.scope_principal_id or "", goal.scope_audience or ""),
            ).fetchone()
        if row is None or row[0] is None or row[1] is None:
            return fallback
        return type(fallback)(float(row[0]), tuple(json.loads(row[1])))

    def change(self, operation: str) -> None:
        goal = self._selected()
        now = datetime.now(timezone.utc)
        ref = self._evidence(now)
        if operation in {"approve", "reject"}:
            changed = self.service.review_self_candidate(
                goal=goal, approve=operation == "approve",
                principal=self.principal, evidence_refs=(ref,), now=now,
            )
        else:
            if goal.origin is not GoalOrigin.USER:
                raise PermissionError("only USER goals use pause/resume/cancel controls")
            expected, target = {
                "pause": (GoalStatus.ACTIVE, GoalStatus.PAUSED),
                "resume": (GoalStatus.PAUSED, GoalStatus.ACTIVE),
                "cancel": (goal.status, GoalStatus.CANCELLED),
            }[operation]
            if goal.status is not expected:
                raise ValueError(f"goal is {goal.status.value}, not {expected.value}")
            changed = self.service.transition(
                goal_id=goal.id, principal_id=goal.scope_principal_id,
                audience=goal.scope_audience, expected_status=expected,
                next_status=target, actor_principal_id=self.principal.principal_id,
                authenticated_principal=self.principal, evidence_refs=(ref,), now=now,
                note=f"authenticated tray owner requested {operation}",
            )
            if operation == "resume":
                changed = self.service.set_run_state(
                    goal=changed, run_state=GoalRunState.PENDING_INSPECTION,
                    actor_principal_id=self.principal.principal_id, now=now,
                )
        self.status.set(f"{changed.title}: {changed.status.value}")
        self.refresh()
