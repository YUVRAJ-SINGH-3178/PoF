"""
Unit tests for ReVerificationEngine module (USP verification).
Tests that candidates are independently verified and rejected false positives are blocked.
"""

import pytest
from pathlib import Path
from core.face_encoder import FaceEncoder
from core.reverse_search import SearchCandidate
from core.verifier import ReVerificationEngine

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_images"
QUERY_IMAGE = SAMPLE_DIR / "query_face.jpg"
MATCH_IMAGE = SAMPLE_DIR / "matching_candidate.jpg"
DIFF_IMAGE = SAMPLE_DIR / "different_person.jpg"


@pytest.fixture
def encoder():
    return FaceEncoder()


@pytest.fixture
def verifier(encoder):
    return ReVerificationEngine(encoder=encoder, similarity_threshold=0.60)


def test_positive_candidate_verification(encoder, verifier):
    query_face = encoder.detect_and_encode(QUERY_IMAGE)[0]
    candidate = SearchCandidate(
        source_platform="x.com",
        page_url="https://x.com/verified_user/status/100",
        image_url=str(MATCH_IMAGE),
        page_title="Keynote Announcement",
        match_type="page_match"
    )

    res = verifier.verify_candidate(query_face.embedding, candidate)
    assert res.is_verified is True
    assert res.face_detected is True
    assert res.cosine_similarity >= 0.85
    assert res.match_confidence_bp >= 8500
    assert "VERIFIED_MATCH" in res.status_reason


def test_negative_candidate_rejection(encoder, verifier):
    query_face = encoder.detect_and_encode(QUERY_IMAGE)[0]
    candidate = SearchCandidate(
        source_platform="linkedin.com",
        page_url="https://linkedin.com/in/unrelated",
        image_url=str(DIFF_IMAGE),
        page_title="Unrelated Profile",
        match_type="page_match"
    )

    res = verifier.verify_candidate(query_face.embedding, candidate)
    assert res.is_verified is False
    assert res.face_detected is True
    assert res.cosine_similarity < 0.40
    assert "REJECTED" in res.status_reason


def test_re_verify_all_mixed_candidates(encoder, verifier):
    query_face = encoder.detect_and_encode(QUERY_IMAGE)[0]
    candidates = [
        SearchCandidate("x.com", "https://x.com/post/1", str(MATCH_IMAGE), "Post 1", "match"),
        SearchCandidate("linkedin.com", "https://linkedin.com/in/p2", str(DIFF_IMAGE), "Post 2", "match")
    ]

    report = verifier.re_verify_all(query_face, candidates, threshold=0.60)
    assert report.total_candidates_examined == 2
    assert len(report.verified_matches) == 1
    assert len(report.rejected_candidates) == 1
    assert report.has_verified_match is True
    assert report.best_match.candidate.page_url == "https://x.com/post/1"


def test_re_verify_all_zero_matches(encoder, verifier):
    query_face = encoder.detect_and_encode(QUERY_IMAGE)[0]
    candidates = [
        SearchCandidate("linkedin.com", "https://linkedin.com/in/p2", str(DIFF_IMAGE), "Post 2", "match")
    ]

    report = verifier.re_verify_all(query_face, candidates, threshold=0.60)
    assert report.has_verified_match is False
    assert len(report.verified_matches) == 0
    assert len(report.rejected_candidates) == 1
    assert report.best_match is None
