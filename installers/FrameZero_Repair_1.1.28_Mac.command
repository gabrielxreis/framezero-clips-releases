#!/bin/bash
set -u
export TERM="${TERM:-xterm-256color}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
APP="$ROOT/app"
VENV="$APP/venv"
SYSTEM_APP="/Applications/FrameZero Clips.app"
USER_APP="$HOME/Applications/FrameZero Clips.app"
LOG_DIR="$HOME/Library/Logs/FrameZero"
LOG="$LOG_DIR/framezero-repair-1.1.28.log"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG") 2>&1

clear 2>/dev/null || true
cat <<'MSG'
============================================================
      FRAMEZERO CLIPS - REPARO MAC INTEL 1.1.28
============================================================
Este reparo corrige:
- loop de atualização Core/instalador
- bloqueio Apple Silicon
- ambiente Python em pasta incorreta
- compatibilidade mlx_whisper via faster-whisper
- TERM ausente ao abrir pelo app
============================================================
MSG

if [ "$(uname -m)" != "x86_64" ]; then
  echo "[ERRO] Este reparo é específico para Mac Intel (x86_64)."
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
fi
if [ ! -d "$ROOT" ]; then
  echo "[ERRO] Instalação não encontrada em: $ROOT"
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
fi

echo "Encerrando processos antigos..."
pkill -f "$ROOT" 2>/dev/null || true
pkill -f "servidor.py" 2>/dev/null || true
for PORT in 8765 8766 8889; do
  PID="$(lsof -ti tcp:$PORT 2>/dev/null || true)"
  [ -n "$PID" ] && kill -9 $PID 2>/dev/null || true
done
sleep 2

BACKUP="$ROOT/.intel-repair-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for F in INICIAR.command INICIAR-FRAMEZERO.command FrameZero-Update-Check.command INSTALAR-MAC.command; do
  [ -f "$ROOT/$F" ] && cp "$ROOT/$F" "$BACKUP/$F"
done

echo "Removendo travas Apple Silicon dos scripts instalados..."
while IFS= read -r -d '' FILE; do
  /usr/bin/perl -0777 -i -pe 's/if\s+\[\s*"?\$?\(?(?:uname\s+-m|ARCH|MACHINE_ARCH)[^\n]*\n(?:(?!\nfi\b).)*?(?:exige Mac Apple Silicon|requires Apple Silicon|M1\/M2\/M3\/M4).*?\nfi/echo "OK: Mac Intel autorizado pelo instalador universal."/gis' "$FILE" 2>/dev/null || true
  /usr/bin/perl -i -pe 'if (/ERRO:.*(?:exige Mac Apple Silicon|Apple Silicon \(M1\/M2\/M3\/M4\)|não é Apple Silicon)/i) { $_="echo \"OK: Mac Intel autorizado pelo instalador universal.\"\n" }' "$FILE" 2>/dev/null || true
  chmod +x "$FILE" 2>/dev/null || true
done < <(find "$ROOT" -type f \( -name '*.command' -o -name '*.sh' -o -name '*.bash' \) -print0)

cat > "$ROOT/FrameZero-Update-Check.command" <<'UPDATER'
#!/bin/bash
set +e
export TERM="${TERM:-xterm-256color}"
ROOT_DIR="${ROOT_DIR:-$HOME/Library/Application Support/obs-studio/FrameZero}"
MANIFEST="${TMPDIR:-/tmp}/framezero-core-version-$$.json"
URL="https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json"
trap 'rm -f "$MANIFEST" 2>/dev/null || true' EXIT

echo "============================================================"
echo " VERIFICANDO VERSÃO DO CORE FRAMEZERO"
echo "============================================================"
if ! curl -fsSL --connect-timeout 10 -H "Cache-Control: no-cache" "$URL?ts=$(date +%s)" -o "$MANIFEST"; then
  echo "AVISO: não foi possível consultar o GitHub. Abrindo versão local."
  exit 0
fi
REMOTE_CORE="$(plutil -extract latest_version raw -o - "$MANIFEST" 2>/dev/null || echo 1.1.19)"
LOCAL_CORE="1.1.19"
if [ -f "$ROOT_DIR/framezero_local_version.json" ]; then
  LOCAL_CORE="$(plutil -extract version raw -o - "$ROOT_DIR/framezero_local_version.json" 2>/dev/null || echo 1.1.19)"
fi
echo "Core local: $LOCAL_CORE"
echo "Core disponível: $REMOTE_CORE"
if [ "$REMOTE_CORE" != "$LOCAL_CORE" ]; then
  echo "Há uma nova versão do Core, mas a atualização automática está desativada no Mac Intel até existir pacote Intel validado."
else
  echo "FrameZero Core já está atualizado."
