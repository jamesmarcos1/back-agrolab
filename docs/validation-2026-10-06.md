# Revalidação da API para integração Swift

Data: 06/10/2026, horário de Brasília (America/Sao_Paulo). Verificações externas de infraestrutura/erros iniciadas às 15:14. Os testes abaixo foram executados novamente nesta entrega; os resultados não foram deduzidos apenas da publicação anterior.

**Resultado:** 48 testes automatizados passaram, cobertura 92,46%, e 33 verificações externas passaram (10 de infraestrutura/erros e 23 chamadas do fluxo de autenticação). O backend está apto para a integração funcional descrita em `docs/swift-integration.md`. O app iOS ainda precisa ser implementado/testado no ambiente Apple.

## Ambiente e escopo

| Verificação | Ambiente |
| --- | --- |
| Suíte de testes | Python 3.13.1 no Windows + PostgreSQL 18.6 do Docker local |
| Isolamento da suíte | Banco novo com sufixo `_test`, criado exclusivamente para esta execução e removido ao terminar |
| API publicada | `https://api-agrolab.jamesmarcos.com` na Oracle/Coolify |
| Confirmação/recuperação | SMTP real do Resend, com destinatário de teste oficial `delivered+...@resend.dev` |
| Conta pública utilizada | Conta temporária criada pelo cadastro; encerramento solicitado pela própria sessão autenticada |
| Swift/Xcode | Não disponível no workspace; nenhum `.swift`, `.xcodeproj` ou `.xcworkspace` encontrado |

A suíte usou PostgreSQL real, mas relógio e envio de e-mail substituíveis para testar expirações/erros sem aguardar minutos nem enviar dezenas de mensagens. O fluxo público usou a API hospedada e a integração SMTP real. O destinatário oficial do provedor simula entrega; isso não comprova chegada na caixa Gmail/Outlook nem latência de uma caixa pessoal.

Nenhum teste de tabelas foi apontado para o banco produtivo. Nenhuma limpeza geral foi disparada em produção. A exclusão solicitada pela conta temporária fica para o job horário do backend. Senhas, OTPs e tokens não fazem parte deste relatório.

## 1. Suíte automatizada

Comando de teste executado com `TEST_DATABASE_URL` definido apenas no processo e apontando para o banco descartável:

```text
python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=70
```

Resultado: **48 passed, 2 warnings em 27,67 s**. Cobertura total **92,46%**; mínimo exigido **70%**.

Os dois avisos são de depreciação da integração Starlette/AnyIO no TestClient. Não produziram falhas nos testes; atualização futura das dependências deve respeitar os locks e repetir a suíte.

Comportamentos cobertos incluem cadastro pendente, confirmação única, preservação de zeros no OTP, aceitação em 59 s/rejeição em 60 s, reenvio, erro SMTP, normalização, limites, JWT adulterado/expirado, perfil do titular, refresh/replay, logout, recuperação, exclusão e concorrência com a limpeza.

## 2. Infraestrutura e respostas externas

| Verificação executada | Resultado observado | Estado |
| --- | --- | --- |
| Conexão TLS com cadeia/hostname verificados | TLS 1.3; certificado válido até 04/01/2027 10:27:17 no horário de Brasília | Passou |
| GET `/health/live` | 200, `{"status":"ok"}` | Passou |
| GET `/health/ready` | 200, `{"status":"ready"}` | Passou |
| GET `/api/v1/users/me` sem Bearer | 401, INVALID_SESSION | Passou |
| POST `/api/v1/auth/login` sem campos | 422, VALIDATION_ERROR | Passou |
| POST login com credenciais inválidas | 401, INVALID_CREDENTIALS | Passou |
| POST refresh com token inválido | 401, INVALID_SESSION | Passou |
| GET `/docs` de produção | 404, conforme configuração que desabilita Swagger público | Passou |
| Headers da resposta | Cache-Control no-store, HSTS e X-Content-Type-Options nosniff | Passou |
| Acesso HTTP a rota da API | 302 encaminhando para HTTPS | Passou |

As respostas de erro verificadas incluíram `error.code` e `error.request_id`, permitindo tratamento estável no Swift e correlação de suporte.

## 3. Fluxo público de autenticação

As etapas abaixo resumem **23 chamadas verificadas**, incluindo acessos antes/depois das mutações e login intermediário. Todas retornaram o status esperado.

| Cenário | Evidência observada | Estado |
| --- | --- | --- |
| Cadastro pendente | 202; registration_token opaco e prazos de 60 s; resposta não contém OTP | Passou |
| Reenvio antecipado | 429, RESEND_TOO_EARLY e Retry-After positivo | Passou |
| Confirmação pelo e-mail | 201; código obtido da prévia do e-mail no Resend; confirmação concluída em 7,8 s desde o início da solicitação | Passou |
| Perfil após confirmação | 200; UUID válido, e-mail do titular e email_verified=true | Passou |
| Senha incorreta | 401, INVALID_CREDENTIALS | Passou |
| Login correto | 200; bearer, expires_in=900 e tokens com tipos/formato esperados | Passou |
| Refresh | 200; refresh novo diferente do anterior; novo access acessa o perfil | Passou |
| Reutilização do refresh anterior | 401; sessão da família revogada, novo access passa a receber 401 | Passou |
| Logout e repetição do logout | 204 nas duas chamadas; access encerrado recebe 401 | Passou |
| Solicitar recuperação | 202; e-mail de recuperação emitido pelo Resend | Passou |
| Redefinir senha com token do e-mail | 204; sessão anterior recebe 401 e senha antiga não faz login | Passou |
| Login com senha nova | 200 | Passou |
| Encerrar a própria conta | 202; access bloqueado imediatamente e novo login recusado | Passou |

Os formatos de sessão/perfil/desafio também foram conferidos para a decodificação: String nos tokens, Int nos prazos, Bool em email_verified e UUID em id. `/users/me` retorna o usuário diretamente; login/verify/refresh retornam o usuário dentro de `user`.

## 4. O que ainda precisa ser validado

| Item | Motivo/como concluir |
| --- | --- |
| Compilação do cliente Swift | Projeto não está nesta pasta e Xcode não está disponível; compilar no Mac |
| Decodificação pelos DTOs Swift reais | Executar XCTest com respostas do contrato e com o APIClient do projeto |
| Persistência/erros do Keychain | Testar no simulador/iPhone, incluindo fechar/reabrir o app |
| Concorrência de refresh no cliente | Simular duas respostas 401 simultâneas e confirmar uma única renovação |
| Navegação, loading e UX offline | Executar roteiro manual do guia; API correta não comprova esses comportamentos |
| Caixa pessoal e preenchimento do código | Cadastrar e-mail controlado pelo testador e conferir recebimento no iPhone |
| Exclusão física da nova conta temporária | Solicitação aceita e acesso bloqueado; não aguardado o próximo ciclo horário nesta validação |
| Disponibilidade mensal e carga de 500 usuários | Exigem monitoramento e teste de carga próprios; não comprovados por smoke test |
| Backup externo automático e custódia da chave | Continuam pendentes conforme o runbook; não são resolvidos pela integração Swift |

Para considerar o aplicativo pronto, compilar o projeto, executar seus testes e preencher o roteiro de aceite no guia. Este relatório confirma o funcionamento observado do backend neste momento, sem declarar o aplicativo iOS validado.
