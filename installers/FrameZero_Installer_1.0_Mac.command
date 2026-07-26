#!/bin/bash
set -u

trap 'RC=$?; if [ "$RC" -ne 0 ]; then echo ""; echo "[ERRO] O instalador encontrou um problema."; read -r -p "Pressione ENTER para fechar..." _; fi' EXIT

CURRENT_INSTALLER_VERSION="1.1.20"
VERSION_URL="https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json"
TMP="${TMPDIR:-/tmp}/FrameZeroOnlineInstaller"
VERSION_FILE="$TMP/version.json"
INSTALL_ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
APP_DIR="$INSTALL_ROOT/app"
mkdir -p "$TMP"

ARCH="$(uname -m 2>/dev/null || echo unknown)"
case "$ARCH" in
  arm64) PLATFORM_NAME="Apple Silicon"; TRANSCRIPTION_ENGINE="mlx-whisper" ;;
  x86_64) PLATFORM_NAME="Intel"; TRANSCRIPTION_ENGINE="faster-whisper" ;;
  *) PLATFORM_NAME="$ARCH"; TRANSCRIPTION_ENGINE="faster-whisper" ;;
esac

brand_header() {
  clear
  cat <<TXT
============================================================
          FrameZero Clips Installer 1.1.20 - macOS
============================================================
 Mac detectado: $PLATFORM_NAME ($ARCH)
 Motor local: $TRANSCRIPTION_ENGINE
============================================================
TXT
}

pause_menu() {
  echo
  read -r -p "Pressione ENTER para voltar ao menu..." _
}

download_file() {
  URL="$1"
  OUT="$2"
  LABEL="$3"
  echo "$LABEL"
  curl -fL "$URL" -o "$OUT"
}

read_json() {
  KEY="$1"
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get(sys.argv[2],''))" "$VERSION_FILE" "$KEY" 2>/dev/null && return 0
  fi
  if command -v plutil >/dev/null 2>&1; then
    plutil -extract "$KEY" raw -o - "$VERSION_FILE" 2>/dev/null && return 0
  fi
  echo ""
}

load_manifest() {
  brand_header
  echo "Baixando informações da versão mais recente..."
  if ! download_file "$VERSION_URL" "$VERSION_FILE" "Consultando atualização..."; then
    echo "[ERRO] Não foi possível baixar o manifesto de versão."
    return 1
  fi
  LATEST_VERSION="$(read_json latest_version)"
  RELEASE_NAME="$(read_json release_name)"
  MAC_URL="$(read_json mac_url)"
  [ -n "$MAC_URL" ] || { echo "[ERRO] O manifesto não contém mac_url."; return 1; }
}

version_gt() {
  python3 - "$1" "$2" <<'PYV' 2>/dev/null || return 1
import sys
from itertools import zip_longest

def parts(v):
    return [int(x) if x.isdigit() else 0 for x in str(v).replace('v','').split('.')]
print('1' if parts(sys.argv[1]) > parts(sys.argv[2]) else '0')
PYV
}

self_update_if_needed() {
  [ "${FRAMEZERO_NO_SELF_UPDATE:-}" = "1" ] && return 0
  NEW_VER="$(read_json online_installer_version)"
  NEW_URL="$(read_json online_installer_mac_url)"
  [ -n "$NEW_VER" ] || return 0
  [ -n "$NEW_URL" ] || return 0
  IS_GT="$(version_gt "$NEW_VER" "$CURRENT_INSTALLER_VERSION")"
  if [ "$IS_GT" = "1" ]; then
    echo "Atualização do instalador encontrada: $NEW_VER"
    NEW_SCRIPT="$TMP/FrameZero_Installer_${NEW_VER}_Mac.command"
    if curl -fL "$NEW_URL" -o "$NEW_SCRIPT"; then
      chmod +x "$NEW_SCRIPT" 2>/dev/null || true
      xattr -d com.apple.quarantine "$NEW_SCRIPT" 2>/dev/null || true
      FRAMEZERO_NO_SELF_UPDATE=1 exec bash "$NEW_SCRIPT"
    fi
  fi
}

