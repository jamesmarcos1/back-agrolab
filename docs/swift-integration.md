# Integração do AgroLab com Swift / SwiftUI

Guia de entrega para o responsável pelo aplicativo iOS. Atualizado em 06/10/2026. Backend publicado e validado; o projeto Swift não está nesta pasta, portanto este guia não representa uma implementação já compilada no Xcode.

## 1. Configuração para começar

| Item | Valor |
| --- | --- |
| Base da API | `https://api-agrolab.jamesmarcos.com/api/v1` |
| Login | `POST https://api-agrolab.jamesmarcos.com/api/v1/auth/login` |
| Teste de conexão | `GET https://api-agrolab.jamesmarcos.com/health/ready` |
| Resposta de saúde esperada | HTTP 200, `{"status":"ready"}` |
| Formato | JSON, nomes de campos em `snake_case` |
| Headers JSON | `Content-Type: application/json` e `Accept: application/json` |
| Header autenticado | `Authorization: Bearer ACCESS_TOKEN` |
| Versão da política atualmente aceita | `2026-10-06` |

Usar a URL HTTPS publicada tanto no iPhone quanto no simulador. Não incluir `:8000`: essa é a porta interna do container. A raiz do domínio não é uma tela de login; as chamadas usam as rotas da tabela.

`http://localhost:8000` só funciona se o backend estiver no computador ao qual esse localhost se refere. O backend local desta entrega está no Windows; o localhost do simulador no Mac não aponta para esse Windows. Swagger local: `http://localhost:8000/docs`; Mailpit local: `http://localhost:8025`.

