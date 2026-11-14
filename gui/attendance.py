"""
attendance.py — Live Face Recognition & Attendance page
Real-time webcam feed with face detection overlay, auto-marking, and FPS counter.
"""

import threading
import queue
import time
import cv2
import customtkinter as ctk

from utils.helpers import PALETTE, bgr_to_ctk_image, placeholder_ctk_image, Toast


CAM_W, CAM_H = 680, 510


class AttendancePage(ctk.CTkFrame):
    """
    Live attendance recognition page.
    Left panel: camera feed with overlays.
    Right panel: recognition info + marked-attendance log.
    """

    # How long (ms) a recognised card stays highlighted
    CARD_FLASH_MS = 3000
    # Minimum seconds between auto-marking the SAME student (de-bounce)
    MARK_COOLDOWN = 10

    def __init__(self, parent, db, engine, root):
        super().__init__(parent, fg_color=PALETTE["bg"], corner_radius=0)
        self.db     = db
        self.engine = engine
        self.root   = root

        self._running     = False
        self._stop_evt    = threading.Event()
        self._frame_q     = queue.Queue(maxsize=2)
        self._result_q    = queue.Queue(maxsize=4)
        self._last_marked: dict[str, float] = {}   # {student_id: epoch}
        self._student_cache: dict[str, dict] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self._build_camera_panel()
        self._build_info_panel()

    # ------------------------------------------------------------------
    # Camera panel (left)
    # ------------------------------------------------------------------

    def _build_camera_panel(self):
        left = ctk.CTkFrame(self, fg_color=PALETTE["bg"], corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        # Header row
        hdr = ctk.CTkFrame(left, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="📷  Live Face Recognition",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=PALETTE["text"],
        ).grid(row=0, column=0, sticky="w")

        # FPS + status badges
        self._fps_lbl = ctk.CTkLabel(
            hdr, text="FPS: —",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        )
        self._fps_lbl.grid(row=0, column=1, padx=8)

        self._status_badge = ctk.CTkLabel(
            hdr, text="● STOPPED",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PALETTE["danger"],
        )
        self._status_badge.grid(row=0, column=2, padx=4)

        # Camera feed
        cam_wrapper = ctk.CTkFrame(
            left,
            fg_color=PALETTE["card"],
            corner_radius=14,
            border_width=1,
            border_color=PALETTE["border"],
        )
        cam_wrapper.grid(row=1, column=0, sticky="nsew")
        cam_wrapper.grid_columnconfigure(0, weight=1)
        cam_wrapper.grid_rowconfigure(0, weight=1)

        self._cam_lbl = ctk.CTkLabel(cam_wrapper, text="")
        self._cam_lbl.grid(row=0, column=0, padx=6, pady=6)
        self._cam_lbl.configure(image=placeholder_ctk_image(
            (CAM_W, CAM_H), "Press 'Start' to begin recognition"
        ))

        # Controls
        ctrl = ctk.CTkFrame(left, fg_color="transparent")
        ctrl.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ctrl.grid_columnconfigure(0, weight=1)
        ctrl.grid_columnconfigure(1, weight=1)

        self._start_btn = ctk.CTkButton(
            ctrl, text="▶  Start Recognition",
            height=44, corner_radius=10,
            fg_color=PALETTE["success"],
            hover_color="#27ae60",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start,
        )
        self._start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._stop_btn = ctk.CTkButton(
            ctrl, text="⏹  Stop",
            height=44, corner_radius=10,
            fg_color=PALETTE["danger"],
            hover_color="#c0392b",
            font=ctk.CTkFont(size=14, weight="bold"),
            state="disabled",
            command=self._stop,
        )
        self._stop_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    # ------------------------------------------------------------------
    # Info panel (right)
    # ------------------------------------------------------------------

    def _build_info_panel(self):
        right = ctk.CTkFrame(
            self,
            fg_color=PALETTE["card"],
            width=320,
            corner_radius=0,
        )
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)
        right.grid_propagate(False)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(3, weight=1)

        # Last recognised card
        ctk.CTkLabel(
            right, text="Last Recognised",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["text_secondary"],
        ).grid(row=0, column=0, padx=16, pady=(20, 4), sticky="w")

        self._recog_card = ctk.CTkFrame(
            right,
            fg_color=PALETTE["card2"],
            corner_radius=12,
            border_width=1,
            border_color=PALETTE["border"],
        )
        self._recog_card.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        self._recog_card.grid_columnconfigure(0, weight=1)

        self._recog_name  = ctk.CTkLabel(
            self._recog_card, text="—",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PALETTE["text"],
        )
        self._recog_name.grid(row=0, column=0, pady=(14, 2))

        self._recog_id    = ctk.CTkLabel(
            self._recog_card, text="",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        )
        self._recog_id.grid(row=1, column=0, pady=2)

        self._recog_dept  = ctk.CTkLabel(
            self._recog_card, text="",
            font=ctk.CTkFont(size=12),
            text_color=PALETTE["text_secondary"],
        )
        self._recog_dept.grid(row=2, column=0, pady=2)

        self._recog_conf  = ctk.CTkLabel(
            self._recog_card, text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["accent"],
        )
        self._recog_conf.grid(row=3, column=0, pady=(2, 8))

        self._att_toast   = ctk.CTkLabel(
            self._recog_card, text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PALETTE["success"],
        )
        self._att_toast.grid(row=4, column=0, pady=(0, 10))

        # Today's marked log
        ctk.CTkLabel(
            right, text="Marked Today",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETTE["text_secondary"],
        ).grid(row=2, column=0, padx=16, pady=(8, 4), sticky="w")

        self._log_frame = ctk.CTkScrollableFrame(
            right,
            fg_color="transparent",
            corner_radius=0,
        )
        self._log_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._log_frame.grid_columnconfigure(0, weight=1)

        # Threshold label
        self._thresh_lbl = ctk.CTkLabel(
            right, text="",
            font=ctk.CTkFont(size=11),
            text_color=PALETTE["text_secondary"],
        )
        self._thresh_lbl.grid(row=4, column=0, padx=12, pady=(0, 12), sticky="w")

        self._refresh_log()
        self._update_threshold_label()

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def _start(self):
        if not self.engine.is_trained:
            self._att_toast.configure(
                text="⚠ Model not trained! Use 'Train Model' first.",
                text_color=PALETTE["danger"],
            )
            self.after(4000, lambda: self._att_toast.configure(text=""))
            return

        self._running = True
        self._stop_evt.clear()
        self._student_cache = {
            s["StudentID"]: s for s in self.db.get_all_students()
        }

        cam_idx = int(self.db.get_setting("camera_index", "0"))

        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._status_badge.configure(text="● RUNNING", text_color=PALETTE["success"])

        threading.Thread(
            target=self._recognition_worker,
            args=(cam_idx,),
            daemon=True,
        ).start()
        self._poll_gui()

    def _stop(self):
        self._stop_evt.set()
        self._running = False
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_badge.configure(text="● STOPPED", text_color=PALETTE["danger"])
        self._fps_lbl.configure(text="FPS: —")
        self._cam_lbl.configure(
            image=placeholder_ctk_image(
                (CAM_W, CAM_H), "Press 'Start' to begin recognition"
            )
        )

    def _recognition_worker(self, cam_idx: int):
        """Background thread: reads frames, runs recognition, feeds queues."""
        cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(cam_idx)
        if not cap.isOpened():
            self.after(0, lambda: self._att_toast.configure(
                text="❌ Camera not available!", text_color=PALETTE["danger"]
            ))
            self._running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        dist_thresh = float(self.db.get_setting("confidence_threshold", "70"))
        fps_timer   = time.time()
        frame_count = 0

        try:
            while not self._stop_evt.is_set():
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.03)
                    continue

                frame_count += 1
                elapsed = time.time() - fps_timer
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    frame_count = 0
                    fps_timer   = time.time()
                    self.after(0, lambda f=fps: self._fps_lbl.configure(
                        text=f"FPS: {f:.0f}"
                    ))

                results = self.engine.recognize_frame(frame, dist_threshold=dist_thresh)
                annotated = self.engine.draw_results(frame, results, self._student_cache)

                if not self._frame_q.full():
                    self._frame_q.put(annotated)

                if not self._result_q.full():
                    self._result_q.put(results)

        finally:
            cap.release()

    def _poll_gui(self):
        """Main-thread poll: update camera label and process recognition results."""
        if not self._running:
            return

        # Update camera feed
        try:
            frame = self._frame_q.get_nowait()
            self._cam_lbl.configure(image=bgr_to_ctk_image(frame, (CAM_W, CAM_H)))
        except Exception:
            pass

        # Process recognition results
        try:
            results = self._result_q.get_nowait()
            for res in results:
                if res["student_id"]:
                    self._handle_recognition(res)
        except Exception:
            pass

        self.after(30, self._poll_gui)

    # ------------------------------------------------------------------
    # Attendance logic
    # ------------------------------------------------------------------

    def _handle_recognition(self, res: dict):
        sid  = res["student_id"]
        conf = res["confidence"]
        stu  = self._student_cache.get(sid)
        if not stu:
            return

        # Update info card
        self._recog_name.configure(text=stu["Name"])
        self._recog_id.configure(text=f"ID: {sid}   •   {stu['Year']}")
        self._recog_dept.configure(text=stu["Department"])
        self._recog_conf.configure(text=f"Confidence: {conf:.0f}%")

        # Auto-mark attendance (with de-bounce)
        now      = time.time()
        last     = self._last_marked.get(sid, 0)
        cooldown = self.MARK_COOLDOWN

        if now - last > cooldown:
            self._last_marked[sid] = now
            ok, msg = self.db.mark_attendance(sid, stu["Name"], stu["Department"])
            color = PALETTE["success"] if ok else PALETTE["warning"]
            self._att_toast.configure(text=msg, text_color=color)
            self.after(4000, lambda: self._att_toast.configure(text=""))

            if ok:
                self._recog_card.configure(border_color=PALETTE["success"])
                self.after(self.CARD_FLASH_MS,
                           lambda: self._recog_card.configure(
                               border_color=PALETTE["border"]
                           ))
                self._refresh_log()

    # ------------------------------------------------------------------
    # Log panel
    # ------------------------------------------------------------------

    def _refresh_log(self):
        for w in self._log_frame.winfo_children():
            w.destroy()

        records = self.db.get_today_attendance()
        if not records:
            ctk.CTkLabel(
                self._log_frame, text="No attendance yet today.",
                font=ctk.CTkFont(size=12),
                text_color=PALETTE["text_secondary"],
            ).pack(pady=8)
            return

        for rec in records:
            row = ctk.CTkFrame(
                self._log_frame,
                fg_color=PALETTE["card2"],
                corner_radius=8,
            )
            row.pack(fill="x", pady=2, padx=2)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                row, text=rec["Name"],
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=PALETTE["text"], anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 0))

            ctk.CTkLabel(
                row, text=f"{rec['StudentID']}  |  {rec['Time']}",
                font=ctk.CTkFont(size=11),
                text_color=PALETTE["text_secondary"], anchor="w",
            ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))

            ctk.CTkLabel(
                row, text="✓",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=PALETTE["success"],
            ).grid(row=0, column=1, rowspan=2, padx=10)

    def _update_threshold_label(self):
        t = self.db.get_setting("confidence_threshold", "70")
        self._thresh_lbl.configure(
            text=f"Distance threshold: {t}  (Settings to adjust)"
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_show(self):
        self._refresh_log()
        self._update_threshold_label()

    def on_hide(self):
        if self._running:
            self._stop()
