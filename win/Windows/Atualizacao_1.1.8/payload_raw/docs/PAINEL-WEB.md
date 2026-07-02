# FrameZero v67 — Painel somente por URL

A página principal do plugin roda somente em:

```text
https://clips.framezeroai.com.br/obs
```

Não existe mais `app/painel.html`, redirecionamento local ou fallback HTML.

O aplicativo local continua necessário apenas para fazer a ponte com:

```text
OBS WebSocket
BlackHole
VPS faster-whisper
FFmpeg
WebSocket local ws://localhost:8765
```

No OBS, configure o dock assim:

```text
Docks > Custom Browser Docks

Nome: FrameZero Clips
URL: https://clips.framezeroai.com.br/obs
```

O painel web deve conectar no servidor local do FrameZero usando:

```text
ws://localhost:8765
```
