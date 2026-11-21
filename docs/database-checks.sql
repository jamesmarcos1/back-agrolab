-- AgroLab: acompanhamento manual, sem consultar senhas ou tokens.
-- Executar conectado ao banco agrolab, com psql.
\set ON_ERROR_STOP on
\pset pager off

BEGIN READ ONLY;
SET LOCAL statement_timeout = '10s';
SET LOCAL TIME ZONE 'America/Sao_Paulo';

-- 1. Usuarios que concluiram a confirmacao e contas aguardando exclusao.
SELECT status, COUNT(*) AS quantidade
FROM users
GROUP BY status
ORDER BY status;

-- 2. Cadastros pendentes ainda nao confirmados.
-- Esta contagem nao representa contas ativas nem garantia de entrega SMTP.
-- inert identifica solicitacoes que nao podem criar outra conta existente.
SELECT
    COUNT(*) FILTER (
        WHERE consumed_at IS NULL AND NOT inert AND expires_at > NOW()
    ) AS pendentes_nao_confirmados,
    COUNT(*) FILTER (
        WHERE consumed_at IS NOT NULL
    ) AS confirmados_ainda_na_tabela_temporaria,
    COUNT(*) FILTER (
        WHERE consumed_at IS NULL AND expires_at <= NOW()
    ) AS expirados_aguardando_limpeza
FROM pending_registrations;

-- 3. Ultimas 20 contas confirmadas, com email parcialmente oculto.
SELECT
    id,
    LEFT(SPLIT_PART(email, '@', 1), 2) || '***@' ||
        SPLIT_PART(email, '@', 2) AS email_parcial,
    status,
    email_verified_at,
    created_at
FROM users
ORDER BY created_at DESC
LIMIT 20;

-- 4. Eventos de autenticacao nas ultimas 24 horas.
SELECT event, COUNT(*) AS quantidade, MAX(at) AS ultima_ocorrencia
FROM auth_events
WHERE at >= NOW() - INTERVAL '24 hours'
GROUP BY event
ORDER BY quantidade DESC, event;

-- 5. Ultimos 30 eventos: correlacionar request_id com erro no app/log da API.
SELECT at, event, request_id
FROM auth_events
ORDER BY at DESC
LIMIT 30;

-- 6. Sessoes ainda utilizaveis de usuarios ativos.
SELECT COUNT(*) AS sessoes_validas
FROM sessions AS s
JOIN users AS u ON u.id = s.user_id
WHERE s.revoked_at IS NULL
    AND s.expires_at > NOW()
    AND u.status = 'active';

-- 7. Pedidos de exclusao ainda presentes na fila.
SELECT COUNT(*) AS exclusoes_na_fila, MIN(requested_at) AS pedido_mais_antigo
FROM deletion_requests
WHERE completed_at IS NULL;

ROLLBACK;
