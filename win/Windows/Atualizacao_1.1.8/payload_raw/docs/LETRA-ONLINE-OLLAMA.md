# Refino de letra online via Ollama/VPS

Quando o modo de corte estiver em **Música**, o FrameZero passa a informar para a VPS/Ollama que a internet está disponível e que ela pode usar busca online como referência para entender a letra cantada.

## Regra principal

A internet ajuda, mas não manda mais que o áudio.

O sistema deve:

- buscar letra semelhante apenas como referência;
- comparar com o trecho transcrito;
- corrigir somente quando a confiança for alta;
- não substituir se houver dúvida;
- preservar louvor espontâneo, ministração cantada ou improviso;
- nunca escrever marcadores como “Música”, “Louvor” ou “Instrumental” no SRT;
- não copiar letras completas, apenas usar referência para corrigir palavras do trecho.

## Payload enviado para /analyze-text em modo Música

```json
{
  "content_type": "musica",
  "mode": "music_lyrics_refinement",
  "allow_web_search": true,
  "internet_connected": true,
  "lyrics_reference_source": "web_via_ollama_vps",
  "lyrics_reference_policy": "internet_sugere_audio_manda",
  "minimum_lyrics_confidence": 0.82,
  "preserve_spontaneous_worship": true
}
```

## Política de confiança

- confiança alta: pode corrigir palavra parecida;
- confiança média: mantém o áudio/transcrição;
- confiança baixa: não altera;
- se for espontâneo: não força letra online.
