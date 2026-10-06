# Backend do AgroLab

Este backend implementa a autenticação do aplicativo AgroLab em Swift. Ele cadastra o produtor, confirma seu e-mail, faz login e controla as sessões. Foi criado a partir do UC01 dos três documentos com MVP da pasta `Trabalho-Agrolab`.

## O que foi implementado e por quê

| Entrega | Comportamento | Motivo |
| --- | --- | --- |
| API FastAPI | Contrato HTTP JSON e documentação OpenAPI | É a stack exigida pela arquitetura e pode ser consumida por URLSession no Swift |
| PostgreSQL e SQLAlchemy | Dados persistidos com índices, relacionamentos e transações | O banco relacional está previsto no projeto; transações evitam confirmação duplicada e sessões inconsistentes |
| Migrações Alembic | Versão inicial de todas as tabelas de autenticação | Evoluir o banco de forma rastreável, sem recriar tabelas em cada inicialização |
| Cadastro pendente | Conta ativa só é criada após confirmar código e senha | O fluxo principal do UC01 exige confirmação antes de acessar o app |
| Código de e-mail | Seis dígitos, inclusive zeros iniciais, duração de 60 segundos, uso único | Atende RN02 e RNF-007; expiração e reenvio são controlados pelo servidor |
| Reenvio | Disponível após 60 segundos; substitui o código anterior | Atende FA02 e impede uso paralelo de códigos antigos |
| bcrypt | Custo 12 por padrão, mínimo 10; senhas nunca persistidas em texto | Atende RNF-006 e dificulta recuperação de senha a partir do banco |
| OTP com HMAC | Persistido como digest usando segredo separado | Um código tem poucas combinações; hash simples seria insuficiente contra enumeração offline |
| JWT de acesso | Expira em 15 minutos e identifica usuário e sessão | Autoriza chamadas sem transportar senha; valida assinatura, emissor e destinatário |
| Refresh opaco | Sete dias de duração absoluta, rotação e detecção de reutilização | Mantém o usuário conectado e permite revogar sessões comprometidas |
| Logout efetivo | Revoga refresh e acesso da sessão no banco | JWT de uma sessão encerrada para de funcionar antes de seu vencimento |
| Perfil `/users/me` | Retorna apenas o usuário autenticado | Estabelece o isolamento que os futuros módulos usarão, conforme RNF-008 |
| Recuperação de senha | Token aleatório de 15 minutos, uso único; revoga sessões | Evita contas sem recuperação e impede manter sessões antigas após redefinir senha |
| Encerramento e limpeza | Bloqueia acesso imediatamente; job elimina dados ativos | Dá suporte ao requisito de exclusão em até 30 dias |
| Limites persistidos | Contadores PostgreSQL por IP/e-mail | Impede que reiniciar a API ou usar vários processos elimine a proteção contra abuso |
| Logs mínimos | Eventos, horário e IDs; sem senha, OTP ou tokens | Permite investigar falhas sem gravar credenciais |
| Erros padronizados | Código estável, mensagem pt-BR e request ID | Facilita o tratamento no Swift e evita expor entradas sensíveis |
| Docker | API, banco, caixa de e-mail de teste e limpeza | Reproduz o ambiente e facilita o deploy no Coolify |
| CI | Lint, formato, testes, cobertura, migrações e build | Impede publicar uma alteração sem passar pelas verificações |

O documento chama a confirmação inicial de “2FA”. Aqui ela combina senha e código de e-mail no cadastro. Isso não representa MFA obrigatório em todos os logins. `email_verified_at` registra a confirmação; não usamos `dois_fatores_ativo` para afirmar uma proteção permanente inexistente.

## Decisões de arquitetura

O backend é um monólito modular: uma aplicação com responsabilidades separadas. O login não precisa de microsserviços, Kubernetes ou fila distribuída. A API concentra validação e acesso ao banco; o iPhone não recebe credenciais de PostgreSQL.

Foi escolhida Oracle + Coolify porque o responsável já usa essa infraestrutura. O usuário confirmou que os documentos podem ser atualizados para substituir AWS. PostgreSQL permanece, e o app continuará independente do provedor porque consome HTTPS.

