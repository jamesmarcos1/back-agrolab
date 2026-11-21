# Entrega do login AgroLab para a equipe Swift

Preparado em 06/10/2026. Este arquivo é o ponto de partida para quem vai implementar o login no aplicativo iOS.

## Mensagem pronta para enviar com o ZIP

> Pessoal, a API de autenticação do AgroLab está publicada.
>
> Base: https://api-agrolab.jamesmarcos.com/api/v1
>
> Login: POST /auth/login, enviando JSON com email e password.
>
> O ZIP inclui o guia Swift, o contrato OpenAPI e o relatório de validação do backend. Comecem pelo arquivo docs/swift-integration.md: tem as requisições, respostas, tratamento de erros, Keychain, renovação de sessão e checklist para testar no iPhone.
>
> O login precisa de uma conta com e-mail confirmado. Cada um deve cadastrar sua própria conta de teste, usando uma caixa de e-mail que controla, e confirmar o código recebido. O código dura 60 segundos; o app também precisa permitir o reenvio após esse prazo.
>
> Para entregar o login, precisamos conseguir entrar, consultar /users/me, guardar o refresh token no Keychain, restaurar a sessão ao reabrir o app, renovar os tokens e sair. Validem senha incorreta, falta de internet e o roteiro do guia no Xcode/iPhone. Para o fluxo completo de autenticação, implementem também cadastro/confirmação, recuperação e encerramento de conta.
>
> Se alguma chamada falhar, me mandem a rota, o status HTTP, error.code, request_id e o horário. Não mandem senhas, códigos ou tokens.

## Arquivos do pacote

O arquivo `entregas/agrolab-swift-2026-10-06.zip` contém somente:

| Arquivo | Uso |
| --- | --- |
| `LEIA-ME.md` | Esta orientação e a mensagem acima |
| `docs/swift-integration.md` | Guia principal: o que implementar no app e como validar |
| `docs/api.md` | Contrato resumido das rotas e exemplos JSON |
| `docs/openapi.json` | Especificação das operações, campos e respostas |
| `docs/validation-2026-10-06.md` | Evidências e limites da validação já feita no backend |

Os colegas não precisam de acesso à VPS, ao Coolify, ao banco ou ao Resend para consumir a API. O cliente Swift não usa chave de API compartilhada: recebe seus próprios tokens depois de autenticar. Não enviar a pasta inteira do backend, `.env`, `.runtime`, backups ou chaves SSH junto com a integração.

## Como começar

1. Conferir a conexão com `GET https://api-agrolab.jamesmarcos.com/health/ready`. O esperado é HTTP 200 com `{"status":"ready"}`; esse teste verifica API/banco, não o envio de e-mail.
2. Configurar a base HTTPS no app e os DTOs `Codable` seguindo o guia. Usar `Content-Type: application/json` e `Accept: application/json`. Não usar a porta interna `8000` na URL publicada.
3. Implementar `POST /auth/login` e `GET /users/me`. A segunda chamada recebe `Authorization: Bearer ACCESS_TOKEN`; não enviar a senha novamente.
4. Implementar armazenamento, restauração, refresh e logout antes de considerar a sessão pronta. O refresh token é substituído após cada renovação; chamadas concorrentes devem compartilhar uma única renovação.
5. Completar as telas do fluxo de autenticação e executar o roteiro de aceite no guia. Tratar respostas `204` sem tentar decodificar JSON e respeitar `Retry-After` nos erros `429`.

O OTP deve ser `String` de seis dígitos, preservando zeros iniciais. Senhas de cadastro/redefinição precisam de pelo menos 12 caracteres e no máximo 72 bytes UTF-8. A versão de política atualmente aceita é `2026-10-06`; o app só envia `accepted_terms: true` depois da aceitação explícita.

## Quando podemos considerar a integração concluída

Precisamos receber a confirmação de compilação no Xcode e o checklist do guia preenchido. Para a tela de login, o aceite inclui credenciais válidas/incorretas, perfil autenticado, reabertura do app, renovação de sessão, logout e falhas de rede. Para concluir o fluxo completo, incluir cadastro com confirmação/reenvio, recuperação de senha e encerramento de conta.

Na validação do backend registrada em 06/10/2026, passaram 48 testes automatizados com cobertura de 92,46% e 33 verificações externas. O relatório detalha os ambientes e cenários. O projeto Swift não está neste workspace: ainda não foi compilado nem testado no simulador/iPhone, e o teste SMTP com destinatário oficial do Resend não comprova recebimento em uma caixa pessoal.

O ZIP é uma entrega da integração. As pendências operacionais do servidor continuam registradas no README e em `docs/deploy.md` do backend.
