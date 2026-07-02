# FrameZero v71 — VPS faster-whisper PT-BR

A transcrição principal agora é fixa em VPS com `faster-whisper`.

## Endpoints permitidos

```text
POST http://2.25.157.230:8000/transcribe-fastwhisper
POST http://2.25.157.230:8000/transcribe
```

O endpoint padrão do plugin é:

```text
http://2.25.157.230:8000/transcribe-fastwhisper
```

## Configuração padrão

```text
transcricao=vps
engine=faster-whisper
blocos=12s
```

Para mais contexto e menos alucinação em frases curtas, usar blocos de 15s.

## Removido

```text
/transcribe-fastwhisper
FunASR
SenseVoiceSmall
modo local como transcrição principal
híbrido local→VPS
```

O app local continua apenas como ponte com OBS, BlackHole, gravação, cortes e WebSocket `ws://localhost:8765`.
