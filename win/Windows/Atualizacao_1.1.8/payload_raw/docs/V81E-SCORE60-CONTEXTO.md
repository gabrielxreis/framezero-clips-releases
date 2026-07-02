# V81E Score 60+ Contexto

Ajuste feito para corte em tempo real com Gemini/rating 60+.

Mudanças:
- Mantém a base v81e.
- Mantém keyfix da Google/Gemini.
- Score/rating 60+ já pode gerar corte ao vivo.
- Prompt do Gemini ficou menos rígido: aceita gancho, ilustração, história e contexto útil para post, não apenas clipe viral 90+.
- Gemini mínimo de caracteres reduzido para detectar trechos antes.
- Fallback contextual leve para casos em que Gemini responde `wait_more`, mas já existe um bloco com assunto claro como persistência/negociação/história.
