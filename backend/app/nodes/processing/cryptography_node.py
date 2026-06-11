"""
KAI-Flow Cryptography Node
===========================

A secure, flexible, and robust processing node designed to encrypt and decrypt texts,
JSON payloads, or variable structures within AI workflows using AES (GCM/CBC), Fernet,
ChaCha20-Poly1305, RSA-OAEP, or Base64.
Supports dynamic Jinja2 template rendering for incoming data streams.
"""

import base64
import json
import logging
import os
import secrets
from typing import Dict, Any, Union, Optional

from jinja2 import Environment
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.backends import default_backend

from ..base import (
    ProcessorNode,
    NodeInput,
    NodeOutput,
    NodeType,
    NodeProperty,
    NodePropertyType,
    NodePosition,
)

logger = logging.getLogger(__name__)

class CryptographyNode(ProcessorNode):
    """
    Cryptography Node - Enterprise-grade encryption, decryption, digital signing, and verification.
    
    Provides AES-GCM, AES-CBC, ChaCha20-Poly1305, RSA-OAEP, RSA-PSS signatures, Fernet, and Base64
    cryptographic capabilities for KAI-Flow workflows.
    """
    
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "CryptographyNode",
            "display_name": "Cryptography",
            "description": (
                "Enterprise-grade symmetric and asymmetric encryption, decryption, digital signing, and verification. "
                "Supports Jinja templates and Base64 fallback encoding."
            ),
            "category": "Processing",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "cryptography", "path": "icons/Cryptography.svg", "alt": "Cryptography"},
            "colors": ["emerald-400", "emerald-600"],
            "inputs": [
                NodeInput(
                    name="input_data",
                    displayName="Input",
                    type="any",
                    description="Input data to process. If unconnected, reads from the Text Input property.",
                    is_connection=True,
                    required=False,
                    direction=NodePosition.LEFT,
                ),
            ],
            "outputs": [
                NodeOutput(
                    name="output",
                    displayName="Output",
                    type="any",
                    description="Cryptographic output (encrypted string, decrypted payload, signature, or verification result).",
                    is_connection=True,
                    direction=NodePosition.RIGHT,
                ),
                NodeOutput(
                    name="success",
                    displayName="Success",
                    type="bool",
                    description="Indicates if the cryptographic operation completed successfully.",
                ),
                NodeOutput(
                    name="error",
                    displayName="Error",
                    type="str",
                    description="Contains the error message if the operation failed.",
                )
            ],
            "properties": [
                NodeProperty(
                    name="action",
                    displayName="Action",
                    type=NodePropertyType.SELECT,
                    description="Select the cryptographic action to perform.",
                    required=True,
                    default="encrypt",
                    options=[
                        {"label": "Encrypt", "value": "encrypt"},
                        {"label": "Decrypt", "value": "decrypt"},
                        {"label": "Sign", "value": "sign"},
                        {"label": "Verify", "value": "verify"},
                        {"label": "Generate", "value": "generate"}
                    ]
                ),
                NodeProperty(
                    name="crypto_type",
                    displayName="Cryptography Type",
                    type=NodePropertyType.SELECT,
                    description="Select symmetric (shared key) or asymmetric (public/private key) cryptography.",
                    required=True,
                    default="symmetric",
                    options=[
                        {"label": "Symmetric (Shared Key)", "value": "symmetric"},
                        {"label": "Asymmetric (Public/Private Key)", "value": "asymmetric"}
                    ]
                ),
                NodeProperty(
                    name="cipher",
                    displayName="Cipher / Algorithm",
                    type=NodePropertyType.SELECT,
                    description="Choose the cryptographic algorithm.",
                    required=True,
                    default="aes-256-gcm",
                    options=[
                        {"label": "AES-256-GCM (Recommended)", "value": "aes-256-gcm"},
                        {"label": "AES-128-GCM", "value": "aes-128-gcm"},
                        {"label": "AES-256-CBC", "value": "aes-256-cbc"},
                        {"label": "ChaCha20-Poly1305", "value": "chacha20-poly1305"},
                        {"label": "Fernet (Legacy AES-128)", "value": "fernet"},
                        {"label": "Base64 (Encoding only)", "value": "base64"},
                        {"label": "RSA-OAEP (Asymmetric Encryption)", "value": "rsa-oaep"},
                        {"label": "RSA-SHA256 (Signature)", "value": "rsa-sha256"},
                        {"label": "RSA-SHA512 (Signature)", "value": "rsa-sha512"}
                    ]
                ),
                NodeProperty(
                    name="key",
                    displayName="Secret Key / Passphrase",
                    type=NodePropertyType.PASSWORD,
                    description="The secret key or passphrase for symmetric operations.",
                    required=False,
                    default="",
                    hint="Any password or passphrase. E.g. 'my-secure-key-123'",
                    displayOptions={
                        "show": {
                            "crypto_type": "symmetric"
                        }
                    }
                ),
                NodeProperty(
                    name="rsa_key_source",
                    displayName="RSA Key Source",
                    type=NodePropertyType.SELECT,
                    description="Whether to provide your own PEM key or automatically generate a new key pair.",
                    required=False,
                    default="provide",
                    options=[
                        {"label": "Provide PEM Key", "value": "provide"},
                        {"label": "Auto-Generate Key Pair", "value": "auto-generate"}
                    ],
                    displayOptions={
                        "show": {
                            "crypto_type": "asymmetric"
                        }
                    }
                ),
                NodeProperty(
                    name="private_key",
                    displayName="Private Key (PEM)",
                    type=NodePropertyType.TEXT_AREA,
                    description="RSA Private Key in PEM format. Required for Decrypt and Sign actions.",
                    required=False,
                    default="",
                    rows=5,
                    displayOptions={
                        "show": {
                            "crypto_type": "asymmetric",
                            "rsa_key_source": "provide"
                        }
                    }
                ),
                NodeProperty(
                    name="public_key",
                    displayName="Public Key (PEM)",
                    type=NodePropertyType.TEXT_AREA,
                    description="RSA Public Key in PEM format. Required for Encrypt and Verify actions.",
                    required=False,
                    default="",
                    rows=5,
                    displayOptions={
                        "show": {
                            "crypto_type": "asymmetric",
                            "rsa_key_source": "provide"
                        }
                    }
                ),
                NodeProperty(
                    name="signature",
                    displayName="Signature (Base64)",
                    type=NodePropertyType.TEXT_AREA,
                    description="The digital signature to verify. Required for Verify action.",
                    required=False,
                    default="",
                    rows=3,
                    displayOptions={
                        "show": {
                            "action": "verify"
                        }
                    }
                ),
                NodeProperty(
                    name="key_size",
                    displayName="Key Size (Bits)",
                    type=NodePropertyType.SELECT,
                    description="Select the size of the RSA key to generate.",
                    required=False,
                    default="2048",
                    options=[
                        {"label": "2048 Bits (Standard)", "value": "2048"},
                        {"label": "4096 Bits (High Security)", "value": "4096"}
                    ],
                    displayOptions={
                        "show": {
                            "action": "generate",
                            "crypto_type": "asymmetric"
                        }
                    }
                ),
                NodeProperty(
                    name="key_length",
                    displayName="Key Length (Anahtar Uzunluğu)",
                    type=NodePropertyType.SELECT,
                    description="Select the bit length of the key to generate.",
                    required=False,
                    default="256-bit",
                    options=[
                        {"label": "128-bit (16 Bytes)", "value": "128-bit"},
                        {"label": "256-bit (32 Bytes)", "value": "256-bit"},
                        {"label": "512-bit (64 Bytes)", "value": "512-bit"}
                    ],
                    displayOptions={
                        "show": {
                            "action": "generate",
                            "crypto_type": "symmetric"
                        }
                    }
                ),
                NodeProperty(
                    name="symmetric_key_format",
                    displayName="Key Format",
                    type=NodePropertyType.SELECT,
                    description="Select the output format for the generated symmetric key.",
                    required=False,
                    default="base64",
                    options=[
                        {"label": "Base64 encoded", "value": "base64"},
                        {"label": "Hexadecimal (Hex)", "value": "hex"},
                        {"label": "URL-safe Base64", "value": "url-safe"}
                    ],
                    displayOptions={
                        "show": {
                            "action": "generate",
                            "crypto_type": "symmetric"
                        }
                    }
                ),
                NodeProperty(
                    name="text_input",
                    displayName="Text Input",
                    type=NodePropertyType.TEXT_AREA,
                    description="Provide a template or string to process. Supports Jinja variables (e.g. {{ start.input }}).",
                    required=False,
                    default="",
                    rows=6
                ),
            ],
        }

    def _derive_key_pbkdf2(self, passphrase: str, length: int = 32) -> bytes:
        """
        Derive a key of specified length from a string passphrase using PBKDF2.
        Ensures users can enter normal passphrases safely.
        """
        if not passphrase:
            raise ValueError("Passphrase cannot be empty.")
            
        # Standard salt for deterministic symmetric workflow key derivation
        salt = b'kai_flow_crypto_node_salt_2026'
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def _load_private_key(self, pem_str: str):
        """Parse RSA Private Key from PEM string."""
        try:
            return serialization.load_pem_private_key(
                pem_str.strip().encode('utf-8'),
                password=None,
                backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"Failed to load RSA Private Key: {str(e)}")

    def _load_public_key(self, pem_str: str):
        """Parse RSA Public Key from PEM string."""
        try:
            return serialization.load_pem_public_key(
                pem_str.strip().encode('utf-8'),
                backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"Failed to load RSA Public Key: {str(e)}")

    def _generate_rsa_key_pair(self) -> tuple[str, str]:
        """Generate a new 2048-bit RSA private and public key pair in PEM format."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return private_pem, public_pem

    # --- Symmetric Helper Methods ---
    def _encrypt_aes_gcm(self, plaintext: str, key: bytes) -> str:
        aesgcm = AESGCM(key)
        iv = os.urandom(12)
        ciphertext = aesgcm.encrypt(iv, plaintext.encode('utf-8'), None)
        return base64.b64encode(iv + ciphertext).decode('utf-8')

    def _decrypt_aes_gcm(self, encrypted_b64: str, key: bytes) -> str:
        data = base64.b64decode(encrypted_b64.strip())
        if len(data) < 12:
            raise ValueError("Encrypted data is too short for AES-GCM")
        iv = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(key)
        decrypted = aesgcm.decrypt(iv, ciphertext, None)
        return decrypted.decode('utf-8')

    def _encrypt_aes_cbc(self, plaintext: str, key: bytes) -> str:
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        padder = sym_padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode('utf-8')) + padder.finalize()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        return base64.b64encode(iv + ciphertext).decode('utf-8')

    def _decrypt_aes_cbc(self, encrypted_b64: str, key: bytes) -> str:
        data = base64.b64decode(encrypted_b64.strip())
        if len(data) < 16:
            raise ValueError("Encrypted data is too short for AES-CBC")
        iv = data[:16]
        ciphertext = data[16:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = sym_padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()
        return decrypted.decode('utf-8')

    def _encrypt_chacha20_poly1305(self, plaintext: str, key: bytes) -> str:
        chacha = ChaCha20Poly1305(key)
        nonce = os.urandom(12)
        ciphertext = chacha.encrypt(nonce, plaintext.encode('utf-8'), None)
        return base64.b64encode(nonce + ciphertext).decode('utf-8')

    def _decrypt_chacha20_poly1305(self, encrypted_b64: str, key: bytes) -> str:
        data = base64.b64decode(encrypted_b64.strip())
        if len(data) < 12:
            raise ValueError("Encrypted data is too short for ChaCha20-Poly1305")
        nonce = data[:12]
        ciphertext = data[12:]
        chacha = ChaCha20Poly1305(key)
        decrypted = chacha.decrypt(nonce, ciphertext, None)
        return decrypted.decode('utf-8')

    # --- Asymmetric Helper Methods ---
    def _encrypt_rsa_oaep(self, plaintext: str, public_key_pem: str) -> str:
        pub_key = self._load_public_key(public_key_pem)
        ciphertext = pub_key.encrypt(
            plaintext.encode('utf-8'),
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(ciphertext).decode('utf-8')

    def _decrypt_rsa_oaep(self, encrypted_b64: str, private_key_pem: str) -> str:
        priv_key = self._load_private_key(private_key_pem)
        ciphertext = base64.b64decode(encrypted_b64.strip())
        decrypted = priv_key.decrypt(
            ciphertext,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted.decode('utf-8')

    def _sign_rsa(self, plaintext: str, private_key_pem: str, hash_algo: str) -> str:
        priv_key = self._load_private_key(private_key_pem)
        chosen_hash = hashes.SHA512() if hash_algo == "sha512" else hashes.SHA256()
        signature = priv_key.sign(
            plaintext.encode('utf-8'),
            asym_padding.PSS(
                mgf=asym_padding.MGF1(chosen_hash),
                salt_length=asym_padding.PSS.MAX_LENGTH
            ),
            chosen_hash
        )
        return base64.b64encode(signature).decode('utf-8')

    def _verify_rsa(self, plaintext: str, signature_b64: str, public_key_pem: str, hash_algo: str) -> bool:
        pub_key = self._load_public_key(public_key_pem)
        chosen_hash = hashes.SHA512() if hash_algo == "sha512" else hashes.SHA256()
        try:
            signature = base64.b64decode(signature_b64.strip())
            pub_key.verify(
                signature,
                plaintext.encode('utf-8'),
                asym_padding.PSS(
                    mgf=asym_padding.MGF1(chosen_hash),
                    salt_length=asym_padding.PSS.MAX_LENGTH
                ),
                chosen_hash
            )
            return True
        except Exception:
            return False

    def _render_jinja_template(self, template_str: str, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> str:
        """Render Jinja2 template with inputs and connected nodes as execution context."""
        try:
            context = {}
            context.update(inputs)
            
            for node_name, node_output in connected_nodes.items():
                context[node_name] = node_output
                if isinstance(node_output, dict):
                    for k, v in node_output.items():
                        if k not in context:
                            context[k] = v

            def _tojson_unicode(value):
                return json.dumps(value, ensure_ascii=False, default=str)

            env = Environment()
            env.filters["tojson"] = _tojson_unicode
            
            processed = template_str.replace("${" + "{", "{{").replace("}}", "}}")
            template = env.from_string(processed)
            return template.render(**context)
        except Exception as e:
            logger.warning(f"[CryptographyNode] Jinja template rendering failed: {e}")
            return template_str

    def _extract_primary_input(self, input_data: Any) -> str:
        """Safely extract plain string or stringified JSON from incoming input types."""
        if input_data is None:
            return ""
            
        if hasattr(input_data, 'page_content'):
            return str(input_data.page_content)
            
        if isinstance(input_data, dict):
            if "output" in input_data:
                return self._extract_primary_input(input_data["output"])
            if "content" in input_data:
                return self._extract_primary_input(input_data["content"])
            try:
                return json.dumps(input_data, ensure_ascii=False)
            except Exception:
                return str(input_data)
                
        if isinstance(input_data, (list, tuple)):
            try:
                return json.dumps(input_data, ensure_ascii=False)
            except Exception:
                return str(input_data)
                
        return str(input_data)

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> Dict[str, Any]:
        """Execute encryption/decryption based on configuration properties."""
        logger.info("Executing CryptographyNode dynamically")

        # Resolve action (backward compatible with mode)
        action = (
            inputs.get("action")
            or inputs.get("mode")
            or getattr(self, "user_data", {}).get("action")
            or getattr(self, "user_data", {}).get("mode", "encrypt")
        )
        
        # Resolve crypto_type
        crypto_type = (
            inputs.get("crypto_type")
            or getattr(self, "user_data", {}).get("crypto_type", "symmetric")
        )
        
        # Resolve cipher (backward compatible with algorithm)
        cipher = (
            inputs.get("cipher")
            or getattr(self, "user_data", {}).get("cipher", None)
        )
        if not cipher:
            old_algo = (
                inputs.get("algorithm")
                or getattr(self, "user_data", {}).get("algorithm", None)
            )
            if old_algo == "aes":
                cipher = "fernet"
            elif old_algo == "base64":
                cipher = "base64"
            else:
                cipher = "aes-256-gcm"

        # Parameters
        key = inputs.get("key") or getattr(self, "user_data", {}).get("key", "")
        rsa_key_source = (
            inputs.get("rsa_key_source")
            or getattr(self, "user_data", {}).get("rsa_key_source", "provide")
        )
        private_key = (
            inputs.get("private_key")
            or getattr(self, "user_data", {}).get("private_key", "")
        )
        public_key = (
            inputs.get("public_key")
            or getattr(self, "user_data", {}).get("public_key", "")
        )
        signature = (
            inputs.get("signature")
            or getattr(self, "user_data", {}).get("signature", "")
        )
        text_input = (
            inputs.get("text_input")
            or getattr(self, "user_data", {}).get("text_input", "")
        )

        # New properties for Generate Key action
        key_size = inputs.get("key_size") or getattr(self, "user_data", {}).get("key_size", "2048")
        symmetric_key_format = inputs.get("symmetric_key_format") or getattr(self, "user_data", {}).get("symmetric_key_format", "base64")

        # Retrieve text to encrypt/decrypt/sign/verify (skipped for generate action)
        actual_value = ""
        if action != "generate":
            if text_input and str(text_input).strip():
                actual_value = self._render_jinja_template(str(text_input), inputs, connected_nodes)
            else:
                connected_input = connected_nodes.get("input_data")
                actual_value = self._extract_primary_input(connected_input)

            # Validation of input data
            if not actual_value or not str(actual_value).strip():
                logger.warning("CryptographyNode failed: Empty input data provided.")
                return {
                    "output": "",
                    "success": False,
                    "error": "Input data cannot be empty."
                }

        generated_priv = None
        generated_pub = None

        # Handle RSA Key Generation if requested
        if crypto_type == "asymmetric" and rsa_key_source == "auto-generate":
            if action in ("encrypt", "sign", "verify"):
                try:
                    generated_priv, generated_pub = self._generate_rsa_key_pair()
                    if action == "encrypt":
                        public_key = generated_pub
                    elif action == "sign":
                        private_key = generated_priv
                    elif action == "verify":
                        public_key = generated_pub
                except Exception as e:
                    return {
                        "output": "",
                        "success": False,
                        "error": f"Failed to auto-generate RSA keys: {str(e)}"
                    }

        try:
            processed_result = ""
            
            if action == "encrypt":
                if crypto_type == "symmetric":
                    if cipher == "base64":
                        processed_result = base64.b64encode(actual_value.encode('utf-8')).decode('utf-8')
                    else:
                        if not key:
                            raise ValueError(f"Secret Key is required for symmetric cipher: {cipher}")
                        
                        if cipher == "aes-256-gcm":
                            derived = self._derive_key_pbkdf2(key, 32)
                            processed_result = self._encrypt_aes_gcm(actual_value, derived)
                        elif cipher == "aes-128-gcm":
                            derived = self._derive_key_pbkdf2(key, 16)
                            processed_result = self._encrypt_aes_gcm(actual_value, derived)
                        elif cipher == "aes-256-cbc":
                            derived = self._derive_key_pbkdf2(key, 32)
                            processed_result = self._encrypt_aes_cbc(actual_value, derived)
                        elif cipher == "chacha20-poly1305":
                            derived = self._derive_key_pbkdf2(key, 32)
                            processed_result = self._encrypt_chacha20_poly1305(actual_value, derived)
                        elif cipher == "fernet":
                            salt = b'kai_flow_crypto_node_salt_2026'
                            kdf = PBKDF2HMAC(
                                algorithm=hashes.SHA256(),
                                length=32,
                                salt=salt,
                                iterations=100000,
                            )
                            derived = base64.urlsafe_b64encode(kdf.derive(key.encode('utf-8')))
                            f = Fernet(derived)
                            processed_result = f.encrypt(actual_value.encode('utf-8')).decode('utf-8')
                        else:
                            raise ValueError(f"Unsupported symmetric cipher: {cipher}")
                
                elif crypto_type == "asymmetric":
                    if not public_key:
                        raise ValueError("Public Key (PEM) is required for asymmetric encryption.")
                    processed_result = self._encrypt_rsa_oaep(actual_value, public_key)
                else:
                    raise ValueError(f"Unsupported cryptography type: {crypto_type}")

                response = {
                    "output": processed_result,
                    "success": True,
                    "error": None
                }
                if generated_priv and generated_pub:
                    response["private_key"] = generated_priv
                    response["public_key"] = generated_pub
                return response

            elif action == "decrypt":
                if crypto_type == "symmetric":
                    if cipher == "base64":
                        processed_result = base64.b64decode(actual_value.strip().encode('utf-8')).decode('utf-8')
                    else:
                        if not key:
                            raise ValueError(f"Secret Key is required for symmetric cipher: {cipher}")
                        
                        if cipher == "aes-256-gcm":
                            derived = self._derive_key_pbkdf2(key, 32)
                            processed_result = self._decrypt_aes_gcm(actual_value, derived)
                        elif cipher == "aes-128-gcm":
                            derived = self._derive_key_pbkdf2(key, 16)
                            processed_result = self._decrypt_aes_gcm(actual_value, derived)
                        elif cipher == "aes-256-cbc":
                            derived = self._derive_key_pbkdf2(key, 32)
                            processed_result = self._decrypt_aes_cbc(actual_value, derived)
                        elif cipher == "chacha20-poly1305":
                            derived = self._derive_key_pbkdf2(key, 32)
                            processed_result = self._decrypt_chacha20_poly1305(actual_value, derived)
                        elif cipher == "fernet":
                            salt = b'kai_flow_crypto_node_salt_2026'
                            kdf = PBKDF2HMAC(
                                algorithm=hashes.SHA256(),
                                length=32,
                                salt=salt,
                                iterations=100000,
                            )
                            derived = base64.urlsafe_b64encode(kdf.derive(key.encode('utf-8')))
                            f = Fernet(derived)
                            processed_result = f.decrypt(actual_value.strip().encode('utf-8')).decode('utf-8')
                        else:
                            raise ValueError(f"Unsupported symmetric cipher: {cipher}")
                
                elif crypto_type == "asymmetric":
                    if not private_key:
                        raise ValueError("Private Key (PEM) is required for asymmetric decryption.")
                    processed_result = self._decrypt_rsa_oaep(actual_value, private_key)
                else:
                    raise ValueError(f"Unsupported cryptography type: {crypto_type}")

                # JSON parsing logic from original node
                try:
                    parsed_json = json.loads(processed_result)
                    if isinstance(parsed_json, dict):
                        result_dict = {
                            "output": parsed_json,
                            "success": True,
                            "error": None,
                            "raw_output": processed_result
                        }
                        for k, v in parsed_json.items():
                            if k not in result_dict:
                                result_dict[k] = v
                        return result_dict
                    elif isinstance(parsed_json, list):
                        return {
                            "output": parsed_json,
                            "success": True,
                            "error": None,
                            "raw_output": processed_result
                        }
                except json.JSONDecodeError:
                    pass
                
                return {
                    "output": processed_result,
                    "success": True,
                    "error": None
                }

            elif action == "sign":
                if crypto_type != "asymmetric":
                    raise ValueError("Sign action is only supported for asymmetric cryptography.")
                if not private_key:
                    raise ValueError("Private Key (PEM) is required for digital signature creation.")
                
                hash_algo = "sha512" if cipher == "rsa-sha512" else "sha256"
                processed_result = self._sign_rsa(actual_value, private_key, hash_algo)
                
                response = {
                    "output": processed_result,
                    "success": True,
                    "error": None
                }
                if generated_priv and generated_pub:
                    response["private_key"] = generated_priv
                    response["public_key"] = generated_pub
                return response

            elif action == "verify":
                if crypto_type != "asymmetric":
                    raise ValueError("Verify action is only supported for asymmetric cryptography.")
                if not public_key:
                    raise ValueError("Public Key (PEM) is required for digital signature verification.")
                if not signature:
                    raise ValueError("Signature (Base64) is required for verification.")
                
                hash_algo = "sha512" if cipher == "rsa-sha512" else "sha256"
                verified = self._verify_rsa(actual_value, signature, public_key, hash_algo)
                
                response = {
                    "output": verified,
                    "verified": verified,
                    "success": True,
                    "error": None
                }
                if generated_priv and generated_pub:
                    response["private_key"] = generated_priv
                    response["public_key"] = generated_pub
                return response

            elif action == "generate":
                if crypto_type == "symmetric":
                    # Resolve key length
                    key_length_str = inputs.get("key_length") or getattr(self, "user_data", {}).get("key_length", "256-bit")
                    
                    if key_length_str == "128-bit":
                        nbytes = 16
                    elif key_length_str == "512-bit":
                        nbytes = 64
                    else:  # "256-bit"
                        nbytes = 32
                        
                    # Resolve format
                    fmt = inputs.get("symmetric_key_format") or getattr(self, "user_data", {}).get("symmetric_key_format", "base64")
                    
                    if fmt == "hex":
                        processed_result = secrets.token_hex(nbytes)
                    elif fmt == "url-safe":
                        processed_result = secrets.token_urlsafe(nbytes)
                    else:  # base64
                        processed_result = base64.b64encode(secrets.token_bytes(nbytes)).decode('utf-8')
                    
                    return {
                        "output": processed_result,
                        "success": True,
                        "error": None
                    }
                elif crypto_type == "asymmetric":
                    # Parse RSA key size
                    try:
                        bits = int(key_size)
                    except ValueError:
                        bits = 2048
                        
                    # Generate RSA key pair
                    private_key_obj = rsa.generate_private_key(
                        public_exponent=65537,
                        key_size=bits,
                        backend=default_backend()
                    )
                    public_key_obj = private_key_obj.public_key()
                    
                    private_pem = private_key_obj.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    ).decode('utf-8')
                    
                    public_pem = public_key_obj.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    ).decode('utf-8')
                    
                    return {
                        "output": private_pem,
                        "private_key": private_pem,
                        "public_key": public_pem,
                        "success": True,
                        "error": None
                    }
                else:
                    raise ValueError(f"Unsupported cryptography type for key generation: {crypto_type}")

            else:
                raise ValueError(f"Unsupported action: {action}")

        except Exception as e:
            logger.error(f"CryptographyNode execution failed: {e}")
            return {
                "output": "",
                "success": False,
                "error": f"Cryptographic operation failed: {str(e)}"
            }