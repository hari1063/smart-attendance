"""
face_engine.py — FaceEngine for Smart Attendance System
Handles face detection, image capture, LBPH model training, and recognition.
Uses OpenCV's built-in LBPH recognizer (no dlib/CMake required).
"""

import cv2
import numpy as np
import os
import pickle
import threading
from pathlib import Path
from typing import Callable


# ── Constants ─────────────────────────────────────────────────────────────────

DATASET_DIR = "dataset"
TRAINER_DIR = "trainer"
TRAINER_YML = os.path.join(TRAINER_DIR, "trainer.yml")
LABEL_MAP   = os.path.join(TRAINER_DIR, "label_map.pkl")

CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


# ── FaceEngine ─────────────────────────────────────────────────────────────────

class FaceEngine:
    """
    Manages all face-recognition operations:
      • capture_images()  — grab 40 training images per student
      • train_model()     — build LBPH model from dataset
      • recognize_face()  — run prediction on a video frame
      • draw_results()    — overlay bounding boxes + labels onto frame
    """

    # Face ROI size fed into the recognizer
    FACE_SIZE = (200, 200)

    def __init__(self):
        self._cascade   = cv2.CascadeClassifier(CASCADE_PATH)
        self._recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )
        self._label_map: dict[int, str] = {}   # {label_id: student_id}
        self.is_trained = False

        # Ensure directories exist
        for d in (DATASET_DIR, TRAINER_DIR):
            Path(d).mkdir(parents=True, exist_ok=True)

        # Try to load a previously trained model
        self._load_model()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(self) -> bool:
        """Load persisted LBPH model and label map if available."""
        if os.path.isfile(TRAINER_YML) and os.path.isfile(LABEL_MAP):
            try:
                self._recognizer.read(TRAINER_YML)
                with open(LABEL_MAP, "rb") as fh:
                    self._label_map = pickle.load(fh)
                self.is_trained = True
                return True
            except Exception:
                self.is_trained = False
        return False

    def _detect(self, gray: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Run Haar cascade on a pre-converted grayscale frame."""
        eq = cv2.equalizeHist(gray)
        faces = self._cascade.detectMultiScale(
            eq,
            scaleFactor=1.15,
            minNeighbors=5,
            minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
        return list(faces) if len(faces) > 0 else []

    # ------------------------------------------------------------------
    # Public API — image capture
    # ------------------------------------------------------------------

    def capture_images(
        self,
        student_id: str,
        label_id: int,
        capture_count: int = 40,
        camera_index: int = 0,
        progress_cb: Callable[[int, int, np.ndarray, tuple], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> tuple[bool, str]:
        """
        Open the webcam and capture up-to `capture_count` face images.

        For each detected face the cropped grayscale ROI is saved to
        dataset/<student_id>/<student_id>_<n>.jpg

        progress_cb(count, total, bgr_frame, bbox) is called after each capture.
        stop_event allows the caller to abort early.
        """
        folder = Path(DATASET_DIR) / student_id
        folder.mkdir(parents=True, exist_ok=True)

        # Remove old images for fresh capture
        for f in folder.glob("*.jpg"):
            f.unlink(missing_ok=True)

        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(camera_index)          # fallback
        if not cap.isOpened():
            return False, "Could not open camera. Check camera index in Settings."

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        count = 0
        try:
            while count < capture_count:
                if stop_event and stop_event.is_set():
                    break

                ret, frame = cap.read()
                if not ret:
                    continue

                gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self._detect(gray)

                for (x, y, w, h) in faces[:1]:   # use the largest/first face only
                    count += 1
                    roi = cv2.resize(gray[y : y + h, x : x + w], self.FACE_SIZE)
                    path = str(folder / f"{student_id}_{count}.jpg")
                    cv2.imwrite(path, roi)

                    if progress_cb:
                        progress_cb(count, capture_count, frame.copy(), (x, y, w, h))

                    if count >= capture_count:
                        break

        finally:
            cap.release()

        if count < 5:
            return (
                False,
                f"Only captured {count} images. Ensure good lighting, "
                "face the camera directly, and try again.",
            )
        return True, f"Captured {count} images for student {student_id}."

    # ------------------------------------------------------------------
    # Public API — training
    # ------------------------------------------------------------------

    def train_model(
        self,
        db_manager,
        progress_cb: Callable[[str, int], None] | None = None,
    ) -> tuple[bool, str]:
        """
        Read all dataset images and (re)train the LBPH recognizer.
        `progress_cb(student_name, total_images_so_far)` optional callback.
        """
        students = db_manager.get_all_students()
        if not students:
            return False, "No students registered — nothing to train."

        faces_data: list[np.ndarray] = []
        labels:     list[int]        = []
        label_map:  dict[int, str]   = {}
        total = 0

        for stu in students:
            sid      = stu["StudentID"]
            label_id = stu["LabelID"]
            folder   = Path(DATASET_DIR) / sid

            if not folder.exists():
                continue

            imgs = sorted(folder.glob("*.jpg"))
            if not imgs:
                continue

            label_map[label_id] = sid

            for img_path in imgs:
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img = cv2.resize(img, self.FACE_SIZE)
                faces_data.append(img)
                labels.append(label_id)
                total += 1

            if progress_cb:
                progress_cb(stu["Name"], total)

        if not faces_data:
            return (
                False,
                "No training images found in dataset/. "
                "Register students and capture images first.",
            )

        # Build a fresh recognizer
        rec = cv2.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )
        rec.train(faces_data, np.array(labels, dtype=np.int32))

        Path(TRAINER_DIR).mkdir(parents=True, exist_ok=True)
        rec.save(TRAINER_YML)
        with open(LABEL_MAP, "wb") as fh:
            pickle.dump(label_map, fh)

        self._recognizer = rec
        self._label_map  = label_map
        self.is_trained  = True

        return (
            True,
            f"Model trained on {total} images from {len(label_map)} student(s).",
        )

    # ------------------------------------------------------------------
    # Public API — recognition
    # ------------------------------------------------------------------

    def recognize_frame(
        self,
        frame: np.ndarray,
        dist_threshold: float = 70.0,
    ) -> list[dict]:
        """
        Detect and recognise all faces in a BGR frame.

        Returns a list of dicts:
          {
            "bbox":       (x, y, w, h),
            "student_id": str | None,
            "label_id":   int,
            "distance":   float,
            "confidence": float   # 0-100; higher = more confident
          }
        """
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._detect(gray)
        results = []

        for (x, y, w, h) in faces:
            roi = cv2.resize(gray[y : y + h, x : x + w], self.FACE_SIZE)

            if self.is_trained:
                try:
                    label, dist = self._recognizer.predict(roi)
                except Exception:
                    label, dist = -1, 999.0
            else:
                label, dist = -1, 999.0

            # Map distance → 0-100 confidence display
            # LBPH distances in practice: 0-30 great, 30-60 ok, 60-80 borderline, 80+ unknown
            confidence = max(0.0, min(100.0, round(100.0 - dist, 1)))

            if self.is_trained and dist <= dist_threshold:
                student_id = self._label_map.get(label)
            else:
                student_id = None

            results.append(
                {
                    "bbox":       (x, y, w, h),
                    "student_id": student_id,
                    "label_id":   label,
                    "distance":   round(dist, 1),
                    "confidence": confidence,
                }
            )

        return results

    # ------------------------------------------------------------------
    # Public API — drawing
    # ------------------------------------------------------------------

    def draw_results(
        self,
        frame:    np.ndarray,
        results:  list[dict],
        students: dict[str, dict],          # {student_id: student_row}
    ) -> np.ndarray:
        """
        Overlay bounding boxes + labels onto a copy of `frame`.
        `students` is a lookup dict populated from the DB.
        """
        out = frame.copy()

        for res in results:
            x, y, w, h = res["bbox"]

            if res["student_id"] and res["student_id"] in students:
                stu   = students[res["student_id"]]
                color = (0, 220, 100)                  # green — known
                line1 = stu["Name"]
                line2 = f"{stu['StudentID']}  {res['confidence']:.0f}%"
            else:
                color = (60, 60, 240)                  # red-ish — unknown
                line1 = "Unknown"
                line2 = ""

            # Rectangle
            cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)

            # Top label bar
            bar_y = y - 28 if y > 30 else y + h + 2
            cv2.rectangle(out, (x, bar_y), (x + w, bar_y + 28), color, -1)
            cv2.putText(
                out, line1, (x + 4, bar_y + 18),
                cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA,
            )

            if line2:
                cv2.putText(
                    out, line2, (x + 4, y + h + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA,
                )

        return out

    # ------------------------------------------------------------------
    # Public API — dataset helpers
    # ------------------------------------------------------------------

    def delete_student_images(self, student_id: str) -> tuple[bool, str]:
        """Remove the dataset folder for a student."""
        import shutil
        folder = Path(DATASET_DIR) / student_id
        try:
            if folder.exists():
                shutil.rmtree(folder)
            return True, f"Images deleted for {student_id}."
        except Exception as exc:
            return False, f"Could not delete images: {exc}"

    def image_count(self, student_id: str) -> int:
        """Return number of captured images for a student."""
        folder = Path(DATASET_DIR) / student_id
        if not folder.exists():
            return 0
        return len(list(folder.glob("*.jpg")))

    def available_cameras(self, max_index: int = 4) -> list[int]:
        """Return list of available camera indices."""
        available = []
        for idx in range(max_index):
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                available.append(idx)
                cap.release()
        return available
