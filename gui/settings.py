"""
settings.py — Settings page for Smart Attendance System
Admin password, confidence threshold, camera selector, theme, backup/restore.
"""

import customtkinter as ctk
from tkinter import filedialog
import threading

from utils.helpers import PALETTE, Toast


class SettingsPage(ctk.CTkFrame):
    """
    System settings with grouped sections:
    • Security (admin password)
    • Recognition (threshold, camera)
    • Appearance (theme)
    • Database (backup, restore)
    • About
    """

    def __init__(self, parent, db, engine, root):
        super().__init__(parent, fg_color=PALETTE["bg"], corner_radius=0)
        self.db     = db
        self.engine = engine
        self.root   = root

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=PALETTE["bg"], corner_radius=0
        )
        self._scroll.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_all()

    # ------------------------------------------------------------------
    # Section builder helpers
    # ------------------------------------------------------------------

    def _section(self, title: str, icon: str, row: int) -> ctk.CTkFrame:
        """Return a styled card frame for a settings section."""
        card = ctk.CTkFrame(
            self._scroll,
            fg_color=PALETTE["card"],
            corner_radius=14,
            border_width=1,
            border_color=PALETTE["border"],
        )
        card.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=f"{icon}  {title}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETTE["accent"],
            anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        ctk.CTkFrame(card, fg_color=PALETTE["border"], height=1).grid(
            row=1, column=0, sticky="ew", padx=20, pady=(0, 12)
        )
        return card

    def _label(self, parent, text: str, row: int, small: bool = False):
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=11 if small else 12, weight="bold"),
            text_color=PALETTE["text_secondary" if small else "text"],
            anchor="w",
        ).grid(row=row, column=0, padx=20, pady=(8, 2), sticky="w")

    def _entry(
        self, parent, row: int, placeholder: str = "",
        show: str = "", width: int = 260,
    ) -> ctk.CTkEntry:
        e = ctk.CTkEntry(
            parent, placeholder_text=placeholder, show=show,
            width=width, height=38, corner_radius=8,
            fg_color=PALETTE["card2"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=13),
        )
        e.grid(row=row, column=0, padx=20, pady=(0, 4), sticky="w")
        return e

    def _button(
        self, parent, text: str, row: int,
        color: str = None, cmd=None, width: int = 160,
    ) -> ctk.CTkButton:
        b = ctk.CTkButton(
            parent, text=text, width=width, height=38, corner_radius=8,
            fg_color=color or PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            font=ctk.CTkFont(size=13, weight="bold"),
            command=cmd,
        )
        b.grid(row=row, column=0, padx=20, pady=(4, 8), sticky="w")
        return b

    # ------------------------------------------------------------------
    # Build all sections
    # ------------------------------------------------------------------

    def _build_all(self):
        # Page title
        ctk.CTkLabel(
            self._scroll, text="⚙️  Settings",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, padx=24, pady=(20, 12), sticky="w")

        self._build_security(row=1)
        self._build_recognition(row=2)
        self._build_appearance(row=3)
        self._build_database(row=4)
        self._build_about(row=5)

    # ── Security ──────────────────────────────────────────────────────

    def _build_security(self, row: int):
        card = self._section("Security", "🔒", row)
        card.grid_columnconfigure(1, weight=1)

        self._label(card, "Current Password", 2)
        self._old_pwd = self._entry(card, 3, "Current password", show="*")

        self._label(card, "New Password", 4)
        self._new_pwd = self._entry(card, 5, "New password", show="*")

        self._label(card, "Confirm New Password", 6)
        self._cnf_pwd = self._entry(card, 7, "Confirm password", show="*")

        self._pwd_toast = Toast(card, row=8, col=0)

        self._button(card, "💾  Update Password", 9,
                     color=PALETTE["accent"], cmd=self._change_password)

    def _change_password(self):
        old = self._old_pwd.get()
        new = self._new_pwd.get()
        cnf = self._cnf_pwd.get()

        admin_pwd = self.db.get_setting("admin_password", "admin123")

        if old != admin_pwd:
            self._pwd_toast.show("Current password is incorrect.", PALETTE["danger"])
            return
        if not new:
            self._pwd_toast.show("New password cannot be empty.", PALETTE["danger"])
            return
        if new != cnf:
            self._pwd_toast.show("New passwords do not match.", PALETTE["danger"])
            return

        self.db.set_setting("admin_password", new)
        self._old_pwd.delete(0, "end")
        self._new_pwd.delete(0, "end")
        self._cnf_pwd.delete(0, "end")
        self._pwd_toast.show("Password updated successfully!", PALETTE["success"])

    # ── Recognition ───────────────────────────────────────────────────

    def _build_recognition(self, row: int):
        card = self._section("Face Recognition", "🎯", row)
        card.grid_columnconfigure(0, weight=1)

        # Threshold slider
        self._label(card, "Recognition Distance Threshold", 2)
        self._label(
            card,
            "Lower = stricter matching (fewer false positives).\n"
            "Higher = more tolerant (better detection in varied lighting).\n"
            "Recommended: 50–80.",
            3, small=True
        )

        threshold_val = float(self.db.get_setting("confidence_threshold", "70"))

        self._thresh_lbl = ctk.CTkLabel(
            card, text=f"Threshold: {threshold_val:.0f}",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["accent"],
        )
        self._thresh_lbl.grid(row=4, column=0, padx=20, pady=(6, 2), sticky="w")

        self._thresh_slider = ctk.CTkSlider(
            card, from_=10, to=150, number_of_steps=140,
            button_color=PALETTE["accent"],
            button_hover_color=PALETTE["accent_hover"],
            progress_color=PALETTE["accent"],
            width=300,
        )
        self._thresh_slider.set(threshold_val)
        self._thresh_slider.grid(row=5, column=0, padx=20, pady=(0, 4), sticky="w")
        self._thresh_slider.configure(
            command=lambda v: (
                self._thresh_lbl.configure(text=f"Threshold: {v:.0f}"),
                self.db.set_setting("confidence_threshold", str(int(v))),
            )
        )

        # Camera index
        self._label(card, "Camera Index", 6)
        self._label(card, "0 = default webcam, 1 = secondary camera, etc.", 7, small=True)

        cam_row = ctk.CTkFrame(card, fg_color="transparent")
        cam_row.grid(row=8, column=0, padx=20, pady=(4, 4), sticky="w")

        self._cam_entry = ctk.CTkEntry(
            cam_row, width=80, height=38, corner_radius=8,
            fg_color=PALETTE["card2"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=13),
        )
        self._cam_entry.insert(0, self.db.get_setting("camera_index", "0"))
        self._cam_entry.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            cam_row, text="Apply", width=80, height=38, corner_radius=8,
            fg_color=PALETTE["accent_dim"], hover_color=PALETTE["accent"],
            font=ctk.CTkFont(size=12),
            command=self._set_camera,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            cam_row, text="🔍 Detect Cameras", width=160, height=38, corner_radius=8,
            fg_color=PALETTE["card2"], hover_color=PALETTE["border"],
            text_color=PALETTE["text_secondary"],
            font=ctk.CTkFont(size=12),
            command=self._detect_cameras,
        ).pack(side="left")

        self._cam_toast = Toast(card, row=9, col=0)

        # Capture count
        self._label(card, "Default Capture Count", 10)
        cap_cnt = int(self.db.get_setting("capture_count", "40"))

        self._cap_lbl = ctk.CTkLabel(
            card, text=f"Count: {cap_cnt}",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["accent"],
        )
        self._cap_lbl.grid(row=11, column=0, padx=20, pady=(6, 2), sticky="w")

        self._cap_slider = ctk.CTkSlider(
            card, from_=20, to=80, number_of_steps=60,
            button_color=PALETTE["accent"],
            button_hover_color=PALETTE["accent_hover"],
            progress_color=PALETTE["accent"],
            width=300,
        )
        self._cap_slider.set(cap_cnt)
        self._cap_slider.grid(row=12, column=0, padx=20, pady=(0, 16), sticky="w")
        self._cap_slider.configure(
            command=lambda v: (
                self._cap_lbl.configure(text=f"Count: {v:.0f}"),
                self.db.set_setting("capture_count", str(int(v))),
            )
        )

    def _set_camera(self):
        try:
            idx = int(self._cam_entry.get())
            self.db.set_setting("camera_index", str(idx))
            self._cam_toast.show(f"Camera index set to {idx}.", PALETTE["success"])
        except ValueError:
            self._cam_toast.show("Invalid camera index.", PALETTE["danger"])

    def _detect_cameras(self):
        self._cam_toast.show("Detecting cameras…", PALETTE["warning"])

        def _detect():
            cams = self.engine.available_cameras()
            msg  = f"Available cameras: {cams}" if cams else "No cameras detected."
            self.after(0, lambda: self._cam_toast.show(msg, PALETTE["success"]))

        threading.Thread(target=_detect, daemon=True).start()

    # ── Appearance ────────────────────────────────────────────────────

    def _build_appearance(self, row: int):
        card = self._section("Appearance", "🎨", row)

        self._label(card, "Color Theme", 2)

        theme_row = ctk.CTkFrame(card, fg_color="transparent")
        theme_row.grid(row=3, column=0, padx=20, pady=(4, 16), sticky="w")

        current = self.db.get_setting("theme", "dark")

        def _set_theme(t: str):
            import customtkinter as ctk_inner
            ctk_inner.set_appearance_mode(t)
            self.db.set_setting("theme", t)

        for label, val in [("🌙 Dark Mode", "dark"), ("☀️ Light Mode", "light"),
                            ("🖥️ System", "system")]:
            ctk.CTkRadioButton(
                theme_row, text=label, value=val,
                font=ctk.CTkFont(size=13),
                text_color=PALETTE["text"],
                fg_color=PALETTE["accent"],
                border_color=PALETTE["border"],
                variable=ctk.StringVar(value=current),
                command=lambda t=val: _set_theme(t),
            ).pack(side="left", padx=16)

    # ── Database ──────────────────────────────────────────────────────

    def _build_database(self, row: int):
        card = self._section("Database", "🗄️", row)

        self._label(card, "Backup Database", 2)
        self._label(
            card,
            "Save a copy of the database to protect your attendance records.",
            3, small=True,
        )

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=4, column=0, padx=20, pady=(4, 12), sticky="w")

        ctk.CTkButton(
            btn_row, text="📦 Backup Now", width=140, height=38, corner_radius=8,
            fg_color=PALETTE["accent"], hover_color=PALETTE["accent_hover"],
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._backup_db,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row, text="♻️ Restore Backup", width=150, height=38, corner_radius=8,
            fg_color=PALETTE["warning"], hover_color="#b7791f",
            text_color="#111",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._restore_db,
        ).pack(side="left")

        self._db_toast = Toast(card, row=5, col=0)

    def _backup_db(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
            initialfile="attendance_backup.db",
        )
        if path:
            ok, msg = self.db.backup(path)
            self._db_toast.show(msg, PALETTE["success"] if ok else PALETTE["danger"])

    def _restore_db(self):
        path = filedialog.askopenfilename(
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")]
        )
        if path:
            ok, msg = self.db.restore(path)
            self._db_toast.show(msg, PALETTE["success"] if ok else PALETTE["danger"])

    # ── About ─────────────────────────────────────────────────────────

    def _build_about(self, row: int):
        card = self._section("About", "ℹ️", row)

        info = [
            ("Application",   "Smart Attendance System"),
            ("Version",       "1.0.0"),
            ("Engine",        "OpenCV LBPH Face Recognizer"),
            ("GUI",           "CustomTkinter 5.x"),
            ("Database",      "SQLite 3"),
            ("Python",        "3.12+"),
        ]

        for r, (k, v) in enumerate(info, start=2):
            ctk.CTkLabel(
                card, text=f"{k}:",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=PALETTE["text_secondary"],
                anchor="w",
                width=140,
            ).grid(row=r, column=0, padx=20, pady=3, sticky="w")
            ctk.CTkLabel(
                card, text=v,
                font=ctk.CTkFont(size=12),
                text_color=PALETTE["text"],
                anchor="w",
            ).grid(row=r, column=1, padx=0, pady=3, sticky="w")
            card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text="\nBuilt with ❤️  using Python, OpenCV and CustomTkinter.\n",
            font=ctk.CTkFont(size=11),
            text_color=PALETTE["text_secondary"],
        ).grid(row=len(info) + 3, column=0, columnspan=2, pady=(4, 12))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_show(self):
        pass

    def on_hide(self):
        pass
