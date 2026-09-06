"""
Core Re-Verification Engine (USP - Mandatory Component).
Every candidate returned by the search API is treated strictly as an unverified visual lead.
This module downloads each candidate, executes face detection and encoding using the
exact same biometric model, and calculates vector embedding distance.
Only candidates satisfying the mathematical similarity threshold are permitted on-chain.
"""

import os
import io
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any, Tuple
import requests
import numpy as np
import cv2

from core.face_encoder import FaceEncoder, FaceDetectionResult
from core.reverse_search import SearchCandidate


@dataclass
class CandidateVerificationResult:
    candidate: SearchCandidate
    face_detected: bool
    detection_confidence: float
    cosine_similarity: float
    cosine_distance: float
    euclidean_distance: float
    is_verified: bool
    status_reason: str
    match_confidence_bp: int       # Basis points [0 - 10000] (e.g., 9407 = 94.07%)
    candidate_embedding: Optional[np.ndarray] = None
    candidate_face_hash: Optional[str] = None
    quality_passed: bool = True
    quality_score: float = 0.0
    multi_face_audit: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class VerificationReport:
    query_face: FaceDetectionResult
    total_candidates_examined: int
    verified_matches: List[CandidateVerificationResult]
    rejected_candidates: List[CandidateVerificationResult]
    best_match: Optional[CandidateVerificationResult]
    has_verified_match: bool
    threshold_used: float


