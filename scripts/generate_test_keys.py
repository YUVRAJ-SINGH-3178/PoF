#!/usr/bin/env python3
"""
Utility script to generate a new Ethereum/Polygon testnet wallet,
check balance on Polygon Amoy, and display instructions for getting faucet tokens.
"""

import sys
from eth_account import Account
from web3 import Web3

AMOY_RPC = "https://rpc-amoy.polygon.technology"

def main():
    print("\n=== Testnet Wallet Generator & Diagnostic ===")
    account = Account.create()
    print(f"Generated Public Address : {account.address}")
    print(f"Private Key              : {account.key.hex()}")
    print("\nTo use this wallet, copy the private key to your .env file:")
    print(f"WEB3_PRIVATE_KEY={account.key.hex()}\n")

    print("Checking Polygon Amoy RPC connection...")
    try:
        w3 = Web3(Web3.HTTPProvider(AMOY_RPC))
        if w3.is_connected():
            print("Successfully connected to Polygon Amoy RPC!")
            print(f"Current Block Number: {w3.eth.block_number}")
        else:
            print("[Warning] Could not reach default Amoy RPC endpoint.")
    except Exception as e:
        print(f"[Warning] RPC check error: {e}")

    print("\nFund this wallet on Polygon Amoy testnet:")
    print("Faucet URL: https://faucet.polygon.technology/")
    print(f"Paste your address: {account.address}\n")

if __name__ == "__main__":
    main()
