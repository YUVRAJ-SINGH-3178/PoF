"""
Unit tests for Smart Contract artifacts, IPFS integration, and Web3 encoding.
"""

import json
from pathlib import Path
from web3 import Web3
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


def test_ipfs_client_deterministic_cid():
    client = IPFSClient()
    receipt = client.pin_file(QUERY_IMAGE)
    assert receipt.cid.startswith("Qm"), "IPFS CIDv0 must start with Qm"
    assert receipt.ipfs_uri == f"ipfs://{receipt.cid}"
    assert receipt.gateway_url == f"https://ipfs.io/ipfs/{receipt.cid}"


def test_blockchain_writer_calldata_encoding():
    writer = BlockchainWriter(network="amoy")
    dummy_face_hash = "0x" + "ab" * 32
    ipfs_cid = "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco"
    matched_url = "https://x.com/verified/status/12345"
    confidence_bp = 9407
    source_platform = "x.com"
    detection_method = "YuNet+SFace-128d"

    receipt = writer.write_verification(
        face_hash=dummy_face_hash,
        ipfs_cid=ipfs_cid,
        matched_url=matched_url,
        match_confidence_bp=confidence_bp,
        source_platform=source_platform,
        detection_method=detection_method
    )

    assert receipt.tx_hash.startswith("0x"), "Transaction hash must be 0x-prefixed hex"
    assert receipt.explorer_url.startswith("https://amoy.polygonscan.com/tx/0x")
    assert receipt.network_name == "Polygon Amoy Testnet"
    assert receipt.chain_id == 80002
