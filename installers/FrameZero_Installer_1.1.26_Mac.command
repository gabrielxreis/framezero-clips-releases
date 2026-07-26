#!/bin/bash
set -u
trap 'RC=$?; if [ "$RC" -ne 0 ]; then echo; echo "[ERRO] A instalação encontrou um problema."; read -r -p "Pressione ENTER para fechar..." _; fi' EXIT

VERSION_URL="https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json"
TMP_BASE="${TMPDIR:-/tmp}"
TMP="$TMP_BASE/FrameZeroInstaller1126"
MANIFEST="$TMP/version.json"
ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
APP="$ROOT/app"
SYSTEM_APP="/Applications/FrameZero Clips.app"
USER_APP="$HOME/Applications/FrameZero Clips.app"
ARCH="$(uname -m 2>/dev/null || echo unknown)"
[ "$ARCH" = "arm64" ] && ENGINE="mlx-whisper" || ENGINE="faster-whisper"
[ "$ARCH" = "arm64" ] && PLATFORM="Apple Silicon" || PLATFORM="Intel"

clean_installer_cache(){
  echo "Limpando cache e arquivos temporários de instalações anteriores..."
  rm -rf "$TMP_BASE/FrameZeroInstaller"* "$TMP_BASE/FrameZeroOnlineInstaller" "$TMP_BASE/framezero-installer-"* "$TMP_BASE/framezero-install-"* "$TMP_BASE/framezero-download-"* "$TMP_BASE/framezero-extract-"* "$TMP_BASE/framezero-run-"*.command "$TMP_BASE/FrameZero_Installer_"*.command "$HOME/Library/Caches/FrameZeroInstaller" "$HOME/Library/Caches/FrameZero Installer" "$HOME/Library/Caches/br.com.framezero.installer" 2>/dev/null || true
  mkdir -p "$TMP"
  echo "[OK] Cache do instalador limpo."
}

cleanup_current_download(){ rm -rf "$TMP/clips.zip" "$TMP/package" "$TMP/FrameZero Clips.app" "$TMP/FrameZeroIcon.iconset" 2>/dev/null || true; }

header(){ clear; cat <<EOF
============================================================
          FrameZero Clips Installer 1.1.26 - macOS
============================================================
 Mac detectado: $PLATFORM ($ARCH)
 Motor local: $ENGINE
============================================================
EOF
}

json_value(){ KEY="$1"; if command -v plutil >/dev/null 2>&1; then plutil -extract "$KEY" raw -o - "$MANIFEST" 2>/dev/null && return 0; fi; /usr/bin/awk -v key="\"$KEY\"" '$0 ~ key {sub(/^[^:]*:[[:space:]]*/,""); gsub(/[\",]/,""); print; exit}' "$MANIFEST"; }
load(){ rm -f "$MANIFEST" 2>/dev/null || true; curl -fL "$VERSION_URL?cb=$(date +%s)" -o "$MANIFEST" || return 1; MAC_URL="$(json_value mac_url)"; LATEST="$(json_value latest_version)"; NAME="$(json_value release_name)"; }

patch_all_scripts_native(){
  DIR="$1"; COUNT=0
  while IFS= read -r -d '' FILE; do
    if grep -qiE 'exige Mac Apple Silicon|requires Apple Silicon|M1/M2/M3/M4' "$FILE" 2>/dev/null; then
      /usr/bin/perl -0777 -i -pe 's/if\s+[^\n]*(?:uname\s+-m|ARCH|MACHINE_ARCH|x86_64|arm64)[^\n]*\n(?:(?!\nfi\b).)*?(?:exige Mac Apple Silicon|requires Apple Silicon|M1\/M2\/M3\/M4).*?\nfi/echo "OK: Mac Intel autorizado pelo instalador universal."/gis' "$FILE"
      /usr/bin/perl -i -pe 'if (/exige Mac Apple Silicon|requires Apple Silicon|M1\/M2\/M3\/M4/i) { $_="echo \"OK: Mac Intel autorizado pelo instalador universal.\"\n" }' "$FILE"
      chmod +x "$FILE" 2>/dev/null || true; COUNT=$((COUNT + 1))
    fi
  done < <(find "$DIR" -type f \( -name '*.command' -o -name '*.sh' -o -name '*.bash' \) -print0)
  echo "Scripts corrigidos: $COUNT"
  if grep -RniE 'exige Mac Apple Silicon|requires Apple Silicon|M1/M2/M3/M4' "$DIR" --include='*.command' --include='*.sh' --include='*.bash' 2>/dev/null; then echo "[ERRO] Ainda existe uma trava Apple Silicon no pacote extraído."; return 1; fi
  echo "[OK] Todas as travas Apple Silicon foram removidas."
}

