# Adding another language

The module can contain multiple language bundles and selects one from the Android system locale at runtime.

## 1. Create a bundle

Example for German:

```powershell
python tools/scaffold_language.py de-DE `
  --display-name Deutsch `
  --match-tag de-DE `
  --match-tag de
```

This creates `translation/locales/de-DE/` and registers it in `translation/languages.json`.

Locale tags are matched exactly after converting underscores to hyphens and lowercasing. Add every intended fallback explicitly. For example, `pt-BR` does not automatically match `pt` unless both tags are listed.

## 2. Translate catalogue targets

Fill the `target` column in `p0.csv` and `p1.csv`.

Do not change:

- `key`, `source_type` or `source_hr`;
- format placeholders such as `%1$s`;
- Activity names or view IDs;
- numbers, currencies, dates, GB/MB values, minutes or product identifiers unless the UI wording requires a safe rearrangement.

Blank targets are allowed. A blank target leaves the original text unchanged.

## 3. Translate aliases and patterns

- Fill `target` in `aliases.json`.
- Fill `replacement` in `patterns.json`.
- Keep each regular expression, Activity and view ID unchanged.
- Preserve capture references such as `$1`, `$2` and `$3`.

## 4. Maintain the glossary

Use `glossary.csv` to record preferred terminology, forbidden alternatives and product-name handling.

## 5. Generate and validate

```powershell
python MojA1Zh/tools/generate_translations.py
python tools/audit_public_repo.py
```

The generator requires every bundle to have the same rule structure and rejects conflicting exact translations, changed placeholders, unknown resources, invalid regular expressions and missing capture groups.

## 6. Test safely

- Test with the intended Android system locale.
- Confirm an unsupported locale leaves Moj A1 unchanged.
- Do not submit purchases, login attempts, voucher codes or account changes during translation testing.
- Verify amounts, numbers and user-entered text remain unchanged.

