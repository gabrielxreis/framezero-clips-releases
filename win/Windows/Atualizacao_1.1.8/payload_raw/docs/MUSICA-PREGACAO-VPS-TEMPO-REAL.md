# FrameZero v50 — Música/Pregação + VPS quase em tempo real

## Transcrição via VPS

Quando o modo selecionado for `Minha VPS`, o FrameZero não carrega Whisper local.
Para reduzir atraso, os blocos ao vivo via VPS foram reduzidos para 4 segundos.

Config padrão:

```json
{
  "transcricao_modo": "vps",
  "vps_bloco_segundos_ao_vivo": 4.0,
  "vps_timeout_seg": 45,
  "vps_fallback_local": false
}
```

Observação: HTTP por arquivo não é palavra por palavra. Para ficar realmente instantâneo, a VPS precisa de um endpoint streaming/WebSocket. Esta versão deixa o fluxo quase em tempo real sem carregar o Mac.

## Detecção automática: música ou pregação

O sistema classifica cada bloco como:

- `pregacao`
- `musica`

### Pregação

Prioriza:

- palavra direcionada;
- aplicação;
- conclusão de história;
- ministração;
- frase de impacto.

Evita cortar história solta sem sentido.

### Música/louvor

Prioriza:

- refrão;
- ponte;
- clímax musical;
- repetição bonita;
- frase cantável;
- ponto de emoção.

Nesse caso, o corte não precisa ter aplicação de pregação. Ele precisa ser bonito, emocional e fechado.
