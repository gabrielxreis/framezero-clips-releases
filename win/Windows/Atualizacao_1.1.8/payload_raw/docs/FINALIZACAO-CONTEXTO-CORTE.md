# v48 — Finalização de contexto do corte viral

Esta versão corrige o caso em que o corte termina no meio da conclusão da ideia.

## Regra nova

O FrameZero continua respeitando o tempo configurado no painel, por exemplo 15s a 45s, mas agora evita terminar o vídeo em frases abertas como:

- "você está..."
- "porque nessa noite você..."
- "só que..."
- "então..."
- frases terminando com vírgula, dois pontos ou reticências.

## Como funciona

1. Detecta o pico viral/emocional.
2. Busca a janela pelo timecode do SRT/transcrição.
3. Verifica se o fim tem fechamento natural.
4. Se o fim estiver incompleto, puxa as próximas linhas do SRT até fechar a ideia.
5. Se passar do tempo máximo configurado, desloca o início para frente, preservando o pico e a conclusão.
6. Se mesmo assim não couber, penaliza essa janela e tenta escolher outra melhor.

## Resultado

O corte deve terminar com contexto mais completo, sem cortar o final da frase ou da aplicação espiritual.

O vídeo final continua saindo como:

- video.mp4
- legenda.srt
- legenda.ass
- metadata.json
- resumo-do-corte.txt
- legenda-instagram.txt
- legenda-tiktok.txt
