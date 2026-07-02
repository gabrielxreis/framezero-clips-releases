#!/bin/bash
set +e
clear
cat <<WARN
============================================================
      DESINSTALACAO TOTAL - FRAMEZERO v1.0.66
============================================================

Isto remove:
- FrameZero Clips
- FrameZero Nations
- Aitum Vertical / OBS Vertical Canvas
- Aitum Multistream
- plugins do OBS instalados pelo FrameZero
- configuracoes completas do OBS
- BlackHole da raiz do macOS em /Library/Audio/Plug-Ins/HAL

ATENCAO: o OBS nao sera removido, mas vai abrir zerado.
WARN
echo
read -p "Digite APAGAR para confirmar: " CONFIRMA
CONFIRMA_UPPER="$(printf '%s' "$CONFIRMA" | tr '[:lower:]' '[:upper:]')"
if [ "$CONFIRMA_UPPER" != "APAGAR" ] && [ "$CONFIRMA_UPPER" != "DELETE" ]; then
  echo "Cancelado."
  read -r -p "Pressione Enter para sair..." _
  exit 0
fi

echo "Solicitando permissao de administrador para remover plugins/drivers de sistema..."
sudo -v || { echo "Permissao negada."; read -p "Pressione Enter para sair..." _; exit 1; }

while true; do sudo -n true; sleep 30; kill -0 "$$" || exit; done 2>/dev/null & SUDO_KEEPALIVE=$!
trap 'kill "$SUDO_KEEPALIVE" 2>/dev/null' EXIT

echo "Fechando OBS, FrameZero e processos relacionados..."
pkill -f "OBS" 2>/dev/null || true
pkill -f "obs" 2>/dev/null || true
pkill -f "FrameZero" 2>/dev/null || true
pkill -f "servidor.py" 2>/dev/null || true
pkill -f "Aitum" 2>/dev/null || true
for P in 8765 8766 8889 4455; do
  lsof -ti tcp:$P | xargs kill -9 2>/dev/null || true
done
sleep 1

OBS_DIR="$HOME/Library/Application Support/obs-studio"
OBS_SYS_DIR="/Library/Application Support/obs-studio"

echo "Removendo FrameZero Clips, Nations, atalhos, caches e pastas..."
rm -rf "$OBS_DIR/FrameZero" "$OBS_DIR/FrameZeroNations"
rm -rf "$HOME/Library/Application Support/FrameZero" "$HOME/Library/Application Support/FrameZero Clips" "$HOME/Library/Application Support/FrameZero Nations"
rm -rf "$HOME/Library/Caches/FrameZero" "$HOME/Library/Caches/FrameZero Clips" "$HOME/Library/Caches/FrameZero Nations"
rm -rf "$HOME/Library/Logs/FrameZero" "$HOME/Library/Logs/FrameZero Clips" "$HOME/Library/Logs/FrameZero Nations"
rm -f "$HOME/Library/LaunchAgents/com.framezero"*.plist 2>/dev/null || true
rm -rf "$HOME/Desktop/FrameZero Clips.command" "$HOME/Desktop/FrameZero Nations.command" "$HOME/Applications/FrameZero Launcher.app"
rm -rf "$HOME/Movies/FrameZero_Cortes"* "$HOME/Documents/FrameZero_Cortes"* "$HOME/Desktop/FrameZero_Cortes"*
sudo rm -rf /Library/Application\ Support/FrameZero* /Library/LaunchAgents/com.framezero*.plist /Library/LaunchDaemons/com.framezero*.plist 2>/dev/null || true

echo "Desinstalando/forget pacotes Aitum, Vertical Canvas, Multistream, Face Tracker e BlackHole..."
for PKG in $(pkgutil --pkgs 2>/dev/null | grep -Ei "aitum|vertical|multistream|multi-stream|obs-vertical|obs.*multi|blackhole|existential|existentialaudio|face.*tracker|source.*record"); do
  sudo pkgutil --forget "$PKG" >/dev/null 2>&1 || true
done

