#!/usr/bin/env python3
"""
Independent Verification Re-Derivation Script.

Core USP (Second-Order): "Verification is re-derivable, not just recorded."
Given two images (or a saved verification report / on-chain manifest), this script
re-runs the exact open-source biometric encoder, re-computes both embedding hashes,
re-calculates the cosine similarity, and verifies the cryptographic signature
without trusting any prior runner.

Usage:
    # Verify from two images directly:
    python scripts/rederive_verification.py \
        --query-image sample_images/query_face.jpg \
        --candidate-image sample_images/matching_candidate.jpg

    # Verify an exported report artifact and cryptographic signature:
    python scripts/rederive_verification.py --report sample_report.json
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.face_encoder import FaceEncoder
from eth_account import Account
from eth_account.messages import encode_defunct


def rederive_from_images(query_path: str, candidate_path: str, threshold: float = 0.60):
    print("\n" + "=" * 80)
    print("      INDEPENDENT BIOMETRIC RE-DERIVATION AUDIT")
    print("      USP: Claimed on-chain matches can be mathematically recomputed")
    print("=" * 80)

    encoder = FaceEncoder()

    print(f"\n1. Encoding Query Image: {query_path}")
    q_faces = encoder.detect_and_encode(query_path)
    if not q_faces:
        print("[FAIL] No face detected in query image.")
        return False
    q_face = q_faces[0]
    print(f"   - Detection Method  : {q_face.detection_method}")
    print(f"   - Detection Score   : {q_face.confidence * 100:.2f}%")
    print(f"   - Re-Derived Hash   : {q_face.face_hash}")

    print(f"\n2. Encoding Candidate Image: {candidate_path}")
    c_faces = encoder.detect_and_encode(candidate_path)
    if not c_faces:
        print("[FAIL] No face detected in candidate image.")
        return False
    c_face = c_faces[0]
    print(f"   - Detection Method  : {c_face.detection_method}")
    print(f"   - Detection Score   : {c_face.confidence * 100:.2f}%")
    print(f"   - Re-Derived Hash   : {c_face.face_hash}")

    print("\n3. Re-Calculating Exact Biometric Distance")
    similarity = encoder.compute_cosine_similarity(q_face.embedding, c_face.embedding)
    distance = encoder.compute_cosine_distance(q_face.embedding, c_face.embedding)
    l2_dist = encoder.compute_euclidean_distance(q_face.embedding, c_face.embedding)
    confidence_bp = int(similarity * 10000)
    is_match = similarity >= threshold

    print(f"   - Cosine Similarity : {similarity:.6f}")
    print(f"   - Cosine Distance   : {distance:.6f}")
    print(f"   - Euclidean (L2)    : {l2_dist:.6f}")
    print(f"   - Basis Points      : {confidence_bp} bp ({confidence_bp / 100:.2f}%)")
    print(f"   - Threshold Used    : {threshold:.2f}")
    print(f"   - Audit Result      : {'[VERIFIED MATCH]' if is_match else '[REJECTED - DIFFERENT PERSON]'}")

    print("\n4. Summary of Cryptographic Values for On-Chain Cross-Check:")
    print(f"   * bytes32 queryFaceHash     : {q_face.face_hash}")
    print(f"   * bytes32 candidateFaceHash : {c_face.face_hash}")
    print(f"   * uint256 matchConfidence   : {confidence_bp} bp")
    print("=" * 80 + "\n")
    return is_match


def verify_report_signature(report_path: str):
    print("\n" + "=" * 80)
    print("      CRYPTOGRAPHIC REPORT & ATTESTATION VERIFIER")
    print("=" * 80)

    p = Path(report_path)
    if not p.exists():
        print(f"[ERROR] Report file not found: {report_path}")
        return False

    with open(p, "r") as f:
        data = json.load(f)

    summary = data.get("summary", {})
    attestation = data.get("attestation", {})

    print(f"\n1. Loaded Verification Report: {report_path}")
    print(f"   - Query Face Hash     : {summary.get('query_face_hash')}")
    print(f"   - Candidate Face Hash : {summary.get('candidate_face_hash')}")
    print(f"   - Similarity Claimed  : {summary.get('similarity')}")
    print(f"   - Tx Hash Claimed     : {summary.get('tx_hash')}")
    print(f"   - Contract Address    : {summary.get('contract_address')}")
    print(f"   - IPFS Manifest CID   : {summary.get('ipfs_manifest_cid')}")

    print("\n2. Re-Verifying EIP-191 Cryptographic Signature")
    claimed_signer = attestation.get("signer_address")
    sig = attestation.get("signature")

    canonical_str = json.dumps(summary, sort_keys=True, separators=(',', ':'))
    signable_msg = encode_defunct(text=canonical_str)
    try:
        recovered = Account.recover_message(signable_msg, signature=bytes.fromhex(sig[2:] if sig.startswith("0x") else sig))
        print(f"   - Claimed Signer     : {claimed_signer}")
        print(f"   - Recovered Signer   : {recovered}")
        
        matches = recovered.lower() == claimed_signer.lower()
        print(f"   - Signature Status   : {'[VALID - SIGNATURE MATCHES SENDER]' if matches else '[INVALID SIGNATURE]'}")
        if attestation.get("is_demo_signature"):
            print("   - Note: Report signed with deterministic demo wallet key.")
        return matches
    except Exception as e:
        print(f"[ERROR] Failed recovering signature: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="VeriFace Independent Re-Derivation & Signature Verifier"
    )
    parser.add_argument("--query-image", type=str, help="Path to query face image")
    parser.add_argument("--candidate-image", type=str, help="Path to candidate face image")
    parser.add_argument("--threshold", type=float, default=0.60, help="Similarity threshold")
    parser.add_argument("--report", type=str, help="Path to exported verification report JSON")

    args = parser.parse_args()

    if args.report:
        ok = verify_report_signature(args.report)
        sys.exit(0 if ok else 1)
    elif args.query_image and args.candidate_image:
        ok = rederive_from_images(args.query_image, args.candidate_image, args.threshold)
        sys.exit(0 if ok else 1)
    else:
        print("Specify either --report <path> or both --query-image <path> and --candidate-image <path>")
        sys.exit(1)


if __name__ == "__main__":
    main()
