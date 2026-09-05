"""
Core Re-Verification Engine (USP - Mandatory Component).
Every candidate returned by the search API is treated strictly as an unverified visual lead.
This module downloads each candidate, executes face detection and encoding using the
exact same biometric model, and calculates vector embedding distance.
Only candidates satisfying the mathematical similarity threshold are permitted on-chain.
"""

import os
import io
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Union
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
        request_timeout: int = 15
    ):
        self.encoder = encoder
        self.similarity_threshold = similarity_threshold
        self.request_timeout = request_timeout

    def _download_image(self, url_or_path: str) -> Optional[np.ndarray]:
        """Fetch image from URL or read local file path."""
        # Check if local path exists first
        if os.path.exists(url_or_path):
            img = cv2.imread(url_or_path)
            if img is not None:
                return img

        # Otherwise attempt HTTP fetch
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            try:
                resp = requests.get(url_or_path, headers=headers, timeout=self.request_timeout)
                if resp.status_code == 200:
                    arr = np.frombuffer(resp.content, dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    return img
            except Exception as e:
                print(f"  [Re-Verify] Warning: Could not download candidate image from {url_or_path}: {e}")
                return None

        return None

    def verify_candidate(
        self,
        query_embedding: np.ndarray,
        candidate: SearchCandidate,
        threshold: Optional[float] = None
    ) -> CandidateVerificationResult:
        """
        Download and mathematically re-verify a single search candidate.
        """
        thresh = threshold if threshold is not None else self.similarity_threshold

        # 1. Download or load candidate image
        target_src = candidate.image_url or candidate.page_url
        img = self._download_image(target_src)

        if img is None:
            return CandidateVerificationResult(
                candidate=candidate,
                face_detected=False,
                detection_confidence=0.0,
                cosine_similarity=0.0,
                cosine_distance=1.0,
                euclidean_distance=2.0,
                is_verified=False,
                status_reason="FAILED_DOWNLOAD: Candidate image could not be retrieved",
                match_confidence_bp=0,
                candidate_embedding=None
            )

        # 2. Detect and extract face features from candidate image
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
                status_reason="NO_FACE_DETECTED: Candidate image contains no detectable face",
                match_confidence_bp=0,
                candidate_embedding=None
            )

        # 3. If multiple faces exist in candidate image, select the closest to query face
        best_cand_face = None
        best_sim = -1.0
        best_dist = 2.0
        best_l2 = 2.0

        for face in detected_faces:
            sim = self.encoder.compute_cosine_similarity(query_embedding, face.embedding)
            dist = self.encoder.compute_cosine_distance(query_embedding, face.embedding)
            l2 = self.encoder.compute_euclidean_distance(query_embedding, face.embedding)

            if sim > best_sim:
                best_sim = sim
                best_dist = dist
                best_l2 = l2
                best_cand_face = face

        # 4. Strict thresholding test
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
            candidate_embedding=best_cand_face.embedding
        )

    def re_verify_all(
        self,
        query_face: FaceDetectionResult,
        candidates: List[SearchCandidate],
        threshold: Optional[float] = None
    ) -> VerificationReport:
        """
        Execute full biometric verification across all search candidates.
        """
        thresh = threshold if threshold is not None else self.similarity_threshold
        verified: List[CandidateVerificationResult] = []
        rejected: List[CandidateVerificationResult] = []

        for cand in candidates:
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
            total_candidates_examined=len(candidates),
            verified_matches=verified,
            rejected_candidates=rejected,
            best_match=best_match,
            has_verified_match=bool(best_match is not None),
            threshold_used=thresh
        )
