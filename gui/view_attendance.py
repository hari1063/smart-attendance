"""
view_attendance.py — Attendance Reports page
Filter by date range, student ID, department. Export to CSV / Excel.
"""

import os
import customtkinter as ctk
from datetime import datetime, timedelta
from tkinter import filedialog

from utils.helpers import PALETTE, Toast, export_filename


COLS   = ["#", "Att. ID", "Student ID", "Name", "Department", "Date", "Time", "Status"]
WIDTHS = [35,   60,        100,          160,    140,           95,    70,     70]


class ViewAttendancePage(ctk.CTkFrame):
    """
    Attendance report view with filters, sortable table, and CSV/Excel export.
    """

    def __init__(self, parent, db, root):
        super().__init__(parent, fg_color=PALETTE["bg"], corner_radius=0)
        self.db   = db
        self.root = root

        self._records: list[dict] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_filters()
        self._build_table()
        self._load_records()

    # ------------------------------------------------------------------

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 4))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="📋  Attendance Reports",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, sticky="w")

        self._count_lbl = ctk.CTkLabel(
            hdr, text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["text_secondary"],
        )
        self._count_lbl.grid(row=1, column=0, sticky="w")

    def _build_filters(self):
        filt = ctk.CTkFrame(
            self,
            fg_color=PALETTE["card"],
            corner_radius=12,
            border_width=1,
            border_color=PALETTE["border"],
        )
        filt.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))

        # Row 0: date pickers + search
        def lbl(parent, text, row, col):
            ctk.CTkLabel(
                parent, text=text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=PALETTE["text_secondary"],
            ).grid(row=row, column=col, padx=(14, 4), pady=(12, 2), sticky="w")

        def entry(parent, row, col, placeholder="", width=140):
            e = ctk.CTkEntry(
                parent,
                placeholder_text=placeholder,
                width=width, height=36, corner_radius=8,
                fg_color=PALETTE["card2"],
                border_color=PALETTE["border"],
                text_color=PALETTE["text"],
                font=ctk.CTkFont(size=12),
            )
            e.grid(row=row, column=col, padx=(0, 10), pady=(0, 10), sticky="w")
            return e

        lbl(filt, "From Date",  0, 0)
        lbl(filt, "To Date",    0, 1)
        lbl(filt, "Student ID / Name", 0, 2)
        lbl(filt, "Department", 0, 3)

        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m-01")

        self._from_entry = entry(filt, 1, 0, month)
        self._to_entry   = entry(filt, 1, 1, today)
        self._sid_entry  = entry(filt, 1, 2, "Search…", 180)

        depts = ["All Departments"] + self.db.get_departments()
        self._dept_combo = ctk.CTkComboBox(
            filt, values=depts, width=180, height=36, corner_radius=8,
            fg_color=PALETTE["card2"], border_color=PALETTE["border"],
            text_color=PALETTE["text"], dropdown_fg_color=PALETTE["card"],
            dropdown_text_color=PALETTE["text"],
            font=ctk.CTkFont(size=12), state="readonly",
        )
        self._dept_combo.set("All Departments")
        self._dept_combo.grid(row=1, column=3, padx=(0, 10), pady=(0, 10))

        # Buttons
        btn_frame = ctk.CTkFrame(filt, fg_color="transparent")
        btn_frame.grid(row=1, column=4, padx=(0, 14), pady=(0, 10))

        ctk.CTkButton(
            btn_frame, text="🔍 Search", width=90, height=36, corner_radius=8,
            fg_color=PALETTE["accent"], hover_color=PALETTE["accent_hover"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._load_records,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame, text="↺ Reset", width=80, height=36, corner_radius=8,
            fg_color=PALETTE["card2"], hover_color=PALETTE["border"],
            text_color=PALETTE["text_secondary"],
            font=ctk.CTkFont(size=12),
            command=self._reset_filters,
        ).pack(side="left", padx=4)

        # Quick date presets
        preset_frame = ctk.CTkFrame(filt, fg_color="transparent")
        preset_frame.grid(row=2, column=0, columnspan=5, padx=14, pady=(0, 12), sticky="w")

        for txt, days in [("Today", 0), ("Last 7 days", 7), ("Last 30 days", 30), ("All time", -1)]:
            ctk.CTkButton(
                preset_frame, text=txt,
                width=100, height=28, corner_radius=6,
                fg_color=PALETTE["accent_dim"],
                hover_color=PALETTE["accent"],
                font=ctk.CTkFont(size=11),
                command=lambda d=days: self._apply_preset(d),
            ).pack(side="left", padx=4)

        # Export buttons
        exp_frame = ctk.CTkFrame(filt, fg_color="transparent")
        exp_frame.grid(row=2, column=3, columnspan=2, padx=(0, 14), pady=(0, 12), sticky="e")

        ctk.CTkButton(
            exp_frame, text="📄 Export CSV", width=120, height=28, corner_radius=6,
            fg_color=PALETTE["success"], hover_color="#27ae60",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._export_csv,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            exp_frame, text="📊 Export Excel", width=130, height=28, corner_radius=6,
            fg_color="#217346", hover_color="#1a5c38",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._export_excel,
        ).pack(side="left", padx=4)

        self._toast = Toast(filt, row=3, col=0, columnspan=5)

    def _build_table(self):
        container = ctk.CTkFrame(
            self,
            fg_color=PALETTE["card"],
            corner_radius=12,
            border_width=1,
            border_color=PALETTE["border"],
        )
        container.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        # Column header
        col_hdr = ctk.CTkFrame(container, fg_color=PALETTE["card2"])
        col_hdr.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))

        for i, (col, w) in enumerate(zip(COLS, WIDTHS)):
            ctk.CTkLabel(
                col_hdr, text=col, width=w,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=PALETTE["text_secondary"],
                anchor="w",
            ).grid(row=0, column=i, padx=(6, 0), pady=8, sticky="w")

        self._table = ctk.CTkScrollableFrame(
            container, fg_color="transparent", corner_radius=0
        )
        self._table.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_records(self):
        date_from  = self._from_entry.get().strip() or None
        date_to    = self._to_entry.get().strip()   or None
        student_id = self._sid_entry.get().strip()  or None
        dept       = self._dept_combo.get()
        if dept == "All Departments":
            dept = None

        self._records = self.db.get_attendance(
            date_from=date_from, date_to=date_to,
            student_id=student_id, department=dept,
        )
        self._render_table()

    def _render_table(self):
        for w in self._table.winfo_children():
            w.destroy()

        self._count_lbl.configure(
            text=f"{len(self._records)} record(s) found"
        )

        if not self._records:
            ctk.CTkLabel(
                self._table, text="No records found for the selected filters.",
                font=ctk.CTkFont(size=13),
                text_color=PALETTE["text_secondary"],
            ).pack(pady=30)
            return

        for row_num, rec in enumerate(self._records):
            bg = PALETTE["card"] if row_num % 2 == 0 else PALETTE["card2"]
            row_f = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=4)
            row_f.pack(fill="x", pady=1)

            values = [
                str(row_num + 1),
                str(rec.get("AttendanceID", "")),
                rec["StudentID"],
                rec["Name"],
                rec["Department"],
                rec["Date"],
                rec["Time"],
                rec["Status"],
            ]
            colors = [PALETTE["text_secondary"]] * 7 + [PALETTE["success"]]

            for i, (val, col, w) in enumerate(zip(values, colors, WIDTHS)):
                ctk.CTkLabel(
                    row_f, text=val, width=w,
                    font=ctk.CTkFont(size=11),
                    text_color=col, anchor="w",
                ).grid(row=0, column=i, padx=(6, 0), pady=5, sticky="w")

    # ------------------------------------------------------------------
    # Filters helpers
    # ------------------------------------------------------------------

    def _reset_filters(self):
        self._from_entry.delete(0, "end")
        self._to_entry.delete(0, "end")
        self._sid_entry.delete(0, "end")
        self._dept_combo.set("All Departments")
        self._load_records()

    def _apply_preset(self, days: int):
        today = datetime.now()
        self._to_entry.delete(0, "end")
        self._to_entry.insert(0, today.strftime("%Y-%m-%d"))
        self._from_entry.delete(0, "end")
        if days == 0:
            self._from_entry.insert(0, today.strftime("%Y-%m-%d"))
        elif days > 0:
            start = today - timedelta(days=days)
            self._from_entry.insert(0, start.strftime("%Y-%m-%d"))
        # else: leave blank for "all time"
        self._load_records()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_csv(self):
        if not self._records:
            self._toast.show("No records to export!", PALETTE["warning"])
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            initialdir=os.path.abspath("exports"),
        )
        if path:
            ok, msg = self.db.export_to_csv(path, self._records)
            self._toast.show(msg, PALETTE["success"] if ok else PALETTE["danger"])

    def _export_excel(self):
        if not self._records:
            self._toast.show("No records to export!", PALETTE["warning"])
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            initialdir=os.path.abspath("exports"),
        )
        if path:
            ok, msg = self.db.export_to_excel(path, self._records)
            self._toast.show(msg, PALETTE["success"] if ok else PALETTE["danger"])

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_show(self):
        # Refresh department list
        depts = ["All Departments"] + self.db.get_departments()
        self._dept_combo.configure(values=depts)
        self._load_records()

    def on_hide(self):
        pass
