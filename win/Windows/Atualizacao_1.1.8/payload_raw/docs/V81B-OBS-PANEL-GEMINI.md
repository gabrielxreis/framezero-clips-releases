# V81B — Painel OBS corrigido para Gemini

Correção aplicada no `app/obs-panel.html` e no `obs-panel-v81-standalone.html`.

## O que mudou

- O painel agora mostra **Análise de cortes por IA** com opção **Desligado** e **Gemini Free**.
- Campo para colar a chave Gemini API (`AIza...`).
- Botão **Como criar minha chave Gemini?** apontando para o tutorial oficial.
- Modos de economia de créditos:
  - **Econômico**: janela de 3 minutos, análise a cada 60 segundos.
  - **Equilibrado**: janela de 2 minutos, análise a cada 45 segundos.
  - **Agressivo**: janela de 3 minutos, análise a cada 30 segundos.
- Quando Gemini está ativo, ele vira o **diretor de cortes**: o detector local não dispara primeiro. O Gemini observa o contexto maior e só libera corte quando o raciocínio estiver fechado.
- Se o Gemini decidir que o trecho não é viral ou ainda está incompleto, o sistema não corta nada naquela rodada.
- Se a chave falhar, faltar internet ou bater limite, o detector local entra como fallback.

## Padrão recomendado

Use:

- Transcrição: **Padrão / MLX Whisper local**
- Modo de corte: **Corte Seguro**
- Análise IA: **Gemini Free**
- Economia: **Econômico**

Esse modo economiza chamadas porque envia blocos maiores de texto, em vez de mandar frase por frase.
