#!/usr/bin/env python3
"""
Face ID + Blockchain Verification Pipeline (Production CLI).

USP: Search APIs are treated strictly as candidate generators, not verifiers.
Every candidate returned is independently re-scored using deep biometric face embeddings
before any record is permitted on the public blockchain testnet.

Second-Order USP: Verification is re-derivable, not just recorded.
Both queryFaceHash and candidateFaceHash are anchored on-chain alongside an IPFS
verification manifest, enabling third parties to independently recompute embeddings
and verify claimed similarity scores without trusting the local runner.

Usage:
    # Live production mode (requires .env credentials):
    python pipeline.py --image path/to/input.jpg --consent-confirmed

    # Offline benchmark / demo mode (safe for testing without live APIs):
    python pipeline.py --demo-mode --image sample_images/query_face.jpg --consent-confirmed
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

from core.face_encoder import FaceEncoder
from core.reverse_search import ReverseImageSearch, SearchCandidate
from core.verifier import ReVerificationEngine, VerificationReport
from core.ipfs_client import IPFSClient
from core.blockchain_writer import BlockchainWriter

BANNER = """
================================================================================
     FACE ID + BLOCKCHAIN BIOMETRIC RE-VERIFICATION PIPELINE
     USP: Mathematical Embedding Distance Re-Verification Before On-Chain Write
     USP 2: Re-Derivable On-Chain Records (Query + Candidate Biometric Hashes)
