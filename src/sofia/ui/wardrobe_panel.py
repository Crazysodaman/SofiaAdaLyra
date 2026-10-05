"""Catalog browser and structured wardrobe submission editor."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import uuid4

from sofia.avatar.wardrobe_review import WardrobeReviewStore, document
from sofia.emotion.journal import EmotionalJournal
from sofia.social.model import SocialScope
from sofia.social.principals import SPARKS_PRINCIPAL_ID


def current_mood(state_path) -> str:
    """Read the same decaying relationship projection used by conversation."""
    journal = EmotionalJournal(state_path)
    now = datetime.now(timezone.utc)
    scope = SocialScope.relationship(SPARKS_PRINCIPAL_ID)
    state = journal.current_state(now=now, subject=SPARKS_PRINCIPAL_ID, scope=scope)
    events = journal.recent(now=now, days=7, limit=50, subject=SPARKS_PRINCIPAL_ID, scope=scope)
    latest = max((event.occurred_at for event in events), default=None)
    lines = [f"Mood: {state.tone}", f"As of: {state.as_of.isoformat()}", f"Latest observation: {latest.isoformat() if latest else 'No emotional observations yet'}"]
    for emotion in state.active:
        lines.append(f"{emotion.name}: {emotion.intensity:.0%} intensity")
        lines.append("Evidence: " + ", ".join(emotion.evidence_refs))
    if not state.active:
        lines.append("No active emotions in the current projection.")
    return "\n".join(lines)


class WardrobePanel:
    def __init__(self, sections, parent):
        self.sections = sections
        self.tk, self.ttk, self.root = sections.tk, sections.ttk, sections.root
        self.store = WardrobeReviewStore(sections.config.state_path)
        self.catalog = self.store.catalog()
        self.selected = None
        self.entries = {}
        self.kind = "garment"
        self.template = None
        self.status = self.tk.StringVar(self.root, value="Submissions are reviewed by the running Sofía application. Accepted metadata updates her live wardrobe and survives restart.")
        self.ttk.Label(parent, textvariable=self.status, wraplength=660).pack(anchor="w", pady=6)
        self.tabs = self.ttk.Notebook(parent)
        self.tabs.pack(fill="both", expand=True)
        browse, edit, reviews = (self.ttk.Frame(self.tabs, padding=8) for _ in range(3))
        for frame, name in ((browse, "Items & outfits"), (edit, "Editor"), (reviews, "Review queue")):
            self.tabs.add(frame, text=name)
        self.filter = self.tk.StringVar(self.root)
        self.ttk.Label(browse, text="Search by name, ID or garment type").pack(anchor="w")
        self.ttk.Entry(browse, textvariable=self.filter).pack(fill="x", pady=5)
        self.tree = self.ttk.Treeview(browse, columns=("kind", "name", "detail"), show="headings", height=12)
        for column, label, width in (("kind", "Type", 70), ("name", "Name", 230), ("detail", "ID / garment type", 330)):
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, stretch=True)
        scroll = self.ttk.Scrollbar(browse, command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", lambda event: self.select())
        self.filter.trace_add("write", lambda *args: self.populate())
        self.details_frame = self.sections.viewer(browse, "Selected design / outfit metadata", lambda: json.dumps(self.selected[1], indent=2) if self.selected else "Select an item or outfit.")
        for label, action in (("Refresh catalog", self.refresh), ("Edit selected", self.edit_selected), ("New item", lambda: self.new("garment")), ("New outfit", lambda: self.new("outfit"))):
            self.ttk.Button(browse, text=label, command=sections.guarded(action)).pack(anchor="w", pady=3)
        self.editor_title = self.tk.StringVar(self.root, value="Select a catalog entry to edit, or create a new item/outfit.")
        self.ttk.Label(edit, textvariable=self.editor_title, wraplength=650).pack(anchor="w")
        self.editor_frame = self.ttk.Frame(edit)
        self.editor_frame.pack(fill="x")
        self.ttk.Button(edit, text="Submit to Sofía for approval", command=sections.guarded(self.submit)).pack(anchor="w", pady=10)
        self.review_choice = self.tk.StringVar(self.root)
        self.review_combo = self.ttk.Combobox(reviews, textvariable=self.review_choice, state="readonly")
        self.review_combo.pack(fill="x", pady=6)
        self.review_frame = self.sections.viewer(reviews, "Decision, reason and submitted design", self.review_details, interval_ms=15000)
        self.review_combo.bind("<<ComboboxSelected>>", lambda event: self.review_frame.refresh())
        self.ttk.Button(reviews, text="Retry failed review", command=sections.guarded(self.retry)).pack(anchor="w", pady=4)
        self.review_input = self.tk.StringVar(self.root)
        self.ttk.Label(reviews, text="Your preference input when Sofía asks a question").pack(anchor="w")
        self.ttk.Entry(reviews, textvariable=self.review_input).pack(fill="x", pady=4)
        self.ttk.Button(reviews, text="Reply to Sofía’s question", command=sections.guarded(self.supply_input)).pack(anchor="w", pady=4)
        self.refresh()

    def populate(self):
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        query = self.filter.get().casefold().strip()
        for blueprint in self.catalog.blueprints:
            value = document(blueprint.design)
            key = "garment:" + value["item_id"]
            if not query or query in f"{value['item_id']} {value['name']} {value['garment_type']}".casefold():
                self.tree.insert("", "end", iid=key, values=("Item", value["name"], f"{value['item_id']} / {value['garment_type']}"))
                self.rows[key] = ("garment", value)
        for outfit in self.catalog.presets:
            value = document(outfit)
            key = "outfit:" + value["outfit_id"]
            if not query or query in f"{value['outfit_id']} {value['display_name']}".casefold():
                self.tree.insert("", "end", iid=key, values=("Outfit", value["display_name"] or value["outfit_id"], value["outfit_id"]))
                self.rows[key] = ("outfit", value)

    def select(self):
        choice = self.tree.selection()
        self.selected = self.rows.get(choice[0]) if choice else None
        self.details_frame.refresh()

    def refresh(self):
        self.catalog = self.store.catalog()
        self.populate()
        self.selected = None
        self.details_frame.refresh()
        self.review_frame.refresh()

    def edit_selected(self):
        if self.selected is None:
            raise ValueError("Select an item or outfit")
        self.edit(*self.selected)

    def new(self, kind):
        template = document(next(value.design for value in self.catalog.blueprints if not value.private_only)) if kind == "garment" else document(self.catalog.preset("day.default"))
        template["item_id" if kind == "garment" else "outfit_id"] = f"custom.{kind}.{uuid4().hex[:10]}"
        template["name" if kind == "garment" else "display_name"] = "New wardrobe item" if kind == "garment" else "New outfit"
        if kind == "outfit":
            template["manual_only"] = True
        self.edit(kind, template)

    def edit(self, kind, value):
        self.kind, self.template = kind, deepcopy(value)
        self.entries = {}
        for widget in self.editor_frame.winfo_children():
            widget.destroy()
        self.editor_title.set("Editing item design" if kind == "garment" else "Editing outfit composition")
        def controls(parent, raw, prefix=()):
            for key, initial in raw.items():
                path = (*prefix, key)
                label = key.replace("_", " ").capitalize()
                if isinstance(initial, dict):
                    frame = self.ttk.LabelFrame(parent, text=label, padding=8)
                    frame.pack(fill="x", pady=6)
                    controls(frame, initial, path)
                elif type(initial) is bool:
                    variable = self.tk.BooleanVar(self.root, value=initial)
                    self.ttk.Checkbutton(parent, text=label, variable=variable).pack(anchor="w", pady=3)
                    self.entries[path] = (variable, initial)
                else:
                    variable = self.tk.StringVar(self.root, value=", ".join(initial) if isinstance(initial, list) else "" if initial is None else str(initial))
                    self.ttk.Label(parent, text=label + (" (comma-separated)" if isinstance(initial, list) else "")).pack(anchor="w", pady=(6, 2))
                    self.ttk.Entry(parent, textvariable=variable).pack(fill="x")
                    self.entries[path] = (variable, initial)
        controls(self.editor_frame, self.template)
        if kind == "outfit":
            chooser = self.ttk.LabelFrame(self.editor_frame, text="Choose garments for the outfit (Ctrl/Shift selects multiple)", padding=8)
            chooser.pack(fill="x", pady=8)
            items = self.tk.Listbox(chooser, selectmode="extended", exportselection=False, height=10)
            scroll = self.ttk.Scrollbar(chooser, command=items.yview)
            scroll.pack(side="right", fill="y")
            items.configure(yscrollcommand=scroll.set)
            items.pack(fill="x")
            identifiers = tuple(blueprint.garment.item_id for blueprint in self.catalog.blueprints)
            for index, blueprint in enumerate(self.catalog.blueprints):
                items.insert("end", f"{blueprint.design.name} — {blueprint.garment.item_id}")
                if blueprint.garment.item_id in self.template["item_ids"]:
                    items.selection_set(index)
            def use_selected():
                self.entries[("item_ids",)][0].set(", ".join(identifiers[index] for index in items.curselection()))
            self.ttk.Button(chooser, text="Use selected garments", command=use_selected).pack(anchor="w", pady=5)
        self.tabs.select(1)

    def payload(self):
        if self.template is None:
            raise ValueError("Create or select a design first")
        result = deepcopy(self.template)
        for path, (variable, initial) in self.entries.items():
            raw = variable.get()
            if type(initial) is bool:
                value = bool(raw)
            elif isinstance(initial, list):
                value = [part.strip() for part in raw.split(",") if part.strip()]
            elif type(initial) in (int, float) or path[-1].endswith("_c"):
                value = float(raw) if str(raw).strip() else None
            elif initial is None:
                value = raw.strip() or None
            else:
                value = raw.strip()
            target = result
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
        return result

    def submit(self):
        key = self.store.submit(self.kind, self.payload())
        self.status.set(f"Submitted {key}. Pending Sofía’s review; the catalog remains unchanged until approval.")
        self.review_choice.set(key)
        self.review_frame.refresh()
        self.tabs.select(2)

    def review_details(self):
        reviews = self.store.list()
        keys = tuple(row["proposal_id"] for row in reviews)
        self.review_combo.configure(values=keys)
        if self.review_choice.get() not in keys:
            self.review_choice.set(keys[0] if keys else "")
        row = next((row for row in reviews if row["proposal_id"] == self.review_choice.get()), None)
        if row is None:
            return "No wardrobe submissions yet."
        return f"Status: {row['status']}\nSubmitted: {row['submitted_at']}\nReviewed: {row['reviewed_at'] or 'Awaiting review'}\nReason: {row['reason'] or 'No decision yet'}\n\nDesign:\n" + json.dumps(json.loads(row["payload_json"]), indent=2)

    def retry(self):
        self.store.retry(self.review_choice.get())
        self.status.set("Review queued again. Sofía’s running application will retry it.")

    def supply_input(self):
        self.store.supply_input(self.review_choice.get(), self.review_input.get())
        self.review_input.set("")
        self.status.set("Your preference input is queued. Sofía will make her own decision.")
