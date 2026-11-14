"""
dashboard.py — Dashboard page for Smart Attendance System
Displays stat cards, today's attendance table, and quick-action buttons.
"""

import customtkinter as ctk
from datetime import datetime

from utils.helpers import PALETTE, friendly_date


# ── Stat card widget ───────────────────────────────────────────────────────────

class StatCard(ctk.CTkFrame):
    """A coloured metric card with icon, number, and label."""

    def __init__(self, parent, icon: str, title: str, value: str, color: str, **kw):
        super().__init__(
            parent,
            fg_color=PALETTE["card"],
            corner_radius=14,
            border_width=1,
            border_color=PALETTE["border"],
            **kw,
        )
        self.grid_columnconfigure(0, weight=1)

        # Accent bar at top
        bar = ctk.CTkFrame(self, fg_color=color, height=5, corner_radius=3)
        bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        icon_lbl = ctk.CTkLabel(
            self, text=icon, font=ctk.CTkFont(size=32),
            text_color=color,
        )
        icon_lbl.grid(row=1, column=0, pady=(14, 2))

        self.value_lbl = ctk.CTkLabel(
            self, text=value,
            font=ctk.CTkFont(family="Segoe UI", size=36, weight="bold"),
            text_color=PALETTE["text"],
        )
        self.value_lbl.grid(row=2, column=0, pady=2)

        ctk.CTkLabel(
            self, text=title,
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        ).grid(row=3, column=0, pady=(0, 14))

    def update_value(self, v: str):
        self.value_lbl.configure(text=v)


# ── Dashboard page ─────────────────────────────────────────────────────────────

class DashboardPage(ctk.CTkFrame):
    """Home page showing summary statistics and latest attendance."""

    REFRESH_MS = 30_000   # auto-refresh every 30 s

    def __init__(self, parent, db, engine, root):
        super().__init__(parent, fg_color=PALETTE["bg"], corner_radius=0)
        self.db     = db
        self.engine = engine
        self.root   = root

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_stat_cards()
        self._build_attendance_table()
        self._build_quick_actions()
        self._refresh()

    # ------------------------------------------------------------------

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="Dashboard",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, sticky="w")

        self._date_lbl = ctk.CTkLabel(
            hdr, text=friendly_date(datetime.now().strftime("%Y-%m-%d")),
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["text_secondary"],
        )
        self._date_lbl.grid(row=1, column=0, sticky="w")

    def _build_stat_cards(self):
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=8)
        for i in range(4):
            cards_frame.grid_columnconfigure(i, weight=1)

        specs = [
            ("👥", "Total Students",    "0", PALETTE["accent"]),
            ("✅", "Present Today",     "0", PALETTE["success"]),
            ("📅", "This Month",        "0", PALETTE["warning"]),
            ("📊", "Attendance Rate",   "0%", "#9b59b6"),
        ]
        self._cards: list[StatCard] = []
        for col, (icon, title, val, color) in enumerate(specs):
            card = StatCard(cards_frame, icon, title, val, color)
            card.grid(row=0, column=col, padx=8, pady=4, sticky="nsew")
            self._cards.append(card)

    def _build_attendance_table(self):
        sec = ctk.CTkFrame(self, fg_color=PALETTE["card"],
                           corner_radius=14, border_width=1,
                           border_color=PALETTE["border"])
        sec.grid(row=2, column=0, sticky="nsew", padx=24, pady=8)
        sec.grid_columnconfigure(0, weight=1)
        sec.grid_rowconfigure(1, weight=1)

        # Section header
        hdr = ctk.CTkFrame(sec, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="Today's Attendance",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, sticky="w")

        refresh_btn = ctk.CTkButton(
            hdr, text="↻ Refresh", width=90, height=28, corner_radius=6,
            fg_color=PALETTE["accent_dim"], hover_color=PALETTE["accent"],
            font=ctk.CTkFont(size=12),
            command=self._refresh,
        )
        refresh_btn.grid(row=0, column=1)

        # Column headers
        cols   = ["#", "Student ID", "Name", "Department", "Time", "Status"]
        widths = [40,   120,          180,    150,           80,     80]

        col_frame = ctk.CTkFrame(sec, fg_color=PALETTE["card2"])
        col_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 0))

        for i, (col, w) in enumerate(zip(cols, widths)):
            ctk.CTkLabel(
                col_frame, text=col, width=w,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=PALETTE["text_secondary"],
                anchor="w",
            ).grid(row=0, column=i, padx=(8, 0), pady=6, sticky="w")

        # Scrollable rows
        self._table = ctk.CTkScrollableFrame(
            sec, fg_color="transparent", corner_radius=0
        )
        self._table.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        sec.grid_rowconfigure(2, weight=1)

        self._row_widths = widths

    def _build_quick_actions(self):
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 16))
        for i in range(4):
            actions.grid_columnconfigure(i, weight=1)

        btns = [
            ("📝  Register Student", PALETTE["accent"],   "register"),
            ("📷  Start Attendance", PALETTE["success"],  "attendance"),
            ("📋  View Reports",     PALETTE["warning"],  "view"),
            ("👥  Manage Students",  "#9b59b6",           "students"),
        ]
        for col, (txt, color, page) in enumerate(btns):
            ctk.CTkButton(
                actions, text=txt, height=44, corner_radius=10,
                fg_color=color, hover_color=color,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda p=page: self.root.show_page(p),
            ).grid(row=0, column=col, padx=6)

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _refresh(self):
        stats = self.db.get_stats()

        self._cards[0].update_value(str(stats["total_students"]))
        self._cards[1].update_value(str(stats["today_count"]))
        self._cards[2].update_value(str(stats["month_students"]))
        self._cards[3].update_value(f"{stats['attendance_rate']}%")

        # Rebuild table rows
        for w in self._table.winfo_children():
            w.destroy()

        records = self.db.get_today_attendance()

        if not records:
            ctk.CTkLabel(
                self._table, text="No attendance recorded today.",
                font=ctk.CTkFont(size=13),
                text_color=PALETTE["text_secondary"],
            ).pack(pady=20)
            return

        for row_num, rec in enumerate(records):
            bg = PALETTE["card"] if row_num % 2 == 0 else PALETTE["card2"]
            row_frame = ctk.CTkFrame(self._table, fg_color=bg, corner_radius=4)
            row_frame.pack(fill="x", pady=1)

            values = [
                str(row_num + 1),
                rec["StudentID"],
                rec["Name"],
                rec["Department"],
                rec["Time"],
                rec["Status"],
            ]
            colors = [PALETTE["text_secondary"]] * 5 + [PALETTE["success"]]

            for i, (val, col, w) in enumerate(
                zip(values, colors, self._row_widths)
            ):
                ctk.CTkLabel(
                    row_frame, text=val, width=w,
                    font=ctk.CTkFont(size=12),
                    text_color=col, anchor="w",
                ).grid(row=0, column=i, padx=(8, 0), pady=6, sticky="w")

        # Schedule next auto-refresh
        self.after(self.REFRESH_MS, self._refresh)

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_show(self):
        self._refresh()

    def on_hide(self):
        pass