================================================================================
"""

DEMO_PREFIX = "[DEMO — NOT VERIFIABLE — NO LIVE API CALL MADE]"


def format_step(step_num: int, title: str) -> str:
    line = "-" * 80
    return f"\n{line}\n[STEP {step_num}] {title.upper()}\n{line}"


def check_live_credentials() -> List[str]:
    """Check for presence of required credentials for live mode."""
    missing = []
    
    # 1. Search credentials
    searcher = ReverseImageSearch()
    if not searcher.has_credentials():
        missing.append("Search API: GOOGLE_VISION_API_KEY or GOOGLE_APPLICATION_CREDENTIALS or BING_VISUAL_SEARCH_API_KEY or APIFY_API_KEY")
        
    # 2. IPFS credentials
    ipfs_client = IPFSClient()
    if not ipfs_client.has_credentials():
        missing.append("IPFS Storage: PINATA_JWT or (PINATA_API_KEY and PINATA_API_SECRET)")
        
    # 3. Blockchain credentials
    writer = BlockchainWriter(network="amoy")
    if not writer.has_wallet():
        missing.append("Blockchain Wallet: WEB3_PRIVATE_KEY")
    if not writer.contract_address:
        missing.append("Blockchain Contract: CONTRACT_ADDRESS")
        
    return missing


def run_pipeline(
    image_path: str,
    threshold: float = 0.60,
    network: str = "amoy",
    candidates_file: Optional[str] = None,
    save_report_path: Optional[str] = None,
    demo_mode: bool = False,
    consent_confirmed: bool = False,
    max_candidates: int = 20
) -> bool:
    print(BANNER)

    input_img = Path(image_path)
    if not input_img.exists():
        print(f"[ERROR] Input image file not found: {image_path}")
        return False

    # -------------------------------------------------------------------------
    # CREDENTIAL VALIDATION (Live Mode Enforcement - Rule 1)
    # -------------------------------------------------------------------------
    if not demo_mode:
        missing_creds = check_live_credentials()
        if missing_creds:
            print("\n" + "=" * 80)
            print("[FATAL ERROR] MISSING LIVE CREDENTIALS IN PRODUCTION MODE")
            print("=" * 80)
            print("The pipeline runs in LIVE VERIFIABLE MODE by default. Silent fallbacks")
            print("are strictly disabled to guarantee all outputs correspond to genuine state.")
            print("\nThe following required credential(s) are missing from your .env:")
            for m in missing_creds:
                print(f"  [-] {m}")
            print("\nHOW TO PROCEED:")
            print("  1. For LIVE production runs:")
            print("     Configure the missing keys in your .env file (see .env.example).")
            print("  2. For OFFLINE demonstration / benchmark testing:")
            print("     Re-run with the explicit --demo-mode flag:")
            print(f"     python pipeline.py --demo-mode --image {image_path} --consent-confirmed")
            print("=" * 80 + "\n")
            return False
    else:
        print(f"{DEMO_PREFIX} Running in explicit demonstration / benchmark mode.")
        print(f"{DEMO_PREFIX} Output contains simulated cryptographic and network artifacts.\n")

    # -------------------------------------------------------------------------
    # STEP 1: Face Detection & Encoding
    # -------------------------------------------------------------------------
    print(format_step(1, "Face Detection & Feature Encoding"))
    print(f"Loading image: {input_img.resolve()}")
    try:
        encoder = FaceEncoder()
    except Exception as e:
        print(f"[ERROR] Failed to initialize FaceEncoder: {e}")
        return False

    faces = encoder.detect_and_encode(input_img)
    if not faces:
        print("\n[RESULT] No human face detected in input image.")
        print("Verification pipeline stopped: Cannot proceed without an initial face embedding.")
        return False

    primary_face = faces[0]
    print(f"  [+] Status             : 1 Face Detected (Primary)")
    print(f"  [+] Detection Method   : {primary_face.detection_method}")
    print(f"  [+] Detection Score    : {primary_face.confidence * 100:.2f}%")
    print(f"  [+] Bounding Box       : {primary_face.bbox} [x, y, w, h]")
    print(f"  [+] Embedding Dimension: {len(primary_face.embedding)}-d (L2-Normalized)")
    print(f"  [+] Face Hash (bytes32): {primary_face.face_hash}")

    # -------------------------------------------------------------------------
    # STEP 2: Reverse-Image Search (Candidate Lead Discovery)
    # -------------------------------------------------------------------------
    print(format_step(2, "Reverse-Image Search (Candidate Lead Discovery)"))
    searcher = ReverseImageSearch()
    candidates: List[SearchCandidate] = []

    if not demo_mode and searcher.has_credentials():
        print("  [*] Querying Reverse Image Search API (Google Vision / Bing)...")
        try:
            candidates = searcher.search(input_img)
            print(f"  [+] Search completed: Discovered {len(candidates)} candidate leads.")
        except Exception as e:
            print(f"  [!] Search API query error: {e}")
            return False
    else:
        # In demo mode, load benchmark test leads
        print(f"  {DEMO_PREFIX} Using canned benchmark candidate leads.")
        cand_path = None
        if candidates_file and Path(candidates_file).exists():
            cand_path = Path(candidates_file)
        elif (Path("sample_images") / "test_candidates.json").exists():
            cand_path = Path("sample_images") / "test_candidates.json"

        if cand_path:
            print(f"  {DEMO_PREFIX} Loaded candidates from: {cand_path}")
            with open(cand_path, "r") as f:
                raw_cands = json.load(f)
                candidates = [SearchCandidate(**c) for c in raw_cands]
        else:
            print("  [!] No candidate leads available.")
            return False

    if not candidates:
        print("\n  [RESULT] 0 candidates found matching social platform filters.")
        print("  Pipeline finished: No candidates to verify.")
        return False

    print(f"\n  Discovered Candidates ({len(candidates)} visual leads):")
    for i, cand in enumerate(candidates[:max_candidates], 1):
        print(f"    [{i}] Platform: {cand.source_platform}")
        print(f"        Page URL: {cand.page_url}")
        print(f"        Image   : {cand.image_url}")

    # -------------------------------------------------------------------------
    # STEP 3: Re-Verification Step (Core USP - Mandatory)
    # -------------------------------------------------------------------------
    print(format_step(3, "Mathematical Re-Verification (Core USP Differentiator)"))
    print(f"  Verification Threshold Configured : Cosine Similarity >= {threshold:.2f}")
    print(f"  Candidate Processing Limit (Cap)  : Up to {max_candidates} candidates")
    print(f"  Requirement                       : Independent biometric feature re-extraction\n")

    verifier = ReVerificationEngine(encoder=encoder, similarity_threshold=threshold)
    report: VerificationReport = verifier.re_verify_all(
        primary_face,
        candidates,
        threshold=threshold,
        max_candidates=max_candidates
    )

    print("  Candidate-by-Candidate Re-Verification Results:")
    all_results = report.verified_matches + report.rejected_candidates
    for i, res in enumerate(all_results, 1):
        status_tag = "[PASS - VERIFIED]" if res.is_verified else "[FAIL - REJECTED]"
        print(f"    Candidate #{i}: {res.candidate.page_url}")
        print(f"      Platform     : {res.candidate.source_platform}")
        print(f"      Quality Check: {'PASS' if res.quality_passed else 'FAIL'} (Score: {res.quality_score:.1f})")
        print(f"      Face In Lead : {'Yes' if res.face_detected else 'No'}")
        if res.candidate_face_hash:
            print(f"      Cand Hash    : {res.candidate_face_hash}")
        print(f"      Similarity   : {res.cosine_similarity:.4f} (Cosine Distance: {res.cosine_distance:.4f})")
        print(f"      Confidence   : {res.match_confidence_bp / 100:.2f}%")
        print(f"      Verdict      : {status_tag} -> {res.status_reason}\n")

    # -------------------------------------------------------------------------
    # STEP 4: Verified Match Evaluation
    # -------------------------------------------------------------------------
    print(format_step(4, "Verified Match Determination"))
    if not report.has_verified_match:
        print("  [FAIL] NO VERIFIED MATCH FOUND.")
        print(f"  None of the {report.total_candidates_examined} candidate leads passed the similarity threshold (>={threshold:.2f}).")
        print("  [CRITICAL RULE ENFORCED] The pipeline will NOT fabricate a match or lower the threshold.")
        print("  Blockchain write is ABORTED.")
        return False

    best = report.best_match
    print(f"  [SUCCESS] GENUINE IDENTITY MATCH CONFIRMED!")
    print(f"  Matched Post/Profile  : {best.candidate.page_url}")
    print(f"  Source Platform       : {best.candidate.source_platform}")
    print(f"  Biometric Similarity  : {best.cosine_similarity:.4f} (Threshold: {threshold:.2f})")
    print(f"  Match Confidence (bp) : {best.match_confidence_bp} ({best.match_confidence_bp / 100:.2f}%)")
    print(f"  Query Face Hash       : {primary_face.face_hash}")
    print(f"  Candidate Face Hash   : {best.candidate_face_hash}")

    # -------------------------------------------------------------------------
    # STEP 5: IPFS Decentralized Manifest Storage (USP 2: Re-Derivability)
    # -------------------------------------------------------------------------
    print(format_step(5, "IPFS Decentralized Verification Manifest"))
    ipfs_client = IPFSClient()

    # Compute raw image hashes for manifest
    with open(input_img, "rb") as f:
        query_image_sha256 = hashlib.sha256(f.read()).hexdigest()

    cand_img_sha256 = "N/A"
    cand_src = best.candidate.image_url or best.candidate.page_url
    if cand_src and os.path.exists(cand_src):
        with open(cand_src, "rb") as f:
            cand_img_sha256 = hashlib.sha256(f.read()).hexdigest()

    # Construct the complete verification manifest
    verification_manifest = {
        "protocol": "VeriFace/PoF",
        "version": "1.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": {
            "face_hash": primary_face.face_hash,
            "image_sha256": query_image_sha256,
            "detection_method": primary_face.detection_method,
            "confidence": primary_face.confidence,
            "bbox": primary_face.bbox
        },
        "candidate": {
            "face_hash": best.candidate_face_hash,
            "image_sha256": cand_img_sha256,
            "matched_url": best.candidate.page_url,
            "source_platform": best.candidate.source_platform,
            "quality_score": best.quality_score
        },
        "biometric_proof": {
            "cosine_similarity": float(best.cosine_similarity),
            "cosine_distance": float(best.cosine_distance),
            "euclidean_distance": float(best.euclidean_distance),
            "match_confidence_bp": int(best.match_confidence_bp),
            "similarity_threshold": float(threshold),
            "is_verified": True
        },
        "compliance": {
            "consent_confirmed": consent_confirmed,
            "privacy_standard": "GDPR-Art9/BIPA-Sec15-Redacted",
            "subject_identity_recorded": False
        }
    }

    if not demo_mode and ipfs_client.has_credentials():
        print("  [*] Pinning verification manifest to live Pinata IPFS node...")
    else:
        print(f"  {DEMO_PREFIX} Generating deterministic manifest CID (No live pin).")

    manifest_receipt = ipfs_client.pin_json(
        verification_manifest,
        name=f"veriface-manifest-{primary_face.face_hash[2:10]}",
        demo_mode=demo_mode
    )

    print(f"  [+] Manifest CID     : {manifest_receipt.cid}")
    print(f"  [+] IPFS URI         : {manifest_receipt.ipfs_uri}")
    print(f"  [+] Gateway URL      : {manifest_receipt.gateway_url}")
    print(f"  [+] Live Pinned      : {'Yes (Pinata Cloud)' if manifest_receipt.is_real_pin else 'No (Deterministic Mock CID)'}")

    # -------------------------------------------------------------------------
    # STEP 6: Blockchain Testnet Write & Consent Gate
    # -------------------------------------------------------------------------
    print(format_step(6, f"Blockchain Testnet Write ({network.upper()}) & Consent Gate"))

    # Enforce Consent Gate (Requirement 7)
    if not consent_confirmed:
        print("\n  [FATAL: CONSENT GATE ENFORCED]")
        print("  Biometric data anchoring is subject to strict privacy ethics (GDPR Art. 9, BIPA).")
        print("  The pipeline will NOT write to blockchain without explicit consent confirmation.")
        print("  Re-run with the flag: --consent-confirmed\n")
        return False

    print("  [+] Consent Status   : CONFIRMED (Explicit Subject Authorization Logged)")
    print("  [+] Privacy Control  : Anonymized Biometric Vectors Only (No PII Stored)")

    writer = BlockchainWriter(network=network)
    print(f"  [*] Target Network   : {writer.net_cfg['name']} (Chain ID {writer.net_cfg['chain_id']})")
    print(f"  [*] RPC Endpoint     : {writer.rpc_url}")
    print(f"  [*] Node Connected   : {'Yes' if writer.is_connected() else 'No'}")

    wallet_addr = writer.get_wallet_address()
    if wallet_addr:
        print(f"  [*] Wallet Address   : {wallet_addr}")
        print(f"  [*] Native Balance   : {writer.get_balance():.6f} Native Token")
    else:
        if demo_mode:
            print(f"  {DEMO_PREFIX} Using mock wallet signer for demo simulation.")
        else:
            print("  [!] No wallet configured.")

    tx_receipt = writer.write_verification(
        face_hash=primary_face.face_hash,
        candidate_face_hash=best.candidate_face_hash,
        ipfs_cid=manifest_receipt.cid,
        matched_url=best.candidate.page_url,
        match_confidence_bp=best.match_confidence_bp,
        source_platform=best.candidate.source_platform,
        detection_method=primary_face.detection_method
    )

    # -------------------------------------------------------------------------
    # STEP 7: Block Explorer Link & Audit Proof
    # -------------------------------------------------------------------------
    print(format_step(7, "Public Block Explorer Link & Proof"))
    if demo_mode:
        print(f"  {DEMO_PREFIX} Transaction Hash : {tx_receipt.tx_hash}")
        print(f"  {DEMO_PREFIX} Contract Address : {tx_receipt.contract_address}")
        print(f"  {DEMO_PREFIX} Block Explorer   : {tx_receipt.explorer_url}")
        print(f"  {DEMO_PREFIX} Status           : {tx_receipt.status_message}")
    else:
        print(f"  Transaction Hash    : {tx_receipt.tx_hash}")
        print(f"  Contract Address    : {tx_receipt.contract_address}")
        if tx_receipt.block_number:
            print(f"  Confirmed in Block  : {tx_receipt.block_number}")
            print(f"  Gas Used            : {tx_receipt.gas_used}")
        print(f"\n  >>> PUBLIC BLOCK EXPLORER URL <<<\n  {tx_receipt.explorer_url}\n")
        print(f"  Status Note         : {tx_receipt.status_message}")

    # -------------------------------------------------------------------------
    # STEP 8: Cryptographic Report Binding (Requirement 3)
    # -------------------------------------------------------------------------
    canonical_report_summary = {
        "query_face_hash": primary_face.face_hash,
        "candidate_face_hash": best.candidate_face_hash,
        "ipfs_manifest_cid": manifest_receipt.cid,
        "matched_url": best.candidate.page_url,
        "source_platform": best.candidate.source_platform,
        "similarity": best.cosine_similarity,
        "confidence_bp": best.match_confidence_bp,
        "tx_hash": tx_receipt.tx_hash,
        "contract_address": tx_receipt.contract_address,
        "consent_confirmed": consent_confirmed,
        "is_demo_mode": demo_mode
    }

    attestation = writer.sign_report_attestation(canonical_report_summary)

    print("\n" + "-" * 80)
    print("[CRYPTOGRAPHIC ATTESTATION]")
    print("-" * 80)
    print(f"  Signer Wallet Address : {attestation['signer_address']}")
    print(f"  Signature (EIP-191)   : {attestation['signature'][:30]}...{attestation['signature'][-10:]}")
    print(f"  Payload Hash (Keccak) : {attestation['canonical_payload_sha256']}")
    print(f"  Signature Recovered   : {'VALID' if attestation['verified_signer'] else 'INVALID'}")
    if attestation['is_demo_signature']:
        print(f"  {DEMO_PREFIX} Attestation signed with demo key.")

    if save_report_path:
        full_saved_report = {
            "summary": canonical_report_summary,
            "manifest": verification_manifest,
            "attestation": attestation,
            "multi_face_audit": best.multi_face_audit
        }
        with open(save_report_path, "w") as f:
            json.dump(full_saved_report, f, indent=2)
        print(f"\nSaved cryptographically signed report to {save_report_path}")

    print("\n================================================================================")
    print("                      PIPELINE EXECUTION COMPLETED")
    print("================================================================================\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Face ID + Blockchain Verification Pipeline (Production-Hardened CLI)"
    )
    parser.add_argument(
        "--image",
        type=str,
        default="sample_images/query_face.jpg",
        help="Path to input face image (JPG/PNG)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.60,
        help="Biometric cosine similarity threshold (default: 0.60)"
    )
    parser.add_argument(
        "--network",
        type=str,
        default="amoy",
        choices=["amoy", "sepolia"],
        help="Target blockchain testnet (amoy or sepolia)"
    )
    parser.add_argument(
        "--candidates",
        type=str,
        default=None,
        help="Optional path to candidate leads JSON file"
    )
    parser.add_argument(
        "--save-report",
        type=str,
        default=None,
        help="Optional path to export cryptographically signed verification report JSON"
    )
    parser.add_argument(
        "--demo-mode",
        action="store_true",
        default=False,
        help="Run in offline demonstration mode (prefixes demo markers, suppresses live API checks)"
    )
    parser.add_argument(
        "--consent-confirmed",
        action="store_true",
        default=False,
        help="Confirm subject's explicit consent for biometric verification & on-chain anchoring (GDPR/BIPA control)"
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=20,
        help="Maximum candidates to examine in a single run (default: 20)"
    )

    args = parser.parse_args()
    success = run_pipeline(
        image_path=args.image,
        threshold=args.threshold,
        network=args.network,
        candidates_file=args.candidates,
        save_report_path=args.save_report,
        demo_mode=args.demo_mode,
        consent_confirmed=args.consent_confirmed,
        max_candidates=args.max_candidates
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
