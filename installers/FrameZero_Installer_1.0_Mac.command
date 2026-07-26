#!/bin/bash
set -u
trap 'RC=$?; if [ "$RC" -ne 0 ]; then echo; echo "[ERRO] A instalação encontrou um problema."; read -r -p "Pressione ENTER para fechar..." _; fi' EXIT

VERSION_URL="https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json"
TMP="${TMPDIR:-/tmp}/FrameZeroInstaller1123"
MANIFEST="$TMP/version.json"
ROOT="$HOME/Library/Application Support/obs-studio/FrameZero"
APP="$ROOT/app"
mkdir -p "$TMP"
ARCH="$(uname -m 2>/dev/null || echo unknown)"
[ "$ARCH" = "arm64" ] && ENGINE="mlx-whisper" || ENGINE="faster-whisper"
[ "$ARCH" = "arm64" ] && PLATFORM="Apple Silicon" || PLATFORM="Intel"

header(){ clear; cat <<EOF
============================================================
          FrameZero Clips Installer 1.1.23 - macOS
============================================================
 Mac detectado: $PLATFORM ($ARCH)
 Motor local: $ENGINE
============================================================
EOF
}

json(){ python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],''))" "$MANIFEST" "$1" 2>/dev/null || plutil -extract "$1" raw -o - "$MANIFEST" 2>/dev/null || true; }
load(){ curl -fL "$VERSION_URL?cb=$(date +%s)" -o "$MANIFEST" || return 1; MAC_URL="$(json mac_url)"; LATEST="$(json latest_version)"; NAME="$(json release_name)"; }
python_bin(){ for P in /usr/local/bin/python3 /opt/homebrew/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 "$(command -v python3 2>/dev/null || true)"; do [ -n "$P" ] && [ -x "$P" ] && { echo "$P"; return 0; }; done; return 1; }

patch_all_scripts(){
  DIR="$1"; PY="$(python_bin)" || return 1
  "$PY" - "$DIR" <<'PY'
import os,re,sys
root=sys.argv[1]
changed=[]
patterns=[
 r'(?ms)^\s*if\s+.*(?:uname\s+-m|ARCH|MACHINE_ARCH).*?(?:!=|<>).*?arm64.*?;?\s*then\s*\n.*?(?:exige|requires).*?Apple Silicon.*?\n\s*fi\s*',
 r'(?ms)^\s*if\s+.*?(?:x86_64|Intel).*?;?\s*then\s*\n.*?(?:exige|requires).*?Apple Silicon.*?\n\s*fi\s*',
]
for base,_,files in os.walk(root):
    for name in files:
        if not (name.endswith(('.command','.sh','.bash')) or 'install' in name.lower()):
            continue
        p=os.path.join(base,name)
        try: raw=open(p,'r',encoding='utf-8',errors='ignore').read()
        except Exception: continue
        new=raw
        for pat in patterns:
            new=re.sub(pat,'echo "OK: Mac Intel autorizado pelo instalador universal."\n',new)
        lines=new.splitlines(True)
        for i,line in enumerate(lines):
            low=line.lower()
            if ('exige mac apple silicon' in low or 'requires apple silicon' in low) and ('erro' in low or 'error' in low):
                start=i
                while start>=0 and not lines[start].lstrip().startswith('if '): start-=1
                end=i
                while end<len(lines) and lines[end].strip()!='fi': end+=1
                if start>=0 and end<len(lines):
                    lines[start:end+1]=['echo "OK: Mac Intel autorizado pelo instalador universal."\n']
                else:
                    lines[i]='echo "OK: Mac Intel autorizado pelo instalador universal."\n'
                new=''.join(lines)
                break
        if new!=raw:
            open(p,'w',encoding='utf-8').write(new); changed.append(p)
print('Scripts corrigidos:',len(changed))
for p in changed: print(' -',p)
PY
  if grep -RniE 'exige Mac Apple Silicon|requires Apple Silicon' "$DIR" --include='*.command' --include='*.sh' 2>/dev/null; then
    echo "[ERRO] Ainda existe trava Apple Silicon no pacote extraído."
    return 1
  fi
  echo "[OK] Todas as travas Apple Silicon foram removidas."
}

prepare_intel(){
  [ "$ARCH" = "x86_64" ] || return 0
  PY="$(python_bin)" || { echo "[ERRO] Python 3 não encontrado."; return 1; }
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
  ZIP="$TMP/clips.zip"; DIR="$TMP/package"; rm -rf "$DIR"; mkdir -p "$DIR"
  curl -fL "$MAC_URL?cb=$(date +%s)" -o "$ZIP" || return 1
  unzip -q -o "$ZIP" -d "$DIR" || return 1
  [ "$ARCH" = "x86_64" ] && patch_all_scripts "$DIR"
  SCRIPT="$(find "$DIR" -type f -iname '*clips*.command' | head -n1)"
  [ -n "$SCRIPT" ] || SCRIPT="$(find "$DIR" -type f -name '*.command' | head -n1)"
  [ -n "$SCRIPT" ] || { echo "[ERRO] Instalador interno não encontrado."; return 1; }
  chmod +x "$SCRIPT"; xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true
  FRAMEZERO_MAC_ARCH="$ARCH" FRAMEZERO_TRANSCRIPTION_ENGINE="$ENGINE" FRAMEZERO_INSTALL_WITH_NATIONS=0 FRAMEZERO_AUTO_INSTALL=clean bash "$SCRIPT" || return 1
  prepare_intel || return 1
  echo "[OK] FrameZero Clips instalado para $PLATFORM."
}

load || true
while true; do
 header; echo "Versão disponível: ${LATEST:-?} - ${NAME:-?}"; echo
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
