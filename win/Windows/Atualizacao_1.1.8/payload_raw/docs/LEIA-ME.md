# FrameZero Clips — OBS com transcrição, cortes, vertical e áudio integrado

## Arquivos para clicar

Na raiz da pasta ficam poucos itens:

- `INSTALAR-MAC.command`: instala ou atualiza tudo.
- `INICIAR.command`: criado depois da instalação; fica como plano B/manual.
- `LEIA-PRIMEIRO-MAC.txt`: instrução rápida caso o macOS bloqueie.

Os arquivos técnicos ficam separados:

- `app/`: painel, servidor, overlay, requisitos e configuração.
- `config/perfil-obs/`: perfil OBS pronto.
- `plugins/`: instaladores locais opcionais de BlackHole, Aitum Vertical, Aitum Multistream e Face Tracker.
- `docs/`: manual.

## O que o instalador Mac faz

A opção **2) Atualizar limpo** apaga o antigo e reescreve tudo:

- ambiente Python;
- atalho `INICIAR.command` como plano B;
- inicializador automático do FrameZero quando o OBS abrir;
- perfil OBS `FrameZero Clips`;
- Face Tracker;
- Aitum Vertical / Vertical Canvas;
- Aitum Multistream;
- BlackHole 2ch para áudio do OBS.

## BlackHole integrado

O instalador tenta instalar o BlackHole 2ch automaticamente, sem o usuário precisar baixar manualmente.

Ordem de instalação:

1. Se existir um `.pkg` em `plugins/blackhole/macos/`, usa esse arquivo local.
2. Se não existir, baixa automaticamente da release oficial do GitHub `ExistentialAudio/BlackHole`.
3. Se o GitHub falhar, tenta Homebrew (opcional; esta versao nao instala automaticamente) como fallback.

Depois de instalar o BlackHole, pode ser necessário reiniciar o Mac uma vez para o driver aparecer.

Configuração no OBS:

1. OBS > Ajustes > Áudio > Avançado.
2. Em **Monitoring Device**, escolha **BlackHole 2ch**.
3. No mixer do OBS, abra **Propriedades avançadas de áudio**.
4. Na fonte do microfone/pregação, escolha **Monitor and Output**.
5. No painel do FrameZero, clique no alto-falante e use **Áudio do OBS via BlackHole**.

## Aitum Vertical integrado

O instalador também instala o Aitum Vertical / Vertical Canvas oficial.

Depois de instalar, abra o OBS e procure em:

- Docks > Aitum Vertical
- Docks > Vertical Scenes
- Docks > Vertical Output
- Docks > Vertical Canvas

Esse é o painel/canvas vertical acoplável dentro do OBS.


## Aitum Multistream integrado

A partir da v17, o instalador também instala o **Aitum Multistream** oficial.

Ele adiciona ao OBS uma área/painel para configurar várias saídas de transmissão, como YouTube, Twitch, TikTok, Instagram Live via RTMP e outros destinos compatíveis. Quando usado junto com o Aitum Vertical, ele permite controlar saídas horizontais e verticais no mesmo OBS.

Depois de instalar, abra o OBS e procure em:

- Docks > Aitum Multistream
- Ferramentas > Aitum Multistream
- Docks > Multistream

As chaves de transmissão continuam sendo configuradas pelo usuário dentro do OBS/Aitum Multistream. O FrameZero não salva nem mexe nas chaves de live.

Para instalação offline, coloque o arquivo `aitum-multistream-macos-universal.pkg` em `plugins/aitum-multistream/macos/` e rode `Atualizar limpo`.

## Face Tracker integrado

O instalador instala o Face Tracker correto para Mac M1/M2/M3/M4 ou Intel.

No OBS:

1. Clique com botão direito na fonte da câmera.
2. Filtros.
3. Em **Filtros de Efeito**, clique no `+`.
4. Escolha **Face Tracker**.


## Corte automático sem OpenAI

A partir da v15, o FrameZero clipa automaticamente mesmo sem chave da OpenAI.

O detector local analisa a transcrição ao vivo e pontua momentos por:

- palavras e frases fortes;
- perguntas e chamadas diretas;
- emoção dominante;
- repetição e ênfase;
- frases curtas/médias com potencial de Reels/Shorts.

No painel, clique no ícone da chave/automação e escolha a sensibilidade:

