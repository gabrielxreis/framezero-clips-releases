#!/bin/bash
set -u
trap 'RC=$?; if [ "$RC" -ne 0 ]; then echo ""; echo "[ERRO/ERROR] O instalador encontrou um problema e não será fechado automaticamente."; read -r -p "Pressione ENTER para fechar..." _; fi' EXIT
CURRENT_INSTALLER_VERSION="1.0.72"
VERSION_URL="https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json"
TMP="${TMPDIR:-/tmp}/FrameZeroOnlineInstaller"
VERSION_FILE="$TMP/version.json"
LANGUAGE="pt"
mkdir -p "$TMP"

brand_header() {
  clear
  cat <<TXT
============================================================
                FrameZero Installer 1.0.72 - Mac
============================================================
 @gabrielxreis_                         @framezeroai
============================================================
TXT
}

welcome() {
  brand_header
  cat <<TXT
Seja bem-vindo ao instalador oficial do FrameZero.

Este instalador é só o bootstrap: ele baixa sempre o instalador real mais recente e prepara tudo automaticamente.
Depois que você escolher instalar, ele segue direto sem perguntas extras.
TXT
  echo
  LANGUAGE="pt"
}

T() {
  KEY="$1"
  if [ "$LANGUAGE" = "en" ]; then
    case "$KEY" in
      manifest) echo "Downloading version information" ;;
      manifest_error) echo "[ERROR] Could not download version information." ;;
      welcome) echo "Welcome to FrameZero." ;;
      source) echo "The installer checks updates and prepares the Mac before installing or opening the app." ;;
      version) echo "Clips version" ;;
      menu_title) echo "What do you want to do?" ;;
      opt1) echo "Install FrameZero Clips" ;;
      opt2) echo "Install FrameZero Clips + Nations" ;;
      opt3) echo "Install Nations only" ;;
      opt4) echo "Uninstall FrameZero completely (Clips + Nations + saved files)" ;;
      opt5) echo "Check updates again" ;;
      opt6) echo "Exit" ;;
      choose) echo "Option" ;;
      downloading_clips) echo "Downloading FrameZero Clips" ;;
      downloading_nations) echo "Downloading FrameZero Nations" ;;
      extracting) echo "Extracting package..." ;;
      running) echo "Running installer" ;;
      done) echo "Action completed." ;;
      back) echo "Press Enter to return to the menu..." ;;
      invalid) echo "Invalid option." ;;
      nations_off) echo "[NATIONS] Nations is not enabled for this version." ;;
      nations_empty) echo "[NATIONS] Nations package not found." ;;
      no_script) echo "[ERROR] No installer script found in the downloaded package." ;;
      confirm_uninstall) echo "Type DELETE to confirm full removal" ;;
      removed) echo "FrameZero was completely removed." ;;
      cancelled) echo "Cancelled." ;;
      *) echo "$KEY" ;;
    esac
  else
    case "$KEY" in
      manifest) echo "Baixando informações de versão" ;;
      manifest_error) echo "[ERRO] Não consegui baixar as informações de versão." ;;
      welcome) echo "Seja bem-vindo ao FrameZero." ;;
      source) echo "O instalador verifica atualizações e prepara o Mac antes de instalar ou abrir o app." ;;
      version) echo "Versão Clips" ;;
      menu_title) echo "O que você deseja fazer?" ;;
      opt1) echo "Instalar FrameZero Clips + Nations" ;;
      opt2) echo "Instalar somente FrameZero Clips" ;;
      opt3) echo "Instalar somente Nations" ;;
      opt4) echo "Desinstalar FrameZero completo (Clips + Nations + salvos)" ;;
      opt5) echo "Verificar atualizações novamente" ;;
      opt6) echo "Sair" ;;
      choose) echo "Opção" ;;
      downloading_clips) echo "Baixando FrameZero Clips" ;;
      downloading_nations) echo "Baixando FrameZero Nations" ;;
      extracting) echo "Extraindo pacote..." ;;
      running) echo "Executando instalador" ;;
      done) echo "Ação concluída." ;;
      back) echo "Pressione Enter para voltar ao menu..." ;;
      invalid) echo "Opção inválida." ;;
      nations_off) echo "[NATIONS] O Nations não está liberado para esta versão." ;;
      nations_empty) echo "[NATIONS] Pacote do Nations não encontrado." ;;
      no_script) echo "[ERRO] Nenhum instalador encontrado no pacote baixado." ;;
      confirm_uninstall) echo "Digite APAGAR para confirmar a remoção completa" ;;
      removed) echo "FrameZero removido por completo." ;;
      cancelled) echo "Cancelado." ;;
      *) echo "$KEY" ;;
    esac
  fi
}

