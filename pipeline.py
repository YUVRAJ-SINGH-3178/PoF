#!/usr/bin/env python3
"""
Face ID + Blockchain Verification Pipeline (Production CLI).

USP: Search APIs are treated strictly as candidate generators, not verifiers.
Every candidate returned is independently re-scored using deep biometric face embeddings
before any record is permitted on the public blockchain testnet.

Usage:
    python pipeline.py --image path/to/input.jpg
    python pipeline.py --image path/to/input.jpg --threshold 0.65 --network amoy
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List
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
================================================================================
"""


def format_step(step_num: int, title: str) -> str:
    line = "-" * 80
    return f"\n{line}\n[STEP {step_num}] {title.upper()}\n{line}"


def run_pipeline(
    image_path: str,
    threshold: float = 0.60,
    network: str = "amoy",
    candidates_file: Optional[str] = None,
    save_report_path: Optional[str] = None
) -> bool:
    print(BANNER)

    input_img = Path(image_path)
    if not input_img.exists():
        print(f"[ERROR] Input image file not found: {image_path}")
        return False

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
    # STEP 2: Genuine Reverse-Image Search (Social Media Filtering)
    # -------------------------------------------------------------------------
    print(format_step(2, "Genuine Reverse-Image Search (Candidate Lead Discovery)"))
    searcher = ReverseImageSearch()
    candidates = []

    if searcher.has_credentials():
        print("  [*] Querying Reverse Image Search API (Google Vision / Bing)...")
        try:
            candidates = searcher.search(input_img)
            print(f"  [+] Search completed: Discovered {len(candidates)} candidate leads.")
        except Exception as e:
            print(f"  [!] Search API query error: {e}")
    else:
        print("  [INFO] No Search API keys configured in .env (GOOGLE_VISION_API_KEY / BING_VISUAL_SEARCH_API_KEY).")
        if candidates_file and Path(candidates_file).exists():
            print(f"  [*] Loading candidate test leads from: {candidates_file}")
            with open(candidates_file, "r") as f:
                raw_cands = json.load(f)
                candidates = [SearchCandidate(**c) for c in raw_cands]
        elif (Path("sample_images") / "test_candidates.json").exists():
            default_cand_file = Path("sample_images") / "test_candidates.json"
            print(f"  [*] Using verified benchmark candidate leads from: {default_cand_file}")
            with open(default_cand_file, "r") as f:
                raw_cands = json.load(f)
                candidates = [SearchCandidate(**c) for c in raw_cands]
        else:
            print("  [!] No search candidates available. Provide API keys or candidate leads.")

    if not candidates:
        print("\n  [RESULT] 0 candidates found matching social platform filters.")
        print("  Pipeline finished: No candidates to verify.")
        return False

    print("\n  Discovered Candidates (Treated as unverified visual leads):")
    for i, cand in enumerate(candidates, 1):
        print(f"    [{i}] Platform: {cand.source_platform}")
        print(f"        Page URL: {cand.page_url}")
        print(f"        Image   : {cand.image_url}")

    # -------------------------------------------------------------------------
    # STEP 3: Re-Verification Step (Core USP - Mandatory)
    # -------------------------------------------------------------------------
    print(format_step(3, "Mathematical Re-Verification (Core USP Differentiator)"))
    print(f"  Verification Threshold Configured : Cosine Similarity >= {threshold:.2f}")
    print(f"  Requirement                       : Independent biometric feature re-extraction\n")

    verifier = ReVerificationEngine(encoder=encoder, similarity_threshold=threshold)
    report: VerificationReport = verifier.re_verify_all(primary_face, candidates, threshold=threshold)

    print("  Candidate-by-Candidate Re-Verification Results:")
    all_results = report.verified_matches + report.rejected_candidates
    for i, res in enumerate(all_results, 1):
        status_tag = "[PASS - VERIFIED]" if res.is_verified else "[FAIL - REJECTED]"
        print(f"    Candidate #{i}: {res.candidate.page_url}")
        print(f"      Platform     : {res.candidate.source_platform}")
        print(f"      Face In Lead : {'Yes' if res.face_detected else 'No'}")
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

    # -------------------------------------------------------------------------
    # STEP 5: IPFS Decentralized Asset Pinning
    # -------------------------------------------------------------------------
    print(format_step(5, "IPFS Decentralized Asset Storage"))
    ipfs_client = IPFSClient()
    if ipfs_client.has_credentials():
        print("  [*] Pinning image to live IPFS node via Pinata API...")
    else:
        print("  [INFO] No PINATA_JWT found in .env; generating deterministic multihash IPFS CID...")

    receipt = ipfs_client.pin_file(input_img)
    print(f"  [+] IPFS CID    : {receipt.cid}")
    print(f"  [+] IPFS URI    : {receipt.ipfs_uri}")
    print(f"  [+] Gateway URL : {receipt.gateway_url}")
    print(f"  [+] Live Pinned : {'Yes (Pinata)' if receipt.is_real_pin else 'Deterministic CID'}")

    # -------------------------------------------------------------------------
    # STEP 6: Blockchain Testnet Write
    # -------------------------------------------------------------------------
    print(format_step(6, f"Blockchain Testnet Write ({network.upper()})"))
    writer = BlockchainWriter(network=network)
    print(f"  [*] Target Network: {writer.net_cfg['name']} (Chain ID {writer.net_cfg['chain_id']})")
    print(f"  [*] RPC Endpoint  : {writer.rpc_url}")
    print(f"  [*] Node Connected: {'Yes' if writer.is_connected() else 'No'}")

    wallet_addr = writer.get_wallet_address()
    if wallet_addr:
        print(f"  [*] Wallet Address: {wallet_addr}")
        print(f"  [*] Native Balance: {writer.get_balance():.6f} Token")
    else:
        print("  [INFO] No WEB3_PRIVATE_KEY found in .env.")

    tx_receipt = writer.write_verification(
        face_hash=primary_face.face_hash,
        ipfs_cid=receipt.cid,
        matched_url=best.candidate.page_url,
        match_confidence_bp=best.match_confidence_bp,
        source_platform=best.candidate.source_platform,
        detection_method=primary_face.detection_method
    )

    # -------------------------------------------------------------------------
    # STEP 7: Block Explorer Link Output
    # -------------------------------------------------------------------------
    print(format_step(7, "Public Block Explorer Link & Proof"))
    print(f"  Transaction Hash    : {tx_receipt.tx_hash}")
    print(f"  Contract Address    : {tx_receipt.contract_address}")
    if tx_receipt.block_number:
        print(f"  Confirmed in Block  : {tx_receipt.block_number}")
        print(f"  Gas Used            : {tx_receipt.gas_used}")
    print(f"\n  >>> PUBLIC BLOCK EXPLORER URL <<<\n  {tx_receipt.explorer_url}\n")
    print(f"  Status Note         : {tx_receipt.status_message}")

    if save_report_path:
        out_data = {
            "query_face_hash": primary_face.face_hash,
            "detection_method": primary_face.detection_method,
            "matched_url": best.candidate.page_url,
            "source_platform": best.candidate.source_platform,
            "similarity": best.cosine_similarity,
            "confidence_bp": best.match_confidence_bp,
            "ipfs_cid": receipt.cid,
            "tx_hash": tx_receipt.tx_hash,
            "explorer_url": tx_receipt.explorer_url
        }
        with open(save_report_path, "w") as f:
            json.dump(out_data, f, indent=2)
        print(f"\nSaved JSON report to {save_report_path}")

    print("\n================================================================================")
    print("                      PIPELINE EXECUTION COMPLETED")
    print("================================================================================\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Face ID + Blockchain Verification Pipeline (Production CLI)"
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
        help="Optional path to candidate leads JSON file (for testing)"
    )
    parser.add_argument(
        "--save-report",
        type=str,
        default=None,
        help="Optional path to export verification report JSON"
    )

    args = parser.parse_args()
    success = run_pipeline(
        image_path=args.image,
        threshold=args.threshold,
        network=args.network,
        candidates_file=args.candidates,
        save_report_path=args.save_report
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
