# OBS Whisper + IA VPS — Configuração integrada ao FrameZero

Esta versão do FrameZero já vem pronta para usar a VPS do Gabriel. O usuário final não precisa configurar endpoint, token ou modelo.

## API pública

Base URL:

```txt
http://2.25.157.230:8000
```

Health check:

```txt
GET /health
```

Transcrição:

```txt
POST /transcribe
```

Análise de texto:

```txt
POST /analyze-text
```

Header obrigatório usado pelo plugin:

```txt
x-api-key: framezero_obs_2026
```

## Modelos da VPS

Ollama roda apenas internamente na VPS em:

```txt
http://127.0.0.1:11434
```

Modelo principal de análise:

```txt
criador-cristao:latest
```

Modelo base:

```txt
qwen2.5:3b
```

Modelo extra instalado:

```txt
deepseek-r1:1.5b
```

## Como o FrameZero usa

1. Captura o áudio do OBS no Mac, preferencialmente via BlackHole 2ch.
2. Envia blocos de áudio para `/transcribe`.
3. Recebe `text` e `segments`.
4. Envia o texto para `/analyze-text`.
5. Usa o retorno da IA da VPS para gerar score, título, hook, motivo e sugestão de legenda.
6. No fim da gravação, cria uma pasta principal e uma subpasta para cada corte.

## Segurança

O acesso SSH da VPS não é usado pelo plugin e não deve ser colocado no código do app. O plugin usa apenas HTTP + `x-api-key`.


## v37 — VPS sem /analyze-text

Se a VPS ainda não tiver o endpoint `/analyze-text`, o FrameZero não mostra erro repetido. Ele continua transcrevendo pela VPS e usa o detector local de cortes automaticamente.
