# Contrato da autenticação AgroLab

JSON, snake_case, UUIDs, mensagens em pt-BR. Prefixo `/api/v1`. API local `http://localhost:8000`; endereço de produção previsto `https://api-agrolab.jamesmarcos.com`.

## Cadastro e confirmação

`POST /auth/register` com:

```json
{"name":"Marcos","email":"produtor@example.com","password":"Senha-segura-123!","accepted_terms":true,"privacy_policy_version":"2026-10-06"}
```

Resposta 202:

```json
{"registration_token":"TOKEN_OPACO_RECEBIDO","expires_in":60,"resend_after":60}
```

A UI exibe a verificação, guarda o token e mantém temporariamente a senha em memória. A política enviada deve coincidir com a versão configurada no servidor. A API não entrega o código de e-mail na resposta.

`POST /auth/verify-email`:

```json
{"registration_token":"TOKEN_OPACO_RECEBIDO","code":"000007","password":"Senha-segura-123!"}
```

Sucesso 201 retorna sessão; o usuário pode acessar a home. Código é string para preservar zeros. `POST /auth/resend-code` recebe apenas registration_token e retorna 202 com o novo prazo; antes de 60 segundos retorna 429. A UI deve confirmar o e-mail antes do reenvio, conforme FA02.

## Login e sessão

`POST /auth/login` recebe email e password. Sucesso 200, com formato também usado por confirmação e refresh:

```json
{
  "access_token":"JWT_RECEBIDO",
  "refresh_token":"TOKEN_OPACO_RECEBIDO",
  "token_type":"bearer",
  "expires_in":900,
  "user":{"id":"UUID_RECEBIDO","name":"Marcos","email":"produtor@example.com","email_verified":true}
}
```

`GET /users/me` usa `Authorization: Bearer JWT_RECEBIDO`. Retorna o objeto user. `POST /auth/refresh` recebe refresh_token e retorna um par novo. Sempre substitua o refresh anterior no Keychain antes de liberar outras chamadas. A duração de sete dias não é estendida pela rotação.

`POST /auth/logout` recebe refresh_token e retorna 204, sem corpo. É idempotente. Remova os dados locais após logout. Tokens de sessões encerradas deixam de autorizar `/users/me` imediatamente.

## Recuperação e encerramento

`POST /auth/forgot-password` recebe email. Sempre retorna 202 com mensagem genérica. O e-mail de recuperação contém um token opaco para inserir na tela de recuperação; não depende de um site público ou deep link ainda não definido pelo projeto Swift.

`POST /auth/reset-password` recebe reset_token e new_password. Retorna 204, revoga sessões anteriores e exige novo login. Token expira em 15 minutos e só pode ser usado uma vez.

`DELETE /users/me` usa Bearer e corpo password. Retorna 202 com confirmação de solicitação, bloqueia o acesso e agenda exclusão. Depois de aceitar o encerramento, novas chamadas autenticadas retornam 401, pois a sessão já foi revogada.

## Erros e renovação no Swift

```json
{"error":{"code":"INVALID_CREDENTIALS","message":"E-mail ou senha incorretos.","request_id":"UUID_DA_REQUISICAO"}}
```

| Status | Tratamento |
| --- | --- |
| 400 | Código/token inválido, expirado ou usado; solicitar nova ação |
| 401 | Credenciais erradas ou sessão inválida; em chamada protegida, tentar refresh uma única vez |
| 422 | Campos inválidos, senha fora da regra ou política desatualizada |
| 429 | Aguardar o cabeçalho Retry-After |
| 503 | Banco/serviço indisponível; apresentar mensagem e opção de tentar novamente |

Para uma chamada protegida que receba 401, um coordenador de sessão (por exemplo, um actor) deve reunir as chamadas concorrentes em uma única renovação. Se refresh falhar, apagar os tokens e voltar ao login. Não reenviar automaticamente register/verify/reset sem avaliar o resultado: podem já ter sido processados antes de uma perda de conexão.

A validade do código começa no servidor no momento da emissão; o prazo recebido ajuda o contador da UI, mas não aumenta a validade em função da latência. Falta de conexão deve ser tratada como erro de URLSession, não como credencial inválida. E-mails podem atrasar: aguarde o contador e permita reenvio.

No simulador do mesmo computador, usar localhost. Em iPhone físico, a URL local precisa ser alcançável pela rede e o ATS precisa ser considerado para desenvolvimento; homologação HTTPS é o caminho preferido. Não desabilitar ATS globalmente para produção.

OpenAPI está em `openapi.json`. Foi exportado do código com `python -m scripts.export_openapi`; não contém segredos ou dados do banco.