pause_menu() { echo; read -r -p "$(T back)" _; }

download_file() {
  URL="$1"; OUT="$2"; LABEL="$3"
  echo "$LABEL"
  # O curl mostra porcentagem, tamanho, velocidade media, tempo e velocidade atual.
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
  echo "$(T welcome)"
  echo "$(T source)"
  echo
  if ! download_file "$VERSION_URL" "$VERSION_FILE" "$(T manifest)" ; then
    echo
    echo "$(T manifest_error)"
    pause_menu
    return 1
  fi
  LATEST_VERSION="$(read_json latest_version)"
  RELEASE_NAME="$(read_json release_name)"
  MAC_URL="$(read_json mac_url)"
  NATIONS_AVAILABLE="$(read_json nations_available)"
  NATIONS_URL="$(read_json nations_mac_url)"
  return 0
}

version_gt() {
  python3 - "$1" "$2" <<'PYV' 2>/dev/null || return 1
import sys
from itertools import zip_longest

def parts(v):
    return [int(x) if x.isdigit() else 0 for x in str(v).replace('v','').split('.')]
a=parts(sys.argv[1]); b=parts(sys.argv[2])
print('1' if a>b else '0')
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
    echo ""
    echo "Atualização do instalador encontrada: $NEW_VER"
    echo "Baixando o instalador novo do GitHub antes de continuar..."
    NEW_SCRIPT="$TMP/FrameZero_Installer_${NEW_VER}_Mac.command"
    if curl -fL "$NEW_URL" -o "$NEW_SCRIPT"; then
      chmod +x "$NEW_SCRIPT" 2>/dev/null || true
      xattr -d com.apple.quarantine "$NEW_SCRIPT" 2>/dev/null || true
      echo "Abrindo instalador atualizado..."
      FRAMEZERO_NO_SELF_UPDATE=1 exec bash "$NEW_SCRIPT"
    else
      echo "[AVISO] Não consegui atualizar o instalador. Continuando com este mesmo."
    fi
  fi
}

download_and_run() {
  URL="$1"; ZIPNAME="$2"; PATTERN="$3"; LABEL="$4"
  ZIPPATH="$TMP/$ZIPNAME"; EXTRACT="$TMP/extract_$ZIPNAME"
  rm -rf "$EXTRACT"; mkdir -p "$EXTRACT"
  echo
  if ! download_file "$URL" "$ZIPPATH" "$LABEL" ; then
    echo
    echo "[ERRO/ERROR] download failed."
    return 1
  fi
  echo "$(T extracting)"
  if ! unzip -q -o "$ZIPPATH" -d "$EXTRACT"; then
    echo "[ERRO/ERROR] extract failed."
    return 1
  fi
  SCRIPT="$(find "$EXTRACT" -type f -name "$PATTERN" | head -n 1)"
  if [ -z "$SCRIPT" ]; then echo "$(T no_script)"; return 1; fi
  chmod +x "$SCRIPT" 2>/dev/null || true
  xattr -dr com.apple.quarantine "$EXTRACT" 2>/dev/null || true
  echo "$(T running)..."
  bash "$SCRIPT"
}