fi
exit 0
UPDATER
chmod +x "$ROOT/FrameZero-Update-Check.command"

cat > "$ROOT/INICIAR.command" <<'LAUNCH'
#!/bin/bash
set +e
export TERM="${TERM:-xterm-256color}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
ROOT_DIR="$HOME/Library/Application Support/obs-studio/FrameZero"
cd "$ROOT_DIR" || exit 1
[ -x "$ROOT_DIR/FrameZero-Update-Check.command" ] && bash "$ROOT_DIR/FrameZero-Update-Check.command" || true
exec /bin/bash "$ROOT_DIR/INICIAR-FRAMEZERO.command"
LAUNCH
chmod +x "$ROOT/INICIAR.command"

MAIN="$ROOT/INICIAR-FRAMEZERO.command"
if [ ! -f "$MAIN" ]; then
  echo "[ERRO] INICIAR-FRAMEZERO.command não encontrado."
  exit 1
fi

/usr/bin/perl -0777 -i -pe 's/^#!\/bin\/bash\n/#!\/bin\/bash\nexport TERM="\${TERM:-xterm-256color}"\nexport PATH="\/usr\/local\/bin:\/opt\/homebrew\/bin:\/usr\/bin:\/bin:\/usr\/sbin:\/sbin:\$PATH"\n/' "$MAIN"
/usr/bin/perl -i -pe 's#^VENV_DIR=.*#VENV_DIR="$APP_DIR/venv"#' "$MAIN"
/usr/bin/perl -0777 -i -pe 's/check_for_updates\nUPD_RC=\$\?\nif \[ "\$UPD_RC" = "10" \]; then.*?\nfi/echo "Atualização automática do pacote desativada no Mac Intel; verificando apenas a versão do Core."/s' "$MAIN"
/usr/bin/perl -0777 -i -pe 's/if \[ "\$\(uname -m\)" != "arm64" \]; then\n.*?\nfi/echo "OK: Mac Intel autorizado."/s' "$MAIN"
chmod +x "$MAIN"

cat > "$ROOT/framezero_local_version.json" <<'JSON'
{
  "app": "FrameZero Clips",
  "version": "1.1.19",
  "clips_version": "1.1.19",
  "core_version": "1.1.19",
  "installer_version": "1.1.26",
  "installer_ui_version": "1.1.26",
  "online_installer_version": "1.1.26",
  "platform": "mac-intel",
  "transcription_engine": "faster-whisper"
}
JSON

find_python3(){
  for P in /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /opt/homebrew/bin/python3 "$(command -v python3 2>/dev/null || true)"; do
    [ -n "$P" ] && [ -x "$P" ] && { echo "$P"; return 0; }
  done
  return 1
}

PY="$(find_python3 || true)"
if [ -z "$PY" ]; then
  echo "[ERRO] Python 3 não encontrado. Instale Python 3.12 e execute este reparo novamente."
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
fi

echo "Python encontrado: $PY"
rm -rf "$VENV"
"$PY" -m venv "$VENV" || exit 1
VPY="$VENV/bin/python"
"$VPY" -m pip install --upgrade pip setuptools wheel || exit 1

REQ="$APP/requirements.txt"
FILTERED="${TMPDIR:-/tmp}/framezero-intel-requirements-$$.txt"
if [ -f "$REQ" ]; then
  grep -Eiv '^[[:space:]]*(mlx|mlx-whisper|mlx_whisper|mlx-lm)([<>=!~[:space:]]|$)' "$REQ" > "$FILTERED" || true
  [ -s "$FILTERED" ] && "$VPY" -m pip install -r "$FILTERED" || true
fi
"$VPY" -m pip install "faster-whisper>=1.1,<2" "ctranslate2>=4,<5" numpy sounddevice websockets obsws-python requests openai scipy imageio-ffmpeg || exit 1
rm -f "$FILTERED" 2>/dev/null || true

cat > "$APP/mlx_whisper.py" <<'PYSHIM'
"""Compatibilidade mlx_whisper para Mac Intel usando faster-whisper."""
from __future__ import annotations
import os
from functools import lru_cache
from typing import Any
from faster_whisper import WhisperModel

@lru_cache(maxsize=4)
def _model(name: str, device: str, compute_type: str) -> WhisperModel:
    return WhisperModel(name, device=device, compute_type=compute_type)

