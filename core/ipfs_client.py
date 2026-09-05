"""
Decentralized Storage Client (IPFS).
Pins verified face images and identity metadata manifests to IPFS via Pinata or Web3.Storage.
Returns canonical IPFS CIDs (ipfs://Qm... or ipfs://bafy...) to be anchored on-chain.
"""

import os
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Union, Dict, Any
import requests

PINATA_PIN_FILE_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"
PINATA_PIN_JSON_URL = "https://api.pinata.cloud/pinning/pinJSONToIPFS"


@dataclass
class IPFSReceipt:
    cid: str                # e.g., "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco" or "bafy..."
    ipfs_uri: str           # e.g., "ipfs://Qm..."
    gateway_url: str        # e.g., "https://gateway.pinata.cloud/ipfs/Qm..."
    pin_size: int
    is_real_pin: bool       # True if pinned to live IPFS node via Pinata API


class IPFSClient:
    """
    Client for pinning images and cryptographic metadata manifests to IPFS.
    """

    def __init__(
        self,
        pinata_jwt: Optional[str] = None,
        pinata_api_key: Optional[str] = None,
        pinata_api_secret: Optional[str] = None
    ):
        self.pinata_jwt = pinata_jwt or os.getenv("PINATA_JWT")
        self.pinata_api_key = pinata_api_key or os.getenv("PINATA_API_KEY")
        self.pinata_api_secret = pinata_api_secret or os.getenv("PINATA_API_SECRET")

    def has_credentials(self) -> bool:
        """Check whether live Pinata credentials are configured."""
        return bool(self.pinata_jwt or (self.pinata_api_key and self.pinata_api_secret))

    def _get_headers(self) -> Dict[str, str]:
        if self.pinata_jwt:
            return {"Authorization": f"Bearer {self.pinata_jwt}"}
        elif self.pinata_api_key and self.pinata_api_secret:
            return {
                "pinata_api_key": self.pinata_api_key,
                "pinata_secret_api_key": self.pinata_api_secret
            }
        return {}

    @staticmethod
    def compute_deterministic_cid(file_bytes: bytes) -> str:
        """
        Compute deterministic base58-style IPFS v0 CID (Qm...) from content hash
        for verifiable offline integrity checking if API key is not yet set.
        """
        sha256_hash = hashlib.sha256(file_bytes).digest()
        # IPFS multihash prefix for sha256 (0x12) + length 32 (0x20)
        multihash = b"\x12\x20" + sha256_hash

        # Standard Base58 encode
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        num = int.from_bytes(multihash, "big")
        encoded = ""
        while num > 0:
            num, rem = divmod(num, 58)
            encoded = alphabet[rem] + encoded

        # Preserve leading zeros
        for byte in multihash:
            if byte == 0:
                encoded = "1" + encoded
            else:
                break
        return encoded

    def pin_file(self, file_path: Union[str, Path]) -> IPFSReceipt:
        """
        Upload image file to IPFS via Pinata.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found at {path}")

        with open(path, "rb") as f:
            file_bytes = f.read()

        if self.has_credentials():
            headers = self._get_headers()
            files = {
                "file": (path.name, file_bytes)
            }
            metadata = {
                "name": f"face-id-verification-{path.stem}"
            }
            data = {"pinataMetadata": json.dumps(metadata)}

            try:
                resp = requests.post(PINATA_PIN_FILE_URL, headers=headers, files=files, data=data, timeout=30)
                if resp.status_code == 200:
                    res_json = resp.json()
                    cid = res_json["IpfsHash"]
                    pin_size = res_json.get("PinSize", len(file_bytes))
                    return IPFSReceipt(
                        cid=cid,
                        ipfs_uri=f"ipfs://{cid}",
                        gateway_url=f"https://gateway.pinata.cloud/ipfs/{cid}",
                        pin_size=pin_size,
                        is_real_pin=True
                    )
                else:
                    print(f"[IPFS Warning] Pinata API returned {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[IPFS Warning] Live Pinata upload error: {e}")

        # Fallback to deterministic cryptographic CID
        cid = self.compute_deterministic_cid(file_bytes)
        return IPFSReceipt(
            cid=cid,
            ipfs_uri=f"ipfs://{cid}",
            gateway_url=f"https://ipfs.io/ipfs/{cid}",
            pin_size=len(file_bytes),
            is_real_pin=False
        )

    def pin_json(self, data_dict: Dict[str, Any], name: str = "verification-metadata") -> IPFSReceipt:
        """
        Pin JSON metadata manifest to IPFS.
        """
        json_bytes = json.dumps(data_dict, indent=2).encode("utf-8")

        if self.has_credentials():
            headers = self._get_headers()
            headers["Content-Type"] = "application/json"
            payload = {
                "pinataMetadata": {"name": name},
                "pinataContent": data_dict
            }
            try:
                resp = requests.post(PINATA_PIN_JSON_URL, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    res_json = resp.json()
                    cid = res_json["IpfsHash"]
                    return IPFSReceipt(
                        cid=cid,
                        ipfs_uri=f"ipfs://{cid}",
                        gateway_url=f"https://gateway.pinata.cloud/ipfs/{cid}",
                        pin_size=res_json.get("PinSize", len(json_bytes)),
                        is_real_pin=True
                    )
            except Exception as e:
                print(f"[IPFS Warning] Live Pinata JSON upload error: {e}")

        cid = self.compute_deterministic_cid(json_bytes)
        return IPFSReceipt(
            cid=cid,
            ipfs_uri=f"ipfs://{cid}",
            gateway_url=f"https://ipfs.io/ipfs/{cid}",
            pin_size=len(json_bytes),
            is_real_pin=False
        )
