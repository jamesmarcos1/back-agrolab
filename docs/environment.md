# Registro do ambiente de desenvolvimento

Em 06/10/2026, o Ubuntu existente estava cadastrado no WSL, mas seu `ext4.vhdx` não existia no caminho registrado. Foram verificados os diretórios de perfil e migração indicados; a pasta `Desktop/vps` continha uma chave SSH válida da Oracle, não um backup do disco Ubuntu.

Com autorização do usuário, foi criado um ambiente separado Ubuntu 24.04 no disco D, nome `Ubuntu-AgroLab`, preservando o cadastro antigo. A distribuição nova iniciou e disponibiliza OpenSSH.

```powershell
wsl -d Ubuntu-AgroLab
```

Na validação inicial foi usado `wsl -d Ubuntu-AgroLab -u root` para inspeção. A configuração de usuário interativo/senha do ambiente novo permanece a cargo do usuário; o Ubuntu antigo não foi apagado ou declarado recuperado.

O Docker Desktop 4.72.0 falhou em sockets AF_UNIX temporários do Windows: primeiro dockerInference, depois engine.sock no serviço de segredos. A pasta de runtime inicial foi preservada em backup e recriada. O segundo diretório recusou renomeação, inclusive em tentativa administrativa. Não foi executado reset de fábrica, prune, remoção de volumes ou exclusão de VHDX. O Docker Desktop ainda precisa de resolução no Windows antes de usar Compose local.

Foi criado um cluster PostgreSQL exclusivo em `.runtime/pgdata`, usando os binários 17.4 existentes. Porta 54329, escuta somente 127.0.0.1, autenticação SCRAM e senha aleatória local. Foram criados `agrolab` e `agrolab_test`; os bancos preexistentes não foram alterados. `.runtime` e `.env` são ignorados pelo Git.

O uv apresentou falha ao persistir temporários entre discos C e D. Cache e TMP/TEMP foram definidos para `.uv-cache` no mesmo disco do projeto somente nos comandos de instalação. Não foram alteradas variáveis globais do Windows.

A Oracle foi acessada por SSH com a chave existente indicada pelo usuário. Foram inspecionados arquitetura, RAM, disco e containers. O Docker da VPS funciona e é administrado via sudo; a chave privada não foi exibida nem copiada para arquivos do projeto.
