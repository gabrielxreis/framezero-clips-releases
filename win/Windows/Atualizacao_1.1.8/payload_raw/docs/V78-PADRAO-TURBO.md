# FrameZero v79 — Padrão/Turbo + Corte Seguro

## Modo Padrão
- MLX Whisper local/offline no Mac Apple Silicon.
- Sem custo recorrente.
- Blocos maiores para transcrição mais confiável.
- Corte Seguro: mais contexto para evitar cortes picados.

## Modo Turbo
- OpenAI Realtime Transcription com `gpt-realtime-whisper`.
- A chave OpenAI fica salva localmente no `config.json`.
- Delay padrão: `high`, priorizando acerto/contexto.
- Custo de referência: US$ 0,017 por minuto de áudio.

## Regras
- A VPS antiga continua removida.
- Não usar `/transcribe` nem `/transcribe-fastwhisper`.
- Não usar FunASR/SenseVoice.
- O agrupador de assunto deve evitar dividir o mesmo tema bom em dois cortes.
