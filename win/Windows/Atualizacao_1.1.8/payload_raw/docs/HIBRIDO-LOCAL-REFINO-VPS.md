# Híbrido: local + VPS

No modo híbrido, o FrameZero trabalha assim:

1. O Whisper local captura e transcreve o áudio para aparecer rápido no painel.
2. A VPS/Ollama recebe o texto, o tipo de conteúdo e o contexto acumulado.
3. A VPS refina a legenda, entende se é Pregação ou Música, e decide os melhores cortes.
4. O vídeo só é cortado depois, usando timecode/SRT e contexto refinado.

Importante:

- Híbrido não envia áudio para `/transcribe` por padrão.
- Híbrido envia texto/contexto para `/analyze-text`.
- Modo VPS puro envia áudio para `/transcribe` e não carrega Whisper local.
- Modo Local não usa VPS.

Fluxo resumido:

```
Local/Híbrido: áudio -> Whisper local -> texto rápido -> VPS/Ollama refina -> corte final
VPS puro: áudio -> VPS /transcribe -> VPS/Ollama analisa -> corte final
```
