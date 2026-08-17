# FrameZero — Referência do Instalador Windows

Leia este arquivo **antes** de mexer em qualquer `.bat` deste repositório.
Ele existe para não repetir erros já pagos em suporte.

---

## 1. Mapa dos arquivos (quem chama quem)

```
INICIAR_INSTALADOR_WINDOWS.bat          (bootstrap que o cliente clica)
  └─ gera %TEMP%\FrameZero_PreClean_And_Start.ps1
       ├─ mata python/obs, limpa %TEMP%\FrameZeroOnlineInstaller e caches
       ├─ baixa installers/FrameZero_Installer_1.0_Windows.bat
       │    -> %USERPROFILE%\Downloads\FrameZero_Installer_Atualizado.bat
       └─ executa esse .bat
            └─ FrameZero_Installer_1.0_Windows.bat (instalador real)
                 ├─ :LOAD_MANIFEST     baixa latest/version.json
                 ├─ :SELF_UPDATE_IF_NEEDED  (compara online_installer_version)
                 └─ :DOWNLOAD_AND_RUN  baixa ZIP -> extrai -> roda .bat interno
```

Cópias que precisam ficar **idênticas** (o cliente recebe a de `installers/`):

- `FrameZero_Installer_1.0_Windows.bat` (raiz)
- `installers/FrameZero_Installer_1.0_Windows.bat`

> Regra: editou um, copie para o outro no mesmo commit.
> `cp FrameZero_Installer_1.0_Windows.bat installers/FrameZero_Installer_1.0_Windows.bat`

Manifests: `latest/version.json` é o que o instalador lê. `version.json` (raiz) é legado —
sempre confira qual URL o script está usando antes de mexer.

---

## 2. Armadilhas de `.bat` que já causaram bug real

### 2.1 `%ERRORLEVEL%` dentro de bloco `( )` — **o erro clássico**

O arquivo abre com `setlocal EnableExtensions DisableDelayedExpansion`.
Isso significa: **tudo entre parênteses é expandido na hora de LER o bloco**, antes de
qualquer comando dentro dele rodar. Ou seja:

```bat
REM ERRADO — %ERRORLEVEL% vale o valor de ANTES do curl (quase sempre 0)
if not errorlevel 1 (
  curl.exe -fL --output "%OUT%" "%URL%"
  exit /b %ERRORLEVEL%
)
```

Consequência real (bug de 2026): o download falhava com `curl (60)`, a função retornava 0,
o `if errorlevel 1 (echo [ERRO] download failed)` nunca disparava e o script seguia para o
`Expand-Archive` de um ZIP que não existia. O cliente via
`O caminho ...clips_windows.zip não existe` — mensagem que não tem nada a ver com a causa.

Formas certas:

```bat
REM 1) fora de bloco, usando goto
curl.exe -fL --output "%OUT%" "%URL%"
if errorlevel 1 goto FALHOU
exit /b 0

REM 2) dentro de bloco, retorne constante
if errorlevel 1 exit /b 1

REM 3) se precisar do valor, capture fora do bloco
call :ALGO
set "RC=%ERRORLEVEL%"
```

**Nunca** escreva `exit /b %ERRORLEVEL%` nem `if errorlevel 1 exit /b %ERRORLEVEL%`
dentro de `( )`. `exit /b %ERRORLEVEL%` fora de bloco é seguro.

Checagem rápida antes de commitar:

```bash
grep -n "ERRORLEVEL" FrameZero_Installer_1.0_Windows.bat
```

e confirme, para cada ocorrência, que a linha **não** está dentro de parênteses.

### 2.2 Parênteses em `echo` dentro de bloco

Dentro de `( )`, um `)` no texto fecha o bloco. Escape com `^`:

```bat
if errorlevel 1 (
  echo [ERRO] pacote ausente ^(download falhou^).
  exit /b 1
)
```

Fora de bloco, `echo 1) faça isso` funciona sem escape.

