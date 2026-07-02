# v81d — HTML limpo

Esta build removeu os arquivos antigos de painel standalone da raiz da pasta:

- obs-panel-v67-standalone.html
- obs-panel-v78-standalone.html
- obs-panel-v79-standalone.html
- obs-panel-v80-standalone.html
- obs-panel-v81-standalone.html

Agora o painel oficial fica somente em:

- app/obs-panel.html

O arquivo `app/overlay.html` foi mantido porque é o overlay usado pelo sistema, não uma versão duplicada do painel.
