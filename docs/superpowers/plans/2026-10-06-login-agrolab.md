# Plano de implementação do login AgroLab

Data: 06/10/2026. Estado: proposta pronta para revisão; nenhum backend implementado ou publicado.

**Objetivo:** entregar o UC01 com cadastro, confirmação de e-mail, login e gestão de sessão, acessível por HTTPS ao aplicativo Swift.
**Arquitetura:** monólito modular FastAPI, PostgreSQL privado e envio de e-mail transacional. Containers na VPS Oracle administrados pelo Coolify.
**Stack proposta:** Python 3.13, FastAPI, Pydantic, SQLAlchemy 2, psycopg, Alembic, bcrypt, PyJWT, pytest, HTTPX e Docker.
**Execução futura:** implementar sequencialmente, verificando cada etapa. Este arquivo é a proposta de arquitetura e seu plano de execução; não autoriza provisionamentos nesta etapa.

## 1. Evidências e decisões

Foram consultados os textos dos três DOCX da pasta Trabalho-Agrolab:
- Documento_de_Arquitetura_-_AgroLab_com_MVP.docx: seções 3, 7 e 10; tabela de controles OWASP.
- DRS_-_AgroLab_com_MVP.docx: UC01, fluxo principal, FA01, FA02, FE01, FE02, RN01 e RN02; recorte do MVP.
- Documento_de_visao_-_com_MVP.docx: requisitos não funcionais e escopo do MVP.

A pasta back-agrolab estava vazia. Nenhum código Swift ou configuração de VPS foi inspecionado. Não foram encontradas instruções AGENTS.md dentro da pasta do projeto. Diagramas embutidos nos DOCX não foram validados visualmente; a modelagem abaixo é proposta e deverá ser reconciliada com o DER antes da primeira migração.

Confirmado nos documentos:
- App nativo Swift/SwiftUI, iOS 17+, MVVM e Keychain para credenciais.
- Backend Python/FastAPI e banco PostgreSQL 18.
- Cadastro solicita nome, e-mail e senha; conta é criada após validação do código.
- Código aleatório de seis dígitos por e-mail, duração de exatamente 60 segundos, uso único.
- Reenvio liberado após 60 segundos, inclusive no servidor; novo código invalida o anterior.
- Login posterior por e-mail e senha.
- bcrypt com custo mínimo 10; HTTPS TLS 1.2+; dados pessoais criptografados em repouso com AES-256.
- JWT com refresh token, limites de tentativa e logs de acesso não autorizado.
- Ambientes dev e produção separados; CI/CD e segredos fora do Git.
- Cobertura mínima de 70%, disponibilidade mensal de 99%, meta de 500 usuários simultâneos e exclusão de dados em até 30 dias.

**Decisão confirmada pelo usuário:** é permitido atualizar os documentos para Oracle + Coolify. A arquitetura ainda escreve AWS e alguns trechos escrevem Supabase/AWS; esses textos precisam ser harmonizados posteriormente.

O documento cita patches específicos de Python/FastAPI. Não foram validados como versões disponíveis e adequadas. Na implementação, conferir disponibilidade, suporte e vulnerabilidades; fixar versões compatíveis em lockfile e respeitar a regra documental de bibliotecas estáveis publicadas há pelo menos 30 dias, tratando correções urgentes de segurança conforme o documento.

## 2. Abordagens comparadas

| Abordagem | Vantagem | Custo ou limitação | Decisão |
| --- | --- | --- | --- |
| FastAPI + PostgreSQL na Oracle, Coolify | Aproveita infraestrutura conhecida e permite cumprir o UC01 com precisão | Equipe mantém autenticação, servidor, e-mail e backups | Recomendada |
| FastAPI + Firebase Authentication | Autenticação gerenciada e SDK Apple | Exige redesenhar requisitos de senha, confirmação e sessão; fluxo padrão não equivale automaticamente ao código de 60 segundos do DRS | Fora desta entrega |
| FastAPI + PostgreSQL na AWS | Alinha-se ao texto original | Introduz outra infraestrutura a configurar e operar | Alternativa se AWS voltar a ser obrigatória |

Firebase pode autenticar usuários de um app Swift e fornecer tokens verificáveis por um backend. Portanto, é uma alternativa técnica real, mas não traz aderência automática ao UC01. Não manter dois sistemas de senha ou duas autoridades de sessão.

