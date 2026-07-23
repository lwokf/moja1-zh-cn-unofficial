# Contributing

Contributions to translations, compatibility rules and documentation are welcome.

## Translation rules

- Preserve amounts, phone numbers, dates, currency codes, GB/MB values, minutes and product identifiers.
- Do not add fuzzy matching or unrestricted machine translation.
- Server-delivered text must use complete-source matching plus an exact Activity and view resource entry name.
- Dynamic values must use a full-match regular expression with narrowly defined capture groups.
- Do not translate legal text without explicit human review.
- Do not add rules that trigger, automate or bypass purchases, authentication or account actions.

## Privacy

Never commit official APKs, decompiled application assets, account screenshots/XML, LSPosed databases, full device logs, signing keys, passwords, tokens or API keys.

Run the public-repository audit before submitting a pull request:

```powershell
python tools/audit_public_repo.py
```

