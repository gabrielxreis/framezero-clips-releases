"""
FrameZero Clips 1.1.8 - v1.0.108 Worship Scoring & Song Naming.

Recursos:
  1. Transcreve localmente; VPS ASR desativada no fluxo ao vivo.
  2. Timestamp zera quando o OBS comeca a gravar/transmitir.
  3. Deteccao de cortes:
       - SEM chave OpenAI: modo automatico local com cunho viral/emocional
         (historia, pico de voz, tensao, virada, frase de impacto e CTA).
       - COM chave OpenAI: opcional; o GPT melhora titulo/razao dos cortes.
  4. Clipe durante a live via Replay Buffer do OBS:
       - automatico quando o detector local/IA aponta um momento forte (acima do limiar)
       - manual pelo botao no painel
     O OBS salva um arquivo so daquele trecho, na hora.
  5. Botao no painel pra colar/salvar a chave da OpenAI (guardada em config.json).

A transcricao agora usa MLX MLX Whisper local no Mac Apple Silicon.
Sem VPS, sem FunASR, sem SenseVoice e sem /transcribe.
"""

import asyncio
import json
import os
import re
import time
import shutil
import gc
import threading
import queue
import io
import wave
import tempfile
import platform
import base64
from pathlib import Path

import numpy as np

# Dependências avançadas opcionais. Não são obrigatórias para iniciar o Core.
# Se não existirem, o FrameZero usa o detector leve para não quebrar máquinas fracas.
try:
    import scipy.signal as _fz_scipy_signal
    FZ_SCIPY_OK = True
except Exception:
    _fz_scipy_signal = None
    FZ_SCIPY_OK = False

try:
    import librosa as _fz_librosa
    FZ_LIBROSA_OK = True
except Exception:
    _fz_librosa = None
    FZ_LIBROSA_OK = False

# Fix: no Windows ARM64, sounddevice procura libportaudioarm64.dll mas o pacote
# instala com nome libportaudio64bit.dll. Copia antes de importar.
try:
    import importlib.util, shutil as _shutil
    _sd_spec = importlib.util.find_spec("_sounddevice_data")
    if _sd_spec:
        _pb = Path(_sd_spec.submodule_search_locations[0]) / "portaudio-binaries"
        _arm = _pb / "libportaudioarm64.dll"
        _x64 = _pb / "libportaudio64bit.dll"
        if not _arm.exists() and _x64.exists():
            _shutil.copy2(_x64, _arm)
except Exception:
    pass

try:
    import sounddevice as sd
    SOUNDDEVICE_OK = True
    SOUNDDEVICE_ERROR = ""
except Exception as e:
    sd = None
    SOUNDDEVICE_OK = False
    SOUNDDEVICE_ERROR = str(e)
    print(f"[audio] sounddevice/PortAudio indisponivel: {e}")
    print("[audio] O servidor vai continuar sem captura direta do dispositivo. Use o plugin/audio via OBS ou instale/repare o driver de audio se precisar.")

try:
    import soundcard as sc
    SOUNDCARD_OK = True
    SOUNDCARD_ERROR = ""
except Exception as e:
    sc = None
    SOUNDCARD_OK = False
    SOUNDCARD_ERROR = str(e)

try:
    import mlx_whisper
    TEM_MLX = True
except Exception:
    mlx_whisper = None
    TEM_MLX = False
try:
    from faster_whisper import WhisperModel
    TEM_FASTER_WHISPER = True
except Exception:
    WhisperModel = None
    TEM_FASTER_WHISPER = False
import websockets
import obsws_python as obs
import logging
logging.getLogger("websockets.server").setLevel(logging.CRITICAL)

# ----------------------------- VERSAO DO PLUGIN -----------------------------
PLUGIN_NAME = "FrameZero Clips"
PLUGIN_VERSION = "1.1.8"
PLUGIN_RELEASE = "FrameZero Clips 1.1.8"
PLUGIN_MIN_PANEL_VERSION = "1.1.0"

def plugin_platform():
    sistema = platform.system().lower()
    if sistema.startswith("win"):
        return "windows"
    if sistema == "darwin":
        return "mac"
    return sistema or "unknown"

def plugin_version_payload():
    return {
        "tipo": "plugin_version",
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "release": PLUGIN_RELEASE,
        "min_panel_version": PLUGIN_MIN_PANEL_VERSION,
        "platform": plugin_platform(),
        "plugin_installed": True,
        "installed": True,
        "versao": PLUGIN_VERSION,
        "plugin_version": PLUGIN_VERSION,
        "global_language_rules": True,
        "ai_boost_available": True,
    }



# ----------------------------- VERSION / UPDATE STATUS -----------------------------
VERSION_MANIFEST_URL = "https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json"
LOCAL_INSTALLER_VERSION = "1.0.48"


def _safe_json_file(path):
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _stable_root_dir():
    # app/servidor.py -> FrameZero/
    try:
        return PASTA.parent
    except Exception:
        return Path.cwd()


def _version_tuple(v):
    try:
        return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4])
    except Exception:
        return (0,)


def _is_remote_newer(remote, local):
    rt = _version_tuple(remote)
    lt = _version_tuple(local)
    ln = max(len(rt), len(lt))
    rt += (0,) * (ln - len(rt))
    lt += (0,) * (ln - len(lt))
    return rt > lt


def framezero_version_status(fetch_remote=True):
    local_file = _stable_root_dir() / "framezero_local_version.json"
    local_data = _safe_json_file(local_file)
    local_version = str(local_data.get("version") or local_data.get("latest_version") or PLUGIN_VERSION)
    local_installer = str(local_data.get("installer_version") or local_data.get("online_installer_version") or config_usuario.get("installer_version") or LOCAL_INSTALLER_VERSION)
    payload = {
        "tipo": "version_status_result",
        "type": "version_status_result",
        "ok": True,
        "app": PLUGIN_NAME,
        "local_version": local_version,
        "local_clips_version": local_version,
        "local_installer_version": local_installer,
        "current_version": local_version,
        "current_installer_version": local_installer,
        "update_available": False,
        "required_update": False,
        "force_update": False,
        "version_manifest_url": VERSION_MANIFEST_URL,
        "platform": plugin_platform(),
    }
    if not fetch_remote:
        return payload
    try:
        if requests is None:
            raise RuntimeError("requests indisponível")
        r = requests.get(VERSION_MANIFEST_URL, timeout=7, headers={"User-Agent":"FrameZero-Core"})
        r.raise_for_status()
        remote = r.json()
        latest_version = str(remote.get("latest_version") or remote.get("version") or local_version)
        latest_installer = str(remote.get("online_installer_version") or remote.get("installer_version") or remote.get("installer_ui_version") or local_installer)
        force = bool(remote.get("force_update", False) or remote.get("required_update", False))
        needs = force or _is_remote_newer(latest_version, local_version) or _is_remote_newer(latest_installer, local_installer)
        payload.update({
            "remote_ok": True,
            "latest_version": latest_version,
            "latest_clips_version": latest_version,
            "latest_installer_version": latest_installer,
            "update_available": bool(needs),
            "required_update": bool(force),
            "force_update": bool(force),
            "release_name": remote.get("release_name") or remote.get("version_name") or remote.get("version_label"),
            "release_notes": remote.get("release_notes") or remote.get("notes") or remote.get("message"),
            "mac_url": remote.get("mac_url"),
            "windows_url": remote.get("windows_url"),
            "manifest": remote,
        })
    except Exception as e:
        payload.update({"remote_ok": False, "remote_error": str(e)})
    return payload


def framezero_start_update_now():
    root = _stable_root_dir()
    system = platform.system().lower()
    try:
        import subprocess
        if system == "darwin":
            script = root / "INICIAR-FRAMEZERO.command"
            if script.exists():
                subprocess.Popen(["/bin/bash", str(script)], cwd=str(root), env={**os.environ, "FRAMEZERO_UPDATE_NOW":"1"})
                return True, "Atualizador iniciado. O FrameZero pode reiniciar durante a atualização."
        elif system.startswith("win"):
            for name in ("INICIAR-FRAMEZERO-WINDOWS.bat", "INICIAR-WINDOWS.bat"):
                script = root / name
                if script.exists():
                    subprocess.Popen(["cmd.exe", "/c", "start", "FrameZero Update", str(script)], cwd=str(root), env={**os.environ, "FRAMEZERO_UPDATE_NOW":"1"})
                    return True, "Atualizador iniciado. O FrameZero pode reiniciar durante a atualização."
        return False, "Não encontrei o launcher local para iniciar a atualização. Abra o app FrameZero novamente."
    except Exception as e:
        return False, str(e)

try:
    import requests
except Exception:
    requests = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ----------------------------- CONFIGURACAO -----------------------------

PASTA = Path(__file__).parent
ARQ_CONFIG = PASTA / "config.json"

CONFIG = {
    "modelo": "small",
    "modelo_ao_vivo": "small",
    "modelo_refino": "large-v3-turbo",
    "idioma": "pt",
    # v1.1 Global Language Rules: um idioma por vez, sem modo automático por padrão.
    "language_profile": "pt-BR",
    "global_language_mode": "standard",       # standard=leve; ai_boost=opcional com OpenAI/Gemini
    "source_language": "pt",
    "output_language": "pt-BR",
    "live_translation_enabled": False,
    "live_translation_provider": "gemini",    # gemini ou openai
    "live_translation_target": "en",
    "phrase_ai_enabled": False,               # análise frase por frase, desligado por padrão
    "phrase_ai_provider": "gemini",
    "sample_rate": 16000,
    "canais": 1,
    "bloco_segundos": 4.0,
    "bloco_segundos_ao_vivo_local": 4.0,
    "beam_size_ao_vivo": 5,
    "vps_modo_tempo_real": True,
    "vps_bloco_segundos_ao_vivo": 2.5,
    "segurar_frase_incompleta_ao_vivo": False,
    "beam_size": 7,
    # MLX Whisper local usa prompt curto em PT-BR; refino contextual fica na VPS/Ollama.
    "prompt_transcricao": "",
    "transcricao_motor": "padrao",  # padrao=MLX local; turbo=OpenAI Realtime
    "transcricao_ativa": True,
    "openai_realtime_model": "gpt-realtime-whisper",
    "openai_realtime_delay": "high",
    "openai_realtime_commit_segundos": 12.0,
    "gemini_api_key": "",
    "gemini_enabled": False,
    "gemini_model": "gemini-2.5-flash-lite",
    # Gemini economico: analisa menos vezes, mas com janela movel grande.
    "gemini_intervalo_seg": 45.0,
    "gemini_janela_contexto_seg": 180.0,
    "gemini_min_chars": 700,
    "gemini_max_chars": 9000,
    "gemini_timeout_seg": 35.0,
    "gemini_tutorial_url": "https://ai.google.dev/gemini-api/docs/api-key",
    "corte_seguro": True,
    "agrupar_assunto": True,
    "local_asr_engine": "mlx-whisper",
    "whisper_local_perfil": "leve",          # leve ou pro
    "whisper_local_modelo_leve": "mlx-community/whisper-large-v3-turbo",
    "whisper_local_modelo_pro": "mlx-community/whisper-large-v3",
    "whisper_local_device_cpu": "cpu",
    "whisper_local_compute_type_cpu": "int8",
    "whisper_local_compute_type_gpu": "float16",
    "whisper_local_usuario_tem_gpu": False,
    "whisper_local_task": "transcribe",
    "whisper_local_language": "pt",
    "forcar_ptbr_local": True,
    "idioma_whisper_local": "pt",
    "correcao_contextual_ao_vivo": True,
    "modelo_ao_vivo_rapido": "base",
    "modelo_ao_vivo_preciso": "small",
    "whisper_local_perfil": "leve",             # leve ou pro
    "whisper_local_usuario_tem_gpu": False,      # usuario informa se o PC tem GPU NVIDIA/CUDA
    "whisper_local_modelo_leve": "mlx-community/whisper-large-v3-turbo",
    "whisper_local_modelo_pro": "mlx-community/whisper-large-v3",
    "whisper_local_device_cpu": "cpu",
    "whisper_local_device_gpu": "cuda:0",
    "whisper_local_sensevoice_aceita_ptbr": False,
    "whisper_local_rejeitar_ingles_em_ptbr": True,
    "whisper_local_fallback_vps_se_invalido": False,
    "whisper_local_baixar_modelo_durante_gravacao": False,
    "whisper_local_vad_model": "fsmn-vad",
    "whisper_local_punc_model": "ct-punc",
    "transcricao_modo": "local",        # Windows/Mac: transcricao local; VPS removida/desativada
    "whisper_vps_base_url": "http://2.25.157.230:8000",
    "transcription_engine": "mlx-whisper",
    "whisper_vps_endpoint": "/transcribe-fastwhisper",
    "whisper_vps_url": "http://2.25.157.230:8000/transcribe-fastwhisper",
    "whisper_vps_token": "framezero_obs_2026",
    "vps_auth_header": "x-api-key",
    "vps_modelo_ia_principal": "criador-cristao:latest",
    "vps_modelo_ia_base": "qwen2.5:3b",
    "vps_modelo_ia_extra": "deepseek-r1:1.5b",
    "vps_ollama_interno": "http://127.0.0.1:11434",
    "whisper_vps_health_endpoint": "/health",
    "whisper_vps_jobs_endpoint": "/jobs",
    "vps_timeout_seg": 45,
    "vps_poll_jobs": True,
    "vps_job_timeout_seg": 90,
    "vps_fallback_local": False,
    "vps_enviar_audio_ao_vivo": False,
    "whisper_vps_analyze_endpoint": "/analyze-text",
    "vps_analisar_com_ia_local": False,
    "vps_analyze_timeout_seg": 120,
    "vps_analyze_min_chars": 80,
    "vps_analyze_live_endpoint": "/analyze-live-chunk",
    "vps_tentar_analyze_live_chunk": False,
    "forcar_blackhole_se_existir": True,
    "forcar_blackhole_input_channels": True,
    "audio_device_index_forcado": None,
    "transcricao_tempo_real_prioridade": True,
    "vps_analyze_async": True,
    "audio_min_rms_para_status": 0.006,
    "dispositivo_audio": None,
    "obs_audio_source_name": "FrameZero Audio",
    "obs_apply_audio_device": True,

    "obs_host": "localhost",
    "obs_porta": 4455,
    "obs_senha": "TROQUE_AQUI",

    "porta_painel": 8765,
    "painel_url": "https://clips.framezeroai.com.br/obs",
    "painel_ws_url": "ws://localhost:8765",
    "usar_painel_web": True,
    # Plugin opcional obs-audio-to-websocket: recebe audio do mixer do OBS.
    # O plugin do OBS conecta AQUI (ele e o cliente, nos somos o servidor).
    "porta_plugin_audio": 8889,
    "rota_plugin_audio": "/audio",

    # Cortes
    "limiar_corte": 60,          # v81e score60: corte em tempo real libera a partir de 60+
    "modo_corte_auto": "local", # local por padrao; OpenAI e apenas reforco opcional
    "cooldown_corte_seg": 60,    # v81: Corte Seguro segura para nao picotar assunto
    "segundos_clipe": 120,       # quanto o Replay Buffer guarda pra tras (ajuste no OBS tambem)
    "intervalo_ia_seg": 15,      # v81: Corte Seguro analisa com mais contexto
    "duracao_corte_min": 35,     # v1.0.103: corte final minimo padrao
    "duracao_corte_max": 90,     # v1.0.103: corte seguro maximo padrao
    "margem_antes_corte": 22,    # segundos antes do pico emocional
    "margem_depois_corte": 14,   # segundos depois do pico emocional
    "corte_exato_automatico": True,
    "usar_srt_como_timecode": True,     # usa timestamps da transcrição/SRT como fonte de corte exato
    "srt_idioma": "pt-BR",
    "srt_caracteres_por_linha": 37,
    "srt_linha_unica": True,
    "srt_quebrar_em_cues": True,
    "corrigir_legenda_contexto": True,
    "finalizacao_contexto_corte": True,  # evita terminar corte no meio da conclusão da frase/ideia
    "modo_contexto_pregacao": True,  # entende historia/ensino/aplicacao antes de cortar
    "preferir_palavra_direcionada": True,  # prioriza trechos aplicáveis ao público
    "historia_precisa_aplicacao": True,  # evita exportar só a história sem a conclusão/palavra
    "tipo_conteudo": "mixed",       # legado: pregacao/musica; v102 aceita mixed/sermon/podcast/worship
    "clip_mode": "mixed",           # mixed, sermon, podcast, worship, bilingual_sermon
    "detectar_musica_pregacao": True, # no modo misto o Core identifica fala/musica sozinho
    "worship_intelligence": "auto",  # auto, off, always: análise musical avançada só quando precisa
    "performance_mode": "auto",      # auto, light, advanced
    "bilingual_context": "auto",     # auto/off/on: pregação EN + tradução PT-BR
    "bilingual_preserve_original_translation": True,
    "bilingual_min_window_sec": 45,
    "bilingual_max_window_sec": 90,
    "smart_cult_service_mode": True,
    "manual_moment": "auto",         # auto, sermon, worship, ministry
    "musica_priorizar_refrao": True,  # em música, prioriza refrão, ponte, clímax e partes bonitas
    "ollama_internet_conectado": True,
    "musica_usar_letra_online": True,
    "musica_refino_online": True,
    "musica_busca_letra_online": True,
    "musica_nao_substituir_sem_confianca": True,
    "musica_confianca_minima_letra": 0.82,
    "musica_preservar_louvor_espontaneo": True,
    "lyrics_reference_source": "web_via_ollama_vps",
    "lyrics_reference_policy": "internet_sugere_audio_manda",
    "vps_transcricao_quase_tempo_real": True,  # usa blocos curtos via VPS para reduzir atraso
    "max_linhas_busca_aplicacao": 18,
    "preferir_fechamento_frase": True,   # tenta terminar em ponto/fechamento natural do SRT
    "contexto_transcricao": "pregação cristã brasileira; nomes bíblicos: Abraão, Sara, Agar, Ismael, Noé, Arca de Noé, Senhor, Deus, serva, timão",
    # SRT limpo no padrão PT-BR.
    # v81j: não geramos mais legenda.ass para manter a pasta do corte mais limpa.
    "subtitle_font_family": "Poppins",
    "subtitle_font_size": 13,
    "subtitle_bold": True,
    "subtitle_alignment": 2,
    "subtitle_primary_color_ass": "&H00FFFFFF",
    "subtitle_outline_color_ass": "&H00000000",
    "subtitle_back_color_ass": "&H80000000",
    "subtitle_outline": 2,
    "subtitle_shadow": 0,
    "corte_exato_busca_seg": 90,     # procura a melhor janela até 90s ao redor do pico
    "corte_exato_score_minimo": 88,  # v81: evita cortes ruins com score alto
    "gerar_mapa_cortes": True,       # CSV/TXT com minutagem exata para pós
    "pasta_principal_cortes": "FrameZero_Cortes",
    # v81j: gera automaticamente as duas entregas principais dentro da mesma pasta do título.
    # Estrutura final: Pasta do Título / Título - 16x9.mp4
    #                  Pasta do Título / Título - 9x16.mp4
    "gerar_versoes_automaticas": True,
    "versoes_corte_automaticas": ["16x9", "9x16"],
    "usar_titulo_no_nome_video": True,
    # Proporcao manual antiga continua existindo como fallback quando o modo automático for desligado.
    "proporcao_corte": "original",

    # Modo Vertical nativo do FrameZero: sem instalar o Aitum.
    # Via WebSocket o OBS nao permite criar uma segunda tela/canvas independente
    # igual ao Aitum; esta funcao automatiza preview 9:16, cena auxiliar e cortes finais verticais.
    "vertical_ativo": False,
    "vertical_cena": "FrameZero Vertical",
    "vertical_proporcao": "9:16",
    "vertical_seguir_pastor": False,
}

# config.json guarda coisas que o usuario muda pelo painel (ex: chave OpenAI)
def carregar_config_usuario():
    if ARQ_CONFIG.exists():
        try:
            return json.loads(ARQ_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def salvar_config_usuario(d):
    atual = carregar_config_usuario()
    atual.update(d)
    ARQ_CONFIG.write_text(json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")

config_usuario = carregar_config_usuario()

def migrar_config_v103():
    """Aplica novos padrões seguros sem apagar preferências avançadas do usuário.
    Se vier das versões 1.0.102/anteriores com 15/45/60s, migra para 35-90s.
    """
    try:
        updates = {}
        mn = int(config_usuario.get("duracao_corte_min", CONFIG.get("duracao_corte_min", 35)) or 35)
        mx = int(config_usuario.get("duracao_corte_max", CONFIG.get("duracao_corte_max", 90)) or 90)
        if mn < 35:
            updates["duracao_corte_min"] = 35
        if mx < 90:
            updates["duracao_corte_max"] = 90
        for k in ("worship_intelligence", "performance_mode", "bilingual_context", "manual_moment"):
            if k not in config_usuario:
                updates[k] = CONFIG.get(k)
        if "smart_cult_service_mode" not in config_usuario:
            updates["smart_cult_service_mode"] = True
        if "bilingual_preserve_original_translation" not in config_usuario:
            updates["bilingual_preserve_original_translation"] = True
        if updates:
            config_usuario.update(updates)
            salvar_config_usuario(updates)
            print(f"[config] migração v1.0.103 aplicada: duração={config_usuario.get('duracao_corte_min')}-{config_usuario.get('duracao_corte_max')}s culto_inteligente={config_usuario.get('smart_cult_service_mode')}")
    except Exception as e:
        print(f"[config] migração v1.0.103 ignorada: {e}")

migrar_config_v103()


# ----------------------------- GLOBAL LANGUAGE RULES v1.1.3 -----------------------------

# O FrameZero trabalha com UM idioma por vez por padrão.
# Não existe modo automático nesta etapa: o usuário escolhe o idioma no painel.
# v1.1.3 prepara TODOS os idiomas exibidos no painel com contexto cristão, padrões de história,
# humor, emoção, frases fortes, hashtags e livros bíblicos para extração de referências.
# AI Boost é opcional e pode habilitar tradução ao vivo e análise frase por frase via OpenAI/Gemini.
LANGUAGE_PROFILES = {
    "pt-BR": {
        "label": "Português Brasil", "whisper_language": "pt", "output_language": "pt-BR",
        "context": "pregação cristã brasileira; pastor falando no púlpito; culto; igreja; referências bíblicas; testemunhos; histórias; brincadeiras; interação com a igreja; momentos emocionantes; aplicação prática; apelo espiritual; fé, esperança, cura e restauração",
        "ai_language": "português brasileiro", "caption_style": "emocional, direto, cristão brasileiro, natural para Reels/TikTok/Shorts",
        "god_terms": {"deus":"Deus", "senhor":"Senhor", "jesus":"Jesus", "cristo":"Cristo", "espirito santo":"Espírito Santo", "espírito santo":"Espírito Santo"},
        "impact_patterns": ["não desista", "nao desista", "Deus está", "Deus não terminou", "receba essa palavra", "eu profetizo", "eu declaro", "chegou a hora", "a partir de hoje", "essa palavra é pra você", "Deus vai fazer", "o Senhor está dizendo", "não acabou"],
        "humor_patterns": ["olha para a pessoa do lado", "quem conhece alguém assim", "tem gente", "sabe aquela pessoa", "cutuca o irmão", "fala para o seu vizinho", "olha pro irmão"],
        "story_patterns": ["eu lembro", "uma vez", "teve um dia", "quando eu era", "deixa eu te contar", "aconteceu comigo", "eu estava", "cheguei em casa"],
        "emotion_patterns": ["choro", "dor", "perda", "medo", "ansiedade", "cura", "milagre", "promessa", "propósito", "recomeço", "restauração"],
        "hashtags": ["#pregação", "#fé", "#Jesus", "#Deus", "#igreja", "#reelscristao", "#palavradedeus"],
    },
    "en": {
        "label": "English", "whisper_language": "en", "output_language": "en",
        "context": "Christian sermon in English; pastor preaching; church service; pulpit stories; Bible references; testimony; jokes; audience interaction; emotional moments; practical application; altar call; hope, healing, restoration and faith",
        "ai_language": "English", "caption_style": "clear, inspirational, natural for church social media, Reels, TikTok and Shorts",
        "god_terms": {"god":"God", "lord":"Lord", "jesus":"Jesus", "christ":"Christ", "holy spirit":"Holy Spirit"},
        "impact_patterns": ["don't give up", "God is not finished", "this word is for you", "I declare", "I believe", "the Lord is saying", "your story is not over", "God is still working", "this is your season", "it is not over", "receive this word"],
        "humor_patterns": ["look at your neighbor", "tell your neighbor", "you know someone like this", "some of y'all", "some of you", "don't act like", "can I be honest"],
        "story_patterns": ["I remember", "one day", "there was a time", "when I was", "let me tell you", "I was talking to", "I walked into", "years ago"],
        "emotion_patterns": ["pain", "fear", "anxiety", "healing", "miracle", "promise", "purpose", "restoration", "hope", "breakthrough"],
        "hashtags": ["#sermon", "#faith", "#Jesus", "#God", "#church", "#christianreels", "#bible"],
    },
    "es": {
        "label": "Español", "whisper_language": "es", "output_language": "es",
        "context": "predicación cristiana en español; pastor predicando; culto; iglesia; historias del púlpito; referencias bíblicas; testimonios; bromas; interacción con la iglesia; momentos emocionales; aplicación práctica; llamado espiritual; fe, esperanza, sanidad y restauración",
        "ai_language": "español", "caption_style": "pastoral, emocional, latino, natural para Reels, TikTok y Shorts",
        "god_terms": {"dios":"Dios", "señor":"Señor", "senor":"Señor", "jesús":"Jesús", "jesus":"Jesús", "cristo":"Cristo", "espíritu santo":"Espíritu Santo", "espiritu santo":"Espíritu Santo"},
        "impact_patterns": ["no te rindas", "Dios no ha terminado", "esta palabra es para ti", "yo declaro", "recibe esta palabra", "Dios está obrando", "tu historia no ha terminado", "el Señor te dice", "no se acabó"],
        "humor_patterns": ["mira a la persona de al lado", "dile a tu vecino", "quién conoce a alguien así", "algunos de ustedes", "no se hagan", "puedo ser honesto"],
        "story_patterns": ["yo recuerdo", "un día", "hubo un tiempo", "cuando yo era", "déjame contarte", "me pasó", "estaba hablando con"],
        "emotion_patterns": ["dolor", "miedo", "ansiedad", "sanidad", "milagro", "promesa", "propósito", "restauración", "esperanza"],
        "hashtags": ["#predicación", "#fe", "#Jesús", "#Dios", "#iglesia", "#reelscristianos", "#biblia"],
    },
    "fr": {
        "label":"Français", "whisper_language":"fr", "output_language":"fr",
        "context":"prédication chrétienne en français; pasteur qui prêche; culte; église; histoires au pupitre; références bibliques; témoignages; humour; interaction avec l'assemblée; moments émotionnels; application pratique; appel spirituel; foi, espérance, guérison et restauration",
        "ai_language":"français", "caption_style":"clair, pastoral, inspirant, naturel pour Reels, TikTok et Shorts",
        "god_terms":{"dieu":"Dieu", "seigneur":"Seigneur", "jésus":"Jésus", "jesus":"Jésus", "christ":"Christ", "saint-esprit":"Saint-Esprit", "esprit saint":"Esprit Saint"},
        "impact_patterns":["n'abandonne pas", "Dieu n'a pas fini", "cette parole est pour toi", "je déclare", "reçois cette parole", "ton histoire n'est pas terminée", "Dieu agit encore", "le Seigneur te dit"],
        "humor_patterns":["regarde ton voisin", "dis à ton voisin", "qui connaît quelqu'un comme ça", "certains d'entre vous", "soyons honnêtes"],
        "story_patterns":["je me souviens", "un jour", "il y a eu un temps", "quand j'étais", "laisse-moi te raconter", "cela m'est arrivé"],
        "emotion_patterns":["douleur", "peur", "anxiété", "guérison", "miracle", "promesse", "restauration", "espérance"],
        "hashtags":["#prédication", "#foi", "#Jésus", "#Dieu", "#église", "#Bible"],
    },
    "de": {
        "label":"Deutsch", "whisper_language":"de", "output_language":"de",
        "context":"christliche Predigt auf Deutsch; Pastor predigt; Gottesdienst; Kirche; Kanzelgeschichten; Bibelstellen; Zeugnisse; Humor; Interaktion mit der Gemeinde; emotionale Momente; praktische Anwendung; geistlicher Aufruf; Glaube, Hoffnung, Heilung und Wiederherstellung",
        "ai_language":"Deutsch", "caption_style":"klar, inspirierend, kirchlich, natürlich für Reels, TikTok und Shorts",
        "god_terms":{"gott":"Gott", "herr":"Herr", "jesus":"Jesus", "christus":"Christus", "heiliger geist":"Heiliger Geist"},
        "impact_patterns":["gib nicht auf", "Gott ist noch nicht fertig", "dieses Wort ist für dich", "ich erkläre", "empfange dieses Wort", "deine Geschichte ist nicht vorbei", "Gott wirkt noch", "der Herr sagt dir"],
        "humor_patterns":["schau deinen Nachbarn an", "sag deinem Nachbarn", "wer kennt jemanden so", "einige von euch", "seien wir ehrlich"],
        "story_patterns":["ich erinnere mich", "eines Tages", "es gab eine Zeit", "als ich", "lass mich dir erzählen", "mir ist passiert"],
        "emotion_patterns":["Schmerz", "Angst", "Sorge", "Heilung", "Wunder", "Verheißung", "Wiederherstellung", "Hoffnung"],
        "hashtags":["#predigt", "#glaube", "#Jesus", "#Gott", "#kirche", "#bibel"],
    },
    "it": {
        "label":"Italiano", "whisper_language":"it", "output_language":"it",
        "context":"predicazione cristiana in italiano; pastore che predica; culto; chiesa; storie dal pulpito; riferimenti biblici; testimonianze; battute; interazione con la chiesa; momenti emozionanti; applicazione pratica; chiamata spirituale; fede, speranza, guarigione e restaurazione",
        "ai_language":"italiano", "caption_style":"chiaro, pastorale, ispirazionale, naturale per Reels, TikTok e Shorts",
        "god_terms":{"dio":"Dio", "signore":"Signore", "gesù":"Gesù", "gesu":"Gesù", "cristo":"Cristo", "spirito santo":"Spirito Santo"},
        "impact_patterns":["non arrenderti", "Dio non ha finito", "questa parola è per te", "io dichiaro", "ricevi questa parola", "la tua storia non è finita", "Dio sta ancora operando", "il Signore ti dice"],
        "humor_patterns":["guarda il tuo vicino", "di' al tuo vicino", "chi conosce qualcuno così", "alcuni di voi", "siamo onesti"],
        "story_patterns":["mi ricordo", "un giorno", "c'è stato un tempo", "quando ero", "lascia che ti racconti", "mi è successo"],
        "emotion_patterns":["dolore", "paura", "ansia", "guarigione", "miracolo", "promessa", "restaurazione", "speranza"],
        "hashtags":["#predicazione", "#fede", "#Gesù", "#Dio", "#chiesa", "#Bibbia"],
    },
    "pt-PT": {
        "label":"Português Portugal", "whisper_language":"pt", "output_language":"pt-PT",
        "context":"pregação cristã em português europeu; pastor a pregar; culto; igreja; histórias no púlpito; referências bíblicas; testemunhos; humor; interação com a congregação; momentos emocionantes; aplicação prática; apelo espiritual; fé, esperança, cura e restauração",
        "ai_language":"português europeu", "caption_style":"claro, pastoral, cristão, natural para Reels, TikTok e Shorts",
        "god_terms":{"deus":"Deus", "senhor":"Senhor", "jesus":"Jesus", "cristo":"Cristo", "espirito santo":"Espírito Santo", "espírito santo":"Espírito Santo"},
        "impact_patterns":["não desistas", "Deus não terminou", "esta palavra é para ti", "eu declaro", "recebe esta palavra", "a tua história não acabou", "Deus ainda está a agir", "o Senhor está a dizer"],
        "humor_patterns":["olha para a pessoa ao lado", "diz ao teu vizinho", "quem conhece alguém assim", "alguns de vocês", "sejamos honestos"],
        "story_patterns":["lembro-me", "um dia", "houve um tempo", "quando eu era", "deixa-me contar-te", "aconteceu-me"],
        "emotion_patterns":["dor", "medo", "ansiedade", "cura", "milagre", "promessa", "restauração", "esperança"],
        "hashtags":["#pregação", "#fé", "#Jesus", "#Deus", "#igreja", "#bíblia"],
    },
    "ko": {
        "label":"Korean · 한국어", "whisper_language":"ko", "output_language":"ko",
        "context":"한국어 기독교 설교; 목사가 강단에서 설교함; 예배; 교회; 성경 구절; 간증; 이야기; 유머; 회중과의 상호작용; 감동적인 순간; 실제 적용; 영적 초청; 믿음, 소망, 치유와 회복",
        "ai_language":"Korean", "caption_style":"분명하고 목회적이며 감동적인 한국어 숏폼 스타일",
        "god_terms":{"하나님":"하나님", "주님":"주님", "예수":"예수님", "예수님":"예수님", "성령":"성령님"},
        "impact_patterns":["포기하지 마세요", "하나님은 아직 끝내지 않으셨습니다", "이 말씀은 당신을 위한 것입니다", "제가 선포합니다", "이 말씀을 받으세요", "당신의 이야기는 끝나지 않았습니다", "주님이 말씀하십니다"],
        "humor_patterns":["옆 사람을 보세요", "옆 사람에게 말하세요", "이런 사람 아시죠", "우리 솔직해집시다", "여러분 중에"],
        "story_patterns":["제가 기억합니다", "어느 날", "그런 때가 있었습니다", "제가 어렸을 때", "이야기 하나 하겠습니다", "제게 이런 일이 있었습니다"],
        "emotion_patterns":["고통", "두려움", "불안", "치유", "기적", "약속", "회복", "소망", "돌파"],
        "hashtags":["#설교", "#믿음", "#예수님", "#하나님", "#교회", "#성경"],
    },
    "ja": {
        "label":"Japanese · 日本語", "whisper_language":"ja", "output_language":"ja",
        "context":"日本語のキリスト教説教; 牧師が説教している; 礼拝; 教会; 聖書箇所; 証し; 物語; ユーモア; 会衆とのやりとり; 感動的な瞬間; 実践的な適用; 霊的な招き; 信仰、希望、癒やし、回復",
        "ai_language":"Japanese", "caption_style":"明確で敬意があり、牧会的でショート動画向けの自然な日本語",
        "god_terms":{"神":"神", "主":"主", "イエス":"イエス", "キリスト":"キリスト", "聖霊":"聖霊"},
        "impact_patterns":["あきらめないで", "神はまだ終わっていません", "この言葉はあなたのためです", "私は宣言します", "この言葉を受け取ってください", "あなたの物語は終わっていません", "主が語っておられます"],
        "humor_patterns":["隣の人を見てください", "隣の人に言ってください", "こういう人を知っていますか", "正直に言いましょう", "皆さんの中に"],
        "story_patterns":["覚えています", "ある日", "そんな時がありました", "私が若かった頃", "話をさせてください", "私に起こったことです"],
        "emotion_patterns":["痛み", "恐れ", "不安", "癒やし", "奇跡", "約束", "回復", "希望"],
        "hashtags":["#説教", "#信仰", "#イエス", "#神", "#教会", "#聖書"],
    },
    "zh": {
        "label":"Mandarin Chinese · 中文", "whisper_language":"zh", "output_language":"zh",
        "context":"普通话基督教讲道; 牧师在讲台上讲道; 礼拜; 教会; 圣经经文; 见证; 故事; 幽默; 与会众互动; 感人的时刻; 实际应用; 属灵呼召; 信心、盼望、医治和恢复",
        "ai_language":"Simplified Chinese", "caption_style":"清楚、牧养性、鼓舞人心、适合短视频的自然中文",
        "god_terms":{"神":"神", "上帝":"上帝", "主":"主", "耶稣":"耶稣", "基督":"基督", "圣灵":"圣灵"},
        "impact_patterns":["不要放弃", "神还没有结束", "这句话是给你的", "我宣告", "领受这句话", "你的故事还没有结束", "主正在对你说", "神仍然在工作"],
        "humor_patterns":["看看你旁边的人", "告诉你旁边的人", "你认识这样的人吗", "我们诚实一点", "你们当中有些人"],
        "story_patterns":["我记得", "有一天", "曾经有一段时间", "当我还是", "让我告诉你", "这件事发生在我身上"],
        "emotion_patterns":["痛苦", "恐惧", "焦虑", "医治", "神迹", "应许", "恢复", "盼望"],
        "hashtags":["#讲道", "#信仰", "#耶稣", "#上帝", "#教会", "#圣经"],
    },
    "hi": {
        "label":"Hindi · हिन्दी", "whisper_language":"hi", "output_language":"hi",
        "context":"हिन्दी मसीही संदेश; पास्टर मंच से प्रचार कर रहा है; आराधना सभा; कलीसिया; बाइबल संदर्भ; गवाही; कहानियाँ; हल्के मजाक; सभा से बातचीत; भावनात्मक क्षण; व्यावहारिक अनुप्रयोग; आत्मिक बुलाहट; विश्वास, आशा, चंगाई और बहाली",
        "ai_language":"Hindi", "caption_style":"स्पष्ट, पास्टोरल, प्रेरणादायक और शॉर्ट वीडियो के लिए स्वाभाविक हिन्दी",
        "god_terms":{"परमेश्वर":"परमेश्वर", "प्रभु":"प्रभु", "यीशु":"यीशु", "मसीह":"मसीह", "पवित्र आत्मा":"पवित्र आत्मा"},
        "impact_patterns":["हार मत मानो", "परमेश्वर ने अभी समाप्त नहीं किया", "यह वचन तुम्हारे लिए है", "मैं घोषणा करता हूँ", "इस वचन को ग्रहण करो", "तुम्हारी कहानी समाप्त नहीं हुई", "प्रभु तुमसे कह रहा है"],
        "humor_patterns":["अपने पास वाले को देखो", "अपने पड़ोसी से कहो", "क्या आप ऐसे किसी को जानते हैं", "आइए ईमानदार रहें", "आप में से कुछ लोग"],
        "story_patterns":["मुझे याद है", "एक दिन", "एक समय था", "जब मैं", "मुझे आपको बताने दीजिए", "मेरे साथ ऐसा हुआ"],
        "emotion_patterns":["दर्द", "भय", "चिंता", "चंगाई", "चमत्कार", "प्रतिज्ञा", "बहाली", "आशा"],
        "hashtags":["#प्रचार", "#विश्वास", "#यीशु", "#परमेश्वर", "#कलीसिया", "#बाइबल"],
    },
    "ar": {
        "label":"Arabic · العربية", "whisper_language":"ar", "output_language":"ar",
        "context":"عظة مسيحية باللغة العربية; راعٍ يتكلم من المنبر; اجتماع كنيسة; مراجع كتابية; شهادات; قصص; مزاح لطيف; تفاعل مع الحضور; لحظات مؤثرة; تطبيق عملي; دعوة روحية; إيمان ورجاء وشفاء واسترداد",
        "ai_language":"Arabic", "caption_style":"واضح ورعوي ومؤثر وطبيعي لمقاطع قصيرة",
        "god_terms":{"الله":"الله", "الرب":"الرب", "يسوع":"يسوع", "المسيح":"المسيح", "الروح القدس":"الروح القدس"},
        "impact_patterns":["لا تستسلم", "الله لم ينته بعد", "هذه الكلمة لك", "أنا أعلن", "اقبل هذه الكلمة", "قصتك لم تنته", "الرب يقول لك", "الله لا يزال يعمل"],
        "humor_patterns":["انظر إلى الشخص بجانبك", "قل لجارك", "هل تعرف شخصًا مثل هذا", "لنكن صادقين", "البعض منكم"],
        "story_patterns":["أتذكر", "في يوم من الأيام", "كان هناك وقت", "عندما كنت", "دعني أخبرك", "حدث هذا معي"],
        "emotion_patterns":["ألم", "خوف", "قلق", "شفاء", "معجزة", "وعد", "استرداد", "رجاء"],
        "hashtags":["#عظة", "#إيمان", "#يسوع", "#الله", "#كنيسة", "#الكتاب_المقدس"],
    },
    "id": {
        "label":"Indonesian", "whisper_language":"id", "output_language":"id",
        "context":"khotbah Kristen dalam bahasa Indonesia; pendeta berkhotbah; ibadah gereja; referensi Alkitab; kesaksian; cerita; humor; interaksi dengan jemaat; momen emosional; aplikasi praktis; panggilan rohani; iman, harapan, kesembuhan dan pemulihan",
        "ai_language":"Indonesian", "caption_style":"jelas, pastoral, inspiratif, natural untuk Reels, TikTok dan Shorts",
        "god_terms":{"tuhan":"Tuhan", "allah":"Allah", "yesus":"Yesus", "kristus":"Kristus", "roh kudus":"Roh Kudus"},
        "impact_patterns":["jangan menyerah", "Tuhan belum selesai", "firman ini untukmu", "saya mendeklarasikan", "terimalah firman ini", "ceritamu belum selesai", "Tuhan sedang berkata kepadamu"],
        "humor_patterns":["lihat orang di sebelahmu", "katakan kepada tetanggamu", "siapa yang kenal orang seperti ini", "mari jujur", "beberapa dari kalian"],
        "story_patterns":["saya ingat", "suatu hari", "ada suatu masa", "ketika saya", "izinkan saya bercerita", "ini terjadi pada saya"],
        "emotion_patterns":["rasa sakit", "takut", "cemas", "kesembuhan", "mukjizat", "janji", "pemulihan", "harapan"],
        "hashtags":["#khotbah", "#iman", "#Yesus", "#Tuhan", "#gereja", "#Alkitab"],
    },
    "tl": {
        "label":"Tagalog / Filipino", "whisper_language":"tl", "output_language":"tl",
        "context":"Kristiyanong sermon sa Tagalog/Filipino; pastor na nangangaral; church service; Bible references; testimonya; kuwento; biro; interaction sa congregation; emotional moments; practical application; spiritual call; pananampalataya, pag-asa, kagalingan at pagpapanumbalik",
        "ai_language":"Tagalog/Filipino", "caption_style":"malinaw, pastoral, inspiring, natural para sa Reels, TikTok at Shorts",
        "god_terms":{"diyos":"Diyos", "panginoon":"Panginoon", "hesus":"Hesus", "jesus":"Jesus", "cristo":"Cristo", "banal na espiritu":"Banal na Espiritu"},
        "impact_patterns":["huwag kang susuko", "hindi pa tapos ang Diyos", "ang salitang ito ay para sa iyo", "idine-deklara ko", "tanggapin mo ang salitang ito", "hindi pa tapos ang kuwento mo", "sinasabi ng Panginoon sa iyo"],
        "humor_patterns":["tingnan mo ang katabi mo", "sabihin mo sa katabi mo", "may kilala ba kayong ganito", "maging honest tayo", "ilan sa inyo"],
        "story_patterns":["naaalala ko", "isang araw", "may panahon", "noong ako ay", "ikukuwento ko sa inyo", "nangyari ito sa akin"],
        "emotion_patterns":["sakit", "takot", "pag-aalala", "kagalingan", "himala", "pangako", "pagpapanumbalik", "pag-asa"],
        "hashtags":["#sermon", "#pananampalataya", "#Jesus", "#Diyos", "#church", "#Bible"],
    },
    "sw": {
        "label":"Swahili", "whisper_language":"sw", "output_language":"sw",
        "context":"mahubiri ya Kikristo kwa Kiswahili; mchungaji anahubiri; ibada ya kanisa; marejeo ya Biblia; ushuhuda; hadithi; ucheshi; mawasiliano na kusanyiko; nyakati za hisia; matumizi ya vitendo; wito wa kiroho; imani, tumaini, uponyaji na urejesho",
        "ai_language":"Swahili", "caption_style":"wazi, ya kichungaji, yenye kutia moyo, asili kwa Reels, TikTok na Shorts",
        "god_terms":{"mungu":"Mungu", "bwana":"Bwana", "yesu":"Yesu", "kristo":"Kristo", "roho mtakatifu":"Roho Mtakatifu"},
        "impact_patterns":["usikate tamaa", "Mungu hajamaliza", "neno hili ni kwa ajili yako", "natangaza", "pokea neno hili", "hadithi yako haijaisha", "Bwana anakwambia"],
        "humor_patterns":["mtazame jirani yako", "mwambie jirani yako", "nani anamjua mtu kama huyu", "tuseme ukweli", "baadhi yenu"],
        "story_patterns":["nakumbuka", "siku moja", "kulikuwa na wakati", "nilipokuwa", "acha niwaambie", "hili lilinitokea"],
        "emotion_patterns":["maumivu", "hofu", "wasiwasi", "uponyaji", "muujiza", "ahadi", "urejesho", "tumaini"],
        "hashtags":["#mahubiri", "#imani", "#Yesu", "#Mungu", "#kanisa", "#Biblia"],
    },
    "yo": {
        "label":"Yoruba", "whisper_language":"yo", "output_language":"yo",
        "context":"ìwàásù Kristẹni ní èdè Yorùbá; pásítọ̀ ń wàásù; ìjọsìn; ìjọ; ìtọ́kasí Bíbélì; ẹ̀rí; ìtàn; awada; ìbáṣepọ̀ pẹ̀lú ìjọ; àsìkò ìmọ̀lára; ohun tí a lè fi sí ìṣe; ìpè ẹ̀mí; ìgbàgbọ́, ìrètí, ìwòsàn àti ìmúpadàbọ̀sípò",
        "ai_language":"Yoruba", "caption_style":"kedere, ti olùṣọ́-àgùntàn, ìmísí, adayeba fún Reels, TikTok àti Shorts",
        "god_terms":{"olorun":"Ọlọrun", "ọlọrun":"Ọlọrun", "olúwa":"Olúwa", "oluwa":"Olúwa", "jesu":"Jésù", "jésù":"Jésù", "emi mimo":"Ẹmí Mímọ́", "ẹmí mímọ́":"Ẹmí Mímọ́"},
        "impact_patterns":["má ṣe juwọ́ silẹ", "Ọlọrun kò tíì parí", "ọ̀rọ̀ yìí jẹ́ fún ọ", "mo kéde", "gba ọ̀rọ̀ yìí", "ìtàn rẹ kò tíì parí", "Olúwa ń sọ fún ọ"],
        "humor_patterns":["wo ẹni tó wà lẹ́gbẹ̀ẹ́ rẹ", "sọ fún aládùúgbò rẹ", "ta ló mọ ẹni báyìí", "ẹ jẹ́ ká sọ òtítọ́", "diẹ ninu yín"],
        "story_patterns":["mo rántí", "ní ọjọ́ kan", "àkókò kan wà", "nígbà tí mo jẹ́", "jẹ́ kí n sọ fún yín", "èyí ṣẹlẹ̀ sí mi"],
        "emotion_patterns":["ìrora", "ẹ̀rù", "àníyàn", "ìwòsàn", "ìyanu", "ìlérí", "ìmúpadàbọ̀sípò", "ìrètí"],
        "hashtags":["#ìwàásù", "#ìgbàgbọ́", "#Jesu", "#Ọlọrun", "#ìjọ", "#Bíbélì"],
    },
}

SUPPORTED_LANGUAGE_ORDER = ["pt-BR","en","es","fr","de","it","pt-PT","ko","ja","zh","hi","ar","id","tl","sw","yo"]

def perfil_id_atual():
    pid = str(config_usuario.get("language_profile", CONFIG.get("language_profile", "pt-BR")) or "pt-BR").strip()
    return pid if pid in LANGUAGE_PROFILES else "pt-BR"

def perfil_idioma_atual():
    return LANGUAGE_PROFILES.get(perfil_id_atual(), LANGUAGE_PROFILES["pt-BR"])

def whisper_language_atual():
    return str(config_usuario.get("source_language") or perfil_idioma_atual().get("whisper_language") or "pt").strip()

def output_language_atual():
    return str(config_usuario.get("output_language") or perfil_idioma_atual().get("output_language") or perfil_id_atual()).strip()

def contexto_transcricao_atual():
    return str(config_usuario.get("contexto_transcricao") or perfil_idioma_atual().get("context") or "Christian sermon").strip()

def ai_language_atual():
    return str(perfil_idioma_atual().get("ai_language") or output_language_atual()).strip()

def ai_boost_ativo():
    return str(config_usuario.get("global_language_mode", CONFIG.get("global_language_mode", "standard"))).lower().strip() == "ai_boost"

def live_translation_ativa():
    return ai_boost_ativo() and bool(config_usuario.get("live_translation_enabled", CONFIG.get("live_translation_enabled", False)))

def phrase_ai_ativa():
    return ai_boost_ativo() and bool(config_usuario.get("phrase_ai_enabled", CONFIG.get("phrase_ai_enabled", False)))

def perfis_idioma_para_painel():
    return [{"id": k, "label": LANGUAGE_PROFILES[k].get("label", k), "whisper_language": LANGUAGE_PROFILES[k].get("whisper_language", k)} for k in SUPPORTED_LANGUAGE_ORDER if k in LANGUAGE_PROFILES]

def _global_terms_regex(categoria):
    termos=[]
    prof=perfil_idioma_atual()
    for chave in (categoria, "impact_patterns", "humor_patterns", "story_patterns", "emotion_patterns"):
        if categoria == chave or categoria == "all":
            termos += [str(x) for x in prof.get(chave, []) if str(x).strip()]
    termos += [str(x) for x in (prof.get("god_terms", {}) or {}).keys() if str(x).strip()]
    # remove muito curtos para evitar falso positivo
    termos = sorted(set([t.strip() for t in termos if len(t.strip()) >= 3]), key=len, reverse=True)
    if not termos:
        return None
    return re.compile("|".join(re.escape(_norm(t)) for t in termos), re.I)

def score_global_idioma(texto):
    """Bônus leve por idioma para o detector local reconhecer histórias, humor, emoção e frases fortes.
    A IA/Gemini continua sendo o principal cérebro global, mas esse bônus ajuda sem deixar pesado.
    """
    prof = perfil_idioma_atual()
    normal = _norm(texto or "")
    if not normal:
        return 0, []
    score = 0
    razoes = []
    categorias = [
        ("impact_patterns", 18, "frase forte do idioma"),
        ("humor_patterns", 16, "humor/interação no púlpito"),
        ("story_patterns", 14, "história/ilustração"),
        ("emotion_patterns", 14, "momento emocional"),
    ]
    for campo, peso, razao in categorias:
        hits = 0
        for termo in prof.get(campo, []) or []:
            if _norm(str(termo)) in normal:
                hits += 1
        if hits:
            score += min(peso + (hits-1)*4, peso+12)
            razoes.append(razao)
    god_hits = 0
    for termo in (prof.get("god_terms", {}) or {}).keys():
        if _norm(str(termo)) in normal:
            god_hits += 1
    if god_hits:
        score += min(10 + god_hits*3, 22)
        razoes.append("vocabulário cristão do idioma")
    return score, razoes[:4]

def prompt_global_cortes():
    perfil = perfil_idioma_atual()
    lingua = ai_language_atual()
    contexto = contexto_transcricao_atual()
    estilo = perfil.get("caption_style", "natural church social media")
    impact = ", ".join(perfil.get("impact_patterns", [])[:14])
    humor = ", ".join(perfil.get("humor_patterns", [])[:10])
    story = ", ".join(perfil.get("story_patterns", [])[:10])
    emotion = ", ".join(perfil.get("emotion_patterns", [])[:10])
    hashtags = ", ".join(perfil.get("hashtags", [])[:10])
    return f"""You are a global AI clipping director for Christian churches.

Analyze a sermon/message in this language: {lingua}.
Context: {contexto}.
Output language: {lingua}.
Social caption style: {estilo}.
Suggested hashtag style: {hashtags}.

Your job is to find the BEST short-form clips from a Christian sermon, worship talk, church service, podcast or pulpit message.
Do not only look for dramatic phrases. Also find moments that can work as viral/social clips:
- stories and illustrations from the pulpit
- jokes, light moments and audience interaction
- funny examples the pastor uses to make the congregation laugh
- emotional and memorable moments
- strong faith declarations
- practical application for everyday life
- clear biblical teaching
- spiritual calls, prayer moments and altar-call style moments
- pastoral confrontation with love
- hope, healing, identity, restoration and breakthrough moments
- curiosity hooks and turning points
- simple explanations that make a complex biblical idea easy to understand

Language-specific hints:
Impact phrases/patterns: {impact or 'use natural strong phrases for this language'}
Humor/audience patterns: {humor or 'detect natural humor and audience interaction'}
Story patterns: {story or 'detect personal stories and illustrations'}
Emotion patterns: {emotion or 'detect emotional pastoral moments'}

Return titles, reasons, impact phrases, captions and Bible references naturally in {lingua}.
Never translate unless live translation/output language explicitly asks for it.
Do not invent Bible verses; only extract references that appear or are clearly mentioned.
Respond only as valid JSON."""

BIBLE_BOOKS_BY_PROFILE = {
    "pt-BR": r"G[eê]nesis|[ÊE]xodo|Lev[ií]tico|N[uú]meros|Deuteron[oô]mio|Josu[eé]|Ju[ií]zes|Rute|(?:1|2)\s*Samuel|(?:1|2)\s*Reis|(?:1|2)\s*Cr[oô]nicas|Esdras|Neemias|Ester|J[oó]|Salmos?|Prov[eé]rbios|Eclesiastes|Cantares|Isa[ií]as|Jeremias|Lamenta[cç][oõ]es|Ezequiel|Daniel|Oseias|Joel|Am[oó]s|Obadias|Jonas|Miqueias|Naum|Habacuque|Sofonias|Ageu|Zacarias|Malaquias|Mateus|Marcos|Lucas|Jo[aã]o|Atos|Romanos|(?:1|2)\s*Cor[ií]ntios|G[aá]latas|Ef[eé]sios|Filipenses|Colossenses|Tessalonicenses|Tim[oó]teo|Tito|Filemom|Hebreus|Tiago|Pedro|Judas|Apocalipse|Gn|Ex|Lv|Nm|Dt|Js|Jz|Rt|Sl|Pv|Ec|Is|Jr|Ez|Dn|Mt|Mc|Lc|Jo|At|Rm|Ap",
    "en": r"Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|(?:1|2)\s*Samuel|(?:1|2)\s*Kings|(?:1|2)\s*Chronicles|Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|Ecclesiastes|Song of Songs|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|(?:1|2)\s*Corinthians|Galatians|Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|Revelation|Gen|Ex|Lev|Num|Deut|Josh|Judg|Ps|Prov|Matt|Mk|Lk|Jn|Rom|Rev",
    "es": r"G[eé]nesis|[ÉE]xodo|Lev[ií]tico|N[uú]meros|Deuteronomio|Josu[eé]|Jueces|Rut|(?:1|2)\s*Samuel|(?:1|2)\s*Reyes|(?:1|2)\s*Cr[oó]nicas|Esdras|Nehem[ií]as|Ester|Job|Salmos?|Proverbios|Eclesiast[eé]s|Cantares|Isa[ií]as|Jerem[ií]as|Lamentaciones|Ezequiel|Daniel|Oseas|Joel|Am[oó]s|Abd[ií]as|Jon[aá]s|Miqueas|Nah[uú]m|Habacuc|Sofon[ií]as|Hageo|Zacar[ií]as|Malaqu[ií]as|Mateo|Marcos|Lucas|Juan|Hechos|Romanos|Corintios|G[aá]latas|Efesios|Filipenses|Colosenses|Tesalonicenses|Timoteo|Tito|Filem[oó]n|Hebreos|Santiago|Pedro|Judas|Apocalipsis|Gn|Ex|Sal|Mt|Mc|Lc|Jn|Ro|Ap",
    "fr": r"Gen[eè]se|Exode|L[eé]vitique|Nombres|Deut[eé]ronome|Josu[eé]|Juges|Ruth|Samuel|Rois|Chroniques|Esdras|N[eé]h[eé]mie|Esther|Job|Psaumes?|Proverbes|Eccl[eé]siaste|Cantique|[ÉE]sa[iï]e|J[eé]r[eé]mie|Lamentations|[ÉE]z[eé]chiel|Daniel|Os[eé]e|Jo[eë]l|Amos|Abdias|Jonas|Mich[eé]e|Nahum|Habacuc|Sophonie|Agg[eé]e|Zacharie|Malachie|Matthieu|Marc|Luc|Jean|Actes|Romains|Corinthiens|Galates|[ÉE]ph[eé]siens|Philippiens|Colossiens|Thessaloniciens|Timoth[eé]e|Tite|Phil[eé]mon|H[eé]breux|Jacques|Pierre|Jude|Apocalypse",
    "de": r"Genesis|Exodus|Levitikus|Numeri|Deuteronomium|Josua|Richter|Rut|Samuel|K[oö]nige|Chronik|Esra|Nehemia|Ester|Hiob|Psalmen?|Spr[uü]che|Prediger|Hohelied|Jesaja|Jeremia|Klagelieder|Hesekiel|Ezechiel|Daniel|Hosea|Joel|Amos|Obadja|Jona|Micha|Nahum|Habakuk|Zefanja|Haggai|Sacharja|Maleachi|Matth[aä]us|Markus|Lukas|Johannes|Apostelgeschichte|R[oö]mer|Korinther|Galater|Epheser|Philipper|Kolosser|Thessalonicher|Timotheus|Titus|Philemon|Hebr[aä]er|Jakobus|Petrus|Judas|Offenbarung",
    "it": r"Genesi|Esodo|Levitico|Numeri|Deuteronomio|Giosu[eè]|Giudici|Rut|Samuele|Re|Cronache|Esdra|Neemia|Ester|Giobbe|Salmi?|Proverbi|Ecclesiaste|Cantico|Isaia|Geremia|Lamentazioni|Ezechiele|Daniele|Osea|Gioele|Amos|Abdia|Giona|Michea|Naum|Abacuc|Sofonia|Aggeo|Zaccaria|Malachia|Matteo|Marco|Luca|Giovanni|Atti|Romani|Corinzi|Galati|Efesini|Filippesi|Colossesi|Tessalonicesi|Timoteo|Tito|Filemone|Ebrei|Giacomo|Pietro|Giuda|Apocalisse",
    "ko": r"창세기|출애굽기|레위기|민수기|신명기|여호수아|사사기|룻기|사무엘상|사무엘하|열왕기상|열왕기하|역대상|역대하|에스라|느헤미야|에스더|욥기|시편|잠언|전도서|아가|이사야|예레미야|예레미야애가|에스겔|다니엘|호세아|요엘|아모스|오바댜|요나|미가|나훔|하박국|스바냐|학개|스가랴|말라기|마태복음|마가복음|누가복음|요한복음|사도행전|로마서|고린도전서|고린도후서|갈라디아서|에베소서|빌립보서|골로새서|데살로니가전서|데살로니가후서|디모데전서|디모데후서|디도서|빌레몬서|히브리서|야고보서|베드로전서|베드로후서|요한일서|요한이서|요한삼서|유다서|요한계시록",
    "ja": r"創世記|出エジプト記|レビ記|民数記|申命記|ヨシュア記|士師記|ルツ記|サムエル記|列王記|歴代誌|エズラ記|ネヘミヤ記|エステル記|ヨブ記|詩篇|詩編|箴言|伝道者の書|雅歌|イザヤ書|エレミヤ書|哀歌|エゼキエル書|ダニエル書|ホセア書|ヨエル書|アモス書|オバデヤ書|ヨナ書|ミカ書|ナホム書|ハバクク書|ゼパニヤ書|ハガイ書|ゼカリヤ書|マラキ書|マタイ|マルコ|ルカ|ヨハネ|使徒|ローマ|コリント|ガラテヤ|エペソ|エフェソ|ピリピ|コロサイ|テサロニケ|テモテ|テトス|ピレモン|ヘブル|ヘブライ|ヤコブ|ペテロ|ペトロ|ユダ|黙示録",
    "zh": r"创世记|出埃及记|利未记|民数记|申命记|约书亚记|士师记|路得记|撒母耳记|列王纪|历代志|以斯拉记|尼希米记|以斯帖记|约伯记|诗篇|箴言|传道书|雅歌|以赛亚书|耶利米书|耶利米哀歌|以西结书|但以理书|何西阿书|约珥书|阿摩司书|俄巴底亚书|约拿书|弥迦书|那鸿书|哈巴谷书|西番雅书|哈该书|撒迦利亚书|玛拉基书|马太福音|马可福音|路加福音|约翰福音|使徒行传|罗马书|哥林多前书|哥林多后书|加拉太书|以弗所书|腓立比书|歌罗西书|帖撒罗尼迦|提摩太|提多书|腓利门书|希伯来书|雅各书|彼得|约翰一书|约翰二书|约翰三书|犹大书|启示录",
    "hi": r"उत्पत्ति|निर्गमन|लैव्यव्यवस्था|गिनती|व्यवस्थाविवरण|यहोशू|न्यायियों|रूत|शमूएल|राजाओं|इतिहास|एज्रा|नहेमायाह|एस्तेर|अय्यूब|भजन|नीतिवचन|सभोपदेशक|श्रेष्ठगीत|यशायाह|यिर्मयाह|विलापगीत|यहेजकेल|दानिय्येल|होशे|योएल|आमोस|ओबद्याह|योना|मीका|नहूम|हबक्कूक|सपन्याह|हाग्गै|जकर्याह|मलाकी|मत्ती|मरकुस|लूका|यूहन्ना|प्रेरितों|रोमियों|कुरिन्थियों|गलातियों|इफिसियों|फिलिप्पियों|कुलुस्सियों|थिस्सलुनीकियों|तीमुथियुस|तीतुस|फिलेमोन|इब्रानियों|याकूब|पतरस|यहूदा|प्रकाशितवाक्य",
    "ar": r"التكوين|الخروج|اللاويين|العدد|التثنية|يشوع|القضاة|راعوث|صموئيل|الملوك|أخبار الأيام|عزرا|نحميا|أستير|أيوب|المزامير|الأمثال|الجامعة|نشيد الأنشاد|إشعياء|إرميا|مراثي|حزقيال|دانيال|هوشع|يوئيل|عاموس|عوبديا|يونان|ميخا|ناحوم|حبقوق|صفنيا|حجّي|زكريا|ملاخي|متى|مرقس|لوقا|يوحنا|أعمال الرسل|رومية|كورنثوس|غلاطية|أفسس|فيلبي|كولوسي|تسالونيكي|تيموثاوس|تيطس|فليمون|العبرانيين|يعقوب|بطرس|يهوذا|الرؤيا",
    "id": r"Kejadian|Keluaran|Imamat|Bilangan|Ulangan|Yosua|Hakim-hakim|Rut|Samuel|Raja-raja|Tawarikh|Ezra|Nehemia|Ester|Ayub|Mazmur|Amsal|Pengkhotbah|Kidung Agung|Yesaya|Yeremia|Ratapan|Yehezkiel|Daniel|Hosea|Yoel|Amos|Obaja|Yunus|Mikha|Nahum|Habakuk|Zefanya|Hagai|Zakharia|Maleakhi|Matius|Markus|Lukas|Yohanes|Kisah Para Rasul|Roma|Korintus|Galatia|Efesus|Filipi|Kolose|Tesalonika|Timotius|Titus|Filemon|Ibrani|Yakobus|Petrus|Yudas|Wahyu",
    "tl": r"Genesis|Exodo|Levitico|Mga Bilang|Deuteronomio|Josue|Mga Hukom|Ruth|Samuel|Mga Hari|Mga Cronica|Ezra|Nehemias|Ester|Job|Mga Awit|Kawikaan|Eclesiastes|Awit ni Solomon|Isaias|Jeremias|Panaghoy|Ezekiel|Daniel|Oseas|Joel|Amos|Obadias|Jonas|Mikas|Nahum|Habakuk|Sofonias|Hageo|Zacarias|Malakias|Mateo|Marcos|Lucas|Juan|Mga Gawa|Roma|Corinto|Galacia|Efeso|Filipos|Colosas|Tesalonica|Timoteo|Tito|Filemon|Hebreo|Santiago|Pedro|Judas|Pahayag",
    "sw": r"Mwanzo|Kutoka|Walawi|Hesabu|Kumbukumbu la Torati|Yoshua|Waamuzi|Ruthu|Samweli|Wafalme|Mambo ya Nyakati|Ezra|Nehemia|Esta|Ayubu|Zaburi|Mithali|Mhubiri|Wimbo Ulio Bora|Isaya|Yeremia|Maombolezo|Ezekieli|Danieli|Hosea|Yoeli|Amosi|Obadia|Yona|Mika|Nahumu|Habakuki|Sefania|Hagai|Zekaria|Malaki|Mathayo|Marko|Luka|Yohana|Matendo|Warumi|Wakorintho|Wagalatia|Waefeso|Wafilipi|Wakolosai|Wathesalonike|Timotheo|Tito|Filemoni|Waebrania|Yakobo|Petro|Yuda|Ufunuo",
    "yo": r"Jẹnẹsisi|Genesisi|Eksodu|Lefitiku|Numeri|Deuteronomi|Joṣua|Joshua|Onidajọ|Rutu|Samueli|Awọn Ọba|Kronika|Esra|Nehemiah|Esteri|Jobu|Orin Dafidi|Owe|Oniwasu|Orin Solomoni|Aisaya|Jeremiah|Ẹkún Jeremiah|Esekiẹli|Danieli|Hosea|Joeli|Amosi|Obadiah|Jona|Mika|Nahumu|Habakuku|Sefania|Hagai|Sekariah|Malaki|Matiu|Marku|Luku|Johanu|Iṣe Awon Aposteli|Romu|Korinti|Galatia|Efesu|Filipi|Kolosse|Tẹsalonika|Timotiu|Titu|Filemoni|Heberu|Jakọbu|Peteru|Juda|Ifihan",
}

def bible_books_regex_atual():
    pid = perfil_id_atual()
    if pid == "pt-PT": pid = "pt-BR"
    return BIBLE_BOOKS_BY_PROFILE.get(pid) or BIBLE_BOOKS_BY_PROFILE.get("en")

# ----------------------------- FIM GLOBAL LANGUAGE RULES v1.1.3 -----------------------------


# ----------------------------- DETECTOR LOCAL DE CORTES -----------------------------

PALAVRAS_IMPACTO = {
    "deus","jesus","cristo","espirito","santo","senhor","milagre","cura",
    "libertacao","vitoria","fe","creia","levanta","hoje","agora","gloria",
    "aleluia","amem","profetico","uncao","altar","salvacao","graca","poder",
    "fogo","avivamento","transformacao","proposito","chamado","promessa",
    "familia","casamento","filho","filha","casa","dor","medo","ansiedade",
    "perdao","arrependimento","recomeco","impossivel","deserto","processo",
}

FRASES_IMPACTO = {
    "deus vai": 24, "deus esta": 20, "deus não": 18, "deus nao": 18,
    "eu profetizo": 32, "eu declaro": 30, "receba": 22, "tome posse": 26,
    "não desista": 34, "nao desista": 34, "não pare": 28, "nao pare": 28,
    "presta atenção": 22, "presta atencao": 22, "escuta isso": 24,
    "olha para mim": 20, "eu vim te dizer": 28, "o senhor está dizendo": 30,
    "o senhor esta dizendo": 30, "você não": 18, "voce nao": 18,
    "você vai": 20, "voce vai": 20, "chegou a hora": 30, "a partir de hoje": 28,
    "nunca mais": 24, "tem gente": 18, "sabe por quê": 18, "sabe por que": 18,
    "a bíblia diz": 20, "a biblia diz": 20, "está escrito": 20, "esta escrito": 20,
}


# Gatilhos adicionais para pregação que costuma performar em cortes:
# historia + tensão + virada + presença/voz + aplicação direta.
FRASES_VIRAIS_PREGA = {
    "deixa eu te contar": 20, "presta atenção": 18, "presta atencao": 18,
    "o problema é": 18, "o problema e": 18, "o ponto é": 16, "o ponto e": 16,
    "a questão é": 16, "a questao e": 16, "a verdade é": 22, "a verdade e": 22,
    "sabe o que acontece": 18, "sabe o que deus": 24, "quando deus": 18,
    "tem uma coisa": 16, "eu quero te dizer": 22, "escuta isso": 20,
    "foi aí que": 18, "foi ai que": 18, "até que": 16, "ate que": 16,
    "mas deus": 26, "só que deus": 24, "so que deus": 24, "de repente": 20,
    "no dia em que": 16, "quando ele percebe": 18, "olha para mim": 18,
    "isso aqui é forte": 24, "isso aqui e forte": 24, "isso é muito forte": 24,
}

PALAVRAS_EMOCIONAIS_PREGA = {
    "choro", "chorou", "dor", "ferida", "perda", "luto", "medo", "ansiedade",
    "depressao", "depressão", "sozinho", "deserto", "processo", "humilhado",
    "quebrado", "quebrantado", "arrependimento", "perdao", "perdão",
    "milagre", "cura", "restauracao", "restauração", "promessa", "proposito",
    "propósito", "presenca", "presença", "gloria", "glória", "uncao", "unção",
    "avivamento", "espirito", "espírito", "jesus", "deus"
}

# Música/louvor: a regra de corte é diferente de pregação.
# Em música, o melhor corte costuma estar no refrão, ponte, clímax, subida de emoção,
# repetição bonita ou frase cantável. Não precisa ter aplicação/explicação como pregação.
PALAVRAS_MUSICA_LOUVOR = {
    "louvor", "adoracao", "adoração", "cantar", "canto", "canção", "cancao",
    "voz", "som", "melodia", "refrão", "refrao", "ponte", "coro", "ministração",
    "minha alma", "meu coração", "meu coracao", "te adoro", "eu te amo",
    "santo", "digno", "hosana", "aleluia", "gloria", "glória", "pra sempre",
    "para sempre", "vem senhor", "espírito santo", "espirito santo"
}

FRASES_MUSICA_IMPACTO = {
    "te adoro": 28, "eu te amo": 26, "tu és santo": 30, "tu es santo": 30,
    "santo santo": 34, "digno é": 28, "digno e": 28, "pra sempre": 22,
    "para sempre": 22, "minha alma": 24, "meu coração": 22, "meu coracao": 22,
    "vem senhor": 24, "espírito santo": 26, "espirito santo": 26,
    "aleluia": 18, "glória": 18, "gloria": 18, "hosana": 20,
}


# ----------------------------- v1.0.107 WORSHIP SCORING & SONG NAMING -----------------------------
FZ107_VIDEO_EXTERNO_PATTERNS = [
    r"\b(cleanmymac|macbook|aplicativo|aplicativos|instalador|instaladores|ferramentas gratuitamente|7 dias|cupom|link na bio|se inscreva|curte e compartilha)\b",
    r"\b(tutorial|review|unboxing|produto|an[uú]ncio|propaganda|patrocinado|sponsor|compre agora|arrasta pra cima)\b",
    r"\b(iphone|ipad|notebook|windows|download|atualizar todos os aplicativos|lixo do sistema)\b",
]

FZ107_FRASES_LOUVOR_CORACAO = {
    "sem ti nao somos nada": 34,
    "sem ti não somos nada": 34,
    "nao vou mais te deixar": 32,
    "não vou mais te deixar": 32,
    "meu prazer e te louvar": 30,
    "meu prazer é te louvar": 30,
    "lugar seguro": 24,
    "tudo deixarei": 26,
    "te amar": 18,
    "tua mao me sustentou": 26,
    "tua mão me sustentou": 26,
    "presenca de jeova": 28,
    "presença de jeová": 28,
    "espirito santo": 26,
    "espírito santo": 26,
    "eu me rendo": 30,
    "me entrego": 28,
    "tu es tudo": 26,
    "tu és tudo": 26,
    "santo santo": 30,
    "digno": 20,
    "aleluia": 16,
}

FZ107_PALAVRAS_ADORACAO_PROFUNDA = {
    "jesus","deus","senhor","espirito","espírito","santo","presenca","presença",
    "adorar","adoracao","adoração","louvar","louvor","rendo","entrego","quebranta",
    "cura","milagre","promessa","graca","graça","amor","alma","coracao","coração",
    "fiel","digno","gloria","glória","aleluia","jeova","jeová","salvador"
}

FZ107_STOP_TITLE = {
    "eu","tu","voce","você","ele","ela","nos","nós","meu","minha","teu","tua",
    "que","pra","para","com","sem","por","de","da","do","em","no","na","um","uma",
    "e","o","a","os","as","mais","muito","muita","agora","assim","isso"
}

def fz107_parece_video_externo(texto):
    normal = _norm(texto or "")
    if not normal:
        return False
    return any(re.search(p, normal, re.I) for p in FZ107_VIDEO_EXTERNO_PATTERNS)

def fz107_conf_texto_louvor(texto):
    normal = _norm(texto or "")
    palavras = [p.strip(".,!?;:()[]{}\"'") for p in normal.split() if p.strip()]
    if not palavras:
        return 0
    score = 0
    for frase, peso in FZ107_FRASES_LOUVOR_CORACAO.items():
        if _norm(frase) in normal:
            score += peso
    ad = sum(1 for p in palavras if p in FZ107_PALAVRAS_ADORACAO_PROFUNDA)
    score += min(35, ad * 5)
    repeticao = len(palavras) - len(set(palavras))
    if repeticao >= 2:
        score += min(18, repeticao * 3)
    if 5 <= len(palavras) <= 32:
        score += 10
    if len(palavras) > 55:
        score -= 10
    if fz107_parece_video_externo(texto):
        score -= 80
    return max(0, min(100, score))

def fz107_nome_musica_por_letra(texto):
    original = re.sub(r"\s+", " ", (texto or "")).strip()
    normal = _norm(original)
    if not normal or fz107_parece_video_externo(original):
        return "", 0
    melhores = []
    for frase, peso in FZ107_FRASES_LOUVOR_CORACAO.items():
        nf = _norm(frase)
        if nf in normal:
            melhores.append((peso, frase))
    if melhores:
        melhores.sort(reverse=True)
        nome = melhores[0][1]
        nome = nome[:1].upper() + nome[1:]
        return nome, min(95, 62 + melhores[0][0])
    partes = re.split(r"(?<=[.!?…])\s+|,|\n", original)
    candidatas = []
    for parte in partes:
        p = re.sub(r"\s+", " ", parte).strip(" -–—:;,.!?")
        np = _norm(p)
        palavras = [x for x in np.split() if x not in FZ107_STOP_TITLE]
        if 3 <= len(palavras) <= 9 and fz107_conf_texto_louvor(p) >= 28:
            freq = normal.count(np)
            candidatas.append((freq, fz107_conf_texto_louvor(p), p))
    if candidatas:
        candidatas.sort(key=lambda x: (x[0], x[1]), reverse=True)
        nome = candidatas[0][2]
        nome = " ".join(w[:1].upper() + w[1:] for w in nome.split())
        return nome[:52], min(88, 50 + candidatas[0][1] + candidatas[0][0] * 6)
    palavras = original.split()
    if 4 <= len(palavras) <= 12 and fz107_conf_texto_louvor(original) >= 35:
        nome = " ".join(w[:1].upper() + w[1:] for w in original.strip(".,!?").split())
        return nome[:52], 70
    return "", 0

def fz107_titulo_louvor(texto, fallback="Momento de louvor"):
    nome, conf = fz107_nome_musica_por_letra(texto)
    if nome and conf >= 78:
        return f"Louvor - {nome}"
    if nome and conf >= 60:
        return f"Louvor - Possível {nome}"
    return fallback

def fz107_score_emocional_louvor(texto, feats=None):
    feats = feats or {}
    normal = _norm(texto or "")
    palavras = [p for p in normal.split() if p]
    if not palavras:
        return 0, ["sem letra confiável"], "adoração", "louvor"
    if fz107_parece_video_externo(texto):
        return 0, ["vídeo externo/propaganda bloqueado"], "neutro", "ignorado"
    score = 28
    razoes = ["louvor detectado"]
    conf_letra = fz107_conf_texto_louvor(texto)
    score += min(36, int(conf_letra * 0.45))
    if conf_letra >= 55:
        razoes.append("letra forte")
    elif conf_letra >= 30:
        razoes.append("letra de adoração")
    for frase, peso in FZ107_FRASES_LOUVOR_CORACAO.items():
        if _norm(frase) in normal:
            score += min(18, int(peso * 0.35))
            razoes.append("frase sensível")
            break
    repeticao = len(palavras) - len(set(palavras))
    if repeticao >= 2:
        score += min(16, repeticao * 3)
        razoes.append("repetição congregacional")
    rms = float((feats or {}).get("rms", 0.0) or 0.0)
    energy = int((feats or {}).get("energy_score", 0) or 0)
    dynamic = float((feats or {}).get("dynamic", 0.0) or 0.0)
    if rms < 0.09 and conf_letra >= 45:
        score += 12
        razoes.append("parte íntima com letra clara")
    elif energy >= 82 and conf_letra >= 35:
        score += 10
        razoes.append("energia + letra")
    elif energy >= 82 and conf_letra < 20:
        score -= 12
        razoes.append("energia alta sem letra clara")
    if dynamic >= 0.75:
        score += 8
        razoes.append("crescimento emocional")
    if len(palavras) <= 4:
        score -= 10
    if len(palavras) > 70 and repeticao < 3:
        score -= 8
    emocao = "adoração"
    if re.search(r"\b(rendo|entrego|quebranta|sem ti|alma|coracao|coração|choro|cura)\b", normal):
        emocao = "quebrantamento"
    elif re.search(r"\b(aleluia|gloria|glória|celebr|vitoria|vitória|prazer e te louvar|prazer é te louvar)\b", normal):
        emocao = "celebração"
    funcao = "refrão/congregação" if repeticao >= 2 else "momento sensível de louvor"
    return max(0, min(96, int(score))), list(dict.fromkeys(razoes))[:5], emocao, funcao
# ----------------------------- /v1.0.107 WORSHIP SCORING & SONG NAMING -----------------------------

PALAVRAS_PREGA_FALA = {
    "biblia", "bíblia", "versiculo", "versículo", "capitulo", "capítulo",
    "texto", "pregacao", "pregação", "mensagem", "ensino", "historia", "história",
    "abraao", "abraão", "moises", "moisés", "davi", "paulo", "pedro",
    "olha", "presta", "atencao", "atenção", "entenda", "voce", "você",
    "porque", "portanto", "significa", "aplicacao", "aplicação", "disse"
}

def classificar_conteudo_bloco(texto):
    """Retorna 'musica' ou 'pregacao' olhando texto, repetição e vocabulário.
    É heurístico e serve para escolher a lógica de corte certa sem depender da IA.
    """
    normal = _norm(texto or "")
    if not normal:
        return "pregacao"
    palavras = [p.strip(".,!?;:()[]{}\"'") for p in normal.split() if p.strip(".,!?;:()[]{}\"'")]
    music_score = 0
    prega_score = 0
    for termo in PALAVRAS_MUSICA_LOUVOR:
        if _norm(termo) in normal:
            music_score += 5
    for termo in PALAVRAS_PREGA_FALA:
        if _norm(termo) in normal:
            prega_score += 4
    for frase, peso in FRASES_MUSICA_IMPACTO.items():
        if _norm(frase) in normal:
            music_score += max(5, int(peso/4))
    # Música costuma repetir palavras/frases curtas; pregação costuma ter frases longas e explicativas.
    if palavras:
        repeticao = len(palavras) - len(set(palavras))
        if repeticao >= 3:
            music_score += min(18, repeticao * 3)
        media_len = sum(len(p) for p in palavras) / max(1, len(palavras))
        if len(palavras) <= 22 and repeticao >= 2:
            music_score += 10
        if len(palavras) >= 34:
            prega_score += 8
    if re.search(r"\b(versiculo|versículo|capitulo|capítulo|a biblia diz|está escrito|esta escrito)\b", normal):
        prega_score += 18
    if re.search(r"\b(refr[aã]o|ponte|coro|cant[a-z]*|adora[a-z]*|louvor)\b", normal):
        music_score += 16
    return "musica" if music_score >= prega_score + 8 else "pregacao"


def tipo_conteudo_atual(texto=""):
    """Usa o seletor manual do painel. Se o usuário ativar detecção automática, classifica pelo texto."""
    manual = str(config_usuario.get("tipo_conteudo", CONFIG.get("tipo_conteudo", "pregacao"))).lower().strip()
    if manual not in ("pregacao", "musica"):
        manual = "pregacao"
    if bool(config_usuario.get("detectar_musica_pregacao", CONFIG.get("detectar_musica_pregacao", False))):
        return classificar_conteudo_bloco(texto or "")
    return manual


def clip_mode_atual():
    """Modo principal v1.0.102: mixed, sermon, podcast ou worship.
    Aceita nomes antigos para não quebrar painel/config de versões anteriores.
    """
    modo = str(config_usuario.get("clip_mode", config_usuario.get("modo_conteudo", config_usuario.get("tipo_conteudo", CONFIG.get("clip_mode", "mixed")))) or "mixed").lower().strip()
    aliases = {
        "misto": "mixed", "culto": "mixed", "culto_completo": "mixed", "culto completo": "mixed", "auto": "mixed", "automatico": "mixed", "automático": "mixed",
        "pregacao": "sermon", "pregação": "sermon", "sermao": "sermon", "sermão": "sermon",
        "pregacao_traduzida": "bilingual_sermon", "pregação traduzida": "bilingual_sermon", "traduzida": "bilingual_sermon", "bilingue": "bilingual_sermon", "bilíngue": "bilingual_sermon",
        "podcast_cristao": "podcast", "podcast cristao": "podcast", "podcast cristão": "podcast",
        "louvor": "worship", "musica": "worship", "música": "worship", "adoracao": "worship", "adoração": "worship",
    }
    modo = aliases.get(modo, modo)
    if modo not in ("mixed", "sermon", "podcast", "worship", "bilingual_sermon"):
        modo = "mixed"
    return modo

def manual_moment_atual():
    momento = str(config_usuario.get("manual_moment", CONFIG.get("manual_moment", "auto")) or "auto").lower().strip()
    aliases = {"pregacao":"sermon","pregação":"sermon","louvor":"worship","adoracao":"worship","adoração":"worship","ministracao":"ministry","ministração":"ministry","apelo":"ministry"}
    momento = aliases.get(momento, momento)
    if momento not in ("auto", "sermon", "worship", "ministry"):
        momento = "auto"
    return momento

def worship_intelligence_atual():
    modo = str(config_usuario.get("worship_intelligence", CONFIG.get("worship_intelligence", "auto")) or "auto").lower().strip()
    aliases = {"automatica":"auto", "automática":"auto", "desligada":"off", "ligada":"always", "sempre":"always", "avancada":"always", "avançada":"always"}
    modo = aliases.get(modo, modo)
    if modo not in ("auto", "off", "always"):
        modo = "auto"
    return modo

def performance_mode_atual():
    modo = str(config_usuario.get("performance_mode", CONFIG.get("performance_mode", "auto")) or "auto").lower().strip()
    aliases = {"leve":"light", "avancado":"advanced", "avançado":"advanced", "automatico":"auto", "automático":"auto"}
    modo = aliases.get(modo, modo)
    if modo not in ("auto", "light", "advanced"):
        modo = "auto"
    return modo

def bilingual_context_atual():
    modo = str(config_usuario.get("bilingual_context", CONFIG.get("bilingual_context", "auto")) or "auto").lower().strip()
    aliases = {"automatico":"auto", "automático":"auto", "ligado":"on", "ativado":"on", "desligado":"off"}
    modo = aliases.get(modo, modo)
    if modo not in ("auto", "on", "off"):
        modo = "auto"
    return modo


def tipo_conteudo_por_modo(texto=""):
    """Adapta o modo novo ao classificador antigo de texto.
    mixed identifica pelo texto; worship força música; sermon/podcast priorizam fala.
    """
    modo = clip_mode_atual()
    if modo == "worship":
        return "musica"
    if modo in ("sermon", "podcast", "bilingual_sermon"):
        return "pregacao"
    return classificar_conteudo_bloco(texto or "")


def audio_features_misto(audio, sr=16000):
    """Análise leve de áudio só com numpy para não quebrar instalação.
    Retorna métricas suficientes para diferenciar silêncio, fala, música dominante e clímax.
    """
    try:
        a = np.asarray(audio, dtype=np.float32).flatten()
        if len(a) == 0:
            return {"rms":0.0,"peak":0.0,"dynamic":0.0,"zcr":0.0,"energy_score":0,"music_score":0,"speech_score":0,"kind":"silence"}
        a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
        rms = float(np.sqrt(np.mean(np.square(a))))
        peak = float(np.max(np.abs(a))) if len(a) else 0.0
        frame = max(256, int(sr * 0.25))
        hop = frame
        vals = []
        for i in range(0, max(1, len(a)-frame+1), hop):
            x = a[i:i+frame]
            if len(x):
                vals.append(float(np.sqrt(np.mean(np.square(x)))))
        if not vals: vals = [rms]
        med = float(np.median(vals))
        mx = float(max(vals))
        dynamic = float((mx - med) / max(0.001, med))
        signs = np.sign(a)
        zcr = float(np.mean(np.abs(np.diff(signs)) > 0)) if len(a) > 2 else 0.0
        crest = peak / max(0.001, rms)
        energy_score = int(max(0, min(100, (rms / 0.055) * 55 + dynamic * 18 + min(crest, 8) * 2)))
        music_score = int(max(0, min(100, energy_score + (12 if zcr < 0.18 else 0) + (10 if dynamic > 0.7 else 0))))
        speech_score = int(max(0, min(100, (rms / 0.045) * 45 + (18 if 0.08 <= zcr <= 0.32 else 4))))
        if rms < float(config_usuario.get("audio_min_rms_para_status", CONFIG.get("audio_min_rms_para_status", 0.006))):
            kind = "silence"
        elif music_score >= max(58, speech_score + 8):
            kind = "music"
        elif music_score >= 50 and speech_score >= 45:
            kind = "speech_with_music"
        else:
            kind = "speech"
        return {"rms":rms,"peak":peak,"dynamic":dynamic,"zcr":zcr,"crest":crest,"energy_score":energy_score,"music_score":music_score,"speech_score":speech_score,"kind":kind}
    except Exception as e:
        return {"rms":0.0,"peak":0.0,"dynamic":0.0,"zcr":0.0,"energy_score":0,"music_score":0,"speech_score":0,"kind":"unknown","error":str(e)}


ultimo_corte_musical_audio = 0.0
music_audio_segment_start = None
music_audio_segment_seconds = 0.0
music_audio_invalidos = 0
ultima_linha_musical_status = 0.0

def emitir_transcricao_musical_detectada(t, kind, feats=None, motivo="music-status"):
    """Mostra no painel/terminal quando o bloco é louvor/melodia, mesmo sem letra confiável.
    Não inventa letra: se o ASR não entendeu a parte cantada, exibimos status musical seguro.
    Quando o Whisper conseguir letra válida, o fluxo normal mostra a transcrição cantada.
    """
    global ultima_linha_musical_status, linhas
    try:
        if not bool(config_usuario.get("music_emit_transcription_status", CONFIG.get("music_emit_transcription_status", True))):
            return
        now_t = float(t or 0)
        min_gap = float(config_usuario.get("music_transcription_status_interval", CONFIG.get("music_transcription_status_interval", 8)))
        if ultima_linha_musical_status and now_t - float(ultima_linha_musical_status) < min_gap:
            return
        if kind == "music":
            texto = "[louvor instrumental / melodia detectada]"
        elif kind == "speech_with_music":
            texto = "[louvor com voz detectada — aguardando letra confiável]"
        else:
            texto = "[áudio musical detectado]"
        linha = {
            "tipo": "linha",
            "texto": texto,
            "inicio": round(max(0.0, now_t - 1.0), 2),
            "fim": round(now_t, 2),
            "timestamp": fmt(now_t),
            "volume_rms": round(float((feats or {}).get("rms", 0.0) or 0.0), 4),
            "pico_voz": False,
            "transcricao_origem": "music-detector",
            "language_profile": perfil_id_atual(),
            "music_status": True,
            "motivo": motivo
        }
        linhas.append(linha)
        enviar(linha)
        ultima_linha_musical_status = now_t
        print(f"[{linha['timestamp']}] {texto}")
    except Exception as e:
        print(f"[music] falha ao enviar status de transcricao musical: {e}")

def registrar_corte_musical_audio(t0, bloco_segundos, feats, motivo="music-audio"):
    """Gera candidato de corte para louvor/ministração mesmo quando o Whisper não devolve texto.
    Hotfix v1.0.106: força candidato de áudio quando o ASR trava em speech_with_music.
    Não cria SRT falso. Só usa o áudio para clipar momento musical/emocional.
    """
    global ultimo_corte_musical_audio, music_audio_segment_start, music_audio_segment_seconds, music_audio_invalidos
    modo = clip_mode_atual()
    if modo not in ("mixed", "worship"):
        return False

    bloco = max(1.0, float(bloco_segundos or 0))
    now_t = float(t0 or 0) + bloco
    kind = str(feats.get("kind", "unknown"))

    if kind not in ("music", "speech_with_music"):
        music_audio_segment_start = None
        music_audio_segment_seconds = 0.0
        music_audio_invalidos = 0
        return False

    if music_audio_segment_start is None:
        music_audio_segment_start = max(0.0, now_t - bloco)
        music_audio_segment_seconds = 0.0
        music_audio_invalidos = 0

    music_audio_segment_seconds += bloco
    if any(x in str(motivo).lower() for x in ("whisper", "asr", "invalido", "falhou")):
        music_audio_invalidos += 1

    emitir_transcricao_musical_detectada(now_t, kind, feats, motivo=motivo)

    dur_min = float(config_usuario.get("duracao_corte_min", CONFIG.get("duracao_corte_min", 35)))
    dur_min = max(25.0, min(45.0, dur_min))
    force_after = int(config_usuario.get("music_asr_force_after_invalid", CONFIG.get("music_asr_force_after_invalid", 2)))
    force_after = max(1, force_after)
    # v1.0.105: se o ASR falhar 2x em fala com música, não espera indefinidamente.
    # Dispara candidato por áudio a partir de 30s e o normalizador expande o clipe final para 35-90s.
    force_min = min(dur_min, float(config_usuario.get("music_force_min_seconds", CONFIG.get("music_force_min_seconds", 30))))
    force_min = max(20.0, min(35.0, force_min))
    forced = music_audio_invalidos >= force_after and music_audio_segment_seconds >= force_min

    if music_audio_segment_seconds < dur_min and not forced:
        print(f"[music] acumulando contexto: tipo={kind} dur={music_audio_segment_seconds:.0f}/{dur_min:.0f}s invalidos={music_audio_invalidos} force_min={force_min:.0f}s")
        return False

    cooldown_padrao = max(45, int(config_usuario.get("worship_cooldown_seg", config_usuario.get("cooldown_corte_seg", CONFIG.get("cooldown_corte_seg", 60)))))
    cooldown = 20 if forced else cooldown_padrao
    if cooldown > 0 and ultimo_corte_musical_audio and now_t - float(ultimo_corte_musical_audio or 0) < cooldown:
        print(f"[music] contexto bom, mas em cooldown: restante={int(cooldown - (now_t - float(ultimo_corte_musical_audio or 0)))}s")
        return False

    score = int(feats.get("music_score", feats.get("energy_score", 0)) or 0)
    limiar = 72 if modo == "mixed" else 62
    if kind == "speech_with_music":
        score = max(score, int((feats.get("music_score",0)*0.55) + (feats.get("speech_score",0)*0.45)))
        limiar = 78

    if forced:
        limiar = 62 if kind == "speech_with_music" else min(limiar, 68)
        score = max(limiar, min(86, int((feats.get("music_score",0)*0.45) + (feats.get("speech_score",0)*0.25) + (feats.get("energy_score",0)*0.20) + 12)))
        print(f"[music] FORCE AUDIO v1.0.107: ASR invalido={music_audio_invalidos} tipo={kind} dur={music_audio_segment_seconds:.0f}s score={score} -> candidato sem SRT falso")

    if score < limiar:
        print(f"[music] aguardando momento mais forte: score={score} limiar={limiar} tipo={kind} dur={music_audio_segment_seconds:.0f}s")
        return False

    titulo = "Louvor - Momento de adoração" if modo == "worship" else "Culto - Momento com música"
    if forced and kind == "speech_with_music":
        titulo = "Louvor - Voz com música" if modo == "worship" else "Culto - Fala com música"
    if feats.get("dynamic",0) > 0.85:
        titulo = "Louvor - Clímax de adoração" if modo == "worship" else "Culto - Virada emocional"

    texto = "Trecho detectado pelo áudio em modo louvor/fala com música. Sem legenda forçada para evitar SRT errado."
    razao = f"{motivo}: energia={feats.get('energy_score',0)} musica={feats.get('music_score',0)} fala={feats.get('speech_score',0)} dinamica={round(float(feats.get('dynamic',0)),2)} invalidos={music_audio_invalidos} forced={forced}"
    registrar_corte(texto, min(100, max(score, limiar)), titulo, razao, now_t, emocao="adoração", funcao="clímax musical", origem="mixed-worship-audio")
    ultimo_corte_musical_audio = now_t
    print(f"[music] corte candidato por áudio: score={score} tipo={kind} dur={music_audio_segment_seconds:.0f}s forced={forced} t={fmt(now_t)}")

    music_audio_segment_start = None
    music_audio_segment_seconds = 0.0
    music_audio_invalidos = 0
    return True


def score_heuristico_musica(texto):
    # v1.0.107: pontuação emocional de louvor.
    original = texto.strip()
    if fz107_parece_video_externo(original):
        return 0, ["vídeo externo/propaganda bloqueado"], "neutro", "ignorado"
    score, razoes, emocao, funcao = fz107_score_emocional_louvor(original, {})
    return score, razoes, emocao, funcao

EMOCOES_LOCAL = [
    ("quebrantamento", ["choro","dor","perdao","arrependimento","quebrantado","quebrantamento"]),
    ("fé", ["fe","creia","impossivel","milagre","promessa","vitoria"]),
    ("esperança", ["esperanca","recomeco","amanha","novo","restaurar","levanta"]),
    ("urgência", ["hoje","agora","tempo","hora","decida","escolha"]),
    ("convicção", ["declaro","profetizo","verdade","nunca","sempre","receba"]),
]

def _norm(txt):
    txt = txt.lower()
    txt = txt.replace("ã","a").replace("á","a").replace("à","a").replace("â","a")
    txt = txt.replace("é","e").replace("ê","e").replace("í","i")
    txt = txt.replace("ó","o").replace("ô","o").replace("õ","o").replace("ú","u").replace("ç","c")
    return re.sub(r"\s+", " ", txt).strip()

def corte_modo_atual():
    modo = str(config_usuario.get("corte_modo", config_usuario.get("modo_corte", "standard"))).lower().strip()
    return "fast" if modo == "fast" else "standard"

def current_limiar():
    try:
        base = int(config_usuario.get("limiar_corte", CONFIG["limiar_corte"]))
    except Exception:
        base = CONFIG["limiar_corte"]
    # Corte Seguro precisa ser mais delicado: score ruim não pode virar 100 e cortar toda hora.
    if corte_modo_atual() == "standard":
        return max(60, base)
    return max(60, base)

def duracao_cortes_config():
    """Retorna duração mínima/máxima configurada no painel.
    Esta função é a autoridade única para evitar clipes de Replay Buffer com 2 minutos.
    """
    try:
        mn = int(config_usuario.get("duracao_corte_min", config_usuario.get("chunk_seconds_min", CONFIG.get("duracao_corte_min", 35))))
    except Exception:
        mn = int(CONFIG.get("duracao_corte_min", 35))
    try:
        mx = int(config_usuario.get("duracao_corte_max", config_usuario.get("chunk_seconds_max", CONFIG.get("duracao_corte_max", 90))))
    except Exception:
        mx = int(CONFIG.get("duracao_corte_max", 90))
    # Padrão oficial v1.0.103: 35s a 90s. Mantém limite superior seguro.
    mn = max(35, min(300, mn))
    mx = max(mn, min(300, mx))
    return mn, mx

def normalizar_janela_corte(inicio, fim, pico=None):
    """Garante que qualquer corte respeite exatamente min/max do painel.
    Se a janela vier maior (ex: replay buffer 120s), recorta ao redor do pico.
    """
    mn, mx = duracao_cortes_config()
    try: inicio = float(inicio or 0)
    except Exception: inicio = 0.0
    try: fim = float(fim or 0)
    except Exception: fim = inicio
    if pico is None:
        pico = fim if fim > inicio else inicio
    try: pico = float(pico or 0)
    except Exception: pico = inicio
    inicio = max(0.0, inicio)
    fim = max(inicio, fim)
    dur = fim - inicio
    if dur <= 0:
        # manual: pega a duração máxima anterior ao momento atual
        fim = max(inicio + mn, pico)
        inicio = max(0.0, fim - mx)
        dur = fim - inicio
    if dur > mx:
        # Mantém o pico dentro do clipe, com contexto antes e depois.
        antes = min(max(5.0, mx * 0.55), max(0.0, pico - inicio))
        novo_ini = max(0.0, pico - antes)
        novo_fim = novo_ini + mx
        if novo_fim < pico:
            novo_fim = pico
            novo_ini = max(0.0, novo_fim - mx)
        inicio, fim, dur = novo_ini, novo_fim, mx
    if dur < mn:
        extra = mn - dur
        inicio = max(0.0, inicio - extra * 0.55)
        fim = inicio + mn
        dur = mn
    # Segurança final: nunca ultrapassar máximo configurado.
    if dur > mx:
        fim = inicio + mx
        dur = mx
    return round(inicio, 2), round(fim, 2), round(dur, 2)


def score_heuristico(texto):
    """Pontua uma frase sem OpenAI. Projetado para cortar pouco, mas cortar sozinho.
    Em modo automático, primeiro entende se o trecho é música/louvor ou pregação.
    """
    original = texto.strip()
    if tipo_conteudo_por_modo(original) == "musica":
        return score_heuristico_musica(original)
    normal = _norm(original)
    palavras = [p.strip(".,!?;:()[]{}\"'") for p in normal.split()]
    palavras = [p for p in palavras if p]
    if len(palavras) < 4:
        return 0, [], "", ""

    score = 0
    razoes = []

    # v1.1.3 Global All Languages + Clean Install + Plugin Detect Fix: bônus por perfil de idioma escolhido no painel.
    try:
        bonus_global, raz_global = score_global_idioma(original)
        if bonus_global:
            score += bonus_global
            razoes.extend(raz_global)
    except Exception:
        pass

    # Frases compostas valem mais que palavras soltas.
    for frase, peso in FRASES_IMPACTO.items():
        if _norm(frase) in normal:
            score += peso
            razoes.append(frase)

    # Camada viral/emocional para pregação: historia, tensao, virada e aplicação.
    for frase, peso in FRASES_VIRAIS_PREGA.items():
        if _norm(frase) in normal:
            score += peso
            razoes.append("viral: " + frase)

    n_emo = sum(1 for p in palavras if p in {_norm(x) for x in PALAVRAS_EMOCIONAIS_PREGA})
    if n_emo:
        score += min(n_emo * 7, 34)
        razoes.append("emoção espiritual")

    n_imp = sum(1 for p in palavras if p in {_norm(x) for x in PALAVRAS_IMPACTO})
    if n_imp:
        score += min(n_imp * 10, 38)
        razoes.append("palavras fortes")

    # Frases curtas/médias funcionam melhor como corte.
    if 7 <= len(palavras) <= 28:
        score += 12
    elif 29 <= len(palavras) <= 45:
        score += 6

    # Gatilhos de fala que geralmente viram corte.
    if "?" in original:
        score += 10; razoes.append("pergunta")
    if "!" in original:
        score += 8; razoes.append("ênfase")
    if re.search(r"\b(voce|você|tu|alguem|alguém|quem)\b", normal):
        score += 8
    if re.search(r"\b(hoje|agora|nunca|sempre|precisa|deve|pare|levanta|receba)\b", normal):
        score += 10; razoes.append("chamada")
    if re.search(r"\b(eu lembro|um dia|quando eu|teve uma vez|historia|história)\b", normal):
        score += 8; razoes.append("história")

    # Repetição de palavras importantes aumenta impacto.
    reps = len(palavras) - len(set(palavras))
    if reps >= 3:
        score += 5

    emocao = "fé"
    for nome, termos in EMOCOES_LOCAL:
        if any(_norm(t) in palavras or _norm(t) in normal for t in termos):
            emocao = nome
            break

    if any(r in razoes for r in ["pergunta", "chamada"]):
        funcao = "gancho"
    elif "história" in razoes:
        funcao = "história"
    elif score >= 78:
        funcao = "clímax"
    else:
        funcao = "declaração"

    # v81: calibração anti-score inflado.
    # Antes, palavras isoladas como "Deus", "hoje", "receba" podiam somar 100.
    # Agora 90+ só acontece quando há combinação de gancho + aplicação/virada + contexto.
    tem_direcao = bool(re.search(r"\b(voce|você|tu|alguem|alguém|quem|sua|seu|te|ti)\b", normal))
    tem_aplicacao = bool(re.search(r"\b(hoje|agora|precisa|deve|pare|levanta|receba|decida|escolha|nao desista|não desista|a partir de hoje|eu vim te dizer|eu quero te dizer)\b", normal))
    tem_virada = bool(re.search(r"\b(mas deus|so que deus|só que deus|de repente|foi ai que|foi aí que|ate que|até que|quando deus)\b", normal))
    tem_historia = bool(re.search(r"\b(historia|história|quando eu|um dia|teve uma vez|eu lembro|ele chegou|ela chegou)\b", normal))
    tem_base_biblica = bool(re.search(r"\b(biblia|bíblia|est[aá] escrito|versiculo|versículo|capitulo|capítulo)\b", normal))
    tem_frase_impacto = any(_norm(frase) in normal for frase in list(FRASES_IMPACTO.keys()) + list(FRASES_VIRAIS_PREGA.keys()))
    sinais_qualidade = sum([tem_direcao, tem_aplicacao, tem_virada, tem_historia, tem_base_biblica, tem_frase_impacto])

    # Penaliza fillers/trechos sem ideia fechada.
    if re.fullmatch(r"(e|aí|ai|né|tipo|então|entao|amém|amem|aleluia|glória|gloria|senhor|deus|jesus)[\s,.!?-]*", normal):
        score = min(score, 35)
    if len(palavras) < 8:
        score = min(score, 62)
    elif len(palavras) < 12 and sinais_qualidade < 3:
        score = min(score, 74)
    if len(palavras) > 70:
        score = min(score, 82)

    # Se não tem combinação de sinais, não pode parecer "100".
    if sinais_qualidade <= 1:
        score = min(score, 76)
    elif sinais_qualidade == 2:
        score = min(score, 86)
    elif sinais_qualidade == 3:
        score = min(score, 94)

    # 98-100 reservado para corte realmente excepcional, não para qualquer frase forte.
    if score >= 98 and sinais_qualidade < 5:
        score = 96
    if score >= 90 and not (tem_aplicacao or tem_virada or tem_direcao):
        score = 88

    return min(score, 100), razoes[:4], emocao, funcao

def titulo_local(texto, emocao, funcao):
    palavras = [p.strip(".,!?;:()[]{}\"'") for p in texto.split()]
    normal = _norm(texto)
    if "mas deus" in normal or "so que deus" in normal or "só que deus" in normal:
        return "Quando Deus entra na história"
    if "quem voce pensa que e" in normal or "quem você pensa que é" in normal:
        return "Quem você pensa que é?"
    if "sabe" in normal and "deus" in normal:
        return "Você sabe o que Deus está dizendo?"
    base = " ".join(palavras[:8]).strip()
    if len(base) > 46:
        base = base[:43].rstrip() + "..."
    if not base:
        base = f"Momento de {emocao}"
    return base[0].upper() + base[1:]

def cortes_locais(linhas_acumuladas):
    """Recebe [(tempo,texto)] e devolve cortes locais candidatos."""
    candidatos = []
    for i, (tt, tx) in enumerate(linhas_acumuladas):
        textos = [(tt, tx)]
        if i > 0:
            textos.append((linhas_acumuladas[i-1][0], linhas_acumuladas[i-1][1] + " " + tx))
        for tempo, texto in textos:
            s, raz, emocao, funcao = score_heuristico(texto)
            if volume_pico_no_tempo(tempo):
                s = min(100, s + 12)
                raz = (raz or []) + ["pico de voz/presença"]
                if emocao == "fé":
                    emocao = "presença"
            modo_corte = corte_modo_atual()
            limite_candidato = max(60, current_limiar() - (8 if modo_corte == "fast" else 2))
            # Corte Seguro só considera trechos com substância.
            if modo_corte == "standard" and len([p for p in _norm(texto).split() if p]) < 10:
                continue
            if s >= limite_candidato:
                candidatos.append({
                    "trecho": texto.strip(),
                    "score": s,
                    "titulo": titulo_local(texto, emocao, funcao),
                    "razao": ", ".join(raz) if raz else "detecção local",
                    "emocao": emocao,
                    "funcao": funcao,
                    "tempo": tempo,
                })
    # Melhor candidato da rodada para evitar excesso de clipes.
    candidatos.sort(key=lambda c: c["score"], reverse=True)
    return candidatos[:1]

ultimos_cortes_locais = []

def corte_local_repetido(texto, tempo):
    """Evita clipes duplicados quando a mesma frase aparece em janelas consecutivas."""
    global ultimos_cortes_locais
    normal = _norm(texto)[:90]
    cooldown = int(config_usuario.get("cooldown_corte_seg", CONFIG["cooldown_corte_seg"]))
    if corte_modo_atual() == "standard":
        cooldown = max(cooldown, 55)
    novos = []
    repetido = False
    for ant_txt, ant_t in ultimos_cortes_locais:
        if tempo - ant_t < cooldown:
            novos.append((ant_txt, ant_t))
            if normal and (normal in ant_txt or ant_txt in normal):
                repetido = True
    ultimos_cortes_locais = novos
    if repetido:
        return True
    ultimos_cortes_locais.append((normal, tempo))
    return False

def volume_pico_no_tempo(tempo):
    # considera pico se qualquer linha nos últimos ~2s teve volume acima do normal.
    try:
        t = float(tempo)
        for k, v in list(volume_picos.items()):
            if abs(float(k) - t) <= 2.5 and v:
                return True
    except Exception:
        pass
    return False

# ----------------------------- ESTADO -----------------------------
# ----------------------------- ESTADO -----------------------------

fila_audio = queue.Queue()
fila_analise = queue.Queue()
clientes = set()
loop_principal = None

gravando = False
transcricao_ativa_runtime = True
inicio_gravacao = None
gravacao_completa = None  # caminho do arquivo completo que o OBS gravou
linhas = []
cortes = []
obs_req = None            # cliente de request do OBS (pra disparar replay)
obs_conectado = False     # OBS WebSocket conectou com sucesso?

texto_desde_ia = []       # acumula linhas ate a proxima analise da IA
texto_contexto_ia = []     # janela movel maior para Gemini entender o assunto antes de cortar
ultima_ia = 0

# Sinais simples de presença/volume da fala para reforçar cortes emocionais.
volume_historico = []
volume_picos = {}

# Fila de clipes que pediram save mas ainda nao terminaram (pra renomear depois).
# Cada item: {"titulo","timestamp","inicio","fim"}
clipes_pendentes = queue.Queue()

# Pastas principais da sessão
pasta_cortes_ao_vivo = None
pasta_cortes_finais = None

# ----------------------------- AUDIO / TEMPO -----------------------------

stream_audio = None  # o InputStream atual
loopback_audio_thread = None
loopback_audio_stop = None

audio_status_atual = {"ok": False, "nome": "não iniciado", "rms": 0.0, "msg": "aguardando áudio"}
vps_status_atual = {"ok": True, "modo": "local", "msg": "MLX local/offline", "url": ""}
ultimo_status_audio_envio = 0
ultimo_status_vps_envio = 0

# Fonte de audio ativa: "dispositivo" (seletor local) ou "plugin" (mixer do OBS)
fonte_audio = "dispositivo"
plugin_conectado = False

def parse_audio_plugin(data):
    """
    Decodifica o pacote binario do obs-audio-to-websocket.
    Cabecalho de 28 bytes (little-endian), depois strings, depois PCM 16-bit.
    Devolve (audio_float32_mono, sample_rate) ou (None, None) se invalido.
    """
    import struct
    try:
        if len(data) < 28:
            return None, None
        off = 0
        # timestamp(8) sample_rate(4) channels(4) bit_depth(4) idLen(4) nameLen(4)
        _ts = struct.unpack_from("<Q", data, off)[0]; off += 8
        sr = struct.unpack_from("<I", data, off)[0]; off += 4
        ch = struct.unpack_from("<I", data, off)[0]; off += 4
        _bd = struct.unpack_from("<I", data, off)[0]; off += 4
        id_len = struct.unpack_from("<I", data, off)[0]; off += 4
        nm_len = struct.unpack_from("<I", data, off)[0]; off += 4
        off += id_len + nm_len  # pula as strings de id e nome da fonte
        pcm = data[off:]
        if not pcm:
            return None, None
        amostras = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        if ch == 2:  # estereo interleaved -> mono
            amostras = amostras.reshape(-1, 2).mean(axis=1)
        return amostras, sr
    except Exception as e:
        print(f"[plugin] pacote invalido: {e}")
        return None, None

def reamostrar(audio, sr_origem, sr_destino):
    """Reamostragem linear simples (sem dependencia extra) pro ASR (16kHz)."""
    if sr_origem == sr_destino or len(audio) == 0:
        return audio
    razao = sr_destino / sr_origem
    n_novo = int(len(audio) * razao)
    if n_novo <= 0:
        return audio
    idx = np.linspace(0, len(audio) - 1, n_novo)
    return np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)

def preparar_audio_whisper(audio):
    """Limpa e nivela o bloco antes de transcrever.
    Ajuda muito quando o audio vem baixo do OBS/BlackHole ou com DC offset.
    """
    if audio is None or len(audio) == 0:
        return audio
    audio = audio.astype(np.float32)
    audio = audio - float(np.mean(audio))
    rms = float(np.sqrt(np.mean(audio * audio)) + 1e-9)
    pico = float(np.max(np.abs(audio)) + 1e-9)

    # Se o audio estiver baixo, sobe o nivel sem estourar.
    # Mantem limite conservador para nao distorcer a voz.
    if rms < 0.045:
        ganho = min(6.0, 0.075 / rms)
        audio = audio * ganho

    pico = float(np.max(np.abs(audio)) + 1e-9)
    if pico > 0.98:
        audio = audio / pico * 0.98
    return np.clip(audio, -1.0, 1.0).astype(np.float32)



def audio_para_wav_bytes(audio, sample_rate=16000):
    """Converte float32 mono [-1,1] para WAV 16-bit em memoria."""
    audio = np.asarray(audio, dtype=np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype('<i2')
    bio = io.BytesIO()
    with wave.open(bio, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm.tobytes())
    bio.seek(0)
    return bio.getvalue()


def _vps_url(endpoint=None):
    """Monta URL da VPS. v74 bloqueia /transcribe porque ele alucinou/ecoou prompt."""
    allowed = ("/transcribe-fastwhisper",)
    old_ep = "/transcribe-" + "funasr"
    if endpoint is None:
        explicit = config_usuario.get('whisper_vps_url') or CONFIG.get('whisper_vps_url')
        if explicit:
            explicit = str(explicit).replace(old_ep, "/transcribe-fastwhisper")
            if explicit.endswith(allowed):
                return explicit
        endpoint = config_usuario.get('whisper_vps_endpoint') or CONFIG.get('whisper_vps_endpoint', '/transcribe-fastwhisper')
    base = (config_usuario.get('whisper_vps_base_url') or CONFIG.get('whisper_vps_base_url') or '').rstrip('/')
    endpoint = str(endpoint or '').strip().replace(old_ep, "/transcribe-fastwhisper")
    if endpoint.startswith('http://') or endpoint.startswith('https://'):
        if endpoint.endswith(old_ep):
            endpoint = endpoint.replace(old_ep, "/transcribe-fastwhisper")
        if endpoint.endswith(allowed):
            return endpoint
        return base + "/transcribe-fastwhisper" if base else "http://2.25.157.230:8000/transcribe-fastwhisper"
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    if endpoint not in allowed:
        endpoint = '/transcribe-fastwhisper'
    return base + endpoint

def _vps_headers(extra_plain=False):
    token = config_usuario.get('whisper_vps_token') or CONFIG.get('whisper_vps_token')
    header_name = config_usuario.get('vps_auth_header') or CONFIG.get('vps_auth_header', 'x-api-key')
    headers = {}
    if token:
        # Header obrigatorio da VPS OBS ASR + IA.
        headers[str(header_name)] = token
        # Compatibilidade opcional com builds antigos. A VPS atual usa x-api-key.
        if extra_plain:
            headers['x-api-key'] = token
            headers['Authorization'] = f'Bearer {token}'
            headers['X-API-Key'] = token
            headers['X-FrameZero-Key'] = token
    return headers


def _extrair_transcricao_vps(resp):
    """Aceita respostas da fase 1 e também formatos comuns de APIs ASR."""
    if not isinstance(resp, dict):
        return str(resp or '').strip(), []
    texto = (resp.get('text') or resp.get('texto') or resp.get('transcription') or
             resp.get('transcricao') or resp.get('result') or resp.get('resultado') or '').strip()
    segmentos = resp.get('segments') or resp.get('segmentos') or resp.get('chunks') or []
    if not texto and isinstance(segmentos, list):
        texto = ' '.join(str(x.get('text') or x.get('texto') or '').strip() for x in segmentos if isinstance(x, dict)).strip()
    return texto, segmentos if isinstance(segmentos, list) else []


def _poll_job_vps(job_id):
    """Suporte futuro para Fase 2: /jobs/{id} com status em background."""
    if not job_id or not config_usuario.get('vps_poll_jobs', CONFIG.get('vps_poll_jobs', True)):
        return '', []
    import time as _time
    jobs_ep = config_usuario.get('whisper_vps_jobs_endpoint') or CONFIG.get('whisper_vps_jobs_endpoint', '/jobs')
    url = _vps_url(str(jobs_ep).rstrip('/') + '/' + str(job_id))
    timeout_total = float(config_usuario.get('vps_job_timeout_seg', CONFIG.get('vps_job_timeout_seg', 180)))
    deadline = _time.time() + timeout_total
    while _time.time() < deadline:
        r = requests.get(url, headers=_vps_headers(True), timeout=15)
        r.raise_for_status()
        data = r.json()
        status = str(data.get('status') or data.get('estado') or '').lower()
        if status in ('concluido', 'concluído', 'completed', 'done', 'ok', 'success') or data.get('text') or data.get('texto') or data.get('segments'):
            return _extrair_transcricao_vps(data)
        if status in ('erro', 'error', 'failed', 'falhou'):
            raise RuntimeError(f"job VPS falhou: {data}")
        _time.sleep(2.0)
    raise TimeoutError('timeout aguardando job da VPS atual')


def transcrever_vps(audio):
    """Envia um bloco WAV para a VPS atual e devolve (texto, segmentos).
    Compatível com a API OBS faster-whisper:
      POST /transcribe multipart/form-data campo file
      retorno: {text/texto, segments/segmentos}
    Também já suporta uma futura Fase 2 com job_id + /jobs/{id}.
    """
    if requests is None:
        raise RuntimeError("biblioteca requests nao instalada")
    url = _vps_url()
    if not url:
        raise RuntimeError("whisper_vps_url/base_url nao configurada")

    wav = audio_para_wav_bytes(audio, CONFIG['sample_rate'])
    files = {'file': ('framezero_live.wav', wav, 'audio/wav')}
    data = {
        'language': whisper_language_atual(),
        'task': 'transcribe',
        'format': 'json',
        'timestamps': 'true',
        'source': 'framezero_obs',
        'engine': config_usuario.get('transcription_engine', CONFIG.get('transcription_engine', 'whisper')),
    }
    timeout = float(config_usuario.get('vps_timeout_seg', CONFIG.get('vps_timeout_seg', 60)))
    r = requests.post(url, headers=_vps_headers(False), files=files, data=data, timeout=timeout)
    if r.status_code in (401, 403):
        # tenta outro formato comum de token antes de desistir
        r = requests.post(url, headers=_vps_headers(True), files=files, data=data, timeout=timeout)
    r.raise_for_status()

    try:
        resp = r.json()
    except Exception:
        txt = (r.text or '').strip()
        return txt, []

    # Fase 2: se a API devolver job_id em vez do texto na hora, o cliente já sabe aguardar.
    job_id = resp.get('job_id') or resp.get('id') if isinstance(resp, dict) else None
    status = str(resp.get('status') or resp.get('estado') or '').lower() if isinstance(resp, dict) else ''
    if job_id and status in ('aguardando', 'queued', 'processando', 'processing', 'pending'):
        return _poll_job_vps(job_id)

    return _extrair_transcricao_vps(resp)


def testar_vps_whisper():
    """Teste leve opcional. Nao trava se /health ainda nao existir na Fase 1."""
    if requests is None:
        return False, 'requests nao instalado'
    health = config_usuario.get('whisper_vps_health_endpoint') or CONFIG.get('whisper_vps_health_endpoint', '/health')
    try:
        r = requests.get(_vps_url(health), headers=_vps_headers(True), timeout=5)
        if r.status_code == 404:
            return True, 'API sem /health ainda, usando /transcribe-fastwhisper'
        r.raise_for_status()
        try:
            data = r.json()
            modelo = data.get('deepseek_model') or data.get('model') or data.get('modelo') or ''
            whisper = data.get('whisper') or ''
            whisper = data.get('whisper') or data.get('engine') or data.get('transcription_engine') or ''
            msg = 'VPS online'
            if modelo:
                msg += f' • IA: {modelo}'
            if whisper:
                msg += f' • Whisper: {whisper}'
            if whisper:
                msg += f' • Whisper: {whisper}'
            return True, msg
        except Exception:
            return True, 'VPS online'
    except Exception as e:
        return False, str(e)


def _parse_json_possivel(valor):
    """A API /analyze-text pode devolver analysis como string contendo JSON.
    Esta função tenta limpar markdown/think tags e transformar em dict.
    """
    if isinstance(valor, (dict, list)):
        return valor
    if valor is None:
        return None
    txt = str(valor).strip()
    if not txt:
        return None
    # remove blocos markdown e tags de raciocinio que modelos locais às vezes retornam
    txt = re.sub(r"```(?:json)?", "", txt, flags=re.I).replace("```", "").strip()
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.I|re.S).strip()
    try:
        return json.loads(txt)
    except Exception:
        pass
    # tenta extrair o maior objeto JSON dentro do texto
    ini = txt.find('{'); fim = txt.rfind('}')
    if ini >= 0 and fim > ini:
        try:
            return json.loads(txt[ini:fim+1])
        except Exception:
            return None
    return None



def _parse_analysis_texto_livre(txt, t_ref=0, texto_base=""):
    """A VPS pode retornar analysis como texto simples:
    Título: ...\nHook: ...\nMotivo: ...\nScore: ...\nLegenda: ...\nCapa: ...
    Transforma isso em um corte padrao.
    """
    txt = str(txt or "").strip()
    if not txt:
        return None
    def campo(nomes):
        for nome in nomes:
            m = re.search(rf"(?im)^\s*{nome}\s*[:\-]\s*(.+)$", txt)
            if m:
                return m.group(1).strip()
        return ""
    score_txt = campo(["Score", "Pontuação", "Pontuacao"])
    mscore = re.search(r"\d{1,3}", score_txt or txt)
    score = int(mscore.group(0)) if mscore else 0
    if score <= 0:
        # Se a IA respondeu texto útil mas sem score, não cria corte automático.
        return None
    titulo = campo(["Título", "Titulo", "Title"]) or titulo_local(texto_base or txt, "fé", "impacto")
    hook = campo(["Hook", "Gancho"])
    motivo = campo(["Motivo", "Reason", "Razão", "Razao"]) or "análise da IA local da VPS"
    legenda = campo(["Legenda", "Caption", "Suggested caption"])
    capa = campo(["Capa", "Cover"])
    return {
        "trecho": hook or (texto_base[:260] if texto_base else txt[:260]),
        "score": max(0, min(score, 100)),
        "titulo": titulo,
        "razao": motivo,
        "emocao": "fé",
        "funcao": "viral/emocional",
        "tempo": float(t_ref or 0),
        "suggested_caption": legenda,
        "hook": hook,
        "capa": capa,
    }

def _normalizar_cortes_vps(data, t_ref=0, texto_base=""):
    """Aceita formatos atuais/futuros da VPS e devolve lista padrão de cortes."""
    if not data:
        return []
    if isinstance(data, str):
        data = _parse_json_possivel(data)
    if not isinstance(data, dict):
        return []

    # /analyze-text atual pode ser:
    # {success, analysis:{...}} OU {success, analysis:"JSON"} OU {success, analysis:"Título: ... Score: ..."}
    if 'analysis' in data:
        valor_analysis = data.get('analysis')
        analisado = _parse_json_possivel(valor_analysis)
        if isinstance(analisado, dict):
            data = analisado
        else:
            corte_txt = _parse_analysis_texto_livre(valor_analysis, t_ref, texto_base)
            if corte_txt:
                return [corte_txt]

    bruto = data.get('cuts') or data.get('cortes') or data.get('moments') or data.get('momentos') or []
    # /analyze-live-chunk futuro pode devolver um único corte
    if not bruto and any(k in data for k in ('is_good_cut','score','title','titulo','hook')):
        if data.get('is_good_cut', True):
            bruto = [data]
    if isinstance(bruto, dict):
        bruto = [bruto]
    if not isinstance(bruto, list):
        return []

    out=[]
    for c in bruto:
        if not isinstance(c, dict):
            continue
        score = c.get('score') or c.get('viral_score') or c.get('pontuacao') or 0
        try: score = int(float(score))
        except Exception: score = 0
        if score <= 0:
            continue
        trecho = (c.get('trecho') or c.get('text') or c.get('texto') or c.get('quote') or c.get('hook') or texto_base[:260]).strip()
        titulo = (c.get('title') or c.get('titulo') or c.get('suggested_title') or c.get('sugestao_titulo') or titulo_local(trecho, c.get('emocao','fé'), c.get('funcao','impacto'))).strip()
        razao = (c.get('reason') or c.get('motivo') or c.get('razao') or c.get('razão') or 'análise da IA local da VPS').strip()
        emocao = (c.get('emotion') or c.get('emocao') or c.get('emoção') or 'fé').strip()
        funcao = (c.get('function') or c.get('funcao') or c.get('função') or c.get('narrative_function') or 'impacto').strip()
        ts = c.get('start_time') or c.get('inicio') or c.get('inicio_seg') or c.get('tempo') or t_ref
        try: ts = float(ts)
        except Exception: ts = float(t_ref or 0)
        # se veio tempo relativo ao bloco, soma t_ref quando fizer sentido
        if ts < 10 and t_ref > 10:
            ts = float(t_ref) + ts
        out.append({
            'trecho': trecho,
            'score': score,
            'titulo': titulo,
            'razao': razao,
            'emocao': emocao,
            'funcao': funcao,
            'tempo': ts,
            'suggested_caption': c.get('suggested_caption') or c.get('caption') or c.get('legenda') or '',
            'hook': c.get('hook') or ''
        })
    return out


PROMPT_GEMINI_CORTE = """Você é um diretor de edição de cortes para redes sociais em português brasileiro, especializado em pregação, culto, podcast e entrevista.

Sua função NÃO é transcrever. Você recebe texto já transcrito e decide se existe UM corte útil para post, Reels, TikTok ou Shorts.

REGRA PRINCIPAL DA v81e-score60:
- O limite/rating de corte em tempo real é 60+.
- Se algum trecho tiver score 60 ou mais, retorne clip_ready.
- Não espere score 90. Score 90+ é raro; score 60-69 já pode ser um corte simples, de contexto, gancho ou história.
- Não seja rígido demais: corte bom para rede social nem sempre tem conclusão teológica completa; pode ser uma abertura curiosa, uma ilustração, uma história, uma pergunta ou o começo de um assunto interessante.

Critérios para aceitar score 60+:
- Faz sentido sozinho para quem não viu o vídeo completo OU apresenta claramente um assunto/história.
- Tem começo compreensível e uma ideia central clara.
- Pode virar post por curiosidade, identificação, humor, ensino, exemplo, história, autoridade, emoção ou gancho.
- Exemplo válido: uma fala sobre pessoas persistentes, negociação, barganha, 25 de Março, ou uma ilustração cotidiana que prepara uma mensagem. Isso deve virar corte 60-75, mesmo antes da aplicação final.

Critérios para NÃO cortar:
- Só boas-vindas, repetição de capítulo/versículo, microfrase solta ou ruído de transcrição.
- Trecho confuso sem assunto claro.
- Continuação que começa no meio de uma ideia sem contexto.

Regras de duração:
- Prefira cortes de 20 a 60 segundos.
- Pode sugerir até 75 segundos se for o mesmo assunto.
- Se tiver uma janela de 30-60s com ideia clara e score 60+, retorne clip_ready.
- Use wait_more apenas quando NÃO existir nenhum trecho aproveitável com score 60+.

Escala de score:
- 60-69: corte aproveitável/simples, bom gancho, contexto ou história.
- 70-79: bom corte para post.
- 80-89: corte forte.
- 90-95: corte excepcional.

Responda APENAS em JSON válido, sem markdown.

Formatos aceitos:
1) Sem corte aproveitável:
{"status":"ignore","reason":"trecho sem assunto claro ou só boas-vindas/repetição","cortes":[]}

2) Possível corte, mas ainda incompleto e abaixo de 60:
{"status":"wait_more","reason":"tema começou, mas ainda não existe corte aproveitável 60+","topic":"tema detectado","suggested_wait_seconds":30,"cortes":[]}

3) Corte pronto:
{"status":"clip_ready","cortes":[{"trecho":"trecho exato completo","score":60,"titulo":"título curto","razao":"por que esse trecho já serve para post","emocao":"emoção","funcao":"gancho|aplicacao|virada|climax|historia|ensino|contexto","inicio_relativo":0,"fim_relativo":60,"mesmo_assunto":true,"frases_de_impacto":["frase forte do trecho"],"versiculos":["Lucas 18"]}]}

4) Deve juntar com trecho anterior:
{"status":"merge_previous","cortes":[{"trecho":"trecho completo juntando o assunto","score":60,"titulo":"título curto","razao":"motivo","inicio_relativo":0,"fim_relativo":75,"mesmo_assunto":true,"frases_de_impacto":["frase forte do trecho"],"versiculos":["referência bíblica citada, se houver"]}]}

Sempre que possível, preencha:
- frases_de_impacto: 1 a 5 frases fortes, compartilháveis ou chamativas dentro do próprio corte.
- versiculos: referências bíblicas citadas ou claramente usadas no trecho, como "Lucas 18", "João 3:16", "Salmo 23". Se não houver, use lista vazia.
"""

def _extrair_json_obj(txt):
    bruto = str(txt or "").strip()
    if not bruto:
        return {}
    bruto = re.sub(r"^```(?:json)?\s*", "", bruto, flags=re.I).strip()
    bruto = re.sub(r"\s*```$", "", bruto).strip()
    try:
        return json.loads(bruto)
    except Exception:
        m = re.search(r"\{.*\}", bruto, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
    return {}

def analisar_com_gemini(texto, t_ref=0, t_fim=None):
    """Gemini API Free como cérebro de cortes: analisa contexto acumulado e sugere cortes virais.
    Não transcreve áudio. Só avalia texto já transcrito, para economizar cota/créditos.
    """
    if requests is None:
        return None
    if not bool(config_usuario.get("gemini_enabled", CONFIG.get("gemini_enabled", False))):
        return None
    chave = str(config_usuario.get("gemini_api_key", CONFIG.get("gemini_api_key", "")) or "").strip()
    if not chave:
        return None
    texto = limpar_texto_transcricao(texto)
    if len(texto) < int(config_usuario.get("gemini_min_chars", CONFIG.get("gemini_min_chars", 1200))):
        return []
    modelo = str(config_usuario.get("gemini_model", CONFIG.get("gemini_model", "gemini-2.5-flash-lite"))).strip() or "gemini-2.5-flash-lite"
    max_chars = int(config_usuario.get("gemini_max_chars", CONFIG.get("gemini_max_chars", 9000)) or 9000)
    timeout = float(config_usuario.get("gemini_timeout_seg", CONFIG.get("gemini_timeout_seg", 35.0)))
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={chave}"
    tipo_conteudo = tipo_conteudo_atual(texto)
    limiar_atual = current_limiar()
    instrucoes_rodada = (
        f"\n\nLIMIAR DESTA RODADA: score {limiar_atual}+. "
        f"Qualquer corte com score >= {limiar_atual} deve ser retornado como clip_ready. "
        "Não responda wait_more se já existir um gancho, história, exemplo ou assunto aproveitável para post."
    )
    payload = {
        "contents": [{"role":"user", "parts":[{"text": prompt_global_cortes() + "\n\n" + PROMPT_GEMINI_CORTE + instrucoes_rodada + "\n\nTipo provável: " + tipo_conteudo + "\nIdioma/perfil: " + perfil_id_atual() + " / saída: " + ai_language_atual() + "\nJanela: " + fmt(t_ref) + " até " + fmt(t_fim or t_ref) + "\n\nTRANSCRIÇÃO:\n" + texto[-max_chars:]}]}],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.85,
            "maxOutputTokens": 1100,
            "responseMimeType": "application/json"
        }
    }
    try:
        r = requests.post(url, headers={"Content-Type":"application/json"}, json=payload, timeout=timeout)
        if r.status_code in (400,401,403):
            print(f"[gemini] chave/conta recusada ({r.status_code}). Confira a chave no painel.")
            return None
        if r.status_code == 429:
            print("[gemini] limite da chave atingido. Usando detector local nesta rodada.")
            return None
        r.raise_for_status()
        data = r.json()
        text_out = ""
        try:
            cand = data.get("candidates", [])[0]
            parts = cand.get("content", {}).get("parts", [])
            text_out = "\n".join(str(x.get("text", "")) for x in parts if x.get("text"))
        except Exception:
            text_out = ""
        obj = _extrair_json_obj(text_out)
        status = str(obj.get("status", "") if isinstance(obj, dict) else "").strip().lower()
        cortes = obj.get("cortes", []) if isinstance(obj, dict) else []
        # Alguns modelos respondem wait_more, mas ainda devolvem um corte 60+.
        # Na v81e-score60, se veio corte com rating suficiente, processamos mesmo assim.
        if status in ("ignore", "wait_more") and not cortes:
            if status == "wait_more":
                print(f"[gemini] aguardando mais contexto: {obj.get('reason') or obj.get('razao') or obj.get('topic') or ''}")
            return []
        if not cortes and status in ("clip_ready", "merge_previous") and isinstance(obj, dict):
            cortes = [obj]
        norm = []
        for c in cortes[:2]:
            try:
                score = int(float(c.get("score", 0)))
            except Exception:
                score = 0
            # Gemini só reforça corte bom. Não deixa score inflado virar 100 fácil.
            if score >= 98:
                score = 95
            if score < 60:
                continue
            trecho = str(c.get("trecho") or "").strip()
            if len(trecho) < 30:
                continue
            ts = c.get("inicio_relativo", c.get("inicio", c.get("tempo", 0)))
            try: ts = float(ts)
            except Exception: ts = 0.0
            if ts < 120:
                ts = float(t_ref or 0) + ts
            norm.append({
                "trecho": trecho,
                "score": score,
                "titulo": str(c.get("titulo") or titulo_local(trecho, c.get("emocao","fé"), c.get("funcao","impacto"))).strip(),
                "razao": str(c.get("razao") or "Gemini analisou contexto e potencial viral.").strip(),
                "emocao": str(c.get("emocao") or "fé").strip(),
                "funcao": str(c.get("funcao") or "impacto").strip(),
                "tempo": ts,
                "frases_de_impacto": c.get("frases_de_impacto") or c.get("frases_impacto") or c.get("frase_impacto") or c.get("impact_phrases") or [],
                "versiculos": c.get("versiculos") or c.get("versiculos_biblicos") or c.get("referencias_biblicas") or c.get("bible_verses") or [],
            })
        if norm:
            print(f"[gemini] {len(norm)} candidato(s) forte(s) encontrados.")
        return norm
    except Exception as e:
        if not globals().get('_avisou_gemini_falha', False):
            globals()['_avisou_gemini_falha'] = True
            print(f"[gemini] indisponível. Usando detector local: {e}")
        return None


def analisar_com_vps(texto, t_ref=0, t_fim=None):
    """Usa a IA local da VPS via /analyze-text para sugerir cortes.
    Retorna lista de cortes normalizada ou None quando falhar.
    """
    if requests is None:
        return None
    if not config_usuario.get('vps_analisar_com_ia_local', CONFIG.get('vps_analisar_com_ia_local', True)):
        return None
    texto = limpar_texto_transcricao(texto)
    min_chars = int(config_usuario.get('vps_analyze_min_chars', CONFIG.get('vps_analyze_min_chars', 220)))
    if len(texto) < min_chars:
        return []
    timeout = float(config_usuario.get('vps_analyze_timeout_seg', CONFIG.get('vps_analyze_timeout_seg', 60)))

    # Endpoint futuro recomendado no README. Mantido desligado por padrão.
    if config_usuario.get('vps_tentar_analyze_live_chunk', CONFIG.get('vps_tentar_analyze_live_chunk', False)):
        try:
            ep_live = config_usuario.get('vps_analyze_live_endpoint', CONFIG.get('vps_analyze_live_endpoint', '/analyze-live-chunk'))
            tipo_conteudo = tipo_conteudo_atual(texto)
            payload = {"start_time": float(t_ref or 0), "end_time": float(t_fim or t_ref or 0), "text": texto, "content_type": tipo_conteudo}
            r = requests.post(_vps_url(ep_live), headers={**_vps_headers(True), 'Content-Type':'application/json'}, json=payload, timeout=timeout)
            if r.status_code != 404:
                r.raise_for_status()
                return _normalizar_cortes_vps(r.json(), t_ref, texto)
        except Exception as e:
            print(f"[vps-ia] analyze-live-chunk falhou, usando analyze-text: {e}")

    try:
        ep = config_usuario.get('whisper_vps_analyze_endpoint', CONFIG.get('whisper_vps_analyze_endpoint', '/analyze-text'))
        tipo_conteudo = tipo_conteudo_atual(texto)
        if tipo_conteudo == "musica":
            usar_letra_online = bool(config_usuario.get("musica_usar_letra_online", CONFIG.get("musica_usar_letra_online", True)))
            contexto_ia = "culto cristao brasileiro; trecho identificado como musica/louvor; priorizar refrao, ponte, climax emocional, partes bonitas e frases cantaveis; nao exigir aplicacao de pregacao"
            if usar_letra_online:
                contexto_ia += "; Ollama/VPS tem acesso a internet: pode buscar letra semelhante online para entender o que esta sendo cantado, mas a internet apenas sugere; o audio/transcricao manda"
            regras_ia = {
                "content_type": "musica",
                "prefer_chorus": True,
                "prefer_bridge": True,
                "prefer_emotional_peak": True,
                "min_score_for_cut": 80,
                "strong_cut_score": 90,
                "allow_web_search": usar_letra_online,
                "internet_connected": bool(config_usuario.get("ollama_internet_conectado", CONFIG.get("ollama_internet_conectado", True))),
                "lyrics_reference_online": usar_letra_online,
                "lyrics_reference_policy": "internet_sugere_audio_manda",
                "do_not_replace_if_low_confidence": True,
                "minimum_lyrics_confidence": float(config_usuario.get("musica_confianca_minima_letra", CONFIG.get("musica_confianca_minima_letra", 0.82))),
                "preserve_spontaneous_worship": True,
                "do_not_invent_lyrics": True,
                "do_not_output_audio_labels": True
            }
        else:
            contexto_ia = "pregacao crista brasileira; priorizar palavra direcionada, aplicacao e contexto fechado; nao sugerir corte que termine no meio de historia ou frase"
            regras_ia = {"content_type": "pregacao", "avoid_unfinished_story": True, "prefer_direct_word": True, "min_score_for_cut": 80, "strong_cut_score": 90}
        payload = {"text": texto, "start_time": float(t_ref or 0), "end_time": float(t_fim or t_ref or 0),
                   "content_type": tipo_conteudo, "context": contexto_ia, "rules": regras_ia}
        if tipo_conteudo == "musica":
            payload.update({
                "mode": "music_lyrics_refinement",
                "allow_web_search": bool(config_usuario.get("musica_usar_letra_online", CONFIG.get("musica_usar_letra_online", True))),
                "internet_connected": bool(config_usuario.get("ollama_internet_conectado", CONFIG.get("ollama_internet_conectado", True))),
                "lyrics_reference_source": config_usuario.get("lyrics_reference_source", CONFIG.get("lyrics_reference_source", "web_via_ollama_vps")),
                "lyrics_reference_policy": "internet_sugere_audio_manda",
                "minimum_lyrics_confidence": float(config_usuario.get("musica_confianca_minima_letra", CONFIG.get("musica_confianca_minima_letra", 0.82))),
                "preserve_spontaneous_worship": True,
                "instructions": [
                    "Procure letra online apenas como referencia quando o trecho parecer musica/louvor.",
                    "Nao substitua a legenda se a confianca for baixa.",
                    "Nao copie letra inteira; use apenas para corrigir palavras provaveis do trecho cantado.",
                    "Se for espontaneo ou improvisado, preserve o que foi ouvido.",
                    "Nunca escreva marcadores como Musica, Louvor ou Instrumental no SRT."
                ]
            })
        r = requests.post(_vps_url(ep), headers={**_vps_headers(True), 'Content-Type':'application/json'}, json=payload, timeout=timeout)
        if r.status_code == 404:
            # Nem toda VPS tem /analyze-text ainda. Nao deixar isso poluir o terminal
            # nem parecer erro para o usuario: cai no detector local automaticamente.
            if not globals().get('_avisou_analyze_404', False):
                globals()['_avisou_analyze_404'] = True
                print("[vps-ia] /analyze-text nao existe nesta VPS. Usando detector local de cortes sem IA da VPS.")
            return None
        r.raise_for_status()
        return _normalizar_cortes_vps(r.json(), t_ref, texto)
    except Exception as e:
        if not globals().get('_avisou_analyze_falha', False):
            globals()['_avisou_analyze_falha'] = True
            print(f"[vps-ia] indisponivel. Usando detector local de cortes: {e}")
        return None



def modelo_mlx_atual():
    perfil = str(config_usuario.get("whisper_local_perfil", CONFIG.get("whisper_local_perfil", "leve"))).lower().strip()
    if perfil == "pro":
        return config_usuario.get("whisper_local_modelo_pro", CONFIG.get("whisper_local_modelo_pro", "mlx-community/whisper-large-v3"))
    return config_usuario.get("whisper_local_modelo_leve", CONFIG.get("whisper_local_modelo_leve", "mlx-community/whisper-large-v3-turbo"))

class SegmentoASR:
    def __init__(self, start, end, text):
        self.start = float(start or 0)
        self.end = float(end or 0)
        self.text = text or ""

def prompt_transcricao_atual():
    """Prompt mínimo para o ASR conforme o idioma escolhido no Modo Global.
    Não usamos modo automático: o painel define o perfil de idioma.
    Prompts longos podem vazar para a legenda, então o prompt é curto.
    """
    tipo = str(config_usuario.get("tipo_conteudo", CONFIG.get("tipo_conteudo", "pregacao"))).lower()
    perfil = perfil_idioma_atual()
    lang = ai_language_atual()
    if tipo == "musica":
        return None
    return f"{lang}. Christian sermon. Bible references. Pastor speaking."


def limpar_tags_asr(txt):
    """Remove tags internas de ASR antigo que não podem aparecer em legenda."""
    t = str(txt or "")
    # Formatos reais: <|en|>, < | en | >, <|EMO_UNKNOWN|>, < | S pe ech | > etc.
    t = re.sub(r"<\s*\|[^>]{0,80}\|\s*>", " ", t)
    t = re.sub(r"<\s*\|?\s*(?:en|zh|ja|ko|yue|pt|EMO[_\s-]*UNKNOWN|Speech|S\s*pe\s*ech|withitn|withi\s*tn)\s*\|?\s*>", " ", t, flags=re.I)
    t = re.sub(r"\b(?:EMO\s*_\s*UNKNOWN|S\s*pe\s*ech|withi\s*tn|Speech)\b", " ", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()

def detectar_idioma_linha_simples(txt):
    """Detector leve EN/PT-BR para culto traduzido. Não substitui Whisper; só evita descartar inglês válido."""
    low = str(txt or "").lower()
    tokens = re.findall(r"[a-zA-ZÀ-ÿ]+", low)
    if not tokens:
        return "unknown", 0
    pt_words = set("que de do da dos das não nao você voce pra para com uma um ele ela deus senhor jesus gente agora aqui ali porque então entao família familia igreja vida hoje quando meu minha nosso nossa esta está ser ter foi vai se eu nos nós o a os as em no na por mais como".split())
    en_words = set("the and but with within now home give simple day their father child children table presence god lord jesus you your he she will if are is was be see who what where when remain anointed holy glory come receive seat seated high place spirit".split())
    pt = sum(1 for t in tokens if _norm(t) in pt_words)
    en = sum(1 for t in tokens if t in en_words)
    tem_pt_acento = bool(re.search(r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]", str(txt or "")))
    if tem_pt_acento:
        pt += 1
    if en >= max(2, pt + 1):
        return "en", en
    if pt >= max(2, en):
        return "pt", pt
    return "unknown", max(pt, en)

def contexto_bilingue_ativo(linhas_ref=None, texto_atual=""):
    """Ativa quando há alternância EN/PT ou quando o usuário escolhe Pregação traduzida."""
    modo = clip_mode_atual()
    conf = bilingual_context_atual()
    if conf == "off":
        return False
    if conf == "on" or modo == "bilingual_sermon":
        return True
    if modo not in ("mixed", "sermon", "bilingual_sermon"):
        return False
    pares = list(linhas_ref or [])[-10:]
    langs = []
    for _, tx in pares:
        lang, score = detectar_idioma_linha_simples(tx)
        if score >= 2 and lang in ("en", "pt"):
            langs.append(lang)
    if texto_atual:
        lang, score = detectar_idioma_linha_simples(texto_atual)
        if score >= 2 and lang in ("en", "pt"):
            langs.append(lang)
    return ("en" in langs and "pt" in langs)

def ajustar_intervalo_por_culto_inteligente(intervalo_base, feats_audio=None):
    """Mantém análise leve sempre e só intensifica louvor quando realmente parece louvor."""
    try:
        if not bool(config_usuario.get("smart_cult_service_mode", CONFIG.get("smart_cult_service_mode", True))):
            return intervalo_base
        wi = worship_intelligence_atual()
        if wi == "off":
            return intervalo_base
        momento = manual_moment_atual()
        kind = (feats_audio or {}).get("kind")
        if momento == "worship" or wi == "always":
            return max(10.0, min(float(intervalo_base), 15.0))
        if wi == "auto" and kind in ("music", "speech_with_music") and float((feats_audio or {}).get("music_score", 0) or 0) >= 65:
            return max(12.0, min(float(intervalo_base), 18.0))
        return intervalo_base
    except Exception:
        return intervalo_base

def worship_advanced_enabled(feats_audio=None):
    """Camada avançada opcional. Se faltar librosa/scipy, não quebra."""
    if worship_intelligence_atual() == "off":
        return False
    if performance_mode_atual() == "light":
        return False
    if worship_intelligence_atual() == "always" or manual_moment_atual() == "worship":
        return bool(FZ_LIBROSA_OK or FZ_SCIPY_OK)
    if (feats_audio or {}).get("kind") in ("music", "speech_with_music") and float((feats_audio or {}).get("music_score", 0) or 0) >= 65:
        return bool(FZ_LIBROSA_OK or FZ_SCIPY_OK)
    return False

def audio_features_musicais_avancadas(audio, sr=16000):
    """Análise opcional de melodia/energia. Roda em baixa frequência e nunca bloqueia o Core."""
    out = {"advanced": False, "melody_score": 0, "crescendo_score": 0, "tempo_score": 0}
    try:
        a = np.asarray(audio, dtype=np.float32).flatten()
        if len(a) < sr:
            return out
        if FZ_LIBROSA_OK and _fz_librosa is not None:
            y = a
            # Reduz custo: trabalha no sample rate já baixo do FrameZero.
            rms = _fz_librosa.feature.rms(y=y, frame_length=1024, hop_length=512)[0]
            if len(rms) > 3:
                crescendo = float(max(0.0, rms[-1] - np.median(rms)) / max(1e-4, np.median(rms)))
                out["crescendo_score"] = int(max(0, min(100, crescendo * 45)))
            zcr = _fz_librosa.feature.zero_crossing_rate(y, frame_length=1024, hop_length=512)[0]
            out["melody_score"] = int(max(0, min(100, (1.0 - float(np.median(zcr))) * 80)))
            out["advanced"] = True
        elif FZ_SCIPY_OK and _fz_scipy_signal is not None:
            # Fallback leve com scipy: envelope + variação espectral simples.
            env = np.abs(_fz_scipy_signal.hilbert(a))
            if len(env) > 10:
                out["crescendo_score"] = int(max(0, min(100, (float(np.percentile(env, 90)) / max(1e-4, float(np.median(env)))) * 18)))
            out["advanced"] = True
        return out
    except Exception as e:
        out["error"] = str(e)
        return out

def texto_whisper_invalido(txt, origem="local"):
    """Bloqueia lixo de ASR antes de virar SRT/corte.

    MLX Whisper local em chunks curtos pode alucinar inglês, japonês/chinês
    ou palavras quebradas como "N oji io C to". Em PT-BR isso nunca deve virar
    legenda nem acionar corte.
    """
    raw = str(txt or "")
    if not raw.strip():
        return True

    # Tags internas de ASR antigo ou pedaços delas.
    if re.search(r"<\s*\|", raw) or re.search(r"EMO\s*_\s*UNKNOWN|S\s*pe\s*ech|withi\s*tn|Speech", raw, re.I):
        return True

    # Caracteres CJK/Japonês/Koreano quase sempre são alucinação neste fluxo PT-BR.
    if re.search(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]", raw):
        return True

    limpo = limpar_tags_asr(raw).strip()
    if len(limpo) < 3:
        return True

    # Regras anti-lixo muito agressivas foram criadas para PT-BR.
    # No Modo Global, para idiomas diferentes de português, mantemos apenas os bloqueios universais
    # acima (tags internas, CJK indevido, texto vazio) para não descartar inglês/espanhol/etc.
    if whisper_language_atual() not in ("pt", "pt-BR", "pt-PT"):
        return False

    # v1.0.103: em culto traduzido, inglês curto pode ser a fala original do pregador.
    # Não descartar automaticamente EN quando o modo bilingue está ativo/automático.
    try:
        lang_detectado, lang_score = detectar_idioma_linha_simples(limpo)
        if lang_detectado == "en" and lang_score >= 2 and bilingual_context_atual() != "off" and clip_mode_atual() in ("mixed", "sermon", "bilingual_sermon"):
            return False
    except Exception:
        pass

    low = limpo.lower()
    norm_low = _norm(limpo)

    # Se o ASR repetir instrução/prompt do sistema, descarta.
    if ("o audio e de uma pregacao" in norm_low or
        "culto podcast ou aula biblica" in norm_low or
        "transcricao fiel em portugues brasileiro" in norm_low or
        "nao invente palavras" in norm_low or
        "nao traduza" in norm_low):
        return True

    # Padrões reais vistos no Mac: letras soltas e sílabas sem sentido.
    if re.search(r"\b[a-z]\s+[a-z]{1,4}\s+[a-z]{1,4}\s+[a-z]\s+[a-z]{1,4}\b", low, re.I):
        return True

    tokens = re.findall(r"[A-Za-zÀ-ÿ]+", limpo)
    if tokens:
        single = [w for w in tokens if len(w) == 1]
        short = [w for w in tokens if len(w) <= 3]
        long_words = [w for w in tokens if len(w) >= 11]

        # Ex.: "N oji io C to", "C ont do H esh pe".
        if len(tokens) <= 8 and (len(single) >= 2 or len(short) >= max(3, len(tokens)-1)):
            return True

        portugues_sinais = re.findall(r"\b(que|de|do|da|dos|das|não|nao|você|voce|pra|para|com|uma|um|ele|ela|deus|senhor|jesus|gente|agora|aqui|ali|porque|então|entao|família|familia|igreja|vida|hoje|quando|meu|minha|nosso|nossa)\b", low)
        ingles_sinais = re.findall(r"\b(the|and|but|with|within|now|home|give|failed|simple|day|their|shot|speech|recommendations|recommendation|philosophy|philosophysopher|cont|esh|inch|gsc)\b", low)
        lixo_sinais = re.findall(r"\b(oji|philosophysopher|recommendations|gsc|inch|esh|withitn|spech|hesh|tepi)\b", low)

        if lixo_sinais:
            return True
        if len(ingles_sinais) >= 1 and len(portugues_sinais) == 0 and len(tokens) <= 10:
            if not (bilingual_context_atual() != "off" and clip_mode_atual() in ("mixed", "sermon", "bilingual_sermon")):
                return True
        if long_words and len(portugues_sinais) == 0 and len(tokens) <= 6:
            return True

        # Texto quase todo ASCII/inglês sem nenhuma palavra portuguesa comum em PT-BR.
        tem_acento = bool(re.search(r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]", limpo))
        if not tem_acento and len(portugues_sinais) == 0 and len(tokens) <= 7:
            # Bloqueia frases curtas sem cara de português.
            vogais_pt = sum(1 for c in low if c in "aeiouáàâãéêíóôõú")
            if len(tokens) >= 2 and vogais_pt <= max(2, len("".join(tokens)) * 0.35):
                return True

    # Repetição curta sem sentido.
    if re.fullmatch(r"(?:[A-Za-z]{1,4}\s*){1,8}[.,!?]?", limpo) and len(limpo.split()) <= 8:
        return True
    return False

def _wav_temp_from_audio(audio):
    audio = preparar_audio_whisper(audio).astype(np.float32)
    wav_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    pcm = np.clip(audio, -1.0, 1.0)
    pcm16 = (pcm * 32767.0).astype(np.int16)
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(CONFIG.get("sample_rate", 16000)))
        wf.writeframes(pcm16.tobytes())
    return wav_path, audio

def _transcrever_faster(modelo, audio):
    if not TEM_FASTER_WHISPER or WhisperModel is None:
        raise RuntimeError("faster-whisper não instalado no Windows.")
    audio = preparar_audio_whisper(audio).astype(np.float32)
    idioma = whisper_language_atual()
    model_name = "small"
    if isinstance(modelo, dict):
        model_name = modelo.get("modelo") or modelo.get("model") or model_name
    # Cache simples do modelo para evitar recarregar a cada bloco.
    global _FASTER_MODEL_CACHE
    try:
        cache = _FASTER_MODEL_CACHE
    except NameError:
        cache = _FASTER_MODEL_CACHE = {}
    key = str(model_name)
    if key not in cache:
        print(f"[faster-whisper] carregando modelo={model_name} device=cpu compute=int8")
        cache[key] = WhisperModel(model_name, device="cpu", compute_type="int8")
    wav_path, _ = _wav_temp_from_audio(audio)
    try:
        segments, info = cache[key].transcribe(
            wav_path,
            language=idioma,
            task="transcribe",
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
            word_timestamps=False,
        )
        textos=[]
        segs_lista=[]
        for sg in segments:
            txt=(getattr(sg,"text","") or "").strip()
            if txt:
                textos.append(txt)
                segs_lista.append(SegmentoASR(float(getattr(sg,"start",0) or 0), float(getattr(sg,"end",0) or 0), txt))
        texto=limpar_texto_transcricao(limpar_tags_asr(" ".join(textos).strip()))
        if texto_whisper_invalido(texto, origem="faster-local"):
            raise RuntimeError("faster-whisper retornou texto invalido; bloqueado para nao gerar SRT/corte errado.")
        return texto, segs_lista
    finally:
        try:
            os.remove(wav_path)
        except Exception:
            pass

def transcrever_local(modelo, audio):
    """Transcrição local: MLX no Mac Apple Silicon; Faster-Whisper no Windows."""
    if isinstance(modelo, dict) and str(modelo.get("engine","")).lower().startswith("faster"):
        return _transcrever_faster(modelo, audio)
    if (platform.system().lower().startswith("win") or not TEM_MLX) and TEM_FASTER_WHISPER:
        return _transcrever_faster(modelo, audio)
    if not TEM_MLX or mlx_whisper is None:
        raise RuntimeError("Nenhum motor local disponível. No Windows use faster-whisper; no Mac Apple Silicon use mlx-whisper.")

    audio = preparar_audio_whisper(audio).astype(np.float32)
    idioma = whisper_language_atual()
    modelo_nome = modelo_mlx_atual()

    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=modelo_nome,
        language=idioma,
        task="transcribe",
        condition_on_previous_text=False,
        initial_prompt=None,
        word_timestamps=False,
        verbose=False,
    )

    segmentos_raw = result.get("segments") or [] if isinstance(result, dict) else []
    segs_lista = []
    textos = []
    for sg in segmentos_raw:
        if isinstance(sg, dict):
            txt = (sg.get("text") or sg.get("texto") or "").strip()
            st = sg.get("start", sg.get("inicio", 0))
            en = sg.get("end", sg.get("fim", 0))
        else:
            txt = (getattr(sg, "text", "") or "").strip()
            st = getattr(sg, "start", 0)
            en = getattr(sg, "end", 0)
        if txt:
            textos.append(txt)
            segs_lista.append(SegmentoASR(st, en, txt))

    texto = " ".join(textos).strip()
    if not texto and isinstance(result, dict):
        texto = (result.get("text") or result.get("transcription") or "").strip()
        if texto:
            dur = float(len(audio) / max(1, CONFIG.get("sample_rate", 16000)))
            segs_lista = [SegmentoASR(0, dur, texto)]

    texto = limpar_texto_transcricao(limpar_tags_asr(texto))
    if texto_whisper_invalido(texto, origem="mlx-local"):
        raise RuntimeError("MLX Whisper retornou texto invalido; bloqueado para nao gerar SRT/corte errado.")
    return texto, segs_lista


def _resample_linear(audio, src_rate=16000, dst_rate=24000):
    audio = np.asarray(audio, dtype=np.float32).flatten()
    if src_rate == dst_rate:
        return audio
    if len(audio) < 2:
        return audio
    dur = len(audio) / float(src_rate)
    x_old = np.linspace(0, dur, num=len(audio), endpoint=False)
    x_new = np.linspace(0, dur, num=max(1, int(dur * dst_rate)), endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def _pcm16_b64(audio_float):
    audio_float = np.clip(np.asarray(audio_float, dtype=np.float32).flatten(), -1.0, 1.0)
    pcm = (audio_float * 32767.0).astype(np.int16).tobytes()
    return base64.b64encode(pcm).decode("ascii")


async def _openai_realtime_transcribe_async(audio, timeout_seg=45):
    chave = (config_usuario.get("openai_api_key") or config_usuario.get("openai_key") or "").strip()
    if not chave:
        raise RuntimeError("Modo Turbo precisa da chave OpenAI nas configuracoes.")
    modelo = str(config_usuario.get("openai_realtime_model", CONFIG.get("openai_realtime_model", "gpt-realtime-whisper")))
    delay = str(config_usuario.get("openai_realtime_delay", CONFIG.get("openai_realtime_delay", "high"))).lower().strip()
    if delay not in ("minimal", "low", "medium", "high", "xhigh"):
        delay = "high"

    audio24 = _resample_linear(preparar_audio_whisper(audio), CONFIG.get("sample_rate", 16000), 24000)
    audio_b64 = _pcm16_b64(audio24)
    url = f"wss://api.openai.com/v1/realtime?model={modelo}"
    headers = {
        "Authorization": f"Bearer {chave}",
        "OpenAI-Beta": "realtime=v1",
    }

    async def _connect():
        try:
            return await websockets.connect(url, additional_headers=headers, max_size=20_000_000)
        except TypeError:
            return await websockets.connect(url, extra_headers=headers, max_size=20_000_000)

    async with await _connect() as ws_openai:
        await ws_openai.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "transcription": {
                            "model": modelo,
                            "language": whisper_language_atual(),
                            "delay": delay,
                        },
                        "turn_detection": None,
                    }
                }
            }
        }))
        await ws_openai.send(json.dumps({"type": "input_audio_buffer.append", "audio": audio_b64}))
        await ws_openai.send(json.dumps({"type": "input_audio_buffer.commit"}))

        partes = []
        final = ""
        fim = time.time() + timeout_seg
        while time.time() < fim:
            try:
                msg = await asyncio.wait_for(ws_openai.recv(), timeout=5)
            except asyncio.TimeoutError:
                continue
            ev = json.loads(msg)
            tipo = ev.get("type", "")
            if tipo == "conversation.item.input_audio_transcription.delta":
                delta = ev.get("delta") or ""
                if delta:
                    partes.append(delta)
            elif tipo == "conversation.item.input_audio_transcription.completed":
                final = (ev.get("transcript") or "").strip()
                break
            elif tipo == "error":
                erro = ev.get("error") or ev
                raise RuntimeError(f"OpenAI Realtime erro: {erro}")
        texto = final or "".join(partes).strip()
        return texto


def transcrever_openai_realtime(audio):
    """Modo Turbo: usa OpenAI Realtime Transcription com chave do usuario.
    A chamada e por chunk para manter compatibilidade com o pipeline atual de cortes.
    """
    texto = asyncio.run(_openai_realtime_transcribe_async(audio))
    texto = limpar_texto_transcricao(limpar_tags_asr(texto))
    if texto_whisper_invalido(texto, origem="openai-turbo"):
        raise RuntimeError("OpenAI Realtime retornou texto invalido/vazio")
    dur = float(len(audio) / max(1, CONFIG.get("sample_rate", 16000)))
    return texto, [SegmentoASR(0, dur, texto)]

def traduzir_texto_ao_vivo(texto):
    """AI Boost opcional: traduz uma linha ao vivo usando Gemini ou OpenAI.
    Desligado por padrão para manter o FrameZero leve.
    """
    texto = str(texto or "").strip()
    if not texto or not live_translation_ativa():
        return ""
    alvo = str(config_usuario.get("live_translation_target", CONFIG.get("live_translation_target", "en")) or "en")
    prov = str(config_usuario.get("live_translation_provider", CONFIG.get("live_translation_provider", "gemini"))).lower().strip()
    try:
        if prov == "openai":
            cl = cliente_openai()
            if cl is None:
                return ""
            r = cl.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":f"Translate the text to {alvo}. Keep it natural for sermon captions. Return only the translation."},
                          {"role":"user","content":texto}],
                temperature=0.1,
            )
            return (r.choices[0].message.content or "").strip()
        # Gemini
        if requests is None:
            return ""
        chave = str(config_usuario.get("gemini_api_key", CONFIG.get("gemini_api_key", "")) or "").strip()
        if not chave:
            return ""
        modelo = str(config_usuario.get("gemini_model", CONFIG.get("gemini_model", "gemini-2.5-flash-lite"))).strip() or "gemini-2.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={chave}"
        payload = {"contents":[{"role":"user", "parts":[{"text": f"Translate this sermon caption line to {alvo}. Return only the translation, no notes.\n\n{texto}"}]}], "generationConfig":{"temperature":0.1,"maxOutputTokens":220}}
        r = requests.post(url, headers={"Content-Type":"application/json"}, json=payload, timeout=12)
        r.raise_for_status()
        data = r.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return " ".join(str(p.get("text", "")) for p in parts if p.get("text")).strip()
    except Exception as e:
        if not globals().get('_avisou_traducao_live_falha', False):
            globals()['_avisou_traducao_live_falha'] = True
            print(f"[global-ai] tradução ao vivo indisponível nesta rodada: {e}")
        return ""

def enviar_audio_status(ok=None, nome=None, rms=None, msg=None, origem=None):
    """Atualiza e envia status de áudio para o painel/Terminal."""
    global audio_status_atual, ultimo_status_audio_envio
    if ok is not None: audio_status_atual["ok"] = bool(ok)
    if nome is not None: audio_status_atual["nome"] = nome
    if rms is not None: audio_status_atual["rms"] = round(float(rms), 5)
    if msg is not None: audio_status_atual["msg"] = msg
    if origem is not None: audio_status_atual["origem"] = origem
    now = time.time()
    # evita flood no websocket
    if now - ultimo_status_audio_envio > 1.5:
        ultimo_status_audio_envio = now
        enviar({"tipo":"audio_status", **audio_status_atual})

def enviar_vps_status(ok=None, msg=None, modo=None, url=None):
    """Atualiza e envia status da VPS atual para o painel/Terminal."""
    global vps_status_atual, ultimo_status_vps_envio
    if ok is not None: vps_status_atual["ok"] = bool(ok)
    if msg is not None: vps_status_atual["msg"] = str(msg)
    if modo is not None: vps_status_atual["modo"] = str(modo)
    if url is not None: vps_status_atual["url"] = str(url)
    now = time.time()
    if now - ultimo_status_vps_envio > 1.0:
        ultimo_status_vps_envio = now
        enviar({"tipo":"vps_status", **vps_status_atual})

def callback_audio(indata, frames, t, status):
    if status: print(f"[audio] {status}")
    try:
        arr = np.asarray(indata, dtype=np.float32)
        if arr.size:
            rms = float(np.sqrt(np.mean(arr * arr)) + 1e-9)
            if rms > 0.0005:
                enviar_audio_status(ok=True, rms=rms, msg="recebendo áudio", origem="dispositivo")
    except Exception:
        pass
    fila_audio.put(indata.copy())

def _audio_device_category(nome, max_in=0, max_out=0, device_id=None):
    nome_l = str(nome or '').lower()
    did_l = str(device_id or '').lower()
    virtual_terms = ('vb-audio', 'vb audio', 'vb-cable', 'vbcable', 'cable input', 'cable output', 'blackhole', 'virtual')
    if any(t in nome_l or t in did_l for t in virtual_terms):
        return 'Dispositivos virtuais'
    if int(max_out or 0) > 0 and int(max_in or 0) <= 0:
        return 'Saídas / Loopback'
    if str(device_id or '').startswith(('loopback:', 'loopback_sc:')):
        return 'Saídas / Loopback'
    return 'Entradas'

def _is_recommended_audio(nome, device_id=None):
    s = (str(nome or '') + ' ' + str(device_id or '')).lower()
    return any(t in s for t in ('vb-audio', 'vb audio', 'vb-cable', 'vbcable', 'cable output', 'blackhole', 'loopback'))

def listar_dispositivos_entrada():
    """Lista fontes de áudio para transcrição.
    Mantém o nome antigo por compatibilidade, mas agora inclui entradas,
    saídas/loopback do Windows e dispositivos virtuais para o painel OBS.
    """
    saida = []
    seen = set()
    sistema = platform.system().lower()
    if sd is not None:
        try:
            devs = sd.query_devices()
            default_in = None
            default_out = None
            try:
                if sd.default.device:
                    default_in = sd.default.device[0]
                    default_out = sd.default.device[1] if len(sd.default.device) > 1 else None
            except Exception:
                pass
            for i, d in enumerate(devs):
                nome = str(d.get('name', f'Dispositivo {i}'))
                max_in = int(d.get('max_input_channels', 0) or 0)
                max_out = int(d.get('max_output_channels', 0) or 0)
                if max_in > 0:
                    cat = _audio_device_category(nome, max_in, max_out, i)
                    item = {
                        'id': i, 'nome': nome, 'name': nome, 'device_id': str(i), 'device_name': nome,
                        'padrao': (i == default_in), 'default': (i == default_in),
                        'channels_in': max_in, 'channels_out': max_out,
                        'category': cat, 'is_input': True, 'is_output': False, 'is_loopback': False,
                        'recommended': _is_recommended_audio(nome, i)
                    }
                    key = ('in', str(i), nome.lower())
                    if key not in seen:
                        saida.append(item); seen.add(key)
                if sistema == 'windows' and max_out > 0:
                    did = f'loopback:{i}'
                    cat = _audio_device_category(nome, max_in, max_out, did)
                    item = {
                        'id': did, 'nome': nome + ' (loopback)', 'name': nome + ' (loopback)',
                        'device_id': did, 'device_name': nome,
                        'padrao': (i == default_out), 'default': (i == default_out),
                        'channels_in': max_in, 'channels_out': max_out,
                        'category': cat, 'is_input': False, 'is_output': True, 'is_loopback': True,
                        'recommended': _is_recommended_audio(nome, did)
                    }
                    key = ('out', str(i), nome.lower())
                    if key not in seen:
                        saida.append(item); seen.add(key)
        except Exception as e:
            print(f'[audio] erro ao listar sounddevice: {e}')
    # Fallback/extra para loopback real via soundcard no Windows.
    if platform.system().lower() == 'windows' and sc is not None:
        try:
            for mic in sc.all_microphones(include_loopback=True):
                nome = str(getattr(mic, 'name', '') or '')
                mid = str(getattr(mic, 'id', '') or nome)
                if not nome:
                    continue
                is_lb = ('loopback' in nome.lower()) or ('loopback' in mid.lower())
                if is_lb or _is_recommended_audio(nome, mid):
                    did = 'loopback_sc:' + mid
                    item = {
                        'id': did, 'nome': nome, 'name': nome, 'device_id': did, 'device_name': nome,
                        'padrao': False, 'default': False, 'channels_in': None, 'channels_out': None,
                        'category': _audio_device_category(nome, 0, 2, did),
                        'is_input': not is_lb, 'is_output': True, 'is_loopback': True,
                        'recommended': _is_recommended_audio(nome, did)
                    }
                    key = ('sc', mid.lower(), nome.lower())
                    if key not in seen:
                        saida.append(item); seen.add(key)
        except Exception as e:
            print(f'[audio] erro ao listar soundcard loopback: {e}')
    return saida

def encontrar_blackhole():
    """Procura BlackHole 2ch no macOS.
    No Windows retorna vazio, porque o fluxo Windows usa dispositivos locais/VB-CABLE.
    """
    if platform.system().lower() != "darwin" or sd is None:
        return None, None
    try:
        devs = sd.query_devices()
        candidatos = []
        for i, d in enumerate(devs):
            nome = str(d.get("name", ""))
            if "blackhole" in nome.lower() and int(d.get("max_input_channels", 0) or 0) > 0:
                candidatos.append((i, nome, int(d.get("max_input_channels", 0) or 0), int(d.get("max_output_channels", 0) or 0)))
        if candidatos:
            candidatos.sort(key=lambda x: ("2ch" not in x[1].lower(), x[0]))
            i, nome, ins, outs = candidatos[0]
            print(f"[audio] BlackHole input encontrado: indice {i} • {nome} • in:{ins} out:{outs}")
            return i, nome
    except Exception as e:
        print(f"[audio] erro procurando BlackHole: {e}")
    return None, None

def blackhole_instalado():
    return bool(encontrar_blackhole()[1]) if platform.system().lower() == "darwin" else False

def encontrar_vbcable_windows():
    """Procura a entrada de captura do VB-Audio/VB-CABLE no Windows.
    O dispositivo que o Core precisa ouvir normalmente aparece como
    CABLE Output, Input (VB-Audio Point) ou algo contendo VB-Audio.
    """
    if platform.system().lower() != "windows" or sd is None:
        return None, None
    try:
        devs = sd.query_devices()
        candidatos = []
        termos_fortes = ("cable output", "vb-audio", "vb audio", "vbcable", "vb-cable", "vb-audio point")
        for i, d in enumerate(devs):
            nome = str(d.get("name", ""))
            nome_l = nome.lower()
            ins = int(d.get("max_input_channels", 0) or 0)
            if ins <= 0:
                continue
            if any(t in nome_l for t in termos_fortes):
                score = 0
                if "cable output" in nome_l: score += 50
                if "vb-audio" in nome_l or "vb audio" in nome_l: score += 30
                if "point" in nome_l: score += 20
                if "input" in nome_l: score += 5
                candidatos.append((score, i, nome))
        if candidatos:
            candidatos.sort(reverse=True)
            _, i, nome = candidatos[0]
            print(f"[audio] VB-CABLE input encontrado: indice {i} • {nome}")
            return i, nome
    except Exception as e:
        print(f"[audio] erro procurando VB-CABLE: {e}")
    return None, None

def _stop_audio_stream_atual():
    global stream_audio, loopback_audio_stop, loopback_audio_thread
    if stream_audio is not None:
        try: stream_audio.stop()
        except Exception: pass
        try: stream_audio.close()
        except Exception: pass
        stream_audio = None
    if loopback_audio_stop is not None:
        try: loopback_audio_stop.set()
        except Exception: pass
    if loopback_audio_thread is not None:
        try: loopback_audio_thread.join(timeout=1.5)
        except Exception: pass
    loopback_audio_thread = None
    loopback_audio_stop = None

def _resolver_dispositivo_por_nome(nome, prefer_output=False):
    if sd is None or not nome:
        return None
    n = str(nome).replace('(loopback)', '').strip().lower()
    try:
        devs = sd.query_devices()
        candidatos = []
        for i, d in enumerate(devs):
            dn = str(d.get('name', '')).strip().lower()
            if not dn:
                continue
            if dn == n or n in dn or dn in n:
                max_in = int(d.get('max_input_channels', 0) or 0)
                max_out = int(d.get('max_output_channels', 0) or 0)
                if prefer_output and max_out > 0:
                    return f'loopback:{i}'
                if not prefer_output and max_in > 0:
                    return i
                candidatos.append((i, max_in, max_out))
        for i, max_in, max_out in candidatos:
            if max_in > 0:
                return i
        for i, max_in, max_out in candidatos:
            if max_out > 0:
                return f'loopback:{i}'
    except Exception:
        pass
    return None

def _normalizar_audio_id(dispositivo, device_name=None, is_output=False, is_loopback=False):
    if dispositivo in (None, '', 'padrao', 'padrão', 'default'):
        return None
    d = str(dispositivo).strip()
    if d.startswith(('loopback:', 'loopback_sc:')):
        return d
    try:
        return int(d)
    except Exception:
        pass
    # IDs hash do navegador não servem para PortAudio. Resolve pelo nome enviado pelo painel/Core.
    resolved = _resolver_dispositivo_por_nome(device_name or d, prefer_output=bool(is_output or is_loopback))
    if resolved is not None:
        return resolved
    # Fallback para VB-CABLE se o painel enviou saída/loopback sem ID reconhecível.
    if platform.system().lower() == 'windows' and (is_output or is_loopback):
        for item in listar_dispositivos_entrada():
            nm = str(item.get('nome') or item.get('name') or '').lower()
            if ('cable output' in nm or 'vb-cable' in nm or 'vb audio' in nm) and item.get('is_input'):
                try: return int(item.get('id'))
                except Exception: return item.get('id')
    return d

def _start_soundcard_loopback(dispositivo, device_name=None):
    global stream_audio, loopback_audio_stop, loopback_audio_thread
    if sc is None:
        return False, 'soundcard indisponivel: ' + str(SOUNDCARD_ERROR)
    ident = str(dispositivo or '')
    alvo = ident.replace('loopback_sc:', '').replace('loopback:', '').strip()
    name_hint = str(device_name or alvo or '').replace('(loopback)', '').strip().lower()
    try:
        mics = sc.all_microphones(include_loopback=True)
        mic = None
        # Primeiro por ID exato vindo do Core.
        for m in mics:
            mid = str(getattr(m, 'id', '') or '')
            mn = str(getattr(m, 'name', '') or '')
            if ident.startswith('loopback_sc:') and mid == alvo:
                mic = m; break
            if name_hint and (name_hint == mn.lower() or name_hint in mn.lower() or mn.lower() in name_hint):
                mic = m; break
        # Depois por índice de saída sounddevice convertido para nome.
        if mic is None and ident.startswith('loopback:') and sd is not None:
            try:
                idx = int(alvo)
                out_name = str(sd.query_devices(idx).get('name', '')).lower()
                for m in mics:
                    mn = str(getattr(m, 'name', '') or '').lower()
                    if out_name and (out_name in mn or mn in out_name or 'loopback' in mn):
                        mic = m; break
            except Exception:
                pass
        if mic is None:
            return False, 'loopback do Windows não encontrado para ' + str(device_name or dispositivo)
        stop = threading.Event()
        loopback_audio_stop = stop
        sample_rate = int(CONFIG.get('sample_rate', 16000))
        canais = 2 if platform.system().lower() == 'windows' else int(CONFIG.get('canais', 1))
        mic_nome_seguro = str(device_name or dispositivo)
        try:
            mic_nome_seguro = str(getattr(mic, 'name', mic_nome_seguro) or mic_nome_seguro)
        except Exception:
            pass
        def _worker():
            com_iniciado = False
            try:
                if platform.system().lower() == 'windows':
                    try:
                        import ctypes
                        ctypes.windll.ole32.CoInitialize(None)
                        com_iniciado = True
                    except Exception:
                        pass
                with mic.recorder(samplerate=sample_rate, channels=canais) as rec:
                    while not stop.is_set():
                        data = rec.record(numframes=max(1024, int(sample_rate * 0.20)))
                        if data is None:
                            continue
                        arr = np.asarray(data, dtype=np.float32)
                        if arr.ndim == 1:
                            arr = arr.reshape(-1, 1)
                        if arr.shape[1] > 1:
                            arr = arr.mean(axis=1, keepdims=True).astype(np.float32)
                        try:
                            rms = float(np.sqrt(np.mean(arr * arr)) + 1e-9)
                            if rms > 0.0005:
                                enviar_audio_status(ok=True, nome=mic_nome_seguro, rms=rms, msg='recebendo áudio do loopback', origem='loopback')
                        except Exception:
                            pass
                        fila_audio.put(arr.copy())
                        try:
                            _fz_nations_audio_hook(arr.copy(), sample_rate)
                        except Exception:
                            pass
            except Exception as e:
                print(f'[audio] loopback soundcard parou: {e}')
                enviar_audio_status(ok=False, nome=mic_nome_seguro, rms=0.0, msg='loopback parou: ' + str(e), origem='loopback')
            finally:
                if com_iniciado:
                    try:
                        import ctypes
                        ctypes.windll.ole32.CoUninitialize()
                    except Exception:
                        pass
        t = threading.Thread(target=_worker, daemon=True)
        loopback_audio_thread = t
        class _LoopbackWrapper:
            def stop(self_inner):
                stop.set()
            def close(self_inner):
                stop.set()
        stream_audio = _LoopbackWrapper()
        t.start()
        nome = str(getattr(mic, 'name', device_name or dispositivo))
        print(f'[audio] capturando loopback Windows de: {nome}')
        enviar_audio_status(ok=True, nome=nome, rms=0.0, msg='loopback conectado; aguardando sinal', origem='loopback')
        return True, nome
    except Exception as e:
        return False, str(e)

def abrir_audio(dispositivo, device_name=None, is_output=False, is_loopback=False):
    """Abre (ou reabre) o stream de captura no dispositivo escolhido.
    No Windows aceita IDs loopback:<id>/loopback_sc:<id> para capturar saídas.
    """
    global stream_audio
    if sd is None and not (platform.system().lower() == 'windows' and sc is not None):
        msg = f"sounddevice/PortAudio indisponivel: {SOUNDDEVICE_ERROR}"
        print(f"[audio] {msg}")
        enviar_audio_status(ok=False, nome="audio local indisponivel", rms=0.0, msg=msg, origem="sem-sounddevice")
        return False, msg
    dispositivo = _normalizar_audio_id(dispositivo, device_name=device_name, is_output=is_output, is_loopback=is_loopback)
    _stop_audio_stream_atual()
    if platform.system().lower() == 'windows' and isinstance(dispositivo, str) and dispositivo.startswith(('loopback:', 'loopback_sc:')):
        ok, nome = _start_soundcard_loopback(dispositivo, device_name=device_name)
        if ok:
            with fila_audio.mutex:
                fila_audio.queue.clear()
            return ok, nome
        print(f'[audio] WASAPI loopback indisponivel: {nome}')
        vb_id, vb_nome = encontrar_vbcable_windows()
        if vb_id is not None:
            print(f'[audio] fallback: usando VB-CABLE como entrada de captura: {vb_nome}')
            try:
                stream_audio = sd.InputStream(
                    samplerate=CONFIG["sample_rate"], channels=CONFIG["canais"],
                    dtype="float32", device=vb_id, callback=callback_audio)
                stream_audio.start()
                with fila_audio.mutex:
                    fila_audio.queue.clear()
                enviar_audio_status(ok=True, nome=vb_nome, rms=0.0, msg='VB-CABLE conectado; aguardando sinal', origem='vbcable')
                return True, vb_nome
            except Exception as e2:
                print(f'[audio] fallback VB-CABLE falhou: {e2}')
        enviar_audio_status(ok=False, nome=str(device_name or dispositivo), rms=0.0, msg='falha ao abrir loopback: ' + str(nome), origem='loopback')
        return False, nome
    try:
        stream_audio = sd.InputStream(
            samplerate=CONFIG["sample_rate"], channels=CONFIG["canais"],
            dtype="float32", device=dispositivo, callback=callback_audio)
        stream_audio.start()
        with fila_audio.mutex:
            fila_audio.queue.clear()
        nome = "padrao do sistema"
        if dispositivo is not None:
            try: nome = sd.query_devices(dispositivo).get("name", str(dispositivo))
            except Exception: nome = str(device_name or dispositivo)
        print(f"[audio] capturando de: {nome}")
        origem = "blackhole" if "blackhole" in str(nome).lower() else ("loopback" if is_output or is_loopback else "dispositivo")
        enviar_audio_status(ok=True, nome=nome, rms=0.0, msg="áudio conectado; aguardando sinal", origem=origem)
        return True, nome
    except Exception as e:
        print(f"[audio] falha ao abrir dispositivo {dispositivo}: {e}")
        enviar_audio_status(ok=False, nome=str(device_name or dispositivo), rms=0.0, msg=f"falha ao abrir áudio: {e}")
        return False, str(e)

def fmt(s):
    h=int(s//3600); m=int((s%3600)//60); x=int(s%60)
    return f"{h:02d}:{m:02d}:{x:02d}"

def fmt_srt(s):
    h=int(s//3600); m=int((s%3600)//60); x=int(s%60); ms=int((s-int(s))*1000)
    return f"{h:02d}:{m:02d}:{x:02d},{ms:03d}"


def _cfg_int(nome, padrao):
    try:
        return int(config_usuario.get(nome, CONFIG.get(nome, padrao)))
    except Exception:
        return padrao

def _cfg_bool(nome, padrao):
    v = config_usuario.get(nome, CONFIG.get(nome, padrao))
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "sim", "yes", "on")

def quebrar_texto_srt_ptbr(texto, limite=None, linha_unica=None):
    """Quebra legenda em português brasileiro para o padrão do projeto.
    Padrão: 37 caracteres e linha única. Se o texto passar disso, vira novos cues,
    não segunda linha dentro do mesmo cue.
    """
    limite = limite or _cfg_int("srt_caracteres_por_linha", 37)
    linha_unica = _cfg_bool("srt_linha_unica", True) if linha_unica is None else linha_unica
    texto = corrigir_legenda_por_contexto(re.sub(r"\s+", " ", str(texto or "")).strip())
    if not texto:
        return []
    palavras = texto.split(" ")
    partes = []
    atual = ""
    for palavra in palavras:
        if not atual:
            if len(palavra) <= limite:
                atual = palavra
            else:
                # palavra muito grande: corta em pedaços para nunca passar do limite
                for i in range(0, len(palavra), limite):
                    pedaco = palavra[i:i+limite]
                    if len(pedaco) == limite:
                        partes.append(pedaco)
                    else:
                        atual = pedaco
        elif len(atual) + 1 + len(palavra) <= limite:
            atual += " " + palavra
        else:
            partes.append(atual)
            if len(palavra) <= limite:
                atual = palavra
            else:
                for i in range(0, len(palavra), limite):
                    pedaco = palavra[i:i+limite]
                    if len(pedaco) == limite:
                        partes.append(pedaco)
                    else:
                        atual = pedaco
    if atual:
        partes.append(atual)
    # linha única: cada item é uma única linha. Se um dia desligar, ainda mantemos seguro.
    if linha_unica:
        return partes
    return partes

def adicionar_cues_srt(out, indice, inicio, fim, texto):
    """Adiciona cues respeitando pt-BR, 37 caracteres e linha única."""
    partes = quebrar_texto_srt_ptbr(texto)
    if not partes:
        return indice
    dur = max(0.7, float(fim) - float(inicio))
    passo = dur / max(1, len(partes))
    for n, parte in enumerate(partes):
        a = float(inicio) + passo * n
        b = float(inicio) + passo * (n + 1)
        if n == len(partes) - 1:
            b = float(fim)
        if b <= a:
            b = a + 0.7
        out += [str(indice), f"{fmt_srt(a)} --> {fmt_srt(b)}", parte, ""]
        indice += 1
    return indice

def fmt_ass(s):
    """Tempo ASS: H:MM:SS.cc"""
    s = max(0.0, float(s or 0))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    x = int(s % 60)
    cs = int(round((s - int(s)) * 100))
    if cs >= 100:
        x += 1
        cs = 0
    return f"{h}:{m:02d}:{x:02d}.{cs:02d}"


def ass_escape(txt):
    txt = re.sub(r"\s+", " ", str(txt or "")).strip()
    return txt.replace("{", "(").replace("}", ")")


def ass_header():
    """Legenda estilizada equivalente ao preset, sem depender do arquivo .preset."""
    font = config_usuario.get("subtitle_font_family", CONFIG.get("subtitle_font_family", "Poppins"))
    size = _cfg_int("subtitle_font_size", 13)
    bold = -1 if _cfg_bool("subtitle_bold", True) else 0
    alignment = _cfg_int("subtitle_alignment", 2)
    primary = config_usuario.get("subtitle_primary_color_ass", CONFIG.get("subtitle_primary_color_ass", "&H00FFFFFF"))
    outline_color = config_usuario.get("subtitle_outline_color_ass", CONFIG.get("subtitle_outline_color_ass", "&H00000000"))
    back = config_usuario.get("subtitle_back_color_ass", CONFIG.get("subtitle_back_color_ass", "&H80000000"))
    outline = _cfg_int("subtitle_outline", 2)
    shadow = _cfg_int("subtitle_shadow", 0)
    return f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: GAB USA Subtitle,{font},{size},{primary},&H000000FF,{outline_color},{back},{bold},0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},80,80,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ass_from_srt(srt_text):
    """Converte o SRT gerado (37 caracteres, linha única) em ASS com estilo Poppins/Bold."""
    events = []
    blocks = re.split(r"\n\s*\n", str(srt_text or "").strip())
    for block in blocks:
        lines_block = [x.strip() for x in block.splitlines() if x.strip()]
        if len(lines_block) < 3:
            continue
        tempo = None
        texto_linhas = []
        for ln in lines_block:
            if "-->" in ln:
                tempo = ln
            elif not ln.isdigit():
                texto_linhas.append(ln)
        if not tempo or not texto_linhas:
            continue
        try:
            ini, fim = [x.strip() for x in tempo.split("-->")]
            def parse_srt_time(t):
                hms, ms = t.split(',')
                h, m, sec = hms.split(':')
                return int(h)*3600 + int(m)*60 + int(sec) + int(ms)/1000
            a = parse_srt_time(ini)
            b = parse_srt_time(fim)
            texto = ass_escape(" ".join(texto_linhas))
            events.append(f"Dialogue: 0,{fmt_ass(a)},{fmt_ass(b)},GAB USA Subtitle,,0,0,0,,{texto}")
        except Exception:
            continue
    return ass_header() + "\n".join(events) + "\n"

# ----------------------------- OBS -----------------------------

def descobrir_senha_obs():
    """
    Le a senha e a porta do WebSocket direto da config do OBS, pra pessoa nao
    precisar copiar na mao. O OBS guarda isso em texto. Procura nos locais
    conhecidos (varia por versao/sistema). Devolve (senha, porta) ou (None, None).

    Prioridade: senha que o usuario tenha colado em config.json > config do OBS.
    """
    # 1. se a pessoa ja salvou manualmente, respeita
    manual = config_usuario.get("obs_senha", "").strip()
    if manual and manual != "TROQUE_AQUI":
        return manual, config_usuario.get("obs_porta", CONFIG["obs_porta"])

    home = Path.home()
    # locais possiveis da config do plugin websocket, Mac e Windows
    candidatos = []
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        base = Path(appdata) / "obs-studio"
    else:
        base = home / "Library" / "Application Support" / "obs-studio"
    # arquivo novo (plugin proprio) e o antigo (global.ini)
    candidatos += [
        base / "plugin_config" / "obs-websocket" / "config.json",
        base / "global.ini",
    ]

    import configparser
    for arq in candidatos:
        try:
            if not arq.exists():
                continue
            if arq.suffix == ".json":
                dados = json.loads(arq.read_text(encoding="utf-8"))
                senha = dados.get("server_password") or dados.get("ServerPassword")
                porta = dados.get("server_port") or dados.get("ServerPort") or CONFIG["obs_porta"]
                ativo = dados.get("server_enabled", dados.get("ServerEnabled", True))
                if senha and ativo:
                    print(f"[obs] senha lida automaticamente de {arq.name}")
                    return str(senha), int(porta)
            else:  # global.ini
                cp = configparser.ConfigParser()
                cp.read(arq, encoding="utf-8-sig")
                if cp.has_section("OBSWebSocket"):
                    senha = cp.get("OBSWebSocket", "ServerPassword", fallback="")
                    porta = cp.getint("OBSWebSocket", "ServerPort", fallback=CONFIG["obs_porta"])
                    ativo = cp.getboolean("OBSWebSocket", "ServerEnabled", fallback=True)
                    auth = cp.getboolean("OBSWebSocket", "AuthRequired", fallback=bool(senha))
                    if ativo and (senha or not auth):
                        if senha:
                            print(f"[obs] senha lida automaticamente de {arq.name}")
                        else:
                            print(f"[obs] WebSocket sem senha detectado em {arq.name}")
                        return senha, porta
        except Exception as e:
            print(f"[obs] nao deu pra ler {arq.name}: {e}")
    return None, None


def replay_status_ativo():
    """Retorna True se o Replay Buffer do OBS ja estiver rodando."""
    if obs_req is None:
        return False
    try:
        st = obs_req.get_replay_buffer_status()
        for attr in ("output_active", "outputActive", "replay_buffer_active", "replayBufferActive"):
            if hasattr(st, attr):
                return bool(getattr(st, attr))
        # obsws-python costuma devolver um objeto com attrs; fallback por string/dict
        if isinstance(st, dict):
            return bool(st.get("outputActive") or st.get("output_active"))
    except Exception:
        pass
    return False

def garantir_replay_buffer(silencioso=False):
    """Liga o Replay Buffer quando possivel.
    OBS pode retornar erro 500 quando o buffer ja esta rodando; nesse caso tratamos como OK.
    """
    if obs_req is None:
        return False
    if replay_status_ativo():
        if not silencioso:
            print("[obs] Replay Buffer ja estava ativo.")
        return True
    try:
        obs_req.start_replay_buffer()
        time.sleep(0.4)
        if replay_status_ativo():
            if not silencioso:
                print("[obs] Replay Buffer iniciado.")
            return True
        # em alguns OBS o status demora; assume OK se nao explodiu
        if not silencioso:
            print("[obs] Replay Buffer solicitado.")
        return True
    except Exception as e:
        # code 500 normalmente significa 'ja ativo' ou estado invalido temporario.
        if replay_status_ativo():
            if not silencioso:
                print("[obs] Replay Buffer ja estava ativo.")
            return True
        if not silencioso:
            print(f"[obs] Replay Buffer nao iniciou: {e}")
        return False

def iniciar_obs(senha_manual=None, porta_manual=None):
    global obs_req, obs_conectado
    # ordem: senha manual (do painel) > descoberta automatica > config padrao
    if senha_manual:
        senha = senha_manual
        porta = porta_manual or CONFIG["obs_porta"]
        print("[obs] usando senha informada no painel.")
    else:
        senha_auto, porta_auto = descobrir_senha_obs()
        senha = senha_auto if senha_auto is not None else CONFIG["obs_senha"]
        if senha == "TROQUE_AQUI":
            senha = ""
        porta = porta_auto if porta_auto else CONFIG["obs_porta"]
        if senha_auto:
            print("[obs] usando senha do WebSocket descoberta automaticamente.")
        elif senha_auto == "":
            print("[obs] usando WebSocket sem senha configurado automaticamente.")
    # cliente de eventos (escuta inicio/fim de gravacao e replay salvo)
    ev = None
    ultimo_erro = None
    # Na primeira abertura do OBS no Windows, o WebSocket pode demorar alguns segundos.
    # Em vez de falhar de cara, tenta por mais tempo e depois salva a senha quando conectar.
    for tentativa in range(1, 16):
        try:
            ev = obs.EventClient(host=CONFIG["obs_host"], port=porta, password=senha)
            obs_req = obs.ReqClient(host=CONFIG["obs_host"], port=porta,
                                    password=senha, timeout=3)
            ultimo_erro = None
            break
        except Exception as e:
            ultimo_erro = e
            obs_conectado = False
            if tentativa in (1, 5, 10):
                print(f"[obs] aguardando WebSocket do OBS abrir ({tentativa}/15): {e}")
            time.sleep(1.2)
    if ultimo_erro is not None or obs_req is None:
        obs_conectado = False
        print(f"[obs] nao conectou ({ultimo_erro}). Segue em modo manual, sem clipe automatico.")
        print("[obs] Dica: abra o OBS, ative o WebSocket (Ferramentas) e rode de novo.")
        return False
    try:
        # Depois que conectou uma vez, guarda a senha/porta para não pedir de novo.
        salvar_config_usuario({"obs_senha": senha, "obs_porta": porta})
        config_usuario["obs_senha"] = senha
        config_usuario["obs_porta"] = porta
    except Exception:
        pass

    def zerar(motivo):
        global gravando, inicio_gravacao, linhas, cortes, texto_desde_ia, texto_contexto_ia, ultima_ia
        gravando = True; inicio_gravacao = time.time()
        linhas = []; cortes = []; texto_desde_ia = []; texto_contexto_ia = []; ultima_ia = time.time()
        # liga o replay buffer pra ja estar guardando o trecho recente.
        rb_ok = garantir_replay_buffer(silencioso=True)
        print(f"[obs] {motivo} -> 00:00:00" + (" + replay buffer ativo" if rb_ok else " + replay buffer pendente"))
        enviar({"tipo":"status","gravando":True,"motivo":motivo,"transcricao_ativa":bool(config_usuario.get("transcricao_ativa", CONFIG.get("transcricao_ativa", True)))})

    def parar(motivo):
        global gravando
        gravando = False
        print(f"[obs] {motivo}")
        enviar({"tipo":"status","gravando":False,"motivo":motivo,"transcricao_ativa":bool(config_usuario.get("transcricao_ativa", CONFIG.get("transcricao_ativa", True)))})

    def on_record_state_changed(d):
        global gravacao_completa
        e = getattr(d,"output_state","")
        if "STARTED" in e: zerar("Gravacao iniciada")
        elif "STOPPED" in e:
            # o evento de parada ja traz o caminho do arquivo gravado
            caminho = getattr(d,"output_path","") or getattr(d,"outputPath","")
            if caminho: gravacao_completa = caminho
            parar("Gravacao encerrada")
            enviar({"tipo":"gravacao_pronta","caminho":gravacao_completa})

    def on_stream_state_changed(d):
        e = getattr(d,"output_state","")
        if "STARTED" in e: zerar("Transmissao iniciada")
        elif "STOPPED" in e: parar("Transmissao encerrada")

    def on_replay_buffer_saved(d):
        caminho = getattr(d,"saved_replay_path","") or getattr(d,"savedReplayPath","")
        finalizar_clipe(caminho)

    ev.callback.register([on_record_state_changed, on_stream_state_changed,
                          on_replay_buffer_saved])
    obs_conectado = True
    print("[obs] conectado.")
    try:
        if bool(config_usuario.get("obs_apply_audio_device", CONFIG.get("obs_apply_audio_device", True))):
            d_salvo = config_usuario.get("dispositivo_audio", config_usuario.get("audio_input_device_id", None))
            n_salvo = config_usuario.get("audio_input_device_name") or _audio_device_name(d_salvo)
            if d_salvo is not None or n_salvo:
                ok_audio_obs, msg_audio_obs = aplicar_audio_no_obs(d_salvo, n_salvo)
                print(f"[obs-audio] apply inicial: {'OK' if ok_audio_obs else 'AVISO'} - {msg_audio_obs}")
    except Exception as e:
        print(f"[obs-audio] apply inicial falhou: {e}")
    return True


def _obj_get(obj, *names, default=None):
    for name in names:
        try:
            if isinstance(obj, dict) and name in obj:
                return obj.get(name)
            if hasattr(obj, name):
                return getattr(obj, name)
        except Exception:
            pass
    return default

def _audio_device_name(dispositivo):
    if dispositivo in (None, '', 'padrao'):
        return 'padrao do sistema'
    try:
        idx = int(dispositivo)
        if sd is not None:
            return str(sd.query_devices(idx).get('name', idx))
    except Exception:
        pass
    return str(dispositivo)

def _audio_device_id(dispositivo):
    return _normalizar_audio_id(dispositivo)

def _obs_audio_input_kind():
    sistema = platform.system().lower()
    if sistema == 'darwin':
        return 'coreaudio_input_capture'
    if sistema == 'windows':
        return 'wasapi_input_capture'
    return 'pulse_input_capture'

def _obs_audio_settings_para_device(device_id, device_name):
    # OBS usa IDs internos por sistema, mas em muitos casos aceita nome/UID.
    # Mantemos os dois para maximizar compatibilidade entre macOS/Windows.
    nome = str(device_name or device_id or '').strip()
    did = '' if device_id is None else str(device_id)
    if nome.lower() in ('', 'none', 'padrao', 'padrão', 'padrao do sistema'):
        return {}
    return {
        'device_id': nome,
        'device_name': nome,
        'device': nome,
        'id': did or nome,
    }

def aplicar_audio_no_obs(device_id=None, device_name=None, source_name=None):
    """Cria/atualiza a fonte fixa FrameZero Audio no OBS.
    O painel/site chama o Core; o Core aplica no OBS via WebSocket.
    """
    global obs_conectado
    source_name = source_name or config_usuario.get('obs_audio_source_name') or CONFIG.get('obs_audio_source_name', 'FrameZero Audio')
    device_name = device_name or _audio_device_name(device_id)
    if obs_req is None or not obs_conectado:
        return False, 'OBS WebSocket não conectado'
    kind = _obs_audio_input_kind()
    settings = _obs_audio_settings_para_device(device_id, device_name)
    try:
        exists = False
        try:
            res = obs_req.get_input_list()
            inputs = _obj_get(res, 'inputs', 'input_list', 'inputList', default=[]) or []
            for it in inputs:
                nm = _obj_get(it, 'inputName', 'input_name', 'name', default='')
                if str(nm) == source_name:
                    exists = True
                    break
        except Exception:
            exists = False

        if exists:
            try:
                obs_req.set_input_settings(source_name, settings, True)
            except TypeError:
                obs_req.set_input_settings(input_name=source_name, input_settings=settings, overlay=True)
            print(f'[obs-audio] fonte atualizada: {source_name} -> {device_name}')
        else:
            scene_name = None
            try:
                cur = obs_req.get_current_program_scene()
                scene_name = _obj_get(cur, 'currentProgramSceneName', 'current_program_scene_name', 'sceneName', 'scene_name')
            except Exception:
                pass
            if not scene_name:
                try:
                    cur = obs_req.get_current_preview_scene()
                    scene_name = _obj_get(cur, 'currentPreviewSceneName', 'current_preview_scene_name', 'sceneName', 'scene_name')
                except Exception:
                    pass
            if not scene_name:
                return False, 'não consegui descobrir a cena atual do OBS'
            try:
                obs_req.create_input(scene_name, source_name, kind, settings, True)
            except TypeError:
                obs_req.create_input(scene_name=scene_name, input_name=source_name, input_kind=kind, input_settings=settings, scene_item_enabled=True)
            print(f'[obs-audio] fonte criada na cena {scene_name}: {source_name} -> {device_name}')

        salvar_config_usuario({
            'obs_audio_source_name': source_name,
            'obs_apply_audio_device': True,
            'obs_audio_source_kind': kind,
            'obs_audio_device_name': device_name,
            'obs_audio_device_id': device_id,
        })
        return True, f'OBS atualizado: {source_name} -> {device_name}'
    except Exception as e:
        print(f'[obs-audio] falha ao atualizar OBS: {e}')
        return False, str(e)

def nome_seguro(texto, limite=50):
    """Slug curto para compatibilidade com arquivos antigos."""
    t = str(texto or "").strip().lower()
    t = re.sub(r"\s+", "-", t)
    t = re.sub(r"[^a-z0-9\-áàâãéêíóôõúç]", "", t)
    t = re.sub(r"-+", "-", t).strip("-")
    return (t[:limite].strip("-") or "momento")

def titulo_arquivo_seguro(texto, limite=90):
    """Nome legível para pasta/arquivo, preservando título e funcionando no Windows/macOS."""
    t = str(texto or "").strip()
    t = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", t)
    t = re.sub(r"\s+", " ", t).strip(" ._-–—")
    if not t:
        t = "Momento"
    if len(t) > limite:
        t = t[:limite].rstrip(" ._-–—")
    return t or "Momento"

def titulo_corte_limpo(c):
    return titulo_arquivo_seguro((c or {}).get("titulo") or "Momento", 90)

def nome_video_corte(c, prop=None):
    titulo = titulo_corte_limpo(c)
    if prop:
        return f"{titulo} - {str(prop).replace(':', 'x')}.mp4"
    return f"{titulo}.mp4"


def titulo_hashtag(t):
    return re.sub(r"[^a-zA-Z0-9áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ\s]", "", t).strip()

def hashtags_padrao(c):
    perfil = perfil_idioma_atual()
    tags = list(perfil.get("hashtags") or ["#sermon", "#faith", "#Jesus", "#church"])
    emocao = _norm(c.get("emocao", ""))
    if perfil_id_atual().startswith("pt"):
        if "quebrant" in emocao: tags += ["#quebrantamento", "#arrependimento"]
        if "esper" in emocao: tags += ["#esperança", "#recomeço"]
        if "urg" in emocao: tags += ["#palavradedeus", "#hoje"]
        if "hist" in _norm(c.get("funcao", "")): tags += ["#historia", "#biblia"]
    elif perfil_id_atual() == "en":
        if "hope" in emocao: tags += ["#hope", "#encouragement"]
        if "story" in _norm(c.get("funcao", "")): tags += ["#bible", "#story"]
    elif perfil_id_atual() == "es":
        if "esper" in emocao: tags += ["#esperanza", "#palabradedios"]
        if "hist" in _norm(c.get("funcao", "")): tags += ["#biblia", "#historia"]
    return " ".join(dict.fromkeys(tags))

def legenda_instagram(c):
    titulo = titulo_hashtag(c.get("titulo") or "Sermon moment")
    frase = (c.get("texto") or "").strip()
    frase_curta = frase if len(frase) <= 180 else frase[:177].rstrip() + "..."
    pid = perfil_id_atual()
    if pid == "en":
        return (f"{titulo}\n\n{frase_curta}\n\nA message like this can strengthen your faith and speak to someone right on time. Save this clip and share it with someone who needs encouragement today.\n\nScore: {c.get('score', 0)}/100\nEmotion: {c.get('emocao') or 'faith'}\nClip type: {c.get('funcao') or 'impact'}\n\n{hashtags_padrao(c)}")
    if pid == "es":
        return (f"{titulo}\n\n{frase_curta}\n\nA veces Dios usa una palabra para fortalecer la fe de alguien. Guarda este corte y compártelo con alguien que necesite escucharlo hoy.\n\nScore: {c.get('score', 0)}/100\nEmoción: {c.get('emocao') or 'fe'}\nFunción del corte: {c.get('funcao') or 'impacto'}\n\n{hashtags_padrao(c)}")
    return (
        f"{titulo}\n\n"
        f"{frase_curta}\n\n"
        "Às vezes Deus usa uma frase para alinhar tudo de novo por dentro. "
        "Salva esse corte para assistir de novo e envia para alguém que precisa ouvir isso hoje.\n\n"
        f"Score viral: {c.get('score', 0)}/100\n"
        f"Emoção: {c.get('emocao') or 'fé'}\n"
        f"Função do corte: {c.get('funcao') or 'impacto'}\n\n"
        f"{hashtags_padrao(c)}"
    )

def legenda_tiktok(c):
    titulo = titulo_hashtag(c.get("titulo") or "Sermon clip")
    frase = (c.get("texto") or "").strip()
    frase_curta = frase if len(frase) <= 120 else frase[:117].rstrip() + "..."
    pid = perfil_id_atual()
    if pid == "en":
        return f"{titulo}\n\n{frase_curta}\n\nWatch this to the end. This word has a strong turn.\n\n{hashtags_padrao(c)}"
    if pid == "es":
        return f"{titulo}\n\n{frase_curta}\n\nMíralo hasta el final. Esta palabra tiene una vuelta fuerte.\n\n{hashtags_padrao(c)}"
    return (
        f"{titulo}\n\n"
        f"{frase_curta}\n\n"
        "Assiste até o final. Essa palavra tem uma virada forte.\n\n"
        f"{hashtags_padrao(c)}"
    )


def texto_do_corte(c):
    """Texto principal do corte, usando o melhor campo disponível."""
    c = c or {}
    return str(
        c.get("texto_final_corte")
        or c.get("texto")
        or c.get("trecho")
        or c.get("quote")
        or c.get("hook")
        or ""
    ).strip()


def _lista_strings(valor):
    """Normaliza campos vindos da IA em lista de strings limpas."""
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set)):
        bruto = list(valor)
    else:
        txt = str(valor).strip()
        if not txt:
            return []
        bruto = re.split(r"\n|;|\|", txt)
    out = []
    for item in bruto:
        if isinstance(item, dict):
            item = item.get("texto") or item.get("frase") or item.get("referencia") or item.get("versiculo") or item.get("title") or ""
        item = re.sub(r"\s+", " ", str(item or "").strip(" -–—•\t"))
        if item and item not in out:
            out.append(item)
    return out


def _sentencas(texto):
    texto = re.sub(r"\s+", " ", str(texto or "")).strip()
    if not texto:
        return []
    partes = re.split(r"(?<=[.!?…])\s+", texto)
    # quando o Whisper vem sem pontuação, quebra em blocos de até ~24 palavras.
    if len(partes) <= 1 and len(texto.split()) > 28:
        palavras = texto.split()
        partes = [" ".join(palavras[i:i+24]) for i in range(0, len(palavras), 24)]
    return [p.strip(" \t\n\r-–—") for p in partes if len(p.strip()) >= 12]


def extrair_frases_de_impacto(c, limite=5):
    """Extrai frases fortes do corte. Usa a resposta da IA quando houver e aplica fallback local."""
    c = c or {}
    campos = [
        c.get("frases_de_impacto"), c.get("frases_impacto"), c.get("frase_impacto"),
        c.get("impact_phrases"), c.get("frases"), c.get("hook")
    ]
    frases = []
    for campo in campos:
        frases.extend(_lista_strings(campo))
    texto = texto_do_corte(c)
    # Fallback: frases com força emocional, ensino, contraste, pergunta ou fechamento.
    gatilhos = re.compile(
        r"\b(verdade|segredo|ningu[eé]m|n[aã]o desista|Deus|Jesus|f[eé]|promessa|processo|"
        r"persist|ora[cç][aã]o|milagre|mudou tudo|entendi|aprendi|problema|por isso|"
        r"sabe|quem conhece|o que|por qu[eê]|quando|mas|s[oó] que|quanto mais|nunca|sempre)\b",
        re.I,
    )
    for sent in _sentencas(texto):
        limpa = re.sub(r"\s+", " ", sent).strip()
        if len(limpa) < 30 or len(limpa) > 240:
            continue
        if gatilhos.search(limpa) or "?" in limpa or "!" in limpa:
            frases.append(limpa)
    # Se ainda não tem nada, pega a primeira frase usável do corte.
    if not frases:
        for sent in _sentencas(texto):
            limpa = re.sub(r"\s+", " ", sent).strip()
            if 30 <= len(limpa) <= 220:
                frases.append(limpa)
                break
    out = []
    for frase in frases:
        frase = re.sub(r"\s+", " ", str(frase or "")).strip(" \"'“”‘’.-–—")
        if not frase:
            continue
        if len(frase) > 260:
            frase = frase[:257].rstrip() + "..."
        if frase not in out:
            out.append(frase)
        if len(out) >= limite:
            break
    return out


def extrair_versiculos(c):
    """Extrai referências bíblicas no idioma escolhido, sem inventar versículo."""
    c = c or {}
    refs = []
    for campo in (
        c.get("versiculos"), c.get("versiculos_biblicos"), c.get("referencias_biblicas"),
        c.get("bible_verses"), c.get("referencias")
    ):
        refs.extend(_lista_strings(campo))
    texto = texto_do_corte(c)
    livros = bible_books_regex_atual()
    padrao = re.compile(
        rf"\b((?:{livros})\s*(?:chapter\s*|cap[ií]tulo\s*)?\d{{1,3}}(?:\s*[:.]\s*\d{{1,3}}(?:\s*[-–]\s*\d{{1,3}})?)?)\b",
        re.I,
    )
    for m in padrao.finditer(texto):
        refs.append(m.group(1))
    out = []
    for ref in refs:
        ref = re.sub(r"\s+", " ", str(ref or "")).strip(" .,;:-–—")
        if not ref or not re.search(r"\d", ref):
            continue
        if ref not in out:
            out.append(ref)
    return out


def texto_frases_de_impacto(c):
    frases = extrair_frases_de_impacto(c)
    titulo = (c or {}).get("titulo") or "Momento"
    linhas_out = [f"FRASES DE IMPACTO — {titulo}", ""]
    if not frases:
        linhas_out.append("Nenhuma frase de impacto detectada neste corte.")
    else:
        for i, frase in enumerate(frases, 1):
            linhas_out.append(f"{i:02d}. {frase}")
    linhas_out.append("")
    return "\n".join(linhas_out)


def texto_versiculos(c):
    versiculos = extrair_versiculos(c)
    titulo = (c or {}).get("titulo") or "Momento"
    linhas_out = [f"VERSÍCULOS / REFERÊNCIAS BÍBLICAS — {titulo}", ""]
    if not versiculos:
        linhas_out.append("Nenhum versículo detectado neste corte.")
    else:
        for i, ref in enumerate(versiculos, 1):
            linhas_out.append(f"{i:02d}. {ref}")
    linhas_out.append("")
    return "\n".join(linhas_out)


def texto_briefing_corte(c):
    frases = extrair_frases_de_impacto(c)
    versiculos = extrair_versiculos(c)
    return "\n".join([
        f"TÍTULO: {c.get('titulo','Momento')}",
        f"SCORE: {c.get('score',0)}/100",
        f"TIMESTAMP: {c.get('timestamp','00:00:00')}",
        f"EMOÇÃO: {c.get('emocao','')}",
        f"FUNÇÃO NARRATIVA: {c.get('funcao','')}",
        f"RAZÃO DO CORTE: {c.get('razao','')}",
        f"FRASES DE IMPACTO: {len(frases)}",
        f"VERSÍCULOS DETECTADOS: {len(versiculos)}",
        "",
        "TRECHO:",
        texto_do_corte(c),
        "",
        "PRINCIPAIS FRASES:",
        "\n".join([f"- {x}" for x in frases]) if frases else "Nenhuma frase de impacto detectada.",
        "",
        "VERSÍCULOS / REFERÊNCIAS:",
        "\n".join([f"- {x}" for x in versiculos]) if versiculos else "Nenhum versículo detectado.",
        "",
        "LEGENDA INSTAGRAM:",
        legenda_instagram(c),
        "",
        "LEGENDA TIKTOK:",
        legenda_tiktok(c),
        "",
    ])

def pasta_principal(base_dir, tipo="final"):
    global pasta_cortes_ao_vivo, pasta_cortes_finais
    nome = config_usuario.get("pasta_principal_cortes", CONFIG.get("pasta_principal_cortes", "FrameZero_Cortes"))
    if tipo == "ao_vivo":
        if not pasta_cortes_ao_vivo:
            pasta_cortes_ao_vivo = os.path.join(base_dir, f"{nome}_AoVivo_" + time.strftime("%Y-%m-%d_%H-%M"))
            os.makedirs(pasta_cortes_ao_vivo, exist_ok=True)
        return pasta_cortes_ao_vivo
    if not pasta_cortes_finais:
        pasta_cortes_finais = os.path.join(base_dir, f"{nome}_Finais_" + time.strftime("%Y-%m-%d_%H-%M"))
        os.makedirs(pasta_cortes_finais, exist_ok=True)
    return pasta_cortes_finais

def pasta_do_corte(pasta_mae, c):
    """Cria pasta do corte com o título em primeiro lugar, para ficar fácil achar."""
    ts = (c.get("timestamp") or "00:00:00").replace(":", "-")
    titulo = titulo_arquivo_seguro(c.get("titulo") or "Momento", 72)
    score = str(int(float(c.get("score", 0) or 0))).zfill(3)
    nome = f"{titulo} - {ts} - score {score}"
    pasta = os.path.join(pasta_mae, nome)
    n = 2
    while os.path.exists(pasta):
        pasta = os.path.join(pasta_mae, f"{nome} ({n})"); n += 1
    os.makedirs(pasta, exist_ok=True)
    return pasta

def salvar_arquivos_corte(pasta, c, video_path=None, srt_text=None, videos=None):
    # Arquivos de apoio para editor/social media.
    try:
        meta = dict(c)
        meta["srt_idioma"] = config_usuario.get("srt_idioma", CONFIG.get("srt_idioma", "pt-BR"))
        meta["srt_caracteres_por_linha"] = _cfg_int("srt_caracteres_por_linha", 37)
        meta["srt_linha_unica"] = _cfg_bool("srt_linha_unica", True)
        meta["subtitle_style"] = {
            "formato": "SRT",
            "arquivo": "legenda.srt",
            "fonte_recomendada": config_usuario.get("subtitle_font_family", CONFIG.get("subtitle_font_family", "Poppins")),
            "tamanho_recomendado": _cfg_int("subtitle_font_size", 13),
            "bold_recomendado": _cfg_bool("subtitle_bold", True),
            "observacao": "v81j: legenda.ass removida; a legenda principal fica em legenda.srt."
        }
        frases_impacto = extrair_frases_de_impacto(meta)
        versiculos = extrair_versiculos(meta)
        meta["frases_de_impacto"] = frases_impacto
        meta["versiculos"] = versiculos
        if video_path:
            meta["video"] = os.path.basename(video_path)
        if videos:
            meta["videos"] = {k: os.path.relpath(v, pasta) for k, v in videos.items()}
        Path(os.path.join(pasta, "metadata.json")).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        Path(os.path.join(pasta, "resumo-do-corte.txt")).write_text(texto_briefing_corte(meta), encoding="utf-8")
        Path(os.path.join(pasta, "frases-de-impacto.txt")).write_text(texto_frases_de_impacto(meta), encoding="utf-8")
        Path(os.path.join(pasta, "versiculos.txt")).write_text(texto_versiculos(meta), encoding="utf-8")
        legendas_sociais = "\n".join([
            "LEGENDA INSTAGRAM",
            "=================",
            legenda_instagram(c),
            "",
            "LEGENDA TIKTOK",
            "==============",
            legenda_tiktok(c),
            "",
        ])
        Path(os.path.join(pasta, "legendas-redes-sociais.txt")).write_text(legendas_sociais, encoding="utf-8")
        if srt_text is not None:
            Path(os.path.join(pasta, "legenda.srt")).write_text(srt_text, encoding="utf-8")
    except Exception as e:
        print(f"[corte] falhou ao salvar arquivos sociais: {e}")

def finalizar_clipe(caminho_original):
    """
    Chamado quando o OBS termina de salvar um replay.
    Renomeia o arquivo com o titulo do momento e gera um .srt daquele trecho.
    """
    if not caminho_original or not os.path.exists(caminho_original):
        print(f"[clipe] salvo, mas caminho nao encontrado: {caminho_original}")
        enviar({"tipo":"clipe_salvo","caminho":caminho_original,"nome":""})
        return

    # pega o momento pendente associado a este save (FIFO)
    try:
        info = clipes_pendentes.get_nowait()
    except queue.Empty:
        info = {"titulo":"momento","timestamp":fmt(0),"inicio":0,"fim":0}

    pasta_gravacao = os.path.dirname(caminho_original)
    # Janela exata do corte em tempo da gravação/live.
    inicio_real, fim_real, dur_real = normalizar_janela_corte(info.get("inicio", 0), info.get("fim", 0), pico=info.get("fim", 0))
    c_meta = {
        "titulo": info.get("titulo", "Momento"),
        "timestamp": info.get("timestamp", fmt(fim_real)),
        "inicio": inicio_real,
        "fim": fim_real,
        "inicio_exato": inicio_real,
        "fim_exato": fim_real,
        "duracao_exata": dur_real,
        "tempo": fim_real,
        "score": info.get("score", 0),
        "texto": info.get("texto", info.get("titulo", "")),
        "razao": info.get("razao", "clipe automático ao vivo"),
        "emocao": info.get("emocao", "fé"),
        "funcao": info.get("funcao", "impacto"),
        "origem": info.get("origem", "ao_vivo"),
    }
    pasta_mae = pasta_principal(pasta_gravacao, "ao_vivo")
    pasta_corte = pasta_do_corte(pasta_mae, c_meta)
    novo_video = ""
    videos_gerados = {}

    # O OBS salva o Replay Buffer inteiro (ex: 120s). Aqui cortamos esse arquivo bruto
    # e já entregamos as duas versões automáticas: 16x9 e 9x16.
    recorte_ok = False
    if caminho_ffmpeg():
        try:
            dur_replay = duracao_video_seg(caminho_original)
            if not dur_replay:
                dur_replay = float(config_usuario.get("segundos_clipe", CONFIG.get("segundos_clipe", 120)))
            # O final do arquivo de Replay Buffer é o momento em que pedimos SaveReplayBuffer,
            # não necessariamente o timestamp do pico. Isso evita corte deslocado ou bruto de 2min.
            fim_buffer_timeline = float(info.get("replay_solicitado_em", fim_real) or fim_real)
            inicio_buffer = max(0.0, fim_buffer_timeline - float(dur_replay))
            offset = max(0.0, inicio_real - inicio_buffer)
            dur_saida = min(dur_real, max(0.5, float(dur_replay) - offset))
            videos_gerados = gerar_versoes_do_corte(caminho_original, pasta_corte, c_meta, inicio=offset, duracao=dur_saida, timeout=240)
            recorte_ok = bool(videos_gerados)
            # usa 9x16 como preview principal quando existir; senão 16x9.
            novo_video = videos_gerados.get("9x16") or videos_gerados.get("16x9") or next(iter(videos_gerados.values()), "")
            if recorte_ok:
                dur_out = duracao_video_seg(novo_video)
                _mn_chk, _mx_chk = duracao_cortes_config()
                if dur_out and dur_out > (_mx_chk + 2.0):
                    print(f"[clipe] recorte saiu maior que o maximo configurado ({dur_out:.1f}s > {_mx_chk}s).")
                try: os.remove(caminho_original)
                except Exception: pass
            else:
                print("[clipe] ffmpeg nao conseguiu gerar versões 16x9/9x16; vou manter arquivo original como bruto.")
        except Exception as e:
            print(f"[clipe] falhou ao recortar Replay Buffer: {e}")
    if not recorte_ok:
        # Fallback: preserva o replay bruto, mas deixa claro no nome.
        ext = os.path.splitext(caminho_original)[1] or ".mov"
        bruto = os.path.join(pasta_corte, "replay-buffer-bruto" + ext)
        try:
            shutil.move(caminho_original, bruto)
            novo_video = bruto
        except Exception as e:
            print(f"[clipe] nao deu pra mover replay bruto ({e}), mantendo caminho original")
            novo_video = caminho_original
            pasta_corte = os.path.dirname(novo_video)

    # gera o .srt só da janela exata, com timecode reiniciado em 00:00:00.
    srt = gerar_srt_corte_preciso(inicio_real, fim_real)
    salvar_arquivos_corte(pasta_corte, c_meta, video_path=novo_video, srt_text=srt, videos=videos_gerados)

    nome = os.path.basename(pasta_corte)
    print(f"[clipe] salvo na pasta: {nome}  (16x9 + 9x16 na mesma pasta + srt + legendas sociais unificadas)")
    enviar({"tipo":"clipe_salvo","caminho":novo_video,"nome":nome})

def salvar_clipe(titulo="Momento", timestamp=None, inicio=None, fim=None, motivo="manual", texto="", score=0, razao="", emocao="", funcao="", origem=""):
    """Pede pro OBS cuspir o trecho recente do Replay Buffer, guardando o titulo
    pra renomear o arquivo quando o save terminar."""
    if obs_req is None:
        enviar({"tipo":"aviso","texto":"OBS nao conectado, nao deu pra clipar."})
        return
    # tempo atual da live se nao veio especificado (clipe manual)
    agora = (time.time() - inicio_gravacao) if inicio_gravacao else 0
    fim_real = fim if fim is not None else agora
    if inicio is None:
        _mn, _mx = duracao_cortes_config()
        ini_real = max(0, fim_real - _mx)
    else:
        ini_real = inicio
    ini_real, fim_real, _dur_real = normalizar_janela_corte(ini_real, fim_real, pico=fim_real)
    clipes_pendentes.put({
        "titulo": titulo,
        "timestamp": timestamp or fmt(fim_real),
        "inicio": ini_real,
        "fim": fim_real,
        "replay_solicitado_em": agora,
        "texto": texto or titulo,
        "score": score,
        "razao": razao,
        "emocao": emocao,
        "funcao": funcao,
        "origem": origem or motivo,
    })
    try:
        if not replay_status_ativo():
            garantir_replay_buffer(silencioso=True)
            time.sleep(0.6)
        obs_req.save_replay_buffer()
        print(f"[clipe] disparado ({motivo}) - {titulo}")
    except Exception as e:
        # Tenta uma vez iniciar o buffer e salvar novamente.
        try:
            garantir_replay_buffer(silencioso=True)
            time.sleep(1.0)
            obs_req.save_replay_buffer()
            print(f"[clipe] disparado apos ativar replay ({motivo}) - {titulo}")
            return
        except Exception as e2:
            print(f"[clipe] falhou: {e2}")
            try: clipes_pendentes.get_nowait()
            except queue.Empty: pass
            enviar({"tipo":"aviso","texto":"Replay Buffer nao esta rodando no OBS. Ative em Controles > Iniciar buffer de repetição."})

# ----------------------------- PREVIEW + TRACKING -----------------------------

preview_ativo = False
vertical_ativo = bool(config_usuario.get("vertical_ativo", CONFIG["vertical_ativo"]))

def nome_cena_programa():
    """Nome da cena atual/programa no OBS."""
    if obs_req is None:
        return None
    try:
        cur = obs_req.get_current_program_scene()
        return getattr(cur, "current_program_scene_name", None) or getattr(cur, "scene_name", None)
    except Exception as e:
        print(f"[obs] nao consegui ler cena atual: {e}")
        return None

def configurar_cena_vertical(ligar=True):
    """
    Ativa/desativa o Modo Vertical dentro do FrameZero.

    O que ele faz:
      - salva 9:16 como proporcao padrao dos cortes;
      - tenta criar uma cena auxiliar 'FrameZero Vertical' no OBS com a cena atual
        aninhada, sem preview do corte.

    O painel/canvas vertical real fica por conta do Aitum Vertical instalado no OBS.
    """
    global vertical_ativo
    vertical_ativo = bool(ligar)
    config_usuario["vertical_ativo"] = vertical_ativo
    config_usuario["proporcao_corte"] = "9:16"
    salvar_config_usuario({"vertical_ativo": vertical_ativo, "proporcao_corte": "9:16"})

    if not vertical_ativo:
        print("[vertical] modo vertical desligado")
        return True, "Modo Vertical desligado"

    if obs_req is None:
        return False, "Modo Vertical ligado no painel, mas OBS nao conectado"

    cena_vertical = config_usuario.get("vertical_cena", CONFIG["vertical_cena"])
    cena_programa = nome_cena_programa()
    try:
        try:
            cenas = obs_req.get_scene_list()
            lista = getattr(cenas, "scenes", []) or []
            nomes = []
            for c in lista:
                if isinstance(c, dict):
                    nomes.append(c.get("sceneName") or c.get("scene_name"))
                else:
                    nomes.append(getattr(c, "scene_name", None) or getattr(c, "sceneName", None))
            if cena_vertical not in nomes:
                obs_req.create_scene(cena_vertical)
                print(f"[vertical] cena criada: {cena_vertical}")
        except Exception as e:
            print(f"[vertical] nao consegui verificar/criar cena: {e}")

        if cena_programa and cena_programa != cena_vertical:
            try:
                itens = obs_req.get_scene_item_list(cena_vertical)
                lista_itens = getattr(itens, "scene_items", []) or []
                ja_tem = False
                for it in lista_itens:
                    nome_fonte = (it.get("sourceName") if isinstance(it, dict) else getattr(it, "source_name", None))
                    if nome_fonte == cena_programa:
                        ja_tem = True
                        break
                if not ja_tem:
                    obs_req.create_scene_item(cena_vertical, cena_programa, True)
                    print(f"[vertical] fonte adicionada: {cena_programa} -> {cena_vertical}")
            except Exception as e:
                print(f"[vertical] nao consegui adicionar fonte/cena aninhada: {e}")

        return True, f"Modo Vertical ligado. Cena auxiliar sem preview: {cena_vertical}"
    except Exception as e:
        print(f"[vertical] falhou: {e}")
        return False, "Modo Vertical ligado no painel; cena auxiliar nao foi criada"

def obter_screenshot_obs():
    """Pega um screenshot da cena atual do OBS via WebSocket (base64 jpg)."""
    if obs_req is None:
        return None
    try:
        # cena atual
        nome_cena = nome_cena_programa()
        if not nome_cena:
            return None
        # screenshot em jpg, largura modesta pra nao pesar
        r = obs_req.get_source_screenshot(nome_cena, "jpg", 640, 360, 60)
        return getattr(r, "image_data", None)  # data:image/jpg;base64,...
    except Exception as e:
        print(f"[preview] falhou: {e}")
        return None

def loop_preview():
    """Enquanto o preview estiver ativo, manda frames da cena do OBS ao painel."""
    while True:
        if preview_ativo and obs_req is not None:
            img = obter_screenshot_obs()
            if img:
                enviar({"tipo": "preview_frame", "img": img})
            time.sleep(0.6)  # ~1.6 fps: leve, suficiente pra conferir enquadramento
        else:
            time.sleep(0.3)

def face_tracker_instalado():
    """Confere se o plugin Face Tracker existe nos caminhos padrao do OBS no macOS."""
    possiveis = [
        Path.home() / "Library/Application Support/obs-studio/plugins/obs-face-tracker.plugin",
        Path("/Library/Application Support/obs-studio/plugins/obs-face-tracker.plugin"),
    ]
    return any(p.exists() for p in possiveis)

def _extrair_nome_item(item):
    if isinstance(item, dict):
        return item.get("sourceName") or item.get("source_name") or item.get("inputName") or item.get("input_name")
    return (getattr(item, "source_name", None) or getattr(item, "sourceName", None) or
            getattr(item, "input_name", None) or getattr(item, "inputName", None))

def _fontes_da_cena_atual():
    nomes = []
    try:
        cena = nome_cena_programa()
        if not cena:
            return nomes
        itens = obs_req.get_scene_item_list(cena)
        lista = getattr(itens, "scene_items", []) or getattr(itens, "sceneItems", []) or []
        for it in lista:
            nome = _extrair_nome_item(it)
            if nome and nome not in nomes:
                nomes.append(nome)
        if cena not in nomes:
            nomes.append(cena)
    except Exception as e:
        print(f"[tracking] nao consegui listar fontes da cena: {e}")
    return nomes

def ligar_tracking(ligar):
    """
    Liga/desliga o filtro Face Tracker se ele ja estiver em alguma fonte da cena.

    Importante: o Face Tracker e um FILTRO da fonte da camera, nao da cena inteira.
    Antes o sistema tentava ligar o filtro na cena e avisava errado que o plugin
    nao estava adicionado. Agora ele procura o filtro nas fontes da cena e, se
    nao encontrar, avisa corretamente que o plugin esta instalado, mas o filtro
    ainda precisa ser colocado uma vez na camera.
    """
    if obs_req is None:
        return False, "OBS nao conectado"

    instalado = face_tracker_instalado()
    fontes = _fontes_da_cena_atual()
    candidatos = []

    # 1) Procura filtros existentes nas fontes da cena
    for fonte in fontes:
        try:
            resp = obs_req.get_source_filter_list(fonte)
            filtros = getattr(resp, "filters", []) or getattr(resp, "source_filters", []) or []
            for f in filtros:
                if isinstance(f, dict):
                    nome_filtro = f.get("filterName") or f.get("filter_name") or f.get("name")
                    tipo_filtro = f.get("filterKind") or f.get("filter_kind") or f.get("kind") or ""
                else:
                    nome_filtro = (getattr(f, "filter_name", None) or getattr(f, "filterName", None) or getattr(f, "name", None))
                    tipo_filtro = (getattr(f, "filter_kind", None) or getattr(f, "filterKind", None) or getattr(f, "kind", None) or "")
                texto = f"{nome_filtro or ''} {tipo_filtro or ''}".lower()
                if "face" in texto and "tracker" in texto:
                    candidatos.append((fonte, nome_filtro or "Face Tracker"))
        except Exception:
            pass

    # 2) Tenta nomes comuns como fallback
    for fonte in fontes:
        for nome_filtro in ("Face Tracker", "face-tracker", "Face Tracker Filter"):
            if (fonte, nome_filtro) in candidatos:
                continue
            try:
                obs_req.set_source_filter_enabled(fonte, nome_filtro, ligar)
                return True, f"Face Tracker {'ligado' if ligar else 'desligado'} em {fonte}"
            except Exception:
                pass

    # 3) Liga/desliga candidatos encontrados
    if candidatos:
        fonte, filtro = candidatos[0]
        try:
            obs_req.set_source_filter_enabled(fonte, filtro, ligar)
            return True, f"Face Tracker {'ligado' if ligar else 'desligado'} em {fonte}"
        except Exception as e:
            print(f"[tracking] falhou ao alternar {filtro} em {fonte}: {e}")

    if instalado:
        return False, "Face Tracker instalado. Falta adicionar o filtro uma vez na fonte da camera: Filtros > Filtros de Efeito > + > Face Tracker."
    return False, "Face Tracker nao instalado ou OBS nao carregou o plugin."

# ----------------------------- IA (OpenAI) -----------------------------

def cliente_openai():
    chave = config_usuario.get("openai_key", "").strip()
    if not chave or OpenAI is None:
        return None
    try:
        return OpenAI(api_key=chave)
    except Exception:
        return None

PROMPT_CORTE = """Voce analisa a transcricao de um culto cristao brasileiro e identifica
os MELHORES momentos para cortes de video curtos (Reels/Shorts).

Primeiro entenda se o trecho é PREGAÇÃO ou MÚSICA/LOUVOR.

Se for PREGAÇÃO:
- Priorize frase de impacto citavel, climax emocional, historia fechada,
  palavra direcionada, aplicacao, ministracao ou ensino claro.
- NAO marque apenas uma historia pela metade.
- Prefira o ponto onde a história vira aplicacao para quem esta ouvindo.

Se for MÚSICA/LOUVOR:
- Priorize refrão, ponte, clímax emocional, repetição bonita, subida da música,
  parte cantável e frase forte de adoração.
- Não exija explicação ou aplicação como em pregação.
- O corte pode ser um trecho bonito, emocional e completo do refrão/ponte.

Para CADA momento, avalie:
- tipo_conteudo: pregacao ou musica.
- score (0-100): potencial viral. 90+ = excepcional, 80-89 = forte.
- emocao: a emocao dominante.
- funcao: ex: gancho, climax, declaracao, chamada, historia, ensino,
  palavra_direcionada, refrao, ponte, climax_musical.
- contexto_fechado: se o corte teria sentido sozinho, com começo compreensivel
  e fim sem deixar frase/ideia musical pela metade.

Responda APENAS em JSON valido, sem texto fora dele, no formato:
{"cortes":[{"trecho":"a frase exata","score":0-100,"titulo":"titulo curto",
"razao":"por que corta","emocao":"emocao dominante","funcao":"funcao narrativa",
"tipo_conteudo":"pregacao ou musica"}]}
Se nao houver momento bom no texto, responda {"cortes":[]}."""

PROMPT_CAPITULOS = """Voce recebe a transcricao COMPLETA de uma pregacao crista
com timestamps. Divida ela em capitulos tematicos (ex: Abertura, Leitura biblica,
Desenvolvimento, Ilustracao, Ministracao, Chamada).

Responda APENAS em JSON valido, no formato:
{"capitulos":[{"inicio_seg":0,"titulo":"titulo do capitulo","tema":"tema resumido"}]}
Use o segundo de inicio de cada capitulo. Maximo 8 capitulos."""

def analisar_com_ia(texto, t_ref):
    cl = cliente_openai()
    if cl is None:
        return None
    try:
        r = cl.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":PROMPT_CORTE},
                      {"role":"user","content":texto}],
            temperature=0.3,
            response_format={"type":"json_object"},
        )
        dados = json.loads(r.choices[0].message.content)
        return dados.get("cortes", [])
    except Exception as e:
        print(f"[ia] erro ({e}) -> usando heuristica nesta rodada")
        return None

def gerar_capitulos_ia():
    """Gera capitulos tematicos da pregacao inteira (chamado no fim do culto)."""
    cl = cliente_openai()
    if cl is None or not linhas:
        return []
    # monta a transcricao com timestamps em segundos
    txt = "\n".join(f"[{int(l['inicio'])}s] {l['texto']}" for l in linhas)
    try:
        r = cl.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":PROMPT_CAPITULOS},
                      {"role":"user","content":txt[:12000]}],
            temperature=0.3,
            response_format={"type":"json_object"},
        )
        caps = json.loads(r.choices[0].message.content).get("capitulos", [])
        for c in caps:
            c["timestamp"] = fmt(c.get("inicio_seg", 0))
        return caps
    except Exception as e:
        print(f"[ia] capitulos falharam: {e}")
        return []

# ----------------------------- TRANSCRICAO -----------------------------

pendencia_transcricao = ""

def _regex_replace_ci(txt, pattern, repl):
    return re.sub(pattern, repl, txt, flags=re.IGNORECASE)


def remover_vazamento_prompt_e_hallucinacao(txt):
    """Remove frases que são instruções internas do sistema e não fala/canto real.
    Isso evita aparecer no SRT coisas como: "Não troque palavras cantadas...".
    Também reduz loops curtos típicos de Whisper em áudio musical/ruidoso.
    """
    t = str(txt or "")
    if not t.strip():
        return t
    frases_banidas = [
        "não troque palavras cantadas",
        "nao troque palavras cantadas",
        "não troque palavras por palavras parecidas",
        "nao troque palavras por palavras parecidas",
        "transcrição fiel em português brasileiro",
        "transcricao fiel em portugues brasileiro",
        "o áudio é de uma pregação",
        "o audio e de uma pregacao",
        "pregação culto podcast ou aula bíblica",
        "pregacao culto podcast ou aula biblica",
        "culto podcast ou aula bíblica",
        "culto podcast ou aula biblica",
        "a pregação, culto, podcast ou aula bíblica",
        "a pregacao culto podcast ou aula biblica",
        "não traduza",
        "nao traduza",
        "não invente palavras",
        "nao invente palavras",
        "preserve o que a pessoa falou",
        "conteúdo atual:",
        "conteudo atual:",
        "reconheça refrões",
        "reconheca refroes",
        "nomes bíblicos",
        "nomes biblicos",
    ]
    partes = re.split(r"(?<=[.!?…])\s+|\n+", t)
    limpas = []
    for parte in partes:
        p = parte.strip()
        if not p:
            continue
        n = _norm(p)
        if any(b in n for b in frases_banidas):
            continue
        # Whisper às vezes descreve áudio musical como "Música" ao invés de transcrever canto.
        # Isso NÃO é letra e não deve entrar no SRT.
        palavras_norm = [w for w in re.findall(r"[a-zà-ÿ]+", n) if w]
        if palavras_norm and all(w in {"musica", "música", "music", "song", "louvor", "canto"} for w in palavras_norm) and len(palavras_norm) <= 4:
            continue
        if re.fullmatch(r"(?:m[uú]sica|music|song|louvor|canto)(?:[.,!?:;\s-]*(?:m[uú]sica|music|song|louvor|canto)){1,}.*", p, flags=re.IGNORECASE):
            continue
        # Remove loops absurdos de filler em chunk curto, mas não remove refrão real longo.
        palavras = [w for w in re.findall(r"[A-Za-zÀ-ÿ]+", n) if w]
        if len(palavras) >= 5:
            unicas = set(palavras)
            if len(unicas) <= 2 and len(palavras) >= 6:
                continue
        # Ex.: "E aí, aí, aí, aí..." normalmente é hallucinação/filler.
        if re.fullmatch(r"(?:e\s+)?(?:ai|aí)(?:[,\s.?!…-]*(?:ai|aí)){3,}.*", n):
            continue
        limpas.append(p)
    return " ".join(limpas).strip()

def corrigir_legenda_por_contexto(txt):
    """Correção leve de legenda antes de salvar/transmitir.
    Não muda timecode. Só corrige palavras que o Whisper costuma errar em pregação
    e nomes bíblicos pelo contexto, evitando SRT com 'a Braão', 'serba', etc.
    """
    if not _cfg_bool("corrigir_legenda_contexto", True):
        return str(txt or "")
    t = remover_vazamento_prompt_e_hallucinacao(str(txt or ""))
    if not t.strip():
        return t

    # Em modo música, não aplicar correções de pregação/bíblia que podem trocar letra cantada.
    # Música deve preservar o que foi cantado; a IA só usa isso para escolher refrão/clímax.
    tipo = str(config_usuario.get("tipo_conteudo", CONFIG.get("tipo_conteudo", "pregacao"))).lower()
    if tipo == "musica":
        t = re.sub(r"\s+", " ", t).strip()
        return t.replace(" ,", ",").replace(" .", ".").replace(" ?", "?").replace(" !", "!")

    # Correções leves por idioma do Modo Global.
    perfil = perfil_idioma_atual()
    for original, correto in (perfil.get("god_terms") or {}).items():
        try:
            t = _regex_replace_ci(t, rf"\b{re.escape(original)}\b", correto)
        except Exception:
            pass

    # As regras contextuais pesadas abaixo são específicas de português.
    if whisper_language_atual() not in ("pt", "pt-BR", "pt-PT"):
        t = re.sub(r"\s+", " ", t).strip()
        return t.replace(" ,", ",").replace(" .", ".").replace(" ?", "?").replace(" !", "!")

    # nomes bíblicos e termos comuns em pregações
    regras = [
        (r"\b(?:a|à)\s+braão\b", "Abraão"),
        (r"\bbraão\b", "Abraão"),
        (r"\babr[aã]o\b", "Abraão"),
        (r"\ba\s+br[aã]o\b", "Abraão"),
        (r"\bsar[aá]\b", "Sara"),
        (r"\bagar\b", "Agar"),
        (r"\bismael\b", "Ismael"),
        (r"\bno[eé]\b", "Noé"),
        (r"\barca de no[eé]\b", "Arca de Noé"),
        (r"\bserba\b", "serva"),
        (r"\bserva!", "serva!"),
        (r"\bo senhor\b", "o Senhor"),
        (r"\bdo senhor\b", "do Senhor"),
        (r"\bsenhor\b", "Senhor"),
        (r"\bdeus\b", "Deus"),
    ]
    for pat, rep in regras:
        t = _regex_replace_ci(t, pat, rep)

    # correções contextuais vistas no SRT enviado pelo usuário
    contextuais = [
        (r"Ela est[aá] sendo criada", "Ela está sendo guiada"),
        (r"est[aá] sendo criada", "está sendo guiada"),
        (r"garantia de ser andou", "garantia dizendo"),
        (r"garantia de ser ando", "garantia dizendo"),
        (r"ser andou", "dizendo"),
        (r"para Abraão, n[aã]o deu\s+para ela, mas deu para Abraão", "para Abraão; não deu para ela, mas deu para Abraão"),
        (r"filho dela, agora", "filho dela. Agora"),
        (r"falou isso com ela\? N[aã]o, mas falou\s+com Abraão", "falou isso com ela? Não, mas falou com Abraão"),
        (r"A Arca de Noé, que n[aã]o tinha\.", "A Arca de Noé, que não tinha..."),
        (r"O Timão\?", "O timão?"),
        (r"n[aã]o tinha Timão", "não tinha timão"),
    ]
    for pat, rep in contextuais:
        t = _regex_replace_ci(t, pat, rep)

    # limpeza final de pontuação e espaços
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace(" ,", ",").replace(" .", ".").replace(" ?", "?").replace(" !", "!")
    t = t.replace("..", ".") if "..." not in t else t
    return t

def limpar_texto_transcricao(txt):
    txt = re.sub(r"\s+", " ", (txt or "")).strip()
    # Corrige alguns artefatos comuns de chunks pequenos/ruidosos.
    txt = txt.replace(" ,", ",").replace(" .", ".").replace(" ?", "?").replace(" !", "!")
    txt = corrigir_legenda_por_contexto(txt)
    return txt

def dividir_linhas_continuas(txt, max_chars=360):
    """Quebra o bloco em linhas mais naturais, sem deixar cada segmento do ASR virar uma frase picotada."""
    txt = limpar_texto_transcricao(txt)
    if not txt:
        return []
    partes = re.split(r"(?<=[.!?…])\s+", txt)
    linhas_out = []
    atual = ""
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        if not atual:
            atual = parte
        elif len(atual) + 1 + len(parte) <= max_chars:
            atual += " " + parte
        else:
            linhas_out.append(atual.strip())
            atual = parte
    if atual:
        linhas_out.append(atual.strip())
    # Se o Whisper não pontuou, não fatiar em micro pedaços: só quebra se estiver enorme.
    final = []
    for linha in linhas_out:
        if len(linha) <= max_chars + 80:
            final.append(linha)
        else:
            palavras = linha.split()
            buf = ""
            for w in palavras:
                if len(buf) + len(w) + 1 > max_chars:
                    final.append(buf.strip())
                    buf = w
                else:
                    buf = (buf + " " + w).strip()
            if buf:
                final.append(buf.strip())
    return [x for x in final if len(x.strip()) >= 8]

def registrar_corte(texto, score, titulo, razao, t, emocao="", funcao="", origem="local"):
    nivel = "forte" if int(score) >= 90 else ("possivel" if int(score) >= 80 else "baixo")
    corte = {"tipo":"corte","texto":texto,"score":score,"titulo":titulo,
             "razao":razao,"emocao":emocao,"funcao":funcao,"origem":origem,
             "nivel": nivel,
             "tempo":round(t,1),"timestamp":fmt(t)}
    if bool(config_usuario.get("corte_exato_automatico", CONFIG.get("corte_exato_automatico", True))):
        corte = enriquecer_corte_com_janela(corte)
    cortes.append(corte)
    enviar(corte)
    if corte.get("inicio_exato") is not None and corte.get("fim_exato") is not None:
        print(f"[CORTE {corte.get('score', score)} {nivel.upper()}] {fmt(t)} - {titulo} | exato {fmt(corte['inicio_exato'])} até {fmt(corte['fim_exato'])} ({corte.get('duracao_exata')}s)")
    else:
        print(f"[CORTE {score} {nivel.upper()}] {fmt(t)} - {titulo} ({emocao})")
    # dispara clipe automatico se passar do limiar
    if score >= current_limiar():
        if corte_local_repetido(texto, t):
            print(f"[CORTE] duplicado/cooldown ignorado: {fmt(t)}")
            return
        antes = int(config_usuario.get("margem_antes_corte", CONFIG.get("margem_antes_corte", 10)))
        depois = int(config_usuario.get("margem_depois_corte", CONFIG.get("margem_depois_corte", 8)))
        ini_clip = corte.get("inicio_exato", max(0, t - antes))
        fim_clip = corte.get("fim_exato", t + depois)
        ini_clip, fim_clip, _dur_clip = normalizar_janela_corte(ini_clip, fim_clip, pico=t)
        salvar_clipe(titulo=titulo, timestamp=fmt(t), inicio=ini_clip,
                     fim=fim_clip, motivo=f"{origem}: {titulo}", texto=texto,
                     score=score, razao=razao, emocao=emocao, funcao=funcao, origem=origem)



def cortes_contextuais_score60(linhas_ref):
    """Fallback leve para a v81e-score60.
    Quando Gemini fica conservador demais, detecta blocos de assunto/história já úteis
    para post com rating 60+, sem exigir frase viral perfeita.
    """
    if not linhas_ref:
        return []
    try:
        limiar = current_limiar()
    except Exception:
        limiar = 60
    if limiar > 60:
        return []
    # Usa uma janela recente de até 90s, pulando boas-vindas/repetição bíblica quando possível.
    pares = [(float(tt or 0), (tx or '').strip()) for tt, tx in linhas_ref if (tx or '').strip()]
    if not pares:
        return []
    end_t = pares[-1][0]
    candidatos_inicio = []
    gatilhos_inicio = re.compile(r"\b(voc[eê] sabe|existem algumas pessoas|quem conhece|tem uma|tem um|eu lembro|sabe aquela|uma vez|quando eu|par[aá]bola|hist[oó]ria|olha|presta aten[cç][aã]o)\b", re.I)
    lixo_inicio = re.compile(r"\b(muito bom estar aqui|boa noite|receber todos|abra a sua b[ií]blia|lucas cap[ií]tulo|lucas 18|am[eé]m)\b", re.I)
    for idx, (tt, tx) in enumerate(pares):
        if end_t - tt > 90:
            continue
        if gatilhos_inicio.search(tx) and not lixo_inicio.search(tx):
            candidatos_inicio.append(idx)
    start_idx = candidatos_inicio[0] if candidatos_inicio else 0
    # Se começou com boas-vindas/bíblia, avança até o primeiro trecho mais narrativo.
    while start_idx < len(pares) - 1 and lixo_inicio.search(pares[start_idx][1]):
        start_idx += 1
    trecho_pares = pares[start_idx:]
    if not trecho_pares:
        return []
    start_t = trecho_pares[0][0]
    if end_t - start_t < 35:
        return []
    if end_t - start_t > 90:
        # Mantém os últimos 75-90s do mesmo assunto se a janela ficou grande demais.
        trecho_pares = [(tt, tx) for tt, tx in trecho_pares if end_t - tt <= 90]
        if not trecho_pares:
            return []
        start_t = trecho_pares[0][0]
    texto = " ".join(tx for _, tx in trecho_pares).strip()
    normal = _norm(texto)
    palavras = [p for p in normal.split() if p]
    if len(palavras) < 45:
        return []
    # Pontuação de assunto: não busca viral perfeito; busca post aproveitável.
    score = 55
    razoes = []
    if re.search(r"\b(quem conhece|voc[eê] sabe|existem algumas pessoas|tem gente|algumas pessoas)\b", normal):
        score += 8; razoes.append("gancho de identificação")
    if re.search(r"\b(persist|negoci|barganh|conseguir o que quer|talento natural)\b", normal):
        score += 10; razoes.append("assunto claro")
    if re.search(r"\b(eu lembro|quando eu|uma vez|historia|história|25 de mar[cç]o|s[aã]o paulo)\b", normal):
        score += 8; razoes.append("exemplo/história")
    if re.search(r"\b(n[aã]o importa|at[eé] conseguir|sempre|natural|interessante|justa)\b", normal):
        score += 5; razoes.append("tensão/curiosidade")
    if re.search(r"\b(muito bom estar aqui|abra a sua b[ií]blia|lucas 18)\b", normal) and not re.search(r"\b(persist|negoci|barganh|hist[oó]ria|quem conhece)\b", normal):
        return []
    score = min(78, max(60, score))
    if score < limiar:
        return []
    titulo = "Pessoas persistentes conseguem o que querem" if re.search(r"\b(persist|negoci|barganh)\b", normal) else titulo_local(texto, "curiosidade", "gancho")
    return [{
        "trecho": texto,
        "score": score,
        "titulo": titulo,
        "razao": ", ".join(razoes) if razoes else "assunto com contexto suficiente para post",
        "emocao": "curiosidade",
        "funcao": "gancho/contexto",
        "tempo": start_t,
    }]

def processar_analise_cortes(bloco_txt, t_ref, t_fim, linhas_ref=None):
    """Analisa cortes sem travar a transcrição ao vivo.

    v81b: quando Gemini está ativo, ele vira o diretor de edição.
    Ou seja: o detector local não dispara primeiro; o Gemini observa contexto maior
    e só libera corte quando entender que o raciocínio está fechado.
    Se Gemini falhar/limitar, o detector local entra como fallback.
    """
    linhas_ref = linhas_ref or []
    gemini_pronto = bool(config_usuario.get("gemini_enabled", CONFIG.get("gemini_enabled", False))) and bool(str(config_usuario.get("gemini_api_key", "") or "").strip())

    if gemini_pronto:
        try:
            cortes_ia = analisar_com_gemini(bloco_txt, t_ref, t_fim)
            # None = falha/sem internet/limite/chave ruim -> fallback local.
            # [] = Gemini analisou e decidiu não cortar/aguaradar -> não faz nada.
            if cortes_ia is not None:
                if len(cortes_ia) == 0 and current_limiar() <= 60:
                    # Gemini pode ser conservador em introduções de pregação.
                    # Com rating 60+, liberamos também blocos de assunto/história úteis para post.
                    cortes_ia = cortes_contextuais_score60(linhas_ref)
                if len(cortes_ia) > 0:
                    limite_ia = current_limiar()
                    for c in cortes_ia[:1]:
                        if int(c.get("score", 0) or 0) < limite_ia:
                            continue
                        t_corte = float(c.get("tempo", t_ref))
                        trecho_ref = (c.get("trecho") or "")[:18].lower()
                        if trecho_ref:
                            for (tt, tx) in linhas_ref:
                                if trecho_ref in tx.lower():
                                    t_corte = tt; break
                        registrar_corte(c.get("trecho", ""), int(c.get("score", 0)),
                                        c.get("titulo", "Momento"), c.get("razao", ""), t_corte,
                                        emocao=c.get("emocao", ""), funcao=c.get("funcao", ""), origem="gemini-score60")
                return
        except Exception as e:
            print(f"[gemini] analise falhou; usando fallback local: {e}")

    # v1.0.103: culto bilingue EN/PT. Se o contexto tem as duas línguas,
    # só libera corte com janela maior para preservar original + tradução.
    try:
        if contexto_bilingue_ativo(linhas_ref, bloco_txt):
            min_bi = float(config_usuario.get("bilingual_min_window_sec", CONFIG.get("bilingual_min_window_sec", 45)) or 45)
            max_bi = float(config_usuario.get("bilingual_max_window_sec", CONFIG.get("bilingual_max_window_sec", 90)) or 90)
            if linhas_ref:
                end_t_bi = float(linhas_ref[-1][0])
                pares_bi = [(float(tt), tx) for tt, tx in linhas_ref if end_t_bi - float(tt) <= max_bi]
                dur_bi = end_t_bi - float(pares_bi[0][0]) if pares_bi else 0
                if dur_bi >= min_bi:
                    texto_bi = " ".join(tx for _, tx in pares_bi).strip()
                    langs_bi = [detectar_idioma_linha_simples(tx)[0] for _, tx in pares_bi]
                    if "en" in langs_bi and "pt" in langs_bi and len(texto_bi.split()) >= 45:
                        score_bi = 84
                        if re.search(r"\b(Deus|Jesus|Senhor|God|Lord|presence|presen[cç]a|esp[ií]rito|spirit|father|pai|mesa|table|anointed|ungido)\b", texto_bi, re.I):
                            score_bi = 90
                        titulo_bi = titulo_local(texto_bi, "fé", "pregação traduzida")
                        registrar_corte(texto_bi, score_bi, titulo_bi, "pregação traduzida: preservou fala original em inglês + tradução em português", pares_bi[0][0], emocao="fé", funcao="contexto bilíngue", origem="bilingual-sermon")
                        return
    except Exception as e:
        print(f"[bilingue] analise ignorada: {e}")

    # Fallback / modo sem Gemini: detector local respeitando o modo escolhido.
    disparou_local = False
    try:
        modo_corte = corte_modo_atual()
        candidatos_locais = cortes_locais(linhas_ref)
        if candidatos_locais:
            limite = current_limiar()
            max_itens = 2 if modo_corte == "fast" else 1
            origem = "fast-local" if modo_corte == "fast" else "corte-seguro"
            for c in candidatos_locais[:max_itens]:
                if int(c.get("score", 0)) < limite:
                    continue
                titulo_c = c["titulo"]
                try:
                    if tipo_conteudo_por_modo(c.get("trecho", "")) == "musica":
                        titulo_c = fz107_titulo_louvor(c.get("trecho", ""), fallback=titulo_c)
                except Exception:
                    pass
                registrar_corte(c["trecho"], int(c["score"]), titulo_c, c["razao"], c["tempo"],
                                emocao=c.get("emocao", ""), funcao=c.get("funcao", ""), origem=origem)
                disparou_local = True
                if modo_corte == "standard":
                    break
    except Exception as e:
        print(f"[local] analise de cortes falhou: {e}")

    # v1.0.102: VPS removida. Sem refino remoto/DeepSeek antigo.
    # Gemini opcional continua disponível quando a pessoa coloca a chave no painel.

    if not disparou_local:
        pass

def worker_analise_cortes():
    while True:
        item = fila_analise.get()
        if item is None:
            continue
        try:
            processar_analise_cortes(*item)
        except Exception as e:
            print(f"[analise] worker falhou: {e}")


def whisper_local_disponivel():
    """v75: transcrição local oficial é MLX Whisper no Apple Silicon."""
    return bool(TEM_MLX)

def modo_transcricao_efetivo(modo):
    """v75: tudo roda local/offline com MLX Whisper.
    Se o painel antigo mandar hibrido/vps, aceitamos a escolha visual,
    mas o áudio nunca vai para VPS nem /transcribe.
    """
    modo = str(modo or 'local').lower().strip()
    if modo not in ('local', 'hibrido', 'vps'):
        modo = 'local'
    if modo in ('hibrido', 'vps'):
        print(f"[config] painel pediu {modo}, mas esta versão usa transcrição local/offline quando possível. Transcrevendo local.")
    if not (TEM_MLX or TEM_FASTER_WHISPER):
        print("[asr] Nenhum motor local instalado. No Windows instale faster-whisper; no Mac Apple Silicon instale mlx-whisper.")
    return 'local'

def cuda_disponivel_local():
    return False

def modelo_faster_atual():
    perfil = str(config_usuario.get("whisper_local_perfil", CONFIG.get("whisper_local_perfil", "leve"))).lower().strip()
    # Modelos compatíveis com faster-whisper no Windows.
    return "large-v3-turbo" if perfil == "pro" else "small"

def escolher_whisper_local_runtime():
    perfil = str(config_usuario.get("whisper_local_perfil", CONFIG.get("whisper_local_perfil", "leve"))).lower().strip()
    if perfil not in ("leve", "pro"):
        perfil = "leve"
    if platform.system().lower().startswith("win") or (not TEM_MLX and TEM_FASTER_WHISPER):
        modelo = modelo_faster_atual()
        return modelo, "faster-whisper", "cpu", perfil, False
    modelo = modelo_mlx_atual()
    return modelo, "mlx-metal", "metal", perfil, True

def loop_transcricao():
    global ultima_ia, texto_desde_ia, texto_contexto_ia, pendencia_transcricao
    modo_configurado = str(config_usuario.get("transcricao_modo", CONFIG.get("transcricao_modo", "hibrido"))).lower().strip()
    modo_transcricao = modo_transcricao_efetivo(modo_configurado)
    modelo = None

    def carregar_modelo_local():
        nonlocal modelo
        if modelo is None:
            if not (TEM_MLX or TEM_FASTER_WHISPER):
                raise RuntimeError("Nenhum motor local instalado. Windows: faster-whisper. Mac Apple Silicon: mlx-whisper.")
            nome_modelo, device, compute, perfil, tem_gpu = escolher_whisper_local_runtime()
            engine = "faster-whisper" if device == "faster-whisper" else "mlx-whisper"
            modelo = {"engine":engine, "modelo":nome_modelo, "perfil":perfil}
            if engine == "faster-whisper":
                print(f"[faster-local] perfil={perfil} modelo={nome_modelo} device=CPU compute=int8")
                print("[faster-local] pronto. Na primeira vez o modelo pode baixar do Hugging Face.")
            else:
                print(f"[mlx-local] perfil={perfil} modelo={nome_modelo} device=Apple Silicon/Metal")
                print("[mlx-local] pronto. Na primeira vez o modelo pode baixar do Hugging Face.")
        return modelo

    if modo_transcricao in ("vps", "hibrido"):
        print(f"[vps-asr] usando API: {_vps_url()}")
        print(f"[vps-ia] usando analise local DeepSeek: {_vps_url(config_usuario.get('whisper_vps_analyze_endpoint', CONFIG.get('whisper_vps_analyze_endpoint', '/analyze-text')))}")
        ok_vps, msg_vps = testar_vps_whisper()
        print(f"[vps-asr] health: {msg_vps}")
        modo_status = "hibrido" if modo_transcricao == "hibrido" else "vps"
        enviar_vps_status(ok=ok_vps, msg=("VPS online para analise/refino" if modo_transcricao == "hibrido" and ok_vps else msg_vps), modo=modo_status, url=_vps_url())
        if modo_transcricao == "vps":
            if config_usuario.get("vps_fallback_local", CONFIG.get("vps_fallback_local", False)):
                print("[vps-asr] fallback local ativo se a VPS falhar.")
            else:
                print("[vps-asr] modo VPS puro: MLX Whisper local NAO sera carregado.")
        if modo_transcricao == "hibrido":
            print("[tempo-real] modo hibrido: Whisper LOCAL transcreve ao vivo; VPS/Ollama refina texto/contexto e decide cortes. Audio nao vai para /transcribe.")
            carregar_modelo_local()
    else:
        enviar_vps_status(ok=True, msg=("Faster-Whisper local/offline" if platform.system().lower().startswith("win") else "MLX local/offline"), modo="local", url="")
        carregar_modelo_local()

    # v79: Padrao = MLX Corte Seguro; Turbo = OpenAI Realtime.
    transcricao_motor = str(config_usuario.get("transcricao_motor", CONFIG.get("transcricao_motor", "padrao"))).lower().strip()
    if transcricao_motor not in ("padrao", "turbo"):
        transcricao_motor = "padrao"
    if transcricao_motor == "turbo":
        bloco_segundos_atual = float(config_usuario.get("openai_realtime_commit_segundos", CONFIG.get("openai_realtime_commit_segundos", 12.0)))
        print(f"[turbo] OpenAI Realtime ativo: chunks de {bloco_segundos_atual:.1f}s delay={config_usuario.get('openai_realtime_delay','high')}")
    else:
        bloco_segundos_atual = float(config_usuario.get("bloco_segundos_corte_seguro", config_usuario.get("bloco_segundos", 15.0)))
        print(f"[padrao] janela interna de analise: blocos de {bloco_segundos_atual:.1f}s | corte final 35-90s")
    print(f"[modo] {clip_mode_atual()} | v1.0.108 worship-scoring-fix | corte={config_usuario.get('duracao_corte_min', CONFIG.get('duracao_corte_min'))}-{config_usuario.get('duracao_corte_max', CONFIG.get('duracao_corte_max'))}s | louvor={worship_intelligence_atual()} | bilingue={bilingual_context_atual()} | VPS desativada")
    amostras = int(CONFIG["sample_rate"]*bloco_segundos_atual)
    buffer = np.zeros((0,CONFIG["canais"]),dtype=np.float32)

    while True:
        try: chunk = fila_audio.get(timeout=1.0)
        except queue.Empty: continue

        if not gravando:
            buffer = np.zeros((0,CONFIG["canais"]),dtype=np.float32); continue
        if not bool(config_usuario.get("transcricao_ativa", CONFIG.get("transcricao_ativa", True))):
            buffer = np.zeros((0,CONFIG["canais"]),dtype=np.float32); continue

        buffer = np.concatenate([buffer,chunk],axis=0)
        if len(buffer) < amostras: continue

        bloco = buffer[:amostras]; buffer = buffer[amostras:]
        audio = preparar_audio_whisper(bloco[:,0])
        rms = float(np.sqrt(np.mean(np.square(audio)))) if len(audio) else 0.0
        volume_historico.append(rms)
        if len(volume_historico) > 60:
            del volume_historico[:-60]
        base_vol = float(np.median(volume_historico)) if volume_historico else rms
        pico_bloco = bool(rms > max(0.025, base_vol * 1.45))
        min_rms = float(config_usuario.get("audio_min_rms_para_status", CONFIG.get("audio_min_rms_para_status", 0.006)))
        if rms >= min_rms:
            enviar_audio_status(ok=True, rms=rms, msg="áudio entrando", origem="captura")
        else:
            enviar_audio_status(ok=False, rms=rms, msg="áudio muito baixo ou sem sinal. Confira OBS > Monitoring Device = BlackHole/VB-CABLE e Monitor and Output.", origem="captura")
            # Sem sinal real, nao envia silencio/ruido para o Whisper nem para VPS.
            # Isso evita spam de "texto invalido" e impede SRT/corte errado.
            continue
        t0 = (time.time()-bloco_segundos_atual) - inicio_gravacao
        if t0 < 0: t0 = 0
        feats_audio = audio_features_misto(audio, CONFIG.get("sample_rate", 16000))
        if worship_advanced_enabled(feats_audio):
            adv_feats = audio_features_musicais_avancadas(audio, CONFIG.get("sample_rate", 16000))
            if adv_feats.get("advanced"):
                feats_audio.update(adv_feats)
                try:
                    feats_audio["music_score"] = int(max(feats_audio.get("music_score", 0), min(100, feats_audio.get("music_score", 0) + adv_feats.get("crescendo_score", 0)*0.18 + adv_feats.get("melody_score", 0)*0.12)))
                except Exception:
                    pass
        modo_clip = clip_mode_atual()
        if modo_clip in ("mixed", "worship") and feats_audio.get("kind") in ("music", "speech_with_music"):
            print(f"[classifier] modo={modo_clip} tipo={feats_audio.get('kind')} fala={feats_audio.get('speech_score')} musica={feats_audio.get('music_score')} rms={feats_audio.get('rms'):.4f}")

        # Modo pode ser alterado pelo painel: padrao ou turbo.
        modo_configurado = str(config_usuario.get("transcricao_modo", CONFIG.get("transcricao_modo", "local"))).lower().strip()
        modo_transcricao = modo_transcricao_efetivo(modo_configurado)
        # VPS foi removida/desativada. Se o painel antigo pedir VPS/hibrido, força local.
        if modo_transcricao in ("vps", "hibrido"):
            print("[asr] VPS desativada nesta versao; usando transcricao local.")
            modo_transcricao = "local"
        transcricao_motor = str(config_usuario.get("transcricao_motor", CONFIG.get("transcricao_motor", "padrao"))).lower().strip()
        if transcricao_motor not in ("padrao", "turbo"):
            transcricao_motor = "padrao"
        if modo_transcricao == "vps" and modelo is not None and not config_usuario.get("vps_fallback_local", CONFIG.get("vps_fallback_local", False)):
            modelo = None
            gc.collect()
            print("[mlx-local] descarregado: modo VPS puro ativo.")
        origem_transcricao = modo_transcricao
        try:
            if transcricao_motor == "turbo":
                texto_bloco, segs_lista = transcrever_openai_realtime(audio)
                origem_transcricao = "openai-turbo"
            elif modo_transcricao == "vps" and config_usuario.get("vps_enviar_audio_ao_vivo", CONFIG.get("vps_enviar_audio_ao_vivo", False)):
                texto_vps, segmentos_vps = transcrever_vps(audio)
                enviar_vps_status(ok=True, msg="VPS respondeu", modo="vps", url=_vps_url())
                texto_bloco = limpar_texto_transcricao(limpar_tags_asr(texto_vps))
                if texto_whisper_invalido(texto_bloco, origem="vps"):
                    raise RuntimeError("VPS retornou texto invalido; bloqueado para nao gerar SRT/corte errado")
                # adapta segmentos da VPS para o mesmo formato usado pelo ASR local
                class SegObj:
                    def __init__(self, start, end, text):
                        self.start = float(start or 0)
                        self.end = float(end or bloco_segundos_atual)
                        self.text = text or ""
                segs_lista = []
                for sg in segmentos_vps:
                    if isinstance(sg, dict):
                        segs_lista.append(SegObj(sg.get('start', sg.get('inicio', 0)), sg.get('end', sg.get('fim', bloco_segundos_atual)), sg.get('text', sg.get('texto', ''))))
                if not segs_lista:
                    segs_lista = [SegObj(0, bloco_segundos_atual, texto_bloco)]
            else:
                texto_bloco, segs_lista = transcrever_local(carregar_modelo_local(), audio)
                origem_transcricao = "local"
        except Exception as e:
            erro = str(e)
            if transcricao_motor == "turbo":
                print(f"[turbo] falhou: {e}. Voltando para Padrao/MLX neste bloco.")
                try:
                    texto_bloco, segs_lista = transcrever_local(carregar_modelo_local(), audio)
                    origem_transcricao = "local-fallback-turbo"
                except Exception as e2:
                    print(f"[turbo] fallback MLX tambem falhou: {e2}")
                    continue
            elif modo_transcricao != "vps" and "texto invalido" in erro.lower():
                if clip_mode_atual() in ("mixed", "worship") and feats_audio.get("kind") in ("music", "speech_with_music"):
                    ok_music = registrar_corte_musical_audio(t0, bloco_segundos_atual, feats_audio, motivo="whisper-invalido-musica")
                    print(f"[asr] transcricao invalida, mas o bloco parece {feats_audio.get('kind')}; VPS desativada; motor musical {'gerou candidato' if ok_music else 'avaliou e aguardou'}. ({e})")
                    continue
                print(f"[asr] bloco descartado: transcricao invalida/sem fala PT-BR confiavel; VPS desativada. ({e})")
                continue
            elif "whisper" in erro.lower() or "mlx" in erro.lower() or "faster" in erro.lower():
                if clip_mode_atual() in ("mixed", "worship") and feats_audio.get("kind") in ("music", "speech_with_music"):
                    ok_music = registrar_corte_musical_audio(t0, bloco_segundos_atual, feats_audio, motivo="asr-falhou-musica")
                    print(f"[asr-local] ASR falhou, mas o bloco parece {feats_audio.get('kind')}; VPS desativada; motor musical {'gerou candidato' if ok_music else 'aguardou'}. ({e})")
                    continue
                # Sem VPS: nao tenta fallback remoto. Descarta o bloco e espera o proximo.
                print(f"[asr-local] bloco descartado: transcricao local falhou ou retornou texto invalido. VPS desativada. ({e})")
                continue
            else:
                print(f"[asr-local] falhou: {e}")
                continue
        if pendencia_transcricao:
            texto_bloco = limpar_texto_transcricao(pendencia_transcricao + " " + texto_bloco)
            pendencia_transcricao = ""

        # Segurança final: nada de lixo do ASR no painel, SRT ou gatilho de corte.
        if texto_whisper_invalido(texto_bloco, origem=origem_transcricao):
            if clip_mode_atual() in ("mixed", "worship") and feats_audio.get("kind") in ("music", "speech_with_music"):
                ok_music = registrar_corte_musical_audio(t0, bloco_segundos_atual, feats_audio, motivo="texto-invalido-pos-asr")
                print(f"[whisper-{origem_transcricao}] texto invalido; bloco tratado como {feats_audio.get('kind')}; VPS desativada; motor musical {'gerou candidato' if ok_music else 'aguardou'}")
                continue
            print(f"[whisper-{origem_transcricao}] bloco descartado: texto invalido/sem PT-BR confiavel")
            continue

        # No modo VPS tempo real, mostra a fala assim que chega para não parecer travado.
        # No modo local/refinado, ainda pode segurar frase incompleta para juntar melhor.
        segurar_incompleta = bool(config_usuario.get("segurar_frase_incompleta_ao_vivo", CONFIG.get("segurar_frase_incompleta_ao_vivo", False)))
        if segurar_incompleta and texto_bloco and not re.search(r"[.!?…]$", texto_bloco) and len(texto_bloco) < 260:
            pendencia_transcricao = texto_bloco
            texto_bloco = ""

        linhas_bloco = dividir_linhas_continuas(texto_bloco)
        if linhas_bloco:
            seg_start = segs_lista[0].start if segs_lista else 0
            seg_end = segs_lista[-1].end if segs_lista else bloco_segundos_atual
            dur = max(1.0, float(seg_end - seg_start))
            for idx, txt in enumerate(linhas_bloco):
                frac = idx / max(1, len(linhas_bloco))
                t = t0 + float(seg_start) + dur * frac
                linha = {"tipo":"linha","texto":txt,"inicio":round(t,2),
                         "fim":round(min(t0+seg_end, t + dur/max(1,len(linhas_bloco))),2),"timestamp":fmt(t),
                         "volume_rms":round(rms,4),"pico_voz":pico_bloco,"transcricao_origem":origem_transcricao,
                         "language_profile":perfil_id_atual()}
                if live_translation_ativa():
                    trad = traduzir_texto_ao_vivo(txt)
                    if trad:
                        linha["traducao"] = trad
                        linha["traducao_idioma"] = config_usuario.get("live_translation_target", "en")
                volume_picos[round(t,1)] = bool(pico_bloco or (clip_mode_atual()=="mixed" and feats_audio.get("kind")=="speech_with_music" and feats_audio.get("music_score",0)>=55))
                # limpa mapa antigo para não crescer indefinidamente
                for kk in list(volume_picos.keys()):
                    try:
                        if t - float(kk) > 900:
                            volume_picos.pop(kk, None)
                    except Exception:
                        pass
                linhas.append(linha); enviar(linha)
                texto_desde_ia.append((t,txt))
                texto_contexto_ia.append((t,txt))
                janela_ctx = float(config_usuario.get("gemini_janela_contexto_seg", CONFIG.get("gemini_janela_contexto_seg", 180.0)) or 180.0)
                texto_contexto_ia = [(tt,tx) for (tt,tx) in texto_contexto_ia if t - float(tt) <= janela_ctx]
                print(f"[{linha['timestamp']}] {txt}")

        # de tempos em tempos, manda o acumulado pra análise de cortes SEM travar a transcrição.
        # A análise da VPS/DeepSeek pode demorar; o texto ao vivo não pode ficar esperando isso.
        gemini_pronto = bool(config_usuario.get("gemini_enabled", CONFIG.get("gemini_enabled", False))) and bool(str(config_usuario.get("gemini_api_key", "") or "").strip())
        intervalo_analise = float(config_usuario.get("gemini_intervalo_seg", CONFIG.get("gemini_intervalo_seg", 60.0)) if gemini_pronto else config_usuario.get("intervalo_ia_seg", CONFIG.get("intervalo_ia_seg", 15)))
        if phrase_ai_ativa():
            # AI Boost opcional: analisa mais perto do tempo real. Pode consumir mais API.
            intervalo_analise = 4.0 if gemini_pronto else 6.0
        elif corte_modo_atual() == "standard":
            intervalo_analise = max(30.0 if gemini_pronto else 15.0, intervalo_analise)
        else:
            intervalo_analise = min(intervalo_analise, 8.0) if not gemini_pronto else max(30.0, intervalo_analise)
        intervalo_analise = ajustar_intervalo_por_culto_inteligente(intervalo_analise, feats_audio)
        base_analise = texto_contexto_ia if gemini_pronto else texto_desde_ia
        if time.time()-ultima_ia >= intervalo_analise and base_analise:
            bloco_txt = " ".join(x[1] for x in base_analise)
            t_ref = base_analise[0][0]
            t_fim = base_analise[-1][0] if base_analise else t_ref
            linhas_ref = list(base_analise)
            try:
                if bool(config_usuario.get("vps_analyze_async", CONFIG.get("vps_analyze_async", True))):
                    fila_analise.put((bloco_txt, t_ref, t_fim, linhas_ref))
                else:
                    processar_analise_cortes(bloco_txt, t_ref, t_fim, linhas_ref)
            except Exception as e:
                print(f"[analise] nao conseguiu enfileirar: {e}")
            texto_desde_ia = []; ultima_ia = time.time()

# ----------------------------- WEBSOCKET -----------------------------

def enviar(payload):
    if loop_principal is None: return
    msg = json.dumps(payload, ensure_ascii=False)
    for ws in list(clientes):
        asyncio.run_coroutine_threadsafe(_envia(ws,msg), loop_principal)

async def _envia(ws,msg):
    try: await ws.send(msg)
    except Exception: clientes.discard(ws)

async def handler(ws):
    global fonte_audio, preview_ativo, vertical_ativo, texto_desde_ia, texto_contexto_ia, pendencia_transcricao, ultima_ia
    clientes.add(ws)
    # manda estado inicial: chave, gravando, dispositivos de audio e o atual
    disp_atual = config_usuario.get("dispositivo_audio", CONFIG["dispositivo_audio"])
    await ws.send(json.dumps({"tipo":"status","gravando":gravando,
        "transcricao_ativa":bool(config_usuario.get("transcricao_ativa", CONFIG.get("transcricao_ativa", True))),
        "tem_chave":bool(config_usuario.get("openai_key")),
        "obs_conectado":obs_conectado,
        "plugin_installed": True,
        "plugin_version": PLUGIN_VERSION,
        "version": PLUGIN_VERSION}, ensure_ascii=False))
    await ws.send(json.dumps(plugin_version_payload(), ensure_ascii=False))
    await ws.send(json.dumps({"tipo":"dispositivos", "type":"audio_devices",
        "devices":[{"id": str(x.get("id")), "name": x.get("nome"), "device_id": str(x.get("id")), "device_name": x.get("nome"), "category": x.get("category"), "is_input": x.get("is_input"), "is_output": x.get("is_output"), "is_loopback": x.get("is_loopback"), "channels_in": x.get("channels_in"), "channels_out": x.get("channels_out"), "recommended": x.get("recommended", bool("blackhole" in str(x.get("nome","")).lower())), "default": x.get("padrao")} for x in listar_dispositivos_entrada()],
        "selected_device_id": None if disp_atual is None else str(disp_atual),
        "lista":listar_dispositivos_entrada(),
        "atual":disp_atual,
        "fonte":fonte_audio,
        "plugin_conectado":plugin_conectado,
        "blackhole_instalado": blackhole_instalado(),
        "sounddevice_ok": SOUNDDEVICE_OK,
        "sounddevice_erro": SOUNDDEVICE_ERROR}, ensure_ascii=False))
    await ws.send(json.dumps({"tipo":"audio_status", **audio_status_atual}, ensure_ascii=False))
    await ws.send(json.dumps({"tipo":"vps_status", **vps_status_atual}, ensure_ascii=False))
    await ws.send(json.dumps({"tipo":"config_extra",
        "language_profiles":perfis_idioma_para_painel(),
        "language_profile":perfil_id_atual(),
        "source_language":whisper_language_atual(),
        "output_language":output_language_atual(),
        "global_language_mode":config_usuario.get("global_language_mode", CONFIG.get("global_language_mode", "standard")),
        "live_translation_enabled":bool(config_usuario.get("live_translation_enabled", CONFIG.get("live_translation_enabled", False))),
        "live_translation_provider":config_usuario.get("live_translation_provider", CONFIG.get("live_translation_provider", "gemini")),
        "live_translation_target":config_usuario.get("live_translation_target", CONFIG.get("live_translation_target", "en")),
        "phrase_ai_enabled":bool(config_usuario.get("phrase_ai_enabled", CONFIG.get("phrase_ai_enabled", False))),
        "phrase_ai_provider":config_usuario.get("phrase_ai_provider", CONFIG.get("phrase_ai_provider", "gemini")),
        "proporcao":config_usuario.get("proporcao_corte", CONFIG["proporcao_corte"]),
        "vertical_ativo":vertical_ativo,
        "vertical_cena":config_usuario.get("vertical_cena", CONFIG["vertical_cena"]),
        "transcricao_modo":"local",
        "whisper_local_perfil":config_usuario.get("whisper_local_perfil", CONFIG.get("whisper_local_perfil", "leve")),
        "whisper_local_usuario_tem_gpu":config_usuario.get("whisper_local_usuario_tem_gpu", CONFIG.get("whisper_local_usuario_tem_gpu", False)),
        "whisper_vps_base_url":"",
        "whisper_vps_token":"",
        "transcription_engine":config_usuario.get("transcription_engine", "mlx-whisper"),
        "transcricao_motor":config_usuario.get("transcricao_motor", "padrao"),
        "transcricao_ativa":bool(config_usuario.get("transcricao_ativa", CONFIG.get("transcricao_ativa", True))),
        "openai_api_key":config_usuario.get("openai_api_key", config_usuario.get("openai_key", "")),
        "openai_realtime_model":config_usuario.get("openai_realtime_model", "gpt-realtime-whisper"),
        "openai_realtime_delay":config_usuario.get("openai_realtime_delay", "high"),
        "gemini_api_key":config_usuario.get("gemini_api_key", ""),
        "gemini_enabled":bool(config_usuario.get("gemini_enabled", False)),
        "gemini_model":config_usuario.get("gemini_model", "gemini-2.5-flash-lite"),
        "gemini_tutorial_url":config_usuario.get("gemini_tutorial_url", CONFIG.get("gemini_tutorial_url", "https://ai.google.dev/gemini-api/docs/api-key")),
        "corte_seguro":config_usuario.get("corte_seguro", True),
        "agrupar_assunto":config_usuario.get("agrupar_assunto", True),
        "duracao_corte_min":config_usuario.get("duracao_corte_min", CONFIG.get("duracao_corte_min", 35)),
        "duracao_corte_max":config_usuario.get("duracao_corte_max", CONFIG.get("duracao_corte_max", 90)),
        "corte_exato_automatico":config_usuario.get("corte_exato_automatico", CONFIG.get("corte_exato_automatico", True)),
        "clip_mode":clip_mode_atual(),
        "worship_intelligence":worship_intelligence_atual(),
        "performance_mode":performance_mode_atual(),
        "bilingual_context":bilingual_context_atual(),
        "manual_moment":manual_moment_atual(),
        "smart_cult_service_mode":bool(config_usuario.get("smart_cult_service_mode", CONFIG.get("smart_cult_service_mode", True))),
        "worship_advanced_available":bool(FZ_LIBROSA_OK or FZ_SCIPY_OK),
        "tipo_conteudo":config_usuario.get("tipo_conteudo", CONFIG.get("tipo_conteudo", "mixed")),
        "detectar_musica_pregacao":config_usuario.get("detectar_musica_pregacao", CONFIG.get("detectar_musica_pregacao", True)),
        "musica_usar_letra_online":config_usuario.get("musica_usar_letra_online", CONFIG.get("musica_usar_letra_online", True)),
        "ollama_internet_conectado":config_usuario.get("ollama_internet_conectado", CONFIG.get("ollama_internet_conectado", True)),
        "musica_confianca_minima_letra":config_usuario.get("musica_confianca_minima_letra", CONFIG.get("musica_confianca_minima_letra", 0.82))} , ensure_ascii=False))
    for l in linhas: await ws.send(json.dumps(l, ensure_ascii=False))
    for c in cortes: await ws.send(json.dumps(c, ensure_ascii=False))
    try:
        async for raw in ws:
            try: req = json.loads(raw)
            except Exception: continue
            acao = req.get("acao")
            tipo_msg = req.get("type") or req.get("tipo")
            if not acao:
                if tipo_msg in ("audio_devices_list", "get_audio_devices"):
                    acao = "listar_dispositivos"
                elif tipo_msg in ("audio_device_change", "audio_input_select", "audio_output_select", "set_audio_device", "select_audio_device", "audio_source_change"):
                    acao = "escolher_dispositivo"
                elif tipo_msg in ("transcription_start", "transcricao_start"):
                    acao = "toggle_transcricao"; req["ativa"] = True
                elif tipo_msg in ("transcription_stop", "transcricao_stop"):
                    acao = "toggle_transcricao"; req["ativa"] = False
                elif tipo_msg in ("settings", "set_settings", "clip_settings", "cult_service_settings"):
                    acao = "salvar_culto_inteligente_config"
            if acao == "get_plugin_version":
                await ws.send(json.dumps(plugin_version_payload(), ensure_ascii=False))
            elif acao == "version_status":
                await ws.send(json.dumps(framezero_version_status(fetch_remote=True), ensure_ascii=False))
            elif acao == "update_now":
                status_update = framezero_version_status(fetch_remote=True)
                if not status_update.get("update_available"):
                    await ws.send(json.dumps({"tipo":"update_now_result","type":"update_now_result","ok":True,"started":False,"message":"FrameZero já está atualizado.","version_status":status_update}, ensure_ascii=False))
                else:
                    started, msg = framezero_start_update_now()
                    await ws.send(json.dumps({"tipo":"update_now_result","type":"update_now_result","ok":bool(started),"started":bool(started),"message":msg,"version_status":status_update}, ensure_ascii=False))
            elif acao == "salvar_chave":
                chave = (req.get("chave") or "").strip()
                config_usuario["openai_key"] = chave
                config_usuario["openai_api_key"] = chave
                salvar_config_usuario({"openai_key": chave, "openai_api_key": chave})
                ok = bool(chave)
                await ws.send(json.dumps({"tipo":"chave_salva","tem_chave":ok}, ensure_ascii=False))
                print(f"[chave] {'salva' if ok else 'removida'}")
            elif acao == "listar_dispositivos":
                lista_audio = listar_dispositivos_entrada()
                atual_audio = config_usuario.get("dispositivo_audio", None)
                await ws.send(json.dumps({"tipo":"dispositivos", "type":"audio_devices",
                    "lista":lista_audio,
                    "devices":[{"id": str(x.get("id")), "name": x.get("nome"), "device_id": str(x.get("id")), "device_name": x.get("nome"), "category": x.get("category"), "is_input": x.get("is_input"), "is_output": x.get("is_output"), "is_loopback": x.get("is_loopback"), "channels_in": x.get("channels_in"), "channels_out": x.get("channels_out"), "recommended": x.get("recommended", bool("blackhole" in str(x.get("nome","")).lower())), "default": x.get("padrao")} for x in lista_audio],
                    "atual":atual_audio,
                    "selected_device_id": None if atual_audio is None else str(atual_audio),
                    "blackhole_instalado": blackhole_instalado(),
                    "sounddevice_ok": SOUNDDEVICE_OK,
                    "sounddevice_erro": SOUNDDEVICE_ERROR}, ensure_ascii=False))
            elif acao == "escolher_dispositivo":
                payload_req = req.get("payload") if isinstance(req.get("payload"), dict) else {}
                data_req = req.get("data") if isinstance(req.get("data"), dict) else {}
                d = (req.get("dispositivo") or req.get("device_id") or req.get("selected_device_id") or req.get("id") or req.get("audio_device_id") or req.get("value") or req.get("device") or req.get("audio_device") or payload_req.get("device_id") or payload_req.get("selected_device_id") or payload_req.get("id") or payload_req.get("value") or data_req.get("device_id") or data_req.get("selected_device_id") or data_req.get("id") or data_req.get("value"))
                device_name_req = (req.get("device_name") or req.get("nome") or req.get("name") or payload_req.get("device_name") or payload_req.get("name") or payload_req.get("nome") or data_req.get("device_name") or data_req.get("name") or data_req.get("nome"))
                is_output_req = bool(req.get("is_output") or req.get("is_loopback") or payload_req.get("is_output") or payload_req.get("is_loopback") or data_req.get("is_output") or data_req.get("is_loopback") or str(req.get("category") or payload_req.get("category") or data_req.get("category") or '').lower().startswith('sa'))
                d = _normalizar_audio_id(d, device_name=device_name_req, is_output=is_output_req, is_loopback=is_output_req)
                # escolher um dispositivo automaticamente volta a fonte pra "dispositivo"
                fonte_audio = "dispositivo"
                config_usuario["fonte_audio"] = "dispositivo"
                salvar_config_usuario({"fonte_audio": "dispositivo"})
                ok, nome = abrir_audio(d, device_name=device_name_req, is_output=is_output_req, is_loopback=is_output_req)
                if device_name_req:
                    nome = device_name_req if ok else nome
                obs_ok = False
                obs_msg = "OBS não solicitado"
                apply_obs = bool(req.get("apply_to_obs", req.get("obs", True)))
                if ok:
                    config_usuario["dispositivo_audio"] = d
                    salvar_config_usuario({"dispositivo_audio": d, "audio_input_device_id": d, "audio_input_device_name": nome})
                    if apply_obs:
                        obs_ok, obs_msg = aplicar_audio_no_obs(d, nome)
                await ws.send(json.dumps({"tipo":"dispositivo_ok", "type":"audio_device_changed", "ok":ok,
                    "nome":nome,"device_name":nome,"atual":d,"device_id": None if d is None else str(d), "category": "Saídas / Loopback" if is_output_req else "Entradas", "is_output": bool(is_output_req), "is_loopback": bool(is_output_req), "fonte":"dispositivo",
                    "obs_updated": bool(obs_ok), "obs_ok": bool(obs_ok), "obs_msg": obs_msg}, ensure_ascii=False))
            elif acao == "usar_blackhole_obs":
                if platform.system().lower() == "darwin":
                    bh_id, bh_nome = encontrar_blackhole()
                    if bh_id is None:
                        await ws.send(json.dumps({"tipo":"blackhole_ok","ok":False,
                            "msg":"BlackHole 2ch nao apareceu ainda. Reinicie o Mac depois da instalacao e abra o OBS de novo."}, ensure_ascii=False))
                    else:
                        fonte_audio = "dispositivo"
                        config_usuario["fonte_audio"] = "dispositivo"
                        config_usuario["dispositivo_audio"] = bh_id
                        salvar_config_usuario({"fonte_audio":"dispositivo","dispositivo_audio":bh_id})
                        ok, nome = abrir_audio(bh_id)
                        obs_ok, obs_msg = (False, "OBS não conectado")
                        if ok:
                            obs_ok, obs_msg = aplicar_audio_no_obs(bh_id, nome if ok else bh_nome)
                        await ws.send(json.dumps({"tipo":"blackhole_ok","ok":ok, "type":"audio_device_changed",
                            "nome":nome if ok else bh_nome,"device_name":nome if ok else bh_nome,"atual":bh_id,"device_id":str(bh_id),
                            "obs_updated": bool(obs_ok), "obs_msg": obs_msg,
                            "msg":"BlackHole selecionado e aplicado no OBS." if obs_ok else "BlackHole selecionado no Core. OBS não foi atualizado: " + str(obs_msg)}, ensure_ascii=False))
                else:
                    await ws.send(json.dumps({"tipo":"blackhole_ok","ok":False,
                        "msg":"BlackHole nao disponivel no Windows. Use VB-CABLE ou um dispositivo de entrada do Windows."}, ensure_ascii=False))
            elif acao == "usar_plugin_mixer":
                # legado: passa a usar o audio que vem do plugin obs-audio-to-websocket, se existir.
                fonte_audio = "plugin"
                config_usuario["fonte_audio"] = "plugin"
                salvar_config_usuario({"fonte_audio": "plugin"})
                # fecha o stream local do microfone, ja que nao sera usado
                if stream_audio is not None:
                    try: stream_audio.stop(); stream_audio.close()
                    except Exception: pass
                await ws.send(json.dumps({"tipo":"fonte_plugin_ok",
                    "conectado":plugin_conectado}, ensure_ascii=False))
                print("[audio] fonte = plugin do mixer do OBS")
            elif acao == "toggle_transcricao":
                atual = bool(config_usuario.get("transcricao_ativa", CONFIG.get("transcricao_ativa", True)))
                novo = bool(req.get("ativa")) if "ativa" in req else (not atual)
                config_usuario["transcricao_ativa"] = novo
                salvar_config_usuario({"transcricao_ativa": novo})
                if not novo:
                    texto_desde_ia = []
                    texto_contexto_ia = []
                    pendencia_transcricao = ""
                else:
                    ultima_ia = time.time()
                enviar({"tipo":"transcricao_toggle","ativa":novo,"gravando":gravando,
                        "motivo":"transcrição reativada" if novo else "transcrição desativada"})
                print(f"[transcricao] {'reativada' if novo else 'desativada'} pelo painel")
            elif acao == "clipar_agora":
                titulo = (req.get("titulo") or "momento-manual").strip()
                salvar_clipe(titulo=titulo, motivo="manual")
            elif acao == "salvar_senha_obs":
                s = (req.get("senha") or "").strip()
                p = req.get("porta")
                try: p = int(p) if p else CONFIG["obs_porta"]
                except Exception: p = CONFIG["obs_porta"]
                config_usuario["obs_senha"] = s
                config_usuario["obs_porta"] = p
                salvar_config_usuario({"obs_senha": s, "obs_porta": p})
                ok = iniciar_obs(senha_manual=s, porta_manual=p) if s else False
                await ws.send(json.dumps({"tipo":"obs_status","conectado":bool(ok),
                    "manual":True}, ensure_ascii=False))
                print(f"[obs] senha do painel: {'conectou' if ok else 'falhou'}")
            elif acao == "salvar_transcricao_config":
                # v79: seletor Padrao/Turbo. Padrao usa MLX local; Turbo usa OpenAI Realtime.
                modo_painel = str(req.get("transcricao") or req.get("modo_transcricao") or req.get("transcription_mode") or req.get("modo") or "local").lower().strip()
                motor = str(req.get("transcricao_motor") or req.get("motor_transcricao") or req.get("engine_modo") or req.get("modo_motor") or config_usuario.get("transcricao_motor", "padrao")).lower().strip()
                if motor not in ("padrao", "turbo"):
                    motor = "padrao"
                perfil = str(req.get("whisper_local_perfil") or config_usuario.get("whisper_local_perfil", CONFIG.get("whisper_local_perfil", "leve"))).lower().strip()
                if perfil not in ("leve", "pro"):
                    perfil = "leve"
                updates = {
                    "transcricao_modo": "local",
                    "transcricao_modo_painel": modo_painel,
                    "transcricao_motor": motor,
                    "motor_transcricao": motor,
                    "transcricao_ativa": bool(config_usuario.get("transcricao_ativa", CONFIG.get("transcricao_ativa", True))),
                    "openai_realtime_model": req.get("openai_realtime_model", "gpt-realtime-whisper"),
                    "openai_realtime_delay": req.get("openai_realtime_delay", "high"),
                    "openai_realtime_commit_segundos": float(req.get("openai_realtime_commit_segundos", 12.0) or 12.0),
                    "gemini_enabled": bool(req.get("gemini_enabled", config_usuario.get("gemini_enabled", False))),
                    # IMPORTANTE: nao apagar a chave Gemini salva quando o painel envia payload parcial
                    # ou quando o campo vem vazio durante conexao/reconfiguracao.
                    "gemini_api_key": (
                        str(req.get("gemini_api_key") or "").strip()
                        if str(req.get("gemini_api_key") or "").strip()
                        else str(config_usuario.get("gemini_api_key", "") or "").strip()
                    ),
                    "gemini_model": req.get("gemini_model", config_usuario.get("gemini_model", "gemini-2.5-flash-lite")),
                    "gemini_intervalo_seg": float(req.get("gemini_intervalo_seg", config_usuario.get("gemini_intervalo_seg", 60.0)) or 60.0),
                    "gemini_janela_contexto_seg": float(req.get("gemini_janela_contexto_seg", config_usuario.get("gemini_janela_contexto_seg", 180.0)) or 180.0),
                    "gemini_min_chars": int(req.get("gemini_min_chars", config_usuario.get("gemini_min_chars", 1200)) or 1200),
                    "gemini_max_chars": int(req.get("gemini_max_chars", config_usuario.get("gemini_max_chars", 9000)) or 9000),
                    "bloco_segundos_corte_seguro": float(req.get("bloco_segundos_corte_seguro", 15.0) or 15.0),
                    "overlap_segundos_corte_seguro": float(req.get("overlap_segundos_corte_seguro", 5.0) or 5.0),
                    "corte_seguro": True,
                    "agrupar_assunto": True,
                    "vps_enviar_audio_ao_vivo": False,
                    "hibrido_processa_local_refina_vps": False,
                    "hibrido_envia_audio_para_vps": False,
                    "hibrido_envia_texto_para_vps": False,
                    "vps_fallback_local": False,
                    "vps_analisar_com_ia_local": False,
                    "whisper_vps_url": "",
                    "whisper_vps_base_url": "",
                    "whisper_vps_endpoint": "",
                    "whisper_vps_analyze_endpoint": "",
                    "transcription_engine": "mlx-whisper",
                    "local_asr_engine": "mlx-whisper",
                    "forcar_ptbr_local": perfil_id_atual().startswith("pt"),
                    "idioma_whisper_local": whisper_language_atual(),
                    "whisper_local_language": whisper_language_atual(),
                    "whisper_local_task": "transcribe",
                    "correcao_contextual_ao_vivo": True,
                    "prompt_transcricao": "",
                    "whisper_local_perfil": perfil,
                    "whisper_local_usuario_tem_gpu": False,
                    "whisper_local_modelo_leve": "mlx-community/whisper-large-v3-turbo",
                    "whisper_local_modelo_pro": "mlx-community/whisper-large-v3",
                }
                chave_turbo = (req.get("openai_api_key") or req.get("openai_key") or req.get("chave_openai") or "").strip()
                if chave_turbo:
                    updates["openai_api_key"] = chave_turbo
                    updates["openai_key"] = chave_turbo
                config_usuario.update(updates)
                salvar_config_usuario(updates)
                enviar({"tipo":"config_ok", **updates})
                print(f"[config] motor={motor} padrao=mlx turbo=openai-realtime modelo={modelo_mlx_atual()} painel_pediu={modo_painel}")
            elif acao == "salvar_whisper_local_config":
                perfil = str(req.get("perfil") or req.get("whisper_local_perfil") or "leve").lower().strip()
                if perfil not in ("leve", "pro"):
                    perfil = "leve"
                tem_gpu = bool(req.get("tem_gpu", req.get("whisper_local_usuario_tem_gpu", False)))
                updates = {
                    "whisper_local_perfil": perfil,
                    "whisper_local_usuario_tem_gpu": tem_gpu,
                    "whisper_local_modelo_leve": "mlx-community/whisper-large-v3-turbo",
                    "whisper_local_modelo_pro": "mlx-community/whisper-large-v3",
                    "modelo_ao_vivo": "small",
                }
                config_usuario.update(updates)
                salvar_config_usuario(updates)
                enviar({"tipo":"whisper_local_config_ok", **updates})
                print(f"[config] whisper_local perfil={perfil} gpu={tem_gpu} modelo={updates['modelo_ao_vivo']}")
            elif acao == "salvar_global_language_config":
                # Regra oficial: somente UM idioma por vez. Se o painel mandar lista por engano, usa o primeiro item válido.
                _perfil_raw = req.get("language_profile") or req.get("idioma") or "pt-BR"
                if isinstance(_perfil_raw, (list, tuple)):
                    _perfil_raw = _perfil_raw[0] if _perfil_raw else "pt-BR"
                perfil = str(_perfil_raw).strip()
                if perfil not in LANGUAGE_PROFILES:
                    perfil = "pt-BR"
                modo_global = str(req.get("global_language_mode") or req.get("modo_global") or "standard").lower().strip()
                if modo_global not in ("standard", "ai_boost"):
                    modo_global = "standard"
                prof = LANGUAGE_PROFILES[perfil]
                updates = {
                    "language_profile": perfil,
                    "global_language_mode": modo_global,
                    "source_language": prof.get("whisper_language", "pt"),
                    "output_language": prof.get("output_language", perfil),
                    "whisper_local_language": prof.get("whisper_language", "pt"),
                    "idioma_whisper_local": prof.get("whisper_language", "pt"),
                    "forcar_ptbr_local": perfil.startswith("pt"),
                    "contexto_transcricao": prof.get("context", "Christian sermon"),
                    "prompt_transcricao": "",
                    "transcricao_modo": "local",
                }
                config_usuario.update(updates)
                salvar_config_usuario(updates)
                enviar({"tipo":"global_language_ok", **updates, "language_profiles":perfis_idioma_para_painel()})
                print(f"[global] idioma={perfil} whisper={updates['source_language']} modo={modo_global}")
            elif acao == "salvar_ai_boost_config":
                modo_global = "ai_boost" if bool(req.get("enabled", req.get("ai_boost_enabled", True))) else "standard"
                provider = str(req.get("provider") or req.get("live_translation_provider") or config_usuario.get("live_translation_provider", "gemini")).lower().strip()
                if provider not in ("gemini", "openai"):
                    provider = "gemini"
                target = str(req.get("target_language") or req.get("live_translation_target") or config_usuario.get("live_translation_target", "en")).strip() or "en"
                updates = {
                    "global_language_mode": modo_global,
                    "live_translation_enabled": bool(req.get("live_translation_enabled", False)),
                    "live_translation_provider": provider,
                    "live_translation_target": target,
                    "phrase_ai_enabled": bool(req.get("phrase_ai_enabled", False)),
                    "phrase_ai_provider": provider,
                }
                config_usuario.update(updates)
                salvar_config_usuario(updates)
                enviar({"tipo":"ai_boost_ok", **updates})
                print(f"[global-ai] modo={modo_global} provider={provider} traducao={updates['live_translation_enabled']} frase_ai={updates['phrase_ai_enabled']} target={target}")
            elif acao == "salvar_tipo_conteudo":
                tipo_conteudo = str(req.get("tipo_conteudo") or req.get("content_type") or "pregacao").lower().strip()
                if tipo_conteudo not in ("pregacao", "musica"):
                    tipo_conteudo = "pregacao"
                updates = {"tipo_conteudo": tipo_conteudo, "detectar_musica_pregacao": False}
                config_usuario.update(updates)
                salvar_config_usuario(updates)
                enviar({"tipo":"tipo_conteudo_ok", **updates})
                print(f"[config] tipo_conteudo={tipo_conteudo}")
            elif acao == "salvar_refino_letra_online":
                ativo = bool(req.get("ativo", True))
                conf = req.get("confianca_minima", config_usuario.get("musica_confianca_minima_letra", CONFIG.get("musica_confianca_minima_letra", 0.82)))
                try:
                    conf = float(conf)
                except Exception:
                    conf = 0.82
                conf = max(0.50, min(0.98, conf))
                updates = {
                    "ollama_internet_conectado": True,
                    "musica_usar_letra_online": ativo,
                    "musica_refino_online": ativo,
                    "musica_busca_letra_online": ativo,
                    "musica_nao_substituir_sem_confianca": True,
                    "musica_confianca_minima_letra": conf,
                    "musica_preservar_louvor_espontaneo": True,
                    "lyrics_reference_source": "web_via_ollama_vps",
                    "lyrics_reference_policy": "internet_sugere_audio_manda"
                }
                config_usuario.update(updates)
                salvar_config_usuario(updates)
                enviar({"tipo":"refino_letra_online_ok", **updates})
                print(f"[config] refino_letra_online={ativo} conf={conf}")
            elif acao == "salvar_gemini_config":
                # A chave da Google/Gemini deve permanecer salva mesmo quando o usuario
                # desliga o Gemini ou quando o painel reconecta e manda um payload sem chave.
                chave_recebida = req.get("gemini_api_key", req.get("chave_gemini", None))
                chave_atual = str(config_usuario.get("gemini_api_key", "") or "").strip()
                if chave_recebida is None:
                    chave = chave_atual
                else:
                    chave_nova = str(chave_recebida or "").strip()
                    chave = "" if bool(req.get("gemini_clear_key", False)) else (chave_nova or chave_atual)
                ativo = bool(req.get("gemini_enabled", config_usuario.get("gemini_enabled", bool(chave))))
                updates = {
                    "gemini_enabled": ativo,
                    "gemini_api_key": chave,
                    "gemini_model": req.get("gemini_model", config_usuario.get("gemini_model", "gemini-2.5-flash-lite")),
                    "gemini_intervalo_seg": float(req.get("gemini_intervalo_seg", config_usuario.get("gemini_intervalo_seg", 60.0)) or 60.0),
                    "gemini_janela_contexto_seg": float(req.get("gemini_janela_contexto_seg", config_usuario.get("gemini_janela_contexto_seg", 180.0)) or 180.0),
                    "gemini_min_chars": int(req.get("gemini_min_chars", config_usuario.get("gemini_min_chars", 1200)) or 1200),
                    "gemini_max_chars": int(req.get("gemini_max_chars", config_usuario.get("gemini_max_chars", 9000)) or 9000),
                    "gemini_tutorial_url": "https://ai.google.dev/gemini-api/docs/api-key",
                }
                config_usuario.update(updates)
                salvar_config_usuario(updates)
                enviar({"tipo":"gemini_config_ok", **updates})
                print(f"[gemini] enabled={ativo} model={updates['gemini_model']} intervalo={updates['gemini_intervalo_seg']}s")
            elif acao in ("salvar_clip_mode", "salvar_modo_conteudo"):
                modo = str(req.get("clip_mode", req.get("modo", req.get("tipo_conteudo", "mixed")))).lower().strip()
                aliases = {"misto":"mixed","culto":"mixed","culto_completo":"mixed","pregacao":"sermon","pregação":"sermon","pregacao_traduzida":"bilingual_sermon","pregação traduzida":"bilingual_sermon","bilingue":"bilingual_sermon","bilíngue":"bilingual_sermon","louvor":"worship","musica":"worship","música":"worship"}
                modo = aliases.get(modo, modo)
                if modo not in ("mixed", "sermon", "podcast", "worship", "bilingual_sermon"):
                    modo = "mixed"
                tipo_legado = "musica" if modo == "worship" else ("pregacao" if modo in ("sermon", "podcast", "bilingual_sermon") else "mixed")
                updates = {"clip_mode": modo, "modo_conteudo": modo, "tipo_conteudo": tipo_legado, "detectar_musica_pregacao": modo == "mixed"}
                config_usuario.update(updates)
                salvar_config_usuario(updates)
                enviar({"tipo":"clip_mode_ok", **updates})
                print(f"[config] clip_mode={modo} tipo_legado={tipo_legado}")
            elif acao == "salvar_culto_inteligente_config":
                modo = str(req.get("clip_mode", req.get("modo", config_usuario.get("clip_mode", "mixed")))).lower().strip()
                aliases = {"misto":"mixed","culto":"mixed","culto completo":"mixed","pregacao":"sermon","pregação":"sermon","pregacao_traduzida":"bilingual_sermon","pregação traduzida":"bilingual_sermon","bilingue":"bilingual_sermon","bilíngue":"bilingual_sermon","louvor":"worship","musica":"worship","música":"worship"}
                modo = aliases.get(modo, modo)
                if modo not in ("mixed", "sermon", "podcast", "worship", "bilingual_sermon"):
                    modo = "mixed"
                wi = str(req.get("worship_intelligence", req.get("inteligencia_louvor", config_usuario.get("worship_intelligence", "auto")))).lower().strip()
                wi = {"automatica":"auto","automática":"auto","desligada":"off","off":"off","sempre":"always","avancada":"always","avançada":"always","on":"always"}.get(wi, wi)
                if wi not in ("auto", "off", "always"):
                    wi = "auto"
                perf = str(req.get("performance_mode", req.get("desempenho", config_usuario.get("performance_mode", "auto")))).lower().strip()
                perf = {"leve":"light","avancado":"advanced","avançado":"advanced","automatico":"auto","automático":"auto"}.get(perf, perf)
                if perf not in ("auto", "light", "advanced"):
                    perf = "auto"
                bi = str(req.get("bilingual_context", req.get("contexto_bilingue", config_usuario.get("bilingual_context", "auto")))).lower().strip()
                bi = {"automatico":"auto","automático":"auto","ligado":"on","ativado":"on","desligado":"off"}.get(bi, bi)
                if bi not in ("auto", "on", "off"):
                    bi = "auto"
                moment = str(req.get("manual_moment", req.get("momento", config_usuario.get("manual_moment", "auto")))).lower().strip()
                moment = {"pregacao":"sermon","pregação":"sermon","louvor":"worship","adoracao":"worship","adoração":"worship","ministracao":"ministry","ministração":"ministry","apelo":"ministry"}.get(moment, moment)
                if moment not in ("auto", "sermon", "worship", "ministry"):
                    moment = "auto"
                try:
                    mn = int(req.get("duracao_corte_min", req.get("min", config_usuario.get("duracao_corte_min", 35))))
                    mx = int(req.get("duracao_corte_max", req.get("max", config_usuario.get("duracao_corte_max", 90))))
                except Exception:
                    mn, mx = 35, 90
                mn = max(35, min(300, mn)); mx = max(mn, min(300, mx))
                tipo_legado = "musica" if modo == "worship" else ("pregacao" if modo in ("sermon", "podcast", "bilingual_sermon") else "mixed")
                updates = {"clip_mode": modo, "modo_conteudo": modo, "tipo_conteudo": tipo_legado, "detectar_musica_pregacao": modo == "mixed",
                           "worship_intelligence": wi, "performance_mode": perf, "bilingual_context": bi, "manual_moment": moment,
                           "smart_cult_service_mode": bool(req.get("smart_cult_service_mode", req.get("culto_inteligente", True))),
                           "duracao_corte_min": mn, "duracao_corte_max": mx,
                           "bilingual_preserve_original_translation": True}
                config_usuario.update(updates); salvar_config_usuario(updates)
                enviar({"tipo":"culto_inteligente_ok", **updates, "worship_advanced_available": bool(FZ_LIBROSA_OK or FZ_SCIPY_OK)})
                print(f"[config] culto_inteligente modo={modo} louvor={wi} bilingue={bi} momento={moment} dur={mn}-{mx}s")
            elif acao == "salvar_corte_config":
                modo = str(req.get("corte_modo", req.get("modo_corte", "standard"))).lower().strip()
                if modo not in ("fast", "standard"):
                    modo = "standard"
                if modo == "fast":
                    updates = {
                        "corte_modo": "fast",
                        "limiar_corte": int(req.get("limiar_corte", 60)),
                        "cooldown_corte_seg": int(req.get("cooldown_corte_segundos", req.get("cooldown_corte_seg", 18))),
                        "intervalo_ia_seg": float(req.get("janela_analise_segundos", 8)),
                        "duracao_corte_min": 35,
                        "duracao_corte_max": 90,
                        "margem_antes_corte": 20,
                        "margem_depois_corte": 12,
                        "corte_seguro_agrupar_assunto": False,
                    }
                else:
                    # Corte Seguro: menos cortes, mais contexto, sem score inflado e sem picotar assunto.
                    updates = {
                        "corte_modo": "standard",
                        "limiar_corte": max(60, int(req.get("limiar_corte", 60))),
                        "cooldown_corte_seg": max(55, int(req.get("cooldown_corte_segundos", req.get("cooldown_corte_seg", 60)))),
                        "intervalo_ia_seg": max(15.0, float(req.get("janela_analise_segundos", 30))),
                        "duracao_corte_min": 35,
                        "duracao_corte_max": 90,
                        "margem_antes_corte": 22,
                        "margem_depois_corte": 14,
                        "corte_seguro_agrupar_assunto": True,
                    }
                config_usuario.update(updates)
                salvar_config_usuario(updates)
                enviar({"tipo":"config_ok", **updates})
                print(f"[config] modo corte={modo} limiar={updates['limiar_corte']} cooldown={updates['cooldown_corte_seg']} intervalo={updates['intervalo_ia_seg']} dur={updates['duracao_corte_min']}-{updates['duracao_corte_max']}")
            elif acao == "salvar_duracao_cortes":
                try:
                    mn = int(req.get("min", 35))
                    mx = int(req.get("max", 90))
                except Exception:
                    mn, mx = 35, 90
                mn = max(35, min(300, mn))
                mx = max(35, min(300, mx))
                if mx < mn:
                    mx = mn
                # Margens proporcionais para o clipe automático e cortes finais.
                antes = max(3, min(20, int(mn * 0.65)))
                depois = max(3, min(20, int(mn * 0.45)))
                updates = {"duracao_corte_min": mn, "duracao_corte_max": mx,
                           "margem_antes_corte": antes, "margem_depois_corte": depois}
                config_usuario.update(updates)
                salvar_config_usuario(updates)
                enviar({"tipo":"duracao_ok", **updates})
                print(f"[config] duracao cortes min={mn}s max={mx}s")
            elif acao == "preview":
                await ws.send(json.dumps({"tipo":"preview_status","ativo":False,"msg":"Preview do corte removido"}, ensure_ascii=False))
            elif acao == "vertical_mode":
                ligar = bool(req.get("ligar"))
                ok, msg = configurar_cena_vertical(ligar)
                await ws.send(json.dumps({"tipo":"vertical_status","ok":ok,
                    "ligado":vertical_ativo,"msg":msg,
                    "cena":config_usuario.get("vertical_cena", CONFIG["vertical_cena"])} , ensure_ascii=False))
            elif acao == "tracking":
                ligar = bool(req.get("ligar"))
                ok, msg = ligar_tracking(ligar)
                config_usuario["tracking"] = ligar if ok else config_usuario.get("tracking", False)
                if ok: salvar_config_usuario({"tracking": ligar})
                await ws.send(json.dumps({"tipo":"tracking_status","ok":ok,
                    "ligado":(ligar if ok else False),"msg":msg}, ensure_ascii=False))
            elif acao == "escolher_proporcao":
                p = req.get("proporcao", "9:16")
                if p in ("9:16","1:1","16:9","original"):
                    config_usuario["proporcao_corte"] = p
                    salvar_config_usuario({"proporcao_corte": p})
                    await ws.send(json.dumps({"tipo":"proporcao_ok","proporcao":p}, ensure_ascii=False))
                    print(f"[proporcao] cortes em {p}")
            elif acao == "recomecar":
                resetar_sessao()
            elif acao == "gerar_cortes":
                threading.Thread(target=gerar_cortes_precisos, daemon=True).start()
            elif acao == "gerar_capitulos":
                def _caps():
                    caps = gerar_capitulos_ia()
                    enviar({"tipo":"capitulos","lista":caps})
                threading.Thread(target=_caps, daemon=True).start()
            elif acao == "exportar_srt":
                await ws.send(json.dumps({"tipo":"arquivo_srt","conteudo":gerar_srt()}, ensure_ascii=False))
            elif acao == "exportar_txt":
                await ws.send(json.dumps({"tipo":"arquivo_txt","conteudo":gerar_txt()}, ensure_ascii=False))
    finally:
        clientes.discard(ws)

# ----------------------------- CORTES PRECISOS (pos-culto) -----------------------------

def caminho_ffmpeg():
    """Acha o ffmpeg: primeiro no PATH do sistema, depois na pasta do projeto
    (onde o instalador Windows pode ter colocado)."""
    no_path = shutil.which("ffmpeg")
    if no_path:
        return no_path
    local = PASTA / "ffmpeg" / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if local.exists():
        return str(local)
    return None

def caminho_ffprobe():
    """Acha o ffprobe para ler a duração/timecode real dos arquivos do OBS."""
    no_path = shutil.which("ffprobe")
    if no_path:
        return no_path
    local = PASTA / "ffmpeg" / "bin" / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if local.exists():
        return str(local)
    return None

def duracao_video_seg(caminho):
    """Retorna duração real do arquivo em segundos usando ffprobe.
    Isso é essencial para recortar Replay Buffer: o arquivo bruto pode ter 120s,
    mas o corte final precisa respeitar o timecode do SRT/transcrição.
    """
    ffprobe = caminho_ffprobe()
    if not ffprobe or not caminho or not os.path.exists(caminho):
        return None
    try:
        import subprocess
        r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", caminho],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return float((r.stdout or "").strip())
    except Exception:
        pass
    return None

def filtro_proporcao(prop):
    """
    Devolve o filtro -vf do ffmpeg pra reenquadrar o clipe na proporcao pedida.
    Faz crop central a partir de um video 1920x1080. 'original' nao reenquadra.
      9:16  -> 1080x1920 (Reels/Shorts/TikTok), crop central na largura
      1:1   -> 1080x1080 (feed quadrado), crop central
      16:9  -> mantem widescreen (so garante 1920x1080)
    """
    prop = str(prop or "original").replace("x", ":")
    if prop == "9:16":
        # recorta a faixa central vertical e escala pra 1080x1920
        return "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"
    if prop == "1:1":
        return "crop=ih:ih:(iw-ih)/2:0,scale=1080:1080"
    if prop == "16:9":
        return "scale=1920:1080"
    return ""  # original: sem reframe

def versoes_corte_config():
    """Versões que o FrameZero deve entregar automaticamente para cada corte."""
    if bool(config_usuario.get("gerar_versoes_automaticas", CONFIG.get("gerar_versoes_automaticas", True))):
        bruto = config_usuario.get("versoes_corte_automaticas", CONFIG.get("versoes_corte_automaticas", ["16x9", "9x16"]))
        if isinstance(bruto, str):
            bruto = [x.strip() for x in bruto.split(",") if x.strip()]
        saida = []
        for p in bruto or []:
            p = str(p).replace("x", ":")
            if p in ("16:9", "9:16", "1:1", "original") and p not in saida:
                saida.append(p)
        return saida or ["16:9", "9:16"]
    p = str(config_usuario.get("proporcao_corte", CONFIG.get("proporcao_corte", "original"))).replace("x", ":")
    return [p if p in ("16:9", "9:16", "1:1", "original") else "original"]

def pasta_formato_corte(pasta_corte, prop):
    """v81j: mantém todas as versões dentro da mesma pasta do título, sem subpastas 16x9/9x16."""
    os.makedirs(pasta_corte, exist_ok=True)
    return pasta_corte

def executar_ffmpeg_corte(entrada, saida, inicio=None, duracao=None, prop="original", timeout=300):
    ffmpeg = caminho_ffmpeg()
    if not ffmpeg:
        return False
    try:
        import subprocess
        cmd = [ffmpeg, "-y"]
        if inicio is not None:
            cmd += ["-ss", f"{float(inicio):.2f}"]
        cmd += ["-i", entrada]
        if duracao is not None:
            cmd += ["-t", f"{float(duracao):.2f}"]
        vf = filtro_proporcao(prop)
        if vf:
            cmd += ["-vf", vf]
        cmd += ["-c:v", "libx264", "-c:a", "aac", "-preset", "veryfast", "-movflags", "+faststart", saida]
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        ok = (r.returncode == 0 and os.path.exists(saida) and os.path.getsize(saida) > 0)
        if not ok:
            err = (r.stderr or b"").decode("utf-8", "ignore")[-400:]
            print(f"[ffmpeg] falhou gerando {saida}: {err}")
        return ok
    except Exception as e:
        print(f"[ffmpeg] erro gerando {saida}: {e}")
        return False

def gerar_versoes_do_corte(entrada, pasta_corte, c, inicio=None, duracao=None, timeout=300):
    """Gera automaticamente 16x9 e 9x16 na mesma pasta do título, com o título no nome do arquivo."""
    videos = {}
    os.makedirs(pasta_corte, exist_ok=True)
    for prop in versoes_corte_config():
        prop_label = str(prop).replace(":", "x")
        saida = os.path.join(pasta_corte, nome_video_corte(c, prop_label))
        if executar_ffmpeg_corte(entrada, saida, inicio=inicio, duracao=duracao, prop=prop, timeout=timeout):
            videos[prop_label] = saida
    return videos


def gerar_cortes_fallback_local(max_cortes=12):
    """Quando nenhum momento foi marcado ao vivo, cria candidatos a partir da transcrição.
    Isso evita o erro 'Nenhum momento para gerar' no fim do culto.
    Não dispara replay buffer; só prepara a lista para o corte preciso da gravação completa.
    """
    candidatos = []
    if not linhas:
        return []
    # janelas de 1, 2 e 3 linhas para pegar frases completas.
    for i in range(len(linhas)):
        for janela in (1, 2, 3):
            bloco = linhas[i:i+janela]
            if not bloco:
                continue
            texto = " ".join((x.get("texto") or "").strip() for x in bloco).strip()
            if len(texto.split()) < 5:
                continue
            s, raz, emocao, funcao = score_heuristico(texto)
            if any(x.get("pico_voz") for x in bloco):
                s = min(100, s + 12)
                raz = (raz or []) + ["pico de voz/presença"]
                if emocao == "fé":
                    emocao = "presença"
            # guarda tudo com score razoável; se nada bater, a gente usa os melhores abaixo.
            candidatos.append({
                "tipo":"corte",
                "texto":texto,
                "score":int(s),
                "titulo":titulo_local(texto, emocao, funcao),
                "razao":", ".join(raz) if raz else "gerado no fim pela análise local",
                "emocao":emocao,
                "funcao":funcao,
                "origem":"fallback_local",
                "tempo":round(float(bloco[0].get("inicio", 0)), 1),
                "timestamp":fmt(float(bloco[0].get("inicio", 0))),
            })
    candidatos.sort(key=lambda c: c["score"], reverse=True)
    escolhidos = []
    vistos = []
    for c in candidatos:
        normal = _norm(c["texto"])[:120]
        if not normal:
            continue
        # evita cortes muito próximos ou texto praticamente repetido.
        if any(abs(c["tempo"] - e["tempo"]) < 35 for e in escolhidos):
            continue
        if any(normal in v or v in normal for v in vistos):
            continue
        escolhidos.append(c); vistos.append(normal)
        if len(escolhidos) >= max_cortes:
            break
    return escolhidos


def texto_linhas(bloco):
    return " ".join((x.get("texto") or "").strip() for x in bloco).strip()

def segundos_linha_inicio(l):
    try:
        return float(l.get("inicio", 0) or 0)
    except Exception:
        return 0.0

def segundos_linha_fim(l):
    try:
        return float(l.get("fim", l.get("inicio", 0)) or 0)
    except Exception:
        return segundos_linha_inicio(l)


# ----------------------------- FECHAMENTO DE CONTEXTO DO CORTE -----------------------------

_TERMINADORES_FALA = re.compile(r"[.!?…]$|(\bam[eé]m\b|\bentendeu\b|\bgl[oó]ria a deus\b|\baleluia\b)$", re.I)
_INICIO_NOVA_IDEIA = re.compile(r"^(agora|ent[aã]o|e ent[aã]o|mas|s[oó] que|por[eé]m|quando|voc[eê]|voce|olha|escuta|presta aten[cç][aã]o|nessa noite|hoje)\b", re.I)
_FINAL_INCOMPLETO = re.compile(
    r"(\b(e|mas|porque|por que|que|quando|ent[aã]o|s[oó] que|pra|para|com|de|da|do|das|dos|em|no|na|nos|nas|pelo|pela|pelos|pelas|voc[eê]|voce|ela|ele|eu|n[oã]s|essa|esse|isso|aquela|aquele|est[aá]|estava|ser[aá]|foi)\s*)$|[,:;]$|\.{3}$|…$",
    re.I,
)

def _txt_linha(i):
    try:
        return (linhas[i].get("texto") or "").strip()
    except Exception:
        return ""

def linha_tem_fechamento(i):
    """True quando a linha termina como fechamento natural de fala/ideia."""
    t = _txt_linha(i)
    if not t:
        return False
    if _TERMINADORES_FALA.search(t.strip()):
        return True
    # Algumas transcrições não trazem pontuação; aceitamos fechamentos típicos de pregação.
    if re.search(r"\b(deus|senhor|jesus|esp[ií]rito santo|prop[oó]sito|promessa|dire[cç][aã]o|rumo|vit[oó]ria|milagre)\s*$", t, re.I):
        return True
    return False

def texto_parece_incompleto(txt):
    """Detecta legenda/corte terminando no meio da ideia."""
    t = re.sub(r"\s+", " ", str(txt or "")).strip()
    if not t:
        return True
    if _TERMINADORES_FALA.search(t):
        return False
    if _FINAL_INCOMPLETO.search(t):
        return True
    ult = t.split()[-1].lower().strip(".,!?;:…")
    return ult in {"que","quando","porque","mas","então","pra","para","com","de","da","do","em","pela","pelo","você","voce","está","esta"}


_HISTORIA_PREGA = re.compile(
    r"\b(era|havia|tinha|estava|estavam|aconteceu|acontecia|chegou|chegaram|foi|foram|andou|vinha|veio|saiu|entrou|passou|encontrou|disse|perguntou|respondeu|homem|mulher|filho|filha|pai|m[aã]e|casa|cidade|deserto|barco|mar|tempestade|disc[ií]pulo|disc[ií]pulos|abra[aã]o|sara|agar|ismael|no[eé]|davi|jos[eé]|mois[eé]s|pedro|paulo|jesus)\b",
    re.I,
)
_PALAVRA_DIRECIONADA = re.compile(
    r"\b(voc[eê]|voce|sua|seu|teu|tua|hoje|agora|nesta noite|nessa noite|essa palavra|a palavra|receba|escuta|olha|presta aten[cç][aã]o|entenda|aprenda|guarde isso|isso significa|isso quer dizer|deus est[aá]|o senhor est[aá]|deus vai|deus quer|deus pode|deus n[aã]o|o senhor vai|o senhor quer|o senhor n[aã]o|o senhor pode|a sua vida|na sua casa|na sua fam[ií]lia|no seu minist[eé]rio|no seu chamado|no seu prop[oó]sito|voc[eê] precisa|voc[eê] n[aã]o pode|n[aã]o pare|n[aã]o desista|levanta|volta|creia|confia|confie|posicione|se posiciona)\b",
    re.I,
)
_FECHAMENTO_DIRECIONADO = re.compile(
    r"\b(am[eé]m|receba|gl[oó]ria a deus|aleluia|em nome de jesus|na sua vida|na sua casa|na sua fam[ií]lia|no seu minist[eé]rio|no seu chamado|no seu prop[oó]sito|deus vai fazer|o senhor vai fazer|deus est[aá] fazendo|o senhor est[aá] fazendo|n[aã]o acabou|vai acontecer|essa palavra [eé] pra voc[eê]|isso [eé] pra voc[eê])\b[.!?…]*$",
    re.I,
)
_INICIO_MEIO_HISTORIA = re.compile(r"^(ele|ela|eles|elas|aquele|aquela|isso|essa|esse|e|a[ií]|ent[aã]o|mas)\b", re.I)

def bloco_tem_historia(bloco):
    txt = texto_linhas(bloco)
    return bool(_HISTORIA_PREGA.search(txt))

def bloco_tem_palavra_direcionada(bloco):
    txt = texto_linhas(bloco)
    return bool(_PALAVRA_DIRECIONADA.search(txt))

def linha_tem_palavra_direcionada(i):
    return bool(_PALAVRA_DIRECIONADA.search(_txt_linha(i)))

def bloco_tem_fechamento_direcionado(bloco):
    txt = texto_linhas(bloco)
    return bool(_FECHAMENTO_DIRECIONADO.search(txt)) or (bloco_tem_palavra_direcionada(bloco) and not texto_parece_incompleto(txt))

def historia_sem_aplicacao(bloco):
    if not bool(config_usuario.get("historia_precisa_aplicacao", CONFIG.get("historia_precisa_aplicacao", True))):
        return False
    return bloco_tem_historia(bloco) and not bloco_tem_palavra_direcionada(bloco)

def ajustar_para_palavra_direcionada(a, b, idx_pico=None, dur_max=None):
    """Quando o trecho é história, tenta incluir a aplicação/palavra direcionada.

    Isso evita corte bonito visualmente mas sem sentido: a história começa, cria tensão,
    e o vídeo acaba antes da mensagem para o público.
    """
    if not bool(config_usuario.get("modo_contexto_pregacao", CONFIG.get("modo_contexto_pregacao", True))):
        return a, b, False
    if not linhas:
        return a, b, False
    dur_min, mx_cfg = duracao_cortes_config()
    dur_max = float(dur_max or mx_cfg)
    a = max(0, int(a)); b = min(len(linhas)-1, int(b))
    idx_pico = b if idx_pico is None else int(idx_pico)
    idx_pico = max(a, min(idx_pico, len(linhas)-1))

    def dur(aa, bb):
        return segundos_linha_fim(linhas[bb]) - segundos_linha_inicio(linhas[aa])
    def caberia(aa, bb):
        return dur(aa, bb) <= dur_max + 0.02

    bloco = linhas[a:b+1]
    if not bloco_tem_historia(bloco) or bloco_tem_palavra_direcionada(bloco):
        return a, b, False

    limite = min(len(linhas)-1, b + int(config_usuario.get("max_linhas_busca_aplicacao", CONFIG.get("max_linhas_busca_aplicacao", 18))))
    melhor = None
    viu_aplicacao = False
    for nb in range(b + 1, limite + 1):
        if linha_tem_palavra_direcionada(nb):
            viu_aplicacao = True
        bloco_tmp = linhas[a:nb+1]
        if not viu_aplicacao and not bloco_tem_palavra_direcionada(bloco_tmp):
            continue
        # depois que achou aplicação, tenta parar em fechamento natural.
        if not (linha_tem_fechamento(nb) or bloco_tem_fechamento_direcionado(bloco_tmp)) and nb < limite:
            continue
        aa = a
        while aa < idx_pico and not caberia(aa, nb):
            aa += 1
        if aa <= idx_pico <= nb and caberia(aa, nb):
            bloco_final = linhas[aa:nb+1]
            if bloco_tem_palavra_direcionada(bloco_final):
                melhor = (aa, nb, False)
                if bloco_tem_fechamento_direcionado(bloco_final):
                    return aa, nb, False
    if melhor:
        return melhor
    return a, b, True

def ajustar_fim_para_fechamento(a, b, idx_pico=None, dur_max=None):
    """Ajusta a janela para não terminar no meio da conclusão do contexto.

    Primeiro tenta estender o fim até fechamento natural.
    Se passar do máximo configurado, move o início para frente e preserva o pico.
    """
    if not linhas:
        return a, b, False
    dur_min, mx_cfg = duracao_cortes_config()
    dur_max = float(dur_max or mx_cfg)
    a = max(0, int(a)); b = min(len(linhas)-1, int(b))
    idx_pico = b if idx_pico is None else int(idx_pico)
    idx_pico = max(a, min(idx_pico, len(linhas)-1))

    def dur(aa, bb):
        return segundos_linha_fim(linhas[bb]) - segundos_linha_inicio(linhas[aa])

    def caberia(aa, bb):
        return dur(aa, bb) <= dur_max + 0.02

    if linha_tem_fechamento(b) and caberia(a, b):
        return a, b, False

    melhor = (a, b, texto_parece_incompleto(texto_linhas(linhas[a:b+1])))
    limite_busca = min(len(linhas)-1, b + 10)
    for nb in range(b + 1, limite_busca + 1):
        fecha = linha_tem_fechamento(nb)
        proxima = _txt_linha(nb + 1) if nb + 1 < len(linhas) else ""
        inicio_nova = bool(_INICIO_NOVA_IDEIA.search(proxima)) if proxima else False

        # Só considera parada boa quando fechou a frase/ideia ou a próxima linha começa nova ideia.
        if not fecha and not inicio_nova and nb < limite_busca:
            continue

        aa = a
        while aa < idx_pico and not caberia(aa, nb):
            aa += 1

        if caberia(aa, nb) and aa <= idx_pico <= nb:
            incompleto = not (fecha or inicio_nova)
            melhor = (aa, nb, incompleto)
            if not incompleto:
                return aa, nb, False

    aa, bb, inc = melhor
    while bb + 1 < len(linhas) and caberia(aa, bb + 1):
        bb += 1
        if linha_tem_fechamento(bb):
            return aa, bb, False

    inc = texto_parece_incompleto(texto_linhas(linhas[aa:bb+1]))
    return aa, bb, inc

def indice_linha_mais_proxima(t):
    if not linhas:
        return None
    try:
        alvo = float(t or 0)
    except Exception:
        alvo = 0.0
    melhor_i, melhor_d = 0, 10**9
    for i, l in enumerate(linhas):
        ini = segundos_linha_inicio(l); fim = segundos_linha_fim(l)
        centro = (ini + fim) / 2.0
        d = abs(centro - alvo)
        if d < melhor_d:
            melhor_i, melhor_d = i, d
    return melhor_i

def janela_score_edicao(bloco, corte_ref=None):
    """Pontua uma janela de linhas para achar onde o corte deve começar e terminar.
    A ideia é entregar menos trabalho na pós: pegar gancho + desenvolvimento + virada,
    respeitando duração mínima/máxima escolhida pelo usuário.
    """
    txt = texto_linhas(bloco)
    if not txt:
        return 0, [], "fé", "impacto"
    s, raz, emocao, funcao = score_heuristico(txt)
    ref = _norm((corte_ref or {}).get("texto", ""))[:80]
    norm = _norm(txt)
    if ref and (ref in norm or norm[:80] in ref):
        s += 10; raz = (raz or []) + ["contém o pico detectado"]
    if re.search(r"\?", txt):
        s += 6
    if re.search(r"\b(mas|então|até que|de repente|só que|porém|quando)\b", txt.lower()):
        s += 7; raz = (raz or []) + ["virada narrativa"]
    if re.search(r"\b(você|voce|hoje|agora|escuta|entenda|olha|presta atenção)\b", txt.lower()):
        s += 5
    if any(x.get("pico_voz") for x in bloco):
        s += 10; raz = (raz or []) + ["pico de voz/presença"]
        if emocao == "fé":
            emocao = "presença"
    if bool(config_usuario.get("modo_contexto_pregacao", CONFIG.get("modo_contexto_pregacao", True))):
        tem_hist = bloco_tem_historia(bloco)
        tem_dir = bloco_tem_palavra_direcionada(bloco)
        if tem_dir:
            s += 16
            raz = (raz or []) + ["palavra direcionada/aplicação"]
            funcao = "palavra direcionada" if funcao in ("história", "ensino", "impacto") else funcao
        if tem_hist and tem_dir:
            s += 8
            raz = (raz or []) + ["história com aplicação"]
        elif tem_hist and not tem_dir and bool(config_usuario.get("historia_precisa_aplicacao", CONFIG.get("historia_precisa_aplicacao", True))):
            s -= 24
            raz = (raz or []) + ["história sem aplicação penalizada"]
        primeiro = (bloco[0].get("texto") or "").strip()
        if _INICIO_MEIO_HISTORIA.search(primeiro) and tem_hist and not tem_dir:
            s -= 10
            raz = (raz or []) + ["começo no meio da história"]
        if tem_hist and not bloco_tem_fechamento_direcionado(bloco):
            s -= 8
    if len(txt.split()) < 18:
        s -= 12
    if bool(config_usuario.get("finalizacao_contexto_corte", CONFIG.get("finalizacao_contexto_corte", True))) and texto_parece_incompleto(txt):
        s -= 22
        raz = (raz or []) + ["fim incompleto penalizado"]
    return max(0, min(int(s), 100)), raz[:5] if raz else [], emocao, funcao

def calcular_janela_corte_ideal(corte_ref, dur_min=None, dur_max=None):
    """Define minutagem exata do corte usando as linhas transcritas.

    Em vez de cortar apenas uma margem fixa antes/depois do pico, ele testa várias
    janelas ao redor do momento detectado e escolhe a melhor janela com score viral.
    Retorna início/fim em segundos da gravação, texto final do corte e metadados.
    """
    if not linhas:
        t = float(corte_ref.get("tempo", 0) or 0)
        return {"inicio": max(0, t), "fim": max(0, t) + 15, "duracao": 15,
                "texto_final": corte_ref.get("texto", ""), "score_janela": corte_ref.get("score", 0),
                "razoes_janela": [], "metodo": "fallback_sem_linhas"}
    dur_min = int(dur_min or config_usuario.get("duracao_corte_min", CONFIG.get("duracao_corte_min", 15)))
    dur_max = int(dur_max or config_usuario.get("duracao_corte_max", CONFIG.get("duracao_corte_max", 45)))
    dur_min = max(5, dur_min)
    dur_max = max(dur_min, dur_max)
    pico = float(corte_ref.get("tempo", 0) or 0)
    busca = float(config_usuario.get("corte_exato_busca_seg", CONFIG.get("corte_exato_busca_seg", 90)))
    idx = indice_linha_mais_proxima(pico)
    if idx is None:
        idx = 0
    indices_validos = []
    for i,l in enumerate(linhas):
        if abs(segundos_linha_inicio(l) - pico) <= busca:
            indices_validos.append(i)
    if not indices_validos:
        indices_validos = list(range(max(0, idx-8), min(len(linhas), idx+9)))
    min_i, max_i = min(indices_validos), max(indices_validos)
    candidatos = []
    for a in range(max(0, idx-10, min_i), min(idx+1, max_i+1)):
        for b in range(max(a, idx), min(len(linhas)-1, idx+14, max_i)+1):
            ini = segundos_linha_inicio(linhas[a])
            fim = segundos_linha_fim(linhas[b])
            dur = max(0.1, fim - ini)
            if dur < dur_min or dur > dur_max:
                continue
            aa, bb, incompleto_ctx = (a, b, False)
            if bool(config_usuario.get("finalizacao_contexto_corte", CONFIG.get("finalizacao_contexto_corte", True))):
                aa, bb, incompleto_ctx = ajustar_fim_para_fechamento(a, b, idx_pico=idx, dur_max=dur_max)
            aa, bb, incompleto_hist = ajustar_para_palavra_direcionada(aa, bb, idx_pico=idx, dur_max=dur_max)
            incompleto_ctx = incompleto_ctx or incompleto_hist
            ini = segundos_linha_inicio(linhas[aa])
            fim = segundos_linha_fim(linhas[bb])
            dur = fim - ini
            if dur < dur_min or dur > dur_max:
                continue
            bloco = linhas[aa:bb+1]
            txt = texto_linhas(bloco)
            if len(txt.split()) < 12:
                continue
            s, raz, emo, func = janela_score_edicao(bloco, corte_ref)
            if incompleto_ctx:
                s -= 28
                raz = (raz or []) + ["contexto/palavra direcionada incompleta"]
            bonus = 0
            primeiro = (bloco[0].get("texto") or "").strip().lower()
            ultimo = (bloco[-1].get("texto") or "").strip()
            if re.match(r"^(você|voce|quando|por que|sabe|escuta|olha|então|e então|agora|aí|ai)\b", primeiro):
                bonus += 4
            if re.search(r"[.!?…]$", ultimo):
                bonus += 3
            if ini <= pico <= fim:
                bonus += 8
            if pico - ini < 3 and dur > dur_min + 5:
                bonus -= 5
            candidatos.append((s+bonus, ini, fim, aa, bb, txt, raz, emo, func))
    if not candidatos:
        margem_antes = int(config_usuario.get("margem_antes_corte", CONFIG.get("margem_antes_corte", 10)))
        ini = max(0, pico - margem_antes)
        fim = ini + min(max(dur_min, margem_antes + int(config_usuario.get("margem_depois_corte", CONFIG.get("margem_depois_corte", 8)))), dur_max)
        bloco = [l for l in linhas if segundos_linha_fim(l) >= ini and segundos_linha_inicio(l) <= fim]
        txt = texto_linhas(bloco) or corte_ref.get("texto", "")
        s, raz, emo, func = janela_score_edicao(bloco, corte_ref) if bloco else (int(corte_ref.get("score",0) or 0), [], corte_ref.get("emocao",""), corte_ref.get("funcao",""))
        return {"inicio": round(ini,2), "fim": round(fim,2), "duracao": round(fim-ini,2),
                "texto_final": txt, "score_janela": s, "razoes_janela": raz,
                "emocao_janela": emo, "funcao_janela": func, "metodo": "fallback_margem"}
    candidatos.sort(key=lambda x: x[0], reverse=True)
    score_j, ini, fim, a, b, txt, raz, emo, func = candidatos[0]
    return {"inicio": round(ini,2), "fim": round(fim,2), "duracao": round(fim-ini,2),
            "linha_inicio": a, "linha_fim": b, "texto_final": txt,
            "score_janela": int(max(0, min(score_j, 100))), "razoes_janela": raz,
            "emocao_janela": emo, "funcao_janela": func, "metodo": "janela_viral_emocional"}

def janela_por_timecode_srt(corte_ref, prefer_ini=None, prefer_fim=None):
    """Escolhe início/fim usando as linhas da transcrição como se fossem o SRT oficial.

    A regra é: o corte só começa e termina em timecodes de fala transcrita
    (linha['inicio'] e linha['fim']). Isso evita exportar 2 minutos de Replay Buffer
    quando o usuário configurou 15s a 45s.
    """
    if not bool(config_usuario.get("usar_srt_como_timecode", CONFIG.get("usar_srt_como_timecode", True))):
        return None
    if not linhas:
        return None
    dur_min, dur_max = duracao_cortes_config()
    try:
        pico = float(corte_ref.get("tempo", corte_ref.get("fim_exato", 0)) or 0)
    except Exception:
        pico = 0.0
    idx = indice_linha_mais_proxima(pico)
    if idx is None:
        return None

    # Limita busca ao entorno do pico para evitar pegar história inteira.
    busca = float(config_usuario.get("corte_exato_busca_seg", CONFIG.get("corte_exato_busca_seg", 90)))
    candidatos = []
    min_i = max(0, idx - 16)
    max_i = min(len(linhas) - 1, idx + 16)
    for a in range(min_i, idx + 1):
        for b in range(max(a, idx), max_i + 1):
            ini = segundos_linha_inicio(linhas[a])
            fim = segundos_linha_fim(linhas[b])
            if abs(ini - pico) > busca and abs(fim - pico) > busca:
                continue
            dur = fim - ini
            if dur < dur_min or dur > dur_max:
                continue
            aa, bb, incompleto_ctx = (a, b, False)
            if bool(config_usuario.get("finalizacao_contexto_corte", CONFIG.get("finalizacao_contexto_corte", True))):
                aa, bb, incompleto_ctx = ajustar_fim_para_fechamento(a, b, idx_pico=idx, dur_max=dur_max)
            aa, bb, incompleto_hist = ajustar_para_palavra_direcionada(aa, bb, idx_pico=idx, dur_max=dur_max)
            incompleto_ctx = incompleto_ctx or incompleto_hist
            ini = segundos_linha_inicio(linhas[aa])
            fim = segundos_linha_fim(linhas[bb])
            dur = fim - ini
            if dur < dur_min or dur > dur_max:
                continue
            bloco = linhas[aa:bb+1]
            txt = texto_linhas(bloco)
            if len(txt.split()) < 8:
                continue
            s, raz, emo, func = janela_score_edicao(bloco, corte_ref)
            if incompleto_ctx:
                s -= 28
                raz = (raz or []) + ["contexto/palavra direcionada incompleta"]
            # preferência por janelas próximas da sugestão da IA/detector, quando houver
            dist_bonus = 0
            if prefer_ini is not None and prefer_fim is not None:
                try:
                    dist = abs(float(prefer_ini)-ini) + abs(float(prefer_fim)-fim)
                    dist_bonus = max(-12, 8 - dist/5)
                except Exception:
                    dist_bonus = 0
            # o pico precisa estar dentro, de preferência com contexto antes e depois
            if ini <= pico <= fim:
                s += 10
                if pico - ini < 2 and dur > dur_min + 5:
                    s -= 6
                if fim - pico < 2 and dur > dur_min + 5:
                    s -= 4
            candidatos.append((s + dist_bonus, ini, fim, aa, bb, txt, raz, emo, func))
    if not candidatos:
        # fallback: começa/finaliza no SRT mais próximo e respeita max.
        a = max(0, idx - 2)
        b = idx
        while b + 1 < len(linhas) and segundos_linha_fim(linhas[b]) - segundos_linha_inicio(linhas[a]) < dur_min:
            b += 1
        while b + 1 < len(linhas) and segundos_linha_fim(linhas[b+1]) - segundos_linha_inicio(linhas[a]) <= dur_max:
            # expande só se a próxima linha ainda mantém o corte dentro do máximo
            b += 1
            if segundos_linha_fim(linhas[b]) - pico >= max(6, dur_min * 0.35):
                break
        if bool(config_usuario.get("finalizacao_contexto_corte", CONFIG.get("finalizacao_contexto_corte", True))):
            a, b, _inc_ctx = ajustar_fim_para_fechamento(a, b, idx_pico=idx, dur_max=dur_max)
        a, b, _inc_hist = ajustar_para_palavra_direcionada(a, b, idx_pico=idx, dur_max=dur_max)
        ini = segundos_linha_inicio(linhas[a]); fim = segundos_linha_fim(linhas[b])
        ini, fim, dur = normalizar_janela_corte(ini, fim, pico=pico)
        bloco = [l for l in linhas if segundos_linha_fim(l) >= ini and segundos_linha_inicio(l) <= fim]
        txt = texto_linhas(bloco) or corte_ref.get("texto", "")
        return {"inicio": round(ini,2), "fim": round(fim,2), "duracao": round(fim-ini,2),
                "linha_inicio": a, "linha_fim": b, "texto_final": txt,
                "score_janela": corte_ref.get("score", 0), "razoes_janela": ["timecode do SRT/transcrição"],
                "emocao_janela": corte_ref.get("emocao", ""), "funcao_janela": corte_ref.get("funcao", ""),
                "metodo": "srt_timecode_fallback"}
    candidatos.sort(key=lambda x: x[0], reverse=True)
    score_j, ini, fim, a, b, txt, raz, emo, func = candidatos[0]
    return {"inicio": round(ini,2), "fim": round(fim,2), "duracao": round(fim-ini,2),
            "linha_inicio": a, "linha_fim": b, "texto_final": txt,
            "score_janela": int(max(0, min(score_j, 100))),
            "razoes_janela": (raz or []) + ["timecode do SRT/transcrição"],
            "emocao_janela": emo, "funcao_janela": func, "metodo": "srt_timecode"}

def enriquecer_corte_com_janela(corte_ref):
    try:
        janela_base = calcular_janela_corte_ideal(corte_ref)
        janela_srt = janela_por_timecode_srt(corte_ref, janela_base.get("inicio"), janela_base.get("fim"))
        janela = janela_srt or janela_base
        corte_ref.update({
            "inicio_exato": janela.get("inicio"),
            "fim_exato": janela.get("fim"),
            "duracao_exata": janela.get("duracao"),
            "inicio_exato_fmt": fmt(float(janela.get("inicio", 0) or 0)),
            "fim_exato_fmt": fmt(float(janela.get("fim", 0) or 0)),
            "texto_final_corte": janela.get("texto_final") or corte_ref.get("texto", ""),
            "score_janela": janela.get("score_janela"),
            "metodo_minutagem": janela.get("metodo"),
            "timecode_base": "srt/transcricao" if str(janela.get("metodo", "")).startswith("srt") else "janela_transcricao",
            "razoes_janela": janela.get("razoes_janela", []),
        })
        if janela.get("score_janela", 0) > int(corte_ref.get("score", 0) or 0):
            corte_ref["score"] = janela.get("score_janela")
        if janela.get("emocao_janela") and not corte_ref.get("emocao"):
            corte_ref["emocao"] = janela.get("emocao_janela")
        if janela.get("funcao_janela") and not corte_ref.get("funcao"):
            corte_ref["funcao"] = janela.get("funcao_janela")
    except Exception as e:
        print(f"[corte-exato] falhou ao enriquecer corte: {e}")
    return corte_ref

def salvar_mapa_cortes(pasta_cortes, itens):
    if not itens:
        return
    try:
        import csv
        csv_path = os.path.join(pasta_cortes, "mapa-dos-cortes.csv")
        txt_path = os.path.join(pasta_cortes, "mapa-dos-cortes.txt")
        campos = ["n", "titulo", "score", "inicio", "fim", "duracao", "timestamp", "emocao", "funcao", "pasta", "video_16x9", "video_9x16"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            for i, it in enumerate(itens, 1):
                c = it.get("corte", {})
                w.writerow({
                    "n": i,
                    "titulo": c.get("titulo", ""),
                    "score": c.get("score", ""),
                    "inicio": fmt(float(c.get("inicio_exato", c.get("tempo", 0)) or 0)),
                    "fim": fmt(float(c.get("fim_exato", 0) or 0)),
                    "duracao": c.get("duracao_exata", ""),
                    "timestamp": c.get("timestamp", ""),
                    "emocao": c.get("emocao", ""),
                    "funcao": c.get("funcao", ""),
                    "pasta": os.path.basename(it.get("pasta", "")),
                    "video_16x9": os.path.relpath((it.get("videos") or {}).get("16x9", ""), it.get("pasta", "")) if (it.get("videos") or {}).get("16x9") else "",
                    "video_9x16": os.path.relpath((it.get("videos") or {}).get("9x16", ""), it.get("pasta", "")) if (it.get("videos") or {}).get("9x16") else "",
                })
        linhas_txt = ["MAPA DOS CORTES — FRAMEZERO", ""]
        for i, it in enumerate(itens, 1):
            c = it.get("corte", {})
            linhas_txt.append(f"{i:02d}. {c.get('titulo','Momento')} — Score {c.get('score',0)}/100")
            linhas_txt.append(f"    Início: {fmt(float(c.get('inicio_exato', c.get('tempo', 0)) or 0))} | Fim: {fmt(float(c.get('fim_exato', 0) or 0))} | Duração: {c.get('duracao_exata','')}s")
            linhas_txt.append(f"    Emoção: {c.get('emocao','')} | Função: {c.get('funcao','')}")
            linhas_txt.append(f"    Pasta: {os.path.basename(it.get('pasta',''))}")
            vids = it.get('videos') or {}
            if vids.get('16x9'):
                linhas_txt.append(f"    16x9: {os.path.relpath(vids.get('16x9'), it.get('pasta',''))}")
            if vids.get('9x16'):
                linhas_txt.append(f"    9x16: {os.path.relpath(vids.get('9x16'), it.get('pasta',''))}")
            linhas_txt.append("")
        mapa_texto = "\n".join(linhas_txt)
        Path(txt_path).write_text(mapa_texto, encoding="utf-8")
        Path(os.path.join(pasta_cortes, "indice-dos-cortes.txt")).write_text(mapa_texto, encoding="utf-8")

        frases_gerais = []
        versiculos_gerais = []
        for it in itens:
            c = it.get("corte", {})
            for frase in extrair_frases_de_impacto(c):
                if frase not in frases_gerais:
                    frases_gerais.append(frase)
            for ref in extrair_versiculos(c):
                if ref not in versiculos_gerais:
                    versiculos_gerais.append(ref)

        linhas_frases = ["FRASES DE IMPACTO DA PREGAÇÃO", ""]
        if frases_gerais:
            linhas_frases += [f"{i:02d}. {frase}" for i, frase in enumerate(frases_gerais, 1)]
        else:
            linhas_frases.append("Nenhuma frase de impacto detectada nos cortes finais.")
        Path(os.path.join(pasta_cortes, "frases-de-impacto-da-pregacao.txt")).write_text("\n".join(linhas_frases) + "\n", encoding="utf-8")

        linhas_versiculos = ["VERSÍCULOS / REFERÊNCIAS BÍBLICAS DA PREGAÇÃO", ""]
        if versiculos_gerais:
            linhas_versiculos += [f"{i:02d}. {ref}" for i, ref in enumerate(versiculos_gerais, 1)]
        else:
            linhas_versiculos.append("Nenhum versículo detectado nos cortes finais.")
        Path(os.path.join(pasta_cortes, "versiculos-da-pregacao.txt")).write_text("\n".join(linhas_versiculos) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"[cortes] falhou ao salvar mapa geral: {e}")

def resetar_sessao():
    """Limpa tudo que foi capturado no painel/servidor e recomeça a sessão.
    Se o OBS estiver gravando/transmitindo, zera o contador do FrameZero a partir de agora.
    """
    global inicio_gravacao, gravacao_completa, linhas, cortes, texto_desde_ia, texto_contexto_ia, ultima_ia, ultimos_cortes_locais, pasta_cortes_ao_vivo, pasta_cortes_finais, volume_historico, volume_picos
    linhas = []
    cortes = []
    texto_desde_ia = []
    texto_contexto_ia = []
    ultimos_cortes_locais = []
    volume_historico = []
    volume_picos = {}
    ultima_ia = time.time()
    gravacao_completa = None
    pasta_cortes_ao_vivo = None
    pasta_cortes_finais = None
    if gravando:
        inicio_gravacao = time.time()
        if obs_req:
            garantir_replay_buffer(silencioso=True)
    else:
        inicio_gravacao = None
    enviar({"tipo":"reset_ok","gravando":gravando,"motivo":"Sessão reiniciada"})
    enviar({"tipo":"status","gravando":gravando,"transcricao_ativa":bool(config_usuario.get("transcricao_ativa", CONFIG.get("transcricao_ativa", True))),"motivo":"reiniciado" if gravando else "pausado"})
    print("[reset] sessão limpa pelo painel")

def gerar_cortes_precisos():
    """
    Depois do culto: pega a gravacao completa do OBS e corta cada momento
    marcado no ponto exato, em mp4, ja nomeado, com .srt do lado.
    Roda numa thread pra nao travar o servidor.
    """
    if not gravacao_completa or not os.path.exists(gravacao_completa):
        enviar({"tipo":"aviso","texto":"Gravacao completa nao encontrada. Verifique se o OBS terminou de salvar."})
        return
    if not cortes:
        novos = gerar_cortes_fallback_local()
        if novos:
            cortes.extend(novos)
            for c in novos:
                enviar(c)
            enviar({"tipo":"aviso","texto":f"Nenhum momento estava marcado. Gerei {len(novos)} cortes pela análise local da transcrição."})
        else:
            enviar({"tipo":"aviso","texto":"Nenhum momento marcado e transcrição insuficiente para gerar cortes."})
            return
    ffmpeg = caminho_ffmpeg()
    if ffmpeg is None:
        enviar({"tipo":"aviso","texto":"FFmpeg nao encontrado. Reinstale com o instalador."})
        return

    pasta_base = os.path.dirname(gravacao_completa)
    pasta_cortes = pasta_principal(pasta_base, "final")

    total = len(cortes)
    enviar({"tipo":"cortes_inicio","total":total})
    print(f"[cortes] gerando {total} cortes de {gravacao_completa}")

    # Duração vem SEMPRE do painel/config. Nunca usa Replay Buffer como duração do corte.
    margem_antes = int(config_usuario.get("margem_antes_corte", CONFIG.get("margem_antes_corte", 10)))
    margem_depois = int(config_usuario.get("margem_depois_corte", CONFIG.get("margem_depois_corte", 8)))
    dur_min, dur_max = duracao_cortes_config()

    feitos = 0
    mapa_itens = []
    for c in cortes:
        # janela exata do corte: gancho + pico + conclusão, respeitando duração min/max.
        if bool(config_usuario.get("corte_exato_automatico", CONFIG.get("corte_exato_automatico", True))):
            c = enriquecer_corte_com_janela(c)
        if c.get("inicio_exato") is not None and c.get("fim_exato") is not None:
            # Já vem alinhado ao SRT/transcrição quando possível; normaliza só para respeitar min/max.
            ini, fim, dur = normalizar_janela_corte(c.get("inicio_exato"), c.get("fim_exato"), pico=c.get("tempo"))
        else:
            ini, fim, dur = normalizar_janela_corte(max(0, float(c["tempo"]) - margem_antes), float(c["tempo"]) + margem_depois, pico=c.get("tempo"))
        c["inicio_exato"] = round(ini, 2)
        c["fim_exato"] = round(fim, 2)
        c["duracao_exata"] = round(dur, 2)
        c["inicio_exato_fmt"] = fmt(ini)
        c["fim_exato_fmt"] = fmt(fim)
        pasta_corte = pasta_do_corte(pasta_cortes, c)

        try:
            videos_gerados = gerar_versoes_do_corte(gravacao_completa, pasta_corte, c, inicio=ini, duracao=dur, timeout=420)
            if not videos_gerados:
                print(f"[cortes] ffmpeg não gerou nenhuma versão para '{c.get('titulo','momento')}'")
                continue
            saida = videos_gerados.get("9x16") or videos_gerados.get("16x9") or next(iter(videos_gerados.values()))
            # srt + pacote social do corte
            srt = gerar_srt_corte_preciso(ini, ini + dur)
            salvar_arquivos_corte(pasta_corte, c, video_path=saida, srt_text=srt, videos=videos_gerados)
            mapa_itens.append({"corte": dict(c), "pasta": pasta_corte, "video": saida, "videos": videos_gerados})
            feitos += 1
            enviar({"tipo":"corte_pronto","nome":os.path.basename(pasta_corte),
                    "feitos":feitos,"total":total,
                    "inicio":fmt(ini),"fim":fmt(ini+dur),"duracao":round(dur,2),"score":c.get("score",0)})
            print(f"[cortes] {feitos}/{total} {os.path.basename(pasta_corte)} | {fmt(ini)} até {fmt(ini+dur)} ({dur:.1f}s) | versões: {', '.join(videos_gerados.keys())}")
        except Exception as e:
            print(f"[cortes] falhou em '{c.get('titulo','momento')}': {e}")

    salvar_mapa_cortes(pasta_cortes, mapa_itens)
    enviar({"tipo":"cortes_fim","feitos":feitos,"total":total,"pasta":pasta_cortes})
    print(f"[cortes] concluido: {feitos}/{total} em {pasta_cortes}")

def gerar_srt_corte_preciso(ini_clipe, fim_clipe):
    """SRT so das falas dentro do corte preciso, timecode reiniciado em 00:00:00."""
    out=[]; i=1
    for l in linhas:
        if l["fim"] < ini_clipe or l["inicio"] > fim_clipe:
            continue
        a = max(0, l["inicio"] - ini_clipe)
        b = max(a + 0.5, l["fim"] - ini_clipe)
        i = adicionar_cues_srt(out, i, a, b, l["texto"])
    if not out:
        out = ["1","00:00:00,000 --> 00:00:02,000","(sem fala neste trecho)",""]
    return "\n".join(out)

# ----------------------------- EXPORT -----------------------------

def gerar_srt_trecho(inicio_corte, fim_corte, segundos_buffer):
    """
    Gera um .srt so das falas dentro do clipe, com o timecode REINICIADO em
    00:00:00 no comeco do clipe. O clipe comeca em (fim_corte - segundos_buffer)
    porque o Replay Buffer guarda os segundos anteriores ao disparo.
    """
    inicio_clipe = max(0, fim_corte - segundos_buffer)
    fim_clipe = fim_corte + 4  # pequena margem depois do gatilho
    out = []
    i = 1
    for l in linhas:
        # a linha precisa cair dentro da janela do clipe
        if l["fim"] < inicio_clipe or l["inicio"] > fim_clipe:
            continue
        ini_rel = max(0, l["inicio"] - inicio_clipe)
        fim_rel = max(ini_rel + 0.5, l["fim"] - inicio_clipe)
        i = adicionar_cues_srt(out, i, ini_rel, fim_rel, l["texto"])
    if not out:
        out = ["1", "00:00:00,000 --> 00:00:02,000", "(sem fala transcrita neste trecho)", ""]
    return "\n".join(out)


def gerar_txt():
    return "\n".join(f"[{l['timestamp']}] {l['texto']}" for l in linhas)

def gerar_srt():
    out=[]
    i = 1
    for l in linhas:
        i = adicionar_cues_srt(out, i, l["inicio"], l["fim"], l["texto"])
    return "\n".join(out)

# ----------------------------- MAIN -----------------------------

async def handler_plugin_audio(ws):
    """Recebe o audio do plugin obs-audio-to-websocket (mixer do OBS).
    O plugin e o cliente; este servidor escuta na porta 8889, rota /audio."""
    global plugin_conectado
    plugin_conectado = True
    print("[plugin] obs-audio-to-websocket conectado")
    enviar({"tipo":"plugin_status","conectado":True})
    try:
        async for msg in ws:
            if isinstance(msg, (bytes, bytearray)):
                # so usa o audio do plugin se a fonte escolhida for "plugin"
                if fonte_audio != "plugin":
                    continue
                audio, sr = parse_audio_plugin(bytes(msg))
                if audio is None:
                    continue
                audio16k = reamostrar(audio, sr, CONFIG["sample_rate"])
                # injeta na mesma fila que o ASR consome (formato [N,1])
                fila_audio.put(audio16k.reshape(-1, 1))
            else:
                # mensagem de controle JSON (start/stop) - so loga
                pass
    finally:
        plugin_conectado = False
        print("[plugin] desconectado")
        enviar({"tipo":"plugin_status","conectado":False})

async def main():
    global loop_principal
    loop_principal = asyncio.get_running_loop()
    iniciar_obs()

    # Modo vertical desativado por padrao.
    # O Aitum pode estar instalado, mas o FrameZero nao cria/forca cena vertical automaticamente.
    try:
        if bool(config_usuario.get("vertical_ativo", CONFIG["vertical_ativo"])):
            configurar_cena_vertical(True)
    except Exception as e:
        print(f"[vertical] auto-start falhou: {e}")

    disp = config_usuario.get("dispositivo_audio", CONFIG["dispositivo_audio"])
    global fonte_audio
    fonte_audio = config_usuario.get("fonte_audio", "dispositivo")

    # Mac: se existir BlackHole, seleciona automaticamente como entrada do FrameZero.
    # Windows: se existir VB-CABLE e ainda não houver dispositivo salvo, seleciona automaticamente
    # a entrada de captura do VB-CABLE para o Core realmente ouvir o áudio do OBS/sistema.
    if platform.system().lower() == "darwin" and bool(config_usuario.get("forcar_blackhole_se_existir", CONFIG.get("forcar_blackhole_se_existir", True))):
        bh_id, bh_nome = encontrar_blackhole()
        if bh_id is not None:
            fonte_audio = "dispositivo"
            disp = bh_id
            config_usuario["fonte_audio"] = "dispositivo"
            config_usuario["dispositivo_audio"] = bh_id
            salvar_config_usuario({"fonte_audio":"dispositivo", "dispositivo_audio":bh_id})
            print(f"[audio] BlackHole detectado e selecionado automaticamente: {bh_nome}")
        else:
            print("[audio] BlackHole não detectado. Usando dispositivo padrão como fallback.")
            enviar_audio_status(ok=False, nome="BlackHole não detectado", rms=0.0, msg="BlackHole não apareceu; reinicie o Mac ou use microfone padrão")
    elif platform.system().lower() == "windows" and fonte_audio == "dispositivo" and disp in (None, "", "padrao", "padrão", "default"):
        vb_id, vb_nome = encontrar_vbcable_windows()
        if vb_id is not None:
            disp = vb_id
            config_usuario["fonte_audio"] = "dispositivo"
            config_usuario["dispositivo_audio"] = vb_id
            salvar_config_usuario({"fonte_audio":"dispositivo", "dispositivo_audio":vb_id, "audio_input_device_id":vb_id, "audio_input_device_name":vb_nome})
            print(f"[audio] VB-CABLE detectado e selecionado automaticamente: {vb_nome}")

    if fonte_audio == "dispositivo":
        ok_audio, nome_audio = abrir_audio(disp)
        if not ok_audio and disp is not None:
            print("[audio] fallback: tentando dispositivo padrão do sistema")
            abrir_audio(None)
    else:
        print("[audio] fonte = plugin do OBS (aguardando conexao do plugin)")
    threading.Thread(target=worker_analise_cortes, daemon=True).start()
    threading.Thread(target=loop_transcricao, daemon=True).start()

    # servidor do painel + servidor do plugin de audio, juntos
    async with websockets.serve(handler,"localhost",CONFIG["porta_painel"]), \
               websockets.serve(handler_plugin_audio,"localhost",CONFIG["porta_plugin_audio"]):
        print("="*60)
        print(f"[painel] {config_usuario.get('painel_url', CONFIG.get('painel_url', 'https://clips.framezeroai.com.br/obs'))}")
        print(f"[painel-ws] ws://localhost:{CONFIG['porta_painel']}")
        print(f"[plugin] ws://localhost:{CONFIG['porta_plugin_audio']}{CONFIG['rota_plugin_audio']} (audio do mixer, opcional)")
        print("="*60)
        await asyncio.Future()

def listar():
    if sd is None:
        print(f"sounddevice/PortAudio indisponivel: {SOUNDDEVICE_ERROR}")
    else:
        print(sd.query_devices())

if __name__ == "__main__":
    import sys
    if len(sys.argv)>1 and sys.argv[1]=="--dispositivos":
        listar()
    else:
        try: asyncio.run(main())
        except KeyboardInterrupt: print("\n[fim]")