- **Mais cortes**: limiar 55;
- **Normal**: limiar 65;
- **Só fortes**: limiar 78.

A OpenAI virou opcional. Com chave, ela melhora títulos e razões; sem chave, o corte automático local continua ativo.

## Uso diário

Depois da instalação, o operador abre **apenas o OBS**.

O instalador cria um LaunchAgent do macOS chamado `com.reiscrew.framezero.obswatcher`. Ele fica observando o OBS em segundo plano. Quando o OBS abre, o FrameZero inicia automaticamente sem precisar clicar no `INICIAR.command`. Quando o OBS fecha, o FrameZero é encerrado para não consumir recursos.

O `INICIAR.command` continua existindo só como plano B/manual para suporte.

Logs de diagnóstico ficam em:

- `logs/auto-start.log`
- `logs/framezero-server.log`
- `logs/launchagent.err.log`


## Inicialização automática v17

A partir da v16, não precisa clicar em `INICIAR.command` no dia a dia. Abra só o OBS. O FrameZero sobe sozinho em segundo plano pelo LaunchAgent do macOS.

Se algo não iniciar, use `INICIAR.command` como plano B e veja os logs em `logs/`.

## Modo vertical sem preview do corte

A partir da v16, o preview do corte foi removido para deixar a operação mais limpa.

O Aitum Vertical continua sendo instalado para fornecer o canvas/painel vertical real dentro do OBS. O FrameZero fica responsável pela transcrição, detecção local e clipes automáticos.

No OBS, use o painel/canvas do Aitum Vertical para a operação vertical.

## Face Tracker

O botão **Seguir pastor** agora diferencia duas situações:

- plugin Face Tracker instalado, mas filtro ainda não foi colocado na câmera;
- plugin realmente ausente/não carregado pelo OBS.

O Face Tracker é um filtro da **fonte da câmera**, não da cena inteira. Por isso, na primeira vez, adicione em: fonte da câmera > Filtros > Filtros de Efeito > + > Face Tracker. Depois o botão do FrameZero consegue ligar/desligar esse filtro.


## Transcrição melhorada — v18

A transcrição local agora usa o modelo `small` por padrão, em vez de `base`, com leitura em blocos maiores, beam search mais preciso e normalização automática do volume antes de enviar ao Whisper. Isso melhora bastante quando o áudio vem do OBS/BlackHole, microfone baixo ou som de igreja com reverberação.

Se o Mac ficar pesado, troque em `app/config.json`:

```json
"modelo": "base"
```

Se quiser mais precisão e aceitar mais uso de CPU, use:

```json
"modelo": "medium"
```


---

## Atualização v19 — sem modo vertical automático + Recomeçar

- O modo vertical do FrameZero agora vem desativado por padrão. O Aitum Vertical pode continuar instalado no OBS, mas o FrameZero não cria nem força cena vertical automaticamente.
- A proporção padrão dos cortes finais voltou para `original`. Se quiser vertical, selecione 9:16 manualmente na hora de gerar cortes.
- O botão **Recomeçar** limpa tudo que foi capturado na sessão atual: transcrição, cortes, capítulos, estado de gravação do painel e lista de momentos.
- Se no fim da gravação nenhum momento tiver sido marcado ao vivo, o botão **Gerar Cortes** faz uma análise local da transcrição e cria candidatos automaticamente, em vez de parar com “nenhum momento para gerar”.


## v20 — OBS abre o FrameZero junto

Depois da instalação, o usuário não precisa clicar no `INICIAR.command` no dia a dia. Ao abrir o OBS, o LaunchAgent do macOS detecta o OBS aberto e executa automaticamente o `INICIAR.command` em uma janela do Terminal. Essa janela fica visível para mostrar logs e precisa permanecer aberta durante a gravação/transmissão.

Se o OBS for fechado, o FrameZero também é encerrado.


## v21

- Ao abrir o OBS, o FrameZero abre o INICIAR.command em uma janela do Terminal automaticamente.
- O Replay Buffer agora é tratado de forma mais segura: erro 500 do OBS não gera traceback e o sistema tenta iniciar o buffer antes de salvar clipes.
- Detector local reduz duplicidade de cortes na mesma janela de análise.

## v22 — Pacote viral/emocional por corte

