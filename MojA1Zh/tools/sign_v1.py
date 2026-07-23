#!/usr/bin/env python3
"""Create a standard SHA-256/RSA JAR (APK v1) signature without Java."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import os
import tempfile
import zipfile
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

SIGNER_BASENAME = "MOJA1ZH"
MANIFEST_NAME = "META-INF/MANIFEST.MF"
SF_NAME = f"META-INF/{SIGNER_BASENAME}.SF"
RSA_NAME = f"META-INF/{SIGNER_BASENAME}.RSA"


def b64_sha256(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")


def fold_header(name: str, value: str) -> bytes:
    raw = f"{name}: {value}".encode("utf-8")
    lines: list[bytes] = []
    first = True
    while raw:
        limit = 70 if first else 69
        chunk, raw = raw[:limit], raw[limit:]
        lines.append((b"" if first else b" ") + chunk + b"\r\n")
        first = False
    return b"".join(lines)


def section(headers: list[tuple[str, str]]) -> bytes:
    return b"".join(fold_header(name, value) for name, value in headers) + b"\r\n"


def is_old_signature(name: str) -> bool:
    upper = name.upper()
    if upper == MANIFEST_NAME:
        return True
    if not upper.startswith("META-INF/"):
        return False
    leaf = upper[len("META-INF/"):]
    return "/" not in leaf and leaf.endswith((".SF", ".RSA", ".DSA", ".EC"))


def load_or_create_identity(key_path: Path, cert_path: Path):
    if key_path.exists() != cert_path.exists():
        raise ValueError("Signing key and certificate must either both exist or both be absent")

    if key_path.exists():
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        if key.public_key().public_numbers() != cert.public_key().public_numbers():
            raise ValueError("Signing key does not match certificate")
        return key, cert

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "MojA1Zh Local Module Signer"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MojA1Zh"),
    ])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, cert


def build_signature_files(entries: list[tuple[str, bytes]], key, cert):
    main = section([
        ("Manifest-Version", "1.0"),
        ("Created-By", "MojA1Zh Python Signer"),
    ])
    manifest_sections: list[tuple[str, bytes]] = []
    for name, data in sorted(entries, key=lambda item: item[0]):
        manifest_sections.append((name, section([
            ("Name", name),
            ("SHA-256-Digest", b64_sha256(data)),
        ])))
    manifest = main + b"".join(value for _, value in manifest_sections)

    sf_main = section([
        ("Signature-Version", "1.0"),
        ("Created-By", "MojA1Zh Python Signer"),
        ("SHA-256-Digest-Manifest", b64_sha256(manifest)),
        ("SHA-256-Digest-Manifest-Main-Attributes", b64_sha256(main)),
    ])
    sf_sections = [
        section([("Name", name), ("SHA-256-Digest", b64_sha256(value))])
        for name, value in manifest_sections
    ]
    signature_file = sf_main + b"".join(sf_sections)

    signature_block = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(signature_file)
        .add_signer(cert, key, hashes.SHA256())
        .sign(
            serialization.Encoding.DER,
            [
                pkcs7.PKCS7Options.DetachedSignature,
                pkcs7.PKCS7Options.Binary,
                # Android's legacy JarVerifier rejects OpenSSL's optional
                # SMIMECapabilities signed attribute.
                pkcs7.PKCS7Options.NoCapabilities,
            ],
        )
    )
    return manifest, signature_file, signature_block


def sign_apk(input_path: Path, output_path: Path, key_path: Path, cert_path: Path) -> None:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output APK paths must differ")
    key, cert = load_or_create_identity(key_path, cert_path)

    with zipfile.ZipFile(input_path, "r") as source:
        infos = [info for info in source.infolist() if not is_old_signature(info.filename)]
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("APK contains duplicate ZIP entry names")
        payloads = {info.filename: source.read(info.filename) for info in infos}

    signed_entries = [
        (info.filename, payloads[info.filename])
        for info in infos
        if not info.is_dir()
    ]
    manifest, signature_file, signature_block = build_signature_files(signed_entries, key, cert)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=output_path.name + ".", suffix=".tmp", dir=output_path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", allowZip64=True, strict_timestamps=False) as target:
            for name, data in (
                (MANIFEST_NAME, manifest),
                (SF_NAME, signature_file),
                (RSA_NAME, signature_block),
            ):
                info = zipfile.ZipInfo(name)
                info.date_time = (2026, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                target.writestr(info, data)
            for info in infos:
                target.writestr(info, payloads[info.filename])
        temp_path.replace(output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    with zipfile.ZipFile(output_path, "r") as signed:
        for required in (MANIFEST_NAME, SF_NAME, RSA_NAME, "AndroidManifest.xml", "classes.dex"):
            if required not in signed.namelist():
                raise ValueError(f"Signed APK is missing {required}")
    print(f"Signed: {output_path}")
    print(f"SHA-256: {hashlib.sha256(output_path.read_bytes()).hexdigest().upper()}")
    print(f"Certificate SHA-256: {cert.fingerprint(hashes.SHA256()).hex().upper()}")


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--key", type=Path, default=project / "signing" / "moja1zh-key.pem")
    parser.add_argument("--cert", type=Path, default=project / "signing" / "moja1zh-cert.pem")
    args = parser.parse_args()
    sign_apk(args.input.resolve(), args.output.resolve(), args.key.resolve(), args.cert.resolve())


if __name__ == "__main__":
    main()
