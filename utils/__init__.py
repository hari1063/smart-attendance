"""
Utils package for Smart Attendance System.
Exposes DatabaseManager, FaceEngine, and helper functions.
"""
from .database import DatabaseManager
from .face_engine import FaceEngine
from . import helpers

__all__ = ["DatabaseManager", "FaceEngine", "helpers"]
