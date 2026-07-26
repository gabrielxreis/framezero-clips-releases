#!/bin/bash
set -u
export TERM="${TERM:-xterm-256color}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
APP="$ROOT/app"
VENV="$APP/venv"
SYSTEM_APP="/Applications/FrameZero Clips.app"
USER_APP="$HOME/Applications/FrameZero Clips.app"
DESKTOP_CMD="$HOME/Desktop/Abrir FrameZero Clips.command"
LOG_DIR="$HOME/Library/Logs/FrameZero"
LOG="$LOG_DIR/framezero-repair-1.1.30.log"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG") 2>&1

clear 2>/dev/null || true
cat <<'MSG'
============================================================
 FRAMEZERO CLIPS - REPARO DEFINITIVO MAC INTEL 1.1.30
============================================================
Este reparo remove o launcher antigo, desativa auto-update do
pacote e inicia diretamente o servidor pelo ambiente Intel.
============================================================
MSG

[ "$(uname -m)" = "x86_64" ] || { echo "[ERRO] Exclusivo para Mac Intel."; read -r -p "ENTER para fechar..." _; exit 1; }
[ -d "$ROOT" ] || { echo "[ERRO] Instalação não encontrada: $ROOT"; read -r -p "ENTER para fechar..." _; exit 1; }
[ -f "$APP/servidor.py" ] || { echo "[ERRO] servidor.py não encontrado em $APP"; read -r -p "ENTER para fechar..." _; exit 1; }

pkill -f "$ROOT" 2>/dev/null || true
pkill -f "servidor.py" 2>/dev/null || true
sleep 2

BACKUP="$ROOT/.intel-launcher-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for F in INICIAR.command INICIAR-FRAMEZERO.command FrameZero-Update-Check.command INICIAR.command.framezero-original-before-autoupdate-fix; do
  [ -f "$ROOT/$F" ] && cp "$ROOT/$F" "$BACKUP/$F" 2>/dev/null || true
done
rm -f "$ROOT/INICIAR.command.framezero-original-before-autoupdate-fix"

if [ ! -x "$VENV/bin/python" ]; then
  echo "[ERRO] Ambiente Intel não encontrado em: $VENV"
  echo "Execute primeiro o reparo 1.1.28 e depois este 1.1.30."
  read -r -p "ENTER para fechar..." _
  exit 1
fi

cat > "$ROOT/FrameZero-Update-Check.command" <<'UPD'
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
echo "Atualização automática do pacote desativada no Mac Intel."
echo "Core instalado: 1.1.19"
exit 0
UPD
chmod +x "$ROOT/FrameZero-Update-Check.command"

cat > "$ROOT/INICIAR-FRAMEZERO.command" <<'MAIN'
#!/bin/bash
set +e
export TERM="${TERM:-xterm-256color}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
APP="$ROOT/app"
VENV="$APP/venv"
SITE_URL="https://clips.framezeroai.com.br/obs"
LOG_DIR="$ROOT/logs"
LOG="$LOG_DIR/framezero-terminal.log"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG") 2>&1
clear 2>/dev/null || true
cat <<EOF
============================================================
 FRAMEZERO CLIPS 1.1.19 - MAC INTEL
============================================================
Painel: $SITE_URL
Log: $LOG
Deixe esta janela aberta enquanto estiver usando o FrameZero.
============================================================
EOF

kill_port(){ P="$1"; PID="$(lsof -ti tcp:$P 2>/dev/null || true)"; [ -n "$PID" ] && kill -9 $PID 2>/dev/null || true; }
kill_port 8765
kill_port 8766
kill_port 8889

if [ ! -x "$VENV/bin/python" ]; then
  echo "ERRO: ambiente Python Intel ausente em $VENV"
  read -r -p "ENTER para fechar..." _
  exit 1
fi