install_nations() {
  if [ "$NATIONS_AVAILABLE" != "True" ] && [ "$NATIONS_AVAILABLE" != "true" ]; then echo "$(T nations_off)"; return 0; fi
  if [ -z "$NATIONS_URL" ]; then echo "$(T nations_empty)"; return 0; fi
  FRAMEZERO_NATIONS_AUTO_INSTALL=1 download_and_run "$NATIONS_URL" "nations.zip" "*NATIONS*.command" "$(T downloading_nations)"
}

cleanup_old_tmp_framezero() {
  rm -f /tmp/framezero-run-*.command 2>/dev/null || true
  find /tmp -maxdepth 1 -type d -name "framezero-installer-*" -mtime +0 -exec rm -rf {} + 2>/dev/null || true
}

launch_clips_after_install() {
  LAUNCHER="$HOME/Library/Application Support/obs-studio/FrameZero/INICIAR.command"
  if [ -f "$LAUNCHER" ]; then
    chmod +x "$LAUNCHER" 2>/dev/null || true
    xattr -d com.apple.quarantine "$LAUNCHER" 2>/dev/null || true
    echo ""
    echo "Iniciando FrameZero Clips..."
    cleanup_old_tmp_framezero
    bash "$LAUNCHER"
  else
    echo ""
    echo "FrameZero instalado. Para abrir, use o atalho na pasta do FrameZero no OBS."
  fi
}

start_nations_languages_background() {
  echo ""
  echo "Baixando idiomas do Nations em segundo plano."
  echo "O FrameZero Clips já pode ser usado enquanto os idiomas ficam disponíveis."
  LOG="$TMP/nations-languages-background.log"
  nohup bash "$0" --nations-langs-background > "$LOG" 2>&1 &
  echo "Log dos idiomas: $LOG"
}

