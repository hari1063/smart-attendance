"""
main_window.py — Root application window for Smart Attendance System
Dark-teal themed CustomTkinter shell with animated sidebar navigation.
"""

import threading
import customtkinter as ctk
from datetime import datetime

from utils.database  import DatabaseManager
from utils.face_engine import FaceEngine
from utils.helpers   import PALETTE, ensure_dirs

# Import all pages (imported lazily to avoid circular issues at startup)
from gui.dashboard       import DashboardPage
from gui.register        import RegisterPage
from gui.attendance      import AttendancePage
from gui.view_attendance import ViewAttendancePage
from gui.student_mgmt    import StudentManagementPage
from gui.settings        import SettingsPage


# ── Sidebar nav item ───────────────────────────────────────────────────────────

class NavItem(ctk.CTkFrame):
    """Single sidebar navigation button with icon label + text label."""

    def __init__(self, parent, icon: str, label: str, command, **kwargs):
        super().__init__(
            parent,
            fg_color="transparent",
            corner_radius=8,
            cursor="hand2",
            **kwargs,
        )
        self.command = command
        self._active = False

        self._icon_lbl = ctk.CTkLabel(
            self, text=icon, font=ctk.CTkFont(size=20), width=36,
            text_color=PALETTE["text_secondary"],
        )
        self._icon_lbl.pack(side="left", padx=(10, 4), pady=8)

        self._text_lbl = ctk.CTkLabel(
            self, text=label, font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["text_secondary"], anchor="w",
        )
        self._text_lbl.pack(side="left", fill="x", expand=True, padx=(0, 10))

        for w in (self, self._icon_lbl, self._text_lbl):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>",    self._on_enter)
            w.bind("<Leave>",    self._on_leave)

    def _on_click(self, _=None):
        self.command()

    def _on_enter(self, _=None):
        if not self._active:
            self.configure(fg_color=PALETTE["sidebar_hover"])

    def _on_leave(self, _=None):
        if not self._active:
            self.configure(fg_color="transparent")

    def set_active(self, active: bool):
        self._active = active
        if active:
            self.configure(fg_color=PALETTE["accent_dim"])
            self._icon_lbl.configure(text_color=PALETTE["accent"])
            self._text_lbl.configure(text_color=PALETTE["accent"])
        else:
            self.configure(fg_color="transparent")
            self._icon_lbl.configure(text_color=PALETTE["text_secondary"])
            self._text_lbl.configure(text_color=PALETTE["text_secondary"])


# ── Main window ────────────────────────────────────────────────────────────────

