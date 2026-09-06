"""
Unit tests for Smart Contract artifacts, IPFS integration, Web3 encoding, and report signing.
"""

import json
from pathlib import Path
from web3 import Web3
from eth_account import Account
from core.ipfs_client import IPFSClient
from core.blockchain_writer import BlockchainWriter

ROOT_DIR = Path(__file__).resolve().parent.parent
COMPILED_CONTRACT_PATH = ROOT_DIR / "contracts" / "FaceVerificationRegistry.json"
SAMPLE_DIR = ROOT_DIR / "sample_images"
QUERY_IMAGE = SAMPLE_DIR / "query_face.jpg"


def test_compiled_contract_exists_and_valid():
    assert COMPILED_CONTRACT_PATH.exists(), "FaceVerificationRegistry.json must exist"
    with open(COMPILED_CONTRACT_PATH, "r") as f:
        data = json.load(f)

    assert "abi" in data, "Contract JSON must contain ABI"
    assert "bytecode" in data, "Contract JSON must contain bytecode"
    assert len(data["bytecode"]) > 100, "Bytecode must not be empty"

    # Verify functions in ABI
    func_names = [item["name"] for item in data["abi"] if item.get("type") == "function"]
    assert "recordVerification" in func_names, "Contract must include recordVerification function"
    assert "getRecord" in func_names, "Contract must include getRecord function"
    assert "getRecordCount" in func_names, "Contract must include getRecordCount function"
    assert "getRecordIdsByCandidateFaceHash" in func_names, "Contract must include getRecordIdsByCandidateFaceHash"

    # Verify recordVerification includes candidateFaceHash (USP 2: Re-Derivability)
    rec_fn = next(item for item in data["abi"] if item.get("name") == "recordVerification")
    input_names = [inp["name"] for inp in rec_fn["inputs"]]
    assert "_faceHash" in input_names
    assert "_candidateFaceHash" in input_names
    assert len(input_names) == 7, "recordVerification must accept 7 arguments including candidateFaceHash"


def test_ipfs_client_deterministic_cid_demo_mode():
    client = IPFSClient()
    receipt = client.pin_file(QUERY_IMAGE, demo_mode=True)
    assert receipt.cid.startswith("Qm"), "IPFS CIDv0 must start with Qm"
    assert "DEMO MOCK CID" in receipt.ipfs_uri
    assert receipt.gateway_url == "[DEMO - NO LIVE GATEWAY]"
    assert receipt.is_real_pin is False


def test_ipfs_client_pin_json_manifest():
    client = IPFSClient()
    manifest_payload = {
        "protocol": "VeriFace/PoF",
        "query": {"face_hash": "0x" + "11" * 32},
        "candidate": {"face_hash": "0x" + "22" * 32},
        "similarity": 0.9407
    }
    receipt = client.pin_json(manifest_payload, demo_mode=True)
    assert receipt.cid.startswith("Qm")
    assert receipt.is_real_pin is False
    assert receipt.gateway_url == "[DEMO - NO LIVE GATEWAY]"


def test_blockchain_writer_calldata_encoding_and_demo_mode():
    writer = BlockchainWriter(network="amoy")
    dummy_q_hash = "0x" + "ab" * 32
    dummy_c_hash = "0x" + "cd" * 32
    ipfs_cid = "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco"
    matched_url = "https://x.com/verified/status/12345"
    confidence_bp = 9407
    source_platform = "x.com"
    detection_method = "YuNet+SFace-128d"

    receipt = writer.write_verification(
        face_hash=dummy_q_hash,
        candidate_face_hash=dummy_c_hash,
        ipfs_cid=ipfs_cid,
        matched_url=matched_url,
        match_confidence_bp=confidence_bp,
        source_platform=source_platform,
        detection_method=detection_method
    )

    # In demo mode, tx_hash is clearly marked and real explorer links are suppressed
    assert "[DEMO MOCK TX" in receipt.tx_hash
    assert receipt.explorer_url == "[DEMO - NO EXPLORER LINK]"
    assert receipt.is_live_tx is False
    assert "DEMO" in receipt.status_message


def test_cryptographic_report_signing():
    writer = BlockchainWriter(network="amoy")
    test_report_data = {
        "query_face_hash": "0x" + "aa" * 32,
        "candidate_face_hash": "0x" + "bb" * 32,
        "similarity": 0.9407,
        "tx_hash": "0x" + "cc" * 32
    }
    attestation = writer.sign_report_attestation(test_report_data)

    assert attestation["signer_address"].startswith("0x")
    assert len(attestation["signature"]) > 60
    assert attestation["verified_signer"] is True
    assert attestation["is_demo_signature"] is True
