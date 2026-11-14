"""
app.py — Entry point for Smart Attendance System
Bootstraps directories, shows admin login, then launches the main window.
"""

import sys
import os

# ── Ensure the project root is always on the path ────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

from utils.database   import DatabaseManager
from utils.face_engine import FaceEngine
from utils.helpers    import ensure_dirs, PALETTE


# ─────────────────────────────────────────────────────────────────────────────
# Admin Login Window
# ─────────────────────────────────────────────────────────────────────────────

class LoginWindow(ctk.CTk):
    """
    Splash / login screen shown before the main application.
    Validates admin password stored in the Settings table.
    """

    def __init__(self, db: DatabaseManager, engine: FaceEngine):
        super().__init__()
        self.db     = db
        self.engine = engine

        self.title("Smart Attendance System — Login")
        self.geometry("440x540")
        self.resizable(False, False)
        self.configure(fg_color=PALETTE["bg"])

        ctk.set_appearance_mode(db.get_setting("theme", "dark"))
        ctk.set_default_color_theme("blue")

        self._build_ui()
        self._result = False

    # ------------------------------------------------------------------

    def _build_ui(self):
        # Outer card
        card = ctk.CTkFrame(
            self,
            fg_color=PALETTE["card"],
            corner_radius=20,
            border_width=1,
            border_color=PALETTE["border"],
        )
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.88, relheight=0.88)
        card.grid_columnconfigure(0, weight=1)

        # Logo
        ctk.CTkLabel(
            card, text="🎓",
            font=ctk.CTkFont(size=64),
        ).grid(row=0, column=0, pady=(30, 4))

        ctk.CTkLabel(
            card, text="Smart Attendance System",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=PALETTE["accent"],
        ).grid(row=1, column=0, pady=(0, 2))

        ctk.CTkLabel(
            card, text="AI-Powered Face Recognition Attendance",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        ).grid(row=2, column=0, pady=(0, 24))

        # Separator
        ctk.CTkFrame(card, fg_color=PALETTE["border"], height=1).grid(
            row=3, column=0, sticky="ew", padx=24, pady=(0, 20)
        )

        # Password field
        ctk.CTkLabel(
            card, text="Administrator Password",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["text_secondary"],
            anchor="w",
        ).grid(row=4, column=0, padx=28, sticky="w")

        self._pwd = ctk.CTkEntry(
            card,
            show="*",
            placeholder_text="Enter password…",
            height=44, corner_radius=10,
            fg_color=PALETTE["card2"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
            font=ctk.CTkFont(size=14),
        )
        self._pwd.grid(row=5, column=0, padx=28, pady=(6, 4), sticky="ew")
        self._pwd.bind("<Return>", lambda _: self._login())

        # Error label
        self._err = ctk.CTkLabel(
            card, text="",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["danger"],
        )
        self._err.grid(row=6, column=0, pady=2)

        # Login button
        ctk.CTkButton(
            card,
            text="🔓  Login",
            height=46, corner_radius=10,
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._login,
        ).grid(row=7, column=0, padx=28, pady=(10, 6), sticky="ew")

        # Skip (for dev/demo — remove in production)
        ctk.CTkButton(
            card,
            text="Skip Login (Demo Mode)",
            height=32, corner_radius=8,
            fg_color="transparent",
            hover_color=PALETTE["card2"],
            text_color=PALETTE["text_secondary"],
            font=ctk.CTkFont(size=11),
            border_width=0,
            command=self._skip,
        ).grid(row=8, column=0, padx=28, pady=(0, 10))

        # Footer
        ctk.CTkLabel(
            card,
            text="Default password: admin123",
            font=ctk.CTkFont(size=10),
            text_color=PALETTE["text_secondary"],
        ).grid(row=9, column=0, pady=(4, 20))

        self._pwd.focus()

    # ------------------------------------------------------------------

    def _login(self):
        entered = self._pwd.get()
        admin   = self.db.get_setting("admin_password", "admin123")

        if entered == admin:
            self._result = True
            self.destroy()
        else:
            self._err.configure(text="❌ Incorrect password. Please try again.")
            self._pwd.delete(0, "end")

    def _skip(self):
        self._result = True
        self.destroy()

    def run(self) -> bool:
        self.mainloop()
        return self._result


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # 1. Create required directories
    ensure_dirs()

    # 2. Initialise the database and face engine
    db     = DatabaseManager("database/attendance.db")
    engine = FaceEngine()

    # 3. Show login screen
    login = LoginWindow(db, engine)
    if not login.run():
        return  # user closed without logging in

    # 4. Launch the main application
    from gui.main_window import MainWindow
    app = MainWindow(db, engine)
    app.mainloop()


if __name__ == "__main__":
    main()
