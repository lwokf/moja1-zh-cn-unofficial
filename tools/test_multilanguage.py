#!/usr/bin/env python3
"""Smoke-test language scaffolding and partial-bundle generation."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="moja1-language-test-") as temp_value:
        temp = Path(temp_value)
        shutil.copytree(root / "translation", temp / "translation")
        (temp / "tools").mkdir()
        shutil.copy2(root / "tools" / "scaffold_language.py", temp / "tools")
        (temp / "MojA1Zh" / "tools").mkdir(parents=True)
        shutil.copy2(
            root / "MojA1Zh" / "tools" / "generate_translations.py",
            temp / "MojA1Zh" / "tools",
        )
        shutil.copytree(root / "MojA1Zh" / "config", temp / "MojA1Zh" / "config")

        subprocess.run(
            [
                sys.executable, str(temp / "tools" / "scaffold_language.py"), "fr-FR",
                "--display-name", "Français", "--match-tag", "fr-FR",
                "--match-tag", "fr",
            ],
            cwd=temp,
            check=True,
        )
        subprocess.run(
            [sys.executable, str(temp / "MojA1Zh" / "tools" / "generate_translations.py")],
            cwd=temp,
            check=True,
        )
        generated = (
            temp / "MojA1Zh" / "generated" / "src" / "io" / "github" / "moja1zh" /
            "TranslationData.java"
        ).read_text(encoding="utf-8")
        assert '{"fr-FR", "fr-fr"}' in generated
        assert '{"fr-FR", "fr"}' in generated
        assert generated.count('{"fr-FR",') == 2
    print("Multilanguage scaffold smoke test passed.")


if __name__ == "__main__":
    main()

