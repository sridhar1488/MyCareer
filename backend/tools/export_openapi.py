"""Export the public contract without accessing a database or reading local secrets."""

import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app

app = create_app(
    Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite://",
        secret_key="openapi-generation-only-not-a-credential",
    )
)
output = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
output.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
app.state.engine.dispose()
print(f"Public OpenAPI contract exported to {output.name}")
