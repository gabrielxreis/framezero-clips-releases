# v72 — Transcrição VPS em tempo real

A v71 usava blocos de 12s/15s, que são bons para contexto, mas não parecem tempo real.

A v72 muda o ao vivo para micro-blocos:

- transcricao=vps
- engine=faster-whisper
- endpoint principal: http://2.25.157.230:8000/transcribe-fastwhisper
- endpoint secundário permitido: http://2.25.157.230:8000/transcribe
- bloco ao vivo: 3s
- local/híbrido não fazem ASR local

Mesmo se o painel mandar `hibrido`, o servidor força VPS em micro-blocos para mostrar texto rapidamente.