Firebase Authentication é uma alternativa possível, mas esta entrega usa autenticação própria para cumprir exatamente o contrato documentado de bcrypt, OTP e sessões. Não existem duas autoridades de login.

O DER antigo usa nomes em português e inclui telefone. A API usa `users.name`, `users.email` e `users.password_hash`, equivalentes a nome, e-mail e senha_hash; o cadastro não coleta telefone porque o UC01 pede apenas nome/e-mail/senha. Foram adicionadas tabelas próprias de segurança, sem criar tabelas das funcionalidades agrícolas ainda não implementadas.

## Estrutura

```text
app/
  main.py                  aplicação, health checks e erros
  core/                    configuração e segurança
  db/                      modelos, conexão e locks PostgreSQL
  modules/auth/            schemas, rotas, regras e limites
  integrations/email.py    SMTP com TLS em produção
  jobs/cleanup.py          limpeza e exclusão de contas
migrations/                evolução versionada do banco
tests/                     testes unitários e integração real
scripts/                   configuração local e exportação OpenAPI
docs/                      contrato, deploy, progresso e plano
```

## Executar com Docker

Requisitos: Docker Engine/Desktop funcionando e Docker Compose. Para desenvolvimento Python fora do container, usar Python 3.13.

No PowerShell, entre na pasta deste README e execute:

```powershell
python scripts/setup_local.py
docker compose up --build -d
docker compose ps
```

O script gera `.env` com segredos aleatórios locais e preserva qualquer arquivo existente. A aplicação de migrações termina antes de iniciar API e limpeza. Não envie `.env` ao Git.

- API: http://localhost:8000
- Swagger local: http://localhost:8000/docs
- E-mails de teste no Mailpit: http://localhost:8025
- Saúde: http://localhost:8000/health/ready

Os códigos ficam na caixa Mailpit durante desenvolvimento. Não são retornados pela API. O PostgreSQL local expõe a porta 54329 exclusivamente em `127.0.0.1`; em produção o banco deve ser privado sem publicação de porta.

```powershell
docker compose logs api
docker compose stop
```

`stop` preserva o volume. Não use remoção de volumes se quiser manter os dados.

## Executar Python localmente

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
python scripts/setup_local.py
docker compose up -d db mailpit
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

`requirements.lock` fixa as dependências de desenvolvimento; `requirements-prod.lock` contém somente execução. Os locks foram resolvidos com corte de publicação em 06/09/2026, respeitando a regra de dependências estáveis publicadas há pelo menos 30 dias. O Dockerfile usa o lock de produção e executa com usuário sem privilégios.

Nesta máquina, o Docker Desktop apresentou falhas de sockets Windows e o Ubuntu antigo estava cadastrado com VHDX ausente. A validação inicial usou os binários PostgreSQL 17.4 já instalados, com um cluster novo em `.runtime/pgdata` na porta 54329. Nenhum banco existente foi reutilizado. O alvo do Compose e CI é PostgreSQL 18. Consulte `docs/environment.md` para o registro desses ajustes; não execute dois servidores na mesma porta.

## Testes e qualidade

Os testes de integração precisam de PostgreSQL real. Eles recriam tabelas e recusam qualquer banco cujo nome não termine em `_test`. Nunca aponte os testes para o banco de produção.

Crie uma vez o banco `agrolab_test` com o usuário local. Depois configure a URL de teste sem copiar segredos para o histórico:

```powershell
$env:TEST_DATABASE_URL = & .\.venv\Scripts\python.exe -c "from app.core.config import Settings; from sqlalchemy.engine import make_url; print(make_url(Settings().database_url).set(database='agrolab_test').render_as_string(hide_password=False))"
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing --cov-fail-under=70
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\alembic.exe check
```

Cobertura mínima exigida: 70%. Os testes verificam limites exatos de expiração, confirmação única, reenvio, contas duplicadas, falha de e-mail, isolamento, JWT adulterado, logout, replay de refresh, redefinição de senha, exclusão e concorrência com o job de limpeza.

Uma revisão independente identificou ordem de locks divergente, distinção de contas em falha SMTP e disputas com a limpeza. Foram adicionados testes que reproduziram os erros e passaram após a correção. Limites e revogações de respostas esperadas são confirmados no banco mesmo quando a API retorna erro; desfazer essas transações permitiria ignorar as tentativas ou manter sessões comprometidas.

