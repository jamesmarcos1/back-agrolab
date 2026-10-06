"""Gera segredos locais sem sobrescrever configuração existente."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    raise SystemExit(".env já existe; configuração preservada.")
password = secrets.token_hex(24)
text = (root / ".env.example").read_text(encoding="utf-8")
text = text.replace("agrolab:CHANGE_ME@", f"agrolab:{password}@")
text = text.replace("POSTGRES_PASSWORD=CHANGE_ME", f"POSTGRES_PASSWORD={password}")
text = text.replace("JWT_SECRET=CHANGE_ME", f"JWT_SECRET={secrets.token_hex(32)}")
text = text.replace("OTP_SECRET=CHANGE_ME", f"OTP_SECRET={secrets.token_hex(32)}")
target.write_text(text, encoding="utf-8")
print(".env criado com segredos locais. Não envie este arquivo ao Git.")
