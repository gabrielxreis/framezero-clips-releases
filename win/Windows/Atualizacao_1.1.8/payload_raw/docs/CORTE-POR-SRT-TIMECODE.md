# Corte por SRT / Timecode — FrameZero v42

Nesta versão, o FrameZero usa a minutagem da transcrição/SRT como base principal para cortar.

## Por que isso existe

O Replay Buffer do OBS pode salvar um arquivo bruto com 120 segundos ou mais. Isso é bom para segurança, mas o corte final não deve sair com 2 minutos se o usuário configurou 15s a 45s.

## Regra nova

1. A transcrição gera linhas com `inicio`, `fim` e `texto`.
2. Essas linhas são tratadas como o SRT mestre da gravação.
3. Quando um momento forte é detectado, o sistema procura a melhor janela de fala ao redor do pico.
4. O início e o fim do corte são alinhados aos timecodes do SRT/transcrição.
5. O FFmpeg corta o vídeo exatamente nessa janela.
6. O `video.mp4` final respeita o mínimo/máximo configurado no painel.

Padrão:

```txt
mínimo: 15s
máximo: 45s
```

## Replay Buffer

Para clipes ao vivo, o FrameZero agora mede a duração real do arquivo bruto com `ffprobe` e calcula o offset correto dentro do Replay Buffer. Isso evita usar a duração configurada do OBS como se fosse o tempo real do arquivo.

## Arquivos finais

Cada corte continua saindo com:

```txt
video.mp4
legenda.srt
metadata.json
resumo-do-corte.txt
legenda-instagram.txt
legenda-tiktok.txt
```

No `metadata.json`, o campo `timecode_base` indica quando o corte foi baseado em `srt/transcricao`.