find_python3() {
  for PY in \
    /usr/local/bin/python3 \
    /opt/homebrew/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
    "$(command -v python3 2>/dev/null || true)"; do
    [ -n "$PY" ] && [ -x "$PY" ] && { echo "$PY"; return 0; }
  done
  return 1
}

install_python_if_needed() {
  if find_python3 >/dev/null 2>&1; then return 0; fi
  echo "Python 3 não encontrado. Tentando instalar pelo Homebrew..."
  if ! command -v brew >/dev/null 2>&1; then
    echo "[ERRO] Instale o Python 3 antes de continuar."
    echo "Acesse python.org e instale uma versão compatível com seu Mac."
    return 1
  fi
  brew install python || return 1
}

patch_local_configuration() {
  PY="$(find_python3)" || return 1
  CONFIG="$APP_DIR/config.json"
  [ -f "$CONFIG" ] || return 0
  "$PY" - "$CONFIG" "$TRANSCRIPTION_ENGINE" <<'PY'
import json, sys
path, engine = sys.argv[1], sys.argv[2]
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception:
    data = {}
data['transcription_engine'] = engine
data['transcricao_modo'] = 'local'
data['whisper_backend_status'] = 'enabled'
data['whisper_vps_url'] = ''
data['whisper_vps_token'] = ''
data['vps_fallback_local'] = False
data['vps_enviar_audio_ao_vivo'] = False
with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
PY
}

prepare_intel_backend() {
  [ "$ARCH" = "x86_64" ] || return 0
  echo
  echo "Preparando transcrição local para Mac Intel..."
  install_python_if_needed || return 1
  PY="$(find_python3)" || return 1
  VENV="$APP_DIR/venv"
  REQ="$APP_DIR/requirements.txt"
  FILTERED_REQ="$TMP/requirements-intel.txt"

  rm -rf "$VENV"
  "$PY" -m venv "$VENV" || return 1
  VPY="$VENV/bin/python"
  "$VPY" -m pip install --upgrade pip setuptools wheel || return 1

  if [ -f "$REQ" ]; then
    grep -Eiv '(^|[-_])(mlx|mlx-whisper|apple-metal)([-_=<> ]|$)' "$REQ" > "$FILTERED_REQ" || true
    if [ -s "$FILTERED_REQ" ]; then
      "$VPY" -m pip install -r "$FILTERED_REQ" || return 1
    fi
  fi

  "$VPY" -m pip install "faster-whisper>=1.1,<2" "ctranslate2>=4,<5" || return 1

  find "$APP_DIR" -type f \( -name '*.py' -o -name '*.json' -o -name '*.command' -o -name '*.sh' \) -print0 2>/dev/null | while IFS= read -r -d '' FILE; do
    "$PY" - "$FILE" <<'PY' 2>/dev/null || true
import sys
p=sys.argv[1]
try:
    raw=open(p,'r',encoding='utf-8').read()
except Exception:
    raise SystemExit
new=raw.replace('mlx-whisper','faster-whisper').replace('mlx_whisper','faster_whisper')
if new != raw:
    open(p,'w',encoding='utf-8').write(new)
PY
  done

  patch_local_configuration || return 1
  echo "[OK] Backend local Intel preparado com faster-whisper."
}

prepare_apple_silicon_backend() {
  [ "$ARCH" = "arm64" ] || return 0
  patch_local_configuration || true
  echo "[OK] Apple Silicon usará MLX Whisper local."
}

