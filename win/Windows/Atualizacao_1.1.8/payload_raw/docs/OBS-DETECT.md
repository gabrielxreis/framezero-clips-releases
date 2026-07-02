# OBS Detect integrado ao FrameZero

Plugin oficial: https://github.com/royshil/obs-detect

Função: detecção/rastreamento de objetos dentro do OBS, com suporte a detecção de face, tracking, pixelate/masking e exportação de detecções.

## Instalação

O instalador do FrameZero procura se o OBS Detect já está instalado em:

- `~/Library/Application Support/obs-studio/plugins/`
- `/Library/Application Support/obs-studio/plugins/`

Se já estiver na versão atual, ele não reinstala. Se estiver ausente ou mais antigo, instala/atualiza.

## Offline

Coloque o arquivo `.pkg` em:

```txt
plugins/obs-detect/macos/
```

Nome recomendado:

```txt
obs-detect-0.0.3-macos-universal.pkg
```

## Uso no OBS

Depois de abrir o OBS:

```txt
Fonte de vídeo > Filtros > Filtros de Efeito > + > OBS Detect / Detect
```

Se não aparecer, feche e abra o OBS novamente e confira o log do OBS por `obs-detect`.
