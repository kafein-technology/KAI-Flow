import base64
import os
import re
import logging
from typing import Optional, Callable
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

class EnvEncryption:
    """
    Handles encryption and decryption of environment variables using AES-256-GCM
    with keys derived from ENCRYPTION_SECRET_KEY via PBKDF2.
    """
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or os.getenv("ENCRYPTION_SECRET_KEY")
        self._key = None
        if self.secret_key:
            self._key = self._derive_key(self.secret_key)
            
    def _derive_key(self, secret_key: str) -> bytes:
        # PBKDF2 to derive a 256-bit key matching Kafein Java EncryptionUtil
        salt = b"randomSalt"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=65536,
        )
        return kdf.derive(secret_key.encode("utf-8"))

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypts plaintext string using AES-256-GCM.
        Returns a base64 encoded string containing the 12-byte nonce and GCM payload.
        """
        if not self._key:
            raise ValueError("ENCRYPTION_SECRET_KEY is not set or provided.")
        if plaintext is None:
            return None
            
        aesgcm = AESGCM(self._key)
        nonce = os.urandom(12)  # Recommended nonce size for GCM is 12 bytes
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        
        # Combine nonce and ciphertext (which includes the 16-byte GCM tag)
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode("utf-8")

    def decrypt(self, val: str, var_name: str) -> str:
        """
        Decrypts a base64 encoded ciphertext string using AES-256-GCM.
        If decryption fails (wrong key, bad GCM tag, or plain text value), fissions a RuntimeError.
        """
        if not self._key:
            return val
        if not val:
            return val
            
        try:
            # Base64 decode
            combined = base64.b64decode(val.encode("utf-8"), validate=True)
            if len(combined) < 28:  # 12 bytes nonce + at least 16 bytes tag/ciphertext
                raise ValueError("Payload too short for GCM")
                
            nonce = combined[:12]
            ciphertext = combined[12:]
            
            aesgcm = AESGCM(self._key)
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext_bytes.decode("utf-8")
        except Exception as e:
            # Raise a strict RuntimeError as required to fail fast
            raise RuntimeError(
                f"Failed to decrypt environment variable '{var_name}' using ENCRYPTION_SECRET_KEY. "
                f"Ensure the value is correctly encrypted with the configured key. Error: {e}"
            )

def decrypt_database_url(url: str, decrypt_func: Callable[[str, str], str]) -> str:
    """
    Utility to decrypt a DATABASE_URL.
    Supports standard PostgreSQL connection URLs, entirely encrypted URLs, and JDBC-style parameter URLs.
    """
    if not url:
        return url
        
    # First, try to decrypt the entire URL (in case the whole URL was encrypted)
    try:
        return decrypt_func(url, "DATABASE_URL (entire)")
    except RuntimeError:
        pass  # If decrypting the entire URL fails, we assume only the credentials inside are encrypted
        
    # Check if there is credentials section (between :// and @)
    # Match: protocol://[credentials]@[rest_of_url]
    match = re.match(r"^([^:]+://)([^@]+)@(.*)$", url)
    if match:
        protocol, creds, rest = match.groups()
        if ":" in creds:
            user, password = creds.split(":", 1)
            # Decrypt user and password individually. If they fail, RuntimeError will be raised.
            user = decrypt_func(user, "DATABASE_URL (username)")
            password = decrypt_func(password, "DATABASE_URL (password)")
            return f"{protocol}{user}:{password}@{rest}"
        else:
            creds = decrypt_func(creds, "DATABASE_URL (credentials)")
            return f"{protocol}{creds}@{rest}"
            
    # Check for JDBC-style parameters: ?user=...&password=...
    if "?" in url:
        base_url, query_str = url.split("?", 1)
        params = query_str.split("&")
        new_params = []
        for p in params:
            if "=" in p:
                k, v = p.split("=", 1)
                # If the key is 'user', 'username', or 'password', we decrypt it
                if k.lower() in ("user", "username", "password"):
                    v = decrypt_func(v, f"DATABASE_URL (query param '{k}')")
                new_params.append(f"{k}={v}")
            else:
                new_params.append(p)
        return f"{base_url}?{'&'.join(new_params)}"
            
    return url
