# SRT pt-BR + legenda estilizada

O FrameZero gera legenda automática em português brasileiro com:

- `legenda.srt`: arquivo limpo, compatível com qualquer editor.
- `legenda.ass`: arquivo estilizado com as características do preset antigo, sem precisar copiar `.preset`.

Padrão aplicado:

- Idioma: pt-BR
- Máximo: 37 caracteres por cue
- Linha única
- Fonte estilizada no ASS: Poppins
- Tamanho: 13
- Peso: Bold
- Arquivo de preset externo: não é mais copiado para os cortes

Observação: o formato SRT puro não armazena fonte, peso, cor, posição ou preset de texto. Por isso o estilo visual fica no `legenda.ass`, enquanto o `legenda.srt` permanece limpo para máxima compatibilidade.