find_python3(){ for P in /usr/local/bin/python3 /opt/homebrew/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 "$(command -v python3 2>/dev/null || true)"; do [ -n "$P" ] && [ -x "$P" ] && { echo "$P"; return 0; }; done; return 1; }
ensure_python3(){ find_python3 >/dev/null 2>&1 && return 0; if command -v brew >/dev/null 2>&1; then echo "Instalando Python 3 para o motor local Intel..."; brew install python || return 1; find_python3 >/dev/null 2>&1 && return 0; fi; echo "[ERRO] Python 3 é necessário para instalar o faster-whisper no Mac Intel."; return 1; }

prepare_intel(){
  [ "$ARCH" = "x86_64" ] || return 0
  ensure_python3 || return 1; PY="$(find_python3)" || return 1
  rm -rf "$APP/venv"; "$PY" -m venv "$APP/venv" || return 1
  "$APP/venv/bin/python" -m pip install --upgrade pip setuptools wheel || return 1
  "$APP/venv/bin/python" -m pip install "faster-whisper>=1.1,<2" "ctranslate2>=4,<5" || return 1
  if [ -f "$APP/config.json" ]; then "$PY" - "$APP/config.json" <<'PY'
import json,sys
p=sys.argv[1]
try:d=json.load(open(p,encoding='utf-8'))
except:d={}
d.update({'transcription_engine':'faster-whisper','transcricao_modo':'local','whisper_vps_url':'','whisper_vps_token':'','vps_fallback_local':False,'vps_enviar_audio_ao_vivo':False})
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
PY
  fi
  echo "[OK] faster-whisper local instalado para Mac Intel."
}

find_launcher(){ for L in "$ROOT/INICIAR.command" "$ROOT/FrameZero Clips.command" "$ROOT/iniciar.command" "$ROOT/start.command"; do [ -f "$L" ] && { echo "$L"; return 0; }; done; return 1; }

build_app_icon(){
  RES="$1"
  ICNS="$(find "$ROOT" -type f -iname '*.icns' 2>/dev/null | head -n1)"
  if [ -n "$ICNS" ] && [ -f "$ICNS" ]; then cp "$ICNS" "$RES/FrameZero.icns"; return 0; fi
  PNG="$(find "$ROOT" -type f \( -iname '*framezero*.png' -o -iname '*logo*.png' -o -iname '*icon*.png' \) 2>/dev/null | head -n1)"
  [ -n "$PNG" ] && [ -f "$PNG" ] || return 1
  ICONSET="$TMP/FrameZeroIcon.iconset"; rm -rf "$ICONSET"; mkdir -p "$ICONSET"
  for SPEC in '16 icon_16x16.png' '32 icon_16x16@2x.png' '32 icon_32x32.png' '64 icon_32x32@2x.png' '128 icon_128x128.png' '256 icon_128x128@2x.png' '256 icon_256x256.png' '512 icon_256x256@2x.png' '512 icon_512x512.png' '1024 icon_512x512@2x.png'; do
    SIZE="${SPEC%% *}"; NAME="${SPEC#* }"; sips -z "$SIZE" "$SIZE" "$PNG" --out "$ICONSET/$NAME" >/dev/null 2>&1 || true
  done
  iconutil -c icns "$ICONSET" -o "$RES/FrameZero.icns" >/dev/null 2>&1
}

create_app_shortcut(){
  LAUNCHER="$(find_launcher)" || { echo "[ERRO] Launcher do FrameZero não foi encontrado em $ROOT" >&2; return 1; }
  chmod +x "$LAUNCHER" 2>/dev/null || true
  APP_TARGET="$SYSTEM_APP"; sudo -v 2>/dev/null || APP_TARGET="$USER_APP"
  BUILD="$TMP/FrameZero Clips.app"; rm -rf "$BUILD"; mkdir -p "$BUILD/Contents/MacOS" "$BUILD/Contents/Resources"
  build_app_icon "$BUILD/Contents/Resources" || echo "[AVISO] Logo não encontrada; o app usará o ícone padrão." >&2
  cat > "$BUILD/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>FrameZero Clips</string>
<key>CFBundleDisplayName</key><string>FrameZero Clips</string>
<key>CFBundleIdentifier</key><string>br.com.framezero.clips</string>
<key>CFBundleVersion</key><string>1.1.26</string>
<key>CFBundleShortVersionString</key><string>1.1.26</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleExecutable</key><string>FrameZero Clips</string>
<key>CFBundleIconFile</key><string>FrameZero</string>
<key>LSMinimumSystemVersion</key><string>10.15</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
  cat > "$BUILD/Contents/MacOS/FrameZero Clips" <<EOF
#!/bin/bash
ROOT="$ROOT"
LAUNCHER="$LAUNCHER"
LOG_DIR="\$HOME/Library/Logs/FrameZero"
LOG="\$LOG_DIR/framezero-launch.log"
mkdir -p "\$LOG_DIR"
echo "==== FrameZero iniciado em \$(date) ====" >> "\$LOG"
chmod +x "\$LAUNCHER" 2>/dev/null || true
xattr -d com.apple.quarantine "\$LAUNCHER" 2>/dev/null || true
/bin/bash "\$LAUNCHER" >> "\$LOG" 2>&1 &
LAUNCH_PID=\$!
sleep 5
if kill -0 "\$LAUNCH_PID" 2>/dev/null; then
  while kill -0 "\$LAUNCH_PID" 2>/dev/null; do sleep 3; done
  exit 0
fi
if pgrep -f "\$ROOT|servidor.py|FrameZero" >/dev/null 2>&1; then
  while pgrep -f "\$ROOT|servidor.py|FrameZero" >/dev/null 2>&1; do sleep 5; done
  exit 0
fi
osascript -e 'display dialog "O FrameZero não conseguiu iniciar. O arquivo de diagnóstico será aberto." buttons {"OK"} default button "OK" with icon stop' >/dev/null 2>&1 || true
open "\$LOG" 2>/dev/null || true
exit 1
EOF
  chmod +x "$BUILD/Contents/MacOS/FrameZero Clips"; xattr -dr com.apple.quarantine "$BUILD" 2>/dev/null || true; codesign --force --deep --sign - "$BUILD" >/dev/null 2>&1 || true
  if [ "$APP_TARGET" = "$SYSTEM_APP" ]; then sudo rm -rf "$SYSTEM_APP"; sudo cp -R "$BUILD" "$SYSTEM_APP"; sudo touch "$SYSTEM_APP"; else mkdir -p "$HOME/Applications"; rm -rf "$USER_APP"; cp -R "$BUILD" "$USER_APP"; touch "$USER_APP"; fi
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_TARGET" >/dev/null 2>&1 || true
  killall Finder Dock >/dev/null 2>&1 || true
  echo "[OK] App criado com launcher persistente em: $APP_TARGET" >&2; printf '%s' "$APP_TARGET"
}

