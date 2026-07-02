# API do plugin do OBS — FrameZero v38

Base URL: `http://2.25.157.230:8000`

## Headers
Todas as chamadas protegidas usam:

```txt
x-api-key: framezero_obs_2026
```

## Health
`GET /health`

Resposta esperada inclui `status`, `api`, `whisper`, `ollama` e `deepseek_model`. O plugin usa este endpoint só para status; se falhar, pode continuar com fallback local.

## Transcrição
`POST /transcribe` com `multipart/form-data` e campo `file`.

Formatos: `.mp4`, `.mov`, `.mp3`, `.wav`, `.m4a`.

## Análise de cortes
`POST /analyze-text` com JSON:

```json
{
  "text": "texto transcrito do trecho da live",
  "start_time": 120,
  "end_time": 165
}
```

O plugin aceita `analysis` como JSON puro ou texto no formato:

```txt
Título: ...
Hook: ...
Motivo: ...
Score: ...
Legenda: ...
Capa: ...
```

## Regra de score
- `score >= 80`: possível corte.
- `score >= 90`: corte forte.

## Janela padrão de corte
- mínimo: 15s
- máximo: 45s

## O que o plugin NÃO usa
O plugin não acessa Open WebUI, porta 3000/8080, Ollama 11434, login de GUI ou SSH. Isso é interno da VPS.
