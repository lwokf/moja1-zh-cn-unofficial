#!/data/data/com.termux/files/usr/bin/sh
set -eu

PREFIX=/data/data/com.termux/files/usr
HOME=/data/data/com.termux/files/home
PATH="$PREFIX/bin:/system/bin"
TMPDIR="$PREFIX/tmp"
export PREFIX HOME PATH TMPDIR

case "$PWD" in
    "$HOME"/moja1zh-build-*) ;;
    *) echo "Refusing to build outside a dedicated moja1zh-build-* directory" >&2; exit 2 ;;
esac

rm -rf build
mkdir -p build/stubs build/classes

find stubs -name '*.java' -type f | sort > build/stub-sources.txt
find src generated/src -name '*.java' -type f | sort > build/module-sources.txt

ecj -encoding UTF-8 -source 1.7 -target 1.7 -proc:none \
    -d build/stubs @build/stub-sources.txt

ecj -encoding UTF-8 -source 1.7 -target 1.7 -proc:none \
    -cp "build/stubs:$PREFIX/share/java/android.jar" \
    -d build/classes @build/module-sources.txt

dx --dex --min-sdk-version=24 --output=build/classes.dex build/classes

aapt package -f \
    -M AndroidManifest.xml \
    -S res \
    -A assets \
    -I /system/framework/framework-res.apk \
    -F build/MojA1Zh-unsigned.apk

cd build
aapt add MojA1Zh-unsigned.apk classes.dex
sha256sum MojA1Zh-unsigned.apk
