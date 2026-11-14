"""
register.py — Student Registration page for Smart Attendance System
Form + live webcam capture with animated progress bar.
"""

import threading
import queue
import cv2
import customtkinter as ctk
from PIL import Image

from utils.helpers import PALETTE, Toast, bgr_to_ctk_image, placeholder_ctk_image


DEPARTMENTS = [
    "Computer Science", "Information Technology", "Electronics",
    "Mechanical", "Civil", "Electrical", "Business Administration",
    "Mathematics", "Physics", "Chemistry",
]
YEARS    = ["1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year"]
SECTIONS = ["A", "B", "C", "D", "E", "F"]

CAM_W, CAM_H = 420, 315


class RegisterPage(ctk.CTkFrame):
    """
    Student registration page.
    Left panel: form fields.  Right panel: live webcam preview + progress.
    """

    def __init__(self, parent, db, engine, root):
        super().__init__(parent, fg_color=PALETTE["bg"], corner_radius=0)
        self.db     = db
        self.engine = engine
        self.root   = root

        self._cap        = None
        self._cam_thread = None
        self._stop_evt   = threading.Event()
        self._frame_q    = queue.Queue(maxsize=2)
        self._capturing  = False
        self._capture_count = 0

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_form()
        self._build_camera_panel()

    # ------------------------------------------------------------------
    # Left: form
    # ------------------------------------------------------------------

    def _build_form(self):
        form = ctk.CTkScrollableFrame(
            self,
            fg_color=PALETTE["card"],
            width=380,
            corner_radius=0,
        )
        form.grid(row=0, column=0, sticky="nsew")
        form.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(
            form, text="📝  Register New Student",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=PALETTE["accent"],
        ).grid(row=0, column=0, pady=(24, 4), padx=20, sticky="w")

        ctk.CTkLabel(
            form, text="Fill all fields, then capture face images.",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        ).grid(row=1, column=0, pady=(0, 16), padx=20, sticky="w")

        row = 2
        def lbl(text):
            nonlocal row
            ctk.CTkLabel(
                form, text=text,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=PALETTE["text_secondary"],
                anchor="w",
            ).grid(row=row, column=0, padx=20, pady=(10, 2), sticky="w")
            row += 1

        def entry(placeholder=""):
            nonlocal row
            e = ctk.CTkEntry(
                form, placeholder_text=placeholder,
                height=40, corner_radius=8,
                border_color=PALETTE["border"],
                fg_color=PALETTE["card2"],
                text_color=PALETTE["text"],
                font=ctk.CTkFont(size=13),
            )
            e.grid(row=row, column=0, padx=20, pady=(0, 2), sticky="ew")
            row += 1
            return e

        def combo(values, placeholder="Select…"):
            nonlocal row
            c = ctk.CTkComboBox(
                form, values=values,
                height=40, corner_radius=8,
                border_color=PALETTE["border"],
                fg_color=PALETTE["card2"],
                text_color=PALETTE["text"],
                dropdown_fg_color=PALETTE["card"],
                dropdown_text_color=PALETTE["text"],
                font=ctk.CTkFont(size=13),
                state="readonly",
            )
            c.set(placeholder)
            c.grid(row=row, column=0, padx=20, pady=(0, 2), sticky="ew")
            row += 1
            return c

        lbl("Student ID *")
        self._sid   = entry("e.g.  2024CS001")

        lbl("Full Name *")
        self._name  = entry("e.g.  John Doe")

        lbl("Department *")
        self._dept  = combo(DEPARTMENTS)

        lbl("Year *")
        self._year  = combo(YEARS)

        lbl("Section *")
        self._sec   = combo(SECTIONS)

        # Capture count
        lbl("Images to Capture")
        ctk.CTkLabel(
            form, text="40",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        ).grid(row=row, column=0, padx=20, sticky="w")
        row += 1
        self._slider = ctk.CTkSlider(
            form, from_=20, to=60, number_of_steps=40,
            button_color=PALETTE["accent"],
            button_hover_color=PALETTE["accent_hover"],
            progress_color=PALETTE["accent"],
        )
        self._slider.set(40)
        self._slider.grid(row=row, column=0, padx=20, pady=(0, 4), sticky="ew")
        self._slider.configure(command=lambda v: self._update_count_lbl(v))
        row += 1

        # Buttons
        self._capture_btn = ctk.CTkButton(
            form,
            text="📷  Start Face Capture",
            height=46, corner_radius=10,
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start_capture,
        )
        self._capture_btn.grid(row=row, column=0, padx=20, pady=(16, 6), sticky="ew")
        row += 1

        self._stop_btn = ctk.CTkButton(
            form, text="⏹  Stop Capture",
            height=38, corner_radius=8,
            fg_color=PALETTE["danger"],
            hover_color="#c0392b",
            font=ctk.CTkFont(size=13),
            state="disabled",
            command=self._stop_capture,
        )
        self._stop_btn.grid(row=row, column=0, padx=20, pady=(0, 6), sticky="ew")
        row += 1

        self._clear_btn = ctk.CTkButton(
            form, text="🗑  Clear Form",
            height=36, corner_radius=8,
            fg_color=PALETTE["card2"],
            hover_color=PALETTE["border"],
            text_color=PALETTE["text_secondary"],
            font=ctk.CTkFont(size=12),
            command=self._clear_form,
        )
        self._clear_btn.grid(row=row, column=0, padx=20, pady=(0, 20), sticky="ew")
        row += 1

        # Toast
        self._toast = Toast(form, row=row, col=0)
        row += 1

    # ------------------------------------------------------------------
    # Right: camera panel
    # ------------------------------------------------------------------

    def _build_camera_panel(self):
        panel = ctk.CTkFrame(self, fg_color=PALETTE["bg"], corner_radius=0)
        panel.grid(row=0, column=1, sticky="nsew", padx=24, pady=24)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="Live Camera Preview",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Camera display
        cam_frame = ctk.CTkFrame(
            panel,
            fg_color=PALETTE["card"],
            corner_radius=14,
            border_width=1,
            border_color=PALETTE["border"],
        )
        cam_frame.grid(row=1, column=0, sticky="nsew")
        cam_frame.grid_columnconfigure(0, weight=1)
        cam_frame.grid_rowconfigure(0, weight=1)

        self._cam_lbl = ctk.CTkLabel(cam_frame, text="")
        self._cam_lbl.grid(row=0, column=0, padx=8, pady=8)
        self._cam_lbl.configure(image=placeholder_ctk_image((CAM_W, CAM_H)))

        # Progress
        prog_frame = ctk.CTkFrame(panel, fg_color="transparent")
        prog_frame.grid(row=2, column=0, sticky="ew", pady=12)
        prog_frame.grid_columnconfigure(0, weight=1)

        self._prog_lbl = ctk.CTkLabel(
            prog_frame,
            text="Images captured: 0 / 40",
            font=ctk.CTkFont(size=13),
            text_color=PALETTE["text_secondary"],
        )
        self._prog_lbl.grid(row=0, column=0, sticky="w")

        self._progress = ctk.CTkProgressBar(
            prog_frame,
            progress_color=PALETTE["accent"],
            fg_color=PALETTE["card2"],
            corner_radius=6,
            height=14,
        )
        self._progress.grid(row=1, column=0, sticky="ew", pady=4)
        self._progress.set(0)

        # Guidance tips
        tips = ctk.CTkFrame(
            panel, fg_color=PALETTE["card2"],
            corner_radius=10, border_width=1,
            border_color=PALETTE["border"],
        )
        tips.grid(row=3, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkLabel(
            tips,
            text="💡 Tips for better recognition",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PALETTE["accent"],
            anchor="w",
        ).pack(anchor="w", padx=14, pady=(10, 4))

        for tip in [
            "• Ensure good, even lighting on your face.",
            "• Look directly at the camera.",
            "• Slightly move/tilt your head for variety.",
            "• Remove sunglasses or heavy accessories.",
        ]:
            ctk.CTkLabel(
                tips, text=tip,
                font=ctk.CTkFont(size=11),
                text_color=PALETTE["text_secondary"],
                anchor="w",
            ).pack(anchor="w", padx=14, pady=1)
        ctk.CTkLabel(tips, text="").pack(pady=4)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_count_lbl(self, v):
        pass  # slider updates the label implicitly

    def _validate_form(self) -> tuple[bool, str]:
        sid  = self._sid.get().strip()
        name = self._name.get().strip()
        dept = self._dept.get()
        year = self._year.get()
        sec  = self._sec.get()

        if not sid:   return False, "Student ID is required."
        if not name:  return False, "Full Name is required."
        if dept in ("Select…", ""): return False, "Please select a Department."
        if year in ("Select…", ""): return False, "Please select a Year."
        if sec  in ("Select…", ""): return False, "Please select a Section."

        return True, (sid, name, dept, year, sec)

    def _clear_form(self):
        self._sid.delete(0, "end")
        self._name.delete(0, "end")
        self._dept.set("Select…")
        self._year.set("Select…")
        self._sec.set("Select…")
        self._slider.set(40)
        self._progress.set(0)
        self._prog_lbl.configure(text="Images captured: 0 / 40")
        self._capture_count = 0

    # ------------------------------------------------------------------
    # Capture flow
    # ------------------------------------------------------------------

    def _start_capture(self):
        ok, result = self._validate_form()
        if not ok:
            self._toast.show(result, PALETTE["danger"])
            return

        sid, name, dept, year, sec = result

        # Check duplicate ID
        if self.db.get_student_by_id(sid):
            self._toast.show(
                f"Student ID '{sid}' already registered!", PALETTE["danger"]
            )
            return

        # First save to DB so we have a LabelID
        ok, msg = self.db.add_student(sid, name, dept, year, sec)
        if not ok:
            self._toast.show(msg, PALETTE["danger"])
            return

        student = self.db.get_student_by_id(sid)
        label_id = student["LabelID"]
        total = int(self._slider.get())

        self._capturing = True
        self._capture_count = 0
        self._stop_evt.clear()

        self._capture_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")

        cam_idx = int(self.db.get_setting("camera_index", "0"))

        self._cam_thread = threading.Thread(
            target=self._capture_worker,
            args=(sid, label_id, total, cam_idx),
            daemon=True,
        )
        self._cam_thread.start()
        self._poll_frame()

    def _capture_worker(self, sid: str, label_id: int, total: int, cam_idx: int):
        """Background thread: captures images and posts frames to queue."""

        def _progress_cb(count, _total, frame, bbox):
            self._capture_count = count
            x, y, w, h = bbox
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 210, 100), 2)
            cv2.putText(
                frame, f"Captured: {count}/{_total}",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 210, 100), 2
            )
            if not self._frame_q.full():
                self._frame_q.put(frame)

        ok, msg = self.engine.capture_images(
            student_id=sid,
            label_id=label_id,
            capture_count=total,
            camera_index=cam_idx,
            progress_cb=_progress_cb,
            stop_event=self._stop_evt,
        )
        self.after(0, lambda: self._capture_done(ok, msg, total))

    def _poll_frame(self):
        """Pull the latest frame from the queue and update the camera label."""
        if not self._capturing:
            return
        try:
            frame = self._frame_q.get_nowait()
            img   = bgr_to_ctk_image(frame, (CAM_W, CAM_H))
            self._cam_lbl.configure(image=img)

            pct = self._capture_count / max(int(self._slider.get()), 1)
            self._progress.set(min(pct, 1.0))
            self._prog_lbl.configure(
                text=f"Images captured: {self._capture_count} / {int(self._slider.get())}"
            )
        except Exception:
            pass

        if self._capturing:
            self.after(30, self._poll_frame)

    def _capture_done(self, ok: bool, msg: str, total: int):
        self._capturing = False
        self._capture_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")

        if ok:
            self._progress.set(1.0)
            self._prog_lbl.configure(
                text=f"Images captured: {self._capture_count} / {total}"
            )
            self._toast.show(
                f"✓ {msg}  |  Please click 'Train Model' from the sidebar.",
                PALETTE["success"],
                duration=6000,
            )
        else:
            self._toast.show(msg, PALETTE["danger"])

    def _stop_capture(self):
        self._stop_evt.set()
        self._capturing = False
        self._capture_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._toast.show("Capture stopped.", PALETTE["warning"])

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_show(self):
        pass

    def on_hide(self):
        self._stop_evt.set()
        self._capturing = False
