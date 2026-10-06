"""Exporta somente o contrato público, sem configurações ou dados do banco."""

import json
from pathlib import Path

from app.main import create_app

root = Path(__file__).resolve().parents[1]
app = create_app()
(root / "docs" / "openapi.json").write_text(
    json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8"
)
app.state.engine.dispose()
print("docs/openapi.json exportado")
