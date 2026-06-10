#!/usr/bin/env python3
"""
CLI Utility to encrypt and decrypt KAI-Flow environment variables using AES-256-GCM.
"""
import os
import sys
import argparse
from getpass import getpass

# Add current directory to path to find app module
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from app.core.env_encryption import EnvEncryption
except ImportError as e:
    print(f"Error importing env_encryption: {e}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="KAI-Flow Environment Variables Encryption CLI")
    parser.add_argument("-v", "--value", help="The value to encrypt or decrypt")
    parser.add_argument("-s", "--secret", help="The ENCRYPTION_SECRET_KEY to use (optional, will look in env or prompt)")
    parser.add_argument("-d", "--decrypt", action="store_true", help="Perform decryption instead of encryption")
    
    args = parser.parse_args()
    
    # Get secret key
    secret = args.secret or os.getenv("ENCRYPTION_SECRET_KEY")
    if not secret:
        print("ENCRYPTION_SECRET_KEY not provided via arguments or environment variable.")
        secret = getpass("Enter ENCRYPTION_SECRET_KEY: ").strip()
        if not secret:
            print("Error: Encryption key cannot be empty.")
            sys.exit(1)
            
    # Get value to process
    value = args.value
    if not value:
        value = input("Enter value to encrypt/decrypt: ").strip()
        if not value:
            print("Error: Value to encrypt/decrypt cannot be empty.")
            sys.exit(1)
            
    try:
        encryptor = EnvEncryption(secret_key=secret)
        
        if args.decrypt:
            decrypted = encryptor.decrypt(value, "CLI Input")
            print("\n--- DECRYPTED VALUE ---")
            print(decrypted)
            print("-----------------------")
        else:
            encrypted = encryptor.encrypt(value)
            print("\n--- ENCRYPTED VALUE (Copy to .env) ---")
            print(encrypted)
            print("--------------------------------------")
            
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