export PATH="$ROOT/bin:$APP/ffmpeg/bin:$PATH"
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg não encontrado; instalando fallback local..."
  "$VENV/bin/python" -m pip install --upgrade imageio-ffmpeg || true
  "$VENV/bin/python" - "$ROOT" "$APP" <<'PY'
import os,shutil,stat,sys
import imageio_ffmpeg
src=imageio_ffmpeg.get_ffmpeg_exe()
for dst in [os.path.join(sys.argv[1],'bin','ffmpeg'),os.path.join(sys.argv[2],'ffmpeg','bin','ffmpeg')]:
 os.makedirs(os.path.dirname(dst),exist_ok=True); shutil.copy2(src,dst); os.chmod(dst,os.stat(dst).st_mode|stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH)
PY
fi

open -a "OBS" 2>/dev/null || open -a "OBS Studio" 2>/dev/null || true
open "$SITE_URL" >/dev/null 2>&1 || true
cd "$APP" || exit 1

echo "Testando servidor Python..."
if ! "$VENV/bin/python" -c "import mlx_whisper, faster_whisper, numpy; print('Dependências Intel OK')"; then
  echo "ERRO: dependências Intel incompletas."
  read -r -p "ENTER para fechar..." _
  exit 1
fi

echo "Iniciando servidor FrameZero..."
"$VENV/bin/python" "$APP/servidor.py"
RC=$?
echo
echo "FrameZero encerrado com código $RC"
read -r -p "Pressione ENTER para fechar..." _
exit "$RC"
MAIN
chmod +x "$ROOT/INICIAR-FRAMEZERO.command"

cat > "$ROOT/INICIAR.command" <<'ENTRY'
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
cd "$ROOT" || exit 1
exec /bin/bash "$ROOT/INICIAR-FRAMEZERO.command"
ENTRY
chmod +x "$ROOT/INICIAR.command"

cat > "$DESKTOP_CMD" <<'DESKTOP'
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
cd "$ROOT" || { echo "Instalação não encontrada."; read -r -p "ENTER..." _; exit 1; }
exec /bin/bash "$ROOT/INICIAR.command"
DESKTOP
chmod +x "$DESKTOP_CMD"
xattr -d com.apple.quarantine "$DESKTOP_CMD" 2>/dev/null || true
xattr -dr com.apple.quarantine "$ROOT" 2>/dev/null || true

APP_TARGET="$SYSTEM_APP"
[ -d "$APP_TARGET" ] || APP_TARGET="$USER_APP"
if [ -d "$APP_TARGET" ]; then
  OSA="${TMPDIR:-/tmp}/framezero-intel-launch.applescript"
  cat > "$OSA" <<'OSAEOF'
on run
 set p to POSIX path of (path to home folder) & "Desktop/Abrir FrameZero Clips.command"
 tell application "Terminal"
  activate
  do script "/bin/bash " & quoted form of p
 end tell
end run
OSAEOF
  TMP_APP="${TMPDIR:-/tmp}/FrameZero Clips.app"
  rm -rf "$TMP_APP"
  osacompile -o "$TMP_APP" "$OSA" || exit 1
  if [ "$APP_TARGET" = "$SYSTEM_APP" ]; then
    sudo rm -rf "$SYSTEM_APP"
    sudo cp -R "$TMP_APP" "$SYSTEM_APP"
    sudo xattr -dr com.apple.quarantine "$SYSTEM_APP" 2>/dev/null || true
  else
    rm -rf "$USER_APP"
    cp -R "$TMP_APP" "$USER_APP"
    xattr -dr com.apple.quarantine "$USER_APP" 2>/dev/null || true
  fi
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_TARGET" >/dev/null 2>&1 || true
fi

echo "[OK] Launchers antigos removidos e execução Intel direta instalada."
echo "Abrindo pelo atalho da Mesa..."
open "$DESKTOP_CMD"
echo "Log do reparo: $LOG"
read -r -p "Pressione ENTER para fechar o reparo..." _
