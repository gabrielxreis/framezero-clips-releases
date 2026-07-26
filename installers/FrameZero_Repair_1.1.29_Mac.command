#!/bin/bash
set -u
export TERM="${TERM:-xterm-256color}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
SYSTEM_APP="/Applications/FrameZero Clips.app"
USER_APP="$HOME/Applications/FrameZero Clips.app"
DESKTOP_CMD="$HOME/Desktop/Abrir FrameZero Clips.command"
LOG_DIR="$HOME/Library/Logs/FrameZero"
LOG="$LOG_DIR/framezero-repair-1.1.29.log"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG") 2>&1

clear 2>/dev/null || true
cat <<'EOF'
============================================================
 FRAMEZERO CLIPS - REPARO DO EXECUTOR MAC INTEL 1.1.29
============================================================
Este reparo recria o aplicativo para abrir o launcher real
em uma janela visível do Terminal e cria um atalho na Mesa.
============================================================
EOF

if [ "$(uname -m)" != "x86_64" ]; then
  echo "[ERRO] Este reparo é exclusivo para Mac Intel."
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
fi

if [ ! -d "$ROOT" ] || [ ! -f "$ROOT/INICIAR.command" ]; then
  echo "[ERRO] O FrameZero instalado não foi encontrado em:"
  echo "$ROOT"
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
fi

pkill -f "$ROOT" 2>/dev/null || true
pkill -f "servidor.py" 2>/dev/null || true
sleep 2

chmod +x "$ROOT/INICIAR.command" "$ROOT/INICIAR-FRAMEZERO.command" 2>/dev/null || true
xattr -dr com.apple.quarantine "$ROOT" 2>/dev/null || true

cat > "$DESKTOP_CMD" <<'DESKTOP'
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
LOG_DIR="$HOME/Library/Logs/FrameZero"
LOG="$LOG_DIR/framezero-launch-visible.log"
mkdir -p "$LOG_DIR"
clear 2>/dev/null || true
echo "============================================================"
echo " FRAMEZERO CLIPS - EXECUTOR MAC INTEL"
echo "============================================================"
echo "Log: $LOG"
echo "Deixe esta janela aberta enquanto estiver usando o FrameZero."
echo "============================================================"
cd "$ROOT" || { echo "ERRO: instalação não encontrada."; read -r -p "ENTER para fechar..." _; exit 1; }
/bin/bash "$ROOT/INICIAR.command" 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
echo
echo "O FrameZero foi encerrado com código: $RC"
echo "Log salvo em: $LOG"
read -r -p "Pressione ENTER para fechar..." _
exit "$RC"
DESKTOP
chmod +x "$DESKTOP_CMD"
xattr -d com.apple.quarantine "$DESKTOP_CMD" 2>/dev/null || true

APP_TARGET="$SYSTEM_APP"
if ! sudo -n true 2>/dev/null; then
  sudo -v 2>/dev/null || APP_TARGET="$USER_APP"
fi

TMP_APP="${TMPDIR:-/tmp}/FrameZero Clips.app"
rm -rf "$TMP_APP"

OSA_SCRIPT="${TMPDIR:-/tmp}/framezero-clips-launcher.applescript"
cat > "$OSA_SCRIPT" <<'APPLESCRIPT'
on run
  set launcherPath to POSIX path of (path to home folder) & "Desktop/Abrir FrameZero Clips.command"
  tell application "Terminal"
    activate
    do script "export TERM=xterm-256color; /bin/bash " & quoted form of launcherPath
  end tell
end run
APPLESCRIPT

if ! osacompile -o "$TMP_APP" "$OSA_SCRIPT"; then
  echo "[ERRO] Não foi possível gerar o aplicativo com AppleScript."
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
fi

PLIST="$TMP_APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName FrameZero Clips" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName FrameZero Clips" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier br.com.framezero.clips.intel" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 1.1.29" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion 1.1.29" "$PLIST" 2>/dev/null || true

ICON="$(find "$ROOT" -type f -iname '*.icns' 2>/dev/null | head -n1)"
if [ -n "$ICON" ] && [ -f "$ICON" ]; then
  cp "$ICON" "$TMP_APP/Contents/Resources/FrameZero.icns"
  /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string FrameZero" "$PLIST" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Set :CFBundleIconFile FrameZero" "$PLIST" 2>/dev/null || true
fi

xattr -dr com.apple.quarantine "$TMP_APP" 2>/dev/null || true
codesign --force --deep --sign - "$TMP_APP" >/dev/null 2>&1 || true

if [ "$APP_TARGET" = "$SYSTEM_APP" ]; then
  sudo rm -rf "$SYSTEM_APP"
  sudo cp -R "$TMP_APP" "$SYSTEM_APP"
  sudo xattr -dr com.apple.quarantine "$SYSTEM_APP" 2>/dev/null || true
else
  mkdir -p "$HOME/Applications"
  rm -rf "$USER_APP"
  cp -R "$TMP_APP" "$USER_APP"
  xattr -dr com.apple.quarantine "$USER_APP" 2>/dev/null || true
fi

/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_TARGET" >/dev/null 2>&1 || true
killall Finder Dock >/dev/null 2>&1 || true

echo "[OK] Aplicativo recriado em: $APP_TARGET"
echo "[OK] Atalho de emergência criado em: $DESKTOP_CMD"
echo
echo "Abrindo o executor agora..."
open -n "$APP_TARGET"

echo
echo "Se o app não abrir, dê dois cliques em:"
echo "$DESKTOP_CMD"
echo "Log do reparo: $LOG"
read -r -p "Pressione ENTER para fechar esta janela..." _
