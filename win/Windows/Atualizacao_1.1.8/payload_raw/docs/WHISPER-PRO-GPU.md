# Whisper Pro / GPU

A v58 adiciona dois switches nas configurações:

- **Whisper local:** Normal ou Whisper Pro
- **Hardware do usuário:** Sem GPU ou Tenho GPU

## Normal
Usa `small` em CPU/int8. É o modo leve para usuários comuns.

## Whisper Pro
Usa `large-v3-turbo`.

- Com GPU: `cuda` + `float16`
- Sem GPU: `cpu` + `int8` como fallback, com aviso de lentidão

O modo VPS continua sem carregar Whisper local. O Whisper local só roda nos modos Local ou Híbrido.
