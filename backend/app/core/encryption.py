import os
import logging
import json
import base64
from typing import Dict, Any, Union, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from .constants import CREDENTIAL_MASTER_KEY

class CredentialEncryption:
    """
    Handles encryption and decryption of sensitive credential data using Fernet
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption with a master key
        If no key provided, uses environment variable or generates one
        """
        if master_key:
            self.master_key = master_key
        else:
            self.master_key = CREDENTIAL_MASTER_KEY
            
        if not self.master_key:
            # Generate a new key if none exists (for development)
            # In production, this should be provided via environment
            self.master_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
            logging.warning(
                "  Generated new encryption key. Set CREDENTIAL_MASTER_KEY environment variable!"
            )

        # Create Fernet cipher
        self.cipher = self._create_cipher()
    
    def _create_cipher(self) -> Fernet:
        """Create Fernet cipher from master key"""
        try:
            # Ensure master_key is not None
            if not self.master_key:
                raise ValueError("Master key is required")
                
            # If master key is already a valid Fernet key
            if len(self.master_key) == 44 and self.master_key.endswith('='):
                key = self.master_key.encode()
            else:
                # Derive key from master key using PBKDF2
                salt = b"salt_"  # In production, use a random salt stored separately
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
            
            return Fernet(key)

        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")
    
    def encrypt(self, data: Union[Dict[str, Any], str]) -> bytes:
        """
        Encrypt credential data
        
        Args:
            data: Dictionary or string to encrypt
            
        Returns:
            Encrypted bytes
        """
        try:
            # Convert to JSON string if dict
            if isinstance(data, dict):
                json_str = json.dumps(data, sort_keys=True)
            else:
                json_str = str(data)
            
            # Encrypt the JSON string
            encrypted_data = self.cipher.encrypt(json_str.encode('utf-8'))
            return encrypted_data
            
        except Exception as e:
            raise ValueError(f"Encryption failed: {e}")
    
    def decrypt(self, encrypted_data: bytes) -> Dict[str, Any]:
        """
        Decrypt credential data
        
        Args:
            encrypted_data: Encrypted bytes to decrypt
            
        Returns:
            Decrypted dictionary
        """
        try:
            # Decrypt the data
            decrypted_bytes = self.cipher.decrypt(encrypted_data)
            decrypted_str = decrypted_bytes.decode('utf-8')
            
            # Parse JSON
            try:
                return json.loads(decrypted_str)
            except json.JSONDecodeError:
                # If not JSON, return as string in a dict
                return {"value": decrypted_str}
                
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
    
    def rotate_key(self, new_master_key: str, old_encrypted_data: bytes) -> bytes:
        """
        Re-encrypt data with a new master key
        
        Args:
            new_master_key: New encryption key
            old_encrypted_data: Data encrypted with old key
            
        Returns:
            Data encrypted with new key
        """
        # Decrypt with old key
        decrypted_data = self.decrypt(old_encrypted_data)

        # Create new cipher with new key
        old_master_key = self.master_key
        self.master_key = new_master_key
        self.cipher = self._create_cipher()
        
        try:
            # Encrypt with new key
            return self.encrypt(decrypted_data)
        except Exception as e:
            # Restore old key on failure
            self.master_key = old_master_key
            self.cipher = self._create_cipher()
            raise e


# Global encryption instance
_encryption = CredentialEncryption()

def encrypt_data(data: Union[Dict[str, Any], str]) -> bytes:
    """
    Convenience function to encrypt data using global instance
    """
    return _encryption.encrypt(data)

def decrypt_data(encrypted_data: bytes) -> Dict[str, Any]:
    """
    Convenience function to decrypt data using global instance
    """
    return _encryption.decrypt(encrypted_data)

def get_encryption_instance() -> CredentialEncryption:
    """
    Get the global encryption instance
    """
    return _encryption

def set_master_key(master_key: str):
    """
    Set a new master key for encryption
    """
    global _encryption
    _encryption = CredentialEncryption(master_key)

# Utility functions for key generation
def generate_master_key() -> str:
    """
    Generate a new master key for encryption
    """
    return base64.urlsafe_b64encode(os.urandom(32)).decode()

def generate_fernet_key() -> str:
    """
    Generate a Fernet-compatible key
    """
    return Fernet.generate_key().decode() 