O domínio pode continuar no provedor atual. Apenas o DNS do subdomínio da API apontará para a Oracle. A hospedagem de sites do provedor não precisa executar Python.

## 3. Topologia proposta

iPhone (Swift/URLSession + Keychain)
→ HTTPS api-agrolab.DOMINIO-DO-USUARIO
→ proxy do Coolify na Oracle
→ container FastAPI
→ PostgreSQL em rede privada

FastAPI → provedor de e-mail transacional por SMTP autenticado com TLS.

- Subdomínio de desenvolvimento separado: api-agrolab-dev.DOMINIO-DO-USUARIO.
- Containers, credenciais, chaves, banco e volumes separados entre dev e produção.
- Sem publicação da porta 5432 do banco na internet.
- Dockerfile para a API; PostgreSQL como recurso persistente do Coolify.
- Docker Compose para desenvolvimento local, com PostgreSQL e caixa de e-mail de teste.
- Sem Kubernetes, microsserviços, Redis ou fila distribuída nesta etapa. Limites de tentativa e estado de sessões persistidos no PostgreSQL, para funcionarem com múltiplos processos.
- Dimensionamento depende de CPU, RAM, arquitetura ARM/x86, espaço e carga atual da VPS. Não pressupor capacidade para 500 usuários.

## 4. Escopo da primeira entrega

Obrigatório: cadastro pendente, código e reenvio, confirmação, login, refresh, logout, usuário atual, isolamento por conta, limitação de tentativas, auditoria, documentação e deploy.

Complemento recomendado antes de usuários reais: recuperação de senha e encerramento de conta. São tarefas explícitas no plano, separadas do caminho de login. A exclusão atende ao requisito documental; recuperação evita contas sem possibilidade de acesso.

Fora desta entrega: AgroBot, Gemini, diagnósticos, culturas, histórico, sincronização offline, login social e MFA em todos os acessos.

Os documentos chamam a confirmação inicial de “2FA”. Implementaremos senha + código de e-mail no primeiro acesso, sem afirmar que isso equivale a MFA permanente ou resistente a phishing. Manter email_verified_at separado de eventual configuração futura de MFA; reconciliar o campo legado dois_fatores_ativo do DER com esse significado.

## 5. Contrato HTTP proposto

Prefixo /api/v1. JSON com campos em snake_case, IDs UUID, datas UTC ISO 8601. Mensagens pt-BR e códigos de erro estáveis.

| Método e rota | Entrada principal | Resultado |
| --- | --- | --- |
| POST /auth/register | name, email, password, privacy_policy_version, accepted_terms | 202: registration_token opaco, expires_in=60, resend_after=60 |
| POST /auth/verify-email | registration_token, code, password | 201: cria usuário ativo e emite sessão |
| POST /auth/resend-code | registration_token | 202: prazo do novo código; respeita espera de 60 s |
| POST /auth/login | email, password | 200: tokens e usuário mínimo |
| POST /auth/refresh | refresh_token | 200: novo par de tokens |
| POST /auth/logout | refresh_token | 204: revoga a sessão associada |
| GET /users/me | Authorization: Bearer access_token | 200: id, name, email, email_verified |
| POST /auth/forgot-password | email | 202: resposta genérica |
| POST /auth/reset-password | reset_token, new_password | 204: altera senha e revoga sessões |
| DELETE /users/me | Bearer e confirmação da senha | 202: encerra acesso e agenda exclusão |
| GET /health/live | nenhuma | 200: processo disponível |
| GET /health/ready | nenhuma | 200 se banco pronto; 503 caso contrário |

Resposta de sessão: access_token, token_type="bearer", expires_in=900, refresh_token, user={id,name,email,email_verified}.
Erro: error={code,message,request_id}; nunca retornar senha, código ou segredo em mensagens.
Status: 401 credenciais/sessão inválidas; 400 código inválido, expirado ou usado; 422 formato inválido; 429 com Retry-After para limites; 503 dependência indisponível.
Cadastros repetidos e recuperação não devem confirmar a existência de contas a terceiros. Respostas genéricas e desafio inerte de formato equivalente para e-mail já registrado; nunca alterar uma conta existente via register.
A confirmação da senha em verify-email cumpre RN02; o app pode reutilizar a senha apenas em memória durante o cadastro e descartá-la ao terminar.

### Parâmetros propostos além do documento

