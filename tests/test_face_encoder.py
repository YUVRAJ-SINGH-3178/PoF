"""
Unit tests for FaceEncoder module.
Tests detection, normalization, deterministic hash generation, and distance metrics.
"""

import numpy as np
import pytest
from pathlib import Path
from core.face_encoder import FaceEncoder

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_images"
QUERY_IMAGE = SAMPLE_DIR / "query_face.jpg"
MATCH_IMAGE = SAMPLE_DIR / "matching_candidate.jpg"
DIFF_IMAGE = SAMPLE_DIR / "different_person.jpg"


@pytest.fixture
def encoder():
    return FaceEncoder()


def test_face_detection_and_shape(encoder):
    results = encoder.detect_and_encode(QUERY_IMAGE)
    assert len(results) >= 1, "Should detect at least 1 face"
    face = results[0]
    assert face.confidence > 0.80, "Detection confidence should exceed 80%"
    assert len(face.embedding) == 128, "SFace embedding dimension must be 128-d"
    assert len(face.bbox) == 4, "Bounding box must be [x, y, w, h]"


def test_embedding_normalization(encoder):
    results = encoder.detect_and_encode(QUERY_IMAGE)
    face = results[0]
    norm = np.linalg.norm(face.embedding)
    assert np.isclose(norm, 1.0, atol=1e-5), f"Embedding must be unit normalized (got norm {norm})"


def test_deterministic_face_hash(encoder):
    results1 = encoder.detect_and_encode(QUERY_IMAGE)
    results2 = encoder.detect_and_encode(QUERY_IMAGE)
    hash1 = results1[0].face_hash
    hash2 = results2[0].face_hash

    assert hash1.startswith("0x"), "Face hash must start with 0x"
    assert len(hash1) == 66, "Face hash must be a 32-byte hex string (64 hex chars + 0x)"
    assert hash1 == hash2, "Identical face must produce exact same face hash"


def test_same_person_high_similarity(encoder):
    results_query = encoder.detect_and_encode(QUERY_IMAGE)
    results_match = encoder.detect_and_encode(MATCH_IMAGE)

    is_match, similarity, distance = encoder.compare_embeddings(
        results_query[0].embedding,
        results_match[0].embedding,
        threshold=0.60
    )

    assert is_match is True, "Same person must match with threshold 0.60"
    assert similarity >= 0.85, f"Expected high similarity for same person (got {similarity})"
    assert distance <= 0.15, f"Expected low distance for same person (got {distance})"


def test_different_person_low_similarity(encoder):
    results_query = encoder.detect_and_encode(QUERY_IMAGE)
    results_diff = encoder.detect_and_encode(DIFF_IMAGE)

    is_match, similarity, distance = encoder.compare_embeddings(
        results_query[0].embedding,
        results_diff[0].embedding,
        threshold=0.60
    )

    assert is_match is False, "Different individuals must NOT match with threshold 0.60"
    assert similarity < 0.40, f"Expected low similarity for different person (got {similarity})"
    assert distance > 0.60, f"Expected high distance for different person (got {distance})"