class ReVerificationEngine:
    """
    Independent Biometric Verification Engine.
    Enforces that search API results cannot be written on-chain without
    explicit mathematical proof of biometric identity match.
    """

    def __init__(
        self,
        encoder: FaceEncoder,
        similarity_threshold: float = 0.60,
        request_timeout: int = 15,
        min_dimension: int = 80,
        min_blur_variance: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5
    ):
        self.encoder = encoder
        self.similarity_threshold = similarity_threshold
        self.request_timeout = request_timeout
        self.min_dimension = min_dimension
        self.min_blur_variance = min_blur_variance
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def evaluate_image_quality(self, img: np.ndarray) -> Tuple[bool, float, str]:
        """
        Inspect candidate image for blur (Laplacian variance) and minimum resolution.
        Ensures low-quality or blurry images are flagged explicitly as quality-insufficient
        rather than producing ambiguous low similarity scores.
        """
        h, w = img.shape[:2]
        if w < self.min_dimension or h < self.min_dimension:
            return False, 0.0, f"QUALITY_INSUFFICIENT: Resolution {w}x{h} below minimum threshold {self.min_dimension}x{self.min_dimension}"

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if blur_var < self.min_blur_variance:
            return False, blur_var, f"QUALITY_INSUFFICIENT: Image blur score {blur_var:.1f} < threshold {self.min_blur_variance:.1f}"

        return True, blur_var, f"QUALITY_OK: Focus {blur_var:.1f}, {w}x{h}"

    def _download_image(self, url_or_path: str) -> Tuple[Optional[np.ndarray], str]:
        """
        Fetch image from URL with retry and exponential backoff, or read local file path.
        Returns (image_ndarray_or_None, status_detail_str).
        """
        # Check if local path exists first
        if os.path.exists(url_or_path):
            img = cv2.imread(url_or_path)
            if img is not None:
                return img, "OK_LOCAL"
            return None, f"FAILED_READ: Image at '{url_or_path}' could not be decoded"

        # Otherwise attempt HTTP fetch with retry and backoff
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            last_err = ""
            for attempt in range(1, self.max_retries + 1):
                try:
                    resp = requests.get(url_or_path, headers=headers, timeout=self.request_timeout)
                    if resp.status_code == 200:
                        arr = np.frombuffer(resp.content, dtype=np.uint8)
                        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if img is not None:
                            return img, "OK_HTTP"
                        return None, "FAILED_DECODE: Payload is not a valid image format"
                    elif resp.status_code in (404, 410):
                        return None, f"FAILED_DOWNLOAD: HTTP {resp.status_code} (Not Found)"
                    else:
                        last_err = f"HTTP {resp.status_code}"
                except requests.RequestException as e:
                    last_err = str(e)
                except Exception as e:
                    last_err = str(e)

                if attempt < self.max_retries:
                    sleep_sec = self.backoff_factor * (2 ** (attempt - 1))
                    time.sleep(sleep_sec)

            return None, f"FAILED_DOWNLOAD: Exhausted {self.max_retries} retries ({last_err})"

        return None, f"FAILED_INVALID_SOURCE: '{url_or_path}' is not a valid local path or HTTP URL"

    def verify_candidate(
        self,
        query_embedding: np.ndarray,
        candidate: SearchCandidate,
        threshold: Optional[float] = None
    ) -> CandidateVerificationResult:
        """
        Download, quality-check, and mathematically re-verify a single search candidate.
        Includes full audit trail for multi-face candidate images and records candidateFaceHash.
        """
        thresh = threshold if threshold is not None else self.similarity_threshold

        # 1. Download or load candidate image with retry & backoff
        target_src = candidate.image_url or candidate.page_url
        img, fetch_status = self._download_image(target_src)

        if img is None:
            return CandidateVerificationResult(
                candidate=candidate,
                face_detected=False,
                detection_confidence=0.0,
                cosine_similarity=0.0,
                cosine_distance=1.0,
                euclidean_distance=2.0,
                is_verified=False,
                status_reason=fetch_status,
                match_confidence_bp=0,
                candidate_embedding=None,
                candidate_face_hash=None,
                quality_passed=False,
                quality_score=0.0,
                multi_face_audit=[]
            )

        # 2. Quality & blur pre-check
        quality_ok, quality_score, quality_reason = self.evaluate_image_quality(img)
        if not quality_ok:
            return CandidateVerificationResult(
                candidate=candidate,
                face_detected=False,
                detection_confidence=0.0,
                cosine_similarity=0.0,
                cosine_distance=1.0,
                euclidean_distance=2.0,
                is_verified=False,
                status_reason=quality_reason,
                match_confidence_bp=0,
                candidate_embedding=None,
                candidate_face_hash=None,
                quality_passed=False,
                quality_score=quality_score,
                multi_face_audit=[]
            )

        # 3. Detect and extract face features from candidate image
        detected_faces = self.encoder.detect_and_encode(img)

        if not detected_faces:
            return CandidateVerificationResult(
                candidate=candidate,
                face_detected=False,
                detection_confidence=0.0,
                cosine_similarity=0.0,
                cosine_distance=1.0,
                euclidean_distance=2.0,
                is_verified=False,
                status_reason="NO_FACE_DETECTED: Candidate image contains no detectable human face",
                match_confidence_bp=0,
                candidate_embedding=None,
                candidate_face_hash=None,
                quality_passed=True,
                quality_score=quality_score,
                multi_face_audit=[]
            )

        # 4. Multi-face evaluation: inspect every face detected in candidate image
        multi_face_audit: List[Dict[str, Any]] = []
        best_cand_face = None
        best_sim = -1.0
        best_dist = 2.0
        best_l2 = 2.0

        for idx, face in enumerate(detected_faces, 1):
            sim = self.encoder.compute_cosine_similarity(query_embedding, face.embedding)
            dist = self.encoder.compute_cosine_distance(query_embedding, face.embedding)
            l2 = self.encoder.compute_euclidean_distance(query_embedding, face.embedding)

            audit_entry = {
                "face_index": idx,
                "bbox": face.bbox,
                "confidence": face.confidence,
                "cosine_similarity": sim,
                "face_hash": face.face_hash,
                "is_selected": False
            }
            multi_face_audit.append(audit_entry)

            if sim > best_sim:
                best_sim = sim
                best_dist = dist
                best_l2 = l2
                best_cand_face = face

        # Mark selected face in audit trail
        for entry in multi_face_audit:
            if entry["face_hash"] == best_cand_face.face_hash:
                entry["is_selected"] = True

        # If multiple faces were found, log the audit trail
        if len(detected_faces) > 1:
            print(f"      [Multi-Face Audit] Candidate contains {len(detected_faces)} detected faces:")
            for entry in multi_face_audit:
                sel_tag = "[SELECTED CANDIDATE]" if entry["is_selected"] else "[REJECTED OTHER FACE]"
                print(f"        - Face #{entry['face_index']}: Conf={entry['confidence']*100:.1f}%, Sim={entry['cosine_similarity']:.4f} -> {sel_tag}")

        # 5. Strict thresholding test
        is_verified = best_sim >= thresh
        # Basis points: e.g. 0.9407 -> 9407 (94.07%)
        confidence_bp = max(0, min(10000, int(best_sim * 10000)))

        if is_verified:
            reason = f"VERIFIED_MATCH: Cosine Similarity {best_sim:.4f} >= threshold {thresh:.2f}"
        else:
            reason = f"REJECTED: Cosine Similarity {best_sim:.4f} < threshold {thresh:.2f} (Visual False Positive)"

        return CandidateVerificationResult(
            candidate=candidate,
            face_detected=True,
            detection_confidence=best_cand_face.confidence,
            cosine_similarity=best_sim,
            cosine_distance=best_dist,
            euclidean_distance=best_l2,
            is_verified=is_verified,
            status_reason=reason,
            match_confidence_bp=confidence_bp,
            candidate_embedding=best_cand_face.embedding,
            candidate_face_hash=best_cand_face.face_hash,
            quality_passed=True,
            quality_score=quality_score,
            multi_face_audit=multi_face_audit
        )

    def re_verify_all(
        self,
        query_face: FaceDetectionResult,
        candidates: List[SearchCandidate],
        threshold: Optional[float] = None,
        max_candidates: int = 20
    ) -> VerificationReport:
        """
        Execute full biometric verification across candidate leads with per-run candidate cap.
        """
        thresh = threshold if threshold is not None else self.similarity_threshold
        verified: List[CandidateVerificationResult] = []
        rejected: List[CandidateVerificationResult] = []

        total_discovered = len(candidates)
        candidates_to_process = candidates
        if total_discovered > max_candidates:
            print(f"  [Re-Verify] Cap Enforced: Processing first {max_candidates} leads (out of {total_discovered} discovered).")
            candidates_to_process = candidates[:max_candidates]

        for cand in candidates_to_process:
            res = self.verify_candidate(query_face.embedding, cand, threshold=thresh)
            if res.is_verified:
                verified.append(res)
            else:
                rejected.append(res)

        # Sort verified matches by highest similarity
        verified.sort(key=lambda r: r.cosine_similarity, reverse=True)
        best_match = verified[0] if verified else None

        return VerificationReport(
            query_face=query_face,
            total_candidates_examined=len(candidates_to_process),
            verified_matches=verified,
            rejected_candidates=rejected,
            best_match=best_match,
            has_verified_match=bool(best_match is not None),
            threshold_used=thresh
        )
