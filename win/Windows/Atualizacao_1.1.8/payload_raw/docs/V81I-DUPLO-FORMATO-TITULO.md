# FrameZero Clips v81i — Pastas por título + 16x9 e 9x16 automáticos

## O que mudou

- Cada corte agora cria uma pasta com o título em primeiro lugar.
- Cada corte gera automaticamente duas versões:
  - `16x9/`
  - `9x16/`
- O arquivo final de vídeo recebe o nome do título do corte.

## Exemplo de saída

```txt
FrameZero_Cortes_Finais_2026-06-27_21-30/
└── Você sabe negociar - 00-01-15 - score 065/
    ├── 16x9/
    │   └── Você sabe negociar - 16x9.mp4
    ├── 9x16/
    │   └── Você sabe negociar - 9x16.mp4
    ├── legenda.srt
    ├── legenda.ass
    ├── legenda-instagram.txt
    ├── legenda-tiktok.txt
    ├── resumo-do-corte.txt
    └── metadata.json
```

## Observação

O modo manual de proporção continua existindo como fallback, mas o padrão agora é entregar 16x9 e 9x16 juntos.
