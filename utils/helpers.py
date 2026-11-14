"""
helpers.py — Utility helpers for Smart Attendance System
Time formatting, folder setup, PIL ↔ CTk conversion, toast messages.
"""

import os
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
import customtkinter as ctk
from PIL import Image


# ── Directory bootstrap ────────────────────────────────────────────────────────

PROJECT_DIRS = [
    "database",
    "dataset",
    "trainer",
    "exports",
    "models",
    "attendance",
    "icons",
    "gui",
    "utils",
]


def ensure_dirs():
    """Create all required project directories if they do not exist."""
    for d in PROJECT_DIRS:
        Path(d).mkdir(parents=True, exist_ok=True)


# ── DateTime helpers ───────────────────────────────────────────────────────────

def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.now().strftime(fmt)


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def time_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def friendly_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to a readable form like 'Wed, Jul 30 2026'."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%a, %b %d %Y")
    except ValueError:
        return date_str


def export_filename(prefix: str, ext: str) -> str:
    """Generate a timestamped export filename."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join("exports", f"{prefix}_{ts}.{ext}")


# ── Image conversion ───────────────────────────────────────────────────────────

def bgr_to_ctk_image(
    bgr_frame: np.ndarray,
    size: tuple[int, int] = (640, 480),
) -> ctk.CTkImage:
    """
    Convert an OpenCV BGR frame to a CTkImage suitable for display in a CTkLabel.
    This is the bridge between the OpenCV camera thread and the CTk GUI thread.
    """
    rgb  = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    pil  = Image.fromarray(rgb).resize(size, Image.Resampling.LANCZOS)
    return ctk.CTkImage(light_image=pil, dark_image=pil, size=size)


def placeholder_ctk_image(
    size: tuple[int, int] = (640, 480),
    text: str = "Camera feed will appear here",
    bg_color: tuple[int, int, int] = (18, 18, 30),
) -> ctk.CTkImage:
    """Create a dark placeholder image with centred text for the camera widget."""
    img = Image.new("RGB", size, color=bg_color)

    # Draw centred text using PIL
    try:
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            ((size[0] - tw) // 2, (size[1] - th) // 2),
            text,
            fill=(80, 80, 100),
            font=font,
        )
    except Exception:
        pass

    return ctk.CTkImage(light_image=img, dark_image=img, size=size)


# ── Toast / Status helper ──────────────────────────────────────────────────────

class Toast:
    """
    Lightweight temporary status label.
    Call show(message, color) to display for `duration` ms then fade.
    """

    def __init__(self, parent, row: int = 0, col: int = 0, columnspan: int = 1):
        self._label = ctk.CTkLabel(
            parent,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent",
            text_color="#3fb950",
            anchor="center",
        )
        self._label.grid(row=row, column=col, columnspan=columnspan,
                         pady=(4, 0), sticky="ew")
        self._after_id = None

    def show(
        self,
        message: str,
        color:   str = "#3fb950",
        duration: int = 3500,
    ):
        if self._after_id:
            self._label.after_cancel(self._after_id)
        self._label.configure(text=message, text_color=color)
        self._after_id = self._label.after(duration, self.clear)

    def clear(self):
        self._label.configure(text="")


# ── Colour palette ─────────────────────────────────────────────────────────────

PALETTE = {
    "accent":          "#00b4d8",
    "accent_hover":    "#0096c7",
    "accent_dim":      "#023e8a",
    "sidebar":         "#0d1117",
    "sidebar_hover":   "#161b22",
    "card":            "#161b22",
    "card2":           "#1c2128",
    "bg":              "#0d1117",
    "text":            "#e6edf3",
    "text_secondary":  "#8b949e",
    "success":         "#3fb950",
    "warning":         "#d29922",
    "danger":          "#f85149",
    "border":          "#30363d",
}
