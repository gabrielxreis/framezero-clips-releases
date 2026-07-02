# Correção v41 — Cortes respeitam duração do painel

Esta versão corrige o problema em que alguns cortes saíam com 2 minutos por causa do Replay Buffer do OBS.

## O que mudou

- O Replay Buffer pode continuar com 120s para segurança, mas o FrameZero agora recorta o arquivo bruto.
- O arquivo final de cada corte sai em `video.mp4` somente com a duração configurada no plugin.
- A duração padrão segue:
  - mínimo: 15s
  - máximo: 45s
- Se o usuário alterar no painel, o corte final respeita o novo mínimo/máximo.
- Os cortes finais gerados depois da gravação também usam a mesma regra.

## Importante

O OBS sempre salva o Replay Buffer inteiro. Por isso, antes alguns clipes vinham com 120s.
Agora o FrameZero usa FFmpeg para transformar o replay bruto em um corte final exato.

Se por algum motivo o FFmpeg falhar, o sistema salva o arquivo bruto como `replay-buffer-bruto.mov` dentro da pasta do corte, para não perder o material.
