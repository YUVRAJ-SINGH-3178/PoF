#!/usr/bin/env python3
"""
Deployment script for FaceVerificationRegistry smart contract.
Supports Polygon Amoy testnet, Ethereum Sepolia, or any EVM testnet.
"""

import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

# Load environment variables
load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
COMPILED_CONTRACT_PATH = ROOT_DIR / "contracts" / "FaceVerificationRegistry.json"

NETWORK_CONFIGS = {
    "amoy": {
        "name": "Polygon Amoy Testnet",
        "rpc_url": os.getenv("AMOY_RPC_URL", "https://polygon-amoy-bor-rpc.publicnode.com"),
        "chain_id": 80002,
        "explorer": "https://amoy.polygonscan.com"
    },
    "sepolia": {
        "name": "Ethereum Sepolia Testnet",
        "rpc_url": os.getenv("SEPOLIA_RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com"),
        "chain_id": 11155111,
        "explorer": "https://sepolia.etherscan.io"
    }
}

def deploy(network: str = "amoy", private_key: str = None, rpc_url: str = None) -> str:
    net_key = network.lower()
    cfg = NETWORK_CONFIGS.get(net_key, NETWORK_CONFIGS["amoy"])
    if net_key == "sepolia":
        target_rpc = rpc_url or os.getenv("SEPOLIA_RPC_URL") or cfg["rpc_url"]
    else:
        target_rpc = rpc_url or os.getenv("AMOY_RPC_URL") or os.getenv("WEB3_RPC_URL") or cfg["rpc_url"]

    pk = private_key or os.getenv("WEB3_PRIVATE_KEY")

    if not pk or "your_faucet" in pk.lower() or pk.strip() in ("", "0x"):
        print("\n[ERROR] Valid private key required. Set WEB3_PRIVATE_KEY in your .env file.")
        print("WEB3_PRIVATE_KEY currently contains a placeholder or is missing.")
        print("In MetaMask: Account Details -> Show Private Key -> copy 64-character hex key.")
        print("Example: WEB3_PRIVATE_KEY=0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d\n")
        return None

    if not pk.startswith("0x"):
        pk = "0x" + pk

    try:
        account = Account.from_key(pk)
    except Exception as e:
        print(f"\n[ERROR] Failed to load private key: {e}")
        print("Ensure WEB3_PRIVATE_KEY in .env is a valid 64-character hex private key (not your public wallet address).\n")
        return None

    if not COMPILED_CONTRACT_PATH.exists():
        print(f"[ERROR] Compiled contract file not found at {COMPILED_CONTRACT_PATH}")
        return None

    with open(COMPILED_CONTRACT_PATH, "r") as f:
        contract_data = json.load(f)

    abi = contract_data["abi"]
    bytecode = contract_data["bytecode"]

    print(f"Connecting to {cfg['name']} via {target_rpc}...")
    w3 = Web3(Web3.HTTPProvider(target_rpc))
    if not w3.is_connected():
        print(f"[ERROR] Failed to connect to RPC node at {target_rpc}")
        return None

    balance_wei = w3.eth.get_balance(account.address)
    balance_eth = w3.from_wei(balance_wei, "ether")
    print(f"Deployer Address: {account.address}")
    print(f"Account Balance:  {balance_eth:.6f} Native Token")

    if balance_wei == 0:
        print(f"[WARNING] Account balance is 0. Please fund your address {account.address} from a faucet.")
        print(f"Polygon Amoy Faucet: https://faucet.polygon.technology/")
        print(f"Sepolia Faucet: https://sepoliafaucet.com/")
        return None

    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(account.address)

    print("Estimating gas and constructing transaction...")
    tx_params = {
        "from": account.address,
        "nonce": nonce,
        "chainId": cfg["chain_id"]
    }

    min_prio = w3.to_wei(1.5, "gwei") if net_key == "sepolia" else w3.to_wei(30, "gwei")
    try:
        latest_block = w3.eth.get_block("latest")
        base_fee = latest_block.get("baseFeePerGas")
        if base_fee:
            try:
                suggested_prio = w3.eth.max_priority_fee
            except Exception:
                suggested_prio = min_prio
            priority_fee = max(suggested_prio or min_prio, min_prio)
            tx_params["maxPriorityFeePerGas"] = priority_fee
            tx_params["maxFeePerGas"] = int(base_fee * 1.5 + priority_fee)
        else:
            tx_params["gasPrice"] = max(w3.eth.gas_price, min_prio)
    except Exception:
        tx_params["gasPrice"] = min_prio + w3.to_wei(2, "gwei")

    construct_tx = Contract.constructor().build_transaction(tx_params)
    gas_estimate = w3.eth.estimate_gas(construct_tx)
    construct_tx["gas"] = int(gas_estimate * 1.2)

    print("Signing deployment transaction...")
    signed_tx = w3.eth.account.sign_transaction(construct_tx, private_key=pk)

    print("Broadcasting transaction to blockchain...")
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_hash_hex = tx_hash.hex()
    print(f"Transaction sent! Tx Hash: {tx_hash_hex}")
    print(f"Explorer URL: {cfg['explorer']}/tx/{tx_hash_hex}")

    print("Waiting for block confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

    if receipt.status == 1:
        contract_address = receipt.contractAddress
        print("\n========================================================")
        print(f"  CONTRACT DEPLOYED SUCCESSFULLY!")
        print(f"  Contract Address: {contract_address}")
        print(f"  Block Number:     {receipt.blockNumber}")
        print(f"  Gas Used:         {receipt.gasUsed}")
        print(f"  Explorer:         {cfg['explorer']}/address/{contract_address}")
        print("========================================================\n")

        # Optionally update .env
        update_env_file(contract_address, target_rpc)
        return contract_address
    else:
        print("[ERROR] Deployment transaction failed (reverted) on-chain.")
        return None

def update_env_file(contract_address: str, rpc_url: str):
    env_path = ROOT_DIR / ".env"
    lines = []
    has_contract = False
    has_rpc = False
    if env_path.exists():
        with open(env_path, "r") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.startswith("CONTRACT_ADDRESS="):
            new_lines.append(f"CONTRACT_ADDRESS={contract_address}\n")
            has_contract = True
        elif line.startswith("WEB3_RPC_URL="):
            new_lines.append(f"WEB3_RPC_URL={rpc_url}\n")
            has_rpc = True
        else:
            new_lines.append(line)

    if not has_contract:
        new_lines.append(f"CONTRACT_ADDRESS={contract_address}\n")
    if not has_rpc:
        new_lines.append(f"WEB3_RPC_URL={rpc_url}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)
    print(f"Updated CONTRACT_ADDRESS and WEB3_RPC_URL in {env_path}")

if __name__ == "__main__":
    net = sys.argv[1] if len(sys.argv) > 1 else "amoy"
    deploy(network=net)
