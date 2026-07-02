# V81C — Instalador inteligente

Esta revisão ajusta o `INSTALAR-MAC.command` para economizar tempo em reinstalações e atualizações. Agora a opção padrão é **Instalação inteligente / atualizar**.

## O que mudou

- O instalador verifica se o venv `.framezero/venv` já existe e usa Python compatível.
- Verifica se os módulos principais já estão instalados:
  - `mlx_whisper`
  - `numpy`
  - `sounddevice`
  - `websockets`
  - `obsws_python`
  - `requests`
  - `openai`
  - `scipy`
- Salva um hash do `app/requirements.txt` em `.framezero/.requirements.sha256`.
- Se o `requirements.txt` não mudou e os módulos estão OK, pula a reinstalação pesada.
- Faz checagem de atualização do `pip`/pacotes no máximo uma vez a cada 24h por padrão.
- Se quiser forçar a atualização completa, rode no Terminal:

```bash
FRAMEZERO_FORCE_UPDATE=1 ./INSTALAR-MAC.command
```

- Se quiser mudar a frequência da checagem de versões, use:

```bash
FRAMEZERO_UPDATE_TTL_HOURS=6 ./INSTALAR-MAC.command
```

## Resultado esperado

Na primeira instalação, ele instala tudo normalmente. Nas próximas instalações, basta pressionar ENTER na opção padrão `Instalação inteligente / atualizar`.

Nas próximas vezes, se já estiver tudo pronto, ele mostra:

```text
Dependências já instaladas e conferidas recentemente. Pulando instalação para economizar tempo.
```

Se faltar pacote, se o requirements mudar ou se passar o intervalo de checagem, ele atualiza somente o necessário com:

```bash
pip install --upgrade --upgrade-strategy only-if-needed -r app/requirements.txt
```
