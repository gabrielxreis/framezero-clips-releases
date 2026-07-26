#!/bin/bash
set -u
trap 'RC=$?; if [ "$RC" -ne 0 ]; then echo; echo "[ERRO] A instalação encontrou um problema."; read -r -p "Pressione ENTER para fechar..." _; fi' EXIT

VERSION_URL="https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json"
TMP="${TMPDIR:-/tmp}/FrameZeroInstaller1125"
MANIFEST="$TMP/version.json"
ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
APP="$ROOT/app"
SYSTEM_APP="/Applications/FrameZero Clips.app"
USER_APP="$HOME/Applications/FrameZero Clips.app"
mkdir -p "$TMP"
ARCH="$(uname -m 2>/dev/null || echo unknown)"
[ "$ARCH" = "arm64" ] && ENGINE="mlx-whisper" || ENGINE="faster-whisper"
[ "$ARCH" = "arm64" ] && PLATFORM="Apple Silicon" || PLATFORM="Intel"

header(){ clear; cat <<EOF
============================================================
          FrameZero Clips Installer 1.1.25 - macOS
============================================================
 Mac detectado: $PLATFORM ($ARCH)
 Motor local: $ENGINE
============================================================
EOF
}

json_value(){
  KEY="$1"
  if command -v plutil >/dev/null 2>&1; then
    plutil -extract "$KEY" raw -o - "$MANIFEST" 2>/dev/null && return 0
  fi
  /usr/bin/awk -v key="\"$KEY\"" '$0 ~ key {sub(/^[^:]*:[[:space:]]*/,""); gsub(/[\",]/,""); print; exit}' "$MANIFEST"
}

load(){
  curl -fL "$VERSION_URL?cb=$(date +%s)" -o "$MANIFEST" || return 1
  MAC_URL="$(json_value mac_url)"
  LATEST="$(json_value latest_version)"
  NAME="$(json_value release_name)"
}

patch_all_scripts_native(){
  DIR="$1"
  COUNT=0
  while IFS= read -r -d '' FILE; do
    if grep -qiE 'exige Mac Apple Silicon|requires Apple Silicon|M1/M2/M3/M4' "$FILE" 2>/dev/null; then
      cp "$FILE" "$FILE.framezero-backup"
      /usr/bin/perl -0777 -i -pe 's/if\s+[^\n]*(?:uname\s+-m|ARCH|MACHINE_ARCH|x86_64|arm64)[^\n]*\n(?:(?!\nfi\b).)*?(?:exige Mac Apple Silicon|requires Apple Silicon|M1\/M2\/M3\/M4).*?\nfi/echo "OK: Mac Intel autorizado pelo instalador universal."/gis' "$FILE"
      /usr/bin/perl -i -pe 'if (/exige Mac Apple Silicon|requires Apple Silicon|M1\/M2\/M3\/M4/i) { $_="echo \"OK: Mac Intel autorizado pelo instalador universal.\"\n" }' "$FILE"
      chmod +x "$FILE" 2>/dev/null || true
      COUNT=$((COUNT + 1))
    fi
  done < <(find "$DIR" -type f \( -name '*.command' -o -name '*.sh' -o -name '*.bash' \) -print0)
  echo "Scripts corrigidos: $COUNT"
  if grep -RniE 'exige Mac Apple Silicon|requires Apple Silicon|M1/M2/M3/M4' "$DIR" --include='*.command' --include='*.sh' --include='*.bash' 2>/dev/null; then
    echo "[ERRO] Ainda existe uma trava Apple Silicon no pacote extraído."
    return 1
  fi
  echo "[OK] Todas as travas Apple Silicon foram removidas sem usar Python."
}

find_python3(){
  for P in /usr/local/bin/python3 /opt/homebrew/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 "$(command -v python3 2>/dev/null || true)"; do
    [ -n "$P" ] && [ -x "$P" ] && { echo "$P"; return 0; }
  done
  return 1
}

ensure_python3(){
  find_python3 >/dev/null 2>&1 && return 0
  if command -v brew >/dev/null 2>&1; then
    echo "Instalando Python 3 para o motor local Intel..."
    brew install python || return 1
    find_python3 >/dev/null 2>&1 && return 0
  fi
  echo "[ERRO] Python 3 é necessário para instalar o faster-whisper no Mac Intel."
  return 1
}

