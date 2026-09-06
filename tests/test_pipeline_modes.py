"""
Unit tests for pipeline runtime modes, security gates, and cryptographic report signing.
Tests:
1. Live mode credential enforcement (silent fallback elimination).
2. Consent gate enforcement (GDPR/BIPA privacy control).
3. Demo mode execution with simulated artifacts and non-explorer URLs.
4. Cryptographic report generation and EIP-191 signature recovery.
"""

import json
from pathlib import Path
from pipeline import run_pipeline, check_live_credentials

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT_DIR / "sample_images"
QUERY_IMAGE = SAMPLE_DIR / "query_face.jpg"


def test_live_mode_credential_validation():
    # In clean or test environment without live credentials, check_live_credentials identifies missing keys
    missing = check_live_credentials()
    assert len(missing) > 0, "Should detect missing live credentials in unconfigured environment"

    # Running pipeline in live mode without credentials must fail immediately
    success = run_pipeline(
        image_path=str(QUERY_IMAGE),
        demo_mode=False,
        consent_confirmed=True
    )
    assert success is False, "Live mode pipeline must abort when credentials are not configured"


def test_consent_gate_enforcement():
    # Running in demo mode without explicit consent must abort at the consent gate
    success = run_pipeline(
        image_path=str(QUERY_IMAGE),
        demo_mode=True,
        consent_confirmed=False
    )
    assert success is False, "Pipeline must abort if --consent-confirmed is not provided"


def test_demo_mode_execution_success(tmp_path):
    report_file = tmp_path / "test_report.json"
    success = run_pipeline(
        image_path=str(QUERY_IMAGE),
        demo_mode=True,
        consent_confirmed=True,
        save_report_path=str(report_file)
    )
    assert success is True, "Pipeline in demo mode with consent must succeed"
    assert report_file.exists(), "Saved report file must be written"

    with open(report_file, "r") as f:
        data = json.load(f)

    # Check that report structure contains manifest, attestation, and summary
    assert "summary" in data
    assert "manifest" in data
    assert "attestation" in data

    summary = data["summary"]
    assert summary["consent_confirmed"] is True
    assert summary["is_demo_mode"] is True
    assert summary["query_face_hash"].startswith("0x")
    assert summary["candidate_face_hash"].startswith("0x")

    attestation = data["attestation"]
    assert attestation["verified_signer"] is True
    assert attestation["signer_address"].startswith("0x")
    assert len(attestation["signature"]) > 50

    # Ensure demo mode does NOT output real polygonscan URLs in report
    assert "polygonscan.com" not in summary.get("explorer_url", "")
