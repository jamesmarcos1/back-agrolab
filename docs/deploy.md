# Publicação Oracle e Coolify

Publicado em 06/10/2026: https://api-agrolab.jamesmarcos.com. `/health/ready` respondeu 200 com certificado validado; o fluxo de autenticação pela internet passou. Swagger está desabilitado em produção; o contrato está em `docs/openapi.json`.

## Topologia e recursos

Projeto **AgroLab**, ambiente **production**, serviço **agrolab-auth-production** no Coolify existente. A inspeção mostrou VPS ARM/aarch64 com aproximadamente 12 GB RAM, cerca de 4 GB disponíveis e outros projetos ativos. Não foram reutilizados bancos ou credenciais desses projetos.

Foi usado Docker Compose Empty com `compose.production.yaml`: banco, migração, API e limpeza em uma rede do próprio recurso. Isso permite versionar a topologia e coordenar a migração sem depender de um repositório remoto ainda inexistente. A imagem ARM `agrolab-api:20261006` já está na VPS; `pull_policy: never` exige construir cada nova tag antes de alterar o Compose no painel. Não há implantação automática ao editar arquivos locais.

- PostgreSQL 18 persistente em rede privada, sem porta pública. Não reutilizar bancos do Zelo ou Coolify.
- API baseada no Dockerfile, porta interna 8000.
- Produção: api-agrolab.jamesmarcos.com. Desenvolvimento local com Docker/Mailpit. Homologação pública api-agrolab-dev.jamesmarcos.com ainda não foi criada.
- Desenvolvimento e produção usam dados, chaves, remetentes e issuer/audience separados.
- Job de limpeza com a mesma imagem e configuração, comando `python -m app.jobs.cleanup --loop`; intervalo de uma hora. O lock no banco evita dois jobs simultâneos.

Desabilitar o healthcheck HTTP herdado da imagem no worker de limpeza: ele não abre uma porta HTTP. No Compose isso já está configurado. Monitorar o processo e eventos de conclusão/falha do job no ambiente hospedado.

Na publicação, API e PostgreSQL estavam healthy, migração terminou com código 0 e limpeza estava em execução. O Coolify excluiu a migração do status do serviço. O worker sem healthcheck pode deixar o status agregado como `Running (unknown)`; isso não substitui a verificação HTTP da API nem a inspeção do processo de limpeza.

Volume persistente observado: `r13cwfklsavepdjyxl5j5rqs_agrolab-postgres-data`, montado em `/var/lib/postgresql`, conforme PostgreSQL 18. Banco e API não possuem publicação direta de portas no host; acesso público somente pelo proxy. RAM observada após publicação: API ~70 MiB, banco ~34 MiB, limpeza ~56 MiB. Esses valores são ociosos, não uma medição de capacidade.

## Variáveis de produção

| Variável | Configuração |
| --- | --- |
| ENVIRONMENT | production |
| DATABASE_URL | postgresql+psycopg com host privado do banco |
| JWT_SECRET / OTP_SECRET | Dois segredos aleatórios independentes de pelo menos 64 caracteres |
| JWT_ISSUER | agrolab-production |
| JWT_AUDIENCE | agrolab-ios-production |
| BCRYPT_COST | 12 inicialmente, medir latência; mínimo 10 |
| SMTP_HOST / SMTP_PORT | smtp.resend.com / 465 |
| SMTP_SECURITY | ssl |
| SMTP_USERNAME / SMTP_PASSWORD | resend / chave Resend exclusiva com Sending access limitada ao domínio |
| MAIL_FROM | AgroLab <agrolab@jamesmarcos.com> |
| PRIVACY_POLICY_VERSION | Versão efetivamente apresentada no app |
| DB_POOL_SIZE | 5 por processo inicialmente |

Segredos ficam no painel do Coolify ou mecanismo de segredos escolhido, sem entrar no Git ou nas descrições de execução. A produção rejeita configuração de SMTP sem TLS, segredos de teste e audiência de desenvolvimento.

## Proxy e HTTPS