A v22 melhora o corte automático local para mensagens de pregação. O detector agora procura não só palavras fortes, mas também sinais que costumam performar melhor em cortes:

- história sendo contada;
- tensão antes da virada;
- pico emocional ou espiritual;
- frase de presença/voz forte;
- aplicação direta para quem está assistindo;
- momento com potencial viral para Reels, Shorts e TikTok.

Quando o OBS salva um clipe ao vivo ou quando o operador clica em **Gerar Cortes** no fim, cada corte agora ganha uma pasta própria dentro de uma pasta principal:

```text
FrameZero_Cortes_Finais_2026-06-26_15-30/
  00-03-12_score-085_quando-deus-entra-na-historia/
    video.mp4
    legenda.srt
    metadata.json
    resumo-do-corte.txt
    legenda-instagram.txt
    legenda-tiktok.txt
```

Para clipes salvos durante a live via Replay Buffer, a pasta principal fica como:

```text
FrameZero_Cortes_AoVivo_2026-06-26_15-30/
```

Cada pasta de corte contém:

- o vídeo;
- a legenda `.srt`;
- título;
- score viral;
- emoção dominante;
- função narrativa;
- razão do corte;
- legenda pronta para Instagram;
- legenda pronta para TikTok;
- `metadata.json` para integração futura com outros sistemas.

A OpenAI continua opcional. Sem chave, o FrameZero gera tudo localmente.


## v23 — Transcrição contínua

Esta versão reduz a transcrição picotada/cortada. O FrameZero agora usa blocos maiores de áudio, junta os segmentos do Whisper em frases mais naturais, segura pontas de frases incompletas para unir com o próximo bloco e desativa o VAD agressivo que cortava falas em pausas de pregação.

Configuração padrão desta versão:
- modelo: small
- bloco_segundos: 14
- beam_size: 7
- transcrição local/offline

Se o Mac aguentar e a prioridade for máxima precisão, pode trocar `modelo` para `medium` em `app/config.json`.


---

## Transcrição pela VPS Whisper

Esta versão vem configurada para usar a VPS Whisper do FrameZero:

- URL: `http://2.25.157.230:8000/transcribe`
- Token: salvo localmente em `app/config.json`
- Modo: `transcricao_modo = vps`

Durante a gravação, o FrameZero envia blocos de áudio para a VPS e recebe a transcrição de volta. Se a VPS falhar ou demorar, o sistema cai automaticamente para o Whisper local, desde que `vps_fallback_local` esteja ativo.

A VPS deve aceitar `POST multipart/form-data` com o arquivo de áudio no campo `file` ou `audio` e retornar JSON com pelo menos um destes campos: `text`, `texto`, `transcription` ou `transcricao`. Se retornar `segments`, o FrameZero também aproveita os tempos dos segmentos.


---

## VPS Whisper configurada

Esta versão usa a VPS Whisper como modo principal de transcrição:

```txt
http://2.25.157.230:8000/transcribe
```

A chave configurada é enviada nos headers compatíveis com a API. Se a VPS falhar, o FrameZero volta automaticamente para o Whisper local.

A integração completa está em `docs/OBS-WHISPER-API.md`.


---

## Modo Zero Config

Esta versão já vem pronta para o usuário final:

- VPS Whisper configurada: `http://2.25.157.230:8000/transcribe`.
- Chave configurada: `DEFINA_FZ_VPS_TOKEN`.
- FrameZero inicia automaticamente quando o OBS abre.
- Perfil OBS `FrameZero Clips` é criado automaticamente.
- Gravação em MOV para evitar erro/corrupção.
- Replay Buffer habilitado com 120 segundos.
- Cortes automáticos locais ativos sem OpenAI.
- Pastas por corte com vídeo, SRT, metadata e legendas para Instagram/TikTok.
- Modo vertical desligado por padrão.
- Botão Recomeçar disponível no painel.

Uso do cliente: abrir o OBS e gravar. O restante já sobe junto.

Observação: chaves de transmissão do YouTube/TikTok/Instagram continuam sendo configuradas dentro do próprio OBS/Aitum, por segurança. O FrameZero não salva chave de live.


## Transcrição em tempo real via VPS Whisper

Esta versão vem em modo zero config usando a VPS Whisper:

- URL: `http://2.25.157.230:8000/transcribe`
- Chave: já configurada internamente
- Modo: VPS em tempo real
- Blocos ao vivo: 5 segundos
- Fallback: Whisper local se a VPS falhar

Ao abrir o OBS, o FrameZero sobe junto. Quando iniciar gravação/transmissão, ele captura o áudio, envia pequenos blocos para a VPS e mostra a transcrição no painel.

Se a VPS estiver lenta, a transcrição pode atrasar. Para ficar realmente ao vivo, a VPS precisa responder cada bloco em poucos segundos.

---

## v28 — Diagnóstico automático de áudio e VPS

Esta versão força automaticamente o **BlackHole 2ch** como entrada de áudio quando ele existir no Mac. Assim o usuário não precisa escolher dispositivo manualmente e evita o erro comum de o FrameZero ficar ouvindo o “padrão do sistema” em vez do áudio do OBS.

No painel aparecem dois indicadores:

- **Áudio**: mostra se está entrando sinal de áudio de verdade.
- **VPS**: mostra se a VPS Whisper respondeu ou se o sistema caiu para fallback local.

Fluxo esperado:

1. OBS envia/monitora a fonte da pregação para o **BlackHole 2ch**.
2. FrameZero captura o BlackHole automaticamente.
3. FrameZero envia blocos de 5s para `http://2.25.157.230:8000/transcribe`.
4. A VPS devolve o texto.
5. O painel mostra a transcrição e detecta cortes.

Se aparecer **Áudio: sem sinal**, confira no OBS:

- Ajustes > Áudio > Avançado > Dispositivo de monitoramento = BlackHole 2ch
- Mixer > Propriedades avançadas de áudio > fonte da pregação = Monitorar e enviar saída

Se aparecer **VPS: offline/fallback**, o sistema continua funcionando com Whisper local, mas a VPS não respondeu dentro do tempo configurado.


## VPS Whisper + IA DeepSeek

Esta versão vem pré-configurada para usar a VPS `http://2.25.157.230:8000`. O FrameZero envia áudio para `/transcribe` e texto acumulado para `/analyze-text`, usando o header `x-api-key: DEFINA_FZ_VPS_TOKEN`. Se a VPS falhar, o sistema volta para o modo local automaticamente.


## BlackHole já instalado

Se o Mac já tiver BlackHole 2ch instalado, o instalador não reinstala. Ele apenas mantém o driver existente e configura o FrameZero para usar BlackHole como entrada principal.


## Ajuste v31 — sem MKV

O perfil FrameZero Clips agora grava em MOV no OBS, porque alguns Macs/editores estavam apresentando problema com MKV.

Os cortes finais continuam saindo como MP4 H.264/AAC dentro da pasta de cada corte:

- video.mp4
- legenda.srt
- metadata.json
- legenda-instagram.txt
- legenda-tiktok.txt
- resumo-do-corte.txt

Se um clipe ao vivo vier como MOV, ele fica preservado na pasta do corte. Os cortes finais gerados pelo botão Gerar Cortes são sempre normalizados em MP4.


## VPS Whisper + IA já configurada

Esta versão já vem configurada para usar a API:

```txt
http://2.25.157.230:8000
```

Endpoints usados automaticamente:

```txt
GET /health
POST /transcribe
POST /analyze-text
```

Header usado pelo plugin:

```txt
x-api-key: DEFINA_FZ_VPS_TOKEN
```

A IA principal da VPS é `criador-cristao:latest`, rodando via Ollama internamente na VPS. O usuário final não precisa configurar nada disso.


## v33 — Transcrição em tempo real

- Força BlackHole de entrada com `max_input_channels > 0`.
- Usa blocos de 5 segundos para a VPS Whisper.
- A análise de cortes por IA roda em segundo plano, sem travar a transcrição.
- Se o áudio estiver entrando no BlackHole, o painel deve mostrar texto alguns segundos depois da fala.


## v34 — Transcrição realmente ao vivo

Esta versão usa modo híbrido por padrão:

- **Ao vivo no painel:** Whisper local leve em blocos curtos de 2,5 segundos, para o texto aparecer rápido.
- **VPS:** continua configurada para análise de cortes, score, título, hook e refinamento/finalização.

