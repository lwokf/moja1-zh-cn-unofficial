#!/usr/bin/env python3
"""Validate localization catalogues and generate deterministic Java data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

FORMAT_TOKEN = re.compile(r"%(?:\d+\$)?[-#+ 0,(<]*\d*(?:\.\d+)?(?:[tT])?[a-zA-Z%]")
REQUIRED_COLUMNS = {
    "priority", "source_type", "key", "source_hr", "target_zh_CN", "match_policy"
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def digest_many(paths: list[Path]) -> str:
    value = hashlib.sha256()
    for path in paths:
        value.update(path.name.encode("utf-8"))
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    return value.hexdigest().upper()


def java_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def placeholders(value: str) -> Counter[str]:
    return Counter(token for token in FORMAT_TOKEN.findall(value) if token != "%%")


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns: {sorted(missing)}")
        return list(reader)


def generate(catalogues: list[Path], inventory: Path, config_path: Path, output: Path) -> None:
    rows = [row for catalogue in catalogues for row in load_csv(catalogue)]
    config = json.loads(config_path.read_text(encoding="utf-8"))

    if not rows:
        raise ValueError("Localization catalogues are empty")
    if any(row["priority"] not in {"P0", "P1"} for row in rows):
        raise ValueError("Only P0 and P1 rows may be compiled into this module")

    keys = [row["key"] for row in rows]
    duplicate_keys = [key for key, count in Counter(keys).items() if count > 1]
    if duplicate_keys:
        raise ValueError(f"Duplicate keys: {duplicate_keys}")

    for row in rows:
        if row["source_type"] not in {"android_resource", "server_exact"}:
            raise ValueError(f"Unsupported source_type for {row['key']}: {row['source_type']}")
        if placeholders(row["source_hr"]) != placeholders(row["target_zh_CN"]):
            raise ValueError(f"Format placeholders changed in {row['key']}")

    source_targets: dict[str, str] = {}
    for row in rows:
        old = source_targets.setdefault(row["source_hr"], row["target_zh_CN"])
        if old != row["target_zh_CN"]:
            raise ValueError(f"Conflicting exact translations for: {row['source_hr']!r}")

    with inventory.open("r", encoding="utf-8-sig", newline="") as handle:
        inventory_rows = list(csv.DictReader(handle))
    inventory_map = {row["resource_name"]: row["value"] for row in inventory_rows}

    resource_rows = [row for row in rows if row["source_type"] == "android_resource"]
    for row in resource_rows:
        actual = inventory_map.get(row["key"])
        if actual is None:
            raise ValueError(f"Resource key not found in APK inventory: {row['key']}")
        if actual != row["source_hr"]:
            raise ValueError(
                f"Resource source mismatch for {row['key']}: catalogue={row['source_hr']!r}, APK={actual!r}"
            )

    server_rows = [row for row in rows if row["source_type"] == "server_exact"]
    server_context = config["server_context"]
    inline_context_keys = {
        row["key"] for row in server_rows if row.get("activity") and row.get("view_id")
    }
    configured_context_keys = {row["key"] for row in server_rows} - inline_context_keys
    if set(server_context) != configured_context_keys:
        raise ValueError(
            "Server context keys differ from catalogue: "
            f"missing={sorted(configured_context_keys - set(server_context))}, "
            f"extra={sorted(set(server_context) - configured_context_keys)}"
        )

    resource_rules = [row for row in resource_rows if row["source_hr"] != row["target_zh_CN"]]
    local_rules = [row for row in resource_rows if row["source_hr"] != row["target_zh_CN"]]

    compiled_server: list[tuple[str, str, str, str, str]] = []
    compiled_context: dict[str, dict[str, str]] = {}
    server_by_key = {row["key"]: row for row in server_rows}
    for row in server_rows:
        if row.get("activity") and row.get("view_id"):
            context = {"activity": row["activity"], "view_id": row["view_id"]}
        else:
            context = server_context[row["key"]]
        compiled_context[row["key"]] = context
        compiled_server.append(
            (row["key"], row["source_hr"], row["target_zh_CN"], context["activity"], context["view_id"])
        )

    for alias in config.get("server_exact_aliases", []):
        base_key = alias["base_key"]
        if base_key not in server_by_key:
            raise ValueError(f"Alias base key is unknown: {base_key}")
        context = compiled_context[base_key]
        if placeholders(alias["source"]) != placeholders(alias["target"]):
            raise ValueError(f"Format placeholders changed in alias {alias['rule_id']}")
        compiled_server.append(
            (
                alias["rule_id"],
                alias["source"],
                alias["target"],
                alias.get("activity", context["activity"]),
                alias.get("view_id", context["view_id"]),
            )
        )

    compiled_patterns: list[tuple[str, str, str, str, str]] = []
    for rule in config.get("server_pattern_rules", []):
        re.compile(rule["pattern"])
        compiled_patterns.append(
            (
                rule["rule_id"],
                rule["pattern"],
                rule["replacement"],
                rule["activity"],
                rule["view_id"],
            )
        )

    all_rule_ids = keys + [row[0] for row in compiled_server[len(server_rows):]] + [row[0] for row in compiled_patterns]
    duplicate_rule_ids = [key for key, count in Counter(all_rule_ids).items() if count > 1]
    if duplicate_rule_ids:
        raise ValueError(f"Duplicate compiled rule ids: {duplicate_rule_ids}")

    def emit_rows(values: list[tuple[str, ...]]) -> str:
        return "\n".join(
            "        {" + ", ".join(java_string(item) for item in value) + "}," for value in values
        )

    resource_values = [(row["key"], row["key"], row["target_zh_CN"]) for row in resource_rules]
    local_values = [(row["key"], row["source_hr"], row["target_zh_CN"]) for row in local_rules]
    languages = ", ".join(java_string(value) for value in config["enabled_languages"])

    java = f'''// Generated by tools/generate_translations.py. Do not edit manually.
package io.github.moja1zh;

final class TranslationData {{
    static final String TARGET_PACKAGE = {java_string(config["target_package"])};
    static final String TARGET_PROCESS = {java_string(config["target_process"])};
    static final int TARGET_VERSION_CODE = {int(config["target_version_code"])};
    static final String[] ENABLED_LANGUAGES = new String[] {{{languages}}};
    static final String CATALOGUE_SHA256 = {java_string(digest_many(catalogues))};
    static final String CONFIG_SHA256 = {java_string(digest(config_path))};

    // rule id, Android resource entry name, translated text
    static final String[][] RESOURCE_RULES = new String[][] {{
{emit_rows(resource_values)}
    }};

    // rule id, exact local source text, translated text
    static final String[][] LOCAL_EXACT_RULES = new String[][] {{
{emit_rows(local_values)}
    }};

    // rule id, exact server source, translated text, Activity, view resource entry name
    static final String[][] SERVER_EXACT_RULES = new String[][] {{
{emit_rows(compiled_server)}
    }};

    // rule id, full-match regex, replacement, Activity, view resource entry name
    static final String[][] SERVER_PATTERN_RULES = new String[][] {{
{emit_rows(compiled_patterns)}
    }};

    private TranslationData() {{}}
}}
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(java, encoding="utf-8", newline="\n")
    print(
        f"Generated {output}: catalogue={len(rows)}, resources={len(resource_values)}, "
        f"local_exact={len(local_values)}, server_exact={len(compiled_server)}, "
        f"server_pattern={len(compiled_patterns)}"
    )


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    workspace = project.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalogue", action="append", type=Path)
    parser.add_argument("--inventory", type=Path, default=project / "config" / "resource_inventory.csv")
    parser.add_argument("--config", type=Path, default=project / "config" / "runtime_rules.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=project / "generated" / "src" / "io" / "github" / "moja1zh" / "TranslationData.java",
    )
    args = parser.parse_args()
    catalogues = args.catalogue or [
        workspace / "translation" / "p0_zh-CN.csv",
        workspace / "translation" / "p1_zh-CN.csv",
    ]
    generate(
        [path.resolve() for path in catalogues],
        args.inventory.resolve(),
        args.config.resolve(),
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