Estes valores são decisões iniciais, ajustáveis por configuração:
- Access token de 15 minutos; refresh com limite absoluto de 7 dias por sessão.
- Código expira quando agora >= expires_at; comparação feita pelo servidor.
- Cinco erros de código invalidam o desafio; reenviar não zera o limite agregado.
- Login: 5 falhas por e-mail em 15 minutos e 30 tentativas por IP em 15 minutos.
- Cadastro, reenvio e recuperação: até 5 envios por e-mail/hora e 20 por IP/hora; reenvio nunca antes de 60 segundos.
- Senha: mínimo de 12 caracteres e máximo de 72 bytes UTF-8 para bcrypt; rejeitar excedente explicitamente, sem truncar. Sem alteração silenciosa de espaços ou conteúdo da senha.
- bcrypt custo inicial 12, medido na VPS; nunca inferior a 10.
- Cadastro pendente expira em 24 horas; token de recuperação aleatório expira em 15 minutos.
- Mudanças nesses limites não alteram os 60 segundos obrigatórios do OTP.

## 6. Persistência e segurança

Tabelas propostas:
- users: id, name, email normalizado e único, password_hash, email_verified_at, status, privacy_policy_version, terms_accepted_at, created_at, updated_at.
- pending_registrations: dados temporários, hash da senha, hash do registration_token aleatório, expiração; a conta ativa só surge na confirmação.
- verification_challenges: cadastro, finalidade, HMAC do código com chave secreta do servidor, expires_at, consumed_at, attempts, last_sent_at.
- sessions e refresh_tokens: usuário, família da sessão, hash do token, expiração, revogação, token substituído.
- password_reset_tokens: hash, usuário, finalidade, expiração e consumo.
- auth_rate_limits: contadores por janela e identificador derivado, atualizados atomicamente.
- auth_events: evento, timestamp, request_id, session_id quando existente e metadados mínimos.
- deletion_requests: solicitação e estado de exclusão para rastrear cumprimento do prazo.

Normalizar e-mail de forma consistente sem remover pontos ou aplicar regras específicas do Gmail. Índice único no banco, incluindo testes de cadastros concorrentes. Datas UTC e relógio do servidor sincronizado.

OTP gerado com secrets, inclusive zeros à esquerda; persistir HMAC, pois hash simples de seis dígitos permite enumeração offline. Chave separada da assinatura JWT. Não registrar códigos, tokens ou senhas.

Verificação, consumo de OTP, criação do usuário e criação de sessão devem ser transacionais. Duas confirmações simultâneas só podem gerar uma conta/sessão bem-sucedida.

Access JWT assinado com chave forte e algoritmo fixo, contendo sub, sid, iat, exp, iss e aud; sem dados pessoais. Todas as rotas protegidas validam assinatura, claims, usuário ativo e sessão não revogada. Isso permite logout efetivo mesmo antes da expiração do JWT.

Refresh opaco aleatório de alta entropia, persistido como hash e rotacionado atomicamente. Reutilização de token já consumido revoga a família de sessão. O iOS deve serializar renovações para evitar corridas.

Limites persistidos e atômicos, inclusive após reinício do container. Confiar em cabeçalhos de IP encaminhado somente do proxy conhecido. Respostas de login genéricas, com verificação de hash fictício para usuário inexistente.

Enviar e-mail com timeout e tratamento de falha. Desafio pode ficar pendente para nova tentativa; nunca emitir tokens ou ativar conta porque o envio falhou. Sem fila nesta fase, medir latência real de entrega: o minuto começa na emissão do desafio, não na chegada ao destinatário.

Criptografia: confirmar que o volume onde ficam os dados do PostgreSQL é um volume OCI com AES-256 em repouso. Isso protege o armazenamento, não impede consultas por um administrador autorizado. Dumps externos precisam de criptografia própria ou armazenamento com AES-256; não presumir que a proteção do volume acompanha o arquivo exportado.

Exclusão: revogar sessões imediatamente, purgar dados ativos e temporários, aplicar retenção de logs sem credenciais e política de backups compatível com o prazo máximo de 30 dias. Proposta: backups com retenção máxima de 14 dias e restauração que reaplica as exclusões antes de liberar acesso. A implementação técnica não deve ser descrita como certificação automática de conformidade legal.

## 7. Estrutura de arquivos planejada

