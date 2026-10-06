class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, retry_after: int | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


def invalid_credentials():
    return APIError(401, "INVALID_CREDENTIALS", "E-mail ou senha incorretos.")


def invalid_session():
    return APIError(401, "INVALID_SESSION", "Sua sessão expirou. Entre novamente.")


def invalid_code():
    return APIError(400, "INVALID_CODE", "Código inválido, expirado ou já utilizado.")
