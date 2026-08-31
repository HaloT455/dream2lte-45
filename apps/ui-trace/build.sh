#!/usr/bin/env bash
set -euo pipefail
app_dir=$(cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(cd -- "$app_dir/../.." && pwd)
trace_sdk=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}
test -n "$trace_sdk"
build_tools="$trace_sdk/build-tools/35.0.0"
android_jar="$trace_sdk/platforms/android-35/android.jar"
out="$app_dir/out"
mkdir -p "$out/gen" "$out/classes" "$out/dex" "$out/assets" "$out/test"
cp "$repo_dir/scripts/collect_ui_perfetto.sh" "$out/assets/collect_ui_perfetto.sh"
cp "$app_dir/assets/ui-perfetto.pbtxt" "$out/assets/ui-perfetto.pbtxt"
javac --release 8 -d "$out/test" "$app_dir/src/vn/alice/uitrace/SafeFiles.java" "$app_dir/src/vn/alice/uitrace/TraceArchive.java" "$app_dir/tests/SafeFilesTest.java" "$app_dir/tests/TraceArchiveTest.java"
java -ea -cp "$out/test" vn.alice.uitrace.SafeFilesTest
java -ea -Xmx32m -cp "$out/test" vn.alice.uitrace.TraceArchiveTest
"$build_tools/aapt2" compile --dir "$app_dir/res" -o "$out/resources.zip"
"$build_tools/aapt2" link -o "$out/base.apk" -I "$android_jar" --manifest "$app_dir/AndroidManifest.xml" \
    --java "$out/gen" -A "$out/assets" "$out/resources.zip"
find "$app_dir/src" "$out/gen" -name '*.java' -print > "$out/sources.txt"
javac --release 8 -encoding UTF-8 -classpath "$android_jar" -d "$out/classes" @"$out/sources.txt"
jar cf "$out/classes.jar" -C "$out/classes" .
"$build_tools/d8" --release --min-api 26 --lib "$android_jar" --output "$out/dex" "$out/classes.jar"
zip -j "$out/base.apk" "$out/dex/classes.dex"
"$build_tools/zipalign" -f -p 4 "$out/base.apk" "$out/aligned.apk"
# Per-build diagnostic signing key: never upload the private key or password.
export TRACE_KEY_PASSWORD
TRACE_KEY_PASSWORD=$(openssl rand -hex 24)
keytool -genkeypair -keystore "$out/signing.p12" -storetype PKCS12 \
    -storepass:env TRACE_KEY_PASSWORD -keypass:env TRACE_KEY_PASSWORD \
    -alias ui-trace -keyalg RSA -keysize 3072 -validity 3650 \
    -dname 'CN=ALice UI Trace Diagnostic' -noprompt
"$build_tools/apksigner" sign --ks "$out/signing.p12" --ks-key-alias ui-trace \
    --ks-pass env:TRACE_KEY_PASSWORD --key-pass env:TRACE_KEY_PASSWORD \
    --out "$out/ALice-UI-Trace-1.1.apk" "$out/aligned.apk"
"$build_tools/apksigner" verify --verbose --print-certs "$out/ALice-UI-Trace-1.1.apk" > "$out/apk-verification.txt"
"$build_tools/aapt2" dump badging "$out/ALice-UI-Trace-1.1.apk" >> "$out/apk-verification.txt"
"$build_tools/zipalign" -c -p 4 "$out/ALice-UI-Trace-1.1.apk"
grep -q "package: name='vn.alice.uitrace' versionCode='2'" "$out/apk-verification.txt"
! grep -q 'INTERNET\|MANAGE_EXTERNAL_STORAGE\|REQUEST_INSTALL_PACKAGES\|RECEIVE_BOOT_COMPLETED\|application-debuggable' "$out/apk-verification.txt"
cd "$out"
sha256sum ALice-UI-Trace-1.1.apk > SHA256SUMS
