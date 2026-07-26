#!/bin/bash
set -u
trap 'RC=$?; if [ "$RC" -ne 0 ]; then echo; echo "[ERRO] A instalação encontrou um problema."; read -r -p "Pressione ENTER para fechar..." _; fi' EXIT

CURRENT_INSTALLER_VERSION="1.1.22"
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

header(){ clear; cat <<TXT
============================================================
          FrameZero Clips Installer 1.1.22 - macOS
============================================================
 Mac detectado: $PLATFORM_NAME ($ARCH)
 Motor local: $TRANSCRIPTION_ENGINE
============================================================
TXT
}

read_json(){ python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],''))" "$VERSION_FILE" "$1" 2>/dev/null || plutil -extract "$1" raw -o - "$VERSION_FILE" 2>/dev/null || true; }
load_manifest(){ header; curl -fL "$VERSION_URL?cb=$(date +%s)" -o "$VERSION_FILE" || return 1; LATEST_VERSION="$(read_json latest_version)"; RELEASE_NAME="$(read_json release_name)"; MAC_URL="$(read_json mac_url)"; }
find_python3(){ for P in /usr/local/bin/python3 /opt/homebrew/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 "$(command -v python3 2>/dev/null || true)"; do [ -n "$P" ] && [ -x "$P" ] && { echo "$P"; return 0; }; done; return 1; }

patch_inner_installer(){
  SCRIPT="$1"
  PY="$(find_python3)" || return 1
  "$PY" - "$SCRIPT" <<'PY'
import sys
p=sys.argv[1]
text=open(p,'r',encoding='utf-8',errors='ignore').read()
lines=text.splitlines(True)
needle='esta versão exige Mac Apple Silicon'
idx=next((i for i,l in enumerate(lines) if needle in l),None)
if idx is None:
    needle='esta versao exige Mac Apple Silicon'
    idx=next((i for i,l in enumerate(lines) if needle in l),None)
if idx is None:
    print('Nenhuma trava Apple Silicon encontrada; seguindo.')
    raise SystemExit(0)
start=idx
while start>=0 and not lines[start].lstrip().startswith('if '):
    start-=1
end=idx
while end<len(lines) and lines[end].strip()!='fi':
    end+=1
if start>=0 and end<len(lines):
    repl=['if [ "$(uname -m)" = "x86_64" ]; then\n','  echo "OK: Mac Intel detectado. A trava Apple Silicon foi removida pelo instalador universal."\n','fi\n']
    lines[start:end+1]=repl
else:
    lines[idx]='echo "OK: Mac Intel autorizado pelo instalador universal."\n'
open(p,'w',encoding='utf-8').writelines(lines)
print('Trava Apple Silicon removida do instalador interno.')
PY
}

prepare_intel(){
  [ "$ARCH" = "x86_64" ] || return 0
  PY="$(find_python3)" || { echo "[ERRO] Python 3 não encontrado."; return 1; }
  VENV="$APP_DIR/venv"
  rm -rf "$VENV"
  "$PY" -m venv "$VENV" || return 1
  "$VENV/bin/python" -m pip install --upgrade pip setuptools wheel || return 1
  "$VENV/bin/python" -m pip install "faster-whisper>=1.1,<2" "ctranslate2>=4,<5" || return 1
  CONFIG="$APP_DIR/config.json"
  if [ -f "$CONFIG" ]; then
    "$PY" - "$CONFIG" <<'PY'
import json,sys
p=sys.argv[1]
try: d=json.load(open(p,encoding='utf-8'))
except: d={}
d.update({'transcription_engine':'faster-whisper','transcricao_modo':'local','whisper_vps_url':'','whisper_vps_token':'','vps_fallback_local':False,'vps_enviar_audio_ao_vivo':False})
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
PY
  fi
  echo "[OK] faster-whisper local preparado para Mac Intel."
}

install_clips(){
  ZIP="$TMP/clips.zip"; DIR="$TMP/clips"; rm -rf "$DIR"; mkdir -p "$DIR"
  curl -fL "$MAC_URL?cb=$(date +%s)" -o "$ZIP" || return 1
  unzip -q -o "$ZIP" -d "$DIR" || return 1
  SCRIPT="$(find "$DIR" -type f -name '*FRAMEZERO*CLIPS*.command' | head -n1)"
  [ -n "$SCRIPT" ] || SCRIPT="$(find "$DIR" -type f -name '*.command' | head -n1)"
  [ -n "$SCRIPT" ] || { echo "[ERRO] Instalador interno não encontrado."; return 1; }
  chmod +x "$SCRIPT"; xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true
  [ "$ARCH" = "x86_64" ] && patch_inner_installer "$SCRIPT"
  FRAMEZERO_MAC_ARCH="$ARCH" FRAMEZERO_TRANSCRIPTION_ENGINE="$TRANSCRIPTION_ENGINE" FRAMEZERO_INSTALL_WITH_NATIONS=0 FRAMEZERO_AUTO_INSTALL=clean bash "$SCRIPT" || return 1
  prepare_intel || return 1
  echo "[OK] FrameZero Clips instalado para $PLATFORM_NAME."
}

uninstall_clips(){ read -r -p "Digite APAGAR para confirmar: " C; [ "$(echo "$C"|tr '[:lower:]' '[:upper:]')" = "APAGAR" ] || return 0; pkill -f FrameZero 2>/dev/null || true; rm -rf "$INSTALL_ROOT" "$HOME/Library/Application Support/FrameZero"* "$HOME/Library/Caches/FrameZero"* "$HOME/Library/Logs/FrameZero"* "$HOME/Applications/FrameZero"*.app 2>/dev/null || true; sudo rm -rf /Applications/FrameZero*.app /Library/Application\ Support/FrameZero* 2>/dev/null || true; echo "[OK] FrameZero Clips removido."; }

load_manifest || true
while true; do
  header
  echo "Versão disponível: ${LATEST_VERSION:-?} - ${RELEASE_NAME:-?}"
  echo
  echo "[1] Instalar ou atualizar FrameZero Clips"
  echo "[2] Abrir FrameZero Clips"
  echo "[3] Verificar atualizações"
  echo "[4] Desinstalar FrameZero Clips"
  echo "[5] Sair"
  read -r -p "Opção: " OP
  case "$OP" in
    1) install_clips; read -r -p "Pressione ENTER..." _ ;;
    2) [ -f "$INSTALL_ROOT/INICIAR.command" ] && bash "$INSTALL_ROOT/INICIAR.command" || open -a "FrameZero Clips" 2>/dev/null || true ;;
    3) load_manifest ;;
    4) uninstall_clips ;;
    5) exit 0 ;;
  esac
done
