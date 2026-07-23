#!/usr/bin/env python3
"""Create a new, initially untranslated Moj A1 locale bundle."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

LANGUAGE_ID = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


def blank_catalogue(source: Path, target: Path) -> None:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    for row in rows:
        row["target"] = ""
        row["status"] = "todo"
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def blank_glossary(source: Path, target: Path) -> None:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    for row in rows:
        row["preferred_target"] = ""
        row["status"] = "todo"
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def blank_json(source: Path, target: Path, translated_field: str) -> None:
    rows = json.loads(source.read_text(encoding="utf-8"))
    for row in rows:
        row[translated_field] = ""
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    translation = root / "translation"
    manifest_path = translation / "languages.json"
    parser = argparse.ArgumentParser()
    parser.add_argument("language_id", help="BCP 47 bundle id, for example de-DE")
    parser.add_argument("--display-name")
    parser.add_argument("--match-tag", action="append", dest="match_tags")
    parser.add_argument("--reference", default="zh-CN")
    args = parser.parse_args()

    language_id = args.language_id
    if not LANGUAGE_ID.fullmatch(language_id):
        raise SystemExit(f"Invalid language id: {language_id}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if any(row["id"].lower() == language_id.lower() for row in manifest["languages"]):
        raise SystemExit(f"Language already exists: {language_id}")
    reference = next(
        (row for row in manifest["languages"] if row["id"] == args.reference), None
    )
    if reference is None:
        raise SystemExit(f"Reference language not found: {args.reference}")

    reference_dir = translation / "locales" / args.reference
    target_dir = translation / "locales" / language_id
    if target_dir.exists():
        raise SystemExit(f"Target directory already exists: {target_dir}")
    target_dir.mkdir(parents=True)

    blank_catalogue(reference_dir / "p0.csv", target_dir / "p0.csv")
    blank_catalogue(reference_dir / "p1.csv", target_dir / "p1.csv")
    blank_glossary(reference_dir / "glossary.csv", target_dir / "glossary.csv")
    blank_json(reference_dir / "aliases.json", target_dir / "aliases.json", "target")
    blank_json(reference_dir / "patterns.json", target_dir / "patterns.json", "replacement")

    match_tags = args.match_tags or [language_id]
    manifest["languages"].append({
        "id": language_id,
        "display_name": args.display_name or language_id,
        "match_tags": match_tags,
        "catalogues": [
            f"locales/{language_id}/p0.csv",
            f"locales/{language_id}/p1.csv",
        ],
        "aliases": f"locales/{language_id}/aliases.json",
        "patterns": f"locales/{language_id}/patterns.json",
        "glossary": f"locales/{language_id}/glossary.csv",
    })
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Created {target_dir}")
    print("Blank targets are allowed and will keep the original text.")
    print("Run: python MojA1Zh/tools/generate_translations.py")


if __name__ == "__main__":
    main()

