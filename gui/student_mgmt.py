"""
student_mgmt.py — Student Management page
View, search, edit, and delete registered students.
Password-protected destructive actions.
"""

import customtkinter as ctk
from tkinter import messagebox

from utils.helpers import PALETTE, Toast


class StudentManagementPage(ctk.CTkFrame):
    """
    Scrollable list of registered students with inline edit and delete.
    """

    def __init__(self, parent, db, engine, root):
        super().__init__(parent, fg_color=PALETTE["bg"], corner_radius=0)
        self.db     = db
        self.engine = engine
        self.root   = root

        self._selected_id: str | None = None
        self._students:    list[dict] = []

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_list_panel()
        self._build_detail_panel()
        self._refresh_list()

    # ------------------------------------------------------------------
    # Left: student list
    # ------------------------------------------------------------------

    def _build_list_panel(self):
        panel = ctk.CTkFrame(
            self, fg_color=PALETTE["card"],
            width=300, corner_radius=0,
        )
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        # Header
        ctk.CTkLabel(
            panel, text="👥  Students",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        # Search
        self._search = ctk.CTkEntry(
            panel, placeholder_text="🔍  Search by name or ID…",
            height=36, corner_radius=8,
            fg_color=PALETTE["card2"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=12),
        )
        self._search.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")
        self._search.bind("<KeyRelease>", lambda _: self._filter_list())

        # Scrollable list
        self._list_frame = ctk.CTkScrollableFrame(
            panel, fg_color="transparent", corner_radius=0
        )
        self._list_frame.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self._list_frame.grid_columnconfigure(0, weight=1)

        # Count label
        self._count_lbl = ctk.CTkLabel(
            panel, text="",
            font=ctk.CTkFont(size=11),
            text_color=PALETTE["text_secondary"],
        )
        self._count_lbl.grid(row=3, column=0, padx=10, pady=(0, 8))

    # ------------------------------------------------------------------
    # Right: detail / edit panel
    # ------------------------------------------------------------------

    def _build_detail_panel(self):
        panel = ctk.CTkFrame(self, fg_color=PALETTE["bg"], corner_radius=0)
        panel.grid(row=0, column=1, sticky="nsew", padx=24, pady=24)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        # Top header
        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="Student Details",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            hdr, text="Select a student from the list to view or edit.",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        ).grid(row=1, column=0, sticky="w")

        # Detail card
        self._detail_card = ctk.CTkFrame(
            panel,
            fg_color=PALETTE["card"],
            corner_radius=14,
            border_width=1,
            border_color=PALETTE["border"],
        )
        self._detail_card.grid(row=1, column=0, sticky="nsew")
        self._detail_card.grid_columnconfigure(1, weight=1)

        # Avatar / icon area
        self._avatar_lbl = ctk.CTkLabel(
            self._detail_card, text="👤",
            font=ctk.CTkFont(size=64),
        )
        self._avatar_lbl.grid(row=0, column=0, columnspan=2, pady=(30, 8))

        self._detail_name = ctk.CTkLabel(
            self._detail_card, text="Select a student",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETTE["text"],
        )
        self._detail_name.grid(row=1, column=0, columnspan=2, pady=(0, 4))

        self._detail_id = ctk.CTkLabel(
            self._detail_card, text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["text_secondary"],
        )
        self._detail_id.grid(row=2, column=0, columnspan=2, pady=(0, 16))

        # Separator
        ctk.CTkFrame(
            self._detail_card, fg_color=PALETTE["border"], height=1
        ).grid(row=3, column=0, columnspan=2, sticky="ew", padx=20)

        # Editable fields
        def field(label, row):
            ctk.CTkLabel(
                self._detail_card, text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=PALETTE["text_secondary"], anchor="w",
            ).grid(row=row, column=0, padx=(24, 8), pady=(14, 2), sticky="w")
            e = ctk.CTkEntry(
                self._detail_card, height=38, corner_radius=8,
                fg_color=PALETTE["card2"], border_color=PALETTE["border"],
                text_color=PALETTE["text"], font=ctk.CTkFont(size=13),
                state="disabled",
            )
            e.grid(row=row, column=1, padx=(0, 24), pady=(14, 2), sticky="ew")
            return e

        self._e_name  = field("Full Name",   4)
        self._e_dept  = field("Department",  5)
        self._e_year  = field("Year",        6)
        self._e_sec   = field("Section",     7)

        # Image count
        self._img_lbl = ctk.CTkLabel(
            self._detail_card, text="",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        )
        self._img_lbl.grid(row=8, column=0, columnspan=2, pady=(10, 0))

        # Action buttons
        btn_row = ctk.CTkFrame(self._detail_card, fg_color="transparent")
        btn_row.grid(row=9, column=0, columnspan=2, pady=(16, 20))

        self._edit_btn = ctk.CTkButton(
            btn_row, text="✏️  Edit",
            width=110, height=40, corner_radius=8,
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled",
            command=self._edit_student,
        )
        self._edit_btn.pack(side="left", padx=8)

        self._save_btn = ctk.CTkButton(
            btn_row, text="💾  Save",
            width=110, height=40, corner_radius=8,
            fg_color=PALETTE["success"], hover_color="#27ae60",
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled",
            command=self._save_student,
        )
        self._save_btn.pack(side="left", padx=8)

        self._del_btn = ctk.CTkButton(
            btn_row, text="🗑️  Delete",
            width=110, height=40, corner_radius=8,
            fg_color=PALETTE["danger"], hover_color="#c0392b",
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled",
            command=self._delete_student,
        )
        self._del_btn.pack(side="left", padx=8)

        self._toast = Toast(self._detail_card, row=10, col=0, columnspan=2)

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _refresh_list(self):
        self._students = self.db.get_all_students()
        self._filter_list()

    def _filter_list(self):
        q = self._search.get().strip().lower()
        filtered = [
            s for s in self._students
            if q in s["Name"].lower() or q in s["StudentID"].lower()
        ] if q else self._students

        for w in self._list_frame.winfo_children():
            w.destroy()

        self._count_lbl.configure(text=f"{len(filtered)} student(s)")

        for stu in filtered:
            card = ctk.CTkButton(
                self._list_frame,
                text=f"{stu['Name']}\n{stu['StudentID']}  •  {stu['Department']}",
                font=ctk.CTkFont(size=12),
                height=56, corner_radius=8, anchor="w",
                fg_color=PALETTE["card2"],
                hover_color=PALETTE["accent_dim"],
                text_color=PALETTE["text"],
                command=lambda s=stu: self._select_student(s),
            )
            card.pack(fill="x", padx=4, pady=2)

    def _select_student(self, stu: dict):
        self._selected_id = stu["StudentID"]
        self._load_detail(stu)

    def _load_detail(self, stu: dict):
        self._detail_name.configure(text=stu["Name"])
        self._detail_id.configure(
            text=f"ID: {stu['StudentID']}   •   Registered: {stu['RegisteredDate'][:10]}"
        )

        for entry, val in [
            (self._e_name, stu["Name"]),
            (self._e_dept, stu["Department"]),
            (self._e_year, stu["Year"]),
            (self._e_sec,  stu["Section"]),
        ]:
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, val)
            entry.configure(state="disabled")

        count = self.engine.image_count(stu["StudentID"])
        self._img_lbl.configure(text=f"📷 {count} training images captured")

        self._edit_btn.configure(state="normal")
        self._del_btn.configure(state="normal")
        self._save_btn.configure(state="disabled")

    # ------------------------------------------------------------------
    # Edit / Save / Delete
    # ------------------------------------------------------------------

    def _edit_student(self):
        for e in (self._e_name, self._e_dept, self._e_year, self._e_sec):
            e.configure(state="normal")
        self._save_btn.configure(state="normal")
        self._edit_btn.configure(state="disabled")

    def _save_student(self):
        if not self._selected_id:
            return
        name = self._e_name.get().strip()
        dept = self._e_dept.get().strip()
        year = self._e_year.get().strip()
        sec  = self._e_sec.get().strip()

        if not all([name, dept, year, sec]):
            self._toast.show("All fields are required.", PALETTE["danger"])
            return

        ok, msg = self.db.update_student(self._selected_id, name, dept, year, sec)
        self._toast.show(msg, PALETTE["success"] if ok else PALETTE["danger"])

        for e in (self._e_name, self._e_dept, self._e_year, self._e_sec):
            e.configure(state="disabled")
        self._save_btn.configure(state="disabled")
        self._edit_btn.configure(state="normal")

        self._refresh_list()
        stu = self.db.get_student_by_id(self._selected_id)
        if stu:
            self._detail_name.configure(text=stu["Name"])

    def _delete_student(self):
        if not self._selected_id:
            return

        # Ask for admin password
        self._confirm_delete_dialog(self._selected_id)

    def _confirm_delete_dialog(self, student_id: str):
        stu = self.db.get_student_by_id(student_id)
        if not stu:
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Confirm Delete")
        dlg.geometry("380x260")
        dlg.resizable(False, False)
        dlg.configure(fg_color=PALETTE["card"])
        dlg.grab_set()

        ctk.CTkLabel(
            dlg, text="⚠️  Delete Student",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=PALETTE["danger"],
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            dlg,
            text=f"This will permanently delete\n'{stu['Name']}' ({student_id})\nand all their attendance records.",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text"],
        ).pack(pady=8)

        ctk.CTkLabel(
            dlg, text="Enter admin password to confirm:",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        ).pack(pady=(8, 2))

        pwd_entry = ctk.CTkEntry(
            dlg, show="*", width=200, height=36, corner_radius=8,
            fg_color=PALETTE["card2"], border_color=PALETTE["border"],
            text_color=PALETTE["text"],
        )
        pwd_entry.pack(pady=4)

        err_lbl = ctk.CTkLabel(
            dlg, text="",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["danger"],
        )
        err_lbl.pack(pady=2)

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(pady=12)

        def _do_delete():
            pwd = pwd_entry.get()
            admin_pwd = self.db.get_setting("admin_password", "admin123")
            if pwd != admin_pwd:
                err_lbl.configure(text="Incorrect password!")
                return

            # Delete from DB + dataset
            self.db.delete_student(student_id)
            self.engine.delete_student_images(student_id)

            dlg.destroy()
            self._selected_id = None
            self._detail_name.configure(text="Select a student")
            self._detail_id.configure(text="")
            self._img_lbl.configure(text="")
            for e in (self._e_name, self._e_dept, self._e_year, self._e_sec):
                e.configure(state="normal")
                e.delete(0, "end")
                e.configure(state="disabled")
            self._edit_btn.configure(state="disabled")
            self._del_btn.configure(state="disabled")
            self._save_btn.configure(state="disabled")
            self._refresh_list()
            self._toast.show("Student deleted. Retrain the model.", PALETTE["warning"])

        ctk.CTkButton(
            btn_row, text="Delete", width=100, height=36,
            fg_color=PALETTE["danger"], hover_color="#c0392b",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=_do_delete,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_row, text="Cancel", width=100, height=36,
            fg_color=PALETTE["card2"], hover_color=PALETTE["border"],
            text_color=PALETTE["text"],
            command=dlg.destroy,
        ).pack(side="left", padx=8)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_show(self):
        self._refresh_list()

    def on_hide(self):
        pass
