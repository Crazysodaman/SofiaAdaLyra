"""Pinned public-key helpers for authenticated fleet TLS."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization

def public_key_fingerprint_from_der_certificate(certificate_der:bytes)->str:
    if not isinstance(certificate_der,(bytes,bytearray)) or not certificate_der:
        raise ValueError("certificate DER bytes required")
    cert=x509.load_der_x509_certificate(bytes(certificate_der))
    public_key=cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return sha256(public_key).hexdigest()

def public_key_fingerprint_from_pem_certificate(path:Path|str)->str:
    cert=x509.load_pem_x509_certificate(Path(path).read_bytes())
    public_key=cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return sha256(public_key).hexdigest()