def transcribe(audio: Any, path_or_hf_repo: str | None = None, **kwargs: Any) -> dict[str, Any]:
    model_name = os.getenv("FRAMEZERO_INTEL_WHISPER_MODEL", "small")
    device = os.getenv("FRAMEZERO_INTEL_WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("FRAMEZERO_INTEL_WHISPER_COMPUTE", "int8")
    language = kwargs.pop("language", None)
    task = kwargs.pop("task", "transcribe")
    beam_size = int(kwargs.pop("beam_size", 5) or 5)
    vad_filter = bool(kwargs.pop("vad_filter", True))
    model = _model(model_name, device, compute_type)
    segments, info = model.transcribe(audio, language=language, task=task, beam_size=beam_size, vad_filter=vad_filter)
    out_segments = []
    text_parts = []
    for seg in segments:
        text = (seg.text or "").strip()
        text_parts.append(text)
        out_segments.append({
            "id": getattr(seg, "id", len(out_segments)),
            "seek": getattr(seg, "seek", 0),
            "start": float(seg.start),
            "end": float(seg.end),
            "text": text,
            "tokens": list(getattr(seg, "tokens", []) or []),
            "temperature": float(getattr(seg, "temperature", 0.0) or 0.0),
            "avg_logprob": float(getattr(seg, "avg_logprob", 0.0) or 0.0),
            "compression_ratio": float(getattr(seg, "compression_ratio", 0.0) or 0.0),
            "no_speech_prob": float(getattr(seg, "no_speech_prob", 0.0) or 0.0),
        })
    return {
        "text": " ".join(x for x in text_parts if x).strip(),
        "segments": out_segments,
        "language": getattr(info, "language", language),
        "duration": float(getattr(info, "duration", 0.0) or 0.0),
    }
PYSHIM

mkdir -p "$ROOT/.framezero"
rm -rf "$ROOT/.framezero/venv" 2>/dev/null || true
ln -s "$VENV" "$ROOT/.framezero/venv"

if [ -f "$HOME/.zprofile" ] && grep -q '/opt/homebrew/bin/brew' "$HOME/.zprofile"; then
  cp "$HOME/.zprofile" "$HOME/.zprofile.before-framezero-intel-repair"
  grep -v '/opt/homebrew/bin/brew' "$HOME/.zprofile.before-framezero-intel-repair" > "$HOME/.zprofile"
  if [ -x /usr/local/bin/brew ]; then
    printf '\neval "$(/usr/local/bin/brew shellenv)"\n' >> "$HOME/.zprofile"
  fi
fi

APP_TARGET="$SYSTEM_APP"
[ -d "$APP_TARGET" ] || APP_TARGET="$USER_APP"
if [ -d "$APP_TARGET" ]; then
  EXEC="$APP_TARGET/Contents/MacOS/FrameZero Clips"
  mkdir -p "$(dirname "$EXEC")"
  cat > "$EXEC" <<'APPEXEC'
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
LOG_DIR="$HOME/Library/Logs/FrameZero"
LOG="$LOG_DIR/framezero-launch.log"
mkdir -p "$LOG_DIR"
cd "$ROOT" || exit 1
echo "==== FrameZero iniciado em $(date) ====" >> "$LOG"
/bin/bash "$ROOT/INICIAR.command" >> "$LOG" 2>&1 &
PID=$!
sleep 10
if kill -0 "$PID" 2>/dev/null || pgrep -f "servidor.py" >/dev/null 2>&1; then
  while kill -0 "$PID" 2>/dev/null || pgrep -f "servidor.py" >/dev/null 2>&1; do sleep 5; done
  exit 0
fi
osascript -e 'display dialog "O FrameZero não conseguiu iniciar. O diagnóstico será aberto." buttons {"OK"} default button "OK" with icon stop' >/dev/null 2>&1 || true
open "$LOG" 2>/dev/null || true
exit 1
APPEXEC
  chmod +x "$EXEC"
  xattr -dr com.apple.quarantine "$APP_TARGET" 2>/dev/null || true
  codesign --force --deep --sign - "$APP_TARGET" >/dev/null 2>&1 || true
fi

xattr -dr com.apple.quarantine "$ROOT" 2>/dev/null || true
chmod +x "$ROOT"/*.command 2>/dev/null || true

echo "Testando dependências Intel..."
cd "$APP"
if ! "$VPY" - <<'PYTEST'
import mlx_whisper, numpy, sounddevice, websockets
from faster_whisper import WhisperModel
print("Dependências Intel OK")
PYTEST
then
  echo "[ERRO] Falha no teste das dependências. Veja: $LOG"
  read -r -p "Pressione ENTER para fechar..." _
  exit 1
fi

echo "[OK] Reparo Intel concluído."
echo "Abrindo FrameZero Clips..."
if [ -d "$APP_TARGET" ]; then
  open -n "$APP_TARGET"
else
  /bin/bash "$ROOT/INICIAR.command"
fi

echo "Log do reparo: $LOG"
read -r -p "Pressione ENTER para fechar esta janela..." _
