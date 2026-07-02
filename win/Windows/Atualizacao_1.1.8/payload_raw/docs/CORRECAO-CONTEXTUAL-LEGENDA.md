# Correção contextual de legenda

A partir da v47, o FrameZero aplica uma correção leve antes de mostrar/salvar as legendas.

Objetivo:
- reduzir erros comuns do Whisper em pregações;
- corrigir nomes bíblicos pelo contexto;
- manter os timecodes originais do SRT;
- manter português brasileiro;
- manter 37 caracteres por cue e linha única.

Exemplos tratados:
- `a Braão` / `Braão` -> `Abraão`
- `serba` -> `serva`
- `ser andou` -> `dizendo`
- `senhor` -> `Senhor`
- `deus` -> `Deus`
- `está sendo criada` -> `está sendo guiada`, quando vier no contexto da pregação

Configuração em `app/config.json`:

```json
{
  "corrigir_legenda_contexto": true,
  "contexto_transcricao": "pregação cristã brasileira; nomes bíblicos: Abraão, Sara, Agar, Ismael, Noé, Arca de Noé, Senhor, Deus, serva, timão"
}
```

O arquivo `legenda.srt` continua limpo e compatível com qualquer editor. O arquivo `legenda.ass` continua carregando o estilo visual.