Não é necessário desabilitar ATS, aceitar certificados inválidos ou instalar SDK de Firebase para esse login. URLSession atende às chamadas HTTP da integração. [Referência Apple: URLSession](https://developer.apple.com/documentation/foundation/urlsession).

## 2. Arquivos e responsabilidades sugeridos no app

Adaptar os nomes à estrutura MVVM que o projeto já utiliza.

| Arquivo/componente a implementar | Responsabilidade |
| --- | --- |
| `AppEnvironment` | Base URL e versão da política; separar configurações de desenvolvimento/produção |
| `AuthDTOs` | Codable dos corpos e respostas abaixo |
| `APIClient` | URLSession, JSON, headers, status HTTP, erros e timeout |
| `AuthService` | Métodos register, verify, resend, login, refresh, logout, forgot, reset e delete |
| `KeychainStore` | Gravar, atualizar, ler e remover o refresh token; tratar erros do Keychain |
| `AuthSession` | Estado da sessão, renovação compartilhada e invalidação de operações antigas |
| `LoginViewModel` | Formulário, loading, erro de credenciais e entrada na home |
| `RegistrationViewModel` / `VerificationViewModel` | Cadastro pendente, código, prazo e reenvio |
| ViewModels de recuperação/perfil | Redefinição de senha, logout e encerramento |

Atualizações de UI pertencem ao `MainActor`. Evitar duas requisições ao tocar duas vezes no botão: desabilitar a ação enquanto estiver em andamento. Só navegar para a home após obter e instalar uma sessão válida.

## 3. Contrato completo que o Swift precisa consumir

As rotas abaixo são relativas à base `/api/v1`. A coluna de sucesso indica o status esperado; `204` não contém JSON.

| Método/rota | Corpo JSON | Sucesso | Resposta |
| --- | --- | --- | --- |
| POST `/auth/register` | `name`, `email`, `password`, `accepted_terms`, `privacy_policy_version` | 202 | Desafio pendente |
| POST `/auth/verify-email` | `registration_token`, `code`, `password` | 201 | Sessão + usuário |
| POST `/auth/resend-code` | `registration_token` | 202 | Desafio e novos prazos |
| POST `/auth/login` | `email`, `password` | 200 | Sessão + usuário |
| POST `/auth/refresh` | `refresh_token` | 200 | Novos tokens + usuário |
| POST `/auth/logout` | `refresh_token` | 204 | Sem corpo |
| GET `/users/me` | Sem corpo; Bearer | 200 | Usuário diretamente, sem envelope `user` |
| POST `/auth/forgot-password` | `email` | 202 | Mensagem genérica |
| POST `/auth/reset-password` | `reset_token`, `new_password` | 204 | Sem corpo |
| DELETE `/users/me` | `password`; Bearer | 202 | Confirmação da solicitação |

Não adicionar campos extras: a API rejeita campos desconhecidos com 422. O cadastro não possui telefone nesta entrega.

### Cadastro pendente

O e-mail abaixo ilustra o formato. Para testar entrega no app, usar uma caixa de e-mail que o testador controla; para desenvolvimento local, os e-mails ficam no Mailpit.

```json
{
  "name": "Nome do produtor",
  "email": "produtor@example.com",
  "password": "Senha-segura-123!",
  "accepted_terms": true,
  "privacy_policy_version": "2026-10-06"
}
```

`accepted_terms` só deve ser verdadeiro após a aceitação explícita da pessoa. Apresentar os termos/política no app; combinar alterações de versão com o backend.

Resposta 202:

```json
{
  "registration_token": "TOKEN_OPACO_RECEBIDO",
  "expires_in": 60,
  "resend_after": 60
}
```

Esse token é de cadastro pendente, não de acesso. Manter token, e-mail e senha temporariamente em memória durante a confirmação. Um cadastro pendente não pode abrir a home. `202` indica aceitação da solicitação; não comprova entrega do e-mail nem informa se o endereço já pertence a uma conta.

### Confirmar código

```json
{
  "registration_token": "TOKEN_OPACO_RECEBIDO",
  "code": "000007",
  "password": "Senha-segura-123!"
}
```

`code` é String de seis dígitos: transformar em Int elimina zeros iniciais. O código expira no servidor em 60 segundos, é de uso único e o reenvio invalida o anterior. A confirmação também verifica a senha do cadastro. Depois de 201, descartar os dados temporários e instalar os tokens da sessão.

### Sessão recebida no login, confirmação e refresh

```json
{
  "access_token": "JWT_RECEBIDO",
  "refresh_token": "TOKEN_OPACO_RECEBIDO",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "c0a80101-1234-4567-89ab-123456789abc",
    "name": "Nome do produtor",
    "email": "produtor@example.com",
    "email_verified": true
  }
}
```

O access token dura 15 minutos. A sessão tem duração absoluta de até sete dias; renovar não reinicia esses sete dias. No refresh, substituir o token anterior pelo novo, inclusive no Keychain.

`GET /users/me` retorna apenas o objeto mostrado dentro de `user`. O perfil deve vir dessa resposta/autenticação; o cliente não escolhe o ID de outro usuário.

### Recuperação e encerramento

`forgot-password` recebe e-mail e retorna mensagem genérica. O e-mail de recuperação contém um token para inserir na tela do app; não há deep link implementado nessa entrega. `reset-password` recebe esse token e a nova senha, expira em 15 minutos e revoga as sessões anteriores. Após 204, voltar ao login.

Para encerrar conta, confirmar a senha, enviar DELETE com Bearer e JSON `{"password":"SENHA_INFORMADA"}`. Após 202, remover os tokens locais e voltar ao login. O acesso fica bloqueado imediatamente; a purga é executada pelo job do backend.

## 4. Regras de formulário e contador

- Cadastro/nova senha: mínimo de 12 caracteres e máximo de 72 bytes UTF-8. Em Swift, conferir `password.utf8.count <= 72`; o servidor continua sendo a autoridade da validação. Se contar o mínimo no cliente, Python conta pontos Unicode; `unicodeScalars.count` se aproxima dessa regra, enquanto `String.count` conta grafemas.
- Não aplicar trim, minúsculas ou qualquer transformação à senha. E-mail pode ter espaços nas extremidades removidos; a API normaliza para minúsculas.
- Nome é obrigatório; limite de 120 caracteres. Login exige e-mail e senha; não precisa reenviar nome/termos.
- Usar teclado numérico para o código, mas guardar o valor como String.
- Os 60 segundos começam na emissão no servidor. O tempo de rede/e-mail não prolonga a validade. O contador é uma indicação da tela; tratar `INVALID_CODE` mesmo que a tela ainda mostre segundos.
- Para um contador conservador de expiração, considerar o instante em que iniciou a requisição e recalcular ao voltar do segundo plano. Para o reenvio, aguardar `resend_after` contado a partir da resposta, evitando liberar antes da janela do servidor.
- Ao receber 429, respeitar `Retry-After`; manter os dados da tela e apresentar a espera. Não disparar reenvios automáticos.

## 5. Tokens, inicialização e concorrência

Guardar **refresh token no Keychain** e access token preferencialmente em memória. Não guardar senha, OTP, registration_token ou tokens em UserDefaults. Não registrar bodies de autenticação, headers Authorization ou tokens no console/analytics.

Usar item Generic Password com service/account próprios do AgroLab. Para o MVP em primeiro plano, considerar `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` e não habilitar sincronização desse token. Tratar falha ao salvar/ler; não apresentar login persistente como bem-sucedido se o novo refresh não foi armazenado. [Referência Apple: acessibilidade do Keychain](https://developer.apple.com/documentation/security/restricting-keychain-item-accessibility).

Ao abrir o app:

1. Exibir estado de restauração, sem liberar a home prematuramente.
2. Ler refresh do Keychain. Se não houver, exibir login.
3. Renovar uma vez, salvar o novo refresh e instalar access/usuário.
4. Conferir `/users/me` quando necessário e liberar a home somente com sessão válida.
5. Se a sessão for recusada, remover tokens e voltar ao login. Falta de rede deve aparecer como falta de rede, sem ser rotulada como senha incorreta.

Para uma rota protegida que retorna 401: fazer uma renovação e repetir a chamada original **no máximo uma vez**. Não fazer isso no 401 do próprio login ou refresh. Não criar ciclos infinitos entre `/users/me` e `/auth/refresh`.

**Um actor sozinho não garante uma única chamada de refresh durante awaits.** Manter uma operação de renovação em andamento (`Task` compartilhada); chamadas concorrentes aguardam essa mesma operação. Ela deve incluir requisição, gravação do novo refresh e instalação da sessão antes de liberar os demais chamadores. [Referência Apple: reentrância e actors](https://developer.apple.com/videos/play/wwdc2021/10133/).

Incrementar uma geração/versão de sessão no login/logout. Uma operação antiga que termine depois do logout não pode reinstalar tokens nem apagar a renovação de uma sessão nova. Conferir a geração antes de aplicar o resultado.

Se o envio do refresh ocorrer mas a resposta se perder, o servidor pode já ter consumido o token. Não repetir automaticamente o refresh antigo: isso pode revogar a família de sessão por replay. Tratar o resultado incerto solicitando novo login quando a conexão permitir.

Logout online: enviar refresh atual, aguardar 204 e limpar estado local/Keychain. Se não houver rede, ainda pode encerrar o estado local, mas não afirmar que a revogação no servidor foi confirmada.

## 6. Exemplo Swift de DTOs e login

Exemplo de referência para adaptar à camada de rede do projeto. Não implementa Keychain nem coordenação de sessão. **Não foi compilado no Xcode nesta máquina Windows**; conferir também as configurações de isolamento do projeto ao usar Swift 6.

```swift
import Foundation

struct UserDTO: Decodable, Sendable {
    let id: UUID
    let name: String
    let email: String
    let emailVerified: Bool

    enum CodingKeys: String, CodingKey {
        case id, name, email
        case emailVerified = "email_verified"
    }
}

struct SessionDTO: Decodable, Sendable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let expiresIn: Int
    let user: UserDTO

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
        case expiresIn = "expires_in"
        case user
    }
}

struct ServerProblem: Decodable, Sendable {
    let code: String
    let message: String
    let requestID: String?

    enum CodingKeys: String, CodingKey {
        case code, message
        case requestID = "request_id"
    }
}

struct ErrorEnvelope: Decodable {
    let error: ServerProblem
}

enum APIClientError: Error {
    case invalidResponse
    case server(status: Int, problem: ServerProblem?, retryAfter: TimeInterval?)
}

struct AuthAPI {
    private struct LoginBody: Encodable {
        let email: String
        let password: String
    }

    let baseURL: URL
    let session: URLSession

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func login(email: String, password: String) async throws -> SessionDTO {
        let url = baseURL.appendingPathComponent("auth")
            .appendingPathComponent("login")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = try JSONEncoder().encode(
            LoginBody(email: email, password: password)
        )

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw APIClientError.invalidResponse
        }
        guard http.statusCode == 200 else {
            let problem = try? JSONDecoder().decode(ErrorEnvelope.self, from: data)
            let retry = http.value(forHTTPHeaderField: "Retry-After")
                .flatMap { TimeInterval($0) }
            throw APIClientError.server(
                status: http.statusCode, problem: problem?.error, retryAfter: retry
            )
        }
        return try JSONDecoder().decode(SessionDTO.self, from: data)
    }
}
```

Instanciar com `URL(string: "https://api-agrolab.jamesmarcos.com/api/v1")` validada. O ViewModel chama `login`, trata erro e entrega `SessionDTO` ao gerenciador de sessão; esse gerenciador persiste refresh, instala access/usuário e então libera a navegação.

Para as outras rotas, reutilizar o tratamento de rede, usando o status esperado da tabela. Logout/reset retornam 204: não tentar decodificar JSON vazio. Os CodingKeys acima são explícitos; não combinar esses mesmos DTOs com `.convertFromSnakeCase`, pois isso pode quebrar o mapeamento.

## 7. Erros e mensagens da tela

Exemplo real de formato:

```json
{"error":{"code":"INVALID_CREDENTIALS","message":"E-mail ou senha incorretos.","request_id":"ID_DA_REQUISICAO"}}
```

| Situação | Ação do app |
| --- | --- |
| 401 / INVALID_CREDENTIALS no login | Mostrar erro e manter formulário; não tentar refresh |
| 401 / INVALID_SESSION em rota protegida | Uma renovação compartilhada e uma repetição; depois login se recusada |
| 400 / INVALID_CODE | Código/senha da confirmação inválidos, expirados ou usados; oferecer reenvio após prazo |
| 422 / VALIDATION_ERROR | Revisar campos; a resposta é genérica e não contém erros individuais do Pydantic |
| 422 / POLICY_VERSION_INVALID | Solicitar atualização da versão dos termos/app; não repetir a mesma versão em loop |
| 429 | Mostrar espera de Retry-After e preservar formulário |
| 500/503 | Mostrar indisponibilidade temporária; não rotular como senha errada |
| URLError / timeout / offline | Mostrar falha de conexão; evitar reenvio automático de mutações |

Usar `request_id` para correlação no suporte. Não mostrar stack traces ou dados privados. Um timeout após register/verify/reset/delete pode deixar resultado incerto; conferir estado antes de repetir a operação. Depois de uma confirmação cuja resposta se perdeu, login normal pode recuperar o acesso.

## 8. Ordem prática de implementação

1. Configuração, DTOs e APIClient: confirmar health e decodificação.
2. Login real + `/users/me`: loading, erro, usuário e navegação.
3. Keychain e AuthSession: restauração ao abrir o app, refresh compartilhado e logout.
4. Cadastro e verificação: fluxo pendente, código String e contador/reenvio.
5. Recuperação, nova senha e encerramento da conta.
6. XCTest para erros/concorrência e roteiro manual abaixo no iPhone/simulador.

## 9. Como validar no iPhone / Xcode

Primeiro abrir o endereço de health no Safari do iPhone. Isso testa conexão/certificado daquele dispositivo; não testa o app. Depois executar o app pelo Xcode com a base HTTPS configurada e uma conta criada pelo próprio fluxo, usando e-mail que o testador controla.

| Conferência | Resultado esperado | Feito no app? |
| --- | --- | --- |
| Cadastro válido | Abre verificação; não abre home antes de confirmar | [ ] |
| Código recebido, dentro dos 60 s | 201 e home após instalação da sessão | [ ] |
| Código começando com zero | Seis dígitos preservados no JSON | [ ] |
| Código expirado/incorreto | Erro tratado; sem sessão; reenvio disponível no prazo | [ ] |
| Reenvio antes de 60 s | Botão bloqueado; eventual 429 tratado | [ ] |
| Reenvio liberado | Novo código; anterior não confirma | [ ] |
| Login correto | Nome/e-mail do titular; perfil vem de `/users/me` | [ ] |
| Login incorreto | Mensagem, sem navegação e sem loop de refresh | [ ] |
| Fechar e reabrir o app | Restaura com refresh do Keychain; não pede senha salva | [ ] |
| Access expirado | Uma renovação e uma repetição da rota; testar após 15+ min ou em XCTest | [ ] |
| Duas chamadas protegidas recebem 401 juntas | Uma única chamada de refresh; ambas aguardam instalação dos novos tokens | [ ] |
| Logout durante refresh | Resposta antiga não restaura login | [ ] |
| Logout online | Volta ao login; JWT encerrado não acessa perfil | [ ] |
| Recuperação de senha | Token do e-mail funciona; senha antiga e sessões antigas deixam de funcionar | [ ] |
| Encerramento | Confirma senha, remove estado local e bloqueia novo acesso | [ ] |
| Modo avião / retorno da rede | Erro de conexão claro, loading encerra, sem requisições em loop | [ ] |
| App em segundo plano na tela de código | Contador recalculado; servidor decide a validade | [ ] |
| Armazenamento/logs | Tokens só no local previsto; sem senha/OTP em UserDefaults ou console | [ ] |

Em XCTest, usar `URLProtocol`/serviço substituível para simular 200/201/202/204, 400/401/422/429/503 e timeout. Conferir requests emitidos, JSON e quantidade de renovações. Asserções de UI/Keychain precisam executar no ambiente Apple. A API pública é para smoke test; testes repetitivos de erros/concorrência devem usar o ambiente local/testes isolados para não consumir limites de produção.

## 10. Critério de aceite e material entregue

Integração aceita quando o app compilar, os testes XCTest do cliente passarem e o roteiro acima for executado no iPhone/simulador. API aprovada isoladamente não comprova armazenamento, navegação ou tratamento de erros do app.

Material do backend: `docs/api.md` (contrato), `docs/openapi.json` (OpenAPI), `README.md` (execução/decisões) e `docs/validation-2026-10-06.md` (evidência desta revalidação). Não foi fornecida conta de teste permanente nem senha de exemplo para usar em produção; criar a própria conta pelo cadastro.
