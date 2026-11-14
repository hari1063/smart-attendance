"""
database.py — DatabaseManager for Smart Attendance System
Handles all SQLite operations: students, attendance, settings, export.
"""

import sqlite3
import os
import shutil
from datetime import datetime
from pathlib import Path
import pandas as pd


class DatabaseManager:
    """
    Manages all SQLite database operations for the Smart Attendance System.
    Provides methods for student CRUD, attendance tracking, settings, and exports.
    """

    def __init__(self, db_path: str = "database/attendance.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.create_tables()

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Return a connection with Row factory enabled."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------

    def create_tables(self):
        """Create all required tables if they do not already exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS Students (
            StudentID       TEXT PRIMARY KEY,
            Name            TEXT NOT NULL,
            Department      TEXT NOT NULL,
            Year            TEXT NOT NULL,
            Section         TEXT NOT NULL,
            ImagePath       TEXT DEFAULT '',
            RegisteredDate  TEXT NOT NULL,
            LabelID         INTEGER NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS Attendance (
            AttendanceID  INTEGER PRIMARY KEY AUTOINCREMENT,
            StudentID     TEXT    NOT NULL,
            Name          TEXT    NOT NULL,
            Department    TEXT    NOT NULL,
            Date          TEXT    NOT NULL,
            Time          TEXT    NOT NULL,
            Status        TEXT    NOT NULL DEFAULT 'Present',
            FOREIGN KEY (StudentID) REFERENCES Students(StudentID)
        );

        CREATE TABLE IF NOT EXISTS Settings (
            Key   TEXT PRIMARY KEY,
            Value TEXT NOT NULL
        );
        """
        defaults = [
            ("admin_password",       "admin123"),
            ("confidence_threshold", "70"),   # distance threshold (lower = stricter)
            ("camera_index",         "0"),
            ("theme",                "dark"),
            ("capture_count",        "40"),
        ]
        with self._connect() as conn:
            conn.executescript(ddl)
            conn.executemany(
                "INSERT OR IGNORE INTO Settings (Key, Value) VALUES (?, ?)",
                defaults,
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Student operations
    # ------------------------------------------------------------------

    def add_student(
        self,
        student_id: str,
        name: str,
        department: str,
        year: str,
        section: str,
        image_path: str = "",
    ) -> tuple[bool, str]:
        """Insert a new student. Returns (success, message)."""
        try:
            with self._connect() as conn:
                # Duplicate check
                if conn.execute(
                    "SELECT 1 FROM Students WHERE StudentID = ?", (student_id,)
                ).fetchone():
                    return False, f"Student ID '{student_id}' already exists!"

                # Next label ID
                row = conn.execute("SELECT MAX(LabelID) FROM Students").fetchone()
                label_id = (row[0] + 1) if row[0] is not None else 1

                conn.execute(
                    """INSERT INTO Students
                       (StudentID, Name, Department, Year, Section,
                        ImagePath, RegisteredDate, LabelID)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        student_id, name, department, year, section,
                        image_path,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        label_id,
                    ),
                )
                conn.commit()
                return True, f"Student '{name}' registered successfully!"
        except sqlite3.Error as exc:
            return False, f"Database error: {exc}"

    def get_all_students(self) -> list[dict]:
        """Return all students ordered by name."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM Students ORDER BY Name"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_student_by_id(self, student_id: str) -> dict | None:
        """Return a single student dict or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM Students WHERE StudentID = ?", (student_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_student_by_label(self, label_id: int) -> dict | None:
        """Return the student assigned the given LBPH label."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM Students WHERE LabelID = ?", (label_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_student(
        self,
        student_id: str,
        name: str,
        department: str,
        year: str,
        section: str,
    ) -> tuple[bool, str]:
        """Update mutable student fields. Returns (success, message)."""
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    """UPDATE Students
                       SET Name=?, Department=?, Year=?, Section=?
                       WHERE StudentID=?""",
                    (name, department, year, section, student_id),
                )
                if cur.rowcount == 0:
                    return False, "Student not found!"
                conn.commit()
                return True, "Student updated successfully!"
        except sqlite3.Error as exc:
            return False, f"Database error: {exc}"

    def delete_student(self, student_id: str) -> tuple[bool, str]:
        """Delete a student and all their attendance records."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM Attendance WHERE StudentID = ?", (student_id,)
                )
                cur = conn.execute(
                    "DELETE FROM Students WHERE StudentID = ?", (student_id,)
                )
                if cur.rowcount == 0:
                    return False, "Student not found!"
                conn.commit()
                return True, "Student and attendance records deleted!"
        except sqlite3.Error as exc:
            return False, f"Database error: {exc}"

    def student_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM Students").fetchone()[0]

    def get_departments(self) -> list[str]:
        """Return sorted list of unique departments."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT Department FROM Students ORDER BY Department"
            ).fetchall()
            return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Attendance operations
    # ------------------------------------------------------------------

    def mark_attendance(
        self, student_id: str, name: str, department: str
    ) -> tuple[bool, str]:
        """
        Insert an attendance record for today.
        Returns (False, message) if already marked today.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        now   = datetime.now().strftime("%H:%M:%S")
        try:
            with self._connect() as conn:
                if conn.execute(
                    "SELECT 1 FROM Attendance WHERE StudentID=? AND Date=?",
                    (student_id, today),
                ).fetchone():
                    return False, f"{name} is already marked present today."
                conn.execute(
                    """INSERT INTO Attendance
                       (StudentID, Name, Department, Date, Time, Status)
                       VALUES (?, ?, ?, ?, ?, 'Present')""",
                    (student_id, name, department, today, now),
                )
                conn.commit()
                return True, f"✓ Attendance recorded for {name}!"
        except sqlite3.Error as exc:
            return False, f"Database error: {exc}"

    def is_marked_today(self, student_id: str) -> bool:
        """Check if a student is already marked for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        with self._connect() as conn:
            return bool(
                conn.execute(
                    "SELECT 1 FROM Attendance WHERE StudentID=? AND Date=?",
                    (student_id, today),
                ).fetchone()
            )

    def get_attendance(
        self,
        date_from:  str | None = None,
        date_to:    str | None = None,
        student_id: str | None = None,
        department: str | None = None,
    ) -> list[dict]:
        """Return filtered attendance records, newest first."""
        query  = "SELECT * FROM Attendance WHERE 1=1"
        params: list = []

        if date_from:
            query += " AND Date >= ?"; params.append(date_from)
        if date_to:
            query += " AND Date <= ?"; params.append(date_to)
        if student_id:
            query += " AND (StudentID LIKE ? OR Name LIKE ?)"; params += [f"%{student_id}%"] * 2
        if department:
            query += " AND Department = ?"; params.append(department)

        query += " ORDER BY Date DESC, Time DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_today_attendance(self) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.get_attendance(date_from=today, date_to=today)

    def get_stats(self) -> dict:
        """Return dashboard statistics."""
        today       = datetime.now().strftime("%Y-%m-%d")
        month_start = datetime.now().strftime("%Y-%m-01")

        with self._connect() as conn:
            total_students = conn.execute("SELECT COUNT(*) FROM Students").fetchone()[0]
            today_count    = conn.execute(
                "SELECT COUNT(*) FROM Attendance WHERE Date=?", (today,)
            ).fetchone()[0]
            month_students = conn.execute(
                "SELECT COUNT(DISTINCT StudentID) FROM Attendance WHERE Date>=?",
                (month_start,),
            ).fetchone()[0]
            total_records  = conn.execute("SELECT COUNT(*) FROM Attendance").fetchone()[0]

        return {
            "total_students":  total_students,
            "today_count":     today_count,
            "month_students":  month_students,
            "total_records":   total_records,
            "attendance_rate": round(
                (today_count / total_students * 100) if total_students else 0, 1
            ),
        }

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT Value FROM Settings WHERE Key=?", (key,)
            ).fetchone()
            return row[0] if row else default

    def set_setting(self, key: str, value: str) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO Settings (Key, Value) VALUES (?, ?)",
                    (key, value),
                )
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_to_csv(self, filepath: str, records: list[dict]) -> tuple[bool, str]:
        """Write records to a CSV file."""
        try:
            if not records:
                return False, "No records to export."
            pd.DataFrame(records).to_csv(filepath, index=False)
            return True, f"Exported {len(records)} records to {filepath}"
        except Exception as exc:
            return False, f"Export error: {exc}"

    def export_to_excel(self, filepath: str, records: list[dict]) -> tuple[bool, str]:
        """Write records to an Excel (.xlsx) file."""
        try:
            if not records:
                return False, "No records to export."
            df = pd.DataFrame(records)
            with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Attendance")
                ws = writer.sheets["Attendance"]
                for col in ws.columns:
                    ws.column_dimensions[col[0].column_letter].width = max(
                        len(str(col[0].value)) + 4,
                        max(len(str(c.value or "")) for c in col) + 2,
                    )
            return True, f"Exported {len(records)} records to {filepath}"
        except Exception as exc:
            return False, f"Export error: {exc}"

    # ------------------------------------------------------------------
    # Backup / Restore
    # ------------------------------------------------------------------

    def backup(self, backup_path: str) -> tuple[bool, str]:
        try:
            shutil.copy2(self.db_path, backup_path)
            return True, f"Database backed up to {backup_path}"
        except Exception as exc:
            return False, f"Backup error: {exc}"

    def restore(self, backup_path: str) -> tuple[bool, str]:
        try:
            shutil.copy2(backup_path, self.db_path)
            return True, "Database restored successfully!"
        except Exception as exc:
            return False, f"Restore error: {exc}"