launch_after_install(){ APP_PATH="$1"; echo "Iniciando FrameZero Clips..."; [ -d "$APP_PATH" ] && open -n "$APP_PATH" && return 0; LAUNCHER="$(find_launcher)" || return 1; nohup /bin/bash "$LAUNCHER" > "$HOME/Library/Logs/FrameZero/framezero-launch.log" 2>&1 & }

install(){
  cleanup_current_download; ZIP="$TMP/clips.zip"; DIR="$TMP/package"; mkdir -p "$DIR"
  echo "Baixando pacote novo do FrameZero Clips..."; curl -fL "$MAC_URL?cb=$(date +%s)" -o "$ZIP" || return 1; unzip -q -o "$ZIP" -d "$DIR" || return 1
  [ "$ARCH" = "x86_64" ] && patch_all_scripts_native "$DIR" || true
  SCRIPT="$(find "$DIR" -type f -iname '*clips*.command' | head -n1)"; [ -n "$SCRIPT" ] || SCRIPT="$(find "$DIR" -type f -name '*.command' | head -n1)"; [ -n "$SCRIPT" ] || { echo "[ERRO] Instalador interno não encontrado."; return 1; }
  chmod +x "$SCRIPT"; xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true
  FRAMEZERO_MAC_ARCH="$ARCH" FRAMEZERO_TRANSCRIPTION_ENGINE="$ENGINE" FRAMEZERO_INSTALL_WITH_NATIONS=0 FRAMEZERO_AUTO_INSTALL=clean bash "$SCRIPT" || return 1
  prepare_intel || return 1; APP_PATH="$(create_app_shortcut)" || return 1; launch_after_install "$APP_PATH" || return 1; cleanup_current_download
  echo "[OK] FrameZero Clips instalado e iniciado para $PLATFORM."
}

clean_installer_cache; load || true
while true; do
  header; echo "Versão disponível: ${LATEST:-?} - ${NAME:-?}"; echo
  echo "[1] Instalar ou atualizar FrameZero Clips"; echo "[2] Abrir FrameZero Clips"; echo "[3] Verificar atualizações"; echo "[4] Limpar cache do instalador"; echo "[5] Desinstalar FrameZero Clips"; echo "[6] Sair"
  read -r -p "Opção: " OP
  case "$OP" in
    1) install; read -r -p "Pressione ENTER..." _ ;;
    2) [ -d "$SYSTEM_APP" ] && open -n "$SYSTEM_APP" || { [ -d "$USER_APP" ] && open -n "$USER_APP"; } || { L="$(find_launcher)" && /bin/bash "$L"; } ;;
    3) clean_installer_cache; load ;;
    4) clean_installer_cache; load; read -r -p "Cache limpo. Pressione ENTER..." _ ;;
    5) read -r -p "Digite APAGAR: " C; if [ "$(echo "$C"|tr '[:lower:]' '[:upper:]')" = "APAGAR" ]; then rm -rf "$ROOT" "$HOME/Library/Application Support/FrameZero"* "$HOME/Library/Caches/FrameZero"* "$HOME/Library/Logs/FrameZero"* "$USER_APP" 2>/dev/null || true; sudo rm -rf "$SYSTEM_APP" 2>/dev/null || true; fi ;;
    6) cleanup_current_download; exit 0 ;;
  esac
done