echo "Removendo plugins OBS Aitum Vertical, Aitum Multistream e outros instalados pelo FrameZero..."
PLUGIN_PATTERNS=(
  '*aitum*'
  '*Aitum*'
  '*vertical*'
  '*Vertical*'
  '*multistream*'
  '*Multistream*'
  '*multi-stream*'
  '*canvas*'
  '*Canvas*'
  '*obs-vertical-canvas*'
  '*obs-aitum-multistream*'
  '*obs-multi-rtmp*'
  '*face*tracker*'
  '*Face*Tracker*'
  '*facetracker*'
  '*obs-face-tracker*'
  '*source-record*'
)
PLUGIN_BASES=(
  "$HOME/Library/Application Support/obs-studio"
  "/Library/Application Support/obs-studio"
  "/Applications/OBS.app/Contents"
  "/Applications/OBS Studio.app/Contents"
)
PLUGIN_SUBS=(
  "plugins"
  "obs-plugins"
  "data/obs-plugins"
  "Resources/data/obs-plugins"
  "Resources/obs-plugins"
  "MacOS"
)
for BASEDIR in "${PLUGIN_BASES[@]}"; do
  for SUB in "${PLUGIN_SUBS[@]}"; do
    DIR="$BASEDIR/$SUB"
    [ -d "$DIR" ] || continue
    for PAT in "${PLUGIN_PATTERNS[@]}"; do
      sudo find "$DIR" -maxdepth 4 -iname "$PAT" -exec rm -rf {} + 2>/dev/null || true
    done
  done
done
# caminhos conhecidos dos plugins do OBS no Mac
sudo rm -rf \
  "/Library/Application Support/obs-studio/plugins/aitum-multistream.plugin" \
  "/Library/Application Support/obs-studio/plugins/obs-aitum-multistream.plugin" \
  "/Library/Application Support/obs-studio/plugins/obs-vertical-canvas.plugin" \
  "/Library/Application Support/obs-studio/plugins/vertical-canvas.plugin" \
  "/Library/Application Support/obs-studio/data/obs-plugins/aitum-multistream" \
  "/Library/Application Support/obs-studio/data/obs-plugins/obs-aitum-multistream" \
  "/Library/Application Support/obs-studio/data/obs-plugins/obs-vertical-canvas" \
  "/Library/Application Support/obs-studio/data/obs-plugins/vertical-canvas" 2>/dev/null || true

echo "Zerando configuracoes completas do OBS do usuario e plugins globais..."
rm -rf "$OBS_DIR" 2>/dev/null || true
sudo rm -rf "$OBS_SYS_DIR" 2>/dev/null || true

echo "Removendo BlackHole da raiz do macOS..."
if [ -d "/Library/Audio/Plug-Ins/HAL" ]; then
  cd /Library/Audio/Plug-Ins/HAL || true
  sudo rm -rf BlackHole*.driver *BlackHole* *blackhole* 2>/dev/null || true
fi
sudo rm -rf     /Library/Audio/Plug-Ins/HAL/BlackHole*.driver     /Library/Audio/Plug-Ins/HAL/*BlackHole*     /Library/Audio/Plug-Ins/HAL/*blackhole*     /Library/Extensions/BlackHole*.kext     /Library/Extensions/*BlackHole*     /Library/Receipts/*BlackHole*     /Library/LaunchDaemons/*BlackHole*     /Library/LaunchAgents/*BlackHole*     /Applications/BlackHole*.app     /var/db/receipts/*BlackHole*     /var/db/receipts/*blackhole*     /usr/local/lib/*BlackHole*     /usr/local/share/*BlackHole* 2>/dev/null || true
sudo killall coreaudiod >/dev/null 2>&1 || true

echo
echo "[OK] Desinstalacao total concluida. FrameZero, Nations, OBS configs, Aitum Vertical, Aitum Multistream e BlackHole foram removidos quando encontrados."
echo "Se o BlackHole ou algum plugin ainda aparecer, reinicie o Mac uma vez."
echo
read -p "Pressione Enter para sair..." _
