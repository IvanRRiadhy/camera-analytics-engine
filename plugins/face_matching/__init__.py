"""
Face Matching Vision Plugin Components.

Includes YuNet face detection and SFace deep facial feature embedding.
"""

from camera_analytics.plugins.face_matching.detector import FaceDetection, YuNetDetector
from camera_analytics.plugins.face_matching.embedder import BaseFaceEmbedder, SFaceEmbedder

__all__ = [
    "FaceDetection",
    "YuNetDetector",
    "BaseFaceEmbedder",
    "SFaceEmbedder",
]

