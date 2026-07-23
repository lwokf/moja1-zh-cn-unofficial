#!/usr/bin/env python3
"""Validate locale bundles and generate deterministic multilingual Java data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

FORMAT_TOKEN = re.compile(r"%(?:\d+\$)?[-#+ 0,(<]*\d*(?:\.\d+)?(?:[tT])?[a-zA-Z%]")
REPLACEMENT_GROUP = re.compile(r"\$(\d+)")
REQUIRED_COLUMNS = {
    "priority", "source_type", "key", "source_hr", "target", "match_policy"
}
STRUCTURE_COLUMNS = (
    "priority", "source_type", "source_hr", "match_policy", "activity", "view_id"
)


def normalized_bytes(path: Path) -> bytes:
    if path.suffix.lower() in {".csv", ".json", ".txt", ".md"}:
        text = path.read_text(encoding="utf-8-sig")
        return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return path.read_bytes()


def digest(path: Path) -> str:
    return hashlib.sha256(normalized_bytes(path)).hexdigest().upper()


def digest_many(paths: list[Path], root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted(set(paths), key=lambda item: item.resolve().as_posix()):
        try:
            label = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            label = path.name
        value.update(label.encode("utf-8"))
        value.update(b"\0")
        value.update(normalized_bytes(path))
        value.update(b"\0")
    return value.hexdigest().upper()


def java_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def placeholders(value: str) -> Counter[str]:
    return Counter(token for token in FORMAT_TOKEN.findall(value) if token != "%%")


def normalize_tag(value: str) -> str:
    return value.strip().replace("_", "-").lower()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns: {sorted(missing)}")
        return list(reader)


def load_json_list(path: Path) -> list[dict[str, str]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected a JSON list")
    return value


def row_structure(rows: list[dict[str, str]]) -> dict[str, tuple[str, ...]]:
    return {
        row["key"]: tuple(row.get(column, "") for column in STRUCTURE_COLUMNS)
        for row in rows
    }


def alias_structure(rows: list[dict[str, str]]) -> list[tuple[str, ...]]:
    return sorted(
        (
            row["rule_id"], row["base_key"], row["source"],
            row.get("activity", ""), row.get("view_id", ""),
        )
        for row in rows
    )


def pattern_structure(rows: list[dict[str, str]]) -> list[tuple[str, ...]]:
    return sorted(
        (
            row["rule_id"], row["pattern"], row["activity"], row["view_id"],
        )
        for row in rows
    )


def generate(
        language_manifest: Path,
        inventory: Path,
        config_path: Path,
        output: Path) -> None:
    manifest = json.loads(language_manifest.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    language_rows = manifest.get("languages")
    if not isinstance(language_rows, list) or not language_rows:
        raise ValueError("Language manifest must contain a non-empty languages list")

    with inventory.open("r", encoding="utf-8-sig", newline="") as handle:
        inventory_rows = list(csv.DictReader(handle))
    inventory_map = {row["resource_name"]: row["value"] for row in inventory_rows}

    root = language_manifest.resolve().parents[1]
    translation_root = language_manifest.resolve().parent
    input_paths = [language_manifest.resolve()]
    language_match_rules: list[tuple[str, str]] = []
    resource_values: list[tuple[str, str, str, str]] = []
    local_values: list[tuple[str, str, str, str]] = []
    server_values: list[tuple[str, str, str, str, str, str]] = []
    pattern_values: list[tuple[str, str, str, str, str, str]] = []
    language_ids: set[str] = set()
    tag_owners: dict[str, str] = {}
    baseline_rows: dict[str, tuple[str, ...]] | None = None
    baseline_aliases: list[tuple[str, ...]] | None = None
    baseline_patterns: list[tuple[str, ...]] | None = None
    totals: list[str] = []

    for language in language_rows:
        language_id = language["id"].strip()
        if not language_id or language_id in language_ids:
            raise ValueError(f"Invalid or duplicate language id: {language_id!r}")
        language_ids.add(language_id)

        tags = language.get("match_tags")
        if not isinstance(tags, list) or not tags:
            raise ValueError(f"{language_id}: match_tags must be a non-empty list")
        for tag in tags:
            normalized = normalize_tag(tag)
            if not normalized:
                raise ValueError(f"{language_id}: empty locale match tag")
            old_owner = tag_owners.get(normalized)
            if old_owner is not None:
                raise ValueError(
                    f"Locale tag {tag!r} is duplicated by {old_owner} and {language_id}"
                )
            tag_owners[normalized] = language_id
            language_match_rules.append((language_id, normalized))

        catalogue_paths = [
            (translation_root / value).resolve() for value in language.get("catalogues", [])
        ]
        if not catalogue_paths:
            raise ValueError(f"{language_id}: no catalogues configured")
        rows = [row for path in catalogue_paths for row in load_csv(path)]
        input_paths.extend(catalogue_paths)
        if not rows:
            raise ValueError(f"{language_id}: localization catalogues are empty")
        if any(row["priority"] not in {"P0", "P1"} for row in rows):
            raise ValueError(f"{language_id}: only P0 and P1 rows may be compiled")

        keys = [row["key"] for row in rows]
        duplicate_keys = [key for key, count in Counter(keys).items() if count > 1]
        if duplicate_keys:
            raise ValueError(f"{language_id}: duplicate keys: {duplicate_keys}")

        structure = row_structure(rows)
        if baseline_rows is None:
            baseline_rows = structure
        elif structure != baseline_rows:
            missing = sorted(set(baseline_rows) - set(structure))
            extra = sorted(set(structure) - set(baseline_rows))
            changed = sorted(
                key for key in set(structure).intersection(baseline_rows)
                if structure[key] != baseline_rows[key]
            )
            raise ValueError(
                f"{language_id}: catalogue structure differs: "
                f"missing={missing}, extra={extra}, changed={changed}"
            )

        for row in rows:
            if row["source_type"] not in {"android_resource", "server_exact"}:
                raise ValueError(
                    f"{language_id}: unsupported source_type for {row['key']}: "
                    f"{row['source_type']}"
                )
            target = row["target"]
            if target and placeholders(row["source_hr"]) != placeholders(target):
                raise ValueError(f"{language_id}: format placeholders changed in {row['key']}")

        source_targets: dict[str, str] = {}
        for row in rows:
            target = row["target"]
            if not target:
                continue
            old = source_targets.setdefault(row["source_hr"], target)
            if old != target:
                raise ValueError(
                    f"{language_id}: conflicting exact translations for {row['source_hr']!r}"
                )

        resource_rows = [row for row in rows if row["source_type"] == "android_resource"]
        for row in resource_rows:
            actual = inventory_map.get(row["key"])
            if actual is None:
                raise ValueError(f"Resource key not found in inventory: {row['key']}")
            if actual != row["source_hr"]:
                raise ValueError(
                    f"Resource mismatch for {row['key']}: "
                    f"catalogue={row['source_hr']!r}, inventory={actual!r}"
                )

        server_rows = [row for row in rows if row["source_type"] == "server_exact"]
        server_context = config["server_context"]
        inline_context_keys = {
            row["key"] for row in server_rows if row.get("activity") and row.get("view_id")
        }
        configured_context_keys = {row["key"] for row in server_rows} - inline_context_keys
        if set(server_context) != configured_context_keys:
            raise ValueError(
                f"{language_id}: server contexts differ: "
                f"missing={sorted(configured_context_keys - set(server_context))}, "
                f"extra={sorted(set(server_context) - configured_context_keys)}"
            )

        compiled_context: dict[str, dict[str, str]] = {}
        server_by_key = {row["key"]: row for row in server_rows}
        for row in resource_rows:
            target = row["target"]
            if target and row["source_hr"] != target:
                resource_values.append((language_id, row["key"], row["key"], target))
                local_values.append((language_id, row["key"], row["source_hr"], target))
        for row in server_rows:
            if row.get("activity") and row.get("view_id"):
                context = {"activity": row["activity"], "view_id": row["view_id"]}
            else:
                context = server_context[row["key"]]
            compiled_context[row["key"]] = context
            target = row["target"]
            if target and row["source_hr"] != target:
                server_values.append(
                    (
                        language_id, row["key"], row["source_hr"], target,
                        context["activity"], context["view_id"],
                    )
                )

        alias_path = (translation_root / language["aliases"]).resolve()
        aliases = load_json_list(alias_path)
        input_paths.append(alias_path)
        current_alias_structure = alias_structure(aliases)
        if baseline_aliases is None:
            baseline_aliases = current_alias_structure
        elif current_alias_structure != baseline_aliases:
            raise ValueError(f"{language_id}: alias structure differs from the first language")
        for alias in aliases:
            base_key = alias["base_key"]
            if base_key not in server_by_key:
                raise ValueError(f"{language_id}: alias base key is unknown: {base_key}")
            target = alias.get("target", "")
            if target and placeholders(alias["source"]) != placeholders(target):
                raise ValueError(
                    f"{language_id}: format placeholders changed in alias {alias['rule_id']}"
                )
            if not target or alias["source"] == target:
                continue
            old = source_targets.setdefault(alias["source"], target)
            if old != target:
                raise ValueError(
                    f"{language_id}: conflicting alias translation for {alias['source']!r}"
                )
            context = compiled_context[base_key]
            server_values.append(
                (
                    language_id, alias["rule_id"], alias["source"], target,
                    alias.get("activity", context["activity"]),
                    alias.get("view_id", context["view_id"]),
                )
            )

        pattern_path = (translation_root / language["patterns"]).resolve()
        patterns = load_json_list(pattern_path)
        input_paths.append(pattern_path)
        current_pattern_structure = pattern_structure(patterns)
        if baseline_patterns is None:
            baseline_patterns = current_pattern_structure
        elif current_pattern_structure != baseline_patterns:
            raise ValueError(f"{language_id}: pattern structure differs from the first language")
        for rule in patterns:
            compiled = re.compile(rule["pattern"])
            replacement = rule.get("replacement", "")
            referenced_groups = [int(value) for value in REPLACEMENT_GROUP.findall(replacement)]
            if referenced_groups and max(referenced_groups) > compiled.groups:
                raise ValueError(
                    f"{language_id}: replacement references a missing group in {rule['rule_id']}"
                )
            if not replacement:
                continue
            pattern_values.append(
                (
                    language_id, rule["rule_id"], rule["pattern"], replacement,
                    rule["activity"], rule["view_id"],
                )
            )

        all_rule_ids = (
            keys + [row["rule_id"] for row in aliases] + [row["rule_id"] for row in patterns]
        )
        duplicate_rule_ids = [
            key for key, count in Counter(all_rule_ids).items() if count > 1
        ]
        if duplicate_rule_ids:
            raise ValueError(f"{language_id}: duplicate rule ids: {duplicate_rule_ids}")

        totals.append(
            f"{language_id}: catalogue={len(rows)}, "
            f"translated={sum(bool(row['target']) for row in rows)}, "
            f"aliases={sum(bool(row.get('target')) for row in aliases)}, "
            f"patterns={sum(bool(row.get('replacement')) for row in patterns)}"
        )

    def emit_rows(values: list[tuple[str, ...]]) -> str:
        return "\n".join(
            "        {" + ", ".join(java_string(item) for item in value) + "},"
            for value in values
        )

    java = f'''// Generated by tools/generate_translations.py. Do not edit manually.
package io.github.moja1zh;

final class TranslationData {{
    static final String TARGET_PACKAGE = {java_string(config["target_package"])};
    static final String TARGET_PROCESS = {java_string(config["target_process"])};
    static final int TARGET_VERSION_CODE = {int(config["target_version_code"])};
    static final String CATALOGUE_SHA256 = {java_string(digest_many(input_paths, root))};
    static final String CONFIG_SHA256 = {java_string(digest(config_path))};

    // language bundle id, normalized Android locale tag
    static final String[][] LANGUAGE_MATCH_RULES = new String[][] {{
{emit_rows(language_match_rules)}
    }};

    // language, rule id, Android resource entry name, translated text
    static final String[][] RESOURCE_RULES = new String[][] {{
{emit_rows(resource_values)}
    }};

    // language, rule id, exact local source text, translated text
    static final String[][] LOCAL_EXACT_RULES = new String[][] {{
{emit_rows(local_values)}
    }};

    // language, rule id, exact server source, translated text, Activity, view entry name
    static final String[][] SERVER_EXACT_RULES = new String[][] {{
{emit_rows(server_values)}
    }};

    // language, rule id, full-match regex, replacement, Activity, view entry name
    static final String[][] SERVER_PATTERN_RULES = new String[][] {{
{emit_rows(pattern_values)}
    }};

    private TranslationData() {{}}
}}
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(java, encoding="utf-8", newline="\n")
    print(
        f"Generated {output}: languages={len(language_rows)}, "
        f"resources={len(resource_values)}, local_exact={len(local_values)}, "
        f"server_exact={len(server_values)}, server_pattern={len(pattern_values)}"
    )
    for value in totals:
        print(f"  {value}")


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    workspace = project.parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--languages", type=Path, default=workspace / "translation" / "languages.json"
    )
    parser.add_argument(
        "--inventory", type=Path, default=project / "config" / "resource_inventory.csv"
    )
    parser.add_argument(
        "--config", type=Path, default=project / "config" / "runtime_base.json"
    )
    parser.add_argument(
        "--output", type=Path,
        default=project / "generated" / "src" / "io" / "github" / "moja1zh" /
        "TranslationData.java",
    )
    args = parser.parse_args()
    generate(
        args.languages.resolve(), args.inventory.resolve(), args.config.resolve(),
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
