#!/usr/bin/env python3
"""
Diagnostic Verification & Accuracy Tuning Script.
Runs a live health check on all configured APIs:
1. Face Models & ONNX Runtime (YuNet + SFace)
2. Google Cloud Vision API (Reverse-Image Search)
3. Pinata Cloud API (IPFS Decentralized Storage)
4. Polygon Amoy Blockchain & Testnet Wallet Balance
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import requests

# Load environment configuration
load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def check_mark(status: bool) -> str:
    return "[PASS] " if status else "[FAIL] "

def verify_models():
    print("\n" + "=" * 60)
    print("1. CHECKING BIOMETRIC FACE RECOGNITION MODELS")
    print("=" * 60)
    yunet = ROOT_DIR / "models" / "yunet.onnx"
    sface = ROOT_DIR / "models" / "sface.onnx"
    
    y_ok = yunet.exists() and yunet.stat().st_size > 100000
    s_ok = sface.exists() and sface.stat().st_size > 30000000
    
    print(f"  {check_mark(y_ok)} YuNet Detector Model : {yunet.name} ({yunet.stat().st_size // 1024 if yunet.exists() else 0} KB)")
    print(f"  {check_mark(s_ok)} SFace Recognizer Model: {sface.name} ({sface.stat().st_size // (1024*1024) if sface.exists() else 0} MB)")
    
    try:
        from core.face_encoder import FaceEncoder
        enc = FaceEncoder()
        print(f"  {check_mark(True)} OpenCV DNN & ONNXRuntime loaded successfully.")
        return y_ok and s_ok
    except Exception as e:
        print(f"  {check_mark(False)} Error loading FaceEncoder: {e}")
        return False

def verify_google_vision():
    print("\n" + "=" * 60)
    print("2. CHECKING REVERSE-IMAGE SEARCH API")
    print("=" * 60)
    api_key = os.getenv("GOOGLE_VISION_API_KEY")
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    bing_key = os.getenv("BING_VISUAL_SEARCH_API_KEY")

    if not api_key and not creds_path and not bing_key:
        print("  [FAIL] No Search API keys found in .env.")
        print("  -> Set GOOGLE_VISION_API_KEY=AIzaSy... in .env")
        print("  -> Where to get it: https://console.cloud.google.com/apis/credentials")
        return False

    if api_key:
        print(f"  [*] Testing Google Cloud Vision API Key: {api_key[:6]}...{api_key[-4:]}")
        test_url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
        payload = {
            "requests": [
                {
                    "image": {"content": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="},
                    "features": [{"type": "WEB_DETECTION", "maxResults": 1}]
                }
            ]
        }
        try:
            resp = requests.post(test_url, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"  {check_mark(True)} Google Cloud Vision API is LIVE and working!")
                return True
            else:
                err_msg = resp.json().get("error", {}).get("message", resp.text)
                print(f"  {check_mark(False)} Google Vision API Error ({resp.status_code}): {err_msg}")
                if "SERVICE_DISABLED" in err_msg or "has not been used" in err_msg:
                    print("  -> Enable it here: https://console.cloud.google.com/apis/library/vision.googleapis.com")
                return False
        except Exception as e:
            print(f"  {check_mark(False)} Network error contacting Google Vision API: {e}")
            return False
            
    if bing_key:
        print(f"  {check_mark(True)} Bing Visual Search Key configured ({bing_key[:6]}...).")
        return True

    return False

def verify_pinata_ipfs():
    print("\n" + "=" * 60)
    print("3. CHECKING IPFS STORAGE (PINATA)")
    print("=" * 60)
    jwt = os.getenv("PINATA_JWT")
    api_key = os.getenv("PINATA_API_KEY")
    api_secret = os.getenv("PINATA_API_SECRET")

    if not jwt and not (api_key and api_secret):
        print("  [FAIL] No Pinata credentials found in .env.")
        print("  -> Set PINATA_JWT=eyJhbGciOi... in .env")
        print("  -> Where to get it: https://app.pinata.cloud/developers/api-keys")
        return False

    headers = {}
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    else:
        headers["pinata_api_key"] = api_key
        headers["pinata_secret_api_key"] = api_secret

    try:
        resp = requests.get("https://api.pinata.cloud/data/testAuthentication", headers=headers, timeout=10)
        if resp.status_code == 200:
            msg = resp.json().get("message", "Authenticated")
            print(f"  {check_mark(True)} Pinata IPFS API is LIVE: {msg}")
            return True
        else:
            print(f"  {check_mark(False)} Pinata API authentication failed ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"  {check_mark(False)} Network error contacting Pinata: {e}")
        return False

def verify_blockchain():
    print("\n" + "=" * 60)
    print("4. CHECKING POLYGON AMOY TESTNET & WALLET")
    print("=" * 60)
    from core.blockchain_writer import BlockchainWriter
    writer = BlockchainWriter(network="amoy")
    
    rpc_ok = writer.is_connected()
    if rpc_ok:
        block = writer.w3.eth.block_number
        print(f"  {check_mark(True)} RPC Node Connected: {writer.rpc_url} (Block #{block})")
    else:
        print(f"  {check_mark(False)} Could not connect to RPC: {writer.rpc_url}")
        return False

    wallet_addr = writer.get_wallet_address()
    if not wallet_addr:
        print("  [FAIL] No WEB3_PRIVATE_KEY found in .env.")
        print("  -> Run `python scripts/generate_test_keys.py` to create one.")
        return False

    balance = writer.get_balance()
    print(f"  {check_mark(True)} Wallet Address: {wallet_addr}")
    bal_ok = balance > 0
    print(f"  {check_mark(bal_ok)} Wallet Balance: {balance:.6f} POL (Amoy)")
    if not bal_ok:
        print("  -> Fund wallet via free faucet: https://faucet.polygon.technology/")
        print(f"  -> Paste your address: {wallet_addr}")

    contract_addr = os.getenv("CONTRACT_ADDRESS")
    if contract_addr:
        try:
            code = writer.w3.eth.get_code(contract_addr)
            has_code = len(code) > 2
            print(f"  {check_mark(has_code)} Smart Contract Address: {contract_addr} ({'Active on-chain' if has_code else 'No bytecode found'})")
        except Exception as e:
            print(f"  [FAIL] Error querying contract at {contract_addr}: {e}")
    else:
        print("  [INFO] CONTRACT_ADDRESS not set in .env.")
        print("  -> Deploy contract using: python scripts/deploy_contract.py amoy")

    return rpc_ok and bal_ok

def main():
    print("""
============================================================
       FACE ID + BLOCKCHAIN PIPELINE: SETUP DIAGNOSTIC
============================================================
    """)
    m = verify_models()
    v = verify_google_vision()
    p = verify_pinata_ipfs()
    b = verify_blockchain()

    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print(f"  Models & Biometrics: {'READY' if m else 'NEEDS ATTENTION'}")
    print(f"  Reverse Search API : {'READY' if v else 'MISSING / NEEDS KEY'}")
    print(f"  IPFS Pinata Storage: {'READY' if p else 'MISSING / NEEDS KEY'}")
    print(f"  Blockchain Testnet : {'READY' if b else 'NEEDS WALLET / FAUCET'}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
