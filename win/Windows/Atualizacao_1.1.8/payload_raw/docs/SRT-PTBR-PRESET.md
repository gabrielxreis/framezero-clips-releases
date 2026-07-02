# SRT automático — Português brasileiro

A partir da v45, todo `legenda.srt` gerado pelo FrameZero sai no padrão:

- idioma: português brasileiro (`pt-BR`);
- máximo de 37 caracteres por legenda;
- linha única por cue;
- se a frase passar de 37 caracteres, o sistema divide em novos cues, não em duas linhas;
- cada pasta de corte recebe também o preset `GAB USA Subtitle.preset`.

Arquivos por corte:

```txt
video.mp4
legenda.srt
GAB USA Subtitle.preset
metadata.json
resumo-do-corte.txt
legenda-instagram.txt
legenda-tiktok.txt
```

O preset fica também em `app/presets/GAB USA Subtitle.preset`.
