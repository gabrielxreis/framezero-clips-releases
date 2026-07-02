# Corte exato automático

O FrameZero calcula automaticamente início e fim de cada corte na gravação completa.

## Como funciona

1. Durante a gravação, ele detecta um pico/candidato de corte.
2. No fim, ao gerar cortes, ele procura uma janela ao redor do pico.
3. Ele testa janelas entre o tempo mínimo e máximo configurados.
4. Escolhe a melhor janela com gancho, emoção, virada narrativa e conclusão.
5. Exporta o vídeo final e os arquivos sociais em uma subpasta.

## Padrão

- mínimo: 15s
- máximo: 45s
- score 80+: possível corte
- score 90+: corte forte

## Arquivos gerados

Cada corte tem:

- video.mp4
- legenda.srt
- metadata.json
- legenda-instagram.txt
- legenda-tiktok.txt
- resumo-do-corte.txt

A pasta principal tem:

- mapa-dos-cortes.csv
- mapa-dos-cortes.txt
