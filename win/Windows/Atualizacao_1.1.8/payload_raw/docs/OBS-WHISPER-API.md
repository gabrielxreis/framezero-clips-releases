# OBS Whisper API — integração FrameZero

## Servidor configurado

```txt
http://2.25.157.230:8000
```

Endpoint usado pelo FrameZero:

```txt
POST /transcribe
```

URL final:

```txt
http://2.25.157.230:8000/transcribe
```

Chave configurada:

```txt
framezero_obs_2026
```

O FrameZero envia a chave em múltiplos headers para compatibilidade:

```txt
Authorization: Bearer framezero_obs_2026
X-API-Key: framezero_obs_2026
X-FrameZero-Key: framezero_obs_2026
```

Se a API responder 401/403, ele tenta também:

```txt
token: framezero_obs_2026
x-token: framezero_obs_2026
```

## Fase 1 — API básica

O FrameZero envia `multipart/form-data` com o campo:

```txt
file
```

Campos extras enviados:

```txt
language=pt
task=transcribe
format=json
timestamps=true
source=framezero_obs
```

Resposta aceita:

```json
{
  "text": "transcrição completa",
  "segments": [
    {"start": 0.0, "end": 4.2, "text": "texto do trecho"}
  ]
}
```

Também aceita `texto`, `transcription`, `transcricao`, `segmentos` ou `chunks`.

## Fase 2 — preparada

A v25 já está preparada para futura API em background:

- `GET /health`
- `POST /transcribe` retornando `job_id`
- `GET /jobs/{job_id}` retornando status e resultado

Status reconhecidos:

```txt
aguardando / queued / pending
processando / processing
concluido / completed / done / ok / success
erro / error / failed / falhou
```

Se `/health` ainda não existir, o FrameZero não trava; ele considera como Fase 1 e usa `/transcribe` direto.
