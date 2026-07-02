# Perfil OBS atualizado

Esta versão aplica automaticamente o perfil OBS enviado para o FrameZero Clips.

Arquivos aplicados no perfil `FrameZero Clips`:

- `basic.ini`
- `recordEncoder.json`
- `streamEncoder.json`

Configurações principais:

- Saída em modo avançado.
- Replay Buffer ativado em 120 segundos.
- Pasta de gravação: `~/Movies/FrameZero`.
- Monitoramento de áudio: `BlackHole 2ch`.
- Resolução: 1920x1080.
- FPS: 30.
- Encoder Apple VideoToolbox H.264.
- Bitrate dos encoders: 8200.

O instalador troca caminhos fixos do template para a pasta correta do usuário no Mac atual.