prepare_intel(){
  [ "$ARCH" = "x86_64" ] || return 0
  ensure_python3 || return 1
  PY="$(find_python3)" || return 1
  rm -rf "$APP/venv"
  "$PY" -m venv "$APP/venv" || return 1
  "$APP/venv/bin/python" -m pip install --upgrade pip setuptools wheel || return 1
  "$APP/venv/bin/python" -m pip install "faster-whisper>=1.1,<2" "ctranslate2>=4,<5" || return 1
  if [ -f "$APP/config.json" ]; then
    "$PY" - "$APP/config.json" <<'PY'
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

find_launcher(){
  for L in \
    "$ROOT/INICIAR.command" \
    "$ROOT/FrameZero Clips.command" \
    "$ROOT/iniciar.command" \
    "$ROOT/start.command"; do
    [ -f "$L" ] && { echo "$L"; return 0; }
  done
  return 1
}

create_app_shortcut(){
  LAUNCHER="$(find_launcher)" || { echo "[ERRO] Launcher do FrameZero não foi encontrado em $ROOT"; return 1; }
  chmod +x "$LAUNCHER" 2>/dev/null || true

  APP_TARGET="$SYSTEM_APP"
  if ! sudo -n true 2>/dev/null; then
    sudo -v || APP_TARGET="$USER_APP"
  fi

  BUILD="$TMP/FrameZero Clips.app"
  rm -rf "$BUILD"
  mkdir -p "$BUILD/Contents/MacOS" "$BUILD/Contents/Resources"

  cat > "$BUILD/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>FrameZero Clips</string>
<key>CFBundleDisplayName</key><string>FrameZero Clips</string>
<key>CFBundleIdentifier</key><string>br.com.framezero.clips</string>
<key>CFBundleVersion</key><string>1.1.25</string>
<key>CFBundleShortVersionString</key><string>1.1.25</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleExecutable</key><string>FrameZero Clips</string>
<key>LSMinimumSystemVersion</key><string>10.15</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST

  cat > "$BUILD/Contents/MacOS/FrameZero Clips" <<EOF
#!/bin/bash
LAUNCHER="$LAUNCHER"
chmod +x "\$LAUNCHER" 2>/dev/null || true
xattr -d com.apple.quarantine "\$LAUNCHER" 2>/dev/null || true
exec /bin/bash "\$LAUNCHER"
EOF
  chmod +x "$BUILD/Contents/MacOS/FrameZero Clips"
  xattr -dr com.apple.quarantine "$BUILD" 2>/dev/null || true
  codesign --force --deep --sign - "$BUILD" >/dev/null 2>&1 || true

  if [ "$APP_TARGET" = "$SYSTEM_APP" ]; then
    sudo rm -rf "$SYSTEM_APP"
    sudo cp -R "$BUILD" "$SYSTEM_APP"
    sudo chown -R root:wheel "$SYSTEM_APP" 2>/dev/null || true
  else
    mkdir -p "$HOME/Applications"
    rm -rf "$USER_APP"
    cp -R "$BUILD" "$USER_APP"
  fi

  echo "[OK] Atalho criado em: $APP_TARGET"
  printf '%s' "$APP_TARGET"
}

launch_after_install(){
  APP_PATH="$1"
  echo "Iniciando FrameZero Clips..."
  if [ -d "$APP_PATH" ]; then
    open "$APP_PATH" && return 0
  fi
  LAUNCHER="$(find_launcher)" || return 1
  nohup /bin/bash "$LAUNCHER" > "$TMP/framezero-start.log" 2>&1 &
  disown 2>/dev/null || true
}

install(){
  ZIP="$TMP/clips.zip"
  DIR="$TMP/package"
  rm -rf "$DIR"
  mkdir -p "$DIR"
  echo "Baixando pacote FrameZero Clips..."
  curl -fL "$MAC_URL?cb=$(date +%s)" -o "$ZIP" || return 1
  unzip -q -o "$ZIP" -d "$DIR" || return 1
  [ "$ARCH" = "x86_64" ] && patch_all_scripts_native "$DIR" || true

  SCRIPT="$(find "$DIR" -type f -iname '*clips*.command' | head -n1)"
  [ -n "$SCRIPT" ] || SCRIPT="$(find "$DIR" -type f -name '*.command' | head -n1)"
  [ -n "$SCRIPT" ] || { echo "[ERRO] Instalador interno não encontrado."; return 1; }

  chmod +x "$SCRIPT"
  xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true
  FRAMEZERO_MAC_ARCH="$ARCH" FRAMEZERO_TRANSCRIPTION_ENGINE="$ENGINE" FRAMEZERO_INSTALL_WITH_NATIONS=0 FRAMEZERO_AUTO_INSTALL=clean bash "$SCRIPT" || return 1
  prepare_intel || return 1
  APP_PATH="$(create_app_shortcut)" || return 1
  launch_after_install "$APP_PATH" || { echo "[AVISO] Instalado, mas não foi possível abrir automaticamente."; return 1; }
  echo "[OK] FrameZero Clips instalado e iniciado para $PLATFORM."
}

load || true
while true; do
  header
  echo "Versão disponível: ${LATEST:-?} - ${NAME:-?}"
  echo
  echo "[1] Instalar ou atualizar FrameZero Clips"
  echo "[2] Abrir FrameZero Clips"
  echo "[3] Verificar atualizações"
  echo "[4] Desinstalar FrameZero Clips"
  echo "[5] Sair"
  read -r -p "Opção: " OP
  case "$OP" in
    1) install; read -r -p "Pressione ENTER..." _ ;;
    2) [ -d "$SYSTEM_APP" ] && open "$SYSTEM_APP" || { [ -d "$USER_APP" ] && open "$USER_APP"; } || { L="$(find_launcher)" && /bin/bash "$L"; } ;;
    3) load ;;
    4) read -r -p "Digite APAGAR: " C; if [ "$(echo "$C"|tr '[:lower:]' '[:upper:]')" = "APAGAR" ]; then rm -rf "$ROOT" "$HOME/Library/Application Support/FrameZero"* "$HOME/Library/Caches/FrameZero"* "$HOME/Library/Logs/FrameZero"* "$USER_APP" 2>/dev/null || true; sudo rm -rf "$SYSTEM_APP" 2>/dev/null || true; fi ;;
    5) exit 0 ;;
  esac
done
