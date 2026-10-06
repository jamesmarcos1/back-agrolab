# Publicação Oracle e Coolify

Estado inicial: backend preparado; infraestrutura produtiva ainda não publicada.

## Topologia e recursos

Criar projeto AgroLab no Coolify existente. Usar aplicações, banco e credenciais próprias. A inspeção mostrou VPS ARM/aarch64 com aproximadamente 12 GB RAM, cerca de 4 GB disponíveis e outros projetos ativos. Medir novamente antes de provisionar.

- PostgreSQL 18 persistente em rede privada, sem porta pública. Não reutilizar bancos do Zelo ou Coolify.
- API baseada no Dockerfile, porta interna 8000.
- Domínios previstos: api-agrolab.jamesmarcos.com e api-agrolab-dev.jamesmarcos.com.
- Dev e produção com dados, chaves, remetentes e issuer/audience separados.
- Job de limpeza com a mesma imagem e configuração, comando `python -m app.jobs.cleanup --loop`; intervalo de uma hora. O lock no banco evita dois jobs simultâneos.

Desabilitar o healthcheck HTTP herdado da imagem no worker de limpeza: ele não abre uma porta HTTP. No Compose isso já está configurado. Monitorar o processo e eventos de conclusão/falha do job no ambiente hospedado.

## Variáveis de produção

| Variável | Configuração |
| --- | --- |
| ENVIRONMENT | production |
| DATABASE_URL | postgresql+psycopg com host privado do banco |
| JWT_SECRET / OTP_SECRET | Dois segredos aleatórios independentes de pelo menos 64 caracteres |
| JWT_ISSUER | agrolab-production |
| JWT_AUDIENCE | agrolab-ios-production |
| BCRYPT_COST | 12 inicialmente, medir latência; mínimo 10 |
| SMTP_HOST / SMTP_PORT | Endpoint do provedor de e-mail |
| SMTP_SECURITY | starttls ou ssl |
| SMTP_USERNAME / SMTP_PASSWORD | Credenciais do remetente autorizado |
| MAIL_FROM | Remetente verificado do domínio |
| PRIVACY_POLICY_VERSION | Versão efetivamente apresentada no app |
| DB_POOL_SIZE | 5 por processo inicialmente |

Segredos ficam no painel do Coolify ou mecanismo de segredos escolhido, sem entrar no Git ou nas descrições de execução. A produção rejeita configuração de SMTP sem TLS, segredos de teste e audiência de desenvolvimento.

## Proxy e HTTPS

Configurar DNS no provedor autoritativo atual, sem substituir os registros dos outros projetos. No Coolify, adicionar o domínio HTTPS e verificar certificado e renovação. Firewall OCI/host deve permitir somente as portas necessárias, sem abrir PostgreSQL.

Uvicorn deve confiar em cabeçalhos encaminhados apenas do proxy Traefik. Configurar `FORWARDED_ALLOW_IPS` com o IP ou faixa da rede Docker privada efetivamente usada pelo proxy e restringir o acesso direto ao container. Não usar `*` com porta acessível por clientes externos. O código usa request.client para os limites; não interpreta diretamente X-Forwarded-For informado pelo cliente.

A API recusa HTTP em produção, exceto health checks internos. Se o proxy não for reconhecido, HTTPS externo pode ser visto como HTTP: corrigir a lista de proxies confiáveis, sem desativar a verificação.

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

Backup diário fora da VPS, criptografado, com retenção máxima de 14 dias. Testar restauração em banco descartável e registrar resultado. Volume persistente evita perder dados em redeploy, mas não substitui backup.

O job remove dados ativos de contas encerradas. Cópias antigas expiram pela retenção. Caso haja restauração de backup antigo, reaplicar solicitações de exclusão ocorridas após o backup antes de liberar o sistema; o procedimento precisa de um registro operacional seguro desses pedidos, separado do backup restaurado. Essa dependência operacional ainda deve ser definida antes de usar dados reais.

## Operação e rollback

Monitorar disponibilidade, falhas SMTP, espaço de disco, readiness e execução de limpeza. Logs registram tipo de falha e request ID sem credenciais. Conferir cobertura mensal de 99% com monitoramento externo; validar 500 usuários com cenário de carga definido.

Para falha de aplicação, retornar à imagem anterior e repetir o smoke test. Não executar downgrade destrutivo como rollback automático. Migrações futuras precisam ser retrocompatíveis; recuperação de dados depende de backup verificado.

## Pendências externas

DNS/subdomínio, recurso AgroLab no Coolify, remetente SMTP real, política e destino de backups, atualização dos DOCX e teste em Swift. A chave SSH indicada pelo usuário permitiu inspeção da VPS; nenhum conteúdo privado da chave foi mostrado no chat ou colocado no repositório.
