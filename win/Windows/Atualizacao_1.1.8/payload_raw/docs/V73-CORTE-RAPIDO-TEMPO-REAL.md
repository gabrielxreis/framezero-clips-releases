# v73 — corte rápido + transcrição mais perto de tempo real

Configuração padrão:

- transcricao=vps
- engine=faster-whisper
- endpoint=/transcribe-fastwhisper
- blocos ao vivo=2.5s
- análise de corte a cada 3s
- detector local de corte roda antes da IA/VPS

Mudança importante: a IA da VPS/DeepSeek não segura mais o corte procurando uma opção melhor.
O detector rápido dispara o clipe primeiro; a IA fica apenas como reforço/refino.