Configurar DNS no provedor autoritativo atual, sem substituir os registros dos outros projetos. No Coolify, adicionar o domínio HTTPS e verificar certificado e renovação. Firewall OCI/host deve permitir somente as portas necessárias, sem abrir PostgreSQL.

Uvicorn deve confiar em cabeçalhos encaminhados apenas do proxy Traefik. Configurar `FORWARDED_ALLOW_IPS` com o IP ou faixa da rede Docker privada efetivamente usada pelo proxy e restringir o acesso direto ao container. Não usar `*` com porta acessível por clientes externos. O código usa request.client para os limites; não interpreta diretamente X-Forwarded-For informado pelo cliente.

Na rede `r13cwfklsavepdjyxl5j5rqs`, o proxy foi observado em `10.0.7.5`; esse valor foi configurado em `TRUSTED_PROXY_IPS`, referenciado pelo Compose. Após recriar proxy ou rede, confirmar seu endereço com `docker inspect coolify-proxy` e atualizar a variável no Coolify se necessário. Reiniciar o recurso aplica novas variáveis; apenas salvar não altera containers em execução.

O campo Domains da API no Coolify é `https://api-agrolab.jamesmarcos.com:8000`. O sufixo indica a porta interna do container; o iPhone utiliza HTTPS normal na porta 443. Essa distinção segue a [documentação do Compose no Coolify](https://coolify.io/docs/applications/builds/docker-compose).

A API recusa HTTP em produção, exceto health checks internos. Se o proxy não for reconhecido, HTTPS externo pode ser visto como HTTP: corrigir a lista de proxies confiáveis, sem desativar a verificação. Um health check pode continuar passando nessa situação; conferir também uma rota como `/api/v1/users/me`, que deve retornar 401 sem autenticação, e não HTTPS_REQUIRED.

## DNS e remetente

DNS autoritativo na Cloudflare, apesar de o domínio ser administrado na Hostinger. Registros novos, preservando os anteriores:

| Tipo | Nome | Conteúdo | Proxy |
| --- | --- | --- | --- |
| A | api-agrolab | 163.176.206.209 | DNS only |
| TXT | resend._domainkey | Chave DKIM pública gerada pelo Resend; consultar painel | Não se aplica |
| CNAME | rsend | rsend-sae1.forge.rmta.net | DNS only |
| CNAME | send | send.forge.rmta.net | DNS only |
| TXT | _dmarc | v=DMARC1; p=none; | Não se aplica |

Resend verificou o domínio jamesmarcos.com na região São Paulo. Não foi configurado recebimento nem contratado e-mail na Hostinger. O endereço de remetente não representa uma caixa postal. SMTP usa TLS com a chave dedicada, conforme a [documentação Resend](https://resend.com/docs/send-with-smtp); acompanhar consumo e limites no [plano gratuito](https://resend.com/pricing).

## Sequência de rollout

1. CI passa: lint, testes, cobertura >=70%, migração e build.
2. Construir imagem ARM compatível, preferencialmente fora da VPS se houver pressão de memória.
3. Criar PostgreSQL e confirmar armazenamento persistente em volume OCI com AES-256.
4. Fazer backup antes de alterações posteriores de schema.
5. Executar `alembic upgrade head` uma vez como etapa de release, antes de trocar containers. Não executar migrações em cada worker simultaneamente.
6. Iniciar API e limpeza, verificar `/health/ready`.
7. Habilitar domínio/HTTPS e testar externamente.
8. Confirmar remetente e SPF/DKIM/DMARC; medir recebimento dentro dos 60 segundos do OTP.
9. Executar fluxo real de cadastro, verificação, login, perfil, refresh e logout.

Não adicionar usuários manualmente com senha em texto para demonstração; usar o fluxo de cadastro.

## Backups e exclusão

Agendamento diário **na VPS** já criado no Coolify: `0 3 * * *`, timezone UTC (00:00 em São Paulo nesta data), apenas banco `agrolab`, timeout 300 s. Retenção limitada a 14 cópias, 14 dias e 1 GB; o primeiro limite atingido aplica a retenção. A execução inicial mostrou Success em 1 s, tamanho 21,84 KB. Seguir as [instruções de backup do Coolify](https://coolify.io/docs/databases/backups) para ver execuções e configurar um armazenamento externo validado.

O volume do Docker fica no armazenamento da instância Oracle. A OCI documenta AES-256 em repouso para boot/block volumes e seus backups; a configuração de chave e política específica no console OCI ainda não foi inspecionada. Dumps fora desse armazenamento precisam de proteção própria. Referência: [criptografia OCI](https://docs.oracle.com/en-us/iaas/Content/Security/Reference/blockstorage_security.htm).

Foi criada também uma cópia criptografada **fora da VPS**, neste computador, com `scripts/backup_database.ps1`. O script lê pg_dump custom por SSH, criptografa em memória com AES-256-GCM e grava `.agbackup` em `.runtime/backups`. Não grava dump legível. `key.dpapi` protege a chave aleatória de 32 bytes com DPAPI CurrentUser; exige o mesmo Windows/usuário. Essa vinculação precisa ser resolvida com custódia recuperável da chave antes de depender da cópia para desastre do computador.

`scripts/verify_backup.ps1` confirmou descriptografia, rejeição de adulteração e restauração em um banco novo `_test` no PostgreSQL 18 descartável: recuperou um usuário de teste e versão Alembic `1d36578fa9a0`. Nenhuma restauração foi feita no banco de produção.

Para repetir a validação, criar um container descartável na VPS (por exemplo, `agrolab-restore-check`), isolado com `--network none`, usando PostgreSQL18, POSTGRES_USER=agrolab e autenticação temporária interna. Aguardar pg_isready; executar localmente:

```powershell
.\scripts\verify_backup.ps1 -BackupFile 'CAMINHO_ABSOLUTO_DO_BACKUP.agbackup' -SshKeyPath 'CAMINHO_ABSOLUTO_DA_CHAVE_SSH' -RestoreContainer agrolab-restore-check
```

O script cria um banco novo com nome datado terminado em `_test`, recusa o nome do container produtivo e remove apenas seu banco ao terminar ou falhar. `-KeepRestoreDatabase` permite preservar explicitamente a cópia para inspeção; nesse caso ela contém os dados do backup e precisa ser eliminada após o uso. Remover somente o container descartável criado para essa validação depois de conferir o resultado. Não importar um backup antigo diretamente em produção para testar recuperação.

**Pendente:** destino externo automático (nenhum S3 validado no Coolify), custódia da chave, retenção/alertas externos. A cópia manual não constitui backup diário externo automático. Volume persistente evita perda em redeploy, mas não substitui recuperação fora da VPS.

O job remove dados ativos de contas encerradas. Cópias antigas expiram pela retenção. Caso haja restauração de backup antigo, reaplicar solicitações de exclusão ocorridas após o backup antes de liberar o sistema; o procedimento precisa de um registro operacional seguro desses pedidos, separado do backup restaurado. Essa dependência operacional ainda deve ser definida antes de usar dados reais.

## Operação e rollback

Monitorar disponibilidade, falhas SMTP, espaço de disco, readiness e execução de limpeza. Logs registram tipo de falha e request ID sem credenciais. Conferir cobertura mensal de 99% com monitoramento externo; validar 500 usuários com cenário de carga definido.

Para falha de aplicação, retornar à imagem anterior e repetir o smoke test. Não executar downgrade destrutivo como rollback automático. Migrações futuras precisam ser retrocompatíveis; recuperação de dados depende de backup verificado.

## Pendências externas

Destino externo automático/custódia de backup, alertas, monitoramento, teste de carga, atualização posterior dos DOCX e teste no Swift. Nenhum repositório remoto foi criado; CI do GitHub está preparada, mas ainda não executou como pipeline remota. Não foi validado rollback entre versões distintas porque esta é a primeira imagem produtiva. A chave SSH indicada pelo usuário não foi mostrada no chat nem colocada no repositório.
