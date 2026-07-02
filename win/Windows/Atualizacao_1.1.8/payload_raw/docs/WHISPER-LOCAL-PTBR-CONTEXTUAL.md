# Whisper local PT-BR contextual

A v53 ajusta o modo híbrido para o Whisper local entender melhor português brasileiro.

## Como fica

- Modelo local ao vivo padrão: `base` em vez de `tiny`.
- Idioma fixo: `pt`.
- Prompt contextual para pregação, culto, louvor e ministração.
- Glossário com termos bíblicos e nomes próprios.
- Beam ao vivo padrão: `5` para reduzir troca de palavras.
- Bloco local padrão: `2.5s`, equilibrando tempo real e qualidade.

## Regra principal

O Whisper local mostra a legenda rápida. A VPS/IA refina o contexto, entende se é música ou pregação e só depois decide/corta.

## Importante

`tiny` é mais rápido, mas erra muito em português e em termos bíblicos. Por isso o padrão agora é `base`. Para mais precisão, pode usar `small`, mas pesa mais no Mac.
