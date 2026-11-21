# Como verificar cadastros e acompanhar o AgroLab

Atualizado em 07/10/2026. Este guia serve ao responsavel pelo backend. O pacote Swift continua sendo suficiente para os colegas que desenvolvem o aplicativo; eles nao precisam de acesso ao banco ou aos paineis administrativos.

## 1. Ver o banco pelo Coolify

1. Acesse https://coolify.jamesmarcos.com e abra o projeto **AgroLab**, ambiente de producao e servico **agrolab-auth-production**.
2. Abra **Terminal** e selecione o container do banco, identificado pelo componente `db`. O nome publicado nesta entrega e `db-r13cwfklsavepdjyxl5j5rqs`.
3. No terminal do container, execute:

```sh
psql -U agrolab -d agrolab -v ON_ERROR_STOP=1 -P pager=off
```

Se o terminal aberto for o do servidor, em vez do container, use:

```sh
sudo docker exec -it db-r13cwfklsavepdjyxl5j5rqs psql -U agrolab -d agrolab -v ON_ERROR_STOP=1 -P pager=off
```

O nome do container deve ser confirmado no recurso se a stack for recriada. O Coolify disponibiliza terminal e logs de containers; consulte a [documentacao do terminal](https://coolify.io/docs/core/infrastructure/servers/web-terminal).

4. Dentro do `psql`, cole as consultas de `docs/database-checks.sql`. Elas comecam uma transacao `READ ONLY`, definem horario de Sao Paulo e limite de dez segundos por comando, e terminam com `ROLLBACK`. Nao alteram registros. [Transacoes somente leitura no PostgreSQL](https://www.postgresql.org/docs/18/sql-set-transaction.html).
5. Use `\q` para sair. Se uma consulta falhar enquanto a transacao estiver aberta, execute `ROLLBACK;` antes de repetir o bloco.

Os valores de configuracao sao os da entrega atual. O usuario do banco ainda tem privilegios administrativos: `READ ONLY` protege as consultas deste roteiro contra escrita acidental, mas nao substitui a criacao futura de um usuario com permissoes restritas. O acesso permanece pela VPS/Coolify; nao e preciso publicar a porta do PostgreSQL na internet.

## 2. O que cada registro significa

| Tabela/resultado | Como interpretar |
| --- | --- |
| `pending_registrations` | Solicitacoes de cadastro temporarias; ainda nao sao usuarios ativos |
| `users` com `status = 'active'` | Conta criada depois de confirmar email/codigo e senha |
| `email_verified_at` | Momento em que a confirmacao foi concluida |
| `sessions` | Sessoes emitidas; contar apenas as nao revogadas/nem expiradas e de contas ativas |
| `auth_events` | Eventos de cadastro, confirmacao, login, refresh, recuperacao e exclusao |
| `deletion_requests` | Fila de exclusao; o acesso ja e bloqueado quando a solicitacao e aceita |

A tabela de pendentes conserva registros consumidos ate a limpeza. Por isso, nao comparar o total bruto dessa tabela com o numero de contas: as consultas diferenciam confirmados e nao confirmados, e descartam desafios inertes da contagem de pendentes utilizaveis. A validade do cadastro temporario nao estende os 60 segundos do codigo de confirmacao.

Eventos uteis:

| Evento | Significado |
| --- | --- |
| `registration_requested` | Solicitacao aceita; nao comprova envio/entrega do email |
| `registration_verified` | Confirmacao concluida |
| `login_succeeded` / `login_denied` | Login aceito / recusado |
| `session_refreshed` / `session_revoked` | Sessao renovada / encerrada |
| `refresh_replayed` | Refresh antigo reutilizado, com revogacao da sessao |
| `email_delivery_failed` | A tentativa SMTP falhou; investigar API e Resend |
| `password_reset_completed` | Senha redefinida |
| `deletion_requested` | Exclusao solicitada |

Esses eventos nao sao um registro de todas as chamadas HTTP: falhas de validacao, por exemplo, podem ocorrer antes do servico de autenticacao. A limpeza remove eventos com mais de 14 dias e eventos associados ao email de uma conta eliminada. Portanto, esses totais nao sao estatisticas historicas permanentes.

## 3. Teste pratico com uma conta controlada por voce

1. Cadastre pelo app ou pela API usando sua propria caixa de email. HTTP 202 significa cadastro pendente: ainda nao deve existir a nova conta ativa em `users`.
2. Confirme o codigo dentro de 60 segundos. Depois de HTTP 201, a conta deve aparecer em `users`, com `status = 'active'` e `email_verified_at` preenchido.
3. Faca login. Espere HTTP 200, o evento `login_succeeded` e uma sessao utilizavel. Confira `GET /api/v1/users/me`: o perfil deve ser o da conta usada.
4. Faca logout. Espere HTTP 204 e confirme que o access token da sessao encerrada recebe 401 em `/users/me`. Outras sessoes da conta podem continuar ativas.
5. Para conferir o titular exato, no seu terminal privado consulte apenas os campos abaixo, substituindo o exemplo pelo email de teste normalizado. Evite copiar dados pessoais para grupos:

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10s';
SET LOCAL TIME ZONE 'America/Sao_Paulo';
SELECT id, email, status, created_at, email_verified_at
FROM users
WHERE email = 'seu-email-de-teste@example.com';
ROLLBACK;
```

Depois de cada etapa, repita as consultas em uma nova transacao. A chegada de um cadastro ao banco nao garante que o email chegou na caixa da pessoa, nem que a UI Swift instalou corretamente a sessao.

## 4. Acompanhamento rotineiro

- **Banco:** consulte contas recentes, eventos, sessoes validas e fila de exclusao com o arquivo SQL. Ele seleciona campos especificos, sem hashes de senha, OTPs ou tokens.
- **API:** no Coolify, abra os logs do componente `api`. Correlacione o `request_id` do erro no aplicativo com o evento/log do servidor. Nao sao gravados corpos de requisicao ou credenciais.
- **Email:** no painel do Resend, confira entrega, rejeicoes e consumo. Uma aceitaçao SMTP nao comprova chegada na caixa pessoal.
- **Infraestrutura:** confira containers, ultimas execucoes de backup e `GET https://api-agrolab.jamesmarcos.com/health/ready`, que deve responder HTTP 200 com `{"status":"ready"}`. Health check verifica API/banco, nao o Swift, email ou recuperabilidade do backup.

Este roteiro e manual. Alertas externos de indisponibilidade, falha SMTP, consumo, backup e limpeza ainda precisam ser configurados. Logs gravados e health checks internos nao constituem acompanhamento automatico com notificacoes.

## 5. Verificacao executada em 07/10/2026

As sete consultas de `docs/database-checks.sql` foram executadas no banco publicado por SSH, em transacao `READ ONLY`, encerrada por `ROLLBACK`. Todas terminaram sem erro. A API respondeu HTTP 200 com `{"status":"ready"}`, com validacao do certificado TLS.

No momento da consulta, nao havia contas em `users`, cadastros pendentes, sessoes utilizaveis ou pedidos de exclusao na fila. Permaneciam eventos compativeis com as validacoes anteriores, incluindo recusas de acesso e a reutilizacao intencional do refresh descrita no relatorio de 06/10. Esse e um retrato do momento; repetir depois do cadastro de uma conta de teste para acompanhar novos registros.

A consulta confirmou a disponibilidade do banco e o funcionamento do roteiro. Nao foi criado outro cadastro nem reenviado email nesta verificacao; o fluxo funcional completo continua documentado no relatorio de 06/10/2026.

Para inspecao visual com um cliente como DBeaver ou pgAdmin, a proxima configuracao seria um tunel SSH e uma conta de leitura restrita. Esse acesso ainda nao foi preparado nesta entrega. O terminal do Coolify permite conferir o banco agora sem abrir acesso publico.
