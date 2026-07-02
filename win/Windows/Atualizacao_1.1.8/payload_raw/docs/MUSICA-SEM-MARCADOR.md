# Modo Música sem marcador falso

Nesta versão, o Whisper local não recebe `initial_prompt` no modo Música, porque prompts curtos ainda podiam vazar na legenda como `Música. Música.`.

Também foi adicionado um filtro para remover marcadores descritivos que não são letra cantada, como:

- Música.
- Música. Música.
- Music.
- Song.
- Louvor.

A legenda só deve salvar texto cantado real ou fala real detectada.