### 2.3 `powershell` que falha mas retorna 0

Erro não-terminante do PowerShell **não** gera exit code 1. Se você precisa detectar falha,
force:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { ...; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
```

### 2.4 Nunca confie só no exit code — valide o arquivo

Depois de qualquer download, antes de extrair/executar:

```bat
if not exist "%ZIP_PATH%" ( echo [ERRO] pacote ausente. & exit /b 1 )
```

### 2.5 Caminhos com espaço

Sempre `-LiteralPath` no PowerShell e sempre aspas nas variáveis (`"%VAR%"`).
`C:\Users\Nome Sobrenome\...` já quebrou o updater antes.

---

## 3. Rede / TLS — o erro que NÃO é bug nosso

```
curl: (60) schannel: SEC_E_UNTRUSTED_ROOT (0x80090325)
```

O `curl.exe` do Windows usa o **schannel** (repositório de certificados do Windows).
Se o PC não confia na cadeia do GitHub, o download morre. Causas, em ordem de frequência:

1. Antivírus/firewall com inspeção SSL (Kaspersky, Sophos, ESET, Fortinet, Zscaler).
2. Proxy corporativo com certificado próprio (rede de empresa/igreja com TI).
3. Windows sem atualizações → root CAs desatualizados.

O que o instalador faz hoje: tenta `curl` → cai no PowerShell com TLS 1.2 → se ainda falhar,
mostra mensagem explicando antivírus/proxy e oferece download manual.

**Não** "resolva" isso com `curl -k` nem `--ssl-no-revoke` como padrão: desliga a verificação
e abre o instalador para MITM (o cliente executaria um `.bat`/ZIP arbitrário). Se algum dia
for realmente necessário, tem que ser opção explícita do usuário, avisada na tela.

---

## 4. Checklist antes de commitar mudança no instalador Windows

- [ ] `grep -n "ERRORLEVEL"` — nenhuma ocorrência de `%ERRORLEVEL%` dentro de `( )`
- [ ] Todo download seguido de `if errorlevel 1` **e** `if not exist`
- [ ] `)` escapado como `^)` em `echo` dentro de blocos
- [ ] PowerShell crítico com `$ErrorActionPreference='Stop'` + `try/catch` + `exit`
- [ ] Todas as variáveis de caminho entre aspas
- [ ] Bumpei `CURRENT_INSTALLER_VERSION`, o `title` e os comentários de versão
- [ ] Copiei o arquivo da raiz para `installers/` (ficaram idênticos: `diff -q`)
- [ ] `latest/version.json` → `online_installer_version` continua **maior** que
      `CURRENT_INSTALLER_VERSION`, senão o self-update para de rodar
- [ ] Escrevi `PATCH_V<versao>_<NOME>.txt` descrevendo a mudança
- [ ] Testei em Windows real (ou pedi para o cliente testar) — `.bat` não roda no Mac

## 5. Como testar sem cliente

Em um Windows (VM serve):

```bat
del /f /q "%USERPROFILE%\Downloads\FrameZero_Installer_Atualizado.bat"
rmdir /s /q "%TEMP%\FrameZeroOnlineInstaller"
INICIAR_INSTALADOR_WINDOWS.bat
```

Para simular falha de rede e conferir se a mensagem certa aparece: desligue o Wi-Fi
logo depois do menu, ou aponte `VERSION_URL` para um host inexistente numa cópia local.

---

## 6. Histórico de causas-raiz já diagnosticadas

| Data | Sintoma visto pelo cliente | Causa real | Correção |
|---|---|---|---|
| 2026-08 | `clips_windows.zip não existe` + `Expand-Archive InvalidArgument` | `curl (60)` SEC_E_UNTRUSTED_ROOT + `exit /b %ERRORLEVEL%` dentro de bloco engolindo o erro | fallback PowerShell/TLS 1.2, `if not exist`, mensagem clara, `exit /b 1` (v1.0.112) |
