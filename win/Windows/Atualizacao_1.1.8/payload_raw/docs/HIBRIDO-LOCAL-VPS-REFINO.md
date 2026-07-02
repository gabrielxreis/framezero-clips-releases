# FrameZero v52 — Híbrido Local + VPS para tempo real

Fluxo recomendado para live/culto:

1. O Mac roda Whisper local leve (`tiny`) em blocos curtos de 1,5s para a legenda aparecer quase em tempo real.
2. A VPS continua ligada para análise/refino e decisão dos cortes.
3. O usuário escolhe no topo do painel se o conteúdo é `Pregação` ou `Música`.
4. Em Pregação, a IA prioriza contexto fechado, palavra direcionada, aplicação e ministração.
5. Em Música, a IA prioriza refrão, ponte, clímax, repetição bonita e parte emocional.
6. O corte final é feito depois usando o SRT/timecode refinado e respeitando a duração configurada.

Observação: HTTP /transcribe por arquivo nunca será palavra por palavra como WebSocket streaming. Para latência mínima real, a próxima evolução da VPS é um endpoint WebSocket de áudio contínuo.
