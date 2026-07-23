# Compatibility and safety model

## Application gate

The current release activates only for package/process `hr.infinum.mojvip`, Moj A1 versionCode `7010000`, and a Chinese system language. If any gate fails, the module leaves the application unchanged.

## Translation layers

1. Android resource entry-name replacement.
2. Exact local-source fallback.
3. Server text replacement requiring full source, Activity and view ID.
4. Full-match regular expressions for narrowly defined dynamic values.

Any exception is fail-open and retains the original text.

## Protected content

- `EditText` values are never replaced.
- Unknown text is never translated.
- Numbers and dynamic account values are captured and reinserted unchanged.
- Network traffic, authentication and application data are not modified.
- WebView DOM content is not injected in the current release.

