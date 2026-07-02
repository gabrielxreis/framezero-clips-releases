# V77 - MLX com instalador automático de Python 3.12

Esta versão corrige o problema do Mac rodando Python 3.14.

Se não houver Python 3.10-3.13 compatível, o instalador tenta:

1. usar Homebrew para instalar `python@3.12`, se Homebrew existir;
2. baixar o instalador oficial do Python 3.12 no python.org;
3. instalar o pacote com `sudo installer`;
4. criar o venv `.framezero/venv` usando Python 3.12;
5. instalar `mlx-whisper` dentro do venv.

O `INICIAR.command` também verifica se o venv foi criado com Python incompatível e força reinstalação se necessário.