Importante: a VPS via `POST /transcribe` recebe arquivos em blocos, então não é streaming palavra por palavra. Para sensação de tempo real, o FrameZero usa o Mac para mostrar a fala rapidamente e usa a VPS sem travar a tela.


## Configurações de transcrição e duração dos cortes

No painel do FrameZero, o botão de engrenagem abre as configurações principais:

- **Whisper local**: roda a transcrição e os cortes no próprio Mac/OBS, como nas versões anteriores. É o modo padrão e não exige VPS.
- **Minha VPS**: permite colocar a URL base da VPS e a chave `x-api-key`. O plugin envia para `/transcribe` e usa `/analyze-text` quando disponível.

A duração dos cortes também pode ser ajustada no painel. O padrão recomendado é:

- mínimo: **15 segundos**
- máximo: **45 segundos**

Esses valores controlam os cortes finais gerados no fim da gravação e ajudam a manter os vídeos no formato ideal para Reels, Shorts e TikTok.


## Configurações com copiar e colar

Na engrenagem do painel, os campos de URL da VPS e chave agora aceitam copiar/colar normalmente.
Também há botões **Colar** ao lado dos campos e uma caixa **Colar configuração completa** para colar tudo de uma vez, por exemplo:

```txt
URL: http://2.25.157.230:8000
Chave: DEFINA_FZ_VPS_TOKEN
Mínimo: 15
Máximo: 45
```

Depois clique em **Ler config colada** e **Salvar**.


## v37 — VPS sem /analyze-text

Se a VPS ainda não tiver o endpoint `/analyze-text`, o FrameZero não mostra erro repetido. Ele continua transcrevendo pela VPS e usa o detector local de cortes automaticamente.


## v38 — API final da VPS

O plugin vem configurado para usar `http://2.25.157.230:8000` com `x-api-key: DEFINA_FZ_VPS_TOKEN`, endpoints `/health`, `/transcribe` e `/analyze-text`. A análise envia `text`, `start_time` e `end_time`. Score 80+ vira possível corte; 90+ vira corte forte.


---

## OBS Detect integrado

O instalador também integra o plugin oficial **OBS Detect** (`royshil/obs-detect`) para detecção/rastreamento de objetos e rostos dentro do OBS.

Ele é instalado como plugin nativo do OBS e deve aparecer como filtro em fontes de vídeo. No OBS, use:

```txt
Fonte de vídeo > Filtros > Filtros de Efeito > + > Detect / OBS Detect
```

O instalador não reinstala se o OBS Detect já estiver instalado na versão atual. Ele só atualiza quando encontra uma versão mais antiga.

Para instalação offline, coloque o pacote Mac dentro de:

```txt
plugins/obs-detect/macos/obs-detect-0.0.3-macos-universal.pkg
```

Depois rode `INSTALAR-MAC.command` e escolha `2) Atualizar limpo`.


## Corte exato automático na gravação completa

A partir desta versão, o FrameZero não salva apenas o “momento” aproximado. Ele calcula a minutagem ideal do corte na gravação completa, buscando uma janela com gancho, pico emocional/viral e fechamento.

Padrão de duração:

- mínimo: 15 segundos
- máximo: 45 segundos

No fim da gravação, ao clicar em **Gerar Cortes**, cada corte sai em uma pasta própria com:

- `video.mp4` — trecho já cortado no ponto ideal;
- `legenda.srt`;
- `metadata.json` com início, fim, duração, score e origem;
- `legenda-instagram.txt`;
- `legenda-tiktok.txt`;
- `resumo-do-corte.txt`.

A pasta principal também recebe:

- `mapa-dos-cortes.csv`;
- `mapa-dos-cortes.txt`.

Esses mapas mostram a minutagem exata de cada corte para reduzir o trabalho na pós.


## v41 — cortes respeitam tempo configurado

O FrameZero agora recorta o Replay Buffer bruto e entrega `video.mp4` somente dentro da duração configurada no painel. O padrão é 15s a 45s.

## v42 — Corte por SRT / Timecode

O FrameZero agora usa a minutagem da transcrição/SRT como base para definir início e fim dos cortes. Isso evita que arquivos do Replay Buffer saiam com 2 minutos quando o painel está configurado para 15s a 45s.

O arquivo bruto do Replay Buffer pode continuar com 120s por segurança, mas o `video.mp4` entregue em cada pasta é recortado com FFmpeg usando o timecode correto.


