# Música sem prompt vazando na legenda

A partir desta versão, o modo Música não envia instruções longas para o Whisper local.

Problema corrigido:
- O Whisper estava colocando no SRT frases internas como “Não troque palavras cantadas...”
- Em chunks curtos, o prompt longo podia virar texto transcrito.

Fluxo novo:
- Whisper local recebe só contexto mínimo: português brasileiro + música/louvor.
- O texto cantado é preservado.
- Correções bíblicas/contextuais ficam desligadas no modo Música.
- Filtros removem vazamento de prompt e loops de áudio como “e aí, aí, aí...”.

Modo Pregação continua com correção contextual bíblica.
