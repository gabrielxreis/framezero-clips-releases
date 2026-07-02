# v74 - HTML + anti eco de prompt

- HTML standalone incluído em `obs-panel-v67-standalone.html` e `app/obs-panel.html`.
- Modos de transcrição: Local, Híbrido, VPS.
- Endpoint `/transcribe` bloqueado porque ecoou/alucinou texto.
- Endpoint permitido: `/transcribe-fastwhisper`.
- Removido prompt longo do ASR local para evitar que o Whisper repita instruções como fala real.
- Filtro descarta frases de prompt como: “O áudio é de uma pregação, culto, podcast ou aula bíblica”.
- Deduplicação de linhas repetidas no painel.
