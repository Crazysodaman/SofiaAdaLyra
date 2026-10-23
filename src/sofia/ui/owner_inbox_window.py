"""Attended local approval inbox window.

This is an operator-only Windows session client. It is not a model tool,
remote WebAuthn bridge, or permission to execute effects on its own.
"""
from __future__ import annotations

from queue import Empty, Queue
from threading import Thread

from sofia.platform.safe.approval_inbox import ApprovalInbox
from sofia.platform.safe.owner_enroll_browser import require_owner_windows_account


def open_owner_inbox_window(state_path, *, parent=None):
    import tkinter as tk
    from tkinter import messagebox, ttk

    require_owner_windows_account(state_path)
    inbox = ApprovalInbox(state_path)
    root = tk.Toplevel(parent) if parent is not None else tk.Tk()
    root.title("Sofía | Owner approval inbox")
    root.geometry("850x540")
    root.minsize(620, 380)

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Pending owner approvals",
              font=("Segoe UI", 13, "bold")).pack(anchor="w")
    ttk.Label(
        frame, text="Each action needs its own attended security-key signature. "
                    "A queue entry never grants permission.",
        wraplength=790,
    ).pack(anchor="w", pady=(3, 10))

    requests = tk.Listbox(frame, height=9, exportselection=False)
    requests.pack(fill="both", expand=True)
    review = tk.Text(frame, height=8, wrap="word", state="disabled")
    review.pack(fill="both", expand=True, pady=(8, 4))
    result = tk.StringVar(value="No approval selected.")
    ttk.Label(frame, textvariable=result, wraplength=790).pack(
        anchor="w", pady=(4, 6),
    )

    button_row = ttk.Frame(frame)
    button_row.pack(fill="x")
    cache = []
    work = Queue()
    busy = {"active": False}

    def selected():
        index = requests.curselection()
        return cache[index[0]] if index and index[0] < len(cache) else None

    def refresh():
        nonlocal cache
        try:
            inbox.recover()
            current = inbox.list_requests(limit=100)
            keep = selected()
            cache = list(current)
            requests.delete(0, tk.END)
            for item in cache:
                requests.insert(tk.END, f"{item.status.upper():9}  "
                                f"{item.capability}   {item.request_id[:8]} "
                                f"(expires {item.expires_at.astimezone().strftime('%m/%d %I:%M %p')})")
            if keep is not None:
                for i, item in enumerate(cache):
                    if item.request_id == keep.request_id:
                        requests.selection_set(i)
                        break
            display_selected()
        except (OSError, RuntimeError, PermissionError, ValueError) as exc:
            result.set(f"SAFE inbox unavailable: {type(exc).__name__}: {exc}")

    def display_selected(_event=None):
        item = selected()
        import json
        content = ("Select a request to review its exact parameters."
                   if item is None else
                   json.dumps({
                       "request_id": item.request_id, "capability": item.capability,
                       "parameters": item.parameters, "fingerprint": item.fingerprint,
                       "status": item.status, "expires_at": item.expires_at.isoformat(),
                   }, indent=2, sort_keys=True, ensure_ascii=False))
        review.configure(state="normal")
        review.delete("1.0", tk.END)
        review.insert("1.0", content)
        review.configure(state="disabled")

    requests.bind("<<ListboxSelect>>", display_selected)

    def approve():
        if busy["active"]:
            return
        item = selected()
        if item is None or item.status != "pending":
            result.set("Select a pending request.")
            return
        if not messagebox.askyesno(
            "Review exact action", "Approve only the selected action and target? "
            "Your FIDO2 key and PIN/biometric verification will be required.",
            parent=root,
        ):
            return
        try:
            from sofia.platform.safe.owner_approval_ui import select_security_key_for_settings
            credential = select_security_key_for_settings(state_path, parent=root)
        except (PermissionError, OSError, RuntimeError, ValueError) as exc:
            result.set(f"Cannot begin security-key review: {exc}")
            return
        busy["active"] = True
        result.set("Awaiting owner-presence FIDO2 browser ceremony...")
        def worker():
            try:
                approved = inbox.approve_attended(
                    item.request_id, credential_id=credential,
                )
                work.put((True, approved.request_id))
            except Exception as exc:
                work.put((False, f"{type(exc).__name__}: {exc}"))
        Thread(target=worker, name="sofia-owner-inbox-attended",
               daemon=False).start()

    def deny():
        item = selected()
        if item is None or item.status not in ("pending", "reviewing"):
            result.set("Select an unapproved request.")
            return
        if not messagebox.askyesno("Reject approval",
                                    "Reject this pending request?",
                                    parent=root):
            return
        try:
            inbox.deny_attended(item.request_id)
            result.set("Owner rejected the request. No authority granted.")
            refresh()
        except (OSError, PermissionError, ValueError) as exc:
            messagebox.showerror("SAFE denial failed", str(exc), parent=root)

    ttk.Button(button_row, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(button_row, text="Review with FIDO2", command=approve).pack(
        side="left", padx=8,
    )
    ttk.Button(button_row, text="Deny", command=deny).pack(side="left")

    def poll():
        try:
            success, detail = work.get_nowait()
        except Empty:
            pass
        else:
            busy["active"] = False
            result.set("Owner approval signed: " + detail if success else
                       "Approval refused: " + detail)
            refresh()
        if root.winfo_exists():
            root.after(350, poll)

    def pump_notifications():
        # Durable events are acknowledged only after delivery to this owner UI.
        # The outbox may redeliver after a crash; event_id is the dedupe key.
        received = []
        try:
            inbox.deliver_notifications(lambda event: received.append(event))
            if received:
                last = received[-1]
                result.set(
                    f"{len(received)} owner inbox event(s); latest: "
                    f"{last.event_type} for {last.capability} "
                    f"(event #{last.event_id})."
                )
                refresh()
        except (OSError, PermissionError, RuntimeError, ValueError) as exc:
            result.set(f"Notification delivery deferred: {exc}")
        if root.winfo_exists():
            root.after(5000, pump_notifications)

    refresh()
    root.after(350, poll)
    root.after(1500, pump_notifications)
    if parent is None:
        root.mainloop()
    return root