- pyproject.toml e lockfile: dependências, testes e lint.
- app/main.py: montagem da aplicação, erros e rotas.
- app/core/config.py, security.py, logging.py: configuração, primitivas de segurança e logs.
- app/db/session.py e migrations/: conexão e migrações Alembic.
- app/modules/auth/{router,schemas,models,service,repository}.py: cadastro, desafios e sessões.
- app/modules/users/{router,schemas,models,service}.py: perfil e encerramento.
- app/integrations/email.py: contrato Mailer.send_verification(to, code, expires_seconds) e send_password_reset(to, token).
- app/jobs/cleanup.py: descarte de dados temporários e execução de exclusões; execução agendada sem concorrência.
- tests/{unit,integration}/: relógio e e-mail substituíveis, integração com PostgreSQL real de teste.
- Dockerfile, compose.yaml, .dockerignore, .env.example: execução reproduzível.
- .github/workflows/ci.yml: lint, testes, cobertura e build.
- README.md, docs/api.md, docs/deploy.md: consumo Swift e operação.

Essa estrutura será reconciliada com o DER antes de implementar modelos; não criar antecipadamente tabelas de funcionalidades futuras.

## 8. Plano de execução e verificação

Cada tarefa: escrever os testes de comportamento, confirmar que falham pelo motivo esperado, implementar, executar os testes correspondentes e revisar o diff. Commits locais por tarefa quando houver repositório; não publicar nem integrar automaticamente em produção.

### Tarefa 1 — Base executável e contrato
- [ ] Reconciliar USUARIO e convenções do DER; fixar versões compatíveis e dependências.
- [ ] Criar aplicação, settings, PostgreSQL local, migração inicial, health checks e esquema de erros.
- [ ] Produzir interfaces get_db() e configuração validada no startup.
- [ ] Testar: /health/live=200; /health/ready=503 sem banco; configuração de produção rejeita segredos ausentes ou valores de teste.
- [ ] Verificar com docker compose up --build, alembic upgrade head e pytest tests/integration/test_health.py.

### Tarefa 2 — Cadastro, código e e-mail
- [ ] Implementar register, verify-email e resend-code usando Mailer e relógio injetáveis.
- [ ] Transacionar desafio e ativação; manter pendências sem acesso autenticado.
- [ ] Testar: nome/e-mail/senha inválidos; e-mail repetido normalizado; concorrência; zeros à esquerda; código aceito em 59 s e rejeitado em 60 s; uso único; senha incorreta na confirmação; reenvio bloqueado em 59 s e liberado em 60 s; código antigo rejeitado; limite de erros; falha no envio sem ativação.
- [ ] Verificar com pytest tests/integration/test_registration.py tests/integration/test_verification.py.

### Tarefa 3 — Login, autorização e sessões
- [ ] Implementar login, get_current_user(), /users/me, refresh e logout.
- [ ] Produzir dependência comum de usuário autenticado para futuros módulos.
- [ ] Testar: login válido; usuário inexistente e senha errada com mesma resposta; pendente não entra; JWT expirado/adulterado ou com audience errada; token de outro ambiente; dados retornados pertencem ao titular; logout invalida JWT e refresh; rotação; reuso e concorrência.
- [ ] Verificar com pytest tests/integration/test_login.py tests/integration/test_sessions.py tests/integration/test_authorization.py.

### Tarefa 4 — Recuperação, exclusão e proteção contra abuso
- [ ] Implementar recuperação, encerramento, limpeza e limites persistidos.
- [ ] Revogar todas as sessões após redefinição de senha ou encerramento.
- [ ] Testar: recuperação com resposta genérica; token expirado/usado; senha alterada; exclusão idempotente; purga no prazo; 429 e Retry-After; limites preservados após reinício e sob concorrência; logs sem segredos.
- [ ] Verificar com pytest tests/integration/test_recovery.py tests/integration/test_deletion.py tests/integration/test_rate_limits.py.

### Tarefa 5 — Entrega do contrato ao app Swift
- [ ] Gerar OpenAPI e exemplos JSON reais de sucesso/erro para cada rota.
- [ ] Documentar URLSession, Codable, Bearer, Keychain, expiração, timeout e códigos da API.
- [ ] No app: guardar refresh no Keychain; access preferencialmente em memória; nunca senha em UserDefaults; refresh serializado com no máximo uma repetição da chamada.
- [ ] Exibir contador a partir dos prazos do servidor, confirmação de e-mail antes do reenvio e mensagem de falta de conexão.
- [ ] Verificar fluxo cadastro → código → home → logout → login → refresh em iPhone/simulador com o responsável pelo Swift. O código do app não está nesta pasta e essa validação permanece dependente do projeto iOS.

