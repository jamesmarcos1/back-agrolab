# Execução do plano de login AgroLab

Plano: superpowers/plans/2026-10-06-login-agrolab.md. Início: 06/10/2026.

- Usuário autorizou implementação e acesso à infraestrutura; pediu README explicando tudo que foi feito e por quê.
- Domínio: jamesmarcos.com. Coolify: https://coolify.jamesmarcos.com. VPS acessada pelo Ubuntu/WSL.
- Ruling: pasta nova sem Git; criado repositório local na branch feat/login. Não há branch compartilhada a isolar.
- Ruling: DER antigo contém nome, email, senha_hash, telefone, dois_fatores_ativo e timestamps. Nome/email/senha são obrigatórios no UC01; telefone não será coletado. email_verified_at representa confirmação inicial; MFA permanente fica separado.
- Ruling: sem projeto Swift presente, entregar contrato e guia de consumo; validação em iPhone depende do responsável pelo app.
- Ruling: uv apresentou erro 17 entre discos C/D; cache e temporários ajustados para o disco D no workspace.
- Pré-verificação: cadastro produz usuário/sessão consumidos por autorização; toda mutação usa transação PostgreSQL. Relógio e Mailer substituíveis nos testes.

## Estado

- Tarefa 1: base e migração inicial implementadas; health, configuração e alembic check verificados.
- Tarefa 2: cadastro pendente, confirmação, reenvio, SMTP e limites implementados e testados.
- Tarefa 3: login, perfil, JWT, refresh, replay e logout implementados e testados.
- Tarefa 4: recuperação, exclusão, limpeza e proteções implementadas e testadas.
- Tarefa 5: README, guia Swift e OpenAPI entregues. Integração real com o projeto iOS permanece pendente, pois não está no workspace.
- Tarefa 6: CI e Dockerfile preparados; imagem ARM final construída na Oracle; 48 testes passando com PostgreSQL18/Linux ARM, cobertura 92,46%. Migração inicial e alembic check verificados no PostgreSQL18. DNS, projeto produtivo no Coolify, SMTP real e backups ainda em configuração.

## Evidência e decisões de revisão

- Primeira suíte: 36 testes passando no PostgreSQL17.4 isolado; cobertura 89,60%.
- Revisão independente: sem achados críticos; confirmou disputa de locks register/resend, distinção de contas em falha SMTP e corrida com limpeza. Seis falhas foram reproduzidas; oito testes de regressão passaram após os ajustes.
- Ruling: cadastro/reenvio retornam 202 mesmo na falha de entrega SMTP, preservando indistinguibilidade de contas. 202 significa solicitação aceita; falhas são registradas internamente, não ativam usuário e permitem reenvio posterior. Custo: cliente não sabe imediatamente que SMTP falhou; depende de monitoramento e opção de reenvio.
- Rechecagem identificou disputa na limpeza de contador ao virar a janela. Teste com contador já persistido reproduziu a falha. Limpeza passou a usar transações separadas por entidade e retenção isolada, mantendo apenas o gate global em conexão própria. Custo: mais transações e duas conexões durante o job.
- Ruling: ordem de locks de e-mail/usuário precede contadores compartilhados de envio. Tokens são relidos após locks, e registros ausentes retornam erros esperados.
- Healthcheck HTTP desabilitado no worker, que não possui servidor HTTP.
- Suíte após ajustes: 47 testes, cobertura 92,46%, no PostgreSQL17.4. Adicionado também teste de esquema Bearer no OpenAPI; nova verificação final em andamento.

## Ambiente e infraestrutura

- Oracle acessível com a chave existente da pasta indicada: ARM, ~12GB RAM, ~4GB disponíveis durante a inspeção, Docker29.5.2 e Coolify4.1.2. Inspeção de outros containers foi somente leitura.
- Banco PostgreSQL18 de validação temporário criado sem volume, com porta apenas loopback e túnel SSH. Imagem ARM de validação construída; não é publicação produtiva.
- Ubuntu-AgroLab instalado separado no disco D e iniciado com sucesso; cadastro antigo preservado. Docker Desktop ainda bloqueado por socket Windows inacessível, inclusive após tentativa administrativa. Sem reset/prune/remoção de volumes.
- Usuário informou que ainda precisa criar a caixa de e-mail do domínio; definição do provedor/remetente continua pendente.
- Hostinger autenticada: painel mostrou somente contratação de plano de e-mail. Resend SMTP gratuito proposto como alternativa para o MVP; escolha pendente.
- DNS autoritativo confirmado na Cloudflare, não no hPanel. Subdomínio da API e registros do remetente precisam ser configurados lá.
- Coolify autenticado no navegador disponibilizado pelo usuário; configuração de recursos ainda em preparação.