uninstall_all() {
  clear
  cat <<'WARN'
============================================================
      DESINSTALACAO TOTAL - FRAMEZERO v1.0.72
============================================================

Isto remove:
- FrameZero Clips
- FrameZero Nations
- Aitum Vertical / OBS Vertical Canvas
- Aitum Multistream
- plugins do OBS instalados pelo FrameZero
- configuracoes completas do OBS do usuario e do sistema
- BlackHole da raiz do macOS em /Library/Audio/Plug-Ins/HAL

ATENCAO: o OBS.app nao sera removido, mas vai abrir zerado.
WARN
  echo
  read -r -p "Digite APAGAR para confirmar: " CONFIRMA
  CONFIRMA_UPPER="$(printf '%s' "$CONFIRMA" | tr '[:lower:]' '[:upper:]')"
  if [ "$CONFIRMA_UPPER" != "APAGAR" ] && [ "$CONFIRMA_UPPER" != "DELETE" ]; then
    echo "Cancelado. Nada foi removido."
    read -r -p "Pressione Enter para voltar..." _
    return 0
  fi

  echo "Solicitando permissao de administrador para remover plugins/drivers de sistema..."
  sudo -v || { echo "Permissao negada."; read -r -p "Pressione Enter para sair..." _; return 1; }

  echo "Fechando OBS, FrameZero e processos relacionados..."
  pkill -f "OBS" 2>/dev/null || true
  pkill -f "obs" 2>/dev/null || true
  pkill -f "FrameZero" 2>/dev/null || true
  pkill -f "framezero" 2>/dev/null || true
  pkill -f "servidor.py" 2>/dev/null || true
  pkill -f "Aitum" 2>/dev/null || true
  for P in 8765 8766 8889 4455; do
    lsof -ti tcp:$P 2>/dev/null | xargs kill -9 2>/dev/null || true
  done
  sleep 1

  OBS_USER="$HOME/Library/Application Support/obs-studio"
  OBS_SYSTEM="/Library/Application Support/obs-studio"

  echo "Removendo FrameZero Clips, Nations, atalhos, caches e apps antigos..."
  rm -rf \
    "$HOME/Library/Application Support/FrameZero" \
    "$HOME/Library/Application Support/FrameZero Clips" \
    "$HOME/Library/Application Support/FrameZero Nations" \
    "$HOME/Library/Caches/FrameZero" \
    "$HOME/Library/Caches/FrameZero Clips" \
    "$HOME/Library/Caches/FrameZero Nations" \
    "$HOME/Library/Logs/FrameZero" \
    "$HOME/Library/Logs/FrameZero Clips" \
    "$HOME/Library/Logs/FrameZero Nations" \
    "$HOME/Desktop/FrameZero Clips.command" \
    "$HOME/Desktop/FrameZero Nations.command" \
    "$HOME/Applications/FrameZero Launcher.app" \
    "$HOME/Applications/FrameZero.app" \
    "$HOME/Applications/FrameZero Clips.app" \
    "$HOME/Applications/FrameZero Nations.app" \
    "$HOME/Applications/Iniciar Instalador FrameZero.app" \
    "$HOME/Movies/FrameZero_Cortes"* \
    "$HOME/Documents/FrameZero_Cortes"* \
    "$HOME/Desktop/FrameZero_Cortes"* 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents"/com.framezero*.plist "$HOME/Library/LaunchAgents"/br.com.framezero*.plist 2>/dev/null || true
  sudo rm -rf /Library/Application\ Support/FrameZero* /Library/LaunchAgents/com.framezero*.plist /Library/LaunchDaemons/com.framezero*.plist 2>/dev/null || true
  sudo rm -rf /Applications/FrameZero*.app /Applications/"FrameZero Clips"*.app /Applications/"FrameZero Nations"*.app /Applications/"Iniciar Instalador FrameZero.app" 2>/dev/null || true

  echo "Removendo configuracoes completas do OBS e plugins instalados no usuario..."
  rm -rf "$OBS_USER" 2>/dev/null || true

  echo "Removendo configuracoes completas do OBS e plugins instalados no sistema..."
  sudo rm -rf "$OBS_SYSTEM" 2>/dev/null || true

  echo "Removendo Aitum Vertical, Aitum Multistream e rastros de plugins OBS..."
  for BASE in "$HOME/Library/Application Support" "/Library/Application Support" "/Applications/OBS.app/Contents" "/Applications/OBS Studio.app/Contents"; do
    [ -d "$BASE" ] || continue
    sudo find "$BASE" -maxdepth 6 \( \
      -iname '*aitum*' -o \
      -iname '*vertical*' -o \
      -iname '*multistream*' -o \
      -iname '*multi-stream*' -o \
      -iname '*obs-vertical-canvas*' -o \
      -iname '*obs-aitum-multistream*' -o \
      -iname '*obs-multi-rtmp*' -o \
      -iname '*face*tracker*' -o \
      -iname '*source-record*' \
    \) -exec rm -rf {} + 2>/dev/null || true
  done

  echo "Removendo recibos de pacotes relacionados..."
  pkgutil --pkgs 2>/dev/null | grep -Ei 'aitum|vertical|multistream|multi-stream|obs-vertical|obs.*multi|blackhole|existential|existentialaudio|face.*tracker|source.*record|framezero' | while read -r PKG; do
    sudo pkgutil --forget "$PKG" >/dev/null 2>&1 || true
  done

  echo "Removendo BlackHole da raiz do macOS..."
  if [ -d "/Library/Audio/Plug-Ins/HAL" ]; then
    cd /Library/Audio/Plug-Ins/HAL || true
    sudo rm -rf BlackHole*.driver *BlackHole* *blackhole* 2>/dev/null || true
  fi
  sudo rm -rf     /Library/Audio/Plug-Ins/HAL/BlackHole*.driver     /Library/Audio/Plug-Ins/HAL/*BlackHole*     /Library/Audio/Plug-Ins/HAL/*blackhole*     /Library/Extensions/BlackHole*.kext     /Library/Extensions/*BlackHole*     /Library/Receipts/*BlackHole*     /Library/LaunchDaemons/*BlackHole*     /Library/LaunchAgents/*BlackHole*     /Applications/BlackHole*.app     /var/db/receipts/*BlackHole*     /var/db/receipts/*blackhole*     /usr/local/lib/*BlackHole*     /usr/local/share/*BlackHole* 2>/dev/null || true
  sudo killall coreaudiod >/dev/null 2>&1 || true

  echo
  echo "[OK] Desinstalacao total concluida."
  echo "O OBS.app nao foi apagado, mas as configs/plugins do OBS foram removidos."
  echo "Se BlackHole/Aitum ainda aparecerem, reinicie o Mac uma vez."
  echo
  read -r -p "Pressione Enter para sair..." _
}

run_plugin_check_if_clips_installed() {
  PLUGIN_SCRIPT="$HOME/Library/Application Support/obs-studio/FrameZero/FRAMEZERO-INSTALL-OBS-PLUGINS-MAC.command"
  if [ -f "$PLUGIN_SCRIPT" ]; then
    chmod +x "$PLUGIN_SCRIPT" 2>/dev/null || true
    echo ""
    echo "Verificando plugins obrigatórios do OBS antes de continuar..."
    bash "$PLUGIN_SCRIPT" || return 1
  else
    echo ""
    echo "AVISO: instalador de plugins do Clips não encontrado. Instale o FrameZero Clips primeiro para preparar BlackHole/Aitum/Face Tracker."
  fi
  return 0
}

main_menu() {
  while true; do
    brand_header
    echo "$(T welcome)"
    echo "$(T source)"
    echo
    echo "$(T version): ${LATEST_VERSION:-?} - ${RELEASE_NAME:-?}"
    echo
    echo "$(T menu_title)"
    echo
    echo "[1] Instalar FrameZero Clips + Nations"
    echo "[2] Instalar somente FrameZero Clips"
    echo "[3] Instalar somente o pacote adicional Nations"
    echo "[4] Verificar atualizações"
    echo "[5] Desinstalar FrameZero completo"
    echo "[6] Sair"
    echo
    read -r -p "$(T choose): " OPCAO
    case "$OPCAO" in
      1) FRAMEZERO_INSTALL_WITH_NATIONS=1 FRAMEZERO_SKIP_LAUNCH=1 FRAMEZERO_AUTO_INSTALL=clean download_and_run "$MAC_URL" "clips.zip" "*FRAMEZERO*CLIPS*.command" "$(T downloading_clips)" && FRAMEZERO_NATIONS_CORE_ONLY=1 FRAMEZERO_INCLUDE_TMP_TARGETS=0 install_nations && run_plugin_check_if_clips_installed && start_nations_languages_background && launch_clips_after_install; echo; echo "$(T done)"; pause_menu ;;
      2) FRAMEZERO_INSTALL_WITH_NATIONS=0 FRAMEZERO_AUTO_INSTALL=clean download_and_run "$MAC_URL" "clips.zip" "*FRAMEZERO*CLIPS*.command" "$(T downloading_clips)"; echo; echo "$(T done)"; pause_menu ;;
      3) FRAMEZERO_INSTALL_WITH_NATIONS=1 install_nations && run_plugin_check_if_clips_installed; echo; echo "$(T done)"; pause_menu ;;
      4) load_manifest; pause_menu ;;
      5) uninstall_all; echo; echo "$(T done)"; pause_menu ;;
      6) exit 0 ;;
      *) echo "$(T invalid)"; pause_menu ;;
    esac
  done
}

if [ "${1:-}" = "--nations-langs-background" ]; then
  welcome
  load_manifest || exit 1
  FRAMEZERO_NATIONS_LANGS_ONLY=1 FRAMEZERO_INCLUDE_TMP_TARGETS=0 install_nations
  exit $?
fi

welcome
load_manifest || true
self_update_if_needed || true
main_menu