### Tarefa 6 — CI, homologação e deploy Oracle/Coolify
- [ ] Validar recursos e carga da VPS, arquitetura CPU, volumes, disponibilidade do Coolify e isolamento dos outros projetos.
- [ ] Configurar CI: ruff check ., pytest --cov=app --cov-fail-under=70 e docker build; sem deploy se algum falhar.
- [ ] Configurar dev e produção separados; segredos no Coolify; build por commit aprovado, preferencialmente fora da VPS se ela tiver pouca memória.
- [ ] Criar PostgreSQL persistente, executar migração como etapa única antes do rollout e verificar readiness.
- [ ] Criar DNS no provedor autoritativo atual, apontar para a VPS, configurar HTTPS e verificar cadeia TLS; liberar regras necessárias no firewall do host e OCI.
- [ ] Configurar remetente e-mail e registros SPF/DKIM/DMARC conforme o provedor escolhido; verificar entrega real dentro da janela do OTP.
- [ ] Agendar backup diário criptografado fora da VPS, retenção máxima de 14 dias e alertas de falha; restaurar em banco descartável.
- [ ] Fazer smoke test externo completo; testar rollback de imagem. Migrações devem ser retrocompatíveis; rollback de aplicação não desfaz migração automaticamente.
- [ ] Medir carga em homologação com capacidade protegida para não afetar Zelo/app-bolsa. A meta de 500 usuários simultâneos precisa de cenário e taxa de requisições definidos; não significa 500 hashes de senha simultâneos.
- [ ] Entregar URL HTTPS, OpenAPI/Swagger de dev, exemplos, usuário de teste criado por fluxo normal e instruções de operação.
- [ ] Atualizar os DOCX em uma tarefa posterior para refletir a infraestrutura realmente entregue.

## 9. Critérios para considerar pronto

- Cadastro exige confirmação; usuário não confirmado nunca recebe sessão completa.
- OTP de seis dígitos, 60 s, uso único e reenvio controlado comprovados por testes.
- Login, refresh, logout e /users/me consumíveis pelo Swift.
- Proteções contra abuso, isolamento, logs e cobertura >=70% verificados.
- Dados persistem após redeploy; PostgreSQL inacessível publicamente.
- HTTPS e e-mail real funcionam; dev e produção isolados.
- Backup restaurado com sucesso; runbook de falha e rollback disponível.
- Sem declarar cumpridos 99% de disponibilidade ou 500 usuários apenas porque o deploy subiu: dependem de monitoramento e teste de capacidade.

## 10. Infraestrutura e documentação ainda a confirmar

Esses dados não impedem desenvolver e testar localmente; são necessários para publicar:
- Domínio/subdomínio exato e provedor que controla o DNS.
- Recursos livres da VPS, arquitetura de CPU e acesso ao projeto Coolify.
- Provedor de e-mail, remetente autorizado, credenciais e limites de envio.
- Destino externo de backups, criptografia, retenção e alertas.
- Local do repositório Git e projeto Swift; formatos esperados pela tela atual.

Não foram acessados Oracle, Coolify, Firebase, DNS ou projetos Zelo/app-bolsa. Não há orçamento de infraestrutura validado; reaproveitar VPS pode reduzir custo incremental, mas e-mail, backups e recursos extras podem ser cobrados.

Atualizações documentais previstas: AWS/Supabase → Oracle/Coolify; diagrama de implantação; configuração de criptografia e backups; nomenclatura da confirmação inicial; versões de dependências validadas. A menção atual a RAID 1/espelhamento não pode ser marcada como atendida por um único container e um backup; documentar durabilidade do volume e recuperação reais ou implementar a redundância exigida.

## 11. Referências técnicas consultadas

- FastAPI, segurança com JWT: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- Coolify, aplicações: https://coolify.io/docs/applications/
- Coolify, rede e proxy: https://coolify.io/docs/core/networking-in-coolify
- Coolify, backups e teste de restauração: https://coolify.io/docs/databases/backups
- Firebase, autenticação Apple por senha: https://firebase.google.com/docs/auth/ios/password-auth
- Firebase, verificação de tokens no backend: https://firebase.google.com/docs/auth/admin/verify-id-tokens
- Oracle, criptografia dos volumes: https://docs.oracle.com/en-us/iaas/Content/Security/Reference/blockstorage_security.htm
- Apple, Keychain: https://developer.apple.com/documentation/security/keychain-services

