import hashlib
import os
from Crypto.Cipher import AES as _AES_pycrypto
from Crypto.Protocol.KDF import PBKDF2 as _PBKDF2_pycrypto
from Crypto.Random import get_random_bytes as _urandom

def _derive_key_impl(password_bytes: bytes, salt: bytes, key_size: int, iterations: int) -> bytes:
    return _PBKDF2_pycrypto(password_bytes, salt, dkLen=key_size, count=iterations)

def _aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes):
    """Returns (ciphertext, tag)."""
    cipher = _AES_pycrypto.new(key, _AES_pycrypto.MODE_GCM, nonce=nonce)
    return cipher.encrypt_and_digest(plaintext)

def _aes_gcm_decrypt(key: bytes, nonce: bytes, tag: bytes, ciphertext: bytes) -> bytes:
    cipher = _AES_pycrypto.new(key, _AES_pycrypto.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)

# constants
PBKDF2_ITERATIONS = 200_000
SALT_SIZE   = 16   
KEY_SIZE    = 32   
NONCE_SIZE  = 16   
TAG_SIZE    = 16   
SHA256_SIZE = 32 

class Encrypt:

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        return _derive_key_impl(password.encode(), salt, KEY_SIZE, PBKDF2_ITERATIONS)


    @staticmethod
    def encrypt_data(data: bytes, password: str) -> bytes:
        salt  = _urandom(SALT_SIZE)
        nonce = _urandom(NONCE_SIZE)
        key   = Encrypt._derive_key(password, salt)

        digest    = hashlib.sha256(data).digest()
        plaintext = digest + data

        ciphertext, tag = _aes_gcm_encrypt(key, nonce, plaintext)

        return salt + nonce + tag + ciphertext

    @staticmethod
    def decrypt_data(blob: bytes, password: str) -> bytes:
        header_len = SALT_SIZE + NONCE_SIZE + TAG_SIZE
        if len(blob) < header_len + SHA256_SIZE:
            raise ValueError("Ciphertext blob too short to be valid.")

        salt       = blob[:SALT_SIZE]
        nonce      = blob[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
        tag        = blob[SALT_SIZE + NONCE_SIZE : header_len]
        ciphertext = blob[header_len:]
        key = Encrypt._derive_key(password, salt)

        try:
            plaintext = _aes_gcm_decrypt(key, nonce, tag, ciphertext)
        except (ValueError, Exception) as exc:
            raise ValueError(
                "Decryption failed: incorrect password or corrupted data."
            ) from exc

        stored_digest = plaintext[:SHA256_SIZE]
        payload       = plaintext[SHA256_SIZE:]
        actual_digest = hashlib.sha256(payload).digest()

        if stored_digest != actual_digest:
            raise ValueError(
                "Integrity check failed: SHA-256 digest mismatch. "
                "The recovered data may be corrupted."
            )

        return payload

    @staticmethod
    def encrypt_text(text: str, password: str) -> bytes:
        return Encrypt.encrypt_data(text.encode(), password)

    @staticmethod
    def decrypt_text(blob: bytes, password: str) -> str:
        return Encrypt.decrypt_data(blob, password).decode()