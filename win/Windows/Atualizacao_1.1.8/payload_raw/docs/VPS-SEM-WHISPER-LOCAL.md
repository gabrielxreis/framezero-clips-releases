# Modo VPS puro

Nesta versão, quando o usuário selecionar **Minha VPS**, o FrameZero não carrega o Whisper local.

Isso evita travamento no Mac quando o OBS inicia gravação, porque o computador fica responsável apenas por:

- capturar áudio do BlackHole;
- enviar blocos para a VPS;
- receber transcrição;
- marcar cortes;
- cortar depois que a gravação terminar.

O Whisper local só é carregado quando o usuário escolher o modo **Whisper local**.
