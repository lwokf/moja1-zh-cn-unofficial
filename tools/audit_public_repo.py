#!/usr/bin/env python3
"""Fail when a prospective public repository contains known private artifacts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES = {".last-device-build-path", "base.apk", "modules_config.db", "modules_config.db-shm", "modules_config.db-wal", "moja1zh-key.pem"}
FORBIDDEN_PARTS = {"artifacts", "original", "p1-private", "p1-deep-private", "p1-localized-private", "lsposed-db"}
TEXT_PATTERNS = {
    "absolute Windows user path": re.compile(r"C:\\Users\\", re.IGNORECASE),
    "private Termux build path": re.compile(r"/data/data/com\.termux/files/home/moja1zh-build-"),
    "known test phone number": re.compile(r"091[\s-]?950[\s-]?4890"),
    "known device account identifier": re.compile("U149" + "263624"),
}
TEXT_SUFFIXES = {".csv", ".java", ".json", ".md", ".py", ".sh", ".txt", ".xml"}

def main() -> int:
    failures: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT)
        lower_parts = {part.lower() for part in relative.parts}
        if path.name.lower() in FORBIDDEN_NAMES:
            failures.append(f"forbidden filename: {relative}")
        if lower_parts.intersection(FORBIDDEN_PARTS):
            failures.append(f"forbidden private path: {relative}")
        if path.suffix.lower() in {".apk", ".aab", ".db", ".jks", ".keystore", ".p12"}:
            failures.append(f"forbidden binary/secret type: {relative}")
        if path.stat().st_size > 2 * 1024 * 1024:
            failures.append(f"unexpected file over 2 MiB: {relative}")
        if path.suffix.lower() in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for label, pattern in TEXT_PATTERNS.items():
                if pattern.search(text):
                    failures.append(f"{label}: {relative}")
    if failures:
        print("Public repository audit failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Public repository audit passed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
