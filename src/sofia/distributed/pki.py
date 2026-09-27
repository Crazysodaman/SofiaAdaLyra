"""Operator-only PKI provisioning for pinned mutual-TLS Fleet links.

This module creates local private keys and certificates. It never uploads,
logs, or returns private-key material. The CA private key must remain under
operator control and must not be copied to Fleet nodes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Iterable

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .tls import public_key_fingerprint_from_pem_certificate


def _write_private_key(path: Path, key) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _write_certificate(path: Path, certificate: x509.Certificate) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))


def _name(common_name: str) -> x509.Name:
    value = common_name.strip()
    if not value:
        raise ValueError("common name required")
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, value)])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serial() -> int:
    return x509.random_serial_number()


def _refuse_network_secret_root(root: Path) -> None:
    text = str(root)
    if text.startswith("\\\\"):
        raise ValueError(
            "Fleet PKI private material must be generated on local storage, not a UNC/network path"
        )


def create_ca(
    *,
    certificate_path: Path,
    private_key_path: Path,
    common_name: str = "Sofia Ada Lyra Fleet CA",
    days: int = 3650,
) -> None:
    if days < 1:
        raise ValueError("days must be positive")
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    now = _utcnow()
    subject = _name(common_name)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(_serial())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    _write_private_key(private_key_path, key)
    _write_certificate(certificate_path, certificate)


def _load_ca(certificate_path: Path, private_key_path: Path):
    certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())
    key = serialization.load_pem_private_key(
        private_key_path.read_bytes(),
        password=None,
    )
    if not isinstance(key, rsa.RSAPrivateKey):
        raise TypeError("Fleet CA key must be RSA")
    public = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    cert_public = certificate.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if public != cert_public:
        raise ValueError("Fleet CA certificate and private key do not match")
    basic = certificate.extensions.get_extension_for_class(
        x509.BasicConstraints
    ).value
    if not basic.ca:
        raise ValueError("Fleet CA certificate is not a CA")
    return certificate, key


def _sans(dns_names: Iterable[str], ip_addresses: Iterable[str]):
    values: list[x509.GeneralName] = []
    for raw in dns_names:
        value = raw.strip()
        if not value:
            raise ValueError("DNS SAN must not be empty")
        values.append(x509.DNSName(value))
    for raw in ip_addresses:
        values.append(x509.IPAddress(ip_address(raw.strip())))
    if not values:
        raise ValueError("at least one DNS or IP SAN is required")
    return x509.SubjectAlternativeName(values)


def issue_leaf(
    *,
    ca_certificate_path: Path,
    ca_private_key_path: Path,
    certificate_path: Path,
    private_key_path: Path,
    common_name: str,
    server: bool,
    dns_names: Iterable[str] = (),
    ip_addresses: Iterable[str] = (),
    days: int = 825,
) -> None:
    if days < 1:
        raise ValueError("days must be positive")
    ca_certificate, ca_key = _load_ca(
        ca_certificate_path,
        ca_private_key_path,
    )
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    now = _utcnow()
    eku = (
        ExtendedKeyUsageOID.SERVER_AUTH
        if server
        else ExtendedKeyUsageOID.CLIENT_AUTH
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(common_name))
        .issuer_name(ca_certificate.subject)
        .public_key(key.public_key())
        .serial_number(_serial())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([eku]), critical=False)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
    )
    if server:
        builder = builder.add_extension(
            _sans(dns_names, ip_addresses),
            critical=False,
        )
    certificate = builder.sign(ca_key, hashes.SHA256())
    _write_private_key(private_key_path, key)
    _write_certificate(certificate_path, certificate)


def bootstrap_pair(
    *,
    output_directory: Path,
    server_name: str,
    server_dns_names: Iterable[str],
    server_ip_addresses: Iterable[str] = (),
    controller_name: str = "Venus",
) -> dict[str, str]:
    root = output_directory.resolve()
    _refuse_network_secret_root(root)
    ca_dir = root / "ca"
    venus_dir = root / "venus"
    server_dir = root / server_name.casefold()

    ca_cert = ca_dir / "fleet-ca.pem"
    ca_key = ca_dir / "fleet-ca-key.pem"
    venus_cert = venus_dir / "venus-client.pem"
    venus_key = venus_dir / "venus-client-key.pem"
    server_cert = server_dir / f"{server_name.casefold()}-server.pem"
    server_key = server_dir / f"{server_name.casefold()}-server-key.pem"

    if any(
        path.exists()
        for path in (
            ca_cert,
            ca_key,
            venus_cert,
            venus_key,
            server_cert,
            server_key,
        )
    ):
        raise FileExistsError(
            "Fleet PKI output already exists; implicit key replacement is forbidden"
        )

    create_ca(
        certificate_path=ca_cert,
        private_key_path=ca_key,
    )
    issue_leaf(
        ca_certificate_path=ca_cert,
        ca_private_key_path=ca_key,
        certificate_path=venus_cert,
        private_key_path=venus_key,
        common_name=controller_name,
        server=False,
    )
    issue_leaf(
        ca_certificate_path=ca_cert,
        ca_private_key_path=ca_key,
        certificate_path=server_cert,
        private_key_path=server_key,
        common_name=server_name,
        server=True,
        dns_names=tuple(server_dns_names),
        ip_addresses=tuple(server_ip_addresses),
    )

    return {
        "ca_certificate": str(ca_cert),
        "ca_private_key": str(ca_key),
        "controller_certificate": str(venus_cert),
        "controller_private_key": str(venus_key),
        "controller_public_key_sha256": (
            public_key_fingerprint_from_pem_certificate(venus_cert)
        ),
        "server_certificate": str(server_cert),
        "server_private_key": str(server_key),
        "server_public_key_sha256": (
            public_key_fingerprint_from_pem_certificate(server_cert)
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.distributed.pki")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap-pair")
    bootstrap.add_argument("--output-dir", required=True)
    bootstrap.add_argument("--server-name", required=True)
    bootstrap.add_argument("--server-dns", action="append", default=[])
    bootstrap.add_argument("--server-ip", action="append", default=[])
    bootstrap.add_argument("--controller-name", default="Venus")

    fingerprint = sub.add_parser("fingerprint")
    fingerprint.add_argument("certificate")

    args = parser.parse_args(argv)

    try:
        if args.command == "fingerprint":
            print(public_key_fingerprint_from_pem_certificate(args.certificate))
            return 0

        dns_names = tuple(args.server_dns) or (args.server_name,)
        result = bootstrap_pair(
            output_directory=Path(args.output_dir),
            server_name=args.server_name,
            server_dns_names=dns_names,
            server_ip_addresses=tuple(args.server_ip),
            controller_name=args.controller_name,
        )
        for key in (
            "ca_certificate",
            "controller_certificate",
            "controller_private_key",
            "controller_public_key_sha256",
            "server_certificate",
            "server_private_key",
            "server_public_key_sha256",
        ):
            print(f"{key}={result[key]}")
        print(
            "ca_private_key=<kept locally; path intentionally not printed>",
        )
        return 0
    except Exception as exc:
        print(f"Fleet PKI provisioning failed: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
