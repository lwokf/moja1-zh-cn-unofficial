# Language bundles

`languages.json` declares the locale bundles compiled into the module. Runtime selection uses exact, normalized BCP 47 tags from each bundle's `match_tags` list; there is no implicit language fallback.

Each locale directory contains:

- `p0.csv` and `p1.csv`: resource and exact server translations;
- `aliases.json`: confirmed exact-source aliases and their translations;
- `patterns.json`: strict full-match dynamic templates and localized replacements;
- `glossary.csv`: terminology guidance for contributors.

The structural fields, source text, Activity and view ID must remain identical across languages. Target fields may be blank while a language is incomplete; blank rules retain the original application text.

See [docs/ADDING_LANGUAGE.md](../docs/ADDING_LANGUAGE.md).

