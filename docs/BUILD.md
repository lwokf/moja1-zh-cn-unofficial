# Build instructions

## Generate translation data

Requirements: Python 3.10 or newer. No original Moj A1 APK is required; the minimal resource inventory is included in `MojA1Zh/config/resource_inventory.csv`.

From the repository root:

```powershell
python MojA1Zh/tools/generate_translations.py
```

The generator validates catalogue columns, duplicate keys, format placeholders, resource names, source values, server contexts and regular expressions, then writes `MojA1Zh/generated/src/io/github/moja1zh/TranslationData.java`.

## Build the APK in Termux

The tested build environment provides ECJ, DX, AAPT and Android framework resources. Copy the repository to a dedicated Termux home directory whose name starts with `moja1zh-build-`, then run:

```sh
cd ~/moja1zh-build-YYYYMMDD-HHMMSS/MojA1Zh
sh build-termux.sh
```

The unsigned APK is created at `MojA1Zh/build/MojA1Zh-unsigned.apk`.

## Local signing

The signing helper requires Python and the `cryptography` package:

```powershell
python MojA1Zh/tools/sign_v1.py `
  MojA1Zh/build/MojA1Zh-unsigned.apk `
  MojA1Zh/build/MojA1Zh-local.apk
```

If no key pair exists, the helper creates one under `MojA1Zh/signing/`. These files are ignored by Git and must remain private. Locally signed builds cannot update the official project release unless they use the same private key.

Release APKs are signed offline by the maintainer. The private release key is not stored in this repository or GitHub Actions.

