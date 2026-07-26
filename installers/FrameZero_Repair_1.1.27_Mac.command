#!/bin/bash
set -u

ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
SYSTEM_APP="/Applications/FrameZero Clips.app"
USER_APP="$HOME/Applications/FrameZero Clips.app"
LOG_DIR="$HOME/Library/Logs/FrameZero"
LOG="$LOG_DIR/framezero-repair.log"
ARCH="$(uname -m 2>/dev/null || echo unknown)"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG") 2>&1

clear 2>/dev/null || true
cat <<EOF
============================================================
       FRAMEZERO CLIPS - REPARO MAC INTEL 1.1.27
============================================================
Arquitetura detectada: $ARCH
Instalação: $ROOT
============================================================
EOF

if [ ! -d "$ROOT" ]; then
  echo "[ERRO] A instalação do FrameZero não foi encontrada."
  echo "Execute primeiro o instalador oficial 1.1.26."
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
fi

echo
echo "Encerrando processos antigos..."
pkill -f "$ROOT" 2>/dev/null || true
pkill -f "servidor.py" 2>/dev/null || true
sleep 2

echo "Corrigindo scripts instalados..."
COUNT=0
while IFS= read -r -d '' FILE; do
  if grep -qiE 'exige Mac Apple Silicon|requires Apple Silicon|M1/M2/M3/M4' "$FILE" 2>/dev/null; then
    cp "$FILE" "$FILE.before-intel-repair" 2>/dev/null || true
    /usr/bin/perl -0777 -i -pe 's/if\s+[^\n]*(?:uname\s+-m|ARCH|MACHINE_ARCH|x86_64|arm64)[^\n]*\n(?:(?!\nfi\b).)*?(?:exige Mac Apple Silicon|requires Apple Silicon|M1\/M2\/M3\/M4).*?\nfi/echo "OK: Mac Intel autorizado pelo instalador universal."/gis' "$FILE"
    /usr/bin/perl -i -pe 'if (/exige Mac Apple Silicon|requires Apple Silicon|M1\/M2\/M3\/M4/i) { $_="echo \"OK: Mac Intel autorizado pelo instalador universal.\"\n" }' "$FILE"
    chmod +x "$FILE" 2>/dev/null || true
    COUNT=$((COUNT + 1))
  fi
done < <(find "$ROOT" -type f \( -name '*.command' -o -name '*.sh' -o -name '*.bash' \) -print0)

echo "Scripts com trava corrigidos: $COUNT"

if grep -RniE 'exige Mac Apple Silicon|requires Apple Silicon|M1/M2/M3/M4' "$ROOT" --include='*.command' --include='*.sh' --include='*.bash' 2>/dev/null; then
  echo "[ERRO] Ainda foi encontrada uma trava Apple Silicon."
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
fi

echo "Restaurando a versão correta do Core para 1.1.19..."
while IFS= read -r -d '' FILE; do
  [ -f "$FILE" ] || continue
  [ "$(stat -f%z "$FILE" 2>/dev/null || echo 9999999)" -lt 1048576 ] || continue
  grep -Iq . "$FILE" 2>/dev/null || continue
  if grep -q '1\.1\.26' "$FILE" 2>/dev/null; then
    /usr/bin/perl -i -pe 's/1\.1\.26/1.1.19/g' "$FILE" 2>/dev/null || true
  fi
done < <(find "$ROOT" -type f -print0)

for VERSION_FILE in \
  "$ROOT/version.txt" \
  "$ROOT/.version" \
  "$ROOT/app/version.txt" \
  "$ROOT/app/.version" \
  "$ROOT/CURRENT_VERSION"; do
  [ -f "$VERSION_FILE" ] && printf '1.1.19\n' > "$VERSION_FILE"
done

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

LAUNCHER="$(find_launcher)" || {
  echo "[ERRO] O launcher local não foi encontrado."
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
}

chmod +x "$LAUNCHER" 2>/dev/null || true
xattr -d com.apple.quarantine "$LAUNCHER" 2>/dev/null || true

APP_TARGET="$SYSTEM_APP"
if [ ! -d "$SYSTEM_APP" ]; then
  APP_TARGET="$USER_APP"
fi

if [ ! -d "$APP_TARGET" ]; then
  echo "[ERRO] O aplicativo FrameZero Clips.app não foi encontrado."
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
fi

APP_EXEC="$APP_TARGET/Contents/MacOS/FrameZero Clips"
mkdir -p "$(dirname "$APP_EXEC")"
cat > "$APP_EXEC" <<EOF
#!/bin/bash
export TERM="\${TERM:-xterm-256color}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:\$PATH"
ROOT="$ROOT"
LAUNCHER="$LAUNCHER"
LOG_DIR="\$HOME/Library/Logs/FrameZero"
LOG="\$LOG_DIR/framezero-launch.log"
mkdir -p "\$LOG_DIR"
echo "==== FrameZero iniciado em \$(date) ====" >> "\$LOG"
chmod +x "\$LAUNCHER" 2>/dev/null || true
xattr -d com.apple.quarantine "\$LAUNCHER" 2>/dev/null || true
cd "\$ROOT" || exit 1
/bin/bash "\$LAUNCHER" >> "\$LOG" 2>&1 &
PID=\$!
sleep 8
if kill -0 "\$PID" 2>/dev/null || pgrep -f "servidor.py|\$ROOT" >/dev/null 2>&1; then
  while kill -0 "\$PID" 2>/dev/null || pgrep -f "servidor.py|\$ROOT" >/dev/null 2>&1; do sleep 5; done
  exit 0
fi
osascript -e 'display dialog "O FrameZero não conseguiu iniciar. O diagnóstico será aberto." buttons {"OK"} default button "OK" with icon stop' >/dev/null 2>&1 || true
open "\$LOG" 2>/dev/null || true
exit 1
EOF

chmod +x "$APP_EXEC"
xattr -dr com.apple.quarantine "$APP_TARGET" 2>/dev/null || true
codesign --force --deep --sign - "$APP_TARGET" >/dev/null 2>&1 || true
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_TARGET" >/dev/null 2>&1 || true

echo "[OK] Launcher e aplicativo reparados."
echo "Abrindo FrameZero Clips..."
open -n "$APP_TARGET"

echo
echo "O app foi aberto. Se ocorrer outro erro, envie este arquivo:"
echo "$HOME/Library/Logs/FrameZero/framezero-launch.log"
read -r -p "Pressione ENTER para fechar o reparo..." _
