# v75 — MLX Whisper Local PT-BR

Esta versão remove a transcrição por VPS e troca o motor por MLX Whisper local no Mac Apple Silicon.

## Motor

- `mlx-whisper`
- Modelo leve/padrão: `mlx-community/whisper-large-v3-turbo`
- Modelo pro: `mlx-community/whisper-large-v3`
- Idioma fixo: `pt`
- `condition_on_previous_text=false`
- Sem `initial_prompt` no tempo real

## Removido do fluxo

- `/transcribe`
- `/transcribe-fastwhisper`
- FunASR
- SenseVoice
- faster-whisper local
- ctranslate2/tokenizers
- VPS para transcrição

## Mantido

- Painel HTML
- WebSocket `ws://localhost:8765`
- BlackHole/OBS
- Detecção local de cortes Fast/Standard
- OpenAI opcional para títulos/refino
- SRT/ASS e cortes por FFmpeg

## Regras anti-alucinação

- Bloqueio de eco de prompt
- Bloqueio de texto repetido
- Bloqueio de CJK/japonês/chinês/coreano no PT-BR
- Bloqueio de frases curtas sem português confiável

