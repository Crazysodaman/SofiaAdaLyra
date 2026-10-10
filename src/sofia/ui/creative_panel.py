"""Authenticated local creative-project explorer and text revision editor."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sofia.creative import (
    ArtifactKind,
    CreativeExplorer,
    CreativeProject,
    CreativeRequest,
    CreativeService,
    CreativeStore,
    CreativeWorkspaceManager,
    ManagedAssetStore,
    NativeCreativeAdapter,
)
from sofia.social.principals import SPARKS_PRINCIPAL_ID


class CreativePanel:
    """Expose only Sparks's local/private project partition to the desktop UI."""

    _AUDIENCE = "local:text"
    _EDITABLE = frozenset((ArtifactKind.TEXT, ArtifactKind.STORY))

    def __init__(self, sections, parent) -> None:
        self.sections = sections
        self.tk, self.ttk, self.root = sections.tk, sections.ttk, sections.root
        self.store = CreativeStore(sections.config.state_path)
        creative_root = Path(sections.config.state_path).parent / "creative"
        self.service = CreativeService(
            self.store,
            CreativeWorkspaceManager(creative_root / "workspaces"),
            ManagedAssetStore(creative_root / "assets"),
        )
        self.explorer = CreativeExplorer(self.store)
        self.projects = {}
        self.artifacts = {}

        self.project_choice = self.tk.StringVar(self.root)
        self.artifact_choice = self.tk.StringVar(self.root)
        self.revision_choice = self.tk.StringVar(self.root)
        self.project_title = self.tk.StringVar(self.root)
        self.artifact_title = self.tk.StringVar(self.root)

        controls = self.ttk.LabelFrame(parent, text="Projects", padding=8)
        controls.pack(fill="x", pady=6)
        self.project_combo = self.ttk.Combobox(
            controls, textvariable=self.project_choice, state="readonly",
        )
        self.project_combo.pack(fill="x", pady=3)
        self.project_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_artifacts())
        self.ttk.Entry(controls, textvariable=self.project_title).pack(fill="x", pady=3)
        self.ttk.Button(
            controls, text="Create private project",
            command=sections.guarded(self.create_project),
        ).pack(anchor="w", pady=3)

        inventory = self.ttk.LabelFrame(parent, text="Artifact inventory", padding=8)
        inventory.pack(fill="x", pady=6)
        self.artifact_combo = self.ttk.Combobox(
            inventory, textvariable=self.artifact_choice, state="readonly",
        )
        self.artifact_combo.pack(fill="x", pady=3)
        self.artifact_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_artifact())
        self.revision_combo = self.ttk.Combobox(
            inventory, textvariable=self.revision_choice, state="readonly",
        )
        self.revision_combo.pack(fill="x", pady=3)

        self.ttk.Label(parent, text="Artifact title").pack(anchor="w")
        self.ttk.Entry(parent, textvariable=self.artifact_title).pack(fill="x", pady=3)
        self.editor = self.tk.Text(parent, height=14, wrap="word")
        self.editor.pack(fill="both", expand=True, pady=5)

        buttons = self.ttk.Frame(parent)
        buttons.pack(fill="x")
        for label, action in (
            ("Refresh", self.refresh),
            ("New text artifact", self.new_text),
            ("Save text revision", self.save_revision),
            ("Recover selected revision", self.recover_revision),
        ):
            self.ttk.Button(
                buttons, text=label, command=sections.guarded(action),
            ).pack(side="left", padx=3, pady=4)
        self.refresh()

    def _project_id(self) -> str:
        label = self.project_choice.get()
        if label not in self.projects:
            raise ValueError("Select a creative project")
        return self.projects[label].project_id

    def refresh(self) -> None:
        projects = self.store.list_projects(SPARKS_PRINCIPAL_ID, self._AUDIENCE)
        self.projects = {f"{item.title} — {item.project_id}": item for item in projects}
        values = tuple(self.projects)
        self.project_combo.configure(values=values)
        if self.project_choice.get() not in self.projects:
            self.project_choice.set(values[0] if values else "")
        self.refresh_artifacts()

    def create_project(self) -> None:
        title = self.project_title.get().strip()
        if not title:
            raise ValueError("Enter a project title")
        self.store.create_project(CreativeProject(
            f"project-{uuid4().hex}", title, SPARKS_PRINCIPAL_ID,
            self._AUDIENCE, datetime.now(timezone.utc),
        ))
        self.project_title.set("")
        self.refresh()

    def refresh_artifacts(self) -> None:
        self.artifacts = {}
        if self.project_choice.get() in self.projects:
            project_id = self.projects[self.project_choice.get()].project_id
            values = self.explorer.list_project(
                project_id, owner_principal_id=SPARKS_PRINCIPAL_ID,
                audience_id=self._AUDIENCE,
            )
            self.artifacts = {
                f"{item.title} — {item.artifact_id} ({item.kind.value})": item
                for item in values
            }
        choices = tuple(self.artifacts)
        self.artifact_combo.configure(values=choices)
        if self.artifact_choice.get() not in self.artifacts:
            self.artifact_choice.set(choices[0] if choices else "")
        self.load_artifact()

    def load_artifact(self) -> None:
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        selected = self.artifacts.get(self.artifact_choice.get())
        if selected is None:
            self.artifact_title.set("")
            self.revision_combo.configure(values=())
            self.revision_choice.set("")
            return
        self.artifact_title.set(selected.title)
        history = self.explorer.history(
            selected.artifact_id, owner_principal_id=SPARKS_PRINCIPAL_ID,
            audience_id=self._AUDIENCE,
        )
        revisions = tuple(str(item.revision) for item in history)
        self.revision_combo.configure(values=revisions)
        self.revision_choice.set(str(selected.revision))
        path, media_type = self.explorer.verified_preview(
            selected.artifact_id, owner_principal_id=SPARKS_PRINCIPAL_ID,
            audience_id=self._AUDIENCE,
        )
        if selected.kind in self._EDITABLE and selected.byte_size <= 1_000_000:
            self.editor.insert("1.0", path.read_text(encoding="utf-8"))
        else:
            self.editor.insert(
                "1.0",
                f"Verified {selected.kind.value} artifact\nMedia: {media_type}\n"
                f"Bytes: {selected.byte_size}\nSHA-256: {selected.content_sha256}\n"
                f"Tool: {selected.tool_id} {selected.tool_version}",
            )
            self.editor.configure(state="disabled")

    def new_text(self) -> None:
        self._project_id()
        self.artifact_choice.set("")
        self.artifact_title.set("New text artifact")
        self.revision_choice.set("")
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")

    def save_revision(self) -> None:
        project_id = self._project_id()
        selected = self.artifacts.get(self.artifact_choice.get())
        if selected is not None and selected.kind not in self._EDITABLE:
            raise ValueError("This built-in editor only revises text and story artifacts")
        title = self.artifact_title.get().strip()
        content = self.editor.get("1.0", "end-1c")
        if not title or not content.strip():
            raise ValueError("Title and content are required")
        artifact_id = selected.artifact_id if selected else f"artifact-{uuid4().hex}"
        kind = selected.kind if selected else ArtifactKind.TEXT
        license_id = selected.license_id if selected else "private"
        moment = datetime.now(timezone.utc)
        self.service.create(CreativeRequest(
            f"request-{uuid4().hex}", project_id, artifact_id, kind, title,
            SPARKS_PRINCIPAL_ID, SPARKS_PRINCIPAL_ID, self._AUDIENCE,
            license_id, {"content": content},
            f"ui:creative-edit:{uuid4().hex}",
        ), NativeCreativeAdapter(), now=moment)
        self.refresh_artifacts()

    def recover_revision(self) -> None:
        selected = self.artifacts.get(self.artifact_choice.get())
        if selected is None or not self.revision_choice.get():
            raise ValueError("Select an artifact revision")
        target = int(self.revision_choice.get())
        if not self.sections.messagebox.askyesno(
            "Recover creative revision",
            f"Restore revision {target} of {selected.title} as a new revision?",
            parent=self.root,
        ):
            return
        self.explorer.recover(
            selected.artifact_id, target_revision=target,
            owner_principal_id=SPARKS_PRINCIPAL_ID,
            audience_id=self._AUDIENCE,
            evidence_ref=f"ui:creative-recover:{uuid4().hex}",
            now=datetime.now(timezone.utc),
        )
        self.refresh_artifacts()
