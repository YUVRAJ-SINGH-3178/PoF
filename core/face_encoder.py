"""
Face Detection and Biometric Embedding Module.
Implements deep learning face detection (YuNet) and feature extraction (SFace / InsightFace),
producing normalized embeddings, deterministic face hashes, and biometric distance metrics.
"""

import os
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union
import numpy as np
import cv2

# Project paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_YUNET_PATH = ROOT_DIR / "models" / "yunet.onnx"
DEFAULT_SFACE_PATH = ROOT_DIR / "models" / "sface.onnx"


@dataclass
class FaceDetectionResult:
    bbox: List[int]                     # [x, y, width, height]
    confidence: float                   # Detection confidence [0.0 - 1.0]
    embedding: np.ndarray               # Normalized 128-d or 512-d embedding vector
    face_hash: str                      # Deterministic 0x-prefixed SHA-256 hash (bytes32 hex)
    detection_method: str               # Model identifier (e.g., 'YuNet+SFace-128d')
    landmarks: Optional[List[List[float]]] = None


class FaceEncoder:
    """
    Production-grade face detector and feature encoder.
    Provides face alignment, feature extraction, normalization, and distance metrics.
    """

    def __init__(
        self,
        detector_path: Optional[Union[str, Path]] = None,
        recognizer_path: Optional[Union[str, Path]] = None,
        score_threshold: float = 0.80,
        nms_threshold: float = 0.30,
        top_k: int = 5000,
    ):
        self.detector_path = Path(detector_path or DEFAULT_YUNET_PATH)
        self.recognizer_path = Path(recognizer_path or DEFAULT_SFACE_PATH)
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        self.top_k = top_k
        self.method_name = "YuNet+SFace-128d"

        if not self.detector_path.exists():
            raise FileNotFoundError(f"Face detector model not found at {self.detector_path}")
        if not self.recognizer_path.exists():
            raise FileNotFoundError(f"Face recognizer model not found at {self.recognizer_path}")

        # Initialize detector with default input size (will be updated dynamically per image)
        self.detector = cv2.FaceDetectorYN.create(
            str(self.detector_path),
            "",
            (320, 320),
            score_threshold=self.score_threshold,
            nms_threshold=self.nms_threshold,
            top_k=self.top_k
        )
        self.recognizer = cv2.FaceRecognizerSF.create(str(self.recognizer_path), "")

    def _load_image(self, image_input: Union[str, Path, bytes, np.ndarray]) -> np.ndarray:
        """Helper to convert various image input types to BGR numpy array."""
        if isinstance(image_input, np.ndarray):
            return image_input
        elif isinstance(image_input, (str, Path)):
            path_str = str(image_input)
            if not os.path.exists(path_str):
                raise FileNotFoundError(f"Input image not found: {path_str}")
            img = cv2.imread(path_str)
            if img is None:
                raise ValueError(f"Could not decode image at {path_str}")
            return img
        elif isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode image from byte buffer")
            return img
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

    def detect_and_encode(
        self,
        image_input: Union[str, Path, bytes, np.ndarray],
        require_single_face: bool = False
    ) -> List[FaceDetectionResult]:
        """
        Detect faces in image and extract normalized embeddings.
        Returns a list of FaceDetectionResult objects sorted by detection confidence (descending).
        """
        img = self._load_image(image_input)
        h, w = img.shape[:2]

        # Update detector input size dynamically for this image
        self.detector.setInputSize((w, h))

        # Detect faces: returns (faces, ...)
        _, faces = self.detector.detect(img)

        if faces is None or len(faces) == 0:
            return []

        results = []
        for face in faces:
            confidence = float(face[14])
            bbox = [int(face[0]), int(face[1]), int(face[2]), int(face[3])]

            # Extract 5 facial landmark points
            landmarks = [
                [float(face[4]), float(face[5])],   # Right eye
                [float(face[6]), float(face[7])],   # Left eye
                [float(face[8]), float(face[9])],   # Nose tip
                [float(face[10]), float(face[11])], # Right mouth corner
                [float(face[12]), float(face[13])], # Left mouth corner
            ]

            # Align and crop face using recognizer module
            aligned_face = self.recognizer.alignCrop(img, face)

            # Extract feature embedding (128-d for SFace)
            feature = self.recognizer.feature(aligned_face)
            embedding = feature.flatten().astype(np.float32)

            # Strictly normalize embedding to unit length (L2 norm = 1.0)
            norm = np.linalg.norm(embedding)
            if norm > 1e-6:
                embedding = embedding / norm

            # Generate deterministic SHA-256 hash of the normalized embedding vector (bytes32 hex)
            emb_bytes = embedding.tobytes()
            face_hash = "0x" + hashlib.sha256(emb_bytes).hexdigest()

            results.append(FaceDetectionResult(
                bbox=bbox,
                confidence=confidence,
                embedding=embedding,
                face_hash=face_hash,
                detection_method=self.method_name,
                landmarks=landmarks
            ))

        # Sort by confidence descending
        results.sort(key=lambda r: r.confidence, reverse=True)

        if require_single_face and len(results) > 1:
            # Keep only highest confidence primary face
            results = [results[0]]

        return results

    @staticmethod
    def compute_cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Compute cosine similarity between two unit-normalized vectors:
        Cosine Similarity = dot(v1, v2) (since norm=1.0)
        Range: [-1.0, 1.0]
        """
        v1 = emb1.flatten()
        v2 = emb2.flatten()
        dot_product = float(np.dot(v1, v2))
        return max(-1.0, min(1.0, dot_product))

    @staticmethod
    def compute_cosine_distance(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Compute cosine distance: 1.0 - Cosine Similarity
        Range: [0.0, 2.0] (0.0 = identical, >0.5 = different identities)
        """
        similarity = FaceEncoder.compute_cosine_similarity(emb1, emb2)
        return float(1.0 - similarity)

    @staticmethod
    def compute_euclidean_distance(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute Euclidean (L2) distance between embeddings."""
        v1 = emb1.flatten()
        v2 = emb2.flatten()
        return float(np.linalg.norm(v1 - v2))

    def compare_embeddings(
        self,
        emb1: np.ndarray,
        emb2: np.ndarray,
        threshold: float = 0.60
    ) -> Tuple[bool, float, float]:
        """
        Compare two face embeddings against verification threshold.
        Returns:
            is_match (bool): True if cosine similarity >= threshold
            similarity (float): Cosine similarity [0.0 - 1.0]
            distance (float): Cosine distance (1 - similarity)
        """
        similarity = self.compute_cosine_similarity(emb1, emb2)
        distance = self.compute_cosine_distance(emb1, emb2)
        is_match = similarity >= threshold
        return is_match, similarity, distance