download_and_run_clips() {
  ZIPPATH="$TMP/framezero-clips.zip"
  EXTRACT="$TMP/framezero-clips-extract"
  rm -rf "$EXTRACT"
  mkdir -p "$EXTRACT"

  download_file "$MAC_URL" "$ZIPPATH" "Baixando FrameZero Clips ${LATEST_VERSION:-}..." || return 1
  echo "Extraindo pacote..."
  unzip -q -o "$ZIPPATH" -d "$EXTRACT" || return 1

  SCRIPT="$(find "$EXTRACT" -type f -name '*FRAMEZERO*CLIPS*.command' | head -n 1)"
  [ -n "$SCRIPT" ] || SCRIPT="$(find "$EXTRACT" -type f -name '*.command' | head -n 1)"
  [ -n "$SCRIPT" ] || { echo "[ERRO] Instalador interno não encontrado."; return 1; }

  chmod +x "$SCRIPT" 2>/dev/null || true
  xattr -dr com.apple.quarantine "$EXTRACT" 2>/dev/null || true

  echo "Executando instalador para $PLATFORM_NAME..."
  FRAMEZERO_MAC_ARCH="$ARCH" \
  FRAMEZERO_TRANSCRIPTION_ENGINE="$TRANSCRIPTION_ENGINE" \
  FRAMEZERO_INSTALL_WITH_NATIONS=0 \
  FRAMEZERO_AUTO_INSTALL=clean \
  bash "$SCRIPT" || return 1

  prepare_intel_backend || return 1
  prepare_apple_silicon_backend || return 1
  echo
  echo "[OK] FrameZero Clips instalado para $PLATFORM_NAME."
}

launch_clips() {
  LAUNCHER="$INSTALL_ROOT/INICIAR.command"
  if [ -f "$LAUNCHER" ]; then
    chmod +x "$LAUNCHER" 2>/dev/null || true
    xattr -d com.apple.quarantine "$LAUNCHER" 2>/dev/null || true
    bash "$LAUNCHER"
  else
    open -a "FrameZero Clips" 2>/dev/null || true
  fi
}

uninstall_clips() {
  brand_header
  echo "Esta ação remove o FrameZero Clips e os componentes instalados por ele."
  read -r -p "Digite APAGAR para confirmar: " CONFIRMA
  CONFIRMA="$(printf '%s' "$CONFIRMA" | tr '[:lower:]' '[:upper:]')"
  [ "$CONFIRMA" = "APAGAR" ] || { echo "Cancelado."; return 0; }

  sudo -v || return 1
  pkill -f "FrameZero" 2>/dev/null || true
  pkill -f "servidor.py" 2>/dev/null || true
  rm -rf "$INSTALL_ROOT" \
    "$HOME/Library/Application Support/FrameZero" \
    "$HOME/Library/Application Support/FrameZero Clips" \
    "$HOME/Library/Caches/FrameZero"* \
    "$HOME/Library/Logs/FrameZero"* \
    "$HOME/Desktop/FrameZero Clips.command" \
    "$HOME/Applications/FrameZero.app" \
    "$HOME/Applications/FrameZero Clips.app" 2>/dev/null || true
  sudo rm -rf /Applications/FrameZero*.app /Library/Application\ Support/FrameZero* 2>/dev/null || true
  echo "[OK] FrameZero Clips removido."
}

main_menu() {
  while true; do
    brand_header
    echo "Versão disponível: ${LATEST_VERSION:-?} - ${RELEASE_NAME:-?}"
    echo
    echo "[1] Instalar ou atualizar FrameZero Clips"
    echo "[2] Abrir FrameZero Clips"
    echo "[3] Verificar atualizações"
    echo "[4] Desinstalar FrameZero Clips"
    echo "[5] Sair"
    echo
    read -r -p "Opção: " OPCAO
    case "$OPCAO" in
      1) download_and_run_clips; pause_menu ;;
      2) launch_clips; pause_menu ;;
      3) load_manifest; pause_menu ;;
      4) uninstall_clips; pause_menu ;;
      5) exit 0 ;;
      *) echo "Opção inválida."; pause_menu ;;
    esac
  done
}

load_manifest || true
self_update_if_needed || true
main_menu
