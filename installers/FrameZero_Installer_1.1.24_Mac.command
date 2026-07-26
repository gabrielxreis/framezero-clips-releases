#!/bin/bash
set -u
trap 'RC=$?; if [ "$RC" -ne 0 ]; then echo; echo "[ERRO] A instalação encontrou um problema."; read -r -p "Pressione ENTER para fechar..." _; fi' EXIT

VERSION_URL="https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json"
TMP="${TMPDIR:-/tmp}/FrameZeroInstaller1124"
MANIFEST="$TMP/version.json"
ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
APP="$ROOT/app"
mkdir -p "$TMP"
ARCH="$(uname -m 2>/dev/null || echo unknown)"
[ "$ARCH" = "arm64" ] && ENGINE="mlx-whisper" || ENGINE="faster-whisper"
[ "$ARCH" = "arm64" ] && PLATFORM="Apple Silicon" || PLATFORM="Intel"

header(){ clear; cat <<EOF
============================================================
          FrameZero Clips Installer 1.1.24 - macOS
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
  echo "Instale o Python 3 pelo site oficial e execute novamente."
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

install(){
  ZIP="$TMP/clips.zip"
  DIR="$TMP/package"
  rm -rf "$DIR"
  mkdir -p "$DIR"
  echo "Baixando pacote FrameZero Clips..."
  curl -fL "$MAC_URL?cb=$(date +%s)" -o "$ZIP" || return 1
  unzip -q -o "$ZIP" -d "$DIR" || return 1

  if [ "$ARCH" = "x86_64" ]; then
    patch_all_scripts_native "$DIR" || return 1
  fi

  SCRIPT="$(find "$DIR" -type f -iname '*clips*.command' | head -n1)"
  [ -n "$SCRIPT" ] || SCRIPT="$(find "$DIR" -type f -name '*.command' | head -n1)"
  [ -n "$SCRIPT" ] || { echo "[ERRO] Instalador interno não encontrado."; return 1; }

  chmod +x "$SCRIPT"
  xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true
  FRAMEZERO_MAC_ARCH="$ARCH" FRAMEZERO_TRANSCRIPTION_ENGINE="$ENGINE" FRAMEZERO_INSTALL_WITH_NATIONS=0 FRAMEZERO_AUTO_INSTALL=clean bash "$SCRIPT" || return 1
  prepare_intel || return 1
  echo "[OK] FrameZero Clips instalado para $PLATFORM."
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
    2) [ -f "$ROOT/INICIAR.command" ] && bash "$ROOT/INICIAR.command" || open -a "FrameZero Clips" 2>/dev/null || true ;;
    3) load ;;
    4) read -r -p "Digite APAGAR: " C; [ "$(echo "$C"|tr '[:lower:]' '[:upper:]')" = "APAGAR" ] && rm -rf "$ROOT" "$HOME/Library/Application Support/FrameZero"* "$HOME/Library/Caches/FrameZero"* "$HOME/Library/Logs/FrameZero"* 2>/dev/null || true ;;
    5) exit 0 ;;
  esac
done
