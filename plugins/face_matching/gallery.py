"""
Face Gallery Enrollment, Validation, SHA256 Caching, and Vector Similarity Matching.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import cv2
import numpy as np

from camera_analytics.core.human.quality_estimator import FaceQualityEstimator
from camera_analytics.plugins.face_matching.detector import FaceDetection, YuNetDetector
from camera_analytics.plugins.face_matching.embedder import BaseFaceEmbedder

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PersonMetadata:
    """Metadata attributes associated with an enrolled identity."""

    person_id: str
    full_name: str
    department: str = ""
    role: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PersonCandidate:
    """Evaluated match candidate representing a unique enrolled person."""

    person_id: str
    full_name: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class FaceGallery:
    """In-memory gallery index of enrolled face embeddings with person-level aggregation."""

    def __init__(
        self,
        embeddings: np.ndarray,
        owner_ids: List[str],
        persons: Dict[str, PersonMetadata],
        cache_dir: Optional[Path] = None,
        accepted_images_count: int = 0,
        rejected_images_count: int = 0,
        excluded_people_count: int = 0,
        rejection_reasons_summary: Optional[Dict[str, int]] = None,
        single_image_people: Optional[List[str]] = None,
        confusable_pairs: Optional[List[Tuple[str, str, float]]] = None,
        startup_report: str = "",
    ) -> None:
        self._embeddings = embeddings  # Shape: (N, 128) float32 L2-normalized
        self._owner_ids = owner_ids    # Length: N
        self._persons = persons        # Maps person_id -> PersonMetadata
        self._cache_dir = cache_dir
        self.accepted_images_count = accepted_images_count
        self.rejected_images_count = rejected_images_count
        self.excluded_people_count = excluded_people_count
        self.rejection_reasons_summary = rejection_reasons_summary or {}
        self.single_image_people = single_image_people or []
        self.confusable_pairs = confusable_pairs or []
        self.startup_report = startup_report

    @property
    def size(self) -> int:
        """Return total number of distinct enrolled identities."""
        return len(self._persons)

    @property
    def total_embeddings(self) -> int:
        """Return total number of enrolled face template vectors."""
        return len(self._owner_ids)

    @property
    def total_people(self) -> int:
        """Return total number of distinct enrolled identities."""
        return len(self._persons)

    def get_person(self, person_id: str) -> Optional[PersonMetadata]:
        """Retrieve person metadata by ID."""
        return self._persons.get(person_id)

    def match(self, query_embedding: np.ndarray, top_k: int = 5) -> List[PersonCandidate]:
        """Perform vectorized cosine similarity search returning best score per unique person.

        Args:
            query_embedding: 1D float32 L2-normalized query embedding (128-D).
            top_k: Maximum number of distinct person candidates to return.

        Returns:
            List of PersonCandidate objects sorted descending by score.
            The top-2 candidate is guaranteed to be a different person, not a second image of top-1.
        """
        if self._embeddings.size == 0 or len(self._owner_ids) == 0:
            return []

        q = np.asarray(query_embedding, dtype=np.float32).flatten()
        norm = float(np.linalg.norm(q))
        if norm > 1e-9:
            q = q / norm
        else:
            return []

        # Vectorized cosine dot product against all N gallery templates
        scores = np.dot(self._embeddings, q)

        # Aggregate by person: person score = max over that person's images
        person_best_scores: Dict[str, float] = {}
        for p_id, score_val in zip(self._owner_ids, scores):
            s = float(score_val)
            if p_id not in person_best_scores or s > person_best_scores[p_id]:
                person_best_scores[p_id] = s

        # Sort candidate persons descending by score
        sorted_pairs = sorted(person_best_scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]

        candidates: List[PersonCandidate] = []
        for p_id, best_score in sorted_pairs:
            p_meta = self._persons.get(p_id)
            full_name = p_meta.full_name if p_meta else p_id
            extra_meta = p_meta.metadata if p_meta else {}
            candidates.append(
                PersonCandidate(
                    person_id=p_id,
                    full_name=full_name,
                    score=round(best_score, 4),
                    metadata=extra_meta,
                )
            )

        return candidates

    @classmethod
    def load(
        cls,
        gallery_path: Union[str, Path],
        detector: YuNetDetector,
        embedder: BaseFaceEmbedder,
        cosine_threshold: float = 0.40,
        cache_dir: Optional[Union[str, Path]] = None,
    ) -> FaceGallery:
        """Load, validate, and index face identity profiles from a gallery directory.

        Enrollment Rules per image:
            1. Exactly one face detected (reject 0 or >1).
            2. Face bounding box width >= 80 px.
            3. Near-frontal orientation: eye-line roll < 20 deg and nose between the eyes horizontally.
            4. Composite FaceQualityEstimator >= 0.30.

        Args:
            gallery_path: Directory path containing identity profiles.
            detector: YuNetDetector instance for face detection & landmarks.
            embedder: BaseFaceEmbedder instance for 128-D embedding extraction.
            cosine_threshold: Threshold above which two distinct identities are flagged as confusable.
            cache_dir: Cache directory for SHA256 embedding vectors (default: cache/faces).

        Returns:
            FaceGallery index instance ready for thread-safe matching.
        """
        start_time = time.perf_counter()
        g_path = Path(gallery_path).resolve()
        if not g_path.is_dir():
            raise FileNotFoundError(f"Face gallery directory not found at: {g_path}")

        # Resolve cache directory relative to exe folder when frozen or CWD
        if cache_dir is None:
            if getattr(sys, "frozen", False):
                base_dir = Path(sys.executable).resolve().parent
            else:
                base_dir = Path.cwd()
            c_path = base_dir / "cache" / "faces"
        else:
            c_path = Path(cache_dir).resolve()
        c_path.mkdir(parents=True, exist_ok=True)

        valid_exts = {".jpg", ".jpeg", ".png", ".webp"}

        # 1. Discover all identity packages
        # Maps person_id -> {"images": List[Path], "meta_file": Optional[Path]}
        person_packages: Dict[str, Dict[str, Any]] = {}

        # Mode A: Subdirectories per person (<id>/ containing images + meta.json)
        for item in sorted(g_path.iterdir()):
            if item.is_dir():
                p_id = item.name
                imgs = sorted([f for f in item.iterdir() if f.is_file() and f.suffix.lower() in valid_exts])
                meta_f = item / "meta.json"
                if not meta_f.exists():
                    meta_f = item / f"{p_id}_meta.json"
                if not meta_f.exists():
                    meta_f = item / f"{p_id}.json"
                if imgs:
                    person_packages[p_id] = {
                        "images": imgs,
                        "meta_file": meta_f if meta_f.exists() else None,
                    }

        # Mode B: Flat files (<id>.(jpg|png) paired with <id>_meta.json)
        for item in sorted(g_path.iterdir()):
            if item.is_file() and item.suffix.lower() in valid_exts:
                p_id = item.stem
                if p_id in person_packages:
                    continue
                meta_candidates = [
                    g_path / f"{p_id}_meta.json",
                    g_path / f"{p_id}.json",
                    g_path / f"{p_id}.meta.json",
                ]
                meta_f = next((mf for mf in meta_candidates if mf.exists()), None)
                person_packages[p_id] = {
                    "images": [item],
                    "meta_file": meta_f,
                }

        # 2. Process, validate, and embed identity images
        all_embeddings: List[np.ndarray] = []
        all_owner_ids: List[str] = []
        loaded_persons: Dict[str, PersonMetadata] = {}

        accepted_images_count = 0
        rejected_images_count = 0
        rejection_reasons_summary: Dict[str, int] = {}
        single_image_people: List[str] = []
        excluded_people_count = 0

        for p_id, pkg in person_packages.items():
            meta_dict: Dict[str, Any] = {}
            full_name = p_id
            dept = ""
            role = ""

            if pkg["meta_file"] and pkg["meta_file"].is_file():
                try:
                    with open(pkg["meta_file"], "r", encoding="utf-8") as mf:
                        meta_dict = json.load(mf)
                    full_name = meta_dict.get("full_name", meta_dict.get("name", p_id))
                    dept = meta_dict.get("department", "")
                    role = meta_dict.get("role", "")
                except Exception as meta_exc:
                    logger.warning("[FaceGallery] Failed to parse metadata file '%s': %s", pkg["meta_file"], meta_exc)

            person_accepted_embs: List[np.ndarray] = []

            for img_path in pkg["images"]:
                # Compute image SHA256
                try:
                    raw_bytes = img_path.read_bytes()
                    img_sha = hashlib.sha256(raw_bytes).hexdigest()
                except Exception as read_exc:
                    rejected_images_count += 1
                    reason = f"read_failure: {read_exc}"
                    rejection_reasons_summary[reason] = rejection_reasons_summary.get(reason, 0) + 1
                    logger.warning("[FaceGallery] Rejected image for '%s' (%s): %s", p_id, img_path.name, reason)
                    continue

                cache_file = c_path / f"{img_sha}.npy"

                # Check embedding cache
                if cache_file.is_file():
                    try:
                        emb = np.load(str(cache_file))
                        if emb.shape == (128,) and abs(float(np.linalg.norm(emb)) - 1.0) < 1e-4:
                            person_accepted_embs.append(emb)
                            accepted_images_count += 1
                            continue
                    except Exception:
                        pass  # Invalidate corrupted cache and re-process

                # Decode image
                frame = cv2.imread(str(img_path))
                if frame is None or frame.size == 0:
                    rejected_images_count += 1
                    reason = "unreadable_image"
                    rejection_reasons_summary[reason] = rejection_reasons_summary.get(reason, 0) + 1
                    logger.warning("[FaceGallery] Rejected image for '%s' (%s): %s", p_id, img_path.name, reason)
                    continue

                # Validation 1: Exactly one face detected
                faces = detector.detect(frame)
                if len(faces) == 0:
                    rejected_images_count += 1
                    reason = "zero_faces_detected"
                    rejection_reasons_summary[reason] = rejection_reasons_summary.get(reason, 0) + 1
                    logger.warning("[FaceGallery] Rejected image for '%s' (%s): No face detected", p_id, img_path.name)
                    continue
                if len(faces) > 1:
                    rejected_images_count += 1
                    reason = f"multiple_faces_detected ({len(faces)})"
                    rejection_reasons_summary[reason] = rejection_reasons_summary.get(reason, 0) + 1
                    logger.warning("[FaceGallery] Rejected image for '%s' (%s): Found %d faces (expected exactly 1)", p_id, img_path.name, len(faces))
                    continue

                face = faces[0]

                # Validation 2: Face width >= 80 px
                if face.w < 80.0:
                    rejected_images_count += 1
                    reason = f"width_too_small ({face.w:.1f}px < 80px)"
                    rejection_reasons_summary[reason] = rejection_reasons_summary.get(reason, 0) + 1
                    logger.warning("[FaceGallery] Rejected image for '%s' (%s): Face width %.1fpx < 80px", p_id, img_path.name, face.w)
                    continue

                # Validation 3: Near-frontal orientation (roll < 20 deg, nose between eyes)
                re, le, nt, rm, lm = face.landmarks
                dy = le[1] - re[1]
                dx = le[0] - re[0]
                roll_deg = abs(cv2.fastAtan2(dy, dx))
                if roll_deg > 180.0:
                    roll_deg = 360.0 - roll_deg

                if roll_deg >= 20.0:
                    rejected_images_count += 1
                    reason = f"excessive_roll ({roll_deg:.1f} deg >= 20 deg)"
                    rejection_reasons_summary[reason] = rejection_reasons_summary.get(reason, 0) + 1
                    logger.warning("[FaceGallery] Rejected image for '%s' (%s): Eye roll %.1f deg >= 20 deg", p_id, img_path.name, roll_deg)
                    continue

                min_eye_x = min(re[0], le[0])
                max_eye_x = max(re[0], le[0])
                if not (min_eye_x <= nt[0] <= max_eye_x):
                    rejected_images_count += 1
                    reason = f"nose_not_between_eyes (nose_x={nt[0]:.1f} not in [{min_eye_x:.1f}, {max_eye_x:.1f}])"
                    rejection_reasons_summary[reason] = rejection_reasons_summary.get(reason, 0) + 1
                    logger.warning("[FaceGallery] Rejected image for '%s' (%s): Nose not horizontally between eyes", p_id, img_path.name)
                    continue

                # Validation 4: Face quality >= 0.30
                img_h, img_w = frame.shape[:2]
                fx1 = max(0, int(round(face.x)))
                fy1 = max(0, int(round(face.y)))
                fx2 = min(img_w, int(round(face.x + face.w)))
                fy2 = min(img_h, int(round(face.y + face.h)))
                crop = frame[fy1:fy2, fx1:fx2]
                q_score = FaceQualityEstimator.evaluate_quality(face_crop=crop) if crop.size > 0 else 0.0

                if q_score < 0.30:
                    rejected_images_count += 1
                    reason = f"low_quality ({q_score:.3f} < 0.30)"
                    rejection_reasons_summary[reason] = rejection_reasons_summary.get(reason, 0) + 1
                    logger.warning("[FaceGallery] Rejected image for '%s' (%s): Quality score %.3f < 0.30", p_id, img_path.name, q_score)
                    continue

                # All enrollment gates passed: extract and cache embedding
                try:
                    emb = embedder.embed(frame, face)
                    np.save(str(cache_file), emb)
                    person_accepted_embs.append(emb)
                    accepted_images_count += 1
                except Exception as emb_exc:
                    rejected_images_count += 1
                    reason = f"embedding_error: {emb_exc}"
                    rejection_reasons_summary[reason] = rejection_reasons_summary.get(reason, 0) + 1
                    logger.warning("[FaceGallery] Rejected image for '%s' (%s): Embedding failed (%s)", p_id, img_path.name, emb_exc)

            if len(person_accepted_embs) == 0:
                excluded_people_count += 1
                logger.warning("[FaceGallery] Excluded person '%s': No accepted face images", p_id)
            else:
                if len(person_accepted_embs) == 1:
                    single_image_people.append(p_id)

                loaded_persons[p_id] = PersonMetadata(
                    person_id=p_id,
                    full_name=full_name,
                    department=dept,
                    role=role,
                    metadata=meta_dict,
                )
                for e in person_accepted_embs:
                    all_embeddings.append(e)
                    all_owner_ids.append(p_id)

        # Assemble normalized feature matrix
        if all_embeddings:
            embeddings_mat = np.stack(all_embeddings, axis=0).astype(np.float32)
        else:
            embeddings_mat = np.zeros((0, 128), dtype=np.float32)

        # 3. Confusable-Identity Check
        confusable_pairs: List[Tuple[str, str, float]] = []
        if len(all_embeddings) > 1:
            # Pairwise cosine matrix
            sim_matrix = np.dot(embeddings_mat, embeddings_mat.T)
            n_templates = len(all_owner_ids)
            seen_pairs: Set[Tuple[str, str]] = set()

            for i in range(n_templates):
                for j in range(i + 1, n_templates):
                    id_a = all_owner_ids[i]
                    id_b = all_owner_ids[j]
                    if id_a == id_b:
                        continue
                    pair_key = (min(id_a, id_b), max(id_a, id_b))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    pair_sim = float(sim_matrix[i, j])
                    if pair_sim >= cosine_threshold:
                        confusable_pairs.append((id_a, id_b, pair_sim))
                        logger.warning(
                            "[FaceGallery] Confusable identity detected between '%s' and '%s' (similarity: %.4f >= %.4f)",
                            id_a, id_b, pair_sim, cosine_threshold
                        )

        # 4. Warnings for single-image persons
        for p_single in single_image_people:
            logger.warning("[FaceGallery] Person '%s' has only 1 enrolled image (higher risk of lighting/pose variance)", p_single)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # 5. Startup Report (Single unified INFO block)
        startup_report = (
            f"\n======================================================================\n"
            f"  FACE GALLERY ENROLLMENT STARTUP REPORT\n"
            f"======================================================================\n"
            f"Gallery Path       : {g_path}\n"
            f"Cache Path         : {c_path}\n"
            f"People Enrolled    : {len(loaded_persons)} / {len(person_packages)}\n"
            f"People Excluded    : {excluded_people_count}\n"
            f"Images Accepted    : {accepted_images_count}\n"
            f"Images Rejected    : {rejected_images_count}\n"
            f"Single-Image People: {len(single_image_people)} ({', '.join(single_image_people) if single_image_people else 'None'})\n"
            f"Confusable Pairs   : {len(confusable_pairs)}\n"
            f"Total Matrix Shape : {embeddings_mat.shape}\n"
            f"Indexing Time      : {elapsed_ms:.2f} ms\n"
            f"Rejection Summary  : {rejection_reasons_summary or 'None'}\n"
            f"======================================================================"
        )
        logger.info(startup_report)

        return cls(
            embeddings=embeddings_mat,
            owner_ids=all_owner_ids,
            persons=loaded_persons,
            cache_dir=c_path,
            accepted_images_count=accepted_images_count,
            rejected_images_count=rejected_images_count,
            excluded_people_count=excluded_people_count,
            rejection_reasons_summary=rejection_reasons_summary,
            single_image_people=single_image_people,
            confusable_pairs=confusable_pairs,
            startup_report=startup_report,
        )