class MainWindow(ctk.CTk):
    """
    Root window.  Hosts the sidebar and a single content frame whose child
    is swapped to show the selected page.
    """

    TITLE  = "Smart Attendance System"
    W, H   = 1280, 760
    SIDEBAR_W = 220

    NAV = [
        ("🏠", "Dashboard",         "dashboard"),
        ("📝", "Register Student",  "register"),
        ("🧠", "Train Model",       "train"),
        ("📷", "Start Attendance",  "attendance"),
        ("📋", "View Attendance",   "view"),
        ("👥", "Student Records",   "students"),
        ("⚙️", "Settings",          "settings"),
    ]

    def __init__(self, db: DatabaseManager, engine: FaceEngine):
        super().__init__()

        self.db     = db
        self.engine = engine

        # ── Window setup ──────────────────────────────────────────────
        self.title(self.TITLE)
        self.geometry(f"{self.W}x{self.H}")
        self.minsize(1024, 680)
        self.configure(fg_color=PALETTE["bg"])

        # Apply theme colours
        ctk.set_default_color_theme("blue")
        self._apply_theme()

        # ── Layout ────────────────────────────────────────────────────
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_sidebar()
        self._build_content()

        # ── Pages ─────────────────────────────────────────────────────
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._current_page = ""
        self._nav_items:    dict[str, NavItem] = {}

        self._build_nav()
        self.show_page("dashboard")

        # ── Clock update ──────────────────────────────────────────────
        self._update_clock()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Theme helper
    # ------------------------------------------------------------------

    def _apply_theme(self):
        """Patch CTk colour variables for the dark-teal look."""
        self._theme_mode = self.db.get_setting("theme", "dark")
        ctk.set_appearance_mode(self._theme_mode)

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------

    def _build_topbar(self):
        bar = ctk.CTkFrame(
            self, fg_color=PALETTE["sidebar"], height=52, corner_radius=0
        )
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        # Logo + title
        logo = ctk.CTkLabel(
            bar,
            text="  🎓  Smart Attendance System",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=PALETTE["accent"],
        )
        logo.grid(row=0, column=0, padx=20, pady=12, sticky="w")

        # Real-time clock
        self._clock_lbl = ctk.CTkLabel(
            bar,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["text_secondary"],
        )
        self._clock_lbl.grid(row=0, column=1, padx=20, pady=12, sticky="e")

        # Theme toggle button
        self._theme_btn = ctk.CTkButton(
            bar, text="☀️ Light" if self._theme_mode == "dark" else "🌙 Dark",
            width=90, height=30, corner_radius=6,
            fg_color=PALETTE["card"], hover_color=PALETTE["card2"],
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=12),
            command=self._toggle_theme,
        )
        self._theme_btn.grid(row=0, column=2, padx=(0, 16), pady=12)

    def _build_sidebar(self):
        self._sidebar = ctk.CTkFrame(
            self,
            width=self.SIDEBAR_W,
            fg_color=PALETTE["sidebar"],
            corner_radius=0,
        )
        self._sidebar.grid(row=1, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)
        self._sidebar.grid_rowconfigure(99, weight=1)   # spacer row

    def _build_content(self):
        self._content = ctk.CTkFrame(
            self, fg_color=PALETTE["bg"], corner_radius=0
        )
        self._content.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

    def _build_nav(self):
        for idx, (icon, label, key) in enumerate(self.NAV):
            if key == "train":
                # Train model is a button action, not a page
                item = NavItem(
                    self._sidebar, icon, label,
                    command=lambda: self._train_model_dialog(),
                )
            else:
                item = NavItem(
                    self._sidebar, icon, label,
                    command=lambda k=key: self.show_page(k),
                )
            item.grid(row=idx, column=0, padx=8, pady=2, sticky="ew")
            self._nav_items[key] = item

        # Exit button at bottom
        exit_btn = ctk.CTkButton(
            self._sidebar,
            text="🚪  Exit",
            font=ctk.CTkFont(size=13),
            fg_color=PALETTE["danger"],
            hover_color="#c0392b",
            corner_radius=8,
            height=38,
            command=self._on_close,
        )
        exit_btn.grid(row=100, column=0, padx=12, pady=16, sticky="ew")

    # ------------------------------------------------------------------
    # Page routing
    # ------------------------------------------------------------------

    def _get_page(self, key: str) -> ctk.CTkFrame:
        if key not in self._pages:
            constructors = {
                "dashboard":  lambda: DashboardPage(self._content,   self.db, self.engine, self),
                "register":   lambda: RegisterPage(self._content,    self.db, self.engine, self),
                "attendance": lambda: AttendancePage(self._content,  self.db, self.engine, self),
                "view":       lambda: ViewAttendancePage(self._content, self.db, self),
                "students":   lambda: StudentManagementPage(self._content, self.db, self.engine, self),
                "settings":   lambda: SettingsPage(self._content,    self.db, self.engine, self),
            }
            self._pages[key] = constructors[key]()
        return self._pages[key]

    def show_page(self, key: str):
        """Hide current page, show requested page, highlight nav item."""
        # Stop camera on old page if applicable
        if self._current_page:
            old = self._pages.get(self._current_page)
            if old and hasattr(old, "on_hide"):
                old.on_hide()
            if self._current_page in self._nav_items:
                self._nav_items[self._current_page].set_active(False)

        page = self._get_page(key)
        page.grid(row=0, column=0, sticky="nsew")
        page.tkraise()

        if hasattr(page, "on_show"):
            page.on_show()

        if key in self._nav_items:
            self._nav_items[key].set_active(True)

        self._current_page = key

    def refresh_page(self, key: str):
        """Force-rebuild a cached page (e.g. after training or registration)."""
        if key in self._pages:
            self._pages[key].destroy()
            del self._pages[key]
        if self._current_page == key:
            self._current_page = ""
            self.show_page(key)

    # ------------------------------------------------------------------
    # Train model dialog
    # ------------------------------------------------------------------

    def _train_model_dialog(self):
        """Show a toplevel progress dialog and train in a background thread."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Train Model")
        dlg.geometry("420x240")
        dlg.resizable(False, False)
        dlg.configure(fg_color=PALETTE["card"])
        dlg.grab_set()

        ctk.CTkLabel(
            dlg, text="🧠  Training Face Recognition Model",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETTE["accent"],
        ).pack(pady=(24, 8))

        status_lbl = ctk.CTkLabel(
            dlg, text="Preparing dataset...",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        )
        status_lbl.pack(pady=4)

        progress = ctk.CTkProgressBar(dlg, width=360)
        progress.pack(pady=12)
        progress.set(0)
        progress.configure(mode="indeterminate")
        progress.start()

        result_lbl = ctk.CTkLabel(
            dlg, text="", font=ctk.CTkFont(size=13, weight="bold")
        )
        result_lbl.pack(pady=4)

        def _do_train():
            def _cb(name, total):
                dlg.after(0, lambda: status_lbl.configure(
                    text=f"Processing {name}… ({total} images)"
                ))

            ok, msg = self.engine.train_model(self.db, progress_cb=_cb)

            def _done():
                progress.stop()
                progress.configure(mode="determinate")
                progress.set(1 if ok else 0)
                result_lbl.configure(
                    text=msg,
                    text_color=PALETTE["success"] if ok else PALETTE["danger"],
                )
                # Refresh dashboard stats
                if ok:
                    self.refresh_page("dashboard")
                dlg.after(3000, dlg.destroy)

            dlg.after(0, _done)

        threading.Thread(target=_do_train, daemon=True).start()

    # ------------------------------------------------------------------
    # Theme toggle
    # ------------------------------------------------------------------

    def _toggle_theme(self):
        new = "light" if self._theme_mode == "dark" else "dark"
        self._theme_mode = new
        ctk.set_appearance_mode(new)
        self.db.set_setting("theme", new)
        self._theme_btn.configure(
            text="☀️ Light" if new == "dark" else "🌙 Dark"
        )

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _update_clock(self):
        now = datetime.now().strftime("%A, %B %d %Y   |   %I:%M:%S %p")
        self._clock_lbl.configure(text=now)
        self.after(1000, self._update_clock)

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def _on_close(self):
        # Signal any running camera threads to stop
        for page in self._pages.values():
            if hasattr(page, "on_hide"):
                try:
                    page.on_hide()
                except Exception:
                    pass
        self.destroy()
