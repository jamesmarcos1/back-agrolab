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
- Tarefa 6: CI e Dockerfile preparados; imagem ARM construída e publicada na Oracle/Coolify; 48 testes passaram no PostgreSQL18/Linux ARM, cobertura 92,46%. Migração e alembic check verificados. DNS/HTTPS/Resend publicados; fluxo externo completo passou. Backup diário local configurado; cópia externa criptografada restaurada. Automação externa depende do destino de armazenamento.

## Evidência e decisões de revisão

- Primeira suíte: 36 testes passando no PostgreSQL17.4 isolado; cobertura 89,60%.
- Revisão independente: sem achados críticos; confirmou disputa de locks register/resend, distinção de contas em falha SMTP e corrida com limpeza. Seis falhas foram reproduzidas; oito testes de regressão passaram após os ajustes.
- Ruling: cadastro/reenvio retornam 202 mesmo na falha de entrega SMTP, preservando indistinguibilidade de contas. 202 significa solicitação aceita; falhas são registradas internamente, não ativam usuário e permitem reenvio posterior. Custo: cliente não sabe imediatamente que SMTP falhou; depende de monitoramento e opção de reenvio.
- Rechecagem identificou disputa na limpeza de contador ao virar a janela. Teste com contador já persistido reproduziu a falha. Limpeza passou a usar transações separadas por entidade e retenção isolada, mantendo apenas o gate global em conexão própria. Custo: mais transações e duas conexões durante o job.
- Ruling: ordem de locks de e-mail/usuário precede contadores compartilhados de envio. Tokens são relidos após locks, e registros ausentes retornam erros esperados.
- Healthcheck HTTP desabilitado no worker, que não possui servidor HTTP.
- Suíte após ajustes: 47 testes no PostgreSQL17.4. Adicionado teste de esquema Bearer no OpenAPI; suíte final: 48 testes passando no PostgreSQL18, cobertura 92,46%.

## Ambiente e infraestrutura

- Oracle acessível com a chave existente da pasta indicada: ARM, ~12GB RAM, ~4GB disponíveis durante a inspeção, Docker29.5.2 e Coolify4.1.2. Inspeção de outros containers foi somente leitura.
- Banco PostgreSQL18 de validação temporário criado sem volume, somente loopback. A suíte final foi executada diretamente em container ARM; testes não usaram o banco produtivo.
- Ubuntu-AgroLab instalado separado no disco D e iniciado; cadastro antigo preservado. Renomeação Windows dos sockets falhou; preservação dos dois diretórios pelo novo WSL permitiu iniciar o Docker Engine 29.4.2. Sem reset/prune/remoção de volumes.
- Usuário escolheu Resend gratuito. Remetente `agrolab@jamesmarcos.com`, domínio verificado, chave exclusiva com Sending access limitada a jamesmarcos.com. Não foi contratada caixa postal na Hostinger.
- Cloudflare: A api-agrolab apontando para a Oracle, DNS only; TXT resend._domainkey, CNAME rsend e send em DNS only, TXT _dmarc. Registros anteriores preservados; recebimento de e-mail não habilitado.
- Coolify: projeto AgroLab / production / agrolab-auth-production. Compose com banco persistente privado, migração única, API e limpeza horária. Imagem local agrolab-api:20261006, construída na VPS. Segredos próprios; proxy confiável observado em 10.0.7.5.
- HTTPS público: health/ready=200; fluxo register/resend/verify/login/me/refresh/logout/delete passou. Logout e exclusão bloquearam JWT imediatamente. O código foi lido apenas do e-mail de teste do provedor, nunca retornado pela API. Exclusão da conta temporária ficou para o job horário.
- Backup Coolify: 03:00 UTC diariamente, retenção 14 dias/14 cópias/1 GB; primeira execução Success, banco agrolab, 21,84 KB. Cópia externa AES-256-GCM no computador, chave protegida por DPAPI. Restauração no PostgreSQL18 descartável recuperou usuário e schema 1d36578fa9a0; adulteração rejeitada.
- Revisão das rotinas de backup: disputa de criação da chave reproduzida, corrigida com publicação atômica sem sobrescrita e verificada com oito inicializações concorrentes. Banco de restauração agora é removido no finally somente quando criado pela execução; preservação requer flag explícita. Revisão limitada aprovou as correções.
- Verificado também erro real de pg_restore: um dump inválido foi rejeitado e o banco recém-criado foi removido pelo finally. Container PostgreSQL18 de validação descartável e sua rede foram encerrados/removidos após as verificações, sem alterar recursos produtivos. Cluster nativo local provisório foi encerrado para liberar a porta do Compose; arquivos preservados.
- Cópias temporárias em texto de segredos produtivos foram removidas; configuração local de implantação protegida por DPAPI em `.runtime/production.env.dpapi`, ignorada pelo Git. Segredos permanecem configurados no Coolify.
- Docker local: hello-world passou; Compose x64 construído e iniciado, API/PostgreSQL18.6/Mailpit saudáveis, migração com código 0. Health/Swagger/Mailpit responderam 200 e schema 1d36578fa9a0 foi confirmado. Ubuntu-AgroLab definido como distribuição WSL padrão; o cadastro Ubuntu antigo continua preservado.
- Revisão automática bloqueou execução manual de limpeza produtiva por alcance de exclusão. Não foi executada nem contornada; a solicitação da conta de teste permanece no processamento horário configurado.

## Pendências da operação

Definir bucket externo e custódia recuperável da chave, alertas/monitoramento, registro operacional de exclusões para recuperação e testes de carga. Projeto Swift e atualização posterior dos DOCX não estão nesta entrega. A branch local não foi enviada; CI do GitHub está preparada, mas a publicação inicial usou validações manuais, sem alegar execução remota do workflow.
