#!/usr/bin/env bash
# Gera o APK da Coleta de Campo sem Gradle: aapt2 (ou aapt) + javac + d8 (ou dx) + apksigner.
# Uso:  JAVA_HOME=<jdk 11+> KEYSTORE=<.jks> KSPASS=<senha> bash android/build.sh
# Requer: Android SDK (build-tools + uma plataforma android-23 ou superior) e um JDK com javac.
# Funciona no Git Bash do Windows (SDK do Android Studio) e no Linux (SDK oficial ou pacotes
# aapt, dalvik-exchange, zipalign, apksigner e android-sdk-platform-23 do Ubuntu).
# O keystore NÃO fica no repositório: KEYSTORE e KSPASS vêm do ambiente.
set -euo pipefail
cd "$(dirname "$0")"
SDK="${ANDROID_HOME:-${LOCALAPPDATA:-/usr/lib}/Android/Sdk}"
[ -d "$SDK" ] || SDK=/usr/lib/android-sdk
BT="${BUILD_TOOLS:-$(ls -d "$SDK"/build-tools/* 2>/dev/null | sort -V | tail -1)}"
PLAT="${PLATFORM:-$(ls -d "$SDK"/platforms/android-* 2>/dev/null | sort -V | tail -1)}"
AJAR="$PLAT/android.jar"
JB="${JAVA_HOME:+$JAVA_HOME/bin/}"
EXE=""; BAT=""; case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) EXE=".exe"; BAT=".bat";; esac
ferr() { for c in "$@"; do if [ -x "$BT/$c" ]; then echo "$BT/$c"; return; fi; command -v "${c%.*}" 2>/dev/null && return; done; return 1; }
AAPT2=$(ferr "aapt2$EXE" || true); AAPT=$(ferr "aapt$EXE" || true)
D8=$(ferr "d8$BAT" || true); DX=$(ferr "dx$BAT" dalvik-exchange || true)
ZIPALIGN=$(ferr "zipalign$EXE"); APKSIGNER=$(ferr "apksigner$BAT")
: "${KEYSTORE:?defina KEYSTORE}"; : "${KSPASS:?defina KSPASS}"
VC="${VERSION_CODE:-1}"; VN="${VERSION_NAME:-1.0}"
OUT=build; rm -rf $OUT; mkdir -p $OUT/compiled $OUT/classes $OUT/assets
echo "SDK: $SDK | plataforma: $(basename "$PLAT") | versão $VN ($VC)"

cp ../index.html $OUT/assets/index.html          # única fonte da coleta
sed -i "s/const VERSAO = \"[^\"]*\"/const VERSAO = \"$VN\"/" $OUT/assets/index.html
if [ -n "$AAPT2" ]; then
  "$AAPT2" compile --dir res -o $OUT/compiled
  "$AAPT2" link -I "$AJAR" --manifest AndroidManifest.xml -A $OUT/assets \
    --min-sdk-version 24 --target-sdk-version 34 --version-code "$VC" --version-name "$VN" \
    $OUT/compiled/*.flat -o $OUT/base.apk
else
  "$AAPT" package -f -M AndroidManifest.xml -S res -A $OUT/assets -I "$AJAR" \
    --min-sdk-version 24 --target-sdk-version 34 --version-code "$VC" --version-name "$VN" -F $OUT/base.apk
fi
"${JB}javac$EXE" --release 8 -Xlint:-options -cp "$AJAR" -d $OUT/classes $(find src -name '*.java')
(cd $OUT/classes && "${JB}jar$EXE" cf ../classes.jar .)
if [ -n "$D8" ]; then "$D8" --release --lib "$AJAR" --output $OUT $OUT/classes.jar
else "$DX" --dex --output=$OUT/classes.dex $OUT/classes.jar; fi
python3 - <<PY 2>/dev/null || python - <<PY
import zipfile
z=zipfile.ZipFile("$OUT/base.apk","a"); z.write("$OUT/classes.dex","classes.dex"); z.close()
PY
import zipfile
z=zipfile.ZipFile("$OUT/base.apk","a"); z.write("$OUT/classes.dex","classes.dex"); z.close()
PY
"$ZIPALIGN" -f -p 4 $OUT/base.apk $OUT/aligned.apk
"$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass env:KSPASS --out "${APK_OUT:-$OUT/coleta-de-campo.apk}" $OUT/aligned.apk
"$APKSIGNER" verify --print-certs "${APK_OUT:-$OUT/coleta-de-campo.apk}" | head -3