## SRT PT-BR com preset

O SRT automático sai em português brasileiro, com até 37 caracteres por legenda, linha única por cue e copia o preset `GAB USA Subtitle.preset` para a pasta de cada corte.


## Legendas automáticas

Cada corte gera `legenda.srt` em pt-BR com 37 caracteres por cue e linha única. O estilo visual equivalente ao preset antigo é gerado em `legenda.ass` com Poppins, tamanho 13 e bold, sem precisar copiar arquivo `.preset`.

---

## v48 — Corte não termina no meio do contexto

Agora o FrameZero evita finalizar o corte no meio da conclusão da frase. Ele usa o timecode do SRT/transcrição para procurar um fechamento natural antes de exportar o vídeo final.

Se o trecho ideal passar do tempo máximo configurado, o sistema não entrega um corte maior: ele desloca o início para frente e preserva o pico + finalização do contexto.

---

## v49 — Contexto de pregação

Os cortes agora entendem melhor quando o pregador está contando uma história. O sistema evita exportar apenas uma ilustração sem conclusão e prioriza o momento em que a história vira aplicação, palavra direcionada ou ministração.


## v50 — Música/Pregação + VPS quase em tempo real

- Modo VPS puro: não carrega Whisper local.
- Blocos ao vivo via VPS reduzidos para 4s.
- Detecta automaticamente se o trecho é música/louvor ou pregação.
- Música prioriza refrão, ponte, clímax emocional e partes bonitas.
- Pregação prioriza palavra direcionada, aplicação e contexto fechado.


## v53 - Whisper local PT-BR contextual

No modo híbrido, o Whisper local não usa mais o modelo tiny como padrão. Agora usa base, idioma fixo pt-BR, prompt contextual cristão e glossário bíblico/louvor para errar menos palavras. A VPS continua responsável pelo refino e decisão dos cortes.


## v54 — Switch Pregação/Música

O painel agora tem um switch único no topo: Pregação ou Música. A escolha é manual, salva no config e desativa a detecção automática para evitar conflito.


## v55 — Música sem prompt hallucinado

No modo Música, o Whisper local usa prompt mínimo e não aplica correções de pregação na letra cantada. Também remove vazamentos de instrução interna no SRT.

## v57 — Letra online via Ollama conectado à internet

No modo **Música**, o plugin agora envia para a VPS/Ollama instruções para usar internet como referência de letra, quando disponível. A regra é: **a internet sugere, o áudio manda**. O sistema não deve trocar a letra se a confiança for baixa e deve preservar louvor espontâneo.


## v58 — Whisper Pro / GPU

Configurações agora têm switches para **Whisper Normal/Whisper Pro** e **Sem GPU/Tenho GPU**. Whisper Pro usa `large-v3-turbo`; com GPU usa CUDA/float16, sem GPU cai para CPU/int8 com aviso de lentidão.


## v59 — Híbrido local + refino na VPS

No modo híbrido, o Whisper local faz a transcrição rápida/preview. A VPS/Ollama recebe o texto e contexto para refinar legenda, entender música ou pregação e decidir cortes. O áudio não é enviado para `/transcribe` nesse modo; ele só vai para `/transcribe` no modo VPS puro.

## v71 — VPS faster-whisper PT-BR

A transcrição oficial agora é fixa em VPS com `engine=faster-whisper`. O endpoint padrão é `http://2.25.157.230:8000/transcribe-fastwhisper`; o endpoint alternativo permitido é `http://2.25.157.230:8000/transcribe`. Outros motores/endpoints foram removidos do fluxo. Blocos ao vivo: 12s por padrão, com 15s como opção segura para mais contexto.


## Atualização v72 — VPS faster-whisper em tempo real

A transcrição ao vivo agora usa micro-blocos de 3s na VPS. Blocos de 12s/15s foram removidos do fluxo ao vivo porque geravam atraso. Endpoints permitidos: `/transcribe-fastwhisper` e `/transcribe`.


## Atualização v73 — corte rápido em tempo real

- Micro-blocos VPS reduzidos para 2.5s.
- Análise de corte a cada 3s.
- Detector local de cortes roda antes da IA da VPS.
- A IA não segura mais o clipe procurando algo melhor.
- Cooldown reduzido para 18s.

