# Registro do ambiente de desenvolvimento

Em 06/10/2026, o Ubuntu existente estava cadastrado no WSL, mas seu `ext4.vhdx` não existia no caminho registrado. Foram verificados os diretórios de perfil e migração indicados; a pasta `Desktop/vps` continha uma chave SSH válida da Oracle, não um backup do disco Ubuntu.

Com autorização do usuário, foi criado um ambiente separado Ubuntu 24.04 no disco D, nome `Ubuntu-AgroLab`, preservando o cadastro antigo. A distribuição nova iniciou e disponibiliza OpenSSH.

```powershell
wsl -d Ubuntu-AgroLab
```

`Ubuntu-AgroLab` também foi definido como distribuição padrão; `wsl` abre esse ambiente. O atalho antigo Ubuntu continua associado ao cadastro cujo VHDX está ausente.

Na validação inicial foi usado `wsl -d Ubuntu-AgroLab -u root` para inspeção. A configuração de usuário interativo/senha do ambiente novo permanece a cargo do usuário; o Ubuntu antigo não foi apagado ou declarado recuperado.

O Docker Desktop 4.72.0 falhou em sockets AF_UNIX temporários do Windows: primeiro dockerInference, depois engine.sock no serviço de segredos. A renomeação pelo Windows falhou inclusive em tentativa administrativa. O Ubuntu novo conseguiu acessar esses arquivos via DrvFS. Com os processos do Docker parados, foram preservados os dois diretórios temporários:

- `C:\Users\USUARIO\AppData\Local\Docker\run.agrolab-preserved-20261006-wsl`
- `C:\Users\USUARIO\AppData\Local\docker-secrets-engine.agrolab-preserved-20261006-wsl`

Após a inicialização, o Docker recriou os diretórios e o Engine Linux 29.4.2 respondeu pela API. Não foi executado reset de fábrica, prune, remoção de volumes ou exclusão de VHDX. A recuperação removeu o bloqueio dos sockets preservando seus arquivos; o erro pode reaparecer após outra interrupção que deixe sockets antigos, pois a limitação de acesso do Windows não foi corrigida por atualização do sistema.

`docker run --rm hello-world` passou, confirmando download e execução de container. Os containers locais preexistentes do Zelo voltaram a executar; seus bancos e volumes foram preservados.

Foi criado um cluster PostgreSQL exclusivo em `.runtime/pgdata`, usando os binários 17.4 existentes. Porta 54329, escuta somente 127.0.0.1, autenticação SCRAM e senha aleatória local. Foram criados `agrolab` e `agrolab_test`; os bancos preexistentes não foram alterados. `.runtime` e `.env` são ignorados pelo Git.

Após recuperar o Docker, esse cluster provisório foi encerrado com pg_ctl para liberar a porta 54329 ao PostgreSQL 18 do Compose. Seus arquivos continuam em `.runtime/pgdata`.

`docker compose up --build -d` passou nesta máquina x64. PostgreSQL 18.6, API e Mailpit ficaram saudáveis; migração saiu com código 0. `/health/ready`, Swagger local e Mailpit retornaram HTTP 200. O banco local confirmou schema `1d36578fa9a0`. O Compose está ativo; `docker compose stop` encerra os serviços mantendo seu volume.

O uv apresentou falha ao persistir temporários entre discos C e D. Cache e TMP/TEMP foram definidos para `.uv-cache` no mesmo disco do projeto somente nos comandos de instalação. Não foram alteradas variáveis globais do Windows.

A Oracle foi acessada por SSH com a chave existente indicada pelo usuário. Foram inspecionados arquitetura, RAM, disco e containers. O Docker da VPS funciona e é administrado via sudo; a chave privada não foi exibida nem copiada para arquivos do projeto.