## API e consumo pelo Swift

O contrato completo está em `docs/openapi.json` e o guia em `docs/api.md`.

| Método | Rota | Finalidade |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Criar cadastro pendente |
| POST | `/api/v1/auth/verify-email` | Confirmar código e senha |
| POST | `/api/v1/auth/resend-code` | Reenviar após 60 segundos |
| POST | `/api/v1/auth/login` | Entrar |
| POST | `/api/v1/auth/refresh` | Renovar e rotacionar tokens |
| POST | `/api/v1/auth/logout` | Encerrar sessão |
| GET | `/api/v1/users/me` | Ler perfil autenticado |
| POST | `/api/v1/auth/forgot-password` | Solicitar recuperação |
| POST | `/api/v1/auth/reset-password` | Definir nova senha |
| DELETE | `/api/v1/users/me` | Encerrar conta, confirmando senha |

No Swift: usar URLSession e Codable; refresh no Keychain, access preferencialmente em memória. A senha do cadastro deve ser mantida somente em memória até confirmar o código e descartada em seguida. Não guardar senha ou tokens em UserDefaults. Serializar renovações: duas chamadas de refresh para o mesmo token podem revogar a sessão por detecção de replay.

## Regras e limites

- Senha: mínimo de 12 caracteres, máximo de 72 bytes UTF-8; bcrypt não deve truncar senha. E-mails normalizados para minúsculas; não removemos pontos ou aplicamos regras específicas do Gmail.
- Código: expira quando o relógio do servidor atinge 60 segundos. Após cinco erros de código/senha, o desafio é invalidado; reenviar não limpa esse contador.
- Login: até cinco falhas por e-mail e 30 tentativas por IP a cada janela de 15 minutos.
- Cadastro, reenvio e recuperação compartilham limites de cinco envios por e-mail e 20 por IP em uma hora.
- As janelas de limite são fixas, alinhadas pelo relógio UTC; todas as atualizações são atômicas no banco.
- `429` inclui `Retry-After`. O app deve respeitar o prazo do servidor.
- Cadastro e recuperação têm respostas genéricas. `202` significa solicitação aceita, não confirmação de entrega SMTP. Falhas são registradas internamente, preservando a resposta externa indistinguível; reenvio continua disponível após o intervalo.
- JWT contém apenas claims de segurança. Toda rota autenticada verifica também o estado da sessão e da conta no banco.
- Logs de acesso HTTP são desativados no comando de execução para evitar URLs sensíveis; os eventos da aplicação têm IDs para investigação.

## Produção e hospedagem

Endereço previsto: `https://api-agrolab.jamesmarcos.com`. Coolify existente: `https://coolify.jamesmarcos.com`. A VPS foi inspecionada por SSH: ARM/aarch64, aproximadamente 12 GB RAM; há outros projetos ativos. O deploy deve usar recursos e bancos próprios do AgroLab.

`docs/deploy.md` registra variáveis, rede privada, proxy confiável, migrações, backup e rollback. A API de produção exige HTTPS, SMTP autenticado com TLS, segredos distintos e emissor/destinatário JWT próprios. Swagger fica desabilitado em produção.

O DNS sozinho não publica a API: é necessário configurar o aplicativo no Coolify, certificado, e-mail, job de limpeza e backups. O backup externo deve ser criptografado e testado por restauração; retenção proposta de 14 dias. Criptografia do volume Oracle não acompanha automaticamente um dump exportado.

## Limitações e próximas entregas

O backend não implementa diagnóstico, culturas, histórico, sincronização ou AgroBot. A ausência do projeto Swift impede validar a tela no iPhone nesta pasta. Publicação depende da configuração de DNS/Coolify e do remetente real de e-mail. A disponibilidade de 99% e capacidade de 500 usuários precisam de monitoramento e teste de carga; não são garantidas por um container funcionando.

Os três DOCX ainda precisam refletir Oracle/Coolify e a configuração efetiva de redundância, criptografia e recuperação. `docs/progress.md` mantém o estado da implementação e o que foi verificado, sem confundir código entregue com infraestrutura ainda pendente.
