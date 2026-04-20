"""History browser (tkinter). Search, view, copy, delete, export."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pyperclip

from voxflow.history import History


class HistoryWindow:
    def __init__(self, history: History) -> None:
        self.history = history
        self.root: tk.Tk | None = None
        self.tree: ttk.Treeview | None = None
        self.var_search = None
        self.txt_detail: tk.Text | None = None

    def show(self) -> None:
        self.root = tk.Tk()
        self.root.title("VoxFlow — History")
        self.root.geometry("800x560")

        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        self.var_search = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.var_search, width=40)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self._refresh())
        ttk.Button(top, text="Search", command=self._refresh).pack(side="left")
        ttk.Button(top, text="Export...", command=self._export).pack(side="right")
        ttk.Button(top, text="Clear all", command=self._clear_all).pack(side="right", padx=6)

        body = ttk.PanedWindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.Frame(body)
        self.tree = ttk.Treeview(
            left, columns=("when", "lang", "preview"), show="headings", selectmode="browse"
        )
        self.tree.heading("when", text="When")
        self.tree.heading("lang", text="Lang")
        self.tree.heading("preview", text="Preview")
        self.tree.column("when", width=140, stretch=False)
        self.tree.column("lang", width=50, stretch=False)
        self.tree.column("preview", width=360)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        body.add(left, weight=2)

        right = ttk.Frame(body)
        self.txt_detail = tk.Text(right, wrap="word")
        self.txt_detail.pack(fill="both", expand=True)
        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=6)
        ttk.Button(actions, text="Copy", command=self._copy_selected).pack(side="left")
        ttk.Button(actions, text="Delete", command=self._delete_selected).pack(side="left", padx=6)
        body.add(right, weight=3)

        self._refresh()
        self.root.mainloop()

    # ----- data -----
    def _refresh(self) -> None:
        assert self.tree is not None
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        search = (self.var_search.get() if self.var_search else "") or None
        entries = self.history.list(limit=500, search=search)
        for e in entries:
            preview = (e["final_text"] or "")[:80].replace("\n", " ")
            when = e["created_at"][:19].replace("T", " ")
            self.tree.insert("", "end", iid=str(e["id"]),
                             values=(when, e.get("language") or "", preview))
        if self.txt_detail is not None:
            self.txt_detail.delete("1.0", "end")

    def _selected_id(self) -> int | None:
        if self.tree is None:
            return None
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _on_select(self, _event=None) -> None:
        sid = self._selected_id()
        if sid is None or self.txt_detail is None:
            return
        entries = self.history.list(limit=500)
        entry = next((e for e in entries if e["id"] == sid), None)
        self.txt_detail.delete("1.0", "end")
        if entry is None:
            return
        self.txt_detail.insert("end", f"{entry['created_at']}  ({entry.get('language') or 'auto'})\n")
        self.txt_detail.insert("end", f"Duration: {entry.get('duration_s', 0):.2f}s\n\n")
        self.txt_detail.insert("end", "--- Final ---\n")
        self.txt_detail.insert("end", (entry.get("final_text") or "") + "\n\n")
        self.txt_detail.insert("end", "--- Raw ---\n")
        self.txt_detail.insert("end", entry.get("raw_text") or "")

    def _copy_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            return
        entries = self.history.list(limit=500)
        entry = next((e for e in entries if e["id"] == sid), None)
        if entry:
            pyperclip.copy(entry.get("final_text") or "")

    def _delete_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            return
        self.history.delete(sid)
        self._refresh()

    def _clear_all(self) -> None:
        if messagebox.askyesno("Clear history", "Delete ALL transcription history?"):
            self.history.clear()
            self._refresh()

    def _export(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export history",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt")],
        )
        if not path:
            return
        entries = self.history.list(limit=10000)
        lines: list[str] = []
        is_md = path.lower().endswith(".md")
        for e in entries:
            when = e["created_at"][:19].replace("T", " ")
            if is_md:
                lines.append(f"### {when}  _(lang: {e.get('language') or 'auto'})_")
            else:
                lines.append(f"[{when}] ({e.get('language') or 'auto'})")
            lines.append(e.get("final_text") or "")
            lines.append("")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        messagebox.showinfo("Export", f"Exported {len(entries)} entries to:\n{path}")
